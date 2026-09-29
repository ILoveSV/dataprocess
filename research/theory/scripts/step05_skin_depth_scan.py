from _common import FIGURE_DIR, TABLE_DIR, write_csv

import matplotlib.pyplot as plt
import numpy as np

from src.constants import DEFAULT_SIGMA_S_PER_M, DISTANCES_M
from src.plotting import save_current_figure
from src.propagation import frequency_attenuation, skin_depth


def main():
    freqs = [0.1, 0.3, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 30.0, 50.0, 100.0]
    rows = []
    for f in freqs:
        delta = float(skin_depth(f, DEFAULT_SIGMA_S_PER_M))
        for R in DISTANCES_M:
            rows.append({"frequency_hz": f, "sigma_s_per_m": DEFAULT_SIGMA_S_PER_M, "skin_depth_m": delta, "R_m": R, "attenuation": float(frequency_attenuation(R, f, DEFAULT_SIGMA_S_PER_M))})
    write_csv(TABLE_DIR / "skin_depth_scan.csv", ["frequency_hz", "sigma_s_per_m", "skin_depth_m", "R_m", "attenuation"], rows)

    dense_f = np.logspace(-1, 2, 200)
    plt.figure(figsize=(7, 4.5))
    plt.loglog(dense_f, skin_depth(dense_f, DEFAULT_SIGMA_S_PER_M))
    plt.xlabel("frequency f (Hz)")
    plt.ylabel("skin depth delta (m)")
    plt.title("Skin depth in conductive seawater")
    plt.grid(True, which="both", alpha=0.3)
    save_current_figure(FIGURE_DIR / "skin_depth_vs_frequency.png")

    plt.figure(figsize=(7, 4.5))
    for f in [1.0, 3.0, 7.0, 30.0, 50.0]:
        plt.semilogy(DISTANCES_M, [frequency_attenuation(R, f, DEFAULT_SIGMA_S_PER_M) for R in DISTANCES_M], marker="o", label=f"{f:g} Hz")
    plt.xlabel("range R (m)")
    plt.ylabel("attenuation exp(-R/delta)")
    plt.title("Engineering frequency attenuation")
    plt.grid(True, which="both", alpha=0.3)
    plt.legend()
    save_current_figure(FIGURE_DIR / "attenuation_vs_distance_by_frequency.png")


if __name__ == "__main__":
    main()
