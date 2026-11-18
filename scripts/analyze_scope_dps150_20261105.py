"""Analyze one oscilloscope CSV; no hardware access or input modification."""

from pathlib import Path
import csv
import hashlib
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import optimize, signal

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis/dps150_scope_20261105/scope_1"
SOURCE = Path("E:/scope_1.csv")
COMMANDS = ROOT / "local/logs/dps150_pipe_20261105_151639/commands.csv"


def fit(t, y, frequency, harmonics=1, trend=False):
    columns = [np.ones(len(t))]
    if trend:
        columns.append(t-np.mean(t))
    for k in range(1, harmonics+1):
        columns.extend((np.sin(2*np.pi*k*frequency*t),
                        np.cos(2*np.pi*k*frequency*t)))
    matrix = np.column_stack(columns)
    coef = np.linalg.lstsq(matrix, y, rcond=None)[0]
    prediction = matrix @ coef
    offset = 2 if trend else 1
    amplitudes = np.hypot(coef[offset::2], coef[offset+1::2])
    return dict(dc_v=float(coef[0]), amplitudes_v=amplitudes.tolist(),
        residual_rms_v=float(np.sqrt(np.mean((y-prediction)**2))),
        residual_relative_to_base_rms_pct=float(
            100*np.sqrt(np.mean((y-prediction)**2))/(amplitudes[0]/np.sqrt(2))),
        fitted_2to5_harmonic_ratio_pct=(float(100*np.linalg.norm(amplitudes[1:])/amplitudes[0])
                                     if harmonics>1 else None)), prediction


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    test_t = np.arange(500)/1000
    test_y = 2+.7*np.sin(2*np.pi*5*test_t)+.1*np.cos(2*np.pi*10*test_t)
    test_fit, _ = fit(test_t, test_y, 5., 5)
    assert np.allclose(test_fit["amplitudes_v"][:2], [.7, .1], atol=1e-12)
    assert test_fit["residual_rms_v"] < 1e-12
    values = np.loadtxt(SOURCE, delimiter=",", skiprows=2)
    t, y = values.T
    dt = np.diff(t)
    assert np.all(np.isfinite(values)) and np.all(dt>0)
    assert np.max(abs(dt-np.median(dt))) < 1e-10
    fs = 1/np.median(dt)
    # Centering avoids the finite-record resampler's artificial DC edge jump.
    decimation = 100
    mean = np.mean(y)
    small = signal.resample_poly(y-mean, 1, decimation)+mean
    ts = t[0]+np.arange(len(small))*decimation/fs
    guard = (ts>=t[0]+.005) & (ts<=t[-1]-.005)
    tg, yg = ts[guard], small[guard]
    frequencies = np.linspace(3., 7., 401)
    errors = [fit(tg, yg, f)[0]["residual_rms_v"] for f in frequencies]
    index = int(np.argmin(errors))
    lower, upper = frequencies[max(index-1, 0)], frequencies[min(index+1, 400)]
    optimized = optimize.minimize_scalar(
        lambda f: fit(tg, yg, f)[0]["residual_rms_v"],
        bounds=(lower, upper), method="bounded")
    free_frequency = float(optimized.x)
    free_fit, _ = fit(tg, yg, free_frequency)
    models = {}
    for harmonics, trend in ((1, False), (5, False), (5, True)):
        name = f"nominal_5hz_h{harmonics}_trend{int(trend)}"
        models[name] = fit(tg, yg, 5., harmonics, trend)[0]
    fundamental, prediction = fit(t, y, 5.)
    harmonic, harmonic_prediction = fit(t, y, 5., 5)
    smoothed = signal.savgol_filter(small, 31, 3)
    peak_indices, _ = signal.find_peaks(smoothed, distance=120, prominence=.5)
    trough_indices, _ = signal.find_peaks(-smoothed, distance=120, prominence=.5)
    peak_intervals = np.diff(ts[peak_indices])
    trough_intervals = np.diff(ts[trough_indices])
    with COMMANDS.open(encoding="utf-8-sig", newline="") as handle:
        commands = list(csv.DictReader(handle))
    sent = np.array([float(row["send_start_s"]) for row in commands])
    target = np.array([float(row["target_s"]) for row in commands])
    intervals = np.diff(sent)*1000
    raw_levels = np.unique(np.round(y, 6))
    diffs = np.diff(raw_levels)
    positive = diffs[diffs>1e-4]
    result = dict(
        acquisition=dict(source=str(SOURCE), sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            points=len(t), sample_rate_hz=fs, time_start_s=float(t[0]),
            time_end_s=float(t[-1]), duration_with_final_sample_s=len(t)/fs,
            cycles_at_commanded_5hz=len(t)/fs*5,
            source_file_date_not_trusted=True,
            approximate_voltage_level_step_v=float(np.median(positive)),
            source_units=["second", "Volt"]),
        measured=dict(raw_mean_v=float(np.mean(y)), raw_min_v=float(min(y)),
            raw_max_v=float(max(y)), raw_q01_q99_v=np.quantile(y, [.01, .99]).tolist(),
            smoothed_guard_min_v=float(min(smoothed[guard])),
            smoothed_guard_max_v=float(max(smoothed[guard])),
            smoothed_peak_intervals_s=peak_intervals.tolist(),
            smoothed_trough_intervals_s=trough_intervals.tolist()),
        free_single_sine_fit=dict(frequency_hz=free_frequency, **free_fit),
        fixed_5hz_full_raw_fit=fundamental,
        fixed_5hz_full_raw_low_order_harmonic_fit=harmonic,
        fit_sensitivity_1khz_resampled_guarded=models,
        current_conversion_assuming_measured_resistor_815ohm=dict(
            base_peak_ma=fundamental["amplitudes_v"][0]/815*1000,
            fitted_dc_ma=fundamental["dc_v"]/815*1000,
            note="Derived from scope voltage, not independent current-probe data"),
        command_context=dict(source=str(COMMANDS.relative_to(ROOT)),
            sha256=hashlib.sha256(COMMANDS.read_bytes()).hexdigest(), points=len(sent),
            intended_interval_ms=5,
            interval_quantiles_ms=dict(zip(("min", "median", "p95", "p99", "max"),
                np.quantile(intervals, (0,.5,.95,.99,1)).tolist())),
            host_lateness_p95_ms=float(np.quantile(sent-target, .95)*1000),
            host_lateness_max_ms=float(max(sent-target)*1000),
            intervals_over_10ms=int(sum(intervals>10))),
        limitations=["Only 0.5 s; no reliable long-run repeatability or bandwidth limit",
            "Single-sine residual includes harmonics, jitter, drift, pickup and noise, not THD",
            "Harmonic ratio covers orders 2-5 only, assumes stationarity, and has few cycles; not standardized full-band THD",
            "DC and frequency estimates depend on short-record model; raw average is phase-window dependent",
            "Scope timing has no synchronized wall-clock marker with host log; causal point-by-point matching unavailable",
            "Host send timestamps are not device execution timestamps",
            "Cannot uniquely separate power supply, program scheduling, probe pickup and contact effects",
            "This is a resistor voltage test, not electrochemical load or TC electric-field calibration"])
    (OUT/"results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), constrained_layout=True)
    axes[0].plot(t, y, lw=.35, color="#78838d", label="Scope CSV, raw")
    axes[0].plot(ts, smoothed, lw=1.8, color="#267052", label="Smoothed for shape display")
    axes[0].plot(t, prediction, lw=1.4, color="#ba5429", label="Best amplitude/phase at fixed 5 Hz")
    axes[0].set(ylabel="Voltage (V)", title="Measured output vs fixed-frequency sine fit")
    axes[0].legend(loc="lower right", fontsize=8)
    axes[1].plot(t, y-prediction, lw=.35, color="#78838d", label="Raw minus fixed 5 Hz sine")
    axes[1].plot(ts, smoothed-np.interp(ts, t, prediction), lw=1.5, color="#276493")
    axes[1].set(ylabel="Residual (V)", title="Residual includes distortion, timing variation and noise")
    zoom = (sent-sent[0] < .5)
    axes[2].plot((sent-sent[0])[zoom][1:], np.diff(sent[zoom])*1000, color="#775633", marker=".", ms=3)
    axes[2].axhline(5, color="#276493", ls="--", label="Nominal 5 ms")
    axes[2].set(xlabel="Time (s)", ylabel="Send interval (ms)",
        title="First 0.5 s of command log: illustrative, NOT synchronized to scope")
    axes[2].legend(fontsize=8)
    for ax in axes:
        ax.grid(alpha=.2)
    fig.savefig(OUT/"scope_1_analysis.png", dpi=170)
    plt.close(fig)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
