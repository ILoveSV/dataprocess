# Performance Current Structure

This document is the retained performance-side summary. Earlier temporary audit, modification, cache, and benchmark reports have been removed from the main docs set.

## Current performance structure

The project currently uses a staged data-processing flow:

```text
timedata
  -> freqdata
  -> freqavedata
  -> timeplots
  -> freqplots
  -> nistdiagnostics
  -> background contrast / later analysis pipelines
```

The main CLI entry point is `src/main.py`. Some performance-related behavior is controlled through CLI options such as:

- `--plots none|minimal|full`
- `--dpi`
- `--max-plot-points`
- `--force`
- `--skip-existing`
- `--no-skip-existing`
- `--export-excel`

The performance utilities are currently centered around:

- `src/utils/perf_timing.py`
- `src/utils/cache_utils.py`
- `scripts/profile_pipeline.py`

## Timing structure

The timing helper records module-level and stage-level elapsed time. It is intended to support profiling without changing scientific results.

Typical timing categories include:

- file scan
- CSV read
- TDMS read
- FFT compute
- metric compute
- plotting
- savefig
- JSON/CSV/Excel write

The profiling script can run selected modules and write profiling outputs such as:

- `profiling_result.prof`
- `profiling_top50.txt`
- `module_timing_summary.json`

## Plot mode structure

Frequency plotting supports multiple plot modes:

- `none`: compute and export metrics without PNG plots
- `minimal`: generate a small set of core figures
- `full`: generate the complete figure set

This separates metric computation from plotting cost. The intended default for repeated processing is `none` or `minimal`; `full` is better suited for final visual inspection or report figures.

## Cache structure

The project includes lightweight stage-level cache behavior.

The cache is based on:

- input file list
- input modification times
- expected output files
- parameter signature
- cache metadata

Supported cache-style behavior includes:

- skip when outputs are up to date
- recompute with `--force`
- disable skip behavior with `--no-skip-existing`

The cache is stage-level, not a full DAG and not per-file incremental recomputation.

## Known bottleneck structure

The main performance costs are currently organized around:

- large CSV read/write
- full FFT CSV parsing
- plotting and `savefig`
- Excel export
- repeated group-level figure generation
- large intermediate frequency-domain files

For full group processing, CSV parsing and plotting remain important costs. Cache HIT behavior is intended to avoid repeated parsing and rendering when inputs and parameters have not changed.

## Current practical guidance

For routine iteration:

```powershell
python -m src.main freqplots --input <fft_csv_folder> --output <out_dir> --plots none
```

For quick visual review:

```powershell
python -m src.main freqplots --input <fft_csv_folder> --output <out_dir> --plots minimal
```

For final figures:

```powershell
python -m src.main freqplots --input <fft_csv_folder> --output <out_dir> --plots full
```

Use `--force` only when outputs must be regenerated.

## Remaining optimization direction

Future performance work should focus on structure rather than changing formulas:

- keep metric computation and plotting separated
- reduce repeated CSV reads
- avoid unnecessary full PNG generation
- keep cache signatures complete when parameters change
- consider more efficient intermediate formats only after profiling evidence
- keep output equivalence checks when optimizing FFT or feature computations

## Non-goals

Do not change these as part of performance cleanup:

- FFT normalization
- PSD gain definition
- background contrast formula
- pump net definition
- candidate feature formula
- strict-mode frequency-axis filtering policy

Performance optimization should preserve scientific outputs unless a separate analysis change is explicitly approved.
