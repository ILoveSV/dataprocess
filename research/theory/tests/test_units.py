import math
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.propagation import skin_depth, static_dipole_field


def test_static_dipole_field_reference_value():
    value = static_dipole_field(100.0, 4.0, 100.0)
    expected = 100.0 / (4.0 * math.pi * 4.0 * 100.0**3)
    assert math.isclose(value, expected, rel_tol=1e-12)


def test_skin_depth_positive():
    assert skin_depth(3.0, 4.0) > 0.0
