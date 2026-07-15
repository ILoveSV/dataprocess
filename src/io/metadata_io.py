def normalize_sampling_rate(metadata, default_rate=500000):
    """Parse sampling rate from metadata and return a positive integer Hz."""
    if metadata:
        raw_interval = metadata.get('sampling_interval_seconds')
        if raw_interval is not None:
            try:
                interval = float(raw_interval)
                if interval > 0:
                    return int(round(1.0 / interval))
            except (TypeError, ValueError):
                pass

        raw_rate = metadata.get('sampling_rate_hz')
        if raw_rate is not None:
            try:
                rate = int(round(float(raw_rate)))
                if rate > 0:
                    return rate
            except (TypeError, ValueError):
                pass

    return int(default_rate)

