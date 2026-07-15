import argparse
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


GROUPS = ["2m0hz", "3m0hz", "5m0hz"]
WINDOWS = [(float(start), float(start + 20_000)) for start in range(0, 200_000, 20_000)]
PSD_COLUMNS = [
    "background_group",
    "channel",
    "freq_hz",
    "background_logpsd_median",
    "background_logpsd_p10",
    "background_logpsd_p90",
    "file_count_background",
    "df_hz",
]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Stable Peak Review v1: 0Hz background PSD 20 kHz segmented review plots.")
    parser.add_argument("--input", default=None, help="Path to background_psd_diff_curves.csv")
    parser.add_argument("--background-output", default="D:/Lab/results/26.5.12/background_contrast_v1")
    parser.add_argument("--output", default="analysis_out/stable_peak_review_v1")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    background_output = Path(args.background_output)
    input_path = Path(args.input) if args.input else background_output / "background_psd_diff_curves.csv"
    output_dir = Path(args.output)
    figure_dir = output_dir / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    expected_outputs = [
        output_dir / "stable_peak_review_index_v1.csv",
        output_dir / "stable_peak_review_coarse_summary_v1.csv",
        output_dir / "stable_peak_review_run_config_v1.json",
    ]
    if not args.force and all(path.exists() for path in expected_outputs):
        print(f"Stable Peak Review v1 outputs already exist: {output_dir}")
        return output_dir

    psd, audit = load_background_psd(input_path)
    index_rows, summary_rows = write_review_plots(psd, figure_dir)
    index = pd.DataFrame(index_rows)
    summary = pd.DataFrame(summary_rows)
    index.to_csv(output_dir / "stable_peak_review_index_v1.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(output_dir / "stable_peak_review_coarse_summary_v1.csv", index=False, encoding="utf-8-sig")
    run_config = {
        "input_path": str(input_path),
        "background_output": str(background_output),
        "output_dir": str(output_dir),
        "groups": GROUPS,
        "frequency_windows_hz": [{"low_hz": low, "high_hz": high} for low, high in WINDOWS],
        "plot_count": int(len(index)),
        "plot_method": "background_logpsd_median curve with optional p10-p90 shaded band",
        "aggregation_note": "Rows are grouped by background_group/channel/freq_hz and median aggregated to remove duplicate active-group references.",
        "scope_guard": "No new peak detection, no TDMS rerun, no FFT rerun, no background contrast formula change.",
    }
    write_json(output_dir / "stable_peak_review_run_config_v1.json", {"run_config": run_config, "input_audit": audit})
    write_markdown_index(output_dir / "stable_peak_review_index_v1.md", index)
    write_report(output_dir, input_path, index, summary, audit)
    print(f"Stable Peak Review v1 output: {output_dir}")
    return output_dir


def load_background_psd(input_path):
    if not input_path.exists():
        raise FileNotFoundError(f"PSD input not found: {input_path}")
    head = pd.read_csv(input_path, nrows=1)
    missing = set(PSD_COLUMNS).difference(head.columns)
    if missing:
        raise ValueError(f"{input_path} is missing required columns: {sorted(missing)}")
    frames = []
    chunks = pd.read_csv(input_path, usecols=PSD_COLUMNS, chunksize=500_000)
    for chunk in chunks:
        chunk = chunk[chunk["background_group"].astype(str).str.lower().isin(GROUPS)].copy()
        chunk = chunk[(chunk["freq_hz"] >= 0.0) & (chunk["freq_hz"] <= 200_000.0)].copy()
        frames.append(chunk)
    if not frames:
        raise ValueError(f"No 0Hz background PSD rows found in {input_path}")
    raw = pd.concat(frames, ignore_index=True)
    grouped = raw.groupby(["background_group", "channel", "freq_hz"], as_index=False).agg(
        background_logpsd_median=("background_logpsd_median", "median"),
        background_logpsd_p10=("background_logpsd_p10", "median"),
        background_logpsd_p90=("background_logpsd_p90", "median"),
        file_count_background=("file_count_background", "max"),
        df_hz=("df_hz", "median"),
    )
    audit = {
        "input_path": str(input_path),
        "raw_rows_used": int(len(raw)),
        "deduplicated_rows": int(len(grouped)),
        "groups": sorted(grouped["background_group"].unique().tolist()),
        "channels": natural_sort(grouped["channel"].unique().tolist()),
        "freq_min_hz": float(grouped["freq_hz"].min()),
        "freq_max_hz": float(grouped["freq_hz"].max()),
        "median_df_hz": float(grouped["df_hz"].median()),
        "duplicate_reference_note": "background PSD rows can appear once per active comparison; deduplicated before plotting.",
    }
    return grouped, audit


def write_review_plots(psd, figure_dir):
    index_rows = []
    summary_rows = []
    for group in GROUPS:
        group_df = psd[psd["background_group"].astype(str).str.lower().eq(group)].copy()
        for channel in natural_sort(group_df["channel"].unique().tolist()):
            channel_df = group_df[group_df["channel"] == channel].sort_values("freq_hz")
            for low, high in WINDOWS:
                cur = channel_df[(channel_df["freq_hz"] >= low) & (channel_df["freq_hz"] <= high)].copy()
                if cur.empty:
                    continue
                out_dir = figure_dir / group / channel
                out_dir.mkdir(parents=True, exist_ok=True)
                window_id = f"{int(low/1000):03d}_{int(high/1000):03d}k"
                path = out_dir / f"{group}_{channel}_{window_id}_background_psd.png"
                plot_segment(cur, group, channel, low, high, path)
                max_idx = cur["background_logpsd_median"].idxmax()
                max_row = cur.loc[max_idx]
                index_rows.append({
                    "group": group,
                    "channel": channel,
                    "freq_window_low_hz": low,
                    "freq_window_high_hz": high,
                    "freq_window_label": f"{int(low/1000)}-{int(high/1000)} kHz",
                    "plot_path": str(path),
                    "source": "background_psd_diff_curves.csv",
                    "plot_type": "median PSD with p10-p90 band",
                    "scope_note": "manual review plot; no peak detection algorithm",
                })
                summary_rows.append({
                    "group": group,
                    "channel": channel,
                    "freq_window_low_hz": low,
                    "freq_window_high_hz": high,
                    "coarse_max_freq_hz": float(max_row["freq_hz"]),
                    "coarse_max_logpsd": float(max_row["background_logpsd_median"]),
                    "median_logpsd_in_window": float(cur["background_logpsd_median"].median()),
                    "p90_logpsd_in_window": float(cur["background_logpsd_median"].quantile(0.90)),
                    "n_frequency_bins": int(len(cur)),
                    "df_hz": float(cur["df_hz"].median()),
                    "note": "coarse max is a visual navigation aid only, not a peak detection result",
                })
    return index_rows, summary_rows


def plot_segment(cur, group, channel, low, high, path):
    x = cur["freq_hz"].to_numpy(dtype=float) / 1000.0
    y = cur["background_logpsd_median"].to_numpy(dtype=float)
    p10 = cur["background_logpsd_p10"].to_numpy(dtype=float)
    p90 = cur["background_logpsd_p90"].to_numpy(dtype=float)
    plt.figure(figsize=(10, 4.8))
    if np.isfinite(p10).any() and np.isfinite(p90).any():
        plt.fill_between(x, p10, p90, color="#9ecae1", alpha=0.35, linewidth=0, label="p10-p90")
    plt.plot(x, y, color="#08519c", linewidth=1.1, label="median PSD")
    plt.xlim(low / 1000.0, high / 1000.0)
    plt.xlabel("frequency (kHz)")
    plt.ylabel("log PSD / PSD dB")
    plt.title(f"{group} 0Hz background PSD | {channel} | {int(low/1000)}-{int(high/1000)} kHz")
    status_note = channel_status_note(group, channel)
    plt.text(0.01, 0.02, status_note, transform=plt.gca().transAxes, fontsize=8, color="#4d4d4d")
    plt.grid(True, alpha=0.25, linewidth=0.5)
    plt.legend(loc="best", fontsize=8)
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def channel_status_note(group, channel):
    notes = ["mask: none; background PSD review"]
    if channel == "channel9" and group.startswith("5m"):
        notes.append("channel9: known/suspect bad in 5m pilot context")
    if channel == "channel5":
        notes.append("channel5: suspect/sensitive channel in pilot context")
    return " | ".join(notes)


def write_markdown_index(path, index):
    lines = [
        "# Stable Peak Review v1 Plot Index",
        "",
        "This index lists 0Hz background PSD segmented plots for manual review. No peak detection or scientific conclusion is encoded here.",
        "",
        "| group | channel | window | plot |",
        "|---|---|---|---|",
    ]
    for _, row in index.iterrows():
        lines.append(f"| {row['group']} | {row['channel']} | {row['freq_window_label']} | `{row['plot_path']}` |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(output_dir, input_path, index, summary, audit):
    report = Path("docs/STABLE_PEAK_REVIEW_V1.md")
    report.parent.mkdir(parents=True, exist_ok=True)
    groups = ", ".join(sorted(index["group"].unique().tolist())) if not index.empty else "None"
    channels = ", ".join(natural_sort(index["channel"].unique().tolist())) if not index.empty else "None"
    lines = [
        "# Stable Peak Review v1",
        "",
        "## Purpose",
        "",
        "This step generates manual-review PSD plots for 0Hz backgrounds. The 0-200 kHz range is split into fixed 20 kHz windows so narrow, stable-looking peaks can be inspected visually across distance groups and channels.",
        "",
        "## Scope",
        "",
        "- Groups: 2m0hz, 3m0hz, 5m0hz only.",
        "- Frequency windows: 0-20, 20-40, 40-60, 60-80, 80-100, 100-120, 120-140, 140-160, 160-180, 180-200 kHz.",
        "- Plot unit: background median log PSD / PSD dB with p10-p90 band when available.",
        "- No new peak detection or peak identification algorithm was added.",
        "- No TDMS, FFT main pipeline, or background contrast formula was rerun.",
        "",
        "## Inputs",
        "",
        f"- PSD source: `{input_path}`",
        f"- Raw rows used: {audit['raw_rows_used']}",
        f"- Deduplicated rows used for plotting: {audit['deduplicated_rows']}",
        f"- Median frequency resolution: {audit['median_df_hz']:.6g} Hz",
        "",
        "## Outputs",
        "",
        f"- Output directory: `{output_dir}`",
        f"- Plot count: {len(index)}",
        f"- Groups covered: {groups}",
        f"- Channels covered: {channels}",
        "- Index CSV: `stable_peak_review_index_v1.csv`",
        "- Coarse visual-navigation summary: `stable_peak_review_coarse_summary_v1.csv`",
        "",
        "## Manual Review Guidance",
        "",
        "- Start with windows that previously looked relevant: 40-60 kHz, 120-140 kHz, 160-180 kHz, and 180-200 kHz.",
        "- Compare the same channel and same 20 kHz window across 2m0hz, 3m0hz, and 5m0hz.",
        "- Treat channel9 in 5m and channel5 as QC-sensitive while reviewing; this plot set does not mask them out.",
        "- Use the coarse max table only as a navigation aid. It is not a peak detector and should not replace visual confirmation.",
        "",
        "## Next Step",
        "",
        "After manual review, confirmed stable narrow peak candidates can be specified explicitly for a later feature extraction or validation step.",
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def natural_sort(values):
    def key(value):
        parts = re.split(r"(\d+)", str(value))
        return [int(part) if part.isdigit() else part for part in parts]
    return sorted(values, key=key)


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
