#!/usr/bin/env python3
"""Widen every silkscreen graphic stroke under 0.15 mm to 0.15 mm, board graphics and graphics inside placed footprints.
Only (width ...) lines change, plus the (end ...) of a filled circle, whose radius drops by half the added width so its
printed outline stays exactly where it was. Nothing else in the file is touched.
usage: widen_silk.py IN OUT"""
import re, sys, math
MIN = 0.15
src, dst = sys.argv[1:3]
L = open(src, encoding="utf-8").read().split("\n")
def n(v): return ("%.6f" % v).rstrip("0").rstrip(".")
head = re.compile(r"^(\t+)\((fp|gr)_(line|rect|poly|circle|arc|curve)$")
changed = 0; i = 0
while i < len(L):
    m = head.match(L[i])
    if not m: i += 1; continue
    ind = m.group(1); e = i + 1
    while L[e] != ind + ")": e += 1
    blk = L[i:e + 1]
    if any(re.search(r'\(layer "[FB]\.SilkS"\)', l) for l in blk):
        wk = [k for k in range(i, e) if re.match(r"^\s*\(width [\d.]+\)$", L[k])]
        assert len(wk) == 1, (i, L[i])
        w = float(re.search(r"[\d.]+", L[wk[0]].strip()[6:]).group(0))
        if w < MIN - 1e-9:
            L[wk[0]] = re.sub(r"\(width [\d.]+\)", "(width %s)" % n(MIN), L[wk[0]])
            if m.group(3) == "circle" and any(l.strip() == "(fill yes)" for l in blk):
                ck = [k for k in range(i, e) if L[k].strip().startswith("(center ")][0]
                ek = [k for k in range(i, e) if L[k].strip().startswith("(end ")][0]
                cx, cy = map(float, re.findall(r"[-\d.]+", L[ck].strip()[7:])[:2])
                ex, ey = map(float, re.findall(r"[-\d.]+", L[ek].strip()[4:])[:2])
                r = math.hypot(ex - cx, ey - cy); r2 = r - (MIN - w) / 2
                L[ek] = re.sub(r"\(end [^)]*\)", "(end %s %s)" % (n(cx + (ex - cx) * r2 / r), n(cy + (ey - cy) * r2 / r)), L[ek])
            changed += 1
            print("widened %s %.2f -> %.2f at line %d" % (L[i].strip(), w, MIN, i + 1))
    i = e + 1
open(dst, "w", encoding="utf-8").write("\n".join(L))
print("changed", changed)

# The TO-220 outlines of T911 and T921 end 0.155 mm from the top board edge; the wider stroke's round cap would bring them
# to 0.137 mm. Pull the two side lines' top ends down by the added half-width (0.02 mm, the cap growth plus the polygon tolerance) so the printed ink ends where it did.
L = open(dst, encoding="utf-8").read().split("\n")
for ref in ("T911", "T921"):
    p = [k for k, l in enumerate(L) if l.strip() == '(property "Reference" "%s"' % ref]; assert len(p) == 1
    s = p[0]
    while not L[s].startswith("\t(footprint "): s -= 1
    e = s + 1
    while L[e] != "\t)": e += 1
    for old, new in (("(start -2.78 -1.6)", "(start -2.78 -1.58)"), ("(end 7.86 -1.6)", "(end 7.86 -1.58)")):
        ks = [k for k in range(s, e) if L[k].strip() == old]; assert len(ks) == 1, (ref, old, ks)
        L[ks[0]] = L[ks[0]].replace(old, new); print(ref, old, "->", new)
open(dst, "w", encoding="utf-8").write("\n".join(L))
