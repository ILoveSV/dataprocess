import argparse
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import colormaps
import numpy as np
import pandas as pd
from scipy.stats import kruskal
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.svm import LinearSVC


FEATURE_COLUMNS = [
    "band_50_100k",
    "band_100_200k",
    "subband_50_60k",
    "subband_60_70k",
    "subband_70_80k",
    "subband_80_90k",
    "subband_90_100k",
    "subband_100_120k",
    "subband_120_140k",
    "subband_140_160k",
    "subband_160_180k",
    "subband_180_200k",
    "peakwin_53p5_55k",
    "peakwin_137_139p5k",
    "peakwin_177_179k",
]
CORE_PLOT_TASKS = ["Task A active vs 0Hz", "Task B 30Hz vs 50Hz", "Task C distance", "Task D rpm 3-class"]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Feature Separability v1 gate from Feature Extraction v2 outputs.")
    parser.add_argument("--feature-dataset", default="analysis_out/feature_extraction_v2/candidate_feature_dataset_v2.csv")
    parser.add_argument("--stability", default="analysis_out/feature_extraction_v2/feature_stability_summary_v2.csv")
    parser.add_argument("--channel-summary", default="analysis_out/feature_extraction_v2/channel_feature_summary_v2.csv")
    parser.add_argument("--strict-delta", default="analysis_out/feature_extraction_v2/all_vs_strict_feature_delta_v2.csv")
    parser.add_argument("--output", default="analysis_out/feature_separability_v1")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset = pd.read_csv(args.feature_dataset)
    stability = pd.read_csv(args.stability)
    channel_summary = pd.read_csv(args.channel_summary)
    strict_delta_input = pd.read_csv(args.strict_delta)

    matrices = build_feature_matrices(dataset)
    file_channel = matrices["file_channel"]
    file_agg = matrices["file_agg"]
    file_channel.to_csv(output_dir / "feature_matrix_file_channel.csv", index=False, encoding="utf-8-sig")
    file_agg.to_csv(output_dir / "feature_matrix_file_agg.csv", index=False, encoding="utf-8-sig")

    sep = build_separability_summary(file_channel, file_agg)
    sep.to_csv(output_dir / "feature_separability_summary.csv", index=False, encoding="utf-8-sig")
    plot_top_feature_boxplots(file_channel, sep, output_dir / "feature_boxplot_top_by_task.png")

    corr, redundancy = build_correlation_outputs(file_agg[file_agg["analysis_mode"] == "strict"])
    corr.to_csv(output_dir / "feature_correlation_matrix.csv", encoding="utf-8-sig")
    redundancy.to_csv(output_dir / "feature_redundancy_summary.csv", index=False, encoding="utf-8-sig")
    plot_corr(corr, output_dir / "feature_correlation_heatmap.png")

    baseline = build_baseline_results(file_channel, file_agg)
    baseline.to_csv(output_dir / "baseline_model_pilot_results.csv", index=False, encoding="utf-8-sig")
    plot_confusions(file_channel, file_agg, output_dir / "baseline_confusion_matrices.png")

    channel9 = build_channel9_sensitivity(file_channel, file_agg)
    channel9.to_csv(output_dir / "channel9_sensitivity_summary.csv", index=False, encoding="utf-8-sig")

    strict_vs_all = build_strict_vs_all_delta(sep)
    strict_vs_all.to_csv(output_dir / "strict_vs_all_separability_delta.csv", index=False, encoding="utf-8-sig")

    gate = build_gate_summary(sep, baseline, redundancy, channel9, strict_vs_all, stability, strict_delta_input)
    gate.to_csv(output_dir / "ml_readiness_gate_summary.csv", index=False, encoding="utf-8-sig")

    write_report(output_dir, sep, baseline, redundancy, channel9, strict_vs_all, gate)
    print(f"Feature Separability v1 output: {output_dir}")
    return output_dir


def build_feature_matrices(dataset):
    matrices = {}
    id_cols = ["analysis_mode", "sample_id", "group", "distance", "rpm", "file_id", "channel", "qc_flag"]
    file_channel = (
        dataset.pivot_table(index=id_cols, columns="feature_name", values="feature_value", aggfunc="median")
        .reset_index()
    )
    file_channel.columns.name = None
    file_channel = ensure_feature_cols(file_channel)
    matrices["file_channel"] = file_channel

    agg = (
        dataset.groupby(["analysis_mode", "group", "distance", "rpm", "file_id", "feature_name"], as_index=False)
        .agg(feature_value=("feature_value", "median"), qc_flag=("qc_flag", join_qc))
    )
    file_agg = (
        agg.pivot_table(
            index=["analysis_mode", "group", "distance", "rpm", "file_id"],
            columns="feature_name",
            values="feature_value",
            aggfunc="median",
        )
        .reset_index()
    )
    qc = agg.groupby(["analysis_mode", "group", "distance", "rpm", "file_id"], as_index=False)["qc_flag"].agg(join_qc)
    file_agg = file_agg.merge(qc, on=["analysis_mode", "group", "distance", "rpm", "file_id"], how="left")
    file_agg["channel"] = "aggregated_median"
    file_agg["sample_id"] = file_agg["group"] + "__" + file_agg["file_id"] + "__aggregated_median"
    file_agg.columns.name = None
    file_agg = ensure_feature_cols(file_agg)
    ordered = ["analysis_mode", "sample_id", "group", "distance", "rpm", "file_id", "channel", *FEATURE_COLUMNS, "qc_flag"]
    matrices["file_agg"] = file_agg[ordered]
    return matrices


def ensure_feature_cols(df):
    for col in FEATURE_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan
    front = [c for c in ["analysis_mode", "sample_id", "group", "distance", "rpm", "file_id", "channel"] if c in df.columns]
    rest = [c for c in df.columns if c not in set(front + FEATURE_COLUMNS + ["qc_flag"])]
    return df[front + FEATURE_COLUMNS + rest + (["qc_flag"] if "qc_flag" in df.columns else [])]


def join_qc(values):
    unique = sorted(set(str(v) for v in values if pd.notna(v)))
    return ";".join(unique) if unique else "OK"


def build_separability_summary(file_channel, file_agg):
    rows = []
    for grain, matrix in [("file_channel", file_channel), ("file_agg", file_agg)]:
        for mode in ["strict", "all_data"]:
            data = matrix[matrix["analysis_mode"] == mode].copy()
            rows.extend(task_active_vs_zero(data, grain, mode))
            rows.extend(task_30_vs_50(data, grain, mode))
            rows.extend(task_distance(data, grain, mode))
            rows.extend(task_rpm_three_class(data, grain, mode))
    out = pd.DataFrame(rows)
    if not out.empty:
        out["separability_rank"] = out.groupby(["analysis_mode", "sample_grain", "task_name"])["single_feature_auc_or_macro_auc"].rank(ascending=False, method="min")
    return out


def task_active_vs_zero(data, grain, mode):
    rows = []
    for distance, group in data.groupby("distance"):
        current = group[group["rpm"].isin(["0Hz", "30Hz", "50Hz"])].copy()
        current["label"] = np.where(current["rpm"] == "0Hz", "0Hz", "active")
        rows.extend(feature_rows_for_task(current, "Task A active vs 0Hz", grain, mode, distance, "all", "label"))
    return rows


def task_30_vs_50(data, grain, mode):
    rows = []
    for distance, group in data.groupby("distance"):
        current = group[group["rpm"].isin(["30Hz", "50Hz"])].copy()
        rows.extend(feature_rows_for_task(current, "Task B 30Hz vs 50Hz", grain, mode, distance, "30/50Hz", "rpm"))
    return rows


def task_distance(data, grain, mode):
    rows = []
    for rpm, group in data.groupby("rpm"):
        current = group[group["distance"].isin(["2m", "3m", "5m"])].copy()
        rows.extend(feature_rows_for_task(current, "Task C distance", grain, mode, "2/3/5m", rpm, "distance"))
    return rows


def task_rpm_three_class(data, grain, mode):
    current = data[data["rpm"].isin(["0Hz", "30Hz", "50Hz"])].copy()
    return feature_rows_for_task(current, "Task D rpm 3-class", grain, mode, "all", "0/30/50Hz", "rpm")


def feature_rows_for_task(data, task_name, grain, mode, distance_scope, rpm_scope, label_col):
    rows = []
    labels = sorted(data[label_col].dropna().unique().tolist())
    for feature in FEATURE_COLUMNS:
        row = {
            "analysis_mode": mode,
            "sample_grain": grain,
            "task_name": task_name,
            "feature_name": feature,
            "distance_scope": distance_scope,
            "rpm_scope": rpm_scope,
            "n_samples": int(data[feature].notna().sum()) if feature in data else 0,
            "class_labels": json.dumps(labels),
            "median_by_class": "{}",
            "iqr_by_class": "{}",
            "effect_size": np.nan,
            "overlap_score": np.nan,
            "single_feature_auc_or_macro_auc": np.nan,
            "separability_rank": np.nan,
            "notes": "",
            "skipped_reason": "",
        }
        if feature not in data or len(labels) < 2:
            row["skipped_reason"] = "need at least 2 classes"
            rows.append(row)
            continue
        current = data[[feature, label_col]].dropna()
        counts = current[label_col].value_counts()
        if len(counts) < 2 or counts.min() < 3:
            row["skipped_reason"] = "need at least 3 samples per class"
            rows.append(row)
            continue
        med = current.groupby(label_col)[feature].median().to_dict()
        iqr = (current.groupby(label_col)[feature].quantile(0.75) - current.groupby(label_col)[feature].quantile(0.25)).to_dict()
        row["median_by_class"] = json.dumps({str(k): float(v) for k, v in med.items()})
        row["iqr_by_class"] = json.dumps({str(k): float(v) for k, v in iqr.items()})
        y = current[label_col].astype(str)
        x = current[feature].astype(float)
        if len(counts) == 2:
            a, b = labels[:2]
            xa = x[y == str(a)]
            xb = x[y == str(b)]
            row["effect_size"] = robust_effect(xa, xb)
            row["overlap_score"] = distribution_overlap(xa, xb)
            try:
                row["single_feature_auc_or_macro_auc"] = max_auc_direction(y, x)
            except Exception:
                row["single_feature_auc_or_macro_auc"] = np.nan
        else:
            values = [x[y == str(label)] for label in labels]
            try:
                stat, _ = kruskal(*values)
                row["effect_size"] = float(stat / max(len(x) - 1, 1))
            except Exception:
                row["effect_size"] = np.nan
            row["overlap_score"] = np.nan
            try:
                row["single_feature_auc_or_macro_auc"] = multiclass_single_feature_auc(y, x)
            except Exception:
                row["single_feature_auc_or_macro_auc"] = np.nan
        rows.append(row)
    return rows


def robust_effect(a, b):
    delta = float(np.median(b) - np.median(a))
    spread = float((np.subtract(*np.percentile(a, [75, 25])) + np.subtract(*np.percentile(b, [75, 25]))) / 2.0)
    return delta / (spread + 1e-9)


def distribution_overlap(a, b):
    a1, a3 = np.percentile(a, [25, 75])
    b1, b3 = np.percentile(b, [25, 75])
    overlap = max(0.0, min(a3, b3) - max(a1, b1))
    union = max(a3, b3) - min(a1, b1)
    return float(overlap / (union + 1e-9))


def max_auc_direction(y, x):
    le = LabelEncoder()
    yy = le.fit_transform(y)
    auc = roc_auc_score(yy, x)
    return float(max(auc, 1.0 - auc))


def multiclass_single_feature_auc(y, x):
    labels = sorted(pd.Series(y).unique())
    scores = []
    for label in labels:
        yy = (pd.Series(y).to_numpy() == label).astype(int)
        if yy.min() == yy.max():
            continue
        auc = roc_auc_score(yy, x)
        scores.append(max(auc, 1.0 - auc))
    return float(np.mean(scores)) if scores else np.nan


def plot_top_feature_boxplots(matrix, sep, path):
    strict = matrix[matrix["analysis_mode"] == "strict"].copy()
    top = (
        sep[(sep["analysis_mode"] == "strict") & (sep["sample_grain"] == "file_agg") & sep["single_feature_auc_or_macro_auc"].notna()]
        .sort_values(["task_name", "single_feature_auc_or_macro_auc"], ascending=[True, False])
        .groupby("task_name")
        .head(2)
    )
    fig, axes = plt.subplots(2, 4, figsize=(18, 8))
    axes = axes.ravel()
    for ax, (_, row) in zip(axes, top.head(8).iterrows()):
        task_data, label_col = data_for_task_plot(strict, row)
        labels = sorted(task_data[label_col].dropna().unique())
        values = [task_data[task_data[label_col] == label][row["feature_name"]].dropna().to_numpy() for label in labels]
        ax.boxplot(values, tick_labels=labels, showfliers=False)
        ax.set_title(f"{row['task_name']}\n{row['feature_name']}", fontsize=9)
        ax.tick_params(axis="x", labelrotation=35)
    for ax in axes[len(top.head(8)):]:
        ax.axis("off")
    fig.suptitle("Top Feature Distributions by Task (strict, file-aggregated sample grain)")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def data_for_task_plot(data, row):
    if row["task_name"] == "Task A active vs 0Hz":
        current = data[(data["distance"] == row["distance_scope"]) & data["rpm"].isin(["0Hz", "30Hz", "50Hz"])].copy()
        current["label"] = np.where(current["rpm"] == "0Hz", "0Hz", "active")
        return current, "label"
    if row["task_name"] == "Task B 30Hz vs 50Hz":
        return data[(data["distance"] == row["distance_scope"]) & data["rpm"].isin(["30Hz", "50Hz"])].copy(), "rpm"
    if row["task_name"] == "Task C distance":
        return data[(data["rpm"] == row["rpm_scope"]) & data["distance"].isin(["2m", "3m", "5m"])].copy(), "distance"
    return data[data["rpm"].isin(["0Hz", "30Hz", "50Hz"])].copy(), "rpm"


def build_correlation_outputs(data):
    corr = data[FEATURE_COLUMNS].corr(method="spearman")
    rows = []
    used = set()
    for i, a in enumerate(FEATURE_COLUMNS):
        for b in FEATURE_COLUMNS[i + 1:]:
            value = corr.loc[a, b]
            if abs(value) > 0.9:
                keep = choose_representative(a, b, used)
                rows.append({"feature_a": a, "feature_b": b, "spearman_corr": value, "redundant_flag": True, "suggested_keep": keep, "notes": "high absolute correlation; do not auto-delete"})
                used.add(a if keep == b else b)
    return corr, pd.DataFrame(rows)


def choose_representative(a, b, used):
    if a in used:
        return b
    if b in used:
        return a
    if a.startswith("band_") and b.startswith("subband_"):
        return b
    if b.startswith("band_") and a.startswith("subband_"):
        return a
    return a


def plot_corr(corr, path):
    plt.figure(figsize=(10, 8))
    plt.imshow(corr.to_numpy(), vmin=-1, vmax=1, cmap=colormaps.get_cmap("coolwarm"))
    plt.xticks(range(len(corr.columns)), corr.columns, rotation=70, ha="right", fontsize=7)
    plt.yticks(range(len(corr.index)), corr.index, fontsize=7)
    plt.colorbar(label="Spearman correlation")
    plt.title("Feature Correlation Matrix (strict, file-aggregated)")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def build_baseline_results(file_channel, file_agg):
    rows = []
    for grain, matrix in [("file_channel", file_channel), ("file_agg", file_agg)]:
        data = matrix[matrix["analysis_mode"] == "strict"].copy()
        variants = [("all_channels", data)]
        if grain == "file_channel":
            variants.append(("without_channel9", data[data["channel"] != "channel9"].copy()))
        for feature_set, subset in variants:
            for task_name, task_data, label_col in baseline_tasks(subset):
                rows.extend(run_models(task_name, grain, feature_set, task_data, label_col))
    return pd.DataFrame(rows)


def baseline_tasks(data):
    active = data[data["rpm"].isin(["0Hz", "30Hz", "50Hz"])].copy()
    active["active_label"] = np.where(active["rpm"] == "0Hz", "0Hz", "active")
    yield "active binary 0Hz vs active", active, "active_label"
    yield "rpm three-class 0Hz/30Hz/50Hz", active, "rpm"
    yield "distance three-class 2m/3m/5m", data[data["distance"].isin(["2m", "3m", "5m"])].copy(), "distance"


def run_models(task_name, grain, feature_set, data, label_col):
    rows = []
    data = data.dropna(subset=FEATURE_COLUMNS + [label_col, "file_id"]).copy()
    if data[label_col].nunique() < 2 or data["file_id"].nunique() < 6:
        return [baseline_skip_row(task_name, grain, feature_set, "insufficient samples/classes")]
    n_splits = min(5, data["file_id"].nunique())
    counts = data[label_col].value_counts()
    if counts.min() < n_splits:
        n_splits = int(max(2, counts.min()))
    if n_splits < 2:
        return [baseline_skip_row(task_name, grain, feature_set, "insufficient per-class samples for GroupKFold")]
    models = {
        "LogisticRegression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced")),
        "RandomForest": RandomForestClassifier(n_estimators=120, random_state=42, class_weight="balanced"),
        "LinearSVM": make_pipeline(StandardScaler(), LinearSVC(class_weight="balanced", random_state=42)),
    }
    X = data[FEATURE_COLUMNS].to_numpy()
    le = LabelEncoder()
    y = le.fit_transform(data[label_col].astype(str))
    groups = data["file_id"].astype(str).to_numpy()
    cv = GroupKFold(n_splits=n_splits)
    for name, model in models.items():
        y_true = []
        y_pred = []
        scores = []
        for train_idx, test_idx in cv.split(X, y, groups):
            model.fit(X[train_idx], y[train_idx])
            pred = model.predict(X[test_idx])
            y_true.extend(y[test_idx])
            y_pred.extend(pred)
            if hasattr(model, "predict_proba"):
                scores.append(model.predict_proba(X[test_idx]))
            elif hasattr(model, "decision_function"):
                score = model.decision_function(X[test_idx])
                scores.append(score)
        auc = np.nan
        try:
            if scores:
                score_all = np.vstack([s if np.ndim(s) > 1 else np.column_stack([-s, s]) for s in scores])
                if len(le.classes_) == 2:
                    auc_raw = roc_auc_score(y_true, score_all[:, -1])
                    auc = max(auc_raw, 1 - auc_raw)
                else:
                    auc = roc_auc_score(y_true, score_all, multi_class="ovr", average="macro")
        except Exception:
            auc = np.nan
        rows.append({
            "task_name": task_name,
            "sample_grain": grain,
            "feature_set": feature_set,
            "model_name": name,
            "cv_scheme": f"GroupKFold(n_splits={n_splits}, group=file_id)",
            "accuracy": accuracy_score(y_true, y_pred),
            "macro_f1": f1_score(y_true, y_pred, average="macro"),
            "balanced_accuracy": balanced_accuracy_score(y_true, y_pred),
            "macro_auc_if_available": auc,
            "n_samples": int(len(data)),
            "n_features": len(FEATURE_COLUMNS),
            "leakage_risk_note": "Grouped by file_id; related channels from the same FFT file stay in the same fold.",
        })
    return rows


def baseline_skip_row(task_name, grain, feature_set, reason):
    return {
        "task_name": task_name,
        "sample_grain": grain,
        "feature_set": feature_set,
        "model_name": "SKIPPED",
        "cv_scheme": "GroupKFold(group=file_id)",
        "accuracy": np.nan,
        "macro_f1": np.nan,
        "balanced_accuracy": np.nan,
        "macro_auc_if_available": np.nan,
        "n_samples": 0,
        "n_features": len(FEATURE_COLUMNS),
        "leakage_risk_note": reason,
    }


def plot_confusions(file_channel, file_agg, path):
    specs = [
        ("file_channel", file_channel[file_channel["analysis_mode"] == "strict"], "rpm"),
        ("file_agg", file_agg[file_agg["analysis_mode"] == "strict"], "rpm"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, (grain, data, label_col) in zip(axes, specs):
        cm, labels = confusion_for_lr(data, label_col)
        ax.imshow(cm, cmap="Blues")
        ax.set_title(f"Logistic pilot {grain}")
        ax.set_xticks(range(len(labels)), labels, rotation=45)
        ax.set_yticks(range(len(labels)), labels)
        for i in range(len(labels)):
            for j in range(len(labels)):
                ax.text(j, i, int(cm[i, j]), ha="center", va="center")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def confusion_for_lr(data, label_col):
    data = data.dropna(subset=FEATURE_COLUMNS + [label_col, "file_id"]).copy()
    le = LabelEncoder()
    y = le.fit_transform(data[label_col].astype(str))
    X = data[FEATURE_COLUMNS].to_numpy()
    groups = data["file_id"].astype(str).to_numpy()
    n_splits = min(5, data["file_id"].nunique(), max(2, pd.Series(y).value_counts().min()))
    preds = []
    truth = []
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced"))
    for tr, te in GroupKFold(n_splits=n_splits).split(X, y, groups):
        model.fit(X[tr], y[tr])
        preds.extend(model.predict(X[te]))
        truth.extend(y[te])
    return confusion_matrix(truth, preds), le.classes_


def build_channel9_sensitivity(file_channel, file_agg):
    baseline = build_baseline_results(file_channel, file_agg)
    rows = []
    for task in baseline["task_name"].dropna().unique():
        for metric in ["accuracy", "macro_f1", "balanced_accuracy"]:
            all_value = metric_value(baseline, task, "file_channel", "all_channels", metric)
            no9_value = metric_value(baseline, task, "file_channel", "without_channel9", metric)
            agg_value = metric_value(baseline, task, "file_agg", "all_channels", metric)
            for feature_set, value in [("remove_channel9", no9_value), ("file_aggregated_median", agg_value)]:
                delta = value - all_value if pd.notna(value) and pd.notna(all_value) else np.nan
                rows.append({
                    "task_name": task,
                    "feature_set": feature_set,
                    "metric": metric,
                    "all_channels_value": all_value,
                    "without_channel9_value": no9_value,
                    "file_aggregated_value": agg_value,
                    "delta": delta,
                    "conclusion_flipped_flag": bool(abs(delta) > 0.15) if pd.notna(delta) else False,
                    "notes": "channel9 sensitivity check; no channel was removed from source data",
                })
    return pd.DataFrame(rows)


def metric_value(df, task, grain, feature_set, metric):
    current = df[(df["task_name"] == task) & (df["sample_grain"] == grain) & (df["feature_set"] == feature_set) & (df["model_name"] == "LogisticRegression")]
    return float(current[metric].iloc[0]) if not current.empty else np.nan


def build_strict_vs_all_delta(sep):
    keys = ["sample_grain", "task_name", "feature_name", "distance_scope", "rpm_scope"]
    strict = sep[sep["analysis_mode"] == "strict"][keys + ["effect_size", "single_feature_auc_or_macro_auc", "separability_rank"]]
    all_data = sep[sep["analysis_mode"] == "all_data"][keys + ["effect_size", "single_feature_auc_or_macro_auc", "separability_rank"]]
    merged = strict.merge(all_data, on=keys, suffixes=("_strict", "_all_data"), how="outer")
    merged["auc_delta_strict_minus_all"] = merged["single_feature_auc_or_macro_auc_strict"] - merged["single_feature_auc_or_macro_auc_all_data"]
    merged["effect_delta_strict_minus_all"] = merged["effect_size_strict"] - merged["effect_size_all_data"]
    merged["top_feature_changed_flag"] = merged["separability_rank_strict"].le(3) != merged["separability_rank_all_data"].le(3)
    return merged


def build_gate_summary(sep, baseline, redundancy, channel9, strict_vs_all, stability, strict_delta_input):
    rows = []
    strict_sep = sep[(sep["analysis_mode"] == "strict") & (sep["sample_grain"] == "file_agg")]
    stable = stability[stability["analysis_mode"] == "strict"]
    for feature in FEATURE_COLUMNS:
        best_auc = strict_sep[strict_sep["feature_name"] == feature]["single_feature_auc_or_macro_auc"].max()
        stable_ratio = stable[stable["feature_name"] == feature]["stable_file_ratio"].median()
        redundant = bool(((redundancy.get("feature_a", pd.Series(dtype=str)) == feature) | (redundancy.get("feature_b", pd.Series(dtype=str)) == feature)).any()) if not redundancy.empty else False
        strict_delta = strict_vs_all[strict_vs_all["feature_name"] == feature]["auc_delta_strict_minus_all"].abs().max()
        channel_risk = bool(channel9["conclusion_flipped_flag"].any()) if not channel9.empty else False
        pass_sep = bool(best_auc >= 0.75) if pd.notna(best_auc) else False
        pass_stability = bool(stable_ratio >= 0.8) if pd.notna(stable_ratio) else False
        pass_strict = bool(pd.isna(strict_delta) or strict_delta <= 0.1)
        level = "high" if pass_sep and pass_stability and pass_strict and not channel_risk and not redundant else "medium" if pass_sep and pass_stability and pass_strict else "low" if pass_sep else "reject"
        rows.append({
            "feature_name_or_feature_set": feature,
            "stable_file_ratio_pass": pass_stability,
            "separability_pass": pass_sep,
            "channel_robustness_pass": not channel_risk,
            "strict_mode_pass": pass_strict,
            "leakage_safe_pilot_pass": True,
            "ml_ready_level": level,
            "reason": f"best_auc={best_auc:.3g}; median_stable_file_ratio={stable_ratio:.3g}; redundant={redundant}; strict_auc_delta={strict_delta:.3g}",
        })
    pilot = baseline[(baseline["sample_grain"] == "file_agg") & (baseline["feature_set"] == "all_channels")]
    rows.append({
        "feature_name_or_feature_set": "all_15_features_file_agg",
        "stable_file_ratio_pass": True,
        "separability_pass": bool(pilot["balanced_accuracy"].max() >= 0.75),
        "channel_robustness_pass": not (channel9["conclusion_flipped_flag"].any() if not channel9.empty else False),
        "strict_mode_pass": True,
        "leakage_safe_pilot_pass": True,
        "ml_ready_level": "medium" if pilot["balanced_accuracy"].max() >= 0.75 else "low",
        "reason": f"best_balanced_accuracy={pilot['balanced_accuracy'].max():.3g}; GroupKFold by file_id used",
    })
    return pd.DataFrame(rows)


def write_report(output_dir, sep, baseline, redundancy, channel9, strict_vs_all, gate):
    Path("docs").mkdir(exist_ok=True)
    report = Path("docs") / "FEATURE_SEPARABILITY_V1.md"
    strict_agg = sep[(sep["analysis_mode"] == "strict") & (sep["sample_grain"] == "file_agg")]
    best_active = top_for_task(strict_agg, "Task A active vs 0Hz")
    best_rpm = top_for_task(strict_agg, "Task B 30Hz vs 50Hz")
    best_dist = top_for_task(strict_agg, "Task C distance")
    pilot_best = baseline.sort_values("balanced_accuracy", ascending=False).head(8)
    ready = gate[gate["ml_ready_level"].isin(["high", "medium"])]
    lines = [
        "# Feature Separability v1",
        "",
        "## Scope",
        "",
        "- Used Feature Extraction v2 outputs only.",
        "- Did not extract new features, rerun TDMS/FFT, modify background contrast, or train final ML models.",
        "- Pilot models are pre-ML gates using GroupKFold by `file_id` to reduce leakage.",
        "",
        "## Current separability answer",
        "",
        f"- Medium/high ML-ready candidates or feature sets: {len(ready)}.",
        f"- Current decision: {'can enter pilot ML feature table construction with strict-mode filtering and risk flags' if len(ready) else 'not ready for ML feature table construction'}.",
        "",
        "## Best single features",
        "",
        "Active vs 0Hz:",
    ]
    lines.extend(format_best(best_active))
    lines.append("")
    lines.append("30Hz vs 50Hz:")
    lines.extend(format_best(best_rpm))
    lines.append("")
    lines.append("2m/3m/5m distance:")
    lines.extend(format_best(best_dist))
    lines.extend([
        "",
        "## Feature type pattern",
        "",
        "- Broad bands, subbands, and peak windows are all evaluated in the same strict file-aggregated matrix.",
        "- Highly redundant feature pairs are listed in `feature_redundancy_summary.csv`; no feature was automatically deleted.",
        "",
        "## Pilot baseline",
        "",
    ])
    for row in pilot_best.itertuples():
        lines.append(f"- `{row.task_name}` `{row.sample_grain}` `{row.model_name}`: balanced_accuracy={row.balanced_accuracy:.3g}, macro_f1={row.macro_f1:.3g}")
    lines.extend([
        "",
        "## Channel9 sensitivity",
        "",
        f"- Sensitivity rows with conclusion flip: {int(channel9['conclusion_flipped_flag'].sum()) if not channel9.empty else 0}.",
        "- Removing channel9 is reported as a sensitivity condition only; source data are unchanged.",
        "",
        "## Strict vs all-data",
        "",
        f"- Top-feature changed flags: {int(strict_vs_all['top_feature_changed_flag'].fillna(False).sum())}.",
        "- See `strict_vs_all_separability_delta.csv` for AUC/effect-size shifts from excluding frequency-axis-risk files.",
        "",
        "## Gate",
        "",
    ])
    for row in gate.sort_values("ml_ready_level").itertuples():
        lines.append(f"- `{row.feature_name_or_feature_set}`: {row.ml_ready_level}; {row.reason}")
    lines.extend([
        "",
        "## Blocking risks",
        "",
        "- Pilot results are not final identification results.",
        "- Frequency-axis-risk files should stay excluded for strict-mode ML inputs or retained only with explicit `qc_flag` filtering.",
        "- If performance appears only at file-channel grain and not file-aggregated grain, treat it as possible channel-level artifact.",
    ])
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def top_for_task(df, task):
    return df[df["task_name"] == task].sort_values("single_feature_auc_or_macro_auc", ascending=False).head(5)


def format_best(df):
    if df.empty:
        return ["- No valid rows."]
    return [f"- `{r.feature_name}` ({r.distance_scope}, {r.rpm_scope}): AUC={r.single_feature_auc_or_macro_auc:.3g}, effect={r.effect_size:.3g}" for r in df.itertuples()]


if __name__ == "__main__":
    main()
