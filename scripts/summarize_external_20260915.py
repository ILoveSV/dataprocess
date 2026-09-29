"""Traceable comparison of preserved September 9 and continuation external-field cases."""
from pathlib import Path
import pandas as pd
import numpy as np
import hashlib,json
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/thesis_followup_20260915/external'
rows=[]
columns=['frequency_hz','v_re','v_im','ex_re','ex_im','ey_re','ey_im','ez_re','ez_im','norm_e_v_m_per_v']
for directory in [ROOT/'results/thesis_followup_20260909/external',OUT]:
 for p in sorted(directory.glob('*_[234]m.csv')):
  a=pd.read_csv(p,comment='%',header=None)
  if a.shape[1]==11:a=a.drop(columns=1)
  assert a.shape[1]==10,(p,a.shape)
  a.columns=columns
  for row in a.to_dict('records'):
   assert np.isfinite([row[k] for k in columns]).all()
   row.update(case=p.stem[:-3],distance_m=int(p.stem[-2]),source=str(p.relative_to(ROOT)),source_sha256=hashlib.sha256(p.read_bytes()).hexdigest());rows.append(row)
d=pd.DataFrame(rows);assert not d.duplicated(['case','distance_m','frequency_hz']).any()
d.to_csv(OUT/'all_transfers.csv',index=False,encoding='utf-8-sig')
pairs=[('local_h100','local_h075','local_mesh'),('local_h075','local_h050','local_mesh'),('local_h050','local_r15_h6','domain'),('local_r15_h6','local_r20_h9','domain'),('local_r20_h9','local_r30_h15','domain'),('local_r30_h15','local_r40_h21','domain'),('local_r30_h15','local_r30_h15_h025','local_mesh_final'),('gap_g010','gap_g300','gap'),('gap_g010','single_g010','boundary'),('gap_g300','single_g300','boundary')]
pairs += [('gap_g010','gap_g010_fine','gap_mesh'),('gap_g300','gap_g300_fine','gap_mesh')]
pairs +=[(a+'_ppr',b+'_ppr',t+'_ppr') for a,b,t in pairs]
comparisons=[]
for a,b,t in pairs:
 for distance in [2,3,4]:
  u=d[d.case.eq(a)&d.distance_m.eq(distance)];v=d[d.case.eq(b)&d.distance_m.eq(distance)]
  if len(u)!=1 or len(v)!=1:continue
  u=u.iloc[0];v=v.iloc[0]
  eu=np.array([complex(u.ex_re,u.ex_im),complex(u.ey_re,u.ey_im),complex(u.ez_re,u.ez_im)]);ev=np.array([complex(v.ex_re,v.ex_im),complex(v.ey_re,v.ey_im),complex(v.ez_re,v.ez_im)])
  comparisons.append(dict(reference=a,candidate=b,type=t,distance_m=distance,norm_relative_change=v.norm_e_v_m_per_v/u.norm_e_v_m_per_v-1,vector_relative_difference=np.linalg.norm(ev-eu)/np.linalg.norm(eu)))
c=pd.DataFrame(comparisons);c.to_csv(OUT/'comparisons.csv',index=False,encoding='utf-8-sig')
print(c[c.type.str.contains('ppr')].to_string(index=False))
