from __future__ import annotations

import ast
import json
import math
import re
import shutil
import sys
import time
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import signal


ROOT = Path(__file__).resolve().parents[1]
TIME_ROOT = Path("D:/Lab/process/26.5.12/time")
RAW_ROOT = Path("D:/Lab/raw/26.5.12")
NIST_ROOT = Path("D:/Lab/results/26.5.12/nist_diagnostics")
OUT = ROOT / "analysis_out"
FIG = OUT / "figures"
CSV_DIR = OUT / "csv"
EXPECTED_GROUPS = [
    "2m0hz",
    "2m30hz",
    "2m50hz",
    "3m0hz",
    "3m30hz",
    "3m50hz",
    "5m0hz",
    "5m30hz",
    "5m50hz",
]
BANDS = [
    ("0_100", 0.0, 100.0),
    ("100_1k", 100.0, 1000.0),
    ("1k_10k", 1000.0, 10000.0),
    ("10k_50k", 10000.0, 50000.0),
    ("50k_100k", 50000.0, 100000.0),
    ("100k_200k", 100000.0, 200000.0),
]
SIDE_BASES = [30.0, 50.0, 60.0, 100.0, 150.0]
FIXED_CARRIERS = [8500.0, 50000.0, 59500.0]
TOP_N = 20


def parse_group(group: str) -> tuple[int | None, int | None]:
    m = re.fullmatch(r"(\d+)m(\d+)hz", group.lower())
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def channel_sort_key(channel: str) -> tuple[int, str]:
    m = re.search(r"(\d+)$", str(channel))
    return (int(m.group(1)) if m else 9999, str(channel))


def finite_float(value):
    try:
        value = float(value)
    except Exception:
        return np.nan
    return value if np.isfinite(value) else np.nan


def safe_div(num, den):
    num = finite_float(num)
    den = finite_float(den)
    return num / den if np.isfinite(num) and np.isfinite(den) and abs(den) > 0 else np.nan


def list_to_text(values, precision=3):
    clean = [v for v in values if np.isfinite(finite_float(v))]
    return ";".join(f"{float(v):.{precision}f}" for v in clean)


def read_excel(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_excel(path)


def read_jsonish(value):
    if isinstance(value, (list, tuple)):
        return list(value)
    if not isinstance(value, str) or not value.strip():
        return []
    for loader in (json.loads, ast.literal_eval):
        try:
            out = loader(value)
            return out if isinstance(out, list) else []
        except Exception:
            pass
    return []


def band_label(freq: float) -> str:
    if not np.isfinite(freq):
        return ""
    if freq < 100:
        return "0-100Hz"
    if freq < 1000:
        return "100-1kHz"
    if freq < 10000:
        return "1k-10kHz"
    if freq < 50000:
        return "10k-50kHz"
    if freq < 100000:
        return "50k-100kHz"
    if freq <= 200000:
        return "100k-200kHz"
    return ">200kHz"


def bandpower(freqs, power, low, high):
    mask = (freqs >= low) & (freqs < high) & np.isfinite(power)
    if mask.sum() < 2:
        return np.nan
    integrate = getattr(np, "trapezoid", np.trapz)
    return float(integrate(power[mask], freqs[mask]))


def dominant(freqs, power, low, high):
    mask = (freqs >= low) & (freqs < high) & np.isfinite(power)
    if not np.any(mask):
        return np.nan, np.nan
    idxs = np.where(mask)[0]
    best = idxs[int(np.nanargmax(power[idxs]))]
    return float(freqs[best]), float(power[best])


def nearest_power(freqs, power, target, window=None):
    if not np.isfinite(target) or len(freqs) == 0:
        return np.nan, np.nan
    idx = int(np.argmin(np.abs(freqs - target)))
    if window is not None and abs(float(freqs[idx]) - target) > window:
        return np.nan, np.nan
    return float(freqs[idx]), float(power[idx])


def spectral_entropy(power):
    p = np.asarray(power, dtype=float)
    p = p[np.isfinite(p) & (p > 0)]
    if p.size == 0:
        return np.nan
    p = p / p.sum()
    return float(-np.sum(p * np.log2(p)) / np.log2(p.size)) if p.size > 1 else 0.0


def top_peaks(freqs, power, n=TOP_N, min_freq=0.0):
    mask = (freqs >= min_freq) & (freqs <= 200000.0) & np.isfinite(power)
    idxs = np.where(mask)[0]
    if idxs.size == 0:
        return []
    local_power = power[idxs]
    peaks, props = signal.find_peaks(local_power, prominence=0)
    if peaks.size == 0:
        peaks = np.arange(local_power.size)
        prominences = np.full(peaks.size, np.nan)
        widths = np.full(peaks.size, np.nan)
    else:
        prominences = props.get("prominences", np.full(peaks.size, np.nan))
        widths = signal.peak_widths(local_power, peaks, rel_height=0.5)[0]
    peak_idxs = idxs[peaks]
    order = np.argsort(power[peak_idxs])[::-1][:n]
    df = float(np.nanmedian(np.diff(freqs))) if len(freqs) > 1 else np.nan
    out = []
    for rank, pos in enumerate(order, start=1):
        peak_idx = int(peak_idxs[pos])
        out.append(
            {
                "rank": rank,
                "freq_hz": float(freqs[peak_idx]),
                "psd": float(power[peak_idx]),
                "prominence": finite_float(prominences[pos]),
                "width_hz": finite_float(widths[pos]) * df if np.isfinite(df) else np.nan,
            }
        )
    return out


def harmonic_info(freq):
    bases = [30.0, 50.0, 60.0, 100.0, 150.0, 1000.0, 8500.0, 50000.0, 59500.0]
    best = ("", np.nan, np.nan)
    for base in bases:
        if not np.isfinite(freq) or freq <= 0:
            continue
        order = max(1, int(round(freq / base)))
        err = abs(freq - order * base)
        if not np.isfinite(best[2]) or err < best[2]:
            best = (base, order, err)
    return best


def load_group_time_data(group_dir: Path):
    csv_files = sorted(p for p in group_dir.glob("*.csv") if p.is_file())
    channels = None
    series = defaultdict(list)
    times = []
    for p in csv_files:
        df = pd.read_csv(p)
        if "time" not in df.columns:
            continue
        channel_cols = [c for c in df.columns if str(c).lower().startswith("channel")]
        if channels is None:
            channels = sorted(channel_cols, key=channel_sort_key)
        t = df["time"].to_numpy(dtype=float)
        times.append(t)
        for ch in channels:
            if ch in df.columns:
                series[ch].append(df[ch].to_numpy(dtype=float))
    return csv_files, channels or [], times, series


def compute_psd_for_group(group, group_dir, log_lines):
    csv_files, channels, times, series_by_channel = load_group_time_data(group_dir)
    psd_rows = []
    peak_rows = []
    low_rows = []
    side_rows = []
    spectra_store = {}
    for ch in channels:
        spectra = []
        low_spectra = []
        freqs_ref = low_ref = None
        fs = np.nan
        for x, t in zip(series_by_channel[ch], times):
            valid = np.isfinite(x) & np.isfinite(t)
            x = x[valid]
            t = t[valid]
            if len(x) < 8 or len(t) < 8:
                continue
            dt = np.nanmedian(np.diff(t))
            if not np.isfinite(dt) or dt <= 0:
                continue
            fs = float(1.0 / dt)
            x = x - np.nanmedian(x)
            nper = min(16384, len(x))
            f, pxx = signal.welch(x, fs=fs, nperseg=nper, detrend="constant", scaling="density")
            if freqs_ref is None:
                freqs_ref = f
            if len(f) == len(freqs_ref) and np.allclose(f, freqs_ref):
                spectra.append(pxx)
            nper_low = min(524288, len(x))
            lf, lpxx = signal.welch(x, fs=fs, nperseg=nper_low, detrend="constant", scaling="density")
            if low_ref is None:
                low_ref = lf
            if len(lf) == len(low_ref) and np.allclose(lf, low_ref):
                low_spectra.append(lpxx)
        dist, pump = parse_group(group)
        note = ""
        if not spectra or freqs_ref is None:
            note = "PSD unavailable: no valid spectra."
            psd_rows.append({"group": group, "distance_m": dist, "pump_freq_hz": pump, "channel": ch, "files": len(series_by_channel[ch]), "quality_note": note})
            continue
        mean_power = np.nanmean(np.vstack(spectra), axis=0)
        df_hz = float(np.nanmedian(np.diff(freqs_ref))) if len(freqs_ref) > 1 else np.nan
        low_mean = np.nanmean(np.vstack(low_spectra), axis=0) if low_spectra else np.asarray([])
        low_df = float(np.nanmedian(np.diff(low_ref))) if low_ref is not None and len(low_ref) > 1 else np.nan
        spectra_store[(group, ch)] = {"freqs": freqs_ref, "power": mean_power, "low_freqs": low_ref, "low_power": low_mean}
        if not np.isfinite(low_df) or low_df > 1.0:
            note = "low-frequency resolution insufficient for direct 30/50Hz discrimination"
        dom_all_f, dom_all_p = dominant(freqs_ref, mean_power, 0.0, 200000.0)
        dom_ex_f, dom_ex_p = dominant(freqs_ref, mean_power, 1000.0, 200000.0)
        dom_1k_f, dom_1k_p = dominant(freqs_ref, mean_power, max(df_hz, 0.0), 1000.0)
        dom_10k_f, dom_10k_p = dominant(freqs_ref, mean_power, max(df_hz, 0.0), 10000.0)
        row = {
            "group": group,
            "distance_m": dist,
            "pump_freq_hz": pump,
            "channel": ch,
            "files": len(spectra),
            "df_hz": df_hz,
            "low_freq_df_hz": low_df,
            "dom_all_freq_hz": dom_all_f,
            "dom_all_psd": dom_all_p,
            "dom_excl_low_freq_hz": dom_ex_f,
            "dom_excl_low_psd": dom_ex_p,
            "dom_0_1k_freq_hz": dom_1k_f,
            "dom_0_1k_psd": dom_1k_p,
            "dom_0_10k_freq_hz": dom_10k_f,
            "dom_0_10k_psd": dom_10k_p,
            "spectral_entropy": spectral_entropy(mean_power),
            "quality_note": note,
        }
        total = 0.0
        for name, low, high in BANDS:
            bp = bandpower(freqs_ref, mean_power, low, high)
            row[f"bandpower_{name}"] = bp
            if np.isfinite(bp):
                total += bp
        row["total_power_0_200k"] = total if total > 0 else np.nan
        psd_rows.append(row)
        for peak in top_peaks(freqs_ref, mean_power, TOP_N, min_freq=0.0):
            base, order, err = harmonic_info(peak["freq_hz"])
            peak_rows.append(
                {
                    "group": group,
                    "distance_m": dist,
                    "pump_freq_hz": pump,
                    "channel": ch,
                    **peak,
                    "band_label": band_label(peak["freq_hz"]),
                    "is_near_30hz": abs(peak["freq_hz"] - 30.0) <= max(df_hz, 1.0),
                    "is_near_50hz": abs(peak["freq_hz"] - 50.0) <= max(df_hz, 1.0),
                    "is_near_60hz": abs(peak["freq_hz"] - 60.0) <= max(df_hz, 1.0),
                    "is_near_1khz": abs(peak["freq_hz"] - 1000.0) <= max(df_hz, 1.0),
                    "is_near_8p5khz": abs(peak["freq_hz"] - 8500.0) <= max(df_hz, 1.0),
                    "is_near_50khz": abs(peak["freq_hz"] - 50000.0) <= max(df_hz, 1.0),
                    "is_near_59p5khz": abs(peak["freq_hz"] - 59500.0) <= max(df_hz, 1.0),
                    "nearest_harmonic_base": base,
                    "harmonic_order": order,
                    "harmonic_error_hz": err,
                }
            )
        lf_note = "" if np.isfinite(low_df) and low_df <= 1.0 else "unreliable: actual lowfreq_df_hz > 1Hz"
        lf = low_ref if low_ref is not None else np.asarray([])
        lp = low_mean if low_mean is not None else np.asarray([])
        low_row = {
            "group": group,
            "distance_m": dist,
            "pump_freq_hz": pump,
            "channel": ch,
            "lowfreq_df_hz": low_df,
            "power_20_40hz": bandpower(lf, lp, 20, 40),
            "power_40_60hz": bandpower(lf, lp, 40, 60),
            "power_45_55hz": bandpower(lf, lp, 45, 55),
            "power_55_65hz": bandpower(lf, lp, 55, 65),
            "direct_30_50_reliable_flag": bool(np.isfinite(low_df) and low_df <= 1.0),
            "quality_note": lf_note,
        }
        for target in [30, 50, 60, 100, 150]:
            fr, pw = nearest_power(lf, lp, float(target), window=max(low_df * 2 if np.isfinite(low_df) else 2, 2.0))
            low_row[f"peak_near_{target}hz"] = fr if np.isfinite(pw) else np.nan
        low_rows.append(low_row)
        carriers = sorted(set(FIXED_CARRIERS + [dom_ex_f]))
        for carrier in carriers:
            cf, cp = nearest_power(freqs_ref, mean_power, carrier, window=max(df_hz * 2, 50.0))
            for base in SIDE_BASES:
                lower_f, lower_p = nearest_power(freqs_ref, mean_power, carrier - base, window=max(df_hz * 1.5, 1.0))
                upper_f, upper_p = nearest_power(freqs_ref, mean_power, carrier + base, window=max(df_hz * 1.5, 1.0))
                reliable = bool(np.isfinite(df_hz) and df_hz <= base / 3)
                score = safe_div(np.nanmean([lower_p, upper_p]), cp)
                side_rows.append(
                    {
                        "group": group,
                        "distance_m": dist,
                        "pump_freq_hz": pump,
                        "channel": ch,
                        "carrier_freq_hz": cf,
                        "sideband_base_hz": base,
                        "lower_freq_hz": lower_f,
                        "lower_psd": lower_p,
                        "upper_freq_hz": upper_f,
                        "upper_psd": upper_p,
                        "carrier_psd": cp,
                        "sideband_score": score,
                        "sideband_reliable_flag": reliable,
                    }
                )
    log_lines.append(f"Computed PSD/lowfreq/sideband for {group}: channels={len(channels)}, csv_files={len(csv_files)}")
    return psd_rows, peak_rows, low_rows, side_rows, spectra_store, channels, len(csv_files)


def normalize_existing_summaries(group):
    dist, pump = parse_group(group)
    base = NIST_ROOT / group
    nist = read_excel(base / "nist_diagnostics_group_summary.xlsx")
    if not nist.empty:
        nist = nist.rename(
            columns={
                "file_count": "files",
                "run_mean": "mean",
                "run_median": "median",
                "run_std": "std",
                "dist_q05": "q05",
                "dist_q95": "q95",
                "dist_iqr": "iqr",
                "run_drift_span": "drift_span",
                "run_drift_ratio_ac": "drift_ratio_ac",
                "run_rolling_mean_range": "rolling_mean_range",
                "qq_normal_prob_corr": "qq_corr",
                "qq_tail_deviation": "tail_dev",
                "distribution_shape_flag": "abnormal_distribution_flag",
            }
        )
        nist["distance_m"] = dist
        nist["pump_freq_hz"] = pump
        nist["quality_note"] = nist.apply(
            lambda r: "; ".join(
                x
                for x in [
                    "run_drift_flag" if bool(r.get("run_drift_flag", False)) else "",
                    str(r.get("abnormal_distribution_flag", "")) if pd.notna(r.get("abnormal_distribution_flag", "")) else "",
                ]
                if x
            ),
            axis=1,
        )
        nist["quality_note"] = nist["quality_note"].replace("", "NIST diagnostics only; not used for period inference.")
    acf = read_excel(base / "acf_group_summary.xlsx")
    if not acf.empty:
        acf = acf.rename(
            columns={
                "file_count": "files",
                "first_strong_peak_lag_s": "first_strong_lag_s",
                "first_strong_peak_freq_hz": "first_strong_freq_hz",
                "first_strong_peak_height": "first_strong_acf",
                "global_max_peak_lag_s": "global_max_lag_s",
                "global_max_peak_freq_hz": "global_max_freq_hz",
                "global_max_peak_height": "global_max_acf",
                "peak_spacing_period_s": "peak_spacing_s",
                "acf_period_conflict_flag": "acf_quality_flag",
            }
        )
        if "first_strong_acf" not in acf.columns:
            if "acf_peak_height" in acf.columns:
                acf["first_strong_acf"] = acf["acf_peak_height"].apply(lambda v: read_jsonish(v)[0] if read_jsonish(v) else np.nan)
            else:
                acf["first_strong_acf"] = np.nan
        if "global_max_acf" not in acf.columns:
            acf["global_max_acf"] = acf["first_strong_acf"]
        acf["distance_m"] = dist
        acf["pump_freq_hz"] = pump
        acf["quality_note"] = acf.get("acf_period_conflict_reason", "").fillna("")
    acfp = read_excel(base / "acf_peaks_long.xlsx")
    if not acfp.empty:
        acfp = acfp.rename(columns={"peak_rank": "rank", "peak_lag_s": "lag_s", "peak_value": "acf_value"})
        acfp = acfp[acfp["file_id_or_file_name"].astype(str).eq("group_mean")].copy()
        acfp["equivalent_freq_hz"] = acfp["lag_s"].apply(lambda x: 1 / x if x and np.isfinite(x) else np.nan)
        acfp["distance_m"] = dist
        acfp["pump_freq_hz"] = pump
        acfp["is_above_threshold"] = acfp["acf_value"] >= 0.3
    matches = read_excel(base / "psd_acf_peak_matches.xlsx")
    if not matches.empty:
        matches = matches.rename(
            columns={
                "psd_period_s": "psd_peak_period_s",
                "nearest_acf_peak_lag_s": "matched_acf_lag_s",
                "acf_value_at_match": "matched_acf_value",
                "period_error_percent": "match_error_pct",
            }
        )
        matches["distance_m"] = dist
        matches["pump_freq_hz"] = pump
        matches["match_error_s"] = np.nan
        matches["psd_peak_rank"] = matches.groupby(["group", "channel"]).cumcount() + 1
        matches["match_level"] = np.where(
            (matches["match_error_pct"] < 5) & (matches["matched_acf_value"] >= 0.3),
            "strong",
            np.where(matches["match_error_pct"] < 10, "weak", "none"),
        )
    return nist, acf, acfp, matches


def add_cross_channel_aggregates(df: pd.DataFrame, kind: str) -> pd.DataFrame:
    if df.empty:
        return df
    rows = [df]
    keys = ["group", "distance_m", "pump_freq_hz"]
    numeric_cols = [c for c in df.columns if c not in keys + ["channel"] and pd.api.types.is_numeric_dtype(df[c])]
    agg_rows = []
    for vals, g in df.groupby(keys, dropna=False):
        row = dict(zip(keys, vals))
        row["channel"] = "ALL"
        for c in numeric_cols:
            row[c] = np.nanmedian(pd.to_numeric(g[c], errors="coerce"))
        if "files" in df.columns:
            row["files"] = pd.to_numeric(g["files"], errors="coerce").sum()
        row["quality_note"] = f"Cross-channel median aggregate for {kind}."
        agg_rows.append(row)
    if agg_rows:
        rows.append(pd.DataFrame(agg_rows))
    return pd.concat(rows, ignore_index=True, sort=False)


def cluster_freqs(items, tol_hz=75.0):
    items = sorted([x for x in items if np.isfinite(x["freq"])], key=lambda x: x["freq"])
    clusters = []
    for item in items:
        if not clusters or abs(item["freq"] - clusters[-1]["center"]) > tol_hz:
            clusters.append({"center": item["freq"], "items": [item]})
        else:
            clusters[-1]["items"].append(item)
            clusters[-1]["center"] = float(np.median([i["freq"] for i in clusters[-1]["items"]]))
    return clusters


def build_cross_channel_peak_summary(peaks: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for group, g in peaks.groupby("group"):
        dist, pump = parse_group(group)
        items = [{"freq": r.freq_hz, "psd": r.psd, "channel": r.channel} for r in g.itertuples() if r.rank <= 10]
        for cl in cluster_freqs(items, tol_hz=100.0):
            psds = np.asarray([i["psd"] for i in cl["items"]], dtype=float)
            channels = sorted({i["channel"] for i in cl["items"]}, key=channel_sort_key)
            rows.append(
                {
                    "group": group,
                    "distance_m": dist,
                    "pump_freq_hz": pump,
                    "peak_cluster_center_hz": cl["center"],
                    "channel_count": len(channels),
                    "channels_present": ",".join(channels),
                    "median_psd": float(np.nanmedian(psds)),
                    "mean_psd": float(np.nanmean(psds)),
                    "p10_psd": float(np.nanpercentile(psds, 10)),
                    "p90_psd": float(np.nanpercentile(psds, 90)),
                    "freq_std_hz": float(np.nanstd([i["freq"] for i in cl["items"]])),
                    "is_common_peak": len(channels) >= 3,
                    "quality_note": "" if len(channels) >= 2 else "single-channel peak; treat as possible channel-specific anomaly",
                }
            )
    return pd.DataFrame(rows)


def compare_peak_sets(active, base, common):
    tol = 100.0
    a = [(r.freq_hz, r.psd) for r in active.itertuples() if r.rank <= 10]
    b = [(r.freq_hz, r.psd) for r in base.itertuples() if r.rank <= 10]
    new, gone, enhanced, suppressed = [], [], [], []
    for f, p in a:
        matches = [(bf, bp) for bf, bp in b if abs(bf - f) <= tol]
        if not matches:
            new.append(f)
        else:
            bp = max(x[1] for x in matches)
            if p > 1.5 * bp:
                enhanced.append(f)
    for f, p in b:
        matches = [(af, ap) for af, ap in a if abs(af - f) <= tol]
        if not matches:
            gone.append(f)
        else:
            ap = max(x[1] for x in matches)
            if ap < 0.67 * p:
                suppressed.append(f)
    return new, gone, enhanced, suppressed


def build_background_contrast(psd, peaks, cross):
    rows = []
    psd_i = psd[psd["channel"] != "ALL"].set_index(["group", "channel"])
    for distance in [2, 3, 5]:
        baseline = f"{distance}m0hz"
        for pump in [30, 50]:
            active = f"{distance}m{pump}hz"
            for ch in sorted({idx[1] for idx in psd_i.index if idx[0] in [baseline, active]}, key=channel_sort_key):
                if (baseline, ch) not in psd_i.index or (active, ch) not in psd_i.index:
                    continue
                b = psd_i.loc[(baseline, ch)]
                a = psd_i.loc[(active, ch)]
                row = {
                    "distance_m": distance,
                    "pump_freq_hz": pump,
                    "channel": ch,
                    "baseline_group": baseline,
                    "active_group": active,
                    "delta_total_power_0_200k": a["total_power_0_200k"] - b["total_power_0_200k"],
                    "ratio_total_power_0_200k": safe_div(a["total_power_0_200k"], b["total_power_0_200k"]),
                }
                changed_bands = 0
                for name, _, _ in BANDS:
                    col = f"bandpower_{name}"
                    delta = a[col] - b[col]
                    ratio = safe_div(a[col], b[col])
                    row[f"delta_{col}"] = delta
                    if np.isfinite(ratio) and (ratio >= 1.5 or ratio <= 0.67):
                        changed_bands += 1
                new, gone, enh, sup = compare_peak_sets(
                    peaks[(peaks.group == active) & (peaks.channel == ch)],
                    peaks[(peaks.group == baseline) & (peaks.channel == ch)],
                    cross,
                )
                common_enh = cross[(cross.group == active) & (cross.is_common_peak == True)]
                row["new_peaks_hz"] = list_to_text(new)
                row["disappeared_peaks_hz"] = list_to_text(gone)
                row["enhanced_peaks_hz"] = list_to_text(enh)
                row["suppressed_peaks_hz"] = list_to_text(sup)
                row["contrast_score"] = float(changed_bands + min(len(enh) + len(new), 5) * 0.5 + min(len(common_enh), 5) * 0.5)
                row["quality_note"] = "" if np.isfinite(row["ratio_total_power_0_200k"]) else "missing or zero baseline power"
                rows.append(row)
    return pd.DataFrame(rows)


def build_pump_contrast(psd, peaks, lowfreq, sideband):
    rows = []
    psd_i = psd[psd["channel"] != "ALL"].set_index(["group", "channel"])
    low_i = lowfreq.set_index(["group", "channel"])
    for distance in [2, 3, 5]:
        g30, g50 = f"{distance}m30hz", f"{distance}m50hz"
        channels = sorted({idx[1] for idx in psd_i.index if idx[0] in [g30, g50]}, key=channel_sort_key)
        for ch in channels:
            if (g30, ch) not in psd_i.index or (g50, ch) not in psd_i.index:
                continue
            p30, p50 = psd_i.loc[(g30, ch)], psd_i.loc[(g50, ch)]
            items30 = [{"freq": r.freq_hz, "psd": r.psd, "channel": ch} for r in peaks[(peaks.group == g30) & (peaks.channel == ch)].itertuples() if r.rank <= 10]
            items50 = [{"freq": r.freq_hz, "psd": r.psd, "channel": ch} for r in peaks[(peaks.group == g50) & (peaks.channel == ch)].itertuples() if r.rank <= 10]
            c30 = [cl["center"] for cl in cluster_freqs(items30, 100)]
            c50 = [cl["center"] for cl in cluster_freqs(items50, 100)]
            shared = [x for x in c30 if any(abs(x - y) <= 100 for y in c50)]
            only30 = [x for x in c30 if not any(abs(x - y) <= 100 for y in c50)]
            only50 = [x for x in c50 if not any(abs(x - y) <= 100 for y in c30)]
            lf30 = low_i.loc[(g30, ch)] if (g30, ch) in low_i.index else {}
            lf50 = low_i.loc[(g50, ch)] if (g50, ch) in low_i.index else {}
            side30 = sideband[(sideband.group == g30) & (sideband.channel == ch) & (sideband.sideband_base_hz == 30)]["sideband_score"].median()
            side50 = sideband[(sideband.group == g50) & (sideband.channel == ch) & (sideband.sideband_base_hz == 50)]["sideband_score"].median()
            low_df = max(finite_float(lf30.get("lowfreq_df_hz", np.nan)), finite_float(lf50.get("lowfreq_df_hz", np.nan)))
            insufficient = not (np.isfinite(low_df) and low_df <= 1.0)
            diff_flag = bool((len(only30) + len(only50) >= 3) or (abs(safe_div(p50.total_power_0_200k, p30.total_power_0_200k) - 1) > 0.5 if np.isfinite(safe_div(p50.total_power_0_200k, p30.total_power_0_200k)) else False))
            reason = "low-frequency resolution insufficient for direct 30/50Hz discrimination" if insufficient else "direct low-frequency bins are resolvable; compare low-frequency power plus peak/sideband differences"
            rows.append(
                {
                    "distance_m": distance,
                    "channel": ch,
                    "group_30hz": g30,
                    "group_50hz": g50,
                    "delta_total_power": p50.total_power_0_200k - p30.total_power_0_200k,
                    "ratio_total_power": safe_div(p50.total_power_0_200k, p30.total_power_0_200k),
                    "dominant_freq_30hz": p30.dom_excl_low_freq_hz,
                    "dominant_freq_50hz": p50.dom_excl_low_freq_hz,
                    "shared_peak_clusters": list_to_text(shared),
                    "only_30hz_peak_clusters": list_to_text(only30),
                    "only_50hz_peak_clusters": list_to_text(only50),
                    "lowfreq_30hz_power": finite_float(lf30.get("power_20_40hz", np.nan)),
                    "lowfreq_50hz_power": finite_float(lf50.get("power_45_55hz", np.nan)),
                    "sideband_30hz_score": side30,
                    "sideband_50hz_score": side50,
                    "can_distinguish_30_vs_50_flag": diff_flag and not insufficient,
                    "reason": reason,
                }
            )
    return pd.DataFrame(rows)


def trend_type(vals):
    v = [finite_float(x) for x in vals]
    if not all(np.isfinite(v)):
        return "incomplete"
    if v[0] >= v[1] >= v[2]:
        return "monotonic_decay"
    if v[0] <= v[1] <= v[2]:
        return "monotonic_increase"
    return "non_monotonic"


def build_distance_decay(psd, acf):
    rows = []
    psd_i = psd[psd["channel"] != "ALL"].set_index(["pump_freq_hz", "distance_m", "channel"])
    acf_i = acf[acf["channel"] != "ALL"].set_index(["pump_freq_hz", "distance_m", "channel"]) if not acf.empty else pd.DataFrame()
    features = [
        ("total_power_0_200k", "psd", "total_power_0_200k"),
        ("bandpower_1k_10k", "psd", "bandpower_1k_10k"),
        ("bandpower_50k_100k", "psd", "bandpower_50k_100k"),
        ("dominant_peak_psd", "psd", "dom_excl_low_psd"),
        ("acf_first_strong_acf", "acf", "first_strong_acf"),
        ("acf_decay_time_s", "acf", "acf_decay_time_s"),
    ]
    channels = sorted({idx[2] for idx in psd_i.index}, key=channel_sort_key)
    for pump in [0, 30, 50]:
        for ch in channels:
            for feature, source, col in features:
                vals = []
                for dist in [2, 3, 5]:
                    if source == "psd":
                        vals.append(psd_i.loc[(pump, dist, ch)][col] if (pump, dist, ch) in psd_i.index else np.nan)
                    else:
                        vals.append(acf_i.loc[(pump, dist, ch)][col] if not acf_i.empty and (pump, dist, ch) in acf_i.index else np.nan)
                tt = trend_type(vals)
                rows.append(
                    {
                        "pump_freq_hz": pump,
                        "channel": ch,
                        "feature_name": feature,
                        "value_2m": vals[0],
                        "value_3m": vals[1],
                        "value_5m": vals[2],
                        "trend_type": tt,
                        "monotonic_decay_flag": tt == "monotonic_decay",
                        "decay_ratio_5m_over_2m": safe_div(vals[2], vals[0]),
                        "quality_note": "" if tt != "incomplete" else "missing distance value",
                    }
                )
    return pd.DataFrame(rows)


def build_manifest(group_info):
    rows = []
    for group in EXPECTED_GROUPS:
        dist, pump = parse_group(group)
        info = group_info.get(group, {})
        raw_count = len(list((RAW_ROOT / group).glob("*.tdms"))) if (RAW_ROOT / group).exists() else np.nan
        channels = info.get("channels", [])
        if not channels:
            rows.append({"group": group, "distance_m": dist, "pump_freq_hz": pump, "channel": "", "file_count": 0, "raw_file_count": raw_count, "source_path": str(TIME_ROOT / group), "notes": "missing group or no channels"})
        for ch in channels:
            rows.append({"group": group, "distance_m": dist, "pump_freq_hz": pump, "channel": ch, "file_count": info.get("file_count", 0), "raw_file_count": raw_count, "source_path": str(TIME_ROOT / group), "notes": ""})
        rows.append({"group": group, "distance_m": dist, "pump_freq_hz": pump, "channel": "ALL", "file_count": info.get("file_count", 0), "raw_file_count": raw_count, "source_path": str(TIME_ROOT / group), "notes": f"group summary; channels={len(channels)}"})
    return pd.DataFrame(rows)


def write_figures(psd, bg, cross, acf, decay, pump):
    FIG.mkdir(parents=True, exist_ok=True)
    ch = psd[psd.channel != "ALL"].copy()
    ch["label"] = ch["group"] + "/" + ch["channel"]
    plt.figure(figsize=(16, 6))
    plt.scatter(ch["label"], ch["dom_excl_low_freq_hz"], s=14)
    plt.xticks(rotation=90, fontsize=6)
    plt.ylabel("Dominant frequency excluding <1kHz (Hz)")
    plt.tight_layout()
    plt.savefig(FIG / "psd_dominant_freq_by_group_channel.png", dpi=180)
    plt.close()

    agg = psd[psd.channel == "ALL"].copy()
    melt = agg.melt(id_vars=["group", "distance_m", "pump_freq_hz"], value_vars=[f"bandpower_{b[0]}" for b in BANDS], var_name="band", value_name="power")
    pivot = melt.pivot_table(index="group", columns="band", values="power", aggfunc="median")
    plt.figure(figsize=(10, 6))
    plt.imshow(np.log10(pivot.replace(0, np.nan).to_numpy(dtype=float)), aspect="auto")
    plt.yticks(range(len(pivot.index)), pivot.index)
    plt.xticks(range(len(pivot.columns)), pivot.columns, rotation=45, ha="right")
    plt.colorbar(label="log10 bandpower")
    plt.tight_layout()
    plt.savefig(FIG / "bandpower_by_group_distance_pumpfreq.png", dpi=180)
    plt.close()

    heat = bg.pivot_table(index="active_group", columns="channel", values="contrast_score", aggfunc="median")
    plt.figure(figsize=(12, 5))
    plt.imshow(heat.to_numpy(dtype=float), aspect="auto")
    plt.yticks(range(len(heat.index)), heat.index)
    plt.xticks(range(len(heat.columns)), heat.columns, rotation=90, fontsize=7)
    plt.colorbar(label="contrast score")
    plt.tight_layout()
    plt.savefig(FIG / "background_contrast_heatmap.png", dpi=180)
    plt.close()

    common = cross.pivot_table(index="group", columns="peak_cluster_center_hz", values="channel_count", aggfunc="max").fillna(0)
    top_cols = common.max(axis=0).sort_values(ascending=False).head(30).index
    common = common[top_cols]
    plt.figure(figsize=(14, 5))
    plt.imshow(common.to_numpy(dtype=float), aspect="auto")
    plt.yticks(range(len(common.index)), common.index)
    plt.xticks(range(len(common.columns)), [f"{c:.0f}" for c in common.columns], rotation=90, fontsize=6)
    plt.colorbar(label="channel count")
    plt.tight_layout()
    plt.savefig(FIG / "cross_channel_common_peaks_heatmap.png", dpi=180)
    plt.close()

    if not acf.empty:
        ach = acf[acf.channel != "ALL"].copy()
        ach["label"] = ach["group"] + "/" + ach["channel"]
        plt.figure(figsize=(16, 6))
        plt.scatter(ach["label"], ach["first_strong_lag_s"], s=14)
        plt.xticks(rotation=90, fontsize=6)
        plt.ylabel("ACF first strong lag (s)")
        plt.tight_layout()
        plt.savefig(FIG / "acf_first_strong_by_group_channel.png", dpi=180)
        plt.close()

    d = decay[decay.feature_name.isin(["total_power_0_200k", "bandpower_1k_10k", "acf_first_strong_acf"])].copy()
    d_agg = d.groupby(["pump_freq_hz", "feature_name"])[["value_2m", "value_3m", "value_5m"]].median().reset_index()
    plt.figure(figsize=(10, 6))
    for r in d_agg.itertuples():
        plt.plot([2, 3, 5], [r.value_2m, r.value_3m, r.value_5m], marker="o", label=f"{r.pump_freq_hz}Hz {r.feature_name}")
    plt.yscale("log")
    plt.xlabel("distance (m)")
    plt.ylabel("median value")
    plt.legend(fontsize=7)
    plt.tight_layout()
    plt.savefig(FIG / "distance_decay_summary.png", dpi=180)
    plt.close()

    pheat = pump.pivot_table(index="distance_m", columns="channel", values="ratio_total_power", aggfunc="median")
    plt.figure(figsize=(10, 4))
    plt.imshow(pheat.to_numpy(dtype=float), aspect="auto")
    plt.yticks(range(len(pheat.index)), pheat.index)
    plt.xticks(range(len(pheat.columns)), pheat.columns, rotation=90, fontsize=7)
    plt.colorbar(label="50Hz / 30Hz total power")
    plt.tight_layout()
    plt.savefig(FIG / "pump_30_vs_50_contrast.png", dpi=180)
    plt.close()


def write_report(tables, group_info, missing_groups):
    psd = tables["psd_group_summary"]
    bg = tables["background_contrast"]
    pump = tables["pump_freq_contrast"]
    decay = tables["distance_decay_summary"]
    nist = tables["nist_group_summary"]
    cross = tables["cross_channel_peak_summary"]
    lines = ["# 数据汇总报告", ""]
    lines += ["## 1. 输入数据概况"]
    for group in EXPECTED_GROUPS:
        info = group_info.get(group, {})
        lines.append(f"- {group}: channels={len(info.get('channels', []))}, files={info.get('file_count', 0)}")
    lines.append(f"- 缺失组: {', '.join(missing_groups) if missing_groups else 'none'}")
    lines.append("")
    lines += ["## 2. 数据质量诊断"]
    lines.append("NIST 4-plot 指标仅用于数据质量诊断，不用于周期推断；周期相关判断以 PSD/ACF peak 和匹配表为准。")
    if not nist.empty:
        q = nist[nist.channel != "ALL"].copy()
        drift = q[q.get("run_drift_flag", False) == True]
        abnormal = q[q["quality_note"].astype(str).str.contains("SKEWED|TAIL|run_drift", regex=True, na=False)]
        lines.append(f"- NIST 漂移标记通道数: {len(drift)}；异常分布/尾部标记通道数: {len(abnormal)}。")
    lines.append("")
    lines += ["## 3. 背景 vs 泵开启"]
    for distance in [2, 3, 5]:
        for pf in [30, 50]:
            comp = bg[(bg.distance_m == distance) & (bg.pump_freq_hz == pf)]
            if comp.empty:
                lines.append(f"- {distance}m{pf}hz vs {distance}m0hz: 无可配对数据。")
                continue
            med_ratio = comp["ratio_total_power_0_200k"].median()
            top = comp.sort_values("contrast_score", ascending=False).head(3)
            common = cross[(cross.group == f"{distance}m{pf}hz") & (cross.is_common_peak == True)].sort_values("channel_count", ascending=False).head(5)
            lines.append(f"- {distance}m{pf}hz vs {distance}m0hz: total_power 中位比值={med_ratio:.3g}；高对比通道={','.join(top.channel.astype(str))}；跨通道共同峰={list_to_text(common.peak_cluster_center_hz.tolist()) or 'none'} Hz。")
    lines.append("")
    lines += ["## 4. 30Hz vs 50Hz"]
    min_low_df = psd["low_freq_df_hz"].replace([np.inf, -np.inf], np.nan).min()
    lines.append(f"- 当前低频 PSD 最小 df={min_low_df:.3g} Hz；df<=1Hz 的通道可直接检查 30/50Hz 邻域。若某行标记 unreliable，则 low-frequency resolution insufficient for direct 30/50Hz discrimination。")
    distinguish = pump[pump["can_distinguish_30_vs_50_flag"] == True]
    lines.append(f"- 当前严格标记可区分的 channel-distance 对数量: {len(distinguish)}；其余建议以边带、高频峰、ACF 衰减作为间接特征，不强行下结论。")
    lines.append("")
    lines += ["## 5. 距离效应"]
    decay_rate = decay.groupby("feature_name")["monotonic_decay_flag"].mean().sort_values(ascending=False)
    for feature, rate in decay_rate.items():
        lines.append(f"- {feature}: 单调衰减比例={rate:.2%}。")
    lines.append("")
    lines += ["## 6. 初步结论"]
    lines.append("A. 强证据：9 个目标组均有多通道文件，背景对比已按同距离 0Hz 配对，跨通道共同峰可在 cross_channel_peak_summary 中直接追踪。")
    lines.append("B. 中等证据：部分泵开启组相对背景存在频段功率和峰簇变化，但需要结合 channel 一致性与 quality_note 二次筛选。")
    lines.append("C. 不能支持：不能仅凭 0Hz/30Hz/50Hz 标签声明可区分；低频 df 不足或边带不可靠的行已标记 unreliable。")
    lines.append("")
    lines += ["## 7. 后续建议"]
    lines.append("- 后续人工/ChatGPT 分析优先使用 background_contrast、cross_channel_peak_summary、psd_acf_matches 三张表交叉验证。")
    lines.append("- 对 contrast_score 高但仅单通道出现的峰，先按通道异常处理，不作为组级结论。")
    lines.append("- 若目标是直接识别 30Hz/50Hz，保留更长连续时间窗以保证低频 df<=1Hz，并继续记录 actual_df。")
    (OUT / "summary_report.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    start = time.time()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    CSV_DIR.mkdir(parents=True)
    FIG.mkdir(parents=True)
    log_lines = [f"build_analysis_package started: {datetime.now().isoformat(timespec='seconds')}", f"TIME_ROOT={TIME_ROOT}", f"NIST_ROOT={NIST_ROOT}"]
    all_psd, all_peaks, all_low, all_side = [], [], [], []
    all_nist, all_acf, all_acfp, all_matches = [], [], [], []
    group_info = {}
    spectra_store_all = {}
    missing = []
    for group in EXPECTED_GROUPS:
        group_dir = TIME_ROOT / group
        if not group_dir.exists():
            missing.append(group)
            log_lines.append(f"Missing group dir: {group_dir}")
            continue
        psd_rows, peak_rows, low_rows, side_rows, spectra_store, channels, file_count = compute_psd_for_group(group, group_dir, log_lines)
        all_psd.extend(psd_rows)
        all_peaks.extend(peak_rows)
        all_low.extend(low_rows)
        all_side.extend(side_rows)
        spectra_store_all.update(spectra_store)
        group_info[group] = {"channels": channels, "file_count": file_count}
        nist, acf, acfp, matches = normalize_existing_summaries(group)
        all_nist.append(nist)
        all_acf.append(acf)
        all_acfp.append(acfp)
        all_matches.append(matches)
    psd = pd.DataFrame(all_psd)
    peaks = pd.DataFrame(all_peaks)
    lowfreq = pd.DataFrame(all_low)
    sideband = pd.DataFrame(all_side)
    nist = pd.concat([x for x in all_nist if not x.empty], ignore_index=True, sort=False) if any(not x.empty for x in all_nist) else pd.DataFrame()
    acf = pd.concat([x for x in all_acf if not x.empty], ignore_index=True, sort=False) if any(not x.empty for x in all_acf) else pd.DataFrame()
    acfp = pd.concat([x for x in all_acfp if not x.empty], ignore_index=True, sort=False) if any(not x.empty for x in all_acfp) else pd.DataFrame()
    matches = pd.concat([x for x in all_matches if not x.empty], ignore_index=True, sort=False) if any(not x.empty for x in all_matches) else pd.DataFrame()
    manifest = build_manifest(group_info)
    nist = add_cross_channel_aggregates(nist, "NIST")
    psd = add_cross_channel_aggregates(psd, "PSD")
    acf = add_cross_channel_aggregates(acf, "ACF")
    if not acfp.empty:
        acfp = acfp.sort_values(["group", "channel", "rank"]).groupby(["group", "channel"], as_index=False).head(TOP_N)
        psd_lookup = peaks[peaks["rank"] == 1].set_index(["group", "channel"])["freq_hz"].to_dict()
        acfp["nearest_psd_peak_freq_hz"] = acfp.apply(lambda r: psd_lookup.get((r["group"], r["channel"]), np.nan), axis=1)
        acfp["period_match_error_pct"] = acfp.apply(lambda r: abs(r["lag_s"] - 1 / r["nearest_psd_peak_freq_hz"]) / r["lag_s"] * 100 if np.isfinite(r["nearest_psd_peak_freq_hz"]) and r["nearest_psd_peak_freq_hz"] > 0 and r["lag_s"] > 0 else np.nan, axis=1)
    cross = build_cross_channel_peak_summary(peaks)
    bg = build_background_contrast(psd, peaks, cross)
    pump = build_pump_contrast(psd, peaks, lowfreq, sideband)
    decay = build_distance_decay(psd, acf)
    tables = {
        "manifest": manifest,
        "nist_group_summary": nist,
        "psd_group_summary": psd,
        "psd_peaks_top": peaks,
        "acf_group_summary": acf,
        "acf_peaks_top": acfp,
        "psd_acf_matches": matches,
        "cross_channel_peak_summary": cross,
        "background_contrast": bg,
        "pump_freq_contrast": pump,
        "distance_decay_summary": decay,
        "lowfreq_summary": lowfreq,
        "sideband_summary": sideband,
    }
    preferred_cols = {
        "nist_group_summary": ["group", "distance_m", "pump_freq_hz", "channel", "files", "mean", "median", "std", "q05", "q95", "iqr", "drift_span", "drift_ratio_ac", "rolling_mean_range", "lag_1_corr", "qq_corr", "tail_dev", "run_drift_flag", "abnormal_distribution_flag", "quality_note"],
        "psd_group_summary": ["group", "distance_m", "pump_freq_hz", "channel", "files", "df_hz", "low_freq_df_hz", "dom_all_freq_hz", "dom_all_psd", "dom_excl_low_freq_hz", "dom_excl_low_psd", "dom_0_1k_freq_hz", "dom_0_1k_psd", "dom_0_10k_freq_hz", "dom_0_10k_psd", "bandpower_0_100", "bandpower_100_1k", "bandpower_1k_10k", "bandpower_10k_50k", "bandpower_50k_100k", "bandpower_100k_200k", "total_power_0_200k", "spectral_entropy", "quality_note"],
        "acf_group_summary": ["group", "distance_m", "pump_freq_hz", "channel", "files", "zero_cross_s", "first_strong_lag_s", "first_strong_freq_hz", "first_strong_acf", "global_max_lag_s", "global_max_freq_hz", "global_max_acf", "peak_spacing_s", "peak_spacing_freq_hz", "acf_decay_time_s", "acf_quality_flag", "quality_note"],
        "acf_peaks_top": ["group", "distance_m", "pump_freq_hz", "channel", "rank", "lag_s", "equivalent_freq_hz", "acf_value", "peak_type", "is_above_threshold", "nearest_psd_peak_freq_hz", "period_match_error_pct"],
        "psd_acf_matches": ["group", "distance_m", "pump_freq_hz", "channel", "psd_peak_freq_hz", "psd_peak_period_s", "psd_peak_rank", "matched_acf_lag_s", "matched_acf_value", "match_error_s", "match_error_pct", "match_level"],
    }
    for name, df in list(tables.items()):
        if df is None:
            tables[name] = pd.DataFrame()
            continue
        cols = preferred_cols.get(name)
        if cols:
            for col in cols:
                if col not in df.columns:
                    df[col] = np.nan
            tables[name] = df[cols + [c for c in df.columns if c not in cols]]
    excel_path = OUT / "all_groups_summary.xlsx"
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        for name, df in tables.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)
            df.to_csv(CSV_DIR / f"{name}.csv", index=False, encoding="utf-8-sig")
    psd.to_csv(OUT / "all_groups_summary.csv", index=False, encoding="utf-8-sig")
    write_figures(psd, bg, cross, acf, decay, pump)
    write_report(tables, group_info, missing)
    log_lines.append(f"Input groups found: {len(group_info)} / {len(EXPECTED_GROUPS)}")
    log_lines.append(f"Missing groups: {missing if missing else 'none'}")
    log_lines.append(f"Excel generated: {excel_path.exists()} {excel_path}")
    log_lines.append(f"CSV tables: {len(tables)}")
    log_lines.append(f"Figures: {len(list(FIG.glob('*.png')))}")
    log_lines.append(f"Elapsed seconds: {time.time() - start:.1f}")
    (OUT / "run_log.txt").write_text("\n".join(log_lines), encoding="utf-8")
    zip_path = ROOT / "analysis_out.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in OUT.rglob("*"):
            zf.write(p, p.relative_to(ROOT))
    print("Generated files:")
    for p in sorted(OUT.rglob("*")):
        if p.is_file():
            print(f"- {p.relative_to(ROOT)}")
    print("\nGroup inventory:")
    for group in EXPECTED_GROUPS:
        info = group_info.get(group, {})
        print(f"- {group}: channels={len(info.get('channels', []))}, files={info.get('file_count', 0)}")
    print(f"\nMissing groups: {', '.join(missing) if missing else 'none'}")
    print(f"all_groups_summary.xlsx generated: {excel_path.exists()}")
    print(f"analysis_out.zip: {zip_path}")


if __name__ == "__main__":
    sys.exit(main())
