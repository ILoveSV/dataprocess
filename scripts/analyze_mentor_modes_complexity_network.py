"""Explore adaptive modes, complexity, robust common state, and directed networks."""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import signal, spatial, stats
from sklearn.exceptions import ConvergenceWarning
from statsmodels.tsa.api import VAR
from statsmodels.tsa.statespace.structural import UnobservedComponents

from scripts.analyze_pre_electrochemical_dynamics import (
    case_fields,
    detrended,
    robust_scale,
    standardized,
)
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
import antropy as ant
from PyEMD import EEMD, EMD
from vmdpy import VMD


ANALYSIS_SIGNALS = ("slow_pc1", "fast_residual_rms_pc1")
MODE_BANDS = {
    "below_0p15hz": (0.0, 0.15),
    "0p15_0p5hz": (0.15, 0.5),
    "0p5_2hz": (0.5, 2.0),
    "above_2hz": (2.0, np.inf),
}


def normalized(values: np.ndarray) -> np.ndarray:
    residual = detrended(values)
    return residual / float(robust_scale(residual).squeeze())


def multiscale_entropy(values: np.ndarray, scales: range = range(1, 11)) -> np.ndarray:
    x = normalized(values)
    result = []
    for scale in scales:
        usable = len(x) // scale * scale
        coarse = x[:usable].reshape(-1, scale).mean(axis=1)
        if len(coarse) < 40:
            result.append(np.nan)
            continue
        value = float(ant.sample_entropy(coarse, order=2))
        result.append(value if np.isfinite(value) else np.nan)
    return np.asarray(result, dtype=np.float64)


def multifractal_dfa(
    values: np.ndarray, q_values: tuple[float, ...] = (-4.0, -2.0, 0.0, 2.0, 4.0),
) -> dict[str, float]:
    """Estimate generalized Hurst exponents with linear-detrended MF-DFA."""
    x = normalized(values)
    profile = np.cumsum(x - np.mean(x))
    maximum_scale = max(16, len(x) // 4)
    scales = np.unique(np.geomspace(8, maximum_scale, 12).astype(int))
    fluctuation = {q: [] for q in q_values}
    valid_scales = []
    for scale in scales:
        segment_count = len(profile) // scale
        if segment_count < 4:
            continue
        variances = []
        coordinates = np.arange(scale, dtype=np.float64)
        for offset in (0, len(profile) - segment_count * scale):
            for segment_index in range(segment_count):
                start = offset + segment_index * scale
                segment_values = profile[start:start + scale]
                coefficients = np.polyfit(coordinates, segment_values, 1)
                residual = segment_values - np.polyval(coefficients, coordinates)
                variances.append(float(np.mean(residual ** 2)))
        variance = np.maximum(np.asarray(variances, dtype=np.float64), 1e-15)
        valid_scales.append(scale)
        for q in q_values:
            if q == 0.0:
                value = float(np.exp(0.5 * np.mean(np.log(variance))))
            else:
                value = float(np.mean(variance ** (q / 2.0)) ** (1.0 / q))
            fluctuation[q].append(value)
    log_scale = np.log(np.asarray(valid_scales, dtype=np.float64))
    hq = np.asarray([
        np.polyfit(log_scale, np.log(np.maximum(fluctuation[q], 1e-15)), 1)[0]
        for q in q_values
    ], dtype=np.float64)
    q_array = np.asarray(q_values, dtype=np.float64)
    tau = q_array * hq - 1.0
    alpha = np.gradient(tau, q_array)
    spectrum = q_array * alpha - tau
    return {
        "mfdfa_h_q_minus4": float(hq[0]),
        "mfdfa_h_q_0": float(hq[2]),
        "mfdfa_h_q_2": float(hq[3]),
        "mfdfa_h_q_4": float(hq[4]),
        "mfdfa_delta_h_minus4_to_4": float(hq[0] - hq[-1]),
        "mfdfa_singularity_width": float(np.max(alpha) - np.min(alpha)),
        "mfdfa_spectrum_peak": float(np.max(spectrum)),
        "mfdfa_scale_count": len(valid_scales),
    }


def diagonal_line_lengths(matrix: np.ndarray, minimum: int = 2) -> list[int]:
    lengths: list[int] = []
    for offset in range(-matrix.shape[0] + 1, matrix.shape[1]):
        diagonal = np.diagonal(matrix, offset=offset)
        padded = np.r_[False, diagonal, False]
        changes = np.diff(padded.astype(np.int8))
        starts = np.flatnonzero(changes == 1)
        ends = np.flatnonzero(changes == -1)
        lengths.extend(int(value) for value in ends - starts if value >= minimum)
    return lengths


def vertical_line_lengths(matrix: np.ndarray, minimum: int = 2) -> list[int]:
    lengths: list[int] = []
    for column in range(matrix.shape[1]):
        values = matrix[:, column]
        padded = np.r_[False, values, False]
        changes = np.diff(padded.astype(np.int8))
        starts = np.flatnonzero(changes == 1)
        ends = np.flatnonzero(changes == -1)
        lengths.extend(int(value) for value in ends - starts if value >= minimum)
    return lengths


def recurrence_features(values: np.ndarray) -> dict[str, float]:
    x = normalized(values)
    acf = signal.correlate(x, x, mode="full", method="fft")[len(x) - 1:]
    acf /= np.maximum(np.arange(len(x), 0, -1), 1)
    acf /= max(acf[0], 1e-15)
    below = np.flatnonzero(acf <= np.exp(-1.0))
    delay = int(np.clip(below[0] if len(below) else 1, 1, 20))
    dimension = 3
    count = len(x) - (dimension - 1) * delay
    if count < 80:
        return {
            "rqa_delay_samples": delay,
            "rqa_recurrence_rate": np.nan,
            "rqa_determinism": np.nan,
            "rqa_laminarity": np.nan,
            "rqa_trapping_time_samples": np.nan,
            "rqa_diagonal_entropy": np.nan,
        }
    embedded = np.column_stack([
        x[index * delay:index * delay + count] for index in range(dimension)
    ])
    distance = spatial.distance.squareform(spatial.distance.pdist(embedded))
    upper = distance[np.triu_indices(count, 1)]
    threshold = float(np.percentile(upper, 5.0))
    recurrence = distance <= threshold
    np.fill_diagonal(recurrence, False)
    recurrence_points = int(np.sum(recurrence))
    diagonal = diagonal_line_lengths(recurrence, minimum=2)
    vertical = vertical_line_lengths(recurrence, minimum=2)
    diagonal_points = int(np.sum(diagonal))
    vertical_points = int(np.sum(vertical))
    diagonal_entropy = np.nan
    if diagonal:
        _, counts = np.unique(diagonal, return_counts=True)
        probabilities = counts / counts.sum()
        diagonal_entropy = float(-np.sum(probabilities * np.log(probabilities)))
    return {
        "rqa_delay_samples": delay,
        "rqa_recurrence_rate": float(recurrence_points / max(count * (count - 1), 1)),
        "rqa_determinism": float(diagonal_points / max(recurrence_points, 1)),
        "rqa_laminarity": float(vertical_points / max(recurrence_points, 1)),
        "rqa_trapping_time_samples": float(np.mean(vertical)) if vertical else 0.0,
        "rqa_diagonal_entropy": diagonal_entropy,
    }


def phase_randomized_surrogate(values: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    x = normalized(values)
    spectrum = np.fft.rfft(x)
    phase = rng.uniform(0.0, 2.0 * np.pi, len(spectrum))
    phase[0] = 0.0
    if len(x) % 2 == 0:
        phase[-1] = 0.0
    return np.fft.irfft(np.abs(spectrum) * np.exp(1j * phase), n=len(x))


def complexity_features(values: np.ndarray, sample_rate: float,
                        surrogate_count: int, seed: int) -> dict[str, float]:
    x = normalized(values)
    mse = multiscale_entropy(x)
    base = {
        "dfa_alpha": float(ant.detrended_fluctuation(x)),
        **multifractal_dfa(x),
        "sample_entropy": float(ant.sample_entropy(x, order=2)),
        "permutation_entropy_normalized": float(
            ant.perm_entropy(x, order=3, delay=1, normalize=True)
        ),
        "spectral_entropy_normalized": float(ant.spectral_entropy(
            x, sf=sample_rate, method="welch", normalize=True,
            nperseg=min(256, len(x)),
        )),
        "multiscale_entropy_mean_1_5": float(np.nanmean(mse[:5])),
        "multiscale_entropy_mean_6_10": (
            float(np.nanmean(mse[5:])) if np.isfinite(mse[5:]).any() else np.nan
        ),
        "multiscale_entropy_slope": float(
            np.polyfit(np.arange(1, 11)[np.isfinite(mse)], mse[np.isfinite(mse)], 1)[0]
        ) if np.isfinite(mse).sum() >= 3 else np.nan,
        **recurrence_features(x),
    }
    rng = np.random.default_rng(seed)
    surrogate_dfa = []
    surrogate_entropy = []
    for _ in range(surrogate_count):
        surrogate = phase_randomized_surrogate(x, rng)
        surrogate_dfa.append(float(ant.detrended_fluctuation(surrogate)))
        surrogate_entropy.append(float(ant.sample_entropy(surrogate, order=2)))
    for metric, null in (
        ("dfa_alpha", surrogate_dfa),
        ("sample_entropy", surrogate_entropy),
    ):
        null_values = np.asarray(null, dtype=np.float64)
        observed = base[metric]
        center = float(np.median(null_values))
        deviation = abs(observed - center)
        p_value = float((np.sum(np.abs(null_values - center) >= deviation) + 1)
                        / (len(null_values) + 1))
        base[f"{metric}_phase_surrogate_p"] = p_value
        base[f"{metric}_minus_surrogate_median"] = float(observed - center)
    base["phase_surrogate_count"] = surrogate_count
    return base


def mode_band_energies(modes: np.ndarray, sample_rate: float) -> dict[str, float]:
    total = float(np.sum(modes ** 2))
    band_energy = {"below_0p15hz": 0.0, "0p15_0p5hz": 0.0, "0p5_2hz": 0.0,
                   "above_2hz": 0.0}
    centers = []
    mode_energies = []
    for mode in modes:
        frequency, power = signal.welch(mode, fs=sample_rate, nperseg=min(256, len(mode)))
        center = float(frequency[int(np.argmax(power))])
        energy = float(np.sum(mode ** 2))
        centers.append(center)
        mode_energies.append(energy)
        if center < 0.15:
            band_energy["below_0p15hz"] += energy
        elif center < 0.5:
            band_energy["0p15_0p5hz"] += energy
        elif center < 2.0:
            band_energy["0p5_2hz"] += energy
        else:
            band_energy["above_2hz"] += energy
    fractions = np.asarray(mode_energies) / max(total, 1e-15)
    return {
        "mode_count": modes.shape[0],
        "dominant_mode_center_hz": float(centers[int(np.argmax(mode_energies))]),
        "mode_energy_entropy": float(-np.sum(
            fractions[fractions > 0] * np.log(fractions[fractions > 0])
        )),
        **{f"mode_energy_fraction_{key}": value / max(total, 1e-15)
           for key, value in band_energy.items()},
    }


def emd_features(values: np.ndarray, sample_rate: float) -> dict[str, float]:
    x = normalized(values)
    decomposition = EMD().emd(x, max_imf=7)
    result = mode_band_energies(decomposition, sample_rate)
    reconstruction = np.sum(decomposition, axis=0)
    result["reconstruction_nrmse"] = float(
        np.sqrt(np.mean((x - reconstruction) ** 2)) / max(np.std(x), 1e-15)
    )
    return result


def aligned_multichannel_emd_features(
    matrix: np.ndarray, sample_rate: float,
) -> dict[str, float]:
    """Align channelwise EMD modes by band without claiming strict MEMD."""
    values = standardized(matrix)
    per_channel: list[list[tuple[float, float]]] = []
    for channel in range(values.shape[1]):
        decomposition = EMD().emd(values[:, channel], max_imf=7)
        total = float(np.sum(decomposition ** 2))
        rows: list[tuple[float, float]] = []
        for mode in decomposition:
            frequency, power = signal.welch(
                mode, fs=sample_rate, nperseg=min(256, len(mode))
            )
            rows.append((
                float(frequency[int(np.argmax(power))]),
                float(np.sum(mode ** 2) / max(total, 1e-15)),
            ))
        per_channel.append(rows)
    result: dict[str, float] = {
        "aligned_emd_channel_count": matrix.shape[1],
        "aligned_emd_median_mode_count": float(np.median([
            len(rows) for rows in per_channel
        ])),
    }
    for name, (low, high) in MODE_BANDS.items():
        present = []
        centers = []
        energy = []
        for rows in per_channel:
            selected = [(center, fraction) for center, fraction in rows
                        if low <= center < high]
            present.append(bool(selected))
            centers.extend(center for center, _ in selected)
            energy.append(sum(fraction for _, fraction in selected))
        result[f"aligned_emd_channel_presence_fraction_{name}"] = float(np.mean(present))
        result[f"aligned_emd_energy_fraction_median_{name}"] = float(np.median(energy))
        result[f"aligned_emd_center_iqr_hz_{name}"] = (
            float(np.percentile(centers, 75) - np.percentile(centers, 25))
            if centers else np.nan
        )
    return result


def eemd_features(values: np.ndarray, sample_rate: float, seed: int,
                  trials: int = 20) -> dict[str, float]:
    x = normalized(values)
    decomposition_model = EEMD(trials=trials, noise_width=0.05, parallel=False)
    decomposition_model.noise_seed(seed)
    decomposition = decomposition_model.eemd(x, max_imf=7)
    result = mode_band_energies(decomposition, sample_rate)
    reconstruction = np.sum(decomposition, axis=0)
    result["reconstruction_nrmse"] = float(
        np.sqrt(np.mean((x - reconstruction) ** 2)) / max(np.std(x), 1e-15)
    )
    result["ensemble_trials"] = trials
    return result


def vmd_features(values: np.ndarray, sample_rate: float, mode_count: int,
                 alpha: float) -> dict[str, float]:
    x = normalized(values)
    if len(x) % 2:
        x = x[:-1]
    modes, _, omega = VMD(x, alpha, 0.0, mode_count, 0, 1, 1e-7)
    result = mode_band_energies(modes, sample_rate)
    result["requested_mode_count"] = mode_count
    result["alpha"] = alpha
    result["reconstruction_nrmse"] = float(
        np.sqrt(np.mean((x - np.sum(modes, axis=0)) ** 2)) / max(np.std(x), 1e-15)
    )
    centers = np.sort(np.asarray(omega[-1], dtype=np.float64) * sample_rate)
    result["variational_center_frequencies_hz"] = ";".join(f"{item:.6g}" for item in centers)
    return result


def robust_pca(matrix: np.ndarray, maximum_iterations: int = 500,
               tolerance: float = 1e-7) -> tuple[np.ndarray, np.ndarray, int]:
    data = standardized(matrix)
    norm_two = np.linalg.norm(data, 2)
    norm_inf = np.linalg.norm(data.ravel(), np.inf) / np.sqrt(max(data.shape))
    dual = data / max(norm_two, norm_inf, 1e-15)
    sparse = np.zeros_like(data)
    low_rank = np.zeros_like(data)
    mu = 1.25 / max(norm_two, 1e-15)
    mu_bar = mu * 1e7
    rho = 1.5
    lam = 1.0 / np.sqrt(max(data.shape))
    norm_data = np.linalg.norm(data, "fro")
    for iteration in range(1, maximum_iterations + 1):
        temp = data - sparse + dual / mu
        left, singular, right = np.linalg.svd(temp, full_matrices=False)
        keep = singular > 1.0 / mu
        if np.any(keep):
            low_rank = (left[:, keep] * (singular[keep] - 1.0 / mu)) @ right[keep]
        else:
            low_rank.fill(0.0)
        temp = data - low_rank + dual / mu
        sparse = np.sign(temp) * np.maximum(np.abs(temp) - lam / mu, 0.0)
        residual = data - low_rank - sparse
        dual += mu * residual
        mu = min(mu * rho, mu_bar)
        if np.linalg.norm(residual, "fro") / max(norm_data, 1e-15) < tolerance:
            break
    return low_rank, sparse, iteration


def robust_pca_features(matrix: np.ndarray) -> dict[str, float]:
    low_rank, sparse, iterations = robust_pca(matrix)
    total_energy = float(np.sum(standardized(matrix) ** 2))
    sparse_energy_by_channel = np.sum(sparse ** 2, axis=0)
    singular = np.linalg.svd(low_rank, compute_uv=False)
    rank = int(np.sum(singular > max(singular[0] * 1e-6, 1e-10))) if len(singular) else 0
    return {
        "rpca_rank": rank,
        "rpca_low_rank_energy_fraction": float(np.sum(low_rank ** 2) / max(total_energy, 1e-15)),
        "rpca_sparse_energy_fraction": float(np.sum(sparse ** 2) / max(total_energy, 1e-15)),
        "rpca_sparse_entry_fraction": float(np.mean(np.abs(sparse) > 1e-6)),
        "rpca_max_channel_sparse_energy_fraction": float(
            np.max(sparse_energy_by_channel) / max(np.sum(sparse_energy_by_channel), 1e-15)
        ),
        "rpca_iterations": iterations,
    }


def state_space_features(values: np.ndarray) -> dict[str, float]:
    x = normalized(values)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=ConvergenceWarning)
        warnings.simplefilter("ignore", category=RuntimeWarning)
        model = UnobservedComponents(x, level="local linear trend")
        fit = model.fit(disp=False, maxiter=300)
    parameters = dict(zip(fit.param_names, fit.params))
    observation = float(parameters.get("sigma2.irregular", np.nan))
    level = float(parameters.get("sigma2.level", np.nan))
    trend = float(parameters.get("sigma2.trend", np.nan))
    denominator = float(np.dot(x[:-1], x[:-1]))
    autoregressive = float(np.dot(x[:-1], x[1:]) / max(denominator, 1e-15))
    return {
        "state_space_log_likelihood_per_sample": float(fit.llf / len(x)),
        "state_space_observation_variance": observation,
        "state_space_level_variance": level,
        "state_space_trend_variance": trend,
        "state_space_level_to_observation_variance": float(
            level / max(observation, 1e-15)
        ) if np.isfinite(level) and np.isfinite(observation) else np.nan,
        "state_space_ar1": autoregressive,
        "state_space_converged": bool(fit.mle_retvals.get("converged", False)),
    }


def benjamini_hochberg(p_values: np.ndarray) -> np.ndarray:
    values = np.asarray(p_values, dtype=np.float64)
    order = np.argsort(values)
    ranked = values[order]
    adjusted = ranked * len(values) / np.arange(1, len(values) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    result = np.empty_like(adjusted)
    result[order] = np.clip(adjusted, 0.0, 1.0)
    return result


def granger_network(matrix: np.ndarray, channel_indices: np.ndarray
                    ) -> tuple[list[dict[str, object]], dict[str, float]]:
    data = standardized(matrix)
    try:
        fit = VAR(data).fit(maxlags=5, ic="aic", trend="c")
        if fit.k_ar == 0:
            fit = VAR(data).fit(maxlags=1, trend="c")
    except Exception:
        return [], {
            "var_lag_order": np.nan,
            "granger_test_count": 0,
            "granger_fdr_edge_count": 0,
            "granger_fdr_edge_density": np.nan,
            "granger_median_log10_p": np.nan,
        }
    rows = []
    for source in range(data.shape[1]):
        for target in range(data.shape[1]):
            if source == target:
                continue
            try:
                test = fit.test_causality(target, [source], kind="f")
                p_value = float(test.pvalue)
                statistic = float(test.test_statistic)
            except Exception:
                p_value = 1.0
                statistic = np.nan
            rows.append({
                "source_channel": int(channel_indices[source] + 1),
                "target_channel": int(channel_indices[target] + 1),
                "f_statistic": statistic,
                "p_value": p_value,
            })
    adjusted = benjamini_hochberg(np.array([row["p_value"] for row in rows]))
    for row, value in zip(rows, adjusted):
        row["fdr_p_value"] = float(value)
        row["fdr_significant"] = bool(value <= 0.05)
    significant = int(np.sum(adjusted <= 0.05))
    return rows, {
        "var_lag_order": int(fit.k_ar),
        "granger_test_count": len(rows),
        "granger_fdr_edge_count": significant,
        "granger_fdr_edge_density": significant / max(len(rows), 1),
        "granger_median_log10_p": float(np.median(np.log10(np.maximum(
            [row["p_value"] for row in rows], 1e-300
        )))),
    }


def plot_representative_modes(values: np.ndarray, sample_rate: float,
                              output: Path, title: str) -> None:
    x = normalized(values)
    if len(x) % 2:
        x = x[:-1]
    modes, _, omega = VMD(x, 2000.0, 0.0, 4, 0, 1, 1e-7)
    time = np.arange(len(x)) / sample_rate
    fig, axes = plt.subplots(5, 1, figsize=(11, 8), sharex=True)
    axes[0].plot(time, x, linewidth=0.8, color="#333333")
    axes[0].set_ylabel("signal")
    centers = np.asarray(omega[-1]) * sample_rate
    for index, mode in enumerate(modes):
        axes[index + 1].plot(time, mode, linewidth=0.8)
        axes[index + 1].set_ylabel(f"M{index + 1}\n{centers[index]:.2f}Hz")
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=METHOD_OUTPUT / "modes_complexity_network")
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--surrogates", type=int, default=39)
    parser.add_argument("--eemd-trials", type=int, default=20)
    args = parser.parse_args(argv)
    output = args.output
    figures = output / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    cases = all_cases()
    if args.max_cases > 0:
        cases = cases[:args.max_cases]
    health = load_health_table()

    complexity_rows: list[dict[str, object]] = []
    mode_rows: list[dict[str, object]] = []
    aligned_emd_rows: list[dict[str, object]] = []
    network_rows: list[dict[str, object]] = []
    granger_rows: list[dict[str, object]] = []
    representative = None

    for case_index, case in enumerate(cases, start=1):
        loaded = load_analysis_signals(case, health)
        fields = case_fields(case)
        for signal_name in ANALYSIS_SIGNALS:
            values = loaded.signals[signal_name]
            complexity_rows.append({
                **fields,
                "signal_name": signal_name,
                **complexity_features(
                    values, loaded.sample_rate_hz, args.surrogates,
                    stable_seed("complexity", case.case_id, signal_name),
                ),
            })
            mode_rows.append({
                **fields, "signal_name": signal_name, "method": "EMD",
                "parameter_key": "max_imf=7", **emd_features(values, loaded.sample_rate_hz),
            })
            if signal_name == "slow_pc1":
                mode_rows.append({
                    **fields, "signal_name": signal_name, "method": "EEMD",
                    "parameter_key": f"trials={args.eemd_trials};noise=0.05",
                    **eemd_features(
                        values, loaded.sample_rate_hz,
                        stable_seed("eemd", case.case_id), args.eemd_trials,
                    ),
                })
            for mode_count in (3, 4, 5):
                for alpha in ((500.0, 2000.0, 8000.0) if mode_count == 4 else (2000.0,)):
                    mode_rows.append({
                        **fields, "signal_name": signal_name, "method": "VMD",
                        "parameter_key": f"K={mode_count};alpha={alpha:g}",
                        **vmd_features(values, loaded.sample_rate_hz, mode_count, alpha),
                    })

        network = {
            **fields,
            **robust_pca_features(loaded.slow_channels),
            **state_space_features(loaded.signals["slow_pc1"]),
        }
        aligned_emd_rows.append({
            **fields,
            "method": "channelwise_EMD_band_alignment",
            "method_scope": "multichannel approximation; not projection MEMD",
            **aligned_multichannel_emd_features(
                loaded.slow_channels, loaded.sample_rate_hz
            ),
        })
        edges, granger_summary = granger_network(
            loaded.slow_channels, loaded.healthy_indices
        )
        network.update(granger_summary)
        network_rows.append(network)
        granger_rows.extend([{**fields, **row} for row in edges])
        if case.case_id == "duo1_tc1_30hz":
            representative = (loaded.signals["slow_pc1"], loaded.sample_rate_hz)
        print(f"[{case_index}/{len(cases)}] {case.case_id}", flush=True)

    complexity = write_frame(output / "complexity_case_features.csv", complexity_rows)
    modes = write_frame(output / "adaptive_mode_case_features.csv", mode_rows)
    aligned_emd = write_frame(
        output / "aligned_multichannel_emd_case_features.csv", aligned_emd_rows
    )
    network = write_frame(output / "network_state_case_features.csv", network_rows)
    write_frame(output / "granger_channel_edges.csv", granger_rows)

    complexity_features_to_compare = [
        "dfa_alpha", "sample_entropy", "permutation_entropy_normalized",
        "mfdfa_h_q_2", "mfdfa_delta_h_minus4_to_4", "mfdfa_singularity_width",
        "spectral_entropy_normalized", "multiscale_entropy_mean_1_5",
        "multiscale_entropy_mean_6_10", "multiscale_entropy_slope",
        "rqa_determinism", "rqa_laminarity", "rqa_trapping_time_samples",
        "rqa_diagonal_entropy",
    ]
    mode_features_to_compare = [
        "dominant_mode_center_hz", "mode_energy_entropy",
        "mode_energy_fraction_below_0p15hz", "mode_energy_fraction_0p15_0p5hz",
        "mode_energy_fraction_0p5_2hz", "mode_energy_fraction_above_2hz",
        "reconstruction_nrmse",
    ]
    network_features_to_compare = [
        "rpca_rank", "rpca_low_rank_energy_fraction", "rpca_sparse_energy_fraction",
        "rpca_sparse_entry_fraction", "rpca_max_channel_sparse_energy_fraction",
        "state_space_level_to_observation_variance", "state_space_ar1",
        "granger_fdr_edge_count", "granger_fdr_edge_density",
    ]
    write_frame(
        output / "matched_complexity_contrasts.csv",
        generic_matched_contrasts(
            cases, complexity, complexity_features_to_compare, ["signal_name"]
        ),
    )
    write_frame(
        output / "matched_mode_contrasts.csv",
        generic_matched_contrasts(
            cases, modes, mode_features_to_compare,
            ["signal_name", "method", "parameter_key"],
        ),
    )
    aligned_emd_features_to_compare = [
        column for column in aligned_emd.columns
        if column.startswith("aligned_emd_") and column != "aligned_emd_channel_count"
    ]
    write_frame(
        output / "matched_aligned_multichannel_emd_contrasts.csv",
        generic_matched_contrasts(
            cases, aligned_emd, aligned_emd_features_to_compare,
            ["method", "method_scope"],
        ),
    )
    write_frame(
        output / "matched_network_state_contrasts.csv",
        generic_matched_contrasts(cases, network, network_features_to_compare, []),
    )
    if representative is not None:
        plot_representative_modes(
            representative[0], representative[1],
            figures / "representative_vmd_modes.png",
            "VMD of duo1 TC1 30 Hz slow common mode",
        )
    write_manifest(output, "modes_complexity_network", {
        "case_count": len(cases),
        "signals": list(ANALYSIS_SIGNALS),
        "phase_surrogate_count": args.surrogates,
        "eemd_trials": args.eemd_trials,
        "complexity_rows": len(complexity),
        "mode_rows": len(modes),
        "aligned_multichannel_emd_rows": len(aligned_emd),
        "network_rows": len(network),
        "granger_edge_rows": len(granger_rows),
    })
    print(f"Output: {output}")
    return output


if __name__ == "__main__":
    main()
