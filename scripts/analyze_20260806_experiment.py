"""Analyze the 2026-08-06 detector-crossover and VFD-carrier experiments."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime
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


DEFAULT_ROOT = Path(r"D:\Lab\raw\26.8.6")
BLOCK_SECONDS = 0.1
SPECTRUM_NFFT = 262_144
TRIM_START_SECONDS = 15.0
TRIM_END_SECONDS = 5.0


@dataclass(frozen=True)
class Case:
    case_id: str
    experiment: str
    detector: str
    arrangement: str
    position: str
    condition: str
    carrier_khz: int | None
    output_hz: int | None
    folder: Path


def cases(root: Path) -> list[Case]:
    output: list[Case] = []
    for arrangement, suffix in (("duo1", "duo"), ("duo2", "duo2")):
        condition_folders = {
            "background": "background",
            "vfd_stop": "vfd",
            "30hz": "30" if arrangement == "duo1" else "30hz",
            "50hz": "50" if arrangement == "duo1" else "50hz",
        }
        for detector in ("TC1", "TC2"):
            position = "A" if (arrangement == "duo1") == (detector == "TC1") else "B"
            base = root / f"{detector.lower()}{suffix}"
            for condition, folder_name in condition_folders.items():
                output_hz = int(condition[:2]) if condition in ("30hz", "50hz") else None
                output.append(Case(
                    f"{arrangement}_{detector.lower()}_{condition}",
                    "duo",
                    detector,
                    arrangement,
                    position,
                    condition,
                    4 if output_hz else None,
                    output_hz,
                    base / folder_name,
                ))

    for detector in ("TC1", "TC2"):
        base = root / f"{detector.lower()}vfd"
        output.extend([
            Case(f"vfd_{detector.lower()}_background", "vfd", detector, "vfd", "fixed",
                 "background", None, None, base / "background"),
            Case(f"vfd_{detector.lower()}_vfd_stop", "vfd", detector, "vfd", "fixed",
                 "vfd_stop", None, None, base / "vfd"),
        ])
        for carrier in (4, 8, 12):
            for output_hz in (30, 50):
                if detector == "TC1":
                    folder_name = f"vfd{carrier}k{output_hz}hz"
                else:
                    folder_name = f"{carrier}k{output_hz}hz"
                output.append(Case(
                    f"vfd_{detector.lower()}_{carrier}k_{output_hz}hz",
                    "vfd",
                    detector,
                    "vfd",
                    "fixed",
                    "run",
                    carrier,
                    output_hz,
                    base / folder_name,
                ))
    return output


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def robust_z(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    center = np.nanmedian(values)
    scale = 1.4826 * np.nanmedian(np.abs(values - center))
    if not np.isfinite(scale) or scale < 1e-12:
        scale = np.nanstd(values)
    return (values - center) / max(float(scale), 1e-12)


def extract_tdms(path: Path) -> dict[str, object]:
    with TdmsFile.open(path) as tdms:
        group = tdms.groups()[0]
        channels = group.channels()
        channel_names = [channel.name for channel in channels]
        sample_count = len(channels[0])
        sample_rate = 1.0 / float(channels[0].properties["wf_increment"])
        start_time = channels[0].properties.get("wf_start_time")
        block_size = int(round(BLOCK_SECONDS * sample_rate))
        sub_size = int(round(sample_rate / 1000.0))
        sub_per_block = block_size // sub_size

        feature_names = (
            "slow_mean",
            "broadband_rms",
            "subkhz_rms",
            "fast_residual_rms",
            "difference_rms",
        )
        feature_lists = {name: [[] for _ in channels] for name in feature_names}
        leftovers = [np.empty(0, dtype=float) for _ in channels]
        previous = [None for _ in channels]
        health = [{
            "count": 0,
            "sum": 0.0,
            "sumsq": 0.0,
            "minimum": np.inf,
            "maximum": -np.inf,
            "diff_sumsq": 0.0,
            "diff_count": 0,
            "flat_diff_count": 0,
            "clip_count": 0,
            "nonfinite_count": 0,
        } for _ in channels]

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
                data = np.asarray(chunk_channel[:], dtype=float)
                finite = np.isfinite(data)
                values = data[finite]
                item = health[channel_index]
                item["nonfinite_count"] += int(np.sum(~finite))
                item["count"] += len(values)
                item["sum"] += float(np.sum(values))
                item["sumsq"] += float(np.sum(values * values))
                if len(values):
                    item["minimum"] = min(item["minimum"], float(np.min(values)))
                    item["maximum"] = max(item["maximum"], float(np.max(values)))
                    item["clip_count"] += int(np.sum(np.abs(values) >= 9.9))

                if previous[channel_index] is None:
                    differences = np.diff(data)
                else:
                    differences = np.diff(np.r_[previous[channel_index], data])
                differences = differences[np.isfinite(differences)]
                item["diff_sumsq"] += float(np.sum(differences * differences))
                item["diff_count"] += len(differences)
                item["flat_diff_count"] += int(np.sum(np.abs(differences) <= 1e-12))
                if len(data):
                    previous[channel_index] = data[-1]

                combined = np.concatenate((leftovers[channel_index], np.nan_to_num(data)))
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
            if chunk_index and chunk_index % 750 == 0:
                print(f"    streamed {100.0 * chunk_end / sample_count:5.1f}%", flush=True)

    features: dict[str, np.ndarray] = {}
    for name, per_channel in feature_lists.items():
        common = min(len(values) for values in per_channel)
        features[name] = np.column_stack([
            np.asarray(values[:common], dtype=float) for values in per_channel
        ])

    if np.isnan(spectral).any():
        raise RuntimeError(f"Missing spectrum samples in {path}")
    window = signal.windows.hann(SPECTRUM_NFFT, sym=False)
    normalization = sample_rate * np.sum(window * window)
    psd = []
    for channel_segments in spectral:
        segment_psd = []
        for segment_values in channel_segments:
            values = signal.detrend(segment_values.astype(float))
            fft = np.fft.rfft(values * window)
            current = np.abs(fft) ** 2 / normalization
            current[1:-1] *= 2.0
            segment_psd.append(current)
        psd.append(np.median(segment_psd, axis=0))

    health_rows = []
    for channel_index, item in enumerate(health):
        count = max(int(item["count"]), 1)
        mean = item["sum"] / count
        variance = max(item["sumsq"] / count - mean * mean, 0.0)
        health_rows.append({
            "channel_index": channel_index + 1,
            "channel_name": channel_names[channel_index],
            "mean": mean,
            "std": np.sqrt(variance),
            "minimum": item["minimum"],
            "maximum": item["maximum"],
            "range": item["maximum"] - item["minimum"],
            "difference_rms": np.sqrt(item["diff_sumsq"] / max(item["diff_count"], 1)),
            "flat_difference_fraction": item["flat_diff_count"] / max(item["diff_count"], 1),
            "clip_fraction": item["clip_count"] / count,
            "nonfinite_fraction": item["nonfinite_count"] / max(sample_count, 1),
        })
    frequency = np.fft.rfftfreq(SPECTRUM_NFFT, 1.0 / sample_rate)
    return {
        "sample_rate": sample_rate,
        "duration_s": sample_count / sample_rate,
        "start_time": str(start_time),
        "channel_names": channel_names,
        "features": features,
        "frequency": frequency,
        "psd": np.asarray(psd),
        "health": health_rows,
    }


def save_cache(path: Path, result: dict[str, object]) -> None:
    payload = {
        "sample_rate": result["sample_rate"],
        "duration_s": result["duration_s"],
        "start_time": result["start_time"],
        "channel_names": np.asarray(result["channel_names"]),
        "frequency_hz": result["frequency"],
        "psd": result["psd"],
        "health_json": json.dumps(result["health"]),
    }
    payload.update(result["features"])
    np.savez_compressed(path, **payload)


def load_cache(path: Path) -> dict[str, object]:
    with np.load(path) as data:
        return {
            "sample_rate": float(data["sample_rate"]),
            "duration_s": float(data["duration_s"]),
            "start_time": str(data["start_time"]),
            "channel_names": data["channel_names"].tolist(),
            "frequency": data["frequency_hz"],
            "psd": data["psd"],
            "health": json.loads(str(data["health_json"])),
            "features": {
                name: data[name]
                for name in ("slow_mean", "broadband_rms", "subkhz_rms",
                             "fast_residual_rms", "difference_rms")
            },
        }


def bandpowers(frequency: np.ndarray, psd: np.ndarray) -> dict[str, float]:
    bands = {
        "5_100hz": (5.0, 100.0),
        "100_1khz": (100.0, 1_000.0),
        "1_20khz": (1_000.0, 20_000.0),
        "20_80khz": (20_000.0, 80_000.0),
        "80_200khz": (80_000.0, 199_900.0),
    }
    output = {}
    for name, (low, high) in bands.items():
        use = (frequency >= low) & (frequency < high)
        output[name] = float(np.trapz(psd[use], frequency[use]))
    return output


BAND_NAMES = ("5_100hz", "100_1khz", "1_20khz", "20_80khz", "80_200khz")


def case_band_matrix(result: dict[str, object]) -> np.ndarray:
    return np.asarray([
        [bandpowers(result["frequency"], channel_psd)[name] for name in BAND_NAMES]
        for channel_psd in result["psd"]
    ])


def stable_feature(result: dict[str, object], name: str) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(result["features"][name], dtype=float)
    if name != "slow_mean":
        positive = values[values > 0]
        floor = float(np.percentile(positive, 0.1)) if len(positive) else 1e-15
        values = np.log10(np.maximum(values, floor))
    fs = 1.0 / BLOCK_SECONDS
    start = int(round(TRIM_START_SECONDS * fs))
    end = len(values) - int(round(TRIM_END_SECONDS * fs))
    time_s = (np.arange(start, end) + 0.5) / fs
    return time_s, values[start:end]


def band_limited(values: np.ndarray, fs: float = 10.0) -> np.ndarray:
    values = np.nan_to_num(robust_z(values))
    sos = signal.butter(3, [0.05, 0.70], btype="bandpass", fs=fs, output="sos")
    return signal.sosfiltfilt(sos, values)


def duo_crossover_rows(
    all_cases: list[Case],
    results: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    duo_cases = [case for case in all_cases if case.experiment == "duo"]
    matrices = {case.case_id: case_band_matrix(results[case.case_id]) for case in duo_cases}
    rows: list[dict[str, object]] = []
    for condition in ("background", "vfd_stop", "30hz", "50hz"):
        for band_index, band in enumerate(BAND_NAMES):
            detector_values: dict[tuple[str, str], float] = {}
            contrasts: dict[tuple[str, str], float] = {}
            for arrangement in ("duo1", "duo2"):
                for detector in ("TC1", "TC2"):
                    case = next(item for item in duo_cases if item.arrangement == arrangement
                                and item.detector == detector and item.condition == condition)
                    result = results[case.case_id]
                    valid = valid_channel_indices(result)
                    db = 10.0 * np.log10(matrices[case.case_id][valid, band_index] + 1e-30)
                    detector_values[(arrangement, detector)] = float(np.median(db))
                    background = next(item for item in duo_cases if item.arrangement == arrangement
                                      and item.detector == detector and item.condition == "background")
                    paired_valid = common_valid_channel_indices(
                        result, results[background.case_id]
                    )
                    paired = 10.0 * np.log10(
                        (matrices[case.case_id][paired_valid, band_index] + 1e-30)
                        / (matrices[background.case_id][paired_valid, band_index] + 1e-30)
                    )
                    contrasts[(arrangement, detector)] = float(np.median(paired))

            absolute_d1 = detector_values[("duo1", "TC1")] - detector_values[("duo1", "TC2")]
            absolute_d2 = detector_values[("duo2", "TC1")] - detector_values[("duo2", "TC2")]
            contrast_d1 = contrasts[("duo1", "TC1")] - contrasts[("duo1", "TC2")]
            contrast_d2 = contrasts[("duo2", "TC1")] - contrasts[("duo2", "TC2")]
            rows.append({
                "condition": condition,
                "band": band,
                "tc1_minus_tc2_duo1_db": absolute_d1,
                "tc1_minus_tc2_duo2_db": absolute_d2,
                "estimated_detector_bias_db": 0.5 * (absolute_d1 + absolute_d2),
                "estimated_position_effect_db": 0.5 * (absolute_d1 - absolute_d2),
                "contrast_tc1_duo1_db": contrasts[("duo1", "TC1")],
                "contrast_tc2_duo1_db": contrasts[("duo1", "TC2")],
                "contrast_tc1_duo2_db": contrasts[("duo2", "TC1")],
                "contrast_tc2_duo2_db": contrasts[("duo2", "TC2")],
                "contrast_detector_difference_duo1_db": contrast_d1,
                "contrast_detector_difference_duo2_db": contrast_d2,
                "contrast_detector_bias_db": 0.5 * (contrast_d1 + contrast_d2),
                "contrast_position_effect_db": 0.5 * (contrast_d1 - contrast_d2),
            })
    return rows


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def correlation_at_small_lag(x: np.ndarray, y: np.ndarray, fs: float = 10.0) -> tuple[float, float, float]:
    x = band_limited(x, fs)
    y = band_limited(y, fs)
    zero = float(np.corrcoef(x, y)[0, 1])
    shifts = list(range(-int(fs), int(fs) + 1))
    correlations = []
    for shift in shifts:
        if shift < 0:
            correlations.append(float(np.corrcoef(x[-shift:], y[:shift])[0, 1]))
        elif shift > 0:
            correlations.append(float(np.corrcoef(x[:-shift], y[shift:])[0, 1]))
        else:
            correlations.append(zero)
    best = int(np.nanargmax(np.abs(correlations)))
    return zero, correlations[best], shifts[best] / fs


def duo_synchronous_rows(
    all_cases: list[Case],
    results: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for arrangement in ("duo1", "duo2"):
        for condition in ("background", "vfd_stop", "30hz", "50hz"):
            case1 = next(case for case in all_cases if case.experiment == "duo"
                         and case.arrangement == arrangement and case.detector == "TC1"
                         and case.condition == condition)
            case2 = next(case for case in all_cases if case.experiment == "duo"
                         and case.arrangement == arrangement and case.detector == "TC2"
                         and case.condition == condition)
            result1, result2 = results[case1.case_id], results[case2.case_id]
            common_channels = common_valid_channel_indices(result1, result2)
            start1, start2 = parse_time(result1["start_time"]), parse_time(result2["start_time"])
            offset_s = (start2 - start1).total_seconds()
            for feature in ("slow_mean", "subkhz_rms", "broadband_rms", "fast_residual_rms"):
                time1, values1 = stable_feature(result1, feature)
                time2, values2 = stable_feature(result2, feature)
                # TC2 relative time expressed on the TC1 acquisition clock.
                time2_on_1 = time2 + offset_s
                common_start = max(time1[0], time2_on_1[0])
                common_end = min(time1[-1], time2_on_1[-1])
                common_time = np.arange(common_start, common_end, BLOCK_SECONDS)
                zero_values, best_values, lag_values = [], [], []
                for channel in common_channels:
                    x = np.interp(common_time, time1, values1[:, channel])
                    y = np.interp(common_time, time2_on_1, values2[:, channel])
                    zero, best, lag = correlation_at_small_lag(x, y)
                    zero_values.append(zero)
                    best_values.append(best)
                    lag_values.append(lag)
                rows.append({
                    "arrangement": arrangement,
                    "condition": condition,
                    "feature": feature,
                    "tc2_start_after_tc1_s": offset_s,
                    "overlap_duration_s": len(common_time) * BLOCK_SECONDS,
                    "valid_paired_channels": len(common_channels),
                    "median_abs_zero_lag_correlation": float(np.median(np.abs(zero_values))),
                    "median_abs_best_pm1s_correlation": float(np.median(np.abs(best_values))),
                    "support_fraction_abs_zero_gt0_3": float(np.mean(np.abs(zero_values) > 0.3)),
                    "support_fraction_abs_best_gt0_3": float(np.mean(np.abs(best_values) > 0.3)),
                    "median_best_lag_s": float(np.median(lag_values)),
                })
    return rows


def local_tone_metrics(
    frequency: np.ndarray,
    psd: np.ndarray,
    target_hz: float,
    target_half_width: float = 120.0,
) -> dict[str, float]:
    target = np.abs(frequency - target_hz) <= target_half_width
    baseline = (
        (np.abs(frequency - target_hz) >= 350.0)
        & (np.abs(frequency - target_hz) <= 1_000.0)
    )
    search = np.abs(frequency - target_hz) <= max(600.0, 0.08 * target_hz)
    target_power = float(np.mean(psd[target]))
    target_indices = np.flatnonzero(target)
    target_peak_index = target_indices[np.argmax(psd[target])]
    target_peak_power = float(psd[target_peak_index])
    baseline_power = float(np.median(psd[baseline]))
    search_indices = np.flatnonzero(search)
    peak_index = search_indices[np.argmax(psd[search])]
    return {
        "tone_power_db": 10.0 * np.log10(target_power + 1e-30),
        "tone_excess_db": 10.0 * np.log10((target_power + 1e-30) / (baseline_power + 1e-30)),
        "target_peak_excess_db": 10.0 * np.log10(
            (target_peak_power + 1e-30) / (baseline_power + 1e-30)
        ),
        "target_peak_frequency_hz": float(frequency[target_peak_index]),
        "target_peak_offset_hz": float(frequency[target_peak_index] - target_hz),
        "local_peak_frequency_hz": float(frequency[peak_index]),
        "local_peak_offset_hz": float(frequency[peak_index] - target_hz),
    }


def top_power_fraction(psd: np.ndarray, fraction: float = 0.01) -> float:
    count = max(1, int(np.ceil(len(psd) * fraction)))
    top = np.partition(psd, len(psd) - count)[-count:]
    return float(np.sum(top) / max(float(np.sum(psd)), 1e-30))


def dominant_vfd_lines(
    frequency: np.ndarray,
    active_psd: np.ndarray,
    stop_psd: np.ndarray,
    valid: list[int],
    limit: int = 30,
) -> list[dict[str, float]]:
    active_aggregate = np.median(active_psd[valid], axis=0)
    stop_aggregate = np.median(stop_psd[valid], axis=0)
    active_db = 10.0 * np.log10(active_aggregate + 1e-30)
    baseline = signal.savgol_filter(active_db, 2001, 2)
    local_excess = active_db - baseline
    contrast = 10.0 * np.log10(
        (active_aggregate + 1e-30) / (stop_aggregate + 1e-30)
    )
    use = (frequency >= 1_000.0) & (frequency <= 195_000.0)
    candidates, properties = signal.find_peaks(
        local_excess,
        height=5.0,
        prominence=2.0,
        distance=8,
    )
    candidates = candidates[use[candidates] & (contrast[candidates] >= 3.0)]
    if not len(candidates):
        return []
    score = local_excess[candidates] + np.maximum(contrast[candidates], 0.0)
    candidates = candidates[np.argsort(score)[::-1][:limit]]
    rows: list[dict[str, float]] = []
    for rank, peak_index in enumerate(candidates, start=1):
        start = max(0, peak_index - 2)
        end = min(len(frequency), peak_index + 3)
        channel_contrasts = []
        for channel in valid:
            active_peak = float(np.max(active_psd[channel, start:end]))
            stop_local = float(np.median(stop_psd[channel, start:end]))
            channel_contrasts.append(
                10.0 * np.log10((active_peak + 1e-30) / (stop_local + 1e-30))
            )
        channel_contrasts = np.asarray(channel_contrasts)
        rows.append({
            "rank": rank,
            "frequency_hz": float(frequency[peak_index]),
            "local_line_excess_db": float(local_excess[peak_index]),
            "contrast_vfd_stop_db": float(contrast[peak_index]),
            "median_channel_contrast_db": float(np.median(channel_contrasts)),
            "channel_support_fraction_gt6db": float(np.mean(channel_contrasts > 6.0)),
        })
    return rows


def cluster_frequencies(values: list[float], tolerance_hz: float = 250.0) -> list[float]:
    groups: list[list[float]] = []
    for value in sorted(values):
        if not groups or value - float(np.mean(groups[-1])) > tolerance_hz:
            groups.append([value])
        else:
            groups[-1].append(value)
    return [float(np.mean(group)) for group in groups]


def dominant_line_overlap_rows(
    line_rows: list[dict[str, object]],
    match_tolerance_hz: float = 300.0,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for detector in ("TC1", "TC2"):
        for output_hz in (30, 50):
            clusters = {}
            for carrier in (4, 8, 12):
                frequencies = [
                    float(row["frequency_hz"])
                    for row in line_rows
                    if row["detector"] == detector
                    and row["output_hz"] == output_hz
                    and row["carrier_khz"] == carrier
                ]
                clusters[carrier] = cluster_frequencies(frequencies)
            for carrier_a, carrier_b in ((4, 8), (4, 12), (8, 12)):
                remaining = clusters[carrier_b].copy()
                matched = 0
                offsets = []
                for frequency_a in clusters[carrier_a]:
                    if not remaining:
                        break
                    index = int(np.argmin(np.abs(np.asarray(remaining) - frequency_a)))
                    offset = remaining[index] - frequency_a
                    if abs(offset) <= match_tolerance_hz:
                        matched += 1
                        offsets.append(offset)
                        remaining.pop(index)
                count_a = len(clusters[carrier_a])
                count_b = len(clusters[carrier_b])
                rows.append({
                    "detector": detector,
                    "output_hz": output_hz,
                    "carrier_a_khz": carrier_a,
                    "carrier_b_khz": carrier_b,
                    "cluster_count_a": count_a,
                    "cluster_count_b": count_b,
                    "matched_cluster_count": matched,
                    "matched_fraction_of_smaller_set": matched / max(min(count_a, count_b), 1),
                    "matched_jaccard_fraction": matched / max(count_a + count_b - matched, 1),
                    "median_abs_match_offset_hz": (
                        float(np.median(np.abs(offsets))) if offsets else np.nan
                    ),
                })
    return rows


def vfd_analysis_rows(
    all_cases: list[Case],
    results: dict[str, dict[str, object]],
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    vfd_cases = [case for case in all_cases if case.experiment == "vfd"]
    band_rows: list[dict[str, object]] = []
    tone_rows: list[dict[str, object]] = []
    comb_rows: list[dict[str, object]] = []
    concentration_rows: list[dict[str, object]] = []
    line_rows: list[dict[str, object]] = []
    for detector in ("TC1", "TC2"):
        background = next(case for case in vfd_cases if case.detector == detector
                          and case.condition == "background")
        stopped = next(case for case in vfd_cases if case.detector == detector
                       and case.condition == "vfd_stop")
        bg_matrix = case_band_matrix(results[background.case_id])
        stop_matrix = case_band_matrix(results[stopped.case_id])
        for case in [item for item in vfd_cases if item.detector == detector and item.condition == "run"]:
            result = results[case.case_id]
            valid = common_valid_channel_indices(
                result,
                results[background.case_id],
                results[stopped.case_id],
            )
            try:
                strict_valid = common_valid_channel_indices(
                    result,
                    results[background.case_id],
                    results[stopped.case_id],
                    exclude_suspect=True,
                )
            except ValueError:
                strict_valid = []
            matrix = case_band_matrix(result)
            for band_index, band in enumerate(BAND_NAMES):
                vs_bg = 10.0 * np.log10(
                    (matrix[valid, band_index] + 1e-30) / (bg_matrix[valid, band_index] + 1e-30)
                )
                vs_stop = 10.0 * np.log10(
                    (matrix[valid, band_index] + 1e-30) / (stop_matrix[valid, band_index] + 1e-30)
                )
                strict_vs_bg = 10.0 * np.log10(
                    (matrix[strict_valid, band_index] + 1e-30)
                    / (bg_matrix[strict_valid, band_index] + 1e-30)
                ) if strict_valid else np.array([])
                strict_vs_stop = 10.0 * np.log10(
                    (matrix[strict_valid, band_index] + 1e-30)
                    / (stop_matrix[strict_valid, band_index] + 1e-30)
                ) if strict_valid else np.array([])
                band_rows.append({
                    "case_id": case.case_id,
                    "detector": detector,
                    "carrier_khz": case.carrier_khz,
                    "output_hz": case.output_hz,
                    "band": band,
                    "median_contrast_background_db": float(np.median(vs_bg)),
                    "q25_contrast_background_db": float(np.percentile(vs_bg, 25)),
                    "q75_contrast_background_db": float(np.percentile(vs_bg, 75)),
                    "median_contrast_vfd_stop_db": float(np.median(vs_stop)),
                    "positive_vs_stop_channel_fraction": float(np.mean(vs_stop > 0.0)),
                    "common_healthy_channel_count": len(valid),
                    "strict_non_suspect_channel_count": len(strict_valid),
                    "strict_median_contrast_background_db": (
                        float(np.median(strict_vs_bg)) if len(strict_vs_bg) else np.nan
                    ),
                    "strict_median_contrast_vfd_stop_db": (
                        float(np.median(strict_vs_stop)) if len(strict_vs_stop) else np.nan
                    ),
                })

                band_limits = {
                    "5_100hz": (5.0, 100.0),
                    "100_1khz": (100.0, 1_000.0),
                    "1_20khz": (1_000.0, 20_000.0),
                    "20_80khz": (20_000.0, 80_000.0),
                    "80_200khz": (80_000.0, 199_900.0),
                }
                low, high = band_limits[band]
                frequency = np.asarray(result["frequency"])
                use = (frequency >= low) & (frequency < high)
                active_concentration = np.array([
                    top_power_fraction(result["psd"][channel, use]) for channel in valid
                ])
                stop_concentration = np.array([
                    top_power_fraction(results[stopped.case_id]["psd"][channel, use])
                    for channel in valid
                ])
                concentration_rows.append({
                    "case_id": case.case_id,
                    "detector": detector,
                    "carrier_khz": case.carrier_khz,
                    "output_hz": case.output_hz,
                    "band": band,
                    "top_1pct_power_fraction_active_median": float(
                        np.median(active_concentration)
                    ),
                    "top_1pct_power_fraction_stop_median": float(
                        np.median(stop_concentration)
                    ),
                    "active_minus_stop_fraction_median": float(
                        np.median(active_concentration - stop_concentration)
                    ),
                    "channel_fraction_more_concentrated_than_stop": float(
                        np.mean(active_concentration > stop_concentration)
                    ),
                })

            aggregate = np.median(result["psd"][valid], axis=0)
            frequency = result["frequency"]
            for candidate_khz in (4, 8, 12):
                metrics = local_tone_metrics(frequency, aggregate, candidate_khz * 1000.0)
                channel_metrics = [
                    local_tone_metrics(
                        frequency, result["psd"][channel], candidate_khz * 1000.0
                    )
                    for channel in valid
                ]
                channel_excess = np.array([
                    item["tone_excess_db"] for item in channel_metrics
                ])
                channel_peak_excess = np.array([
                    item["target_peak_excess_db"] for item in channel_metrics
                ])
                channel_peak_offset = np.array([
                    item["target_peak_offset_hz"] for item in channel_metrics
                ])
                tone_rows.append({
                    "case_id": case.case_id,
                    "detector": detector,
                    "carrier_khz": case.carrier_khz,
                    "output_hz": case.output_hz,
                    "candidate_khz": candidate_khz,
                    "candidate_is_setting": candidate_khz == case.carrier_khz,
                    "channel_median_tone_excess_db": float(np.median(channel_excess)),
                    "channel_max_tone_excess_db": float(np.max(channel_excess)),
                    "channel_support_fraction_tone_excess_gt3db": float(
                        np.mean(channel_excess > 3.0)
                    ),
                    "channel_median_target_peak_excess_db": float(
                        np.median(channel_peak_excess)
                    ),
                    "channel_support_fraction_target_peak_gt10db": float(
                        np.mean(channel_peak_excess > 10.0)
                    ),
                    "channel_median_abs_target_peak_offset_hz": float(
                        np.median(np.abs(channel_peak_offset))
                    ),
                    **metrics,
                })
            for candidate_khz in (4, 8, 12):
                harmonics = []
                for order in range(1, 17):
                    target = candidate_khz * 1000.0 * order
                    if target >= 195_000.0:
                        break
                    harmonics.append(local_tone_metrics(frequency, aggregate, target)["tone_excess_db"])
                comb_rows.append({
                    "case_id": case.case_id,
                    "detector": detector,
                    "carrier_khz": case.carrier_khz,
                    "output_hz": case.output_hz,
                    "candidate_khz": candidate_khz,
                    "candidate_is_setting": candidate_khz == case.carrier_khz,
                    "harmonic_count": len(harmonics),
                    "comb_median_excess_db": float(np.median(harmonics)),
                    "comb_mean_positive_excess_db": float(np.mean(np.maximum(harmonics, 0.0))),
                    "comb_positive_fraction": float(np.mean(np.asarray(harmonics) > 3.0)),
                })
            for line in dominant_vfd_lines(
                frequency,
                np.asarray(result["psd"]),
                np.asarray(results[stopped.case_id]["psd"]),
                valid,
            ):
                line_frequency = float(line["frequency_hz"])
                line_index = int(np.argmin(np.abs(np.asarray(frequency) - line_frequency)))
                if "welch_epoch_psd_mean" in result:
                    epoch_psd = np.asarray(result["welch_epoch_psd_mean"])[
                        :, valid, line_index
                    ]
                    temporal_sd = np.std(
                        10.0 * np.log10(np.maximum(epoch_psd, 1e-300)), axis=0
                    )
                    line["median_channel_welch_temporal_sd_db"] = float(
                        np.median(temporal_sd)
                    )
                    line["q75_channel_welch_temporal_sd_db"] = float(
                        np.percentile(temporal_sd, 75)
                    )
                line_rows.append({
                    "case_id": case.case_id,
                    "detector": detector,
                    "carrier_khz": case.carrier_khz,
                    "output_hz": case.output_hz,
                    **line,
                })
    return band_rows, tone_rows, comb_rows, concentration_rows, line_rows


def first_component(values: np.ndarray) -> tuple[np.ndarray, float]:
    matrix = np.column_stack([np.clip(robust_z(values[:, index]), -8.0, 8.0)
                              for index in range(values.shape[1])])
    u, singular, _ = np.linalg.svd(np.nan_to_num(matrix), full_matrices=False)
    component = u[:, 0] * singular[0]
    explained = singular[0] ** 2 / max(float(np.sum(singular * singular)), 1e-30)
    return component, float(explained)


def reference_response(values: np.ndarray, period_s: float, fs: float = 10.0) -> dict[str, float]:
    filtered = band_limited(values, fs)
    frequency, psd = signal.periodogram(filtered, fs=fs, window="hann", detrend="linear")
    target = 1.0 / period_s
    resolution = frequency[1] - frequency[0]
    target_mask = np.abs(frequency - target) <= max(1.5 * resolution, 0.012)
    baseline = ((frequency >= 0.05) & (frequency <= 0.70)
                & (np.abs(frequency - target) >= max(3.0 * resolution, 0.04)))
    return {
        "reference_frequency_hz": target,
        "spectral_snr": float(np.max(psd[target_mask]) / max(float(np.median(psd[baseline])), 1e-30)),
    }


def water_reference_rows(
    all_cases: list[Case],
    results: dict[str, dict[str, object]],
    period_s: float = 3.10,
) -> list[dict[str, object]]:
    exact_mode = all("archive_metadata" in result for result in results.values())
    features = ("slow_mean", "subkhz_rms", "broadband_rms", "fast_residual_rms")
    channel_snr_by_case_feature: dict[tuple[str, str], np.ndarray] = {}
    pca_by_case_feature: dict[tuple[str, str], tuple[float, float]] = {}
    for case in all_cases:
        result = results[case.case_id]
        valid = valid_channel_indices(result)
        for feature in features:
            _, values = stable_feature(result, feature)
            selected = values[:, valid]
            component, explained = first_component(selected)
            pca_response = reference_response(component, period_s)
            channel_snr_by_case_feature[(case.case_id, feature)] = np.array([
                reference_response(values[:, index], period_s)["spectral_snr"]
                for index in range(values.shape[1])
            ])
            pca_by_case_feature[(case.case_id, feature)] = (
                explained, pca_response["spectral_snr"]
            )

    rows: list[dict[str, object]] = []
    for case in all_cases:
        controls = [
            item for item in all_cases
            if item.experiment == case.experiment
            and item.arrangement == case.arrangement
            and item.detector == case.detector
            and item.condition in ("background", "vfd_stop")
        ]
        for feature in features:
            valid = common_valid_channel_indices(
                results[case.case_id],
                *(results[control.case_id] for control in controls),
            )
            channel_snr = channel_snr_by_case_feature[(case.case_id, feature)][valid]
            control_matrix = np.vstack([
                channel_snr_by_case_feature[(control.case_id, feature)][valid]
                for control in controls
            ])
            matched_control_max = np.max(control_matrix, axis=0)
            control_file_medians = np.median(control_matrix, axis=1)
            control_snr = control_matrix.ravel()
            if exact_mode:
                empirical_null_95 = np.nan
                pooled_support = np.nan
            else:
                empirical_null_95 = float(np.percentile(control_snr, 95))
                pooled_support = float(np.mean(channel_snr > empirical_null_95))
            explained, pca_reference_snr = pca_by_case_feature[(case.case_id, feature)]
            rows.append({
                "case_id": case.case_id,
                "experiment": case.experiment,
                "detector": case.detector,
                "arrangement": case.arrangement,
                "condition": case.condition,
                "carrier_khz": case.carrier_khz,
                "output_hz": case.output_hz,
                "feature": feature,
                "common_healthy_channel_count": len(valid),
                "common_healthy_channels_1based": ";".join(
                    str(index + 1) for index in valid
                ),
                "target_period_s": period_s,
                "pca_explained_fraction": explained,
                "pca_reference_snr": pca_reference_snr,
                "median_channel_reference_snr": float(np.median(channel_snr)),
                "max_channel_reference_snr": float(np.max(channel_snr)),
                "support_fraction_snr_gt5": float(np.mean(channel_snr > 5.0)),
                "support_fraction_snr_gt10": float(np.mean(channel_snr > 10.0)),
                "empirical_null_median_snr": float(np.median(control_snr)),
                "empirical_null_95_snr": empirical_null_95,
                "support_fraction_above_empirical_null95": pooled_support,
                "median_snr_ratio_to_empirical_null_median": float(
                    np.median(channel_snr) / max(float(np.median(control_snr)), 1e-30)
                ),
                "matched_control_definition": "per-channel max(background, vfd_stop)",
                "support_fraction_above_matched_control_max": float(
                    np.mean(channel_snr > matched_control_max)
                ),
                "median_channel_snr_ratio_to_matched_control_max": float(
                    np.median(channel_snr / np.maximum(matched_control_max, 1e-30))
                ),
                "file_median_reference_snr": float(np.median(channel_snr)),
                "control_file_median_snr_max": float(np.max(control_file_medians)),
                "file_median_exceeds_all_control_files": bool(
                    np.median(channel_snr) > np.max(control_file_medians)
                ),
                "channel_pooled_null_is_exploratory": True,
                "channel_pooled_null_used_for_decision": not exact_mode,
            })
    return rows


def health_and_band_rows(
    all_cases: list[Case],
    results: dict[str, dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    health_rows: list[dict[str, object]] = []
    band_rows: list[dict[str, object]] = []
    for case in all_cases:
        result = results[case.case_id]
        quality = assess_channel_quality(result)
        for channel_index, health in enumerate(result["health"]):
            row = asdict(case) | health | quality[channel_index]
            row["folder"] = str(case.folder)
            health_rows.append(row)
            band_rows.append({
                **{key: value for key, value in asdict(case).items() if key != "folder"},
                "channel_index": channel_index + 1,
                "channel_name": result["channel_names"][channel_index],
                "automatic_bad": quality[channel_index]["automatic_bad"],
                "automatic_suspect": quality[channel_index]["automatic_suspect"],
                **bandpowers(result["frequency"], result["psd"][channel_index]),
            })
    return health_rows, band_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument(
        "--output", type=Path,
        default=Path('experiments/20260806'),
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
    cache_dir = args.output / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    exact_dir = args.output / "exact_archive"
    if args.exact:
        exact_dir.mkdir(parents=True, exist_ok=True)

    all_cases = cases(args.root)
    results: dict[str, dict[str, object]] = {}
    for index, case in enumerate(all_cases, start=1):
        cache_path = cache_dir / f"{case.case_id}.npz"
        archive_path = exact_dir / case.case_id
        if args.exact and archive_complete(archive_path):
            print(f"[{index:02d}/{len(all_cases)}] exact archive {case.case_id}", flush=True)
            result = load_exact_archive(archive_path)
        elif args.exact:
            files = list(case.folder.glob("*.tdms"))
            if len(files) != 1:
                raise RuntimeError(f"Expected one TDMS in {case.folder}, found {len(files)}")
            print(f"[{index:02d}/{len(all_cases)}] exact extract {case.case_id}", flush=True)
            build_exact_archive(files[0], archive_path, ExactArchiveConfig())
            result = load_exact_archive(archive_path)
        elif cache_path.exists():
            print(f"[{index:02d}/{len(all_cases)}] cache {case.case_id}", flush=True)
            result = load_cache(cache_path)
        else:
            files = list(case.folder.glob("*.tdms"))
            if len(files) != 1:
                raise RuntimeError(f"Expected one TDMS in {case.folder}, found {len(files)}")
            print(f"[{index:02d}/{len(all_cases)}] extract {case.case_id}", flush=True)
            result = extract_tdms(files[0])
            save_cache(cache_path, result)
        results[case.case_id] = result

    if args.archive_only:
        print(f"Exact archives complete: {exact_dir.resolve()}", flush=True)
        return

    health_rows, band_rows = health_and_band_rows(all_cases, results)
    write_csv(args.output / "channel_health.csv", health_rows)
    write_csv(args.output / "channel_bandpower.csv", band_rows)
    duo_rows = duo_crossover_rows(all_cases, results)
    write_csv(args.output / "duo_crossover_summary.csv", duo_rows)
    sync_rows = duo_synchronous_rows(all_cases, results)
    write_csv(args.output / "duo_synchronous_correlations.csv", sync_rows)
    (
        vfd_band_rows,
        vfd_tone_rows,
        vfd_comb_rows,
        vfd_concentration_rows,
        vfd_line_rows,
    ) = vfd_analysis_rows(all_cases, results)
    write_csv(args.output / "vfd_band_contrasts.csv", vfd_band_rows)
    write_csv(args.output / "vfd_candidate_tones.csv", vfd_tone_rows)
    write_csv(args.output / "vfd_harmonic_comb_scores.csv", vfd_comb_rows)
    write_csv(args.output / "vfd_line_concentration.csv", vfd_concentration_rows)
    write_csv(args.output / "vfd_dominant_lines.csv", vfd_line_rows)
    write_csv(
        args.output / "vfd_dominant_line_overlap.csv",
        dominant_line_overlap_rows(vfd_line_rows),
    )
    water_rows = water_reference_rows(all_cases, results)
    write_csv(args.output / "water_3p1s_reference_test.csv", water_rows)
    if args.exact:
        write_csv(
            args.output / "exact_temporal_band_stability.csv",
            temporal_band_rows(all_cases, results, valid_channel_indices),
        )
        write_csv(
            args.output / "exact_low_frequency_blind_peaks.csv",
            low_frequency_blind_rows(all_cases, results, valid_channel_indices),
        )

    fig, axes = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
    health_plot_bands = ("5_100hz", "1_20khz")
    for row_index, detector in enumerate(("TC1", "TC2")):
        for column_index, band in enumerate(health_plot_bands):
            axis = axes[row_index, column_index]
            medians = []
            for channel in range(1, 13):
                powers = [
                    float(row[band]) for row in band_rows
                    if row["detector"] == detector and row["channel_index"] == channel
                    and not bool(row["automatic_bad"])
                ]
                medians.append(
                    10.0 * np.log10(np.median(powers) + 1e-30) if powers else np.nan
                )
            colors = [
                "#c0392b" if any(
                    bool(row["automatic_bad"])
                    for row in band_rows
                    if row["detector"] == detector and row["channel_index"] == channel
                ) else "#2878b5"
                for channel in range(1, 13)
            ]
            axis.bar(np.arange(1, 13), medians, color=colors)
            axis.set_title(f"{detector}: {band}")
            axis.set_xlabel("Channel")
            axis.set_ylabel("Median band power (dB)")
            axis.set_xticks(range(1, 13))
            axis.grid(axis="y", alpha=0.2)
    fig.savefig(args.output / "channel_health_bandpower_overview.png", dpi=180)
    plt.close(fig)

    run30_water = [row for row in water_rows if row["output_hz"] == 30]
    feature_order = ("slow_mean", "subkhz_rms", "broadband_rms", "fast_residual_rms")
    case_order = sorted({str(row["case_id"]) for row in run30_water})
    support_field = (
        "support_fraction_above_matched_control_max"
        if args.exact else "support_fraction_above_empirical_null95"
    )
    support_matrix = np.array([
        [
            next(
                float(row[support_field])
                for row in run30_water
                if row["case_id"] == case_id and row["feature"] == feature
            )
            for feature in feature_order
        ]
        for case_id in case_order
    ])
    fig, axis = plt.subplots(figsize=(10, 7), constrained_layout=True)
    image = axis.imshow(support_matrix, aspect="auto", cmap="viridis", vmin=0.0, vmax=0.5)
    axis.set_xticks(np.arange(len(feature_order)), feature_order, rotation=20, ha="right")
    axis.set_yticks(np.arange(len(case_order)), case_order)
    axis.set_title(
        "30 Hz runs: channel support above per-channel control maximum"
        if args.exact else
        "30 Hz runs: channel support above same-session empirical null 95th percentile"
    )
    for row_index in range(len(case_order)):
        for column_index in range(len(feature_order)):
            axis.text(column_index, row_index, f"{support_matrix[row_index, column_index]:.2f}",
                      ha="center", va="center", color="white" if support_matrix[row_index, column_index] > 0.25 else "black")
    fig.colorbar(image, ax=axis, label="Supporting channel fraction")
    fig.savefig(args.output / "water_3p1s_detection_support.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5), constrained_layout=True)
    for axis, condition in zip(axes, ("30hz", "50hz")):
        selected = [row for row in duo_rows if row["condition"] == condition]
        x = np.arange(len(BAND_NAMES))
        width = 0.2
        series = (
            ("TC1 duo1", "contrast_tc1_duo1_db"),
            ("TC2 duo1", "contrast_tc2_duo1_db"),
            ("TC1 duo2", "contrast_tc1_duo2_db"),
            ("TC2 duo2", "contrast_tc2_duo2_db"),
        )
        for index, (label, field) in enumerate(series):
            values = [
                next(float(row[field]) for row in selected if row["band"] == band)
                for band in BAND_NAMES
            ]
            axis.bar(x + (index - 1.5) * width, values, width, label=label)
        axis.axhline(0.0, color="black", lw=0.7)
        axis.set_xticks(x, BAND_NAMES, rotation=20, ha="right")
        axis.set_title(f"{condition}: contrast to arrangement background")
        axis.set_ylabel("Band-power contrast (dB)")
        axis.grid(axis="y", alpha=0.2)
        axis.legend(fontsize=8)
    fig.savefig(args.output / "duo_crossover_contrasts.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(14, 9), constrained_layout=True)
    plot_bands = ("1_20khz", "20_80khz", "80_200khz")
    for row_index, detector in enumerate(("TC1", "TC2")):
        stop_case = next(case for case in all_cases if case.experiment == "vfd"
                         and case.detector == detector and case.condition == "vfd_stop")
        stop_result = results[stop_case.case_id]
        frequency = results[stop_case.case_id]["frequency"]
        use = (frequency >= 1_000.0) & (frequency <= 50_000.0)
        for column_index, output_hz in enumerate((30, 50)):
            axis = axes[row_index, column_index]
            for carrier in (4, 8, 12):
                case = next(item for item in all_cases if item.experiment == "vfd"
                            and item.detector == detector and item.condition == "run"
                            and item.carrier_khz == carrier and item.output_hz == output_hz)
                active_result = results[case.case_id]
                valid = common_valid_channel_indices(active_result, stop_result)
                active_channel_psd = active_result["psd"][valid]
                stop_channel_psd = stop_result["psd"][valid]
                channel_contrast = 10.0 * np.log10(
                    (active_channel_psd + 1e-30) / (stop_channel_psd + 1e-30)
                )
                contrast = np.median(channel_contrast, axis=0)
                axis.plot(frequency[use] / 1000.0, contrast[use], lw=0.65, alpha=0.8,
                          label=f"{carrier} kHz")
            for marker in (4, 8, 12):
                axis.axvline(marker, color="black", alpha=0.12, lw=0.8)
            axis.axhline(0.0, color="black", lw=0.6)
            axis.set_title(f"{detector}, output {output_hz} Hz")
            axis.set_xlabel("Frequency (kHz)")
            axis.set_ylabel("PSD relative to VFD STOP (dB)")
            axis.set_ylim(-15, 30)
            axis.grid(alpha=0.2)
            axis.legend(fontsize=8)
    fig.savefig(args.output / "vfd_carrier_spectrum_contrasts.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5), constrained_layout=True)
    for axis, detector in zip(axes, ("TC1", "TC2")):
        width = 0.12
        x = np.arange(len(plot_bands))
        offset_index = 0
        for output_hz in (30, 50):
            for carrier in (4, 8, 12):
                selected = [row for row in vfd_band_rows if row["detector"] == detector
                            and row["output_hz"] == output_hz and row["carrier_khz"] == carrier
                            and row["band"] in plot_bands]
                selected.sort(key=lambda item: plot_bands.index(item["band"]))
                values = [item["median_contrast_vfd_stop_db"] for item in selected]
                axis.bar(x + (offset_index - 2.5) * width, values, width,
                         label=f"{carrier}k/{output_hz}Hz")
                offset_index += 1
        axis.axhline(0.0, color="black", lw=0.7)
        axis.set_xticks(x, plot_bands)
        axis.set_title(detector)
        axis.set_ylabel("Contrast to VFD STOP (dB)")
        axis.grid(axis="y", alpha=0.2)
        axis.legend(fontsize=7, ncol=2)
    fig.savefig(args.output / "vfd_band_contrasts.png", dpi=180)
    plt.close(fig)
    manifest = {
        "root": str(args.root),
        "block_seconds": BLOCK_SECONDS,
        "spectrum_nfft": SPECTRUM_NFFT,
        "channel_exclusion": (
            "dynamic per acquisition; comparisons use the healthy-channel intersection"
        ),
        "duo_position_convention": {
            "duo1": {"TC1": "A", "TC2": "B"},
            "duo2": {"TC1": "B", "TC2": "A"},
        },
        "cases": [asdict(case) | {"folder": str(case.folder)} for case in all_cases],
    }
    (args.output / "analysis_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    flagged = [row for row in health_rows if row["automatic_bad"]]
    print(f"Wrote {args.output.resolve()}, automatic bad rows={len(flagged)}", flush=True)


if __name__ == "__main__":
    main()
