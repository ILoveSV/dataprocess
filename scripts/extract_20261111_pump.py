"""Stream the November pump recordings into per-channel, full-rate features."""

import argparse
import json
from pathlib import Path

import numpy as np
from nptdms import TdmsFile
from scipy import fft, signal

from channel_quality import assess_channel_quality
from state_recognizer import BANDS, KEYS

FS = 400_000
LOW_FS = 4_000
PAD = 2_000
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "20261111_pump"
RAW = Path("D:/Lab/raw/raw/11.11")
EXTRA_BANDS = {
    "line60": (58, 62), "line90": (88, 92), "line120": (118, 122),
    "line150": (148, 152), "line200": (198, 202),
    "line300": (298, 302), "line400": (398, 402), "line450": (448, 452),
}
FREQ = fft.rfftfreq(FS, 1 / FS)
WINDOW = signal.windows.hann(FS, sym=False)
NORM = FS * np.dot(WINDOW, WINDOW)
SLICES = [slice(a, b) for a, b in (BANDS | EXTRA_BANDS).values()]


def inventory(raw):
    result = []
    for folder in ("2", "3", "4", "2-2", "3-2", "4-2"):
        paths = sorted((raw / folder).glob("*.tdms"))
        expected = 2 if folder == "3-2" else 1
        if len(paths) != expected:
            raise ValueError(f"{folder}: expected {expected} TDMS files, found {len(paths)}")
        for i, path in enumerate(paths):
            case = ("3-2_early", "3-2_late")[i] if folder == "3-2" else folder
            result.append((case, path))
    return result


def extract(path, target):
    with TdmsFile.open(path) as td:
        group, = td.groups()
        channels = group.channels()
        names = [ch.name for ch in channels]
        count = len(channels[0])
        if len(channels) != 12 or any(
            len(ch) != count or not np.isclose(1 / ch.properties["wf_increment"], FS, rtol=1e-9)
            or str(ch.properties.get("unit_string", ch.properties.get("NI_UnitDescription", ""))).lower()
            not in ("v", "volts") for ch in channels
        ):
            raise ValueError(f"Unexpected TDMS shape, sample rate or units: {path}")
        if td.file_status.incomplete_final_segment:
            raise ValueError(f"Incomplete final TDMS segment: {path}")
        meta = dict(source=str(path), bytes=path.stat().st_size, channels=names,
                    sample_count=count, fs=FS, duration_s=count / FS,
                    full_seconds=count // FS, tail_s=count % FS / FS,
                    wf_start_time=str(channels[0].properties.get("wf_start_time")),
                    tdms_properties={k: str(v) for k, v in td.properties.items()},
                    group_properties={k: str(v) for k, v in group.properties.items()})
        arrays = {name: [] for name in KEYS + ["bandpower", "extra_power", "small_psd",
                                               "epoch_psd", "epoch_counts", "low",
                                               "second_bad", "second_flat"]}
        offset = None
        global_sum = np.zeros(12)
        global_square = np.zeros(12)
        diff_square = np.zeros(12)
        lo = np.full(12, np.inf)
        hi = np.full(12, -np.inf)
        bad = np.zeros(12, dtype=np.int64)
        flat = np.zeros(12, dtype=np.int64)
        last = None
        carry = np.empty((12, 0))
        history = None
        epoch = np.zeros((12, len(FREQ)))
        in_epoch = 0
        seen = 0

        def consume(body, right):
            nonlocal history, in_epoch, epoch
            if history is None:
                history = np.repeat(body[:, :1], PAD, axis=1)
            if right.shape[1] < PAD:
                last_sample = right[:, -1:] if right.shape[1] else body[:, -1:]
                right = np.concatenate((right, np.repeat(last_sample, PAD - right.shape[1], axis=1)), axis=1)
            second_bad = (~np.isfinite(body)).sum(axis=1)
            x = np.where(np.isfinite(body), body, 0.0)
            overlap = np.concatenate((history, x, right[:, :PAD]), axis=1)
            reduced = signal.resample_poly(np.nan_to_num(overlap, posinf=0, neginf=0),
                                           1, FS // LOW_FS, axis=1, padtype="constant")
            arrays["low"].append(reduced[:, PAD // (FS // LOW_FS):][:, :LOW_FS].astype("float32"))
            history = x[:, -PAD:].copy()
            b = x.reshape(12, 10, FS // 10)
            means = b.reshape(12, 10, 100, FS // 1000).mean(axis=3)
            sr = means.std(axis=2)
            rms = b.std(axis=2)
            arrays["slow_mean"].append((b.mean(axis=2) + offset[:, None]).T)
            arrays["broadband_rms"].append(rms.T)
            arrays["subkhz_rms"].append(sr.T)
            arrays["fast_residual_rms"].append(np.sqrt(np.maximum(rms**2 - sr**2, 0)).T)
            arrays["difference_rms"].append(np.sqrt(np.mean(np.diff(b, axis=2)**2, axis=2) / 2).T)
            arrays["second_bad"].append(second_bad)
            arrays["second_flat"].append(np.mean(np.diff(x, axis=1) == 0, axis=1))
            ft = fft.rfft((x - x.mean(axis=1, keepdims=True)) * WINDOW, axis=1, workers=2)
            psd = np.abs(ft)**2 / NORM
            psd[:, 1:-1] *= 2
            bp = np.column_stack([psd[:, s].sum(axis=1) for s in SLICES])
            arrays["bandpower"].append(bp[:, :len(BANDS)])
            arrays["extra_power"].append(bp[:, len(BANDS):])
            arrays["small_psd"].append(psd[:, :2001].astype("float32"))
            epoch += psd
            in_epoch += 1
            if in_epoch == 5:
                arrays["epoch_psd"].append((epoch / in_epoch).astype("float32"))
                arrays["epoch_counts"].append(in_epoch)
                epoch.fill(0)
                in_epoch = 0

        for chunk in td.data_chunks():
            cc = chunk[group.name].channels()
            if not cc or not len(cc[0]):
                continue
            if [c.name for c in cc] != names or any(int(c.offset) != seen for c in cc):
                raise ValueError(f"TDMS discontinuity at {seen}: {path}")
            x = np.stack([c[:] for c in cc]).astype("float64", copy=False)
            seen += x.shape[1]
            if offset is None:
                offset = np.where(np.isfinite(x[:, 0]), x[:, 0], 0.0)
            x -= offset[:, None]
            finite = np.isfinite(x)
            safe = np.where(finite, x, 0.0)
            bad += (~finite).sum(axis=1)
            global_sum += safe.sum(axis=1)
            global_square += np.einsum("ij,ij->i", safe, safe)
            lo = np.minimum(lo, np.min(np.where(finite, x, np.inf), axis=1))
            hi = np.maximum(hi, np.max(np.where(finite, x, -np.inf), axis=1))
            dx = np.diff(safe, axis=1, prepend=safe[:, :1] if last is None else last)
            if last is None:
                flat -= 1
            flat += (dx == 0).sum(axis=1)
            diff_square += np.einsum("ij,ij->i", dx, dx)
            last = safe[:, -1:].copy()
            carry = np.concatenate((carry, x), axis=1)
            start = 0
            while carry.shape[1] - start >= FS + PAD:
                consume(carry[:, start:start + FS], carry[:, start + FS:start + FS + PAD])
                start += FS
            if start:
                carry = carry[:, start:].copy()
        if seen != count:
            raise ValueError(f"Read {seen} rather than {count} samples/channel: {path}")
        if carry.shape[1] >= FS:
            consume(carry[:, :FS], carry[:, FS:])
        if in_epoch:
            arrays["epoch_psd"].append((epoch / in_epoch).astype("float32"))
            arrays["epoch_counts"].append(in_epoch)
        if len(arrays["bandpower"]) != count // FS:
            raise ValueError(f"Incorrect number of feature windows: {path}")
        valid_count = np.maximum(count - bad, 1)
        sd = np.sqrt(np.maximum(global_square / valid_count - (global_sum / valid_count)**2, 0))
        stats = [dict(std=sd[j], difference_rms=np.sqrt(diff_square[j] / (count - 1)),
                      range=hi[j] - lo[j], flat_difference_fraction=flat[j] / (count - 1),
                      nonfinite_fraction=bad[j] / count, minimum_v=lo[j] + offset[j],
                      maximum_v=hi[j] + offset[j], mean_v=global_sum[j] / valid_count[j] + offset[j])
                 for j in range(12)]
        packed = {name: np.stack(items) for name, items in arrays.items()}
        for name in KEYS:
            packed[name] = packed[name].reshape(-1, 12)
        packed["low"] = np.concatenate(arrays["low"], axis=1)
        meta["health"] = assess_channel_quality(dict(
            channel_names=names, health=stats, welch_segment_bandpower=packed["bandpower"][:, :, 3:8]))
        for row, stat in zip(meta["health"], stats):
            row.update(stat)
        target.mkdir(parents=True, exist_ok=True)
        np.savez(target / "features.npz", **packed, low_offset_v=offset)
        (target / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        print(f"{target.name}: {meta['duration_s']:.3f} s; "
              f"suspect {[r['channel_index'] for r in meta['health'] if r['automatic_suspect']]}",
              flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=RAW)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--case", action="append")
    parser.add_argument("--background", type=Path,
                        help="Optional separate November 10 background TDMS, not a pump recording")
    args = parser.parse_args()
    sources = inventory(args.raw)
    if args.background is not None:
        sources.append(("back", args.background))
    if args.case is not None and set(args.case) - {case for case, _ in sources}:
        parser.error("Unknown case; processing back requires --background")
    for case, path in sources:
        if args.case is None or case in args.case:
            extract(path, args.out / "cache" / case)


if __name__ == "__main__":
    main()
