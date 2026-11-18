#!/usr/bin/env python3
"""The interlock's input network: the controller's proof-of-life output (POL_OUT, PC7) through the series resistor R207 to the
inverting buffer U201's input (POL_IN), with the strap R201 (27 kohm to +5V) over R202 (82 kohm to ground) that leaves POL_IN high,
and so the buffer output low, whenever the controller leaves the pin undriven.

It answers: the levels POL_IN takes in each controller state against the buffer's thresholds; the most the strap puts on the
controller pin (DS12110 Table 109) in each supply state; what the controller's output can push into the buffer's input and the
unpowered +5V net with +5V absent (F2b); the edge delay.

Run:  python3 -I A_pol_series.py > A_pol_series.log     (from this folder; exit 0 when no check fails)

Every constant names its source on its line. Datasheets: STM32H743 DS12110 Rev 11; Texas Instruments SN74AHCT1G14 SCLS322P (June 2013).
"""
import math
import sys

fails = []


def check(name, ok, text):
    print(("PASS  " if ok else "FAIL  ") + name + ": " + text)
    if not ok:
        fails.append(name)


# ---------------------------------------------------------------- values (sheets/102-interlock.yaml), 1 % parts
TOL = 0.01
R207, RA, RB = 1000.0, 27e3, 82e3           # R207 1 kohm C21190; R201 27 kohm to +5V C22967; R202 82 kohm to ground C23254
R207_LO, R207_HI = R207 * (1 - TOL), R207 * (1 + TOL)
RA_LO, RA_HI = RA * (1 - TOL), RA * (1 + TOL)
RB_LO, RB_HI = RB * (1 - TOL), RB * (1 + TOL)
# ---------------------------------------------------------------- supplies
V5_MIN, V5_MAX = 4.75, 5.25                 # the proof's +5V band (circuit-proof.md): module 5 V +-2.5 %, 5.25 V the brief's rail-high case, USB VBUS at most 5.25 V
V5_MODULE_MAX = 5.125                       # IRM-20-SPEC 2025-11-21, 5 V +2.5 %
V5_TRIP = 6.75                              # the module's over-voltage trip, upper end (IRM-20-SPEC)
VDD_MIN, VDD_MAX = 3.135, 3.6               # +3V3 -5 % ; DS12110 Rev 11 range upper end
# ---------------------------------------------------------------- DS12110 Rev 11
VOH_MIN = lambda vdd: vdd - 0.4             # Tables 148/51: VOH min VDD - 0.4 V at IIO = -8 mA
R_OL = 0.4 / 8e-3                           # VOL max 0.4 V at IIO = 8 mA, taken as 50 ohm: the drop of a driver is convex in its current through the origin, so 0.4 V / 8 mA bounds it at any smaller current (the argument the output-resistance figures of A_models.inc use)
ILKG_PIN = 1.5e-6                           # Table 147/50: FT_xx input leakage 1500 nA max for Max(VDDXXX) < VIN <= 5.5 V
PIN_MAX_VDD_ABSENT = 4.0                    # Table 109: VIN max Min(Min(VDD,VDDA,VDD33USB,VBAT) + 4.0, 6 V): 4.0 V with VDD absent
PIN_MAX_VDD_UP = 6.0                        # ... 6.0 V for every supply of 2.0 V and above
# ---------------------------------------------------------------- Texas Instruments SN74AHCT1G14, SCLS322P, Electrical characteristics
VT_PLUS_MAX, VT_MINUS_MIN = 2.0, 0.5        # VT+ 2.0 V max, VT- 0.5 V min at VCC 4.5 V (-40..85 C); 5.5 V: VT- 0.6 V min
II_MAX = 1e-6                               # II +-1 uA max, VI = 5.5 V or GND, VCC 0 V to 5.5 V, -40..85 C
IIK = 20e-3                                 # absolute maximum input clamp current, VI < 0 (not applicable above ground)
VI_ABS = 7.0                                # absolute maximum input voltage -0.5..7 V

rth = lambda ra, rb: ra * rb / (ra + rb)
k_hi = RB_HI / (RB_HI + RA_LO)
k_lo = RB_LO / (RB_LO + RA_HI)

# ---------------------------------------------------------------- 1. levels at POL_IN (U201 pin 2) in each controller state
print("== levels at POL_IN against VT+ max %.1f V and VT- min %.1f V" % (VT_PLUS_MAX, VT_MINUS_MIN))
print("   strap divider ratio %.4f to %.4f of +5V; Thevenin resistance %.2f kohm" % (k_lo, k_hi, rth(RA, RB) / 1e3))
# pin undriven (reset, 3V3 absent, firmware not yet driving): the strap alone, less the pin's and the buffer input's leakage
v_idle = V5_MIN * k_lo - (ILKG_PIN + II_MAX) * rth(RA_HI, RB_LO)
check("idle high (pin undriven)", v_idle > VT_PLUS_MAX, "%.3f V (+5V %.2f V x %.4f, less %.1f uA of pin and buffer leakage through %.2f kohm) vs VT+ max %.1f V: margin %.2f V"
      % (v_idle, V5_MIN, k_lo, (ILKG_PIN + II_MAX) * 1e6, rth(RA_HI, RB_LO) / 1e3, VT_PLUS_MAX, v_idle - VT_PLUS_MAX))
# pin driven high: the pin holds POL_IN at its own level; the strap, at most a pull-up toward its Thevenin level, only lifts it
v_drv_hi = VOH_MIN(VDD_MIN)
check("driven high", v_drv_hi > VT_PLUS_MAX, "at least %.3f V (VOH min VDD - 0.4 V at VDD %.3f V; the strap pulls toward %.2f V or more, so only lifts it) vs VT+ max %.1f V: margin %.2f V"
      % (v_drv_hi, VDD_MIN, V5_MIN * k_lo, VT_PLUS_MAX, v_drv_hi - VT_PLUS_MAX))
# pin driven low: the strap's Thevenin source drives current through R207 and the pin's low-level resistance
vth_hi = V5_MAX * k_hi
v_drv_lo = vth_hi * (R207_HI + R_OL) / (R207_HI + R_OL + rth(RA_LO, RB_HI))
i_lo = vth_hi / (rth(RA_LO, RB_HI) + R207_HI + R_OL)
v_drv_lo_unscaled = i_lo * R207_HI + 0.4
check("driven low", v_drv_lo < VT_MINUS_MIN, "at most %.3f V (+5V %.2f V, strap Thevenin %.2f V and %.2f kohm into R207 + %.0f ohm; pin sinks %.0f uA) vs VT- min %.1f V: margin %.2f V (the pin's VOL taken unscaled at 0.4 V would give %.3f V: that is not used, 0.4 V is the figure at 8 mA, the pin sinks %.2f mA)"
      % (v_drv_lo, V5_MAX, vth_hi, rth(RA_LO, RB_HI) / 1e3, R_OL, i_lo * 1e6, VT_MINUS_MIN, VT_MINUS_MIN - v_drv_lo, v_drv_lo_unscaled, i_lo * 1e3))
check("controller pin current", i_lo < 20e-3, "%.0f uA sunk by the pin driving low vs the pin's 20 mA continuous maximum (DS12110 Table 110)" % (i_lo * 1e6))
print("   strap current from +5V: %.1f uA at %.2f V (adds to the supply budget)" % (V5_MAX / (RA_LO + RB_LO) * 1e6, V5_MAX))

# ---------------------------------------------------------------- 2. what the strap puts on the controller pin, pin undriven
print("== controller pin PC7 voltage with the pin undriven (DS12110 Table 109)")
for label, v5 in (("IRM-20 5 V +2.5 %", V5_MODULE_MAX), ("+5V band top / USB VBUS maximum", V5_MAX)):
    v = v5 * k_hi - ILKG_PIN * 0  # leakage only lowers the level; not credited
    check("pin with VDD absent, %s" % label, v <= PIN_MAX_VDD_ABSENT, "%.3f V (+5V %.3f V x %.4f) vs %.1f V (VDD absent): margin %.3f V" % (v, v5, k_hi, PIN_MAX_VDD_ABSENT, PIN_MAX_VDD_ABSENT - v))
v_trip = V5_TRIP * k_hi
check("pin at the module's over-voltage trip, VDD present", v_trip <= PIN_MAX_VDD_UP, "%.2f V (+5V %.2f V x %.4f) vs %.1f V (VDD 2.0 V and above): margin %.2f V; the double fault of the trip with VDD absent (%.2f V against 4.0 V) is not covered, the same exclusion the wall-board inputs R764 R765 carry"
      % (v_trip, V5_TRIP, k_hi, PIN_MAX_VDD_UP, PIN_MAX_VDD_UP - v_trip, v_trip))
v_cable = 10.3 * k_hi
print("   cable-position plug-in surge: D402's 10.3 V clamp level x %.4f = %.2f V against %.1f V (a bench state, mains off, accepted for U201 and U791 in open-items.md (b); PC7 and the wall-board inputs PE15 PD7 ride the same exposure and are not named there)" % (k_hi, v_cable, PIN_MAX_VDD_UP))
print("   pin leakage with the pin undriven and VIN above VDD: %.1f uA max (Table 147) x %.2f kohm = %.0f mV shift of the level, not credited above" % (ILKG_PIN * 1e6, rth(RA_HI, RB_HI) / 1e3, ILKG_PIN * rth(RA_HI, RB_HI) * 1e3))
print("   driven high, the strap's open-circuit level %.2f V to %.2f V is above the pin's own %.2f V: %.0f uA flows into the pin's high-side driver (a level under VIN max, no positive injection below it, Table 110 note 3)"
      % (V5_MIN * k_lo, vth_hi, VDD_MAX, max(0.0, (vth_hi - VDD_MAX) / (rth(RA_LO, RB_HI) + R207_LO)) * 1e6))

# ---------------------------------------------------------------- 3. +5V absent, +3V3 present (F2b)
print("== +5V absent, +3V3 present: the controller's output driving high into the unpowered buffer and the +5V net through the strap")
i_in = VDD_MAX / (R207_LO + RB_LO)
i_up = VDD_MAX / (R207_LO + RA_LO)
check("current out of the pin", i_in + i_up < 20e-3, "at most %.0f uA to ground through R202 plus %.0f uA toward the +5V net through R201 at %.1f V: %.0f uA vs the pin's 20 mA" % (i_in * 1e6, i_up * 1e6, VDD_MAX, (i_in + i_up) * 1e6))
check("buffer input with VCC = 0", II_MAX < 1e-3, "II +-%.0f uA max at VI = 5.5 V with VCC 0 V to 5.5 V (SCLS322P Electrical characteristics), the input sits at %.2f V at most; the 20 mA IIK is for VI < 0 and not the limit here" % (II_MAX * 1e6, VDD_MAX))
print("   the +5V net can be lifted by at most the pin's level, %.1f V, through %.1f kohm; the coil sees that across itself and two FETs whose gates are at ground unless U201 pumps them (outside the sheet's 4.5 V minimum VCC); 70 C pick-up is 4.20 V (+20 %% of 3.50 V), 25 C 3.50 V: %.1f V is under the 70 C figure and not under the 25 C one with the FETs fully on" % (VDD_MAX, (R207_LO + RA_LO) / 1e3, VDD_MAX))

# ---------------------------------------------------------------- 4. delay against the interlock's timing
print("== added edge delay (pin driving through R207 into the input capacitance)")
C = 50e-12                                   # a generous bound for the buffer pin (2 pF typical, 10 pF max, SCLS322P Ci), the track and the pads, not a read capacitance
v_hi_src = VOH_MIN(VDD_MIN)
rpar = rth(R207_HI, rth(RA_HI, RB_LO))       # source resistance of the node with the strap in parallel, upper ends
def rc_to(v0, vf, vt, r):
    return r * C * math.log((vf - v0) / (vf - vt))
# rising: pin goes high from the driven-low state; node starts at v_drv_lo, settles toward (pin level and strap in parallel)
vf_rise = (v_hi_src / R207_HI + V5_MIN * k_lo / rth(RA_HI, RB_LO)) / (1 / R207_HI + 1 / rth(RA_HI, RB_LO))
t_rise = rc_to(v_drv_lo, vf_rise, VT_PLUS_MAX, rpar)
# falling: pin goes low from the driven-high state; node starts at v_hi_src and settles toward v_drv_lo through R207 + pin
vf_fall = v_drv_lo
t_fall = rpar * C * math.log((v_hi_src - vf_fall) / (VT_MINUS_MIN - vf_fall))
worst = max(t_rise, t_fall)
print("   node source resistance %.0f ohm x %.0f pF: tau %.1f ns; rising edge reaches VT+ max after %.1f ns; falling edge reaches VT- min after %.1f ns" % (rpar, C * 1e12, rpar * C * 1e9, t_rise * 1e9, t_fall * 1e9))
check("delay against the minimum phase width", worst < 25e-6 / 100, "worst edge delay %.1f ns is %.2f %% of the 25 us minimum phase width; the two phases differ by at most %.1f ns" % (worst * 1e9, worst / 25e-6 * 100, abs(t_rise - t_fall) * 1e9))
check("delay against the removal budget", worst < 100e-3 / 1e4, "%.1f ns against the 100 ms removal budget: %.1e of it (a delay of the first and every edge; the refresh interval and the edge pump downstream are unchanged)" % (worst * 1e9, worst / 100e-3))

print("\nSUMMARY: %d failing %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
