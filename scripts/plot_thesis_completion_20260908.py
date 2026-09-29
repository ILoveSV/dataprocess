"""Publication figures using ReportLab vector graphics, rasterized with PDFium."""
from pathlib import Path
import math
import numpy as np
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
import pypdfium2 as pdfium
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT / 'analysis/thesis_completion_20260908'
BLUE='#2166AC'; RED='#B2182B'; GREEN='#1B7837'; GREY='#777777'
def begin(path,title,subtitle='',h=420):
 c=canvas.Canvas(str(path.with_suffix('.pdf')),pagesize=(720,h)); c.setFont('Helvetica-Bold',16);c.drawString(32,h-28,title)
 c.setFont('Helvetica',9);c.drawString(32,h-45,subtitle);return c
def end(c,path):
 c.save();pdf=pdfium.PdfDocument(str(path.with_suffix('.pdf')));pdf[0].render(scale=2).to_pil().save(path);pdf.close()
def txt(c,x,y,s,size=9,color='#222222',align='left'):
 c.setFillColor(HexColor(color));c.setFont('Helvetica',size);getattr(c,{'left':'drawString','right':'drawRightString','center':'drawCentredString'}[align])(x,y,str(s))
def axes(c,box,xlim,ylim,xlabel,ylabel,log=False,xticks=None):
 x,y,w,h=box
 def sx(v):return x+w*((math.log10(v)-math.log10(xlim[0]))/(math.log10(xlim[1])-math.log10(xlim[0])) if log else (v-xlim[0])/(xlim[1]-xlim[0]))
 def sy(v):return y+h*(v-ylim[0])/(ylim[1]-ylim[0])
 for v in np.linspace(*ylim,5):
  yy=sy(v);c.setStrokeColor(HexColor('#E1E5EA'));c.setLineWidth(.5);c.line(x,yy,x+w,yy);txt(c,x-6,yy-3,f'{v:.3g}',8,align='right')
 for v in (xticks if xticks is not None else np.linspace(*xlim,5)):
  xx=sx(v);txt(c,xx,y-14,f'{v:.3g}',8,align='center')
 c.setStrokeColor(HexColor('#333333'));c.line(x,y,x+w,y);c.line(x,y,x,y+h)
 txt(c,x+w/2,y-30,xlabel,9,align='center');txt(c,x,y+h+10,ylabel,9)
 return sx,sy
def line(c,sx,sy,x,y,color=BLUE):
 c.setStrokeColor(HexColor(color));c.setFillColor(HexColor(color));c.setLineWidth(1.5)
 for i in range(1,len(x)):c.line(sx(x[i-1]),sy(y[i-1]),sx(x[i]),sy(y[i]))
 for a,b in zip(x,y):c.circle(sx(a),sy(b),2.3,stroke=0,fill=1)
g=pd.read_csv(OUT/'misses_by_group.csv'); rec=pd.read_csv(OUT/'record_predictions.csv')
p=OUT/'misses_by_group.png';c=begin(p,'RUN misses in saved grouped predictions','Combined model | 24 RUN records | no retraining')
for i,r in enumerate(g.itertuples()):
 y=325-i*34;txt(c,30,y+5,r.group.replace('20260','').replace('|',' / '),10)
 for v,col,offset in [(r.run_correct,BLUE,0),(r.run_missed,RED,r.run_correct)]:
  if v==0:continue
  c.setFillColor(HexColor(col));c.rect(265+offset*55,y,55*v,20,fill=1,stroke=0)
 txt(c,610,y+5,f'{r.run_missed}/{r.run_n} missed',10)
txt(c,265,30,'Blue: detected RUN',10,BLUE);txt(c,420,30,'Red: RUN predicted STOP',10,RED);end(c,p)
p=OUT/'feature_scatter.png';c=begin(p,'Fixed features and missed RUN records','Features are differences from local background. Panels use identical axis limits.')
x=rec.pool_minus_background;y=rec.epoch_minus_background
xlim=(float(x.min())-.003,float(x.max())+.003);ylim=(float(y.min())-.003,float(y.max())+.003)
for j,det in enumerate(['tc1','tc2']):
 sx,sy=axes(c,(65+j*345,90,270,230),xlim,ylim,'Pooled coherence minus BG','Epoch median minus BG')
 txt(c,180+j*345,350,det.upper(),12,align='center')
 for r in rec[rec.detector.eq(det)].itertuples():
  col=RED if r.error_type=='RUN漏判' else BLUE if r.true_label=='run' else GREY
  c.setFillColor(HexColor(col));c.setStrokeColor(HexColor(col));xx=sx(r.pool_minus_background);yy=sy(r.epoch_minus_background)
  if r.true_label=='stop':c.rect(xx-3,yy-3,6,6,fill=1,stroke=0)
  else:c.circle(xx,yy,3,fill=1,stroke=0)
txt(c,65,30,'Circle: RUN   Square: STOP   Red: missed RUN   Blue: detected RUN',10);end(c,p)
p=OUT/'background_and_contrasts.png';c=begin(p,'Background level and condition contrasts','Descriptive group summaries; differences do not establish a physical cause of misses.')
for j,(col,title) in enumerate([('background_pool','Background pooled coherence'),('run_pool_bg_median','Median RUN minus BG')]):
 sx,sy=axes(c,(60+j*350,95,285,235),(-.5,7.5),(0,max(g[col].max()*1.15,.01)), 'Group index (same order as miss figure)',title,xticks=list(range(8)))
 for i,r in enumerate(g.itertuples()):
  v=getattr(r,col);c.setFillColor(HexColor(BLUE if r.detector=='tc1' else RED));c.rect(sx(i)-9,sy(0),18,sy(v)-sy(0),fill=1,stroke=0)
txt(c,65,35,'Blue: TC1    Red: TC2',10);end(c,p)
gap=pd.read_csv(OUT/'gap/gap_comparison.csv');p=OUT/'gap/gap_comparison.png';c=begin(p,'Electrode gap comparison in the water-domain model','Scenario: electrode pair center shifted +55 mm; same mesh level 5 at all six gaps.')
sx,sy=axes(c,(65,90,275,230),(0,300),(0,100),'Surface gap (mm)','Water resistance (ohm)',xticks=[0,50,100,200,300]);line(c,sx,sy,gap.gap_mm.tolist(),gap.resistance_ohm.tolist())
sx,sy=axes(c,(415,90,270,230),(0,300),(0,5.5),'Surface gap (mm)','Uniform-water dipole proxy ratio',xticks=[0,50,100,200,300])
line(c,sx,sy,gap.gap_mm.tolist(),gap.uniform_water_dipole_fixed_i_relative.tolist(),BLUE);line(c,sx,sy,gap.gap_mm.tolist(),gap.uniform_water_dipole_fixed_v_relative.tolist(),RED)
txt(c,420,345,'Blue: fixed I    Red: fixed V',9);txt(c,65,32,'Right panel is an analytical proxy, not COMSOL air-field gain or detector sensitivity.',10);end(c,p)
curves=pd.read_csv(OUT/'detection/power_curves.csv');summ=pd.read_csv(OUT/'detection/power_summary.csv')
p=OUT/'detection/power_curves_60s.png';c=begin(p,'Conditional detection probability in archived noise','Known frequency; 60 s window; equal record weights; software injection after slow-mean extraction.')
colors=[BLUE,GREEN,RED]
for j,det in enumerate(['tc1','tc2']):
 sx,sy=axes(c,(65+j*345,95,270,220),(.01,1000),(0,1.05),'Injected peak amplitude (microvolt)','Detection probability',True,[.01,.1,1,10,100,1000]);txt(c,190+j*345,345,det.upper(),12,align='center')
 for k,freq in enumerate(sorted(curves.f_hz.unique())):
  z=curves[curves.detector.eq(det)&curves.T_s.eq(60)&np.isclose(curves.f_hz,freq)&curves.amplitude_uv_peak.gt(0)]
  line(c,sx,sy,z.amplitude_uv_peak.tolist(),z.power.tolist(),colors[k])
  txt(c,65+k*220,53,f'{freq:.4g} Hz',10,colors[k])
txt(c,65,27,'Observed held-out null false alarms: TC1 25%; TC2 12.5% (60 s). Not a validated LOD.',10,RED);end(c,p)
p=OUT/'detection/heldout_false_alarm.png';c=begin(p,'Threshold transfer to held-out noise groups','Threshold: calibration-noise 95th percentile. The nominal 5% rate is not maintained.')
sx,sy=axes(c,(65,100,610,215),(-.5,15.5),(0,.3),'Setting index (see power_summary.csv)','Held-out null false-alarm fraction',xticks=list(range(16)))
for i,r in enumerate(summ.itertuples()):
 c.setFillColor(HexColor(BLUE if r.detector=='tc1' else RED));c.rect(sx(i)-8,sy(0),16,sy(r.heldout_null_false_alarm)-sy(0),stroke=0,fill=1)
c.setStrokeColor(HexColor(GREY));c.setDash(3,3);c.line(sx(-.5),sy(.05),sx(15.5),sy(.05));txt(c,80,350,'Dashed line: 5% reference',10);txt(c,65,40,'Settings 0-7: TC1. Settings 8-15: TC2. Multiple windows are not independent experiments.',10);end(c,p)
print('Created 6 figures as vector PDF and 2x PNG')
