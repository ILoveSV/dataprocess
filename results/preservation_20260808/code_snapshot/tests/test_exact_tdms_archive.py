import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from nptdms import ChannelObject, TdmsWriter
from scipy import signal

from scripts.exact_tdms_archive import (
    ExactArchiveConfig,
    _integrated_bandpowers,
    _one_sided_psd,
    archive_complete,
    build_exact_archive,
    load_exact_archive,
    validate_exact_archive,
)


class ExactTdmsArchiveTests(unittest.TestCase):
    def test_one_sided_psd_matches_scipy_periodogram(self) -> None:
        rng = np.random.default_rng(42)
        sample_rate = 4_000.0
        values = rng.normal(size=(4096, 2))
        window = signal.windows.hann(len(values), sym=False)

        actual = _one_sided_psd(values, sample_rate, window)
        expected = np.column_stack([
            signal.periodogram(
                values[:, index],
                fs=sample_rate,
                window=window,
                detrend="linear",
                scaling="density",
            )[1]
            for index in range(values.shape[1])
        ])

        np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-18)

    def test_integrated_bandpowers_has_channel_band_shape(self) -> None:
        frequency = np.linspace(0.0, 200_000.0, 200_001)
        psd = np.ones((len(frequency), 3))
        result = _integrated_bandpowers(frequency, psd)

        self.assertEqual(result.shape, (3, 5))
        np.testing.assert_allclose(result[0], result[1])

    def test_build_and_reload_small_tdms_archive(self) -> None:
        sample_rate = 4_000.0
        sample_count = 40_000
        time_s = np.arange(sample_count) / sample_rate
        channels = [
            5.0 + 1e-3 * np.sin(2.0 * np.pi * 0.5 * time_s),
            5.0 + 2e-3 * np.sin(2.0 * np.pi * 50.0 * time_s),
        ]
        properties = {
            "wf_increment": 1.0 / sample_rate,
            "wf_start_time": np.datetime64("2026-08-08T00:00:00"),
            "wf_samples": sample_count,
        }
        config = ExactArchiveConfig(
            trim_start_seconds=1.0,
            trim_end_seconds=1.0,
            block_seconds=0.1,
            subblock_seconds=0.01,
            welch_nperseg=1024,
            low_rate_hz=400.0,
            analysis_rate_hz=10.0,
            lowpass_pass_hz=180.0,
            lowpass_stop_hz=200.0,
            snippet_seconds=0.1,
            peak_count_per_segment=8,
        )

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "small.tdms"
            output = root / "archive"
            with TdmsWriter(source) as writer:
                writer.write_segment([
                    ChannelObject("group", f"channel{index + 1}", values, properties)
                    for index, values in enumerate(channels)
                ])

            build_exact_archive(source, output, config)
            self.assertTrue(archive_complete(output))
            self.assertEqual(validate_exact_archive(output), [])
            result = load_exact_archive(output)

            self.assertEqual(result["psd"].shape, (2, 513))
            self.assertEqual(result["features"]["slow_mean"].shape[1], 2)
            self.assertGreater(len(result["welch_segment_time_s"]), 3)
            self.assertEqual(len(result["health"]), 2)
            self.assertEqual(result["welch_epoch_psd_mean"].shape, (8, 2, 513))
            self.assertTrue(np.all(np.isfinite(result["welch_epoch_psd_mean"])))


if __name__ == "__main__":
    unittest.main()
