"""Compare archived pure-background acquisitions with dynamic channel QC."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from channel_quality import assess_channel_quality, valid_channel_indices


BANDS = ("5_100hz", "100_1khz", "1_20khz", "20_80khz", "80_200khz")
BAND_LIMITS = {
    "5_100hz": (5.0, 100.0),
    "100_1khz": (100.0, 1_000.0),
    "1_20khz": (1_000.0, 20_000.0),
    "20_80khz": (20_000.0, 80_000.0),
    "80_200khz": (80_000.0, 199_900.0),
}


@dataclass(frozen=True)
class BackgroundCase:
    case_id: str
    date: str
    detector: str
    group: str
    position: str
    archive: Path


def discover_cases(backup_project: Path) -> list[BackgroundCase]:
    roots = {
        "2026-06-17": backup_project / "results" / "experiment_20260617" / "exact_archive",
        "2026-07-31": backup_project / "results" / "experiment_20260731" / "tdms" / "exact_archive",
        "2026-08-06": backup_project / "results" / "experiment_20260806" / "exact_archive",
    }
    cases: list[BackgroundCase] = []

    for folder in sorted(roots["2026-06-17"].glob("*m_0hz__*")):
        distance = folder.name.split("m_", maxsplit=1)[0] + " m"
        cases.append(BackgroundCase(
            folder.name,
            "2026-06-17",
            "unlabeled",
            f"distance_{distance.replace(' ', '')}",
            distance,
            folder,
        ))

    july = roots["2026-07-31"]
    cases.extend([
        BackgroundCase(
            "morning_background", "2026-07-31", "TC2", "morning", "recorded position",
            july / "morning_background",
        ),
        BackgroundCase(
            "afternoon_background", "2026-07-31", "TC1", "afternoon", "recorded position",
            july / "afternoon_background",
        ),
    ])

    august = roots["2026-08-06"]
    august_details = (
        ("duo1_tc1_background", "TC1", "duo1", "A"),
        ("duo1_tc2_background", "TC2", "duo1", "B"),
        ("vfd_tc1_background", "TC1", "vfd", "fixed"),
        ("vfd_tc2_background", "TC2", "vfd", "fixed"),
        ("duo2_tc1_background", "TC1", "duo2", "B"),
        ("duo2_tc2_background", "TC2", "duo2", "A"),
    )
    for case_id, detector, group, position in august_details:
        cases.append(BackgroundCase(
            case_id, "2026-08-06", detector, group, position, august / case_id
        ))
    return cases


def load_case(case: BackgroundCase) -> dict[str, object]:
    with (case.archive / "metadata.json").open(encoding="utf-8") as handle:
        metadata = json.load(handle)
    with (case.archive / "health.json").open(encoding="utf-8") as handle:
        health = json.load(handle)
    with np.load(case.archive / "welch.npz") as data:
        result: dict[str, object] = {
            "channel_names": list(metadata["channel_names"]),
            "health": health,
            "frequency_hz": np.asarray(data["frequency_hz"], dtype=np.float64),
            "psd_mean": np.asarray(data["psd_mean"], dtype=np.float64),
            "welch_segment_bandpower": np.asarray(data["segment_bandpower"], dtype=np.float64),
            "band_names": [str(value) for value in data["band_names"]],
            "segment_time_s": np.asarray(data["segment_time_s"], dtype=np.float64),
        }
    result["quality"] = assess_channel_quality(result)
    result["valid"] = valid_channel_indices(result)
    result["metadata"] = metadata
    return result


def full_record_band_matrix(result: dict[str, object]) -> np.ndarray:
    frequency = np.asarray(result["frequency_hz"], dtype=np.float64)
    psd = np.asarray(result["psd_mean"], dtype=np.float64)
    matrix = np.empty((psd.shape[0], len(BANDS)), dtype=np.float64)
    for band_index, band in enumerate(BANDS):
        low, high = BAND_LIMITS[band]
        use = (frequency >= low) & (frequency < high)
        matrix[:, band_index] = np.trapezoid(psd[:, use], frequency[use], axis=1)
    return matrix


def describe_case(case: BackgroundCase, result: dict[str, object]) -> list[dict[str, object]]:
    power = np.asarray(result["welch_segment_bandpower"], dtype=np.float64)
    valid = list(result["valid"])
    band_names = list(result["band_names"])
    metadata = dict(result["metadata"])
    full_record_power = full_record_band_matrix(result)
    rows: list[dict[str, object]] = []
    for band in BANDS:
        band_index = band_names.index(band)
        channel_segment_db = 10.0 * np.log10(
            np.maximum(power[:, valid, band_index], 1e-300)
        )
        segment_db = np.median(channel_segment_db, axis=1)
        median_db = float(np.median(segment_db))
        full_record_channel_db = 10.0 * np.log10(
            np.maximum(full_record_power[valid, band_index], 1e-300)
        )
        full_record_median_db = float(np.median(full_record_channel_db))
        rows.append({
            "case_id": case.case_id,
            "date": case.date,
            "start_time": metadata["start_time"],
            "detector": case.detector,
            "group": case.group,
            "position": case.position,
            "duration_s": metadata["duration_s"],
            "healthy_channel_count": len(valid),
            "healthy_channels_1based": ";".join(str(index + 1) for index in valid),
            "band": band,
            "full_record_median_bandpower_db_re_1v2": full_record_median_db,
            "full_record_equivalent_rms_v": float(
                np.sqrt(10.0 ** (full_record_median_db / 10.0))
            ),
            "segment_median_bandpower_db_re_1v2": median_db,
            "within_file_iqr_db": float(np.percentile(segment_db, 75) - np.percentile(segment_db, 25)),
            "within_file_q05_db": float(np.percentile(segment_db, 5)),
            "within_file_q95_db": float(np.percentile(segment_db, 95)),
            "welch_segment_count": len(segment_db),
        })
    return rows


def pairwise_rows(
    cases: list[BackgroundCase], results: dict[str, dict[str, object]]
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for left_index, left in enumerate(cases):
        for right in cases[left_index + 1:]:
            if left.detector != right.detector:
                continue
            if left.detector == "unlabeled" and left.date != right.date:
                continue
            left_result = results[left.case_id]
            right_result = results[right.case_id]
            common = sorted(set(left_result["valid"]) & set(right_result["valid"]))
            if len(common) < 4:
                continue
            left_power = np.asarray(left_result["welch_segment_bandpower"], dtype=np.float64)
            right_power = np.asarray(right_result["welch_segment_bandpower"], dtype=np.float64)
            left_full_record = full_record_band_matrix(left_result)
            right_full_record = full_record_band_matrix(right_result)
            left_band_names = list(left_result["band_names"])
            right_band_names = list(right_result["band_names"])
            for band in BANDS:
                left_band = left_band_names.index(band)
                right_band = right_band_names.index(band)
                left_db = 10.0 * np.log10(np.maximum(left_power[:, common, left_band], 1e-300))
                right_db = 10.0 * np.log10(np.maximum(right_power[:, common, right_band], 1e-300))
                pairwise_delta = np.median(
                    right_db[:, None, :] - left_db[None, :, :], axis=2
                ).ravel()
                full_record_channel_delta = 10.0 * np.log10(
                    np.maximum(right_full_record[common, right_band], 1e-300)
                    / np.maximum(left_full_record[common, left_band], 1e-300)
                )
                rows.append({
                    "detector": left.detector,
                    "left_case": left.case_id,
                    "right_case": right.case_id,
                    "left_date": left.date,
                    "right_date": right.date,
                    "same_date": left.date == right.date,
                    "band": band,
                    "common_healthy_channel_count": len(common),
                    "full_record_median_channel_delta_db": float(
                        np.median(full_record_channel_delta)
                    ),
                    "full_record_q25_channel_delta_db": float(
                        np.percentile(full_record_channel_delta, 25)
                    ),
                    "full_record_q75_channel_delta_db": float(
                        np.percentile(full_record_channel_delta, 75)
                    ),
                    "right_minus_left_median_db": float(np.median(pairwise_delta)),
                    "right_minus_left_q025_db": float(np.percentile(pairwise_delta, 2.5)),
                    "right_minus_left_q975_db": float(np.percentile(pairwise_delta, 97.5)),
                    "absolute_median_difference_db": abs(float(np.median(pairwise_delta))),
                })
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--backup-project",
        type=Path,
        default=Path(r"E:\backup\DataProcess_20260809\project"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results") / "archived_background_comparison",
    )
    args = parser.parse_args()

    cases = discover_cases(args.backup_project)
    results = {case.case_id: load_case(case) for case in cases}
    summary = [row for case in cases for row in describe_case(case, results[case.case_id])]
    pairwise = pairwise_rows(cases, results)
    write_csv(args.output / "background_band_summary.csv", summary)
    write_csv(args.output / "same_detector_background_pairwise.csv", pairwise)

    high = [row for row in summary if row["band"] == "80_200khz"]
    for row in high:
        print(
            f"{row['case_id']}: {row['full_record_median_bandpower_db_re_1v2']:.4f} dB, "
            f"{1e3 * row['full_record_equivalent_rms_v']:.4f} mV RMS, "
            f"IQR {row['within_file_iqr_db']:.4f} dB, "
            f"healthy {row['healthy_channel_count']}"
        )


if __name__ == "__main__":
    main()
