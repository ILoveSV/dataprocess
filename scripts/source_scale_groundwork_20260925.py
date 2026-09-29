"""Conditional source/scale calculations; no measured sensor-field calibration."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
THEORY = ROOT / 'research/theory'
sys.path.insert(0, str(THEORY))
from src.propagation import (  # noqa: E402
    point_current_electric_field,
    point_current_potential,
    static_dipole_field,
)

OUT = ROOT / 'analysis/source_scale_groundwork_20260925'
SOURCE = ROOT / 'analysis/thesis_followup_20260915/external/gap_current_scaled.csv'


def save_csv(name, rows):
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate():
    checks = []

    def check(name, actual, expected):
        np.testing.assert_allclose(actual, expected, rtol=1e-9, atol=1e-12)
        checks.append(name)

    # Use exact source-pair fields to check the scale laws, including near field.
    currents = np.array([0.01, -0.01])
    positions = np.array([[0.15, 0.0, 0.0], [-0.15, 0.0, 0.0]])
    observer = np.array([0.6, 0.4, 0.3])
    sigma = 4.0
    field = point_current_electric_field(currents, positions, observer, sigma)
    potential = point_current_potential(currents, positions, observer, sigma)
    check("balanced_source", currents.sum(), 0.0)
    check("linear_current", point_current_electric_field(3 * currents, positions, observer, sigma), 3 * field)
    check("inverse_conductivity", point_current_electric_field(currents, positions, observer, 2 * sigma), field / 2)
    check("far_field_inverse_cube", static_dipole_field(0.003, sigma, 4), static_dipole_field(0.003, sigma, 2) / 8)
    lam, conductivity_ratio, current_ratio = 0.01, 0.0125, 0.002
    scaled_field = point_current_electric_field(current_ratio * currents, lam * positions, lam * observer, conductivity_ratio * sigma)
    scaled_potential = point_current_potential(current_ratio * currents, lam * positions, lam * observer, conductivity_ratio * sigma)
    check("finite_source_field_scaling", scaled_field, field * current_ratio / conductivity_ratio / lam**2)
    check("finite_source_potential_scaling", scaled_potential, potential * current_ratio / conductivity_ratio / lam)
    check("current_density_scaling", conductivity_ratio * sigma * scaled_field, sigma * field * current_ratio / lam**2)
    modulated = point_current_electric_field(1.03 * currents, positions, observer, sigma)
    check("fixed_geometry_modulation", modulated - field, 0.03 * field)
    equatorial_exact = np.linalg.norm(point_current_electric_field(currents, positions, [0, 2, 0], sigma))
    check("equatorial_pair_closed_form", equatorial_exact, 0.003 / (4 * math.pi * sigma * (2**2 + 0.15**2)**1.5))
    return checks


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    checks = validate()
    reference = []
    current, separation = 0.01, 0.30
    for sigma in (0.05, 4.0):
        for distance in (2.0, 3.0, 4.0):
            field = float(static_dipole_field(current * separation, sigma, distance))
            exact = np.linalg.norm(point_current_electric_field(
                [current, -current], [[separation / 2, 0, 0], [-separation / 2, 0, 0]], [0, distance, 0], sigma,
            ))
            reference.append({
                "scenario": "assumed_infinite_uniform_water_equatorial",
                "I0_A": current, "effective_source_separation_m": separation,
                "sigma_S_m": sigma, "distance_from_source_center_m": distance,
                "E_dc_dipole_uV_m": field * 1e6,
                "E_dc_finite_pair_uV_m": exact * 1e6,
                "dipole_relative_error_pct": (field / exact - 1) * 100,
                "E_ac_peak_3pct_uV_m": field * 0.03 * 1e6,
                "E_ac_rms_3pct_uV_m": field * 0.03 / math.sqrt(2) * 1e6,
                "J_dc_uA_m2": sigma * field * 1e6,
            })
    save_csv("uniform_water_reference.csv", reference)

    save_csv("modulation_scenarios.csv", [{
        "assumed_modulation_fraction": m,
        "I0_A": 0.01,
        "delta_I_peak_mA": m * 10,
        "E_ac_peak_over_E_dc": m,
        "E_ac_rms_over_E_dc": m / math.sqrt(2),
        "amplitude_ratio_dB_peak_vs_dc": 20 * math.log10(m),
    } for m in (0.001, 0.01, 0.03, 0.10)])

    scaling = []
    for sigma_ratio in (1.0, 0.01, 0.05 / 4):
        lam = 0.01
        for constraint, current_ratio in (
            ("equal_E", sigma_ratio * lam**2),
            ("equal_potential", sigma_ratio * lam),
            ("equal_J", lam**2),
        ):
            scaling.append({
                "constraint": constraint,
                "length_ratio_lab_to_reference": lam,
                "conductivity_ratio_lab_to_reference": sigma_ratio,
                "current_ratio_lab_to_reference": current_ratio,
                "E_ratio_lab_to_reference": current_ratio / sigma_ratio / lam**2,
                "potential_ratio_lab_to_reference": current_ratio / sigma_ratio / lam,
                "J_ratio_lab_to_reference": current_ratio / lam**2,
            })
    save_csv("geometric_scaling.csv", scaling)
    save_csv("motional_source_scale.csv", [{
        "velocity_m_s": u, "B_T": 50e-6, "sin_angle": 1.0,
        "u_cross_B_uV_m": u * 50,
        "meaning": "local_motional_emf_scale_not_remote_observed_field",
    } for u in (0.01, 0.1, 1.0)])

    with SOURCE.open(encoding="utf-8-sig", newline="") as stream:
        source_rows = list(csv.DictReader(stream))
    table = {(row["case"], float(row["distance_m"])): row for row in source_rows}
    gain_rows = []
    for distance in (2.0, 3.0, 4.0):
        small, large = (table[(case, distance)] for case in ("gap_g010", "gap_g300"))
        single = table[("single_g010", distance)]
        e_small, e_large = (float(row["e_norm_at_10ma_v_m"]) for row in (small, large))
        gain_rows.append({
            "distance_from_bucket_wall_m": distance, "frequency_Hz": 0.001,
            "small_gap_mm": 10, "large_gap_mm": 300,
            "small_E_at_10mA_mV_m": 1e3 * e_small,
            "large_E_at_10mA_mV_m": 1e3 * e_large,
            "gap_gain_at_equal_port_current": e_large / e_small,
            "gap_gain_at_equal_differential_voltage": float(large["e_norm_per_1v"]) / float(small["e_norm_per_1v"]),
            "single_vs_balanced_small_gap_equal_voltage": float(single["e_norm_per_1v"]) / float(small["e_norm_per_1v"]),
            "status": "recomputed_from_existing_COMSOL_not_new_experiment_or_solver_run",
        })
    save_csv("existing_comsol_ratios.csv", gain_rows)
    assert all(4.2 < row["gap_gain_at_equal_port_current"] < 4.4 for row in gain_rows)
    checks.append("existing_comsol_gap_ratio_range")

    manifest = {
        "date": "2026-09-25",
        "scope": "theory_groundwork_and_existing_simulation_postprocessing",
        "assumptions": {
            "water_reference": "infinite_uniform_stationary_conductor; fixed_source_pair; no_bucket_air_or_electrode_polarization",
            "I0_A": current, "effective_source_separation_m": separation,
            "conductivities_S_m": [0.05, 4.0],
            "modulation_fraction": "assumed_scenarios_not_measured_or_universal",
            "scaling": "geometrically_similar_linear_conduction_with_matching_normalized_boundaries",
            "sensor_calibration": "not_available_no_input_field_detection_limit_computed",
        },
        "inputs_sha256": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in (SOURCE, THEORY / "src/propagation.py", Path(__file__).resolve())
        },
        "verification": {"passed": checks, "count": len(checks)},
        "outputs": {path.name: sha256(path) for path in sorted(OUT.glob("*.csv"))},
    }
    (OUT / "calculation_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(OUT), "checks_passed": len(checks), "uniform_water": reference, "existing_COMSOL": gain_rows}, indent=2))


if __name__ == "__main__":
    main()
