"""Candidate: per-chip models, training-only reliability weights and causal health gating.
No physical saturation limits are assumed. Outputs are exploratory.
"""
import sys,json,argparse,time
from pathlib import Path
import numpy as np,pandas as pd,joblib
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.analyze_20260921_switching import load,stable_labels,nominal
from scripts.state_recognizer import KEYS,BANDS,raw_blocks,cache_blocks,save_result
OUT=ROOT / 'analysis/20260922_health_fusion'

def calibration(blocks):
 refs={k:np.median(np.concatenate([b[k] for b in blocks[5:20]]),axis=0) for k in KEYS}
 scale=np.maximum(1.4826*np.median(abs(np.concatenate([b['slow_mean'] for b in blocks[5:20]])-refs['slow_mean']),axis=0),1e-5)
 power=np.median([b['bandpower'] for b in blocks[5:20]],axis=0)
 valid=np.isfinite(scale)&np.all(np.isfinite(power),axis=1)
 for v in refs.values():valid &=np.isfinite(v)
 valid &= refs['broadband_rms']>1e-8
 return refs,scale,power,valid

def channel_features(b,cal):
 refs,scale,power,valid=cal;cols=[]
 with np.errstate(invalid='ignore',divide='ignore'):
  for k in KEYS:
   x=b[k]
   x=np.clip(abs(x-refs[k])/scale,0,20) if k=='slow_mean' else np.clip(20*np.log10(np.maximum(x,1e-15)/refs[k]),-10,30)
   v=x.mean(axis=0);cols.extend([v,v])
  p=np.clip(10*np.log10(np.maximum(b['bandpower'],1e-30)/np.maximum(power,1e-30)),-10,40)
 return np.column_stack(cols+[p,p])

class Health:
 def __init__(self,valid):self.valid=np.array(valid);self.active=np.array(valid);self.good=np.zeros(12,int)
 def step(self,b):
  ok=np.ones(12,bool);reason=np.array(['healthy']*12,dtype=object)
  for k in KEYS+['bandpower']:
   finite=np.all(np.isfinite(b[k]),axis=0 if k!='bandpower' else 1);reason[~finite]='nonfinite';ok &=finite
  flat=np.all(b['broadband_rms']<=1e-8,axis=0);reason[flat]='flat_raw';ok &=~flat
  ok &=self.valid;reason[~self.valid]='invalid_initial_baseline'
  self.good=np.where(ok,self.good+1,0);self.active[~ok]=False
  restoring=ok&~self.active&(self.good<3);reason[restoring]='recovering_3s'
  self.active[ok&(self.good>=3)]=True
  return self.active.copy(),reason

def prepare(c):
 blocks=list(cache_blocks(c));cal=calibration(blocks[:20]);return np.stack([channel_features(b,cal) for b in blocks])

def fit_channel(cases,j):
 x=np.concatenate([c['F'][c['y']!='excluded',j] for c in cases]);y=np.concatenate([c['y'][c['y']!='excluded'] for c in cases]);valid=np.isfinite(x).all(axis=1)
 return make_pipeline(StandardScaler(),LogisticRegression(C=.1,class_weight='balanced',max_iter=2000)).fit(x[valid],y[valid])

def train(cases):
 # All reliability estimation happens inside the current training partition.
 reliab=np.zeros(12)
 for j in range(12):
  scores=[]
  for c in cases:
   m=fit_channel([d for d in cases if d['id']!=c['id']],j);mask=c['mask'];scores.append(balanced_accuracy_score(c['y'][mask],m.predict(c['F'][mask,j])))
  reliab[j]=np.mean(scores)
 # Fixed formula, no outer-test tuning; all >=0.55 candidates remain as fallback.
 weights=np.where(reliab>=.55,np.exp(12*(reliab-reliab.max())),0)
 if weights.sum()==0:weights=np.ones(12)
 weights/=weights.sum()
 return {'version':'health_fusion_v1','models':[fit_channel(cases,j) for j in range(12)],'reliability':reliab,'weights':weights,'training_ids':[c['id'] for c in cases],'training_sources':[c['m']['source'] for c in cases],'channel_names':cases[0]['m']['channel_names']}

def infer(blocks,model):
 warm=[];health=None;cal=None;state='off';candidate=None;count=0;rows=[];channels=[]
 for i,b in enumerate(blocks):
  if i<20:
   warm.append(b)
   if i==19:cal=calibration(warm);health=Health(cal[-1])
   rows.append({'time_end_s':i+1,'raw_binary':'calibrating','confirmed_binary':'calibrating','decision':'calibrating','prob_on':np.nan,'event':''});continue
  active,reasons=health.step(b);f=channel_features(b,cal);probs=np.full(12,np.nan)
  for j,m in enumerate(model['models']):
   if active[j] and np.isfinite(f[j]).all():probs[j]=m.predict_proba(f[j:j+1])[0,list(m.classes_).index('on')]
  usable=np.flatnonzero(np.isfinite(probs)&(model['weights']>0));selected=sorted(usable,key=lambda j:(-model['weights'][j],j))[:3];weight=np.zeros(12)
  if selected:weight[selected]=model['weights'][selected]/model['weights'][selected].sum()
  event='';event_type=''
  if not selected:
   p=np.nan;raw='unknown';out='unknown';candidate=None;count=0;state='unknown'
  else:
   p=float(np.sum(probs[selected]*weight[selected]));raw='on' if p>=.5 else 'off'
   if raw==candidate:count+=1
   else:candidate=raw;count=1
   if count>=3 and state!=raw:
    event_type='state_reacquired' if state=='unknown' else 'state_transition';state=raw;event=raw
   out='transition_pending' if raw!=state else state
  rows.append({'time_end_s':i+1,'raw_binary':raw,'confirmed_binary':state,'decision':out,'prob_on':p,'model_score':max(p,1-p) if np.isfinite(p) else np.nan,'event':event,'event_type':event_type,'effective_channels':','.join(str(j+1) for j in selected),'healthy_channel_count':int(active.sum()),'largest_weight':max(weight),'single_channel_fallback':len(selected)==1})
  for j in range(12):channels.append({'time_end_s':i+1,'channel':j+1,'health':reasons[j],'usable':bool(active[j]),'selected':j in selected,'prob_on':probs[j],'weight':weight[j]})
 return pd.DataFrame(rows),pd.DataFrame(channels)

def save_candidate(d,h,out,meta):
 save_result(d,out,meta);h.to_csv(out/'channel_health.csv',index=False,encoding='utf-8-sig')
 # Extend the old local replay widget, with explicit health and selected weights.
 page=(out/'回放.html').read_text(encoding='utf-8').replace('频率标签为探索性输出。','本候选只判断启停，未输出频率细分。')
 data=h.to_json(orient='records',force_ascii=False).replace('</','<\\/')
 extra='''<h2>当前通道状态</h2><div id="chips"></div><script>const healthData=HEALTH;const oldDraw=draw;draw=function(){oldDraw();const t=data[+seek.value].time_end_s,rows=healthData.filter(x=>x.time_end_s===t);const words={healthy:'可用',nonfinite:'无效数值，已退出',flat_raw:'卡死/平坦，已退出',recovering_3s:'恢复观察中',invalid_initial_baseline:'初始基准无效'};document.getElementById('chips').innerHTML=rows.length?'<table style="width:100%;text-align:left"><tr><th>芯片通道</th><th>健康状态</th><th>参与融合</th><th>当前权重</th><th>运行概率</th></tr>'+rows.map(r=>`<tr><td>${r.channel}</td><td>${words[r.health]||r.health}</td><td>${r.selected?'是':'否'}</td><td>${r.weight.toFixed(3)}</td><td>${r.prob_on===null?'—':r.prob_on.toFixed(3)}</td></tr>`).join('')+'</table>':'初始校准阶段';};labels.unknown='无有效证据';seek.oninput=draw;draw();</script>'''
 (out/'回放.html').write_text(page+extra.replace('HEALTH',data),encoding='utf-8')

def score(c,d):
 mask=c['mask'];y=c['y'];pr=d.confirmed_binary.to_numpy();unknown=pr=='unknown';off=mask&(y=='off');on=mask&(y=='on')
 # Unknown is a miss of the true class, never silently removed from denominators.
 ba=.5*(np.mean(pr[off]=='off')+np.mean(pr[on]=='on'));ev=d[d.event.fillna('')!=''];used=set();details=[]
 for t,s in nominal(c['group']):
  if s=='30Hz':continue
  target='off' if s=='off' else 'on';hit=ev[(ev.event==target)&(ev.time_end_s>=t)&(ev.time_end_s<=t+15)&~ev.index.isin(used)];det=np.nan
  if len(hit):idx=hit.index[0];used.add(idx);det=float(hit.time_end_s.iloc[0])
  details.append({'case_id':c['id'],'target':target,'nominal_s':t,'detected_s':det,'delay_s':det-t})
 return {'case_id':c['id'],'confirmed_BA':ba,'off_false_positive':np.mean(pr[off]=='on'),'on_miss_or_unknown':np.mean(pr[on]!='on'),'unknown_fraction':np.mean(unknown[mask]),'events_hit':len(used),'unmatched_events':len(ev)-len(used)},details

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--predict',type=Path);ap.add_argument('--model',type=Path,default=OUT/'model.joblib');ap.add_argument('--output',type=Path);ap.add_argument('--initial-off-confirmed',action='store_true');a=ap.parse_args();OUT.mkdir(exist_ok=True)
 if a.predict:
  if not a.initial_off_confirmed or a.output is None:ap.error('Provide --initial-off-confirmed and --output; same wiring and first20s off required')
  m=joblib.load(a.model)
  if str(a.predict.resolve()).lower() in [str(Path(s).resolve()).lower() for s in m['training_sources']]:ap.error('Input was used in training; choose its held-out model')
  started=time.perf_counter();meta={'source':str(a.predict),'model':str(a.model),'training_ids':m['training_ids'],'mode':'health-fusion raw replay'};it=raw_blocks(a.predict,meta,allow_nonfinite=True);first=next(it)
  if meta['channel_names']!=m['channel_names']:raise ValueError('Channel mapping mismatch')
  import itertools
  d,h=infer(itertools.chain([first],it),m);meta['wall_s_before_output']=time.perf_counter()-started;save_candidate(d,h,a.output,meta);print(json.dumps(meta,ensure_ascii=False,indent=2));return
 cases=load()
 for c in cases:c['y']=stable_labels(c,True);c['mask']=(c['y']!='excluded')&(np.arange(len(c['y']))>=20);c['F']=prepare(c)
 scores=[];events=[];weights=[]
 for c in cases:
  m=train([d for d in cases if d['id']!=c['id']]);joblib.dump(m,OUT/(c['id']+'_heldout.joblib'));d,h=infer(cache_blocks(c),m);save_candidate(d,h,OUT/c['id'],{'source':c['id'],'training_ids':m['training_ids'],'mode':'nested training-only health fusion'});s,e=score(c,d);scores.append(s);events+=e
  weights.extend([{'held_out':c['id'],'channel':j+1,'training_only_BA':m['reliability'][j],'base_weight':m['weights'][j]} for j in range(12)]);print('FOLD',c['id'],s,flush=True)
 for name,data in [('validation',scores),('events',events),('training_only_weights',weights)]:pd.DataFrame(data).to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig')
 joblib.dump(train(cases),OUT/'model.joblib');print('COMPLETE',flush=True)

if __name__=='__main__':main()
