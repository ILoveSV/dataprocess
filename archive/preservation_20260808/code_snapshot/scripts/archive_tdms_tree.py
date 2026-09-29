"""Build exact archives for every TDMS file below a directory tree."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from exact_tdms_archive import ExactArchiveConfig, archive_complete, build_exact_archive


def case_id(root: Path, source: Path) -> str:
    relative = source.relative_to(root).with_suffix("")
    text = "__".join(relative.parts)
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trim-start", type=float, default=1.0)
    parser.add_argument("--trim-end", type=float, default=1.0)
    args = parser.parse_args()
    sources = sorted(args.root.rglob("*.tdms"))
    if not sources:
        raise FileNotFoundError(f"No TDMS files below {args.root}")
    args.output.mkdir(parents=True, exist_ok=True)
    config = ExactArchiveConfig(
        trim_start_seconds=args.trim_start,
        trim_end_seconds=args.trim_end,
    )
    for index, source in enumerate(sources, start=1):
        destination = args.output / case_id(args.root, source)
        if archive_complete(destination):
            print(f"[{index}/{len(sources)}] archive {destination.name}", flush=True)
            continue
        print(f"[{index}/{len(sources)}] extract {source}", flush=True)
        build_exact_archive(source, destination, config)
    print(f"Exact archives complete: {args.output.resolve()}", flush=True)


if __name__ == "__main__":
    main()
