"""Recompute the complete 2026-05-12 batch and test cross-distance recognition."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import fft as sp_fft
from scipy import signal
from sklearn.metrics import balanced_accuracy_score

from scripts.analyze_mentor_wavelet_relaxation import cwt_analysis
from scripts.analyze_pre_electrochemical_dynamics import (
    red_noise_periodicity_pvalues,
    sinusoid_fit_metrics,
)
from scripts.analyze_pulse_relaxation_raw import dynamic_healthy_channels


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = Path(r"E:\Lab\process\26.5.12\time")
DEFAULT_OUTPUT = PROJECT_ROOT / "results/mentor_aligned_raw_completion_v3/batch_20260512"
CHANNELS = [f"channel{index}" for index in range(1, 13)]
BANDS = {
    "5_100hz": (5.0, 100.0),
    "100_1khz": (100.0, 1_000.0),
    "1_20khz": (1_000.0, 20_000.0),
    "20_80khz": (20_000.0, 80_000.0),
    "80_200khz": (80_000.0, 199_000.0),
}
GROUP_PATTERN = re.compile(r"(?P<distance>\d+)m(?P<condition>0|30|50)hz", re.I)


def metadata_path(path: Path) -> Path:
    return path.with_name(path.stem + "_metadata.json")


def discover_files(root: Path) -> list[tuple[str, str, Path]]:
    rows = []
    for directory in sorted(root.iterdir()):
        if not directory.is_dir():
            continue
        match = GROUP_PATTERN.fullmatch(directory.name)
        if not match:
            continue
        for path in sorted(directory.glob("*.csv")):
            rows.append((match.group("distance") + "m", match.group("condition") + "hz", path))
    return rows


def file_key(path: Path) -> str:
    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:20]


def block_envelopes(values: np.ndarray, sample_rate: float) -> dict[str, np.ndarray]:
    block_size = int(round(0.1 * sample_rate))
    subblock_size = int(round(0.001 * sample_rate))
    block_count = len(values) // block_size
    blocks = values[:block_count * block_size].reshape(
        block_count, block_size, values.shape[1]
    )
    subblocks = blocks.reshape(
        block_count, block_size // subblock_size, subblock_size, values.shape[1]
    )
    submeans = np.mean(subblocks, axis=2)
    residual = subblocks - submeans[:, :, None, :]
    return {
        "slow_mean": np.mean(blocks, axis=1),
        "broadband_rms": np.std(blocks, axis=1),
        "subkhz_rms": np.std(submeans, axis=1),
        "fast_residual_rms": np.sqrt(np.mean(residual ** 2, axis=(1, 2))),
        "difference_rms": np.sqrt(0.5 * np.mean(np.diff(blocks, axis=1) ** 2, axis=1)),
    }


def spectral_features(
    values: np.ndarray, healthy: np.ndarray, sample_rate: float,
    window_count: int = 8, nperseg: int = 65_536,
) -> dict[str, float]:
    starts = np.linspace(0, len(values) - nperseg, window_count, dtype=int)
    taper = signal.windows.hann(nperseg, sym=False).astype(np.float32)
    psd_rows = []
    for start in starts:
        piece = values[start:start + nperseg, healthy]
        piece = piece - np.mean(piece, axis=0, keepdims=True)
        transformed = sp_fft.rfft(piece * taper[:, None], axis=0, workers=-1)
        power = np.abs(transformed) ** 2 / (sample_rate * np.sum(taper ** 2))
        power[1:-1] *= 2.0
        psd_rows.append(power)
    psd = np.asarray(psd_rows, dtype=np.float64)
    frequency = sp_fft.rfftfreq(nperseg, 1.0 / sample_rate)
    result = {}
    for name, (low, high) in BANDS.items():
        use = (frequency >= low) & (frequency < high)
        integrated = np.trapezoid(psd[:, use], frequency[use], axis=1)
        channel_median = np.median(integrated, axis=0)
        result[f"bandpower_{name}_db"] = float(
            10.0 * np.log10(max(np.median(channel_median), 1e-300))
        )
        result[f"bandpower_{name}_temporal_iqr_db"] = float(np.median(
            np.ptp(np.percentile(
                10.0 * np.log10(np.maximum(integrated, 1e-300)), [25, 75], axis=0
            ), axis=0)
        ))
    return result


def analyze_file(
    distance: str, condition: str, path: Path, cache: Path,
) -> dict[str, object]:
    metadata = json.loads(metadata_path(path).read_text(encoding="utf-8"))
    frame = pd.read_csv(path, usecols=CHANNELS, dtype=np.float32)
    values = frame.to_numpy(dtype=np.float32, copy=False)
    sample_rate = float(metadata["sampling_rate_hz"])
    healthy, health_rows = dynamic_healthy_channels(values)
    envelopes = block_envelopes(values, sample_rate)
    np.savez_compressed(
        cache / f"{file_key(path)}.npz",
        **{name: np.asarray(item, dtype=np.float32) for name, item in envelopes.items()},
        healthy_indices=healthy,
    )
    return {
        "distance": distance,
        "condition": condition,
        "source_csv": str(path),
        "source_filename": str(metadata["filename"]),
        "start_time": str(metadata["start_time"]),
        "sample_rate_hz": sample_rate,
        "duration_s": float(metadata["total_duration_seconds"]),
        "healthy_channel_count": len(healthy),
        "healthy_channel_indices_1based": (healthy + 1).tolist(),
        "automatic_bad_channels_1based": [
            row["channel_index"] for row in health_rows if row["automatic_bad"]
        ],
        **spectral_features(values, healthy, sample_rate),
    }


def interpolate_missing(values: np.ndarray) -> np.ndarray:
    result = np.asarray(values, dtype=float).copy()
    indices = np.arange(len(result))
    for column in range(result.shape[1]):
        finite = np.isfinite(result[:, column])
        if np.sum(finite) < 3:
            result[:, column] = np.nanmedian(result)
        elif not np.all(finite):
            result[:, column] = np.interp(indices, indices[finite], result[finite, column])
    return result


def group_pc(values: np.ndarray) -> np.ndarray:
    clean = interpolate_missing(values)
    clean = signal.detrend(clean, axis=0)
    scale = 1.4826 * np.median(np.abs(clean - np.median(clean, axis=0)), axis=0)
    clean /= np.maximum(scale[None, :], 1e-12)
    covariance = clean.T @ clean / len(clean)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    weights = eigenvectors[:, -1]
    response = clean @ weights
    return response / max(np.std(response), 1e-15)


def load_group_signal(group: pd.DataFrame, cache: Path, feature: str) -> np.ndarray:
    rows = []
    for item in group.sort_values("start_time").itertuples(index=False):
        path = Path(item.source_csv)
        with np.load(cache / f"{file_key(path)}.npz") as data:
            values = np.asarray(data[feature], dtype=float)
            healthy = set(np.asarray(data["healthy_indices"], dtype=int).tolist())
        for channel in range(values.shape[1]):
            if channel not in healthy:
                values[:, channel] = np.nan
        if feature != "slow_mean":
            values = np.log10(np.maximum(values, 1e-30))
        rows.append(values)
    return group_pc(np.vstack(rows))


def analyze_groups(files: pd.DataFrame, cache: Path) -> pd.DataFrame:
    rows = []
    for (distance, condition), group in files.groupby(["distance", "condition"]):
        row: dict[str, object] = {
            "distance": distance,
            "condition": condition,
            "file_count": len(group),
            "duration_s": float(group["duration_s"].sum()),
            "median_healthy_channel_count": float(group["healthy_channel_count"].median()),
        }
        for name in BANDS:
            row[f"bandpower_{name}_db"] = float(group[f"bandpower_{name}_db"].median())
            row[f"bandpower_{name}_between_file_iqr_db"] = float(
                group[f"bandpower_{name}_db"].quantile(0.75)
                - group[f"bandpower_{name}_db"].quantile(0.25)
            )
        for feature in (
            "slow_mean", "broadband_rms", "subkhz_rms",
            "fast_residual_rms", "difference_rms",
        ):
            values = load_group_signal(group, cache, feature)
            cwt = cwt_analysis(values, 10.0)["summary"]
            for key in (
                "global_peak_frequency_hz", "global_peak_power_to_red_noise",
                "significant_point_fraction", "significant_ridge_fraction",
            ):
                row[f"{feature}_cwt_{key}"] = float(cwt[key])
            fit = sinusoid_fit_metrics(values, 10.0, 1.0 / 3.1)
            pvalues, phi = red_noise_periodicity_pvalues(
                values, 10.0, [1.0 / 3.1], repeats=499,
                seed=20260512 + int(distance[:-1]) * 100 + int(condition[:-2]),
            )
            row[f"{feature}_3p1s_amplitude_sigma"] = float(fit["sinusoid_amplitude"])
            row[f"{feature}_3p1s_variance_fraction"] = float(fit["sinusoid_variance_fraction"])
            row[f"{feature}_3p1s_red_noise_pointwise_p"] = float(
                pvalues[0]["red_noise_pointwise_p"]
            )
            row[f"{feature}_3p1s_red_noise_familywise_p"] = float(
                pvalues[0]["red_noise_search_familywise_p"]
            )
            row[f"{feature}_ar1_phi"] = phi
        rows.append(row)
    return pd.DataFrame(rows)


def matched_contrasts(groups: pd.DataFrame) -> pd.DataFrame:
    rows = []
    numeric = [
        column for column in groups.columns
        if pd.api.types.is_numeric_dtype(groups[column])
        and column not in {"file_count", "duration_s", "median_healthy_channel_count"}
    ]
    for distance, distance_group in groups.groupby("distance"):
        background = distance_group[distance_group["condition"] == "0hz"].iloc[0]
        for condition in ("30hz", "50hz"):
            active = distance_group[distance_group["condition"] == condition].iloc[0]
            for feature in numeric:
                rows.append({
                    "distance": distance,
                    "condition": condition,
                    "reference_condition": "0hz",
                    "feature": feature,
                    "active": active[feature],
                    "reference": background[feature],
                    "difference": active[feature] - background[feature],
                })
    return pd.DataFrame(rows)


def grouped_predictions(
    frame: pd.DataFrame, feature_columns: list[str], labels: np.ndarray,
) -> np.ndarray:
    predictions = np.empty(len(frame), dtype=object)
    distances = frame["distance"].to_numpy()
    values = frame[feature_columns].to_numpy(dtype=float)
    for held in np.unique(distances):
        train = distances != held
        test = ~train
        center = np.nanmedian(values[train], axis=0)
        scale = 1.4826 * np.nanmedian(np.abs(values[train] - center), axis=0)
        scale = np.where(np.isfinite(scale) & (scale > 1e-12), scale, 1.0)
        train_values = np.nan_to_num((values[train] - center) / scale)
        test_values = np.nan_to_num((values[test] - center) / scale)
        classes = np.unique(labels[train])
        centroids = np.stack([
            np.mean(train_values[labels[train] == label], axis=0) for label in classes
        ])
        distance_matrix = np.sum(
            (test_values[:, None, :] - centroids[None, :, :]) ** 2, axis=2
        )
        predictions[test] = classes[np.argmin(distance_matrix, axis=1)]
    return predictions


def recognition_rows(groups: pd.DataFrame, permutations: int = 999) -> pd.DataFrame:
    baseline = [f"bandpower_{name}_db" for name in BANDS]
    new = [
        f"{feature}_cwt_global_peak_power_to_red_noise"
        for feature in ("slow_mean", "broadband_rms", "fast_residual_rms", "difference_rms")
    ] + [
        f"{feature}_3p1s_amplitude_sigma"
        for feature in ("slow_mean", "broadband_rms", "difference_rms")
    ]
    feature_sets = {
        "baseline_spectral": baseline,
        "new_temporal": new,
        "combined": baseline + new,
    }
    rng = np.random.default_rng(20260512)
    rows = []
    tasks = {
        "0_30_50_cross_distance": groups.copy(),
        "30_50_cross_distance": groups[groups["condition"].isin(["30hz", "50hz"])].copy(),
    }
    for task, frame in tasks.items():
        labels = frame["condition"].to_numpy(dtype=object)
        for feature_set, columns in feature_sets.items():
            predicted = grouped_predictions(frame, columns, labels)
            observed = balanced_accuracy_score(labels, predicted)
            null = []
            for _ in range(permutations):
                shuffled = labels.copy()
                for distance in frame["distance"].unique():
                    use = frame["distance"].to_numpy() == distance
                    shuffled[use] = rng.permutation(shuffled[use])
                permuted_prediction = grouped_predictions(frame, columns, shuffled)
                null.append(balanced_accuracy_score(shuffled, permuted_prediction))
            null_values = np.asarray(null)
            rows.append({
                "task": task,
                "feature_set": feature_set,
                "sample_count": len(frame),
                "held_out_distance_count": frame["distance"].nunique(),
                "feature_count": len(columns),
                "balanced_accuracy": float(observed),
                "permutation_null_median": float(np.median(null_values)),
                "permutation_null_q95": float(np.percentile(null_values, 95)),
                "permutation_p": float(
                    (np.sum(null_values >= observed) + 1) / (len(null_values) + 1)
                ),
                "predictions": ";".join(map(str, predicted)),
                "labels": ";".join(map(str, labels)),
            })
    return pd.DataFrame(rows)


def cross_batch_direction(contrasts: pd.DataFrame) -> pd.DataFrame:
    old = pd.read_csv(
        PROJECT_ROOT / "results/mentor_aligned_pre_electrochemical_v1/matched_band_contrasts.csv"
    )
    old = old[
        (old["dataset"].astype(str) == "20260617")
        & (old["reference_condition"] == "background")
    ].copy()
    rows = []
    for condition in ("30hz", "50hz"):
        for band_name in BANDS:
            feature = f"bandpower_{band_name}_db"
            current = contrasts[
                (contrasts["condition"] == condition) & (contrasts["feature"] == feature)
            ]["difference"].to_numpy(dtype=float)
            historical = old[
                (old["condition"] == condition) & (old["band_name"] == band_name)
            ]["median_difference_db"].to_numpy(dtype=float)
            combined = np.r_[current, historical]
            dominant = np.sign(np.median(combined))
            rows.append({
                "condition": condition,
                "band_name": band_name,
                "20260512_distance_count": len(current),
                "20260617_distance_count": len(historical),
                "20260512_median_difference_db": float(np.median(current)),
                "20260617_median_difference_db": float(np.median(historical)),
                "batch_median_same_direction": bool(
                    np.sign(np.median(current)) == np.sign(np.median(historical))
                ),
                "combined_dominant_direction_fraction": float(np.mean(np.sign(combined) == dominant)),
            })
    return pd.DataFrame(rows)


def plot_summary(groups: pd.DataFrame, output: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    colors = {"0hz": "#777777", "30hz": "#3976a8", "50hz": "#bf5b45"}
    for condition in ("0hz", "30hz", "50hz"):
        selected = groups[groups["condition"] == condition].copy()
        selected["distance_m"] = selected["distance"].str[:-1].astype(float)
        axes[0].plot(
            selected["distance_m"], selected["bandpower_80_200khz_db"],
            marker="o", label=condition, color=colors[condition],
        )
        axes[1].plot(
            selected["distance_m"], selected["difference_rms_3p1s_amplitude_sigma"],
            marker="o", label=condition, color=colors[condition],
        )
    axes[0].set_ylabel("Median 80-200 kHz band power (dB)")
    axes[1].set_ylabel("3.1 s fitted amplitude (standardized)")
    for axis in axes:
        axis.set_xlabel("Distance (m)")
        axis.set_xticks([2, 3, 5])
        axis.legend()
        axis.grid(alpha=0.25)
    axes[0].set_title("Full 360-file spectral batch")
    axes[1].set_title("Group-concatenated low-frequency check")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--permutations", type=int, default=999)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    cache = args.output / "file_cache"
    cache.mkdir(parents=True, exist_ok=True)
    files = discover_files(args.input)
    if args.limit:
        files = files[:args.limit]
    rows = []
    for index, (distance, condition, path) in enumerate(files, start=1):
        summary_path = cache / f"{file_key(path)}.json"
        if summary_path.exists() and not args.force:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            print(f"[{index:03d}/{len(files):03d}] cached {path.name}", flush=True)
        else:
            print(f"[{index:03d}/{len(files):03d}] {distance} {condition} {path.name}", flush=True)
            payload = analyze_file(distance, condition, path, cache)
            summary_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        rows.append(payload)
    file_frame = pd.DataFrame(rows)
    file_frame.to_csv(args.output / "file_features_dynamic_health.csv", index=False)
    group_frame = analyze_groups(file_frame, cache)
    group_frame.to_csv(args.output / "distance_condition_features.csv", index=False)
    contrasts = matched_contrasts(group_frame)
    contrasts.to_csv(args.output / "matched_background_contrasts.csv", index=False)
    recognition = recognition_rows(group_frame, permutations=args.permutations)
    recognition.to_csv(args.output / "cross_distance_identifiability.csv", index=False)
    directions = cross_batch_direction(contrasts)
    directions.to_csv(args.output / "cross_batch_direction_consistency.csv", index=False)
    plot_summary(group_frame, args.output / "batch_20260512_summary.png")
    manifest = {
        "analysis": "20260512_full_batch_completion",
        "input": str(args.input),
        "file_count": len(file_frame),
        "group_count": len(group_frame),
        "dynamic_bad_channel_per_file": True,
        "independence_rule": "40 adjacent files are one distance-condition run, not 40 independent replicates",
        "cross_validation": "leave one distance out",
    }
    (args.output / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Output: {args.output}", flush=True)


if __name__ == "__main__":
    main()
