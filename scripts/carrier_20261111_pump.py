"""Native-rate one-second replay of candidate carrier lines and sidebands."""

import argparse
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from nptdms import TdmsFile
from scipy import fft

from analyze_20261111_pump import COLORS, CONFIRMED, IDS, STAGES, confirmed, db, fit, metrics, stage_labels
from extract_20261111_pump import FS, NORM, OUT, RAW, WINDOW, inventory

CENTERS = (4000, 8000, 12000, 16000)
FREQS = sorted(set(CENTERS) | {c + f for c in CENTERS for f in (-100, -60, -50, -30, 30, 50, 60, 100)})


def extract(path, expected):
    with TdmsFile.open(path) as td:
        group, = td.groups()
        assert [c.name for c in group.channels()] == expected["channels"]
        buf = np.empty((12, FS))
        pos = seen = 0
        rows, floor = [], []
        for data in td.data_chunks():
            channels = data[group.name].channels()
            if not channels or not len(channels[0]):
                continue
            assert all(ch.offset == seen for ch in channels)
            x = np.stack([ch[:] for ch in channels])
            seen += x.shape[1]
            start = 0
            while start < x.shape[1]:
                count = min(FS-pos, x.shape[1]-start)
                buf[:, pos:pos+count] = x[:, start:start+count]
                pos += count
                start += count
                if pos != FS:
                    continue
                # Unreliable nonfinite channels are never accepted as line evidence.
                z = np.nan_to_num(buf - buf[:, :1], posinf=0, neginf=0)
                tf = fft.rfft(z*WINDOW, axis=1, workers=2)
                p = 2*np.abs(tf)**2/NORM
                half = np.array([2 if f in CENTERS else 4 for f in FREQS])
                rows.append(np.stack([p[:, f-h:f+h+1].sum(axis=1) for f, h in zip(FREQS, half)], axis=1))
                floor.append(np.stack([
                    np.median(np.concatenate((p[:, f-19:f-8], p[:, f+9:f+20]), axis=1), axis=1) * (2*h+1)
                    for f, h in zip(FREQS, half)], axis=1))
                pos = 0
        assert seen == expected["sample_count"] and len(rows) == expected["full_seconds"]
        return np.array(rows), np.array(floor)


def load(out, raw):
    cases = {}
    for case, path in inventory(raw):
        parent = out / "cache" / case
        meta = json.loads((parent / "metadata.json").read_text(encoding="utf-8"))
        cache = parent / "carrier_lines.npz"
        if cache.exists():
            with np.load(cache) as z:
                power, floor = z["power"], z["floor"]
        else:
            power, floor = extract(path, meta)
            np.savez(cache, power=power, floor=floor, frequencies=FREQS)
        eligible = np.array([not r["automatic_suspect"] for r in meta["health"]])
        f = [FREQS.index(v) for v in CENTERS]
        sides = [FREQS.index(v) for v in (3970, 4030, 3950, 4050, 7970, 8030, 7950, 8050)]
        values = {}
        for scope, lo, hi in (("ch8", 5, 15), ("ch8_baseline20", 5, 20), ("eligible", 5, 15)):
            clip = power[:, :, f]
            ref = np.median(clip[lo:hi], axis=0)
            change = np.clip(db(clip, ref), -15, 40)
            prom = np.clip(db(clip, floor[:, :, f]), -15, 45)
            side = np.clip(db(power[:, :, sides], floor[:, :, sides]), -15, 45)
            if scope == "eligible":
                change = np.quantile(change[:, eligible], .90, axis=1)
                prom = np.quantile(prom[:, eligible], .90, axis=1)
                side = np.quantile(side[:, eligible], .90, axis=1)
            else:
                change, prom, side = change[:, 7], prom[:, 7], side[:, 7]
            values[scope] = np.c_[change, prom, side]
        cases[case] = dict(case=case, protocol_b="-" in case, n=len(power), features=values,
                           power=power, floor=floor, health=eligible)
        print(f"{case}: {len(power)} one-second carrier measurements", flush=True)
    return [cases[c] for c in IDS]


def evaluate(cases, out):
    pred, scores, stages, events = [], [], [], []
    for d in cases:
        case = d["case"]
        for train_rule in ("all", "certain", "cross_protocol"):
            if train_rule == "certain" and case not in CONFIRMED:
                continue
            train = [r for r in cases if r is not d and
                     (train_rule != "certain" or r["case"] in CONFIRMED) and
                     (train_rule != "cross_protocol" or r["protocol_b"] != d["protocol_b"])]
            for group in d["features"]:
                for task in ("binary", "speed", "three"):
                    if task == "speed" and d["protocol_b"]:
                        continue
                    if task == "three" and d["protocol_b"]:
                        continue
                    model = fit(train, group, task, 2)
                    if model is None:
                        continue
                    y = stage_labels(d)
                    if task == "binary":
                        y = np.where(y == "excluded", y, np.where(y == "off", "off", "on"))
                    mask = (np.arange(d["n"]) >= 20) & (y != "excluded")
                    if task == "speed":
                        mask &= y != "off"
                    prob = model.predict_proba(d["features"][group])
                    classes = model.classes_
                    raw = classes[prob.argmax(axis=1)]
                    stable, ee = confirmed(raw)
                    key = dict(case=case, group=group, task=task, train_rule=train_rule)
                    for kind, response in (("raw", raw), ("confirmed", stable)):
                        scores.append(key | dict(kind=kind) | metrics(y, response, mask))
                    if train_rule != "all":
                        continue
                    for i in range(d["n"]):
                        pred.append(key | dict(start_s=i, end_s=i+1, expected=y[i],
                                               raw=raw[i], confirmed=stable[i], scored=mask[i]) |
                                    {f"score_{s}": prob[i, j] for j, s in enumerate(classes)})
                    for t, s in ee:
                        events.append(key | dict(end_s=t, event=s))
        for i, label in enumerate(STAGES[d["protocol_b"]]):
            a, b = 30*i+5, 30*i+20
            for f0 in CENTERS:
                f = FREQS.index(f0)
                z = d["power"][:, :, f]
                p = d["floor"][:, :, f]
                for ch in range(12):
                    stages.append(dict(case=case, stage=i, state=label, carrier_hz=f0,
                                       channel=ch+1, eligible=d["health"][ch],
                                       median_uv_rms=np.sqrt(np.median(z[a:b, ch]))*1e6,
                                       median_prominence_db=np.median(db(z[a:b, ch], p[a:b, ch])),
                                       change_vs_initial_5_15_db=db(np.median(z[a:b, ch]),
                                                                   np.median(z[5:15, ch]))))
    for name, rows in (("carrier_predictions", pred), ("carrier_validation", scores),
                       ("carrier_stages", stages), ("carrier_events", events)):
        pd.DataFrame(rows).to_csv(out / (name + ".csv"), index=False)
    return pd.DataFrame(pred)


def plot(cases, pred, out):
    fig, axes = plt.subplots(len(cases), 2, sharex=True, figsize=(14, 15))
    for d, (left, right) in zip(cases, axes):
        for ax in (left, right):
            for i, label in enumerate(STAGES[d["protocol_b"]]):
                ax.axvspan(i*30, i*30+(20 if i < 3 else 30), color=COLORS[label], alpha=.11)
                if i:
                    ax.axvspan(i*30-10, i*30, color="#999999", alpha=.20)
        t = np.arange(d["n"]) + .5
        for f, color in zip(CENTERS[:3], ("#265293", "#257b70", "#a44a31")):
            left.semilogy(t, np.sqrt(d["power"][:, 7, FREQS.index(f)])*1e6,
                          lw=.9, color=color, label=f"{f//1000} kHz")
        for s, color in (("ch8", "#2a5794"), ("eligible", "#858585")):
            q = pred[(pred.case == d["case"]) & (pred.group == s) & (pred.task == "binary") & (pred.end_s > 20)]
            right.plot(q.end_s, q.score_on, color=color, label=s, lw=1.0)
        right.axhline(.5, color="#333333", ls="--", lw=.6)
        right.set_ylim(-.04, 1.04)
        left.set_ylabel(d["case"]+"\nRMS (uV)")
    axes[0, 0].set_title("CH8: narrow-line RMS, raw sample rate")
    axes[0, 1].set_title("Held-out binary score using carrier features")
    for ax in axes[0]:
        ax.legend(ncol=3, loc="upper right", fontsize=8)
    for ax in axes[-1]:
        ax.set_xlabel("Elapsed time (s)")
    fig.tight_layout()
    fig.savefig(out / "carrier_timeline.png", dpi=170)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=type(OUT), default=OUT)
    p.add_argument("--raw", type=type(RAW), default=RAW)
    args = p.parse_args()
    cases = load(args.out, args.raw)
    pred = evaluate(cases, args.out)
    plot(cases, pred, args.out)


if __name__ == "__main__":
    main()
