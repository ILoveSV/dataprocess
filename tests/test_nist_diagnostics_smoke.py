import numpy as np

from src.features.nist_diagnostics import compute_group_nist_diagnostics, compute_nist_diagnostics


def test_nist_diagnostics_smoke():
    x = [1, 2, 3, 4, 5]
    time = [0, 1, 2, 3, 4]

    result = compute_nist_diagnostics(x, time)

    assert 'metrics' in result
    assert 'plot_data' in result
    metrics = result['metrics']
    assert 'run_drift_slope' in metrics
    assert 'lag_1_corr' in metrics
    assert 'dist_iqr' in metrics
    assert 'qq_normal_prob_corr' in metrics
    for value in metrics.values():
        if isinstance(value, (int, float, np.integer, np.floating)):
            assert np.isfinite(value) or np.isnan(value)


def test_group_nist_diagnostics_smoke():
    series = [
        np.asarray([1, 2, 3, 4, 5], dtype=float),
        np.asarray([2, 3, 4, 5, 6], dtype=float),
    ]
    times = [
        np.asarray([0, 1, 2, 3, 4], dtype=float),
        np.asarray([0, 1, 2, 3, 4], dtype=float),
    ]

    result = compute_group_nist_diagnostics(series, times)

    assert 'metrics' in result
    assert 'plot_data' in result
    metrics = result['metrics']
    assert 'run_drift_slope' in metrics
    assert 'lag_1_corr' in metrics
    assert 'acf_first_peak_value' in metrics
    assert 'dist_iqr' in metrics
    assert 'qq_normal_prob_corr' in metrics
    boundaries = result['plot_data']['run_sequence']['file_boundaries']
    assert len(boundaries) == 1
