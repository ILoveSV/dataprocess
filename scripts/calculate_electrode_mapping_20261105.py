"""Conditional sizing from existing DC COMSOL outputs; not an AC simulation."""

from pathlib import Path
import csv
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "research/01_vessel_background/iccp_v1"
OUT = ROOT / "analysis/electrode_mapping_20261105"


def csv_rows(path):
    with path.open(encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    audit_path = MODEL / "results/base_10A_audit.csv"
    lines = audit_path.read_text(encoding="utf-8-sig").splitlines()
    audit = next(csv.reader([line for line in lines if not line.startswith("%")][0:1]))
    # Column names and order are retained in the original COMSOL table header.
    iccp, hull_current, steel_area = float(audit[1]), float(audit[2]), float(audit[8])
    damage, exposed_area = .02, .20*.10
    effective_area = steel_area*damage
    j_exposed = abs(hull_current)/effective_area
    same_j_current = j_exposed*exposed_area
    sigma_list = (.04, .05, .1, .2, .5, 4.)
    gap_effective, water_receiver_distance = .30, 3.
    inputs = [audit_path, MODEL / "parameters.properties",
              MODEL / "results/base_10A_side_tidy.csv"]
    field_rows = csv_rows(inputs[-1])
    mapping = []
    for position in field_rows:
        if round(float(position["y_m"])) not in (50, 100):
            continue
        dc_field = float(position["normE_V_m"])
        for assumed_fraction in (.01, .10):
            target = dc_field*assumed_fraction
            for sigma in sigma_list:
                # Exact equatorial field for two point current poles in infinite water.
                gain = gap_effective/(4*math.pi*sigma*(water_receiver_distance**2
                                                     +(gap_effective/2)**2)**1.5)
                current = target/gain
                mapping.append(dict(model_side_distance_m=float(position["y_m"]),
                    model_dc_normE_uv_m=dc_field*1e6,
                    assumed_ac_field_fraction=assumed_fraction,
                    target_ac_field_uv_m=target*1e6, water_sigma_s_m=sigma,
                    water_conductivity_us_cm=sigma*10000,
                    effective_current_centroid_distance_m=gap_effective,
                    water_receiver_from_pair_midpoint_m=water_receiver_distance,
                    ideal_pair_gain_uv_m_per_ma=gain*1000,
                    required_ac_current_peak_ma=current*1000,
                    scope="Hypothetical field fraction; infinite-water point-pole mapping; NOT bucket-air prediction"))
    budgets = []
    for sigma in sigma_list:
        # A one-dimensional current-tube budget, not a resistance bound or FEM result.
        area_example = .005
        resistance = gap_effective/(sigma*area_example)
        budgets.append(dict(sigma_s_m=sigma, conductivity_us_cm=sigma*10000,
            assumed_current_tube_area_m2=area_example, path_length_m=gap_effective,
            illustrative_water_resistance_ohm=resistance,
            illustrative_water_drop_at_10ma_v=.01*resistance,
            scope="Uniform current-tube budget only; excludes polarization, leads, fringing and actual tank geometry"))
    for name, rows in (("conditional_water_field_mapping.csv", mapping),
                       ("illustrative_voltage_budget.csv", budgets)):
        with (OUT/name).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    result = dict(model=dict(length_m=50, beam_m=6, depth_m=20, sigma_s_m=4,
                            iccp_dc_a=iccp, steel_wet_area_m2=steel_area,
                            coating_active_fraction=damage,
                            steel_net_cathodic_a=abs(hull_current),
                            rotation_and_ac_not_solved=True),
        experimental_steel_area_m2=exposed_area,
        model_effective_steel_area_m2=effective_area,
        average_exposed_net_current_density_a_m2=j_exposed,
        experimental_current_at_same_mean_j_ma=same_j_current*1000,
        practical_starting_design=dict(sigma_s_m=.1, conductivity_us_cm=1000,
            sigma_sensitivity_s_m=[.05, .2], effective_centroid_separation_m=.30,
            graphite_wetted_area_unknown=True,
            status="Engineering starting point, NOT a uniquely derived scale model"),
        hypothetical_exact_1to100_psm=dict(
            requires_same_geometry_material_polarization_and_boundaries=True,
            length_scale=.01, water_sigma_s_m=.04, dc_iccp_ma=1,
            corresponding_E_scale=100,
            note="Steady electrochemical scaling only, not a dynamic similarity claim"),
        caveats=["The two-electrode setup does not reproduce distributed hull/propeller/ICCP return currents",
                 "Steel and graphite area alone cannot uniquely determine conductivity or separation",
                 "1% and 10% are hypothetical field AC fractions, not computed propeller modulation",
                 "The measured TC output is not a calibrated water electric field",
                 "Historical TC receivers are in air; infinite-water values are not their inputs",
                 "A finite tank, surface, feed wires, common mode and electrode impedance require a dedicated model"],
        inputs=[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in inputs])
    assert abs(same_j_current*1000-7.300792)<.001
    assert exposed_area == .020000000000000004
    (OUT/"calculation_results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("Example water mapping, sigma=0.1 S/m:")
    print(json.dumps([row for row in mapping if row["water_sigma_s_m"] == .1], indent=2))


if __name__ == "__main__":
    main()
