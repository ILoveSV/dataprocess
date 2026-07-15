import argparse
import json
from itertools import combinations
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


CHANNELS = [f"channel{i}" for i in range(1, 13)]
DISTANCES = ["2m", "3m", "5m"]
ACTIVE = {
    "30Hz_minus_0Hz": "30Hz",
    "50Hz_minus_0Hz": "50Hz",
}
WINDOWS = [(float(start), float(start + 20_000)) for start in range(0, 200_000, 20_000)]
EPS = 1e-30
PLOT_BIN_HZ = 25.0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Per-channel Background-Subtracted PSD Response Consistency v1.")
    parser.add_argument("--frequency-dataset", default="analysis_out/feature_extraction_v2/candidate_feature_dataset_v2.csv")
    parser.add_argument("--background-psd-curves", default="D:/Lab/results/26.5.12/background_contrast_v1/background_psd_diff_curves.csv")
    parser.add_argument("--fft-root", default="D:/Lab/process/26.5.12/frequency")
    parser.add_argument("--plot-source", choices=["existing_curves", "fft_current"], default="existing_curves")
    parser.add_argument("--output", default="analysis_out/background_subtracted_psd_response_consistency_per_channel_v1")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    response = build_response_matrix(Path(args.frequency_dataset))
    response.to_csv(out / "psd_response_feature_matrix_per_channel_v1.csv", index=False, encoding="utf-8-sig")
    consistency = build_consistency(response)
    consistency.to_csv(out / "psd_response_consistency_summary_per_channel_v1.csv", index=False, encoding="utf-8-sig")
    candidates = build_candidates(consistency)
    candidates.to_csv(out / "psd_response_candidate_features_per_channel_v1.csv", index=False, encoding="utf-8-sig")
    channel_summary = build_channel_summary(consistency)
    channel_summary.to_csv(out / "psd_response_channel_summary_v1.csv", index=False, encoding="utf-8-sig")
    if args.plot_source == "fft_current":
        plot_index = write_review_figures_from_fft(Path(args.fft_root), out / "review_figures")
    else:
        plot_index = write_review_figures(Path(args.background_psd_curves), out / "review_figures")
    plot_index.to_csv(out / "psd_response_review_figure_index_per_channel_v1.csv", index=False, encoding="utf-8-sig")
    write_json(out / "psd_response_per_channel_run_config_v1.json", {
        "frequency_dataset": args.frequency_dataset,
        "background_psd_curves": args.background_psd_curves,
        "fft_root": args.fft_root,
        "plot_source": args.plot_source,
        "plot_bin_hz": PLOT_BIN_HZ if args.plot_source == "fft_current" else None,
        "plot_downsampling": "median_per_bin_readability_match_original_resolution" if args.plot_source == "fft_current" else None,
        "output": args.output,
        "channel_mode": "per_channel_no_channel_aggregation",
        "active_conditions": list(ACTIVE.keys()),
        "distance_sets": ["2m3m", "2m3m5m"],
        "response_unit": "dB difference for feature matrix; psd_gain_dB for review curves",
        "scope_guard": "No ML, no 50Hz-30Hz, no TDMS/FFT rerun, no background formula change.",
    })
    write_report(out, response, consistency, candidates, channel_summary, plot_index)
    print(f"Per-channel Background-Subtracted PSD Response Consistency v1 output: {out}")


def build_response_matrix(path):
    if not path.exists():
        raise FileNotFoundError(f"Missing frequency feature dataset: {path}")
    df = pd.read_csv(path)
    if "analysis_mode" in df.columns:
        df = df[df["analysis_mode"].astype(str).str.lower().eq("strict")].copy()
    df["file_id"] = df["file_id"].astype(str).map(normalize_file_id)
    rows = []
    for active_condition, rpm in ACTIVE.items():
        for distance in DISTANCES:
            bg = df[(df["distance"] == distance) & (df["rpm"] == "0Hz")]
            ac = df[(df["distance"] == distance) & (df["rpm"] == rpm)]
            for channel in CHANNELS:
                bgc = bg[bg["channel"] == channel]
                acc = ac[ac["channel"] == channel]
                if bgc.empty or acc.empty:
                    continue
                for feature, fbg in bgc.groupby("feature_name"):
                    fac = acc[acc["feature_name"] == feature]
                    if fac.empty:
                        continue
                    bg_vals = pd.to_numeric(fbg["feature_value"], errors="coerce").dropna()
                    ac_vals = pd.to_numeric(fac["feature_value"], errors="coerce").dropna()
                    if bg_vals.empty or ac_vals.empty:
                        continue
                    rows.append({
                        "active_condition": active_condition,
                        "distance": distance,
                        "channel": channel,
                        "feature_name": f"freq__{feature}",
                        "feature_domain": "frequency",
                        "response_value": float(ac_vals.median() - bg_vals.median()),
                        "response_unit": "dB_feature_difference",
                        "n_files_active": int(ac_vals.size),
                        "n_files_background": int(bg_vals.size),
                        "qc_flag": join_qc(fac.get("qc_flag", pd.Series(dtype=str)).tolist() + fbg.get("qc_flag", pd.Series(dtype=str)).tolist()),
                        "channel_status_note": channel_status_note(distance, channel),
                    })
    return pd.DataFrame(rows)


def build_consistency(matrix):
    rows = []
    for (active, channel, feature), group in matrix.groupby(["active_condition", "channel", "feature_name"]):
        values = {row["distance"]: float(row["response_value"]) for _, row in group.iterrows()}
        for distance_set, dists in [("2m3m", ["2m", "3m"]), ("2m3m5m", ["2m", "3m", "5m"])]:
            if not all(d in values for d in dists):
                continue
            vals = [values[d] for d in dists]
            level, notes = consistency_level(vals, distance_set)
            rows.append({
                "active_condition": active,
                "channel": channel,
                "distance_set": distance_set,
                "feature_name": feature,
                "feature_domain": "frequency",
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
                "channel_status_note": channel_status_note("", channel),
                "notes": notes,
            })
    return pd.DataFrame(rows)


def build_candidates(consistency):
    rows = []
    for (active, channel, feature), group in consistency.groupby(["active_condition", "channel", "feature_name"]):
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
        else:
            category = "reject_or_unclear"
        rows.append({
            "active_condition": active,
            "channel": channel,
            "feature_name": feature,
            "candidate_category": category,
            "consistency_2m3m": g23["consistency_level"],
            "consistency_2m3m5m": full_level,
            "weak_5m_warning": bool(gfull["weak_5m_warning"]) if gfull is not None else False,
            "channel_status_note": channel_status_note("", channel),
            "notes": "per-channel response-consistency screen, not final science conclusion",
        })
    return pd.DataFrame(rows)


def build_channel_summary(consistency):
    rows = []
    for (active, distance_set, channel), group in consistency.groupby(["active_condition", "distance_set", "channel"]):
        counts = group["consistency_level"].value_counts().to_dict()
        rows.append({
            "active_condition": active,
            "distance_set": distance_set,
            "channel": channel,
            "n_features": int(len(group)),
            "n_strong": int(counts.get("strong", 0)),
            "n_moderate": int(counts.get("moderate", 0)),
            "n_weak": int(counts.get("weak", 0)),
            "n_inconsistent": int(counts.get("inconsistent", 0)),
            "top_strong_features": json.dumps(group[group["consistency_level"].isin(["strong", "moderate"])]["feature_name"].head(8).tolist(), ensure_ascii=False),
            "channel_status_note": channel_status_note("", channel),
        })
    return pd.DataFrame(rows)


def write_review_figures(curves_path, figure_dir):
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
    for channel in CHANNELS:
        cdf = df[df["channel"] == channel].copy()
        for active_condition, rpm_value in [("30Hz_minus_0Hz", 30.0), ("50Hz_minus_0Hz", 50.0)]:
            adf = cdf[np.isclose(cdf["pump_freq_hz"], rpm_value)].copy()
            for distance_set, dists in [("2m3m", ["2m", "3m"]), ("2m3m5m", ["2m", "3m", "5m"])]:
                for low, high in WINDOWS:
                    seg = adf[(adf["freq_hz"] >= low) & (adf["freq_hz"] <= high)].copy()
                    if seg.empty:
                        continue
                    out_dir = figure_dir / channel / active_condition / distance_set
                    out_dir.mkdir(parents=True, exist_ok=True)
                    path = out_dir / f"{channel}_{active_condition}_{distance_set}_{int(low/1000):03d}_{int(high/1000):03d}k.png"
                    plot_segment(seg, channel, active_condition, distance_set, dists, low, high, path)
                    rows.append({
                        "channel": channel,
                        "active_condition": active_condition,
                        "distance_set": distance_set,
                        "freq_window_low_hz": low,
                        "freq_window_high_hz": high,
                        "plot_path": str(path),
                        "aggregation": "single channel; no channel aggregation",
                        "channel_status_note": channel_status_note("", channel),
                    })
    return pd.DataFrame(rows)


def write_review_figures_from_fft(fft_root, figure_dir):
    figure_dir.mkdir(parents=True, exist_ok=True)
    group_curves = build_group_channel_psd_curves(fft_root)
    rows = []
    for channel in CHANNELS:
        for active_condition, rpm in ACTIVE.items():
            for distance_set, dists in [("2m3m", ["2m", "3m"]), ("2m3m5m", ["2m", "3m", "5m"])]:
                for low, high in WINDOWS:
                    out_dir = figure_dir / channel / active_condition / distance_set
                    out_dir.mkdir(parents=True, exist_ok=True)
                    path = out_dir / f"{channel}_{active_condition}_{distance_set}_{int(low/1000):03d}_{int(high/1000):03d}k.png"
                    plot_fft_response_segment(group_curves, channel, rpm, distance_set, dists, low, high, path)
                    rows.append({
                        "channel": channel,
                        "active_condition": active_condition,
                        "distance_set": distance_set,
                        "freq_window_low_hz": low,
                        "freq_window_high_hz": high,
                        "plot_path": str(path),
                        "aggregation": "single channel; group median logPSD from current FFT files; active minus same-distance 0Hz",
                        "channel_status_note": channel_status_note("", channel),
                    })
    return pd.DataFrame(rows)


def build_group_channel_psd_curves(fft_root):
    curves = {}
    groups = [f"{distance}{rpm}" for distance in DISTANCES for rpm in ["0hz", "30hz", "50hz"]]
    usecols = ["frequency", *[f"amplitude{i}" for i in range(1, 13)]]
    for group in groups:
        group_dir = fft_root / group
        if not group_dir.exists():
            continue
        per_channel = {channel: [] for channel in CHANNELS}
        for csv_file in sorted(group_dir.glob("FFT_*.csv")):
            for chunk in pd.read_csv(csv_file, usecols=usecols, chunksize=250_000):
                chunk = chunk[(chunk["frequency"] >= 0.0) & (chunk["frequency"] <= 200_000.0)].copy()
                if chunk.empty:
                    continue
                freq = chunk["frequency"].to_numpy(dtype=float)
                for channel_idx, channel in enumerate(CHANNELS, start=1):
                    amp_col = f"amplitude{channel_idx}"
                    values = pd.to_numeric(chunk[amp_col], errors="coerce").to_numpy(dtype=float)
                    per_channel[channel].append(pd.DataFrame({
                        "frequency": freq,
                        "logpsd_db": 10.0 * np.log10(np.square(values) + EPS),
                    }))
        for channel, series in per_channel.items():
            if not series:
                continue
            all_rows = pd.concat(series, ignore_index=True)
            curves[(group, channel)] = all_rows.groupby("frequency", as_index=False)["logpsd_db"].median().sort_values("frequency")
    return curves


def plot_fft_response_segment(group_curves, channel, rpm, distance_set, dists, low, high, path):
    plt.figure(figsize=(10, 4.8))
    colors = {"2m": "#1f77b4", "3m": "#ff7f0e", "5m": "#2ca02c"}
    for distance in dists:
        active_group = f"{distance}{rpm.lower()}"
        background_group = f"{distance}0hz"
        active = group_curves.get((active_group, channel))
        background = group_curves.get((background_group, channel))
        if active is None or background is None:
            continue
        merged = active.merge(background, on="frequency", suffixes=("_active", "_background"))
        merged = merged[(merged["frequency"] >= low) & (merged["frequency"] <= high)].copy()
        if merged.empty:
            continue
        response = merged["logpsd_db_active"] - merged["logpsd_db_background"]
        plot_df = downsample_median_for_plot(merged["frequency"], response, PLOT_BIN_HZ)
        plt.plot(plot_df["frequency"] / 1000.0, plot_df["response"], linewidth=0.9, alpha=0.95, label=distance, color=colors.get(distance))
    plt.axhline(0, color="#555555", linewidth=0.8, linestyle="--")
    plt.xlim(low / 1000.0, high / 1000.0)
    plt.xlabel("frequency (kHz)")
    plt.ylabel("PSD response vs same-distance 0Hz (dB)")
    plt.title(f"{channel} | {rpm}-0Hz PSD response | {distance_set} | current FFT files, 25 Hz readable bins | {int(low/1000)}-{int(high/1000)} kHz")
    note = channel_status_note("", channel)
    if note:
        plt.text(0.01, 0.02, note, transform=plt.gca().transAxes, fontsize=8, color="#4d4d4d")
    plt.grid(True, alpha=0.25, linewidth=0.5)
    plt.legend(title="distance", fontsize=8)
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def downsample_median_for_plot(frequency, response, bin_hz):
    data = pd.DataFrame({
        "frequency": pd.to_numeric(frequency, errors="coerce"),
        "response": pd.to_numeric(response, errors="coerce"),
    }).dropna()
    if data.empty:
        return data
    data["plot_bin"] = np.floor(data["frequency"] / bin_hz).astype(int)
    return (
        data.groupby("plot_bin", as_index=False)
        .agg(frequency=("frequency", "median"), response=("response", "median"))
        .sort_values("frequency")[["frequency", "response"]]
    )


def plot_segment(seg, channel, active_condition, distance_set, dists, low, high, path):
    plt.figure(figsize=(10, 4.8))
    colors = {"2m": "#1f77b4", "3m": "#ff7f0e", "5m": "#2ca02c"}
    for distance in dists:
        group = f"{distance}{'30hz' if active_condition.startswith('30') else '50hz'}"
        cur = seg[seg["active_group"].astype(str).str.lower().eq(group)].sort_values("freq_hz")
        if cur.empty:
            continue
        plt.plot(cur["freq_hz"] / 1000.0, cur["psd_gain_dB"], linewidth=1.0, label=distance, color=colors.get(distance))
    plt.axhline(0, color="#555555", linewidth=0.8, linestyle="--")
    plt.xlim(low / 1000.0, high / 1000.0)
    plt.xlabel("frequency (kHz)")
    plt.ylabel("PSD gain vs same-distance 0Hz (dB)")
    plt.title(f"{channel} | {active_condition} PSD response | {distance_set} | {int(low/1000)}-{int(high/1000)} kHz")
    note = channel_status_note("", channel)
    if note:
        plt.text(0.01, 0.02, note, transform=plt.gca().transAxes, fontsize=8, color="#4d4d4d")
    plt.grid(True, alpha=0.25, linewidth=0.5)
    plt.legend(title="distance", fontsize=8)
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


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


def normalize_file_id(file_id):
    value = Path(str(file_id)).name
    if value.startswith("FFT_"):
        value = value[4:]
    return value


def channel_status_note(distance, channel):
    notes = []
    if channel == "channel9":
        notes.append("channel9 QC-sensitive, especially 5m pilot context")
    if channel == "channel5":
        notes.append("channel5 suspect/sensitive pilot channel")
    return "; ".join(notes)


def first_row(df):
    return None if df.empty else df.iloc[0]


def join_qc(values):
    vals = sorted({str(v) for v in values if str(v) and str(v) not in {"OK", "nan"}})
    return ";".join(vals) if vals else "OK"


def write_report(out, response, consistency, candidates, channel_summary, plot_index):
    report = Path("docs/BACKGROUND_SUBTRACTED_PSD_RESPONSE_CONSISTENCY_PER_CHANNEL_V1.md")
    report.parent.mkdir(parents=True, exist_ok=True)
    counts = candidates["candidate_category"].value_counts().to_dict() if not candidates.empty else {}
    levels = consistency.groupby(["active_condition", "distance_set"])["consistency_level"].value_counts().to_dict() if not consistency.empty else {}
    best_channels = channel_summary.sort_values(["n_strong", "n_moderate"], ascending=False).head(12)
    lines = [
        "# Background-Subtracted PSD Response Consistency Per-Channel v1",
        "",
        "## Purpose",
        "",
        "This is the per-channel companion to the channel-aggregated PSD response consistency analysis. It checks each channel separately so narrow response structures are not hidden by across-channel median aggregation.",
        "",
        "## Scope",
        "",
        "- PSD/frequency features only.",
        "- Active conditions: 30Hz-0Hz and 50Hz-0Hz.",
        "- Distance sets: 2m/3m and 2m/3m/5m.",
        "- Channel mode: each channel is analyzed separately; no channel aggregation or mask aggregation is applied.",
        "- No 50Hz-30Hz, no pump-net contrast, no ML, no TDMS/FFT rerun, and no background contrast formula change.",
        "",
        "## Outputs",
        "",
        f"- Feature response rows: {len(response)}",
        f"- Consistency rows: {len(consistency)}",
        f"- Review plots: {len(plot_index)}",
        f"- Candidate category counts: {counts}",
        "",
        "## Consistency Snapshot",
        "",
    ]
    for (active, distance_set, level), count in sorted(levels.items()):
        lines.append(f"- {active} / {distance_set} / {level}: {count}")
    lines += [
        "",
        "## Channels With More Strong/Moderate PSD Responses",
        "",
    ]
    for _, row in best_channels.iterrows():
        lines.append(f"- {row['active_condition']} / {row['distance_set']} / {row['channel']}: strong={row['n_strong']}, moderate={row['n_moderate']}, weak={row['n_weak']}, inconsistent={row['n_inconsistent']}")
    lines += [
        "",
        "## Review Figures",
        "",
        "Per-channel segmented overlays are under `review_figures/<channel>/<active_condition>/<distance_set>/`. Each plot covers one 20 kHz window from 0-200 kHz.",
        "",
        "## Interpretation Guard",
        "",
        "This output is for per-channel PSD response consistency screening and manual review. It is not an ML result and not a final scientific conclusion. channel9/channel5 notes are current pilot QC context, not permanent channel rules.",
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
