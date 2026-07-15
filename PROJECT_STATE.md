# PROJECT_STATE.md

## English Version

### 1. Project Identity

This appears to be a Python data-processing and analysis project for experimentally collected sensor/time-series data. The repository contains code for converting TDMS files to time-domain CSV plus metadata, exporting FFT CSV files, averaging FFT files by folder/group, calculating time-domain metrics, generating frequency-domain plots and JSON/CSV summaries, and running NIST-style run-sequence/lag/distribution/PSD/ACF diagnostics. A background contrast module and related smoke/real-data scripts were also found, but they should be treated as one discovered module family, not as the central identity of the whole project.

The main identifiable data type appears to be multi-channel sampled time-series data, with repository evidence for TDMS raw input, time CSV intermediate files, FFT CSV intermediate files, Excel/CSV/JSON/PNG/TXT outputs, and metadata JSON files. The current local config paths point to `D:/Lab/raw/26.5.12`, `D:/Lab/process/26.5.12/*`, and `D:/Lab/results/26.5.12/*`; these should not be treated as permanent project paths without human confirmation. Existing reports mention processed groups `2m0hz`, `2m30hz`, `2m50hz`, `3m0hz`, `3m30hz`, `3m50hz`, `5m0hz`, `5m30hz`, and `5m50hz`, with 12 channels and 40 files per processed group in the reported checked real-data run.

What can be confirmed from the repository:

- The project has a Python CLI entry point in `src/main.py` and a preset wrapper in `run.py`.
- The main processing chain appears to be TDMS -> time CSV/metadata -> FFT CSV -> average FFT CSV -> time/frequency/NIST outputs.
- The codebase has been split into `core`, `io`, `features`, `summaries`, `reports`, `plots`, `pipelines`, legacy-compatible `data_io` wrappers, and legacy-compatible `visualization` wrappers.
- Existing outputs are present under `analysis_out/` and `results/`.
- Several performance, cache, metric registry, and background contrast documents exist under `docs/`.

What still needs human confirmation:

- The scientific meaning of each data group name.
- Which groups are true background groups and which are target/experiment groups.
- Whether same-distance 0 Hz groups are accepted as background references for all future analysis.
- Whether feature-level background contrast is sufficient, or whether any stronger waveform-level cancellation is allowed.
- Which generated outputs are exploratory, internal-only, or suitable for reports/papers.
- Whether `verification/`, `interview/`, and `articles/` should be treated as part of this DataProcess project or as adjacent/legacy material.

Project identity is partially inferred from repository content and requires human confirmation.

### 2. Repository Overview

Relevant project directories and files:

- `README.md`: Main project overview, CLI usage, pipeline map, expected outputs, and current code layout. The file content is readable but appears mojibake in the current PowerShell display; the structure and commands are still identifiable.
- `REQUIREMENTS.md` and `requirements.txt`: Dependency and requirement-related files.
- `run.py`: Preset wrapper around `python -m src.main`. Presets include `full`, `preprocess`, `time`, `freq`, `visualize`, `report`, and `load`.
- `config/`: Runtime configuration.
  - `rawpath.yaml`: Template-like path config with `${work_dir}` variables.
  - `paths.yaml`: Generated/resolved paths. Current local config paths point to `D:/Lab` and date `26.5.12`; this is not assumed to be a permanent project path.
  - `parameters.yaml`: Currently includes time-domain parameters such as `time_channels: 8`, `time_sampling_rate: 500000`, and `time_window_size: 1000`.
  - `logging.yaml`: Logging configuration.
- `src/`: Main Python implementation.
  - `src/main.py`: Main CLI dispatcher.
  - `src/core/`: Config loading, constants, and path resolution helpers.
  - `src/io/`: CSV/TDMS/metadata read helpers.
  - `src/features/`: Core computations including FFT, time metrics, NIST diagnostics/PSD/ACF, and background contrast.
  - `src/summaries/`: Group-level summaries for time metrics, frequency summaries, NIST diagnostics, and background contrast.
  - `src/reports/`: Excel/CSV/JSON/TXT/background-contrast exporters.
  - `src/plots/`: Frequency and NIST plot generation.
  - `src/pipelines/`: Pipeline entry points.
  - `src/data_io/` and `src/visualization/`: Legacy-compatible wrappers/aliases for older entry points.
  - `src/utils/`: File utilities, logging utilities, cache utilities, and performance timing.
- `scripts/`: Utility scripts.
  - `profile_pipeline.py`: cProfile/tracemalloc wrapper for selected pipeline modules.
  - `build_analysis_package.py`: Builds the `analysis_out/` package, summary report, CSV tables, figures, and `analysis_out.zip`.
- `tests/`: Smoke and unit-style tests for cache utilities, FFT core, metadata/time CSV IO, path resolver, frequency plots, NIST plots/diagnostics, pipeline cache behavior, time metrics, and background contrast.
- `docs/`: Project documentation and run notes.
  - `BACKGROUND_CONTRAST_V1.md`: According to this doc, it records background contrast scope, schemas, pairing rule, smoke coverage, and smoke command.
  - `METRIC_REGISTRY.md`: Appears to record metric definitions and implementation locations.
  - `PERFORMANCE_AUDIT.md`, `PERFORMANCE_CACHE_V1_2.md`, `PERFORMANCE_V1_1_RESULT.md`, `PERFORMANCE_FULL_GROUP_V1_2.md`: According to these docs, they record performance/cache/run observations and output locations.
- `analysis_out/`: Existing generated analysis package and performance/smoke outputs, according to file names and contained reports.
- `results/`: Older local result outputs, including `2025.11.11` and `retry`; current relevance needs human confirmation.
- `logs/`: Application logs, mostly May 2026.
- `analysis_output_check_report.md`: Appears to be a real-data output check report for the 26.5.12 run.
- `analysis_out.zip`: Appears to be a zip package generated from `analysis_out/`.

Directories with unclear or possibly adjacent relevance:

- `articles/`: Contains raw PDF files and paragraph summaries. It may be literature/reference material for the project, but direct pipeline linkage is not confirmed. Need human confirmation.
- `verification/`: Contains extensive SystemVerilog/UVM/RTL verification content and verification docs. It appears unrelated to the Python DataProcess pipeline from the scanned content. Need human confirmation.
- `interview/`: Contains SystemVerilog files. Relevance to this data-processing project is unclear. Need human confirmation.
- `.pytest_cache/`, `__pycache__/`: Cache directories; excluded from project state.

### 3. Data Inventory and Output Artifacts

Input and intermediate data inventory:

- Raw data root from current local config paths: `D:/Lab/raw/26.5.12`.
  - Expected raw format: `*.tdms`.
  - Repository-local raw TDMS files were not found in the scanned project root.
  - Current raw data appears to live outside the repository according to config and reports.
- Time-domain intermediate root from current local config paths: `D:/Lab/process/26.5.12/time`.
  - Expected files: time CSV and matching `*_metadata.json`.
  - Expected CSV columns: `time`, then channel columns such as `channel1`, `channel2`, etc.
  - According to README, metadata fields include filename, start time, sampling interval/rate, data length, duration, channel count, and channel names.
- Frequency-domain intermediate root from current local config paths: `D:/Lab/process/26.5.12/frequency`.
  - Expected files: `FFT_<input_filename>.csv`.
  - Expected columns: `frequency`, then per-channel amplitude/phase columns.
- Average FFT root from current local config paths: `D:/Lab/process/26.5.12/frequency_ave`.
  - Expected files: `average_fft_<folder_name>_<file_count>files.csv` and `processing_summary.txt`.
- Analysis output roots from current local config paths:
  - `D:/Lab/results/26.5.12/time`
  - `D:/Lab/results/26.5.12/frequency`
  - NIST and background contrast paths appear to be derived in code/docs from the results root.
- Existing real-data check report:
  - `analysis_output_check_report.md` reports that the full real-data flow used `D:\Lab\raw\26.5.12`, `D:\Lab\process\26.5.12\time`, and `D:\Lab\results\26.5.12`; these are current local paths reported by that file, not permanent project paths.
  - It reports processed groups `2m0hz`, `2m30hz`, `2m50hz`, `3m0hz`, `3m30hz`, `3m50hz`, `5m0hz`, `5m30hz`, and `5m50hz`.
  - It reports 40 raw TDMS files and 40 time CSV files per processed group, 12 channels per group, and no missing files in those 9 processed groups.
  - It reports `3m20hz` as requested but not found, and `3m30hz` as found/processed.
  - It reports that background subtraction was not configured and not run in that checked flow.
- Data grouping and experimental meaning require human confirmation.

Existing output artifacts inside this repository:

- `analysis_out/summary_report.md`: Appears to be a generated analysis package summary. It reports 9 input groups, 12 channels, 40 files per group, and summarizes NIST/PSD/ACF/background-vs-active-style derived outputs. Scientific conclusions in this file should not be treated as validated by this state file.
- `analysis_out/run_log.txt`: Appears to be a build log for `analysis_out`; it reports `TIME_ROOT=D:\Lab\process\26.5.12\time`, `NIST_ROOT=D:\Lab\results\26.5.12\nist_diagnostics`, 9 groups found, Excel generated, 13 CSV tables, 7 figures, and elapsed seconds. These `D:\Lab` paths are reported current local paths.
- `analysis_out/all_groups_summary.xlsx` and `analysis_out/all_groups_summary.csv`: Group-level summary outputs.
- `analysis_out/csv/`: Existing CSV exports including ACF summaries, PSD summaries, background contrast, distance decay, low-frequency summary, manifest, PSD/ACF matches, pump-frequency contrast, sideband summary, and cross-channel peak summaries.
- `analysis_out/figures/`: Existing PNG figures for ACF, background contrast heatmap, bandpower, cross-channel peaks, distance decay, PSD dominant frequency, and pump 30 vs 50 contrast.
- `analysis_out/contrast_v1_smoke/`: Synthetic smoke outputs for background contrast, including Excel, CSV, TXT, and Markdown report files.
- `analysis_out/perf_quick_smoke/`: Quick smoke/performance inputs and outputs using small samples, timing JSON files, validation JSON files, cache metadata, timeplots/freqdata/freqavedata/freqplots outputs, and v1.1/cache validation outputs.
- `analysis_out/perf_full_group_v1_2/`: According to file names and performance docs, this contains full `2m0hz` frequency group benchmark outputs with `none`, `minimal`, and `full` plot modes, timing JSON, stdout/stderr logs, cache metadata, and benchmark summaries.
- `results/2025.11.11/`: Older frequency and time result outputs for `GROUP1`/`GROUP2` and summary JSON. Need human confirmation before treating as current.
- `results/retry/`: Older retry time outputs and plots for `GROUP1`. Need human confirmation before treating as current.
- `logs/`: Runtime logs from May 2026.
- `analysis_out.zip`: Packaged copy of `analysis_out/`.

### 4. Processing Modules

Main CLI and orchestration:

- `src/main.py`: Main dispatcher for modules `timedata`, `freqdata`, `freqavedata`, `timeplots`, `freqplots`, `nistdiagnostics`, `nistplots`, `visualize`, `report`, and `all`. It also calls `generate_paths_config()` on startup.
- `run.py`: Preset runner that calls `python -m src.main <module>` with `--config config/parameters.yaml`.

Configuration/path modules:

- `src/core/config_loader.py`: Finds project root and loads configuration.
- `src/core/path_resolver.py`: Resolves scan folders and derives output paths, including time metrics and NIST diagnostics output paths.
- `src/utils/file_utils.py`: Generates `config/paths.yaml` from `config/rawpath.yaml`.
- `src/utils/cache_utils.py`: Builds and checks cache metadata for pipeline stages.
- `src/utils/perf_timing.py`: Records timing summaries.
- `src/utils/logging_utils.py`: Sets up logging.

Input/output modules:

- `src/io/tdms_io.py`: TDMS-related IO helper. Exact behavior not fully enumerated in this document.
- `src/io/time_csv_io.py`: Reads time CSV data/headers and collects CSV groups, excluding known output file names.
- `src/io/metadata_io.py`: Normalizes sampling-rate metadata.
- `src/io/fft_csv_io.py`: FFT CSV IO helper. Exact behavior not fully enumerated in this document.

Pipeline modules:

- `src/pipelines/tdms_to_time_pipeline.py`: Converts TDMS files to time CSV and metadata JSON. Likely input: `raw_data_dir/**/*.tdms`. Likely output: CSV plus `*_metadata.json` under `tdms_reader_time_output_dir`, preserving relative structure.
- `src/pipelines/fft_export_pipeline.py`: Converts time CSV files to FFT CSV. Likely input: time CSV plus metadata JSON. Output: `FFT_<input_filename>.csv` under `tdms_reader_frequency_output_dir`; cache metadata at `.cache/freqdata_cache.json`.
- `src/pipelines/fft_average_pipeline.py`: Averages `FFT_*.csv` files by folder. Output: `average_fft_<folder>_<count>files.csv`, summary text, and cache metadata.
- `src/pipelines/time_quality_pipeline.py`: Computes time-domain file metrics and group/data-completeness summaries. Input: time CSV file or folder. Output: `time_series_metrics.xlsx` or CSV, `time_series_group_summary.xlsx`, and `data_completeness_summary.xlsx`.
- `src/pipelines/frequency_analysis_pipeline.py`: Computes frequency-domain group metrics and optional plots. Input: FFT CSV file/folder. Output: per-group `frequency_plots_report.json`, `dominant_frequencies.csv`, optional PNG plots, `fft_analysis_summary.json`, and `.cache/freqplots_cache.json`.
- `src/pipelines/nist_diagnostics_pipeline.py`: Runs NIST-style diagnostics, PSD, ACF, summaries, and optional 4-plot/ACF/PSD figures for time CSV groups. Outputs include `nist_diagnostics_metrics.xlsx`, `nist_file_stability_summary.xlsx`, `nist_diagnostics_group_summary.xlsx`, `acf_group_summary.xlsx`, `psd_group_summary.xlsx`, `psd_acf_summary.xlsx`, `psd_acf_peak_matches.xlsx`, `harmonic_matches_long.xlsx`, `cross_channel_peak_summary.xlsx`, `psd_peaks_long.xlsx`, `acf_peaks_long.xlsx`, `background_subtraction_summary.xlsx`, and `figures/`.
- `src/pipelines/background_contrast_smoke_pipeline.py`: Builds synthetic smoke inputs and exports background-contrast smoke outputs to `analysis_out/contrast_v1_smoke/` by default. This is recorded as one discovered module/pipeline family.
- `src/pipelines/background_contrast_real_pipeline.py`: Appears to read configured time/NIST real-data outputs for fixed groups, compute feature-level background contrast, and write CSV/XLSX/PNG/Markdown/TXT outputs under the current local config-derived `D:/Lab/results/26.5.12/background_contrast_v1` path by default unless `--output` is given. This path should not be treated as permanent without human confirmation.

Feature modules:

- `src/features/time_metrics.py`: Per-file time-domain metrics such as sample count, duration, dt statistics, mean/median/min/max, peak-to-peak, std, AC RMS, robust sigma, crest factor, drift metrics, outlier/spike/tail/extreme rates, and QC helper functions.
- `src/features/fft_core.py`: FFT calculation helper.
- `src/features/fft_statistics.py`: Frequency-domain statistics helper. Exact outputs not fully enumerated here.
- `src/features/fft_average.py`: FFT averaging helper.
- `src/features/nist_diagnostics.py`: NIST-style run sequence, lag, distribution, and normal probability metrics.
- `src/features/nist_psd.py`: Welch PSD, peak, bandpower, spectral entropy, and low-frequency PSD metrics.
- `src/features/nist_acf.py`: ACF diagnostics, peaks, peak spacing, PSD/ACF matching, and related period metrics.
- `src/features/background_contrast.py`: Feature-level background pairing and contrast for PSD gain curves, bandpower, peaks, and ACF.

Summary/report/plot modules:

- `src/summaries/time_group_summary.py`: Time-domain group and completeness summaries.
- `src/summaries/frequency_group_summary.py`: Frequency group summary helper.
- `src/summaries/nist_diagnostics_summary.py`: NIST diagnostics summaries.
- `src/summaries/background_contrast_summary.py`: Cross-channel support, 30 Hz vs 50 Hz net contrast, distance decay, and outlier marking for background contrast.
- `src/reports/excel_export.py`: Time metrics/group/completeness Excel exporters.
- `src/reports/nist_excel_export.py`: NIST/PSD/ACF Excel exporters.
- `src/reports/background_contrast_export.py`: Background contrast smoke exporters.
- `src/reports/csv_export.py`, `json_report.py`, `text_report.py`: General export helpers.
- `src/plots/frequency_plots.py`, `src/plots/nist_4plot.py`, `src/plots/nist_acf_plot.py`, `src/plots/nist_psd_plot.py`: Plotting modules.

Legacy-compatible wrappers:

- `src/data_io/tdms_reader_time.py`: Wrapper for TDMS-to-time behavior.
- `src/data_io/tdms_reader_frequency.py`: Wrapper for time CSV to FFT behavior.
- `src/data_io/tdms_reader_frequency_average.py`: Wrapper for FFT averaging behavior.
- `src/visualization/time_series_plots.py`: Wrapper for time quality plotting/export behavior.
- `src/visualization/frequency_plots.py`: Wrapper for frequency analysis behavior.
- `src/visualization/fft_analysis.py`: Compatibility alias/wrapper for frequency analysis.

Utility scripts:

- `scripts/profile_pipeline.py`: Profiles `timedata`, `freqdata`, `freqavedata`, `timeplots`, `freqplots`, or `all`, writing `profiling_result.prof`, `profiling_top50.txt`, and `module_timing_summary.json`.
- `scripts/build_analysis_package.py`: Builds `analysis_out/` outputs and `analysis_out.zip` from real-data/NIST-derived sources. It writes summary reports, CSV tables, figures, and package logs.

### 5. Pipeline / Run Entry Points

Confirmed commands from repository files:

```powershell
python -m src.main timedata
python -m src.main freqdata
python -m src.main freqavedata
python -m src.main timeplots
python -m src.main freqplots
python -m src.main nistdiagnostics
python -m src.main nistplots
python -m src.main visualize
python -m src.main report
python -m src.main all
```

Main CLI options visible in `src/main.py` include:

```powershell
python -m src.main <module> --data-folder <path>
python -m src.main <module> --input <path> --output <path>
python -m src.main <module> --config config/parameters.yaml --log-config config/logging.yaml
python -m src.main freqplots --plots none|minimal|full --dpi 150 --max-plot-points 5000
python -m src.main <module> --force
python -m src.main <module> --no-skip-existing
python -m src.main timeplots --export-excel
```

Preset wrapper commands from `run.py`:

```powershell
python run.py full
python run.py preprocess
python run.py time
python run.py freq
python run.py visualize
python run.py report
python run.py load
python run.py time <data_folder>
python run.py preprocess <data_folder>
```

Direct pipeline commands found in README/docs/code:

```powershell
python -m src.pipelines.tdms_to_time_pipeline
python -m src.pipelines.fft_export_pipeline
python -m src.pipelines.fft_average_pipeline
python -m src.pipelines.time_quality_pipeline --input <time_csv_folder>
python -m src.pipelines.frequency_analysis_pipeline
python -m src.pipelines.frequency_analysis_pipeline --input <fft_csv_folder> --output <out_dir> --plots none
python -m src.pipelines.frequency_analysis_pipeline --input <fft_csv_folder> --output <out_dir> --plots minimal
python -m src.pipelines.frequency_analysis_pipeline --input <fft_csv_folder> --output <out_dir> --plots full
python -m src.pipelines.background_contrast_smoke_pipeline
python -m src.pipelines.background_contrast_smoke_pipeline --output <out_dir>
python -m src.pipelines.background_contrast_real_pipeline
python -m src.pipelines.background_contrast_real_pipeline --time-root <time_root> --nist-root <nist_root> --output <out_dir>
```

Profiling commands found in docs/script:

```powershell
python scripts/profile_pipeline.py --module timeplots --data-folder <path>
python scripts/profile_pipeline.py --module freqplots --output-dir analysis_out/perf/freqplots
python scripts/profile_pipeline.py --module all --data-folder <small_test_group>
```

Build/package script:

```powershell
python scripts/build_analysis_package.py
```

Testing commands found in docs/README:

```powershell
python -m pytest tests -q
python -m compileall -q src tests
python -m pytest tests/test_cache_utils.py -q
python -m pytest tests/test_freqplots_main_output_smoke.py -q
python -m pytest tests/test_pipeline_cache_smoke.py -q
```

No tests or pipelines were run while creating this `PROJECT_STATE.md`.

### 6. Discovery Notes

This `PROJECT_STATE.md` was generated from a conservative repository discovery pass. It used file/directory scans plus targeted reads of key project files. No long-running data pipeline was executed.

Key files and directories actually referenced during discovery:

- Root files: `README.md`, `run.py`, `requirements.txt`, `REQUIREMENTS.md`, `analysis_output_check_report.md`.
- Config files: `config/rawpath.yaml`, `config/paths.yaml`, `config/parameters.yaml`, `config/logging.yaml`.
- Main code structure: `src/main.py`, `src/core/`, `src/io/`, `src/features/`, `src/summaries/`, `src/reports/`, `src/plots/`, `src/pipelines/`, `src/data_io/`, `src/visualization/`, `src/utils/`.
- Pipeline/script files read directly: `src/pipelines/background_contrast_smoke_pipeline.py`, `src/pipelines/background_contrast_real_pipeline.py`, `scripts/profile_pipeline.py`.
- Documentation read directly or scanned for commands/outputs: `docs/BACKGROUND_CONTRAST_V1.md`, `docs/PERFORMANCE_AUDIT.md`, `docs/PERFORMANCE_FULL_GROUP_V1_2.md`, plus filenames in the rest of `docs/`.
- Output directories scanned: `analysis_out/`, `analysis_out/csv/`, `analysis_out/figures/`, `analysis_out/contrast_v1_smoke/`, `analysis_out/perf_quick_smoke/`, `analysis_out/perf_full_group_v1_2/`, `results/`, `logs/`.
- Tests scanned by filename and search results: `tests/`.

Content not fully checked:

- External data under `D:/Lab` was not opened or validated.
- Large/generated outputs were not exhaustively read; only directory/file names and selected reports/logs were inspected.
- Most source files were identified by path and search results, not line-by-line audited.
- `verification/` was not deeply inspected because it appears to contain extensive SystemVerilog/UVM material with unclear relation to this Python data-processing project.
- `articles/` PDF contents were not read; only filenames and processed paragraph-summary files were noted.
- No scientific validity, data quality, or research conclusion was evaluated.

### 7. Known Human Decisions

These decisions should not be made automatically by AI:

- Confirm the scientific/experimental meaning of group names such as `2m0hz`, `2m30hz`, `2m50hz`, `3m0hz`, `3m30hz`, `3m50hz`, `5m0hz`, `5m30hz`, and `5m50hz`.
- Confirm which groups are background groups and which are target/experiment groups.
- Confirm whether same-distance `0hz` groups may be used as background references.
- Confirm whether strong waveform-level background cancellation is allowed. Repository docs currently describe background contrast as feature-level and explicitly not point-by-point waveform subtraction.
- Confirm whether only feature-level contrast should be used for current reporting.
- Confirm which outputs are exploratory, internal QA, benchmark-only, smoke-only, or acceptable for external reports/papers.
- Confirm whether old `results/2025.11.11`, `results/retry`, and deleted/absent `fft_analysis_results` git entries should remain historical references or be ignored.
- Confirm whether `analysis_out/summary_report.md` conclusions should be used as research conclusions or treated only as generated analysis notes.
- Confirm whether full real-data processing is allowed in future AI/Codex runs, because the pipeline can read/write large external directories under `D:/Lab`.
- Confirm assumptions about stationarity, synchronization, channel identity, sampling rate, metadata reliability, frequency resolution, and TDMS channel mapping.
- Confirm whether the current `config/parameters.yaml` value `time_channels: 8` is still meaningful when recent real-data reports show 12 channels.
- Confirm whether `verification/`, `interview/`, and `articles/` belong to this project state or should be moved/excluded.

### 8. Maintenance Notes

Update this file whenever a new module, pipeline, data run, output directory, report, or important configuration change is added.

For each update, record:

- Date.
- Change summary.
- New or modified files.
- New data or outputs.
- Run command, if any.
- Output path, if any.
- Unresolved questions.
- Human decisions still required.

Keep this file as a navigation and project-state document. Do not turn it into a research evaluation report, and do not use it to certify algorithmic or scientific validity. If evidence is missing or ambiguous, write `UNKNOWN` or `Need human confirmation` instead of guessing.

---

## 中文版 / Chinese Translation

### 1. 项目身份

这看起来是一个用于实验采集传感器/时间序列数据的 Python 数据处理与分析项目。仓库中包含将 TDMS 文件转换为时域 CSV 和 metadata、导出 FFT CSV、按文件夹/组平均 FFT 文件、计算时域指标、生成频域图表与 JSON/CSV summary，以及运行 NIST 风格的 run-sequence/lag/distribution/PSD/ACF 诊断的代码。仓库中也发现了 background contrast 模块及相关 smoke/real-data 脚本，但它应作为已发现的一个模块家族记录，而不是作为整个项目的中心身份。

主要可识别的数据类型似乎是多通道采样时间序列数据。仓库证据显示项目使用 TDMS 原始输入、time CSV 中间文件、FFT CSV 中间文件、Excel/CSV/JSON/PNG/TXT 输出，以及 metadata JSON 文件。当前本机配置路径指向 `D:/Lab/raw/26.5.12`、`D:/Lab/process/26.5.12/*` 和 `D:/Lab/results/26.5.12/*`；在没有人工确认前，不应把这些路径视为项目永久路径。已有报告提到已处理组 `2m0hz`、`2m30hz`、`2m50hz`、`3m0hz`、`3m30hz`、`3m50hz`、`5m0hz`、`5m30hz` 和 `5m50hz`，并在报告中的已检查真实数据运行中记录每个组 12 个通道、40 个文件。

可以从仓库中确认的事实：

- 项目有 Python CLI 入口 `src/main.py`，以及 preset 包装入口 `run.py`。
- 主处理链路看起来是 TDMS -> time CSV/metadata -> FFT CSV -> average FFT CSV -> time/frequency/NIST 输出。
- 代码已拆分为 `core`、`io`、`features`、`summaries`、`reports`、`plots`、`pipelines`、兼容旧入口的 `data_io` wrappers，以及兼容旧入口的 `visualization` wrappers。
- 仓库内已有输出位于 `analysis_out/` 和 `results/`。
- `docs/` 下存在性能、cache、metric registry 和 background contrast 相关文档。

仍需人工确认的事项：

- 每个数据组名称的科学/实验含义。
- 哪些组是真正的 background 组，哪些组是 target/experiment 组。
- 是否接受同距离 `0 Hz` 组作为未来所有分析的 background reference。
- feature-level background contrast 是否足够，或者是否允许更强的 waveform-level cancellation。
- 哪些生成输出是探索性的、仅内部使用的，哪些可以用于报告/论文。
- `verification/`、`interview/` 和 `articles/` 应被视为本 DataProcess 项目的一部分，还是相邻/历史材料。

项目身份是根据仓库内容部分推断的，需要人工确认。

### 2. 仓库总览

与项目相关的目录和文件：

- `README.md`：主项目概览、CLI 用法、pipeline map、预期输出和当前代码结构。该文件在当前 PowerShell 显示中出现乱码，但结构和命令仍可识别。
- `REQUIREMENTS.md` 和 `requirements.txt`：依赖和需求相关文件。
- `run.py`：对 `python -m src.main` 的 preset 包装。preset 包括 `full`、`preprocess`、`time`、`freq`、`visualize`、`report` 和 `load`。
- `config/`：运行配置。
  - `rawpath.yaml`：带 `${work_dir}` 变量的路径模板式配置。
  - `paths.yaml`：已生成/解析的路径。当前本机配置路径指向 `D:/Lab` 和日期 `26.5.12`；这不应被假定为项目永久路径。
  - `parameters.yaml`：当前包含时域参数，例如 `time_channels: 8`、`time_sampling_rate: 500000` 和 `time_window_size: 1000`。
  - `logging.yaml`：日志配置。
- `src/`：主要 Python 实现。
  - `src/main.py`：主 CLI dispatcher。
  - `src/core/`：配置加载、常量和路径解析 helper。
  - `src/io/`：CSV/TDMS/metadata 读取 helper。
  - `src/features/`：核心计算，包括 FFT、time metrics、NIST diagnostics/PSD/ACF 和 background contrast。
  - `src/summaries/`：time metrics、frequency summaries、NIST diagnostics 和 background contrast 的组级 summary。
  - `src/reports/`：Excel/CSV/JSON/TXT/background-contrast 导出器。
  - `src/plots/`：frequency 和 NIST 图表生成。
  - `src/pipelines/`：pipeline 入口。
  - `src/data_io/` 和 `src/visualization/`：兼容旧入口的 wrappers/aliases。
  - `src/utils/`：文件工具、日志工具、cache 工具和性能 timing。
- `scripts/`：工具脚本。
  - `profile_pipeline.py`：针对指定 pipeline module 的 cProfile/tracemalloc wrapper。
  - `build_analysis_package.py`：构建 `analysis_out/` package、summary report、CSV tables、figures 和 `analysis_out.zip`。
- `tests/`：针对 cache utilities、FFT core、metadata/time CSV IO、path resolver、frequency plots、NIST plots/diagnostics、pipeline cache 行为、time metrics 和 background contrast 的 smoke/unit 风格测试。
- `docs/`：项目文档和运行记录。
  - `BACKGROUND_CONTRAST_V1.md`：根据该文档，它记录 background contrast 的 scope、schema、pairing rule、smoke coverage 和 smoke command。
  - `METRIC_REGISTRY.md`：看起来记录指标定义和实现位置。
  - `PERFORMANCE_AUDIT.md`、`PERFORMANCE_CACHE_V1_2.md`、`PERFORMANCE_V1_1_RESULT.md`、`PERFORMANCE_FULL_GROUP_V1_2.md`：根据这些文档，它们记录性能/cache/运行观察和输出位置。
- `analysis_out/`：根据文件名和其中的报告，这是已有生成的 analysis package 和 performance/smoke 输出。
- `results/`：较旧的本地结果输出，包括 `2025.11.11` 和 `retry`；当前相关性需要人工确认。
- `logs/`：应用日志，主要是 2026 年 5 月。
- `analysis_output_check_report.md`：看起来是针对 26.5.12 运行的真实数据输出检查报告。
- `analysis_out.zip`：看起来是由 `analysis_out/` 生成的压缩包。

相关性不清楚或可能属于相邻内容的目录：

- `articles/`：包含 raw PDF 文件和 paragraph summaries。它可能是项目文献/参考材料，但未确认与 pipeline 直接相连。Need human confirmation。
- `verification/`：包含大量 SystemVerilog/UVM/RTL 验证内容和验证文档。从扫描到的内容看，它似乎与 Python DataProcess pipeline 无关。Need human confirmation。
- `interview/`：包含 SystemVerilog 文件。与本数据处理项目的关系不清楚。Need human confirmation。
- `.pytest_cache/`、`__pycache__/`：缓存目录；不纳入项目状态。

### 3. 数据清单与已有输出文件

输入与中间数据清单：

- 当前本机配置路径中的 raw data root：`D:/Lab/raw/26.5.12`。
  - 预期原始格式：`*.tdms`。
  - 在已扫描的仓库根目录内未发现本地 raw TDMS 文件。
  - 根据配置和报告，当前 raw data 似乎位于仓库外部。
- 当前本机配置路径中的时域中间数据 root：`D:/Lab/process/26.5.12/time`。
  - 预期文件：time CSV 和对应的 `*_metadata.json`。
  - 预期 CSV 列：`time`，随后是 `channel1`、`channel2` 等通道列。
  - 根据 README，metadata 字段包括 filename、start time、sampling interval/rate、data length、duration、channel count 和 channel names。
- 当前本机配置路径中的频域中间数据 root：`D:/Lab/process/26.5.12/frequency`。
  - 预期文件：`FFT_<input_filename>.csv`。
  - 预期列：`frequency`，随后是每个通道的 amplitude/phase 列。
- 当前本机配置路径中的 average FFT root：`D:/Lab/process/26.5.12/frequency_ave`。
  - 预期文件：`average_fft_<folder_name>_<file_count>files.csv` 和 `processing_summary.txt`。
- 当前本机配置路径中的 analysis output roots：
  - `D:/Lab/results/26.5.12/time`
  - `D:/Lab/results/26.5.12/frequency`
  - NIST 和 background contrast 路径看起来由代码/docs 从 results root 推导。
- 已有真实数据检查报告：
  - `analysis_output_check_report.md` 报告 full real-data flow 使用了 `D:\Lab\raw\26.5.12`、`D:\Lab\process\26.5.12\time` 和 `D:\Lab\results\26.5.12`；这些是该文件报告的当前本机路径，不是项目永久路径。
  - 它报告了已处理组 `2m0hz`、`2m30hz`、`2m50hz`、`3m0hz`、`3m30hz`、`3m50hz`、`5m0hz`、`5m30hz` 和 `5m50hz`。
  - 它报告每个已处理组有 40 个 raw TDMS 文件和 40 个 time CSV 文件，每组 12 个通道，并且这 9 个已处理组没有缺失文件。
  - 它报告 `3m20hz` 是 requested-but-not-found，`3m30hz` 是 found-and-processed。
  - 它报告在该检查流程中 background subtraction 未配置且未运行。
- 数据分组和实验含义需要人工确认。

仓库内已有输出文件：

- `analysis_out/summary_report.md`：看起来是生成的 analysis package summary。它报告 9 个 input groups、12 个 channels、每组 40 个 files，并汇总 NIST/PSD/ACF/background-vs-active 风格的派生输出。该文件中的科学结论不应被本状态文件视为已验证结论。
- `analysis_out/run_log.txt`：看起来是 `analysis_out` 构建日志；它报告 `TIME_ROOT=D:\Lab\process\26.5.12\time`、`NIST_ROOT=D:\Lab\results\26.5.12\nist_diagnostics`、找到 9 个组、生成 Excel、13 个 CSV 表、7 张图，以及 elapsed seconds。这些 `D:\Lab` 路径是报告中的当前本机路径。
- `analysis_out/all_groups_summary.xlsx` 和 `analysis_out/all_groups_summary.csv`：组级 summary 输出。
- `analysis_out/csv/`：已有 CSV 导出，包括 ACF summaries、PSD summaries、background contrast、distance decay、low-frequency summary、manifest、PSD/ACF matches、pump-frequency contrast、sideband summary 和 cross-channel peak summaries。
- `analysis_out/figures/`：已有 PNG 图，包括 ACF、background contrast heatmap、bandpower、cross-channel peaks、distance decay、PSD dominant frequency 和 pump 30 vs 50 contrast。
- `analysis_out/contrast_v1_smoke/`：background contrast 的 synthetic smoke 输出，包括 Excel、CSV、TXT 和 Markdown report 文件。
- `analysis_out/perf_quick_smoke/`：使用小样本的 quick smoke/performance 输入和输出、timing JSON、validation JSON、cache metadata、timeplots/freqdata/freqavedata/freqplots 输出，以及 v1.1/cache validation 输出。
- `analysis_out/perf_full_group_v1_2/`：根据文件名和性能文档，这里包含完整 `2m0hz` frequency group benchmark 输出，包含 `none`、`minimal`、`full` plot modes、timing JSON、stdout/stderr logs、cache metadata 和 benchmark summaries。
- `results/2025.11.11/`：较旧的 `GROUP1`/`GROUP2` frequency/time result 输出和 summary JSON。在视为当前结果前需要人工确认。
- `results/retry/`：较旧的 `GROUP1` retry time 输出和图。在视为当前结果前需要人工确认。
- `logs/`：2026 年 5 月运行日志。
- `analysis_out.zip`：`analysis_out/` 的打包副本。

### 4. 数据处理模块

主 CLI 与流程组织：

- `src/main.py`：主 dispatcher，支持 `timedata`、`freqdata`、`freqavedata`、`timeplots`、`freqplots`、`nistdiagnostics`、`nistplots`、`visualize`、`report` 和 `all`。启动时还会调用 `generate_paths_config()`。
- `run.py`：preset runner，会使用 `--config config/parameters.yaml` 调用 `python -m src.main <module>`。

配置/路径模块：

- `src/core/config_loader.py`：查找 project root 并加载配置。
- `src/core/path_resolver.py`：解析 scan folders 并推导输出路径，包括 time metrics 和 NIST diagnostics 输出路径。
- `src/utils/file_utils.py`：根据 `config/rawpath.yaml` 生成 `config/paths.yaml`。
- `src/utils/cache_utils.py`：为 pipeline stages 构建和检查 cache metadata。
- `src/utils/perf_timing.py`：记录 timing summaries。
- `src/utils/logging_utils.py`：设置日志。

输入/输出模块：

- `src/io/tdms_io.py`：TDMS 相关 IO helper。本文档未完整枚举其精确行为。
- `src/io/time_csv_io.py`：读取 time CSV 数据/表头并收集 CSV groups，会排除已知输出文件名。
- `src/io/metadata_io.py`：标准化 sampling-rate metadata。
- `src/io/fft_csv_io.py`：FFT CSV IO helper。本文档未完整枚举其精确行为。

Pipeline 模块：

- `src/pipelines/tdms_to_time_pipeline.py`：将 TDMS 文件转换为 time CSV 和 metadata JSON。可能输入：`raw_data_dir/**/*.tdms`。可能输出：在 `tdms_reader_time_output_dir` 下保留相对结构的 CSV 和 `*_metadata.json`。
- `src/pipelines/fft_export_pipeline.py`：将 time CSV 文件转换为 FFT CSV。可能输入：time CSV 加 metadata JSON。输出：`tdms_reader_frequency_output_dir` 下的 `FFT_<input_filename>.csv`；cache metadata 位于 `.cache/freqdata_cache.json`。
- `src/pipelines/fft_average_pipeline.py`：按文件夹平均 `FFT_*.csv` 文件。输出：`average_fft_<folder>_<count>files.csv`、summary text 和 cache metadata。
- `src/pipelines/time_quality_pipeline.py`：计算时域单文件指标、组级 summary 和数据完整性 summary。输入：time CSV 文件或文件夹。输出：`time_series_metrics.xlsx` 或 CSV、`time_series_group_summary.xlsx`、`data_completeness_summary.xlsx`。
- `src/pipelines/frequency_analysis_pipeline.py`：计算频域组级指标和可选图表。输入：FFT CSV 文件/文件夹。输出：每组 `frequency_plots_report.json`、`dominant_frequencies.csv`、可选 PNG 图、`fft_analysis_summary.json` 和 `.cache/freqplots_cache.json`。
- `src/pipelines/nist_diagnostics_pipeline.py`：对 time CSV groups 运行 NIST 风格 diagnostics、PSD、ACF、summaries 和可选 4-plot/ACF/PSD figures。输出包括 `nist_diagnostics_metrics.xlsx`、`nist_file_stability_summary.xlsx`、`nist_diagnostics_group_summary.xlsx`、`acf_group_summary.xlsx`、`psd_group_summary.xlsx`、`psd_acf_summary.xlsx`、`psd_acf_peak_matches.xlsx`、`harmonic_matches_long.xlsx`、`cross_channel_peak_summary.xlsx`、`psd_peaks_long.xlsx`、`acf_peaks_long.xlsx`、`background_subtraction_summary.xlsx` 和 `figures/`。
- `src/pipelines/background_contrast_smoke_pipeline.py`：构造 synthetic smoke inputs，并默认向 `analysis_out/contrast_v1_smoke/` 导出 background-contrast smoke outputs。这里将它记录为一个已发现的 module/pipeline family。
- `src/pipelines/background_contrast_real_pipeline.py`：看起来会读取配置的 time/NIST 真实数据输出，对固定组计算 feature-level background contrast，并默认写入当前本机配置派生的 `D:/Lab/results/26.5.12/background_contrast_v1` 路径下的 CSV/XLSX/PNG/Markdown/TXT 输出，除非提供 `--output`。没有人工确认前，不应把该路径视为永久路径。

Feature 模块：

- `src/features/time_metrics.py`：单文件时域指标，例如 sample count、duration、dt statistics、mean/median/min/max、peak-to-peak、std、AC RMS、robust sigma、crest factor、drift metrics、outlier/spike/tail/extreme rates，以及 QC helper functions。
- `src/features/fft_core.py`：FFT 计算 helper。
- `src/features/fft_statistics.py`：频域统计 helper。此处未完整枚举精确输出。
- `src/features/fft_average.py`：FFT 平均 helper。
- `src/features/nist_diagnostics.py`：NIST 风格 run sequence、lag、distribution 和 normal probability metrics。
- `src/features/nist_psd.py`：Welch PSD、peak、bandpower、spectral entropy 和 low-frequency PSD metrics。
- `src/features/nist_acf.py`：ACF diagnostics、peaks、peak spacing、PSD/ACF matching 和相关 period metrics。
- `src/features/background_contrast.py`：针对 PSD gain curves、bandpower、peaks 和 ACF 的 feature-level background pairing 与 contrast。

Summary/report/plot 模块：

- `src/summaries/time_group_summary.py`：时域组级和 completeness summaries。
- `src/summaries/frequency_group_summary.py`：频域组级 summary helper。
- `src/summaries/nist_diagnostics_summary.py`：NIST diagnostics summaries。
- `src/summaries/background_contrast_summary.py`：background contrast 的 cross-channel support、30 Hz vs 50 Hz net contrast、distance decay 和 outlier marking。
- `src/reports/excel_export.py`：time metrics/group/completeness Excel exporters。
- `src/reports/nist_excel_export.py`：NIST/PSD/ACF Excel exporters。
- `src/reports/background_contrast_export.py`：background contrast smoke exporters。
- `src/reports/csv_export.py`、`json_report.py`、`text_report.py`：通用导出 helper。
- `src/plots/frequency_plots.py`、`src/plots/nist_4plot.py`、`src/plots/nist_acf_plot.py`、`src/plots/nist_psd_plot.py`：绘图模块。

兼容旧入口 wrappers：

- `src/data_io/tdms_reader_time.py`：TDMS-to-time 行为的 wrapper。
- `src/data_io/tdms_reader_frequency.py`：time CSV to FFT 行为的 wrapper。
- `src/data_io/tdms_reader_frequency_average.py`：FFT averaging 行为的 wrapper。
- `src/visualization/time_series_plots.py`：time quality plotting/export 行为的 wrapper。
- `src/visualization/frequency_plots.py`：frequency analysis 行为的 wrapper。
- `src/visualization/fft_analysis.py`：frequency analysis 的 compatibility alias/wrapper。

工具脚本：

- `scripts/profile_pipeline.py`：profile `timedata`、`freqdata`、`freqavedata`、`timeplots`、`freqplots` 或 `all`，输出 `profiling_result.prof`、`profiling_top50.txt` 和 `module_timing_summary.json`。
- `scripts/build_analysis_package.py`：从 real-data/NIST-derived sources 构建 `analysis_out/` 输出和 `analysis_out.zip`。它会写 summary reports、CSV tables、figures 和 package logs。

### 5. Pipeline / 运行入口

仓库文件中确认的命令：

```powershell
python -m src.main timedata
python -m src.main freqdata
python -m src.main freqavedata
python -m src.main timeplots
python -m src.main freqplots
python -m src.main nistdiagnostics
python -m src.main nistplots
python -m src.main visualize
python -m src.main report
python -m src.main all
```

`src/main.py` 中可见的主要 CLI options 包括：

```powershell
python -m src.main <module> --data-folder <path>
python -m src.main <module> --input <path> --output <path>
python -m src.main <module> --config config/parameters.yaml --log-config config/logging.yaml
python -m src.main freqplots --plots none|minimal|full --dpi 150 --max-plot-points 5000
python -m src.main <module> --force
python -m src.main <module> --no-skip-existing
python -m src.main timeplots --export-excel
```

`run.py` 中的 preset wrapper 命令：

```powershell
python run.py full
python run.py preprocess
python run.py time
python run.py freq
python run.py visualize
python run.py report
python run.py load
python run.py time <data_folder>
python run.py preprocess <data_folder>
```

README/docs/code 中找到的直接 pipeline 命令：

```powershell
python -m src.pipelines.tdms_to_time_pipeline
python -m src.pipelines.fft_export_pipeline
python -m src.pipelines.fft_average_pipeline
python -m src.pipelines.time_quality_pipeline --input <time_csv_folder>
python -m src.pipelines.frequency_analysis_pipeline
python -m src.pipelines.frequency_analysis_pipeline --input <fft_csv_folder> --output <out_dir> --plots none
python -m src.pipelines.frequency_analysis_pipeline --input <fft_csv_folder> --output <out_dir> --plots minimal
python -m src.pipelines.frequency_analysis_pipeline --input <fft_csv_folder> --output <out_dir> --plots full
python -m src.pipelines.background_contrast_smoke_pipeline
python -m src.pipelines.background_contrast_smoke_pipeline --output <out_dir>
python -m src.pipelines.background_contrast_real_pipeline
python -m src.pipelines.background_contrast_real_pipeline --time-root <time_root> --nist-root <nist_root> --output <out_dir>
```

docs/script 中找到的 profiling 命令：

```powershell
python scripts/profile_pipeline.py --module timeplots --data-folder <path>
python scripts/profile_pipeline.py --module freqplots --output-dir analysis_out/perf/freqplots
python scripts/profile_pipeline.py --module all --data-folder <small_test_group>
```

构建/package 脚本：

```powershell
python scripts/build_analysis_package.py
```

docs/README 中找到的测试命令：

```powershell
python -m pytest tests -q
python -m compileall -q src tests
python -m pytest tests/test_cache_utils.py -q
python -m pytest tests/test_freqplots_main_output_smoke.py -q
python -m pytest tests/test_pipeline_cache_smoke.py -q
```

创建本 `PROJECT_STATE.md` 时没有运行测试或 pipeline。

### 6. Discovery Notes / 发现记录

本 `PROJECT_STATE.md` 是通过一次保守的仓库 discovery 生成和修订的。过程使用了文件/目录扫描，以及对关键项目文件的定向读取。没有执行耗时数据 pipeline。

本次 discovery 实际参考的关键文件和目录：

- 根目录文件：`README.md`、`run.py`、`requirements.txt`、`REQUIREMENTS.md`、`analysis_output_check_report.md`。
- 配置文件：`config/rawpath.yaml`、`config/paths.yaml`、`config/parameters.yaml`、`config/logging.yaml`。
- 主要代码结构：`src/main.py`、`src/core/`、`src/io/`、`src/features/`、`src/summaries/`、`src/reports/`、`src/plots/`、`src/pipelines/`、`src/data_io/`、`src/visualization/`、`src/utils/`。
- 直接读取过的 pipeline/script 文件：`src/pipelines/background_contrast_smoke_pipeline.py`、`src/pipelines/background_contrast_real_pipeline.py`、`scripts/profile_pipeline.py`。
- 直接读取或通过搜索扫描过命令/输出的文档：`docs/BACKGROUND_CONTRAST_V1.md`、`docs/PERFORMANCE_AUDIT.md`、`docs/PERFORMANCE_FULL_GROUP_V1_2.md`，以及 `docs/` 中其他文件的文件名。
- 扫描过的输出目录：`analysis_out/`、`analysis_out/csv/`、`analysis_out/figures/`、`analysis_out/contrast_v1_smoke/`、`analysis_out/perf_quick_smoke/`、`analysis_out/perf_full_group_v1_2/`、`results/`、`logs/`。
- 通过文件名和搜索结果扫描过的测试目录：`tests/`。

未完整检查的内容：

- 未打开或验证 `D:/Lab` 下的外部数据。
- 未穷尽读取大型/生成输出；只检查了目录/文件名和部分报告/日志。
- 大多数源码文件是通过路径和搜索结果识别的，不是逐行审计。
- `verification/` 未深入检查，因为它看起来包含大量 SystemVerilog/UVM 材料，和本 Python 数据处理项目的关系不清楚。
- 未读取 `articles/` 中 PDF 的内容；只记录了文件名和已处理的 paragraph-summary 文件。
- 未评价科学有效性、数据质量或研究结论。

### 7. 需要人工确认的关键决策

以下决策不应由 AI 自动决定：

- 确认 `2m0hz`、`2m30hz`、`2m50hz`、`3m0hz`、`3m30hz`、`3m50hz`、`5m0hz`、`5m30hz`、`5m50hz` 等 group names 的科学/实验含义。
- 确认哪些组是 background groups，哪些组是 target/experiment groups。
- 确认是否可以使用同距离 `0hz` groups 作为 background references。
- 确认是否允许 strong waveform-level background cancellation。仓库文档当前将 background contrast 描述为 feature-level，并明确不是 point-by-point waveform subtraction。
- 确认当前报告是否只能使用 feature-level contrast。
- 确认哪些输出是 exploratory、internal QA、benchmark-only、smoke-only，哪些可以用于外部报告/论文。
- 确认旧的 `results/2025.11.11`、`results/retry` 和 git 中已删除/当前不存在的 `fft_analysis_results` 条目应作为历史参考保留还是忽略。
- 确认 `analysis_out/summary_report.md` 中的 conclusions 应作为研究结论使用，还是仅作为生成的 analysis notes。
- 确认未来 AI/Codex 是否允许运行 full real-data processing，因为 pipeline 可能读取/写入 `D:/Lab` 下的大型外部目录。
- 确认关于 stationarity、synchronization、channel identity、sampling rate、metadata reliability、frequency resolution 和 TDMS channel mapping 的假设。
- 确认当近期真实数据报告显示 12 个通道时，当前 `config/parameters.yaml` 中的 `time_channels: 8` 是否仍有意义。
- 确认 `verification/`、`interview/` 和 `articles/` 是否属于本项目状态，还是应移动/排除。

### 8. 维护说明

每当新增 module、pipeline、data run、output directory、report 或重要配置变更时，都应更新本文件。

每次更新时记录：

- 日期。
- 变更摘要。
- 新增或修改的文件。
- 新数据或输出。
- 运行命令（如果有）。
- 输出路径（如果有）。
- 未解决问题。
- 仍需人工确认的决策。

请将本文件保持为导航和项目状态文档。不要把它变成研究评价报告，也不要用它来证明算法或科学有效性。如果证据缺失或含糊，请写 `UNKNOWN` 或 `Need human confirmation`，不要猜测。
---

## 2026-06-14 Update - merged TDMS and first-test-pipeline

This section records the latest Codex-side changes so later work can resume without rediscovery.

### New / changed code

- Added merged TDMS time-data conversion support:
  - `src/data_io/tdms_reader_time_merged.py`
  - `src/pipelines/merged_tdms_to_time_pipeline.py`
- Added `first-test-pipeline`:
  - `src/pipelines/first_test_pipeline.py`
  - wired through `src/main.py`
- Added/updated PSD review plotting:
  - `src/plots/nist_psd_plot.py`
  - first-test PSD output now keeps only:
    - one full `0-200 kHz` figure
    - split bands `0-20`, `20-40`, `40-60`, `60-80`, `80-100`, `100-120`, `120-140`, `140-160`, `160-180`, `180-200 kHz`
- Added tests:
  - `tests/test_merged_tdms_segments.py`
  - `tests/test_first_test_pipeline.py`

### Merged TDMS conversion behavior

- New raw format assumption: each experimental group can contain one large merged `.tdms` file instead of many short legacy files.
- The new conversion pipeline splits a merged TDMS into legacy-compatible process CSV segments with columns such as `time`, `channel1`, `channel2`, etc.
- Default segment duration is `2.7` seconds, matching the existing `FILE_DURATION` convention.
- Important CLI options:
  - `--segment-seconds`
  - `--min-segment-seconds`
  - `--max-segments-per-file`
  - `--max-workers`
  - `--skip-existing` / `--no-skip-existing`
- Resume behavior:
  - completed CSV + metadata segment pairs are skipped by default
  - logs include `RESUME merged_timedata skip existing segment ...`

Example:

```powershell
python -m src.pipelines.merged_tdms_to_time_pipeline --input "D:\Lab\raw\44.6.9\vac" --output "D:\Lab\process\44.6.9\vac\time" --segment-seconds 2.7 --max-segments-per-file 3 --max-workers 1
```

### first-test-pipeline behavior

Pipeline name: `first-test-pipeline`.

Main outputs:

- NIST-style 4-plot figures
- PSD review figures
- median bandpower gain dB table/figures, optional and should be skipped when no background group exists
- file-level time-domain feature table
- group-level time-domain summary table
- data-completeness summary
- `figure_index.csv`
- `first_test_manifest.json`

Important CLI switches:

- `--skip-4plot`
- `--skip-psd`
- `--skip-bandpower-gain`
- `--skip-time-stats`
- `--export-time-stats-excel`
- `--max-files`
- `--max-channels`
- `--skip-existing` / `--no-skip-existing`

The time-domain statistics are intentionally implemented by calling existing project methods, not by adding new feature math:

- `time_quality_pipeline.process_files`
- `time_metrics.calculate_file_metrics`
- `time_group_summary.summarize_group_metrics`
- `time_group_summary.summarize_data_completeness`
- `excel_export` helpers when Excel export is enabled

Resume behavior:

- group-level manifests are stored under `<output>/.first_test_group_manifests/`
- completed groups are skipped when input files, mtimes, parameters, enabled steps, and expected figures still match
- logs include:
  - `First-test processing group=... progress=X/Y files=N`
  - `RESUME first-test skip existing group=...`
  - `RESUME first-test wrote group manifest...`
- If interrupted mid-group, rerunning the same command should only redo that unfinished group.

Example for `vac`, which currently appears to have no background group:

```powershell
python -m src.main first-test-pipeline --input "D:\Lab\process\44.6.9\vac\time" --output "analysis_out\first_test_pipeline_44_6_9_vac" --max-files 3 --skip-bandpower-gain
```

### Validation already run

```powershell
python -m py_compile src\pipelines\merged_tdms_to_time_pipeline.py src\pipelines\first_test_pipeline.py src\main.py
python -m pytest tests\test_first_test_pipeline.py tests\test_merged_tdms_segments.py
```

Result: `6 passed`.

### Data processing already completed

For non-vac `D:\Lab\raw\44.6.9`:

```powershell
python -m src.pipelines.merged_tdms_to_time_pipeline --input "D:\Lab\raw\44.6.9" --output "D:\Lab\process\44.6.9\time" --segment-seconds 2.7 --max-segments-per-file 3 --max-workers 1
```

Observed result:

- output directory: `D:\Lab\process\44.6.9\time`
- 174 process CSV files
- 174 metadata JSON files
- about 27.49 GB CSV output
- only first 3 segments per TDMS were generated

Then first-test was run:

```powershell
python -m src.main first-test-pipeline --input "D:\Lab\process\44.6.9\time" --output "analysis_out\first_test_pipeline_44_6_9" --max-files 3 --max-channels 0
```

Observed result:

- output directory: `analysis_out\first_test_pipeline_44_6_9`
- groups: 58
- figure-index rows: 5577
- 4plot figures: 696
- PSD figures: 4872
- median bandpower gain figures: 9
- bandpower gain rows: 3240

Caveat: this completed run happened before the PSD review-range change, so future first-test runs will produce fewer PSD figures and only the requested `0-200 kHz` plus `20 kHz` band figures.

### Current estimate for vac full/bounded processing

Inspected input: `D:\Lab\raw\44.6.9\vac`.

Observed:

- about 130 TDMS files
- raw size about 138.89 GB
- appears to have no `no`/background group

Recommended initial bounded run:

- `--max-segments-per-file 3`
- expected process output: about 390 CSV files
- rough process CSV size: about 62 GB
- first-test should use `--skip-bandpower-gain`

Heavier options:

- `--max-segments-per-file 5`: about 650 CSV files, about 103 GB CSV
- `--max-segments-per-file 10`: about 1300 CSV files, about 205 GB CSV
- all segments estimated around 1513 segments and is not recommended as the first pass

### Operational continuation notes

- For long runs, rerun the exact same command to continue from progress; both merged TDMS conversion and first-test now have skip/resume behavior.
- Keep `--skip-existing` as the default unless intentionally regenerating outputs.
- For datasets without a background group, use `--skip-bandpower-gain`; do not run background contrast/cancellation until the background mapping is confirmed by a human.
- If a run is interrupted, check recent logs for `RESUME ...` lines and group progress lines before deciding whether to change the bounded file/segment count.
