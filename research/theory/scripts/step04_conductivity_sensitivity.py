from _common import FIGURE_DIR, TABLE_DIR, write_csv

import matplotlib.pyplot as plt
import numpy as np

from src.constants import DEFAULT_P0_A_M, DISTANCES_M, SIGMA_RANGE_S_PER_M
from src.plotting import save_current_figure
from src.propagation import static_dipole_field


def main():
    sigmas = [3.0, 4.0, 5.0, 6.0]
    rows = []
    for sigma in sigmas:
        for R in DISTANCES_M:
            E = float(static_dipole_field(DEFAULT_P0_A_M, sigma, R))
            rows.append({"P_a_m": DEFAULT_P0_A_M, "sigma_s_per_m": sigma, "R_m": R, "E_v_per_m": E, "relative_to_sigma4": E / float(static_dipole_field(DEFAULT_P0_A_M, 4.0, R))})
    write_csv(TABLE_DIR / "conductivity_sensitivity.csv", ["P_a_m", "sigma_s_per_m", "R_m", "E_v_per_m", "relative_to_sigma4"], rows)

    dense_R = np.logspace(1, 3.5, 200)
    Emin = static_dipole_field(DEFAULT_P0_A_M, SIGMA_RANGE_S_PER_M[1], dense_R)
    Emax = static_dipole_field(DEFAULT_P0_A_M, SIGMA_RANGE_S_PER_M[0], dense_R)
    plt.figure(figsize=(7, 4.5))
    plt.loglog(dense_R, static_dipole_field(DEFAULT_P0_A_M, 4.0, dense_R), label="sigma=4 S/m")
    plt.fill_between(dense_R, Emin, Emax, alpha=0.25, label="sigma=3-6 S/m")
    plt.xlabel("range R (m)")
    plt.ylabel("electric field E (V/m)")
    plt.title("Conductivity sensitivity of dipole field")
    plt.grid(True, which="both", alpha=0.3)
    plt.legend()
    save_current_figure(FIGURE_DIR / "conductivity_sensitivity_band.png")


if __name__ == "__main__":
    main()
