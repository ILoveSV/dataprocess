# Zero-State Background Consistency v1

## Purpose

Previous analyses mainly used same-distance active vs 0Hz background subtraction, such as 2m30Hz vs 2m0Hz. This analysis checks whether 2m0Hz, 3m0Hz, and 5m0Hz are mutually consistent zero-state backgrounds.

## Groups Analyzed

- 2m0hz
- 3m0hz
- 5m0hz

No 30Hz or 50Hz active groups are included in the main analysis.

## Inputs

- Mask matrix: `analysis_out\channel_mask_sensitivity_v1\masked_feature_matrix_file_agg_v1.csv`
- Channel-structure reference: `analysis_out\channel_correlation_features_v1\channel_correlation_feature_matrix_file_v1.csv`

## Mask Strategy

- `mask_all`: historical all-channel reference.
- `mask_no_ch9_global`: current main QC convention for comparison.
- `mask_no_ch9_ch5_global`: conservative control.
- Channel-structure features are included under `mask_all` only because they are already file-level array features; masked channel-structure values were not fabricated.

## Overall Background Consistency

- Under `mask_no_ch9_global`, consistency counts are: {'low': 184, 'inconsistent': 147, 'high': 132, 'medium': 62}
- A high AUC here is a warning, not a success: it means 0Hz backgrounds can be separated by distance.

## Domain-Level Differences

- `tf`: inconsistent=90, low=163, medium=60, high=122
- `acf`: inconsistent=22, low=13, medium=2, high=2
- `time`: inconsistent=20, low=8, medium=0, high=8
- `frequency`: inconsistent=15, low=0, medium=0, high=0

## Channel9 / Channel5 Effect

- Features whose 0Hz mismatch was reduced by global channel9 masking: 22
- Features whose mismatch was further reduced by channel5 masking: 12
- If mismatch remains after both masks, it is treated as experiment-condition or batch/background risk rather than channel-quality-only risk.

## High-Risk Features For Distance Interpretation

acf__acf_abs_integral_0_0p1ms, acf__acf_abs_integral_0p1_0p5ms, acf__acf_abs_integral_0p5_1ms, acf__acf_abs_integral_1_5ms, acf__acf_abs_integral_5_20ms, acf__acf_efold_lag, acf__acf_efold_time_sec, acf__acf_first_below_0p1_lag, acf__acf_first_below_0p1_time_sec, acf__acf_first_peak_lag, acf__acf_first_peak_time_sec, acf__acf_first_peak_value, acf__acf_first_zero_cross_lag, acf__acf_first_zero_cross_time_sec, acf__acf_lag1, acf__acf_lag10, acf__acf_lag100, acf__acf_lag2, acf__acf_lag20, acf__acf_lag5

## Impact On Previous Candidate Features

- Recommended action counts: {'downgrade_for_distance_task': 172, 'keep': 126, 'reject_for_distance_task': 114, 'keep_with_same_distance_background_only': 58}
- Same-distance active-vs-background interpretation remains safer than direct cross-distance comparison when 0Hz backgrounds differ.
- Distance classification can learn zero-state background differences if these risks are not controlled.

## ML Implications

- If 0Hz backgrounds are separable by distance, distance classifiers may learn background/batch structure rather than active response.
- Future datasets should record richer metadata and support cross-batch/cross-variable validation.
- Features with high zero-state background risk should be restricted to same-distance background subtraction or downgraded for distance tasks.

## Scope Guard

- No machine learning was run.
- No new features were extracted.
- No TDMS/FFT/background contrast pipeline was rerun.
- No existing formulas were modified.
- Existing conclusions are not directly overturned; this report marks zero-state background consistency risk.
