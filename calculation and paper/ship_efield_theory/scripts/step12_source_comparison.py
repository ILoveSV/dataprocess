from _common import FIGURE_DIR, TABLE_DIR, write_csv

import math
import matplotlib.pyplot as plt
import numpy as np

from src.constants import (
    DEFAULT_B0_T,
    DEFAULT_FS_HZ,
    DEFAULT_L_SHIP_M,
    DEFAULT_M1,
    DEFAULT_P0_A_M,
    DEFAULT_SIGMA_S_PER_M,
    DEFAULT_SPEED_M_PER_S,
    DIRECTION_FACTORS,
    P0_SCAN_A_M,
)
from src.plotting import save_current_figure
from src.propagation import frequency_attenuation, shaft_rate_field, static_dipole_field
from src.source_models import harmonic_modulation, moving_envelope_timescale


COMPARISON_DISTANCES_M = [30.0, 50.0, 100.0, 300.0, 500.0, 1000.0, 3000.0]
DECISION_DISTANCES_M = [30.0, 50.0, 100.0, 300.0, 500.0, 1000.0]
DECISION_KEY_DISTANCES_M = [100.0, 300.0, 1000.0]
M1_DECISION_VALUES = [0.01, 0.03, 0.1]
BASELINE_M = 1.0


def field_region(range_m):
    boundary = 3.0 * DEFAULT_L_SHIP_M
    if float(range_m) >= boundary:
        return "far_field_R_ge_3L"
    return "near_intermediate_estimate_R_lt_3L"


def db_ratio(value, reference):
    return 20.0 * math.log10(float(value) / float(reference))


def motional_wake_local_upper_bound(speed_m_per_s=DEFAULT_SPEED_M_PER_S, B0_t=DEFAULT_B0_T):
    return float(speed_m_per_s) * float(B0_t)


def static_range_at(R):
    values = []
    for P0 in P0_SCAN_A_M:
        values.append(static_dipole_field(P0, DEFAULT_SIGMA_S_PER_M, R, Ctheta=DIRECTION_FACTORS["equatorial"]))
        values.append(static_dipole_field(P0, DEFAULT_SIGMA_S_PER_M, R, Ctheta=DIRECTION_FACTORS["axial"]))
    return min(values), max(values)


def shaft_range_at(R):
    values = []
    for P0 in P0_SCAN_A_M:
        for m1 in M1_DECISION_VALUES:
            values.append(shaft_rate_field(P0, m1, DEFAULT_FS_HZ, 1, R, DEFAULT_SIGMA_S_PER_M, Ctheta=DIRECTION_FACTORS["equatorial"]))
            values.append(shaft_rate_field(P0, m1, DEFAULT_FS_HZ, 1, R, DEFAULT_SIGMA_S_PER_M, Ctheta=DIRECTION_FACTORS["axial"]))
    return min(values), max(values)


def main():
    rows = []
    for P0 in P0_SCAN_A_M:
        for R in COMPARISON_DISTANCES_M:
            E_eq = float(static_dipole_field(P0, DEFAULT_SIGMA_S_PER_M, R, Ctheta=DIRECTION_FACTORS["equatorial"]))
            E_rms = float(static_dipole_field(P0, DEFAULT_SIGMA_S_PER_M, R, Ctheta=DIRECTION_FACTORS["rms"]))
            E_axial = float(static_dipole_field(P0, DEFAULT_SIGMA_S_PER_M, R, Ctheta=DIRECTION_FACTORS["axial"]))
            rows.append({
                "observable_id": "UEP_result_signature_static_P0",
                "P0_a_m": P0,
                "R_m": R,
                "field_region": field_region(R),
                "frequency_hz": 0.0,
                "model": "baseline_quasi_static_far_field_dipole",
                "direction": "range_equatorial_to_axial",
                "E_equatorial_v_per_m": E_eq,
                "E_rms_v_per_m": E_rms,
                "E_axial_v_per_m": E_axial,
                "E_min_v_per_m": E_eq,
                "E_max_v_per_m": E_axial,
                "E_optional_conservative_v_per_m": E_eq,
                "relative_to_static_equatorial_db": 0.0,
                "deltaV_1m_min_v": E_eq * BASELINE_M,
                "deltaV_1m_max_v": E_axial * BASELINE_M,
                "interpretation": "UEP is treated as the resulting signature of P0=P_corr+P_SACP+P_ICCP, not as an independent additive source.",
            })
            for n in [1, 2, 3, 4, 5]:
                m_n = harmonic_modulation(DEFAULT_M1, n)
                E_shaft_eq = float(shaft_rate_field(P0, m_n, DEFAULT_FS_HZ, n, R, DEFAULT_SIGMA_S_PER_M, Ctheta=DIRECTION_FACTORS["equatorial"]))
                E_shaft_rms = float(shaft_rate_field(P0, m_n, DEFAULT_FS_HZ, n, R, DEFAULT_SIGMA_S_PER_M, Ctheta=DIRECTION_FACTORS["rms"]))
                E_shaft_axial = float(shaft_rate_field(P0, m_n, DEFAULT_FS_HZ, n, R, DEFAULT_SIGMA_S_PER_M, Ctheta=DIRECTION_FACTORS["axial"]))
                E_shaft_cons = float(shaft_rate_field(P0, m_n, DEFAULT_FS_HZ, n, R, DEFAULT_SIGMA_S_PER_M, conservative_diffusion=True))
                rows.append({
                    "observable_id": f"shaft_modulation_n{n}",
                    "P0_a_m": P0,
                    "R_m": R,
                    "field_region": field_region(R),
                    "frequency_hz": DEFAULT_FS_HZ * n,
                    "model": "baseline_quasi_static_with_optional_conservative_diffusion",
                    "direction": "range_equatorial_to_axial",
                    "E_equatorial_v_per_m": E_shaft_eq,
                    "E_rms_v_per_m": E_shaft_rms,
                    "E_axial_v_per_m": E_shaft_axial,
                    "E_min_v_per_m": E_shaft_eq,
                    "E_max_v_per_m": E_shaft_axial,
                    "E_optional_conservative_v_per_m": E_shaft_cons,
                    "relative_to_static_equatorial_db": db_ratio(E_shaft_eq, E_eq),
                    "deltaV_1m_min_v": E_shaft_eq * BASELINE_M,
                    "deltaV_1m_max_v": E_shaft_axial * BASELINE_M,
                    "interpretation": "Shaft-rate line is modulation of P0. The baseline column does not include exp(-R/delta); the conservative column is sensitivity only.",
                })
    fieldnames = [
        "observable_id",
        "P0_a_m",
        "R_m",
        "field_region",
        "frequency_hz",
        "model",
        "direction",
        "E_equatorial_v_per_m",
        "E_rms_v_per_m",
        "E_axial_v_per_m",
        "E_min_v_per_m",
        "E_max_v_per_m",
        "E_optional_conservative_v_per_m",
        "relative_to_static_equatorial_db",
        "deltaV_1m_min_v",
        "deltaV_1m_max_v",
        "interpretation",
    ]
    write_csv(TABLE_DIR / "source_comparison_by_range.csv", fieldnames, rows)

    pivot_rows = []
    for R in [100.0, 300.0, 1000.0]:
        static_row = next(row for row in rows if row["P0_a_m"] == DEFAULT_P0_A_M and row["R_m"] == R and row["observable_id"] == "UEP_result_signature_static_P0")
        shaft_row = next(row for row in rows if row["P0_a_m"] == DEFAULT_P0_A_M and row["R_m"] == R and row["observable_id"] == "shaft_modulation_n1")
        pivot_rows.append({
            "P0_a_m": DEFAULT_P0_A_M,
            "R_m": R,
            "field_region": field_region(R),
            "E_static_equatorial_v_per_m": static_row["E_equatorial_v_per_m"],
            "E_static_axial_v_per_m": static_row["E_axial_v_per_m"],
            "E_shaft1_baseline_equatorial_v_per_m": shaft_row["E_equatorial_v_per_m"],
            "E_shaft1_baseline_axial_v_per_m": shaft_row["E_axial_v_per_m"],
            "E_shaft1_optional_conservative_v_per_m": shaft_row["E_optional_conservative_v_per_m"],
            "shaft1_relative_to_static_db": shaft_row["relative_to_static_equatorial_db"],
        })
    write_csv(TABLE_DIR / "source_comparison_pivot.csv", list(pivot_rows[0].keys()), pivot_rows)

    wake_rows = []
    wake_upper = motional_wake_local_upper_bound()
    for R in COMPARISON_DISTANCES_M:
        tau = moving_envelope_timescale(R, DEFAULT_SPEED_M_PER_S)
        wake_rows.append({
            "R_or_R0_m": R,
            "field_region": field_region(R),
            "wake_local_upper_bound_v_per_m": wake_upper,
            "v_m_per_s": DEFAULT_SPEED_M_PER_S,
            "B0_t": DEFAULT_B0_T,
            "moving_tau_s": tau["tau_s"],
            "moving_t_half_s": tau["t_half_s"],
            "moving_full_half_width_s": tau["full_half_width_s"],
            "interpretation": "Wake is a local motional upper bound E<=vB0 and is not ranked against UEP/shaft far-field dipole rows.",
        })
    write_csv(TABLE_DIR / "wake_and_motion_boundary.csv", ["R_or_R0_m", "field_region", "wake_local_upper_bound_v_per_m", "v_m_per_s", "B0_t", "moving_tau_s", "moving_t_half_s", "moving_full_half_width_s", "interpretation"], wake_rows)

    lab_rows = []
    for channel in ["i"]:
        lab_rows.append({
            "channel": channel,
            "model": "V_i(t)=S_i(t)+A_50_i cos(2pi50t+phi_50_i)+sum_k A_k_i cos(2pik50t+phi_k_i)+n_i(t)",
            "A_50_i": "measured_or_parameter_input",
            "A_k_i": "measured_or_parameter_input",
            "note": "For 200 L tank, pump, DAQ, and BNC coupling, do not infer 50 Hz amplitude from open-sea skin depth or 1/R spreading.",
        })
    write_csv(TABLE_DIR / "powerline_lab_nuisance_model.csv", ["channel", "model", "A_50_i", "A_k_i", "note"], lab_rows)

    range_rows = []
    for R in DECISION_DISTANCES_M:
        static_min, static_max = static_range_at(R)
        shaft_min, shaft_max = shaft_range_at(R)
        shaft_baseline = float(shaft_rate_field(DEFAULT_P0_A_M, DEFAULT_M1, DEFAULT_FS_HZ, 1, R, DEFAULT_SIGMA_S_PER_M))
        range_rows.append({
            "R_m": R,
            "field_region": field_region(R),
            "E_static_min_v_per_m": static_min,
            "E_static_max_v_per_m": static_max,
            "E_static_min_uV_per_m": static_min * 1e6,
            "E_static_max_uV_per_m": static_max * 1e6,
            "E_shaft_min_v_per_m": shaft_min,
            "E_shaft_max_v_per_m": shaft_max,
            "E_shaft_min_uV_per_m": shaft_min * 1e6,
            "E_shaft_max_uV_per_m": shaft_max * 1e6,
            "E_shaft_m1_0p03_P0_300_baseline_v_per_m": shaft_baseline,
            "E_shaft_m1_0p03_P0_300_baseline_uV_per_m": shaft_baseline * 1e6,
        })
    write_csv(TABLE_DIR / "distance_source_strength_ranges.csv", list(range_rows[0].keys()), range_rows)

    decision_rows = []
    for source_id, source_name, frequency_label, directly_sortable, priority in [
        ("static_UEP_ICCP_signature", "UEP/ICCP静态场", "0 Hz/慢变", "yes", "第二优先：梯度和多通道一致性"),
        ("shaft_fundamental", "轴频基频", f"{DEFAULT_FS_HZ:g} Hz", "yes", "第一优先：当前最适合验证"),
        ("wake_local_upper_bound", "尾流局部上限", "低频宽带", "no", "第四优先：后续单独模型"),
        ("powerline_50hz", "50 Hz工频干扰", "50 Hz及倍频", "no", "第三优先：测量和剔除"),
    ]:
        row = {
            "source_id": source_id,
            "source_name": source_name,
            "frequency_label": frequency_label,
            "direct_far_field_sorting": directly_sortable,
            "experiment_priority": priority,
        }
        for R in DECISION_KEY_DISTANCES_M:
            if source_id == "static_UEP_ICCP_signature":
                lo, hi = static_range_at(R)
                row[f"E_{int(R)}m_range_v_per_m"] = f"{lo:.6e}--{hi:.6e}"
                row[f"E_{int(R)}m_range_uV_per_m"] = f"{lo * 1e6:.6e}--{hi * 1e6:.6e}"
            elif source_id == "shaft_fundamental":
                lo, hi = shaft_range_at(R)
                row[f"E_{int(R)}m_range_v_per_m"] = f"{lo:.6e}--{hi:.6e}"
                row[f"E_{int(R)}m_range_uV_per_m"] = f"{lo * 1e6:.6e}--{hi * 1e6:.6e}"
            elif source_id == "wake_local_upper_bound":
                upper = motional_wake_local_upper_bound()
                row[f"E_{int(R)}m_range_v_per_m"] = f"local <= {upper:.6e}"
                row[f"E_{int(R)}m_range_uV_per_m"] = f"local <= {upper * 1e6:.6e}"
            else:
                row[f"E_{int(R)}m_range_v_per_m"] = "measured A50_i / d_eff"
                row[f"E_{int(R)}m_range_uV_per_m"] = "measured"
        decision_rows.append(row)
    decision_fields = list(decision_rows[0].keys())
    write_csv(TABLE_DIR / "executive_final_decision_table.csv", decision_fields, decision_rows)

    voltage_rows = []
    for E_target in [1e-6, 1e-7, 1e-8, 1e-9]:
        row = {"E_target_v_per_m": E_target, "E_target_uV_per_m": E_target * 1e6}
        for d in [0.01, 0.05, 0.1, 0.5, 1.0]:
            dv = E_target * d
            row[f"DeltaV_d_{str(d).replace('.', 'p')}_m_v"] = dv
            row[f"DeltaV_d_{str(d).replace('.', 'p')}_m_uV"] = dv * 1e6
        voltage_rows.append(row)
    write_csv(TABLE_DIR / "lab_equivalent_voltage_design.csv", list(voltage_rows[0].keys()), voltage_rows)

    plt.figure(figsize=(8, 5))
    for obs_id in ["UEP_result_signature_static_P0", "shaft_modulation_n1", "shaft_modulation_n2", "shaft_modulation_n3"]:
        curve = [row for row in rows if row["P0_a_m"] == DEFAULT_P0_A_M and row["observable_id"] == obs_id]
        plt.loglog([row["R_m"] for row in curve], [row["E_equatorial_v_per_m"] for row in curve], marker="o", label=f"{obs_id} eq")
    plt.axvline(3.0 * DEFAULT_L_SHIP_M, color="k", linestyle=":", linewidth=1, label="R=3 L_ship")
    plt.xlabel("range R (m)")
    plt.ylabel("electric field E (V/m), equatorial")
    plt.title("Baseline quasi-static P0 signature and shaft modulation")
    plt.grid(True, which="both", alpha=0.3)
    plt.legend(fontsize=8)
    save_current_figure(FIGURE_DIR / "comparable_source_E_vs_R.png")

    plt.figure(figsize=(7, 4.5))
    n = 1
    m_n = harmonic_modulation(DEFAULT_M1, n)
    baseline = [shaft_rate_field(DEFAULT_P0_A_M, m_n, DEFAULT_FS_HZ, n, R, DEFAULT_SIGMA_S_PER_M) for R in COMPARISON_DISTANCES_M]
    conservative = [
        shaft_rate_field(DEFAULT_P0_A_M, m_n, DEFAULT_FS_HZ, n, R, DEFAULT_SIGMA_S_PER_M, conservative_diffusion=True)
        for R in COMPARISON_DISTANCES_M
    ]
    attenuation = [frequency_attenuation(R, DEFAULT_FS_HZ, DEFAULT_SIGMA_S_PER_M) for R in COMPARISON_DISTANCES_M]
    plt.loglog(COMPARISON_DISTANCES_M, baseline, marker="o", label="baseline quasi-static")
    plt.loglog(COMPARISON_DISTANCES_M, conservative, marker="s", linestyle="--", label="optional conservative")
    plt.loglog(COMPARISON_DISTANCES_M, attenuation, marker="^", linestyle=":", label="exp(-R/delta) factor")
    plt.xlabel("range R (m)")
    plt.ylabel("E (V/m) or attenuation factor")
    plt.title("Shaft n=1 conservative diffusion sensitivity")
    plt.grid(True, which="both", alpha=0.3)
    plt.legend(fontsize=8)
    save_current_figure(FIGURE_DIR / "shaft_conservative_diffusion_sensitivity.png")

    heat_sources = ["static", "shaft n=1", "shaft n=2", "shaft n=3"]
    heat_ranges = [100.0, 300.0, 1000.0]
    heat = np.zeros((len(heat_sources), len(heat_ranges)))
    for j, R in enumerate(heat_ranges):
        for i, obs_id in enumerate(["UEP_result_signature_static_P0", "shaft_modulation_n1", "shaft_modulation_n2", "shaft_modulation_n3"]):
            row = next(item for item in rows if item["P0_a_m"] == DEFAULT_P0_A_M and item["R_m"] == R and item["observable_id"] == obs_id)
            heat[i, j] = math.log10(max(row["E_equatorial_v_per_m"], 1e-30))
    plt.figure(figsize=(7, 4.6))
    im = plt.imshow(heat, aspect="auto", cmap="viridis")
    plt.colorbar(im, label="log10(E / V m^-1), equatorial")
    plt.xticks(range(len(heat_ranges)), [f"{R:g} m" for R in heat_ranges])
    plt.yticks(range(len(heat_sources)), heat_sources, fontsize=8)
    plt.title("P0 signature and shaft line strength")
    plt.xlabel("range")
    plt.ylabel("observable")
    save_current_figure(FIGURE_DIR / "source_frequency_strength_map.png")


if __name__ == "__main__":
    main()
