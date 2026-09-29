"""Cycle-paired multichannel state analysis for old cathodic records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from scripts.analyze_cathodic_mentor_lowfreq import (
    FEATURES,
    CaseSpec,
    build_specs,
    healthy_indices,
    protocol_start,
    robust_scale,
    time_axis,
)
from scripts.build_cathodic_mentor_methods_report import bh_adjust
from scripts.exact_tdms_archive import load_exact_archive


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "results/cathodic_mentor_methods_v1/state_network"
TIMING_OFFSETS_S = (-1.0, 0.0, 1.0)
GROUPS = (*FEATURES, "combined")


def paired_vectors(
    spec: CaseSpec,
    timing_offset_s: float,
) -> tuple[dict[str, np.ndarray], dict[str, list[str]], np.ndarray]:
    loaded = load_exact_archive(spec.archive)
    times = time_axis(loaded)
    healthy = healthy_indices(loaded)
    if not spec.cycles or spec.nominal_period_s is None:
        raise ValueError(f"{spec.case} has no repeated switching protocol")
    period = spec.nominal_period_s
    state_duration = period * spec.duty
    margin = min(0.8, 0.15 * state_duration)
    start = protocol_start(spec, float(times[-1])) + timing_offset_s
    vectors: dict[str, list[np.ndarray]] = {feature: [] for feature in FEATURES}
    labels = {
        feature: [f"{feature}:ch{index + 1}" for index in healthy]
        for feature in FEATURES
    }
    standardized = {}
    for feature in FEATURES:
        values = np.asarray(loaded["features"][feature], dtype=float)[:, healthy]
        scale = robust_scale(values, axis=0)
        standardized[feature] = values / scale[None, :]
    valid_cycles = []
    for cycle in range(spec.cycles):
        cycle_start = start + cycle * period
        on = (
            (times >= cycle_start + margin)
            & (times < cycle_start + state_duration - margin)
        )
        off = (
            (times >= cycle_start + state_duration + margin)
            & (times < cycle_start + period - margin)
        )
        if np.sum(on) < 3 or np.sum(off) < 3:
            continue
        valid_cycles.append(cycle + 1)
        for feature in FEATURES:
            values = standardized[feature]
            vectors[feature].append(
                np.median(values[on], axis=0) - np.median(values[off], axis=0)
            )
    result = {feature: np.asarray(rows) for feature, rows in vectors.items()}
    result["combined"] = np.concatenate([result[feature] for feature in FEATURES], axis=1)
    labels["combined"] = [item for feature in FEATURES for item in labels[feature]]
    return result, labels, np.asarray(valid_cycles, dtype=int)


def unit_rows(values: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    return values / np.maximum(norms, 1e-15)


def alignment_statistic(unit_vectors: np.ndarray) -> float:
    count = len(unit_vectors)
    if count < 2:
        return np.nan
    gram = unit_vectors @ unit_vectors.T
    return float((np.sum(gram) - count) / (count * (count - 1)))


def exact_alignment_p(unit_vectors: np.ndarray) -> float:
    count = len(unit_vectors)
    observed = alignment_statistic(unit_vectors)
    masks = np.arange(1 << count, dtype=np.uint32)[:, None]
    bits = ((masks >> np.arange(count, dtype=np.uint32)) & 1).astype(float)
    signs = 2.0 * bits - 1.0
    sums = signs @ unit_vectors
    null = (np.sum(sums * sums, axis=1) - count) / (count * (count - 1))
    return float(np.mean(null >= observed - 1e-15))


def exact_projection_p(values: np.ndarray) -> float:
    x = np.asarray(values, dtype=float)
    observed = float(np.mean(x))
    count = len(x)
    masks = np.arange(1 << count, dtype=np.uint32)[:, None]
    bits = ((masks >> np.arange(count, dtype=np.uint32)) & 1).astype(float)
    signs = 2.0 * bits - 1.0
    null = np.mean(signs * x[None, :], axis=1)
    return float(np.mean(null >= observed - 1e-15))


def summarize_vectors(values: np.ndarray) -> dict[str, float | int]:
    unit = unit_rows(values)
    scores = []
    for index in range(len(unit)):
        centroid = np.mean(np.delete(unit, index, axis=0), axis=0)
        centroid /= max(float(np.linalg.norm(centroid)), 1e-15)
        scores.append(float(unit[index] @ centroid))
    return {
        "cycle_count": len(values),
        "dimension_count": values.shape[1],
        "median_effect_rms_sigma": float(
            np.median(np.linalg.norm(values, axis=1) / np.sqrt(values.shape[1]))
        ),
        "mean_pairwise_alignment": alignment_statistic(unit),
        "leave_one_cycle_projection_median": float(np.median(scores)),
        "leave_one_cycle_positive_fraction": float(np.mean(np.asarray(scores) > 0.0)),
        "alignment_signflip_p": exact_alignment_p(unit),
    }


def analyze_protocols() -> tuple[pd.DataFrame, dict[tuple[str, str], dict[str, object]]]:
    rows = []
    payloads: dict[tuple[str, str], dict[str, object]] = {}
    specs = [spec for spec in build_specs() if spec.cycles]
    for index, spec in enumerate(specs, start=1):
        print(f"[{index:02d}/{len(specs):02d}] {spec.batch}/{spec.case}", flush=True)
        for offset in TIMING_OFFSETS_S:
            vectors, labels, cycles = paired_vectors(spec, offset)
            for group in GROUPS:
                rows.append({
                    "batch": spec.batch,
                    "case": spec.case,
                    "kind": spec.kind,
                    "current_ma": spec.current_ma,
                    "repeat": spec.repeat,
                    "timing_offset_s": offset,
                    "feature_group": group,
                    **summarize_vectors(vectors[group]),
                })
            if offset == 0.0:
                payloads[(spec.case, spec.batch)] = {
                    "spec": spec, "vectors": vectors, "labels": labels,
                    "cycles": cycles,
                }
    frame = pd.DataFrame(rows)
    nominal = frame[frame["timing_offset_s"].eq(0.0)].copy()
    nominal["alignment_signflip_fdr"] = bh_adjust(
        nominal["alignment_signflip_p"].to_numpy()
    )
    frame = frame.merge(
        nominal[["batch", "case", "feature_group", "alignment_signflip_fdr"]],
        on=["batch", "case", "feature_group"], how="left",
    )
    return frame, payloads


def transfer_analysis(
    payloads: dict[tuple[str, str], dict[str, object]],
) -> pd.DataFrame:
    rows = []
    for current, first_case, second_case in (
        (1000.0, "cp1000near", "cp1000near2"),
        (3000.0, "cp3000near", "cp3000near2"),
    ):
        first = payloads[(first_case, "8.11.2")]
        second = payloads[(second_case, "8.11.2")]
        for group in GROUPS:
            first_labels = first["labels"][group]
            second_labels = second["labels"][group]
            common = sorted(set(first_labels).intersection(second_labels))
            first_positions = [first_labels.index(label) for label in common]
            second_positions = [second_labels.index(label) for label in common]
            first_values = unit_rows(first["vectors"][group][:, first_positions])
            second_values = unit_rows(second["vectors"][group][:, second_positions])
            for source_case, source, target_case, target in (
                (first_case, first_values, second_case, second_values),
                (second_case, second_values, first_case, first_values),
            ):
                centroid = np.mean(source, axis=0)
                centroid /= max(float(np.linalg.norm(centroid)), 1e-15)
                scores = target @ centroid
                rows.append({
                    "current_ma": current,
                    "feature_group": group,
                    "source_case": source_case,
                    "target_case": target_case,
                    "common_dimension_count": len(common),
                    "target_cycle_count": len(scores),
                    "target_projection_median": float(np.median(scores)),
                    "target_projection_mean": float(np.mean(scores)),
                    "target_positive_fraction": float(np.mean(scores > 0.0)),
                    "projection_signflip_p": exact_projection_p(scores),
                })
    frame = pd.DataFrame(rows)
    frame["projection_signflip_fdr"] = bh_adjust(
        frame["projection_signflip_p"].to_numpy()
    )
    return frame


def plot_results(summary: pd.DataFrame, transfer: pd.DataFrame, output: Path) -> None:
    nominal = summary[summary["timing_offset_s"].eq(0.0)]
    pivot = nominal.pivot(index="case", columns="feature_group", values="mean_pairwise_alignment")
    pivot = pivot.reindex(columns=GROUPS)
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    image = axes[0].imshow(pivot.to_numpy(), aspect="auto", cmap="RdBu_r", vmin=-0.25, vmax=0.25)
    axes[0].set_xticks(np.arange(len(pivot.columns)), pivot.columns, rotation=60, ha="right")
    axes[0].set_yticks(np.arange(len(pivot.index)), pivot.index)
    axes[0].set_title("Within-record cycle alignment")
    fig.colorbar(image, ax=axes[0], label="Mean pairwise cosine")

    combined = transfer[transfer["feature_group"].eq("combined")]
    labels = combined["source_case"] + " -> " + combined["target_case"]
    axes[1].bar(np.arange(len(combined)), combined["target_projection_median"], color="#3976a8")
    axes[1].axhline(0.0, color="#555555", linewidth=0.8)
    axes[1].set_xticks(np.arange(len(combined)), labels, rotation=55, ha="right")
    axes[1].set_ylabel("Median target projection")
    axes[1].set_title("Cross-repeat transfer: combined state")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    summary, payloads = analyze_protocols()
    transfer = transfer_analysis(payloads)
    summary.to_csv(args.output / "state_cycle_alignment.csv", index=False)
    transfer.to_csv(args.output / "state_cross_repeat_transfer.csv", index=False)
    plot_results(summary, transfer, args.output / "state_network_summary.png")
    manifest = {
        "analysis": "cathodic_cycle_paired_state_network",
        "protocol_case_count": int(summary["case"].nunique()),
        "feature_groups": list(GROUPS),
        "timing_offsets_s": list(TIMING_OFFSETS_S),
        "null": "exact independent cycle-direction sign flips",
        "limitations": [
            "manual switching has no synchronized current trace",
            "005hz has only four cycles",
            "old electrode spacing was approximately 1 cm",
        ],
    }
    (args.output / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Output: {args.output}", flush=True)


if __name__ == "__main__":
    main()
