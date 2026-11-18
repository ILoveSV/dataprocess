"""Native-rate all-pair coherence for contiguous five-second pump epochs."""

import argparse
import json
from itertools import combinations

import numpy as np
import pandas as pd
from nptdms import TdmsFile
from scipy import fft, signal
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from extract_20261111_pump import FS, OUT, RAW, inventory

SIZE = FS // 4
WINDOWS = 20
BANDS = ((4, 100), (100, 1000), (1000, 20000), (20000, 80000), (80000, 199900))
F = fft.rfftfreq(SIZE, 1 / FS)
F_SLICES = [slice(np.searchsorted(F, lo), np.searchsorted(F, hi)) for lo, hi in BANDS]
WIN = signal.windows.hann(SIZE, sym=False).astype("float32")


def cross_metrics(z):
    pair_power = np.sum(np.abs(z)**2, axis=0)
    pairs = []
    for i, j in combinations(range(z.shape[1]), 2):
        cross = np.sum(z[:, i] * np.conj(z[:, j]), axis=0)
        power = pair_power[i] * pair_power[j]
        coherence = np.clip(np.abs(cross)**2 / np.maximum(power, 1e-30), 0.0, 1.0)
        pairs.append((i, j, [float(np.median(coherence[s])) for s in F_SLICES]))
    return pairs


def process(case, path, target, fixed_channels=None):
    meta = json.loads((target / "cache" / case / "metadata.json").read_text(encoding="utf-8"))
    keep = (np.asarray(fixed_channels, dtype=int) if fixed_channels is not None else
            np.array([j for j, r in enumerate(meta["health"]) if not r["automatic_suspect"]]))
    seen = 0
    carry = np.empty((len(keep), 0))
    samples = None
    acc = []
    results = []
    count = 0

    def consume(body):
        nonlocal count
        x = body.astype("float32")
        acc.append(fft.rfft((x - x.mean(axis=1, keepdims=True)) * WIN, axis=1, workers=2))
        if len(acc) != WINDOWS:
            return
        z = np.stack(acc)
        for i, j, m in cross_metrics(z):
            for (lo, hi), v in zip(BANDS, m):
                results.append(dict(case=case, epoch_start_s=count*5, epoch_end_s=count*5+5,
                                    ch1=int(keep[i]+1), ch2=int(keep[j]+1),
                                    band=f"{lo}_{hi}", median_coherence=v))
        count += 1
        acc.clear()

    with TdmsFile.open(path) as td:
        group, = td.groups()
        names = [ch.name for ch in group.channels()]
        assert names == meta["channels"]
        for chunk in td.data_chunks():
            cc = chunk[group.name].channels()
            if not cc or not len(cc[0]):
                continue
            if any(int(cc[i].offset) != seen for i in keep):
                raise ValueError(f"Stream discontinuity: {case}")
            x = np.stack([cc[i][:] for i in keep])
            seen += x.shape[1]
            if samples is None:
                samples = x[:, :1].copy()
            x -= samples
            if not np.isfinite(x).all():
                raise ValueError(f"Unexpected nonfinite retained channel: {case}")
            carry = np.concatenate((carry, x), axis=1)
            use = carry.shape[1] // SIZE
            for j in range(use):
                consume(carry[:, j*SIZE:(j+1)*SIZE])
            if use:
                carry = carry[:, use*SIZE:].copy()
    assert seen == meta["sample_count"]
    assert count == seen // (5*FS)
    print(f"{case}: {count} full 5 s epochs, {len(keep)} channels", flush=True)
    return results


def classify(frame, out):
    rows, scores = [], []
    certain = {"2", "3", "4", "3-2_late"}
    common = set.intersection(*[set(z.ch1) | set(z.ch2) for _, z in frame.groupby("case")])
    have_lines = all((out / "cache" / c / "carrier_lines.npz").exists() for c in frame.case.unique())
    for name, f in [("per_file", frame), ("common", frame[
            frame.ch1.isin(common) & frame.ch2.isin(common)])]:
        q = f.groupby(["case", "epoch_start_s", "band"]).median_coherence.median().unstack()
        cases = {}
        for case, z in q.groupby(level=0):
            a = z.reset_index(level=0, drop=True)
            x = a - a.loc[[5, 10, 15]].median()
            if have_lines:
                with np.load(out / "cache" / case / "carrier_lines.npz") as lines:
                    power = lines["power"]
                    frequencies = lines["frequencies"].tolist()
                    for center in (4000, 8000, 12000):
                        v = power[:, 7, frequencies.index(center)]
                        baseline = np.median(v[5:15])
                        x[f"ch8_{center}"] = [10*np.log10(np.median(v[t:t+5])/baseline) for t in x.index]
            y = pd.Series("excluded", index=x.index)
            states = ("off", "50Hz", "off", "50Hz") if "-" in case else ("off", "50Hz", "30Hz", "off")
            for i, s in enumerate(states):
                y.loc[[30*i+5, 30*i+10, 30*i+15]] = s
            cases[case] = (x, y)
        sets = [("80_200k", ["80000_199900"]), ("all_bands", list(q.columns))]
        if have_lines:
            line_names = [f"ch8_{k}" for k in (4000, 8000, 12000)]
            sets.extend([("ch8_lines", line_names), ("80_200k_and_ch8", ["80000_199900", *line_names])])
        for task in ("binary", "speed", "three"):
            for group, features in sets:
                for test, (x, y) in cases.items():
                    if task in ("speed", "three") and "-" in test:
                        continue
                    for rule in ("all", "certain", "cross_protocol"):
                        if rule == "certain" and test not in certain:
                            continue
                        xs, ys = [], []
                        for case, (v, s) in cases.items():
                            if case == test or (rule == "certain" and case not in certain) or (
                                    rule == "cross_protocol" and ("-" in case) == ("-" in test)):
                                continue
                            m = s.isin(["30Hz", "50Hz"]) if task == "speed" else s != "excluded"
                            xs.append(v.loc[m, features])
                            ys.append(s[m].replace({"30Hz": "on", "50Hz": "on"}) if task == "binary" else s[m])
                        labels = pd.concat(ys)
                        if labels.nunique() < (3 if task == "three" else 2):
                            continue
                        model = make_pipeline(StandardScaler(), LogisticRegression(C=.1, class_weight="balanced"))
                        model.fit(pd.concat(xs), labels)
                        pred = model.predict(x[features])
                        classes = model.classes_
                        p = model.predict_proba(x[features])
                        m = (y.index >= 20) & (y != "excluded")
                        if task == "speed":
                            m &= y != "off"
                        yy = y.replace({"30Hz": "on", "50Hz": "on"}) if task == "binary" else y
                        recall = {f"recall_{s}": np.mean(pred[m & (yy == s)] == s) for s in yy[m].unique()}
                        key = dict(case=test, channels=name, group=group, task=task, train_rule=rule)
                        scores.append(key | recall | dict(balanced_accuracy=np.mean(list(recall.values())), n=m.sum()))
                        for i, t in enumerate(y.index):
                            rows.append(key | dict(epoch_start_s=t, expected=yy.iloc[i],
                                                   predicted=pred[i], scored=bool(m.iloc[i])) |
                                        {f"score_{s}": p[i, j] for j, s in enumerate(classes)})
    predictions = pd.DataFrame(rows)
    predictions.to_csv(out / "coherence_predictions.csv", index=False)
    pd.DataFrame(scores).to_csv(out / "coherence_validation.csv", index=False)
    scored = predictions[predictions.scored].copy()
    scored["stage"] = scored.epoch_start_s // 30
    votes = []
    for key, v in scored.groupby(["case", "channels", "group", "task", "train_rule", "stage"]):
        counts = v.predicted.value_counts()
        winner = counts.index[0] if (counts == counts.iloc[0]).sum() == 1 else "tie"
        votes.append(dict(zip(["case", "channels", "group", "task", "train_rule", "stage"], key)) |
                     dict(expected=v.expected.iloc[0], majority=winner, correct=winner == v.expected.iloc[0],
                          correct_windows=int((v.predicted == v.expected).sum()), windows=len(v)))
    pd.DataFrame(votes).to_csv(out / "coherence_stage_votes.csv", index=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=type(OUT), default=OUT)
    parser.add_argument("--raw", type=type(RAW), default=RAW)
    parser.add_argument("--reuse-pairs", action="store_true")
    args = parser.parse_args()
    path0 = args.out / "coherence_pairs_5s.csv"
    if args.reuse_pairs:
        frame = pd.read_csv(path0)
    else:
        rows = []
        for case, path in inventory(args.raw):
            rows.extend(process(case, path, args.out))
        frame = pd.DataFrame(rows)
        frame.to_csv(path0, index=False)
    compact = frame.groupby(["case", "epoch_start_s", "epoch_end_s", "band"]).median_coherence.median().reset_index()
    compact.to_csv(args.out / "coherence_5s.csv", index=False)
    out = []
    for (case, band), d in compact.groupby(["case", "band"]):
        states = ("off", "50Hz", "off", "50Hz") if "-" in case else ("off", "50Hz", "30Hz", "off")
        power = [float(d[d.epoch_start_s.isin([i*30+5, i*30+10, i*30+15])].median_coherence.median())
                 for i in range(4)]
        for i, label in enumerate(states):
            out.append(dict(case=case, stage=i, state=label, band=band, median_coherence=power[i],
                            delta_vs_initial_off=power[i]-power[0],
                            delta_vs_later_off=power[i]-power[states.index("off", 1)]))
    pd.DataFrame(out).to_csv(args.out / "coherence_stages.csv", index=False)
    classify(frame, args.out)


if __name__ == "__main__":
    main()
