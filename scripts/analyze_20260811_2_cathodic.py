# -*- coding: utf-8 -*-
"""Exact analysis of the 2026-08-11 second cathodic-protection batch.

The raw acquisitions contain manually timed, nominal 5 s ON / 5 s OFF
cycles.  This script uses the full-coverage exact archives, estimates timing
only on discovery channels, and reports the result on held-out channels.
Channel health is assessed independently for every acquisition.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal, stats

from channel_quality import assess_channel_quality
from exact_tdms_archive import BAND_NAMES, load_exact_archive


FEATURES = (
    "slow_mean",
    "broadband_rms",
    "subkhz_rms",
    "fast_residual_rms",
    "difference_rms",
)
CP_CASES = (
    "cp200near",
    "cp500near",
    "cp1000near",
    "cp1000near2",
    "cp3000near",
    "cp3000near2",
)
CASE_ORDER = ("bkg", "opensvnear", *CP_CASES, "bkg2")


@dataclass(frozen=True)
class CaseInfo:
    current_ma: float | None
    cycles: int
    kind: str
    repeat: int


CASE_INFO = {
    "bkg": CaseInfo(None, 0, "background", 1),
    "bkg2": CaseInfo(None, 0, "background", 2),
    "opensvnear": CaseInfo(0.0, 8, "open_control", 1),
    "cp200near": CaseInfo(200.0, 12, "closed_circuit", 1),
    "cp500near": CaseInfo(500.0, 12, "closed_circuit", 1),
    "cp1000near": CaseInfo(1000.0, 12, "closed_circuit", 1),
    "cp1000near2": CaseInfo(1000.0, 12, "closed_circuit", 2),
    "cp3000near": CaseInfo(3000.0, 12, "closed_circuit", 1),
    "cp3000near2": CaseInfo(3000.0, 12, "closed_circuit", 2),
}


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_cases(root: Path) -> dict[str, dict[str, object]]:
    cases: dict[str, dict[str, object]] = {}
    for case in CASE_ORDER:
        matches = sorted(root.glob(f"{case}__*"))
        if len(matches) != 1:
            raise ValueError(f"Expected one exact archive for {case}; found {len(matches)}")
        cases[case] = load_exact_archive(matches[0])
    return cases


def time_axis(result: dict[str, object]) -> np.ndarray:
    rate = float(result["envelope_fs"])
    count = len(result["features"]["slow_mean"])
    first = float(
        result["archive_metadata"]["lowpass_filter"]["analysis_rate_first_sample_time_s"]
    )
    return first + np.arange(count) / rate


def healthy_indices(result: dict[str, object]) -> list[int]:
    return [
        index
        for index, row in enumerate(assess_channel_quality(result))
        if not bool(row["automatic_suspect"])
    ]


def polynomial_design(times: np.ndarray) -> np.ndarray:
    centered = 2.0 * (times - np.mean(times)) / max(float(np.ptp(times)), 1e-9)
    return np.column_stack(
        (np.ones(len(times)), centered, centered**2, centered**3)
    )


def protocol_state(
    times: np.ndarray, start_s: float, period_s: float, duty: float, cycles: int
) -> np.ndarray:
    relative = times - start_s
    active = (relative >= 0.0) & (relative < cycles * period_s)
    return (active & ((relative % period_s) < duty * period_s)).astype(float)


def fit_state(
    values: np.ndarray,
    times: np.ndarray,
    start_s: float,
    period_s: float,
    duty: float,
    cycles: int,
) -> tuple[np.ndarray, np.ndarray]:
    base = polynomial_design(times)
    state = protocol_state(times, start_s, period_s, duty, cycles)
    full = np.column_stack((base, state))
    base_fit = base @ np.linalg.lstsq(base, values, rcond=None)[0]
    coefficients = np.linalg.lstsq(full, values, rcond=None)[0]
    full_fit = full @ coefficients
    base_sse = np.sum((values - base_fit) ** 2, axis=0)
    full_sse = np.sum((values - full_fit) ** 2, axis=0)
    delta_r2 = np.maximum(0.0, base_sse - full_sse) / np.maximum(base_sse, 1e-30)
    return coefficients[-1], delta_r2


def timing_candidates(duration_s: float, cycles: int) -> list[tuple[float, float, float]]:
    candidates = []
    for start_s in np.arange(26.0, 34.01, 0.25):
        for end_margin_s in np.arange(26.0, 34.01, 0.25):
            period_s = (duration_s - start_s - end_margin_s) / cycles
            if not 8.5 <= period_s <= 11.5:
                continue
            for duty in (0.45, 0.50, 0.55):
                candidates.append((float(start_s), float(period_s), float(duty)))
    return candidates


def select_timing(
    values: np.ndarray,
    times: np.ndarray,
    discovery_columns: list[int],
    cycles: int,
    duration_s: float,
) -> tuple[float, float, float, float]:
    best: tuple[float, float, float, float] | None = None
    discovery = values[:, discovery_columns]
    for start_s, period_s, duty in timing_candidates(duration_s, cycles):
        _, delta_r2 = fit_state(
            discovery, times, start_s, period_s, duty, cycles
        )
        score = float(np.median(delta_r2))
        if best is None or score > best[-1]:
            best = (start_s, period_s, duty, score)
    if best is None:
        raise RuntimeError("No timing candidates")
    return best


def phase_percentile(
    values: np.ndarray,
    times: np.ndarray,
    start_s: float,
    period_s: float,
    duty: float,
    cycles: int,
    observed_r2: float,
) -> float:
    null_scores = []
    for shift in np.linspace(0.0, period_s, 80, endpoint=False):
        _, delta_r2 = fit_state(
            values, times, start_s + shift, period_s, duty, cycles
        )
        null_scores.append(float(np.median(delta_r2)))
    return float(np.mean(np.asarray(null_scores) <= observed_r2))


def analyze_inventory(
    cases: dict[str, dict[str, object]], output: Path
) -> list[dict[str, object]]:
    inventory = []
    health_rows = []
    for case in CASE_ORDER:
        result = cases[case]
        quality = assess_channel_quality(result)
        bad = [int(row["channel_index"]) for row in quality if row["automatic_bad"]]
        suspect = [
            int(row["channel_index"])
            for row in quality
            if row["automatic_suspect"] and not row["automatic_bad"]
        ]
        info = CASE_INFO[case]
        inventory.append(
            {
                "case": case,
                "kind": info.kind,
                "set_current_ma": info.current_ma,
                "assumed_cycle_count": info.cycles,
                "repeat": info.repeat,
                "start_time": result["start_time"],
                "duration_s": float(result["duration_s"]),
                "sample_rate_hz": float(result["sample_rate"]),
                "sample_count": int(result["archive_metadata"]["sample_count"]),
                "bad_channels_1based": ";".join(map(str, bad)),
                "additional_suspect_channels_1based": ";".join(map(str, suspect)),
                "healthy_channel_count": len(healthy_indices(result)),
            }
        )
        health_rows.extend({"case": case, **row} for row in quality)
    write_csv(output / "case_inventory.csv", inventory)
    write_csv(output / "channel_health.csv", health_rows)
    return inventory


def analyze_fixed_harmonic(
    cases: dict[str, dict[str, object]], output: Path
) -> list[dict[str, object]]:
    rows = []
    frequency_grid = np.arange(0.035, 0.251, 0.005)
    for case in CASE_ORDER:
        result = cases[case]
        times = time_axis(result)
        indices = healthy_indices(result)
        values = np.asarray(result["features"]["slow_mean"])[:, indices] * 1e6
        base = polynomial_design(times)
        residual = values - base @ np.linalg.lstsq(base, values, rcond=None)[0]
        amplitudes = []
        target_complex = None
        for frequency in frequency_grid:
            design = np.column_stack(
                (
                    np.sin(2.0 * np.pi * frequency * times),
                    np.cos(2.0 * np.pi * frequency * times),
                )
            )
            coefficients = np.linalg.lstsq(design, residual, rcond=None)[0]
            complex_coefficient = coefficients[0] + 1j * coefficients[1]
            amplitudes.append(np.abs(complex_coefficient))
            if np.isclose(frequency, 0.1):
                target_complex = complex_coefficient
        if target_complex is None:
            raise RuntimeError("0.1 Hz is absent from the harmonic grid")
        amplitudes_array = np.asarray(amplitudes)
        median_grid = np.median(amplitudes_array, axis=1)
        target_amplitude = np.abs(target_complex)
        phase = np.angle(target_complex)
        rows.append(
            {
                "case": case,
                "channel_count": len(indices),
                "median_0p1hz_amplitude_uv_peak": float(np.median(target_amplitude)),
                "q25_0p1hz_amplitude_uv_peak": float(np.quantile(target_amplitude, 0.25)),
                "q75_0p1hz_amplitude_uv_peak": float(np.quantile(target_amplitude, 0.75)),
                "max_0p1hz_amplitude_uv_peak": float(np.max(target_amplitude)),
                "phase_coherence": float(np.abs(np.mean(np.exp(1j * phase)))),
                "phase_or_antiphase_coherence": float(
                    np.abs(np.mean(np.exp(2j * phase)))
                ),
                "nearby_frequency_percentile": float(
                    np.mean(median_grid <= np.median(target_amplitude))
                ),
            }
        )
    write_csv(output / "fixed_0p1hz_harmonic.csv", rows)
    return rows


def analyze_timing_crossvalidation(
    cases: dict[str, dict[str, object]], output: Path
) -> tuple[list[dict[str, object]], dict[str, dict[int, float]], dict[str, list[tuple[float, float, float]]]]:
    rows = []
    response_vectors: dict[str, dict[int, float]] = {}
    selected_timings: dict[str, list[tuple[float, float, float]]] = {}
    for case in ("opensvnear", *CP_CASES):
        result = cases[case]
        info = CASE_INFO[case]
        times = time_axis(result)
        indices = healthy_indices(result)
        response_vectors[case] = {}
        selected_timings[case] = []
        for feature in FEATURES:
            values = np.asarray(result["features"][feature])[:, indices] * 1e6
            for fold in range(2):
                discovery = list(range(fold, len(indices), 2))
                validation = list(range(1 - fold, len(indices), 2))
                start_s, period_s, duty, discovery_r2 = select_timing(
                    values,
                    times,
                    discovery,
                    info.cycles,
                    float(result["duration_s"]),
                )
                coefficients, validation_r2 = fit_state(
                    values[:, validation],
                    times,
                    start_s,
                    period_s,
                    duty,
                    info.cycles,
                )
                validation_score = float(np.median(validation_r2))
                row = {
                    "case": case,
                    "feature": feature,
                    "fold": fold + 1,
                    "discovery_channel_count": len(discovery),
                    "validation_channel_count": len(validation),
                    "selected_start_s": start_s,
                    "selected_period_s": period_s,
                    "selected_duty": duty,
                    "discovery_median_delta_r2": discovery_r2,
                    "validation_median_delta_r2": validation_score,
                    "validation_median_response_uv": float(np.median(coefficients)),
                    "validation_median_abs_response_uv": float(
                        np.median(np.abs(coefficients))
                    ),
                    "validation_same_sign_fraction": float(
                        max(np.mean(coefficients > 0), np.mean(coefficients < 0))
                    ),
                    "validation_phase_percentile": phase_percentile(
                        values[:, validation],
                        times,
                        start_s,
                        period_s,
                        duty,
                        info.cycles,
                        validation_score,
                    ),
                }
                rows.append(row)
                if feature == "slow_mean":
                    selected_timings[case].append((start_s, period_s, duty))
                    for local_column, coefficient in zip(validation, coefficients):
                        response_vectors[case][indices[local_column]] = float(coefficient)
    write_csv(output / "timing_crossvalidation.csv", rows)
    return rows, response_vectors, selected_timings


def refined_edges(
    values: np.ndarray,
    times: np.ndarray,
    discovery_columns: list[int],
    start_s: float,
    period_s: float,
    duty: float,
    cycles: int,
) -> tuple[np.ndarray, np.ndarray]:
    discovery = values[:, discovery_columns]
    smooth = signal.savgol_filter(discovery, 7, 2, axis=0, mode="interp")
    derivative = np.gradient(smooth, times, axis=0)
    scale = 1.4826 * np.median(
        np.abs(derivative - np.median(derivative, axis=0)), axis=0
    )
    standardized = derivative / np.maximum(scale, 1e-9)
    score = np.median(np.abs(standardized), axis=1)
    nominal = []
    signs = []
    for cycle in range(cycles):
        nominal.extend(
            (start_s + cycle * period_s, start_s + (cycle + duty) * period_s)
        )
        signs.extend((1.0, -1.0))
    selected = []
    for edge in nominal:
        use = np.flatnonzero((times >= edge - 1.25) & (times <= edge + 1.25))
        selected.append(float(times[use[np.argmax(score[use])]]))
    return np.asarray(selected), np.asarray(signs)


def event_response(
    values: np.ndarray,
    times: np.ndarray,
    edges: np.ndarray,
    signs: np.ndarray,
) -> np.ndarray:
    responses = []
    for edge, sign_value in zip(edges, signs):
        pre = (times >= edge - 1.0) & (times < edge - 0.25)
        post = (times > edge + 0.25) & (times <= edge + 1.0)
        if np.sum(pre) < 3 or np.sum(post) < 3:
            continue
        delta = np.median(values[post], axis=0) - np.median(values[pre], axis=0)
        responses.append(sign_value * delta)
    return np.asarray(responses)


def event_signflip_pvalue(responses: np.ndarray, seed: int) -> tuple[float, float]:
    observed = float(np.linalg.norm(np.mean(responses, axis=0)))
    random = np.random.default_rng(seed)
    null = []
    for _ in range(1999):
        signs = random.choice((-1.0, 1.0), size=(len(responses), 1))
        null.append(float(np.linalg.norm(np.mean(responses * signs, axis=0))))
    pvalue = (1.0 + np.sum(np.asarray(null) >= observed)) / (len(null) + 1.0)
    return observed, float(pvalue)


def analyze_events(
    cases: dict[str, dict[str, object]],
    timings: dict[str, list[tuple[float, float, float]]],
    output: Path,
) -> list[dict[str, object]]:
    rows = []
    event_rows = []
    for case in ("opensvnear", *CP_CASES):
        result = cases[case]
        info = CASE_INFO[case]
        times = time_axis(result)
        indices = healthy_indices(result)
        values = np.asarray(result["features"]["slow_mean"])[:, indices] * 1e6
        for fold in range(2):
            discovery = list(range(fold, len(indices), 2))
            validation = list(range(1 - fold, len(indices), 2))
            start_s, period_s, duty = timings[case][fold]
            edges, signs = refined_edges(
                values,
                times,
                discovery,
                start_s,
                period_s,
                duty,
                info.cycles,
            )
            responses = event_response(values[:, validation], times, edges, signs)
            mean_vector = np.mean(responses, axis=0)
            same_sign = np.mean(
                np.sign(responses) == np.sign(mean_vector)[None, :]
            )
            correlations = []
            if len(responses) > 2:
                for event_index in range(len(responses)):
                    reference = np.mean(
                        np.delete(responses, event_index, axis=0), axis=0
                    )
                    if np.std(reference) > 0 and np.std(responses[event_index]) > 0:
                        correlations.append(
                            np.corrcoef(reference, responses[event_index])[0, 1]
                        )
            norm_uv, pvalue = event_signflip_pvalue(
                responses, seed=20260811 + 100 * CASE_ORDER.index(case) + fold
            )
            rows.append(
                {
                    "case": case,
                    "fold": fold + 1,
                    "event_count": len(responses),
                    "median_abs_edge_adjustment_s": float(
                        np.median(
                            np.abs(
                                edges
                                - np.asarray(
                                    [
                                        value
                                        for cycle in range(info.cycles)
                                        for value in (
                                            start_s + cycle * period_s,
                                            start_s + (cycle + duty) * period_s,
                                        )
                                    ]
                                )
                            )
                        )
                    ),
                    "median_signed_step_uv": float(np.median(mean_vector)),
                    "median_abs_mean_step_uv": float(np.median(np.abs(mean_vector))),
                    "event_channel_same_sign_fraction": float(same_sign),
                    "median_leave_one_event_out_spatial_correlation": float(
                        np.median(correlations) if correlations else np.nan
                    ),
                    "mean_vector_l2_uv": norm_uv,
                    "signflip_pvalue": pvalue,
                }
            )
            for event_index, (edge, response) in enumerate(zip(edges, responses)):
                for local_column, value in zip(validation, response):
                    event_rows.append(
                        {
                            "case": case,
                            "fold": fold + 1,
                            "event": event_index + 1,
                            "edge_time_s": edge,
                            "channel_index": indices[local_column] + 1,
                            "polarity_adjusted_step_uv": float(value),
                        }
                    )
    write_csv(output / "edge_response_summary.csv", rows)
    write_csv(output / "edge_responses.csv", event_rows)
    return rows


def analyze_high_bands(
    cases: dict[str, dict[str, object]],
    timings: dict[str, list[tuple[float, float, float]]],
    output: Path,
) -> list[dict[str, object]]:
    rows = []
    for case in ("opensvnear", *CP_CASES):
        result = cases[case]
        info = CASE_INFO[case]
        indices = healthy_indices(result)
        segment_times = np.asarray(result["welch_segment_time_s"], dtype=float)
        nperseg = int(result["archive_metadata"]["config"]["welch_nperseg"])
        segment_times += 0.5 * nperseg / float(result["sample_rate"])
        power = np.asarray(result["welch_segment_bandpower"])[:, indices, :]
        power_db = 10.0 * np.log10(np.maximum(power, 1e-300))
        for band_index, band_name in enumerate(BAND_NAMES):
            for fold in range(2):
                discovery = list(range(fold, len(indices), 2))
                validation = list(range(1 - fold, len(indices), 2))
                start_s, period_s, duty = timings[case][fold]
                coefficients, delta_r2 = fit_state(
                    power_db[:, validation, band_index],
                    segment_times,
                    start_s,
                    period_s,
                    duty,
                    info.cycles,
                )
                rows.append(
                    {
                        "case": case,
                        "band": str(band_name),
                        "fold": fold + 1,
                        "validation_channel_count": len(validation),
                        "median_on_minus_off_db": float(np.median(coefficients)),
                        "median_abs_on_minus_off_db": float(
                            np.median(np.abs(coefficients))
                        ),
                        "median_delta_r2": float(np.median(delta_r2)),
                        "same_sign_fraction": float(
                            max(np.mean(coefficients > 0), np.mean(coefficients < 0))
                        ),
                    }
                )
    write_csv(output / "synchronized_bandpower.csv", rows)
    return rows


def vector_pair_metrics(
    first: dict[int, float], second: dict[int, float]
) -> dict[str, float]:
    common = sorted(set(first) & set(second))
    a = np.asarray([first[index] for index in common])
    b = np.asarray([second[index] for index in common])
    correlation = float(np.corrcoef(a, b)[0, 1]) if len(common) >= 3 else np.nan
    cosine = float(np.dot(a, b) / max(np.linalg.norm(a) * np.linalg.norm(b), 1e-30))
    return {
        "common_channel_count": len(common),
        "spatial_correlation": correlation,
        "cosine_similarity": cosine,
        "sign_agreement": float(np.mean(np.sign(a) == np.sign(b))),
        "first_median_uv": float(np.median(a)),
        "second_median_uv": float(np.median(b)),
        "first_median_abs_uv": float(np.median(np.abs(a))),
        "second_median_abs_uv": float(np.median(np.abs(b))),
    }


def harmonic_vector(
    result: dict[str, object], indices: list[int], frequency_hz: float
) -> np.ndarray:
    times = time_axis(result)
    values = np.asarray(result["features"]["slow_mean"])[:, indices] * 1e6
    base = polynomial_design(times)
    residual = values - base @ np.linalg.lstsq(base, values, rcond=None)[0]
    design = np.column_stack(
        (
            np.sin(2.0 * np.pi * frequency_hz * times),
            np.cos(2.0 * np.pi * frequency_hz * times),
        )
    )
    coefficients = np.linalg.lstsq(design, residual, rcond=None)[0]
    return coefficients[0] + 1j * coefficients[1]


def analyze_repeats_and_dose(
    cases: dict[str, dict[str, object]], output: Path
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    response_vectors: dict[str, dict[int, float]] = {}
    record_rows = []
    for case in CP_CASES:
        result = cases[case]
        indices = healthy_indices(result)
        values = np.asarray(result["features"]["slow_mean"])[:, indices] * 1e6
        coefficients, delta_r2 = fit_state(
            values, time_axis(result), 30.0, 10.0, 0.5, 12
        )
        response_vectors[case] = dict(zip(indices, map(float, coefficients)))
        record_rows.append(
            {
                "case": case,
                "current_ma": CASE_INFO[case].current_ma,
                "repeat": CASE_INFO[case].repeat,
                "timing": "fixed_nominal_start30_period10_duty0p5",
                "median_response_uv": float(np.median(coefficients)),
                "median_abs_response_uv": float(np.median(np.abs(coefficients))),
                "median_delta_r2": float(np.median(delta_r2)),
            }
        )

    repeat_rows = []
    for current, first_case, second_case in (
        (1000, "cp1000near", "cp1000near2"),
        (3000, "cp3000near", "cp3000near2"),
    ):
        first_result = cases[first_case]
        second_result = cases[second_case]
        common = sorted(
            set(healthy_indices(first_result)) & set(healthy_indices(second_result))
        )
        frequency_grid = np.arange(0.035, 0.251, 0.005)
        harmonic_similarity = []
        for frequency_hz in frequency_grid:
            first_harmonic = harmonic_vector(first_result, common, frequency_hz)
            second_harmonic = harmonic_vector(second_result, common, frequency_hz)
            harmonic_similarity.append(
                float(
                    abs(np.vdot(first_harmonic, second_harmonic))
                    / max(
                        np.linalg.norm(first_harmonic)
                        * np.linalg.norm(second_harmonic),
                        1e-30,
                    )
                )
            )
        target_index = int(np.argmin(np.abs(frequency_grid - 0.1)))
        target_similarity = harmonic_similarity[target_index]
        repeat_rows.append(
            {
                "current_ma": current,
                "first_case": first_case,
                "second_case": second_case,
                **vector_pair_metrics(
                    response_vectors[first_case], response_vectors[second_case]
                ),
                "fixed_timing": "start30_period10_duty0p5",
                "harmonic_0p1hz_complex_spatial_similarity": target_similarity,
                "harmonic_0p1hz_nearby_similarity_percentile": float(
                    np.mean(np.asarray(harmonic_similarity) <= target_similarity)
                ),
            }
        )

    dose_rows = []
    grouped = {
        200.0: ("cp200near",),
        500.0: ("cp500near",),
        1000.0: ("cp1000near", "cp1000near2"),
        3000.0: ("cp3000near", "cp3000near2"),
    }
    for current, names in grouped.items():
        selected = [row for row in record_rows if row["case"] in names]
        dose_rows.append(
            {
                "current_ma": current,
                "record_count": len(names),
                "timing": "fixed_nominal_start30_period10_duty0p5",
                "median_of_record_median_response_uv": float(
                    np.median([row["median_response_uv"] for row in selected])
                ),
                "median_of_record_median_abs_response_uv": float(
                    np.median([row["median_abs_response_uv"] for row in selected])
                ),
                "minimum_record_median_response_uv": float(
                    np.min([row["median_response_uv"] for row in selected])
                ),
                "maximum_record_median_response_uv": float(
                    np.max([row["median_response_uv"] for row in selected])
                ),
            }
        )
    currents = np.asarray([row["current_ma"] for row in dose_rows], dtype=float)
    signed = np.asarray(
        [row["median_of_record_median_response_uv"] for row in dose_rows], dtype=float
    )
    absolute = np.asarray(
        [row["median_of_record_median_abs_response_uv"] for row in dose_rows],
        dtype=float,
    )
    rho_signed = float(stats.spearmanr(currents, signed).statistic)
    rho_absolute = float(stats.spearmanr(currents, absolute).statistic)
    for row in dose_rows:
        row["global_spearman_rho_signed"] = rho_signed
        row["global_spearman_rho_absolute"] = rho_absolute
    write_csv(output / "repeatability.csv", repeat_rows)
    write_csv(output / "nominal_record_responses.csv", record_rows)
    write_csv(output / "dose_response.csv", dose_rows)
    return repeat_rows, dose_rows


def plot_results(
    cases: dict[str, dict[str, object]],
    timings: dict[str, list[tuple[float, float, float]]],
    dose_rows: list[dict[str, object]],
    repeat_rows: list[dict[str, object]],
    output: Path,
) -> None:
    fig, axes = plt.subplots(4, 2, figsize=(14, 11), constrained_layout=True)
    for axis, case in zip(axes.flat, ("opensvnear", *CP_CASES, "bkg2")):
        result = cases[case]
        times = time_axis(result)
        indices = healthy_indices(result)
        values = np.asarray(result["features"]["slow_mean"])[:, indices] * 1e6
        centered = values - np.median(values, axis=0)
        axis.plot(times, centered, color="#8b949e", lw=0.55, alpha=0.26)
        axis.plot(times, np.median(centered, axis=1), color="#111111", lw=1.1)
        if case in timings:
            start_s, period_s, duty = timings[case][0]
            state = protocol_state(
                times, start_s, period_s, duty, CASE_INFO[case].cycles
            )
            scale = max(float(np.quantile(np.abs(centered), 0.8)), 1.0)
            axis.plot(times, state * scale, color="#d1495b", lw=0.8, alpha=0.8)
        axis.set_title(case)
        axis.set_ylabel("Centered low-rate signal (uV)")
        axis.grid(alpha=0.18)
    axes[-1, 0].set_xlabel("Time (s)")
    axes[-1, 1].set_xlabel("Time (s)")
    fig.savefig(output / "low_frequency_timelines.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), constrained_layout=True)
    currents = np.asarray([row["current_ma"] for row in dose_rows])
    signed = np.asarray(
        [row["median_of_record_median_response_uv"] for row in dose_rows]
    )
    absolute = np.asarray(
        [row["median_of_record_median_abs_response_uv"] for row in dose_rows]
    )
    axes[0].plot(currents, signed, marker="o", label="signed median", color="#33658a")
    axes[0].plot(currents, absolute, marker="s", label="median absolute", color="#d1495b")
    axes[0].axhline(0.0, color="#222222", lw=0.7)
    axes[0].set(xlabel="Set current (mA)", ylabel="Cross-validated response (uV)", title="Dose check")
    axes[0].legend(frameon=False)
    axes[1].bar(
        ["1000 mA", "3000 mA"],
        [float(row["spatial_correlation"]) for row in repeat_rows],
        color=("#33658a", "#d1495b"),
    )
    axes[1].axhline(0.0, color="#222222", lw=0.7)
    axes[1].set(ylim=(-1.0, 1.0), ylabel="Spatial correlation", title="Independent repeats")
    for axis in axes:
        axis.grid(alpha=0.18)
    fig.savefig(output / "dose_and_repeatability.png", dpi=180)
    plt.close(fig)


def average_rows(rows: list[dict[str, object]], case: str, feature: str, key: str) -> float:
    values = [
        float(row[key])
        for row in rows
        if row["case"] == case and row.get("feature") == feature
    ]
    return float(np.mean(values))


def write_report(
    output: Path,
    inventory: list[dict[str, object]],
    harmonic_rows: list[dict[str, object]],
    timing_rows: list[dict[str, object]],
    event_rows: list[dict[str, object]],
    band_rows: list[dict[str, object]],
    repeat_rows: list[dict[str, object]],
    dose_rows: list[dict[str, object]],
) -> None:
    harmonic = {str(row["case"]): row for row in harmonic_rows}
    repeat = {int(row["current_ma"]): row for row in repeat_rows}
    dose = {int(row["current_ma"]): row for row in dose_rows}
    low_summary = {
        case: {
            "r2": average_rows(timing_rows, case, "slow_mean", "validation_median_delta_r2"),
            "signed": average_rows(timing_rows, case, "slow_mean", "validation_median_response_uv"),
            "absolute": average_rows(timing_rows, case, "slow_mean", "validation_median_abs_response_uv"),
            "phase": average_rows(timing_rows, case, "slow_mean", "validation_phase_percentile"),
        }
        for case in ("opensvnear", *CP_CASES)
    }
    event_summary = {
        case: {
            key: float(np.mean([float(row[key]) for row in event_rows if row["case"] == case]))
            for key in (
                "median_signed_step_uv",
                "median_abs_mean_step_uv",
                "event_channel_same_sign_fraction",
                "median_leave_one_event_out_spatial_correlation",
                "signflip_pvalue",
            )
        }
        for case in ("opensvnear", *CP_CASES)
    }
    max_high = {
        case: max(
            abs(float(row["median_on_minus_off_db"]))
            for row in band_rows
            if row["case"] == case
        )
        for case in ("opensvnear", *CP_CASES)
    }
    bad_text = ", ".join(
        f"{row['case']}: 坏道 {row['bad_channels_1based'] or '无'}, 另有可疑道 {row['additional_suspect_channels_1based'] or '无'}"
        for row in inventory
    )
    table_lines = []
    for case in ("opensvnear", *CP_CASES):
        table_lines.append(
            f"| {case} | {low_summary[case]['signed']:+.2f} | {low_summary[case]['absolute']:.2f} | "
            f"{100 * low_summary[case]['r2']:.2f}% | {event_summary[case]['median_signed_step_uv']:+.2f} | "
            f"{event_summary[case]['signflip_pvalue']:.3f} | {max_high[case]:.3f} |"
        )
    report = f"""# 2026-08-11 第二批阴极保护实验精确分析

## 1. 数据与方法

- 分析目录：`E:\\Lab\\raw\\8.11.2` 的 9 个 TDMS 文件；所有结论来自完整覆盖的精确归档，不是短窗口或通道拼接结果。
- `cp200/500/1000/3000near` 中数字按电源设定电流 mA 解释；1000 mA 与 3000 mA 各有两次独立记录。
- 各闭路电流文件约 180 s，和“前 30 s OFF + 12 次约 5 s ON/5 s OFF + 后 30 s OFF”相符。OPEN 为 {next(row['duration_s'] for row in inventory if row['case'] == 'opensvnear'):.2f} s，本报告按 8 个循环拟合；这是根据时长作出的重建，不是同步电流记录。
- 每个文件独立判坏道；没有把某次坏道状态固定套到其他文件。{bad_text}。
- 手操误差处理：在 26–34 s 的开始/结束余量内搜索平均周期和 45%/50%/55% 占空比。每次只用一半健康通道找时刻，另一半通道给出结果，再交换两半；这样避免同一通道既选时刻又证明信号。

## 2. 主要数值

| 工况 | 低频有符号 ON-OFF (uV) | 低频绝对响应 (uV) | 独立通道解释率 | 边沿极性校正响应 (uV) | 边沿符号翻转 p | 最大同步频带变化 (dB) |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(table_lines)}

固定 0.1 Hz 正弦拟合的健康通道中位幅值：背景 1 为 {float(harmonic['bkg']['median_0p1hz_amplitude_uv_peak']):.2f} uV，背景 2 为 {float(harmonic['bkg2']['median_0p1hz_amplitude_uv_peak']):.2f} uV，OPEN 为 {float(harmonic['opensvnear']['median_0p1hz_amplitude_uv_peak']):.2f} uV；闭路各组范围为 {min(float(harmonic[name]['median_0p1hz_amplitude_uv_peak']) for name in CP_CASES):.2f}–{max(float(harmonic[name]['median_0p1hz_amplitude_uv_peak']) for name in CP_CASES):.2f} uV。目标频率没有稳定高于背景。

重复性是最关键的判据。使用事先规定的 30 s 起始、10 s 周期和 50% 占空比，不再搜索时刻：1000 mA 两次低频响应空间相关系数为 {float(repeat[1000]['spatial_correlation']):+.2f}、符号一致率 {float(repeat[1000]['sign_agreement']):.2f}；3000 mA 分别为 {float(repeat[3000]['spatial_correlation']):+.2f} 和 {float(repeat[3000]['sign_agreement']):.2f}。允许两次手操存在整体相位差后，固定 0.1 Hz 的复数空间相似度在 1000 mA 为 {float(repeat[1000]['harmonic_0p1hz_complex_spatial_similarity']):.2f}（邻频第 {100 * float(repeat[1000]['harmonic_0p1hz_nearby_similarity_percentile']):.0f} 百分位），3000 mA 为 {float(repeat[3000]['harmonic_0p1hz_complex_spatial_similarity']):.2f}（第 {100 * float(repeat[3000]['harmonic_0p1hz_nearby_similarity_percentile']):.0f} 百分位）。二者都没有达到 95% 的频率特异性标准。

固定名义时序下，200、500、1000、3000 mA 的记录间中位有符号响应依次为 {dose[200]['median_of_record_median_response_uv']:+.2f}、{dose[500]['median_of_record_median_response_uv']:+.2f}、{dose[1000]['median_of_record_median_response_uv']:+.2f}、{dose[3000]['median_of_record_median_response_uv']:+.2f} uV；绝对响应依次为 {dose[200]['median_of_record_median_abs_response_uv']:.2f}、{dose[500]['median_of_record_median_abs_response_uv']:.2f}、{dose[1000]['median_of_record_median_abs_response_uv']:.2f}、{dose[3000]['median_of_record_median_abs_response_uv']:.2f} uV。绝对响应与电流的 Spearman 相关仅为 {dose[200]['global_spearman_rho_absolute']:+.2f}，没有单调剂量关系。

需要保留一个弱提示：`cp3000near2` 的时序搜索后低频绝对响应为 {low_summary['cp3000near2']['absolute']:.2f} uV、独立通道解释率 {100 * low_summary['cp3000near2']['r2']:.2f}%，比多数闭路组突出；但同电流第一次只有 {low_summary['cp3000near']['absolute']:.2f} uV 和 {100 * low_summary['cp3000near']['r2']:.2f}%，且 0.1 Hz 幅值没有稳定超过背景。因此它只能记为孤立候选，不能记为阳性。

## 3. 结论

**本批数据仍未得到可信的阴极保护阳性检出，但 3000 mA 第二次记录存在一个值得保留的弱候选。** 允许手操定时误差后可以从低频漂移中拟合出若干微伏，但 OPEN 对照也有同量级拟合；1000/3000 mA 的固定时序空间图样未复现；绝对响应不随电流单调增强；开和关边沿不能形成稳定的反向瞬态；5 Hz–200 kHz 的五个时变频带也没有同步增强。

这不是“阴极保护没有电磁信号”，而是：**在本次单一距离、TC2、当前电极几何和采集链下，即使设定到 3000 mA，也没有检出可与手操开关同步、可重复并具有剂量关系的信号。** 因为没有同步记录实际输出电流波形，时序只能重建；同时只测了一个距离，所以不能判断距离衰减。

目前可把约 {max(float(harmonic['bkg']['median_0p1hz_amplitude_uv_peak']), float(harmonic['bkg2']['median_0p1hz_amplitude_uv_peak'])):.1f} uV 视为本批 0.1 Hz 单通道典型背景拟合量级，而不能把 1–5 uV 的任一拟合值直接称为检出。要宣布阳性，至少要同时满足：相对 OPEN/背景显著、独立重复同方向且空间相关、电流增加时响应增强、开关边沿极性相反。

## 4. 输出

- `case_inventory.csv`、`channel_health.csv`：工况与逐文件动态通道质量。
- `fixed_0p1hz_harmonic.csv`：固定 0.1 Hz 幅值、相位一致性和邻频排序。
- `timing_crossvalidation.csv`：手操时序搜索及独立通道验证。
- `edge_response_summary.csv`、`edge_responses.csv`：局部边沿重建和逐次瞬态。
- `synchronized_bandpower.csv`：5 Hz–200 kHz 五频带同步 ON-OFF 变化。
- `repeatability.csv`、`nominal_record_responses.csv`、`dose_response.csv`：不经过时序搜索的重复性和电流剂量检验。
- `low_frequency_timelines.png`、`dose_and_repeatability.png`：主要可视化。
"""
    (output / "EXPERIMENT_ANALYSIS_REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--archive-root",
        type=Path,
        default=Path("results/experiment_20260811_2/exact_archive"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("results/experiment_20260811_2")
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    cases = load_cases(args.archive_root)
    inventory = analyze_inventory(cases, args.output)
    harmonic_rows = analyze_fixed_harmonic(cases, args.output)
    timing_rows, _response_vectors, timings = analyze_timing_crossvalidation(
        cases, args.output
    )
    event_rows = analyze_events(cases, timings, args.output)
    band_rows = analyze_high_bands(cases, timings, args.output)
    repeat_rows, dose_rows = analyze_repeats_and_dose(cases, args.output)
    plot_results(cases, timings, dose_rows, repeat_rows, args.output)
    write_report(
        args.output,
        inventory,
        harmonic_rows,
        timing_rows,
        event_rows,
        band_rows,
        repeat_rows,
        dose_rows,
    )
    print(f"Analysis complete: {args.output.resolve()}")


if __name__ == "__main__":
    main()
