# Time + Frequency Feature Comparison v1

## Inputs

- Frequency feature table: `analysis_out/feature_extraction_v2/candidate_feature_dataset_v2.csv`
- Frequency stability table: `analysis_out/feature_extraction_v2/feature_stability_summary_v2.csv`
- Time feature table: `analysis_out/time_domain_features_v1/time_domain_feature_dataset_v1.csv`
- Time stability table: `analysis_out/time_domain_features_v1/time_domain_feature_stability_summary_v1.csv`

## Scope

- No machine learning was run.
- No new features were extracted.
- No TDMS/FFT/background contrast pipeline was rerun.
- No plot is used as a substitute for CSV metrics.

## Feature counts and grain

- Frequency features: 15
- Time features: 36
- Main analysis grain: file_agg, because it reduces channel-replication leakage and matches later pilot ML table construction.
- File-channel matrix rows: 4212
- File-aggregated matrix rows: 351

## Key alignment audit

- Common group/file/channel keys after normalized file_id alignment: 4212
- Frequency-only keys: 0
- Time-only keys: 108
- Note: Frequency file_id uses FFT_ prefix; normalized_file_key removes only the FFT_ prefix and keeps .csv suffix for alignment.

## Time-domain usefulness

- file_agg time usefulness counts: {'high': 4}
- Time-domain features do show separability in several tasks, but baseline/location features require caution.
- Frequency features remain the main line because they map directly to the established high-frequency candidate bands and subbands.
- Time-domain non-baseline distribution/variation features are useful as auxiliary checks and possible complementary features.

## Roles

- Frequency primary candidates: 15
- Time auxiliary candidates: 20
- Time QC-only features: 16

## Recommended feature sets

- frequency_core: ['freq__subband_50_60k', 'freq__subband_60_70k', 'freq__subband_70_80k', 'freq__subband_80_90k', 'freq__subband_90_100k', 'freq__subband_140_160k', 'freq__subband_180_200k', 'freq__peakwin_53p5_55k', 'freq__peakwin_137_139p5k', 'freq__peakwin_177_179k']
- time_auxiliary: ['time__peak_to_peak', 'time__std', 'time__ac_rms', 'time__robust_sigma', 'time__mad', 'time__iqr', 'time__q05_q95_range', 'time__q10_q90_range', 'time__skewness', 'time__kurtosis', 'time__crest_factor', 'time__impulse_factor', 'time__shape_factor', 'time__tail_ratio']
- combined_nonredundant: ['freq__subband_50_60k', 'freq__subband_60_70k', 'freq__subband_70_80k', 'freq__subband_80_90k', 'freq__subband_90_100k', 'freq__subband_140_160k', 'freq__subband_180_200k', 'freq__peakwin_53p5_55k', 'freq__peakwin_137_139p5k', 'freq__peakwin_177_179k', 'time__peak_to_peak', 'time__std', 'time__ac_rms', 'time__robust_sigma', 'time__mad', 'time__iqr', 'time__q05_q95_range', 'time__q10_q90_range', 'time__skewness', 'time__kurtosis', 'time__crest_factor', 'time__impulse_factor', 'time__shape_factor', 'time__tail_ratio']
- qc_features: ['time__linear_slope', 'time__drift_span', 'time__drift_ratio_robust', 'time__start_end_delta', 'time__start_end_delta_ratio', 'time__spike_count_3sigma', 'time__spike_rate_3sigma', 'time__spike_count_5sigma', 'time__max_abs_z_robust', 'time__clipping_flag', 'time__rolling_rms_median', 'time__rolling_rms_iqr', 'time__rolling_rms_cv', 'time__rolling_mean_range', 'time__stable_window_ratio', 'time__longest_stable_duration']
- excluded_baseline_risk: ['time__mean', 'time__median', 'time__dc_offset', 'time__min', 'time__max', 'time__rms']

## Redundancy

- Highly redundant pairs |corr| > 0.9: 75
- See `combined_feature_redundancy_summary.csv` for frequency-frequency, time-time, and time-frequency pairs.

## Pilot ML recommendation

- Use `frequency_core` as the baseline feature set.
- Add `time_auxiliary` for a combined nonredundant candidate set.
- Keep `qc_features` out of recognition features; use them for filtering or audit.
- Keep baseline-risk features out of primary recognition interpretation even when AUC is high.
