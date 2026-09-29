"""Shared data loading and bookkeeping for mentor-aligned method exploration."""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.analyze_pre_electrochemical_dynamics import (
    ENVELOPE_FEATURES,
    Case,
    case_fields,
    case_time_arrays,
    detrended,
    discover_cases,
    matched_controls,
    principal_component,
    robust_scale,
    standardized,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
METHOD_OUTPUT = PROJECT_ROOT / "results/mentor_aligned_methods_v2"
BASE_ANALYSIS = PROJECT_ROOT / "results/mentor_aligned_pre_electrochemical_v1"
LOCAL_DEPENDENCIES = PROJECT_ROOT / ".codex_tmp/mentor_method_deps"


def enable_local_dependencies() -> None:
    path = str(LOCAL_DEPENDENCIES)
    if LOCAL_DEPENDENCIES.is_dir() and path not in sys.path:
        sys.path.append(path)


def stable_seed(*parts: object) -> int:
    digest = hashlib.sha256("|".join(map(str, parts)).encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "little")


@dataclass(frozen=True)
class AnalysisSignals:
    case: Case
    sample_rate_hz: float
    healthy_indices: np.ndarray
    slow_channels: np.ndarray
    channel_signals: dict[str, np.ndarray]
    signals: dict[str, np.ndarray]
    metadata: dict[str, object]


def load_health_table(base: Path = BASE_ANALYSIS) -> pd.DataFrame:
    path = base / "channel_health_dynamic.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Run the base mentor analysis first: {path}")
    return pd.read_csv(path)


def healthy_indices(case: Case, health: pd.DataFrame) -> np.ndarray:
    rows = health[health["case_id"] == case.case_id].sort_values("channel_index")
    if len(rows) != 12:
        raise ValueError(f"Expected 12 health rows for {case.case_id}, found {len(rows)}")
    indices = rows.loc[~rows["automatic_bad"].astype(bool), "channel_index"].to_numpy(int) - 1
    if len(indices) < 4:
        raise ValueError(f"Insufficient healthy channels for {case.case_id}: {len(indices)}")
    return indices


def load_analysis_signals(case: Case, health: pd.DataFrame) -> AnalysisSignals:
    metadata, arrays, sample_rate = case_time_arrays(case)
    healthy = healthy_indices(case, health)
    slow_channels = np.asarray(arrays["slow_mean"][:, healthy], dtype=np.float64)
    slow_pc, _, _ = principal_component(slow_channels)
    signals = {"slow_pc1": standardized(slow_pc)}
    channel_signals = {"slow_pc1": slow_channels}
    for feature in ENVELOPE_FEATURES:
        values = np.log10(np.maximum(np.asarray(arrays[feature], dtype=np.float64), 1e-30))
        selected = values[:, healthy]
        pc, _, _ = principal_component(selected)
        signals[f"{feature}_pc1"] = standardized(pc)
        channel_signals[f"{feature}_pc1"] = selected
    return AnalysisSignals(
        case=case,
        sample_rate_hz=float(sample_rate),
        healthy_indices=healthy,
        slow_channels=slow_channels,
        channel_signals=channel_signals,
        signals={name: np.asarray(value, dtype=np.float64).squeeze()
                 for name, value in signals.items()},
        metadata=metadata,
    )


def dependency_versions() -> dict[str, str]:
    enable_local_dependencies()
    import antropy
    import pywt
    import ruptures
    import scipy
    import sklearn
    import ssqueezepy

    try:
        import importlib.metadata as metadata
        emd_version = metadata.version("EMD-signal")
        vmd_version = metadata.version("vmdpy")
    except Exception:
        emd_version = "unknown"
        vmd_version = "unknown"
    return {
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scipy": scipy.__version__,
        "scikit_learn": sklearn.__version__,
        "pywavelets": pywt.__version__,
        "ruptures": getattr(ruptures, "__version__", "unknown"),
        "ssqueezepy": getattr(ssqueezepy, "__version__", "unknown"),
        "antropy": getattr(antropy, "__version__", "unknown"),
        "emd_signal": emd_version,
        "vmdpy": vmd_version,
    }


def write_frame(path: Path, rows: list[dict[str, object]] | pd.DataFrame) -> pd.DataFrame:
    frame = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return frame


def write_manifest(output: Path, name: str, payload: dict[str, object]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    complete = {
        "analysis": name,
        "project_root": str(PROJECT_ROOT),
        "dependencies": dependency_versions(),
        **payload,
    }
    (output / "run_manifest.json").write_text(
        json.dumps(complete, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def all_cases() -> list[Case]:
    return discover_cases(PROJECT_ROOT)


def generic_matched_contrasts(
    cases: list[Case], frame: pd.DataFrame, feature_columns: list[str],
    identity_columns: list[str],
) -> pd.DataFrame:
    """Pair file-level features to each local background/STOP control."""
    rows: list[dict[str, object]] = []
    for case in cases:
        active = frame[frame["case_id"] == case.case_id]
        if active.empty:
            continue
        for control in matched_controls(case, cases):
            reference = frame[frame["case_id"] == control.case_id]
            if reference.empty:
                continue
            if identity_columns:
                merged = active.merge(
                    reference,
                    on=identity_columns,
                    suffixes=("_active", "_reference"),
                )
            else:
                merged = active.assign(_pair_key=1).merge(
                    reference.assign(_pair_key=1),
                    on="_pair_key", suffixes=("_active", "_reference"),
                ).drop(columns="_pair_key")
            for _, item in merged.iterrows():
                base = {
                    **case_fields(case),
                    "reference_case_id": control.case_id,
                    "reference_condition": control.condition,
                }
                for column in identity_columns:
                    base[column] = item[column]
                for column in feature_columns:
                    active_value = item[f"{column}_active"]
                    reference_value = item[f"{column}_reference"]
                    base[f"{column}_active"] = active_value
                    base[f"{column}_reference"] = reference_value
                    base[f"{column}_difference"] = active_value - reference_value
                rows.append(base)
    return pd.DataFrame(rows)
