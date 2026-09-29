"""Per-acquisition channel health classification.

Channel failures are not assumed to persist between files. Every comparison
uses the intersection of channels classified as healthy in all participating
acquisitions.
"""

from __future__ import annotations

import numpy as np


CORE_METRICS = ("std", "difference_rms", "range")


def _robust_z(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    center = np.nanmedian(values)
    scale = 1.4826 * np.nanmedian(np.abs(values - center))
    if not np.isfinite(scale) or scale < 1e-12:
        scale = np.nanstd(values)
    if not np.isfinite(scale) or scale < 1e-12:
        return np.zeros_like(values)
    return (values - center) / scale


def assess_channel_quality(result: dict[str, object]) -> list[dict[str, object]]:
    channel_count = len(result["channel_names"])
    health = result.get("health")
    if health is None:
        return [{
            "channel_index": index + 1,
            "automatic_bad": False,
            "automatic_suspect": False,
            "health_score": 0,
            "health_reasons": "health_metrics_unavailable",
        } for index in range(channel_count)]

    metric_z: dict[str, np.ndarray] = {}
    for metric in CORE_METRICS:
        values = np.array([float(row[metric]) for row in health])
        metric_z[metric] = _robust_z(np.log10(np.maximum(values, 1e-30)))

    temporal_instability = np.full(channel_count, np.nan)
    temporal_z = np.zeros(channel_count)
    if "welch_segment_bandpower" in result:
        segment_power = np.asarray(result["welch_segment_bandpower"], dtype=np.float64)
        segment_db = 10.0 * np.log10(np.maximum(segment_power, 1e-300))
        temporal_instability = np.median(np.std(segment_db, axis=0), axis=1)
        temporal_z = _robust_z(temporal_instability)

    rows: list[dict[str, object]] = []
    for index, source in enumerate(health):
        reasons = []
        hard = (
            float(source.get("nonfinite_fraction", 0.0)) > 0.0
            or float(source.get("flat_difference_fraction", 0.0)) > 0.95
            or float(source.get("std", 0.0)) < 1e-10
            or float(source.get("clip_fraction", 0.0)) > 0.001
        )
        if hard:
            reasons.append("hard_failure")
        core_outliers = 0
        extreme_core = False
        row: dict[str, object] = {
            "channel_index": index + 1,
            "channel_name": result["channel_names"][index],
        }
        for metric in CORE_METRICS:
            z = float(metric_z[metric][index])
            row[f"within_file_{metric}_robust_z"] = z
            if abs(z) > 6.0:
                core_outliers += 1
                reasons.append(f"{metric}_outlier")
            if abs(z) > 10.0:
                extreme_core = True
        temporal_value = float(temporal_instability[index])
        temporal_score = float(temporal_z[index])
        temporal_bad = np.isfinite(temporal_value) and temporal_score > 8.0
        temporal_suspect = np.isfinite(temporal_value) and temporal_score > 6.0
        if temporal_bad:
            reasons.append("temporal_band_instability")

        automatic_bad = bool(
            hard
            or core_outliers >= 2
            or extreme_core
            or (temporal_bad and core_outliers >= 1)
        )
        automatic_suspect = bool(
            automatic_bad or core_outliers >= 1 or temporal_suspect
        )
        row.update({
            "temporal_band_sd_db_median": temporal_value,
            "within_file_temporal_band_sd_robust_z": temporal_score,
            "core_outlier_votes": core_outliers,
            "automatic_bad": automatic_bad,
            "automatic_suspect": automatic_suspect,
            "health_score": int(hard) * 3 + core_outliers + int(temporal_bad) * 2,
            "health_reasons": ";".join(reasons),
        })
        rows.append(row)
    return rows


def valid_channel_indices(result: dict[str, object], *, exclude_suspect: bool = False) -> list[int]:
    return [
        index for index, row in enumerate(assess_channel_quality(result))
        if not bool(row["automatic_suspect"] if exclude_suspect else row["automatic_bad"])
    ]


def common_valid_channel_indices(*results: dict[str, object],
                                 minimum: int = 4,
                                 exclude_suspect: bool = False) -> list[int]:
    if not results:
        return []
    common = set(valid_channel_indices(results[0], exclude_suspect=exclude_suspect))
    for result in results[1:]:
        common &= set(valid_channel_indices(result, exclude_suspect=exclude_suspect))
    selected = sorted(common)
    if len(selected) < minimum:
        raise ValueError(
            f"Only {len(selected)} common healthy channels remain; minimum is {minimum}"
        )
    return selected
