from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import signal

from scripts.analyze_pre_electrochemical_dynamics import (
    allan_deviation,
    autocorrelation_metrics,
    coherence_matrices,
    lagged_correlation,
    line_tracks,
    red_noise_periodicity_pvalues,
    sinusoid_fit_metrics,
)
from scripts.analyze_legacy_pulse_outputs import parse_group_name
from scripts.build_mentor_aligned_evidence_report import (
    run_stop_exploratory_classification,
)
from scripts.analyze_mentor_wavelet_relaxation import (
    cwt_analysis,
    fit_exponential_relaxation,
)
from scripts.analyze_mentor_event_shape_models import (
    fit_event_shape_models,
    matrix_pencil_poles,
)
from scripts.analyze_mentor_modes_complexity_network import (
    aligned_multichannel_emd_features,
    benjamini_hochberg,
    multifractal_dfa,
    recurrence_features,
    robust_pca,
)
from scripts.analyze_mentor_nonlinear_highfreq import (
    bicoherence_values,
    phase_amplitude_coupling,
)
from scripts.analyze_mentor_multimethod_identifiability import grouped_predictions


def test_allan_deviation_constant_signal_is_zero() -> None:
    rows = allan_deviation(np.ones(1000), 10.0, (0.1, 1.0, 10.0))
    assert rows
    assert all(np.isclose(row["allan_deviation_v"], 0.0) for row in rows)


def test_acf_finds_slow_ar_process() -> None:
    rng = np.random.default_rng(42)
    values = np.zeros(5000)
    for index in range(1, len(values)):
        values[index] = 0.95 * values[index - 1] + rng.normal(scale=0.1)
    result = autocorrelation_metrics(values, 10.0, 10.0)
    assert result["ar1_phi"] > 0.9
    assert result["ar1_tau_s"] > 1.0
    assert result["acf_e_fold_s"] > 1.0


def test_lagged_correlation_recovers_delay() -> None:
    rng = np.random.default_rng(7)
    source = rng.normal(size=1000)
    delayed = np.concatenate([np.zeros(5), source[:-5]])
    result = lagged_correlation(source, delayed, 10.0, 1.0)
    assert abs(result["max_abs_lag_correlation"]) > 0.95
    assert np.isclose(result["lag_at_max_abs_s"], 0.5)


def test_line_tracks_reports_persistent_frequency() -> None:
    frequency = np.array([
        [1000.0, 3000.0],
        [1001.0, 4000.0],
        [999.0, 5000.0],
        [1002.0, 6000.0],
    ])
    power = np.array([
        [10.0, 1.0],
        [9.0, 1.0],
        [11.0, 1.0],
        [10.0, 1.0],
    ])
    tracks = line_tracks(frequency, power, bin_width_hz=10.0)
    assert tracks[0]["persistence_fraction"] == 1.0
    assert abs(tracks[0]["median_frequency_hz"] - 1000.5) < 2.0


def test_coherence_detects_shared_tone() -> None:
    rng = np.random.default_rng(123)
    sample_rate = 4000.0
    time = np.arange(16 * 8192) / sample_rate
    tone = np.sin(2.0 * np.pi * 250.0 * time)
    values = np.column_stack([
        tone + rng.normal(scale=0.8, size=len(time)),
        0.7 * tone + rng.normal(scale=0.8, size=len(time)),
        rng.normal(size=len(time)),
    ])
    result = coherence_matrices(values, sample_rate)
    frequency = result["frequency_hz"]
    coherence = result["coherence"]
    tone_bin = int(np.argmin(np.abs(frequency - 250.0)))
    assert coherence[tone_bin, 0, 1] > 0.8
    assert coherence[tone_bin, 0, 1] > coherence[tone_bin, 0, 2]


def test_sinusoid_fit_recovers_amplitude_and_variance() -> None:
    sample_rate = 10.0
    time = np.arange(1000) / sample_rate
    values = 2.5 * np.sin(2.0 * np.pi * 0.4 * time)
    result = sinusoid_fit_metrics(values, sample_rate, 0.4)
    assert np.isclose(result["sinusoid_amplitude"], 2.5, rtol=1e-3)
    assert result["sinusoid_variance_fraction"] > 0.999


def test_red_noise_test_rejects_null_for_strong_tone() -> None:
    sample_rate = 10.0
    time = np.arange(1200) / sample_rate
    rng = np.random.default_rng(11)
    values = 3.0 * np.sin(2.0 * np.pi * 0.4 * time) + rng.normal(size=len(time))
    rows, _ = red_noise_periodicity_pvalues(
        values, sample_rate, [0.4], repeats=100, seed=12
    )
    assert rows[0]["red_noise_pointwise_p"] < 0.05
    assert rows[0]["red_noise_search_familywise_p"] < 0.05


def test_parse_legacy_pulse_group() -> None:
    result = parse_group_name("non_vac/0930/二阶波-Δ2/0v20ms-10v10ms-12v10ms")
    assert result["source_mode"] == "non_vac"
    assert result["pulse_level_count"] == 3
    assert result["pulse_max_v"] == 12.0
    assert result["pulse_total_duration_ms"] == 40.0
    assert result["is_second_order_positive"]


def test_run_stop_classification_reports_stop_false_positives() -> None:
    spectral = pd.DataFrame({
        "dataset": [20260806] * 6,
        "condition": ["run", "30hz", "50hz", "vfd_stop", "vfd_stop", "vfd_stop"],
        "redistribution_score_db": [0.2, 0.15, 0.1, 0.12, 0.02, -0.05],
        "dual_band_run_signature": [True, True, True, True, False, False],
    })
    result = run_stop_exploratory_classification(spectral)
    direction = result.iloc[0]
    assert direction["true_run"] == 3
    assert direction["false_run_on_stop"] == 1
    assert np.isclose(direction["specificity"], 2.0 / 3.0)


def test_cwt_recovers_subhertz_tone() -> None:
    sample_rate = 10.0
    time = np.arange(1200) / sample_rate
    values = np.sin(2.0 * np.pi * 0.3 * time)
    result = cwt_analysis(values, sample_rate)["summary"]
    assert abs(result["global_peak_frequency_hz"] - 0.3) < 0.05
    assert result["significant_ridge_fraction"] > 0.5


def test_cwt_ar1_empirical_null_has_reasonable_false_positive_rate() -> None:
    rng = np.random.default_rng(1201)
    values = signal.lfilter([1.0], [1.0, -0.8], rng.normal(size=1500))
    result = cwt_analysis(values, 10.0)["summary"]
    assert 0.0 <= result["significant_point_fraction"] <= 0.15


def test_exponential_relaxation_recovers_tau() -> None:
    sample_rate = 10.0
    time = np.arange(200) / sample_rate
    values = 2.0 * np.exp(-time / 3.0) + 0.25
    result = fit_exponential_relaxation(values, 0, sample_rate)
    assert abs(result["relaxation_tau_s"] - 3.0) < 0.3
    assert result["relaxation_r2"] > 0.99


def test_benjamini_hochberg_is_monotone_in_rank() -> None:
    raw = np.array([0.001, 0.02, 0.5, 0.04])
    adjusted = benjamini_hochberg(raw)
    order = np.argsort(raw)
    assert np.all(np.diff(adjusted[order]) >= 0.0)
    assert adjusted[0] <= 0.01


def test_robust_pca_separates_sparse_outlier() -> None:
    time = np.linspace(-1.0, 1.0, 100)
    low_rank = np.column_stack([time, 2.0 * time, -time])
    observed = low_rank.copy()
    observed[50, 1] += 20.0
    recovered_low, recovered_sparse, _ = robust_pca(observed)
    assert np.argmax(np.abs(recovered_sparse)) == np.ravel_multi_index((50, 1), observed.shape)
    assert np.linalg.matrix_rank(recovered_low, tol=1e-3) <= 2


def test_recurrence_quantification_detects_periodic_structure() -> None:
    time = np.arange(600) / 10.0
    periodic = np.sin(2.0 * np.pi * 0.3 * time)
    rng = np.random.default_rng(101)
    noise = rng.normal(size=len(time))
    periodic_result = recurrence_features(periodic)
    noise_result = recurrence_features(noise)
    assert periodic_result["rqa_determinism"] > noise_result["rqa_determinism"]


def test_phase_amplitude_coupling_detects_known_modulation() -> None:
    sample_rate = 10.0
    time = np.arange(3000) / sample_rate
    phase_signal = np.sin(2.0 * np.pi * 0.1 * time)
    amplitude_signal = (
        1.0 + 0.8 * np.cos(2.0 * np.pi * 0.1 * time)
    ) * np.sin(2.0 * np.pi * 1.0 * time)
    result = phase_amplitude_coupling(
        phase_signal, amplitude_signal, sample_rate, (0.05, 0.15), 39, 314,
    )
    assert result["modulation_index"] > result["null_modulation_index_q95"]
    assert result["phase_randomized_null_p"] <= 0.05


def test_bicoherence_detects_quadratic_phase_coupling() -> None:
    rng = np.random.default_rng(2718)
    segment_count = 300
    frequency_count = 64
    first_bin = 7
    second_bin = 11
    spectra = (
        rng.normal(size=(segment_count, frequency_count))
        + 1j * rng.normal(size=(segment_count, frequency_count))
    ) * 0.05
    first_phase = rng.uniform(-np.pi, np.pi, segment_count)
    second_phase = rng.uniform(-np.pi, np.pi, segment_count)
    spectra[:, first_bin] += np.exp(1j * first_phase)
    spectra[:, second_bin] += np.exp(1j * second_phase)
    spectra[:, first_bin + second_bin] += np.exp(1j * (first_phase + second_phase))
    coupled = bicoherence_values(
        spectra, np.array([first_bin]), np.array([second_bin])
    )[0]
    unrelated = bicoherence_values(
        spectra, np.array([first_bin]), np.array([second_bin + 3])
    )[0]
    assert coupled > 0.8
    assert coupled > 10.0 * unrelated


def test_multifractal_dfa_white_noise_has_near_half_hurst_exponent() -> None:
    rng = np.random.default_rng(1618)
    result = multifractal_dfa(rng.normal(size=5000))
    assert 0.35 < result["mfdfa_h_q_2"] < 0.65
    assert result["mfdfa_scale_count"] >= 8


def test_aligned_multichannel_emd_finds_shared_band() -> None:
    sample_rate = 10.0
    time = np.arange(1200) / sample_rate
    shared = np.sin(2.0 * np.pi * 0.3 * time)
    matrix = np.column_stack([shared, 0.8 * shared, 1.2 * shared])
    result = aligned_multichannel_emd_features(matrix, sample_rate)
    assert result["aligned_emd_channel_presence_fraction_0p15_0p5hz"] == 1.0


def test_event_shape_model_prefers_double_exponential() -> None:
    sample_rate = 10.0
    time = np.arange(120) / sample_rate
    values = 2.0 * np.exp(-time / 0.8) + np.exp(-time / 6.0) + 0.2
    result = fit_event_shape_models(values, 0, sample_rate)
    assert result["preferred_shape_model"] == "double_exponential"
    assert result["preferred_to_second_delta_aicc"] > 4.0
    assert result["shape_parameters_identifiable"]


def test_matrix_pencil_finds_damped_frequency() -> None:
    sample_rate = 10.0
    time = np.arange(120) / sample_rate
    values = np.exp(-time / 4.0) * np.cos(2.0 * np.pi * 0.35 * time)
    poles = matrix_pencil_poles(values, sample_rate)
    physical = [row for row in poles if 0.2 <= row["frequency_hz"] <= 0.5]
    assert physical
    assert abs(physical[0]["frequency_hz"] - 0.35) < 0.05


def test_grouped_classifier_generalizes_shared_feature() -> None:
    rng = np.random.default_rng(577)
    groups = np.repeat(np.arange(6), 20)
    labels = np.tile(np.repeat(["off", "on"], 10), 6)
    shared = (labels == "on").astype(float) + rng.normal(scale=0.1, size=len(labels))
    nuisance = groups + rng.normal(scale=0.2, size=len(labels))
    features = np.column_stack([shared, nuisance])
    prediction, selected = grouped_predictions(
        features, labels, groups, np.array(["shared", "nuisance"]), 1
    )
    assert np.mean(prediction == labels) > 0.95
    assert selected["shared"] == 6
