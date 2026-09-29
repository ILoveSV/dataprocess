"""Analyze transient hydraulic pulse exports from WaterLoopPulsationV10.

The script keeps the hydraulic solve and electrokinetic conversion separate. It
uses complete cycles at the end of each transient run, reports cycle-to-cycle
repeatability, and converts pressure harmonics to equivalent streaming current
with the same thin-double-layer parameters used by the V7 COMSOL model.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "results" / "pulsation_v10" / "raw"
SUMMARY_FILE = ROOT / "results" / "pulsation_v10" / "hydraulic_harmonics.csv"
CASE_FILE = ROOT / "results" / "pulsation_v10" / "hydraulic_case_summary.csv"

PULSE_PERIOD_S = 3.1
SAMPLES_PER_PERIOD = 100
ANALYSIS_PERIODS = 3
MAX_HARMONIC = 10

# Values are intentionally identical to WaterLoopStreamingPotentialV7.java.
EPSILON_0 = 8.8541878128e-12
EPSILON_R_WATER = 80.2
ZETA_WALL_V = -30e-3
MU_WATER_PA_S = 1.002e-3
SIGMA_WATER_S_M = 0.05
PIPE_DIAMETER_M = 0.040
PIPE_LENGTH_M = 2.8

C_STREAM_V_PA = (
    EPSILON_0 * EPSILON_R_WATER * ZETA_WALL_V
    / (MU_WATER_PA_S * SIGMA_WATER_S_M)
)
PIPE_AREA_M2 = math.pi * (PIPE_DIAMETER_M / 2) ** 2
CURRENT_PER_PRESSURE_A_PA = (
    SIGMA_WATER_S_M * PIPE_AREA_M2 * abs(C_STREAM_V_PA) / PIPE_LENGTH_M
)


def read_comsol_table(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rows: list[list[float]] = []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        for line in handle:
            if line.startswith("%") or not line.strip():
                continue
            values = next(csv.reader([line]))
            rows.append([float(value) for value in values[:3]])
    data = np.asarray(rows, dtype=float)
    if data.ndim != 2 or data.shape[1] != 3:
        raise ValueError(f"Unexpected COMSOL table format: {path}")
    return data[:, 0], data[:, 1], data[:, 2]


def parse_case(path: Path) -> tuple[int, float]:
    stem = path.stem
    mode_text, amplitude_text = stem.split("_A")
    return int(mode_text.removeprefix("op")), int(amplitude_text) / 100.0


def analyze(path: Path) -> tuple[dict[str, float], list[dict[str, float]]]:
    mode_hz, amplitude = parse_case(path)
    time_s, velocity_m_s, pressure_pa = read_comsol_table(path)
    required = ANALYSIS_PERIODS * SAMPLES_PER_PERIOD
    if time_s.size < required + 1:
        raise ValueError(f"Not enough samples for {ANALYSIS_PERIODS} periods: {path}")

    # Drop the duplicated final cycle endpoint so the DFT window is periodic.
    time_window = time_s[-(required + 1):-1]
    velocity_window = velocity_m_s[-(required + 1):-1]
    pressure_window = pressure_pa[-(required + 1):-1]
    dt = float(np.mean(np.diff(time_window)))

    pressure_cycles = pressure_window.reshape(ANALYSIS_PERIODS, SAMPLES_PER_PERIOD)
    velocity_cycles = velocity_window.reshape(ANALYSIS_PERIODS, SAMPLES_PER_PERIOD)
    pressure_scale = max(float(np.ptp(pressure_cycles[-1])), 1e-30)
    velocity_scale = max(float(np.ptp(velocity_cycles[-1])), 1e-30)
    pressure_repeatability = float(
        np.max(np.abs(pressure_cycles[-1] - pressure_cycles[-2])) / pressure_scale
    )
    velocity_repeatability = float(
        np.max(np.abs(velocity_cycles[-1] - velocity_cycles[-2])) / velocity_scale
    )

    pressure_ac = pressure_window - np.mean(pressure_window)
    spectrum = np.fft.rfft(pressure_ac) / pressure_ac.size
    frequencies = np.fft.rfftfreq(pressure_ac.size, dt)

    harmonics: list[dict[str, float]] = []
    for harmonic in range(1, MAX_HARMONIC + 1):
        target = harmonic / PULSE_PERIOD_S
        index = int(np.argmin(np.abs(frequencies - target)))
        pressure_peak = 2.0 * abs(spectrum[index])
        pressure_rms = pressure_peak / math.sqrt(2.0)
        streaming_voltage_rms = abs(C_STREAM_V_PA) * pressure_rms
        streaming_current_rms = CURRENT_PER_PRESSURE_A_PA * pressure_rms
        harmonics.append(
            {
                "operating_mode_hz": mode_hz,
                "velocity_amplitude_A": amplitude,
                "harmonic": harmonic,
                "frequency_hz": frequencies[index],
                "pressure_rms_pa": pressure_rms,
                "streaming_voltage_rms_v": streaming_voltage_rms,
                "streaming_current_rms_a": streaming_current_rms,
                "pressure_phase_rad": float(np.angle(spectrum[index])),
            }
        )

    case = {
        "operating_mode_hz": mode_hz,
        "velocity_amplitude_A": amplitude,
        "mean_velocity_m_s": float(np.mean(velocity_window)),
        "mean_pressure_pa": float(np.mean(pressure_window)),
        "pressure_peak_to_peak_pa": float(np.ptp(pressure_window)),
        "pressure_repeatability_fraction": pressure_repeatability,
        "velocity_repeatability_fraction": velocity_repeatability,
        "fundamental_pressure_rms_pa": harmonics[0]["pressure_rms_pa"],
        "fundamental_streaming_voltage_rms_v": harmonics[0]["streaming_voltage_rms_v"],
        "fundamental_streaming_current_rms_a": harmonics[0]["streaming_current_rms_a"],
        "total_harmonic_streaming_current_rms_a": math.sqrt(
            sum(item["streaming_current_rms_a"] ** 2 for item in harmonics)
        ),
    }
    return case, harmonics


def write_rows(path: Path, rows: list[dict[str, float]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    cases: list[dict[str, float]] = []
    harmonics: list[dict[str, float]] = []
    for path in sorted(RAW_DIR.glob("op*_A*.csv")):
        case, case_harmonics = analyze(path)
        cases.append(case)
        harmonics.extend(case_harmonics)
    if not cases:
        raise SystemExit(f"No pulse exports found under {RAW_DIR}")
    write_rows(CASE_FILE, cases)
    write_rows(SUMMARY_FILE, harmonics)
    for case in cases:
        print(
            "PULSE_CASE,"
            f"op={int(case['operating_mode_hz'])},"
            f"A={case['velocity_amplitude_A']:.3f},"
            f"p_mean={case['mean_pressure_pa']:.6g} Pa,"
            f"p1_rms={case['fundamental_pressure_rms_pa']:.6g} Pa,"
            f"I1_rms={case['fundamental_streaming_current_rms_a']:.6g} A,"
            f"repeat={case['pressure_repeatability_fraction']:.3g}"
        )


if __name__ == "__main__":
    main()
