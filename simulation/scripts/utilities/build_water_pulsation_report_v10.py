"""Combine V10 hydraulic harmonics with the COMSOL external-field transfer."""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
RESULT_DIR = ROOT / "results/pulsation_v10"
TRANSFER_LOG = ROOT / "build" / "hydraulic_pulse_transfer_v10_stdout.log"
HYDRAULIC_HARMONICS = RESULT_DIR / "hydraulic_harmonics.csv"
HYDRAULIC_CASES = RESULT_DIR / "hydraulic_case_summary.csv"
OLD_SUMMARY = ROOT / "results/doorway_environment_v9_summary.csv"

TRANSFER_CSV = RESULT_DIR / "external_unit_current_transfer.csv"
FIELD_HARMONICS_CSV = RESULT_DIR / "external_field_harmonics.csv"
FIELD_CASES_CSV = RESULT_DIR / "external_field_case_summary.csv"
COMPARISON_CSV = RESULT_DIR / "old_5percent_comparison.csv"
PLOT_FILE = RESULT_DIR / "water_pulsation_field_scan.png"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def parse_transfer_log() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with TRANSFER_LOG.open("r", encoding="utf-16", errors="replace") as handle:
        for line in handle:
            marker = line.find("PULSE_TRANSFER,")
            if marker < 0:
                continue
            values = line[marker:].strip().split(",")
            if len(values) != 8:
                continue
            rows.append(
                {
                    "harmonic": int(values[1]),
                    "frequency_hz": float(values[2]),
                    "distance_from_tank_wall_m": int(values[3]),
                    "quantity": values[4],
                    "real_per_amp": float(values[5]),
                    "imaginary_per_amp": float(values[6]),
                    "magnitude_per_amp": float(values[7]),
                }
            )
    if len(rows) != 10 * 3 * 7:
        raise ValueError(f"Expected 210 transfer rows, found {len(rows)}")
    return rows


def confidence(repeatability: float) -> str:
    if repeatability <= 0.03:
        return "high"
    if repeatability <= 0.10:
        return "medium"
    return "low"


def main() -> None:
    transfer_rows = parse_transfer_log()
    write_csv(TRANSFER_CSV, transfer_rows)
    transfer = {
        (
            int(row["harmonic"]),
            int(row["distance_from_tank_wall_m"]),
            str(row["quantity"]),
        ): row
        for row in transfer_rows
    }

    hydraulic_harmonics = read_csv(HYDRAULIC_HARMONICS)
    hydraulic_cases = {
        (int(float(row["operating_mode_hz"])), float(row["velocity_amplitude_A"])): row
        for row in read_csv(HYDRAULIC_CASES)
    }

    old_fields: dict[tuple[int, int], dict[str, float]] = {}
    for row in read_csv(OLD_SUMMARY):
        if not row["source_type"].startswith("water_flow_"):
            continue
        key = (int(row["frequency_hz"]), int(row["distance_from_tank_wall_m"]))
        old_fields[key] = {
            "norm": float(row["normE_V_per_m"]),
            "sensor": float(row["sensor_axis_E_V_per_m"]),
        }

    field_harmonics: list[dict[str, object]] = []
    for item in hydraulic_harmonics:
        mode = int(float(item["operating_mode_hz"]))
        amplitude = float(item["velocity_amplitude_A"])
        harmonic = int(item["harmonic"])
        current_rms = float(item["streaming_current_rms_a"])
        for distance in (2, 3, 4):
            vector_squared = 0.0
            for quantity in ("Ex", "Ey", "Ez"):
                gain = transfer[(harmonic, distance, quantity)]
                vector_squared += float(gain["magnitude_per_amp"]) ** 2
            vector_gain = math.sqrt(vector_squared)
            sensor_gain = float(transfer[(harmonic, distance, "E_sensor")]["magnitude_per_amp"])
            field_harmonics.append(
                {
                    "operating_mode_hz": mode,
                    "velocity_amplitude_A": amplitude,
                    "harmonic": harmonic,
                    "frequency_hz": float(item["frequency_hz"]),
                    "distance_from_tank_wall_m": distance,
                    "streaming_current_rms_a": current_rms,
                    "vector_field_rms_v_per_m": vector_gain * current_rms,
                    "sensor_axis_field_rms_v_per_m": sensor_gain * current_rms,
                }
            )
    write_csv(FIELD_HARMONICS_CSV, field_harmonics)

    grouped: dict[tuple[int, float, int], list[dict[str, object]]] = defaultdict(list)
    for row in field_harmonics:
        grouped[
            (
                int(row["operating_mode_hz"]),
                float(row["velocity_amplitude_A"]),
                int(row["distance_from_tank_wall_m"]),
            )
        ].append(row)

    field_cases: list[dict[str, object]] = []
    comparisons: list[dict[str, object]] = []
    for (mode, amplitude, distance), harmonics in sorted(grouped.items()):
        harmonics.sort(key=lambda row: int(row["harmonic"]))
        hydraulic = hydraulic_cases[(mode, amplitude)]
        repeatability = float(hydraulic["pressure_repeatability_fraction"])
        vector_total = math.sqrt(
            sum(float(row["vector_field_rms_v_per_m"]) ** 2 for row in harmonics)
        )
        sensor_total = math.sqrt(
            sum(float(row["sensor_axis_field_rms_v_per_m"]) ** 2 for row in harmonics)
        )
        old = old_fields[(mode, distance)]
        field_cases.append(
            {
                "operating_mode_hz": mode,
                "velocity_amplitude_A": amplitude,
                "hydraulic_frequency_hz": harmonics[0]["frequency_hz"],
                "distance_from_tank_wall_m": distance,
                "mean_velocity_m_per_s": float(hydraulic["mean_velocity_m_s"]),
                "mean_pressure_pa": float(hydraulic["mean_pressure_pa"]),
                "fundamental_pressure_rms_pa": float(hydraulic["fundamental_pressure_rms_pa"]),
                "fundamental_streaming_current_rms_a": float(
                    hydraulic["fundamental_streaming_current_rms_a"]
                ),
                "fundamental_vector_field_rms_v_per_m": harmonics[0][
                    "vector_field_rms_v_per_m"
                ],
                "total_10_harmonic_vector_field_rms_v_per_m": vector_total,
                "fundamental_sensor_axis_field_rms_v_per_m": harmonics[0][
                    "sensor_axis_field_rms_v_per_m"
                ],
                "total_10_harmonic_sensor_axis_field_rms_v_per_m": sensor_total,
                "cycle_repeatability_fraction": repeatability,
                "confidence": confidence(repeatability),
            }
        )
        comparisons.append(
            {
                "operating_mode_hz": mode,
                "velocity_amplitude_A": amplitude,
                "distance_from_tank_wall_m": distance,
                "new_hydraulic_frequency_hz": harmonics[0]["frequency_hz"],
                "new_total_vector_field_rms_v_per_m": vector_total,
                "old_fixed_5percent_frequency_hz": mode,
                "old_fixed_5percent_vector_field_v_per_m": old["norm"],
                "new_to_old_vector_ratio": vector_total / old["norm"],
                "new_total_sensor_axis_field_rms_v_per_m": sensor_total,
                "old_fixed_5percent_sensor_axis_field_v_per_m": old["sensor"],
                "new_to_old_sensor_ratio": sensor_total / old["sensor"],
            }
        )
    write_csv(FIELD_CASES_CSV, field_cases)
    write_csv(COMPARISON_CSV, comparisons)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
    colors = {2: "#1565c0", 3: "#2e7d32", 4: "#c62828"}
    for axis, mode in zip(axes, (30, 50)):
        for distance in (2, 3, 4):
            selected = [
                row for row in field_cases
                if row["operating_mode_hz"] == mode
                and row["distance_from_tank_wall_m"] == distance
            ]
            axis.plot(
                [100 * float(row["velocity_amplitude_A"]) for row in selected],
                [float(row["total_10_harmonic_vector_field_rms_v_per_m"]) for row in selected],
                marker="o",
                linewidth=1.8,
                color=colors[distance],
                label=f"{distance} m",
            )
            axis.axhline(
                old_fields[(mode, distance)]["norm"],
                color=colors[distance],
                linestyle="--",
                linewidth=0.9,
                alpha=0.55,
            )
        axis.set_title(f"VFD operating mode: {mode} Hz")
        axis.set_xlabel("Velocity modulation A (%)")
        axis.set_yscale("log")
        axis.grid(True, which="both", alpha=0.25)
    axes[0].set_ylabel("Water-source electric field RMS (V/m)")
    axes[1].legend(title="From tank wall")
    fig.suptitle("3.1 s hydraulic pulse parameter scan (solid) vs old fixed-5% model (dashed)")
    fig.tight_layout()
    fig.savefig(PLOT_FILE, dpi=180)
    plt.close(fig)

    print(f"TRANSFER_ROWS={len(transfer_rows)}")
    print(f"FIELD_CASE_ROWS={len(field_cases)}")
    print(f"PLOT={PLOT_FILE}")


if __name__ == "__main__":
    main()
