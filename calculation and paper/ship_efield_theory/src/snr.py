"""SNR and parameterized detection-range estimates."""

import math
import numpy as np

from .propagation import static_dipole_field, frequency_attenuation, shaft_rate_field


def snr_db(signal, noise):
    """Return 20*log10(signal/noise) in dB for field amplitudes in the same units."""
    signal_arr = np.asarray(signal, dtype=float)
    noise_arr = np.asarray(noise, dtype=float)
    return 20.0 * np.log10(signal_arr / noise_arr)


def processing_gain_db(M=1, B_hz=1.0, T_s=1.0, loss_db=0.0):
    """Return ideal coherent-channel and narrow-band integration gain in dB."""
    return 10.0 * math.log10(float(M)) + 10.0 * math.log10(float(B_hz) * float(T_s)) - float(loss_db)


def effective_threshold_field(noise_floor_v_per_m, threshold_db=6.0, M=1, B_hz=1.0, T_s=1.0, loss_db=0.0):
    """Return field amplitude needed before processing to meet an SNR threshold."""
    gain_db = processing_gain_db(M, B_hz, T_s, loss_db)
    return float(noise_floor_v_per_m) * 10.0 ** ((float(threshold_db) - gain_db) / 20.0)


def spectral_detection_threshold(S_E_sqrt_v_per_m_sqrt_hz, T_int_s, gamma=2.0):
    """Return E_min(f,T)=gamma*S_E^1/2(f)/sqrt(T_int)."""
    return float(gamma) * float(S_E_sqrt_v_per_m_sqrt_hz) / math.sqrt(float(T_int_s))


def analytic_detection_range(P_a_m, sigma_s_per_m, Emin_v_per_m, Ctheta=1.0, modulation=1.0):
    """Return Rmax in m ignoring exponential frequency attenuation."""
    numerator = float(Ctheta) * float(P_a_m) * float(modulation)
    denominator = 4.0 * math.pi * float(sigma_s_per_m) * float(Emin_v_per_m)
    return (numerator / denominator) ** (1.0 / 3.0)


def solve_detection_range(P_a_m, sigma_s_per_m, Emin_v_per_m, f_hz=None, Ctheta=1.0, modulation=1.0, R_min_m=1.0, R_max_m=100000.0):
    """Return Rmax in m, optionally including exp(-R/delta) frequency attenuation."""
    if f_hz is None or float(f_hz) <= 0.0:
        return analytic_detection_range(P_a_m, sigma_s_per_m, Emin_v_per_m, Ctheta, modulation)

    def field_at(R):
        return float(modulation) * static_dipole_field(P_a_m, sigma_s_per_m, R, Ctheta) * frequency_attenuation(R, f_hz, sigma_s_per_m)

    lo = float(R_min_m)
    hi = float(R_max_m)
    if field_at(lo) < Emin_v_per_m:
        return 0.0
    while field_at(hi) > Emin_v_per_m and hi < 1e7:
        hi *= 2.0
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if field_at(mid) >= Emin_v_per_m:
            lo = mid
        else:
            hi = mid
    return lo


def shaft_snr_curve(P0_a_m, m_n, fs_hz, harmonic, R_m, sigma_s_per_m, noise_floor_v_per_m, Ctheta=1.0, conservative_diffusion=False):
    """Return shaft component SNR in dB over distance."""
    signal = shaft_rate_field(P0_a_m, m_n, fs_hz, harmonic, R_m, sigma_s_per_m, Ctheta, conservative_diffusion=conservative_diffusion)
    return snr_db(signal, noise_floor_v_per_m)
