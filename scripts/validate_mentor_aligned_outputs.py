"""Validate the mentor-aligned analysis outputs and write a compact audit record."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate(base: Path) -> dict[str, object]:
    manifest = json.loads((base / "run_manifest.json").read_text(encoding="utf-8"))
    health = pd.read_csv(base / "channel_health_dynamic.csv")
    spectral = pd.read_csv(base / "spectral_redistribution_score.csv")
    classification = pd.read_csv(base / "run_stop_exploratory_classification.csv")
    periodicity = pd.read_csv(base / "slow_periodicity_candidates.csv")
    synchrony = pd.read_csv(base / "cross_detector_synchrony.csv")
    consistency = pd.read_csv(base / "time_domain_feature_consistency.csv")
    pulse_manifest = json.loads(
        (base / "legacy_pulse/run_manifest.json").read_text(encoding="utf-8")
    )

    require(manifest["case_count"] == 49, "Expected 49 exact-archive cases")
    require(health["case_id"].nunique() == 49, "Health table does not cover 49 cases")
    require(len(health) == 49 * 12, "Health table must contain 12 channels per case")

    active = spectral[
        (spectral["dataset"] != 20260617)
        & spectral["condition"].isin(["30hz", "50hz", "run"])
    ]
    historical = spectral[
        (spectral["dataset"] == 20260617)
        & spectral["condition"].isin(["30hz", "50hz"])
    ]
    stop = spectral[
        (spectral["dataset"] != 20260617)
        & (spectral["condition"] == "vfd_stop")
    ]
    require(len(active) == 24, "Expected 24 later RUN/background pairs")
    require(active["dual_band_run_signature"].all(), "Later RUN signature is not 24/24")
    require(len(historical) == 6, "Expected six historical direction-reference pairs")
    require(historical["dual_band_run_signature"].all(), "Historical direction is not 6/6")
    require(len(stop) == 8, "Expected eight STOP/background controls")
    require(int(stop["dual_band_run_signature"].sum()) == 4, "Expected 4/8 STOP positives")

    direction = classification[
        classification["rule"] == "dual_band_direction_plus_background_drift"
    ].iloc[0]
    require(int(direction["true_run"]) == 24, "Direction rule RUN count mismatch")
    require(int(direction["false_run_on_stop"]) == 4, "Direction rule STOP false positives mismatch")

    fixed = periodicity[periodicity["candidate_type"] == "fixed_3p1s"]
    searched = periodicity[periodicity["candidate_type"] == "pc1_search_peak"]
    require(len(fixed) == 40, "Expected 40 long-file fixed-period tests")
    require(int((fixed["red_noise_pointwise_p"] <= 0.05).sum()) == 0,
            "A 3.1 s candidate unexpectedly passed red-noise testing")
    require(len(searched) == 200, "Expected 200 blind-search candidates")
    require(int((searched["red_noise_search_familywise_p"] <= 0.05).sum()) == 0,
            "A blind-search candidate unexpectedly passed familywise testing")
    require(len(synchrony) == 40, "Expected 40 cross-detector synchrony tests")
    require(int((synchrony["lag_null_p"] <= 0.05).sum()) == 0,
            "A cross-detector synchrony result unexpectedly passed the lag-null test")

    allan_5s_stop = consistency[
        (consistency["feature"] == "allan_tau_5s")
        & (consistency["reference_condition"] == "vfd_stop")
    ].iloc[0]
    require(int(allan_5s_stop["stratum_negative_count"]) == 8,
            "Expected 8/8 negative 5 s Allan stratum contrasts to STOP")
    require(int(allan_5s_stop["sample_negative_count"]) == 18,
            "Expected 18/24 negative 5 s Allan file contrasts to STOP")

    require(pulse_manifest["group_count"] == 188, "Expected 188 retained pulse groups")
    require(pulse_manifest["row_count"] == 2256, "Expected 2256 pulse group-channel rows")

    critical_tables = [
        spectral,
        classification,
        consistency,
        pd.read_csv(base / "frequency_30_50_pairing.csv"),
        pd.read_csv(base / "background_cross_session_ranges.csv"),
        pd.read_csv(base / "narrow_line_case_summary.csv"),
    ]
    for frame in critical_tables:
        numeric = frame.select_dtypes(include=[np.number]).to_numpy(dtype=float)
        require(not np.isinf(numeric).any(), "Infinite value in a critical result table")

    figure_paths = [
        base / "figures/spectral_redistribution.png",
        base / "figures/frequency_30_50_pairing.png",
        base / "figures/background_cross_session_ranges.png",
        base / "figures/water_3p1s_red_noise_test.png",
        base / "figures/narrow_line_temporal_validation.png",
        base / "figures/time_domain_feature_consistency.png",
        base / "legacy_pulse/legacy_pulse_amplitude_dependence.png",
        base / "legacy_pulse/legacy_pulse_repeatability.png",
    ]
    for path in figure_paths:
        require(path.is_file() and path.stat().st_size > 10_000,
                f"Missing or unexpectedly small figure: {path}")

    return {
        "validated_at": datetime.now().isoformat(),
        "status": "pass",
        "exact_archive_case_count": manifest["case_count"],
        "channel_health_row_count": len(health),
        "later_run_pair_count": len(active),
        "later_run_signature_count": int(active["dual_band_run_signature"].sum()),
        "stop_control_count": len(stop),
        "stop_direction_false_positive_count": int(stop["dual_band_run_signature"].sum()),
        "fixed_3p1s_test_count": len(fixed),
        "fixed_3p1s_pass_count": int((fixed["red_noise_pointwise_p"] <= 0.05).sum()),
        "blind_period_candidate_count": len(searched),
        "blind_period_familywise_pass_count": int(
            (searched["red_noise_search_familywise_p"] <= 0.05).sum()
        ),
        "cross_detector_test_count": len(synchrony),
        "cross_detector_lag_null_pass_count": int((synchrony["lag_null_p"] <= 0.05).sum()),
        "allan_5s_stop_negative_strata": int(allan_5s_stop["stratum_negative_count"]),
        "allan_5s_stop_strata": int(allan_5s_stop["stratum_count"]),
        "legacy_pulse_group_count": pulse_manifest["group_count"],
        "validated_figure_count": len(figure_paths),
    }


def write_summary(base: Path, summary: dict[str, object]) -> None:
    (base / "VALIDATION_SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# 分析输出验收记录",
        "",
        f"状态：{summary['status']}；时间：{summary['validated_at']}。",
        "",
        f"- 精确归档：{summary['exact_archive_case_count']}个；动态健康记录：{summary['channel_health_row_count']}行。",
        f"- 后期RUN双频带方向：{summary['later_run_signature_count']}/{summary['later_run_pair_count']}；STOP同方向误报：{summary['stop_direction_false_positive_count']}/{summary['stop_control_count']}。",
        f"- 3.1 s红噪声检验：{summary['fixed_3p1s_pass_count']}/{summary['fixed_3p1s_test_count']}通过；盲搜族检验：{summary['blind_period_familywise_pass_count']}/{summary['blind_period_candidate_count']}通过。",
        f"- 跨探测器错位对照：{summary['cross_detector_lag_null_pass_count']}/{summary['cross_detector_test_count']}通过。",
        f"- 5 s Allan相对STOP层级下降：{summary['allan_5s_stop_negative_strata']}/{summary['allan_5s_stop_strata']}。",
        f"- 主动脉冲保留工况：{summary['legacy_pulse_group_count']}；核心图验收：{summary['validated_figure_count']}张。",
    ]
    (base / "VALIDATION_SUMMARY.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path,
        default=Path("results/mentor_aligned_pre_electrochemical_v1"),
    )
    args = parser.parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    base = args.input if args.input.is_absolute() else project_root / args.input
    summary = validate(base)
    write_summary(base, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return base


if __name__ == "__main__":
    main()
