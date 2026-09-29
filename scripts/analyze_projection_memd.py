"""Strict projection-based multivariate empirical mode decomposition checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import signal

from scripts.analyze_pre_electrochemical_dynamics import case_fields
from scripts.mentor_method_common import (
    METHOD_OUTPUT,
    all_cases,
    generic_matched_contrasts,
    load_analysis_signals,
    load_health_table,
    stable_seed,
    write_frame,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "results/mentor_aligned_raw_completion_v3/projection_memd"
SIGNALS = ("slow_pc1", "fast_residual_rms_pc1")
BANDS = {
    "0p05_0p15hz": (0.05, 0.15),
    "0p15_0p5hz": (0.15, 0.5),
    "0p5_2hz": (0.5, 2.0),
    "2_5hz": (2.0, 5.01),
}


def projection_directions(channel_count: int, count: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    directions = rng.normal(size=(count, channel_count))
    directions /= np.maximum(np.linalg.norm(directions, axis=1, keepdims=True), 1e-15)
    return directions


def envelope(values: np.ndarray, extrema: np.ndarray) -> np.ndarray | None:
    if len(extrema) < 2:
        return None
    indices = np.unique(np.r_[0, extrema, len(values) - 1]).astype(int)
    if len(indices) < 4:
        return None
    time = np.arange(len(values), dtype=float)
    return np.column_stack([
        np.interp(time, indices, values[indices, channel])
        for channel in range(values.shape[1])
    ])


def multivariate_local_mean(
    values: np.ndarray, directions: np.ndarray,
) -> tuple[np.ndarray | None, int]:
    envelope_sum = np.zeros_like(values, dtype=float)
    valid = 0
    for direction in directions:
        projection = values @ direction
        maxima, _ = signal.find_peaks(projection)
        minima, _ = signal.find_peaks(-projection)
        upper = envelope(values, maxima)
        lower = envelope(values, minima)
        if upper is None or lower is None:
            continue
        envelope_sum += 0.5 * (upper + lower)
        valid += 1
    if valid < max(4, len(directions) // 4):
        return None, valid
    return envelope_sum / valid, valid


def residual_has_modes(values: np.ndarray, directions: np.ndarray) -> bool:
    support = 0
    for direction in directions:
        projection = values @ direction
        extrema = len(signal.find_peaks(projection)[0]) + len(signal.find_peaks(-projection)[0])
        support += extrema >= 4
    return support >= max(4, len(directions) // 3)


def projection_memd(
    values: np.ndarray, direction_count: int = 16, maximum_imfs: int = 5,
    maximum_sifts: int = 10, stop_sd: float = 0.12, seed: int = 0,
) -> tuple[np.ndarray, np.ndarray, list[dict[str, float]]]:
    x = np.asarray(values, dtype=float)
    if x.ndim != 2 or x.shape[0] < 32 or x.shape[1] < 2:
        raise ValueError("Projection MEMD expects samples x at least two channels")
    directions = projection_directions(x.shape[1], direction_count, seed)
    residual = x.copy()
    imfs = []
    diagnostics = []
    for mode_index in range(maximum_imfs):
        if not residual_has_modes(residual, directions):
            break
        candidate = residual.copy()
        valid_directions = 0
        last_sd = np.inf
        for sift_index in range(maximum_sifts):
            local_mean, valid_directions = multivariate_local_mean(candidate, directions)
            if local_mean is None:
                break
            updated = candidate - local_mean
            last_sd = float(
                np.sum((candidate - updated) ** 2)
                / max(np.sum(candidate ** 2), 1e-15)
            )
            candidate = updated
            if sift_index >= 2 and last_sd <= stop_sd:
                break
        if valid_directions < max(4, direction_count // 4):
            break
        imfs.append(candidate)
        residual = residual - candidate
        diagnostics.append({
            "mode_index": mode_index + 1,
            "sift_count": sift_index + 1,
            "final_sift_sd": last_sd,
            "valid_direction_count": valid_directions,
        })
    return np.asarray(imfs), residual, diagnostics


def standardized_channels(values: np.ndarray) -> np.ndarray:
    x = signal.detrend(np.asarray(values, dtype=float), axis=0)
    scale = 1.4826 * np.median(np.abs(x - np.median(x, axis=0)), axis=0)
    return x / np.maximum(scale[None, :], 1e-12)


def mode_metrics(
    imfs: np.ndarray, residual: np.ndarray, original: np.ndarray,
    sample_rate: float,
) -> tuple[list[dict[str, float]], dict[str, float]]:
    total_energy = float(np.sum(original ** 2))
    rows = []
    band_energy = {name: 0.0 for name in BANDS}
    for mode_index, mode in enumerate(imfs, start=1):
        frequency = np.fft.rfftfreq(len(mode), 1.0 / sample_rate)
        power = np.abs(np.fft.rfft(
            signal.detrend(mode, axis=0) * signal.windows.hann(len(mode))[:, None], axis=0
        )) ** 2
        centers = np.sum(frequency[:, None] * power, axis=0) / np.maximum(
            np.sum(power, axis=0), 1e-15
        )
        energy = float(np.sum(mode ** 2))
        covariance = mode.T @ mode / max(len(mode), 1)
        eigenvalues = np.linalg.eigvalsh(covariance)
        center = float(np.median(centers))
        assigned = "outside"
        for name, (low, high) in BANDS.items():
            if low <= center < high:
                assigned = name
                band_energy[name] += energy
                break
        rows.append({
            "mode_index": mode_index,
            "center_frequency_hz_median": center,
            "center_frequency_hz_iqr": float(np.percentile(centers, 75) - np.percentile(centers, 25)),
            "energy_fraction": energy / max(total_energy, 1e-15),
            "channel_pc1_variance_fraction": float(
                eigenvalues[-1] / max(np.sum(eigenvalues), 1e-15)
            ),
            "assigned_band": assigned,
        })
    reconstructed = np.sum(imfs, axis=0) + residual if len(imfs) else residual
    summary = {
        **{
            f"memd_energy_fraction_{name}": energy / max(total_energy, 1e-15)
            for name, energy in band_energy.items()
        },
        "memd_mode_count": len(imfs),
        "memd_residual_energy_fraction": float(
            np.sum(residual ** 2) / max(total_energy, 1e-15)
        ),
        "memd_reconstruction_nrmse": float(
            np.sqrt(np.mean((reconstructed - original) ** 2))
            / max(np.std(original), 1e-15)
        ),
        "memd_dominant_mode_center_hz": (
            float(max(rows, key=lambda row: row["energy_fraction"])["center_frequency_hz_median"])
            if rows else np.nan
        ),
    }
    return rows, summary


def analyze_configuration(
    values: np.ndarray, sample_rate: float, directions: int, seed: int,
) -> tuple[list[dict[str, float]], dict[str, float], np.ndarray, np.ndarray, list[dict[str, float]]]:
    original = standardized_channels(values)
    imfs, residual, diagnostics = projection_memd(
        original, direction_count=directions, seed=seed
    )
    rows, summary = mode_metrics(imfs, residual, original, sample_rate)
    return rows, summary, imfs, residual, diagnostics


def synthetic_check(output: Path) -> dict[str, float]:
    sample_rate = 10.0
    time = np.arange(0.0, 120.0, 1.0 / sample_rate)
    rng = np.random.default_rng(20260829)
    channels = []
    for index in range(6):
        channels.append(
            (1.0 + 0.08 * index) * np.sin(2.0 * np.pi * 0.32 * time + 0.1 * index)
            + 0.45 * np.sin(2.0 * np.pi * 1.35 * time - 0.06 * index)
            + 0.08 * rng.normal(size=len(time))
        )
    values = np.column_stack(channels)
    imfs, residual, _ = projection_memd(values, direction_count=24, seed=20260829)
    rows, summary = mode_metrics(imfs, residual, values, sample_rate)
    centers = np.asarray([row["center_frequency_hz_median"] for row in rows])
    return {
        "synthetic_reconstruction_nrmse": summary["memd_reconstruction_nrmse"],
        "synthetic_0p32hz_nearest_error_hz": float(np.min(np.abs(centers - 0.32))) if len(centers) else np.nan,
        "synthetic_1p35hz_nearest_error_hz": float(np.min(np.abs(centers - 1.35))) if len(centers) else np.nan,
        "synthetic_mode_count": len(rows),
    }


def plot_representative(
    time: np.ndarray, original: np.ndarray, imfs: np.ndarray, residual: np.ndarray,
    output: Path,
) -> None:
    count = min(len(imfs), 4)
    fig, axes = plt.subplots(count + 2, 1, figsize=(12, 2.0 * (count + 2)), sharex=True)
    axes[0].plot(time, original[:, 0], color="#333333", linewidth=0.8)
    axes[0].set_ylabel("input")
    for index in range(count):
        axes[index + 1].plot(time, imfs[index, :, 0], color="#3976a8", linewidth=0.8)
        axes[index + 1].set_ylabel(f"IMF {index + 1}")
    axes[-1].plot(time, residual[:, 0], color="#bf5b45", linewidth=0.8)
    axes[-1].set_ylabel("residual")
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle("Projection MEMD: representative healthy channel")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    cache = args.output / "cases"
    cache.mkdir(parents=True, exist_ok=True)
    cases = all_cases()
    if args.limit:
        cases = cases[:args.limit]
    health = load_health_table()
    representative = None
    for index, case in enumerate(cases, start=1):
        path = cache / f"{case.case_id}.json"
        if path.exists() and not args.force:
            print(f"[{index:02d}/{len(cases):02d}] cached {case.case_id}", flush=True)
            continue
        print(f"[{index:02d}/{len(cases):02d}] {case.case_id}", flush=True)
        loaded = load_analysis_signals(case, health)
        payload: dict[str, object] = {**case_fields(case), "signals": {}}
        for signal_name in SIGNALS:
            values = loaded.channel_signals[signal_name]
            configurations = {}
            for directions in (16, 24):
                rows, summary, imfs, residual, diagnostics = analyze_configuration(
                    values, loaded.sample_rate_hz, directions,
                    stable_seed(case.case_id, signal_name, directions),
                )
                configurations[str(directions)] = {
                    "directions": directions,
                    "summary": summary,
                    "modes": rows,
                    "sift_diagnostics": diagnostics,
                }
                if representative is None and directions == 24:
                    representative = (
                        np.arange(len(values)) / loaded.sample_rate_hz,
                        standardized_channels(values), imfs, residual,
                    )
            payload["signals"][signal_name] = configurations
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_rows = []
    mode_rows = []
    robustness_rows = []
    expected = {case.case_id for case in cases}
    for path in sorted(cache.glob("*.json")):
        if path.stem not in expected:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        fields = {key: payload[key] for key in (
            "dataset", "case_id", "arrangement", "detector", "condition",
            "distance", "carrier_khz", "output_hz",
        )}
        for signal_name, configurations in payload["signals"].items():
            for direction_key, configuration in configurations.items():
                summary_rows.append({
                    **fields, "signal_name": signal_name,
                    "direction_count": int(direction_key), **configuration["summary"],
                })
                for row in configuration["modes"]:
                    mode_rows.append({
                        **fields, "signal_name": signal_name,
                        "direction_count": int(direction_key), **row,
                    })
            first = configurations["16"]["summary"]
            second = configurations["24"]["summary"]
            robustness_rows.append({
                **fields, "signal_name": signal_name,
                "dominant_center_absolute_difference_hz": abs(
                    first["memd_dominant_mode_center_hz"] - second["memd_dominant_mode_center_hz"]
                ),
                "mode_count_difference": abs(first["memd_mode_count"] - second["memd_mode_count"]),
                **{
                    f"energy_fraction_absolute_difference_{name}": abs(
                        first[f"memd_energy_fraction_{name}"]
                        - second[f"memd_energy_fraction_{name}"]
                    ) for name in BANDS
                },
            })
    summary = write_frame(args.output / "projection_memd_features.csv", summary_rows)
    write_frame(args.output / "projection_memd_modes.csv", mode_rows)
    write_frame(args.output / "projection_memd_parameter_robustness.csv", robustness_rows)
    main_summary = summary[summary["direction_count"] == 24].copy()
    feature_columns = [
        column for column in main_summary.columns
        if column.startswith("memd_") and pd.api.types.is_numeric_dtype(main_summary[column])
        and column not in {"memd_mode_count"}
    ]
    contrasts = generic_matched_contrasts(
        cases, main_summary, feature_columns, ["signal_name"]
    )
    write_frame(args.output / "projection_memd_matched_contrasts.csv", contrasts)
    check = synthetic_check(args.output)
    (args.output / "synthetic_validation.json").write_text(
        json.dumps(check, indent=2), encoding="utf-8"
    )
    if representative is not None:
        plot_representative(*representative, args.output / "projection_memd_representative.png")
    manifest = {
        "analysis": "strict_projection_memd",
        "case_count": len(cases),
        "signals": list(SIGNALS),
        "direction_counts": [16, 24],
        "implementation": "multivariate envelopes from extrema of hypersphere projections",
        "strict_multivariate": True,
        "synthetic_validation": check,
    }
    (args.output / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Output: {args.output}", flush=True)


if __name__ == "__main__":
    main()
