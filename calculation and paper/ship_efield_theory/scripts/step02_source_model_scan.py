from _common import FIGURE_DIR, TABLE_DIR, write_csv

import matplotlib.pyplot as plt
import numpy as np

from src.plotting import save_current_figure
from src.source_models import dipole_moment


def main():
    rows = []
    currents = np.array([1.0, -1.0])
    for L in [1.0, 3.0, 10.0, 30.0, 100.0]:
        positions = np.array([[0.5 * L, 0.0, 0.0], [-0.5 * L, 0.0, 0.0]])
        P = dipole_moment(currents, positions)
        rows.append({"I_a": 1.0, "separation_m": L, "P_x_a_m": float(P[0]), "P_y_a_m": float(P[1]), "P_z_a_m": float(P[2]), "P_norm_a_m": float(np.linalg.norm(P)), "current_sum_a": float(np.sum(currents))})
    write_csv(TABLE_DIR / "source_dipole_examples.csv", ["I_a", "separation_m", "P_x_a_m", "P_y_a_m", "P_z_a_m", "P_norm_a_m", "current_sum_a"], rows)

    plt.figure(figsize=(7, 4.5))
    plt.plot([r["separation_m"] for r in rows], [r["P_norm_a_m"] for r in rows], marker="o")
    plt.xlabel("source separation L (m)")
    plt.ylabel("dipole moment |P| (A m)")
    plt.title("Two-point current-source equivalent dipole")
    plt.grid(True, alpha=0.3)
    save_current_figure(FIGURE_DIR / "source_dipole_moment_vs_separation.png")


if __name__ == "__main__":
    main()
