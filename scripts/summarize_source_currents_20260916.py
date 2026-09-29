"""Source-current diagnostics and conditional fixed-current amplitude scaling."""
from pathlib import Path
import hashlib
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/thesis_followup_20260915/external'
rows=[]
for p in sorted(OUT.glob('*_current_pos.csv')):
 case=p.name.removesuffix('_current_pos.csv');row={'case':case}
 currents=[]
 for g in ['pos','neg','ground']:
  f=OUT/f'{case}_current_{g}.csv';a=pd.read_csv(f,comment='%',header=None)
  assert a.shape==(1,2),(f,a.shape)
  z=complex(str(a.iloc[0,1]).replace('i','j'));assert np.isfinite([z.real,z.imag]).all()
  row.update({f'{g}_re_a':z.real,f'{g}_im_a':z.imag,f'{g}_source':str(f.relative_to(ROOT)),f'{g}_sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
  if 'frequency_hz' in row:assert row['frequency_hz']==a.iloc[0,0]
  row['frequency_hz']=a.iloc[0,0];currents.append(z)
 pos,neg,ground=currents;assert abs(pos)>0
 row.update(pos_abs_a=abs(pos),balance_abs_a=abs(sum(currents)),balance_relative_to_pos=abs(sum(currents))/abs(pos),effective_impedance_magnitude_ohm=1/abs(pos))
 rows.append(row)
c=pd.DataFrame(rows);assert not c.duplicated(['case','frequency_hz']).any()
c.to_csv(OUT/'source_currents.csv',index=False,encoding='utf-8-sig')
t=pd.read_csv(OUT/'all_transfers.csv');scaled=[]
for r in rows:
 for e in t[t.case.eq(r['case']+'_ppr')].to_dict('records'):
  assert e['frequency_hz']==r['frequency_hz']
  scaled.append(dict(case=r['case'],distance_m=e['distance_m'],frequency_hz=r['frequency_hz'],gap_mm=int(r['case'].split('_g')[1][:3]) if '_g' in r['case'] else np.nan,
   e_norm_per_1v=e['norm_e_v_m_per_v'],positive_current_per_1v_a=r['pos_abs_a'],scale_to_10ma=.01/r['pos_abs_a'],e_norm_at_10ma_v_m=e['norm_e_v_m_per_v']*.01/r['pos_abs_a'],effective_impedance_magnitude_ohm=r['effective_impedance_magnitude_ohm'],balance_relative_to_pos=r['balance_relative_to_pos'],
   meaning='Amplitude scaling of specified ground-referenced drive to |positive-port current|=10mA; not a solved floating-current source'))
pd.DataFrame(scaled).to_csv(OUT/'gap_current_scaled.csv',index=False,encoding='utf-8-sig')
print(c[['case','pos_abs_a','effective_impedance_magnitude_ohm','balance_relative_to_pos']].to_string(index=False))
