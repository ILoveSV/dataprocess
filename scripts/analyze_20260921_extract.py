"""Read-only full-record extraction for September 21 switching experiments."""
from pathlib import Path
import sys,json,time
import numpy as np
from scipy import fft,signal
from nptdms import TdmsFile
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT / 'experiments/20260921_switching'; (OUT/'cache').mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'scripts'))
from channel_quality import assess_channel_quality
BANDS={'line30':(28,32),'line50':(48,52),'line100':(98,102),'low5_100':(5,100),'b100_1k':(100,1000),'b1_20k':(1000,20000),'b20_80k':(20000,80000),'b80_200k':(80000,199900),'carrier4k':(3950,4050),'carrier8k':(7950,8050),'carrier12k':(11950,12050),'near100k':(99000,101000)}
for folder in ['111','222']:
 for ri,path in enumerate(sorted((Path('E:/Lab/raw/9.21')/folder).glob('*.tdms')),1):
  cid=f'g{folder}_r{ri}'; target=OUT/'cache'/f'{cid}.npz'
  if target.exists(): print('CACHED',cid,flush=True);continue
  started=time.time(); print('START',cid,str(path),flush=True)
  with TdmsFile.open(path) as td:
   group=td.groups()[0];chs=group.channels();names=[c.name for c in chs];C=len(chs);fs=round(1/chs[0].properties['wf_increment']);n=min(map(len,chs))
   buf=np.empty((C,fs),dtype=np.float64);pos=0;secs=0;slow=[];rms=[];subrms=[];fast=[];diff=[];bp=[];spectra=[];low=[];seen=0;flat=np.zeros(C);ndiff=0;nonfinite=np.zeros(C);clipped=np.zeros(C);mins=np.full(C,np.inf);maxs=np.full(C,-np.inf)
   f=fft.rfftfreq(fs,1/fs);win=signal.windows.hann(fs,sym=False);norm=fs*np.sum(win*win);masks={k:(f>=lo)&(f<hi) for k,(lo,hi) in BANDS.items()};last=np.full(C,np.nan)
   def consume(x,spectral=True):
    global ndiff,last,flat,nonfinite,clipped,mins,maxs
    nonfinite+=np.sum(~np.isfinite(x),axis=1);clipped+=np.sum(np.abs(x)>=9.9,axis=1);mins=np.minimum(mins,np.nanmin(x,axis=1));maxs=np.maximum(maxs,np.nanmax(x,axis=1))
    dx=np.diff(x,axis=1);flat+=np.sum(np.abs(dx)<=1e-12,axis=1);ndiff+=dx.shape[1]
    bs=fs//10;use=x.shape[1]//bs*bs
    if use:
     block=x[:,:use].reshape(C,-1,bs);sm=block.mean(axis=2);slow.extend(sm.T);rms.extend(block.std(axis=2).T);subs=block.reshape(C,-1,100,fs//1000);means=subs.mean(axis=3);sr=means.std(axis=2);subrms.extend(sr.T);fast.extend(np.sqrt(np.maximum(block.var(axis=2)-sr**2,0)).T);diff.extend(np.sqrt(np.mean(np.diff(block,axis=2)**2,axis=2)/2).T);low.extend(means.reshape(C,-1).T)
    if spectral:
     z=fft.rfft((x-x.mean(axis=1,keepdims=True))*win,axis=1,workers=2);ps=np.abs(z)**2/norm;ps[:,1:-1]*=2
     bp.append(np.stack([ps[:,mask].sum(axis=1) for mask in masks.values()],axis=1))
     coarse=ps[:,:200000].reshape(C,2000,100).mean(axis=2);spectra.append(coarse)
   for chunk in td.data_chunks():
    cc=chunk[group.name].channels()
    if len(cc)!=C: raise ValueError('channel chunk count mismatch')
    arr=np.stack([np.asarray(c[:],dtype=np.float64) for c in cc]);offsets=[int(c.offset) for c in cc]
    if len(set(offsets))!=1 or offsets[0]!=seen: raise ValueError(('discontinuity',offsets,seen))
    seen+=arr.shape[1];at=0
    while at<arr.shape[1]:
     take=min(fs-pos,arr.shape[1]-at);buf[:,pos:pos+take]=arr[:,at:at+take];pos+=take;at+=take
     if pos==fs:
      consume(buf);pos=0;secs+=1
      if secs%30==0:print(cid,'seconds',secs,'elapsed',round(time.time()-started,1),flush=True)
   if pos:consume(buf[:,:pos],False)
   slow=np.array(slow);rms=np.array(rms);diff=np.array(diff)
   health=[{'mean':float(slow[:,c].mean()),'std':float(np.sqrt(np.mean(rms[:,c]**2)+np.var(slow[:,c]))),'range':float(maxs[c]-mins[c]),'difference_rms':float(np.sqrt(np.mean(diff[:,c]**2))),'nonfinite_fraction':float(nonfinite[c]/seen),'clip_fraction':float(clipped[c]/seen),'flat_difference_fraction':float(flat[c]/max(ndiff,1))} for c in range(C)]
   quality=assess_channel_quality({'channel_names':names,'health':health})
   meta={'case_id':cid,'folder':folder,'repeat':ri,'source':str(path),'source_bytes':path.stat().st_size,'source_mtime_ns':path.stat().st_mtime_ns,'fs':fs,'sample_counts':[len(c) for c in chs],'samples_read':seen,'duration_s':n/fs,'tail_without_spectrum_s':pos/fs,'channel_names':names,'channel_properties':[dict(c.properties) for c in chs],'health':health,'quality':quality,'spectral_method':'full raw 1s Hann periodogram, 1Hz bins; plot PSD coarsened to 100Hz bins','slow_method':'nonoverlapping 0.1s block means, RMS, 1ms block-mean spread and residual','bands':BANDS}
   np.savez_compressed(target,slow_mean=slow,broadband_rms=rms,subkhz_rms=np.array(subrms),fast_residual_rms=np.array(fast),difference_rms=diff,bandpower=np.array(bp),psd100=np.array(spectra),low1k=np.array(low),meta=json.dumps(meta,default=str))
   print('DONE',cid,'seconds',n/fs,'healthy',sum(not q['automatic_bad'] for q in quality),'elapsed',round(time.time()-started,1),flush=True)
print('EXTRACTION COMPLETE',flush=True)
