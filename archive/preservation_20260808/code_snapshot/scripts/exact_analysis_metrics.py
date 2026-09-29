"""Experiment-level metrics derived from full-coverage exact archives."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Callable, Iterable

import numpy as np
from scipy import ndimage, signal


BAND_NAMES = ("5_100hz", "100_1khz", "1_20khz", "20_80khz", "80_200khz")
FEATURE_NAMES = ("slow_mean", "subkhz_rms", "broadband_rms", "fast_residual_rms")


def _case_fields(case: object) -> dict[str, object]:
    values = asdict(case) if is_dataclass(case) else vars(case)
    return {
        key: value
        for key, value in values.items()
        if key != "folder" and isinstance(value, (str, int, float, bool, type(None)))
    }


def _control_group(case: object) -> tuple[object, ...]:
    if hasattr(case, "experiment"):
        return (
            getattr(case, "experiment"),
            getattr(case, "arrangement"),
            getattr(case, "detector"),
        )
    return (getattr(case, "session"), getattr(case, "detector"))


def _controls(case: object, cases: Iterable[object]) -> list[object]:
    group = _control_group(case)
    return [
        item for item in cases
        if _control_group(item) == group
        and getattr(item, "condition") in ("background", "vfd_stop")
    ]


def temporal_band_rows(
    cases: list[object],
    results: dict[str, dict[str, object]],
    valid_channels: Callable[[dict[str, object]], list[int]],
) -> list[dict[str, object]]:
    """Describe every Welch segment without treating segments as replicates."""
    rows: list[dict[str, object]] = []
    for case in cases:
        result = results[getattr(case, "case_id")]
        if "welch_segment_bandpower" not in result:
            continue
        controls = _controls(case, cases)
        comparison_results = [result] + [results[getattr(item, "case_id")] for item in controls]
        selected_set = set(valid_channels(comparison_results[0]))
        for comparison_result in comparison_results[1:]:
            selected_set &= set(valid_channels(comparison_result))
        selected = sorted(selected_set)
        if len(selected) < 4:
            raise ValueError(f"Only {len(selected)} common healthy channels for {getattr(case, 'case_id')}")
        powers = np.asarray(result["welch_segment_bandpower"], dtype=np.float64)
        for band_index, band in enumerate(BAND_NAMES):
            channel_segment_db = 10.0 * np.log10(
                np.maximum(powers[:, selected, band_index], 1e-300)
            )
            segment_db = np.median(channel_segment_db, axis=1)
            row = {
                **_case_fields(case),
                "band": band,
                "welch_segment_count": len(segment_db),
                "common_healthy_channel_count": len(selected),
                "common_healthy_channels_1based": ";".join(str(index + 1) for index in selected),
                "segment_median_db": float(np.median(segment_db)),
                "segment_q05_db": float(np.percentile(segment_db, 5)),
                "segment_q25_db": float(np.percentile(segment_db, 25)),
                "segment_q75_db": float(np.percentile(segment_db, 75)),
                "segment_q95_db": float(np.percentile(segment_db, 95)),
                "segment_iqr_db": float(np.percentile(segment_db, 75) - np.percentile(segment_db, 25)),
                "median_channel_temporal_sd_db": float(np.median(np.std(channel_segment_db, axis=0))),
                "segments_are_descriptive_not_independent_replicates": True,
            }
            if controls:
                all_pairwise_controls = []
                for control in controls:
                    control_result = results[getattr(control, "case_id")]
                    control_power = np.asarray(
                        control_result["welch_segment_bandpower"], dtype=np.float64
                    )
                    control_channel_segment_db = 10.0 * np.log10(np.maximum(
                        control_power[:, selected, band_index], 1e-300
                    ))
                    pairwise_control = np.median(
                        channel_segment_db[:, None, :]
                        - control_channel_segment_db[None, :, :],
                        axis=2,
                    )
                    all_pairwise_controls.append(pairwise_control.ravel())
                    prefix = f"contrast_to_{getattr(control, 'condition')}"
                    row.update({
                        f"{prefix}_median_db": float(np.median(pairwise_control)),
                        f"{prefix}_q025_db": float(np.percentile(pairwise_control, 2.5)),
                        f"{prefix}_q975_db": float(np.percentile(pairwise_control, 97.5)),
                        f"{prefix}_temporal_superiority_fraction": float(
                            np.mean(pairwise_control > 0.0)
                        ),
                    })
                pairwise = np.concatenate(all_pairwise_controls)
                row.update({
                    "matched_controls": ";".join(getattr(item, "case_id") for item in controls),
                    "median_contrast_to_control_segments_db": float(np.median(pairwise)),
                    "contrast_to_control_segments_q025_db": float(np.percentile(pairwise, 2.5)),
                    "contrast_to_control_segments_q975_db": float(np.percentile(pairwise, 97.5)),
                    "temporal_superiority_fraction": float(np.mean(pairwise > 0.0)),
                })
            rows.append(row)
    return rows


def _stable_feature(result: dict[str, object], feature: str,
                    trim_start_s: float, trim_end_s: float) -> np.ndarray:
    values = np.asarray(result["features"][feature], dtype=np.float64)
    if feature != "slow_mean":
        positive = values[values > 0]
        floor = float(np.percentile(positive, 0.1)) if len(positive) else 1e-15
        values = np.log10(np.maximum(values, floor))
    fs = float(result["envelope_fs"])
    start = int(round(trim_start_s * fs))
    end = len(values) - int(round(trim_end_s * fs))
    return values[start:end]


def _feature_periodogram(values: np.ndarray, sample_rate: float) -> tuple[np.ndarray, np.ndarray]:
    frequency, psd = signal.periodogram(
        values,
        fs=sample_rate,
        window="hann",
        detrend="linear",
        axis=0,
        scaling="density",
    )
    return frequency, psd.T


def _target_power(frequency: np.ndarray, psd: np.ndarray,
                  target_hz: float, half_width_hz: float) -> np.ndarray:
    use = np.abs(frequency - target_hz) <= half_width_hz
    return np.max(psd[:, use], axis=1)


def low_frequency_blind_rows(
    cases: list[object],
    results: dict[str, dict[str, object]],
    valid_channels: Callable[[dict[str, object]], list[int]],
    trim_start_s: float = 15.0,
    trim_end_s: float = 5.0,
    low_hz: float = 0.05,
    high_hz: float = 4.5,
    peak_limit: int = 10,
) -> list[dict[str, object]]:
    """Discover low-frequency candidates and compare them with matched controls.

    Candidate selection and evaluation use the same file, so these rows are
    explicitly exploratory. They are useful for locating repeatable targets,
    not for assigning confirmatory p-values.
    """
    spectra: dict[tuple[str, str], tuple[np.ndarray, np.ndarray]] = {}
    for case in cases:
        result = results[getattr(case, "case_id")]
        fs = float(result["envelope_fs"])
        for feature in FEATURE_NAMES:
            values = _stable_feature(result, feature, trim_start_s, trim_end_s)
            spectra[(getattr(case, "case_id"), feature)] = _feature_periodogram(values, fs)

    rows: list[dict[str, object]] = []
    for case in cases:
        if getattr(case, "condition") in ("background", "vfd_stop"):
            continue
        controls = _controls(case, cases)
        comparison_results = [results[getattr(case, "case_id")]] + [
            results[getattr(item, "case_id")] for item in controls
        ]
        selected_set = set(valid_channels(comparison_results[0]))
        for comparison_result in comparison_results[1:]:
            selected_set &= set(valid_channels(comparison_result))
        selected = sorted(selected_set)
        if len(selected) < 4:
            raise ValueError(f"Only {len(selected)} common healthy channels for {getattr(case, 'case_id')}")
        for feature in FEATURE_NAMES:
            frequency, psd = spectra[(getattr(case, "case_id"), feature)]
            use = (frequency >= low_hz) & (frequency <= min(high_hz, 0.95 * frequency[-1]))
            use_indices = np.flatnonzero(use)
            if len(use_indices) < 7:
                continue
            aggregate_db = 10.0 * np.log10(
                np.maximum(np.median(psd[selected], axis=0), 1e-300)
            )
            local_db = aggregate_db[use]
            kernel = min(31, len(local_db) if len(local_db) % 2 else len(local_db) - 1)
            kernel = max(kernel, 3)
            baseline = ndimage.median_filter(local_db, size=kernel, mode="nearest")
            excess = local_db - baseline
            peaks, properties = signal.find_peaks(excess, prominence=1.0, distance=2)
            if not len(peaks):
                continue
            score = properties["prominences"] + np.maximum(excess[peaks], 0.0)
            order = np.argsort(score)[::-1][:peak_limit]
            resolution = float(np.median(np.diff(frequency)))
            half_width = max(1.5 * resolution, 0.012)
            for rank, peak_local_index in enumerate(peaks[order], start=1):
                index = use_indices[peak_local_index]
                target = float(frequency[index])
                active_power = _target_power(frequency, psd[selected], target, half_width)
                control_powers = []
                for control in controls:
                    control_frequency, control_psd = spectra[(getattr(control, "case_id"), feature)]
                    control_powers.append(_target_power(
                        control_frequency,
                        control_psd[selected],
                        target,
                        half_width,
                    ))
                matched_control_max = np.max(np.vstack(control_powers), axis=0)
                contrast = 10.0 * np.log10(
                    np.maximum(active_power, 1e-300)
                    / np.maximum(matched_control_max, 1e-300)
                )
                rows.append({
                    **_case_fields(case),
                    "feature": feature,
                    "rank_within_case_feature": rank,
                    "frequency_hz": target,
                    "period_s": 1.0 / target,
                    "frequency_resolution_hz": resolution,
                    "common_healthy_channel_count": len(selected),
                    "common_healthy_channels_1based": ";".join(
                        str(index + 1) for index in selected
                    ),
                    "aggregate_local_excess_db": float(excess[peak_local_index]),
                    "aggregate_peak_prominence_db": float(properties["prominences"][order][rank - 1]),
                    "matched_controls": ";".join(getattr(item, "case_id") for item in controls),
                    "median_channel_contrast_to_matched_control_max_db": float(np.median(contrast)),
                    "q25_channel_contrast_to_matched_control_max_db": float(np.percentile(contrast, 25)),
                    "q75_channel_contrast_to_matched_control_max_db": float(np.percentile(contrast, 75)),
                    "channel_support_fraction_above_control": float(np.mean(contrast > 0.0)),
                    "channel_support_fraction_above_control_3db": float(np.mean(contrast > 3.0)),
                    "exploratory_same_file_peak_selection": True,
                })
    return rows
