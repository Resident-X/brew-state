"""3.3 V rail: LT1963AEST-3.3#TRPBF dropout and thermal limit, and the controller's junction temperature.

Sources (each read 2026-10-29):
  LT1963A  Analog Devices (Linear Technology) LT1963A series data sheet, 1963aff (the revision LCSC hosts for C459918, SOT-223 ST package):
           fixed 3.3 V output 3.200 to 3.400 V over 4.3 V to 20 V input and 1 mA to 1.5 A load and temperature (Electrical Characteristics),
           dropout 0.27 V maximum at 500 mA at 25 degC and 0.35 V maximum over temperature, GND pin current 1.5 mA maximum at no load,
           5.5 mA at 100 mA, 25 mA at 500 mA and 120 mA at 1.5 A (maxima over temperature), IN and OUT pins +/-20 V absolute maximum,
           operating junction 125 degC ("for continuous normal conditions the maximum junction temperature rating of 125 degC must not be
           exceeded"), Table 5 (SOT-223 junction to ambient, still air, 1/16 inch FR-4, 1 oz copper): 42 degC/W (2500 mm2 top, 2500 mm2
           back), 50 (225 top, 2500 back), 56 (100 top, 2500 back), 49 (1000 top, 1000 back), 52 (1000 top, none back); pin order 1 IN,
           2 GND (tab), 3 OUT; output capacitor: 10 uF with ESR from 0 ohm at 3.3 V (Table 1); current limit 2 A typical at VIN = 7 V.
  IRM-20   Mean Well IRM-20 series specification IRM-20-SPEC 2025-11-21 (https://www.meanwell.com/Upload/PDF/IRM-20/IRM-20-SPEC.PDF): 5 V output tolerance
           +/-2.5 %, ripple 200 mVp-p max, over-voltage 5.75 to 6.75 V.
  DS12110  STMicroelectronics DS12110 Rev 11 (January 2026): Table 119 (maximum run current, code in ITCM), Table 113 (maximum
           junction temperature by power scale), Table 222 (LQFP100 junction-to-ambient 45.0 degC/W), Table 112 (TA).
  Air:     controller-board-design-constraints.md, Enclosure air temperature: 70 degC assumed.
Run: python3 -I b_regulator_thermal.py
"""
TA = 70.0
vin_nom, tol = 5.0, 0.025
vin_max, vin_min = vin_nom * (1 + tol), vin_nom * (1 - tol)
ripple_pp = 0.200
vout_min, vout_max = 3.200, 3.400   # LT1963A-3.3 over line, load and temperature
dropout_max = 0.35   # at 500 mA over temperature; the controller and the other 3.3 V loads at 200 MHz are 293 mA at most
tj_max_reg = 125.0   # operating junction temperature for continuous normal conditions
tha_reg = 56.0       # maker's Table 5, 100 mm2 top copper over a 2500 mm2 board with 2500 mm2 back copper
# GND pin current, maximum over temperature (A -> A), interpolated linearly between the tabulated points
IGND = [(0.0, 1.5e-3), (0.001, 1.6e-3), (0.1, 5.5e-3), (0.5, 25e-3), (1.5, 120e-3)]


def ignd(i):
    for (a, ia), (b, ib) in zip(IGND, IGND[1:]):
        if i <= b:
            return ia + (ib - ia) * (i - a) / (b - a)
    return IGND[-1][1]


def pd(i, vin=vin_max, vout=vout_min):
    return i * (vin - vout) + vin * ignd(i)


def imax_for(theta):
    pmax = (tj_max_reg - TA) / theta
    lo, hi = 0.0, 1.5
    for _ in range(60):
        mid = (lo + hi) / 2
        if pd(mid) <= pmax:
            lo = mid
        else:
            hi = mid
    return lo


print("Dropout")
worst_in = vin_min - ripple_pp / 2
print("  lowest input %.3f V (4.875 V less half the 200 mVp-p ripple); needs >= %.3f V for the highest output %.3f V + dropout %.3f V" % (
    worst_in, vout_max + dropout_max, vout_max, dropout_max))
print("  margin %.3f V -> in regulation: %s" % (worst_in - (vout_max + dropout_max), worst_in >= vout_max + dropout_max))

print("Regulator thermal (TA 70, junction limit %.0f, theta_JA = %.0f degC/W, the maker's 100 mm2 top / 2500 mm2 back figure)" % (tj_max_reg, tha_reg))
pmax = (tj_max_reg - TA) / tha_reg
imax = imax_for(tha_reg)
print("  PD max %.3f W; PD = (5.125-%.3f)*I + 5.125*IGND(I), IGND from the maker's maxima (25 mA at 500 mA) -> largest 3.3 V load %.3f A" % (pmax, vout_min, imax))
for th in (42, 49, 52, 56, 70, 110):
    print("    theta_JA %3d: %.3f A" % (th, imax_for(th)))
print("  at the 0.293 A of stated 3.3 V loads: GND pin %.1f mA, PD %.3f W, junction %.1f degC" % (ignd(0.293) * 1e3, pd(0.293), TA + tha_reg * pd(0.293)))

# ---- controller: DS12110 Table 119, maximum IDD (mA) at Tj 25/85/105/125, fCPU, power scale, peripherals
T119 = {
    # (fCPU MHz, scale, peripherals): ({Tj: mA}, TJmax)
    (480, "VOS0", "disabled"): ({25: 226, 85: 307, 105: 390}, 105.0),
    (400, "VOS1", "disabled"): ({25: 168, 85: 230, 105: 296, 125: 384}, 125.0),
    (300, "VOS2", "disabled"): ({25: 114, 85: 170, 105: 224, 125: 297}, 125.0),
    (200, "VOS3", "disabled"): ({25: 71, 85: 121, 105: 164, 125: 223}, 125.0),
    (480, "VOS0", "enabled"): ({25: 348, 85: 439, 105: 550}, 105.0),
    (400, "VOS1", "enabled"): ({25: 256, 85: 327, 105: 416, 125: 536}, 125.0),
    (300, "VOS2", "enabled"): ({25: 183, 85: 248, 105: 320, 125: 419}, 125.0),
    (200, "VOS3", "enabled"): ({25: 116, 85: 174, 105: 233, 125: 313}, 125.0),
}
THJA = 45.0   # Table 222, LQFP100
VDD = 3.400   # the regulator's upper output, the more pessimistic supply for the controller

def idd_at(tab, tj):
    ks = sorted(tab)
    if tj <= ks[0]:
        return tab[ks[0]]
    for a, b in zip(ks, ks[1:]):
        if tj <= b:
            return tab[a] + (tab[b] - tab[a]) * (tj - a) / (b - a)
    return None  # beyond the last tabulated junction temperature

print("Controller junction temperature at TA 70 degC, VDD 3.400 V, theta_JA 45.0 (maximum IDD, interpolated between the table's Tj columns)")
print("  %-28s %-9s %-9s %-9s %s" % ("configuration", "IDD mA", "TJ degC", "TJmax", "result"))
rows = {}
for key, (tab, tjmax) in T119.items():
    tj = TA
    ok = True
    idd = None
    for _ in range(200):
        idd = idd_at(tab, tj)
        if idd is None:
            ok = False
            break
        new = TA + THJA * VDD * idd / 1000.0
        if abs(new - tj) < 1e-6:
            break
        tj = new
        if tj > tjmax + 60:
            ok = False
            break
    if ok and tj <= tjmax:
        res = "holds"
    else:
        res = "FAILS"
    rows[key] = (idd, tj, tjmax, res)
    print("  %-28s %-9s %-9s %-9.0f %s" % ("%d MHz %s, periph %s" % key, ("%.0f" % idd) if idd else "n/a", ("%.1f" % tj) if ok else "diverges", tjmax, res))

print("3.3 V rail total at the configurations that hold, against the regulator's limit %.3f A" % imax)
for key, (idd, tj, tjmax, res) in rows.items():
    if res == "holds":
        print("  %-28s controller %.0f mA -> room left for every other 3.3 V load: %.0f mA" % ("%d MHz %s, periph %s" % key, idd, imax * 1000 - idd))
print("Division record figure: 439 mA (480 MHz VOS0, all peripherals, Tj 85) -> regulator PD %.3f W against the limit %.3f W" % (
    pd(0.439), pmax))
