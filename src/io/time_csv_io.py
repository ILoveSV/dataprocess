from pathlib import Path
import logging

import pandas as pd

from src.utils.perf_timing import add_counter, timed_step


logger = logging.getLogger('data_process')

EXCLUDED_INPUT_NAMES = {
    'quality_assessment.csv',
    'quality_assessment_table.csv',
    'quality_assessment.xlsx',
    'time_series_metrics.xlsx',
    'time_series_group_summary.xlsx',
}


def read_csv_data(csv_file_path):
    """Read one time-domain CSV and return detected channel columns."""
    try:
        logger.info("Reading CSV file: %s", csv_file_path)

        try:
            with timed_step('timeplots.csv_read', file=Path(csv_file_path).name):
                df = pd.read_csv(csv_file_path)
        except Exception as exc:
            logger.warning("Default CSV reader failed, retrying with python engine: %s", exc)
            with timed_step('timeplots.csv_read_python_engine', file=Path(csv_file_path).name):
                df = pd.read_csv(csv_file_path, engine='python')

        time_column = 'time'
        channel_columns = [col for col in df.columns if str(col).startswith('channel')]

        if time_column not in df.columns:
            raise ValueError("CSV file is missing required 'time' column")
        if not channel_columns:
            raise ValueError("CSV file has no columns starting with 'channel'")

        logger.info("Read %s rows and %s channels", len(df), len(channel_columns))
        add_counter('timeplots.input_files', 1)
        add_counter('timeplots.input_rows', len(df))
        return df, time_column, channel_columns

    except Exception as exc:
        logger.error("Failed to read CSV file %s: %s", csv_file_path, exc)
        raise


def read_csv_header(csv_file_path):
    """Read only the header row and return detected time/channel columns."""
    csv_file_path = Path(csv_file_path)
    with timed_step('timeplots.csv_header_read', file=csv_file_path.name):
        df = pd.read_csv(csv_file_path, nrows=0)
    time_column = 'time'
    channel_columns = [col for col in df.columns if str(col).startswith('channel')]
    if time_column not in df.columns:
        raise ValueError("CSV file is missing required 'time' column")
    if not channel_columns:
        raise ValueError("CSV file has no columns starting with 'channel'")
    return time_column, channel_columns


def collect_csv_files(input_path):
    """Collect direct CSV files from a file or directory."""
    input_path = Path(input_path)
    if input_path.is_file():
        return [] if input_path.name in EXCLUDED_INPUT_NAMES else [input_path]
    return sorted(
        csv_file for csv_file in input_path.glob('*.csv')
        if csv_file.name not in EXCLUDED_INPUT_NAMES
    )


def collect_csv_groups(input_path):
    """Return one CSV group per folder that should produce one workbook."""
    input_path = Path(input_path)
    with timed_step('timeplots.file_scan', folder=input_path):
        if input_path.is_file():
            return [(input_path.parent, [input_path])]

        direct_files = collect_csv_files(input_path)
        if direct_files:
            return [(input_path, direct_files)]

        grouped = {}
        for csv_file in sorted(input_path.glob('**/*.csv')):
            if csv_file.name in EXCLUDED_INPUT_NAMES:
                continue
            grouped.setdefault(csv_file.parent, []).append(csv_file)

        return sorted(grouped.items(), key=lambda item: str(item[0]))


def safe_sheet_name(name, used_names):
    """Create an Excel-compatible unique sheet name."""
    cleaned = ''.join(ch if ch not in r'[]:*?/\\' else '_' for ch in str(name))
    cleaned = cleaned[:31] or 'sheet'
    candidate = cleaned
    suffix = 1
    while candidate in used_names:
        suffix_text = f"_{suffix}"
        candidate = f"{cleaned[:31 - len(suffix_text)]}{suffix_text}"
        suffix += 1
    used_names.add(candidate)
    return candidate
