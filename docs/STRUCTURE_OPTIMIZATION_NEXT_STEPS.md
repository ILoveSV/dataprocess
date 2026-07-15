# Structure Optimization Next Steps

## Purpose

This document records the current structural optimization targets for the DataProcess project. It is intended as the next-step engineering guide after the project has expanded from time/frequency EDA and background contrast into PSD zoom, candidate feature extraction, and feature separability gating.

The goal is not to change scientific formulas immediately. The goal is to make the current algorithm chain easier to maintain, rerun, audit, and extend.

## Current Status

The project now contains more analysis stages than the original main workflow describes.

The confirmed algorithm chain is:

```text
TDMS
  -> time CSV + metadata
  -> FFT CSV
  -> NIST diagnostics / PSD / ACF
  -> background contrast
  -> PSD zoom
  -> candidate validation v1
  -> candidate feature extraction v2
  -> feature separability v1
```

The original CLI entry point in `src/main.py` currently exposes:

```text
timedata
freqdata
freqavedata
timeplots
freqplots
nistdiagnostics
nistplots
visualize
report
all
```

The newer stages are implemented as independent pipeline modules under `src/pipelines/`:

- `psd_zoom_pipeline.py`
- `candidate_feature_validation_pipeline.py`
- `candidate_feature_extraction_v2_pipeline.py`
- `feature_separability_v1_pipeline.py`

This is a reasonable staging pattern, but these modules are not yet integrated into the main CLI presets or the full/report workflow.

## Main Structural Issues

### 1. Candidate Feature Definitions Are Duplicated

The same frequency windows and candidate features are hard-coded in multiple places:

- `src/pipelines/candidate_feature_validation_pipeline.py`
- `src/pipelines/candidate_feature_extraction_v2_pipeline.py`
- `src/pipelines/feature_separability_v1_pipeline.py`

Examples include:

- `band_50_100k`
- `band_100_200k`
- subbands from `50_60k` to `180_200k`
- peak windows around 54 kHz, 138 kHz, and 178 kHz

Risk:

- A future change to a frequency window may update one stage but not another.
- Validation, extraction, and separability reports may silently use different definitions.
- Feature naming can drift across CSV outputs.

Recommended optimization:

- Create one shared candidate feature registry, for example:

```text
src/features/candidate_feature_registry.py
```

This registry should define feature id, feature type, frequency bounds, display label, priority, and risk notes.

All candidate feature pipelines should import from this registry instead of defining their own feature lists.

### 2. Active Channel Count Is Hard-Coded

The current analysis correctly treats active channels as 12, but this is hard-coded in several modules.

Examples:

- `REAL_CHANNELS = [f"channel{i}" for i in range(1, 13)]`
- `CHANNELS = [f"channel{i}" for i in range(1, 13)]`
- support ratios using denominator `12`

Risk:

- If a future dataset uses a different active channel set, support count and channel contribution results may be wrong.
- The project may confuse theoretical channel count with actual active channel count.

Recommended optimization:

- Resolve active channels from audit output, config, or detected input columns.
- Preserve `expected_channel_count` separately from `active_channel_count`.
- Avoid hard-coded denominator `12` except in legacy compatibility paths.

### 3. New Pipelines Are Not Integrated Into Main CLI

The newer algorithms are run as direct modules:

```powershell
python -m src.pipelines.psd_zoom_pipeline
python -m src.pipelines.candidate_feature_validation_pipeline
python -m src.pipelines.candidate_feature_extraction_v2_pipeline
python -m src.pipelines.feature_separability_v1_pipeline
```

Risk:

- Users may run `python -m src.main all` and assume the full modern analysis has completed, when it has not.
- `run.py` presets do not represent the current real workflow.
- Report generation may omit the newer outputs.

Recommended optimization:

- Add explicit modules to `src/main.py`, for example:

```text
psdzoom
candidatevalidate
featureextract
featureseparability
candidateflow
```

- Add matching presets in `run.py`.
- Keep the default `all` conservative unless the full runtime and input assumptions are well controlled.

### 4. v1 and v2 Candidate Pipelines Need Clearer Boundaries

Current roles:

- `candidate_feature_validation_v1` uses already aggregated background contrast and PSD zoom outputs.
- `candidate_feature_extraction_v2` extracts file-level/channel-level features directly from FFT CSV files.

This is scientifically important because v1 cannot truly evaluate file-level stability, while v2 can.

Risk:

- v1 outputs may be mistaken for full file-level validation.
- v1 and v2 may appear redundant unless their roles are documented in the workflow.

Recommended optimization:

- Treat v1 as an interpretation and screening layer:

```text
aggregated PSD zoom interpretation / candidate window discovery
```

- Treat v2 as the formal candidate feature source:

```text
file x channel feature dataset construction
```

- Make downstream separability and future ML consume v2 outputs, not v1 outputs.

### 5. Feature Separability Has Moved Ahead Of Final Scientific Validation

`feature_separability_v1_pipeline.py` already builds feature matrices, evaluates AUC/effect size, checks redundancy, runs pilot baseline models, and writes ML readiness gates.

This is useful, but it should remain a gate rather than a final model claim.

Risk:

- Perfect or near-perfect pilot scores may be overinterpreted.
- Remaining risks include frequency-axis filtering, channel dominance, file grouping leakage, and physical mechanism ambiguity.

Recommended optimization:

- Keep the current labels such as `pilot`, `gate`, and `not final model`.
- Require strict-mode inputs for all future modeling.
- Preserve `qc_flag`, `analysis_mode`, `file_id`, `channel`, `distance`, and `rpm` in every downstream feature matrix.
- Do not promote features to final conclusions based only on separability scores.

### 6. Some Older Pipeline Utilities Are Duplicated

Several older pipeline modules still contain local versions of config/path helpers.

Examples include repeated `load_config` or `resolve_scan_folder` style logic in:

- `tdms_to_time_pipeline.py`
- `fft_export_pipeline.py`
- `fft_average_pipeline.py`
- `frequency_analysis_pipeline.py`

There is also at least one duplicated `calculate_fft_statistics` definition in `frequency_analysis_pipeline.py`.

Risk:

- Behavior can diverge across stages.
- Bug fixes to path resolution or config loading may not apply everywhere.

Recommended optimization:

- Consolidate config and path handling into `src/core/config_loader.py` and `src/core/path_resolver.py`.
- Remove duplicate helper definitions after smoke tests pass.
- Keep legacy wrappers only as thin compatibility layers.

### 7. Packaging Script Contains Algorithm-Like Logic

`scripts/build_analysis_package.py` contains several analysis-like helpers, including bandpower, dominant frequency, top peaks, background contrast, and distance decay logic.

Risk:

- The package builder can become a second analysis implementation.
- Reported values may diverge from `src/features/` and `src/summaries/`.

Recommended optimization:

- Treat `scripts/build_analysis_package.py` as packaging/report assembly only.
- Move reusable metrics into `src/features/` or `src/summaries/`.
- Make the script consume existing canonical CSV/XLSX outputs rather than recomputing analysis where possible.

## Recommended Target Structure

The long-term structure should look like this:

```text
src/core/
  config_loader.py
  path_resolver.py

src/io/
  tdms_io.py
  time_csv_io.py
  fft_csv_io.py
  metadata_io.py

src/features/
  time_metrics.py
  nist_diagnostics.py
  nist_psd.py
  nist_acf.py
  background_contrast.py
  candidate_feature_registry.py
  candidate_feature_extraction.py

src/summaries/
  time_group_summary.py
  nist_diagnostics_summary.py
  background_contrast_summary.py
  candidate_feature_summary.py
  feature_separability_summary.py

src/plots/
  nist_4plot.py
  nist_psd_plot.py
  nist_acf_plot.py
  frequency_plots.py
  contrast_plots.py
  candidate_feature_plots.py

src/reports/
  excel_export.py
  nist_excel_export.py
  background_contrast_export.py
  candidate_feature_export.py

src/pipelines/
  tdms_to_time_pipeline.py
  fft_export_pipeline.py
  fft_average_pipeline.py
  time_quality_pipeline.py
  frequency_analysis_pipeline.py
  nist_diagnostics_pipeline.py
  background_contrast_real_pipeline.py
  psd_zoom_pipeline.py
  candidate_feature_validation_pipeline.py
  candidate_feature_extraction_v2_pipeline.py
  feature_separability_v1_pipeline.py
```

The immediate change does not need to move every file. The key is to define canonical owners for feature definitions, channel detection, and pipeline entry points.

## Suggested Optimization Order

### Step 1. Add Candidate Feature Registry

Create a single source of truth for candidate frequency windows.

Expected users:

- PSD zoom
- candidate validation v1
- feature extraction v2
- feature separability v1
- future reports

### Step 2. Centralize Active Channel Resolution

Create helper logic such as:

```text
detect_active_channels(input_tables, expected_channel_count=None)
```

Then update support count, channel heatmap, channel ranking, and feature extraction to consume that resolved list.

### Step 3. Integrate New Pipelines Into CLI

Add explicit module choices in `src/main.py` and presets in `run.py`.

Suggested names:

```text
psdzoom
candidatevalidate
featureextract
featureseparability
candidateflow
```

### Step 4. Document v1/v2 Workflow Boundary

Make the workflow rule explicit:

```text
v1 = aggregated PSD zoom screening and interpretation
v2 = formal file-level/channel-level candidate feature dataset
```

Downstream feature matrices and ML gates should use v2.

### Step 5. Clean Obvious Duplicate Helpers

Start with low-risk cleanup:

- duplicate `calculate_fft_statistics`
- repeated path/config loaders
- duplicated feature column lists

Run existing smoke tests after each cleanup.

### Step 6. Keep ML As A Gate

Do not turn pilot model results into final detection claims yet.

Before final modeling, still require:

- strict frequency-axis filtering
- channel dominance review
- file-level stability confirmation
- distance decay consistency
- detection margin / empirical FPR / empirical TPR

## Non-Goals For This Optimization Pass

Do not change the following during the first structure cleanup:

- background contrast formula
- PSD gain definition
- pump net definition
- time-domain vs feature-level background distinction
- raw TDMS conversion behavior
- scientific interpretation of high-frequency response
- channel deletion policy

The first optimization pass should be structural and reproducibility-focused.

## Desired End State

After optimization, a new user or future Codex run should be able to answer:

- Which pipeline stage owns each output?
- Which feature registry defines every candidate frequency window?
- Which channel list was used, and why?
- Whether strict mode excluded the 9 frequency-axis-risk files.
- Whether a result came from aggregated PSD zoom or file-level FFT extraction.
- Which outputs are screening artifacts, which are candidate features, and which are only pilot ML gates.

The project should preserve the current scientific caution while making the code structure match the actual analysis maturity.
