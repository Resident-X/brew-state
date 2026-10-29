#!/usr/bin/env python3
"""Series resistor R207 between the controller's proof-of-life output (POL_OUT, PC7) and the interlock buffer U201 input
(POL_IN): the current it leaves in the buffer's input when +5V is absent and +3V3 present, the logic levels it leaves
at the buffer input, and the delay it adds against the interlock's timing.

Run:  python3 -I A_pol_series.py > A_pol_series.log     (from this folder; exit 0 when no check fails)

Every constant names its source on its line. Datasheets read 2026-10-29.
"""
import math
import sys

fails = []


def check(name, ok, text):
    print(("PASS  " if ok else "FAIL  ") + name + ": " + text)
    if not ok:
        fails.append(name)


# ---------------------------------------------------------------- values (sheets/102-interlock.yaml)
R207 = 1000.0                        # 1 kohm, 1 % UNI-ROYAL 0603WAF1001T5E (C21190)
R_LO, R_HI = R207 * 0.99, R207 * 1.01
RPD = 100e3 / 2 * 1.01               # R201 || R202, 100 kohm 1 % each: 50 kohm, upper end
RPD_LO = 100e3 / 2 * 0.99
# ---------------------------------------------------------------- supplies (as A_calcs.py / D_holdoff.py take them)
VDD_MIN, VDD_MAX = 3.135, 3.6        # +3V3 -5 % (owner B's regulator tolerance replaces it); DS12110 Rev 11 range upper end
# DS12110 Rev 11 Table 51: CMOS port at 8 mA: VOH min VDD - 0.4 V, VOL max 0.4 V. The load here is microamperes, so these are bounds.
VOH_MIN = lambda vdd: vdd - 0.4
VOL_MAX = 0.4
# Nexperia 74AHC1G17 / 74AHCT1G17 Rev. 5, Table 8 (AHCT): VT+ <= 2.0 V and VT- >= 0.5 V at VCC 4.5 V.
VT_PLUS_MAX, VT_MINUS_MIN = 2.0, 0.5
# Clamp current: the nearest rating the maker states for the input protection is IIK 20 mA (stated for VI < -0.5 V);
# the sheet states nothing for an input above an unpowered VCC, so 20 mA is the comparison, not a read limit for this case.
IIK = 20e-3
VF_CLAMP = 0.7                       # silicon input clamp diode forward drop taken, as D_holdoff.py takes it (unsourced)

# ---------------------------------------------------------------- 1. +5V absent, +3V3 present (F2b)
print("== +5V absent, +3V3 present: the buffer's input clamp to its unpowered VCC")
for vcc in (0.0, 1.0):
    i = (VDD_MAX - VF_CLAMP - vcc) / R_LO
    print("   VDD %.1f V, VCC rail held at %.1f V by its loads, R207 %.0f ohm (-1 %%): clamp current %.2f mA" % (VDD_MAX, vcc, R_LO, i * 1e3))
i_max = (VDD_MAX - VF_CLAMP) / R_LO
i_bound = VDD_MAX / R_LO             # no forward drop at all, output resistance zero: an upper bound whatever the diode
check("clamp current, +5V absent", i_max < IIK, "worst %.2f mA vs 20 mA: x%.1f under (without the %.1f V diode drop, bounded at %.2f mA: x%.1f under)"
      % (i_max * 1e3, IIK / i_max, VF_CLAMP, i_bound * 1e3, IIK / i_bound))
print("   without R207 the current is limited by the controller's output resistance alone (unsourced), so nothing here bounds it")

# ---------------------------------------------------------------- 2. logic levels at the buffer input
print("== levels at U201 pin 2 (POL_IN)")
vin_high = VOH_MIN(VDD_MIN) * RPD_LO / (RPD_LO + R_HI)
check("input high clears VT+", vin_high > VT_PLUS_MAX, "%.3f V (VOH min %.3f V x 49.5 kohm / (49.5 kohm + %.0f ohm)) vs VT+ max %.1f V: margin %.2f V"
      % (vin_high, VOH_MIN(VDD_MIN), R_HI, VT_PLUS_MAX, vin_high - VT_PLUS_MAX))
check("input low under VT-", VOL_MAX < VT_MINUS_MIN, "at most %.1f V (VOL max, the divider only lowers it) vs VT- min %.1f V" % (VOL_MAX, VT_MINUS_MIN))
print("   reset strap: controller pin floating or low, input held by R201 || R202 (%.1f kohm); output high drives at most %.1f V / %.2f kohm = %.0f uA"
      % (RPD_LO / 1e3, VDD_MAX, (RPD_LO + R_LO) / 1e3, VDD_MAX / (RPD_LO + R_LO) * 1e6))

# ---------------------------------------------------------------- 3. delay against the interlock's timing
print("== added delay")
# Input capacitance: the sheet's Table 8 CI is not read here, so 50 pF is taken as a generous bound for the buffer pin (10 pF assumed),
# the track, the test pad and the pull-down pads. A step of the controller's output drives R207 into C with the pull-downs to ground.
C = 50e-12
rth = R_HI * RPD / (R_HI + RPD)
tau = rth * C
vf = VOH_MIN(VDD_MIN) * RPD / (RPD + R_HI)       # settled input level for the worst high
vf_lo = vf
t_rise = tau * math.log(vf_lo / (vf_lo - VT_PLUS_MAX))
v_start = vf
t_fall = tau * math.log(v_start / VT_MINUS_MIN)
print("   Thevenin %.0f ohm x %.0f pF: tau %.1f ns; rising edge reaches VT+ max after %.1f ns; falling edge reaches VT- min after %.1f ns"
      % (rth, C * 1e12, tau * 1e9, t_rise * 1e9, t_fall * 1e9))
worst_delay = max(t_rise, t_fall)
asym = abs(t_rise - t_fall)
check("delay against the minimum phase width", worst_delay < 25e-6 / 100, "worst edge delay %.1f ns is %.2f %% of the 25 us minimum phase width; the high and low phases differ by at most %.1f ns"
      % (worst_delay * 1e9, worst_delay / 25e-6 * 100, asym * 1e9))
check("delay against the removal budget", worst_delay < 100e-3 / 1e4, "%.1f ns against the 100 ms removal budget: %.1e of it (a pure delay of the first and every edge; the refresh interval and the edge pump downstream are unchanged)"
      % (worst_delay * 1e9, worst_delay / 100e-3))

print("\nSUMMARY: %d failing %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
