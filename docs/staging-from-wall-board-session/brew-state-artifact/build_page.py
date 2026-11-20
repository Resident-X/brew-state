import re,base64,hashlib,sys
src,dst=sys.argv[1:3]
s=open(src,encoding='utf-8').read()
uris=list(re.finditer(r'data:image/webp;base64,([A-Za-z0-9+/=]+)',s))
assert len(uris)==13
names=['RT','RB','L1 F.Cu','L2 In1.Cu','L3 In2.Cu','L4 In3.Cu','L5 In4.Cu','L6 B.Cu','LE Edge.Cuts','LS F.SilkS','LB B.SilkS','logo','hero']
new={0:'render_top.webp',1:'render_bottom.webp',2:'masks/F.Cu.webp',7:'masks/B.Cu.webp',9:'masks/F.SilkS.webp',12:'hero.webp'}
out=[];last=0
for i,m in enumerate(uris):
    out.append(s[last:m.start(1)])
    out.append(base64.b64encode(open(new[i],'rb').read()).decode() if i in new else m.group(1))
    last=m.end(1)
out.append(s[last:]); t=''.join(out)
open(dst,'w',encoding='utf-8').write(t)
u2=list(re.finditer(r'data:image/webp;base64,([A-Za-z0-9+/=]+)',t))
h=lambda x:hashlib.sha256(x.encode()).hexdigest()[:16]
print(f"{'image':14} {'before':16} {'after':16} status")
for i,(a,b) in enumerate(zip(uris,u2)):
    print(f"{names[i]:14} {h(a.group(1))} {h(b.group(1))} {'CHANGED' if a.group(1)!=b.group(1) else 'identical'}")
strip=lambda x:re.sub(r'data:image/webp;base64,[A-Za-z0-9+/=]+','URI',x)
print('non-URI text identical:', strip(s)==strip(t), 'size', len(t.encode()))
