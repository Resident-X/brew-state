#!/usr/bin/env python3
"""Zero-crossing detector: stress on the series resistors R630 R631 and the LED, and the LED current against the one point where the sheet states a
collector current.  Run: python3 -I E_zc_stress.py
Sources: Fosan FRC series FJ-JS-3001-V3.0 (2512: 1 W at 70 degC, max working voltage 200 V, max overload voltage 400 V, derating to 0 at 155 degC, 100 ppm/K,
1 % tolerance), Lite-On LTV-814 series BNS-OD-C131/A4 p.8-9 (IF +/-50 mA, P 70 mW, VF 1.4 V max at 20 mA, CTR 20-300 % at IF = +/-1 mA and VCE = 5 V, IC 0.2-3 mA at IF = 1 mA),
constraints record (216-253 V ac, 50 Hz, air 70 degC; entry varistor 775 V at 50 A).
"""
import math
R_NOM = 60.4e3
TOL, TCR, DT = 0.01, 100e-6, 45.0
r_lo = R_NOM * (1 - TOL) * (1 - TCR * DT)
r_hi = R_NOM * (1 + TOL) * (1 + TCR * DT)
print(f"R630 = R631: {r_lo:.0f} ohm (low end) to {r_hi:.0f} ohm (high end), 1 % and 100 ppm/K over +{DT:.0f} K")
VF_MAX = 1.4
VF_TYP = 1.2
for vrms in (253.0, 216.0):
    vpk = vrms * math.sqrt(2)
    for label, r, vf in (("R low, VF 1.2", r_lo, VF_TYP), ("R high, VF 1.4", r_hi, VF_MAX)):
        ipk = (vpk - vf) / (2 * r)
        vres = (vrms - 0) / 2          # each resistor takes half of the line (the LED's drop is a fraction of a percent of it)
        p_each = ((vpk - vf) / math.sqrt(2) / 2) ** 2 / r
        print(f"  {vrms:.0f} V rms, {label}: LED peak current {ipk*1e3:.3f} mA; each resistor {vres:.1f} V rms ({vres*math.sqrt(2):.1f} V pk), {p_each*1e3:.0f} mW")
v_each = 253.0 / 2
p_hi = (253.0 / 2) ** 2 / r_lo
print(f"worst resistor: {v_each:.1f} V rms against 200 V max working: {100*v_each/200:.1f} %; power {p_hi*1e3:.0f} mW against 1000 mW at 70 degC air ({100*p_hi/1.0:.1f} %)")
print(f"  derating curve: rating 100 % up to 70 degC; the 70 degC air figure is the curve's flat end, so no derating applies at 70 degC (it applies above 70 degC to 0 at 155 degC)")
print(f"  one resistor shorted: the other carries {253.0:.0f} V rms: {100*253.0/200:.0f} % of 200 V (over the working figure; under the 400 V overload figure)")
print(f"  entry varistor clamp 775 V across the pair: {775/2:.0f} V each against 400 V max overload voltage (the sheet's short-time overload test applies 2.5 x the rated voltage for 5 s, p.6); the maker states no microsecond surge rating")
print(f"  LED: peak {max((253*math.sqrt(2)-VF_TYP)/(2*r_lo),0)*1e3:.2f} mA against 50 mA (IF abs max): {100*((253*math.sqrt(2)-VF_TYP)/(2*r_lo))/50e-3:.1f} %; LED power peak {VF_MAX*(253*math.sqrt(2)-VF_TYP)/(2*r_lo)*1e3:.1f} mW against 70 mW")
i_min = (216 * math.sqrt(2) - VF_MAX) / (2 * r_hi)
print(f"LED peak current at the lowest supply, resistors high, VF max: {i_min*1e3:.3f} mA, against 1.0 mA, the one current at which the sheet states a collector current (IC >= 0.2 mA at CTR 20 %): {i_min/1e-3:.2f}x")
for vrms in (216.0, 253.0):
    vpk = vrms * math.sqrt(2)
    t1 = math.asin((1e-3 * 2 * r_hi + VF_MAX) / vpk) / (2 * math.pi * 50)
    print(f"  time for IF to reach 1 mA after a crossing at {vrms:.0f} V rms, R high, VF max: {t1*1e3:.3f} ms ({math.degrees(math.asin((1e-3*2*r_hi+VF_MAX)/vpk)):.1f} degrees)")
print("pull-up R632 = 22 kohm: collector current that pulls the output to VIL max = 0.3 VDD from VDD: IC >= 0.7 VDD / 22k = %.3f mA (VDD 3.0) .. %.3f mA (3.6); the sheet's IC min at IF = 1 mA is 0.2 mA at VCE = 5 V (not at this VCE)" % (0.7*3.0/22e3*1e3, 0.7*3.6/22e3*1e3))
print("  to release: IC must fall below %.3f mA (VDD 3.0) to %.3f mA (VDD 3.6) = 0.3 VDD / 22k; the sheet states no collector current below IF = 1 mA" % (0.3*3.0/22e3*1e3, 0.3*3.6/22e3*1e3))
print("collector: VCE max 3.6 V <= 35 V; pull-up current <= 0.16 mA <= IC 50 mA")
