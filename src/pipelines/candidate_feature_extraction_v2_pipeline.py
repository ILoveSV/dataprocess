import argparse
import json
import math
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


FEATURES = [
    ("band_50_100k", "bandpower", 50_000.0, 100_000.0),
    ("band_100_200k", "bandpower", 100_000.0, 200_000.0),
    ("subband_50_60k", "subband", 50_000.0, 60_000.0),
    ("subband_60_70k", "subband", 60_000.0, 70_000.0),
    ("subband_70_80k", "subband", 70_000.0, 80_000.0),
    ("subband_80_90k", "subband", 80_000.0, 90_000.0),
    ("subband_90_100k", "subband", 90_000.0, 100_000.0),
    ("subband_100_120k", "subband", 100_000.0, 120_000.0),
    ("subband_120_140k", "subband", 120_000.0, 140_000.0),
    ("subband_140_160k", "subband", 140_000.0, 160_000.0),
    ("subband_160_180k", "subband", 160_000.0, 180_000.0),
    ("subband_180_200k", "subband", 180_000.0, 200_000.0),
    ("peakwin_53p5_55k", "peak_window", 53_500.0, 55_000.0),
    ("peakwin_137_139p5k", "peak_window", 137_000.0, 139_500.0),
    ("peakwin_177_179k", "peak_window", 177_000.0, 179_000.0),
]
CHANNELS = [f"channel{i}" for i in range(1, 13)]
AMPLITUDE_COLS = [f"amplitude{i}" for i in range(1, 13)]
EPS = 1e-30


def main(argv=None):
    parser = argparse.ArgumentParser(description="Feature Extraction v2: file-level/channel-level candidate features from FFT CSV files.")
    parser.add_argument("--fft-root", default="D:/Lab/process/26.5.12/frequency")
    parser.add_argument("--background-output", default="D:/Lab/results/26.5.12/background_contrast_v1")
    parser.add_argument("--output", default="analysis_out/feature_extraction_v2")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--chunksize", type=int, default=120_000)
    args = parser.parse_args(argv)

    fft_root = Path(args.fft_root)
    background_output = Path(args.background_output)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    audit = read_fft_audit(background_output / "fft_group_input_audit.csv")
    dataset_path = output_dir / "candidate_feature_dataset_v2.csv"
    if args.force or not dataset_path.exists():
        dataset = extract_dataset(fft_root, audit, chunksize=args.chunksize)
        dataset.to_csv(dataset_path, index=False, encoding="utf-8-sig")
    else:
        dataset = pd.read_csv(dataset_path)

    stability = build_stability_summary(dataset)
    stability.to_csv(output_dir / "feature_stability_summary_v2.csv", index=False, encoding="utf-8-sig")

    channel_summary = build_channel_summary(dataset)
    channel_summary.to_csv(output_dir / "channel_feature_summary_v2.csv", index=False, encoding="utf-8-sig")

    mode_delta = compare_all_vs_strict(stability)
    mode_delta.to_csv(output_dir / "all_vs_strict_feature_delta_v2.csv", index=False, encoding="utf-8-sig")

    write_boxplot(dataset, output_dir / "candidate_feature_boxplot_by_group_v2.png")
    write_run_summary(output_dir, fft_root, background_output, audit, dataset, stability, mode_delta)
    write_report(output_dir, fft_root, background_output, audit, dataset, stability, channel_summary, mode_delta)
    print(f"Feature Extraction v2 output: {output_dir}")
    return output_dir


def read_fft_audit(path):
    if not path.exists():
        return {"path": str(path), "warning_files": set(), "rows": []}
    df = pd.read_csv(path)
    warning = df[df["status"].astype(str).str.upper().eq("WARNING")].copy()
    return {
        "path": str(path),
        "warning_files": set(warning["file"].astype(str).tolist()),
        "rows": warning.to_dict("records"),
    }


def extract_dataset(fft_root, audit, chunksize=120_000):
    rows = []
    warning_files = audit["warning_files"]
    csv_files = sorted(Path(fft_root).glob("*/*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No FFT CSV files found under {fft_root}")
    for csv_file in csv_files:
        group = csv_file.parent.name
        parsed = parse_group(group)
        if parsed is None:
            continue
        file_rows = extract_file_features(csv_file, group, parsed, warning_files, chunksize)
        rows.extend(file_rows)
    return pd.DataFrame(rows)


def extract_file_features(csv_file, group, parsed, warning_files, chunksize):
    accum = {
        (feature_name, channel): {"power": 0.0, "bins": 0, "df_values": []}
        for feature_name, _, _, _ in FEATURES
        for channel in CHANNELS
    }
    usecols = ["frequency", *AMPLITUDE_COLS]
    file_warning = csv_file.name in warning_files
    nan_or_inf = False
    for chunk in pd.read_csv(csv_file, usecols=usecols, chunksize=chunksize):
        freq = chunk["frequency"].astype(float).to_numpy()
        if len(freq) > 1:
            df_hz = float(np.nanmedian(np.diff(freq)))
        else:
            df_hz = np.nan
        for feature_name, _, low, high in FEATURES:
            mask = (freq >= low) & (freq <= high)
            if not mask.any():
                continue
            for idx, channel in enumerate(CHANNELS, start=1):
                values = chunk[f"amplitude{idx}"].astype(float).to_numpy()[mask]
                if not np.isfinite(values).all():
                    nan_or_inf = True
                    values = values[np.isfinite(values)]
                if len(values) == 0:
                    continue
                item = accum[(feature_name, channel)]
                item["power"] += float(np.sum(values * values) * df_hz)
                item["bins"] += int(len(values))
                item["df_values"].append(df_hz)
    base_qc = []
    if file_warning:
        base_qc.append("frequency_axis_risk")
    if nan_or_inf:
        base_qc.append("nan_or_inf_filtered")
    rows = []
    for mode in ["all_data", "strict"]:
        if mode == "strict" and file_warning:
            continue
        for feature_name, feature_type, low, high in FEATURES:
            for channel in CHANNELS:
                item = accum[(feature_name, channel)]
                qc = list(base_qc)
                if item["bins"] == 0:
                    qc.append("no_bins")
                    value = np.nan
                else:
                    value = 10.0 * math.log10(item["power"] + EPS)
                rows.append({
                    "analysis_mode": mode,
                    "sample_id": f"{group}__{csv_file.stem}__{channel}",
                    "group": group,
                    "distance": parsed["distance"],
                    "rpm": parsed["rpm"],
                    "file_id": csv_file.name,
                    "channel": channel,
                    "feature_name": feature_name,
                    "feature_value": value,
                    "feature_type": feature_type,
                    "freq_low_hz": low,
                    "freq_high_hz": high,
                    "bin_count": item["bins"],
                    "frequency_resolution_hz": float(np.nanmedian(item["df_values"])) if item["df_values"] else np.nan,
                    "qc_flag": ";".join(qc) if qc else "OK",
                })
    return rows


def build_stability_summary(dataset):
    rows = []
    valid = dataset[np.isfinite(dataset["feature_value"].astype(float))].copy()
    for keys, group in valid.groupby(["analysis_mode", "group", "feature_name", "feature_type", "channel"]):
        values = group["feature_value"].astype(float)
        median = float(values.median())
        q1 = float(values.quantile(0.25))
        q3 = float(values.quantile(0.75))
        iqr = q3 - q1
        std = float(values.std(ddof=1)) if len(values) > 1 else 0.0
        mean = float(values.mean())
        p10 = float(values.quantile(0.10))
        p90 = float(values.quantile(0.90))
        cv = float(std / (abs(mean) + EPS))
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        stable = values.between(lower, upper)
        rows.append({
            "analysis_mode": keys[0],
            "group": keys[1],
            "feature_name": keys[2],
            "feature_type": keys[3],
            "channel": keys[4],
            "median": median,
            "mean": mean,
            "std": std,
            "iqr": iqr,
            "p10": p10,
            "p90": p90,
            "cv": cv,
            "stable_file_ratio": float(stable.mean()),
            "outlier_file_count": int((~stable).sum()),
            "file_count": int(len(values)),
        })
    return pd.DataFrame(rows)


def build_channel_summary(dataset):
    valid = dataset[np.isfinite(dataset["feature_value"].astype(float))].copy()
    grouped = valid.groupby(["analysis_mode", "group", "feature_name", "feature_type", "channel"], as_index=False).agg(
        median_feature_value=("feature_value", "median"),
        mean_feature_value=("feature_value", "mean"),
        file_count=("file_id", "nunique"),
    )
    rows = []
    for keys, group in grouped.groupby(["analysis_mode", "group", "feature_name"]):
        denom = float(group["median_feature_value"].abs().sum()) or EPS
        ranked = group.copy()
        ranked["rank"] = ranked["median_feature_value"].rank(ascending=False, method="min").astype(int)
        ranked["contribution_ratio"] = ranked["median_feature_value"].abs() / denom
        ranked["channel9_flag"] = ranked["channel"].eq("channel9")
        rows.append(ranked)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def compare_all_vs_strict(stability):
    keys = ["group", "feature_name", "feature_type", "channel"]
    all_df = stability[stability["analysis_mode"] == "all_data"][keys + ["median", "stable_file_ratio", "outlier_file_count"]]
    strict_df = stability[stability["analysis_mode"] == "strict"][keys + ["median", "stable_file_ratio", "outlier_file_count"]]
    merged = all_df.merge(strict_df, on=keys, suffixes=("_all_data", "_strict"), how="outer")
    merged["median_delta_strict_minus_all"] = merged["median_strict"] - merged["median_all_data"]
    merged["stable_file_ratio_delta"] = merged["stable_file_ratio_strict"] - merged["stable_file_ratio_all_data"]
    merged["strict_changed_flag"] = merged["median_delta_strict_minus_all"].abs() > 0.5
    return merged


def write_boxplot(dataset, path):
    core = [
        "band_50_100k",
        "band_100_200k",
        "peakwin_53p5_55k",
        "peakwin_137_139p5k",
        "peakwin_177_179k",
    ]
    data = dataset[(dataset["analysis_mode"] == "strict") & (dataset["feature_name"].isin(core))].copy()
    data = data.groupby(["group", "file_id", "feature_name"], as_index=False)["feature_value"].median()
    labels = []
    values = []
    for feature in core:
        for group in sorted(data["group"].unique(), key=group_sort_key):
            current = data[(data["feature_name"] == feature) & (data["group"] == group)]["feature_value"].dropna()
            if current.empty:
                continue
            labels.append(f"{feature}\n{group}")
            values.append(current.to_numpy())
    plt.figure(figsize=(16, 7))
    if values:
        plt.boxplot(values, labels=labels, showfliers=False)
        plt.xticks(rotation=70, ha="right", fontsize=7)
        plt.ylabel("log integrated amplitude power dB")
    else:
        plt.text(0.5, 0.5, "No strict-mode feature values", ha="center", va="center")
    plt.title("Candidate Feature File-Level Distribution by Group (strict mode)")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def write_run_summary(output_dir, fft_root, background_output, audit, dataset, stability, mode_delta):
    payload = {
        "fft_root": str(fft_root),
        "background_output": str(background_output),
        "feature_count": len(FEATURES),
        "groups": sorted(dataset["group"].unique().tolist(), key=group_sort_key),
        "file_count_all_data": int(dataset[dataset["analysis_mode"] == "all_data"]["file_id"].nunique()),
        "file_count_strict": int(dataset[dataset["analysis_mode"] == "strict"]["file_id"].nunique()),
        "warning_files": sorted(list(audit["warning_files"])),
        "row_count": int(len(dataset)),
        "strict_changed_rows": int(mode_delta["strict_changed_flag"].fillna(False).sum()) if not mode_delta.empty else 0,
        "feature_definition": "10*log10(sum(amplitude^2 * frequency_resolution_hz) + EPS) per FFT file/channel/window",
    }
    (output_dir / "feature_extraction_v2_run_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_report(output_dir, fft_root, background_output, audit, dataset, stability, channel_summary, mode_delta):
    Path("docs").mkdir(parents=True, exist_ok=True)
    report_path = Path("docs") / "CANDIDATE_FEATURE_EXTRACTION_V2.md"
    warning_files = sorted(list(audit["warning_files"]))
    strict_files = dataset[dataset["analysis_mode"] == "strict"]["file_id"].nunique()
    all_files = dataset[dataset["analysis_mode"] == "all_data"]["file_id"].nunique()
    stable = stability[stability["analysis_mode"] == "strict"]
    stable_top = stable.sort_values("stable_file_ratio", ascending=False).head(10)
    changed = mode_delta[mode_delta["strict_changed_flag"].fillna(False)] if not mode_delta.empty else pd.DataFrame()
    lines = [
        "# Candidate Feature Extraction v2",
        "",
        "## Scope",
        "",
        "- Generated file-level/channel-level candidate features from FFT CSV files.",
        "- Did not run machine learning.",
        "- Did not modify background contrast formulas.",
        "- Did not rerun TDMS conversion or FFT export.",
        "",
        "## Inputs",
        "",
        f"- FFT root: `{fft_root}`",
        f"- Background output: `{background_output}`",
        f"- FFT audit: `{background_output / 'fft_group_input_audit.csv'}`",
        "",
        "## Feature Definition",
        "",
        "- For each FFT file, channel, and candidate frequency window, the feature is `10*log10(sum(amplitude^2 * df_hz) + EPS)`.",
        "- This is a file-level frequency-domain integrated amplitude-power feature, not a reused group-median PSD zoom value.",
        "- Rows preserve `file_id` and `channel` dimensions.",
        "",
        "## Modes",
        "",
        f"- all-data mode file count: {all_files}",
        f"- strict mode file count: {strict_files}",
        f"- strict mode excludes {len(warning_files)} frequency-axis risk files.",
        "",
        "Frequency-axis risk files:",
    ]
    lines.extend(f"- `{name}`" for name in warning_files)
    lines.extend([
        "",
        "## Extracted Features",
        "",
    ])
    lines.extend(f"- `{name}` ({kind}, {low:g}-{high:g} Hz)" for name, kind, low, high in FEATURES)
    lines.extend([
        "",
        "## Stability",
        "",
        "- `stable_file_ratio` is the fraction of file values inside `[Q1 - 1.5*IQR, Q3 + 1.5*IQR]` for each group/feature/channel.",
        "- `outlier_file_count` is the number of files outside that interval.",
        "",
        "Top strict-mode stable rows:",
    ])
    for row in stable_top.itertuples():
        lines.append(f"- `{row.group} {row.channel} {row.feature_name}`: stable_file_ratio={row.stable_file_ratio:.3g}, median={row.median:.3g}")
    lines.extend([
        "",
        "## All-data vs strict-mode",
        "",
        f"- Rows with median shift > 0.5 dB after strict exclusion: {len(changed)}",
        "- See `all_vs_strict_feature_delta_v2.csv` for per group/feature/channel deltas.",
        "",
        "## ML Readiness",
        "",
        "- This output is suitable as a candidate feature table input for later validation or ML dataset construction.",
        "- Because frequency-axis-risk files exist, downstream ML should either use strict mode or include `qc_flag`/`analysis_mode` as filtering metadata.",
        "- No feature is promoted here as a physical mechanism.",
    ])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_group(group):
    match = re.fullmatch(r"(\d+(?:\.\d+)?)m(\d+(?:\.\d+)?)hz", group)
    if not match:
        return None
    distance = float(match.group(1))
    rpm = float(match.group(2))
    return {
        "distance": f"{int(distance)}m" if distance.is_integer() else f"{distance:g}m",
        "rpm": f"{int(rpm)}Hz" if rpm.is_integer() else f"{rpm:g}Hz",
    }


def group_sort_key(group):
    parsed = parse_group(str(group))
    if parsed is None:
        return (999, 999)
    return (float(parsed["distance"].replace("m", "")), float(parsed["rpm"].replace("Hz", "")))


if __name__ == "__main__":
    main()
