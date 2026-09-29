"""Mentor-aligned low-frequency and relaxation reanalysis of cathodic data."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import signal, stats

from scripts.analyze_mentor_wavelet_relaxation import (
    cwt_analysis,
    synchrosqueezed_summary,
    wavelet_coherence,
)
from scripts.analyze_projection_memd import analyze_configuration
from scripts.analyze_pulse_relaxation_raw import (
    best_relaxation_template,
    principal_response,
    single_tau_fit,
)
from scripts.channel_quality import assess_channel_quality
from scripts.exact_tdms_archive import load_exact_archive
from scripts.mentor_method_common import stable_seed


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIRST_ARCHIVE = PROJECT_ROOT / 'experiments/20260811/exact_archive'
SECOND_ARCHIVE = PROJECT_ROOT / 'experiments/20260811_2/exact_archive'
DEFAULT_OUTPUT = PROJECT_ROOT / 'analysis/cathodic_mentor_methods_v1/low_frequency'
FEATURES = (
    "slow_mean",
    "broadband_rms",
    "subkhz_rms",
    "fast_residual_rms",
    "difference_rms",
)
MEMD_SIGNALS = ("slow_mean", "fast_residual_rms")


@dataclass(frozen=True)
class CaseSpec:
    batch: str
    case: str
    archive: Path
    current_ma: float | None
    kind: str
    repeat: int
    cycles: int
    target_hz: float
    nominal_start_s: float | None
    nominal_period_s: float | None
    duty: float


def archive_for(root: Path, case: str) -> Path:
    matches = sorted(root.glob(f"{case}__*"))
    if len(matches) != 1:
        raise ValueError(f"Expected one archive for {case}, found {len(matches)}")
    return matches[0]


def build_specs() -> list[CaseSpec]:
    specs = [
        CaseSpec(
            "8.11", "005hz", archive_for(FIRST_ARCHIVE, "005hz"), 100.0,
            "closed_circuit", 1, 4, 0.05, None, 20.0, 0.5,
        )
    ]
    info = {
        "bkg": (None, "background", 1, 0),
        "bkg2": (None, "background", 2, 0),
        "opensvnear": (0.0, "open_control", 1, 8),
        "cp200near": (200.0, "closed_circuit", 1, 12),
        "cp500near": (500.0, "closed_circuit", 1, 12),
        "cp1000near": (1000.0, "closed_circuit", 1, 12),
        "cp1000near2": (1000.0, "closed_circuit", 2, 12),
        "cp3000near": (3000.0, "closed_circuit", 1, 12),
        "cp3000near2": (3000.0, "closed_circuit", 2, 12),
    }
    for case, (current, kind, repeat, cycles) in info.items():
        archive = archive_for(SECOND_ARCHIVE, case)
        loaded = load_exact_archive(archive)
        period = (
            (float(loaded["duration_s"]) - 60.0) / cycles if cycles else 10.0
        )
        specs.append(CaseSpec(
            "8.11.2", case, archive, current, kind, repeat, cycles, 0.1,
            30.0 if cycles else None, period if cycles else None, 0.5,
        ))
    return specs


def time_axis(loaded: dict[str, object]) -> np.ndarray:
    rate = float(loaded["envelope_fs"])
    count = len(loaded["features"]["slow_mean"])
    first = float(
        loaded["archive_metadata"]["lowpass_filter"][
            "analysis_rate_first_sample_time_s"
        ]
    )
    return first + np.arange(count) / rate


def healthy_indices(loaded: dict[str, object]) -> np.ndarray:
    rows = assess_channel_quality(loaded)
    healthy = [
        index for index, row in enumerate(rows)
        if not bool(row["automatic_suspect"])
    ]
    if len(healthy) < 4:
        healthy = [
            index for index, row in enumerate(rows)
            if not bool(row["automatic_bad"])
        ]
    return np.asarray(healthy, dtype=int)


def robust_scale(values: np.ndarray, axis: int = 0) -> np.ndarray:
    center = np.median(values, axis=axis, keepdims=True)
    scale = 1.4826 * np.median(np.abs(values - center), axis=axis)
    fallback = np.std(values, axis=axis)
    return np.where(scale > 1e-12, scale, np.maximum(fallback, 1e-12))


def common_response(values: np.ndarray) -> tuple[np.ndarray, float, np.ndarray]:
    x = signal.detrend(np.asarray(values, dtype=float), axis=0)
    x /= robust_scale(x, axis=0)[None, :]
    covariance = x.T @ x / max(len(x), 1)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    weights = eigenvectors[:, -1]
    if np.sum(weights) < 0.0:
        weights = -weights
    return (
        x @ weights,
        float(eigenvalues[-1] / max(np.sum(eigenvalues), 1e-15)),
        weights,
    )


def protocol_state(times: np.ndarray, spec: CaseSpec) -> np.ndarray:
    if not spec.cycles or spec.nominal_period_s is None:
        return np.zeros(len(times), dtype=float)
    start = protocol_start(spec, times[-1])
    relative = times - start
    active = (relative >= 0.0) & (
        relative < spec.cycles * spec.nominal_period_s
    )
    return (
        active
        & ((relative % spec.nominal_period_s) < spec.duty * spec.nominal_period_s)
    ).astype(float)


def protocol_start(spec: CaseSpec, duration_s: float) -> float:
    if spec.nominal_start_s is not None:
        return spec.nominal_start_s
    assert spec.nominal_period_s is not None
    return 0.5 * (duration_s - spec.cycles * spec.nominal_period_s)


def harmonic_fit(
    values: np.ndarray, times: np.ndarray, frequency: float,
) -> tuple[float, complex]:
    centered = 2.0 * (times - np.mean(times)) / max(np.ptp(times), 1e-9)
    base = np.column_stack((
        np.ones(len(times)), centered, centered**2, centered**3,
    ))
    residual = values - base @ np.linalg.lstsq(base, values, rcond=None)[0]
    design = np.column_stack((
        np.sin(2.0 * np.pi * frequency * times),
        np.cos(2.0 * np.pi * frequency * times),
    ))
    coefficients = np.linalg.lstsq(design, residual, rcond=None)[0]
    value = complex(coefficients[0], coefficients[1])
    return float(abs(value)), value


def nearby_frequency_p(
    values: np.ndarray, times: np.ndarray, target_hz: float,
) -> tuple[float, float, float]:
    observed, _ = harmonic_fit(values, times, target_hz)
    factors = np.r_[np.linspace(0.70, 0.96, 70), np.linspace(1.04, 1.30, 70)]
    null = np.asarray([
        harmonic_fit(values, times, target_hz * factor)[0] for factor in factors
    ])
    p_value = float((np.sum(null >= observed) + 1) / (len(null) + 1))
    return observed, p_value, float(np.percentile(null, 95))


def target_cwt_metrics(
    analysis: dict[str, object], target_hz: float, active: np.ndarray | None,
) -> dict[str, float]:
    frequency = np.asarray(analysis["frequencies_hz"])
    index = int(np.argmin(np.abs(frequency - target_hz)))
    ratio = np.asarray(analysis["power_to_red"])[index]
    valid = np.asarray(analysis["valid"])[index]
    use = valid if active is None else (valid & active)
    return {
        "target_cwt_frequency_hz": float(frequency[index]),
        "target_cwt_power_to_red_median": float(np.median(ratio[use])) if np.any(use) else np.nan,
        "target_cwt_significant_fraction": float(np.mean(ratio[use] > 1.0)) if np.any(use) else np.nan,
        "target_cwt_valid_count": int(np.sum(use)),
    }


def fold_cycles(
    values: np.ndarray, times: np.ndarray, spec: CaseSpec,
) -> tuple[np.ndarray, float]:
    if not spec.cycles or spec.nominal_period_s is None:
        raise ValueError("No repeated protocol")
    rate = 1.0 / np.median(np.diff(times))
    period_samples = int(round(spec.nominal_period_s * rate))
    start = int(round((protocol_start(spec, times[-1]) - times[0]) * rate))
    cycles = []
    for index in range(spec.cycles):
        first = start + index * period_samples
        last = first + period_samples
        if first >= 0 and last <= len(values):
            cycles.append(values[first:last])
    if len(cycles) < 3:
        raise ValueError(f"Only {len(cycles)} complete cycles")
    return np.asarray(cycles, dtype=float), rate


def folded_relaxation(
    values: np.ndarray, times: np.ndarray, spec: CaseSpec,
) -> dict[str, float | str]:
    cycles, rate = fold_cycles(values, times, spec)
    cycle_count, period_samples, channel_count = cycles.shape
    fold_mean = np.mean(cycles, axis=0)
    fold_sem = np.std(cycles, axis=0, ddof=1) / np.sqrt(cycle_count)
    response, _, weights, variance_fraction = principal_response(
        fold_mean, fold_sem, np.arange(channel_count)
    )
    centered_cycles = cycles - np.mean(cycles, axis=1, keepdims=True)
    scale = np.maximum(np.median(fold_sem, axis=0), 1e-9)
    profiles = np.einsum(
        "tpc,c->tp", centered_cycles / scale[None, None, :], weights,
        optimize=True,
    )
    correlations = [
        stats.pearsonr(first, second).statistic
        for first, second in combinations(profiles, 2)
        if np.std(first) > 0.0 and np.std(second) > 0.0
    ]
    template = np.zeros(period_samples, dtype=float)
    template[:int(round(spec.duty * period_samples))] = 1.0
    level_shift, level_corr = circular_correlation(response, template)
    derivative = np.diff(template, prepend=template[-1])
    edge_shift, edge_corr = circular_correlation(response, derivative)
    relaxation = best_relaxation_template(response, template, rate)
    choices = [
        ("level", level_shift, level_corr, np.nan),
        ("transition", edge_shift, edge_corr, np.nan),
        (
            "exponential_relaxation", int(relaxation["shift_samples"]),
            float(relaxation["correlation"]), float(relaxation["tau_s"]),
        ),
    ]
    alignment_type, alignment_shift, template_corr, template_tau = max(
        choices, key=lambda item: abs(item[2])
    )
    aligned_template = np.roll(template, alignment_shift)
    transitions = np.flatnonzero(aligned_template != np.roll(aligned_template, 1))
    tau_rows = []
    for profile in profiles:
        for transition in transitions:
            next_transition = transitions[(np.flatnonzero(transitions == transition)[0] + 1) % len(transitions)]
            length = int((next_transition - transition) % period_samples)
            if length < max(6, int(rate)):
                continue
            event = profile[(transition + np.arange(length)) % period_samples]
            tau_rows.append(single_tau_fit(event, rate))
    identifiable = [row for row in tau_rows if row["tau_identifiable"]]
    taus = np.asarray([row["single_tau_s"] for row in identifiable], dtype=float)
    strong = [
        row for row in tau_rows
        if row["tau_identifiable"]
        and row["single_r2"] >= 0.7
        and row["single_vs_linear_delta_aicc"] >= 10.0
    ]
    return {
        "cycle_count_used": cycle_count,
        "folded_pc1_variance_fraction": variance_fraction,
        "cycle_profile_correlation_median": float(np.median(correlations)),
        "template_alignment_type": alignment_type,
        "template_alignment_shift_samples": int(alignment_shift),
        "template_correlation": float(template_corr),
        "relaxation_template_tau_s": float(template_tau),
        "event_fit_count": len(tau_rows),
        "identifiable_tau_fraction": len(identifiable) / max(len(tau_rows), 1),
        "strong_exponential_fraction": len(strong) / max(len(tau_rows), 1),
        "tau_median_s": float(np.median(taus)) if len(taus) else np.nan,
        "tau_cv": float(np.std(taus) / max(np.mean(taus), 1e-15)) if len(taus) else np.nan,
    }


def circular_correlation(first: np.ndarray, second: np.ndarray) -> tuple[int, float]:
    x = first - np.mean(first)
    y = second - np.mean(second)
    raw = np.fft.irfft(np.fft.rfft(x) * np.conj(np.fft.rfft(y)), n=len(x))
    denominator = max(float(np.linalg.norm(x) * np.linalg.norm(y)), 1e-15)
    best = int(np.argmax(np.abs(raw)))
    return best, float(raw[best] / denominator)


def analyze_case(spec: CaseSpec) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    loaded = load_exact_archive(spec.archive)
    times = time_axis(loaded)
    healthy = healthy_indices(loaded)
    state = protocol_state(times, spec) if spec.cycles else None
    cycle_window = None
    if spec.cycles and spec.nominal_period_s is not None:
        start = protocol_start(spec, times[-1])
        cycle_window = (times >= start) & (
            times < start + spec.cycles * spec.nominal_period_s
        )
    feature_rows = []
    relaxation_rows = []
    for feature in FEATURES:
        values = np.asarray(loaded["features"][feature])[:, healthy]
        common, variance_fraction, _ = common_response(values)
        wavelet = cwt_analysis(common, float(loaded["envelope_fs"]))
        row: dict[str, object] = {
            "batch": spec.batch,
            "case": spec.case,
            "kind": spec.kind,
            "current_ma": spec.current_ma,
            "repeat": spec.repeat,
            "feature": feature,
            "duration_s": float(loaded["duration_s"]),
            "healthy_channel_count": len(healthy),
            "common_pc1_variance_fraction": variance_fraction,
            **wavelet["summary"],
            **target_cwt_metrics(wavelet, spec.target_hz, cycle_window),
            **synchrosqueezed_summary(common, float(loaded["envelope_fs"])),
        }
        amplitude, frequency_p, null_q95 = nearby_frequency_p(
            common, times, spec.target_hz
        )
        row.update({
            "target_common_amplitude_sigma": amplitude,
            "target_nearby_frequency_p": frequency_p,
            "target_nearby_frequency_null_q95": null_q95,
        })
        if spec.cycles and state is not None:
            state_wavelet = cwt_analysis(state, float(loaded["envelope_fs"]))
            row.update(wavelet_coherence(
                wavelet, state_wavelet, float(loaded["envelope_fs"]),
                null_shifts=99,
                seed=stable_seed("cathodic-wavelet", spec.batch, spec.case, feature),
            ))
            relaxation = folded_relaxation(values, times, spec)
            relaxation_rows.append({
                "batch": spec.batch,
                "case": spec.case,
                "kind": spec.kind,
                "current_ma": spec.current_ma,
                "repeat": spec.repeat,
                "feature": feature,
                "target_nearby_frequency_p": frequency_p,
                **relaxation,
            })
        feature_rows.append(row)

    memd_rows = []
    for feature in MEMD_SIGNALS:
        values = np.asarray(loaded["features"][feature])[:, healthy]
        for directions in (16, 24):
            modes, summary, _, _, diagnostics = analyze_configuration(
                values,
                float(loaded["envelope_fs"]),
                directions,
                stable_seed("cathodic-memd", spec.batch, spec.case, feature, directions),
            )
            nearest = min(
                modes,
                key=lambda item: abs(item["center_frequency_hz_median"] - spec.target_hz),
                default=None,
            )
            memd_rows.append({
                "batch": spec.batch,
                "case": spec.case,
                "kind": spec.kind,
                "current_ma": spec.current_ma,
                "repeat": spec.repeat,
                "feature": feature,
                "direction_count": directions,
                "target_hz": spec.target_hz,
                "target_nearest_mode_frequency_hz": (
                    nearest["center_frequency_hz_median"] if nearest else np.nan
                ),
                "target_nearest_mode_energy_fraction": (
                    nearest["energy_fraction"] if nearest else np.nan
                ),
                "valid_direction_min": min(
                    [item["valid_direction_count"] for item in diagnostics],
                    default=0,
                ),
                **summary,
            })
    return feature_rows, relaxation_rows, memd_rows


def bh_adjust(values: np.ndarray) -> np.ndarray:
    p = np.asarray(values, dtype=float)
    order = np.argsort(p)
    ranked = p[order]
    adjusted = np.minimum.accumulate(
        (ranked * len(ranked) / np.arange(1, len(ranked) + 1))[::-1]
    )[::-1]
    result = np.empty_like(adjusted)
    result[order] = np.minimum(adjusted, 1.0)
    return result


def add_fdr(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        finite = np.isfinite(result[column])
        result.loc[finite, f"{column}_fdr"] = bh_adjust(
            result.loc[finite, column].to_numpy(dtype=float)
        )
    return result


def plot_summary(features: pd.DataFrame, relaxation: pd.DataFrame, output: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.4))
    slow = features[(features["batch"] == "8.11.2") & (features["feature"] == "slow_mean")]
    colors = slow["kind"].map({
        "background": "#777777", "open_control": "#d49a3a",
        "closed_circuit": "#3976a8",
    })
    axes[0].scatter(
        slow["current_ma"].fillna(-100), slow["target_cwt_power_to_red_median"],
        c=colors, s=55,
    )
    axes[0].axhline(1.0, color="#555555", linestyle="--", linewidth=0.9)
    axes[0].set_xlabel("Set current (mA); background shown at -100")
    axes[0].set_ylabel("0.1 Hz CWT power / AR(1) threshold")
    axes[0].set_title("Target-period wavelet evidence")
    folded = relaxation[
        (relaxation["batch"] == "8.11.2")
        & (relaxation["feature"] == "slow_mean")
    ]
    axes[1].scatter(
        folded["current_ma"], folded["template_correlation"].abs(),
        c=folded["kind"].map({
            "open_control": "#d49a3a", "closed_circuit": "#3976a8",
        }), s=55,
    )
    axes[1].axhline(0.25, color="#555555", linestyle="--", linewidth=0.9)
    axes[1].set_xlabel("Set current (mA)")
    axes[1].set_ylabel("Absolute best template correlation")
    axes[1].set_title("Folded level/edge/exponential matching")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    specs = build_specs()
    if args.limit:
        specs = specs[:args.limit]
    feature_rows = []
    relaxation_rows = []
    memd_rows = []
    for index, spec in enumerate(specs, start=1):
        print(f"[{index:02d}/{len(specs):02d}] {spec.batch}/{spec.case}", flush=True)
        feature, relaxation, memd = analyze_case(spec)
        feature_rows.extend(feature)
        relaxation_rows.extend(relaxation)
        memd_rows.extend(memd)
    features = add_fdr(pd.DataFrame(feature_rows), [
        "target_nearby_frequency_p", "circular_shift_null_p",
    ])
    relaxation = add_fdr(pd.DataFrame(relaxation_rows), [
        "target_nearby_frequency_p",
    ])
    memd = pd.DataFrame(memd_rows)
    features.to_csv(args.output / "cathodic_cwt_sst_features.csv", index=False)
    relaxation.to_csv(args.output / "cathodic_folded_relaxation.csv", index=False)
    memd.to_csv(args.output / "cathodic_projection_memd.csv", index=False)
    plot_summary(features, relaxation, args.output / "cathodic_lowfreq_summary.png")
    manifest = {
        "analysis": "cathodic_mentor_low_frequency",
        "case_count": len(specs),
        "feature_count": len(features),
        "relaxation_count": len(relaxation),
        "memd_configuration_count": len(memd),
        "limitations": [
            "manual switching has no synchronized current trace",
            "8.11 005hz retains four complete nominal cycles",
            "old electrode spacing was approximately 1 cm",
        ],
    }
    (args.output / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Output: {args.output}", flush=True)


if __name__ == "__main__":
    main()
