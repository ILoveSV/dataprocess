import csv
import math
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_ROOT = ROOT.parent / "results" / "experiment_20260617" / "exact_archive"
COMSOL_PHASORS = ROOT / "results" / "doorway_environment_v9_phasors.csv"
OUTPUT_DIR = ROOT / "results" / "nonwater_source_audit_v12"
DISTANCES = (2, 3, 4)
CONDITIONS = (30, 50)
FREQUENCY_BANDS = {
    "5_100hz": (5.0, 100.0),
    "100_1khz": (100.0, 1_000.0),
    "1_20khz": (1_000.0, 20_000.0),
    "20_80khz": (20_000.0, 80_000.0),
    "80_200khz": (80_000.0, 200_000.0),
}
VECTOR_QUANTITIES = ("Ex", "Ey", "Ez")


def find_archive(distance, condition):
    matches = sorted(ARCHIVE_ROOT.glob(f"{distance}m_{condition}hz__*"))
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one archive for {distance} m, {condition} Hz; found {len(matches)}"
        )
    return matches[0]


def load_psd(distance, condition):
    archive = find_archive(distance, condition)
    with np.load(archive / "welch.npz") as data:
        return data["frequency_hz"].copy(), data["psd_mean"].copy()


def integrate_psd(frequency, psd, low_hz, high_hz):
    mask = (frequency >= low_hz) & (frequency <= high_hz)
    if np.count_nonzero(mask) < 2:
        raise RuntimeError(f"Insufficient bins in {low_hz}-{high_hz} Hz")
    return np.trapz(psd[:, mask], frequency[mask], axis=1)


def matched_power_statistics(active_power, background_power):
    tiny = np.finfo(float).tiny
    contrast_db = 10.0 * np.log10(
        np.maximum(active_power, tiny) / np.maximum(background_power, tiny)
    )
    net_power = np.maximum(active_power - background_power, 0.0)
    return {
        "active_rms_median_V": float(np.median(np.sqrt(active_power))),
        "background_rms_median_V": float(np.median(np.sqrt(background_power))),
        "contrast_median_db": float(np.median(contrast_db)),
        "contrast_q25_db": float(np.quantile(contrast_db, 0.25)),
        "contrast_q75_db": float(np.quantile(contrast_db, 0.75)),
        "positive_channel_fraction": float(np.mean(active_power > background_power)),
        "background_subtracted_rms_median_V": float(np.median(np.sqrt(net_power))),
    }


def write_experimental_distance_summary():
    output = OUTPUT_DIR / "experimental_distance_spectral_summary.csv"
    fieldnames = [
        "distance_label_m",
        "condition_hz",
        "metric",
        "frequency_low_hz",
        "frequency_high_hz",
        "active_rms_median_V",
        "background_rms_median_V",
        "contrast_median_db",
        "contrast_q25_db",
        "contrast_q75_db",
        "positive_channel_fraction",
        "background_subtracted_rms_median_V",
        "comparison_scope",
    ]
    rows = []
    for distance in DISTANCES:
        frequency_bg, psd_bg = load_psd(distance, 0)
        for condition in CONDITIONS:
            frequency, psd = load_psd(distance, condition)
            if not np.array_equal(frequency, frequency_bg):
                raise RuntimeError("Active and background frequency grids differ")

            intervals = dict(FREQUENCY_BANDS)
            intervals[f"tone_{condition}hz"] = (
                condition - 3.1,
                condition + 3.1,
            )
            for metric, (low_hz, high_hz) in intervals.items():
                active_power = integrate_psd(frequency, psd, low_hz, high_hz)
                background_power = integrate_psd(
                    frequency_bg, psd_bg, low_hz, high_hz
                )
                row = {
                    "distance_label_m": distance,
                    "condition_hz": condition,
                    "metric": metric,
                    "frequency_low_hz": low_hz,
                    "frequency_high_hz": high_hz,
                    **matched_power_statistics(active_power, background_power),
                    "comparison_scope": (
                        "sensor output voltage; sequential active/background files; "
                        "not calibrated to V/m"
                    ),
                }
                rows.append(row)

    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return output, rows


def load_comsol_phasors():
    phasors = {}
    with COMSOL_PHASORS.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (
                row["source_type"],
                int(row["distance_from_tank_wall_m"]),
                row["quantity"],
            )
            phasors[key] = complex(float(row["real"]), float(row["imaginary"]))
    return phasors


def vector_magnitude(phasors, source_case, distance):
    return math.sqrt(sum(
        abs(phasors[(source_case, distance, quantity)]) ** 2
        for quantity in VECTOR_QUANTITIES
    ))


def write_low_frequency_trend_comparison(experimental_rows):
    phasors = load_comsol_phasors()
    experimental_tones = {
        (int(row["condition_hz"]), int(row["distance_label_m"])): row
        for row in experimental_rows
        if row["metric"].startswith("tone_")
    }
    output = OUTPUT_DIR / "low_frequency_distance_trend_comparison.csv"
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "condition_hz",
            "distance_label_m",
            "comsol_cable_only_field_V_per_m",
            "comsol_field_ratio_to_2m",
            "experiment_tone_contrast_median_db",
            "experiment_tone_positive_channel_fraction",
            "experiment_background_subtracted_tone_rms_median_V",
            "experiment_net_tone_ratio_to_2m",
            "direct_absolute_comparison_allowed",
        ])
        for condition in CONDITIONS:
            source_case = f"vfd_motor_cable_{condition}hz"
            comsol_2m = vector_magnitude(phasors, source_case, 2)
            experiment_2m = experimental_tones[(condition, 2)][
                "background_subtracted_rms_median_V"
            ]
            for distance in DISTANCES:
                comsol_field = vector_magnitude(phasors, source_case, distance)
                experiment = experimental_tones[(condition, distance)]
                experiment_net = experiment["background_subtracted_rms_median_V"]
                ratio = experiment_net / experiment_2m if experiment_2m > 0.0 else math.nan
                writer.writerow([
                    condition,
                    distance,
                    comsol_field,
                    comsol_field / comsol_2m,
                    experiment["contrast_median_db"],
                    experiment["positive_channel_fraction"],
                    experiment_net,
                    ratio,
                    False,
                ])
    return output


def write_vfd_carrier_evidence():
    source = ROOT.parent / "results" / "experiment_20260806" / "vfd_band_contrasts.csv"
    output = OUTPUT_DIR / "vfd_carrier_run_stop_evidence.csv"
    kept = []
    with source.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if row["band"] in {"1_20khz", "20_80khz", "80_200khz"}:
                kept.append({
                    "detector": row["detector"],
                    "carrier_khz": row["carrier_khz"],
                    "output_hz": row["output_hz"],
                    "band": row["band"],
                    "median_run_minus_stop_db": row["median_contrast_vfd_stop_db"],
                    "positive_channel_fraction": row[
                        "positive_vs_stop_channel_fraction"
                    ],
                    "interpretation": (
                        "RUN-chain evidence only; not calibrated to V/m and not unique "
                        "attribution to the configured carrier"
                    ),
                })
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=kept[0].keys())
        writer.writeheader()
        writer.writerows(kept)
    return output


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    experimental_output, experimental_rows = write_experimental_distance_summary()
    outputs = (
        experimental_output,
        write_low_frequency_trend_comparison(experimental_rows),
        write_vfd_carrier_evidence(),
    )
    for output in outputs:
        print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
