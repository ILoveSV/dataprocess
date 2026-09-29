from _common import FIGURE_DIR, TABLE_DIR, write_csv

import matplotlib.pyplot as plt

from src.constants import DEFAULT_SIGMA_S_PER_M, DIPOLE_MOMENTS_A_M, DISTANCES_M
from src.plotting import save_current_figure
from src.propagation import static_dipole_field


def main():
    rows = []
    plt.figure(figsize=(7, 4.5))
    for P in DIPOLE_MOMENTS_A_M:
        values = []
        for R in DISTANCES_M:
            E = float(static_dipole_field(P, DEFAULT_SIGMA_S_PER_M, R))
            values.append(E)
            rows.append({"P_a_m": P, "sigma_s_per_m": DEFAULT_SIGMA_S_PER_M, "R_m": R, "E_v_per_m": E, "E_uV_per_m": E * 1e6})
        plt.loglog(DISTANCES_M, values, marker="o", label=f"P={P:g} A m")
    write_csv(TABLE_DIR / "static_dipole_scan.csv", ["P_a_m", "sigma_s_per_m", "R_m", "E_v_per_m", "E_uV_per_m"], rows)
    plt.xlabel("range R (m)")
    plt.ylabel("electric field E (V/m)")
    plt.title("Static equivalent current-dipole field")
    plt.grid(True, which="both", alpha=0.3)
    plt.legend(fontsize=8)
    save_current_figure(FIGURE_DIR / "E_vs_R_for_P.png")


if __name__ == "__main__":
    main()
