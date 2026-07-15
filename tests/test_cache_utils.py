import os
import time

from src.utils.cache_utils import build_cache_metadata, is_cache_hit, write_cache_metadata


def _touch(path, text):
    path.write_text(text, encoding="utf-8")
    return path


def _valid_cache(tmp_path):
    input_file = _touch(tmp_path / "input.csv", "a")
    output_file = _touch(tmp_path / "output.csv", "b")
    now = time.time()
    os.utime(input_file, (now - 10, now - 10))
    os.utime(output_file, (now, now))
    params = {"mode": "x"}
    metadata_path = tmp_path / ".cache" / "stage_cache.json"
    write_cache_metadata(
        metadata_path,
        build_cache_metadata("stage", [input_file], [output_file], params, input_dir=tmp_path, output_dir=tmp_path),
    )
    return input_file, output_file, params, metadata_path


def test_cache_miss_output_missing(tmp_path):
    input_file, output_file, params, metadata_path = _valid_cache(tmp_path)
    output_file.unlink()
    hit, reason = is_cache_hit("stage", [input_file], [output_file], params, metadata_path)
    assert not hit
    assert reason == "missing output"


def test_cache_miss_metadata_missing(tmp_path):
    input_file = _touch(tmp_path / "input.csv", "a")
    output_file = _touch(tmp_path / "output.csv", "b")
    hit, reason = is_cache_hit("stage", [input_file], [output_file], {"mode": "x"}, tmp_path / ".cache" / "missing.json")
    assert not hit
    assert reason == "missing metadata"


def test_cache_miss_force(tmp_path):
    input_file, output_file, params, metadata_path = _valid_cache(tmp_path)
    hit, reason = is_cache_hit("stage", [input_file], [output_file], params, metadata_path, force=True)
    assert not hit
    assert reason == "force enabled"


def test_cache_miss_input_newer_than_output(tmp_path):
    input_file, output_file, params, metadata_path = _valid_cache(tmp_path)
    now = time.time()
    os.utime(input_file, (now + 10, now + 10))
    hit, reason = is_cache_hit("stage", [input_file], [output_file], params, metadata_path)
    assert not hit
    assert reason == "input newer than output"


def test_cache_miss_param_signature_changed(tmp_path):
    input_file, output_file, params, metadata_path = _valid_cache(tmp_path)
    hit, reason = is_cache_hit("stage", [input_file], [output_file], {"mode": "y"}, metadata_path)
    assert not hit
    assert reason == "parameter signature changed"


def test_cache_miss_input_file_list_changed(tmp_path):
    input_file, output_file, params, metadata_path = _valid_cache(tmp_path)
    extra = _touch(tmp_path / "extra.csv", "c")
    hit, reason = is_cache_hit("stage", [input_file, extra], [output_file], params, metadata_path)
    assert not hit
    assert reason == "input file list changed"


def test_cache_hit_all_valid(tmp_path):
    input_file, output_file, params, metadata_path = _valid_cache(tmp_path)
    hit, reason = is_cache_hit("stage", [input_file], [output_file], params, metadata_path)
    assert hit
    assert reason == "cache hit"
