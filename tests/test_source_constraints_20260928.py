"""Unit, bookkeeping, and port-normalization checks for the source audit."""

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "source_constraints", ROOT / 'research/01_vessel_background/source_constraints/audit_source_constraints.py')
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class SourceConstraintTests(unittest.TestCase):
    def test_area_conversion_and_no_double_count(self):
        rows = [dict(id="a", role="injection", current_magnitude_mA=.5, area_cm2=10),
                dict(id="b", role="return", current_magnitude_mA=.5, area_cm2=20)]
        result = audit.source_balance(rows)
        self.assertAlmostEqual(result["branches"][0]["mean_current_density_magnitude_A_m2"], .5)
        self.assertAlmostEqual(result["injected_current_A"], .0005)
        self.assertAlmostEqual(result["sum_of_magnitudes_A"], .001)
        self.assertAlmostEqual(result["imbalance_A"], 0)

    def test_unbalanced_source_is_reported_not_corrected(self):
        rows = [dict(id="a", role="injection", current_magnitude_mA=2, area_cm2=10),
                dict(id="b", role="return", current_magnitude_mA=1, area_cm2=10)]
        self.assertAlmostEqual(audit.source_balance(rows)["imbalance_A"], .001)

    def test_duplicate_source_rejected(self):
        row = dict(id="a", role="injection", current_magnitude_mA=1, area_cm2=10)
        with self.assertRaises(ValueError):
            audit.source_balance([row, row])

    def test_port_scalings_agree_for_matched_load(self):
        result = audit.port_comparison(.1, 2, 20)
        self.assertEqual(result["current_based_over_voltage_based_field"], 1)

    def test_ratio_matches_direct_field_scaling(self):
        kv, resistance, current, voltage = .002, 31, 3, 3.4
        by_voltage = kv * voltage
        by_current = kv * resistance * current
        result = audit.port_comparison(current, voltage, resistance)
        self.assertAlmostEqual(by_current / by_voltage,
                               result["current_based_over_voltage_based_field"])

    def test_invalid_values_rejected(self):
        for value in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                audit.port_comparison(value, 1, 10)

    def test_incremental_slope_and_order(self):
        result = audit.incremental_slopes([dict(I_A=1, V_V=1.69), dict(I_A=2, V_V=2.61)])
        self.assertAlmostEqual(result[0]["delta_V_over_delta_I_ohm"], .92)
        with self.assertRaises(ValueError):
            audit.incremental_slopes([dict(I_A=2, V_V=1), dict(I_A=1, V_V=2)])


if __name__ == "__main__":
    unittest.main()
