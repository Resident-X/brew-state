#!/usr/bin/env python3
"""Round-2 silk edits on the heater wall board: move named silk items (only their (at ...) / (xy ...) lines change) and
insert two new texts before the final ')'. Every edit asserts it matches exactly one place.
usage: edit_silk.py IN OUT
"""
import re, sys, uuid
src, dst = sys.argv[1:3]
L = open(src, encoding="utf-8").read().split("\n")
def n(v): return ("%.4f" % v).rstrip("0").rstrip(".")
def block_of_uuid(u):
    hits = [i for i, l in enumerate(L) if l.strip() == '(uuid "%s")' % u]
    assert len(hits) == 1, (u, hits)
    i = hits[0]
    s = i
    while not L[s].startswith("\t(gr_"): s -= 1
    return s, i
def move_at(u, x, y, rot):
    s, e = block_of_uuid(u)
    ats = [k for k in range(s, e) if L[k].strip().startswith("(at ")]
    assert len(ats) == 1
    old = L[ats[0]]; L[ats[0]] = re.sub(r"\(at [^)]*\)", "(at %s %s %s)" % (n(x), n(y), n(rot)), old)
    print("moved", L[s].strip(), old.strip(), "->", L[ats[0]].strip())
def shift_poly(u, dx, dy):
    s, e = block_of_uuid(u)
    ks = [k for k in range(s, e) if "(xy " in L[k]]
    assert len(ks) == 1
    old = L[ks[0]]
    L[ks[0]] = re.sub(r"\(xy ([-\d.]+) ([-\d.]+)\)", lambda m: "(xy %s %s)" % (n(float(m.group(1)) + dx), n(float(m.group(2)) + dy)), old)
    print("shifted poly", u, "->", L[ks[0]].strip())
def move_ref(ref, lx, ly, rot):
    hits = [i for i, l in enumerate(L) if l.strip() == '(property "Reference" "%s"' % ref]
    assert len(hits) == 1, ref
    k = hits[0] + 1; assert L[k].strip().startswith("(at ")
    old = L[k]; L[k] = re.sub(r"\(at [^)]*\)", "(at %s %s %s)" % (n(lx), n(ly), n(rot)), old)
    print("ref", ref, old.strip(), "->", L[k].strip())
# (b) hazard block: 3.75 mm right, onto the bare laminate east of the HEAT_S_GATE_R track
DX = 3.75
for u in ("05a04f14-16a0-5a89-a6a1-5bf55079e764", "f31c05bc-eddf-5e98-9ec5-a9151ad02e68"): shift_poly(u, DX, 0)
for u, y in (("57d77b44-8ac8-5782-ac57-99733d97c506", 58.6), ("1482a521-3182-5897-b965-35dbfc49d918", 61),
             ("7c1d3a52-90e4-5b6a-8f3e-2d4b6a1c9e07", 63.4), ("4062b7ac-f5ec-5d44-8aae-0a96b81c2b52", 65.6)):
    move_at(u, 41 + DX, y, 0)
# (a) J931 pin names: columns directly left of J931, left-to-right in the header's own pin order 3, 2, 1
move_at("e11d627e-10d0-52cc-9dbe-d29d6463d295", 52.6, 64.6, 90)
move_at("7c40a9db-46db-5ba1-9f44-10426046d7a2", 54.1, 64.6, 90)
move_at("318cac57-6381-5e02-b0cc-dc4ced4c4975", 55.6, 64.6, 90)
# the reference texts that held that strip (footprint-relative coordinates; text angle absolute)
move_ref("J931", 0, 12.28, 90)      # board (50.9, 58.2), vertical, heading the pin-name columns
move_ref("U911", 2.29, -7.04, 0)    # board (53.6, 47.9), left of U911's upper half, between the pour and the slot
move_ref("U921", 7.39, 0.24, 0)     # board (60.4, 73.6), just below U921's output pads
NS = uuid.UUID("5d1c0f7e-3a52-4b0a-9a6e-77c0b4a3e003")
def text(key, s, layer, x, y, just):
    return ('\t(gr_text "%s"\n\t\t(at %s %s 0)\n\t\t(layer "%s")\n\t\t(uuid "%s")\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t\t(justify %s)\n\t\t)\n\t)'
            % (s, n(x), n(y), layer, uuid.uuid5(NS, key), just))
new = [text("j931_dest", "TO MAIN BOARD J761", "F.SilkS", 56.2, 68.25, "right"),
       text("jlc_order", "JLCJLCJLCJLC", "B.SilkS", 56.5, 80.0, "mirror")]
assert L[-1] == "" and L[-2] == ")"
L = L[:-2] + new + [")", ""]
open(dst, "w", encoding="utf-8").write("\n".join(L))
