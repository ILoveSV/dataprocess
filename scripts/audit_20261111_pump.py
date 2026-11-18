"""Targeted controls: channels, slow rhythms, narrow lines and transition timing."""

import argparse
import numpy as np
import pandas as pd
from scipy import ndimage, signal

from analyze_20261111_pump import (
    IDS, POWER_GROUPS, STAGES, confirmed, db, derive, fit, fmedian, metrics,
    read, stage_labels,
)
from extract_20261111_pump import LOW_FS, OUT


def channel_sensitivity(cases, out):
    rows = []
    common = np.logical_and.reduce([d["health"] for d in cases])
    for kind in ("common", "include8", "only8", "all"):
        for d in cases:
            m = d["health"].copy()
            if kind == "common":
                m = common
            elif kind == "all":
                m[:] = True
            else:
                if kind == "only8":
                    m[:] = False
                m[7] = True
            valid = m[None, :] & (d["second_bad"] == 0) & (d["second_flat"] < .95)
            for group, keys in POWER_GROUPS.items():
                v = np.stack([d["trans"][k] for k in keys], axis=-1)
                v = np.where(valid[:, :, None], v, np.nan)
                v[:4] = 0
                d["features"][group] = np.column_stack((np.nanmedian(v, axis=1), np.nanquantile(v, .9, axis=1)))
        for d in cases:
            y = stage_labels(d)
            for group in POWER_GROUPS:
                for task in ("binary", "speed", "three"):
                    if task == "speed" and d["protocol_b"]:
                        continue
                    model = fit([r for r in cases if r is not d], group, task, 2)
                    raw = model.predict(d["features"][group])
                    stable, _ = confirmed(raw)
                    mask = (np.arange(d["n"]) >= 20) & (y != "excluded")
                    if task == "speed":
                        mask &= y != "off"
                    target = np.where(y == "off", "off", "on") if task == "binary" else y
                    rows.append(dict(case=d["case"], channel_rule=kind, group=group, task=task) |
                                metrics(target, stable, mask))
    pd.DataFrame(rows).to_csv(out / "channel_sensitivity.csv", index=False)
    return common


def slow_audit(cases, common, out):
    rows, lines = [], []
    for d in cases:
        for lo, hi in ((2, 18), (5, 20), (7, 19)):
            measurements = []
            for i, state in enumerate(STAGES[d["protocol_b"]]):
                a, b = i*30 + lo, i*30 + hi
                x = d["low"][:, a*LOW_FS:b*LOW_FS].astype("float64")
                x = signal.resample_poly(x, 1, LOW_FS // 100, axis=1, padtype="line")
                f, p = signal.periodogram(x, fs=100, window="hann", detrend="linear", axis=1)
                vals = {}
                for left, right, name in ((.1, 1, "0p1_1"), (.2, 1, "0p2_1"), (.22, .43, "near_0p323"),
                                           (1, 5, "1_5")):
                    mask = (f >= left) & (f < right)
                    vals[name] = p[:, mask].sum(axis=1) * (f[1] - f[0])
                measurements.append(vals)
                if (lo, hi) == (5, 20):
                    t = np.arange(x.shape[1]) / 100
                    design = np.column_stack((np.ones_like(t), t-t.mean(), np.cos(2*np.pi*.323*t),
                                              np.sin(2*np.pi*.323*t)))
                    beta = np.linalg.lstsq(design, x.T, rcond=None)[0]
                    for ch, amp in enumerate(np.hypot(beta[-2], beta[-1]) * 1e6):
                        lines.append(dict(case=d["case"], stage=i, state=state, channel=ch+1,
                                          usable=d["health"][ch], fit_0p323_peak_uv=amp))
            stops = [i for i, s in enumerate(STAGES[d["protocol_b"]]) if s == "off"]
            for i, (label, m) in enumerate(zip(STAGES[d["protocol_b"]], measurements)):
                if label == "off":
                    continue
                for k, v in m.items():
                    for rule, keep in [("per_file", d["health"]), ("common", common)]:
                        diffs = [float(np.median(db(v[keep], measurements[j][k][keep]))) for j in stops]
                        rows.append(dict(case=d["case"], stage=i, state=label, feature=k,
                                         window_start_s=lo, window_end_s=hi, channels=rule,
                                         vs_initial_off_db=diffs[0], vs_later_off_db=diffs[1],
                                         lower_than_both_off=max(diffs) < 0))
    pd.DataFrame(rows).to_csv(out / "slow_window_audit.csv", index=False)
    pd.DataFrame(lines).to_csv(out / "fixed_0p323_fit.csv", index=False)


def narrow_audit(cases, out):
    peaks, hits, repeat = [], [], []
    grids = {s: [] for s in ("30Hz", "50Hz")}
    for d in cases:
        states = STAGES[d["protocol_b"]]
        eligible = d["health"]
        eps = d["epoch_psd"]
        freq = np.arange(eps.shape[-1])
        tracks = [eps[i*6+1:i*6+4, eligible, :] for i in range(4)]
        off = np.maximum.reduce([np.median(tracks[i], axis=0) for i, s in enumerate(states) if s == "off"])
        for i, s in enumerate(states):
            if s == "off":
                continue
            cur = tracks[i]
            mid = np.median(cur, axis=0)
            # Compare the strongest bin within +/-1 Hz and require all three 5 s blocks.
            contrast = db(ndimage.maximum_filter1d(cur, 3, axis=-1),
                          ndimage.maximum_filter1d(off, 3, axis=-1)[None, :, :])
            db_mid = 10*np.log10(np.maximum(mid, 1e-30))
            neighbor = ndimage.uniform_filter1d(db_mid, size=31, axis=-1)
            prom = db_mid - neighbor
            supported = (np.min(contrast, axis=0) >= 3) & (prom >= 6)
            supported[:, :20] = False
            supported[:, 199900:] = False
            grid = ndimage.maximum_filter1d(supported, 3, axis=-1).sum(axis=0)
            grids[s].append((d["case"], i, grid))
            for j, ch in enumerate(np.flatnonzero(eligible)):
                for left, right in ((20, 1000), (1000, 20000), (20000, 80000), (80000, 199900)):
                    q = np.flatnonzero(supported[j, left:right]) + left
                    order = np.argsort(np.min(contrast[:, j, q], axis=0))[::-1][:5]
                    for k in q[order]:
                        peaks.append(dict(case=d["case"], stage=i, state=s, channel=ch+1, frequency_hz=k,
                                          band_start_hz=left, min_three_blocks_db=np.min(contrast[:, j, k]),
                                          prominence_db=prom[j, k]))
            strong = np.flatnonzero(grid >= 3)
            for k in strong:
                hits.append(dict(case=d["case"], stage=i, state=s, frequency_hz=k,
                                 supporting_channels=grid[k]))
    for s, entries in grids.items():
        cases0 = sorted({case for case, _, _ in entries})
        per_case = np.stack([np.maximum.reduce([grid for c, _, grid in entries if c == case])
                             for case in cases0])
        for k in np.flatnonzero((per_case >= 3).sum(axis=0) >= 2):
            repeat.append(dict(state=s, frequency_hz=k,
                               records_with_3ch="+".join(c for c, row in zip(cases0, per_case) if row[k] >= 3),
                               n_records_3ch=int((per_case[:, k] >= 3).sum()),
                               n_records_1ch=int((per_case[:, k] >= 1).sum())))
    pd.DataFrame(peaks, columns=["case", "stage", "state", "channel", "frequency_hz", "band_start_hz",
                                 "min_three_blocks_db", "prominence_db"]).to_csv(out / "narrow_lines_by_channel.csv", index=False)
    pd.DataFrame(hits, columns=["case", "stage", "state", "frequency_hz", "supporting_channels"]).to_csv(
        out / "narrow_lines_multichannel.csv", index=False)
    pd.DataFrame(repeat, columns=["state", "frequency_hz", "records_with_3ch", "n_records_3ch",
                                  "n_records_1ch"]).to_csv(out / "narrow_lines_repeated.csv", index=False)


def transient_audit(cases, out):
    rows, control = [], []
    for d in cases:
        x = d["slow_mean"].reshape(d["n"], 10, 12)
        r = d["broadband_rms"].reshape(d["n"], 10, 12)
        ref = np.diff(x[:20].reshape(-1, 12), axis=0)
        scale = np.maximum(1.4826*np.median(abs(ref-np.median(ref, axis=0)), axis=0), 1e-7)
        delta = np.diff(x.reshape(-1, 12), axis=0, prepend=x[0, :1]).reshape(x.shape)
        score = np.max(np.abs(delta), axis=1)/scale
        ref_r = np.median(r[5:20], axis=(0, 1))
        rms = np.max(r, axis=1) / ref_r
        keep = d["valid"]
        dr = fmedian(score, keep, axis=1)
        rr = fmedian(rms, keep, axis=1)
        for a in (20, 50, 80):
            for name, y in (("dc_jump", dr), ("rms_burst", rr)):
                ix = a + int(np.argmax(y[a:a+10]))
                base = np.r_[y[5:20], y[32:48], y[62:78], y[92:min(118, d["n"])]]
                rows.append(dict(case=d["case"], nominal_command_s=a, feature=name,
                                 peak_second_start_s=ix, peak=y[ix], stable_q95=np.quantile(base, .95),
                                 stable_max=base.max(), above_stable_max=y[ix] > base.max()))
        for i in range(d["n"]):
            control.append(dict(case=d["case"], start_s=i, dc_jump_score=dr[i], rms_burst_score=rr[i],
                                dc_jump_ch8=score[i, 7], rms_burst_ch8=rms[i, 7],
                                dc_jump_ch11=score[i, 10], rms_burst_ch11=rms[i, 10]))
    pd.DataFrame(rows).to_csv(out / "transient_windows.csv", index=False)
    pd.DataFrame(control).to_csv(out / "transient_traces.csv", index=False)


def distance_audit(cases, common, out):
    """Compare response similarity; this is not a calibrated distance estimator."""
    names = ("b100_1k", "b1_20k", "b20_80k", "b80_200k", "line30", "line50", "low5_100")
    features = {}
    for d in cases:
        def signature(i, j, k):
            a = np.median(d["vals"][k][i*30+5:i*30+20], axis=0)
            b = np.median(d["vals"][k][j*30+5:j*30+20], axis=0)
            return db(a[common], b[common])
        features[d["case"]] = np.array([[signature(i, j, k) for k in names]
                                        for i, j in ((1, 0), (3, 2)) if i == 1 or d["protocol_b"]])
    rows = []
    for c, f in features.items():
        if len(f) != 2:
            continue
        for ref in ("2", "3", "4", "3-2_late"):
            if ref == c:
                continue
            for k, name in enumerate(names):
                a, b = f[:, k], features[ref][0, k]
                rows.append(dict(case=c, reference=ref, feature=name,
                                 first_run_distance_db=np.linalg.norm(a[0]-b)/np.sqrt(len(b)),
                                 second_run_distance_db=np.linalg.norm(a[1]-b)/np.sqrt(len(b)),
                                 own_repeat_distance_db=np.linalg.norm(a[0]-a[1])/np.sqrt(len(b))))
    pd.DataFrame(rows).to_csv(out / "distance_signature_audit.csv", index=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default=OUT, type=type(OUT))
    args = p.parse_args()
    cases = [derive(read(args.out, case)) for case in IDS]
    common = channel_sensitivity(cases, args.out)
    slow_audit(cases, common, args.out)
    narrow_audit(cases, args.out)
    transient_audit(cases, args.out)
    distance_audit(cases, common, args.out)
    print("Audits complete:", args.out, flush=True)


if __name__ == "__main__":
    main()
