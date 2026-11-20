"""Silk-over-copper census (KiCad python). usage: silk_copper.py BOARD [MARGIN_MM=0.3]
For every visible F.SilkS / B.SilkS text and graphic (board-level and inside footprints) take its printed shape
(strokes as outlines) and judge it against the copper of ITS OWN face (front silk vs F.Cu: zone fills, tracks,
pads, vias): OK-LAMINATE when the shape grown by MARGIN touches no copper, OK-ON-COPPER when the shape grown by
MARGIN lies wholly inside one copper feature (one connected piece of copper), else FLAG with its copper overlap and
the nearest copper edge. The same judgement against the OTHER face's copper is printed as information only.
"""
import sys, math
import pcbnew
mm = pcbnew.ToMM; M = pcbnew.FromMM
b = pcbnew.LoadBoard(sys.argv[1])
MARG = float(sys.argv[2]) if len(sys.argv) > 2 else 0.3
L = b.GetLayerName


def copper(lay):
    u = pcbnew.SHAPE_POLY_SET()
    for z in b.Zones():
        if not z.GetIsRuleArea() and z.IsOnLayer(lay):
            u.BooleanAdd(z.GetFilledPolysList(lay))
    for t in b.GetTracks():
        if t.IsOnLayer(lay):
            t.TransformShapeToPolygon(u, lay, 0, M(0.002), pcbnew.ERROR_INSIDE)
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.IsOnLayer(lay) and p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                p.TransformShapeToPolygon(u, lay, 0, M(0.002), pcbnew.ERROR_INSIDE)
    u.Simplify()
    return u


CU = {pcbnew.F_Cu: copper(pcbnew.F_Cu), pcbnew.B_Cu: copper(pcbnew.B_Cu)}


def shape_of(item, lay):
    ps = pcbnew.SHAPE_POLY_SET()
    item.TransformShapeToPolygon(ps, lay, 0, M(0.002), pcbnew.ERROR_INSIDE)
    ps.Simplify()
    return ps


def judge(P, C):
    G = pcbnew.SHAPE_POLY_SET(P)
    G.Inflate(M(MARG), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, M(0.002))
    inter = pcbnew.SHAPE_POLY_SET(G); inter.BooleanIntersection(C)
    if inter.Area() <= 0:
        return "OK-LAMINATE", 0.0
    out = pcbnew.SHAPE_POLY_SET(G); out.BooleanSubtract(C)
    if out.Area() <= 1e3:  # (nm^2) grown shape wholly inside copper
        # wholly inside one connected piece?
        for c in range(C.OutlineCount()):
            one = pcbnew.SHAPE_POLY_SET(); one.AddOutline(C.Outline(c))
            for h in range(C.HoleCount(c)):
                one.AddHole(C.Hole(c, h))
            o2 = pcbnew.SHAPE_POLY_SET(G); o2.BooleanSubtract(one)
            if o2.Area() <= 1e3:
                return "OK-ON-COPPER", 1.0
        return "FLAG(on two copper pieces)", 1.0
    i2 = pcbnew.SHAPE_POLY_SET(P); i2.BooleanIntersection(C)
    return "FLAG", i2.Area() / max(P.Area(), 1)


rows = []
def visit(owner, item):
    ln = L(item.GetLayer())
    if ln not in ("F.Silkscreen", "B.Silkscreen"):
        return
    if item.GetClass() in ("PCB_TEXT", "PCB_FIELD") and not item.IsVisible():
        return
    lay = pcbnew.F_Cu if ln.startswith("F") else pcbnew.B_Cu
    other = pcbnew.B_Cu if lay == pcbnew.F_Cu else pcbnew.F_Cu
    P = shape_of(item, item.GetLayer())
    if P.Area() <= 0:
        return
    bb = P.BBox()
    what = repr(item.GetShownText(True)) if item.GetClass() in ("PCB_TEXT", "PCB_FIELD") else item.GetShapeStr()
    v, frac = judge(P, CU[lay])
    i0 = pcbnew.SHAPE_POLY_SET(P); i0.BooleanIntersection(CU[lay])
    f0 = i0.Area() / max(P.Area(), 1)
    if v.startswith("FLAG"):
        v = "CROSSES-EDGE" if 1e-6 < f0 < 1 - 1e-6 else ("NEAR-EDGE(on copper)" if f0 >= 1 - 1e-6 else "NEAR-COPPER(laminate)")
    vo, _ = judge(P, CU[other])
    rows.append((v, owner, ln, what, (mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())), frac, vo))


for d in b.GetDrawings():
    visit("board", d)
for f in b.GetFootprints():
    for x in list(f.GetFields()) + list(f.GraphicalItems()):
        visit(f.GetReference(), x)
nflag = 0
for r in sorted(rows, key=lambda r: (r[0], r[1])):
    if not r[0].startswith("OK"):
        nflag += 1
    print("%-26s %-6s %-13s %-22s box (%.2f,%.2f)-(%.2f,%.2f) on-copper %3.0f%%   [other face: %s]" % (
        r[0], r[1], r[2][:13], r[3][:22], r[4][0], r[4][1], r[4][2], r[4][3], r[5] * 100, r[6]))
import collections
print("SUMMARY silk objects %d, not OK against own-face copper (margin %.2f mm): %d; by class %s" % (len(rows), MARG, nflag, sorted(collections.Counter(r[0] for r in rows).items())))
