#!/usr/bin/env python3
"""Apply widen_silk.py's change to the board's own footprint library, so each placed footprint still matches its library copy:
every silk stroke under 0.15 mm becomes 0.15 mm, a filled silk circle's radius drops by half the added width, and the TO-220
outline's two side lines end 0.02 mm lower at the top. Only those tokens change in each file.
usage: widen_lib.py PRETTY_DIR"""
import re, sys, os, math
MIN = 0.15
def n(v): return ("%.6f" % v).rstrip("0").rstrip(".")
for fn in sorted(os.listdir(sys.argv[1])):
    if not fn.endswith(".kicad_mod"): continue
    p = os.path.join(sys.argv[1], fn); L = open(p, encoding="utf-8").read().split("\n"); c = 0
    for k, l in enumerate(L):
        if not re.search(r'\(layer "[FB]\.SilkS"\)', l) or not l.lstrip().startswith(("(fp_line", "(fp_rect", "(fp_poly", "(fp_circle", "(fp_arc")): continue
        w = float(re.search(r"\(width ([\d.]+)\)", l).group(1))
        if w >= MIN - 1e-9: continue
        l = re.sub(r"\(width [\d.]+\)", "(width %s)" % n(MIN), l)
        if l.lstrip().startswith("(fp_circle") and re.search(r"\(fill (yes|solid)\)", l):
            cx, cy = map(float, re.search(r"\(center ([-\d.]+) ([-\d.]+)\)", l).groups())
            ex, ey = map(float, re.search(r"\(end ([-\d.]+) ([-\d.]+)\)", l).groups())
            r = math.hypot(ex - cx, ey - cy); r2 = r - (MIN - w) / 2
            l = re.sub(r"\(end [^)]*\)", "(end %s %s)" % (n(cx + (ex - cx) * r2 / r), n(cy + (ey - cy) * r2 / r)), l)
        if fn.startswith("TO-220-3_Vertical_Insulated_OvalPads"):
            l = l.replace("(start -2.78 -1.6)", "(start -2.78 -1.58)").replace("(end 7.86 -1.6)", "(end 7.86 -1.58)")
        L[k] = l; c += 1
    open(p, "w", encoding="utf-8").write("\n".join(L)); print(fn, "changed", c)
