"""Compare event relaxation models and extract exploratory matrix-pencil poles."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.analyze_pre_electrochemical_dynamics import case_fields, detrended, robust_scale
from scripts.mentor_method_common import (
    METHOD_OUTPUT,
    all_cases,
    generic_matched_contrasts,
    load_analysis_signals,
    load_health_table,
    write_frame,
    write_manifest,
)


ANALYSIS_SIGNALS = ("slow_pc1", "fast_residual_rms_pc1")


def information_criteria(sse: float, count: int, parameters: int) -> tuple[float, float]:
    corrected_sse = max(float(sse), 1e-30)
    aic = count * np.log(corrected_sse / count) + 2.0 * parameters
    correction = (
        2.0 * parameters * (parameters + 1) / (count - parameters - 1)
        if count > parameters + 1 else np.inf
    )
    return float(aic), float(aic + correction)


def linear_model_fit(y: np.ndarray, design: np.ndarray) -> tuple[float, np.ndarray]:
    coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
    residual = y - design @ coefficients
    return float(np.sum(residual ** 2)), coefficients


def matrix_pencil_poles(
    values: np.ndarray, sample_rate: float, maximum_order: int = 8,
) -> list[dict[str, float]]:
    y = np.asarray(values, dtype=np.float64)
    y = y - np.median(y[int(0.8 * len(y)):])
    columns = max(8, len(y) // 2)
    rows = len(y) - columns
    if rows < 8:
        return []
    first = np.column_stack([y[index:index + rows] for index in range(columns)])
    second = np.column_stack([y[index + 1:index + rows + 1] for index in range(columns)])
    left, singular, right = np.linalg.svd(first, full_matrices=False)
    if not len(singular) or singular[0] <= 0.0:
        return []
    estimated = int(np.sum(singular / singular[0] >= 0.03))
    rank = int(np.clip(estimated, 1, min(maximum_order, len(singular))))
    reduced = (
        left[:, :rank].T.conj() @ second @ right[:rank].T.conj()
        @ np.diag(1.0 / np.maximum(singular[:rank], 1e-15))
    )
    poles = np.linalg.eigvals(reduced)
    sample = np.arange(len(y), dtype=np.float64)
    vandermonde = np.column_stack([pole ** sample for pole in poles])
    amplitudes, *_ = np.linalg.lstsq(vandermonde, y.astype(np.complex128), rcond=None)
    result = []
    for pole, amplitude in zip(poles, amplitudes):
        magnitude = float(abs(pole))
        if not 0.0 < magnitude < 1.05:
            continue
        damping_rate = -sample_rate * np.log(magnitude)
        frequency = abs(float(np.angle(pole) * sample_rate / (2.0 * np.pi)))
        result.append({
            "frequency_hz": frequency,
            "tau_s": float(1.0 / damping_rate) if damping_rate > 0.0 else np.inf,
            "amplitude": float(abs(amplitude)),
            "pole_magnitude": magnitude,
            "model_rank": rank,
        })
    return sorted(result, key=lambda row: row["amplitude"], reverse=True)


def fit_event_shape_models(
    values: np.ndarray, start: int, sample_rate: float, duration_s: float = 12.0,
) -> dict[str, object]:
    end = min(len(values), start + int(round(duration_s * sample_rate)))
    y = np.asarray(values[start:end], dtype=np.float64)
    if len(y) < max(20, int(round(5.0 * sample_rate))):
        return {"shape_status": "too_short"}
    time = np.arange(len(y), dtype=np.float64) / sample_rate
    tau_grid = np.geomspace(max(0.2, 2.0 / sample_rate), 24.0, 36)

    candidates: list[dict[str, object]] = []
    best_single = None
    for tau in tau_grid:
        design = np.column_stack([np.exp(-time / tau), np.ones_like(time)])
        sse, coefficients = linear_model_fit(y, design)
        if best_single is None or sse < best_single[0]:
            best_single = (sse, tau, coefficients)
    assert best_single is not None
    single_aic, single_aicc = information_criteria(best_single[0], len(y), 3)
    candidates.append({
        "model": "single_exponential", "sse": best_single[0],
        "aic": single_aic, "aicc": single_aicc,
    })

    best_double = None
    reduced_grid = tau_grid[::2]
    for first_index, first_tau in enumerate(reduced_grid[:-1]):
        for second_tau in reduced_grid[first_index + 1:]:
            design = np.column_stack([
                np.exp(-time / first_tau), np.exp(-time / second_tau),
                np.ones_like(time),
            ])
            sse, coefficients = linear_model_fit(y, design)
            if best_double is None or sse < best_double[0]:
                best_double = (sse, first_tau, second_tau, coefficients)
    assert best_double is not None
    double_aic, double_aicc = information_criteria(best_double[0], len(y), 5)
    candidates.append({
        "model": "double_exponential", "sse": best_double[0],
        "aic": double_aic, "aicc": double_aicc,
    })

    poles = matrix_pencil_poles(y, sample_rate)
    physical_poles = [row for row in poles if (
        0.03 <= row["frequency_hz"] <= min(2.0, sample_rate / 2.0)
        and 0.2 <= row["tau_s"] <= 30.0
    )]
    best_damped = None
    for pole in physical_poles[:4]:
        envelope = np.exp(-time / pole["tau_s"])
        phase = 2.0 * np.pi * pole["frequency_hz"] * time
        design = np.column_stack([
            envelope * np.cos(phase), envelope * np.sin(phase), np.ones_like(time),
        ])
        sse, coefficients = linear_model_fit(y, design)
        if best_damped is None or sse < best_damped[0]:
            best_damped = (sse, pole, coefficients)
    if best_damped is not None:
        damped_aic, damped_aicc = information_criteria(best_damped[0], len(y), 5)
        candidates.append({
            "model": "damped_oscillation", "sse": best_damped[0],
            "aic": damped_aic, "aicc": damped_aicc,
        })

    preferred = min(candidates, key=lambda row: row["aicc"])
    ordered_aicc = sorted(float(row["aicc"]) for row in candidates)
    total = float(np.sum((y - np.mean(y)) ** 2))
    if preferred["model"] == "single_exponential":
        parameters_identifiable = bool(best_single[1] <= duration_s)
    elif preferred["model"] == "double_exponential":
        parameters_identifiable = bool(
            best_double[2] / max(best_double[1], 1e-15) >= 2.0
            and best_double[2] <= duration_s
        )
    else:
        assert best_damped is not None
        parameters_identifiable = bool(
            best_damped[1]["tau_s"] <= duration_s
            and best_damped[1]["frequency_hz"] * duration_s >= 2.0
        )
    result: dict[str, object] = {
        "shape_status": "ok",
        "preferred_shape_model": preferred["model"],
        "preferred_model_r2": float(1.0 - float(preferred["sse"]) / max(total, 1e-15)),
        "shape_parameters_identifiable": parameters_identifiable,
        "preferred_to_second_delta_aicc": (
            ordered_aicc[1] - ordered_aicc[0] if len(ordered_aicc) > 1 else np.nan
        ),
        "single_tau_s": float(best_single[1]),
        "single_aicc": single_aicc,
        "double_tau_fast_s": float(best_double[1]),
        "double_tau_slow_s": float(best_double[2]),
        "double_aicc": double_aicc,
        "matrix_pencil_rank": poles[0]["model_rank"] if poles else 0,
        "matrix_pencil_physical_pole_count": len(physical_poles),
    }
    if best_damped is not None:
        result.update({
            "damped_frequency_hz": float(best_damped[1]["frequency_hz"]),
            "damped_tau_s": float(best_damped[1]["tau_s"]),
            "damped_aicc": float(next(
                row["aicc"] for row in candidates
                if row["model"] == "damped_oscillation"
            )),
        })
    else:
        result.update({
            "damped_frequency_hz": np.nan,
            "damped_tau_s": np.nan,
            "damped_aicc": np.nan,
        })
    return result


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=METHOD_OUTPUT / "event_shape_models")
    parser.add_argument(
        "--event-details", type=Path,
        default=METHOD_OUTPUT / "wavelet_relaxation" / "changepoint_event_details.csv",
    )
    parser.add_argument("--max-cases", type=int, default=0)
    args = parser.parse_args(argv)
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    try:
        event_details = pd.read_csv(args.event_details)
    except pd.errors.EmptyDataError:
        event_details = pd.DataFrame(columns=["case_id", "signal_name"])
    if not {"case_id", "signal_name"}.issubset(event_details.columns):
        event_details = pd.DataFrame(columns=["case_id", "signal_name"])
    cases = all_cases()
    if args.max_cases > 0:
        cases = cases[:args.max_cases]
    health = load_health_table()
    rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    for case_index, case in enumerate(cases, start=1):
        loaded = load_analysis_signals(case, health)
        fields = case_fields(case)
        case_events = event_details[event_details["case_id"] == case.case_id]
        for signal_name in ANALYSIS_SIGNALS:
            values = detrended(loaded.signals[signal_name])
            values /= float(robust_scale(values).squeeze())
            signal_events = case_events[case_events["signal_name"] == signal_name]
            case_rows = []
            for event in signal_events.itertuples(index=False):
                result = fit_event_shape_models(
                    values, int(event.event_sample), loaded.sample_rate_hz
                )
                row = {
                    **fields,
                    "signal_name": signal_name,
                    "event_sample": int(event.event_sample),
                    "event_time_s": float(event.event_time_s),
                    "absolute_step_amplitude_robust_sigma": float(
                        event.absolute_step_amplitude_robust_sigma
                    ),
                    "channel_changepoint_support_fraction": float(
                        event.channel_changepoint_support_fraction
                    ),
                    **result,
                }
                rows.append(row)
                case_rows.append(row)
            credible = [row for row in case_rows if (
                row.get("shape_status") == "ok"
                and row["absolute_step_amplitude_robust_sigma"] >= 0.5
                and row["channel_changepoint_support_fraction"] >= 0.5
                and row.get("preferred_model_r2", -np.inf) >= 0.5
                and row.get("preferred_to_second_delta_aicc", -np.inf) >= 4.0
                and row.get("shape_parameters_identifiable", False)
            )]
            summary_rows.append({
                **fields,
                "signal_name": signal_name,
                "event_model_count": len(case_rows),
                "credible_shape_event_count": len(credible),
                "credible_shape_event_fraction": len(credible) / max(len(case_rows), 1),
                "credible_damped_event_count": sum(
                    row.get("preferred_shape_model") == "damped_oscillation"
                    for row in credible
                ),
                "credible_double_exponential_event_count": sum(
                    row.get("preferred_shape_model") == "double_exponential"
                    for row in credible
                ),
                "median_credible_delta_aicc": float(np.median([
                    row["preferred_to_second_delta_aicc"] for row in credible
                ])) if credible else np.nan,
            })
        print(f"[{case_index}/{len(cases)}] {case.case_id}", flush=True)
    details = write_frame(output / "event_shape_model_details.csv", rows)
    summary = write_frame(output / "event_shape_case_summary.csv", summary_rows)
    features = [
        "event_model_count", "credible_shape_event_count",
        "credible_shape_event_fraction", "credible_damped_event_count",
        "credible_double_exponential_event_count", "median_credible_delta_aicc",
    ]
    write_frame(
        output / "matched_event_shape_contrasts.csv",
        generic_matched_contrasts(cases, summary, features, ["signal_name"]),
    )
    write_manifest(output, "event_shape_models", {
        "case_count": len(cases),
        "event_detail_rows": len(details),
        "case_summary_rows": len(summary),
        "candidate_models": [
            "single_exponential", "double_exponential", "damped_oscillation"
        ],
        "matrix_pencil_role": "candidate pole generator; not standalone evidence",
    })
    print(f"Output: {output}")
    return output


if __name__ == "__main__":
    main()
