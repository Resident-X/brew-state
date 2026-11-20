import numpy as np, os, sys
from PIL import Image, ImageFilter
SRC = sys.argv[1]
OUT = sys.argv[2]
W = int(sys.argv[3]) if len(sys.argv) > 3 else 2400
os.makedirs(OUT, exist_ok=True)
BG = np.array([246, 245, 241], float)
LAYERS = {
    'F.Cu': (198, 58, 57), 'In1.Cu': (221, 157, 51), 'In2.Cu': (64, 163, 106), 'In3.Cu': (136, 91, 198),
    'In4.Cu': (43, 175, 175), 'B.Cu': (51, 107, 187), 'Edge.Cuts': (181, 146, 23), 'F.SilkS': None,
}

def silk_colour(a):
    # darkest common colour
    flat = a.reshape(-1, 3)
    d = np.linalg.norm(flat - BG, axis=1)
    sel = flat[d > np.percentile(d, 99.5)]
    return sel.mean(axis=0)

# crop box from Edge.Cuts
edge = np.asarray(Image.open(f'{SRC}/layer-Edge.Cuts.jpg').convert('RGB'), float)
dist = np.linalg.norm(edge - BG, axis=2)
ys, xs = np.where(dist > 60)
m = 12
box = (xs.min() - m, ys.min() - m, xs.max() + m, ys.max() + m)
print('box', box)
for name, col in LAYERS.items():
    a = np.asarray(Image.open(f'{SRC}/layer-{name}.jpg').convert('RGB'), float)
    if col is None:
        col = silk_colour(a)
        print('silk colour', col)
    d = BG - np.array(col, float)
    v = BG - a
    t = (v @ d) / (d @ d)
    resid = np.linalg.norm(v - t[..., None] * d, axis=2)
    alpha = np.clip(t, 0, 1) * np.clip(1 - (resid - 6) / 18, 0, 1)
    al = Image.fromarray((alpha * 255).round().astype(np.uint8), 'L')
    if name in ('Edge.Cuts',):
        al = al.filter(ImageFilter.MaxFilter(5))
    al = al.crop(box)
    h = round(W * al.size[1] / al.size[0])
    al = al.resize((W, h), Image.LANCZOS)
    q = np.asarray(al, float) / 255
    q = np.where(q < 0.12, 0, np.where(q > 0.88, 1, np.round(q * 6) / 6))
    al = Image.fromarray((q * 255).round().astype(np.uint8), "L")
    rgba = Image.merge('RGBA', [Image.new('L', al.size, 0)] * 3 + [al])
    p = f'{OUT}/{name}.webp'
    rgba.save(p, lossless=True, method=6)
    print(name, al.size, os.path.getsize(p))
