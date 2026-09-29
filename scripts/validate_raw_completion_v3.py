"""Validate all artifacts produced after the original raw data were restored."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = PROJECT_ROOT / 'analysis/mentor_aligned_raw_completion_v3'


def validate(base: Path) -> dict[str, object]:
    errors: list[str] = []

    def read(relative: str) -> pd.DataFrame:
        path = base / relative
        if not path.is_file():
            errors.append(f"missing {relative}")
            return pd.DataFrame()
        try:
            return pd.read_csv(path)
        except Exception as error:
            errors.append(f"cannot read {relative}: {error}")
            return pd.DataFrame()

    high = read("full_raw_highfrequency/full_raw_highfrequency_features.csv")
    epochs = read("full_raw_highfrequency/full_raw_epoch_features.csv")
    peaks = read("full_raw_highfrequency/full_raw_narrow_peak_persistence.csv")
    memd = read("projection_memd/projection_memd_features.csv")
    memd_robust = read("projection_memd/projection_memd_parameter_robustness.csv")
    pulse = read("pulse_relaxation/pulse_group_summary.csv")
    pulse_events = read("pulse_relaxation/pulse_transition_models.csv")
    pulse_health = read("pulse_relaxation/pulse_dynamic_channel_health.csv")
    batch_files = read("batch_20260512/file_features_dynamic_health.csv")
    batch_groups = read("batch_20260512/distance_condition_features.csv")
    ident = read("identifiability/raw_completion_identifiability_summary.csv")

    expected_counts = [
        ("full raw cases", len(high), 49),
        ("full raw epochs", len(epochs), 49 * 8 * 3),
        ("projection MEMD configurations", len(memd), 49 * 2 * 2),
        ("projection MEMD robustness rows", len(memd_robust), 49 * 2),
        ("pulse groups", len(pulse), 188),
        ("pulse channel-health rows", len(pulse_health), 188 * 12),
        ("20260512 files", len(batch_files), 360),
        ("20260512 distance-condition groups", len(batch_groups), 9),
        ("identifiability rows", len(ident), 49),
    ]
    for name, observed, expected in expected_counts:
        if observed != expected:
            errors.append(f"{name}: expected {expected}, found {observed}")
    if not high.empty:
        if high["case_id"].nunique() != 49:
            errors.append("full raw case IDs are not unique")
        if not np.all(high["raw_window_count"] == 96):
            errors.append("not every full raw case uses 96 windows")
        if not np.all(high["full_bicoherence_window_epoch_count"] == 8):
            errors.append("not every full raw case has eight bicoherence epochs")
        carrier = high[high["carrier_khz"].notna()]
        if len(carrier) != 12:
            errors.append(f"expected 12 carrier cases, found {len(carrier)}")
    if not epochs.empty:
        counts = epochs.groupby(["case_id", "band_name"]).size()
        if not np.all(counts == 8):
            errors.append("full raw epoch table does not have eight epochs per case-band")
    if not memd.empty:
        if float(memd["memd_reconstruction_nrmse"].max()) > 1e-8:
            errors.append("projection MEMD reconstruction error is too large")
        if set(memd["direction_count"].unique()) != {16, 24}:
            errors.append("projection MEMD parameter audit is incomplete")
    synthetic_path = base / "projection_memd/synthetic_validation.json"
    if not synthetic_path.is_file():
        errors.append("missing MEMD synthetic validation")
    else:
        synthetic = json.loads(synthetic_path.read_text(encoding="utf-8"))
        if synthetic["synthetic_reconstruction_nrmse"] > 1e-8:
            errors.append("MEMD synthetic reconstruction failed")
        if synthetic["synthetic_0p32hz_nearest_error_hz"] > 0.05:
            errors.append("MEMD synthetic low mode was not recovered")
        if synthetic["synthetic_1p35hz_nearest_error_hz"] > 0.12:
            errors.append("MEMD synthetic high mode was not recovered")
    if not pulse.empty:
        if pulse["group_name"].nunique() != 188:
            errors.append("pulse group names are not unique")
        if np.any(pulse["cycle_count"] < 3):
            errors.append("a pulse group has fewer than three complete cycles")
        if np.any(pulse["healthy_channel_count"] < 4):
            errors.append("a pulse group has fewer than four healthy channels")
        if not np.all(pulse["analysis_version"] == 3):
            errors.append("pulse groups were not all generated with relaxation-template version 3")
        if "relaxation_template_tau_s" not in pulse:
            errors.append("pulse relaxation-template time constants are missing")
    if not pulse_events.empty:
        required = [
            "single_tau_s", "single_r2", "single_vs_linear_delta_aicc",
            "double_tau_fast_s", "double_tau_slow_s",
            "matrix_pencil_physical_pole_count", "credible_relaxation",
        ]
        missing = [column for column in required if column not in pulse_events]
        if missing:
            errors.append(f"pulse transition model columns missing: {missing}")
    if not batch_files.empty:
        counts = batch_files.groupby(["distance", "condition"]).size()
        if not np.all(counts == 40):
            errors.append(f"20260512 group file counts are not all 40: {counts.to_dict()}")
        if np.any(batch_files["healthy_channel_count"] < 4):
            errors.append("a 20260512 file has fewer than four healthy channels")
    if not ident.empty:
        if not np.all((ident["grouped_balanced_accuracy"] >= 0.0) & (ident["grouped_balanced_accuracy"] <= 1.0)):
            errors.append("identifiability accuracy outside [0, 1]")
        if not np.all((ident["permutation_p"] > 0.0) & (ident["permutation_p"] <= 1.0)):
            errors.append("identifiability permutation p outside (0, 1]")
    if peaks.empty:
        errors.append("full raw narrow-peak table is empty")

    required_final = [
        "RAW_COMPLETION_REPORT.md",
        "RAW_COMPLETION_METHOD_COVERAGE.csv",
        "RAW_COMPLETION_RESULT_MATRIX.csv",
        "FULL_RAW_STRATIFIED_SIGNIFICANCE.csv",
        "FULL_RAW_EPOCH_SUPERIORITY.csv",
        "PULSE_VOLTAGE_DEPENDENCE_FDR.csv",
        "PULSE_PERIOD_SPECIFICITY_FDR.csv",
        "PROJECTION_MEMD_SIGNIFICANCE.csv",
        "IDENTIFIABILITY_CLASS_RECALL.csv",
        "REPORT_SUMMARY.json",
    ]
    for relative in required_final:
        if not (base / relative).is_file():
            errors.append(f"missing final artifact {relative}")
    figures = list(base.rglob("*.png"))
    for path in figures:
        if path.stat().st_size < 10_000:
            errors.append(f"figure unexpectedly small: {path}")
    result = {
        "status": "pass" if not errors else "fail",
        "error_count": len(errors),
        "errors": errors,
        "figure_count": len(figures),
    }
    (base / "VALIDATION_SUMMARY.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    args = parser.parse_args()
    result = validate(args.base)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
