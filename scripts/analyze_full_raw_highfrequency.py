"""Complete full-record high-frequency checks from the original TDMS files.

The exact archives retain full-coverage PSD and band-power summaries but only
three raw 1 s snippets.  This script samples the complete stable interval of
every original record so cross-channel phase, bicoherence repeatability and
carrier-comb evidence can be checked without treating three snippets as the
whole acquisition.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from nptdms import TdmsFile
from scipy import fft as sp_fft
from scipy import signal

from scripts.analyze_pre_electrochemical_dynamics import case_fields
from scripts.mentor_method_common import (
    all_cases,
    generic_matched_contrasts,
    healthy_indices,
    load_health_table,
    stable_seed,
    write_frame,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / 'analysis/mentor_aligned_raw_completion_v3/full_raw_highfrequency'
DEFAULT_RAW_ROOT = Path(r"E:\Lab\raw")
BANDS = {
    "2_20khz": (2_000.0, 20_000.0),
    "20_80khz": (20_000.0, 80_000.0),
    "80_200khz": (80_000.0, 199_000.0),
}


def json_value(value: object) -> object:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return [json_value(item) for item in value.tolist()]
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    return value


def raw_file_index(root: Path) -> dict[str, Path]:
    paths = sorted(root.rglob("*.tdms"))
    result: dict[str, Path] = {}
    duplicates: set[str] = set()
    for path in paths:
        if path.name in result:
            duplicates.add(path.name)
        else:
            result[path.name] = path
    for name in duplicates:
        result.pop(name, None)
    return result


def archive_source_name(archive: Path) -> str:
    metadata = json.loads((archive / "metadata.json").read_text(encoding="utf-8"))
    source = metadata.get("source_tdms_path", metadata.get("source_path"))
    if not source:
        raise KeyError(f"No source TDMS path in {archive / 'metadata.json'}")
    return Path(str(source)).name


def sample_windows(
    tdms_path: Path,
    selected_channels: np.ndarray,
    archive: Path,
    window_count: int,
    window_samples: int,
) -> tuple[np.ndarray, np.ndarray, float, list[str]]:
    metadata = json.loads((archive / "metadata.json").read_text(encoding="utf-8"))
    config = metadata.get("config", {})
    with TdmsFile.open(tdms_path) as tdms:
        group = tdms.groups()[0]
        channels = group.channels()
        sample_count = len(channels[0])
        sample_rate = 1.0 / float(channels[0].properties["wf_increment"])
        trim_start = int(round(float(config.get("trim_start_seconds", 0.0)) * sample_rate))
        trim_end = int(round(float(config.get("trim_end_seconds", 0.0)) * sample_rate))
        first = max(0, trim_start)
        last = sample_count - trim_end - window_samples
        if last <= first:
            first = 0
            last = sample_count - window_samples
        count = min(window_count, max(8, (last - first) // max(window_samples, 1)))
        starts = np.linspace(first, last, count, dtype=np.int64)
        values = np.empty(
            (len(starts), window_samples, len(selected_channels)), dtype=np.float32
        )
        for channel_position, channel_index in enumerate(selected_channels):
            channel = channels[int(channel_index)]
            for window_index, start in enumerate(starts):
                piece = np.asarray(
                    channel[int(start):int(start) + window_samples], dtype=np.float32
                )
                if len(piece) != window_samples:
                    raise RuntimeError(
                        f"Short TDMS slice in {tdms_path}: {len(piece)} != {window_samples}"
                    )
                values[window_index, :, channel_position] = piece
        names = [channels[int(index)].name for index in selected_channels]
    return values, starts / sample_rate, float(sample_rate), names


def one_sided_psd(spectra: np.ndarray, sample_rate: float, window: np.ndarray) -> np.ndarray:
    power = np.abs(spectra) ** 2 / (sample_rate * float(np.sum(window * window)))
    power[:, 1:-1] *= 2.0
    return np.asarray(power, dtype=np.float64)


def band_summary(
    frequency: np.ndarray, values: np.ndarray, low: float, high: float
) -> tuple[float, float, float]:
    use = (frequency >= low) & (frequency < high)
    selected = values[use]
    if not np.any(use) or not np.any(np.isfinite(selected)):
        return np.nan, np.nan, np.nan
    maximum = int(np.nanargmax(selected))
    return (
        float(np.nanmedian(selected)),
        float(np.nanmax(selected)),
        float(frequency[use][maximum]),
    )


def pair_coherence_phase_curves(spectra: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    coherence_rows = []
    phase_rows = []
    for first in range(spectra.shape[2]):
        for second in range(first + 1, spectra.shape[2]):
            cross = spectra[:, :, first] * np.conj(spectra[:, :, second])
            cross_mean = np.mean(cross, axis=0)
            denominator = (
                np.mean(np.abs(spectra[:, :, first]) ** 2, axis=0)
                * np.mean(np.abs(spectra[:, :, second]) ** 2, axis=0)
            )
            coherence_rows.append(
                np.abs(cross_mean) ** 2 / np.maximum(denominator, 1e-30)
            )
            phase_rows.append(np.abs(np.mean(
                cross / np.maximum(np.abs(cross), 1e-30), axis=0
            )))
    return (
        np.median(np.asarray(coherence_rows), axis=0),
        np.median(np.asarray(phase_rows), axis=0),
    )


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


def scalar_bicoherence(
    windows: np.ndarray, sample_rate: float, seed: int,
    nperseg: int = 4096, grid_step_bins: int = 32, surrogate_count: int = 19,
) -> dict[str, float]:
    fft_rows = []
    owners = []
    taper = signal.windows.hann(nperseg, sym=False).astype(np.float32)
    step = nperseg // 2
    for owner, row in enumerate(windows):
        for start in range(0, len(row) - nperseg + 1, step):
            part = signal.detrend(row[start:start + nperseg], type="linear")
            fft_rows.append(sp_fft.rfft(part * taper))
            owners.append(owner)
    spectra = np.asarray(fft_rows, dtype=np.complex64)
    owners_array = np.asarray(owners, dtype=int)
    maximum_bin = nperseg // 2
    grid = np.arange(grid_step_bins, maximum_bin, grid_step_bins, dtype=int)
    first_grid, second_grid = np.meshgrid(grid, grid, indexing="ij")
    use = (first_grid <= second_grid) & (first_grid + second_grid <= maximum_bin)
    first_bins = first_grid[use]
    second_bins = second_grid[use]
    observed = bicoherence_values(spectra, first_bins, second_bins)
    best = int(np.nanargmax(observed))
    resolution = sample_rate / nperseg

    epoch_maxima = []
    epoch_sum_frequencies = []
    window_count = len(windows)
    for epoch_indices in np.array_split(np.arange(window_count), 8):
        selected = np.isin(owners_array, epoch_indices)
        if np.sum(selected) < 8:
            continue
        epoch_values = bicoherence_values(
            spectra[selected], first_bins, second_bins
        )
        epoch_best = int(np.nanargmax(epoch_values))
        epoch_maxima.append(float(epoch_values[epoch_best]))
        epoch_sum_frequencies.append(float(
            (first_bins[epoch_best] + second_bins[epoch_best]) * resolution
        ))

    rng = np.random.default_rng(seed)
    null_maxima = []
    for _ in range(surrogate_count):
        phases = rng.uniform(-np.pi, np.pi, spectra.shape)
        phases[:, 0] = 0.0
        phases[:, -1] = 0.0
        null_maxima.append(float(np.max(bicoherence_values(
            spectra, first_bins, second_bins, phases
        ))))
    null = np.asarray(null_maxima, dtype=float)
    pooled_sum = float((first_bins[best] + second_bins[best]) * resolution)
    epoch_sum = np.asarray(epoch_sum_frequencies, dtype=float)
    tolerance = grid_step_bins * resolution * 2.0
    return {
        "full_bicoherence_max": float(observed[best]),
        "full_bicoherence_q99": float(np.percentile(observed, 99)),
        "full_bicoherence_f1_hz": float(first_bins[best] * resolution),
        "full_bicoherence_f2_hz": float(second_bins[best] * resolution),
        "full_bicoherence_sum_hz": pooled_sum,
        "full_bicoherence_surrogate_p": float(
            (np.sum(null >= observed[best]) + 1) / (len(null) + 1)
        ),
        "full_bicoherence_null_q95": float(np.percentile(null, 95)),
        "full_bicoherence_epoch_max_median": float(
            np.median(epoch_maxima) if epoch_maxima else np.nan
        ),
        "full_bicoherence_epoch_max_cv": float(
            np.std(epoch_maxima) / max(np.mean(epoch_maxima), 1e-15)
            if epoch_maxima else np.nan
        ),
        "full_bicoherence_epoch_sum_frequency_range_hz": float(
            np.ptp(epoch_sum) if len(epoch_sum) else np.nan
        ),
        "full_bicoherence_epoch_peak_repeat_fraction": float(
            np.mean(np.abs(epoch_sum - pooled_sum) <= tolerance)
            if len(epoch_sum) else np.nan
        ),
        "full_bicoherence_fft_segment_count": int(len(spectra)),
        "full_bicoherence_window_epoch_count": int(len(epoch_maxima)),
    }


def comb_metrics(
    frequency: np.ndarray, power_windows: np.ndarray, carrier_hz: float,
) -> tuple[float, float, int]:
    resolution = float(frequency[1] - frequency[0])
    harmonics = np.arange(carrier_hz, frequency[-1] - 1_000.0, carrier_hz)
    contrasts = []
    for harmonic in harmonics:
        center = int(round(harmonic / resolution))
        if center < 24 or center + 24 >= power_windows.shape[1]:
            continue
        line = np.max(power_windows[:, center - 1:center + 2], axis=1)
        floor = np.median(np.concatenate((
            power_windows[:, center - 24:center - 6],
            power_windows[:, center + 7:center + 25],
        ), axis=1), axis=1)
        contrasts.append(10.0 * np.log10(np.maximum(line, 1e-300) / np.maximum(floor, 1e-300)))
    if not contrasts:
        return np.nan, np.nan, 0
    matrix = np.stack(contrasts, axis=1)
    per_window = np.median(matrix, axis=1)
    return float(np.median(per_window)), float(np.mean(per_window >= 6.0)), matrix.shape[1]


def narrow_peak_rows(
    case_id: str, frequency: np.ndarray, power_windows: np.ndarray,
    maximum_count: int = 12,
) -> list[dict[str, float | str]]:
    mean_db = 10.0 * np.log10(np.maximum(np.mean(power_windows, axis=0), 1e-300))
    use_indices = np.flatnonzero((frequency >= 20_000.0) & (frequency <= 199_000.0))
    local_peaks, properties = signal.find_peaks(
        mean_db[use_indices], prominence=2.0, distance=3
    )
    if not len(local_peaks):
        return []
    order = np.argsort(properties["prominences"])[::-1][:maximum_count]
    rows = []
    for rank, selected in enumerate(order, start=1):
        index = int(use_indices[local_peaks[selected]])
        low = max(0, index - 20)
        high = min(power_windows.shape[1], index + 21)
        floor_indices = np.r_[np.arange(low, max(low, index - 4)),
                              np.arange(min(high, index + 5), high)]
        line = np.max(power_windows[:, max(0, index - 1):index + 2], axis=1)
        floor = np.median(power_windows[:, floor_indices], axis=1)
        contrast = 10.0 * np.log10(np.maximum(line, 1e-300) / np.maximum(floor, 1e-300))
        rows.append({
            "case_id": case_id,
            "peak_rank": rank,
            "frequency_hz": float(frequency[index]),
            "mean_prominence_db": float(properties["prominences"][selected]),
            "window_contrast_db_median": float(np.median(contrast)),
            "window_contrast_db_q10": float(np.percentile(contrast, 10)),
            "occupancy_contrast_ge_6db": float(np.mean(contrast >= 6.0)),
        })
    return rows


def analyze_case(
    case, raw_path: Path, health: pd.DataFrame, window_count: int,
    window_samples: int,
) -> dict[str, object]:
    selected = healthy_indices(case, health)
    windows, window_times, sample_rate, channel_names = sample_windows(
        raw_path, selected, case.archive, window_count, window_samples
    )
    centered = windows - np.mean(windows, axis=1, keepdims=True)
    channel_scale = np.std(centered.reshape(-1, centered.shape[-1]), axis=0)
    standardized = centered / np.maximum(channel_scale[None, None, :], 1e-12)
    covariance = np.einsum("wsc,wsd->cd", standardized, standardized, optimize=True)
    covariance /= float(standardized.shape[0] * standardized.shape[1])
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    weights = eigenvectors[:, -1]
    if np.sum(weights) < 0.0:
        weights = -weights
    common_windows = np.einsum("wsc,c->ws", standardized, weights, optimize=True)

    taper = signal.windows.hann(window_samples, sym=False).astype(np.float32)
    spectra = sp_fft.rfft(
        standardized * taper[None, :, None], axis=1, workers=-1
    ).astype(np.complex64, copy=False)
    frequency = sp_fft.rfftfreq(window_samples, 1.0 / sample_rate)
    power = one_sided_psd(spectra, sample_rate, taper)
    common_spectra = sp_fft.rfft(
        common_windows * taper[None, :], axis=1, workers=-1
    ).astype(np.complex64, copy=False)
    common_power = one_sided_psd(common_spectra, sample_rate, taper)

    median_coherence, median_phase_locking = pair_coherence_phase_curves(spectra)
    epoch_curves = [
        pair_coherence_phase_curves(spectra[indices])
        for indices in np.array_split(np.arange(len(spectra)), 8)
        if len(indices) >= 6
    ]

    result: dict[str, object] = {
        **case_fields(case),
        "raw_tdms_path": str(raw_path),
        "raw_window_count": len(windows),
        "raw_window_samples": window_samples,
        "raw_window_seconds": window_samples / sample_rate,
        "sample_rate_hz": sample_rate,
        "stable_span_sampled_seconds": float(window_times[-1] - window_times[0]),
        "healthy_channel_count": len(selected),
        "healthy_channel_indices_1based": (selected + 1).tolist(),
        "healthy_channel_names": channel_names,
        "raw_pc1_variance_fraction": float(
            eigenvalues[-1] / max(np.sum(eigenvalues), 1e-15)
        ),
    }
    epoch_rows: list[dict[str, object]] = []
    for band_name, (low, high) in BANDS.items():
        use = (frequency >= low) & (frequency < high)
        integrated = np.trapezoid(common_power[:, use], frequency[use], axis=1)
        result[f"common_bandpower_{band_name}_db_median"] = float(
            10.0 * np.log10(max(np.median(integrated), 1e-300))
        )
        result[f"common_bandpower_{band_name}_db_iqr"] = float(
            np.ptp(np.percentile(10.0 * np.log10(np.maximum(integrated, 1e-300)), [25, 75]))
        )
        coherence_median, coherence_max, coherence_frequency = band_summary(
            frequency, median_coherence, low, high
        )
        phase_median, phase_max, phase_frequency = band_summary(
            frequency, median_phase_locking, low, high
        )
        result[f"pair_coherence_{band_name}_median"] = coherence_median
        result[f"pair_coherence_{band_name}_max"] = coherence_max
        result[f"pair_coherence_{band_name}_max_frequency_hz"] = coherence_frequency
        result[f"pair_phase_locking_{band_name}_median"] = phase_median
        result[f"pair_phase_locking_{band_name}_max"] = phase_max
        result[f"pair_phase_locking_{band_name}_max_frequency_hz"] = phase_frequency
        epoch_coherence = np.asarray([
            band_summary(frequency, curves[0], low, high)[0]
            for curves in epoch_curves
        ])
        epoch_phase = np.asarray([
            band_summary(frequency, curves[1], low, high)[0]
            for curves in epoch_curves
        ])
        result[f"pair_coherence_{band_name}_epoch_median"] = float(
            np.median(epoch_coherence)
        )
        result[f"pair_coherence_{band_name}_epoch_iqr"] = float(
            np.percentile(epoch_coherence, 75) - np.percentile(epoch_coherence, 25)
        )
        result[f"pair_phase_locking_{band_name}_epoch_median"] = float(
            np.median(epoch_phase)
        )
        result[f"pair_phase_locking_{band_name}_epoch_iqr"] = float(
            np.percentile(epoch_phase, 75) - np.percentile(epoch_phase, 25)
        )
        for epoch_index, (coherence_value, phase_value) in enumerate(
            zip(epoch_coherence, epoch_phase), start=1
        ):
            epoch_rows.append({
                "case_id": case.case_id,
                "epoch_index": epoch_index,
                "band_name": band_name,
                "pair_coherence_median": float(coherence_value),
                "pair_phase_locking_median": float(phase_value),
            })

    for carrier_khz in (4.0, 8.0, 12.0):
        score, occupancy, harmonic_count = comb_metrics(
            frequency, common_power, carrier_khz * 1_000.0
        )
        token = f"{int(carrier_khz)}khz"
        result[f"carrier_comb_{token}_score_db"] = score
        result[f"carrier_comb_{token}_occupancy_ge_6db"] = occupancy
        result[f"carrier_comb_{token}_harmonic_count"] = harmonic_count

    configured = case.carrier_khz
    if configured is not None:
        configured_score = float(result[f"carrier_comb_{int(configured)}khz_score_db"])
        alternatives = [
            float(result[f"carrier_comb_{int(item)}khz_score_db"])
            for item in (4.0, 8.0, 12.0) if item != configured
        ]
        result["configured_carrier_comb_margin_db"] = configured_score - max(alternatives)
        scores = {
            item: float(result[f"carrier_comb_{int(item)}khz_score_db"])
            for item in (4.0, 8.0, 12.0)
        }
        result["carrier_comb_predicted_khz"] = max(scores, key=scores.get)
        result["carrier_comb_prediction_correct"] = bool(
            result["carrier_comb_predicted_khz"] == configured
        )
    else:
        result["configured_carrier_comb_margin_db"] = np.nan
        result["carrier_comb_predicted_khz"] = np.nan
        result["carrier_comb_prediction_correct"] = np.nan

    result.update(scalar_bicoherence(
        common_windows, sample_rate, stable_seed(case.case_id, "full_raw_bicoherence")
    ))
    result["peaks"] = narrow_peak_rows(case.case_id, frequency, common_power)
    result["epochs"] = epoch_rows
    return result


def build_contrasts(cases, features: pd.DataFrame) -> pd.DataFrame:
    columns = [
        column for column in features.columns
        if column.startswith(("common_bandpower_", "pair_coherence_", "pair_phase_locking_", "carrier_comb_", "full_bicoherence_"))
        and pd.api.types.is_numeric_dtype(features[column])
        and not column.endswith(("_count", "_frequency_hz", "_harmonic_count"))
    ]
    return generic_matched_contrasts(cases, features, columns, [])


def plot_summary(features: pd.DataFrame, output: Path) -> None:
    later = features[features["dataset"].astype(str) == "20260806"].copy()
    if later.empty:
        return
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    condition_order = ["background", "vfd_stop", "30hz", "50hz", "run"]
    data = [
        later.loc[later["condition"] == condition, "pair_coherence_80_200khz_median"].dropna()
        for condition in condition_order
    ]
    axes[0].boxplot(data, tick_labels=condition_order, showfliers=False)
    axes[0].set_ylabel("Median channel-pair coherence")
    axes[0].set_title("80-200 kHz cross-channel coherence")
    margins = later.dropna(subset=["configured_carrier_comb_margin_db"])
    axes[1].axhline(0.0, color="#555555", linewidth=0.8)
    axes[1].scatter(
        margins["carrier_khz"], margins["configured_carrier_comb_margin_db"],
        c=margins["detector"].map({"tc1": "#3976a8", "tc2": "#bf5b45"}),
        s=55,
    )
    axes[1].set_xticks([4, 8, 12])
    axes[1].set_xlabel("Configured carrier (kHz)")
    axes[1].set_ylabel("Configured comb score margin (dB)")
    axes[1].set_title("Does the harmonic comb follow the setting?")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--window-count", type=int, default=96)
    parser.add_argument("--window-samples", type=int, default=16_384)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    case_output = args.output / "cases"
    case_output.mkdir(parents=True, exist_ok=True)
    cases = all_cases()
    if args.limit:
        cases = cases[:args.limit]
    health = load_health_table()
    raw_index = raw_file_index(args.raw_root)
    missing = [case.case_id for case in cases if archive_source_name(case.archive) not in raw_index]
    if missing:
        raise FileNotFoundError(f"Original TDMS not found for: {missing}")

    for index, case in enumerate(cases, start=1):
        path = case_output / f"{case.case_id}.json"
        if path.exists() and not args.force:
            print(f"[{index:02d}/{len(cases):02d}] cached {case.case_id}", flush=True)
            continue
        source_name = archive_source_name(case.archive)
        print(f"[{index:02d}/{len(cases):02d}] {case.case_id}: {raw_index[source_name]}", flush=True)
        result = analyze_case(
            case, raw_index[source_name], health,
            window_count=args.window_count, window_samples=args.window_samples,
        )
        path.write_text(
            json.dumps(json_value(result), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    payloads = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(case_output.glob("*.json"))
        if any(path.stem == case.case_id for case in cases)
    ]
    peak_rows = []
    epoch_rows = []
    feature_rows = []
    for payload in payloads:
        peak_rows.extend(payload.pop("peaks", []))
        epoch_rows.extend(payload.pop("epochs", []))
        feature_rows.append(payload)
    features = write_frame(args.output / "full_raw_highfrequency_features.csv", feature_rows)
    write_frame(args.output / "full_raw_narrow_peak_persistence.csv", peak_rows)
    write_frame(args.output / "full_raw_epoch_features.csv", epoch_rows)
    contrasts = build_contrasts(cases, features)
    write_frame(args.output / "full_raw_highfrequency_matched_contrasts.csv", contrasts)
    plot_summary(features, args.output / "full_raw_highfrequency_summary.png")
    manifest = {
        "analysis": "full_raw_highfrequency_completion",
        "case_count": len(features),
        "raw_root": str(args.raw_root),
        "window_count_per_file": args.window_count,
        "window_samples": args.window_samples,
        "sampling_strategy": "uniform windows across complete stable interval",
        "dynamic_bad_channel_source": str(
            PROJECT_ROOT / 'analysis/mentor_aligned_pre_electrochemical_v1/channel_health_dynamic.csv'
        ),
        "limitations": [
            "Uniform windows cover the full interval but are not every raw sample.",
            "Bicoherence uses a coarse 3.125 kHz interaction grid for tractability.",
        ],
    }
    (args.output / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Output: {args.output}", flush=True)


if __name__ == "__main__":
    main()
