"""Parameterized source models for equivalent current dipoles and shaft modulation."""

import warnings
import numpy as np

from .geometry import range_vs_time
from .propagation import static_dipole_field


def total_equivalent_dipole(P_corr_a_m, P_sacp_a_m, P_iccp_a_m):
    """Return P0=P_corr+P_SACP+P_ICCP in A*m."""
    return float(P_corr_a_m) + float(P_sacp_a_m) + float(P_iccp_a_m)


def dipole_moment(currents_a, positions_m, current_tolerance_a=1e-9):
    """Return current dipole moment vector in A*m from point current sources.

    currents_a has shape (N,), positions_m has shape (N, 3). A warning is emitted
    when total current is not approximately zero.
    """
    currents = np.asarray(currents_a, dtype=float)
    positions = np.asarray(positions_m, dtype=float)
    if positions.shape != (currents.size, 3):
        raise ValueError("positions_m must have shape (N, 3)")
    if abs(float(np.sum(currents))) > current_tolerance_a:
        warnings.warn("Total current is not zero; current conservation is violated.", RuntimeWarning)
    return np.sum(currents[:, None] * positions, axis=0)


def harmonic_modulation(m1, harmonic):
    """Return engineering assumption m_n = m_1 / n, dimensionless."""
    return float(m1) / int(harmonic)


def shaft_rate_components(P0_a_m, m1, fs_hz, harmonics):
    """Return shaft-rate component metadata with moment amplitudes in A*m."""
    rows = []
    for n in harmonics:
        m_n = harmonic_modulation(m1, n)
        rows.append({"harmonic": int(n), "frequency_hz": float(fs_hz) * int(n), "m_n": m_n, "delta_P_a_m": float(P0_a_m) * m_n})
    return rows


def moving_envelope(t_s, R0_m, speed_m_per_s, P_a_m, sigma_s_per_m, Ctheta=1.0):
    """Return moving-target static-field envelope E_env(t) in V/m."""
    R = range_vs_time(R0_m, speed_m_per_s, t_s)
    return static_dipole_field(P_a_m, sigma_s_per_m, R, Ctheta)


def moving_shaft_signal(t_s, R0_m, speed_m_per_s, P_a_m, sigma_s_per_m, fs_hz, m_list, phases_rad=None, Ctheta=1.0):
    """Return moving shaft-rate signal in V/m using E_env(t) times harmonic modulation."""
    t = np.asarray(t_s, dtype=float)
    phases = np.zeros(len(m_list), dtype=float) if phases_rad is None else np.asarray(phases_rad, dtype=float)
    if phases.size != len(m_list):
        raise ValueError("phases_rad must match m_list length")
    envelope = moving_envelope(t, R0_m, speed_m_per_s, P_a_m, sigma_s_per_m, Ctheta)
    modulation = np.zeros_like(t)
    for idx, m_n in enumerate(m_list, start=1):
        modulation += float(m_n) * np.cos(2.0 * np.pi * idx * float(fs_hz) * t + phases[idx - 1])
    return envelope * modulation


def moving_envelope_timescale(R0_m, speed_m_per_s):
    """Return approach-envelope time scale tau and half-amplitude time in seconds."""
    tau_s = float(R0_m) / float(speed_m_per_s)
    t_half_s = tau_s * np.sqrt(2.0 ** (2.0 / 3.0) - 1.0)
    return {"tau_s": tau_s, "t_half_s": float(t_half_s), "full_half_width_s": float(2.0 * t_half_s)}
