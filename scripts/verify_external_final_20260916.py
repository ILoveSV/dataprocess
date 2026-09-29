"""Finite values, export identity, conservation and numerical-sensitivity record."""
from pathlib import Path
import pandas as pd
import numpy as np
import hashlib,json
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT / 'analysis/thesis_followup_20260915/external'
t=pd.read_csv(OUT/'all_transfers.csv');c=pd.read_csv(OUT/'comparisons.csv')
expected=[f'gap_g{g:03d}' for g in [10,20,50,100,200,300]]+['single_g010','single_g300','gap_g010_fine','gap_g300_fine']
checks={}
for case in expected:
 for suffix in ['', '_ppr']:
  subset=t[t.case.eq(case+suffix)]
  assert set(subset.distance_m)=={2,3,4},case+suffix
  assert len(subset)==3
  assert subset.frequency_hz.eq(.001).all()
  checks[case+suffix+'_three_points']=True
norm=np.sqrt(sum(t[f'{a}_re']**2+t[f'{a}_im']**2 for a in ['ex','ey','ez']))
checks['max_norm_component_relative_error']=float(np.max(np.abs(norm-t.norm_e_v_m_per_v)/norm))
assert checks['max_norm_component_relative_error']<1e-8
for row in t.to_dict('records'):
 assert hashlib.sha256((ROOT/row['source']).read_bytes()).hexdigest()==row['source_sha256']
checks['all_transfer_source_hashes_match']=True
curr=pd.read_csv(OUT/'source_currents.csv')
assert set(expected)<=set(curr.case)
checks['max_source_current_balance_relative']=float(curr.balance_relative_to_pos.max())
assert checks['max_source_current_balance_relative']<1e-4
route=pd.read_csv(OUT/'routing_clearance.csv')
checks['minimum_declared_copper_capsule_clearance_mm']=float(route[route.routing.eq('declared_split_height')].capsule_clearance_mm.min())
assert checks['minimum_declared_copper_capsule_clearance_mm']>0
for typ in ['local_mesh_final_ppr','gap_mesh_ppr']:
 a=c[c.type.eq(typ)];assert len(a)>0
 checks[typ]={'maximum_abs_norm_change':float(a.norm_relative_change.abs().max()),'maximum_vector_difference':float(a.vector_relative_difference.max()),'screen_norm_2pct_pass':bool((a.norm_relative_change.abs()<.02).all()),'screen_vector_2pct_pass':bool((a.vector_relative_difference<.02).all())}
a=c[c.reference.eq('local_r30_h15_ppr')&c.candidate.eq('local_r40_h21_ppr')]
checks['domain_final_ppr']={'maximum_abs_norm_change':float(a.norm_relative_change.abs().max()),'maximum_vector_difference':float(a.vector_relative_difference.max()),'screen_vector_5pct_pass':bool((a.vector_relative_difference<.05).all())}
checks['interpretation']='Adjacent numerical sensitivity, not a bound on exact-solution error or experimental validation. Gap/route changes require their own endpoint mesh checks.'
checks['completed_date']='2026-09-18'
(OUT/'verification_final.json').write_text(json.dumps(checks,indent=2,ensure_ascii=False),encoding='utf8')
print(json.dumps(checks,indent=2,ensure_ascii=False))
