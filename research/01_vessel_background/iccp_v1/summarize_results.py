"""Postprocess only this ICCP scenario; no experimental data are read."""
import csv
import argparse
import configparser
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results"
COLS = ["x_m", "y_m", "z_m", "water_potential_V", "Ex_V_m", "Ey_V_m", "Ez_V_m", "normE_V_m"]
AUDIT = ["Vm_V_AgAgCl", "I_ICCP_A", "steel_net_anodic_A", "prop_net_anodic_A", "circuit_residual_A",
         "far_gradient_flux_A", "steel_gradient_residual_A", "prop_gradient_residual_A", "steel_wet_area_m2",
         "prop_wet_area_m2", "anode1_area_m2", "anode2_area_m2", "anode3_area_m2", "anode4_area_m2",
         "steel_eta_min_V", "steel_eta_max_V", "steel_fraction_below_minus_0_8V", "prop_eta_min_V",
         "prop_eta_max_V", "steel_extrapolated_area_fraction", "prop_extrapolated_area_fraction"]


def read_points(path):
    raw = np.loadtxt(path, delimiter=",", comments="%", encoding="utf-8-sig")
    return raw.reshape(8, -1).T


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(fields); w.writerows(rows)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base-only',action='store_true')
    args=parser.parse_args()
    config=configparser.RawConfigParser();config.optionxform=str
    config.read_string('[parameters]\n'+(ROOT/'parameters.properties').read_text(encoding='ascii'))
    parameters=dict(config['parameters'])
    audits = {}
    for p in OUT.glob("*_audit.csv"):
        name = p.name.removesuffix("_audit.csv")
        if args.base_only and not name.startswith('base_'):continue
        audits[name] = dict(zip(AUDIT, np.loadtxt(p, comments="%", delimiter=",", encoding="utf-8-sig")))
    base_cases=sorted([n for n in audits if n.startswith('base_')],key=lambda n:audits[n]['I_ICCP_A'])
    case_order=base_cases+sorted(n for n in audits if not n.startswith('base_'))
    nominal_text=parameters['I_total'].split('[')[0]
    nominal=float(nominal_text)
    selected=min(base_cases,key=lambda n:abs(audits[n]['I_ICCP_A']-nominal))
    suffix=selected.removeprefix('base_')
    all_side = []
    for p in OUT.glob("*_side.csv"):
        if "_tidy" in p.stem:
            continue
        name = p.stem.removesuffix("_side")
        if name not in audits:continue
        for mode in ["side", "axial", "plane"]:
            data = read_points(OUT / f"{name}_{mode}.csv")
            write_csv(OUT / f"{name}_{mode}_tidy.csv", COLS, data)
            if mode == "side":
                all_side.extend([[name, audits[name]["I_ICCP_A"], *row[:3], *(row[4:] * 1e6)] for row in data])
    write_csv(OUT / "field_distance_comparison.csv",
              ["case", "I_ICCP_A", "x_m", "y_m", "z_m", "Ex_uV_m", "Ey_uV_m", "Ez_uV_m", "normE_uV_m"], all_side)
    off=next(n for n in base_cases if audits[n]['I_ICCP_A']==0)
    background=read_points(OUT/f'{off}_side.csv')
    changes=[]
    for name in base_cases:
        sample=read_points(OUT/f'{name}_side.csv')
        np.testing.assert_allclose(sample[:,:3],background[:,:3],atol=1e-9)
        difference=sample[:,4:7]-background[:,4:7]
        for i,row in enumerate(sample):
            changes.append([name,audits[name]['I_ICCP_A'],row[1],background[i,7]*1e6,row[7]*1e6,
                            *(difference[i]*1e6),np.linalg.norm(difference[i])*1e6])
    write_csv(OUT/'iccp_induced_field_change.csv',
              ['case','I_ICCP_A','side_offset_m','off_normE_uV_m','on_normE_uV_m',
               'deltaEx_uV_m','deltaEy_uV_m','deltaEz_uV_m','delta_vector_norm_uV_m'],changes)
    write_csv(OUT / "circuit_audit_summary.csv", ["case", *AUDIT],
              [[name, *(audits[name][k] for k in AUDIT)] for name in case_order])
    colors = ["#555555", "#007e8a", "#d44e36", "#8a568f"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout="constrained")
    for color, name in zip(colors, base_cases):
        current=audits[name]['I_ICCP_A']
        a = read_points(OUT / f"{name}_axial.csv")
        b = read_points(OUT / f"{name}_side.csv")
        axes[0].plot(a[:, 0], a[:, 7]*1e6, label=f"ICCP {current} A", color=color)
        axes[1].loglog(b[:, 1], b[:, 7]*1e6, "o-", label=f"ICCP {current} A", color=color)
    axes[0].set(xlabel="Longitudinal x (m)", ylabel="Electric-field magnitude (uV/m)", title="20 m below keel; y = 0")
    axes[1].set(xlabel="Side offset from centerline (m)", ylabel="Electric-field magnitude (uV/m)", title="Same depth as hull center; x = 0")
    for ax in axes: ax.grid(alpha=.25); ax.legend()
    fig.savefig(OUT / "current_and_distance_comparison.png", dpi=180); plt.close(fig)
    data = read_points(OUT / f"{selected}_plane.csv")
    xx, yy = data[:,0].reshape(41,81), data[:,1].reshape(41,81)
    fig, ax = plt.subplots(figsize=(10,5.2), layout="constrained")
    c = ax.pcolormesh(xx,yy,data[:,7].reshape(41,81)*1e6,cmap="inferno",shading="auto")
    ax.quiver(xx[::4,::4],yy[::4,::4],data[:,4].reshape(41,81)[::4,::4],data[:,5].reshape(41,81)[::4,::4],color="white",alpha=.7)
    ax.set(xlabel="Longitudinal x (m)",ylabel="Transverse y (m)",title=f"ICCP {nominal:g} A: external electric field",aspect="equal")
    fig.colorbar(c,ax=ax,label="|E| (uV/m)")
    fig.savefig(OUT / "external_field_plane.png",dpi=180);plt.close(fig)
    fig, axes = plt.subplots(1,2,figsize=(10,4.5),layout="constrained")
    for ax,name in zip(axes,["hy80","nab"]):
        t=np.loadtxt(ROOT/"data"/f"{name}_polarization.csv",delimiter=",",skiprows=1)
        ax.plot(t[:,1],t[:,0],color="#0077a8",linewidth=2)
        ax.set_xscale("symlog",linthresh=.003);ax.axvline(0,color=".6",linewidth=.7)
        ax.set(xlabel="Net anodic current density (A/m2)",ylabel="Potential (V vs Ag/AgCl)",title=name.upper());ax.grid(alpha=.25)
    fig.savefig(OUT/"polarization_curves.png",dpi=180);plt.close(fig)
    checks={}
    for label,left,right in [("mesh",selected,f"fine_{suffix}"),("outer_domain",f"fine_{suffix}",f"wide_{suffix}")]:
        if left not in audits or right not in audits:continue
        for mode in ["axial","side"]:
            a,b=read_points(OUT/f"{left}_{mode}.csv"),read_points(OUT/f"{right}_{mode}.csv")
            error=np.linalg.norm(a[:,4:7]-b[:,4:7],axis=1)/np.maximum(np.linalg.norm(b[:,4:7],axis=1),1e-30)
            checks[f"{label}_{mode}_max_percent"]=float(error.max()*100)
            if mode=='axial':
                checks[f"{label}_{mode}_within_100m_max_percent"]=float(error[np.abs(b[:,0])<=100.000001].max()*100)
    report=["# 三维潜艇 ICCP 初版模型", "", "完成日期：2026-10-18。独立新建工程，未改旧模型及实验数据。", "",
      "## 模型性质", "",
      "采用 Schaefer 等 COMSOL 2011 的三维潜艇/非线性极化建模方法，HY-80 和 NAB 曲线由 Thiel 等 2020 图3b、3d矢量路径数字化。几何、阳极位置及部分参数为明确假设，因此属于论文方法参考算例，不是某篇文章的完整数值复现或某型号实艇标定。", "",
      "## 参数与回路", "",
      "- 长50 m、宽6 m，艇体中心浸深20 m；椭球艇体、指挥台、十字舵、轴及圆盘螺旋桨。", 
      "- 海水4 S/m。钢艇体均匀涂层破损率2%，螺旋桨NAB裸露；曲线统一为论文的Ag/AgCl参考。",
      "- 四个独立阳极，前后各一对，纵向位置±12 m；半径0.25 m，绝缘屏蔽半径0.75 m。前后各承担50%总电流。",
      "- 扫描0、5、10、20 A。0 A仅关闭ICCP，仍保留钢与NAB之间的电偶腐蚀。",
      "- 金属连接按理想导体共同电位Vm处理；ICCP正端连阳极，负端连艇体。Vm由所有金属界面净电流与阳极总电流的积分平衡联立求出。",
      "- 水面电绝缘；水域半宽/深度250 m，远边界0 V仅作为电解质参考。艇体未强制接地。初版只算水下稳态场，未加入空气、海底、SACP、旋转、流体与电源纹波。", "",
      "## 方程与数值", "",
      "海水求解 div(J)=0，J=-sigma*grad(phi)；金属表面净阳极电流密度j=f(Vm-phi)，钢表面乘涂层破损率。全局方程 int_steel(j)+int_prop(j)+I_ICCP=0。阳极湿表面均匀注入支路电流，背面与绝缘屏蔽接触，不向水注流。",
      "", "COMSOL Electric Currents加Global Equations，二次四面体、全耦合非线性稳态、PARDISO，求解相对容差1e-7。极化曲线为线性插值，端点线性外推；逐工况记录外推面积比例。",
      "", "## 回路与保护电位", "",
      "-0.8 V仅为展示保护状态的参考判据，不代表完整标准符合性认证。", "",
      "|工况|钢界面净阳极电流/A|螺旋桨净阳极电流/A|回路残差/A|钢表面电位范围/V|低于-0.8V面积比例|",
      "|---|---:|---:|---:|---|---:|"]
    for n in case_order:
        a=audits[n]
        report.append(f"|{n}|{a['steel_net_anodic_A']:.5g}|{a['prop_net_anodic_A']:.5g}|{a['circuit_residual_A']:.3g}|{a['steel_eta_min_V']:.4f} ~ {a['steel_eta_max_V']:.4f}|{a['steel_fraction_below_minus_0_8V']:.2%}|")
    report += ["", "负值表示水中电流进入金属。艇体和螺旋桨电流是求解结果，未预设其回流比例。", "",
      "## 距离场强", "", "下表为同深度、艇体中心侧向偏距，单位uV/m；不是到艇壁的净距离。", "",
      "|ICCP电流|10m|20m|30m|50m|75m|100m|", "|---|---:|---:|---:|---:|---:|---:|"]
    for name in base_cases:
        i=audits[name]['I_ICCP_A']
        e=read_points(OUT/f"{name}_side.csv")[:,7]*1e6
        report.append(f"|{i:g} A|"+"|".join(f"{v:.3g}" for v in e)+"|")
    report += ['', 'ICCP引起的变化另存iccp_induced_field_change.csv，按矢量E(通电)-E(关闭)计算，再取模。这个量包含ICCP导致的腐蚀/回流重分布；它不是两组场强模值直接相减，也不是可任意线性叠加的独立源。', '', '## 数值检查', '']
    for k,v in checks.items():report.append(f"- {k}: {v:.3f}%")
    if checks:
        report += ['', '这组检查支持首版量级与相对趋势估算，但完整纵向测线对远边界仍较敏感，最大外域差异出现在x=150m远端，不能声称全域已充分收敛。不同位置应分别看检查结果；这些数值差异不包括几何、极化曲线数字化、涂层和实际源强的不确定性。']
    report += ["", "整体积分平衡约束残差与有限元电势梯度在边界上的直接通量积分不是同一个指标；后者也完整保留在circuit_audit_summary.csv，不能用全局约束很小替代局部通量或网格检验。网格和外域比较仅针对本次测点及测线，不是全域误差上界。",
      "", "## 参数修改和复现", "",
      "参数入口parameters.properties；GUI中也可直接修改模型全局参数后重建几何/网格并求解。修改曲线可替换插值函数。脚本方式见run_model.ps1。所有参数假设与来源见PARAMETER_SOURCES.md。", "",
      "本轮仅为可运行的首版外场算例。0至20A的当前工况没有达到整艇-0.8V参考判据，不能称为充分保护。未从本模型给出真实艇的探测距离。",
      '', '初版阳极湿表面采用均匀给定电流密度近似，未联立阳极反应过电位、电源输出电压或反馈控制动态。']
    (ROOT/"初版模型说明与结果.md").write_text("\n".join(report)+"\n",encoding="utf-8")
    report += ['', '## 本次参数文件原值', '', '|参数|表达式|','|---|---|']
    report += [f'|{k}|{v}|' for k,v in parameters.items()]
    (ROOT/"初版模型说明与结果.md").write_text("\n".join(report)+"\n",encoding="utf-8")
    manifest={"parameters":parameters,"audits":audits,"checks":checks,"sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/"SubmarineICCP.java",ROOT/"parameters.properties",ROOT/"data"/"hy80_polarization.csv",ROOT/"data"/"nab_polarization.csv"]}}
    (OUT/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps({"checks":checks,"cases":list(audits)},indent=2))


if __name__=="__main__":main()
