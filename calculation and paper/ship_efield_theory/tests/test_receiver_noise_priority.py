from pathlib import Path
import sys

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.noise_model import continuous_noise, line_noise
from src.receiver_model import mems_voltage, small_baseline_voltage, voltage_difference


def test_small_baseline_voltage_zero_for_perpendicular_baseline():
    E = np.array([1e-9, 0.0, 0.0])
    baseline = np.array([0.0, 1.0, 0.0])
    assert small_baseline_voltage(E, baseline) == 0.0


def test_small_baseline_voltage_scales_with_baseline_length():
    E = np.array([1e-9, 0.0, 0.0])
    d1 = small_baseline_voltage(E, np.array([1.0, 0.0, 0.0]))
    d2 = small_baseline_voltage(E, np.array([2.0, 0.0, 0.0]))
    assert d2 == 2.0 * d1


def test_mems_voltage_linear_response():
    v1 = mems_voltage(1e-9, 1e-3)
    v2 = mems_voltage(2e-9, 1e-3)
    assert v2 == 2.0 * v1


def test_voltage_difference_zero_for_same_potential():
    assert voltage_difference(1.0, 1.0) == 0.0


def test_continuous_noise_decreases_with_frequency_for_positive_alpha():
    assert continuous_noise(10.0, N0=1.0, f0_hz=1.0, alpha=1.0) < continuous_noise(1.0, N0=1.0, f0_hz=1.0, alpha=1.0)


def test_line_noise_peaks_near_center():
    near = line_noise(np.array([50.0]), [(50.0, 1.0)], bandwidth_hz=0.5)[0]
    far = line_noise(np.array([49.0]), [(50.0, 1.0)], bandwidth_hz=0.5)[0]
    assert near > far
