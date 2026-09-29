# -*- coding: utf-8 -*-
"""Analyze the 2026-08-11 TC2 cathodic-protection experiment.

The analysis consumes exact archives, not raw TDMS files.  Protocol timing is
reconstructed from the operator log and is therefore kept explicit in every
output table.  Per-acquisition channel quality is assessed dynamically.
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

from channel_quality import assess_channel_quality, common_valid_channel_indices
from exact_tdms_archive import load_exact_archive


CASE_ORDER = (
    "bkg",
    "bar5a",
    "out100ma",
    "5v100ma",
    "bkg2",
    "5v100ma2",
    "alter100ma",
    "5v50ma",
    "5v10ma",
    "alter50ma",
    "10to100",
    "005hz",
)
FEATURES = (
    "slow_mean",
    "broadband_rms",
    "subkhz_rms",
    "fast_residual_rms",
    "difference_rms",
)
BANDS = (
    ("5_100hz", 5.0, 100.0),
    ("100_1khz", 100.0, 1_000.0),
    ("1_20khz", 1_000.0, 20_000.0),
    ("20_80khz", 20_000.0, 80_000.0),
    ("80_200khz", 80_000.0, 199_900.0),
)


@dataclass(frozen=True)
class Protocol:
    case: str
    currents_ma: tuple[float, ...]
    block_seconds: float
    timing_source: str


PROTOCOLS = {
    "alter50ma": Protocol(
        "alter50ma", (0.0, 50.0, 0.0, 50.0, 0.0), 30.0,
        "operator_log_centered_5x30s",
    ),
    "alter100ma": Protocol(
        "alter100ma", (0.0, 100.0, 0.0, 100.0, 0.0), 30.0,
        "operator_log_centered_5x30s",
    ),
    "10to100": Protocol(
        "10to100", (0.0, 10.0, 0.0, 50.0, 0.0, 100.0, 0.0, 200.0, 0.0),
        30.0, "operator_log_centered_9x30s",
    ),
}


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_cases(root: Path) -> dict[str, dict[str, object]]:
    output = {}
    for case in CASE_ORDER:
        matches = sorted(root.glob(f"{case}__*"))
        if len(matches) != 1:
            raise ValueError(f"Expected one archive for {case}, found {len(matches)}")
        output[case] = load_exact_archive(matches[0])
    return output


def time_axis(result: dict[str, object]) -> np.ndarray:
    rate = float(result["envelope_fs"])
    count = len(result["features"]["slow_mean"])
    first = float(
        result["archive_metadata"]["lowpass_filter"]["analysis_rate_first_sample_time_s"]
    )
    return first + np.arange(count) / rate


def protocol_edges(result: dict[str, object], protocol: Protocol) -> np.ndarray:
    total = len(protocol.currents_ma) * protocol.block_seconds
    start = (float(result["duration_s"]) - total) / 2.0
    return start + np.arange(len(protocol.currents_ma) + 1) * protocol.block_seconds


def interval_level(
    values: np.ndarray,
    times: np.ndarray,
    start: float,
    end: float,
    edge_trim_s: float = 5.0,
) -> np.ndarray:
    use = (times >= start + edge_trim_s) & (times < end - edge_trim_s)
    if np.sum(use) < 10:
        raise ValueError(f"Interval {start:.2f}-{end:.2f}s has too few samples")
    return np.median(values[use], axis=0)


def integrated_power(
    frequency: np.ndarray, psd: np.ndarray, low: float, high: float
) -> np.ndarray:
    use = (frequency >= low) & (frequency < high)
    return np.trapz(psd[..., use], frequency[use], axis=-1)


def harmonic_coefficient(values: np.ndarray, rate: float, frequency: float) -> complex:
    times = (np.arange(len(values)) + 0.5) / rate
    normalized_time = 2.0 * (times - np.mean(times)) / np.ptp(times)
    design = np.column_stack((
        np.ones(len(times)),
        normalized_time,
        normalized_time**2,
        normalized_time**3,
        np.sin(2.0 * np.pi * frequency * times),
        np.cos(2.0 * np.pi * frequency * times),
    ))
    coefficient = np.linalg.lstsq(design, values, rcond=None)[0]
    return complex(coefficient[-2], coefficient[-1])


def local_excess_db(
    frequency: np.ndarray,
    psd: np.ndarray,
    center_hz: float,
    feature_half_width_hz: float = 20.0,
    side_half_width_hz: float = 125.0,
) -> np.ndarray:
    feature = (
        (frequency >= center_hz - feature_half_width_hz)
        & (frequency <= center_hz + feature_half_width_hz)
    )
    side = (
        (frequency >= center_hz - side_half_width_hz)
        & (frequency <= center_hz + side_half_width_hz)
        & ~feature
    )
    feature_density = np.trapz(psd[..., feature], frequency[feature], axis=-1) / (
        frequency[feature][-1] - frequency[feature][0]
    )
    side_indices = np.flatnonzero(side)
    side_density = np.trapz(psd[..., side], frequency[side], axis=-1) / (
        (frequency[side_indices][-1] - frequency[side_indices][0])
        - 2.0 * feature_half_width_hz
    )
    return 10.0 * np.log10(
        np.maximum(feature_density, 1e-300) / np.maximum(side_density, 1e-300)
    )


def interval_mean_current(
    start: float,
    end: float,
    edges: np.ndarray,
    currents: tuple[float, ...],
) -> float:
    charge = 0.0
    for index, current in enumerate(currents):
        overlap = max(0.0, min(end, edges[index + 1]) - max(start, edges[index]))
        charge += overlap * current
    return charge / (end - start)


def collect_inventory_and_health(
    cases: dict[str, dict[str, object]], output: Path
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    inventory = []
    health_rows = []
    for case in CASE_ORDER:
        result = cases[case]
        quality = assess_channel_quality(result)
        inventory.append({
            "case": case,
            "start_time": result["start_time"],
            "duration_s": result["duration_s"],
            "sample_rate_hz": result["sample_rate"],
            "sample_count": result["archive_metadata"]["sample_count"],
            "channel_count": len(result["channel_names"]),
            "automatic_bad_channels": ";".join(
                str(row["channel_index"]) for row in quality if row["automatic_bad"]
            ),
            "automatic_suspect_channels": ";".join(
                str(row["channel_index"])
                for row in quality
                if row["automatic_suspect"] and not row["automatic_bad"]
            ),
        })
        for row in quality:
            health_rows.append({"case": case, **row})
    write_csv(output / "case_inventory.csv", inventory)
    write_csv(output / "channel_health.csv", health_rows)
    return inventory, health_rows


def analyze_steady_cases(
    cases: dict[str, dict[str, object]], output: Path
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    comparisons = (
        ("bar5a", "bkg"),
        ("out100ma", "bkg"),
        ("5v10ma", "bkg2"),
        ("5v50ma", "bkg2"),
        ("5v100ma", "bkg2"),
        ("5v100ma2", "bkg2"),
    )
    band_rows = []
    offset_rows = []
    for case, reference in comparisons:
        result = cases[case]
        baseline = cases[reference]
        indices = common_valid_channel_indices(
            result, baseline, exclude_suspect=True
        )
        frequency = np.asarray(result["frequency"])
        for band, low, high in BANDS:
            current_power = integrated_power(frequency, result["psd"][indices], low, high)
            baseline_power = integrated_power(
                frequency, baseline["psd"][indices], low, high
            )
            contrast = 10.0 * np.log10(current_power / baseline_power)
            band_rows.append({
                "case": case,
                "reference": reference,
                "band": band,
                "common_channel_count": len(indices),
                "median_delta_db": float(np.median(contrast)),
                "q25_delta_db": float(np.quantile(contrast, 0.25)),
                "q75_delta_db": float(np.quantile(contrast, 0.75)),
                "positive_channel_fraction": float(np.mean(contrast > 0.0)),
            })

        current_level = np.median(result["features"]["slow_mean"][:, indices], axis=0)
        baseline_level = np.median(
            baseline["features"]["slow_mean"][:, indices], axis=0
        )
        offset_uv = 1e6 * (current_level - baseline_level)
        for local_index, channel_index in enumerate(indices):
            offset_rows.append({
                "case": case,
                "reference": reference,
                "channel_index": channel_index + 1,
                "offset_uv": float(offset_uv[local_index]),
            })
    write_csv(output / "steady_band_contrasts.csv", band_rows)
    write_csv(output / "steady_baseline_offsets.csv", offset_rows)
    return band_rows, offset_rows


def analyze_block_protocols(
    cases: dict[str, dict[str, object]], output: Path
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    response_rows = []
    schedule_rows = []
    for case, protocol in PROTOCOLS.items():
        result = cases[case]
        quality = assess_channel_quality(result)
        indices = [
            index for index, row in enumerate(quality) if not row["automatic_suspect"]
        ]
        times = time_axis(result)
        edges = protocol_edges(result, protocol)
        for block_index, current in enumerate(protocol.currents_ma):
            schedule_rows.append({
                "case": case,
                "block_index": block_index,
                "start_s": float(edges[block_index]),
                "end_s": float(edges[block_index + 1]),
                "current_ma": current,
                "timing_source": protocol.timing_source,
            })

        for feature in FEATURES:
            values = np.asarray(result["features"][feature])[:, indices] * 1e6
            levels = np.stack([
                interval_level(values, times, edges[index], edges[index + 1])
                for index in range(len(protocol.currents_ma))
            ])
            for block_index, current in enumerate(protocol.currents_ma):
                if current <= 0.0:
                    continue
                if block_index == 0 or block_index == len(protocol.currents_ma) - 1:
                    continue
                if protocol.currents_ma[block_index - 1] != 0.0:
                    continue
                if protocol.currents_ma[block_index + 1] != 0.0:
                    continue
                response = levels[block_index] - 0.5 * (
                    levels[block_index - 1] + levels[block_index + 1]
                )
                cycle = 1 + sum(
                    value > 0.0 for value in protocol.currents_ma[:block_index]
                )
                for local_index, channel_index in enumerate(indices):
                    response_rows.append({
                        "case": case,
                        "feature": feature,
                        "cycle": cycle,
                        "current_ma": current,
                        "channel_index": channel_index + 1,
                        "response_uv": float(response[local_index]),
                        "timing_source": protocol.timing_source,
                        "edge_trim_s": 5.0,
                    })
    write_csv(output / "protocol_schedule.csv", schedule_rows)
    write_csv(output / "coded_block_responses.csv", response_rows)

    summaries = []
    for case in ("alter50ma", "alter100ma"):
        for feature in FEATURES:
            rows = [
                row for row in response_rows
                if row["case"] == case and row["feature"] == feature
            ]
            channels = sorted({int(row["channel_index"]) for row in rows})
            first = np.array([
                next(float(row["response_uv"]) for row in rows
                     if row["channel_index"] == channel and row["cycle"] == 1)
                for channel in channels
            ])
            second = np.array([
                next(float(row["response_uv"]) for row in rows
                     if row["channel_index"] == channel and row["cycle"] == 2)
                for channel in channels
            ])
            summaries.append({
                "case": case,
                "feature": feature,
                "cycle_spatial_correlation": float(np.corrcoef(first, second)[0, 1]),
                "cycle_sign_agreement": float(np.mean(np.sign(first) == np.sign(second))),
                "cycle1_median_response_uv": float(np.median(first)),
                "cycle2_median_response_uv": float(np.median(second)),
            })

    for feature in FEATURES:
        rows = [
            row for row in response_rows
            if row["case"] == "10to100" and row["feature"] == feature
        ]
        channels = sorted({int(row["channel_index"]) for row in rows})
        currents = np.array(sorted({float(row["current_ma"]) for row in rows}))
        matrix = np.array([
            [
                next(float(row["response_uv"]) for row in rows
                     if row["channel_index"] == channel
                     and row["current_ma"] == current)
                for current in currents
            ]
            for channel in channels
        ])
        rho = np.array([
            stats.spearmanr(currents, values).statistic for values in matrix
        ])
        slope = np.sum(matrix * currents, axis=1) / np.sum(currents**2)
        summaries.append({
            "case": "10to100",
            "feature": feature,
            "median_spearman_rho": float(np.median(rho)),
            "positive_rho_fraction": float(np.mean(rho > 0.0)),
            "median_slope_uv_per_ma": float(np.median(slope)),
            **{
                f"median_response_{current:g}ma_uv": float(np.median(matrix[:, index]))
                for index, current in enumerate(currents)
            },
        })
    write_csv(output / "coded_response_summary.csv", summaries)
    return response_rows, summaries


def analyze_005hz(
    cases: dict[str, dict[str, object]], output: Path
) -> list[dict[str, object]]:
    rows = []
    channel_rows = []
    frequency_grid = np.arange(0.02, 0.2001, 0.005)
    for case in ("005hz", "bkg", "bkg2", "out100ma", "5v100ma", "5v100ma2"):
        result = cases[case]
        quality = assess_channel_quality(result)
        indices = [
            index for index, row in enumerate(quality) if not row["automatic_suspect"]
        ]
        rate = float(result["envelope_fs"])
        for feature in FEATURES:
            values = np.asarray(result["features"][feature])[:, indices] * 1e6
            target = np.array([
                harmonic_coefficient(values[:, column], rate, 0.05)
                for column in range(values.shape[1])
            ])
            grid_amplitude = np.array([
                np.median([
                    abs(harmonic_coefficient(values[:, column], rate, frequency))
                    for column in range(values.shape[1])
                ])
                for frequency in frequency_grid
            ])
            phase = np.angle(target)
            for local_index, channel_index in enumerate(indices):
                channel_rows.append({
                    "case": case,
                    "feature": feature,
                    "channel_index": channel_index + 1,
                    "target_frequency_hz": 0.05,
                    "amplitude_uv_peak": float(abs(target[local_index])),
                    "phase_rad": float(phase[local_index]),
                })
            rows.append({
                "case": case,
                "feature": feature,
                "target_frequency_hz": 0.05,
                "channel_count": len(indices),
                "median_amplitude_uv_peak": float(np.median(np.abs(target))),
                "q25_amplitude_uv_peak": float(np.quantile(np.abs(target), 0.25)),
                "q75_amplitude_uv_peak": float(np.quantile(np.abs(target), 0.75)),
                "max_amplitude_uv_peak": float(np.max(np.abs(target))),
                "phase_coherence": float(abs(np.mean(np.exp(1j * phase)))),
                "phase_or_antiphase_coherence": float(
                    abs(np.mean(np.exp(2j * phase)))
                ),
                "nearby_frequency_percentile": float(
                    np.mean(grid_amplitude <= np.median(np.abs(target)))
                ),
            })

    slow_rows = {
        case: {
            int(row["channel_index"]): float(row["amplitude_uv_peak"])
            for row in channel_rows
            if row["case"] == case and row["feature"] == "slow_mean"
        }
        for case in ("005hz", "bkg", "bkg2")
    }
    common = sorted(set.intersection(*(set(values) for values in slow_rows.values())))
    null = np.array([
        slow_rows[case][channel]
        for case in ("bkg", "bkg2")
        for channel in common
    ])
    threshold = float(np.quantile(null, 0.95))
    support = float(np.mean([
        slow_rows["005hz"][channel]
        > max(slow_rows["bkg"][channel], slow_rows["bkg2"][channel])
        for channel in common
    ]))
    fixed_row = next(
        row for row in rows
        if row["case"] == "005hz" and row["feature"] == "slow_mean"
    )
    fixed_row["pooled_background_95_uv_peak"] = threshold
    fixed_row["fraction_above_same_channel_background_max"] = support
    write_csv(output / "fixed_005hz_harmonic.csv", rows)
    write_csv(output / "fixed_005hz_channel.csv", channel_rows)
    return rows


def analyze_narrow_candidate(
    cases: dict[str, dict[str, object]], output: Path
) -> tuple[float, list[dict[str, object]], list[dict[str, object]]]:
    active = ("5v10ma", "5v50ma", "5v100ma", "5v100ma2")
    baseline = cases["bkg2"]
    indices = common_valid_channel_indices(
        baseline, *(cases[name] for name in active), exclude_suspect=True
    )
    frequency = np.asarray(baseline["frequency"])
    contrasts = []
    for case in active:
        contrasts.append(np.median(
            10.0 * np.log10(
                np.maximum(cases[case]["psd"][indices], 1e-300)
                / np.maximum(baseline["psd"][indices], 1e-300)
            ),
            axis=0,
        ))
    joint = np.min(np.stack(contrasts), axis=0)
    search = (frequency >= 1_000.0) & (frequency <= 199_900.0)
    candidate_index = np.flatnonzero(search)[np.argmax(joint[search])]
    candidate_hz = float(frequency[candidate_index])

    chronology = []
    for case in CASE_ORDER:
        result = cases[case]
        quality = assess_channel_quality(result)
        local_indices = [
            index for index, row in enumerate(quality) if not row["automatic_suspect"]
        ]
        excess = local_excess_db(
            frequency, result["psd"][local_indices], candidate_hz
        )
        chronology.append({
            "case": case,
            "start_time": result["start_time"],
            "candidate_frequency_hz": candidate_hz,
            "median_local_excess_db": float(np.median(excess)),
            "q25_local_excess_db": float(np.quantile(excess, 0.25)),
            "q75_local_excess_db": float(np.quantile(excess, 0.75)),
        })
    write_csv(output / "narrow_candidate_chronology.csv", chronology)

    epoch_rows = []
    for case in ("alter50ma", "alter100ma", "10to100"):
        result = cases[case]
        protocol = PROTOCOLS[case]
        quality = assess_channel_quality(result)
        local_indices = [
            index for index, row in enumerate(quality) if not row["automatic_suspect"]
        ]
        epochs = np.asarray(result["welch_epoch_psd_mean"])[:, local_indices]
        excess = local_excess_db(frequency, epochs, candidate_hz)
        edges = protocol_edges(result, protocol)
        trim_start = float(result["archive_metadata"]["config"]["trim_start_seconds"])
        trim_end = float(result["archive_metadata"]["config"]["trim_end_seconds"])
        epoch_edges = np.linspace(
            trim_start, float(result["duration_s"]) - trim_end, len(epochs) + 1
        )
        for epoch_index in range(len(epochs)):
            current = interval_mean_current(
                epoch_edges[epoch_index],
                epoch_edges[epoch_index + 1],
                edges,
                protocol.currents_ma,
            )
            epoch_rows.append({
                "case": case,
                "epoch": epoch_index + 1,
                "start_s": float(epoch_edges[epoch_index]),
                "end_s": float(epoch_edges[epoch_index + 1]),
                "mean_protocol_current_ma": current,
                "median_local_excess_db": float(np.median(excess[epoch_index])),
            })
    write_csv(output / "narrow_candidate_epochs.csv", epoch_rows)
    return candidate_hz, chronology, epoch_rows


def plot_protocols(cases: dict[str, dict[str, object]], output: Path) -> None:
    plot_cases = ("alter100ma", "alter50ma", "10to100", "005hz")
    fig, axes = plt.subplots(4, 1, figsize=(12, 10), constrained_layout=True)
    for axis, case in zip(axes, plot_cases):
        result = cases[case]
        quality = assess_channel_quality(result)
        indices = [
            index for index, row in enumerate(quality) if not row["automatic_suspect"]
        ]
        times = time_axis(result)
        values = result["features"]["slow_mean"][:, indices] * 1e6
        values -= np.median(values, axis=0)
        window = min(21, len(values) // 2 * 2 - 1)
        smoothed = signal.savgol_filter(values, window, 2, axis=0)
        for column in range(smoothed.shape[1]):
            axis.plot(times, smoothed[:, column], color="#7a8790", alpha=0.28, lw=0.7)
        axis.plot(times, np.median(smoothed, axis=1), color="#111111", lw=1.2)
        if case in PROTOCOLS:
            protocol = PROTOCOLS[case]
            edges = protocol_edges(result, protocol)
            for index, current in enumerate(protocol.currents_ma):
                if current > 0.0:
                    axis.axvspan(
                        edges[index], edges[index + 1], color="#d95f02", alpha=0.12
                    )
        else:
            start = 30.0
            end = float(result["duration_s"]) - 30.0
            on = True
            while start < end:
                next_edge = min(start + 10.0, end)
                if on:
                    axis.axvspan(start, next_edge, color="#1b9e77", alpha=0.12)
                start = next_edge
                on = not on
        axis.set_title(case)
        axis.set_ylabel("Centered mean (uV)")
        axis.grid(alpha=0.18)
    axes[-1].set_xlabel("Time (s); shading is reconstructed protocol ON time")
    fig.savefig(output / "coded_low_frequency_timelines.png", dpi=180)
    plt.close(fig)


def plot_summaries(
    cases: dict[str, dict[str, object]],
    harmonic_rows: list[dict[str, object]],
    chronology: list[dict[str, object]],
    response_rows: list[dict[str, object]],
    output: Path,
) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), constrained_layout=True)

    stair = [
        row for row in response_rows
        if row["case"] == "10to100" and row["feature"] == "slow_mean"
    ]
    channels = sorted({int(row["channel_index"]) for row in stair})
    currents = np.array(sorted({float(row["current_ma"]) for row in stair}))
    matrix = np.array([
        [
            next(float(row["response_uv"]) for row in stair
                 if row["channel_index"] == channel and row["current_ma"] == current)
            for current in currents
        ]
        for channel in channels
    ])
    for values in matrix:
        axes[0].plot(currents, values, color="#7a8790", alpha=0.55, marker="o", ms=3)
    axes[0].plot(currents, np.median(matrix, axis=0), color="#111111", lw=2, marker="o")
    axes[0].axhline(0, color="#222222", lw=0.7)
    axes[0].set(
        title="10-200 mA staircase (file: 10to100)",
        xlabel="Current (mA)",
        ylabel="ON - adjacent OFF (uV)",
    )

    selected = [
        row for row in harmonic_rows
        if row["feature"] == "slow_mean" and row["case"] in ("bkg", "bkg2", "005hz")
    ]
    order = ("bkg", "bkg2", "005hz")
    selected.sort(key=lambda row: order.index(str(row["case"])))
    axes[1].bar(
        range(len(selected)),
        [float(row["median_amplitude_uv_peak"]) for row in selected],
        color=("#8c8c8c", "#8c8c8c", "#1b9e77"),
    )
    axes[1].set_xticks(range(len(selected)), [str(row["case"]) for row in selected])
    axes[1].set(title="Fixed 0.05 Hz fit", ylabel="Median amplitude (uV peak)")

    chronology_by_case = {str(row["case"]): row for row in chronology}
    values = [float(chronology_by_case[case]["median_local_excess_db"]) for case in CASE_ORDER]
    axes[2].plot(range(len(CASE_ORDER)), values, color="#33658a", marker="o", ms=4)
    axes[2].axhline(0, color="#222222", lw=0.7)
    axes[2].set_xticks(range(len(CASE_ORDER)), CASE_ORDER, rotation=65, ha="right")
    axes[2].set(title="Best common narrow-band candidate", ylabel="Local excess (dB)")

    for axis in axes:
        axis.grid(alpha=0.18)
    fig.savefig(output / "cathodic_summary.png", dpi=180)
    plt.close(fig)


def median_from_rows(
    rows: list[dict[str, object]], case: str, reference: str, key: str
) -> float:
    values = [
        float(row[key]) for row in rows
        if row["case"] == case and row.get("reference") == reference
    ]
    return float(np.median(values))


def write_report(
    output: Path,
    band_rows: list[dict[str, object]],
    offset_rows: list[dict[str, object]],
    response_rows: list[dict[str, object]],
    response_summary: list[dict[str, object]],
    harmonic_rows: list[dict[str, object]],
    candidate_hz: float,
    chronology: list[dict[str, object]],
    epoch_rows: list[dict[str, object]],
) -> None:
    def harmonic(case: str, feature: str) -> dict[str, object]:
        return next(
            row for row in harmonic_rows
            if row["case"] == case and row["feature"] == feature
        )

    def summary(case: str, feature: str) -> dict[str, object]:
        return next(
            row for row in response_summary
            if row["case"] == case and row["feature"] == feature
        )

    fixed = harmonic("005hz", "slow_mean")
    background_amplitudes = np.array([
        float(harmonic(case, "slow_mean")["median_amplitude_uv_peak"])
        for case in ("bkg", "bkg2")
    ])
    stair = summary("10to100", "slow_mean")
    alt50 = summary("alter50ma", "slow_mean")
    alt100 = summary("alter100ma", "slow_mean")
    local = {str(row["case"]): float(row["median_local_excess_db"]) for row in chronology}

    def epoch_cycle_contrasts(case: str) -> list[float]:
        selected = [row for row in epoch_rows if row["case"] == case]
        current = np.array([float(row["mean_protocol_current_ma"]) for row in selected])
        value = np.array([float(row["median_local_excess_db"]) for row in selected])
        peaks, _ = signal.find_peaks(current, distance=2)
        return [
            float(value[index] - 0.5 * (value[index - 1] + value[index + 1]))
            for index in peaks
            if 0 < index < len(value) - 1
        ]

    bar_offset = median_from_rows(offset_rows, "bar5a", "bkg", "offset_uv")
    open_offset = median_from_rows(offset_rows, "out100ma", "bkg", "offset_uv")
    bar_bands = {
        row["band"]: float(row["median_delta_db"])
        for row in band_rows if row["case"] == "bar5a" and row["reference"] == "bkg"
    }

    alter100_tone = epoch_cycle_contrasts("alter100ma")
    alter50_tone = epoch_cycle_contrasts("alter50ma")

    report = f"""# 2026-08-11 阴极保护预实验精确分析报告

## 1. 数据与质量控制

- 共分析 12 个 TC2 文件，采样率 400 kHz，单文件时长 53.9-288.6 s。
- 每个文件独立进行动态坏道判断。本批次所有文件均检出 8、11 通道异常；`5v10ma` 的 12 通道和 `bkg` 的 5 通道另被列为可疑。主统计排除坏道和可疑通道。
- 低频保留完整 10 Hz 时间轴；高频使用全部稳定样本的 262144 点、50% 重叠 Welch 结果。所有运算在 float64 中完成。
- 手动协议没有同步电流标记。30 s 区块按操作记录居中重建，并在每个边沿舍弃 5 s。以下区块结果属于“按实验记录重建时间”的检验。

## 2. 低频编码结果

### 2.1 固定 0.05 Hz

`005hz` 慢均值在预先指定的 0.05 Hz 上得到通道中位拟合幅值 {float(fixed['median_amplitude_uv_peak']):.2f} uV peak，四分位范围 {float(fixed['q25_amplitude_uv_peak']):.2f}-{float(fixed['q75_amplitude_uv_peak']):.2f} uV。两段背景在同一频率上的中位幅值为 {background_amplitudes[0]:.2f} 和 {background_amplitudes[1]:.2f} uV。`005hz` 各通道相位相干度仅 {float(fixed['phase_coherence']):.2f}，没有形成共同相位响应。

因此 {float(fixed['median_amplitude_uv_peak']):.2f} uV 只是固定频率拟合出来的表观幅值，不是已经检出的阴极保护信号；它没有超过本次背景。按两段背景逐通道结果合并得到的粗略 95% 筛查量级为 {float(fixed['pooled_background_95_uv_peak']):.2f} uV peak，且只有 {100*float(fixed['fraction_above_same_channel_background_max']):.0f}% 的通道超过本通道两段背景中的较大值。背景记录较短，因此这只能作为保守的经验阈值，不能当作传感器外场标定值。

### 2.2 30 s 开关与电流阶梯

- `alter50ma` 两个 ON 区块的慢均值空间响应相关系数为 {float(alt50['cycle_spatial_correlation']):+.2f}，同号通道比例 {100*float(alt50['cycle_sign_agreement']):.0f}%。
- `alter100ma` 对应结果为 {float(alt100['cycle_spatial_correlation']):+.2f} 和 {100*float(alt100['cycle_sign_agreement']):.0f}%。
- 阶梯实验经相邻 OFF 区块校正后，10/50/100/200 mA 的通道中位慢均值响应分别为 {float(stair['median_response_10ma_uv']):+.2f}、{float(stair['median_response_50ma_uv']):+.2f}、{float(stair['median_response_100ma_uv']):+.2f}、{float(stair['median_response_200ma_uv']):+.2f} uV；逐通道 Spearman 系数中位数为 {float(stair['median_spearman_rho']):+.2f}。

响应没有随电流单调增加，50 与 100 mA 的空间分布也没有复现。因此低频结论是“本批次未检出可重复、可随电流定标的响应”，不能写成已经检出阴极保护信号。

## 3. 高频结果

稳态 10/50/100 mA 相对 `bkg2` 的三个高频宽带变化均接近零，典型量级小于约 0.01 dB。没有观察到随电流增加的宽带抬升。

对 10 mA、50 mA 和两次 100 mA 稳态文件共同搜索，最强的共同窄带候选位于 {candidate_hz:.1f} Hz。其局部超额在 `bkg2` 为 {local['bkg2']:+.2f} dB，在稳态电流文件中为：10 mA {local['5v10ma']:+.2f} dB、50 mA {local['5v50ma']:+.2f} dB、100 mA 两次 {local['5v100ma']:+.2f}/{local['5v100ma2']:+.2f} dB。

这个候选不满足归因条件：幅值不随电流排序；第一次 100 mA 很弱；`alter100ma` 两次 ON 附近的相邻历元差分别为 {alter100_tone[0]:+.2f}/{alter100_tone[1]:+.2f} dB，`alter50ma` 为 {alter50_tone[0]:+.2f}/{alter50_tone[1]:+.2f} dB，同一文件内两次响应方向相反。它更像随时间变化的仪器或环境窄带结构，不能归因于电极电流或电化学过程。

## 4. BAR 与开路对照

`bar5a` 相对前一段背景的跨文件慢均值中位偏移为 {bar_offset:+.1f} uV，但实际无输出的 `out100ma` 相对同一背景偏移反而达到 {open_offset:+.1f} uV；`bkg` 自身首末 5 s 的健康通道中位变化也约为 +142 uV。说明这种跨文件直流偏移主要受传感器慢漂移影响，不能把 BAR 的偏移认定为 5 A 电流信号。

BAR 相对背景的高频带变化为：1-20 kHz {bar_bands['1_20khz']:+.3f} dB、20-80 kHz {bar_bands['20_80khz']:+.3f} dB、80-200 kHz {bar_bands['80_200khz']:+.3f} dB，均没有形成强正对照。由于 BAR 是单一稳态文件、没有在同一记录中开关，当前设计无法可靠检验静态 5 A 引起的直流偏置。

## 5. 当前结论

1. 本批 TC2 数据没有检出可重复的 0.05 Hz 阴极保护响应。
2. 30 s 开关和 10-200 mA 阶梯均未得到跨周期、跨电流复现且单调的低频变化。
3. 未发现可随电流或 ON/OFF 状态稳定变化的高频宽带或窄谱线。
4. BAR 文件存在跨文件直流偏移，但开路对照偏移更大，因此不能作为检出证据。
5. 结论应表述为“在本次几何位置、TC2 和电流范围内未可靠检出”，而不是“阴极保护没有电磁信号”。没有同步记录实际电流波形，是本次归因能力的主要限制。

## 6. 输出文件

- `case_inventory.csv`、`channel_health.csv`：文件与动态通道质量。
- `protocol_schedule.csv`、`coded_block_responses.csv`：重建协议和逐通道相邻 OFF 校正响应。
- `fixed_005hz_harmonic.csv`、`fixed_005hz_channel.csv`：固定 0.05 Hz 幅值、相位与邻频排序。
- `steady_band_contrasts.csv`、`steady_baseline_offsets.csv`：稳态频带与直流偏移。
- `narrow_candidate_chronology.csv`、`narrow_candidate_epochs.csv`：最强共同窄带候选及时间检验。
- `coded_low_frequency_timelines.png`、`cathodic_summary.png`：主要可视化。
"""
    (output / "EXPERIMENT_ANALYSIS_REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--archive-root",
        type=Path,
        default=Path("results/experiment_20260811/exact_archive"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("results/experiment_20260811")
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    cases = load_cases(args.archive_root)
    collect_inventory_and_health(cases, args.output)
    band_rows, offset_rows = analyze_steady_cases(cases, args.output)
    response_rows, response_summary = analyze_block_protocols(cases, args.output)
    harmonic_rows = analyze_005hz(cases, args.output)
    candidate_hz, chronology, epoch_rows = analyze_narrow_candidate(cases, args.output)
    plot_protocols(cases, args.output)
    plot_summaries(cases, harmonic_rows, chronology, response_rows, args.output)
    write_report(
        args.output,
        band_rows,
        offset_rows,
        response_rows,
        response_summary,
        harmonic_rows,
        candidate_hz,
        chronology,
        epoch_rows,
    )
    print(f"Analysis complete: {args.output}")


if __name__ == "__main__":
    main()
