#!/usr/bin/env python3
"""Generates the three sheet fragments of the sensing front ends (blocks 500-599) and the
standalone simulation decks that carry exactly the same reference designators and values.

Run from the repository root:  python3 -I hardware/sunbeam-em7000/main-board/circuit-proof/C_gen_sheets.py

The parts table below is the single source of both the sheet files (sheets/5*.yaml) and the decks
(circuit-proof/C_*.cir), so a deck cannot name a value the sheet does not carry.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)  # hardware/sunbeam-em7000/main-board
SHEETS = os.path.join(OUT, "sheets")
os.makedirs(SHEETS, exist_ok=True)

# ---------------------------------------------------------------- the catalogue parts
R0603 = "Resistor_SMD:R_0603_1608Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
PART = {
    "R10K": dict(lib_id="Device:R", value="10k", rating="1% 100ppm/K 0603 100mW", footprint=R0603,
                 mpn="0603WAF1002T5E", maker="UNI-ROYAL", lcsc="C25804", cls="basic"),
    "R20K": dict(lib_id="Device:R", value="20k", rating="1% 100ppm/K 0603 100mW", footprint=R0603,
                 mpn="0603WAF2002T5E", maker="UNI-ROYAL", lcsc="C4184", cls="basic"),
    "R1K": dict(lib_id="Device:R", value="1k", rating="1% 100ppm/K 0603 100mW", footprint=R0603,
                mpn="0603WAF1001T5E", maker="UNI-ROYAL", lcsc="C21190", cls="basic"),
    "R100": dict(lib_id="Device:R", value="100", rating="1% 100ppm/K 0603 100mW", footprint=R0603,
                 mpn="0603WAF1000T5E", maker="UNI-ROYAL", lcsc="C22775", cls="basic"),
    "R2K2": dict(lib_id="Device:R", value="2.2k", rating="1% 100ppm/K 0603 100mW", footprint=R0603,
                 mpn="0603WAF2201T5E", maker="UNI-ROYAL", lcsc="C4190", cls="basic"),
    "R0": dict(lib_id="Device:R", value="0", rating="0603 zero-ohm link", footprint=R0603,
               mpn="0603WAF0000T5E", maker="UNI-ROYAL", lcsc="C21189", cls="basic"),
    "R0L": dict(lib_id="Device:R", value="0", rating="1206 zero-ohm link 2A rated 10A overload", footprint="Resistor_SMD:R_1206_3216Metric",
                mpn="1206W4F0000T5E", maker="UNI-ROYAL", lcsc="C17888", cls="basic"),
    "C47N": dict(lib_id="Device:C", value="47n", rating="10% X7R 50V 0603", footprint=C0603,
                 mpn="CL10B473KB8NNNC", maker="Samsung Electro-Mechanics", lcsc="C1622", cls="basic"),
    "C100N": dict(lib_id="Device:C", value="100n", rating="10% X7R 50V 0603", footprint=C0603,
                  mpn="CC0603KRX7R9BB104", maker="YAGEO", lcsc="C14663", cls="basic"),
    "TVS": dict(lib_id="Device:D_TVS", value="PESD5V0F1BL", rating="bidirectional 5.5V standoff, 0.55pF max",
                footprint="Diode_SMD:D_SOD-882", mpn="PESD5V0F1BL,315", maker="Nexperia", lcsc="C45961",
                cls="extended"),
    "BAT54S": dict(lib_id="Diode:BAT54S", value="BAT54S", rating="dual series Schottky 30V 200mA",
                   footprint="Package_TO_SOT_SMD:SOT-23", mpn="BAT54S,215", maker="Nexperia", lcsc="C47546",
                   cls="extended"),
    "PTC": dict(lib_id="Device:Polyfuse", value="MF-NSMF012-2", rating="PTC 0.12A hold 0.29A trip 30V",
                footprint="Fuse:Fuse_1206_3216Metric", mpn="MF-NSMF012-2", maker="Bourns", lcsc="C163517",
                cls="extended"),
    "HDR2": dict(lib_id="Connector_Generic:Conn_01x02", value="Conn_01x02", rating="2.54mm 0.63mm pins",
                 footprint="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
                 mpn="2.54mm 1x2 header", maker="not read", lcsc="C32713268", cls="extended", hand=True),
    "HDR3": dict(lib_id="Connector_Generic:Conn_01x03", value="Conn_01x03", rating="2.54mm 0.63mm pins",
                 footprint="Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
                 mpn="2.54mm 1x3 header", maker="not read", lcsc="C49257", cls="extended", hand=True),
    "HDR4": dict(lib_id="Connector_Generic:Conn_01x04", value="Conn_01x04", rating="2.54mm 0.63mm pins",
                 footprint="Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
                 mpn="2.54mm 1x4 header", maker="not read", lcsc="C32713270", cls="extended", hand=True),
    "TP": dict(lib_id="Connector:TestPoint", value="TestPoint", rating="pad 1.5mm",
               footprint="TestPoint:TestPoint_Pad_D1.5mm", mpn="", maker="", lcsc="", cls="none"),
    "BUF": dict(lib_id="74xGxx:74LVC1G17", value="SN74LVC1G17", rating="Schmitt buffer, 5.5V inputs",
                footprint="Package_TO_SOT_SMD:SOT-353_SC-70-5", mpn="SN74LVC1G17DCKR",
                maker="Texas Instruments", lcsc="C10425", cls="extended"),
}


class Sheet:
    def __init__(self, name, function):
        self.name, self.function = name, function
        self.parts = []   # dicts
        self.nets = {}    # name -> (scope, [pins])
        self.nc = []
        self.notes = ""

    def add(self, ref, kind, function, value=None, dnp=False, mains=False, sim_exclude=False):
        p = dict(PART[kind])
        p.update(ref=ref, function=function, mains=mains, sim_exclude=sim_exclude, dnp=dnp)
        if value is not None:
            p["value"] = value
        self.parts.append(p)

    def net(self, name, scope, *pins):
        scope0, pins0 = self.nets.get(name, (scope, []))
        self.nets[name] = (scope0, pins0 + list(pins))

    def part(self, ref):
        return next(p for p in self.parts if p["ref"] == ref)

    def value(self, ref):
        return self.part(ref)["value"]


def q(s):
    return json.dumps(s)


def emit(sheet, path, custom=None):
    L = []
    L.append("sheet: %s" % q(sheet.name))
    L.append("function: %s" % q(sheet.function))
    L.append("parts:")
    for p in sheet.parts:
        L.append("  - ref: %s" % p["ref"])
        L.append("    lib_id: %s" % q(p["lib_id"]))
        L.append("    value: %s" % q(p["value"]))
        L.append("    rating: %s" % q(p["rating"]))
        L.append("    footprint: %s" % q(p["footprint"]))
        L.append("    mpn: %s" % q(p["mpn"]))
        L.append("    maker: %s" % q(p["maker"]))
        L.append("    lcsc: %s" % (p["lcsc"] if p["lcsc"] else '""'))
        L.append("    class: %s" % p["cls"])
        L.append("    hand: %s" % ("true" if p.get("hand") else "false"))
        L.append("    function: %s" % q(p["function"]))
        L.append("    mains: false")
        L.append("    sim_exclude: %s" % ("true" if p["sim_exclude"] else "false"))
        L.append("    dnp: %s" % ("true" if p["dnp"] else "false"))
    L.append("nets:")
    for n, (scope, pins) in sheet.nets.items():
        L.append("  %s: {scope: %s, pins: [%s]}" % (q(n), scope, ", ".join(q(x) for x in pins)))
    if sheet.nc:
        L.append("no_connect:")
        for pin, why in sheet.nc:
            L.append("  - {pin: %s, reason: %s}" % (q(pin), q(why)))
    else:
        L.append("no_connect: []")
    L.append("custom_symbols: []")
    L.append("custom_footprints: []")
    L.append("power_flags: []")
    L.append("notes: %s" % q(sheet.notes))
    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")


# ======================================================================= SHEET 1: thermistor inputs
S1 = Sheet("Thermistor inputs",
           "Three NTC thermistor dividers, each supplied from the analogue 3.3 V and filtered into one converter pin")
CH = [("COF", "TEMP_C", "coffee block", "J501", "R501", "R502", "C501", "D501", "D502", "TP501", "PC0"),
      ("STM", "TEMP_S", "steam block", "J502", "R503", "R504", "C502", "D503", "D504", "TP502", "PC1"),
      ("WAND", "TEMP_W", "steam wand disc", "J503", "R505", "R506", "C503", "D505", "D506", "TP503", "PC4")]
for ch, hname, what, j, rd, rs, c, dt, db, tp, pc in CH:
    S1.add(j, "HDR2", "%s thermistor header %s, harness lead RT, pin 1 square pad; a thermistor has no polarity" % (what, hname), value=hname)
    S1.add(rd, "R10K", "divider top resistor of the %s thermistor, to the analogue 3.3 V" % what)
    S1.add(dt, "TVS", "transient clamp at the %s header" % what)
    S1.add(rs, "R1K", "series resistor into the converter pin and the clamp; sets the filter with %s" % c)
    S1.add(c, "C47N", "converter-input filter capacitor, charge reservoir for the sampling capacitor")
    S1.add(db, "BAT54S", "steering clamp of the converter pin to GND and +3V3A against a cross-short to a 5 V lead")
    S1.add(tp, "TP", "test point on %s" % ("NTC_" + ch))
    sens, out = "NTC_%s_SENS" % ch, "NTC_%s" % ch
    S1.net(sens, "local", j + ".1", rd + ".2", dt + ".1", rs + ".1")
    S1.net("GND", "power", j + ".2", dt + ".2", c + ".2", db + ".1")
    S1.net("+3V3A", "power", rd + ".1", db + ".2")
    S1.net(out, "global", rs + ".2", c + ".1", db + ".3", tp + ".1")
S1.notes = ("Signal flows left to right: header (left) -> divider node -> series resistor -> filter node -> converter pin label. "
            "+3V3A at the top, GND at the bottom. Each header pin 1 is the square pad; the wand header is fitted rotated 180 degrees on the board "
            "(placement only, no electrical difference). The three channels are identical; draw them as three stacked identical cells. "
            "BAT54S symbol Diode:BAT54S pins: 1=A (to GND), 2=K (to +3V3A), 3=COM (to the converter pin node).")

# ======================================================================= SHEET 2
S2 = Sheet("Flow, pressure and spare analogue inputs",
           "Flow-meter pulse input, the two digital pressure-transducer buses, and the three analogue sensor inputs with 5 V scaling")
# ---- flow
S2.add("J520", "HDR3", "flow meter header CZ1: pin 1 5 V, pin 2 ground, pin 3 signal; pin 1 is the square pad (FLOW)", value="FLOW")
S2.add("R520", "R10K", "pull-up of the meter output to +3V3 (open-drain output re-referenced to 3.3 V)")
S2.add("D520", "TVS", "transient clamp at the flow header")
S2.add("R521", "R1K", "series resistor into the capture pin; limits the current a 5 V push-pull output could push through the pin")
S2.add("C520", "C47N", "flow-input filter capacitor")
S2.add("R522", "R0", "bypass link: fitted by default; removed when the Schmitt buffer U520 is fitted")
S2.add("U520", "BUF", "Schmitt-trigger buffer footprint, not fitted by default (input and output on the two nets the link R522 joins)", dnp=True)
S2.add("C521", "C100N", "supply decoupling of U520, fitted only with U520", dnp=True)
S2.add("TP520", "TP", "test point on FLOW_IN")
S2.net("+5V", "power", "J520.1")
S2.net("GND", "power", "J520.2", "D520.2", "C520.2", "U520.3", "C521.2")
S2.net("FLOW_RAW", "local", "J520.3", "R520.1", "D520.1", "R521.1")
S2.net("+3V3", "power", "R520.2", "U520.5", "C521.1")
S2.net("FLOW_F", "local", "R521.2", "C520.1", "R522.1", "U520.2")
S2.net("FLOW_IN", "global", "R522.2", "U520.4", "TP520.1")
S2.nc.append(("U520.1", "pin 1 is not connected inside SN74LVC1G17 (SCES351 pin table); the package is not fitted by default"))
# ---- digital pressure buses
def digital_bus(sheet, hdr, hname, ptc, link, tvs_c, tvs_d, rs_c, rs_d, rp_c, rp_d, bat_c, bat_d, tp_c, tp_d, tp_v, scl, sda, vfeed, what):
    sheet.add(hdr, "HDR4", "%s digital header: 1 3V3 feed, 2 GND, 3 SCL, 4 SDA" % what, value=hname)
    sheet.add(ptc, "PTC", "short-safe 3.3 V feed to the %s transducer" % what)
    sheet.add(link, "R0L", "isolating link of the %s transducer's 3.3 V feed, on the load side of the PTC" % what)
    sheet.add(tvs_c, "TVS", "transient clamp on the SCL line at the header")
    sheet.add(tvs_d, "TVS", "transient clamp on the SDA line at the header")
    sheet.add(rs_c, "R100", "series protection resistor in SCL")
    sheet.add(rs_d, "R100", "series protection resistor in SDA")
    sheet.add(rp_c, "R2K2", "SCL pull-up to +3V3, Standard-mode 100 kbit/s")
    sheet.add(rp_d, "R2K2", "SDA pull-up to +3V3, Standard-mode 100 kbit/s")
    sheet.add(bat_c, "BAT54S", "steering clamp of the SCL pin to GND and +3V3")
    sheet.add(bat_d, "BAT54S", "steering clamp of the SDA pin to GND and +3V3")
    sheet.add(tp_c, "TP", "test point on %s" % scl)
    sheet.add(tp_d, "TP", "test point on %s" % sda)
    sheet.add(tp_v, "TP", "test point on %s" % vfeed)
    sheet.net("+3V3", "power", ptc + ".1", rp_c + ".2", rp_d + ".2", bat_c + ".2", bat_d + ".2")
    sheet.net(vfeed + "_SRC", "local", ptc + ".2", link + ".1", tp_v + ".1")
    sheet.net(vfeed, "local", link + ".2", hdr + ".1")
    sheet.net("GND", "power", hdr + ".2", tvs_c + ".2", tvs_d + ".2", bat_c + ".1", bat_d + ".1")
    sheet.net(scl + "_X", "local", hdr + ".3", tvs_c + ".1", rs_c + ".1")
    sheet.net(sda + "_X", "local", hdr + ".4", tvs_d + ".1", rs_d + ".1")
    sheet.net(scl, "global", rs_c + ".2", rp_c + ".1", bat_c + ".3", tp_c + ".1")
    sheet.net(sda, "global", rs_d + ".2", rp_d + ".1", bat_d + ".3", tp_d + ".1")

digital_bus(S2, "J521", "STM_D", "F520", "R540", "D521", "D522", "R523", "R524", "R525", "R526", "D523", "D524",
            "TP521", "TP522", "TP523", "STM_SCL", "STM_SDA", "STMD_3V3", "steam-path")
digital_bus(S2, "J522", "BREW_D", "F521", "R541", "D525", "D526", "R527", "R528", "R529", "R530", "D527", "D528",
            "TP524", "TP525", "TP526", "BREW_SCL", "BREW_SDA", "BRWD_3V3", "brew-path")

# ---- analogue 5 V scaling cells
def analog_cell(sheet, hdr, hname, ptc, link, tvs, rt, rb, rs, cap, tp, tpv, out, raw, div, v3, what, extra_burden=None):
    sheet.add(hdr, "HDR4", "%s analogue header: 1 5V, 2 3V3 feed, 3 GND, 4 signal" % what, value=hname)
    sheet.add(ptc, "PTC", "short-safe 3.3 V feed of the %s header" % what)
    sheet.add(link, "R0L", "isolating link of the 3.3 V feed of the %s header, on the load side of the PTC" % what)
    sheet.add(tvs, "TVS", "transient clamp on the signal at the header")
    sheet.add(rt, "R10K", "divider top resistor: scales a 0.5-4.5 V / 5 V sensor to at most 3.3 V")
    sheet.add(rb, "R20K", "divider bottom resistor (ratio 20k/(10k+20k) = 0.667 nominal)")
    sheet.add(rs, "R1K", "series resistor into the converter pin; sets the filter with " + cap)
    sheet.add(cap, "C47N", "converter-input filter capacitor, charge reservoir for the sampling capacitor")
    sheet.add(tp, "TP", "test point on " + out)
    sheet.add(tpv, "TP", "test point on " + v3)
    sheet.net("+5V", "power", hdr + ".1")
    sheet.net("+3V3", "power", ptc + ".1")
    sheet.net(v3 + "_SRC", "local", ptc + ".2", link + ".1", tpv + ".1")
    sheet.net(v3, "local", link + ".2", hdr + ".2")
    sheet.net("GND", "power", hdr + ".3", tvs + ".2", rb + ".2", cap + ".2")
    sheet.net(raw, "local", hdr + ".4", tvs + ".1", rt + ".1")
    sheet.net(div, "local", rt + ".2", rb + ".1", rs + ".1")
    sheet.net(out, "global", rs + ".2", cap + ".1", tp + ".1")

analog_cell(S2, "J523", "SPARE_A", "F522", "R542", "D529", "R531", "R532", "R533", "C522", "TP527", "TP528", "STMP_AN",
            "SPAREA_RAW", "SPAREA_DIV", "SPAREA_3V3", "spare analogue (steam-path fallback)")
analog_cell(S2, "J524", "BREW_A", "F523", "R543", "D530", "R534", "R535", "R536", "C523", "TP529", "TP530", "BREW_AN",
            "BREWA_RAW", "BREWA_DIV", "BREWA_3V3", "brew-path analogue fallback")
analog_cell(S2, "J525", "SPARE_AN2_H", "F524", "R544", "D531", "R537", "R538", "R539", "C524", "TP531", "TP532", "SPARE_AN2",
            "SPAN2_RAW", "SPAN2_DIV", "SPAN2_3V3", "second spare analogue")
S2.notes = ("Four stacked cells, signal left to right: FLOW (header, pull-up, TVS, series R, C, then the link R522 in parallel with the "
            "unfitted buffer U520 footprint, then label FLOW_IN); STM_D and BREW_D (3V3 from +3V3 through the PTC to header pin 1; SCL and SDA "
            "each: header, TVS at the header, series R, pull-up to +3V3 and steering clamp at the converter-side node, labels STM_SCL/STM_SDA "
            "or BREW_SCL/BREW_SDA); SPARE_A, BREW_A, SPARE_AN2_H (3V3 through PTC, 5V direct from +5V, signal pin 4 -> TVS -> 10k/20k divider -> "
            "1k -> 47n -> label). U520 and C521 are drawn and marked do-not-populate; R522 is fitted. Header pin tables: J520 1=+5V 2=GND 3=FLOW_RAW; "
            "J521 1=STMD_3V3 2=GND 3=STM_SCL_X 4=STM_SDA_X; J522 1=BRWD_3V3 2=GND 3=BREW_SCL_X 4=BREW_SDA_X; analogue headers 1=+5V 2=3V3 feed 3=GND 4=signal. "
            "Diode:BAT54S pins: 1=A (GND), 2=K (+3V3), 3=COM (signal node). Device:Polyfuse pin 1 = +3V3 side, pin 2 = toward the header. Each 3.3 V feed runs +3V3 -> PTC -> test point and link R540..R544 (1206, value 0, the isolating link) -> header pin; the test point stands on the PTC side of the link.")

# ======================================================================= SHEET 3
S3 = Sheet("Current sensing inputs",
           "Two current-sensor interfaces, each a three-way header with scaling, an unpopulated burden position and the converter filter")
def current_cell(sheet, hdr, hname, tvs, rt, rb, burden, rs, cap, tp, sig, div, out, n):
    sheet.add(hdr, "HDR3", "current sensor %d header: 1 sensor supply 5V, 2 sensor output, 3 return" % n, value=hname)
    sheet.add(tvs, "TVS", "transient clamp on the sensor output at the header")
    sheet.add(rt, "R10K", "scaling top resistor: keeps a sensor output of up to 5.25 V under the converter pin's 4.0 V maximum")
    sheet.add(rb, "R20K", "scaling bottom resistor")
    sheet.add(burden, "R10K", "burden position for a current-output sensor, not populated; value not sized (sensor not chosen)", value="DNP", dnp=True)
    sheet.add(rs, "R1K", "series resistor into the converter pin; sets the filter with " + cap)
    sheet.add(cap, "C47N", "converter-input filter capacitor")
    sheet.add(tp, "TP", "test point on " + out)
    sheet.net("+5V", "power", hdr + ".1")
    sheet.net(sig, "local", hdr + ".2", tvs + ".1", rt + ".1")
    sheet.net("GND", "power", hdr + ".3", tvs + ".2", rb + ".2", burden + ".2", cap + ".2")
    sheet.net(div, "local", rt + ".2", rb + ".1", burden + ".1", rs + ".1")
    sheet.net(out, "global", rs + ".2", cap + ".1", tp + ".1")

current_cell(S3, "J570", "CURR1_H", "D570", "R570", "R571", "R572", "R573", "C570", "TP570", "CURR1_SIG", "CURR1_DIV", "CURR1_AN", 1)
current_cell(S3, "J571", "CURR2_H", "D571", "R574", "R575", "R576", "R577", "C571", "TP571", "CURR2_SIG", "CURR2_DIV", "CURR2_AN", 2)
S3.notes = ("Two identical cells, signal left to right: header -> TVS -> divider -> series R -> filter -> label. R572 and R576 are drawn with the "
            "value text DNP and marked do-not-populate: they are the burden positions parallel to the bottom resistor. A current-output sensor "
            "is served by fitting a burden there, replacing the top resistor with a zero-ohm link and removing the bottom resistor; the values "
            "wait for the sensor, which the records leave to the owner.")

if __name__ == "__main__":
    emit(S1, os.path.join(SHEETS, "50-thermistor-inputs.yaml"))
    emit(S2, os.path.join(SHEETS, "52-flow-pressure-and-spare-analogue-inputs.yaml"))
    emit(S3, os.path.join(SHEETS, "57-current-sensing-inputs.yaml"))
    print("wrote 3 sheet fragments")
