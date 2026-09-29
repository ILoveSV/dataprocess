"""Build the mentor-aligned evidence report from completed analysis tables."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats


def spectral_redistribution(base: Path) -> pd.DataFrame:
    contrast = pd.read_csv(base / "matched_band_contrasts.csv")
    drift = pd.read_csv(base / "background_block_variability_summary.csv")
    use = contrast[
        (contrast["reference_condition"] == "background")
        & contrast["band_name"].isin(["20_80khz", "80_200khz"])
    ].copy()
    use["carrier_khz"] = use["carrier_khz"].fillna(-1.0)
    use["output_hz"] = use["output_hz"].fillna(-1.0)
    pivot = use.pivot_table(
        index=[
            "dataset", "case_id", "arrangement", "detector", "condition",
            "carrier_khz", "output_hz", "reference_case_id",
        ],
        columns="band_name",
        values="median_channel_typical_difference_db",
    ).reset_index()
    pivot.columns.name = None
    pivot[["carrier_khz", "output_hz"]] = pivot[
        ["carrier_khz", "output_hz"]
    ].replace(-1.0, np.nan)
    drift_pivot = drift[drift["band_name"].isin(["20_80khz", "80_200khz"])].pivot_table(
        index="case_id",
        columns="band_name",
        values="q95_absolute_block_drift_db",
    ).reset_index().rename(columns={
        "case_id": "reference_case_id",
        "20_80khz": "reference_20_80khz_q95_block_drift_db",
        "80_200khz": "reference_80_200khz_q95_block_drift_db",
    })
    pivot = pivot.merge(drift_pivot, on="reference_case_id", how="left")
    pivot["redistribution_score_db"] = pivot["80_200khz"] - pivot["20_80khz"]
    pivot["midband_effect_over_reference_q95"] = (
        pivot["20_80khz"].abs()
        / pivot["reference_20_80khz_q95_block_drift_db"]
    )
    pivot["highband_effect_over_reference_q95"] = (
        pivot["80_200khz"].abs()
        / pivot["reference_80_200khz_q95_block_drift_db"]
    )
    pivot["dual_band_run_signature"] = (
        (pivot["20_80khz"] < 0.0)
        & (pivot["80_200khz"] > 0.0)
        & (pivot["midband_effect_over_reference_q95"] > 1.0)
        & (pivot["highband_effect_over_reference_q95"] > 1.0)
    )
    pivot["evidence_tier"] = np.where(
        pivot["dataset"] == 20260617,
        "historical_direction_reference",
        "later_confirmatory_experiment",
    )
    return pivot


def frequency_pairing(spectral: pd.DataFrame) -> pd.DataFrame:
    active = spectral[spectral["condition"].isin(["30hz", "50hz"])]
    paired = active.pivot_table(
        index=["dataset", "arrangement", "detector"],
        columns="condition",
        values="redistribution_score_db",
    ).dropna().reset_index()
    paired.columns.name = None
    paired["50hz_minus_30hz_score_db"] = paired["50hz"] - paired["30hz"]
    return paired


def background_ranges(base: Path) -> pd.DataFrame:
    band = pd.read_csv(base / "band_temporal_dynamics.csv")
    background = band[
        (band["condition"] == "background")
        & band["detector"].isin(["tc1", "tc2"])
    ]
    return background.groupby(["detector", "band_name"])["segment_median_db"].agg(
        background_min_db="min",
        background_max_db="max",
        background_range_db=lambda values: values.max() - values.min(),
        background_case_count="count",
    ).reset_index()


def narrow_line_summary(base: Path) -> pd.DataFrame:
    lines = pd.read_csv(base / "matched_narrow_line_contrasts.csv")
    lines["robust_and_persistent"] = (
        lines["robust_new_or_enhanced_line_ge_3db"]
        & (lines["active_channel_fraction_presence_ge_0p2"] >= 0.5)
    )
    return lines.groupby([
        "dataset", "case_id", "arrangement", "detector", "condition", "carrier_khz",
        "output_hz", "reference_condition",
    ], dropna=False).agg(
        candidate_line_count=("frequency_hz", "count"),
        robust_line_count=("robust_new_or_enhanced_line_ge_3db", "sum"),
        robust_persistent_line_count=("robust_and_persistent", "sum"),
        maximum_same_bin_contrast_db=("same_bin_aggregate_contrast_db", "max"),
        maximum_neighborhood_contrast_db=("contrast_to_reference_neighborhood_peak_db", "max"),
    ).reset_index()


def run_stop_exploratory_classification(spectral: pd.DataFrame) -> pd.DataFrame:
    """Quantify RUN/STOP separation without presenting an in-sample rule as validated."""
    use = spectral[
        (spectral["dataset"] != 20260617)
        & spectral["condition"].isin(["30hz", "50hz", "run", "vfd_stop"])
    ].copy()
    is_run = use["condition"] != "vfd_stop"
    scores = use["redistribution_score_db"].to_numpy(dtype=float)
    labels = is_run.to_numpy(dtype=bool)
    run_scores = scores[labels]
    stop_scores = scores[~labels]
    auc = float(
        stats.mannwhitneyu(run_scores, stop_scores).statistic
        / (len(run_scores) * len(stop_scores))
    )

    unique_scores = np.unique(scores)
    thresholds = (unique_scores[:-1] + unique_scores[1:]) / 2.0
    candidates = []
    for threshold in thresholds:
        predicted = scores > threshold
        sensitivity = float(np.mean(predicted[labels]))
        specificity = float(np.mean(~predicted[~labels]))
        candidates.append((
            (sensitivity + specificity) / 2.0,
            threshold,
            sensitivity,
            specificity,
            predicted,
        ))
    _, best_threshold, best_sensitivity, best_specificity, best_predicted = max(
        candidates, key=lambda item: (item[0], item[2], item[3])
    )

    direction_predicted = use["dual_band_run_signature"].to_numpy(dtype=bool)

    def row(name: str, predicted: np.ndarray, threshold: float | None,
            sensitivity: float, specificity: float, validation: str) -> dict[str, object]:
        return {
            "rule": name,
            "redistribution_score_threshold_db": threshold,
            "run_count": int(labels.sum()),
            "stop_count": int((~labels).sum()),
            "true_run": int(np.sum(predicted & labels)),
            "missed_run": int(np.sum(~predicted & labels)),
            "false_run_on_stop": int(np.sum(predicted & ~labels)),
            "true_stop": int(np.sum(~predicted & ~labels)),
            "sensitivity": sensitivity,
            "specificity": specificity,
            "balanced_accuracy": (sensitivity + specificity) / 2.0,
            "score_auc_run_vs_stop": auc,
            "validation_status": validation,
        }

    direction_sensitivity = float(np.mean(direction_predicted[labels]))
    direction_specificity = float(np.mean(~direction_predicted[~labels]))
    return pd.DataFrame([
        row(
            "dual_band_direction_plus_background_drift",
            direction_predicted,
            None,
            direction_sensitivity,
            direction_specificity,
            "predefined descriptive rule; no unknown-label validation",
        ),
        row(
            "posthoc_redistribution_score_threshold",
            best_predicted,
            float(best_threshold),
            best_sensitivity,
            best_specificity,
            "threshold selected and evaluated on same archive; exploratory only",
        ),
    ])


def time_domain_feature_consistency(base: Path) -> pd.DataFrame:
    """Summarize signs at both file and shared-background stratum levels."""
    frames: list[pd.DataFrame] = []

    slow = pd.read_csv(base / "matched_slow_dynamics_contrasts.csv")
    slow["family"] = "slow"
    slow["feature"] = slow["metric"]
    slow["effect"] = slow["median_channel_difference"]
    frames.append(slow)

    network = pd.read_csv(base / "matched_network_contrasts.csv")
    network["family"] = "network"
    network["feature"] = network["metric"]
    network["effect"] = network["difference"]
    frames.append(network)

    allan = pd.read_csv(base / "matched_allan_contrasts.csv")
    allan["family"] = "allan"
    allan["feature"] = allan["tau_s"].map(lambda value: f"allan_tau_{value:g}s")
    allan["effect"] = allan["median_allan_amplitude_ratio_db"]
    frames.append(allan)

    coherence = pd.read_csv(base / "matched_low_rate_coherence_contrasts.csv")
    coherence = coherence[coherence["metric"] == "median_coherence"].copy()
    coherence["family"] = "coherence"
    coherence["feature"] = "coherence_" + coherence["band_name"]
    coherence["effect"] = coherence["median_pair_difference"]
    frames.append(coherence)

    combined = pd.concat(frames, ignore_index=True)
    combined = combined[
        (combined["dataset"] != 20260617)
        & combined["condition"].isin(["30hz", "50hz", "run"])
        & combined["reference_condition"].isin(["background", "vfd_stop"])
    ].copy()

    rows = []
    tolerance = 1e-15
    keys = ["family", "feature", "reference_condition"]
    for (family, feature, reference), group in combined.groupby(keys):
        sample = group["effect"].dropna().to_numpy(dtype=float)
        strata = group.groupby(
            ["dataset", "arrangement", "detector"], dropna=False
        )["effect"].median().dropna().to_numpy(dtype=float)

        def counts(values: np.ndarray) -> tuple[int, int, int]:
            return (
                int(np.sum(values > tolerance)),
                int(np.sum(values < -tolerance)),
                int(np.sum(np.abs(values) <= tolerance)),
            )

        sample_positive, sample_negative, sample_zero = counts(sample)
        stratum_positive, stratum_negative, stratum_zero = counts(strata)
        rows.append({
            "family": family,
            "feature": feature,
            "reference_condition": reference,
            "sample_count": len(sample),
            "sample_positive_count": sample_positive,
            "sample_negative_count": sample_negative,
            "sample_zero_count": sample_zero,
            "sample_median_effect": float(np.median(sample)),
            "stratum_count": len(strata),
            "stratum_positive_count": stratum_positive,
            "stratum_negative_count": stratum_negative,
            "stratum_zero_count": stratum_zero,
            "stratum_median_effect": float(np.median(strata)),
            "signed_stratum_balance": float(
                (stratum_positive - stratum_negative) / max(len(strata), 1)
            ),
            "dominant_stratum_fraction": float(
                max(stratum_positive, stratum_negative) / max(len(strata), 1)
            ),
        })
    return pd.DataFrame(rows)


def plot_spectral_redistribution(spectral: pd.DataFrame, output: Path) -> None:
    fig, axis = plt.subplots(figsize=(8.5, 6.5))
    styles = {
        "30hz": ("#2f6f8f", "o"),
        "50hz": ("#c24d3c", "s"),
        "run": ("#598b45", "^"),
        "vfd_stop": ("#777777", "x"),
    }
    for condition, (color, marker) in styles.items():
        selected = spectral[spectral["condition"] == condition]
        axis.scatter(selected["20_80khz"], selected["80_200khz"],
                     color=color, marker=marker, s=55, alpha=0.85, label=condition)
    axis.axvline(0.0, color="#444444", linewidth=0.8)
    axis.axhline(0.0, color="#444444", linewidth=0.8)
    axis.set_xlabel("20-80 kHz contrast to local background (dB)")
    axis.set_ylabel("80-200 kHz contrast to local background (dB)")
    axis.set_title("Local-reference spectral redistribution")
    axis.grid(alpha=0.25)
    axis.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def plot_frequency_pairing(pairing: pd.DataFrame, output: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.8))
    subsets = (
        (pairing[pairing["dataset"] != 20260617], "Later experiments"),
        (pairing[pairing["dataset"] == 20260617], "Early direction reference"),
    )
    for axis, (subset, title) in zip(axes, subsets):
        for _, row in subset.iterrows():
            label = f"{int(row['dataset'])}/{row['arrangement']}/{row['detector']}"
            axis.plot([30, 50], [row["30hz"], row["50hz"]], marker="o",
                      alpha=0.8, label=label)
        axis.set_xlim(27, 53)
        axis.set_xticks([30, 50])
        axis.set_xlabel("Pump output setting (Hz)")
        axis.set_title(title)
        axis.grid(alpha=0.25)
        axis.legend(fontsize=7, loc="best")
    axes[0].set_ylabel("Redistribution score (dB)")
    fig.suptitle("30/50 Hz paired local-reference score")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def plot_background_ranges(ranges: pd.DataFrame, output: Path) -> None:
    bands = ["5_100hz", "100_1khz", "1_20khz", "20_80khz", "80_200khz"]
    x = np.arange(len(bands))
    width = 0.36
    fig, axis = plt.subplots(figsize=(9, 5.5))
    for index, detector in enumerate(("tc1", "tc2")):
        selected = ranges[ranges["detector"] == detector].set_index("band_name")
        values = [selected.loc[band, "background_range_db"] for band in bands]
        axis.bar(x + (index - 0.5) * width, values, width=width,
                 label=detector.upper(), color=("#2f6f8f", "#c56a3d")[index])
    axis.set_yscale("log")
    axis.set_xticks(x, bands, rotation=25, ha="right")
    axis.set_ylabel("Cross-session background range (dB)")
    axis.set_title("Absolute background is not transferable between sessions")
    axis.grid(axis="y", alpha=0.25)
    axis.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def plot_periodicity(base: Path, output: Path) -> None:
    periodicity = pd.read_csv(base / "slow_periodicity_candidates.csv")
    fixed = periodicity[periodicity["candidate_type"] == "fixed_3p1s"].copy()
    fixed = fixed.sort_values(["dataset", "condition", "case_id"]).reset_index(drop=True)
    condition_colors = {
        "background": "#777777", "vfd_stop": "#8f6c45", "30hz": "#2f6f8f",
        "50hz": "#c24d3c", "run": "#598b45",
    }
    colors = fixed["condition"].map(condition_colors).fillna("#555555")
    fig, axis = plt.subplots(figsize=(11, 5.5))
    axis.scatter(np.arange(len(fixed)), fixed["red_noise_pointwise_p"],
                 c=colors, s=42)
    axis.axhline(0.05, color="#b22222", linestyle="--", linewidth=1.0,
                label="p=0.05")
    for condition, color in condition_colors.items():
        axis.scatter([], [], color=color, label=condition)
    axis.set_yscale("log")
    axis.set_ylim(0.04, 1.1)
    axis.set_xlabel("Long-record case index")
    axis.set_ylabel("AR(1) red-noise pointwise p-value")
    axis.set_title("No electrical 3.1 s periodicity survives red-noise testing")
    axis.grid(axis="y", alpha=0.25)
    axis.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def plot_narrow_lines(summary: pd.DataFrame, output: Path) -> None:
    selected = summary[
        (summary["dataset"] == 20260806)
        & (((summary["condition"] == "run") & (summary["reference_condition"] == "vfd_stop"))
           | ((summary["condition"] == "vfd_stop") & (summary["reference_condition"] == "background")))
    ].copy()
    selected["label"] = selected.apply(
        lambda row: (f"{row['detector']}/{row['carrier_khz']:g}k/{row['output_hz']:g}"
                     if row["condition"] == "run"
                     else f"{row['arrangement']}/{row['detector']}/STOP"),
        axis=1,
    )
    selected = selected.sort_values(["condition", "detector", "carrier_khz", "output_hz"])
    x = np.arange(len(selected))
    fig, axis = plt.subplots(figsize=(12, 6))
    axis.bar(x, selected["robust_line_count"], color="#2f6f8f", label="robust local lines")
    axis.bar(x, selected["robust_persistent_line_count"], color="#c24d3c",
             label="also persistent in >= half channels")
    axis.set_xticks(x, selected["label"], rotation=60, ha="right", fontsize=8)
    axis.set_ylabel("Line count")
    axis.set_title("Many average-spectrum lines are not temporally shared")
    axis.grid(axis="y", alpha=0.25)
    axis.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def plot_time_domain_consistency(consistency: pd.DataFrame, output: Path) -> None:
    order = {
        "slow": 0,
        "allan": 1,
        "network": 2,
        "coherence": 3,
    }
    frame = consistency.copy()
    frame["family_order"] = frame["family"].map(order)
    features = (
        frame[["family", "feature", "family_order"]]
        .drop_duplicates()
        .sort_values(["family_order", "feature"])
    )
    labels = [f"{row.family}: {row.feature}" for row in features.itertuples()]
    references = ["background", "vfd_stop"]
    matrix = np.full((len(features), len(references)), np.nan)
    count_matrix = np.zeros_like(matrix, dtype=int)
    for row_index, row in enumerate(features.itertuples()):
        for column_index, reference in enumerate(references):
            selected = frame[
                (frame["family"] == row.family)
                & (frame["feature"] == row.feature)
                & (frame["reference_condition"] == reference)
            ]
            if selected.empty:
                continue
            matrix[row_index, column_index] = selected.iloc[0]["signed_stratum_balance"]
            count_matrix[row_index, column_index] = int(selected.iloc[0]["stratum_count"])
    fig_height = max(8.0, 0.38 * len(features) + 2.0)
    fig, axis = plt.subplots(figsize=(8.5, fig_height))
    image = axis.imshow(matrix, cmap="RdBu_r", vmin=-1.0, vmax=1.0, aspect="auto")
    axis.set_xticks(range(len(references)), ["vs local background", "vs VFD STOP"])
    axis.set_yticks(range(len(labels)), labels, fontsize=8)
    for row_index in range(matrix.shape[0]):
        for column_index in range(matrix.shape[1]):
            if np.isfinite(matrix[row_index, column_index]):
                axis.text(
                    column_index, row_index,
                    f"{matrix[row_index, column_index]:+.2f}\n(n={count_matrix[row_index, column_index]})",
                    ha="center", va="center", fontsize=7,
                    color="white" if abs(matrix[row_index, column_index]) >= 0.65 else "black",
                )
    colorbar = fig.colorbar(image, ax=axis, pad=0.03)
    colorbar.set_label("Stratum sign balance: +1 all increase, -1 all decrease")
    axis.set_title("Steady-state time-domain feature direction consistency")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def build_identifiability(pairing: pd.DataFrame,
                          classification: pd.DataFrame) -> pd.DataFrame:
    recent_pairing = pairing[pairing["dataset"] != 20260617]
    higher_50 = int(np.sum(recent_pairing["50hz_minus_30hz_score_db"] > 0.0))
    direction = classification.iloc[0]
    return pd.DataFrame([
        {
            "target": "paired local background vs steady pump RUN",
            "status": "group difference detected in current archive",
            "evidence": "same dual-band sign in 24/24 later pairs; 6/6 early pairs agree as reference",
            "boundary": "paired detection only; does not validate an unknown-sample RUN classifier",
        },
        {
            "target": "unknown STOP vs RUN sample with local background",
            "status": "candidate separation, not validated classifier",
            "evidence": (
                f"direction rule sensitivity {direction['sensitivity']:.0%}, specificity "
                f"{direction['specificity']:.0%}; score AUC {direction['score_auc_run_vs_stop']:.3f}"
            ),
            "boundary": "4/8 STOP controls mimic the RUN direction; no independent holdout",
        },
        {
            "target": "30 Hz vs 50 Hz output setting",
            "status": "candidate, not validated classifier",
            "evidence": f"redistribution score is higher at 50 Hz in {higher_50}/{len(recent_pairing)} later strata",
            "boundary": "one stratum reverses and no repeated unknown-label validation exists",
        },
        {
            "target": "VFD carrier 4/8/12 kHz",
            "status": "not identifiable",
            "evidence": "set carrier is strongest candidate in only 3/12 cases",
            "boundary": "no repeatable moving main peak or harmonic-comb ordering",
        },
        {
            "target": "3.1 s water/acoustic cycle in electrical output",
            "status": "not detected",
            "evidence": "0/40 long records pass AR(1) red-noise point test",
            "boundary": "does not exclude a weaker or differently timed water signal",
        },
        {
            "target": "VFD STOP vs pure background",
            "status": "not stable",
            "evidence": "band signs change with detector/position/session",
            "boundary": "power-on state cannot be universally recognized from current files",
        },
        {
            "target": "universal high-frequency narrow line",
            "status": "not found",
            "evidence": "line positions and persistence are detector/channel dependent",
            "boundary": "local line changes can still flag a change when a matched reference exists",
        },
    ])


def write_report(base: Path, spectral: pd.DataFrame, pairing: pd.DataFrame,
                 ranges: pd.DataFrame, narrow: pd.DataFrame,
                 identifiability: pd.DataFrame,
                 classification: pd.DataFrame,
                 time_consistency: pd.DataFrame) -> None:
    health = pd.read_csv(base / "channel_health_dynamic.csv")
    periodicity = pd.read_csv(base / "slow_periodicity_candidates.csv")
    coupling = pd.read_csv(base / "low_high_coupling.csv")
    synchrony = pd.read_csv(base / "cross_detector_synchrony.csv")
    coherence = pd.read_csv(base / "matched_low_rate_coherence_contrasts.csv")
    allan = pd.read_csv(base / "matched_allan_contrasts.csv")
    legacy_calibration = pd.read_csv(base / "legacy_pulse/legacy_pulse_amplitude_dependence.csv")
    legacy_summary = pd.read_csv(base / "legacy_pulse/legacy_pulse_group_channel_summary.csv")

    active = spectral[spectral["condition"].isin(["30hz", "50hz", "run"])]
    recent_active = active[active["dataset"] != 20260617]
    historical_active = active[active["dataset"] == 20260617]
    vfd = active[(active["dataset"] == 20260806) & (active["condition"] == "run")]
    duo = active[(active["dataset"] == 20260806) & active["condition"].isin(["30hz", "50hz"])]
    fixed = periodicity[periodicity["candidate_type"] == "fixed_3p1s"]
    searched = periodicity[periodicity["candidate_type"] == "pc1_search_peak"]
    strict_coupling = coupling[
        (coupling["scope"] == "common_pc1")
        & (coupling["lag_null_p"] <= 0.05)
        & (coupling["max_abs_lag_correlation"].abs() >= 0.3)
    ]
    common_coherence = coherence[coherence["metric"] == "median_coherence"]
    run_allan = allan[
        (allan["dataset"] == 20260806)
        & (allan["condition"] == "run")
        & allan["tau_s"].isin([1.0, 2.0])
    ]
    run_narrow = narrow[
        (narrow["dataset"] == 20260806)
        & (narrow["condition"] == "run")
        & (narrow["reference_condition"] == "vfd_stop")
    ]
    stop_narrow = narrow[
        (narrow["dataset"] == 20260806)
        & (narrow["condition"] == "vfd_stop")
        & (narrow["reference_condition"] == "background")
    ]
    practical_pulse = legacy_calibration[
        (legacy_calibration["metric"] == "mean_ac_rms")
        & (legacy_calibration["spearman_rho"].abs() >= 0.8)
        & (legacy_calibration["spearman_p"] <= 0.05)
        & (legacy_calibration["response_relative_range"] >= 0.05)
    ]
    bad_by_dataset = health.groupby("dataset")["automatic_bad"].sum().to_dict()
    detector_background = ranges[ranges["band_name"] == "80_200khz"]
    recent_pairing = pairing[pairing["dataset"] != 20260617]
    historical_pairing = pairing[pairing["dataset"] == 20260617]
    higher_50 = int(np.sum(recent_pairing["50hz_minus_30hz_score_db"] > 0.0))
    historical_higher_50 = int(np.sum(
        historical_pairing["50hz_minus_30hz_score_db"] > 0.0
    ))
    direction_rule = classification.iloc[0]
    posthoc_rule = classification.iloc[1]
    allan_5s_stop = time_consistency[
        (time_consistency["feature"] == "allan_tau_5s")
        & (time_consistency["reference_condition"] == "vfd_stop")
    ].iloc[0]
    allan_5s_background = time_consistency[
        (time_consistency["feature"] == "allan_tau_5s")
        & (time_consistency["reference_condition"] == "background")
    ].iloc[0]

    lines = [
        "# 导师建议导向的电化学实验前数据分析报告",
        "",
        "## 1. 研究对象与证据层级",
        "",
        "本报告把探测器视为带偏置源、量化、慢弛豫、通道串扰和环境耦合的有源多通道网络。分析不再把单个PSD峰直接命名为水流或器件物理过程，而是依次判断：可检测变化、可识别工况、可归因来源。",
        "",
        "正式重算包含49个精确归档：2026-06-17的距离组9个、2026-07-31的工况拆分8个、2026-08-06的交叉换位和载波扫描32个。另复核2026-06-09脉冲实验188个工况的输出级JSON；5月12日只有旧PSD结果，继续作为历史方向参考，不进入最终定量证据。电化学/阴极保护实验暂不纳入。",
        "",
        "## 2. 方法修正",
        "",
        "- 每文件动态判断坏道；自动坏道记录数为：" + str(bad_by_dataset) + "。7月31日TC1除长期异常通道外还出现临时坏道，证明固定坏道表不可用。",
        "- 频带主统计量改为‘每个共同健康通道先做活动-本地对照，再跨通道取中位数’。旧的‘每时刻先跨通道取中位数’会因通道排序切换产生反号。",
        "- Welch段和通道只描述同一文件内稳定性，不当作独立实验重复。背景记录另切为连续时间块，用其95%漂移量评价本地可检测性。",
        "- 周期候选除频谱峰外，还检查前后半段、通道支持、分段相位，并用500次AR(1)红噪声蒙特卡洛检验，抑制慢漂移造成的虚假周期赋值。",
        "- 新增Allan尺度、ACF/AR(1)、PCA网络、时滞相关、1 Hz-1.5 kHz跨通道相干、低高频包络耦合、窄线逐段持续性。",
        "- 现有稳态文件没有统一标注的开关触发时刻；因此ACF、AR(1)和Allan量只解释为有效记忆/漂移尺度，不能直接命名为器件充放电弛豫常数。",
        "- 对应导师提出的三项门槛：重复性按独立文件/日期-摆位-探测器层级统计；显著性用本地背景时间块、红噪声和错位对照评估；相关性同时检查通道内、跨通道及跨探测器结构。",
        "",
        "## 3. 最明确的新结果：运行链频谱重分配",
        "",
        f"在7月31日和8月6日共{len(recent_active)}个30/50 Hz或载波扫描RUN相对本地背景的文件对中，{int(recent_active['dual_band_run_signature'].sum())}/{len(recent_active)}同时满足：20-80 kHz下降、80-200 kHz上升，并且变化超过各自背景内部95%时间块漂移。6月17日早期距离组仅作方向参考，另有{int(historical_active['dual_band_run_signature'].sum())}/{len(historical_active)}同方向。",
        f"- 后期实验20-80 kHz变化范围：{recent_active['20_80khz'].min():.4f}至{recent_active['20_80khz'].max():.4f} dB；最小背景漂移倍率{recent_active['midband_effect_over_reference_q95'].min():.2f}。",
        f"- 后期实验80-200 kHz变化范围：{recent_active['80_200khz'].min():.4f}至{recent_active['80_200khz'].max():.4f} dB；最小背景漂移倍率{recent_active['highband_effect_over_reference_q95'].min():.2f}。",
        f"- 8月6日交叉换位组的80-200 kHz增量为{duo['80_200khz'].min():.4f}至{duo['80_200khz'].max():.4f} dB；VFD扫描RUN组为{vfd['80_200khz'].min():.4f}至{vfd['80_200khz'].max():.4f} dB。",
        "",
        "因此，在同一探测器、相邻本地背景和动态健康通道条件下，可以稳定检出与RUN同时发生的成对频谱差异。它是频谱能量重分配，而不是简单的‘所有高频都增大’。由于泵、电机、VFD、电缆和水流仍共同变化，该特征不能命名为水流信号。",
        "",
        f"但这个结果还不是未知样本分类器：双频带方向判据在24/24个RUN中为阳性，也在{int(direction_rule['false_run_on_stop'])}/{int(direction_rule['stop_count'])}个STOP负对照中为阳性，样本内特异度仅{direction_rule['specificity']:.0%}。重分配分数对RUN/STOP的样本内AUC为{direction_rule['score_auc_run_vs_stop']:.3f}；事后选择阈值{posthoc_rule['redistribution_score_threshold_db']:.4f} dB可得到灵敏度{posthoc_rule['sensitivity']:.0%}、特异度{posthoc_rule['specificity']:.0%}，但阈值在同一批数据上选择和评估，只能作为下一轮验证候选。",
        "",
        "## 4. 本地背景为何不可省略",
        "",
        f"TC1/TC2的80-200 kHz绝对背景跨时段范围分别为{detector_background.set_index('detector').loc['tc1','background_range_db']:.3f}和{detector_background.set_index('detector').loc['tc2','background_range_db']:.3f} dB，已经大于多数单次RUN增量。低频和100 Hz-1 kHz背景范围可达到约2 dB。",
        "",
        "相反，8月6日本地背景内部80-200 kHz时间块95%漂移约0.003-0.008 dB。因此‘有本地背景时能检出’与‘跨时段使用固定绝对阈值’是两件不同的事。当前不能给出无本地对照的通用0.2 dB阈值。",
        "",
        "## 5. 低频与周期结论",
        "",
        f"- 3.1 s固定周期：足够长的{len(fixed)}个文件中，红噪声点检验通过数为{int((fixed['red_noise_pointwise_p'] <= 0.05).sum())}，最小p={fixed['red_noise_pointwise_p'].min():.3f}。",
        f"- 盲搜0.05-2 Hz：{len(searched)}个候选中，多重比较校正后通过数为{int((searched['red_noise_search_familywise_p'] <= 0.05).sum())}，最小校正p={searched['red_noise_search_familywise_p'].min():.3f}。约0.08-0.12 Hz的视觉峰也见于背景和STOP，属于慢漂移/红噪声竞争解释。",
        f"- 低高频共同PC耦合达到|r|>=0.3且错位对照p<=0.05的有{len(strict_coupling)}项，全部集中在7月31日下午TC1，且背景、STOP、30、50 Hz均出现；它说明该时段存在探测器内部共同状态耦合，不是水流特异性。",
        f"- duo同场TC1/TC2同步检验为0/{len(synchrony)}通过；跨通道相干的本地对照变化绝对值最大仅{common_coherence['median_pair_difference'].abs().max():.4f}。没有找到跨探测器共同低频外场主干。",
        f"- VFD RUN相对早期背景在1-2 s Allan尺度上常增大，但相对STOP仅{int(((run_allan['reference_condition']=='vfd_stop') & (run_allan['median_allan_amplitude_ratio_db']>0)).sum())}/{len(run_allan[run_allan['reference_condition']=='vfd_stop'])}为正，不能作为稳定运行特征。",
        f"- 最强的新增时域候选出现在5 s Allan尺度：RUN相对STOP在{int(allan_5s_stop['stratum_negative_count'])}/{int(allan_5s_stop['stratum_count'])}个‘日期/摆位/探测器’层级下降，但单文件仅{int(allan_5s_stop['sample_negative_count'])}/{int(allan_5s_stop['sample_count'])}下降；相对纯背景则为{int(allan_5s_background['sample_negative_count'])}/{int(allan_5s_background['sample_count'])}下降。它提示STOP状态可能带有约5 s波动，尚不是水流或通用RUN特征。",
        "",
        "结论是：当前数据没有检出声学观察到的3.1 s电信号周期，也没有发现其他通过红噪声检验的稳定低频周期。这里的阴性结论是‘未检出’，不是证明水流电信号绝对不存在。",
        "",
        "## 6. 高频窄线与载波",
        "",
        f"VFD RUN相对STOP的平均谱中，每个文件可找到3-30条同频点增益超过3 dB的候选窄线，最大可达{run_narrow['maximum_same_bin_contrast_db'].max():.2f} dB；但加入±300 Hz邻域参考和逐段出现率后，只有{int(run_narrow['robust_persistent_line_count'].sum())}条候选同时在至少半数健康通道中达到20%出现率。",
        f"STOP相对背景本身也产生{int(stop_narrow['robust_line_count'].sum())}条邻域增强候选，说明窄线位置会随时间、探测器状态和参考文件漂移。少数持续候选集中在约123.5-124 kHz，跨4/8/12 kHz设定存在，因而不是设定载波的移动峰。",
        "",
        "既有精确载波检验中，实际4/8/12 kHz设定仅在12个文件中的3个成为最强候选，谐波梳状得分也无稳定排序。因此：可以检测局部窄线发生变化，但不能由窄线频率识别载波设置，更不能把某一窄线唯一归因于VFD功率器件。",
        "",
        "## 7. 30/50 Hz与工况识别",
        "",
        f"将‘80-200 kHz增量减20-80 kHz增量’定义为重分配分数后，50 Hz在后期{higher_50}/{len(recent_pairing)}个‘日期/摆位/探测器’配对中高于30 Hz；6月17日早期参考为{historical_higher_50}/{len(historical_pairing)}同方向。但7月31日下午TC1反向，且每个配对缺少独立重复和未知标签验证，所以它只是候选趋势，不是可交付分类器。",
        "",
        "当前识别能力分层：有本地背景时可检出RUN相对背景的成对组差异；若未知样本还可能是STOP，则尚不能特异识别RUN。30与50、4/8/12 kHz载波和水流本身也不能稳定识别。",
        "",
        "## 8. 主动脉冲实验对传感器能力的补充",
        "",
        f"6月9日保留了188个主动脉冲工况、每工况3次重复。样本量化台阶中位数为{legacy_summary['mean_quantization_step_estimate'].median()*1e3:.4f} mV，{np.mean(legacy_summary['baseline_instability_ratio'] <= 0.1):.1%}的‘工况×通道’重复均值波动不超过本通道robust sigma的10%。",
        f"一阶脉冲的60个‘模式×接法×通道’幅值序列中，有{len(practical_pulse)}个同时满足AC RMS对电压|Spearman rho|>=0.8、p<=0.05且相对变化>=5%；这些集中在少数通道，方向还会随接法改变。它证明系统对主动强扰动有可重复响应，也证明响应属于整个有源网络而非所有通道共享的简单标量。",
        "",
        "当前健康通道原始采样标准差约3-5 mV，量化台阶约0.323 mV。通过频带平均、跨时间积累和本地配对可以分辨远小于4 mV原始宽带波动的统计变化；这不等于单次瞬时电压的检出限，也不能把0.01 dB频带变化直接换算为某个外场微伏值。",
        "",
        "## 9. 最终结论",
        "",
        "1. 本传感器首先表现为有偏置、慢漂移、通道异质和探测器依赖的有源动态网络；逐文件健康判断和本机背景是分析前提。",
        "2. 当前最可靠的被动结果是RUN相对本地背景的20-80/80-200 kHz双频带重分配，后期实验24/24复现，早期6/6仅作方向支持；但STOP有4/8同方向，故它证明成对组差异，不足以特异判定未知样本为RUN。",
        "3. 高频窄线变化可很大，但频率与持续性依赖探测器和时段；它适合做本地变化告警，不适合做统一物理源标签。",
        "4. 3.1 s及盲搜低频周期均未通过红噪声检验；现有数据没有水流特异性电信号证据。",
        "5. RUN相对STOP的5 s Allan幅度在8/8层级下降，是当前最强时域候选；但单文件仍有6/24反向且相对背景不稳定，只能解释为待复核的STOP相关状态变化。",
        "6. 载波设置、30/50工况和STOP状态尚不能稳定识别。理论计算继续用于支持‘水流预期很弱’及解释已观察现象，不应替代实验源分离。",
        "",
        "## 10. 输出",
        "",
        "- `spectral_redistribution_score.csv`：运行链双频带指纹及背景漂移倍率。",
        "- `frequency_30_50_pairing.csv`：30/50配对趋势。",
        "- `background_cross_session_ranges.csv`：不同实验背景强度范围。",
        "- `narrow_line_case_summary.csv`：窄线邻域与持续性汇总。",
        "- `run_stop_exploratory_classification.csv`：RUN/STOP样本内判据、误报和验证边界。",
        "- `time_domain_feature_consistency.csv`：慢动态、Allan、网络和相干特征的文件/层级方向一致性。",
        "- `identifiability_matrix.csv`：检测、识别和归因边界。",
        "- `figures/`：核心证据图。",
        "- `legacy_pulse/`：6月9日主动脉冲输出级复核。",
    ]
    (base / "MENTOR_ALIGNED_EVIDENCE_REPORT.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path,
                        default=Path('analysis/mentor_aligned_pre_electrochemical_v1'))
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    base = args.input if args.input.is_absolute() else root / args.input
    figures = base / "figures"
    figures.mkdir(parents=True, exist_ok=True)

    spectral = spectral_redistribution(base)
    pairing = frequency_pairing(spectral)
    ranges = background_ranges(base)
    narrow = narrow_line_summary(base)
    classification = run_stop_exploratory_classification(spectral)
    time_consistency = time_domain_feature_consistency(base)
    identifiability = build_identifiability(pairing, classification)
    spectral.to_csv(base / "spectral_redistribution_score.csv", index=False)
    pairing.to_csv(base / "frequency_30_50_pairing.csv", index=False)
    ranges.to_csv(base / "background_cross_session_ranges.csv", index=False)
    narrow.to_csv(base / "narrow_line_case_summary.csv", index=False)
    classification.to_csv(base / "run_stop_exploratory_classification.csv", index=False)
    time_consistency.to_csv(base / "time_domain_feature_consistency.csv", index=False)
    identifiability.to_csv(base / "identifiability_matrix.csv", index=False)
    plot_spectral_redistribution(spectral, figures / "spectral_redistribution.png")
    plot_frequency_pairing(pairing, figures / "frequency_30_50_pairing.png")
    plot_background_ranges(ranges, figures / "background_cross_session_ranges.png")
    plot_periodicity(base, figures / "water_3p1s_red_noise_test.png")
    plot_narrow_lines(narrow, figures / "narrow_line_temporal_validation.png")
    plot_time_domain_consistency(
        time_consistency, figures / "time_domain_feature_consistency.png"
    )
    write_report(
        base, spectral, pairing, ranges, narrow, identifiability,
        classification, time_consistency,
    )
    print(f"Output: {base}")
    return base


if __name__ == "__main__":
    main()
