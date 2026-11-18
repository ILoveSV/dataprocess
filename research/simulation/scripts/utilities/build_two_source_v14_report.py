from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "build" / "two_source_v14_stdout.log"
OUTPUT = ROOT / "results/two_source_v14"
V13_SUMMARY = ROOT / "results/minimal_electric_v13/minimal_electric_v13_summary.csv"


def marker_rows(marker: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in LOG.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(marker + ","):
            rows.append(line.split(",")[1:])
    return rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)

    electric: list[dict[str, object]] = []
    for row in marker_rows("V14_E_SUMMARY"):
        electric.append(
            {
                "case": row[0],
                "mode": row[1],
                "frequency_hz": int(row[2]),
                "source_rms_v": float(row[3]),
                "distance_m": int(row[4]),
                "electric_field_v_per_m": float(row[5]),
                "sensor_axis_field_v_per_m": float(row[6]),
            }
        )

    with V13_SUMMARY.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            old_case = row["source_type"]
            if old_case.startswith("motor_differential_"):
                case = old_case.replace("motor_differential_", "cable_differential_")
                mode = "balanced_differential"
            elif old_case.startswith("cable_common_mode_"):
                case = old_case
                mode = "normalized_cable_common_mode"
            else:
                continue
            electric.append(
                {
                    "case": case,
                    "mode": mode,
                    "frequency_hz": int(row["frequency_hz"]),
                    "source_rms_v": float(row["source_voltage_rms_V"]),
                    "distance_m": int(row["distance_from_tank_wall_m"]),
                    "electric_field_v_per_m": float(row["normE_V_per_m"]),
                    "sensor_axis_field_v_per_m": float(row["sensor_axis_E_V_per_m"]),
                }
            )

    magnetic: list[dict[str, object]] = []
    for row in marker_rows("V14_M_SUMMARY"):
        magnetic.append(
            {
                "case": row[0],
                "mode": row[1],
                "frequency_hz": int(row[2]),
                "source_rms_a": float(row[3]),
                "distance_m": int(row[4]),
                "magnetic_flux_density_t": float(row[5]),
                "induced_electric_field_v_per_m": float(row[6]),
            }
        )

    if not electric or not magnetic:
        raise RuntimeError("V14 markers are incomplete; check the COMSOL stdout log")

    write_csv(
        OUTPUT / "two_source_v14_electric_summary.csv",
        list(electric[0]),
        electric,
    )
    write_csv(
        OUTPUT / "two_source_v14_magnetic_summary.csv",
        list(magnetic[0]),
        magnetic,
    )

    comparison: list[dict[str, object]] = []
    lookup = {(r["case"], r["distance_m"]): r for r in electric}
    for frequency in (4000, 12000, 100000, 200000):
        suffix = f"{frequency // 1000}khz"
        cable_case = f"cable_common_mode_{suffix}"
        chassis_case = f"motor_pump_chassis_{suffix}"
        for distance in (2, 3, 4):
            cable = float(lookup[(cable_case, distance)]["electric_field_v_per_m"])
            chassis = float(lookup[(chassis_case, distance)]["electric_field_v_per_m"])
            comparison.append(
                {
                    "frequency_hz": frequency,
                    "distance_m": distance,
                    "cable_field_per_1v_v_per_m": cable,
                    "chassis_field_per_1v_v_per_m": chassis,
                    "chassis_to_cable_ratio": chassis / cable,
                }
            )
    write_csv(
        OUTPUT / "two_source_v14_unit_voltage_comparison.csv",
        list(comparison[0]),
        comparison,
    )

    quality: list[dict[str, object]] = []
    for rows, value_key, family in (
        (electric, "electric_field_v_per_m", "electric"),
        (magnetic, "magnetic_flux_density_t", "magnetic"),
        (magnetic, "induced_electric_field_v_per_m", "induced_electric"),
    ):
        cases = sorted({str(row["case"]) for row in rows})
        for case in cases:
            values = {
                int(row["distance_m"]): float(row[value_key])
                for row in rows
                if row["case"] == case
            }
            quality.append(
                {
                    "family": family,
                    "case": case,
                    "finite": all(value == value and abs(value) != float("inf") for value in values.values()),
                    "monotonic_2m_gt_3m_gt_4m": values[2] > values[3] > values[4],
                    "ratio_3m_to_2m": values[3] / values[2],
                    "ratio_4m_to_2m": values[4] / values[2],
                }
            )
    write_csv(OUTPUT / "two_source_v14_quality_checks.csv", list(quality[0]), quality)

    plot_frequencies = (4000, 12000, 100000, 200000)
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.4), sharey=True)
    for axis, distance in zip(axes, (2, 3, 4)):
        cable_values = []
        chassis_values = []
        for frequency in plot_frequencies:
            suffix = f"{frequency // 1000}khz"
            cable_values.append(
                float(lookup[(f"cable_common_mode_{suffix}", distance)]["electric_field_v_per_m"])
            )
            chassis_values.append(
                float(lookup[(f"motor_pump_chassis_{suffix}", distance)]["electric_field_v_per_m"])
            )
        axis.loglog(plot_frequencies, cable_values, "o-", label="Motor cable common mode")
        axis.loglog(plot_frequencies, chassis_values, "s-", label="Motor/pump chassis")
        axis.set_title(f"{distance} m from tank wall")
        axis.set_xlabel("Frequency (Hz)")
        axis.grid(True, which="both", alpha=0.25)
    axes[0].set_ylabel("Electric field per 1 V RMS (V/m)")
    axes[0].legend(frameon=False)
    fig.suptitle("V14 normalized electric coupling comparison")
    fig.tight_layout()
    fig.savefig(OUTPUT / "two_source_v14_unit_voltage_comparison.png", dpi=180)
    plt.close(fig)

    print(f"V14_REPORT,{len(electric)},{len(magnetic)},{OUTPUT}")


if __name__ == "__main__":
    main()
