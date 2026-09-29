from pathlib import Path
import pandas as pd
import json,hashlib
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT / 'analysis/thesis_completion_20260908/gap'
cols=['gap_mm','pair_center_x_mm','mesh_auto_size','terminal_v_at_10ma','resistance_ohm','power_w','power_balance_relative_error','water_volume_m3','mean_water_field_v_m']
rows=[]
for p in sorted(OUT.glob('g*_m*.csv')):
 d=pd.read_csv(p,comment='%',header=None,names=cols); assert len(d)==1
 r=d.iloc[0].to_dict();r.update(case_id=p.stem,source=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest());rows.append(r)
all=pd.DataFrame(rows); assert len(all)==11
main=all[all.pair_center_x_mm.eq(55)&all.mesh_auto_size.eq(5)].sort_values('gap_mm').copy()
assert main.gap_mm.tolist()==[10,20,50,100,200,300]
main['center_separation_mm']=main.gap_mm+62.5
main['current_at_1v_ma']=1000/main.resistance_ohm
main['mean_water_field_at_1v_v_m']=main.mean_water_field_v_m/main.terminal_v_at_10ma
main['uniform_water_dipole_fixed_i_relative']=main.center_separation_mm/main.center_separation_mm.iloc[0]
main['uniform_water_dipole_fixed_v_relative']=main.uniform_water_dipole_fixed_i_relative*main.resistance_ohm.iloc[0]/main.resistance_ohm
mesh=[]
for gap in [10,300]:
 z=all[all.gap_mm.eq(gap)&all.pair_center_x_mm.eq(55)].set_index('mesh_auto_size')
 for size in [5,4]:
  mesh.append(dict(gap_mm=gap,mesh_auto_size=size,reference_size=3,resistance_relative_difference=(z.loc[size,'resistance_ohm']/z.loc[3,'resistance_ohm']-1),mean_field_relative_difference=(z.loc[size,'mean_water_field_v_m']/z.loc[3,'mean_water_field_v_m']-1)))
for name,df in [('all_cases',all),('gap_comparison',main),('mesh_comparison',pd.DataFrame(mesh))]:df.to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig')
q=dict(successful_cases=len(all),failed_cases=['g010_x055_m6','g300_x055_m6'],failure_reason='Coarse mesh geometry meshing failure; retained as failures',max_power_balance_relative_error=float(all.power_balance_relative_error.max()),water_volume_relative_span=float((all.water_volume_m3.max()-all.water_volume_m3.min())/all.water_volume_m3.mean()),resistance_300_to_10_main=float(main.resistance_ohm.iloc[-1]/main.resistance_ohm.iloc[0]),uniform_water_dipole_fixed_i_gain=float(main.uniform_water_dipole_fixed_i_relative.iloc[-1]),uniform_water_dipole_fixed_v_gain=float(main.uniform_water_dipole_fixed_v_relative.iloc[-1]),air_field_computed=False,source_model='simulation/models/cathodic_protection_tank_3d_current_sweep_v3.mph',source_model_sha256=hashlib.sha256((ROOT / 'simulation/models/cathodic_protection_tank_3d_current_sweep_v3.mph').read_bytes()).hexdigest())
(OUT/'verification.json').write_text(json.dumps(q,indent=2),encoding='utf8')
print(main[['gap_mm','resistance_ohm','current_at_1v_ma','uniform_water_dipole_fixed_i_relative','uniform_water_dipole_fixed_v_relative']].to_string(index=False));print(pd.DataFrame(mesh).to_string(index=False));print(json.dumps(q,indent=2))
