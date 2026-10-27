"""Analyze alpha gutters and write source rectangles; never alters raster assets."""
import json
from pathlib import Path
from PIL import Image
root=Path(__file__).resolve().parents[1]/'frontend/public/assets/characters/pixel/v2'
path=root/'manifest.json'
manifest=json.loads(path.read_text())
registered={}
for name in manifest['characters']:
    image=Image.open(root/(name+'.png')).convert('RGBA')
    w,h=image.size
    alpha=image.getchannel('A')
    rows=[]
    for y in range(h):
        rows.append(sum(1 for v in alpha.crop((0,y,w,y+1)).getdata() if v>160))
    boundaries=[0]
    for r in range(1,6):
        target=r*h/6
        lo,hi=round(target-h/6*.22),round(target+h/6*.22)
        boundaries.append(min(range(lo,hi),key=lambda y:(rows[y],abs(y-target))))
    boundaries.append(h)
    columns=[0]
    counts=[sum(1 for v in alpha.crop((x,0,x+1,h)).getdata() if v>160) for x in range(w)]
    for c in range(1,8):
        target=c*w/8
        lo,hi=round(target-w/8*.22),round(target+w/8*.22)
        columns.append(min(range(lo,hi),key=lambda x:(counts[x],abs(x-target))))
    columns.append(w)
    frames=[]
    for r in range(6):
        for c in range(8):
            x0,x1=columns[c],columns[c+1]
            frames.append(dict(x=x0,y=boundaries[r],width=x1-x0,height=boundaries[r+1]-boundaries[r]))
    registered[name]=frames
    print(name,image.size,boundaries,columns)
manifest['frames']=registered
path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
