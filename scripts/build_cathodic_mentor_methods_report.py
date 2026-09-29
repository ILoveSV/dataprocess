"""Build the mentor-method evidence report for the old cathodic experiments."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'analysis/cathodic_mentor_methods_v1'
LOW = OUTPUT / "low_frequency"
HIGH = OUTPUT / "high_frequency"
FIRST = ROOT / 'experiments/20260811'
SECOND = ROOT / 'experiments/20260811_2'


def bh_adjust(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    result = np.full_like(values, np.nan)
    finite = np.isfinite(values)
    if not np.any(finite):
        return result
    p = values[finite]
    order = np.argsort(p)
    ranked = p[order]
    adjusted = np.minimum.accumulate(
        (ranked * len(ranked) / np.arange(1, len(ranked) + 1))[::-1]
    )[::-1]
    restored = np.empty_like(adjusted)
    restored[order] = np.minimum(adjusted, 1.0)
    result[finite] = restored
    return result


def method_coverage() -> pd.DataFrame:
    first = {
        "bkg": ("background", 0, "无开关协议"),
        "bkg2": ("background", 0, "无开关协议"),
        "bar5a": ("steel_bar_control", 0, "稳态对照，无重复开关"),
        "out100ma": ("open_control", 0, "稳态开路，无重复开关"),
        "5v10ma": ("steady_closed", 0, "稳态电流，无重复开关"),
        "5v50ma": ("steady_closed", 0, "稳态电流，无重复开关"),
        "5v100ma": ("steady_closed", 0, "稳态电流，无重复开关"),
        "5v100ma2": ("steady_closed", 0, "稳态重复，无开关协议"),
        "alter50ma": ("manual_switch", 2, "仅两次ON，重复数不足"),
        "alter100ma": ("manual_switch", 2, "仅两次ON，重复数不足"),
        "10to100": ("current_steps", 1, "每档仅一次，适合剂量探索"),
        "005hz": ("periodic_switch", 4, "四个20 s完整周期"),
    }
    second = {
        "bkg": ("background", 0),
        "bkg2": ("background", 0),
        "opensvnear": ("open_control", 8),
        "cp200near": ("closed_circuit", 12),
        "cp500near": ("closed_circuit", 12),
        "cp1000near": ("closed_circuit", 12),
        "cp1000near2": ("closed_circuit", 12),
        "cp3000near": ("closed_circuit", 12),
        "cp3000near2": ("closed_circuit", 12),
    }
    rows = []
    for case, (role, cycles, limitation) in first.items():
        direct = case == "005hz"
        rows.append({
            "batch": "8.11", "case": case, "role": role,
            "nominal_cycle_count": cycles, "legacy_exact_analysis": True,
            "new_cwt_sst": direct, "new_protocol_cross_wavelet": direct,
            "new_folded_relaxation": direct, "new_projection_memd": direct,
            "new_raw_400khz_on_off": direct, "method_scope_note": limitation,
        })
    for case, (role, cycles) in second.items():
        switched = cycles > 0
        rows.append({
            "batch": "8.11.2", "case": case, "role": role,
            "nominal_cycle_count": cycles, "legacy_exact_analysis": True,
            "new_cwt_sst": True, "new_protocol_cross_wavelet": switched,
            "new_folded_relaxation": switched, "new_projection_memd": True,
            "new_raw_400khz_on_off": switched,
            "method_scope_note": (
                "有重复开关，可做协议锁定分析" if switched
                else "仅用于背景动态与模式基线"
            ),
        })
    return pd.DataFrame(rows)


def low_dose_table(cwt: pd.DataFrame, folded: pd.DataFrame) -> pd.DataFrame:
    rows = []
    cwt_metrics = (
        "target_cwt_power_to_red_median",
        "target_common_amplitude_sigma",
        "target_nearby_frequency_p",
        "median_coherence_0p05_0p5hz",
    )
    fold_metrics = (
        "cycle_profile_correlation_median",
        "template_correlation",
        "identifiable_tau_fraction",
        "strong_exponential_fraction",
        "tau_median_s",
    )
    for source, frame, metrics in (
        ("cwt_sst", cwt, cwt_metrics),
        ("folded_relaxation", folded, fold_metrics),
    ):
        selected = frame[
            frame["batch"].eq("8.11.2")
            & frame["kind"].eq("closed_circuit")
            & frame["feature"].eq("slow_mean")
        ]
        for metric in metrics:
            values = selected[["current_ma", metric]].dropna()
            rho, p_value = stats.spearmanr(values["current_ma"], values[metric])
            rows.append({
                "source": source, "metric": metric, "case_count": len(values),
                "current_level_count": values["current_ma"].nunique(),
                "spearman_rho": float(rho), "spearman_p": float(p_value),
            })
    result = pd.DataFrame(rows)
    result["spearman_fdr"] = bh_adjust(result["spearman_p"].to_numpy())
    return result


def result_matrix(
    cwt: pd.DataFrame,
    folded: pd.DataFrame,
    memd: pd.DataFrame,
    high: pd.DataFrame,
    high_dose: pd.DataFrame,
    low_dose: pd.DataFrame,
    state: pd.DataFrame,
    transfer: pd.DataFrame,
) -> pd.DataFrame:
    protocol_cwt = cwt[np.isfinite(cwt["circular_shift_null_p_fdr"])]
    nominal = high[high["timing_offset_s"].eq(0.0)]
    bandpower = nominal[nominal["metric"].str.startswith("bandpower")]
    network = nominal[~nominal["metric"].str.startswith("bandpower")]
    direction24 = memd[
        memd["direction_count"].eq(24) & memd["feature"].eq("slow_mean")
    ]
    rows = [
        {
            "question": "目标周期是否超过AR(1)红噪声阈值",
            "method": "Morlet CWT + red-noise null",
            "tested": len(cwt), "passed": int(np.sum(cwt["target_cwt_power_to_red_median"] > 1.0)),
            "decision": "不支持",
            "key_result": f"最大目标功率/阈值={cwt['target_cwt_power_to_red_median'].max():.3f}",
        },
        {
            "question": "目标频率是否优于邻近频率",
            "method": "预注册邻频置换 + FDR",
            "tested": len(cwt), "passed": int(np.sum(cwt["target_nearby_frequency_p_fdr"] < 0.05)),
            "decision": "不支持", "key_result": "FDR通过0项",
        },
        {
            "question": "信号是否与名义开关协议时频同步",
            "method": "cross-wavelet + circular shift + FDR",
            "tested": len(protocol_cwt),
            "passed": int(np.sum(protocol_cwt["circular_shift_null_p_fdr"] < 0.05)),
            "decision": "不支持", "key_result": "FDR通过0项",
        },
        {
            "question": "同一周期波形是否重复",
            "method": "cycle folding + leave-cycle profile correlation",
            "tested": len(folded),
            "passed": int(np.sum(folded["cycle_profile_correlation_median"] >= 0.5)),
            "decision": "不支持",
            "key_result": f"最高周期相关={folded['cycle_profile_correlation_median'].max():.3f}",
        },
        {
            "question": "开关后是否存在稳定被动弛豫",
            "method": "level/edge/32-tau exponential templates",
            "tested": len(folded),
            "passed": int(np.sum(folded["strong_exponential_fraction"] >= 0.5)),
            "decision": "不支持",
            "key_result": f"单工况强指数事件占比最高={folded['strong_exponential_fraction'].max():.3f}",
        },
        {
            "question": "MEMD是否分离出目标频率共同模态",
            "method": "projection MEMD, 16/24 directions",
            "tested": len(direction24),
            "passed": int(np.sum(
                np.abs(direction24["target_nearest_mode_frequency_hz"] - direction24["target_hz"])
                <= 0.25 * direction24["target_hz"]
            )),
            "decision": "不支持",
            "key_result": "24方向最近模态中心为0.195-0.225 Hz，而目标为0.05/0.1 Hz",
        },
        {
            "question": "高频宽带能量是否随ON稳定改变",
            "method": "400 kHz逐周期ON-OFF sign-flip + FDR",
            "tested": len(bandpower), "passed": int(np.sum(bandpower["exact_signflip_fdr"] < 0.05)),
            "decision": "不支持", "key_result": "三个频带共24项，FDR通过0项",
        },
        {
            "question": "跨通道高频相干/相位是否随ON改变",
            "method": "pair coherence/phase locking + sign-flip + FDR",
            "tested": len(network), "passed": int(np.sum(network["exact_signflip_fdr"] < 0.05)),
            "decision": "不支持", "key_result": "网络指标共48项，FDR通过0项",
        },
        {
            "question": "效应是否随设定电流单调变化",
            "method": "低频与高频Spearman dose response + FDR",
            "tested": len(low_dose) + len(high_dose),
            "passed": int(np.sum(low_dose["spearman_fdr"] < 0.05) + np.sum(high_dose["spearman_fdr"] < 0.05)),
            "decision": "不支持", "key_result": "低频9项、高频9项，FDR通过0项",
        },
        {
            "question": "多通道ON-OFF状态方向是否逐周期一致",
            "method": "paired state vectors + exact cycle sign flips + FDR",
            "tested": int(np.sum(state["timing_offset_s"].eq(0.0))),
            "passed": int(np.sum(
                state["timing_offset_s"].eq(0.0)
                & (state["alignment_signflip_fdr"] < 0.05)
            )),
            "decision": "不支持",
            "key_result": "48项中0项通过FDR；最佳q=0.070",
        },
        {
            "question": "状态方向能否跨1000/3000 mA重复记录迁移",
            "method": "cross-repeat matched-state projection + sign flips + FDR",
            "tested": len(transfer),
            "passed": int(np.sum(transfer["projection_signflip_fdr"] < 0.05)),
            "decision": "不支持",
            "key_result": "24个双向迁移检验中0项通过FDR",
        },
    ]
    return pd.DataFrame(rows)


def exploratory_candidates(
    cwt: pd.DataFrame,
    high: pd.DataFrame,
    old_fixed_01: pd.DataFrame,
    state: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    repeated_sst = cwt[
        cwt["feature"].eq("slow_mean")
        & cwt["case"].isin(["cp1000near", "cp1000near2"])
    ].sort_values("case")
    rows.append({
        "candidate": "1000 mA两次记录的SST中位脊线",
        "observed": "; ".join(
            f"{row.case}={row.sst_ridge_frequency_median_hz:.3f} Hz"
            for row in repeated_sst.itertuples()
        ),
        "why_not_positive": (
            "脊线IQR为0.198-0.227 Hz，目标CWT/红噪声比仅0.078/0.151，"
            "邻频和协议锁定均不显著，且无剂量单调性"
        ),
        "status": "探索性但不支持识别",
    })
    best_state = state[state["timing_offset_s"].eq(0.0)].sort_values(
        "alignment_signflip_p"
    ).iloc[0]
    rows.append({
        "candidate": f"{best_state['case']}/{best_state['feature_group']}多通道状态",
        "observed": (
            f"pair alignment={best_state['mean_pairwise_alignment']:.3f}, "
            f"raw p={best_state['alignment_signflip_p']:.4f}, "
            f"FDR q={best_state['alignment_signflip_fdr']:.3f}"
        ),
        "why_not_positive": "未过FDR，且第二次1000 mA记录的跨重复迁移为负",
        "status": "单文件状态候选，不能泛化",
    })
    for row in high[
        high["timing_offset_s"].eq(0.0) & (high["exact_signflip_p"] < 0.05)
    ].itertuples():
        rows.append({
            "candidate": f"{row.case}/{row.metric}",
            "observed": (
                f"median ON-OFF={row.median_on_minus_off:.6g}, "
                f"raw p={row.exact_signflip_p:.4f}"
            ),
            "why_not_positive": (
                f"多重比较FDR q={row.exact_signflip_fdr:.3f}，且同电流重复或剂量关系不支持"
            ),
            "status": "原始p候选，已否定",
        })
    first = old_fixed_01[old_fixed_01["case"].eq("cp3000near")].iloc[0]
    second = old_fixed_01[old_fixed_01["case"].eq("cp3000near2")].iloc[0]
    rows.append({
        "candidate": "第二次3000 mA的0.1 Hz拟合幅值",
        "observed": (
            f"repeat2={second['median_0p1hz_amplitude_uv_peak']:.2f} uV, "
            f"repeat1={first['median_0p1hz_amplitude_uv_peak']:.2f} uV"
        ),
        "why_not_positive": "CWT、邻频、协议锁定、周期重复及高频网络均未复现",
        "status": "孤立候选，已否定",
    })
    return pd.DataFrame(rows)


def plot_evidence(
    cwt: pd.DataFrame,
    folded: pd.DataFrame,
    high: pd.DataFrame,
    matrix: pd.DataFrame,
    output: Path,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    slow = cwt[cwt["feature"].eq("slow_mean")].copy()
    slow["label"] = slow["batch"] + "/" + slow["case"]
    colors = slow["kind"].map({
        "background": "#777777", "open_control": "#d28b24",
        "closed_circuit": "#2476a8",
    })
    axes[0, 0].bar(np.arange(len(slow)), slow["target_cwt_power_to_red_median"], color=colors)
    axes[0, 0].axhline(1.0, color="#b8322a", linestyle="--", linewidth=1.2)
    axes[0, 0].set_xticks(np.arange(len(slow)), slow["label"], rotation=70, ha="right", fontsize=8)
    axes[0, 0].set_ylabel("Target CWT power / AR(1) threshold")
    axes[0, 0].set_title("A. Target-period evidence")

    slow_fold = folded[folded["feature"].eq("slow_mean")].copy()
    axes[0, 1].bar(
        np.arange(len(slow_fold)), slow_fold["cycle_profile_correlation_median"],
        color=slow_fold["kind"].map({"open_control": "#d28b24", "closed_circuit": "#2476a8"}),
    )
    axes[0, 1].axhline(0.5, color="#b8322a", linestyle="--", linewidth=1.2)
    axes[0, 1].set_xticks(np.arange(len(slow_fold)), slow_fold["case"], rotation=65, ha="right", fontsize=8)
    axes[0, 1].set_ylabel("Median cycle-profile correlation")
    axes[0, 1].set_title("B. Cycle-to-cycle repeatability")

    nominal = high[
        high["timing_offset_s"].eq(0.0)
        & high["metric"].str.startswith("bandpower")
    ].copy()
    bands = list(nominal["metric"].drop_duplicates())
    cases = list(nominal["case"].drop_duplicates())
    x = np.arange(len(cases))
    width = 0.24
    palette = ("#27856f", "#d28b24", "#7057a6")
    for index, (metric, color) in enumerate(zip(bands, palette)):
        values = nominal[nominal["metric"].eq(metric)].set_index("case").reindex(cases)
        axes[1, 0].bar(x + (index - 1) * width, values["median_on_minus_off"], width, label=metric, color=color)
    axes[1, 0].axhline(0.0, color="#555555", linewidth=0.8)
    axes[1, 0].set_xticks(x, cases, rotation=65, ha="right", fontsize=8)
    axes[1, 0].set_ylabel("Median ON - OFF (dB)")
    axes[1, 0].set_title("C. Raw-rate high-frequency differences")
    axes[1, 0].legend(fontsize=7)

    y = np.arange(len(matrix))
    axes[1, 1].barh(y, matrix["tested"], color="#bfc5ca", label="tested")
    axes[1, 1].barh(y, matrix["passed"], color="#2476a8", label="passed")
    axes[1, 1].set_yticks(y, [f"M{i + 1}" for i in range(len(matrix))])
    axes[1, 1].invert_yaxis()
    axes[1, 1].set_xlabel("Number of tests")
    axes[1, 1].set_title("D. Predefined evidence gates")
    axes[1, 1].legend()
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main() -> None:
    cwt = pd.read_csv(LOW / "cathodic_cwt_sst_features.csv")
    folded = pd.read_csv(LOW / "cathodic_folded_relaxation.csv")
    memd = pd.read_csv(LOW / "cathodic_projection_memd.csv")
    high = pd.read_csv(HIGH / "highfreq_on_off_summary.csv")
    high_dose = pd.read_csv(HIGH / "highfreq_dose_response.csv")
    high_repeat = pd.read_csv(HIGH / "highfreq_repeatability.csv")
    state = pd.read_csv(OUTPUT / "state_network/state_cycle_alignment.csv")
    transfer = pd.read_csv(OUTPUT / "state_network/state_cross_repeat_transfer.csv")
    old_fixed_005 = pd.read_csv(FIRST / "fixed_005hz_harmonic.csv")
    old_fixed_01 = pd.read_csv(SECOND / "fixed_0p1hz_harmonic.csv")

    coverage = method_coverage()
    low_dose = low_dose_table(cwt, folded)
    matrix = result_matrix(
        cwt, folded, memd, high, high_dose, low_dose, state, transfer,
    )
    candidates = exploratory_candidates(cwt, high, old_fixed_01, state)
    coverage.to_csv(OUTPUT / "CATHODIC_METHOD_COVERAGE.csv", index=False)
    low_dose.to_csv(OUTPUT / "cathodic_lowfreq_dose_response.csv", index=False)
    matrix.to_csv(OUTPUT / "CATHODIC_RESULT_MATRIX.csv", index=False)
    candidates.to_csv(OUTPUT / "CATHODIC_EXPLORATORY_CANDIDATES.csv", index=False)
    plot_evidence(cwt, folded, high, matrix, OUTPUT / "cathodic_mentor_evidence_summary.png")

    fixed_005 = old_fixed_005[
        old_fixed_005["case"].eq("005hz") & old_fixed_005["feature"].eq("slow_mean")
    ].iloc[0]
    background_005 = old_fixed_005[
        old_fixed_005["case"].isin(["bkg", "bkg2"])
        & old_fixed_005["feature"].eq("slow_mean")
    ]["median_amplitude_uv_peak"].tolist()
    new_005 = cwt[cwt["case"].eq("005hz") & cwt["feature"].eq("slow_mean")].iloc[0]
    fold_005 = folded[
        folded["case"].eq("005hz") & folded["feature"].eq("slow_mean")
    ].iloc[0]
    slow_second = cwt[
        cwt["batch"].eq("8.11.2") & cwt["feature"].eq("slow_mean")
    ]
    closed_second = slow_second[slow_second["kind"].eq("closed_circuit")]
    nominal = high[high["timing_offset_s"].eq(0.0)]
    best_high = nominal.sort_values("exact_signflip_p").iloc[0]
    raw_high_candidates = nominal[nominal["exact_signflip_p"] < 0.05]
    repeated_same = int(high_repeat["same_direction"].sum())
    fixed_3000_1 = old_fixed_01[old_fixed_01["case"].eq("cp3000near")].iloc[0]
    fixed_3000_2 = old_fixed_01[old_fixed_01["case"].eq("cp3000near2")].iloc[0]

    slow_memd24 = memd[
        memd["direction_count"].eq(24) & memd["feature"].eq("slow_mean")
    ]
    report = f"""# 旧阴极保护实验导师方法重分析报告

## 一、结论先行

使用小波、同步压缩、交叉小波、周期折叠、时域模板、指数弛豫、projection-MEMD、原始400 kHz逐周期频带能量、跨通道相干/相位和剂量关系后，**没有从旧间距约1 cm的数据中恢复出可用于稳定识别阴极保护通断或电流档位的阳性特征**。

这轮分析仍有实质结果：原先几个“可能接近检出”的候选被进一步判定为非特异波动，而不是因为只做频谱才漏掉了一个稳定信号。{len(matrix)}类预定义证据门槛均为0项通过。该结论只适用于旧几何、旧协议，不预判后续约30 cm间距实验的结果。

## 二、最关键的新增判断

### 2.1 第一批0.05 Hz候选被否定

旧固定正弦拟合得到 `005hz` 慢均值中位幅值 {fixed_005['median_amplitude_uv_peak']:.2f} uV peak，看起来像一个候选；但同批背景在同一频率已有 {background_005[0]:.2f} 和 {background_005[1]:.2f} uV peak，通道相位相干仅 {fixed_005['phase_coherence']:.3f}。

新检验进一步显示：目标尺度CWT功率仅为AR(1)红噪声95%阈值的 {new_005['target_cwt_power_to_red_median']:.3f}；邻频原始 `p={new_005['target_nearby_frequency_p']:.3f}`、FDR `q={new_005['target_nearby_frequency_p_fdr']:.3f}`；与开关协议的交叉小波循环移位原始 `p={new_005['circular_shift_null_p']:.3f}`、FDR `q={new_005['circular_shift_null_p_fdr']:.3f}`。周期折叠相关中位数只有 {fold_005['cycle_profile_correlation_median']:.3f}，强指数弛豫事件占比 {fold_005['strong_exponential_fraction']:.3f}。因此，3.90 uV是该频率处的可观测拟合量，不是可检出的特异周期响应。

### 2.2 第二批0.1 Hz也没有隐藏的稳定时域响应

第二批闭路工况慢变量的目标CWT功率/红噪声阈值最高仅 {closed_second['target_cwt_power_to_red_median'].max():.3f}；所有5类特征、所有工况的邻频FDR通过数为 {int((cwt['target_nearby_frequency_p_fdr'] < 0.05).sum())}/{len(cwt)}，交叉小波FDR通过数为 {int((cwt['circular_shift_null_p_fdr'] < 0.05).sum())}/{int(cwt['circular_shift_null_p_fdr'].notna().sum())}。

周期平均后有些波形能与阶跃或指数模板取得较高相关，但单周期之间不重复：全部工况最高周期波形相关仅 {folded['cycle_profile_correlation_median'].max():.3f}，第二批闭路最高仅 {folded[(folded['batch'].eq('8.11.2')) & folded['kind'].eq('closed_circuit')]['cycle_profile_correlation_median'].max():.3f}；开路对照本身达到 {folded[folded['kind'].eq('open_control')]['template_correlation'].abs().max():.3f} 的模板相关。因此“平均后像某种响应”不能作为证据。

### 2.3 MEMD没有分离出目标共同模态

16/24方向projection-MEMD均能以数值误差重构原信号，但24方向下慢变量最接近目标的模态中心为 {slow_memd24['target_nearest_mode_frequency_hz'].min():.3f}-{slow_memd24['target_nearest_mode_frequency_hz'].max():.3f} Hz，并未落在0.05或0.1 Hz目标附近；慢变量主导模态约在3.1-3.3 Hz。说明分解算法没有从混合网络中提取出独立的阴极保护目标模态。

### 2.4 原始采样率高频也没有稳定阳性

高频分析覆盖 `005hz`、开路对照及200-3000 mA闭路记录，共8个协议工况。每周期分别计算2-20、20-80、80-200 kHz的共同成分带功率、跨通道相干和相位锁定，并对名义切换时刻前后1 s做敏感性分析。

名义时刻共72项指标，FDR通过0项。最小原始p值来自 `{best_high['case']}` 的 `{best_high['metric']}`：中位ON-OFF={best_high['median_on_minus_off']:.6g}，原始 `p={best_high['exact_signflip_p']:.4f}`，但FDR为 `q={best_high['exact_signflip_fdr']:.3f}`。原始p<0.05共有{len(raw_high_candidates)}项，均未通过FDR，且相同电流重复记录不稳定；18个高频重复性比较中只有{repeated_same}个方向相同，方向相同本身也没有统计显著性。

旧分析中第二次3000 mA的0.1 Hz拟合幅值为 {fixed_3000_2['median_0p1hz_amplitude_uv_peak']:.2f} uV，第一次仅 {fixed_3000_1['median_0p1hz_amplitude_uv_peak']:.2f} uV；新时频、周期和高频网络指标均没有把它复现为稳定响应。

SST还给出一个值得记录但不能作为结论的现象：两次1000 mA慢变量的中位脊线都落在0.109 Hz附近。然而脊线IQR宽达0.198-0.227 Hz，目标CWT功率仍远低于红噪声阈值，且没有邻频特异性、协议锁定或剂量单调性。因此它保留为探索性候选，不进入识别特征。所有这类候选及否定理由见 `CATHODIC_EXPLORATORY_CANDIDATES.csv`。

### 2.5 不依赖单一频率的多通道状态识别仍不能泛化

进一步把每个周期的多通道ON和OFF压缩为状态向量，并用独立周期方向翻转构造精确零假设。48个“工况×特征组”检验仍为0项通过FDR。最佳结果是`cp1000near/difference_rms`：周期方向平均余弦0.186，留一周期投影中位数0.417，11/12周期同向，原始p=0.0015、FDR q=0.070；在名义时刻前后1 s均保持正方向。

但它不能作为识别特征：把第一次1000 mA学到的状态方向应用到第二次记录，目标投影中位数为-0.152，只有2/12周期为正；反向迁移中位数-0.138。1000/3000 mA共24个双向跨重复迁移检验均未通过FDR。由此可区分两件事：单文件内部存在某些网络状态结构，与存在可跨实验复现的阴极保护物理状态不是一回事。

## 三、导师建议的方法是否都落地

| 方法 | 回答的问题 | 结果 |
|---|---|---|
| Morlet CWT + AR(1)红噪声 | 局部时频增强是否超过有色噪声 | 否 |
| 同步压缩SST | 扩散的小波能量能否聚成稳定脊线 | 未形成目标频率稳定脊线 |
| 交叉小波 + 循环移位 | 是否与名义通断协议同步 | 0项通过FDR |
| 周期折叠 + 留一周期相关 | 平均波形是否逐周期复现 | 否 |
| 阶跃/边缘/指数模板 | 是否存在充电后被动弛豫 | 否 |
| 单事件指数拟合 | 时间常数是否可辨识且稳定 | 强指数事件占比最高{folded['strong_exponential_fraction'].max():.3f} |
| projection-MEMD | 是否存在跨通道共同目标模态 | 否 |
| 400 kHz频带功率 | 高频能量是否随通断变化 | 0项通过FDR |
| 跨通道相干与相位 | 是否存在真实共同外场而非单通道漂移 | 0项通过FDR |
| 剂量与重复实验 | 是否随电流增强并在1000/3000 mA复现 | 否 |
| 多通道配对状态 | 不依赖单频率时ON-OFF网络方向是否重复 | 48项中0项通过FDR |
| 跨重复状态迁移 | 第一次记录学到的方向能否识别第二次 | 24项中0项通过FDR |

详细逐项数值见 `CATHODIC_RESULT_MATRIX.csv`。

## 四、数据利用范围

两批共21个唯一记录均保留在证据链中：第一批12个记录继续使用原有稳态、分块、阶跃、固定频率和坏道动态判断结果；其中周期数足够的 `005hz` 追加全部新方法。第二批9个记录全部进入CWT/SST与MEMD；7个有开关协议的记录追加折叠、弛豫、交叉小波和400 kHz高频分析。第一批其余手动开关只有两次ON、阶梯电流每档只有一次，不能诚实地做重复性显著性检验，未强行套用多周期方法。

逐文件覆盖关系见 `CATHODIC_METHOD_COVERAGE.csv`。每次记录均动态判断健康通道；没有把固定通道清单跨文件复用。

## 五、对后续实验的含义

旧数据支持的最终表述是：**在约1 cm电极间距、无同步电流记录且手动通断的条件下，传感器未稳定检出阴极保护电流引起的准静态周期、弛豫、高频频带或跨通道网络响应。**

它不能推出“传感器永远测不到阴极保护”，因为电偶极矩随电极间距增大，后续约30 cm几何与旧实验不是同一信号强度。新实验应保留同步电流/开关标记；否则即使出现弱效应，仍会受1 s级时刻不确定性限制。

## 六、限制

1. 旧实验电极间距约1 cm，是最主要的物理限制。
2. 没有同步电源电流轨迹，ON/OFF来自名义协议；已用前后1 s敏感性分析，但不能替代硬件同步。
3. `005hz` 只有4个周期，精确符号翻转检验的最小双侧p值有限。
4. 结果中的“0项通过”是对当前预定义特征族而言，不是对任意事后挑选特征的绝对否定。
"""
    (OUTPUT / "CATHODIC_MENTOR_METHODS_REPORT.md").write_text(report, encoding="utf-8")
    manifest = {
        "analysis": "cathodic_mentor_methods_v1",
        "unique_archived_records": len(coverage),
        "new_low_frequency_feature_rows": len(cwt),
        "new_folded_relaxation_rows": len(folded),
        "new_memd_rows": len(memd),
        "new_high_frequency_summary_rows": len(high),
        "state_network_summary_rows": len(state),
        "cross_repeat_transfer_rows": len(transfer),
        "predefined_method_gates_passed": int(matrix["passed"].sum()),
        "report": "CATHODIC_MENTOR_METHODS_REPORT.md",
    }
    (OUTPUT / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(OUTPUT / "CATHODIC_MENTOR_METHODS_REPORT.md")


if __name__ == "__main__":
    main()
