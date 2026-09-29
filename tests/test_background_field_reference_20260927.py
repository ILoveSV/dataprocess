import math
import unittest

import numpy as np
from scipy.integrate import quad
from scipy.special import j1

from scripts.background_field_reference_20260927 import (
    EPS0, eqs_prescreen, finite_depth_static, halfspace, norm,
    point_current_electric_field, source_pair,
)


class BackgroundFieldReferenceTests(unittest.TestCase):
    def setUp(self):
        self.currents, self.positions = source_pair()

    def test_exact_air_broadside(self):
        rho, height = 20.0, 1.0
        expected = -10 / (2 * math.pi * 4 * (rho**2 + 6**2 + 5**2)**1.5)
        phi, field = halfspace(self.currents, self.positions, [0, rho, height])
        np.testing.assert_allclose(field, [expected, 0, 0], atol=1e-14)
        self.assertAlmostEqual(abs(phi), 0)

    def test_exact_water_broadside(self):
        rho = 20.0
        expected = -10 / (4 * math.pi * 4) * ((rho**2 + 5**2)**-1.5 + (rho**2 + 5**2 + 10**2)**-1.5)
        field = halfspace(self.currents, self.positions, [0, rho, -5], medium="water")[1]
        np.testing.assert_allclose(field, [expected, 0, 0], atol=1e-14)

    def test_potential_gradient_both_media(self):
        for medium, point in [("air", np.array([3.0, 7.0, 2.0])), ("water", np.array([3.0, 7.0, -2.0]))]:
            h = 1e-4
            gradient = []
            for axis in np.eye(3):
                up = halfspace(self.currents, self.positions, point + h * axis, medium=medium)[0]
                down = halfspace(self.currents, self.positions, point - h * axis, medium=medium)[0]
                gradient.append(-(up - down) / (2 * h))
            field = halfspace(self.currents, self.positions, point, medium=medium)[1]
            np.testing.assert_allclose(field, gradient, rtol=2e-8, atol=1e-13)

    def test_static_interface_conditions(self):
        point = [3.0, 7.0, 0.0]
        pa, ea = halfspace(self.currents, self.positions, point)
        pw, ew = halfspace(self.currents, self.positions, point, medium="water")
        np.testing.assert_allclose(pa, pw, atol=1e-15)
        np.testing.assert_allclose(ea[:2], ew[:2], atol=1e-15)
        self.assertAlmostEqual(abs(ew[2]), 0)
        self.assertGreater(abs(ea[2]), 0)

    def test_complex_interface_total_current(self):
        point = [3.0, 7.0, 0.0]
        for ga in (0.2 + 0.05j, 2j * math.pi * 0.323 * EPS0):
            gw = 4 + 2j * math.pi * 0.323 * EPS0 * 80
            pa, ea = halfspace(self.currents, self.positions, point, gw, ga)
            pw, ew = halfspace(self.currents, self.positions, point, gw, ga, "water")
            np.testing.assert_allclose(pa, pw, rtol=1e-10)
            np.testing.assert_allclose(ea[:2], ew[:2], rtol=1e-10)
            np.testing.assert_allclose(ga * ea[2], gw * ew[2], rtol=1e-8, atol=1e-18)

    def test_equal_media_matches_existing_uniform_solver(self):
        for medium, point in [("water", [3, 7, -2]), ("air", [3, 7, 2])]:
            expected = point_current_electric_field(self.currents, self.positions, point, 4)
            actual = halfspace(self.currents, self.positions, point, 4, 4, medium)[1]
            np.testing.assert_allclose(actual, expected, rtol=1e-13)

    def test_air_twice_counterfactual_uniform_at_same_point(self):
        point = [3, 7, 2]
        expected = 2 * point_current_electric_field(self.currents, self.positions, point, 4)
        actual = halfspace(self.currents, self.positions, point)[1]
        np.testing.assert_allclose(actual, expected, rtol=1e-13)

    def test_current_and_conductivity_scaling(self):
        point = [3, 7, 2]
        base = halfspace(self.currents, self.positions, point)[1]
        np.testing.assert_allclose(halfspace(3 * self.currents, self.positions, point)[1], 3 * base)
        np.testing.assert_allclose(halfspace(self.currents, self.positions, point, 0.05)[1], 80 * base)

    def test_reversal_and_net_cancellation(self):
        point = [3, 7, 2]
        base = halfspace(self.currents, self.positions, point)[1]
        np.testing.assert_allclose(halfspace(-self.currents, self.positions, point)[1], -base)
        currents = np.r_[self.currents, -self.currents]
        positions = np.r_[self.positions, self.positions]
        np.testing.assert_allclose(halfspace(currents, positions, point)[1], 0, atol=1e-14)

    def test_dipole_far_limit(self):
        rho = 10000.0
        expected = 10 / (2 * math.pi * 4 * rho**3)
        actual = norm(halfspace(self.currents, self.positions, [0, rho, 1])[1])
        self.assertLess(abs(actual / expected - 1), 1e-6)

    def test_zero_potential_does_not_imply_zero_field(self):
        phi, field = halfspace(self.currents, self.positions, [0, 20, 1])
        self.assertEqual(phi, 0)
        self.assertGreater(norm(field), 0)

    def test_finite_depth_equal_bottom_reduces_to_halfspace(self):
        for medium, point in [("air", [3, 7, 2]), ("water", [3, 7, -2])]:
            expected = halfspace(self.currents, self.positions, point, medium=medium)
            actual = finite_depth_static(self.currents, self.positions, point, bottom_sigma=4, medium=medium)
            np.testing.assert_allclose(actual[0], expected[0], rtol=1e-13)
            np.testing.assert_allclose(actual[1], expected[1], rtol=1e-13)

    def test_finite_depth_interface_and_series_convergence(self):
        point = [3, 7, 0]
        pa, ea = finite_depth_static(self.currents, self.positions, point)
        pw, ew = finite_depth_static(self.currents, self.positions, point, medium="water")
        np.testing.assert_allclose(pa, pw, rtol=1e-13)
        np.testing.assert_allclose(ea[:2], ew[:2], rtol=1e-13)
        self.assertLess(abs(ew[2]), 1e-14)
        for bottom in (0.5, 40):
            for rho in (2, 30, 200):
                low = finite_depth_static(self.currents, self.positions, [0, rho, 1], bottom_sigma=bottom, terms=80)[1]
                high = finite_depth_static(self.currents, self.positions, [0, rho, 1], bottom_sigma=bottom, terms=160)[1]
                np.testing.assert_allclose(low, high, rtol=1e-8, atol=1e-17)

    def test_finite_depth_independent_hankel_integral(self):
        rho, h, height, H, separation, sigma, bottom = 30.0, 5.0, 1.0, 20.0, 10.0, 4.0, 0.5
        horizontal_radius = math.hypot(rho, separation / 2)
        q = (sigma - bottom) / (sigma + bottom)

        def kernel(k):
            transfer = (math.exp(-k * (height + h)) + q * math.exp(-k * (height + 2 * H - h))) / (1 - q * math.exp(-2 * H * k))
            return k * j1(k * horizontal_radius) * transfer

        integral, error = quad(kernel, 0, np.inf, epsabs=1e-13, epsrel=1e-10, limit=500)
        expected = -separation / (2 * math.pi * sigma * horizontal_radius) * integral
        actual = finite_depth_static(self.currents, self.positions, [0, rho, height])[1][0]
        np.testing.assert_allclose(actual, expected, rtol=1e-8)
        self.assertLess(error, 1e-11)

    def test_local_admittance_not_a_substitute_for_induction_screen(self):
        f = 1 / 3.1
        gw, ga = 4 + 2j * math.pi * f * EPS0 * 80, 2j * math.pi * f * EPS0
        dc = halfspace(self.currents, self.positions, [0, 200, 1])[1]
        eqs = halfspace(self.currents, self.positions, [0, 200, 1], gw, ga)[1]
        np.testing.assert_allclose(norm(dc), norm(eqs), rtol=1e-10)
        self.assertFalse(eqs_prescreen(f, 4, 201)["passed"])
        self.assertTrue(eqs_prescreen(f, 4, 31)["passed"])

    def test_static_screen_and_invalid_inputs(self):
        self.assertTrue(eqs_prescreen(0, 4, 10000)["passed"])
        with self.assertRaises(ValueError):
            halfspace([1, 0], self.positions, [0, 10, 1])
        with self.assertRaises(ValueError):
            halfspace(self.currents, self.positions, [0, 10, -1])
        with self.assertRaises(ValueError):
            finite_depth_static(self.currents, self.positions, [0, 10, 1], water_depth=4)


if __name__ == "__main__":
    unittest.main()
