"""Traceable source/current checks; no inverse fitting and no real-data pipeline."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def positive(value):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Expected a positive finite value.")
    return value


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_balance(branches):
    totals = {"injection": 0.0, "return": 0.0}
    details = []
    ids = set()
    for branch in branches:
        if branch["id"] in ids:
            raise ValueError("Duplicate branch identifier.")
        ids.add(branch["id"])
        role = branch["role"]
        if role not in totals:
            raise ValueError("Unknown branch role.")
        current_A = positive(branch["current_magnitude_mA"]) * 1e-3
        area_m2 = positive(branch["area_cm2"]) * 1e-4
        totals[role] += current_A
        details.append(dict(id=branch["id"], role=role,
                            current_magnitude_A=current_A,
                            area_m2=area_m2,
                            mean_current_density_magnitude_A_m2=current_A / area_m2))
    if not branches or min(totals.values()) <= 0:
        raise ValueError("Both source and return branches are required.")
    return dict(branches=details, injected_current_A=totals["injection"],
                returned_current_A=totals["return"],
                imbalance_A=totals["injection"] - totals["return"],
                sum_of_magnitudes_A=sum(totals.values()))


def port_comparison(current_A, voltage_V, model_R_ohm):
    current_A, voltage_V, model_R_ohm = map(positive, (current_A, voltage_V, model_R_ohm))
    apparent_R = voltage_V / current_A
    return dict(current_A=current_A, voltage_V=voltage_V,
                reported_V_over_I_ohm=apparent_R,
                model_voltage_at_reported_current_V=model_R_ohm * current_A,
                current_based_over_voltage_based_field=model_R_ohm / apparent_R)


def incremental_slopes(points):
    result = []
    for a, b in zip(points, points[1:]):
        ia, ib = positive(a["I_A"]), positive(b["I_A"])
        va, vb = positive(a["V_V"]), positive(b["V_V"])
        if ib <= ia:
            raise ValueError("Currents must be strictly increasing within each set.")
        result.append(dict(I_from_A=ia, I_to_A=ib,
                           delta_V_over_delta_I_ohm=(vb - va) / (ib - ia)))
    return result


def main():
    input_path = HERE / "inputs.json"
    data = json.loads(input_path.read_text(encoding="utf-8"))
    current_path = ROOT / data["lab_model_comparisons"]["source"]
    with current_path.open(encoding="utf-8-sig", newline="") as stream:
        table = list(csv.DictReader(stream))
    models = []
    for name in data["lab_model_comparisons"]["cases"]:
        records = [r for r in table if r["case"] == name]
        if len(records) != 3 or {int(r["distance_m"]) for r in records} != {2, 3, 4}:
            raise ValueError("Expected three probe rows for each stored source case.")
        R = positive(records[0]["effective_impedance_magnitude_ohm"])
        for row in records:
            if not math.isclose(float(row["frequency_hz"]), .001, abs_tol=1e-12):
                raise ValueError("Unexpected model frequency.")
            if not math.isclose(1 / positive(row["positive_current_per_1v_a"]), R, rel_tol=1e-11):
                raise ValueError("Stored source current and impedance disagree.")
            factor = positive(row["e_norm_at_10ma_v_m"]) / positive(row["e_norm_per_1v"])
            if not math.isclose(factor, .01 * R, rel_tol=1e-11):
                raise ValueError("Stored fixed-current scaling is inconsistent.")
        models.append(dict(case=name, R_ohm=R, frequency_hz=.001))

    comparisons = []
    for group in data["reported_lab_points"]:
        for model in models:
            values = [port_comparison(p["I_A"], p["V_V"], model["R_ohm"])
                      for p in group["points"]]
            comparisons.append(dict(reported_set=group["id"], model=model["case"],
                                    model_R_ohm=model["R_ohm"], points=values))
    slopes = {group["id"]: incremental_slopes(group["points"])
              for group in data["reported_lab_points"]}
    files = [input_path, current_path, HERE / "Gijsel-2026-Implementation.pdf",
             ROOT / "articles/raw/schaefer2019.pdf", ROOT / "articles/raw/wang2018.pdf",
             ROOT / "articles/raw/thiel2020.pdf",
             ROOT / "comsol/docs/阴极保护四档恒流与外部电场V4说明.md",
             ROOT / "results/20260922_channel_diagnosis/逐通道贡献与漏判诊断.md"]
    result = dict(
        scope=data["scope"], new_measurement=False, fitted_conductivity=False,
        measured_scale_model_current_balance=source_balance(data["gijsel2026"]["branches"]),
        published_peak_field_cases=[dict(**r, reported_peak_field_uV_m=r["reported_peak_field_V_m"] * 1e6)
                                    for r in data["wang2018"]["peak_field_cases"]],
        candidate_port_models=models, operating_point_comparisons=comparisons,
        incremental_slopes=slopes,
        limitations=["Reported operating points are approximate and not file-level labels.",
                     "Port disagreement is not proof that a specific sensor, current reading, or material is wrong.",
                     "A published scale model is not a measured full-size submarine.",
                     "No actual vessel current or TC field sensitivity is inferred."],
        source_sha256={str(p.relative_to(ROOT)): sha256(p) for p in files},
        script_sha256=sha256(__file__))
    output = HERE / "audit_results.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = dict(current_balance=result["measured_scale_model_current_balance"],
                   models=models, comparisons=[dict(group=r["reported_set"], model=r["model"],
                   normalization_ratio_min=min(p["current_based_over_voltage_based_field"] for p in r["points"]),
                   normalization_ratio_max=max(p["current_based_over_voltage_based_field"] for p in r["points"]))
                   for r in comparisons], slopes=slopes)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Saved {output}")


if __name__ == "__main__":
    main()
