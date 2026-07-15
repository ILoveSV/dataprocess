from _common import FIGURE_DIR, TABLE_DIR, write_csv

import matplotlib.pyplot as plt
import numpy as np

from src.constants import (
    DEFAULT_DETECTION_GAMMA,
    DEFAULT_FS_HZ,
    DEFAULT_M1,
    DEFAULT_P0_A_M,
    DEFAULT_SIGMA_S_PER_M,
    P0_SCAN_A_M,
    S_E_SQRT_VALUES_V_PER_M_SQRT_HZ,
    T_INT_VALUES_S,
)
from src.plotting import save_current_figure
from src.propagation import shaft_rate_field, static_dipole_field
from src.snr import analytic_detection_range, shaft_snr_curve, solve_detection_range, spectral_detection_threshold
from src.source_models import harmonic_modulation


def main():
    distances = np.logspace(1, 4, 160)
    m1 = DEFAULT_M1
    m_n = harmonic_modulation(m1, 1)
    rows = []
    matrix_rows = []
    key_ranges = [100.0, 300.0, 1000.0]
    for S_E_sqrt in S_E_SQRT_VALUES_V_PER_M_SQRT_HZ:
        for T_int in T_INT_VALUES_S:
            Emin = spectral_detection_threshold(S_E_sqrt, T_int, DEFAULT_DETECTION_GAMMA)
            for P in P0_SCAN_A_M:
                R_baseline = analytic_detection_range(P, DEFAULT_SIGMA_S_PER_M, Emin, modulation=m_n)
                R_conservative = solve_detection_range(P, DEFAULT_SIGMA_S_PER_M, Emin, f_hz=DEFAULT_FS_HZ, modulation=m_n)
                rows.append({
                    "P0_a_m": P,
                    "sigma_s_per_m": DEFAULT_SIGMA_S_PER_M,
                    "m_n": m_n,
                    "frequency_hz": DEFAULT_FS_HZ,
                    "S_E_sqrt_v_per_m_sqrt_hz": S_E_sqrt,
                    "T_int_s": T_int,
                    "gamma": DEFAULT_DETECTION_GAMMA,
                    "E_min_v_per_m": Emin,
                    "Rmax_baseline_quasi_static_m": R_baseline,
                    "Rmax_optional_conservative_m": R_conservative,
                })
                for R in key_ranges:
                    E = float(shaft_rate_field(P, m_n, DEFAULT_FS_HZ, 1, R, DEFAULT_SIGMA_S_PER_M))
                    matrix_rows.append({
                        "P0_a_m": P,
                        "R_m": R,
                        "frequency_hz": DEFAULT_FS_HZ,
                        "m_n": m_n,
                        "S_E_sqrt_v_per_m_sqrt_hz": S_E_sqrt,
                        "T_int_s": T_int,
                        "gamma": DEFAULT_DETECTION_GAMMA,
                        "E_min_v_per_m": Emin,
                        "E_shaft_baseline_quasi_static_v_per_m": E,
                        "detectable_baseline": "yes" if E >= Emin else "no",
                        "margin_db": float(20.0 * np.log10(E / Emin)),
                    })
    write_csv(TABLE_DIR / "snr_range_scan.csv", ["P0_a_m", "sigma_s_per_m", "m_n", "frequency_hz", "S_E_sqrt_v_per_m_sqrt_hz", "T_int_s", "gamma", "E_min_v_per_m", "Rmax_baseline_quasi_static_m", "Rmax_optional_conservative_m"], rows)
    write_csv(TABLE_DIR / "detectability_matrix.csv", ["P0_a_m", "R_m", "frequency_hz", "m_n", "S_E_sqrt_v_per_m_sqrt_hz", "T_int_s", "gamma", "E_min_v_per_m", "E_shaft_baseline_quasi_static_v_per_m", "detectable_baseline", "margin_db"], matrix_rows)

    def status(signal, threshold):
        ratio = float(signal) / float(threshold)
        if ratio >= 10.0:
            return "稳健可测"
        if ratio >= 1.0:
            return "临界可测"
        return "不可测"

    decision_rows = []
    for S_E_sqrt in S_E_SQRT_VALUES_V_PER_M_SQRT_HZ:
        for T_int in T_INT_VALUES_S:
            Emin = spectral_detection_threshold(S_E_sqrt, T_int, DEFAULT_DETECTION_GAMMA)
            row = {
                "S_E_sqrt_v_per_m_sqrt_hz": S_E_sqrt,
                "T_int_s": T_int,
                "gamma": DEFAULT_DETECTION_GAMMA,
                "E_min_v_per_m": Emin,
            }
            for R in key_ranges:
                E_static = float(static_dipole_field(DEFAULT_P0_A_M, DEFAULT_SIGMA_S_PER_M, R))
                E_shaft = float(shaft_rate_field(DEFAULT_P0_A_M, m_n, DEFAULT_FS_HZ, 1, R, DEFAULT_SIGMA_S_PER_M))
                row[f"static_{int(R)}m_status"] = status(E_static, Emin)
                row[f"shaft1_{int(R)}m_status"] = status(E_shaft, Emin)
                row[f"static_{int(R)}m_margin_db"] = float(20.0 * np.log10(E_static / Emin))
                row[f"shaft1_{int(R)}m_margin_db"] = float(20.0 * np.log10(E_shaft / Emin))
            decision_rows.append(row)
    write_csv(TABLE_DIR / "detectability_decision_matrix.csv", list(decision_rows[0].keys()), decision_rows)

    plt.figure(figsize=(7, 4.5))
    for S_E_sqrt in S_E_SQRT_VALUES_V_PER_M_SQRT_HZ:
        Emin = spectral_detection_threshold(S_E_sqrt, 100.0, DEFAULT_DETECTION_GAMMA)
        snr = shaft_snr_curve(DEFAULT_P0_A_M, m_n, DEFAULT_FS_HZ, 1, distances, DEFAULT_SIGMA_S_PER_M, Emin)
        plt.semilogx(distances, snr, label=f"S_E^1/2={S_E_sqrt:.0e}, T=100 s")
    plt.axhline(0.0, color="k", linestyle="--", linewidth=1, label="E=E_min")
    plt.xlabel("range R (m)")
    plt.ylabel("SNR (dB)")
    plt.title("Parameterized shaft-rate detectability vs range")
    plt.grid(True, which="both", alpha=0.3)
    plt.legend(fontsize=8)
    save_current_figure(FIGURE_DIR / "SNR_vs_R.png")

    plt.figure(figsize=(7, 4.5))
    for S_E_sqrt in S_E_SQRT_VALUES_V_PER_M_SQRT_HZ:
        Emin = spectral_detection_threshold(S_E_sqrt, 100.0, DEFAULT_DETECTION_GAMMA)
        rmax = [analytic_detection_range(P, DEFAULT_SIGMA_S_PER_M, Emin, modulation=m_n) for P in P0_SCAN_A_M]
        plt.loglog(P0_SCAN_A_M, rmax, marker="o", label=f"S_E^1/2={S_E_sqrt:.0e}, T=100 s")
    plt.xlabel("equivalent dipole moment P (A m)")
    plt.ylabel("Rmax baseline quasi-static (m)")
    plt.title("Parameterized Rmax vs source strength")
    plt.grid(True, which="both", alpha=0.3)
    plt.legend(fontsize=8)
    save_current_figure(FIGURE_DIR / "Rmax_vs_P.png")

    plt.figure(figsize=(7, 4.5))
    emins = [spectral_detection_threshold(S_E_sqrt, 100.0, DEFAULT_DETECTION_GAMMA) for S_E_sqrt in S_E_SQRT_VALUES_V_PER_M_SQRT_HZ]
    rmax_noise = [analytic_detection_range(DEFAULT_P0_A_M, DEFAULT_SIGMA_S_PER_M, Emin, modulation=m_n) for Emin in emins]
    plt.loglog(emins, rmax_noise, marker="o")
    plt.gca().invert_xaxis()
    plt.xlabel("field threshold Emin (V/m)")
    plt.ylabel("Rmax baseline quasi-static (m)")
    plt.title("Parameterized Rmax vs spectral-noise-derived threshold")
    plt.grid(True, which="both", alpha=0.3)
    save_current_figure(FIGURE_DIR / "Rmax_vs_noise_floor.png")


if __name__ == "__main__":
    main()
