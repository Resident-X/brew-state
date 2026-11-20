# Same steps as the original: crop the 3200x2200 render to its alpha bbox + 30 px, resize to 1600 wide (LANCZOS), webp q80 alpha80 m6.
import sys,os
from PIL import Image
src,crop,out=sys.argv[1:4]
im=Image.open(src); b=im.getbbox(); m=30
c=im.crop((b[0]-m,b[1]-m,b[2]+m,b[3]+m)); print('bbox',b,'crop',c.size); c.save(crop)
w=1600; r=c.resize((w,round(w*c.size[1]/c.size[0])),Image.LANCZOS); print(r.size)
r.save(out,quality=80,alpha_quality=80,method=6); print(os.path.getsize(out))
