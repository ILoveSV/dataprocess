"""Real-feature regression, causality and raw TDMS reader contract tests."""
import sys,json,tempfile
from pathlib import Path
import numpy as np,pandas as pd
from nptdms import TdmsWriter,ChannelObject
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.state_recognizer import Baseline,raw_blocks,cache_blocks,matrix,Decisions,OUT

def test_real_feature_predictions_match_previous_analysis():
 old=pd.read_csv(ROOT/'results/20260921_switching/exploratory_clipped_predictions.csv')
 for path in (ROOT/'results/20260921_switching/cache').glob('*.npz'):
  cid=path.stem;new=pd.read_csv(OUT/cid/'predictions.csv');expected=old[(old.case_id==cid)&(old.method=='clipped_binary')].sort_values('time_end_s')
  assert list(new.raw_binary.iloc[20:])==list(expected.prediction.iloc[20:])

def test_baseline_future_causality_and_rejection():
 with np.load(ROOT/'results/20260921_switching/cache/g111_r1.npz') as z:c={k:z[k] for k in z.files if k!='meta'}
 blocks=list(cache_blocks(c));b=Baseline(blocks[:20]);before=b.transform(blocks[20]);blocks[30]['slow_mean'][:]=1e6
 np.testing.assert_array_equal(before,b.transform(blocks[20]))
 broken=[{k:v.copy() for k,v in x.items()} for x in blocks[:20]]
 for x in broken:x['broadband_rms'][:,0]=0
 try:Baseline(broken)
 except ValueError:pass
 else:raise AssertionError('Flat baseline channel must be rejected')

def test_raw_tdms_stream_values_and_tail():
 # Synthetic input verifies interfaces and arithmetic ONLY, not research accuracy.
 fs=400000;names=['ch'+str(i) for i in range(12)];t=np.arange(fs)/fs
 expected=None
 with tempfile.TemporaryDirectory(prefix='recognizer_test_') as td:
  path=Path(td)/'synthetic.tdms'
  with TdmsWriter(path) as writer:
   for sec in range(21):
    x=np.stack([(1+j*.02+.01*np.sin(2*np.pi*(30+j)*t)).astype('float32') for j in range(12)])
    if sec==20:expected=x.astype(float)
    writer.write_segment([ChannelObject('data',n,x[j],properties={'wf_increment':1/fs,'unit_string':'Volts'}) for j,n in enumerate(names)])
  meta={};count=0
  for block in raw_blocks(path,meta):count+=1;last=block
  assert count==21 and meta['samples_read']==21*fs
  independent=expected.reshape(12,10,40000)
  np.testing.assert_allclose(last['slow_mean'],independent.mean(axis=2).T,atol=1e-12)
  np.testing.assert_allclose(last['broadband_rms'],independent.std(axis=2).T,atol=1e-12)
  # A 30 Hz sine has variance A²/2, all captured by the 28..32 Hz Hann main lobe.
  np.testing.assert_allclose(last['bandpower'][0,0],.01**2/2,rtol=1e-5)
