"""USB cable power (C15): bench-state budget, drop, regulator input, source selection, back-feed (the selector alone), unit-load and inrush rules, clamp residue.

Sources (each read 2026-10-29; figures are the maker's maxima unless the row says typical):
  USB 2.0     Universal Serial Bus Specification Revision 2.0 (usb.org, usb_20_20240927 package, usb_20.pdf): 7.2.1 (unit load = 100 mA,
              "No device shall supply (source) current on VBUS at its upstream facing port at any time", one unit load until configured),
              7.2.1.3 (low-power function operates down to 4.40 V at the plug end of the cable), 7.2.2 (functions drawing more than one
              unit load operate with a 4.75 V minimum at the connector end of their upstream cable; 125 mV cable drop), 7.2.4.1 (the
              largest load a cable end may see is 10 uF in parallel with 44 ohm; more bypass capacitance needs VBUS surge current limiting).
  LT1963A-3.3  Analog Devices LT1963A series, 1963aff (LCSC C459918, replacing the AP7361C-33ER-13): output 3.200 to 3.400 V, dropout 0.35 V
              maximum at 500 mA over temperature, GND pin current 1.5 mA at no load, 5.5 mA at 100 mA, 25 mA at 500 mA (maxima), IN +/-20 V
              absolute maximum, pins 1 IN, 2 GND (tab), 3 OUT; output capacitance two 22 uF X5R (C304, C305).
  MF-MSMF050-2 Bourns MF-MSMF series datasheet (bourns.com), LCSC C17313: hold 0.50 A, trip 1.00 A, Vmax 15 V, Imax 100 A, Rmin 0.15 ohm,
              R1max 1.00 ohm, 8.0 A trips within 0.15 s at 23 degC; hold current 0.44 A at 40 degC, 0.33 A at 70 degC (derating chart).
  SMF6.0A     Littelfuse SMF series, LCSC C207260: VR 6.0 V, VBR 6.67 to 7.37 V, IR 400 uA at VR, Ipp 19.4 A, VC 10.3 V at Ipp.
  USBLC6-2SC6 STMicroelectronics DS4260 Rev 7: IRM 150 nA maximum at VRM 5.25 V, VBR 6 V minimum (VBUS to GND), VF 1.1 V at 10 mA,
              2.1 example Rd 0.5 ohm, VT 1.1 V, VBR 6.1 V, Rd_TRANSIL 0.5 ohm, Ip = 8 kV / 330 ohm = 24 A.
  SN74HCT541  Texas Instruments: VCC absolute maximum 7 V, recommended 4.5 to 5.5 V, ICC 80 uA maximum, increase 3 mA maximum for each input at a TTL level.
  Loads       sheets' bring-up/*.yaml rail_loads; DS12110 Table 119 through b_regulator_thermal.py (200 MHz VOS3: 233 mA with peripherals
              enabled at 105 degC junction, 116 mA at 25 degC, 71 mA with peripherals disabled at 25 degC).
  Indicators  sheet 740: six indicator lines, each 300 ohm from the gated anode rail (the panel's LED forward voltage is not read here, so it is taken as 0 V).
"""
# ---- bench state ----------------------------------------------------------------------
# Bench state (owner, 2026-10-29): only the controller, its regulators, the indicators it carries and the debug and USB parts are
# powered; no sensor head, gauge, load or mains is connected. Bench air up to 40 degC (the fuse derating figure below).
TA_BENCH, THJA, VDD = 40.0, 45.0, 3.399
T119 = {  # (fCPU MHz, scale, peripherals): maximum IDD in mA at Tj 25 / 85 degC (DS12110 Rev 11 Table 119)
    "200 MHz VOS3 peripherals enabled": {25: 116, 85: 174},
    "200 MHz VOS3 peripherals disabled": {25: 71, 85: 121},
}

def idd(tab, tj):
    (a, ia), (b, ib) = sorted(tab.items())
    return ia + (ib - ia) * (tj - a) / (b - a)

def solve(tab):
    tj = TA_BENCH
    for _ in range(200):
        new = TA_BENCH + THJA * VDD * idd(tab, tj) / 1000.0
        if abs(new - tj) < 1e-9:
            break
        tj = new
    return idd(tab, tj) / 1000.0, tj

ctrl_run, tj_run = solve(T119["200 MHz VOS3 peripherals enabled"])
ctrl_low = idd(T119["200 MHz VOS3 peripherals disabled"], 25.0) / 1000.0     # lowest tabulated figure
other_3v3 = 0.293 - 0.240 - (0.006 + 0.0004)    # circuit-proof.md rail budget less the controller and the header-fed transducers
# regulator GND pin current, maximum over temperature (A -> A), linear between the maker's tabulated points
IGND = [(0.0, 1.5e-3), (0.001, 1.6e-3), (0.1, 5.5e-3), (0.5, 25e-3), (1.5, 120e-3)]


def ignd(i):
    for (a, ia), (b, ib) in zip(IGND, IGND[1:]):
        if i <= b:
            return ia + (ib - ia) * (i - a) / (b - a)
    return IGND[-1][1]


ldo_q = ignd(ctrl_run + other_3v3)
direct_5v = {"U201 supply": 0.0017, "U791 buffer (five inputs at the TTL-level increase, bound)": 0.0146, "HX711 x2": 0.0030}
indicators = 6 * 5.25 / 300.0
buzzer_bound = 0.053     # shorted-buzzer bound; held off by its gate pull-down and not sounded by loading or debugging firmware
excluded = {"interlock coil K201": 0.094, "valve coils": 0.108, "pump LED stages": 0.0589,
            "heater LED stages": 0.0589, "gauge drivers": 0.140}

fixed = other_3v3 + ldo_q + sum(direct_5v.values())
bench = ctrl_run + fixed + indicators
print("(a1) bench-state load from the cable, controller 200 MHz VOS3 peripherals enabled at TA %.0f degC (Tj %.1f degC): %.0f mA" % (TA_BENCH, tj_run, ctrl_run * 1000))
print("     other 3.3 V loads %.1f mA, regulator ground pin %.2f mA, U201 %.1f mA, U791 %.1f mA, HX711 x2 %.1f mA, six indicators on %.1f mA"
      % (other_3v3 * 1e3, ldo_q * 1e3, 1.7, 14.6, 3.0, indicators * 1e3))
print("     total %.4f A; with the buzzer sounding at its bound %.4f A; excluded (loads and their drivers, held off): %.3f A"
      % (bench, bench + buzzer_bound, sum(excluded.values())))
print("     against the 0.500 A of a high-power function (USB 2.0 7.2.1): margin %.3f A; against the fuse hold at 40 degC (0.44 A): margin %.3f A (%.0f %%)"
      % (0.5 - bench, 0.44 - bench, 100 * (0.44 - bench) / 0.44))

pre = ctrl_run + fixed
pre_floor = ctrl_low + fixed - direct_5v["U791 buffer (five inputs at the TTL-level increase, bound)"]
print("(a1b) before configuration (indicator rail off: its gate switch holds it off), controller as above: %.3f A; "
      "with the controller at the lowest tabulated figure (%.0f mA) and U791 at rest: %.3f A; the standard's one unit load is 0.100 A"
      % (pre, ctrl_low * 1e3, pre_floor))

# ---- (a2) drop and regulator --------------------------------------------------------
vbus_min, r1max, rmin = 4.75, 1.00, 0.15
v_usb = vbus_min - bench * r1max
print("(a2) VBUS minimum at the connector end 4.75 V (USB 2.0 7.2.2, functions above one unit load): drop %.3f V in F401 at R1max; F401 output goes straight to pin 3 of JP301 (a header contact's few milliohms are under 1 mV at this current)"
      % (bench * r1max))
print("     +5V on cable power %.3f V" % v_usb)
vout_max, dropout = 3.400, 0.35
need = vout_max + dropout
i33 = ctrl_run + other_3v3
print("     LT1963A-3.3 input must be at least %.3f V (%.3f + %.3f, the dropout maximum at 500 mA over temperature; the 3.3 V load is %.0f mA): margin %.3f V -> in regulation: %s"
      % (need, vout_max, dropout, i33 * 1e3, v_usb - need, v_usb >= need))
print("     fuse resistance at which the margin is gone: %.2f ohm (R1max %.2f ohm)" % ((vbus_min - need) / bench, r1max))
print("     if only the low-power figure of 4.40 V held at the connector (not the case for a board above one unit load): +5V %.3f V, margin %.3f V"
      % (4.40 - bench * r1max, 4.40 - bench * r1max - need))
print("     U791 sees %.3f V against its recommended 4.5 V minimum and 7 V absolute maximum; the gauge it drives is not connected in the bench state" % v_usb)

# ---- (c) which sources the selector can join -----------------------------------------
print("(c)  JP301 states (pin 1 +5V_MOD, pin 2 +5V, pin 3 USB_VBUS_F): one shorting jumper spans two adjacent pins and pin 2 takes one jumper")
for name, joins in (("no jumper", []), ("jumper on 1-2", [(1, 2)]), ("jumper on 2-3", [(2, 3)])):
    groups = {1: 1, 2: 2, 3: 3}
    for a, b in joins:
        for k in groups:
            if groups[k] == groups[b]:
                groups[k] = groups[a]
    print("     %-14s +5V joined to module: %-5s to cable path: %-5s module joined to cable path: %s"
          % (name, groups[2] == groups[1], groups[2] == groups[3], groups[1] == groups[3]))

# ---- (b) nothing from the board reaches the cable ---------------------------------------
# No series blocking element: the selector is the only part between the cable path and the module. A source joined to the cable
# path would have to be on pin 3 of JP301, and the only way to join pin 3 to any source is the jumper on 2-3, which leaves pin 1 open.
for name, joins in (("jumper on 1-2", [(1, 2)]), ("jumper on 2-3", [(2, 3)])):
    groups = {1: 1, 2: 2, 3: 3}
    for a, b in joins:
        for k in groups:
            if groups[k] == groups[b]:
                groups[k] = groups[a]
    module_to_cable = groups[1] == groups[3]
    rail_source_on_cable = groups[2] == groups[3] and groups[2] == groups[1]
    assert not module_to_cable and not rail_source_on_cable
print("(b)  no jumper position joins pin 1 (module) to pin 3 (cable path), checked above for every state; the board never sources current into the cable:")
print("     jumper on 1-2: the cable side (pin 3, USB_VBUS_F) is open at JP301, so nothing from +5V reaches F401, D402 or the cable;")
print("     jumper on 2-3: the module output (pin 1) is open, so the module drives nothing and the cable feeds only the board's own loads;")
print("     with a computer on the cable and the jumper on 1-2 the cable carries only the clamps' leakage (D401 IRM <= 150 nA at 5.25 V, D402 IR <= 400 uA at VR 6.0 V), far under 0.100 A")

# ---- (d) inrush -----------------------------------------------------------------------
c5, c3reg, c3 = 30.2e-6, 44.0e-6, 7.101e-6   # +3V3_REG: C304 and C305, 22 uF nominal each at 0 V bias
c = c5 + c3reg + c3
q = c5 * 5.25 + (c3reg + c3) * 3.333
print("(d)  jumper on 2-3: capacitance behind the fuse %.1f uF (C301 and C302 stay on the module's side) against the 10 uF of USB 2.0 7.2.4.1: %.1fx; charge %.0f uC"
      % (c * 1e6, c / 10e-6, q * 1e6))
print("     peak at Rmin %.1f A (tau %.0f us), at R1max %.2f A (tau %.0f us); fuse Imax 100 A; inrush above 8 A lasts about 3 tau = %.0f us at most"
      % (5.25 / rmin, rmin * c * 1e6, 5.25 / r1max, r1max * c * 1e6, 3 * r1max * c * 1e6))
print("     undamped step-response bound on the VBUS node: %.2f V (twice the 5.25 V source); D402 holds it to VC 10.3 V at 19.4 A; with the jumper on 2-3 the fuse output is the +5V rail, so the rail parts (LT1963A input 20 V absolute maximum; U201 and U791 7 V) are exposed to whatever F401 does not damp; no block now sits between them and the cable" % (2 * 5.25))
print("     charge through a 44 ohm / 10 uF load: %.0f uC; the limit's equivalent is met only with surge limiting ahead of %.1f uF" % (10e-6 * 5.25 * 1e6, c * 1e6))

# ---- clamp residue at the controller pin ----------------------------------------------
ip = 24.0
rd_ext = (10.3 - 7.37) / 19.4
v_node = (ip + 6.1 / 0.5 + 7.37 / rd_ext) / (1 / 0.5 + 1 / rd_ext)
vf = 1.1 + 0.5 * ip
print("(e)  DS4260 2.1 with VBUS open: VCL+ = %.1f V (6.1 + 0.5 x 24 + 1.1 + 0.5 x 24)" % (6.1 + 0.5 * ip + 1.1 + 0.5 * ip))
print("     with VBUS on D402 (Rd %.3f ohm from its sheet, typical-based): node %.1f V, VCL+ = %.1f V; the pin's DC limit is 6 V (4 V with VDD absent)"
      % (rd_ext, v_node, v_node + vf))
