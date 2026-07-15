# Channel Mask Sensitivity v1

## Purpose

Channel9 is treated as a confirmed bad/suspect channel in 5m groups, and channel5 is treated as a suspect sensitive channel. This analysis re-aggregates existing file_id x channel feature tables under several channel masks to check whether conclusions depend on those channels.

## Inputs

- frequency: `analysis_out\feature_extraction_v2\candidate_feature_dataset_v2.csv` rows=63180 features=15
- time: `analysis_out\time_domain_features_v1\time_domain_feature_dataset_v1.csv` rows=155520 features=36
- acf: `analysis_out\acf_features_v1\acf_feature_dataset_v1.csv` rows=168480 features=39
- tf: `analysis_out\time_frequency_stability_features_v1\tf_stability_feature_dataset_v1.csv` rows=1879200 features=435

## Masks

- `mask_all`: original all-channel reference; excludes global=[], by_distance={}
- `mask_hard_bad_by_group`: simulate removing only the known bad channel where it occurred; excludes global=[], by_distance={'5m': ['channel9']}
- `mask_no_ch9_global`: fair modeling-oriented mask that removes channel9 everywhere; excludes global=['channel9'], by_distance={}
- `mask_no_ch9_ch5_global`: conservative comparison excluding confirmed channel9 risk and suspected channel5 risk; excludes global=['channel9', 'channel5'], by_distance={}
- `mask_healthy_candidate`: default healthy-channel candidate mask; currently equivalent to mask_no_ch9_ch5_global; excludes global=['channel9', 'channel5'], by_distance={}

## Outputs and Coverage

- Combined input rows: 2266380
- Masked file-level matrix rows: 1800
- Separability rows: 26250
- Robustness status counts: {'keep_with_warning': 284, 'robust_keep': 186, 'downgrade': 55}

## Channel9 / Channel5 Dependence

- Features with channel9 dependency flag: 28
- Features with channel5 dependency flag: 26
- `mask_no_ch9_global` is recommended as the main follow-up analysis mask because it avoids distance-specific channel removal.
- `mask_no_ch9_ch5_global` should be kept as the conservative comparison mask.

## Frequency / PSD Candidate Robustness

freq__subband_140_160k, freq__subband_120_140k, freq__peakwin_177_179k, freq__subband_80_90k, freq__subband_180_200k, freq__subband_90_100k, freq__subband_50_60k, freq__subband_160_180k, freq__band_100_200k, freq__band_50_100k

## TF Stability Candidate Robustness

tf__subband_180_200k__tf_peak_freq_median, tf__subband_140_160k__tf_peak_freq_median, tf__subband_140_160k__tf_bandpower_p90, tf__subband_140_160k__tf_bandpower_median, tf__subband_140_160k__tf_bandpower_mean, tf__peakwin_53p5_55k__tf_peak_freq_median, tf__peakwin_137_139p5k__tf_peak_freq_median, tf__band_100_200k__tf_bandpower_median, tf__subband_90_100k__tf_bandpower_p90, tf__subband_90_100k__tf_bandpower_median, tf__subband_90_100k__tf_bandpower_mean, tf__band_100_200k__tf_background_threshold_occupancy_ratio, tf__band_100_200k__tf_background_relative_median_gain, tf__band_100_200k__tf_background_detection_margin, tf__subband_60_70k__tf_background_threshold_occupancy_ratio, tf__subband_60_70k__tf_background_relative_median_gain, tf__subband_60_70k__tf_background_detection_margin, tf__subband_50_60k__tf_bandpower_p10, tf__subband_50_60k__tf_bandpower_mean, tf__subband_180_200k__tf_background_relative_median_gain

## Downgrade / Reject Examples

freq__subband_60_70k, tf__subband_80_90k__tf_bandpower_p10, tf__subband_80_90k__tf_bandpower_median, tf__subband_80_90k__tf_bandpower_mean, freq__subband_70_80k, tf__subband_60_70k__tf_bandpower_p90, tf__subband_60_70k__tf_bandpower_p10, tf__subband_60_70k__tf_bandpower_median, tf__subband_60_70k__tf_bandpower_mean, tf__peakwin_53p5_55k__tf_peak_value_median, tf__peakwin_53p5_55k__tf_peak_prominence_median, tf__peakwin_53p5_55k__tf_bandpower_p90, tf__peakwin_53p5_55k__tf_bandpower_p10, tf__peakwin_53p5_55k__tf_bandpower_median, tf__peakwin_53p5_55k__tf_bandpower_mean, freq__subband_100_120k, freq__peakwin_53p5_55k, tf__subband_90_100k__tf_peak_freq_median, tf__subband_80_90k__tf_bandpower_p90, acf__acf_lag1

## Interpretation

Features that remain strong under `mask_no_ch9_global` are not dependent on channel9. Features that remain strong under `mask_no_ch9_ch5_global` are also not dependent on channel5. Features that collapse after channel removal are marked as dependency or unstable risk, not interpreted as physical target response.

## Scope Guard

- No machine learning was run.
- No new signal features were extracted.
- No TDMS/FFT/background contrast processing was rerun.
- No original data or old outputs were deleted.
- No additional bad channels were inferred automatically.
- Group-specific masks are treated as QC sensitivity checks, not final modeling conclusions.
