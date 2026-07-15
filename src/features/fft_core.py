import numpy as np


def perform_fft_analysis(data, sampling_rate=50000):
    """Run the existing FFT algorithm and return positive frequencies only."""
    n = len(data)
    fft_result = np.fft.fft(data)

    sampling_rate = int(round(float(sampling_rate)))
    if sampling_rate <= 0:
        raise ValueError('Invalid sampling_rate: {}'.format(sampling_rate))

    freqs = np.fft.fftfreq(n, 1 / sampling_rate)
    amplitude = np.abs(fft_result) / n
    phase = np.angle(fft_result)

    positive_freq_idx = freqs > 0
    return freqs[positive_freq_idx], amplitude[positive_freq_idx], phase[positive_freq_idx]

