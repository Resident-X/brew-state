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
rest = {k: val(f"A_rest_{k}_fix.log", "tdeca") * 1e3 for k in ("high", "low", "float_high", "float_low")}
rest_late = max(val(f"A_rest_{k}_fix.log", "vlatea") for k in rest)
coil_h       = val("A_removal_coil.log", "tcoil_per_h") * 1e3           # ms per henry, clamp at zener low end, diode drop ~0
coil_h_real  = val("A_removal_coil_real.log", "tcoil_per_h") * 1e3
coil_h_zs    = val("A_removal_coil_zshort.log", "tcoil_per_h") * 1e3
# analytic cross-check of the clamp decay per henry: (L/R) ln((R*I0 + Vc)/(R*Ido + Vc)), R 55.8, I0 94.09 mA, Vc 11.4 V, Ido 7.3 mA
R, I0, Vc, Ido = 55.8, 5.25/55.8, 11.4, 7.3e-3
coil_h_an = 1/R * math.log((R*I0 + Vc)/(R*Ido + Vc)) * 1e3
turnoff, release, interval = 1.0, 8.0, 100.0
print("gate decay, start at the rail top, to 0.6 V (sourced threshold) : %.2f ms ; to 0.5 V (the record's end point): %.2f ms" % (rail_start, rail_start05))
print("gate decay, start as pumped, either held level, fixed circuit   : %.2f ms" % nat_fix)
print("gate decay, record's 19-part circuit: POL_OUT held high %.2f ms; POL_OUT held LOW (buffer output held high) %.1f ms" % (nat_rec_hi, nat_rec_lo))
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
print("rest states, drawn circuit, gate decay from the last pump to 0.6 V: " + ", ".join("%s %.2f ms" % (k, v) for k, v in rest.items()) + " (budget term %.2f ms); gate at 0.5 s or later at most %.2e V" % (rail_start, rest_late))
print("buffer peak current: %.1f mA at 87.5 ohm, %.1f mA at the sheet's 77.5 ohm (against +-25 mA continuous, no transient figure stated)" % (-val("A_buffer_peak.log", "ipeak") * 1e3, -val("A_buffer_peak_sheet.log", "ipeak") * 1e3))
print("supply ramps, output high-impedance (the strap holds POL_IN): rail ramp / gate peak / time gate above 0.6 V / above 0.73 V / above 1.8 V / coil current peak, time at or above the 51.3 mA pick-up current (FETs at 0.6 V)")
for tr in ("1", "5", "10", "20", "50", "200"):
    n = f"A_powerup_float_{tr}ms.log"
    c = f"A_powerup_coil_{tr}ms.log" if tr != "200" else None
    row = "  %4s ms: %.3f V, %.1f ms, %.1f ms, %.1f ms" % (tr, val(n, "vgmaxa"), val(n, "tabove06a", 0) * 1e3, val(n, "tabove073a", 0) * 1e3, val(n, "tabove18a", 0) * 1e3)
    if c and tr != "200":
        row += " ; coil %.1f mA, %.1f ms" % (val(c, "icoilmax") * 1e3, val(c, "tcoil35", 0) * 1e3)
    print(row)
for tr in ("1", "20"):
    n = f"A_powerup_float_{tr}ms_vf71.log"
    print("  %4s ms with pump diodes at VF 0.71 V (sensitivity): %.3f V, %.1f ms above 0.6 V, %.1f ms above 1.8 V" % (tr, val(n, "vgmaxa"), val(n, "tabove06a", 0) * 1e3, val(n, "tabove18a", 0) * 1e3))
print("supply ramps, output held LOW (buffer output high at the rail's rise), the stuck-low rail-restart case:")
for tr in ("1", "5", "10", "20", "50"):
    n = f"A_powerup_low_{tr}ms.log" if tr in ("1", "20") else None
    c = f"A_powerup_coil_low_{tr}ms.log"
    print("  %4s ms: coil current peak %.1f mA, %.1f ms at or above the pick-up current%s" % (tr, val(c, "icoilmax") * 1e3, val(c, "tcoil35", 0) * 1e3, ("; gate peak %.2f V, %.1f ms above 0.6 V" % (val(n, "vgmaxa"), val(n, "tabove06a", 0) * 1e3)) if n else ""))
print("rail dips to 0 / 1 / 2 / 3 / 4 V and back in 1 ms each way, output held low: gate peak " + ", ".join("%.2f V" % val(f"A_dip_low_{d}V.log", "vgmaxa") for d in ("0", "1", "2", "3", "4")))
print("supply ramps down, output high-impedance: gate peak " + ", ".join("%s ms %.1e V" % (tr, val(f"A_powerdown_float_{tr}ms.log", "vgmaxa")) for tr in ("1", "20", "200")))
