import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from src import main as src_main
from src.pipelines import fft_average_pipeline, time_quality_pipeline


def _write_fft_csv(path, offset=0.0):
    frequency = np.linspace(1.0, 200.0, 32)
    data = {"frequency": frequency}
    for channel in range(1, 3):
        data[f"amplitude{channel}"] = np.sin(frequency / 30.0 + offset + channel) ** 2 + 0.01
        data[f"phase{channel}"] = np.cos(frequency / 40.0 + offset + channel)
    pd.DataFrame(data).to_csv(path, index=False)


def _write_time_csv(path):
    pd.DataFrame({
        "time": np.arange(20, dtype=float) / 10.0,
        "channel1": np.linspace(0.0, 1.0, 20),
        "channel2": np.linspace(1.0, 2.0, 20),
    }).to_csv(path, index=False)


def test_freqplots_cache_hit_force_and_parameter_change(tmp_path, monkeypatch):
    input_dir = tmp_path / "input" / "sample"
    input_dir.mkdir(parents=True)
    _write_fft_csv(input_dir / "FFT_1.csv", 0.0)
    _write_fft_csv(input_dir / "FFT_2.csv", 0.2)
    output_dir = tmp_path / "out"

    def run(*extra):
        monkeypatch.setenv("DATAPROCESS_TIMING_SUMMARY", str(tmp_path / "timing.json"))
        monkeypatch.setattr(sys, "argv", ["src.main", "freqplots", "--input", str(input_dir), "--output", str(output_dir), "--plots", "none", *extra])
        src_main.main()

    run()
    report = output_dir / "sample" / "frequency_plots_report.json"
    assert report.exists()
    assert (output_dir / ".cache" / "freqplots_cache.json").exists()
    first_mtime = report.stat().st_mtime

    run()
    second_mtime = report.stat().st_mtime
    assert second_mtime == first_mtime

    time.sleep(1.1)
    run("--force")
    assert report.stat().st_mtime > second_mtime

    monkeypatch.setattr(sys, "argv", ["src.main", "freqplots", "--input", str(input_dir), "--output", str(output_dir), "--plots", "minimal"])
    src_main.main()
    assert (output_dir / "sample" / "group_mean_amplitude_summary.png").exists()
    metadata = json.loads((output_dir / ".cache" / "freqplots_cache.json").read_text(encoding="utf-8"))
    assert metadata["params"]["plots"] == "minimal"


def test_timeplots_export_excel_cache_signature(tmp_path):
    input_dir = tmp_path / "time"
    input_dir.mkdir()
    _write_time_csv(input_dir / "a.csv")
    csv_output = tmp_path / "out" / "time_series_metrics.csv"
    xlsx_output = tmp_path / "out" / "time_series_metrics.xlsx"

    time_quality_pipeline.main(["--input", str(input_dir), "--output", str(csv_output)])
    assert csv_output.exists()
    assert (csv_output.parent / ".cache" / "timeplots_cache.json").exists()

    time_quality_pipeline.main(["--input", str(input_dir), "--output", str(xlsx_output), "--export-excel"])
    assert xlsx_output.exists()
    metadata = json.loads((xlsx_output.parent / ".cache" / "timeplots_cache.json").read_text(encoding="utf-8"))
    assert metadata["params"]["export_excel"] is True


def test_freqavedata_input_update_cache_miss(tmp_path, monkeypatch):
    input_root = tmp_path / "frequency"
    group = input_root / "sample"
    group.mkdir(parents=True)
    _write_fft_csv(group / "FFT_1.csv", 0.0)
    _write_fft_csv(group / "FFT_2.csv", 0.1)
    output_dir = tmp_path / "average"

    monkeypatch.setattr(
        fft_average_pipeline,
        "load_config",
        lambda: {
            "tdms_reader_frequency_output_dir": str(input_root),
            "tdms_reader_frequency_average_output_dir": str(output_dir),
            "raw_data_dir": str(tmp_path / "raw"),
        },
    )

    fft_average_pipeline.main()
    average = output_dir / "sample" / "average_fft_sample_2files.csv"
    assert average.exists()

    fft_average_pipeline.main()
    second_mtime = average.stat().st_mtime
    fft_average_pipeline.main()
    assert average.stat().st_mtime == second_mtime

    time.sleep(1.1)
    updated = group / "FFT_1.csv"
    os.utime(updated, None)
    fft_average_pipeline.main()
    assert average.stat().st_mtime > second_mtime
