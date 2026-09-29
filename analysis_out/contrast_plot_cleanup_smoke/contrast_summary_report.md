# Background Contrast v1.0 Report

## 1. Run Summary

- Input groups: 2m0hz, 2m30hz, 2m50hz.
- Formal channels: channel1-channel12.
- `channel=ALL` present: False; excluded from formal statistics: True.
- Missing or incomplete groups: none.
- Output location: `analysis_out\contrast_plot_cleanup_smoke`.

## 2. Smoke Coverage

smoke_test_coverage_status = PARTIAL

- PASS: 59.5kHz gain > 8dB
- PASS: 50k-100k band gain ~= 10dB
- PASS: lowfreq df=24.414 unreliable
- PASS: lowfreq df=0.5 reliable
- PASS: new/enhanced/suppressed/shared peak classification
- PASS: ACF change flag
- PASS: 8/12 strong, 6/12 medium, 3/12 weak, 1/12 none
- PASS: pumpfreq net contrast = 50 net - 30 net
- PASS: distance decay monotonic
- PASS: ALL channel excluded from formal support count

## 3. Background Pair Results

- 2m30hz vs 2m0hz: levels={'strong': 11, 'none': 2}; top features=bandpower:50khz_100khz(12), bandpower:100khz_200khz(12), bandpower:10khz_50khz(12), bandpower:59p5khz_pm1khz(12), bandpower:50khz_pm1khz(12); outlier_channels=['channel1', 'channel10', 'channel11', 'channel12', 'channel2', 'channel3', 'channel4', 'channel5', 'channel6', 'channel7', 'channel9']
- 2m50hz vs 2m0hz: levels={'strong': 11, 'none': 2}; top features=bandpower:50khz_100khz(12), bandpower:100khz_200khz(12), bandpower:10khz_50khz(12), bandpower:59p5khz_pm1khz(12), bandpower:50khz_pm1khz(12); outlier_channels=['channel1', 'channel10', 'channel11', 'channel12', 'channel2', 'channel3', 'channel4', 'channel5', 'channel6', 'channel7', 'channel9']

## 4. Bandpower Contrast

- 0_100hz: median_gain_dB={'2m30hz': 0.29, '2m50hz': 0.129}; support_rows={'2m30hz': 12, '2m50hz': 12}; lowfreq_reliable_all=True.
- 100hz_1khz: median_gain_dB={'2m30hz': 0.231, '2m50hz': 0.137}; support_rows={'2m30hz': 12, '2m50hz': 12}; lowfreq_reliable_all=True.
- 100khz_200khz: median_gain_dB={'2m30hz': 1.658, '2m50hz': 5.476}; support_rows={'2m30hz': 12, '2m50hz': 12}; lowfreq_reliable_all=True.
- 10khz_50khz: median_gain_dB={'2m30hz': 1.297, '2m50hz': 1.733}; support_rows={'2m30hz': 12, '2m50hz': 12}; lowfreq_reliable_all=True.
- 1khz_10khz: median_gain_dB={'2m30hz': 0.006, '2m50hz': 0.008}; support_rows={'2m30hz': 12, '2m50hz': 12}; lowfreq_reliable_all=True.
- 50hz_pm2hz: median_gain_dB={'2m30hz': 0.17, '2m50hz': 0.123}; support_rows={'2m30hz': 12, '2m50hz': 12}; lowfreq_reliable_all=False.
- 50khz_100khz: median_gain_dB={'2m30hz': 5.98, '2m50hz': 8.075}; support_rows={'2m30hz': 12, '2m50hz': 12}; lowfreq_reliable_all=True.
- 50khz_pm1khz: median_gain_dB={'2m30hz': 0.381, '2m50hz': 0.332}; support_rows={'2m30hz': 12, '2m50hz': 12}; lowfreq_reliable_all=True.
- 59p5khz_pm1khz: median_gain_dB={'2m30hz': 0.689, '2m50hz': 0.546}; support_rows={'2m30hz': 12, '2m50hz': 12}; lowfreq_reliable_all=True.
- 8p5khz_pm300hz: median_gain_dB={'2m30hz': 0.026, '2m50hz': 0.056}; support_rows={'2m30hz': 12, '2m50hz': 12}; lowfreq_reliable_all=True.

## 5. Peak Contrast

- 8.5kHz nearby: {'shared_peak': 5, 'new_peak': 1}.
- 50kHz nearby: {'new_peak': 4}.
- 59.5kHz nearby: {'new_peak': 6}.
- 30/50/60Hz nearby: none.

## 6. ACF Contrast

- 2m30hz: changed_channels=10/12, median_delta_first_acf=0.004763, median_delta_global_acf=0.004763, median_delta_peak_spacing_s=2.5e-06.
- 2m50hz: changed_channels=10/12, median_delta_first_acf=0.004182, median_delta_global_acf=0.004182, median_delta_peak_spacing_s=5.625e-06.

## 7. 30Hz vs 50Hz Net Contrast

Formula: `(50Hz - 0Hz) - (30Hz - 0Hz)`.

- 2m: distinguishable_rows=15/120.

## 8. Distance Decay

- No complete 2m/3m/5m feature triplets.

## 9. Outlier Channels

- channel1: 4 marked rows; examples=['59p5khz_pm1khz', '100hz_1khz', '50khz_pm1khz', '59p5khz_pm1khz'].
- channel10: 4 marked rows; examples=['50khz_pm1khz', '8p5khz_pm300hz', '50khz_pm1khz', '8p5khz_pm300hz'].
- channel11: 6 marked rows; examples=['1khz_10khz', '50khz_pm1khz', '8p5khz_pm300hz', '1khz_10khz', '50khz_pm1khz'].
- channel12: 2 marked rows; examples=['59p5khz_pm1khz', '59p5khz_pm1khz'].
- channel2: 3 marked rows; examples=['1khz_10khz', '8p5khz_pm300hz', '1khz_10khz'].
- channel3: 2 marked rows; examples=['50khz_pm1khz', '50khz_pm1khz'].
- channel4: 4 marked rows; examples=['59p5khz_pm1khz', '1khz_10khz', '59p5khz_pm1khz', '8p5khz_pm300hz'].
- channel5: 4 marked rows; examples=['50khz_pm1khz', '0_100hz', '1khz_10khz', '50khz_pm1khz'].
- channel6: 2 marked rows; examples=['59p5khz_pm1khz', '8p5khz_pm300hz'].
- channel7: 3 marked rows; examples=['1khz_10khz', '59p5khz_pm1khz', '59p5khz_pm1khz'].
- channel9: 2 marked rows; examples=['8p5khz_pm300hz', '8p5khz_pm300hz'].
- Outliers are marked only; no rows were deleted.

## 10. Conclusions

Strong evidence:
- 2m30hz vs 2m0hz bandpower:0_100hz support=12/12.
- 2m30hz vs 2m0hz bandpower:100hz_1khz support=12/12.
- 2m30hz vs 2m0hz bandpower:100khz_200khz support=12/12.
- 2m30hz vs 2m0hz bandpower:10khz_50khz support=12/12.
- 2m30hz vs 2m0hz bandpower:1khz_10khz support=12/12.
- 2m30hz vs 2m0hz bandpower:50hz_pm2hz support=12/12.
- 2m30hz vs 2m0hz bandpower:50khz_100khz support=12/12.
- 2m30hz vs 2m0hz bandpower:50khz_pm1khz support=12/12.
- 2m30hz vs 2m0hz bandpower:59p5khz_pm1khz support=12/12.
- 2m30hz vs 2m0hz bandpower:8p5khz_pm300hz support=12/12.

Moderate evidence:

Not supported:
- 2m30hz vs 2m0hz peak:10khz_200khz support=0/12.
- 2m30hz vs 2m0hz peak:1khz_10khz support=0/12.
- 2m50hz vs 2m0hz peak:10khz_200khz support=0/12.
- 2m50hz vs 2m0hz peak:1khz_10khz support=0/12.

## 11. Limitations

- Background and active groups were not synchronously acquired, so no raw waveform point-by-point subtraction was performed.
- Low-frequency 30/50/60Hz reliability depends on `df_hz` and `bin_count`.
- Observed differences cannot be directly attributed to water flow.
- Observed differences cannot be directly equated with the power-supply frequency itself.
- This remains feature-level background contrast, not physical source separation.
- PSD curves were adapter-generated as `psd_curve_level = group_median_recomputed`; p10/p90 in curve contrast are not file-level re-estimates.

## Plot Cleanup Status

- skipped_distance_decay: true
- reason: need at least 2 distances
