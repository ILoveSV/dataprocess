from pathlib import Path
import sys

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.geometry import range_vs_time
from src.propagation import frequency_attenuation, shaft_rate_field, skin_depth
from src.snr import solve_detection_range


def test_range_vs_time_is_symmetric_and_minimal_at_zero():
    t = np.array([-10.0, 0.0, 10.0])
    ranges = range_vs_time(100.0, 5.0, t)
    assert ranges[0] == ranges[2]
    assert ranges[1] == 100.0
    assert ranges[1] < ranges[0]


def test_higher_frequency_has_smaller_skin_depth_and_attenuation():
    assert skin_depth(7.0, 4.0) < skin_depth(1.0, 4.0)
    assert frequency_attenuation(1000.0, 7.0, 4.0) < frequency_attenuation(1000.0, 1.0, 4.0)


def test_zero_modulation_zero_shaft_field():
    assert shaft_rate_field(100.0, 0.0, 3.0, 1, 100.0, 4.0) == 0.0


def test_detection_range_increases_with_source_strength():
    r1 = solve_detection_range(100.0, 4.0, 1e-10, f_hz=3.0, modulation=0.03)
    r2 = solve_detection_range(300.0, 4.0, 1e-10, f_hz=3.0, modulation=0.03)
    assert r2 > r1
