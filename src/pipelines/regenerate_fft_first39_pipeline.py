import argparse
import json
from pathlib import Path

from src.pipelines.fft_export_pipeline import process_csv_file


GROUPS = ["2m0hz", "2m30hz", "2m50hz", "3m0hz", "3m30hz", "3m50hz", "5m0hz", "5m30hz", "5m50hz"]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Regenerate FFT CSV files from the first N time CSV files per group.")
    parser.add_argument("--time-root", default="D:/Lab/process/26.5.12/time")
    parser.add_argument("--frequency-root", default="D:/Lab/process/26.5.12/frequency")
    parser.add_argument("--groups", nargs="+", default=GROUPS)
    parser.add_argument("--keep-first", type=int, default=39)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    time_root = Path(args.time_root)
    frequency_root = Path(args.frequency_root)
    if not args.overwrite:
        raise SystemExit("Refusing to overwrite FFT outputs without --overwrite")

    manifest = {
        "time_root": str(time_root),
        "frequency_root": str(frequency_root),
        "keep_first": args.keep_first,
        "groups": {},
        "scope_note": "Existing FFT_*.csv files are removed per selected group before regenerating from first N time CSV files.",
    }
    for group in args.groups:
        time_dir = time_root / group
        out_dir = frequency_root / group
        if not time_dir.exists():
            manifest["groups"][group] = {"status": "skipped", "reason": f"missing time group dir: {time_dir}"}
            continue
        out_dir.mkdir(parents=True, exist_ok=True)
        old_fft = sorted(out_dir.glob("FFT_*.csv"))
        for path in old_fft:
            path.unlink()
        csv_files = sorted(path for path in time_dir.glob("*.csv") if not path.name.startswith("FFT_"))
        selected = csv_files[: args.keep_first]
        excluded = csv_files[args.keep_first :]
        for csv_file in selected:
            process_csv_file(str(csv_file), str(frequency_root), str(time_root))
        manifest["groups"][group] = {
            "status": "ok",
            "old_fft_deleted": len(old_fft),
            "time_csv_found": len(csv_files),
            "time_csv_processed": len(selected),
            "excluded_files": [path.name for path in excluded],
            "output_fft_count": len(list(out_dir.glob("FFT_*.csv"))),
        }

    manifest_path = frequency_root / "fft_regenerate_first39_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Regenerated FFT first-N manifest: {manifest_path}")


if __name__ == "__main__":
    main()
