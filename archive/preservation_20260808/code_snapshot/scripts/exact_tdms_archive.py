"""Full-coverage, reusable TDMS analysis archive.

The archive is intentionally larger than the experiment-specific caches. It
retains anti-aliased low-rate traces, full-coverage Welch summaries, temporal
band powers, dominant-line tracks, block envelopes, health statistics, and
centered raw snippets so the original multi-gigabyte TDMS file is not needed
for the analyses currently used by this project.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from nptdms import TdmsFile
from scipy import signal


ARCHIVE_VERSION = 4
BAND_NAMES = ("5_100hz", "100_1khz", "1_20khz", "20_80khz", "80_200khz")
BAND_LIMITS = ((5.0, 100.0), (100.0, 1_000.0), (1_000.0, 20_000.0),
               (20_000.0, 80_000.0), (80_000.0, 199_900.0))


@dataclass(frozen=True)
class ExactArchiveConfig:
    trim_start_seconds: float = 15.0
    trim_end_seconds: float = 5.0
    block_seconds: float = 0.1
    subblock_seconds: float = 0.001
    welch_nperseg: int = 262_144
    welch_overlap_fraction: float = 0.5
    low_rate_hz: float = 4_000.0
    analysis_rate_hz: float = 10.0
    lowpass_pass_hz: float = 1_800.0
    lowpass_stop_hz: float = 2_000.0
    lowpass_pass_ripple_db: float = 0.05
    lowpass_stop_attenuation_db: float = 100.0
    snippet_seconds: float = 1.0
    snippet_centers: tuple[float, ...] = (0.20, 0.50, 0.80)
    peak_count_per_segment: int = 64
    welch_epoch_count: int = 8


def _json_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, np.generic):
        return _json_value(value.item())
    if isinstance(value, np.ndarray):
        return [_json_value(item) for item in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return str(value)


def _one_sided_psd(values: np.ndarray, sample_rate: float, window: np.ndarray) -> np.ndarray:
    detrended = signal.detrend(values, axis=0, type="linear")
    transformed = np.fft.rfft(detrended * window[:, None], axis=0)
    power = np.abs(transformed) ** 2 / (sample_rate * np.sum(window * window))
    power[1:-1] *= 2.0
    return power


def _integrated_bandpowers(frequency: np.ndarray, psd: np.ndarray) -> np.ndarray:
    values = []
    for low, high in BAND_LIMITS:
        use = (frequency >= low) & (frequency < high)
        values.append(np.trapz(psd[use], frequency[use], axis=0))
    return np.stack(values, axis=-1)


def _filter_initial_state(sos: np.ndarray, first_row: np.ndarray) -> np.ndarray:
    steady = signal.sosfilt_zi(sos)
    return steady[:, :, None] * first_row[None, None, :]


def _save_centered_snippets(path: Path, snippets: np.ndarray, starts: np.ndarray,
                            sample_rate: float) -> None:
    offsets = snippets[:, :1, :].copy()
    centered = (snippets - offsets).astype(np.float32)
    np.savez_compressed(
        path,
        centered_v=centered,
        offset_v=offsets[:, 0, :],
        start_sample=starts,
        sample_rate_hz=sample_rate,
    )


def archive_complete(path: Path) -> bool:
    required = (
        "metadata.json",
        "health.json",
        "low_rate.npz",
        "envelopes.npz",
        "welch.npz",
        "raw_snippets.npz",
        "COMPLETE",
    )
    if not path.is_dir() or not all((path / name).exists() for name in required):
        return False
    try:
        metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return int(metadata.get("archive_version", -1)) == ARCHIVE_VERSION


def validate_exact_archive(path: Path) -> list[str]:
    """Load every retained product and return structural validation errors."""
    if not archive_complete(path):
        return ["archive is incomplete or has the wrong version"]
    problems: list[str] = []
    try:
        metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
        health = json.loads((path / "health.json").read_text(encoding="utf-8"))
        channel_count = len(metadata["channel_names"])
        sample_count = int(metadata["sample_count"])
        config = metadata["config"]
        block_size = int(round(float(config["block_seconds"]) * metadata["sample_rate_hz"]))
        expected_blocks = sample_count // block_size
        if len(health) != channel_count:
            problems.append("health channel count mismatch")

        with np.load(path / "low_rate.npz") as data:
            if data["low_rate_v"].shape[1] != channel_count:
                problems.append("low_rate channel count mismatch")
            if data["analysis_rate_v"].shape != (expected_blocks, channel_count):
                problems.append("analysis_rate shape mismatch")
        with np.load(path / "envelopes.npz") as data:
            for name in (
                "slow_mean", "slow_mean_boxcar", "broadband_rms", "subkhz_rms",
                "fast_residual_rms", "difference_rms",
            ):
                if data[name].shape != (expected_blocks, channel_count):
                    problems.append(f"{name} shape mismatch")
        with np.load(path / "welch.npz") as data:
            frequency_count = len(data["frequency_hz"])
            segment_count = int(metadata["welch"]["segment_count"])
            epoch_count = int(metadata["welch"]["epoch_count"])
            if data["psd_mean"].shape != (channel_count, frequency_count):
                problems.append("mean PSD shape mismatch")
            if data["epoch_psd_mean"].shape != (
                epoch_count, channel_count, frequency_count
            ):
                problems.append("epoch PSD shape mismatch")
            if data["segment_bandpower"].shape != (
                segment_count, channel_count, len(BAND_NAMES)
            ):
                problems.append("segment bandpower shape mismatch")
            for name in ("psd_mean", "epoch_psd_mean", "segment_bandpower"):
                if not np.all(np.isfinite(data[name])):
                    problems.append(f"{name} contains non-finite values")
        with np.load(path / "raw_snippets.npz") as data:
            if data["centered_v"].shape[2] != channel_count:
                problems.append("raw snippet channel count mismatch")
            if not np.all(np.isfinite(data["centered_v"])):
                problems.append("raw snippets contain non-finite values")
    except (OSError, ValueError, KeyError, IndexError) as error:
        problems.append(f"archive load failed: {error}")
    return problems


def build_exact_archive(tdms_path: Path, output: Path,
                        config: ExactArchiveConfig | None = None) -> None:
    """Read every TDMS sample once and write the reusable analysis archive."""
    config = config or ExactArchiveConfig()
    output.mkdir(parents=True, exist_ok=True)
    complete_marker = output / "COMPLETE"
    if complete_marker.exists():
        complete_marker.unlink()

    with TdmsFile.open(tdms_path) as tdms:
        group = tdms.groups()[0]
        channels = group.channels()
        channel_names = [item.name for item in channels]
        channel_count = len(channels)
        sample_count = len(channels[0])
        sample_rate = 1.0 / float(channels[0].properties["wf_increment"])
        start_time = channels[0].properties.get("wf_start_time")

        block_size = int(round(config.block_seconds * sample_rate))
        subblock_size = int(round(config.subblock_seconds * sample_rate))
        if block_size % subblock_size:
            raise ValueError("Block size must contain whole subblocks")
        low_decimation = int(round(sample_rate / config.low_rate_hz))
        if not np.isclose(sample_rate / low_decimation, config.low_rate_hz, rtol=1e-9):
            raise ValueError("Raw sample rate is not an integer multiple of low_rate_hz")
        analysis_decimation = int(round(config.low_rate_hz / config.analysis_rate_hz))
        if not np.isclose(config.low_rate_hz / analysis_decimation,
                          config.analysis_rate_hz, rtol=1e-9):
            raise ValueError("low_rate_hz is not an integer multiple of analysis_rate_hz")

        stable_start = int(round(config.trim_start_seconds * sample_rate))
        stable_end = sample_count - int(round(config.trim_end_seconds * sample_rate))
        if stable_end - stable_start < config.welch_nperseg:
            raise ValueError("Stable interval is shorter than one Welch segment")

        filter_order, critical = signal.ellipord(
            config.lowpass_pass_hz,
            config.lowpass_stop_hz,
            config.lowpass_pass_ripple_db,
            config.lowpass_stop_attenuation_db,
            fs=sample_rate,
        )
        lowpass_sos = signal.ellip(
            filter_order,
            config.lowpass_pass_ripple_db,
            config.lowpass_stop_attenuation_db,
            critical,
            btype="lowpass",
            fs=sample_rate,
            output="sos",
        )
        dc_gain = abs(signal.sosfreqz(lowpass_sos, worN=np.array([0.0]), fs=sample_rate)[1][0])
        lowpass_sos[0, :3] /= dc_gain
        lowpass_state = None

        health = {
            "count": np.zeros(channel_count, dtype=np.int64),
            "sum": np.zeros(channel_count),
            "sumsq": np.zeros(channel_count),
            "minimum": np.full(channel_count, np.inf),
            "maximum": np.full(channel_count, -np.inf),
            "diff_sumsq": np.zeros(channel_count),
            "diff_count": np.zeros(channel_count, dtype=np.int64),
            "flat_diff_count": np.zeros(channel_count, dtype=np.int64),
            "clip_count": np.zeros(channel_count, dtype=np.int64),
            "nonfinite_count": np.zeros(channel_count, dtype=np.int64),
        }
        previous_row: np.ndarray | None = None

        block_buffer = np.empty((0, channel_count))
        envelope_lists = {name: [] for name in (
            "slow_mean_boxcar",
            "broadband_rms",
            "subkhz_rms",
            "fast_residual_rms",
            "difference_rms",
        )}
        low_rate_parts: list[np.ndarray] = []
        low_rate_indices: list[np.ndarray] = []

        nperseg = config.welch_nperseg
        step = int(round(nperseg * (1.0 - config.welch_overlap_fraction)))
        if step <= 0:
            raise ValueError("Welch overlap leaves a non-positive step")
        window = signal.windows.hann(nperseg, sym=False)
        frequency = np.fft.rfftfreq(nperseg, 1.0 / sample_rate)
        psd_sum = np.zeros((len(frequency), channel_count))
        epoch_psd_sum = np.zeros(
            (config.welch_epoch_count, len(frequency), channel_count),
            dtype=np.float64,
        )
        epoch_segment_count = np.zeros(config.welch_epoch_count, dtype=np.int64)
        segment_starts: list[int] = []
        segment_bandpowers: list[np.ndarray] = []
        segment_peak_frequency: list[np.ndarray] = []
        segment_peak_power: list[np.ndarray] = []
        welch_buffer = np.empty((0, channel_count))
        welch_buffer_start: int | None = None
        welch_tail = np.empty((0, channel_count))

        snippet_length = int(round(config.snippet_seconds * sample_rate))
        snippet_starts = np.array([
            int(round(center * sample_count - snippet_length / 2))
            for center in config.snippet_centers
        ], dtype=np.int64)
        snippet_starts = np.clip(snippet_starts, 0, sample_count - snippet_length)
        snippets = np.full(
            (len(snippet_starts), snippet_length, channel_count),
            np.nan,
            dtype=np.float64,
        )

        peak_use = np.where((frequency >= 1_000.0) & (frequency <= 199_500.0))[0]
        peak_count = min(config.peak_count_per_segment, len(peak_use))

        def process_welch_segment(values: np.ndarray, start_sample: int) -> None:
            nonlocal psd_sum, epoch_psd_sum, epoch_segment_count
            current = _one_sided_psd(values, sample_rate, window)
            psd_sum += current
            center_sample = start_sample + nperseg / 2.0
            epoch_fraction = (center_sample - stable_start) / (stable_end - stable_start)
            epoch_index = min(
                config.welch_epoch_count - 1,
                max(0, int(np.floor(epoch_fraction * config.welch_epoch_count))),
            )
            epoch_psd_sum[epoch_index] += current
            epoch_segment_count[epoch_index] += 1
            segment_starts.append(start_sample)
            segment_bandpowers.append(_integrated_bandpowers(frequency, current))

            selected = current[peak_use]
            local_indices = np.argpartition(selected, -peak_count, axis=0)[-peak_count:]
            local_power = np.take_along_axis(selected, local_indices, axis=0)
            order = np.argsort(local_power, axis=0)[::-1]
            local_indices = np.take_along_axis(local_indices, order, axis=0)
            local_power = np.take_along_axis(local_power, order, axis=0)
            segment_peak_frequency.append(frequency[peak_use[local_indices]].T)
            segment_peak_power.append(local_power.T)

        expected_offset = 0
        for chunk_index, data_chunk in enumerate(tdms.data_chunks()):
            chunk_group = data_chunk[group.name]
            chunk_channels = chunk_group.channels()
            if not chunk_channels or len(chunk_channels[0]) == 0:
                continue
            chunk_offset = int(chunk_channels[0].offset)
            if chunk_offset != expected_offset:
                raise RuntimeError(
                    f"Non-contiguous TDMS chunks: expected {expected_offset}, got {chunk_offset}"
                )
            matrix = np.column_stack([
                np.asarray(chunk_channel[:], dtype=np.float64)
                for chunk_channel in chunk_channels
            ])
            chunk_end = chunk_offset + len(matrix)
            expected_offset = chunk_end

            finite = np.isfinite(matrix)
            safe = np.where(finite, matrix, 0.0)
            health["nonfinite_count"] += np.sum(~finite, axis=0)
            health["count"] += np.sum(finite, axis=0)
            health["sum"] += np.sum(safe, axis=0)
            health["sumsq"] += np.sum(safe * safe, axis=0)
            health["minimum"] = np.minimum(
                health["minimum"], np.min(np.where(finite, matrix, np.inf), axis=0)
            )
            health["maximum"] = np.maximum(
                health["maximum"], np.max(np.where(finite, matrix, -np.inf), axis=0)
            )
            health["clip_count"] += np.sum(finite & (np.abs(matrix) >= 9.9), axis=0)

            differences = np.diff(
                matrix if previous_row is None else np.vstack((previous_row, matrix)), axis=0
            )
            differences = np.where(np.isfinite(differences), differences, 0.0)
            health["diff_sumsq"] += np.sum(differences * differences, axis=0)
            health["diff_count"] += len(differences)
            health["flat_diff_count"] += np.sum(np.abs(differences) <= 1e-12, axis=0)
            previous_row = matrix[-1:].copy()

            combined = np.vstack((block_buffer, np.nan_to_num(matrix)))
            block_count = len(combined) // block_size
            used = block_count * block_size
            if block_count:
                blocks = combined[:used].reshape(block_count, block_size, channel_count)
                subblocks = blocks.reshape(
                    block_count, block_size // subblock_size, subblock_size, channel_count
                )
                submeans = np.mean(subblocks, axis=2)
                residual = subblocks - submeans[:, :, None, :]
                envelope_lists["slow_mean_boxcar"].append(np.mean(blocks, axis=1))
                envelope_lists["broadband_rms"].append(np.std(blocks, axis=1))
                envelope_lists["subkhz_rms"].append(np.std(submeans, axis=1))
                envelope_lists["fast_residual_rms"].append(
                    np.sqrt(np.mean(residual * residual, axis=(1, 2)))
                )
                envelope_lists["difference_rms"].append(
                    np.sqrt(0.5 * np.mean(np.diff(blocks, axis=1) ** 2, axis=1))
                )
            block_buffer = combined[used:].copy()

            if lowpass_state is None:
                lowpass_state = _filter_initial_state(lowpass_sos, matrix[0])
            filtered, lowpass_state = signal.sosfilt(
                lowpass_sos, np.nan_to_num(matrix), axis=0, zi=lowpass_state
            )
            raw_indices = np.arange(chunk_offset, chunk_end, dtype=np.int64)
            take_low = raw_indices % low_decimation == 0
            low_rate_parts.append(filtered[take_low])
            low_rate_indices.append(raw_indices[take_low])

            overlap_start = max(stable_start, chunk_offset)
            overlap_end = min(stable_end, chunk_end)
            if overlap_end > overlap_start:
                piece = np.nan_to_num(matrix[
                    overlap_start - chunk_offset:overlap_end - chunk_offset
                ])
                if welch_buffer_start is None:
                    welch_buffer_start = overlap_start
                expected_piece_start = welch_buffer_start + len(welch_buffer)
                if overlap_start != expected_piece_start:
                    raise RuntimeError("Stable Welch stream is not contiguous")
                welch_buffer = np.vstack((welch_buffer, piece))
                welch_tail = np.vstack((welch_tail, piece))[-nperseg:]
                while len(welch_buffer) >= nperseg:
                    process_welch_segment(welch_buffer[:nperseg], welch_buffer_start)
                    welch_buffer = welch_buffer[step:].copy()
                    welch_buffer_start += step

            for snippet_index, snippet_start in enumerate(snippet_starts):
                snippet_end = snippet_start + snippet_length
                copy_start = max(snippet_start, chunk_offset)
                copy_end = min(snippet_end, chunk_end)
                if copy_end <= copy_start:
                    continue
                snippets[
                    snippet_index,
                    copy_start - snippet_start:copy_end - snippet_start,
                ] = matrix[copy_start - chunk_offset:copy_end - chunk_offset]

            if chunk_index and chunk_index % 250 == 0:
                percent = 100.0 * chunk_end / sample_count
                print(f"    {tdms_path.name}: {percent:5.1f}%", flush=True)

        if expected_offset != sample_count:
            raise RuntimeError(f"Read {expected_offset} samples, expected {sample_count}")
        final_start = stable_end - nperseg
        if not segment_starts or segment_starts[-1] != final_start:
            if len(welch_tail) != nperseg:
                raise RuntimeError("Could not construct final Welch segment")
            process_welch_segment(welch_tail, final_start)
        if np.isnan(snippets).any():
            raise RuntimeError("One or more raw snippets were not completely filled")

    low_rate = np.vstack(low_rate_parts)
    low_indices = np.concatenate(low_rate_indices)
    center_offset = int(round(0.5 * config.block_seconds * config.low_rate_hz))
    analysis_rate = signal.resample_poly(
        low_rate[center_offset:],
        up=1,
        down=analysis_decimation,
        axis=0,
        window=("kaiser", 12.0),
        padtype="line",
    )
    complete_block_count = sample_count // block_size
    analysis_rate = analysis_rate[:complete_block_count]
    envelopes = {
        name: np.vstack(parts) if parts else np.empty((0, len(channel_names)))
        for name, parts in envelope_lists.items()
    }
    envelopes["slow_mean"] = analysis_rate

    count = np.maximum(health["count"], 1)
    mean = health["sum"] / count
    variance = np.maximum(health["sumsq"] / count - mean * mean, 0.0)
    health_rows = []
    for index, name in enumerate(channel_names):
        health_rows.append({
            "channel_index": index + 1,
            "channel_name": name,
            "mean": float(mean[index]),
            "std": float(np.sqrt(variance[index])),
            "minimum": float(health["minimum"][index]),
            "maximum": float(health["maximum"][index]),
            "range": float(health["maximum"][index] - health["minimum"][index]),
            "difference_rms": float(np.sqrt(
                health["diff_sumsq"][index] / max(int(health["diff_count"][index]), 1)
            )),
            "flat_difference_fraction": float(
                health["flat_diff_count"][index] / max(int(health["diff_count"][index]), 1)
            ),
            "clip_fraction": float(health["clip_count"][index] / count[index]),
            "nonfinite_fraction": float(health["nonfinite_count"][index] / sample_count),
        })

    source_stat = tdms_path.stat()
    metadata = {
        "archive_version": ARCHIVE_VERSION,
        "source_path": str(tdms_path.resolve()),
        "source_size_bytes": source_stat.st_size,
        "source_mtime_ns": source_stat.st_mtime_ns,
        "sample_rate_hz": sample_rate,
        "sample_count": sample_count,
        "duration_s": sample_count / sample_rate,
        "start_time": str(start_time),
        "channel_names": channel_names,
        "group_name": group.name,
        "group_properties": _json_value(group.properties),
        "channel_properties": [_json_value(item.properties) for item in channels],
        "config": asdict(config),
        "lowpass_filter": {
            "type": "causal elliptic SOS before decimation",
            "order": filter_order,
            "sos": lowpass_sos.tolist(),
            "dc_gain_before_normalization": dc_gain,
            "raw_to_low_decimation": low_decimation,
            "low_to_analysis_decimation": analysis_decimation,
            "analysis_rate_first_sample_time_s": 0.5 * config.block_seconds,
        },
        "welch": {
            "definition": "all stable samples covered; 50% overlap plus final endpoint segment",
            "segment_count": len(segment_starts),
            "nperseg": nperseg,
            "step": step,
            "window": "periodic Hann",
            "detrend": "linear",
            "epoch_count": config.welch_epoch_count,
            "epoch_definition": "Welch segments assigned by center time to equal stable-time bins",
        },
        "band_names": BAND_NAMES,
        "band_limits_hz": BAND_LIMITS,
    }
    (output / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output / "health.json").write_text(
        json.dumps(health_rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    np.savez_compressed(
        output / "low_rate.npz",
        low_rate_v=low_rate,
        low_rate_sample_index=low_indices,
        low_rate_hz=config.low_rate_hz,
        analysis_rate_v=analysis_rate,
        analysis_rate_hz=config.analysis_rate_hz,
    )
    np.savez_compressed(
        output / "envelopes.npz",
        envelope_rate_hz=1.0 / config.block_seconds,
        **envelopes,
    )
    segment_count = len(segment_starts)
    if np.any(epoch_segment_count == 0):
        raise RuntimeError("One or more Welch time epochs contain no segments")
    epoch_psd_mean = epoch_psd_sum / epoch_segment_count[:, None, None]
    np.savez_compressed(
        output / "welch.npz",
        frequency_hz=frequency,
        psd_mean=(psd_sum / segment_count).T,
        epoch_psd_mean=epoch_psd_mean.transpose(0, 2, 1).astype(np.float32),
        epoch_segment_count=epoch_segment_count,
        segment_start_sample=np.asarray(segment_starts, dtype=np.int64),
        segment_time_s=np.asarray(segment_starts, dtype=float) / sample_rate,
        segment_bandpower=np.stack(segment_bandpowers),
        segment_peak_frequency_hz=np.stack(segment_peak_frequency),
        segment_peak_power=np.stack(segment_peak_power),
        band_names=np.asarray(BAND_NAMES),
    )
    _save_centered_snippets(
        output / "raw_snippets.npz", snippets, snippet_starts, sample_rate
    )
    complete_marker.write_text("complete\n", encoding="ascii")


def load_exact_archive(path: Path) -> dict[str, object]:
    if not archive_complete(path):
        raise FileNotFoundError(f"Incomplete exact archive: {path}")
    metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
    health = json.loads((path / "health.json").read_text(encoding="utf-8"))
    with np.load(path / "envelopes.npz") as data:
        features = {
            name: data[name]
            for name in ("slow_mean", "broadband_rms", "subkhz_rms",
                         "fast_residual_rms", "difference_rms")
        }
        envelope_rate = float(data["envelope_rate_hz"])
        slow_mean_boxcar = data["slow_mean_boxcar"]
    with np.load(path / "welch.npz") as data:
        frequency = data["frequency_hz"]
        psd = data["psd_mean"]
        segment_time = data["segment_time_s"]
        segment_bandpower = data["segment_bandpower"]
        segment_peak_frequency = data["segment_peak_frequency_hz"]
        segment_peak_power = data["segment_peak_power"]
        epoch_psd_mean = data["epoch_psd_mean"]
        epoch_segment_count = data["epoch_segment_count"]
    return {
        "sample_rate": float(metadata["sample_rate_hz"]),
        "duration_s": float(metadata["duration_s"]),
        "start_time": str(metadata["start_time"]),
        "channel_names": list(metadata["channel_names"]),
        "features": features,
        "slow_mean_boxcar": slow_mean_boxcar,
        "frequency": frequency,
        "psd": psd,
        "health": health,
        "envelope_fs": envelope_rate,
        "welch_segment_time_s": segment_time,
        "welch_segment_bandpower": segment_bandpower,
        "welch_segment_peak_frequency_hz": segment_peak_frequency,
        "welch_segment_peak_power": segment_peak_power,
        "welch_epoch_psd_mean": epoch_psd_mean,
        "welch_epoch_segment_count": epoch_segment_count,
        "archive_metadata": metadata,
    }
