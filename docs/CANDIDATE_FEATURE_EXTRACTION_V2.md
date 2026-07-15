# Candidate Feature Extraction v2

## Scope

- Generated file-level/channel-level candidate features from FFT CSV files.
- Did not run machine learning.
- Did not modify background contrast formulas.
- Did not rerun TDMS conversion or FFT export.

## Inputs

- FFT root: `D:\Lab\process\26.5.12\frequency`
- Background output: `D:\Lab\results\26.5.12\background_contrast_v1`
- FFT audit: `D:\Lab\results\26.5.12\background_contrast_v1\fft_group_input_audit.csv`

## Feature Definition

- For each FFT file, channel, and candidate frequency window, the feature is `10*log10(sum(amplitude^2 * df_hz) + EPS)`.
- This is a file-level frequency-domain integrated amplitude-power feature, not a reused group-median PSD zoom value.
- Rows preserve `file_id` and `channel` dimensions.

## Modes

- all-data mode file count: 351
- strict mode file count: 351
- strict mode excludes 9 frequency-axis risk files.

Frequency-axis risk files:
- `FFT_20260512075157.173184.csv`
- `FFT_20260512075451.773184.csv`
- `FFT_20260512075745.273184.csv`
- `FFT_20260512080301.670775.csv`
- `FFT_20260512080945.424857.csv`
- `FFT_20260512081411.848005.csv`
- `FFT_20260512081755.548005.csv`
- `FFT_20260512082129.448005.csv`
- `FFT_20260512082414.544907.csv`

## Extracted Features

- `band_50_100k` (bandpower, 50000-100000 Hz)
- `band_100_200k` (bandpower, 100000-200000 Hz)
- `subband_50_60k` (subband, 50000-60000 Hz)
- `subband_60_70k` (subband, 60000-70000 Hz)
- `subband_70_80k` (subband, 70000-80000 Hz)
- `subband_80_90k` (subband, 80000-90000 Hz)
- `subband_90_100k` (subband, 90000-100000 Hz)
- `subband_100_120k` (subband, 100000-120000 Hz)
- `subband_120_140k` (subband, 120000-140000 Hz)
- `subband_140_160k` (subband, 140000-160000 Hz)
- `subband_160_180k` (subband, 160000-180000 Hz)
- `subband_180_200k` (subband, 180000-200000 Hz)
- `peakwin_53p5_55k` (peak_window, 53500-55000 Hz)
- `peakwin_137_139p5k` (peak_window, 137000-139500 Hz)
- `peakwin_177_179k` (peak_window, 177000-179000 Hz)

## Stability

- `stable_file_ratio` is the fraction of file values inside `[Q1 - 1.5*IQR, Q3 + 1.5*IQR]` for each group/feature/channel.
- `outlier_file_count` is the number of files outside that interval.

Top strict-mode stable rows:
- `5m50hz channel9 subband_90_100k`: stable_file_ratio=1, median=-48.6
- `2m0hz channel1 band_100_200k`: stable_file_ratio=1, median=-62.1
- `5m50hz channel2 subband_80_90k`: stable_file_ratio=1, median=-68.7
- `5m50hz channel11 subband_80_90k`: stable_file_ratio=1, median=-71.1
- `5m50hz channel1 subband_80_90k`: stable_file_ratio=1, median=-69.5
- `5m50hz channel9 subband_70_80k`: stable_file_ratio=1, median=-47.2
- `5m50hz channel8 subband_70_80k`: stable_file_ratio=1, median=-70.4
- `5m50hz channel6 subband_70_80k`: stable_file_ratio=1, median=-70.6
- `5m50hz channel5 subband_70_80k`: stable_file_ratio=1, median=-65.8
- `5m50hz channel4 subband_70_80k`: stable_file_ratio=1, median=-70

## All-data vs strict-mode

- Rows with median shift > 0.5 dB after strict exclusion: 0
- See `all_vs_strict_feature_delta_v2.csv` for per group/feature/channel deltas.

## ML Readiness

- This output is suitable as a candidate feature table input for later validation or ML dataset construction.
- Because frequency-axis-risk files exist, downstream ML should either use strict mode or include `qc_flag`/`analysis_mode` as filtering metadata.
- No feature is promoted here as a physical mechanism.
