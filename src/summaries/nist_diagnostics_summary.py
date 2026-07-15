import numpy as np
import pandas as pd


NIST_GROUP_SUMMARY_COLUMNS = [
    'group',
    'channel',
    'file_count',
    'mean_run_drift_ratio_ac',
    'max_run_drift_ratio_ac',
    'mean_run_rolling_mean_range',
    'max_run_rolling_mean_range',
    'mean_run_rolling_ac_rms_cv',
    'max_run_rolling_ac_rms_cv',
    'mean_run_max_step_jump_ratio_ac',
    'max_run_max_step_jump_ratio_ac',
    'mean_lag_1_corr',
    'max_abs_lag_1_corr',
    'mean_lag_2_corr',
    'max_abs_lag_2_corr',
    'mean_acf_first_peak_value',
    'max_acf_first_peak_value',
    'mean_dist_iqr',
    'mean_dist_skewness',
    'mean_dist_kurtosis',
    'mean_dist_robust_tail_fraction',
    'max_dist_robust_tail_fraction',
    'mean_dist_mode_ratio',
    'max_dist_mode_ratio',
    'mean_qq_normal_prob_corr',
    'min_qq_normal_prob_corr',
    'mean_qq_tail_deviation',
    'max_qq_tail_deviation',
]


def _finite(series):
    values = pd.to_numeric(series, errors='coerce').to_numpy(dtype=float)
    return values[np.isfinite(values)]


def _mean(group, column):
    values = _finite(group[column]) if column in group else np.asarray([])
    return float(np.mean(values)) if values.size else np.nan


def _max(group, column):
    values = _finite(group[column]) if column in group else np.asarray([])
    return float(np.max(values)) if values.size else np.nan


def _min(group, column):
    values = _finite(group[column]) if column in group else np.asarray([])
    return float(np.min(values)) if values.size else np.nan


def _max_abs(group, column):
    values = _finite(group[column]) if column in group else np.asarray([])
    return float(np.max(np.abs(values))) if values.size else np.nan


def summarize_nist_diagnostics(rows):
    """Summarize per-file/channel NIST diagnostics by group and channel."""
    if not rows:
        return pd.DataFrame(columns=NIST_GROUP_SUMMARY_COLUMNS)

    df = pd.DataFrame(rows)
    summary_rows = []
    for (group_name, channel), group_df in df.groupby(['group', 'channel'], dropna=False):
        summary_rows.append({
            'group': group_name,
            'channel': channel,
            'file_count': int(len(group_df)),
            'mean_run_drift_ratio_ac': _mean(group_df, 'run_drift_ratio_ac'),
            'max_run_drift_ratio_ac': _max(group_df, 'run_drift_ratio_ac'),
            'mean_run_rolling_mean_range': _mean(group_df, 'run_rolling_mean_range'),
            'max_run_rolling_mean_range': _max(group_df, 'run_rolling_mean_range'),
            'mean_run_rolling_ac_rms_cv': _mean(group_df, 'run_rolling_ac_rms_cv'),
            'max_run_rolling_ac_rms_cv': _max(group_df, 'run_rolling_ac_rms_cv'),
            'mean_run_max_step_jump_ratio_ac': _mean(group_df, 'run_max_step_jump_ratio_ac'),
            'max_run_max_step_jump_ratio_ac': _max(group_df, 'run_max_step_jump_ratio_ac'),
            'mean_lag_1_corr': _mean(group_df, 'lag_1_corr'),
            'max_abs_lag_1_corr': _max_abs(group_df, 'lag_1_corr'),
            'mean_lag_2_corr': _mean(group_df, 'lag_2_corr'),
            'max_abs_lag_2_corr': _max_abs(group_df, 'lag_2_corr'),
            'mean_acf_first_peak_value': _mean(group_df, 'acf_first_peak_value'),
            'max_acf_first_peak_value': _max(group_df, 'acf_first_peak_value'),
            'mean_dist_iqr': _mean(group_df, 'dist_iqr'),
            'mean_dist_skewness': _mean(group_df, 'dist_skewness'),
            'mean_dist_kurtosis': _mean(group_df, 'dist_kurtosis'),
            'mean_dist_robust_tail_fraction': _mean(group_df, 'dist_robust_tail_fraction'),
            'max_dist_robust_tail_fraction': _max(group_df, 'dist_robust_tail_fraction'),
            'mean_dist_mode_ratio': _mean(group_df, 'dist_mode_ratio'),
            'max_dist_mode_ratio': _max(group_df, 'dist_mode_ratio'),
            'mean_qq_normal_prob_corr': _mean(group_df, 'qq_normal_prob_corr'),
            'min_qq_normal_prob_corr': _min(group_df, 'qq_normal_prob_corr'),
            'mean_qq_tail_deviation': _mean(group_df, 'qq_tail_deviation'),
            'max_qq_tail_deviation': _max(group_df, 'qq_tail_deviation'),
        })

    return pd.DataFrame(summary_rows, columns=NIST_GROUP_SUMMARY_COLUMNS)
