"""Receiver-side parameterized electric-field response models."""

import numpy as np


def voltage_difference(phi_i_v, phi_j_v):
    """Return voltage difference Delta V_ij in V."""
    return np.asarray(phi_i_v, dtype=float) - np.asarray(phi_j_v, dtype=float)


def small_baseline_voltage(E_vec_v_per_m, baseline_vec_m):
    """Return small-baseline voltage approximation in V.

    Formula: Delta V ~= -E dot baseline.
    """
    E = np.asarray(E_vec_v_per_m, dtype=float)
    baseline = np.asarray(baseline_vec_m, dtype=float)
    return -np.sum(E * baseline, axis=-1)


def equivalent_gradient(delta_v, baseline_length_m):
    """Return equivalent electric-field gradient estimate in V/m."""
    return np.asarray(delta_v, dtype=float) / float(baseline_length_m)


def mems_voltage(E_v_per_m, K_v_per_v_per_m, bias_v=0.0, noise_v=0.0):
    """Return parameterized MEMS output voltage in V.

    K is a symbolic/calibrated transfer coefficient in V/(V/m). Without measured
    calibration this is only a parameterized linear response model.
    """
    return float(K_v_per_v_per_m) * np.asarray(E_v_per_m, dtype=float) + float(bias_v) + np.asarray(noise_v, dtype=float)
