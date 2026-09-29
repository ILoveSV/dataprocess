"""Run wavelet, synchrosqueezing, changepoint, relaxation, and filter audits."""

from __future__ import annotations

import argparse
import functools
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pywt
from scipy import ndimage, signal, stats

from scripts.analyze_pre_electrochemical_dynamics import case_fields, detrended, robust_scale
from scripts.mentor_method_common import (
    METHOD_OUTPUT,
    all_cases,
    enable_local_dependencies,
    generic_matched_contrasts,
    load_analysis_signals,
    load_health_table,
    stable_seed,
    write_frame,
    write_manifest,
)


enable_local_dependencies()
import ruptures as rpt
from ssqueezepy import ssq_cwt


WAVELET = "cmor1.5-1.0"
FREQUENCIES_HZ = np.geomspace(0.05, 2.0, 48)
WAVELET_BANDS = {
    "0p05_0p15hz": (0.05, 0.15),
    "0p15_0p5hz": (0.15, 0.5),
    "0p5_2hz": (0.5, 2.0),
}


@functools.lru_cache(maxsize=64)
def empirical_ar1_wavelet_null(
    sample_rate_key: float, phi_key: float, repeats: int = 32,
) -> tuple[np.ndarray, np.ndarray]:
    """Calibrate PyWavelets power using unit-variance AR(1) simulations."""
    sample_rate = float(sample_rate_key)
    phi = float(phi_key)
    length = 2048
    burn = 256
    rng = np.random.default_rng(stable_seed("cwt-ar1-null", sample_rate_key, phi_key))
    scales = pywt.central_frequency(WAVELET) * sample_rate / FREQUENCIES_HZ
    time = np.arange(length, dtype=np.float64) / sample_rate
    valid = np.ones((len(scales), length), dtype=bool)
    for index, edge in enumerate(np.sqrt(2.0) * scales / sample_rate):
        valid[index] = (time >= edge) & (time <= time[-1] - edge)
    rows = [[] for _ in scales]
    for _ in range(repeats):
        innovations = rng.normal(size=length + burn)
        surrogate = signal.lfilter([1.0], [1.0, -phi], innovations)[burn:]
        surrogate -= np.mean(surrogate)
        surrogate /= max(np.std(surrogate), 1e-15)
        coefficients, _ = pywt.cwt(
            surrogate, scales, WAVELET, sampling_period=1.0 / sample_rate,
        )
        power = np.abs(coefficients) ** 2
        for index in range(len(scales)):
            rows[index].append(power[index, valid[index]])
    means = np.asarray([
        np.mean(np.concatenate(values)) for values in rows
    ], dtype=np.float64)
    q95 = np.asarray([
        np.percentile(np.concatenate(values), 95) for values in rows
    ], dtype=np.float64)
    return means, q95


def ar1_coefficient(values: np.ndarray) -> float:
    x = detrended(values)
    denominator = float(np.dot(x[:-1], x[:-1]))
    if denominator <= 1e-15:
        return 0.0
    return float(np.clip(np.dot(x[:-1], x[1:]) / denominator, -0.99, 0.99))


def cwt_analysis(values: np.ndarray, sample_rate: float) -> dict[str, object]:
    x = detrended(values) / float(robust_scale(detrended(values)).squeeze())
    scales = pywt.central_frequency(WAVELET) * sample_rate / FREQUENCIES_HZ
    coefficients, frequencies = pywt.cwt(
        x, scales, WAVELET, sampling_period=1.0 / sample_rate,
    )
    power = np.abs(coefficients) ** 2
    phi = ar1_coefficient(x)
    phi_key = float(np.round(phi / 0.05) * 0.05)
    null_mean_unit, null_q95_unit = empirical_ar1_wavelet_null(
        float(np.round(sample_rate, 6)), phi_key,
    )
    red_noise = np.var(x) * null_mean_unit
    threshold = np.var(x) * null_q95_unit
    time = np.arange(len(x), dtype=np.float64) / sample_rate
    coi_seconds = np.sqrt(2.0) * scales / sample_rate
    valid = np.ones_like(power, dtype=bool)
    for index, edge in enumerate(coi_seconds):
        valid[index] = (time >= edge) & (time <= time[-1] - edge)
    ratio = power / np.maximum(threshold[:, None], 1e-15)
    masked_ratio = np.where(valid, ratio, np.nan)
    global_power = np.array([
        np.nanmedian(power[index, valid[index]]) if np.any(valid[index]) else np.nan
        for index in range(len(frequencies))
    ])
    peak_index = int(np.nanargmax(global_power))
    safe_ratio = np.where(valid, ratio, -np.inf)
    ridge_index = np.argmax(safe_ratio, axis=0)
    ridge_ratio = safe_ratio[ridge_index, np.arange(len(x))]
    ridge_frequency = frequencies[ridge_index]
    ridge_valid = np.isfinite(ridge_ratio)
    significant_ridge = ridge_valid & (ridge_ratio > 1.0)
    row: dict[str, object] = {
        "ar1_phi": phi,
        "global_peak_frequency_hz": float(frequencies[peak_index]),
        "global_peak_power_to_red_noise": float(
            global_power[peak_index] / max(red_noise[peak_index], 1e-15)
        ),
        "significant_point_fraction": float(
            np.sum(valid & (ratio > 1.0)) / max(np.sum(valid), 1)
        ),
        "significant_ridge_fraction": float(np.mean(significant_ridge)),
        "ridge_frequency_median_hz": float(np.median(ridge_frequency[ridge_valid])),
        "ridge_frequency_iqr_hz": float(
            np.percentile(ridge_frequency[ridge_valid], 75)
            - np.percentile(ridge_frequency[ridge_valid], 25)
        ),
    }
    for band_name, (low, high) in WAVELET_BANDS.items():
        use = (frequencies >= low) & (frequencies < high)
        band_ratio = masked_ratio[use]
        band_valid = valid[use]
        finite_band_ratio = ratio[use][band_valid]
        row[f"{band_name}_median_power_to_red"] = (
            float(np.median(finite_band_ratio)) if len(finite_band_ratio) else np.nan
        )
        row[f"{band_name}_significant_fraction"] = float(
            np.sum(band_valid & (ratio[use] > 1.0)) / max(np.sum(band_valid), 1)
        )
    return {
        "summary": row,
        "coefficients": coefficients,
        "frequencies_hz": frequencies,
        "power_to_red": ratio,
        "valid": valid,
        "time_s": time,
    }


def smooth_wavelet(values: np.ndarray, scales: np.ndarray) -> np.ndarray:
    original_ndim = values.ndim
    batch = values[None, ...] if original_ndim == 2 else values
    result = np.empty_like(
        batch, dtype=np.complex128 if np.iscomplexobj(batch) else np.float64
    )
    for index, scale in enumerate(scales):
        sigma = float(np.clip(0.35 * scale, 1.0, max(batch.shape[2] / 10.0, 1.0)))
        result[:, index] = ndimage.gaussian_filter1d(
            batch[:, index], sigma=sigma, axis=-1, mode="nearest"
        )
    result = ndimage.gaussian_filter1d(result, sigma=1.0, axis=1, mode="nearest")
    return result[0] if original_ndim == 2 else result


def wavelet_coherence(
    first: dict[str, object], second: dict[str, object], sample_rate: float,
    null_shifts: int, seed: int,
) -> dict[str, float]:
    wx = np.asarray(first["coefficients"])
    wy = np.asarray(second["coefficients"])
    frequencies = np.asarray(first["frequencies_hz"])
    scales = pywt.central_frequency(WAVELET) * sample_rate / frequencies
    valid = np.asarray(first["valid"]) & np.asarray(second["valid"])
    first_power = smooth_wavelet(np.abs(wx) ** 2 / scales[:, None], scales).real

    def score(other: np.ndarray) -> tuple[float, float, float, float]:
        cross = smooth_wavelet(wx * np.conj(other) / scales[:, None], scales)
        second_power = smooth_wavelet(np.abs(other) ** 2 / scales[:, None], scales).real
        coherence = np.abs(cross) ** 2 / np.maximum(first_power * second_power, 1e-15)
        coherence = np.clip(coherence, 0.0, 1.0)
        use = valid & (frequencies[:, None] >= 0.05) & (frequencies[:, None] < 0.5)
        values = coherence[use]
        phase = np.angle(cross[use])
        strong = values >= np.nanpercentile(values, 75)
        phase_resultant = float(np.abs(np.mean(np.exp(1j * phase[strong])))) if np.any(strong) else np.nan
        return (
            float(np.nanmedian(values)),
            float(np.nanpercentile(values, 95)),
            float(np.mean(values >= 0.5)),
            phase_resultant,
        )

    observed = score(wy)
    rng = np.random.default_rng(seed)
    minimum_shift = max(1, int(round(10.0 * sample_rate)))
    candidates = np.arange(minimum_shift, max(minimum_shift + 1, wy.shape[1] - minimum_shift))
    if len(candidates) == 0:
        shifts = np.array([], dtype=int)
    else:
        shifts = rng.choice(candidates, size=min(null_shifts, len(candidates)), replace=False)
    if len(shifts):
        shifted = np.stack([np.roll(wy, int(shift), axis=1) for shift in shifts])
        cross = smooth_wavelet(
            wx[None, :, :] * np.conj(shifted) / scales[None, :, None], scales
        )
        second_power = smooth_wavelet(
            np.abs(shifted) ** 2 / scales[None, :, None], scales
        ).real
        coherence = np.abs(cross) ** 2 / np.maximum(
            first_power[None, :, :] * second_power, 1e-15
        )
        coherence = np.clip(coherence, 0.0, 1.0)
        use = valid & (frequencies[:, None] >= 0.05) & (frequencies[:, None] < 0.5)
        null_medians = np.median(coherence[:, use], axis=1)
    else:
        null_medians = np.array([], dtype=np.float64)
    p_value = float((np.sum(null_medians >= observed[0]) + 1) / (len(null_medians) + 1))
    return {
        "median_coherence_0p05_0p5hz": observed[0],
        "q95_coherence_0p05_0p5hz": observed[1],
        "fraction_coherence_ge_0p5": observed[2],
        "strong_phase_resultant": observed[3],
        "circular_shift_null_p": p_value,
        "circular_shift_count": len(null_medians),
        "null_median_coherence_q95": float(np.percentile(null_medians, 95)) if len(null_medians) else np.nan,
    }


def synchrosqueezed_summary(values: np.ndarray, sample_rate: float) -> dict[str, float]:
    x = detrended(values) / float(robust_scale(detrended(values)).squeeze())
    transformed, _, frequencies, _ = ssq_cwt(x, fs=sample_rate, wavelet="morlet", nv=16)
    power = np.abs(transformed) ** 2
    use = (frequencies >= 0.05) & (frequencies <= 2.0)
    selected_power = power[use]
    selected_frequency = frequencies[use]
    ridge_index = np.argmax(selected_power, axis=0)
    ridge_frequency = selected_frequency[ridge_index]
    sorted_power = np.sort(selected_power, axis=0)
    concentration = np.sum(sorted_power[-3:], axis=0) / np.maximum(
        np.sum(selected_power, axis=0), 1e-15
    )
    return {
        "sst_ridge_frequency_median_hz": float(np.median(ridge_frequency)),
        "sst_ridge_frequency_iqr_hz": float(
            np.percentile(ridge_frequency, 75) - np.percentile(ridge_frequency, 25)
        ),
        "sst_top3_bin_concentration_median": float(np.median(concentration)),
        "sst_top3_bin_concentration_q75": float(np.percentile(concentration, 75)),
    }


def pelt_changepoints(values: np.ndarray, sample_rate: float) -> list[int]:
    x = detrended(values) / float(robust_scale(detrended(values)).squeeze())
    minimum = max(5, int(round(3.0 * sample_rate)))
    penalty = 5.0 * math.log(max(len(x), 2))
    points = rpt.Pelt(model="l2", min_size=minimum, jump=1).fit(x).predict(pen=penalty)
    return [int(point) for point in points if point < len(x)]


def fit_exponential_relaxation(
    values: np.ndarray, start: int, sample_rate: float, duration_s: float = 12.0,
) -> dict[str, float]:
    end = min(len(values), start + int(round(duration_s * sample_rate)))
    y = np.asarray(values[start:end], dtype=np.float64)
    if len(y) < max(12, int(4 * sample_rate)):
        return {"relaxation_tau_s": np.nan, "relaxation_amplitude": np.nan,
                "relaxation_baseline": np.nan, "relaxation_r2": np.nan,
                "relaxation_tau_at_boundary": False}
    time = np.arange(len(y), dtype=np.float64) / sample_rate
    taus = np.geomspace(max(0.2, 2.0 / sample_rate), min(20.0, duration_s * 2.0), 80)
    best = None
    for tau in taus:
        design = np.column_stack([np.exp(-time / tau), np.ones_like(time)])
        coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
        prediction = design @ coefficients
        sse = float(np.sum((y - prediction) ** 2))
        if best is None or sse < best[0]:
            best = (sse, tau, coefficients, prediction)
    assert best is not None
    total = float(np.sum((y - np.mean(y)) ** 2))
    tau = float(best[1])
    return {
        "relaxation_tau_s": tau,
        "relaxation_amplitude": float(best[2][0]),
        "relaxation_baseline": float(best[2][1]),
        "relaxation_r2": float(1.0 - best[0] / max(total, 1e-15)),
        "relaxation_tau_at_boundary": bool(
            np.isclose(tau, taus[0]) or np.isclose(tau, taus[-1])
        ),
    }


def event_rows(
    values: np.ndarray, channel_values: np.ndarray, sample_rate: float,
) -> tuple[list[dict[str, object]], dict[str, float]]:
    x = detrended(values) / float(robust_scale(detrended(values)).squeeze())
    points = pelt_changepoints(x, sample_rate)
    normalized_channels = detrended(channel_values)
    normalized_channels /= np.maximum(
        robust_scale(normalized_channels), 1e-15
    )
    pre = max(2, int(round(sample_rate)))
    post = max(2, int(round(sample_rate)))
    waveform_pre = int(round(2.0 * sample_rate))
    waveform_post = int(round(12.0 * sample_rate))
    rows: list[dict[str, object]] = []
    waveforms: list[np.ndarray] = []
    for point in points:
        if point < waveform_pre or point + waveform_post > len(x):
            continue
        before = float(np.median(x[max(0, point - pre):point]))
        after = float(np.median(x[point:min(len(x), point + post)]))
        step = after - before
        channel_before = np.median(
            normalized_channels[max(0, point - pre):point], axis=0
        )
        channel_after = np.median(
            normalized_channels[point:min(len(x), point + post)], axis=0
        )
        support = float(np.mean(np.abs(channel_after - channel_before) >= 0.5))
        relaxation = fit_exponential_relaxation(x, point, sample_rate)
        waveform = x[point - waveform_pre:point + waveform_post].copy()
        if step < 0:
            waveform *= -1.0
        waveforms.append(waveform)
        rows.append({
            "event_sample": point,
            "event_time_s": point / sample_rate,
            "step_amplitude_robust_sigma": step,
            "absolute_step_amplitude_robust_sigma": abs(step),
            "channel_changepoint_support_fraction": support,
            **relaxation,
        })
    repeatability = np.nan
    if len(waveforms) >= 2:
        matrix = np.vstack(waveforms)
        template = np.median(matrix, axis=0)
        correlations = [np.corrcoef(item, template)[0, 1] for item in matrix]
        repeatability = float(np.nanmedian(correlations))
    credible = [row for row in rows if (
        row["absolute_step_amplitude_robust_sigma"] >= 0.5
        and row["relaxation_r2"] >= 0.5
        and not row["relaxation_tau_at_boundary"]
        and row["channel_changepoint_support_fraction"] >= 0.5
    )]
    summary = {
        "changepoint_count": len(rows),
        "changepoint_rate_per_minute": len(rows) / max(len(x) / sample_rate / 60.0, 1e-12),
        "median_absolute_step_robust_sigma": float(np.median([
            row["absolute_step_amplitude_robust_sigma"] for row in rows
        ])) if rows else 0.0,
        "median_channel_support_fraction": float(np.median([
            row["channel_changepoint_support_fraction"] for row in rows
        ])) if rows else 0.0,
        "credible_relaxation_count": len(credible),
        "median_credible_relaxation_tau_s": float(np.median([
            row["relaxation_tau_s"] for row in credible
        ])) if credible else np.nan,
        "event_waveform_repeatability_median_r": repeatability,
    }
    return rows, summary


def preprocessors(values: np.ndarray, sample_rate: float,
                  normalize_input: bool = True) -> dict[str, np.ndarray]:
    x = detrended(values)
    if normalize_input:
        x = x / float(robust_scale(x).squeeze())

    def odd_window(seconds: float) -> int:
        width = max(5, int(round(seconds * sample_rate)))
        return width if width % 2 else width + 1

    maximum_window = len(x) - 1 if len(x) % 2 == 0 else len(x)
    savgol_1 = min(odd_window(1.1), maximum_window)
    savgol_3 = min(odd_window(3.1), maximum_window)
    sos = signal.butter(4, [0.05, 2.0], btype="bandpass", fs=sample_rate, output="sos")
    coefficients = pywt.wavedec(x, "db4", mode="symmetric")
    sigma = np.median(np.abs(coefficients[-1])) / 0.6745
    threshold = sigma * np.sqrt(2.0 * np.log(len(x)))
    shrunk = [coefficients[0]] + [
        pywt.threshold(item, threshold, mode="soft") for item in coefficients[1:]
    ]
    wavelet = pywt.waverec(shrunk, "db4", mode="symmetric")[:len(x)]
    q = 0.01
    r = 1.0
    state = np.empty_like(x)
    estimate = x[0]
    covariance = 1.0
    for index, observation in enumerate(x):
        covariance += q
        gain = covariance / (covariance + r)
        estimate += gain * (observation - estimate)
        covariance *= 1.0 - gain
        state[index] = estimate
    return {
        "unfiltered_detrended": x,
        "savgol_1p1s": signal.savgol_filter(x, savgol_1, 3),
        "savgol_3p1s": signal.savgol_filter(x, savgol_3, 3),
        "zero_phase_bandpass_0p05_2hz": signal.sosfiltfilt(sos, x),
        "wavelet_db4_shrinkage": wavelet,
        "kalman_local_level": state,
    }


def sinusoid_coefficients(values: np.ndarray, sample_rate: float,
                          frequency: float) -> np.ndarray:
    time = np.arange(len(values), dtype=np.float64) / sample_rate
    design = np.column_stack([
        np.sin(2.0 * np.pi * frequency * time),
        np.cos(2.0 * np.pi * frequency * time),
        np.ones_like(time),
        time - np.mean(time),
    ])
    coefficients, *_ = np.linalg.lstsq(design, values, rcond=None)
    return coefficients[:2]


def injection_rows(values: np.ndarray, sample_rate: float) -> list[dict[str, object]]:
    base = detrended(values) / float(robust_scale(detrended(values)).squeeze())
    base_paths = preprocessors(base, sample_rate, normalize_input=False)
    time = np.arange(len(values), dtype=np.float64) / sample_rate
    sinusoid = 0.2 * np.sin(2.0 * np.pi * (1.0 / 3.1) * time)
    event_index = len(values) // 2
    transient = np.zeros_like(time)
    transient[event_index:] = 0.5 * np.exp(-(time[event_index:] - time[event_index]) / 3.0)
    sinusoid_paths = preprocessors(base + sinusoid, sample_rate, normalize_input=False)
    transient_paths = preprocessors(base + transient, sample_rate, normalize_input=False)
    rows = []
    for name in base_paths:
        delta_sinusoid = sinusoid_paths[name] - base_paths[name]
        recovered = sinusoid_coefficients(delta_sinusoid, sample_rate, 1.0 / 3.1)
        recovered_amplitude = float(np.linalg.norm(recovered))
        delta_transient = transient_paths[name] - base_paths[name]
        relaxation = fit_exponential_relaxation(delta_transient, event_index, sample_rate)
        nearby_change = any(
            abs(item - event_index) <= sample_rate for item in pelt_changepoints(
                transient_paths[name], sample_rate
            )
        )
        rows.append({
            "filter_name": name,
            "injected_sinusoid_frequency_hz": 1.0 / 3.1,
            "injected_sinusoid_amplitude_sigma": 0.2,
            "recovered_sinusoid_amplitude_sigma": recovered_amplitude,
            "sinusoid_amplitude_recovery_ratio": recovered_amplitude / 0.2,
            "injected_transient_tau_s": 3.0,
            "injected_transient_amplitude_sigma": 0.5,
            "recovered_transient_tau_s": relaxation["relaxation_tau_s"],
            "transient_tau_recovery_ratio": relaxation["relaxation_tau_s"] / 3.0,
            "transient_relaxation_r2": relaxation["relaxation_r2"],
            "transient_changepoint_detected_within_1s": nearby_change,
        })
    return rows


def plot_representative_scalograms(cache: dict[tuple[str, str], dict[str, object]],
                                    output: Path) -> None:
    case_ids = ["duo1_tc1_background", "duo1_tc1_30hz", "duo1_tc1_50hz"]
    available = [case_id for case_id in case_ids if (case_id, "slow_pc1") in cache]
    if not available:
        return
    fig = plt.figure(figsize=(11, 3.1 * len(available)))
    grid = fig.add_gridspec(
        len(available), 2, width_ratios=[30, 1], hspace=0.35, wspace=0.08
    )
    axes = []
    for index in range(len(available)):
        axes.append(fig.add_subplot(
            grid[index, 0], sharex=axes[0] if axes else None
        ))
    for axis, case_id in zip(axes, available):
        result = cache[(case_id, "slow_pc1")]
        ratio = np.where(result["valid"], result["power_to_red"], np.nan)
        mesh = axis.pcolormesh(
            result["time_s"], result["frequencies_hz"],
            np.log10(np.maximum(ratio, 1e-3)), shading="auto", cmap="viridis",
            vmin=-1.0, vmax=1.0,
        )
        axis.contour(
            result["time_s"], result["frequencies_hz"], ratio,
            levels=[1.0], colors="white", linewidths=0.7,
        )
        axis.set_yscale("log")
        axis.set_ylim(0.05, 2.0)
        axis.set_ylabel("Hz")
        axis.set_title(case_id)
    axes[-1].set_xlabel("Trimmed record time (s)")
    color_axis = fig.add_subplot(grid[:, 1])
    colorbar = fig.colorbar(mesh, cax=color_axis)
    colorbar.set_label("log10(power / AR1 q95)")
    fig.suptitle("Morlet CWT of slow common mode")
    fig.subplots_adjust(left=0.09, right=0.94, top=0.92, bottom=0.08)
    fig.savefig(output, dpi=180)
    plt.close(fig)


def plot_injection_recovery(frame: pd.DataFrame, output: Path) -> None:
    if frame.empty:
        return
    summary = frame.groupby("filter_name").agg(
        sinusoid=("sinusoid_amplitude_recovery_ratio", "median"),
        tau=("transient_tau_recovery_ratio", "median"),
        detection=("transient_changepoint_detected_within_1s", "mean"),
    ).reset_index()
    x = np.arange(len(summary))
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    width = 0.36
    axes[0].bar(x - width / 2, summary["sinusoid"], width, label="3.1 s amplitude")
    axes[0].bar(x + width / 2, summary["tau"], width, label="3 s relaxation tau")
    axes[0].axhline(1.0, color="#444444", linewidth=0.8)
    axes[0].set_ylabel("Median recovery ratio")
    axes[0].legend()
    axes[0].grid(axis="y", alpha=0.25)
    axes[1].bar(x, summary["detection"], color="#2f6f8f")
    axes[1].set_ylabel("Injected event detection fraction")
    axes[1].set_ylim(0.0, 1.05)
    axes[1].set_xticks(x, summary["filter_name"], rotation=30, ha="right")
    axes[1].grid(axis="y", alpha=0.25)
    fig.suptitle("Filter sensitivity by synthetic-signal recovery")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=METHOD_OUTPUT / "wavelet_relaxation")
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--start-case", type=int, default=0,
                        help="Zero-based case offset, primarily for resumable validation runs.")
    parser.add_argument("--coherence-null-shifts", type=int, default=24)
    args = parser.parse_args(argv)
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    figures = output / "figures"
    figures.mkdir(exist_ok=True)
    health = load_health_table()
    cases = all_cases()
    if args.start_case > 0:
        cases = cases[args.start_case:]
    if args.max_cases > 0:
        cases = cases[:args.max_cases]

    cwt_rows: list[dict[str, object]] = []
    coherence_rows: list[dict[str, object]] = []
    sst_rows: list[dict[str, object]] = []
    changepoint_rows: list[dict[str, object]] = []
    event_detail_rows: list[dict[str, object]] = []
    filter_rows: list[dict[str, object]] = []
    injection: list[dict[str, object]] = []
    cwt_cache: dict[tuple[str, str], dict[str, object]] = {}

    for case_index, case in enumerate(cases, start=1):
        loaded = load_analysis_signals(case, health)
        fields = case_fields(case)
        local_cwt: dict[str, dict[str, object]] = {}
        for signal_name, values in loaded.signals.items():
            result = cwt_analysis(values, loaded.sample_rate_hz)
            local_cwt[signal_name] = result
            if case.case_id in {
                "duo1_tc1_background", "duo1_tc1_30hz", "duo1_tc1_50hz"
            }:
                cwt_cache[(case.case_id, signal_name)] = result
            cwt_rows.append({**fields, "signal_name": signal_name, **result["summary"]})
        sst_rows.append({
            **fields,
            "signal_name": "slow_pc1",
            **synchrosqueezed_summary(loaded.signals["slow_pc1"], loaded.sample_rate_hz),
        })
        for envelope_signal in [name for name in loaded.signals if name != "slow_pc1"]:
            coherence_rows.append({
                **fields,
                "first_signal": "slow_pc1",
                "second_signal": envelope_signal,
                **wavelet_coherence(
                    local_cwt["slow_pc1"], local_cwt[envelope_signal],
                    loaded.sample_rate_hz, args.coherence_null_shifts,
                    stable_seed("wavelet-coherence", case.case_id, envelope_signal),
                ),
            })
        for signal_name, values in loaded.signals.items():
            channel_values = loaded.channel_signals[signal_name]
            events, summary = event_rows(values, channel_values, loaded.sample_rate_hz)
            changepoint_rows.append({**fields, "signal_name": signal_name, **summary})
            event_detail_rows.extend([
                {**fields, "signal_name": signal_name, "event_index": index, **event}
                for index, event in enumerate(events, start=1)
            ])
        for filter_name, filtered in preprocessors(
            loaded.signals["slow_pc1"], loaded.sample_rate_hz
        ).items():
            wavelet = cwt_analysis(filtered, loaded.sample_rate_hz)["summary"]
            points = pelt_changepoints(filtered, loaded.sample_rate_hz)
            amplitude = sinusoid_coefficients(filtered, loaded.sample_rate_hz, 1.0 / 3.1)
            filter_rows.append({
                **fields,
                "signal_name": "slow_pc1",
                "filter_name": filter_name,
                "fixed_3p1s_amplitude_sigma": float(np.linalg.norm(amplitude)),
                "changepoint_count": len(points),
                "wavelet_global_peak_frequency_hz": wavelet["global_peak_frequency_hz"],
                "wavelet_significant_ridge_fraction": wavelet["significant_ridge_fraction"],
            })
        if case.condition == "background":
            injection.extend([
                {**fields, **row} for row in injection_rows(
                    loaded.signals["slow_pc1"], loaded.sample_rate_hz
                )
            ])
        print(f"[{case_index}/{len(cases)}] {case.case_id}", flush=True)

    cwt = write_frame(output / "cwt_case_features.csv", cwt_rows)
    coherence = write_frame(output / "cross_wavelet_coherence.csv", coherence_rows)
    sst = write_frame(output / "synchrosqueezed_case_features.csv", sst_rows)
    changes = write_frame(output / "changepoint_relaxation_summary.csv", changepoint_rows)
    write_frame(output / "changepoint_event_details.csv", event_detail_rows)
    filters = write_frame(output / "filter_sensitivity_case_features.csv", filter_rows)
    injections = write_frame(output / "filter_injection_recovery.csv", injection)

    cwt_contrasts = generic_matched_contrasts(
        cases, cwt,
        feature_columns=[
            "global_peak_frequency_hz", "global_peak_power_to_red_noise",
            "significant_point_fraction", "significant_ridge_fraction",
            "ridge_frequency_median_hz", "ridge_frequency_iqr_hz",
        ],
        identity_columns=["signal_name"],
    )
    change_contrasts = generic_matched_contrasts(
        cases, changes,
        feature_columns=[
            "changepoint_count", "changepoint_rate_per_minute",
            "median_absolute_step_robust_sigma", "median_channel_support_fraction",
            "credible_relaxation_count", "median_credible_relaxation_tau_s",
            "event_waveform_repeatability_median_r",
        ],
        identity_columns=["signal_name"],
    )
    coherence_contrasts = generic_matched_contrasts(
        cases, coherence,
        feature_columns=[
            "median_coherence_0p05_0p5hz", "q95_coherence_0p05_0p5hz",
            "fraction_coherence_ge_0p5", "strong_phase_resultant",
        ],
        identity_columns=["first_signal", "second_signal"],
    )
    write_frame(output / "matched_cwt_contrasts.csv", cwt_contrasts)
    write_frame(output / "matched_changepoint_contrasts.csv", change_contrasts)
    write_frame(output / "matched_wavelet_coherence_contrasts.csv", coherence_contrasts)

    plot_representative_scalograms(cwt_cache, figures / "representative_slow_cwt.png")
    plot_injection_recovery(injections, figures / "filter_injection_recovery.png")
    write_manifest(output, "wavelet_relaxation", {
        "case_count": len(cases),
        "wavelet": WAVELET,
        "frequency_grid_hz": FREQUENCIES_HZ.tolist(),
        "coherence_null_shifts": args.coherence_null_shifts,
        "cwt_case_feature_rows": len(cwt),
        "coherence_rows": len(coherence),
        "sst_rows": len(sst),
        "changepoint_summary_rows": len(changes),
        "filter_case_rows": len(filters),
        "injection_rows": len(injections),
    })
    print(f"Output: {output}")
    return output


if __name__ == "__main__":
    main()
