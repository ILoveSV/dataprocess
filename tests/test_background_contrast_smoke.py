import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.features.background_contrast import (
    REAL_CHANNELS,
    compute_acf_contrast,
    compute_bandpower_contrast,
    compute_peak_contrast,
    compute_psd_gain_curves,
    make_background_pairs,
)
from src.pipelines.background_contrast_smoke_pipeline import (
    build_smoke_acf_summary_df,
    build_smoke_outputs,
    build_smoke_peaks_df,
    build_smoke_psd_curve_df,
    build_support_fixture,
)
from src.summaries.background_contrast_summary import (
    DEFAULT_BANDS,
    compute_cross_channel_support,
    compute_distance_decay_after_background,
    compute_pumpfreq_net_contrast,
)


def test_background_contrast_smoke_outputs_core_expectations():
    outputs = build_smoke_outputs()
    psd_gain = outputs["psd_gain_curves"]
    bandpower = outputs["bandpower"]
    peak = outputs["peak"]
    acf = outputs["acf"]
    cross = outputs["cross_channel"]
    net = outputs["pumpfreq_net"]
    decay = outputs["distance_decay"]

    gain_595 = _nearest_gain(psd_gain, "2m30hz", "channel1", 59500.0)
    gain_85 = _nearest_gain(psd_gain, "2m30hz", "channel1", 8500.0)
    assert gain_595 > 8.0
    assert abs(gain_85) < 3.0

    band = bandpower[(bandpower["active_group"] == "2m30hz") & (bandpower["channel"] == "channel1") & (bandpower["band_name"] == "50kHz-100kHz")].iloc[0]
    assert np.isclose(band["band_gain_dB"], 10.0, atol=0.5)
    assert bool(band["support_flag"])

    assert _peak_type(peak, "2m30hz", "channel1", "59.5kHz±1kHz") == "new_peak"
    assert _peak_type(peak, "2m30hz", "channel1", "50kHz±1kHz") == "enhanced_peak"
    assert _peak_type(peak, "2m30hz", "channel1", "100kHz-200kHz") == "suppressed_peak"
    assert _peak_type(peak, "2m30hz", "channel1", "8.5kHz±300Hz") == "shared_peak"

    acf_row = acf[(acf["active_group"] == "2m30hz") & (acf["channel"] == "channel1")].iloc[0]
    assert bool(acf_row["acf_change_flag"])
    assert np.isclose(acf_row["delta_first_strong_acf"], 0.4)
    assert acf_row["delta_first_strong_lag_s"] < 0

    cc = cross[(cross["contrast_pair"] == "2m50hz vs 2m0hz") & (cross["feature_type"] == "bandpower") & (cross["feature_name"] == "50kHz-100kHz")].iloc[0]
    assert cc["conclusion_level"] == "strong"

    net_row = net[(net["distance_m"] == 2.0) & (net["channel"] == "channel1") & (net["feature_type"] == "bandpower") & (net["feature_name"] == "50kHz-100kHz")].iloc[0]
    assert np.isclose(net_row["delta_50_minus_30"], 7.0, atol=0.5)
    assert bool(net_row["can_distinguish_flag"])

    decay_row = decay[(decay["pump_freq_hz"] == 30.0) & (decay["feature_type"] == "bandpower") & (decay["feature_name"] == "50kHz-100kHz") & (decay["channel"] == "channel1")].iloc[0]
    assert bool(decay_row["monotonic_decay_flag"])


def test_low_frequency_reliability_rules():
    bands = pd.DataFrame([{"band_name": "30Hz±2Hz", "band_low_hz": 28.0, "band_high_hz": 32.0}])
    coarse = _lowfreq_curve_df(df_hz=24.414, freqs=[30.0])
    fine = _lowfreq_curve_df(df_hz=0.5, freqs=[28.0, 30.0, 32.0])
    pairs = pd.DataFrame([{"distance_m": 2.0, "active_group": "2m30hz", "background_group": "2m0hz", "pump_freq_hz": 30.0, "missing_background": False}])

    coarse_out = compute_bandpower_contrast(coarse, pairs, bands)
    fine_out = compute_bandpower_contrast(fine, pairs, bands)

    assert not bool(coarse_out[coarse_out["channel"] == "channel1"].iloc[0]["lowfreq_reliable_flag"])
    assert "low_frequency_resolution_unreliable" in coarse_out[coarse_out["channel"] == "channel1"].iloc[0]["quality_note"]
    assert bool(fine_out[fine_out["channel"] == "channel1"].iloc[0]["lowfreq_reliable_flag"])


def test_cross_channel_support_levels_and_all_exclusion():
    expected = {"strong": 8, "medium": 6, "weak": 3, "none": 1}
    for level, count in expected.items():
        fixture = build_support_fixture(level)
        summary = compute_cross_channel_support({"bandpower": fixture})
        row = summary.iloc[0]
        assert row["support_channel_count"] == count
        assert row["conclusion_level"] == level
        assert row["support_channel_ratio"] == count / 12.0


def test_make_background_pairs_missing_background():
    pairs = make_background_pairs(["2m30hz", "3m0hz", "3m50hz"])
    missing = pairs[pairs["active_group"] == "2m30hz"].iloc[0]
    present = pairs[pairs["active_group"] == "3m50hz"].iloc[0]
    assert bool(missing["missing_background"])
    assert present["background_group"] == "3m0hz"


def _nearest_gain(df, active_group, channel, freq):
    current = df[(df["active_group"] == active_group) & (df["channel"] == channel)].copy()
    current["err"] = (current["freq_hz"] - freq).abs()
    return current.sort_values("err").iloc[0]["psd_gain_dB"]


def _peak_type(df, active_group, channel, band_name):
    return df[(df["active_group"] == active_group) & (df["channel"] == channel) & (df["band_name"] == band_name)].iloc[0]["peak_type"]


def _lowfreq_curve_df(df_hz, freqs):
    rows = []
    for group, pump, mult in [("2m0hz", 0.0, 1.0), ("2m30hz", 30.0, 2.0)]:
        for channel in REAL_CHANNELS + ["ALL"]:
            for file_idx in range(5):
                for freq in freqs:
                    rows.append({
                        "group": group,
                        "distance_m": 2.0,
                        "pump_freq_hz": pump,
                        "channel": channel,
                        "file_id": f"file{file_idx}",
                        "freq_hz": freq,
                        "psd": 1e-12 * mult,
                        "df_hz": df_hz,
                        "is_smoke_test": True,
                    })
    return pd.DataFrame(rows)
