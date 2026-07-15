import argparse
import json
import math
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.signal import find_peaks
from scipy.stats import kruskal
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import LabelEncoder


CHANNELS = [f"channel{i}" for i in range(1, 13)]
LAG_FEATURES = [1, 2, 5, 10, 20, 50, 100]
INTEGRAL_WINDOWS = [
    ("acf_abs_integral_0_0p1ms", 0.0, 0.0001),
    ("acf_abs_integral_0p1_0p5ms", 0.0001, 0.0005),
    ("acf_abs_integral_0p5_1ms", 0.0005, 0.001),
    ("acf_abs_integral_1_5ms", 0.001, 0.005),
    ("acf_abs_integral_5_20ms", 0.005, 0.020),
    ("acf_abs_integral_20_50ms", 0.020, 0.050),
]
NEAR_FREQS = [("54k", 54_000.0), ("138k", 138_000.0), ("178k", 178_000.0)]
EPS = 1e-30


def main(argv=None):
    parser = argparse.ArgumentParser(description="ACF Feature Analysis v1 from time CSV files.")
    parser.add_argument("--time-root", default="D:/Lab/process/26.5.12/time")
    parser.add_argument("--output", default="analysis_out/acf_features_v1")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--max-lag-sec", type=float, default=0.05)
    parser.add_argument("--preprocessing-mode", choices=["ac_centered", "ac_detrended"], default="ac_centered")
    args = parser.parse_args(argv)

    time_root = Path(args.time_root)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset_path = output_dir / "acf_feature_dataset_v1.csv"
    if args.force or not dataset_path.exists():
        dataset, audit = extract_acf_dataset(time_root, args.max_lag_sec, args.preprocessing_mode)
        dataset.to_csv(dataset_path, index=False, encoding="utf-8-sig")
        write_json(output_dir / "acf_feature_input_audit_v1.json", audit)
    else:
        dataset = pd.read_csv(dataset_path)
        audit = read_json(output_dir / "acf_feature_input_audit_v1.json")

    stability = build_stability_summary(dataset)
    stability.to_csv(output_dir / "acf_feature_stability_summary_v1.csv", index=False, encoding="utf-8-sig")
    write_schema(output_dir / "acf_feature_schema_v1.json")
    write_run_config(output_dir / "acf_feature_run_config_v1.json", time_root, args.max_lag_sec, args.preprocessing_mode)

    file_channel, file_agg = build_matrices(dataset)
    file_channel.to_csv(output_dir / "acf_feature_matrix_file_channel_v1.csv", index=False, encoding="utf-8-sig")
    file_agg.to_csv(output_dir / "acf_feature_matrix_file_agg_v1.csv", index=False, encoding="utf-8-sig")

    sep = build_separability(file_channel, file_agg)
    sep.to_csv(output_dir / "acf_feature_separability_summary_v1.csv", index=False, encoding="utf-8-sig")

    corr, redundancy = build_redundancy(file_agg)
    corr.to_csv(output_dir / "acf_feature_correlation_matrix_v1.csv", encoding="utf-8-sig")
    redundancy.to_csv(output_dir / "acf_feature_redundancy_summary_v1.csv", index=False, encoding="utf-8-sig")

    comparison = compare_with_existing(sep)
    comparison.to_csv(output_dir / "acf_vs_existing_feature_comparison_v1.csv", index=False, encoding="utf-8-sig")

    roles = build_role_assignment(sep, redundancy)
    roles.to_csv(output_dir / "acf_feature_role_assignment_v1.csv", index=False, encoding="utf-8-sig")
    feature_sets = build_feature_sets(roles)
    write_json(output_dir / "recommended_acf_feature_sets_v1.json", feature_sets)
    maybe_write_combined_sets(output_dir, feature_sets)
    plot_top_auc(sep, output_dir / "acf_top_auc_bar_v1.png")
    write_report(output_dir, time_root, audit, dataset, sep, comparison, roles, feature_sets, args.max_lag_sec, args.preprocessing_mode)
    print(f"ACF Feature Analysis v1 output: {output_dir}")
    return output_dir


def extract_acf_dataset(time_root, max_lag_sec, preprocessing_mode):
    rows = []
    audit = {"time_root": str(time_root), "groups": {}, "warnings": [], "preprocessing_mode": preprocessing_mode}
    group_dirs = [p for p in sorted(time_root.iterdir()) if p.is_dir() and parse_group(p.name)]
    for group_dir in group_dirs:
        group = group_dir.name
        parsed = parse_group(group)
        files = sorted(group_dir.glob("*.csv"))
        audit["groups"][group] = {"file_count": len(files), "files": []}
        for path in files:
            file_rows, file_audit = process_file(path, group, parsed, max_lag_sec, preprocessing_mode)
            rows.extend(file_rows)
            audit["groups"][group]["files"].append(file_audit)
            if file_audit["qc_warnings"]:
                audit["warnings"].append({"group": group, "file": path.name, "warnings": file_audit["qc_warnings"]})
    return pd.DataFrame(rows), audit


def process_file(path, group, parsed, max_lag_sec, preprocessing_mode):
    df = pd.read_csv(path)
    channels = [c for c in CHANNELS if c in df.columns]
    time = df["time"].astype(float).to_numpy()
    sr, duration, time_warnings = sampling_info(time)
    max_lag_samples = int(round(max_lag_sec * sr)) if np.isfinite(sr) and sr > 0 else 0
    max_lag_samples = max(1, min(max_lag_samples, len(df) - 1))
    file_audit = {
        "group": group,
        "file": path.name,
        "channels": channels,
        "missing_channels": [c for c in CHANNELS if c not in channels],
        "n_samples": int(len(df)),
        "duration_seconds": duration,
        "sampling_rate_hz": sr,
        "max_lag_samples": max_lag_samples,
        "max_lag_seconds": float(max_lag_samples / sr) if sr else np.nan,
        "preprocessing_mode": preprocessing_mode,
        "qc_warnings": list(time_warnings),
        "nan_or_inf_channels": [],
        "constant_channels": [],
        "acf_failed_channels": [],
    }
    data = df[channels].astype(float).to_numpy()
    rows = []
    for idx, channel in enumerate(channels):
        x = data[:, idx]
        qc = list(time_warnings)
        if not np.isfinite(x).all():
            qc.append("nan_or_inf_filtered")
            file_audit["nan_or_inf_channels"].append(channel)
            valid = np.isfinite(x)
            x = x[valid]
            t = time[valid]
        else:
            t = time
        if len(x) < max_lag_samples + 2:
            qc.append("too_short")
        if np.nanstd(x) <= EPS:
            qc.append("constant_signal")
            file_audit["constant_channels"].append(channel)
        try:
            acf = compute_acf(x, t, max_lag_samples, preprocessing_mode)
            features = acf_features(acf, sr, max_lag_samples, max_lag_sec)
        except Exception as exc:
            qc.append("acf_failed")
            file_audit["acf_failed_channels"].append({"channel": channel, "error": str(exc)})
            features = empty_features(sr, max_lag_samples, max_lag_sec)
        for name, meta in features.items():
            rows.append({
                "sample_id": f"{group}__{path.stem}__{channel}",
                "group": group,
                "distance": parsed["distance"],
                "rpm": parsed["rpm"],
                "file_id": path.name,
                "channel": channel,
                "feature_domain": "acf",
                "feature_name": name,
                "feature_value": meta["value"],
                "feature_type": meta["feature_type"],
                "unit": meta["unit"],
                "qc_flag": ";".join(sorted(set(qc))) if qc else "OK",
                "n_samples": int(len(x)),
                "duration_seconds": duration,
                "sampling_rate_hz": sr,
                "max_lag_samples": max_lag_samples,
                "max_lag_seconds": float(max_lag_samples / sr) if sr else np.nan,
                "preprocessing_mode": preprocessing_mode,
                "notes": meta.get("notes", ""),
            })
    if file_audit["nan_or_inf_channels"]:
        file_audit["qc_warnings"].append("nan_or_inf")
    if file_audit["constant_channels"]:
        file_audit["qc_warnings"].append("constant_signal")
    if file_audit["acf_failed_channels"]:
        file_audit["qc_warnings"].append("acf_failed")
    return rows, file_audit


def compute_acf(x, time, max_lag_samples, preprocessing_mode):
    x = np.asarray(x, dtype=float)
    if preprocessing_mode == "ac_detrended" and len(x) > 2:
        slope = np.polyfit(time - time[0], x, 1)[0]
        x = x - slope * (time - time[0])
    x = x - np.mean(x)
    n = len(x)
    nfft = 1 << (2 * n - 1).bit_length()
    spec = np.fft.rfft(x, n=nfft)
    acf = np.fft.irfft(spec * np.conjugate(spec), n=nfft)[: max_lag_samples + 1]
    if abs(acf[0]) <= EPS:
        out = np.full(max_lag_samples + 1, np.nan)
        out[0] = 1.0
        return out
    acf = acf / acf[0]
    acf[0] = 1.0
    return acf


def acf_features(acf, sr, max_lag_samples, max_lag_sec):
    out = {}
    def add(name, value, feature_type, unit="unitless", notes=""):
        out[name] = {"value": value, "feature_type": feature_type, "unit": unit, "notes": notes}

    for lag in LAG_FEATURES:
        add(f"acf_lag{lag}", value_at(acf, lag), "short_lag")
    for name, start, end in INTEGRAL_WINDOWS:
        start_lag = int(round(start * sr))
        end_lag = int(round(end * sr))
        if end_lag > max_lag_samples:
            add(name, np.nan, "integral_strength", "s", "skipped: max_lag_sec does not cover this window")
        else:
            add(name, float(np.sum(np.abs(acf[start_lag:end_lag + 1])) / sr), "integral_strength", "s")
    add_decay_features(add, acf, sr)
    add_peak_features(add, acf, sr)
    for label, freq in NEAR_FREQS:
        lag = int(round(sr / freq))
        add(f"acf_near_{label}_lag", lag, "high_frequency_near_lag", "samples", "approximate nearest-sample lag feature")
        add(f"acf_near_{label}_value", value_at(acf, lag), "high_frequency_near_lag", "unitless", "approximate nearest-sample lag feature; high-frequency warning")
    short = float(np.sum(acf[1:min(len(acf), 101)] ** 2))
    long_start = int(round(0.005 * sr))
    long_end = min(len(acf) - 1, int(round(0.05 * sr)))
    long = float(np.sum(acf[long_start:long_end + 1] ** 2)) if long_end > long_start else np.nan
    nonrandom = float(short + (0.1 * long if np.isfinite(long) else 0.0))
    add("acf_nonrandomness_score", nonrandom, "randomness")
    add("acf_short_lag_energy", short, "randomness")
    add("acf_long_lag_energy", long, "randomness")
    add("acf_long_short_ratio", float(long / (short + EPS)) if np.isfinite(long) else np.nan, "randomness")
    return out


def add_decay_features(add, acf, sr):
    zero = first_condition(acf, lambda arr: arr <= 0, start=1, consecutive=1)
    below = first_condition(acf, lambda arr: arr < 0.1, start=1, consecutive=5)
    efold = first_condition(acf, lambda arr: arr < 1 / math.e, start=1, consecutive=5)
    add("acf_first_zero_cross_lag", zero, "decay", "samples")
    add("acf_first_zero_cross_time_sec", lag_time(zero, sr), "decay", "s")
    add("acf_first_below_0p1_lag", below, "decay", "samples")
    add("acf_first_below_0p1_time_sec", lag_time(below, sr), "decay", "s")
    add("acf_efold_lag", efold, "decay", "samples")
    add("acf_efold_time_sec", lag_time(efold, sr), "decay", "s")


def add_peak_features(add, acf, sr):
    peaks, props = find_peaks(acf[1:], height=0.0)
    peaks = peaks + 1
    if len(peaks):
        values = acf[peaks]
        first = int(peaks[0])
        max_idx = int(np.argmax(values))
        max_lag = int(peaks[max_idx])
        above_02 = int(np.sum(values > 0.2))
        above_01 = int(np.sum(values > 0.1))
        spacing = np.diff(peaks)
        spacing_cv = float(np.std(spacing) / (np.mean(spacing) + EPS)) if len(spacing) > 1 else np.nan
        periodicity = float(np.max(values) * above_01 / (1.0 + (spacing_cv if np.isfinite(spacing_cv) else 1.0)))
        first_val = float(acf[first])
        max_val = float(acf[max_lag])
    else:
        first = max_lag = np.nan
        first_val = max_val = np.nan
        above_02 = above_01 = 0
        spacing_cv = periodicity = np.nan
    add("acf_first_peak_lag", first, "peak_periodicity", "samples")
    add("acf_first_peak_time_sec", lag_time(first, sr), "peak_periodicity", "s")
    add("acf_first_peak_value", first_val, "peak_periodicity")
    add("acf_max_peak_lag", max_lag, "peak_periodicity", "samples")
    add("acf_max_peak_time_sec", lag_time(max_lag, sr), "peak_periodicity", "s")
    add("acf_max_peak_value", max_val, "peak_periodicity")
    add("acf_peak_count_above_0p2", above_02, "peak_periodicity", "count")
    add("acf_peak_count_above_0p1", above_01, "peak_periodicity", "count")
    add("acf_peak_spacing_cv", spacing_cv, "peak_periodicity")
    add("acf_periodicity_score", periodicity, "peak_periodicity")


def value_at(acf, lag):
    return float(acf[lag]) if lag < len(acf) else np.nan


def lag_time(lag, sr):
    return float(lag / sr) if pd.notna(lag) and np.isfinite(lag) and sr else np.nan


def first_condition(acf, predicate, start=1, consecutive=1):
    arr = predicate(acf)
    for idx in range(start, len(arr) - consecutive + 1):
        if np.all(arr[idx:idx + consecutive]):
            return int(idx)
    return np.nan


def empty_features(sr, max_lag_samples, max_lag_sec):
    return {name: {"value": np.nan, "feature_type": "UNKNOWN", "unit": "UNKNOWN", "notes": "acf_failed"} for name in all_feature_names()}


def all_feature_names():
    names = [f"acf_lag{x}" for x in LAG_FEATURES]
    names += [x[0] for x in INTEGRAL_WINDOWS]
    names += [
        "acf_first_zero_cross_lag", "acf_first_zero_cross_time_sec",
        "acf_first_below_0p1_lag", "acf_first_below_0p1_time_sec",
        "acf_efold_lag", "acf_efold_time_sec",
        "acf_first_peak_lag", "acf_first_peak_time_sec", "acf_first_peak_value",
        "acf_max_peak_lag", "acf_max_peak_time_sec", "acf_max_peak_value",
        "acf_peak_count_above_0p2", "acf_peak_count_above_0p1", "acf_peak_spacing_cv", "acf_periodicity_score",
    ]
    for label, _ in NEAR_FREQS:
        names += [f"acf_near_{label}_lag", f"acf_near_{label}_value"]
    names += ["acf_nonrandomness_score", "acf_short_lag_energy", "acf_long_lag_energy", "acf_long_short_ratio"]
    return names


def build_stability_summary(dataset):
    rows = []
    data = dataset[pd.to_numeric(dataset["feature_value"], errors="coerce").notna()].copy()
    data["feature_value"] = data["feature_value"].astype(float)
    for keys, group in data.groupby(["group", "distance", "rpm", "channel", "feature_name", "feature_type"]):
        values = group["feature_value"]
        median = float(values.median())
        mad = float(np.median(np.abs(values - median)))
        stable = np.abs(values - median) <= 3.0 * (1.4826 * mad + EPS)
        rows.append({
            "group": keys[0], "distance": keys[1], "rpm": keys[2], "channel": keys[3],
            "feature_name": keys[4], "feature_type": keys[5],
            "median": median, "mean": float(values.mean()),
            "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
            "iqr": float(values.quantile(0.75) - values.quantile(0.25)),
            "p10": float(values.quantile(0.10)), "p90": float(values.quantile(0.90)),
            "cv": float(values.std(ddof=1) / (abs(values.mean()) + EPS)) if len(values) > 1 else 0.0,
            "stable_file_ratio": float(stable.mean()),
            "outlier_file_count": int((~stable).sum()),
            "valid_file_count": int(len(values)),
            "qc_warning_count": int((group["qc_flag"].astype(str) != "OK").sum()),
        })
    return pd.DataFrame(rows)


def build_matrices(dataset):
    id_cols = ["sample_id", "group", "distance", "rpm", "file_id", "channel"]
    fc = dataset.pivot_table(index=id_cols, columns="feature_name", values="feature_value", aggfunc="median").reset_index()
    fc.columns.name = None
    qc = dataset.groupby(id_cols, as_index=False)["qc_flag"].agg(join_qc)
    fc = fc.merge(qc, on=id_cols, how="left")
    agg = dataset.groupby(["group", "distance", "rpm", "file_id", "feature_name"], as_index=False).agg(feature_value=("feature_value", "median"), qc_flag=("qc_flag", join_qc))
    fa = agg.pivot_table(index=["group", "distance", "rpm", "file_id"], columns="feature_name", values="feature_value", aggfunc="median").reset_index()
    fa.columns.name = None
    qc2 = agg.groupby(["group", "distance", "rpm", "file_id"], as_index=False)["qc_flag"].agg(join_qc)
    fa = fa.merge(qc2, on=["group", "distance", "rpm", "file_id"], how="left")
    fa["channel"] = "aggregated_median"
    fa["sample_id"] = fa["group"] + "__" + fa["file_id"].str.replace(".csv", "", regex=False) + "__aggregated_median"
    front = ["sample_id", "group", "distance", "rpm", "file_id", "channel"]
    features = sorted([c for c in fa.columns if c.startswith("acf_")])
    return fc[front + sorted([c for c in fc.columns if c.startswith("acf_")]) + ["qc_flag"]], fa[front + features + ["qc_flag"]]


def join_qc(values):
    unique = sorted(set(str(v) for v in values if pd.notna(v)))
    return ";".join(unique) if unique else "OK"


def build_separability(file_channel, file_agg):
    rows = []
    for grain, matrix in [("file_channel", file_channel), ("file_agg", file_agg)]:
        rows.extend(task_rows(matrix, grain))
    out = pd.DataFrame(rows)
    if not out.empty:
        out["separability_rank"] = out.groupby(["sample_grain", "task_name"])["single_feature_auc_or_macro_auc"].rank(ascending=False, method="min")
    return out


def task_rows(matrix, grain):
    rows = []
    for distance, group in matrix.groupby("distance"):
        current = group[group["rpm"].isin(["0Hz", "30Hz", "50Hz"])].copy()
        current["label"] = np.where(current["rpm"] == "0Hz", "0Hz", "active")
        rows.extend(feature_rows(current, grain, "Task A active vs 0Hz", distance, "all", "label"))
        current = group[group["rpm"].isin(["30Hz", "50Hz"])].copy()
        rows.extend(feature_rows(current, grain, "Task B 30Hz vs 50Hz", distance, "30/50Hz", "rpm"))
    for rpm, group in matrix.groupby("rpm"):
        current = group[group["distance"].isin(["2m", "3m", "5m"])].copy()
        rows.extend(feature_rows(current, grain, "Task C distance", "2/3/5m", rpm, "distance"))
    rows.extend(feature_rows(matrix[matrix["rpm"].isin(["0Hz", "30Hz", "50Hz"])].copy(), grain, "Task D rpm 3-class", "all", "0/30/50Hz", "rpm"))
    return rows


def feature_rows(data, grain, task_name, distance_scope, rpm_scope, label_col):
    rows = []
    labels = sorted(data[label_col].dropna().unique().tolist()) if label_col in data else []
    features = [c for c in data.columns if c.startswith("acf_")]
    for feature in features:
        current = data[[feature, label_col]].dropna()
        row = {
            "task_name": task_name, "sample_grain": grain, "feature_domain": "acf",
            "feature_name": feature, "feature_type": acf_feature_type(feature),
            "distance_scope": distance_scope, "rpm_scope": rpm_scope,
            "n_samples": int(len(current)), "class_labels": json.dumps(labels),
            "median_by_class": "{}", "iqr_by_class": "{}", "effect_size": np.nan,
            "overlap_score": np.nan, "single_feature_auc_or_macro_auc": np.nan,
            "separability_rank": np.nan, "qc_warning": "", "notes": acf_feature_warning(feature),
            "skipped_reason": "",
        }
        counts = current[label_col].value_counts() if label_col in current else pd.Series(dtype=int)
        if len(counts) < 2 or counts.min() < 3:
            row["skipped_reason"] = "need at least 2 classes and 3 samples per class"
            rows.append(row)
            continue
        x = current[feature].astype(float)
        y = current[label_col].astype(str)
        med = current.groupby(label_col)[feature].median().to_dict()
        iqr = (current.groupby(label_col)[feature].quantile(0.75) - current.groupby(label_col)[feature].quantile(0.25)).to_dict()
        row["median_by_class"] = json.dumps({str(k): float(v) for k, v in med.items()})
        row["iqr_by_class"] = json.dumps({str(k): float(v) for k, v in iqr.items()})
        if len(counts) == 2:
            labs = sorted(counts.index.astype(str).tolist())
            a = x[y == labs[0]]
            b = x[y == labs[1]]
            row["effect_size"] = robust_effect(a, b)
            row["overlap_score"] = overlap_score(a, b)
            row["single_feature_auc_or_macro_auc"] = max_auc(y, x)
        else:
            values = [x[y == str(label)] for label in sorted(counts.index.astype(str).tolist())]
            try:
                stat, _ = kruskal(*values)
                row["effect_size"] = float(stat / max(len(x) - 1, 1))
            except Exception:
                pass
            row["single_feature_auc_or_macro_auc"] = macro_auc(y, x)
        rows.append(row)
    return rows


def robust_effect(a, b):
    spread = ((np.percentile(a, 75) - np.percentile(a, 25)) + (np.percentile(b, 75) - np.percentile(b, 25))) / 2
    return float((np.median(b) - np.median(a)) / (spread + EPS))


def overlap_score(a, b):
    a1, a3 = np.percentile(a, [25, 75])
    b1, b3 = np.percentile(b, [25, 75])
    return float(max(0, min(a3, b3) - max(a1, b1)) / (max(a3, b3) - min(a1, b1) + EPS))


def max_auc(y, x):
    yy = LabelEncoder().fit_transform(y)
    auc = roc_auc_score(yy, x)
    return float(max(auc, 1 - auc))


def macro_auc(y, x):
    labels = sorted(pd.Series(y).unique())
    scores = []
    for label in labels:
        yy = (pd.Series(y).to_numpy() == label).astype(int)
        if yy.min() != yy.max():
            auc = roc_auc_score(yy, x)
            scores.append(max(auc, 1 - auc))
    return float(np.mean(scores)) if scores else np.nan


def build_redundancy(file_agg):
    features = [c for c in file_agg.columns if c.startswith("acf_")]
    corr = file_agg[features].corr(method="spearman")
    rows = []
    for i, a in enumerate(features):
        for b in features[i + 1:]:
            val = corr.loc[a, b]
            if abs(val) > 0.9:
                rows.append({"feature_a": a, "feature_b": b, "spearman_corr": val, "redundant_flag": True, "suggested_keep": suggest_keep(a, b), "notes": "high absolute correlation; do not auto-delete"})
    return corr, pd.DataFrame(rows)


def suggest_keep(a, b):
    if "near_" in a and "near_" not in b:
        return b
    if "near_" in b and "near_" not in a:
        return a
    if "lag" in a and "integral" in b:
        return b
    return a


def compare_with_existing(acf_sep):
    path = Path("analysis_out/time_frequency_feature_comparison_v1/combined_feature_separability_summary.csv")
    if not path.exists():
        return pd.DataFrame([{"skipped_reason": "existing time+frequency comparison not found"}])
    existing = pd.read_csv(path)
    rows = []
    acf = acf_sep[(acf_sep["sample_grain"] == "file_agg") & acf_sep["single_feature_auc_or_macro_auc"].notna()]
    ex = existing[(existing["sample_grain"] == "file_agg") & existing["single_feature_auc_or_macro_auc"].notna()]
    for task in sorted(set(acf["task_name"]) | set(ex["task_name"])):
        freq = ex[(ex["task_name"] == task) & (ex["feature_domain"] == "frequency")].sort_values("single_feature_auc_or_macro_auc", ascending=False)
        time = ex[(ex["task_name"] == task) & (ex["feature_domain"] == "time")].sort_values("single_feature_auc_or_macro_auc", ascending=False)
        a = acf[acf["task_name"] == task].sort_values("single_feature_auc_or_macro_auc", ascending=False)
        best_acf = float(a["single_feature_auc_or_macro_auc"].iloc[0]) if not a.empty else np.nan
        best_freq = float(freq["single_feature_auc_or_macro_auc"].iloc[0]) if not freq.empty else np.nan
        best_time = float(time["single_feature_auc_or_macro_auc"].iloc[0]) if not time.empty else np.nan
        value = "low"
        reason = "ACF below existing feature domains or below 0.75 AUC gate"
        if pd.notna(best_acf) and best_acf >= 0.75 and best_acf >= max(best_freq, best_time) - 0.03:
            value = "high"
            reason = "ACF top AUC close to existing top domains"
        elif pd.notna(best_acf) and best_acf >= 0.75:
            value = "medium"
            reason = "ACF has standalone separability"
        rows.append({
            "task_name": task,
            "best_frequency_auc": best_freq,
            "best_time_auc": best_time,
            "best_acf_auc": best_acf,
            "best_frequency_feature": freq["feature_name"].iloc[0] if not freq.empty else "",
            "best_time_feature": time["feature_name"].iloc[0] if not time.empty else "",
            "best_acf_feature": a["feature_name"].iloc[0] if not a.empty else "",
            "acf_additional_value": value,
            "reason": reason,
        })
    return pd.DataFrame(rows)


def build_role_assignment(sep, redundancy):
    redundant = set(redundancy["feature_a"].tolist() + redundancy["feature_b"].tolist()) if not redundancy.empty else set()
    rows = []
    for feature, group in sep.groupby("feature_name"):
        best = group.sort_values("single_feature_auc_or_macro_auc", ascending=False).head(1).iloc[0]
        warning = "near_" in feature
        qc = acf_feature_type(feature) in {"randomness", "decay"} or "integral_20_50ms" in feature
        role = "auxiliary_candidate"
        if qc:
            role = "qc_only"
        if best.single_feature_auc_or_macro_auc < 0.65:
            role = "reject"
        if warning and role == "auxiliary_candidate":
            role = "auxiliary_candidate"
        if feature in redundant and role == "auxiliary_candidate":
            role = "auxiliary_candidate"
        rows.append({
            "feature_name": feature,
            "feature_type": acf_feature_type(feature),
            "best_task": best.task_name,
            "best_auc": best.single_feature_auc_or_macro_auc,
            "best_effect_size": best.effect_size,
            "redundancy_level": "high" if feature in redundant else "low",
            "high_frequency_lag_warning": bool(warning),
            "qc_role_flag": bool(qc),
            "recommended_role": role,
            "reason": role_reason(role, warning, qc, feature in redundant),
        })
    return pd.DataFrame(rows)


def acf_feature_type(feature):
    if feature.startswith("acf_lag"):
        return "short_lag"
    if "integral" in feature:
        return "integral_strength"
    if "below" in feature or "zero" in feature or "efold" in feature:
        return "decay"
    if "peak" in feature or "periodicity" in feature:
        return "peak_periodicity"
    if "near_" in feature:
        return "high_frequency_near_lag"
    if "random" in feature or "energy" in feature or "ratio" in feature:
        return "randomness"
    return "acf"


def acf_feature_warning(feature):
    return "approximate nearest-sample lag; high-frequency interpretation warning" if "near_" in feature else ""


def role_reason(role, warning, qc, redundant):
    parts = [f"role={role}"]
    if warning:
        parts.append("high-frequency nearest-sample lag warning")
    if qc:
        parts.append("QC/randomness/stability oriented")
    if redundant:
        parts.append("high redundancy")
    return "; ".join(parts)


def build_feature_sets(roles):
    return {
        "acf_auxiliary": roles[roles["recommended_role"] == "auxiliary_candidate"]["feature_name"].tolist(),
        "acf_qc_features": roles[roles["recommended_role"] == "qc_only"]["feature_name"].tolist(),
        "acf_rejected": roles[roles["recommended_role"] == "reject"]["feature_name"].tolist(),
        "acf_high_frequency_warning_features": roles[roles["high_frequency_lag_warning"]]["feature_name"].tolist(),
    }


def maybe_write_combined_sets(output_dir, acf_sets):
    path = Path("analysis_out/time_frequency_feature_comparison_v1/recommended_feature_sets_v1.json")
    if not path.exists():
        return
    base = read_json(path)
    combined = dict(base)
    combined["acf_auxiliary"] = acf_sets["acf_auxiliary"]
    combined["combined_nonredundant_with_acf"] = base.get("combined_nonredundant", []) + acf_sets["acf_auxiliary"]
    combined["qc_features"] = base.get("qc_features", []) + acf_sets["acf_qc_features"]
    write_json(output_dir / "recommended_feature_sets_with_acf_v1.json", combined)


def plot_top_auc(sep, path):
    data = sep[(sep["sample_grain"] == "file_agg") & sep["single_feature_auc_or_macro_auc"].notna()]
    top = data.sort_values("single_feature_auc_or_macro_auc", ascending=False).groupby("task_name").head(1)
    plt.figure(figsize=(9, 4))
    plt.bar(top["task_name"], top["single_feature_auc_or_macro_auc"])
    plt.xticks(rotation=30, ha="right")
    plt.ylabel("Top ACF AUC")
    plt.title("Top ACF Feature AUC by Task")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def write_schema(path):
    write_json(path, {
        "feature_domain": "acf",
        "feature_names": all_feature_names(),
        "common_keys": ["group", "distance", "rpm", "file_id", "channel"],
        "acf_normalization": "acf[0] = 1",
        "default_preprocessing": "ac_centered",
    })


def write_run_config(path, time_root, max_lag_sec, preprocessing_mode):
    write_json(path, {
        "time_root": str(time_root),
        "max_lag_sec": max_lag_sec,
        "preprocessing_mode": preprocessing_mode,
        "acf_method": "FFT-based autocorrelation per file/channel",
        "normalization": "divide by lag-0 autocorrelation so acf[0]=1",
        "first_below_threshold_consecutive_lags": 5,
        "periodicity_score": "max_peak_value * peak_count_above_0p1 / (1 + peak_spacing_cv)",
    })


def write_report(output_dir, time_root, audit, dataset, sep, comparison, roles, feature_sets, max_lag_sec, preprocessing_mode):
    Path("docs").mkdir(exist_ok=True)
    report = Path("docs") / "ACF_FEATURE_ANALYSIS_V1.md"
    top = sep[(sep["sample_grain"] == "file_agg") & sep["single_feature_auc_or_macro_auc"].notna()].sort_values("single_feature_auc_or_macro_auc", ascending=False).head(8)
    role_counts = roles["recommended_role"].value_counts().to_dict()
    comp_lines = []
    if "acf_additional_value" in comparison.columns:
        for row in comparison.itertuples():
            comp_lines.append(f"- `{row.task_name}`: best_acf_auc={row.best_acf_auc:.3g}, additional_value={row.acf_additional_value}; best_acf={row.best_acf_feature}")
    lines = [
        "# ACF Feature Analysis v1",
        "",
        "## Purpose",
        "",
        "PSD describes frequency energy, time-domain statistics describe amplitude/distribution, and ACF describes temporal correlation structure and non-randomness.",
        "",
        "## Inputs",
        "",
        f"- Time CSV root: `{time_root}`",
        f"- Groups read: {', '.join(sorted(audit.get('groups', {}).keys(), key=group_sort_key))}",
        "",
        "## ACF calculation",
        "",
        f"- Preprocessing: `{preprocessing_mode}`.",
        f"- Max lag: `{max_lag_sec}` seconds.",
        "- ACF is computed from mean-centered signal using FFT-based autocorrelation.",
        "- ACF is normalized so `acf[0] = 1`.",
        "- Default sampling rate is read from each time CSV, approximately 400 kHz.",
        "",
        "## Extracted ACF features",
        "",
        "- Short-lag ACF values.",
        "- Absolute ACF integrals across fixed time windows.",
        "- Decay/decorrelation lag and time features.",
        "- Peak/periodicity features.",
        "- Approximate nearest-sample lag features for 54k/138k/178k.",
        "- Nonrandomness, short-lag energy, long-lag energy, and long/short ratio.",
        "",
        "## High-frequency lag limitation",
        "",
        "- 54k/138k/178k periods correspond to only a few samples at ~400 kHz.",
        "- `acf_near_54k`, `acf_near_138k`, and `acf_near_178k` features are auxiliary diagnostics only, not proof of stable physical frequency peaks.",
        "",
        "## Separability",
        "",
    ]
    for row in top.itertuples():
        lines.append(f"- `{row.feature_name}` `{row.task_name}`: AUC={row.single_feature_auc_or_macro_auc:.3g}, effect={row.effect_size:.3g}")
    lines.extend([
        "",
        "## ACF vs existing PSD/time features",
        "",
        *comp_lines,
        "",
        "## Roles",
        "",
        f"- Role counts: {role_counts}",
        f"- ACF auxiliary: {feature_sets['acf_auxiliary']}",
        f"- ACF QC features: {feature_sets['acf_qc_features']}",
        f"- ACF rejected: {feature_sets['acf_rejected']}",
        "",
        "## Scope guard",
        "",
        "- No machine learning was run.",
        "- No large plot set was generated.",
        "- No FFT or background contrast outputs were modified.",
        "- ACF high AUC is not interpreted as a physical mechanism.",
    ])
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def sampling_info(time):
    if len(time) < 2:
        return np.nan, np.nan, ["too_short", "invalid_sampling_rate"]
    dt = float(np.median(np.diff(time)))
    sr = 1.0 / dt if dt > 0 else np.nan
    duration = float(time[-1] - time[0])
    warnings = []
    if not np.isfinite(sr):
        warnings.append("invalid_sampling_rate")
    return sr, duration, warnings


def parse_group(group):
    match = re.fullmatch(r"(\d+(?:\.\d+)?)m(\d+(?:\.\d+)?)hz", str(group))
    if not match:
        return None
    distance = float(match.group(1))
    rpm = float(match.group(2))
    return {"distance": f"{int(distance)}m" if distance.is_integer() else f"{distance:g}m", "rpm": f"{int(rpm)}Hz" if rpm.is_integer() else f"{rpm:g}Hz"}


def group_sort_key(group):
    parsed = parse_group(group)
    if parsed is None:
        return (999, 999)
    return (float(parsed["distance"].replace("m", "")), float(parsed["rpm"].replace("Hz", "")))


def read_json(path):
    if not Path(path).exists():
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, payload):
    Path(path).write_text(json.dumps(to_jsonable(payload), indent=2, ensure_ascii=False), encoding="utf-8")


def to_jsonable(value):
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


if __name__ == "__main__":
    main()
