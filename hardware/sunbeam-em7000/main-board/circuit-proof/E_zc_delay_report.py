#!/usr/bin/env python3
"""Reads E_zc_delay.log and E_zc_delay.map and prints, for every run, the delay between the true crossing and the
reported edge.  Run: python3 -I E_zc_delay_report.py
  assert delay   = time from a zero crossing to the output falling through VIL (the third falling edge, whose crossing is at 20 ms)
  release lead   = time from the output rising through VIH to the next zero crossing (the third rising edge, next crossing at 30 ms)
Both are 'by how much the reported edge is displaced from the true crossing'; the midpoint of the high gap is the crossing itself
when the two are equal.
"""
import re, sys

log = open("E_zc_delay.log").read()
vals = {}
for m in re.finditer(r"^(tf|tr)_(\d+)\s*=\s*([-+0-9.eE]+)", log, re.M):
    vals[(m.group(1), int(m.group(2)))] = float(m.group(3))
if not vals:
    sys.exit("no measurement lines in the log")
rows = []
for line in open("E_zc_delay.map"):
    i, tag = line.split()
    i = int(i)
    tf, tr = vals[("tf", i)], vals[("tr", i)]
    rows.append((tag, (tf - 20e-3) * 1e3, (30e-3 - tr) * 1e3))
print(f"{'case':56s} {'assert delay ms':>16s} {'release lead ms':>16s}")
for tag, a, r in rows:
    print(f"{tag:56s} {a:16.4f} {r:16.4f}")
al = [r[1] for r in rows]
rl = [r[2] for r in rows]
print(f"\nassert delay  : min {min(al):.4f} ms  max {max(al):.4f} ms  (of a 10 ms half-cycle: {100*min(al)/10:.2f} % to {100*max(al)/10:.2f} %)")
print(f"release lead  : min {min(rl):.4f} ms  max {max(rl):.4f} ms")
print(f"spread of the assert delay across the cases: {max(al)-min(al):.4f} ms = {(max(al)-min(al))*360/20:.2f} degrees of the 50 Hz cycle")
# the CTR = 20 % cases only (the one end the datasheet states at IF = 1 mA) and the CTR = 300 % cases only
for name in ("ctrmin", "ctrmax"):
    sel = [r for r in rows if ("_ctr" + name[3:]) in r[0]]
    print(f"{name}: assert delay {min(r[1] for r in sel):.4f}..{max(r[1] for r in sel):.4f} ms; release lead {min(r[2] for r in sel):.4f}..{max(r[2] for r in sel):.4f} ms")
