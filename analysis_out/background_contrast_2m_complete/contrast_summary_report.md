# Background Contrast v1.0 Report

## 1. Run Summary

- Input groups: 2m0hz, 2m30hz, 2m50hz.
- Formal channels: channel1-channel12.
- `channel=ALL` present: False; excluded from formal statistics: True.
- Missing or incomplete groups: none.
- Output location: `analysis_out\background_contrast_2m_complete`.

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

- 2m30hz vs 2m0hz: levels={'strong': 11, 'none': 2}; top features=bandpower:50kHz-100kHz(12), bandpower:100kHz-200kHz(12), bandpower:10kHz-50kHz(12), bandpower:59.5kHz±1kHz(12), bandpower:50kHz±1kHz(12); outlier_channels=['channel1', 'channel10', 'channel11', 'channel12', 'channel2', 'channel3', 'channel4', 'channel5', 'channel6', 'channel7', 'channel9']
- 2m50hz vs 2m0hz: levels={'strong': 11, 'none': 2}; top features=bandpower:50kHz-100kHz(12), bandpower:100kHz-200kHz(12), bandpower:10kHz-50kHz(12), bandpower:59.5kHz±1kHz(12), bandpower:50kHz±1kHz(12); outlier_channels=['channel1', 'channel10', 'channel11', 'channel12', 'channel2', 'channel3', 'channel4', 'channel5', 'channel6', 'channel7', 'channel9']

## 4. Bandpower Contrast

- 0-100Hz: median_gain_dB={'2m30hz': 0.29, '2m50hz': 0.129}; support_rows={'2m30hz': 12, '2m50hz': 12}; lowfreq_reliable_all=True.
- 100Hz-1kHz: median_gain_dB={'2m30hz': 0.231, '2m50hz': 0.137}; support_rows={'2m30hz': 12, '2m50hz': 12}; lowfreq_reliable_all=True.
- 100kHz-200kHz: median_gain_dB={'2m30hz': 1.658, '2m50hz': 5.476}; support_rows={'2m30hz': 12, '2m50hz': 12}; lowfreq_reliable_all=True.
- 10kHz-50kHz: median_gain_dB={'2m30hz': 1.297, '2m50hz': 1.733}; support_rows={'2m30hz': 12, '2m50hz': 12}; lowfreq_reliable_all=True.
- 1kHz-10kHz: median_gain_dB={'2m30hz': 0.006, '2m50hz': 0.008}; support_rows={'2m30hz': 12, '2m50hz': 12}; lowfreq_reliable_all=True.
- 50Hz±2Hz: median_gain_dB={'2m30hz': 0.17, '2m50hz': 0.123}; support_rows={'2m30hz': 12, '2m50hz': 12}; lowfreq_reliable_all=False.
- 50kHz-100kHz: median_gain_dB={'2m30hz': 5.98, '2m50hz': 8.075}; support_rows={'2m30hz': 12, '2m50hz': 12}; lowfreq_reliable_all=True.
- 50kHz±1kHz: median_gain_dB={'2m30hz': 0.381, '2m50hz': 0.332}; support_rows={'2m30hz': 12, '2m50hz': 12}; lowfreq_reliable_all=True.
- 59.5kHz±1kHz: median_gain_dB={'2m30hz': 0.689, '2m50hz': 0.546}; support_rows={'2m30hz': 12, '2m50hz': 12}; lowfreq_reliable_all=True.
- 8.5kHz±300Hz: median_gain_dB={'2m30hz': 0.026, '2m50hz': 0.056}; support_rows={'2m30hz': 12, '2m50hz': 12}; lowfreq_reliable_all=True.

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

- channel1: 4 marked rows; examples=['59.5kHz±1kHz', '100Hz-1kHz', '50kHz±1kHz', '59.5kHz±1kHz'].
- channel10: 4 marked rows; examples=['50kHz±1kHz', '8.5kHz±300Hz', '50kHz±1kHz', '8.5kHz±300Hz'].
- channel11: 6 marked rows; examples=['1kHz-10kHz', '50kHz±1kHz', '8.5kHz±300Hz', '1kHz-10kHz', '50kHz±1kHz'].
- channel12: 2 marked rows; examples=['59.5kHz±1kHz', '59.5kHz±1kHz'].
- channel2: 3 marked rows; examples=['1kHz-10kHz', '8.5kHz±300Hz', '1kHz-10kHz'].
- channel3: 2 marked rows; examples=['50kHz±1kHz', '50kHz±1kHz'].
- channel4: 4 marked rows; examples=['59.5kHz±1kHz', '1kHz-10kHz', '59.5kHz±1kHz', '8.5kHz±300Hz'].
- channel5: 4 marked rows; examples=['50kHz±1kHz', '0-100Hz', '1kHz-10kHz', '50kHz±1kHz'].
- channel6: 2 marked rows; examples=['59.5kHz±1kHz', '8.5kHz±300Hz'].
- channel7: 3 marked rows; examples=['1kHz-10kHz', '59.5kHz±1kHz', '59.5kHz±1kHz'].
- channel9: 2 marked rows; examples=['8.5kHz±300Hz', '8.5kHz±300Hz'].
- Outliers are marked only; no rows were deleted.

## 10. Conclusions

Strong evidence:
- 2m30hz vs 2m0hz bandpower:0-100Hz support=12/12.
- 2m30hz vs 2m0hz bandpower:100Hz-1kHz support=12/12.
- 2m30hz vs 2m0hz bandpower:100kHz-200kHz support=12/12.
- 2m30hz vs 2m0hz bandpower:10kHz-50kHz support=12/12.
- 2m30hz vs 2m0hz bandpower:1kHz-10kHz support=12/12.
- 2m30hz vs 2m0hz bandpower:50Hz±2Hz support=12/12.
- 2m30hz vs 2m0hz bandpower:50kHz-100kHz support=12/12.
- 2m30hz vs 2m0hz bandpower:50kHz±1kHz support=12/12.
- 2m30hz vs 2m0hz bandpower:59.5kHz±1kHz support=12/12.
- 2m30hz vs 2m0hz bandpower:8.5kHz±300Hz support=12/12.

Moderate evidence:

Not supported:
- 2m30hz vs 2m0hz peak:10k_200kHz support=0/12.
- 2m30hz vs 2m0hz peak:1k_10kHz support=0/12.
- 2m50hz vs 2m0hz peak:10k_200kHz support=0/12.
- 2m50hz vs 2m0hz peak:1k_10kHz support=0/12.

## 11. Limitations

- Background and active groups were not synchronously acquired, so no raw waveform point-by-point subtraction was performed.
- Low-frequency 30/50/60Hz reliability depends on `df_hz` and `bin_count`.
- Observed differences cannot be directly attributed to water flow.
- Observed differences cannot be directly equated with the power-supply frequency itself.
- This remains feature-level background contrast, not physical source separation.
- PSD curves were adapter-generated as `psd_curve_level = group_median_recomputed`; p10/p90 in curve contrast are not file-level re-estimates.
