from pathlib import Path
import sys
import numpy as np,joblib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.health_fusion_recognizer import infer,save_candidate,OUT,cache_blocks

def inputs():
 with np.load(ROOT / 'experiments/20260921_switching/cache/g111_r3.npz') as z:c={k:z[k] for k in z.files if k!='meta'}
 return [{k:v.copy() for k,v in b.items()} for b in cache_blocks(c)],joblib.load(OUT/'g111_r3_heldout.joblib')

def test_channel_failure_and_recovery_are_causal():
 blocks,m=inputs();before,_=infer(blocks,m)
 for b in blocks[40:45]:b['slow_mean'][:,7]=np.nan
 after,h=infer(blocks,m)
 np.testing.assert_array_equal(before.confirmed_binary.iloc[:40],after.confirmed_binary.iloc[:40]);np.testing.assert_allclose(before.prob_on.iloc[20:40],after.prob_on.iloc[20:40])
 ch=h[h.channel==8].set_index('time_end_s');assert not ch.loc[41:47,'usable'].any();assert ch.loc[48,'usable'];assert (ch.loc[41:45,'health']=='nonfinite').all();assert (ch.loc[46:47,'health']=='recovering_3s').all()
 assert not h[(h.channel==8)&h.time_end_s.between(41,47)].selected.any()
 save_candidate(after,h,OUT/'test_nan_chip8',{'source':'人工注入：第8路40–45秒无效值；不是新实验','mode':'synthetic fault test on existing real features'})

def test_flat_all_channels_outputs_unknown_and_reacquires():
 blocks,m=inputs()
 for b in blocks[70:74]:b['broadband_rms'][:]=0
 d,h=infer(blocks,m);assert (d.set_index('time_end_s').loc[71:76,'confirmed_binary']=='unknown').all();assert (d.set_index('time_end_s').loc[71:76,'decision']=='unknown').all();assert np.isnan(d.set_index('time_end_s').loc[71,'prob_on']);assert (d.event_type=='state_reacquired').any()
 save_candidate(d,h,OUT/'test_all_flat',{'source':'人工注入：全部通道70–74秒卡死；不是新实验','mode':'synthetic fault test on existing real features'})

def test_raw_nonfinite_opt_in_preserves_default(monkeypatch):
 # Small mocked TDMS stream isolates the changed reader contract; the older test
 # separately checks the real TDMS format and full stream arithmetic.
 import scripts.state_recognizer as reader
 class Channel:
  properties={'wf_increment':1/400000,'unit_string':'Volts'}
  offset=0
  def __init__(self,j):self.name=str(j);self.j=j
  def __len__(self):return 21*400000
  def __getitem__(self,key):
   x=np.ones(400000)
   if self.j==7:x[0]=np.nan
   return x[key]
 class Group:
  name='group'
  def channels(self):return [Channel(j) for j in range(12)]
 class Fake:
  def __enter__(self):return self
  def __exit__(self,*args):pass
  def groups(self):return [Group()]
  def data_chunks(self):yield {'group':Group()}
 monkeypatch.setattr(reader.TdmsFile,'open',lambda path:Fake())
 try:next(reader.raw_blocks('unused',{}))
 except ValueError as exc:assert 'Nonfinite' in str(exc)
 else:raise AssertionError('Old reader default must reject nonfinite samples')
 b=next(reader.raw_blocks('unused',{},allow_nonfinite=True));assert np.isnan(b['slow_mean'][:,7]).any();assert np.isfinite(b['slow_mean'][:,0]).all()
