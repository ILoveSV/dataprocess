from pathlib import Path
import json

import pandas as pd

from src.io.time_csv_io import safe_sheet_name
from src.summaries.nist_diagnostics_summary import summarize_nist_diagnostics


def export_nist_metrics_excel(rows, output_path):
    """Export per-file/channel NIST diagnostics to Excel, one sheet per channel."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)

    used_sheet_names = set()
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        if df.empty:
            pd.DataFrame().to_excel(writer, sheet_name='metrics', index=False)
        else:
            for channel, channel_df in df.groupby('channel', dropna=False):
                sheet_name = safe_sheet_name(str(channel), used_sheet_names)
                channel_df.to_excel(writer, sheet_name=sheet_name, index=False)
    return output_path


def export_nist_group_summary_excel(rows, output_path, summary_rows=None):
    """Export group/channel NIST diagnostics summary to Excel."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(summary_rows) if summary_rows is not None else summarize_nist_diagnostics(rows)
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='group_summary', index=False)
    return output_path


def export_nist_file_stability_summary_excel(rows, output_path):
    """Export compact per-file/channel stability summary for NIST diagnostics."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([_stability_row(row) for row in rows])
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='file_stability', index=False)
    return output_path


def export_psd_group_summary_excel(rows, output_path):
    """Export group/channel PSD summary to Excel."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        'group',
        'channel',
        'file_count',
        'is_smoke_test',
        'fs',
        'nperseg',
        'noverlap',
        'df',
        'df_hz',
        'freq_resolution_hz',
        'segment_duration_s',
        'dc_component_psd',
        'dominant_freq_excl_dc_hz',
        'dominant_psd_excl_dc',
        'dominant_freq_1_100_hz',
        'dominant_psd_1_100',
        'dominant_freq_0_1k_hz',
        'dominant_freq_0_10k_hz',
        'dom_all_freq_hz',
        'dom_all_psd',
        'dom_excl_low_freq_hz',
        'dom_excl_low_psd',
        'dom_excl_low_cutoff_hz',
        'dominant_freq_0_100Hz',
        'dominant_freq_100_1000Hz',
        'dominant_freq_1k_10kHz',
        'dominant_freq_10k_200kHz',
        'top_peaks_freq_hz',
        'top_peaks_psd',
        'top_peaks_period_s',
        'top_peaks_prominence',
        'local_noise_floor',
        'peak_to_floor_ratio',
        'mean_psd_at_peak',
        'median_psd_at_peak',
        'p10_psd_at_peak',
        'p90_psd_at_peak',
        'mean_median_ratio',
        'p90_p10_ratio',
        'low_freq_nperseg',
        'low_freq_df',
        'band_power_0_50Hz',
        'band_power_50_100Hz',
        'band_power_100_1000Hz',
        'band_power_1k_10kHz',
        'band_power_10k_50kHz',
        'band_power_50k_200kHz',
        'spectral_entropy',
        'bin_count_in_band_0_5Hz',
        'bin_count_in_band_0_20Hz',
        'bin_count_in_band_0_100Hz',
        'reliable_low_freq_flag_0_5Hz',
        'reliable_low_freq_flag_0_20Hz',
        'reliable_low_freq_flag_0_100Hz',
    ]
    df = pd.DataFrame([_psd_summary_row(row) for row in rows])
    df = df.reindex(columns=columns)
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='psd_group_summary', index=False)
    return output_path


def export_acf_group_summary_excel(rows, output_path):
    """Export group/channel ACF summary to Excel."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        'group',
        'channel',
        'file_count',
        'is_smoke_test',
        'fs',
        'dt',
        'max_lag_s',
        'zero_cross_s',
        'first_below_threshold_s',
        'first_strong_peak_lag_s',
        'first_strong_peak_freq_hz',
        'global_max_peak_lag_s',
        'global_max_peak_freq_hz',
        'peak_spacing_period_s',
        'peak_spacing_freq_hz',
        'acf_decay_time_s',
        'acf_period_conflict_flag',
        'acf_period_conflict_reason',
        'acf_primary_period_s',
        'acf_peak_lag_s',
        'acf_peak_height',
        'acf_peak_prominence',
        'psd_peak_freq_hz',
        'psd_peak_period_s',
        'nearest_acf_peak_lag_s',
        'nearest_multiple_k',
        'matched_lag_s',
        'acf_value_at_psd_period',
        'acf_psd_period_error_percent',
        'acf_psd_matches',
        'acf_psd_peak_may_be_harmonic',
    ]
    df = pd.DataFrame([_acf_summary_row(row) for row in rows])
    df = df.reindex(columns=columns)
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='acf_group_summary', index=False)
    return output_path


def export_psd_acf_summary_excel(psd_rows, acf_rows, output_path):
    """Export combined PSD/ACF group-channel summary."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    acf_by_key = {(row.get('group'), row.get('channel')): row for row in acf_rows}
    rows = []
    for psd in psd_rows:
        key = (psd.get('group'), psd.get('channel'))
        acf = acf_by_key.get(key, {})
        fundamental_period = _period(psd.get('psd_dom_excl_low_freq_hz'))
        acf_primary = acf.get('acf_primary_period_s')
        abs_error = _abs_error(fundamental_period, acf_primary)
        rel_error = abs_error / fundamental_period if pd.notna(abs_error) and pd.notna(fundamental_period) and fundamental_period else pd.NA
        rows.append({
            'group': psd.get('group'),
            'channel': psd.get('channel'),
            'file_count': psd.get('file_count'),
            'is_smoke_test': psd.get('is_smoke_test', False),
            'fs': psd.get('psd_fs'),
            'nperseg': psd.get('psd_nperseg'),
            'df': psd.get('psd_df'),
            'dom_all_freq_hz': psd.get('psd_dom_all_freq_hz'),
            'dom_excl_low_freq_hz': psd.get('psd_dom_excl_low_freq_hz'),
            'dom_excl_low_period_s': _period(psd.get('psd_dom_excl_low_freq_hz')),
            'psd_fundamental_freq_hz': psd.get('psd_dom_excl_low_freq_hz'),
            'psd_fundamental_period_s': fundamental_period,
            'acf_primary_period_s': acf_primary,
            'fundamental_period_abs_error_s': abs_error,
            'fundamental_period_rel_error': rel_error,
            'fundamental_match_flag': bool(pd.notna(rel_error) and rel_error <= 0.10),
            'acf_peak_spacing_period_s': acf.get('acf_peak_spacing_period_s'),
            'acf_peak_spacing_freq_hz': acf.get('acf_peak_spacing_freq_hz'),
            'acf_psd_match_error_percent': acf.get('acf_psd_period_error_percent'),
            'mean_median_ratio_at_peak': psd.get('psd_mean_median_ratio'),
            'p90_p10_ratio_at_peak': psd.get('psd_p90_p10_ratio'),
        })
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name='psd_acf_summary', index=False)
    return output_path


def export_harmonic_matches_long_excel(acf_rows, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for row in acf_rows:
        for match in _json_list(row.get('acf_psd_matches')):
            if not isinstance(match, dict):
                continue
            rows.append({
                'group': row.get('group'),
                'channel': row.get('channel'),
                'file_count': row.get('file_count'),
                'is_smoke_test': row.get('is_smoke_test', False),
                'psd_peak_freq_hz': match.get('psd_peak_freq_hz'),
                'psd_period_s': match.get('psd_peak_period_s'),
                'nearest_acf_peak_lag_s': match.get('nearest_acf_peak_lag_s'),
                'nearest_multiple_k': match.get('nearest_multiple_k'),
                'matched_lag_s': match.get('matched_lag_s'),
                'error_percent': match.get('error_percent'),
                'acf_value_at_match': match.get('acf_value_at_matched_lag'),
                'is_smoke_test': row.get('is_smoke_test', False),
            })
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name='harmonic_matches', index=False)
    return output_path


def export_psd_acf_match_table_excel(acf_rows, output_path):
    """Export one row per PSD peak to ACF match result."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for row in acf_rows:
        for match in _json_list(row.get('acf_psd_matches')):
            if not isinstance(match, dict):
                continue
            rows.append({
                'group': row.get('group'),
                'channel': row.get('channel'),
                'file_count': row.get('file_count'),
                'psd_peak_freq_hz': match.get('psd_peak_freq_hz'),
                'psd_period_s': match.get('psd_peak_period_s'),
                'acf_first_strong_s': row.get('acf_first_strong_peak_lag_s'),
                'acf_global_max_s': row.get('acf_global_max_peak_lag_s'),
                'acf_spacing_s': row.get('acf_peak_spacing_period_s'),
                'nearest_acf_peak_lag_s': match.get('nearest_acf_peak_lag_s'),
                'nearest_multiple_k': match.get('nearest_multiple_k'),
                'period_error_percent': match.get('error_percent'),
                'acf_value_at_match': match.get('acf_value_at_matched_lag'),
            })
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name='psd_acf_peak_matches', index=False)
    return output_path


def export_psd_peaks_long_excel(psd_rows, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for row in psd_rows:
        freqs = _json_list(row.get('psd_top_peaks_freq_hz'))
        powers = _json_list(row.get('psd_top_peaks_psd'))
        periods = _json_list(row.get('psd_top_peaks_period_s'))
        ratios = row.get('psd_peak_to_floor_ratio')
        for idx, freq in enumerate(freqs, start=1):
            rows.append({
                'group': row.get('group'),
                'channel': row.get('channel'),
                'file_id_or_file_name': 'group_mean',
                'peak_rank': idx,
                'peak_freq_hz': freq,
                'peak_psd': powers[idx - 1] if idx - 1 < len(powers) else pd.NA,
                'peak_period_s': periods[idx - 1] if idx - 1 < len(periods) else pd.NA,
                'peak_to_floor_ratio': ratios if idx == 1 else pd.NA,
                'band_name': _band_name(freq),
                'is_smoke_test': row.get('is_smoke_test', False),
            })
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name='psd_peaks_long', index=False)
    return output_path


def export_acf_peaks_long_excel(acf_rows, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for row in acf_rows:
        lags = _json_list(row.get('acf_peak_lag_s'))
        heights = _json_list(row.get('acf_peak_height'))
        for idx, lag in enumerate(lags, start=1):
            rows.append({
                'group': row.get('group'),
                'channel': row.get('channel'),
                'file_id_or_file_name': 'group_mean',
                'peak_rank': idx,
                'peak_lag_s': lag,
                'peak_value': heights[idx - 1] if idx - 1 < len(heights) else pd.NA,
                'peak_type': _acf_peak_type(row, lag),
                'is_smoke_test': row.get('is_smoke_test', False),
            })
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name='acf_peaks_long', index=False)
    return output_path


def export_background_subtraction_summary_excel(rows, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        'target_group', 'background_group', 'channel', 'mean_delta_v',
        'rms_delta_v', 'std_delta_v', 'band_power_delta_0_100',
        'band_power_delta_0_1k', 'band_power_delta_0_10k',
        'dominant_freq_before_hz', 'dominant_freq_after_hz',
        'subtraction_valid_flag', 'note',
    ]
    df = pd.DataFrame(rows, columns=columns)
    if df.empty:
        df = pd.DataFrame([{'subtraction_valid_flag': False, 'note': 'no background group configured'}], columns=columns)
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='background_subtraction', index=False)
    return output_path


def export_cross_channel_peak_summary_excel(psd_rows, output_path):
    """Cluster top PSD peaks across channels and export a group-level summary."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = _cross_channel_peak_clusters(psd_rows)
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name='cross_channel_peaks', index=False)
    return output_path


def _psd_summary_row(row):
    return {
        'group': row.get('group'),
        'channel': row.get('channel'),
        'file_count': row.get('file_count'),
        'is_smoke_test': row.get('is_smoke_test', False),
        'fs': row.get('psd_fs'),
        'nperseg': row.get('psd_nperseg'),
        'noverlap': row.get('psd_noverlap'),
        'df': row.get('psd_df'),
        'df_hz': row.get('psd_df_hz'),
        'freq_resolution_hz': row.get('psd_freq_resolution_hz'),
        'segment_duration_s': row.get('psd_segment_duration_s'),
        'dc_component_psd': row.get('psd_dc_component_psd'),
        'dominant_freq_excl_dc_hz': row.get('psd_dominant_freq_excl_dc_hz'),
        'dominant_psd_excl_dc': row.get('psd_dominant_psd_excl_dc'),
        'dominant_freq_1_100_hz': row.get('psd_dominant_freq_1_100_hz'),
        'dominant_psd_1_100': row.get('psd_dominant_psd_1_100'),
        'dominant_freq_0_1k_hz': row.get('psd_dominant_freq_0_1k_hz'),
        'dominant_freq_0_10k_hz': row.get('psd_dominant_freq_0_10k_hz'),
        'dom_all_freq_hz': row.get('psd_dom_all_freq_hz'),
        'dom_all_psd': row.get('psd_dom_all_psd'),
        'dom_excl_low_freq_hz': row.get('psd_dom_excl_low_freq_hz'),
        'dom_excl_low_psd': row.get('psd_dom_excl_low_psd'),
        'dom_excl_low_cutoff_hz': row.get('psd_dom_excl_low_cutoff_hz'),
        'dominant_freq_0_100Hz': row.get('psd_dominant_freq_0_100Hz'),
        'dominant_freq_100_1000Hz': row.get('psd_dominant_freq_100_1000Hz'),
        'dominant_freq_1k_10kHz': row.get('psd_dominant_freq_1k_10kHz'),
        'dominant_freq_10k_200kHz': row.get('psd_dominant_freq_10k_200kHz'),
        'top_peaks_freq_hz': row.get('psd_top_peaks_freq_hz'),
        'top_peaks_psd': row.get('psd_top_peaks_psd'),
        'top_peaks_period_s': row.get('psd_top_peaks_period_s'),
        'top_peaks_prominence': row.get('psd_top_peaks_prominence'),
        'local_noise_floor': row.get('psd_local_noise_floor'),
        'peak_to_floor_ratio': row.get('psd_peak_to_floor_ratio'),
        'mean_psd_at_peak': row.get('psd_mean_psd_at_peak'),
        'median_psd_at_peak': row.get('psd_median_psd_at_peak'),
        'p10_psd_at_peak': row.get('psd_p10_psd_at_peak'),
        'p90_psd_at_peak': row.get('psd_p90_psd_at_peak'),
        'mean_median_ratio': row.get('psd_mean_median_ratio'),
        'p90_p10_ratio': row.get('psd_p90_p10_ratio'),
        'low_freq_nperseg': row.get('psd_low_freq_nperseg'),
        'low_freq_df': row.get('psd_low_freq_df'),
        'band_power_0_50Hz': row.get('psd_band_power_0_50Hz'),
        'band_power_50_100Hz': row.get('psd_band_power_50_100Hz'),
        'band_power_100_1000Hz': row.get('psd_band_power_100_1000Hz'),
        'band_power_1k_10kHz': row.get('psd_band_power_1k_10kHz'),
        'band_power_10k_50kHz': row.get('psd_band_power_10k_50kHz'),
        'band_power_50k_200kHz': row.get('psd_band_power_50k_200kHz'),
        'spectral_entropy': row.get('psd_spectral_entropy'),
        'bin_count_in_band_0_5Hz': row.get('psd_bin_count_in_band_0_5Hz'),
        'bin_count_in_band_0_20Hz': row.get('psd_bin_count_in_band_0_20Hz'),
        'bin_count_in_band_0_100Hz': row.get('psd_bin_count_in_band_0_100Hz'),
        'reliable_low_freq_flag_0_5Hz': row.get('psd_reliable_low_freq_flag_0_5Hz'),
        'reliable_low_freq_flag_0_20Hz': row.get('psd_reliable_low_freq_flag_0_20Hz'),
        'reliable_low_freq_flag_0_100Hz': row.get('psd_reliable_low_freq_flag_0_100Hz'),
    }


def _acf_summary_row(row):
    return {
        'group': row.get('group'),
        'channel': row.get('channel'),
        'file_count': row.get('file_count'),
        'is_smoke_test': row.get('is_smoke_test', False),
        'fs': row.get('acf_fs'),
        'dt': row.get('acf_dt'),
        'max_lag_s': row.get('acf_max_lag_s'),
        'zero_cross_s': row.get('acf_zero_cross_s'),
        'first_below_threshold_s': row.get('acf_first_below_threshold_s'),
        'first_strong_peak_lag_s': row.get('acf_first_strong_peak_lag_s'),
        'first_strong_peak_freq_hz': row.get('acf_first_strong_peak_freq_hz'),
        'global_max_peak_lag_s': row.get('acf_global_max_peak_lag_s'),
        'global_max_peak_freq_hz': row.get('acf_global_max_peak_freq_hz'),
        'peak_spacing_period_s': row.get('acf_peak_spacing_period_s'),
        'peak_spacing_freq_hz': row.get('acf_peak_spacing_freq_hz'),
        'acf_decay_time_s': row.get('acf_decay_time_s'),
        'acf_period_conflict_flag': row.get('acf_period_conflict_flag'),
        'acf_period_conflict_reason': row.get('acf_period_conflict_reason'),
        'acf_primary_period_s': row.get('acf_primary_period_s'),
        'acf_peak_lag_s': row.get('acf_peak_lag_s'),
        'acf_peak_height': row.get('acf_peak_height'),
        'acf_peak_prominence': row.get('acf_peak_prominence'),
        'psd_peak_freq_hz': _primary_match_value(row, 'psd_peak_freq_hz'),
        'psd_peak_period_s': _primary_match_value(row, 'psd_peak_period_s'),
        'nearest_acf_peak_lag_s': _primary_match_value(row, 'nearest_acf_peak_lag_s'),
        'nearest_multiple_k': _primary_match_value(row, 'nearest_multiple_k'),
        'matched_lag_s': _primary_match_value(row, 'matched_lag_s'),
        'acf_value_at_psd_period': row.get('acf_value_at_psd_period'),
        'acf_psd_period_error_percent': row.get('acf_psd_period_error_percent'),
        'acf_psd_matches': row.get('acf_psd_matches'),
        'acf_psd_peak_may_be_harmonic': row.get('acf_psd_peak_may_be_harmonic'),
    }


def _cross_channel_peak_clusters(psd_rows):
    by_group = {}
    for row in psd_rows:
        group = row.get('group')
        channel = row.get('channel')
        df = row.get('psd_df')
        tolerance = max(2 * float(df), 50.0) if df else 50.0
        freqs = _json_list(row.get('psd_top_peaks_freq_hz'))
        powers = _json_list(row.get('psd_top_peaks_psd'))
        for idx, freq in enumerate(freqs):
            if freq is None:
                continue
            by_group.setdefault(group, []).append({
                'freq': float(freq),
                'power': float(powers[idx]) if idx < len(powers) and powers[idx] is not None else pd.NA,
                'channel': channel,
                'tolerance': tolerance,
            })

    output = []
    for group, peaks in by_group.items():
        peaks = sorted(peaks, key=lambda item: item['freq'])
        clusters = []
        for peak in peaks:
            if not clusters or abs(peak['freq'] - clusters[-1]['center']) > peak['tolerance']:
                clusters.append({'items': [peak], 'center': peak['freq']})
            else:
                clusters[-1]['items'].append(peak)
                clusters[-1]['center'] = sum(item['freq'] for item in clusters[-1]['items']) / len(clusters[-1]['items'])
        centers = [cluster['center'] for cluster in clusters]
        for cluster in clusters:
            items = cluster['items']
            channels = sorted({item['channel'] for item in items})
            powers = [item['power'] for item in items if pd.notna(item['power'])]
            output.append({
                'group': group,
                'peak_cluster_center_hz': cluster['center'],
                'channels_present': ','.join(channels),
                'channel_count': len(channels),
                'mean_peak_power': sum(powers) / len(powers) if powers else pd.NA,
                'median_peak_power': pd.Series(powers).median() if powers else pd.NA,
                'possible_harmonic_relation': _harmonic_relation(cluster['center'], centers),
            })
    return output


def _json_list(value):
    if value in (None, '') or pd.isna(value):
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def _primary_match_value(row, key):
    matches = _json_list(row.get('acf_psd_matches'))
    if matches and isinstance(matches[0], dict):
        return matches[0].get(key)
    return pd.NA


def _harmonic_relation(freq, centers):
    if not centers or freq <= 0:
        return ''
    relations = []
    for center in centers:
        if center <= 0 or center == freq:
            continue
        ratio = freq / center
        nearest = round(ratio)
        if nearest >= 2 and abs(ratio - nearest) <= 0.03:
            relations.append(f'~{nearest}x {center:.6g}Hz')
    return '; '.join(relations)


def _period(freq):
    try:
        freq = float(freq)
    except (TypeError, ValueError):
        return pd.NA
    return 1.0 / freq if freq > 0 else pd.NA


def _abs_error(a, b):
    try:
        if pd.isna(a) or pd.isna(b):
            return pd.NA
        return abs(float(a) - float(b))
    except (TypeError, ValueError):
        return pd.NA


def _band_name(freq):
    try:
        freq = float(freq)
    except (TypeError, ValueError):
        return ''
    if freq < 100:
        return '0_100Hz'
    if freq < 1000:
        return '100_1000Hz'
    if freq < 10000:
        return '1k_10kHz'
    if freq < 200000:
        return '10k_200kHz'
    return 'above_200kHz'


def _acf_peak_type(row, lag):
    labels = []
    for key, label in [
        ('acf_first_strong_peak_lag_s', 'first_strong'),
        ('acf_global_max_peak_lag_s', 'global_max'),
        ('acf_peak_spacing_period_s', 'spacing'),
    ]:
        try:
            if abs(float(row.get(key)) - float(lag)) <= 1e-12:
                labels.append(label)
        except (TypeError, ValueError):
            pass
    return '|'.join(labels) if labels else 'local_peak'


def _stability_row(row):
    robust_sigma = row.get('run_robust_sigma')
    try:
        mad = float(robust_sigma) / 1.4826
    except (TypeError, ValueError):
        mad = pd.NA
    return {
        'group': row.get('group'),
        'file': row.get('file'),
        'channel': row.get('channel'),
        'mean': row.get('run_mean'),
        'median': row.get('run_median'),
        'std': row.get('run_std'),
        'rms': row.get('run_ac_rms'),
        'mad': mad,
        'q05': row.get('dist_q05'),
        'q95': row.get('dist_q95'),
        'lag1_corr': row.get('lag_1_corr'),
        'qq_corr': row.get('qq_normal_prob_corr'),
        'tail_dev': row.get('qq_tail_deviation'),
        'drift_span': row.get('run_drift_span'),
        'rolling_mean_range': row.get('run_rolling_mean_range'),
    }
