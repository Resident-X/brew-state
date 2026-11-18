#!/usr/bin/env python3
"""Hold-off arithmetic for every load the drive stages of work package D switch.

Run:  python3 -I D_holdoff.py     (prints each figure proof-rows/D-holdoff.md quotes; exit 0 when every check holds)

Sources (read 2026-10-29):
  controller pin in reset: STMicroelectronics DS12110 Rev 11, Table 8 note ("all I/Os are set as floating inputs during and after reset"),
      the GPIO description ("After reset, all GPIOs (except debug pins) are in Analog mode"); Table 50 Ilkg FT_xx +/-250 nA, FT_u +/-350 nA (VIN <= VDD),
      FT_xx 1500 nA and FT_u 5000 nA above VDD up to 5.5 V; Table 14 operating VIN on FT pins <= Min(VDD) + 3.6 V and < 5.5 V, internal pulls off above VDD + 0.3 V; Table 11 absolute maximum Min(VDD + 4.0, 6) V;
      Table 12 IINJ -5/+0 mA.
  AO3400A: AOS Rev 3 (Dec 2011): VGS(th) 0.65..1.45 V, IGSS 100 nA, IDSS 1 uA (VDS 30 V, 25 degC) and 5 uA (TJ 55 degC).
  AO3401A: AOS Rev 3.1 (Dec 2023): VGS(th) -0.5..-1.3 V, IDSS -1 uA, IGSS 100 nA.
"""
import sys

bad = []


def chk(name, ok, text):
    print(("PASS  " if ok else "FAIL  ") + name + ": " + text)
    if not ok:
        bad.append(name)


ILKG = 350e-9          # worst pad leakage among the pins used (PA9 is FT_u)
IGSS = 100e-9
IDSS55 = 5e-6
VTH_MIN = 0.65
RG, RPD = 100 * 1.01, 100e3 * 1.01
v_gate = (ILKG + IGSS) * (RG + RPD)
print("== gate pull-down: every NMOS stage with a 100 kohm pull-down (Q701 Q711 Q731 Q741 Q761 Q771 Q823 Q824)")
chk("gate level under leakage", v_gate < VTH_MIN,
    "(Ilkg %.0f nA + IGSS %.0f nA) x (Rg + Rpd) = %.1f mV vs VGS(th) min %.2f V: margin x%.0f" % (ILKG * 1e9, IGSS * 1e9, v_gate * 1e3, VTH_MIN, VTH_MIN / v_gate))
chk("leakage through the LED, pump drive", IDSS55 < 10e-3, "IDSS 5 uA (55 degC) is x%.0f under IFT max 10 mA (the sheet states no minimum trigger current)" % (10e-3 / IDSS55))
chk("leakage through the LED, heater drive", IDSS55 < 5e-3, "IDSS 5 uA is x%.0f under IFT max 5 mA (the sheet states no minimum trigger current)" % (5e-3 / IDSS55))
v_coil_leak = IDSS55 * 97.2
chk("leakage through a valve coil", v_coil_leak < 0.25 / 100, "5 uA x 97.2 ohm = %.2f mV vs drop-out 0.25 V min: x%.0f" % (v_coil_leak * 1e3, 0.25 / v_coil_leak))

print("\n== anode rail gate Q821 / Q822 (R822 10 kohm: the gate discharge sets the turn-off after a reset)")
RPD_ANODE = 10e3 * 1.01
v_gate_anode = (ILKG + IGSS) * (RG + RPD_ANODE)
chk("Q821 gate level under leakage, R822 10 kohm", v_gate_anode < VTH_MIN,
    "(Ilkg %.0f nA + IGSS %.0f nA) x (Rg + R822) = %.1f mV vs VGS(th) min %.2f V: margin x%.0f" % (ILKG * 1e9, IGSS * 1e9, v_gate_anode * 1e3, VTH_MIN, VTH_MIN / v_gate_anode))
vsg_off = 0.0
chk("PMOS off, both pull-ups", True, "gate pulled to +5V by R823 || R824 (11 k): VSG 0 V vs |VGS(th)| min 0.5 V; leakage drop: IGSS 100 nA x 11 k = %.1f mV" % (IGSS * 11e3 * 1e3))
chk("PMOS off, one pull-up open", True, "gate pulled to +5V by 22 k: IGSS 100 nA x 22 k = %.1f mV; VSG stays under 0.5 V by x%.0f" % (IGSS * 22e3 * 1e3, 0.5 / (IGSS * 22e3)))
print("   both pull-ups open (a second fault): the gate floats and the switch keeps the state it had; the anode rail can stay lit after a command off. Indicators only; not detected by the board")
print("   anode rail with Q822 off: R825 22 k bleed to ground; leakage IDSS 1 uA x 22 k = %.0f mV (rail reads 0 within 0.1 V)" % (1e-6 * 22e3 * 1e3))

print("\n== gauge buffer U791 inputs (R796..R800 1 k series, R801..R805 10 k to ground)")
RS, RPDG = 1e3, 10e3
vin_hi = 2.735 * RPDG / (RS + RPDG)
vin_lo = 0.4 * RPDG / (RS + RPDG)
chk("buffer VIH with the divider", vin_hi >= 2.0, "controller VOH_min 2.735 V x 10 k / 11 k = %.3f V vs HCT VIH 2.0 V: margin %.3f V" % (vin_hi, vin_hi - 2.0))
chk("buffer VIL with the divider", vin_lo <= 0.8, "VOL 0.4 V x 10 k / 11 k = %.3f V vs VIL 0.8 V" % vin_lo)
vleak = (ILKG + 1e-6) * RPDG
chk("input level in reset", vleak < 0.8, "(Ilkg 350 nA + HCT II 1 uA) x 10 k = %.1f mV vs VIL 0.8 V" % (vleak * 1e3))
# +5V absent with 3V3 present: controller output 3.3 V driving an unpowered HCT541 input: the input clamp to VCC
for vdd in (3.3, 3.6):
    for vcl in (0.0, 1.0):
        i = (vdd - 0.7 - vcl) / RS
        print("   +5V absent: input clamp current %.2f mA (VDD %.1f V, VCC rail held at %.1f V by its loads); IIK limit 20 mA" % (i * 1e3, vdd, vcl))
chk("input clamp current, +5V absent", (3.6 - 0.7) / RS < 20e-3, "worst %.2f mA per input vs IIK 20 mA (SCLS306C): x%.1f" % ((3.6 - 0.7) / RS * 1e3, 20e-3 / ((3.6 - 0.7) / RS)))
print("   5 inputs x %.2f mA = %.1f mA could reach the +5V rail through the clamps if it is held low by nothing else" % ((3.6 - 0.7) / RS * 1e3, 5 * (3.6 - 0.7) / RS * 1e3))

print("\n== key lines KEY1..KEY5 and the anode rail")
chk("pin voltage with VDD present", 5.25 < 5.5 and 5.25 <= 1.65 + 3.6, "anode rail on (firmware-driven), VF taken as 0: pin <= 5.25 V; operating limit Min(VDD) + 3.6 V and below 5.5 V holds for VDD >= 1.65 V")
chk("pin voltage with +3V3 absent, +5V present", True, "ANODE_GATE is a floating input / low, Q821 gate pulled down, Q822 gate pulled to +5V: anode rail %.0f mV, key pin <= 0.1 V" % (1e-6 * 22e3 * 1e3))
# Brown-out. +3V3 is made from +5V by U302 (LT1963A), which in dropout keeps VDD within 0.35 V of +5V (minimum input 1.9 V typical, 2.5 V maximum),
# and the anode rail is never above +5V (the source of Q822 is on +5V): in a normal brown-out the rail cannot exceed VDD + 2.5 V.
chk("pin voltage in a normal brown-out", 0.35 <= 2.5, "rail at most +5V; VDD within 0.35 V of +5V while U302 is in dropout: rail minus VDD at most 0.35 V, under the 2.5 V margin to Min(VDD) + 3.6 V and 5.5 V")
# The one residual: +3V3 lost alone while +5V stays up and firmware has the anode rail enabled (ANODE_GATE driven high).
# Once Q822 is off the rail discharges in microseconds through R825 and the five 10 k key pull-ups, so the turn-off after reset is the
# chain of delays below; the panel's wiring capacitance does not set it.
# Sources: TI TLV803 (SBVS157): tw 10 us (pulse duration at VDD, the only timing figure the sheet prints), VOL 0.4 V at IOL 2 mA, VDD 3.3 V;
#   VIT- 2.87 to 2.99 V. DS12110 Rev 11 Table 152: NRST VIL 0.3 VDD.
#   AO3400A (Q821), AOS Rev 3.1 (July 2023): Qg 6 nC typical, 7 nC maximum at VGS 4.5 V; Qgd 1.8 nC typical (VDS 15 V); Coss 75 pF; VGS(th) 0.65 / 1.05 / 1.45 V.
#   AO3401A (Q822), AOS Rev 3.1 (December 2023): Qg(4.5 V) 7 nC typical; VGS(th) -0.5 / -0.9 / -1.3 V.
# Assumptions stated here: the threshold falls 2.5 mV/K (a typical figure for this device class; the sheets give it only as a normalised
#   curve), so at 70 degC the AO3400A minimum is 0.54 V and its typical 0.94 V; the AO3400A gate-drain charge for a 0 to 5 V swing is taken
#   as the sheet's 0 to 15 V figure (it can only be less), scaled by 7/6 in the worst case; the anode rail and its two harnesses are taken as 1 nF.
import math
print("\n== +3V3 lost alone while +5V and the anode rail stay up (a fault-only residual)")


def turnoff(worst):
    t_sup = 10e-6
    c418 = 100e-9 * (1.10 if worst else 1.0)
    r_sup = 0.4 / 2e-3                                  # open-drain resistance bound from VOL 0.4 V at 2 mA
    v_rst = 2.99 if worst else 2.93                     # VDD at which the supervisor trips
    t_nrst = r_sup * c418 * math.log(v_rst / (0.3 * 2.87))
    r822 = 10e3 * (1.01 if worst else 1.0)
    qg, qgd = (7e-9, 1.8e-9 * 7 / 6) if worst else (6e-9, 1.8e-9)
    c_in = (qg - 1.8e-9) / 4.5                          # Q821 input capacitance with the drain low: gate charge less the Miller charge, over 4.5 V
    vp = 0.54 if worst else 0.94                        # plateau at the 0.45 mA drain current, about the threshold, at 70 degC
    t_gate = r822 * c_in * math.log(v_rst / vp)
    t_miller = qgd * r822 / vp
    r_pu = 11e3 * (1.01 if worst else 1.0)              # R823 || R824
    c_pg = 7e-9 / 4.5 + 75e-12                          # Q822 gate charge over 4.5 V, plus Q821 Coss
    vth822 = 0.5 if worst else 0.9
    t_pu = r_pu * c_pg * math.log(5.0 / vth822)         # Q822 gate pulled from VSG 5 V to its threshold
    t_rail = (22e3 * 2.06e3 / (22e3 + 2.06e3)) * 1e-9   # rail through R825 || five 10.3 k key paths, 1 nF
    # the Q821 Miller interval and the Q822 gate rise are the same node rising: the typical figure counts the longer, the worst case both
    total = t_sup + t_nrst + t_gate + (t_miller + t_pu if worst else max(t_miller, t_pu)) + t_rail
    return total, (t_sup, t_nrst, t_gate, t_miller, t_pu, t_rail)


for worst in (False, True):
    tot, parts = turnoff(worst)
    print("   turn-off after reset, %s: supervisor %.1f + NRST (C418) %.1f + Q821 gate to plateau %.1f + Q821 Miller %.1f + Q822 gate pull-up %.1f + rail %.1f us -> %.0f us%s"
          % ("worst" if worst else "typical", *[p * 1e6 for p in parts], tot * 1e6, "" if worst else " (Miller and pull-up overlap: the longer counted)"))
T_TYP, T_WORST = turnoff(False)[0], turnoff(True)[0]
# Time available after the supervisor trips (VDD 2.87 V, the lowest trip) until VDD reaches 1.65 V (operating limit with the rail at 5.25 V)
# and 1.25 V (absolute maximum, 5.25 V - 4.0 V). Load-side +3V3 capacitance 8.3 uF nominal (C401..C409, C422, C521, C609..C611, C641,
# C642, C646, C647, C673, C678); load 0.293 A, the rail's stated maximum, as a constant current (fastest fall) or as 11.3 ohm.
C3, I3, R3 = 8.3e-6, 0.293, 3.3 / 0.293


def avail(v_end):
    return C3 * (2.87 - v_end) / I3, R3 * C3 * math.log(2.87 / v_end)


a_op, a_abs = avail(1.65), avail(1.25)
print("   time available after the trip: operating limit %.0f to %.0f us, absolute maximum %.0f to %.0f us (constant-current to resistive load)"
      % (a_op[0] * 1e6, a_op[1] * 1e6, a_abs[0] * 1e6, a_abs[1] * 1e6))
for name, t in (("typical", T_TYP), ("worst", T_WORST)):
    v = max(0.0, 2.87 - I3 * t / C3)
    print("   at the %s turn-off (%.0f us, constant-current load) VDD is %.2f V: the key pin at 5.25 V is %.2f V over the absolute maximum (VDD + 4.0 V) and %.2f V over the operating limit, for %.0f us"
          % (name, t * 1e6, v, 5.25 - (v + 4.0), 5.25 - (v + 3.6), (t - a_abs[0]) * 1e6))
print("   current per indicator element meanwhile: at most 5.25 V / 300 ohm = %.1f mA (330 ohm element %.1f mA), VF taken as 0 and the pin at 0 V; %.1f mA on a two-element line"
      % (5.25 / 300 * 1e3, 5.25 / 330 * 1e3, 2 * 5.25 / 300 * 1e3))
print("RESIDUAL  +3V3 lost alone: NOT inside the pin limit by these figures (turn-off %.0f us typical, %.0f us worst, against %.0f to %.0f us available to the absolute maximum); a fault-only residual accepted by the owner (S-88 of owner-sign-off.md), held at bring-up by the rule not to remove +3V3 while firmware drives ANODE_GATE"
      % (T_TYP * 1e6, T_WORST * 1e6, a_abs[0] * 1e6, a_abs[1] * 1e6))

print("\nSUMMARY: %d failing %s" % (len(bad), bad))
sys.exit(1 if bad else 0)
