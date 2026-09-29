"""Validate cathodic mentor-method analysis outputs."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'analysis/cathodic_mentor_methods_v1'


def main() -> None:
    low = OUTPUT / "low_frequency"
    high = OUTPUT / "high_frequency"
    cwt = pd.read_csv(low / "cathodic_cwt_sst_features.csv")
    folded = pd.read_csv(low / "cathodic_folded_relaxation.csv")
    memd = pd.read_csv(low / "cathodic_projection_memd.csv")
    summary = pd.read_csv(high / "highfreq_on_off_summary.csv")
    cycles = pd.read_csv(high / "highfreq_cycle_differences.csv")
    health = pd.read_csv(high / "highfreq_dynamic_health.csv")
    coverage = pd.read_csv(OUTPUT / "CATHODIC_METHOD_COVERAGE.csv")
    matrix = pd.read_csv(OUTPUT / "CATHODIC_RESULT_MATRIX.csv")
    candidates = pd.read_csv(OUTPUT / "CATHODIC_EXPLORATORY_CANDIDATES.csv")
    state = pd.read_csv(OUTPUT / "state_network/state_cycle_alignment.csv")
    transfer = pd.read_csv(OUTPUT / "state_network/state_cross_repeat_transfer.csv")

    assert len(cwt) == 50
    assert len(folded) == 40
    assert len(memd) == 40
    assert len(summary) == 216
    assert len(cycles) == 252
    assert len(health) == 8
    assert len(coverage) == 21
    assert len(matrix) == 11
    assert len(candidates) >= 6
    assert len(state) == 144
    assert len(transfer) == 24
    assert set(summary["timing_offset_s"]) == {-1.0, 0.0, 1.0}
    assert set(summary["case"]) == {
        "005hz", "opensvnear", "cp200near", "cp500near",
        "cp1000near", "cp1000near2", "cp3000near", "cp3000near2",
    }
    nominal = summary[summary["timing_offset_s"].eq(0.0)]
    assert len(nominal) == 72
    assert int(np.sum(nominal["exact_signflip_fdr"] < 0.05)) == 0
    assert int(np.sum(cwt["target_nearby_frequency_p_fdr"] < 0.05)) == 0
    assert int(np.sum(cwt["circular_shift_null_p_fdr"] < 0.05)) == 0
    assert int(matrix["passed"].sum()) == 0
    assert int(np.sum(
        state["timing_offset_s"].eq(0.0)
        & (state["alignment_signflip_fdr"] < 0.05)
    )) == 0
    assert int(np.sum(transfer["projection_signflip_fdr"] < 0.05)) == 0
    assert health["healthy_channel_indices_1based"].nunique() > 1
    assert (memd["memd_reconstruction_nrmse"] < 1e-10).all()
    for required in (
        "CATHODIC_MENTOR_METHODS_REPORT.md",
        "cathodic_mentor_evidence_summary.png",
        "run_manifest.json",
    ):
        assert (OUTPUT / required).is_file()
    manifest = json.loads((OUTPUT / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["unique_archived_records"] == 21
    assert manifest["predefined_method_gates_passed"] == 0
    print("Cathodic mentor-method outputs validated.")


if __name__ == "__main__":
    main()
