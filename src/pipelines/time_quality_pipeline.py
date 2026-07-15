import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from src.core.config_loader import load_config
from src.core.path_resolver import derive_output_path, derive_summary_path
from src.features.time_metrics import METRIC_NAMES, calculate_file_metrics
from src.io.time_csv_io import collect_csv_groups, read_csv_data, read_csv_header
from src.reports.excel_export import export_data_completeness_excel, export_group_summary_excel, export_to_excel
from src.utils.perf_timing import add_counter, timed_step
from src.utils.cache_utils import build_cache_metadata, is_cache_hit, write_cache_metadata
from src.summaries.time_group_summary import GROUP_SUMMARY_COLUMNS, summarize_data_completeness, summarize_group_metrics


logger = logging.getLogger('data_process')


def process_files(csv_files, channel_columns):
    """Process every CSV and build one table per channel."""
    channel_rows = {channel: [] for channel in channel_columns}

    for csv_file in csv_files:
        file_name = Path(csv_file).name
        try:
            df, time_column, _ = read_csv_data(csv_file)
            time_values = df[time_column].values

            for channel in channel_columns:
                row = {'file': file_name}
                if channel in df.columns:
                    with timed_step('timeplots.metric_compute', file=file_name, channel=channel):
                        metrics = calculate_file_metrics(df[channel].values, time_values=time_values)
                    if metrics is None:
                        metrics = {metric: np.nan for metric in METRIC_NAMES}
                else:
                    metrics = {metric: np.nan for metric in METRIC_NAMES}

                row.update(metrics)
                channel_rows[channel].append(row)

        except Exception as exc:
            logger.warning("Failed to process file %s: %s", csv_file, exc)
            for channel in channel_columns:
                row = {'file': file_name}
                row.update({metric: np.nan for metric in METRIC_NAMES})
                channel_rows[channel].append(row)

    return channel_rows


def main(argv=None):
    """Entry point for time-domain metric summary export."""
    try:
        parser = argparse.ArgumentParser(description='Export time-domain file metrics by channel')
        parser.add_argument('--input', '-i', type=str, default=None, help='Input CSV file or folder')
        parser.add_argument('--output', '-o', type=str, default=None, help='Output file path')
        parser.add_argument('--export-excel', action='store_true')
        parser.add_argument('--force', action='store_true')
        parser.add_argument('--skip-existing', dest='skip_existing', action='store_true', default=True)
        parser.add_argument('--no-skip-existing', dest='skip_existing', action='store_false')
        args = parser.parse_args(argv)

        with timed_step('timeplots.module_total'):
            config = load_config()
            input_path = Path(args.input or config['tdms_reader_time_output_dir'])
            csv_groups = collect_csv_groups(input_path)

            if not csv_groups:
                logger.warning("No CSV files found: %s", input_path)
                return None

            output_paths = []
            for group_dir, input_files in csv_groups:
                logger.info("Processing %s CSV files in %s", len(input_files), group_dir)
                add_counter('timeplots.discovered_files', len(input_files))

                if args.output and len(csv_groups) == 1:
                    output_path = Path(args.output)
                else:
                    output_path = derive_output_path(group_dir, config)
                    if not args.export_excel:
                        output_path = output_path.with_suffix('.csv')

                if args.export_excel:
                    expected_outputs = [
                        output_path,
                        derive_summary_path(output_path),
                        Path(output_path).with_name('data_completeness_summary.xlsx'),
                    ]
                else:
                    expected_outputs = [
                        output_path,
                        output_path.with_name('time_series_group_summary.csv'),
                        output_path.with_name('data_completeness_summary.csv'),
                    ]
                params = {
                    'stage': 'timeplots',
                    'export_excel': args.export_excel,
                    'output_format': 'xlsx' if args.export_excel else 'csv',
                    'metric_names': METRIC_NAMES,
                }
                metadata_path = output_path.parent / '.cache' / 'timeplots_cache.json'
                hit, reason = is_cache_hit(
                    'timeplots',
                    input_files,
                    expected_outputs,
                    params,
                    metadata_path,
                    force=args.force,
                    skip_existing=args.skip_existing,
                )
                if hit:
                    output_paths.append(output_path)
                    continue

                _, channel_columns = read_csv_header(input_files[0])
                channel_rows = process_files(input_files, channel_columns)

                if args.export_excel:
                    try:
                        export_group_summary_excel(channel_rows, group_dir, derive_summary_path(output_path))
                        export_data_completeness_excel(
                            channel_rows,
                            group_dir,
                            Path(output_path).with_name('data_completeness_summary.xlsx'),
                        )
                    except PermissionError as exc:
                        logger.warning("Could not update group summary workbook because it is locked: %s", exc)
                    try:
                        export_to_excel(channel_rows, output_path)
                    except PermissionError as exc:
                        logger.warning("Could not update Excel file because it is locked: %s", exc)
                else:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    rows = []
                    for channel, channel_data in channel_rows.items():
                        for row in channel_data:
                            rows.append({'channel': channel, **row})
                    pd.DataFrame(rows).to_csv(output_path, index=False, encoding='utf-8-sig')
                    summary = summarize_group_metrics(channel_rows, group_dir)
                    summary_rows = [{'channel': channel, **row} for channel, row in summary.items()]
                    pd.DataFrame(summary_rows, columns=GROUP_SUMMARY_COLUMNS).to_csv(
                        output_path.with_name('time_series_group_summary.csv'),
                        index=False,
                        encoding='utf-8-sig',
                    )
                    pd.DataFrame(summarize_data_completeness(channel_rows, group_dir)).to_csv(
                        output_path.with_name('data_completeness_summary.csv'),
                        index=False,
                        encoding='utf-8-sig',
                    )
                write_cache_metadata(
                    metadata_path,
                    build_cache_metadata('timeplots', input_files, expected_outputs, params, input_dir=group_dir, output_dir=output_path.parent),
                )
                output_paths.append(output_path)

            logger.info(
                "Time-domain metric summary complete: %s groups, %s files",
                len(csv_groups),
                sum(len(files) for _, files in csv_groups),
            )
            return output_paths

    except Exception as exc:
        logger.error("Time-domain metric summary failed: %s", exc)
        import traceback
        logger.error(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
