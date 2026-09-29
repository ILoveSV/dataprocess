"""Plot exact full-record PSD comparisons for TC1 and TC2 under one VFD run."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / 'experiments/20260806'
ARCHIVE = RESULT / "exact_archive"
HEALTH = RESULT / "channel_health.csv"

RUN_CASES = {
    "TC1": "vfd_tc1_12k_30hz",
    "TC2": "vfd_tc2_12k_30hz",
}
STOP_CASES = {
    "TC1": "vfd_tc1_vfd_stop",
    "TC2": "vfd_tc2_vfd_stop",
}


def healthy_indices(case_id: str, health: pd.DataFrame) -> set[int]:
    selected = health.loc[health["case_id"] == case_id]
    bad = set(selected.loc[selected["automatic_bad"], "channel_index"].astype(int) - 1)
    return set(range(len(selected))) - bad


def load_common_psd(detector: str, health: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    run_case = RUN_CASES[detector]
    stop_case = STOP_CASES[detector]
    common = sorted(healthy_indices(run_case, health) & healthy_indices(stop_case, health))
    if len(common) < 4:
        raise RuntimeError(f"Only {len(common)} common healthy channels remain for {detector}")

    with np.load(ARCHIVE / run_case / "welch.npz") as run_data:
        frequency = np.asarray(run_data["frequency_hz"], dtype=np.float64)
        run_psd = np.median(np.asarray(run_data["psd_mean"], dtype=np.float64)[common], axis=0)
    with np.load(ARCHIVE / stop_case / "welch.npz") as stop_data:
        stop_frequency = np.asarray(stop_data["frequency_hz"], dtype=np.float64)
        stop_psd = np.median(np.asarray(stop_data["psd_mean"], dtype=np.float64)[common], axis=0)
    if not np.allclose(frequency, stop_frequency, rtol=0.0, atol=1e-9):
        raise RuntimeError(f"Frequency grids differ for {detector}")
    return frequency, run_psd, stop_psd, len(common)


def plot_band(low_hz: float, high_hz: float, output_name: str) -> None:
    health = pd.read_csv(HEALTH)
    health["automatic_bad"] = health["automatic_bad"].astype(bool)
    loaded = {detector: load_common_psd(detector, health) for detector in ("TC1", "TC2")}

    fig, axes = plt.subplots(1, 2, figsize=(15.2, 5.8), sharex=True, sharey=True, constrained_layout=True)
    for axis, detector in zip(axes, ("TC1", "TC2")):
        frequency, run_psd, stop_psd, channel_count = loaded[detector]
        use = (frequency >= low_hz) & (frequency <= high_hz)
        x = frequency[use] / 1000.0
        run_db = 10.0 * np.log10(np.maximum(run_psd[use], 1e-300))
        stop_db = 10.0 * np.log10(np.maximum(stop_psd[use], 1e-300))
        peak_index = int(np.argmax(run_db))
        peak_khz = float(x[peak_index])

        axis.plot(x, stop_db, color="#7A7F87", lw=0.75, alpha=0.85, label="VFD STOP")
        axis.plot(x, run_db, color="#B31B34", lw=0.85, alpha=0.95, label="12 kHz / 30 Hz RUN")
        axis.axvline(peak_khz, color="#B31B34", lw=1.0, ls="--", alpha=0.8)
        axis.set_title(f"{detector}: strongest RUN peak {peak_khz:.2f} kHz", fontsize=14, weight="bold")
        axis.set_xlabel("Frequency (kHz)")
        axis.set_xlim(low_hz / 1000.0, high_hz / 1000.0)
        axis.grid(True, color="#D5D8DC", lw=0.6, alpha=0.8)
        axis.legend(loc="upper right", frameon=False, fontsize=10)
        axis.text(
            0.985,
            0.035,
            f"median of {channel_count} common healthy channels",
            transform=axis.transAxes,
            ha="right",
            va="bottom",
            fontsize=9,
            color="#667085",
        )

    axes[0].set_ylabel("PSD (dB re 1 V²/Hz)")
    fig.savefig(RESULT / output_name, dpi=220, facecolor="white")
    plt.close(fig)


def main() -> None:
    plot_band(50_000.0, 60_000.0, "vfd_detector_psd_50_60khz.png")
    plot_band(130_000.0, 160_000.0, "vfd_detector_psd_130_160khz.png")


if __name__ == "__main__":
    main()
