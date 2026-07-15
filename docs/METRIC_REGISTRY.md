# Metric Registry

This registry lists metrics that are currently implemented by DataProcess.

Allowed `layer` values:

- `L0_integrity`
- `L1_nist_run_sequence`
- `L1_nist_lag`
- `L1_nist_distribution`
- `L1_nist_normal_probability`
- `L2_stability_window`
- `L3_background_model`
- `L4_frequency_domain`

Allowed lifecycle values:

- `keep`: keep the metric in the current output.
- `deprecate`: keep temporarily for compatibility, but do not use as a primary quality metric.
- `move_to_nist`: implemented now, but should be migrated or reinterpreted under the NIST-style layer in a future refactor.

## Time Per-File Metrics

Implemented in `src/features/time_metrics.py` and exported by `src/reports/excel_export.py` to `time_series_metrics.xlsx`.

| metric_name | layer | formula | meaning | unit | implemented_file | keep/deprecate/move_to_nist |
| --- | --- | --- | --- | --- | --- | --- |
| sample_count | L0_integrity | `count(finite x and valid time if provided)` | Number of valid samples used for metric calculation. | samples | `src/features/time_metrics.py` | keep |
| duration_seconds | L0_integrity | `time[-1] - time[0]`; fallback `FILE_DURATION` | Effective file duration. | s | `src/features/time_metrics.py` | keep |
| dt_median | L0_integrity | `median(diff(time))` for positive finite time steps | Median sampling interval. | s | `src/features/time_metrics.py` | keep |
| dt_std | L0_integrity | `std(diff(time))` for positive finite time steps | Sampling interval jitter indicator. | s | `src/features/time_metrics.py` | keep |
| mean | L1_nist_distribution | `mean(x)` | File-level DC baseline. | V | `src/features/time_metrics.py` | keep |
| median | L1_nist_distribution | `median(x)` | Robust file-level baseline. | V | `src/features/time_metrics.py` | keep |
| min | L1_nist_distribution | `min(x)` | Minimum observed voltage. | V | `src/features/time_metrics.py` | keep |
| max | L1_nist_distribution | `max(x)` | Maximum observed voltage. | V | `src/features/time_metrics.py` | keep |
| peak_to_peak | L1_nist_distribution | `max(x) - min(x)` | Full observed voltage span. | V | `src/features/time_metrics.py` | keep |
| std | L1_nist_distribution | `std(x, ddof=0)` | Standard deviation of raw voltage samples. | V | `src/features/time_metrics.py` | keep |
| ac_rms | L1_nist_distribution | `sqrt(mean((x - mean(x))^2))` | AC fluctuation RMS after removing DC mean. | V | `src/features/time_metrics.py` | keep |
| robust_sigma | L1_nist_distribution | `1.4826 * median(abs(x - median(x)))` | Robust noise scale estimated from MAD. | V | `src/features/time_metrics.py` | keep |
| crest_factor | L1_nist_distribution | `max(abs(x - mean(x))) / ac_rms` | Peak-to-RMS factor for within-file fluctuation. | dimensionless | `src/features/time_metrics.py` | keep |
| drift_slope | L1_nist_run_sequence | `slope(polyfit(time, x, 1))` | Linear within-file drift slope. | V/s | `src/features/time_metrics.py` | move_to_nist |
| drift_span | L1_nist_run_sequence | `abs(drift_slope) * duration_seconds` | Within-file linear drift amplitude. | V | `src/features/time_metrics.py` | move_to_nist |
| drift_ratio_robust | L1_nist_run_sequence | `drift_span / robust_sigma` | Within-file drift relative to robust noise scale. | dimensionless | `src/features/time_metrics.py` | move_to_nist |
| drift_ratio_ac | L1_nist_run_sequence | `drift_span / ac_rms` | Within-file drift relative to AC RMS. | dimensionless | `src/features/time_metrics.py` | move_to_nist |
| strict_global_outlier_rate | L1_nist_distribution | `count(abs(x - median(x)) > 15 * robust_sigma) / sample_count` | Strict global candidate outlier fraction. | fraction | `src/features/time_metrics.py` | deprecate |
| candidate_isolated_spike_rate | L1_nist_distribution | `strict outlier samples in runs with length <= 3 / sample_count` | Candidate isolated spike sample fraction. | fraction | `src/features/time_metrics.py` | keep |
| candidate_cluster_spike_rate | L1_nist_distribution | `strict outlier samples in runs with length > 3 / sample_count` | Candidate clustered spike sample fraction. | fraction | `src/features/time_metrics.py` | keep |
| robust_tail_fraction | L1_nist_distribution | `count(abs(x - median(x)) > 5 * robust_sigma) / sample_count` | Robust tail fraction; indicates heavy tails, not bad-point rate. | fraction | `src/features/time_metrics.py` | keep |
| repeated_extreme_rate | L0_integrity | `(max(0, count(x == max) - 1) + max(0, count(x == min) - 1)) / sample_count` | Fraction of repeated extreme samples beyond first min/max occurrence. | fraction | `src/features/time_metrics.py` | keep |
| repeated_extreme_count | L0_integrity | `count(x == max) + count(x == min)` | Count of samples exactly equal to file min or max. | samples | `src/features/time_metrics.py` | keep |

## Time Group Summary Metrics

Implemented in `src/summaries/time_group_summary.py` and exported by `src/reports/excel_export.py` to `time_series_group_summary.xlsx`.

| metric_name | layer | formula | meaning | unit | implemented_file | keep/deprecate/move_to_nist |
| --- | --- | --- | --- | --- | --- | --- |
| channel | L0_integrity | `channel name` | Channel identifier. | text | `src/summaries/time_group_summary.py` | keep |
| group | L0_integrity | `Path(group_dir).name` | Group/folder identifier. | text | `src/summaries/time_group_summary.py` | keep |
| file_count | L0_integrity | `len(files in group)` | Number of files summarized for the channel. | files | `src/summaries/time_group_summary.py` | keep |
| mean_of_file_means | L1_nist_distribution | `mean(mean_i)` | Average DC baseline across files. | V | `src/summaries/time_group_summary.py` | keep |
| std_of_file_means | L1_nist_run_sequence | `std(mean_i, ddof=0)` | Cross-file baseline variation. | V | `src/summaries/time_group_summary.py` | move_to_nist |
| range_of_file_means | L1_nist_run_sequence | `max(mean_i) - min(mean_i)` | Cross-file baseline range. | V | `src/summaries/time_group_summary.py` | move_to_nist |
| baseline_stability_factor | L1_nist_run_sequence | `mean_ac_rms / std_of_file_means` | How many within-file noise RMS units fit into cross-file baseline variation denominator inverted as stability factor. | dimensionless | `src/summaries/time_group_summary.py` | move_to_nist |
| baseline_instability_ratio | L1_nist_run_sequence | `std_of_file_means / mean_ac_rms` | Cross-file baseline instability relative to within-file AC RMS. | dimensionless | `src/summaries/time_group_summary.py` | move_to_nist |
| mean_robust_sigma | L1_nist_distribution | `mean(robust_sigma_i)` | Average robust noise scale across files. | V | `src/summaries/time_group_summary.py` | keep |
| std_robust_sigma | L1_nist_distribution | `std(robust_sigma_i, ddof=0)` | Cross-file variation of robust noise scale. | V | `src/summaries/time_group_summary.py` | keep |
| max_robust_sigma | L1_nist_distribution | `max(robust_sigma_i)` | Worst robust noise scale across files. | V | `src/summaries/time_group_summary.py` | keep |
| robust_sigma_cv | L1_nist_distribution | `std_robust_sigma / mean_robust_sigma` | Relative variation of robust noise scale. | dimensionless | `src/summaries/time_group_summary.py` | keep |
| mean_ac_rms | L1_nist_distribution | `mean(ac_rms_i)` | Average AC RMS across files. | V | `src/summaries/time_group_summary.py` | keep |
| std_ac_rms | L1_nist_distribution | `std(ac_rms_i, ddof=0)` | Cross-file variation of AC RMS. | V | `src/summaries/time_group_summary.py` | keep |
| cv_ac_rms | L1_nist_distribution | `std_ac_rms / mean_ac_rms` | Relative variation of AC RMS. | dimensionless | `src/summaries/time_group_summary.py` | keep |
| mean_crest_factor | L1_nist_distribution | `mean(crest_factor_i)` | Average peak-to-RMS factor across files. | dimensionless | `src/summaries/time_group_summary.py` | keep |
| max_crest_factor | L1_nist_distribution | `max(crest_factor_i)` | Worst peak-to-RMS factor across files. | dimensionless | `src/summaries/time_group_summary.py` | keep |
| max_peak_to_peak | L1_nist_distribution | `max(peak_to_peak_i)` | Largest observed file voltage span. | V | `src/summaries/time_group_summary.py` | keep |
| median_drift_ratio_robust | L1_nist_run_sequence | `median(drift_ratio_robust_i)` | Typical within-file drift relative to robust noise. | dimensionless | `src/summaries/time_group_summary.py` | move_to_nist |
| max_drift_ratio_robust | L1_nist_run_sequence | `max(drift_ratio_robust_i)` | Worst within-file drift relative to robust noise. | dimensionless | `src/summaries/time_group_summary.py` | move_to_nist |
| median_drift_ratio_ac | L1_nist_run_sequence | `median(drift_ratio_ac_i)` | Typical within-file drift relative to AC RMS. | dimensionless | `src/summaries/time_group_summary.py` | move_to_nist |
| max_drift_ratio_ac | L1_nist_run_sequence | `max(drift_ratio_ac_i)` | Worst within-file drift relative to AC RMS. | dimensionless | `src/summaries/time_group_summary.py` | move_to_nist |
| cross_drift_slope_v_per_s | L1_nist_run_sequence | `slope(polyfit(i * FILE_DURATION, mean_i, 1))` | Cross-file baseline drift slope over acquisition order. | V/s | `src/summaries/time_group_summary.py` | move_to_nist |
| cross_drift_span | L1_nist_run_sequence | `abs(cross_drift_slope_v_per_s) * FILE_DURATION * (N - 1)` | Cross-file baseline drift span. | V | `src/summaries/time_group_summary.py` | move_to_nist |
| cross_drift_ratio_robust | L1_nist_run_sequence | `cross_drift_span / median(robust_sigma_i)` | Cross-file drift relative to median robust sigma. | dimensionless | `src/summaries/time_group_summary.py` | move_to_nist |
| cross_drift_ratio_ac | L1_nist_run_sequence | `cross_drift_span / mean(ac_rms_i)` | Cross-file drift relative to average AC RMS. | dimensionless | `src/summaries/time_group_summary.py` | move_to_nist |
| median_robust_sigma_for_ratio | L1_nist_distribution | `median(robust_sigma_i)` | Denominator used by `cross_drift_ratio_robust`. | V | `src/summaries/time_group_summary.py` | keep |
| mean_candidate_isolated_spike_rate | L1_nist_distribution | `mean(candidate_isolated_spike_rate_i)` | Average candidate isolated spike fraction. | fraction | `src/summaries/time_group_summary.py` | keep |
| max_candidate_isolated_spike_rate | L1_nist_distribution | `max(candidate_isolated_spike_rate_i)` | Worst candidate isolated spike fraction. | fraction | `src/summaries/time_group_summary.py` | keep |
| mean_candidate_cluster_spike_rate | L1_nist_distribution | `mean(candidate_cluster_spike_rate_i)` | Average candidate clustered spike fraction. | fraction | `src/summaries/time_group_summary.py` | keep |
| max_candidate_cluster_spike_rate | L1_nist_distribution | `max(candidate_cluster_spike_rate_i)` | Worst candidate clustered spike fraction. | fraction | `src/summaries/time_group_summary.py` | keep |
| mean_robust_tail_fraction | L1_nist_distribution | `mean(robust_tail_fraction_i)` | Average robust tail fraction. | fraction | `src/summaries/time_group_summary.py` | keep |
| max_robust_tail_fraction | L1_nist_distribution | `max(robust_tail_fraction_i)` | Worst robust tail fraction. | fraction | `src/summaries/time_group_summary.py` | keep |
| mean_repeated_extreme_rate | L0_integrity | `mean(repeated_extreme_rate_i)` | Average repeated extreme rate across files. | fraction | `src/summaries/time_group_summary.py` | keep |
| max_repeated_extreme_rate | L0_integrity | `max(repeated_extreme_rate_i)` | Worst repeated extreme rate across files. | fraction | `src/summaries/time_group_summary.py` | keep |
| max_repeated_extreme_count | L0_integrity | `max(repeated_extreme_count_i)` | Largest repeated extreme count across files. | samples | `src/summaries/time_group_summary.py` | keep |

## FFT Export Metrics

Implemented in `src/features/fft_core.py` and `src/pipelines/fft_export_pipeline.py`, exported to `FFT_<input_filename>.csv`.

| metric_name | layer | formula | meaning | unit | implemented_file | keep/deprecate/move_to_nist |
| --- | --- | --- | --- | --- | --- | --- |
| frequency | L4_frequency_domain | `np.fft.fftfreq(n, 1 / sampling_rate)[freqs > 0]` | Positive frequency bins. | Hz | `src/features/fft_core.py` | keep |
| amplitudeN | L4_frequency_domain | `abs(np.fft.fft(channelN)) / n` for positive frequencies | FFT amplitude for channel N. | input unit | `src/features/fft_core.py` | keep |
| phaseN | L4_frequency_domain | `angle(np.fft.fft(channelN))` for positive frequencies | FFT phase for channel N. | rad | `src/features/fft_core.py` | keep |

## FFT Average Metrics

Implemented in `src/pipelines/fft_average_pipeline.py` and re-exported by `src/features/fft_average.py`, exported to `average_fft_<folder>_<count>files.csv`.

| metric_name | layer | formula | meaning | unit | implemented_file | keep/deprecate/move_to_nist |
| --- | --- | --- | --- | --- | --- | --- |
| average_frequency | L4_frequency_domain | `frequency` copied from first valid FFT file after axis consistency check | Frequency axis for averaged FFT data. | Hz | `src/pipelines/fft_average_pipeline.py` | keep |
| average_amplitudeN | L4_frequency_domain | `mean(amplitudeN_i)` across valid FFT files | Average FFT amplitude for channel N. | input unit | `src/pipelines/fft_average_pipeline.py` | keep |
| average_phaseN | L4_frequency_domain | `mean(phaseN_i)` across valid FFT files | Average FFT phase for channel N. | rad | `src/pipelines/fft_average_pipeline.py` | keep |

## Frequency Analysis Metrics And Report Fields

Implemented in `src/pipelines/frequency_analysis_pipeline.py` and re-exported by `src/features/fft_statistics.py`, `src/plots/frequency_plots.py`, and `src/reports/json_report.py`.

| metric_name | layer | formula | meaning | unit | implemented_file | keep/deprecate/move_to_nist |
| --- | --- | --- | --- | --- | --- | --- |
| dominant_frequencies | L4_frequency_domain | Frequencies of top peaks from `signal.find_peaks(amplitude, height=amplitude.max()*0.05, distance=10)`, sorted by amplitude | Dominant peak frequencies per amplitude channel. | Hz | `src/pipelines/frequency_analysis_pipeline.py` | keep |
| dominant_amplitudes | L4_frequency_domain | `amplitude` at `dominant_frequencies` | Peak amplitudes corresponding to dominant frequencies. | input unit | `src/pipelines/frequency_analysis_pipeline.py` | keep |
| total_energy | L4_frequency_domain | `trapz(amplitude, frequency)` | Integrated FFT amplitude over frequency. | input unit * Hz | `src/pipelines/frequency_analysis_pipeline.py` | keep |
| peak_count | L4_frequency_domain | `len(peaks)` from `find_peaks` | Number of detected spectral peaks. | count | `src/pipelines/frequency_analysis_pipeline.py` | keep |
| max_amplitude | L4_frequency_domain | `max(amplitude)` | Maximum FFT amplitude for a channel. | input unit | `src/pipelines/frequency_analysis_pipeline.py` | keep |
| mean_amplitude | L4_frequency_domain | `mean(amplitude)` | Mean FFT amplitude for a channel. | input unit | `src/pipelines/frequency_analysis_pipeline.py` | keep |
| std_amplitude | L4_frequency_domain | `std(amplitude)` | Standard deviation of FFT amplitude for a channel. | input unit | `src/pipelines/frequency_analysis_pipeline.py` | keep |
| frequency_range | L4_frequency_domain | `[min(frequency), max(frequency)]` | Frequency coverage for a channel spectrum. | Hz | `src/pipelines/frequency_analysis_pipeline.py` | keep |
| mean_phase_diff | L4_frequency_domain | `mean(unwrap(phase_channel - phase_reference))` | Mean unwrapped phase difference relative to reference channel. | rad | `src/pipelines/frequency_analysis_pipeline.py` | keep |
| std_phase_diff | L4_frequency_domain | `std(unwrap(phase_channel - phase_reference))` | Variation of unwrapped phase difference. | rad | `src/pipelines/frequency_analysis_pipeline.py` | keep |
| estimated_time_delay_ms | L4_frequency_domain | `-slope(polyfit(frequency, phase_diff_unwrapped, 1)) / (2*pi) * 1000` for valid 10-500 Hz band | Estimated inter-channel time delay from phase slope. | ms | `src/pipelines/frequency_analysis_pipeline.py` | keep |
| phase_coherence | L4_frequency_domain | `abs(mean(exp(1j * phase_diff_unwrapped)))` | Phase coherence relative to reference channel. | dimensionless | `src/pipelines/frequency_analysis_pipeline.py` | keep |
| cv_amplitude | L4_frequency_domain | `std_amplitude / (mean_amplitude + 1e-8)` in group stability plot | Frequency-wise coefficient of variation across files. | dimensionless | `src/pipelines/frequency_analysis_pipeline.py` | keep |
| overall_cv | L4_frequency_domain | `mean(cv_amplitude[frequency < 500])` | Low-frequency group amplitude variation summary. | dimensionless | `src/pipelines/frequency_analysis_pipeline.py` | keep |
| feature_frequency_actual_frequency | L4_frequency_domain | `frequency[argmin(abs(frequency - target_freq))]` | Nearest available frequency bin to target feature frequency. | Hz | `src/pipelines/frequency_analysis_pipeline.py` | keep |
| feature_frequency_amplitude | L4_frequency_domain | `amplitude[argmin(abs(frequency - target_freq))]` | Amplitude at nearest target feature frequency bin. | input unit | `src/pipelines/frequency_analysis_pipeline.py` | keep |
| feature_frequency_error | L4_frequency_domain | `abs(actual_frequency - target_freq)` | Frequency-bin mismatch relative to target frequency. | Hz | `src/pipelines/frequency_analysis_pipeline.py` | keep |
| frequency_clusters | L4_frequency_domain | Cluster dominant frequencies using tolerance `50 Hz`, returning up to first 3 cluster centers | Dominant frequency cluster centers. | Hz | `src/pipelines/frequency_analysis_pipeline.py` | keep |
| amplitude_consistency_cv | L4_frequency_domain | `std(channel_max_amplitudes) / mean(channel_max_amplitudes)` | Report field for cross-file max-amplitude consistency. | dimensionless | `src/pipelines/frequency_analysis_pipeline.py` | deprecate |
| energy_consistency_cv | L4_frequency_domain | `std(channel_energies) / mean(channel_energies)` | Report field for cross-file total-energy consistency. | dimensionless | `src/pipelines/frequency_analysis_pipeline.py` | deprecate |

## NIST Diagnostics Metrics

Implemented in `src/features/nist_diagnostics.py`, exported by `src/reports/nist_excel_export.py` to `nist_diagnostics_metrics.xlsx`, and plotted by `src/plots/nist_4plot.py`.

| metric_name | layer | formula | meaning | unit | implemented_file | keep/deprecate/move_to_nist |
| --- | --- | --- | --- | --- | --- | --- |
| run_mean | L1_nist_run_sequence | `mean(x)` | Mean level used in run sequence diagnostics. | V | `src/features/nist_diagnostics.py` | keep |
| run_median | L1_nist_run_sequence | `median(x)` | Robust center used in run sequence diagnostics. | V | `src/features/nist_diagnostics.py` | keep |
| run_std | L1_nist_run_sequence | `std(x, ddof=0)` | Run sequence vertical spread. | V | `src/features/nist_diagnostics.py` | keep |
| run_ac_rms | L1_nist_run_sequence | `sqrt(mean((x - mean(x))^2))` | Run sequence AC RMS. | V | `src/features/nist_diagnostics.py` | keep |
| run_robust_sigma | L1_nist_run_sequence | `1.4826 * median(abs(x - median(x)))` | Robust spread for run sequence diagnostics. | V | `src/features/nist_diagnostics.py` | keep |
| run_drift_slope | L1_nist_run_sequence | `slope(polyfit(time_or_index, x, 1))` | Linear trend slope in run sequence. | V/s | `src/features/nist_diagnostics.py` | keep |
| run_drift_span | L1_nist_run_sequence | `abs(run_drift_slope) * duration_seconds` | Run sequence linear drift span. | V | `src/features/nist_diagnostics.py` | keep |
| run_drift_ratio_ac | L1_nist_run_sequence | `run_drift_span / run_ac_rms` | Drift relative to run AC RMS. | dimensionless | `src/features/nist_diagnostics.py` | keep |
| run_drift_ratio_robust | L1_nist_run_sequence | `run_drift_span / run_robust_sigma` | Drift relative to robust spread. | dimensionless | `src/features/nist_diagnostics.py` | keep |
| run_rolling_mean_range | L1_nist_run_sequence | `max(window_mean) - min(window_mean)` using block windows | Range of local mean estimates. | V | `src/features/nist_diagnostics.py` | keep |
| run_rolling_ac_rms_cv | L1_nist_run_sequence | `std(window_ac_rms) / mean(window_ac_rms)` using block windows | Relative variation of local AC RMS estimates. | dimensionless | `src/features/nist_diagnostics.py` | keep |
| run_rolling_mad_cv | L1_nist_run_sequence | `std(window_mad_sigma) / mean(window_mad_sigma)` using block windows | Relative variation of local robust spread estimates. | dimensionless | `src/features/nist_diagnostics.py` | keep |
| run_max_step_jump | L1_nist_run_sequence | `max(abs(diff(x)))` | Largest adjacent-sample jump. | V | `src/features/nist_diagnostics.py` | keep |
| run_max_step_jump_ratio_ac | L1_nist_run_sequence | `run_max_step_jump / run_ac_rms` | Largest adjacent jump relative to AC RMS. | dimensionless | `src/features/nist_diagnostics.py` | keep |
| lag_1_corr | L1_nist_lag | `corr(x[:-1], x[1:])` | Lag-1 serial correlation. | dimensionless | `src/features/nist_diagnostics.py` | keep |
| lag_2_corr | L1_nist_lag | `corr(x[:-2], x[2:])` | Lag-2 serial correlation. | dimensionless | `src/features/nist_diagnostics.py` | keep |
| acf_first_peak_lag_samples | L1_nist_lag | first local ACF peak lag, fallback max absolute ACF lag | Lag of first ACF peak. | samples | `src/features/nist_diagnostics.py` | keep |
| acf_first_peak_lag_seconds | L1_nist_lag | `acf_first_peak_lag_samples * median(diff(time))` | First ACF peak lag converted to time. | s | `src/features/nist_diagnostics.py` | keep |
| acf_first_peak_value | L1_nist_lag | `acf[acf_first_peak_lag_samples]` | ACF value at first selected peak. | dimensionless | `src/features/nist_diagnostics.py` | keep |
| dist_min | L1_nist_distribution | `min(x)` | Minimum sample value. | V | `src/features/nist_diagnostics.py` | keep |
| dist_max | L1_nist_distribution | `max(x)` | Maximum sample value. | V | `src/features/nist_diagnostics.py` | keep |
| dist_peak_to_peak | L1_nist_distribution | `max(x) - min(x)` | Distribution span. | V | `src/features/nist_diagnostics.py` | keep |
| dist_q01 | L1_nist_distribution | `quantile(x, 0.01)` | 1st percentile. | V | `src/features/nist_diagnostics.py` | keep |
| dist_q05 | L1_nist_distribution | `quantile(x, 0.05)` | 5th percentile. | V | `src/features/nist_diagnostics.py` | keep |
| dist_q25 | L1_nist_distribution | `quantile(x, 0.25)` | 25th percentile. | V | `src/features/nist_diagnostics.py` | keep |
| dist_q50 | L1_nist_distribution | `quantile(x, 0.50)` | Median / 50th percentile. | V | `src/features/nist_diagnostics.py` | keep |
| dist_q75 | L1_nist_distribution | `quantile(x, 0.75)` | 75th percentile. | V | `src/features/nist_diagnostics.py` | keep |
| dist_q95 | L1_nist_distribution | `quantile(x, 0.95)` | 95th percentile. | V | `src/features/nist_diagnostics.py` | keep |
| dist_q99 | L1_nist_distribution | `quantile(x, 0.99)` | 99th percentile. | V | `src/features/nist_diagnostics.py` | keep |
| dist_iqr | L1_nist_distribution | `dist_q75 - dist_q25` | Interquartile range. | V | `src/features/nist_diagnostics.py` | keep |
| dist_skewness | L1_nist_distribution | `scipy.stats.skew(x)` | Distribution skewness. | dimensionless | `src/features/nist_diagnostics.py` | keep |
| dist_kurtosis | L1_nist_distribution | `scipy.stats.kurtosis(x, fisher=True)` | Excess kurtosis. | dimensionless | `src/features/nist_diagnostics.py` | keep |
| dist_robust_tail_fraction | L1_nist_distribution | `count(abs(x - median(x)) > 5 * robust_sigma) / n` | Robust heavy-tail fraction. | fraction | `src/features/nist_diagnostics.py` | keep |
| dist_strict_global_outlier_rate | L1_nist_distribution | `count(abs(x - median(x)) > 15 * robust_sigma) / n` | Strict global candidate outlier fraction. | fraction | `src/features/nist_diagnostics.py` | deprecate |
| dist_crest_factor | L1_nist_distribution | `max(abs(x - mean(x))) / ac_rms` | Distribution peak-to-RMS factor. | dimensionless | `src/features/nist_diagnostics.py` | keep |
| dist_mode_ratio | L1_nist_distribution | `max(value_count) / n` | Fraction of the most repeated exact value. | fraction | `src/features/nist_diagnostics.py` | keep |
| dist_unique_value_count | L1_nist_distribution | `count(unique(x))` | Number of unique exact sample values. | count | `src/features/nist_diagnostics.py` | keep |
| qq_normal_prob_corr | L1_nist_normal_probability | `corr(theoretical_normal_quantiles, ordered_values)` | Normal probability / QQ correlation. | dimensionless | `src/features/nist_diagnostics.py` | keep |
| qq_slope | L1_nist_normal_probability | `slope(polyfit(theoretical_quantiles, ordered_values, 1))` | QQ fit slope. | V | `src/features/nist_diagnostics.py` | keep |
| qq_intercept | L1_nist_normal_probability | `intercept(polyfit(theoretical_quantiles, ordered_values, 1))` | QQ fit intercept. | V | `src/features/nist_diagnostics.py` | keep |
| qq_tail_deviation | L1_nist_normal_probability | `mean(abs(ordered_values - qq_fit_line) in p<=0.05 or p>=0.95) / robust_sigma` | Normal probability tail deviation. | dimensionless | `src/features/nist_diagnostics.py` | keep |

## NIST Diagnostics Group Summary Metrics

Implemented in `src/summaries/nist_diagnostics_summary.py` and exported to `nist_diagnostics_group_summary.xlsx`.

| metric_name | layer | formula | meaning | unit | implemented_file | keep/deprecate/move_to_nist |
| --- | --- | --- | --- | --- | --- | --- |
| mean_run_drift_ratio_ac | L1_nist_run_sequence | `mean(run_drift_ratio_ac_i)` | Average run drift ratio relative to AC RMS. | dimensionless | `src/summaries/nist_diagnostics_summary.py` | keep |
| max_run_drift_ratio_ac | L1_nist_run_sequence | `max(run_drift_ratio_ac_i)` | Worst run drift ratio relative to AC RMS. | dimensionless | `src/summaries/nist_diagnostics_summary.py` | keep |
| mean_run_rolling_mean_range | L1_nist_run_sequence | `mean(run_rolling_mean_range_i)` | Average local-mean range. | V | `src/summaries/nist_diagnostics_summary.py` | keep |
| max_run_rolling_mean_range | L1_nist_run_sequence | `max(run_rolling_mean_range_i)` | Worst local-mean range. | V | `src/summaries/nist_diagnostics_summary.py` | keep |
| mean_run_rolling_ac_rms_cv | L1_nist_run_sequence | `mean(run_rolling_ac_rms_cv_i)` | Average local AC RMS variation. | dimensionless | `src/summaries/nist_diagnostics_summary.py` | keep |
| max_run_rolling_ac_rms_cv | L1_nist_run_sequence | `max(run_rolling_ac_rms_cv_i)` | Worst local AC RMS variation. | dimensionless | `src/summaries/nist_diagnostics_summary.py` | keep |
| mean_run_max_step_jump_ratio_ac | L1_nist_run_sequence | `mean(run_max_step_jump_ratio_ac_i)` | Average max adjacent jump relative to AC RMS. | dimensionless | `src/summaries/nist_diagnostics_summary.py` | keep |
| max_run_max_step_jump_ratio_ac | L1_nist_run_sequence | `max(run_max_step_jump_ratio_ac_i)` | Worst max adjacent jump relative to AC RMS. | dimensionless | `src/summaries/nist_diagnostics_summary.py` | keep |
| mean_lag_1_corr | L1_nist_lag | `mean(lag_1_corr_i)` | Average lag-1 serial correlation. | dimensionless | `src/summaries/nist_diagnostics_summary.py` | keep |
| max_abs_lag_1_corr | L1_nist_lag | `max(abs(lag_1_corr_i))` | Worst absolute lag-1 serial correlation. | dimensionless | `src/summaries/nist_diagnostics_summary.py` | keep |
| mean_lag_2_corr | L1_nist_lag | `mean(lag_2_corr_i)` | Average lag-2 serial correlation. | dimensionless | `src/summaries/nist_diagnostics_summary.py` | keep |
| max_abs_lag_2_corr | L1_nist_lag | `max(abs(lag_2_corr_i))` | Worst absolute lag-2 serial correlation. | dimensionless | `src/summaries/nist_diagnostics_summary.py` | keep |
| mean_acf_first_peak_value | L1_nist_lag | `mean(acf_first_peak_value_i)` | Average selected first ACF peak value. | dimensionless | `src/summaries/nist_diagnostics_summary.py` | keep |
| max_acf_first_peak_value | L1_nist_lag | `max(acf_first_peak_value_i)` | Worst selected first ACF peak value. | dimensionless | `src/summaries/nist_diagnostics_summary.py` | keep |
| mean_dist_iqr | L1_nist_distribution | `mean(dist_iqr_i)` | Average IQR. | V | `src/summaries/nist_diagnostics_summary.py` | keep |
| mean_dist_skewness | L1_nist_distribution | `mean(dist_skewness_i)` | Average distribution skewness. | dimensionless | `src/summaries/nist_diagnostics_summary.py` | keep |
| mean_dist_kurtosis | L1_nist_distribution | `mean(dist_kurtosis_i)` | Average excess kurtosis. | dimensionless | `src/summaries/nist_diagnostics_summary.py` | keep |
| mean_dist_robust_tail_fraction | L1_nist_distribution | `mean(dist_robust_tail_fraction_i)` | Average robust tail fraction. | fraction | `src/summaries/nist_diagnostics_summary.py` | keep |
| max_dist_robust_tail_fraction | L1_nist_distribution | `max(dist_robust_tail_fraction_i)` | Worst robust tail fraction. | fraction | `src/summaries/nist_diagnostics_summary.py` | keep |
| mean_dist_mode_ratio | L1_nist_distribution | `mean(dist_mode_ratio_i)` | Average exact-mode ratio. | fraction | `src/summaries/nist_diagnostics_summary.py` | keep |
| max_dist_mode_ratio | L1_nist_distribution | `max(dist_mode_ratio_i)` | Worst exact-mode ratio. | fraction | `src/summaries/nist_diagnostics_summary.py` | keep |
| mean_qq_normal_prob_corr | L1_nist_normal_probability | `mean(qq_normal_prob_corr_i)` | Average QQ normal probability correlation. | dimensionless | `src/summaries/nist_diagnostics_summary.py` | keep |
| min_qq_normal_prob_corr | L1_nist_normal_probability | `min(qq_normal_prob_corr_i)` | Worst QQ normal probability correlation. | dimensionless | `src/summaries/nist_diagnostics_summary.py` | keep |
| mean_qq_tail_deviation | L1_nist_normal_probability | `mean(qq_tail_deviation_i)` | Average QQ tail deviation. | dimensionless | `src/summaries/nist_diagnostics_summary.py` | keep |
| max_qq_tail_deviation | L1_nist_normal_probability | `max(qq_tail_deviation_i)` | Worst QQ tail deviation. | dimensionless | `src/summaries/nist_diagnostics_summary.py` | keep |
