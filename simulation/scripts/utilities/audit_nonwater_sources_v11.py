import csv
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "results/doorway_environment_v9_phasors.csv"
OUTPUT_DIR = ROOT / "results/nonwater_source_audit_v11"
DISTANCES = (2, 3, 4)
VECTOR_QUANTITIES = ("Ex", "Ey", "Ez")

V_LINE_RMS = 380.0
V_PHASE_RMS = V_LINE_RMS / math.sqrt(3.0)
SOURCE_RMS = {
    "pump_chassis_30hz": 1.0,
    "pump_chassis_50hz": 1.0,
    "vfd_motor_cable_30hz": 0.6 * V_PHASE_RMS,
    "vfd_motor_cable_50hz": V_PHASE_RMS,
    "wall_supply_50hz": V_PHASE_RMS,
    "vfd_pwm_4khz": 100.0,
    "vfd_pwm_8khz": 50.0,
    "vfd_pwm_12khz": 25.0,
}
FREQUENCY_HZ = {
    "pump_chassis_30hz": 30,
    "pump_chassis_50hz": 50,
    "vfd_motor_cable_30hz": 30,
    "vfd_motor_cable_50hz": 50,
    "wall_supply_50hz": 50,
    "vfd_pwm_4khz": 4000,
    "vfd_pwm_8khz": 8000,
    "vfd_pwm_12khz": 12000,
}
OPERATING_CASES = {
    30: {
        "with_pump": ("pump_chassis_30hz", "vfd_motor_cable_30hz"),
        "without_pump": ("vfd_motor_cable_30hz",),
        "cable_only": ("vfd_motor_cable_30hz",),
    },
    50: {
        "with_pump": (
            "pump_chassis_50hz",
            "vfd_motor_cable_50hz",
            "wall_supply_50hz",
        ),
        "without_pump": ("vfd_motor_cable_50hz", "wall_supply_50hz"),
        "cable_only": ("vfd_motor_cable_50hz",),
    },
}


def load_phasors():
    phasors = {}
    with INPUT.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (
                row["source_type"],
                int(row["distance_from_tank_wall_m"]),
                row["quantity"],
            )
            phasors[key] = complex(float(row["real"]), float(row["imaginary"]))
    return phasors


def sum_quantity(phasors, cases, distance, quantity):
    return sum((phasors[(case, distance, quantity)] for case in cases), 0j)


def vector_magnitude(phasors, cases, distance):
    return math.sqrt(sum(
        abs(sum_quantity(phasors, cases, distance, quantity)) ** 2
        for quantity in VECTOR_QUANTITIES
    ))


def write_no_pump_comparison(phasors):
    output = OUTPUT_DIR / "no_pump_comparison.csv"
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "operating_frequency_hz",
            "distance_from_tank_wall_m",
            "field_with_pump_V_per_m",
            "field_without_pump_V_per_m",
            "field_change_after_removing_pump_percent",
            "field_cable_only_V_per_m",
            "field_change_from_without_pump_after_removing_wall_percent",
            "sensor_axis_with_pump_V_per_m",
            "sensor_axis_without_pump_V_per_m",
            "sensor_axis_change_after_removing_pump_percent",
            "sensor_axis_cable_only_V_per_m",
            "sensor_axis_change_from_without_pump_after_removing_wall_percent",
        ])
        for frequency, selections in OPERATING_CASES.items():
            for distance in DISTANCES:
                field_with = vector_magnitude(
                    phasors, selections["with_pump"], distance
                )
                field_without = vector_magnitude(
                    phasors, selections["without_pump"], distance
                )
                field_cable_only = vector_magnitude(
                    phasors, selections["cable_only"], distance
                )
                sensor_with = abs(sum_quantity(
                    phasors, selections["with_pump"], distance, "E_sensor"
                ))
                sensor_without = abs(sum_quantity(
                    phasors, selections["without_pump"], distance, "E_sensor"
                ))
                sensor_cable_only = abs(sum_quantity(
                    phasors, selections["cable_only"], distance, "E_sensor"
                ))
                writer.writerow([
                    frequency,
                    distance,
                    field_with,
                    field_without,
                    100.0 * (field_without / field_with - 1.0),
                    field_cable_only,
                    100.0 * (field_cable_only / field_without - 1.0),
                    sensor_with,
                    sensor_without,
                    100.0 * (sensor_without / sensor_with - 1.0),
                    sensor_cable_only,
                    100.0 * (sensor_cable_only / sensor_without - 1.0),
                ])
    return output


def write_source_transfer_coefficients(phasors):
    output = OUTPUT_DIR / "source_transfer_coefficients.csv"
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "source_case",
            "frequency_hz",
            "reference_excitation_V_rms",
            "distance_from_tank_wall_m",
            "model_field_V_per_m",
            "field_transfer_per_V_source_1_per_m",
            "model_sensor_axis_V_per_m",
            "sensor_transfer_per_V_source_1_per_m",
        ])
        for source_case, source_rms in SOURCE_RMS.items():
            for distance in DISTANCES:
                field = vector_magnitude(phasors, (source_case,), distance)
                sensor = abs(phasors[(source_case, distance, "E_sensor")])
                writer.writerow([
                    source_case,
                    FREQUENCY_HZ[source_case],
                    source_rms,
                    distance,
                    field,
                    field / source_rms,
                    sensor,
                    sensor / source_rms,
                ])
    return output


def write_assumption_register():
    output = OUTPUT_DIR / "uncertain_parameter_register.csv"
    rows = [
        (
            "pump chassis source",
            "1 V RMS applied to the entire pump chassis at 30/50 Hz",
            "unmeasured reference excitation",
            "high",
            "omit from the nominal model; retain only as a per-volt sensitivity case",
            "measure chassis-to-PE voltage spectrum or PE current and PE impedance",
        ),
        (
            "motor cable geometry",
            "three bare straight 8 mm-radius phase conductors; no PE, jacket, shield, or twist",
            "likely weakens phase cancellation and can overestimate the far electric field",
            "high",
            "replace with the actual multicore cross-section and route",
            "cable marking, core area, outer diameter, PE core, shield/armor and grounding",
        ),
        (
            "motor fundamental excitation",
            "131.6 V RMS at 30 Hz and 219.4 V RMS at 50 Hz phase-to-ground",
            "V/f assumption; terminal spectrum and common-mode component are unmeasured",
            "medium-high",
            "solve a unit-voltage transfer model and scale with measured line-to-PE FFT",
            "motor-terminal phase-to-PE voltage spectrum at 30 and 50 Hz operating points",
        ),
        (
            "PWM common-mode excitation",
            "100/50/25 V RMS at 4/8/12 kHz, identical phase on all three cores",
            "assumed amplitudes dominate the reported high-frequency field",
            "very high",
            "report only per-volt transfer until measured; then scale by measured common-mode FFT",
            "actual switching frequency and common-mode line-to-PE RMS spectrum",
        ),
        (
            "wall supply route",
            "three 3 cm conductor stubs next to the supply enclosure",
            "not a representation of the real in-wall cable route; bias direction is unknown",
            "high",
            "exclude from source attribution or replace with measured background/actual route",
            "route, burial depth, conduit, phase bundling, PE and nearby rebar",
        ),
        (
            "metal frame grounding",
            "all aluminum-frame surfaces fixed at ideal 0 V",
            "may over-shield the observation region and underestimate field",
            "medium-high",
            "run grounded, floating and finite-ground-impedance sensitivity cases",
            "frame-to-building-PE continuity and impedance",
        ),
        (
            "outer air boundary",
            "5 m radius domain with electric insulation boundary",
            "the 4 m point is only about 0.72 m from the side boundary",
            "high",
            "perform 5/7.5/10 m domain convergence or add an infinite-element domain",
            "no new experiment required",
        ),
        (
            "MEMS conversion",
            "point electric field with unit field-to-voltage coefficient",
            "cannot predict measured voltage without sensor/package/reference coupling",
            "very high",
            "separate environmental field from sensor transfer and calibrate the latter",
            "sensor orientation, package, input capacitance, ground/reference and calibration factor",
        ),
    ]
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "item",
            "current_model_assumption",
            "risk_or_bias",
            "uncertainty",
            "recommended_conservative_treatment",
            "required_information",
        ])
        writer.writerows(rows)
    return output


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    phasors = load_phasors()
    outputs = (
        write_no_pump_comparison(phasors),
        write_source_transfer_coefficients(phasors),
        write_assumption_register(),
    )
    for output in outputs:
        print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
