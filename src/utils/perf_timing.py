import json
import logging
import os
import time
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path


logger = logging.getLogger('data_process')

_timings = defaultdict(lambda: {'count': 0, 'seconds': 0.0})
_counters = defaultdict(float)


def reset_timing():
    _timings.clear()
    _counters.clear()


@contextmanager
def timed_step(name, **fields):
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        item = _timings[name]
        item['count'] += 1
        item['seconds'] += elapsed
        details = ' '.join(f'{key}={value}' for key, value in fields.items() if value is not None)
        logger.info("TIMING %s seconds=%.6f %s", name, elapsed, details)


def add_counter(name, value=1):
    try:
        _counters[name] += float(value)
    except (TypeError, ValueError):
        logger.debug("Ignoring non-numeric timing counter %s=%r", name, value)


def record_file_size(path, counter_name):
    try:
        file_path = Path(path)
        if file_path.exists():
            add_counter(counter_name, file_path.stat().st_size)
    except OSError:
        logger.debug("Could not stat output file for timing summary: %s", path)


def get_summary():
    timings = {}
    for name, item in sorted(_timings.items()):
        count = int(item['count'])
        seconds = float(item['seconds'])
        timings[name] = {
            'count': count,
            'seconds': seconds,
            'avg_seconds': seconds / count if count else 0.0,
        }
    return {
        'timings': timings,
        'counters': {name: value for name, value in sorted(_counters.items())},
    }


def write_summary(output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as handle:
        json.dump(get_summary(), handle, indent=2, ensure_ascii=False)
    logger.info("Timing summary written to: %s", output_path)
    return output_path


def maybe_write_summary(default_path='module_timing_summary.json'):
    output_path = os.environ.get('DATAPROCESS_TIMING_SUMMARY', default_path)
    if output_path:
        return write_summary(output_path)
    return None
