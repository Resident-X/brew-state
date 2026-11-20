#!/usr/bin/env python3
"""Round 7 changes on the heater wall board, re-runnable from HEAD 9e6bb8ee's board file.

usage: edit_r7.py HEAD.kicad_pcb OUT.kicad_pcb [--work DIR] [--keep-blade-bottom]
(HEAD's .kicad_pro and .kicad_dru must sit beside it with the same stem)

Text edits only (every other line of the file is kept as it is):
 7.2  OUT_C_F0: the band's right edge becomes ONE straight line at x 57.95, the pin-2 neck's own edge, from the
      neck to the end of U911 pin 6's finger (removes the 0.45 mm chamfer at y 25.4 and the 0.3 mm step at y 35.9);
      the band keeps its 5.0 mm width by moving its left edge from x 53.4 to x 52.95, and the funnel under the pin
      keeps its width by starting the 45-degree left chamfer at the neck (56.45, 24.97) instead of (56.45, 25.4)
      (the fill stays 1.5 mm off T911 pin 1 by the zone's own clearance, as at the waist today).
 7.1  silk: every legend and reference wholly on bare laminate or wholly on one front copper feature with 0.3 mm
      margin:
      - blade legends read upward (90 degrees) in pairs along their strip, heading left, tag right: RET / RETURN
        on the RET strip, OUT_S / STEAM on the OUT_S strip; OUT_C / COFFEE on bare laminate beside J911's strip
        (that strip is 4.35 mm long above the blade, shorter than the words);
      - RV921's reference reads upward in the bare gap between the RET and OUT_S strips, above its body;
      - the maker block (logo and its two lines) moves 0.5 mm right, off J911's copper edge;
      - footprint outlines are left as their library draws them (--clip-outlines would cut them at copper edges,
        but the pre-order check refuses a placed footprint that differs from its library copy); clip.json in the
        work folder still lists where each outline crosses a copper edge.
Zones whose outline changed are refilled headless in KiCad and only their fills are transplanted back; every other
zone's refill is compared with the committed fill and must be identical.
"""
import argparse, json, math, os, re, shutil, subprocess, sys, uuid as uuidlib

KPY = "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3"
HERE = os.path.abspath(__file__)
MARG = 0.3


def block_end(t, i):
    d = 0
    j = i
    while True:
        c = t[j]
        if c == '"':
            j = t.index('"', j + 1)
        elif c == "(":
            d += 1
        elif c == ")":
            d -= 1
            if d == 0:
                return j + 1
        j += 1


def find_zone(t, name):
    for m in re.finditer(r"\n\t\(zone\n", t):
        s = m.start() + 1
        e = block_end(t, s)
        if '(name "%s")' % name in t[s:e]:
            return s, e
    raise SystemExit("zone %s not found" % name)


def zone_names(t):
    out = []
    for m in re.finditer(r"\n\t\(zone\n", t):
        s = m.start() + 1
        e = block_end(t, s)
        n = re.search(r'\(name "([^"]*)"\)', t[s:e])
        if n and "(keepout" not in t[s:e]:
            out.append(n.group(1))
    return out


def fmt(v):
    s = ("%.6f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def write_pts(pts, per=5):
    items = ["(xy %s %s)" % (fmt(x), fmt(y)) for x, y in pts]
    return "\n".join("\t\t\t\t" + " ".join(items[i:i + per]) for i in range(0, len(items), per))


def fills_of(zt):
    return re.findall(r"\n\t\t\(filled_polygon\n.*?\n\t\t\)(?=\n)", zt, flags=re.S)


def replace_outline(t, name, old_seq, new_seq, log, tol=1e-6):
    s, e = find_zone(t, name)
    zt = t[s:e]
    m = re.search(r"\(polygon\n\t\t\t\(pts\n(.*?)\n\t\t\t\)\n\t\t\)", zt, re.S)
    pts = [(float(a), float(b)) for a, b in re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)", m.group(1))]
    for i in range(len(pts) - len(old_seq) + 1):
        if all(abs(pts[i + k][0] - old_seq[k][0]) <= tol and abs(pts[i + k][1] - old_seq[k][1]) <= tol for k in range(len(old_seq))):
            break
    else:
        raise SystemExit("%s: sequence not in the file: %s" % (name, old_seq))
    new = pts[:i] + list(new_seq) + pts[i + len(old_seq):]
    log.append("== %s OLD (%d pts)\n%s\n== %s NEW (%d pts)\n%s\n" % (
        name, len(pts), " ".join("(%s,%s)" % (fmt(x), fmt(y)) for x, y in pts),
        name, len(new), " ".join("(%s,%s)" % (fmt(x), fmt(y)) for x, y in new)))
    zt = zt[:m.start(1)] + write_pts(new) + zt[m.end(1):]
    zt = re.sub(r"\n\t\t\(filled_polygon\n.*?\n\t\t\)(?=\n)", "", zt, flags=re.S)
    return t[:s] + zt + t[e:]


def uid_block(t, uid, depth_tabs):
    """the block holding (uuid "uid") whose opening paren sits after depth_tabs tabs"""
    k = t.index('(uuid "%s")' % uid)
    pat = "\n" + "\t" * depth_tabs + "("
    s = t.rfind(pat, 0, k) + len(pat) - 1
    return s, block_end(t, s)


def gr_text_set(t, label, old_at, new_at, log):
    pat = '(gr_text "%s"\n\t\t(at %s)' % (label, old_at)
    k = t.index(pat)
    assert t.count(pat) == 1, label
    t = t[:k] + '(gr_text "%s"\n\t\t(at %s)' % (label, new_at) + t[k + len(pat):]
    log.append("== silk text %r: (at %s) -> (at %s)" % (label, old_at, new_at))
    return t


def field_set(t, ref, old_at, new_at, log):
    k = t.index('(property "Reference" "%s"' % ref)
    m = re.compile(r"\(at ([-\d. ]+)\)").search(t, k)
    assert m.group(1) == old_at, (ref, m.group(1))
    log.append("== %s reference: (at %s) -> (at %s) [footprint frame]" % (ref, old_at, new_at))
    return t[:m.start()] + "(at %s)" % new_at + t[m.end():]


def shift_block(b, dx):
    def f(m):
        return "(%s %s %s" % (m.group(1), fmt(float(m.group(2)) + dx), m.group(3))
    return re.sub(r"\((xy|start|end|at) ([-\d.]+) ([-\d.]+)", f, b)


# ------------------------------------------------------------------ KiCad side (run under KiCad's python)
def kicad_fill(src, dst):
    import pcbnew
    b = pcbnew.LoadBoard(src)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(dst, b)


def kicad_maker_uuids(src, out):
    import pcbnew
    b = pcbnew.LoadBoard(src)
    mm = pcbnew.ToMM
    ids = []
    for d in b.GetDrawings():
        if b.GetLayerName(d.GetLayer()) != "F.Silkscreen":
            continue
        bb = d.GetBoundingBox()
        if 46.0 <= mm(bb.GetLeft()) and mm(bb.GetRight()) <= 58.5 and 87.0 <= mm(bb.GetTop()) and mm(bb.GetBottom()) <= 93.0:
            ids.append((d.m_Uuid.AsString(), d.GetClass(), d.GetText() if d.GetClass() == "PCB_TEXT" else d.GetShapeStr()))
    json.dump(ids, open(out, "w"))


def kicad_clip(src, out):
    """for each footprint silk graphic (line or rect) that crosses a front copper edge, the pieces to keep"""
    import pcbnew
    mm = pcbnew.ToMM; M = pcbnew.FromMM
    b = pcbnew.LoadBoard(src)
    lay = pcbnew.F_Cu
    Z = pcbnew.SHAPE_POLY_SET()          # zones and tracks: edges kept 0.3 mm clear
    for z in b.Zones():
        if not z.GetIsRuleArea() and z.IsOnLayer(lay):
            Z.BooleanAdd(z.GetFilledPolysList(lay))
    for tr in b.GetTracks():
        if tr.IsOnLayer(lay):
            tr.TransformShapeToPolygon(Z, lay, 0, M(0.002), pcbnew.ERROR_INSIDE)
    Z.Simplify()
    C = pcbnew.SHAPE_POLY_SET(Z)         # all copper: pads kept the maker's 0.15 mm pad-to-silk clear
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.IsOnLayer(lay) and p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                p.TransformShapeToPolygon(C, lay, 0, M(0.002), pcbnew.ERROR_INSIDE)
    C.Simplify()

    def chains_of(P):
        out = []
        for c in range(P.OutlineCount()):
            out.append(P.Outline(c))
            for h in range(P.HoleCount(c)):
                out.append(P.Hole(c, h))
        return out
    chC, chZ = chains_of(C), chains_of(Z)

    def label(x, y, w):
        p = pcbnew.VECTOR2I(M(x), M(y))
        dC = mm(int(min(math.sqrt(ch.SquaredDistance(p, True)) for ch in chC)))
        dZ = mm(int(min(math.sqrt(ch.SquaredDistance(p, True)) for ch in chZ)))
        if dC < w / 2 + 0.15 or dZ < w / 2 + MARG:
            return "X"
        for c in range(C.OutlineCount()):
            one = pcbnew.SHAPE_POLY_SET(); one.AddOutline(C.Outline(c))
            for h in range(C.HoleCount(c)):
                one.AddHole(C.Hole(c, h))
            if one.Contains(p):
                return "C%d" % c
        return "L"

    def crosses(item):
        P = pcbnew.SHAPE_POLY_SET()
        item.TransformShapeToPolygon(P, item.GetLayer(), 0, M(0.002), pcbnew.ERROR_INSIDE)
        i0 = pcbnew.SHAPE_POLY_SET(P); i0.BooleanIntersection(C)
        f = i0.Area() / max(P.Area(), 1)
        return 1e-6 < f < 1 - 1e-6

    res = []
    for f in b.GetFootprints():
        for g in f.GraphicalItems():
            if b.GetLayerName(g.GetLayer()) != "F.Silkscreen" or g.GetClass() != "PCB_SHAPE":
                continue
            st = g.GetShapeStr()
            if st not in ("Line", "Rect"):
                continue
            if not crosses(g):
                continue
            w = mm(g.GetWidth())
            if st == "Line":
                segs = [((mm(g.GetStart().x), mm(g.GetStart().y)), (mm(g.GetEnd().x), mm(g.GetEnd().y)))]
            else:
                x0, y0, x1, y1 = mm(g.GetStart().x), mm(g.GetStart().y), mm(g.GetEnd().x), mm(g.GetEnd().y)
                segs = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
            keep = []
            for (ax, ay), (bx, by) in segs:
                L_ = math.hypot(bx - ax, by - ay)
                n = max(1, int(L_ / 0.01))
                labs = [label(ax + (bx - ax) * i / n, ay + (by - ay) * i / n, w) for i in range(n + 1)]
                i = 0
                while i <= n:
                    if labs[i] == "X":
                        i += 1
                        continue
                    j = i
                    while j + 1 <= n and labs[j + 1] == labs[i]:
                        j += 1
                    if (j - i) * L_ / n >= 0.3 or (i == 0 and j == n):
                        p = (ax + (bx - ax) * i / n, ay + (by - ay) * i / n)
                        q = (ax + (bx - ax) * j / n, ay + (by - ay) * j / n)
                        keep.append((p, q, labs[i]))
                    i = j + 1
            res.append({"ref": f.GetReference(), "uuid": g.m_Uuid.AsString(), "shape": st, "width": w,
                        "fp_at": (mm(f.GetPosition().x), mm(f.GetPosition().y)), "fp_rot": f.GetOrientationDegrees(),
                        "keep": keep})
    json.dump(res, open(out, "w"), indent=1)


# ------------------------------------------------------------------ driver
def to_rel(ax, ay, fx, fy, rot):
    dx, dy = ax - fx, ay - fy
    th = math.radians(rot)
    return (dx * math.cos(th) - dy * math.sin(th), dx * math.sin(th) + dy * math.cos(th))


def run_kicad(*args):
    subprocess.run(["nice", KPY, HERE] + list(args), check=True, stderr=subprocess.DEVNULL)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--work", default=None)
    ap.add_argument("--keep-blade-bottom", action="store_true")
    ap.add_argument("--clip-outlines", action="store_true",
                    help="cut footprint outlines at copper edges; OFF by default because the pre-order check refuses a "
                         "board footprint whose graphics differ from its library copy (lib_footprint_mismatch)")
    a = ap.parse_args()
    work = a.work or os.path.join(os.path.dirname(os.path.abspath(a.dst)), "scratch")
    os.makedirs(work, exist_ok=True)
    stem = os.path.splitext(os.path.abspath(a.src))[0]
    fdir = os.path.join(work, "kicad")
    os.makedirs(fdir, exist_ok=True)
    for ext in (".kicad_pro", ".kicad_dru"):
        shutil.copy(stem + ext, os.path.join(fdir, "heater-wall-board" + ext))
    scratch_pcb = os.path.join(fdir, "heater-wall-board.kicad_pcb")
    src_t = open(a.src, encoding="utf-8").read()
    t = src_t
    log = []

    # 7.2 copper
    old = [(56.45, 23.76), (56.45, 25.4), (53.4, 28.45), (53.4, 29.0), (53.4, 29.4), (53.4, 35.9), (49.3, 40.0),
           (49.3, 46.425), (58.1, 46.425), (58.1, 36.2), (58.4, 35.9), (58.4, 29.4), (58.4, 29.0), (58.4, 25.85),
           (57.95, 25.4), (57.95, 23.76)]
    new = [(56.45, 23.76), (56.45, 24.97), (52.95, 28.47), (52.95, 36.35), (49.3, 40.0),
           (49.3, 46.425), (57.95, 46.425), (57.95, 23.76)]
    t = replace_outline(t, "OUT_C_F0", old, new, log)
    changed = ["OUT_C_F0"]

    # 7.1 legends (board texts; 90 = reading upward)
    t = gr_text_set(t, "RET", "24.5 80.3 0", "23.475 79.9 90", log)
    t = gr_text_set(t, "RETURN", "24.5 82.3 0", "25.6 79.9 90", log)
    t = gr_text_set(t, "OUT_S", "32.6 80.3 0", "31.575 79.9 90", log)
    t = gr_text_set(t, "STEAM", "32.6 82.3 0", "33.7 79.9 90", log)
    t = gr_text_set(t, "OUT_C", "44 80.3 0", "38.45 82 90", log)
    t = gr_text_set(t, "COFFEE", "44 82.3 0", "40.575 82 90", log)
    # RV921 reference: footprint at (31, 42.5) rotated 180, so the frame offset is (31 - x, 42.5 - y); the field
    # angle is stored absolute
    t = field_set(t, "RV921", "2.5 -2.8 0", "2.35 6.8 90", log)

    # maker block +0.5 mm in x
    open(scratch_pcb, "w", encoding="utf-8").write(t)
    ids_json = os.path.join(work, "maker_ids.json")
    run_kicad("--maker", scratch_pcb, ids_json)
    ids = json.load(open(ids_json))
    assert len(ids) >= 30, ids
    for u, cls, what in ids:
        s, e = uid_block(t, u, 1)
        t = t[:s] + shift_block(t[s:e], 0.5) + t[e:]
    log.append("== maker block: %d items (logo polygons and lines, 'MADE WITH', 'STAIRCASE') moved +0.5 mm in x" % len(ids))

    # refill, transplant the changed zone's fill, check the others are identical
    open(scratch_pcb, "w", encoding="utf-8").write(t)
    filled = os.path.join(work, "filled.kicad_pcb")
    run_kicad("--fill", scratch_pcb, filled)
    ft = open(filled, encoding="utf-8").read()
    for name in zone_names(t):
        fs, fe = find_zone(ft, name)
        blocks = fills_of(ft[fs:fe])
        if name in changed:
            s, e = find_zone(t, name)
            zt = t[s:e]
            end = zt.rindex("\n\t)")
            zt = zt[:end] + "".join(blocks) + zt[end:]
            t = t[:s] + zt + t[e:]
            print("REFILLED", name, len(blocks))
        else:
            ss, se = find_zone(src_t, name)
            no = [float(v) for x in fills_of(src_t[ss:se]) for p in re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)", x) for v in p]
            nn = [float(v) for x in blocks for p in re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)", x) for v in p]
            ok = len(no) == len(nn) and all(abs(p - q) < 1e-6 for p, q in zip(no, nn))
            print("UNCHANGED-ZONE", name, "refill identical" if ok else "REFILL DIFFERS")
            if not ok:
                raise SystemExit("refill of an unchanged zone differs")

    # footprint outlines cut at copper edges (judged on the refilled copper)
    open(scratch_pcb, "w", encoding="utf-8").write(t)
    clip_json = os.path.join(work, "clip.json")
    run_kicad("--clip", scratch_pcb, clip_json)
    clips = json.load(open(clip_json)) if a.clip_outlines else []
    for c in clips:
        s, e = uid_block(t, c["uuid"], 2)
        blk = t[s:e]
        kind = "fp_line" if c["shape"] == "Line" else "fp_rect"
        assert blk.startswith("(" + kind), blk[:30]
        keep = c["keep"]
        if c["ref"] in ("J911", "J921", "J941") and not a.keep_blade_bottom:
            # the rectangle's bottom side stands alone under the strip end; drop it with the cut, keep the bracket
            ymax = max(max(p[1], q[1]) for p, q, _ in keep)
            keep = [k for k in keep if not (abs(k[0][1] - ymax) < 1e-6 and abs(k[1][1] - ymax) < 1e-6)]
        layer = re.search(r'\(layer "[^"]*"\)', blk).group(0)
        stroke = re.search(r"\(stroke\n.*?\n\t\t\t\)", blk, re.S).group(0)
        new_blocks = []
        for i, (p, q, lab) in enumerate(keep):
            rp = to_rel(p[0], p[1], c["fp_at"][0], c["fp_at"][1], c["fp_rot"])
            rq = to_rel(q[0], q[1], c["fp_at"][0], c["fp_at"][1], c["fp_rot"])
            nu = str(uuidlib.uuid5(uuidlib.NAMESPACE_URL, "heater-wall-board/r7/%s/%d" % (c["uuid"], i)))
            new_blocks.append("(fp_line\n\t\t\t(start %s %s)\n\t\t\t(end %s %s)\n\t\t\t%s\n\t\t\t%s\n\t\t\t(uuid \"%s\")\n\t\t)" % (
                fmt(round(rp[0], 6)), fmt(round(rp[1], 6)), fmt(round(rq[0], 6)), fmt(round(rq[1], 6)), stroke, layer, nu))
        t = t[:s] + "\n\t\t".join(new_blocks) + t[e:]
        log.append("== %s silk %s %s cut at copper edges into %d pieces: %s" % (
            c["ref"], c["shape"].lower(), c["uuid"], len(new_blocks),
            "; ".join("(%.3f,%.3f)-(%.3f,%.3f) %s" % (p[0], p[1], q[0], q[1], "laminate" if lab == "L" else "on copper")
                      for p, q, lab in keep)))
    open(a.dst, "w", encoding="utf-8").write(t)
    open(os.path.join(work, "changes.txt"), "w").write("\n".join(log) + "\n")
    print("wrote", a.dst)


if __name__ == "__main__":
    if sys.argv[1] == "--fill":
        kicad_fill(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "--maker":
        kicad_maker_uuids(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "--clip":
        kicad_clip(sys.argv[2], sys.argv[3])
    else:
        main()
