"""Recover pulse-locked waveforms and relaxation evidence from 44.6.9 CSV data."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from itertools import combinations
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import fft as sp_fft
from scipy import signal, stats

from scripts.analyze_legacy_pulse_outputs import PULSE_TOKEN, parse_group_name
from scripts.analyze_mentor_event_shape_models import information_criteria, matrix_pencil_poles


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = Path(r"E:\Lab\process\44.6.9")
DEFAULT_OUTPUT = PROJECT_ROOT / 'analysis/mentor_aligned_raw_completion_v3/pulse_relaxation'
CHANNEL_COLUMNS = [f"channel{index}" for index in range(1, 13)]


def stable_seed(*parts: object) -> int:
    digest = hashlib.sha256("|".join(map(str, parts)).encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "little")


def normalized_group_name(root: Path, directory: Path) -> str:
    parts = directory.relative_to(root).parts
    if parts[:2] == ("time", "non_vac"):
        return "/".join(("non_vac", *parts[2:]))
    if parts[:2] == ("vac", "time"):
        return "/".join(("vac", *parts[2:]))
    return "/".join(parts)


def discover_groups(root: Path) -> dict[str, list[Path]]:
    groups: dict[str, list[Path]] = {}
    for path in sorted(root.rglob("*.csv")):
        name = normalized_group_name(root, path.parent)
        groups.setdefault(name, []).append(path)
    return groups


def pulse_tokens(group_name: str) -> list[tuple[float, float]]:
    parsed = parse_group_name(group_name)
    sequence = str(parsed["pulse_sequence"])
    return [
        (float(match.group("voltage")), float(match.group("duration")))
        for match in PULSE_TOKEN.finditer(sequence)
    ]


def metadata_path(csv_path: Path) -> Path:
    return csv_path.with_name(csv_path.stem + "_metadata.json")


def read_downsampled_group(
    paths: list[Path], downsample: int,
) -> tuple[np.ndarray, float, list[np.ndarray], list[dict[str, object]]]:
    segments = []
    metadata_rows = []
    sample_rate = None
    for path in sorted(paths):
        metadata = json.loads(metadata_path(path).read_text(encoding="utf-8"))
        frame = pd.read_csv(path, usecols=CHANNEL_COLUMNS, dtype=np.float32)
        raw = frame.to_numpy(dtype=np.float32, copy=False)
        usable = len(raw) // downsample * downsample
        reduced = raw[:usable].reshape(-1, downsample, len(CHANNEL_COLUMNS)).mean(axis=1)
        segment_start = int(metadata["segment_start_sample"]) // downsample
        metadata["downsampled_start"] = segment_start
        metadata["downsampled_count"] = len(reduced)
        segments.append((segment_start, np.asarray(reduced, dtype=np.float32)))
        metadata_rows.append(metadata)
        current_rate = float(metadata["sampling_rate_hz"]) / downsample
        if sample_rate is None:
            sample_rate = current_rate
        elif not np.isclose(sample_rate, current_rate, rtol=1e-8):
            raise ValueError(f"Sampling-rate mismatch in {path.parent}")
    segments.sort(key=lambda item: item[0])
    expected = segments[0][0]
    ordered = []
    for start, values in segments:
        if start != expected:
            raise RuntimeError(f"Non-contiguous pulse segments: expected {expected}, got {start}")
        ordered.append(values)
        expected += len(values)
    return np.vstack(ordered), float(sample_rate), ordered, metadata_rows


def robust_z(values: np.ndarray) -> np.ndarray:
    center = np.median(values)
    scale = 1.4826 * np.median(np.abs(values - center))
    if not np.isfinite(scale) or scale <= 1e-12:
        scale = np.std(values)
    return (values - center) / max(scale, 1e-12)


def dynamic_healthy_channels(values: np.ndarray) -> tuple[np.ndarray, list[dict[str, object]]]:
    standard_deviation = np.std(values, axis=0)
    difference_rms = np.sqrt(np.mean(np.diff(values, axis=0) ** 2, axis=0) / 2.0)
    ranges = np.ptp(values, axis=0)
    metrics = {
        "std": standard_deviation,
        "difference_rms": difference_rms,
        "range": ranges,
    }
    scores = {
        name: robust_z(np.log10(np.maximum(metric, 1e-30)))
        for name, metric in metrics.items()
    }
    rows = []
    healthy = []
    for index in range(values.shape[1]):
        votes = sum(abs(scores[name][index]) > 6.0 for name in scores)
        extreme = any(abs(scores[name][index]) > 10.0 for name in scores)
        hard = bool(
            standard_deviation[index] < 1e-10
            or np.mean(np.abs(values[:, index]) >= 9.9) > 0.001
            or np.mean(np.abs(np.diff(values[:, index])) <= 1e-12) > 0.95
        )
        bad = bool(hard or votes >= 2 or extreme)
        if not bad:
            healthy.append(index)
        rows.append({
            "channel_index": index + 1,
            "std_v": float(standard_deviation[index]),
            "difference_rms_v": float(difference_rms[index]),
            "range_v": float(ranges[index]),
            "automatic_bad": bad,
            "bad_vote_count": int(votes),
        })
    if len(healthy) < 4:
        order = np.argsort(np.abs(scores["std"]))
        healthy = sorted(order[:max(4, min(8, len(order)))].tolist())
    return np.asarray(healthy, dtype=int), rows


def fold_profile(values: np.ndarray, period_samples: int) -> tuple[np.ndarray, np.ndarray, int]:
    cycle_count = len(values) // period_samples
    if cycle_count < 3:
        raise ValueError("Fewer than three complete pulse cycles")
    cycles = values[:cycle_count * period_samples].reshape(
        cycle_count, period_samples, values.shape[1]
    )
    mean = np.mean(cycles, axis=0)
    sem = np.std(cycles, axis=0, ddof=1) / np.sqrt(cycle_count)
    return mean, sem, cycle_count


def principal_response(
    fold_mean: np.ndarray, fold_sem: np.ndarray, healthy: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    noise = np.median(fold_sem[:, healthy], axis=0)
    scaled = (fold_mean[:, healthy] - np.mean(fold_mean[:, healthy], axis=0))
    scaled /= np.maximum(noise[None, :], 1e-9)
    covariance = scaled.T @ scaled / max(len(scaled), 1)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    weights = eigenvectors[:, -1]
    response = scaled @ weights
    response_sem = np.sqrt(np.sum(
        (fold_sem[:, healthy] / np.maximum(noise[None, :], 1e-9)) ** 2
        * weights[None, :] ** 2,
        axis=1,
    ))
    return response, response_sem, weights, float(
        eigenvalues[-1] / max(np.sum(eigenvalues), 1e-15)
    )


def circular_correlation(first: np.ndarray, second: np.ndarray) -> tuple[int, float]:
    x = first - np.mean(first)
    y = second - np.mean(second)
    raw = sp_fft.irfft(sp_fft.rfft(x) * np.conj(sp_fft.rfft(y)), n=len(x))
    denominator = max(float(np.linalg.norm(x) * np.linalg.norm(y)), 1e-15)
    best = int(np.argmax(np.abs(raw)))
    return best, float(raw[best] / denominator)


def best_relaxation_template(
    response: np.ndarray, voltage_template: np.ndarray, sample_rate: float,
    tau_count: int = 32,
) -> dict[str, object]:
    """Match a periodic voltage-transition train after a causal exponential kernel."""
    derivative = np.diff(voltage_template, prepend=voltage_template[-1])
    minimum_tau = max(2.0 / sample_rate, 1e-6)
    maximum_tau = max(minimum_tau * 1.01, 0.5 * len(voltage_template) / sample_rate)
    tau_grid = np.geomspace(minimum_tau, maximum_tau, tau_count)
    best = None
    time = np.arange(len(voltage_template)) / sample_rate
    derivative_spectrum = sp_fft.rfft(derivative)
    for tau in tau_grid:
        kernel = np.exp(-time / tau)
        candidate = sp_fft.irfft(
            derivative_spectrum * sp_fft.rfft(kernel), n=len(voltage_template)
        )
        shift, correlation = circular_correlation(response, candidate)
        if best is None or abs(correlation) > abs(best[2]):
            best = (shift, tau, correlation, candidate)
    assert best is not None
    return {
        "shift_samples": int(best[0]),
        "tau_s": float(best[1]),
        "correlation": float(best[2]),
        "template": np.asarray(best[3], dtype=float),
    }


def harmonic_comb_score_from_spectrum(
    frequency: np.ndarray, power: np.ndarray, fundamental_hz: float,
) -> float:
    sample_rate = 2.0 * frequency[-1]
    resolution = frequency[1] - frequency[0]
    contrasts = []
    for harmonic in np.arange(fundamental_hz, min(2_000.0, sample_rate / 2.0 - 5.0), fundamental_hz):
        nearest_mains = 50.0 * round(harmonic / 50.0)
        if nearest_mains >= 50.0 and abs(harmonic - nearest_mains) <= max(0.75, 3.0 * resolution):
            continue
        center = int(round(harmonic / resolution))
        if center < 12 or center + 12 >= len(power):
            continue
        line = np.max(power[center - 1:center + 2])
        floor = np.median(np.r_[power[center - 12:center - 3], power[center + 4:center + 13]])
        contrasts.append(10.0 * np.log10(max(line, 1e-300) / max(floor, 1e-300)))
    return float(np.median(contrasts)) if contrasts else np.nan


def single_tau_fit(values: np.ndarray, sample_rate: float) -> dict[str, float]:
    y = np.asarray(values, dtype=float)
    if len(y) > 600:
        factor = int(np.ceil(len(y) / 600))
        usable = len(y) // factor * factor
        y = y[:usable].reshape(-1, factor).mean(axis=1)
        sample_rate /= factor
    time = np.arange(len(y)) / sample_rate
    duration = time[-1] if len(time) else 0.0
    baseline_design = np.column_stack([np.ones_like(time), time])
    baseline_coefficients, *_ = np.linalg.lstsq(baseline_design, y, rcond=None)
    baseline_sse = float(np.sum((y - baseline_design @ baseline_coefficients) ** 2))
    _, baseline_aicc = information_criteria(baseline_sse, len(y), 2)
    tau_grid = np.geomspace(max(2.0 / sample_rate, 1e-6), max(duration * 2.0, 4.0 / sample_rate), 52)
    best = None
    for tau in tau_grid:
        design = np.column_stack([np.exp(-time / tau), np.ones_like(time), time])
        coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
        residual = y - design @ coefficients
        sse = float(np.sum(residual ** 2))
        if best is None or sse < best[0]:
            best = (sse, tau, coefficients)
    assert best is not None
    _, aicc = information_criteria(best[0], len(y), 4)
    total = float(np.sum((y - np.mean(y)) ** 2))
    return {
        "single_tau_s": float(best[1]),
        "single_r2": float(1.0 - best[0] / max(total, 1e-15)),
        "single_aicc": float(aicc),
        "linear_aicc": float(baseline_aicc),
        "single_vs_linear_delta_aicc": float(baseline_aicc - aicc),
        "tau_identifiable": bool(5.0 / sample_rate <= best[1] <= 0.8 * max(duration, 1e-15)),
    }


def double_tau_fit(values: np.ndarray, sample_rate: float) -> dict[str, float]:
    y = np.asarray(values, dtype=float)
    if len(y) > 400:
        factor = int(np.ceil(len(y) / 400))
        usable = len(y) // factor * factor
        y = y[:usable].reshape(-1, factor).mean(axis=1)
        sample_rate /= factor
    time = np.arange(len(y)) / sample_rate
    duration = time[-1]
    tau_grid = np.geomspace(max(2.0 / sample_rate, 1e-6), max(duration * 2.0, 4.0 / sample_rate), 20)
    best = None
    for first_index, first_tau in enumerate(tau_grid[:-1]):
        for second_tau in tau_grid[first_index + 1:]:
            design = np.column_stack([
                np.exp(-time / first_tau), np.exp(-time / second_tau),
                np.ones_like(time), time,
            ])
            coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
            residual = y - design @ coefficients
            sse = float(np.sum(residual ** 2))
            if best is None or sse < best[0]:
                best = (sse, first_tau, second_tau)
    assert best is not None
    _, aicc = information_criteria(best[0], len(y), 6)
    total = float(np.sum((y - np.mean(y)) ** 2))
    return {
        "double_tau_fast_s": float(best[1]),
        "double_tau_slow_s": float(best[2]),
        "double_r2": float(1.0 - best[0] / max(total, 1e-15)),
        "double_aicc": float(aicc),
        "double_tau_separation": float(best[2] / max(best[1], 1e-15)),
        "double_identifiable": bool(
            best[2] / max(best[1], 1e-15) >= 2.0 and best[2] <= 0.8 * duration
        ),
    }


def circular_slice(values: np.ndarray, start: int, length: int) -> np.ndarray:
    return values[(start + np.arange(length)) % len(values)]


def analyze_group(
    group_name: str, paths: list[Path], downsample: int,
) -> dict[str, object]:
    parsed = parse_group_name(group_name)
    tokens = pulse_tokens(group_name)
    if not tokens:
        raise ValueError(f"No pulse sequence parsed from {group_name}")
    values, sample_rate, segments, metadata_rows = read_downsampled_group(paths, downsample)
    healthy, health_rows = dynamic_healthy_channels(values)
    period_samples = int(round(sum(duration for _, duration in tokens) * 1e-3 * sample_rate))
    fold_mean, fold_sem, cycle_count = fold_profile(values, period_samples)
    response, response_sem, weights, variance_fraction = principal_response(
        fold_mean, fold_sem, healthy
    )

    template_parts = [
        np.full(int(round(duration * 1e-3 * sample_rate)), voltage, dtype=float)
        for voltage, duration in tokens
    ]
    template = np.concatenate(template_parts)
    if len(template) != period_samples:
        template = signal.resample(template, period_samples)
    derivative = np.diff(template, prepend=template[-1])
    level_shift, level_correlation = circular_correlation(response, template)
    derivative_shift, derivative_correlation = circular_correlation(response, derivative)
    relaxation = best_relaxation_template(response, template, sample_rate)
    alignments = [
        ("level", level_shift, level_correlation, np.nan),
        ("transition", derivative_shift, derivative_correlation, np.nan),
        (
            "exponential_relaxation", int(relaxation["shift_samples"]),
            float(relaxation["correlation"]), float(relaxation["tau_s"]),
        ),
    ]
    alignment_type, alignment_shift, template_correlation, alignment_tau = max(
        alignments, key=lambda item: abs(item[2])
    )
    aligned_template = np.roll(template, alignment_shift)

    standardized = signal.detrend(values[:, healthy], axis=0)
    scales = np.std(standardized, axis=0)
    standardized /= np.maximum(scales[None, :], 1e-12)
    continuous_pc = standardized @ weights
    fundamental = sample_rate / period_samples
    comb_frequency, comb_power = signal.periodogram(
        signal.detrend(continuous_pc), fs=sample_rate,
        window="hann", scaling="density",
    )
    observed_comb = harmonic_comb_score_from_spectrum(
        comb_frequency, comb_power, fundamental
    )
    rng = np.random.default_rng(stable_seed(group_name, "comb"))
    null_scores = []
    for factor in rng.uniform(0.94, 1.06, 99):
        if abs(factor - 1.0) < 0.005:
            factor += 0.008
        null_scores.append(harmonic_comb_score_from_spectrum(
            comb_frequency, comb_power, fundamental * factor
        ))
    null = np.asarray(null_scores, dtype=float)
    comb_p = float((np.sum(null >= observed_comb) + 1) / (len(null) + 1))

    segment_profiles = []
    for segment_values in segments:
        segment_mean, _, _ = fold_profile(segment_values, period_samples)
        centered = segment_mean[:, healthy] - np.mean(segment_mean[:, healthy], axis=0)
        centered /= np.maximum(np.median(fold_sem[:, healthy], axis=0)[None, :], 1e-9)
        segment_profiles.append(centered @ weights)
    segment_correlations = [
        stats.pearsonr(first, second).statistic
        for first, second in combinations(segment_profiles, 2)
        if np.std(first) > 0.0 and np.std(second) > 0.0
    ]
    segment_correlation_median = float(np.median(segment_correlations)) if segment_correlations else np.nan

    transitions = np.flatnonzero(aligned_template != np.roll(aligned_template, 1))
    transition_rows = []
    for transition_index, start in enumerate(transitions):
        next_start = int(transitions[(transition_index + 1) % len(transitions)])
        length = (next_start - int(start)) % period_samples
        if length < 12:
            continue
        event = circular_slice(response, int(start), length)
        event_sem = circular_slice(response_sem, int(start), length)
        single = single_tau_fit(event, sample_rate)
        double = double_tau_fit(event, sample_rate)
        fit_values = event
        fit_rate = sample_rate
        if len(fit_values) > 240:
            factor = int(np.ceil(len(fit_values) / 240))
            usable = len(fit_values) // factor * factor
            fit_values = fit_values[:usable].reshape(-1, factor).mean(axis=1)
            fit_rate /= factor
        poles = matrix_pencil_poles(fit_values, fit_rate, maximum_order=6)
        physical_poles = [
            pole for pole in poles
            if 2.0 / fit_rate <= pole["tau_s"] <= length / sample_rate
            and pole["frequency_hz"] <= fit_rate / 2.0
        ]
        segment_taus = []
        for profile in segment_profiles:
            segment_event = circular_slice(profile, int(start), length)
            segment_taus.append(single_tau_fit(segment_event, sample_rate)["single_tau_s"])
        tau_cv = float(np.std(segment_taus) / max(np.mean(segment_taus), 1e-15))
        amplitude = float(np.ptp(event))
        event_snr = amplitude / max(float(np.median(event_sem)), 1e-15)
        credible = bool(
            comb_p <= 0.05
            and segment_correlation_median >= 0.5
            and abs(template_correlation) >= 0.25
            and event_snr >= 5.0
            and single["single_vs_linear_delta_aicc"] >= 10.0
            and single["single_r2"] >= 0.7
            and single["tau_identifiable"]
            and tau_cv <= 0.5
        )
        previous_value = float(aligned_template[(int(start) - 1) % period_samples])
        next_value = float(aligned_template[int(start)])
        transition_rows.append({
            "transition_index": transition_index,
            "transition_sample": int(start),
            "from_voltage_v": previous_value,
            "to_voltage_v": next_value,
            "next_state_duration_s": length / sample_rate,
            "event_peak_to_peak": amplitude,
            "event_snr_vs_fold_sem": event_snr,
            "segment_single_tau_cv": tau_cv,
            "segment_single_tau_median_s": float(np.median(segment_taus)),
            "matrix_pencil_physical_pole_count": len(physical_poles),
            "matrix_pencil_dominant_tau_s": (
                float(physical_poles[0]["tau_s"]) if physical_poles else np.nan
            ),
            "matrix_pencil_dominant_frequency_hz": (
                float(physical_poles[0]["frequency_hz"]) if physical_poles else np.nan
            ),
            **single,
            **double,
            "credible_relaxation": credible,
        })

    fold_rms = float(np.sqrt(np.mean((response - np.mean(response)) ** 2)))
    fold_snr = fold_rms / max(float(np.median(response_sem)), 1e-15)
    return {
        "analysis_version": 3,
        "group_name": group_name,
        **parsed,
        "pulse_tokens": tokens,
        "input_files": [str(path) for path in paths],
        "source_filenames": [str(row["filename"]) for row in metadata_rows],
        "downsampled_rate_hz": sample_rate,
        "period_s": period_samples / sample_rate,
        "fundamental_hz": fundamental,
        "cycle_count": cycle_count,
        "healthy_channel_indices_1based": (healthy + 1).tolist(),
        "healthy_channel_count": len(healthy),
        "channel_health": health_rows,
        "pulse_locked_pc1_variance_fraction": variance_fraction,
        "pulse_locked_rms": fold_rms,
        "pulse_locked_snr_vs_fold_sem": fold_snr,
        "template_alignment_type": alignment_type,
        "template_alignment_shift_samples": alignment_shift,
        "template_correlation": template_correlation,
        "relaxation_template_tau_s": alignment_tau,
        "exact_period_harmonic_comb_score_db": observed_comb,
        "nearby_period_surrogate_p": comb_p,
        "nearby_period_null_q95_db": float(np.nanpercentile(null, 95)),
        "segment_profile_correlation_median": segment_correlation_median,
        "credible_relaxation_count": int(sum(
            row["credible_relaxation"] for row in transition_rows
        )),
        "transition_count": len(transition_rows),
        "transitions": transition_rows,
    }


def flatten_results(payloads: list[dict[str, object]]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_rows = []
    transition_rows = []
    health_rows = []
    for payload in payloads:
        summary = {
            key: value for key, value in payload.items()
            if key not in {"transitions", "channel_health", "pulse_tokens", "input_files", "source_filenames"}
        }
        summary_rows.append(summary)
        for row in payload["transitions"]:
            transition_rows.append({"group_name": payload["group_name"], **row})
        for row in payload["channel_health"]:
            health_rows.append({"group_name": payload["group_name"], **row})
    return pd.DataFrame(summary_rows), pd.DataFrame(transition_rows), pd.DataFrame(health_rows)


def calibration_table(summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    first = summary[summary["is_first_order"].astype(bool)].copy()
    metrics = [
        "pulse_locked_rms", "pulse_locked_snr_vs_fold_sem",
        "exact_period_harmonic_comb_score_db", "template_correlation",
    ]
    for keys, group in first.groupby(["source_mode", "setup"]):
        if group["pulse_max_v"].nunique() < 4:
            continue
        for metric in metrics:
            values = group[["pulse_max_v", metric]].dropna()
            if values["pulse_max_v"].nunique() < 4:
                continue
            rho, p_value = stats.spearmanr(values["pulse_max_v"], values[metric])
            rows.append({
                "source_mode": keys[0], "setup": keys[1], "metric": metric,
                "group_count": len(values), "voltage_level_count": values["pulse_max_v"].nunique(),
                "spearman_rho": float(rho), "spearman_p": float(p_value),
            })
    return pd.DataFrame(rows)


def plot_results(summary: pd.DataFrame, transitions: pd.DataFrame, output: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    for mode, color in (("non_vac", "#3976a8"), ("vac", "#bf5b45")):
        selected = summary[summary["source_mode"] == mode]
        axes[0].scatter(
            selected["pulse_max_v"], selected["exact_period_harmonic_comb_score_db"],
            s=28, alpha=0.65, label=mode, color=color,
        )
    axes[0].axhline(0.0, color="#555555", linewidth=0.8)
    axes[0].set_xlabel("Maximum programmed pulse voltage (V)")
    axes[0].set_ylabel("Exact-period harmonic-comb score (dB)")
    axes[0].legend()
    axes[0].set_title("Pulse-period locking across all 188 conditions")
    accepted = transitions[transitions["credible_relaxation"].astype(bool)]
    axes[1].hist(
        transitions["single_vs_linear_delta_aicc"].clip(-50, 100), bins=45,
        color="#789d4a", alpha=0.75,
    )
    axes[1].axvline(10.0, color="#555555", linestyle="--", linewidth=0.9)
    axes[1].set_xlabel("Single exponential improvement over linear model (delta AICc)")
    axes[1].set_ylabel("Transition count")
    axes[1].set_title(f"Strict credible relaxations: {len(accepted)}/{len(transitions)}")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--downsample", type=int, default=20)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    cache = args.output / "groups"
    cache.mkdir(parents=True, exist_ok=True)
    groups = discover_groups(args.input)
    items = sorted(groups.items())
    if args.limit:
        items = items[:args.limit]
    for index, (name, paths) in enumerate(items, start=1):
        key = hashlib.sha256(name.encode("utf-8")).hexdigest()[:20]
        path = cache / f"{key}.json"
        if path.exists() and not args.force:
            cached = json.loads(path.read_text(encoding="utf-8"))
            if int(cached.get("analysis_version", 0)) == 3:
                print(f"[{index:03d}/{len(items):03d}] cached {name}", flush=True)
                continue
        print(f"[{index:03d}/{len(items):03d}] {name}", flush=True)
        payload = analyze_group(name, paths, args.downsample)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    expected = {hashlib.sha256(name.encode("utf-8")).hexdigest()[:20] for name, _ in items}
    payloads = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(cache.glob("*.json")) if path.stem in expected
    ]
    summary, transitions, health = flatten_results(payloads)
    summary.to_csv(args.output / "pulse_group_summary.csv", index=False)
    transitions.to_csv(args.output / "pulse_transition_models.csv", index=False)
    health.to_csv(args.output / "pulse_dynamic_channel_health.csv", index=False)
    calibration = calibration_table(summary)
    calibration.to_csv(args.output / "pulse_voltage_dependence.csv", index=False)
    plot_results(summary, transitions, args.output / "pulse_relaxation_summary.png")
    manifest = {
        "analysis": "raw_pulse_relaxation_completion",
        "analysis_version": 3,
        "input": str(args.input),
        "group_count": len(summary),
        "transition_count": len(transitions),
        "credible_relaxation_count": int(transitions["credible_relaxation"].sum()),
        "original_sample_rate_hz": 400_000.0,
        "analysis_sample_rate_hz": float(summary["downsampled_rate_hz"].median()),
        "anti_alias_note": "20-sample boxcar aggregation; relaxation below 0.1 ms remains unresolved",
        "template_note": "level, transition and 32-tau periodic exponential-relaxation templates audited",
    }
    (args.output / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Output: {args.output}", flush=True)


if __name__ == "__main__":
    main()
