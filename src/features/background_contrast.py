import math
import re
from pathlib import Path

import numpy as np
import pandas as pd


EPS = 1e-30
REAL_CHANNELS = [f"channel{i}" for i in range(1, 13)]


PSD_CURVE_COLUMNS = [
    "group", "distance_m", "pump_freq_hz", "channel", "file_id",
    "freq_hz", "psd", "df_hz", "is_smoke_test",
]
PSD_PEAK_COLUMNS = [
    "group", "distance_m", "pump_freq_hz", "channel", "file_id",
    "peak_rank", "peak_freq_hz", "peak_psd", "peak_snr_dB",
    "df_hz", "band_name", "is_smoke_test",
]
ACF_SUMMARY_COLUMNS = [
    "group", "distance_m", "pump_freq_hz", "channel", "file_id",
    "first_strong_lag_s", "first_strong_acf", "global_max_lag_s",
    "global_max_acf", "peak_spacing_s", "acf_decay_time_s",
    "is_smoke_test",
]


def make_background_pairs(groups):
    """Build same-distance active-vs-0Hz background pairs from group names."""
    parsed = []
    for group in groups:
        info = _parse_group_name(group)
        if info is not None:
            parsed.append({"group": group, **info})

    backgrounds = {row["distance_m"]: row["group"] for row in parsed if row["pump_freq_hz"] == 0}
    rows = []
    for row in sorted(parsed, key=lambda x: (x["distance_m"], x["pump_freq_hz"], x["group"])):
        if row["pump_freq_hz"] == 0:
            continue
        bg_group = backgrounds.get(row["distance_m"])
        rows.append({
            "distance_m": row["distance_m"],
            "active_group": row["group"],
            "background_group": bg_group,
            "pump_freq_hz": row["pump_freq_hz"],
            "missing_background": bg_group is None,
        })
    return pd.DataFrame(rows)


def compute_psd_gain_curves(psd_curve_df, pairs, exclude_all_channel=True, eps=EPS):
    """Compute active-minus-background median log PSD curves by channel/frequency."""
    _require_columns(psd_curve_df, PSD_CURVE_COLUMNS, "psd_curve_df")
    pairs_df = _as_pairs_df(pairs)
    df, excluded_all = _filter_channels(psd_curve_df, exclude_all_channel)
    df = df.copy()
    df["logpsd_dB"] = 10.0 * np.log10(df["psd"].astype(float).clip(lower=0.0) + eps)

    rows = []
    for pair in pairs_df.to_dict("records"):
        if pair.get("missing_background") or pd.isna(pair.get("background_group")):
            continue
        active = df[df["group"] == pair["active_group"]]
        bg = df[df["group"] == pair["background_group"]]
        if active.empty or bg.empty:
            continue
        active_stats = _curve_stats(active, "active")
        bg_stats = _curve_stats(bg, "background")
        merged = active_stats.merge(bg_stats, on=["channel", "freq_hz"], how="inner")
        for _, row in merged.iterrows():
            notes = _note(excluded_all, "excluded_ALL")
            df_hz = _median_number([row.get("active_df_hz"), row.get("background_df_hz")])
            rows.append({
                "distance_m": pair["distance_m"],
                "active_group": pair["active_group"],
                "background_group": pair["background_group"],
                "pump_freq_hz": pair["pump_freq_hz"],
                "channel": row["channel"],
                "freq_hz": row["freq_hz"],
                "background_logpsd_median": row["background_logpsd_median"],
                "active_logpsd_median": row["active_logpsd_median"],
                "psd_gain_dB": row["active_logpsd_median"] - row["background_logpsd_median"],
                "background_logpsd_p10": row["background_logpsd_p10"],
                "background_logpsd_p90": row["background_logpsd_p90"],
                "active_logpsd_p10": row["active_logpsd_p10"],
                "active_logpsd_p90": row["active_logpsd_p90"],
                "file_count_background": int(row["background_file_count"]),
                "file_count_active": int(row["active_file_count"]),
                "df_hz": df_hz,
                "quality_note": notes,
            })
    return pd.DataFrame(rows, columns=[
        "distance_m", "active_group", "background_group", "pump_freq_hz",
        "channel", "freq_hz", "background_logpsd_median", "active_logpsd_median",
        "psd_gain_dB", "background_logpsd_p10", "background_logpsd_p90",
        "active_logpsd_p10", "active_logpsd_p90", "file_count_background",
        "file_count_active", "df_hz", "quality_note",
    ])


def compute_bandpower_contrast(psd_curve_df, pairs, bands, exclude_all_channel=True, eps=EPS):
    """Compute background contrast of file-level PSD bandpower."""
    _require_columns(psd_curve_df, PSD_CURVE_COLUMNS, "psd_curve_df")
    pairs_df = _as_pairs_df(pairs)
    bands_df = _as_bands_df(bands)
    df, excluded_all = _filter_channels(psd_curve_df, exclude_all_channel)
    file_band = _file_bandpower(df, bands_df)
    rows = []

    for pair in pairs_df.to_dict("records"):
        if pair.get("missing_background") or pd.isna(pair.get("background_group")):
            continue
        for channel in REAL_CHANNELS:
            for band in bands_df.to_dict("records"):
                active = _select_band(file_band, pair["active_group"], channel, band["band_name"])
                bg = _select_band(file_band, pair["background_group"], channel, band["band_name"])
                if active.empty or bg.empty:
                    continue
                active_vals = active["bandpower"].astype(float).values
                bg_vals = bg["bandpower"].astype(float).values
                active_log = 10.0 * np.log10(active_vals + eps)
                bg_log = 10.0 * np.log10(bg_vals + eps)
                active_med = float(np.median(active_vals))
                bg_med = float(np.median(bg_vals))
                band_gain = 10.0 * math.log10((active_med + eps) / (bg_med + eps))
                effect = _robust_effect_size(active_log, bg_log, eps)
                bin_count = int(min(active["bin_count"].median(), bg["bin_count"].median()))
                df_hz = _median_number([active["df_hz"].median(), bg["df_hz"].median()])
                lowfreq_reliable, low_note = _lowfreq_reliability(band["band_name"], df_hz, bin_count)
                support = bool(abs(band_gain) >= 3.0 or abs(effect) >= 1.0)
                rows.append({
                    "distance_m": pair["distance_m"],
                    "active_group": pair["active_group"],
                    "background_group": pair["background_group"],
                    "pump_freq_hz": pair["pump_freq_hz"],
                    "channel": channel,
                    "band_name": band["band_name"],
                    "band_low_hz": band["band_low_hz"],
                    "band_high_hz": band["band_high_hz"],
                    "bin_count": bin_count,
                    "df_hz": df_hz,
                    "bg_bandpower_median": bg_med,
                    "active_bandpower_median": active_med,
                    "band_gain_dB": band_gain,
                    "robust_effect_size": effect,
                    "lowfreq_reliable_flag": lowfreq_reliable,
                    "support_flag": support,
                    "quality_note": _join_notes(_note(excluded_all, "excluded_ALL"), low_note),
                })
    return pd.DataFrame(rows, columns=[
        "distance_m", "active_group", "background_group", "pump_freq_hz",
        "channel", "band_name", "band_low_hz", "band_high_hz", "bin_count",
        "df_hz", "bg_bandpower_median", "active_bandpower_median",
        "band_gain_dB", "robust_effect_size", "lowfreq_reliable_flag",
        "support_flag", "quality_note",
    ])


def compute_peak_contrast(active_peaks_df, background_peaks_df, pairs, exclude_all_channel=True, eps=EPS):
    """Classify active PSD peaks against same-distance background peaks."""
    _require_columns(active_peaks_df, PSD_PEAK_COLUMNS, "active_peaks_df")
    _require_columns(background_peaks_df, PSD_PEAK_COLUMNS, "background_peaks_df")
    pairs_df = _as_pairs_df(pairs)
    active_df, excluded_a = _filter_channels(active_peaks_df, exclude_all_channel)
    bg_df, excluded_b = _filter_channels(background_peaks_df, exclude_all_channel)
    excluded_all = excluded_a or excluded_b
    rows = []
    for pair in pairs_df.to_dict("records"):
        if pair.get("missing_background") or pd.isna(pair.get("background_group")):
            continue
        active_pair = active_df[active_df["group"] == pair["active_group"]]
        bg_pair = bg_df[bg_df["group"] == pair["background_group"]]
        for _, peak in active_pair.iterrows():
            candidates = bg_pair[bg_pair["channel"] == peak["channel"]]
            match = _nearest_peak_match(peak, candidates)
            bg_psd = np.nan
            bg_snr = np.nan
            bg_freq = np.nan
            err = np.nan
            if match is None:
                peak_type = "new_peak"
                delta = np.nan
            else:
                bg_freq = float(match["peak_freq_hz"])
                bg_psd = float(match["peak_psd"])
                bg_snr = match.get("peak_snr_dB", np.nan)
                err = abs(float(peak["peak_freq_hz"]) - bg_freq)
                delta = 10.0 * math.log10((float(peak["peak_psd"]) + eps) / (bg_psd + eps))
                peak_type = _classify_matched_peak(delta)
            active_snr = peak.get("peak_snr_dB", np.nan)
            support = _peak_support_flag(peak_type, delta, active_snr)
            rows.append({
                "distance_m": pair["distance_m"],
                "active_group": pair["active_group"],
                "background_group": pair["background_group"],
                "pump_freq_hz": pair["pump_freq_hz"],
                "channel": peak["channel"],
                "peak_freq_hz": float(peak["peak_freq_hz"]),
                "matched_bg_freq_hz": bg_freq,
                "match_error_hz": err,
                "peak_type": peak_type,
                "active_peak_psd": float(peak["peak_psd"]),
                "bg_peak_psd": bg_psd,
                "delta_peak_dB": delta,
                "active_peak_snr_dB": active_snr,
                "bg_peak_snr_dB": bg_snr,
                "band_name": peak.get("band_name", ""),
                "support_flag": support,
                "quality_note": _note(excluded_all, "excluded_ALL"),
            })
    return pd.DataFrame(rows, columns=[
        "distance_m", "active_group", "background_group", "pump_freq_hz",
        "channel", "peak_freq_hz", "matched_bg_freq_hz", "match_error_hz",
        "peak_type", "active_peak_psd", "bg_peak_psd", "delta_peak_dB",
        "active_peak_snr_dB", "bg_peak_snr_dB", "band_name", "support_flag",
        "quality_note",
    ])


def compute_acf_contrast(acf_summary_df, pairs, exclude_all_channel=True):
    """Compute median ACF feature deltas by active/background group and channel."""
    _require_columns(acf_summary_df, ACF_SUMMARY_COLUMNS, "acf_summary_df")
    pairs_df = _as_pairs_df(pairs)
    df, excluded_all = _filter_channels(acf_summary_df, exclude_all_channel)
    features = [
        "first_strong_lag_s", "first_strong_acf", "global_max_lag_s",
        "global_max_acf", "peak_spacing_s", "acf_decay_time_s",
    ]
    agg = df.groupby(["group", "channel"], as_index=False)[features].median(numeric_only=True)
    rows = []
    for pair in pairs_df.to_dict("records"):
        if pair.get("missing_background") or pd.isna(pair.get("background_group")):
            continue
        for channel in REAL_CHANNELS:
            active = _one_row(agg, pair["active_group"], channel)
            bg = _one_row(agg, pair["background_group"], channel)
            if active is None or bg is None:
                continue
            delta_first_lag = active["first_strong_lag_s"] - bg["first_strong_lag_s"]
            delta_spacing = active["peak_spacing_s"] - bg["peak_spacing_s"]
            flag = bool(
                abs(active["first_strong_acf"] - bg["first_strong_acf"]) >= 0.1
                or abs(active["global_max_acf"] - bg["global_max_acf"]) >= 0.1
                or _relative_change(delta_first_lag, bg["first_strong_lag_s"]) >= 0.2
                or _relative_change(delta_spacing, bg["peak_spacing_s"]) >= 0.2
            )
            rows.append({
                "distance_m": pair["distance_m"],
                "active_group": pair["active_group"],
                "background_group": pair["background_group"],
                "pump_freq_hz": pair["pump_freq_hz"],
                "channel": channel,
                "bg_first_strong_lag_s": bg["first_strong_lag_s"],
                "active_first_strong_lag_s": active["first_strong_lag_s"],
                "delta_first_strong_lag_s": delta_first_lag,
                "bg_first_strong_acf": bg["first_strong_acf"],
                "active_first_strong_acf": active["first_strong_acf"],
                "delta_first_strong_acf": active["first_strong_acf"] - bg["first_strong_acf"],
                "bg_global_max_lag_s": bg["global_max_lag_s"],
                "active_global_max_lag_s": active["global_max_lag_s"],
                "delta_global_max_lag_s": active["global_max_lag_s"] - bg["global_max_lag_s"],
                "bg_global_max_acf": bg["global_max_acf"],
                "active_global_max_acf": active["global_max_acf"],
                "delta_global_max_acf": active["global_max_acf"] - bg["global_max_acf"],
                "bg_peak_spacing_s": bg["peak_spacing_s"],
                "active_peak_spacing_s": active["peak_spacing_s"],
                "delta_peak_spacing_s": delta_spacing,
                "bg_acf_decay_time_s": bg["acf_decay_time_s"],
                "active_acf_decay_time_s": active["acf_decay_time_s"],
                "delta_acf_decay_time_s": active["acf_decay_time_s"] - bg["acf_decay_time_s"],
                "acf_change_flag": flag,
                "quality_note": _note(excluded_all, "excluded_ALL"),
            })
    return pd.DataFrame(rows)


def _parse_group_name(group):
    match = re.fullmatch(r"(?P<distance>\d+(?:\.\d+)?)m(?P<pump>\d+(?:\.\d+)?)hz", str(group).lower())
    if not match:
        return None
    return {
        "distance_m": float(match.group("distance")),
        "pump_freq_hz": float(match.group("pump")),
    }


def _as_pairs_df(pairs):
    return pairs.copy() if isinstance(pairs, pd.DataFrame) else pd.DataFrame(pairs)


def _as_bands_df(bands):
    return bands.copy() if isinstance(bands, pd.DataFrame) else pd.DataFrame(bands)


def _require_columns(df, columns, name):
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(f"{name} missing required columns: {missing}")


def _filter_channels(df, exclude_all_channel):
    if not exclude_all_channel:
        return df.copy(), False
    excluded_all = bool((df["channel"].astype(str).str.upper() == "ALL").any())
    return df[df["channel"].isin(REAL_CHANNELS)].copy(), excluded_all


def _curve_stats(df, prefix):
    grouped = df.groupby(["channel", "freq_hz"])
    stats = grouped["logpsd_dB"].agg(
        **{
            f"{prefix}_logpsd_median": "median",
            f"{prefix}_logpsd_p10": lambda x: np.percentile(x, 10),
            f"{prefix}_logpsd_p90": lambda x: np.percentile(x, 90),
        }
    ).reset_index()
    counts = grouped["file_id"].nunique().reset_index(name=f"{prefix}_file_count")
    dfs = grouped["df_hz"].median().reset_index(name=f"{prefix}_df_hz")
    return stats.merge(counts, on=["channel", "freq_hz"]).merge(dfs, on=["channel", "freq_hz"])


def _file_bandpower(df, bands_df):
    rows = []
    for band in bands_df.to_dict("records"):
        mask = (df["freq_hz"] >= band["band_low_hz"]) & (df["freq_hz"] <= band["band_high_hz"])
        current = df[mask]
        for keys, group in current.groupby(["group", "distance_m", "pump_freq_hz", "channel", "file_id"]):
            df_hz = float(group["df_hz"].median())
            rows.append({
                "group": keys[0],
                "distance_m": keys[1],
                "pump_freq_hz": keys[2],
                "channel": keys[3],
                "file_id": keys[4],
                "band_name": band["band_name"],
                "bandpower": float((group["psd"].astype(float) * group["df_hz"].astype(float)).sum()),
                "bin_count": int(len(group)),
                "df_hz": df_hz,
            })
    return pd.DataFrame(rows)


def _select_band(file_band, group, channel, band_name):
    return file_band[
        (file_band["group"] == group)
        & (file_band["channel"] == channel)
        & (file_band["band_name"] == band_name)
    ]


def _robust_effect_size(active_log, bg_log, eps):
    active_med = float(np.median(active_log))
    bg_med = float(np.median(bg_log))
    sigma = math.sqrt(_robust_sigma(active_log) ** 2 + _robust_sigma(bg_log) ** 2)
    return (active_med - bg_med) / (sigma + eps)


def _robust_sigma(values):
    values = np.asarray(values, dtype=float)
    med = np.median(values)
    return float(1.4826 * np.median(np.abs(values - med)))


def _lowfreq_reliability(band_name, df_hz, bin_count):
    is_low_target = band_name in {"30hz_pm2hz", "50hz_pm2hz", "60hz_pm2hz"}
    if not is_low_target:
        return True, ""
    reliable = bool(df_hz <= 1.0 and bin_count >= 3)
    return reliable, "" if reliable else "low_frequency_resolution_unreliable"


def _nearest_peak_match(peak, candidates):
    if candidates.empty:
        return None
    freq = float(peak["peak_freq_hz"])
    df_hz = float(peak.get("df_hz", np.nan))
    if not np.isfinite(df_hz):
        df_hz = 0.0
    tol = max(2.0 * df_hz, 2.0) if freq < 200.0 else max(2.0 * df_hz, 50.0)
    current = candidates.copy()
    current["match_error"] = (current["peak_freq_hz"].astype(float) - freq).abs()
    current = current[current["match_error"] <= tol]
    if current.empty:
        return None
    return current.sort_values("match_error").iloc[0]


def _classify_matched_peak(delta_peak_dB):
    if delta_peak_dB >= 6.0:
        return "enhanced_peak"
    if delta_peak_dB <= -6.0:
        return "suppressed_peak"
    return "shared_peak"


def _peak_support_flag(peak_type, delta_peak_dB, active_snr):
    if peak_type not in {"new_peak", "enhanced_peak"}:
        return False
    if pd.notna(active_snr):
        return bool(float(active_snr) >= 6.0)
    return bool(pd.notna(delta_peak_dB) and float(delta_peak_dB) >= 6.0)


def _one_row(df, group, channel):
    rows = df[(df["group"] == group) & (df["channel"] == channel)]
    if rows.empty:
        return None
    return rows.iloc[0]


def _relative_change(delta, baseline):
    if not np.isfinite(baseline) or abs(baseline) < EPS:
        return 0.0
    return abs(float(delta) / float(baseline))


def _median_number(values):
    clean = [float(v) for v in values if pd.notna(v)]
    return float(np.median(clean)) if clean else np.nan


def _note(condition, text):
    return text if condition else ""


def _join_notes(*notes):
    return ";".join(note for note in notes if note)
