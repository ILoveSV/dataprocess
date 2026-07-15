import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import kruskal
from sklearn.metrics import roc_auc_score


EPS = 1e-30
CHANNELS = [f"channel{i}" for i in range(1, 13)]
MASKS = {
    "mask_all": {
        "type": "global",
        "exclude_global": [],
        "exclude_by_distance": {},
        "purpose": "original all-channel reference",
        "risk": "includes known channel9 failure in 5m groups",
    },
    "mask_hard_bad_by_group": {
        "type": "group-specific",
        "exclude_global": [],
        "exclude_by_distance": {"5m": ["channel9"]},
        "purpose": "simulate removing only the known bad channel where it occurred",
        "risk": "group-specific masking can encode distance-specific QC decisions and should not be used as a final modeling shortcut",
    },
    "mask_no_ch9_global": {
        "type": "global",
        "exclude_global": ["channel9"],
        "exclude_by_distance": {},
        "purpose": "fair modeling-oriented mask that removes channel9 everywhere",
        "risk": "removes potentially useful non-5m channel9 information to avoid 5m-specific leakage",
    },
    "mask_no_ch9_ch5_global": {
        "type": "global",
        "exclude_global": ["channel9", "channel5"],
        "exclude_by_distance": {},
        "purpose": "conservative comparison excluding confirmed channel9 risk and suspected channel5 risk",
        "risk": "may discard useful signal if channel5 is not actually faulty",
    },
    "mask_healthy_candidate": {
        "type": "global",
        "exclude_global": ["channel9", "channel5"],
        "exclude_by_distance": {},
        "purpose": "default healthy-channel candidate mask; currently equivalent to mask_no_ch9_ch5_global",
        "risk": "does not automatically infer any additional suspect channels",
    },
}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Channel Mask Sensitivity v1 from existing file/channel feature tables.")
    parser.add_argument("--frequency", default="analysis_out/feature_extraction_v2/candidate_feature_dataset_v2.csv")
    parser.add_argument("--time", default="analysis_out/time_domain_features_v1/time_domain_feature_dataset_v1.csv")
    parser.add_argument("--acf", default="analysis_out/acf_features_v1/acf_feature_dataset_v1.csv")
    parser.add_argument("--tf", default="analysis_out/time_frequency_stability_features_v1/tf_stability_feature_dataset_v1.csv")
    parser.add_argument("--output", default="analysis_out/channel_mask_sensitivity_v1")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    input_path = out / "combined_mask_input_features_v1.csv"
    matrix_path = out / "masked_feature_matrix_file_agg_v1.csv"

    write_json(out / "channel_mask_config_v1.json", MASKS)
    if args.force or not input_path.exists():
        combined, audit = load_combined_inputs(args)
        combined.to_csv(input_path, index=False, encoding="utf-8-sig")
        write_json(out / "channel_mask_input_audit_v1.json", audit)
    else:
        combined = pd.read_csv(input_path)
        audit = read_json(out / "channel_mask_input_audit_v1.json")

    if args.force or not matrix_path.exists():
        matrix = build_masked_matrix(combined)
        matrix.to_csv(matrix_path, index=False, encoding="utf-8-sig")
    else:
        matrix = pd.read_csv(matrix_path)

    roles = load_feature_roles()
    sep = build_separability(matrix, roles)
    sep.to_csv(out / "masked_feature_separability_summary_v1.csv", index=False, encoding="utf-8-sig")
    delta = build_delta(sep)
    delta.to_csv(out / "mask_sensitivity_delta_v1.csv", index=False, encoding="utf-8-sig")
    robustness = build_robustness(sep, delta)
    robustness.to_csv(out / "feature_robustness_by_mask_v1.csv", index=False, encoding="utf-8-sig")
    deps = build_channel_dependency(sep)
    deps.to_csv(out / "channel9_channel5_dependency_summary_v1.csv", index=False, encoding="utf-8-sig")
    write_json(out / "recommended_feature_sets_after_channel_mask_v1.json", recommended_sets(robustness, roles))
    write_report(out, combined, matrix, sep, delta, robustness, deps, audit)
    print(f"Channel Mask Sensitivity v1 output: {out}")


def load_combined_inputs(args):
    frames = []
    audit = {"inputs": {}, "skipped": []}
    specs = [
        ("frequency", Path(args.frequency)),
        ("time", Path(args.time)),
        ("acf", Path(args.acf)),
        ("tf", Path(args.tf)),
    ]
    for domain, path in specs:
        if not path.exists():
            audit["skipped"].append({"source_domain": domain, "source_file": str(path), "reason": "file not found"})
            continue
        try:
            df = pd.read_csv(path)
        except Exception as exc:
            audit["skipped"].append({"source_domain": domain, "source_file": str(path), "reason": f"read failed: {exc}"})
            continue
        missing = [c for c in ["group", "distance", "rpm", "file_id", "channel", "feature_name", "feature_value"] if c not in df.columns]
        if missing:
            audit["skipped"].append({"source_domain": domain, "source_file": str(path), "reason": f"missing columns: {missing}"})
            continue
        if domain == "frequency" and "analysis_mode" in df.columns:
            df = df[df["analysis_mode"].astype(str).str.lower().eq("strict")].copy()
        out = pd.DataFrame()
        out["source_domain"] = domain
        out["group"] = df["group"].astype(str)
        out["distance"] = df["distance"].astype(str)
        out["rpm"] = df["rpm"].astype(str)
        out["file_id"] = df["file_id"].astype(str).map(normalize_file_id)
        out["channel"] = df["channel"].astype(str)
        out["feature_name"] = make_feature_names(domain, df)
        out["feature_value"] = pd.to_numeric(df["feature_value"], errors="coerce")
        out["feature_type"] = df["feature_type"].astype(str) if "feature_type" in df.columns else ""
        out["unit"] = df["unit"].astype(str) if "unit" in df.columns else default_unit(domain)
        out["qc_flag"] = df["qc_flag"].astype(str) if "qc_flag" in df.columns else "UNKNOWN"
        out["source_file"] = str(path)
        out = out[out["feature_value"].notna()].copy()
        frames.append(out)
        audit["inputs"][domain] = {
            "source_file": str(path),
            "rows_loaded": int(len(out)),
            "n_groups": int(out["group"].nunique()),
            "n_files": int(out[["group", "file_id"]].drop_duplicates().shape[0]),
            "n_channels": int(out["channel"].nunique()),
            "n_features": int(out["feature_name"].nunique()),
        }
    if not frames:
        return pd.DataFrame(), audit
    return pd.concat(frames, ignore_index=True), audit


def make_feature_names(domain, df):
    if domain == "frequency":
        return "freq__" + df["feature_name"].astype(str)
    if domain == "time":
        return "time__" + df["feature_name"].astype(str)
    if domain == "acf":
        return "acf__" + df["feature_name"].astype(str)
    if domain == "tf":
        return "tf__" + df["band_id"].astype(str) + "__" + df["feature_name"].astype(str)
    return domain + "__" + df["feature_name"].astype(str)


def normalize_file_id(file_id):
    value = Path(str(file_id)).name
    if value.startswith("FFT_"):
        value = value[4:]
    return value


def default_unit(domain):
    if domain in {"frequency", "tf"}:
        return "dB_or_unitless"
    return "unitless"


def build_masked_matrix(combined):
    matrices = []
    for mask_name, spec in MASKS.items():
        cur = apply_mask(combined, spec)
        grouped = cur.groupby(["group", "distance", "rpm", "file_id", "feature_name"], as_index=False).agg(
            feature_value=("feature_value", "median"),
            feature_domain=("source_domain", "first"),
            feature_type=("feature_type", "first"),
            n_channels_used=("channel", "nunique"),
            excluded_channels=("channel", lambda s: excluded_for_sample(spec, cur.loc[s.index[0], "distance"])),
            qc_flag=("qc_flag", join_qc_series),
        )
        piv = grouped.pivot_table(index=["group", "distance", "rpm", "file_id"], columns="feature_name", values="feature_value", aggfunc="median").reset_index()
        channel_info = grouped.groupby(["group", "distance", "rpm", "file_id"], as_index=False).agg(
            n_channels_used=("n_channels_used", "median"),
            excluded_channels=("excluded_channels", first_nonempty),
            qc_flag=("qc_flag", join_qc_series),
        )
        piv = piv.merge(channel_info, on=["group", "distance", "rpm", "file_id"], how="left")
        piv.insert(0, "mask_name", mask_name)
        piv.insert(1, "sample_id", piv["mask_name"].astype(str) + "__" + piv["group"].astype(str) + "__" + piv["file_id"].astype(str))
        piv.insert(6, "aggregation_method", "median_across_retained_channels")
        piv["qc_warning"] = np.where(piv["n_channels_used"] < 8, "less_than_8_channels_used", "")
        matrices.append(piv)
    matrix = pd.concat(matrices, ignore_index=True)
    matrix.columns.name = None
    return matrix


def apply_mask(df, spec):
    excluded_global = set(spec.get("exclude_global", []))
    keep = ~df["channel"].isin(excluded_global)
    for distance, channels in spec.get("exclude_by_distance", {}).items():
        keep &= ~((df["distance"] == distance) & df["channel"].isin(channels))
    return df[keep].copy()


def excluded_for_sample(spec, distance):
    channels = list(spec.get("exclude_global", []))
    channels.extend(spec.get("exclude_by_distance", {}).get(str(distance), []))
    return ",".join(sorted(set(channels))) if channels else ""


def build_separability(matrix, roles):
    rows = []
    for mask_name, mask_df in matrix.groupby("mask_name"):
        for distance, group in mask_df.groupby("distance"):
            cur = group[group["rpm"].isin(["0Hz", "30Hz", "50Hz"])].copy()
            cur["label"] = np.where(cur["rpm"] == "0Hz", "0Hz", "active")
            rows.extend(sep_rows(mask_name, cur, "Task A active vs 0Hz", distance, "all", "label", roles))
            cur = group[group["rpm"].isin(["30Hz", "50Hz"])].copy()
            rows.extend(sep_rows(mask_name, cur, "Task B 30Hz vs 50Hz", distance, "30/50Hz", "rpm", roles))
        for rpm, group in mask_df.groupby("rpm"):
            rows.extend(sep_rows(mask_name, group, "Task C distance", "2/3/5m", rpm, "distance", roles))
        rows.extend(sep_rows(mask_name, mask_df[mask_df["rpm"].isin(["0Hz", "30Hz", "50Hz"])].copy(), "Task D rpm 3-class", "all", "0/30/50Hz", "rpm", roles))
    out = pd.DataFrame(rows)
    if not out.empty:
        out["separability_rank"] = out.groupby(["mask_name", "task_name"])["single_feature_auc_or_macro_auc"].rank(ascending=False, method="min")
    return out


def sep_rows(mask_name, data, task_name, distance_scope, rpm_scope, label_col, roles):
    meta = {"mask_name", "sample_id", "group", "distance", "rpm", "file_id", "aggregation_method", "n_channels_used", "excluded_channels", "qc_flag", "qc_warning", "label"}
    features = [c for c in data.columns if c not in meta]
    labels = sorted(data[label_col].dropna().astype(str).unique().tolist()) if label_col in data else []
    rows = []
    for feature in features:
        cur = data[[feature, label_col, "n_channels_used", "qc_warning"]].dropna(subset=[feature, label_col])
        domain = feature.split("__", 1)[0] if "__" in feature else "unknown"
        role = roles.get(feature, {})
        row = {
            "mask_name": mask_name,
            "task_name": task_name,
            "feature_domain": domain,
            "feature_name": feature,
            "feature_type": role.get("feature_type", infer_type(feature)),
            "distance_scope": distance_scope,
            "rpm_scope": rpm_scope,
            "n_samples": int(len(cur)),
            "class_labels": json.dumps(labels),
            "median_by_class": "{}",
            "iqr_by_class": "{}",
            "effect_size": np.nan,
            "overlap_score": np.nan,
            "single_feature_auc_or_macro_auc": np.nan,
            "separability_rank": np.nan,
            "n_channels_used_median": float(cur["n_channels_used"].median()) if not cur.empty else np.nan,
            "qc_warning": join_qc_series(cur["qc_warning"]) if not cur.empty else "",
            "background_relative_flag": int("tf_background_" in feature),
            "recommended_role": role.get("recommended_role", ""),
            "notes": role.get("reason", ""),
            "skipped_reason": "",
        }
        counts = cur[label_col].astype(str).value_counts() if label_col in cur else pd.Series(dtype=int)
        if len(counts) < 2 or counts.min() < 3:
            row["skipped_reason"] = "need at least 2 classes and 3 samples per class"
            rows.append(row)
            continue
        x = pd.to_numeric(cur[feature], errors="coerce")
        y = cur[label_col].astype(str)
        ok = x.notna() & y.notna()
        x, y = x[ok], y[ok]
        grouped = pd.DataFrame({"x": x, "y": y}).groupby("y")["x"]
        row["median_by_class"] = json.dumps({str(k): float(v) for k, v in grouped.median().to_dict().items()})
        row["iqr_by_class"] = json.dumps({str(k): float(v) for k, v in (grouped.quantile(0.75) - grouped.quantile(0.25)).to_dict().items()})
        if counts.size == 2:
            labs = sorted(counts.index.astype(str).tolist())
            a, b = x[y == labs[0]], x[y == labs[1]]
            row["effect_size"] = robust_effect(a, b)
            row["overlap_score"] = overlap_score(a, b)
            row["single_feature_auc_or_macro_auc"] = max_auc(y, x)
        else:
            vals = [x[y == lab] for lab in sorted(counts.index.astype(str).tolist())]
            try:
                stat, _ = kruskal(*vals)
                row["effect_size"] = float(stat / max(len(x) - 1, 1))
            except Exception:
                pass
            row["single_feature_auc_or_macro_auc"] = macro_auc(y, x)
        rows.append(row)
    return rows


def build_delta(sep):
    base = sep[sep["mask_name"] == "mask_all"].copy()
    others = sep[sep["mask_name"] != "mask_all"].copy()
    keys = ["task_name", "feature_name", "feature_domain", "distance_scope", "rpm_scope"]
    merged = others.merge(base[keys + ["single_feature_auc_or_macro_auc", "effect_size", "separability_rank"]], on=keys, how="left", suffixes=("_compared", "_baseline"))
    rows = []
    for _, row in merged.iterrows():
        auc_b = row["single_feature_auc_or_macro_auc_baseline"]
        auc_c = row["single_feature_auc_or_macro_auc_compared"]
        eff_b = row["effect_size_baseline"]
        eff_c = row["effect_size_compared"]
        auc_delta = auc_c - auc_b if pd.notna(auc_b) and pd.notna(auc_c) else np.nan
        rel = effect_relative_change(eff_b, eff_c)
        rank_shift = row["separability_rank_compared"] - row["separability_rank_baseline"] if pd.notna(row["separability_rank_compared"]) and pd.notna(row["separability_rank_baseline"]) else np.nan
        conclusion, reason = sensitivity_label(auc_delta, rel, rank_shift)
        rows.append({
            "task_name": row["task_name"],
            "feature_name": row["feature_name"],
            "feature_domain": row["feature_domain"],
            "distance_scope": row["distance_scope"],
            "rpm_scope": row["rpm_scope"],
            "baseline_mask": "mask_all",
            "compared_mask": row["mask_name"],
            "auc_baseline": auc_b,
            "auc_compared": auc_c,
            "auc_delta": auc_delta,
            "effect_size_baseline": eff_b,
            "effect_size_compared": eff_c,
            "effect_size_relative_change": rel,
            "rank_baseline": row["separability_rank_baseline"],
            "rank_compared": row["separability_rank_compared"],
            "rank_shift": rank_shift,
            "conclusion_stability": conclusion,
            "reason": reason,
        })
    return pd.DataFrame(rows)


def build_robustness(sep, delta):
    best_all = sep[(sep["mask_name"] == "mask_all") & sep["single_feature_auc_or_macro_auc"].notna()].sort_values("single_feature_auc_or_macro_auc", ascending=False)
    rows = []
    for feature, group in best_all.groupby("feature_name", sort=False):
        best = group.iloc[0]
        task = best["task_name"]
        scope = (best["distance_scope"], best["rpm_scope"])
        vals = {}
        for mask in MASKS:
            cur = sep[(sep["mask_name"] == mask) & (sep["feature_name"] == feature) & (sep["task_name"] == task) & (sep["distance_scope"] == scope[0]) & (sep["rpm_scope"] == scope[1])]
            vals[mask] = float(cur["single_feature_auc_or_macro_auc"].iloc[0]) if not cur.empty and pd.notna(cur["single_feature_auc_or_macro_auc"].iloc[0]) else np.nan
        auc_all = vals.get("mask_all", np.nan)
        auc_no9 = vals.get("mask_no_ch9_global", np.nan)
        auc_no95 = vals.get("mask_no_ch9_ch5_global", np.nan)
        valid = [v for v in vals.values() if pd.notna(v)]
        auc_min = float(np.nanmin(valid)) if valid else np.nan
        auc_drop = float(auc_all - auc_min) if pd.notna(auc_all) and pd.notna(auc_min) else np.nan
        dcur = delta[(delta["feature_name"] == feature) & (delta["task_name"] == task) & (delta["distance_scope"] == scope[0]) & (delta["rpm_scope"] == scope[1])]
        eff_drop = max_effect_drop(dcur)
        ch9_dep = pd.notna(auc_all) and pd.notna(auc_no9) and (auc_all - auc_no9 > 0.10)
        ch5_dep = pd.notna(auc_no9) and pd.notna(auc_no95) and (auc_no9 - auc_no95 > 0.10)
        stable = pd.notna(auc_drop) and auc_drop <= 0.05 and not ch9_dep and not ch5_dep
        if stable and auc_min >= 0.75:
            status = "robust_keep"
        elif auc_drop <= 0.10 if pd.notna(auc_drop) else False:
            status = "keep_with_warning"
        elif ch9_dep or ch5_dep or (pd.notna(auc_drop) and auc_drop <= 0.20):
            status = "downgrade"
        else:
            status = "reject"
        rows.append({
            "feature_name": feature,
            "feature_domain": best["feature_domain"],
            "feature_type": best["feature_type"],
            "best_task": task,
            "distance_scope": scope[0],
            "rpm_scope": scope[1],
            "auc_mask_all": auc_all,
            "auc_mask_no_ch9_global": auc_no9,
            "auc_mask_no_ch9_ch5_global": auc_no95,
            "auc_min_across_masks": auc_min,
            "auc_max_drop": auc_drop,
            "effect_size_max_drop": eff_drop,
            "stable_across_masks_flag": bool(stable),
            "ch9_dependency_flag": bool(ch9_dep),
            "ch5_dependency_flag": bool(ch5_dep),
            "recommended_status": status,
            "reason": robustness_reason(status, auc_drop, ch9_dep, ch5_dep),
        })
    return pd.DataFrame(rows)


def build_channel_dependency(sep):
    rows = []
    best_all = sep[(sep["mask_name"] == "mask_all") & sep["single_feature_auc_or_macro_auc"].notna()].sort_values("single_feature_auc_or_macro_auc", ascending=False)
    for feature, group in best_all.groupby("feature_name", sort=False):
        best = group.iloc[0]
        task = best["task_name"]
        scope = (best["distance_scope"], best["rpm_scope"])
        def auc(mask):
            cur = sep[(sep["mask_name"] == mask) & (sep["feature_name"] == feature) & (sep["task_name"] == task) & (sep["distance_scope"] == scope[0]) & (sep["rpm_scope"] == scope[1])]
            return float(cur["single_feature_auc_or_macro_auc"].iloc[0]) if not cur.empty and pd.notna(cur["single_feature_auc_or_macro_auc"].iloc[0]) else np.nan
        a0, a9, a95 = auc("mask_all"), auc("mask_no_ch9_global"), auc("mask_no_ch9_ch5_global")
        d9 = a9 - a0 if pd.notna(a0) and pd.notna(a9) else np.nan
        d95 = a95 - a9 if pd.notna(a9) and pd.notna(a95) else np.nan
        rows.append({
            "feature_name": feature,
            "feature_domain": best["feature_domain"],
            "task_name": task,
            "distance_scope": scope[0],
            "rpm_scope": scope[1],
            "auc_mask_all": a0,
            "auc_no_ch9": a9,
            "auc_no_ch9_ch5": a95,
            "delta_no_ch9": d9,
            "delta_no_ch9_ch5": d95,
            "ch9_dependency_level": dependency_level(d9),
            "ch5_dependency_level": dependency_level(d95),
            "interpretation_note": dependency_note(d9, d95),
        })
    return pd.DataFrame(rows)


def recommended_sets(robustness, roles):
    def pick(domain, statuses):
        return robustness[(robustness["feature_domain"] == domain) & robustness["recommended_status"].isin(statuses)]["feature_name"].tolist()
    qc = [k for k, v in roles.items() if v.get("recommended_role") == "qc_only"]
    return {
        "robust_frequency_core": pick("freq", ["robust_keep", "keep_with_warning"]),
        "robust_time_auxiliary": pick("time", ["robust_keep", "keep_with_warning"]),
        "robust_acf_auxiliary": pick("acf", ["robust_keep", "keep_with_warning"]),
        "robust_tf_auxiliary": pick("tf", ["robust_keep", "keep_with_warning"]),
        "qc_features": qc,
        "downgraded_due_to_ch9_dependency": robustness[robustness["ch9_dependency_flag"]]["feature_name"].tolist(),
        "downgraded_due_to_ch5_dependency": robustness[robustness["ch5_dependency_flag"]]["feature_name"].tolist(),
        "rejected_mask_unstable": robustness[robustness["recommended_status"] == "reject"]["feature_name"].tolist(),
    }


def load_feature_roles():
    roles = {}
    paths = [
        Path("analysis_out/time_frequency_feature_comparison_v1/feature_role_assignment_v1.csv"),
        Path("analysis_out/acf_features_v1/acf_feature_role_assignment_v1.csv"),
        Path("analysis_out/time_frequency_stability_features_v1/tf_stability_feature_role_assignment_v1.csv"),
    ]
    for path in paths:
        if not path.exists():
            continue
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            name = str(row.get("feature_name", ""))
            if "band_id" in row and pd.notna(row.get("band_id")):
                name = f"tf__{row['band_id']}__{name}"
            elif path.name == "feature_role_assignment_v1.csv":
                domain = str(row.get("feature_domain", ""))
                prefix = {"frequency": "freq", "time": "time"}.get(domain, domain)
                name = name if name.startswith(prefix + "__") else f"{prefix}__{name}"
            elif path.name.startswith("acf"):
                name = name if name.startswith("acf__") else f"acf__{name}"
            roles[name] = {
                "feature_type": str(row.get("feature_type", "")),
                "recommended_role": str(row.get("recommended_role", "")),
                "reason": str(row.get("reason", "")),
            }
    return roles


def write_report(out, combined, matrix, sep, delta, robustness, deps, audit):
    report = Path("docs/CHANNEL_MASK_SENSITIVITY_V1.md")
    report.parent.mkdir(parents=True, exist_ok=True)
    role_counts = robustness["recommended_status"].value_counts().to_dict()
    robust_freq = robustness[(robustness["feature_domain"] == "freq") & robustness["recommended_status"].isin(["robust_keep", "keep_with_warning"])]["feature_name"].head(20).tolist()
    robust_tf = robustness[(robustness["feature_domain"] == "tf") & robustness["recommended_status"].isin(["robust_keep", "keep_with_warning"])]["feature_name"].head(20).tolist()
    ch9 = int(robustness["ch9_dependency_flag"].sum())
    ch5 = int(robustness["ch5_dependency_flag"].sum())
    top_unstable = robustness[robustness["recommended_status"].isin(["downgrade", "reject"])].head(20)["feature_name"].tolist()
    lines = [
        "# Channel Mask Sensitivity v1",
        "",
        "## Purpose",
        "",
        "Channel9 is treated as a confirmed bad/suspect channel in 5m groups, and channel5 is treated as a suspect sensitive channel. This analysis re-aggregates existing file_id x channel feature tables under several channel masks to check whether conclusions depend on those channels.",
        "",
        "## Inputs",
        "",
    ]
    for domain, info in audit.get("inputs", {}).items():
        lines.append(f"- {domain}: `{info['source_file']}` rows={info['rows_loaded']} features={info['n_features']}")
    lines += [
        "",
        "## Masks",
        "",
    ]
    for name, spec in MASKS.items():
        lines.append(f"- `{name}`: {spec['purpose']}; excludes global={spec['exclude_global']}, by_distance={spec['exclude_by_distance']}")
    lines += [
        "",
        "## Outputs and Coverage",
        "",
        f"- Combined input rows: {len(combined)}",
        f"- Masked file-level matrix rows: {len(matrix)}",
        f"- Separability rows: {len(sep)}",
        f"- Robustness status counts: {role_counts}",
        "",
        "## Channel9 / Channel5 Dependence",
        "",
        f"- Features with channel9 dependency flag: {ch9}",
        f"- Features with channel5 dependency flag: {ch5}",
        "- `mask_no_ch9_global` is recommended as the main follow-up analysis mask because it avoids distance-specific channel removal.",
        "- `mask_no_ch9_ch5_global` should be kept as the conservative comparison mask.",
        "",
        "## Frequency / PSD Candidate Robustness",
        "",
        ", ".join(robust_freq) if robust_freq else "No robust frequency features found by current rules.",
        "",
        "## TF Stability Candidate Robustness",
        "",
        ", ".join(robust_tf) if robust_tf else "No robust TF features found by current rules.",
        "",
        "## Downgrade / Reject Examples",
        "",
        ", ".join(top_unstable) if top_unstable else "None by current rules.",
        "",
        "## Interpretation",
        "",
        "Features that remain strong under `mask_no_ch9_global` are not dependent on channel9. Features that remain strong under `mask_no_ch9_ch5_global` are also not dependent on channel5. Features that collapse after channel removal are marked as dependency or unstable risk, not interpreted as physical target response.",
        "",
        "## Scope Guard",
        "",
        "- No machine learning was run.",
        "- No new signal features were extracted.",
        "- No TDMS/FFT/background contrast processing was rerun.",
        "- No original data or old outputs were deleted.",
        "- No additional bad channels were inferred automatically.",
        "- Group-specific masks are treated as QC sensitivity checks, not final modeling conclusions.",
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def robust_effect(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    denom = 0.5 * ((np.nanpercentile(a, 75) - np.nanpercentile(a, 25)) + (np.nanpercentile(b, 75) - np.nanpercentile(b, 25))) + EPS
    return float((np.nanmedian(b) - np.nanmedian(a)) / denom)


def overlap_score(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    lo = max(np.nanpercentile(a, 25), np.nanpercentile(b, 25))
    hi = min(np.nanpercentile(a, 75), np.nanpercentile(b, 75))
    span = max(np.nanpercentile(np.concatenate([a, b]), 75) - np.nanpercentile(np.concatenate([a, b]), 25), EPS)
    return float(max(0.0, hi - lo) / span)


def max_auc(y, x):
    y = pd.Series(y).astype(str)
    x = pd.Series(x).astype(float)
    labs = sorted(y.unique())
    if len(labs) != 2:
        return np.nan
    yy = (y == labs[1]).astype(int)
    try:
        auc = roc_auc_score(yy, x)
        return float(max(auc, 1.0 - auc))
    except Exception:
        return np.nan


def macro_auc(y, x):
    y = pd.Series(y).astype(str)
    x = pd.Series(x).astype(float)
    vals = []
    for lab in sorted(y.unique()):
        yy = (y == lab).astype(int)
        try:
            auc = roc_auc_score(yy, x)
            vals.append(max(auc, 1.0 - auc))
        except Exception:
            pass
    return float(np.mean(vals)) if vals else np.nan


def sensitivity_label(auc_delta, effect_change, rank_shift):
    reasons = []
    score = "stable"
    if pd.notna(auc_delta):
        ad = abs(auc_delta)
        if ad > 0.20:
            score = "unstable"
        elif ad > 0.10:
            score = "sensitive"
        elif ad > 0.05:
            score = "mildly_sensitive"
        reasons.append(f"auc_delta={auc_delta:.3g}")
    if pd.notna(effect_change) and effect_change < -0.30 and score in {"stable", "mildly_sensitive"}:
        score = "sensitive"
        reasons.append("effect_size_drop_gt_30pct")
    if pd.notna(rank_shift) and abs(rank_shift) > 50:
        reasons.append("rank_shift_warning")
    return score, "; ".join(reasons)


def effect_relative_change(base, compared):
    if pd.isna(base) or pd.isna(compared) or abs(base) < EPS:
        return np.nan
    return float((abs(compared) - abs(base)) / (abs(base) + EPS))


def max_effect_drop(delta):
    vals = pd.to_numeric(delta["effect_size_relative_change"], errors="coerce")
    return float(vals.min()) if not vals.dropna().empty else np.nan


def dependency_level(delta):
    if pd.isna(delta):
        return "unknown"
    drop = -delta
    if drop > 0.20:
        return "high"
    if drop > 0.10:
        return "medium"
    return "low"


def dependency_note(d9, d95):
    if dependency_level(d9) in {"high", "medium"} or dependency_level(d95) in {"high", "medium"}:
        return "performance drops after channel removal; possible channel dependency or contamination risk"
    return "robust under channel9/channel5 masks by current AUC rule"


def robustness_reason(status, auc_drop, ch9_dep, ch5_dep):
    parts = [f"status={status}"]
    if pd.notna(auc_drop):
        parts.append(f"auc_max_drop={auc_drop:.3g}")
    if ch9_dep:
        parts.append("channel9 dependency")
    if ch5_dep:
        parts.append("channel5 dependency")
    return "; ".join(parts)


def infer_type(feature):
    if feature.startswith("freq__"):
        return "frequency"
    if feature.startswith("time__"):
        return "time"
    if feature.startswith("acf__"):
        return "acf"
    if feature.startswith("tf__"):
        return "time_frequency_stability"
    return "unknown"


def join_qc_series(values):
    vals = sorted({str(v) for v in values if str(v) and str(v) not in {"OK", "nan"}})
    return ";".join(vals) if vals else "OK"


def first_nonempty(values):
    for value in values:
        if str(value):
            return str(value)
    return ""


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else {}


if __name__ == "__main__":
    main()
