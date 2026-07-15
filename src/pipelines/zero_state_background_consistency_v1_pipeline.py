import argparse
import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import kruskal
from sklearn.metrics import roc_auc_score


EPS = 1e-30
ZERO_GROUPS = ["2m0hz", "3m0hz", "5m0hz"]
CORE_MASKS = ["mask_all", "mask_no_ch9_global", "mask_no_ch9_ch5_global"]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Zero-State Background Consistency v1.")
    parser.add_argument("--mask-matrix", default="analysis_out/channel_mask_sensitivity_v1/masked_feature_matrix_file_agg_v1.csv")
    parser.add_argument("--mask-config", default="analysis_out/channel_mask_sensitivity_v1/channel_mask_config_v1.json")
    parser.add_argument("--recommended-after-mask", default="analysis_out/channel_mask_sensitivity_v1/recommended_feature_sets_after_channel_mask_v1.json")
    parser.add_argument("--channel-correlation-matrix", default="analysis_out/channel_correlation_features_v1/channel_correlation_feature_matrix_file_v1.csv")
    parser.add_argument("--channel-correlation-roles", default="analysis_out/channel_correlation_features_v1/channel_correlation_feature_role_assignment_v1.csv")
    parser.add_argument("--output", default="analysis_out/zero_state_background_consistency_v1")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    matrix, audit = build_zero_state_matrix(args)
    matrix.to_csv(out / "zero_state_feature_matrix_by_mask_v1.csv", index=False, encoding="utf-8-sig")
    write_json(out / "zero_state_background_input_audit_v1.json", audit)

    summary = build_consistency_summary(matrix)
    summary.to_csv(out / "zero_state_background_consistency_summary_v1.csv", index=False, encoding="utf-8-sig")
    pairwise = build_pairwise_delta(matrix)
    pairwise.to_csv(out / "zero_state_pairwise_background_delta_v1.csv", index=False, encoding="utf-8-sig")
    domain = build_domain_summary(summary)
    domain.to_csv(out / "zero_state_background_domain_summary_v1.csv", index=False, encoding="utf-8-sig")
    mask_effect = build_mask_effect(summary)
    mask_effect.to_csv(out / "zero_state_mask_effect_summary_v1.csv", index=False, encoding="utf-8-sig")
    risk = build_risk_features(summary)
    risk.to_csv(out / "zero_state_background_risk_features_v1.csv", index=False, encoding="utf-8-sig")
    impact = build_impact_table(summary, risk, args.recommended_after_mask)
    impact.to_csv(out / "zero_state_background_impact_on_previous_findings_v1.csv", index=False, encoding="utf-8-sig")
    write_report(out, matrix, summary, domain, mask_effect, risk, impact, audit)
    print(f"Zero-State Background Consistency v1 output: {out}")


def build_zero_state_matrix(args):
    audit = {"inputs": {}, "skipped": []}
    mask_path = Path(args.mask_matrix)
    if not mask_path.exists():
        raise FileNotFoundError(f"Required mask matrix not found: {mask_path}")
    mask_df = pd.read_csv(mask_path)
    mask_df["group_norm"] = mask_df["group"].astype(str).str.lower()
    zero = mask_df[mask_df["group_norm"].isin(ZERO_GROUPS) & mask_df["mask_name"].isin(CORE_MASKS)].copy()
    zero = zero.drop(columns=["group_norm"], errors="ignore")
    audit["inputs"]["masked_feature_matrix"] = {
        "path": str(mask_path),
        "rows_read": int(len(mask_df)),
        "zero_rows_used": int(len(zero)),
        "masks_used": sorted(zero["mask_name"].unique().tolist()),
    }

    frames = [zero]
    cc_path = Path(args.channel_correlation_matrix)
    if cc_path.exists():
        cc = pd.read_csv(cc_path)
        cc["group_norm"] = cc["group"].astype(str).str.lower()
        cc = cc[cc["group_norm"].isin(ZERO_GROUPS)].copy()
        if not cc.empty:
            meta = {"sample_id", "group", "distance", "rpm", "file_id", "qc_flag", "group_norm"}
            feature_cols = [c for c in cc.columns if c not in meta]
            cc = cc.rename(columns={c: f"channel_structure__{c}" for c in feature_cols})
            cc.insert(0, "mask_name", "mask_all")
            cc.insert(6, "aggregation_method", "file_level_channel_structure")
            cc["n_channels_used"] = np.nan
            cc["excluded_channels"] = ""
            cc["qc_warning"] = ""
            cc = cc.drop(columns=["group_norm"], errors="ignore")
            frames.append(cc)
        audit["inputs"]["channel_correlation_matrix"] = {
            "path": str(cc_path),
            "zero_rows_used": int(len(cc)),
            "mask_note": "channel-structure features are included under mask_all only; masked channel-structure re-computation was not fabricated",
        }
    else:
        audit["skipped"].append({"input": str(cc_path), "reason": "channel correlation matrix not found"})

    matrix = pd.concat(frames, ignore_index=True, sort=False)
    matrix = matrix[matrix["rpm"].astype(str).str.lower().eq("0hz")].copy()
    return matrix, audit


def build_consistency_summary(matrix):
    rows = []
    meta = {"mask_name", "sample_id", "group", "distance", "rpm", "file_id", "aggregation_method", "n_channels_used", "excluded_channels", "qc_flag", "qc_warning"}
    for mask_name, mask_df in matrix.groupby("mask_name"):
        features = [c for c in mask_df.columns if c not in meta]
        for feature in features:
            cur = mask_df[["group", "distance", feature]].dropna()
            if cur.empty:
                continue
            by_group = {g: pd.to_numeric(cur[cur["group"].str.lower() == g][feature], errors="coerce").dropna() for g in ZERO_GROUPS}
            if any(len(v) == 0 for v in by_group.values()):
                continue
            med = {g: float(v.median()) for g, v in by_group.items()}
            iqr = {g: float(v.quantile(0.75) - v.quantile(0.25)) for g, v in by_group.items()}
            pair_effects = []
            pair_deltas = []
            pair_overlaps = []
            for a, b in combinations(ZERO_GROUPS, 2):
                pair_effects.append(abs(robust_effect(by_group[a], by_group[b])))
                pair_deltas.append(abs(med[b] - med[a]))
                pair_overlaps.append(overlap_score(by_group[a], by_group[b]))
            labels = cur["group"].astype(str).str.lower()
            values = pd.to_numeric(cur[feature], errors="coerce")
            ok = values.notna()
            auc = macro_auc(labels[ok], values[ok])
            k_eff = kruskal_effect([by_group[g] for g in ZERO_GROUPS])
            bg_range = max(med.values()) - min(med.values())
            bg_cv = float(np.std(list(med.values()), ddof=1) / (abs(np.mean(list(med.values()))) + EPS))
            level = consistency_level(auc, max(pair_effects), float(np.mean(pair_overlaps)))
            rows.append({
                "mask_name": mask_name,
                "feature_domain": feature_domain(feature),
                "feature_name": feature,
                "feature_type": feature_type(feature),
                "n_samples_total": int(sum(len(v) for v in by_group.values())),
                "n_samples_by_group": json.dumps({g: int(len(v)) for g, v in by_group.items()}),
                "median_2m0hz": med["2m0hz"],
                "median_3m0hz": med["3m0hz"],
                "median_5m0hz": med["5m0hz"],
                "iqr_2m0hz": iqr["2m0hz"],
                "iqr_3m0hz": iqr["3m0hz"],
                "iqr_5m0hz": iqr["5m0hz"],
                "background_range": bg_range,
                "background_cv": bg_cv,
                "max_pairwise_effect_size": float(max(pair_effects)),
                "max_pairwise_median_delta": float(max(pair_deltas)),
                "overlap_score_summary": float(np.mean(pair_overlaps)),
                "auc_distance_3class_or_macro_auc": auc,
                "kruskal_or_anova_effect": k_eff,
                "consistency_level": level,
                "notes": consistency_note(level, auc),
            })
    return pd.DataFrame(rows)


def build_pairwise_delta(matrix):
    rows = []
    meta = {"mask_name", "sample_id", "group", "distance", "rpm", "file_id", "aggregation_method", "n_channels_used", "excluded_channels", "qc_flag", "qc_warning"}
    for mask_name, mask_df in matrix.groupby("mask_name"):
        features = [c for c in mask_df.columns if c not in meta]
        for feature in features:
            for a, b in combinations(ZERO_GROUPS, 2):
                va = pd.to_numeric(mask_df[mask_df["group"].str.lower() == a][feature], errors="coerce").dropna()
                vb = pd.to_numeric(mask_df[mask_df["group"].str.lower() == b][feature], errors="coerce").dropna()
                if len(va) < 3 or len(vb) < 3:
                    continue
                auc = max_auc(pd.Series([a] * len(va) + [b] * len(vb)), pd.concat([va, vb], ignore_index=True))
                effect = robust_effect(va, vb)
                overlap = overlap_score(va, vb)
                mismatch = bool(abs(effect) > 1.5 or (pd.notna(auc) and auc > 0.75) or overlap < 0.25)
                rows.append({
                    "mask_name": mask_name,
                    "feature_domain": feature_domain(feature),
                    "feature_name": feature,
                    "pair": f"{a}_vs_{b}",
                    "median_a": float(va.median()),
                    "median_b": float(vb.median()),
                    "median_delta": float(vb.median() - va.median()),
                    "effect_size": effect,
                    "overlap_score": overlap,
                    "single_feature_auc": auc,
                    "background_mismatch_flag": mismatch,
                    "notes": "AUC/effect indicates 0Hz background difference, not target response" if mismatch else "",
                })
    return pd.DataFrame(rows)


def build_domain_summary(summary):
    rows = []
    for (mask, domain), group in summary.groupby(["mask_name", "feature_domain"]):
        counts = group["consistency_level"].value_counts().to_dict()
        worst = group.sort_values("auc_distance_3class_or_macro_auc", ascending=False)["feature_name"].head(8).tolist()
        best = group.sort_values(["consistency_level", "auc_distance_3class_or_macro_auc"], ascending=[True, True])["feature_name"].head(8).tolist()
        rows.append({
            "mask_name": mask,
            "feature_domain": domain,
            "n_features": int(len(group)),
            "n_high_consistency": int(counts.get("high", 0)),
            "n_medium_consistency": int(counts.get("medium", 0)),
            "n_low_consistency": int(counts.get("low", 0)),
            "n_inconsistent": int(counts.get("inconsistent", 0)),
            "worst_features": json.dumps(worst, ensure_ascii=False),
            "best_consistent_features": json.dumps(best, ensure_ascii=False),
            "interpretation": domain_interpretation(domain, counts),
        })
    return pd.DataFrame(rows)


def build_mask_effect(summary):
    rows = []
    all_features = sorted(summary["feature_name"].unique().tolist())
    for feature in all_features:
        cur = summary[summary["feature_name"] == feature]
        def rec(mask):
            hit = cur[cur["mask_name"] == mask]
            return hit.iloc[0] if not hit.empty else None
        a = rec("mask_all")
        n9 = rec("mask_no_ch9_global")
        n95 = rec("mask_no_ch9_ch5_global")
        if a is None:
            continue
        auc_all = val(a, "auc_distance_3class_or_macro_auc")
        auc_n9 = val(n9, "auc_distance_3class_or_macro_auc")
        auc_n95 = val(n95, "auc_distance_3class_or_macro_auc")
        d9 = auc_n9 - auc_all if pd.notna(auc_all) and pd.notna(auc_n9) else np.nan
        d95 = auc_n95 - auc_n9 if pd.notna(auc_n9) and pd.notna(auc_n95) else np.nan
        red9 = pd.notna(d9) and d9 < -0.05
        red5 = pd.notna(d95) and d95 < -0.05
        rows.append({
            "feature_domain": feature_domain(feature),
            "feature_name": feature,
            "consistency_mask_all": a["consistency_level"],
            "consistency_no_ch9": n9["consistency_level"] if n9 is not None else "not_available",
            "consistency_no_ch9_ch5": n95["consistency_level"] if n95 is not None else "not_available",
            "auc_all": auc_all,
            "auc_no_ch9": auc_n9,
            "auc_no_ch9_ch5": auc_n95,
            "auc_delta_no_ch9": d9,
            "auc_delta_no_ch9_ch5": d95,
            "background_mismatch_reduced_by_ch9_mask": bool(red9),
            "background_mismatch_reduced_by_ch5_mask": bool(red5),
            "conclusion": mask_effect_conclusion(red9, red5, auc_all, auc_n95),
        })
    return pd.DataFrame(rows)


def build_risk_features(summary):
    rows = []
    for _, row in summary.iterrows():
        risk, usage, reason = risk_level(row)
        rows.append({
            "feature_name": row["feature_name"],
            "feature_domain": row["feature_domain"],
            "mask_name": row["mask_name"],
            "background_consistency_level": row["consistency_level"],
            "risk_level": risk,
            "recommended_usage": usage,
            "reason": reason,
        })
    return pd.DataFrame(rows)


def build_impact_table(summary, risk, recommended_path):
    recommended = read_json(Path(recommended_path))
    groups = {
        "robust_frequency_core": recommended.get("robust_frequency_core", []),
        "robust_time_auxiliary": recommended.get("robust_time_auxiliary", []),
        "robust_acf_auxiliary": recommended.get("robust_acf_auxiliary", []),
        "robust_tf_auxiliary": recommended.get("robust_tf_auxiliary", []),
    }
    features = ["freq__band_50_100k", "freq__band_100_200k"]
    roles = {}
    for role, vals in groups.items():
        for feature in vals:
            roles[feature] = role
            features.append(feature)
    features = sorted(set(features))
    rows = []
    main = risk[risk["mask_name"] == "mask_no_ch9_global"].copy()
    fallback = risk[risk["mask_name"] == "mask_all"].copy()
    for feature in features:
        r = main[main["feature_name"] == feature]
        if r.empty:
            r = fallback[fallback["feature_name"] == feature]
        if r.empty:
            rows.append({
                "feature_name": feature,
                "feature_domain": feature_domain(feature),
                "previously_recommended_role": roles.get(feature, "explicit_check"),
                "zero_state_background_risk": "not_available",
                "impact_on_distance_interpretation": "unknown",
                "impact_on_active_vs_background_interpretation": "unknown",
                "recommended_action": "manual_review",
                "notes": "feature not found in zero-state summary",
            })
            continue
        rr = r.iloc[0]
        action = impact_action(rr["risk_level"])
        rows.append({
            "feature_name": feature,
            "feature_domain": rr["feature_domain"],
            "previously_recommended_role": roles.get(feature, "explicit_check"),
            "zero_state_background_risk": rr["risk_level"],
            "impact_on_distance_interpretation": distance_impact(rr["risk_level"]),
            "impact_on_active_vs_background_interpretation": active_impact(rr["risk_level"]),
            "recommended_action": action,
            "notes": rr["reason"],
        })
    return pd.DataFrame(rows)


def write_report(out, matrix, summary, domain, mask_effect, risk, impact, audit):
    report = Path("docs/ZERO_STATE_BACKGROUND_CONSISTENCY_V1.md")
    report.parent.mkdir(parents=True, exist_ok=True)
    main = summary[summary["mask_name"] == "mask_no_ch9_global"]
    counts = main["consistency_level"].value_counts().to_dict()
    worst_domains = domain[domain["mask_name"] == "mask_no_ch9_global"].sort_values("n_inconsistent", ascending=False)
    improved_ch9 = int(mask_effect["background_mismatch_reduced_by_ch9_mask"].sum()) if not mask_effect.empty else 0
    improved_ch5 = int(mask_effect["background_mismatch_reduced_by_ch5_mask"].sum()) if not mask_effect.empty else 0
    high_risk = risk[(risk["mask_name"] == "mask_no_ch9_global") & risk["risk_level"].isin(["high_background_risk", "reject_for_distance_interpretation"])].head(20)
    impact_counts = impact["recommended_action"].value_counts().to_dict() if not impact.empty else {}
    lines = [
        "# Zero-State Background Consistency v1",
        "",
        "## Purpose",
        "",
        "Previous analyses mainly used same-distance active vs 0Hz background subtraction, such as 2m30Hz vs 2m0Hz. This analysis checks whether 2m0Hz, 3m0Hz, and 5m0Hz are mutually consistent zero-state backgrounds.",
        "",
        "## Groups Analyzed",
        "",
        "- 2m0hz",
        "- 3m0hz",
        "- 5m0hz",
        "",
        "No 30Hz or 50Hz active groups are included in the main analysis.",
        "",
        "## Inputs",
        "",
        f"- Mask matrix: `{audit.get('inputs', {}).get('masked_feature_matrix', {}).get('path', 'UNKNOWN')}`",
        f"- Channel-structure reference: `{audit.get('inputs', {}).get('channel_correlation_matrix', {}).get('path', 'skipped')}`",
        "",
        "## Mask Strategy",
        "",
        "- `mask_all`: historical all-channel reference.",
        "- `mask_no_ch9_global`: current main QC convention for comparison.",
        "- `mask_no_ch9_ch5_global`: conservative control.",
        "- Channel-structure features are included under `mask_all` only because they are already file-level array features; masked channel-structure values were not fabricated.",
        "",
        "## Overall Background Consistency",
        "",
        f"- Under `mask_no_ch9_global`, consistency counts are: {counts}",
        "- A high AUC here is a warning, not a success: it means 0Hz backgrounds can be separated by distance.",
        "",
        "## Domain-Level Differences",
        "",
    ]
    for _, row in worst_domains.iterrows():
        lines.append(f"- `{row['feature_domain']}`: inconsistent={row['n_inconsistent']}, low={row['n_low_consistency']}, medium={row['n_medium_consistency']}, high={row['n_high_consistency']}")
    lines += [
        "",
        "## Channel9 / Channel5 Effect",
        "",
        f"- Features whose 0Hz mismatch was reduced by global channel9 masking: {improved_ch9}",
        f"- Features whose mismatch was further reduced by channel5 masking: {improved_ch5}",
        "- If mismatch remains after both masks, it is treated as experiment-condition or batch/background risk rather than channel-quality-only risk.",
        "",
        "## High-Risk Features For Distance Interpretation",
        "",
        ", ".join(high_risk["feature_name"].tolist()) if not high_risk.empty else "No high-risk features under current rules.",
        "",
        "## Impact On Previous Candidate Features",
        "",
        f"- Recommended action counts: {impact_counts}",
        "- Same-distance active-vs-background interpretation remains safer than direct cross-distance comparison when 0Hz backgrounds differ.",
        "- Distance classification can learn zero-state background differences if these risks are not controlled.",
        "",
        "## ML Implications",
        "",
        "- If 0Hz backgrounds are separable by distance, distance classifiers may learn background/batch structure rather than active response.",
        "- Future datasets should record richer metadata and support cross-batch/cross-variable validation.",
        "- Features with high zero-state background risk should be restricted to same-distance background subtraction or downgraded for distance tasks.",
        "",
        "## Scope Guard",
        "",
        "- No machine learning was run.",
        "- No new features were extracted.",
        "- No TDMS/FFT/background contrast pipeline was rerun.",
        "- No existing formulas were modified.",
        "- Existing conclusions are not directly overturned; this report marks zero-state background consistency risk.",
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def consistency_level(auc, max_effect, mean_overlap):
    if pd.isna(auc):
        return "inconsistent"
    if auc <= 0.60 and max_effect <= 1.0 and mean_overlap >= 0.50:
        return "high"
    if auc <= 0.70 and max_effect <= 1.5 and mean_overlap >= 0.35:
        return "medium"
    if auc <= 0.85 and max_effect <= 2.5:
        return "low"
    return "inconsistent"


def consistency_note(level, auc):
    if level == "high":
        return "0Hz groups are broadly overlapping for this feature"
    if level == "medium":
        return "moderate 0Hz background difference; use caution for cross-distance interpretation"
    if level == "low":
        return "visible 0Hz background mismatch"
    return f"strong 0Hz background mismatch; high AUC={auc:.3g} means distance-like background separation"


def risk_level(row):
    level = row["consistency_level"]
    auc = row["auc_distance_3class_or_macro_auc"]
    if level == "high":
        return "low_background_risk", "safe_for_background_reference", "0Hz groups overlap well under current metrics"
    if level == "medium":
        return "medium_background_risk", "use_with_same-distance_background_only", "moderate 0Hz mismatch; same-distance background is safer"
    if level == "low":
        return "high_background_risk", "warning_for_distance_task", "0Hz groups show distance-like differences; distance interpretation is confounded"
    return "reject_for_distance_interpretation", "reject_for_distance_task", f"0Hz backgrounds are separable by this feature; macro AUC={auc:.3g}"


def domain_interpretation(domain, counts):
    bad = counts.get("low", 0) + counts.get("inconsistent", 0)
    good = counts.get("high", 0) + counts.get("medium", 0)
    if bad > good:
        return "background mismatch is prominent in this feature family"
    return "this feature family is comparatively more consistent"


def mask_effect_conclusion(red9, red5, auc_all, auc_n95):
    if red9 and red5:
        return "background mismatch is partly reduced by channel9 and channel5 masks"
    if red9:
        return "background mismatch is partly channel9-driven"
    if red5:
        return "background mismatch is partly channel5-driven after channel9 removal"
    if pd.notna(auc_n95) and auc_n95 > 0.75:
        return "mismatch persists after channel masks; likely not channel-quality-only"
    return "no strong mask-driven change detected"


def impact_action(risk):
    return {
        "low_background_risk": "keep",
        "medium_background_risk": "keep_with_same_distance_background_only",
        "high_background_risk": "downgrade_for_distance_task",
        "reject_for_distance_interpretation": "reject_for_distance_task",
    }.get(risk, "manual_review")


def distance_impact(risk):
    if risk in {"high_background_risk", "reject_for_distance_interpretation"}:
        return "distance task may be confounded by zero-state background differences"
    if risk == "medium_background_risk":
        return "distance task requires caution and same-distance controls"
    return "low zero-state background confounding risk by current rules"


def active_impact(risk):
    if risk in {"high_background_risk", "reject_for_distance_interpretation"}:
        return "same-distance active-vs-background remains usable, but cross-distance comparisons need caution"
    return "same-distance active-vs-background interpretation is not strongly challenged by this check"


def feature_domain(feature):
    if feature.startswith("freq__"):
        return "frequency"
    if feature.startswith("time__"):
        return "time"
    if feature.startswith("acf__"):
        return "acf"
    if feature.startswith("tf__"):
        return "tf"
    if feature.startswith("channel_structure__"):
        return "channel_structure"
    return "unknown"


def feature_type(feature):
    if feature.startswith("freq__"):
        return "frequency_candidate"
    if feature.startswith("time__"):
        return "time_statistic"
    if feature.startswith("acf__"):
        return "acf"
    if feature.startswith("tf__"):
        return "time_frequency_stability"
    if feature.startswith("channel_structure__"):
        return "channel_structure"
    return "unknown"


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
    both = np.concatenate([a, b])
    span = max(np.nanpercentile(both, 75) - np.nanpercentile(both, 25), EPS)
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


def kruskal_effect(groups):
    try:
        stat, _ = kruskal(*groups)
        n = sum(len(g) for g in groups)
        return float(stat / max(n - 1, 1))
    except Exception:
        return np.nan


def val(row, col):
    if row is None:
        return np.nan
    value = row[col]
    return float(value) if pd.notna(value) else np.nan


def read_json(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
