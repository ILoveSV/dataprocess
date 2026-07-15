# Background-Subtracted PSD Response Consistency Per-Channel v1

## Purpose

This is the per-channel companion to the channel-aggregated PSD response consistency analysis. It checks each channel separately so narrow response structures are not hidden by across-channel median aggregation.

## Scope

- PSD/frequency features only.
- Active conditions: 30Hz-0Hz and 50Hz-0Hz.
- Distance sets: 2m/3m and 2m/3m/5m.
- Channel mode: each channel is analyzed separately; no channel aggregation or mask aggregation is applied.
- No 50Hz-30Hz, no pump-net contrast, no ML, no TDMS/FFT rerun, and no background contrast formula change.

## Outputs

- Feature response rows: 1080
- Consistency rows: 720
- Review plots: 480
- Candidate category counts: {'reject_or_unclear': 258, 'robust_2m3m5m_candidate': 72, 'distance_dependent_response': 21, '2m3m_only_candidate_due_to_weak_5m': 5, 'robust_2m3m_candidate': 4}

## Consistency Snapshot

- 30Hz_minus_0Hz / 2m3m / inconsistent: 6
- 30Hz_minus_0Hz / 2m3m / moderate: 20
- 30Hz_minus_0Hz / 2m3m / strong: 16
- 30Hz_minus_0Hz / 2m3m / weak: 138
- 30Hz_minus_0Hz / 2m3m5m / inconsistent: 8
- 30Hz_minus_0Hz / 2m3m5m / moderate: 23
- 30Hz_minus_0Hz / 2m3m5m / strong: 15
- 30Hz_minus_0Hz / 2m3m5m / weak: 134
- 50Hz_minus_0Hz / 2m3m / inconsistent: 13
- 50Hz_minus_0Hz / 2m3m / moderate: 26
- 50Hz_minus_0Hz / 2m3m / strong: 19
- 50Hz_minus_0Hz / 2m3m / weak: 122
- 50Hz_minus_0Hz / 2m3m5m / inconsistent: 17
- 50Hz_minus_0Hz / 2m3m5m / moderate: 26
- 50Hz_minus_0Hz / 2m3m5m / strong: 15
- 50Hz_minus_0Hz / 2m3m5m / weak: 122

## Channels With More Strong/Moderate PSD Responses

- 50Hz_minus_0Hz / 2m3m / channel5: strong=7, moderate=2, weak=5, inconsistent=1
- 30Hz_minus_0Hz / 2m3m / channel5: strong=5, moderate=2, weak=8, inconsistent=0
- 50Hz_minus_0Hz / 2m3m5m / channel5: strong=4, moderate=4, weak=6, inconsistent=1
- 30Hz_minus_0Hz / 2m3m5m / channel9: strong=4, moderate=1, weak=9, inconsistent=1
- 30Hz_minus_0Hz / 2m3m5m / channel5: strong=3, moderate=4, weak=8, inconsistent=0
- 50Hz_minus_0Hz / 2m3m / channel10: strong=3, moderate=2, weak=9, inconsistent=1
- 30Hz_minus_0Hz / 2m3m / channel10: strong=3, moderate=1, weak=11, inconsistent=0
- 50Hz_minus_0Hz / 2m3m5m / channel10: strong=3, moderate=1, weak=9, inconsistent=2
- 50Hz_minus_0Hz / 2m3m / channel9: strong=3, moderate=0, weak=12, inconsistent=0
- 30Hz_minus_0Hz / 2m3m / channel2: strong=2, moderate=4, weak=9, inconsistent=0
- 30Hz_minus_0Hz / 2m3m5m / channel2: strong=2, moderate=4, weak=9, inconsistent=0
- 30Hz_minus_0Hz / 2m3m / channel1: strong=2, moderate=2, weak=11, inconsistent=0

## Review Figures

Per-channel segmented overlays are under `review_figures/<channel>/<active_condition>/<distance_set>/`. Each plot covers one 20 kHz window from 0-200 kHz.

## Interpretation Guard

This output is for per-channel PSD response consistency screening and manual review. It is not an ML result and not a final scientific conclusion. channel9/channel5 notes are current pilot QC context, not permanent channel rules.
