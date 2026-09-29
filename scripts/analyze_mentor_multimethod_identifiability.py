"""Test whether new method features identify conditions under grouped validation."""

from __future__ import annotations

import argparse
import warnings
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, confusion_matrix
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.preprocessing import StandardScaler

from scripts.build_mentor_methods_v2_report import contrast_tables, feature_identity, read_frame
from scripts.mentor_method_common import METHOD_OUTPUT, stable_seed, write_frame, write_manifest


INDEX_COLUMNS = [
    "dataset", "case_id", "arrangement", "detector", "condition", "distance",
    "carrier_khz", "output_hz", "reference_case_id", "reference_condition",
]


def multimethod_feature_matrix(base: Path) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for family, path in contrast_tables(base):
        frame = read_frame(path)
        if frame.empty:
            continue
        frame = frame[
            (frame["dataset"] != 20260617)
            & (frame["reference_condition"] == "background")
        ]
        identities = feature_identity(frame)
        differences = [column for column in frame if column.endswith("_difference")]
        for item in frame.itertuples(index=False):
            identity = ";".join(
                f"{column}={getattr(item, column)}" for column in identities
            ) or "all"
            base_row = {column: getattr(item, column) for column in INDEX_COLUMNS}
            for difference in differences:
                value = getattr(item, difference)
                if not np.isfinite(value):
                    continue
                rows.append({
                    **base_row,
                    "feature_key": (
                        f"{family}|{difference.removesuffix('_difference')}|{identity}"
                    ),
                    "value": float(value),
                })
    spectral = read_frame(
        base.parent / "mentor_aligned_pre_electrochemical_v1"
        / "spectral_redistribution_score.csv"
    )
    if not spectral.empty:
        spectral = spectral[spectral["dataset"] != 20260617]
        spectral_features = ["20_80khz", "80_200khz", "redistribution_score_db"]
        for _, item in spectral.iterrows():
            base_row = {
                "dataset": item["dataset"],
                "case_id": item["case_id"],
                "arrangement": item["arrangement"],
                "detector": item["detector"],
                "condition": item["condition"],
                "distance": np.nan,
                "carrier_khz": item["carrier_khz"],
                "output_hz": item["output_hz"],
                "reference_case_id": item["reference_case_id"],
                "reference_condition": "background",
            }
            for feature in spectral_features:
                rows.append({
                    **base_row,
                    "feature_key": f"baseline_spectral|{feature}|all",
                    "value": float(item[feature]),
                })
    long = pd.DataFrame(rows)
    if long.empty:
        return long
    row_keys = ["case_id", "reference_case_id"]
    metadata = long[INDEX_COLUMNS].drop_duplicates(row_keys)
    wide = long.pivot_table(
        index=row_keys, columns="feature_key", values="value", aggfunc="median",
    ).reset_index()
    wide = metadata.merge(wide, on=row_keys, how="inner")
    wide.columns.name = None
    return wide


def grouped_predictions(
    features: np.ndarray, labels: np.ndarray, groups: np.ndarray,
    feature_names: np.ndarray, selected_count: int,
) -> tuple[np.ndarray, Counter[str]]:
    predictions = np.empty_like(labels, dtype=object)
    selected = Counter()
    for train, test in LeaveOneGroupOut().split(features, labels, groups):
        training = features[train]
        finite_fraction = np.mean(np.isfinite(training), axis=0)
        use = finite_fraction >= 0.5
        if not np.any(use):
            raise ValueError("No features meet training-fold coverage threshold")
        imputer = SimpleImputer(strategy="median")
        training_imputed = imputer.fit_transform(training[:, use])
        test_imputed = imputer.transform(features[test][:, use])
        variable = np.var(training_imputed, axis=0) > 1e-12
        if not np.any(variable):
            raise ValueError("No nonconstant features remain in training fold")
        use_names = feature_names[use][variable]
        training_variable = training_imputed[:, variable]
        test_variable = test_imputed[:, variable]
        k = min(
            selected_count, training_variable.shape[1],
            max(1, len(train) - len(np.unique(labels[train]))),
        )
        selector = SelectKBest(f_classif, k=k)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            warnings.simplefilter("ignore", category=UserWarning)
            training_selected = selector.fit_transform(training_variable, labels[train])
        test_selected = selector.transform(test_variable)
        scaler = StandardScaler()
        training_scaled = scaler.fit_transform(training_selected)
        test_scaled = scaler.transform(test_selected)
        classifier = LogisticRegression(
            class_weight="balanced", max_iter=2000, C=1.0,
            solver="liblinear" if len(np.unique(labels)) == 2 else "lbfgs",
        )
        classifier.fit(training_scaled, labels[train])
        predictions[test] = classifier.predict(test_scaled)
        selected.update(use_names[selector.get_support()].tolist())
    return predictions, selected


def shuffled_within_groups(
    labels: np.ndarray, groups: np.ndarray, rng: np.random.Generator,
) -> np.ndarray:
    shuffled = labels.copy()
    for group in np.unique(groups):
        use = np.flatnonzero(groups == group)
        shuffled[use] = rng.permutation(shuffled[use])
    return shuffled


def evaluate_task(
    frame: pd.DataFrame, task: str, label_column: str, selected_count: int,
    permutations: int, feature_set: str,
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame]:
    metadata = set(INDEX_COLUMNS)
    available = [column for column in frame if column not in metadata]
    if feature_set == "baseline_spectral_only":
        available = [column for column in available if column.startswith("baseline_spectral|")]
    elif feature_set == "new_methods_only":
        available = [column for column in available if not column.startswith("baseline_spectral|")]
    feature_names = np.asarray(available)
    features = frame[feature_names].apply(pd.to_numeric, errors="coerce").to_numpy()
    labels = frame[label_column].astype(str).to_numpy()
    groups = (
        frame["dataset"].astype(str) + "|" + frame["arrangement"].astype(str)
        + "|" + frame["detector"].astype(str)
    ).to_numpy()
    prediction, selected = grouped_predictions(
        features, labels, groups, feature_names, selected_count
    )
    observed = float(balanced_accuracy_score(labels, prediction))
    rng = np.random.default_rng(stable_seed("multimethod_classifier", task, feature_set))
    null = []
    for _ in range(permutations):
        shuffled = shuffled_within_groups(labels, groups, rng)
        shuffled_prediction, _ = grouped_predictions(
            features, shuffled, groups, feature_names, selected_count
        )
        null.append(float(balanced_accuracy_score(shuffled, shuffled_prediction)))
    null_values = np.asarray(null, dtype=np.float64)
    class_order = sorted(np.unique(labels))
    matrix = confusion_matrix(labels, prediction, labels=class_order)
    summary = {
        "task": task,
        "feature_set": feature_set,
        "sample_count": len(frame),
        "group_count": len(np.unique(groups)),
        "class_count": len(class_order),
        "feature_count_before_fold_filter": len(feature_names),
        "selected_features_per_fold": selected_count,
        "grouped_balanced_accuracy": observed,
        "permutation_null_median": float(np.median(null_values)),
        "permutation_null_q95": float(np.percentile(null_values, 95)),
        "permutation_p": float((np.sum(null_values >= observed) + 1) / (len(null_values) + 1)),
        "class_order": ";".join(class_order),
        "confusion_matrix_rows": ";".join(
            ",".join(str(int(value)) for value in row) for row in matrix
        ),
        "interpretation": "exploratory_grouped_cv; not external validation",
    }
    predictions = frame[INDEX_COLUMNS].copy()
    predictions["task"] = task
    predictions["feature_set"] = feature_set
    predictions["true_label"] = labels
    predictions["predicted_label"] = prediction
    predictions["group"] = groups
    selections = pd.DataFrame([
        {"task": task, "feature_set": feature_set, "feature_key": feature,
         "fold_selection_count": count}
        for feature, count in selected.most_common()
    ])
    return summary, predictions, selections


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=METHOD_OUTPUT)
    parser.add_argument("--output", type=Path, default=METHOD_OUTPUT / "identifiability")
    parser.add_argument("--permutations", type=int, default=199)
    parser.add_argument("--selected-features", type=int, default=10)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    matrix = multimethod_feature_matrix(args.base)
    write_frame(args.output / "multimethod_local_background_feature_matrix.csv", matrix)
    tasks = [
        ("run_vs_stop", matrix[matrix["condition"].isin(["30hz", "50hz", "run", "vfd_stop"])].copy(), "condition"),
        ("30hz_vs_50hz", matrix[matrix["condition"].isin(["30hz", "50hz"])].copy(), "condition"),
        ("carrier_4_8_12khz", matrix[
            matrix["arrangement"].eq("vfd")
            & matrix["carrier_khz"].isin([4.0, 8.0, 12.0])
        ].copy(), "carrier_khz"),
    ]
    summaries = []
    prediction_frames = []
    selection_frames = []
    for task, frame, label_column in tasks:
        if task == "run_vs_stop":
            frame["condition"] = np.where(
                frame["condition"].eq("vfd_stop"), "stop", "run"
            )
        for feature_set in ("baseline_spectral_only", "new_methods_only", "combined"):
            summary, predictions, selections = evaluate_task(
                frame, task, label_column, args.selected_features,
                args.permutations, feature_set,
            )
            summaries.append(summary)
            prediction_frames.append(predictions)
            selection_frames.append(selections)
            print(
                f"{task}/{feature_set}: balanced accuracy="
                f"{summary['grouped_balanced_accuracy']:.3f}", flush=True
            )
    write_frame(args.output / "grouped_identifiability_summary.csv", summaries)
    write_frame(
        args.output / "grouped_identifiability_predictions.csv",
        pd.concat(prediction_frames, ignore_index=True),
    )
    write_frame(
        args.output / "grouped_identifiability_selected_features.csv",
        pd.concat(selection_frames, ignore_index=True),
    )
    write_manifest(args.output, "multimethod_identifiability", {
        "permutations": args.permutations,
        "selected_features_per_fold": args.selected_features,
        "task_count": len(tasks) * 3,
        "feature_matrix_rows": len(matrix),
        "feature_matrix_columns": len(matrix.columns),
        "grouping": "dataset|arrangement|detector",
    })
    print(f"Output: {args.output}")
    return args.output


if __name__ == "__main__":
    main()
