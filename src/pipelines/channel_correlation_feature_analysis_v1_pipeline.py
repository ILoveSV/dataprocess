import argparse
import json
import re
from itertools import combinations
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import colormaps
import numpy as np
import pandas as pd
from scipy.stats import kruskal, rankdata
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import LabelEncoder


CHANNELS = [f"channel{i}" for i in range(1, 13)]
EPS = 1e-30


def main(argv=None):
    parser = argparse.ArgumentParser(description="Channel Correlation Feature Analysis v1.")
    parser.add_argument("--time-root", default="D:/Lab/process/26.5.12/time")
    parser.add_argument("--output", default="analysis_out/channel_correlation_features_v1")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    pair_path = output_dir / "channel_pair_correlation_dataset_v1.csv"
    feature_path = output_dir / "channel_correlation_feature_dataset_v1.csv"
    if args.force or not pair_path.exists() or not feature_path.exists():
        pair_df, feature_df, audit = extract_features(Path(args.time_root))
        pair_df.to_csv(pair_path, index=False, encoding="utf-8-sig")
        feature_df.to_csv(feature_path, index=False, encoding="utf-8-sig")
        write_json(output_dir / "channel_correlation_input_audit_v1.json", audit)
    else:
        pair_df = pd.read_csv(pair_path)
        feature_df = pd.read_csv(feature_path)
        audit = read_json(output_dir / "channel_correlation_input_audit_v1.json")

    stability = build_stability(feature_df)
    stability.to_csv(output_dir / "channel_correlation_feature_stability_summary_v1.csv", index=False, encoding="utf-8-sig")
    matrix = build_feature_matrix(feature_df)
    matrix.to_csv(output_dir / "channel_correlation_feature_matrix_file_v1.csv", index=False, encoding="utf-8-sig")
    pair_df.to_csv(output_dir / "channel_pair_correlation_matrix_long_v1.csv", index=False, encoding="utf-8-sig")

    sep = build_separability(matrix)
    sep.to_csv(output_dir / "channel_correlation_feature_separability_summary_v1.csv", index=False, encoding="utf-8-sig")
    corr, redundancy = build_redundancy(matrix)
    corr.to_csv(output_dir / "channel_correlation_feature_correlation_matrix_v1.csv", encoding="utf-8-sig")
    redundancy.to_csv(output_dir / "channel_correlation_feature_redundancy_summary_v1.csv", index=False, encoding="utf-8-sig")

    comparison = compare_existing(sep)
    comparison.to_csv(output_dir / "channel_corr_vs_existing_feature_comparison_v1.csv", index=False, encoding="utf-8-sig")
    roles = build_roles(sep, redundancy)
    roles.to_csv(output_dir / "channel_correlation_feature_role_assignment_v1.csv", index=False, encoding="utf-8-sig")
    sets = build_sets(roles)
    write_json(output_dir / "recommended_channel_correlation_feature_sets_v1.json", sets)
    maybe_combined_sets(output_dir, sets)
    plot_top_auc(sep, output_dir / "channel_corr_top_auc_bar_v1.png")
    plot_group_heatmap(matrix, output_dir / "channel_corr_feature_summary_heatmap_v1.png")
    write_report(output_dir, args.time_root, audit, pair_df, feature_df, sep, comparison, roles, sets)
    print(f"Channel Correlation Feature Analysis v1 output: {output_dir}")
    return output_dir


def extract_features(time_root):
    pair_rows = []
    feature_rows = []
    audit = {"time_root": str(time_root), "groups": {}, "warnings": []}
    group_dirs = [p for p in sorted(time_root.iterdir()) if p.is_dir() and parse_group(p.name)]
    for group_dir in group_dirs:
        group = group_dir.name
        parsed = parse_group(group)
        files = sorted(group_dir.glob("*.csv"))
        audit["groups"][group] = {"file_count": len(files), "files": []}
        for path in files:
            pairs, features, file_audit = process_file(path, group, parsed)
            pair_rows.extend(pairs)
            feature_rows.extend(features)
            audit["groups"][group]["files"].append(file_audit)
            if file_audit["qc_warnings"]:
                audit["warnings"].append({"group": group, "file": path.name, "warnings": file_audit["qc_warnings"]})
    return pd.DataFrame(pair_rows), pd.DataFrame(feature_rows), audit


def process_file(path, group, parsed):
    df = pd.read_csv(path)
    channels = [c for c in CHANNELS if c in df.columns]
    time = df["time"].astype(float).to_numpy()
    sr, duration, warnings = sampling_info(time)
    data = df[channels].astype(float).to_numpy()
    qc = list(warnings)
    if len(channels) != len(CHANNELS):
        qc.append("missing_channel")
    if not np.isfinite(data).all():
        qc.append("nan_or_inf")
    std = np.nanstd(data, axis=0)
    constant = [channels[i] for i, value in enumerate(std) if value <= EPS]
    if constant:
        qc.append("constant_channel")
    centered = data - np.nanmean(data, axis=0)
    z = centered / (np.nanstd(centered, axis=0, ddof=1) + EPS)
    corr = np.corrcoef(z, rowvar=False)
    ranks = np.apply_along_axis(rankdata, 0, data)
    spear = np.corrcoef(ranks, rowvar=False)
    pair_rows = pair_table(corr, spear, group, parsed, path, channels, qc, len(df), duration, sr)
    feature_rows = feature_table(data, centered, z, corr, group, parsed, path, channels, qc)
    file_audit = {
        "group": group,
        "file": path.name,
        "channels": channels,
        "missing_channels": [c for c in CHANNELS if c not in channels],
        "n_samples": int(len(df)),
        "duration_seconds": duration,
        "sampling_rate_hz": sr,
        "constant_channels": constant,
        "qc_warnings": qc,
    }
    return pair_rows, feature_rows, file_audit


def pair_table(corr, spear, group, parsed, path, channels, qc, n_samples, duration, sr):
    rows = []
    for i, j in combinations(range(len(channels)), 2):
        value = corr[i, j]
        sp = spear[i, j]
        pair_id = f"{channels[i]}__{channels[j]}"
        rows.append({
            "sample_id": f"{group}__{path.stem}__{pair_id}",
            "group": group,
            "distance": parsed["distance"],
            "rpm": parsed["rpm"],
            "file_id": path.name,
            "channel_i": channels[i],
            "channel_j": channels[j],
            "pair_id": pair_id,
            "correlation_method": "zscored_pearson_main_spearman_control",
            "pearson_corr": value,
            "spearman_corr": sp,
            "abs_pearson_corr": abs(value) if np.isfinite(value) else np.nan,
            "qc_flag": ";".join(sorted(set(qc))) if qc else "OK",
            "n_samples": n_samples,
            "duration_seconds": duration,
            "sampling_rate_hz": sr,
            "preprocessing_mode": "demean_then_zscore",
            "notes": "",
        })
    return rows


def feature_table(raw_data, centered, z, corr, group, parsed, path, channels, qc):
    vals = corr[np.triu_indices(len(channels), k=1)]
    abs_vals = np.abs(vals)
    common = np.nanmean(centered, axis=1)
    residual = centered - common[:, None]
    channel_rms = np.sqrt(np.nanmean(centered * centered, axis=0))
    residual_rms = np.sqrt(np.nanmean(residual * residual, axis=0))
    total_energy = np.nansum(centered * centered, axis=0)
    total_energy_sum = float(np.nansum(total_energy)) + EPS
    contributions = total_energy / total_energy_sum
    dominant_idx = int(np.nanargmax(contributions))
    channel9_idx = channels.index("channel9") if "channel9" in channels else None
    eigvals = np.linalg.eigvalsh(np.nan_to_num(corr, nan=0.0))
    eigvals = np.sort(np.maximum(eigvals, 0.0))[::-1]
    eig_sum = float(eigvals.sum()) + EPS
    ratios = eigvals / eig_sum
    entropy = -float(np.sum(ratios * np.log(ratios + EPS)) / np.log(len(ratios))) if len(ratios) else np.nan
    features = {
        "corr_mean": (np.nanmean(vals), "overall_strength", "corr"),
        "corr_median": (np.nanmedian(vals), "overall_strength", "corr"),
        "corr_abs_mean": (np.nanmean(abs_vals), "overall_strength", "abs_corr"),
        "corr_abs_median": (np.nanmedian(abs_vals), "overall_strength", "abs_corr"),
        "corr_std": (np.nanstd(vals, ddof=1), "overall_strength", "corr"),
        "corr_iqr": (np.nanpercentile(vals, 75) - np.nanpercentile(vals, 25), "overall_strength", "corr"),
        "corr_min": (np.nanmin(vals), "overall_strength", "corr"),
        "corr_max": (np.nanmax(vals), "overall_strength", "corr"),
        "corr_range": (np.nanmax(vals) - np.nanmin(vals), "overall_strength", "corr"),
        "corr_pair_ratio_gt_0p9": (np.nanmean(abs_vals > 0.9), "pair_ratio", "fraction"),
        "corr_pair_ratio_gt_0p7": (np.nanmean(abs_vals > 0.7), "pair_ratio", "fraction"),
        "corr_pair_ratio_gt_0p5": (np.nanmean(abs_vals > 0.5), "pair_ratio", "fraction"),
        "corr_pair_ratio_lt_0p2": (np.nanmean(abs_vals < 0.2), "pair_ratio", "fraction"),
        "common_mode_rms": (np.sqrt(np.nanmean(common * common)), "common_residual", "V"),
        "residual_rms_mean": (np.nanmean(residual_rms), "common_residual", "V"),
        "residual_rms_median": (np.nanmedian(residual_rms), "common_residual", "V"),
        "common_to_residual_ratio": (np.sqrt(np.nanmean(common * common)) / (np.nanmedian(residual_rms) + EPS), "common_residual", "ratio"),
        "common_mode_fraction": (float(np.nansum(common * common)) / (float(np.nanmean(np.nansum(centered * centered, axis=0))) + EPS), "common_residual", "fraction"),
        "pca_first_component_ratio": (ratios[0] if len(ratios) else np.nan, "pca_structure", "fraction"),
        "pca_first_two_ratio": (ratios[:2].sum() if len(ratios) >= 2 else np.nan, "pca_structure", "fraction"),
        "pca_n_components_90": (int(np.searchsorted(np.cumsum(ratios), 0.9) + 1) if len(ratios) else np.nan, "pca_structure", "count"),
        "pca_spectral_entropy": (entropy, "pca_structure", "unitless"),
        "pca_common_mode_like_flag": (int(ratios[0] > 0.8) if len(ratios) else 0, "pca_structure", "boolean"),
        "channel_mean_spread": (np.nanmax(np.nanmean(raw_data, axis=0)) - np.nanmin(np.nanmean(raw_data, axis=0)), "channel_distribution", "V"),
        "channel_acrms_spread": (np.nanmax(channel_rms) - np.nanmin(channel_rms), "channel_distribution", "V"),
        "channel_feature_cv_acrms": (np.nanstd(channel_rms) / (np.nanmean(channel_rms) + EPS), "channel_distribution", "unitless"),
        "channel_rank_entropy_acrms": (entropy_of(channel_rms), "channel_distribution", "unitless"),
        "dominant_channel_ratio_acrms": (np.nanmax(channel_rms) / (np.nanmedian(channel_rms) + EPS), "channel_distribution", "ratio"),
        "max_channel_contribution_ratio": (float(np.nanmax(contributions)), "dominance_risk", "fraction"),
        "dominant_channel_id": (dominant_idx + 1, "dominance_risk", "channel_index"),
        "dominant_channel_risk_flag": (int(np.nanmax(contributions) > 0.25), "dominance_risk", "boolean"),
        "channel9_contribution_ratio": (float(contributions[channel9_idx]) if channel9_idx is not None else np.nan, "dominance_risk", "fraction"),
        "channel9_rank": (rank_desc(contributions)[channel9_idx] if channel9_idx is not None else np.nan, "dominance_risk", "rank"),
    }
    rows = []
    for name, (value, feature_type, unit) in features.items():
        rows.append({
            "sample_id": f"{group}__{path.stem}__channel_corr",
            "group": group,
            "distance": parsed["distance"],
            "rpm": parsed["rpm"],
            "file_id": path.name,
            "feature_domain": "channel_correlation",
            "feature_name": name,
            "feature_value": value,
            "feature_type": feature_type,
            "unit": unit,
            "qc_flag": ";".join(sorted(set(qc))) if qc else "OK",
            "n_channels": len(channels),
            "n_channel_pairs": int(len(channels) * (len(channels) - 1) / 2),
            "n_valid_pairs": int(np.isfinite(vals).sum()),
            "preprocessing_mode": "demean_then_zscore",
            "notes": feature_note(name),
        })
    return rows


def entropy_of(values):
    x = np.asarray(values, dtype=float)
    x = np.maximum(x, 0)
    p = x / (np.nansum(x) + EPS)
    return -float(np.nansum(p * np.log(p + EPS)) / np.log(len(p))) if len(p) else np.nan


def rank_desc(values):
    order = np.argsort(-np.asarray(values))
    ranks = np.empty(len(values), dtype=int)
    ranks[order] = np.arange(1, len(values) + 1)
    return ranks


def build_stability(feature_df):
    rows = []
    data = feature_df[pd.to_numeric(feature_df["feature_value"], errors="coerce").notna()].copy()
    data["feature_value"] = data["feature_value"].astype(float)
    for keys, group in data.groupby(["group", "distance", "rpm", "feature_name"]):
        values = group["feature_value"]
        median = float(values.median())
        mad = float(np.median(np.abs(values - median)))
        stable = np.abs(values - median) <= 3.0 * (1.4826 * mad + EPS)
        rows.append({
            "group": keys[0], "distance": keys[1], "rpm": keys[2], "feature_name": keys[3],
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


def build_feature_matrix(feature_df):
    matrix = feature_df.pivot_table(index=["sample_id", "group", "distance", "rpm", "file_id"], columns="feature_name", values="feature_value", aggfunc="median").reset_index()
    matrix.columns.name = None
    qc = feature_df.groupby(["sample_id", "group", "distance", "rpm", "file_id"], as_index=False)["qc_flag"].agg(join_qc)
    return matrix.merge(qc, on=["sample_id", "group", "distance", "rpm", "file_id"], how="left")


def build_separability(matrix):
    rows = []
    for distance, group in matrix.groupby("distance"):
        cur = group[group["rpm"].isin(["0Hz", "30Hz", "50Hz"])].copy()
        cur["label"] = np.where(cur["rpm"] == "0Hz", "0Hz", "active")
        rows.extend(feature_rows(cur, "Task A active vs 0Hz", distance, "all", "label"))
        cur = group[group["rpm"].isin(["30Hz", "50Hz"])].copy()
        rows.extend(feature_rows(cur, "Task B 30Hz vs 50Hz", distance, "30/50Hz", "rpm"))
    for rpm, group in matrix.groupby("rpm"):
        rows.extend(feature_rows(group, "Task C distance", "2/3/5m", rpm, "distance"))
    rows.extend(feature_rows(matrix[matrix["rpm"].isin(["0Hz", "30Hz", "50Hz"])].copy(), "Task D rpm 3-class", "all", "0/30/50Hz", "rpm"))
    out = pd.DataFrame(rows)
    if not out.empty:
        out["separability_rank"] = out.groupby("task_name")["single_feature_auc_or_macro_auc"].rank(ascending=False, method="min")
    return out


def feature_rows(data, task_name, distance_scope, rpm_scope, label_col):
    features = [c for c in data.columns if c not in {"sample_id", "group", "distance", "rpm", "file_id", "qc_flag", "label"}]
    rows = []
    label_series = first_column(data, label_col)
    labels = sorted(label_series.dropna().unique().tolist()) if label_series is not None else []
    for feature in features:
        cur = data[[feature, label_col]].dropna()
        row = {
            "task_name": task_name, "sample_grain": "file_level", "feature_domain": "channel_correlation",
            "feature_name": feature, "feature_type": feature_type(feature),
            "distance_scope": distance_scope, "rpm_scope": rpm_scope,
            "n_samples": int(len(cur)), "class_labels": json.dumps(labels),
            "median_by_class": "{}", "iqr_by_class": "{}", "effect_size": np.nan,
            "overlap_score": np.nan, "single_feature_auc_or_macro_auc": np.nan,
            "separability_rank": np.nan, "qc_warning": "", "notes": feature_note(feature), "skipped_reason": "",
        }
        cur_labels = first_column(cur, label_col)
        counts = cur_labels.value_counts() if cur_labels is not None else pd.Series(dtype=int)
        if len(counts) < 2 or counts.min() < 3:
            row["skipped_reason"] = "need at least 2 classes and 3 samples per class"
            rows.append(row)
            continue
        x = cur[feature].astype(float)
        y = cur_labels.astype(str)
        grouped = cur.assign(__label=y).groupby("__label")[feature]
        med = grouped.median().to_dict()
        iqr = (grouped.quantile(0.75) - grouped.quantile(0.25)).to_dict()
        row["median_by_class"] = json.dumps({str(k): float(v) for k, v in med.items()})
        row["iqr_by_class"] = json.dumps({str(k): float(v) for k, v in iqr.items()})
        if len(counts) == 2:
            labs = sorted(counts.index.astype(str).tolist())
            a, b = x[y == labs[0]], x[y == labs[1]]
            row["effect_size"] = robust_effect(a, b)
            row["overlap_score"] = overlap_score(a, b)
            row["single_feature_auc_or_macro_auc"] = max_auc(y, x)
        else:
            vals = [x[y == str(label)] for label in sorted(counts.index.astype(str).tolist())]
            try:
                stat, _ = kruskal(*vals)
                row["effect_size"] = float(stat / max(len(x) - 1, 1))
            except Exception:
                pass
            row["single_feature_auc_or_macro_auc"] = macro_auc(y, x)
        rows.append(row)
    return rows


def first_column(frame, name):
    if name not in frame:
        return None
    value = frame[name]
    if isinstance(value, pd.DataFrame):
        return value.iloc[:, 0]
    return value


def build_redundancy(matrix):
    features = [c for c in matrix.columns if c not in {"sample_id", "group", "distance", "rpm", "file_id", "qc_flag"}]
    corr = matrix[features].corr(method="spearman")
    rows = []
    for i, a in enumerate(features):
        for b in features[i + 1:]:
            val = corr.loc[a, b]
            if abs(val) > 0.9:
                rows.append({"feature_a": a, "feature_b": b, "spearman_corr": val, "redundant_flag": True, "suggested_keep": suggest_keep(a, b), "notes": "high absolute correlation; do not auto-delete"})
    return corr, pd.DataFrame(rows)


def compare_existing(sep):
    tf_path = Path("analysis_out/time_frequency_feature_comparison_v1/combined_feature_separability_summary.csv")
    acf_path = Path("analysis_out/acf_features_v1/acf_feature_separability_summary_v1.csv")
    if not tf_path.exists() or not acf_path.exists():
        return pd.DataFrame([{"skipped_reason": "existing time/frequency or ACF comparison files not found"}])
    tf = pd.read_csv(tf_path)
    acf = pd.read_csv(acf_path)
    rows = []
    cc = sep[sep["single_feature_auc_or_macro_auc"].notna()]
    tf = tf[(tf["sample_grain"] == "file_agg") & tf["single_feature_auc_or_macro_auc"].notna()]
    acf = acf[(acf["sample_grain"] == "file_agg") & acf["single_feature_auc_or_macro_auc"].notna()]
    for task in sorted(set(cc["task_name"]) | set(tf["task_name"]) | set(acf["task_name"])):
        freq = top_domain(tf, task, "frequency")
        time = top_domain(tf, task, "time")
        acf_top = acf[acf["task_name"] == task].sort_values("single_feature_auc_or_macro_auc", ascending=False)
        cc_top = cc[cc["task_name"] == task].sort_values("single_feature_auc_or_macro_auc", ascending=False)
        best_cc = float(cc_top["single_feature_auc_or_macro_auc"].iloc[0]) if not cc_top.empty else np.nan
        best_existing = np.nanmax([best_auc(freq), best_auc(time), best_auc(acf_top)])
        value = "high" if pd.notna(best_cc) and best_cc >= 0.75 and best_cc >= best_existing - 0.03 else "medium" if pd.notna(best_cc) and best_cc >= 0.75 else "low"
        rows.append({
            "task_name": task,
            "best_frequency_auc": best_auc(freq),
            "best_time_auc": best_auc(time),
            "best_acf_auc": best_auc(acf_top),
            "best_channel_corr_auc": best_cc,
            "best_frequency_feature": best_feature(freq),
            "best_time_feature": best_feature(time),
            "best_acf_feature": best_feature(acf_top),
            "best_channel_corr_feature": best_feature(cc_top),
            "channel_corr_additional_value": value,
            "reason": "compared by top file-level/file_agg AUC; not a final model conclusion",
        })
    return pd.DataFrame(rows)


def build_roles(sep, redundancy):
    redundant = set(redundancy["feature_a"].tolist() + redundancy["feature_b"].tolist()) if not redundancy.empty else set()
    rows = []
    for feature, group in sep.groupby("feature_name"):
        best = group.sort_values("single_feature_auc_or_macro_auc", ascending=False).head(1).iloc[0]
        common = feature in {"common_mode_rms", "common_to_residual_ratio", "common_mode_fraction", "pca_first_component_ratio", "pca_common_mode_like_flag"}
        dominant = feature in {"max_channel_contribution_ratio", "dominant_channel_ratio_acrms", "dominant_channel_risk_flag", "channel9_contribution_ratio", "channel9_rank", "dominant_channel_id"}
        qc = common or dominant or feature.endswith("_flag") or feature in {"pca_spectral_entropy", "pca_n_components_90"}
        role = "qc_only" if qc else "auxiliary_candidate"
        if best.single_feature_auc_or_macro_auc < 0.65:
            role = "reject" if not qc else "qc_only"
        rows.append({
            "feature_name": feature,
            "feature_type": feature_type(feature),
            "best_task": best.task_name,
            "best_auc": best.single_feature_auc_or_macro_auc,
            "best_effect_size": best.effect_size,
            "redundancy_level": "high" if feature in redundant else "low",
            "common_mode_risk_flag": bool(common),
            "dominant_channel_risk_flag": bool(dominant),
            "qc_role_flag": bool(qc),
            "recommended_role": role,
            "reason": role_reason(role, common, dominant, feature in redundant),
        })
    return pd.DataFrame(rows)


def build_sets(roles):
    return {
        "channel_corr_auxiliary": roles[roles["recommended_role"] == "auxiliary_candidate"]["feature_name"].tolist(),
        "channel_corr_qc_features": roles[roles["recommended_role"] == "qc_only"]["feature_name"].tolist(),
        "channel_corr_rejected": roles[roles["recommended_role"] == "reject"]["feature_name"].tolist(),
        "channel_corr_common_mode_risk_features": roles[roles["common_mode_risk_flag"]]["feature_name"].tolist(),
    }


def maybe_combined_sets(output_dir, sets):
    path = Path("analysis_out/acf_features_v1/recommended_feature_sets_with_acf_v1.json")
    if not path.exists():
        path = Path("analysis_out/time_frequency_feature_comparison_v1/recommended_feature_sets_v1.json")
    if not path.exists():
        return
    base = read_json(path)
    out = dict(base)
    out["channel_corr_auxiliary"] = sets["channel_corr_auxiliary"]
    out["combined_nonredundant_with_channel_corr"] = base.get("combined_nonredundant_with_acf", base.get("combined_nonredundant", [])) + sets["channel_corr_auxiliary"]
    out["qc_features"] = base.get("qc_features", []) + sets["channel_corr_qc_features"]
    write_json(output_dir / "recommended_feature_sets_with_channel_corr_v1.json", out)


def plot_top_auc(sep, path):
    top = sep[sep["single_feature_auc_or_macro_auc"].notna()].sort_values("single_feature_auc_or_macro_auc", ascending=False).groupby("task_name").head(1)
    plt.figure(figsize=(9, 4))
    plt.bar(top["task_name"], top["single_feature_auc_or_macro_auc"])
    plt.xticks(rotation=30, ha="right")
    plt.ylabel("Top channel-correlation AUC")
    plt.title("Top Channel-Correlation Feature AUC by Task")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def plot_group_heatmap(matrix, path):
    features = [c for c in matrix.columns if c not in {"sample_id", "group", "distance", "rpm", "file_id", "qc_flag"}]
    med = matrix.groupby("group")[features].median()
    plt.figure(figsize=(14, 6))
    plt.imshow(med.T, aspect="auto", cmap=colormaps.get_cmap("coolwarm"))
    plt.xticks(range(len(med.index)), med.index, rotation=45, ha="right")
    plt.yticks(range(len(features)), features, fontsize=7)
    plt.colorbar(label="group median")
    plt.title("Channel-Correlation Feature Group Median Heatmap")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def write_report(output_dir, time_root, audit, pair_df, feature_df, sep, comparison, roles, sets):
    Path("docs").mkdir(exist_ok=True)
    report = Path("docs") / "CHANNEL_CORRELATION_FEATURE_ANALYSIS_V1.md"
    top = sep[sep["single_feature_auc_or_macro_auc"].notna()].sort_values("single_feature_auc_or_macro_auc", ascending=False).head(8)
    channel9 = feature_df[feature_df["feature_name"].eq("channel9_contribution_ratio")]["feature_value"].astype(float)
    common_flags = int(feature_df[feature_df["feature_name"].eq("pca_common_mode_like_flag")]["feature_value"].astype(float).sum())
    dominant_flags = int(feature_df[feature_df["feature_name"].eq("dominant_channel_risk_flag")]["feature_value"].astype(float).sum())
    comp_lines = []
    if "channel_corr_additional_value" in comparison.columns:
        for row in comparison.itertuples():
            comp_lines.append(f"- `{row.task_name}`: best_channel_corr_auc={row.best_channel_corr_auc:.3g}, value={row.channel_corr_additional_value}; feature={row.best_channel_corr_feature}")
    lines = [
        "# Channel Correlation Feature Analysis v1",
        "",
        "## Purpose",
        "",
        "PSD/time/ACF features are mostly single-channel. Channel-correlation features describe array-level synchrony, common-mode behavior, residual structure, PCA concentration, and single-channel dominance risk.",
        "",
        "## Inputs",
        "",
        f"- Time CSV root: `{time_root}`",
        f"- Groups read: {', '.join(sorted(audit.get('groups', {}).keys(), key=group_sort_key))}",
        "",
        "## Calculation",
        "",
        "- Each file is processed independently as a time_sample x channel matrix.",
        "- Channels are de-meaned and z-scored before Pearson correlation.",
        "- Spearman correlation is also exported as a robust control.",
        "- Common mode is the per-sample mean across channels after de-meaning.",
        "- PCA features are computed from the channel correlation matrix eigenvalues.",
        "",
        "## Outputs and coverage",
        "",
        f"- Channel-pair rows: {len(pair_df)}",
        f"- File-level feature rows: {len(feature_df)}",
        f"- Groups: {feature_df['group'].nunique()}, files: {feature_df['file_id'].nunique()}",
        "",
        "## Separability",
    ]
    for row in top.itertuples():
        lines.append(f"- `{row.feature_name}` `{row.task_name}`: AUC={row.single_feature_auc_or_macro_auc:.3g}, effect={row.effect_size:.3g}")
    lines.extend([
        "",
        "## Comparison with existing PSD/time/ACF",
        *comp_lines,
        "",
        "## Common-mode and dominance risks",
        "",
        f"- PCA common-mode-like flags across files: {common_flags}",
        f"- Dominant-channel risk flags across files: {dominant_flags}",
        f"- channel9 contribution ratio range: {channel9.min():.3g}-{channel9.max():.3g}",
        "- High channel9 contribution is a needs-check flag, not a bad-channel decision.",
        "",
        "## Roles",
        "",
        f"- Role counts: {roles['recommended_role'].value_counts().to_dict()}",
        f"- Auxiliary: {sets['channel_corr_auxiliary']}",
        f"- QC: {sets['channel_corr_qc_features']}",
        f"- Rejected: {sets['channel_corr_rejected']}",
        "",
        "## Scope guard",
        "",
        "- No machine learning was run.",
        "- No cross-spectrum/coherence was computed.",
        "- No FFT/background contrast output was modified.",
        "- No channel was automatically removed.",
        "- Channel correlation is not interpreted as physical target spatial distribution.",
    ])
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


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


def top_domain(df, task, domain):
    return df[(df["task_name"] == task) & (df["feature_domain"] == domain)].sort_values("single_feature_auc_or_macro_auc", ascending=False)


def best_auc(df):
    return float(df["single_feature_auc_or_macro_auc"].iloc[0]) if df is not None and not df.empty else np.nan


def best_feature(df):
    return str(df["feature_name"].iloc[0]) if df is not None and not df.empty else ""


def suggest_keep(a, b):
    if "corr_abs_median" in (a, b):
        return "corr_abs_median"
    if "pca_first_component_ratio" in (a, b):
        return "pca_first_component_ratio"
    return a


def feature_type(name):
    if name.startswith("corr_pair_ratio"):
        return "pair_ratio"
    if name.startswith("corr_"):
        return "overall_strength"
    if name.startswith("common") or name.startswith("residual"):
        return "common_residual"
    if name.startswith("pca"):
        return "pca_structure"
    if name.startswith("channel"):
        return "channel_distribution"
    return "dominance_risk"


def feature_note(name):
    if "common" in name or "pca_first_component" in name:
        return "common-mode risk indicator; do not directly interpret as target feature"
    if "dominant" in name or "channel9" in name:
        return "single-channel dominance risk indicator"
    return ""


def role_reason(role, common, dominant, redundant):
    parts = [f"role={role}"]
    if common:
        parts.append("common-mode risk")
    if dominant:
        parts.append("dominant-channel risk")
    if redundant:
        parts.append("high redundancy")
    return "; ".join(parts)


def sampling_info(time):
    if len(time) < 2:
        return np.nan, np.nan, ["too_short", "invalid_sampling_rate"]
    dt = float(np.median(np.diff(time)))
    sr = 1.0 / dt if dt > 0 else np.nan
    return sr, float(time[-1] - time[0]), [] if np.isfinite(sr) else ["invalid_sampling_rate"]


def parse_group(group):
    m = re.fullmatch(r"(\d+(?:\.\d+)?)m(\d+(?:\.\d+)?)hz", str(group))
    if not m:
        return None
    d = float(m.group(1)); r = float(m.group(2))
    return {"distance": f"{int(d)}m" if d.is_integer() else f"{d:g}m", "rpm": f"{int(r)}Hz" if r.is_integer() else f"{r:g}Hz"}


def group_sort_key(group):
    parsed = parse_group(group)
    if parsed is None:
        return (999, 999)
    return (float(parsed["distance"].replace("m", "")), float(parsed["rpm"].replace("Hz", "")))


def join_qc(values):
    unique = sorted(set(str(v) for v in values if pd.notna(v)))
    return ";".join(unique) if unique else "OK"


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
