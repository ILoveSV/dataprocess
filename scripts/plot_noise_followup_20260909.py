from pathlib import Path
import json
import numpy as np
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
import pypdfium2 as pdfium
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/thesis_followup_20260909/noise'
BLUE='#2166AC';RED='#B2182B'
def text(c,x,y,s,size=10,color='#222222'):
 c.setFillColor(HexColor(color));c.setFont('Helvetica',size);c.drawString(x,y,s)
def begin(name,title,subtitle):
 p=OUT/(name+'.pdf');c=canvas.Canvas(str(p),pagesize=(760,440));text(c,30,410,title,16);text(c,30,390,subtitle,9);return c,p
def end(c,p):
 c.save();d=pdfium.PdfDocument(str(p));d[0].render(scale=2).to_pil().save(p.with_suffix('.png'));d.close()
def axes(c,x,y,w,h,xlo,xhi,ylo,yhi):
 sx=lambda v:x+(v-xlo)/(xhi-xlo)*w;sy=lambda v:y+(v-ylo)/(yhi-ylo)*h
 for v in np.linspace(ylo,yhi,5):
  yy=sy(v);c.setStrokeColor(HexColor('#DDDDDD'));c.line(x,yy,x+w,yy);text(c,x-40,yy-3,f'{v:.3g}',8)
 for v in np.linspace(xlo,xhi,5):text(c,sx(v)-5,y-15,f'{v:.3g}',8)
 c.setStrokeColor(HexColor('#222222'));c.line(x,y,x+w,y);c.line(x,y,x,y+h)
 return sx,sy
d=pd.read_csv(OUT/'window_diagnostics.csv');s=pd.read_csv(OUT/'summary.csv')
c,p=begin('false_alarm_comparison','Held-out null false alarms before and after normalization','Same two dates; same windows and folds; one prespecified exploratory normalization candidate.')
base=s[s.method.eq('absolute_amplitude')].reset_index(drop=True);norm=s[s.method.eq('residual_mad_normalized')].reset_index(drop=True)
assert base[['detector','T_s','f_hz']].equals(norm[['detector','T_s','f_hz']])
sx,sy=axes(c,65,90,655,255,-.5,15.5,0,.3)
for i in range(len(base)):
 for offset,q,col in [(-5,base,BLUE),(5,norm,RED)]:
  v=q.false_alarm.iloc[i];c.setFillColor(HexColor(col));c.rect(sx(i)+offset-4,sy(0),8,sy(v)-sy(0),fill=1,stroke=0)
c.setStrokeColor(HexColor('#777777'));c.setDash(3,3);c.line(sx(-.5),sy(.05),sx(15.5),sy(.05))
text(c,65,360,'Null false-alarm fraction');text(c,65,50,'Blue: absolute amplitude    Red: residual-MAD normalized    Dashed: 5% reference',10)
text(c,65,27,'Settings 0-7: TC1; 8-15: TC2. See summary.csv for frequency and duration.',9);end(c,p)
c,p=begin('noise_trace_comparison','TC1 background traces from the archived slow-mean output','First 60 s of the archived stable interval; each displayed trace is demeaned, not normalized.')
manifest=pd.read_csv(ROOT/'results/thesis_completion_20260908/detection/noise_manifest.csv').set_index('case_id')
for j,case in enumerate(['afternoon_background','afternoon_vfd_stop','duo1_tc1_background','duo1_tc1_vfd_stop']):
 r=manifest.loc[case];b=(ROOT/r.source).parent;m=json.loads((b/'metadata.json').read_text(encoding='utf8'));z=np.load(b/'envelopes.npz');fs=float(z['envelope_rate_hz']);tt=m['lowpass_filter']['analysis_rate_first_sample_time_s']+np.arange(len(z['slow_mean']))/fs;yy=z['slow_mean'][:,json.loads(r.channels)].mean(axis=1)*1e6;yy=yy[tt>=m['config']['trim_start_seconds']][:round(fs*60)];yy-=yy.mean();t=np.arange(len(yy))/fs
 x=65+(j%2)*370;y=245-(j//2)*175;sx,sy=axes(c,x,y,295,110,0,60,-300,300)
 text(c,x,y+128,case,10);c.setStrokeColor(HexColor(BLUE if j<2 else RED));c.setLineWidth(.6)
 for k in range(1,len(t)):c.line(sx(t[k-1]),sy(yy[k-1]),sx(t[k]),sy(yy[k]))
text(c,65,25,'Vertical axes: microvolt (same limits). Horizontal axes: seconds. These are existing noise records.',9);end(c,p)
c,p=begin('normalization_power_tradeoff','Detection-power tradeoff at 60 seconds','The normalized score does not provide a uniformly better detector. No best-setting selection.')
q=base[base.T_s.eq(60)].merge(norm[norm.T_s.eq(60)],on=['detector','T_s','f_hz'],suffixes=('_base','_norm'))
for i,r in enumerate(q.itertuples()):
 y=335-i*42;text(c,35,y,f'{r.detector.upper()}  {r.f_hz:.4g} Hz',11)
 text(c,245,y,f'{r.mean_power90_minimum_tested_uv_peak_base:g} -> {r.mean_power90_minimum_tested_uv_peak_norm:g} microvolt',11)
 text(c,495,y,f'FPR {r.false_alarm_base:.1%} -> {r.false_alarm_norm:.1%}',11)
text(c,35,50,'Amplitude: smallest tested level giving at least 90% mean power, sustained at larger tested levels.',9)
text(c,35,27,'This is not a validated instrument limit of detection.',10,RED);end(c,p)
print('3 figures created')
