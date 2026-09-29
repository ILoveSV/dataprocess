"""Conservative centerline/capsule clearance audit for declared copper routing."""
import numpy as np
import pandas as pd
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/thesis_followup_20260915/external'
def distance(p,q,r,s):
 p,q,r,s=map(lambda x:np.array(x,float),(p,q,r,s));u=q-p;v=s-r;w=p-r
 candidates=[]
 for a in [0.,1.]:
  b=np.clip(np.dot(v,w+a*u)/np.dot(v,v),0,1);candidates.append((a,b))
 for b in [0.,1.]:
  a=np.clip(np.dot(u,b*v-w)/np.dot(u,u),0,1);candidates.append((a,b))
 a,b=np.linalg.lstsq(np.column_stack([u,-v]),-w,rcond=None)[0]
 if 0<=a<=1 and 0<=b<=1:candidates.append((a,b))
 return min(np.linalg.norm(w+a*u-b*v) for a,b in candidates)
rows=[]
for gap in [10,20,50,100,200,300]:
 xn=.055-(gap/1000+.0625)/2;xp=.055+(gap/1000+.0625)/2
 for label,zp in [('legacy_equal_height',.9),('declared_split_height',.92)]:
  neg=[((.92,-.303,.3),(0,-.033,.9)),((0,-.033,.9),(xn,0,.9)),((xn,0,.852),(xn,0,.9))]
  pos=[((.92,-.297,.3),(0,-.027,zp)),((0,-.027,zp),(xp,0,zp)),((xp,0,.852),(xp,0,zp))]
  for i,n in enumerate(neg):
   for j,p in enumerate(pos):
    d=distance(*n,*p)
    rows.append(dict(gap_mm=gap,routing=label,neg_part=i,pos_part=j,centerline_distance_mm=d*1000,capsule_clearance_mm=d*1000-3))
d=pd.DataFrame(rows);d.to_csv(OUT/'routing_clearance.csv',index=False,encoding='utf-8-sig')
new=d[d.routing.eq('declared_split_height')]
assert new.capsule_clearance_mm.min()>0
print(d.groupby(['routing','gap_mm']).capsule_clearance_mm.min().to_string())
