"""Compare TC1 backgrounds and pulse behavior with identical window estimators."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from nptdms import TdmsFile
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from analyze_20261117_needle import FS, OUT as NEW, extract

OUT = NEW / "tc1_comparison"
LAB = Path("D:/Lab/raw/raw")
BANDS = ["20_100Hz","100_1kHz","1_20kHz","20_80kHz","80_199p9kHz"]
COMMON = np.arange(11)
BASE_CHANNELS = [4,6,8,9,10]


def cases():
    for day, folders in [("26.7.31",["tc1"]),("26.8.6",["tc1duo","tc1duo2","tc1vfd"])]:
        for name in folders:
            for path in sorted((LAB/day/name).rglob("*.tdms")):
                desc = path.parent.name.lower()
                role = "BG" if desc=="background" else ("STOP" if desc in ("vfd","vfdbackground") else "RUN")
                yield dict(case=f"{day}_{name}_{desc}", session=name, day=day, role=role, source=str(path)), path


def summarize(key, z, spans):
    bp = z["power"]
    rows = []
    for label, a, b in spans:
        a1,b1 = 100*a,100*b
        for j in range(12):
            rows.append(key|dict(segment=label, channel=j+1, n_windows=b-a,
                                 bias_v=np.median(z["means"][a1:b1,j]),
                                 rms_mv=1e3*np.median(z["rms"][a1:b1,j]),
                                 **{s:10*np.log10(v) for s,v in zip(BANDS,np.median(bp[a:b,j],axis=0))}))
    return rows


def baseline_tables(all_rows):
    metrics = ["rms_mv", *BANDS]
    x = all_rows[all_rows.channel.isin(BASE_CHANNELS)]
    use = x.role.isin(["BG","STOP"]) & x.segment.str.match(r"^t\d+$")
    use |= x.day.eq("26.11.17") & x.segment.isin(["first1","last1","first2","last2"])
    x = x[use]
    keys = ["day","session","role","case","segment"]
    a = x.groupby(keys,as_index=False)[metrics].median()
    a.to_csv(OUT/"baseline_windows.csv",index=False)
    primary = a[a.role.isin(["BG","STOP"]) | a.segment.isin(["first1","last1"])]
    rows=[]
    for key,g in primary.groupby(["day","session","role"],sort=False):
        for m in metrics:
            g0=g.groupby("case")[m].median()
            rows.append(dict(zip(["day","session","role"],key))|dict(metric=m,
                        records=len(g0),windows=len(g),center=g0.median(),
                        q10=g[m].quantile(.1),q90=g[m].quantile(.9)))
    pd.DataFrame(rows).to_csv(OUT/"baseline_summary.csv",index=False)
    # One observation per record; disjoint old dates and new positions in each fold.
    q = primary[primary.role.ne("STOP")].groupby(["day","session","case"])[BANDS].median().reset_index()
    y = q.day.eq("26.11.17")
    pred=[]
    for old in ("26.7.31","26.8.6"):
        for pos in ("N","NW"):
            test=(~y & q.day.eq(old)) | (y & q.session.eq(pos))
            for name, cols in [("low",BANDS[:2]),("high",BANDS[2:]),("all",BANDS)]:
                m=make_pipeline(StandardScaler(),LogisticRegression(C=.1,class_weight="balanced"))
                m.fit(q.loc[~test,cols],y[~test])
                for row, pr in zip(q[test].itertuples(),m.predict(q.loc[test,cols])):
                    pred.append(dict(case=row.case,old_date_held_out=old,new_position_held_out=pos,
                                     features=name,is_nov17=row.day=="26.11.17",predicted_nov17=pr))
    pd.DataFrame(pred).to_csv(OUT/"background_transfer.csv",index=False)


def pulse_summary(key,z,ref):
    x = z["dv"][:,COMMON]
    v = np.sort(x / np.maximum(ref,1e-12),axis=1)[:,-3]
    hits = np.flatnonzero(v>=5)
    groups = np.split(hits,np.flatnonzero(np.diff(hits)>20)+1) if len(hits) else []
    if len(hits):
        best = int(v.argmax())
        strongest = np.sum(x[best]/ref>=5)
    else:
        strongest = 0
    return key|dict(duration_s=float(z["duration"]), pulse_score_max=v.max(),
                    pulse_bins=len(hits), pulse_clusters=len(groups),
                    channels_at_max=strongest, peak_abs_mv=1e3*z["peak"][:,COMMON].max(),
                    longest_cluster_span_ms=int(max((g[-1]-g[0]+1 for g in groups),default=0)))


def pulse_shape():
    events = pd.read_csv(NEW/"pulse_candidates.csv").sort_values("score")
    rows=[]
    for r in events.drop_duplicates("case",keep="last").itertuples():
        i=int(r.t_s*FS)
        with TdmsFile.open(r.source) as f:
            x=np.stack([c[i-4000:i+8000] for c in f.groups()[0].channels()[:11]])
        d=x-np.median(x[:,:1000],axis=1)[:,None]
        count=np.sum(d<-.1,axis=0)
        rows.append(dict(case=r.case,peak_window_s=r.t_s,
                         time_ge8_below_minus100mv_us=np.sum(count>=8)/FS*1e6,
                         channel_min_time_spread_us=np.ptp(np.argmin(d,axis=1))/FS*1e6))
    pd.DataFrame(rows).to_csv(OUT/"strong_pulse_shape.csv",index=False)


def band_behavior(overview):
    old = overview[overview.segment.eq("full") & overview.channel.isin(BASE_CHANNELS)]
    stop = old[old.role.eq("STOP")][["session","channel",*BANDS]]
    run = old[old.role.eq("RUN")].merge(stop,on=["session","channel"],suffixes=("","_stop"),
                                       validate="many_to_one")
    for name in BANDS:
        run[name] -= run[name+"_stop"]
    run.groupby(["day","session","case"])[BANDS].median().to_csv(OUT/"pump_run_minus_stop_db.csv")
    ev = pd.read_csv(NEW/"pulse_candidates.csv").sort_values("score").drop_duplicates("case",keep="last")
    tr = pd.read_csv(NEW/"time_features.csv")
    rows=[]
    for r in ev.itertuples():
        t=tr[tr.case.eq(r.case)]
        k=(t.t_s-r.t_s).abs().idxmin()
        q=t[abs(t.t_s-r.t_s)>.2]
        rows.append(dict(case=r.case,time_s=r.t_s,
                         **{f"event_{name}_db":t.loc[k,f"band{i}_db"] for i,name in enumerate(BANDS)},
                         **{f"away_{name}_db":q[f"band{i}_db"].median() for i,name in enumerate(BANDS)}))
    pd.DataFrame(rows).to_csv(OUT/"needle_event_vs_remainder_db.csv",index=False)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--baseline-only",action="store_true")
    a=p.parse_args()
    cache=OUT/"cache"
    cache.mkdir(parents=True,exist_ok=True)
    rows,pulses=[],[]
    refs={}
    with np.load(next((NEW/"cache").glob("*.npz"))) as z:
        names = z["channels"]
    for key,path in cases():
        if a.baseline_only and key["role"]=="RUN":
            continue
        z=extract(path,cache/f"{key['case']}.npz")
        assert np.array_equal(z["channels"],names), key["case"]
        n=len(z["power"])
        spans=[("full",0,n),("first1",0,10),("last1",n-10,n)]
        if key["role"] in ("BG","STOP"):
            spans += [(f"t{t}",t*10,(t+1)*10) for t in range(1,n//10-1)]
        rows.extend(summarize(key,z,spans))
        if key["role"]=="BG":
            refs[key["session"]]=np.quantile(z["dv"][:,COMMON],.99,axis=0)
        print(key["case"],n,flush=True)
    for key,path in cases():
        c=cache/f"{key['case']}.npz"
        if c.exists() and (not a.baseline_only or key["role"]!="RUN"):
            z=extract(path,c)
            pulses.append(pulse_summary(key,z,refs[key["session"]]))
    for row in pd.read_csv(NEW/"records.csv").itertuples():
        z=extract(Path(row.source),NEW/"cache"/f"{row.case}.npz")
        key=dict(case=row.case,session=row.position,day="26.11.17",role=f"{row.voltage_kv}kV",source=row.source)
        n=len(z["power"])
        spans=[("first1",0,10),("last1",n-10,n),("first2",0,20),("last2",n-20,n)]
        rows.extend(summarize(key,z,spans))
        pulses.append(pulse_summary(key,z,np.quantile(z["dv"][:1000,COMMON],.99,axis=0)))
    overview = pd.DataFrame(rows)
    overview.to_csv(OUT/"background_channels.csv",index=False)
    if not a.baseline_only:
        baseline_tables(overview)
        pulse_shape()
        band_behavior(overview)
    pd.DataFrame(pulses).to_csv(OUT/"pulse_comparison.csv",index=False)


if __name__=="__main__":
    main()
