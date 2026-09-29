"""Analyze the named videos accompanying the 2026-08-06 VFD experiment."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from pathlib import Path

import matplotlib
import numpy as np
from scipy import signal

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from analyze_20260731_media import (
    DEFAULT_FFMPEG,
    audio_features,
    decode_audio,
    decode_video_gray,
    periodicity,
    video_features,
    windowed_periodicity,
)


DEFAULT_ROOT = Path(r"D:\Lab\raw\26.8.6")


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tone_metric(frequency: np.ndarray, psd: np.ndarray, target: float) -> dict[str, float]:
    center = np.abs(frequency - target) <= 500.0
    baseline = (np.abs(frequency - target) >= 800.0) & (np.abs(frequency - target) <= 1_500.0)
    center_power = float(np.mean(psd[center]))
    baseline_power = float(np.median(psd[baseline]))
    center_indices = np.flatnonzero(center)
    peak_index = center_indices[np.argmax(psd[center])]
    peak_power = float(psd[peak_index])
    return {
        "cluster_power_db": 10.0 * np.log10(center_power + 1e-30),
        "cluster_excess_db": 10.0 * np.log10((center_power + 1e-30) / (baseline_power + 1e-30)),
        "peak_excess_db": 10.0 * np.log10((peak_power + 1e-30) / (baseline_power + 1e-30)),
        "peak_frequency_hz": float(frequency[peak_index]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--ffmpeg", type=Path, default=DEFAULT_FFMPEG)
    parser.add_argument(
        "--output", type=Path,
        default=Path('experiments/20260806/media'),
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    videos = sorted(args.root.glob("*.mp4"))
    pattern = re.compile(r"(?P<carrier>\d+)k(?P<output>\d+)hz(?P<replicate>2?)$", re.IGNORECASE)
    hashes = {path: file_hash(path) for path in videos}
    counts = {value: list(hashes.values()).count(value) for value in set(hashes.values())}
    summary_rows: list[dict[str, object]] = []
    audio_spectra: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    series: dict[str, dict[str, object]] = {}

    for index, path in enumerate(videos, start=1):
        match = pattern.match(path.stem)
        if not match:
            raise ValueError(f"Unexpected video name: {path.name}")
        carrier = int(match.group("carrier"))
        output_hz = int(match.group("output"))
        replicate = 2 if match.group("replicate") else 1
        print(f"[{index:02d}/{len(videos)}] {path.name}", flush=True)

        samples, fs = decode_audio(args.ffmpeg, path, fs=48_000)
        frequency, psd = signal.welch(
            signal.detrend(samples), fs=fs, window="hann", nperseg=65_536,
            noverlap=32_768, detrend="linear", average="median",
        )
        audio_spectra[path.name] = (frequency, psd)
        audio = audio_features(samples, fs)
        audio_period = periodicity(np.asarray(audio["envelope"]), float(audio["frame_fs"]))
        audio_windows = windowed_periodicity(
            np.asarray(audio["envelope"]), float(audio["frame_fs"])
        )

        frames, video_fs = decode_video_gray(args.ffmpeg, path)
        video = video_features(frames, video_fs)
        video_period = periodicity(np.asarray(video["composite"]), video_fs)
        video_windows = windowed_periodicity(np.asarray(video["composite"]), video_fs)
        series[path.name] = {"audio": audio, "video": video}

        row: dict[str, object] = {
            "file": path.name,
            "carrier_khz_from_name": carrier,
            "output_hz_from_name": output_hz,
            "replicate_from_name": replicate,
            "sha256": hashes[path],
            "duplicate_file": counts[hashes[path]] > 1,
            "duration_s": len(samples) / fs,
            **{f"audio_{key}": value for key, value in audio_period.items()},
            **{f"audio_{key}": value for key, value in audio_windows.items()},
            **{f"video_{key}": value for key, value in video_period.items()},
            **{f"video_{key}": value for key, value in video_windows.items()},
        }
        for candidate in (4, 8, 12):
            metrics = tone_metric(frequency, psd, candidate * 1000.0)
            for key, value in metrics.items():
                row[f"audio_{candidate}khz_{key}"] = value
        summary_rows.append(row)

    write_csv(args.output / "video_analysis_summary.csv", summary_rows)

    fig, axes = plt.subplots(5, 2, figsize=(15, 13), constrained_layout=True)
    for axis, row in zip(axes.ravel(), summary_rows):
        values = series[str(row["file"])]
        audio = values["audio"]
        video = values["video"]
        axis.plot(audio["time_s"], np.clip(audio["envelope"], -4, 4), lw=0.8,
                  label=f"audio T={row['audio_period_s']:.2f}s")
        axis.plot(video["time_s"], np.clip(video["composite"], -4, 4), lw=0.8, alpha=0.8,
                  label=f"video T={row['video_period_s']:.2f}s")
        duplicate = " [DUPLICATE LABEL]" if row["duplicate_file"] else ""
        axis.set_title(f"{row['file']}{duplicate}")
        axis.set_ylim(-4.2, 4.2)
        axis.grid(alpha=0.2)
        axis.legend(fontsize=7)
    fig.supxlabel("Time (s)")
    fig.supylabel("Robust z")
    fig.savefig(args.output / "video_water_pulsation_overview.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(14, 9), constrained_layout=True)
    for axis, output_hz in zip(axes, (30, 50)):
        for row in summary_rows:
            if row["output_hz_from_name"] != output_hz or row["duplicate_file"]:
                continue
            frequency, psd = audio_spectra[str(row["file"])]
            use = (frequency >= 1_000.0) & (frequency <= 16_000.0)
            normalized = 10.0 * np.log10(psd + 1e-30)
            normalized -= np.median(normalized[use])
            axis.plot(frequency[use] / 1000.0, normalized[use], lw=0.65,
                      label=str(row["file"]))
        for marker in (4, 8, 12):
            axis.axvline(marker, color="black", alpha=0.15, lw=0.8)
        axis.set_title(f"Video audio spectrum, named output {output_hz} Hz")
        axis.set_xlabel("Frequency (kHz)")
        axis.set_ylabel("Relative PSD (dB)")
        axis.set_ylim(-15, 45)
        axis.grid(alpha=0.2)
        axis.legend(fontsize=7, ncol=2)
    fig.savefig(args.output / "video_audio_carrier_spectra.png", dpi=180)
    plt.close(fig)
    print(f"Wrote {args.output.resolve()}", flush=True)


if __name__ == "__main__":
    main()
