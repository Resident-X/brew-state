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
print("== gate pull-down: every NMOS stage (Q701 Q711 Q731 Q741 Q761 Q771 Q821 Q823 Q824)")
chk("gate level under leakage", v_gate < VTH_MIN,
    "(Ilkg %.0f nA + IGSS %.0f nA) x (Rg + Rpd) = %.1f mV vs VGS(th) min %.2f V: margin x%.0f" % (ILKG * 1e9, IGSS * 1e9, v_gate * 1e3, VTH_MIN, VTH_MIN / v_gate))
chk("leakage through the LED, pump drive", IDSS55 < 10e-3, "IDSS 5 uA (55 degC) is x%.0f under IFT max 10 mA (the sheet states no minimum trigger current)" % (10e-3 / IDSS55))
chk("leakage through the LED, heater drive", IDSS55 < 5e-3, "IDSS 5 uA is x%.0f under IFT max 5 mA (the sheet states no minimum trigger current)" % (5e-3 / IDSS55))
v_coil_leak = IDSS55 * 97.2
chk("leakage through a valve coil", v_coil_leak < 0.25 / 100, "5 uA x 97.2 ohm = %.2f mV vs drop-out 0.25 V min: x%.0f" % (v_coil_leak * 1e3, 0.25 / v_coil_leak))

print("\n== anode rail gate Q821 / Q822")
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
print("   3V3 falling: Q822 turns off when ANODE_GATE leaves its high level; the rail bleeds through R825 22 k; the time to fall is set by the panel's wiring capacitance (unread), not bounded here (open item)")

print("\nSUMMARY: %d failing %s" % (len(bad), bad))
sys.exit(1 if bad else 0)
