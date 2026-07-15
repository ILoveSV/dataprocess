import numpy as np
import pandas as pd
from scipy import stats

from src.core.constants import (
    FILE_DURATION,
    OUTLIER_SIGMA_MULTIPLIER,
    TAIL_SIGMA_MULTIPLIER,
)


DEFAULT_ROLLING_WINDOW_SECONDS = 0.1
DEFAULT_MAX_ACF_LAG = 200
MAX_QQ_POINTS = 20000


def _clean_xy(x, time=None):
    x_arr = np.asarray(x, dtype=float)
    if time is None:
        valid = np.isfinite(x_arr)
        return x_arr[valid], None

    t_arr = pd.to_numeric(pd.Series(time), errors='coerce').to_numpy(dtype=float)
    valid = np.isfinite(x_arr) & np.isfinite(t_arr)
    x_clean = x_arr[valid]
    t_clean = t_arr[valid]
    if x_clean.size:
        t_clean = t_clean - t_clean[0]
    return x_clean, t_clean


def _safe_std(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    return float(np.std(values)) if values.size else np.nan


def _safe_cv(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return np.nan
    mean_val = float(np.mean(values))
    if mean_val == 0:
        return np.nan
    return float(np.std(values) / abs(mean_val))


def _robust_sigma(x):
    if x.size == 0:
        return np.nan
    med = np.median(x)
    return float(1.4826 * np.median(np.abs(x - med)))


def _duration_and_time_axis(x, time):
    n = len(x)
    if time is not None and len(time) == n and n >= 2:
        duration = float(time[-1] - time[0])
        if duration > 0:
            return duration, time
    duration = float(FILE_DURATION)
    return duration, np.linspace(0.0, duration, n, endpoint=False)


def _rolling_window_samples(time_axis, n, window_seconds):
    if n <= 1:
        return 1
    dt = np.diff(time_axis)
    dt = dt[np.isfinite(dt) & (dt > 0)]
    if dt.size:
        dt_median = float(np.median(dt))
    else:
        dt_median = FILE_DURATION / max(n, 1)
    if dt_median <= 0:
        return max(3, min(n, 101))
    window = int(round(float(window_seconds) / dt_median))
    return max(3, min(n, window))


def compute_run_sequence_metrics(x, time=None, window_seconds=None, centered_plot=False, millivolt_centered_plot=False):
    """Compute NIST run-sequence diagnostics without plotting."""
    x, time = _clean_xy(x, time)
    n = len(x)
    if n == 0:
        return _empty_run_sequence_result()

    duration, time_axis = _duration_and_time_axis(x, time)
    run_mean = float(np.mean(x))
    run_median = float(np.median(x))
    run_std = float(np.std(x))
    x_ac = x - run_mean
    run_ac_rms = float(np.sqrt(np.mean(x_ac ** 2)))
    run_robust_sigma = _robust_sigma(x)

    if n >= 2 and duration > 0:
        run_drift_slope, _ = np.polyfit(time_axis, x, 1)
        run_drift_slope = float(run_drift_slope)
        run_drift_span = float(abs(run_drift_slope) * duration)
    else:
        run_drift_slope = np.nan
        run_drift_span = np.nan

    run_drift_ratio_ac = float(run_drift_span / run_ac_rms) if run_ac_rms > 0 and np.isfinite(run_drift_span) else np.nan
    run_drift_ratio_robust = (
        float(run_drift_span / run_robust_sigma)
        if run_robust_sigma > 0 and np.isfinite(run_drift_span)
        else np.nan
    )

    window_seconds = DEFAULT_ROLLING_WINDOW_SECONDS if window_seconds is None else window_seconds
    window = _rolling_window_samples(time_axis, n, window_seconds)
    rolling_time, rolling_mean, rolling_ac_rms, rolling_mad = _window_block_stats(x, time_axis, window)

    finite_rolling_mean = rolling_mean[np.isfinite(rolling_mean)]
    run_rolling_mean_range = (
        float(np.max(finite_rolling_mean) - np.min(finite_rolling_mean))
        if finite_rolling_mean.size
        else np.nan
    )
    run_rolling_ac_rms_cv = _safe_cv(rolling_ac_rms)
    run_rolling_mad_cv = _safe_cv(rolling_mad)

    if n >= 2:
        max_step_jump = float(np.max(np.abs(np.diff(x))))
    else:
        max_step_jump = np.nan
    run_max_step_jump_ratio_ac = float(max_step_jump / run_ac_rms) if run_ac_rms > 0 and np.isfinite(max_step_jump) else np.nan

    metrics = {
        'run_mean': run_mean,
        'run_median': run_median,
        'run_std': run_std,
        'run_ac_rms': run_ac_rms,
        'run_robust_sigma': run_robust_sigma,
        'run_drift_slope': run_drift_slope,
        'run_drift_span': run_drift_span,
        'run_drift_ratio_ac': run_drift_ratio_ac,
        'run_drift_ratio_robust': run_drift_ratio_robust,
        'run_rolling_mean_range': run_rolling_mean_range,
        'run_rolling_ac_rms_cv': run_rolling_ac_rms_cv,
        'run_rolling_mad_cv': run_rolling_mad_cv,
        'run_max_step_jump': max_step_jump,
        'run_max_step_jump_ratio_ac': run_max_step_jump_ratio_ac,
        'run_drift_flag': bool(np.isfinite(run_drift_ratio_ac) and run_drift_ratio_ac > 0.3),
    }
    plot_data = {
        'time_or_index': time_axis,
        'x_for_plot': x,
        'x_axis_label': 'Elapsed time (s)' if time is not None else 'Sample index',
        'center_value': run_median if centered_plot or millivolt_centered_plot else np.nan,
        'y_scale': 1000.0 if millivolt_centered_plot else 1.0,
        'y_axis_label': 'x - median (mV)' if millivolt_centered_plot else ('x - median' if centered_plot else 'Value'),
        'rolling_time_for_plot': rolling_time,
        'rolling_mean_for_plot': rolling_mean,
        'rolling_ac_rms_for_plot': rolling_ac_rms,
    }
    return {'metrics': metrics, 'plot_data': plot_data}


def _window_block_stats(x, time_axis, window):
    """Compute windowed run-sequence stats using non-overlapping blocks."""
    if len(x) == 0:
        empty = np.asarray([])
        return empty, empty, empty, empty

    window = max(1, int(window))
    centers = []
    means = []
    ac_rms_values = []
    mad_values = []
    for start in range(0, len(x), window):
        stop = min(start + window, len(x))
        block = x[start:stop]
        if block.size < 2:
            continue
        block_mean = float(np.mean(block))
        centered = block - block_mean
        centers.append(float(np.mean(time_axis[start:stop])))
        means.append(block_mean)
        ac_rms_values.append(float(np.sqrt(np.mean(centered ** 2))))
        mad_values.append(_robust_sigma(block))

    return (
        np.asarray(centers, dtype=float),
        np.asarray(means, dtype=float),
        np.asarray(ac_rms_values, dtype=float),
        np.asarray(mad_values, dtype=float),
    )


def _empty_run_sequence_result():
    keys = [
        'run_mean', 'run_median', 'run_std', 'run_ac_rms', 'run_robust_sigma',
        'run_drift_slope', 'run_drift_span', 'run_drift_ratio_ac', 'run_drift_ratio_robust',
        'run_rolling_mean_range', 'run_rolling_ac_rms_cv', 'run_rolling_mad_cv',
        'run_max_step_jump', 'run_max_step_jump_ratio_ac', 'run_drift_flag',
    ]
    return {
        'metrics': {key: np.nan for key in keys},
        'plot_data': {
            'time_or_index': np.asarray([]),
            'x_for_plot': np.asarray([]),
            'x_axis_label': 'Elapsed time (s)',
            'center_value': np.nan,
            'y_scale': 1.0,
            'y_axis_label': 'Value',
            'rolling_time_for_plot': np.asarray([]),
            'rolling_mean_for_plot': np.asarray([]),
            'rolling_ac_rms_for_plot': np.asarray([]),
        },
    }


def compute_lag_metrics(x, time=None, max_acf_lag=None):
    """Compute lag-plot and autocorrelation diagnostics."""
    x, time = _clean_xy(x, time)
    n = len(x)
    if n < 2:
        return _empty_lag_result()

    lag_1_corr = _lag_corr(x, 1)
    lag_2_corr = _lag_corr(x, 2)

    max_acf_lag = DEFAULT_MAX_ACF_LAG if max_acf_lag is None else int(max_acf_lag)
    max_lag = max(1, min(max_acf_lag, n - 1))
    acf_lags = np.arange(0, max_lag + 1)
    acf_values = _acf_values(x, max_lag)

    first_peak_lag = np.nan
    first_peak_value = np.nan
    for idx in range(1, len(acf_values) - 1):
        if acf_values[idx] > acf_values[idx - 1] and acf_values[idx] >= acf_values[idx + 1]:
            first_peak_lag = int(acf_lags[idx])
            first_peak_value = float(acf_values[idx])
            break

    if np.isnan(first_peak_lag) and len(acf_values) > 1:
        best_idx = int(np.argmax(np.abs(acf_values[1:])) + 1)
        first_peak_lag = int(acf_lags[best_idx])
        first_peak_value = float(acf_values[best_idx])

    if time is not None and len(time) >= 2:
        dt = np.diff(time)
        dt = dt[np.isfinite(dt) & (dt > 0)]
        dt_median = float(np.median(dt)) if dt.size else np.nan
    else:
        dt_median = np.nan
    first_peak_seconds = float(first_peak_lag * dt_median) if np.isfinite(first_peak_lag) and np.isfinite(dt_median) else np.nan

    metrics = {
        'lag_1_corr': lag_1_corr,
        'lag1_corr': lag_1_corr,
        'lag_2_corr': lag_2_corr,
        'acf_first_peak_lag_samples': first_peak_lag,
        'acf_first_peak_lag_samples_diagnostic': first_peak_lag,
        'acf_first_peak_lag_seconds': first_peak_seconds,
        'acf_first_peak_value': first_peak_value,
        'non_random_flag': bool(np.isfinite(lag_1_corr) and abs(lag_1_corr) > 0.2),
    }
    plot_data = {
        'lag_x': x[:-1],
        'lag_y': x[1:],
        'acf_lags': acf_lags,
        'acf_values': acf_values,
    }
    return {'metrics': metrics, 'plot_data': plot_data}


def _lag_corr(x, lag):
    if len(x) <= lag:
        return np.nan
    a = x[:-lag]
    b = x[lag:]
    if np.std(a) == 0 or np.std(b) == 0:
        return np.nan
    return float(np.corrcoef(a, b)[0, 1])


def _acf_values(x, max_lag):
    x_centered = x - np.mean(x)
    denom = np.dot(x_centered, x_centered)
    if denom == 0:
        values = np.full(max_lag + 1, np.nan)
        values[0] = 1.0
        return values
    return np.asarray([
        float(np.dot(x_centered[:len(x_centered) - lag], x_centered[lag:]) / denom)
        if lag > 0 else 1.0
        for lag in range(max_lag + 1)
    ])


def _empty_lag_result():
    return {
        'metrics': {
            'lag_1_corr': np.nan,
            'lag1_corr': np.nan,
            'lag_2_corr': np.nan,
            'acf_first_peak_lag_samples': np.nan,
            'acf_first_peak_lag_samples_diagnostic': np.nan,
            'acf_first_peak_lag_seconds': np.nan,
            'acf_first_peak_value': np.nan,
            'non_random_flag': False,
        },
        'plot_data': {
            'lag_x': np.asarray([]),
            'lag_y': np.asarray([]),
            'acf_lags': np.asarray([]),
            'acf_values': np.asarray([]),
        },
    }


def compute_distribution_metrics(x):
    """Compute histogram/distribution diagnostics."""
    x, _ = _clean_xy(x)
    n = len(x)
    if n == 0:
        return _empty_distribution_result()

    mean_val = float(np.mean(x))
    median_val = float(np.median(x))
    q01, q05, q25, q50, q75, q95, q99 = np.quantile(x, [0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99])
    iqr = float(q75 - q25)
    robust_sigma = _robust_sigma(x)
    x_ac = x - mean_val
    ac_rms = float(np.sqrt(np.mean(x_ac ** 2)))
    crest_factor = float(np.max(np.abs(x_ac)) / ac_rms) if ac_rms > 0 else np.nan
    robust_tail_fraction = (
        float(np.sum(np.abs(x - median_val) > TAIL_SIGMA_MULTIPLIER * robust_sigma) / n)
        if robust_sigma > 0 else 0.0
    )
    strict_global_outlier_rate = (
        float(np.sum(np.abs(x - median_val) > OUTLIER_SIGMA_MULTIPLIER * robust_sigma) / n)
        if robust_sigma > 0 else 0.0
    )
    unique_values, counts = np.unique(x, return_counts=True)
    mode_ratio = float(np.max(counts) / n) if counts.size else np.nan
    hist_counts, hist_bins = np.histogram(x, bins='auto')

    metrics = {
        'dist_min': float(np.min(x)),
        'dist_max': float(np.max(x)),
        'dist_peak_to_peak': float(np.max(x) - np.min(x)),
        'dist_q01': float(q01),
        'dist_q05': float(q05),
        'dist_q25': float(q25),
        'dist_q50': float(q50),
        'dist_q75': float(q75),
        'dist_q95': float(q95),
        'dist_q99': float(q99),
        'dist_iqr': iqr,
        'dist_skewness': float(stats.skew(x, bias=True)) if n >= 3 else np.nan,
        'dist_kurtosis': float(stats.kurtosis(x, fisher=True, bias=True)) if n >= 4 else np.nan,
        'dist_robust_tail_fraction': robust_tail_fraction,
        'dist_strict_global_outlier_rate': strict_global_outlier_rate,
        'dist_crest_factor': crest_factor,
        'dist_mode_ratio': mode_ratio,
        'dist_unique_value_count': int(unique_values.size),
        'distribution_shape_flag': _distribution_shape_flag(
            float(stats.skew(x, bias=True)) if n >= 3 else np.nan,
            float(stats.kurtosis(x, fisher=True, bias=True)) if n >= 4 else np.nan,
        ),
    }
    plot_data = {
        'hist_counts': hist_counts,
        'hist_bins': hist_bins,
        'mean': mean_val,
        'median': median_val,
        'q05': float(q05),
        'q95': float(q95),
    }
    return {'metrics': metrics, 'plot_data': plot_data}


def _empty_distribution_result():
    keys = [
        'dist_min', 'dist_max', 'dist_peak_to_peak', 'dist_q01', 'dist_q05', 'dist_q25',
        'dist_q50', 'dist_q75', 'dist_q95', 'dist_q99', 'dist_iqr', 'dist_skewness',
        'dist_kurtosis', 'dist_robust_tail_fraction', 'dist_strict_global_outlier_rate',
        'dist_crest_factor', 'dist_mode_ratio', 'dist_unique_value_count', 'distribution_shape_flag',
    ]
    return {
        'metrics': {key: np.nan for key in keys},
        'plot_data': {
            'hist_counts': np.asarray([]),
            'hist_bins': np.asarray([]),
            'mean': np.nan,
            'median': np.nan,
            'q05': np.nan,
            'q95': np.nan,
        },
    }


def compute_normal_probability_metrics(x):
    """Compute normal probability / QQ diagnostics."""
    x, _ = _clean_xy(x)
    n = len(x)
    if n < 2:
        return _empty_qq_result()

    if n > MAX_QQ_POINTS:
        sample_idx = np.linspace(0, n - 1, MAX_QQ_POINTS, dtype=int)
        x_for_qq = x[sample_idx]
    else:
        x_for_qq = x
    ordered = np.sort(x_for_qq)
    n = len(ordered)
    probabilities = (np.arange(1, n + 1) - 0.5) / n
    theoretical = stats.norm.ppf(probabilities)
    if np.std(theoretical) == 0 or np.std(ordered) == 0:
        corr = np.nan
        slope = np.nan
        intercept = np.nan
        fit_line = np.full(n, np.nan)
        tail_deviation = np.nan
    else:
        slope, intercept = np.polyfit(theoretical, ordered, 1)
        slope = float(slope)
        intercept = float(intercept)
        fit_line = slope * theoretical + intercept
        corr = float(np.corrcoef(theoretical, ordered)[0, 1])
        tail_mask = (probabilities <= 0.05) | (probabilities >= 0.95)
        residual = np.abs(ordered - fit_line)
        scale = _robust_sigma(ordered)
        if scale > 0 and np.any(tail_mask):
            tail_deviation = float(np.mean(residual[tail_mask]) / scale)
        elif np.any(tail_mask):
            tail_deviation = float(np.mean(residual[tail_mask]))
        else:
            tail_deviation = np.nan

    metrics = {
        'qq_normal_prob_corr': corr,
        'qq_slope': slope,
        'qq_intercept': intercept,
        'qq_tail_deviation': tail_deviation,
    }
    plot_data = {
        'qq_theoretical_quantiles': theoretical,
        'qq_ordered_values': ordered,
        'qq_fit_line': fit_line,
    }
    return {'metrics': metrics, 'plot_data': plot_data}


def _empty_qq_result():
    return {
        'metrics': {
            'qq_normal_prob_corr': np.nan,
            'qq_slope': np.nan,
            'qq_intercept': np.nan,
            'qq_tail_deviation': np.nan,
        },
        'plot_data': {
            'qq_theoretical_quantiles': np.asarray([]),
            'qq_ordered_values': np.asarray([]),
            'qq_fit_line': np.asarray([]),
        },
    }


def _distribution_shape_flag(skewness, kurtosis):
    flags = []
    if np.isfinite(skewness) and abs(skewness) > 1:
        flags.append('SKEWED')
    if np.isfinite(kurtosis) and abs(kurtosis) > 3:
        flags.append('HEAVY_OR_LIGHT_TAIL')
    return '|'.join(flags) if flags else 'OK'


def compute_nist_diagnostics(x, time=None, params=None):
    """Compute all NIST 4-plot diagnostics and return flat metrics plus plot data."""
    params = params or {}
    run = compute_run_sequence_metrics(
        x,
        time=time,
        window_seconds=params.get('window_seconds'),
        centered_plot=bool(params.get('centered_plot')),
        millivolt_centered_plot=bool(params.get('millivolt_centered_plot')),
    )
    lag = compute_lag_metrics(
        x,
        time=time,
        max_acf_lag=params.get('max_acf_lag'),
    )
    distribution = compute_distribution_metrics(x)
    qq = compute_normal_probability_metrics(x)

    metrics = {}
    for part in (run, lag, distribution, qq):
        metrics.update(part['metrics'])

    plot_data = {
        'run_sequence': run['plot_data'],
        'lag': lag['plot_data'],
        'histogram': distribution['plot_data'],
        'normal_probability': qq['plot_data'],
    }
    return {'metrics': metrics, 'plot_data': plot_data}


def compute_group_nist_diagnostics(file_channel_series_list, time_list=None, params=None):
    """Compute NIST diagnostics for one group/channel across multiple files.

    Run sequence, histogram, and QQ diagnostics use the concatenated samples.
    Lag pairs and ACF are computed within each file and then merged, so file
    boundaries do not create artificial lag relationships.
    """
    params = params or {}
    clean_series, clean_times = _prepare_group_series(file_channel_series_list, time_list)
    if not clean_series:
        return compute_nist_diagnostics([], None, params=params)

    stitched_x, stitched_time, file_boundaries = _stitch_group_series(clean_series, clean_times)
    run = compute_run_sequence_metrics(
        stitched_x,
        time=stitched_time,
        window_seconds=params.get('window_seconds'),
        centered_plot=bool(params.get('centered_plot')),
        millivolt_centered_plot=bool(params.get('millivolt_centered_plot')),
    )
    run['plot_data']['file_boundaries'] = file_boundaries
    run['plot_data']['x_axis_label'] = 'Elapsed time across group (s)'

    lag = compute_group_lag_metrics(
        clean_series,
        clean_times,
        max_acf_lag=params.get('max_acf_lag'),
    )
    distribution = compute_distribution_metrics(stitched_x)
    qq = compute_normal_probability_metrics(stitched_x)

    metrics = {}
    for part in (run, lag, distribution, qq):
        metrics.update(part['metrics'])

    plot_data = {
        'run_sequence': run['plot_data'],
        'lag': lag['plot_data'],
        'histogram': distribution['plot_data'],
        'normal_probability': qq['plot_data'],
    }
    return {'metrics': metrics, 'plot_data': plot_data}


def compute_group_lag_metrics(clean_series, clean_times=None, max_acf_lag=None):
    """Compute lag diagnostics across files without crossing file boundaries."""
    clean_times = clean_times or [None] * len(clean_series)
    valid_series = [np.asarray(series, dtype=float) for series in clean_series if len(series) >= 2]
    if not valid_series:
        return _empty_lag_result()

    lag_x_parts = []
    lag_y_parts = []
    lag2_x_parts = []
    lag2_y_parts = []
    for series in valid_series:
        lag_x_parts.append(series[:-1])
        lag_y_parts.append(series[1:])
        if len(series) > 2:
            lag2_x_parts.append(series[:-2])
            lag2_y_parts.append(series[2:])

    lag_x = np.concatenate(lag_x_parts) if lag_x_parts else np.asarray([])
    lag_y = np.concatenate(lag_y_parts) if lag_y_parts else np.asarray([])
    lag2_x = np.concatenate(lag2_x_parts) if lag2_x_parts else np.asarray([])
    lag2_y = np.concatenate(lag2_y_parts) if lag2_y_parts else np.asarray([])

    lag_1_corr = _paired_corr(lag_x, lag_y)
    lag_2_corr = _paired_corr(lag2_x, lag2_y)

    max_acf_lag = DEFAULT_MAX_ACF_LAG if max_acf_lag is None else int(max_acf_lag)
    max_lag = max(1, min(max_acf_lag, max(len(series) for series in valid_series) - 1))
    acf_lags = np.arange(0, max_lag + 1)
    acf_matrix = []
    for series in valid_series:
        file_max_lag = min(max_lag, len(series) - 1)
        values = np.full(max_lag + 1, np.nan)
        values[:file_max_lag + 1] = _acf_values(series, file_max_lag)
        acf_matrix.append(values)
    acf_values = np.nanmean(np.vstack(acf_matrix), axis=0) if acf_matrix else np.full(max_lag + 1, np.nan)

    first_peak_lag = np.nan
    first_peak_value = np.nan
    for idx in range(1, len(acf_values) - 1):
        if acf_values[idx] > acf_values[idx - 1] and acf_values[idx] >= acf_values[idx + 1]:
            first_peak_lag = int(acf_lags[idx])
            first_peak_value = float(acf_values[idx])
            break
    if np.isnan(first_peak_lag) and len(acf_values) > 1:
        finite = np.where(np.isfinite(acf_values[1:]), np.abs(acf_values[1:]), -np.inf)
        if np.any(finite > -np.inf):
            best_idx = int(np.argmax(finite) + 1)
            first_peak_lag = int(acf_lags[best_idx])
            first_peak_value = float(acf_values[best_idx])

    dt_median = _group_dt_median(clean_times)
    first_peak_seconds = float(first_peak_lag * dt_median) if np.isfinite(first_peak_lag) and np.isfinite(dt_median) else np.nan

    return {
        'metrics': {
            'lag_1_corr': lag_1_corr,
            'lag_2_corr': lag_2_corr,
            'acf_first_peak_lag_samples': first_peak_lag,
            'acf_first_peak_lag_seconds': first_peak_seconds,
            'acf_first_peak_value': first_peak_value,
        },
        'plot_data': {
            'lag_x': lag_x,
            'lag_y': lag_y,
            'acf_lags': acf_lags,
            'acf_values': acf_values,
        },
    }


def _prepare_group_series(file_channel_series_list, time_list=None):
    time_list = time_list or [None] * len(file_channel_series_list)
    clean_series = []
    clean_times = []
    for series, time in zip(file_channel_series_list, time_list):
        x_clean, t_clean = _clean_xy(series, time)
        if x_clean.size:
            clean_series.append(x_clean)
            clean_times.append(t_clean)
    return clean_series, clean_times


def _stitch_group_series(clean_series, clean_times):
    stitched_x_parts = []
    stitched_time_parts = []
    file_boundaries = []
    offset = 0.0

    for idx, x in enumerate(clean_series):
        time = clean_times[idx] if idx < len(clean_times) else None
        duration, axis = _duration_and_time_axis(x, time)
        axis = axis - axis[0] + offset if len(axis) else axis
        stitched_x_parts.append(x)
        stitched_time_parts.append(axis)

        if len(axis) >= 2:
            dt = np.diff(axis)
            dt = dt[np.isfinite(dt) & (dt > 0)]
            step = float(np.median(dt)) if dt.size else FILE_DURATION / max(len(x), 1)
            next_offset = float(axis[-1] + step)
        else:
            step = FILE_DURATION / max(len(x), 1)
            next_offset = offset + max(duration, step)

        if idx < len(clean_series) - 1:
            file_boundaries.append(next_offset)
        offset = next_offset

    return (
        np.concatenate(stitched_x_parts) if stitched_x_parts else np.asarray([]),
        np.concatenate(stitched_time_parts) if stitched_time_parts else np.asarray([]),
        np.asarray(file_boundaries, dtype=float),
    )


def _paired_corr(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    n = min(len(a), len(b))
    if n < 2:
        return np.nan
    a = a[:n]
    b = b[:n]
    if np.std(a) == 0 or np.std(b) == 0:
        return np.nan
    return float(np.corrcoef(a, b)[0, 1])


def _group_dt_median(clean_times):
    dt_parts = []
    for time in clean_times:
        if time is None or len(time) < 2:
            continue
        dt = np.diff(time)
        dt = dt[np.isfinite(dt) & (dt > 0)]
        if dt.size:
            dt_parts.append(dt)
    if not dt_parts:
        return np.nan
    return float(np.median(np.concatenate(dt_parts)))
