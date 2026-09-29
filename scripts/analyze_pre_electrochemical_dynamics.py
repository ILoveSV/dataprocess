"""Mentor-aligned dynamics analysis for experiments before electrochemistry.

The exact archives are treated as a dynamic multi-channel measurement network.
The analysis deliberately separates within-record descriptive evidence from
independent experimental replication.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import signal

from scripts.channel_quality import assess_channel_quality, valid_channel_indices
from scripts.exact_tdms_archive import BAND_NAMES, load_exact_archive


EPS = 1e-30
ALLAN_TAUS_S = (0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0)
ENVELOPE_FEATURES = (
    "broadband_rms",
    "subkhz_rms",
    "fast_residual_rms",
    "difference_rms",
)
COHERENCE_BANDS_HZ = (
    ("1_5hz", 1.0, 5.0),
    ("5_100hz", 5.0, 100.0),
    ("100_500hz", 100.0, 500.0),
    ("500_1500hz", 500.0, 1500.0),
)
SLOW_PERIODICITY_MIN_HZ = 0.05
SLOW_PERIODICITY_MAX_HZ = 2.0
REFERENCE_WATER_PERIODICITY_HZ = 1.0 / 3.1


@dataclass(frozen=True)
class Case:
    dataset: str
    case_id: str
    archive: Path
    arrangement: str
    detector: str
    condition: str
    distance: str = ""
    carrier_khz: float | None = None
    output_hz: float | None = None

    @property
    def control_group(self) -> tuple[str, str, str, str]:
        return self.dataset, self.arrangement, self.detector, self.distance


def parse_case(dataset: str, archive: Path) -> Case:
    name = archive.name.lower()
    if dataset == "20260617":
        prefix = name.split("__", 1)[0]
        distance, state = prefix.split("_", 1)
        condition = "background" if state == "0hz" else state
        output_hz = None if condition == "background" else float(condition[:-2])
        return Case(dataset, archive.name, archive, distance, "unknown",
                    condition, distance=distance, output_hz=output_hz)

    if dataset == "20260731":
        session, state = name.split("_", 1)
        detector = "tc2" if session == "morning" else "tc1"
        condition = state
        output_hz = float(state[:-2]) if state in {"30hz", "50hz"} else None
        return Case(dataset, archive.name, archive, session, detector,
                    condition, output_hz=output_hz)

    if dataset == "20260806":
        parts = name.split("_")
        arrangement, detector = parts[0], parts[1]
        rest = "_".join(parts[2:])
        if rest in {"background", "vfd_stop", "30hz", "50hz"}:
            condition = rest
            output_hz = float(rest[:-2]) if rest in {"30hz", "50hz"} else None
            return Case(dataset, archive.name, archive, arrangement, detector,
                        condition, output_hz=output_hz)
        carrier = float(parts[2][:-1])
        output_hz = float(parts[3][:-2])
        return Case(dataset, archive.name, archive, arrangement, detector,
                    "run", carrier_khz=carrier, output_hz=output_hz)

    raise ValueError(f"Unsupported dataset: {dataset}")


def discover_cases(project_root: Path) -> list[Case]:
    roots = {
        "20260617": project_root / 'experiments/20260617/exact_archive',
        "20260731": project_root / 'experiments/20260731/tdms/exact_archive',
        "20260806": project_root / 'experiments/20260806/exact_archive',
    }
    cases: list[Case] = []
    for dataset, root in roots.items():
        if not root.is_dir():
            continue
        for archive in sorted(path for path in root.iterdir() if path.is_dir()):
            if (archive / "COMPLETE").exists():
                cases.append(parse_case(dataset, archive))
    return cases


def case_fields(case: Case) -> dict[str, object]:
    values = asdict(case)
    values.pop("archive")
    return values


def robust_scale(values: np.ndarray, axis: int = 0) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    center = np.nanmedian(values, axis=axis, keepdims=True)
    scale = 1.4826 * np.nanmedian(np.abs(values - center), axis=axis, keepdims=True)
    fallback = np.nanstd(values, axis=axis, keepdims=True)
    scale = np.where(np.isfinite(scale) & (scale > 1e-15), scale, fallback)
    return np.where(np.isfinite(scale) & (scale > 1e-15), scale, 1.0)


def detrended(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    if values.ndim == 1:
        if len(values) < 3:
            return values - np.nanmean(values)
        return signal.detrend(values, type="linear")
    if len(values) < 3:
        return values - np.nanmean(values, axis=0, keepdims=True)
    return signal.detrend(values, axis=0, type="linear")


def standardized(values: np.ndarray) -> np.ndarray:
    residual = detrended(values)
    return residual / robust_scale(residual, axis=0)


def trim_slice(metadata: dict[str, object], sample_rate: float, length: int) -> slice:
    config = metadata.get("config", {})
    start = int(round(float(config.get("trim_start_seconds", 0.0)) * sample_rate))
    end_trim = int(round(float(config.get("trim_end_seconds", 0.0)) * sample_rate))
    end = length - end_trim
    if end - start < max(30, int(round(3.0 * sample_rate))):
        return slice(0, length)
    return slice(start, end)


def autocorrelation_metrics(values: np.ndarray, sample_rate: float,
                            max_seconds: float = 20.0) -> dict[str, float]:
    x = detrended(np.asarray(values, dtype=np.float64))
    x -= np.mean(x)
    variance = float(np.mean(x * x))
    if len(x) < 4 or variance <= EPS:
        return {
            "acf_e_fold_s": np.nan,
            "acf_first_zero_s": np.nan,
            "acf_integral_positive_s": np.nan,
            "ar1_phi": np.nan,
            "ar1_tau_s": np.nan,
        }
    max_lag = min(len(x) - 2, int(round(max_seconds * sample_rate)), len(x) // 2)
    raw = signal.correlate(x, x, mode="full", method="fft")[len(x) - 1:len(x) + max_lag]
    overlap = np.arange(len(x), len(x) - len(raw), -1, dtype=np.float64)
    acf = raw / overlap
    acf /= max(acf[0], EPS)
    below = np.flatnonzero(acf <= math.exp(-1.0))
    zeros = np.flatnonzero(acf <= 0.0)
    first_zero = int(zeros[0]) if len(zeros) else len(acf) - 1
    integral = float(np.sum(np.maximum(acf[:first_zero + 1], 0.0)) / sample_rate)
    phi = float(np.dot(x[:-1], x[1:]) / max(np.dot(x[:-1], x[:-1]), EPS))
    tau = -1.0 / (sample_rate * math.log(phi)) if 0.0 < phi < 0.999999 else np.nan
    return {
        "acf_e_fold_s": float(below[0] / sample_rate) if len(below) else np.nan,
        "acf_first_zero_s": float(first_zero / sample_rate) if len(zeros) else np.nan,
        "acf_integral_positive_s": integral,
        "ar1_phi": phi,
        "ar1_tau_s": tau,
    }


def allan_deviation(values: np.ndarray, sample_rate: float,
                    taus_s: Iterable[float] = ALLAN_TAUS_S) -> list[dict[str, float]]:
    x = detrended(np.asarray(values, dtype=np.float64))
    base_scale = float(robust_scale(x, axis=0).squeeze())
    rows: list[dict[str, float]] = []
    for requested_tau in taus_s:
        cluster_size = max(1, int(round(requested_tau * sample_rate)))
        cluster_count = len(x) // cluster_size
        if cluster_count < 3:
            continue
        means = x[:cluster_count * cluster_size].reshape(cluster_count, cluster_size).mean(axis=1)
        adev = float(np.sqrt(0.5 * np.mean(np.diff(means) ** 2)))
        rows.append({
            "tau_s": cluster_size / sample_rate,
            "allan_deviation_v": adev,
            "allan_deviation_normalized": adev / max(base_scale, EPS),
            "cluster_count": cluster_count,
        })
    return rows


def lagged_correlation(values_a: np.ndarray, values_b: np.ndarray,
                       sample_rate: float, max_lag_s: float) -> dict[str, float]:
    x = standardized(np.asarray(values_a, dtype=np.float64)).reshape(-1)
    y = standardized(np.asarray(values_b, dtype=np.float64)).reshape(-1)
    n = min(len(x), len(y))
    x, y = x[:n], y[:n]
    max_lag = min(int(round(max_lag_s * sample_rate)), n // 3)
    lags = np.arange(-max_lag, max_lag + 1)
    correlations = np.empty(len(lags), dtype=np.float64)
    for index, lag in enumerate(lags):
        if lag < 0:
            a, b = x[-lag:], y[:n + lag]
        elif lag > 0:
            a, b = x[:n - lag], y[lag:]
        else:
            a, b = x, y
        correlations[index] = np.corrcoef(a, b)[0, 1] if len(a) >= 4 else np.nan
    best = int(np.nanargmax(np.abs(correlations)))
    zero = int(np.flatnonzero(lags == 0)[0])
    return {
        "zero_lag_correlation": float(correlations[zero]),
        "max_abs_lag_correlation": float(correlations[best]),
        "lag_at_max_abs_s": float(lags[best] / sample_rate),
    }


def lag_null_test(values_a: np.ndarray, values_b: np.ndarray, sample_rate: float,
                  observed_lag_s: float = 2.0,
                  null_min_lag_s: float = 7.0,
                  null_max_lag_s: float = 30.0) -> dict[str, float]:
    x = standardized(np.asarray(values_a, dtype=np.float64)).reshape(-1)
    y = standardized(np.asarray(values_b, dtype=np.float64)).reshape(-1)
    n = min(len(x), len(y))
    x, y = x[:n], y[:n]
    max_lag = min(int(round(null_max_lag_s * sample_rate)), n // 3)
    if max_lag < int(round(null_min_lag_s * sample_rate)):
        result = lagged_correlation(x, y, sample_rate, observed_lag_s)
        result.update({"lag_null_p": np.nan, "lag_null_center_count": 0})
        return result
    lags = np.arange(-max_lag, max_lag + 1)
    correlations = np.empty(len(lags), dtype=np.float64)
    for index, lag in enumerate(lags):
        if lag < 0:
            a, b = x[-lag:], y[:n + lag]
        elif lag > 0:
            a, b = x[:n - lag], y[lag:]
        else:
            a, b = x, y
        correlations[index] = np.corrcoef(a, b)[0, 1] if len(a) >= 4 else np.nan
    observed_use = np.abs(lags) <= int(round(observed_lag_s * sample_rate))
    observed_indices = np.flatnonzero(observed_use)
    best = int(observed_indices[np.nanargmax(np.abs(correlations[observed_use]))])
    half_width = int(round(observed_lag_s * sample_rate))
    step = max(1, int(round(sample_rate)))
    centers = np.arange(int(round(null_min_lag_s * sample_rate)), max_lag + 1, step)
    null_values = []
    for sign_value in (-1, 1):
        for center in centers:
            target = sign_value * center
            use = np.abs(lags - target) <= half_width
            if np.any(use):
                null_values.append(float(np.nanmax(np.abs(correlations[use]))))
    observed = float(abs(correlations[best]))
    p_value = ((np.sum(np.asarray(null_values) >= observed) + 1.0)
               / (len(null_values) + 1.0)) if null_values else np.nan
    return {
        "zero_lag_correlation": float(correlations[lags == 0][0]),
        "max_abs_lag_correlation": float(correlations[best]),
        "lag_at_max_abs_s": float(lags[best] / sample_rate),
        "lag_null_p": float(p_value),
        "lag_null_center_count": len(null_values),
    }


def principal_component(values: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    z = standardized(values)
    covariance = np.cov(z, rowvar=False)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = np.maximum(eigenvalues[order], 0.0)
    loadings = eigenvectors[:, order]
    if np.sum(loadings[:, 0]) < 0:
        loadings[:, 0] *= -1.0
    scores = z @ loadings
    ratios = eigenvalues / max(float(np.sum(eigenvalues)), EPS)
    return scores[:, 0], loadings[:, 0], ratios


def moving_block_bootstrap_difference(active: np.ndarray, control: np.ndarray,
                                      block_size: int, repeats: int = 1000,
                                      seed: int = 20260828) -> tuple[float, float]:
    rng = np.random.default_rng(seed)

    def draw(values: np.ndarray) -> np.ndarray:
        n = len(values)
        if n <= block_size:
            return values
        starts = rng.integers(0, n - block_size + 1,
                              size=int(math.ceil(n / block_size)))
        return np.concatenate([values[start:start + block_size] for start in starts])[:n]

    samples = np.empty(repeats, dtype=np.float64)
    for index in range(repeats):
        samples[index] = np.median(draw(active)) - np.median(draw(control))
    return float(np.percentile(samples, 2.5)), float(np.percentile(samples, 97.5))


def moving_block_bootstrap_channel_paired_difference(
    active_db: np.ndarray,
    control_db: np.ndarray,
    block_size: int,
    repeats: int = 1000,
    seed: int = 20260828,
) -> tuple[float, float]:
    """Bootstrap time blocks, then preserve channel pairing in the contrast."""
    rng = np.random.default_rng(seed)

    def draw_rows(values: np.ndarray) -> np.ndarray:
        row_count = len(values)
        if row_count <= block_size:
            return values
        starts = rng.integers(
            0, row_count - block_size + 1,
            size=int(math.ceil(row_count / block_size)),
        )
        return np.concatenate([
            values[start:start + block_size] for start in starts
        ], axis=0)[:row_count]

    samples = np.empty(repeats, dtype=np.float64)
    for index in range(repeats):
        active_channel_typical = np.median(draw_rows(active_db), axis=0)
        control_channel_typical = np.median(draw_rows(control_db), axis=0)
        samples[index] = np.median(active_channel_typical - control_channel_typical)
    return float(np.percentile(samples, 2.5)), float(np.percentile(samples, 97.5))


def line_tracks(frequency: np.ndarray, power: np.ndarray,
                bin_width_hz: float = 10.0,
                minimum_persistence: float = 0.05) -> list[dict[str, float]]:
    """Aggregate retained peak observations into narrow frequency bins."""
    frequency = np.asarray(frequency, dtype=np.float64)
    power = np.asarray(power, dtype=np.float64)
    n_segments = frequency.shape[0]
    bins: dict[int, list[tuple[int, float, float]]] = {}
    for segment_index in range(n_segments):
        segment_best: dict[int, tuple[float, float]] = {}
        for freq, value in zip(frequency[segment_index], power[segment_index]):
            key = int(np.rint(freq / bin_width_hz))
            current = segment_best.get(key)
            if current is None or value > current[1]:
                segment_best[key] = (float(freq), float(value))
        for key, (freq, value) in segment_best.items():
            bins.setdefault(key, []).append((segment_index, freq, value))
    rows = []
    for key, observations in bins.items():
        persistence = len(observations) / max(n_segments, 1)
        if persistence < minimum_persistence:
            continue
        freqs = np.array([item[1] for item in observations])
        powers = np.array([item[2] for item in observations])
        rows.append({
            "frequency_bin_hz": key * bin_width_hz,
            "median_frequency_hz": float(np.median(freqs)),
            "frequency_mad_hz": float(np.median(np.abs(freqs - np.median(freqs)))),
            "frequency_span_hz": float(np.max(freqs) - np.min(freqs)),
            "persistence_fraction": float(persistence),
            "observation_count": len(observations),
            "median_peak_power": float(np.median(powers)),
            "peak_power_db": float(10.0 * np.log10(max(np.median(powers), EPS))),
            "frequency_bin_width_hz": bin_width_hz,
        })
    return sorted(rows, key=lambda row: (-row["persistence_fraction"],
                                         -row["median_peak_power"]))


def coherence_matrices(values: np.ndarray, sample_rate: float,
                       nperseg: int = 8192,
                       minimum_segments: int = 8) -> dict[str, object]:
    """Estimate full-coverage multichannel magnitude-squared coherence."""
    x = np.asarray(values, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] < 2:
        raise ValueError("Coherence requires a samples-by-channels array")
    maximum_segment = max(256, 2 ** int(math.floor(math.log2(
        max(x.shape[0] // minimum_segments, 256)
    ))))
    segment_size = min(int(nperseg), maximum_segment, x.shape[0])
    if segment_size < 256:
        raise ValueError("Insufficient samples for coherence")
    starts = list(range(0, x.shape[0] - segment_size + 1, segment_size))
    final_start = x.shape[0] - segment_size
    if final_start >= 0 and (not starts or starts[-1] != final_start):
        starts.append(final_start)
    if len(starts) < 3:
        raise ValueError("Insufficient segments for coherence")

    window = signal.windows.hann(segment_size, sym=False)
    spectra = []
    for start in starts:
        segment_values = signal.detrend(
            x[start:start + segment_size], axis=0, type="linear"
        )
        spectra.append(np.fft.rfft(segment_values * window[:, None], axis=0))
    spectrum = np.asarray(spectra)
    auto = np.mean(np.abs(spectrum) ** 2, axis=0)
    channel_count = x.shape[1]
    coherence = np.empty(
        (spectrum.shape[1], channel_count, channel_count), dtype=np.float64
    )
    for channel_i in range(channel_count):
        for channel_j in range(channel_i, channel_count):
            cross = np.mean(
                spectrum[:, :, channel_i] * np.conj(spectrum[:, :, channel_j]),
                axis=0,
            )
            values_ij = np.abs(cross) ** 2 / np.maximum(
                auto[:, channel_i] * auto[:, channel_j], EPS
            )
            values_ij = np.clip(values_ij.real, 0.0, 1.0)
            coherence[:, channel_i, channel_j] = values_ij
            coherence[:, channel_j, channel_i] = values_ij
    frequency = np.fft.rfftfreq(segment_size, d=1.0 / sample_rate)
    null_95 = (1.0 - 0.05 ** (1.0 / (len(starts) - 1.0)))
    return {
        "frequency_hz": frequency,
        "coherence": coherence,
        "segment_count": len(starts),
        "segment_size": segment_size,
        "frequency_resolution_hz": sample_rate / segment_size,
        "pointwise_null_95": null_95,
    }


def low_rate_coherence_rows(
    case: Case,
    healthy: np.ndarray,
    metadata: dict[str, object],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    with np.load(case.archive / "low_rate.npz") as data:
        values = np.asarray(data["low_rate_v"], dtype=np.float64)
        sample_rate = float(data["low_rate_hz"])
    values = values[trim_slice(metadata, sample_rate, len(values))][:, healthy]
    result = coherence_matrices(values, sample_rate)
    frequency = np.asarray(result["frequency_hz"])
    coherence = np.asarray(result["coherence"])
    null_95 = float(result["pointwise_null_95"])
    fields = case_fields(case)
    pair_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []

    for band_name, low_hz, high_hz in COHERENCE_BANDS_HZ:
        use = (frequency >= low_hz) & (frequency < high_hz)
        if not np.any(use):
            continue
        band_pair_rows = []
        for local_i in range(len(healthy)):
            for local_j in range(local_i + 1, len(healthy)):
                spectrum = coherence[use, local_i, local_j]
                band_frequency = frequency[use]
                peak_index = int(np.argmax(spectrum))
                row = {
                    **fields,
                    "band_name": band_name,
                    "channel_i": int(healthy[local_i] + 1),
                    "channel_j": int(healthy[local_j] + 1),
                    "median_coherence": float(np.median(spectrum)),
                    "q95_coherence": float(np.percentile(spectrum, 95)),
                    "maximum_coherence": float(spectrum[peak_index]),
                    "maximum_coherence_frequency_hz": float(band_frequency[peak_index]),
                    "fraction_bins_above_pointwise_null_95": float(np.mean(spectrum > null_95)),
                    "pointwise_null_95": null_95,
                    "segment_count": int(result["segment_count"]),
                    "segment_size": int(result["segment_size"]),
                    "frequency_resolution_hz": float(result["frequency_resolution_hz"]),
                }
                pair_rows.append(row)
                band_pair_rows.append(row)
        median_values = np.array([row["median_coherence"] for row in band_pair_rows])
        q95_values = np.array([row["q95_coherence"] for row in band_pair_rows])
        exceedance = np.array([
            row["fraction_bins_above_pointwise_null_95"] for row in band_pair_rows
        ])
        summary_rows.append({
            **fields,
            "band_name": band_name,
            "healthy_channel_count": len(healthy),
            "channel_pair_count": len(band_pair_rows),
            "median_pair_median_coherence": float(np.median(median_values)),
            "q75_pair_median_coherence": float(np.percentile(median_values, 75)),
            "median_pair_q95_coherence": float(np.median(q95_values)),
            "median_pair_fraction_bins_above_null_95": float(np.median(exceedance)),
            "pointwise_null_95": null_95,
            "segment_count": int(result["segment_count"]),
            "frequency_resolution_hz": float(result["frequency_resolution_hz"]),
        })
    return pair_rows, summary_rows


def sinusoid_fit_metrics(values: np.ndarray, sample_rate: float,
                         frequency_hz: float) -> dict[str, float]:
    x = detrended(np.asarray(values, dtype=np.float64)).reshape(-1)
    time = np.arange(len(x), dtype=np.float64) / sample_rate
    design = np.column_stack([
        np.sin(2.0 * np.pi * frequency_hz * time),
        np.cos(2.0 * np.pi * frequency_hz * time),
    ])
    coefficients, _, _, _ = np.linalg.lstsq(design, x, rcond=None)
    fitted = design @ coefficients
    amplitude = float(np.hypot(coefficients[0], coefficients[1]))
    variance_fraction = float(np.sum(fitted ** 2) / max(np.sum(x ** 2), EPS))
    phase = float(np.arctan2(coefficients[1], coefficients[0]))
    return {
        "sinusoid_amplitude": amplitude,
        "sinusoid_variance_fraction": variance_fraction,
        "sinusoid_phase_rad": phase,
    }


def red_noise_periodicity_pvalues(
    values: np.ndarray,
    sample_rate: float,
    candidate_frequencies_hz: list[float],
    repeats: int = 500,
    seed: int = 20260828,
) -> tuple[list[dict[str, float]], float]:
    x = detrended(np.asarray(values, dtype=np.float64)).reshape(-1)
    x /= max(float(np.std(x)), math.sqrt(EPS))
    phi = float(np.dot(x[:-1], x[1:]) / max(np.dot(x[:-1], x[:-1]), EPS))
    phi = float(np.clip(phi, -0.99, 0.99))
    window = signal.windows.hann(len(x), sym=False)
    frequency = np.fft.rfftfreq(len(x), d=1.0 / sample_rate)
    observed_power = np.abs(np.fft.rfft(x * window)) ** 2
    search = ((frequency >= SLOW_PERIODICITY_MIN_HZ)
              & (frequency <= SLOW_PERIODICITY_MAX_HZ))

    rng = np.random.default_rng(seed)
    burn_in = max(200, min(2000, len(x)))
    innovation = rng.normal(size=(repeats, len(x) + burn_in))
    surrogate = signal.lfilter([math.sqrt(max(1.0 - phi ** 2, EPS))],
                               [1.0, -phi], innovation, axis=1)[:, burn_in:]
    surrogate = signal.detrend(surrogate, axis=1, type="linear")
    surrogate /= np.maximum(np.std(surrogate, axis=1, keepdims=True), math.sqrt(EPS))
    surrogate_power = np.abs(np.fft.rfft(
        surrogate * window[None, :], axis=1
    )) ** 2
    surrogate_search_max = np.max(surrogate_power[:, search], axis=1)
    pvalues = []
    for candidate in candidate_frequencies_hz:
        nearest = int(np.argmin(np.abs(frequency - candidate)))
        observed = float(observed_power[nearest])
        pointwise = float((np.sum(surrogate_power[:, nearest] >= observed) + 1.0)
                          / (repeats + 1.0))
        familywise = float((np.sum(surrogate_search_max >= observed) + 1.0)
                           / (repeats + 1.0))
        pvalues.append({
            "red_noise_pointwise_p": pointwise,
            "red_noise_search_familywise_p": familywise,
        })
    return pvalues, phi


def segmented_phase_metrics(values: np.ndarray, sample_rate: float,
                            frequency_hz: float,
                            segment_count: int = 3) -> dict[str, float]:
    x = detrended(np.asarray(values, dtype=np.float64)).reshape(-1)
    boundaries = np.linspace(0, len(x), segment_count + 1, dtype=int)
    phases = []
    amplitudes = []
    for start, end in zip(boundaries[:-1], boundaries[1:]):
        time = np.arange(start, end, dtype=np.float64) / sample_rate
        design = np.column_stack([
            np.sin(2.0 * np.pi * frequency_hz * time),
            np.cos(2.0 * np.pi * frequency_hz * time),
        ])
        coefficients, _, _, _ = np.linalg.lstsq(design, x[start:end], rcond=None)
        amplitudes.append(float(np.hypot(coefficients[0], coefficients[1])))
        phases.append(float(np.arctan2(coefficients[1], coefficients[0])))
    phase_resultant = abs(np.mean(np.exp(1j * np.asarray(phases))))
    amplitude_cv = np.std(amplitudes) / max(np.mean(amplitudes), math.sqrt(EPS))
    return {
        "segmented_phase_resultant": float(phase_resultant),
        "segmented_amplitude_cv": float(amplitude_cv),
        "phase_segment_count": segment_count,
    }


def slow_periodicity_rows(case: Case, slow: np.ndarray, healthy: np.ndarray,
                          sample_rate: float) -> list[dict[str, object]]:
    duration_s = len(slow) / sample_rate
    if duration_s < 30.0:
        return []
    selected = slow[:, healthy]
    pc1, _, _ = principal_component(selected)
    pc1 = detrended(pc1)
    frequency = np.fft.rfftfreq(len(pc1), d=1.0 / sample_rate)
    window = signal.windows.hann(len(pc1), sym=False)
    pc1_power = np.abs(np.fft.rfft(pc1 * window)) ** 2
    search = ((frequency >= SLOW_PERIODICITY_MIN_HZ)
              & (frequency <= SLOW_PERIODICITY_MAX_HZ))
    search_indices = np.flatnonzero(search)
    peaks, _ = signal.find_peaks(pc1_power[search])
    ranked = search_indices[peaks[np.argsort(pc1_power[search][peaks])[::-1]]]
    candidate_frequencies = [REFERENCE_WATER_PERIODICITY_HZ]
    for index in ranked:
        candidate = float(frequency[index])
        resolution = sample_rate / len(pc1)
        if all(abs(candidate - existing) > 2.0 * resolution
               for existing in candidate_frequencies):
            candidate_frequencies.append(candidate)
        if len(candidate_frequencies) >= 6:
            break
    red_noise, red_noise_phi = red_noise_periodicity_pvalues(
        pc1,
        sample_rate,
        candidate_frequencies,
        seed=20260828 + sum(case.case_id.encode("utf-8")),
    )

    fields = case_fields(case)
    rows = []
    half = len(pc1) // 2
    half_resolution = sample_rate / max(half, 1)
    half_peaks = []
    for values in (pc1[:half], pc1[-half:]):
        half_frequency = np.fft.rfftfreq(len(values), d=1.0 / sample_rate)
        half_power = np.abs(np.fft.rfft(
            detrended(values) * signal.windows.hann(len(values), sym=False)
        )) ** 2
        half_use = ((half_frequency >= SLOW_PERIODICITY_MIN_HZ)
                    & (half_frequency <= SLOW_PERIODICITY_MAX_HZ))
        half_peaks.append((half_frequency, half_power, half_use))

    channel_frequency = np.fft.rfftfreq(len(pc1), d=1.0 / sample_rate)
    channel_power = np.abs(np.fft.rfft(
        detrended(selected) * window[:, None], axis=0
    )) ** 2
    for candidate_index, candidate in enumerate(candidate_frequencies):
        nearest = int(np.argmin(np.abs(frequency - candidate)))
        local = ((frequency >= candidate - 0.2)
                 & (frequency <= candidate + 0.2)
                 & (np.abs(frequency - frequency[nearest]) > 2.0 * sample_rate / len(pc1)))
        local_floor = float(np.median(pc1_power[local])) if np.any(local) else np.nan
        prominence_db = float(10.0 * np.log10(
            max(pc1_power[nearest], EPS) / max(local_floor, EPS)
        )) if np.isfinite(local_floor) else np.nan
        pc_fit = sinusoid_fit_metrics(pc1, sample_rate, candidate)
        phase_metrics = segmented_phase_metrics(pc1, sample_rate, candidate)
        channel_fits = [
            sinusoid_fit_metrics(selected[:, index], sample_rate, candidate)
            for index in range(selected.shape[1])
        ]
        channel_r2 = np.array([
            fit["sinusoid_variance_fraction"] for fit in channel_fits
        ])
        tolerance = max(2.0 * sample_rate / len(pc1), 0.02)
        channel_peak_support = []
        for channel_index in range(selected.shape[1]):
            local_search = ((channel_frequency >= max(
                SLOW_PERIODICITY_MIN_HZ, candidate - 0.1
            )) & (channel_frequency <= min(
                SLOW_PERIODICITY_MAX_HZ, candidate + 0.1
            )))
            if not np.any(local_search):
                channel_peak_support.append(False)
                continue
            local_indices = np.flatnonzero(local_search)
            peak_index = local_indices[np.argmax(channel_power[local_search, channel_index])]
            channel_peak_support.append(
                abs(channel_frequency[peak_index] - candidate) <= tolerance
            )
        half_support = []
        half_peak_frequency = []
        for half_frequency, half_power, half_use in half_peaks:
            use = (half_frequency >= candidate - 0.1) & (half_frequency <= candidate + 0.1)
            use &= half_use
            local_indices = np.flatnonzero(use)
            if len(local_indices):
                best = local_indices[np.argmax(half_power[local_indices])]
                best_frequency = float(half_frequency[best])
                half_peak_frequency.append(best_frequency)
                half_support.append(abs(best_frequency - candidate) <= max(
                    2.0 * half_resolution, 0.03
                ))
            else:
                half_peak_frequency.append(np.nan)
                half_support.append(False)
        rows.append({
            **fields,
            "candidate_rank": candidate_index,
            "candidate_type": "fixed_3p1s" if candidate_index == 0 else "pc1_search_peak",
            "candidate_frequency_hz": candidate,
            "candidate_period_s": 1.0 / candidate,
            "frequency_resolution_hz": sample_rate / len(pc1),
            "cycle_count": duration_s * candidate,
            "pc1_sinusoid_amplitude_standardized": pc_fit["sinusoid_amplitude"],
            "pc1_sinusoid_variance_fraction": pc_fit["sinusoid_variance_fraction"],
            "pc1_local_prominence_db": prominence_db,
            "pc1_ar1_phi_for_red_noise": red_noise_phi,
            **red_noise[candidate_index],
            **phase_metrics,
            "median_channel_sinusoid_variance_fraction": float(np.median(channel_r2)),
            "q75_channel_sinusoid_variance_fraction": float(np.percentile(channel_r2, 75)),
            "channel_peak_support_fraction": float(np.mean(channel_peak_support)),
            "first_half_local_peak_hz": half_peak_frequency[0],
            "second_half_local_peak_hz": half_peak_frequency[1],
            "both_halves_support_candidate": bool(all(half_support)),
            "healthy_channel_count": len(healthy),
        })
    return rows


def case_time_arrays(case: Case) -> tuple[dict[str, object], dict[str, np.ndarray], float]:
    metadata = json.loads((case.archive / "metadata.json").read_text(encoding="utf-8"))
    with np.load(case.archive / "envelopes.npz") as data:
        arrays = {name: np.asarray(data[name], dtype=np.float64)
                  for name in ("slow_mean",) + ENVELOPE_FEATURES}
        sample_rate = float(data["envelope_rate_hz"])
    use = trim_slice(metadata, sample_rate, len(arrays["slow_mean"]))
    return metadata, {name: value[use] for name, value in arrays.items()}, sample_rate


def process_case(case: Case) -> dict[str, list[dict[str, object]]]:
    result = load_exact_archive(case.archive)
    quality = assess_channel_quality(result)
    healthy = valid_channel_indices(result)
    metadata, arrays, fs = case_time_arrays(case)
    slow = arrays["slow_mean"]
    fields = case_fields(case)
    outputs: dict[str, list[dict[str, object]]] = {
        "health": [], "slow": [], "allan": [], "network": [], "pairs": [],
        "coupling": [], "band": [], "lines": [], "line_support": [],
        "low_rate_coherence_pairs": [], "low_rate_coherence_summary": [],
        "slow_periodicity": [],
    }

    for row in quality:
        outputs["health"].append({**fields, **row})

    for channel_index in range(slow.shape[1]):
        values = slow[:, channel_index]
        time = np.arange(len(values), dtype=np.float64) / fs
        slope = float(np.polyfit(time, values, 1)[0]) if len(values) >= 3 else np.nan
        residual = detrended(values)
        metrics = autocorrelation_metrics(values, fs)
        outputs["slow"].append({
            **fields,
            "channel_index": channel_index + 1,
            "automatic_bad": bool(quality[channel_index]["automatic_bad"]),
            "automatic_suspect": bool(quality[channel_index]["automatic_suspect"]),
            "trimmed_sample_count": len(values),
            "trimmed_duration_s": len(values) / fs,
            "slow_std_v": float(np.std(residual)),
            "slow_robust_sigma_v": float(robust_scale(residual).squeeze()),
            "slow_linear_slope_v_per_s": slope,
            "slow_start_end_delta_v": float(values[-1] - values[0]),
            **metrics,
        })
        for allan in allan_deviation(values, fs):
            outputs["allan"].append({
                **fields,
                "channel_index": channel_index + 1,
                "automatic_bad": bool(quality[channel_index]["automatic_bad"]),
                **allan,
            })

    selected_slow = slow[:, healthy]
    pc, loadings, ratios = principal_component(selected_slow)
    z = standardized(selected_slow)
    corr = np.corrcoef(z, rowvar=False)
    upper = corr[np.triu_indices(len(healthy), 1)]
    pair_rows = []
    for local_i in range(len(healthy)):
        for local_j in range(local_i + 1, len(healthy)):
            lag = lagged_correlation(z[:, local_i], z[:, local_j], fs, 2.0)
            pair_rows.append({
                **fields,
                "channel_i": healthy[local_i] + 1,
                "channel_j": healthy[local_j] + 1,
                **lag,
            })
    outputs["pairs"].extend(pair_rows)
    outputs["network"].append({
        **fields,
        "healthy_channel_count": len(healthy),
        "healthy_channels": ";".join(str(index + 1) for index in healthy),
        "pca_first_ratio": float(ratios[0]),
        "pca_first_two_ratio": float(np.sum(ratios[:2])),
        "pca_components_90": int(np.searchsorted(np.cumsum(ratios), 0.9) + 1),
        "pca_first_loading_abs_cv": float(np.std(np.abs(loadings))
                                          / max(np.mean(np.abs(loadings)), EPS)),
        "pair_corr_median": float(np.median(upper)),
        "pair_abs_corr_median": float(np.median(np.abs(upper))),
        "pair_abs_corr_max": float(np.max(np.abs(upper))),
        "pair_max_lag_abs_corr_median": float(np.median([
            abs(row["max_abs_lag_correlation"]) for row in pair_rows
        ])),
        "pair_ratio_abs_corr_gt_0p5": float(np.mean(np.abs(upper) > 0.5)),
        "pc1_acf_e_fold_s": autocorrelation_metrics(pc, fs)["acf_e_fold_s"],
    })

    coherence_pairs, coherence_summary = low_rate_coherence_rows(
        case, healthy, metadata
    )
    outputs["low_rate_coherence_pairs"].extend(coherence_pairs)
    outputs["low_rate_coherence_summary"].extend(coherence_summary)
    outputs["slow_periodicity"].extend(
        slow_periodicity_rows(case, slow, healthy, fs)
    )

    for feature in ENVELOPE_FEATURES:
        log_envelope = np.log10(np.maximum(arrays[feature], EPS))
        for channel_index in healthy:
            coupling = lag_null_test(
                slow[:, channel_index], log_envelope[:, channel_index], fs
            )
            outputs["coupling"].append({
                **fields,
                "scope": "same_channel",
                "channel_index": channel_index + 1,
                "envelope_feature": feature,
                **coupling,
            })
        envelope_pc, _, _ = principal_component(log_envelope[:, healthy])
        coupling = lag_null_test(pc, envelope_pc, fs)
        outputs["coupling"].append({
            **fields,
            "scope": "common_pc1",
            "channel_index": 0,
            "envelope_feature": feature,
            **coupling,
        })

    segment_power = np.asarray(result["welch_segment_bandpower"], dtype=np.float64)
    segment_time = np.asarray(result["welch_segment_time_s"], dtype=np.float64)
    for band_index, band_name in enumerate(BAND_NAMES):
        channel_db = 10.0 * np.log10(np.maximum(
            segment_power[:, healthy, band_index], EPS
        ))
        trajectory = np.median(channel_db, axis=1)
        slope = float(np.polyfit(segment_time, trajectory, 1)[0]) if len(trajectory) >= 3 else np.nan
        median = float(np.median(trajectory))
        mad = float(1.4826 * np.median(np.abs(trajectory - median)))
        outputs["band"].append({
            **fields,
            "band_name": band_name,
            "healthy_channel_count": len(healthy),
            "segment_count": len(trajectory),
            "segment_median_db": median,
            "segment_iqr_db": float(np.percentile(trajectory, 75) - np.percentile(trajectory, 25)),
            "segment_robust_sigma_db": mad,
            "temporal_slope_db_per_s": slope,
            "high_event_fraction": float(np.mean(trajectory > median + 3.0 * max(mad, 1e-12))),
            **{f"trajectory_{key}": value for key, value in
               autocorrelation_metrics(trajectory, 1.0 / np.median(np.diff(segment_time)), 15.0).items()},
        })

    peak_frequency = np.asarray(result["welch_segment_peak_frequency_hz"], dtype=np.float64)
    peak_power = np.asarray(result["welch_segment_peak_power"], dtype=np.float64)
    retained_by_channel: dict[int, list[dict[str, float]]] = {}
    for channel_index in healthy:
        tracks = line_tracks(peak_frequency[:, channel_index, :],
                             peak_power[:, channel_index, :])[:30]
        retained_by_channel[channel_index] = tracks
        for rank, track in enumerate(tracks, start=1):
            outputs["lines"].append({
                **fields,
                "channel_index": channel_index + 1,
                "rank_within_channel": rank,
                **track,
            })
    support_bins: dict[int, list[tuple[int, dict[str, float]]]] = {}
    for channel_index, tracks in retained_by_channel.items():
        for track in tracks:
            key = int(np.rint(track["median_frequency_hz"] / 20.0))
            support_bins.setdefault(key, []).append((channel_index, track))
    support_rows = []
    for key, observations in support_bins.items():
        best_by_channel: dict[int, dict[str, float]] = {}
        for channel_index, track in observations:
            current = best_by_channel.get(channel_index)
            if current is None or track["persistence_fraction"] > current["persistence_fraction"]:
                best_by_channel[channel_index] = track
        tracks = list(best_by_channel.values())
        support_rows.append({
            **fields,
            "frequency_bin_hz": key * 20.0,
            "median_frequency_hz": float(np.median([
                track["median_frequency_hz"] for track in tracks
            ])),
            "channel_support_count": len(tracks),
            "channel_support_fraction": len(tracks) / len(healthy),
            "median_persistence_fraction": float(np.median([
                track["persistence_fraction"] for track in tracks
            ])),
            "max_persistence_fraction": float(np.max([
                track["persistence_fraction"] for track in tracks
            ])),
            "median_peak_power_db": float(np.median([
                track["peak_power_db"] for track in tracks
            ])),
        })
    outputs["line_support"].extend(sorted(
        support_rows,
        key=lambda row: (-row["channel_support_count"],
                         -row["median_persistence_fraction"]),
    )[:80])
    return outputs


def matched_controls(case: Case, cases: list[Case]) -> list[Case]:
    if case.condition == "background":
        return []
    candidates = [item for item in cases if item.control_group == case.control_group]
    if case.condition == "vfd_stop":
        return [item for item in candidates if item.condition == "background"]
    return [item for item in candidates if item.condition in {"background", "vfd_stop"}]


def matched_band_contrasts(cases: list[Case]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    cache: dict[str, dict[str, object]] = {}

    def loaded(case: Case) -> dict[str, object]:
        if case.case_id not in cache:
            cache[case.case_id] = load_exact_archive(case.archive)
        return cache[case.case_id]

    for case in cases:
        active = loaded(case)
        for control in matched_controls(case, cases):
            background = loaded(control)
            common = sorted(set(valid_channel_indices(active))
                            & set(valid_channel_indices(background)))
            if len(common) < 4:
                continue
            active_power = np.asarray(active["welch_segment_bandpower"], dtype=np.float64)
            control_power = np.asarray(background["welch_segment_bandpower"], dtype=np.float64)
            active_time = np.asarray(active["welch_segment_time_s"], dtype=np.float64)
            step_s = float(np.median(np.diff(active_time))) if len(active_time) > 1 else 1.0
            for band_index, band_name in enumerate(BAND_NAMES):
                active_channel_db = 10.0 * np.log10(np.maximum(
                    active_power[:, common, band_index], EPS
                ))
                control_channel_db = 10.0 * np.log10(np.maximum(
                    control_power[:, common, band_index], EPS
                ))
                a = np.median(active_channel_db, axis=1)
                b = np.median(control_channel_db, axis=1)
                delta = float(np.median(a) - np.median(b))
                channel_typical_contrast = (
                    np.median(active_channel_db, axis=0)
                    - np.median(control_channel_db, axis=0)
                )
                active_channel_mean_db = 10.0 * np.log10(np.maximum(
                    np.mean(active_power[:, common, band_index], axis=0), EPS
                ))
                control_channel_mean_db = 10.0 * np.log10(np.maximum(
                    np.mean(control_power[:, common, band_index], axis=0), EPS
                ))
                mean_power_channel_contrast = active_channel_mean_db - control_channel_mean_db
                active_aggregate_power = np.median(
                    active_power[:, common, band_index], axis=1
                )
                control_aggregate_power = np.median(
                    control_power[:, common, band_index], axis=1
                )

                def top_fraction_share(values: np.ndarray, fraction: float = 0.1) -> float:
                    count = max(1, int(math.ceil(len(values) * fraction)))
                    return float(np.sum(np.sort(values)[-count:]) / max(np.sum(values), EPS))

                block_size = max(1, int(round(5.0 / step_s)))
                ci_low, ci_high = moving_block_bootstrap_channel_paired_difference(
                    active_channel_db, control_channel_db, block_size=block_size,
                    seed=20260828 + band_index,
                )
                channel_typical = float(np.median(channel_typical_contrast))
                mean_power = float(np.median(mean_power_channel_contrast))
                rows.append({
                    **case_fields(case),
                    "reference_case_id": control.case_id,
                    "reference_condition": control.condition,
                    "band_name": band_name,
                    "common_healthy_channel_count": len(common),
                    "common_healthy_channels": ";".join(str(index + 1) for index in common),
                    "median_difference_db": delta,
                    "aggregate_trajectory_median_difference_db": delta,
                    "median_channel_typical_difference_db": channel_typical,
                    "channel_typical_q25_difference_db": float(
                        np.percentile(channel_typical_contrast, 25)
                    ),
                    "channel_typical_q75_difference_db": float(
                        np.percentile(channel_typical_contrast, 75)
                    ),
                    "channel_typical_positive_fraction": float(
                        np.mean(channel_typical_contrast > 0.0)
                    ),
                    "moving_block_bootstrap_ci_low_db": ci_low,
                    "moving_block_bootstrap_ci_high_db": ci_high,
                    "temporal_superiority_fraction": float(np.mean(a[:, None] > b[None, :])),
                    "mean_power_median_channel_difference_db": mean_power,
                    "mean_power_q25_channel_difference_db": float(
                        np.percentile(mean_power_channel_contrast, 25)
                    ),
                    "mean_power_q75_channel_difference_db": float(
                        np.percentile(mean_power_channel_contrast, 75)
                    ),
                    "mean_power_positive_channel_fraction": float(
                        np.mean(mean_power_channel_contrast > 0.0)
                    ),
                    "mean_power_minus_typical_difference_db": float(
                        mean_power - channel_typical
                    ),
                    "active_top10_segment_power_fraction": top_fraction_share(active_aggregate_power),
                    "reference_top10_segment_power_fraction": top_fraction_share(control_aggregate_power),
                    "active_temporal_iqr_db": float(np.percentile(a, 75) - np.percentile(a, 25)),
                    "reference_temporal_iqr_db": float(np.percentile(b, 75) - np.percentile(b, 25)),
                    "bootstrap_block_seconds": 5.0,
                    "segments_are_not_independent_replicates": True,
                })
    return rows


def peak_presence_metrics(
    peak_frequency: np.ndarray,
    peak_power: np.ndarray,
    channel_indices: list[int],
    target_frequency_hz: float,
    tolerance_hz: float,
) -> dict[str, float]:
    persistence = []
    observed_frequency = []
    observed_power = []
    for channel_index in channel_indices:
        channel_frequency = peak_frequency[:, channel_index, :]
        channel_power = peak_power[:, channel_index, :]
        near = np.abs(channel_frequency - target_frequency_hz) <= tolerance_hz
        present = np.any(near, axis=1)
        persistence.append(float(np.mean(present)))
        if np.any(near):
            observed_frequency.extend(channel_frequency[near].tolist())
            observed_power.extend(channel_power[near].tolist())
    observed_frequency_array = np.asarray(observed_frequency, dtype=float)
    observed_power_array = np.asarray(observed_power, dtype=float)
    return {
        "median_channel_presence_fraction": float(np.median(persistence)),
        "channel_fraction_presence_ge_0p2": float(np.mean(np.asarray(persistence) >= 0.2)),
        "channel_fraction_presence_ge_0p5": float(np.mean(np.asarray(persistence) >= 0.5)),
        "observed_peak_count": len(observed_frequency),
        "observed_frequency_median_hz": (
            float(np.median(observed_frequency_array)) if len(observed_frequency) else np.nan
        ),
        "observed_frequency_mad_hz": (
            float(np.median(np.abs(
                observed_frequency_array - np.median(observed_frequency_array)
            ))) if len(observed_frequency) else np.nan
        ),
        "observed_peak_power_median_db": (
            float(10.0 * np.log10(max(np.median(observed_power_array), EPS)))
            if len(observed_power) else np.nan
        ),
    }


def matched_narrow_line_contrasts(cases: list[Case]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    cache: dict[str, dict[str, object]] = {}

    def loaded(case: Case) -> dict[str, object]:
        if case.case_id not in cache:
            cache[case.case_id] = load_exact_archive(case.archive)
        return cache[case.case_id]

    for case in cases:
        active = loaded(case)
        for control in matched_controls(case, cases):
            reference = loaded(control)
            common = sorted(set(valid_channel_indices(active))
                            & set(valid_channel_indices(reference)))
            if len(common) < 4:
                continue
            frequency = np.asarray(active["frequency"], dtype=float)
            active_psd = np.asarray(active["psd"], dtype=float)
            reference_psd = np.asarray(reference["psd"], dtype=float)
            active_aggregate = np.median(active_psd[common], axis=0)
            reference_aggregate = np.median(reference_psd[common], axis=0)
            active_db = 10.0 * np.log10(np.maximum(active_aggregate, EPS))
            smooth_window = min(2001, len(active_db) - (1 - len(active_db) % 2))
            smooth_window = max(5, smooth_window)
            if smooth_window % 2 == 0:
                smooth_window -= 1
            local_excess = active_db - signal.savgol_filter(active_db, smooth_window, 2)
            same_bin_contrast = 10.0 * np.log10(
                np.maximum(active_aggregate, EPS) / np.maximum(reference_aggregate, EPS)
            )
            use = (frequency >= 1000.0) & (frequency <= 195000.0)
            candidates, _ = signal.find_peaks(
                local_excess, height=5.0, prominence=2.0, distance=8
            )
            candidates = candidates[
                use[candidates] & (same_bin_contrast[candidates] >= 3.0)
            ]
            if not len(candidates):
                continue
            score = local_excess[candidates] + same_bin_contrast[candidates]
            candidates = candidates[np.argsort(score)[::-1][:30]]
            frequency_resolution = float(np.median(np.diff(frequency)))
            tolerance_hz = 300.0
            half_width = max(1, int(math.ceil(tolerance_hz / frequency_resolution)))
            active_peak_frequency = np.asarray(
                active["welch_segment_peak_frequency_hz"], dtype=float
            )
            active_peak_power = np.asarray(
                active["welch_segment_peak_power"], dtype=float
            )
            reference_peak_frequency = np.asarray(
                reference["welch_segment_peak_frequency_hz"], dtype=float
            )
            reference_peak_power = np.asarray(
                reference["welch_segment_peak_power"], dtype=float
            )
            for rank, peak_index in enumerate(candidates, start=1):
                start = max(0, peak_index - half_width)
                end = min(len(frequency), peak_index + half_width + 1)
                reference_local_index = start + int(np.argmax(
                    reference_aggregate[start:end]
                ))
                neighborhood_contrast = 10.0 * np.log10(
                    max(active_aggregate[peak_index], EPS)
                    / max(reference_aggregate[reference_local_index], EPS)
                )
                channel_same_bin_contrast = 10.0 * np.log10(
                    np.maximum(active_psd[common, peak_index], EPS)
                    / np.maximum(reference_psd[common, peak_index], EPS)
                )
                active_presence = peak_presence_metrics(
                    active_peak_frequency, active_peak_power, common,
                    float(frequency[peak_index]), tolerance_hz,
                )
                reference_presence = peak_presence_metrics(
                    reference_peak_frequency, reference_peak_power, common,
                    float(frequency[peak_index]), tolerance_hz,
                )
                rows.append({
                    **case_fields(case),
                    "reference_case_id": control.case_id,
                    "reference_condition": control.condition,
                    "rank": rank,
                    "frequency_hz": float(frequency[peak_index]),
                    "local_line_excess_db": float(local_excess[peak_index]),
                    "same_bin_aggregate_contrast_db": float(
                        same_bin_contrast[peak_index]
                    ),
                    "reference_neighborhood_peak_frequency_hz": float(
                        frequency[reference_local_index]
                    ),
                    "reference_neighborhood_peak_offset_hz": float(
                        frequency[reference_local_index] - frequency[peak_index]
                    ),
                    "contrast_to_reference_neighborhood_peak_db": float(
                        neighborhood_contrast
                    ),
                    "robust_new_or_enhanced_line_ge_3db": bool(
                        neighborhood_contrast >= 3.0
                    ),
                    "median_channel_same_bin_contrast_db": float(
                        np.median(channel_same_bin_contrast)
                    ),
                    "channel_support_fraction_same_bin_gt3db": float(
                        np.mean(channel_same_bin_contrast > 3.0)
                    ),
                    "channel_support_fraction_same_bin_gt6db": float(
                        np.mean(channel_same_bin_contrast > 6.0)
                    ),
                    "common_healthy_channel_count": len(common),
                    "peak_tracking_tolerance_hz": tolerance_hz,
                    **{f"active_{key}": value for key, value in active_presence.items()},
                    **{f"reference_{key}": value for key, value in reference_presence.items()},
                })
    return rows


def background_block_variability(
    cases: list[Case],
    target_block_count: int = 6,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    block_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    for case in cases:
        if case.condition != "background":
            continue
        result = load_exact_archive(case.archive)
        healthy = valid_channel_indices(result)
        segment_power = np.asarray(result["welch_segment_bandpower"], dtype=float)
        segment_time = np.asarray(result["welch_segment_time_s"], dtype=float)
        block_count = min(target_block_count, max(2, len(segment_power) // 8))
        blocks = [indices for indices in np.array_split(
            np.arange(len(segment_power)), block_count
        ) if len(indices) >= 3]
        fields = case_fields(case)
        for band_index, band_name in enumerate(BAND_NAMES):
            channel_db = 10.0 * np.log10(np.maximum(
                segment_power[:, healthy, band_index], EPS
            ))
            full_channel_typical = np.median(channel_db, axis=0)
            band_differences = []
            for block_index, indices in enumerate(blocks):
                block_channel_typical = np.median(channel_db[indices], axis=0)
                channel_difference = block_channel_typical - full_channel_typical
                block_difference = float(np.median(channel_difference))
                band_differences.append(block_difference)
                block_rows.append({
                    **fields,
                    "band_name": band_name,
                    "block_index": block_index,
                    "block_start_s": float(segment_time[indices[0]]),
                    "block_end_s": float(segment_time[indices[-1]]),
                    "block_segment_count": len(indices),
                    "median_channel_difference_from_full_db": block_difference,
                    "q25_channel_difference_from_full_db": float(
                        np.percentile(channel_difference, 25)
                    ),
                    "q75_channel_difference_from_full_db": float(
                        np.percentile(channel_difference, 75)
                    ),
                })
            absolute = np.abs(np.asarray(band_differences))
            summary_rows.append({
                **fields,
                "band_name": band_name,
                "block_count": len(blocks),
                "median_absolute_block_drift_db": float(np.median(absolute)),
                "q95_absolute_block_drift_db": float(np.percentile(absolute, 95)),
                "maximum_absolute_block_drift_db": float(np.max(absolute)),
                "signed_block_range_db": float(
                    np.max(band_differences) - np.min(band_differences)
                ),
            })
    return block_rows, summary_rows


def matched_network_contrasts(cases: list[Case], network: pd.DataFrame) -> list[dict[str, object]]:
    metrics = (
        "pca_first_ratio",
        "pca_first_two_ratio",
        "pair_abs_corr_median",
        "pair_max_lag_abs_corr_median",
        "pair_ratio_abs_corr_gt_0p5",
        "pc1_acf_e_fold_s",
    )
    by_case = network.set_index("case_id")
    rows = []
    for case in cases:
        if case.case_id not in by_case.index:
            continue
        for control in matched_controls(case, cases):
            if control.case_id not in by_case.index:
                continue
            active = by_case.loc[case.case_id]
            reference = by_case.loc[control.case_id]
            for metric in metrics:
                active_value = float(active[metric])
                reference_value = float(reference[metric])
                rows.append({
                    **case_fields(case),
                    "reference_case_id": control.case_id,
                    "reference_condition": control.condition,
                    "metric": metric,
                    "active_value": active_value,
                    "reference_value": reference_value,
                    "difference": active_value - reference_value,
                    "independent_file_count_active": 1,
                    "independent_file_count_reference": 1,
                })
    return rows


def matched_coherence_contrasts(
    cases: list[Case],
    coherence_pairs: pd.DataFrame,
) -> list[dict[str, object]]:
    metrics = (
        "median_coherence",
        "q95_coherence",
        "fraction_bins_above_pointwise_null_95",
    )
    rows = []
    for case in cases:
        active = coherence_pairs[coherence_pairs["case_id"] == case.case_id]
        for control in matched_controls(case, cases):
            reference = coherence_pairs[
                coherence_pairs["case_id"] == control.case_id
            ]
            merged = active.merge(
                reference,
                on=["band_name", "channel_i", "channel_j"],
                suffixes=("_active", "_reference"),
            )
            for band_name, group in merged.groupby("band_name"):
                for metric in metrics:
                    active_values = group[f"{metric}_active"].to_numpy(dtype=float)
                    reference_values = group[f"{metric}_reference"].to_numpy(dtype=float)
                    differences = active_values - reference_values
                    rows.append({
                        **case_fields(case),
                        "reference_case_id": control.case_id,
                        "reference_condition": control.condition,
                        "band_name": band_name,
                        "metric": metric,
                        "common_channel_pair_count": len(group),
                        "active_pair_median": float(np.median(active_values)),
                        "reference_pair_median": float(np.median(reference_values)),
                        "median_pair_difference": float(np.median(differences)),
                        "q25_pair_difference": float(np.percentile(differences, 25)),
                        "q75_pair_difference": float(np.percentile(differences, 75)),
                        "positive_pair_fraction": float(np.mean(differences > 0.0)),
                    })
    return rows


def matched_slow_contrasts(cases: list[Case], slow: pd.DataFrame) -> list[dict[str, object]]:
    metrics = (
        "slow_std_v",
        "slow_robust_sigma_v",
        "slow_linear_slope_v_per_s",
        "acf_e_fold_s",
        "acf_integral_positive_s",
        "ar1_phi",
        "ar1_tau_s",
    )
    rows = []
    for case in cases:
        active = slow[(slow["case_id"] == case.case_id) & (~slow["automatic_bad"])]
        for control in matched_controls(case, cases):
            reference = slow[(slow["case_id"] == control.case_id) & (~slow["automatic_bad"])]
            merged = active.merge(reference, on="channel_index", suffixes=("_active", "_reference"))
            if len(merged) < 4:
                continue
            for metric in metrics:
                a = merged[f"{metric}_active"].to_numpy(dtype=float)
                b = merged[f"{metric}_reference"].to_numpy(dtype=float)
                valid = np.isfinite(a) & np.isfinite(b)
                if np.sum(valid) < 4:
                    continue
                differences = a[valid] - b[valid]
                rows.append({
                    **case_fields(case),
                    "reference_case_id": control.case_id,
                    "reference_condition": control.condition,
                    "metric": metric,
                    "common_healthy_channel_count": int(np.sum(valid)),
                    "active_channel_median": float(np.median(a[valid])),
                    "reference_channel_median": float(np.median(b[valid])),
                    "median_channel_difference": float(np.median(differences)),
                    "positive_channel_fraction": float(np.mean(differences > 0.0)),
                })
    return rows


def matched_allan_contrasts(cases: list[Case], allan: pd.DataFrame) -> list[dict[str, object]]:
    rows = []
    for case in cases:
        active = allan[(allan["case_id"] == case.case_id) & (~allan["automatic_bad"])]
        for control in matched_controls(case, cases):
            reference = allan[(allan["case_id"] == control.case_id) & (~allan["automatic_bad"])]
            merged = active.merge(reference, on=["channel_index", "tau_s"],
                                  suffixes=("_active", "_reference"))
            for tau_s, group in merged.groupby("tau_s"):
                a = group["allan_deviation_v_active"].to_numpy(dtype=float)
                b = group["allan_deviation_v_reference"].to_numpy(dtype=float)
                valid = np.isfinite(a) & np.isfinite(b) & (a > 0.0) & (b > 0.0)
                if np.sum(valid) < 4:
                    continue
                ratio_db = 20.0 * np.log10(a[valid] / b[valid])
                rows.append({
                    **case_fields(case),
                    "reference_case_id": control.case_id,
                    "reference_condition": control.condition,
                    "tau_s": float(tau_s),
                    "common_healthy_channel_count": int(np.sum(valid)),
                    "median_allan_amplitude_ratio_db": float(np.median(ratio_db)),
                    "q25_allan_amplitude_ratio_db": float(np.percentile(ratio_db, 25)),
                    "q75_allan_amplitude_ratio_db": float(np.percentile(ratio_db, 75)),
                    "positive_channel_fraction": float(np.mean(ratio_db > 0.0)),
                })
    return rows


def align_pair_arrays(first: Case, second: Case, feature: str) -> tuple[np.ndarray, np.ndarray, float]:
    metadata_a, arrays_a, fs_a = case_time_arrays(first)
    metadata_b, arrays_b, fs_b = case_time_arrays(second)
    if not np.isclose(fs_a, fs_b):
        raise ValueError("Envelope rates differ")
    start_a = datetime.fromisoformat(str(metadata_a["start_time"])).timestamp()
    start_b = datetime.fromisoformat(str(metadata_b["start_time"])).timestamp()
    start_a += float(metadata_a["lowpass_filter"]["analysis_rate_first_sample_time_s"])
    start_b += float(metadata_b["lowpass_filter"]["analysis_rate_first_sample_time_s"])
    common_start = max(start_a, start_b)
    end_a = start_a + len(arrays_a[feature]) / fs_a
    end_b = start_b + len(arrays_b[feature]) / fs_b
    common_end = min(end_a, end_b)
    count = int(math.floor((common_end - common_start) * fs_a))
    if count < int(10 * fs_a):
        raise ValueError("Insufficient synchronous overlap")
    index_a = int(round((common_start - start_a) * fs_a))
    index_b = int(round((common_start - start_b) * fs_b))
    return (arrays_a[feature][index_a:index_a + count],
            arrays_b[feature][index_b:index_b + count], fs_a)


def cross_detector_sync(cases: list[Case]) -> list[dict[str, object]]:
    rows = []
    duo = [case for case in cases if case.dataset == "20260806"
           and case.arrangement in {"duo1", "duo2"}]
    groups: dict[tuple[str, str], dict[str, Case]] = {}
    for case in duo:
        groups.setdefault((case.arrangement, case.condition), {})[case.detector] = case
    for (arrangement, condition), pair in sorted(groups.items()):
        if set(pair) != {"tc1", "tc2"}:
            continue
        first, second = pair["tc1"], pair["tc2"]
        first_result = load_exact_archive(first.archive)
        second_result = load_exact_archive(second.archive)
        first_valid = valid_channel_indices(first_result)
        second_valid = valid_channel_indices(second_result)
        for feature in ("slow_mean",) + ENVELOPE_FEATURES:
            a, b, fs = align_pair_arrays(first, second, feature)
            if feature != "slow_mean":
                a = np.log10(np.maximum(a, EPS))
                b = np.log10(np.maximum(b, EPS))
            pc_a, _, _ = principal_component(a[:, first_valid])
            pc_b, _, _ = principal_component(b[:, second_valid])
            lag = lag_null_test(pc_a, pc_b, fs, observed_lag_s=2.0,
                                null_min_lag_s=7.0, null_max_lag_s=20.0)
            rows.append({
                "dataset": "20260806",
                "arrangement": arrangement,
                "condition": condition,
                "feature": feature,
                "tc1_case_id": first.case_id,
                "tc2_case_id": second.case_id,
                "overlap_duration_s": len(pc_a) / fs,
                "tc1_healthy_channel_count": len(first_valid),
                "tc2_healthy_channel_count": len(second_valid),
                **lag,
            })
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return frame


def plot_band_contrasts(frame: pd.DataFrame, path: Path) -> None:
    subset = frame[(frame["dataset"] == "20260806")
                   & (frame["reference_condition"] == "background")].copy()
    if subset.empty:
        return
    subset["label"] = subset.apply(
        lambda row: f"{row['arrangement']} {row['detector']} {row['condition']}"
        + (f" {row['carrier_khz']:g}k/{row['output_hz']:g}" if pd.notna(row["carrier_khz"]) else ""),
        axis=1,
    )
    bands = list(BAND_NAMES)
    labels = list(dict.fromkeys(subset["label"]))
    matrix = np.full((len(labels), len(bands)), np.nan)
    for i, label in enumerate(labels):
        for j, band in enumerate(bands):
            values = subset[(subset["label"] == label) & (subset["band_name"] == band)]["median_difference_db"]
            if len(values):
                matrix[i, j] = float(values.iloc[0])
    fig, ax = plt.subplots(figsize=(11, max(5, 0.28 * len(labels))))
    image = ax.imshow(matrix, aspect="auto", cmap="RdBu_r", vmin=-max(0.3, np.nanmax(np.abs(matrix))),
                      vmax=max(0.3, np.nanmax(np.abs(matrix))))
    ax.set_xticks(range(len(bands)), bands)
    ax.set_yticks(range(len(labels)), labels, fontsize=8)
    ax.set_title("2026-08-06 matched local-background band differences")
    fig.colorbar(image, ax=ax, label="median difference (dB)")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_network(frame: pd.DataFrame, path: Path) -> None:
    subset = frame[frame["dataset"] == "20260806"].copy()
    if subset.empty:
        return
    subset["label"] = subset.apply(
        lambda row: f"{row['arrangement']}/{row['detector']}/{row['condition']}"
        + (f"/{row['carrier_khz']:g}k-{row['output_hz']:g}" if pd.notna(row["carrier_khz"]) else ""),
        axis=1,
    )
    subset = subset.sort_values(["arrangement", "detector", "condition", "carrier_khz", "output_hz"])
    x = np.arange(len(subset))
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    axes[0].bar(x, subset["pca_first_ratio"], color="#2f6f8f")
    axes[0].set_ylabel("PC1 variance ratio")
    axes[1].bar(x, subset["pair_max_lag_abs_corr_median"], color="#b65d3a")
    axes[1].set_ylabel("median max |lag correlation|")
    axes[1].set_xticks(x, subset["label"], rotation=70, ha="right", fontsize=7)
    fig.suptitle("2026-08-06 slow-network structure")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def build_report(output: Path, cases: list[Case], frames: dict[str, pd.DataFrame]) -> None:
    health = frames["health"]
    network = frames["network"]
    coupling = frames["coupling"]
    contrast = frames["contrasts"]
    lines = frames["line_support"]
    bad = health.groupby("dataset")["automatic_bad"].sum().to_dict() if not health.empty else {}
    strict_coupling = coupling[(coupling["scope"] == "common_pc1")
                               & (coupling["lag_null_p"] <= 0.05)
                               & (coupling["max_abs_lag_correlation"].abs() >= 0.3)]
    run_806 = contrast[(contrast["dataset"] == "20260806")
                       & (contrast["reference_condition"] == "background")
                       & (contrast["condition"].isin(["30hz", "50hz", "run"]))]
    run_806_high = run_806[run_806["band_name"] == "80_200khz"]
    mean_positive = int(np.sum(run_806_high["mean_power_median_channel_difference_db"] > 0.0))
    typical_positive = int(np.sum(run_806_high["median_channel_typical_difference_db"] > 0.0))
    line_shared = lines[(lines["dataset"] == "20260806")
                        & (lines["channel_support_fraction"] >= 0.5)
                        & (lines["median_persistence_fraction"] >= 0.2)]
    report = [
        "# 电化学实验前动态网络分析 V1",
        "",
        "## 数据与口径",
        "",
        f"- 精确归档工况数：{len(cases)}。",
        "- 每文件独立动态判断坏道；通道、时间窗和 Welch 段不作为独立实验重复。",
        "- 慢动态使用完整 10 Hz 对齐时序；高频时间行为使用完整 Welch 峰轨迹和频带功率。",
        "- 本报告为导师建议下的第一版数据驱动结果，不对数据模态直接赋予器件物理名称。",
        "",
        "## 运行摘要",
        "",
        f"- 自动坏道记录数（文件×通道）：{json.dumps(bad, ensure_ascii=False)}。",
        f"- 20260806 网络摘要行数：{len(network[network['dataset'] == '20260806'])}。",
        f"- 达到 |r|>=0.3 且错位对照 p<=0.05 的共同低高频耦合项：{len(strict_coupling)}。",
        f"- 20260806 RUN 相对本地背景频带比较行数：{len(run_806)}。",
        f"- 20260806 的 80--200 kHz RUN 对照中，全记录平均功率为正 {mean_positive}/{len(run_806_high)}，逐通道典型功率差为正 {typical_positive}/{len(run_806_high)}。",
        f"- 20260806 跨至少半数健康通道且持续率中位数>=20%的候选线簇：{len(line_shared)}。",
        "",
        "## 结果解释边界",
        "",
        "- ACF、AR(1) 和 Allan 指标描述有效时间尺度，不直接等同于某个已知 RC 元件参数。",
        "- 低高频耦合的错位时间对照用于抑制自相关造成的虚假相关，但仍是同一文件内证据。",
        "- 高频峰轨迹来自每段保留的前 64 个峰，适合比较持续性和探测器依赖，不等价于完整高频波形。",
        "- 物理源归因仍需结合本地背景、换位、媒体和后续受控实验。",
        "",
        "## 输出表",
        "",
        "- `channel_health_dynamic.csv`：逐文件动态健康通道。",
        "- `slow_relaxation_metrics.csv`、`allan_deviation.csv`：慢动态时间尺度。",
        "- `network_summary.csv`、`channel_pair_lag_network.csv`：多通道网络结构。",
        "- `low_high_coupling.csv`：准静态状态与高频包络耦合。",
        "- `band_temporal_dynamics.csv`、`matched_band_contrasts.csv`：高频带时间行为和本地对照。",
        "- `matched_narrow_line_contrasts.csv`：窄线相对本地对照、邻域漂移检查和逐段出现率。",
        "- `background_block_variability.csv`、`background_block_variability_summary.csv`：本地背景记录内部时间漂移。",
        "- `matched_slow_dynamics_contrasts.csv`、`matched_allan_contrasts.csv`：慢动态相对本地对照。",
        "- `matched_network_contrasts.csv`：网络结构相对本地对照。",
        "- `low_rate_pair_coherence.csv`、`low_rate_coherence_summary.csv`：1 Hz--1.5 kHz跨通道相干结构。",
        "- `matched_low_rate_coherence_contrasts.csv`：跨通道相干结构相对本地对照。",
        "- `slow_periodicity_candidates.csv`：固定3.1秒候选及盲搜低频周期的跨通道/前后半段支持。",
        "- `line_tracks.csv`、`line_cross_channel_support.csv`：窄谱线持续性和通道支持。",
        "- `cross_detector_synchrony.csv`：duo 同场双探测器共同动态。",
    ]
    (output / "ANALYSIS_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path,
                        default=Path('analysis/mentor_aligned_pre_electrochemical_v1'))
    parser.add_argument("--datasets", nargs="*",
                        default=["20260617", "20260731", "20260806"])
    args = parser.parse_args(argv)
    project_root = args.project_root.resolve()
    output = args.output if args.output.is_absolute() else project_root / args.output
    output.mkdir(parents=True, exist_ok=True)
    cases = [case for case in discover_cases(project_root) if case.dataset in args.datasets]
    if not cases:
        raise FileNotFoundError("No completed exact archive cases found")

    stores = {name: [] for name in (
        "health", "slow", "allan", "network", "pairs", "coupling",
        "band", "lines", "line_support", "low_rate_coherence_pairs",
        "low_rate_coherence_summary", "slow_periodicity",
    )}
    for index, case in enumerate(cases, start=1):
        print(f"[{index:02d}/{len(cases):02d}] {case.dataset} {case.case_id}", flush=True)
        outputs = process_case(case)
        for name, rows in outputs.items():
            stores[name].extend(rows)

    frames = {
        "health": write_csv(output / "channel_health_dynamic.csv", stores["health"]),
        "slow": write_csv(output / "slow_relaxation_metrics.csv", stores["slow"]),
        "allan": write_csv(output / "allan_deviation.csv", stores["allan"]),
        "network": write_csv(output / "network_summary.csv", stores["network"]),
        "pairs": write_csv(output / "channel_pair_lag_network.csv", stores["pairs"]),
        "coupling": write_csv(output / "low_high_coupling.csv", stores["coupling"]),
        "band": write_csv(output / "band_temporal_dynamics.csv", stores["band"]),
        "lines": write_csv(output / "line_tracks.csv", stores["lines"]),
        "line_support": write_csv(output / "line_cross_channel_support.csv", stores["line_support"]),
        "low_rate_coherence_pairs": write_csv(
            output / "low_rate_pair_coherence.csv",
            stores["low_rate_coherence_pairs"],
        ),
        "low_rate_coherence_summary": write_csv(
            output / "low_rate_coherence_summary.csv",
            stores["low_rate_coherence_summary"],
        ),
        "slow_periodicity": write_csv(
            output / "slow_periodicity_candidates.csv",
            stores["slow_periodicity"],
        ),
    }
    contrast_rows = matched_band_contrasts(cases)
    frames["contrasts"] = write_csv(output / "matched_band_contrasts.csv", contrast_rows)
    frames["narrow_line_contrasts"] = write_csv(
        output / "matched_narrow_line_contrasts.csv",
        matched_narrow_line_contrasts(cases),
    )
    background_blocks, background_block_summary = background_block_variability(cases)
    frames["background_blocks"] = write_csv(
        output / "background_block_variability.csv", background_blocks
    )
    frames["background_block_summary"] = write_csv(
        output / "background_block_variability_summary.csv", background_block_summary
    )
    frames["network_contrasts"] = write_csv(
        output / "matched_network_contrasts.csv",
        matched_network_contrasts(cases, frames["network"]),
    )
    frames["coherence_contrasts"] = write_csv(
        output / "matched_low_rate_coherence_contrasts.csv",
        matched_coherence_contrasts(cases, frames["low_rate_coherence_pairs"]),
    )
    frames["slow_contrasts"] = write_csv(
        output / "matched_slow_dynamics_contrasts.csv",
        matched_slow_contrasts(cases, frames["slow"]),
    )
    frames["allan_contrasts"] = write_csv(
        output / "matched_allan_contrasts.csv",
        matched_allan_contrasts(cases, frames["allan"]),
    )
    sync_rows = cross_detector_sync(cases)
    frames["sync"] = write_csv(output / "cross_detector_synchrony.csv", sync_rows)

    plot_band_contrasts(frames["contrasts"], output / "matched_background_band_contrasts.png")
    plot_network(frames["network"], output / "slow_network_structure.png")
    build_report(output, cases, frames)
    manifest = {
        "created": datetime.now().isoformat(),
        "case_count": len(cases),
        "datasets": sorted(set(case.dataset for case in cases)),
        "cases": [case_fields(case) for case in cases],
        "outputs": {name: len(frame) for name, frame in frames.items()},
        "method_notes": {
            "channels_dynamic_per_file": True,
            "windows_are_independent_replicates": False,
            "raw_tdms_required": False,
            "electrochemical_data_included": False,
        },
    }
    (output / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Output: {output}")
    return output


if __name__ == "__main__":
    main()
