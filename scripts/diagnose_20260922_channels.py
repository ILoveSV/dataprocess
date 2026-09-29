"""Exploratory channel ablations and error explanations; never replace deployed models."""
import sys,json,time
from pathlib import Path
import numpy as np,pandas as pd,joblib
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from nptdms import TdmsFile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.analyze_20260921_switching import load,stable_labels,nominal,intervals
from scripts.state_recognizer import Baseline,cache_blocks,KEYS,BANDS
OUT=ROOT/'results/20260922_channel_diagnosis';OUT.mkdir(exist_ok=True);(OUT/'figures').mkdir(exist_ok=True)
REC=ROOT/'results/20260922_recognizer'
plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],'axes.unicode_minus':False})
NAMES=[k+'_'+q for k in KEYS for q in ['median','q90']]+[b+'_'+q for q in ['median','q90'] for b in BANDS]

def normalized_channels(c):
 blocks=list(cache_blocks(c));base=Baseline(blocks[:20]);n=len(blocks);cols=[]
 for k in KEYS:
  x=c[k][:n*10]
  if k=='slow_mean':x=np.clip(abs(x-base.ref[k])/base.scale,0,20)
  else:x=np.clip(20*np.log10(np.maximum(x,1e-15)/base.ref[k]),-10,30)
  cols.append(x.reshape(n,10,12).mean(axis=1))
 p=np.clip(10*np.log10(np.maximum(c['bandpower'],1e-30)/np.maximum(base.power,1e-30)),-10,40)
 return np.concatenate([np.stack(cols,axis=2),p],axis=2)

def aggregate(z,channels):
 x=z[:,channels,:];med=np.median(x,axis=1);q=np.quantile(x,.9,axis=1)
 return np.column_stack([v for i in range(5) for v in [med[:,i],q[:,i]]]+[med[:,5:],q[:,5:]])

def confirm(pr):
 state='off';out=['calibrating']*min(20,len(pr));events=[]
 for j in range(20,len(pr)):
  if j>=22 and len(set(pr[j-2:j+1]))==1 and pr[j]!=state:state=pr[j];events.append((j+1,state))
  out.append(state)
 return np.array(out),events

def event_metrics(c,events):
 used=set();hits=0
 for at,lab in nominal(c['group']):
  if lab=='30Hz':continue
  target='off' if lab=='off' else 'on';found=[i for i,(t,s) in enumerate(events) if i not in used and s==target and at<=t<=at+15]
  if found:used.add(found[0]);hits+=1
 return hits,len(events)-len(used)

def write(name,rows):pd.DataFrame(rows).to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig')

def main():
 cases=load();rows=[];predictions={};explanations=[];counter=[];errorrows=[];statechannels=[];diagnostic_predictions=[];event_details=[]
 for c in cases:
  c['Z']=normalized_channels(c);c['X']=aggregate(c['Z'],list(range(12)));c['y']=stable_labels(c,True);c['states']=stable_labels(c);c['mask']=(c['y']!='excluded')&(np.arange(len(c['y']))>=20)
  m=joblib.load(REC/(c['id']+'_heldout.joblib'));np.testing.assert_allclose(m['binary'].predict_proba(c['X'])[20:,1],pd.read_csv(REC/c['id']/'predictions.csv').prob_on.iloc[20:],atol=1e-12)
 configs=[('all',list(range(12)),list(range(34)))]
 configs += [(f'drop_{j+1:02}',[i for i in range(12) if i!=j],list(range(34))) for j in range(12)]
 configs += [(f'only_{j+1:02}',[j],list(range(34))) for j in range(12)]
 configs += [('without_slow',list(range(12)),list(range(2,34))),('without_spectral',list(range(12)),list(range(10))),('spectral_only',list(range(12)),list(range(10,34)))]
 for name,ch,ix in configs:
  xx=[aggregate(c['Z'],ch)[:,ix] for c in cases]
  for k,c in enumerate(cases):
   trainx=np.concatenate([x[d['y']!='excluded'] for j,(x,d) in enumerate(zip(xx,cases)) if j!=k]);trainy=np.concatenate([d['y'][d['y']!='excluded'] for j,d in enumerate(cases) if j!=k]);model=make_pipeline(StandardScaler(),LogisticRegression(C=.1,class_weight='balanced',max_iter=2000)).fit(trainx,trainy);pr=model.predict(xx[k]);confirmed,events=confirm(pr);mask=c['mask'];y=c['y'];hits,extra=event_metrics(c,events)
   rows.append({'configuration':name,'case_id':c['id'],'raw_BA':balanced_accuracy_score(y[mask],pr[mask]),'confirmed_BA':balanced_accuracy_score(y[mask],confirmed[mask]),'off_false_positive':np.mean(confirmed[mask&(y=='off')]!='off'),'on_miss':np.mean(confirmed[mask&(y=='on')]!='on'),'off_post_false_positive':np.mean(confirmed[(c['t1']>90 if c['group']=='111' else c['t1']>80)&mask&(y=='off')]!='off'),'event_hits':hits,'unmatched_events':extra})
   event_details.extend([{'configuration':name,'case_id':c['id'],'time_s':t,'new_state':s} for t,s in events])
   if name in ['all','only_08','drop_04','drop_08']:
    pp=model.predict_proba(xx[k])[:,1];diagnostic_predictions.extend([{'configuration':name,'case_id':c['id'],'time_end_s':i+1,'confirmed':confirmed[i],'prob_on':pp[i] if i>=20 else np.nan} for i in range(len(pp))])
   if name=='all':predictions[c['id']]=(model,pr,confirmed)
  print('DONE',name,flush=True)
 write('channel_ablation_by_trial',rows);df=pd.DataFrame(rows);summary=df.groupby('configuration').agg(raw_BA=('raw_BA','mean'),confirmed_BA=('confirmed_BA','mean'),off_false_positive=('off_false_positive','mean'),on_miss=('on_miss','mean'),event_hits=('event_hits','sum'),unmatched_events=('unmatched_events','sum')).reset_index();baseline=summary[summary.configuration=='all'].iloc[0];summary['BA_change_percentage_points']=(summary.confirmed_BA-baseline.confirmed_BA)*100;write('channel_ablation_summary',summary)
 for c in cases:
  model,pr,confirmed=predictions[c['id']];saved=pd.read_csv(REC/c['id']/'predictions.csv');assert list(confirmed)==list(saved.confirmed_binary);coef=model[-1].coef_[0];scaled=model[0].transform(c['X']);contrib=scaled*coef;logit=model.decision_function(c['X']);np.testing.assert_allclose(contrib.sum(axis=1)+model[-1].intercept_[0],logit,atol=1e-12)
  # Fixed-model, one-channel-at-baseline counterfactual. Not an additive attribution.
  effects=[]
  for j in range(12):
   z=c['Z'].copy();z[:,j,:]=0;new=model.decision_function(aggregate(z,list(range(12))));effects.append(logit-new)
  effects=np.array(effects).T
  bad=c['mask']&(confirmed!=c['y']);i=0
  while i<len(bad):
   if not bad[i]:i+=1;continue
   a=i
   while i+1<len(bad) and bad[i+1] and c['y'][i+1]==c['y'][a]:i+=1
   end=i+1;ix=np.arange(a,end);top=np.argsort(-abs(contrib[ix].mean(axis=0)))[:5];ce=effects[ix].mean(axis=0);rank=np.argsort(-abs(ce))[:3];kind='false_on' if c['y'][a]=='off' else 'miss_on'
   errorrows.append({'case_id':c['id'],'error':kind,'window_start_s':a,'window_end_s':end,'seconds':end-a,'true':c['y'][a],'mean_prob_on':float(model.predict_proba(c['X'][ix])[:,1].mean()),'raw_prediction_already_correct_seconds':int(np.sum(pr[ix]==c['y'][ix])),'top_features':'; '.join(f'{NAMES[j]}:{contrib[ix,j].mean():+.3f}' for j in top),'top_channel_counterfactuals':'; '.join(f'ch{j+1}:{ce[j]:+.3f}' for j in rank)})
   for j in range(34):explanations.append({'case_id':c['id'],'window_start_s':a,'window_end_s':end,'error':kind,'feature':NAMES[j],'mean_logit_contribution':contrib[ix,j].mean(),'intercept':model[-1].intercept_[0]})
   for j in range(12):counter.append({'case_id':c['id'],'window_start_s':a,'window_end_s':end,'error':kind,'channel':j+1,'actual_minus_baseline_counterfactual_logit':ce[j]})
   i+=1
  for state,a,b in intervals(c['group']):
   mask=(c['t']>=a)&(c['t']<b);base=(c['t']>=5)&(c['t']<20)
   for j in range(12):statechannels.append({'case_id':c['id'],'state':state,'channel':j+1,'channel_name':c['m']['channel_names'][j],'median_mean_V':np.median(c['slow_mean'][mask,j]),'mean_departure_V':np.median(c['slow_mean'][mask,j])-np.median(c['slow_mean'][base,j]),'median_RMS_V':np.median(c['broadband_rms'][mask,j]),'RMS_change_db':20*np.log10(np.median(c['broadband_rms'][mask,j])/np.median(c['broadband_rms'][base,j]))})
  fig,axes=plt.subplots(3,1,figsize=(12,8),sharex=True);t=c['t'];b=(t>=5)&(t<20);delta=c['slow_mean']-np.median(c['slow_mean'][b],axis=0);db=20*np.log10(c['broadband_rms']/np.median(c['broadband_rms'][b],axis=0));
  for ax,data,label,lo,hi in [(axes[0],delta.T,'均值偏移 / V',-.2,.2),(axes[1],db.T,'RMS变化 / dB',-10,40)]:
   im=ax.imshow(data,aspect='auto',origin='lower',extent=[0,len(t)/10,.5,12.5],cmap='RdBu_r',vmin=lo,vmax=hi);fig.colorbar(im,ax=ax,label=label+'（色标范围外饱和显示）');ax.set_yticks(range(1,13));ax.set_ylabel('通道')
  axes[2].plot(np.arange(len(pr))+1,model.predict_proba(c['X'])[:,1],label='运行概率');axes[2].step(np.arange(len(pr))+1,np.where(confirmed=='on',1,np.where(confirmed=='off',0,np.nan)),label='连续确认状态',where='post');axes[2].legend();axes[2].set_xlabel('时间 / s')
  for ax in axes:
   for at,label in nominal(c['group']):ax.axvline(at,color='k',ls='--',lw=.7)
  fig.suptitle(c['id']+' 通道变化与留出预测');fig.tight_layout();fig.savefig(OUT/'figures'/f'{c["id"]}_channels.png',dpi=140);plt.close(fig)
 write('error_intervals',errorrows);write('error_feature_contributions',explanations);write('error_channel_counterfactuals',counter);write('channel_state_statistics',statechannels);write('diagnostic_predictions',diagnostic_predictions);write('ablation_event_details',event_details)
 # Raw snippets selected to cover initial background, first post-stop failure, and runtime misses.
 raw=[];status=[]
 for cid,seconds in [('g111_r1',[12,49,79,105]),('g111_r2',[12,45,52,105]),('g222_r1',[12,56,60,105])]:
  c=next(c for c in cases if c['id']==cid)
  if not Path(c['m']['source']).exists():status.append({'case_id':cid,'status':'raw_unavailable'});continue
  with TdmsFile.open(c['m']['source']) as td:
   ch=td.groups()[0].channels();fig,axes=plt.subplots(len(seconds),2,figsize=(12,9))
   for k,sec in enumerate(seconds):
    mat=np.stack([v[int(sec*400000):int(sec*400000)+40000] for v in ch],axis=1)
    for j in range(12):
     x=mat[:,j];v,n=np.unique(x,return_counts=True);raw.append({'case_id':cid,'start_s':sec,'duration_s':.1,'channel':j+1,'min_V':x.min(),'max_V':x.max(),'rms_V':x.std(),'negative_fraction':np.mean(x<0),'below_minus4p9_fraction':np.mean(x<-4.9),'above4p9_fraction':np.mean(x>4.9),'modal_value_V':v[n.argmax()],'modal_fraction':n.max()/len(x),'adjacent_equal_fraction':np.mean(np.diff(x)==0)})
    # Channel 4 fixed across phases, avoiding changes of channel between rows.
    for col,j in enumerate([3,7]):
     x=mat[:,j];axes[k,col].plot(np.arange(len(x))/400,x,lw=.5);axes[k,col].set_title(f'{sec}s起，通道{j+1}，100 ms');axes[k,col].set_ylabel('V')
   for ax in axes[-1]:ax.set_xlabel('片段内时间 / ms')
   fig.suptitle(cid+' 固定通道4/8原始波形核查（其他通道见表）');fig.tight_layout();fig.savefig(OUT/'figures'/f'{cid}_raw.png',dpi=130);plt.close(fig)
  status.append({'case_id':cid,'status':'raw_checked'})
 write('raw_targeted_audit',raw);write('raw_audit_status',status)
 fig,ax=plt.subplots(figsize=(11,5));s=summary[summary.configuration.str.startswith('drop_')].copy();ax.bar(s.configuration,s.BA_change_percentage_points);ax.axhline(0,color='k',lw=.8);ax.set(ylabel='移除通道后BA变化 / 百分点',title='固定逐个移除通道，重新训练并留出整次记录（探索性敏感性）');ax.tick_params(axis='x',rotation=35);fig.tight_layout();fig.savefig(OUT/'figures/channel_ablation.png',dpi=140);plt.close(fig)
 print(summary.to_string(index=False));print('DIAGNOSIS COMPLETE')

if __name__=='__main__':main()
