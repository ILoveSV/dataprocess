"""Audit and plot the isolated generic-vessel COMSOL calculation."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from background_field_reference_20260927 import halfspace, source_pair

DATA = HERE / "comsol"
OUT = HERE / "results"
CASES = ("base", "fine", "wide", "benchmark")
COLS = ("x_m", "y_m", "z_m", "phi_V", "Ex_V_m", "Ey_V_m", "Ez_V_m", "E_norm_V_m")


def read_points(path: Path, n: int) -> np.ndarray:
    raw = np.loadtxt(path, comments="%", delimiter=",")
    if raw.ndim != 1 or raw.size != 8 * n:
        raise ValueError(f"Unexpected stationary point table shape in {path}: {raw.shape}")
    points = raw.reshape(8, n).T
    if not np.all(np.isfinite(points)):
        raise ValueError(f"Nonfinite values in {path}")
    np.testing.assert_allclose(np.linalg.norm(points[:, 4:7], axis=1), points[:, 7], rtol=1e-10)
    return points


def vector_error(a, b):
    return np.linalg.norm(a[:, 4:7] - b[:, 4:7], axis=1) / np.maximum(b[:, 7], 1e-30)


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def figure_save(fig, name):
    fig.savefig(OUT / f"{name}.png", dpi=180, bbox_inches="tight")
    fig.savefig(OUT / f"{name}.svg", bbox_inches="tight")
    plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    compiled = HERE / "GenericSubmarineDC.class"
    if compiled.stat().st_mtime < (HERE / "GenericSubmarineDC.java").stat().st_mtime:
        raise RuntimeError("The Java source must be recompiled before using these results.")
    required = [DATA / f"{case}.mph" for case in CASES]
    required += [DATA / f"{case}_audit.csv" for case in CASES]
    required += [DATA / f"{case}_{medium}_{kind}.csv" for case in CASES for medium in ("water", "air") for kind in ("line", "side")]
    if any(not p.exists() or p.stat().st_mtime < compiled.stat().st_mtime for p in required):
        raise RuntimeError("Missing or stale model exports: wait for all four current cases to finish.")
    plt.rcParams.update({"font.sans-serif": ["Microsoft YaHei"], "axes.unicode_minus": False, "font.size": 10})
    tables = {(case, medium, kind): read_points(DATA / f"{case}_{medium}_{kind}.csv", 61 if kind == "line" else 6)
              for case in CASES for medium in ("water", "air") for kind in ("line", "side")}
    for (case, medium, kind), values in tables.items():
        np.testing.assert_allclose(values[:, 2], (-65 if kind == "line" else -20) if medium == "water" else (25 if kind == "line" else 1), atol=1e-9)
        write_csv(OUT / f"{case}_{medium}_{kind}_tidy.csv", [dict(zip(COLS, row)) for row in values], COLS)

    audit = {case: np.loadtxt(DATA / f"{case}_audit.csv", comments="%", delimiter=",") for case in CASES}
    for case in CASES:
        assert len(audit[case]) == 11
    for case in CASES[:3]:
        assert abs(audit[case][0]) < 1e-8, f"Unbalanced prescribed source: {case}"
        np.testing.assert_allclose(audit[case][1:3], [1, 1], atol=1e-8)

    errors = []
    for medium in ("water", "air"):
        for kind in ("line", "side"):
            for label, a, b in (("mesh", "base", "fine"), ("outer_domain", "fine", "wide")):
                v = vector_error(tables[a, medium, kind], tables[b, medium, kind])
                for xyz, err in zip(tables[b, medium, kind][:, :3], v):
                    errors.append(dict(check=label, medium=medium, sampling=kind, x_m=xyz[0], y_m=xyz[1], z_m=xyz[2], vector_relative_error=err))

    currents, positions = source_pair(current=1, separation=10, depth=20)
    benchmark = []
    for medium in ("water", "air"):
        for kind in ("line", "side"):
            v = tables["benchmark", medium, kind]
            phi, exact = halfspace(currents, positions, v[:, :3], medium=medium)
            exact = exact.real
            denom = np.linalg.norm(exact, axis=1)
            err = np.linalg.norm(v[:, 4:7] - exact, axis=1) / denom
            for xyz, e, ex, pe, pex, re in zip(v[:, :3], v[:, 4:7], exact, v[:, 3], phi.real, err):
                benchmark.append(dict(medium=medium, sampling=kind, x_m=xyz[0], y_m=xyz[1], z_m=xyz[2], field_numeric_V_m=np.linalg.norm(e), field_exact_V_m=np.linalg.norm(ex), phi_numeric_V=pe, phi_exact_V=pex, vector_relative_error=re))
    write_csv(OUT / "convergence.csv", errors, list(errors[0]))
    write_csv(OUT / "analytic_benchmark.csv", benchmark, list(benchmark[0]))

    summary = {}
    for key, rows in (("convergence", errors), ("analytic_benchmark", benchmark)):
        for medium in ("water", "air"):
            for kind in ("line", "side"):
                for check in (("mesh", "outer_domain") if key == "convergence" else ("benchmark",)):
                    subset = [r for r in rows if r["medium"] == medium and r["sampling"] == kind and r.get("check", "benchmark") == check]
                    summary[f"{check}_{medium}_{kind}_max_percent"] = 100 * max(r["vector_relative_error"] for r in subset)

    distances = []
    for medium in ("water", "air"):
        for k, row in enumerate(tables["wide", medium, "side"]):
            mesh_err = vector_error(tables["base", medium, "side"], tables["fine", medium, "side"])[k]
            outer_err = vector_error(tables["fine", medium, "side"], tables["wide", medium, "side"])[k]
            bench_err = [r["vector_relative_error"] for r in benchmark if r["medium"] == medium and r["sampling"] == "side"][k]
            distances.append(dict(medium=medium, horizontal_offset_m=row[1], z_m=row[2], E_uV_m_per_A=row[7]*1e6,
                                  Ex_uV_m_per_A=row[4]*1e6, Ey_uV_m_per_A=row[5]*1e6, Ez_uV_m_per_A=row[6]*1e6,
                                  mesh_change_percent=100*mesh_err, outer_change_percent=100*outer_err,
                                  benchmark_error_percent=100*bench_err,
                                  all_three_within_5_percent=bool(max(mesh_err, outer_err, bench_err) <= .05)))
    write_csv(OUT / "unit_current_distance.csv", distances, list(distances[0]))

    fig, ax = plt.subplots(figsize=(10, 6.3), layout="constrained")
    ax.axhspan(-75, 0, color="#deeff5")
    ax.axhline(0, color="#286b83", lw=1.5)
    ax.add_patch(Ellipse((0, -20), 50, 6, facecolor="#727d82", edgecolor="#323b40"))
    ax.scatter([12, -20], [-20, -20], c=["#c64c48", "#286b83"], s=45, zorder=5)
    ax.text(0, -9, "通用艇体：长50 m，宽/高6 m，中心深20 m", ha="center")
    ax.text(35, 3, "平坦水面 z=0", color="#286b83")
    ax.axhline(25, color="#c64c48", ls="--", label="空气测线 z=+25 m")
    ax.axhline(-65, color="#286b83", ls="--", label="水下测线 z=-65 m")
    ax.set(xlim=(-80, 80), ylim=(-78, 36), xlabel="沿艇长坐标 x / m", ylabel="竖向坐标 z / m",
           title="舰艇背景小模型：几何与测线（非具体型号，源流分区为假设）")
    ax.legend(loc="lower right")
    ax.set_aspect("equal", adjustable="box")
    figure_save(fig, "01_geometry")

    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True, layout="constrained")
    lim = max(np.max(np.abs(tables["wide", medium, "line"][:, 4:7]))*1e6 for medium in ("water", "air"))*1.1
    for ax, medium, label in zip(axes, ("water", "air"), ("水下 z=-65 m", "空气 z=+25 m")):
        v = tables["wide", medium, "line"]
        for i, color in zip(range(3), ("#286b83", "#a16b29", "#c64c48")):
            ax.plot(v[:, 0], v[:, i+4]*1e6, label=("Ex", "Ey", "Ez")[i], color=color)
        ax.set(title=label, ylabel="场分量 / (μV/m)/A", ylim=(-lim, lim))
        ax.grid(alpha=.2);ax.legend(ncol=3)
    axes[-1].set_xlabel("沿艇长测线坐标 x / m（静态空间分布，不是时间波形）")
    fig.suptitle("规定源流的通用艇体单位响应；不代表实艇已知电流")
    figure_save(fig, "02_field_lines")

    fig, ax = plt.subplots(figsize=(9, 4.8), layout="constrained")
    for medium, label, color in (("water", "水下：同深度 z=-20 m", "#286b83"), ("air", "空气：水面上1 m", "#c64c48")):
        v = tables["wide", medium, "side"]
        ax.semilogy(v[:, 1], v[:, 7]*1e6, "o-", color=color, label=label)
    ax.set(xlabel="艇中侧向水平偏距 / m", ylabel="电场模 / (μV/m)/A", title="距离响应：1 A归一化，两条曲线不是相同源距")
    ax.grid(alpha=.2);ax.legend()
    figure_save(fig, "03_distance")

    lines = ["# 数值结果与核验", "", "更新：2026-09-28。所有数值均为规定源流的通用艇体计算，不是实艇测量或TC灵敏度。", "",
             "## 当前模型层级", "", "公开尺度50 m/20 m；艇宽6 m、分布式源流形状为假设。水中EC与空气ES耦合。源强采用1 A归一化，未求非线性极化。", "",
             "## 单位源流距离表", "", "取扩大外域wide结果。表中单位为μV/m每安培；只有固定源流形状和线性介质时才可按实际等效支路电流缩放。",
             "", "| 水平偏距 | 水下，同深度 | 空气，水面上1 m |", "|---:|---:|---:|"]
    for w, a in zip([r for r in distances if r["medium"] == "water"], [r for r in distances if r["medium"] == "air"]):
        lines.append(f"| {w['horizontal_offset_m']:.0f} m | {w['E_uV_m_per_A']:.4g} | {a['E_uV_m_per_A']:.4g} |")
    lines += ["", "这是传递系数表，不表示真实潜艇采用1 A电流；源流形状若改变，不能仅乘电流。", "", "## 检查结果", "",
              "相对误差按三分量电场差的模除以参考场模计算，避免某个分量过零造成虚假巨大百分比。", "",
              "| 检查 | 水下侧向点 | 空气侧向点 | 水下完整测线 | 空气完整测线 |", "|---|---:|---:|---:|---:|"]
    for check, label in (("mesh", "base→fine网格变化"), ("outer_domain", "500→750 m外域变化"), ("benchmark", "解析边界条件对照")):
        values = [summary[f"{check}_{medium}_{kind}_max_percent"] for kind in ("side", "line") for medium in ("water", "air")]
        lines.append("| "+label+" | "+" | ".join(f"{v:.3f}%" for v in values)+" |")
    lines += ["", "这些是本次数值差异，不是物理参数置信区间；网格差小也不是严格误差上界。5%仅为本轮披露/筛选尺度，不是传感器识别阈值。", "",
              "解析对照在同一挖空艇体、水面和两物理场框架中，将边界输入替换为已知平衡点源解析解的通量及外边界电位；它验证求解链，不证明假设的艇表电流分布等同真实舰艇。", "",
              "规定源汇积分均为±1 A，净输入接近零。对有限元梯度直接积分所得的边界通量另行记录，它不等于规定通量的精确积分。", "",
              "| 情景 | 净规定电流/A | 梯度通量闭合残差/A | 外域净通量/A |", "|---|---:|---:|---:|"]
    for case in CASES[:3]:
        v = audit[case]
        lines.append(f"| {case} | {v[0]:.3g} | {v[7]:.3g} | {v[6]:.3g} |")
    failed = [r for r in distances if not r["all_three_within_5_percent"]]
    lines += ["", "侧向点三项筛选超过5%的点：" + ("；".join(f"{r['medium']} {r['horizontal_offset_m']:.0f} m" for r in failed) if failed else "无") + "。",
              "完整测线有更远的采样点，是否通过请按上表和convergence.csv逐点核对，不将局部通过宣称为全域收敛。", "",
              "## 图与文件", "", "![模型几何](results/01_geometry.png)", "", "![分量曲线](results/02_field_lines.png)", "", "![距离响应](results/03_distance.png)", "",
              "原始导出及MPH在comsol；整理CSV、误差与图片在results；生成脚本为summarize_model.py。", "",
              "## 尚未覆盖", "", "真实极化/涂层/阳极配置、海底、交流感应、轴系与流场、自身接收链及环境噪声。没有据此给出真实艇检测距离或修改实验结论。"]
    (HERE / "数值结果与核验.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    manifest = dict(assumptions="generic public-scale hull; prescribed current; not calibrated vessel or detector",
                    summary=summary, audit={k: v.tolist() for k, v in audit.items()},
                    source_sha256=hashlib.sha256((HERE/"GenericSubmarineDC.java").read_bytes()).hexdigest(),
                    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    csv_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in DATA.glob("*.csv")})
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Side points exceeding the declared 5% screening level: {len(failed)}")


if __name__ == "__main__":
    main()
