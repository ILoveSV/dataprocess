import numpy as np
import pandas as pd

from src.pipelines.first_test_pipeline import build_bandpower_gain_table, run_first_test
from src.plots.nist_psd_plot import plot_group_psd_review_ranges


def test_build_bandpower_gain_table_auto_pairs_same_distance_background():
    freqs = np.array([0.0, 50.0, 100.0, 1000.0, 10000.0, 50000.0, 100000.0])
    background_power = np.ones_like(freqs)
    active_power = np.ones_like(freqs) * 10.0
    group_results = {
        "2m0hz": {
            "psd": {
                "channel1": {
                    "plot_data": {"frequency": freqs, "median_power": background_power},
                    "file_count": 2,
                }
            }
        },
        "2m30hz": {
            "psd": {
                "channel1": {
                    "plot_data": {"frequency": freqs, "median_power": active_power},
                    "file_count": 2,
                }
            }
        },
    }

    table = build_bandpower_gain_table(group_results)

    row = table[(table["active_group"] == "2m30hz") & (table["band_name"] == "50_100Hz")].iloc[0]
    assert row["background_group"] == "2m0hz"
    assert row["median_bandpower_gain_dB"] > 9.9


def test_run_first_test_can_run_time_stats_only(tmp_path):
    input_root = tmp_path / "time"
    group = input_root / "groupA"
    group.mkdir(parents=True)
    for idx in range(2):
        pd.DataFrame({
            "time": [0.0, 0.1, 0.2, 0.3],
            "channel1": [idx, idx + 1, idx + 2, idx + 3],
            "channel2": [idx + 3, idx + 2, idx + 1, idx],
        }).to_csv(group / f"sample_{idx}.csv", index=False)

    output_root = tmp_path / "out"
    manifest = run_first_test(
        input_root=input_root,
        output_root=output_root,
        enable_4plot=False,
        enable_psd=False,
        enable_bandpower_gain=False,
        enable_time_stats=True,
    )

    assert manifest["enabled_steps"]["time_stats"] is True
    assert manifest["figure_count"] == 0
    file_features = pd.read_csv(output_root / "time_file_features.csv")
    group_summary = pd.read_csv(output_root / "time_group_summary.csv")
    assert {"mean", "median", "peak_to_peak", "ac_rms", "robust_sigma"}.issubset(file_features.columns)
    assert {"mean_of_file_means", "std_of_file_means", "cv_ac_rms", "max_peak_to_peak"}.issubset(group_summary.columns)


def test_psd_review_ranges_only_outputs_full_and_20k_windows(tmp_path):
    frequency = np.linspace(0.0, 200_000.0, 101)
    power = np.linspace(1.0, 2.0, 101)
    paths = plot_group_psd_review_ranges(
        {
            "frequency": frequency,
            "mean_power": power,
            "median_power": power,
            "p10_power": power * 0.9,
            "p90_power": power * 1.1,
        },
        {"file_count": 2, "psd_df": 2000.0},
        tmp_path,
        group="g",
        channel="channel1",
    )

    names = sorted(path.name for path in paths)
    assert len(names) == 11
    assert any("full_0_200k" in name for name in names)
    assert any("window_000_020k" in name for name in names)
    assert any("window_180_200k" in name for name in names)
    assert not any("zoom_0_100Hz" in name or "low_freq" in name for name in names)
