"""Validate completeness and basic integrity of mentor methods v2 outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from scripts.mentor_method_common import METHOD_OUTPUT


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=METHOD_OUTPUT)
    args = parser.parse_args(argv)
    base = args.base
    errors: list[str] = []
    required = [
        base / "wavelet_relaxation" / "cwt_case_features.csv",
        base / "wavelet_relaxation" / "filter_injection_recovery.csv",
        base / "event_shape_models" / "event_shape_case_summary.csv",
        base / "modes_complexity_network" / "complexity_case_features.csv",
        base / "modes_complexity_network" / "aligned_multichannel_emd_case_features.csv",
        base / "modes_complexity_network" / "network_state_case_features.csv",
        base / "nonlinear_highfreq" / "phase_amplitude_coupling.csv",
        base / "nonlinear_highfreq" / "short_high_frequency_bicoherence.csv",
        base / "identifiability" / "grouped_identifiability_summary.csv",
        base / "METHOD_COVERAGE_MATRIX.csv",
        base / "METHOD_RESULT_MATRIX.csv",
        base / "METHOD_FEATURE_CONSISTENCY.csv",
        base / "MENTOR_METHOD_EXPLORATION_REPORT.md",
    ]
    case_files = [
        required[0], required[3], required[4], required[5], required[6], required[7]
    ]
    for path in required:
        if not path.exists() or path.stat().st_size == 0:
            errors.append(f"missing_or_empty: {path}")
    for path in case_files:
        if not path.exists():
            continue
        try:
            frame = pd.read_csv(path)
        except pd.errors.EmptyDataError:
            errors.append(f"empty_csv: {path}")
            continue
        if "case_id" in frame and frame["case_id"].nunique() != 49:
            errors.append(f"case_coverage_{frame['case_id'].nunique()}_not_49: {path}")
        numeric = frame.select_dtypes(include=[np.number])
        if np.isinf(numeric.to_numpy(dtype=np.float64)).any():
            errors.append(f"infinite_numeric_value: {path}")
    coverage_path = base / "METHOD_COVERAGE_MATRIX.csv"
    if coverage_path.exists():
        coverage = pd.read_csv(coverage_path)
        if len(coverage) < 19:
            errors.append(f"coverage_rows_{len(coverage)}_below_19")
        if (coverage["status"] == "pending_or_missing").any():
            missing = coverage.loc[
                coverage["status"] == "pending_or_missing", "method"
            ].tolist()
            errors.append(f"pending_or_missing_methods: {missing}")
    image_count = 0
    for path in base.rglob("*.png"):
        image_count += 1
        with Image.open(path) as image:
            if image.width < 400 or image.height < 300:
                errors.append(f"undersized_figure_{image.size}: {path}")
            extrema = image.convert("L").getextrema()
            if extrema[0] == extrema[1]:
                errors.append(f"blank_figure: {path}")
    if image_count < 4:
        errors.append(f"figure_count_{image_count}_below_4")
    summary = {
        "status": "pass" if not errors else "fail",
        "error_count": len(errors),
        "errors": errors,
        "figure_count": image_count,
    }
    (base / "VALIDATION_SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
