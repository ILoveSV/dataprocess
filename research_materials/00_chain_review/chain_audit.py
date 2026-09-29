"""Small conditional checks for the research-chain audit; no raw-data analysis."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXTERNAL = ROOT / "results/thesis_followup_20260915/external"
VESSEL = ROOT / "research_materials/01_vessel_background/results"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def unique_row(table, **criteria):
    found = [r for r in table if all(str(r[k]) == str(v) for k, v in criteria.items())]
    if len(found) != 1:
        raise ValueError(f"Expected one row for {criteria}, found {len(found)}")
    return found[0]


def scaling(length_ratio, conductivity_ratio, current_ratio):
    if not all(math.isfinite(v) and v > 0 for v in
               (length_ratio, conductivity_ratio, current_ratio)):
        raise ValueError("Scaling ratios must be positive and finite.")
    lam, k, a = length_ratio, conductivity_ratio, current_ratio
    return dict(length_ratio=lam, conductivity_ratio=k, current_ratio=a,
                potential_ratio=a / (k * lam), field_ratio=a / (k * lam**2),
                current_density_ratio=a / lam**2, dipole_moment_ratio=a * lam)


def split_drive(balanced, single_ended):
    balanced = np.asarray(balanced, dtype=complex)
    single_ended = np.asarray(single_ended, dtype=complex)
    if balanced.shape != (3,) or single_ended.shape != (3,):
        raise ValueError("Expected three complex field components.")
    if not np.all(np.isfinite(balanced)) or not np.all(np.isfinite(single_ended)):
        raise ValueError("Nonfinite field component.")
    # Both solves have Vdiff=1 V; only the second has Vcm=0.5 V.
    return balanced.copy(), 2 * (single_ended - balanced)


def vector(row):
    field = np.array([complex(float(row[f"e{a}_re"]), float(row[f"e{a}_im"]))
                      for a in "xyz"])
    if not np.all(np.isfinite(field)):
        raise ValueError("Nonfinite exported field.")
    if not math.isclose(float(np.linalg.norm(field)), float(row["norm_e_v_m_per_v"]),
                        rel_tol=1e-8, abs_tol=1e-15):
        raise ValueError("Exported field magnitude disagrees with components.")
    return field


def encode_complex_vector(value):
    return [[float(x.real), float(x.imag)] for x in value]


def main():
    transfer_path = EXTERNAL / "all_transfers.csv"
    current_path = EXTERNAL / "gap_current_scaled.csv"
    vessel_path = VESSEL / "unit_current_distance.csv"
    transfers, current, vessel = map(rows, (transfer_path, current_path, vessel_path))
    inputs = {str(p.relative_to(ROOT)): sha256(p) for p in
              (transfer_path, current_path, vessel_path,
               ROOT / "scripts/ExternalGapCases20260916.java")}

    drive_results = []
    for gap in (10, 300):
        for distance in (2, 3, 4):
            args = dict(distance_m=distance, frequency_hz="0.001")
            b = unique_row(transfers, case=f"gap_g{gap:03d}_ppr", **args)
            s = unique_row(transfers, case=f"single_g{gap:03d}_ppr", **args)
            for item in (b, s):
                path = ROOT / item["source"]
                actual_hash = sha256(path)
                if actual_hash != item["source_sha256"]:
                    raise ValueError(f"Source hash mismatch: {path}")
                inputs[str(path.relative_to(ROOT))] = actual_hash
            kd, kc = split_drive(vector(b), vector(s))
            nd, nc = float(np.linalg.norm(kd)), float(np.linalg.norm(kc))
            if nd <= 0 or nc <= 0:
                raise ValueError("Degenerate field response in stored cases.")
            drive_results.append(dict(
                gap_mm=gap, distance_from_bucket_wall_m=distance,
                frequency_hz=0.001, Kdiff_V_m_per_V=nd, Kcm_V_m_per_V=nc,
                Kdiff_xyz_complex=encode_complex_vector(kd),
                Kcm_xyz_complex=encode_complex_vector(kc),
                Kcm_over_Kdiff_norm=nc / nd,
                equal_contribution_Vcm_over_Vdiff=nd / nc,
                reconstruction_error=float(np.linalg.norm(kd + 0.5 * kc - vector(s))),
                meaning="Conditional linear boundary decomposition, not measured TC coupling"))

    gaps = []
    for distance in (2, 3, 4):
        a = unique_row(current, case="gap_g010", distance_m=distance)
        b = unique_row(current, case="gap_g300", distance_m=distance)
        gaps.append(dict(distance_from_bucket_wall_m=distance,
                         fixed_10mA_field_ratio=float(b["e_norm_at_10ma_v_m"]) /
                         float(a["e_norm_at_10ma_v_m"])))

    # Formal 1:100 geometry example, explicitly not the actual bucket/vessel ratio.
    lam, k = 0.01, 0.05 / 4.0
    scale_results = []
    for name, a in (("same_current", 1.0), ("same_potential", k * lam),
                    ("same_field", k * lam**2)):
        scale_results.append(dict(case=name, **scaling(lam, k, a)))
    scale_results.append(dict(case="DACS_example", **scaling(0.0125, 0.0125, 0.0125**2)))

    selected = []
    for item in vessel:
        if math.isclose(float(item["horizontal_offset_m"]), 100.0):
            field = np.array([float(item[f"E{a}_uV_m_per_A"]) for a in "xyz"])
            magnitude = float(item["E_uV_m_per_A"])
            if not math.isclose(float(np.linalg.norm(field)), magnitude, rel_tol=1e-10):
                raise ValueError("Vessel vector mismatch.")
            selected.append(dict(medium=item["medium"], horizontal_offset_m=100.0,
                                 z_m=float(item["z_m"]), norm_uV_m_per_A=magnitude,
                                 xyz_uV_m_per_A=field.tolist(),
                                 largest_over_smallest_component=float(
                                     max(abs(field)) / min(abs(field)))))
    if len(selected) != 2:
        raise ValueError("Missing water/air vessel reference points.")

    result = dict(
        scope="Analytic scaling and postprocessing of existing conditional FEM results",
        no_new_experiment=True, no_new_comsol_solve=True,
        drive_decomposition=drive_results, gap_ratios=gaps,
        geometric_scaling_examples=scale_results,
        frequency_similarity_example=dict(
            induction_frequency_ratio=1 / (k * lam**2),
            displacement_frequency_ratio=k,
            assumption="Equal permeability and permittivity; not a recommended frequency"),
        vessel_direction_examples=selected,
        source_sha256=inputs,
        script_sha256=sha256(__file__),
    )
    output = HERE / "calculation_results.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(dict(drive_decomposition=[{k: r[k] for k in
                     ("gap_mm", "distance_from_bucket_wall_m", "Kcm_over_Kdiff_norm",
                      "equal_contribution_Vcm_over_Vdiff")} for r in drive_results],
                     gap_ratios=gaps, scaling=scale_results,
                     vessel_direction_examples=selected), indent=2))
    print(f"Saved {output}")


if __name__ == "__main__":
    main()
