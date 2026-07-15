from _common import FIGURE_DIR, TABLE_DIR, write_csv

import matplotlib.pyplot as plt
import numpy as np

from src.constants import DEFAULT_FS_HZ, DEFAULT_M1, DEFAULT_P0_A_M, DEFAULT_SIGMA_S_PER_M, DISTANCES_M, HARMONICS, P0_SCAN_A_M
from src.plotting import save_current_figure
from src.propagation import shaft_rate_field
from src.source_models import harmonic_modulation, shaft_rate_components


def main():
    rows = []
    for P0 in P0_SCAN_A_M:
        for R in DISTANCES_M:
            for n in HARMONICS:
                m_n = harmonic_modulation(DEFAULT_M1, n)
                E_baseline = float(shaft_rate_field(P0, m_n, DEFAULT_FS_HZ, n, R, DEFAULT_SIGMA_S_PER_M))
                E_conservative = float(shaft_rate_field(P0, m_n, DEFAULT_FS_HZ, n, R, DEFAULT_SIGMA_S_PER_M, conservative_diffusion=True))
                rows.append({
                    "P0_a_m": P0,
                    "sigma_s_per_m": DEFAULT_SIGMA_S_PER_M,
                    "R_m": R,
                    "fs_hz": DEFAULT_FS_HZ,
                    "harmonic": n,
                    "frequency_hz": DEFAULT_FS_HZ * n,
                    "m_n": m_n,
                    "E_shaft_baseline_quasi_static_v_per_m": E_baseline,
                    "E_shaft_optional_conservative_v_per_m": E_conservative,
                })
    write_csv(TABLE_DIR / "shaft_rate_scan.csv", ["P0_a_m", "sigma_s_per_m", "R_m", "fs_hz", "harmonic", "frequency_hz", "m_n", "E_shaft_baseline_quasi_static_v_per_m", "E_shaft_optional_conservative_v_per_m"], rows)

    plt.figure(figsize=(7, 4.5))
    for n in HARMONICS:
        m_n = harmonic_modulation(DEFAULT_M1, n)
        values = [shaft_rate_field(DEFAULT_P0_A_M, m_n, DEFAULT_FS_HZ, n, R, DEFAULT_SIGMA_S_PER_M) for R in DISTANCES_M]
        plt.loglog(DISTANCES_M, values, marker="o", label=f"n={n}, f={DEFAULT_FS_HZ*n:g} Hz")
    plt.xlabel("range R (m)")
    plt.ylabel("shaft component E (V/m)")
    plt.title("Shaft-rate harmonic amplitude, baseline quasi-static")
    plt.grid(True, which="both", alpha=0.3)
    plt.legend(fontsize=8)
    save_current_figure(FIGURE_DIR / "shaft_rate_amplitude_by_range.png")

    plt.figure(figsize=(7, 4.5))
    n = 1
    m_n = harmonic_modulation(DEFAULT_M1, n)
    baseline = [shaft_rate_field(DEFAULT_P0_A_M, m_n, DEFAULT_FS_HZ, n, R, DEFAULT_SIGMA_S_PER_M) for R in DISTANCES_M]
    conservative = [shaft_rate_field(DEFAULT_P0_A_M, m_n, DEFAULT_FS_HZ, n, R, DEFAULT_SIGMA_S_PER_M, conservative_diffusion=True) for R in DISTANCES_M]
    plt.loglog(DISTANCES_M, baseline, marker="o", label="baseline quasi-static")
    plt.loglog(DISTANCES_M, conservative, marker="s", linestyle="--", label="optional conservative diffusion")
    plt.xlabel("range R (m)")
    plt.ylabel("shaft n=1 E (V/m)")
    plt.title("Shaft-rate baseline vs optional conservative sensitivity")
    plt.grid(True, which="both", alpha=0.3)
    plt.legend(fontsize=8)
    save_current_figure(FIGURE_DIR / "shaft_rate_baseline_vs_conservative.png")

    comps = shaft_rate_components(DEFAULT_P0_A_M, DEFAULT_M1, DEFAULT_FS_HZ, HARMONICS)
    freqs = [row["frequency_hz"] for row in comps]
    amps = [shaft_rate_field(DEFAULT_P0_A_M, row["m_n"], DEFAULT_FS_HZ, row["harmonic"], 100.0, DEFAULT_SIGMA_S_PER_M) for row in comps]
    plt.figure(figsize=(7, 4.5))
    plt.stem(freqs, amps)
    plt.xlabel("frequency (Hz)")
    plt.ylabel("line amplitude at R=100 m (V/m)")
    plt.title("Illustrative shaft-rate line spectrum")
    plt.grid(True, alpha=0.3)
    save_current_figure(FIGURE_DIR / "shaft_rate_line_spectrum.png")


if __name__ == "__main__":
    main()
