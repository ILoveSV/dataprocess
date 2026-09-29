"""Propagation and field-amplitude estimates in conductive seawater."""

import math
import numpy as np

from .constants import MU0_H_PER_M


def static_dipole_field(P_a_m, sigma_s_per_m, R_m, Ctheta=1.0):
    """Return far-field current-dipole electric-field magnitude in V/m.

    Formula: E = Ctheta * P / (4*pi*sigma*R^3).
    P is equivalent current dipole moment in A*m.
    """
    R = np.asarray(R_m, dtype=float)
    return float(Ctheta) * float(P_a_m) / (4.0 * math.pi * float(sigma_s_per_m) * R**3)


def dipole_direction_fields(P_a_m, sigma_s_per_m, R_m):
    """Return equatorial, rms, and axial far-field amplitudes in V/m."""
    base = static_dipole_field(P_a_m, sigma_s_per_m, R_m, Ctheta=1.0)
    return {
        "equatorial": base,
        "rms": math.sqrt(2.0) * base,
        "axial": 2.0 * base,
    }


def skin_depth(f_hz, sigma_s_per_m, mu_h_per_m=MU0_H_PER_M):
    """Return conductive-medium skin depth in m.

    Formula: delta = sqrt(1 / (pi*f*mu*sigma)).
    """
    f = np.asarray(f_hz, dtype=float)
    return np.sqrt(1.0 / (math.pi * f * float(mu_h_per_m) * float(sigma_s_per_m)))


def frequency_attenuation(R_m, f_hz, sigma_s_per_m, mu_h_per_m=MU0_H_PER_M):
    """Return engineering attenuation factor exp(-R/delta), dimensionless."""
    R = np.asarray(R_m, dtype=float)
    delta = skin_depth(f_hz, sigma_s_per_m, mu_h_per_m)
    return np.exp(-R / delta)


def shaft_rate_field(P0_a_m, m_n, fs_hz, harmonic, R_m, sigma_s_per_m, Ctheta=1.0, conservative_diffusion=False):
    """Return nth shaft-rate electric-field amplitude in V/m.

    The default is quasi-static modulation of the total equivalent dipole P0.
    Set conservative_diffusion=True only for optional sensitivity curves.
    """
    base = static_dipole_field(P0_a_m, sigma_s_per_m, R_m, Ctheta)
    signal = float(m_n) * base
    if conservative_diffusion:
        signal = signal * frequency_attenuation(R_m, float(fs_hz) * int(harmonic), sigma_s_per_m)
    return signal


def point_current_potential(currents_a, positions_m, observation_points_m, sigma_s_per_m):
    """Return phi(r)=sum_k I_k/(4*pi*sigma*|r-r_k|) for point current sources."""
    currents = np.asarray(currents_a, dtype=float)
    positions = np.asarray(positions_m, dtype=float)
    obs = np.asarray(observation_points_m, dtype=float)
    if positions.shape != (currents.size, 3):
        raise ValueError("positions_m must have shape (N, 3)")
    diff = obs[..., None, :] - positions
    distances = np.linalg.norm(diff, axis=-1)
    if np.any(distances == 0.0):
        raise ValueError("observation point coincides with a point source")
    return np.sum(currents / (4.0 * math.pi * float(sigma_s_per_m) * distances), axis=-1)


def point_current_electric_field(currents_a, positions_m, observation_points_m, sigma_s_per_m):
    """Return E=-grad(phi) from discrete point current sources in V/m."""
    currents = np.asarray(currents_a, dtype=float)
    positions = np.asarray(positions_m, dtype=float)
    obs = np.asarray(observation_points_m, dtype=float)
    if positions.shape != (currents.size, 3):
        raise ValueError("positions_m must have shape (N, 3)")
    diff = obs[..., None, :] - positions
    distances = np.linalg.norm(diff, axis=-1)
    if np.any(distances == 0.0):
        raise ValueError("observation point coincides with a point source")
    coeff = currents / (4.0 * math.pi * float(sigma_s_per_m) * distances**3)
    return np.sum(coeff[..., None] * diff, axis=-2)
