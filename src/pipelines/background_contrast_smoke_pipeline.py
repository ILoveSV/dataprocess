import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src.features.background_contrast import (
    REAL_CHANNELS,
    compute_acf_contrast,
    compute_bandpower_contrast,
    compute_peak_contrast,
    compute_psd_gain_curves,
    make_background_pairs,
)
from src.reports.background_contrast_export import export_background_contrast_smoke_outputs
from src.summaries.background_contrast_summary import (
    DEFAULT_BANDS,
    compute_cross_channel_support,
    compute_distance_decay_after_background,
    compute_pumpfreq_net_contrast,
    detect_qc_outlier_channels,
)


SMOKE_OUTPUT_DIR = Path("analysis_out") / "contrast_v1_smoke"


def build_smoke_outputs():
    """Build synthetic inputs and all Background Contrast v1 smoke outputs."""
    psd_curve_df = build_smoke_psd_curve_df()
    peaks_df = build_smoke_peaks_df()
    acf_df = build_smoke_acf_summary_df()
    pairs = make_background_pairs(["2m0hz", "2m30hz", "2m50hz", "3m0hz", "3m30hz", "3m50hz", "5m0hz", "5m30hz", "5m50hz"])

    psd_gain = compute_psd_gain_curves(psd_curve_df, pairs)
    bandpower = compute_bandpower_contrast(psd_curve_df, pairs, DEFAULT_BANDS)
    active_peaks = peaks_df[peaks_df["pump_freq_hz"] != 0].copy()
    background_peaks = peaks_df[peaks_df["pump_freq_hz"] == 0].copy()
    peak = compute_peak_contrast(active_peaks, background_peaks, pairs)
    acf = compute_acf_contrast(acf_df, pairs)
    contrast_tables = {"bandpower": bandpower, "peak": peak, "acf": acf}
    cross_channel = compute_cross_channel_support(contrast_tables)
    pumpfreq_net = compute_pumpfreq_net_contrast(contrast_tables)
    distance_decay = compute_distance_decay_after_background(contrast_tables)
    qc_outliers = detect_qc_outlier_channels(bandpower)
    checks = run_smoke_assertions(psd_gain, bandpower, peak, acf, cross_channel, pumpfreq_net, distance_decay)

    return {
        "psd_gain_curves": psd_gain,
        "bandpower": bandpower,
        "peak": peak,
        "acf": acf,
        "cross_channel": cross_channel,
        "pumpfreq_net": pumpfreq_net,
        "distance_decay": distance_decay,
        "qc_outliers": qc_outliers,
        "report": build_smoke_report(checks),
        "run_log": build_run_log(checks),
    }


def build_smoke_psd_curve_df():
    rows = []
    groups = [
        ("2m0hz", 2.0, 0.0, 1.0),
        ("2m30hz", 2.0, 30.0, 10.0),
        ("2m50hz", 2.0, 50.0, 50.11872336272722),
        ("3m0hz", 3.0, 0.0, 1.0),
        ("3m30hz", 3.0, 30.0, 5.0),
        ("3m50hz", 3.0, 50.0, 5.0),
        ("5m0hz", 5.0, 0.0, 1.0),
        ("5m30hz", 5.0, 30.0, 1.0),
        ("5m50hz", 5.0, 50.0, 1.0),
    ]
    freqs = np.array([0.0, 30.0, 50.0, 60.0, 100.0, 1000.0, 8500.0, 50000.0, 59500.0, 100000.0, 150000.0, 200000.0])
    channels = REAL_CHANNELS + ["ALL"]
    for group, distance, pump, high_band_mult in groups:
        for channel in channels:
            for file_idx in range(5):
                file_factor = 1.0 + 0.02 * (file_idx - 2)
                channel_factor = 1.0 + 0.005 * (0 if channel == "ALL" else int(channel.replace("channel", "")))
                for freq in freqs:
                    psd = 1e-12 * file_factor * channel_factor
                    if freq == 8500.0:
                        psd *= 100.0
                    if freq == 59500.0:
                        psd *= 100.0 * high_band_mult
                    if freq == 50000.0 and pump in {30.0, 50.0}:
                        psd *= high_band_mult
                    rows.append(_psd_row(group, distance, pump, channel, file_idx, freq, psd, 24.414))
    # Extra low-resolution and high-resolution 30Hz-target rows for reliability checks.
    for df_hz, group_suffix in [(24.414, "coarse"), (0.5, "fine")]:
        for group, distance, pump, multiplier in [("2m0hz", 2.0, 0.0, 1.0), ("2m30hz", 2.0, 30.0, 2.0)]:
            for channel in REAL_CHANNELS:
                for file_idx in range(5):
                    freqs = [28.0, 30.0, 32.0] if group_suffix == "fine" else [30.0]
                    for freq in freqs:
                        rows.append(_psd_row(f"{group}_{group_suffix}", distance, pump, channel, file_idx, freq, 1e-12 * multiplier, df_hz))
    return pd.DataFrame(rows)


def build_smoke_peaks_df():
    rows = []
    for distance in [2.0, 3.0, 5.0]:
        for pump in [0.0, 30.0, 50.0]:
            group = f"{int(distance)}m{int(pump)}hz"
            if pump == 0.0:
                peaks = [(8500.0, 1e-9, 12.0, "8.5kHz±300Hz"), (50000.0, 1e-9, 12.0, "50kHz±1kHz"), (100000.0, 1e-8, 15.0, "100kHz-200kHz")]
            elif pump == 30.0:
                peaks = [(8500.0, 1e-9, 12.0, "8.5kHz±300Hz"), (50000.0, 1e-8, 12.0, "50kHz±1kHz"), (59500.0, 1e-8, 12.0, "59.5kHz±1kHz"), (100000.0, 1e-9, 12.0, "100kHz-200kHz")]
            else:
                peaks = [(8500.0, 1e-9, 12.0, "8.5kHz±300Hz"), (50000.0, 1e-8, 12.0, "50kHz±1kHz"), (59500.0, 1e-7, 12.0, "59.5kHz±1kHz"), (100000.0, 1e-9, 12.0, "100kHz-200kHz")]
            for channel in REAL_CHANNELS + ["ALL"]:
                for rank, (freq, psd, snr, band) in enumerate(peaks, start=1):
                    rows.append({
                        "group": group,
                        "distance_m": distance,
                        "pump_freq_hz": pump,
                        "channel": channel,
                        "file_id": "group_median",
                        "peak_rank": rank,
                        "peak_freq_hz": freq,
                        "peak_psd": psd,
                        "peak_snr_dB": snr,
                        "df_hz": 24.414,
                        "band_name": band,
                        "is_smoke_test": True,
                    })
    return pd.DataFrame(rows)


def build_smoke_acf_summary_df():
    rows = []
    for distance in [2.0, 3.0, 5.0]:
        for pump in [0.0, 30.0, 50.0]:
            group = f"{int(distance)}m{int(pump)}hz"
            for channel in REAL_CHANNELS + ["ALL"]:
                for file_idx in range(5):
                    if pump == 0.0:
                        lag, acf, spacing, decay = 0.000585, 0.4, 0.0010, 0.010
                    elif pump == 30.0:
                        lag, acf, spacing, decay = 0.0001175, 0.8, 0.0007, 0.008
                    else:
                        lag, acf, spacing, decay = 0.0001000, 0.9, 0.0006, 0.007
                    rows.append({
                        "group": group,
                        "distance_m": distance,
                        "pump_freq_hz": pump,
                        "channel": channel,
                        "file_id": f"file{file_idx}",
                        "first_strong_lag_s": lag,
                        "first_strong_acf": acf,
                        "global_max_lag_s": lag,
                        "global_max_acf": acf + 0.05,
                        "peak_spacing_s": spacing,
                        "acf_decay_time_s": decay,
                        "is_smoke_test": True,
                    })
    return pd.DataFrame(rows)


def build_support_fixture(level):
    counts = {"strong": 8, "medium": 6, "weak": 3, "none": 1}
    support_count = counts[level]
    rows = []
    for idx, channel in enumerate(REAL_CHANNELS, start=1):
        supported = idx <= support_count
        rows.append({
            "distance_m": 2.0,
            "active_group": "2m30hz",
            "background_group": "2m0hz",
            "pump_freq_hz": 30.0,
            "channel": channel,
            "band_name": f"fixture_{level}",
            "band_gain_dB": 4.0 if supported else 0.0,
            "support_flag": supported,
            "quality_note": "",
        })
    rows.append({**rows[0], "channel": "ALL", "band_gain_dB": 99.0, "support_flag": True, "quality_note": ""})
    return pd.DataFrame(rows)


def run_smoke_assertions(psd_gain, bandpower, peak, acf, cross_channel, pumpfreq_net, distance_decay):
    checks = []
    gain_595 = _nearest(psd_gain, "2m30hz", "channel1", 59500.0)["psd_gain_dB"]
    gain_85 = _nearest(psd_gain, "2m30hz", "channel1", 8500.0)["psd_gain_dB"]
    checks.append(("59.5kHz gain > 8dB", gain_595 > 8.0))
    checks.append(("8.5kHz gain < 3dB", abs(gain_85) < 3.0))
    band = bandpower[(bandpower["active_group"] == "2m30hz") & (bandpower["channel"] == "channel1") & (bandpower["band_name"] == "50kHz-100kHz")].iloc[0]
    checks.append(("50k-100k band gain about 10dB", abs(band["band_gain_dB"] - 10.0) < 0.5 and bool(band["support_flag"])))
    new_peak = peak[(peak["active_group"] == "2m30hz") & (peak["channel"] == "channel1") & (peak["band_name"] == "59.5kHz±1kHz")].iloc[0]
    checks.append(("59.5kHz peak is new/enhanced supported", new_peak["peak_type"] in {"new_peak", "enhanced_peak"} and bool(new_peak["support_flag"])))
    acf_row = acf[(acf["active_group"] == "2m30hz") & (acf["channel"] == "channel1")].iloc[0]
    checks.append(("ACF change flag", bool(acf_row["acf_change_flag"]) and abs(acf_row["delta_first_strong_acf"] - 0.4) < 1e-9 and acf_row["delta_first_strong_lag_s"] < 0))
    cc = cross_channel[(cross_channel["contrast_pair"] == "2m50hz vs 2m0hz") & (cross_channel["feature_type"] == "bandpower") & (cross_channel["feature_name"] == "50kHz-100kHz")].iloc[0]
    checks.append(("cross-channel strong", cc["conclusion_level"] == "strong"))
    net = pumpfreq_net[(pumpfreq_net["distance_m"] == 2.0) & (pumpfreq_net["channel"] == "channel1") & (pumpfreq_net["feature_type"] == "bandpower") & (pumpfreq_net["feature_name"] == "50kHz-100kHz")].iloc[0]
    checks.append(("pumpfreq net contrast", abs(net["delta_50_minus_30"] - 7.0) < 0.5 and bool(net["can_distinguish_flag"])))
    decay = distance_decay[(distance_decay["pump_freq_hz"] == 30.0) & (distance_decay["feature_type"] == "bandpower") & (distance_decay["feature_name"] == "50kHz-100kHz") & (distance_decay["channel"] == "channel1")].iloc[0]
    checks.append(("distance decay monotonic", bool(decay["monotonic_decay_flag"])))
    return checks


def build_smoke_report(checks):
    lines = ["# Background Contrast v1 Smoke Report", ""]
    for name, passed in checks:
        lines.append(f"- {'PASS' if passed else 'FAIL'}: {name}")
    lines.extend([
        "",
        "Synthetic smoke data only. No real experimental group directory was read.",
        "The smoke data includes channel1-channel12 and channel=ALL; ALL is excluded from formal support counts.",
    ])
    return "\n".join(lines) + "\n"


def build_run_log(checks):
    failed = [name for name, passed in checks if not passed]
    status = "PASS" if not failed else "FAIL"
    lines = [f"status={status}", f"check_count={len(checks)}"]
    lines.extend(f"failed={name}" for name in failed)
    return "\n".join(lines) + "\n"


def _psd_row(group, distance, pump, channel, file_idx, freq, psd, df_hz):
    return {
        "group": group,
        "distance_m": distance,
        "pump_freq_hz": pump,
        "channel": channel,
        "file_id": f"file{file_idx}",
        "freq_hz": freq,
        "psd": psd,
        "df_hz": df_hz,
        "is_smoke_test": True,
    }


def _nearest(df, active_group, channel, freq):
    current = df[(df["active_group"] == active_group) & (df["channel"] == channel)].copy()
    current["error"] = (current["freq_hz"] - freq).abs()
    return current.sort_values("error").iloc[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run Background Contrast v1 synthetic smoke pipeline")
    parser.add_argument("--output", "-o", default=str(SMOKE_OUTPUT_DIR))
    args = parser.parse_args(argv)
    outputs = build_smoke_outputs()
    output_dir = export_background_contrast_smoke_outputs(outputs, args.output)
    failed = [name for name, passed in run_smoke_assertions(
        outputs["psd_gain_curves"],
        outputs["bandpower"],
        outputs["peak"],
        outputs["acf"],
        outputs["cross_channel"],
        outputs["pumpfreq_net"],
        outputs["distance_decay"],
    ) if not passed]
    print(f"Background Contrast v1 smoke output: {output_dir}")
    if failed:
        print("FAIL")
        for name in failed:
            print(f" - {name}")
        raise SystemExit(1)
    print("PASS")
    return output_dir


if __name__ == "__main__":
    main()
