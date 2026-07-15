import numpy as np

from src.features.nist_diagnostics import compute_nist_diagnostics
from src.plots.nist_4plot import plot_nist_4plot


def test_nist_4plot_smoke(tmp_path):
    x = np.asarray([1, 2, 3, 4, 5], dtype=float)
    time = np.asarray([0, 1, 2, 3, 4], dtype=float)
    result = compute_nist_diagnostics(x, time)

    output_path = tmp_path / "nist_4plot.png"
    plot_nist_4plot(result['plot_data'], result['metrics'], output_path)

    assert output_path.exists()

