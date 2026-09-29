from __future__ import annotations

import unittest

import numpy as np

from scripts.channel_quality import assess_channel_quality, common_valid_channel_indices


def make_result(bad_channel: int | None = None, unstable_channel: int | None = None):
    health = []
    for index in range(12):
        scale = 1.0 + 0.01 * index
        if index == bad_channel:
            scale = 100.0
        health.append({
            "std": scale,
            "difference_rms": scale,
            "range": scale,
            "nonfinite_fraction": 0.0,
            "flat_difference_fraction": 0.0,
            "clip_fraction": 0.0,
        })
    segment_power = np.ones((20, 12, 5))
    phase = np.linspace(0.0, 2.0 * np.pi, 20)
    for index in range(12):
        segment_power[:, index, :] *= np.exp(
            (0.005 + 0.0002 * index) * np.sin(phase)[:, None]
        )
    if unstable_channel is not None:
        segment_power[::2, unstable_channel, :] = 100.0
    return {
        "channel_names": [f"channel{index + 1}" for index in range(12)],
        "health": health,
        "welch_segment_bandpower": segment_power,
    }


class ChannelQualityTests(unittest.TestCase):
    def test_hardware_metric_outlier_is_excluded(self) -> None:
        rows = assess_channel_quality(make_result(bad_channel=4))
        self.assertTrue(rows[4]["automatic_bad"])
        self.assertFalse(rows[3]["automatic_bad"])

    def test_temporal_variability_alone_is_suspect_not_bad(self) -> None:
        rows = assess_channel_quality(make_result(unstable_channel=2))
        self.assertFalse(rows[2]["automatic_bad"])
        self.assertTrue(rows[2]["automatic_suspect"])

    def test_comparison_uses_healthy_intersection(self) -> None:
        first = make_result(bad_channel=1)
        second = make_result(bad_channel=4)
        self.assertEqual(common_valid_channel_indices(first, second), [0, 2, 3, 5, 6, 7, 8, 9, 10, 11])


if __name__ == "__main__":
    unittest.main()
