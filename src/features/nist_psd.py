import json

import numpy as np
from scipy import signal


DEFAULT_WELCH_NPERSEG = 16384
DEFAULT_LOW_FREQ_NPERSEG = 524288
DEFAULT_TOP_PEAK_COUNT = 5
DEFAULT_EXCLUDE_LOW_HZ = 1000.0
DEFAULT_BANDS = (
    ('0_5Hz', 0.0, 5.0),
    ('0_20Hz', 0.0, 20.0),
    ('0_100Hz', 0.0, 100.0),
    ('0_50Hz', 0.0, 50.0),
    ('50_100Hz', 50.0, 100.0),
    ('100_1000Hz', 100.0, 1000.0),
    ('1k_10kHz', 1000.0, 10000.0),
    ('10k_50kHz', 10000.0, 50000.0),
    ('50k_200kHz', 50000.0, 200000.0),
)
DOMINANT_BANDS = (
    ('0_100Hz', 0.0, 100.0),
    ('100_1000Hz', 100.0, 1000.0),
    ('1k_10kHz', 1000.0, 10000.0),
    ('10k_200kHz', 10000.0, 200000.0),
)


def compute_group_welch_psd(file_channel_series_list, time_list=None, params=None):
    """Compute per-file Welch PSD, then summarize one group/channel.

    Each file is AC-centered with x_ac = x - median(x) before Welch. PSDs are
    averaged across files only after each file-channel PSD has been computed.
    """
    params = params or {}
    clean_series, dt_median = _clean_series_and_dt(file_channel_series_list, time_list)
    if not clean_series or not np.isfinite(dt_median) or dt_median <= 0:
        return _empty_psd_result()

    fs = float(1.0 / dt_median)
    nperseg = int(params.get('welch_nperseg') or DEFAULT_WELCH_NPERSEG)
    spectra = []
    freqs_ref = None
    actual_nperseg = np.nan
    skipped_files = 0

    for series in clean_series:
        current_nperseg = max(8, min(nperseg, len(series)))
        x_ac = series - np.median(series)
        freqs, power = signal.welch(
            x_ac,
            fs=fs,
            nperseg=current_nperseg,
            detrend='constant',
            scaling='density',
        )
        if freqs_ref is None:
            freqs_ref = freqs
            actual_nperseg = current_nperseg
            spectra.append(power)
        elif len(freqs) == len(freqs_ref) and np.allclose(freqs, freqs_ref):
            spectra.append(power)
        else:
            skipped_files += 1

    if not spectra or freqs_ref is None:
        return _empty_psd_result()

    spectra = np.vstack(spectra)
    mean_power = np.nanmean(spectra, axis=0)
    median_power = np.nanmedian(spectra, axis=0)
    p10_power = np.nanpercentile(spectra, 10, axis=0)
    p90_power = np.nanpercentile(spectra, 90, axis=0)
    df = float(np.median(np.diff(freqs_ref))) if len(freqs_ref) >= 2 else np.nan

    dc_component = float(mean_power[0]) if len(mean_power) else np.nan
    dominant_all = _dominant_in_band(freqs_ref, mean_power, 0.0, np.inf)
    dominant_excl_dc = _dominant_in_band(freqs_ref, mean_power, df if np.isfinite(df) else 0.0, np.inf)
    dominant_exclude_low = _dominant_in_band(
        freqs_ref,
        mean_power,
        float(params.get('psd_exclude_low_hz') or DEFAULT_EXCLUDE_LOW_HZ),
        np.inf,
    )
    dominant_by_band = {
        name: _dominant_in_band(freqs_ref, mean_power, low, high)
        for name, low, high in DOMINANT_BANDS
    }
    dom_1_100 = _dominant_in_band(freqs_ref, mean_power, 1.0, 100.0)
    dom_0_1k = _dominant_in_band(freqs_ref, mean_power, df if np.isfinite(df) else 0.0, 1000.0)
    dom_0_10k = _dominant_in_band(freqs_ref, mean_power, df if np.isfinite(df) else 0.0, 10000.0)
    band_power = _band_power(freqs_ref, mean_power, DEFAULT_BANDS)
    top_peaks = _top_peaks(
        freqs_ref,
        mean_power,
        int(params.get('top_peak_count') or DEFAULT_TOP_PEAK_COUNT),
        min_frequency=float(params.get('psd_exclude_low_hz') or DEFAULT_EXCLUDE_LOW_HZ),
    )
    peak_index = _nearest_freq_index(freqs_ref, dominant_exclude_low['frequency'])
    peak_stability = _peak_stability(freqs_ref, mean_power, median_power, p10_power, p90_power, peak_index)
    local_noise_floor = _local_noise_floor(freqs_ref, median_power, dominant_exclude_low['frequency'])
    peak_to_floor_ratio = (
        float(dominant_exclude_low['power'] / local_noise_floor)
        if local_noise_floor and np.isfinite(local_noise_floor) and local_noise_floor > 0
        else np.nan
    )
    low_freq = _compute_low_freq_psd(clean_series, fs, params)

    metrics = {
        'psd_fs': fs,
        'psd_fs_hz': fs,
        'psd_nperseg': int(actual_nperseg) if np.isfinite(actual_nperseg) else np.nan,
        'psd_noverlap': int(actual_nperseg // 2) if np.isfinite(actual_nperseg) else np.nan,
        'psd_df': df,
        'psd_df_hz': df,
        'psd_freq_resolution_hz': df,
        'psd_segment_duration_s': float(actual_nperseg / fs) if np.isfinite(actual_nperseg) else np.nan,
        'psd_dc_component_psd': dc_component,
        'psd_dominant_freq_excl_dc_hz': dominant_excl_dc['frequency'],
        'psd_dominant_psd_excl_dc': dominant_excl_dc['power'],
        'psd_dominant_freq_1_100_hz': dom_1_100['frequency'],
        'psd_dominant_psd_1_100': dom_1_100['power'],
        'psd_dominant_freq_0_1k_hz': dom_0_1k['frequency'],
        'psd_dominant_freq_0_10k_hz': dom_0_10k['frequency'],
        'psd_file_count_used': int(spectra.shape[0]),
        'psd_file_count_skipped': int(skipped_files),
        'psd_dom_all_freq_hz': dominant_all['frequency'],
        'psd_dom_all_psd': dominant_all['power'],
        'psd_dom_excl_low_freq_hz': dominant_exclude_low['frequency'],
        'psd_dom_excl_low_psd': dominant_exclude_low['power'],
        'psd_dom_excl_low_cutoff_hz': float(params.get('psd_exclude_low_hz') or DEFAULT_EXCLUDE_LOW_HZ),
        'psd_top_peaks_freq_hz': json.dumps([peak['frequency'] for peak in top_peaks], ensure_ascii=False),
        'psd_top_peaks_psd': json.dumps([peak['power'] for peak in top_peaks], ensure_ascii=False),
        'psd_top_peaks_period_s': json.dumps([1.0 / peak['frequency'] if peak['frequency'] > 0 else np.nan for peak in top_peaks], ensure_ascii=False),
        'psd_top_peaks_prominence': json.dumps([peak.get('prominence', np.nan) for peak in top_peaks], ensure_ascii=False),
        'psd_top_peaks_records': json.dumps(top_peaks, ensure_ascii=False),
        'psd_local_noise_floor': local_noise_floor,
        'psd_peak_to_floor_ratio': peak_to_floor_ratio,
        'psd_mean_psd_at_peak': peak_stability['mean'],
        'psd_median_psd_at_peak': peak_stability['median'],
        'psd_p10_psd_at_peak': peak_stability['p10'],
        'psd_p90_psd_at_peak': peak_stability['p90'],
        'psd_mean_median_ratio': peak_stability['mean_median_ratio'],
        'psd_p90_p10_ratio': peak_stability['p90_p10_ratio'],
        'psd_low_freq_nperseg': low_freq['nperseg'],
        'psd_low_freq_df': low_freq['df'],
        'psd_spectral_entropy': _spectral_entropy(mean_power),
    }
    for name, peak in dominant_by_band.items():
        metrics[f'psd_dominant_freq_{name}'] = peak['frequency']
        metrics[f'psd_dominant_power_{name}'] = peak['power']
    for name, value in band_power.items():
        metrics[f'psd_band_power_{name}'] = value
        count = _bin_count(freqs_ref, _band_bounds(name))
        metrics[f'psd_bin_count_in_band_{name}'] = count
        metrics[f'psd_reliable_low_freq_flag_{name}'] = bool(count >= 5)

    return {
        'metrics': metrics,
        'plot_data': {
            'frequency': freqs_ref,
            'mean_power': mean_power,
            'median_power': median_power,
            'p10_power': p10_power,
            'p90_power': p90_power,
            'top_peaks_exclude_low': top_peaks,
            'low_frequency': low_freq['plot_data'],
        },
    }


def _clean_series_and_dt(series_list, time_list=None):
    time_list = time_list or [None] * len(series_list)
    clean_series = []
    dt_parts = []
    for series, time in zip(series_list, time_list):
        x = np.asarray(series, dtype=float)
        if time is None:
            valid = np.isfinite(x)
        else:
            t = np.asarray(time, dtype=float)
            valid = np.isfinite(x) & np.isfinite(t)
            t = t[valid]
            if len(t) >= 2:
                dt = np.diff(t)
                dt = dt[np.isfinite(dt) & (dt > 0)]
                if dt.size:
                    dt_parts.append(dt)
        x = x[valid]
        if x.size >= 8:
            clean_series.append(x)
    if not dt_parts:
        return clean_series, np.nan
    return clean_series, float(np.median(np.concatenate(dt_parts)))


def _dominant_in_band(freqs, power, low, high):
    mask = (freqs >= low) & (freqs < high) & np.isfinite(power)
    if not np.any(mask):
        return {'frequency': np.nan, 'power': np.nan}
    indices = np.where(mask)[0]
    best = indices[int(np.nanargmax(power[indices]))]
    return {'frequency': float(freqs[best]), 'power': float(power[best])}


def _top_peaks(freqs, power, count, min_frequency=0.0):
    mask = (freqs >= min_frequency) & np.isfinite(power)
    indices = np.where(mask)[0]
    if indices.size == 0:
        return []
    peak_positions, props = signal.find_peaks(power[indices], prominence=0)
    peak_indices = indices[peak_positions] if peak_positions.size else indices
    order = np.argsort(power[peak_indices])[::-1][:count]
    prominences = props.get('prominences', np.full(len(peak_positions), np.nan))
    prominence_by_index = {
        int(indices[peak_positions[i]]): float(prominences[i])
        for i in range(len(peak_positions))
    }
    return [{
        'frequency': float(freqs[peak_indices[i]]),
        'power': float(power[peak_indices[i]]),
        'period_s': float(1.0 / freqs[peak_indices[i]]) if freqs[peak_indices[i]] > 0 else np.nan,
        'prominence': prominence_by_index.get(int(peak_indices[i]), np.nan),
    } for i in order]


def _compute_low_freq_psd(clean_series, fs, params):
    target_nperseg = int(params.get('low_freq_nperseg') or DEFAULT_LOW_FREQ_NPERSEG)
    spectra = []
    freqs_ref = None
    actual_nperseg = np.nan
    for series in clean_series:
        current_nperseg = max(8, min(target_nperseg, len(series)))
        x_ac = series - np.median(series)
        freqs, power = signal.welch(
            x_ac,
            fs=fs,
            nperseg=current_nperseg,
            detrend='constant',
            scaling='density',
        )
        if freqs_ref is None:
            freqs_ref = freqs
            actual_nperseg = current_nperseg
            spectra.append(power)
        elif len(freqs) == len(freqs_ref) and np.allclose(freqs, freqs_ref):
            spectra.append(power)
    if not spectra or freqs_ref is None:
        empty = np.asarray([])
        return {'nperseg': np.nan, 'df': np.nan, 'plot_data': {'frequency': empty, 'mean_power': empty, 'median_power': empty, 'p10_power': empty, 'p90_power': empty}}
    spectra = np.vstack(spectra)
    df = float(np.median(np.diff(freqs_ref))) if len(freqs_ref) >= 2 else np.nan
    return {
        'nperseg': int(actual_nperseg) if np.isfinite(actual_nperseg) else np.nan,
        'df': df,
        'plot_data': {
            'frequency': freqs_ref,
            'mean_power': np.nanmean(spectra, axis=0),
            'median_power': np.nanmedian(spectra, axis=0),
            'p10_power': np.nanpercentile(spectra, 10, axis=0),
            'p90_power': np.nanpercentile(spectra, 90, axis=0),
        },
    }


def _nearest_freq_index(freqs, frequency):
    if not np.isfinite(frequency) or len(freqs) == 0:
        return None
    return int(np.argmin(np.abs(freqs - frequency)))


def _peak_stability(freqs, mean_power, median_power, p10_power, p90_power, peak_index):
    if peak_index is None:
        return {'mean': np.nan, 'median': np.nan, 'p10': np.nan, 'p90': np.nan, 'mean_median_ratio': np.nan, 'p90_p10_ratio': np.nan}
    mean_value = float(mean_power[peak_index])
    median_value = float(median_power[peak_index])
    p10_value = float(p10_power[peak_index])
    p90_value = float(p90_power[peak_index])
    return {
        'mean': mean_value,
        'median': median_value,
        'p10': p10_value,
        'p90': p90_value,
        'mean_median_ratio': float(mean_value / median_value) if median_value > 0 else np.nan,
        'p90_p10_ratio': float(p90_value / p10_value) if p10_value > 0 else np.nan,
    }


def _local_noise_floor(freqs, power, frequency):
    if not np.isfinite(frequency) or len(freqs) == 0:
        return np.nan
    width = max(5 * float(np.median(np.diff(freqs))), 0.05 * frequency)
    guard = max(2 * float(np.median(np.diff(freqs))), 0.01 * frequency)
    mask = (freqs >= frequency - width) & (freqs <= frequency + width)
    mask &= ~((freqs >= frequency - guard) & (freqs <= frequency + guard))
    values = power[mask & np.isfinite(power)]
    return float(np.median(values)) if values.size else np.nan


def _band_power(freqs, power, bands):
    output = {}
    for label, low, high in bands:
        mask = (freqs >= low) & (freqs < high)
        if np.sum(mask) >= 2:
            output[label] = float(np.trapz(power[mask], freqs[mask]))
        else:
            output[label] = np.nan
    return output


def _bin_count(freqs, bounds):
    if bounds is None:
        return 0
    low, high = bounds
    return int(np.sum((freqs >= low) & (freqs < high)))


def _band_bounds(label):
    for band_label, low, high in DEFAULT_BANDS:
        if band_label == label:
            return low, high
    return None


def _spectral_entropy(power):
    values = np.asarray(power, dtype=float)
    values = values[np.isfinite(values) & (values > 0)]
    total = np.sum(values)
    if total <= 0:
        return np.nan
    probs = values / total
    entropy = -np.sum(probs * np.log2(probs))
    return float(entropy / np.log2(len(probs))) if len(probs) > 1 else np.nan


def _empty_psd_result():
    metrics = {
        'psd_fs': np.nan,
        'psd_fs_hz': np.nan,
        'psd_nperseg': np.nan,
        'psd_noverlap': np.nan,
        'psd_df': np.nan,
        'psd_df_hz': np.nan,
        'psd_freq_resolution_hz': np.nan,
        'psd_segment_duration_s': np.nan,
        'psd_dc_component_psd': np.nan,
        'psd_dominant_freq_excl_dc_hz': np.nan,
        'psd_dominant_psd_excl_dc': np.nan,
        'psd_dominant_freq_1_100_hz': np.nan,
        'psd_dominant_psd_1_100': np.nan,
        'psd_dominant_freq_0_1k_hz': np.nan,
        'psd_dominant_freq_0_10k_hz': np.nan,
        'psd_file_count_used': 0,
        'psd_file_count_skipped': np.nan,
        'psd_dom_all_freq_hz': np.nan,
        'psd_dom_all_psd': np.nan,
        'psd_dom_excl_low_freq_hz': np.nan,
        'psd_dom_excl_low_psd': np.nan,
        'psd_dom_excl_low_cutoff_hz': DEFAULT_EXCLUDE_LOW_HZ,
        'psd_top_peaks_freq_hz': '[]',
        'psd_top_peaks_psd': '[]',
        'psd_top_peaks_period_s': '[]',
        'psd_top_peaks_prominence': '[]',
        'psd_top_peaks_records': '[]',
        'psd_local_noise_floor': np.nan,
        'psd_peak_to_floor_ratio': np.nan,
        'psd_mean_psd_at_peak': np.nan,
        'psd_median_psd_at_peak': np.nan,
        'psd_p10_psd_at_peak': np.nan,
        'psd_p90_psd_at_peak': np.nan,
        'psd_mean_median_ratio': np.nan,
        'psd_p90_p10_ratio': np.nan,
        'psd_low_freq_nperseg': np.nan,
        'psd_low_freq_df': np.nan,
        'psd_spectral_entropy': np.nan,
    }
    for name, _, _ in DOMINANT_BANDS:
        metrics[f'psd_dominant_freq_{name}'] = np.nan
        metrics[f'psd_dominant_power_{name}'] = np.nan
    for name, _, _ in DEFAULT_BANDS:
        metrics[f'psd_band_power_{name}'] = np.nan
        metrics[f'psd_bin_count_in_band_{name}'] = 0
        metrics[f'psd_reliable_low_freq_flag_{name}'] = False
    return {
        'metrics': metrics,
        'plot_data': {
            'frequency': np.asarray([]),
            'mean_power': np.asarray([]),
            'median_power': np.asarray([]),
            'p10_power': np.asarray([]),
            'p90_power': np.asarray([]),
            'top_peaks_exclude_low': [],
            'low_frequency': {
                'frequency': np.asarray([]),
                'mean_power': np.asarray([]),
                'median_power': np.asarray([]),
                'p10_power': np.asarray([]),
                'p90_power': np.asarray([]),
            },
        },
    }
