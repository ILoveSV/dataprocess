import numpy as np

from src.features.fft_core import perform_fft_analysis


def test_fft_core_smoke():
    x = np.sin(np.linspace(0, 2 * np.pi, 100, endpoint=False))

    freqs, amplitude, phase = perform_fft_analysis(x, sampling_rate=1000)

    assert len(freqs) == len(amplitude) == len(phase)
    assert np.all(freqs > 0)
    assert np.all(np.isfinite(amplitude))
    assert np.all(np.isfinite(phase))

