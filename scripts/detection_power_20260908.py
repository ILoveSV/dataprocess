"""Known-frequency, output-domain software injection. No physical calibration."""
from pathlib import Path
import json, hashlib
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/thesis_completion_20260908/detection'; OUT.mkdir(exist_ok=True)
protocol=dict(version=1,frequencies_hz=[1/3.1,.1,.05],durations_s=[20,40,60],minimum_cycles=2,
 amplitudes_uv_peak=[0,.01,.03,.1,.3,1,3,10,30,100,300,1000],phase_count=64,
 maximum_nonoverlapping_windows_per_record=6,threshold_quantile=.95,
 threshold_rule='Same detector, leave entire arrangement group out; inverse empirical CDF with equal record weights',
 statistic='OLS intercept + linear trend + cosine + sine; peak amplitude in slow_mean output domain',
 channel_rule='Previously frozen common healthy channels: CSV uses 1-based indices, converted to zero-based for arrays; coherent equal-channel injection',
 aggregation='Equal records, then equal windows and 64 equally spaced phases; no independent-experiment CI',
 scope='16 archived pump BG/STOP records, 2 dates; does not calibrate cathodic field strength or raw-input transfer')
(OUT/'protocol.json').write_text(json.dumps(protocol,indent=2,ensure_ascii=False),encoding='utf8')
f=pd.read_csv(ROOT/'results/coherence_precision_audit_20260908/features.csv')
f=f[f.config.eq('full64_common') & f.condition.isin(['background','vfd_stop'])].copy()
assert len(f)==16, f[['case_id','condition']]
ch=pd.read_csv(ROOT/'results/coherence_precision_audit_20260908/channel_sets.csv').set_index('case_id')
manifest=[]; windows=[]; signals={}; checks=[]
for r in f.itertuples():
 base=ROOT/('results/experiment_20260731/tdms/exact_archive' if str(r.dataset)=='20260731' else 'results/experiment_20260806/exact_archive')/r.case_id
 m=json.loads((base/'metadata.json').read_text(encoding='utf8'))
 z=np.load(base/'envelopes.npz'); fs=float(z['envelope_rate_hz']); x=z['slow_mean']; channels=[c-1 for c in json.loads(ch.loc[r.case_id,'common'])]
 assert x.dtype==np.float64 and x.shape[1]==12 and max(channels)<12
 t=m['lowpass_filter']['analysis_rate_first_sample_time_s']+np.arange(len(x))/fs
 keep=(t>=m['config']['trim_start_seconds']) & (t<=m['duration_s']-m['config']['trim_end_seconds'])
 y=x[keep][:,channels].mean(axis=1)*1e6; t=t[keep]
 manifest.append(dict(case_id=r.case_id,group=r.group,detector=r.detector,condition=r.condition,fs=fs,n_stable=len(y),channels=str(channels),source=str((base/'envelopes.npz').relative_to(ROOT)),sha256=hashlib.sha256((base/'envelopes.npz').read_bytes()).hexdigest()))
 for T in protocol['durations_s']:
  n=round(T*fs); starts=np.arange(0,len(y)-n+1,n,dtype=int)
  if len(starts)>6: starts=starts[np.unique(np.linspace(0,len(starts)-1,6).round().astype(int))]
  for start in starts:
   tt=np.arange(n)/fs; yy=y[start:start+n]; yy=yy-yy.mean()
   for freq in protocol['frequencies_hz']:
    if freq*T<2-1e-9: continue
    X=np.column_stack([np.ones(n),tt-tt.mean(),np.cos(2*np.pi*freq*tt),np.sin(2*np.pi*freq*tt)])
    beta=np.linalg.lstsq(X,yy,rcond=None)[0][-2:]
    key=len(windows)
    windows.append(dict(window_id=key,case_id=r.case_id,group=r.group,detector=r.detector,condition=r.condition,T_s=T,f_hz=freq,start_s=float(t[start]),cos_uv=beta[0],sin_uv=beta[1],null_amplitude_uv=float(np.linalg.norm(beta))))
    if len(checks)<10:
     A=3.; phase=.71; injected=yy+A*np.cos(2*np.pi*freq*tt+phase)
     actual=np.linalg.lstsq(X,injected,rcond=None)[0][-2:]
     expected=beta+A*np.array([np.cos(phase),-np.sin(phase)])
     checks.append(float(np.max(np.abs(actual-expected))))
w=pd.DataFrame(windows); rows=[]; thresholds=[]
ph=np.arange(64)*2*np.pi/64; unit=np.column_stack([np.cos(ph),-np.sin(ph)])
for (det,T,freq,group),test in w.groupby(['detector','T_s','f_hz','group']):
 train=w[w.detector.eq(det)&w.T_s.eq(T)&np.isclose(w.f_hz,freq)&w.group.ne(group)].copy()
 assert set(train.case_id).isdisjoint(test.case_id)
 train['weight']=1/train.groupby('case_id').window_id.transform('count')/train.case_id.nunique()
 train=train.sort_values('null_amplitude_uv'); cdf=train.weight.cumsum().to_numpy()
 threshold=float(train.null_amplitude_uv.iloc[min(np.searchsorted(cdf,.95),len(train)-1)])
 thresholds.append(dict(detector=det,T_s=T,f_hz=freq,held_group=group,threshold_uv_peak=threshold,calibration_records=train.case_id.nunique(),calibration_windows=len(train),test_records=test.case_id.nunique()))
 for case,z in test.groupby('case_id'):
  b=z[['cos_uv','sin_uv']].to_numpy()
  for A in protocol['amplitudes_uv_peak']:
   hits=np.linalg.norm(b[:,None,:]+A*unit[None,:,:],axis=2)>threshold
   rows.append(dict(detector=det,T_s=T,f_hz=freq,case_id=case,group=group,amplitude_uv_peak=A,detection_probability=float(hits.mean()),windows=len(z),threshold_uv_peak=threshold))
r=pd.DataFrame(rows); curves=[]; summary=[]
for (det,T,freq),z in r.groupby(['detector','T_s','f_hz']):
 vals=[]
 for A,q in z.groupby('amplitude_uv_peak',sort=True):
  row=dict(detector=det,T_s=T,f_hz=freq,amplitude_uv_peak=A,power=q.detection_probability.mean(),minimum_record_power=q.detection_probability.min(),maximum_record_power=q.detection_probability.max(),records=q.case_id.nunique())
  curves.append(row); vals.append(row)
 qualifying=[v['amplitude_uv_peak'] for i,v in enumerate(vals) if all(x['power']>=.9 for x in vals[i:])]
 all_record=[v['amplitude_uv_peak'] for i,v in enumerate(vals) if all(x['minimum_record_power']>=.9 for x in vals[i:])]
 summary.append(dict(detector=det,T_s=T,f_hz=freq,records=z.case_id.nunique(),heldout_null_false_alarm=vals[0]['power'],minimum_tested_amplitude_for_mean_power90_uv_peak=min(qualifying) if qualifying else None,minimum_tested_amplitude_for_all_records_power90_uv_peak=min(all_record) if all_record else None,threshold_min_uv=z.threshold_uv_peak.min(),threshold_max_uv=z.threshold_uv_peak.max()))
for name,df in [('noise_manifest',pd.DataFrame(manifest)),('window_statistics',w),('thresholds',pd.DataFrame(thresholds)),('record_power',r),('power_curves',pd.DataFrame(curves)),('power_summary',pd.DataFrame(summary))]:df.to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig')
assert max(checks)<1e-8
(OUT/'verification.json').write_text(json.dumps(dict(noise_records=len(f),independent_dates=2,ols_injection_max_error_uv=max(checks),train_test_record_overlap=0,phase_count=64,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2),encoding='utf8')
print(pd.DataFrame(summary).to_string(index=False))
