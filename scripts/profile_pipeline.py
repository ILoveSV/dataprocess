#!/usr/bin/env python3
import argparse
import cProfile
import io
import json
import os
import pstats
import sys
import time
import tracemalloc
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def parse_args():
    parser = argparse.ArgumentParser(description="Profile one DataProcess pipeline module with cProfile.")
    parser.add_argument(
        "--module",
        required=True,
        choices=["timedata", "freqdata", "freqavedata", "timeplots", "freqplots", "all"],
        help="Pipeline module to run through src.main.",
    )
    parser.add_argument("--data-folder", default=None, help="Optional small raw/time/frequency group path.")
    parser.add_argument("--output-dir", default=".", help="Directory for profiling outputs.")
    parser.add_argument("--config", default="config/parameters.yaml")
    parser.add_argument("--log-config", default="config/logging.yaml")
    return parser.parse_args()


def build_main_argv(args):
    argv = ["src.main", args.module, "--config", args.config, "--log-config", args.log_config]
    if args.data_folder:
        argv.extend(["--data-folder", args.data_folder])
    return argv


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    profile_path = output_dir / "profiling_result.prof"
    top_path = output_dir / "profiling_top50.txt"
    summary_path = output_dir / "module_timing_summary.json"

    os.environ["DATAPROCESS_TIMING_SUMMARY"] = str(summary_path)

    import src.main as pipeline_main

    old_argv = sys.argv[:]
    sys.argv = build_main_argv(args)

    profiler = cProfile.Profile()
    tracemalloc.start()
    start = time.perf_counter()
    try:
        profiler.enable()
        pipeline_main.main()
        profiler.disable()
    finally:
        elapsed = time.perf_counter() - start
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        sys.argv = old_argv

    profiler.dump_stats(str(profile_path))

    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumtime")
    stats.print_stats(50)
    top_path.write_text(stream.getvalue(), encoding="utf-8")

    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        summary = {"timings": {}, "counters": {}}
    summary.setdefault("profiling", {})
    summary["profiling"].update(
        {
            "module": args.module,
            "data_folder": args.data_folder,
            "elapsed_seconds": elapsed,
            "tracemalloc_current_bytes": current,
            "tracemalloc_peak_bytes": peak,
            "profile_path": str(profile_path),
            "top50_path": str(top_path),
        }
    )
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"profile: {profile_path}")
    print(f"top50: {top_path}")
    print(f"summary: {summary_path}")
    print(f"elapsed_seconds: {elapsed:.3f}")
    print(f"tracemalloc_peak_mb: {peak / 1024 / 1024:.2f}")


if __name__ == "__main__":
    main()
