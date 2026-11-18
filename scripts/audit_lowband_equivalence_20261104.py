"""Scoped archived-voltage audit; synthetic checks do not calibrate hardware."""

from pathlib import Path
import csv
import hashlib
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.channel_quality import assess_channel_quality

OUT = ROOT / "analysis/lowband_equivalence_audit_20261104"
CASES = {
    "TC1_VFD_background": "experiments/20260806/exact_archive/vfd_tc1_background",
    "TC2_VFD_background": "experiments/20260806/exact_archive/vfd_tc2_background",
    "TC2_VFD_4k_50Hz": "experiments/20260806/exact_archive/vfd_tc2_4k_50hz",
    "TC2_CP_background": "experiments/20260811_2/exact_archive/bkg__20260811201213.087736-1",
    "TC2_CP_3000mA_label": "experiments/20260811_2/exact_archive/cp3000near__20260811203210.252604-1",
}


def write_csv(name, rows):
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def coefficients(x, t, frequency):
    matrix = np.column_stack((np.ones(len(t)), t - np.mean(t),
                              np.sin(2*np.pi*frequency*t),
                              np.cos(2*np.pi*frequency*t)))
    fitted = np.linalg.lstsq(matrix, x, rcond=None)[0]
    return fitted[2], fitted[3]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    summaries, channel_rows, health_rows, manifest = [], [], [], []
    example = None
    for label, relative in CASES.items():
        folder = ROOT / relative
        metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
        health = json.loads((folder / "health.json").read_text(encoding="utf-8"))
        with np.load(folder / "welch.npz") as archive:
            powers = archive["segment_bandpower"]
        quality = assess_channel_quality(dict(channel_names=metadata["channel_names"],
            health=health, welch_segment_bandpower=powers))
        good = [i for i, row in enumerate(quality) if not row["automatic_suspect"]]
        if not good:
            raise ValueError(f"No non-suspect channels: {label}")
        for row in quality:
            health_rows.append(dict(case=label, **row))
        with np.load(folder / "low_rate.npz") as archive:
            fs = float(archive["low_rate_hz"])
            x = archive["low_rate_v"][:, good]
        sos = signal.butter(6, 10, fs=fs, output="sos")
        low = signal.sosfiltfilt(sos, x - np.mean(x, axis=0), axis=0)
        decimation = int(round(fs/100))
        low = signal.resample_poly(low, 1, decimation, axis=0)
        fs_low = fs / decimation
        config = metadata["config"]
        start = int(round(config["trim_start_seconds"]*fs_low))
        end = len(low) - int(round(config["trim_end_seconds"]*fs_low))
        stable = signal.detrend(low[start:end], axis=0, type="linear")
        t = np.arange(start, end)/fs_low
        f, psd = signal.welch(stable, fs=fs_low,
            nperseg=min(len(stable), int(20*fs_low)), axis=0, detrend="linear")
        use = (f >= .1) & (f <= 10)
        band_rms = np.sqrt(np.trapezoid(psd[use], f[use], axis=0))
        fit_sin, fit_cos = coefficients(stable, t, 2)
        fits = np.hypot(fit_sin, fit_cos)
        for j, original in enumerate(good):
            channel_rows.append(dict(case=label, channel_1based=original+1,
                archived_duration_s=metadata["duration_s"], stable_duration_s=len(t)/fs_low,
                raw_whole_record_std_uv=health[original]["std"]*1e6,
                output_lowband_0p1_10hz_rms_uv=band_rms[j]*1e6,
                output_2hz_fitted_peak_uv=fits[j]*1e6))
        summaries.append(dict(case=label, healthy_n=len(good),
            excluded_channels=",".join(str(i+1) for i in range(len(quality)) if i not in good),
            duration_s=metadata["duration_s"], stable_duration_s=len(t)/fs_low,
            raw_whole_record_std_median_uv=float(np.median([health[i]["std"] for i in good]))*1e6,
            lowband_0p1_10hz_rms_median_uv=float(np.median(band_rms))*1e6,
            fitted_2hz_peak_median_uv=float(np.median(fits))*1e6))
        archive_sos = np.asarray(metadata["lowpass_filter"]["sos"], dtype=float)
        archive_sos[0, :3] /= metadata["lowpass_filter"]["dc_gain_before_normalization"]
        archive_gain = signal.sosfreqz(archive_sos, worN=np.array([1., 2., 5., 10.]),
                                      fs=metadata["sample_rate_hz"])[1]
        manifest.append(dict(case=label, source_archive=relative,
            low_rate_sha256=hashlib.sha256((folder / "low_rate.npz").read_bytes()).hexdigest(),
            sample_rate_hz=fs, archive_filter_frequencies_hz=[1, 2, 5, 10],
            archive_filter_gain=abs(archive_gain).tolist()))
        if label == "TC2_VFD_background":
            raw_start = int(config["trim_start_seconds"]*fs)
            example = (np.arange(5*int(fs))/fs, x[raw_start:raw_start+5*int(fs), 0],
                       t[:500]-t[0], stable[:500, 0], good[0]+1)

    # Deliberately a voltage-output-domain numerical test, not an injected field.
    fs, update_rate, duration, amplitude = 4000., 200., 60., 10e-6
    t = np.arange(int(fs*duration))/fs
    step_samples = int(fs/update_rate)
    held_t = (np.arange(len(t))//step_samples)/update_rate
    sos = signal.butter(6, 10, fs=fs, output="sos")
    keep = (t >= 5) & (t < duration-5)
    digital = []
    demo = None
    for frequency in (1., 2., 5.):
        ideal = amplitude*np.sin(2*np.pi*frequency*t)
        stairs = amplitude*np.sin(2*np.pi*frequency*held_t)
        smooth_ideal = signal.sosfiltfilt(sos, ideal)
        smooth_stairs = signal.sosfiltfilt(sos, stairs)
        a, b = coefficients(smooth_ideal[keep], t[keep], frequency)
        c, d = coefficients(smooth_stairs[keep], t[keep], frequency)
        ratio = np.hypot(c, d)/np.hypot(a, b)
        lag = np.degrees(np.angle(complex(c, d)/complex(a, b)))
        n = update_rate/frequency
        theoretical_gain = np.sinc(1/n)
        assert abs(ratio-theoretical_gain) < 3e-6
        rms = np.sqrt(np.mean(smooth_ideal[keep]**2))
        shifted_ideal = signal.sosfiltfilt(sos,
            amplitude*np.sin(2*np.pi*frequency*(t-(step_samples-1)/(2*fs))))
        digital.append(dict(frequency_hz=frequency, points_per_cycle=n,
            predicted_continuous_hold_gain=theoretical_gain,
            predicted_continuous_hold_phase_deg=-180/n,
            ideal_continuous_hold_thd_pct=100*np.sqrt(1/theoretical_gain**2-1),
            numerical_lowpass_base_gain_ratio=ratio,
            numerical_grid_phase_deg=lag,
            lowpassed_unaligned_nrmse_pct=100*np.sqrt(np.mean(
                (smooth_stairs[keep]-smooth_ideal[keep])**2))/rms,
            lowpassed_grid_delay_aligned_nrmse_pct=100*np.sqrt(np.mean(
                (smooth_stairs[keep]-shifted_ideal[keep])**2))/rms,
            scope="SYNTHETIC voltage-output-domain; no hardware/field validation"))
        if frequency == 2:
            demo = (t, ideal, stairs, smooth_ideal, smooth_stairs)

    write_csv("record_summary.csv", summaries)
    write_csv("channel_metrics.csv", channel_rows)
    write_csv("dynamic_channel_health.csv", health_rows)
    write_csv("digital_filter_only_check.csv", digital)
    (OUT / "manifest.json").write_text(json.dumps(dict(
        real_data_scope="Five archived records, per-file health; no classification or sensitivity calibration",
        synthetic_scope="Ideal uniform ZOH-like voltage added at output-domain; not a physical electric field",
        processing="4 kHz retained voltage -> 6th order 10 Hz Butterworth forward/backward -> polyphase 100 Hz; stable interval per metadata; PSD 0.1-10 Hz",
        caveats=["2 Hz fits in historical recordings are descriptive, not target detections",
                 "Whole-record raw STD and stable lowband PSD RMS use different intervals and bandwidths",
                 "100 Hz output is numerical processing, not a measured sensor bandwidth",
                 "No DPS150 sinusoidal-load TC acquisition exists among these inspected files",
                 "Digital grid hold is one 4kHz sample shorter in phase than continuous hold"],
        inputs=manifest), ensure_ascii=False, indent=2), encoding="utf-8")
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), constrained_layout=True)
    tr, raw, tl, low, ch = example
    axes[0].plot(tr, (raw-np.mean(raw))*1e6, lw=.5, color="#516879")
    axes[0].set(title=f"Measured TC2 background, channel {ch}: retained 4 kHz voltage",
                ylabel="Centered output (uV)", xlabel="Time within excerpt (s)")
    axes[1].plot(tl, low*1e6, lw=1, color="#226b45")
    axes[1].set(title="Same record: digital 10 Hz low-pass (not a target detection)",
                ylabel="Detrended output (uV)", xlabel="Time within excerpt (s)")
    t, ideal, stairs, smooth_ideal, smooth_stairs = demo
    use = (t>=20) & (t<21)
    axes[2].plot(t[use]-20, smooth_ideal[use]*1e6, label="Synthetic continuous 2 Hz", color="#245a9b")
    axes[2].plot(t[use]-20, smooth_stairs[use]*1e6, "--", label="Synthetic staircase, 200 updates/s", color="#b94d2c")
    axes[2].set(title="Numerical comparison only: after the same 10 Hz low-pass",
                ylabel="Synthetic output (uV)", xlabel="Time (s)")
    axes[2].legend(loc="upper right")
    for ax in axes:
        ax.grid(alpha=.2)
    fig.savefig(OUT / "measured_voltage_and_digital_only_comparison.png", dpi=170)
    plt.close(fig)
    print(json.dumps(dict(records=summaries, digital_only=digital, output=str(OUT)),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
