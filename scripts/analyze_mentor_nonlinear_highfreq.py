"""Explore low/high coupling and short-snippet high-frequency nonlinear structure."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pywt
from scipy import signal

from scripts.analyze_pre_electrochemical_dynamics import case_fields, detrended, robust_scale
from scripts.mentor_method_common import (
    METHOD_OUTPUT,
    all_cases,
    generic_matched_contrasts,
    load_analysis_signals,
    load_health_table,
    stable_seed,
    write_frame,
    write_manifest,
)


PHASE_BANDS = {
    "0p05_0p15hz": (0.05, 0.15),
    "0p15_0p5hz": (0.15, 0.5),
}
AMPLITUDE_BAND = (0.5, 2.0)
HIGH_FREQUENCIES_HZ = np.geomspace(20_000.0, 180_000.0, 24)


def normalized(values: np.ndarray) -> np.ndarray:
    x = detrended(values)
    return x / float(robust_scale(x).squeeze())


def band_hilbert(values: np.ndarray, sample_rate: float,
                 low: float, high: float) -> np.ndarray:
    sos = signal.butter(4, [low, high], btype="bandpass", fs=sample_rate, output="sos")
    filtered = signal.sosfiltfilt(sos, normalized(values))
    return signal.hilbert(filtered)


def modulation_index(phase: np.ndarray, amplitude: np.ndarray,
                     bins: int = 18) -> float:
    edges = np.linspace(-np.pi, np.pi, bins + 1)
    index = np.clip(np.digitize(phase, edges) - 1, 0, bins - 1)
    means = np.array([
        np.mean(amplitude[index == item]) if np.any(index == item) else 0.0
        for item in range(bins)
    ])
    probabilities = means / max(float(np.sum(means)), 1e-15)
    use = probabilities > 0.0
    entropy = -float(np.sum(probabilities[use] * np.log(probabilities[use])))
    return float((np.log(bins) - entropy) / np.log(bins))


def phase_amplitude_coupling(
    phase_signal: np.ndarray, amplitude_signal: np.ndarray, sample_rate: float,
    phase_band: tuple[float, float], null_shifts: int, seed: int,
) -> dict[str, float]:
    phase = np.angle(band_hilbert(
        phase_signal, sample_rate, phase_band[0], phase_band[1]
    ))
    amplitude = np.abs(band_hilbert(
        amplitude_signal, sample_rate, AMPLITUDE_BAND[0], AMPLITUDE_BAND[1]
    ))
    observed = modulation_index(phase, amplitude)
    rng = np.random.default_rng(seed)
    amplitude_spectrum = np.fft.rfft(normalized(amplitude_signal))
    null_rows = []
    for _ in range(null_shifts):
        random_phase = rng.uniform(-np.pi, np.pi, len(amplitude_spectrum))
        random_phase[0] = 0.0
        if len(amplitude_signal) % 2 == 0:
            random_phase[-1] = 0.0
        surrogate = np.fft.irfft(
            np.abs(amplitude_spectrum) * np.exp(1j * random_phase),
            n=len(amplitude_signal),
        )
        surrogate_amplitude = np.abs(band_hilbert(
            surrogate, sample_rate, AMPLITUDE_BAND[0], AMPLITUDE_BAND[1]
        ))
        null_rows.append(modulation_index(phase, surrogate_amplitude))
    null = np.asarray(null_rows, dtype=np.float64)
    return {
        "modulation_index": observed,
        "phase_randomized_null_p": float(
            (np.sum(null >= observed) + 1) / (len(null) + 1)
        ),
        "null_modulation_index_median": float(np.median(null)),
        "null_modulation_index_q95": float(np.percentile(null, 95)),
        "null_shift_count": len(null),
    }


def load_common_raw_snippets(archive: Path, healthy_indices: np.ndarray
                             ) -> tuple[np.ndarray, float]:
    with np.load(archive / "raw_snippets.npz") as data:
        values = np.asarray(data["centered_v"][:, :, healthy_indices], dtype=np.float64)
        sample_rate = float(data["sample_rate_hz"])
    scale = np.std(values, axis=1, keepdims=True)
    standardized = values / np.maximum(scale, 1e-15)
    common = np.median(standardized, axis=2)
    common -= np.mean(common, axis=1, keepdims=True)
    return common, sample_rate


def high_frequency_cwt(snippets: np.ndarray, sample_rate: float) -> dict[str, float]:
    scales = pywt.central_frequency("cmor1.5-1.0") * sample_rate / HIGH_FREQUENCIES_HZ
    window_samples = min(snippets.shape[1], int(round(0.1 * sample_rate)))
    global_power = []
    ridge_medians = []
    ridge_iqrs = []
    concentrations = []
    for snippet in snippets:
        start = (len(snippet) - window_samples) // 2
        values = snippet[start:start + window_samples]
        coefficients, frequencies = pywt.cwt(
            values, scales, "cmor1.5-1.0", sampling_period=1.0 / sample_rate,
        )
        power = np.abs(coefficients) ** 2
        global_power.append(np.mean(power, axis=1))
        ridge = frequencies[np.argmax(power, axis=0)]
        ridge_medians.append(float(np.median(ridge)))
        ridge_iqrs.append(float(np.percentile(ridge, 75) - np.percentile(ridge, 25)))
        sorted_power = np.sort(power, axis=0)
        concentrations.append(float(np.median(
            np.sum(sorted_power[-3:], axis=0) / np.maximum(np.sum(power, axis=0), 1e-15)
        )))
    mean_power = np.mean(global_power, axis=0)
    peak = int(np.argmax(mean_power))
    return {
        "high_cwt_global_peak_frequency_hz": float(HIGH_FREQUENCIES_HZ[peak]),
        "high_cwt_peak_to_median_power_ratio": float(
            mean_power[peak] / max(np.median(mean_power), 1e-15)
        ),
        "high_cwt_ridge_frequency_median_hz": float(np.median(ridge_medians)),
        "high_cwt_ridge_frequency_between_snippet_range_hz": float(
            np.max(ridge_medians) - np.min(ridge_medians)
        ),
        "high_cwt_ridge_iqr_median_hz": float(np.median(ridge_iqrs)),
        "high_cwt_top3_scale_concentration_median": float(np.median(concentrations)),
        "raw_snippet_count": snippets.shape[0],
        "analyzed_seconds_per_snippet": window_samples / sample_rate,
    }


def segmented_fft(snippets: np.ndarray, nperseg: int = 4096) -> np.ndarray:
    window = signal.windows.hann(nperseg, sym=False)
    step = nperseg // 2
    rows = []
    for snippet in snippets:
        for start in range(0, len(snippet) - nperseg + 1, step):
            segment_values = signal.detrend(snippet[start:start + nperseg], type="linear")
            rows.append(np.fft.rfft(segment_values * window))
    return np.asarray(rows, dtype=np.complex128)


def bicoherence_values(
    spectra: np.ndarray, first_bins: np.ndarray, second_bins: np.ndarray,
    phase: np.ndarray | None = None,
) -> np.ndarray:
    values = spectra if phase is None else np.abs(spectra) * np.exp(1j * phase)
    first = values[:, first_bins]
    second = values[:, second_bins]
    summed = values[:, first_bins + second_bins]
    numerator = np.abs(np.mean(first * second * np.conj(summed), axis=0)) ** 2
    denominator = (
        np.mean(np.abs(first * second) ** 2, axis=0)
        * np.mean(np.abs(summed) ** 2, axis=0)
    )
    return numerator / np.maximum(denominator, 1e-30)


def bicoherence_analysis(snippets: np.ndarray, sample_rate: float,
                         surrogate_count: int, seed: int) -> dict[str, object]:
    nperseg = 4096
    spectra = segmented_fft(snippets, nperseg=nperseg)
    maximum_bin = nperseg // 2
    grid = np.arange(16, maximum_bin, 16, dtype=int)
    first_grid, second_grid = np.meshgrid(grid, grid, indexing="ij")
    use = (
        (first_grid <= second_grid)
        & (first_grid + second_grid <= maximum_bin)
    )
    first_bins = first_grid[use]
    second_bins = second_grid[use]
    observed = bicoherence_values(spectra, first_bins, second_bins)
    snippet_maxima = []
    snippet_sum_frequencies = []
    for snippet in snippets:
        snippet_spectra = segmented_fft(snippet[None, :], nperseg=nperseg)
        snippet_values = bicoherence_values(
            snippet_spectra, first_bins, second_bins
        )
        snippet_best = int(np.argmax(snippet_values))
        snippet_maxima.append(float(snippet_values[snippet_best]))
        snippet_sum_frequencies.append(float(
            (first_bins[snippet_best] + second_bins[snippet_best])
            * sample_rate / nperseg
        ))
    rng = np.random.default_rng(seed)
    null_maxima = []
    for _ in range(surrogate_count):
        random_phase = rng.uniform(-np.pi, np.pi, spectra.shape)
        random_phase[:, 0] = 0.0
        random_phase[:, -1] = 0.0
        null_maxima.append(float(np.max(bicoherence_values(
            spectra, first_bins, second_bins, random_phase
        ))))
    null_maxima_array = np.asarray(null_maxima)
    best = int(np.argmax(observed))
    resolution = sample_rate / nperseg
    return {
        "bicoherence_max": float(observed[best]),
        "bicoherence_q99": float(np.percentile(observed, 99)),
        "bicoherence_median": float(np.median(observed)),
        "bicoherence_snippet_max_median": float(np.median(snippet_maxima)),
        "bicoherence_snippet_max_range": float(np.max(snippet_maxima) - np.min(snippet_maxima)),
        "bicoherence_snippet_peak_sum_frequency_range_hz": float(
            np.max(snippet_sum_frequencies) - np.min(snippet_sum_frequencies)
        ),
        "bicoherence_max_f1_hz": float(first_bins[best] * resolution),
        "bicoherence_max_f2_hz": float(second_bins[best] * resolution),
        "bicoherence_max_sum_hz": float((first_bins[best] + second_bins[best]) * resolution),
        "bicoherence_max_phase_surrogate_p": float(
            (np.sum(null_maxima_array >= observed[best]) + 1)
            / (len(null_maxima_array) + 1)
        ),
        "bicoherence_null_max_q95": float(np.percentile(null_maxima_array, 95)),
        "bicoherence_surrogate_count": surrogate_count,
        "bicoherence_fft_segment_count": spectra.shape[0],
        "bicoherence_frequency_resolution_hz": resolution,
        "bicoherence_grid_pair_count": len(observed),
        "_map_first_hz": first_bins * resolution,
        "_map_second_hz": second_bins * resolution,
        "_map_values": observed,
    }


def plot_bicoherence_maps(cache: dict[str, dict[str, object]], output: Path) -> None:
    case_ids = ["duo1_tc1_background", "duo1_tc1_30hz", "duo1_tc1_50hz"]
    available = [item for item in case_ids if item in cache]
    if not available:
        return
    fig = plt.figure(figsize=(5.2 * len(available), 4.8))
    grid = fig.add_gridspec(
        1, len(available) + 1,
        width_ratios=[*[1.0] * len(available), 0.06], wspace=0.25,
    )
    axes = []
    for index in range(len(available)):
        axes.append(fig.add_subplot(
            grid[0, index],
            sharex=axes[0] if axes else None,
            sharey=axes[0] if axes else None,
        ))
    for axis, case_id in zip(axes, available):
        result = cache[case_id]
        scatter = axis.scatter(
            np.asarray(result["_map_first_hz"]) / 1000.0,
            np.asarray(result["_map_second_hz"]) / 1000.0,
            c=np.asarray(result["_map_values"]), s=8, cmap="magma", vmin=0.0, vmax=0.15,
        )
        axis.set_title(case_id)
        axis.set_xlabel("f1 (kHz)")
        axis.set_aspect("equal")
    axes[0].set_ylabel("f2 (kHz)")
    color_axis = fig.add_subplot(grid[0, -1])
    colorbar = fig.colorbar(scatter, cax=color_axis)
    colorbar.set_label("Squared bicoherence")
    fig.suptitle("Exploratory bicoherence from three 1 s raw snippets")
    fig.subplots_adjust(left=0.07, right=0.94, top=0.88, bottom=0.12)
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=METHOD_OUTPUT / "nonlinear_highfreq")
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--pac-null-shifts", type=int, default=39)
    parser.add_argument("--bicoherence-surrogates", type=int, default=49)
    args = parser.parse_args(argv)
    output = args.output
    figures = output / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    health = load_health_table()
    cases = all_cases()
    if args.max_cases > 0:
        cases = cases[:args.max_cases]

    pac_rows: list[dict[str, object]] = []
    high_cwt_rows: list[dict[str, object]] = []
    bicoherence_rows: list[dict[str, object]] = []
    bicoherence_cache: dict[str, dict[str, object]] = {}
    for case_index, case in enumerate(cases, start=1):
        loaded = load_analysis_signals(case, health)
        fields = case_fields(case)
        for phase_name, phase_band in PHASE_BANDS.items():
            for amplitude_signal in [name for name in loaded.signals if name != "slow_pc1"]:
                try:
                    result = phase_amplitude_coupling(
                        loaded.signals["slow_pc1"], loaded.signals[amplitude_signal],
                        loaded.sample_rate_hz, phase_band, args.pac_null_shifts,
                        stable_seed("pac", case.case_id, phase_name, amplitude_signal),
                    )
                    status = "ok"
                except ValueError:
                    result = {
                        "modulation_index": np.nan,
                        "phase_randomized_null_p": np.nan,
                        "null_modulation_index_median": np.nan,
                        "null_modulation_index_q95": np.nan,
                        "null_shift_count": 0,
                    }
                    status = "record_too_short_for_filter"
                pac_rows.append({
                    **fields,
                    "phase_signal": "slow_pc1",
                    "phase_band": phase_name,
                    "amplitude_signal": amplitude_signal,
                    "amplitude_modulation_band": "0p5_2hz",
                    "analysis_status": status,
                    **result,
                })
        snippets, raw_rate = load_common_raw_snippets(case.archive, loaded.healthy_indices)
        high_cwt_rows.append({
            **fields,
            "analysis_scope": "three_1s_raw_snippets_only",
            **high_frequency_cwt(snippets, raw_rate),
        })
        bicoherence = bicoherence_analysis(
            snippets, raw_rate, args.bicoherence_surrogates,
            stable_seed("bicoherence", case.case_id),
        )
        if case.case_id in {
            "duo1_tc1_background", "duo1_tc1_30hz", "duo1_tc1_50hz"
        }:
            bicoherence_cache[case.case_id] = bicoherence
        bicoherence_rows.append({
            **fields,
            "analysis_scope": "three_1s_raw_snippets_only",
            **{key: value for key, value in bicoherence.items() if not key.startswith("_map")},
        })
        print(f"[{case_index}/{len(cases)}] {case.case_id}", flush=True)

    pac = write_frame(output / "phase_amplitude_coupling.csv", pac_rows)
    high_cwt = write_frame(output / "short_high_frequency_cwt.csv", high_cwt_rows)
    bicoherence = write_frame(output / "short_high_frequency_bicoherence.csv", bicoherence_rows)
    write_frame(
        output / "matched_phase_amplitude_contrasts.csv",
        generic_matched_contrasts(
            cases, pac,
            ["modulation_index", "null_modulation_index_q95"],
            ["phase_signal", "phase_band", "amplitude_signal", "amplitude_modulation_band"],
        ),
    )
    write_frame(
        output / "matched_short_high_cwt_contrasts.csv",
        generic_matched_contrasts(
            cases, high_cwt,
            [
                "high_cwt_global_peak_frequency_hz",
                "high_cwt_peak_to_median_power_ratio",
                "high_cwt_ridge_frequency_median_hz",
                "high_cwt_ridge_frequency_between_snippet_range_hz",
                "high_cwt_ridge_iqr_median_hz",
                "high_cwt_top3_scale_concentration_median",
            ],
            ["analysis_scope"],
        ),
    )
    write_frame(
        output / "matched_short_bicoherence_contrasts.csv",
        generic_matched_contrasts(
            cases, bicoherence,
            [
                "bicoherence_max", "bicoherence_q99", "bicoherence_median",
                "bicoherence_snippet_max_median", "bicoherence_snippet_max_range",
                "bicoherence_snippet_peak_sum_frequency_range_hz",
            ],
            ["analysis_scope"],
        ),
    )
    plot_bicoherence_maps(
        bicoherence_cache, figures / "representative_short_bicoherence.png"
    )
    write_manifest(output, "nonlinear_highfreq", {
        "case_count": len(cases),
        "pac_null_shifts": args.pac_null_shifts,
        "bicoherence_surrogates": args.bicoherence_surrogates,
        "pac_rows": len(pac),
        "high_cwt_rows": len(high_cwt),
        "bicoherence_rows": len(bicoherence),
        "high_frequency_scope_limit": "three 1 s raw snippets per file",
    })
    print(f"Output: {output}")
    return output


if __name__ == "__main__":
    main()
