"""Separate source illustration, actual DC FEM outputs and hypothetical commands."""

from pathlib import Path
import csv
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis/source_model_power_comparison_20261105"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "Microsoft YaHei", "font.size": 11,
                         "axes.unicode_minus": False, "axes.spines.top": False,
                         "axes.spines.right": False})
    with (ROOT / "research/01_vessel_background/iccp_v1/results/circuit_audit_summary.csv").open(
            encoding="utf-8-sig") as handle:
        rows = [r for r in csv.DictReader(handle) if r["case"] in
                ("base_0A", "base_5A", "base_10A", "base_20A")]
    rows.sort(key=lambda r: float(r["I_ICCP_A"]))
    fs, update, f0 = 20000, 200, 2
    t = np.arange(fs*2)/fs
    target = 6+4*np.sin(2*np.pi*f0*t)
    held_t = (np.arange(len(t))//(fs//update))/update
    fine = 6+4*np.sin(2*np.pi*f0*held_t)
    quantized = np.round(fine)
    # Arbitrary illustrative branch-current waveform, not a field or measurement.
    source = 1+.12*np.sin(2*np.pi*f0*t)+.035*np.sin(4*np.pi*f0*t+.3)+.02*np.sin(8*np.pi*f0*t-.2)

    fig, axes = plt.subplots(3, 1, figsize=(12, 10), constrained_layout=True)
    fig.suptitle("真实机制、现有COMSOL、电源设定：三者不是同一层证据", fontsize=17)
    axes[0].plot(t, source, color="#19674b", lw=1.5)
    axes[0].axhline(1, color="#888888", ls="--", lw=.8)
    axes[0].set(title="A  真实源的可能形式：直流背景＋轴频及谐波【机制示意，非实测】",
                xlabel="时间 / s", ylabel="某支路电流 / 平均值", xlim=(0, 2), ylim=(.78, 1.22))
    axes[0].text(.99, .96, "示意取轴频2 Hz；幅值与谐波比例任意\n实际总电流未必调制，空间分布也可能变化",
                 transform=axes[0].transAxes, ha="right", va="top", fontsize=10,
                 bbox=dict(facecolor="white", alpha=.9, edgecolor="none"))
    index = np.arange(len(rows))
    prop = np.array([-float(r["prop_net_anodic_A"]) for r in rows])
    axes[1].bar(index, prop, color="#546d91", width=.52)
    axes[1].set_xticks(index, [f"{float(r['I_ICCP_A']):g} A" for r in rows])
    axes[1].set(title="B  本地COMSOL实际结果：四个直流工况，螺旋桨不旋转【已求解】",
                xlabel="设定的ICCP直流电流（不是时间）", ylabel="进入静止螺旋桨的\n净电流 / A", ylim=(0, 5.3))
    for i, value in enumerate(prop):
        axes[1].text(i, value+.07, f"{value:.3f}", ha="center")
    axes[1].text(.99, .96, "没有轴频交流幅值、相位或时间波形结果",
                 transform=axes[1].transAxes, ha="right", va="top", fontsize=10)
    show = t <= 1
    axes[2].plot(t[show], target[show], color="#255ca0", lw=1.6, label="希望得到的连续正弦")
    axes[2].plot(t[show], quantized[show], color="#be582b", lw=1.2,
                 label="按1 mA取整的阶梯设定")
    axes[2].set(title="C  电源可以尝试执行的设定序列【条件示例，非端口实测】",
                xlabel="时间 / s", ylabel="电流设定 / mA", xlim=(0, 1), ylim=(1.5, 12.8))
    axes[2].text(.02, .96, "示例：2 Hz，6±4 mA，标称200点/秒\n图示假定均匀执行；实际电流跟随尚未验证",
                 transform=axes[2].transAxes, va="top", fontsize=10)
    axes[2].legend(loc="upper right", fontsize=10)
    for ax in axes:
        ax.grid(axis="y", alpha=.2)
    fig.savefig(OUT / "01_three_evidence_levels.png", dpi=170)
    plt.close(fig)

    fig, axes = plt.subplots(3, 1, figsize=(12, 10), constrained_layout=True)
    fig.suptitle("阶梯近似与取整是两种误差：以下全部为合成设定序列", fontsize=17)
    interval = (t >= .02) & (t <= .09)
    axes[0].plot(t[interval]*1000, target[interval], color="#255ca0", label="连续正弦")
    axes[0].plot(t[interval]*1000, fine[interval], color="#19674b", label="未取整：理想5 ms保持")
    axes[0].set(title="A  局部放大：100个更新点构成一个2 Hz周期",
                xlabel="时间 / ms", ylabel="电流设定 / mA")
    axes[0].legend(loc="lower right")
    axes[1].plot(t[show], target[show], color="#255ca0", lw=1.5, label="连续正弦")
    axes[1].plot(t[show], quantized[show], color="#be582b", label="1 mA取整，仅9个名义电平")
    axes[1].set(title="B  小幅值调制时，电平数比每周期点数更容易成为限制",
                xlabel="时间 / s", ylabel="电流设定 / mA", xlim=(0, 1))
    axes[1].legend(loc="upper right")
    spectrum_results = {}
    for name, values, color, marker in (("理想阶梯", fine, "#19674b", "o"),
                                        ("1 mA取整阶梯", quantized, "#be582b", "x")):
        centered = values-np.mean(values)
        transform = np.fft.rfft(centered)
        amplitude = 2*abs(transform)/len(values)
        frequency = np.fft.rfftfreq(len(values), 1/fs)
        base = int(round(f0*len(values)/fs))
        rms = np.sqrt(np.mean(centered**2))
        thd = np.sqrt(max(0., 2*rms*rms/amplitude[base]**2-1))
        harmonics = np.arange(1, 11)*f0
        bins = np.rint(harmonics*len(values)/fs).astype(int)
        axes[2].plot(harmonics[1:], amplitude[bins[1:]], marker=marker, ls="none", color=color, label=name)
        spectrum_results[name] = dict(base_peak_ma=float(amplitude[base]),
            full_band_synthetic_thd_pct=float(thd*100),
            harmonics_hz=harmonics.tolist(), harmonic_peak_ma=amplitude[bins].tolist())
    axes[2].set(title="C  放大4–20 Hz谐波（2 Hz基频不显示）：取整误差不只在高频",
                xlabel="频率 / Hz", ylabel="合成设定幅值 / mA", xlim=(3, 21), ylim=(-.003, .065))
    axes[2].set_xticks(np.arange(4, 21, 2))
    axes[2].legend(loc="upper right")
    for ax in axes:
        ax.grid(alpha=.2)
    fig.savefig(OUT / "02_staircase_and_quantization.png", dpi=170)
    plt.close(fig)
    result = dict(scope="No COMSOL solve and no hardware command; source wave arbitrary illustration; power wave hypothetical setpoints",
        actual_comsol_steady_points=[dict(iccp_a=float(r["I_ICCP_A"]),
            propeller_net_incoming_a=-float(r["prop_net_anodic_A"])) for r in rows],
        synthetic_command_assumptions=dict(frequency_hz=f0, uniform_update_per_s=update,
            dc_ma=6, ac_peak_ma=4, quantum_ma=1), synthetic_spectrum=spectrum_results)
    (OUT / "figure_data.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
