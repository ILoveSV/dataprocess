"""Ideal staircase feasibility, quantization and required (not measured) rates.

No serial connection is opened. Existing no-load logs are read as evidence only.
Source for zero-order hold: Analog Devices, Equalizing Techniques Flatten DAC
Frequency Response. Nonlinear cell/power-supply dynamics are not assumed known.
"""
from pathlib import Path
import csv
import hashlib
import json
import math
import struct

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis/dps150_modulation_feasibility_20261104"
LOG = ROOT / "local/logs/dps150_20261104_130536.jsonl"


def metrics(n):
    g = float(np.sinc(1 / n))
    return {
        "points_per_cycle": n,
        "step_upper_bound_percent_of_modulation_peak": 200 * math.sin(math.pi / n),
        "fundamental_loss_percent": 100 * (1 - g),
        "fundamental_delay_degree": 180 / n,
        "thd_all_harmonics_percent": 100 * math.sqrt(1 / g**2 - 1),
        "first_unwanted_harmonic_order": n - 1,
        "thd_harmonics_2_to_10_percent": 100 * math.sqrt(sum(
            1 / m**2 for m in range(2, 11) if m % n in (1, n - 1)
        )),
    }


def quantized(n, amplitude_ma, quantum_ma=1.0):
    # This illustrative bias is exactly representable, avoiding bias rounding.
    bias_ma = 200.0
    k = np.arange(n)
    target = bias_ma + amplitude_ma * np.sin(2 * np.pi * k / n)
    # Nearest-level rounding, with half-level ties rounded upward.
    values = np.floor(target / quantum_ma + 0.5) * quantum_ma
    centered = values - values.mean()
    orders = np.arange(1, 11)
    coeff = (2 / n) * (np.exp(-2j * np.pi * orders[:, None] * k / n) @ centered)
    coeff *= np.sinc(orders / n) * np.exp(-1j * np.pi * orders / n)
    a1 = abs(coeff[0])
    return {
        "points_per_cycle": n, "bias_ma_example": bias_ma,
        "modulation_peak_ma_example": amplitude_ma, "quantum_ma_assumed": quantum_ma,
        "sample_error_upper_bound_percent_of_modulation_peak": 100 * quantum_ma / (2 * amplitude_ma),
        "actual_sample_error_max_percent": float(100 * np.max(abs(values - target)) / amplitude_ma),
        "fundamental_amplitude_error_percent": float(100 * (a1 / amplitude_ma - 1)),
        "thd_all_harmonics_percent": float(100 * np.sqrt(max(0, 2 * np.mean(centered**2) / a1**2 - 1))),
        "thd_harmonics_2_to_10_percent": float(100 * np.linalg.norm(coeff[1:]) / a1),
    }


def write_csv(name, rows):
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ideal = [metrics(n) for n in (10, 20, 37, 40, 50, 91, 100, 182, 200)]
    thresholds = []
    for budget in (10, 5, 2, 1):
        n = next(n for n in range(3, 10001) if metrics(n)["thd_all_harmonics_percent"] <= budget)
        thresholds.append({"thd_budget_percent_design_example": budget, "minimum_integer_N": n,
                           "actual_ideal_thd_percent": metrics(n)["thd_all_harmonics_percent"]})
    rates = []
    for f in (0.01, 0.05, 0.1, 1 / 3.1, 1.0, 5.0):
        for n in (40, 100):
            rates.append({"target_frequency_hz_example": f, "period_s": 1 / f,
                          "points_per_cycle": n, "required_update_rate_hz": n * f,
                          "required_interval_s": 1 / (n * f),
                          "phase_timing_error_1deg_s": 1 / (360 * f),
                          "first_image_frequency_hz": (n - 1) * f})
    quant = [quantized(n, a) for n in (40, 100) for a in (5.0, 10.0, 50.0, 100.0)]
    checks = []
    for n in (10, 20, 40, 100):
        # Independent dense integration verifies ZOH spectrum via Parseval.
        t = np.arange(n * 4000) / (n * 4000)
        y = np.repeat(np.sin(2 * np.pi * np.arange(n) / n), 4000)
        c1 = 2 * np.mean(y * np.exp(-2j * np.pi * t))
        gain_error = abs(abs(c1) - np.sinc(1 / n))
        thd = math.sqrt(max(0, 2 * np.mean(y**2) / abs(c1)**2 - 1))
        thd_error = abs(thd * 100 - metrics(n)["thd_all_harmonics_percent"])
        assert gain_error < 1e-7 and thd_error < 1e-5
        checks.append({"N": n, "dense_gain_error": gain_error, "dense_thd_error_percentage_points": thd_error})

    evidence = {"measured_update_rate_limit_hz": None,
                "physical_output_settling_time_s": None,
                "loaded_current_waveform_thd_percent": None}
    if LOG.exists():
        rows = [json.loads(line) for line in LOG.read_text(encoding="utf-8").splitlines()]
        evidence.update(log_path=str(LOG.relative_to(ROOT)), log_sha256=hashlib.sha256(LOG.read_bytes()).hexdigest(),
                        snapshots=[r for r in rows if r["event"] == "snapshot"])
        voltage_commands = []
        for row in rows:
            if row["event"] == "tx" and row.get("command") == 177 and row.get("kind") == 193:
                voltage_commands.append({"elapsed_s": row["elapsed_s"],
                                         "set_voltage_v": struct.unpack("<f", bytes.fromhex(row["payload_hex"]))[0]})
        evidence["voltage_commands_host_timestamps"] = voltage_commands
        evidence["timing_interpretation"] = "Prior script deliberately waited; timestamps are not maximum throughput or analog response."
    write_csv("ideal_staircase_metrics.csv", ideal)
    write_csv("required_update_rates.csv", rates)
    write_csv("quantization_examples.csv", quant)
    write_csv("design_budget_minimum_N.csv", thresholds)
    result = {"kind": "analytical_and_synthetic_only", "ideal": ideal, "thresholds": thresholds,
              "required_rates": rates, "quantization_examples": quant, "numerical_checks": checks,
              "existing_hardware_evidence": evidence,
              "sources": ["https://www.analog.com/en/resources/technical-articles/equalizing-techniques-flatten-dac-frequency-response.html",
                          "https://www.fnirsi.com.cn/product/41.html",
                          "https://www.gamry.com/application-notes/eis/basics-of-electrochemical-impedance-spectroscopy/"],
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUT / "calculation_results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    font = FontProperties(fname="C:/Windows/Fonts/msyh.ttc")
    fig, axes = plt.subplots(3, 1, figsize=(12, 7), sharex=True, sharey=True)
    x = np.linspace(0, 1, 3000)
    for ax, n, color in zip(axes, (10, 40, 100), ("#B65B29", "#167D8D", "#2860A4")):
        nodes = np.arange(n + 1) / n
        ax.plot(x, np.sin(2 * np.pi * x), color="#888888", label="目标正弦")
        ax.step(nodes, np.sin(2 * np.pi * nodes), where="post", color=color, label=f"理想阶梯 N={n}")
        ax.set_ylim(-1.2, 1.2)
        ax.set_ylabel("交流分量 / ΔI", fontproperties=font)
        ax.grid(alpha=.2)
        ax.legend(prop=font, loc="upper right", ncol=2)
    axes[-1].set_xlabel("时间 / 周期", fontproperties=font)
    fig.tight_layout()
    fig.savefig(OUT / "ideal_staircase_waveforms.png", dpi=180)
    plt.close(fig)
    print(json.dumps({"thresholds": thresholds, "quantization_examples": quant,
                      "hardware_limit_measured": False, "output": str(OUT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
