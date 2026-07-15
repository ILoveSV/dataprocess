from pathlib import Path

from src.core.path_resolver import resolve_scan_folder


def test_resolve_scan_folder_absolute(tmp_path):
    folder = tmp_path / "data"
    folder.mkdir()

    assert Path(resolve_scan_folder(tmp_path, folder)).resolve() == folder.resolve()


def test_resolve_scan_folder_relative(tmp_path):
    folder = tmp_path / "data"
    folder.mkdir()

    assert Path(resolve_scan_folder(tmp_path, "data")).resolve() == folder.resolve()

