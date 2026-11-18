from pathlib import Path
import sys,csv,json,collections,statistics
ROOT=Path(__file__).resolve().parent; WORK=ROOT.parent.parent
sys.path.insert(0,str(ROOT.parent/'algorithm_textbook_20260907/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties, fontManager
fontManager.addfont('C:/Windows/Fonts/simsun.ttc')
plt.rcParams.update({'font.family':['SimSun','DejaVu Sans'],'font.size':10,'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':230})
OUT=ROOT/'figures';OUT.mkdir(exist_ok=True)
def rows(path):return list(csv.DictReader((WORK/path).open(encoding='utf-8-sig')))
def save(fig,name):
    fig.savefig(OUT/name,bbox_inches='tight',facecolor='white');plt.close(fig)
R='results/mentor_aligned_raw_completion_v3/'
allrows=rows(R+'full_raw_highfrequency/full_raw_highfrequency_matched_contrasts.csv')
active=[r for r in allrows if r['reference_condition']=='vfd_stop' and r['condition'] in ['run','30hz','50hz']]
groups=collections.defaultdict(list)
for r in active:groups[(r['dataset'],r['arrangement'],r['detector'])].append(r)
keys=sorted(groups)
strata=[]
for k in keys:
    vals=[float(r['pair_coherence_80_200khz_median_difference']) for r in groups[k]]
    strata.append({'group':'|'.join(k),'n':len(vals),'median':statistics.median(vals),'values':vals})
assert len(strata)==8 and len(active)==24
assert abs(statistics.median(x['median'] for x in strata)-.0117209055460989)<1e-10
epochs=rows(R+'FULL_RAW_EPOCH_SUPERIORITY.csv')
ep=[r for r in epochs if r['reference_condition']=='vfd_stop' and r['band_name']=='80_200khz' and r['metric']=='pair_coherence_median']
assert len(ep)==24
assert sum(float(r['active_epoch_median'])>float(r['reference_epoch_median']) for r in ep)==22
labels=[f'{k[0][4:6]}.{k[0][6:]} / {k[1]} / {k[2].upper()}' for k in keys]
fig,axs=plt.subplots(1,2,figsize=(8.0,4.0),sharey=True,layout='constrained')
for j,k in enumerate(keys):
    vals=[float(r['pair_coherence_80_200khz_median_difference']) for r in groups[k]]
    axs[0].scatter(vals,[j]*len(vals),s=22,color='#adb5bd',label='文件配对' if j==0 else None)
    axs[0].scatter(statistics.median(vals),j,s=40,color='#155d86',marker='D',label='分层中位数' if j==0 else None)
    ee=[float(r['active_epoch_median'])-float(r['reference_epoch_median']) for r in ep if (r['dataset'],r['arrangement'],r['detector'])==k]
    axs[1].scatter(ee,[j]*len(ee),s=22,color='#adb5bd')
    axs[1].scatter(statistics.median(ee),j,s=40,color='#a44035',marker='D')
for ax,title in zip(axs,['(a) 96窗口合并估计','(b) 8时段估计的中位数']):
    ax.axvline(0,color='black',lw=.8,ls='--');ax.set_title(title);ax.set_xlabel('RUN − STOP 相干差');ax.grid(axis='x',alpha=.2)
axs[0].set_yticks(range(8),labels);axs[0].invert_yaxis();axs[0].legend(loc='lower right',fontsize=8)
save(fig,'coherence.png')

duo=rows('results/experiment_20260806/duo_crossover_summary.csv')
bg=[r for r in duo if r['condition']=='background']
print('DUO_COLUMNS',list(bg[0]))
values=[float(r['estimated_detector_bias_db']) for r in bg]
fig,ax=plt.subplots(figsize=(6.7,3.0),layout='constrained')
bandlabels=['5–100 Hz','100 Hz–1 kHz','1–20 kHz','20–80 kHz','80–200 kHz']
ax.bar(range(len(bg)),values,color=['#155d86' if x>=0 else '#a44035' for x in values],width=.55)
ax.axhline(0,color='black',lw=.8);ax.set_xticks(range(len(bg)),bandlabels);ax.set_ylabel('背景探测器效应 TC1 − TC2 / dB');ax.set_ylim(-.62,.46)
for i,v in enumerate(values):ax.text(i,v+(.025 if v>0 else -.025),f'{v:+.3f}',ha='center',va='bottom' if v>0 else 'top')
save(fig,'background.png')

bands=rows('results/experiment_20260806/vfd_band_contrasts.csv')
fig,ax=plt.subplots(figsize=(6.7,3.1),layout='constrained')
for j,band in enumerate(['1_20khz','20_80khz','80_200khz']):
    for det,shift,color in [('TC1',-.11,'#155d86'),('TC2',.11,'#a44035')]:
        vals=[float(r['median_contrast_vfd_stop_db']) for r in bands if r['band']==band and r['detector']==det]
        ax.scatter(np.linspace(j+shift-.035,j+shift+.035,len(vals)),vals,s=26,color=color,label=det if j==0 else None)
ax.axhline(0,color='black',ls='--',lw=.8);ax.set_xticks(range(3),['1–20 kHz','20–80 kHz','80–200 kHz']);ax.set_ylabel('RUN相对本地STOP的频带差 / dB');ax.legend();ax.grid(axis='y',alpha=.2)
save(fig,'band_contrasts.png')

fig,ax=plt.subplots(figsize=(6.7,3.0),layout='constrained')
x=np.arange(3);width=.32
for offset,vals,label,color in [(-width/2,[23,20,23],'RUN − 背景','#155d86'),(width/2,[11,15,10],'RUN − STOP','#a44035')]:
    bars=ax.bar(x+offset,vals,width,label=label,color=color)
    for bar,v in zip(bars,vals):ax.text(bar.get_x()+bar.get_width()/2,v+.3,f'{v}/24',ha='center',fontsize=9)
ax.set_xticks(x,['宽带包络','差分包络','快速残余包络']);ax.set_ylim(0,29);ax.set_ylabel('CWT特征配对正差文件数');ax.legend(ncol=2,loc='upper center');ax.grid(axis='y',alpha=.15)
save(fig,'cwt_counts.png')

summary=rows(R+'identifiability/raw_completion_identifiability_summary.csv')
fig,axs=plt.subplots(1,2,figsize=(7.4,3.2),layout='constrained',gridspec_kw={'width_ratios':[1,1.5]})
mat=np.array([[12,12],[0,8]])
axs[0].imshow(mat,cmap='Blues',vmin=0,vmax=14)
for i in range(2):
    for j in range(2):axs[0].text(j,i,str(mat[i,j]),ha='center',va='center',fontsize=15,color='white' if mat[i,j]>=10 else 'black')
axs[0].set_xticks([0,1],['RUN','STOP']);axs[0].set_yticks([0,1],['RUN','STOP']);axs[0].set_xlabel('预测标签');axs[0].set_ylabel('实际标签');axs[0].set_title('(a) 合并探测器分组验证')
ss=[]
for task in ['run_vs_stop','run_vs_stop_tc1','run_vs_stop_tc2']:
    ss.append(next(r for r in summary if r['task']==task and r['feature_set']=='predefined_80_200khz_coherence'))
bars=axs[1].bar([0,1,2],[float(r['grouped_balanced_accuracy']) for r in ss],color=['#536d7c','#155d86','#a44035'],width=.55)
for bar,r in zip(bars,ss):
    v=float(r['grouped_balanced_accuracy']);p=float(r['permutation_p'])
    axs[1].text(bar.get_x()+bar.get_width()/2,v+.02,f'{v:.3f}\np={p:.3f}',ha='center',fontsize=9)
axs[1].set_ylim(0,1.13);axs[1].axhline(.5,color='black',ls='--',lw=.8);axs[1].set_xticks([0,1,2],['合并模型','TC1模型','TC2模型']);axs[1].set_ylabel('平衡准确率 BA');axs[1].set_title('(b) 分探测器重新训练与验证')
save(fig,'classification.png')

fig,ax=plt.subplots(figsize=(7.1,3.7));ax.axis('off')
boxes=[(.02,.72,.22,.16,'原始TDMS与元数据\n工况与通道映射'),(.37,.72,.26,.16,'逐记录质量判断\n稳定区间与对照配对'),(.02,.34,.27,.2,'完整PSD与慢变量\nfloat64精确归档'),(.365,.34,.27,.2,'96个原始短窗口\n相干补全支路'),(.71,.34,.27,.2,'周期与事件特征\n方法参数及代理检验'),(.24,.02,.52,.16,'文件与分层汇总 → 留一组验证\n效应量 分类召回与解释范围')]
for x,y,w,h,txt in boxes:
    ax.add_patch(plt.Rectangle((x,y),w,h,fill=False,edgecolor='#425563',lw=1));ax.text(x+w/2,y+h/2,txt,ha='center',va='center',fontsize=10)
for a,b in [((.24,.8),(.37,.8)),((.5,.72),(.155,.54)),((.5,.72),(.5,.54)),((.5,.72),(.845,.54)),((.155,.34),(.38,.18)),((.5,.34),(.5,.18)),((.845,.34),(.62,.18))]:ax.annotate('',xy=b,xytext=a,arrowprops={'arrowstyle':'->','lw':1,'color':'#425563'})
ax.set_xlim(0,1);ax.set_ylim(0,1)
save(fig,'workflow.png')
(ROOT/'evidence.json').write_text(json.dumps({'strata':strata,'epoch_positive_files':22,'epoch_files':24,'background_values':values,'classifier_rows':ss},ensure_ascii=False,indent=2),encoding='utf8')
print('FIGURES',len(list(OUT.glob('*.png'))));print('STRATA',strata)
