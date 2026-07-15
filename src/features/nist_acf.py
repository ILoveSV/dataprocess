import numpy as np
from scipy import signal
from scipy.fft import irfft, next_fast_len, rfft


DEFAULT_ACF_MAX_SECONDS = 0.2
DEFAULT_ACF_THRESHOLD = 1 / np.e
DEFAULT_NEAR_ZERO_EXCLUDE_SECONDS = 5e-6
DEFAULT_MIN_PEAK_DISTANCE_SECONDS = 1e-3
DEFAULT_MIN_PEAK_PROMINENCE = 0.01
DEFAULT_STRONG_PEAK_HEIGHT = 0.3
DEFAULT_STRONG_PEAK_PROMINENCE = 0.2


def compute_group_acf_diagnostics(
    file_channel_series_list,
    time_list=None,
    max_acf_lag=None,
    max_acf_seconds=None,
    threshold=None,
    psd_candidate_freq_hz=None,
    psd_candidate_freqs_hz=None,
    min_peak_distance_s=None,
    min_peak_prominence=None,
    near_zero_exclude_s=None,
    strong_peak_height=None,
    strong_peak_prominence=None,
):
    """Compute per-file ACF, then summarize one group/channel.

    Each file is AC-centered with x_ac = x - median(x). ACF pairs never cross
    file boundaries because each file is processed independently before the
    group mean/median/p10/p90 summaries are computed.
    """
    clean_series, clean_times, dt = _clean_group_series(file_channel_series_list, time_list)
    if not clean_series or not np.isfinite(dt) or dt <= 0:
        return _empty_acf_result()

    fs = float(1.0 / dt)
    if max_acf_lag is None:
        max_seconds = DEFAULT_ACF_MAX_SECONDS if max_acf_seconds is None else float(max_acf_seconds)
        max_lag = int(round(max_seconds / dt))
    else:
        max_lag = int(max_acf_lag)
    max_lag = max(1, min(max_lag, max(len(series) for series in clean_series) - 1))

    acf_rows = []
    skipped = 0
    for series in clean_series:
        file_max_lag = min(max_lag, len(series) - 1)
        values = np.full(max_lag + 1, np.nan)
        values[:file_max_lag + 1] = _acf_fft_limited(series, file_max_lag)
        if np.isfinite(values[0]):
            acf_rows.append(values)
        else:
            skipped += 1
    if not acf_rows:
        return _empty_acf_result()

    acf_matrix = np.vstack(acf_rows)
    mean_acf = np.nanmean(acf_matrix, axis=0)
    median_acf = np.nanmedian(acf_matrix, axis=0)
    p10_acf = np.nanpercentile(acf_matrix, 10, axis=0)
    p90_acf = np.nanpercentile(acf_matrix, 90, axis=0)
    std_acf = np.nanstd(acf_matrix, axis=0)
    lags = np.arange(max_lag + 1)
    lag_seconds = lags * dt

    threshold = DEFAULT_ACF_THRESHOLD if threshold is None else float(threshold)
    first_zero = _first_zero_crossing(lag_seconds, mean_acf)
    first_below = _first_below_threshold(lag_seconds, mean_acf, threshold)
    first_peak_lag_s, first_peak_value = _first_local_peak(lag_seconds, mean_acf)

    near_zero_exclude_s = DEFAULT_NEAR_ZERO_EXCLUDE_SECONDS if near_zero_exclude_s is None else max(float(near_zero_exclude_s), 2.0 / fs)
    min_peak_distance_s = DEFAULT_MIN_PEAK_DISTANCE_SECONDS if min_peak_distance_s is None else float(min_peak_distance_s)
    min_peak_prominence = DEFAULT_MIN_PEAK_PROMINENCE if min_peak_prominence is None else float(min_peak_prominence)
    strong_peak_height = DEFAULT_STRONG_PEAK_HEIGHT if strong_peak_height is None else float(strong_peak_height)
    strong_peak_prominence = DEFAULT_STRONG_PEAK_PROMINENCE if strong_peak_prominence is None else float(strong_peak_prominence)
    peak_table = _acf_peak_table(
        lag_seconds,
        mean_acf,
        min_lag_s=near_zero_exclude_s,
        min_peak_distance_s=min_peak_distance_s,
        min_peak_prominence=min_peak_prominence,
    )
    first_strong = _first_strong_peak(peak_table, strong_peak_height, strong_peak_prominence)
    global_max = _global_max_peak(peak_table)
    peak_spacing = _peak_spacing_period(peak_table, strong_peak_height, strong_peak_prominence)
    conflict_flag, conflict_reason = _period_conflict(first_strong.get('lag_s', np.nan), peak_spacing)

    psd_period = float(1.0 / psd_candidate_freq_hz) if psd_candidate_freq_hz and psd_candidate_freq_hz > 0 else np.nan
    acf_value_at_psd_period = _interp_at(lag_seconds, mean_acf, psd_period)
    psd_matches = _match_psd_peaks_to_acf(psd_candidate_freqs_hz or ([psd_candidate_freq_hz] if psd_candidate_freq_hz else []), peak_table, lag_seconds, mean_acf)
    primary_match = psd_matches[0] if psd_matches else {}
    decay_time = _first_below_threshold(lag_seconds, np.abs(mean_acf), threshold)

    return {
        'metrics': {
            'acf_fs': fs,
            'acf_dt': float(dt),
            'acf_max_lag_s': float(lag_seconds[-1]) if len(lag_seconds) else np.nan,
            'acf_file_count_used': int(acf_matrix.shape[0]),
            'acf_file_count_skipped': int(skipped),
            'acf_zero_cross_s': first_zero,
            'acf_first_below_threshold_s': first_below,
            'acf_first_local_peak_lag_s': first_peak_lag_s,
            'acf_first_local_peak_value': first_peak_value,
            'acf_first_strong_peak_lag_s': first_strong.get('lag_s', np.nan),
            'acf_first_strong_peak_freq_hz': _freq_from_lag(first_strong.get('lag_s', np.nan)),
            'acf_first_strong_peak_height': first_strong.get('height', np.nan),
            'acf_first_strong_peak_prominence': first_strong.get('prominence', np.nan),
            'acf_global_max_peak_lag_s': global_max.get('lag_s', np.nan),
            'acf_global_max_peak_freq_hz': _freq_from_lag(global_max.get('lag_s', np.nan)),
            'acf_global_max_peak_height': global_max.get('height', np.nan),
            'acf_global_max_peak_prominence': global_max.get('prominence', np.nan),
            'acf_peak_spacing_period_s': peak_spacing,
            'acf_peak_spacing_freq_hz': _freq_from_lag(peak_spacing),
            'acf_period_conflict_flag': conflict_flag,
            'acf_period_conflict_reason': conflict_reason,
            'acf_primary_period_s': _primary_period(first_strong.get('lag_s', np.nan), global_max.get('lag_s', np.nan), peak_spacing),
            'acf_decay_time_s': decay_time,
            'acf_peak_lag_s': _json_list([peak['lag_s'] for peak in peak_table]),
            'acf_peak_freq_hz': _json_list([peak['freq_hz'] for peak in peak_table]),
            'acf_peak_height': _json_list([peak['height'] for peak in peak_table]),
            'acf_peak_prominence': _json_list([peak['prominence'] for peak in peak_table]),
            'acf_value_at_psd_period': acf_value_at_psd_period,
            'acf_psd_matches': _json_records(psd_matches),
            'acf_psd_period_error_s': primary_match.get('error_s', np.nan),
            'acf_psd_period_error_percent': primary_match.get('error_percent', np.nan),
            'acf_psd_candidate_freq_hz': float(psd_candidate_freq_hz) if psd_candidate_freq_hz else np.nan,
            'acf_psd_candidate_period_s': psd_period,
            'acf_psd_peak_may_be_harmonic': primary_match.get('may_be_harmonic', ''),
        },
        'plot_data': {
            'acf_lags': lags,
            'acf_lag_seconds': lag_seconds,
            'acf_mean': mean_acf,
            'acf_median': median_acf,
            'acf_p10': p10_acf,
            'acf_p90': p90_acf,
            'acf_std': std_acf,
            'acf_threshold': threshold,
            'acf_peak_threshold': strong_peak_height,
            'psd_candidate_period_s': psd_period,
            'psd_peak_periods_s': [match['psd_peak_period_s'] for match in psd_matches],
            'acf_file_count': int(acf_matrix.shape[0]),
        },
    }


def _clean_group_series(series_list, time_list=None):
    time_list = time_list or [None] * len(series_list)
    clean_series = []
    clean_times = []
    dt_parts = []
    for series, time in zip(series_list, time_list):
        x = np.asarray(series, dtype=float)
        if time is None:
            valid = np.isfinite(x)
            t = None
        else:
            t = np.asarray(time, dtype=float)
            valid = np.isfinite(x) & np.isfinite(t)
            t = t[valid]
            if t.size:
                t = t - t[0]
            if len(t) >= 2:
                dt = np.diff(t)
                dt = dt[np.isfinite(dt) & (dt > 0)]
                if dt.size:
                    dt_parts.append(dt)
        x = x[valid]
        if x.size >= 2:
            clean_series.append(x)
            clean_times.append(t)
    dt_median = float(np.median(np.concatenate(dt_parts))) if dt_parts else np.nan
    return clean_series, clean_times, dt_median


def _acf_fft_limited(x, max_lag):
    x = np.asarray(x, dtype=float)
    x_ac = x - np.median(x)
    x_ac = x_ac - np.mean(x_ac)
    if not np.any(np.isfinite(x_ac)):
        return np.full(max_lag + 1, np.nan)
    denom = np.dot(x_ac, x_ac)
    if denom <= 0 or not np.isfinite(denom):
        values = np.full(max_lag + 1, np.nan)
        values[0] = 1.0
        return values
    fft_len = next_fast_len(2 * len(x_ac) - 1)
    spectrum = rfft(x_ac, fft_len)
    corr = irfft(spectrum * np.conj(spectrum), fft_len)[:max_lag + 1]
    acf = corr / denom
    return np.asarray(acf, dtype=float)


def _first_zero_crossing(lag_seconds, acf):
    values = np.asarray(acf, dtype=float)
    for idx in range(1, len(values)):
        if np.isfinite(values[idx]) and values[idx] <= 0:
            return float(lag_seconds[idx])
    return np.nan


def _first_below_threshold(lag_seconds, acf, threshold):
    values = np.asarray(acf, dtype=float)
    mask = np.isfinite(values[1:]) & (np.abs(values[1:]) <= threshold)
    if not np.any(mask):
        return np.nan
    return float(lag_seconds[int(np.argmax(mask) + 1)])


def _first_local_peak(lag_seconds, acf):
    peaks, _ = signal.find_peaks(acf)
    if peaks.size == 0:
        return np.nan, np.nan
    idx = int(peaks[0])
    return float(lag_seconds[idx]), float(acf[idx])


def _acf_peak_table(lag_seconds, acf, min_lag_s, min_peak_distance_s, min_peak_prominence):
    dt = float(np.median(np.diff(lag_seconds))) if len(lag_seconds) >= 2 else np.nan
    if not np.isfinite(dt) or dt <= 0:
        return []
    min_distance = max(1, int(round(min_peak_distance_s / dt)))
    peaks, props = signal.find_peaks(acf, distance=min_distance, prominence=min_peak_prominence)
    prominences = props.get('prominences', signal.peak_prominences(acf, peaks)[0] if peaks.size else [])
    output = []
    for peak, prominence in zip(peaks, prominences):
        lag = float(lag_seconds[peak])
        if lag <= min_lag_s or acf[peak] <= 0:
            continue
        output.append({
            'lag_s': lag,
            'freq_hz': _freq_from_lag(lag),
            'height': float(acf[peak]),
            'prominence': float(prominence),
        })
    return output


def _first_strong_peak(peak_table, min_height, min_prominence):
    for peak in peak_table:
        if peak['height'] > min_height or peak['prominence'] > min_prominence:
            return peak
    return {}


def _global_max_peak(peak_table):
    if not peak_table:
        return {}
    return max(peak_table, key=lambda peak: peak['height'])


def _peak_spacing_period(peak_table, min_height, min_prominence):
    strong_lags = [
        peak['lag_s']
        for peak in peak_table
        if peak['height'] > min_height or peak['prominence'] > min_prominence
    ]
    if len(strong_lags) < 2:
        return np.nan
    return float(np.median(np.diff(strong_lags)))


def _interp_at(x, y, position):
    if not np.isfinite(position) or position < 0 or len(x) == 0:
        return np.nan
    if position > x[-1]:
        return np.nan
    return float(np.interp(position, x, y))


def _peak_near_period(lag_seconds, acf, period):
    if not np.isfinite(period) or period <= 0 or len(lag_seconds) == 0:
        return np.nan, np.nan
    window = max(0.05 * period, 2 * np.median(np.diff(lag_seconds)))
    mask = (lag_seconds >= period - window) & (lag_seconds <= period + window)
    if not np.any(mask):
        return np.nan, np.nan
    idxs = np.where(mask)[0]
    peaks, _ = signal.find_peaks(acf[idxs])
    if peaks.size:
        local = idxs[peaks]
        best = int(local[int(np.argmax(acf[local]))])
    else:
        best = int(idxs[int(np.argmax(acf[idxs]))])
    return float(lag_seconds[best]), float(acf[best])


def _match_psd_peaks_to_acf(psd_freqs, peak_table, lag_seconds, acf):
    matches = []
    peaks = peak_table or []
    for freq in psd_freqs:
        if freq is None or not np.isfinite(freq) or freq <= 0:
            continue
        period = float(1.0 / freq)
        max_multiple = int(np.floor(lag_seconds[-1] / period)) if len(lag_seconds) and period > 0 else 0
        best = None
        for peak in peaks:
            k = max(1, int(round(peak['lag_s'] / period)))
            if k > max_multiple:
                continue
            matched_lag = k * period
            error_s = peak['lag_s'] - matched_lag
            error_percent = abs(error_s) / matched_lag * 100.0 if matched_lag > 0 else np.nan
            candidate = {
                'psd_peak_freq_hz': float(freq),
                'psd_peak_period_s': period,
                'nearest_acf_peak_lag_s': peak['lag_s'],
                'nearest_multiple_k': int(k),
                'matched_lag_s': matched_lag,
                'acf_value_at_matched_lag': _interp_at(lag_seconds, acf, matched_lag),
                'error_s': float(error_s),
                'error_percent': float(error_percent),
                'may_be_harmonic': 'PSD peak may be harmonic / ACF dominant at multiple of PSD period' if k >= 2 else '',
            }
            if best is None or candidate['error_percent'] < best['error_percent']:
                best = candidate
        if best is None:
            matched_lag = period
            best = {
                'psd_peak_freq_hz': float(freq),
                'psd_peak_period_s': period,
                'nearest_acf_peak_lag_s': np.nan,
                'nearest_multiple_k': np.nan,
                'matched_lag_s': matched_lag,
                'acf_value_at_matched_lag': _interp_at(lag_seconds, acf, matched_lag),
                'error_s': np.nan,
                'error_percent': np.nan,
                'may_be_harmonic': '',
            }
        matches.append(best)
    return matches


def _freq_from_lag(lag):
    return float(1.0 / lag) if np.isfinite(lag) and lag > 0 else np.nan


def _primary_period(first_strong, global_max, spacing):
    for value in (first_strong, global_max, spacing):
        if np.isfinite(value) and value > 0:
            return float(value)
    return np.nan


def _period_conflict(first_strong, spacing):
    if not (np.isfinite(first_strong) and first_strong > 0 and np.isfinite(spacing) and spacing > 0):
        return False, ''
    rel = abs(first_strong - spacing) / spacing
    if rel > 0.10:
        return True, f'first_strong differs from peak_spacing by {rel:.3g}'
    return False, ''


def _json_list(values):
    import json
    return json.dumps([float(value) if np.isfinite(value) else None for value in values], ensure_ascii=False)


def _json_records(records):
    import json
    def clean(value):
        if isinstance(value, (float, np.floating)):
            return float(value) if np.isfinite(value) else None
        if isinstance(value, (int, np.integer)):
            return int(value)
        return value
    return json.dumps([{key: clean(value) for key, value in record.items()} for record in records], ensure_ascii=False)


def _empty_acf_result():
    return {
        'metrics': {
            'acf_fs': np.nan,
            'acf_dt': np.nan,
            'acf_max_lag_s': np.nan,
            'acf_file_count_used': 0,
            'acf_file_count_skipped': np.nan,
            'acf_zero_cross_s': np.nan,
            'acf_first_below_threshold_s': np.nan,
            'acf_first_local_peak_lag_s': np.nan,
            'acf_first_local_peak_value': np.nan,
            'acf_first_strong_peak_lag_s': np.nan,
            'acf_first_strong_peak_freq_hz': np.nan,
            'acf_first_strong_peak_height': np.nan,
            'acf_first_strong_peak_prominence': np.nan,
            'acf_global_max_peak_lag_s': np.nan,
            'acf_global_max_peak_freq_hz': np.nan,
            'acf_global_max_peak_height': np.nan,
            'acf_global_max_peak_prominence': np.nan,
            'acf_peak_spacing_period_s': np.nan,
            'acf_peak_spacing_freq_hz': np.nan,
            'acf_period_conflict_flag': False,
            'acf_period_conflict_reason': '',
            'acf_primary_period_s': np.nan,
            'acf_decay_time_s': np.nan,
            'acf_peak_lag_s': '[]',
            'acf_peak_freq_hz': '[]',
            'acf_peak_height': '[]',
            'acf_peak_prominence': '[]',
            'acf_value_at_psd_period': np.nan,
            'acf_psd_matches': '[]',
            'acf_psd_period_error_s': np.nan,
            'acf_psd_period_error_percent': np.nan,
            'acf_psd_candidate_freq_hz': np.nan,
            'acf_psd_candidate_period_s': np.nan,
            'acf_psd_peak_may_be_harmonic': '',
        },
        'plot_data': {
            'acf_lags': np.asarray([]),
            'acf_lag_seconds': np.asarray([]),
            'acf_mean': np.asarray([]),
            'acf_median': np.asarray([]),
            'acf_p10': np.asarray([]),
            'acf_p90': np.asarray([]),
            'acf_std': np.asarray([]),
            'acf_threshold': DEFAULT_ACF_THRESHOLD,
            'acf_peak_threshold': DEFAULT_STRONG_PEAK_HEIGHT,
            'psd_candidate_period_s': np.nan,
            'psd_peak_periods_s': [],
            'acf_file_count': 0,
        },
    }
