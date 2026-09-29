from _common import FIGURE_DIR, TABLE_DIR, write_csv

import matplotlib.pyplot as plt
import numpy as np

from src.constants import CLOSEST_APPROACH_M, DEFAULT_SPEED_M_PER_S
from src.geometry import range_vs_time
from src.plotting import save_current_figure


def main():
    times = np.linspace(-300.0, 300.0, 601)
    rows = []
    plt.figure(figsize=(7, 4.5))
    for R0 in CLOSEST_APPROACH_M:
        ranges = range_vs_time(R0, DEFAULT_SPEED_M_PER_S, times)
        plt.plot(times, ranges, label=f"R0={R0:g} m")
        for t, R in zip(times[::60], ranges[::60]):
            rows.append({"R0_m": R0, "speed_m_per_s": DEFAULT_SPEED_M_PER_S, "time_s": float(t), "R_m": float(R)})
    write_csv(TABLE_DIR / "geometry_range_vs_time.csv", ["R0_m", "speed_m_per_s", "time_s", "R_m"], rows)
    plt.xlabel("time t (s)")
    plt.ylabel("range R(t) (m)")
    plt.title("Straight-line closest-approach range")
    plt.legend()
    plt.grid(True, alpha=0.3)
    save_current_figure(FIGURE_DIR / "range_vs_time.png")


if __name__ == "__main__":
    main()
