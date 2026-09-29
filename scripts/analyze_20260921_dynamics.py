"""Reuse historical stability and event-shape methods on the new scheduled records."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.analyze_20260921_switching import load,intervals,nominal,write
from scripts.analyze_pre_electrochemical_dynamics import autocorrelation_metrics,allan_deviation,lag_null_test,red_noise_periodicity_pvalues
from scripts.analyze_mentor_event_shape_models import fit_event_shape_models
ar=[];al=[];shape=[];lag=[];period=[]
for ci,c in enumerate(load()):
 x=c['slow_mean'];base=np.median(x[(c['t']>=5)&(c['t']<20)],axis=0);slow=np.median(x-base,axis=1);env=np.median(np.log(np.maximum(c['fast_residual_rms'],1e-20)),axis=1)
 for state,a,b in intervals(c['group']):
  mask=(c['t']>=a)&(c['t']<a+15)
  for j in c['valid']:
   v=x[mask,j];fields={'case_id':c['id'],'state':state,'channel':j+1,'window_s':15}
   ar.append({**fields,**autocorrelation_metrics(v,10,5)})
   al.extend([{**fields,**r} for r in allan_deviation(v,10,[.1,.2,.5,1,2,3])])
 for name,v in [('slow_median',slow),('log_fast_envelope',env)]:
  for at,state in nominal(c['group']):shape.append({'case_id':c['id'],'signal':name,'nominal_s':at,'transition_to':state,**fit_event_shape_models(v,int(at*10),10,12)})
  pp,phi=red_noise_periodicity_pvalues(v,10,[.1,.2,.5,1],repeats=99,seed=ci)
  period.extend([{'case_id':c['id'],'signal':name,'candidate_frequency_hz':fq,'ar1_phi':phi,**r} for fq,r in zip([.1,.2,.5,1],pp)])
 lag.append({'case_id':c['id'],**lag_null_test(slow,env,10)})
 print('DYNAMICS',c['id'],flush=True)
write('state_autocorrelation',ar);write('state_allan_deviation',al);write('event_shape_models',shape);write('slow_fast_lag_null',lag);write('slow_periodicity_red_noise',period)
