# Project Context For Continuation

## 1. Project Goal

This project analyzes multi-channel voltage time-series data collected under underwater target / disturbance experiment conditions.

The current goal is:

> Under the current sensor precision and experiment conditions, systematically analyze the collected multi-channel voltage signals and identify time-domain, frequency-domain, multi-channel, and time-frequency features that can stably distinguish different working conditions or target states.

The current stage is not intended to prove the final physical mechanism. It is also not intended to train a final machine-learning model.

The current purpose is to build a reusable pre-ML feature processing and screening workflow:

- convert and check raw data;
- compute candidate signal features;
- mark QC and channel risks;
- compare feature stability and separability;
- prepare candidate feature matrices for later pilot ML, after more experiment variables and repeats are available.

## 2. Experiment System And Data

The experiment system is approximately:

```text
sensor array platform -> amplifier -> NI9222 with BNC analog input -> computer acquisition
```

The sensor body is treated as a black box. It is not currently modified or disassembled. The controllable parts are mainly:

- experiment conditions;
- channel wiring between sensor / amplifier / NI input;
- channel quality checks;
- data processing;
- feature analysis workflow.

Current pilot data focus:

- Main pilot batch: `2026.5.12`;
- Distances: `2m`, `3m`, `5m`;
- Working conditions: `0Hz`, `30Hz`, `50Hz`;
- Typical groups: `2m0hz`, `2m30hz`, `2m50hz`, `3m0hz`, etc.;
- About 40 continuous files per group;
- Current analysis mainly uses 12 active channels;
- Future experiments are expected to extend water volume, conductivity, full 16-channel acquisition, channel spatial relationships, and repeated experiments.

Important note:

The project must distinguish theoretical channel count, expected channel count, and actual active channels used in statistics. Current pilot outputs mostly use 12 active channels.

## 3. Current Research Stage

Current stage:

```text
Pilot Feature System Prototype / pre-ML feature engineering prototype
```

Already completed or prototyped:

- raw data quality checks;
- frequency-domain PSD / bandpower features;
- high-frequency candidate bands, subbands, and peak windows;
- time-domain statistical features;
- ACF features;
- time-frequency stability features;
- channel structure / channel-correlation features;
- channel mask sensitivity analysis;
- pre-ML feature pipeline integration.

Not completed yet:

- complete experiment-variable acquisition;
- cross-batch validation;
- cross-water-volume validation;
- cross-conductivity validation;
- stable full 16-channel acquisition;
- formal machine-learning model;
- final target recognition conclusion;
- final physical-mechanism proof.

## 4. Existing Main Analysis Flow

### 4.1 Data Conversion And Basic Processing

The basic processing flow converts raw data into reusable intermediate files:

```text
TDMS -> time CSV + metadata -> FFT CSV -> downstream analysis outputs
```

The time CSV files preserve raw multi-channel voltage time series. They are used by time-domain, ACF, time-frequency stability, and channel-correlation feature pipelines.

The FFT CSV files preserve frequency-domain amplitude/phase information. They are used by frequency-domain candidate feature extraction and related validation.

### 4.2 PSD / Bandpower Frequency-Domain Features

PSD and bandpower features are used to study high-frequency energy changes, candidate frequency bands, subbands, and peak windows.

Current high-frequency candidate ranges include:

- `50-100 kHz`;
- `100-200 kHz`;
- subbands inside those broad ranges;
- peak windows around approximately 54 kHz, 138 kHz, and 178 kHz.

The formal file-level/channel-level candidate feature source is the v2 extraction output, where each feature is computed from FFT CSV files per file, channel, and frequency window.

### 4.3 Time-Domain Statistical Features

Time-domain features describe the original waveform amplitude, variation, distribution shape, drift, spikes, and local stability.

Feature groups include:

- amplitude/location;
- variation/noise strength;
- distribution shape;
- drift/trend;
- spike/outlier;
- local stability from rolling windows.

These features are useful as auxiliary evidence and QC information. Baseline/location-type features require caution.

### 4.4 ACF Features

ACF features describe temporal correlation structure and non-randomness.

They include:

- short-lag ACF values;
- fixed-window ACF integrals;
- decay/decorrelation lag features;
- peak/periodicity features;
- approximate near-lag diagnostics for high-frequency candidate windows;
- nonrandomness and long/short-lag energy summaries.

High-frequency near-lag ACF features are auxiliary diagnostics only. They should not be interpreted as proof of stable physical frequency peaks.

### 4.5 Time-Frequency Stability Features

Time-frequency stability features check whether PSD candidate bands or peak windows persist across time windows, or whether they are driven by short bursts.

The current method uses rolling FFT / bandpower from time CSV files, with default window settings recorded in the corresponding docs.

Feature types include:

- rolling bandpower statistics;
- peak value / peak prominence / peak frequency summaries;
- occupancy and burstiness indicators;
- background-relative detection-margin-like features;
- threshold occupancy ratios.

These features are auxiliary evidence for PSD candidate stability, not a replacement for PSD / bandpower as the main line.

### 4.6 Channel Correlation / Channel Structure Features

Channel structure features describe array-level behavior:

- channel-to-channel correlation;
- common-mode behavior;
- residual structure;
- PCA concentration;
- dominant-channel risk;
- channel contribution ratios.

They are used to evaluate whether a response is common-mode, single-channel-dominated, or potentially spatially meaningful.

These features are also important for channel QC.

### 4.7 Channel Mask Sensitivity

Channel mask sensitivity compares conclusions under several channel masks:

- all channels;
- exclude known bad channel condition;
- globally exclude channel9;
- globally exclude channel9 and channel5;
- current healthy-channel candidate mask.

This stage checks whether candidate features remain useful after removing known or suspected risky channels.

It does not permanently delete channels or define universal bad-channel rules.

### 4.8 ML Feature Pipeline Integration

The current project includes a pre-ML integration layer.

It organizes existing artifacts into three layers:

1. Feature computation;
2. Data quality and channel QC;
3. Feature validation and selection.

It can summarize or run missing artifacts, depending on options, but it does not train machine-learning models and does not make final recognition claims.

## 5. Current Pilot Findings

The following are candidate findings under the current pilot data only. They are not final scientific conclusions.

### 5.1 High-Frequency PSD / Bandpower Is The Current Main Candidate Line

In the current pilot data, the strongest candidate information appears in high-frequency PSD / bandpower features, especially around:

- `50-100 kHz`;
- `100-200 kHz`.

The PSD zoom analysis indicates that these broad bands are not simply uniform broadband lifts. They appear to include local narrow peaks or mixed local spectral structures.

### 5.2 Subbands And Peak Windows Changed After Channel-Mask Review

Finer subbands and peak windows were reviewed with channel-mask sensitivity.

Some high-frequency subbands remain useful after masking risky channels.

Some peak windows, including ranges such as `53.5-55 kHz` and `137-139.5 kHz`, show sensitivity to abnormal or suspect channels and therefore need downgrade or warning flags.

### 5.3 Time-Domain Features Are Auxiliary, Not The Main Line

Time-domain variation and distribution-shape features may provide auxiliary information.

However, features such as:

- mean;
- median;
- dc_offset;
- min;
- max;
- rms;

have baseline-risk and should not be used directly as primary recognition features without caution.

### 5.4 ACF Features Are Auxiliary Or QC Features

ACF features can help describe non-randomness, temporal correlation, and repeated structure.

High-frequency near-lag features should be treated only as sampling-lag diagnostics. They should not be directly interpreted as stable physical frequency evidence.

### 5.5 Time-Frequency Stability Features Are Informative But Numerous

Time-frequency stability features show strong information in the current pilot data, but the feature count is large and needs compression.

Background-relative TF features behave more like detection-margin indicators.

Burstiness, occupancy, and high-event-count features are better treated as stability or QC risk indicators unless supported by stable median behavior.

### 5.6 Channel Structure Shows channel9 Risk And channel5 Suspicion

Current pilot analysis treats channel9 as a clear bad channel, especially in 5m groups.

channel5 is treated as suspect or unusually sensitive and requires conservative comparison.

These are current pilot-data observations, not permanent channel rules.

### 5.7 High-Frequency Candidate Line Does Not Fully Disappear After channel9/channel5 Exclusion

After excluding channel9 and channel5 in sensitivity checks, the high-frequency candidate line does not fully disappear.

This suggests the current high-frequency candidates are not completely supported by bad channels alone.

However, some individual features are channel-dependent and should be downgraded or carried with warning flags.

## 6. Channel And QC Current Status

Current channel/QC status:

- channel9 is a clear bad-channel risk in the current pilot data, especially in 5m groups;
- channel5 is suspected to be abnormal, overly sensitive, or mixed with a large signal;
- channel9/channel5 must not be hard-coded as permanent bad channels for future experiments;
- future datasets must re-evaluate bad/suspect channels through channel QC and experiment records;
- QC features should mainly be used for sample filtering, risk marking, and channel-mask construction;
- QC features should not be directly used as primary recognition features.

Needed future metadata:

- channel_id;
- sensor_position;
- amplifier_channel;
- NI channel;
- known_bad_channel;
- suspect_channel;
- channel wiring notes;
- experiment record for abnormal channels.

## 7. Current Boundaries: What Not To Do Now

Do not do the following at the current stage:

- do not train or claim a final machine-learning model;
- do not freeze the final feature set;
- do not write the current frequency bands as final physical laws;
- do not hard-code channel9/channel5 as permanent bad channels;
- do not treat current AUC or separability as final recognition performance;
- do not keep adding unlimited new indicators without compression and validation;
- do not ignore metadata, experiment variables, or lack of repeated experiments;
- do not interpret high-frequency candidates as final proof of target physical mechanism;
- do not treat feature-level background contrast as synchronous time-domain subtraction.

## 8. Recommended Next Stage

The next stage should focus on experiments and workflow reuse, not on adding more algorithms.

### 8.1 Improve Experiment Metadata

Recommended metadata fields:

- distance;
- rpm / working condition;
- water volume;
- conductivity;
- temperature;
- experiment_id;
- repeat_id;
- channel_id;
- sensor_position;
- amplifier_channel;
- NI channel;
- known_bad_channel;
- suspect_channel;
- background_group;
- acquisition notes;
- channel wiring notes.

### 8.2 Design The Next Experiment Matrix

Recommended next experiment dimensions:

- water volume variation;
- conductivity variation;
- full 16-channel acquisition;
- repeated experiments;
- explicit background groups;
- channel QC before and after runs;
- consistent channel mapping records.

### 8.3 Reuse The Current Pre-ML Pipeline On New Data

Suggested workflow:

```text
new data
  -> feature computation
  -> QC / channel mask
  -> feature validation
  -> candidate ML feature matrix
```

The current pipeline should be reused to test whether current candidate features remain stable under new data conditions.

### 8.4 Cross-Batch And Cross-Variable Stability

Future validation should check whether the current candidate families remain useful across:

- experiment batches;
- water volume;
- conductivity;
- repeat_id;
- channel masks;
- full 16-channel acquisition;
- background groups.

### 8.5 Enter Pilot ML Only After Data Coverage Improves

Pilot ML should wait until the experiment variables and repeated datasets are sufficient.

Before that, use current outputs as pre-ML candidate feature preparation and screening artifacts only.

## 9. Key Documents And Output Index

### 9.1 Important Docs

- `docs/CANDIDATE_FEATURE_ANALYSIS.md`  
  Consolidated high-frequency candidate feature chain: PSD zoom, v1 aggregated validation, v2 file/channel feature extraction, and separability v1 gate.

- `docs/TIME_DOMAIN_FEATURE_EXTRACTION_V1.md`  
  Time-domain feature extraction scope, feature groups, outputs, and QC notes.

- `docs/ACF_FEATURE_ANALYSIS_V1.md`  
  ACF feature extraction and role assignment, including near-lag limitations.

- `docs/TIME_FREQUENCY_STABILITY_FEATURE_ANALYSIS_V1.md`  
  Rolling time-frequency stability features, background-relative TF features, burstiness/stability roles, and limitations.

- `docs/CHANNEL_CORRELATION_FEATURE_ANALYSIS_V1.md`  
  Channel-correlation, common-mode, PCA, residual, and dominant-channel risk analysis.

- `docs/CHANNEL_MASK_SENSITIVITY_V1.md`  
  Channel mask definitions and feature robustness under channel9/channel5 exclusions.

- `docs/TIME_FREQUENCY_FEATURE_COMPARISON_V1.md`  
  Comparison of time-domain and frequency-domain feature families, feature roles, and recommended feature sets.

- `docs/ML_FEATURE_PIPELINE_INTEGRATION_V1.md`  
  Pre-ML integration layer describing feature computation, QC/channel structure, and feature validation/selection.

- `docs/METRIC_REGISTRY.md`  
  Metric definitions, formulas, layers, implementation locations, and keep/deprecate notes.

- `docs/STRUCTURE_OPTIMIZATION_NEXT_STEPS.md`  
  Structural optimization notes. Useful for future maintenance, but not a scientific result report.

- `docs/PERFORMANCE_CURRENT_STRUCTURE.md`  
  Current performance-side structure summary. Not a scientific result report.

### 9.2 Important analysis_out Directories

- `analysis_out/feature_extraction_v2`  
  Formal frequency candidate feature extraction v2 outputs.

- `analysis_out/feature_separability_v1`  
  Frequency candidate feature separability, redundancy, pilot gate, and readiness outputs.

- `analysis_out/time_domain_features_v1`  
  Time-domain file/channel feature dataset and stability summary.

- `analysis_out/acf_features_v1`  
  ACF feature dataset, stability/separability outputs, and role assignments.

- `analysis_out/time_frequency_stability_features_v1`  
  Rolling time-frequency stability feature outputs and summaries.

- `analysis_out/channel_correlation_features_v1`  
  Channel-correlation, common-mode, PCA, residual, and channel dominance outputs.

- `analysis_out/time_frequency_feature_comparison_v1`  
  Time-frequency feature comparison, redundancy, role assignment, and recommended feature sets.

- `analysis_out/channel_mask_sensitivity_v1`  
  Channel mask robustness, channel dependency, and mask-specific feature outputs.

- `analysis_out/ml_feature_pipeline_integration_v1`  
  Pre-ML integration manifests and orchestration artifacts.

- `analysis_out/background_contrast_2m_complete`  
  Background contrast outputs for the current available checked run. Need later confirmation whether this remains the preferred formal background-contrast directory for future runs.

- `analysis_out/candidate_feature_validation_v1`  
  Aggregated PSD zoom / background-contrast candidate validation v1 outputs. Useful for interpretation, not the formal file-level feature source.

## 10. Open Items Needing Later Confirmation

The following items should be confirmed before treating the workflow as final:

- whether future experiments will use the same channel naming convention;
- whether 12 active channels remain expected or full 16-channel operation becomes stable;
- whether channel9/channel5 issues repeat in future batches;
- exact metadata schema for water volume, conductivity, temperature, repeat_id, and experiment_id;
- whether `analysis_out/background_contrast_2m_complete` is the long-term reference output name or only a current package/output snapshot;
- whether frequency-axis-risk files should be recomputed, excluded, or retained with strict-mode flags in all future analyses;
- how channel spatial positions map to physical sensor locations;
- whether candidate high-frequency bands remain stable across repeated and variable-controlled experiments.

## 11. Short Continuation Summary

This project is currently a pre-ML signal feature engineering prototype for underwater multi-channel voltage data.

The main candidate line is high-frequency PSD / bandpower around `50-100 kHz` and `100-200 kHz`, refined into subbands and peak windows. Time-domain, ACF, time-frequency stability, and channel-structure features have been added as auxiliary/QC feature families.

Current pilot results are promising but not final. The next important work is not to add more algorithms, but to improve experiment metadata, collect controlled repeated datasets, rerun the current feature pipeline, and test whether the candidate feature families remain stable across new variables.
