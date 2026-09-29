import csv
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "results" / "doorway_environment_v9_phasors.csv"
SAMPLE_RATE_HZ = 100_000
DURATION_S = 0.2
DISTANCES = (2, 3, 4)
QUANTITIES = ("Ex", "Ey", "Ez", "E_sensor")
PWM_CASES = ("vfd_pwm_4khz", "vfd_pwm_8khz", "vfd_pwm_12khz")
OPERATING_CASES = {
    30: (
        ("water_flow_30hz", 30),
        ("pump_chassis_30hz", 30),
        ("vfd_motor_cable_30hz", 30),
        ("wall_supply_50hz", 50),
    ),
    50: (
        ("water_flow_50hz", 50),
        ("pump_chassis_50hz", 50),
        ("vfd_motor_cable_50hz", 50),
        ("wall_supply_50hz", 50),
    ),
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


def reconstruct(operating_hz, phasors):
    cases = OPERATING_CASES[operating_hz] + tuple(
        (case, frequency) for case, frequency in zip(PWM_CASES, (4000, 8000, 12000))
    )
    output = ROOT / "results" / f"doorway_environment_v9_time_{operating_hz}hz.csv"
    sample_count = round(SAMPLE_RATE_HZ * DURATION_S)
    sensor_squares = {distance: 0.0 for distance in DISTANCES}

    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["time_s", "distance_from_tank_wall_m", "Ex_V_per_m", "Ey_V_per_m",
             "Ez_V_per_m", "normE_V_per_m", "E_sensor_V_per_m"]
        )
        for sample in range(sample_count):
            time_s = sample / SAMPLE_RATE_HZ
            for distance in DISTANCES:
                values = {}
                for quantity in QUANTITIES:
                    instantaneous = 0.0
                    for case, frequency in cases:
                        phasor = phasors[(case, distance, quantity)]
                        angle = 2.0 * math.pi * frequency * time_s
                        instantaneous += math.sqrt(2.0) * (
                            phasor.real * math.cos(angle) - phasor.imag * math.sin(angle)
                        )
                    values[quantity] = instantaneous
                norm_e = math.sqrt(values["Ex"] ** 2 + values["Ey"] ** 2 + values["Ez"] ** 2)
                sensor_squares[distance] += values["E_sensor"] ** 2
                writer.writerow(
                    [time_s, distance, values["Ex"], values["Ey"], values["Ez"],
                     norm_e, values["E_sensor"]]
                )

    checks = []
    for distance in DISTANCES:
        time_rms = math.sqrt(sensor_squares[distance] / sample_count)
        coherent_by_frequency = {}
        for case, frequency in cases:
            coherent_by_frequency[frequency] = (
                coherent_by_frequency.get(frequency, 0j)
                + phasors[(case, distance, "E_sensor")]
            )
        frequency_rss = math.sqrt(sum(
            abs(phasor) ** 2 for phasor in coherent_by_frequency.values()
        ))
        relative_error = abs(time_rms - frequency_rss) / frequency_rss
        checks.append((operating_hz, distance, time_rms, frequency_rss, relative_error))
    return output, sample_count * len(DISTANCES), checks


def main():
    phasors = load_phasors()
    all_checks = []
    for operating_hz in (30, 50):
        output, rows, checks = reconstruct(operating_hz, phasors)
        all_checks.extend(checks)
        print(f"{output.name}: {rows} rows")

    check_file = ROOT / "results" / "doorway_environment_v9_time_rms_check.csv"
    with check_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["operating_hz", "distance_from_tank_wall_m", "time_rms_V_per_m",
             "frequency_rss_V_per_m", "relative_error"]
        )
        writer.writerows(all_checks)
    print(f"{check_file.name}: {len(all_checks)} rows")


if __name__ == "__main__":
    main()
