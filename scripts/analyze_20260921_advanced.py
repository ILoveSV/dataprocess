"""Apply existing advanced method implementations to the new independent repeats."""
from pathlib import Path
import os,sys,json,time,warnings
os.environ['SSQ_PARALLEL']='0';os.environ['NUMBA_NUM_THREADS']='2';os.environ['OMP_NUM_THREADS']='2'
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.append(str(ROOT / 'local/workbench/mentor_method_deps'))
import numpy as np,pandas as pd
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from nptdms import TdmsFile
from scripts.analyze_20260921_switching import load,intervals,nominal,OUT,model
from scripts.analyze_mentor_modes_complexity_network import emd_features,eemd_features,vmd_features,complexity_features,robust_pca_features,state_space_features,granger_network,aligned_multichannel_emd_features
from scripts.analyze_projection_memd import projection_memd,standardized_channels,mode_metrics
from scripts.analyze_mentor_wavelet_relaxation import cwt_analysis,synchrosqueezed_summary,pelt_changepoints,fit_exponential_relaxation,wavelet_coherence
from scripts.analyze_mentor_nonlinear_highfreq import phase_amplitude_coupling,high_frequency_cwt,bicoherence_analysis
from sklearn.metrics import balanced_accuracy_score
warnings.filterwarnings('ignore',category=RuntimeWarning)
plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],'axes.unicode_minus':False})
rows=[];stage=[];events=[];edges=[];methods=[]
def add(case,scope,method,result):
 clean={k:v for k,v in result.items() if not k.startswith('_')}
 rows.append({'case_id':case['id'],'group':case['group'],'scope':scope,'method':method,**clean})
def safe(case,scope,name,fn):
 try:
  value=fn();add(case,scope,name,value);methods.append({'case_id':case['id'],'scope':scope,'method':name,'status':'completed'});return value
 except Exception as ex:methods.append({'case_id':case['id'],'scope':scope,'method':name,'status':'failed','reason':str(ex)});print('FAILED',case['id'],name,str(ex),flush=True);return {}
def flush():
 for name,data in [('advanced_features',rows),('advanced_stage_features',stage),('offline_changepoints_relaxation',events),('granger_edges',edges),('method_execution',methods)]:pd.DataFrame(data).to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig')
for ci,c in enumerate(load()):
 print('ADVANCED START',c['id'],flush=True);t=c['t'];valid=c['valid'];x=c['slow_mean'][:,valid];z=standardized_channels(x);u,sv,v=np.linalg.svd(z,full_matrices=False);pc=u[:,0]*sv[0];env=np.median(np.log(np.maximum(c['fast_residual_rms'][:,valid],1e-20)),axis=1)
 safe(c,'full_offline','robust_PCA',lambda:robust_pca_features(x));safe(c,'full_offline','aligned_channel_EMD',lambda:aligned_multichannel_emd_features(x,10))
 try:
  imfs,res,diagnostics=projection_memd(z,direction_count=16,maximum_imfs=5,maximum_sifts=10,seed=ci);mr,summary=mode_metrics(imfs,res,z,10);safe(c,'full_offline','projection_MEMD',lambda:summary)
 except Exception as ex:methods.append({'case_id':c['id'],'method':'projection_MEMD','status':'failed','reason':str(ex)})
 cwtcache=[]
 for signame,xx in [('slow_pc1',pc),('fast_envelope',env)]:
  safe(c,signame,'EMD',lambda:emd_features(xx,10));safe(c,signame,'EEMD',lambda:eemd_features(xx,10,ci,trials=20));safe(c,signame,'VMD',lambda:vmd_features(xx,10,4,2000));safe(c,signame,'complexity_MSE_MFDFA_RQA',lambda:complexity_features(xx,10,19,ci));safe(c,signame,'state_space',lambda:state_space_features(xx));safe(c,signame,'synchrosqueezing',lambda:synchrosqueezed_summary(xx,10))
  try:
   cw=cwt_analysis(xx,10);add(c,signame,'CWT_AR1',cw['summary']);cwtcache.append((signame,cw));methods.append({'case_id':c['id'],'scope':signame,'method':'CWT_AR1','status':'completed'})
   cps=pelt_changepoints(xx,10)
   for cp in cps:events.append({'case_id':c['id'],'signal':signame,'kind':'offline_PELT','time_s':cp/10})
   for at,lab in nominal(c['group']):events.append({'case_id':c['id'],'signal':signame,'kind':'schedule_aligned_fit','time_s':at,'transition_to':lab,**fit_exponential_relaxation(xx,int(at*10),10,15)})
  except Exception as ex:methods.append({'case_id':c['id'],'scope':signame,'method':'CWT_PELT','status':'failed','reason':str(ex)})
 safe(c,'full_offline','phase_amplitude_coupling',lambda:phase_amplitude_coupling(pc,env,10,(.15,.5),39,ci))
 if len(cwtcache)==2:safe(c,'full_offline','wavelet_coherence',lambda:wavelet_coherence(cwtcache[0][1],cwtcache[1][1],10,39,ci))
 # All state comparisons use equal 15 second windows; no future-state information in local features.
 for state,a,b in intervals(c['group']):
  ix=(t>=a)&(t<a+15);mat=x[ix];zm=standardized_channels(mat);uu,ss,vv=np.linalg.svd(zm,full_matrices=False);xx=uu[:,0]*ss[0];scope='state_'+state
  ee,nn=granger_network(mat,valid);edges.extend([{'case_id':c['id'],'state':state,**e} for e in ee]);add(c,scope,'Granger',nn)
  row={'case_id':c['id'],'group':c['group'],'state':state,'window_start':a,'window_s':15}
  for name,fn in [('complexity',lambda:complexity_features(xx,10,9,ci)),('emd',lambda:emd_features(xx,10)),('vmd',lambda:vmd_features(xx,10,4,2000))]:
   out=safe(c,scope,name,fn);row.update({name+'_'+k:v for k,v in out.items() if np.isscalar(v) and not isinstance(v,str)})
  corr=np.corrcoef(signal.detrend(mat,axis=0),rowvar=False);row['median_abs_channel_correlation']=np.median(np.abs(corr[np.triu_indices(len(valid),1)]));row['pc1_fraction']=ss[0]**2/np.sum(ss**2);row.update(nn);stage.append(row)
 # Raw high-frequency snippets: 3 disjoint 0.1s excerpts per stable state, same channels.
 with TdmsFile.open(c['m']['source']) as td:
  ch=td.groups()[0].channels();fs=c['m']['fs']
  for state,a,b in intervals(c['group']):
   snippets=[]
   for center in [a+3,a+7,a+11]:
    start=round((center-.05)*fs);mat=np.stack([ch[j][start:start+round(.1*fs)] for j in valid],axis=1);mat=mat-mat.mean(axis=0);mat/=np.maximum(mat.std(axis=0),1e-15);snippets.append(np.median(mat,axis=1))
   snippets=np.array(snippets);safe(c,'state_'+state,'high_frequency_CWT',lambda:high_frequency_cwt(snippets,fs));safe(c,'state_'+state,'bicoherence',lambda:bicoherence_analysis(snippets,fs,19,ci))
 if cwtcache:
  fig,axes=plt.subplots(len(cwtcache),1,figsize=(12,6),sharex=True,squeeze=False)
  for ax,(name,cw) in zip(axes[:,0],cwtcache):
   power=np.where(cw['valid'],cw['power_to_red'],np.nan);im=ax.pcolormesh(cw['time_s'],cw['frequencies_hz'],np.log10(np.maximum(power,1e-8)),shading='auto',cmap='RdBu_r',vmin=-1,vmax=1);ax.set_yscale('log');ax.set_ylabel(name+' / Hz');fig.colorbar(im,ax=ax,label='log10(功率/AR1阈值)')
   for at,lab in nominal(c['group']):ax.axvline(at,c='k',ls='--',lw=.7)
  axes[-1,0].set_xlabel('时间 / s（留白区域为边界影响）');fig.suptitle(c['id']+' 小波时频分析，整记录离线结果');fig.tight_layout();fig.savefig(OUT/'figures'/f'{c["id"]}_cwt.png',dpi=140);plt.close(fig)
 flush();print('ADVANCED DONE',c['id'],flush=True)
# Grouped generalization of local 15s advanced state features, fixed feature set.
f=pd.DataFrame(stage);cols=['complexity_sample_entropy','complexity_permutation_entropy_normalized','complexity_spectral_entropy_normalized','complexity_dfa_alpha','complexity_rqa_determinism','emd_mode_energy_fraction_0p15_0p5hz','vmd_mode_energy_fraction_0p15_0p5hz','pc1_fraction','median_abs_channel_correlation'];sc=[]
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
for group in ['111','222']:
 sub=f[f.group==group].copy();y=sub.state.str.replace('off_pre','off').str.replace('off_post','off').to_numpy();X=sub[cols].replace([np.inf,-np.inf],np.nan).to_numpy(float)
 for cid in sub.case_id.unique():
  test=(sub.case_id==cid).to_numpy();fit=make_pipeline(SimpleImputer(strategy='median'),StandardScaler(),LogisticRegression(C=.1,class_weight='balanced',max_iter=2000)).fit(X[~test],y[~test]);sc.append({'case_id':cid,'group':group,'balanced_accuracy':balanced_accuracy_score(y[test],fit.predict(X[test])),'feature_count':len(cols),'note':'15s local complexity/mode features; sample sizes small'})
pd.DataFrame(sc).to_csv(OUT/'advanced_grouped_validation.csv',index=False,encoding='utf-8-sig')
print('ADVANCED COMPLETE',flush=True)

