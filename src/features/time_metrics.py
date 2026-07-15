import numpy as np
import pandas as pd

from src.core.constants import (
    FILE_DURATION,
    ISOLATED_SPIKE_MAX_RUN_LENGTH,
    OUTLIER_SIGMA_MULTIPLIER,
    TAIL_SIGMA_MULTIPLIER,
)


METRIC_NAMES = [
    'sample_count',
    'duration_seconds',
    'duration_s',
    'dt_median',
    'dt_std',
    'fs_hz',
    'mean',
    'mean_v',
    'median',
    'min',
    'max',
    'peak_to_peak',
    'p2p_v',
    'std',
    'std_v',
    'ac_rms',
    'rms_v',
    'robust_sigma',
    'q05',
    'q50',
    'q95',
    'crest_factor',
    'drift_slope',
    'drift_span',
    'drift_span_v',
    'drift_ratio_robust',
    'drift_ratio_to_robust_sigma',
    'drift_ratio_ac',
    'drift_ratio_to_std',
    'strict_global_outlier_rate',
    'candidate_isolated_spike_rate',
    'candidate_cluster_spike_rate',
    'robust_tail_fraction',
    'repeated_extreme_rate',
    'clipping_rate',
    'repeated_extreme_count',
    'duplicate_rate',
    'unique_value_count',
    'adc_min_hit_count',
    'adc_max_hit_count',
    'quantization_step_estimate',
    'qc_flag',
]


def calculate_file_metrics(values, time_values=None, duration=FILE_DURATION):
    """Calculate per-file baseline, noise, drift, and outlier metrics."""
    x_all = np.asarray(values, dtype=float)

    if time_values is not None:
        t_all = pd.to_numeric(pd.Series(time_values), errors='coerce').to_numpy(dtype=float)
        valid_mask = np.isfinite(x_all) & np.isfinite(t_all)
        x = x_all[valid_mask]
        t = t_all[valid_mask]
        if x.size < 2:
            x = x_all[np.isfinite(x_all)]
            t = None
    else:
        x = x_all[np.isfinite(x_all)]
        t = None

    n_total = x.size
    if n_total == 0:
        return None

    sample_count = int(n_total)
    dt_median = np.nan
    dt_std = np.nan
    if t is not None and n_total >= 2:
        t = t - t[0]
        dt = np.diff(t)
        dt = dt[np.isfinite(dt) & (dt > 0)]
        if dt.size:
            dt_median = float(np.median(dt))
            dt_std = float(np.std(dt))
        duration_seconds = float(t[-1] - t[0])
        fit_time = t
    else:
        duration_seconds = float(duration)
        fit_time = np.linspace(0.0, duration_seconds, n_total, endpoint=False)

    mean_val = float(np.mean(x))
    median_val = float(np.median(x))
    min_val = float(np.min(x))
    max_val = float(np.max(x))
    peak_to_peak = max_val - min_val
    q05, q50, q95 = np.quantile(x, [0.05, 0.50, 0.95])

    x_ac = x - mean_val
    std_val = float(np.std(x))
    ac_rms = float(np.sqrt(np.mean(x_ac ** 2)))
    mad = float(np.median(np.abs(x - median_val)))
    robust_sigma = float(1.4826 * mad)

    if ac_rms > 0:
        crest_factor = float(np.max(np.abs(x_ac)) / ac_rms)
    else:
        crest_factor = np.nan

    if n_total >= 2 and duration_seconds > 0:
        slope, _ = np.polyfit(fit_time, x, 1)
        slope = float(slope)
    else:
        slope = np.nan

    if np.isfinite(slope):
        drift_span = float(abs(slope) * duration_seconds)
    else:
        drift_span = np.nan

    if robust_sigma > 0 and np.isfinite(drift_span):
        drift_ratio_robust = float(drift_span / robust_sigma)
    else:
        drift_ratio_robust = np.nan

    if ac_rms > 0 and np.isfinite(drift_span):
        drift_ratio_ac = float(drift_span / ac_rms)
    else:
        drift_ratio_ac = np.nan

    if robust_sigma > 0:
        centered_abs = np.abs(x - median_val)
        robust_tail_mask = centered_abs > (TAIL_SIGMA_MULTIPLIER * robust_sigma)
        outlier_mask = centered_abs > (OUTLIER_SIGMA_MULTIPLIER * robust_sigma)
        strict_global_outlier_rate = float(np.sum(outlier_mask) / n_total)
        robust_tail_fraction = float(np.sum(robust_tail_mask) / n_total)
    else:
        strict_global_outlier_rate = 0.0
        robust_tail_fraction = 0.0
        outlier_mask = np.zeros(n_total, dtype=bool)

    isolated_spike_count, cluster_spike_count = count_spike_runs(outlier_mask)
    candidate_isolated_spike_rate = float(isolated_spike_count / n_total)
    candidate_cluster_spike_rate = float(cluster_spike_count / n_total)

    max_repeat_count = int(np.sum(x == max_val))
    min_repeat_count = int(np.sum(x == min_val))
    repeated_extreme_count = max_repeat_count + min_repeat_count
    clipping_sample_count = max(0, max_repeat_count - 1) + max(0, min_repeat_count - 1)
    repeated_extreme_rate = float(clipping_sample_count / n_total)
    unique_values, unique_counts = np.unique(x, return_counts=True)
    unique_value_count = int(unique_values.size)
    duplicate_rate = float(1.0 - unique_value_count / n_total) if n_total else np.nan
    quantization_step = _estimate_quantization_step(unique_values)
    fs_hz = float(1.0 / dt_median) if dt_median and np.isfinite(dt_median) and dt_median > 0 else np.nan
    drift_ratio_to_std = float(drift_span / std_val) if std_val > 0 and np.isfinite(drift_span) else np.nan
    qc_flag = _file_qc_flag(
        repeated_extreme_rate=repeated_extreme_rate,
        duplicate_rate=duplicate_rate,
        quantization_step=quantization_step,
        robust_sigma=robust_sigma,
        drift_ratio_to_robust=drift_ratio_robust,
    )

    return {
        'sample_count': sample_count,
        'duration_seconds': duration_seconds,
        'duration_s': duration_seconds,
        'dt_median': dt_median,
        'dt_std': dt_std,
        'fs_hz': fs_hz,
        'mean': mean_val,
        'mean_v': mean_val,
        'median': median_val,
        'min': min_val,
        'max': max_val,
        'peak_to_peak': peak_to_peak,
        'p2p_v': peak_to_peak,
        'std': std_val,
        'std_v': std_val,
        'ac_rms': ac_rms,
        'rms_v': ac_rms,
        'robust_sigma': robust_sigma,
        'q05': float(q05),
        'q50': float(q50),
        'q95': float(q95),
        'crest_factor': crest_factor,
        'drift_slope': slope,
        'drift_span': drift_span,
        'drift_span_v': drift_span,
        'drift_ratio_robust': drift_ratio_robust,
        'drift_ratio_to_robust_sigma': drift_ratio_robust,
        'drift_ratio_ac': drift_ratio_ac,
        'drift_ratio_to_std': drift_ratio_to_std,
        'strict_global_outlier_rate': strict_global_outlier_rate,
        'candidate_isolated_spike_rate': candidate_isolated_spike_rate,
        'candidate_cluster_spike_rate': candidate_cluster_spike_rate,
        'robust_tail_fraction': robust_tail_fraction,
        'repeated_extreme_rate': repeated_extreme_rate,
        'clipping_rate': repeated_extreme_rate,
        'repeated_extreme_count': repeated_extreme_count,
        'duplicate_rate': duplicate_rate,
        'unique_value_count': unique_value_count,
        'adc_min_hit_count': int(min_repeat_count),
        'adc_max_hit_count': int(max_repeat_count),
        'quantization_step_estimate': quantization_step,
        'qc_flag': qc_flag,
    }


def _estimate_quantization_step(unique_values):
    unique_values = np.asarray(unique_values, dtype=float)
    if unique_values.size < 2:
        return np.nan
    diffs = np.diff(np.sort(unique_values))
    diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
    if diffs.size == 0:
        return np.nan
    return float(np.percentile(diffs, 10))


def _file_qc_flag(repeated_extreme_rate, duplicate_rate, quantization_step, robust_sigma, drift_ratio_to_robust):
    flags = []
    if repeated_extreme_rate > 0.001:
        flags.append('POSSIBLE_CLIPPING')
    if duplicate_rate > 0.95 and np.isfinite(quantization_step):
        flags.append('POSSIBLE_QUANTIZATION')
    if drift_ratio_to_robust and np.isfinite(drift_ratio_to_robust) and drift_ratio_to_robust > 1:
        flags.append('HIGH_DRIFT')
    if robust_sigma and np.isfinite(robust_sigma) and robust_sigma <= 0:
        flags.append('CHECK_CHANNEL')
    return '|'.join(flags) if flags else 'OK'


def count_spike_runs(mask):
    """Split strict outlier samples into isolated and clustered spike samples."""
    isolated_count = 0
    cluster_count = 0
    run_length = 0

    for is_spike in mask:
        if is_spike:
            run_length += 1
            continue

        if run_length:
            if run_length <= ISOLATED_SPIKE_MAX_RUN_LENGTH:
                isolated_count += run_length
            else:
                cluster_count += run_length
            run_length = 0

    if run_length:
        if run_length <= ISOLATED_SPIKE_MAX_RUN_LENGTH:
            isolated_count += run_length
        else:
            cluster_count += run_length

    return isolated_count, cluster_count


def finite_values(rows, metric_name):
    """Return finite metric values from row dictionaries."""
    values = []
    for row in rows:
        value = row.get(metric_name)
        if pd.notna(value) and np.isfinite(value):
            values.append(float(value))
    return np.asarray(values, dtype=float)


def clean_metric_value(value):
    """Convert numpy scalars and non-finite floats into plain Python values."""
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    return value
