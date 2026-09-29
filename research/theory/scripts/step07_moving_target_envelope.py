from _common import FIGURE_DIR, TABLE_DIR, write_csv

import matplotlib.pyplot as plt
import numpy as np

from src.constants import DEFAULT_FS_HZ, DEFAULT_M1, DEFAULT_P0_A_M, DEFAULT_SIGMA_S_PER_M, DEFAULT_SPEED_M_PER_S
from src.geometry import range_vs_time
from src.plotting import save_current_figure
from src.source_models import harmonic_modulation, moving_envelope, moving_envelope_timescale, moving_shaft_signal


def main():
    R0 = 300.0
    times = np.linspace(-300.0, 300.0, 1201)
    ranges = range_vs_time(R0, DEFAULT_SPEED_M_PER_S, times)
    envelope = moving_envelope(times, R0, DEFAULT_SPEED_M_PER_S, DEFAULT_P0_A_M, DEFAULT_SIGMA_S_PER_M)
    m_list = [harmonic_modulation(DEFAULT_M1, n) for n in range(1, 6)]
    shaft = moving_shaft_signal(times, R0, DEFAULT_SPEED_M_PER_S, DEFAULT_P0_A_M, DEFAULT_SIGMA_S_PER_M, DEFAULT_FS_HZ, m_list)

    rows = [{"time_s": float(t), "R0_m": R0, "speed_m_per_s": DEFAULT_SPEED_M_PER_S, "R_m": float(R), "E_env_v_per_m": float(E), "E_shaft_v_per_m": float(S)} for t, R, E, S in zip(times, ranges, envelope, shaft)]
    write_csv(TABLE_DIR / "moving_target_envelope.csv", ["time_s", "R0_m", "speed_m_per_s", "R_m", "E_env_v_per_m", "E_shaft_v_per_m"], rows)

    scale_rows = []
    for R0_i in [50.0, 100.0, 300.0, 500.0, 1000.0]:
        scale = moving_envelope_timescale(R0_i, DEFAULT_SPEED_M_PER_S)
        scale_rows.append({
            "R0_m": R0_i,
            "speed_m_per_s": DEFAULT_SPEED_M_PER_S,
            "tau_s": scale["tau_s"],
            "t_half_s": scale["t_half_s"],
            "full_half_width_s": scale["full_half_width_s"],
        })
    write_csv(TABLE_DIR / "moving_envelope_timescale.csv", ["R0_m", "speed_m_per_s", "tau_s", "t_half_s", "full_half_width_s"], scale_rows)

    plt.figure(figsize=(7, 4.5))
    plt.plot(times, ranges)
    plt.xlabel("time t (s)")
    plt.ylabel("range R(t) (m)")
    plt.title("Moving-target range envelope")
    plt.grid(True, alpha=0.3)
    save_current_figure(FIGURE_DIR / "moving_range_vs_time.png")

    plt.figure(figsize=(7, 4.5))
    plt.semilogy(times, envelope)
    plt.xlabel("time t (s)")
    plt.ylabel("E_env(t) (V/m)")
    plt.title("Moving-target electric-field envelope")
    plt.grid(True, which="both", alpha=0.3)
    save_current_figure(FIGURE_DIR / "moving_E_env_vs_time.png")

    plt.figure(figsize=(7, 4.5))
    plt.plot(times, shaft)
    plt.xlabel("time t (s)")
    plt.ylabel("E_shaft(t) (V/m)")
    plt.title("Moving shaft-rate signal, parameterized")
    plt.grid(True, alpha=0.3)
    save_current_figure(FIGURE_DIR / "moving_E_shaft_vs_time.png")


if __name__ == "__main__":
    main()
