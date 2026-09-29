"""Quantify water pulsation evidence in the 2026-07-31 media files.

The MP4 tracks are treated as the primary water reference because their audio
and image streams share a clock. Standalone M4A files are analyzed as secondary
evidence only; they contain speech and computer noise and are not assumed to be
sample-synchronous with TDMS.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import matplotlib
import numpy as np
from scipy import ndimage, signal

matplotlib.use("Agg")
import matplotlib.pyplot as plt


DEFAULT_ROOT = Path(r"D:\Lab\raw\26.7.31")
DEFAULT_FFMPEG = Path(r"D:\tools\ffmpeg-8.1-essentials_build\bin\ffmpeg.exe")


@dataclass(frozen=True)
class MediaCase:
    case_id: str
    session: str
    detector: str
    condition: str
    video: Path | None
    recorder: Path


def media_cases(root: Path) -> list[MediaCase]:
    records = root / "records"
    return [
        MediaCase("morning_background", "morning", "TC2", "background", None,
                  records / "\u7a7a\u8c03\u5916\u673a\u7eaf\u80cc\u666f\u4e0a\u5348.m4a"),
        MediaCase("morning_vfd_stop", "morning", "TC2", "vfd_stop", None,
                  records / "vfd\u4e0a\u5348.m4a"),
        MediaCase("morning_30hz", "morning", "TC2", "30hz", records / "30hz\u4e0a\u5348.mp4",
                  records / "30hz\u4e0a\u5348.m4a"),
        MediaCase("morning_50hz", "morning", "TC2", "50hz", records / "50hz\u4e0a\u5348.mp4",
                  records / "50hz\u4e0a\u5348.m4a"),
        MediaCase("afternoon_background", "afternoon", "TC1", "background", None,
                  records / "\u7a7a\u8c03\u5916\u673a\u7eaf\u80cc\u666f\u4e0b\u5348.m4a"),
        MediaCase("afternoon_vfd_stop", "afternoon", "TC1", "vfd_stop", None,
                  records / "vfd\u4e0b\u5348.m4a"),
        MediaCase("afternoon_30hz", "afternoon", "TC1", "30hz", records / "30hz\u4e0b\u5348.mp4",
                  records / "30hz\u4e0b\u5348.m4a"),
        MediaCase("afternoon_50hz", "afternoon", "TC1", "50hz", records / "50hz\u4e0b\u5348.mp4",
                  records / "50hz\u4e0b\u5348.m4a"),
    ]


def run_ffmpeg(ffmpeg: Path, args: list[str]) -> bytes:
    command = [str(ffmpeg), "-hide_banner", "-loglevel", "error", *args]
    return subprocess.run(command, check=True, stdout=subprocess.PIPE).stdout


def decode_audio(ffmpeg: Path, path: Path, fs: int = 16_000) -> tuple[np.ndarray, int]:
    raw = run_ffmpeg(
        ffmpeg,
        ["-i", str(path), "-vn", "-ac", "1", "-ar", str(fs),
         "-f", "f32le", "-acodec", "pcm_f32le", "pipe:1"],
    )
    return np.frombuffer(raw, dtype="<f4").astype(np.float64), fs


def decode_video_gray(
    ffmpeg: Path,
    path: Path,
    fps: int = 6,
    width: int = 96,
    height: int = 160,
) -> tuple[np.ndarray, float]:
    raw = run_ffmpeg(
        ffmpeg,
        ["-i", str(path), "-an", "-vf",
         f"fps={fps},scale={width}:{height}:flags=area,format=gray",
         "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"],
    )
    frame_size = width * height
    frame_count = len(raw) // frame_size
    frames = np.frombuffer(raw[: frame_count * frame_size], dtype=np.uint8)
    return frames.reshape(frame_count, height, width).astype(np.float32), float(fps)


def robust_zscore(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    center = np.nanmedian(values)
    scale = 1.4826 * np.nanmedian(np.abs(values - center))
    if not np.isfinite(scale) or scale < 1e-12:
        scale = np.nanstd(values)
    return (values - center) / max(float(scale), 1e-12)


def smooth(values: np.ndarray, fs: float, seconds: float = 0.35) -> np.ndarray:
    width = max(3, int(round(seconds * fs)))
    if width % 2 == 0:
        width += 1
    if width >= len(values):
        return values.copy()
    return signal.savgol_filter(values, width, min(2, width - 1), mode="interp")


def band_limited(values: np.ndarray, fs: float, low: float = 0.06, high: float = 0.70) -> np.ndarray:
    values = np.nan_to_num(robust_zscore(values))
    if len(values) < int(8 * fs):
        return signal.detrend(values)
    sos = signal.butter(3, [low, min(high, 0.45 * fs)], btype="bandpass", fs=fs, output="sos")
    return signal.sosfiltfilt(sos, values)


def periodicity(values: np.ndarray, fs: float) -> dict[str, float]:
    filtered = band_limited(values, fs)
    n = len(filtered)
    if n < int(10 * fs):
        return {"period_s": float("nan"), "acf": float("nan"),
                "spectral_snr": float("nan"), "split_agreement": float("nan")}

    acf = signal.correlate(filtered, filtered, mode="full", method="fft")[n - 1 :]
    denom = np.arange(n, 0, -1, dtype=float)
    acf = acf / denom
    acf = acf / max(acf[0], 1e-12)
    min_lag = max(1, int(round(1.5 * fs)))
    max_lag = min(len(acf) - 1, int(round(15.0 * fs)))
    peaks, _ = signal.find_peaks(acf[min_lag : max_lag + 1], distance=max(1, int(fs)))
    if len(peaks):
        candidates = peaks + min_lag
        lag = int(candidates[np.argmax(acf[candidates])])
    else:
        lag = int(min_lag + np.argmax(acf[min_lag : max_lag + 1]))

    freq, psd = signal.periodogram(filtered, fs=fs, window="hann", detrend="linear")
    use = (freq >= 0.06) & (freq <= 0.70)
    peak_index = np.flatnonzero(use)[np.argmax(psd[use])]
    spectral_period = 1.0 / freq[peak_index]
    spectral_snr = psd[peak_index] / max(float(np.median(psd[use])), 1e-15)

    half = n // 2
    half_periods = []
    for segment_values in (filtered[:half], filtered[half:]):
        f_half, p_half = signal.periodogram(segment_values, fs=fs, window="hann", detrend="linear")
        keep = (f_half >= 0.06) & (f_half <= 0.70)
        half_periods.append(1.0 / f_half[np.flatnonzero(keep)[np.argmax(p_half[keep])]])
    split_agreement = min(half_periods) / max(half_periods)

    # Prefer the ACF period when it is close to the dominant spectral period.
    acf_period = lag / fs
    if abs(np.log(acf_period / spectral_period)) <= np.log(1.35):
        period = 0.5 * (acf_period + spectral_period)
    else:
        period = spectral_period
    return {
        "period_s": float(period),
        "acf_period_s": float(acf_period),
        "spectral_period_s": float(spectral_period),
        "acf": float(acf[lag]),
        "spectral_snr": float(spectral_snr),
        "split_agreement": float(split_agreement),
    }


def windowed_periodicity(
    values: np.ndarray,
    fs: float,
    window_seconds: float = 20.0,
    step_seconds: float = 5.0,
) -> dict[str, float]:
    window = int(round(window_seconds * fs))
    step = int(round(step_seconds * fs))
    metrics = [
        periodicity(values[start : start + window], fs)
        for start in range(0, len(values) - window + 1, step)
    ]
    strong = [
        item for item in metrics
        if item["acf"] >= 0.30 and item["spectral_snr"] >= 10.0
    ]
    periods = np.array([item["period_s"] for item in strong], dtype=float)
    return {
        "strong_window_fraction": float(len(strong) / max(len(metrics), 1)),
        "strong_window_count": float(len(strong)),
        "window_count": float(len(metrics)),
        "strong_window_median_period_s": float(np.median(periods)) if len(periods) else float("nan"),
        "strong_window_period_cv": float(np.std(periods) / np.mean(periods)) if len(periods) >= 2 else float("nan"),
    }


def longest_clean_audio_segment(features: dict[str, np.ndarray | float]) -> tuple[slice, float]:
    frame_fs = float(features["frame_fs"])
    speech_like = np.asarray(features["speech_index"]) > 3.0
    dilation = max(1, int(round(0.6 * frame_fs)))
    contaminated = ndimage.maximum_filter1d(speech_like.astype(np.uint8), dilation) > 0
    clean = ~contaminated
    changes = np.diff(np.r_[False, clean, False].astype(np.int8))
    starts = np.flatnonzero(changes == 1)
    ends = np.flatnonzero(changes == -1)
    if not len(starts):
        return slice(0, len(clean)), 0.0
    lengths = ends - starts
    best = int(np.argmax(lengths))
    return slice(int(starts[best]), int(ends[best])), float(lengths[best] / frame_fs)


def video_features(frames: np.ndarray, fs: float) -> dict[str, np.ndarray | float]:
    height, width = frames.shape[1:]
    y0, y1 = int(0.24 * height), int(0.93 * height)
    x0, x1 = int(0.04 * width), int(0.96 * width)
    candidate = frames[:, y0:y1, x0:x1]

    pixel_variability = np.std(candidate, axis=0)
    threshold = np.percentile(pixel_variability, 55)
    dynamic_mask = pixel_variability >= threshold
    differences = np.abs(np.diff(candidate, axis=0))
    motion = np.mean(differences[:, dynamic_mask], axis=1)

    # A second feature catches slow surface-height/brightness changes even when
    # the splash texture remains active throughout the recording.
    level = np.mean(candidate[:, dynamic_mask], axis=1)
    gy = np.abs(np.diff(candidate, axis=1)).mean(axis=(1, 2))
    motion_t = (np.arange(len(motion)) + 0.5) / fs
    level = level[1:]
    gy = gy[1:]

    motion_z = robust_zscore(smooth(motion, fs))
    level_z = robust_zscore(smooth(level, fs, 0.7))
    texture_z = robust_zscore(smooth(gy, fs, 0.7))
    composite = robust_zscore(motion_z + 0.35 * level_z + 0.35 * texture_z)
    return {
        "time_s": motion_t,
        "motion": motion_z,
        "level": level_z,
        "texture": texture_z,
        "composite": composite,
        "dynamic_fraction": float(np.mean(dynamic_mask)),
    }


def audio_features(samples: np.ndarray, fs: int) -> dict[str, np.ndarray | float]:
    samples = signal.detrend(samples)
    nperseg = 2048
    hop = 800
    freq, time_s, stft = signal.stft(
        samples,
        fs=fs,
        window="hann",
        nperseg=nperseg,
        noverlap=nperseg - hop,
        boundary=None,
        padded=False,
    )
    power = np.abs(stft) ** 2 + 1e-20
    stationary = np.percentile(power, 25, axis=1, keepdims=True)
    excess = np.maximum(power / stationary - 1.0, 0.0)

    def band_energy(low: float, high: float, source: np.ndarray = power) -> np.ndarray:
        use = (freq >= low) & (freq < high)
        return 10.0 * np.log10(np.mean(source[use], axis=0) + 1e-20)

    low = band_energy(80, 350)
    water = band_energy(350, 3000)
    high = band_energy(3000, 7000)
    whitened = np.log1p(np.mean(excess[(freq >= 120) & (freq < 7000)], axis=0))

    envelope = robust_zscore(smooth(whitened, 1.0 / np.median(np.diff(time_s)), 0.45))
    frame_fs = 1.0 / np.median(np.diff(time_s))
    speech_index = robust_zscore(water - 0.55 * low - 0.25 * high)
    speech_burst_fraction = float(np.mean(speech_index > 3.0))
    clipping_fraction = float(np.mean(np.abs(samples) >= 0.999))
    return {
        "time_s": time_s,
        "envelope": envelope,
        "low_db": low,
        "water_db": water,
        "high_db": high,
        "speech_index": speech_index,
        "frame_fs": float(frame_fs),
        "speech_burst_fraction": speech_burst_fraction,
        "clipping_fraction": clipping_fraction,
    }


def normalized_for_plot(values: np.ndarray) -> np.ndarray:
    values = robust_zscore(values)
    return np.clip(values, -4.0, 4.0)


def aligned_correlation(
    video_time: np.ndarray,
    video_values: np.ndarray,
    audio_time: np.ndarray,
    audio_values: np.ndarray,
    fs: float = 6.0,
) -> dict[str, float]:
    end = min(float(video_time[-1]), float(audio_time[-1]))
    common = np.arange(max(float(video_time[0]), float(audio_time[0])), end, 1.0 / fs)
    video = band_limited(np.interp(common, video_time, video_values), fs)
    audio = band_limited(np.interp(common, audio_time, audio_values), fs)
    zero = float(np.corrcoef(video, audio)[0, 1])
    max_shift = int(round(1.5 * fs))
    correlations = []
    shifts = range(-max_shift, max_shift + 1)
    for shift in shifts:
        if shift < 0:
            correlations.append(np.corrcoef(video[-shift:], audio[:shift])[0, 1])
        elif shift > 0:
            correlations.append(np.corrcoef(video[:-shift], audio[shift:])[0, 1])
        else:
            correlations.append(zero)
    best = int(np.nanargmax(np.abs(correlations)))
    return {
        "zero_lag_correlation": zero,
        "max_abs_correlation": float(correlations[best]),
        "lag_s_audio_after_video": float(list(shifts)[best] / fs),
    }


def write_timeseries(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def finite_json(value: object) -> object:
    if isinstance(value, dict):
        return {key: finite_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [finite_json(item) for item in value]
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--ffmpeg", type=Path, default=DEFAULT_FFMPEG)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path('experiments/20260731/media'),
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    cases = media_cases(args.root)
    for case in cases:
        if not case.recorder.exists() or (case.video is not None and not case.video.exists()):
            raise FileNotFoundError(case)

    summary_rows: list[dict[str, object]] = []
    timeseries_rows: list[dict[str, object]] = []
    active_results: dict[str, dict[str, object]] = {}
    recorder_results: dict[str, dict[str, object]] = {}

    for case in cases:
        samples, audio_fs = decode_audio(args.ffmpeg, case.recorder)
        recorder = audio_features(samples, audio_fs)
        recorder_period = periodicity(
            np.asarray(recorder["envelope"]), float(recorder["frame_fs"])
        )
        clean_slice, clean_duration = longest_clean_audio_segment(recorder)
        if clean_duration >= 15.0:
            clean_period = periodicity(
                np.asarray(recorder["envelope"])[clean_slice], float(recorder["frame_fs"])
            )
        else:
            clean_period = {key: float("nan") for key in recorder_period}
        recorder_windows = windowed_periodicity(
            np.asarray(recorder["envelope"]), float(recorder["frame_fs"])
        )
        recorder_results[case.case_id] = {"features": recorder, "periodicity": recorder_period}
        row: dict[str, object] = {
            "case_id": case.case_id,
            "session": case.session,
            "detector": case.detector,
            "condition": case.condition,
            "source": "standalone_recorder",
            "duration_s": len(samples) / audio_fs,
            "speech_burst_fraction": recorder["speech_burst_fraction"],
            "clipping_fraction": recorder["clipping_fraction"],
            **recorder_period,
            **{f"clean_{key}": value for key, value in clean_period.items()},
            "longest_clean_segment_s": clean_duration,
            **recorder_windows,
        }
        summary_rows.append(row)
        for time_value, envelope, speech in zip(
            recorder["time_s"], recorder["envelope"], recorder["speech_index"]
        ):
            timeseries_rows.append({
                "case_id": case.case_id,
                "source": "standalone_recorder",
                "time_s": float(time_value),
                "envelope_z": float(envelope),
                "speech_index_z": float(speech),
            })

        if case.video is None:
            continue
        frames, video_fs = decode_video_gray(args.ffmpeg, case.video)
        video = video_features(frames, video_fs)
        video_period = periodicity(np.asarray(video["composite"]), video_fs)
        video_windows = windowed_periodicity(np.asarray(video["composite"]), video_fs)

        mp4_samples, mp4_audio_fs = decode_audio(args.ffmpeg, case.video)
        mp4_audio = audio_features(mp4_samples, mp4_audio_fs)
        mp4_period = periodicity(
            np.asarray(mp4_audio["envelope"]), float(mp4_audio["frame_fs"])
        )
        mp4_windows = windowed_periodicity(
            np.asarray(mp4_audio["envelope"]), float(mp4_audio["frame_fs"])
        )
        correlation = aligned_correlation(
            np.asarray(video["time_s"]),
            np.asarray(video["composite"]),
            np.asarray(mp4_audio["time_s"]),
            np.asarray(mp4_audio["envelope"]),
        )
        period_ratio = min(video_period["period_s"], mp4_period["period_s"]) / max(
            video_period["period_s"], mp4_period["period_s"]
        )
        active_results[case.case_id] = {
            "video": video,
            "video_periodicity": video_period,
            "mp4_audio": mp4_audio,
            "mp4_audio_periodicity": mp4_period,
            "correlation": correlation,
            "period_ratio": float(period_ratio),
        }
        summary_rows.extend([
            {
                "case_id": case.case_id,
                "session": case.session,
                "detector": case.detector,
                "condition": case.condition,
                "source": "video_motion",
                "duration_s": len(frames) / video_fs,
                "speech_burst_fraction": "",
                "clipping_fraction": "",
                **video_period,
                **video_windows,
                **correlation,
                "audio_video_period_ratio": float(period_ratio),
            },
            {
                "case_id": case.case_id,
                "session": case.session,
                "detector": case.detector,
                "condition": case.condition,
                "source": "mp4_audio",
                "duration_s": len(mp4_samples) / mp4_audio_fs,
                "speech_burst_fraction": mp4_audio["speech_burst_fraction"],
                "clipping_fraction": mp4_audio["clipping_fraction"],
                **mp4_period,
                **mp4_windows,
                **correlation,
                "audio_video_period_ratio": float(period_ratio),
            },
        ])
        for time_value, envelope in zip(video["time_s"], video["composite"]):
            timeseries_rows.append({
                "case_id": case.case_id,
                "source": "video_motion",
                "time_s": float(time_value),
                "envelope_z": float(envelope),
                "speech_index_z": "",
            })
        for time_value, envelope, speech in zip(
            mp4_audio["time_s"], mp4_audio["envelope"], mp4_audio["speech_index"]
        ):
            timeseries_rows.append({
                "case_id": case.case_id,
                "source": "mp4_audio",
                "time_s": float(time_value),
                "envelope_z": float(envelope),
                "speech_index_z": float(speech),
            })

    summary_path = args.output / "media_periodicity_summary.csv"
    write_timeseries(summary_path, summary_rows)
    write_timeseries(args.output / "media_feature_timeseries.csv", timeseries_rows)

    active_order = ["morning_30hz", "morning_50hz", "afternoon_30hz", "afternoon_50hz"]
    fig, axes = plt.subplots(4, 1, figsize=(13, 11), sharex=False, constrained_layout=True)
    for axis, case_id in zip(axes, active_order):
        result = active_results[case_id]
        video = result["video"]
        audio = result["mp4_audio"]
        axis.plot(video["time_s"], normalized_for_plot(video["composite"]), lw=1.1,
                  label=f"video motion, T={result['video_periodicity']['period_s']:.2f}s")
        axis.plot(audio["time_s"], normalized_for_plot(audio["envelope"]), lw=0.9, alpha=0.8,
                  label=f"MP4 audio, T={result['mp4_audio_periodicity']['period_s']:.2f}s")
        corr = result["correlation"]
        axis.set_title(
            f"{case_id}: AV period ratio={result['period_ratio']:.2f}, "
            f"max |r|={abs(corr['max_abs_correlation']):.2f}"
        )
        axis.set_ylabel("robust z")
        axis.grid(alpha=0.2)
        axis.legend(loc="upper right", ncol=2, fontsize=8)
    axes[-1].set_xlabel("Time (s)")
    fig.savefig(args.output / "video_audio_pulsation_overview.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(4, 2, figsize=(14, 11), sharex=False, constrained_layout=True)
    for axis, case in zip(axes.ravel(), cases):
        result = recorder_results[case.case_id]
        features = result["features"]
        period = result["periodicity"]
        axis.plot(features["time_s"], normalized_for_plot(features["envelope"]), lw=0.8)
        speech = np.asarray(features["speech_index"]) > 3.0
        axis.fill_between(features["time_s"], -4, 4, where=speech, color="tab:red", alpha=0.12,
                          label="speech-like burst")
        axis.set_title(
            f"{case.case_id}: T={period['period_s']:.2f}s, ACF={period['acf']:.2f}, "
            f"bursts={100 * features['speech_burst_fraction']:.1f}%"
        )
        axis.set_ylim(-4.2, 4.2)
        axis.grid(alpha=0.2)
    fig.supxlabel("Time (s)")
    fig.supylabel("Noise-suppressed audio envelope (robust z)")
    fig.savefig(args.output / "standalone_audio_quality_overview.png", dpi=180)
    plt.close(fig)

    payload = {
        "method": {
            "video_fps": 6,
            "video_size": [96, 160],
            "period_search_s": [1.5, 15.0],
            "audio_note": "MP4 audio is primary; standalone M4A is contamination-sensitive secondary evidence.",
        },
        "summary": summary_rows,
    }
    (args.output / "media_analysis.json").write_text(
        json.dumps(finite_json(payload), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Wrote {args.output.resolve()}")


if __name__ == "__main__":
    main()
