import unittest
from dataclasses import dataclass

import numpy as np

from scripts.exact_analysis_metrics import low_frequency_blind_rows, temporal_band_rows


@dataclass(frozen=True)
class Case:
    case_id: str
    session: str
    detector: str
    condition: str


def result(values: np.ndarray, band_scale: float) -> dict[str, object]:
    feature_values = {
        "slow_mean": values,
        "subkhz_rms": np.exp(values * 0.01),
        "broadband_rms": np.exp(values * 0.02),
        "fast_residual_rms": np.exp(values * 0.03),
    }
    segments = np.ones((20, values.shape[1], 5)) * band_scale
    return {
        "features": feature_values,
        "envelope_fs": 10.0,
        "welch_segment_bandpower": segments,
    }


class ExactAnalysisMetricsTests(unittest.TestCase):
    def test_temporal_band_contrast_uses_control_file(self) -> None:
        time_s = np.arange(800) / 10.0
        values = np.column_stack([np.sin(2 * np.pi * 0.4 * time_s)] * 4)
        cases = [Case("bg", "one", "TC1", "background"), Case("run", "one", "TC1", "30hz")]
        results = {"bg": result(values, 1.0), "run": result(values, 2.0)}

        rows = temporal_band_rows(cases, results, lambda result: [0, 1, 2, 3])
        run_row = next(row for row in rows if row["case_id"] == "run" and row["band"] == "1_20khz")

        self.assertAlmostEqual(run_row["median_contrast_to_control_segments_db"], 10 * np.log10(2))
        self.assertEqual(run_row["temporal_superiority_fraction"], 1.0)

    def test_low_frequency_scan_finds_injected_candidate(self) -> None:
        rng = np.random.default_rng(7)
        time_s = np.arange(1000) / 10.0
        background = rng.normal(scale=0.05, size=(len(time_s), 4))
        active = background + np.sin(2 * np.pi * 0.4 * time_s)[:, None]
        cases = [Case("bg", "one", "TC1", "background"), Case("run", "one", "TC1", "30hz")]
        results = {"bg": result(background, 1.0), "run": result(active, 2.0)}

        rows = low_frequency_blind_rows(
            cases,
            results,
            lambda result: [0, 1, 2, 3],
            trim_start_s=0.0,
            trim_end_s=0.0,
            peak_limit=5,
        )
        candidates = [row for row in rows if row["feature"] == "slow_mean"]

        self.assertTrue(any(abs(float(row["frequency_hz"]) - 0.4) < 0.02 for row in candidates))


if __name__ == "__main__":
    unittest.main()
