from __future__ import annotations

import numpy as np

from scripts.analyze_full_raw_highfrequency import comb_metrics
from scripts.analyze_projection_memd import mode_metrics, projection_memd
from scripts.analyze_pulse_relaxation_raw import (
    best_relaxation_template,
    dynamic_healthy_channels,
    harmonic_comb_score_from_spectrum,
    pulse_tokens,
    single_tau_fit,
)


def test_projection_memd_reconstructs_and_separates_two_modes() -> None:
    sample_rate = 10.0
    time = np.arange(0.0, 80.0, 1.0 / sample_rate)
    values = np.column_stack([
        np.sin(2.0 * np.pi * 0.31 * time + phase)
        + 0.4 * np.sin(2.0 * np.pi * 1.4 * time - phase)
        for phase in np.linspace(0.0, 0.35, 5)
    ])
    imfs, residual, _ = projection_memd(
        values, direction_count=16, maximum_imfs=5, seed=14
    )
    modes, summary = mode_metrics(imfs, residual, values, sample_rate)
    centers = np.asarray([row["center_frequency_hz_median"] for row in modes])
    assert summary["memd_reconstruction_nrmse"] < 1e-10
    assert np.min(np.abs(centers - 0.31)) < 0.05
    assert np.min(np.abs(centers - 1.4)) < 0.12


def test_pulse_parser_ignores_non_voltage_timing_tokens() -> None:
    name = "vac/0930/二阶波-Δ2/t2-10ms210ms/0v20ms-20v50ms-22v10ms"
    assert pulse_tokens(name) == [(0.0, 20.0), (20.0, 50.0), (22.0, 10.0)]


def test_single_tau_fit_recovers_identifiable_decay() -> None:
    sample_rate = 20_000.0
    time = np.arange(0.0, 0.02, 1.0 / sample_rate)
    values = 2.0 * np.exp(-time / 0.0025) + 0.1 + 0.03 * time
    result = single_tau_fit(values, sample_rate)
    assert abs(result["single_tau_s"] - 0.0025) / 0.0025 < 0.2
    assert result["single_r2"] > 0.99
    assert result["single_vs_linear_delta_aicc"] > 10.0
    assert result["tau_identifiable"]


def test_relaxation_template_recovers_periodic_exponential_response() -> None:
    sample_rate = 20_000.0
    template = np.r_[np.zeros(400), np.full(200, 10.0)]
    derivative = np.diff(template, prepend=template[-1])
    time = np.arange(len(template)) / sample_rate
    expected_tau = 0.002
    response = np.fft.irfft(
        np.fft.rfft(derivative) * np.fft.rfft(np.exp(-time / expected_tau)),
        n=len(template),
    )
    response = np.roll(response, 71)
    result = best_relaxation_template(response, template, sample_rate)
    assert abs(result["correlation"]) > 0.99
    assert abs(result["tau_s"] - expected_tau) / expected_tau < 0.25


def test_dynamic_health_rejects_flat_channel_per_file() -> None:
    rng = np.random.default_rng(6)
    values = rng.normal(scale=0.01, size=(5000, 8))
    values[:, 3] = 1.0
    healthy, rows = dynamic_healthy_channels(values)
    assert 3 not in healthy
    assert rows[3]["automatic_bad"]
    assert len(healthy) >= 4


def test_carrier_comb_prefers_injected_harmonic_family() -> None:
    sample_rate = 400_000.0
    nperseg = 16_384
    frequency = np.fft.rfftfreq(nperseg, 1.0 / sample_rate)
    rng = np.random.default_rng(12)
    power = np.abs(rng.normal(size=(32, len(frequency)))) + 1.0
    for harmonic in np.arange(8_000.0, 190_000.0, 8_000.0):
        center = int(np.argmin(np.abs(frequency - harmonic)))
        power[:, center - 1:center + 2] += 100.0
    score_4, _, _ = comb_metrics(frequency, power, 4_000.0)
    score_8, _, _ = comb_metrics(frequency, power, 8_000.0)
    score_12, _, _ = comb_metrics(frequency, power, 12_000.0)
    assert score_8 > score_4
    assert score_8 > score_12


def test_pulse_comb_does_not_count_50hz_mains_harmonics() -> None:
    frequency = np.linspace(0.0, 2_000.0, 20_001)
    power = np.ones_like(frequency)
    for harmonic in np.arange(50.0, 2_000.0, 50.0):
        power[np.argmin(np.abs(frequency - harmonic))] = 1_000.0
    score = harmonic_comb_score_from_spectrum(frequency, power, 25.0)
    assert abs(score) < 1e-9
