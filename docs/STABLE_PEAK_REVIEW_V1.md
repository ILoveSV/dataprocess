# Stable Peak Review v1

## Purpose

This step generates manual-review PSD plots for 0Hz backgrounds. The 0-200 kHz range is split into fixed 20 kHz windows so narrow, stable-looking peaks can be inspected visually across distance groups and channels.

## Scope

- Groups: 2m0hz, 3m0hz, 5m0hz only.
- Frequency windows: 0-20, 20-40, 40-60, 60-80, 80-100, 100-120, 120-140, 140-160, 160-180, 180-200 kHz.
- Plot unit: background median log PSD / PSD dB with p10-p90 band when available.
- No new peak detection or peak identification algorithm was added.
- No TDMS, FFT main pipeline, or background contrast formula was rerun.

## Inputs

- PSD source: `D:\Lab\results\26.5.12\background_contrast_v1\background_psd_diff_curves.csv`
- Raw rows used: 589824
- Deduplicated rows used for plotting: 294912
- Median frequency resolution: 24.4141 Hz

## Outputs

- Output directory: `analysis_out\stable_peak_review_v1`
- Plot count: 360
- Groups covered: 2m0hz, 3m0hz, 5m0hz
- Channels covered: channel1, channel2, channel3, channel4, channel5, channel6, channel7, channel8, channel9, channel10, channel11, channel12
- Index CSV: `stable_peak_review_index_v1.csv`
- Coarse visual-navigation summary: `stable_peak_review_coarse_summary_v1.csv`

## Manual Review Guidance

- Start with windows that previously looked relevant: 40-60 kHz, 120-140 kHz, 160-180 kHz, and 180-200 kHz.
- Compare the same channel and same 20 kHz window across 2m0hz, 3m0hz, and 5m0hz.
- Treat channel9 in 5m and channel5 as QC-sensitive while reviewing; this plot set does not mask them out.
- Use the coarse max table only as a navigation aid. It is not a peak detector and should not replace visual confirmation.

## Next Step

After manual review, confirmed stable narrow peak candidates can be specified explicitly for a later feature extraction or validation step.
