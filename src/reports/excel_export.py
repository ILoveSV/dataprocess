from pathlib import Path
import logging

import pandas as pd

from src.features.time_metrics import METRIC_NAMES
from src.io.time_csv_io import safe_sheet_name
from src.summaries.time_group_summary import (
    GROUP_SUMMARY_COLUMNS,
    summarize_data_completeness,
    summarize_group_metrics,
)
from src.utils.perf_timing import add_counter, record_file_size, timed_step


logger = logging.getLogger('data_process')


def export_to_excel(channel_rows, output_path):
    """Export per-file metrics to Excel, with one sheet per channel."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    columns = ['file'] + METRIC_NAMES
    used_sheet_names = set()
    with timed_step('timeplots.excel_write', file=output_path.name):
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            for channel, rows in channel_rows.items():
                df = pd.DataFrame(rows, columns=columns)
                sheet_name = safe_sheet_name(channel, used_sheet_names)
                df.to_excel(writer, sheet_name=sheet_name, index=False)
    add_counter('timeplots.output_files', 1)
    record_file_size(output_path, 'timeplots.output_bytes')

    logger.info("Metric summary exported to: %s", output_path)
    return output_path


def export_group_summary_excel(channel_rows, group_dir, output_path):
    """Export group-level summaries to one sheet, one row per channel."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    summary = summarize_group_metrics(channel_rows, group_dir)
    rows = []
    for channel, row in summary.items():
        rows.append({'channel': channel, **row})

    df = pd.DataFrame(rows, columns=GROUP_SUMMARY_COLUMNS)
    with timed_step('timeplots.excel_write', file=output_path.name):
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='group_summary', index=False)
            worksheet = writer.sheets['group_summary']
            for column_cells in worksheet.columns:
                max_length = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
                worksheet.column_dimensions[column_cells[0].column_letter].width = min(max_length + 2, 24)
    add_counter('timeplots.output_files', 1)
    record_file_size(output_path, 'timeplots.output_bytes')

    logger.info("Group summary workbook exported to: %s", output_path)
    return output_path


def export_data_completeness_excel(channel_rows, group_dir, output_path):
    """Export per group/channel data completeness summary."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(summarize_data_completeness(channel_rows, group_dir))
    with timed_step('timeplots.excel_write', file=output_path.name):
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='data_completeness', index=False)
    add_counter('timeplots.output_files', 1)
    record_file_size(output_path, 'timeplots.output_bytes')
    logger.info("Data completeness workbook exported to: %s", output_path)
    return output_path
