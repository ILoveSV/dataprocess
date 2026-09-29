from pathlib import Path

import numpy as np

from scripts.analyze_cathodic_mentor_highfreq import (
    CaseSpec as HighCaseSpec,
    exact_signflip_p,
    protocol_window_times,
)
from scripts.analyze_cathodic_mentor_lowfreq import (
    CaseSpec as LowCaseSpec,
    nearby_frequency_p,
    protocol_state,
)
from scripts.build_cathodic_mentor_methods_report import bh_adjust
from scripts.analyze_cathodic_state_network import (
    alignment_statistic,
    exact_alignment_p,
    exact_projection_p,
    unit_rows,
)


def test_exact_signflip_detects_consistent_cycle_effect() -> None:
    values = np.linspace(0.8, 1.2, 12)
    assert exact_signflip_p(values) < 0.001
    alternating = np.tile([-1.0, 1.0], 6)
    assert exact_signflip_p(alternating) == 1.0


def test_nearby_frequency_test_prefers_exact_long_sine() -> None:
    times = np.arange(0.0, 200.0, 0.1)
    values = np.sin(2.0 * np.pi * 0.1 * times)
    amplitude, p_value, q95 = nearby_frequency_p(values, times, 0.1)
    assert amplitude > 0.99
    assert p_value < 0.02
    assert q95 < amplitude


def test_protocol_builders_create_expected_on_off_schedule() -> None:
    high = HighCaseSpec(
        "synthetic", Path("archive"), Path("raw"), 100.0,
        "closed_circuit", 1, 4, 30.0, 20.0,
    )
    windows = protocol_window_times(high)
    assert len(windows) == 3 * 4 * 2 * 4
    assert {row["state"] for row in windows} == {"on", "off"}

    low = LowCaseSpec(
        "batch", "synthetic", Path("archive"), 100.0,
        "closed_circuit", 1, 4, 0.05, 30.0, 20.0, 0.5,
    )
    times = np.arange(0.0, 120.0, 0.1)
    state = protocol_state(times, low)
    assert np.isclose(np.sum(state) / 10.0, 40.0)


def test_bh_adjust_is_monotone_in_p_value_order() -> None:
    p = np.asarray([0.04, 0.001, 0.02, 0.7])
    q = bh_adjust(p)
    order = np.argsort(p)
    assert np.all(np.diff(q[order]) >= 0.0)
    assert np.all(q >= p)


def test_state_alignment_detects_repeated_multichannel_direction() -> None:
    base = np.asarray([1.0, -0.5, 0.25])
    values = np.vstack([base * factor for factor in np.linspace(0.8, 1.2, 12)])
    unit = unit_rows(values)
    assert np.isclose(alignment_statistic(unit), 1.0)
    assert exact_alignment_p(unit) < 0.001
    assert exact_projection_p(np.ones(12)) < 0.001
