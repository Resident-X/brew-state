# Finds, by bisection over ngspice runs of A_hold_L0_fix.cir, the largest gate leakage current (diode + FET gate, shortest-hold
# corner, rail 4.75 V, edges every 12 ms) at which the gate still holds at or above 1.8 V just before the next edge.
# Run from this folder: python3 -I A_hold_limit.py
import re, subprocess, os
base = open("A_hold_L0_fix.cir").read()
def run(il):
    deck = re.sub(r"\.param IL=[^\n]*", f".param IL={il}", base)
    open("A_hold_limit_tmp.cir", "w").write(deck)
    subprocess.run(["ngspice", "-b", "A_hold_limit_tmp.cir", "-o", "A_hold_limit_tmp.log"], capture_output=True)
    log = open("A_hold_limit_tmp.log").read()
    g = float(re.search(r"^gmina\s*=\s*([-\d.e+]+)", log, re.M).group(1))
    m = re.search(r"^tabove_after_edge\s*=\s*([-\d.e+]+)", log, re.M)
    t = float(m.group(1)) if m else float("nan")
    return g, t
lo, hi = 0.0, 1.08e-6
for _ in range(14):
    mid = (lo + hi) / 2
    g, t = run(f"{mid:.4e}")
    if g >= 1.8: lo = mid
    else: hi = mid
g, t = run(f"{lo:.4e}")
print(f"largest total gate leakage with gmin >= 1.8 V: {lo*1e9:.1f} nA   (gmin = {g:.3f} V, time above 1.8 V after an edge = {t*1e3:.2f} ms)")
for f in ("A_hold_limit_tmp.cir", "A_hold_limit_tmp.log"):
    os.remove(f)
