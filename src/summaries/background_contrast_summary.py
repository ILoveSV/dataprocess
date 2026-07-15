import numpy as np
import pandas as pd

from src.features.background_contrast import EPS, REAL_CHANNELS
from src.features.band_labels import default_bands_df


_LEGACY_DEFAULT_BANDS = pd.DataFrame([
    {"band_name": "0-100Hz", "band_low_hz": 0.0, "band_high_hz": 100.0},
    {"band_name": "100Hz-1kHz", "band_low_hz": 100.0, "band_high_hz": 1000.0},
    {"band_name": "1kHz-10kHz", "band_low_hz": 1000.0, "band_high_hz": 10000.0},
    {"band_name": "10kHz-50kHz", "band_low_hz": 10000.0, "band_high_hz": 50000.0},
    {"band_name": "50kHz-100kHz", "band_low_hz": 50000.0, "band_high_hz": 100000.0},
    {"band_name": "100kHz-200kHz", "band_low_hz": 100000.0, "band_high_hz": 200000.0},
    {"band_name": "30Hz±2Hz", "band_low_hz": 28.0, "band_high_hz": 32.0},
    {"band_name": "50Hz±2Hz", "band_low_hz": 48.0, "band_high_hz": 52.0},
    {"band_name": "60Hz±2Hz", "band_low_hz": 58.0, "band_high_hz": 62.0},
    {"band_name": "8.5kHz±300Hz", "band_low_hz": 8200.0, "band_high_hz": 8800.0},
    {"band_name": "50kHz±1kHz", "band_low_hz": 49000.0, "band_high_hz": 51000.0},
    {"band_name": "59.5kHz±1kHz", "band_low_hz": 58500.0, "band_high_hz": 60500.0},
])
DEFAULT_BANDS = default_bands_df()


def compute_cross_channel_support(contrast_tables):
    """Summarize support consistency across channel1-channel12."""
    tables = _as_table_dict(contrast_tables)
    rows = []
    if "bandpower" in tables and not tables["bandpower"].empty:
        rows.extend(_bandpower_support_rows(tables["bandpower"]))
    if "peak" in tables and not tables["peak"].empty:
        rows.extend(_peak_support_rows(tables["peak"]))
    if "acf" in tables and not tables["acf"].empty:
        rows.extend(_acf_support_rows(tables["acf"]))
    return pd.DataFrame(rows, columns=[
        "distance_m", "contrast_pair", "feature_type", "feature_name",
        "support_channel_count", "support_channel_ratio",
        "positive_channel_count", "negative_channel_count", "neutral_channel_count",
        "median_delta", "iqr_delta", "outlier_channels", "conclusion_level",
        "quality_note",
    ])


def compute_pumpfreq_net_contrast(background_contrast_tables):
    """Compare only net contrasts: (50Hz - 0Hz) - (30Hz - 0Hz)."""
    tables = _as_table_dict(background_contrast_tables)
    rows = []
    if "bandpower" in tables and not tables["bandpower"].empty:
        rows.extend(_pumpfreq_bandpower_rows(tables["bandpower"]))
    if "acf" in tables and not tables["acf"].empty:
        rows.extend(_pumpfreq_acf_rows(tables["acf"]))
    if "peak" in tables and not tables["peak"].empty:
        rows.extend(_pumpfreq_peak_rows(tables["peak"]))
    return pd.DataFrame(rows, columns=[
        "distance_m", "channel", "feature_type", "feature_name",
        "net_delta_30hz", "net_delta_50hz", "delta_50_minus_30",
        "can_distinguish_flag", "reason",
    ])


def compute_distance_decay_after_background(background_contrast_tables):
    """Compare 2m/3m/5m net feature values at the same pump frequency."""
    tables = _as_table_dict(background_contrast_tables)
    rows = []
    if "bandpower" in tables and not tables["bandpower"].empty:
        df = tables["bandpower"][tables["bandpower"]["channel"].isin(REAL_CHANNELS)]
        for keys, group in df.groupby(["pump_freq_hz", "band_name", "channel"]):
            by_distance = group.set_index("distance_m")["band_gain_dB"].to_dict()
            if not {2.0, 3.0, 5.0}.issubset(by_distance):
                continue
            v2, v3, v5 = by_distance[2.0], by_distance[3.0], by_distance[5.0]
            rows.append(_decay_row(keys[0], "bandpower", keys[1], keys[2], v2, v3, v5))
    if "acf" in tables and not tables["acf"].empty:
        df = tables["acf"][tables["acf"]["channel"].isin(REAL_CHANNELS)]
        for keys, group in df.groupby(["pump_freq_hz", "channel"]):
            by_distance = group.set_index("distance_m")["delta_first_strong_acf"].to_dict()
            if not {2.0, 3.0, 5.0}.issubset(by_distance):
                continue
            v2, v3, v5 = by_distance[2.0], by_distance[3.0], by_distance[5.0]
            rows.append(_decay_row(keys[0], "acf", "delta_first_strong_acf", keys[1], v2, v3, v5))
    return pd.DataFrame(rows, columns=[
        "pump_freq_hz", "feature_type", "feature_name", "channel",
        "net_value_2m", "net_value_3m", "net_value_5m",
        "monotonic_decay_flag", "decay_ratio_5m_over_2m", "trend_note",
    ])


def detect_qc_outlier_channels(feature_df):
    """Mark robust-z outlier channels without removing them."""
    if feature_df.empty:
        return pd.DataFrame(columns=[
            "group", "distance_m", "pump_freq_hz", "channel", "outlier_type",
            "feature_name", "feature_value", "group_median", "robust_z",
            "suggested_action",
        ])
    value_col = _detect_value_column(feature_df)
    if value_col is None:
        raise ValueError("feature_df needs a supported value column")
    group_cols = [col for col in ["group", "active_group", "distance_m", "pump_freq_hz", "band_name"] if col in feature_df.columns]
    rows = []
    for _, group in feature_df[feature_df["channel"].isin(REAL_CHANNELS)].groupby(group_cols or [lambda _: 0]):
        values = group[value_col].astype(float)
        median = float(values.median())
        mad = float(np.median(np.abs(values - median)))
        sigma = 1.4826 * mad + EPS
        for _, row in group.iterrows():
            value = float(row[value_col])
            robust_z = abs(value - median) / sigma
            power_extreme = value > 0 and median > 0 and value > 5.0 * median
            strong_background = "bg_bandpower_median" in row.index and row.get("bg_bandpower_median", 0) > 5.0 * median and median > 0
            if robust_z > 5.0 or power_extreme or strong_background:
                rows.append({
                    "group": row.get("group", row.get("active_group", "")),
                    "distance_m": row.get("distance_m", np.nan),
                    "pump_freq_hz": row.get("pump_freq_hz", np.nan),
                    "channel": row["channel"],
                    "outlier_type": _outlier_type(robust_z, power_extreme, strong_background),
                    "feature_name": row.get("band_name", value_col),
                    "feature_value": value,
                    "group_median": median,
                    "robust_z": robust_z,
                    "suggested_action": "mark_only_review_channel",
                })
    return pd.DataFrame(rows)


def _as_table_dict(contrast_tables):
    if isinstance(contrast_tables, dict):
        return contrast_tables
    return {"bandpower": contrast_tables}


def _bandpower_support_rows(df):
    rows = []
    current = df[df["channel"].isin(REAL_CHANNELS)].copy()
    for keys, group in current.groupby(["distance_m", "active_group", "background_group", "band_name"]):
        delta = group["band_gain_dB"].astype(float)
        positive = int((delta >= 3.0).sum())
        negative = int((delta <= -3.0).sum())
        support = int(group["support_flag"].astype(bool).sum())
        neutral = 12 - positive - negative
        rows.append(_support_row(keys[0], keys[1], keys[2], "bandpower", keys[3], support, positive, negative, neutral, delta, _all_note(df)))
    return rows


def _peak_support_rows(df):
    rows = []
    current = df[df["channel"].isin(REAL_CHANNELS)].copy()
    current["feature_name"] = current["band_name"].fillna("")
    current.loc[current["feature_name"] == "", "feature_name"] = current["peak_freq_hz"].round(3).astype(str) + "Hz"
    for keys, group in current.groupby(["distance_m", "active_group", "background_group", "feature_name"]):
        positive = int(group["peak_type"].isin(["new_peak", "enhanced_peak"]).sum())
        negative = int((group["peak_type"] == "suppressed_peak").sum())
        neutral = int((group["peak_type"] == "shared_peak").sum())
        support = int(group["support_flag"].astype(bool).sum())
        delta = group["delta_peak_dB"].dropna().astype(float)
        rows.append(_support_row(keys[0], keys[1], keys[2], "peak", keys[3], support, positive, negative, neutral, delta, _all_note(df)))
    return rows


def _acf_support_rows(df):
    rows = []
    current = df[df["channel"].isin(REAL_CHANNELS)].copy()
    for keys, group in current.groupby(["distance_m", "active_group", "background_group"]):
        delta = group["delta_first_strong_acf"].astype(float)
        support = int(group["acf_change_flag"].astype(bool).sum())
        positive = int((delta[group["acf_change_flag"].astype(bool)] > 0).sum())
        negative = int((delta[group["acf_change_flag"].astype(bool)] < 0).sum())
        neutral = 12 - positive - negative
        rows.append(_support_row(keys[0], keys[1], keys[2], "acf", "acf_change", support, positive, negative, neutral, delta, _all_note(df)))
    return rows


def _support_row(distance, active_group, background_group, feature_type, feature_name, support, positive, negative, neutral, delta, note):
    ratio = support / 12.0
    values = np.asarray(delta, dtype=float)
    values = values[np.isfinite(values)]
    q75, q25 = (np.percentile(values, 75), np.percentile(values, 25)) if len(values) else (np.nan, np.nan)
    return {
        "distance_m": distance,
        "contrast_pair": f"{active_group} vs {background_group}",
        "feature_type": feature_type,
        "feature_name": feature_name,
        "support_channel_count": support,
        "support_channel_ratio": ratio,
        "positive_channel_count": positive,
        "negative_channel_count": negative,
        "neutral_channel_count": neutral,
        "median_delta": float(np.median(values)) if len(values) else np.nan,
        "iqr_delta": float(q75 - q25) if len(values) else np.nan,
        "outlier_channels": "",
        "conclusion_level": _conclusion_level(support),
        "quality_note": note,
    }


def _pumpfreq_bandpower_rows(df):
    rows = []
    current = df[df["channel"].isin(REAL_CHANNELS)]
    for keys, group in current.groupby(["distance_m", "channel", "band_name"]):
        by_pump = group.set_index("pump_freq_hz")["band_gain_dB"].to_dict()
        if 30.0 not in by_pump or 50.0 not in by_pump:
            continue
        delta = float(by_pump[50.0] - by_pump[30.0])
        rows.append(_pumpfreq_row(keys[0], keys[1], "bandpower", keys[2], by_pump[30.0], by_pump[50.0], delta, abs(delta) >= 3.0, "abs_delta_ge_3dB" if abs(delta) >= 3.0 else "below_3dB"))
    return rows


def _pumpfreq_acf_rows(df):
    rows = []
    current = df[df["channel"].isin(REAL_CHANNELS)]
    for keys, group in current.groupby(["distance_m", "channel"]):
        by_pump = group.set_index("pump_freq_hz")["delta_first_strong_acf"].to_dict()
        if 30.0 not in by_pump or 50.0 not in by_pump:
            continue
        delta = float(by_pump[50.0] - by_pump[30.0])
        rows.append(_pumpfreq_row(keys[0], keys[1], "acf", "delta_first_strong_acf", by_pump[30.0], by_pump[50.0], delta, abs(delta) >= 0.1, "abs_acf_delta_ge_0p1" if abs(delta) >= 0.1 else "below_acf_threshold"))
    return rows


def _pumpfreq_peak_rows(df):
    rows = []
    current = df[df["channel"].isin(REAL_CHANNELS)]
    current["feature_name"] = current["band_name"].fillna("")
    current.loc[current["feature_name"] == "", "feature_name"] = current["peak_freq_hz"].round(3).astype(str) + "Hz"
    for keys, group in current.groupby(["distance_m", "channel", "feature_name"]):
        by_pump = group.groupby("pump_freq_hz")["peak_type"].agg(lambda s: ",".join(sorted(set(s)))).to_dict()
        if 30.0 not in by_pump or 50.0 not in by_pump:
            continue
        distinguish = by_pump[30.0] != by_pump[50.0]
        rows.append(_pumpfreq_row(keys[0], keys[1], "peak", keys[2], by_pump[30.0], by_pump[50.0], np.nan, distinguish, "different_peak_type" if distinguish else "same_peak_type"))
    return rows


def _pumpfreq_row(distance, channel, feature_type, feature_name, v30, v50, delta, flag, reason):
    return {
        "distance_m": distance,
        "channel": channel,
        "feature_type": feature_type,
        "feature_name": feature_name,
        "net_delta_30hz": v30,
        "net_delta_50hz": v50,
        "delta_50_minus_30": delta,
        "can_distinguish_flag": bool(flag),
        "reason": reason,
    }


def _decay_row(pump, feature_type, feature_name, channel, v2, v3, v5):
    monotonic = bool(v2 > v3 > v5)
    ratio = float(v5 / v2) if abs(v2) > EPS else np.nan
    return {
        "pump_freq_hz": pump,
        "feature_type": feature_type,
        "feature_name": feature_name,
        "channel": channel,
        "net_value_2m": v2,
        "net_value_3m": v3,
        "net_value_5m": v5,
        "monotonic_decay_flag": monotonic,
        "decay_ratio_5m_over_2m": ratio,
        "trend_note": "monotonic_decay" if monotonic else "not_monotonic",
    }


def _conclusion_level(support):
    if support >= 8:
        return "strong"
    if support >= 5:
        return "medium"
    if support >= 2:
        return "weak"
    return "none"


def _all_note(df):
    notes = df.get("quality_note", pd.Series(dtype=str)).dropna().astype(str)
    return "excluded_ALL" if notes.str.contains("excluded_ALL").any() else ""


def _detect_value_column(df):
    for col in ["band_gain_dB", "psd_gain_dB", "delta_first_strong_acf", "active_bandpower_median"]:
        if col in df.columns:
            return col
    return None


def _outlier_type(robust_z, power_extreme, strong_background):
    if strong_background:
        return "strong_background_target_band"
    if power_extreme:
        return "positive_power_extreme"
    return "robust_z_gt_5"
