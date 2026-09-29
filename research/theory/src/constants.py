"""Physical constants and default public parameter ranges.

Units:
- Conductivity: S/m
- Magnetic permeability: H/m
- Distance: m
- Electric field: V/m
- Frequency: Hz
"""

import math

MU0_H_PER_M = 4.0 * math.pi * 1e-7
DEFAULT_SIGMA_S_PER_M = 4.0
SIGMA_RANGE_S_PER_M = (3.0, 6.0)

DEFAULT_B0_T = 50e-6
B0_RANGE_T = (25e-6, 65e-6)

DISTANCES_M = [10.0, 30.0, 50.0, 100.0, 300.0, 500.0, 1000.0, 3000.0]
P0_SCAN_A_M = [30.0, 100.0, 300.0, 1000.0, 3000.0]
DIPOLE_MOMENTS_A_M = P0_SCAN_A_M

SHAFT_FREQUENCIES_HZ = [1.0, 2.0, 3.0, 5.0, 7.0]
HARMONICS = [1, 2, 3, 4, 5]
M1_VALUES = [0.001, 0.003, 0.01, 0.03, 0.1, 0.3]

DEFAULT_SPEED_M_PER_S = 5.0
CLOSEST_APPROACH_M = [50.0, 100.0, 300.0, 500.0, 1000.0]

DEFAULT_P0_A_M = 300.0
DEFAULT_P_CORR_A_M = 100.0
DEFAULT_P_SACP_A_M = 100.0
DEFAULT_P_ICCP_A_M = 100.0
DEFAULT_FS_HZ = 3.0
DEFAULT_M1 = 0.03
DEFAULT_CTHETA = 1.0
DEFAULT_L_SHIP_M = 70.0
DIRECTION_FACTORS = {"equatorial": 1.0, "rms": math.sqrt(2.0), "axial": 2.0}

# Public-literature/engineering reference scales, not real platform parameters.
DEFAULT_WAKE_LOCAL_E_V_PER_M = 3e-6
DEFAULT_WAKE_DECAY_LENGTH_M = 300.0
DEFAULT_POWER_LEAK_E_1M_V_PER_M = 1e-6
DEFAULT_POWER_FREQUENCY_HZ = 50.0

# Parametric spectral-noise scan because no MEMS calibration/noise floor is available.
S_E_SQRT_VALUES_V_PER_M_SQRT_HZ = [1e-12, 1e-11, 1e-10, 1e-9, 1e-8]
T_INT_VALUES_S = [10.0, 100.0, 1000.0]
DEFAULT_DETECTION_GAMMA = 2.0
DEFAULT_DETECTION_THRESHOLD_DB = 6.0
