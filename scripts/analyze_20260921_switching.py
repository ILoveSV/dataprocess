"""Independent-repeat background and dynamic-state analysis, no time feature in classifiers."""
from pathlib import Path
import sys,json,itertools,warnings
import numpy as np,pandas as pd
from scipy import signal,stats
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score,confusion_matrix
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.append(str(ROOT/'.codex_tmp/mentor_method_deps'))
OUT=ROOT/'results/20260921_switching';(OUT/'figures').mkdir(exist_ok=True)
plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],'axes.unicode_minus':False,'figure.dpi':140})
RNG=np.random.default_rng(20260921)
FEATURES=['slow_mean','broadband_rms','subkhz_rms','fast_residual_rms','difference_rms']

def intervals(group):
 return [('off_pre',5,25),('50Hz',42,57),('30Hz',72,87),('off_post',97,117)] if group=='111' else [('off_pre',5,35),('50Hz',52,77),('off_post',87,117)]
def nominal(group):return [(30,'50Hz'),(60,'30Hz'),(90,'off')] if group=='111' else [(40,'50Hz'),(80,'off')]
def write(name,rows):pd.DataFrame(rows).to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig')
def load():
 cases=[]
 for f in sorted((OUT/'cache').glob('*.npz')):
  z=np.load(f);m=json.loads(str(z['meta'])); c={k:z[k] for k in z.files if k!='meta'};c['m']=m;c['id']=m['case_id'];c['group']=m['folder'];c['t']=np.arange(len(c['slow_mean']))/10+.05;c['t1']=np.arange(len(c['bandpower']))+.5
  # Channel eligibility and normalization use only the initial baseline, available before first switch.
  ib=(c['t']>=5)&(c['t']<20);br=c['broadband_rms'][ib];c['valid']=np.flatnonzero((np.median(br,axis=0)>1e-8)&(np.abs(np.median(c['slow_mean'][ib],axis=0))<9.8)&np.all(np.isfinite(br),axis=0));cases.append(c)
 return cases

def design(c):
 ts=c['t'];ii=(ts>=5)&(ts<20);v=c['valid'];n=len(c['t1']);cols=[];names=[]
 for k in FEATURES:
  a=c[k][:,v];b=np.median(a[ii],axis=0)
  if k=='slow_mean':
   scale=np.maximum(1.4826*np.median(np.abs(a[ii]-b),axis=0),1e-8);norm=(a-b)/scale
  else:norm=20*np.log10(np.maximum(a,1e-15)/np.maximum(b,1e-15))
  x=norm[:n*10].reshape(n,10,len(v)).mean(axis=1)
  cols.extend([np.median(x,axis=1),np.quantile(x,.25,axis=1),np.quantile(x,.75,axis=1)]);names.extend([k+'_'+q for q in ['med','q25','q75']])
 bp=c['bandpower'][:,v,:];ref=np.median(bp[(c['t1']>=5)&(c['t1']<20)],axis=0);x=10*np.log10(np.maximum(bp,1e-30)/np.maximum(ref,1e-30))
 for j,name in enumerate(c['m']['bands']):cols.append(np.median(x[:,:,j],axis=1));names.append(name+'_db')
 return np.column_stack(cols),names

def bg_state(c):
 rows=[];spect=[];v=c['valid'];t=c['t'];ints=intervals(c['group']);pre=(t>=ints[0][1])&(t<ints[0][2]);post=(t>=ints[-1][1])&(t<min(ints[-1][2],c['m']['duration_s']-2))
 for j in range(len(c['m']['channel_names'])):
  for k in FEATURES:
   a=c[k][pre,j];b=c[k][post,j];delta=np.median(b)-np.median(a);ratio=20*np.log10(max(np.median(b),1e-15)/max(np.median(a),1e-15)) if k!='slow_mean' else np.nan
   # 2s non-overlapping blocks preserve short-range autocorrelation, no sample-level p-value.
   def blocks(x):return np.median(x[:len(x)//20*20].reshape(-1,20),axis=1)
   aa=blocks(a);bb=blocks(b);d=np.array([np.median(RNG.choice(bb,len(bb)))-np.median(RNG.choice(aa,len(aa))) for _ in range(500)])
   rows.append({'case_id':c['id'],'group':c['group'],'channel':j+1,'baseline_eligible':j in v,'feature':k,'pre':np.median(a),'post':np.median(b),'delta':delta,'delta_uV':delta*1e6,'ratio_db':ratio,'block_bootstrap_low':np.quantile(d,.025),'block_bootstrap_high':np.quantile(d,.975)})
 for state,start,end in ints:
  ix=(c['t1']>=start)&(c['t1']<min(end,c['m']['duration_s']-2));pref=(c['t1']>=ints[0][1])&(c['t1']<ints[0][2]);p=np.median(c['bandpower'][ix][:,v,:],axis=(0,1));b=np.median(c['bandpower'][pref][:,v,:],axis=(0,1))
  for j,name in enumerate(c['m']['bands']):spect.append({'case_id':c['id'],'group':c['group'],'state':state,'band':name,'power_V2':p[j],'rms_uV':np.sqrt(p[j])*1e6,'contrast_pre_db':10*np.log10(max(p[j],1e-30)/max(b[j],1e-30))})
 return rows,spect

def stable_labels(c,binary=False,background_only=False):
 y=np.full(len(c['t1']),'excluded',dtype='<U12')
 for state,a,b in intervals(c['group']):
  lab=('off' if state.startswith('off') else ('on' if binary else state))
  if background_only: lab=state if state.startswith('off') else 'excluded'
  y[(c['t1']>=a)&(c['t1']<min(b,c['m']['duration_s']-2))]=lab
 return y

def model():return make_pipeline(StandardScaler(),LogisticRegression(C=1,class_weight='balanced',max_iter=2000))
def run_cv(cases,indices,task,group,selector,binary=False,bg=False,permutations=0):
 selected=[c for c in cases if c['group']==group] if group!='all' else cases
 mats=[c['X'][:,indices] for c in selected];ys=[stable_labels(c,binary,bg) for c in selected]
 scores=[];preds=[];fits={}
 for k,c in enumerate(selected):
  xx=np.concatenate([m[y!='excluded'] for j,(m,y) in enumerate(zip(mats,ys)) if j!=k]);yy=np.concatenate([y[y!='excluded'] for j,y in enumerate(ys) if j!=k]);fit=model().fit(xx,yy);pr=fit.predict(mats[k]);prob=fit.predict_proba(mats[k]);mask=ys[k]!='excluded';score=balanced_accuracy_score(ys[k][mask],pr[mask]);fits[c['id']]=(pr,prob,fit.classes_)
  scores.append({'task':task,'group':group,'feature_family':selector,'held_out':c['id'],'balanced_accuracy':score,'n_stable_seconds':int(mask.sum()),'chance':1/len(fit.classes_)})
  for j in range(len(pr)):preds.append({'task':task,'feature_family':selector,'case_id':c['id'],'time_end_s':j+1,'true_stable':ys[k][j],'prediction':pr[j],**{'prob_'+str(k):float(v) for k,v in zip(fit.classes_,prob[j])}})
 if permutations:
  null=[]
  for rep in range(permutations):
   py=[np.roll(y,int(RNG.integers(20,max(21,len(y)-20)))) for y in ys];fold=[]
   for k in range(len(selected)):
    xx=np.concatenate([m[y!='excluded'] for j,(m,y) in enumerate(zip(mats,py)) if j!=k]);yy=np.concatenate([y[y!='excluded'] for j,y in enumerate(py) if j!=k]);ft=model().fit(xx,yy);mask=py[k]!='excluded';fold.append(balanced_accuracy_score(py[k][mask],ft.predict(mats[k][mask])))
   null.append(np.mean(fold))
  obs=np.mean([r['balanced_accuracy'] for r in scores]);PERM.append({'task':task,'group':group,'family':selector,'observed_mean':obs,'null_mean':np.mean(null),'null_q95':np.quantile(null,.95),'p':(1+sum(v>=obs for v in null))/(len(null)+1),'n':permutations})
 return scores,preds,fits

def plot_case(c,fits):
 t=c['t'];n=len(c['t1']);v=c['valid'];base=(t>=5)&(t<20);x=c['slow_mean'][:,v];delta=(x-np.median(x[base],axis=0))*1e6
 fig,ax=plt.subplots(4,1,figsize=(12,10),sharex=True)
 for j in range(len(v)):ax[0].plot(t,delta[:,j],lw=.5,alpha=.65)
 ax[0].set_ylabel('通道慢变偏移 / μV')
 for k in ['broadband_rms','fast_residual_rms']:
  a=c[k][:,v];db=np.median(20*np.log10(a/np.median(a[base],axis=0)),axis=1);ax[1].plot(t,db,label=k)
 ax[1].set_ylabel('相对初始背景 / dB');ax[1].legend(fontsize=8)
 for k in ['line30_db','line50_db','b20_80k_db','b80_200k_db']:ax[2].plot(c['t1'],c['X'][:,c['names'].index(k)],label=k)
 ax[2].set_ylabel('频带功率变化 / dB');ax[2].legend(ncol=2,fontsize=8)
 pr,prob,classes=fits[c['id']]
 for j,cl in enumerate(classes):ax[3].plot(np.arange(n)+1,prob[:,j],label=cl)
 ax[3].set_ylabel('留一整次实验预测概率');ax[3].set_xlabel('采集开始后的时间 / s');ax[3].legend(ncol=3)
 for a in ax:
  for at,lab in nominal(c['group']):a.axvline(at,color='k',ls='--',lw=.8);a.axvspan(at,at+(5 if lab=='off' else 10),color='gray',alpha=.13)
  a.grid(alpha=.2)
 fig.suptitle(c['id']+'：实线为数据/独立留出预测，虚线为计划切换时刻');fig.tight_layout();fig.savefig(OUT/'figures'/f'{c["id"]}_dynamic.png');plt.close(fig)
 # State PSD estimates are fully measured raw-FFT powers, coarse only for plotting.
 fig,ax=plt.subplots(figsize=(10,5));fq=np.arange(2000)*100+50
 for state,a,b in intervals(c['group']):
  mask=(c['t1']>=a)&(c['t1']<b);ps=np.median(c['psd100'][mask][:,v,:],axis=(0,1));ax.semilogx(fq,10*np.log10(np.maximum(ps,1e-30)),label=state)
 ax.set(xlabel='频率 / Hz（100 Hz频宽汇总）',ylabel='PSD / dB V²/Hz',title=c['id']+' 稳态频谱');ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(OUT/'figures'/f'{c["id"]}_psd.png');plt.close(fig)

if __name__=='__main__':
 cases=load();assert len(cases)==8,'All eight full records must be extracted first';bg=[];sp=[];health=[]
 for c in cases:
  c['X'],c['names']=design(c);a,b=bg_state(c);bg+=a;sp+=b
  health +=[{'case_id':c['id'],'group':c['group'],**r,**{'baseline_eligible':i in c['valid']},**c['m']['health'][i]} for i,r in enumerate(c['m']['quality'])]
 write('background_channel_comparison',bg);write('state_spectral_contrasts',sp);write('channel_health',health)
 bdf=pd.DataFrame(bg); agg=bdf[bdf.baseline_eligible].groupby(['case_id','group','feature'])[['delta_uV','ratio_db']].median().reset_index();write('background_trial_summary',agg)
 names=cases[0]['names'];families={'slow':[i for i,x in enumerate(names) if x.startswith('slow_')],'envelope':[i for i,x in enumerate(names) if 'rms_' in x],'spectral':[i for i,x in enumerate(names) if x.endswith('_db')],'all':list(range(len(names)))}
 scores=[];pred=[];PERM=[];allfits={}
 for group in ['111','222']:
  for family,idx in families.items():
   a,b,f=run_cv(cases,idx,'state',group,family,permutations=39 if family=='all' else 0);scores+=a;pred+=b
   if family=='all':allfits.update(f)
  a,b,f=run_cv(cases,families['all'],'background_pre_vs_post',group,'all',bg=True);scores+=a;pred+=b
 a,b,f=run_cv(cases,families['all'],'on_off','all','all',binary=True,permutations=39);scores+=a;pred+=b
 write('grouped_validation',scores);write('heldout_predictions',pred);write('circular_shift_validation',PERM)
 # Cross-protocol transfer (not chronological: 111 r5 was acquired after 222).
 train=[c for c in cases if c['group']=='111'];test=[c for c in cases if c['group']=='222'];yy=[stable_labels(c,True) for c in train];fit=model().fit(np.concatenate([c['X'][y!='excluded'] for c,y in zip(train,yy)]),np.concatenate([y[y!='excluded'] for y in yy]));transfer=[]
 for c in test:
  y=stable_labels(c,True);mask=y!='excluded';pr=fit.predict(c['X']);transfer.append({'held_out':c['id'],'balanced_accuracy':balanced_accuracy_score(y[mask],pr[mask]),'off_false_positive_fraction':np.mean(pr[y=='off']!='off'),'on_miss_fraction':np.mean(pr[y=='on']!='on')})
 write('cross_protocol_transfer',transfer)
 events=[];alarms=[]
 for c in cases:
  pr,prob,classes=allfits[c['id']];state='off';trans=[]
  # Three successive 1 s decisions required, actual availability at window end.
  for j in range(22,len(pr)):
   recent=pr[j-2:j+1]
   if len(set(recent))==1 and recent[-1]!=state:
    new=recent[-1];trans.append({'time':j+1,'from':state,'to':new});state=new
  used=set()
  for nominal_t,expected in nominal(c['group']):
   hits=[(k,r) for k,r in enumerate(trans) if k not in used and r['to']==expected and nominal_t<=r['time']<=nominal_t+15]
   if hits:k,r=hits[0];used.add(k);det=r['time']
   else:det=np.nan
   events.append({'case_id':c['id'],'expected':expected,'nominal_s':nominal_t,'detected_s':det,'delay_from_command_s':det-nominal_t,'hit_within_window':np.isfinite(det)})
  for k,r in enumerate(trans):alarms.append({'case_id':c['id'],**r,'matched':k in used})
  plot_case(c,allfits)
 write('transition_detection',events);write('all_detected_transitions',alarms)
 # Sensitivity to transition guard, no refitting or label-based temporal realignment.
 sens=[]
 for guard in [5,10,15]:
  for c in cases:
   y=np.full(len(c['t1']),'excluded',dtype='<U12');bounds=[0]+[a for a,b in nominal(c['group'])]+[min(120,c['m']['duration_s'])];labs=['off']+[b for a,b in nominal(c['group'])]
   for a,b,l in zip(bounds[:-1],bounds[1:],labs):y[(c['t1']>=a+guard)&(c['t1']<b-3)]=l
   mask=y!='excluded';pr=allfits[c['id']][0];sens.append({'case_id':c['id'],'guard_s':guard,'balanced_accuracy':balanced_accuracy_score(y[mask],pr[mask])})
 write('guard_sensitivity',sens)
 write('feature_definition',[{'index':i,'name':x} for i,x in enumerate(names)])
 print(pd.DataFrame(scores).groupby(['task','group','feature_family']).balanced_accuracy.mean().to_string(),flush=True)
 print('BASE COMPLETE',flush=True)

