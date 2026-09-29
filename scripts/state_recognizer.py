"""Offline TDMS state recognizer with causal 1-second extraction and replay.
Use --help. Training and testing are separate; no schedule enters inference.
"""
import argparse,json,sys,time,html
from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from scipy import signal,fft
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score
from nptdms import TdmsFile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
OUT=ROOT/'results/20260922_recognizer'
KEYS=['slow_mean','broadband_rms','subkhz_rms','fast_residual_rms','difference_rms']
BANDS={'line30':(28,32),'line50':(48,52),'line100':(98,102),'low5_100':(5,100),'b100_1k':(100,1000),'b1_20k':(1000,20000),'b20_80k':(20000,80000),'b80_200k':(80000,199900),'carrier4k':(3950,4050),'carrier8k':(7950,8050),'carrier12k':(11950,12050),'near100k':(99000,101000)}

def cache_blocks(c):
 for i in range(len(c['bandpower'])):
  yield {**{k:c[k][i*10:(i+1)*10] for k in KEYS},'bandpower':c['bandpower'][i]}

def raw_blocks(path,metadata,allow_nonfinite=False):
 """Read contiguous full seconds, keeping no full-record waveform in memory."""
 with TdmsFile.open(path) as td:
  groups=td.groups()
  if len(groups)!=1:raise ValueError('Expected exactly one TDMS channel group')
  channels=groups[0].channels();counts=[len(c) for c in channels]
  rates=[1/float(c.properties['wf_increment']) for c in channels]
  if len(channels)!=12 or len(set(counts))!=1 or not np.allclose(rates,400000,rtol=1e-9):raise ValueError('Requires 12 equal-length channels at 400 kHz')
  if counts[0]<21*400000:raise ValueError('Need at least 21 seconds, including 20 seconds initial off baseline')
  units=[str(c.properties.get('unit_string',c.properties.get('NI_UnitDescription',''))) for c in channels]
  if any(u.lower() not in ['volts','v'] for u in units):raise ValueError('Requires voltage units; no automatic calibration conversion')
  metadata.update(channel_names=[c.name for c in channels],sample_count=counts[0],fs=400000,duration_s=counts[0]/400000)
  fs=400000;buf=np.empty((12,fs));pos=0;seen=0;win=signal.windows.hann(fs,sym=False);f=fft.rfftfreq(fs,1/fs);norm=fs*np.sum(win**2);masks=[(f>=a)&(f<b) for a,b in BANDS.values()]
  for chunk in td.data_chunks():
   cc=chunk[groups[0].name].channels()
   if len(cc)!=12 or [c.name for c in cc]!=metadata['channel_names'] or any(int(c.offset)!=seen for c in cc):raise ValueError('Channel order or stream continuity mismatch')
   arr=np.stack([c[:] for c in cc]);seen+=arr.shape[1];at=0
   while at<arr.shape[1]:
    take=min(fs-pos,arr.shape[1]-at);buf[:,pos:pos+take]=arr[:,at:at+take];pos+=take;at+=take
    if pos==fs:
     if not allow_nonfinite and not np.isfinite(buf).all():raise ValueError('Nonfinite raw samples; refusing to silently impute')
     b=buf.reshape(12,10,40000);means=b.reshape(12,10,100,400).mean(axis=3);sr=means.std(axis=2);rms=b.std(axis=2)
     p=abs(fft.rfft((buf-buf.mean(axis=1,keepdims=True))*win,axis=1,workers=2))**2/norm;p[:,1:-1]*=2
     features={'slow_mean':b.mean(axis=2).T,'broadband_rms':rms.T,'subkhz_rms':sr.T,'fast_residual_rms':np.sqrt(np.maximum(rms**2-sr**2,0)).T,'difference_rms':np.sqrt(np.mean(np.diff(b,axis=2)**2,axis=2)/2).T,'bandpower':np.stack([p[:,m].sum(axis=1) for m in masks],axis=1)}
     pos=0;yield features
  metadata.update(samples_read=seen,tail_without_prediction_s=pos/fs)
  if seen!=counts[0]:raise ValueError('Incomplete stream')

class Baseline:
 def __init__(self,blocks):
  if len(blocks)!=20:raise ValueError('Exactly 20 initial seconds required')
  b={k:np.concatenate([r[k] for r in blocks[5:20]]) for k in KEYS}
  if not all(np.isfinite(v).all() for v in b.values()):raise ValueError('Invalid baseline')
  self.ref={k:np.median(v,axis=0) for k,v in b.items()}
  eligible=(self.ref['broadband_rms']>1e-8)&(abs(self.ref['slow_mean'])<9.8)
  if not eligible.all():raise ValueError('Baseline channel failure; this model requires all 12 channels. Do not silently change channel set.')
  self.scale=np.maximum(1.4826*np.median(abs(b['slow_mean']-self.ref['slow_mean']),axis=0),1e-5)
  self.power=np.median([r['bandpower'] for r in blocks[5:20]],axis=0)
 def transform(self,b):
  cols=[]
  for k in KEYS:
   x=b[k]
   if k=='slow_mean':x=np.clip(abs(x-self.ref[k])/self.scale,0,20)
   else:x=np.clip(20*np.log10(np.maximum(x,1e-15)/self.ref[k]),-10,30)
   x=x.mean(axis=0);cols.extend([np.median(x),np.quantile(x,.9)])
  x=np.clip(10*np.log10(np.maximum(b['bandpower'],1e-30)/np.maximum(self.power,1e-30)),-10,40)
  return np.r_[cols,np.median(x,axis=0),np.quantile(x,.9,axis=0)]

def matrix(c):
 blocks=list(cache_blocks(c));baseline=Baseline(blocks[:20]);return np.array([baseline.transform(b) for b in blocks])

def fit(cases):
 from scripts.analyze_20260921_switching import stable_labels
 xx=[];yy=[];sx=[];sy=[]
 for c in cases:
  x=c.get('X_rec');x=matrix(c) if x is None else x;y=stable_labels(c,True);mask=y!='excluded'
  xx.append(x[mask]);yy.append(y[mask]);states=stable_labels(c);on=np.isin(states,['30Hz','50Hz']);sx.append(x[on]);sy.append(states[on])
 def classifier():return make_pipeline(StandardScaler(),LogisticRegression(C=.1,class_weight='balanced',max_iter=2000))
 return {'version':1,'binary':classifier().fit(np.concatenate(xx),np.concatenate(yy)), 'frequency':classifier().fit(np.concatenate(sx),np.concatenate(sy)), 'training_ids':[c['id'] for c in cases], 'training_sources':[c['m']['source'] for c in cases], 'training_fingerprints':[(c['m']['source_bytes'],c['m']['source_mtime_ns']) for c in cases], 'channel_names':cases[0]['m']['channel_names'],'bands':BANDS,'baseline':'initial 20s off confirmed; fit baseline on 5..20s','confidence_threshold':.6,'note':'Exploratory September21 model. Probabilities uncalibrated. Same wiring and acquisition required.'}

class Decisions:
 def __init__(self,model):self.model=model;self.state='off';self.recent=[]
 def step(self,x,t):
  p=self.model['binary'].predict_proba(x[None])[0];classes=self.model['binary'].classes_;raw=str(classes[p.argmax()]);score=float(p.max());self.recent.append(raw);event=''
  if len(self.recent)>=3 and len(set(self.recent[-3:]))==1 and raw!=self.state:self.state=raw;event=raw
  fp=self.model['frequency'].predict_proba(x[None])[0];fq=str(self.model['frequency'].classes_[fp.argmax()]);fscore=float(fp.max())
  decision='uncertain' if score<.6 else (self.state if self.state=='off' else (fq if fscore>=.6 else 'on_frequency_unknown'))
  if raw!=self.state:decision='transition_pending'
  return {'time_end_s':t,'raw_binary':raw,'confirmed_binary':self.state,'decision':decision,'model_score':score,'prob_on':float(p[list(classes).index('on')]),'frequency_candidate':fq if self.state=='on' else '', 'frequency_score':fscore if self.state=='on' else np.nan,'event':event}

def replay(blocks,model,metadata):
 baseline_blocks=[];baseline=None;decision=Decisions(model);rows=[];timings=[]
 iterator=iter(blocks);i=0
 while True:
  started=time.perf_counter()
  try:b=next(iterator)
  except StopIteration:break
  i+=1
  if i<=20:
   baseline_blocks.append(b)
   if i==20:baseline=Baseline(baseline_blocks)
   row={'time_end_s':i,'raw_binary':'calibrating','confirmed_binary':'calibrating','decision':'calibrating','model_score':np.nan,'prob_on':np.nan,'event':''}
  else:
   x=baseline.transform(b);row=decision.step(x,i)
   row['large_voltage_excursion']=bool(np.any(b['broadband_rms']>.1))
  elapsed=time.perf_counter()-started;row['processing_s']=elapsed;rows.append(row);timings.append(elapsed)
 if i<21:raise ValueError('Insufficient baseline plus prediction data')
 metadata.update(processing_mean_s=float(np.mean(timings)),processing_p95_s=float(np.quantile(timings,.95)),processing_max_s=max(timings),seconds_processed=i,confirmed_event_count=sum(bool(r['event']) for r in rows))
 return pd.DataFrame(rows)

def save_result(frame,out,metadata):
 out.mkdir(parents=True,exist_ok=True);frame.to_csv(out/'predictions.csv',index=False,encoding='utf-8-sig');frame[frame.event.fillna('')!=''].to_csv(out/'events.csv',index=False,encoding='utf-8-sig');(out/'run.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
 records=json.loads(frame.to_json(orient='records'));data=json.dumps(records,ensure_ascii=False).replace('</','<\\/');title=html.escape(str(metadata.get('source','数据回放')))
 page='''<!doctype html><meta charset="utf-8"><title>工况识别回放</title><style>body{font:16px/1.8 "Microsoft YaHei",sans-serif;max-width:1100px;margin:32px auto;padding:16px;color:#20354a}button,input,select{font-size:16px;margin:8px}canvas{width:100%;border:1px solid #ddd}.card{padding:20px;background:#eef4f8}small{color:#566}#seek{width:65%}</style><h1>工况识别 · 逐秒回放</h1><p>SOURCE</p><p>前20秒为已确认停泵的校准段。概率为未经校准的模型分数；频率标签为探索性输出。此页回放已计算结果，不连接采集设备。</p><div class="card" id="state"></div><button id="play">播放</button><select id="speed"><option value="1000">1倍速</option><option value="200">5倍速</option><option value="50">20倍速</option></select><input id="seek" type="range" min="0" value="0"><canvas id="plot" width="1080" height="270"></canvas><h2>状态切换记录</h2><div id="events"></div><script>const data=DATA;let timer=null;const seek=document.getElementById('seek'),c=document.getElementById('plot'),ctx=c.getContext('2d');seek.max=data.length-1;const labels={off:'关',on:'运行',calibrating:'校准中',uncertain:'不确定',transition_pending:'待连续确认',on_frequency_unknown:'运行，频率不确定','30Hz':'30 Hz候选','50Hz':'50 Hz候选'};function draw(){let k=+seek.value,r=data[k];document.getElementById('state').textContent=`时间 ${r.time_end_s}s ｜ 输出：${labels[r.decision]||r.decision} ｜ 确认启停：${labels[r.confirmed_binary]} ｜ 模型分数：${r.model_score==null?'—':r.model_score.toFixed(3)}${r.large_voltage_excursion?' ｜ 大幅电压波动提示':''}`;ctx.clearRect(0,0,c.width,c.height);ctx.fillStyle='#345';ctx.fillText('运行概率（蓝）与已确认启停（橙）；只展示当前及过去数据',20,20);for(let b of [0,1]){ctx.strokeStyle='#ddd';ctx.beginPath();ctx.moveTo(35,230-180*b);ctx.lineTo(1050,230-180*b);ctx.stroke();ctx.fillText(b,15,230-180*b);}for(let field of ['prob_on','confirmed_binary']){ctx.beginPath();ctx.strokeStyle=field==='prob_on'?'#1976ab':'#d18c29';let started=false;for(let i=0;i<=k;i++){let v=field==='prob_on'?data[i][field]:(data[i][field]==='on'?1:data[i][field]==='off'?0:null);if(v===null){started=false;continue;}let x=35+i/(data.length-1)*1015,y=230-v*180;if(started)ctx.lineTo(x,y);else ctx.moveTo(x,y);started=true;}ctx.stroke();}document.getElementById('events').textContent=data.slice(0,k+1).filter(x=>x.event).map(x=>`${x.time_end_s}s → ${labels[x.event]}`).join('；')||'尚无确认切换';}seek.oninput=draw;document.getElementById('play').onclick=function(){if(timer){clearTimeout(timer);timer=null;this.textContent='播放';return;}this.textContent='暂停';function tick(){if(+seek.value>=data.length-1){timer=null;document.getElementById('play').textContent='播放';return;}seek.value=+seek.value+1;draw();timer=setTimeout(tick,+document.getElementById('speed').value);}timer=setTimeout(tick,+document.getElementById('speed').value);};draw();</script>'''
 (out/'回放.html').write_text(page.replace('SOURCE',title).replace('DATA',data),encoding='utf-8')

def main():
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True)
 t=sub.add_parser('train-validate');t.add_argument('--output',type=Path,default=OUT)
 r=sub.add_parser('predict');r.add_argument('input',type=Path);r.add_argument('--model',type=Path,default=OUT/'model.joblib');r.add_argument('--output',type=Path,required=True);r.add_argument('--initial-off-confirmed',action='store_true');r.add_argument('--allow-training-record',action='store_true')
 a=p.parse_args()
 if a.cmd=='train-validate':
  from scripts.analyze_20260921_switching import load,stable_labels,nominal
  cases=load();a.output.mkdir(parents=True,exist_ok=True);scores=[];matched=[];frequency_scores=[]
  for c in cases:c['X_rec']=matrix(c)
  for c in cases:
   train=[d for d in cases if d['id']!=c['id']];m=fit(train);joblib.dump(m,a.output/(c['id']+'_heldout.joblib'))
   meta={'source':c['m']['source'],'case_id':c['id'],'mode':'held-out cache replay','training_ids':m['training_ids'],'timing_scope':'cached features only, excludes raw reading/FFT'};df=replay(cache_blocks(c),m,meta);save_result(df,a.output/c['id'],meta)
   y=stable_labels(c,True);mask=(y!='excluded')&(np.arange(len(y))>=20);d=df.loc[mask];actual=y[mask];scores.append({'case_id':c['id'],'raw_binary_BA':balanced_accuracy_score(actual,d.raw_binary),'confirmed_binary_BA':balanced_accuracy_score(actual,d.confirmed_binary),'off_false_positive':np.mean(d.confirmed_binary[actual=='off']!='off'),'on_miss':np.mean(d.confirmed_binary[actual=='on']!='on'),'uncertain_or_pending_fraction':np.mean(d.decision.isin(['uncertain','transition_pending','on_frequency_unknown']))})
   states=stable_labels(c);on=(states!='excluded')&(states!='off')&(df.time_end_s.to_numpy()>20);accepted=df.decision.isin(['30Hz','50Hz']).to_numpy();correct=(df.decision.to_numpy()==states)&on
   frequency_scores.append({'case_id':c['id'],'true_on_seconds':int(on.sum()),'frequency_coverage_on':float((on&accepted).sum()/on.sum()),'frequency_correct_all_on':float(correct.sum()/on.sum()),'frequency_accuracy_when_reported_on':float(correct.sum()/max(1,(on&accepted).sum()))})
   used=set();ee=df[df.event!='']
   for at,s in nominal(c['group']):
    if s=='30Hz':continue
    target='off' if s=='off' else 'on';hit=ee[(ee.event==target)&(ee.time_end_s>=at)&(ee.time_end_s<=at+15)&(~ee.index.isin(used))]
    detected=float(hit.time_end_s.iloc[0]) if len(hit) else np.nan
    if len(hit):used.add(hit.index[0])
    matched.append({'case_id':c['id'],'target':target,'nominal_s':at,'detected_s':detected,'delay_s':detected-at})
   scores[-1]['unmatched_events']=len(ee)-len(used)
   print('VALIDATED',c['id'],scores[-1],flush=True)
  pd.DataFrame(scores).to_csv(a.output/'validation.csv',index=False,encoding='utf-8-sig');pd.DataFrame(matched).to_csv(a.output/'event_validation.csv',index=False,encoding='utf-8-sig');pd.DataFrame(frequency_scores).to_csv(a.output/'frequency_validation.csv',index=False,encoding='utf-8-sig');model=fit(cases);joblib.dump(model,a.output/'model.joblib')
  (a.output/'model_manifest.json').write_text(json.dumps({k:v for k,v in model.items() if k not in ['binary','frequency']},ensure_ascii=False,indent=2),encoding='utf-8')
 else:
  if not a.initial_off_confirmed:p.error('Requires --initial-off-confirmed: first 20 s must be pump-off, VFD powered, with same wiring/units as training')
  model=joblib.load(a.model)
  if model.get('version')!=1:raise ValueError('Unsupported model version')
  st=a.input.stat();seen=(st.st_size,st.st_mtime_ns) in model['training_fingerprints'] or str(a.input.resolve()).lower() in [str(Path(s).resolve()).lower() for s in model['training_sources']]
  if seen and not a.allow_training_record:p.error('Input belongs to training data. Use the held-out model for this record, or explicitly --allow-training-record for a labeled demonstration.')
  meta={'source':str(a.input.resolve()),'model':str(a.model.resolve()),'in_training_set':seen,'mode':'raw TDMS causal replay','training_ids':model['training_ids'],'timing_scope':'TDMS read + extraction + inference; excludes output writing','baseline_condition':'user confirmed initial 20s pump off'}
  started=time.perf_counter();iterator=raw_blocks(a.input,meta);first=next(iterator);first_elapsed=time.perf_counter()-started
  if meta['channel_names']!=model['channel_names']:raise ValueError('Channel name/order differs from training; explicit mapping and validation required')
  import itertools
  df=replay(itertools.chain([first],iterator),model,meta);df.loc[0,'processing_s']+=first_elapsed;meta.update(processing_mean_s=float(df.processing_s.mean()),processing_p95_s=float(df.processing_s.quantile(.95)),processing_max_s=float(df.processing_s.max()),wall_s_excluding_output=time.perf_counter()-started);save_result(df,a.output,meta);print(json.dumps(meta,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
