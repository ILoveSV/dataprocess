from _common import FIGURE_DIR, TABLE_DIR, write_csv

import matplotlib.pyplot as plt
import numpy as np

from src.constants import DEFAULT_P0_A_M, DEFAULT_SIGMA_S_PER_M
from src.plotting import save_current_figure
from src.receiver_model import mems_voltage
from src.source_models import moving_envelope


def main():
    times = np.linspace(-200.0, 200.0, 801)
    E = moving_envelope(times, 300.0, 5.0, DEFAULT_P0_A_M, DEFAULT_SIGMA_S_PER_M)
    K_values = [0.0, 1e-3, 1e-2, 1e-1]
    rows = []
    for K in K_values:
        V = mems_voltage(E, K)
        for t, e, v in zip(times[::8], E[::8], V[::8]):
            rows.append({"K_v_per_v_per_m": K, "time_s": float(t), "E_v_per_m": float(e), "V_out_v": float(v), "note": "K is parameterized, not calibrated"})
    write_csv(TABLE_DIR / "mems_response_parameterized.csv", ["K_v_per_v_per_m", "time_s", "E_v_per_m", "V_out_v", "note"], rows)

    plt.figure(figsize=(7, 4.5))
    for K in K_values[1:]:
        plt.semilogy(times, np.abs(mems_voltage(E, K)), label=f"K={K:g} V/(V/m)")
    plt.xlabel("time t (s)")
    plt.ylabel("|V_out| (V)")
    plt.title("Parameterized MEMS linear response")
    plt.grid(True, which="both", alpha=0.3)
    plt.legend()
    save_current_figure(FIGURE_DIR / "mems_response_parameterized.png")


if __name__ == "__main__":
    main()
