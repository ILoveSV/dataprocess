"""Scientific consistency checks on the exported ICCP calculations."""
import json
from pathlib import Path
import numpy as np
from summarize_results import AUDIT, read_points

ROOT=Path(__file__).resolve().parent
results={}
for p in (ROOT/'results').glob('*_audit.csv'):
    case=p.stem.removesuffix('_audit')
    a=dict(zip(AUDIT,np.loadtxt(p,comments='%',delimiter=',')))
    scale=max(1,abs(a['I_ICCP_A']),abs(a['steel_net_anodic_A']),abs(a['prop_net_anodic_A']))
    assert abs(a['circuit_residual_A']) < 1e-7*scale,(case,'circuit balance')
    assert min(a[f'anode{k}_area_m2'] for k in range(1,5))>0,(case,'anode area')
    assert a['steel_wet_area_m2']>0 and a['prop_wet_area_m2']>0
    for mode,count in [('axial',241),('side',6),('plane',3321)]:
        x=read_points(ROOT/'results'/f'{case}_{mode}.csv')
        assert x.shape==(count,8),(case,mode,x.shape)
        assert np.isfinite(x).all(),(case,mode,'nonfinite values')
        np.testing.assert_allclose(np.linalg.norm(x[:,4:7],axis=1),x[:,7],rtol=1e-8,atol=1e-14)
        if mode=='side':np.testing.assert_allclose(x[:,1],[10,20,30,50,75,100],atol=1e-9)
    results[case]={'circuit_balance_pass':True,'finite_field_values_pass':True,'field_vector_norm_pass':True,
      'steel_extrapolated_area_fraction':a['steel_extrapolated_area_fraction'],
      'prop_extrapolated_area_fraction':a['prop_extrapolated_area_fraction']}
(ROOT/'results'/'validation.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(json.dumps(results,indent=2))
