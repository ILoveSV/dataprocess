import re

import pandas as pd


BAND_DEFINITIONS = [
    {"canonical_band_id": "0_100hz", "display_label": "0-100 Hz", "band_low_hz": 0.0, "band_high_hz": 100.0},
    {"canonical_band_id": "100hz_1khz", "display_label": "100 Hz-1 kHz", "band_low_hz": 100.0, "band_high_hz": 1000.0},
    {"canonical_band_id": "1khz_10khz", "display_label": "1-10 kHz", "band_low_hz": 1000.0, "band_high_hz": 10000.0},
    {"canonical_band_id": "10khz_50khz", "display_label": "10-50 kHz", "band_low_hz": 10000.0, "band_high_hz": 50000.0},
    {"canonical_band_id": "10khz_200khz", "display_label": "10-200 kHz (wide)", "band_low_hz": 10000.0, "band_high_hz": 200000.0, "include_in_default": False},
    {"canonical_band_id": "50khz_100khz", "display_label": "50-100 kHz", "band_low_hz": 50000.0, "band_high_hz": 100000.0},
    {"canonical_band_id": "100khz_200khz", "display_label": "100-200 kHz", "band_low_hz": 100000.0, "band_high_hz": 200000.0},
    {"canonical_band_id": "30hz_pm2hz", "display_label": "30 Hz +/- 2 Hz", "band_low_hz": 28.0, "band_high_hz": 32.0},
    {"canonical_band_id": "50hz_pm2hz", "display_label": "50 Hz +/- 2 Hz", "band_low_hz": 48.0, "band_high_hz": 52.0},
    {"canonical_band_id": "60hz_pm2hz", "display_label": "60 Hz +/- 2 Hz", "band_low_hz": 58.0, "band_high_hz": 62.0},
    {"canonical_band_id": "8p5khz_pm300hz", "display_label": "8.5 kHz +/- 300 Hz", "band_low_hz": 8200.0, "band_high_hz": 8800.0},
    {"canonical_band_id": "50khz_pm1khz", "display_label": "50 kHz +/- 1 kHz", "band_low_hz": 49000.0, "band_high_hz": 51000.0},
    {"canonical_band_id": "59p5khz_pm1khz", "display_label": "59.5 kHz +/- 1 kHz", "band_low_hz": 58500.0, "band_high_hz": 60500.0},
]


_ALIASES = {
    "0-100hz": "0_100hz",
    "0_100hz": "0_100hz",
    "100hz-1khz": "100hz_1khz",
    "100hz_1khz": "100hz_1khz",
    "1khz-10khz": "1khz_10khz",
    "1khz_10khz": "1khz_10khz",
    "1k_10k": "1khz_10khz",
    "1k-10k": "1khz_10khz",
    "10khz-50khz": "10khz_50khz",
    "10khz_50khz": "10khz_50khz",
    "10k_50k": "10khz_50khz",
    "10khz-200khz": "10khz_200khz",
    "10khz_200khz": "10khz_200khz",
    "10k_200k": "10khz_200khz",
    "10k-200k": "10khz_200khz",
    "50khz-100khz": "50khz_100khz",
    "50khz_100khz": "50khz_100khz",
    "50k_100k": "50khz_100khz",
    "100khz-200khz": "100khz_200khz",
    "100khz_200khz": "100khz_200khz",
    "100k_200k": "100khz_200khz",
    "30hz卤2hz": "30hz_pm2hz",
    "30hz±2hz": "30hz_pm2hz",
    "30hz+/-2hz": "30hz_pm2hz",
    "30hz_pm2hz": "30hz_pm2hz",
    "50hz卤2hz": "50hz_pm2hz",
    "50hz±2hz": "50hz_pm2hz",
    "50hz+/-2hz": "50hz_pm2hz",
    "50hz_pm2hz": "50hz_pm2hz",
    "60hz卤2hz": "60hz_pm2hz",
    "60hz±2hz": "60hz_pm2hz",
    "60hz+/-2hz": "60hz_pm2hz",
    "60hz_pm2hz": "60hz_pm2hz",
    "8.5khz卤300hz": "8p5khz_pm300hz",
    "8.5khz±300hz": "8p5khz_pm300hz",
    "8.5khz+/-300hz": "8p5khz_pm300hz",
    "8p5khz_pm300hz": "8p5khz_pm300hz",
    "50khz卤1khz": "50khz_pm1khz",
    "50khz±1khz": "50khz_pm1khz",
    "50khz+/-1khz": "50khz_pm1khz",
    "50khz_pm1khz": "50khz_pm1khz",
    "59.5khz卤1khz": "59p5khz_pm1khz",
    "59.5khz±1khz": "59p5khz_pm1khz",
    "59.5khz+/-1khz": "59p5khz_pm1khz",
    "59p5khz_pm1khz": "59p5khz_pm1khz",
}

_DISPLAY_BY_ID = {row["canonical_band_id"]: row["display_label"] for row in BAND_DEFINITIONS}
_KNOWN_IDS = set(_DISPLAY_BY_ID)


def default_bands_df():
    df = pd.DataFrame(BAND_DEFINITIONS)
    if "include_in_default" in df.columns:
        include = df["include_in_default"].map(lambda value: True if pd.isna(value) else bool(value))
        df = df[include]
    return df.rename(columns={"canonical_band_id": "band_name"})[
        ["band_name", "band_low_hz", "band_high_hz"]
    ]


def canonicalize_band_label(label):
    if label is None or pd.isna(label):
        return ""
    text = str(label).strip()
    key = _normalize(text)
    if key in _ALIASES:
        return _ALIASES[key]
    if key in _KNOWN_IDS:
        return key
    return key


def display_label_for_band(canonical_band_id):
    return _DISPLAY_BY_ID.get(str(canonical_band_id), str(canonical_band_id))


def add_band_display_columns(df, source_col="band_name"):
    if df is None or df.empty or source_col not in df.columns:
        return df
    out = df.copy()
    out["canonical_band_id"] = out[source_col].map(canonicalize_band_label)
    out["display_label"] = out["canonical_band_id"].map(display_label_for_band)
    out[source_col] = out["canonical_band_id"]
    return out


def canonicalize_feature_column(df, column="feature_name"):
    if df is None or df.empty or column not in df.columns:
        return df
    out = df.copy()
    out["canonical_band_id"] = out[column].map(canonicalize_band_label)
    out["display_label"] = out["canonical_band_id"].map(display_label_for_band)
    out[column] = out["canonical_band_id"]
    return out


def build_band_mapping_debug(*tables):
    rows = []
    for table in tables:
        if table is None or table.empty:
            continue
        for column in ("band_name", "feature_name"):
            if column not in table.columns:
                continue
            for old_label, count in table[column].value_counts(dropna=False).items():
                canonical = canonicalize_band_label(old_label)
                rows.append({
                    "old_label": old_label,
                    "canonical_band_id": canonical,
                    "display_label": display_label_for_band(canonical),
                    "data_count": int(count),
                })
    if not rows:
        return pd.DataFrame(columns=["old_label", "canonical_band_id", "display_label", "data_count"])
    return (
        pd.DataFrame(rows)
        .groupby(["old_label", "canonical_band_id", "display_label"], dropna=False, as_index=False)["data_count"]
        .sum()
        .sort_values(["canonical_band_id", "old_label"])
    )


def _normalize(label):
    text = str(label).strip().lower()
    text = text.replace(" ", "")
    text = text.replace("hz", "hz")
    text = text.replace("khz", "khz")
    text = text.replace("±", "±").replace("+/-", "+/-")
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"(?<=\d)k(?=(_|-|\+|$))", "khz", text)
    text = text.replace("khzhz", "khz")
    return text
