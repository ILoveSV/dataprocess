# ML Feature Pipeline Integration v1

## Positioning

This is a reusable pre-ML feature processing and selection workflow. It integrates existing feature-computation, QC/channel-mask, and feature-validation artifacts. It does not train machine-learning models and does not make final scientific claims.

## Three-Layer Structure

### 1. Feature Computation

Computes candidate features from existing time CSV, FFT CSV, or intermediate artifacts. Current modules include frequency PSD/bandpower extraction, time-domain statistics, ACF features, and time-frequency stability features.

### 2. Data Quality and Channel QC

Tracks file quality, channel structure, common-mode/dominant-channel risks, and channel-mask sensitivity. QC modules mark risks and produce mask-specific artifacts; they do not delete raw data or permanently remove channels.

### 3. Feature Validation and Selection

Consumes feature CSV/JSON artifacts and computes stability, separability, redundancy, role assignment, channel-mask robustness, and recommended candidate feature sets. It does not recompute raw signal features.

## Integrated Modules

- `frequency_feature_extraction_v2`: layer=`feature_computation`, status=`complete`, output=`analysis_out\feature_extraction_v2`, runnable
- `time_domain_features_v1`: layer=`feature_computation`, status=`complete`, output=`analysis_out\time_domain_features_v1`, runnable
- `acf_features_v1`: layer=`feature_computation`, status=`complete`, output=`analysis_out\acf_features_v1`, runnable
- `time_frequency_stability_features_v1`: layer=`feature_computation`, status=`complete`, output=`analysis_out\time_frequency_stability_features_v1`, runnable
- `channel_correlation_features_v1`: layer=`qc_and_channel_structure`, status=`complete`, output=`analysis_out\channel_correlation_features_v1`, runnable
- `frequency_feature_separability_v1`: layer=`feature_validation_and_selection`, status=`complete`, output=`analysis_out\feature_separability_v1`, artifact-only; not run by this orchestrator
- `time_frequency_comparison_v1`: layer=`feature_validation_and_selection`, status=`complete`, output=`analysis_out\time_frequency_feature_comparison_v1`, runnable
- `channel_mask_sensitivity_v1`: layer=`qc_and_channel_structure`, status=`complete`, output=`analysis_out\channel_mask_sensitivity_v1`, runnable

## Artifact Connections

- Feature computation modules write long file/channel feature tables and stability summaries.
- Time/frequency, ACF, TF, and channel-mask validation modules consume those existing tables through CSV/JSON artifacts.
- The final pre-ML handoff is the channel-mask sensitivity output plus recommended feature-set JSON files.
- Historical artifacts that contain pilot baseline results are referenced as existing validation outputs, but this orchestrator does not run model-training or baseline-model code.

## How To Re-Run For New Data

Default reuse/inspection run:

```powershell
python -m src.pipelines.ml_feature_pipeline_integration_v1_pipeline --output analysis_out/ml_feature_pipeline_integration_v1
```

Run only missing artifacts:

```powershell
python -m src.pipelines.ml_feature_pipeline_integration_v1_pipeline --time-root D:/Lab/process/NEW/time --fft-root D:/Lab/process/NEW/frequency --background-output D:/Lab/results/NEW/background_contrast_v1 --analysis-root analysis_out/NEW_ml_features --run-missing
```

Use `--force-run` only when intentionally recomputing existing artifacts.

## Future Extension Points

- Water volume and conductivity: extend metadata parsing and task definitions in validation modules, not feature formulas.
- Full 16-channel data: update active-channel discovery and channel QC artifacts; avoid fixed 12-channel assumptions in future modules.
- Channel spatial relationships: add a separate channel-geometry metadata artifact and consume it in channel-structure validation.
- More labels/classes: extend separability task builders while preserving feature CSV schemas.

## Current Pilot Caveats

- Channel9/channel5 masks are current pilot QC artifacts, not permanent rules.
- 50-100 kHz, 100-200 kHz, and peak windows are candidate ranges, not final conclusions.
- Current recommended feature sets are pre-ML candidates only.
- More repeated experiments and cross-batch validation are needed before pilot ML or final claims.

## Scope Guard

- No machine learning was trained.
- No new signal feature algorithm was added.
- No TDMS/FFT/background contrast processing was rerun by default.
- No old modules or outputs were deleted.
