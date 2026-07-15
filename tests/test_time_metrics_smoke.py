import math

from src.features.time_metrics import calculate_file_metrics


def test_time_metrics_smoke():
    time = [0, 0.1, 0.2, 0.3]
    values = [1, 2, 3, 4]

    metrics = calculate_file_metrics(values, time)

    assert metrics['sample_count'] == 4
    assert math.isclose(metrics['duration_seconds'], 0.3)
    assert math.isclose(metrics['dt_median'], 0.1)
    assert metrics['mean'] == 2.5
    assert metrics['median'] == 2.5
    assert metrics['min'] == 1
    assert metrics['max'] == 4
    assert metrics['peak_to_peak'] == 3
    assert math.isfinite(metrics['ac_rms'])
    assert math.isfinite(metrics['drift_slope'])

