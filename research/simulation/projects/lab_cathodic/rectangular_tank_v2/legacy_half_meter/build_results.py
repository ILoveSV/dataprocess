import csv
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIM = HERE.parents[3]
DIST = (0.5, 2, 3, 4)
HIGH = (4000, 8000, 12000, 20000, 50000, 80000, 100000, 120000, 150000, 200000)
ALL = (30, 50, *HIGH)


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(name, header, rows):
    with (HERE / name).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


log = (HERE / "half_meter_stdout.log").read_text(encoding="utf-8-sig").splitlines()
if "HALF_METER_COMPLETED" not in log:
    log.extend((HERE / "half_meter_pe_stdout.log").read_text(encoding="utf-8-sig").splitlines())
assert "HALF_METER_COMPLETED" in log, "Solver did not finish all cases"
data = {}
for line in log:
    if not line.startswith("HM_ROW,"):
        continue
    _, source, *values = next(csv.reader([line]))
    f, drive, d, e, b, domain = map(float, values)
    key = (source, f, d)
    assert key not in data and all(math.isfinite(x) for x in (e, b, domain))
    assert e > 0 and domain > 0
    data[key] = (drive, e, b, int(domain))
expected = {
    "round_v4_unit": (0.001,), "diff30": (30,), "diff50": (50,),
    "cable_cm": HIGH, "chassis_cm": ALL, "pe_loop": ALL,
}
assert set(data) == {(s, f, d) for s, fs in expected.items() for f in fs for d in DIST}


def get_e(source, f, d):
    return data[source, f, d][1]


def check(group, source, frequency, distance, old, new):
    delta = abs(new / old - 1)
    checks.append((group, source, frequency, distance, old, new, delta))
    return delta


old_round_dir = SIM / "results/cathodic_protection_external_field_v4"
old_round = read_csv(old_round_dir / "measured_voltage_scaled_field.csv")
old_v13 = read_csv(SIM / "results/minimal_electric_v13/minimal_electric_v13_summary.csv")
old_v14 = read_csv(SIM / "results/two_source_v14/two_source_v14_electric_summary.csv")
old_m = read_csv(SIM / "results/two_source_v14/two_source_v14_magnetic_summary.csv")
checks = []
round_rows = []
for old in old_round:
    v = float(old["measured_voltage_V"])
    far = [float(old[f"field_{d}m_V_per_m"]) for d in DIST[1:]]
    round_rows.append((float(old["current_A"]), v, v * get_e("round_v4_unit", .001, .5), *far))
    for d, e in zip(DIST[1:], far):
        check("round_v4", "round_v4_scaled", .001, d, e, v * get_e("round_v4_unit", .001, d))

groups = {}
for name, old_rows, mode_key, field_key, distance_key, drive_key in (
    ("v13", old_v13, "excitation_mode", "normE_V_per_m", "distance_from_tank_wall_m", "source_voltage_rms_V"),
    ("v14", old_v14, "mode", "electric_field_v_per_m", "distance_m", "source_rms_v"),
):
    indexed = {}
    for old in old_rows:
        f, d, voltage = map(float, (old["frequency_hz"], old[distance_key], old[drive_key]))
        s = ("diff30" if f == 30 else "diff50") if old[mode_key] == "balanced_differential" else (
            "chassis_cm" if old[mode_key] == "normalized_chassis_common_mode" else "cable_cm")
        e = float(old[field_key])
        indexed.setdefault((s, f, voltage), {})[d] = e
        check(name, s, f, d, e, get_e(s, f, d))
    groups[name] = [(s, f, v, get_e(s, f, .5), *(far[d] for d in DIST[1:]))
                    for (s, f, v), far in indexed.items()]

mag = {}
for old in old_m:
    f, d = float(old["frequency_hz"]), float(old["distance_m"])
    e = float(old["induced_electric_field_v_per_m"])
    b = float(old["magnetic_flux_density_t"])
    mag.setdefault(f, {})[d] = (e, b)
    check("v14_pe_E", "pe_loop", f, d, e, get_e("pe_loop", f, d))
    check("v14_pe_B", "pe_loop", f, d, b, data["pe_loop", f, d][2])

maxima = {g: max(r[-1] for r in checks if r[0] == g) for g in {r[0] for r in checks}}
print("Old-point reproduction (max fractional difference):", maxima)
assert max(maxima.values()) < 0.05, "Old-point mismatch exceeds 5%; inspect model before publishing"

cols = ["field_0p5m_V_per_m", "field_2m_V_per_m", "field_3m_V_per_m", "field_4m_V_per_m"]
write_csv("legacy_solver_fields.csv", ("source", "frequency_hz", "distance_m", "excitation",
                                     "field_v_per_m", "magnetic_flux_density_t", "air_domain"),
          [(*k, *v) for k, v in sorted(data.items())])
write_csv("round_v4_with_0p5m.csv", ("current_A", "measured_voltage_V", *cols), round_rows)
for name, rows in groups.items():
    write_csv(f"{name}_electric_with_0p5m.csv", ("source", "frequency_hz", "source_rms_v", *cols), rows)
write_csv("v14_pe_with_0p5m.csv", ("frequency_hz", "source_rms_a", *cols,
          "B_0p5m_T", "B_2m_T", "B_3m_T", "B_4m_T"),
          [(f, 1, get_e("pe_loop", f, .5), *(mag[f][d][0] for d in DIST[1:]),
            data["pe_loop", f, .5][2], *(mag[f][d][1] for d in DIST[1:])) for f in ALL])
write_csv("old_point_reproduction.csv", ("project", "source", "frequency_hz", "distance_m",
          "old_value", "rerun_value", "relative_difference"), checks)
for case in expected:
    print(case, [(f, get_e(case, f, .5)) for f in expected[case]])
