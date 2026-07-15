# PSD Response Montage Review v1

## Purpose

This review artifact rearranges the latest per-channel first39 background-subtracted PSD response PNGs into larger montage figures for manual inspection of repeated response frequencies.

## Scope

- Active conditions: 30Hz_minus_0Hz and 50Hz_minus_0Hz.
- Distance sets: 2m3m and 2m3m5m.
- Frequency coverage: 0-200 kHz split into 10 fixed 20 kHz windows.
- Montage types: by_window and by_channel.
- Source: existing per-channel PSD response figures; no TDMS, FFT, background contrast, peak detection, ML, or new science conclusion.

## Outputs

- Output directory: `analysis_out\psd_response_montage_review_v1`
- Montage count by type: {'by_channel': 48, 'by_window': 40}
- `montage_by_window/`: one figure per active condition, distance set, and 20 kHz window; each figure contains all 12 channels.
- `montage_by_channel/`: one figure per channel, active condition, and distance set; each figure contains all 10 frequency windows.
- `figure_index_v1.csv`: lookup table for all montage figures.

## Channel Notes

- channel9 is marked BAD according to current pilot QC context.
- channel5 is marked SUSPECT according to current pilot QC context.
- These labels are review annotations, not permanent channel rules.

## Suggested Manual Review Order

- Start with `montage_by_window` for 40-60 kHz, 120-140 kHz, 160-180 kHz, and 180-200 kHz.
- Compare 2m3m first, then check whether the same structure remains in 2m3m5m.
- Use `montage_by_channel` after spotting a candidate frequency band to inspect one channel across all windows.
