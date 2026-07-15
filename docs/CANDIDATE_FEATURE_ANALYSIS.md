# Candidate Feature Analysis

This document consolidates the current high-frequency candidate feature analysis chain.

Merged source documents:

- `PSD_ZOOM_ANALYSIS_RESULT.md`
- `CANDIDATE_FEATURE_VALIDATION_V1.md`
- `CANDIDATE_FEATURE_EXTRACTION_V2.md`
- `FEATURE_SEPARABILITY_V1.md`

## 1. PSD zoom findings

PSD zoom was added after the broad background contrast stage to inspect the two main high-frequency candidate ranges:

- `50-100 kHz`
- `100-200 kHz`

The PSD zoom stage reused `background_psd_diff_curves.csv` from the existing background contrast output. It did not change the background contrast formula.

The reused definitions are:

- PSD gain: `active_logpsd_median - background_logpsd_median`
- Pump net PSD: `(50Hz - 0Hz) - (30Hz - 0Hz)`
- Background group: same-distance `0Hz`
- Active groups: same-distance `30Hz` and `50Hz`

Added outputs included:

- `psd_zoom_summary.csv`
- `psd_zoom_feature_summary.csv`
- `psd_zoom_input_audit.json`
- `psd_zoom_run_config.json`
- raw PSD overlay plots
- PSD gain vs background plots
- pump net PSD plots

Main observation:

The high-frequency response is not a simple smooth broadband lift across the whole `50-100 kHz` or `100-200 kHz` range. PSD zoom indicates local narrow peaks or mixed local spectral structures inside those broad ranges.

Useful zoom metrics:

- `peak_prominence_like_value = max_gain_value - median_gain_value`
- `peak_to_band_ratio = abs(max_gain_value) / max(abs(median_gain_value), 1e-9)`
- `broadband_lift_score = fraction of valid frequency bins with value > 0`
- `integrated_gain` / `band_integral = trapezoid integral over frequency`

Input audit status:

- Audit status: `WARNING`
- FFT frequency-axis warning count: 9
- Skipped items: 0

The 9 frequency-axis warning files remain an important risk for frequency-point-level and peak-level analysis.

## 2. Candidate validation v1

Candidate Feature Validation v1 moved from broad high-frequency bands into local peak and subband candidate validation.

Inputs:

- Background contrast output: `D:\Lab\results\26.5.12\background_contrast_v1`
- PSD zoom output: `D:\Lab\results\26.5.12\background_contrast_v1\psd_zoom`
- Output directory: `analysis_out\candidate_feature_validation_v1`

Scope guard:

- Did not rerun full background contrast.
- Did not change the background contrast formula.
- Did not run machine learning.
- Did not build a final feature dataset.
- Did not perform time-domain synchronous subtraction.

Candidate peaks checked:

- `peak_54k`
- `peak_138k`
- `peak_178k`

Subbands checked:

- `50_60k`
- `60_70k`
- `70_80k`
- `80_90k`
- `90_100k`
- `100_120k`
- `120_140k`
- `140_160k`
- `160_180k`
- `180_200k`

Validation rules:

- `stable_peak_flag=True` requires peak evidence in at least 2 distances and at least 2 non-raw comparison types.
- Peak evidence requires `max_value >= 1 dB` and `peak_prominence_like_value >= 1 dB` inside the candidate window.
- `peak-dominated` is marked when `peak_to_band_ratio >= 5` while median gain is low.
- Broad bands are kept as medium candidates when support is high but frequency-axis/file-level/channel risks remain.
- `ml_ready_flag=True` requires support_channel_count >= 8, no frequency-axis risk, no channel dominance risk, and peak stability where applicable.

Gate summary from v1:

- `band_50_100k`: priority=medium, ml_ready=False
- `band_100_200k`: priority=medium, ml_ready=False
- `peak_54k`: priority=reject, ml_ready=False
- `peak_138k`: priority=reject, ml_ready=False
- `peak_178k`: priority=reject, ml_ready=False

Important limitation:

v1 uses already aggregated group/channel median PSD curves from background contrast and PSD zoom. It cannot safely evaluate true file-level stability, because the current v1 inputs do not preserve per-file PSD curves before aggregation.

Therefore v1 should be treated as:

```text
aggregated PSD zoom screening and interpretation
```

It should not be treated as the formal source for file-level feature modeling.

## 3. Candidate feature extraction v2

Candidate Feature Extraction v2 is the formal file-level/channel-level candidate feature extraction stage.

Inputs:

- FFT root: `D:\Lab\process\26.5.12\frequency`
- Background output: `D:\Lab\results\26.5.12\background_contrast_v1`
- FFT audit: `D:\Lab\results\26.5.12\background_contrast_v1\fft_group_input_audit.csv`

Scope:

- Generated file-level/channel-level candidate features from FFT CSV files.
- Did not run machine learning.
- Did not modify background contrast formulas.
- Did not rerun TDMS conversion or FFT export.

Feature definition:

```text
10*log10(sum(amplitude^2 * df_hz) + EPS)
```

This is computed per FFT file, channel, and candidate frequency window.

This is not a reused group-median PSD zoom value. Rows preserve `file_id` and `channel`.

Modes:

- all-data mode file count: 360
- strict mode file count: 351
- strict mode excludes the 9 frequency-axis-risk files

Extracted features:

- `band_50_100k`
- `band_100_200k`
- `subband_50_60k`
- `subband_60_70k`
- `subband_70_80k`
- `subband_80_90k`
- `subband_90_100k`
- `subband_100_120k`
- `subband_120_140k`
- `subband_140_160k`
- `subband_160_180k`
- `subband_180_200k`
- `peakwin_53p5_55k`
- `peakwin_137_139p5k`
- `peakwin_177_179k`

Stability definition:

- `stable_file_ratio`: fraction of file values inside `[Q1 - 1.5*IQR, Q3 + 1.5*IQR]`
- `outlier_file_count`: number of files outside that interval

All-data vs strict-mode:

- Rows with median shift greater than `0.5 dB` after strict exclusion: 2
- See `all_vs_strict_feature_delta_v2.csv` for per group/feature/channel deltas.

ML readiness note:

This output is suitable as a candidate feature table input for later validation or ML dataset construction. Because frequency-axis-risk files exist, downstream ML should use strict mode or preserve `qc_flag` / `analysis_mode` as filtering metadata.

No feature is promoted here as a physical mechanism.

## 4. Feature separability v1 gate

Feature Separability v1 uses Feature Extraction v2 outputs only.

Scope:

- Used Feature Extraction v2 outputs.
- Did not extract new features.
- Did not rerun TDMS/FFT.
- Did not modify background contrast.
- Did not train final ML models.
- Pilot models are pre-ML gates using GroupKFold by `file_id` to reduce leakage.

Evaluated tasks:

- Active vs 0Hz
- 30Hz vs 50Hz
- 2m/3m/5m distance
- 0Hz/30Hz/50Hz rpm three-class

Evaluated outputs:

- single-feature AUC or macro AUC
- robust effect size
- distribution overlap
- feature correlation / redundancy
- pilot baseline model results
- channel9 sensitivity
- strict vs all-data separability delta
- ML readiness gate summary

Current separability answer:

- Medium/high ML-ready candidates or feature sets: 16
- Current decision: can enter pilot ML feature table construction with strict-mode filtering and risk flags

Important interpretation boundary:

The separability stage is a gate, not a final identification result.

Perfect or near-perfect pilot scores should not be interpreted as final detection capability until the remaining risks are resolved.

## 5. Current risks

### Frequency-axis risk

There are 9 FFT files with frequency-axis warnings. These affect PSD zoom, peak-level comparison, and any frequency-point-level conclusion.

Strict-mode v2 excludes them. Future modeling should prefer strict-mode inputs.

### v1 aggregation limitation

Candidate Validation v1 cannot evaluate true file-level stability because it uses already aggregated PSD zoom/background contrast curves.

v2 is the formal file-level/channel-level feature source.

### Peak feature risk

Peak-related candidates remain lower confidence than bandpower/subband features unless their stability is confirmed across files, channels, distances, and strict-mode frequency axes.

### Channel dominance risk

channel9 appears in sensitivity checks. It is not automatically removed. It should be treated as a review condition:

- possible bad channel
- possible sensitive channel
- possible common-mode/system response
- possible spatially meaningful channel

### Physical mechanism risk

Current features show distance/rpm-related spectral differences. They do not yet prove that the high-frequency response comes from the underwater target electric field itself.

### ML overinterpretation risk

Feature Separability v1 includes pilot baseline models, but these are pre-ML gates. They are not final production models or final scientific claims.

## 6. Recommended next step

Recommended workflow boundary:

```text
PSD zoom = local spectral structure inspection
Candidate validation v1 = aggregated curve screening and interpretation
Candidate extraction v2 = formal file x channel candidate feature table
Feature separability v1 = pre-ML gate and risk screen
```

Next steps:

1. Use v2 strict-mode features as the formal source for downstream feature tables.
2. Keep v1 as interpretive support, not as the file-level validation source.
3. Preserve `analysis_mode`, `qc_flag`, `file_id`, `channel`, `distance`, and `rpm` in downstream matrices.
4. Resolve or consistently exclude the 9 frequency-axis-risk files for strict analyses.
5. Continue channel9 review without automatic deletion.
6. Add detection-margin / empirical FPR / empirical TPR analysis before final ML claims.
7. Keep pilot ML results labeled as gate-level evidence only.
