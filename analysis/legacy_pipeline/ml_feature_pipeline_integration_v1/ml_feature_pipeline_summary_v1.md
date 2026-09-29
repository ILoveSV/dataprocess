# ML Feature Pipeline Integration v1 Summary

- Overall status: `complete`
- ML ready note: Artifacts are organized for a pilot ML input selection step, but more experiments and cross-batch validation are still required before final ML claims.

## Modules

- `frequency_feature_extraction_v2` [feature_computation]: complete -> `analysis/legacy_pipeline\feature_extraction_v2`
- `time_domain_features_v1` [feature_computation]: complete -> `analysis/legacy_pipeline\time_domain_features_v1`
- `acf_features_v1` [feature_computation]: complete -> `analysis/legacy_pipeline\acf_features_v1`
- `time_frequency_stability_features_v1` [feature_computation]: complete -> `analysis/legacy_pipeline\time_frequency_stability_features_v1`
- `channel_correlation_features_v1` [qc_and_channel_structure]: complete -> `analysis/legacy_pipeline\channel_correlation_features_v1`
- `frequency_feature_separability_v1` [feature_validation_and_selection]: complete -> `analysis/legacy_pipeline\feature_separability_v1`
- `time_frequency_comparison_v1` [feature_validation_and_selection]: complete -> `analysis/legacy_pipeline\time_frequency_feature_comparison_v1`
- `channel_mask_sensitivity_v1` [qc_and_channel_structure]: complete -> `analysis/legacy_pipeline\channel_mask_sensitivity_v1`

## Candidate ML Inputs

- `recommended_after_channel_mask`: exists=True path=`analysis/legacy_pipeline\channel_mask_sensitivity_v1\recommended_feature_sets_after_channel_mask_v1.json`
- `masked_file_agg_matrix`: exists=True path=`analysis/legacy_pipeline\channel_mask_sensitivity_v1\masked_feature_matrix_file_agg_v1.csv`
- `frequency_time_recommended_sets`: exists=True path=`analysis/legacy_pipeline\time_frequency_feature_comparison_v1\recommended_feature_sets_v1.json`
- `acf_recommended_sets`: exists=True path=`analysis/legacy_pipeline\acf_features_v1\recommended_acf_feature_sets_v1.json`
- `tf_recommended_sets`: exists=True path=`analysis/legacy_pipeline\time_frequency_stability_features_v1\recommended_feature_sets_with_tf_v1.json`
- `recommended_current_main_mask`: mask_no_ch9_global
- `recommended_conservative_mask`: mask_no_ch9_ch5_global
- `ml_training_status`: not_run_by_this_pipeline
