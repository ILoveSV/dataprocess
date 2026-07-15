# Time-Domain Feature Extraction v1

## Purpose

PSD/bandpower features describe frequency-domain energy. Time-domain statistics add amplitude, variation, spike, drift, distribution-shape, and local-stability descriptors from raw voltage time series.

## Inputs

- Time CSV root: `D:\Lab\process\26.5.12\time`
- Groups read: 2m0hz, 2m30hz, 2m50hz, 3m0hz, 3m30hz, 3m50hz, 5m0hz, 5m30hz, 5m50hz

## Outputs

- `analysis_out\time_domain_features_v1\time_domain_feature_dataset_v1.csv`
- `analysis_out\time_domain_features_v1\time_domain_feature_stability_summary_v1.csv`
- `analysis_out\time_domain_features_v1\time_domain_feature_schema.json`
- `analysis_out\time_domain_features_v1\time_domain_feature_run_config.json`
- `analysis_out\time_domain_features_v1\time_domain_feature_input_audit.json`

## Feature Groups

- Amplitude/location: mean, median, dc_offset, min, max, peak_to_peak.
- Variation/noise strength: std, rms, ac_rms, robust_sigma, mad, iqr, q05_q95_range, q10_q90_range.
- Distribution shape: skewness, Fisher kurtosis, crest_factor, impulse_factor, shape_factor, tail_ratio.
- Drift/trend: linear_slope, drift_span, drift_ratio_robust, start_end_delta, start_end_delta_ratio.
- Spike/outlier: spike_count_3sigma, spike_rate_3sigma, spike_count_5sigma, max_abs_z_robust, clipping_flag.
- Local stability: rolling features using non-overlapping 0.2s windows.

## QC

- QC flag counts: {'OK': 155520}
- Files with audit warnings: 0
- Abnormal files/channels are marked, not deleted.

## Separability Readiness

- The schema shares keys with frequency-domain `candidate_feature_dataset_v2.csv`: group, distance, rpm, file_id, channel.
- These features can enter later separability analysis after optional QC filtering.

## Scope Guard

- No plots were generated.
- No machine learning was run.
- No PSD/background contrast results were modified.
- No FFT workflow was rerun.
- No abnormal channel or file was automatically removed.
- No time-domain feature is interpreted here as a final physical mechanism.
