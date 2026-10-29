#!/usr/bin/env python3
"""Writes the ngspice decks of the sensing front ends (blocks 500-599) from the same parts table
that writes the sheets (C_gen_sheets.py), then runs every one and checks each log.

Reference designators and values in the decks are the sheets'. Elements whose names carry SIM_
(RSIM_, CSIM_, VSIM_, SSIM_, ESIM_) are the stand-ins for what is not on the board: the sensor, the
converter's sample and hold, the supply and the bus capacitance.

Run:  python3 hardware/sunbeam-em7000/main-board/circuit-proof/C_gen_decks.py
"""
import importlib.util
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("G", os.path.join(HERE, "C_gen_sheets.py"))
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)
S1, S2, S3 = G.S1, G.S2, G.S3

R_HI, R_LO = 1.0145, 0.9855      # 1 % and 100 ppm/K over 25..70 degC (UNI-ROYAL data sheet, Feb.12 2019 V.3, section 11)
C_HI, C_LO = 1.10 * 1.15, 0.90 * 0.85   # +-10 % and X7R +-15 % (Samsung MLCC catalogue Nov 2015)
LSB_X1000 = 3.3 / 65536 / 2 * 1000      # half an LSB at VREF+ = 3.3 V, times the 1000 of the error vector
BAT_MODEL = "* BAT54S as two diodes, fitted to the forward-voltage MAXIMA of Nexperia BAT54S 1 July 2022 Table 7 (0.24 V at 0.1 mA, 0.32 at 1, 0.40 at 10, 0.50 at 30, 0.80 at 100 mA)\n.model DSCH D(IS=7.793e-9 N=1.04 RS=3.6)"
SW_MODEL = ".model SWM SW(Ron=1m Roff=1e12 Vt=0.5 Vh=0.2)"
HEADER = ("* Source of every value: the sheet fragment of this block (generated from the same table).\n"
          "* Sim-only elements (names with SIM_) stand for the sensor, the converter's sample and hold and the supply.\n"
          "* Converter: DS12110 Rev 11 Table 77 / Table 174: CADC 4 pF (typ), tS 810.5 cycles, 16 bit, fADC 10 MHz.\n")

decks = []   # (filename, text, expected measurement names)


def num(sheet, ref):
    return sheet.value(ref)


def settle_deck(tag, title, rtop_net, step_node, sheet, parts, out, final_note, step_v, divider):
    """parts: lines of the real circuit. Window and step in one transient."""
    t = []
    t.append("%s" % title)
    t.append(HEADER.rstrip())
    t.append(SW_MODEL)
    t.extend(parts)
    t.append("VSIM_STEP SIM_STEP 0 PWL(0 0 1u %s)" % step_v)
    t.append("CSIM_ADC ADC_H 0 4p")
    t.append("SSIM_SH %s ADC_H CTL 0 SWM" % out)
    t.append("VSIM_CTL CTL 0 PULSE(0 1 30m 1n 1n 81.05u 100)")
    t.append(".ic V(ADC_H)=0")
    t.append(".tran 2u 45m")
    t.append(".control")
    for corner, (rf, cf) in (("slow", (R_HI, C_HI)), ("fast", (R_LO, C_LO))):
        t.append("* corner %s: every resistor at x%.4f, every capacitor at x%.4f of nominal" % (corner, rf, cf))
        for line in divider(rf, cf):
            t.append(line)
        t.append("run")
        t.append("meas tran vfin_%s FIND v(%s) AT=29m" % (corner, out))
        t.append("let errx_%s = (vfin_%s - v(%s))*1000" % (corner, corner, out))
        t.append("meas tran t_set_%s WHEN errx_%s=%.5f FALL=1" % (corner, corner, LSB_X1000))
        t.append("meas tran v_win_%s FIND v(%s) AT=30.0811m" % (corner, out))
        t.append("let kick_uV_%s = (vfin_%s - v_win_%s)*1e6" % (corner, corner, corner))
        t.append("print kick_uV_%s" % corner)
        t.append("meas tran t_rec_%s WHEN errx_%s=%.5f FALL=2" % (corner, corner, LSB_X1000))
        t.append("meas tran v_end_%s FIND v(%s) AT=44m" % (corner, out))
        t.append("let resid_uV_%s = (vfin_%s - v_end_%s)*1e6" % (corner, corner, corner))
        t.append("print resid_uV_%s" % corner)
    t.append(".endc")
    t.append(".end")
    names = []
    for corner in ("slow", "fast"):
        names += ["t_set_%s" % corner, "kick_uV_%s" % corner, "t_rec_%s" % corner, "resid_uV_%s" % corner]
    decks.append(("C_%s_settle.cir" % tag, "\n".join(t) + "\n", names))


# ---------------------------------------------------------------- thermistor channels
for ch, hname, what, j, rd, rs, c, dt, db, tp, pc in G.CH:
    out, sens = "NTC_" + ch, "NTC_%s_SENS" % ch
    parts = ["%s SIM_STEP %s %s" % (rd, sens, num(S1, rd)),
             "RSIM_NTC %s 0 1T" % sens,
             "%s %s %s %s" % (rs, sens, out, num(S1, rs)),
             "%s %s 0 %s" % (c, out, num(S1, c))]

    def divider(rf, cf, rd=rd, rs=rs, c=c, S=S1):
        return ["alter %s = %.6g" % (rd, 10e3 * rf), "alter %s = %.6g" % (rs, 1e3 * rf), "alter %s = %.6g" % (c, 47e-9 * cf)]
    settle_deck("ntc_" + ch.lower(), "Settling and sample memory, %s (%s %s %s): supply step 0 to 3.3 V, sensor open" % (out, rd, rs, c),
                sens, "SIM_STEP", S1, parts, out, "", "3.3", divider)

# ---------------------------------------------------------------- analogue scaling channels
ANA = [("spare_a", "STMP_AN", "SPAREA", "R531", "R532", "R533", "C522", S2, "5.5 V headroom: J523 pin 4"),
       ("brew_a", "BREW_AN", "BREWA", "R534", "R535", "R536", "C523", S2, ""),
       ("spare_an2", "SPARE_AN2", "SPAN2", "R537", "R538", "R539", "C524", S2, ""),
       ("curr1", "CURR1_AN", "CURR1", "R570", "R571", "R573", "C570", S3, ""),
       ("curr2", "CURR2_AN", "CURR2", "R574", "R575", "R577", "C571", S3, "")]
for tag, out, pre, rt, rb, rsr, cap, S, _ in ANA:
    raw = "%s_RAW" % pre if S is S2 else "%s_SIG" % pre
    div = "%s_DIV" % pre
    parts = ["%s SIM_STEP %s %s" % (rt, div, num(S, rt)),
             "%s %s 0 %s" % (rb, div, num(S, rb)),
             "%s %s %s %s" % (rsr, div, out, num(S, rsr)),
             "%s %s 0 %s" % (cap, out, num(S, cap))]

    def divider(rf, cf, rt=rt, rb=rb, rsr=rsr, cap=cap):
        return ["alter %s = %.6g" % (rt, 10e3 * rf), "alter %s = %.6g" % (rb, 20e3 * rf), "alter %s = %.6g" % (rsr, 1e3 * rf),
                "alter %s = %.6g" % (cap, 47e-9 * cf)]
    settle_deck(tag, "Settling and sample memory, %s (%s %s %s %s): sensor step 0 to 4.5 V, ideal sensor output" % (out, rt, rb, rsr, cap),
                div, "SIM_STEP", S, parts, out, "", "4.5", divider)

    # DC scaling and fault levels
    t = ["Converter pin voltage of %s with the sensor output or supply at its high levels, divider at its high-ratio tolerance corner" % out,
         HEADER.rstrip(),
         "%s SIM_SENS %s %s" % (rt, div, num(S, rt)),
         "%s %s 0 %s" % (rb, div, num(S, rb)),
         "%s %s %s %s" % (rsr, div, out, num(S, rsr)),
         "VSIM_SENS SIM_SENS 0 5.125",
         # converter pad leakage of the pin, DS12110 Table 50, +-250 nA (TT_xx and FT_xx), drawn out of the pin
         "ISIM_PAD %s 0 250n" % out,
         ".op",
         ".control",
         "alter %s = %.6g" % (rt, 10e3 * R_LO), "alter %s = %.6g" % (rb, 20e3 * R_HI), "alter %s = %.6g" % (rsr, 1e3 * R_HI)]
    for lab, v in (("5p125", 5.125), ("5p25", 5.25), ("5p5", 5.5)):
        t += ["alter VSIM_SENS = %s" % v, "op", "meas dc pin_%s FIND v(%s)" % (lab, out) if False else "let pin_%s = v(%s)" % (lab, out), "print pin_%s" % lab]
    t += [".endc", ".end"]
    decks.append(("C_%s_scale.cir" % tag, "\n".join(t) + "\n", ["pin_5p125", "pin_5p25", "pin_5p5"]))

# ---------------------------------------------------------------- thermistor cross-short clamp
for ch, hname, what, j, rd, rs, c, dt, db, tp, pc in G.CH:
    out, sens = "NTC_" + ch, "NTC_%s_SENS" % ch
    t = ["Clamp of %s: lead cross-shorted to a 5 V supply lead, node %s driven to the 5 V level" % (out, sens),
         HEADER.rstrip(), BAT_MODEL,
         "VSIM_V3A +3V3A 0 3.3",
         "%s +3V3A %s %s" % (rd, sens, num(S1, rd)),
         "VSIM_XSHORT %s 0 5.25" % sens,
         "%s %s %s %s" % (rs, sens, out, num(S1, rs)),
         "* %s: pin 1 (A) on GND, pin 3 (COM) on the converter pin node, pin 2 (K) on +3V3A" % db,
         "%s_1 0 %s DSCH" % (db, out),
         "%s_2 %s +3V3A DSCH" % (db, out),
         "ISIM_PAD %s 0 250n" % out,
         ".op",
         ".control"]
    for lab, rail in (("rail3p3", 3.3), ("rail3p4", 3.4), ("rail3p5", 3.5), ("rail3p6", 3.6)):
        t += ["alter VSIM_V3A = %s" % rail, "op", "let pin_%s = v(%s)" % (lab, out), "print pin_%s" % lab,
              "let iclamp_mA_%s = (v(%s)-v(%s))/1000*1000" % (lab, sens, out), "print iclamp_mA_%s" % lab]
    t += [".endc", ".end"]
    decks.append(("C_ntc_%s_clamp.cir" % ch.lower(), "\n".join(t) + "\n", ["pin_rail3p3", "pin_rail3p6", "iclamp_mA_rail3p6"]))

# ---------------------------------------------------------------- I2C buses
for tag, hdr, pre, rs_c, rs_d, rp_c, rp_d, scl, sda in (("stm_i2c", "J521", "STM", "R523", "R524", "R525", "R526", "STM_SCL", "STM_SDA"),
                                                         ("brew_i2c", "J522", "BREW", "R527", "R528", "R529", "R530", "BREW_SCL", "BREW_SDA")):
    t = ["Rise time and low level of %s and %s, Standard-mode 100 kbit/s, 400 pF bus on the cable side then on the board side" % (scl, sda),
         HEADER.rstrip(), SW_MODEL,
         "VSIM_V3V3 +3V3 0 3.6",
         "%s %s +3V3 %s" % (rp_c, scl, num(S2, rp_c)),
         "%s %s_X %s %s" % (rs_c, scl, scl, num(S2, rs_c)),
         "* SDA has the same parts; only SCL is simulated, SDA is its twin with %s %s" % (rp_d, rs_d),
         "* bus capacitance: UM10204 Rev 7.0 Table 11, Cb max 400 pF, of which the pins take 31.1 pF (sensor, controller pin, TVS, BAT54S)",
         "CSIM_CABLE %s_X 0 368.9p" % scl,
         "CSIM_BOARD %s 0 31.1p" % scl,
         "* sensor open-drain pull-down, low level at the UM10204 Table 10 maximum VOL of 0.4 V",
         "VSIM_VOL SIM_VOL 0 0.4",
         "SSIM_OD %s_X SIM_VOL SIM_DRV 0 SWM" % scl,
         "VSIM_DRV SIM_DRV 0 PULSE(1 0 20u 1n 1n 100u 200u)",
         ".tran 20n 180u",
         ".control"]
    for lab, rf, cabl, board in (("hi_cable", R_HI, 368.9, 31.1), ("hi_board", R_HI, 31.1, 368.9)):
        t += ["alter %s = %.6g" % (rp_c, 2.2e3 * rf), "alter %s = %.6g" % (rs_c, 100 * rf),
              "alter CSIM_CABLE = %sp" % cabl, "alter CSIM_BOARD = %sp" % board, "run",
              "meas tran tr_mcu_%s TRIG v(%s) VAL=1.08 RISE=1 TARG v(%s) VAL=2.52 RISE=1" % (lab, scl, scl),
              "meas tran tr_sensor_%s TRIG v(%s_X) VAL=1.08 RISE=1 TARG v(%s_X) VAL=2.52 RISE=1" % (lab, scl, scl),
              "meas tran vlow_mcu_%s FIND v(%s) AT=15u" % (lab, scl)]
    t += [".endc", ".end"]
    decks.append(("C_%s.cir" % tag, "\n".join(t) + "\n", ["tr_mcu_hi_cable", "tr_sensor_hi_cable", "tr_mcu_hi_board", "tr_sensor_hi_board", "vlow_mcu_hi_cable"]))

# ---------------------------------------------------------------- flow input
t = ["Flow input FLOW_IN: edges through R521 and C520 for an open-drain meter (3.3 V pull-up R520) and for a 5 V push-pull meter",
     HEADER.rstrip(), SW_MODEL,
     "VSIM_V3V3 +3V3 0 3.3",
     "R520 FLOW_RAW +3V3 %s" % num(S2, "R520"),
     "R521 FLOW_RAW FLOW_F %s" % num(S2, "R521"),
     "C520 FLOW_F 0 %s" % num(S2, "C520"),
     "* R522 is a zero-ohm link in the sheet (value 0); ngspice replaces 0 by 1e-12 ohm and then loses accuracy, so it is simulated as 1 mOhm",
     "R522 FLOW_F FLOW_IN 1m",
     "* meter output stages: open-drain = switch to ground; push-pull = switch to the 5 V rail (high) and to ground (low), 100 Hz square wave",
     "SSIM_OD FLOW_RAW 0 CTLA 0 SWM",
     "VSIM_CTLA CTLA 0 PULSE(0 1 100u 1n 1n 4.9m 10m)",
     ".tran 5u 20m",
     ".control",
     "alter R520 = %.6g" % (10e3 * R_HI), "alter R521 = %.6g" % (1e3 * R_HI), "alter C520 = %.6g" % (47e-9 * C_HI), "run",
     "meas tran vhigh_od MAX v(FLOW_IN) FROM=0.5m TO=10m",
     "meas tran vlow_od MIN v(FLOW_IN) FROM=5m TO=10m",
     "meas tran t_vih_od TRIG v(FLOW_RAW) VAL=1.65 RISE=1 TARG v(FLOW_IN) VAL=2.31 RISE=1",
     "meas tran tr_10_90_od TRIG v(FLOW_IN) VAL=0.33 RISE=1 TARG v(FLOW_IN) VAL=2.97 RISE=1",
     ".endc", ".end"]
decks.append(("C_flow_od.cir", "\n".join(t) + "\n", ["vhigh_od", "vlow_od", "t_vih_od", "tr_10_90_od"]))

t = ["Flow input FLOW_IN with a 5 V push-pull meter output (5.125 V rail high, 5.25 V margin case) through R521, C520 and the TVS leakage",
     HEADER.rstrip(), SW_MODEL,
     "VSIM_V3V3 +3V3 0 3.6",
     "VSIM_5V SIM_5V 0 5.125",
     "R520 FLOW_RAW +3V3 %s" % num(S2, "R520"),
     "R521 FLOW_RAW FLOW_F %s" % num(S2, "R521"),
     "C520 FLOW_F 0 %s" % num(S2, "C520"),
     "* R522 is a zero-ohm link in the sheet (value 0); ngspice replaces 0 by 1e-12 ohm and then loses accuracy, so it is simulated as 1 mOhm",
     "R522 FLOW_F FLOW_IN 1m",
     "SSIM_HI SIM_5V PP_OUT CTLH 0 SWM",
     "SSIM_LO PP_OUT 0 CTLL 0 SWM",
     "RSIM_PP PP_OUT FLOW_RAW 25",
     "VSIM_CTLH CTLH 0 PULSE(0 1 100u 1n 1n 4.9m 10m)",
     "ESIM_INV CTLL 0 VALUE={1-v(CTLH)}",
     "ISIM_PAD FLOW_IN 0 1.5u",
     ".tran 5u 20m",
     ".control",
     "alter R520 = %.6g" % (10e3 * R_LO), "alter R521 = %.6g" % (1e3 * R_HI), "alter C520 = %.6g" % (47e-9 * C_HI)]
for lab, v in (("5p125", 5.125), ("5p25", 5.25)):
    t += ["alter VSIM_5V = %s" % v, "run",
          "meas tran vhigh_pp_%s MAX v(FLOW_IN) FROM=0.5m TO=10m" % lab,
          "meas tran vlow_pp_%s MIN v(FLOW_IN) FROM=5m TO=10m" % lab]
t += [".endc", ".end"]
decks.append(("C_flow_pp.cir", "\n".join(t) + "\n", ["vhigh_pp_5p125", "vhigh_pp_5p25", "vlow_pp_5p125"]))


def main():
    import re
    ok = True
    for name, text, names in decks:
        path = os.path.join(HERE, name)
        with open(path, "w") as f:
            f.write(text)
        log = path[:-4] + ".log"
        r = subprocess.run(["ngspice", "-b", path, "-o", log], capture_output=True, text=True, timeout=300)
        logtxt = open(log).read()
        errs = [l for l in logtxt.splitlines() if l.startswith("Error")]
        got = {}
        for n in names:
            m = re.search(r"^\s*%s\s*=\s*([-+0-9.eE]+)" % re.escape(n), logtxt, re.M | re.I)
            got[n] = m.group(1) if m else None
        status = (r.returncode == 0) and not errs and all(v is not None for v in got.values())
        ok &= status
        print("%-24s exit=%d errors=%d %s" % (name, r.returncode, len(errs), "ok" if status else "FAILS"))
        for n in names:
            print("     %-22s %s" % (n, got[n]))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
