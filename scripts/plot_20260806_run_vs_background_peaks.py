"""Plot representative narrowband RUN peaks against pure background."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from scipy.signal import find_peaks

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial"]
plt.rcParams["axes.unicode_minus"] = False


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results" / "experiment_20260806"
ARCHIVE = RESULT / "exact_archive"
HEALTH = RESULT / "channel_health.csv"
OUTPUT = RESULT / "report_figures"

BACKGROUND_CASE = "vfd_tc1_background"
RUN_CASE = "vfd_tc1_12k_50hz"


def healthy_indices(case_id: str, health: pd.DataFrame) -> set[int]:
    selected = health.loc[health["case_id"] == case_id]
    bad = set(selected.loc[selected["automatic_bad"], "channel_index"].astype(int) - 1)
    return set(range(len(selected))) - bad


def load_psd(case_id: str) -> tuple[np.ndarray, np.ndarray]:
    with np.load(ARCHIVE / case_id / "welch.npz") as data:
        return (
            np.asarray(data["frequency_hz"], dtype=np.float64),
            np.asarray(data["psd_mean"], dtype=np.float64),
        )


def peak_preserving_decimate(
    x: np.ndarray, y: np.ndarray, target_points: int = 1600
) -> tuple[np.ndarray, np.ndarray]:
    if x.size <= target_points:
        return x, y
    selected: list[int] = [0, x.size - 1]
    for indices in np.array_split(np.arange(x.size), target_points // 2):
        if indices.size == 0:
            continue
        local = y[indices]
        selected.extend(
            [
                int(indices[int(np.argmin(local))]),
                int(indices[int(np.argmax(local))]),
            ]
        )
    keep = np.asarray(sorted(set(selected)), dtype=int)
    return x[keep], y[keep]


def select_peak(
    frequency: np.ndarray,
    run_db: np.ndarray,
    background_db: np.ndarray,
) -> int:
    peaks, properties = find_peaks(run_db, prominence=1.0, distance=8)
    if peaks.size == 0:
        return int(np.argmax(run_db - background_db))
    contrast = run_db[peaks] - background_db[peaks]
    score = contrast + 0.25 * properties["prominences"]
    return int(peaks[int(np.argmax(score))])


def strongest_peak(y: np.ndarray) -> int:
    peaks, _ = find_peaks(y, prominence=1.0, distance=8)
    if peaks.size == 0:
        return int(np.argmax(y))
    return int(peaks[int(np.argmax(y[peaks]))])


def plot_band_stacked(
    frequency: np.ndarray,
    run_psd: np.ndarray,
    background_psd: np.ndarray,
    low_hz: float,
    high_hz: float,
    output_name: str,
    channel_count: int,
) -> None:
    use = (frequency >= low_hz) & (frequency <= high_hz)
    x = frequency[use] / 1000.0
    run_db = 10.0 * np.log10(np.maximum(run_psd[use], 1e-300))
    background_db = 10.0 * np.log10(np.maximum(background_psd[use], 1e-300))
    run_peak_index = select_peak(x, run_db, background_db)
    background_peak_index = strongest_peak(background_db)
    run_peak_khz = float(x[run_peak_index])
    background_peak_khz = float(x[background_peak_index])
    peak_gain_db = float(run_db[run_peak_index] - background_db[run_peak_index])

    background_x, background_y = peak_preserving_decimate(x, background_db)
    run_x, run_y = peak_preserving_decimate(x, run_db)

    fig, axes = plt.subplots(
        2,
        1,
        figsize=(13.4, 8.8),
        sharex=True,
        sharey=True,
        constrained_layout=True,
    )
    background_axis, run_axis = axes
    background_axis.plot(
        background_x,
        background_y,
        color="#4F5965",
        lw=0.85,
        alpha=0.95,
    )
    run_axis.plot(
        run_x,
        run_y,
        color="#B31B34",
        lw=0.85,
        alpha=0.95,
    )
    for axis in axes:
        axis.axvline(run_peak_khz, color="#B31B34", lw=0.9, ls=":", alpha=0.55)
        axis.grid(True, color="#D7DADF", lw=0.6, alpha=0.8)
        axis.set_ylabel("PSD（dB re 1 V²/Hz）", fontsize=11)
    background_axis.scatter(
        [background_peak_khz],
        [background_db[background_peak_index]],
        s=28,
        color="#4F5965",
        edgecolor="white",
        linewidth=0.7,
        zorder=5,
    )
    run_axis.scatter(
        [run_peak_khz],
        [run_db[run_peak_index]],
        s=28,
        color="#B31B34",
        edgecolor="white",
        linewidth=0.7,
        zorder=5,
    )
    background_axis.annotate(
        f"背景最强峰：{background_peak_khz:.2f} kHz",
        xy=(background_peak_khz, background_db[background_peak_index]),
        xytext=(18, -38),
        textcoords="offset points",
        fontsize=10,
        color="#3F4853",
        arrowprops={"arrowstyle": "->", "color": "#4F5965", "lw": 0.8},
    )
    run_axis.annotate(
        f"RUN最强峰：{run_peak_khz:.2f} kHz\n该频点较背景 +{peak_gain_db:.1f} dB",
        xy=(run_peak_khz, run_db[run_peak_index]),
        xytext=(18, -42),
        textcoords="offset points",
        fontsize=10,
        color="#8D172A",
        arrowprops={"arrowstyle": "->", "color": "#B31B34", "lw": 0.8},
    )
    background_axis.set_title("纯背景（TC1）", fontsize=12, weight="bold", loc="left")
    run_axis.set_title(
        "运行工况（TC1，载波12 kHz，输出50 Hz）",
        fontsize=12,
        weight="bold",
        loc="left",
    )
    run_axis.set_xlabel("频率（kHz）", fontsize=11)
    run_axis.set_xlim(low_hz / 1000.0, high_hz / 1000.0)
    low_limit = float(np.percentile(np.concatenate([background_db, run_db]), 0.2)) - 0.5
    high_limit = float(max(np.max(run_db), np.max(background_db))) + 0.7
    run_axis.set_ylim(low_limit, high_limit)
    background_axis.text(
        0.99,
        0.92,
        f"精确全记录Welch PSD；{channel_count}个共同健康通道中位数",
        transform=background_axis.transAxes,
        ha="right",
        va="top",
        fontsize=8.5,
        color="#667085",
    )
    fig.suptitle(
        f"{low_hz / 1000:.0f}–{high_hz / 1000:.0f} kHz：纯背景与50 Hz运行频谱上下对比",
        fontsize=17,
        weight="bold",
    )
    fig.savefig(OUTPUT / output_name, dpi=220, facecolor="white")
    plt.close(fig)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    health = pd.read_csv(HEALTH)
    health["automatic_bad"] = health["automatic_bad"].astype(bool)
    common = sorted(
        healthy_indices(BACKGROUND_CASE, health) & healthy_indices(RUN_CASE, health)
    )
    frequency, background_channels = load_psd(BACKGROUND_CASE)
    run_frequency, run_channels = load_psd(RUN_CASE)
    if not np.allclose(frequency, run_frequency, rtol=0.0, atol=1e-9):
        raise RuntimeError("Frequency grids differ")
    background_psd = np.median(background_channels[common], axis=0)
    run_psd = np.median(run_channels[common], axis=0)

    plot_band_stacked(
        frequency,
        run_psd,
        background_psd,
        50_000.0,
        100_000.0,
        "run_vs_background_50_100khz_stacked.png",
        len(common),
    )
    plot_band_stacked(
        frequency,
        run_psd,
        background_psd,
        100_000.0,
        200_000.0,
        "run_vs_background_100_200khz_stacked.png",
        len(common),
    )


if __name__ == "__main__":
    main()
