import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src import main as src_main


def _write_fft_csv(path, offset=0.0):
    frequency = np.linspace(1.0, 1000.0, 64)
    data = {"frequency": frequency}
    for channel in range(1, 3):
        amplitude = np.sin(frequency / 100.0 + channel + offset) ** 2 + 0.01
        phase = np.cos(frequency / 120.0 + channel + offset)
        data[f"amplitude{channel}"] = amplitude
        data[f"phase{channel}"] = phase
    pd.DataFrame(data).to_csv(path, index=False)


def test_main_freqplots_respects_explicit_output(tmp_path, monkeypatch):
    input_dir = tmp_path / "input_fft" / "sample_group"
    input_dir.mkdir(parents=True)
    _write_fft_csv(input_dir / "FFT_sample_1.csv", offset=0.0)
    _write_fft_csv(input_dir / "FFT_sample_2.csv", offset=0.2)

    explicit_output = tmp_path / "explicit_output"
    config_results = tmp_path / "config_results"

    repo_root = Path(__file__).resolve().parents[1]
    rawpath = repo_root / "config" / "rawpath.yaml"
    original_rawpath = rawpath.read_text(encoding="utf-8")
    raw_config = yaml.safe_load(original_rawpath)
    raw_config["frequency_results_dir"] = str(config_results).replace("\\", "/")
    rawpath.write_text(yaml.safe_dump(raw_config, allow_unicode=True, sort_keys=False), encoding="utf-8")

    try:
        monkeypatch.setenv("DATAPROCESS_TIMING_SUMMARY", str(tmp_path / "timing.json"))
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "src.main",
                "freqplots",
                "--input",
                str(input_dir),
                "--output",
                str(explicit_output),
                "--plots",
                "none",
            ],
        )

        src_main.main()

        expected_group = explicit_output / "sample_group"
        assert (expected_group / "frequency_plots_report.json").exists()
        assert (expected_group / "dominant_frequencies.csv").exists()
        assert (explicit_output / "fft_analysis_summary.json").exists()

        assert not list(config_results.glob("**/frequency_plots_report.json"))
        assert not list(config_results.glob("**/dominant_frequencies.csv"))

        summary = json.loads((explicit_output / "fft_analysis_summary.json").read_text(encoding="utf-8"))
        assert summary["plot_mode"] == "none"
        assert summary["total_files"] == 2
    finally:
        rawpath.write_text(original_rawpath, encoding="utf-8")
