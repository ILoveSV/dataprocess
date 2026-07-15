import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import colormaps
import numpy as np
import pandas as pd
from scipy.stats import kruskal
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import LabelEncoder


BASELINE_RISK_FEATURES = {"mean", "median", "dc_offset", "min", "max", "rms"}
QC_FEATURE_TYPES = {"drift", "spike", "local_stability"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Time + Frequency Feature Comparison v1.")
    parser.add_argument("--frequency-dataset", default="analysis_out/feature_extraction_v2/candidate_feature_dataset_v2.csv")
    parser.add_argument("--frequency-stability", default="analysis_out/feature_extraction_v2/feature_stability_summary_v2.csv")
    parser.add_argument("--time-dataset", default="analysis_out/time_domain_features_v1/time_domain_feature_dataset_v1.csv")
    parser.add_argument("--time-stability", default="analysis_out/time_domain_features_v1/time_domain_feature_stability_summary_v1.csv")
    parser.add_argument("--output", default="analysis_out/time_frequency_feature_comparison_v1")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    freq = pd.read_csv(args.frequency_dataset)
    freq_stability = pd.read_csv(args.frequency_stability)
    time = pd.read_csv(args.time_dataset)
    time_stability = pd.read_csv(args.time_stability)

    combined, audit = build_combined_long(freq, time)
    combined.to_csv(output_dir / "combined_feature_dataset_v1.csv", index=False, encoding="utf-8-sig")
    write_json(output_dir / "feature_key_mismatch_audit_v1.json", audit)

    file_channel, file_agg = build_wide_matrices(combined)
    file_channel.to_csv(output_dir / "combined_feature_matrix_file_channel.csv", index=False, encoding="utf-8-sig")
    file_agg.to_csv(output_dir / "combined_feature_matrix_file_agg.csv", index=False, encoding="utf-8-sig")

    sep = build_separability(file_channel, file_agg, combined)
    sep.to_csv(output_dir / "combined_feature_separability_summary.csv", index=False, encoding="utf-8-sig")

    domain_summary = build_domain_comparison(sep)
    domain_summary.to_csv(output_dir / "domain_comparison_summary.csv", index=False, encoding="utf-8-sig")

    corr, redundancy = build_correlation_and_redundancy(file_agg)
    corr.to_csv(output_dir / "combined_feature_correlation_matrix.csv", encoding="utf-8-sig")
    redundancy.to_csv(output_dir / "combined_feature_redundancy_summary.csv", index=False, encoding="utf-8-sig")

    baseline_risk = build_baseline_risk_summary(sep, file_agg)
    baseline_risk.to_csv(output_dir / "baseline_risk_feature_summary.csv", index=False, encoding="utf-8-sig")

    roles = build_role_assignment(sep, redundancy, baseline_risk, combined, freq_stability, time_stability)
    roles.to_csv(output_dir / "feature_role_assignment_v1.csv", index=False, encoding="utf-8-sig")

    feature_sets = build_feature_sets(roles)
    write_json(output_dir / "recommended_feature_sets_v1.json", feature_sets)

    plot_top_auc(domain_summary, output_dir / "feature_domain_top_auc_bar.png")
    write_report(output_dir, args, combined, file_channel, file_agg, sep, domain_summary, redundancy, roles, feature_sets, audit)
    print(f"Time + Frequency Feature Comparison v1 output: {output_dir}")
    return output_dir


def build_combined_long(freq, time):
    freq = freq[freq["analysis_mode"] == "strict"].copy()
    freq["normalized_file_key"] = freq["file_id"].map(normalize_file_key)
    time = time.copy()
    time["analysis_mode"] = "time_all"
    time["normalized_file_key"] = time["file_id"].map(normalize_file_key)

    freq_keys = set(zip(freq["group"], freq["normalized_file_key"], freq["channel"]))
    time_keys = set(zip(time["group"], time["normalized_file_key"], time["channel"]))
    common = freq_keys & time_keys
    freq_only = freq_keys - time_keys
    time_only = time_keys - freq_keys

    freq = freq[freq.apply(lambda r: (r["group"], r["normalized_file_key"], r["channel"]) in common, axis=1)].copy()
    time = time[time.apply(lambda r: (r["group"], r["normalized_file_key"], r["channel"]) in common, axis=1)].copy()

    freq_out = pd.DataFrame({
        "sample_id": freq["group"] + "__" + freq["normalized_file_key"] + "__" + freq["channel"],
        "group": freq["group"],
        "distance": freq["distance"],
        "rpm": freq["rpm"],
        "file_id": freq["file_id"],
        "normalized_file_key": freq["normalized_file_key"],
        "channel": freq["channel"],
        "feature_domain": "frequency",
        "feature_name": "freq__" + freq["feature_name"].astype(str),
        "raw_feature_name": freq["feature_name"],
        "feature_value": freq["feature_value"],
        "feature_type": freq["feature_type"],
        "unit": "dB",
        "qc_flag": freq["qc_flag"],
        "source_table": "candidate_feature_dataset_v2.csv",
        "analysis_mode": "strict",
    })
    time_out = pd.DataFrame({
        "sample_id": time["group"] + "__" + time["normalized_file_key"] + "__" + time["channel"],
        "group": time["group"],
        "distance": time["distance"],
        "rpm": time["rpm"],
        "file_id": time["file_id"],
        "normalized_file_key": time["normalized_file_key"],
        "channel": time["channel"],
        "feature_domain": "time",
        "feature_name": "time__" + time["feature_name"].astype(str),
        "raw_feature_name": time["feature_name"],
        "feature_value": time["feature_value"],
        "feature_type": time["feature_type"],
        "unit": time["unit"],
        "qc_flag": time["qc_flag"],
        "source_table": "time_domain_feature_dataset_v1.csv",
        "analysis_mode": "time_all",
    })
    audit = {
        "freq_strict_key_count": len(freq_keys),
        "time_key_count": len(time_keys),
        "common_key_count": len(common),
        "freq_only_key_count": len(freq_only),
        "time_only_key_count": len(time_only),
        "note": "Frequency file_id uses FFT_ prefix; normalized_file_key removes only the FFT_ prefix and keeps .csv suffix for alignment.",
    }
    return pd.concat([freq_out, time_out], ignore_index=True), audit


def normalize_file_key(file_id):
    text = str(file_id)
    if text.startswith("FFT_"):
        text = text[4:]
    return text


def build_wide_matrices(combined):
    id_cols = ["sample_id", "group", "distance", "rpm", "normalized_file_key", "channel"]
    file_channel = combined.pivot_table(index=id_cols, columns="feature_name", values="feature_value", aggfunc="median").reset_index()
    file_channel.columns.name = None
    qc = combined.groupby(id_cols, as_index=False)["qc_flag"].agg(join_qc)
    mode = combined.groupby(id_cols, as_index=False)["analysis_mode"].agg(lambda s: "strict+time_all")
    file_channel = file_channel.merge(qc, on=id_cols, how="left").merge(mode, on=id_cols, how="left")
    file_channel = file_channel.rename(columns={"normalized_file_key": "file_id"})

    agg = combined.groupby(["group", "distance", "rpm", "normalized_file_key", "feature_name"], as_index=False).agg(
        feature_value=("feature_value", "median"),
        qc_flag=("qc_flag", join_qc),
    )
    file_agg = agg.pivot_table(index=["group", "distance", "rpm", "normalized_file_key"], columns="feature_name", values="feature_value", aggfunc="median").reset_index()
    file_agg.columns.name = None
    qc2 = agg.groupby(["group", "distance", "rpm", "normalized_file_key"], as_index=False)["qc_flag"].agg(join_qc)
    file_agg = file_agg.merge(qc2, on=["group", "distance", "rpm", "normalized_file_key"], how="left")
    file_agg = file_agg.rename(columns={"normalized_file_key": "file_id"})
    file_agg["channel"] = "aggregated_median"
    file_agg["sample_id"] = file_agg["group"] + "__" + file_agg["file_id"] + "__aggregated_median"
    file_agg["analysis_mode"] = "strict+time_all"
    front = ["sample_id", "group", "distance", "rpm", "file_id", "channel"]
    features = sorted([c for c in file_agg.columns if c.startswith("freq__") or c.startswith("time__")])
    file_agg = file_agg[front + features + ["qc_flag", "analysis_mode"]]
    features_fc = sorted([c for c in file_channel.columns if c.startswith("freq__") or c.startswith("time__")])
    file_channel = file_channel[front + features_fc + ["qc_flag", "analysis_mode"]]
    return file_channel, file_agg


def join_qc(values):
    unique = sorted(set(str(v) for v in values if pd.notna(v)))
    return ";".join(unique) if unique else "OK"


def build_separability(file_channel, file_agg, combined):
    meta = combined.drop_duplicates("feature_name").set_index("feature_name")[["feature_domain", "feature_type"]].to_dict("index")
    rows = []
    for grain, matrix in [("file_channel", file_channel), ("file_agg", file_agg)]:
        rows.extend(task_rows(matrix, grain, "Task A active vs 0Hz", "distance", ["0Hz", "30Hz", "50Hz"], "active_binary"))
        rows.extend(task_rows(matrix, grain, "Task B 30Hz vs 50Hz", "distance", ["30Hz", "50Hz"], "rpm"))
        rows.extend(task_rows(matrix, grain, "Task C distance", "rpm", ["2m", "3m", "5m"], "distance"))
        rows.extend(feature_rows_for_task(matrix[matrix["rpm"].isin(["0Hz", "30Hz", "50Hz"])].copy(), grain, "Task D rpm 3-class", "all", "0/30/50Hz", "rpm"))
    out = pd.DataFrame(rows)
    if not out.empty:
        out["feature_domain"] = out["feature_name"].map(lambda x: meta.get(x, {}).get("feature_domain", "UNKNOWN"))
        out["feature_type"] = out["feature_name"].map(lambda x: meta.get(x, {}).get("feature_type", "UNKNOWN"))
        out["separability_rank"] = out.groupby(["sample_grain", "task_name"])["single_feature_auc_or_macro_auc"].rank(ascending=False, method="min")
    return out


def task_rows(matrix, grain, task_name, scope_col, labels, label_mode):
    rows = []
    for scope, group in matrix.groupby(scope_col):
        if label_mode == "active_binary":
            current = group[group["rpm"].isin(labels)].copy()
            current["label"] = np.where(current["rpm"] == "0Hz", "0Hz", "active")
            rows.extend(feature_rows_for_task(current, grain, task_name, scope if scope_col == "distance" else "all", "all", "label"))
        elif label_mode == "rpm":
            current = group[group["rpm"].isin(labels)].copy()
            rows.extend(feature_rows_for_task(current, grain, task_name, scope, "30/50Hz", "rpm"))
        else:
            current = group[group["distance"].isin(labels)].copy()
            rows.extend(feature_rows_for_task(current, grain, task_name, "2/3/5m", scope, "distance"))
    return rows


def feature_rows_for_task(data, grain, task_name, distance_scope, rpm_scope, label_col):
    feature_cols = [c for c in data.columns if c.startswith("freq__") or c.startswith("time__")]
    rows = []
    labels = sorted(data[label_col].dropna().unique().tolist()) if label_col in data else []
    for feature in feature_cols:
        current = data[[feature, label_col]].dropna()
        row = {
            "task_name": task_name,
            "sample_grain": grain,
            "feature_name": feature,
            "distance_scope": distance_scope,
            "rpm_scope": rpm_scope,
            "n_samples": int(len(current)),
            "class_labels": json.dumps(labels),
            "median_by_class": "{}",
            "iqr_by_class": "{}",
            "effect_size": np.nan,
            "overlap_score": np.nan,
            "single_feature_auc_or_macro_auc": np.nan,
            "separability_rank": np.nan,
            "qc_warning": "",
            "notes": "",
            "skipped_reason": "",
        }
        counts = current[label_col].value_counts() if label_col in current else pd.Series(dtype=int)
        if len(counts) < 2 or counts.min() < 3:
            row["skipped_reason"] = "need at least 2 classes and 3 samples per class"
            rows.append(row)
            continue
        y = current[label_col].astype(str)
        x = current[feature].astype(float)
        med = current.groupby(label_col)[feature].median().to_dict()
        iqr = (current.groupby(label_col)[feature].quantile(0.75) - current.groupby(label_col)[feature].quantile(0.25)).to_dict()
        row["median_by_class"] = json.dumps({str(k): float(v) for k, v in med.items()})
        row["iqr_by_class"] = json.dumps({str(k): float(v) for k, v in iqr.items()})
        if len(counts) == 2:
            labels2 = sorted(counts.index.astype(str).tolist())
            a = x[y == labels2[0]]
            b = x[y == labels2[1]]
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
    spread = ((np.percentile(a, 75) - np.percentile(a, 25)) + (np.percentile(b, 75) - np.percentile(b, 25))) / 2.0
    return float((np.median(b) - np.median(a)) / (spread + 1e-9))


def overlap_score(a, b):
    a1, a3 = np.percentile(a, [25, 75])
    b1, b3 = np.percentile(b, [25, 75])
    return float(max(0, min(a3, b3) - max(a1, b1)) / (max(a3, b3) - min(a1, b1) + 1e-9))


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


def build_domain_comparison(sep):
    rows = []
    current = sep[sep["single_feature_auc_or_macro_auc"].notna()].copy()
    for keys, group in current.groupby(["task_name", "sample_grain"]):
        freq = group[group["feature_domain"] == "frequency"].sort_values("single_feature_auc_or_macro_auc", ascending=False)
        time = group[group["feature_domain"] == "time"].sort_values("single_feature_auc_or_macro_auc", ascending=False)
        best_freq_auc = float(freq["single_feature_auc_or_macro_auc"].max()) if not freq.empty else np.nan
        best_time_auc = float(time["single_feature_auc_or_macro_auc"].max()) if not time.empty else np.nan
        time_use = "low"
        reason = "time features weaker than frequency"
        if pd.notna(best_time_auc) and pd.notna(best_freq_auc):
            if best_time_auc >= best_freq_auc - 0.03:
                time_use = "high"
                reason = "best time feature is close to best frequency feature"
            elif best_time_auc >= 0.75:
                time_use = "medium"
                reason = "time feature has standalone separability"
        rows.append({
            "task_name": keys[0],
            "sample_grain": keys[1],
            "top_10_features_overall": json.dumps(group.sort_values("single_feature_auc_or_macro_auc", ascending=False)["feature_name"].head(10).tolist()),
            "top_10_frequency_features": json.dumps(freq["feature_name"].head(10).tolist()),
            "top_10_time_features": json.dumps(time["feature_name"].head(10).tolist()),
            "best_frequency_auc": best_freq_auc,
            "best_time_auc": best_time_auc,
            "best_frequency_effect_size": float(freq["effect_size"].abs().max()) if not freq.empty else np.nan,
            "best_time_effect_size": float(time["effect_size"].abs().max()) if not time.empty else np.nan,
            "time_domain_usefulness": time_use,
            "reason": reason,
        })
    return pd.DataFrame(rows)


def build_correlation_and_redundancy(file_agg):
    features = [c for c in file_agg.columns if c.startswith("freq__") or c.startswith("time__")]
    corr = file_agg[features].corr(method="spearman")
    rows = []
    for i, a in enumerate(features):
        for b in features[i + 1:]:
            value = corr.loc[a, b]
            if abs(value) > 0.9:
                rows.append({
                    "feature_a": a,
                    "feature_b": b,
                    "domain_pair": domain_of(a) + "-" + domain_of(b),
                    "spearman_corr": value,
                    "redundant_flag": True,
                    "suggested_keep": suggest_keep(a, b),
                    "notes": redundancy_note(a, b),
                })
    return corr, pd.DataFrame(rows)


def domain_of(feature):
    return "frequency" if feature.startswith("freq__") else "time"


def suggest_keep(a, b):
    if a.startswith("freq__") and b.startswith("time__"):
        return a
    if b.startswith("freq__") and a.startswith("time__"):
        return b
    if "dc_offset" in a or "dc_offset" in b:
        return b if "dc_offset" in a else a
    return a


def redundancy_note(a, b):
    if "ac_rms" in (a + b) or "robust_sigma" in (a + b) or "rolling_rms" in (a + b):
        return "variation/rms feature may track frequency-domain energy"
    if any(x in (a + b) for x in ["mean", "median", "dc_offset"]):
        return "baseline-risk time feature redundancy"
    return "high absolute correlation; do not auto-delete"


def build_baseline_risk_summary(sep, file_agg):
    rows = []
    current = sep[(sep["feature_name"].isin("time__" + f for f in BASELINE_RISK_FEATURES)) & sep["single_feature_auc_or_macro_auc"].notna()]
    for _, row in current.iterrows():
        feature = row["feature_name"]
        med = file_agg.groupby("group")[feature].median().to_dict() if feature in file_agg else {}
        level = "high" if row["single_feature_auc_or_macro_auc"] >= 0.85 else "medium" if row["single_feature_auc_or_macro_auc"] >= 0.75 else "low"
        usage = "exclude_from_primary" if level == "high" else "qc_only" if feature in {"time__mean", "time__median", "time__dc_offset"} else "auxiliary"
        rows.append({
            "feature_name": feature,
            "task_name": row["task_name"],
            "auc": row["single_feature_auc_or_macro_auc"],
            "effect_size": row["effect_size"],
            "median_by_group": json.dumps({str(k): float(v) for k, v in med.items()}),
            "baseline_risk_level": level,
            "recommended_usage": usage,
            "reason": "baseline/location feature may reflect DC offset, acquisition zero, distance batch, wiring, or amplifier bias",
        })
    return pd.DataFrame(rows)


def build_role_assignment(sep, redundancy, baseline_risk, combined, freq_stability, time_stability):
    feature_meta = combined.drop_duplicates("feature_name").set_index("feature_name")[["feature_domain", "feature_type"]].to_dict("index")
    roles = []
    redundant_features = set(redundancy["feature_a"].tolist() + redundancy["feature_b"].tolist()) if not redundancy.empty else set()
    baseline_high = set(baseline_risk[baseline_risk["baseline_risk_level"].isin(["high", "medium"])]["feature_name"]) if not baseline_risk.empty else set()
    for feature, meta in feature_meta.items():
        current = sep[sep["feature_name"] == feature]
        best = current.sort_values("single_feature_auc_or_macro_auc", ascending=False).head(1)
        best_auc = float(best["single_feature_auc_or_macro_auc"].iloc[0]) if not best.empty else np.nan
        best_effect = float(best["effect_size"].iloc[0]) if not best.empty else np.nan
        best_task = str(best["task_name"].iloc[0]) if not best.empty else "UNKNOWN"
        baseline_risk_flag = feature in baseline_high or raw_name(feature) in BASELINE_RISK_FEATURES
        qc_role = meta["feature_type"] in QC_FEATURE_TYPES or raw_name(feature) in {"clipping_flag", "stable_window_ratio", "longest_stable_duration"}
        redundancy_level = "high" if feature in redundant_features else "low"
        if qc_role:
            role = "qc_only"
        elif baseline_risk_flag:
            role = "auxiliary_candidate" if best_auc >= 0.8 else "qc_only"
        elif meta["feature_domain"] == "frequency" and best_auc >= 0.75:
            role = "primary_candidate"
        elif meta["feature_domain"] == "time" and best_auc >= 0.75 and redundancy_level == "low":
            role = "auxiliary_candidate"
        elif best_auc >= 0.65:
            role = "auxiliary_candidate"
        else:
            role = "reject"
        roles.append({
            "feature_name": feature,
            "feature_domain": meta["feature_domain"],
            "feature_type": meta["feature_type"],
            "best_task": best_task,
            "best_auc": best_auc,
            "best_effect_size": best_effect,
            "redundancy_level": redundancy_level,
            "baseline_risk_flag": bool(baseline_risk_flag),
            "qc_role_flag": bool(qc_role),
            "recommended_role": role,
            "reason": role_reason(role, baseline_risk_flag, qc_role, redundancy_level),
        })
    return pd.DataFrame(roles)


def raw_name(feature):
    return feature.split("__", 1)[1] if "__" in feature else feature


def role_reason(role, baseline, qc, redundancy):
    parts = [f"role={role}", f"redundancy={redundancy}"]
    if baseline:
        parts.append("baseline-risk")
    if qc:
        parts.append("QC-oriented")
    return "; ".join(parts)


def build_feature_sets(roles):
    frequency_core = roles[(roles["feature_domain"] == "frequency") & (roles["recommended_role"] == "primary_candidate") & (roles["redundancy_level"] != "high")]["feature_name"].tolist()
    if not frequency_core:
        frequency_core = roles[(roles["feature_domain"] == "frequency") & (roles["recommended_role"] == "primary_candidate")]["feature_name"].head(8).tolist()
    time_aux = roles[(roles["feature_domain"] == "time") & (roles["recommended_role"] == "auxiliary_candidate") & (~roles["baseline_risk_flag"]) & (~roles["qc_role_flag"])]["feature_name"].tolist()
    qc = roles[roles["recommended_role"] == "qc_only"]["feature_name"].tolist()
    baseline = roles[roles["baseline_risk_flag"]]["feature_name"].tolist()
    combined = frequency_core + [f for f in time_aux if f not in frequency_core]
    return {
        "frequency_core": frequency_core,
        "time_auxiliary": time_aux,
        "combined_nonredundant": combined,
        "qc_features": qc,
        "excluded_baseline_risk": baseline,
    }


def plot_top_auc(domain_summary, path):
    data = domain_summary[domain_summary["sample_grain"] == "file_agg"].copy()
    x = np.arange(len(data))
    plt.figure(figsize=(10, 5))
    plt.bar(x - 0.18, data["best_frequency_auc"], width=0.36, label="frequency")
    plt.bar(x + 0.18, data["best_time_auc"], width=0.36, label="time")
    plt.xticks(x, data["task_name"], rotation=30, ha="right")
    plt.ylabel("Top AUC")
    plt.title("Top Frequency vs Time Feature AUC by Task (file_agg)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def write_report(output_dir, args, combined, file_channel, file_agg, sep, domain_summary, redundancy, roles, feature_sets, audit):
    Path("docs").mkdir(exist_ok=True)
    report = Path("docs") / "TIME_FREQUENCY_FEATURE_COMPARISON_V1.md"
    freq_count = combined[combined["feature_domain"] == "frequency"]["feature_name"].nunique()
    time_count = combined[combined["feature_domain"] == "time"]["feature_name"].nunique()
    dom = domain_summary[domain_summary["sample_grain"] == "file_agg"]
    useful = dom["time_domain_usefulness"].value_counts().to_dict()
    primary_freq = roles[(roles["feature_domain"] == "frequency") & (roles["recommended_role"] == "primary_candidate")]
    aux_time = roles[(roles["feature_domain"] == "time") & (roles["recommended_role"] == "auxiliary_candidate")]
    qc_time = roles[(roles["feature_domain"] == "time") & (roles["recommended_role"] == "qc_only")]
    lines = [
        "# Time + Frequency Feature Comparison v1",
        "",
        "## Inputs",
        "",
        f"- Frequency feature table: `{args.frequency_dataset}`",
        f"- Frequency stability table: `{args.frequency_stability}`",
        f"- Time feature table: `{args.time_dataset}`",
        f"- Time stability table: `{args.time_stability}`",
        "",
        "## Scope",
        "",
        "- No machine learning was run.",
        "- No new features were extracted.",
        "- No TDMS/FFT/background contrast pipeline was rerun.",
        "- No plot is used as a substitute for CSV metrics.",
        "",
        "## Feature counts and grain",
        "",
        f"- Frequency features: {freq_count}",
        f"- Time features: {time_count}",
        f"- Main analysis grain: file_agg, because it reduces channel-replication leakage and matches later pilot ML table construction.",
        f"- File-channel matrix rows: {len(file_channel)}",
        f"- File-aggregated matrix rows: {len(file_agg)}",
        "",
        "## Key alignment audit",
        "",
        f"- Common group/file/channel keys after normalized file_id alignment: {audit['common_key_count']}",
        f"- Frequency-only keys: {audit['freq_only_key_count']}",
        f"- Time-only keys: {audit['time_only_key_count']}",
        f"- Note: {audit['note']}",
        "",
        "## Time-domain usefulness",
        "",
        f"- file_agg time usefulness counts: {useful}",
        "- Time-domain features do show separability in several tasks, but baseline/location features require caution.",
        "- Frequency features remain the main line because they map directly to the established high-frequency candidate bands and subbands.",
        "- Time-domain non-baseline distribution/variation features are useful as auxiliary checks and possible complementary features.",
        "",
        "## Roles",
        "",
        f"- Frequency primary candidates: {len(primary_freq)}",
        f"- Time auxiliary candidates: {len(aux_time)}",
        f"- Time QC-only features: {len(qc_time)}",
        "",
        "## Recommended feature sets",
        "",
        f"- frequency_core: {feature_sets['frequency_core']}",
        f"- time_auxiliary: {feature_sets['time_auxiliary']}",
        f"- combined_nonredundant: {feature_sets['combined_nonredundant']}",
        f"- qc_features: {feature_sets['qc_features']}",
        f"- excluded_baseline_risk: {feature_sets['excluded_baseline_risk']}",
        "",
        "## Redundancy",
        "",
        f"- Highly redundant pairs |corr| > 0.9: {len(redundancy)}",
        "- See `combined_feature_redundancy_summary.csv` for frequency-frequency, time-time, and time-frequency pairs.",
        "",
        "## Pilot ML recommendation",
        "",
        "- Use `frequency_core` as the baseline feature set.",
        "- Add `time_auxiliary` for a combined nonredundant candidate set.",
        "- Keep `qc_features` out of recognition features; use them for filtering or audit.",
        "- Keep baseline-risk features out of primary recognition interpretation even when AUC is high.",
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


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
