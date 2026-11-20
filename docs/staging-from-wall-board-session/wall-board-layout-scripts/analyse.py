"""Geometry census of a heater wall board file (KiCad python).

usage: analyse.py BOARD.kicad_pcb
Prints, per copper zone: outline vertices with interior angles (flags < 90 deg), filled polygon count (islands),
acute corners of the fill (straight segments >= 0.1 mm both sides), neck test by erosion (does the fill split
when eroded by w/2 for w in a ladder), distance of the fill to the board edge; silk text ink boxes and whether
each straddles a copper edge on its face; silk stroke and text size census.
"""
import math, sys
import pcbnew

mm = pcbnew.ToMM
M = pcbnew.FromMM
b = pcbnew.LoadBoard(sys.argv[1])
L = b.GetLayerName


def ang(p0, p1, p2):
    """interior angle at p1 of a polygon traversed p0->p1->p2, assuming orientation sign s"""
    ax, ay = p0[0] - p1[0], p0[1] - p1[1]
    bx, by = p2[0] - p1[0], p2[1] - p1[1]
    a = math.degrees(math.atan2(ay, ax) - math.atan2(by, bx)) % 360.0
    return a


def area(pts):
    return 0.5 * sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))


def chain_pts(ch):
    return [(mm(ch.CPoint(i).x), mm(ch.CPoint(i).y)) for i in range(ch.PointCount())]


def angles(pts):
    s = 1 if area(pts) > 0 else -1
    out = []
    n = len(pts)
    for i in range(n):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]
        a = ang(p0, p1, p2)
        if s < 0:
            a = 360 - a
        # with y down, KiCad orientation: compute both and pick consistent by sum check below
        out.append(a)
    tot = sum(out)
    exp = (n - 2) * 180
    if abs(tot - exp) > 1:
        out = [360 - a for a in out]
    return out


edge = b.GetBoardEdgesBoundingBox()
outline = pcbnew.SHAPE_POLY_SET()
b.GetBoardPolygonOutlines(outline, True)
edge_chain = outline.Outline(0)


def dist_to_edge(poly):
    best = 1e9
    for c in range(poly.OutlineCount()):
        ch = poly.Outline(c)
        for i in range(ch.PointCount()):
            p = ch.CPoint(i)
            d = edge_chain.SquaredDistance(p)
            best = min(best, math.sqrt(d))
    return mm(int(best))


print("== ZONE OUTLINES (acute < 90 flagged)")
for z in b.Zones():
    if z.GetIsRuleArea():
        continue
    o = z.Outline()
    pts = chain_pts(o.Outline(0))
    a = angles(pts)
    print("ZONE", z.GetZoneName(), L(z.GetLayer()), "n", len(pts))
    for p, x in zip(pts, a):
        tag = "  <-- ACUTE" if x < 89.9 else ("  reflex" if x > 180.1 else "")
        if x < 89.9 or (abs(x - 180) > 0.1 and not (len(pts) > 40 and 170 < x < 190)):
            print("   v (%.4f, %.4f) %.1f%s" % (p[0], p[1], x, tag))

print("== ZONE FILLS")
for z in b.Zones():
    if z.GetIsRuleArea():
        continue
    for lay in z.GetLayerSet().Seq():
        fp = z.GetFilledPolysList(lay)
        n = fp.OutlineCount()
        tot = fp.Area() / 1e12
        print("FILL", z.GetZoneName(), L(lay), "islands", n, "area_mm2 %.2f" % tot, "edge_dist %.3f" % dist_to_edge(fp))
        for c in range(n):
            pts = chain_pts(fp.Outline(c))
            a = angles(pts)
            m = len(pts)
            for i in range(m):
                if a[i] < 89.0:
                    l1 = math.dist(pts[i - 1], pts[i]); l2 = math.dist(pts[i], pts[(i + 1) % m])
                    if l1 >= 0.1 and l2 >= 0.1:
                        print("   acute fill corner (%.3f, %.3f) %.1f deg, sides %.2f %.2f" % (pts[i][0], pts[i][1], a[i], l1, l2))
            print("   island %d bbox (%.2f,%.2f)-(%.2f,%.2f) holes %d" % (c, min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts), fp.HoleCount(c)))
        # neck ladder: erode by w/2, count outlines
        res = []
        for w in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0):
            e = pcbnew.SHAPE_POLY_SET(fp)
            e.Deflate(M(w / 2), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, M(0.005))
            res.append("%g:%d" % (w, e.OutlineCount()))
        print("   erosion ladder (width:parts)", " ".join(res))

print("== TRACKS")
for t in b.GetTracks():
    if t.GetClass() == "PCB_TRACK":
        s, e = t.GetStart(), t.GetEnd()
        dx, dy = mm(e.x - s.x), mm(e.y - s.y)
        a = math.degrees(math.atan2(dy, dx)) % 180
        print("TRK %-40s %s w %.2f len %.3f angle %.1f" % (t.GetNetname(), L(t.GetLayer()), mm(t.GetWidth()), math.hypot(dx, dy), a))

print("== SILK TEXT (ink boxes) and copper under them")
fills = {}
for lay in (pcbnew.F_Cu, pcbnew.B_Cu):
    u = pcbnew.SHAPE_POLY_SET()
    for z in b.Zones():
        if not z.GetIsRuleArea() and z.IsOnLayer(lay):
            u.BooleanAdd(z.GetFilledPolysList(lay))
    for t in b.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t.GetLayer() == lay:
            t.TransformShapeToPolygon(u, lay, 0, M(0.005), pcbnew.ERROR_INSIDE)
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.IsOnLayer(lay):
                p.TransformShapeToPolygon(u, lay, 0, M(0.005), pcbnew.ERROR_INSIDE)
    u.Simplify()
    fills[lay] = u


def texts():
    for d in b.GetDrawings():
        if d.GetClass() == "PCB_TEXT":
            yield "board", d
    for f in b.GetFootprints():
        for t in [f.Reference(), f.Value()] + list(f.GraphicalItems()) + list(f.GetFields()):
            if t.GetClass() in ("PCB_TEXT", "PCB_FIELD"):
                yield f.GetReference(), t


seen = set()
for owner, t in texts():
    key = (owner, t.GetLayer(), t.GetText(), t.GetPosition().x, t.GetPosition().y)
    if key in seen:
        continue
    seen.add(key)
    ln = L(t.GetLayer())
    if "Silk" not in ln or not t.IsVisible():
        continue
    bb = t.GetEffectiveTextShape().BBox() if hasattr(t, "GetEffectiveTextShape") else t.GetBoundingBox()
    x0, y0, x1, y1 = mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())
    th = mm(t.GetEffectiveTextPenWidth())
    x0 -= th / 2; y0 -= th / 2; x1 += th / 2; y1 += th / 2
    box = pcbnew.SHAPE_POLY_SET()
    box.NewOutline()
    for px, py in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        box.Append(M(px), M(py))
    lay = pcbnew.F_Cu if ln.startswith("F") else pcbnew.B_Cu
    inter = pcbnew.SHAPE_POLY_SET(box)
    inter.BooleanIntersection(fills[lay])
    frac = inter.Area() / max(box.Area(), 1)
    tag = "on copper" if frac > 0.98 else ("CROSSES COPPER EDGE (%.0f%% on copper)" % (frac * 100) if frac > 0.02 else "on laminate")
    print("TEXT %-6s %-14s %-22r at (%.3f,%.3f) h %.2f th %.2f ink (%.2f,%.2f)-(%.2f,%.2f) %s" % (
        owner, ln, t.GetShownText(True), mm(t.GetPosition().x), mm(t.GetPosition().y), mm(t.GetTextHeight()), th, x0, y0, x1, y1, tag))
