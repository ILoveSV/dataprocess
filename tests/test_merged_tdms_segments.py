import pytest

from src.pipelines.merged_tdms_to_time_pipeline import segment_bounds


def test_segment_bounds_splits_by_seconds():
    bounds = segment_bounds(
        total_samples=25,
        sampling_interval=0.1,
        segment_seconds=1.0,
    )

    assert bounds == [(0, 10), (10, 20), (20, 25)]


def test_segment_bounds_can_drop_short_tail():
    bounds = segment_bounds(
        total_samples=25,
        sampling_interval=0.1,
        segment_seconds=1.0,
        min_segment_seconds=0.6,
    )

    assert bounds == [(0, 10), (10, 20)]


def test_segment_bounds_rejects_invalid_duration():
    with pytest.raises(ValueError):
        segment_bounds(
            total_samples=25,
            sampling_interval=0.1,
            segment_seconds=0.0,
        )
