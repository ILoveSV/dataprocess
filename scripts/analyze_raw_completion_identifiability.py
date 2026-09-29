"""Grouped unknown-label tests after adding full-record raw high-frequency features."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.analyze_mentor_multimethod_identifiability import (
    INDEX_COLUMNS,
    evaluate_task,
    multimethod_feature_matrix,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_V2 = PROJECT_ROOT / 'analysis/mentor_aligned_methods_v2'
DEFAULT_RAW = (
    PROJECT_ROOT / 'analysis/mentor_aligned_raw_completion_v3/full_raw_highfrequency/full_raw_highfrequency_matched_contrasts.csv'
)
DEFAULT_OUTPUT = PROJECT_ROOT / 'analysis/mentor_aligned_raw_completion_v3/identifiability'


def full_raw_matrix(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame = frame[
        (frame["dataset"].astype(str) != "20260617")
        & (frame["reference_condition"] == "background")
    ].copy()
    differences = [
        column for column in frame.columns
        if column.endswith("_difference")
        and not column.endswith(("frequency_hz_difference", "count_difference"))
    ]
    rows = []
    for item in frame.itertuples(index=False):
        base = {column: getattr(item, column) for column in INDEX_COLUMNS}
        for column in differences:
            value = getattr(item, column)
            if not np.isfinite(value):
                continue
            rows.append({
                **base,
                "feature_key": f"full_raw|{column.removesuffix('_difference')}|all",
                "value": float(value),
            })
    long = pd.DataFrame(rows)
    metadata = long[INDEX_COLUMNS].drop_duplicates(["case_id", "reference_case_id"])
    wide = long.pivot_table(
        index=["case_id", "reference_case_id"], columns="feature_key",
        values="value", aggfunc="median",
    ).reset_index()
    wide = metadata.merge(wide, on=["case_id", "reference_case_id"], how="inner")
    wide.columns.name = None
    return wide


def combined_matrix(v2: Path, raw_path: Path) -> pd.DataFrame:
    existing = multimethod_feature_matrix(v2)
    raw = full_raw_matrix(raw_path)
    raw_features = [column for column in raw if column.startswith("full_raw|")]
    return existing.merge(
        raw[["case_id", "reference_case_id", *raw_features]],
        on=["case_id", "reference_case_id"], how="inner",
    )


def select_feature_set(frame: pd.DataFrame, feature_set: str) -> pd.DataFrame:
    metadata = set(INDEX_COLUMNS)
    feature_columns = [column for column in frame if column not in metadata]
    if feature_set == "baseline_spectral_only":
        selected = [column for column in feature_columns if column.startswith("baseline_spectral|")]
    elif feature_set == "v2_methods_only":
        selected = [
            column for column in feature_columns
            if not column.startswith(("baseline_spectral|", "full_raw|"))
        ]
    elif feature_set == "full_raw_only":
        selected = [column for column in feature_columns if column.startswith("full_raw|")]
    elif feature_set == "full_raw_phase_coherence":
        selected = [
            column for column in feature_columns
            if column.startswith("full_raw|")
            and ("pair_coherence" in column or "pair_phase_locking" in column)
        ]
    elif feature_set == "predefined_coherence_bands":
        allowed = {
            "full_raw|pair_coherence_20_80khz_median|all",
            "full_raw|pair_coherence_80_200khz_median|all",
            "full_raw|pair_coherence_20_80khz_epoch_median|all",
            "full_raw|pair_coherence_80_200khz_epoch_median|all",
        }
        selected = [column for column in feature_columns if column in allowed]
    elif feature_set == "predefined_80_200khz_coherence":
        allowed = {
            "full_raw|pair_coherence_80_200khz_median|all",
            "full_raw|pair_coherence_80_200khz_epoch_median|all",
        }
        selected = [column for column in feature_columns if column in allowed]
    elif feature_set == "combined_all":
        selected = feature_columns
    else:
        raise ValueError(feature_set)
    return frame[[*INDEX_COLUMNS, *selected]].copy()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v2", type=Path, default=DEFAULT_V2)
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--permutations", type=int, default=499)
    parser.add_argument("--selected-features", type=int, default=8)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    matrix = combined_matrix(args.v2, args.raw)
    matrix.to_csv(args.output / "raw_completion_feature_matrix.csv", index=False)

    task_frames = {}
    run_stop = matrix[
        matrix["condition"].isin(["30hz", "50hz", "run", "vfd_stop"])
    ].copy()
    run_stop["condition"] = np.where(
        run_stop["condition"] == "vfd_stop", "stop", "run"
    )
    task_frames["run_vs_stop"] = run_stop
    for detector in ("tc1", "tc2"):
        task_frames[f"run_vs_stop_{detector}"] = run_stop[
            run_stop["detector"] == detector
        ].copy()
    thirty_fifty = matrix[matrix["condition"].isin(["30hz", "50hz"])].copy()
    task_frames["30hz_vs_50hz"] = thirty_fifty
    for detector in ("tc1", "tc2"):
        task_frames[f"30hz_vs_50hz_{detector}"] = thirty_fifty[
            thirty_fifty["detector"] == detector
        ].copy()
    carrier = matrix[matrix["carrier_khz"].notna()].copy()
    carrier["condition"] = carrier["carrier_khz"].astype(str)
    task_frames["carrier_4_8_12khz"] = carrier

    feature_sets = (
        "baseline_spectral_only", "v2_methods_only", "full_raw_only",
        "full_raw_phase_coherence", "predefined_coherence_bands",
        "predefined_80_200khz_coherence", "combined_all",
    )
    summaries = []
    predictions = []
    selections = []
    for task, task_frame in task_frames.items():
        for feature_set in feature_sets:
            selected = select_feature_set(task_frame, feature_set)
            summary, prediction, selection = evaluate_task(
                selected, task, "condition", args.selected_features,
                args.permutations, "combined",
            )
            summary["feature_set"] = feature_set
            prediction["feature_set"] = feature_set
            selection["feature_set"] = feature_set
            summaries.append(summary)
            predictions.append(prediction)
            selections.append(selection)
            print(
                f"{task}/{feature_set}: {summary['grouped_balanced_accuracy']:.3f}, "
                f"p={summary['permutation_p']:.4f}", flush=True,
            )
    pd.DataFrame(summaries).to_csv(
        args.output / "raw_completion_identifiability_summary.csv", index=False
    )
    pd.concat(predictions, ignore_index=True).to_csv(
        args.output / "raw_completion_predictions.csv", index=False
    )
    pd.concat(selections, ignore_index=True).to_csv(
        args.output / "raw_completion_feature_selection.csv", index=False
    )
    print(f"Output: {args.output}", flush=True)


if __name__ == "__main__":
    main()
