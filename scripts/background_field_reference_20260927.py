"""Conditional source-field predictions, not measured TC detector sensitivity."""

from __future__ import annotations

import csv
import hashlib
import importlib
import importlib.util
import json
import math
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
THEORY = ROOT / "calculation and paper/ship_efield_theory"
# The historical theory project also names its package "src". Load it under
# a private name so importing it cannot replace the main processing package.
_THEORY_PACKAGE = "_dataprocess_ship_theory"
if _THEORY_PACKAGE not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        _THEORY_PACKAGE, THEORY / "src/__init__.py",
        submodule_search_locations=[str(THEORY / "src")],
    )
    _package = importlib.util.module_from_spec(_spec)
    sys.modules[_THEORY_PACKAGE] = _package
    _spec.loader.exec_module(_package)
_propagation = importlib.import_module(f"{_THEORY_PACKAGE}.propagation")
point_current_electric_field = _propagation.point_current_electric_field
skin_depth = _propagation.skin_depth

OUT = ROOT / "results/background_field_reference_20260927"
EPS0 = 8.8541878128e-12
MU0 = 4 * math.pi * 1e-7
REFERENCE = dict(current_A=1.0, separation_m=10.0, depth_m=5.0, sigma_S_m=4.0, air_height_m=1.0)
DISTANCES = (2.0, 5.0, 10.0, 20.0, 30.0, 50.0, 100.0, 200.0)


def source_pair(current=1.0, separation=10.0, depth=5.0):
    if separation <= 0 or depth <= 0:
        raise ValueError("Positive separation and depth are required.")
    return np.array([current, -current]), np.array([[separation / 2, 0, -depth], [-separation / 2, 0, -depth]])


def source_kernel(currents, positions, points):
    currents = np.asarray(currents, dtype=complex)
    positions = np.asarray(positions, dtype=float)
    points = np.asarray(points, dtype=float)
    if positions.shape != (len(currents), 3) or points.shape[-1] != 3:
        raise ValueError("Expected source and observer coordinates with three components.")
    delta = points[..., None, :] - positions
    radius = np.linalg.norm(delta, axis=-1)
    if np.any(radius <= 0):
        raise ValueError("Observer coincides with a point source.")
    potential = np.sum(currents / radius, axis=-1)
    field = np.sum((currents / radius**3)[..., None] * delta, axis=-2)
    return potential, field


def halfspace(currents, positions, points, water_admittance=4.0, air_admittance=0.0, medium="air"):
    """Flat-interface scalar-potential solution; induction is not included."""
    positions, points = np.asarray(positions, float), np.asarray(points, float)
    if np.any(positions[:, 2] >= 0):
        raise ValueError("All sources must lie below z=0.")
    if abs(sum(currents)) > 1e-12 * max(1.0, sum(abs(np.asarray(currents)))):
        raise ValueError("The reference source must include a balanced return current.")
    if medium not in ("air", "water"):
        raise ValueError("medium must be air or water")
    if (medium == "air" and np.any(points[..., 2] < 0)) or (medium == "water" and np.any(points[..., 2] > 0)):
        raise ValueError("Observer is in the wrong half-space.")
    gw, ga = complex(water_admittance), complex(air_admittance)
    if gw.real <= 0 or ga.real < 0:
        raise ValueError("Conductivities must be physical and water must conduct.")
    potential, field = source_kernel(currents, positions, points)
    if medium == "air":
        factor = 1 / (2 * math.pi * (gw + ga))
        return factor * potential, factor * field
    mirror = positions.copy()
    mirror[:, 2] *= -1
    phi_image, e_image = source_kernel(currents, mirror, points)
    reflection = (gw - ga) / (gw + ga)
    factor = 1 / (4 * math.pi * gw)
    return factor * (potential + reflection * phi_image), factor * (field + reflection * e_image)


def finite_depth_static(currents, positions, points, water_sigma=4.0, bottom_sigma=0.5, water_depth=20.0, medium="air", terms=80):
    """DC three-layer image series: insulating air, water, conducting bottom."""
    positions, points = np.asarray(positions, float), np.asarray(points, float)
    if not (water_sigma > 0 and bottom_sigma > 0 and terms >= 1):
        raise ValueError("Positive conductivities and at least one image term required.")
    if np.any(positions[:, 2] >= 0) or np.any(positions[:, 2] <= -water_depth):
        raise ValueError("Sources must lie inside the water layer.")
    if abs(sum(currents)) > 1e-12:
        raise ValueError("Balanced source pair required.")
    if medium not in ("water", "air"):
        raise ValueError("Only water and air receivers are implemented.")
    if medium == "air" and np.any(points[..., 2] < 0):
        raise ValueError("Air receiver must be above the interface.")
    if medium == "water" and (np.any(points[..., 2] > 0) or np.any(points[..., 2] < -water_depth)):
        raise ValueError("Water receiver must lie in the water layer.")
    reflection = (water_sigma - bottom_sigma) / (water_sigma + bottom_sigma)
    phi = np.zeros(points.shape[:-1], dtype=complex)
    field = np.zeros(points.shape, dtype=complex)
    # With a perfectly insulating top, the two image families have equal weights.
    for n in range(-terms, terms + 1):
        weight = reflection ** abs(n)
        if weight == 0:
            continue
        lower = positions.copy()
        lower[:, 2] = -np.abs(-positions[:, 2] + 2 * n * water_depth)
        p, e = source_kernel(np.asarray(currents) * weight, lower, points)
        if medium == "air":
            phi += 2 * p
            field += 2 * e
        else:
            upper = lower.copy()
            upper[:, 2] *= -1
            pi, ei = source_kernel(np.asarray(currents) * weight, upper, points)
            phi += p + pi
            field += e + ei
    factor = 1 / (4 * math.pi * water_sigma)
    return factor * phi, factor * field


def eqs_prescreen(frequency, sigma, length):
    """L/delta <= 0.1 is a declared screening choice, not an error guarantee."""
    if frequency < 0 or sigma <= 0 or length <= 0:
        raise ValueError("Nonnegative frequency and positive sigma/length required.")
    if frequency == 0:
        return dict(skin_depth_m=None, L_over_delta=0.0, induction_parameter=0.0, passed=True)
    delta = float(skin_depth(frequency, sigma))
    ratio = length / delta
    return dict(skin_depth_m=delta, L_over_delta=ratio, induction_parameter=2 * ratio**2, passed=bool(ratio <= 0.1))


def norm(field):
    return np.linalg.norm(field, axis=-1)


def save_csv(name, rows):
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def setup_plots():
    plt.rcParams.update({"font.family": "Microsoft YaHei", "font.size": 10, "axes.unicode_minus": False,
                         "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 130,
                         "savefig.dpi": 180, "axes.grid": True, "grid.alpha": 0.20})


def save_plot(fig, stem):
    fig.savefig(OUT / f"{stem}.png", bbox_inches="tight")
    fig.savefig(OUT / f"{stem}.svg", bbox_inches="tight")
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    c, s = source_pair()
    reference_rows = []
    for rho in DISTANCES:
        water_obs, air_obs = np.array([0, rho, -5.0]), np.array([0, rho, 1.0])
        uniform = norm(point_current_electric_field(c, s, water_obs, 4.0))
        pw, ew = halfspace(c, s, water_obs, medium="water")
        pa, ea = halfspace(c, s, air_obs)
        finite = norm(finite_depth_static(c, s, air_obs)[1])
        reference_rows.append({
            "horizontal_offset_from_pair_center_m": rho, "I0_A": 1.0, "effective_separation_m": 10.0,
            "source_depth_m": 5.0, "air_receiver_height_m": 1.0, "water_receiver_depth_m": 5.0,
            "sigma_water_S_m": 4.0, "p0_A_m": 10.0,
            "E_infinite_water_dc_uV_m": float(uniform * 1e6),
            "E_halfspace_water_dc_uV_m": float(norm(ew) * 1e6),
            "E_halfspace_air_dc_uV_m": float(norm(ea) * 1e6),
            "air_Ex_dc_uV_m": float(ea[0].real * 1e6),
            "air_phi_dc_V": float(pa.real),
            "E_air_finite_depth20m_bottom0p5_dc_uV_m": float(finite * 1e6),
            "finite_bottom_over_deep_water": float(finite / norm(ea)),
            "status": "assumed_static_reference_not_measured_target_or_detector",
        })
    save_csv("reference_distance_dc.csv", reference_rows)

    modulation = []
    for rho in DISTANCES:
        obs = np.array([0, rho, 1.0])
        length = max(10.0, float(np.max(np.linalg.norm(obs - s, axis=1))))
        for f in (0.001, 0.01, 0.05, 0.1, 1 / 3.1, 1.0, 10.0, 50.0):
            gw = 4.0 + 2j * math.pi * f * EPS0 * 80
            ga = 2j * math.pi * f * EPS0
            base = float(norm(halfspace(c, s, obs, gw, ga)[1]))
            audit = eqs_prescreen(f, 4.0, length)
            for m in (0.001, 0.01, 0.1):
                modulation.append({"rho_m": rho, "frequency_Hz": f, "I0_A": 1.0, "modulation_assumed": m,
                    "delta_I_peak_A": m, "delta_p_peak_A_m": 10 * m, "L_screen_m": length,
                    "L_over_delta": audit["L_over_delta"], "skin_depth_m": audit["skin_depth_m"],
                    "passed_induction_prescreen": audit["passed"],
                    "E_air_ac_peak_uV_m_if_prescreen_passed": base * m * 1e6 if audit["passed"] else None,
                    "E_air_ac_rms_uV_m_if_prescreen_passed": base * m * 1e6 / math.sqrt(2) if audit["passed"] else None,
                    "reason": "conditional_EQS_not_calibrated" if audit["passed"] else "requires_inductive_EM_model_no_prediction_reported"})
    save_csv("modulation_with_validity.csv", modulation)

    frequency_rows = []
    for sigma in (0.05, 4.0):
        for f in (0.001, 0.01, 0.05, 0.1, 1 / 3.1, 1.0, 10.0, 50.0):
            delta = float(skin_depth(f, sigma))
            frequency_rows.append({"sigma_S_m": sigma, "frequency_Hz": f, "skin_depth_m": delta,
                "maximum_L_at_declared_prescreen_m": 0.1 * delta,
                "water_displacement_to_conduction": 2 * math.pi * f * EPS0 * 80 / sigma,
                "status": "screening_not_detection_range_or_error_bound"})
    save_csv("frequency_validity.csv", frequency_rows)

    lab = []
    for rho in (2.0, 3.0, 4.0):
        for sigma in (0.05, 4.0):
            for current in (0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 3.0):
                lc, ls = source_pair(current, 0.30, 0.30)
                e = float(norm(halfspace(lc, ls, [0, rho, 0.5], sigma)[1]))
                lab.append({"rho_from_pair_center_m": rho, "assumed_current_A": current, "effective_separation_m": 0.3,
                    "source_depth_m": 0.3, "air_height_m": 0.5, "sigma_S_m": sigma, "E_air_dc_uV_m": e * 1e6,
                    "E_air_ac_peak_for_assumed_1pct_uV_m": e * 0.01 * 1e6,
                    "status": "ideal_open_water_small_source_NOT_actual_bucket_prediction"})
    save_csv("small_source_ideal_reference.csv", lab)

    sensitivity = []
    for sigma in (0.05, 0.5, 4.0):
        for depth in (1.0, 5.0, 20.0):
            for height in (0.1, 1.0, 5.0):
                for current in (0.1, 1.0, 10.0):
                    sc, ss = source_pair(current, 10.0, depth)
                    e = float(norm(halfspace(sc, ss, [0, 20.0, height], sigma)[1]))
                    sensitivity.append({"rho_m": 20.0, "I_A": current, "d_eff_m": 10.0, "source_depth_m": depth,
                        "air_height_m": height, "sigma_S_m": sigma, "E_air_dc_uV_m": e * 1e6,
                        "status": "independent_assumed_parameter_sweep_not_confidence_interval"})
    save_csv("parameter_sensitivity.csv", sensitivity)

    cancellation = []
    obs = np.array([0.0, 30.0, 1.0])
    unit = norm(halfspace(c, s, obs)[1])
    for residual in (1.0, 0.1, 0.01, 0.0):
        e = norm(halfspace(np.r_[c, -(1 - residual) * c], np.r_[s, s], obs)[1])
        cancellation.append({"residual_fraction": residual, "sum_positive_source_current_A": 2 - residual,
            "net_p_A_m": 10 * residual, "E_air_dc_uV_m": float(e * 1e6), "fraction_of_single_source": float(e / unit),
            "status": "algebraic_colocated_opposed_loop_example_not_vessel_geometry"})
    save_csv("net_source_cancellation.csv", cancellation)

    setup_plots()
    rho = np.geomspace(2, 200, 320)
    air_points, water_points = np.column_stack([0 * rho, rho, 0 * rho + 1]), np.column_stack([0 * rho, rho, 0 * rho - 5])
    uniform = norm(point_current_electric_field(c, s, water_points, 4.0)) * 1e6
    water = norm(halfspace(c, s, water_points, medium="water")[1]) * 1e6
    air = norm(halfspace(c, s, air_points)[1]) * 1e6
    bottom = norm(finite_depth_static(c, s, air_points)[1]) * 1e6
    fig, ax = plt.subplots(figsize=(9, 5.4), layout="constrained")
    for values, label, color, style in (
        (uniform, "无限水体：接收深度5 m", "#555555", "--"),
        (water, "水面下：接收深度5 m", "#2672a3", "-"),
        (air, "水面上：接收高度1 m", "#c74739", "-"),
        (bottom, "水面上：加20 m水深、0.5 S/m海底", "#367b50", ":")):
        ax.loglog(rho, values, style, lw=2.2, color=color, label=label)
    ax.set(xlabel="水平偏距 ρ（m，自源汇中点起）", ylabel="静态电场模（μV/m）", title="背景参考源：1 A，有效间距10 m，深度5 m，水电导率4 S/m")
    ax.legend(fontsize=9)
    fig.text(0.02, -0.04, "有限源汇解析预测；曲线不是实测结果，也不是探测器输出或检出距离。", fontsize=9)
    save_plot(fig, "01_distance_and_boundary")

    fig, ax = plt.subplots(figsize=(9, 5.4), layout="constrained")
    for m, color in ((0.001, "#2672a3"), (0.01, "#c74739"), (0.1, "#367b50")):
        # Long-distance values are withheld when the induction pre-screen fails.
        lengths = np.maximum(10, np.sqrt(rho**2 + 6**2 + 5**2))
        mask = lengths / float(skin_depth(1 / 3.1, 4)) <= 0.1
        ax.loglog(rho[mask], (air * m)[mask], color=color, lw=2.3, label=f"假设调制 {100*m:g}%（ΔI={m:g} A峰值）")
    ax.axvspan(rho[~mask][0], 200, color="#e7e7e7", zorder=0)
    ax.text(0.77, 0.50, "此区域需含感应模型\n本轮不报交流预测", transform=ax.transAxes, ha="center", fontsize=9)
    ax.set(xlim=(2, 200), xlabel="水平偏距 ρ（m）", ylabel="交流电场峰值（μV/m）", title="约0.323 Hz调制：同一参考源、空气中1 m高接收")
    ax.legend(fontsize=9, loc="lower left")
    fig.text(0.02, -0.04, "调制比例是假设；L/δ≤0.1为保守预筛选，不是误差保证或传感器检出判据。", fontsize=9)
    save_plot(fig, "02_modulated_field_with_validity")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), layout="constrained")
    for depth, color in ((1, "#2672a3"), (5, "#c74739"), (20, "#367b50")):
        dc, ds = source_pair(1, 10, depth)
        values = norm(halfspace(dc, ds, air_points)[1]) * 1e6
        axes[0].loglog(rho, values, color=color, label=f"源深 {depth} m", lw=2)
    axes[0].set(title="深度敏感性：接收高度固定1 m", xlabel="水平偏距 ρ（m）", ylabel="空气中静态场模（μV/m）")
    axes[0].legend(fontsize=9)
    for sigma, color in ((0.05, "#2672a3"), (0.5, "#c74739"), (4, "#367b50")):
        values = norm(halfspace(c, s, air_points, sigma)[1]) * 1e6
        axes[1].loglog(rho, values, color=color, label=f"σ={sigma:g} S/m", lw=2)
    axes[1].set(title="电导率敏感性：固定1 A源电流", xlabel="水平偏距 ρ（m）", ylabel="空气中静态场模（μV/m）")
    axes[1].legend(fontsize=9)
    fig.text(0.02, -0.04, "其余参数同参考源。电导率取值为情景；固定电压时不能机械使用1/σ关系。", fontsize=9)
    save_plot(fig, "03_depth_and_conductivity")

    fig, ax = plt.subplots(figsize=(9, 4.8), layout="constrained")
    ax.axhspan(-8, 0, color="#e2f0f7", zorder=0)
    ax.axhspan(0, 4, color="#f7f7f7", zorder=0)
    ax.axhline(0, color="#555555", lw=1)
    ax.scatter([-5, 5], [-5, -5], c=["#c74739", "#2672a3"], s=80, zorder=3)
    ax.text(-5, -4.4, "−I", ha="center")
    ax.text(5, -4.4, "+I", ha="center")
    ax.annotate("", (5, -6), (-5, -6), arrowprops={"arrowstyle": "<->", "color": "#444444"})
    ax.text(0, -6.8, "有效源汇间距 d=10 m", ha="center")
    ax.text(-9, 2.5, "空气 z>0：接收高度 a=1 m")
    ax.text(-9, -2, "水体 z<0：σ=4 S/m，源深 h=5 m")
    ax.text(-9, 0.4, "平坦水面 z=0")
    ax.text(0, 1.4, "接收点 (0,ρ,a)\nρ沿垂直纸面的y方向", ha="center", fontsize=10)
    ax.scatter([0], [1], c="#367b50", marker="s", s=65)
    ax.set(xlim=(-10, 10), ylim=(-8, 4), xlabel="源轴方向 x（m）", ylabel="高度 z（m）", title="本轮选择的背景：水下平衡电流源汇；不是整艇几何或实验水桶")
    save_plot(fig, "00_reference_geometry")

    manifest = {
        "date": "2026-09-27", "kind": "conditional_theoretical_predictions_no_new_measurements",
        "reference": REFERENCE, "geometry": "flat_air_water_interface_horizontal_balanced_pair_broadside_receiver",
        "air_sigma_S_m": 0.0, "epsilon_r_water_assumed": 80, "epsilon_r_air_assumed": 1,
        "modulation_depths_are_assumed": [0.001, 0.01, 0.1],
        "finite_depth_DC_sensitivity": dict(water_depth_m=20, bottom_sigma_S_m=0.5, image_terms_each_side=80),
        "EQS_prescreen": "L/delta<=0.1; L=max(d,max_source_receiver_distance); not an accuracy guarantee",
        "no_detection_limit_or_range": True, "no_new_COMSOL_solution": True,
        "inputs_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [Path(__file__), THEORY / "src/propagation.py"]},
        "outputs_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.glob("*")) if p.suffix in (".csv", ".png", ".svg")},
    }
    (OUT / "calculation_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(OUT), "reference_distance": reference_rows, "frequency_validity": frequency_rows}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
