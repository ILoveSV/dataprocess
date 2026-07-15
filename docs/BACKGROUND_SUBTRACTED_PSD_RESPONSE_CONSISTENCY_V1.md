# Background-Subtracted PSD Response Consistency v1

## Purpose

Zero-state backgrounds may vary across distance. This analysis therefore does not require 2m0Hz, 3m0Hz, and 5m0Hz to be identical. Instead it checks whether active PSD response relative to each same-distance 0Hz background has repeatable structure across distances.

## Scope

- PSD/frequency features only.
- Active conditions: 30Hz-0Hz and 50Hz-0Hz.
- Distance sets are reported separately: 2m/3m and 2m/3m/5m.
- Masks compared: mask_all, mask_no_ch9_global, mask_no_ch9_ch5_global.
- No 50Hz-30Hz or pump-net contrast was computed.
- No machine learning, TDMS rerun, FFT rerun, or background-contrast formula change.

## Response Definition

For feature-level tables, response is active group median PSD feature minus same-distance 0Hz background median PSD feature. Existing frequency features are in dB-like bandpower units, so response is reported as dB feature difference. Review curves use existing `psd_gain_dB` from background contrast outputs.

## Outputs

- Feature response rows: 270
- Consistency rows: 180
- Review plots: 120
- Candidate category counts: {'reject_or_unclear': 35, 'robust_2m3m5m_candidate': 35, 'distance_dependent_response': 12, 'robust_2m3m_candidate': 6, 'channel_risk_response': 1, '2m3m_only_candidate_due_to_weak_5m': 1}

## Main-Mask Consistency Snapshot

- `mask_no_ch9_global` consistency counts:
  - 30Hz_minus_0Hz / 2m3m / inconsistent: 2
  - 30Hz_minus_0Hz / 2m3m / moderate: 2
  - 30Hz_minus_0Hz / 2m3m / strong: 4
  - 30Hz_minus_0Hz / 2m3m / weak: 7
  - 30Hz_minus_0Hz / 2m3m5m / inconsistent: 3
  - 30Hz_minus_0Hz / 2m3m5m / moderate: 2
  - 30Hz_minus_0Hz / 2m3m5m / strong: 3
  - 30Hz_minus_0Hz / 2m3m5m / weak: 7
  - 50Hz_minus_0Hz / 2m3m / inconsistent: 3
  - 50Hz_minus_0Hz / 2m3m / moderate: 4
  - 50Hz_minus_0Hz / 2m3m / strong: 4
  - 50Hz_minus_0Hz / 2m3m / weak: 4
  - 50Hz_minus_0Hz / 2m3m5m / inconsistent: 4
  - 50Hz_minus_0Hz / 2m3m5m / moderate: 3
  - 50Hz_minus_0Hz / 2m3m5m / strong: 3
  - 50Hz_minus_0Hz / 2m3m5m / weak: 5

## 5m Weak-Signal Note

2m/3m and 2m/3m/5m are intentionally separated. Features that are consistent in 2m/3m but weaken or become near-zero at 5m are marked separately rather than mixed into the same conclusion.

## Channel Mask Effect

- Mask-sensitive response rows: 46
- channel9/channel5 masks are current pilot QC checks, not permanent channel rules.

## Review Figures

Segmented response overlays are under `review_figures/`. For each active condition, mask, and distance set, 0-200 kHz is split into 20 kHz windows for manual comparison of response shape and narrow peaks.

## Interpretation Guard

Current outputs are PSD response consistency screens. They are not ML results and not final scientific conclusions. Stable response candidates can be used later for focused feature screening or manual peak review.
