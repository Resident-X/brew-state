#!/usr/bin/env python3
"""Final workmanship pass on the heater wall board, re-runnable from the HEAD board file.

usage: edit_final.py HEAD.kicad_pcb OUT.kicad_pcb [--xl 49.3] [--f1top 81.45] [--skip C3,C4,...] [--work DIR]
(HEAD's .kicad_pro and .kicad_dru must sit beside it with the same stem)

Text edits only (insert/replace of blocks; every other line of the file is kept as is):
  C1 OUT_C_F0: fill the wedge between the band's lower diagonal edge and U911 pin 6's finger (band edge
     straight down at x 58.1 after a 0.3 mm 45-degree step at the knee y 35.9), and end the copper left of
     RV911 pad 1 at x = XL instead of the dead stub to x 46.55 (XL 46.55 keeps the stub).
  C2 OUT_C_F1: top edge from y 80.9 to F1TOP (80.9 keeps it).
  C3 HEAT_S_OPTO_MT R921 pad 1 -> U921 pin 4: horizontal, 45 degrees, horizontal into the pad's side at its
     centre line (was a 45-degree run into the pad's corner); same length, locked kept.
  C4 +5V_WB via centred in the gap between U911 pad 1 and J931 pad 3 (y 56.8 -> 56.65), its three tracks follow.
  C5 T911 reference x 49.2 -> 48.6 (mirror of T921 / STEAM about the triac pair's centre x 44.9, over COFFEE).
  C6 RV911 reference x 47.5 -> 48.0 (centred on its body outline, as RV921's is).
  C7 (rejected by the check, MFG-9) R911 / R912 references wholly onto the OUT_C band; always run with --skip C7.
  C7b R911 / R912 references reading upward on bare laminate between the band and the resistor (owner, 2026-11-20).
  C7c (option, --opt C7c) R922 reference reading upward right of R922, the steam chain's mirror of C7b.
Zones whose outline changed lose their old fill; a scratch copy is refilled headless in KiCad and only the
changed zones' filled_polygon blocks are transplanted back. The other zones' fills are compared and must be
unchanged by the refill.
"""
import argparse, os, re, shutil, subprocess, sys, uuid

KPY = "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3"


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


def all_zone_names(t):
    out = []
    for m in re.finditer(r"\n\t\(zone\n", t):
        s = m.start() + 1
        e = block_end(t, s)
        n = re.search(r'\(name "([^"]*)"\)', t[s:e])
        if n and "(keepout" not in t[s:e]:
            out.append(n.group(1))
    return out


def fmt(v):
    return ("%.4f" % v).rstrip("0").rstrip(".")


def write_pts(pts, per=5):
    items = ["(xy %s %s)" % (fmt(x), fmt(y)) for x, y in pts]
    return "\n".join("\t\t\t\t" + " ".join(items[i:i + per]) for i in range(0, len(items), per))


def outline(zt):
    m = re.search(r"\(polygon\n\t\t\t\(pts\n(.*?)\n\t\t\t\)\n\t\t\)", zt, re.S)
    pts = [(float(a), float(b)) for a, b in re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)", m.group(1))]
    return m, pts


def find_seq(pts, seq, name, tol=1e-6):
    for i in range(len(pts) - len(seq) + 1):
        if all(abs(pts[i + k][0] - seq[k][0]) <= tol and abs(pts[i + k][1] - seq[k][1]) <= tol for k in range(len(seq))):
            return i
    raise SystemExit("%s: sequence not in the file: %s" % (name, seq))


def replace_outline(t, name, old_seq, new_seq, log):
    s, e = find_zone(t, name)
    zt = t[s:e]
    m, pts = outline(zt)
    i = find_seq(pts, old_seq, name)
    new = pts[:i] + list(new_seq) + pts[i + len(old_seq):]
    log.append((name, pts, new))
    zt = zt[:m.start(1)] + write_pts(new) + zt[m.end(1):]
    # drop the old fill blocks; the refill supplies them
    zt = re.sub(r"\n\t\t\(filled_polygon\n.*?\n\t\t\)(?=\n)", "", zt, flags=re.S)
    return t[:s] + zt + t[e:]


def seg_block(t, uid):
    k = t.index('(uuid "%s")' % uid)
    s = t.rfind("\n\t(", 0, k) + 2
    return s, block_end(t, s)


def set_seg(t, uid, start, end):
    s, e = seg_block(t, uid)
    b = t[s:e]
    assert b.startswith("(segment"), uid
    b = re.sub(r"\(start [-\d.]+ [-\d.]+\)", "(start %s %s)" % start, b, count=1)
    b = re.sub(r"\(end [-\d.]+ [-\d.]+\)", "(end %s %s)" % end, b, count=1)
    return t[:s] + b + t[e:], b


def get_seg(t, uid):
    s, e = seg_block(t, uid)
    b = t[s:e]
    st = re.search(r"\(start ([-\d.]+) ([-\d.]+)\)", b).groups()
    en = re.search(r"\(end ([-\d.]+) ([-\d.]+)\)", b).groups()
    return tuple(map(float, st)), tuple(map(float, en))


def expect_seg(t, uid, start, end):
    st, en = get_seg(t, uid)
    if max(abs(st[0] - start[0]), abs(st[1] - start[1]), abs(en[0] - end[0]), abs(en[1] - end[1])) > 1e-6:
        raise SystemExit("segment %s is %s -> %s, expected %s -> %s" % (uid, st, en, start, end))


def set_field_xya(t, ref, new, angle, expect_old):
    k = t.index('(property "Reference" "%s"' % ref)
    m = re.compile(r"\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)").search(t, k)
    old = (float(m.group(1)), float(m.group(2)))
    if max(abs(old[0] - expect_old[0]), abs(old[1] - expect_old[1])) > 1e-6:
        raise SystemExit("%s reference at %s, expected %s" % (ref, old, expect_old))
    return t[:m.start()] + "(at %s %s %s)" % (new[0], new[1], angle) + t[m.end():]


def set_field_xy(t, ref, new, expect_old):
    k = t.index('(property "Reference" "%s"' % ref)
    m = re.compile(r"\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)").search(t, k)
    old = (float(m.group(1)), float(m.group(2)))
    if max(abs(old[0] - expect_old[0]), abs(old[1] - expect_old[1])) > 1e-6:
        raise SystemExit("%s reference at %s, expected %s" % (ref, old, expect_old))
    return t[:m.start()] + "(at %s %s %s)" % (new[0], new[1], m.group(3)) + t[m.end():]


def set_field_at(t, ref, dx_new, expect_old):
    k = t.index('(property "Reference" "%s"' % ref)
    m = re.compile(r"\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)").search(t, k)
    old = (float(m.group(1)), float(m.group(2)))
    if max(abs(old[0] - expect_old[0]), abs(old[1] - expect_old[1])) > 1e-6:
        raise SystemExit("%s reference at %s, expected %s" % (ref, old, expect_old))
    return t[:m.start()] + "(at %s %s %s)" % (fmt(dx_new), m.group(2), m.group(3)) + t[m.end():]


def fills_of(zt):
    return re.findall(r"\n\t\t\(filled_polygon\n.*?\n\t\t\)(?=\n)", zt, flags=re.S)


def fill_main(src, dst):
    import pcbnew
    b = pcbnew.LoadBoard(src)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(dst, b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--xl", type=float, default=49.3)
    ap.add_argument("--f1top", type=float, default=81.45)
    ap.add_argument("--skip", default="")
    ap.add_argument("--opt", default="")
    ap.add_argument("--work", default=None)
    a = ap.parse_args()
    skip = set(x for x in a.skip.split(",") if x)
    work = a.work or os.path.join(os.path.dirname(os.path.abspath(a.dst)), "scratch_" + os.path.basename(a.dst))
    os.makedirs(work, exist_ok=True)
    t = open(a.src, encoding="utf-8").read()
    log, changed = [], []

    if "C1" not in skip:
        xl = a.xl
        old = [(53.4, 35.9), (46.55, 42.75), (46.55, 46.425), (58.1, 46.425), (58.1, 44.425), (49.875, 44.425), (58.4, 35.9)]
        new = [(53.4, 35.9), (xl, round(35.9 + 53.4 - xl, 4)), (xl, 46.425), (58.1, 46.425), (58.1, 36.2), (58.4, 35.9)]
        t = replace_outline(t, "OUT_C_F0", old, new, log)
        changed.append("OUT_C_F0")
    if "C2" not in skip and abs(a.f1top - 80.9) > 1e-9:
        old = [(41.55, 80.9), (41.55, 94.1), (46.55, 94.1), (46.55, 80.9)]
        new = [(41.55, a.f1top), (41.55, 94.1), (46.55, 94.1), (46.55, a.f1top)]
        t = replace_outline(t, "OUT_C_F1", old, new, log)
        changed.append("OUT_C_F1")
    if "C3" not in skip:
        A, B = "f9109554-4377-5f1c-8f23-839e56afff5f", "f1da22f9-6062-58e9-8222-ef82e0506fcc"
        expect_seg(t, A, (52.965, 72.5), (56.575, 72.5))
        expect_seg(t, B, (56.575, 72.5), (58.1, 70.975))
        t, _ = set_seg(t, A, ("52.965", "72.5"), ("55.05", "72.5"))
        t, bb = set_seg(t, B, ("55.05", "72.5"), ("56.575", "70.975"))
        nb = bb.replace("(start 55.05 72.5)", "(start 56.575 70.975)").replace("(end 56.575 70.975)", "(end 58.1 70.975)")
        nu = str(uuid.uuid5(uuid.NAMESPACE_URL, "heater-wall-board/final-pass/C3"))
        nb = re.sub(r'\(uuid "[^"]*"\)', '(uuid "%s")' % nu, nb)
        s, e = seg_block(t, B)
        t = t[:e] + "\n\t" + nb + t[e:]
        log.append(("C3", "HEAT_S_OPTO_MT", "(52.965,72.5)-(56.575,72.5)-(58.1,70.975) -> (52.965,72.5)-(55.05,72.5)-(56.575,70.975)-(58.1,70.975)"))
    if "C4" not in skip:
        V = "6c98a447-d491-5727-9aa1-49735b7e03f0"
        k = t.index('(uuid "%s")' % V)
        s = t.rfind("\n\t(", 0, k) + 2
        e = block_end(t, s)
        vb = t[s:e]
        assert "(at 58.1 56.8)" in vb
        t = t[:s] + vb.replace("(at 58.1 56.8)", "(at 58.1 56.65)") + t[e:]
        segs = {"cdd4d039-6bb5-5892-89c4-19776f1d8057": ((63.18, 58.2), (61.78, 56.8), ("63.180000", "58.200000"), ("61.630000", "56.650000")),
                "fcba8e33-dea3-59ca-8346-b3a817a14105": ((61.78, 56.8), (58.1, 56.8), ("61.630000", "56.650000"), ("58.100000", "56.650000")),
                "ace84428-7813-5c90-acbd-104caf4618f2": ((58.1, 56.8), (58.1, 54.955), ("58.100000", "56.650000"), ("58.100000", "54.955000"))}
        for uid, (os_, oe, ns, ne) in segs.items():
            expect_seg(t, uid, os_, oe)
            t, _ = set_seg(t, uid, ns, ne)
        log.append(("C4", "+5V_WB", "via (58.1,56.8) -> (58.1,56.65); B tracks (63.18,58.2)-(61.78,56.8)-(58.1,56.8) -> (63.18,58.2)-(61.63,56.65)-(58.1,56.65); F track start 56.8 -> 56.65"))
    if "C5" not in skip:
        t = set_field_at(t, "T911", -6.06, (-5.46, -0.16))
        log.append(("C5", "T911 reference", "(49.2,22.7) -> (48.6,22.7)"))
    if "C6" not in skip:
        t = set_field_at(t, "RV911", 2.5, (3.0, 5.3))
        log.append(("C6", "RV911 reference", "(47.5,34.7) -> (48.0,34.7)"))
    if "C7b" not in skip:
        # owner's ruling 2026-11-20: R911 and R912 references read upward (90 degrees) on bare laminate in the gap
        # between the OUT_C band (right edge x 58.1 / 58.4) and the resistor's silk (x 61.015), centred on x 59.7
        # and level with the resistor's centre; the field angle is stored absolute, the offset in the part's frame
        t = set_field_xya(t, "R911", ("0", "-2.3"), "90", (0.002501, -3.4))
        t = set_field_xya(t, "R912", ("0", "-2.3"), "90", (1.102501, -3.4))
        log.append(("C7b", "R911 and R912 references", "R911 (58.6,38.5) horizontal -> (59.7,38.503) reading upward; R912 (58.6,27.4) horizontal -> (59.7,28.503) reading upward"))
    if "C7c" in a.opt:
        t = set_field_xya(t, "R922", ("0", "2.3"), "90", (0.002501, 3.8))
        log.append(("C7c", "R922 reference (option)", "(42.4,28.5) horizontal -> (40.9,28.503) reading upward"))
    if "C7" not in skip:
        # with the wedge filled, R911's reference (58.6, 38.5) would stand across the band's new right edge (x 58.1),
        # as R912's (58.6, 27.4) already stands across the band's edge (x 58.4); the gap between the band and the
        # resistors (3.0 and 2.7 mm) is narrower than the 3.6 mm text, so both move wholly onto the band, centred
        # on x 56.0 and level with their resistor's centre
        t = set_field_xy(t, "R911", ("0.002501", "-6"), (0.002501, -3.4))
        t = set_field_xy(t, "R912", ("0.002501", "-6"), (1.102501, -3.4))
        log.append(("C7", "R911 and R912 references", "R911 (58.6,38.5) -> (56.0,38.5); R912 (58.6,27.4) -> (56.0,28.5)"))

    # refill a scratch copy beside copies of the project and rules, transplant only the changed zones' fills
    stem = os.path.splitext(os.path.abspath(a.src))[0]
    fdir = os.path.join(work, "fill")
    os.makedirs(fdir, exist_ok=True)
    for ext in (".kicad_pro", ".kicad_dru"):
        shutil.copy(stem + ext, os.path.join(fdir, "heater-wall-board" + ext))
    pre = os.path.join(fdir, "heater-wall-board.kicad_pcb")
    open(pre, "w", encoding="utf-8").write(t)
    filled = os.path.join(work, "filled.kicad_pcb")
    subprocess.run(["nice", KPY, os.path.abspath(__file__), "--fill", pre, filled], check=True,
                   stderr=subprocess.DEVNULL)
    ft = open(filled, encoding="utf-8").read()
    src_t = open(a.src, encoding="utf-8").read()
    for name in all_zone_names(t):
        fs, fe = find_zone(ft, name)
        blocks = fills_of(ft[fs:fe])
        if name in changed:
            s, e = find_zone(t, name)
            zt = t[s:e]
            assert not fills_of(zt)
            end = zt.rindex("\n\t)")
            zt = zt[:end] + "".join(blocks) + zt[end:]
            t = t[:s] + zt + t[e:]
            print("REFILLED", name, "blocks", len(blocks))
        else:
            ss, se = find_zone(src_t, name)
            old_blocks = fills_of(src_t[ss:se])
            norm = lambda bl: [re.sub(r"\s+", " ", x) for x in bl]
            same = [re.findall(r"[-\d.]+", x) for x in norm(old_blocks)] == [re.findall(r"[-\d.]+", x) for x in norm(blocks)]
            nums_old = [float(v) for x in old_blocks for v in re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)", x) for v in v]
            nums_new = [float(v) for x in blocks for v in re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)", x) for v in v]
            eq = len(nums_old) == len(nums_new) and all(abs(p - q) < 1e-6 for p, q in zip(nums_old, nums_new))
            print("UNCHANGED-ZONE", name, "refill identical" if eq else "REFILL DIFFERS (kept the committed fill)")
    open(a.dst, "w", encoding="utf-8").write(t)
    with open(os.path.join(work, "changes.txt"), "w") as f:
        for item in log:
            if len(item) == 3 and isinstance(item[1], list):
                name, old, new = item
                f.write("== %s OLD (%d pts)\n%s\n== %s NEW (%d pts)\n%s\n\n" % (
                    name, len(old), " ".join("(%s,%s)" % (fmt(x), fmt(y)) for x, y in old),
                    name, len(new), " ".join("(%s,%s)" % (fmt(x), fmt(y)) for x, y in new)))
            else:
                f.write("== %s %s: %s\n\n" % item)
    print("wrote", a.dst, "changes in", os.path.join(work, "changes.txt"))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--fill":
        fill_main(sys.argv[2], sys.argv[3])
    else:
        main()
