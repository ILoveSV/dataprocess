# 2026-11-12 TC2 pump recognition

## Records and labels

TC2, 12 channels at 400 kSa/s; three scheduled recordings and three background
candidates. Actual durations: 2 m 130.392 s, 3 m 121.688 s, 4 m 125.733 s.
The operator supplied command times and a 10 s settling allowance. Initial RUN
is taken as RUN50. These are operator labels, not synchronized device logs.
Score only complete nonoverlapping 5 s windows within nominal steady states.
The first 15 s are reserved for calibration; the baseline uses 5–15 s.
This leaves no scored steady STOP at 2 m. The final 4 m STOP at 125 s has
less than a full window. At 2 m the 45→55 and 100→110 s commands leave no
steady RUN50 gap, and the 80→82 s stable gap cannot fill a 5 s window.
The operator confirmed back2/back3/back4 are VFD-powered pump STOP throughout.
They contribute 72 scored STOP windows after the same 15 s self-calibration
as scheduled recordings. The five scored scheduled STOP windows are included.
Power-on alone without running is not reliably distinguishable from pure
background in the earlier experiments and is not a target class here.

## Cross-date replay

Train logistic regressions only on the seven November 11 recordings using
the three previously used stable 5 s blocks per stage. Test all November 12
records without retraining or choosing thresholds on them. Models use the
current 5 s window and initial baseline; no schedule/distance feature.
The CH8 features here use a mean of five one-second PSDs, not the exact
previous median-power feature, and this is not an already-deployed model.
The same six channels (1,2,3,4,9,10) are fixed in advance from November 11
for the primary result. A post-hoc common clean subset (1,3,9) checks
sensitivity to new suspect channels; it is not a blind score.

| Model | RUN | STOP | Pooled balanced accuracy |
|---|---:|---:|---:|
| 80–200 kHz coherence | 25/28 | 35/77 | 67.4% |
| CH8 carrier lines | 13/28 | 76/77 | 72.6% |
| Fusion | 16/28 | 76/77 | 77.9% |
| Common-channel band power | 4/28 | 15/77 | 16.9% |

These are pooled per-window recalls and their mean, not independent events
or deployment accuracy. The previous 5-STOP-window table omitted the three
now-confirmed STOP files and is superseded. No model was retrained on them.

Coherence only: 2 m RUN 6/6, 3 m RUN 12/13 and STOP 0/2, 4 m RUN 7/9
and STOP 3/3. At 3 m the windows ending at 20 and 25 s were already called
RUN before the planned 25 s command, so the following RUN cannot count as
a clean detected startup. At 4 m the stops/starts are visible but the
windows ending at 45 and 115 s drop to STOP prematurely. The final 125 s
STOP decision is based on a transition window, not a steady STOP test.

Across planned speed changes without a stop, coherence stayed RUN on
21/21 overlapping windows; fusion stayed RUN on 19/21, calling STOP in
both 4 m ramp windows ending 95 and 100 s. The 21 windows are correlated,
not independent events. Conditional speed classification with true RUN
provided by the labels: coherence and fusion each 20/28, but fusion
RUN30 7/14 vs RUN50 13/14; not end-to-end three-state recognition.
The two-second guard and three-channel audit are reported separately.

## Observable features and background

The CH8 4 kHz band RMS medians (steady blocks, including initial STOP) in
uV are: 2 m STOP/50/30 = 11.4/128.1/329.6; 3 m = 11.5/26.5/71.8;
4 m = 9.7/11.5/18.1. 2 m RUN50 has only one complete window. CH8 and
CH11 are suspect throughout; additional suspects are CH10 at 2 m, CH2
at 4 m and CH4 in back4. CH8 is reported separately as a state feature.

With self-calibration, coherence misclassified 40/72 held-out powered-STOP
windows. These form 10 continuous false RUN streaks, the longest 95 s.
Using the separate same-distance scheduled STOP reference instead,
coherence misclassified 40/81 windows in four streaks, the longest 100 s.
Fusion gave zero flags on these three files under either reference, but
missed 12/28 RUN windows and falsely reported STOP on two 4 m ramp windows.
The long coherence streaks show why short consecutive-window confirmation
alone would not solve its STOP false alarms. The alternative reference
counts are diagnostic and not pooled into the primary score.

## Reproduction and outputs

Run `python -B scripts/analyze_20261112_pump.py` from the repository root
for raw extraction and scoring, or pass `--reuse-pairs` to rerun cached
scoring. `--reuse-pairs --channels 1 3 9` reproduces the sensitivity run.
See [timeline](cross_date_replay.png), [inventory](inventory.csv),
[nominal intervals](state_intervals.csv), [scores](scores.csv),
[all window outputs](predictions_5s.csv) and
[first target-class windows](event_candidates.csv), and
[continuous false RUN streaks](stop_false_run_streaks.csv). The first
target-class table lists
candidate confirmations, not validated transition detections or latencies.
