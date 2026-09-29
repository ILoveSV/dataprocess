# Input Consistency Summary

Analysis mode: `all-data mode with risk reporting only`
Strict mode: `False`

## Used files

- `D:\Lab\results\26.5.12\background_contrast_v1\background_psd_diff_curves.csv`
- `D:\Lab\results\26.5.12\background_contrast_v1\background_bandpower_contrast.xlsx`
- `D:\Lab\results\26.5.12\background_contrast_v1\cross_channel_background_contrast.xlsx`
- `D:\Lab\results\26.5.12\background_contrast_v1\pumpfreq_net_contrast.xlsx`
- `D:\Lab\results\26.5.12\background_contrast_v1\psd_zoom\psd_zoom_summary.csv`
- `D:\Lab\results\26.5.12\background_contrast_v1\psd_zoom\psd_zoom_feature_summary.csv`
- `D:\Lab\results\26.5.12\background_contrast_v1\psd_zoom\psd_zoom_input_audit.json`

## Frequency-axis risk

- Warning file count: 9
- `FFT_20260512075157.173184.csv`
- `FFT_20260512075451.773184.csv`
- `FFT_20260512075745.273184.csv`
- `FFT_20260512080301.670775.csv`
- `FFT_20260512080945.424857.csv`
- `FFT_20260512081411.848005.csv`
- `FFT_20260512081755.548005.csv`
- `FFT_20260512082129.448005.csv`
- `FFT_20260512082414.544907.csv`

## Impact

- psd_zoom: Affected because PSD zoom reuses already aggregated PSD curves derived from the full input set.
- peak_stability: Affected because peak windows are evaluated on the same aggregated PSD curves.
- subband_scan: Affected because subband summaries reuse PSD zoom curve values.
- file_level_stability: Cannot be safely evaluated from current aggregated outputs.
