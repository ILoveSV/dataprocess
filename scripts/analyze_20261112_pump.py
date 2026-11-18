"""Cross-date TC2 replay with fixed channels and operator-provided nominal timing."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from analyze_20261111_pump import IDS, STAGES, db
from coherence_20261111_pump import process
from extract_20261111_pump import BANDS, OUT as OLD, extract

OUT = OLD.parent / "20261112_pump"
RAW = Path("D:/Lab/raw/raw/11.12")
COMMON = (1, 2, 3, 4, 9, 10)
CASES = {
    "4m1": (125, [(15, "RUN50"), (45, "STOP"), (70, "RUN50"), (90, "RUN30"), (115, "STOP")]),
    "3m1": (125, [(25, "RUN50"), (50, "RUN30"), (90, "RUN50")]),
    "2m1": (130, [(15, "RUN50"), (30, "RUN30"), (45, "RUN50"), (55, "RUN30"),
                  (70, "RUN50"), (82, "RUN30"), (100, "RUN50"), (110, "RUN30")]),
}
NAMES = {"off": "STOP", "30Hz": "RUN30", "50Hz": "RUN50"}
GROUPS = {
    "coherence": ["coh"],
    "carrier_ch8": ["ch8_4000", "ch8_8000", "ch8_12000"],
    "fusion": ["coh", "ch8_4000", "ch8_8000", "ch8_12000"],
    "common_bandpower": list(BANDS)[3:8],
}


def load(root, case):
    p = root / "cache" / case
    meta = json.loads((p / "metadata.json").read_text(encoding="utf-8"))
    with np.load(p / "features.npz") as z:
        epochs = z["epoch_psd"]
        counts = z["epoch_counts"]
        spec = np.stack([epochs[:, 7, f-2:f+3].sum(axis=1) for f in (4000, 8000, 12000)], axis=1)
        bp = z["bandpower"]
    return meta, spec[counts == 5], bp


def inputs(root, case, coh, reference=None, channels=COMMON):
    meta, spec, bp = load(root, case)
    p = coh[(coh.case == case) & coh.ch1.isin(channels) & coh.ch2.isin(channels)]
    x = p.groupby("epoch_start_s").median_coherence.median().to_frame("coh")
    n = len(x)
    assert len(spec) == n == len(bp) // 5
    for i, f in enumerate((4000, 8000, 12000)):
        x[f"ch8_{f}"] = spec[:, i]
    for i, name in enumerate(BANDS):
        if name in GROUPS["common_bandpower"]:
            x[name] = np.median(np.mean(bp[:n*5, :, i].reshape(n, 5, 12), axis=1)
                                [:, np.array(channels)-1], axis=1)
    # Both calibration blocks precede the earliest commanded transition.
    ref = x.loc[[5, 10]].median() if reference is None else reference
    y = x.astype("float64")
    y["coh"] -= ref["coh"]
    y.loc[:, y.columns != "coh"] = db(x.loc[:, x.columns != "coh"], ref[x.columns != "coh"])
    return meta, x, y, ref


def state_windows(times, duration, events, guard=0):
    intervals = []
    start, state = 0, "STOP"
    for t, target in events:
        intervals.append((start, t, state))
        intervals.append((t, t+10, "TRANSITION"))
        start, state = t+10, target
    intervals.append((start, duration, state))
    labels = pd.Series("UNSCORED", index=times)
    for a, b, s in intervals:
        k = guard if s != "TRANSITION" and a else 0
        labels.loc[(times >= a+k) & (times+5 <= b)] = s
    return labels, intervals


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw", default=RAW, type=Path)
    p.add_argument("--out", default=OUT, type=Path)
    p.add_argument("--reuse-pairs", action="store_true")
    p.add_argument("--channels", nargs="+", type=int, default=COMMON)
    a = p.parse_args()
    cases = [*CASES, "back2", "back3", "back4"]
    pairfile = a.out / "coherence_pairs_5s.csv"
    if not a.reuse_pairs:
        rows = []
        for case in cases:
            path, = (a.raw / case).glob("*.tdms")
            target = a.out / "cache" / case
            if not (target / "metadata.json").exists():
                extract(path, target)
            rows.extend(process(case, path, a.out, fixed_channels=np.array(COMMON)-1))
        pd.DataFrame(rows).to_csv(pairfile, index=False)
    new = pd.read_csv(pairfile)
    old = pd.read_csv(OLD / "coherence_pairs_5s.csv")
    def pairs(x):
        return x[x.ch1.isin(COMMON) & x.ch2.isin(COMMON) & x.band.eq("80000_199900")]
    old, new = pairs(old), pairs(new)
    xx, yy = [], []
    for case in IDS:
        meta0, _, x, _ = inputs(OLD, case, old, channels=a.channels)
        labels = pd.Series("UNSCORED", index=x.index)
        for i, state in enumerate(STAGES["-" in case]):
            labels.loc[[i*30+5, i*30+10, i*30+15]] = NAMES[state]
        xx.append(x)
        yy.append(labels)
    X, Y = pd.concat(xx), pd.concat(yy)
    models = {}
    for name, columns in GROUPS.items():
        for task in ("binary", "speed"):
            k = Y.isin(["RUN30", "RUN50"]) if task == "speed" else Y.ne("UNSCORED")
            y = Y[k] if task == "speed" else Y[k].replace({"RUN30": "RUN", "RUN50": "RUN"})
            models[name, task] = make_pipeline(StandardScaler(), LogisticRegression(
                C=.1, class_weight="balanced")).fit(X.loc[k.to_numpy(), columns], y.to_numpy())
    rows, summaries, inventory, label_rows, events_out, stop_runs = [], [], [], [], [], []
    for case in cases:
        meta, raw, x, _ = inputs(a.out, case, new, channels=a.channels)
        if meta["channels"] != meta0["channels"]:
            raise ValueError(f"Historical channel map does not match {case}")
        t = x.index.to_numpy()
        inventory.append(dict(case=case, source=meta["source"], duration_s=meta["duration_s"],
                              full_blocks=len(t), detector="TC2",
                              role="scheduled" if case in CASES else "powered_stop",
                              suspect=";".join(str(h["channel_index"]) for h in meta["health"]
                                               if h["automatic_suspect"])))
        if case in CASES:
            duration, events = CASES[case]
            labels, intervals = state_windows(t, duration, events)
            guarded, _ = state_windows(t, duration, events, guard=2)
            for start, end, s in intervals:
                if start < meta["duration_s"] and end > start:
                    label_rows.append(dict(case=case, start_s=start, end_s=min(end, meta["duration_s"]),
                                           state=s, source="operator_times_plus_10s"))
        else:
            events = []
            labels = guarded = pd.Series("STOP", index=t)
            label_rows.append(dict(case=case, start_s=0, end_s=meta["duration_s"],
                                   state="STOP", source="operator_confirmed_vfd_powered"))
        for (name, task), m in models.items():
            pr = m.predict_proba(x[GROUPS[name]])
            output = m.classes_[pr.argmax(axis=1)].copy()
            output[t < 15] = "CAL"
            truth = labels if task == "speed" else labels.replace({"RUN30": "RUN", "RUN50": "RUN"})
            use = (t >= 15) & truth.isin(m.classes_).to_numpy()
            use_guard = use & guarded.eq(labels).to_numpy()
            for mode, score in (("nominal", use), ("guard2", use_guard)):
                for s in m.classes_:
                    match = score & truth.eq(s).to_numpy()
                    summaries.append(dict(case=case, model=name, task=task, mask=mode, state=s,
                                          n=int(match.sum()), correct=int((match & (output == s)).sum())))
            for i, k in enumerate(t):
                rows.append(dict(case=case, model=name, task=task, start_s=k, end_s=k+5,
                                 expected=labels.iloc[i], predicted=output[i], scored=use[i],
                                 scored_guard2=use_guard[i],
                                 speed_change=any(j and v!="STOP" and events[j-1][1]!="STOP"
                                                  and k<b+10 and k+5>b
                                                  for j,(b,v) in enumerate(events)),
                                 **{f"score_{s}": pr[i,j] for j,s in enumerate(m.classes_)}))
            if task == "binary" and case in CASES:
                before = "STOP"
                for j, (command, after) in enumerate(events):
                    target = "STOP" if after == "STOP" else "RUN"
                    limit = events[j+1][0] if j+1 < len(events) else min(duration, meta["duration_s"])
                    take = (t+5 > command) & (t+5 <= limit)
                    whole = (t >= command+10) & take
                    if target != before:
                        hit = t[take & (output == target)] + 5
                        stable_hit = t[whole & (output == target)] + 5
                        events_out.append(dict(case=case, model=name, command_s=command, target=target,
                                               planned_stable_s=command+10, end_limit_s=limit,
                                               first_target_end_s=hit[0] if len(hit) else None,
                                               first_stable_target_end_s=stable_hit[0] if len(stable_hit) else None,
                                               stable_windows=int(whole.sum())))
                    before = target
            if task == "binary" and case not in CASES:
                # Also replay background against the independently scheduled same-distance STOP.
                _, _, _, local_stop = inputs(a.out, case[-1]+"m1", new, channels=a.channels)
                _, _, same_x, _ = inputs(a.out, case, new, reference=local_stop, channels=a.channels)
                pred = m.predict(same_x[GROUPS[name]])
                summaries.append(dict(case=case, model=name, task=task, mask="back_vs_initial_stop",
                                      state="RUN_flag", n=len(pred), correct=int((pred=="RUN").sum())))
                summaries.append(dict(case=case, model=name, task=task, mask="back_self_calibrated",
                                      state="RUN_flag", n=int((t>=15).sum()),
                                      correct=int(((t>=15)&(output=="RUN")).sum())))
                for reference, mask in (("back_vs_initial_stop", pred == "RUN"),
                                        ("back_self_calibrated", (t >= 15) & (output == "RUN"))):
                    starts = np.flatnonzero(mask & ~np.r_[False, mask[:-1]])
                    ends = np.flatnonzero(mask & ~np.r_[mask[1:], False])
                    for first, last in zip(starts, ends):
                        stop_runs.append(dict(case=case, model=name, reference=reference,
                                              start_s=t[first], end_s=t[last]+5,
                                              windows=last-first+1))
        raw.to_csv(a.out / f"{case}_features_5s.csv")
    frame = pd.DataFrame(rows)
    suffix = "" if tuple(a.channels) == COMMON else "_channels_" + "_".join(map(str, a.channels))
    for name, z in [("predictions_5s", frame), ("scores", pd.DataFrame(summaries)),
                    ("inventory", pd.DataFrame(inventory)), ("state_intervals", pd.DataFrame(label_rows)),
                    ("event_candidates", pd.DataFrame(events_out)),
                    ("stop_false_run_streaks", pd.DataFrame(stop_runs))]:
        z.to_csv(a.out / f"{name}{suffix}.csv", index=False)
    fig, axes = plt.subplots(3, 1, figsize=(12, 7), sharex=True)
    for case, ax in zip(CASES, axes):
        duration, events = CASES[case]
        _, intervals = state_windows(np.arange(0, duration, 5), duration, events)
        for start, end, s in intervals:
            ax.axvspan(start, end, color={"STOP": "#888888", "RUN50": "#c97942",
                                       "RUN30": "#2c8b72", "TRANSITION": "#d2caca"}[s], alpha=.15)
        z = frame[(frame.case == case) & (frame.task == "binary") & frame.predicted.ne("CAL")]
        for name, group in z.groupby("model"):
            ax.plot(group.end_s, group.score_RUN, marker=".", label=name, lw=1)
        ax.axhline(.5, ls="--", lw=.7, color="gray")
        ax.set_ylabel(case + " RUN")
        ax.set_ylim(-.04, 1.04)
    axes[0].legend(ncol=4, fontsize=8)
    axes[-1].set_xlabel("Window end (s); only data up to this point used")
    fig.tight_layout()
    fig.savefig(a.out / f"cross_date_replay{suffix}.png", dpi=160)


if __name__ == "__main__":
    main()
