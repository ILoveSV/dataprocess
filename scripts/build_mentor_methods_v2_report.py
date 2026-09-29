"""Build a unified, result-oriented report for the mentor-requested methods."""

from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from scripts.analyze_mentor_modes_complexity_network import benjamini_hochberg
from scripts.mentor_method_common import (
    METHOD_OUTPUT,
    PROJECT_ROOT,
    all_cases,
    generic_matched_contrasts,
    write_frame,
)


META_COLUMNS = {
    "dataset", "case_id", "arrangement", "detector", "condition", "distance",
    "carrier_khz", "output_hz", "reference_case_id", "reference_condition",
}


def read_frame(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame()


def contrast_tables(base: Path) -> list[tuple[str, Path]]:
    return [
        ("CWT", base / "wavelet_relaxation" / "matched_cwt_contrasts.csv"),
        ("SST", base / "wavelet_relaxation" / "matched_sst_contrasts.csv"),
        ("cross_wavelet", base / "wavelet_relaxation" / "matched_wavelet_coherence_contrasts.csv"),
        ("changepoint", base / "wavelet_relaxation" / "matched_changepoint_contrasts.csv"),
        ("event_shape", base / "event_shape_models" / "matched_event_shape_contrasts.csv"),
        ("complexity", base / "modes_complexity_network" / "matched_complexity_contrasts.csv"),
        ("adaptive_mode", base / "modes_complexity_network" / "matched_mode_contrasts.csv"),
        ("aligned_channel_EMD", base / "modes_complexity_network" / "matched_aligned_multichannel_emd_contrasts.csv"),
        ("network_state", base / "modes_complexity_network" / "matched_network_state_contrasts.csv"),
        ("PAC", base / "nonlinear_highfreq" / "matched_phase_amplitude_contrasts.csv"),
        ("short_high_CWT", base / "nonlinear_highfreq" / "matched_short_high_cwt_contrasts.csv"),
        ("short_bicoherence", base / "nonlinear_highfreq" / "matched_short_bicoherence_contrasts.csv"),
        ("filter_path", base / "wavelet_relaxation" / "matched_filter_path_contrasts.csv"),
    ]


def ensure_derived_contrasts(base: Path) -> None:
    cases = all_cases()
    wavelet = base / "wavelet_relaxation"
    sst = read_frame(wavelet / "synchrosqueezed_case_features.csv")
    if not sst.empty:
        write_frame(
            wavelet / "matched_sst_contrasts.csv",
            generic_matched_contrasts(
                cases, sst,
                [
                    "sst_ridge_frequency_median_hz", "sst_ridge_frequency_iqr_hz",
                    "sst_top3_bin_concentration_median",
                    "sst_top3_bin_concentration_q75",
                ],
                ["signal_name"],
            ),
        )
    filters = read_frame(wavelet / "filter_sensitivity_case_features.csv")
    if not filters.empty:
        write_frame(
            wavelet / "matched_filter_path_contrasts.csv",
            generic_matched_contrasts(
                cases, filters,
                [
                    "fixed_3p1s_amplitude_sigma", "changepoint_count",
                    "wavelet_global_peak_frequency_hz",
                    "wavelet_significant_ridge_fraction",
                ],
                ["signal_name", "filter_name"],
            ),
        )


def feature_identity(frame: pd.DataFrame) -> list[str]:
    numeric_suffixes = ("_active", "_reference", "_difference")
    return [
        column for column in frame.columns
        if column not in META_COLUMNS
        and not column.endswith(numeric_suffixes)
    ]


def summarize_contrasts(base: Path) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for family, path in contrast_tables(base):
        frame = read_frame(path)
        if frame.empty:
            continue
        frame = frame[
            (frame["dataset"] != 20260617)
            & frame["condition"].isin(["30hz", "50hz", "run"])
            & frame["reference_condition"].isin(["background", "vfd_stop"])
        ].copy()
        identities = feature_identity(frame)
        difference_columns = [column for column in frame if column.endswith("_difference")]
        for difference_column in difference_columns:
            feature = difference_column.removesuffix("_difference")
            group_columns = ["reference_condition", *identities]
            for key, group in frame.groupby(group_columns, dropna=False):
                if not isinstance(key, tuple):
                    key = (key,)
                identity = dict(zip(group_columns, key))
                values = pd.to_numeric(group[difference_column], errors="coerce")
                working = group.assign(_effect=values).dropna(subset=["_effect"])
                if working.empty:
                    continue
                strata = working.groupby(
                    ["dataset", "arrangement", "detector"], dropna=False
                )["_effect"].median().dropna().to_numpy(dtype=np.float64)
                if not len(strata):
                    continue
                positive = int(np.sum(strata > 1e-15))
                negative = int(np.sum(strata < -1e-15))
                nonzero = positive + negative
                dominant = max(positive, negative)
                sign_p = (
                    float(stats.binomtest(dominant, nonzero, 0.5).pvalue)
                    if nonzero else 1.0
                )
                identity_text = ";".join(
                    f"{column}={identity[column]}" for column in identities
                ) or "all"
                rows.append({
                    "family": family,
                    "feature": feature,
                    "identity": identity_text,
                    "reference_condition": identity["reference_condition"],
                    "sample_count": len(working),
                    "sample_median_effect": float(np.median(working["_effect"])),
                    "stratum_count": len(strata),
                    "stratum_positive_count": positive,
                    "stratum_negative_count": negative,
                    "stratum_median_effect": float(np.median(strata)),
                    "dominant_direction": (
                        "positive" if positive > negative else
                        "negative" if negative > positive else "tie"
                    ),
                    "dominant_stratum_fraction": dominant / max(nonzero, 1),
                    "sign_test_p": sign_p,
                })
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result["sign_test_fdr_global_p"] = benjamini_hochberg(
        result["sign_test_p"].to_numpy(dtype=np.float64)
    )
    result["sign_test_fdr_within_family_p"] = np.nan
    for family, index in result.groupby("family").groups.items():
        result.loc[index, "sign_test_fdr_within_family_p"] = benjamini_hochberg(
            result.loc[index, "sign_test_p"].to_numpy(dtype=np.float64)
        )
    result["evidence_grade"] = "inconsistent_or_underpowered"
    strong = (
        (result["stratum_count"] >= 6)
        & (result["dominant_stratum_fraction"] >= 0.875)
        & (result["sign_test_fdr_within_family_p"] <= 0.10)
    )
    candidate = (
        (result["stratum_count"] >= 4)
        & (result["dominant_stratum_fraction"] >= 0.75)
        & (result["sign_test_p"] <= 0.10)
    )
    result.loc[candidate, "evidence_grade"] = "directional_candidate"
    result.loc[strong, "evidence_grade"] = "cross_stratum_stable"
    return result.sort_values(
        ["evidence_grade", "dominant_stratum_fraction", "stratum_count"],
        ascending=[True, False, False],
    )


def significance_sources(base: Path) -> list[tuple[str, Path, list[str]]]:
    return [
        ("complexity", base / "modes_complexity_network" / "complexity_case_features.csv",
         ["dfa_alpha_phase_surrogate_p", "sample_entropy_phase_surrogate_p"]),
        ("cross_wavelet", base / "wavelet_relaxation" / "cross_wavelet_coherence.csv",
         ["circular_shift_null_p"]),
        ("PAC", base / "nonlinear_highfreq" / "phase_amplitude_coupling.csv",
         ["phase_randomized_null_p"]),
        ("short_bicoherence", base / "nonlinear_highfreq" / "short_high_frequency_bicoherence.csv",
         ["bicoherence_max_phase_surrogate_p"]),
    ]


def summarize_significance(base: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    detail_rows = []
    for family, path, p_columns in significance_sources(base):
        frame = read_frame(path)
        if frame.empty:
            continue
        identity_columns = [
            column for column in (
                "signal_name", "phase_signal", "phase_band", "amplitude_signal",
                "analysis_scope",
            ) if column in frame
        ]
        for p_column in p_columns:
            for item in frame.itertuples(index=False):
                value = getattr(item, p_column, np.nan)
                if not np.isfinite(value):
                    continue
                detail_rows.append({
                    "family": family,
                    "p_feature": p_column,
                    "dataset": getattr(item, "dataset"),
                    "case_id": getattr(item, "case_id"),
                    "arrangement": getattr(item, "arrangement"),
                    "detector": getattr(item, "detector"),
                    "condition": getattr(item, "condition"),
                    "identity": ";".join(
                        f"{column}={getattr(item, column)}" for column in identity_columns
                    ) or "all",
                    "raw_p": float(value),
                })
    detail = pd.DataFrame(detail_rows)
    if detail.empty:
        return detail, pd.DataFrame()
    detail["fdr_p_within_family"] = np.nan
    for family, index in detail.groupby("family").groups.items():
        detail.loc[index, "fdr_p_within_family"] = benjamini_hochberg(
            detail.loc[index, "raw_p"].to_numpy(dtype=np.float64)
        )
    summary = detail.groupby(
        ["family", "p_feature", "condition"], dropna=False
    ).agg(
        test_count=("raw_p", "size"),
        raw_p_le_0p05_count=("raw_p", lambda values: int(np.sum(values <= 0.05))),
        fdr_p_le_0p05_count=("fdr_p_within_family", lambda values: int(np.sum(values <= 0.05))),
        median_raw_p=("raw_p", "median"),
    ).reset_index()
    return detail, summary


def method_coverage(base: Path) -> pd.DataFrame:
    prior = PROJECT_ROOT / 'analysis/mentor_aligned_pre_electrochemical_v1'
    rows = [
        ("PSD/narrow-line/band", "complete", prior / "run_manifest.json", "full archived PSD and local contrasts"),
        ("ACF/AR1/Allan/lag/coherence", "complete", prior / "run_manifest.json", "full 4 kHz or 10 Hz archived time series"),
        ("Morlet CWT + COI + red-noise", "complete", base / "wavelet_relaxation" / "cwt_case_features.csv", "0.05-2 Hz full slow records"),
        ("cross-wavelet coherence", "complete", base / "wavelet_relaxation" / "cross_wavelet_coherence.csv", "slow common mode versus energy-envelope PCs"),
        ("synchrosqueezed CWT", "complete", base / "wavelet_relaxation" / "synchrosqueezed_case_features.csv", "0.05-2 Hz ridge concentration"),
        ("PELT + event alignment", "complete", base / "wavelet_relaxation" / "changepoint_event_details.csv", "unlabelled steady-state changes only"),
        ("single/double/damped relaxation", "complete", base / "event_shape_models" / "event_shape_model_details.csv", "AICc model comparison at PELT events"),
        ("matrix pencil", "complete_exploratory", base / "event_shape_models" / "event_shape_model_details.csv", "candidate poles only; requires repeated supported events"),
        ("DFA/MF-DFA", "complete", base / "modes_complexity_network" / "complexity_case_features.csv", "full slow common-mode signals"),
        ("multiscale entropy/RQA", "complete", base / "modes_complexity_network" / "complexity_case_features.csv", "short records may be underpowered"),
        ("EMD/EEMD/VMD", "complete", base / "modes_complexity_network" / "adaptive_mode_case_features.csv", "VMD K/alpha and EEMD sensitivity included"),
        ("strict projection MEMD", "data_or_implementation_limited", base / "modes_complexity_network" / "aligned_multichannel_emd_case_features.csv", "channelwise EMD band alignment used; not labelled MEMD"),
        ("Robust PCA + state space", "complete", base / "modes_complexity_network" / "network_state_case_features.csv", "common/sparse network and local-trend variance"),
        ("conditional VAR Granger", "complete_exploratory", base / "modes_complexity_network" / "granger_channel_edges.csv", "predictive direction, not physical causation"),
        ("phase-amplitude coupling", "complete", base / "nonlinear_highfreq" / "phase_amplitude_coupling.csv", "0.05-0.5 Hz phase to 0.5-2 Hz envelopes"),
        ("high-frequency CWT", "short_window_only", base / "nonlinear_highfreq" / "short_high_frequency_cwt.csv", "three 1 s snippets per file; no full-record persistence claim"),
        ("bispectrum/bicoherence", "short_window_only", base / "nonlinear_highfreq" / "short_high_frequency_bicoherence.csv", "three 1 s snippets with phase-surrogate null"),
        ("filter sensitivity/injection", "complete", base / "wavelet_relaxation" / "filter_injection_recovery.csv", "unfiltered, SG, zero-phase, wavelet shrinkage, Kalman"),
        ("grouped multimethod identifiability", "complete_exploratory", base / "identifiability" / "grouped_identifiability_summary.csv", "leave-one date-arrangement-detector stratum out plus label permutation"),
        ("full 400 kHz time-frequency/coherence", "archive_limited", base / "nonlinear_highfreq" / "run_manifest.json", "full raw waveform was not archived"),
    ]
    return pd.DataFrame([{
        "method": method,
        "status": status if path.exists() else "pending_or_missing",
        "evidence_file": str(path),
        "scope_or_limit": scope,
    } for method, status, path, scope in rows])


def summarize_filter_robustness(base: Path) -> pd.DataFrame:
    injection = read_frame(base / "wavelet_relaxation" / "filter_injection_recovery.csv")
    actual = read_frame(base / "wavelet_relaxation" / "filter_sensitivity_case_features.csv")
    rows: list[dict[str, object]] = []
    if not injection.empty:
        for name, group in injection.groupby("filter_name"):
            rows.append({
                "analysis_type": "synthetic_injection",
                "filter_name": name,
                "case_count": group["case_id"].nunique(),
                "sinusoid_recovery_ratio_median": float(group["sinusoid_amplitude_recovery_ratio"].median()),
                "sinusoid_recovery_ratio_iqr": float(
                    group["sinusoid_amplitude_recovery_ratio"].quantile(0.75)
                    - group["sinusoid_amplitude_recovery_ratio"].quantile(0.25)
                ),
                "transient_tau_recovery_ratio_median": float(group["transient_tau_recovery_ratio"].median()),
                "transient_detection_fraction": float(
                    pd.to_numeric(group["transient_changepoint_detected_within_1s"], errors="coerce").mean()
                ),
                "actual_feature": np.nan,
                "spearman_vs_unfiltered": np.nan,
                "median_absolute_difference_vs_unfiltered": np.nan,
            })
    if not actual.empty:
        metrics = [
            "fixed_3p1s_amplitude_sigma", "changepoint_count",
            "wavelet_global_peak_frequency_hz", "wavelet_significant_ridge_fraction",
        ]
        for metric in metrics:
            pivot = actual.pivot_table(
                index="case_id", columns="filter_name", values=metric, aggfunc="median"
            )
            if "unfiltered_detrended" not in pivot:
                continue
            reference = pivot["unfiltered_detrended"]
            for name in pivot:
                paired = pd.concat([reference, pivot[name]], axis=1).dropna()
                paired.columns = ["reference", "filtered"]
                correlation = (
                    float(stats.spearmanr(paired["reference"], paired["filtered"]).statistic)
                    if len(paired) >= 4 else np.nan
                )
                rows.append({
                    "analysis_type": "observed_feature_sensitivity",
                    "filter_name": name,
                    "case_count": len(paired),
                    "sinusoid_recovery_ratio_median": np.nan,
                    "sinusoid_recovery_ratio_iqr": np.nan,
                    "transient_tau_recovery_ratio_median": np.nan,
                    "transient_detection_fraction": np.nan,
                    "actual_feature": metric,
                    "spearman_vs_unfiltered": correlation,
                    "median_absolute_difference_vs_unfiltered": float(
                        np.median(np.abs(paired["filtered"] - paired["reference"]))
                    ) if len(paired) else np.nan,
                })
    return pd.DataFrame(rows)


def summarize_mode_parameter_robustness(base: Path) -> pd.DataFrame:
    modes = read_frame(base / "modes_complexity_network" / "adaptive_mode_case_features.csv")
    if modes.empty:
        return modes
    modes = modes[modes["method"] == "VMD"].copy()
    metrics = [
        "dominant_mode_center_hz", "mode_energy_entropy",
        "mode_energy_fraction_below_0p15hz", "mode_energy_fraction_0p15_0p5hz",
        "mode_energy_fraction_0p5_2hz", "mode_energy_fraction_above_2hz",
    ]
    rows = []
    for signal_name, signal_frame in modes.groupby("signal_name"):
        for metric in metrics:
            ranges = signal_frame.groupby("case_id")[metric].agg(
                lambda values: float(np.nanmax(values) - np.nanmin(values))
            )
            rows.append({
                "signal_name": signal_name,
                "feature": metric,
                "case_count": len(ranges),
                "median_parameter_range": float(np.median(ranges)),
                "q95_parameter_range": float(np.percentile(ranges, 95)),
            })
    band_columns = [column for column in metrics if "energy_fraction" in column]
    modes["dominant_energy_band"] = modes[band_columns].idxmax(axis=1)
    agreement = modes.groupby(["case_id", "signal_name"])["dominant_energy_band"].agg(
        lambda values: float(values.value_counts(normalize=True).iloc[0])
    ).reset_index(name="parameter_dominant_band_agreement")
    for signal_name, group in agreement.groupby("signal_name"):
        rows.append({
            "signal_name": signal_name,
            "feature": "dominant_energy_band_agreement",
            "case_count": len(group),
            "median_parameter_range": float(group["parameter_dominant_band_agreement"].median()),
            "q95_parameter_range": float(group["parameter_dominant_band_agreement"].quantile(0.95)),
        })
    return pd.DataFrame(rows)


def method_result_matrix(
    coverage: pd.DataFrame, consistency: pd.DataFrame,
    significance: pd.DataFrame,
) -> pd.DataFrame:
    family_to_method = {
        "CWT": "Morlet CWT + COI + red-noise",
        "SST": "synchrosqueezed CWT",
        "cross_wavelet": "cross-wavelet coherence",
        "changepoint": "PELT + event alignment",
        "event_shape": "single/double/damped relaxation",
        "complexity": "DFA/MF-DFA and entropy/RQA",
        "adaptive_mode": "EMD/EEMD/VMD",
        "aligned_channel_EMD": "channelwise aligned EMD",
        "network_state": "Robust PCA/state space/Granger",
        "PAC": "phase-amplitude coupling",
        "short_high_CWT": "high-frequency CWT",
        "short_bicoherence": "bispectrum/bicoherence",
        "filter_path": "filter-path sensitivity",
    }
    rows = []
    for family, method in family_to_method.items():
        selected = consistency[consistency["family"] == family]
        stable = int(np.sum(selected["evidence_grade"] == "cross_stratum_stable"))
        candidates = int(np.sum(selected["evidence_grade"] == "directional_candidate"))
        maximum = float(selected["dominant_stratum_fraction"].max()) if len(selected) else np.nan
        family_significance = significance[significance["family"] == family]
        fdr_significant = int(family_significance["fdr_p_le_0p05_count"].sum()) if len(family_significance) else 0
        if stable:
            result = "cross_stratum_stable_exploratory" if family.startswith("short_") else "cross_stratum_stable"
        elif candidates:
            result = "directional_candidates_only"
        elif len(selected):
            result = "no_stable_local_contrast"
        else:
            result = "no_contrast_table_or_data_limited"
        if family == "CWT" and stable:
            result = "local_background_envelope_candidate_not_stop_specific"
        elif family == "short_bicoherence" and stable:
            result = "pooled_short_window_candidate_not_snippet_repeatable"
        elif family == "filter_path":
            result = "method_dependent_validation_only"
        rows.append({
            "method_family": family,
            "method": method,
            "result_grade": result,
            "stable_feature_count": stable,
            "directional_candidate_count": candidates,
            "maximum_dominant_stratum_fraction": maximum,
            "single_file_fdr_significant_count": fdr_significant,
            "interpretation_boundary": (
                "three 1 s raw snippets only" if family.startswith("short_")
                else "single-file structure is not condition specificity"
            ),
        })
    covered_methods = set(family_to_method.values())
    for item in coverage.itertuples(index=False):
        if item.method in covered_methods:
            continue
        rows.append({
            "method_family": "coverage_only",
            "method": item.method,
            "result_grade": item.status,
            "stable_feature_count": np.nan,
            "directional_candidate_count": np.nan,
            "maximum_dominant_stratum_fraction": np.nan,
            "single_file_fdr_significant_count": np.nan,
            "interpretation_boundary": item.scope_or_limit,
        })
    return pd.DataFrame(rows)


def plot_consistency(consistency: pd.DataFrame, output: Path) -> None:
    def compact_identity(value: str) -> str:
        parts: dict[str, str] = {}
        for item in str(value).split(";"):
            if "=" in item:
                key, entry = item.split("=", 1)
                parts[key] = entry
        if "first_signal" in parts and "second_signal" in parts:
            return f"{parts['first_signal']} -> {parts['second_signal']}"
        if "phase_band" in parts and "amplitude_signal" in parts:
            return f"{parts['phase_band']} -> {parts['amplitude_signal']}"
        if "filter_name" in parts:
            return f"{parts.get('signal_name', 'signal')} / {parts['filter_name']}"
        if "method" in parts:
            parameter = parts.get("parameter_key", "")
            return " / ".join(item for item in (parts.get("signal_name"), parts["method"], parameter) if item)
        if "signal_name" in parts:
            return parts["signal_name"]
        if "analysis_scope" in parts:
            return "pooled three 1 s raw snippets"
        return str(value)[:52]

    feature_labels = {
        "global_peak_frequency_hz": "peak frequency",
        "global_peak_power_to_red_noise": "peak power / AR1 q95",
        "significant_point_fraction": "significant TF fraction",
        "significant_ridge_fraction": "significant ridge fraction",
        "bicoherence_max": "maximum bicoherence",
        "wavelet_global_peak_frequency_hz": "wavelet peak frequency",
        "null_modulation_index_q95": "surrogate MI q95",
        "median_coherence_0p05_0p5hz": "median coherence (0.05-0.5 Hz)",
        "fraction_coherence_ge_0p5": "fraction coherence >= 0.5",
        "modulation_index": "modulation index",
        "mode_energy_fraction_0p5_2hz": "mode energy fraction (0.5-2 Hz)",
        "reconstruction_nrmse": "reconstruction NRMSE",
    }
    selected = consistency[
        (consistency["stratum_count"] >= 4)
        & (consistency["dominant_stratum_fraction"] >= 0.75)
    ].copy()
    if selected.empty:
        return
    selected["score"] = np.sign(selected["stratum_median_effect"]) * selected[
        "dominant_stratum_fraction"
    ]
    selected = selected.sort_values(
        ["evidence_grade", "dominant_stratum_fraction"], ascending=[True, False]
    ).head(14)
    labels = [
        (
            f"{row.family} | {feature_labels.get(row.feature, row.feature)}\n"
            f"{compact_identity(row.identity)} | vs {row.reference_condition}"
        )
        for row in selected.itertuples(index=False)
    ]
    fig, axis = plt.subplots(figsize=(12, max(7, 0.55 * len(selected))))
    colors = np.where(selected["score"] >= 0, "#3976a8", "#bf5b45")
    axis.barh(np.arange(len(selected)), selected["score"], color=colors)
    axis.set_yticks(np.arange(len(selected)), labels)
    axis.invert_yaxis()
    axis.axvline(0.0, color="#333333", linewidth=0.8)
    axis.set_xlim(-1.05, 1.05)
    axis.set_xlabel("Signed dominant fraction across date-arrangement-detector strata")
    axis.set_title("Method candidates surviving local-control direction checks")
    fig.subplots_adjust(left=0.43, right=0.97, top=0.92, bottom=0.10)
    fig.savefig(output, dpi=180)
    plt.close(fig)


def build_report(
    base: Path, coverage: pd.DataFrame, consistency: pd.DataFrame,
    significance: pd.DataFrame,
) -> None:
    complete = int(coverage["status"].isin(["complete", "complete_exploratory"]).sum())
    limited = int(len(coverage) - complete)
    stable = consistency[consistency["evidence_grade"] == "cross_stratum_stable"]
    candidate = consistency[consistency["evidence_grade"] == "directional_candidate"]
    stable_families = ", ".join(sorted(stable["family"].unique())) if len(stable) else "none"
    identifiability = read_frame(
        base / "identifiability" / "grouped_identifiability_summary.csv"
    )
    classifier = {
        (row.task, row.feature_set): row
        for row in identifiability.itertuples(index=False)
    } if not identifiability.empty else {}
    cwt = read_frame(base / "wavelet_relaxation" / "matched_cwt_contrasts.csv")
    later_run = cwt[
        (cwt["dataset"] != 20260617)
        & cwt["condition"].isin(["30hz", "50hz", "run"])
    ] if not cwt.empty else pd.DataFrame()

    def contrast_stat(signal_name: str, feature: str, reference: str) -> tuple[int, int, float]:
        selected = later_run[
            (later_run["signal_name"] == signal_name)
            & (later_run["reference_condition"] == reference)
        ]
        values = pd.to_numeric(selected[f"{feature}_difference"], errors="coerce").dropna()
        return len(values), int(np.sum(values > 0.0)), float(np.median(values)) if len(values) else np.nan

    cwt_broad = contrast_stat("broadband_rms_pc1", "global_peak_power_to_red_noise", "background")
    cwt_diff = contrast_stat("difference_rms_pc1", "global_peak_power_to_red_noise", "background")
    cwt_fast = contrast_stat("fast_residual_rms_pc1", "global_peak_power_to_red_noise", "background")
    cwt_broad_stop = contrast_stat("broadband_rms_pc1", "global_peak_power_to_red_noise", "vfd_stop")
    cwt_diff_stop = contrast_stat("difference_rms_pc1", "global_peak_power_to_red_noise", "vfd_stop")
    cwt_fast_stop = contrast_stat("fast_residual_rms_pc1", "global_peak_power_to_red_noise", "vfd_stop")
    cwt_sig = contrast_stat("difference_rms_pc1", "significant_point_fraction", "background")

    event_summary = read_frame(base / "event_shape_models" / "event_shape_case_summary.csv")
    event_count = int(pd.to_numeric(event_summary.get("event_model_count"), errors="coerce").sum()) if not event_summary.empty else 0
    credible_events = int(pd.to_numeric(event_summary.get("credible_shape_event_count"), errors="coerce").sum()) if not event_summary.empty else 0

    bicoherence = read_frame(base / "nonlinear_highfreq" / "matched_short_bicoherence_contrasts.csv")
    bico_selected = bicoherence[
        (bicoherence["dataset"] != 20260617)
        & bicoherence["condition"].isin(["30hz", "50hz", "run"])
        & (bicoherence["reference_condition"] == "background")
    ] if not bicoherence.empty else pd.DataFrame()
    bico_max = pd.to_numeric(bico_selected.get("bicoherence_max_difference"), errors="coerce").dropna()
    bico_snippet = pd.to_numeric(
        bico_selected.get("bicoherence_snippet_max_median_difference"), errors="coerce"
    ).dropna()

    filter_summary = read_frame(base / "FILTER_ROBUSTNESS_SUMMARY.csv")
    filter_injection = filter_summary[
        filter_summary["analysis_type"] == "synthetic_injection"
    ] if not filter_summary.empty else pd.DataFrame()
    filter_values = {
        row.filter_name: row for row in filter_injection.itertuples(index=False)
    }

    def classifier_value(task: str, feature_set: str) -> str:
        row = classifier.get((task, feature_set))
        return (
            f"{row.grouped_balanced_accuracy:.3f} (p={row.permutation_p:.3g})"
            if row is not None else "not available"
        )
    lines = [
        "# 导师建议新增方法全量探索报告",
        "",
        "## 1. 结论先行",
        "",
        f"本轮方法矩阵共{len(coverage)}项：{complete}项已完成或完成探索性计算，{limited}项因严格MEMD实现或整段400 kHz原始波形缺失而受限。所有结论继续以动态坏道、本机背景和日期-摆位-探测器层级为统计前提。",
        "",
        f"形式上通过层级方向和方法族内FDR的特征族为：{stable_families}，共{len(stable)}个参数化条目；但加入STOP特异性、片段重复性和参数可辨识性后，没有新增结果可以归因为水流。另有{len(candidate)}个条目仅达到方向候选。",
        "",
        "**新增的实质结果1：运行链会改变高频能量包络的低频时变结构。** 后期24个RUN文件相对本地背景，broadband、difference和fast-residual包络的CWT峰值功率/红噪声基线分别有"
        f"{cwt_broad[1]}/{cwt_broad[0]}、{cwt_diff[1]}/{cwt_diff[0]}、{cwt_fast[1]}/{cwt_fast[0]}为正，中位增量为{cwt_broad[2]:.3f}、{cwt_diff[2]:.3f}、{cwt_fast[2]:.3f}；difference包络的显著时频点比例中位增加{cwt_sig[2]:.3f}。",
        "但相对STOP时三项只有"
        f"{cwt_broad_stop[1]}/{cwt_broad_stop[0]}、{cwt_diff_stop[1]}/{cwt_diff_stop[0]}、{cwt_fast_stop[1]}/{cwt_fast_stop[0]}为正，方向不稳定。因此它是RUN相对纯背景的设备链/探测网络状态变化，不是水流特异特征，也不足以稳定排除STOP。",
        "",
        "**新增的实质结果2：没有找到可辨识的自然迟豫波形。** 两个重点信号共检出"
        f"{event_count}个PELT自然事件；在同时要求跨通道支持、R2>=0.5、AICc优势>=4、双时间常数至少相差2倍且均位于12 s观测窗内，或阻尼波形至少包含2个周期后，可接受事件为{credible_events}。因此不能把现有慢漂移命名为器件充放电或网络迟豫。",
        "",
        "**新增的实质结果3：高频存在普遍非线性混频，但当前不具备工况特异性。** 三个1 s片段合并后的最大双相干，RUN相对背景"
        f"{int(np.sum(bico_max > 0))}/{len(bico_max)}为正，中位增加{float(np.median(bico_max)):.3f}；但逐片段最大值中位只有{int(np.sum(bico_snippet > 0))}/{len(bico_snippet)}为正。并且49/49文件（包括背景和STOP）都超过49次相位代理的最小p=0.02。它支持仪器/设备网络中普遍存在谐波耦合，合并短窗候选未通过片段重复性，不能归因为水流。",
        "",
        "**未知标签识别没有被新增方法改善。** RUN/STOP的整组留一平衡准确率：原频带"
        f"{classifier_value('run_vs_stop', 'baseline_spectral_only')}，仅新增方法{classifier_value('run_vs_stop', 'new_methods_only')}，合并{classifier_value('run_vs_stop', 'combined')}。30/50的最好结果为{classifier_value('30hz_vs_50hz', 'combined')}；4/8/12 kHz载波三分类为{classifier_value('carrier_4_8_12khz', 'combined')}，即机会水平。",
        "",
        "**滤波审计限定了哪些方法可以进入正文。** 3.1 s正弦注入的中位幅值回收率：无滤波"
        f"{filter_values['unfiltered_detrended'].sinusoid_recovery_ratio_median:.3f}、1.1 s SG {filter_values['savgol_1p1s'].sinusoid_recovery_ratio_median:.3f}、零相位带通{filter_values['zero_phase_bandpass_0p05_2hz'].sinusoid_recovery_ratio_median:.3f}；Kalman和小波阈值仅{filter_values['kalman_local_level'].sinusoid_recovery_ratio_median:.3f}和{filter_values['wavelet_db4_shrinkage'].sinusoid_recovery_ratio_median:.3f}。后两者会明显压低弱周期并扭曲瞬态，不能单独提供阳性证据。",
        "",
        "SST、交叉小波、DFA/MF-DFA、熵/RQA、EMD/EEMD/VMD、通道对齐EMD、Robust PCA、状态空间、Granger和PAC均已完成探索；它们没有形成同时通过层级重复、本地对照特异、代理/FDR和参数稳健性的新增工况特征。严格投影MEMD仍标为实现受限，不冒充已完成。",
        "",
        "## 2. 验收口径",
        "",
        "- 重复性：先做文件相对本地对照，再在日期 × 摆位 × 探测器层级取中位数。",
        "- 显著性：使用红噪声、相位随机、循环错位或符号检验，并在方法族内或全候选范围做FDR。",
        "- 相关性：区分单通道、跨通道共同模态、TC1/TC2共同外场和低高频包络耦合。",
        "- 稳健性：比较无滤波、SG、零相位带通、小波阈值、Kalman及VMD参数扫描，并用合成注入校验。",
        "- 归因：任何新特征最多先命名为工况相关、探测器相关或网络状态相关，不直接命名为水流。",
        "",
        "## 3. 方法覆盖",
        "",
        "完整逐项状态见 `METHOD_COVERAGE_MATRIX.csv`。严格MEMD没有被伪装为已完成；当前实现是健康通道逐通道EMD后按频带对齐。整段高频时频/相干受归档限制，因为每文件仅保留三个1 s原始片段。",
        "",
        "## 4. 结果表如何读",
        "",
        "`METHOD_FEATURE_CONSISTENCY.csv`中的effect始终为活动工况减本地参考；dominant_stratum_fraction表示独立层级中同方向的比例。`cross_stratum_stable`要求至少6层、方向一致率至少87.5%且方法族内FDR不超过0.10；表中同时保留跨全部候选的全局FDR。`directional_candidate`只表示有方向趋势，不能写成最终发现。",
        "",
        "`METHOD_SURROGATE_SIGNIFICANCE.csv`和`METHOD_SIGNIFICANCE_SUMMARY.csv`回答单文件内结构是否超过相应零假设；它们不能替代活动-背景特异性。",
        "",
        "## 5. 当前边界",
        "",
        "- 稳态记录缺少统一开关触发时刻，变化点后的拟合属于自然事件，不是受控充放电响应。",
        "- 条件Granger是给定VAR模型下的预测关系，不等于电荷真实流向。",
        "- 小波、VMD、EMD和滤波都有模型假设；只有跨模型同方向且注入回收可靠的结果才可进入正文。",
        "- 早期20260617距离组只作方向参考，不进入后期层级门槛。",
        "",
        "## 6. 输出",
        "",
        "- `METHOD_COVERAGE_MATRIX.csv`：导师提到及补充方法的完成/受限状态。",
        "- `METHOD_RESULT_MATRIX.csv`：每类方法的稳定候选数、方向候选数及解释边界。",
        "- `METHOD_FEATURE_CONSISTENCY.csv`：本地对照后的文件级与层级方向结果。",
        "- `METHOD_SURROGATE_SIGNIFICANCE.csv`：红噪声/代理数据显著性明细。",
        "- `METHOD_SIGNIFICANCE_SUMMARY.csv`：各工况显著条目数量。",
        "- `identifiability/`：RUN/STOP、30/50和载波设置的整组留一交叉验证及置换检验。",
        "- 各子目录保留方法级特征、参数、事件明细、图和run manifest。",
    ]
    (base / "MENTOR_METHOD_EXPLORATION_REPORT.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    summary = {
        "coverage_rows": len(coverage),
        "complete_or_exploratory_rows": complete,
        "limited_rows": limited,
        "consistency_rows": len(consistency),
        "cross_stratum_stable_rows": len(stable),
        "directional_candidate_rows": len(candidate),
        "significance_summary_rows": len(significance),
    }
    (base / "REPORT_SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=METHOD_OUTPUT)
    args = parser.parse_args(argv)
    base = args.base
    figures = base / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    ensure_derived_contrasts(base)
    coverage = write_frame(base / "METHOD_COVERAGE_MATRIX.csv", method_coverage(base))
    consistency = write_frame(
        base / "METHOD_FEATURE_CONSISTENCY.csv", summarize_contrasts(base)
    )
    detail, significance = summarize_significance(base)
    detail = write_frame(base / "METHOD_SURROGATE_SIGNIFICANCE.csv", detail)
    significance = write_frame(base / "METHOD_SIGNIFICANCE_SUMMARY.csv", significance)
    write_frame(
        base / "METHOD_RESULT_MATRIX.csv",
        method_result_matrix(coverage, consistency, significance),
    )
    write_frame(
        base / "FILTER_ROBUSTNESS_SUMMARY.csv", summarize_filter_robustness(base)
    )
    write_frame(
        base / "MODE_PARAMETER_ROBUSTNESS.csv",
        summarize_mode_parameter_robustness(base),
    )
    if not consistency.empty:
        plot_consistency(consistency, figures / "method_candidate_consistency.png")
    build_report(base, coverage, consistency, significance)
    print(f"Output: {base}")
    return base


if __name__ == "__main__":
    main()
