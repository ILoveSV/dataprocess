from _common import FIGURE_DIR, TABLE_DIR, write_csv

import matplotlib.pyplot as plt
import numpy as np

from src.noise_model import continuous_noise, line_noise, total_noise
from src.plotting import save_current_figure


def main():
    freqs = np.linspace(0.1, 80.0, 1200)
    terms = [
        {"N0": 1e-10, "f0_hz": 1.0, "alpha": 1.0},
        {"N0": 2e-11, "f0_hz": 10.0, "alpha": 0.2},
    ]
    peaks = [(50.0, 8e-10), (60.0, 4e-10)]
    cont = np.sqrt(sum(continuous_noise(freqs, **term) ** 2 for term in terms))
    line = line_noise(freqs, peaks, bandwidth_hz=0.25)
    total = total_noise(freqs, terms, peaks, bandwidth_hz=0.25, floor=1e-12)
    rows = [{"frequency_hz": float(f), "continuous_noise": float(c), "line_noise": float(l), "total_noise": float(t)} for f, c, l, t in zip(freqs[::4], cont[::4], line[::4], total[::4])]
    write_csv(TABLE_DIR / "noise_spectrum_examples.csv", ["frequency_hz", "continuous_noise", "line_noise", "total_noise"], rows)

    plt.figure(figsize=(7, 4.5))
    plt.semilogy(freqs, cont, label="continuous")
    plt.semilogy(freqs, line + 1e-13, label="line peaks")
    plt.semilogy(freqs, total, label="total")
    plt.xlabel("frequency f (Hz)")
    plt.ylabel("noise amplitude (field units)")
    plt.title("Parameterized low-frequency noise spectrum")
    plt.grid(True, which="both", alpha=0.3)
    plt.legend()
    save_current_figure(FIGURE_DIR / "noise_spectrum_examples.png")


if __name__ == "__main__":
    main()
