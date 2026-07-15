"""Geometry helpers for straight-line closest-approach motion."""

import numpy as np


def range_vs_time(R0_m, speed_m_per_s, t_s):
    """Return source-receiver range R(t) in m.

    Parameters are closest approach R0 in m, speed in m/s, and scalar/array time in s.
    """
    t = np.asarray(t_s, dtype=float)
    return np.sqrt(float(R0_m) ** 2 + (float(speed_m_per_s) * t) ** 2)
