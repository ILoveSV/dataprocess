import argparse
import csv
import json
import math
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import kruskal
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import LabelEncoder


CHANNELS = [f"channel{i}" for i in range(1, 13)]
EPS = 1e-30
BANDS = [
    ("band_50_100k", 50_000.0, 100_000.0),
    ("band_100_200k", 100_000.0, 200_000.0),
    ("subband_50_60k", 50_000.0, 60_000.0),
    ("subband_60_70k", 60_000.0, 70_000.0),
    ("subband_70_80k", 70_000.0, 80_000.0),
    ("subband_80_90k", 80_000.0, 90_000.0),
    ("subband_90_100k", 90_000.0, 100_000.0),
    ("subband_100_120k", 100_000.0, 120_000.0),
    ("subband_120_140k", 120_000.0, 140_000.0),
    ("subband_140_160k", 140_000.0, 160_000.0),
    ("subband_160_180k", 160_000.0, 180_000.0),
    ("subband_180_200k", 180_000.0, 200_000.0),
    ("peakwin_53p5_55k", 53_500.0, 55_000.0),
    ("peakwin_137_139p5k", 137_000.0, 139_500.0),
    ("peakwin_177_179k", 177_000.0, 179_000.0),
]
WINDOW_FEATURES = [
    "window_bandpower_db",
    "window_peak_freq_hz",
    "window_peak_value_db",
    "window_peak_prominence_like",
    "window_band_median_db",
]
BASE_STABILITY_FEATURES = [
    "tf_bandpower_median",
    "tf_bandpower_mean",
    "tf_bandpower_iqr",
    "tf_bandpower_std",
    "tf_bandpower_cv",
    "tf_bandpower_p10",
    "tf_bandpower_p90",
    "tf_bandpower_range",
    "tf_bandpower_stability_ratio",
    "tf_bandpower_occupancy_ratio",
    "tf_longest_high_bandpower_duration",
    "tf_high_bandpower_event_count",
    "tf_peak_value_median",
    "tf_peak_value_iqr",
    "tf_peak_prominence_median",
    "tf_peak_prominence_iqr",
    "tf_peak_persistence_ratio",
    "tf_peak_presence_count",
    "tf_peak_freq_median",
    "tf_peak_freq_iqr",
    "tf_peak_freq_std",
    "tf_peak_freq_jitter_hz",
    "tf_peak_freq_stability_ratio",
    "tf_time_concentration_score",
    "tf_time_entropy",
    "tf_burstiness_score",
]
BACKGROUND_FEATURES = [
    "tf_background_relative_median_gain",
    "tf_background_threshold_occupancy_ratio",
    "tf_background_detection_margin",
]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Time-Frequency Stability Feature Analysis v1.")
    parser.add_argument("--time-root", default="D:/Lab/process/26.5.12/time")
    parser.add_argument("--output", default="analysis_out/time_frequency_stability_features_v1")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--window-sec", type=float, default=0.2)
    parser.add_argument("--overlap", type=float, default=0.0)
    args = parser.parse_args(argv)

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    window_path = out / "tf_window_feature_dataset_v1.csv"
    feature_path = out / "tf_stability_feature_dataset_v1.csv"

    if args.force or not window_path.exists() or not feature_path.exists():
        band_store, audit, run_config = extract_window_and_file_features(
            Path(args.time_root), out, args.window_sec, args.overlap
        )
        features = build_stability_feature_dataset(band_store, args.window_sec, args.overlap)
        features.to_csv(feature_path, index=False, encoding="utf-8-sig")
        write_json(out / "tf_stability_feature_input_audit_v1.json", audit)
        write_json(out / "tf_stability_feature_run_config_v1.json", run_config)
    else:
        features = pd.read_csv(feature_path)
        audit = read_json(out / "tf_stability_feature_input_audit_v1.json")
        run_config = read_json(out / "tf_stability_feature_run_config_v1.json")

    write_json(out / "tf_stability_feature_schema_v1.json", build_schema())
    summary = build_summary(features)
    summary.to_csv(out / "tf_stability_feature_summary_v1.csv", index=False, encoding="utf-8-sig")
    file_channel = build_matrix(features, "file_channel")
    file_agg = build_matrix(features, "file_agg")
    file_channel.to_csv(out / "tf_stability_feature_matrix_file_channel_v1.csv", index=False, encoding="utf-8-sig")
    file_agg.to_csv(out / "tf_stability_feature_matrix_file_agg_v1.csv", index=False, encoding="utf-8-sig")

    sep = build_separability(file_channel, file_agg)
    sep.to_csv(out / "tf_stability_feature_separability_summary_v1.csv", index=False, encoding="utf-8-sig")
    corr, redundancy = build_redundancy(file_agg)
    corr.to_csv(out / "tf_stability_feature_correlation_matrix_v1.csv", encoding="utf-8-sig")
    redundancy.to_csv(out / "tf_stability_feature_redundancy_summary_v1.csv", index=False, encoding="utf-8-sig")
    comparison = compare_existing(sep)
    comparison.to_csv(out / "tf_vs_existing_feature_comparison_v1.csv", index=False, encoding="utf-8-sig")
    roles = assign_roles(sep, redundancy)
    roles.to_csv(out / "tf_stability_feature_role_assignment_v1.csv", index=False, encoding="utf-8-sig")
    write_json(out / "recommended_tf_stability_feature_sets_v1.json", recommended_sets(roles))
    write_combined_recommendations(out, roles)
    plot_top_auc(sep, out / "tf_top_auc_bar_v1.png")
    plot_group_heatmap(features, sep, out / "tf_feature_group_median_heatmap_v1.png")
    write_report(out, features, summary, sep, roles, comparison, audit, run_config)
    print(f"Time-Frequency Stability Feature Analysis v1 output: {out}")


def extract_window_and_file_features(time_root, out, window_sec, overlap):
    window_path = out / "tf_window_feature_dataset_v1.csv"
    if window_path.exists():
        window_path.unlink()
    header_written = False
    band_store = {}
    audit = {"time_root": str(time_root), "groups": {}, "warnings": []}
    run_config = {
        "window_sec": window_sec,
        "overlap": overlap,
        "window_function": "hann",
        "n_fft": "per-file derived from round(sampling_rate_hz * window_sec)",
        "frequency_resolution_hz": "sampling_rate_hz / n_fft",
        "bandpower_formula": "10*log10(sum(periodogram_power_density * df_hz) + EPS)",
        "periodogram_power_density": "abs(rfft((x-mean)*hann))^2 / (sampling_rate_hz * sum(hann^2))",
        "remove_mean": True,
        "detrend": "mean removal only",
        "save_full_stft_matrix": False,
    }
    for group_dir in sorted(time_root.iterdir()):
        if not group_dir.is_dir():
            continue
        parsed = parse_group(group_dir.name)
        if parsed is None:
            continue
        csv_files = sorted(group_dir.glob("*.csv"))
        audit["groups"][group_dir.name] = {"file_count": len(csv_files), "files": []}
        for csv_file in csv_files:
            window_rows, file_band, file_audit = process_file(csv_file, group_dir.name, parsed, window_sec, overlap)
            audit["groups"][group_dir.name]["files"].append(file_audit)
            band_store.update(file_band)
            if window_rows:
                pd.DataFrame(window_rows).to_csv(
                    window_path,
                    mode="a",
                    header=not header_written,
                    index=False,
                    encoding="utf-8-sig",
                )
                header_written = True
    return band_store, audit, run_config


def process_file(path, group, parsed, window_sec, overlap):
    df = pd.read_csv(path)
    channels = [c for c in CHANNELS if c in df.columns]
    time = df["time"].to_numpy(dtype=float) if "time" in df.columns else np.arange(len(df), dtype=float)
    sr, duration, time_qc = sampling_info(time)
    qc = list(time_qc)
    missing = [c for c in CHANNELS if c not in channels]
    if missing:
        qc.append("missing_channels")
    if len(channels) == 0 or not np.isfinite(sr) or sr <= 0:
        qc.append("cannot_compute_tf")
        return [], {}, base_file_audit(path, channels, missing, sr, duration, 0, qc)
    data = df[channels].to_numpy(dtype=float)
    if not np.isfinite(data).all():
        qc.append("nan_or_inf")
    data = np.nan_to_num(data, nan=np.nanmedian(data[np.isfinite(data)]) if np.isfinite(data).any() else 0.0)
    nper = int(round(sr * window_sec))
    nper = max(16, nper)
    step = max(1, int(round(nper * (1.0 - overlap))))
    starts = list(range(0, max(len(data) - nper + 1, 0), step))
    if not starts:
        qc.append("too_short_for_window")
        return [], {}, base_file_audit(path, channels, missing, sr, duration, 0, qc)
    window = np.hanning(nper)
    win_energy = float(np.sum(window * window)) + EPS
    freqs = np.fft.rfftfreq(nper, d=1.0 / sr)
    df_hz = float(freqs[1] - freqs[0]) if len(freqs) > 1 else np.nan
    masks = {band_id: (freqs >= low) & (freqs <= high) for band_id, low, high in BANDS}
    no_bins = [band_id for band_id, mask in masks.items() if int(mask.sum()) == 0]
    if no_bins:
        qc.append("band_without_bins")
    rows = []
    store = {}
    for window_id, start in enumerate(starts):
        end = start + nper
        segment = data[start:end, :]
        segment = segment - np.nanmean(segment, axis=0)
        spec = np.fft.rfft(segment * window[:, None], axis=0)
        power = (np.abs(spec) ** 2) / (sr * win_energy + EPS)
        power_db = 10.0 * np.log10(power + EPS)
        start_sec = float(time[start]) if start < len(time) else float(start / sr)
        end_sec = float(time[end - 1]) if end - 1 < len(time) else float(end / sr)
        for band_id, low, high in BANDS:
            mask = masks[band_id]
            if int(mask.sum()) == 0:
                continue
            band_power = 10.0 * np.log10(np.nansum(power[mask, :], axis=0) * df_hz + EPS)
            band_median = np.nanmedian(power_db[mask, :], axis=0)
            peak_idx_local = np.nanargmax(power[mask, :], axis=0)
            band_freqs = freqs[mask]
            peak_freq = band_freqs[peak_idx_local]
            peak_value = np.nanmax(power_db[mask, :], axis=0)
            prominence = peak_value - band_median
            for ci, channel in enumerate(channels):
                values = {
                    "window_bandpower_db": band_power[ci],
                    "window_peak_freq_hz": peak_freq[ci],
                    "window_peak_value_db": peak_value[ci],
                    "window_peak_prominence_like": prominence[ci],
                    "window_band_median_db": band_median[ci],
                }
                key = (group, path.name, channel, band_id)
                store.setdefault(key, {"parsed": parsed, "low": low, "high": high, "sampling_rate_hz": sr, "frequency_resolution_hz": df_hz, "qc": set(qc), "windows": []})
                store[key]["windows"].append(values)
                for feature_name, feature_value in values.items():
                    rows.append({
                        "sample_id": f"{group}__{path.stem}__{channel}__w{window_id:03d}__{band_id}",
                        "group": group,
                        "distance": parsed["distance"],
                        "rpm": parsed["rpm"],
                        "file_id": path.name,
                        "channel": channel,
                        "window_id": window_id,
                        "window_start_sec": start_sec,
                        "window_end_sec": end_sec,
                        "band_id": band_id,
                        "freq_low_hz": low,
                        "freq_high_hz": high,
                        "feature_name": feature_name,
                        "feature_value": feature_value,
                        "feature_type": window_feature_type(feature_name),
                        "unit": window_unit(feature_name),
                        "qc_flag": join_qc(qc),
                        "n_samples_window": nper,
                        "sampling_rate_hz": sr,
                        "frequency_resolution_hz": df_hz,
                        "notes": window_note(feature_name),
                    })
    file_audit = base_file_audit(path, channels, missing, sr, duration, len(starts), qc)
    file_audit["frequency_resolution_hz"] = df_hz
    file_audit["bands_without_bins"] = no_bins
    return rows, store, file_audit


def build_stability_feature_dataset(band_store, window_sec, overlap):
    bg = {}
    for key, rec in band_store.items():
        group, file_id, channel, band_id = key
        if rec["parsed"]["rpm"] == "0Hz":
            bg.setdefault((rec["parsed"]["distance"], channel, band_id), []).extend([w["window_bandpower_db"] for w in rec["windows"]])
    bg_stats = {}
    for key, values in bg.items():
        arr = np.asarray(values, dtype=float)
        bg_stats[key] = {"median": float(np.nanmedian(arr)), "p95": float(np.nanpercentile(arr, 95))}
    rows = []
    for key, rec in band_store.items():
        group, file_id, channel, band_id = key
        windows = rec["windows"]
        bp = np.asarray([w["window_bandpower_db"] for w in windows], dtype=float)
        pk = np.asarray([w["window_peak_value_db"] for w in windows], dtype=float)
        prom = np.asarray([w["window_peak_prominence_like"] for w in windows], dtype=float)
        pf = np.asarray([w["window_peak_freq_hz"] for w in windows], dtype=float)
        median = np.nanmedian(bp)
        iqr = np.nanpercentile(bp, 75) - np.nanpercentile(bp, 25)
        mad = np.nanmedian(np.abs(bp - median))
        stable = np.abs(bp - median) <= 3.0 * (1.4826 * mad + EPS)
        threshold = median + iqr
        high = bp > threshold
        low, high_freq = rec["low"], rec["high"]
        center = (low + high_freq) / 2.0
        tolerance = min(500.0, max((high_freq - low) * 0.25, rec["frequency_resolution_hz"]))
        values = {
            "tf_bandpower_median": median,
            "tf_bandpower_mean": np.nanmean(bp),
            "tf_bandpower_iqr": iqr,
            "tf_bandpower_std": np.nanstd(bp, ddof=1) if len(bp) > 1 else 0.0,
            "tf_bandpower_cv": np.nanstd(bp, ddof=1) / (abs(np.nanmean(bp)) + EPS) if len(bp) > 1 else 0.0,
            "tf_bandpower_p10": np.nanpercentile(bp, 10),
            "tf_bandpower_p90": np.nanpercentile(bp, 90),
            "tf_bandpower_range": np.nanmax(bp) - np.nanmin(bp),
            "tf_bandpower_stability_ratio": np.nanmean(stable),
            "tf_bandpower_occupancy_ratio": np.nanmean(high),
            "tf_longest_high_bandpower_duration": longest_true_run(high) * window_sec * (1.0 - overlap if overlap < 1 else 1.0),
            "tf_high_bandpower_event_count": count_true_events(high),
            "tf_peak_value_median": np.nanmedian(pk),
            "tf_peak_value_iqr": np.nanpercentile(pk, 75) - np.nanpercentile(pk, 25),
            "tf_peak_prominence_median": np.nanmedian(prom),
            "tf_peak_prominence_iqr": np.nanpercentile(prom, 75) - np.nanpercentile(prom, 25),
            "tf_peak_persistence_ratio": np.nanmean(prom > 3.0),
            "tf_peak_presence_count": np.nansum(prom > 3.0),
            "tf_peak_freq_median": np.nanmedian(pf),
            "tf_peak_freq_iqr": np.nanpercentile(pf, 75) - np.nanpercentile(pf, 25),
            "tf_peak_freq_std": np.nanstd(pf, ddof=1) if len(pf) > 1 else 0.0,
            "tf_peak_freq_jitter_hz": np.nanstd(pf, ddof=1) if len(pf) > 1 else 0.0,
            "tf_peak_freq_stability_ratio": np.nanmean(np.abs(pf - center) <= tolerance),
            "tf_time_concentration_score": top_fraction_share(bp, 0.10),
            "tf_time_entropy": entropy_from_db(bp),
            "tf_burstiness_score": (np.nanpercentile(bp, 90) - median) / (abs(median) + EPS),
        }
        bg_key = (rec["parsed"]["distance"], channel, band_id)
        if bg_key in bg_stats:
            values["tf_background_relative_median_gain"] = median - bg_stats[bg_key]["median"]
            values["tf_background_threshold_occupancy_ratio"] = np.nanmean(bp > bg_stats[bg_key]["p95"])
            values["tf_background_detection_margin"] = median - bg_stats[bg_key]["p95"]
            bg_note = "background threshold uses same-distance 0Hz window bandpower p95/median"
        else:
            values["tf_background_relative_median_gain"] = np.nan
            values["tf_background_threshold_occupancy_ratio"] = np.nan
            values["tf_background_detection_margin"] = np.nan
            bg_note = "skipped: no same-distance 0Hz background threshold"
        for feature_name, feature_value in values.items():
            rows.append({
                "sample_id": f"{group}__{Path(file_id).stem}__{channel}__{band_id}",
                "group": group,
                "distance": rec["parsed"]["distance"],
                "rpm": rec["parsed"]["rpm"],
                "file_id": file_id,
                "channel": channel,
                "feature_domain": "time_frequency_stability",
                "band_id": band_id,
                "freq_low_hz": low,
                "freq_high_hz": high_freq,
                "feature_name": feature_name,
                "feature_value": feature_value,
                "feature_type": stability_feature_type(feature_name),
                "unit": stability_unit(feature_name),
                "qc_flag": join_qc(rec["qc"]),
                "n_windows": len(windows),
                "window_sec": window_sec,
                "overlap": overlap,
                "notes": bg_note if feature_name in BACKGROUND_FEATURES else stability_note(feature_name),
            })
    return pd.DataFrame(rows)


def build_summary(features):
    data = features[pd.to_numeric(features["feature_value"], errors="coerce").notna()].copy()
    data["feature_value"] = data["feature_value"].astype(float)
    rows = []
    for keys, group in data.groupby(["group", "distance", "rpm", "channel", "band_id", "feature_name"]):
        values = group["feature_value"]
        med = float(values.median())
        mad = float(np.median(np.abs(values - med)))
        stable = np.abs(values - med) <= 3.0 * (1.4826 * mad + EPS)
        rows.append({
            "group": keys[0], "distance": keys[1], "rpm": keys[2], "channel": keys[3], "band_id": keys[4], "feature_name": keys[5],
            "median": med, "mean": float(values.mean()), "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
            "iqr": float(values.quantile(0.75) - values.quantile(0.25)), "p10": float(values.quantile(0.10)), "p90": float(values.quantile(0.90)),
            "cv": float(values.std(ddof=1) / (abs(values.mean()) + EPS)) if len(values) > 1 else 0.0,
            "stable_file_ratio": float(stable.mean()), "outlier_file_count": int((~stable).sum()),
            "valid_file_count": int(len(values)), "qc_warning_count": int((group["qc_flag"].astype(str) != "OK").sum()),
        })
    return pd.DataFrame(rows)


def build_matrix(features, grain):
    data = features.copy()
    data["feature_column"] = data["band_id"].astype(str) + "__" + data["feature_name"].astype(str)
    if grain == "file_channel":
        idx = ["group", "distance", "rpm", "file_id", "channel"]
        matrix = data.pivot_table(index=idx, columns="feature_column", values="feature_value", aggfunc="median").reset_index()
        qc = data.groupby(idx, as_index=False)["qc_flag"].agg(join_qc_series)
        matrix = matrix.merge(qc, on=idx, how="left")
        matrix.insert(0, "sample_id", matrix["group"].astype(str) + "__" + matrix["file_id"].astype(str) + "__" + matrix["channel"].astype(str))
    else:
        idx0 = ["group", "distance", "rpm", "file_id", "feature_column"]
        agg = data.groupby(idx0, as_index=False)["feature_value"].median()
        matrix = agg.pivot_table(index=["group", "distance", "rpm", "file_id"], columns="feature_column", values="feature_value", aggfunc="median").reset_index()
        matrix.insert(0, "sample_id", matrix["group"].astype(str) + "__" + matrix["file_id"].astype(str) + "__file_agg")
        matrix.insert(5, "aggregated_channel", "median_across_channels")
        qc = data.groupby(["group", "distance", "rpm", "file_id"], as_index=False)["qc_flag"].agg(join_qc_series)
        matrix = matrix.merge(qc, on=["group", "distance", "rpm", "file_id"], how="left")
    matrix.columns.name = None
    return matrix


def build_separability(file_channel, file_agg):
    rows = []
    for grain, matrix in [("file_channel", file_channel), ("file_agg", file_agg)]:
        for distance, group in matrix.groupby("distance"):
            cur = group[group["rpm"].isin(["0Hz", "30Hz", "50Hz"])].copy()
            cur["label"] = np.where(cur["rpm"] == "0Hz", "0Hz", "active")
            rows.extend(sep_rows(cur, "Task A active vs 0Hz", grain, distance, "all", "label"))
            cur = group[group["rpm"].isin(["30Hz", "50Hz"])].copy()
            rows.extend(sep_rows(cur, "Task B 30Hz vs 50Hz", grain, distance, "30/50Hz", "rpm"))
        for rpm, group in matrix.groupby("rpm"):
            rows.extend(sep_rows(group, "Task C distance", grain, "2/3/5m", rpm, "distance"))
        rows.extend(sep_rows(matrix[matrix["rpm"].isin(["0Hz", "30Hz", "50Hz"])].copy(), "Task D rpm 3-class", grain, "all", "0/30/50Hz", "rpm"))
    out = pd.DataFrame(rows)
    if not out.empty:
        out["separability_rank"] = out.groupby(["task_name", "sample_grain"])["single_feature_auc_or_macro_auc"].rank(ascending=False, method="min")
    return out


def sep_rows(data, task_name, grain, distance_scope, rpm_scope, label_col):
    meta = {"sample_id", "group", "distance", "rpm", "file_id", "channel", "aggregated_channel", "qc_flag", "label"}
    features = [c for c in data.columns if c not in meta]
    rows = []
    labels = sorted(data[label_col].dropna().astype(str).unique().tolist()) if label_col in data else []
    for col in features:
        cur = data[[col, label_col]].dropna()
        feature_name = col.split("__", 1)[1] if "__" in col else col
        band_id = col.split("__", 1)[0] if "__" in col else ""
        row = {
            "task_name": task_name, "sample_grain": grain, "feature_domain": "time_frequency_stability",
            "band_id": band_id, "feature_name": feature_name, "feature_type": stability_feature_type(feature_name),
            "distance_scope": distance_scope, "rpm_scope": rpm_scope, "n_samples": int(len(cur)),
            "class_labels": json.dumps(labels), "median_by_class": "{}", "iqr_by_class": "{}",
            "effect_size": np.nan, "overlap_score": np.nan, "single_feature_auc_or_macro_auc": np.nan,
            "separability_rank": np.nan, "qc_warning": burst_warning(feature_name), "notes": stability_note(feature_name),
            "skipped_reason": "",
        }
        counts = cur[label_col].astype(str).value_counts() if label_col in cur else pd.Series(dtype=int)
        if len(counts) < 2 or counts.min() < 3:
            row["skipped_reason"] = "need at least 2 classes and 3 samples per class"
            rows.append(row)
            continue
        x = pd.to_numeric(cur[col], errors="coerce")
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


def build_redundancy(matrix):
    meta = {"sample_id", "group", "distance", "rpm", "file_id", "channel", "aggregated_channel", "qc_flag"}
    cols = [c for c in matrix.columns if c not in meta]
    corr = matrix[cols].corr(method="spearman")
    rows = []
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            val = corr.loc[a, b]
            if pd.notna(val) and abs(val) > 0.9:
                rows.append({
                    "feature_a": a, "feature_b": b, "spearman_corr": float(val),
                    "redundant_flag": True, "suggested_keep": suggest_keep(a, b),
                    "notes": "high absolute correlation; do not auto-delete",
                })
    return corr, pd.DataFrame(rows)


def compare_existing(sep):
    tf_path = Path("analysis_out/time_frequency_feature_comparison_v1/combined_feature_separability_summary.csv")
    acf_path = Path("analysis_out/acf_features_v1/acf_feature_separability_summary_v1.csv")
    cc_path = Path("analysis_out/channel_correlation_features_v1/channel_correlation_feature_separability_summary_v1.csv")
    if not tf_path.exists() or not acf_path.exists() or not cc_path.exists():
        return pd.DataFrame([{"skipped_reason": "one or more existing comparison files were not found"}])
    tf = pd.read_csv(tf_path)
    acf = pd.read_csv(acf_path)
    cc = pd.read_csv(cc_path)
    tf = tf[(tf.get("sample_grain") == "file_agg") & tf["single_feature_auc_or_macro_auc"].notna()]
    acf = acf[(acf.get("sample_grain") == "file_agg") & acf["single_feature_auc_or_macro_auc"].notna()]
    cc = cc[cc["single_feature_auc_or_macro_auc"].notna()]
    cur = sep[(sep["sample_grain"] == "file_agg") & sep["single_feature_auc_or_macro_auc"].notna()]
    rows = []
    for task in sorted(set(cur["task_name"]) | set(tf["task_name"]) | set(acf["task_name"]) | set(cc["task_name"])):
        freq = top_domain(tf, task, "frequency")
        time = top_domain(tf, task, "time")
        acf_top = top_task(acf, task)
        cc_top = top_task(cc, task)
        tf_top = top_task(cur, task)
        best_tf = best_auc(tf_top)
        best_existing = np.nanmax([best_auc(freq), best_auc(time), best_auc(acf_top), best_auc(cc_top)])
        value = "high" if pd.notna(best_tf) and best_tf >= 0.75 and best_tf >= best_existing - 0.03 else "medium" if pd.notna(best_tf) and best_tf >= 0.75 else "low"
        rows.append({
            "task_name": task,
            "best_frequency_auc": best_auc(freq),
            "best_time_auc": best_auc(time),
            "best_acf_auc": best_auc(acf_top),
            "best_channel_corr_auc": best_auc(cc_top),
            "best_tf_auc": best_tf,
            "best_frequency_feature": best_feature(freq),
            "best_time_feature": best_feature(time),
            "best_acf_feature": best_feature(acf_top),
            "best_channel_corr_feature": best_feature(cc_top),
            "best_tf_feature": best_tf_feature(tf_top),
            "tf_additional_value": value,
            "reason": "compared by top file-level/file-agg single-feature AUC; TF is auxiliary evidence, not final ML",
        })
    return pd.DataFrame(rows)


def assign_roles(sep, redundancy):
    best = sep[sep["single_feature_auc_or_macro_auc"].notna()].sort_values("single_feature_auc_or_macro_auc", ascending=False)
    red = set(redundancy.get("feature_b", pd.Series(dtype=str)).astype(str).tolist())
    rows = []
    pairs = sorted(set(zip(sep["band_id"], sep["feature_name"])))
    for band_id, feature_name in pairs:
        cur = best[(best["band_id"] == band_id) & (best["feature_name"] == feature_name)]
        auc = float(cur["single_feature_auc_or_macro_auc"].iloc[0]) if not cur.empty else np.nan
        effect = float(cur["effect_size"].iloc[0]) if not cur.empty and pd.notna(cur["effect_size"].iloc[0]) else np.nan
        task = cur["task_name"].iloc[0] if not cur.empty else ""
        full = f"{band_id}__{feature_name}"
        burst = int(feature_name in {"tf_time_concentration_score", "tf_burstiness_score", "tf_bandpower_occupancy_ratio", "tf_longest_high_bandpower_duration", "tf_high_bandpower_event_count"})
        bg_risk = int(feature_name in BACKGROUND_FEATURES)
        qc = int(feature_name in {"tf_burstiness_score", "tf_time_concentration_score", "tf_time_entropy", "tf_bandpower_cv", "tf_bandpower_std", "tf_bandpower_range"})
        redundant = "high" if full in red else "low"
        if pd.isna(auc):
            role = "reject"
        elif qc or burst:
            role = "qc_only" if auc < 0.8 or burst else "auxiliary_candidate"
        elif auc >= 0.9 and feature_name in {"tf_bandpower_median", "tf_bandpower_mean", "tf_peak_persistence_ratio", "tf_background_relative_median_gain"}:
            role = "primary_candidate"
        elif auc >= 0.75:
            role = "auxiliary_candidate"
        else:
            role = "reject"
        rows.append({
            "band_id": band_id, "feature_name": feature_name, "feature_type": stability_feature_type(feature_name),
            "best_task": task, "best_auc": auc, "best_effect_size": effect, "redundancy_level": redundant,
            "burstiness_risk_flag": burst, "background_threshold_risk_flag": bg_risk, "qc_role_flag": qc,
            "recommended_role": role,
            "reason": role_reason(role, feature_name, auc, burst, bg_risk, redundant),
        })
    return pd.DataFrame(rows)


def recommended_sets(roles):
    roles = roles.copy()
    roles["full"] = roles["band_id"].astype(str) + "__" + roles["feature_name"].astype(str)
    return {
        "tf_auxiliary": roles[roles["recommended_role"].isin(["primary_candidate", "auxiliary_candidate"])]["full"].tolist(),
        "tf_qc_features": roles[roles["recommended_role"] == "qc_only"]["full"].tolist(),
        "tf_rejected": roles[roles["recommended_role"] == "reject"]["full"].tolist(),
        "tf_burstiness_risk_features": roles[roles["burstiness_risk_flag"] == 1]["full"].tolist(),
    }


def write_combined_recommendations(out, roles):
    base_paths = [
        Path("analysis_out/channel_correlation_features_v1/recommended_feature_sets_with_channel_corr_v1.json"),
        Path("analysis_out/acf_features_v1/recommended_feature_sets_with_acf_v1.json"),
        Path("analysis_out/time_frequency_feature_comparison_v1/recommended_feature_sets_v1.json"),
    ]
    base = {}
    for path in base_paths:
        if path.exists():
            base = read_json(path)
            break
    if not base:
        return
    rec = recommended_sets(roles)
    merged = dict(base)
    merged["tf_auxiliary"] = rec["tf_auxiliary"]
    merged["combined_nonredundant_with_tf"] = unique_list(
        base.get("combined_nonredundant_with_channel_corr", [])
        + base.get("combined_nonredundant_with_acf", [])
        + base.get("combined_nonredundant", [])
        + rec["tf_auxiliary"][:30]
    )
    merged["qc_features"] = unique_list(base.get("qc_features", []) + rec["tf_qc_features"])
    merged["excluded_baseline_risk"] = base.get("excluded_baseline_risk", [])
    write_json(out / "recommended_feature_sets_with_tf_v1.json", merged)


def plot_top_auc(sep, path):
    data = sep[(sep["sample_grain"] == "file_agg") & sep["single_feature_auc_or_macro_auc"].notna()].copy()
    if data.empty:
        return
    top = data.sort_values("single_feature_auc_or_macro_auc", ascending=False).groupby("task_name").head(1)
    labels = top["task_name"].str.replace("Task ", "T", regex=False)
    plt.figure(figsize=(9, 4))
    plt.bar(labels, top["single_feature_auc_or_macro_auc"], color="#4c78a8")
    plt.ylim(0, 1.05)
    plt.ylabel("top single-feature AUC")
    plt.title("Top TF Stability Feature AUC by Task")
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def plot_group_heatmap(features, sep, path):
    top = sep[(sep["sample_grain"] == "file_agg") & sep["single_feature_auc_or_macro_auc"].notna()].sort_values("single_feature_auc_or_macro_auc", ascending=False)
    top_cols = (top["band_id"] + "__" + top["feature_name"]).drop_duplicates().head(20).tolist()
    data = features.copy()
    data["full"] = data["band_id"].astype(str) + "__" + data["feature_name"].astype(str)
    data = data[data["full"].isin(top_cols)]
    if data.empty:
        return
    pivot = data.groupby(["group", "full"])["feature_value"].median().unstack()
    plt.figure(figsize=(12, 5))
    plt.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap="viridis")
    plt.colorbar(label="group median")
    plt.yticks(range(len(pivot.index)), pivot.index)
    plt.xticks(range(len(pivot.columns)), pivot.columns, rotation=75, ha="right", fontsize=7)
    plt.title("Top TF Stability Features: Group Median Heatmap")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def write_report(out, features, summary, sep, roles, comparison, audit, run_config):
    report = Path("docs/TIME_FREQUENCY_STABILITY_FEATURE_ANALYSIS_V1.md")
    report.parent.mkdir(parents=True, exist_ok=True)
    groups = sorted(features["group"].unique().tolist())
    top = sep[(sep["sample_grain"] == "file_agg") & sep["single_feature_auc_or_macro_auc"].notna()].sort_values("single_feature_auc_or_macro_auc", ascending=False).head(12)
    role_counts = roles["recommended_role"].value_counts().to_dict()
    stable_candidates = roles[roles["recommended_role"].isin(["primary_candidate", "auxiliary_candidate"])].head(30)
    burst = roles[roles["burstiness_risk_flag"] == 1].head(30)
    lines = [
        "# Time-Frequency Stability Feature Analysis v1",
        "",
        "## Purpose",
        "",
        "PSD summarizes whole-file spectral strength. Time-frequency stability checks whether candidate bands or peak windows persist across time windows or are driven by short bursts.",
        "",
        "## Inputs",
        "",
        f"- Time CSV root: `{audit.get('time_root', 'UNKNOWN')}`",
        f"- Groups read: {', '.join(groups)}",
        "",
        "## Rolling FFT / Bandpower Method",
        "",
        f"- window_sec: `{run_config.get('window_sec')}`",
        f"- overlap: `{run_config.get('overlap')}`",
        "- window_function: `hann`",
        "- n_fft: derived per file from `round(sampling_rate_hz * window_sec)`",
        "- frequency resolution: `sampling_rate_hz / n_fft`",
        "- bandpower formula: `10*log10(sum(periodogram_power_density * df_hz) + EPS)`",
        "- preprocessing: per-window mean removal; no full FFT pipeline was rerun.",
        "",
        "## Outputs and Coverage",
        "",
        f"- File/channel/band feature rows: {len(features)}",
        f"- Stability summary rows: {len(summary)}",
        f"- Feature roles: {role_counts}",
        "",
        "## Top File-Aggregated Separability Results",
        "",
    ]
    for _, row in top.iterrows():
        lines.append(f"- `{row['band_id']}__{row['feature_name']}` `{row['task_name']}`: AUC={row['single_feature_auc_or_macro_auc']:.3g}, effect={row['effect_size']:.3g}")
    lines += [
        "",
        "## Stable vs Burst-Like Interpretation",
        "",
        "Features based on rolling bandpower median/mean and peak persistence are treated as evidence for persistence across windows. Burstiness, time concentration, occupancy, and high-event count features are treated as burst/risk or QC signals unless supported by stable median behavior.",
        "",
        "### Candidate TF Auxiliary Features",
        "",
        ", ".join((stable_candidates["band_id"] + "__" + stable_candidates["feature_name"]).tolist()) or "None",
        "",
        "### Burstiness / Short-Window Risk Features",
        "",
        ", ".join((burst["band_id"] + "__" + burst["feature_name"]).tolist()) or "None",
        "",
        "## Comparison with Existing Feature Families",
        "",
    ]
    for _, row in comparison.iterrows():
        if "skipped_reason" in row and pd.notna(row.get("skipped_reason")):
            lines.append(f"- skipped: {row['skipped_reason']}")
        else:
            lines.append(f"- `{row['task_name']}`: best_tf_auc={row['best_tf_auc']:.3g}, additional_value={row['tf_additional_value']}, best_tf={row['best_tf_feature']}")
    lines += [
        "",
        "## Role Guidance",
        "",
        "- TF stability features are auxiliary evidence for PSD candidate stability, not a replacement for PSD/bandpower as the main line.",
        "- Background-relative features use same-distance 0Hz window bandpower p95/median and are marked with background-threshold risk.",
        "- Burst-like features should not be interpreted as stable target features without follow-up inspection.",
        "",
        "## Scope Guard",
        "",
        "- No machine learning was run.",
        "- No full FFT pipeline was rerun.",
        "- No background contrast formula was modified.",
        "- No complete STFT matrix or per-file spectrograms were exported.",
        "- No channel or file was automatically deleted.",
        "- High TF AUC is not interpreted as a physical mechanism or final recognition result.",
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_schema():
    return {
        "common_keys": ["group", "distance", "rpm", "file_id", "channel"],
        "window_features": WINDOW_FEATURES,
        "stability_features": BASE_STABILITY_FEATURES + BACKGROUND_FEATURES,
        "bands": [{"band_id": b, "freq_low_hz": l, "freq_high_hz": h} for b, l, h in BANDS],
        "feature_domain": "time_frequency_stability",
        "units": {name: stability_unit(name) for name in BASE_STABILITY_FEATURES + BACKGROUND_FEATURES},
        "can_enter_later_separability": True,
    }


def sampling_info(time):
    if len(time) < 2:
        return np.nan, np.nan, ["too_short"]
    diffs = np.diff(time)
    med = float(np.nanmedian(diffs))
    if not np.isfinite(med) or med <= 0:
        return np.nan, np.nan, ["invalid_sampling_rate"]
    sr = 1.0 / med
    duration = float(time[-1] - time[0])
    qc = []
    if np.nanstd(diffs) > max(abs(med) * 1e-3, 1e-12):
        qc.append("sampling_rate_jitter")
    return float(sr), duration, qc


def parse_group(group):
    m = re.fullmatch(r"(\d+)m(\d+)hz", group.lower())
    if not m:
        return None
    return {"distance": f"{m.group(1)}m", "rpm": f"{m.group(2)}Hz"}


def base_file_audit(path, channels, missing, sr, duration, n_windows, qc):
    return {
        "file": str(path),
        "channels": channels,
        "missing_channels": missing,
        "sampling_rate_hz": sr,
        "duration_seconds": duration,
        "n_windows": n_windows,
        "qc_flag": join_qc(qc),
    }


def longest_true_run(flags):
    best = cur = 0
    for flag in flags:
        if bool(flag):
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def count_true_events(flags):
    count = 0
    prev = False
    for flag in flags:
        cur = bool(flag)
        if cur and not prev:
            count += 1
        prev = cur
    return count


def top_fraction_share(values, frac):
    power = np.power(10.0, np.asarray(values, dtype=float) / 10.0)
    power = np.maximum(power, 0)
    if len(power) == 0 or np.nansum(power) <= 0:
        return np.nan
    n = max(1, int(math.ceil(len(power) * frac)))
    return float(np.nansum(np.sort(power)[-n:]) / (np.nansum(power) + EPS))


def entropy_from_db(values):
    power = np.power(10.0, np.asarray(values, dtype=float) / 10.0)
    power = np.maximum(power, 0)
    p = power / (np.nansum(power) + EPS)
    return -float(np.nansum(p * np.log(p + EPS)) / np.log(len(p))) if len(p) else np.nan


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
    labs = sorted(y.unique())
    if len(labs) < 2:
        return np.nan
    vals = []
    for lab in labs:
        yy = (y == lab).astype(int)
        try:
            auc = roc_auc_score(yy, x)
            vals.append(max(auc, 1.0 - auc))
        except Exception:
            pass
    return float(np.mean(vals)) if vals else np.nan


def window_feature_type(name):
    if "peak" in name:
        return "window_peak"
    if "bandpower" in name or "median" in name:
        return "window_bandpower"
    return "window_tf"


def stability_feature_type(name):
    if name in BACKGROUND_FEATURES:
        return "background_relative"
    if "peak_freq" in name:
        return "peak_frequency_stability"
    if "peak" in name:
        return "peak_persistence"
    if "entropy" in name or "concentration" in name or "burst" in name:
        return "time_concentration"
    if "occupancy" in name or "event" in name or "duration" in name or "stability" in name:
        return "temporal_persistence"
    return "rolling_bandpower"


def window_unit(name):
    if name.endswith("_hz"):
        return "Hz"
    if name.endswith("_db") or "prominence" in name:
        return "dB"
    return "unitless"


def stability_unit(name):
    if name.endswith("_hz") or "jitter" in name:
        return "Hz"
    if "duration" in name:
        return "s"
    if "count" in name:
        return "count"
    if "ratio" in name or "entropy" in name or "score" in name:
        return "unitless"
    if "gain" in name or "margin" in name or "bandpower" in name or "peak_value" in name or "prominence" in name:
        return "dB"
    return "unitless"


def window_note(name):
    if name == "window_peak_prominence_like":
        return "peak_value_db minus median band-bin dB within the same window and band"
    if name == "window_bandpower_db":
        return "periodogram bandpower integrated over the band and converted to dB"
    return ""


def stability_note(name):
    if name == "tf_bandpower_stability_ratio":
        return "fraction of windows within file median +/- 3*MAD-derived robust sigma"
    if name == "tf_bandpower_occupancy_ratio":
        return "within-file occupancy: fraction of windows above file median + IQR"
    if name == "tf_peak_persistence_ratio":
        return "fraction of windows with peak prominence > 3 dB"
    if name == "tf_peak_freq_stability_ratio":
        return "fraction of windows whose peak frequency is near band center within min(500 Hz, 25% band width)"
    if name == "tf_time_concentration_score":
        return "top 10% window linear power share; high value means time-concentrated energy"
    if name == "tf_time_entropy":
        return "entropy of window linear bandpower distribution"
    if name == "tf_burstiness_score":
        return "(p90 - median) / abs(median) on window bandpower dB values"
    return ""


def burst_warning(name):
    return "burstiness risk" if name in {"tf_time_concentration_score", "tf_burstiness_score", "tf_bandpower_occupancy_ratio", "tf_longest_high_bandpower_duration", "tf_high_bandpower_event_count"} else ""


def feature_priority(name):
    order = {
        "tf_bandpower_median": 0,
        "tf_bandpower_mean": 1,
        "tf_peak_persistence_ratio": 2,
        "tf_background_relative_median_gain": 3,
    }
    return order.get(name.split("__")[-1], 10)


def suggest_keep(a, b):
    return a if feature_priority(a) <= feature_priority(b) else b


def role_reason(role, feature, auc, burst, bg_risk, redundant):
    parts = [f"best_auc={auc:.3g}" if pd.notna(auc) else "no usable AUC"]
    if burst:
        parts.append("burstiness/short-window risk")
    if bg_risk:
        parts.append("uses background threshold")
    if redundant == "high":
        parts.append("high redundancy")
    parts.append(f"assigned {role}")
    return "; ".join(parts)


def top_domain(df, task, domain):
    cur = df[(df["task_name"] == task) & (df.get("feature_domain") == domain)]
    return cur.sort_values("single_feature_auc_or_macro_auc", ascending=False)


def top_task(df, task):
    return df[df["task_name"] == task].sort_values("single_feature_auc_or_macro_auc", ascending=False)


def best_auc(df):
    if df is None or df.empty:
        return np.nan
    return float(df["single_feature_auc_or_macro_auc"].iloc[0])


def best_feature(df):
    if df is None or df.empty:
        return ""
    if "feature_name" in df.columns:
        return str(df["feature_name"].iloc[0])
    return ""


def best_tf_feature(df):
    if df is None or df.empty:
        return ""
    return f"{df['band_id'].iloc[0]}__{df['feature_name'].iloc[0]}"


def join_qc(qc):
    vals = sorted({str(x) for x in qc if str(x) and str(x) != "OK"})
    return ";".join(vals) if vals else "OK"


def join_qc_series(values):
    vals = sorted({str(x) for x in values if str(x) and str(x) != "OK"})
    return ";".join(vals) if vals else "OK"


def unique_list(values):
    seen = set()
    out = []
    for value in values:
        if value not in seen:
            out.append(value)
            seen.add(value)
    return out


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else {}


if __name__ == "__main__":
    main()
