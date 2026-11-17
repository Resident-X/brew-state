# Reads the interlock deck logs (run ./A_run_all.sh first) and prints the removal-time budget, the timeout margin and the pick-up margin.
import re, math
def val(log, name, default=None):
    t = open(log).read()
    m = re.search(rf"^{name}\s*=\s*([-\d.e+]+)", t, re.M | re.I)
    if m is None:
        if default is None:
            raise SystemExit(f"{log}: no {name}")
        return default                       # a measure that never triggered: the level was never reached
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

rest = {k: val(f"A_rest_{k}_fix.log", "tdeca") * 1e3 for k in ("high", "low", "float")}
print("rest states, drawn circuit, gate decay from the last pump to 0.6 V: " + ", ".join("%s %.2f ms" % (k, v) for k, v in rest.items()) + " (budget term %.2f ms)" % rail_start)
print("buffer peak current: %.1f mA at 87.5 ohm, %.1f mA at the sheet's 77.5 ohm (against +-25 mA continuous, no transient figure stated)" % (-val("A_buffer_peak.log", "ipeak") * 1e3, -val("A_buffer_peak_sheet.log", "ipeak") * 1e3))
print("supply ramps, controller output undriven (reset): rail ramp / gate peak / time above 0.6 V / above 0.73 V / coil current peak, time at or above the 51.3 mA pick-up current (FETs at 0.6 V, coil 68.2 ohm)")
for tr in ("1", "5", "10", "20", "50", "200"):
    n = f"A_powerup_float_{tr}ms.log"; c = f"A_powerup_coil_{tr}ms.log"
    print("  %4s ms: %.3f V, %.1f ms, %.1f ms ; coil %.1f mA, %.1f ms at or above pick-up current" % (tr, val(n, "vgmaxa"), val(n, "tabove06a", 0) * 1e3, val(n, "tabove073a", 0) * 1e3, val(c, "icoilmax") * 1e3, val(c, "tcoil35", 0) * 1e3))
print("  with the pump diodes at VF 0.71 V (sensitivity, not a sheet figure):")
for tr in ("1", "5", "10"):
    n = f"A_powerup_float_{tr}ms_vf71.log"; c = f"A_powerup_coil_{tr}ms_vf71.log"
    print("  %4s ms: %.3f V, %.1f ms above 0.6 V ; coil %.1f mA, %.2f ms at or above pick-up current" % (tr, val(n, "vgmaxa"), val(n, "tabove06a", 0) * 1e3, val(c, "icoilmax") * 1e3, val(c, "tcoil35", 0) * 1e3))
print("  without R208 (1 T ohm): " + "; ".join("%s ms %.3f V, %.1f ms above 0.6 V" % (tr, val(f"A_powerup_float_{tr}ms_nor208.log", "vgmaxa"), val(f"A_powerup_float_{tr}ms_nor208.log", "tabove06a", 0) * 1e3) for tr in ("1", "20")))
print("supply ramps, controller output driven LOW: " + "; ".join("%s ms gate %.3f V" % (tr, val(f"A_powerup_low_{tr}ms.log", "vgmaxa")) for tr in ("1", "20")) + " ; driven HIGH: " + "; ".join("%s ms gate %.3f V, %.1f ms above 0.6 V" % (tr, val(f"A_powerup_high_{tr}ms.log", "vgmaxa"), val(f"A_powerup_high_{tr}ms.log", "tabove06a", 0) * 1e3) for tr in ("1", "20")))
print("1 ms dips to 0 / 2 / 3 / 4 V and back: output held low gate peak " + ", ".join("%.3f V" % val(f"A_dip_low_{d}V.log", "vgmaxa") for d in ("0", "2", "3", "4")) + " ; output held high " + ", ".join("%.3f V" % val(f"A_dip_high_{d}V.log", "vgmaxa") for d in ("0", "2", "3", "4")))
print("ramps down, output undriven: gate peak " + ", ".join("%s ms %.1e V" % (tr, val(f"A_powerdown_float_{tr}ms.log", "vgmaxa")) for tr in ("1", "20", "200")))
print("faults while the controller toggles, fault at 50 ms, gate decay to 0.6 V from the fault, gate at 0.5 s or later:")
for f in ("u201_high", "u201_low", "u203_high", "u203_low", "interstage_open"):
    n = f"A_fault_{f}.log"
    print("  %-16s %.2f ms, %.1e V" % (f, val(n, "tdeca") * 1e3, max(val(n, "vlatea"), val(n, "vlateb"))))
print("delay from POL_OUT to POL_BUF (50 %% of POL_OUT to 2.6 V of the buffer output, into the pump network): rising %.0f ns, falling %.0f ns, plus the sheet's 2 x 9 ns propagation (SN74AHCT1G14 tPLH/tPHL max, 50 pF, -40..85 C) not in the switch model" % (val("A_delay.log", "tdelay_rise") * 1e9, val("A_delay.log", "tdelay_fall") * 1e9))
