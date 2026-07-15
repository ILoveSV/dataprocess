"""Parameterized low-frequency noise spectrum models."""

import numpy as np


def continuous_noise(f_hz, N0, f0_hz=1.0, alpha=1.0):
    """Return continuous noise amplitude spectrum in field units.

    Formula: N(f) = N0 * (f/f0)^(-alpha). Output units match N0.
    """
    f = np.asarray(f_hz, dtype=float)
    return float(N0) * (f / float(f0_hz)) ** (-float(alpha))


def line_noise(f_hz, peaks, bandwidth_hz=0.1):
    """Return Gaussian narrow-band line noise approximation.

    peaks is an iterable of (frequency_hz, amplitude) pairs.
    """
    f = np.asarray(f_hz, dtype=float)
    result = np.zeros_like(f, dtype=float)
    sigma = float(bandwidth_hz) / 2.355
    for center, amplitude in peaks:
        result += float(amplitude) * np.exp(-0.5 * ((f - float(center)) / sigma) ** 2)
    return result


def total_noise(f_hz, continuous_terms=None, line_peaks=None, bandwidth_hz=0.1, floor=0.0):
    """Return quadrature sum of parameterized noise components."""
    f = np.asarray(f_hz, dtype=float)
    power = np.full_like(f, float(floor) ** 2, dtype=float)
    for term in continuous_terms or []:
        power += continuous_noise(f, **term) ** 2
    if line_peaks:
        power += line_noise(f, line_peaks, bandwidth_hz) ** 2
    return np.sqrt(power)
