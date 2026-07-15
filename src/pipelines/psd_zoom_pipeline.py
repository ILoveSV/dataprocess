import argparse
import json
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.core.config_loader import load_config


logger = logging.getLogger("data_process")

FREQUENCY_RANGES = [
    {"frequency_range": "50-100k", "plot_id": "50_100k", "low_hz": 50_000.0, "high_hz": 100_000.0},
    {"frequency_range": "100-200k", "plot_id": "100_200k", "low_hz": 100_000.0, "high_hz": 200_000.0},
]
REQUIRED_COLUMNS = {
    "distance_m",
    "active_group",
    "background_group",
    "pump_freq_hz",
    "channel",
    "freq_hz",
    "background_logpsd_median",
    "active_logpsd_median",
    "psd_gain_dB",
    "file_count_background",
    "file_count_active",
    "df_hz",
}
FILE_AGGREGATION_METHOD = (
    "reused background_psd_diff_curves.csv from background contrast; upstream PSD is "
    "group_median recomputed per channel, then median logPSD is used by compute_psd_gain_curves"
)
CHANNEL_AGGREGATION_METHOD = "median across active channels at each frequency"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate PSD zoom plots and summaries from existing background contrast PSD curves.")
    parser.add_argument("--input", default=None, help="Path to background_psd_diff_curves.csv")
    parser.add_argument("--background-output", default=None, help="Existing background contrast output directory")
    parser.add_argument("--output", "-o", default=None, help="PSD zoom output directory")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--plots", choices=["minimal", "none"], default="minimal")
    args = parser.parse_args(argv)

    config = load_config()
    default_background = Path(config["time_series_results_dir"]).parent / "background_contrast_v1"
    background_output = Path(args.background_output or default_background)
    input_path = Path(args.input or (background_output / "background_psd_diff_curves.csv"))
    output_dir = Path(args.output or (background_output / "psd_zoom"))
    output_dir.mkdir(parents=True, exist_ok=True)

    run_info = {
        "input_path": str(input_path),
        "background_output": str(background_output),
        "output_dir": str(output_dir),
        "frequency_ranges": FREQUENCY_RANGES,
        "file_aggregation_method": FILE_AGGREGATION_METHOD,
        "channel_aggregation_method": CHANNEL_AGGREGATION_METHOD,
    }

    outputs = [
        output_dir / "psd_zoom_summary.csv",
        output_dir / "psd_zoom_feature_summary.csv",
        output_dir / "psd_zoom_input_audit.json",
        output_dir / "psd_zoom_run_config.json",
    ]
    if not args.force and all(path.exists() for path in outputs):
        print(f"PSD zoom outputs already exist: {output_dir}")
        return output_dir

    df = read_input(input_path)
    audit = audit_input(df, background_output)
    summary, feature_summary, plot_records = build_zoom_outputs(df, audit)

    summary.to_csv(output_dir / "psd_zoom_summary.csv", index=False, encoding="utf-8-sig")
    feature_summary.to_csv(output_dir / "psd_zoom_feature_summary.csv", index=False, encoding="utf-8-sig")
    (output_dir / "psd_zoom_input_audit.json").write_text(json.dumps(to_jsonable(audit), indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / "psd_zoom_run_config.json").write_text(json.dumps(to_jsonable(run_info), indent=2, ensure_ascii=False), encoding="utf-8")

    if args.plots == "minimal":
        write_plots(plot_records, output_dir / "figures")

    write_markdown_report(output_dir, background_output, summary, feature_summary, audit, run_info)
    print(f"PSD zoom output: {output_dir}")
    return output_dir


def read_input(input_path):
    if not input_path.exists():
        raise FileNotFoundError(f"Required PSD curve input not found: {input_path}")
    df = pd.read_csv(input_path)
    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f"{input_path} is missing required columns: {sorted(missing)}")
    return df


def to_jsonable(value):
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return value


def audit_input(df, background_output):
    audit = {
        "status": "PASS",
        "warnings": [],
        "skipped": [],
        "distances": {},
        "fft_group_input_audit": inspect_fft_audit(background_output),
    }
    for distance, group in df.groupby("distance_m"):
        distance_key = _format_distance(distance)
        pumps = sorted(float(v) for v in group["pump_freq_hz"].dropna().unique())
        channels_by_group = {
            str(name): sorted(values.astype(str).unique().tolist(), key=channel_sort_key)
            for name, values in group.groupby("active_group")["channel"]
        }
        freq_counts = group.groupby(["active_group", "channel"])["freq_hz"].nunique()
        df_values = sorted(float(v) for v in group["df_hz"].dropna().unique())
        info = {
            "pumps_present": pumps,
            "has_0hz_background": group["background_group"].notna().any(),
            "has_30hz": 30.0 in pumps,
            "has_50hz": 50.0 in pumps,
            "channels_by_active_group": channels_by_group,
            "frequency_bin_count_min": int(freq_counts.min()) if len(freq_counts) else 0,
            "frequency_bin_count_max": int(freq_counts.max()) if len(freq_counts) else 0,
            "frequency_resolution_hz_median": float(np.nanmedian(df_values)) if df_values else np.nan,
            "ranges": {},
        }
        if not (info["has_0hz_background"] and info["has_30hz"] and info["has_50hz"]):
            reason = "need 0Hz background plus 30Hz and 50Hz active groups"
            audit["skipped"].append({"distance": distance_key, "reason": reason})
            audit["warnings"].append(f"{distance_key}: {reason}")
        if info["frequency_bin_count_min"] != info["frequency_bin_count_max"]:
            audit["warnings"].append(f"{distance_key}: frequency axis length differs across active_group/channel rows")
        channel_sets = list(channels_by_group.values())
        if channel_sets and any(channels != channel_sets[0] for channels in channel_sets[1:]):
            audit["warnings"].append(f"{distance_key}: channel set differs across active groups")
        for freq_range in FREQUENCY_RANGES:
            current = group[(group["freq_hz"] >= freq_range["low_hz"]) & (group["freq_hz"] <= freq_range["high_hz"])]
            n_bins = int(current["freq_hz"].nunique())
            range_info = {
                "n_frequency_bins": n_bins,
                "frequency_min_hz": float(current["freq_hz"].min()) if not current.empty else np.nan,
                "frequency_max_hz": float(current["freq_hz"].max()) if not current.empty else np.nan,
                "skipped": n_bins < 2,
                "skip_reason": "need at least 2 frequency bins" if n_bins < 2 else "",
            }
            info["ranges"][freq_range["frequency_range"]] = range_info
            if range_info["skipped"]:
                audit["skipped"].append({
                    "distance": distance_key,
                    "frequency_range": freq_range["frequency_range"],
                    "reason": range_info["skip_reason"],
                })
                audit["warnings"].append(f"{distance_key} {freq_range['frequency_range']}: {range_info['skip_reason']}")
        audit["distances"][distance_key] = info
    if audit["warnings"] or audit["skipped"] or audit["fft_group_input_audit"].get("warning_count", 0):
        audit["status"] = "WARNING"
    return audit


def inspect_fft_audit(background_output):
    path = Path(background_output) / "fft_group_input_audit.csv"
    if not path.exists():
        return {"path": str(path), "status": "NOT_FOUND", "warning_count": 0, "warning_files": []}
    try:
        df = pd.read_csv(path)
    except Exception as exc:
        return {"path": str(path), "status": "READ_FAILED", "warning_count": 0, "error": str(exc), "warning_files": []}
    warning_col = "status" if "status" in df.columns else None
    if warning_col:
        warnings = df[df[warning_col].astype(str).str.upper().str.contains("WARN")]
    else:
        text = df.astype(str).agg(" ".join, axis=1)
        warnings = df[text.str.upper().str.contains("WARN|DIFFER")]
    file_col = next((col for col in ["file", "file_name", "path", "relative_path"] if col in df.columns), None)
    files = warnings[file_col].dropna().astype(str).unique().tolist() if file_col else []
    return {
        "path": str(path),
        "status": "WARNING" if len(warnings) else "PASS",
        "warning_count": int(len(warnings)),
        "warning_files": files[:50],
    }


def build_zoom_outputs(df, audit):
    summary_rows = []
    feature_rows = []
    plot_records = []
    for distance in sorted(df["distance_m"].dropna().unique()):
        distance_group = df[df["distance_m"] == distance].copy()
        distance_key = _format_distance(distance)
        if any(item.get("distance") == distance_key and "frequency_range" not in item for item in audit["skipped"]):
            continue
        for freq_range in FREQUENCY_RANGES:
            range_key = freq_range["frequency_range"]
            range_audit = audit["distances"].get(distance_key, {}).get("ranges", {}).get(range_key, {})
            if range_audit.get("skipped"):
                continue
            zoom = distance_group[
                (distance_group["freq_hz"] >= freq_range["low_hz"])
                & (distance_group["freq_hz"] <= freq_range["high_hz"])
            ].copy()
            if zoom.empty:
                continue
            curves = build_curves_for_distance_range(zoom, distance, freq_range)
            summary_rows.extend(curves["summary_rows"])
            feature_rows.extend(curves["feature_rows"])
            plot_records.append({**curves["plot_record"], "distance": distance, "frequency_range": freq_range})
    summary = pd.DataFrame(summary_rows)
    feature_summary = pd.DataFrame(feature_rows)
    return summary, feature_summary, plot_records


def build_curves_for_distance_range(zoom, distance, freq_range):
    raw_rows = []
    gain_rows = []
    feature_rows = []
    plot_record = {"raw": {}, "gain": {}, "pump_net": None}

    bg_group = str(zoom["background_group"].dropna().iloc[0])
    bg = aggregate_curve(
        zoom[zoom["background_group"] == bg_group],
        value_col="background_logpsd_median",
        source_group=bg_group,
        comparison_type="raw_overlay",
        distance=distance,
        freq_range=freq_range,
        background_group=bg_group,
        active_group="",
    )
    raw_rows.extend(bg["rows"])
    feature_rows.append(bg["feature"])
    plot_record["raw"]["0Hz"] = bg["curve"]

    for pump in [30.0, 50.0]:
        active = zoom[zoom["pump_freq_hz"].astype(float) == pump]
        if active.empty:
            continue
        active_group = str(active["active_group"].dropna().iloc[0])
        raw = aggregate_curve(
            active,
            value_col="active_logpsd_median",
            source_group=active_group,
            comparison_type="raw_overlay",
            distance=distance,
            freq_range=freq_range,
            background_group=bg_group,
            active_group=active_group,
        )
        raw_rows.extend(raw["rows"])
        feature_rows.append(raw["feature"])
        plot_record["raw"][f"{int(pump)}Hz"] = raw["curve"]

        comparison = f"gain_{int(pump)}_vs_0"
        gain = aggregate_curve(
            active,
            value_col="psd_gain_dB",
            source_group=active_group,
            comparison_type=comparison,
            distance=distance,
            freq_range=freq_range,
            background_group=bg_group,
            active_group=active_group,
        )
        gain_rows.extend(gain["rows"])
        feature_rows.append(gain["feature"])
        plot_record["gain"][f"{int(pump)}Hz - 0Hz"] = gain["curve"]

    gain30 = plot_record["gain"].get("30Hz - 0Hz")
    gain50 = plot_record["gain"].get("50Hz - 0Hz")
    if gain30 is not None and gain50 is not None:
        merged = gain50.merge(gain30, on="frequency_hz", suffixes=("_50", "_30"))
        merged["value"] = merged["value_50"] - merged["value_30"]
        pump_curve = merged[["frequency_hz", "value"]].copy()
        plot_record["pump_net"] = pump_curve
        active50 = str(zoom[zoom["pump_freq_hz"].astype(float) == 50.0]["active_group"].dropna().iloc[0])
        active30 = str(zoom[zoom["pump_freq_hz"].astype(float) == 30.0]["active_group"].dropna().iloc[0])
        rows = curve_to_summary_rows(
            pump_curve,
            distance=distance,
            freq_range=freq_range,
            comparison_type="pump_net_50_minus_30",
            source_group=f"{active50} minus {active30}",
            background_group=bg_group,
            active_group=active50,
        )
        gain_rows.extend(rows)
        feature_rows.append(feature_metrics(
            pump_curve,
            distance=distance,
            freq_range=freq_range,
            comparison_type="pump_net_50_minus_30",
            source_group=f"{active50} minus {active30}",
            background_group=bg_group,
            active_group=active50,
        ))

    return {
        "summary_rows": raw_rows + gain_rows,
        "feature_rows": feature_rows,
        "plot_record": plot_record,
    }


def aggregate_curve(df, value_col, source_group, comparison_type, distance, freq_range, background_group, active_group):
    curve = (
        df.groupby("freq_hz", as_index=False)[value_col]
        .median()
        .rename(columns={"freq_hz": "frequency_hz", value_col: "value"})
        .sort_values("frequency_hz")
    )
    rows = curve_to_summary_rows(curve, distance, freq_range, comparison_type, source_group, background_group, active_group)
    feature = feature_metrics(curve, distance, freq_range, comparison_type, source_group, background_group, active_group)
    return {"curve": curve, "rows": rows, "feature": feature}


def curve_to_summary_rows(curve, distance, freq_range, comparison_type, source_group, background_group, active_group):
    return [
        {
            "distance": _format_distance(distance),
            "frequency_range": freq_range["frequency_range"],
            "comparison_type": comparison_type,
            "frequency_hz": float(row.frequency_hz),
            "value": float(row.value),
            "source_group": source_group,
            "background_group": background_group,
            "active_group": active_group,
            "channel_aggregation_method": CHANNEL_AGGREGATION_METHOD,
            "file_aggregation_method": FILE_AGGREGATION_METHOD,
        }
        for row in curve.itertuples()
    ]


def feature_metrics(curve, distance, freq_range, comparison_type, source_group, background_group, active_group):
    values = curve["value"].astype(float).to_numpy()
    freqs = curve["frequency_hz"].astype(float).to_numpy()
    valid = np.isfinite(values) & np.isfinite(freqs)
    values = values[valid]
    freqs = freqs[valid]
    if len(values) == 0:
        max_idx = None
        max_freq = np.nan
        max_value = np.nan
        median_value = np.nan
        mean_value = np.nan
        band_integral = np.nan
        prominence = np.nan
        peak_to_band_ratio = np.nan
        broadband_lift_score = np.nan
        freq_resolution = np.nan
    else:
        max_idx = int(np.nanargmax(values))
        max_freq = float(freqs[max_idx])
        max_value = float(values[max_idx])
        median_value = float(np.nanmedian(values))
        mean_value = float(np.nanmean(values))
        band_integral = float(np.trapezoid(values, freqs)) if len(values) > 1 else np.nan
        q90 = float(np.nanpercentile(values, 90))
        q50 = median_value
        prominence = float(max_value - q50)
        denom = max(abs(median_value), 1e-9)
        peak_to_band_ratio = float(abs(max_value) / denom)
        broadband_lift_score = float(np.mean(values > 0.0))
        freq_resolution = float(np.nanmedian(np.diff(freqs))) if len(freqs) > 1 else np.nan
    return {
        "distance": _format_distance(distance),
        "frequency_range": freq_range["frequency_range"],
        "comparison_type": comparison_type,
        "source_group": source_group,
        "background_group": background_group,
        "active_group": active_group,
        "max_gain_frequency_hz": max_freq,
        "max_gain_value": max_value,
        "median_gain_value": median_value,
        "mean_gain_value": mean_value,
        "integrated_gain": band_integral,
        "band_integral": band_integral,
        "peak_prominence_like_value": prominence,
        "peak_to_band_ratio": peak_to_band_ratio,
        "broadband_lift_score": broadband_lift_score,
        "n_valid_frequency_bins": int(len(values)),
        "frequency_resolution_hz": freq_resolution,
    }


def write_plots(plot_records, fig_dir):
    fig_dir.mkdir(parents=True, exist_ok=True)
    for record in plot_records:
        distance = record["distance"]
        freq_range = record["frequency_range"]
        suffix = f"{freq_range['plot_id']}_{_format_distance(distance)}"
        title_range = f"{freq_range['frequency_range']}Hz".replace("kHz", "kHz")
        raw_path = fig_dir / f"raw_psd_overlay_{suffix}.png"
        plot_curves(
            record["raw"],
            raw_path,
            title=f"Raw PSD Overlay, {_format_distance(distance)}, {title_range}",
            ylabel="log PSD / PSD dB",
        )
        gain_path = fig_dir / f"psd_gain_vs_background_{suffix}.png"
        plot_curves(
            record["gain"],
            gain_path,
            title=f"PSD Gain vs Background, {_format_distance(distance)}, {title_range}",
            ylabel="PSD gain dB",
        )
        if record["pump_net"] is not None:
            pump_path = fig_dir / f"pump_net_psd_{suffix}.png"
            plot_curves(
                {"50Hz net - 30Hz net": record["pump_net"]},
                pump_path,
                title=f"Pump Net PSD: (50Hz - 0Hz) - (30Hz - 0Hz), {_format_distance(distance)}, {title_range}",
                ylabel="pump net PSD contrast dB",
            )


def plot_curves(curves, output_path, title, ylabel):
    plt.figure(figsize=(11, 6))
    if not curves:
        plt.text(0.5, 0.5, "No data", ha="center", va="center")
    else:
        for label, curve in curves.items():
            plt.plot(curve["frequency_hz"] / 1000.0, curve["value"], label=label, linewidth=1.2)
        plt.legend()
        plt.xlabel("frequency kHz")
        plt.ylabel(ylabel)
    plt.title(title)
    plt.tight_layout()
    plt.savefig(output_path, dpi=160)
    plt.close()


def write_markdown_report(output_dir, background_output, summary, feature_summary, audit, run_info):
    docs_dir = Path("docs")
    docs_dir.mkdir(parents=True, exist_ok=True)
    report_path = docs_dir / "PSD_ZOOM_ANALYSIS_RESULT.md"
    lines = [
        "# PSD Zoom Analysis Result",
        "",
        f"Output directory: `{output_dir}`",
        f"Background contrast source: `{background_output}`",
        "",
        "## Added outputs",
        "",
        "- `psd_zoom_summary.csv`",
        "- `psd_zoom_feature_summary.csv`",
        "- `psd_zoom_input_audit.json`",
        "- `psd_zoom_run_config.json`",
        "- `figures/raw_psd_overlay_50_100k_<distance>.png`",
        "- `figures/raw_psd_overlay_100_200k_<distance>.png`",
        "- `figures/psd_gain_vs_background_50_100k_<distance>.png`",
        "- `figures/psd_gain_vs_background_100_200k_<distance>.png`",
        "- `figures/pump_net_psd_50_100k_<distance>.png`",
        "- `figures/pump_net_psd_100_200k_<distance>.png`",
        "",
        "## Reused data and definitions",
        "",
        "- Reused `background_psd_diff_curves.csv` from the existing background contrast output.",
        "- Reused the existing PSD gain definition: `active_logpsd_median - background_logpsd_median`.",
        f"- File aggregation: {run_info['file_aggregation_method']}.",
        f"- Channel aggregation in this zoom report: {run_info['channel_aggregation_method']}.",
        "",
        "## Raw overlay vs PSD gain",
        "",
        "- Raw PSD overlay plots show the channel-median logPSD curves for 0Hz, 30Hz, and 50Hz at the same distance.",
        "- PSD gain plots show the existing background contrast curve for active pump groups: 30Hz minus 0Hz and 50Hz minus 0Hz.",
        "- Pump net PSD is `(50Hz - 0Hz) - (30Hz - 0Hz)`, matching the existing Pump Net Contrast direction.",
        "",
        "## Metric definitions",
        "",
        "- `peak_prominence_like_value = max_gain_value - median_gain_value` within the zoom range.",
        "- `peak_to_band_ratio = abs(max_gain_value) / max(abs(median_gain_value), 1e-9)`. Larger values suggest a narrow peak dominates the band summary.",
        "- `broadband_lift_score = fraction of valid frequency bins with value > 0`. Values close to 1 suggest broad positive lift across the range.",
        "- `integrated_gain` / `band_integral` is the trapezoid integral of the plotted value over frequency.",
        "",
        "## Input audit",
        "",
        f"- Audit status: `{audit['status']}`",
        f"- Skipped items: {len(audit.get('skipped', []))}",
        f"- FFT audit warning count: {audit.get('fft_group_input_audit', {}).get('warning_count', 0)}",
        "",
    ]
    warning_files = audit.get("fft_group_input_audit", {}).get("warning_files", [])
    if warning_files:
        lines.append("FFT audit warning files:")
        lines.extend(f"- `{name}`" for name in warning_files)
        lines.append("")
    if audit.get("warnings"):
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in audit["warnings"][:30])
        lines.append("")
    lines.extend(["## Distance/range findings", ""])
    lines.extend(summarize_findings(feature_summary))
    lines.extend([
        "",
        "## Sub-band scan recommendation",
        "",
        "This run does not perform sub-band bandpower scanning. Based on PSD zoom only, a later human-approved sub-band scan may be useful where the zoom plots show narrow peaks or mixed behavior inside the broad 50-100k and 100-200k bands.",
        "",
        "## Scope guard",
        "",
        "- No background subtraction formula was changed.",
        "- No time-domain subtraction was performed.",
        "- No machine learning features were added.",
        "- No existing background contrast outputs were deleted.",
    ])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def summarize_findings(feature_summary):
    if feature_summary.empty:
        return ["- No feature summary rows were generated."]
    lines = []
    current = feature_summary[feature_summary["comparison_type"].isin(["gain_30_vs_0", "gain_50_vs_0", "pump_net_50_minus_30"])].copy()
    for keys, group in current.groupby(["distance", "frequency_range"]):
        lines.append(f"### {keys[0]} {keys[1]}")
        for row in group.sort_values("comparison_type").itertuples():
            shape = classify_shape(row.peak_to_band_ratio, row.broadband_lift_score)
            lines.append(
                f"- `{row.comparison_type}`: median={row.median_gain_value:.3g}, max={row.max_gain_value:.3g} "
                f"at {row.max_gain_frequency_hz:.3f} Hz, peak_to_band_ratio={row.peak_to_band_ratio:.3g}, "
                f"broadband_lift_score={row.broadband_lift_score:.3g}; interpretation={shape}."
            )
        lines.append("")
    return lines


def classify_shape(peak_to_band_ratio, broadband_lift_score):
    if pd.isna(peak_to_band_ratio) or pd.isna(broadband_lift_score):
        return "UNKNOWN"
    if broadband_lift_score >= 0.8 and peak_to_band_ratio <= 3.0:
        return "broadband lift-like"
    if peak_to_band_ratio >= 5.0 and broadband_lift_score < 0.8:
        return "narrow peak-dominated-like"
    return "mixed or needs visual review"


def _format_distance(distance):
    value = float(distance)
    return f"{int(value)}m" if value.is_integer() else f"{value:g}m"


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
