import argparse
import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd


CHANNELS = [f"channel{i}" for i in range(1, 13)]
FEATURE_UNITS = {
    "mean": "V",
    "median": "V",
    "dc_offset": "V",
    "min": "V",
    "max": "V",
    "peak_to_peak": "V",
    "std": "V",
    "rms": "V",
    "ac_rms": "V",
    "robust_sigma": "V",
    "mad": "V",
    "iqr": "V",
    "q05_q95_range": "V",
    "q10_q90_range": "V",
    "skewness": "unitless",
    "kurtosis": "unitless_fisher",
    "crest_factor": "unitless",
    "impulse_factor": "unitless",
    "shape_factor": "unitless",
    "tail_ratio": "unitless",
    "linear_slope": "V/s",
    "drift_span": "V",
    "drift_ratio_robust": "unitless",
    "start_end_delta": "V",
    "start_end_delta_ratio": "unitless",
    "spike_count_3sigma": "count",
    "spike_rate_3sigma": "count/s",
    "spike_count_5sigma": "count",
    "max_abs_z_robust": "unitless",
    "clipping_flag": "boolean",
    "rolling_rms_median": "V",
    "rolling_rms_iqr": "V",
    "rolling_rms_cv": "unitless",
    "rolling_mean_range": "V",
    "stable_window_ratio": "fraction",
    "longest_stable_duration": "s",
}
FEATURE_TYPES = {
    **{name: "amplitude" for name in ["mean", "median", "dc_offset", "min", "max", "peak_to_peak"]},
    **{name: "variation" for name in ["std", "rms", "ac_rms", "robust_sigma", "mad", "iqr", "q05_q95_range", "q10_q90_range"]},
    **{name: "distribution_shape" for name in ["skewness", "kurtosis", "crest_factor", "impulse_factor", "shape_factor", "tail_ratio"]},
    **{name: "drift" for name in ["linear_slope", "drift_span", "drift_ratio_robust", "start_end_delta", "start_end_delta_ratio"]},
    **{name: "spike" for name in ["spike_count_3sigma", "spike_rate_3sigma", "spike_count_5sigma", "max_abs_z_robust", "clipping_flag"]},
    **{name: "local_stability" for name in ["rolling_rms_median", "rolling_rms_iqr", "rolling_rms_cv", "rolling_mean_range", "stable_window_ratio", "longest_stable_duration"]},
}
EPS = 1e-30


def main(argv=None):
    parser = argparse.ArgumentParser(description="Time-Domain Feature Extraction v1 from existing time CSV files.")
    parser.add_argument("--time-root", default="D:/Lab/process/26.5.12/time")
    parser.add_argument("--output", default="analysis_out/time_domain_features_v1")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--rolling-window-sec", type=float, default=0.2)
    args = parser.parse_args(argv)

    time_root = Path(args.time_root)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset_path = output_dir / "time_domain_feature_dataset_v1.csv"
    if args.force or not dataset_path.exists():
        dataset, audit = extract_dataset(time_root, args.rolling_window_sec)
        dataset.to_csv(dataset_path, index=False, encoding="utf-8-sig")
        write_json(output_dir / "time_domain_feature_input_audit.json", audit)
    else:
        dataset = pd.read_csv(dataset_path)
        audit = read_json(output_dir / "time_domain_feature_input_audit.json")

    stability = build_stability_summary(dataset)
    stability.to_csv(output_dir / "time_domain_feature_stability_summary_v1.csv", index=False, encoding="utf-8-sig")
    write_schema(output_dir / "time_domain_feature_schema.json")
    write_run_config(output_dir / "time_domain_feature_run_config.json", time_root, args.rolling_window_sec)
    write_report(output_dir, time_root, audit, dataset, stability, args.rolling_window_sec)
    print(f"Time-domain feature output: {output_dir}")
    return output_dir


def extract_dataset(time_root, rolling_window_sec):
    rows = []
    audit = {"time_root": str(time_root), "groups": {}, "files": [], "warnings": []}
    group_dirs = [p for p in sorted(time_root.iterdir()) if p.is_dir() and parse_group(p.name)]
    for group_dir in group_dirs:
        group = group_dir.name
        parsed = parse_group(group)
        csv_files = sorted(group_dir.glob("*.csv"))
        audit["groups"][group] = {"file_count": len(csv_files), "files": []}
        for csv_file in csv_files:
            file_rows, file_audit = process_time_file(csv_file, group, parsed, rolling_window_sec)
            rows.extend(file_rows)
            audit["groups"][group]["files"].append(file_audit)
            audit["files"].append(file_audit)
            if file_audit["qc_warnings"]:
                audit["warnings"].append({"group": group, "file": csv_file.name, "warnings": file_audit["qc_warnings"]})
    return pd.DataFrame(rows), audit


def process_time_file(csv_file, group, parsed, rolling_window_sec):
    df = pd.read_csv(csv_file)
    channels = [c for c in CHANNELS if c in df.columns]
    missing = [c for c in CHANNELS if c not in df.columns]
    time = df["time"].astype(float).to_numpy() if "time" in df.columns else np.arange(len(df), dtype=float)
    sampling_rate, duration, time_warnings = sampling_info(time)
    file_qc = list(time_warnings)
    if missing:
        file_qc.append("missing_channel")
    file_audit = {
        "group": group,
        "file": csv_file.name,
        "path": str(csv_file),
        "n_samples": int(len(df)),
        "duration_seconds": duration,
        "sampling_rate_hz": sampling_rate,
        "channels": channels,
        "missing_channels": missing,
        "qc_warnings": file_qc.copy(),
        "nan_or_inf_channels": [],
        "constant_channels": [],
        "clipping_risk_channels": [],
        "too_short": len(df) < 10,
    }
    rows = []
    for channel in channels:
        values = df[channel].astype(float).to_numpy()
        feature_values, channel_qc = compute_channel_features(values, time, duration, sampling_rate, rolling_window_sec)
        if "nan_or_inf_filtered" in channel_qc:
            file_audit["nan_or_inf_channels"].append(channel)
        if "constant_signal" in channel_qc:
            file_audit["constant_channels"].append(channel)
        if "clipping_risk" in channel_qc:
            file_audit["clipping_risk_channels"].append(channel)
        qc = sorted(set(file_qc + channel_qc))
        for feature_name, feature_value in feature_values.items():
            rows.append({
                "sample_id": f"{group}__{csv_file.stem}__{channel}",
                "group": group,
                "distance": parsed["distance"],
                "rpm": parsed["rpm"],
                "file_id": csv_file.name,
                "channel": channel,
                "feature_name": feature_name,
                "feature_value": feature_value,
                "feature_type": FEATURE_TYPES[feature_name],
                "unit": FEATURE_UNITS[feature_name],
                "window_mode": f"non_overlapping_{rolling_window_sec:g}s",
                "qc_flag": ";".join(qc) if qc else "OK",
                "n_samples": int(len(values)),
                "duration_seconds": duration,
                "sampling_rate_hz": sampling_rate,
                "notes": feature_note(feature_name),
            })
    if file_audit["nan_or_inf_channels"]:
        file_audit["qc_warnings"].append("nan_or_inf")
    if file_audit["constant_channels"]:
        file_audit["qc_warnings"].append("constant_signal")
    if file_audit["clipping_risk_channels"]:
        file_audit["qc_warnings"].append("clipping_risk")
    return rows, file_audit


def compute_channel_features(values, time, duration, sampling_rate, rolling_window_sec):
    qc = []
    finite = np.isfinite(values)
    if not finite.all():
        qc.append("nan_or_inf_filtered")
        values = values[finite]
        time = time[finite]
    if len(values) < 10:
        qc.append("too_short")
        return empty_features(), qc
    if not np.isfinite(sampling_rate) or sampling_rate <= 0:
        qc.append("invalid_sampling_rate")
    mean = float(np.mean(values))
    median = float(np.median(values))
    vmin = float(np.min(values))
    vmax = float(np.max(values))
    centered = values - mean
    residual = values - median
    abs_centered = np.abs(centered)
    rms = float(np.sqrt(np.mean(values * values)))
    ac_rms = float(np.sqrt(np.mean(centered * centered)))
    mad = float(np.median(np.abs(values - median)))
    robust_sigma = 1.4826 * mad
    q05, q10, q25, q75, q90, q95, q99_abs, q95_abs = quantiles(values, abs_centered)
    iqr = float(q75 - q25)
    if np.isclose(vmax, vmin):
        qc.append("constant_signal")
    clipping = clipping_risk(values)
    if clipping:
        qc.append("clipping_risk")
    slope = linear_slope(time, values)
    drift_span = abs(slope) * duration if np.isfinite(slope) and np.isfinite(duration) else np.nan
    start_end = start_end_delta(values)
    denom = robust_sigma + EPS
    z = np.abs(values - median) / denom
    rolling = rolling_features(values, sampling_rate, rolling_window_sec, robust_sigma)
    features = {
        "mean": mean,
        "median": median,
        "dc_offset": mean,
        "min": vmin,
        "max": vmax,
        "peak_to_peak": vmax - vmin,
        "std": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
        "rms": rms,
        "ac_rms": ac_rms,
        "robust_sigma": robust_sigma,
        "mad": mad,
        "iqr": iqr,
        "q05_q95_range": float(q95 - q05),
        "q10_q90_range": float(q90 - q10),
        "skewness": float(pd.Series(values).skew()),
        "kurtosis": float(pd.Series(values).kurt()),
        "crest_factor": float(np.max(abs_centered) / (ac_rms + EPS)),
        "impulse_factor": float(np.max(abs_centered) / (np.mean(abs_centered) + EPS)),
        "shape_factor": float(rms / (np.mean(np.abs(values)) + EPS)),
        "tail_ratio": float(q99_abs / (q95_abs + EPS)),
        "linear_slope": slope,
        "drift_span": drift_span,
        "drift_ratio_robust": float(drift_span / denom) if np.isfinite(drift_span) else np.nan,
        "start_end_delta": start_end,
        "start_end_delta_ratio": float(start_end / denom) if np.isfinite(start_end) else np.nan,
        "spike_count_3sigma": int(np.sum(np.abs(values - median) > 3.0 * denom)),
        "spike_rate_3sigma": float(np.sum(np.abs(values - median) > 3.0 * denom) / duration) if duration > 0 else np.nan,
        "spike_count_5sigma": int(np.sum(np.abs(values - median) > 5.0 * denom)),
        "max_abs_z_robust": float(np.max(z)),
        "clipping_flag": int(clipping),
        **rolling,
    }
    return features, qc


def quantiles(values, abs_centered):
    q05, q10, q25, q75, q90, q95 = np.percentile(values, [5, 10, 25, 75, 90, 95])
    q95_abs, q99_abs = np.percentile(abs_centered, [95, 99])
    return q05, q10, q25, q75, q90, q95, q99_abs, q95_abs


def clipping_risk(values):
    n = len(values)
    if n == 0:
        return False
    vmin = np.min(values)
    vmax = np.max(values)
    max_ratio = np.mean(values == vmax)
    min_ratio = np.mean(values == vmin)
    return bool(max(max_ratio, min_ratio) >= 0.001)


def linear_slope(time, values):
    if len(values) < 2:
        return np.nan
    t = time - np.mean(time)
    denom = float(np.sum(t * t))
    if denom <= 0:
        return np.nan
    return float(np.sum(t * (values - np.mean(values))) / denom)


def start_end_delta(values):
    n = len(values)
    k = max(1, int(n * 0.10))
    return float(np.mean(values[-k:]) - np.mean(values[:k]))


def rolling_features(values, sampling_rate, window_sec, robust_sigma):
    if not np.isfinite(sampling_rate) or sampling_rate <= 0:
        return empty_rolling()
    window = max(10, int(round(sampling_rate * window_sec)))
    if len(values) < window:
        return empty_rolling()
    n_win = len(values) // window
    trimmed = values[: n_win * window].reshape(n_win, window)
    means = trimmed.mean(axis=1)
    centered = trimmed - means[:, None]
    local_rms = np.sqrt(np.mean(centered * centered, axis=1))
    rms_med = float(np.median(local_rms))
    rms_iqr = float(np.percentile(local_rms, 75) - np.percentile(local_rms, 25))
    mean_med = float(np.median(means))
    mean_ok = np.abs(means - mean_med) <= 3.0 * (robust_sigma + EPS)
    rms_ok = np.abs(local_rms - rms_med) <= 3.0 * (rms_iqr + EPS)
    stable = mean_ok & rms_ok
    return {
        "rolling_rms_median": rms_med,
        "rolling_rms_iqr": rms_iqr,
        "rolling_rms_cv": float(np.std(local_rms, ddof=1) / (np.mean(local_rms) + EPS)) if n_win > 1 else 0.0,
        "rolling_mean_range": float(np.max(means) - np.min(means)),
        "stable_window_ratio": float(np.mean(stable)),
        "longest_stable_duration": float(longest_true_run(stable) * window_sec),
    }


def longest_true_run(values):
    best = 0
    current = 0
    for value in values:
        if value:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def empty_features():
    return {name: np.nan for name in FEATURE_UNITS}


def empty_rolling():
    return {
        "rolling_rms_median": np.nan,
        "rolling_rms_iqr": np.nan,
        "rolling_rms_cv": np.nan,
        "rolling_mean_range": np.nan,
        "stable_window_ratio": np.nan,
        "longest_stable_duration": np.nan,
    }


def sampling_info(time):
    warnings = []
    if len(time) < 2:
        return np.nan, np.nan, ["too_short", "invalid_sampling_rate"]
    diffs = np.diff(time)
    dt = float(np.median(diffs))
    duration = float(time[-1] - time[0])
    if not np.isfinite(dt) or dt <= 0:
        warnings.append("invalid_sampling_rate")
        sr = np.nan
    else:
        sr = 1.0 / dt
    if len(diffs) and np.nanstd(diffs) > max(abs(dt) * 0.01, 1e-12):
        warnings.append("sampling_rate_jitter")
    if duration <= 0:
        warnings.append("invalid_duration")
    return sr, duration, warnings


def build_stability_summary(dataset):
    rows = []
    valid = dataset[pd.to_numeric(dataset["feature_value"], errors="coerce").notna()].copy()
    valid["feature_value"] = valid["feature_value"].astype(float)
    for keys, group in valid.groupby(["group", "distance", "rpm", "channel", "feature_name", "feature_type"]):
        values = group["feature_value"].astype(float)
        median = float(values.median())
        mad = float(np.median(np.abs(values - median)))
        robust_sigma = 1.4826 * mad
        if robust_sigma <= EPS:
            q1, q3 = values.quantile([0.25, 0.75])
            iqr = float(q3 - q1)
            lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            stable = values.between(lower, upper)
        else:
            stable = np.abs(values - median) <= 3.0 * robust_sigma
        qc_warning_count = int((group["qc_flag"].astype(str) != "OK").sum())
        rows.append({
            "analysis_mode": "all_data",
            "group": keys[0],
            "distance": keys[1],
            "rpm": keys[2],
            "channel": keys[3],
            "feature_name": keys[4],
            "feature_type": keys[5],
            "median": median,
            "mean": float(values.mean()),
            "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
            "iqr": float(values.quantile(0.75) - values.quantile(0.25)),
            "p10": float(values.quantile(0.10)),
            "p90": float(values.quantile(0.90)),
            "cv": float(values.std(ddof=1) / (abs(values.mean()) + EPS)) if len(values) > 1 else 0.0,
            "stable_file_ratio": float(np.mean(stable)),
            "outlier_file_count": int((~stable).sum()),
            "valid_file_count": int(len(values)),
            "qc_warning_count": qc_warning_count,
        })
    return pd.DataFrame(rows)


def write_schema(path):
    payload = {
        "common_keys_with_candidate_feature_dataset_v2": ["group", "distance", "rpm", "file_id", "channel"],
        "can_enter_separability_analysis": True,
        "features": [
            {
                "feature_name": name,
                "feature_type": FEATURE_TYPES[name],
                "unit": FEATURE_UNITS[name],
            }
            for name in FEATURE_UNITS
        ],
        "fields": {
            "sample_id": "unique group + file stem + channel identifier",
            "qc_flag": "semicolon-separated QC flags; OK when no warning was detected",
            "window_mode": "non-overlapping rolling window mode used for local stability features",
        },
    }
    write_json(path, payload)


def write_run_config(path, time_root, rolling_window_sec):
    write_json(path, {
        "time_root": str(time_root),
        "rolling_window_sec": rolling_window_sec,
        "rolling_window_mode": "non_overlapping",
        "stable_window_rule": "window is stable when local mean is within 3*robust_sigma of median local mean and local ac_rms is within 3*IQR of median local rms",
        "kurtosis_definition": "Fisher kurtosis as returned by pandas Series.kurt",
        "tail_ratio_definition": "q99(abs(x-mean)) / q95(abs(x-mean))",
        "clipping_risk_rule": "repeated exact min or max value ratio >= 0.001",
    })


def write_report(output_dir, time_root, audit, dataset, stability, rolling_window_sec):
    Path("docs").mkdir(exist_ok=True)
    report = Path("docs") / "TIME_DOMAIN_FEATURE_EXTRACTION_V1.md"
    qc_counts = dataset["qc_flag"].value_counts().head(10).to_dict() if not dataset.empty else {}
    lines = [
        "# Time-Domain Feature Extraction v1",
        "",
        "## Purpose",
        "",
        "PSD/bandpower features describe frequency-domain energy. Time-domain statistics add amplitude, variation, spike, drift, distribution-shape, and local-stability descriptors from raw voltage time series.",
        "",
        "## Inputs",
        "",
        f"- Time CSV root: `{time_root}`",
        f"- Groups read: {', '.join(sorted(audit.get('groups', {}).keys(), key=group_sort_key))}",
        "",
        "## Outputs",
        "",
        f"- `{output_dir / 'time_domain_feature_dataset_v1.csv'}`",
        f"- `{output_dir / 'time_domain_feature_stability_summary_v1.csv'}`",
        f"- `{output_dir / 'time_domain_feature_schema.json'}`",
        f"- `{output_dir / 'time_domain_feature_run_config.json'}`",
        f"- `{output_dir / 'time_domain_feature_input_audit.json'}`",
        "",
        "## Feature Groups",
        "",
        "- Amplitude/location: mean, median, dc_offset, min, max, peak_to_peak.",
        "- Variation/noise strength: std, rms, ac_rms, robust_sigma, mad, iqr, q05_q95_range, q10_q90_range.",
        "- Distribution shape: skewness, Fisher kurtosis, crest_factor, impulse_factor, shape_factor, tail_ratio.",
        "- Drift/trend: linear_slope, drift_span, drift_ratio_robust, start_end_delta, start_end_delta_ratio.",
        "- Spike/outlier: spike_count_3sigma, spike_rate_3sigma, spike_count_5sigma, max_abs_z_robust, clipping_flag.",
        f"- Local stability: rolling features using non-overlapping {rolling_window_sec:g}s windows.",
        "",
        "## QC",
        "",
        f"- QC flag counts: {qc_counts}",
        f"- Files with audit warnings: {len(audit.get('warnings', []))}",
        "- Abnormal files/channels are marked, not deleted.",
        "",
        "## Separability Readiness",
        "",
        "- The schema shares keys with frequency-domain `candidate_feature_dataset_v2.csv`: group, distance, rpm, file_id, channel.",
        "- These features can enter later separability analysis after optional QC filtering.",
        "",
        "## Scope Guard",
        "",
        "- No plots were generated.",
        "- No machine learning was run.",
        "- No PSD/background contrast results were modified.",
        "- No FFT workflow was rerun.",
        "- No abnormal channel or file was automatically removed.",
        "- No time-domain feature is interpreted here as a final physical mechanism.",
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def feature_note(feature_name):
    if feature_name == "dc_offset":
        return "dc_offset is reported as mean because no separate background reference is applied in this extraction."
    if feature_name == "kurtosis":
        return "Fisher kurtosis (normal distribution approximately 0)."
    if feature_name == "tail_ratio":
        return "q99(abs(x-mean)) / q95(abs(x-mean))."
    if feature_name == "clipping_flag":
        return "1 when repeated exact min/max ratio suggests clipping risk."
    return ""


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


def parse_group(group):
    match = re.fullmatch(r"(\d+(?:\.\d+)?)m(\d+(?:\.\d+)?)hz", str(group))
    if not match:
        return None
    distance = float(match.group(1))
    rpm = float(match.group(2))
    return {
        "distance": f"{int(distance)}m" if distance.is_integer() else f"{distance:g}m",
        "rpm": f"{int(rpm)}Hz" if rpm.is_integer() else f"{rpm:g}Hz",
    }


def group_sort_key(group):
    parsed = parse_group(group)
    if parsed is None:
        return (999, 999)
    return (float(parsed["distance"].replace("m", "")), float(parsed["rpm"].replace("Hz", "")))


if __name__ == "__main__":
    main()
