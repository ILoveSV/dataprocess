"""Replay and audit the November pump states without time or distance as predictors."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import signal
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from extract_20261111_pump import BANDS, EXTRA_BANDS, KEYS, LOW_FS, OUT

IDS = ("2", "3", "4", "4-2", "3-2_early", "3-2_late", "2-2")
CONFIRMED = ("2", "3", "4", "3-2_late")
LABELS = ("off", "30Hz", "50Hz")
COLORS = {"off": "#6b7280", "30Hz": "#127d72", "50Hz": "#b45127"}
STAGES = {False: ("off", "50Hz", "30Hz", "off"), True: ("off", "50Hz", "off", "50Hz")}
P_NAMES = list(BANDS | EXTRA_BANDS)
POWER_GROUPS = {
    "sub5": ("dc", "lf02_1", "lf1_5"),
    "below100": ("dc", "lf02_1", "lf1_5", "line30", "line50", "line60", "line90", "low5_100"),
    "low_1k": ("dc", "lf02_1", "lf1_5", "line30", "line50", "line60", "line90", "line100",
               "low5_100", "b100_1k", *list(EXTRA_BANDS)[3:]),
    "high_above1k": ("b1_20k", "b20_80k", "b80_200k", "carrier4k", "carrier8k", "carrier12k",
                     "near100k"),
    "low_lines": ("line30", "line50", "line60", "line90", "line100", *list(EXTRA_BANDS)[3:]),
}
POWER_GROUPS["combined"] = tuple(dict.fromkeys(
    POWER_GROUPS["low_1k"] + POWER_GROUPS["high_above1k"] + ("rms", "diff")))


def read(root, case):
    path = root / "cache" / case
    meta = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
    d = dict(np.load(path / "features.npz"))
    n = meta["full_seconds"]
    assert d["bandpower"].shape == (n, 12, len(BANDS))
    assert d["low"].shape == (12, n * LOW_FS)
    assert d["epoch_counts"].sum() == n
    assert all(d[k].shape == (n * 10, 12) for k in KEYS)
    assert np.isfinite(d["bandpower"]).all() and (d["bandpower"] >= 0).all()
    assert np.isfinite(d["epoch_psd"]).all()
    d.update(meta=meta, case=case, n=n, protocol_b="-" in case)
    d["health"] = np.array([not r["automatic_suspect"] for r in meta["health"]])
    d["valid"] = d["health"][None, :] & (d["second_bad"] == 0) & (d["second_flat"] < .95)
    if d["health"].sum() < 4:
        raise ValueError(f"{case}: fewer than four eligible channels")
    return d


def stage_labels(d, guard=2):
    stages = STAGES[d["protocol_b"]]
    y = np.full(d["n"], "excluded", dtype="<U10")
    for i, label in enumerate(stages):
        a = i * 30 + guard
        b = i * 30 + (20 if i < 3 else 30) - guard
        y[a:b] = label
    return y


def db(x, y):
    return 10 * np.log10(np.maximum(x, 1e-30) / np.maximum(y, 1e-30))


def fmedian(x, mask, axis=0):
    return np.nanmedian(np.where(mask, x, np.nan), axis=axis)


def derive(d):
    valid = d["valid"]
    ref = np.arange(d["n"])
    ref = (ref >= 5) & (ref < 20)
    # Anti-alias once more before analyzing the slow 0.2--5 Hz variations.
    x = signal.resample_poly(d["low"].astype("float64"), 1, LOW_FS // 40, axis=1, padtype="line")
    rolling = np.lib.stride_tricks.sliding_window_view(x, 200, axis=1)[:, ::40, :]
    f, p = signal.periodogram(rolling, fs=40, window="hann", detrend="linear", axis=-1)
    p = p.transpose(1, 0, 2)
    if len(p) != d["n"] - 4:
        raise ValueError(f"{d['case']}: slow-window alignment mismatch")
    vals = dict(zip(P_NAMES, np.concatenate((d["bandpower"], d["extra_power"]), axis=2).transpose(2, 0, 1)))
    for low, high, name in [(0.2, 1, "lf02_1"), (1, 5, "lf1_5")]:
        vals[name] = np.vstack((np.full((4, 12), np.nan), p[:, :, (f >= low) & (f < high)].sum(axis=2) * .2))
    for name, k in [("rms", "broadband_rms"), ("diff", "difference_rms")]:
        vals[name] = np.mean(d[k].reshape(d["n"], 10, 12)**2, axis=1)
    means = d["slow_mean"].reshape(d["n"], 10, 12).mean(axis=1)
    base = np.median(means[ref], axis=0)
    d["dc_uv"] = (means - base) * 1e6
    transforms = {k: np.clip(db(v, np.nanmedian(v[ref], axis=0)), -20, 40) for k, v in vals.items()}
    transforms["dc"] = np.clip(np.abs(means - base) /
                               np.maximum(np.median(np.abs(means[ref] - base), axis=0) * 1.4826, 1e-5), 0, 20)
    d.update(vals=vals, trans=transforms, features={})
    for group, keys in POWER_GROUPS.items():
        v = np.stack([transforms[k] for k in keys], axis=-1)
        v = np.where(valid[:, :, None], v, np.nan)
        # The first four seconds have no complete trailing five-second window.
        v[:4] = 0.0
        d["features"][group] = np.column_stack((np.nanmedian(v, axis=1), np.nanquantile(v, .9, axis=1)))
        assert np.isfinite(d["features"][group]).all()
    return d


def stable_power(d, a, b):
    x = d["low"][:, a * LOW_FS:b * LOW_FS].astype("float64")
    f, p = signal.welch(x, fs=LOW_FS, nperseg=min(x.shape[1], LOW_FS * 10),
                        noverlap=LOW_FS * 5, detrend="linear", axis=1)
    df = f[1] - f[0]
    lf = {"stage_0p1_1": (.1, 1), "stage_1_5": (1, 5), "stage_5_20": (5, 20),
          "stage_near_0p323": (.22, .43)}
    out = {k: p[:, (f >= lo) & (f < hi)].sum(axis=1) * df for k, (lo, hi) in lf.items()}
    return out, f, p


def contrasts(cases, out):
    records = []
    stage_psd = {}
    for d in cases:
        ref, f, baseline = stable_power(d, 5, 20)
        stage_psd[d["case"]] = [baseline]
        for j, state in enumerate(STAGES[d["protocol_b"]]):
            a, b = 30*j + 5, min(30*j + 20, d["n"])
            v, _, p = stable_power(d, a, b)
            if j:
                stage_psd[d["case"]].append(p)
            vals = {k: np.nanmedian(z[a:b], axis=0) for k, z in d["vals"].items()} | v
            for k, value in vals.items():
                base = ref[k] if k in ref else np.nanmedian(d["vals"][k][5:20], axis=0)
                for ch, (absolute, delta) in enumerate(zip(value, db(value, base))):
                    records.append(dict(case=d["case"], stage=j, state=state, channel=ch+1,
                                        usable=d["health"][ch], feature=k, power_v2=absolute,
                                        relative_to_initial_off_db=delta))
    df = pd.DataFrame(records)
    df.to_csv(out / "stage_channel_contrasts.csv", index=False)
    compact = df[df.usable].groupby(["case", "stage", "state", "feature"]).relative_to_initial_off_db
    compact.agg(median_db="median", min_db="min", max_db="max", n="count",
                positive_channels=lambda v: int((v > 0).sum())).reset_index().to_csv(
                    out / "stage_contrasts.csv", index=False)
    np.savez(out / "low_stage_psd.npz", freq_hz=f, **{c: np.stack(p) for c, p in stage_psd.items()})
    return df


def fit(train, group, task, guard):
    xs, ys, weights = [], [], []
    for d in train:
        y = stage_labels(d, guard)
        eligible = np.isin(y, ("30Hz", "50Hz")) if task == "speed" else y != "excluded"
        target = np.where(y == "off", "off", "on") if task == "binary" else y
        xs.append(d["features"][group][eligible])
        ys.append(target[eligible])
        weights.append(np.ones(eligible.sum()) / eligible.sum())
    y = np.concatenate(ys)
    if np.unique(y).size < 2 or (task == "three" and np.unique(y).size < 3):
        return None
    w = np.concatenate(weights)
    w *= len(w) / w.sum()
    model = make_pipeline(StandardScaler(), LogisticRegression(C=.1, class_weight="balanced", max_iter=2000))
    return model.fit(np.vstack(xs), y, logisticregression__sample_weight=w)


def confirmed(pred):
    current, pending, count = "off", None, 0
    output, events = [], []
    for t, state in enumerate(pred):
        if t < 20:
            output.append("calibrating")
            continue
        count = count + 1 if state == pending else 1
        pending = state
        if count >= 3 and state != current:
            current = state
            events.append((t+1, state))
        output.append(current)
    return np.array(output), events


def metrics(y, pred, mask):
    out = {f"recall_{s}": float(np.mean(pred[mask & (y == s)] == s))
           for s in np.unique(y[mask])}
    return out | {"balanced_accuracy": float(np.mean(list(out.values()))),
                  "accuracy": float(np.mean(y[mask] == pred[mask])), "n": int(mask.sum())}


def grouped(cases, out):
    validation, predictions, events, matches, stage_votes = [], [], [], [], []
    cases_by_name = {d["case"]: d for d in cases}
    for split in ("leave_record_out", "leave_record_out_certain", "A_to_B", "B_to_A", "A_only_speed"):
        for d in cases:
            case = d["case"]
            if split == "leave_record_out":
                train = [r for r in cases if r is not d]
            elif split == "leave_record_out_certain":
                if case not in CONFIRMED:
                    continue
                train = [cases_by_name[c] for c in CONFIRMED if c != case]
            elif split == "A_only_speed":
                if d["protocol_b"]:
                    continue
                train = [r for r in cases if r is not d and not r["protocol_b"]]
            else:
                want_b = split == "B_to_A"
                if d["protocol_b"] == want_b:
                    continue
                train = [r for r in cases if r["protocol_b"] == want_b]
            for group in POWER_GROUPS:
                for task in ("binary", "speed", "three"):
                    if split == "A_only_speed" and task != "speed":
                        continue
                    if task == "speed" and d["protocol_b"]:
                        continue
                    for guard in (0, 2, 5) if split == "leave_record_out" else (2,):
                        model = fit(train, group, task, guard)
                        if model is None:
                            continue
                        y = stage_labels(d, guard)
                        good = (np.arange(len(y)) >= 20) & (y != "excluded")
                        if task == "speed":
                            good &= y != "off"
                        if task == "binary":
                            y = np.where(y == "excluded", y, np.where(y == "off", "off", "on"))
                        p = model.predict_proba(d["features"][group])
                        classes = model.classes_
                        raw = classes[np.argmax(p, axis=1)]
                        stable, ee = confirmed(raw)
                        key = dict(split=split, case=case, group=group, task=task, guard_s=guard,
                                   training="+".join(r["case"] for r in train))
                        for output, pred in [("raw", raw), ("confirmed", stable)]:
                            validation.append(key | dict(output=output) | metrics(y, pred, good))
                        if guard != 2 or split != "leave_record_out":
                            continue
                        for i in range(d["n"]):
                            probs = {f"score_{s}": p[i, j] for j, s in enumerate(classes)}
                            predictions.append(key | dict(start_s=i, end_s=i+1, expected=y[i],
                                                           scored=good[i], raw=raw[i],
                                                           confirmed=stable[i]) | probs)
                        for i, label in enumerate(STAGES[d["protocol_b"]]):
                            if not i or (task == "speed" and label == "off"):
                                continue
                            if task == "binary":
                                label = "off" if label == "off" else "on"
                            mask = good & (np.arange(d["n"]) >= 30*i) & (np.arange(d["n"]) < 30*(i+1))
                            values, counts = np.unique(stable[mask], return_counts=True)
                            majority = values[counts.argmax()] if (counts == counts.max()).sum() == 1 else "tie"
                            stage_votes.append(key | dict(stage=i, expected=label, majority=majority,
                                                           fraction_correct=float(np.mean(stable[mask] == label))))
                        if task not in ("binary", "three"):
                            continue
                        for t, s in ee:
                            events.append(key | dict(time_end_s=t, target=s))
                        states = STAGES[d["protocol_b"]]
                        used = set()
                        for i in range(1, 4):
                            if task == "binary" and states[i] != "off" and states[i-1] != "off":
                                continue
                            target = states[i] if task == "three" else ("off" if states[i] == "off" else "on")
                            hit = next(((t, s) for t, s in ee if s == target and i*30-10 <= t <= i*30+8
                                        and t not in used), None)
                            if hit:
                                used.add(hit[0])
                            matches.append(key | dict(stage=i, nominal_command_s=i*30-10,
                                                       nominal_stable_s=i*30, expected=target,
                                                       detected_end_s=hit[0] if hit else None))
                        for row in events[-len(ee):] if ee else []:
                            row["unmatched"] = row["time_end_s"] not in used
    for name, rows in (("validation", validation), ("predictions", predictions), ("events", events),
                       ("event_matches", matches), ("stage_votes", stage_votes)):
        pd.DataFrame(rows).to_csv(out / f"{name}.csv", index=False)
    v = pd.DataFrame(validation)
    metric_cols = ["balanced_accuracy", "accuracy", "recall_off", "recall_on", "recall_30Hz", "recall_50Hz"]
    v.groupby(["split", "task", "group", "guard_s", "output"])[metric_cols].mean().reset_index().to_csv(
        out / "validation_record_means.csv", index=False)
    return pd.DataFrame(predictions)


def historical(cases, out):
    from scripts.analyze_20260921_switching import load
    from scripts.health_fusion_recognizer import infer
    from scripts.state_recognizer import fit as old_fit, replay, cache_blocks

    old = old_fit(load())
    import joblib
    import warnings
    from sklearn.exceptions import InconsistentVersionWarning
    path = Path(__file__).resolve().parents[1] / "analysis/20260922_health_fusion/model.joblib"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", InconsistentVersionWarning)
        fusion = joblib.load(path)
    if caught:
        print("Historical fusion model load warnings:", [str(w.message) for w in caught], flush=True)
    rows, scores = [], []
    for d in cases:
        if d["meta"]["channels"] != old["channel_names"] or d["meta"]["channels"] != fusion["channel_names"]:
            print(f"{d['case']}: historical channel names/order differ; transfer skipped", flush=True)
            continue
        y = stage_labels(d)
        mask = (np.arange(d["n"]) >= 20) & (y != "excluded")
        binary = np.where(y == "off", "off", "on")
        for kind in ("sep22_fixed_fusion", "sep22_all_channels"):
            data = {k: d[k].copy() for k in KEYS + ["bandpower"]}
            if kind == "sep22_fixed_fusion":
                data["bandpower"][:, ~d["health"], :] = np.nan
                if np.any(d["second_bad"] > 0):
                    data["bandpower"] = np.where((d["second_bad"] > 0)[:, :, None], np.nan, data["bandpower"])
                result, _ = infer(cache_blocks(data), fusion)
            else:
                if np.any(d["second_bad"] > 0):
                    continue
                result = replay(cache_blocks(data), old, {})
            result.insert(0, "case", d["case"])
            result.insert(1, "model", kind)
            result["expected"] = y
            result["scored"] = mask
            rows.append(result)
            scores.append(dict(case=d["case"], model=kind, task="binary") |
                          metrics(binary, result.confirmed_binary.to_numpy(), mask))
            if kind == "sep22_all_channels" and not d["protocol_b"]:
                scores.append(dict(case=d["case"], model=kind, task="three") |
                              metrics(y, result.decision.to_numpy(), mask))
    pd.concat(rows, ignore_index=True).to_csv(out / "historical_predictions.csv", index=False) if rows else None
    pd.DataFrame(scores).to_csv(out / "historical_validation.csv", index=False)


def plot_timeline(cases, pred, out):
    fig, axes = plt.subplots(len(cases), 2, figsize=(15, 14), sharex=True)
    for d, (left, right) in zip(cases, axes):
        t = np.arange(d["n"]) + .5
        for ax in (left, right):
            for i, s in enumerate(STAGES[d["protocol_b"]]):
                ax.axvspan(i*30, i*30 + (20 if i < 3 else 30), color=COLORS[s], alpha=.085)
                if i:
                    ax.axvspan(i*30-10, i*30, color="#a0a0a0", alpha=.15)
            ax.axhline(0, lw=.6, color="#a0a0a0")
        for name, c in zip(("low5_100", "b100_1k", "b1_20k", "b20_80k", "b80_200k"),
                           ("#2862ab", "#007b73", "#b5781b", "#b34844", "#885393")):
            left.plot(t, fmedian(d["trans"][name], d["valid"], axis=1), lw=1, color=c, label=name)
        left.set_ylabel(f"{d['case']}\nChange (dB)")
        for group, c in zip(("sub5", "below100", "high_above1k", "combined"),
                            ("#757575", "#237d72", "#bf6127", "#264f90")):
            a = pred[(pred.case == d["case"]) & (pred.group == group) & (pred.task == "binary")]
            right.plot(a.end_s[a.end_s > 20], a.score_on[a.end_s > 20], lw=1.15, color=c, label=group)
        right.axhline(.5, color="#666", lw=.7, ls="--")
        right.set_ylim(-.04, 1.04)
    axes[0, 0].legend(ncol=3, fontsize=8, loc="upper left")
    axes[0, 1].legend(ncol=4, fontsize=8, loc="upper left")
    axes[0, 0].set_title("Median across eligible channels, relative to 5-20 s")
    axes[0, 1].set_title("Leave-one-record-out pump RUN scores")
    for ax in axes[-1]:
        ax.set_xlabel("Elapsed time (s)")
    fig.tight_layout()
    fig.savefig(out / "pump_timeline.png", dpi=165)
    plt.close(fig)


def plot_psd(cases, out):
    fig, axes = plt.subplots(len(cases), 2, figsize=(14, 15))
    for d, (low, high) in zip(cases, axes):
        eligible = d["health"]
        fs = np.arange(d["epoch_psd"].shape[-1])
        for i, state in enumerate(STAGES[d["protocol_b"]]):
            ix = [i*6+1, i*6+2, i*6+3]
            sp = d["epoch_psd"][ix][:, eligible].mean(axis=0)
            sp = np.median(10*np.log10(np.maximum(sp, 1e-30)), axis=0)
            for ax, sel in [(low, (fs >= 5) & (fs < 1000)), (high, (fs >= 1000) & (fs < 199900))]:
                if ax is high:
                    ax.semilogx(fs[sel], sp[sel], color=COLORS[state], alpha=.85, lw=.65,
                                ls="--" if i >= 2 and state in STAGES[d["protocol_b"]][:i] else "-",
                                label=f"{i+1}: {state}")
                else:
                    ax.plot(fs[sel], sp[sel], color=COLORS[state], alpha=.85, lw=.8,
                            ls="--" if i >= 2 and state in STAGES[d["protocol_b"]][:i] else "-",
                            label=f"{i+1}: {state}")
        low.set_ylabel(f"{d['case']}\nPSD (dB V²/Hz)")
    axes[0, 0].legend(ncol=4, fontsize=8)
    axes[0, 0].set_title("5 Hz-1 kHz: four stable stages, median channel PSD")
    axes[0, 1].set_title("1-200 kHz: same stages, native-rate FFT")
    for ax in axes[-1]:
        ax.set_xlabel("Frequency (Hz)")
    fig.tight_layout()
    fig.savefig(out / "pump_stable_psd.png", dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--skip-historical", action="store_true")
    args = parser.parse_args()
    out = args.out
    cases = [derive(read(out, c)) for c in IDS]
    assert all(d["meta"]["channels"] == cases[0]["meta"]["channels"] for d in cases)
    extra = [read(out, "back")] if (out / "cache" / "back" / "metadata.json").exists() else []
    inventory = [{k: v for k, v in d["meta"].items() if k not in ("health", "channels")} |
                 dict(case=d["case"], use_in_pump=d["case"] != "back",
                      distance_status="confirmed" if d["case"] in CONFIRMED else "unconfirmed_or_not_applicable",
                      usable_channels=int(d["health"].sum())) for d in cases + extra]
    pd.DataFrame(inventory).to_csv(out / "inventory.csv", index=False)
    pd.DataFrame([dict(case=d["case"]) | row for d in cases + extra for row in d["meta"]["health"]]).to_csv(
        out / "channel_health.csv", index=False)
    contrasts(cases, out)
    pred = grouped(cases, out)
    plot_timeline(cases, pred, out)
    plot_psd(cases, out)
    if not args.skip_historical:
        historical(cases, out)
    print("Analysis complete:", out, flush=True)


if __name__ == "__main__":
    main()
