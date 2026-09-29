"""Frozen-protocol noise audit and one residual-MAD normalization comparison."""
from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];OLD=ROOT/'results/thesis_completion_20260908/detection';OUT=ROOT/'results/thesis_followup_20260909/noise'
OUT.mkdir(exist_ok=True,parents=True)
protocol={'baseline':str(OLD.relative_to(ROOT)),'methods':['absolute_amplitude','residual_mad_normalized'],
 'normalized_statistic':'known-frequency OLS amplitude / (1.4826 * median absolute deviation of OLS residual)',
 'signal_model':'intercept, centered linear trend, cosine, sine; same old windows/frequencies/channels',
 'threshold':'95th empirical quantile, equal calibration-record weights; same detector leave whole group out',
 'normalizer':'Computed on each observed window after fitting target harmonic; exactly invariant to the injected harmonic in this linear model. Not a universal noise estimator.',
 'selection':'One candidate specified before calculating its results. Report every frequency/window setting; do not select by held-out performance.',
 'validation_scope':'Exploratory reanalysis of the same two known dates; not fresh independent validation.',
 'amplitude_grid_uv_peak':[0,.01,.03,.1,.3,1,3,10,30,100,300,1000],'phase_count':64,'scale_floor_uv':1e-12}
(OUT/'protocol.json').write_text(json.dumps(protocol,indent=2,ensure_ascii=False),encoding='utf8')
w=pd.read_csv(OLD/'window_statistics.csv');manifest=pd.read_csv(OLD/'noise_manifest.csv').set_index('case_id');cache={}
details=[];checks=[]
for r in w.itertuples():
 if r.case_id not in cache:
  mrow=manifest.loc[r.case_id];base=(ROOT/mrow.source).parent
  assert hashlib.sha256((base/'envelopes.npz').read_bytes()).hexdigest()==mrow.sha256
  m=json.loads((base/'metadata.json').read_text(encoding='utf8'));z=np.load(base/'envelopes.npz')
  fs=float(z['envelope_rate_hz']);channels=json.loads(mrow.channels)
  y=z['slow_mean'][:,channels].mean(axis=1)*1e6
  cache[r.case_id]=(y,fs,m['lowpass_filter']['analysis_rate_first_sample_time_s'])
 y,fs,t0=cache[r.case_id];start=round((r.start_s-t0)*fs);n=round(r.T_s*fs);yy=y[start:start+n].copy();yy-=yy.mean();tt=np.arange(n)/fs
 assert len(yy)==n and abs((t0+start/fs)-r.start_s)<1e-6
 X=np.column_stack([np.ones(n),tt-tt.mean(),np.cos(2*np.pi*r.f_hz*tt),np.sin(2*np.pi*r.f_hz*tt)])
 beta=np.linalg.lstsq(X,yy,rcond=None)[0];res=yy-X@beta
 mad=1.4826*np.median(np.abs(res-np.median(res)));scale=max(float(mad),1e-12)
 assert np.allclose(beta[-2:],[r.cos_uv,r.sin_uv],atol=1e-8)
 if len(checks)<20:
  inj=yy+30*np.cos(2*np.pi*r.f_hz*tt+.73);b2=np.linalg.lstsq(X,inj,rcond=None)[0];re2=inj-X@b2
  checks.append(dict(residual_max_change_uv=float(np.max(np.abs(re2-res))),harmonic_addition_error_uv=float(np.max(np.abs(b2[-2:]-beta[-2:]-30*np.array([np.cos(.73),-np.sin(.73)]))))))
 details.append({**r._asdict(),'residual_mad_uv':scale,'residual_rms_uv':float(np.sqrt(np.mean(res**2))),'trend_change_uv':float(beta[1]*r.T_s),'peak_to_peak_uv':float(np.ptp(yy)),'normalized_score':r.null_amplitude_uv/scale})
d=pd.DataFrame(details);d.to_csv(OUT/'window_diagnostics.csv',index=False,encoding='utf-8-sig')
rows=[];thresholds=[];phase=np.arange(64)*2*np.pi/64;unit=np.column_stack([np.cos(phase),-np.sin(phase)])
for method in protocol['methods']:
 d['score']=d.null_amplitude_uv if method=='absolute_amplitude' else d.normalized_score
 for (det,T,f,group),test in d.groupby(['detector','T_s','f_hz','group']):
  train=d[d.detector.eq(det)&d.T_s.eq(T)&np.isclose(d.f_hz,f)&d.group.ne(group)].copy()
  assert set(train.case_id).isdisjoint(test.case_id)
  train['weight']=1/train.groupby('case_id').window_id.transform('count')/train.case_id.nunique();train=train.sort_values('score')
  threshold=float(train.score.iloc[min(np.searchsorted(train.weight.cumsum(),.95),len(train)-1)])
  thresholds.append(dict(method=method,detector=det,T_s=T,f_hz=f,group=group,threshold=threshold,calibration_records=train.case_id.nunique()))
  for case,z in test.groupby('case_id'):
   b=z[['cos_uv','sin_uv']].to_numpy();scale=z.residual_mad_uv.to_numpy() if method=='residual_mad_normalized' else np.ones(len(z))
   for A in protocol['amplitude_grid_uv_peak']:
    score=np.linalg.norm(b[:,None,:]+A*unit[None,:,:],axis=2)/scale[:,None]
    rows.append(dict(method=method,detector=det,T_s=T,f_hz=f,group=group,case_id=case,amplitude_uv_peak=A,power=float((score>threshold).mean()),windows=len(z),threshold=threshold))
r=pd.DataFrame(rows);curves=[];summary=[]
for (method,det,T,f),z in r.groupby(['method','detector','T_s','f_hz']):
 vals=[]
 for A,q in z.groupby('amplitude_uv_peak',sort=True):
  v=dict(method=method,detector=det,T_s=T,f_hz=f,amplitude_uv_peak=A,power=q.power.mean(),minimum_record_power=q.power.min(),maximum_record_power=q.power.max());curves.append(v);vals.append(v)
 qualifying=[v['amplitude_uv_peak'] for i,v in enumerate(vals) if all(x['power']>=.9 for x in vals[i:])]
 summary.append(dict(method=method,detector=det,T_s=T,f_hz=f,false_alarm=vals[0]['power'],mean_power90_minimum_tested_uv_peak=min(qualifying) if qualifying else None))
summary=pd.DataFrame(summary)
old=pd.read_csv(OLD/'record_power.csv');b=r[r.method.eq('absolute_amplitude')].merge(old,on=['detector','T_s','f_hz','case_id','amplitude_uv_peak'],validate='one_to_one');assert len(b)==len(old)
baseline_error=float(np.max(np.abs(b.power-b.detection_probability)));assert baseline_error<1e-12
for name,df in [('record_power',r),('thresholds',pd.DataFrame(thresholds)),('curves',pd.DataFrame(curves)),('summary',summary),('false_alarm_records',r[r.amplitude_uv_peak.eq(0)&r.power.gt(0)])]:df.to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig')
v=dict(baseline_max_probability_error=baseline_error,checked_source_records=len(cache),train_test_overlap=0,residual_invariance_max_error_uv=max(x['residual_max_change_uv'] for x in checks),harmonic_injection_max_error_uv=max(x['harmonic_addition_error_uv'] for x in checks),window_count=len(d),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
assert v['residual_invariance_max_error_uv']<1e-8
(OUT/'verification.json').write_text(json.dumps(v,indent=2),encoding='utf8')
print(summary[summary.T_s.eq(60)].to_string(index=False))
