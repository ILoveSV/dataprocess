from _common import FIGURE_DIR, TABLE_DIR, write_csv

import matplotlib.pyplot as plt
import numpy as np

from src.constants import DEFAULT_P0_A_M, DEFAULT_SIGMA_S_PER_M
from src.plotting import save_current_figure
from src.propagation import static_dipole_field
from src.receiver_model import equivalent_gradient, small_baseline_voltage
from src.source_models import moving_envelope


def main():
    times = np.linspace(-200.0, 200.0, 801)
    envelope = moving_envelope(times, 300.0, 5.0, DEFAULT_P0_A_M, DEFAULT_SIGMA_S_PER_M)
    baselines = {
        "x_0p5m": np.array([0.5, 0.0, 0.0]),
        "x_1m": np.array([1.0, 0.0, 0.0]),
        "y_1m": np.array([0.0, 1.0, 0.0]),
    }
    E_vec = np.column_stack([envelope, np.zeros_like(envelope), np.zeros_like(envelope)])
    rows = []
    for name, baseline in baselines.items():
        dV = small_baseline_voltage(E_vec, baseline)
        G = equivalent_gradient(dV, np.linalg.norm(baseline))
        for t, e, dv, g in zip(times[::8], envelope[::8], dV[::8], G[::8]):
            rows.append({"channel": name, "time_s": float(t), "E_x_v_per_m": float(e), "baseline_m": float(np.linalg.norm(baseline)), "deltaV_v": float(dv), "gradient_v_per_m": float(g)})
    write_csv(TABLE_DIR / "receiver_array_voltage.csv", ["channel", "time_s", "E_x_v_per_m", "baseline_m", "deltaV_v", "gradient_v_per_m"], rows)

    plt.figure(figsize=(7, 4.5))
    for name, baseline in baselines.items():
        dV = small_baseline_voltage(E_vec, baseline)
        plt.plot(times, dV, label=name)
    plt.xlabel("time t (s)")
    plt.ylabel("Delta V (V)")
    plt.title("Small-baseline voltage response")
    plt.grid(True, alpha=0.3)
    plt.legend()
    save_current_figure(FIGURE_DIR / "receiver_array_deltaV_vs_time.png")


if __name__ == "__main__":
    main()
