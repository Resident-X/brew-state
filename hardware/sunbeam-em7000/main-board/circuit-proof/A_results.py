# Reads the interlock deck logs (run ./A_run_all.sh first) and prints the removal-time budget, the timeout margin and the pick-up margin.
import re, math
def val(log, name):
    t = open(log).read()
    m = re.search(rf"^{name}\s*=\s*([-\d.e+]+)", t, re.M | re.I)
    return float(m.group(1))
rail_start   = val("A_removal_gate_rail.log", "tr06") * 1e3          # ms, gate from 5.25 V (no diode drop) to 0.6 V
rail_start05 = val("A_removal_gate_rail.log", "tr05") * 1e3          # ms, to 0.5 V (the record's end point)
nat_fix      = max(val("A_removal_gate_high_fix.log", "tdeca"), val("A_removal_gate_low_fix.log", "tdeca")) * 1e3
nat_rec_hi   = val("A_removal_gate_high_rec.log", "tdeca") * 1e3
nat_rec_lo   = val("A_removal_gate_low_rec.log", "tdeca") * 1e3
coil_h       = val("A_removal_coil.log", "tcoil_per_h") * 1e3           # ms per henry, clamp at zener low end, diode drop ~0
coil_h_real  = val("A_removal_coil_real.log", "tcoil_per_h") * 1e3
coil_h_zs    = val("A_removal_coil_zshort.log", "tcoil_per_h") * 1e3
# analytic cross-check of the clamp decay per henry: (L/R) ln((R*I0 + Vc)/(R*Ido + Vc)), R 55.8, I0 94.09 mA, Vc 11.4 V, Ido 7.3 mA
R, I0, Vc, Ido = 55.8, 5.25/55.8, 11.4, 7.3e-3
coil_h_an = 1/R * math.log((R*I0 + Vc)/(R*Ido + Vc)) * 1e3
turnoff, release, interval = 1.0, 8.0, 100.0
print("gate decay, start at the rail top, to 0.6 V (sourced threshold) : %.2f ms ; to 0.5 V (the record's end point): %.2f ms" % (rail_start, rail_start05))
print("gate decay, start as pumped, either held level, fixed circuit   : %.2f ms" % nat_fix)
print("gate decay, record's 19-part circuit: output held low %.2f ms; output held HIGH %.1f ms" % (nat_rec_lo, nat_rec_hi))
print("coil decay per henry: sim %.3f ms/H (diode ~0) ; sim with the BAS116 fit %.3f ms/H ; analytic %.3f ms/H" % (coil_h, coil_h_real, coil_h_an))
fixed = rail_start + turnoff + release
perH = max(coil_h, coil_h_an)
print("fixed part of the budget: %.2f + %.1f + %.1f = %.2f ms ; with the coil per henry %.3f ms/H the removal time is %.2f ms + L x %.3f" % (rail_start, turnoff, release, fixed, perH, fixed, perH))
print("largest coil inductance meeting %.0f ms: (%.0f - %.2f)/%.3f = %.2f H" % (interval, interval, fixed, perH, (interval-fixed)/perH))
print("at 1.68 H (the record's bound): total %.2f ms, margin %.2f ms" % (fixed + 1.68*perH, interval - fixed - 1.68*perH))
print("zener shorted (diode alone clamps, BAS116 fit): %.2f ms/H -> %.2f ms + L x %.2f ; largest L meeting 100 ms: %.2f H" % (coil_h_zs, fixed, coil_h_zs, (interval-fixed)/coil_h_zs))
for c in ("L0_fix","L1_fix","L2_fix","L3_fix","L0_rec"):
    print("hold %s: gate minimum before the next 12 ms edge %.3f V ; time above 1.8 V after an edge %.2f ms ; margin to 12 ms %.2f ms" % (c, val(f"A_hold_{c}.log","gmina"), val(f"A_hold_{c}.log","tabove_after_edge")*1e3, val(f"A_hold_{c}.log","tabove_after_edge")*1e3-12))
for T in ("25C","70C"):
    v = val(f"A_pickup_{T}.log","vcoil"); p = val(f"A_pickup_{T}.log","vpickup_limit")
    print("pick-up %s: coil voltage %.3f V against %.2f V : margin %.3f V (%.1f %%)" % (T, v, p, v-p, 100*(v-p)/p))
