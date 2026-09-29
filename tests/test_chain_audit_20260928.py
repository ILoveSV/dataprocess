"""Analytical identities, input guards, and scaling against a separate field kernel."""

import importlib.util
from pathlib import Path
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "chain_audit", ROOT / "research_materials/00_chain_review/chain_audit.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)

from scripts.background_field_reference_20260927 import halfspace, source_pair


class ChainAuditTests(unittest.TestCase):
    def test_scaling_against_field_kernel(self):
        currents, sources = source_pair(current=1, separation=12, depth=7)
        lam, k, a = .03, .02, .004
        ratios = audit.scaling(lam, k, a)
        for medium, points in (("air", [[3, 8, 2], [40, 15, 5]]),
                               ("water", [[3, 8, -9], [40, 15, -20]])):
            points = np.asarray(points)
            p, e = halfspace(currents, sources, points, medium=medium)
            ps, es = halfspace(currents * a, sources * lam, points * lam,
                               water_admittance=4 * k, medium=medium)
            np.testing.assert_allclose(ps, p * ratios["potential_ratio"], rtol=1e-11)
            np.testing.assert_allclose(es, e * ratios["field_ratio"], rtol=1e-11)

    def test_equal_field_requires_scaled_current(self):
        lam, k = .01, .0125
        self.assertAlmostEqual(audit.scaling(lam, k, k * lam**2)["field_ratio"], 1)

    def test_dacs_keeps_potential_and_current_density(self):
        result = audit.scaling(.0125, .0125, .0125**2)
        self.assertAlmostEqual(result["potential_ratio"], 1)
        self.assertAlmostEqual(result["current_density_ratio"], 1)
        self.assertAlmostEqual(result["field_ratio"], 80)

    def test_scaling_guards(self):
        for ratios in ((0, 1, 1), (1, -1, 1), (1, 1, float("nan"))):
            with self.assertRaises(ValueError):
                audit.scaling(*ratios)

    def test_drive_recovers_known_complex_components(self):
        kd = np.array([1 + 2j, -2, .5j])
        kc = np.array([-3j, 4 + .2j, 2])
        gotd, gotc = audit.split_drive(kd, kd + .5 * kc)
        np.testing.assert_allclose(gotd, kd)
        np.testing.assert_allclose(gotc, kc)

    def test_magnitude_subtraction_is_not_vector_subtraction(self):
        kd, kc = audit.split_drive([1, 0, 0], [0, 1, 0])
        self.assertGreater(np.linalg.norm(kc), 0)
        self.assertEqual(np.linalg.norm([0, 1, 0]) - np.linalg.norm(kd), 0)

    def test_drive_rejects_malformed_input(self):
        for x in ([1, 2], [1, float("nan"), 0]):
            with self.assertRaises(ValueError):
                audit.split_drive(x, [0, 1, 0])

    def test_unique_rows_reject_missing_and_duplicate(self):
        for table in ([], [{"key": "a"}, {"key": "a"}]):
            with self.assertRaises(ValueError):
                audit.unique_row(table, key="a")


if __name__ == "__main__":
    unittest.main()
