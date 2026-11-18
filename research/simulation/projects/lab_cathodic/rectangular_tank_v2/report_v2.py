from pathlib import Path
import csv
import json
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent


def comsol_row(path):
    rows = [line for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip() and not line.startswith("%")]
    values = next(csv.reader(rows[-1:]))
    result = [float(v) for v in values]
    assert all(math.isfinite(v) for v in result), path
    return result


def fields(case):
    return [comsol_row(HERE / f"{case}_point_{d}m.csv")[4]
            for d in ("05", "2", "3", "4")]


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


base = fields("baseline")
cases = {name: fields(name) for name in (
    "negative_earth", "positive_earth", "proxy_0001", "proxy_001", "coarse", "wide")}
water = comsol_row(HERE / "baseline_water.csv")[1:]
legacy = HERE / "legacy_half_meter"
old_cp = read_csv(legacy / "round_v4_with_0p5m.csv")
cable = read_csv(legacy / "v13_electric_with_0p5m.csv")
chassis = read_csv(legacy / "v14_electric_with_0p5m.csv")
pe = read_csv(legacy / "v14_pe_with_0p5m.csv")
distance_labels = ("0.5", "2", "3", "4")


def distance_fields(row):
    return tuple(float(row[f"field_{d.replace('.', 'p')}m_V_per_m"]) for d in distance_labels)


rows = [("新方箱 20 V，平衡差模", "DC近静态", *base)]
for old in old_cp:
    rows.append((f"原圆桶 {old['measured_voltage_V']} V", "DC近静态",
                 *distance_fields(old)))
for frequency in (30, 50):
    old = next(r for r in cable if r["source"] == f"diff{frequency}")
    rows.append((f"电机电缆 {frequency} Hz 差模", "额定基线，RMS", *distance_fields(old)))
for frequency in (4000, 100000):
    for mode, label in (("chassis_cm", "泵/电机机壳"), ("cable_cm", "电机电缆")):
        selected = next(r for r in chassis if float(r["frequency_hz"]) == frequency and r["source"] == mode)
        rows.append((f"{label} {frequency//1000} kHz", "每1 V RMS共模",
                     *distance_fields(selected)))
rows.append(("PE回流 100 kHz 感应场", "每1 A RMS回流",
             *distance_fields(next(r for r in pe if float(r["frequency_hz"]) == 100000))))

with (HERE / "comparison.csv").open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["source", "excitation_basis", "field_0p5m_V_per_m", "field_2m_V_per_m", "field_3m_V_per_m", "field_4m_V_per_m"])
    writer.writerows(rows)
checks = {name: [abs(v / b - 1) for v, b in zip(values, base)]
          for name, values in cases.items() if name in ("coarse", "wide", "proxy_0001", "proxy_001")}
(HERE / "verification.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
fig, ax = plt.subplots(figsize=(15, 7.8), dpi=170)
ax.axis("off")
fig.suptitle("独立模型场强对照：外壁起算 0.5 / 2 / 3 / 4 m，离地 0.5 m", fontsize=17, y=.97)
table = ax.table(cellText=[[r[0], r[1], *(f"{x:.3e}" for x in r[2:])] for r in rows],
                 colLabels=["模型 / 信号源", "输入口径", "0.5 m", "2 m", "3 m", "4 m"],
                 colWidths=[.26, .18, .14, .14, .14, .14], bbox=[0,.12,1,.82], cellLoc="center")
table.auto_set_font_size(False)
table.set_fontsize(11)
for (row, col), cell in table.get_celld().items():
    cell.set_edgecolor("white")
    if row == 0:
        cell.set_facecolor("#243e4b")
        cell.set_text_props(color="white", weight="bold")
    else:
        cell.set_facecolor("#e4f0ee" if row == 1 or col == 2 else ("#f0f2f4" if row % 2 else "#ffffff"))
ax.text(0,.045,"场强单位：V/m。1 V共模与1 A回流是不同口径的单位参考，不是现场幅值。新旧几何、方向和环境不同。",fontsize=10,transform=ax.transAxes)
fig.savefig(HERE / "comparison.png", bbox_inches="tight", facecolor="white")
plt.close(fig)

lines = [
    "# 方形浅水箱 V2：20 V 与外部电场",
    "",
    "[已求解外场工程](rectangular_tank_20V_external_v2.mph) · [直观布局工程](rectangular_tank_layout_v2.mph) · [分类目录](../README.md)",
    "",
    "## 本次更改",
    "",
    "- 内宽改为已确认的20 cm；内长48 cm、内高30 cm、塑料壁厚4 mm仍为暂定值。",
    "- 石墨棒与钢管窗口在轴向和高度上居中正对。两轴平行横放，石墨棒需绝缘垫高；未细画支座。",
    "- 净间距暂取5 cm，使两电极装入20 cm内宽。窗口20×12 cm、钢管长40 cm/外径10 cm、石墨直径25 mm/长20 cm不变。",
    "- 水面仍高出窗口上缘3 mm，水深10.410 cm，净水量约6.587 L。水电导率沿用500 µS/cm。",
    "- 观测点P位于图中向右的外壁外0.5 m、离地0.5 m。内部坐标原点在箱内底，故P=(0.604,0,0.496) m，地面z=-0.004 m。",
    "- 石墨几何域和六个接液面均已核验。水体/空气的实体显示以及只显示水域的结果会遮挡石墨；布局工程不含遮挡它们的水/空气显示体。",
    "",
    "## 计算含义",
    "",
    "水、空气、箱壁和封装层共用电准静态电势求解，电极为理想等势边界。水电导率0.05 S/m；空气、塑料、胶带设为无直流泄漏介质，相对介电常数分别取1.0006、2.3、3.2。使用1 mHz频域解逼近DC场，并用0.1与10 mHz核验；这些频率不是实验谱峰。",
    "",
    "方程为 div[(sigma+j*omega*epsilon)*grad(V)]=0。空气不能用纯导电稳态方程冒充介电场；本版保留位移电流项。方法参考：[COMSOL频域方程](https://doc.comsol.com/6.3/doc/com.comsol.help.acdc/acdc_ug_theory.05.68.html)。",
    "",
    "20 V作为两理想电极间电压，尚未扣除界面过电位。无电极极化、气泡、温升或电导率随时间变化模型。未添加外部电源机壳、引线、门框和玻璃；地面用理想接地平面替代，有限远边界为0 V。不能将这个条件模型等同于真实20 V电源输出的全部外场。",
    "",
    "## 新结果",
    "",
    f"平衡差模基线：钢管-10 V、石墨+10 V，模型欧姆电流约{water[1]:.4f} A，水中耗散约{water[2]:.3f} W。注意：±10 V是指定的对地平均电位假设，并非已经解出真实浮置电源的共模电位。",
    "",
    "| 对地电位情形 | P，外壁0.5 m | 外壁2 m | 外壁3 m | 外壁4 m |",
    "|---|---:|---:|---:|---:|",
]
for label, values in (("平衡差模：钢管-10 V / 石墨+10 V",base),
                      ("钢管接地参考：0 V / +20 V",cases["negative_earth"]),
                      ("石墨接地参考：-20 V / 0 V",cases["positive_earth"])):
    lines.append("|"+label+"|"+"|".join(f"{v:.4e}" for v in values)+"|")
lines += ["", "单位为V/m。后两行仅为边界敏感性情形，不是已确认接地，也不是严格上下界。只有两端电压，尚不能唯一确定空气外场。", "",
          "## 数值核验", "", "| 检查 | P变化 | 2 m变化 | 3 m变化 | 4 m变化 |",
          "|---|---:|---:|---:|---:|"]
for name in checks:
    lines.append("|"+name+"|"+"|".join(f"{100*v:.3f}%" for v in checks[name])+"|")
lines += ["", "coarse为局部网格从水域9→12 mm、近空气60→90 mm、中空气250→350 mm的对照；wide为外域半宽/高度10→15 m。P的场强对这两项变动较稳定，4 m的弱场对外边界较敏感，只用来比较量级。数值稳定性不代表模型假设与现场一致。", "",
          "## 与旧模型对照", "", "旧圆桶、V13、V14新增0.5 m空气点，坐标为(0,-0.78,0.5) m，沿用旧工程朝门方向。圆桶从已存单位差模解直接取点，V13/V14按原工况复算。2、3、4 m保留旧表数值并用复算结果核验。模型不合并，原工程不覆盖。各行从各自容器外壁起算，方向和周围环境不完全相同。DC与AC RMS只比较量级，不等于MEMS电压响应一致。", "",
          "| 模型 | 输入口径 | 0.5 m | 2 m | 3 m | 4 m |", "|---|---|---:|---:|---:|---:|"]
for row in rows:
    lines.append("|"+row[0]+"|"+row[1]+"|"+"|".join(f"{v:.4e}" for v in row[2:])+"|")
lines += ["", "[对比表图](comparison.png) · [数值表](comparison.csv) · [几何图](tank_electrode_layout.png) · [水中电势](water_potential.png) · [水中电流密度](water_current_density.png) · [P点原始结果](baseline_point_05m.csv)",
          "", "[旧工程新增点及全频段数据](legacy_half_meter/README.md)。潜艇为水下海水场，不混入这张空气场强表排名。",
          "", "## 复现", "", "在本目录执行COMSOL编译器编译RectangularTankExternalV2.java，再用comsolbatch -np 4 -graphics -3drend sw运行类文件；CheckRectangularTankV2.java只加载基线模型做网格和外域核验，不覆盖基线。report_v2.py读取求解导出与旧表生成本说明和对比图。"]
(HERE / "README.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
print(json.dumps({"baseline":base,"water":water,"checks":checks},indent=2))
