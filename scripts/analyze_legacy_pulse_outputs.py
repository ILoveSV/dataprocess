"""Summarize retained output-level evidence from the 2026-06-09 pulse tests."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats


PULSE_TOKEN = re.compile(r"(?P<voltage>\d+(?:\.\d+)?)v(?P<duration>\d+(?:\.\d+)?)ms", re.I)


def parse_group_name(group_name: str, source_mode: str | None = None) -> dict[str, object]:
    parts = group_name.split("/")
    pulse_tokens = [
        (float(match.group("voltage")), float(match.group("duration")))
        for match in PULSE_TOKEN.finditer(group_name)
    ]
    voltages = [item[0] for item in pulse_tokens]
    durations = [item[1] for item in pulse_tokens]
    if parts and parts[0] in {"non_vac", "vac"}:
        resolved_mode = parts[0]
        offset = 1
    else:
        resolved_mode = source_mode or ""
        offset = 0
    sequence_index = next(
        (index for index in range(offset, len(parts)) if PULSE_TOKEN.search(parts[index])),
        len(parts),
    )
    return {
        "source_mode": resolved_mode,
        "setup": parts[offset] if len(parts) > offset else "",
        "waveform": parts[offset + 1] if len(parts) > offset + 1 else "",
        "timing_variant": "/".join(parts[offset + 2:sequence_index]),
        "pulse_sequence": parts[sequence_index] if len(parts) > sequence_index else "",
        "replicate_label": "/".join(parts[sequence_index + 1:]),
        "pulse_level_count": len(voltages),
        "pulse_max_v": max(voltages) if voltages else np.nan,
        "pulse_min_v": min(voltages) if voltages else np.nan,
        "pulse_span_v": max(voltages) - min(voltages) if voltages else np.nan,
        "pulse_total_duration_ms": sum(durations) if durations else np.nan,
        "is_first_order": "一阶波" in group_name,
        "is_second_order_positive": "二阶波-Δ2" in group_name,
        "is_second_order_negative": "二阶波-Δ-2" in group_name,
    }


def load_manifest_rows(root: Path) -> pd.DataFrame:
    manifest_dirs = [
        ("non_vac", root / "non_vac/first_test_pipeline_44_6_9_non_vac_first3/.first_test_group_manifests"),
        ("vac", root / "vac/first_test_pipeline_44_6_9_vac_first3/.first_test_group_manifests"),
    ]
    rows: list[dict[str, object]] = []
    for source_mode, manifest_dir in manifest_dirs:
        if not manifest_dir.is_dir():
            continue
        for path in sorted(manifest_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            group_name = str(payload["group_name"])
            parsed = parse_group_name(group_name, source_mode=source_mode)
            for row in payload.get("time_group_rows", []):
                rows.append({
                    "manifest": str(path),
                    "group_name": group_name,
                    **parsed,
                    **row,
                })
    return pd.DataFrame(rows)


def monotonic_pair_fraction(values_x: np.ndarray, values_y: np.ndarray,
                            direction: float) -> float:
    order = np.argsort(values_x)
    differences = np.diff(values_y[order]) * direction
    return float(np.mean(differences >= 0.0)) if len(differences) else np.nan


def calibration_rows(data: pd.DataFrame) -> list[dict[str, object]]:
    metrics = (
        "mean_ac_rms",
        "mean_robust_sigma",
        "mean_of_file_means",
        "mean_p2p_v",
    )
    first_order = data[data["is_first_order"]].copy()
    rows = []
    for keys, group in first_order.groupby(["source_mode", "setup", "channel"]):
        group = group.dropna(subset=["pulse_max_v"])
        for metric in metrics:
            aggregate = group.groupby("pulse_max_v", as_index=False)[metric].median()
            if len(aggregate) < 4 or aggregate["pulse_max_v"].nunique() < 4:
                continue
            x = aggregate["pulse_max_v"].to_numpy(dtype=float)
            y = aggregate[metric].to_numpy(dtype=float)
            if np.unique(y).size < 2:
                continue
            rho, p_value = stats.spearmanr(x, y)
            slope, intercept, slope_low, slope_high = stats.theilslopes(y, x, 0.95)
            direction = 1.0 if rho >= 0.0 else -1.0
            response_range = float(np.max(y) - np.min(y))
            quantization_step = float(
                group["mean_quantization_step_estimate"].replace(0.0, np.nan).median()
            )
            rows.append({
                "source_mode": keys[0],
                "setup": keys[1],
                "channel": keys[2],
                "metric": metric,
                "pulse_level_count": len(aggregate),
                "spearman_rho": float(rho),
                "spearman_p": float(p_value),
                "theil_sen_slope_per_v": float(slope),
                "theil_sen_intercept": float(intercept),
                "theil_sen_slope_low": float(slope_low),
                "theil_sen_slope_high": float(slope_high),
                "monotonic_pair_fraction_in_rho_direction": monotonic_pair_fraction(
                    x, y, direction
                ),
                "response_range": response_range,
                "response_relative_range": float(
                    response_range / max(abs(np.median(y)), 1e-30)
                ),
                "median_quantization_step_v": quantization_step,
                "response_range_in_quantization_steps": float(
                    response_range / max(quantization_step, 1e-30)
                ),
            })
    return rows


def repeatability_rows(data: pd.DataFrame) -> list[dict[str, object]]:
    rows = []
    for keys, group in data.groupby(["source_mode", "channel"]):
        rows.append({
            "source_mode": keys[0],
            "channel": keys[1],
            "group_count": group["group_name"].nunique(),
            "median_file_count": float(group["file_count"].median()),
            "missing_group_fraction": float(group["missing_flag"].mean()),
            "median_baseline_instability_ratio": float(
                group["baseline_instability_ratio"].median()
            ),
            "q90_baseline_instability_ratio": float(
                group["baseline_instability_ratio"].quantile(0.9)
            ),
            "fraction_baseline_instability_ratio_le_0p1": float(
                np.mean(group["baseline_instability_ratio"] <= 0.1)
            ),
            "median_cv_ac_rms": float(group["cv_ac_rms"].median()),
            "q90_cv_ac_rms": float(group["cv_ac_rms"].quantile(0.9)),
            "median_mean_ac_rms_v": float(group["mean_ac_rms"].median()),
            "median_quantization_step_v": float(
                group["mean_quantization_step_estimate"].median()
            ),
            "qc_ok_fraction": float(np.mean(group["qc_flag"] == "OK")),
        })
    return rows


def plot_calibration(calibration: pd.DataFrame, output: Path) -> None:
    subset = calibration[calibration["metric"] == "mean_ac_rms"].copy()
    if subset.empty:
        return
    subset["channel_number"] = subset["channel"].str.extract(r"(\d+)").astype(int)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharey=True)
    for axis, mode in zip(axes, ("non_vac", "vac")):
        selected = subset[subset["source_mode"] == mode]
        setups = sorted(selected["setup"].unique())
        colors = plt.cm.tab10(np.linspace(0.0, 1.0, max(len(setups), 1)))
        for color, setup in zip(colors, setups):
            group = selected[selected["setup"] == setup].copy()
            significant = group["spearman_p"] <= 0.05
            marker_size = 35.0 + 180.0 * np.minimum(
                group["response_relative_range"].to_numpy(dtype=float), 0.5
            ) / 0.5
            facecolors = [color if item else "none" for item in significant]
            axis.scatter(
                group["channel_number"], group["spearman_rho"],
                s=marker_size, facecolors=facecolors,
                edgecolors=color, linewidths=1.1, alpha=0.85, label=setup,
            )
        axis.axhline(0.0, color="#555555", linewidth=0.8)
        axis.axhline(0.8, color="#777777", linestyle="--", linewidth=0.8)
        axis.axhline(-0.8, color="#777777", linestyle="--", linewidth=0.8)
        axis.set_title(mode)
        axis.set_xlabel("Channel")
        axis.set_xticks(range(1, 13))
        axis.grid(alpha=0.25)
        if setups:
            axis.legend(fontsize=8)
    axes[0].set_ylabel("Spearman rho: pulse voltage vs AC RMS")
    fig.suptitle(
        "Legacy pulse-output amplitude dependence\n"
        "filled: p<=0.05; marker size: relative response range (capped at 50%)"
    )
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def plot_repeatability(repeatability: pd.DataFrame, output: Path) -> None:
    frame = repeatability.copy()
    frame["channel_number"] = frame["channel"].str.extract(r"(\d+)").astype(int)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharey=True)
    for axis, mode in zip(axes, ("non_vac", "vac")):
        selected = frame[frame["source_mode"] == mode].sort_values("channel_number")
        axis.bar(selected["channel_number"], selected["median_baseline_instability_ratio"],
                 color="#2f6f8f")
        axis.set_yscale("log")
        axis.set_title(mode)
        axis.set_xlabel("Channel")
        axis.set_xticks(range(1, 13))
        axis.grid(axis="y", alpha=0.25)
    axes[0].set_ylabel("Median repeat-to-repeat mean SD / robust sigma")
    fig.suptitle("Legacy pulse-output repeatability by channel")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def build_report(data: pd.DataFrame, calibration: pd.DataFrame,
                 repeatability: pd.DataFrame, output: Path) -> None:
    group_count = data["group_name"].nunique()
    file_count_values = data.groupby("group_name")["file_count"].first()
    quantization = data["mean_quantization_step_estimate"].replace(0.0, np.nan)
    strong = calibration[
        (calibration["metric"] == "mean_ac_rms")
        & (calibration["spearman_rho"].abs() >= 0.8)
        & (calibration["spearman_p"] <= 0.05)
    ]
    practical = strong[strong["response_relative_range"] >= 0.05]
    above_quantization = practical[
        practical["response_range_in_quantization_steps"] >= 1.0
    ]
    lines = [
        "# 2026-06-09脉冲实验保留输出复核",
        "",
        "## 可用证据",
        "",
        f"- JSON保留工况数：{group_count}；工况×通道行数：{len(data)}。",
        f"- 每工况重复文件数中位数：{file_count_values.median():.0f}。",
        "- 原始逐点CSV不在当前电脑；因此可以复核重复性、幅值依赖和通道质量，不能重新恢复瞬态上升沿、回落常数或跨通道同步波形。",
        "",
        "## 量化与重复性",
        "",
        f"- 估计量化台阶中位数：{quantization.median() * 1e3:.4f} mV。",
        f"- 工况内重复均值波动不超过本通道robust sigma的10%的比例：{np.mean(data['baseline_instability_ratio'] <= 0.1):.1%}。",
        f"- 一阶脉冲中，AC RMS对设定电压达到|Spearman rho|>=0.8且p<=0.05的‘模式×接法×通道’组合：{len(strong)}/{len(calibration[calibration['metric'] == 'mean_ac_rms'])}；其中相对变化至少5%的有{len(practical)}个，绝对变化还超过一个量化台阶的有{len(above_quantization)}个。",
        "",
        "## 解释边界",
        "",
        "- 这些是主动脉冲驱动下的系统响应与仪器学证据，不等同于开放环境中的被动外场检出限。",
        "- 通道间噪声、量化和响应幅值差异显著，因此后续必须逐文件健康判断并在通道内相对本机背景比较。",
        "- 要落实导师所说的‘充电后自然驰豫波形’，仍需原始时序或下一轮保留触发前后波形的数据。",
    ]
    (output / "LEGACY_PULSE_OUTPUT_REPORT.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(r"D:\Lab\results\44.6.9"))
    parser.add_argument("--output", type=Path,
                        default=Path("results/mentor_aligned_pre_electrochemical_v1/legacy_pulse"))
    args = parser.parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    output = args.output if args.output.is_absolute() else project_root / args.output
    output.mkdir(parents=True, exist_ok=True)
    data = load_manifest_rows(args.source)
    if data.empty:
        raise FileNotFoundError(f"No retained pulse manifests found under {args.source}")
    calibration = pd.DataFrame(calibration_rows(data))
    repeatability = pd.DataFrame(repeatability_rows(data))
    data.to_csv(output / "legacy_pulse_group_channel_summary.csv", index=False)
    calibration.to_csv(output / "legacy_pulse_amplitude_dependence.csv", index=False)
    repeatability.to_csv(output / "legacy_pulse_repeatability.csv", index=False)
    plot_calibration(calibration, output / "legacy_pulse_amplitude_dependence.png")
    plot_repeatability(repeatability, output / "legacy_pulse_repeatability.png")
    build_report(data, calibration, repeatability, output)
    manifest = {
        "source": str(args.source),
        "group_count": int(data["group_name"].nunique()),
        "row_count": len(data),
        "raw_time_series_available": False,
    }
    (output / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Output: {output}")
    return output


if __name__ == "__main__":
    main()
