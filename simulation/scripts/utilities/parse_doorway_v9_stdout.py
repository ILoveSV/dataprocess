import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT.parent / "logs" / "doorway_environment_v9_stdout.log"
RESULTS = ROOT / "results"


def records(prefix):
    with LOG.open(encoding="utf-16", errors="ignore") as handle:
        for line in handle:
            marker = line.find(prefix + ",")
            if marker >= 0:
                yield line[marker:].strip().split(",")[1:]


def write_csv(name, header, rows):
    output = RESULTS / name
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"{output.name}: {len(rows)} rows")


def main():
    write_csv(
        "doorway_environment_v9_phasors.csv",
        ["case_index", "source_type", "source_category", "frequency_hz",
         "distance_from_tank_wall_m", "quantity", "real", "imaginary", "magnitude"],
        list(records("PHASOR")),
    )
    write_csv(
        "doorway_environment_v9_summary.csv",
        ["source_type", "source_category", "frequency_hz", "distance_from_tank_wall_m",
         "normE_V_per_m", "sensor_axis_E_V_per_m"],
        list(records("CASE_SUMMARY")),
    )
    write_csv(
        "doorway_environment_v9_superposition.csv",
        ["frequency_hz", "distance_from_tank_wall_m", "relative_residual"],
        list(records("SUPERPOSITION")),
    )


if __name__ == "__main__":
    main()
