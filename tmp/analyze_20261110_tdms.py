from pathlib import Path

import numpy as np
from nptdms import TdmsFile
from scipy import fft


ROOT = Path(r"D:\Lab\raw\raw\26.11.10")
OUT = Path(__file__).resolve().parent / "20261110_tdms"
BANDS = [(4, 100), (100, 1000), (1000, 20000), (20000, 80000), (80000, 199900)]


def analyze(path):
    target = OUT / (path.parent.name + ".npz")
    if target.exists():
        return
    with TdmsFile.open(path) as tdms:
        channels = tdms.groups()[0].channels()
        rate = round(1 / channels[0].properties["wf_increment"])
        count = len(channels)
        assert all(len(ch) == len(channels[0]) for ch in channels)
        assert not tdms.file_status.incomplete_final_segment
        block = rate // 4
        f = fft.rfftfreq(block, 1 / rate)
        window = np.hanning(block + 1)[:-1]
        norm = rate * (window @ window)
        spec_buffer = []
        spectra = []
        spectrum_counts = []
        means, stds, peaks, bands = [], [], [], []
        total = np.zeros(count)
        square = np.zeros(count)
        delta_square = np.zeros(count)
        flat = np.zeros(count)
        nonfinite = np.zeros(count)
        lo = np.full(count, np.inf)
        hi = np.full(count, -np.inf)
        carry = np.empty((count, 0))
        last = None
        samples = 0
        for chunk in tdms.data_chunks():
            x = np.stack([chunk[ch.group_name][ch.name][:] for ch in channels])
            if not x.shape[1]:
                continue
            samples += x.shape[1]
            finite = np.isfinite(x)
            nonfinite += (~finite).sum(axis=1)
            x = np.where(finite, x, 0.0)
            total += x.sum(axis=1)
            square += np.einsum("ij,ij->i", x, x)
            lo = np.minimum(lo, x.min(axis=1))
            hi = np.maximum(hi, x.max(axis=1))
            dx = np.diff(x, axis=1, prepend=x[:, :1] if last is None else last)
            delta_square += np.einsum("ij,ij->i", dx, dx)
            flat += (dx == 0).sum(axis=1)
            last = x[:, -1:].copy()
            carry = np.concatenate((carry, x), axis=1)
            if carry.shape[1] < block:
                continue
            part, carry = carry[:, :block], carry[:, block:].copy()
            assert carry.shape[1] < block
            by_10ms = part.reshape(count, 25, rate // 100)
            means.append(by_10ms.mean(axis=2))
            stds.append(by_10ms.std(axis=2))
            peaks.append(np.max(np.abs(by_10ms - means[-1][..., None]), axis=2))
            transform = fft.rfft((part - part.mean(axis=1, keepdims=True)) * window,
                                 axis=1, workers=2)
            psd = np.abs(transform) ** 2 / norm
            psd[:, 1:-1] *= 2
            bands.append(np.stack([psd[:, (f >= left) & (f < right)].sum(axis=1) * 4
                                   for left, right in BANDS], axis=1))
            spec_buffer.append(psd)
            if len(spec_buffer) == 16:
                spectra.append(np.mean(spec_buffer, axis=0).astype(np.float32))
                spectrum_counts.append(len(spec_buffer))
                spec_buffer.clear()
            if len(bands) % 120 == 0:
                print(path.parent.name, len(bands) / 4, "s", flush=True)
        if spec_buffer:
            spectra.append(np.mean(spec_buffer, axis=0).astype(np.float32))
            spectrum_counts.append(len(spec_buffer))
        assert samples == len(channels[0])
        np.savez(target, means=np.concatenate(means, axis=1), stds=np.concatenate(stds, axis=1),
                 peaks=np.concatenate(peaks, axis=1), bands=np.stack(bands),
                 spectra=np.stack(spectra), spectrum_counts=spectrum_counts, frequencies=f,
                 samples=samples, rate=rate, channels=[ch.name for ch in channels],
                 standard_deviation=np.sqrt(np.maximum(square / samples - (total / samples)**2, 0)),
                 difference_rms=np.sqrt(delta_square / (samples - 1)), lo=lo, hi=hi,
                 flat=flat / samples, nonfinite=nonfinite / samples)
        print(path.parent.name, samples / rate, "s finished", flush=True)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for case in ("35ma", "3v5ma2min", "back-to3v5ma"):
        paths = list((ROOT / case).glob("*.tdms"))
        assert len(paths) == 1
        analyze(paths[0])
