from pathlib import Path
import json
from nptdms import TdmsFile
root=Path('E:/Lab/raw/9.21'); rows=[]
for f in sorted(root.rglob('*.tdms')):
 t=TdmsFile.read_metadata(f); cs=[c for g in t.groups() for c in g.channels()]
 r={'path':str(f),'bytes':f.stat().st_size,'channels':[{'group':g.name,'name':c.name,'n':len(c),'props':dict(c.properties)} for g in t.groups() for c in g.channels()]}
 rows.append(r); print(f.parent.name,f.name,'channels',len(cs),'n',len(cs[0]),'properties',cs[0].properties,flush=True)
Path('experiments/20260921_switching/inventory.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2,default=str),encoding='utf8')
