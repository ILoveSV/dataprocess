"""Build the result-oriented report after all newly supplied raw data are used."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = PROJECT_ROOT / 'analysis/mentor_aligned_raw_completion_v3'


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


def later_run_rows(frame: pd.DataFrame, reference: str) -> pd.DataFrame:
    return frame[
        frame["dataset"].astype(str).isin(["20260731", "20260806"])
        & frame["condition"].isin(["30hz", "50hz", "run"])
        & (frame["reference_condition"] == reference)
    ].copy()


def stratified_highfrequency(frame: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "pair_coherence_20_80khz_median_difference",
        "pair_coherence_80_200khz_median_difference",
        "pair_phase_locking_20_80khz_median_difference",
        "pair_phase_locking_80_200khz_median_difference",
        "full_bicoherence_max_difference",
        "full_bicoherence_epoch_peak_repeat_fraction_difference",
    ]
    rows = []
    for reference in ("background", "vfd_stop"):
        selected = later_run_rows(frame, reference)
        for metric in metrics:
            values = selected.groupby(
                ["dataset", "arrangement", "detector"]
            )[metric].median().dropna()
            if not len(values):
                continue
            try:
                p_value = float(stats.wilcoxon(values).pvalue)
            except ValueError:
                p_value = 1.0
            rows.append({
                "reference_condition": reference,
                "metric": metric.removesuffix("_difference"),
                "stratum_count": len(values),
                "positive_stratum_count": int(np.sum(values > 0.0)),
                "positive_stratum_fraction": float(np.mean(values > 0.0)),
                "stratum_median_difference": float(np.median(values)),
                "stratum_minimum_difference": float(np.min(values)),
                "stratum_maximum_difference": float(np.max(values)),
                "wilcoxon_p": p_value,
            })
    result = pd.DataFrame(rows)
    result["method_family_fdr"] = bh_adjust(result["wilcoxon_p"].to_numpy())
    return result


def epoch_superiority(
    contrasts: pd.DataFrame, epochs: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    selected = contrasts[
        contrasts["dataset"].astype(str).isin(["20260731", "20260806"])
        & contrasts["condition"].isin(["30hz", "50hz", "run"])
    ].drop_duplicates(["case_id", "reference_case_id"])
    for pair in selected.itertuples(index=False):
        for band in ("20_80khz", "80_200khz"):
            active = epochs[
                (epochs["case_id"] == pair.case_id) & (epochs["band_name"] == band)
            ]
            reference = epochs[
                (epochs["case_id"] == pair.reference_case_id) & (epochs["band_name"] == band)
            ]
            for metric in ("pair_coherence_median", "pair_phase_locking_median"):
                first = active[metric].to_numpy(dtype=float)
                second = reference[metric].to_numpy(dtype=float)
                if not len(first) or not len(second):
                    continue
                rows.append({
                    "dataset": pair.dataset,
                    "case_id": pair.case_id,
                    "arrangement": pair.arrangement,
                    "detector": pair.detector,
                    "condition": pair.condition,
                    "reference_case_id": pair.reference_case_id,
                    "reference_condition": pair.reference_condition,
                    "band_name": band,
                    "metric": metric,
                    "active_epoch_median": float(np.median(first)),
                    "reference_epoch_median": float(np.median(second)),
                    "epoch_superiority_fraction": float(np.mean(first[:, None] > second[None, :])),
                    "mann_whitney_p": float(stats.mannwhitneyu(
                        first, second, alternative="two-sided"
                    ).pvalue),
                })
    return pd.DataFrame(rows)


def memd_significance(frame: pd.DataFrame) -> pd.DataFrame:
    selected = frame[
        frame["dataset"].astype(str).isin(["20260731", "20260806"])
        & frame["condition"].isin(["30hz", "50hz", "run"])
    ].copy()
    metrics = [
        column for column in selected.columns
        if column.endswith("_difference")
        and "reconstruction" not in column
    ]
    rows = []
    for reference in ("background", "vfd_stop"):
        for signal_name in selected["signal_name"].unique():
            subset = selected[
                (selected["reference_condition"] == reference)
                & (selected["signal_name"] == signal_name)
            ]
            for metric in metrics:
                values = subset.groupby(
                    ["dataset", "arrangement", "detector"]
                )[metric].median().dropna()
                if len(values) < 4:
                    continue
                try:
                    p_value = float(stats.wilcoxon(values).pvalue)
                except ValueError:
                    p_value = 1.0
                rows.append({
                    "reference_condition": reference,
                    "signal_name": signal_name,
                    "metric": metric.removesuffix("_difference"),
                    "stratum_count": len(values),
                    "positive_fraction": float(np.mean(values > 0.0)),
                    "median_difference": float(np.median(values)),
                    "wilcoxon_p": p_value,
                })
    result = pd.DataFrame(rows)
    result["method_family_fdr"] = bh_adjust(result["wilcoxon_p"].to_numpy())
    return result


def plot_highfrequency(
    contrasts: pd.DataFrame, identifiability: pd.DataFrame, output: Path,
) -> None:
    selected = later_run_rows(contrasts, "vfd_stop")
    metrics = [
        ("pair_coherence_20_80khz_median_difference", "20-80 kHz coherence"),
        ("pair_coherence_80_200khz_median_difference", "80-200 kHz coherence"),
        ("pair_phase_locking_80_200khz_median_difference", "80-200 kHz phase locking"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.4))
    positions = np.arange(len(metrics))
    for metric_index, (metric, _) in enumerate(metrics):
        strata = selected.groupby(["dataset", "arrangement", "detector"])[metric].median()
        x = np.full(len(strata), metric_index) + np.linspace(-0.12, 0.12, len(strata))
        axes[0].scatter(x, strata, s=45, color="#3976a8")
        axes[0].plot(
            [metric_index - 0.2, metric_index + 0.2],
            [np.median(strata), np.median(strata)], color="#bf5b45", linewidth=2.0,
        )
    axes[0].axhline(0.0, color="#555555", linewidth=0.8)
    axes[0].set_xticks(positions, [label for _, label in metrics], rotation=15, ha="right")
    axes[0].set_ylabel("RUN minus local STOP")
    axes[0].set_title("Full-record cross-channel change in 8 independent strata")

    run = identifiability[identifiability["task"] == "run_vs_stop"].copy()
    order = [
        "baseline_spectral_only", "v2_methods_only", "full_raw_only",
        "full_raw_phase_coherence", "predefined_coherence_bands",
        "predefined_80_200khz_coherence", "combined_all",
    ]
    run["feature_set"] = pd.Categorical(run["feature_set"], order, ordered=True)
    run = run.sort_values("feature_set")
    axes[1].barh(
        run["feature_set"].astype(str), run["grouped_balanced_accuracy"],
        color=[
            "#777777", "#789d4a", "#3976a8", "#4f8d79",
            "#d49a3a", "#bf5b45", "#8a6f9e",
        ],
    )
    axes[1].axvline(0.5, color="#555555", linestyle="--", linewidth=0.9)
    for y, row in enumerate(run.itertuples(index=False)):
        axes[1].text(
            row.grouped_balanced_accuracy + 0.01, y,
            f"{row.grouped_balanced_accuracy:.3f}, p={row.permutation_p:.3f}",
            va="center", fontsize=9,
        )
    axes[1].set_xlim(0.0, 1.02)
    axes[1].set_xlabel("Leave-one-stratum-out balanced accuracy")
    axes[1].set_title("Unknown-label RUN/STOP recognition")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def build_report(base: Path) -> dict[str, object]:
    high_base = base / "full_raw_highfrequency"
    high = pd.read_csv(high_base / "full_raw_highfrequency_features.csv")
    high_contrasts = pd.read_csv(high_base / "full_raw_highfrequency_matched_contrasts.csv")
    epochs = pd.read_csv(high_base / "full_raw_epoch_features.csv")
    ident = pd.read_csv(base / "identifiability/raw_completion_identifiability_summary.csv")
    ident_predictions = pd.read_csv(
        base / "identifiability/raw_completion_predictions.csv"
    )
    memd = pd.read_csv(base / "projection_memd/projection_memd_matched_contrasts.csv")
    memd_robust = pd.read_csv(base / "projection_memd/projection_memd_parameter_robustness.csv")
    pulse = pd.read_csv(base / "pulse_relaxation/pulse_group_summary.csv")
    pulse_events = pd.read_csv(base / "pulse_relaxation/pulse_transition_models.csv")
    pulse_calibration = pd.read_csv(base / "pulse_relaxation/pulse_voltage_dependence.csv")
    batch = pd.read_csv(base / "batch_20260512/distance_condition_features.csv")
    batch_files = pd.read_csv(
        base / "batch_20260512/file_features_dynamic_health.csv"
    )
    batch_ident = pd.read_csv(base / "batch_20260512/cross_distance_identifiability.csv")
    cross_batch = pd.read_csv(base / "batch_20260512/cross_batch_direction_consistency.csv")

    high_stats = stratified_highfrequency(high_contrasts)
    high_stats.to_csv(base / "FULL_RAW_STRATIFIED_SIGNIFICANCE.csv", index=False)
    epoch_rows = epoch_superiority(high_contrasts, epochs)
    epoch_rows.to_csv(base / "FULL_RAW_EPOCH_SUPERIORITY.csv", index=False)
    memd_stats = memd_significance(memd)
    memd_stats.to_csv(base / "PROJECTION_MEMD_SIGNIFICANCE.csv", index=False)
    plot_highfrequency(high_contrasts, ident, base / "full_raw_recognition_summary.png")

    confusion_rows = []
    for (task, feature_set, true_label), subset in ident_predictions.groupby(
        ["task", "feature_set", "true_label"]
    ):
        confusion_rows.append({
            "task": task,
            "feature_set": feature_set,
            "true_label": true_label,
            "sample_count": len(subset),
            "correct_count": int(np.sum(subset["true_label"] == subset["predicted_label"])),
            "class_recall": float(np.mean(
                subset["true_label"] == subset["predicted_label"]
            )),
        })
    confusion = pd.DataFrame(confusion_rows)
    confusion.to_csv(base / "IDENTIFIABILITY_CLASS_RECALL.csv", index=False)

    carrier = high[high["carrier_khz"].notna()]
    broad_classifier = ident[
        (ident["task"] == "run_vs_stop")
        & (ident["feature_set"] == "full_raw_phase_coherence")
    ].iloc[0]
    classifier = ident[
        (ident["task"] == "run_vs_stop")
        & (ident["feature_set"] == "predefined_80_200khz_coherence")
    ].iloc[0]
    tc1_classifier = ident[
        (ident["task"] == "run_vs_stop_tc1")
        & (ident["feature_set"] == "predefined_80_200khz_coherence")
    ].iloc[0]
    tc2_classifier = ident[
        (ident["task"] == "run_vs_stop_tc2")
        & (ident["feature_set"] == "predefined_80_200khz_coherence")
    ].iloc[0]
    tc2_combined = ident[
        (ident["task"] == "run_vs_stop_tc2")
        & (ident["feature_set"] == "combined_all")
    ].iloc[0]
    selected_recall = confusion[
        (confusion["task"] == "run_vs_stop")
        & (confusion["feature_set"] == "predefined_80_200khz_coherence")
    ].set_index("true_label")["class_recall"]
    coherence = high_stats[
        (high_stats["reference_condition"] == "vfd_stop")
        & (high_stats["metric"] == "pair_coherence_80_200khz_median")
    ].iloc[0]
    epoch_selected = epoch_rows[
        epoch_rows["reference_condition"].eq("vfd_stop")
        & epoch_rows["band_name"].eq("80_200khz")
        & epoch_rows["metric"].eq("pair_coherence_median")
    ]
    epoch_selected = epoch_selected.assign(
        epoch_median_difference=(
            epoch_selected["active_epoch_median"]
            - epoch_selected["reference_epoch_median"]
        )
    )
    epoch_strata = epoch_selected.groupby(
        ["dataset", "arrangement", "detector"]
    )["epoch_median_difference"].median()
    pulse = pulse.copy()
    pulse["period_method_family_fdr"] = bh_adjust(
        pulse["nearby_period_surrogate_p"].to_numpy()
    )
    pulse.to_csv(base / "PULSE_PERIOD_SPECIFICITY_FDR.csv", index=False)
    pulse_nominal_significant = int(np.sum(
        pulse["nearby_period_surrogate_p"] <= 0.05
    ))
    pulse_significant = int(np.sum(pulse["period_method_family_fdr"] <= 0.05))
    pulse_repeatable = int(np.sum(pulse["segment_profile_correlation_median"] >= 0.5))
    pulse_exponential_templates = int(np.sum(
        pulse["template_alignment_type"] == "exponential_relaxation"
    ))
    pulse_template_correlated = int(np.sum(
        pulse["template_correlation"].abs() >= 0.25
    ))
    pulse_credible = int(pulse_events["credible_relaxation"].astype(bool).sum())
    calibration = pulse_calibration.copy()
    calibration["fdr"] = bh_adjust(calibration["spearman_p"].to_numpy())
    calibration.to_csv(base / "PULSE_VOLTAGE_DEPENDENCE_FDR.csv", index=False)
    calibration_associations = int(np.sum(
        (calibration["fdr"] <= 0.05) & (calibration["spearman_rho"].abs() >= 0.8)
    ))
    memd_positive = int(np.sum(memd_stats["method_family_fdr"] <= 0.05))
    batch_three = batch_ident[
        (batch_ident["task"] == "0_30_50_cross_distance")
        & (batch_ident["feature_set"] == "combined")
    ].iloc[0]
    batch_two = batch_ident[
        (batch_ident["task"] == "30_50_cross_distance")
        & (batch_ident["feature_set"] == "combined")
    ].iloc[0]
    batch_period_columns = [
        column for column in batch.columns
        if column.endswith("_3p1s_red_noise_familywise_p")
    ]
    batch_period_significant = int(np.sum(
        batch[batch_period_columns].to_numpy(dtype=float) <= 0.05
    ))

    coverage = pd.DataFrame([
        {"method": "full-record high-frequency phase/coherence", "status": "complete", "result": "paired positive; compact blind recognition exploratory and detector-dependent"},
        {"method": "full-record bicoherence epoch repeatability", "status": "complete", "result": "network-wide nonlinear structure; not water-specific"},
        {"method": "4/8/12 kHz carrier harmonic-comb tracking", "status": "complete", "result": "negative carrier identification"},
        {"method": "strict projection MEMD", "status": "complete", "result": "method completed; condition result determined by FDR table"},
        {"method": "raw pulse-period locking", "status": "complete", "result": "exact-period and segment-repeatability gates applied"},
        {"method": "raw triggered relaxation models", "status": "complete", "result": "single/double exponential and matrix-pencil gates applied"},
        {"method": "20260512 cross-distance generalization", "status": "complete", "result": "360 files treated as nine runs"},
        {"method": "old cathodic positive-control recheck", "status": "complete_separate", "result": "kept outside pre-electrochemical evidence"},
        {"method": "audio/video synchronized cross-modal analysis", "status": "data_unavailable", "result": "no media files on supplied E:\\Lab tree"},
    ])
    coverage.to_csv(base / "RAW_COMPLETION_METHOD_COVERAGE.csv", index=False)
    results = pd.DataFrame([
        {"question": "Can RUN be separated from STOP?", "grade": "exploratory_positive", "result": f"predefined 80-200 kHz coherence BA={classifier.grouped_balanced_accuracy:.3f}, permutation p={classifier.permutation_p:.3f}; external validation required"},
        {"question": "Does the same RUN/STOP feature generalize across detectors?", "grade": "detector_dependent", "result": f"TC1 BA={tc1_classifier.grouped_balanced_accuracy:.3f}, p={tc1_classifier.permutation_p:.3f}; TC2 BA={tc2_classifier.grouped_balanced_accuracy:.3f}, p={tc2_classifier.permutation_p:.3f}"},
        {"question": "Is cross-channel coherence consistently changed?", "grade": "positive", "result": f"{int(coherence.positive_stratum_count)}/{int(coherence.stratum_count)} strata positive vs STOP"},
        {"question": "Can 4/8/12 kHz carrier be identified?", "grade": "negative", "result": f"harmonic-comb accuracy {carrier.carrier_comb_prediction_correct.mean():.3f}"},
        {"question": "Is a water-specific 30/50 feature available?", "grade": "negative", "result": "grouped 30/50 recognition remains nonsignificant"},
        {"question": "Is a credible pulse relaxation waveform present?", "grade": "positive_if_nonzero" if pulse_credible else "negative", "result": f"{pulse_credible}/{len(pulse_events)} transitions pass all gates"},
        {"question": "Does strict MEMD add a condition feature?", "grade": "positive_if_nonzero" if memd_positive else "negative", "result": f"{memd_positive}/{len(memd_stats)} parameterized tests pass FDR"},
        {"question": "Does 20260512 generalize across distance?", "grade": "exploratory", "result": f"3-class BA={batch_three.balanced_accuracy:.3f}; 30/50 BA={batch_two.balanced_accuracy:.3f}"},
    ])
    results.to_csv(base / "RAW_COMPLETION_RESULT_MATRIX.csv", index=False)

    report = f"""# 导师建议原始数据补全分析报告

## 1. 结论先行

**整段原始高频数据增加了一个此前三短窗无法得到的实质结果：RUN链会提高跨通道高频相干。** RUN相对本地STOP时，80--200 kHz通道对整段相干估计在{int(coherence.positive_stratum_count)}/{int(coherence.stratum_count)}个日期-摆位-探测器层级同向增加，层级中位差为{coherence.stratum_median_difference:.6f}，Wilcoxon p={coherence.wilcoxon_p:.4f}，方法族FDR={coherence.method_family_fdr:.4f}。进一步拆成8个历元后，{int(np.sum(epoch_selected.epoch_median_difference > 0))}/{len(epoch_selected)}个文件配对、{int(np.sum(epoch_strata > 0))}/{len(epoch_strata)}个独立层级的历元中位数仍为正；历元优胜比例中位数为{epoch_selected.epoch_superiority_fraction.median():.3f}。因此它是有用候选，但存在一个TC2摆位的时间局部反向，不能写成无条件稳定。

使用全部整段相干与相位候选特征，RUN/STOP整组留一平衡准确率为{broad_classifier.grouped_balanced_accuracy:.3f}，499次组内标签置换p={broad_classifier.permutation_p:.3f}。进一步只保留预定义80--200 kHz相干中位数及其历元中位数后，平衡准确率为{classifier.grouped_balanced_accuracy:.3f}，p={classifier.permutation_p:.3f}；STOP召回率{selected_recall.get('stop', np.nan):.3f}，RUN召回率{selected_recall.get('run', np.nan):.3f}。分探测器后，TC1为{tc1_classifier.grouped_balanced_accuracy:.3f}、p={tc1_classifier.permutation_p:.3f}，TC2为{tc2_classifier.grouped_balanced_accuracy:.3f}、p={tc2_classifier.permutation_p:.3f}；TC2需合并旧时域和完整高频特征才达到{tc2_combined.grouped_balanced_accuracy:.3f}、p={tc2_combined.permutation_p:.3f}。因此现有数据支持“按探测器建立的运行链状态探索性识别”，不支持一套跨探测器通用规则。80--200 kHz频带是在本研究证据形成过程中确定的，必须在新批次锁定参数外部验证；更不能把RUN标签改写为水流。

**载波结论没有改变。** 4/8/12 kHz谐波梳状模板仅正确{int(carrier.carrier_comb_prediction_correct.sum())}/{len(carrier)}，设定载波得分相对其他模板的中位优势为{carrier.configured_carrier_comb_margin_db.median():.3f} dB；不能识别载波档位。

**30/50 Hz与水流识别仍没有阳性。** 整段原始相干没有改善30/50分类；5月360文件的跨距离结果也未提供可部署的水流标签。

## 2. 主实验整段高频

- 49个文件各从完整稳定区间均匀抽取96个40.96 ms原始窗口，不再由三个1 s片段代表整段。
- 每文件动态使用健康通道；TC1、TC2仍分别相对本机背景和STOP分析。
- 双相干在{int(np.sum(high.full_bicoherence_surrogate_p <= 0.05))}/{len(high)}文件超过19次相位代理；历元峰重复比例中位数{high.full_bicoherence_epoch_peak_repeat_fraction.median():.3f}。它说明系统的非线性混频比三短窗显示得更持续，但背景和STOP同样存在，因此不具备水流特异性。

## 3. 主动脉冲与弛豫

- 完整处理{len(pulse)}个脉冲工况、{len(pulse_events)}个状态转换。
- 每个脉冲工况独立判断坏道，健康通道数范围{int(pulse.healthy_channel_count.min())}--{int(pulse.healthy_channel_count.max())}。
- 精确重复频率相对附近伪频率名义p不超过0.05的工况：{pulse_nominal_significant}/{len(pulse)}；跨188工况方法族FDR后为{pulse_significant}/{len(pulse)}。每组99个伪周期使最小p为0.01，因此全局FDR结果是保守边界，不单独用于宣称周期响应不存在。三段波形中位相关至少0.5的工况：{pulse_repeatable}/{len(pulse)}。
- 方波电平、瞬时边沿和32档指数核模板联合比较后，最佳模板为指数迟豫的工况{pulse_exponential_templates}/{len(pulse)}；但|模板相关|至少0.25的仅{pulse_template_correlated}/{len(pulse)}。
- 同时通过周期特异、三段重复、模板相关、事件SNR、AICc、R2、时间常数可辨识和跨段tau稳定门槛的弛豫：{pulse_credible}/{len(pulse_events)}。
- 电压依赖在方法族FDR后达到|rho|>=0.8的统计关联：{calibration_associations}/{len(calibration)}；必须结合实际相关幅值和方向解释，不能自动记为正向剂量响应。

## 4. 严格投影MEMD

- 已完成真正的多通道投影包络与共同IMF提取，不再使用逐通道EMD频带对齐代替MEMD。
- 16/24方向下主导中心频率差的中位数为{memd_robust.dominant_center_absolute_difference_hz.median():.4f} Hz，90%分位为{memd_robust.dominant_center_absolute_difference_hz.quantile(0.9):.4f} Hz。
- 工况对照中通过方法族FDR的参数化特征为{memd_positive}/{len(memd_stats)}。详细阴性或阳性条目见`PROJECTION_MEMD_SIGNIFICANCE.csv`。

## 5. 2026-05-12跨距离批次

- 360个连续短文件按9个距离-工况运行处理，未把相邻文件当作独立重复。
- 360个文件逐文件动态判断坏道，健康通道数范围{int(batch_files.healthy_channel_count.min())}--{int(batch_files.healthy_channel_count.max())}。
- 3.1 s固定周期在5种信号代理乘9个运行组的红噪声全频搜索中，族错误率校正后阳性{batch_period_significant}/{len(batch) * len(batch_period_columns)}。
- 0/30/50三分类跨距离平衡准确率{batch_three.balanced_accuracy:.3f}，置换p={batch_three.permutation_p:.3f}；30/50二分类为{batch_two.balanced_accuracy:.3f}，p={batch_two.permutation_p:.3f}。
- 与6月17日相同方向的频带-工况组合为{int(cross_batch.batch_median_same_direction.sum())}/{len(cross_batch)}。两个批次均表现为20--80 kHz轻微下降、80--200 kHz轻微上升，但30 Hz和50 Hz方向相同；这支持运行链宽频带重分配的跨批次复现，不支持30/50特异识别，也不能用文件数量制造显著性。

## 6. 旧阴极保护数据边界

8月11日两批已经按完整精确归档做过动态坏道、固定频率、手动开关、边沿、剂量与重复性检查。本轮继续单独保留：旧电极间距约1 cm且没有同步电流波形，不能把它们混入水流识别或最终阴极保护检出结论。

## 7. 文件索引

- 导师方法全覆盖的上一阶段总报告：`analysis/mentor_aligned_methods_v2/MENTOR_METHOD_EXPLORATION_REPORT.md`；其中包含CWT/交叉小波/SST、EMD/EEMD/VMD、复杂性、网络、非线性与滤波审计。本报告只记录原始数据到位后新增或被修正的结果。
- `RAW_COMPLETION_METHOD_COVERAGE.csv`：新增原始数据方法覆盖。
- `RAW_COMPLETION_RESULT_MATRIX.csv`：结果层级矩阵。
- `FULL_RAW_STRATIFIED_SIGNIFICANCE.csv`：整段高频层级检验。
- `FULL_RAW_EPOCH_SUPERIORITY.csv`：文件内部历元复现。
- `PULSE_VOLTAGE_DEPENDENCE_FDR.csv`：脉冲电压依赖多重校正。
- `PULSE_PERIOD_SPECIFICITY_FDR.csv`：188工况目标周期的跨工况多重校正。
- `PROJECTION_MEMD_SIGNIFICANCE.csv`：严格MEMD工况对照。
- `IDENTIFIABILITY_CLASS_RECALL.csv`：盲识别各类别召回率，避免只看单一准确率。
"""
    (base / "RAW_COMPLETION_REPORT.md").write_text(report, encoding="utf-8")
    summary = {
        "status": "complete",
        "full_raw_case_count": len(high),
        "run_stop_phase_coherence_balanced_accuracy": float(classifier.grouped_balanced_accuracy),
        "run_stop_phase_coherence_permutation_p": float(classifier.permutation_p),
        "run_stop_tc1_predefined_balanced_accuracy": float(tc1_classifier.grouped_balanced_accuracy),
        "run_stop_tc1_predefined_permutation_p": float(tc1_classifier.permutation_p),
        "run_stop_tc2_predefined_balanced_accuracy": float(tc2_classifier.grouped_balanced_accuracy),
        "run_stop_tc2_predefined_permutation_p": float(tc2_classifier.permutation_p),
        "carrier_correct_count": int(carrier.carrier_comb_prediction_correct.sum()),
        "carrier_case_count": len(carrier),
        "pulse_group_count": len(pulse),
        "pulse_credible_relaxation_count": pulse_credible,
        "memd_fdr_significant_count": memd_positive,
        "batch_20260512_group_count": len(batch),
    }
    (base / "REPORT_SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    args = parser.parse_args()
    summary = build_report(args.base)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
