"""Traceable thesis registry and descriptive audit of already saved OOF predictions."""
from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/research_validation_20260908/deps'))
import numpy as np
import pandas as pd
OUT=ROOT/'results/thesis_completion_20260908';OUT.mkdir(exist_ok=True)
A=ROOT/'results/coherence_precision_audit_20260908'
def csv(p):return pd.read_csv(p)
def dump(df,name):df.to_csv(OUT/name,index=False,encoding='utf-8-sig')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
p=csv(A/'predictions.csv');p=p[p.config.eq('full64_common')].copy()
f=csv(A/'features.csv');f=f[f.config.eq('full64_common')].copy()
main=p[p.model_detector.eq('combined')].copy()
assert len(main)==32 and not main.case_id.duplicated().any()
main=main.merge(f[['case_id','pool','epoch_median','channel_count']],on='case_id',validate='one_to_one')
bg=f[['case_id','pool','epoch_median']].rename(columns={'case_id':'reference_case_id','pool':'background_pool','epoch_median':'background_epoch_median'})
main=main.merge(bg,on='reference_case_id',validate='many_to_one')
single=p[p.model_detector.isin(['tc1','tc2'])][['case_id','predicted_label']].rename(columns={'predicted_label':'single_detector_prediction'})
main=main.merge(single,on='case_id',validate='one_to_one')
main['pool_minus_background']=main.pool-main.background_pool
main['epoch_minus_background']=main.epoch_median-main.background_epoch_median
main['error_type']=np.select([main.true_label.eq('run')&main.predicted_label.eq('stop'),main.true_label.eq('stop')&main.predicted_label.eq('run')],['RUN漏判','STOP误报'],default='正确')
main=main.sort_values(['dataset','arrangement','detector','true_label','output_hz','carrier_khz']).reset_index(drop=True)
main.insert(0,'record_id',[f'R{i+1:02}' for i in range(len(main))])
assert (main.error_type=='RUN漏判').sum()==12 and (main.error_type=='STOP误报').sum()==0
dump(main,'record_predictions.csv');dump(main[main.error_type.eq('RUN漏判')],'missed_run_records.csv')
groups=[]
for g,z in main.groupby('group',sort=True):
 r=z[z.true_label.eq('run')];s=z[z.true_label.eq('stop')]
 groups.append({'group':g,'detector':z.detector.iloc[0],'run_n':len(r),'run_correct':int(r.predicted_label.eq('run').sum()),'run_missed':int(r.predicted_label.eq('stop').sum()),'stop_n':len(s),'stop_false_alarm':int(s.predicted_label.eq('run').sum()),'single_run_correct':int(r.single_detector_prediction.eq('run').sum()),'background_pool':z.background_pool.iloc[0],'run_pool_bg_median':r.pool_minus_background.median(),'stop_pool_bg':s.pool_minus_background.iloc[0]})
g=pd.DataFrame(groups);dump(g,'misses_by_group.csv')
registry=[]
def add(topic,metric,value,unit,source,selector,scope,claim,limit,chapter='5',kind='既有实测数据分析'):
 path=ROOT/source;assert path.exists(),path
 registry.append({'编号':f'E{len(registry)+1:02}','主题':topic,'指标':metric,'数值':float(value),'单位':unit,'证据类型':kind,'数据范围':scope,'允许表述':claim,'限制':limit,'建议章节':chapter,'来源文件':source,'定位条件或计算':selector,'来源SHA256':sha(path)})
src='results/coherence_precision_audit_20260908/'
effects=csv(A/'effect_summary.csv');r=effects[effects.config.eq('full64_common')].iloc[0]
for metric,v,u in [('RUN−STOP正差层数',r.positive_strata,'层/8层'),('RUN−STOP分层中位差',r.median_difference,'无量纲'),('时段中位数正差配对',r.epoch_positive_files,'配对/24配对'),('Wilcoxon名义p',r.wilcoxon_p,'p')]:
 add('高频相干复核',metric,v,u,src+'effect_summary.csv','config=full64_common','7月31日和8月6日；80≤f<199 kHz','固定共同健康通道后方向保持','8层并非8个独立日期；未重算旧12项检验族q')
cls=csv(A/'classification.csv')
for det in ['combined','tc1','tc2']:
 z=cls[cls.config.eq('full64_common')&cls.detector.eq(det)].iloc[0]
 for name,col in [('BA','grouped_balanced_accuracy'),('组内置换p','permutation_p')]:
  add('状态分类',det+' '+name,z[col],'比例' if name=='BA' else 'p',src+'classification.csv',f'config=full64_common; detector={det}; {col}','32条合并或16条单探测器记录','探索性组外状态区分','依赖本地背景；频带经过前期探索；非新日期验证')
for label,value in [('RUN召回',.5),('STOP召回',1.0)]:add('误判',label,value,'比例',src+'predictions.csv','full64_common; combined; 按真实类别计正确比例','24 RUN / 8 STOP','合并模型漏判12条RUN、未误报STOP','零观测误报不等于未来误报率为零')
ld=csv(A/'leave_date_stress.csv')
for config in ['full64_common','full64_strict']:
 z=ld[ld.config.eq(config)&ld.detector.eq('tc1')].iloc[0]
 add('日期与通道敏感性',config+' TC1 BA',z.balanced_accuracy,'比例',src+'leave_date_stress.csv',f'{config}; tc1','仅2个已探索日期','严格通道下留日期表现下降','不能以高分配置反向选择通道；不是外部验证')
cross=csv(ROOT/'results/experiment_20260806/duo_crossover_summary.csv')
for _,r in cross[cross.condition.eq('background')].iterrows():add('换位背景',r.band+' TC1−TC2',r.estimated_detector_bias_db,'dB','results/experiment_20260806/duo_crossover_summary.csv',f'condition=background; band={r.band}','8月6日双探测器换位','探测器差异随频带变化','特定批次表观差异，不是永久灵敏度校准')
vfd=csv(ROOT/'results/experiment_20260806/vfd_band_contrasts.csv')
for band in ['1_20khz','20_80khz','80_200khz']:
 z=vfd[vfd.band.eq(band)]
 for name,v in [('最小值',z.median_contrast_vfd_stop_db.min()),('最大值',z.median_contrast_vfd_stop_db.max())]:add('频带功率',band+' RUN−STOP '+name,v,'dB','results/experiment_20260806/vfd_band_contrasts.csv',f'band={band}; median_contrast_vfd_stop_db; {name}','固定2 m的12条变频参数RUN','变化属于频带重分配','健康通道规则；宽带差不是窄线峰值')
rs=json.loads((ROOT/'results/mentor_aligned_raw_completion_v3/REPORT_SUMMARY.json').read_text())
add('载波辨识','梳状模板正确数',rs['carrier_correct_count'],'条/12条','results/mentor_aligned_raw_completion_v3/REPORT_SUMMARY.json','carrier_correct_count','12条载波设置记录','未形成稳定载波对应','不同于最强单峰2/12指标')
add('自然弛豫','可信主动脉冲弛豫工况',rs['pulse_credible_relaxation_count'],'工况/188工况','results/mentor_aligned_raw_completion_v3/REPORT_SUMMARY.json','pulse_credible_relaxation_count','188工况；533状态转换','既有规则下未形成可信弛豫参数','不等于没有重复波形；属于主动脉冲支路','讨论')
h=csv(ROOT/'results/experiment_20260811/fixed_005hz_harmonic.csv')
for case in ['005hz','bkg','bkg2']:
 z=h[h.case.eq(case)&h.feature.eq('slow_mean')]
 if len(z):add('旧阴极保护',case+' 0.05 Hz幅值中位数',z.iloc[0].median_amplitude_uv_peak,'µV peak','results/experiment_20260811/fixed_005hz_harmonic.csv',f'case={case}; feature=slow_mean','8月11日第一批','目标与同批背景对照','不同于相干统计；没有独立场强标定','6')
fr=csv(ROOT/'results/mentor_aligned_methods_v2/FILTER_ROBUSTNESS_SUMMARY.csv')
for name in ['savgol_1p1s','kalman_local_level']:
 z=fr[fr.filter_name.eq(name)&fr.analysis_type.eq('synthetic_injection')]
 if len(z):add('软件注入既有结果',name+' 正弦幅值回收',z.iloc[0].sinusoid_recovery_ratio_median,'比例','results/mentor_aligned_methods_v2/FILTER_ROBUSTNESS_SUMMARY.csv',f'filter_name={name}; synthetic_injection','旧3.1 s注入','滤波可能削弱候选幅值','幅值回收不等于检出概率','4','软件注入')
gap=pd.read_csv(OUT/'gap/gap_comparison.csv')
for _,z in gap.iterrows():
 add('间隙水域仿真',f'{int(z.gap_mm)} mm 水路电阻',z.resistance_ohm,'Ω','results/thesis_completion_20260908/gap/gap_comparison.csv',f'gap_mm={z.gap_mm}; mesh=5; pair_x=55 mm','六种间隙条件；10 mA线性水域模型','同一几何移动规则下的条件仿真','非实测；不含电极极化；不是空气场或检出距离','6','COMSOL条件仿真')
det=pd.read_csv(OUT/'detection/power_summary.csv')
for _,z in det[det.T_s.eq(60)].iterrows():
 for metric,column,unit in [('90%平均检出最小测试幅值','minimum_tested_amplitude_for_mean_power90_uv_peak','µV peak'),('留组空白误报','heldout_null_false_alarm','比例')]:
  add('检出能力软件注入',f'{z.detector} {z.f_hz:.6g} Hz 60 s {metric}',z[column],unit,'results/thesis_completion_20260908/detection/power_summary.csv',f'detector={z.detector}; T_s=60; f_hz={z.f_hz}; {column}','每探测器8条泵系统BG/STOP；64个固定相位','已知频率的输出域条件检出能力','误报未稳定控制在5%；无场强标定；不是阴极保护实测检出限','6','软件注入')
reg=pd.DataFrame(registry);dump(reg,'result_registry.csv')
bydet=main[main.true_label.eq('run')].groupby('detector').agg(n=('case_id','count'),missed=('error_type',lambda s:(s=='RUN漏判').sum()))
lines=['# 结果主表与漏判分析','\n2026年9月8日。只复用既有特征和组外预测，没有重训模型或新增实验。',f'\n结果主表收录{len(reg)}项可追溯数字，CSV保留来源定位与哈希。','\n## 主要发现','\n固定共同健康通道合并模型：24条RUN正确12条、漏判12条；8条STOP全部正确。BA=0.75，普通准确率=20/32=0.625。']
for det,z in bydet.iterrows():lines.append(f'\n合并模型在{det.upper()}记录中漏判{int(z.missed)}/{int(z.n)}条RUN。这里按测试记录探测器分组，不是重新训练的单探测器模型。')
lines+=['\n| 分层 | RUN正确 | RUN漏判 | 单探测器模型RUN正确 |','|---|---:|---:|---:|']
for _,z in g.iterrows():lines.append(f'|{z.group.replace(chr(124), " / ")}|{z.run_correct}/{z.run_n}|{z.run_missed}/{z.run_n}|{z.single_run_correct}/{z.run_n}|')
lines+=['\n合并模型与单探测器模型使用不同训练集及训练折尺度，因此不能把其预测混在一起计算一个成绩。','\n8层RUN−STOP同向是层内对比；分类输入是RUN或STOP相对本地背景的特征差，跨层幅度和背景会变化。存在同向差异并不保证一条跨层规则能识别全部记录。图中差异属于描述性线索，不据此断言误判的物理原因。','\n![漏判分布](misses_by_group.png)','\n![固定特征散点](feature_scatter.png)','\n![背景与相对特征](background_and_contrasts.png)','\n## 使用范围','\n本分析不重新筛选频段、阈值、通道或分类器。只有两个旧日期，未计算把窗口当独立实验的置信区间。当前分组保持原定义；同步探测器是否对应同一真实采集单元仍需记录核实。','\n完整逐记录表为record_predictions.csv，12条漏判单列在missed_run_records.csv；主表为result_registry.csv。']
(OUT/'RESULTS_AND_MISSES.md').write_text('\n'.join(lines),encoding='utf8')
(OUT/'registry_workbook_data.json').write_text(json.dumps({'registry':registry,'records':json.loads(main.replace({np.nan:None}).to_json(orient='records',force_ascii=False)),'groups':json.loads(g.to_json(orient='records',force_ascii=False))},ensure_ascii=False,indent=2),encoding='utf8')
(OUT/'registry_verification.json').write_text(json.dumps({'record_count':len(main),'run_count':24,'run_missed':12,'stop_false_alarm':0,'registry_rows':len(reg),'source_hashes_checked':True,'model_retrained':False,'script_sha256':sha(Path(__file__))},indent=2),encoding='utf8')
print(json.dumps({'registry_rows':len(reg),'misses_by_detector':bydet.to_dict(),'group_counts':g[['group','run_missed','run_n']].to_dict('records')},ensure_ascii=False))
