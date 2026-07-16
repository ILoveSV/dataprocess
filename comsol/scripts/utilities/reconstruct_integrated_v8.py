import csv
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "results" / "integrated_sources_v8_phasors.csv"
SAMPLE_RATE_HZ = 100_000
DURATION_S = 0.2
DISTANCES = (2, 3, 4)
QUANTITIES = ("Ex", "Ey", "Ez", "E_sensor")
PWM_CASES = ("vfd_pwm_4khz", "vfd_pwm_8khz", "vfd_pwm_12khz")


def load_phasors():
    phasors = {}
    with INPUT.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (row["source_type"], int(row["distance_m"]), row["quantity"])
            phasors[key] = complex(float(row["real"]), float(row["imaginary"]))
    return phasors


def reconstruct(operating_hz, phasors):
    operating_case = f"combined_{operating_hz}hz"
    cases = ((operating_case, operating_hz),) + tuple(
        (case, frequency) for case, frequency in zip(PWM_CASES, (4000, 8000, 12000))
    )
    output = ROOT / "results" / f"integrated_sources_v8_time_{operating_hz}hz.csv"
    sample_count = round(SAMPLE_RATE_HZ * DURATION_S)

    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["time_s", "distance_m", "Ex_V_per_m", "Ey_V_per_m", "Ez_V_per_m",
             "normE_V_per_m", "E_sensor_V_per_m"]
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
                writer.writerow(
                    [time_s, distance, values["Ex"], values["Ey"], values["Ez"],
                     norm_e, values["E_sensor"]]
                )
    return output, sample_count * len(DISTANCES)


def main():
    phasors = load_phasors()
    for operating_hz in (30, 50):
        output, rows = reconstruct(operating_hz, phasors)
        print(f"{output.name}: {rows} rows")


if __name__ == "__main__":
    main()
