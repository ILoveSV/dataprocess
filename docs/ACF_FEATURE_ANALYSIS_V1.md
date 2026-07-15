# ACF Feature Analysis v1

## Purpose

PSD describes frequency energy, time-domain statistics describe amplitude/distribution, and ACF describes temporal correlation structure and non-randomness.

## Inputs

- Time CSV root: `D:\Lab\process\26.5.12\time`
- Groups read: 2m0hz, 2m30hz, 2m50hz, 3m0hz, 3m30hz, 3m50hz, 5m0hz, 5m30hz, 5m50hz

## ACF calculation

- Preprocessing: `ac_centered`.
- Max lag: `0.05` seconds.
- ACF is computed from mean-centered signal using FFT-based autocorrelation.
- ACF is normalized so `acf[0] = 1`.
- Default sampling rate is read from each time CSV, approximately 400 kHz.

## Extracted ACF features

- Short-lag ACF values.
- Absolute ACF integrals across fixed time windows.
- Decay/decorrelation lag and time features.
- Peak/periodicity features.
- Approximate nearest-sample lag features for 54k/138k/178k.
- Nonrandomness, short-lag energy, long-lag energy, and long/short ratio.

## High-frequency lag limitation

- 54k/138k/178k periods correspond to only a few samples at ~400 kHz.
- `acf_near_54k`, `acf_near_138k`, and `acf_near_178k` features are auxiliary diagnostics only, not proof of stable physical frequency peaks.

## Separability

- `acf_short_lag_energy` `Task B 30Hz vs 50Hz`: AUC=1, effect=-3.06
- `acf_near_138k_value` `Task A active vs 0Hz`: AUC=1, effect=4.7
- `acf_lag50` `Task A active vs 0Hz`: AUC=1, effect=2.26
- `acf_lag20` `Task A active vs 0Hz`: AUC=1, effect=2.5
- `acf_lag100` `Task A active vs 0Hz`: AUC=1, effect=3.04
- `acf_lag10` `Task A active vs 0Hz`: AUC=1, effect=2.83
- `acf_lag50` `Task B 30Hz vs 50Hz`: AUC=1, effect=3.32
- `acf_abs_integral_0p5_1ms` `Task B 30Hz vs 50Hz`: AUC=1, effect=-3.12

## ACF vs existing PSD/time features

- `Task A active vs 0Hz`: best_acf_auc=1, additional_value=high; best_acf=acf_abs_integral_0_0p1ms
- `Task B 30Hz vs 50Hz`: best_acf_auc=1, additional_value=high; best_acf=acf_abs_integral_0_0p1ms
- `Task C distance`: best_acf_auc=0.833, additional_value=high; best_acf=acf_abs_integral_0_0p1ms
- `Task D rpm 3-class`: best_acf_auc=0.685, additional_value=low; best_acf=acf_lag1

## Roles

- Role counts: {'auxiliary_candidate': 23, 'reject': 12, 'qc_only': 4}
- ACF auxiliary: ['acf_abs_integral_0_0p1ms', 'acf_abs_integral_0p1_0p5ms', 'acf_abs_integral_0p5_1ms', 'acf_abs_integral_1_5ms', 'acf_abs_integral_5_20ms', 'acf_first_peak_value', 'acf_lag1', 'acf_lag10', 'acf_lag100', 'acf_lag2', 'acf_lag20', 'acf_lag5', 'acf_lag50', 'acf_max_peak_lag', 'acf_max_peak_time_sec', 'acf_max_peak_value', 'acf_near_138k_value', 'acf_near_178k_value', 'acf_near_54k_value', 'acf_peak_count_above_0p1', 'acf_peak_count_above_0p2', 'acf_peak_spacing_cv', 'acf_periodicity_score']
- ACF QC features: ['acf_abs_integral_20_50ms', 'acf_long_lag_energy', 'acf_nonrandomness_score', 'acf_short_lag_energy']
- ACF rejected: ['acf_efold_lag', 'acf_efold_time_sec', 'acf_first_below_0p1_lag', 'acf_first_below_0p1_time_sec', 'acf_first_peak_lag', 'acf_first_peak_time_sec', 'acf_first_zero_cross_lag', 'acf_first_zero_cross_time_sec', 'acf_long_short_ratio', 'acf_near_138k_lag', 'acf_near_178k_lag', 'acf_near_54k_lag']

## Scope guard

- No machine learning was run.
- No large plot set was generated.
- No FFT or background contrast outputs were modified.
- ACF high AUC is not interpreted as a physical mechanism.
