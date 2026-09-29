"""Within-record ON/OFF high-frequency analysis for old cathodic experiments."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from nptdms import TdmsFile
from scipy import fft as sp_fft
from scipy import signal, stats

from scripts.analyze_full_raw_highfrequency import (
    one_sided_psd,
    pair_coherence_phase_curves,
)
from scripts.channel_quality import assess_channel_quality
from scripts.exact_tdms_archive import load_exact_archive


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIRST_ARCHIVE_ROOT = PROJECT_ROOT / "results/experiment_20260811/exact_archive"
SECOND_ARCHIVE_ROOT = PROJECT_ROOT / "results/experiment_20260811_2/exact_archive"
DEFAULT_OUTPUT = PROJECT_ROOT / "results/cathodic_mentor_methods_v1/high_frequency"
BANDS = {
    "2_20khz": (2_000.0, 20_000.0),
    "20_80khz": (20_000.0, 80_000.0),
    "80_200khz": (80_000.0, 199_000.0),
}
WINDOW_SAMPLES = 16_384
WINDOWS_PER_STATE = 4
TIMING_OFFSETS_S = (-1.0, 0.0, 1.0)


@dataclass(frozen=True)
class CaseSpec:
    case: str
    archive: Path
    raw_path: Path
    current_ma: float
    kind: str
    repeat: int
    cycles: int
    start_s: float
    period_s: float
    duty: float = 0.5


def archive_for(root: Path, case: str) -> Path:
    matches = sorted(root.glob(f"{case}__*"))
    if len(matches) != 1:
        raise ValueError(f"Expected one archive for {case}, found {len(matches)}")
    return matches[0]


def resolve_raw_path(source: object) -> Path:
    path = Path(str(source))
    if path.is_file():
        return path
    parts = path.parts
    if len(parts) >= 3 and parts[1:3] == ("Lab", "raw"):
        relocated = Path("E:/", *parts[1:])
        if relocated.is_file():
            return relocated
    raise FileNotFoundError(path)


def build_specs() -> list[CaseSpec]:
    info = {
        "opensvnear": (0.0, "open_control", 1, 8),
        "cp200near": (200.0, "closed_circuit", 1, 12),
        "cp500near": (500.0, "closed_circuit", 1, 12),
        "cp1000near": (1000.0, "closed_circuit", 1, 12),
        "cp1000near2": (1000.0, "closed_circuit", 2, 12),
        "cp3000near": (3000.0, "closed_circuit", 1, 12),
        "cp3000near2": (3000.0, "closed_circuit", 2, 12),
    }
    first_archive = archive_for(FIRST_ARCHIVE_ROOT, "005hz")
    first_loaded = load_exact_archive(first_archive)
    first_source = first_loaded["archive_metadata"].get("source_path")
    if first_source is None:
        raise KeyError("No TDMS source path for 005hz")
    first_period = 20.0
    first_cycles = 4
    specs = [CaseSpec(
        "005hz", first_archive, resolve_raw_path(first_source), 100.0,
        "closed_circuit", 1, first_cycles,
        0.5 * (float(first_loaded["duration_s"]) - first_cycles * first_period),
        first_period,
    )]
    for case, (current, kind, repeat, cycles) in info.items():
        archive = archive_for(SECOND_ARCHIVE_ROOT, case)
        loaded = load_exact_archive(archive)
        metadata = loaded["archive_metadata"]
        source = metadata.get("source_path", metadata.get("source_tdms_path"))
        if source is None:
            raise KeyError(f"No TDMS source path for {case}")
        raw_path = resolve_raw_path(source)
        period = (float(loaded["duration_s"]) - 60.0) / cycles
        specs.append(CaseSpec(
            case, archive, raw_path, current, kind, repeat, cycles, 30.0, period,
        ))
    return specs


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


def protocol_window_times(spec: CaseSpec) -> list[dict[str, object]]:
    rows = []
    state_duration = spec.period_s * spec.duty
    margin = min(0.8, 0.18 * state_duration)
    window_seconds = WINDOW_SAMPLES / 400_000.0
    for timing_offset in TIMING_OFFSETS_S:
        start = spec.start_s + timing_offset
        for cycle in range(spec.cycles):
            cycle_start = start + cycle * spec.period_s
            for state_index, state in enumerate(("on", "off")):
                first = cycle_start + state_index * state_duration + margin
                last = cycle_start + (state_index + 1) * state_duration - margin - window_seconds
                if last <= first:
                    centers = np.asarray([(first + last) * 0.5])
                else:
                    centers = np.linspace(first, last, WINDOWS_PER_STATE)
                for window_index, time_s in enumerate(centers):
                    rows.append({
                        "timing_offset_s": timing_offset,
                        "cycle_index": cycle + 1,
                        "state": state,
                        "window_index": window_index + 1,
                        "start_time_s": float(time_s),
                    })
    return rows


def read_windows(
    spec: CaseSpec, selected: np.ndarray,
) -> tuple[np.ndarray, pd.DataFrame, float, list[str]]:
    schedule = pd.DataFrame(protocol_window_times(spec))
    with TdmsFile.open(spec.raw_path) as tdms:
        channels = tdms.groups()[0].channels()
        sample_rate = 1.0 / float(channels[0].properties["wf_increment"])
        starts = np.round(schedule["start_time_s"].to_numpy() * sample_rate).astype(np.int64)
        sample_count = len(channels[0])
        if np.any(starts < 0) or np.any(starts + WINDOW_SAMPLES > sample_count):
            raise RuntimeError(f"Protocol windows exceed acquisition in {spec.case}")
        values = np.empty(
            (len(starts), WINDOW_SAMPLES, len(selected)), dtype=np.float32
        )
        for channel_position, channel_index in enumerate(selected):
            channel = channels[int(channel_index)]
            for window_index, start in enumerate(starts):
                values[window_index, :, channel_position] = np.asarray(
                    channel[int(start):int(start) + WINDOW_SAMPLES], dtype=np.float32
                )
        names = [channels[int(index)].name for index in selected]
    return values, schedule, float(sample_rate), names


def integrated_power(
    frequency: np.ndarray, power: np.ndarray, low: float, high: float,
) -> np.ndarray:
    use = (frequency >= low) & (frequency < high)
    return np.trapezoid(power[..., use], frequency[use], axis=-1)


def band_median(frequency: np.ndarray, values: np.ndarray, low: float, high: float) -> float:
    use = (frequency >= low) & (frequency < high)
    return float(np.median(values[use]))


def exact_signflip_p(values: np.ndarray) -> float:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if not len(x):
        return np.nan
    observed = abs(float(np.mean(x)))
    if len(x) <= 15:
        masks = np.arange(1 << len(x), dtype=np.uint32)[:, None]
        bits = ((masks >> np.arange(len(x), dtype=np.uint32)) & 1).astype(float)
        signs = 2.0 * bits - 1.0
        null = np.abs(np.mean(signs * x[None, :], axis=1))
    else:
        rng = np.random.default_rng(20260830)
        signs = rng.choice((-1.0, 1.0), size=(9999, len(x)))
        null = np.abs(np.mean(signs * x[None, :], axis=1))
    return float(np.mean(null >= observed - 1e-15))


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


def analyze_case(spec: CaseSpec) -> dict[str, object]:
    loaded = load_exact_archive(spec.archive)
    selected = healthy_indices(loaded)
    windows, schedule, sample_rate, names = read_windows(spec, selected)
    centered = windows - np.mean(windows, axis=1, keepdims=True)
    scales = np.std(centered.reshape(-1, centered.shape[-1]), axis=0)
    standardized = centered / np.maximum(scales[None, None, :], 1e-12)
    nominal = schedule["timing_offset_s"].eq(0.0).to_numpy()
    covariance = np.einsum(
        "wsc,wsd->cd", standardized[nominal], standardized[nominal], optimize=True
    ) / float(np.sum(nominal) * WINDOW_SAMPLES)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    weights = eigenvectors[:, -1]
    if np.sum(weights) < 0.0:
        weights = -weights
    common = np.einsum("wsc,c->ws", standardized, weights, optimize=True)
    taper = signal.windows.hann(WINDOW_SAMPLES, sym=False).astype(np.float32)
    spectra = sp_fft.rfft(
        standardized * taper[None, :, None], axis=1, workers=-1
    ).astype(np.complex64, copy=False)
    common_spectra = sp_fft.rfft(
        common * taper[None, :], axis=1, workers=-1
    ).astype(np.complex64, copy=False)
    frequency = sp_fft.rfftfreq(WINDOW_SAMPLES, 1.0 / sample_rate)
    common_power = one_sided_psd(common_spectra, sample_rate, taper)
    cycle_rows = []
    for timing_offset in TIMING_OFFSETS_S:
        for cycle in range(1, spec.cycles + 1):
            state_metrics: dict[str, dict[str, float]] = {}
            for state in ("on", "off"):
                use = (
                    schedule["timing_offset_s"].eq(timing_offset)
                    & schedule["cycle_index"].eq(cycle)
                    & schedule["state"].eq(state)
                ).to_numpy()
                coherence, phase = pair_coherence_phase_curves(spectra[use])
                metrics: dict[str, float] = {}
                for band, (low, high) in BANDS.items():
                    power_values = integrated_power(
                        frequency, common_power[use], low, high
                    )
                    metrics[f"bandpower_{band}_db"] = float(
                        10.0 * np.log10(max(np.median(power_values), 1e-300))
                    )
                    metrics[f"pair_coherence_{band}"] = band_median(
                        frequency, coherence, low, high
                    )
                    metrics[f"pair_phase_locking_{band}"] = band_median(
                        frequency, phase, low, high
                    )
                state_metrics[state] = metrics
            row: dict[str, object] = {
                "case": spec.case,
                "kind": spec.kind,
                "current_ma": spec.current_ma,
                "repeat": spec.repeat,
                "timing_offset_s": timing_offset,
                "cycle_index": cycle,
            }
            for metric in state_metrics["on"]:
                row[f"{metric}_on"] = state_metrics["on"][metric]
                row[f"{metric}_off"] = state_metrics["off"][metric]
                row[f"{metric}_difference"] = (
                    state_metrics["on"][metric] - state_metrics["off"][metric]
                )
            cycle_rows.append(row)
    summary_rows = []
    cycle_frame = pd.DataFrame(cycle_rows)
    difference_columns = [
        column for column in cycle_frame if column.endswith("_difference")
    ]
    for timing_offset in TIMING_OFFSETS_S:
        subset = cycle_frame[cycle_frame["timing_offset_s"] == timing_offset]
        for column in difference_columns:
            values = subset[column].to_numpy(dtype=float)
            summary_rows.append({
                "case": spec.case,
                "kind": spec.kind,
                "current_ma": spec.current_ma,
                "repeat": spec.repeat,
                "timing_offset_s": timing_offset,
                "metric": column.removesuffix("_difference"),
                "cycle_count": len(values),
                "median_on_minus_off": float(np.median(values)),
                "mean_on_minus_off": float(np.mean(values)),
                "positive_cycle_fraction": float(np.mean(values > 0.0)),
                "exact_signflip_p": exact_signflip_p(values),
            })
    return {
        "version": 1,
        "case": spec.case,
        "raw_path": str(spec.raw_path),
        "healthy_channel_indices_1based": (selected + 1).tolist(),
        "healthy_channel_names": names,
        "healthy_channel_count": len(selected),
        "sample_rate_hz": sample_rate,
        "window_samples": WINDOW_SAMPLES,
        "windows_per_state_cycle": WINDOWS_PER_STATE,
        "raw_pc1_variance_fraction": float(
            eigenvalues[-1] / max(np.sum(eigenvalues), 1e-15)
        ),
        "cycle_rows": cycle_rows,
        "summary_rows": summary_rows,
    }


def calibration_tables(summary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    nominal = summary[
        summary["timing_offset_s"].eq(0.0)
        & summary["kind"].eq("closed_circuit")
    ].copy()
    dose_rows = []
    for metric, group in nominal.groupby("metric"):
        values = group[["current_ma", "median_on_minus_off"]].dropna()
        rho, p_value = stats.spearmanr(
            values["current_ma"], values["median_on_minus_off"]
        )
        dose_rows.append({
            "metric": metric,
            "case_count": len(values),
            "current_level_count": values["current_ma"].nunique(),
            "spearman_rho": float(rho),
            "spearman_p": float(p_value),
        })
    dose = pd.DataFrame(dose_rows)
    if not dose.empty:
        dose["spearman_fdr"] = bh_adjust(dose["spearman_p"].to_numpy())
    repeat_rows = []
    for current in (1000.0, 3000.0):
        selected = nominal[nominal["current_ma"].eq(current)]
        for metric, group in selected.groupby("metric"):
            if len(group) != 2:
                continue
            first, second = group.sort_values("repeat").itertuples(index=False)
            repeat_rows.append({
                "current_ma": current,
                "metric": metric,
                "repeat1_difference": first.median_on_minus_off,
                "repeat2_difference": second.median_on_minus_off,
                "same_direction": bool(
                    np.sign(first.median_on_minus_off)
                    == np.sign(second.median_on_minus_off)
                ),
                "absolute_difference": abs(
                    first.median_on_minus_off - second.median_on_minus_off
                ),
            })
    return dose, pd.DataFrame(repeat_rows)


def plot_summary(summary: pd.DataFrame, output: Path) -> None:
    nominal = summary[summary["timing_offset_s"].eq(0.0)]
    metrics = [
        "pair_coherence_20_80khz",
        "pair_coherence_80_200khz",
        "pair_phase_locking_80_200khz",
    ]
    fig, axes = plt.subplots(1, len(metrics), figsize=(15, 4.8), sharey=False)
    for axis, metric in zip(axes, metrics):
        selected = nominal[nominal["metric"].eq(metric)]
        axis.axhline(0.0, color="#555555", linewidth=0.8)
        axis.scatter(
            selected["current_ma"], selected["median_on_minus_off"],
            c=selected["kind"].map({
                "open_control": "#d49a3a", "closed_circuit": "#3976a8",
            }), s=55,
        )
        axis.set_xlabel("Set current (mA)")
        axis.set_title(metric.replace("_", " "))
        axis.set_ylabel("ON minus OFF")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def json_value(value: object) -> object:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_value(item) for item in value]
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    case_output = args.output / "cases"
    case_output.mkdir(parents=True, exist_ok=True)
    specs = build_specs()
    if args.limit:
        specs = specs[:args.limit]
    payloads = []
    for index, spec in enumerate(specs, start=1):
        key = hashlib.sha256(spec.case.encode("utf-8")).hexdigest()[:16]
        path = case_output / f"{key}.json"
        if path.exists() and not args.force:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if int(payload.get("version", 0)) == 1:
                print(f"[{index:02d}/{len(specs):02d}] cached {spec.case}", flush=True)
                payloads.append(payload)
                continue
        print(f"[{index:02d}/{len(specs):02d}] {spec.case}", flush=True)
        payload = analyze_case(spec)
        path.write_text(
            json.dumps(json_value(payload), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        payloads.append(payload)
    cycles = pd.DataFrame([
        row for payload in payloads for row in payload["cycle_rows"]
    ])
    summary = pd.DataFrame([
        row for payload in payloads for row in payload["summary_rows"]
    ])
    nominal = summary[summary["timing_offset_s"].eq(0.0)].copy()
    nominal["exact_signflip_fdr"] = bh_adjust(
        nominal["exact_signflip_p"].to_numpy()
    )
    summary = summary.merge(
        nominal[["case", "metric", "exact_signflip_fdr"]],
        on=["case", "metric"], how="left",
    )
    dose, repeats = calibration_tables(summary)
    cycles.to_csv(args.output / "highfreq_cycle_differences.csv", index=False)
    summary.to_csv(args.output / "highfreq_on_off_summary.csv", index=False)
    dose.to_csv(args.output / "highfreq_dose_response.csv", index=False)
    repeats.to_csv(args.output / "highfreq_repeatability.csv", index=False)
    health = pd.DataFrame([{
        "case": payload["case"],
        "healthy_channel_count": payload["healthy_channel_count"],
        "healthy_channel_indices_1based": payload["healthy_channel_indices_1based"],
        "raw_pc1_variance_fraction": payload["raw_pc1_variance_fraction"],
    } for payload in payloads])
    health.to_csv(args.output / "highfreq_dynamic_health.csv", index=False)
    plot_summary(summary, args.output / "cathodic_highfreq_summary.png")
    manifest = {
        "analysis": "cathodic_mentor_high_frequency",
        "case_count": len(payloads),
        "timing_offsets_s": list(TIMING_OFFSETS_S),
        "windows_per_state_cycle": WINDOWS_PER_STATE,
        "window_samples": WINDOW_SAMPLES,
        "limitations": [
            "manual switching has no synchronized current trace",
            "four windows per state-cycle make cycle-level coherence exploratory",
            "old electrode spacing was approximately 1 cm",
        ],
    }
    (args.output / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Output: {args.output}", flush=True)


if __name__ == "__main__":
    main()
