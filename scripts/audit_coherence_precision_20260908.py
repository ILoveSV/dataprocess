"""Bounded, versioned audit of the existing two coherence features; no source edits."""
from pathlib import Path
import sys,os,json,hashlib,ast,time,argparse,itertools,warnings
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / 'local/tmp/research_validation_20260908/deps'))
os.environ.setdefault('OMP_NUM_THREADS','1')
import numpy as np
import pandas as pd
import scipy
from scipy import fft,signal,stats
from nptdms import TdmsFile
from sklearn.feature_selection import SelectKBest,f_classif
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score,confusion_matrix
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
import sklearn,nptdms
OUT=ROOT / 'analysis/coherence_precision_audit_20260908'
OLD=ROOT / 'analysis/mentor_aligned_raw_completion_v3'
META=['dataset','case_id','arrangement','detector','condition','distance','carrier_khz','output_hz']
INDEX_COLUMNS=META+['reference_case_id','reference_condition']
KEYS=['pair_coherence_80_200khz_median','pair_coherence_80_200khz_epoch_median']
CONFIGS=['legacy32_original','center64_then32_original','full64_original','full64_common','full64_strict']
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stable_seed(*parts):return int.from_bytes(hashlib.sha256('|'.join(map(str,parts)).encode()).digest()[:4],'little')
def original_function(name):
    source=ROOT/'scripts/analyze_mentor_multimethod_identifiability.py'
    tree=ast.parse(source.read_text(encoding='utf8'))
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(source),'exec'),globals())
for name in ['grouped_predictions','shuffled_within_groups','evaluate_task']:original_function(name)
def groups(frame):return frame['dataset'].astype(str)+'|'+frame['arrangement']+'|'+frame['detector']
def setup():
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'checkpoints').mkdir(exist_ok=True)
    old=pd.read_csv(OLD/'full_raw_highfrequency/full_raw_highfrequency_features.csv')
    old=old[old.dataset.isin([20260731,20260806])].copy().reset_index(drop=True)
    assert len(old)==40
    h=pd.read_csv(ROOT / 'analysis/mentor_aligned_pre_electrochemical_v1/channel_health_dynamic.csv')
    raw={}
    for p in Path('D:/Lab/raw/raw').rglob('*.tdms'):raw.setdefault(p.name,[]).append(p)
    records=[]
    for _,r in old.iterrows():
        archive=ROOT/('experiments/20260731/tdms/exact_archive' if r.dataset==20260731 else 'experiments/20260806/exact_archive')/r.case_id
        m=json.loads((archive/'metadata.json').read_text(encoding='utf8'))
        name=Path(m.get('source_tdms_path',m.get('source_path'))).name
        candidates=raw.get(name,[])
        assert len(candidates)==1,(name,candidates)
        p=candidates[0];assert p.stat().st_size==m['source_size_bytes'],p
        hh=h[h.case_id==r.case_id].sort_values('channel_index');assert len(hh)==12
        healthy=hh.loc[~hh.automatic_bad,'channel_index'].to_numpy(int)-1
        strict=hh.loc[~hh.automatic_bad & ~hh.automatic_suspect,'channel_index'].to_numpy(int)-1
        assert healthy.tolist()==[x-1 for x in json.loads(r.healthy_channel_indices_1based)]
        records.append({'row':r,'meta':m,'archive':archive,'raw':p,'healthy':healthy,'strict':strict,'group':f'{r.dataset}|{r.arrangement}|{r.detector}'})
    for rec in records:
        same=[x for x in records if x['group']==rec['group']]
        rec['common']=np.array(sorted(set.intersection(*(set(x['healthy']) for x in same))),dtype=int)
        rec['strict_common']=np.array(sorted(set.intersection(*(set(x['strict']) for x in same))),dtype=int)
        assert len(rec['strict_common'])>=4
    manifest={'status':'running','raw_root':'D:/Lab/raw/raw','record_count':40,'window_count':96,'window_samples':16384,'band_hz':[80000,199000],'upper_exclusive':True,'configs':CONFIGS,'new_experiments':False,'full_interval_all_samples':False,'classification_input':'RUN and STOP features minus local background features','code_sha256':digest(Path(__file__)),'source_function_sha256':digest(ROOT/'scripts/analyze_mentor_multimethod_identifiability.py'),'versions':{'numpy':np.__version__,'scipy':scipy.__version__,'sklearn':sklearn.__version__,'nptdms':nptdms.__version__},'files':[{'case_id':r['row'].case_id,'raw':str(r['raw']),'size':r['raw'].stat().st_size,'metadata_sha256':digest(r['archive']/'metadata.json')} for r in records]}
    (OUT/'run_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    pd.DataFrame([{'case_id':r['row'].case_id,'group':r['group'],'healthy':json.dumps((r['healthy']+1).tolist()),'common':json.dumps((r['common']+1).tolist()),'strict_common':json.dumps((r['strict_common']+1).tolist())} for r in records]).to_csv(OUT/'channel_sets.csv',index=False)
    return records,manifest
def read_windows(rec):
    selected=rec['healthy'];config=rec['meta'].get('config',{})
    with TdmsFile.open(rec['raw']) as td:
        channels=td.groups()[0].channels();fs=1/float(channels[0].properties['wf_increment']);n=len(channels[0])
        assert n==rec['meta']['sample_count'];assert len(channels)==12
        assert [c.name for c in channels]==rec['meta']['channel_names']
        first=max(0,int(round(float(config.get('trim_start_seconds',0))*fs)))
        last=n-int(round(float(config.get('trim_end_seconds',0))*fs))-16384
        if last<=first:first=0;last=n-16384
        count=min(96,max(8,(last-first)//16384));assert count==96
        starts=np.linspace(first,last,count,dtype=np.int64)
        x=np.empty((96,16384,len(selected)),np.float64)
        for j,c in enumerate(selected):
            for k,start in enumerate(starts):x[k,:,j]=channels[int(c)][int(start):int(start)+16384]
    assert np.isfinite(x).all()
    return x,fs,starts
def curves(spectra):
    """Same reduction order as original, including averaging each 12-window epoch."""
    pairs=list(itertools.combinations(range(spectra.shape[2]),2));epochs=np.array_split(np.arange(96),8)
    result=np.empty((9,len(pairs),spectra.shape[1]),dtype=np.float64)
    for j,(a,b) in enumerate(pairs):
        cross=spectra[:,:,a]*np.conj(spectra[:,:,b]);pa=np.abs(spectra[:,:,a])**2;pb=np.abs(spectra[:,:,b])**2
        for e,idx in enumerate([slice(None)]+epochs):
            avg=np.mean(cross[idx],axis=0);den=np.mean(pa[idx],axis=0)*np.mean(pb[idx],axis=0)
            result[e,j]=np.abs(avg)**2/np.maximum(den,1e-30)
    return result,pairs
def one_record(rec):
    tic=time.monotonic();x,fs,starts=read_windows(rec);rows=[];pair_rows=[]
    freq=fft.rfftfreq(16384,1/fs);mask=(freq>=80000)&(freq<199000)
    for precision in ['legacy32','center64_then32','full64']:
        if precision=='legacy32':
            base=x.astype(np.float32);centered=base-np.mean(base,axis=1,keepdims=True)
        else:
            centered=x-np.mean(x,axis=1,keepdims=True)
            if precision=='center64_then32':centered=centered.astype(np.float32)
        scale=np.std(centered.reshape(-1,centered.shape[-1]),axis=0)
        standardized=centered/np.maximum(scale[None,None,:],1e-12)
        taper=signal.windows.hann(16384,sym=False).astype(centered.dtype)
        spectra=fft.rfft(standardized*taper[None,:,None],axis=1,workers=2)
        spectra=spectra.astype(np.complex128 if precision=='full64' else np.complex64,copy=False)
        spectra=spectra[:,mask,:]
        cc,pairs=curves(spectra)
        rules=['original','common','strict'] if precision=='full64' else ['original']
        for rule in rules:
            allowed=rec['healthy'] if rule=='original' else rec['common'] if rule=='common' else rec['strict_common']
            use=[i for i,(a,b) in enumerate(pairs) if rec['healthy'][a] in allowed and rec['healthy'][b] in allowed]
            # Original curves were float32 in legacy path; preserve its median rounding.
            use_curves=cc[:,use,:].astype(np.float64 if precision=='full64' else np.float32)
            ec=np.median(np.median(use_curves,axis=1),axis=1)
            r={k:rec['row'][k] for k in META};r.update(config=precision+'_'+rule,group=rec['group'],channel_count=len(allowed),pair_count=len(use),pool=float(ec[0]),epoch_median=float(np.median(ec[1:])))
            r.update({f'epoch_{i}':float(v) for i,v in enumerate(ec[1:])});rows.append(r)
            if precision=='full64':
                for j in use:
                    a,b=pairs[j];pair_rows.append({'case_id':rec['row'].case_id,'config':r['config'],'channel_a':int(rec['healthy'][a]+1),'channel_b':int(rec['healthy'][b]+1),'pool':float(np.median(cc[0,j]))})
        del spectra,cc,centered,standardized
    legacy=rows[0];old=rec['row']
    legacy['legacy_pool_error']=legacy['pool']-old[KEYS[0]];legacy['legacy_epoch_error']=legacy['epoch_median']-old[KEYS[1]]
    payload={'rows':rows,'pairs':pair_rows,'starts':starts.tolist(),'sample_rate':fs,'seconds':time.monotonic()-tic}
    (OUT/'checkpoints'/f'{old.case_id}.json').write_text(json.dumps(payload,ensure_ascii=False,default=lambda v:v.item() if isinstance(v,np.generic) else v),encoding='utf8')
    print(f'{old.case_id}: {time.monotonic()-tic:.1f}s legacy_error={legacy["legacy_pool_error"]:.3g} full64_delta={rows[2]["pool"]-legacy["pool"]:.6g}',flush=True)
    return payload
def summarize(records,manifest,permutations):
    payloads=[json.loads((OUT/'checkpoints'/f'{r["row"].case_id}.json').read_text(encoding='utf8')) for r in records]
    f=pd.DataFrame([r for p in payloads for r in p['rows']]);f.to_csv(OUT/'features.csv',index=False)
    pd.DataFrame([r for p in payloads for r in p['pairs']]).to_csv(OUT/'pair_features.csv',index=False)
    checks=f[f.config=='legacy32_original'][['case_id','legacy_pool_error','legacy_epoch_error']]
    checks.to_csv(OUT/'legacy_reproduction.csv',index=False)
    # Original unmodified function also differs from the historical epoch value
    # by 1.218e-6 on the worst case; see canonical_reproduction_diagnostic.json.
    # Preserve that residual explicitly rather than claiming bitwise reproduction.
    assert checks.legacy_pool_error.abs().max()<1e-6,'Pooled historical reproduction mismatch'
    assert checks.legacy_epoch_error.abs().max()<2e-6,'Epoch historical reproduction mismatch'
    contrasts=[];strata=[];summaries=[]
    for (config,group),g in f.groupby(['config','group']):
        stop=g[g.condition=='vfd_stop'].iloc[0];bg=g[g.condition=='background'].iloc[0]
        for _,r in g.iterrows():
            if r.condition in ['background','vfd_stop']:continue
            q={'config':config,'group':group,'case_id':r.case_id,'detector':r.detector}
            for k in ['pool','epoch_median']:q[k+'_stop_diff']=r[k]-stop[k];q[k+'_bg_diff']=r[k]-bg[k]
            contrasts.append(q)
    c=pd.DataFrame(contrasts);c.to_csv(OUT/'matched_contrasts.csv',index=False)
    for (config,group),g in c.groupby(['config','group']):
        strata.append({'config':config,'group':group,'n':len(g),'pool_diff':g.pool_stop_diff.median(),'epoch_diff':g.epoch_median_stop_diff.median()})
    s=pd.DataFrame(strata);s.to_csv(OUT/'strata.csv',index=False)
    for config,g in s.groupby('config'):
        summaries.append({'config':config,'positive_strata':int((g.pool_diff>0).sum()),'median_difference':g.pool_diff.median(),'wilcoxon_p':stats.wilcoxon(g.pool_diff).pvalue,'epoch_positive_strata':int((g.epoch_diff>0).sum()),'epoch_positive_files':int((c[c.config==config].epoch_median_stop_diff>0).sum())})
    pd.DataFrame(summaries).to_csv(OUT/'effect_summary.csv',index=False)
    # Reuse untouched fold pipeline, background-subtracted inputs, and original label mapping.
    oldmat=pd.read_csv(OLD/'identifiability/raw_completion_feature_matrix.csv')
    oldmat=oldmat[oldmat.condition.isin(['run','30hz','50hz','vfd_stop'])].copy();assert len(oldmat)==32
    out=[];predictions=[];stress=[]
    for config in CONFIGS+['spectral_baseline']:
        if config=='spectral_baseline':frame=oldmat[INDEX_COLUMNS+[x for x in oldmat if x.startswith('baseline_spectral|')]].copy()
        else:
            rr=[]
            for _,r in oldmat.iterrows():
                current=f[(f.config==config)&(f.case_id==r.case_id)].iloc[0]
                background=f[(f.config==config)&(f.case_id==r.reference_case_id)].iloc[0]
                q={k:r[k] for k in INDEX_COLUMNS}
                for key,col in zip(KEYS,['pool','epoch_median']):q[f'full_raw|{key}|all']=current[col]-background[col]
                rr.append(q)
            frame=pd.DataFrame(rr)
        frame['condition']=np.where(frame.condition=='vfd_stop','stop','run')
        for detector in ['combined','tc1','tc2']:
            ff=frame.copy() if detector=='combined' else frame[frame.detector==detector].copy()
            task='run_vs_stop'+('' if detector=='combined' else '_'+detector)
            pp=permutations if config in ['legacy32_original','full64_common','spectral_baseline'] else 0
            if pp:
                su,pr,_=evaluate_task(ff,task,'condition',8,pp,'combined')
            else:
                names=np.asarray([x for x in ff if x not in INDEX_COLUMNS]);y=ff.condition.to_numpy();yp,_=grouped_predictions(ff[names].to_numpy(float),y,groups(ff).to_numpy(),names,8)
                cm=confusion_matrix(y,yp,labels=['run','stop'])
                su={'sample_count':len(ff),'group_count':groups(ff).nunique(),'grouped_balanced_accuracy':balanced_accuracy_score(y,yp),'permutation_p':np.nan,'confusion_matrix_rows':';'.join(','.join(map(str,row)) for row in cm)}
                pr=ff[INDEX_COLUMNS].copy();pr['true_label']=y;pr['predicted_label']=yp
            su.update(config=config,detector=detector,permutations=pp);out.append(su);pr['config']=config;pr['model_detector']=detector;predictions.append(pr)
            names=np.asarray([x for x in ff if x not in INDEX_COLUMNS]);y=ff.condition.to_numpy();yp,_=grouped_predictions(ff[names].to_numpy(float),y,ff.dataset.astype(str).to_numpy(),names,8)
            stress.append({'config':config,'detector':detector,'dates':2,'balanced_accuracy':balanced_accuracy_score(y,yp),'confusion':confusion_matrix(y,yp,labels=['run','stop']).tolist()})
            print(f'CV {config}/{detector}: BA={su["grouped_balanced_accuracy"]:.4f} p={su["permutation_p"]}',flush=True)
        pd.DataFrame(out).to_csv(OUT/'classification.csv',index=False)
    pd.concat(predictions).to_csv(OUT/'predictions.csv',index=False);pd.DataFrame(stress).to_csv(OUT/'leave_date_stress.csv',index=False)
    manifest['status']='complete';manifest['legacy_max_abs_error']=checks[['legacy_pool_error','legacy_epoch_error']].abs().to_numpy().max();manifest['classification_permutations']=permutations
    (OUT/'run_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    print('COMPLETE',OUT,flush=True)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int);ap.add_argument('--permutations',type=int,default=499);ap.add_argument('--summary-only',action='store_true');args=ap.parse_args()
    records,manifest=setup()
    with threadpool_limits(limits=1):
        if not args.summary_only:
            for i,r in enumerate(records[:args.limit] if args.limit else records):
                if (OUT/'checkpoints'/f'{r["row"].case_id}.json').exists():continue
                print(f'[{i+1}/{len(records)}] {r["row"].case_id}',flush=True);one_record(r)
        if not args.limit:summarize(records,manifest,args.permutations)
if __name__=='__main__':main()
