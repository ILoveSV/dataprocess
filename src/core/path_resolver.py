from pathlib import Path
import logging


logger = logging.getLogger('data_process')


def resolve_scan_folder(base_dir, data_folder=None):
    """Resolve scan folder; support absolute or relative data_folder."""
    base_path = Path(base_dir).resolve()
    if not data_folder:
        return str(base_path)

    selected_path = Path(data_folder)
    if not selected_path.is_absolute():
        selected_path = base_path / selected_path
    selected_path = selected_path.resolve()

    if not selected_path.exists():
        logger.error("data folder does not exist: %s", selected_path)
        return None
    if not selected_path.is_dir():
        logger.error("data folder is not a directory: %s", selected_path)
        return None

    return str(selected_path)


def resolve_processed_scan_folder(input_root, raw_data_dir, data_folder=None):
    """Map raw data-folder selections to a matching processed output folder."""
    if not data_folder:
        return input_root

    raw_path = Path(raw_data_dir).resolve()
    input_path = Path(input_root).resolve()
    data_path = Path(data_folder).resolve()

    try:
        if data_path == raw_path or data_path.is_relative_to(raw_path):
            relative = data_path.relative_to(raw_path) if data_path != raw_path else Path('.')
            return str(input_path / relative)
    except AttributeError:
        try:
            relative = data_path.relative_to(raw_path)
            return str(input_path / relative)
        except ValueError:
            pass
    except ValueError:
        pass

    return str(data_path)


def derive_output_path(input_path, config):
    """Map process/time input paths to the configured results/time folder."""
    input_path = Path(input_path)
    results_dir = Path(config.get('time_series_results_dir', 'results/time'))
    process_dir = Path(config.get('tdms_reader_time_output_dir', '')).parent

    source_dir = input_path.parent if input_path.is_file() else input_path

    output_dir = results_dir
    try:
        relative_dir = source_dir.resolve().relative_to(process_dir.resolve())
        output_dir = results_dir.parent / relative_dir
    except (ValueError, OSError):
        output_dir = results_dir

    return output_dir / 'time_series_metrics.xlsx'


def derive_summary_path(metrics_output_path):
    """Return the group summary workbook path next to the per-file metrics workbook."""
    return Path(metrics_output_path).with_name('time_series_group_summary.xlsx')


def derive_nist_diagnostics_output_dir(input_path, config):
    """Map process/time input paths to results/<date>/nist_diagnostics/<relative_group>."""
    input_path = Path(input_path)
    time_root = Path(config.get('tdms_reader_time_output_dir', ''))
    time_results_dir = Path(config.get('time_series_results_dir', 'results/time'))
    nist_root = time_results_dir.parent / 'nist_diagnostics'

    source_dir = input_path.parent if input_path.is_file() else input_path
    try:
        relative_dir = source_dir.resolve().relative_to(time_root.resolve())
        return nist_root / relative_dir
    except (ValueError, OSError):
        return nist_root / source_dir.name
