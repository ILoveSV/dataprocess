import argparse
import logging
import shutil
import json
from pathlib import Path

import numpy as np

from src.core.config_loader import load_config
from src.core.path_resolver import derive_nist_diagnostics_output_dir
from src.features.nist_acf import compute_group_acf_diagnostics
from src.features.nist_diagnostics import compute_group_nist_diagnostics, compute_nist_diagnostics
from src.features.nist_psd import compute_group_welch_psd
from src.io.time_csv_io import collect_csv_groups, read_csv_data
from src.plots.nist_4plot import plot_nist_4plot
from src.plots.nist_acf_plot import plot_group_acf_ranges
from src.plots.nist_psd_plot import plot_group_psd_ranges
from src.reports.nist_excel_export import (
    export_nist_file_stability_summary_excel,
    export_nist_group_summary_excel,
    export_nist_metrics_excel,
    export_acf_group_summary_excel,
    export_cross_channel_peak_summary_excel,
    export_acf_peaks_long_excel,
    export_background_subtraction_summary_excel,
    export_harmonic_matches_long_excel,
    export_psd_peaks_long_excel,
    export_psd_acf_match_table_excel,
    export_psd_acf_summary_excel,
    export_psd_group_summary_excel,
)


logger = logging.getLogger('data_process')


def _clean_metric_value(value):
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float):
        return value if np.isfinite(value) else np.nan
    return value


def process_nist_group(input_files, group_dir, output_dir, params, enable_plots=True, debug_file_plots=False):
    """Process one CSV group and write NIST diagnostics outputs."""
    rows = []
    group_series = {}
    group_times = {}
    group_name = Path(group_dir).name
    is_smoke_test = _is_smoke_group(group_name)
    if enable_plots:
        _prepare_nist_figure_dirs(output_dir, debug_file_plots)

    for csv_file in input_files:
        try:
            df, time_column, channel_columns = read_csv_data(csv_file)
            time_values = df[time_column].values
            file_stem = Path(csv_file).stem

            for channel in channel_columns:
                try:
                    group_series.setdefault(channel, []).append(df[channel].values)
                    group_times.setdefault(channel, []).append(time_values)
                    result = compute_nist_diagnostics(df[channel].values, time=time_values, params=params)
                    metrics = {
                        key: _clean_metric_value(value)
                        for key, value in result['metrics'].items()
                    }
                    row = {
                        'group': group_name,
                        'file': Path(csv_file).name,
                        'channel': channel,
                        'is_smoke_test': is_smoke_test,
                        **metrics,
                    }
                    rows.append(row)

                    if enable_plots and debug_file_plots:
                        figure_path = Path(output_dir) / 'figures' / 'file_4plot' / file_stem / f'{channel}_4plot.png'
                        plot_nist_4plot(
                            result['plot_data'],
                            result['metrics'],
                            figure_path,
                            title=f"{Path(group_dir).name} / {Path(csv_file).name} / {channel}",
                        )
                except Exception as exc:
                    logger.warning("NIST diagnostics failed for %s %s: %s", csv_file, channel, exc)
        except Exception as exc:
            logger.warning("Could not read NIST diagnostics input %s: %s", csv_file, exc)

    group_summary_rows = []
    acf_rows = []
    psd_rows = []
    if enable_plots:
        for channel, series_list in group_series.items():
            try:
                result = compute_group_nist_diagnostics(series_list, time_list=group_times.get(channel), params=params)
                psd_result = compute_group_welch_psd(series_list, time_list=group_times.get(channel), params=params)
                acf_result = compute_group_acf_diagnostics(
                    series_list,
                    time_list=group_times.get(channel),
                    max_acf_lag=params.get('max_acf_lag'),
                    max_acf_seconds=params.get('max_acf_seconds'),
                    psd_candidate_freq_hz=psd_result['metrics'].get('psd_dom_all_freq_hz'),
                    psd_candidate_freqs_hz=_json_metric_list(psd_result['metrics'].get('psd_top_peaks_freq_hz')),
                    min_peak_distance_s=params.get('acf_min_peak_distance_s'),
                    min_peak_prominence=params.get('acf_min_peak_prominence'),
                    near_zero_exclude_s=params.get('acf_near_zero_exclude_s'),
                    strong_peak_height=params.get('acf_strong_peak_height'),
                    strong_peak_prominence=params.get('acf_strong_peak_prominence'),
                )
                metrics = {
                    key: _clean_metric_value(value)
                    for key, value in result['metrics'].items()
                }
                acf_metrics = {
                    key: _clean_metric_value(value)
                    for key, value in acf_result['metrics'].items()
                }
                psd_metrics = {
                    key: _clean_metric_value(value)
                    for key, value in psd_result['metrics'].items()
                }
                group_summary_rows.append({
                    'group': group_name,
                    'channel': channel,
                    'file_count': len(series_list),
                    'is_smoke_test': is_smoke_test,
                    **metrics,
                })
                acf_rows.append({'group': group_name, 'channel': channel, 'file_count': len(series_list), 'is_smoke_test': is_smoke_test, **acf_metrics})
                psd_rows.append({'group': group_name, 'channel': channel, 'file_count': len(series_list), 'is_smoke_test': is_smoke_test, **psd_metrics})
                figure_path = Path(output_dir) / 'figures' / 'group_4plot' / f'{channel}_4plot.png'
                plot_nist_4plot(
                    result['plot_data'],
                    result['metrics'],
                    figure_path,
                    title=f"NIST 4-Plot | group={group_name} | channel={channel} | files={len(series_list)}",
                )
                acf_path = Path(output_dir) / 'figures' / 'acf' / channel
                plot_group_acf_ranges(
                    acf_result['plot_data'],
                    acf_result['metrics'],
                    acf_path,
                    title_prefix=f"ACF | group={group_name} | channel={channel} | files={len(series_list)}",
                    max_psd_period_refs=params.get('max_psd_period_refs'),
                )
                psd_path = Path(output_dir) / 'figures' / 'psd' / f'{channel}_psd.png'
                plot_group_psd_ranges(
                    psd_result['plot_data'],
                    {'file_count': len(series_list), **psd_result['metrics']},
                    psd_path.parent / channel,
                    title_prefix=f"Welch PSD | group={group_name} | channel={channel} | files={len(series_list)}",
                    group=group_name,
                    channel=channel,
                )
            except Exception as exc:
                logger.warning("Group-level NIST diagnostics failed for %s %s: %s", group_name, channel, exc)

    if not group_summary_rows:
        for channel, series_list in group_series.items():
            try:
                result = compute_group_nist_diagnostics(series_list, time_list=group_times.get(channel), params=params)
                psd_result = compute_group_welch_psd(series_list, time_list=group_times.get(channel), params=params)
                acf_result = compute_group_acf_diagnostics(
                    series_list,
                    time_list=group_times.get(channel),
                    max_acf_lag=params.get('max_acf_lag'),
                    max_acf_seconds=params.get('max_acf_seconds'),
                    psd_candidate_freq_hz=psd_result['metrics'].get('psd_dom_all_freq_hz'),
                    psd_candidate_freqs_hz=_json_metric_list(psd_result['metrics'].get('psd_top_peaks_freq_hz')),
                    min_peak_distance_s=params.get('acf_min_peak_distance_s'),
                    min_peak_prominence=params.get('acf_min_peak_prominence'),
                    near_zero_exclude_s=params.get('acf_near_zero_exclude_s'),
                    strong_peak_height=params.get('acf_strong_peak_height'),
                    strong_peak_prominence=params.get('acf_strong_peak_prominence'),
                )
                metrics = {
                    key: _clean_metric_value(value)
                    for key, value in result['metrics'].items()
                }
                acf_metrics = {
                    key: _clean_metric_value(value)
                    for key, value in acf_result['metrics'].items()
                }
                psd_metrics = {
                    key: _clean_metric_value(value)
                    for key, value in psd_result['metrics'].items()
                }
                group_summary_rows.append({
                    'group': group_name,
                    'channel': channel,
                    'file_count': len(series_list),
                    'is_smoke_test': is_smoke_test,
                    **metrics,
                })
                acf_rows.append({'group': group_name, 'channel': channel, 'file_count': len(series_list), 'is_smoke_test': is_smoke_test, **acf_metrics})
                psd_rows.append({'group': group_name, 'channel': channel, 'file_count': len(series_list), 'is_smoke_test': is_smoke_test, **psd_metrics})
            except Exception as exc:
                logger.warning("Group-level NIST summary failed for %s %s: %s", group_name, channel, exc)

    output_dir = Path(output_dir)
    export_nist_metrics_excel(rows, output_dir / 'nist_diagnostics_metrics.xlsx')
    export_nist_file_stability_summary_excel(rows, output_dir / 'nist_file_stability_summary.xlsx')
    export_nist_group_summary_excel(rows, output_dir / 'nist_diagnostics_group_summary.xlsx', summary_rows=group_summary_rows)
    export_acf_group_summary_excel(acf_rows, output_dir / 'acf_group_summary.xlsx')
    export_psd_group_summary_excel(psd_rows, output_dir / 'psd_group_summary.xlsx')
    export_psd_acf_summary_excel(psd_rows, acf_rows, output_dir / 'psd_acf_summary.xlsx')
    export_psd_acf_match_table_excel(acf_rows, output_dir / 'psd_acf_peak_matches.xlsx')
    export_harmonic_matches_long_excel(acf_rows, output_dir / 'harmonic_matches_long.xlsx')
    export_cross_channel_peak_summary_excel(psd_rows, output_dir / 'cross_channel_peak_summary.xlsx')
    export_psd_peaks_long_excel(psd_rows, output_dir / 'psd_peaks_long.xlsx')
    export_acf_peaks_long_excel(acf_rows, output_dir / 'acf_peaks_long.xlsx')
    export_background_subtraction_summary_excel([], output_dir / 'background_subtraction_summary.xlsx')
    if enable_plots:
        _remove_legacy_nist_figure_dirs(output_dir)
    return rows


def _prepare_nist_figure_dirs(output_dir, debug_file_plots):
    """Remove stale NIST figure layouts before writing the current run's plots."""
    figures_dir = Path(output_dir) / 'figures'
    group_dir = figures_dir / 'group_4plot'
    file_dir = figures_dir / 'file_4plot'
    acf_dir = figures_dir / 'acf'
    psd_dir = figures_dir / 'psd'

    for current_dir in (group_dir, file_dir, acf_dir, psd_dir):
        if current_dir.exists():
            shutil.rmtree(current_dir)

    if figures_dir.exists():
        for child in figures_dir.iterdir():
            if child.is_dir() and child.name not in {'group_4plot', 'file_4plot', 'acf', 'psd'}:
                shutil.rmtree(child)

    if not debug_file_plots and file_dir.exists():
        shutil.rmtree(file_dir)


def _json_metric_list(value):
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def _is_smoke_group(group_name):
    lowered = str(group_name).lower()
    return any(token in lowered for token in ('smoke', 'tiny', 'unit', 'debug', 'test'))


def _remove_legacy_nist_figure_dirs(output_dir):
    figures_dir = Path(output_dir) / 'figures'
    if not figures_dir.exists():
        return
    for child in figures_dir.iterdir():
        if child.is_dir() and child.name not in {'group_4plot', 'file_4plot', 'acf', 'psd'}:
            shutil.rmtree(child)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Run NIST 4-plot diagnostics for time-domain background data')
    parser.add_argument('--input', '-i', type=str, default=None, help='Input time CSV file or folder')
    parser.add_argument('--output', '-o', type=str, default=None, help='Output directory')
    parser.add_argument('--no-plots', action='store_true', help='Skip PNG 4-plot generation')
    parser.add_argument('--debug-file-plots', action='store_true', help='Also generate per-file/channel 4-plot PNGs')
    parser.add_argument('--rolling-window-seconds', type=float, default=None)
    parser.add_argument('--max-acf-lag', type=int, default=None)
    parser.add_argument('--max-acf-seconds', type=float, default=None)
    parser.add_argument('--acf-min-peak-distance-s', type=float, default=None)
    parser.add_argument('--acf-min-peak-prominence', type=float, default=None)
    parser.add_argument('--acf-near-zero-exclude-s', type=float, default=None)
    parser.add_argument('--min-period-s', type=float, default=None)
    parser.add_argument('--acf-strong-peak-height', type=float, default=None)
    parser.add_argument('--acf-strong-peak-prominence', type=float, default=None)
    parser.add_argument('--centered-plot', action='store_true', help='Show run sequence as x - median')
    parser.add_argument('--centered-plot-mv', action='store_true', help='Show centered run sequence in mV')
    parser.add_argument('--welch-nperseg', type=int, default=None)
    parser.add_argument('--low-freq-nperseg', type=int, default=None)
    parser.add_argument('--psd-exclude-low-hz', type=float, default=None)
    parser.add_argument('--max-psd-period-refs', type=int, default=1)
    parser.add_argument('--max-files', type=int, default=None, help='Limit files per group for debug runs')
    args = parser.parse_args(argv)

    config = load_config()
    input_path = Path(args.input or config['tdms_reader_time_output_dir'])
    csv_groups = collect_csv_groups(input_path)
    if not csv_groups:
        logger.warning("No CSV files found for NIST diagnostics: %s", input_path)
        return []

    params = {
        'window_seconds': args.rolling_window_seconds,
        'max_acf_lag': args.max_acf_lag,
        'max_acf_seconds': args.max_acf_seconds,
        'acf_min_peak_distance_s': args.acf_min_peak_distance_s,
        'acf_min_peak_prominence': args.acf_min_peak_prominence,
        'acf_near_zero_exclude_s': args.min_period_s if args.min_period_s is not None else args.acf_near_zero_exclude_s,
        'acf_strong_peak_height': args.acf_strong_peak_height,
        'acf_strong_peak_prominence': args.acf_strong_peak_prominence,
        'centered_plot': args.centered_plot,
        'millivolt_centered_plot': args.centered_plot_mv,
        'welch_nperseg': args.welch_nperseg,
        'low_freq_nperseg': args.low_freq_nperseg,
        'psd_exclude_low_hz': args.psd_exclude_low_hz,
        'max_psd_period_refs': args.max_psd_period_refs,
    }
    all_rows = []
    for group_dir, input_files in csv_groups:
        if args.max_files is not None:
            input_files = input_files[:args.max_files]
        output_dir = Path(args.output) if args.output and len(csv_groups) == 1 else derive_nist_diagnostics_output_dir(group_dir, config)
        logger.info("Running NIST diagnostics for %s files in %s", len(input_files), group_dir)
        rows = process_nist_group(
            input_files,
            group_dir,
            output_dir,
            params,
            enable_plots=not args.no_plots,
            debug_file_plots=args.debug_file_plots,
        )
        all_rows.extend(rows)

    logger.info("NIST diagnostics complete: %s rows", len(all_rows))
    return all_rows


if __name__ == "__main__":
    main()
