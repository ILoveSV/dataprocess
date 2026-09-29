"""Audit raw excursions, extraction consistency, and causal event scoring.
Additional clipped features are exploratory; no tuning on held-out trials.
"""
import sys,json
from pathlib import Path
import numpy as np,pandas as pd
from nptdms import TdmsFile
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score,confusion_matrix
import matplotlib.pyplot as plt
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.analyze_20260921_switching import load,intervals,nominal,stable_labels,OUT,write

def event_score(cid,group,pr,binary=False,method='original'):
 state='off';trans=[];events=[]
 for j in range(22,len(pr)):
  if len(set(pr[j-2:j+1]))==1 and pr[j]!=state:
   trans.append({'case_id':cid,'method':method,'time':j+1,'from':state,'to':pr[j]});state=pr[j]
 used=set()
 targets=nominal(group)
 if binary:targets=[(a,'off' if s=='off' else 'on') for a,s in targets if s!='30Hz']
 for at,lab in targets:
  hits=[(k,r) for k,r in enumerate(trans) if k not in used and r['to']==lab and at<=r['time']<=at+15]
  det=np.nan
  if hits:k,r=hits[0];used.add(k);det=r['time']
  events.append({'case_id':cid,'method':method,'expected':lab,'nominal_s':at,'detected_s':det,'delay_from_command_s':det-at,'hit_within_window':np.isfinite(det)})
 for k,r in enumerate(trans):r['matched']=k in used
 return events,trans

def clipped_design(c):
 n=len(c['t1']);ii=(c['t']>=5)&(c['t']<20);v=c['valid'];cols=[]
 for key in ['slow_mean','broadband_rms','subkhz_rms','fast_residual_rms','difference_rms']:
  x=c[key][:,v];b=np.median(x[ii],axis=0)
  if key=='slow_mean':
   scale=np.maximum(1.4826*np.median(abs(x[ii]-b),axis=0),1e-5);x=np.clip(abs(x-b)/scale,0,20)
  else:x=np.clip(20*np.log10(np.maximum(x,1e-15)/b),-10,30)
  x=x[:n*10].reshape(n,10,len(v)).mean(axis=1)
  cols.extend([np.median(x,axis=1),np.quantile(x,.9,axis=1)])
 p=c['bandpower'][:,v];b=np.median(p[(c['t1']>=5)&(c['t1']<20)],axis=0);x=np.clip(10*np.log10(np.maximum(p,1e-30)/np.maximum(b,1e-30)),-10,40)
 cols.extend([np.median(x,axis=1),np.quantile(x,.9,axis=1)])
 return np.column_stack(cols)

cases=load();audit=[];rawrows=[];exc=[]
for c in cases:
 m=c['m'];err=np.max(abs(c['broadband_rms']**2-c['subkhz_rms']**2-c['fast_residual_rms']**2))
 audit.append({'case_id':c['id'],'samples_read':m['samples_read'],'all_channels_same_length':len(set(m['sample_counts']))==1,'all_samples_read':all(n==m['samples_read'] for n in m['sample_counts']),'duration_s':m['duration_s'],'spectral_seconds':len(c['t1']),'tail_without_spectrum_s':m['tail_without_spectrum_s'],'variance_partition_abs_error_V2':err,'baseline_eligible_channel_count':len(c['valid'])})
 base=np.median(c['slow_mean'][(c['t']>=5)&(c['t']<20)],axis=0)
 for state,a,b in intervals(c['group']):
  ix=(c['t']>=a)&(c['t']<b)
  for j in range(12):exc.append({'case_id':c['id'],'state':state,'channel':j+1,'slow_departure_gt_0p1V_fraction':np.mean(abs(c['slow_mean'][ix,j]-base[j])>.1),'rms_gt_0p1V_fraction':np.mean(c['broadband_rms'][ix,j]>.1),'median_rms_V':np.median(c['broadband_rms'][ix,j])})
 # Raw excerpts are an audit sample, not a substitute for the full-record features.
 with TdmsFile.open(m['source']) as td:
  ch=td.groups()[0].channels();fig,axes=plt.subplots(len(intervals(c['group'])),2,figsize=(12,8))
  for row,(state,a,b) in enumerate(intervals(c['group'])):
   snippets=[]
   for center in [a+3,a+7,a+11]:snippets.append(np.stack([cc[round((center-.05)*m['fs']):round((center+.05)*m['fs'])] for cc in ch],axis=1))
   x=np.concatenate(snippets)
   for j in range(12):
    vals,cnt=np.unique(x[:,j],return_counts=True)
    rawrows.append({'case_id':c['id'],'state':state,'channel':j+1,'sampled_seconds':.3,'min_V':x[:,j].min(),'max_V':x[:,j].max(),'negative_fraction':np.mean(x[:,j]<0),'above_4p9V_fraction':np.mean(x[:,j]>4.9),'below_minus4p9V_fraction':np.mean(x[:,j]<-4.9),'most_frequent_value_V':vals[cnt.argmax()],'most_frequent_value_fraction':cnt.max()/len(x)})
   worst=np.argmax(x.std(axis=0));xx=snippets[1][:,worst];axes[row,0].plot(np.arange(len(xx))/m['fs']*1000,xx,lw=.5);axes[row,0].set_title(f'{state}：通道{worst+1}，{a+7:.0f}s附近');axes[row,0].set_ylabel('电压 / V');axes[row,1].hist(xx,bins=100);axes[row,1].set_xlabel('电压 / V')
  axes[-1,0].set_xlabel('片段内时间 / ms');fig.suptitle(c['id']+' 原始波形抽查：每阶段选片段波动最大的通道');fig.tight_layout();fig.savefig(OUT/'figures'/f'{c["id"]}_raw_audit.png',dpi=130);plt.close(fig)
 print('AUDITED',c['id'],flush=True)
write('extraction_validation',audit);write('raw_excerpt_audit',rawrows);write('large_excursion_by_channel',exc)

old=pd.read_csv(OUT/'heldout_predictions.csv');events=[];alarms=[];conf=[]
for c in cases:
 d=old[(old.task=='state')&(old.feature_family=='all')&(old.case_id==c['id'])].sort_values('time_end_s');e,a=event_score(c['id'],c['group'],d.prediction.to_numpy());events+=e;alarms+=a
 for task in ['state','on_off']:
  d=old[(old.task==task)&(old.feature_family=='all')&(old.case_id==c['id'])];d=d[d.true_stable!='excluded']
  for (actual,pred),g in d.groupby(['true_stable','prediction']):conf.append({'case_id':c['id'],'task':task,'true':actual,'prediction':pred,'seconds':len(g)})
write('transition_detection',events);write('all_detected_transitions',alarms);write('heldout_confusion',conf)

scores=[];preds=[];ev=[];al=[]
for c in cases:c['Z']=clipped_design(c)
for group,binary in [('111',False),('222',False),('all',True)]:
 sub=cases if group=='all' else [c for c in cases if c['group']==group]
 for c in sub:
  train=[d for d in sub if d['id']!=c['id']];ys=[stable_labels(d,binary) for d in train];X=np.concatenate([d['Z'][y!='excluded'] for d,y in zip(train,ys)]);y=np.concatenate([y[y!='excluded'] for y in ys]);model=make_pipeline(StandardScaler(),LogisticRegression(C=.1,class_weight='balanced',max_iter=2000)).fit(X,y);pr=model.predict(c['Z']);truth=stable_labels(c,binary);mask=truth!='excluded';method='clipped_binary' if binary else 'clipped_state'
  scores.append({'case_id':c['id'],'group':group,'method':method,'balanced_accuracy':balanced_accuracy_score(truth[mask],pr[mask]),'off_false_positive_fraction':np.mean(pr[truth=='off']!='off'),'on_as_off_fraction':np.mean(pr[np.isin(truth,['on','30Hz','50Hz'])]=='off')})
  preds.extend([{'case_id':c['id'],'method':method,'time_end_s':j+1,'true_stable':truth[j],'prediction':p} for j,p in enumerate(pr)])
  e,a=event_score(c['id'],c['group'],pr,binary,method);ev+=e;al+=a
write('exploratory_clipped_validation',scores);write('exploratory_clipped_predictions',preds);write('exploratory_clipped_events',ev);write('exploratory_clipped_alarms',al)
print(pd.DataFrame(scores).groupby(['group','method']).balanced_accuracy.mean().to_string());print('AUDIT COMPLETE')
