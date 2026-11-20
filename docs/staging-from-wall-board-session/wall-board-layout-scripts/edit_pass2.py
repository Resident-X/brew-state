#!/usr/bin/env python3
"""Pass 2 edit of the heater wall board, re-runnable from the HEAD board file.

usage: edit_pass2.py HEAD.kicad_pcb OUT.kicad_pcb [WORKDIR]
(the HEAD board's .kicad_pro and .kicad_dru must sit beside it, with the same file stem)

1. text-edit the outline polygons of OUT_C_F0, OUT_C_B0, RET_F0, RET_B0 (everything else in the file is kept as is);
2. move the mains warning silk block;
3. refill in KiCad (pcbnew, headless) a scratch copy, and transplant ONLY those four zones' filled_polygon blocks back.
Run with plain python3; the fill step re-invokes this file under KiCad's python (--fill IN OUT).
"""
import os, re, shutil, subprocess, sys

KPY = "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3"
TOL = 0.01
ZONES = ("OUT_C_F0", "OUT_C_B0", "RET_F0", "RET_B0")

# (old sequence as listed by the owner, new sequence); old points are matched within TOL, new points are written as given
# unless an existing neighbour value in the file is the better value (None = keep the file's own value).
EDITS = {
    "OUT_C_F0": (
        [(56.45, 25.40), (53.40, 28.45), (53.40, 29.00), (53.40, 29.40), (53.40, 35.90), (41.55, 47.75), (41.55, 69.60),
         (46.55, 69.60), (46.55, 47.75), (47.88, 46.42), (58.10, 46.42), (58.10, 44.42), (49.88, 44.42), (58.40, 35.90)],
        [None, None, None, None, None, (46.55, 42.75), (46.55, 46.425), None, None, None, None]),
    "OUT_C_B0": (
        [(56.45, 37.60), (51.65, 37.60), (41.55, 47.75), (41.55, 94.10), (46.55, 94.10), (46.55, 47.75), (51.75, 42.50),
         (64.00, 27.40), (59.95, 27.40), (57.95, 25.40), (57.95, 23.76)],
        None),
    "RET_F0": ([(27.2, 22.01), (21.50, 22.01), (21.50, 94.10)], None),
    "RET_B0": ([(27.2, 22.01), (21.50, 22.01), (21.50, 94.10)], None),
}
# explicit replacement tails (list of (old_slice_start, old_slice_end, new_points)) are coded in apply_outline below


def block_end(t, i):
    """index just past the parenthesised block starting at t[i] == '('"""
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


def fmt(v):
    return ("%.4f" % v).rstrip("0").rstrip(".")


def pts_span(zt):
    m = re.search(r"\(polygon\n\t\t\t\(pts\n(.*?)\n\t\t\t\)\n\t\t\)", zt, re.S)
    return m


def parse_pts(body):
    return [(a, b) for a, b in re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)", body)]


def write_pts(pts, per=5):
    items = ["(xy %s %s)" % p for p in pts]
    rows = ["\t\t\t\t" + " ".join(items[i:i + per]) for i in range(0, len(items), per)]
    return "\n".join(rows)


def apply_outline(zt, name, log):
    m = pts_span(zt)
    pts = parse_pts(m.group(1))
    old = [(float(a), float(b)) for a, b in pts]

    def find(seq):
        for i in range(len(old) - len(seq) + 1):
            if all(abs(old[i + k][0] - seq[k][0]) <= TOL and abs(old[i + k][1] - seq[k][1]) <= TOL for k in range(len(seq))):
                return i
        raise SystemExit("%s: the existing sequence is not in the file: %s" % (name, seq))

    seq = EDITS[name][0]
    i = find(seq)
    for k, p in enumerate(seq):
        d = max(abs(old[i + k][0] - p[0]), abs(old[i + k][1] - p[1]))
        if d > 1e-9:
            log.append("%s: listed %s differs from file %s by %.4f" % (name, p, old[i + k], d))
    new = list(pts)
    if name == "OUT_C_F0":
        # points i+5 .. i+9 (41.55,47.75 / 41.55,69.6 / 46.55,69.6 / 46.55,47.75 / 47.88,46.42) become two points
        new[i + 5:i + 10] = [("46.55", "42.75"), ("46.55", pts[i + 9][1])]
    elif name == "OUT_C_B0":
        # (46.55,47.75) (51.75,42.5) (64,42.5) (64,27.4) (59.95,27.4) -> (46.55,49.35) (53.4,42.5) (62.5,42.5) (62.5,29.95)
        new[i + 5:i + 9] = [("46.55", "49.35"), ("53.4", "42.5"), ("62.5", "42.5"), ("62.5", "29.95")]
        # the old list has (64,42.5) before (64,27.4): handle exactly (seq has 9 entries 5..8 = 46.55,51.75 ; the 64 pair is skipped by find)
    else:
        new[i + 1:i + 2] = [("25", "22.01"), ("21.5", "25.51")]
    return zt[:m.start(1)] + write_pts(new) + zt[m.end(1):], pts, new


# the OUT_C_B0 old tail as it is in the file: ... (46.55,47.75) (51.75,42.5) (64,42.5) (64,27.4) (59.95,27.4) (57.95,25.4) (57.95,23.76)
EDITS["OUT_C_B0"] = (
    [(56.45, 37.60), (51.65, 37.60), (41.55, 47.75), (41.55, 94.10), (46.55, 94.10), (46.55, 47.75), (51.75, 42.50),
     (64.00, 42.50), (64.00, 27.40), (59.95, 27.40), (57.95, 25.40), (57.95, 23.76)], None)


def apply_outline_b(zt, name, log):
    m = pts_span(zt)
    pts = parse_pts(m.group(1))
    old = [(float(a), float(b)) for a, b in pts]
    seq = EDITS[name][0]
    for i in range(len(old) - len(seq) + 1):
        if all(abs(old[i + k][0] - seq[k][0]) <= TOL and abs(old[i + k][1] - seq[k][1]) <= TOL for k in range(len(seq))):
            break
    else:
        raise SystemExit("OUT_C_B0 sequence not found")
    for k, p in enumerate(seq):
        d = max(abs(old[i + k][0] - p[0]), abs(old[i + k][1] - p[1]))
        if d > 1e-9:
            log.append("%s: listed %s differs from file %s by %.4f" % (name, p, old[i + k], d))
    new = list(pts)
    new[i + 5:i + 10] = [("46.55", "49.35"), ("53.4", "42.5"), ("62.5", "42.5"), ("62.5", "29.95")]
    return zt[:m.start(1)] + write_pts(new) + zt[m.end(1):], pts, new


# ---------------------------------------------------------------- silk
RATING = "230 V~ 50 Hz"          # set to "230 V~" if the measured ink is too near x 35.0 or the pin-name texts
CX = 41.0
TRI_DY, TRI_DX = -3.0, 7.5       # old centre (33.5, 56.5) -> (41.0, 53.5)
UID = {  # uuids of the HEAD items that are edited in place
    "tri": "05a04f14-16a0-5a89-a6a1-5bf55079e764", "bolt": "f31c05bc-eddf-5e98-9ec5-a9151ad02e68",
    "danger": "57d77b44-8ac8-5782-ac57-99733d97c506", "mains": "1482a521-3182-5897-b965-35dbfc49d918",
    "rating": "4062b7ac-f5ec-5d44-8aae-0a96b81c2b52"}
VOLTAGE_UUID = "7c1d3a52-90e4-5b6a-8f3e-2d4b6a1c9e07"
DY = {"danger": 58.6, "mains": 61.0, "voltage": 63.4, "rating": 65.6}   # centre y; the mains text is split in two


def top_block(t, uuid):
    k = t.index('(uuid "%s")' % uuid)
    s = t.rfind("\n\t(", 0, k) + 1
    return s, block_end(t, s)


def move_poly(t, uuid):
    s, e = top_block(t, uuid)
    b = t[s:e]
    m = re.search(r"\(pts\n\t\t\t(.*?)\n\t\t\)", b, re.S)
    pts = [(float(a), float(c)) for a, c in re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)", m.group(1))]
    new = " ".join("(xy %s %s)" % (fmt(x + TRI_DX), fmt(y + TRI_DY)) for x, y in pts)
    return t[:s] + b[:m.start(1)] + new + b[m.end(1):] + t[e:]


def set_text(t, uuid, label, y):
    s, e = top_block(t, uuid)
    b = t[s:e]
    b = re.sub(r'\(gr_text "[^"]*"', '(gr_text "%s"' % label, b, count=1)
    b = re.sub(r"\(at [-\d.]+ [-\d.]+ 0\)", "(at %s %s 0)" % (fmt(CX), fmt(y)), b, count=1)
    return t[:s] + b + t[e:], b


def do_silk(t):
    t = move_poly(t, UID["tri"])
    t = move_poly(t, UID["bolt"])
    t, _ = set_text(t, UID["danger"], "DANGER", DY["danger"])
    t, mb = set_text(t, UID["mains"], "MAINS", DY["mains"])
    t, _ = set_text(t, UID["rating"], RATING, DY["rating"])
    vb = mb.replace('(gr_text "MAINS"', '(gr_text "VOLTAGE"').replace(UID["mains"], VOLTAGE_UUID)
    vb = re.sub(r"\(at [-\d.]+ [-\d.]+ 0\)", "(at %s %s 0)" % (fmt(CX), fmt(DY["voltage"])), vb, count=1)
    s, e = top_block(t, UID["mains"])
    return t[:e] + "\n" + vb + t[e:]


# ---------------------------------------------------------------- fill
def fill_main(src, dst):
    import pcbnew
    b = pcbnew.LoadBoard(src)
    zs = b.Zones()
    pcbnew.ZONE_FILLER(b).Fill(zs)
    pcbnew.SaveBoard(dst, b)


def fills_of(zt):
    out = []
    for m in re.finditer(r"\n\t\t\(filled_polygon\n", zt):
        s = m.start() + 1
        out.append((s, block_end(zt, s)))
    return out


def main():
    src, dst = sys.argv[1], sys.argv[2]
    work = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(os.path.abspath(dst)), "scratch")
    os.makedirs(work, exist_ok=True)
    t = open(src, encoding="utf-8").read()
    log, summary = [], {}
    for name in ZONES:
        s, e = find_zone(t, name)
        zt = t[s:e]
        zt2, oldp, newp = (apply_outline_b if name == "OUT_C_B0" else apply_outline)(zt, name, log)
        # drop the old fills; they are replaced after the refill
        for fs, fe in reversed(fills_of(zt2)):
            zt2 = zt2[:fs] + zt2[fe + 1:]
        t = t[:s] + zt2 + t[e:]
        summary[name] = (oldp, newp)
    t = do_silk(t)
    # the fill must see the project's net classes and custom rules, so the scratch copy sits beside copies of them
    stem = os.path.splitext(os.path.abspath(src))[0]
    fdir = os.path.join(work, "fill")
    os.makedirs(fdir, exist_ok=True)
    for ext in (".kicad_pro", ".kicad_dru"):
        shutil.copy(stem + ext, os.path.join(fdir, "heater-wall-board" + ext))
    pre = os.path.join(fdir, "heater-wall-board.kicad_pcb")
    open(pre, "w", encoding="utf-8").write(t)
    filled = os.path.join(work, "filled.kicad_pcb")
    subprocess.run(["nice", KPY, os.path.abspath(__file__), "--fill", pre, filled], check=True)
    ft = open(filled, encoding="utf-8").read()
    for name in ZONES:
        s, e = find_zone(t, name)
        fs_, fe_ = find_zone(ft, name)
        fz = ft[fs_:fe_]
        blocks = [fz[a:b] for a, b in fills_of(fz)]
        assert blocks, "no fill produced for " + name
        zt = t[s:e]
        assert not fills_of(zt)
        end = zt.rindex("\n\t)")
        zt = zt[:end + 1] + "".join(b + "\n" for b in blocks) + zt[end + 1:]
        t = t[:s] + zt + t[e:]
        print(name, "fill blocks", len(blocks))
    open(dst, "w", encoding="utf-8").write(t)
    for l in log:
        print("NOTE", l)
    import json
    json.dump({k: v for k, v in summary.items()}, open(os.path.join(work, "outlines.json"), "w"), indent=1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--fill":
        fill_main(sys.argv[2], sys.argv[3])
    else:
        main()
