"""Block-wise TDMS analysis for the 2026-07-31 two-detector experiment.

The analysis separates direct slow voltage, sub-kHz fluctuation, broadband
fluctuation, and within-millisecond residual energy. Water-cycle frequencies
come from the independently analyzed MP4 audio, so the TDMS test does not pick
its target frequency after looking at the sensor result.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib
import numpy as np
from nptdms import TdmsFile
from scipy import signal

from exact_tdms_archive import (
    ExactArchiveConfig,
    archive_complete,
    build_exact_archive,
    load_exact_archive,
)
from exact_analysis_metrics import low_frequency_blind_rows, temporal_band_rows
from channel_quality import (
    assess_channel_quality,
    common_valid_channel_indices,
    valid_channel_indices,
)

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from analyze_20260731_media import band_limited, periodicity, robust_zscore


DEFAULT_ROOT = Path(r"D:\Lab\raw\26.7.31")
BLOCK_SECONDS = 0.1
SPECTRUM_NFFT = 262_144
TRIM_START_SECONDS = 15.0
TRIM_END_SECONDS = 5.0
REFERENCE_PERIODS = {
    "morning_30hz": 3.0600,
    "morning_50hz": 2.5104,
    "afternoon_30hz": 3.0250,
    "afternoon_50hz": 2.5438,
}
VIDEO_START_MINUS_TDMS_START_SECONDS = {
    "morning_30hz": 4.592990,
    "afternoon_30hz": -16.674447,
    "afternoon_50hz": -19.619840,
}


@dataclass(frozen=True)
class TdmsCase:
    case_id: str
    session: str
    detector: str
    condition: str
    folder: Path


def tdms_cases(root: Path) -> list[TdmsCase]:
    return [
        TdmsCase("morning_background", "morning", "TC2", "background", root / "tc2(morn)" / "background"),
        TdmsCase("morning_vfd_stop", "morning", "TC2", "vfd_stop", root / "tc2(morn)" / "VFDbackground"),
        TdmsCase("morning_30hz", "morning", "TC2", "30hz", root / "tc2(morn)" / "30"),
        TdmsCase("morning_50hz", "morning", "TC2", "50hz", root / "tc2(morn)" / "50"),
        TdmsCase("afternoon_background", "afternoon", "TC1", "background", root / "tc1(afternoon)" / "background"),
        TdmsCase("afternoon_vfd_stop", "afternoon", "TC1", "vfd_stop", root / "tc1(afternoon)" / "VFDbackground"),
        TdmsCase("afternoon_30hz", "afternoon", "TC1", "30hz", root / "tc1(afternoon)" / "30hz"),
        TdmsCase("afternoon_50hz", "afternoon", "TC1", "50hz", root / "tc1(afternoon)" / "50hz"),
    ]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def robust_channel_matrix(values: np.ndarray) -> np.ndarray:
    matrix = np.column_stack([robust_zscore(values[:, index]) for index in range(values.shape[1])])
    return np.clip(matrix, -8.0, 8.0)


def prepare_feature(values: np.ndarray, feature_name: str, fs: float) -> np.ndarray:
    prepared = np.asarray(values, dtype=np.float64)
    if feature_name != "slow_mean":
        positive = prepared[prepared > 0]
        floor = float(np.percentile(positive, 0.1)) if len(positive) else 1e-15
        prepared = np.log10(np.maximum(prepared, floor))
    start = int(round(TRIM_START_SECONDS * fs))
    end = len(prepared) - int(round(TRIM_END_SECONDS * fs))
    if end - start < int(round(30.0 * fs)):
        raise ValueError("Stable-state trim leaves less than 30 seconds")
    return prepared[start:end]


def first_component(values: np.ndarray) -> tuple[np.ndarray, float]:
    matrix = robust_channel_matrix(values)
    matrix = np.nan_to_num(matrix)
    u, singular, _ = np.linalg.svd(matrix, full_matrices=False)
    score = u[:, 0] * singular[0]
    explained = singular[0] ** 2 / max(float(np.sum(singular ** 2)), 1e-15)
    return robust_zscore(score), float(explained)


def reference_response(values: np.ndarray, fs: float, period_s: float) -> dict[str, float]:
    filtered = band_limited(values, fs)
    frequency, psd = signal.periodogram(filtered, fs=fs, window="hann", detrend="linear")
    target = 1.0 / period_s
    resolution = frequency[1] - frequency[0]
    target_half_width = max(1.5 * resolution, 0.012)
    target_mask = np.abs(frequency - target) <= target_half_width
    baseline_mask = (
        (frequency >= 0.06)
        & (frequency <= 0.70)
        & (np.abs(frequency - target) >= max(3.0 * resolution, 0.04))
    )
    target_power = float(np.max(psd[target_mask]))
    baseline = float(np.median(psd[baseline_mask]))
    snr = target_power / max(baseline, 1e-15)

    time_s = np.arange(len(filtered)) / fs
    design = np.column_stack([
        np.ones(len(filtered)),
        np.sin(2.0 * np.pi * target * time_s),
        np.cos(2.0 * np.pi * target * time_s),
    ])
    fit = design @ np.linalg.lstsq(design, filtered, rcond=None)[0]
    residual = np.sum((filtered - fit) ** 2)
    total = np.sum((filtered - np.mean(filtered)) ** 2)
    return {
        "reference_frequency_hz": float(target),
        "reference_spectral_snr": float(snr),
        "reference_sine_r2": float(max(0.0, 1.0 - residual / max(total, 1e-15))),
    }


def process_tdms(path: Path) -> dict[str, object]:
    with TdmsFile.open(path) as tdms:
        group = tdms.groups()[0]
        channels = group.channels()
        channel_names = [channel.name for channel in channels]
        sample_count = len(channels[0])
        dt = float(channels[0].properties["wf_increment"])
        sample_rate = 1.0 / dt
        block_size = int(round(BLOCK_SECONDS * sample_rate))
        sub_size = int(round(sample_rate / 1000.0))
        sub_per_block = block_size // sub_size
        if block_size % sub_size:
            raise ValueError("The 0.1 s block must contain whole 1 ms sub-blocks")

        feature_lists = {
            name: [[] for _ in channels]
            for name in ("slow_mean", "broadband_rms", "subkhz_rms", "fast_residual_rms", "difference_rms")
        }
        leftovers = [np.empty(0, dtype=np.float64) for _ in channels]

        centers = np.array([0.20, 0.50, 0.80]) * sample_count
        starts = np.round(centers - SPECTRUM_NFFT / 2).astype(int)
        starts = np.clip(starts, 0, sample_count - SPECTRUM_NFFT)
        # Keep absolute ~5 V samples in float64; float32 would quantize away
        # sub-microvolt high-frequency content before detrending.
        spectral = np.full((len(channels), len(starts), SPECTRUM_NFFT), np.nan, dtype=np.float64)

        for chunk_index, data_chunk in enumerate(tdms.data_chunks()):
            chunk_group = data_chunk[group.name]
            chunk_channels = chunk_group.channels()
            if not chunk_channels or len(chunk_channels[0]) == 0:
                continue
            chunk_offset = int(chunk_channels[0].offset)
            chunk_end = chunk_offset + len(chunk_channels[0])

            for channel_index, chunk_channel in enumerate(chunk_channels):
                data = np.asarray(chunk_channel[:], dtype=np.float64)
                combined = np.concatenate((leftovers[channel_index], data))
                block_count = len(combined) // block_size
                used = block_count * block_size
                if block_count:
                    blocks = combined[:used].reshape(block_count, block_size)
                    sub_blocks = blocks.reshape(block_count, sub_per_block, sub_size)
                    sub_means = np.mean(sub_blocks, axis=2)
                    residual = sub_blocks - sub_means[:, :, None]
                    feature_lists["slow_mean"][channel_index].extend(np.mean(blocks, axis=1))
                    feature_lists["broadband_rms"][channel_index].extend(np.std(blocks, axis=1))
                    feature_lists["subkhz_rms"][channel_index].extend(np.std(sub_means, axis=1))
                    feature_lists["fast_residual_rms"][channel_index].extend(
                        np.sqrt(np.mean(residual * residual, axis=(1, 2)))
                    )
                    feature_lists["difference_rms"][channel_index].extend(
                        np.sqrt(0.5 * np.mean(np.diff(blocks, axis=1) ** 2, axis=1))
                    )
                leftovers[channel_index] = combined[used:].copy()

                for segment_index, start in enumerate(starts):
                    end = start + SPECTRUM_NFFT
                    overlap_start = max(start, chunk_offset)
                    overlap_end = min(end, chunk_end)
                    if overlap_end <= overlap_start:
                        continue
                    source_start = overlap_start - chunk_offset
                    source_end = overlap_end - chunk_offset
                    target_start = overlap_start - start
                    target_end = overlap_end - start
                    spectral[channel_index, segment_index, target_start:target_end] = data[
                        source_start:source_end
                    ]

            if chunk_index and chunk_index % 500 == 0:
                print(f"  streamed {100.0 * chunk_end / sample_count:5.1f}%")

    feature_arrays: dict[str, np.ndarray] = {}
    for name, per_channel in feature_lists.items():
        common_length = min(len(values) for values in per_channel)
        feature_arrays[name] = np.column_stack([
            np.asarray(values[:common_length], dtype=np.float64) for values in per_channel
        ])

    if np.isnan(spectral).any():
        missing = int(np.sum(np.isnan(spectral)))
        raise RuntimeError(f"Spectrum extraction left {missing} missing samples")
    window = signal.windows.hann(SPECTRUM_NFFT, sym=False)
    normalization = sample_rate * np.sum(window ** 2)
    spectra = []
    for channel_segments in spectral:
        segment_psd = []
        for segment_values in channel_segments:
            values = signal.detrend(segment_values.astype(np.float64))
            fft = np.fft.rfft(values * window)
            psd = np.abs(fft) ** 2 / normalization
            psd[1:-1] *= 2.0
            segment_psd.append(psd)
        spectra.append(np.median(segment_psd, axis=0))
    frequency = np.fft.rfftfreq(SPECTRUM_NFFT, 1.0 / sample_rate)
    return {
        "sample_rate": float(sample_rate),
        "duration_s": float(sample_count / sample_rate),
        "channel_names": channel_names,
        "envelope_fs": float(1.0 / BLOCK_SECONDS),
        "features": feature_arrays,
        "frequency": frequency,
        "psd": np.asarray(spectra),
    }


def bandpowers(frequency: np.ndarray, psd: np.ndarray) -> dict[str, float]:
    bands = {
        "5_100hz": (5.0, 100.0),
        "100_1khz": (100.0, 1_000.0),
        "1_20khz": (1_000.0, 20_000.0),
        "20_80khz": (20_000.0, 80_000.0),
        "80_200khz": (80_000.0, 200_000.0),
    }
    result = {}
    for name, (low, high) in bands.items():
        use = (frequency >= low) & (frequency < high)
        result[name] = float(np.trapz(psd[use], frequency[use]))
    return result


def peak_rows(case: TdmsCase, frequency: np.ndarray, psd: np.ndarray,
              valid: list[int] | None = None) -> list[dict[str, object]]:
    aggregate = np.median(psd[valid] if valid is not None else psd, axis=0)
    use = (frequency >= 1_000.0) & (frequency <= 199_500.0)
    freq_use = frequency[use]
    db = 10.0 * np.log10(aggregate[use] + 1e-30)
    baseline = signal.medfilt(db, kernel_size=1001)
    excess = db - baseline
    peaks, properties = signal.find_peaks(excess, prominence=3.0, distance=20)
    order = np.argsort(properties["prominences"])[::-1][:20]
    rows = []
    for rank, peak_position in enumerate(peaks[order], start=1):
        rows.append({
            "case_id": case.case_id,
            "session": case.session,
            "detector": case.detector,
            "condition": case.condition,
            "rank": rank,
            "frequency_hz": float(freq_use[peak_position]),
            "prominence_db": float(properties["prominences"][order][rank - 1]),
            "psd_db": float(db[peak_position]),
        })
    return rows


def load_cached_result(path: Path) -> dict[str, object]:
    with np.load(path) as data:
        features = {
            name: data[name]
            for name in ("slow_mean", "broadband_rms", "subkhz_rms", "fast_residual_rms", "difference_rms")
        }
        frequency = data["frequency_hz"]
        return {
            "sample_rate": float(2.0 * frequency[-1]),
            "duration_s": float(len(data["time_s"]) * BLOCK_SECONDS),
            "channel_names": data["channel_names"].tolist(),
            "envelope_fs": float(1.0 / BLOCK_SECONDS),
            "features": features,
            "frequency": frequency,
            "psd": data["psd"],
        }


def correlation_with_small_lag(x: np.ndarray, y: np.ndarray, fs: float) -> dict[str, float]:
    x = band_limited(x, fs)
    y = band_limited(y, fs)
    zero = float(np.corrcoef(x, y)[0, 1])
    max_shift = int(round(1.0 * fs))
    values = []
    shifts = list(range(-max_shift, max_shift + 1))
    for shift in shifts:
        if shift < 0:
            values.append(float(np.corrcoef(x[-shift:], y[:shift])[0, 1]))
        elif shift > 0:
            values.append(float(np.corrcoef(x[:-shift], y[shift:])[0, 1]))
        else:
            values.append(zero)
    best = int(np.nanargmax(np.abs(values)))
    return {
        "zero_lag_correlation": zero,
        "max_abs_correlation_pm1s": values[best],
        "best_lag_s": shifts[best] / fs,
    }


def media_alignment_rows(
    output_root: Path,
    results: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    media_path = output_root.parent / "media" / "media_feature_timeseries.csv"
    if not media_path.exists():
        print(f"Skipping media alignment because {media_path} is missing", flush=True)
        return []
    import pandas as pd

    media = pd.read_csv(media_path)
    rows = []
    for case_id, offset_s in VIDEO_START_MINUS_TDMS_START_SECONDS.items():
        result = results[case_id]
        valid_channels = valid_channel_indices(result)
        for source in ("mp4_audio", "video_motion"):
            reference = media[(media["case_id"] == case_id) & (media["source"] == source)]
            media_time = reference["time_s"].to_numpy(dtype=float)
            media_values = reference["envelope_z"].to_numpy(dtype=float)
            for feature_name, raw_values in result["features"].items():
                stable = prepare_feature(raw_values, feature_name, result["envelope_fs"])
                tdms_time = TRIM_START_SECONDS + np.arange(len(stable)) / result["envelope_fs"]
                corresponding_media_time = tdms_time - offset_s
                valid = (
                    (corresponding_media_time >= media_time[0])
                    & (corresponding_media_time <= media_time[-1])
                )
                if np.sum(valid) < int(20.0 * result["envelope_fs"]):
                    continue
                interpolated_media = np.interp(corresponding_media_time[valid], media_time, media_values)
                component, explained = first_component(stable[:, valid_channels])
                pca_correlation = correlation_with_small_lag(
                    component[valid], interpolated_media, result["envelope_fs"]
                )
                channel_correlations = [
                    correlation_with_small_lag(
                        robust_zscore(stable[valid, channel_index]),
                        interpolated_media,
                        result["envelope_fs"],
                    )
                    for channel_index in valid_channels
                ]
                zero = np.array([item["zero_lag_correlation"] for item in channel_correlations])
                best = np.array([item["max_abs_correlation_pm1s"] for item in channel_correlations])
                rows.append({
                    "case_id": case_id,
                    "source": source,
                    "feature": feature_name,
                    "timestamp_offset_video_minus_tdms_s": offset_s,
                    "overlap_duration_s": float(np.sum(valid) / result["envelope_fs"]),
                    "healthy_channel_count": len(valid_channels),
                    "healthy_channels_1based": ";".join(
                        str(index + 1) for index in valid_channels
                    ),
                    "pca_explained_fraction": explained,
                    **{f"pca_{key}": value for key, value in pca_correlation.items()},
                    "median_channel_abs_zero_lag_correlation": float(np.median(np.abs(zero))),
                    "max_channel_abs_zero_lag_correlation": float(np.max(np.abs(zero))),
                    "support_fraction_abs_zero_lag_gt0_3": float(np.mean(np.abs(zero) > 0.3)),
                    "median_channel_abs_correlation_pm1s": float(np.median(np.abs(best))),
                    "support_fraction_abs_pm1s_gt0_3": float(np.mean(np.abs(best) > 0.3)),
                })
    return rows


def band_contrast_rows(
    cases: list[TdmsCase],
    bandpower_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    bands = ["5_100hz", "100_1khz", "1_20khz", "20_80khz", "80_200khz"]
    lookup = {(row["case_id"], row["channel_index"]): row for row in bandpower_rows}
    rows = []
    for session in ("morning", "afternoon"):
        session_cases = [case for case in cases if case.session == session]
        for baseline_condition in ("background", "vfd_stop"):
            baseline = next(case for case in session_cases if case.condition == baseline_condition)
            for case in session_cases:
                if case.condition == baseline_condition:
                    continue
                for band in bands:
                    valid_channels = [
                        channel_index for channel_index in range(1, 13)
                        if not bool(lookup[(case.case_id, channel_index)].get("automatic_bad", False))
                        and not bool(lookup[(baseline.case_id, channel_index)].get("automatic_bad", False))
                    ]
                    if len(valid_channels) < 4:
                        raise ValueError(
                            f"Only {len(valid_channels)} healthy paired channels for "
                            f"{case.case_id} versus {baseline.case_id}"
                        )
                    contrast = np.array([
                        10.0 * np.log10(
                            float(lookup[(case.case_id, channel_index)][band])
                            / float(lookup[(baseline.case_id, channel_index)][band])
                        )
                        for channel_index in valid_channels
                    ])
                    rows.append({
                        "session": session,
                        "detector": case.detector,
                        "condition": case.condition,
                        "baseline_condition": baseline_condition,
                        "band": band,
                        "median_contrast_db": float(np.median(contrast)),
                        "q25_contrast_db": float(np.percentile(contrast, 25)),
                        "q75_contrast_db": float(np.percentile(contrast, 75)),
                        "positive_channel_fraction": float(np.mean(contrast > 0.0)),
                        "common_healthy_channel_count": len(valid_channels),
                        "common_healthy_channels_1based": ";".join(
                            str(index) for index in valid_channels
                        ),
                    })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results") / "experiment_20260731" / "tdms",
    )
    parser.add_argument(
        "--exact",
        action="store_true",
        help="Build/load full-coverage archives instead of three-window caches.",
    )
    parser.add_argument(
        "--archive-only",
        action="store_true",
        help="Build exact archives and stop before experiment-level reports.",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    exact_dir = args.output / "exact_archive"
    if args.exact:
        exact_dir.mkdir(parents=True, exist_ok=True)

    cases = tdms_cases(args.root)
    results: dict[str, dict[str, object]] = {}
    envelope_rows: list[dict[str, object]] = []
    channel_rows: list[dict[str, object]] = []
    bandpower_rows: list[dict[str, object]] = []
    peak_output_rows: list[dict[str, object]] = []
    health_rows: list[dict[str, object]] = []

    for case in cases:
        cache_path = args.output / f"{case.case_id}_features.npz"
        archive_path = exact_dir / case.case_id
        if args.exact and archive_complete(archive_path):
            print(f"Loading exact archive for {case.case_id}", flush=True)
            result = load_exact_archive(archive_path)
        elif args.exact:
            matches = list(case.folder.glob("*.tdms"))
            if len(matches) != 1:
                raise RuntimeError(f"Expected one TDMS in {case.folder}, found {len(matches)}")
            print(f"Building exact archive for {case.case_id}", flush=True)
            build_exact_archive(matches[0], archive_path, ExactArchiveConfig())
            result = load_exact_archive(archive_path)
        elif cache_path.exists():
            print(f"Loading cached blocks for {case.case_id}", flush=True)
            result = load_cached_result(cache_path)
        else:
            matches = list(case.folder.glob("*.tdms"))
            if len(matches) != 1:
                raise RuntimeError(f"Expected one TDMS in {case.folder}, found {len(matches)}")
            print(f"Processing {case.case_id}: {matches[0].name}", flush=True)
            result = process_tdms(matches[0])
        results[case.case_id] = result
        quality = assess_channel_quality(result)
        valid = valid_channel_indices(result)
        print(f"  duration={result['duration_s']:.1f}s, fs={result['sample_rate']:.1f}Hz", flush=True)

        save_payload = {
            "time_s": np.arange(next(iter(result["features"].values())).shape[0]) / result["envelope_fs"],
            "frequency_hz": result["frequency"],
            "psd": result["psd"],
            "channel_names": np.asarray(result["channel_names"]),
        }
        save_payload.update(result["features"])
        if not args.exact and not cache_path.exists():
            np.savez_compressed(cache_path, **save_payload)

        for feature_name, values in result["features"].items():
            stable_values = prepare_feature(values, feature_name, result["envelope_fs"])
            pca, explained = first_component(stable_values[:, valid])
            pca_period = periodicity(pca, result["envelope_fs"])
            envelope_rows.append({
                "case_id": case.case_id,
                "session": case.session,
                "detector": case.detector,
                "condition": case.condition,
                "feature": feature_name,
                "healthy_channel_count": len(valid),
                "healthy_channels_1based": ";".join(str(index + 1) for index in valid),
                "pca_explained_fraction": explained,
                **{f"pca_{key}": value for key, value in pca_period.items()},
            })
            for channel_index, channel_name in enumerate(result["channel_names"]):
                channel_period = periodicity(stable_values[:, channel_index], result["envelope_fs"])
                channel_rows.append({
                    "case_id": case.case_id,
                    "session": case.session,
                    "detector": case.detector,
                    "condition": case.condition,
                    "feature": feature_name,
                    "channel_index": channel_index + 1,
                    "channel_name": channel_name,
                    "automatic_bad": quality[channel_index]["automatic_bad"],
                    "automatic_suspect": quality[channel_index]["automatic_suspect"],
                    **channel_period,
                })

        for channel_index, channel_name in enumerate(result["channel_names"]):
            bandpower_rows.append({
                "case_id": case.case_id,
                "session": case.session,
                "detector": case.detector,
                "condition": case.condition,
                "channel_index": channel_index + 1,
                "channel_name": channel_name,
                "automatic_bad": quality[channel_index]["automatic_bad"],
                "automatic_suspect": quality[channel_index]["automatic_suspect"],
                **bandpowers(result["frequency"], result["psd"][channel_index]),
            })
            if "health" in result:
                health_rows.append({
                    "case_id": case.case_id,
                    "session": case.session,
                    "detector": case.detector,
                    "condition": case.condition,
                    **result["health"][channel_index],
                    **quality[channel_index],
                })
        peak_output_rows.extend(peak_rows(case, result["frequency"], result["psd"], valid))

    if args.archive_only:
        print(f"Exact archives complete: {exact_dir.resolve()}", flush=True)
        return

    reference_rows: list[dict[str, object]] = []
    for active_id, period_s in REFERENCE_PERIODS.items():
        active_case = next(case for case in cases if case.case_id == active_id)
        active_result = results[active_id]
        comparison_cases = [case for case in cases if case.session == active_case.session]
        for comparison in comparison_cases:
            result = results[comparison.case_id]
            valid = common_valid_channel_indices(active_result, result)
            for feature_name, values in result["features"].items():
                stable_values = prepare_feature(values, feature_name, result["envelope_fs"])
                selected_values = stable_values[:, valid]
                pca, explained = first_component(selected_values)
                pca_response = reference_response(pca, result["envelope_fs"], period_s)
                channel_responses = [
                    reference_response(selected_values[:, index], result["envelope_fs"], period_s)
                    for index in range(selected_values.shape[1])
                ]
                channel_snr = np.array([item["reference_spectral_snr"] for item in channel_responses])
                channel_r2 = np.array([item["reference_sine_r2"] for item in channel_responses])
                reference_rows.append({
                    "target_case_id": active_id,
                    "target_period_s": period_s,
                    "source_case_id": comparison.case_id,
                    "source_condition": comparison.condition,
                    "session": comparison.session,
                    "detector": comparison.detector,
                    "feature": feature_name,
                    "common_healthy_channel_count": len(valid),
                    "common_healthy_channels_1based": ";".join(
                        str(index + 1) for index in valid
                    ),
                    "pca_explained_fraction": explained,
                    **{f"pca_{key}": value for key, value in pca_response.items()},
                    "median_channel_reference_snr": float(np.median(channel_snr)),
                    "max_channel_reference_snr": float(np.max(channel_snr)),
                    "median_channel_sine_r2": float(np.median(channel_r2)),
                    "support_fraction_snr_gt5": float(np.mean(channel_snr > 5.0)),
                })

    write_csv(args.output / "tdms_envelope_periodicity.csv", envelope_rows)
    write_csv(args.output / "tdms_channel_periodicity.csv", channel_rows)
    write_csv(args.output / "tdms_reference_period_test.csv", reference_rows)
    write_csv(args.output / "tdms_bandpower.csv", bandpower_rows)
    write_csv(args.output / "tdms_high_frequency_peaks.csv", peak_output_rows)
    write_csv(args.output / "tdms_channel_health.csv", health_rows)
    if args.exact:
        write_csv(
            args.output / "tdms_exact_temporal_band_stability.csv",
            temporal_band_rows(cases, results, valid_channel_indices),
        )
        write_csv(
            args.output / "tdms_exact_low_frequency_blind_peaks.csv",
            low_frequency_blind_rows(cases, results, valid_channel_indices),
        )
    alignment_rows = media_alignment_rows(args.output, results)
    write_csv(args.output / "tdms_media_alignment.csv", alignment_rows)
    contrast_rows = band_contrast_rows(cases, bandpower_rows)
    write_csv(args.output / "tdms_band_contrasts.csv", contrast_rows)

    condition_order = ["background", "vfd_stop", "30hz", "50hz"]
    feature_order = ["slow_mean", "subkhz_rms", "broadband_rms", "fast_residual_rms"]
    fig, axes = plt.subplots(4, 2, figsize=(15, 12), sharex=False, constrained_layout=True)
    for column, session in enumerate(("morning", "afternoon")):
        for row, feature_name in enumerate(feature_order):
            axis = axes[row, column]
            for condition in condition_order:
                case = next(item for item in cases if item.session == session and item.condition == condition)
                result = results[case.case_id]
                stable_values = prepare_feature(
                    result["features"][feature_name], feature_name, result["envelope_fs"]
                )
                component, _ = first_component(
                    stable_values[:, valid_channel_indices(result)]
                )
                time_s = TRIM_START_SECONDS + np.arange(len(component)) / result["envelope_fs"]
                axis.plot(time_s, component, lw=0.75, label=condition)
            detector = "TC2" if session == "morning" else "TC1"
            axis.set_title(f"{session} ({detector}) / {feature_name}")
            axis.set_ylabel("PCA robust z")
            axis.grid(alpha=0.2)
            if row == 0:
                axis.legend(fontsize=8, ncol=2)
            if row == len(feature_order) - 1:
                axis.set_xlabel("Time (s)")
    fig.savefig(args.output / "tdms_envelope_overview.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(15, 5.5), constrained_layout=True)
    for axis, session in zip(axes, ("morning", "afternoon")):
        background = next(item for item in cases if item.session == session and item.condition == "background")
        background_result = results[background.case_id]
        frequency = results[background.case_id]["frequency"]
        use = (frequency >= 10.0) & (frequency <= 200_000.0)
        for condition in condition_order:
            case = next(item for item in cases if item.session == session and item.condition == condition)
            result = results[case.case_id]
            valid = common_valid_channel_indices(result, background_result)
            aggregate = np.median(result["psd"][valid], axis=0)
            bg_psd = np.median(background_result["psd"][valid], axis=0)
            contrast_db = 10.0 * np.log10((aggregate + 1e-30) / (bg_psd + 1e-30))
            axis.semilogx(frequency[use], contrast_db[use], lw=0.7, label=condition)
        axis.axhline(0.0, color="black", lw=0.6)
        detector = "TC2" if session == "morning" else "TC1"
        axis.set_title(f"{session} ({detector}): median-channel PSD relative to background")
        axis.set_xlabel("Frequency (Hz)")
        axis.set_ylabel("Contrast (dB)")
        axis.set_ylim(-20, 45)
        axis.grid(alpha=0.2, which="both")
        axis.legend(fontsize=8)
    fig.savefig(args.output / "tdms_spectrum_contrast.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5), constrained_layout=True)
    high_bands = ["1_20khz", "20_80khz", "80_200khz"]
    positions = np.arange(len(high_bands))
    for axis, session in zip(axes, ("morning", "afternoon")):
        width = 0.24
        for index, condition in enumerate(("vfd_stop", "30hz", "50hz")):
            selected = [
                row for row in contrast_rows
                if row["session"] == session
                and row["baseline_condition"] == "background"
                and row["condition"] == condition
                and row["band"] in high_bands
            ]
            selected.sort(key=lambda row: high_bands.index(row["band"]))
            center = np.array([row["median_contrast_db"] for row in selected])
            low = center - np.array([row["q25_contrast_db"] for row in selected])
            high = np.array([row["q75_contrast_db"] for row in selected]) - center
            axis.bar(positions + (index - 1) * width, center, width, yerr=[low, high],
                     capsize=3, label=condition)
        axis.axhline(0.0, color="black", lw=0.7)
        axis.set_xticks(positions, high_bands)
        axis.set_ylabel("Paired contrast to background (dB)")
        detector = "TC2" if session == "morning" else "TC1"
        axis.set_title(f"{session} ({detector})")
        axis.grid(axis="y", alpha=0.2)
        axis.legend(fontsize=8)
    fig.savefig(args.output / "tdms_high_band_contrasts.png", dpi=180)
    plt.close(fig)

    manifest = {
        "block_seconds": BLOCK_SECONDS,
        "spectrum_nfft": SPECTRUM_NFFT,
        "stable_state_trim_seconds": [TRIM_START_SECONDS, TRIM_END_SECONDS],
        "reference_periods_s": REFERENCE_PERIODS,
        "video_start_minus_tdms_start_seconds": VIDEO_START_MINUS_TDMS_START_SECONDS,
        "channel_exclusion": (
            "dynamic per acquisition; comparisons use the healthy-channel intersection"
        ),
        "cases": [case.__dict__ | {"folder": str(case.folder)} for case in cases],
    }
    (args.output / "analysis_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Wrote {args.output.resolve()}", flush=True)


if __name__ == "__main__":
    main()
