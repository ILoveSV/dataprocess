from src.io.metadata_io import normalize_sampling_rate


def test_normalize_sampling_rate_from_interval():
    assert normalize_sampling_rate({'sampling_interval_seconds': 2.5e-6}) == 400000


def test_normalize_sampling_rate_from_rate():
    assert normalize_sampling_rate({'sampling_rate_hz': 400000}) == 400000


def test_normalize_sampling_rate_default():
    assert normalize_sampling_rate({}, default_rate=500000) == 500000

