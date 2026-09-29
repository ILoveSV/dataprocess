"""Build an auditable preservation package before raw TDMS deletion."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from exact_tdms_archive import archive_complete, validate_exact_archive


@dataclass(frozen=True)
class Dataset:
    name: str
    raw_root: Path
    archive_root: Path


DEFAULT_DATASETS = (
    Dataset(
        "20260617",
        Path(r"D:\Lab\raw\26.6.17"),
        Path('experiments/20260617/exact_archive'),
    ),
    Dataset(
        "20260731",
        Path(r"D:\Lab\raw\26.7.31"),
        Path('experiments/20260731/tdms/exact_archive'),
    ),
    Dataset(
        "20260806",
        Path(r"D:\Lab\raw\26.8.6"),
        Path('experiments/20260806/exact_archive'),
    ),
)
MEDIA_SUFFIXES = {".mp4", ".m4a", ".wav", ".jpg", ".jpeg", ".png", ".mov"}
CODE_FILES = (
    "scripts/exact_tdms_archive.py",
    "scripts/exact_analysis_metrics.py",
    "scripts/channel_quality.py",
    "scripts/analyze_20260731_tdms.py",
    "scripts/analyze_20260731_media.py",
    "scripts/analyze_20260806_experiment.py",
    "scripts/analyze_20260806_media.py",
    "scripts/build_preservation_manifest.py",
    "scripts/archive_tdms_tree.py",
    "tests/test_exact_tdms_archive.py",
    "tests/test_channel_quality.py",
    "docs/EXACT_ANALYSIS_AND_RETENTION_20260808.md",
)
REPORT_SUFFIXES = {".csv", ".json", ".md", ".png", ".svg", ".pdf", ".txt"}


def sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def archive_source_lookup(root: Path) -> dict[str, tuple[str, Path]]:
    lookup: dict[str, tuple[str, Path]] = {}
    if not root.is_dir():
        return lookup
    for metadata_path in root.glob("*/metadata.json"):
        case_root = metadata_path.parent
        if not archive_complete(case_root):
            continue
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        source = str(Path(metadata["source_path"]).resolve()).casefold()
        lookup[source] = (case_root.name, case_root)
    return lookup


def package_code(project_root: Path, output: Path) -> list[dict[str, object]]:
    rows = []
    destination = output / "code_snapshot"
    for relative_name in CODE_FILES:
        source = project_root / relative_name
        if not source.exists():
            continue
        target = destination / relative_name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        rows.append({
            "kind": "code",
            "relative_path": str(target.relative_to(output)),
            "size_bytes": target.stat().st_size,
            "sha256": sha256(target),
        })
    return rows


def inventory_analysis_outputs(project_root: Path) -> list[dict[str, object]]:
    rows = []
    results_root = project_root / "experiments"
    for path in sorted(results_root.glob("2026*/**/*")):
        if not path.is_file() or path.suffix.lower() not in REPORT_SUFFIXES:
            continue
        if "exact_archive" in path.parts:
            continue
        rows.append({
            "kind": "analysis_output",
            "relative_path": str(path.relative_to(project_root)),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        action="append",
        nargs=3,
        metavar=("NAME", "RAW_ROOT", "ARCHIVE_ROOT"),
        help="Dataset mapping; may be repeated. Defaults to 20260617, 20260731 and 20260806.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path('archive/preservation_20260808'),
    )
    parser.add_argument(
        "--copy-media",
        action="store_true",
        help="Copy all small media into the preservation package.",
    )
    parser.add_argument(
        "--hash-raw",
        action="store_true",
        help="Read every source TDMS byte and record SHA-256 before deletion.",
    )
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    datasets = (
        [Dataset(name, Path(raw), Path(archive)) for name, raw, archive in args.dataset]
        if args.dataset else list(DEFAULT_DATASETS)
    )

    source_rows: list[dict[str, object]] = []
    retained_rows: list[dict[str, object]] = []
    problems: list[str] = []
    for dataset in datasets:
        raw_root = dataset.raw_root.resolve()
        archive_root = (
            dataset.archive_root
            if dataset.archive_root.is_absolute()
            else (project_root / dataset.archive_root)
        ).resolve()
        lookup = archive_source_lookup(archive_root)
        tdms_files = sorted(raw_root.rglob("*.tdms")) if raw_root.is_dir() else []
        for index, source in enumerate(tdms_files, start=1):
            match = lookup.get(str(source.resolve()).casefold())
            row = {
                "dataset": dataset.name,
                "relative_path": str(source.relative_to(raw_root)),
                "size_bytes": source.stat().st_size,
                "mtime_ns": source.stat().st_mtime_ns,
                "archive_case_id": match[0] if match else "",
                "exact_archive_complete": bool(match),
                "source_sha256": "",
            }
            if args.hash_raw:
                print(
                    f"[{dataset.name} raw {index}/{len(tdms_files)}] hashing {source.name}",
                    flush=True,
                )
                row["source_sha256"] = sha256(source)
            if not match:
                problems.append(f"No exact archive for {source}")
            source_rows.append(row)

        for case_root in sorted(path for path in archive_root.glob("*") if path.is_dir()):
            if not archive_complete(case_root):
                problems.append(f"Incomplete exact archive: {case_root}")
                continue
            for problem in validate_exact_archive(case_root):
                problems.append(f"Invalid exact archive {case_root}: {problem}")
            for path in sorted(item for item in case_root.iterdir() if item.is_file()):
                retained_rows.append({
                    "dataset": dataset.name,
                    "kind": "exact_archive",
                    "relative_path": str(path.relative_to(project_root)),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256(path),
                })

        media_files = sorted(
            path for path in raw_root.rglob("*")
            if path.is_file() and path.suffix.lower() in MEDIA_SUFFIXES
        ) if raw_root.is_dir() else []
        for index, source in enumerate(media_files, start=1):
            if args.copy_media:
                target = output / "media" / dataset.name / source.relative_to(raw_root)
                target.parent.mkdir(parents=True, exist_ok=True)
                print(
                    f"[{dataset.name} media {index}/{len(media_files)}] copying {source.name}",
                    flush=True,
                )
                shutil.copy2(source, target)
                retained_path = target
            else:
                retained_path = source
            retained_rows.append({
                "dataset": dataset.name,
                "kind": "media_copy" if args.copy_media else "media_source_only",
                "relative_path": (
                    str(retained_path.relative_to(output))
                    if args.copy_media else str(retained_path)
                ),
                "size_bytes": retained_path.stat().st_size,
                "sha256": sha256(retained_path),
            })

    retained_rows.extend(package_code(project_root, output))
    retained_rows.extend(inventory_analysis_outputs(project_root))
    write_csv(output / "raw_tdms_manifest.csv", source_rows)
    write_csv(output / "retained_file_manifest.csv", retained_rows)

    packages = {}
    for name in ("numpy", "scipy", "nptdms", "matplotlib", "pandas"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": packages,
        "raw_hashes_included": bool(args.hash_raw),
        "media_copied": bool(args.copy_media),
        "source_tdms_count": len(source_rows),
        "source_tdms_bytes": sum(int(row["size_bytes"]) for row in source_rows),
        "retained_file_count": len(retained_rows),
        "retained_bytes": sum(int(row["size_bytes"]) for row in retained_rows),
        "problems": problems,
    }
    (output / "preservation_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)
    if problems:
        raise RuntimeError("Preservation package is incomplete; see manifest problems")


if __name__ == "__main__":
    main()
