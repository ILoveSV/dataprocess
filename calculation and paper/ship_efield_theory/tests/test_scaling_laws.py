from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.propagation import static_dipole_field


def test_field_scales_as_inverse_range_cubed():
    e1 = static_dipole_field(100.0, 4.0, 100.0)
    e2 = static_dipole_field(100.0, 4.0, 1000.0)
    assert abs((e1 / e2) - 1000.0) < 1e-9


def test_field_scales_linearly_with_dipole_moment():
    e1 = static_dipole_field(100.0, 4.0, 100.0)
    e2 = static_dipole_field(300.0, 4.0, 100.0)
    assert abs((e2 / e1) - 3.0) < 1e-12


def test_field_scales_as_inverse_conductivity():
    e1 = static_dipole_field(100.0, 3.0, 100.0)
    e2 = static_dipole_field(100.0, 6.0, 100.0)
    assert abs((e1 / e2) - 2.0) < 1e-12
