import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import ndimage, signal

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from channel_quality import assess_channel_quality


HERE = Path(__file__).resolve().parent
CASES = ("back-to3v5ma", "3v5ma2min", "35ma")


def prepare(case):
    data = dict(np.load(HERE / "20261110_tdms" / f"{case}.npz"))
    health = [
        dict(std=a, difference_rms=b, range=c, flat_difference_fraction=d,
             nonfinite_fraction=e)
        for a, b, c, d, e in zip(data["standard_deviation"], data["difference_rms"],
                                 data["hi"] - data["lo"], data["flat"], data["nonfinite"])
    ]
    quality = assess_channel_quality(dict(channel_names=data["channels"], health=health,
                                          welch_segment_bandpower=data["bands"]))
    data["excluded"] = [i for i, row in enumerate(quality) if row["automatic_suspect"]]
    data["used"] = [i for i, row in enumerate(quality) if not row["automatic_suspect"]]
    n = data["means"].shape[1] // 100
    data["dc"] = data["means"][:, :n * 100].reshape(12, n, 100).mean(axis=2).T * 1e6
    data["bands_1s"] = data["bands"][:n * 4].reshape(n, 4, 12, 5).mean(axis=1)
    return data


def edge_trace(dc, width=5):
    steps = np.full_like(dc, np.nan)
    for t in range(width, len(dc) - width + 1):
        steps[t] = dc[t:t + width].mean(axis=0) - dc[t - width:t].mean(axis=0)
    return steps


def scan(data, nominal, background):
    used = sorted(set(data["used"]) & set(background["used"]))
    dc = data["dc"][:, used]
    t = np.arange(len(dc)) + 0.5
    m = np.column_stack((np.ones_like(t), (t - t.mean()) / len(t)))
    q = np.linalg.qr(m)[0]
    y = dc - q @ (q.T @ dc)
    edges = edge_trace(dc)
    bg_edges = np.median(np.abs(edge_trace(background["dc"][:, used])), axis=1)
    print("background 5 s edge median |step| p50/p95/max",
          np.round(np.nanpercentile(bg_edges, [50, 95, 100]), 2))
    print("within-file 5 s edge median |step| p50/p95/max",
          np.round(np.nanpercentile(np.median(np.abs(edges), axis=1), [50, 95, 100]), 2))
    fits = []
    selected = []
    lp = data["bands_1s"][:, used]
    for a in range(10, len(t) - int(0.9 * nominal) - 9):
        for b in range(a + round(0.9 * nominal), min(len(t) - 9, a + round(1.1 * nominal) + 1)):
            gate = (t >= a) & (t < b)
            x = gate.astype(float) - q @ (q.T @ gate)
            beta = x @ y / (x @ x)
            local_a, local_b = edges[a], -edges[b]
            cosine = local_a @ local_b / (np.linalg.norm(local_a) * np.linalg.norm(local_b))
            edge_a, edge_b = np.median(abs(local_a)), np.median(abs(local_b))
            overlap = np.all(np.stack([beta * local_a > 0, beta * local_b > 0]), axis=0).sum()
            fits.append((a, b, np.median(abs(beta)), edge_a, edge_b, cosine, overlap,
                         np.median(beta), np.median((x @ y)**2 / (x @ x) / np.sum(y*y, axis=0))))
            # Three phase averages with 3 s removed around each candidate edge.
            before, during, after = [10 * np.log10(v.mean(axis=0)) for v in
                                     (lp[:a-3], lp[a+3:b-3], lp[b+3:])]
            vs_before, vs_after = np.median(during - before, axis=0), np.median(during - after, axis=0)
            persistent = np.maximum(np.minimum(vs_before, vs_after), np.minimum(-vs_before, -vs_after))
            selected.append((a, b, persistent))
    best_dc = max(fits, key=lambda v: v[2])
    best_edges = max(fits, key=lambda v: min(v[3], v[4]) * max(v[5], 0))
    print("candidate a,b, abs_dc, abs_edge1, abs_edge2, cosine, sign_matches, signed_dc, variance")
    print("largest fitted DC", np.round(best_dc, 3))
    print("strongest matching edges", np.round(best_edges, 3))
    if nominal == 120:
        print("23-143 s candidate", np.round(next(v for v in fits if v[:2] == (23, 143)), 3))
    print("max both-sided median changes by band across all candidate timings",
          np.round(np.max([r[2] for r in selected], axis=0), 4))
    return used


def narrow_metrics(data, used, center):
    f, s = data["frequencies"], data["spectra"][:, used, :]
    offsets = abs(f - center)
    peak = s[..., offsets <= 4].mean(axis=2)
    neighborhood = s[..., (offsets >= 16) & (offsets <= 96)].mean(axis=2)
    return 10 * np.log10(peak / neighborhood)


def line_scan(data, used, nominal):
    f = data["frequencies"]
    # Aggregate a 20 Hz band around each 4 Hz bin to allow small peak shifts.
    s = data["spectra"][:, used, :]
    s = s[data["spectrum_counts"] == 16]
    s = ndimage.uniform_filter1d(s, size=5, axis=2)
    cuts = np.arange(len(s)) * 4 + 2
    strong = []
    for a in range(12, int(cuts[-1] - nominal * .9 - 8), 4):
        for length in range(round(nominal * .9 / 4) * 4, round(nominal * 1.1 / 4) * 4 + 1, 4):
            b = a + length
            before, during, after = (cuts < a, (cuts > a) & (cuts < b), cuts > b)
            if min(before.sum(), after.sum()) < 3:
                continue
            p, q, r = [np.median(s[mask], axis=0) for mask in (before, during, after)]
            better = np.minimum(np.median(10 * np.log10(q / p), axis=0),
                                np.median(10 * np.log10(q / r), axis=0))
            prominence = np.median(10 * np.log10(q / ndimage.uniform_filter1d(q, 61, axis=1)), axis=0)
            idx = np.flatnonzero((f >= 1000) & (f < 199900) & (prominence > 3))
            if idx.size:
                i = idx[np.argmax(better[idx])]
                strong.append((better[i], f[i], a, b, prominence[i]))
    print("top narrow-line contrast (dB, Hz, a, b, local dB)", np.round(max(strong), 2) if strong else None)


def report(data):
    bg = data[CASES[0]]
    for case, nominal in zip(CASES[1:], (120, 60)):
        z = data[case]
        print(case, "excluded", [i + 1 for i in z["excluded"]])
        used = scan(z, nominal, bg)
        print("common channels", [i + 1 for i in used])
        for k in (10e3, 20e3, 30e3, 50e3):
            a = np.median(narrow_metrics(z, used, k), axis=1)
            b = np.median(narrow_metrics(bg, used, k), axis=1)
            print(k, "kHz line max, background max, >3dB blocks", np.round([max(a), max(b)], 2),
                  np.flatnonzero(a > 3) * 4)
        line_scan(z, used, nominal)
    morning = data[CASES[1]]
    used = sorted(set(bg["used"]) & set(morning["used"]))
    for a, b in [(0, 20), (20, 24), (24, 36), (36, 48), (48, 132), (140, 164), (168, 232)]:
        power = morning["bands_1s"][a:b, used].mean(axis=0)
        initial = morning["bands_1s"][:20, used].mean(axis=0)
        reference = bg["bands_1s"][:, used].mean(axis=0)
        diff = 10 * np.log10(power / initial)
        print("3V t=", a, b, "median against first 20 s", np.round(np.median(diff, axis=0), 3),
              "100-1000 vs background", np.round(np.median(10 * np.log10(power[:, 1] / reference[:, 1])), 3))


def plot(data):
    fig, axes = plt.subplots(3, 3, figsize=(15, 8), layout="constrained")
    bkg = data[CASES[0]]
    used = sorted(set.intersection(*(set(z["used"]) for z in data.values())))
    base = bkg["bands_1s"][:, used, 1].mean(axis=0)
    for col, (case, title) in enumerate(zip(CASES, ("Background", "3 V / 5 mA", "35ma recording (evening)"))):
        z = data[case]
        t = np.arange(len(z["dc"])) + 0.5
        dc = z["dc"][:, used]
        dc = dc - np.median(dc, axis=0)
        dc = np.apply_along_axis(lambda v: np.convolve(v, np.ones(5) / 5, mode="valid"), 0, dc)
        axes[0, col].plot(t[2:-2], dc, color="#9ca9b5", linewidth=.65, alpha=.65)
        axes[0, col].plot(t[2:-2], np.median(dc, axis=1), color="#173956", linewidth=1.5)
        axes[0, col].set_title(title, fontweight="bold", loc="left")
        band = 10 * np.log10(z["bands_1s"][:, used, 1] / base)
        axes[1, col].plot(t, np.median(band, axis=1), color="#a92039", linewidth=1.25)
        for center, color in zip((10e3, 20e3, 30e3), ("#20708c", "#b5612a", "#777b88")):
            v = np.median(narrow_metrics(z, used, center), axis=1)
            axes[2, col].plot(np.arange(len(v)) * 4 + 2, v, label=f"{center / 1e3:.0f} kHz",
                              color=color, linewidth=1)
        for ax in axes[:, col]:
            ax.set_xlim(0, int(z["samples"]) / int(z["rate"]))
            ax.grid(True, alpha=.2)
            if col == 1:
                ax.axvspan(26, 38, color="#eac780", alpha=.28, linewidth=0)
        axes[0, col].set_ylim(-80, 80)
        axes[1, col].set_ylim(-2, 4)
        axes[2, col].set_ylim(-2.2, 12)
        axes[2, col].set_xlabel("Time from recording start (s)")
    axes[0, 0].set_ylabel("5 s mean, centered (µV)")
    axes[1, 0].set_ylabel("100–1000 Hz power\nvs. background (dB)")
    axes[2, 0].set_ylabel("Line vs. local PSD (dB)")
    axes[2, 2].legend(loc="upper right", ncols=3, fontsize=8)
    output = HERE.parent / "analysis" / "cathodic_20261110"
    output.mkdir(exist_ok=True)
    fig.savefig(output / "discharge_diagnostics.png", dpi=175)
    plt.close(fig)


if __name__ == "__main__":
    data = {case: prepare(case) for case in CASES}
    plot(data)
    report(data)
