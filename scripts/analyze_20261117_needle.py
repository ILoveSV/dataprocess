"""Offline pulse and gate audit for the November 17 TC1 recordings."""

from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from nptdms import TdmsFile
from scipy import fft, signal
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/20261117_needle"
RAW, = Path("D:/Lab/raw/raw").glob("11.17*")
FS = 400_000
N = FS // 10
W = signal.windows.hann(N, sym=False)
F = fft.rfftfreq(N, 1/FS)
BANDS = [(20,100),(100,1000),(1000,20000),(20000,80000),(80000,199900)]


def extract(p, cache):
    if cache.exists():
        with np.load(cache) as z:
            return dict(z)
    means, rms, peak, dv, power, spans = [], [], [], [], [], []
    with TdmsFile.open(p) as f:
        g, = f.groups()
        ch = g.channels()
        n = len(ch[0])
        assert len(ch) == 12 and not f.file_status.incomplete_final_segment
        assert all(len(c) == n and np.isclose(c.properties["wf_increment"],1/FS) for c in ch)
        offset, carry, seen = None, np.empty((12, 0)), 0
        minimum, maximum = np.full(12,np.inf), np.full(12,-np.inf)
        for chunk in f.data_chunks():
            cc = chunk[g.name].channels()
            if not cc or not len(cc[0]):
                continue
            assert all(c.offset == seen and c.name == ref.name for c, ref in zip(cc,ch))
            x = np.stack([c[:] for c in cc])
            assert np.isfinite(x).all()
            seen += x.shape[1]
            minimum = np.minimum(minimum,x.min(axis=1))
            maximum = np.maximum(maximum,x.max(axis=1))
            if offset is None:
                offset = x[:, :1].copy()
            x -= offset
            carry = np.concatenate((carry,x),axis=1)
            count = carry.shape[1]//N
            for i in range(count):
                a = carry[:,i*N:(i+1)*N]
                b = a.reshape(12,100,400)
                m = b.mean(axis=2)
                means.append(m.T + offset.T)
                rms.append(b.std(axis=2).T)
                peak.append(np.max(abs(b-m[:,:,None]),axis=2).T)
                # Include differences at the 1 ms bin boundary.
                prev = a[:, :1] if not spans else spans[-1]
                dv.append(np.max(abs(np.diff(a,axis=1,prepend=prev)).reshape(12,100,400),axis=2).T)
                spans.append(a[:,-1:].copy())
                ft = fft.rfft((a-a.mean(axis=1,keepdims=True))*W,axis=1,workers=2)
                v = abs(ft)**2 * (2/(W@W*N))
                power.append(np.column_stack([v[:,(F>=l)&(F<h)].sum(axis=1) for l,h in BANDS]))
            if count:
                carry = carry[:,count*N:].copy()
        assert seen==n
    z = dict(means=np.concatenate(means),rms=np.concatenate(rms),peak=np.concatenate(peak),
             dv=np.concatenate(dv),power=np.stack(power),duration=n/FS,minimum=minimum,
             maximum=maximum,channels=[c.name for c in ch])
    np.savez(cache,**z)
    return z


def audit(z, key):
    rm, mean, dv = z["rms"], z["means"], z["dv"]
    ref = np.r_[0:1000,len(rm)-1000:len(rm)]
    r0 = np.median(rm[ref],axis=0)
    bias = np.median(mean[ref],axis=0)
    healthy = (r0 > 1e-8) & (r0 < 4*np.median(r0)) & (abs(bias-np.median(bias))<.5)
    assert healthy.sum()>=4
    ratio = dv / np.maximum(np.quantile(dv[ref],.99,axis=0),1e-12)
    pulse = np.sort(ratio[:,healthy],axis=1)[:,-3]
    # Consecutive threshold crossings within 20 ms count as a single cluster.
    hits = np.flatnonzero(pulse>=5)
    clusters = np.split(hits,np.flatnonzero(np.diff(hits)>20)+1) if len(hits) else []
    events = []
    for group in clusters:
        i = group[pulse[group].argmax()]
        events.append(key|dict(t_s=(i+.5)/1000,score=pulse[i],n_channels=int((ratio[i,healthy]>=5).sum()),
                               peak_max_mv=float(1e3*z["peak"][i,healthy].max()),
                               in_edge_reference=bool(i<1000 or i>=len(rm)-1000)))
    p = z["power"][:,healthy]
    p0 = np.median(np.concatenate((p[:10],p[-10:])),axis=0)
    change = np.median(10*np.log10(np.maximum(p,1e-30)/np.maximum(p0,1e-30)),axis=1)
    n = len(p)
    # Search independently for abrupt changes and for a sustained two-edge gate.
    slow = np.median(mean.reshape(n,100,12),axis=1)[:,healthy]*1e6
    slow -= np.median(np.concatenate((slow[:10],slow[-10:])),axis=0)
    t = np.arange(n)/10+.05
    edge = np.full(n,np.nan)
    for i in range(5,n-5):
        edge[i] = np.median(abs(slow[i:i+5].mean(0)-slow[i-5:i].mean(0)))
    best = None
    for a in range(10,n-30):
        for b in range(a+20,n-9):
            pre, act, post = slow[:a],slow[a:b],slow[b:]
            left,right = act.mean(0)-pre.mean(0),act.mean(0)-post.mean(0)
            persistent = np.maximum(np.minimum(left,right),np.minimum(-left,-right))
            score = np.median(persistent)
            if best is None or score>best[0]:
                best=(float(score),a/10,b/10)
    trace = pd.DataFrame(dict(t_s=t, pulse_q3=pulse.reshape(n,100).max(1),edge_uv=edge,
                              dc_median_uv=np.median(slow,axis=1)))
    for i in range(len(BANDS)):
        trace[f"band{i}_db"]=change[:,i]
    row = key|dict(duration_s=float(z["duration"]), channels=";".join(map(str,np.flatnonzero(healthy)+1)),
                   clusters=len(events), interior_clusters=sum(not e["in_edge_reference"] for e in events),
                   ref_clusters=sum(e["in_edge_reference"] for e in events),
                   pulse_max=float(pulse.max()), peak_mv=float(1e3*z["peak"][:,healthy].max()),
                   edge_max_uv=float(np.nanmax(edge)), gate_uv=best[0],gate_start_s=best[1],gate_end_s=best[2])
    for i in range(len(BANDS)):
        row[f"band{i}_p90_db"]=float(np.quantile(change[10:-10,i],.9))
    return row,events,trace


def main():
    cache = OUT/"cache"
    cache.mkdir(parents=True,exist_ok=True)
    rows, events, traces, logs, causal = [], [], [], {}, []
    for d in sorted(RAW.iterdir()):
        if not d.is_dir():
            continue
        pos = "NW" if "\u897f\u5317" in d.name else "N"
        logs[pos]=(d/"log.txt").read_text(encoding="utf-8-sig")
        for folder in sorted(d.glob("*kv")):
            kv=int(folder.name[:-2])
            for i,p in enumerate(sorted(folder.glob("*.tdms")),1):
                case=f"{pos}_{kv:02}kV_{i:02}"
                z=extract(p,cache/f"{case}.npz")
                key=dict(case=case,position=pos,distance_m=1.5 if pos=="NW" else 1.8,
                         voltage_kv=kv,group_current_reported=kv in (10,15),source=str(p))
                row,ev,tr=audit(z,key)
                jumps = z["dv"][:,:11]
                scaled = jumps / np.maximum(np.quantile(jumps[:1000],.99,axis=0),1e-12)
                score = np.sort(scaled,axis=1)[:,-3]
                hits = np.flatnonzero(score[1000:]>=5)+1000
                causal.append(key|dict(max_score=float(score[1000:].max()),
                                       first_alarm_end_s=(hits[0]+1)/1000 if len(hits) else None))
                rows.append(row)
                events.extend(ev)
                traces.append(tr.assign(case=case))
                print(case,round(row["duration_s"],2),row["clusters"],round(row["pulse_max"],2),
                      round(row["gate_uv"],2),flush=True)
    r=pd.DataFrame(rows)
    pred, strong = [], []
    sets={"pulse":["pulse_max","interior_clusters","peak_mv"],
          "slow":["edge_max_uv","gate_uv"],"bands":[f"band{i}_p90_db" for i in range(len(BANDS))]}
    for test in sorted(r.position.unique()):
        tr = r[r.position.ne(test)]
        lower = tr[tr.voltage_kv.ne(15)].pulse_max.max()
        upper = tr[tr.voltage_kv.eq(15)].pulse_max.min()
        threshold = float(np.sqrt(lower*upper))
        for row in r[r.position.eq(test)].itertuples():
            strong.append(dict(case=row.case, held_out_position=test, voltage_kv=row.voltage_kv,
                               threshold=threshold, score=row.pulse_max,
                               predicted_strong=row.pulse_max>=threshold))
        for name,cols in sets.items():
            train=r.position.ne(test)
            x=r[cols].copy()
            if name!="bands":
                x=np.log1p(x.clip(lower=0))
            model=make_pipeline(StandardScaler(),LogisticRegression(class_weight="balanced",C=.3))
            y=r.group_current_reported
            model.fit(x[train],y[train])
            for j,v in zip(r.index[~train],model.predict_proba(x[~train])[:,1]):
                pred.append(dict(case=r.case[j],held_out_position=test,model=name,
                                 group_current_reported=y[j],score=v,predicted=v>=.5))
    r.to_csv(OUT/"records.csv",index=False)
    pd.DataFrame(events).to_csv(OUT/"pulse_candidates.csv",index=False)
    pd.concat(traces).to_csv(OUT/"time_features.csv",index=False)
    pd.DataFrame(pred).to_csv(OUT/"held_out_position.csv",index=False)
    pd.DataFrame(strong).to_csv(OUT/"strong_pulse_transfer.csv",index=False)
    pd.DataFrame(causal).to_csv(OUT/"first_second_replay.csv",index=False)
    (OUT/"log_transcription.json").write_text(json.dumps(logs,ensure_ascii=False,indent=2),encoding="utf-8")
    fig, axes = plt.subplots(1,2,figsize=(10,3.8))
    for pos, marker, shift in [("N","o",-.27),("NW","s",.27)]:
        q = r[r.position.eq(pos)]
        for kv, grp in q.groupby("voltage_kv"):
            axes[0].scatter(kv+shift+np.linspace(-.16,.16,len(grp)),grp.pulse_max,marker=marker,
                            label=pos if kv==5 else None)
    axes[0].axhline(5,color="gray",ls="--")
    axes[0].set(xlabel="Nominal voltage (kV)", ylabel="Record peak: third-channel jump ratio",
                xticks=[5,10,15],yscale="log")
    axes[0].legend()
    for trace in traces:
        case=trace.case.iloc[0]
        if case in ("N_05kV_01","N_10kV_03","N_15kV_01","NW_15kV_01"):
            axes[1].plot(trace.t_s,trace.pulse_q3,label=case,lw=1)
    axes[1].axhline(5,color="gray",ls="--")
    axes[1].set(xlabel="Time from start (s)",ylabel="Max jump ratio per 0.1 s",yscale="log")
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT/"pulse_comparison.png",dpi=160)
    plt.close(fig)


if __name__=="__main__":
    main()
