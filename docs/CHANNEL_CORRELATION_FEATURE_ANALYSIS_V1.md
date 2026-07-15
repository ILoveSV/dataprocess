# Channel Correlation Feature Analysis v1

## Purpose

PSD/time/ACF features are mostly single-channel. Channel-correlation features describe array-level synchrony, common-mode behavior, residual structure, PCA concentration, and single-channel dominance risk.

## Inputs

- Time CSV root: `D:/Lab/process/26.5.12/time`
- Groups read: 2m0hz, 2m30hz, 2m50hz, 3m0hz, 3m30hz, 3m50hz, 5m0hz, 5m30hz, 5m50hz

## Calculation

- Each file is processed independently as a time_sample x channel matrix.
- Channels are de-meaned and z-scored before Pearson correlation.
- Spearman correlation is also exported as a robust control.
- Common mode is the per-sample mean across channels after de-meaning.
- PCA features are computed from the channel correlation matrix eigenvalues.

## Outputs and coverage

- Channel-pair rows: 23760
- File-level feature rows: 11880
- Groups: 9, files: 360

## Separability
- `channel_acrms_spread` `Task A active vs 0Hz`: AUC=1, effect=-2.65
- `channel_feature_cv_acrms` `Task A active vs 0Hz`: AUC=1, effect=-2.81
- `residual_rms_mean` `Task A active vs 0Hz`: AUC=1, effect=-2.44
- `channel_acrms_spread` `Task B 30Hz vs 50Hz`: AUC=1, effect=-3.18
- `channel_feature_cv_acrms` `Task B 30Hz vs 50Hz`: AUC=1, effect=-2.53
- `channel_mean_spread` `Task A active vs 0Hz`: AUC=1, effect=3.04
- `channel_rank_entropy_acrms` `Task B 30Hz vs 50Hz`: AUC=1, effect=2.42
- `common_mode_rms` `Task B 30Hz vs 50Hz`: AUC=1, effect=-3.65

## Comparison with existing PSD/time/ACF
- `Task A active vs 0Hz`: best_channel_corr_auc=1, value=high; feature=channel_acrms_spread
- `Task B 30Hz vs 50Hz`: best_channel_corr_auc=1, value=high; feature=channel_acrms_spread
- `Task C distance`: best_channel_corr_auc=0.833, value=high; feature=channel9_contribution_ratio
- `Task D rpm 3-class`: best_channel_corr_auc=0.619, value=low; feature=channel_rank_entropy_acrms

## Common-mode and dominance risks

- PCA common-mode-like flags across files: 0
- Dominant-channel risk flags across files: 360
- channel9 contribution ratio range: 0.0261-1
- High channel9 contribution is a needs-check flag, not a bad-channel decision.

## Roles

- Role counts: {'auxiliary_candidate': 16, 'qc_only': 13, 'reject': 4}
- Auxiliary: ['channel_acrms_spread', 'channel_feature_cv_acrms', 'channel_mean_spread', 'channel_rank_entropy_acrms', 'corr_abs_mean', 'corr_abs_median', 'corr_iqr', 'corr_max', 'corr_mean', 'corr_median', 'corr_min', 'corr_range', 'corr_std', 'pca_first_two_ratio', 'residual_rms_mean', 'residual_rms_median']
- QC: ['channel9_contribution_ratio', 'channel9_rank', 'common_mode_fraction', 'common_mode_rms', 'common_to_residual_ratio', 'dominant_channel_id', 'dominant_channel_ratio_acrms', 'dominant_channel_risk_flag', 'max_channel_contribution_ratio', 'pca_common_mode_like_flag', 'pca_first_component_ratio', 'pca_n_components_90', 'pca_spectral_entropy']
- Rejected: ['corr_pair_ratio_gt_0p5', 'corr_pair_ratio_gt_0p7', 'corr_pair_ratio_gt_0p9', 'corr_pair_ratio_lt_0p2']

## Scope guard

- No machine learning was run.
- No cross-spectrum/coherence was computed.
- No FFT/background contrast output was modified.
- No channel was automatically removed.
- Channel correlation is not interpreted as physical target spatial distribution.
