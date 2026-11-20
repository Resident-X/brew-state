# KiCad python, READ-ONLY. usage: measure.py NEW.kicad_pcb obst.json out.txt
# Measures every new top-level drawing item (anything that is not Edge.Cuts) and reports the nearest obstacle gap per class.
import pcbnew, json, sys, math
b = pcbnew.LoadBoard(sys.argv[1]); O = json.load(open(sys.argv[2])); mm = pcbnew.ToMM
def gap(a, c):
    dx = max(a[0]-c[2], c[0]-a[2], 0); dy = max(a[1]-c[3], c[1]-a[3], 0); return math.hypot(dx, dy)
EDGE = [("outline-top",(19.9,20.9,65.1,21.0)),("outline-left",(19.9,20.9,20.0,96.1)),("outline-right",(65.0,20.9,65.1,96.1)),("outline-bottom",(19.9,96.0,65.1,96.1)),("slot A",(51.0,49.44,65.0,50.94)),("slot B",(51.0,65.46,65.0,66.96))]
rows = []
for d in b.GetDrawings():
    L = b.GetLayerName(d.GetLayer())
    if L not in ("F.Silkscreen", "F.Fab"): continue
    bb = d.GetBoundingBox(); bx = (mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetRight()), mm(bb.GetBottom()))
    cls = d.GetClass()
    if cls == "PCB_TEXT":
        # KiCad's own text box adds line spacing; the ink box is the glyph height (size) plus the stroke across the line
        sz = mm(d.GetTextHeight()); th = mm(d.GetTextThickness()); h = sz/2 + th/2
        ang = round(d.GetTextAngleDegrees()) % 180
        ink = list(bx)
        if ang == 0: cy = (bx[1]+bx[3])/2; ink[1], ink[3] = cy-h, cy+h
        else: cx = (bx[0]+bx[2])/2; ink[0], ink[2] = cx-h, cx+h
        name = 'text "%s"' % d.GetText(); ink = tuple(ink)
    else:
        name = cls + (" " + d.GetShapeStr() if cls == "PCB_SHAPE" else ""); ink = bx
    rows.append((L, name, bx, ink))
res = []
for i, (L, name, bx, ink) in enumerate(rows):
    g = {}
    def upd(k, v):
        if k not in g or v[0] < g[k][0]: g[k] = v
    if L == "F.Silkscreen":
        for r, n, *c in O["pad"]: upd("mask opening", (gap(ink, c), "%s.%s" % (r, n)))
        for r, n, *c in O["hole"]: upd("hole", (gap(ink, c), "%s.%s" % (r, n)))
        for c in O["via"]: upd("via", (gap(ink, c), ""))
        for r, *c in O["silk"]: upd("existing silk", (gap(ink, c), r))
        for r, *c in O["ref"]: upd("reference text", (gap(ink, c), r))
        for r, *c in O["fab"]: upd("part body (F.Fab)", (gap(ink, c), r))
        for nm, e in EDGE: upd("edge/slot", (gap(ink, e), nm))
        for j, (L2, n2, bx2, ink2) in enumerate(rows):
            if j != i and L2 == "F.Silkscreen": upd("other new silk", (gap(ink, ink2), n2))
    res.append((L, name, bx, ink, g))
with open(sys.argv[3], "w") as f:
    for L, name, bx, ink, g in res:
        f.write("%-12s %-34s kicad box (%.2f,%.2f)-(%.2f,%.2f)  ink/stroke box (%.2f,%.2f)-(%.2f,%.2f)\n" % (L, name, *bx, *ink))
        for k, v in sorted(g.items(), key=lambda kv: kv[1][0])[:99]:
            f.write("      nearest %-18s %.3f mm (%s)\n" % (k, v[0], v[1]))
print(open(sys.argv[3]).read())
