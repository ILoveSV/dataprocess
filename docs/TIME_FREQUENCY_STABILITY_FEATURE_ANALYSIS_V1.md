# Time-Frequency Stability Feature Analysis v1

## Purpose

PSD summarizes whole-file spectral strength. Time-frequency stability checks whether candidate bands or peak windows persist across time windows or are driven by short bursts.

## Inputs

- Time CSV root: `D:\Lab\process\26.5.12\time`
- Groups read: 2m0hz, 2m30hz, 2m50hz, 3m0hz, 3m30hz, 3m50hz, 5m0hz, 5m30hz, 5m50hz

## Rolling FFT / Bandpower Method

- window_sec: `0.2`
- overlap: `0.0`
- window_function: `hann`
- n_fft: derived per file from `round(sampling_rate_hz * window_sec)`
- frequency resolution: `sampling_rate_hz / n_fft`
- bandpower formula: `10*log10(sum(periodogram_power_density * df_hz) + EPS)`
- preprocessing: per-window mean removal; no full FFT pipeline was rerun.

## Outputs and Coverage

- File/channel/band feature rows: 1879200
- Stability summary rows: 46980
- Feature roles: {'auxiliary_candidate': 138, 'reject': 132, 'qc_only': 120, 'primary_candidate': 45}

## Top File-Aggregated Separability Results

- `band_100_200k__tf_background_detection_margin` `Task A active vs 0Hz`: AUC=1, effect=2.72
- `band_100_200k__tf_background_relative_median_gain` `Task A active vs 0Hz`: AUC=1, effect=2.64
- `band_100_200k__tf_background_threshold_occupancy_ratio` `Task A active vs 0Hz`: AUC=1, effect=52
- `subband_70_80k__tf_background_threshold_occupancy_ratio` `Task A active vs 0Hz`: AUC=1, effect=4.24
- `band_100_200k__tf_background_detection_margin` `Task B 30Hz vs 50Hz`: AUC=1, effect=3.35
- `band_100_200k__tf_background_relative_median_gain` `Task B 30Hz vs 50Hz`: AUC=1, effect=3.38
- `band_100_200k__tf_bandpower_mean` `Task B 30Hz vs 50Hz`: AUC=1, effect=3.16
- `band_100_200k__tf_bandpower_median` `Task B 30Hz vs 50Hz`: AUC=1, effect=3.35
- `band_100_200k__tf_bandpower_p10` `Task B 30Hz vs 50Hz`: AUC=1, effect=3.19
- `peakwin_137_139p5k__tf_peak_freq_median` `Task B 30Hz vs 50Hz`: AUC=1, effect=2.62
- `peakwin_137_139p5k__tf_peak_prominence_median` `Task B 30Hz vs 50Hz`: AUC=1, effect=4.78
- `peakwin_177_179k__tf_background_relative_median_gain` `Task B 30Hz vs 50Hz`: AUC=1, effect=4.43

## Stable vs Burst-Like Interpretation

Features based on rolling bandpower median/mean and peak persistence are treated as evidence for persistence across windows. Burstiness, time concentration, occupancy, and high-event count features are treated as burst/risk or QC signals unless supported by stable median behavior.

### Candidate TF Auxiliary Features

band_100_200k__tf_background_detection_margin, band_100_200k__tf_background_relative_median_gain, band_100_200k__tf_background_threshold_occupancy_ratio, band_100_200k__tf_bandpower_cv, band_100_200k__tf_bandpower_mean, band_100_200k__tf_bandpower_median, band_100_200k__tf_bandpower_p10, band_100_200k__tf_bandpower_p90, band_100_200k__tf_bandpower_range, band_100_200k__tf_bandpower_std, band_100_200k__tf_peak_freq_median, band_100_200k__tf_peak_prominence_median, band_100_200k__tf_peak_value_median, band_100_200k__tf_time_entropy, band_50_100k__tf_background_detection_margin, band_50_100k__tf_background_relative_median_gain, band_50_100k__tf_background_threshold_occupancy_ratio, band_50_100k__tf_bandpower_mean, band_50_100k__tf_bandpower_median, band_50_100k__tf_bandpower_p10, band_50_100k__tf_bandpower_p90, band_50_100k__tf_peak_freq_median, band_50_100k__tf_peak_prominence_median, band_50_100k__tf_peak_value_median, peakwin_137_139p5k__tf_background_detection_margin, peakwin_137_139p5k__tf_background_relative_median_gain, peakwin_137_139p5k__tf_background_threshold_occupancy_ratio, peakwin_137_139p5k__tf_bandpower_cv, peakwin_137_139p5k__tf_bandpower_mean, peakwin_137_139p5k__tf_bandpower_median

### Burstiness / Short-Window Risk Features

band_100_200k__tf_bandpower_occupancy_ratio, band_100_200k__tf_burstiness_score, band_100_200k__tf_high_bandpower_event_count, band_100_200k__tf_longest_high_bandpower_duration, band_100_200k__tf_time_concentration_score, band_50_100k__tf_bandpower_occupancy_ratio, band_50_100k__tf_burstiness_score, band_50_100k__tf_high_bandpower_event_count, band_50_100k__tf_longest_high_bandpower_duration, band_50_100k__tf_time_concentration_score, peakwin_137_139p5k__tf_bandpower_occupancy_ratio, peakwin_137_139p5k__tf_burstiness_score, peakwin_137_139p5k__tf_high_bandpower_event_count, peakwin_137_139p5k__tf_longest_high_bandpower_duration, peakwin_137_139p5k__tf_time_concentration_score, peakwin_177_179k__tf_bandpower_occupancy_ratio, peakwin_177_179k__tf_burstiness_score, peakwin_177_179k__tf_high_bandpower_event_count, peakwin_177_179k__tf_longest_high_bandpower_duration, peakwin_177_179k__tf_time_concentration_score, peakwin_53p5_55k__tf_bandpower_occupancy_ratio, peakwin_53p5_55k__tf_burstiness_score, peakwin_53p5_55k__tf_high_bandpower_event_count, peakwin_53p5_55k__tf_longest_high_bandpower_duration, peakwin_53p5_55k__tf_time_concentration_score, subband_100_120k__tf_bandpower_occupancy_ratio, subband_100_120k__tf_burstiness_score, subband_100_120k__tf_high_bandpower_event_count, subband_100_120k__tf_longest_high_bandpower_duration, subband_100_120k__tf_time_concentration_score

## Comparison with Existing Feature Families

- `Task A active vs 0Hz`: best_tf_auc=1, additional_value=high, best_tf=subband_100_120k__tf_background_detection_margin
- `Task B 30Hz vs 50Hz`: best_tf_auc=1, additional_value=high, best_tf=band_100_200k__tf_bandpower_mean
- `Task C distance`: best_tf_auc=0.833, additional_value=high, best_tf=band_100_200k__tf_bandpower_p10
- `Task D rpm 3-class`: best_tf_auc=0.833, additional_value=high, best_tf=subband_60_70k__tf_background_detection_margin

## Role Guidance

- TF stability features are auxiliary evidence for PSD candidate stability, not a replacement for PSD/bandpower as the main line.
- Background-relative features use same-distance 0Hz window bandpower p95/median and are marked with background-threshold risk.
- Burst-like features should not be interpreted as stable target features without follow-up inspection.

## Scope Guard

- No machine learning was run.
- No full FFT pipeline was rerun.
- No background contrast formula was modified.
- No complete STFT matrix or per-file spectrograms were exported.
- No channel or file was automatically deleted.
- High TF AUC is not interpreted as a physical mechanism or final recognition result.
