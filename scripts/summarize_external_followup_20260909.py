from pathlib import Path
import json,hashlib
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/thesis_followup_20260909/external'
cols=['frequency_hz','v_re','v_im','ex_re','ex_im','ey_re','ey_im','ez_re','ez_im','norm_e_v_m_per_v']
rows=[]
for p in sorted(OUT.glob('*_[234]m.csv')):
 d=int(p.stem[-2]);case=p.stem[:-3];z=pd.read_csv(p,comment='%',header=None)
 if z.shape[1]==11:z=z.drop(columns=1)
 assert z.shape[1]==10,(p,z.shape)
 z.columns=cols
 for r in z.to_dict('records'):
  assert all(np.isfinite(r[k]) for k in cols)
  r.update(case=case,distance_from_wall_m=d,source=str(p.relative_to(ROOT)),source_sha256=hashlib.sha256(p.read_bytes()).hexdigest());rows.append(r)
df=pd.DataFrame(rows);df.to_csv(OUT/'all_transfers.csv',index=False,encoding='utf-8-sig')
comparisons=[]
pairs=[('original_saved','headspace_fixed','geometry'),('headspace_fixed','headspace_tape_fixed','geometry'),('headspace_tape_fixed','padded_base','floor_padding'),('padded_base','padded_coarse','mesh'),('padded_base','padded_fine','mesh'),('padded_base','padded_medium','domain'),('padded_medium','padded_large','domain'),('padded_large','padded_larger','domain'),('local_h100','local_h075','local_mesh'),('local_h075','local_h050','local_mesh')]
pairs += [(a+'_ppr',b+'_ppr',kind+'_ppr') for a,b,kind in pairs]
for a,b,kind in pairs:
 for distance in [2,3,4]:
  z1=df[df.case.eq(a)&df.distance_from_wall_m.eq(distance)];z2=df[df.case.eq(b)&df.distance_from_wall_m.eq(distance)]
  if len(z1)!=1 or len(z2)!=1:continue
  r=z1.iloc[0];s=z2.iloc[0]
  ea=np.array([complex(r.ex_re,r.ex_im),complex(r.ey_re,r.ey_im),complex(r.ez_re,r.ez_im)])
  eb=np.array([complex(s.ex_re,s.ex_im),complex(s.ey_re,s.ey_im),complex(s.ez_re,s.ez_im)])
  comparisons.append(dict(reference=a,candidate=b,type=kind,distance_m=distance,norm_relative_change=s.norm_e_v_m_per_v/r.norm_e_v_m_per_v-1,vector_relative_difference=np.linalg.norm(eb-ea)/np.linalg.norm(ea)))
pd.DataFrame(comparisons).to_csv(OUT/'comparisons.csv',index=False,encoding='utf-8-sig')
bench=[]
for p in OUT.glob('sphere_benchmark*.csv'):
 z=pd.read_csv(p,comment='%',header=None).iloc[0].to_numpy()
 assert len(z)==13
 for i in range(3):
  radius=z[1+i];ve=(1/radius-1/5)/(1-1/5);ee=1/(radius**2*(1-1/5))
  bench.append(dict(case=p.stem,radius_m=radius,potential=z[4+i],exact_potential=ve,potential_relative_error=z[4+i]/ve-1,ex=z[7+i],exact_ex=ee,ex_relative_error=z[7+i]/ee-1,norm_e=z[10+i]))
pd.DataFrame(bench).to_csv(OUT/'sphere_comparison.csv',index=False,encoding='utf-8-sig')
print(pd.DataFrame(comparisons).to_string(index=False))
