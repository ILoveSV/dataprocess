import argparse
import json
import logging
import math
import os
from concurrent.futures import ProcessPoolExecutor
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from nptdms import TdmsFile

from src.core.config_loader import load_config
from src.core.constants import FILE_DURATION
from src.core.path_resolver import resolve_scan_folder
from src.utils.perf_timing import add_counter, record_file_size, timed_step


logger = logging.getLogger("data_process")


def segment_bounds(total_samples, sampling_interval, segment_seconds, min_segment_seconds=0.0):
    """Return sample ranges for splitting one continuous TDMS acquisition."""
    if total_samples <= 0:
        return []
    if sampling_interval <= 0:
        raise ValueError(f"Invalid sampling_interval: {sampling_interval}")
    if segment_seconds <= 0:
        raise ValueError(f"Invalid segment_seconds: {segment_seconds}")

    samples_per_segment = max(1, int(round(segment_seconds / sampling_interval)))
    min_samples = max(1, int(math.ceil(min_segment_seconds / sampling_interval))) if min_segment_seconds > 0 else 1

    bounds = []
    for start in range(0, total_samples, samples_per_segment):
        stop = min(start + samples_per_segment, total_samples)
        if stop - start >= min_samples:
            bounds.append((start, stop))
    return bounds


def _as_python_datetime(value):
    if hasattr(value, "astype"):
        return value.astype("M8[us]").astype("O")
    return value


def _read_channel_info(tdms_path):
    tdms_file = TdmsFile.read_metadata(tdms_path)
    groups = tdms_file.groups()
    if not groups:
        raise ValueError("TDMS file has no groups")

    group = groups[0]
    channels = list(group.channels())
    if not channels:
        raise ValueError("TDMS file has no channels in first group")

    lengths = [len(ch) for ch in channels]
    if min(lengths) != max(lengths):
        raise ValueError(f"TDMS channels have different lengths: {lengths}")

    first = channels[0]
    sampling_interval = float(first.properties["wf_increment"])
    sampling_rate_hz = 1.0 / sampling_interval
    start_time = _as_python_datetime(first.properties["wf_start_time"])
    channel_names = {
        f"channel{i + 1}": ch.properties.get("NI_ChannelName", ch.name)
        for i, ch in enumerate(channels)
    }
    channel_paths = [(group.name, ch.name) for ch in channels]

    return {
        "group_name": group.name,
        "channel_paths": channel_paths,
        "channel_names": channel_names,
        "data_length": lengths[0],
        "num_channels": len(channels),
        "sampling_interval": sampling_interval,
        "sampling_rate_hz": sampling_rate_hz,
        "start_time": start_time,
    }


def _segment_filename(segment_start_time, segment_index):
    stamp = segment_start_time.strftime("%Y%m%d%H%M%S.%f")
    return f"{stamp}_seg{segment_index:04d}.csv"


def _write_segment_csv(tdms_file, channel_paths, start, stop, sampling_interval, output_path):
    segment_len = stop - start
    time_values = np.arange(segment_len, dtype=float) * sampling_interval
    data = {"time": [f"{value:.9f}" for value in time_values]}

    for idx, (group_name, channel_name) in enumerate(channel_paths, start=1):
        data[f"channel{idx}"] = tdms_file[group_name][channel_name][start:stop]

    df = pd.DataFrame(data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig", float_format="%.9f")
    return segment_len


def _write_metadata(metadata_path, metadata):
    with open(metadata_path, "w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=2, ensure_ascii=False)


def _segment_complete(output_path, metadata_path, expected_rows):
    if not output_path.exists() or not metadata_path.exists():
        return False
    if output_path.stat().st_size <= 0 or metadata_path.stat().st_size <= 0:
        return False
    try:
        with open(metadata_path, "r", encoding="utf-8") as file:
            metadata = json.load(file)
    except (OSError, json.JSONDecodeError):
        return False
    return (
        metadata.get("source_mode") == "merged_tdms_segment"
        and int(metadata.get("data_length", -1)) == int(expected_rows)
    )


def process_merged_tdms_file(
    tdms_path,
    output_base_dir,
    raw_data_dir,
    segment_seconds=FILE_DURATION,
    min_segment_seconds=0.0,
    max_segments_per_file=None,
    skip_existing=True,
):
    """Split one merged TDMS file into legacy-compatible time CSV files."""
    tdms_path = Path(tdms_path)
    output_base_dir = Path(output_base_dir)
    raw_data_dir = Path(raw_data_dir)

    try:
        with timed_step("merged_timedata.tdms_metadata_read", file=tdms_path.name):
            info = _read_channel_info(str(tdms_path))

        bounds = segment_bounds(
            info["data_length"],
            info["sampling_interval"],
            segment_seconds,
            min_segment_seconds=min_segment_seconds,
        )
        if max_segments_per_file is not None and max_segments_per_file > 0:
            bounds = bounds[: int(max_segments_per_file)]
        add_counter("merged_timedata.input_files", 1)
        add_counter("merged_timedata.output_segments_planned", len(bounds))

        relative_dir = tdms_path.parent.resolve().relative_to(raw_data_dir.resolve())
        output_dir = output_base_dir / relative_dir

        logger.info(
            "Splitting merged TDMS %s into %s segments of %.6g s",
            tdms_path.name,
            len(bounds),
            segment_seconds,
        )

        with TdmsFile.open(str(tdms_path)) as tdms_file:
            for segment_index, (start, stop) in enumerate(bounds, start=1):
                segment_start = info["start_time"] + timedelta(seconds=start * info["sampling_interval"])
                output_path = output_dir / _segment_filename(segment_start, segment_index)
                metadata_path = output_path.with_name(output_path.stem + "_metadata.json")
                expected_rows = stop - start

                if skip_existing and _segment_complete(output_path, metadata_path, expected_rows):
                    logger.info(
                        "RESUME merged_timedata skip existing segment file=%s segment=%s/%s rows=%s",
                        output_path.name,
                        segment_index,
                        len(bounds),
                        expected_rows,
                    )
                    add_counter("merged_timedata.output_segments_skipped", 1)
                    continue

                with timed_step(
                    "merged_timedata.segment_csv_write",
                    file=output_path.name,
                    rows=expected_rows,
                ):
                    rows = _write_segment_csv(
                        tdms_file,
                        info["channel_paths"],
                        start,
                        stop,
                        info["sampling_interval"],
                        output_path,
                    )

                metadata = {
                    "filename": tdms_path.name,
                    "source_tdms_path": str(tdms_path),
                    "source_mode": "merged_tdms_segment",
                    "segment_index": segment_index,
                    "segment_count": len(bounds),
                    "segment_start_sample": start,
                    "segment_stop_sample_exclusive": stop,
                    "start_time": segment_start.isoformat(),
                    "sampling_interval_seconds": info["sampling_interval"],
                    "sampling_rate_hz": info["sampling_rate_hz"],
                    "data_length": rows,
                    "total_duration_seconds": round(rows * info["sampling_interval"], 10),
                    "num_channels": info["num_channels"],
                    "channel_names": info["channel_names"],
                }
                _write_metadata(metadata_path, metadata)

                add_counter("merged_timedata.output_files", 2)
                add_counter("merged_timedata.output_rows", rows)
                record_file_size(output_path, "merged_timedata.output_bytes")
                record_file_size(metadata_path, "merged_timedata.output_bytes")

    except Exception as exc:
        logger.error("Failed to process merged TDMS %s: %s", tdms_path, exc)
        import traceback

        logger.error(traceback.format_exc())


def process_merged_tdms_file_wrapper(args):
    from src.utils.logging_utils import setup_logging

    tdms_path, output_base_dir, raw_data_dir, segment_seconds, min_segment_seconds, max_segments_per_file, skip_existing = args
    project_root = Path(__file__).resolve().parent.parent.parent
    log_config_path = project_root / "config" / "logging.yaml"
    if log_config_path.exists():
        setup_logging(log_config_path)
    return process_merged_tdms_file(
        tdms_path,
        output_base_dir,
        raw_data_dir,
        segment_seconds=segment_seconds,
        min_segment_seconds=min_segment_seconds,
        max_segments_per_file=max_segments_per_file,
        skip_existing=skip_existing,
    )


def process_merged_tdms_files_parallel(
    tdms_files,
    output_base_dir,
    raw_data_dir,
    segment_seconds=FILE_DURATION,
    min_segment_seconds=0.0,
    max_segments_per_file=None,
    skip_existing=True,
    max_workers=None,
):
    workers = max_workers or min(os.cpu_count() or 1, max(1, len(tdms_files)))
    logger.info("TIMING merged_timedata.workers count=%s files=%s", workers, len(tdms_files))
    params = [
        (tdms_file, output_base_dir, raw_data_dir, segment_seconds, min_segment_seconds)
        + (max_segments_per_file, skip_existing)
        for tdms_file in tdms_files
    ]
    with ProcessPoolExecutor(max_workers=workers) as executor:
        list(executor.map(process_merged_tdms_file_wrapper, params))


def collect_tdms_files(scan_folder):
    scan_folder = Path(scan_folder)
    with timed_step("merged_timedata.file_scan", folder=str(scan_folder)):
        return sorted(str(path) for path in scan_folder.rglob("*.tdms"))


def run(
    input_path=None,
    output_path=None,
    data_folder=None,
    segment_seconds=FILE_DURATION,
    min_segment_seconds=0.0,
    max_segments_per_file=None,
    skip_existing=True,
    max_workers=None,
):
    config = load_config()
    raw_data_dir = input_path or config["raw_data_dir"]
    output_base_dir = output_path or config["tdms_reader_time_output_dir"]
    scan_folder = resolve_scan_folder(raw_data_dir, data_folder)
    if not scan_folder:
        return

    logger.info("Merged TDMS input root: %s", raw_data_dir)
    logger.info("Merged TDMS scan folder: %s", scan_folder)
    logger.info("Merged TDMS output root: %s", output_base_dir)

    tdms_files = collect_tdms_files(scan_folder)
    add_counter("merged_timedata.input_files_found", len(tdms_files))
    if not tdms_files:
        logger.warning("No TDMS files found in %s", scan_folder)
        return

    process_merged_tdms_files_parallel(
        tdms_files,
        output_base_dir,
        raw_data_dir,
        segment_seconds=segment_seconds,
        min_segment_seconds=min_segment_seconds,
        max_segments_per_file=max_segments_per_file,
        skip_existing=skip_existing,
        max_workers=max_workers,
    )
    logger.info("Merged TDMS split export completed")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Split merged TDMS files into legacy time CSV segments.")
    parser.add_argument("--input", dest="input_path", default=None)
    parser.add_argument("--output", dest="output_path", default=None)
    parser.add_argument("--data-folder", default=None)
    parser.add_argument("--segment-seconds", type=float, default=FILE_DURATION)
    parser.add_argument("--min-segment-seconds", type=float, default=0.0)
    parser.add_argument("--max-segments-per-file", type=int, default=None)
    parser.add_argument("--max-workers", type=int, default=None)
    parser.add_argument("--skip-existing", dest="skip_existing", action="store_true", default=True)
    parser.add_argument("--no-skip-existing", dest="skip_existing", action="store_false")
    args = parser.parse_args(argv)

    run(
        input_path=args.input_path,
        output_path=args.output_path,
        data_folder=args.data_folder,
        segment_seconds=args.segment_seconds,
        min_segment_seconds=args.min_segment_seconds,
        max_segments_per_file=args.max_segments_per_file,
        skip_existing=args.skip_existing,
        max_workers=args.max_workers,
    )


if __name__ == "__main__":
    main()
