from pathlib import Path

import numpy as np

from src.core.constants import FILE_DURATION
from src.features.time_metrics import clean_metric_value, finite_values


GROUP_SUMMARY_COLUMNS = [
    'channel',
    'group',
    'file_count',
    'expected_file_count',
    'missing_file_count',
    'missing_flag',
    'mean_of_file_means',
    'std_of_file_means',
    'range_of_file_means',
    'baseline_stability_factor',
    'baseline_instability_ratio',
    'mean_robust_sigma',
    'std_robust_sigma',
    'max_robust_sigma',
    'robust_sigma_cv',
    'mean_ac_rms',
    'std_ac_rms',
    'cv_ac_rms',
    'mean_crest_factor',
    'max_crest_factor',
    'max_peak_to_peak',
    'median_drift_ratio_robust',
    'max_drift_ratio_robust',
    'median_drift_ratio_ac',
    'max_drift_ratio_ac',
    'cross_drift_slope_v_per_s',
    'cross_drift_span',
    'cross_drift_ratio_robust',
    'cross_drift_ratio_ac',
    'median_robust_sigma_for_ratio',
    'mean_candidate_isolated_spike_rate',
    'max_candidate_isolated_spike_rate',
    'mean_candidate_cluster_spike_rate',
    'max_candidate_cluster_spike_rate',
    'mean_robust_tail_fraction',
    'max_robust_tail_fraction',
    'mean_repeated_extreme_rate',
    'max_repeated_extreme_rate',
    'max_repeated_extreme_count',
    'mean_sample_count',
    'mean_duration_s',
    'mean_fs_hz',
    'mean_std_v',
    'mean_rms_v',
    'mean_p2p_v',
    'mean_q05',
    'mean_q50',
    'mean_q95',
    'mean_clipping_rate',
    'mean_duplicate_rate',
    'mean_quantization_step_estimate',
    'qc_flag',
]


def summarize_group_metrics(channel_rows, group_dir):
    """Summarize per-file metrics into one group-level row per channel."""
    summary_rows = {}
    expected_file_count = max((len(rows) for rows in channel_rows.values()), default=0)
    group_noise = {
        channel: np.nanmedian(finite_values(rows, 'robust_sigma'))
        for channel, rows in channel_rows.items()
    }
    finite_group_noise = np.asarray([value for value in group_noise.values() if np.isfinite(value)], dtype=float)
    noise_median = float(np.median(finite_group_noise)) if finite_group_noise.size else np.nan
    noise_mad = float(1.4826 * np.median(np.abs(finite_group_noise - noise_median))) if finite_group_noise.size else np.nan
    noise_q20 = float(np.percentile(finite_group_noise, 20)) if finite_group_noise.size else np.nan
    noise_q80 = float(np.percentile(finite_group_noise, 80)) if finite_group_noise.size else np.nan
    noise_q90 = float(np.percentile(finite_group_noise, 90)) if finite_group_noise.size else np.nan

    for channel, rows in channel_rows.items():
        valid_rows = [row for row in rows if _is_valid_metric_row(row)]
        file_means = finite_values(rows, 'mean')
        robust_sigma_values = finite_values(rows, 'robust_sigma')
        ac_rms_values = finite_values(rows, 'ac_rms')
        crest_factors = finite_values(rows, 'crest_factor')
        peak_to_peak_values = finite_values(rows, 'peak_to_peak')
        drift_ratios_robust = finite_values(rows, 'drift_ratio_robust')
        drift_ratios_ac = finite_values(rows, 'drift_ratio_ac')
        isolated_spike_rates = finite_values(rows, 'candidate_isolated_spike_rate')
        cluster_spike_rates = finite_values(rows, 'candidate_cluster_spike_rate')
        robust_tail_fractions = finite_values(rows, 'robust_tail_fraction')
        repeated_extreme_rates = finite_values(rows, 'repeated_extreme_rate')
        repeated_extreme_counts = finite_values(rows, 'repeated_extreme_count')
        sample_counts = finite_values(rows, 'sample_count')
        durations = finite_values(rows, 'duration_s')
        fs_values = finite_values(rows, 'fs_hz')
        std_values = finite_values(rows, 'std_v')
        q05_values = finite_values(rows, 'q05')
        q50_values = finite_values(rows, 'q50')
        q95_values = finite_values(rows, 'q95')
        duplicate_rates = finite_values(rows, 'duplicate_rate')
        quant_steps = finite_values(rows, 'quantization_step_estimate')

        if file_means.size:
            mean_of_file_means = float(np.mean(file_means))
            std_of_file_means = float(np.std(file_means))
            range_of_file_means = float(np.max(file_means) - np.min(file_means))
        else:
            mean_of_file_means = np.nan
            std_of_file_means = np.nan
            range_of_file_means = np.nan

        if robust_sigma_values.size:
            mean_robust_sigma = float(np.mean(robust_sigma_values))
            std_robust_sigma = float(np.std(robust_sigma_values))
            max_robust_sigma = float(np.max(robust_sigma_values))
            robust_sigma_cv = float(std_robust_sigma / mean_robust_sigma) if mean_robust_sigma > 0 else np.nan
            median_robust_sigma = float(np.median(robust_sigma_values))
        else:
            mean_robust_sigma = np.nan
            std_robust_sigma = np.nan
            max_robust_sigma = np.nan
            robust_sigma_cv = np.nan
            median_robust_sigma = np.nan

        if ac_rms_values.size:
            mean_ac_rms = float(np.mean(ac_rms_values))
            std_ac_rms = float(np.std(ac_rms_values))
            cv_ac_rms = float(std_ac_rms / mean_ac_rms) if mean_ac_rms > 0 else np.nan
        else:
            mean_ac_rms = np.nan
            std_ac_rms = np.nan
            cv_ac_rms = np.nan

        if crest_factors.size:
            mean_crest_factor = float(np.mean(crest_factors))
            max_crest_factor = float(np.max(crest_factors))
        else:
            mean_crest_factor = np.nan
            max_crest_factor = np.nan

        max_peak_to_peak = float(np.max(peak_to_peak_values)) if peak_to_peak_values.size else np.nan

        if std_of_file_means > 0 and np.isfinite(mean_ac_rms):
            baseline_stability_factor = float(mean_ac_rms / std_of_file_means)
        else:
            baseline_stability_factor = np.nan

        if mean_ac_rms > 0 and np.isfinite(std_of_file_means):
            baseline_instability_ratio = float(std_of_file_means / mean_ac_rms)
        else:
            baseline_instability_ratio = np.nan

        if drift_ratios_robust.size:
            median_drift_ratio_robust = float(np.median(drift_ratios_robust))
            max_drift_ratio_robust = float(np.max(drift_ratios_robust))
        else:
            median_drift_ratio_robust = np.nan
            max_drift_ratio_robust = np.nan

        if drift_ratios_ac.size:
            median_drift_ratio_ac = float(np.median(drift_ratios_ac))
            max_drift_ratio_ac = float(np.max(drift_ratios_ac))
        else:
            median_drift_ratio_ac = np.nan
            max_drift_ratio_ac = np.nan

        cross_drift_slope_v_per_s = np.nan
        cross_drift_span = np.nan
        cross_drift_ratio_robust = np.nan
        cross_drift_ratio_ac = np.nan
        if file_means.size >= 2:
            file_times = np.arange(file_means.size, dtype=float) * FILE_DURATION
            cross_drift_slope_v_per_s, _ = np.polyfit(file_times, file_means, 1)
            cross_drift_slope_v_per_s = float(cross_drift_slope_v_per_s)
            cross_drift_span = float(abs(cross_drift_slope_v_per_s) * FILE_DURATION * (file_means.size - 1))
            if median_robust_sigma > 0:
                cross_drift_ratio_robust = float(cross_drift_span / median_robust_sigma)
            if mean_ac_rms > 0:
                cross_drift_ratio_ac = float(cross_drift_span / mean_ac_rms)

        mean_isolated_spike_rate = float(np.mean(isolated_spike_rates)) if isolated_spike_rates.size else np.nan
        max_isolated_spike_rate = float(np.max(isolated_spike_rates)) if isolated_spike_rates.size else np.nan
        mean_cluster_spike_rate = float(np.mean(cluster_spike_rates)) if cluster_spike_rates.size else np.nan
        max_cluster_spike_rate = float(np.max(cluster_spike_rates)) if cluster_spike_rates.size else np.nan
        mean_robust_tail_fraction = float(np.mean(robust_tail_fractions)) if robust_tail_fractions.size else np.nan
        max_robust_tail_fraction = float(np.max(robust_tail_fractions)) if robust_tail_fractions.size else np.nan
        mean_repeated_extreme_rate = float(np.mean(repeated_extreme_rates)) if repeated_extreme_rates.size else np.nan
        max_repeated_extreme_rate = float(np.max(repeated_extreme_rates)) if repeated_extreme_rates.size else np.nan
        max_repeated_extreme_count = int(np.max(repeated_extreme_counts)) if repeated_extreme_counts.size else 0

        actual_file_count = len(valid_rows)
        missing_file_count = max(0, expected_file_count - actual_file_count)
        qc_flag = _group_qc_flag(
            missing_file_count=missing_file_count,
            channel_noise=group_noise.get(channel),
            noise_median=noise_median,
            noise_mad=noise_mad,
            noise_q20=noise_q20,
            noise_q80=noise_q80,
            noise_q90=noise_q90,
            robust_sigma_cv=robust_sigma_cv,
            max_drift_ratio=max_drift_ratio_robust,
            clipping_rate=max_repeated_extreme_rate,
        )

        summary_rows[channel] = {
            'group': Path(group_dir).name,
            'file_count': actual_file_count,
            'expected_file_count': expected_file_count,
            'missing_file_count': missing_file_count,
            'missing_flag': bool(missing_file_count > 0),
            'mean_of_file_means': mean_of_file_means,
            'std_of_file_means': std_of_file_means,
            'range_of_file_means': range_of_file_means,
            'baseline_stability_factor': baseline_stability_factor,
            'baseline_instability_ratio': baseline_instability_ratio,
            'mean_robust_sigma': mean_robust_sigma,
            'std_robust_sigma': std_robust_sigma,
            'max_robust_sigma': max_robust_sigma,
            'robust_sigma_cv': robust_sigma_cv,
            'mean_ac_rms': mean_ac_rms,
            'std_ac_rms': std_ac_rms,
            'cv_ac_rms': cv_ac_rms,
            'mean_crest_factor': mean_crest_factor,
            'max_crest_factor': max_crest_factor,
            'max_peak_to_peak': max_peak_to_peak,
            'median_drift_ratio_robust': median_drift_ratio_robust,
            'max_drift_ratio_robust': max_drift_ratio_robust,
            'median_drift_ratio_ac': median_drift_ratio_ac,
            'max_drift_ratio_ac': max_drift_ratio_ac,
            'cross_drift_slope_v_per_s': cross_drift_slope_v_per_s,
            'cross_drift_span': cross_drift_span,
            'cross_drift_ratio_robust': cross_drift_ratio_robust,
            'cross_drift_ratio_ac': cross_drift_ratio_ac,
            'median_robust_sigma_for_ratio': median_robust_sigma,
            'mean_candidate_isolated_spike_rate': mean_isolated_spike_rate,
            'max_candidate_isolated_spike_rate': max_isolated_spike_rate,
            'mean_candidate_cluster_spike_rate': mean_cluster_spike_rate,
            'max_candidate_cluster_spike_rate': max_cluster_spike_rate,
            'mean_robust_tail_fraction': mean_robust_tail_fraction,
            'max_robust_tail_fraction': max_robust_tail_fraction,
            'mean_repeated_extreme_rate': mean_repeated_extreme_rate,
            'max_repeated_extreme_rate': max_repeated_extreme_rate,
            'max_repeated_extreme_count': max_repeated_extreme_count,
            'mean_sample_count': _mean(sample_counts),
            'mean_duration_s': _mean(durations),
            'mean_fs_hz': _mean(fs_values),
            'mean_std_v': _mean(std_values),
            'mean_rms_v': mean_ac_rms,
            'mean_p2p_v': _mean(peak_to_peak_values),
            'mean_q05': _mean(q05_values),
            'mean_q50': _mean(q50_values),
            'mean_q95': _mean(q95_values),
            'mean_clipping_rate': mean_repeated_extreme_rate,
            'mean_duplicate_rate': _mean(duplicate_rates),
            'mean_quantization_step_estimate': _mean(quant_steps),
            'qc_flag': qc_flag,
        }

    return {
        channel: {key: clean_metric_value(value) for key, value in row.items()}
        for channel, row in summary_rows.items()
    }


def summarize_data_completeness(channel_rows, group_dir):
    expected = max((len(rows) for rows in channel_rows.values()), default=0)
    rows = []
    for channel, channel_records in channel_rows.items():
        actual = sum(1 for row in channel_records if _is_valid_metric_row(row))
        missing = max(0, expected - actual)
        rows.append({
            'group': Path(group_dir).name,
            'channel': channel,
            'expected_file_count': expected,
            'actual_file_count': actual,
            'missing_file_count': missing,
            'missing_flag': bool(missing > 0),
        })
    return rows


def _is_valid_metric_row(row):
    value = row.get('sample_count')
    try:
        return np.isfinite(float(value)) and float(value) > 0
    except (TypeError, ValueError):
        return False


def _mean(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    return float(np.mean(values)) if values.size else np.nan


def _group_qc_flag(missing_file_count, channel_noise, noise_median, noise_mad, noise_q20, noise_q80, noise_q90, robust_sigma_cv, max_drift_ratio, clipping_rate):
    flags = []
    if missing_file_count > 0:
        flags.append('MISSING_FILES')
    if np.isfinite(channel_noise) and np.isfinite(noise_median) and channel_noise > noise_median + max(3 * noise_mad, noise_median):
        flags.append('HIGH_NOISE')
    elif np.isfinite(channel_noise) and np.isfinite(noise_q80) and channel_noise >= noise_q80:
        flags.append('CHECK_CHANNEL')
    if np.isfinite(channel_noise) and np.isfinite(noise_q20) and channel_noise <= noise_q20:
        flags.append('CHECK_CHANNEL')
    if np.isfinite(channel_noise) and np.isfinite(noise_q90) and channel_noise >= noise_q90 and 'HIGH_NOISE' not in flags:
        flags.append('HIGH_NOISE')
    if np.isfinite(robust_sigma_cv) and robust_sigma_cv > 1:
        flags.append('CHECK_CHANNEL')
    if np.isfinite(max_drift_ratio) and max_drift_ratio > 1:
        flags.append('HIGH_DRIFT')
    if np.isfinite(clipping_rate) and clipping_rate > 0.001:
        flags.append('POSSIBLE_CLIPPING')
    return '|'.join(flags) if flags else 'OK'
