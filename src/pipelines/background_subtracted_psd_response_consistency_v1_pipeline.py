import argparse
import json
from itertools import combinations
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


MASKS = ["mask_all", "mask_no_ch9_global", "mask_no_ch9_ch5_global"]
DISTANCES = ["2m", "3m", "5m"]
ACTIVE = {
    "30Hz_minus_0Hz": "30Hz",
    "50Hz_minus_0Hz": "50Hz",
}
WINDOWS = [(float(start), float(start + 20_000)) for start in range(0, 200_000, 20_000)]
EPS = 1e-30


def main(argv=None):
    parser = argparse.ArgumentParser(description="Background-Subtracted PSD Response Consistency v1.")
    parser.add_argument("--mask-matrix", default="analysis_out/channel_mask_sensitivity_v1/masked_feature_matrix_file_agg_v1.csv")
    parser.add_argument("--background-psd-curves", default="D:/Lab/results/26.5.12/background_contrast_v1/background_psd_diff_curves.csv")
    parser.add_argument("--output", default="analysis_out/background_subtracted_psd_response_consistency_v1")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    matrix = build_response_matrix(Path(args.mask_matrix))
    matrix.to_csv(out / "psd_response_feature_matrix_v1.csv", index=False, encoding="utf-8-sig")
    consistency = build_consistency(matrix)
    consistency.to_csv(out / "psd_response_consistency_summary_v1.csv", index=False, encoding="utf-8-sig")
    candidates = build_candidates(consistency)
    candidates.to_csv(out / "psd_response_candidate_features_v1.csv", index=False, encoding="utf-8-sig")
    mask_effect = build_mask_effect(consistency)
    mask_effect.to_csv(out / "psd_response_mask_effect_summary_v1.csv", index=False, encoding="utf-8-sig")
    plot_index = write_response_review_figures(Path(args.background_psd_curves), out / "review_figures")
    plot_index.to_csv(out / "psd_response_review_figure_index_v1.csv", index=False, encoding="utf-8-sig")
    write_json(out / "psd_response_run_config_v1.json", {
        "mask_matrix": args.mask_matrix,
        "background_psd_curves": args.background_psd_curves,
        "output": args.output,
        "masks": MASKS,
        "active_conditions": list(ACTIVE.keys()),
        "distance_sets": ["2m3m", "2m3m5m"],
        "response_unit": "dB difference for feature matrix; psd_gain_dB for review curves",
        "scope_guard": "No ML, no 50Hz-30Hz, no TDMS/FFT rerun, no background formula change.",
    })
    write_report(out, matrix, consistency, candidates, mask_effect, plot_index)
    print(f"Background-Subtracted PSD Response Consistency v1 output: {out}")


def build_response_matrix(mask_matrix_path):
    if not mask_matrix_path.exists():
        raise FileNotFoundError(f"Missing mask matrix: {mask_matrix_path}")
    df = pd.read_csv(mask_matrix_path)
    df = df[df["mask_name"].isin(MASKS)].copy()
    freq_features = [c for c in df.columns if c.startswith("freq__")]
    rows = []
    for mask in MASKS:
        mdf = df[df["mask_name"] == mask].copy()
        for active_condition, rpm in ACTIVE.items():
            for distance in DISTANCES:
                bg = mdf[(mdf["distance"] == distance) & (mdf["rpm"] == "0Hz")]
                ac = mdf[(mdf["distance"] == distance) & (mdf["rpm"] == rpm)]
                if bg.empty or ac.empty:
                    continue
                for feature in freq_features:
                    bg_vals = pd.to_numeric(bg[feature], errors="coerce").dropna()
                    ac_vals = pd.to_numeric(ac[feature], errors="coerce").dropna()
                    if bg_vals.empty or ac_vals.empty:
                        continue
                    rows.append({
                        "mask_name": mask,
                        "active_condition": active_condition,
                        "distance": distance,
                        "feature_name": feature,
                        "feature_domain": "frequency",
                        "response_value": float(ac_vals.median() - bg_vals.median()),
                        "response_unit": "dB_feature_difference",
                        "n_files_active": int(ac_vals.size),
                        "n_files_background": int(bg_vals.size),
                        "n_channels_used": float(ac["n_channels_used"].median()) if "n_channels_used" in ac else np.nan,
                        "excluded_channels": first_nonempty(ac.get("excluded_channels", pd.Series(dtype=str))),
                        "qc_flag": join_qc(ac.get("qc_flag", pd.Series(dtype=str)).tolist() + bg.get("qc_flag", pd.Series(dtype=str)).tolist()),
                    })
    return pd.DataFrame(rows)


def build_consistency(matrix):
    rows = []
    for (mask, active, feature), group in matrix.groupby(["mask_name", "active_condition", "feature_name"]):
        values = {row["distance"]: float(row["response_value"]) for _, row in group.iterrows()}
        for distance_set, dists in [("2m3m", ["2m", "3m"]), ("2m3m5m", ["2m", "3m", "5m"])]:
            if not all(d in values for d in dists):
                continue
            vals = [values[d] for d in dists]
            level, notes = consistency_level(vals, distance_set)
            rows.append({
                "mask_name": mask,
                "active_condition": active,
                "distance_set": distance_set,
                "feature_name": feature,
                "response_2m": values.get("2m", np.nan),
                "response_3m": values.get("3m", np.nan),
                "response_5m": values.get("5m", np.nan) if distance_set == "2m3m5m" else np.nan,
                "sign_consistency": sign_consistency(vals),
                "response_range": float(np.nanmax(vals) - np.nanmin(vals)),
                "response_cv": response_cv(vals),
                "max_pairwise_delta": max_pairwise_delta(vals),
                "min_abs_response": float(np.nanmin(np.abs(vals))),
                "consistency_level": level,
                "weak_5m_warning": bool(distance_set == "2m3m5m" and abs(values.get("5m", 0.0)) < 0.25),
                "channel_mask_warning": "",
                "notes": notes,
            })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out = add_channel_mask_warnings(out)
    return out


def consistency_level(vals, distance_set):
    vals = np.asarray(vals, dtype=float)
    signs = sign_consistency(vals)
    max_abs = float(np.nanmax(np.abs(vals)))
    min_abs = float(np.nanmin(np.abs(vals)))
    rng = float(np.nanmax(vals) - np.nanmin(vals))
    cv = response_cv(vals)
    if signs == "near_zero":
        return "weak", "responses are near zero"
    if signs == "mixed_sign":
        return "inconsistent", "response direction changes across distances"
    if max_abs < 0.25:
        return "weak", "response magnitude is very small"
    if rng <= 0.5 or (cv <= 0.35 and min_abs >= 0.5):
        return "strong", f"{distance_set} responses have same direction and similar magnitude"
    if rng <= 1.5 or cv <= 0.75:
        return "moderate", f"{distance_set} responses have same direction but amplitude varies"
    return "weak", f"{distance_set} responses have same direction but large amplitude spread"


def add_channel_mask_warnings(summary):
    keys = ["active_condition", "distance_set", "feature_name"]
    base = summary[summary["mask_name"] == "mask_all"][keys + ["consistency_level", "response_2m", "response_3m", "response_5m"]]
    out = summary.copy()
    warnings = []
    for _, row in out.iterrows():
        if row["mask_name"] == "mask_all":
            warnings.append("")
            continue
        b = base[(base["active_condition"] == row["active_condition"]) & (base["distance_set"] == row["distance_set"]) & (base["feature_name"] == row["feature_name"])]
        if b.empty:
            warnings.append("")
            continue
        b = b.iloc[0]
        delta = max(abs(row.get(c, np.nan) - b.get(c, np.nan)) for c in ["response_2m", "response_3m", "response_5m"] if pd.notna(row.get(c, np.nan)) and pd.notna(b.get(c, np.nan)))
        warnings.append("channel_mask_sensitive" if delta > 0.5 or row["consistency_level"] != b["consistency_level"] else "")
    out["channel_mask_warning"] = warnings
    return out


def build_candidates(consistency):
    rows = []
    for (mask, active, feature), group in consistency.groupby(["mask_name", "active_condition", "feature_name"]):
        g23 = first_row(group[group["distance_set"] == "2m3m"])
        gfull = first_row(group[group["distance_set"] == "2m3m5m"])
        if g23 is None:
            continue
        full_level = gfull["consistency_level"] if gfull is not None else "not_available"
        if g23["consistency_level"] in {"strong", "moderate"} and full_level in {"strong", "moderate"}:
            category = "robust_2m3m5m_candidate"
        elif g23["consistency_level"] in {"strong", "moderate"} and gfull is not None and bool(gfull["weak_5m_warning"]):
            category = "2m3m_only_candidate_due_to_weak_5m"
        elif g23["consistency_level"] in {"strong", "moderate"}:
            category = "robust_2m3m_candidate"
        elif g23["sign_consistency"] == "mixed_sign" or (gfull is not None and gfull["sign_consistency"] == "mixed_sign"):
            category = "distance_dependent_response"
        elif (g23.get("channel_mask_warning", "") or (gfull is not None and gfull.get("channel_mask_warning", ""))):
            category = "channel_risk_response"
        else:
            category = "reject_or_unclear"
        rows.append({
            "mask_name": mask,
            "active_condition": active,
            "feature_name": feature,
            "candidate_category": category,
            "consistency_2m3m": g23["consistency_level"],
            "consistency_2m3m5m": full_level,
            "weak_5m_warning": bool(gfull["weak_5m_warning"]) if gfull is not None else False,
            "channel_mask_warning": g23.get("channel_mask_warning", "") or (gfull.get("channel_mask_warning", "") if gfull is not None else ""),
            "notes": "candidate category is a response-consistency screen, not final science conclusion",
        })
    return pd.DataFrame(rows)


def build_mask_effect(consistency):
    rows = []
    base = consistency[consistency["mask_name"] == "mask_all"]
    for _, row in consistency[consistency["mask_name"] != "mask_all"].iterrows():
        b = base[(base["active_condition"] == row["active_condition"]) & (base["distance_set"] == row["distance_set"]) & (base["feature_name"] == row["feature_name"])]
        if b.empty:
            continue
        b = b.iloc[0]
        deltas = {}
        for col in ["response_2m", "response_3m", "response_5m"]:
            if pd.notna(row[col]) and pd.notna(b[col]):
                deltas[col + "_delta"] = float(row[col] - b[col])
        max_change = max([abs(v) for v in deltas.values()] or [0.0])
        rows.append({
            "active_condition": row["active_condition"],
            "distance_set": row["distance_set"],
            "feature_name": row["feature_name"],
            "baseline_mask": "mask_all",
            "compared_mask": row["mask_name"],
            "consistency_baseline": b["consistency_level"],
            "consistency_compared": row["consistency_level"],
            "max_abs_response_change": max_change,
            "response_change_no_ch9": max_change if row["mask_name"] == "mask_no_ch9_global" else np.nan,
            "response_change_no_ch9_ch5": max_change if row["mask_name"] == "mask_no_ch9_ch5_global" else np.nan,
            "channel_dependency_warning": bool(max_change > 0.5 or b["consistency_level"] != row["consistency_level"]),
            **deltas,
        })
    return pd.DataFrame(rows)


def write_response_review_figures(curves_path, figure_dir):
    if not curves_path.exists():
        return pd.DataFrame([{"skipped_reason": f"missing curves file: {curves_path}"}])
    figure_dir.mkdir(parents=True, exist_ok=True)
    usecols = ["active_group", "background_group", "pump_freq_hz", "channel", "freq_hz", "psd_gain_dB"]
    frames = []
    for chunk in pd.read_csv(curves_path, usecols=usecols, chunksize=500_000):
        chunk = chunk[chunk["background_group"].astype(str).str.lower().isin(["2m0hz", "3m0hz", "5m0hz"])]
        chunk = chunk[chunk["active_group"].astype(str).str.lower().isin(["2m30hz", "3m30hz", "5m30hz", "2m50hz", "3m50hz", "5m50hz"])]
        chunk = chunk[(chunk["freq_hz"] >= 0.0) & (chunk["freq_hz"] <= 200_000.0)]
        frames.append(chunk)
    df = pd.concat(frames, ignore_index=True)
    rows = []
    for mask in MASKS:
        channels = retained_channels(mask)
        mdf = df[df["channel"].isin(channels)].copy()
        agg = mdf.groupby(["active_group", "pump_freq_hz", "freq_hz"], as_index=False)["psd_gain_dB"].median()
        for active_condition, rpm_value in [("30Hz_minus_0Hz", 30.0), ("50Hz_minus_0Hz", 50.0)]:
            adf = agg[np.isclose(agg["pump_freq_hz"], rpm_value)].copy()
            for distance_set, dists in [("2m3m", ["2m", "3m"]), ("2m3m5m", ["2m", "3m", "5m"])]:
                for low, high in WINDOWS:
                    seg = adf[(adf["freq_hz"] >= low) & (adf["freq_hz"] <= high)].copy()
                    if seg.empty:
                        continue
                    out_dir = figure_dir / mask / active_condition / distance_set
                    out_dir.mkdir(parents=True, exist_ok=True)
                    path = out_dir / f"{active_condition}_{distance_set}_{int(low/1000):03d}_{int(high/1000):03d}k.png"
                    plot_response_segment(seg, active_condition, mask, distance_set, dists, low, high, path)
                    rows.append({
                        "mask_name": mask,
                        "active_condition": active_condition,
                        "distance_set": distance_set,
                        "freq_window_low_hz": low,
                        "freq_window_high_hz": high,
                        "plot_path": str(path),
                        "aggregation": "median psd_gain_dB across retained channels",
                        "retained_channels": ",".join(channels),
                    })
    return pd.DataFrame(rows)


def plot_response_segment(seg, active_condition, mask, distance_set, dists, low, high, path):
    plt.figure(figsize=(10, 4.8))
    colors = {"2m": "#1f77b4", "3m": "#ff7f0e", "5m": "#2ca02c"}
    for distance in dists:
        group = f"{distance}{'30hz' if active_condition.startswith('30') else '50hz'}"
        cur = seg[seg["active_group"].astype(str).str.lower().eq(group)].sort_values("freq_hz")
        if cur.empty:
            continue
        plt.plot(cur["freq_hz"] / 1000.0, cur["psd_gain_dB"], linewidth=1.1, label=distance, color=colors.get(distance))
    plt.axhline(0, color="#555555", linewidth=0.8, linestyle="--")
    plt.xlim(low / 1000.0, high / 1000.0)
    plt.xlabel("frequency (kHz)")
    plt.ylabel("PSD gain vs same-distance 0Hz (dB)")
    plt.title(f"{active_condition} PSD response | {distance_set} | {mask} | {int(low/1000)}-{int(high/1000)} kHz")
    plt.grid(True, alpha=0.25, linewidth=0.5)
    plt.legend(title="distance", fontsize=8)
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def retained_channels(mask):
    channels = [f"channel{i}" for i in range(1, 13)]
    if mask == "mask_no_ch9_global":
        return [c for c in channels if c != "channel9"]
    if mask == "mask_no_ch9_ch5_global":
        return [c for c in channels if c not in {"channel9", "channel5"}]
    return channels


def sign_consistency(vals):
    vals = np.asarray(vals, dtype=float)
    if np.nanmax(np.abs(vals)) < 0.25:
        return "near_zero"
    signs = np.sign(vals[np.abs(vals) >= 0.25])
    if len(signs) == 0:
        return "near_zero"
    if np.all(signs > 0):
        return "all_positive"
    if np.all(signs < 0):
        return "all_negative"
    return "mixed_sign"


def response_cv(vals):
    vals = np.asarray(vals, dtype=float)
    return float(np.nanstd(vals, ddof=1) / (abs(np.nanmean(vals)) + EPS)) if len(vals) > 1 else 0.0


def max_pairwise_delta(vals):
    return float(max(abs(a - b) for a, b in combinations(vals, 2))) if len(vals) > 1 else 0.0


def first_row(df):
    return None if df.empty else df.iloc[0]


def first_nonempty(values):
    for value in values:
        if pd.notna(value) and str(value):
            return str(value)
    return ""


def join_qc(values):
    vals = sorted({str(v) for v in values if str(v) and str(v) not in {"OK", "nan"}})
    return ";".join(vals) if vals else "OK"


def write_report(out, matrix, consistency, candidates, mask_effect, plot_index):
    report = Path("docs/BACKGROUND_SUBTRACTED_PSD_RESPONSE_CONSISTENCY_V1.md")
    report.parent.mkdir(parents=True, exist_ok=True)
    counts = candidates["candidate_category"].value_counts().to_dict() if not candidates.empty else {}
    main = consistency[consistency["mask_name"] == "mask_no_ch9_global"]
    main_counts = main.groupby(["active_condition", "distance_set"])["consistency_level"].value_counts().to_dict() if not main.empty else {}
    channel_warn = int(mask_effect["channel_dependency_warning"].sum()) if not mask_effect.empty else 0
    lines = [
        "# Background-Subtracted PSD Response Consistency v1",
        "",
        "## Purpose",
        "",
        "Zero-state backgrounds may vary across distance. This analysis therefore does not require 2m0Hz, 3m0Hz, and 5m0Hz to be identical. Instead it checks whether active PSD response relative to each same-distance 0Hz background has repeatable structure across distances.",
        "",
        "## Scope",
        "",
        "- PSD/frequency features only.",
        "- Active conditions: 30Hz-0Hz and 50Hz-0Hz.",
        "- Distance sets are reported separately: 2m/3m and 2m/3m/5m.",
        "- Masks compared: mask_all, mask_no_ch9_global, mask_no_ch9_ch5_global.",
        "- No 50Hz-30Hz or pump-net contrast was computed.",
        "- No machine learning, TDMS rerun, FFT rerun, or background-contrast formula change.",
        "",
        "## Response Definition",
        "",
        "For feature-level tables, response is active group median PSD feature minus same-distance 0Hz background median PSD feature. Existing frequency features are in dB-like bandpower units, so response is reported as dB feature difference. Review curves use existing `psd_gain_dB` from background contrast outputs.",
        "",
        "## Outputs",
        "",
        f"- Feature response rows: {len(matrix)}",
        f"- Consistency rows: {len(consistency)}",
        f"- Review plots: {len(plot_index)}",
        f"- Candidate category counts: {counts}",
        "",
        "## Main-Mask Consistency Snapshot",
        "",
        "- `mask_no_ch9_global` consistency counts:",
    ]
    for (active_condition, distance_set, level), count in sorted(main_counts.items()):
        lines.append(f"  - {active_condition} / {distance_set} / {level}: {count}")
    lines += [
        "",
        "## 5m Weak-Signal Note",
        "",
        "2m/3m and 2m/3m/5m are intentionally separated. Features that are consistent in 2m/3m but weaken or become near-zero at 5m are marked separately rather than mixed into the same conclusion.",
        "",
        "## Channel Mask Effect",
        "",
        f"- Mask-sensitive response rows: {channel_warn}",
        "- channel9/channel5 masks are current pilot QC checks, not permanent channel rules.",
        "",
        "## Review Figures",
        "",
        "Segmented response overlays are under `review_figures/`. For each active condition, mask, and distance set, 0-200 kHz is split into 20 kHz windows for manual comparison of response shape and narrow peaks.",
        "",
        "## Interpretation Guard",
        "",
        "Current outputs are PSD response consistency screens. They are not ML results and not final scientific conclusions. Stable response candidates can be used later for focused feature screening or manual peak review.",
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
