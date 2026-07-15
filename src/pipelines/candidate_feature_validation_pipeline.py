import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import colormaps
import numpy as np
import pandas as pd


CANDIDATE_PEAKS = [
    {"candidate_peak_id": "peak_54k", "center_freq_hz": 54_000.0, "low_hz": 53_500.0, "high_hz": 55_000.0},
    {"candidate_peak_id": "peak_138k", "center_freq_hz": 138_000.0, "low_hz": 137_000.0, "high_hz": 139_500.0},
    {"candidate_peak_id": "peak_178k", "center_freq_hz": 178_000.0, "low_hz": 177_000.0, "high_hz": 179_000.0},
]
SUBBANDS = [
    ("50_60k", 50_000.0, 60_000.0),
    ("60_70k", 60_000.0, 70_000.0),
    ("70_80k", 70_000.0, 80_000.0),
    ("80_90k", 80_000.0, 90_000.0),
    ("90_100k", 90_000.0, 100_000.0),
    ("100_120k", 100_000.0, 120_000.0),
    ("120_140k", 120_000.0, 140_000.0),
    ("140_160k", 140_000.0, 160_000.0),
    ("160_180k", 160_000.0, 180_000.0),
    ("180_200k", 180_000.0, 200_000.0),
]
FEATURE_WINDOWS = [
    ("band_50_100k", 50_000.0, 100_000.0),
    ("band_100_200k", 100_000.0, 200_000.0),
    ("peak_54k", 53_500.0, 55_000.0),
    ("peak_138k", 137_000.0, 139_500.0),
    ("peak_178k", 177_000.0, 179_000.0),
]
CHANNEL_AGGREGATION_METHOD = "median across channels unless channel-level rows are requested"
FILE_AGGREGATION_METHOD = "existing group/channel median PSD curves from background_psd_diff_curves.csv; no file-level PSD curves available"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Candidate Feature Validation v1 from existing background contrast and PSD zoom outputs.")
    parser.add_argument("--background-output", required=True)
    parser.add_argument("--psd-zoom-output", required=True)
    parser.add_argument("--output", default="analysis_out/candidate_feature_validation_v1")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    background_output = Path(args.background_output)
    psd_zoom_output = Path(args.psd_zoom_output)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    psd_zoom = pd.read_csv(psd_zoom_output / "psd_zoom_summary.csv")
    psd_diff = pd.read_csv(background_output / "background_psd_diff_curves.csv")
    cross = pd.read_excel(background_output / "cross_channel_background_contrast.xlsx")
    bandpower = pd.read_excel(background_output / "background_bandpower_contrast.xlsx")
    pumpnet = pd.read_excel(background_output / "pumpfreq_net_contrast.xlsx")
    zoom_audit = read_json(psd_zoom_output / "psd_zoom_input_audit.json")

    consistency = build_input_consistency(background_output, psd_zoom_output, zoom_audit)
    write_json(output_dir / "input_consistency_summary.json", consistency)
    write_input_consistency_md(output_dir / "input_consistency_summary.md", consistency)

    peak_stability = build_peak_stability(psd_zoom)
    peak_stability.to_csv(output_dir / "peak_stability_summary.csv", index=False, encoding="utf-8-sig")

    subband = build_subband_summary(psd_zoom)
    subband.to_csv(output_dir / "subband_gain_summary.csv", index=False, encoding="utf-8-sig")
    plot_subband_heatmap(subband, output_dir / "subband_gain_heatmap.png")

    channel_summary = build_channel_summary(psd_diff)
    channel_summary.to_csv(output_dir / "channel_candidate_feature_summary.csv", index=False, encoding="utf-8-sig")
    plot_channel_heatmap(channel_summary, output_dir / "channel_candidate_feature_heatmap.png")

    leave_one = build_leave_one_channel_out(channel_summary)
    leave_one.to_csv(output_dir / "leave_one_channel_out_summary.csv", index=False, encoding="utf-8-sig")

    file_level, file_stability = build_file_level_skipped()
    file_level.to_csv(output_dir / "file_level_candidate_features.csv", index=False, encoding="utf-8-sig")
    file_stability.to_csv(output_dir / "feature_stability_summary.csv", index=False, encoding="utf-8-sig")
    plot_file_level_placeholder(output_dir / "candidate_feature_boxplot_by_group.png")

    gate = build_gate_summary(peak_stability, subband, channel_summary, leave_one, cross, bandpower, pumpnet, consistency)
    gate.to_csv(output_dir / "candidate_feature_gate_summary.csv", index=False, encoding="utf-8-sig")

    write_report(output_dir, background_output, psd_zoom_output, consistency, peak_stability, subband, channel_summary, leave_one, gate)
    print(f"Candidate Feature Validation v1 output: {output_dir}")
    return output_dir


def read_json(path):
    if not Path(path).exists():
        return {"status": "NOT_FOUND"}
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


def build_input_consistency(background_output, psd_zoom_output, zoom_audit):
    used_files = [
        str(background_output / "background_psd_diff_curves.csv"),
        str(background_output / "background_bandpower_contrast.xlsx"),
        str(background_output / "cross_channel_background_contrast.xlsx"),
        str(background_output / "pumpfreq_net_contrast.xlsx"),
        str(psd_zoom_output / "psd_zoom_summary.csv"),
        str(psd_zoom_output / "psd_zoom_feature_summary.csv"),
        str(psd_zoom_output / "psd_zoom_input_audit.json"),
    ]
    fft = zoom_audit.get("fft_group_input_audit", {})
    warning_files = fft.get("warning_files", [])
    return {
        "analysis_mode": "all-data mode with risk reporting only",
        "strict_mode": False,
        "reason": "Existing outputs do not preserve safe file-level exclusion hooks for already aggregated PSD zoom curves.",
        "used_files": used_files,
        "fft_frequency_axis_warning_count": len(warning_files),
        "fft_frequency_axis_warning_files": warning_files,
        "risk_impact": {
            "psd_zoom": "Affected because PSD zoom reuses already aggregated PSD curves derived from the full input set.",
            "peak_stability": "Affected because peak windows are evaluated on the same aggregated PSD curves.",
            "subband_scan": "Affected because subband summaries reuse PSD zoom curve values.",
            "file_level_stability": "Cannot be safely evaluated from current aggregated outputs.",
        },
    }


def write_input_consistency_md(path, consistency):
    lines = [
        "# Input Consistency Summary",
        "",
        f"Analysis mode: `{consistency['analysis_mode']}`",
        f"Strict mode: `{consistency['strict_mode']}`",
        "",
        "## Used files",
        "",
    ]
    lines.extend(f"- `{p}`" for p in consistency["used_files"])
    lines.extend(["", "## Frequency-axis risk", ""])
    lines.append(f"- Warning file count: {consistency['fft_frequency_axis_warning_count']}")
    lines.extend(f"- `{p}`" for p in consistency["fft_frequency_axis_warning_files"])
    lines.extend(["", "## Impact", ""])
    lines.extend(f"- {k}: {v}" for k, v in consistency["risk_impact"].items())
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_peak_stability(psd_zoom):
    rows = []
    compare_map = {"raw_overlay": "raw", "gain_30_vs_0": "gain_30_vs_0", "gain_50_vs_0": "gain_50_vs_0", "pump_net_50_minus_30": "pump_net_50_minus_30"}
    for peak in CANDIDATE_PEAKS:
        candidate_rows = []
        for distance, dist_df in psd_zoom.groupby("distance"):
            for raw_comp, out_comp in compare_map.items():
                current = dist_df[
                    (dist_df["comparison_type"] == raw_comp)
                    & (dist_df["frequency_hz"] >= peak["low_hz"])
                    & (dist_df["frequency_hz"] <= peak["high_hz"])
                ]
                if current.empty:
                    continue
                if raw_comp == "raw_overlay":
                    current = current[current["source_group"].astype(str).str.contains("30hz|50hz", case=False, na=False)]
                values = current["value"].astype(float)
                max_value = float(values.max())
                median = float(values.median())
                mean = float(values.mean())
                prominence = max_value - median
                ratio = abs(max_value) / max(abs(median), 1e-9)
                broad = float((values > 0).mean())
                present = raw_comp != "raw_overlay" and max_value >= 1.0 and prominence >= 1.0
                notes = []
                if present:
                    notes.append("peak evidence in window")
                if ratio >= 5 and abs(median) < 0.5:
                    notes.append("peak-dominated; low median gain")
                if broad >= 0.8 and median >= 0.5:
                    notes.append("broadband/mixed")
                candidate_rows.append({
                    "candidate_peak_id": peak["candidate_peak_id"],
                    "center_freq_hz": peak["center_freq_hz"],
                    "freq_window_low_hz": peak["low_hz"],
                    "freq_window_high_hz": peak["high_hz"],
                    "distance": distance,
                    "comparison_type": out_comp,
                    "max_value": max_value,
                    "median_value": median,
                    "mean_value": mean,
                    "peak_prominence_like_value": prominence,
                    "peak_to_band_ratio": ratio,
                    "broadband_lift_score": broad,
                    "_present": present,
                    "risk_flag": "frequency_axis_risk",
                    "notes": "; ".join(notes) if notes else "weak/no peak evidence",
                })
        appears_dist = len(set(r["distance"] for r in candidate_rows if r["_present"]))
        appears_comp = len(set(r["comparison_type"] for r in candidate_rows if r["_present"]))
        stable = appears_dist >= 2 and appears_comp >= 2
        for row in candidate_rows:
            row["appears_in_n_distances"] = appears_dist
            row["appears_in_n_comparisons"] = appears_comp
            row["stable_peak_flag"] = bool(stable)
            if not stable and row["_present"]:
                row["notes"] = row["notes"] + "; weak evidence if isolated"
            row.pop("_present", None)
            rows.append(row)
    return pd.DataFrame(rows)


def build_subband_summary(psd_zoom):
    rows = []
    current = psd_zoom[psd_zoom["comparison_type"].isin(["gain_30_vs_0", "gain_50_vs_0"])].copy()
    for subband_id, low, high in SUBBANDS:
        sub = current[(current["frequency_hz"] >= low) & (current["frequency_hz"] <= high)]
        for keys, group in sub.groupby(["distance", "comparison_type", "source_group", "background_group", "active_group"], dropna=False):
            values = group["value"].astype(float)
            freqs = group["frequency_hz"].astype(float)
            rows.append({
                "distance": keys[0],
                "rpm_or_group": keys[2],
                "background_group": keys[3],
                "active_group": keys[4],
                "comparison_type": keys[1],
                "subband_id": subband_id,
                "freq_low_hz": low,
                "freq_high_hz": high,
                "median_gain_dB": float(values.median()),
                "mean_gain_dB": float(values.mean()),
                "max_gain_dB": float(values.max()),
                "integrated_gain": float(np.trapezoid(values, freqs)) if len(values) > 1 else np.nan,
                "file_or_curve_count": int(len(values)),
                "channel_aggregation_method": "reused PSD zoom channel-median curve",
                "file_aggregation_method": FILE_AGGREGATION_METHOD,
            })
    return pd.DataFrame(rows)


def build_channel_summary(psd_diff):
    rows = []
    for feature_name, low, high in FEATURE_WINDOWS:
        sub = psd_diff[(psd_diff["freq_hz"] >= low) & (psd_diff["freq_hz"] <= high)]
        for keys, group in sub.groupby(["distance_m", "active_group", "background_group", "pump_freq_hz", "channel"]):
            values = group["psd_gain_dB"].astype(float)
            rows.append({
                "channel": keys[4],
                "feature_name": feature_name,
                "distance": f"{int(keys[0])}m",
                "comparison_type": f"gain_{int(keys[3])}_vs_0",
                "median_gain": float(values.median()),
                "active_group": keys[1],
                "background_group": keys[2],
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    out = []
    for keys, group in df.groupby(["feature_name", "distance", "comparison_type"]):
        denom = float(group["median_gain"].abs().sum()) or 1e-9
        med = group["median_gain"].median()
        mad = (group["median_gain"] - med).abs().median() or 1e-9
        ranked = group.copy()
        ranked["rank"] = ranked["median_gain"].rank(ascending=False, method="min").astype(int)
        ranked["contribution_ratio"] = ranked["median_gain"].abs() / denom
        ranked["outlier_flag"] = ((ranked["median_gain"] - med).abs() / (1.4826 * mad)) > 3.0
        ranked["sensitive_channel_candidate_flag"] = (ranked["contribution_ratio"] >= 0.25) | ranked["channel"].eq("channel9")
        out.append(ranked)
    return pd.concat(out, ignore_index=True)


def build_leave_one_channel_out(channel_summary):
    rows = []
    for keys, group in channel_summary.groupby(["feature_name", "distance", "comparison_type"]):
        original = float(group["median_gain"].median())
        for _, row in group.iterrows():
            remaining = group[group["channel"] != row["channel"]]
            after = float(remaining["median_gain"].median()) if not remaining.empty else np.nan
            rel = float((after - original) / (abs(original) + 1e-9)) if np.isfinite(after) else np.nan
            rows.append({
                "removed_channel": row["channel"],
                "feature_name": keys[0],
                "distance": keys[1],
                "comparison_type": keys[2],
                "original_value": original,
                "value_after_removal": after,
                "relative_change": rel,
                "conclusion_flipped_flag": bool(np.sign(original) != np.sign(after) or (abs(original) >= 0.5) != (abs(after) >= 0.5)),
            })
    return pd.DataFrame(rows)


def build_file_level_skipped():
    cols = ["group", "distance", "rpm", "file_id", "channel", "feature_name", "feature_value", "qc_flag", "skipped_reason"]
    stability_cols = ["feature_name", "group", "median", "mean", "std", "iqr", "cv", "p10", "p90", "stable_file_ratio", "outlier_file_count", "notes"]
    reason = "SKIPPED: current background_psd_diff_curves.csv stores group/channel median PSD curves and file_count=1 group_median rows, not per-file PSD curves."
    return pd.DataFrame([{col: "" for col in cols} | {"skipped_reason": reason}]), pd.DataFrame([{col: np.nan for col in stability_cols} | {"notes": reason}])


def build_gate_summary(peak_stability, subband, channel_summary, leave_one, cross, bandpower, pumpnet, consistency):
    rows = []
    freq_risk = consistency["fft_frequency_axis_warning_count"] > 0
    feature_names = ["band_50_100k", "band_100_200k", "peak_54k", "peak_138k", "peak_178k"]
    for feature in feature_names:
        ch = channel_summary[channel_summary["feature_name"] == feature]
        support = support_count_for_feature(feature, cross, bandpower)
        channel_risk = channel_dominance_risk(feature, ch)
        loo = leave_one[leave_one["feature_name"] == feature]
        flipped = bool(loo["conclusion_flipped_flag"].any()) if not loo.empty else False
        med_by_dist = ch.groupby("distance")["median_gain"].median().to_dict() if not ch.empty else {}
        mono = med_by_dist.get("2m", -np.inf) >= med_by_dist.get("3m", -np.inf) >= med_by_dist.get("5m", -np.inf)
        peak_rows = peak_stability[peak_stability["candidate_peak_id"] == feature] if feature.startswith("peak_") else pd.DataFrame()
        peak_dom = bool((peak_rows["peak_to_band_ratio"] >= 5).any()) if not peak_rows.empty else False
        broad = bool((peak_rows["broadband_lift_score"] >= 0.8).any()) if not peak_rows.empty else feature.startswith("band_")
        stable_peak = bool(peak_rows["stable_peak_flag"].any()) if not peak_rows.empty else True
        ml_ready = bool(support >= 8 and not channel_risk and not freq_risk and stable_peak)
        priority = "high" if ml_ready else "medium" if support >= 8 and stable_peak else "low" if support >= 4 else "reject"
        if freq_risk and priority == "high":
            priority = "medium"
        reason = []
        reason.append(f"support_channel_count={support}")
        if freq_risk:
            reason.append("frequency_axis_risk")
        if channel_risk or flipped:
            reason.append("channel dominance sensitivity")
        if peak_dom:
            reason.append("peak-dominated")
        if mono:
            reason.append("distance-relevant candidate")
        rows.append({
            "feature_name": feature,
            "feature_type": "peak" if feature.startswith("peak_") else "bandpower",
            "distance_trend_flag": "2m>=3m>=5m" if mono else "not_monotonic_or_mixed",
            "monotonic_flag": bool(mono),
            "support_channel_count": int(support),
            "stable_file_ratio": np.nan,
            "peak_dominated_flag": peak_dom,
            "broadband_lift_flag": broad,
            "channel_dominance_risk": bool(channel_risk or flipped),
            "frequency_axis_risk": bool(freq_risk),
            "ml_ready_flag": ml_ready,
            "priority": priority,
            "reason": "; ".join(reason),
        })
    return pd.DataFrame(rows)


def support_count_for_feature(feature, cross, bandpower):
    mapping = {"band_50_100k": "50khz_100khz", "band_100_200k": "100khz_200khz"}
    if feature in mapping:
        current = cross[(cross["feature_type"] == "bandpower") & (cross["feature_name"] == mapping[feature])]
        return int(current["support_channel_count"].median()) if not current.empty else 0
    return 0


def channel_dominance_risk(feature, ch):
    if ch.empty:
        return False
    current = ch[ch["channel"].eq("channel9")]
    max_contrib = ch["contribution_ratio"].max()
    return bool(max_contrib >= 0.35 or (not current.empty and current["contribution_ratio"].max() >= 0.25))


def plot_subband_heatmap(subband, path):
    if subband.empty:
        return
    data = subband.copy()
    data["label"] = data["distance"] + " " + data["comparison_type"]
    pivot = data.pivot_table(index="subband_id", columns="label", values="median_gain_dB", aggfunc="median")
    plot_heatmap(pivot, path, "Subband Median PSD Gain dB")


def plot_channel_heatmap(channel_summary, path):
    if channel_summary.empty:
        return
    data = channel_summary.copy()
    data["label"] = data["feature_name"] + " " + data["distance"] + " " + data["comparison_type"]
    pivot = data.pivot_table(index="channel", columns="label", values="median_gain", aggfunc="median")
    pivot = pivot.reindex(sorted(pivot.index, key=channel_sort_key))
    plot_heatmap(pivot, path, "Channel Candidate Feature Median Gain")


def plot_heatmap(pivot, path, title):
    plt.figure(figsize=(13, 7))
    cmap = colormaps.get_cmap("coolwarm").copy()
    cmap.set_bad(color="#d9d9d9")
    plt.imshow(np.ma.masked_invalid(pivot.to_numpy(dtype=float)), aspect="auto", cmap=cmap)
    plt.xticks(range(len(pivot.columns)), pivot.columns, rotation=60, ha="right", fontsize=7)
    plt.yticks(range(len(pivot.index)), pivot.index)
    plt.colorbar(label="dB")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def plot_file_level_placeholder(path):
    plt.figure(figsize=(8, 4))
    plt.text(0.5, 0.5, "File-level PSD curves unavailable in current aggregated outputs", ha="center", va="center")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def write_report(output_dir, background_output, psd_zoom_output, consistency, peak, subband, channel, leave_one, gate):
    docs = Path("docs")
    docs.mkdir(parents=True, exist_ok=True)
    report = docs / "CANDIDATE_FEATURE_VALIDATION_V1.md"
    top = gate.sort_values(["priority", "support_channel_count"], ascending=[True, False])
    channel9 = channel[channel["channel"] == "channel9"] if not channel.empty else pd.DataFrame()
    if not channel9.empty:
        channel9_note = (
            "channel9 is present in sensitivity checks; contribution_ratio range="
            f"{channel9['contribution_ratio'].min():.3g}-{channel9['contribution_ratio'].max():.3g}. "
            "High channel9 contribution is treated as needs-check, not a bad-channel decision."
        )
    else:
        channel9_note = "channel9 not found in channel summary."
    ml_ready = bool(gate["ml_ready_flag"].any())
    top_subbands = (
        subband.sort_values("median_gain_dB", ascending=False)
        .head(8)[["distance", "comparison_type", "subband_id", "median_gain_dB", "max_gain_dB"]]
        if not subband.empty else pd.DataFrame()
    )
    lines = [
        "# Candidate Feature Validation v1",
        "",
        "## Stage",
        "",
        "This moves from broad high-frequency candidate bands into local peak and subband candidate validation.",
        "",
        "## Inputs",
        "",
        f"- Background contrast output: `{background_output}`",
        f"- PSD zoom output: `{psd_zoom_output}`",
        f"- Output directory: `{output_dir}`",
        "",
        "## Scope guard",
        "",
        "- Did not rerun full background contrast.",
        "- Did not change the background contrast formula.",
        "- Did not run machine learning or build a final feature dataset.",
        "- Did not perform time-domain synchronous subtraction.",
        "",
        "## Input risk",
        "",
        f"- Analysis mode: `{consistency['analysis_mode']}`",
        f"- FFT frequency-axis warning files: {consistency['fft_frequency_axis_warning_count']}",
    ]
    lines.extend(f"  - `{name}`" for name in consistency["fft_frequency_axis_warning_files"])
    lines.extend([
        "",
        "## Rules",
        "",
        "- `stable_peak_flag=True` requires peak evidence in at least 2 distances and at least 2 non-raw comparison types.",
        "- Peak evidence requires `max_value >= 1 dB` and `peak_prominence_like_value >= 1 dB` inside the candidate window.",
        "- `peak-dominated` is marked when `peak_to_band_ratio >= 5` while median gain is low.",
        "- Gate keeps broad bands as medium candidates when support is high but frequency-axis/file-level/channel risks remain.",
        "- `ml_ready_flag=True` requires support_channel_count >= 8, no frequency-axis risk, no channel dominance risk, and peak stability where applicable.",
        "",
        "## Gate summary",
        "",
    ])
    for row in top.itertuples():
        lines.append(f"- `{row.feature_name}`: priority={row.priority}, ml_ready={row.ml_ready_flag}, reason={row.reason}")
    lines.extend([
        "",
        "## Candidate peaks",
        "",
    ])
    for peak_id, group in peak.groupby("candidate_peak_id"):
        stable = bool(group["stable_peak_flag"].any())
        best = group.sort_values("max_value", ascending=False).head(1).iloc[0]
        lines.append(f"- `{peak_id}`: stable_peak_flag={stable}; best max={best['max_value']:.3g} at {best['distance']} {best['comparison_type']}; notes={best['notes']}")
    lines.extend([
        "",
        "## Broad bands",
        "",
        "- `50-100k` and `100-200k` should remain as broad candidate containers, but current PSD zoom and subband summaries indicate local peak/mixed spectral structure rather than uniform broadband lift.",
        "",
        "Strongest subband rows by median gain:",
    ])
    if top_subbands.empty:
        lines.append("- No subband rows available.")
    else:
        for row in top_subbands.itertuples():
            lines.append(f"- `{row.distance} {row.comparison_type} {row.subband_id}`: median={row.median_gain_dB:.3g}, max={row.max_gain_dB:.3g}")
    lines.extend([
        "",
        "The broad bands are retained as medium-risk containers, while subband/peak-level candidates should carry risk flags until file-level stability and frequency-axis consistency are resolved.",
        "",
        "## Channel robustness",
        "",
        f"- {channel9_note}",
        "- No channel was automatically removed.",
        "- If all channels move together, this may indicate common-mode/system effect; if a local channel dominates, it is marked as spatial-pattern risk only.",
        "",
        "## File-level stability",
        "",
        "- File-level candidate features were not computed because current outputs store aggregated group/channel median PSD curves, not per-file PSD curves.",
        "- Needed next input: per-file PSD curves or an intermediate table before `compute_psd_gain_curves` collapses file-level rows.",
        "",
        "## Can this enter ML feature table construction?",
        "",
        f"- Current answer: {'YES for medium-risk exploratory candidates only' if ml_ready else 'NOT YET as high-confidence features'}.",
        "- Frequency-axis risk and missing file-level stability prevent high-confidence ML-ready promotion in this validation pass.",
        "",
        "## Next step",
        "",
        "- If accepting medium-risk exploratory features: build a provisional `feature_dataset.csv` with risk flags.",
        "- If requiring stricter validation: first resolve frequency-axis inconsistencies and regenerate per-file PSD feature inputs.",
    ])
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def channel_sort_key(channel):
    text = str(channel)
    if text.startswith("channel"):
        try:
            return int(text.replace("channel", ""))
        except ValueError:
            return 10**9
    return 10**9


if __name__ == "__main__":
    main()
