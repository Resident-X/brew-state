#!/usr/bin/env python3
"""Arithmetic of the sensing front ends of blocks 500-599 (thermistor, analogue 5 V scaling, flow,
I2C pull-ups, PTC feeds).  Prints every result; exits non-zero if a row's own check fails.

Values come from C_gen_sheets.py (the parts table that also writes the sheets), so the numbers here
are the schematic's.  Every constant states the document it is read from.

Run:  python3 hardware/sunbeam-em7000/main-board/circuit-proof/C_front_ends.py
"""
import importlib.util
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("G", os.path.join(HERE, "C_gen_sheets.py"))
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)
S1, S2, S3 = G.S1, G.S2, G.S3


def val(sheet, ref):
    s = sheet.value(ref).replace("k", "e3").replace("n", "e-9").replace("M", "e6")
    return float(s)


fails = []


def check(name, ok):
    print("  CHECK %-62s %s" % (name, "ok" if ok else "FAILS"))
    if not ok:
        fails.append(name)


# ---------------------------------------------------------------- sources (constants)
# DS12110 Rev 11 (STMicroelectronics, January 2026), https://www.st.com/resource/en/datasheet/stm32h743vi.pdf
# (read 2026-10-29 from the copy of ST's PDF under the scratchpad, which the st.com site refuses to a script).
CADC = 4e-12            # Table 77 (rev Y) and Table 174 (rev V): internal sample and hold capacitor, "Typ" 4 pF; no min or max printed
NBITS = 16              # Table 77: 16-bit resolution
TS_CYC = 810.5          # Table 77 / Table 174: sampling time tS up to 810.5 ADC clock cycles
FADC = 10e6             # firmware choice, within Table 77 (slow channels, fADC = 10 MHz, 1 MSPS at 16 bits)
TCONV = (TS_CYC + 0.5 + NBITS / 2) / FADC   # Table 77: tCONV = tS + 0.5 + N/2 cycles
VDDA_MAX = 3.6          # Table 14 / Table 77: VDDA analogue supply 1.62 to 3.6 V
RAIN_REVY = 50e3        # Table 77 (rev Y): external input impedance max 50 kOhm
RAIN_REVV = 170.0       # Table 174 (rev V): external input impedance max, 16-bit, TJ = 125 degC
# Record: controller-io.md, sensing channels, "Update rate" column: every control step, x1 of the 10 ms
# (100 Hz) step-interval-ms (firmware/params/cadence.declaration)
STEP_S = 10e-3
F_NYQ = 1.0 / (2 * STEP_S)
# Resistor: constraints record, "Manufacturer stock and price, per channel", C25804: 10 kOhm +-1 %, +-100 ppm/degC;
# UNI-ROYAL Thick Film Chip Resistors data sheet, Feb.12 2019 V.3, section 11: 0603, R > 10 Ohm, 100 ppm/degC;
# section 6: 1/10 W at 70 degC (all values of the 0603WAF series)
TOL_R, TCR = 0.01, 100e-6
T_REF, T_HOT = 25.0, 70.0   # 25 degC datasheet reference; 70 degC enclosure air (constraints record, Enclosure air temperature)
DT = T_HOT - T_REF
R_HI = 1 + TOL_R + TCR * DT   # highest value of a resistor over the range
R_LO = 1 - TOL_R - TCR * DT
# Capacitor: CL10B473KB8NNNC, +-10 % (K), X7R +-15 % over temperature (Samsung Electro-Mechanics MLCC catalogue, Nov 2015,
# temperature characteristics of capacitance table: A(X5R)/B(X7R) 15 %)
C_HI = 1.10 * 1.15
C_LO = 0.90 * 0.85
LN_LSB = math.log(2 ** NBITS)
LN_HALF = math.log(2 ** (NBITS + 1))

print("== common inputs")
print("  tCONV = (%.1f + 0.5 + %d/2) / %.0f MHz = %.2f us" % (TS_CYC, NBITS, FADC / 1e6, TCONV * 1e6))
TACQ = STEP_S - TCONV
print("  acquisition time = 10 ms - tCONV = %.4f ms" % (TACQ * 1e3))
TAU_MAX = TACQ / LN_LSB
TAU_MAX_HALF = TACQ / LN_HALF
print("  tau allowed = tacq / ln(2^16) = %.4f ms ; with the half-LSB reading ln(2^17) = %.4f ms" % (TAU_MAX * 1e3, TAU_MAX_HALF * 1e3))
print("  highest frequency of interest = Nyquist of the 10 ms update = %.0f Hz" % F_NYQ)
print("  resistor extremes over 25..70 degC: x%.4f .. x%.4f ; capacitor extremes x%.4f .. x%.4f" % (R_LO, R_HI, C_LO, C_HI))

# ================================================================= RCFL-1 rows
print("\n== RCFL-1: settling, reservoir and corner, every converter input")
cells = []
for ch, hname, what, j, rd, rs, c, dt, db, tp, pc in G.CH:
    rdiv, rser, cap = val(S1, rd), val(S1, rs), val(S1, c)
    cells.append(("NTC_" + ch, "%s,%s,%s" % (rd, rs, c), rdiv * R_HI + rser * R_HI, rdiv * R_LO + rser * R_LO, cap,
                  "sensor open (R_NTC -> infinity) gives the largest source"))
for tag, rt, rb, rsr, cap, nm in (("STMP_AN", "R531", "R532", "R533", "C522", "FE_SPAREA"),
                                  ("BREW_AN", "R534", "R535", "R536", "C523", "BREW_A_C"),
                                  ("SPARE_AN2", "R537", "R538", "R539", "C524", "SPARE_AN2_C")):
    a, b, s, cc = val(S2, rt), val(S2, rb), val(S2, rsr), val(S2, cap)
    cells.append((tag, "%s,%s,%s,%s" % (rt, rb, rsr, cap), (a * b / (a + b) + s) * R_HI, (a * b / (a + b) + s) * R_LO, cc,
                  "divider output impedance plus series resistor; sensor output impedance not sourced"))
for tag, rt, rb, rsr, cap in (("CURR1_AN", "R570", "R571", "R573", "C570"), ("CURR2_AN", "R574", "R575", "R577", "C571")):
    a, b, s, cc = val(S3, rt), val(S3, rb), val(S3, rsr), val(S3, cap)
    cells.append((tag, "%s,%s,%s,%s" % (rt, rb, rsr, cap), (a * b / (a + b) + s) * R_HI, (a * b / (a + b) + s) * R_LO, cc,
                  "burden position unpopulated; sensor output impedance not sourced"))
for tag, refs, rth_max, rth_min, cnom, note in cells:
    cmax, cmin = cnom * C_HI, cnom * C_LO
    rc_max = rth_max * cmax
    fc_min = 1 / (2 * math.pi * rc_max)
    zout_allow = TAU_MAX_HALF / cmax - rth_max
    print(" %s (%s): Rth,max = %.3f kOhm, C range %.1f..%.1f nF" % (tag, refs, rth_max / 1e3, cmin * 1e9, cmax * 1e9))
    print("   R*C worst = %.4f ms ; allowed %.4f ms (ln 2^16) / %.4f ms (ln 2^17) ; margin %.1f %%" %
          (rc_max * 1e3, TAU_MAX * 1e3, TAU_MAX_HALF * 1e3, 100 * (1 - rc_max / TAU_MAX_HALF)))
    print("   C min = %.1f nF vs 20*CADC = %.0f pF  (x%.0f) ; corner (R,C highest) = %.0f Hz vs %.0f Hz (x%.1f)" %
          (cmin * 1e9, 20 * CADC * 1e12, cmin / (20 * CADC), fc_min, F_NYQ, fc_min / F_NYQ))
    print("   largest extra source resistance (sensor output impedance) before the half-LSB reading fails = %.2f kOhm" % (zout_allow / 1e3))
    kick = VDDA_MAX * CADC / (CADC + cmin)
    lsb = 3.3 / 2 ** NBITS
    print("   memory of the previous conversion (charge sharing, CADC typ): %.0f uV = %.1f LSB (LSB = %.1f uV)" % (kick * 1e6, kick / lsb, lsb * 1e6))
    check("%s R*C <= tacq/ln(2^16)" % tag, rc_max <= TAU_MAX)
    check("%s R*C <= tacq/ln(2^17)" % tag, rc_max <= TAU_MAX_HALF)
    check("%s C >= 20 CADC" % tag, cmin >= 20 * CADC)
    check("%s corner above Nyquist of the update rate" % tag, fc_min > F_NYQ)
print("  RAIN: rev Y %.0f kOhm max; rev V %.0f Ohm max at 16 bit. The reservoir capacitor stands at the converter pin, with the series resistor on the "
      "sensor side of it, so the impedance the converter sees through the pin during the sampling window is the capacitor's." % (RAIN_REVY / 1e3, RAIN_REVV))
check("every Rth,max below the rev Y RAIN 50 kOhm", all(c[2] < RAIN_REVY for c in cells))

# ================================================================= pin voltages of the analogue scaling cells
print("\n== PINV-1: converter pin voltage, scaling cells (sensor 5 V class)")
a, b = val(S2, "R531"), val(S2, "R532")
r_nom = b / (a + b)
r_max = b * R_HI / (b * R_HI + a * R_LO)
r_min = b * R_LO / (b * R_LO + a * R_HI)
print("  ratio nominal %.4f, over tolerance and 25..70 degC: %.4f .. %.4f (%.2f %% .. %+.2f %%)" % (r_nom, r_min, r_max, 100 * (r_min / r_nom - 1), 100 * (r_max / r_nom - 1)))
for lab, v in (("5 V rail high, IRM-20-5 +2.5 %", 5.125), ("5.25 V (rail-high case of the brief)", 5.25),
               ("5.5 V (S1 transducer supply limit 5.0 +- 0.5 V, function-forms record, S11)", 5.5)):
    vn = v * r_max
    print("  sensor output / supply fault at %.3f V (%s): pin node %.3f V ; limit 4.000 V (Table 11: TT_xx 4.0 V; FT_a with analogue peripheral 4 V, note 5) margin %.3f V" % (v, lab, vn, 4.0 - vn))
    check("pin node below 4.0 V at %.3f V" % v, vn < 4.0)
vfs = 0.9 * 5.125 * r_max
print("  full-scale reading of a 0.5-4.5 V ratiometric sensor on the 5 V rail high: %.3f V (VREF+ = VDDA <= 3.3 V nominal)" % vfs)
check("full scale below 3.3 V on a 5.125 V rail", vfs < 3.3)
# gain error as a share of a 0.5..4.5 V span
err_hi = (r_max / r_nom - 1) * 4.5 / 4.0
err_lo = (1 - r_min / r_nom) * 4.5 / 4.0
print("  gain error of the front end at 4.5 V reading, as a share of the 4.0 V span: +%.2f %% / -%.2f %%" % (100 * err_hi, 100 * err_lo))
fe = max(err_hi, err_lo)
for fs in (7.0, 10.0, 25.0):
    tot = (0.01 + fe) * fs
    print("   full scale %.1f bar: transducer 1 %% FS + front end %.2f %% FS = %.3f bar vs binding 0.25 bar : %s" % (fs, 100 * fe, tot, "within" if tot <= 0.25 else "outside"))
print("   largest full scale the 1 %% divider supports with a 1 %% transducer: %.1f bar" % (0.25 / (0.01 + fe)))
# 0.1 % option, C95204 10k 0.1 % 25 ppm ; the 20 k bottom resistor in 0.1 % is not read in the records
tol01, tcr01 = 0.001, 25e-6
hi01, lo01 = 1 + tol01 + tcr01 * DT, 1 - tol01 - tcr01 * DT
fe01 = ((b * hi01 / (b * hi01 + a * lo01)) / r_nom - 1) * 4.5 / 4.0
print("   with 0.1 %% / 25 ppm resistors the front end is +%.3f %% FS, supporting %.1f bar" % (100 * fe01, 0.25 / (0.01 + fe01)))

# ================================================================= thermistor accuracy
print("\n== thermistor front end: temperature error of the front end alone")
RD = val(S1, "R501")
RSER = val(S1, "R502")
ILEAK = 2e-6 + 0.1e-6 + 0.25e-6   # BAT54S IR max 2 uA (VR 25 V, 25 degC), TVS IRM max 100 nA (VRWM 5 V), pad leakage 250 nA (DS12110 Table 50)
VDD = 3.3
R25 = 100e3   # consistent with the three measured values 95.8..98.3 kOhm at 25.4 degC (connector-pinouts.md)
T25 = 298.15


def rn_of(tc, beta):
    return R25 * math.exp(beta * (1 / (tc + 273.15) - 1 / T25))


def t_of(rn, beta):
    return 1 / (1 / T25 + math.log(rn / R25) / beta) - 273.15


# beta implied by the record statement that the 10 kOhm divider's sensitivity peaks near 85-90 degC (controller-io.md):
for t in (85.0, 90.0):
    print("  beta implied by R_NTC(%.0f degC) = 10 kOhm and R25 = 100 kOhm: %.0f K" % (t, math.log(10) / (1 / (t + 273.15) - 1 / T25) * -1))
worst = {}


def front_error(tc, beta, rd_factor, ileak):
    rn = rn_of(tc, beta)
    rd_act = RD * rd_factor
    # node with the leakage current i drawn out of the sense node through the Thevenin resistance (divider || NTC) + series resistor
    vth = VDD * rn / (rn + rd_act)
    rth = rn * rd_act / (rn + rd_act) + RSER * rd_factor
    v = vth + ileak * rth
    v = min(max(v, 1e-6), VDD - 1e-6)
    rn_est = RD * v / (VDD - v)       # firmware takes the nominal divider
    return t_of(rn_est, beta) - tc


for lab, hi, lo in (("1 % 100 ppm/K divider (C25804)", R_HI, R_LO), ("0.1 % 25 ppm/K divider (C95204)", 1 + 0.001 + 25e-6 * DT, 1 - 0.001 - 25e-6 * DT)):
    print(" %s" % lab)
    for beta in (3000.0, 3838.0, 3950.0, 4097.0, 4500.0):
        row = []
        for tc in (25.0, 60.0, 88.0, 100.0, 150.0):
            e = max(abs(front_error(tc, beta, f, i)) for f in (lo, hi) for i in (-ILEAK, 0.0, ILEAK))
            row.append("%5.2f" % e)
            worst[(lab, beta, tc)] = e
        print("   beta %5.0f K : worst front-end error (degC) at 25/60/88/100/150 degC = %s" % (beta, " ".join(row)))
print("  ADC offset and gain error are typical only in Table 78 / Table 176 (rev V: EO +-10 LSB, EG +-15 LSB); not a bound, so not in the sum:")
dvdt = VDD / 4 * 3950 / (88 + 273.15) ** 2
print("   25 LSB typ = %.2f mV = %.3f degC at 88 degC, beta 3950 K" % (25 * 3.3 / 65536 * 1e3, 25 * 3.3 / 65536 / dvdt))
print("  This row does not close: beta and the element tolerance are pending in the records; the ADC accuracy is typical only.")

# ================================================================= flow input
print("\n== flow input level (PC6, FT_h)")
for lab, v in (("push-pull meter output at 5 V rail high (+2.5 %)", 5.125), ("push-pull at 5.25 V", 5.25), ("open-drain with the 3.3 V pull-up", 3.6)):
    print("  %s: pin %.3f V ; operating limit < 5.5 V (Table 14 note: VIN <= min(VDD..)+3.6 V and < 5.5 V) margin %.3f V ; Table 11 limit min(VDD+4, 6) = 6.0 V margin %.3f V" % (lab, v, 5.5 - v, 6.0 - v))
    check("flow pin below 5.5 V: %s" % lab, v < 5.5)
RP, RS_, CF = val(S2, "R520"), val(S2, "R521"), val(S2, "C520")
tau = (RP * R_HI + RS_ * R_HI) * CF * C_HI
fc = 1 / (2 * math.pi * tau)
print("  open-drain rising edge: tau = (R520 + R521) * C520 = %.0f us ; 10-90 %% rise %.0f us ; corner %.0f Hz" % (tau * 1e6, 2.2 * tau * 1e6, fc))
print("  pulse rate passed at the corner, per millilitre per second of the pump's 7.0 mL/s full scale (estimate in the record): K up to %.0f pulses/L" % (fc / 7.0 * 1000))
print("  open-drain sink current when the meter output is low: %.3f mA at 3.6 V ; the meter's low level at that current is not read." % (3.6 / (RP * R_LO) * 1e3))

# ================================================================= I2C pull-ups
print("\n== BUSL-1: pull-ups of the two I2C buses, Standard-mode")
TR_MAX = 1000e-9       # UM10204 Rev 7.0 Table 11: Standard-mode rise time max 1000 ns
CB_MAX = 400e-12       # UM10204 Table 11: Cb max 400 pF Standard-mode
VOL_SPEC, IOL_SPEC = 0.4, 3e-3   # UM10204 Table 10: VOL1 max 0.4 V at 3 mA sink, Standard-mode
rp, rsr = val(S2, "R525"), val(S2, "R523")
for vdd in (3.0, 3.3, 3.6):
    pass
rp_min = (VDDA_MAX - VOL_SPEC) / IOL_SPEC
print("  Rp(min) = (3.6 - 0.4) / 3 mA = %.0f Ohm (UM10204 equation 2 at VDD = 3.6 V, the rail's datasheet-maximum)" % rp_min)
rp_hi = rp * R_HI
rs_hi = rsr * R_HI
cb_allowed = TR_MAX / (0.8473 * (rp_hi + rs_hi))
print("  fitted Rp = %.0f Ohm (up to %.0f Ohm with tolerance and 25..70 degC), Rs = %.0f Ohm (up to %.0f Ohm)" % (rp, rp_hi, rsr, rs_hi))
print("  Rp(max) at Cb = 400 pF = 1000 ns / (0.8473 * 400 pF) = %.0f Ohm" % (TR_MAX / (0.8473 * CB_MAX)))
print("  bus capacitance the rise time allows with Rp+Rs at their highest: %.0f pF (>= 400 pF bus limit)" % (cb_allowed * 1e12))
check("Rp(min) <= Rp at its lowest", rp_min <= rp * R_LO)
check("Cb allowed by tr >= 400 pF", cb_allowed >= CB_MAX)
check("Rp at its highest <= Rp(max) at 400 pF", (rp_hi + rs_hi) <= TR_MAX / (0.8473 * CB_MAX))
# bus capacitance budget the cable may use
c_pins = 10e-12 + 10e-12 + 2 * 0.55e-12 + 10e-12    # sensor Ci (UM10204 Table 10, 10 pF max), controller pin (10 pF, UM10204 limit; DS12110 CIO 5 pF typ),
                                                    # TVS Cd 0.55 pF max, BAT54S Cd 10 pF max (VR 1 V)
print("  pins on the line: sensor 10 pF + controller pin 10 pF + TVS 0.55 pF + BAT54S 10 pF = %.1f pF ; left for pads, header and cable within 400 pF = %.1f pF" % (c_pins * 1e12, (CB_MAX - c_pins) * 1e12))
# low-level margin through Rs
for vdd in (3.0, 3.3, 3.6):
    il = (vdd - VOL_SPEC) / (rp * R_LO)
    vlow_ctrl = VOL_SPEC + il * rs_hi
    margin = 0.3 * vdd - vlow_ctrl
    need = 0.1 * vdd
    print("  VDD %.1f V: sensor pulls low (0.4 V) through Rs: controller pin sees %.3f V; VIL(max) 0.3 VDD = %.3f V; margin %.3f V vs noise margin 0.1 VDD = %.3f V" % (vdd, vlow_ctrl, 0.3 * vdd, margin, need))
    check("low-level noise margin at VDD %.1f V" % vdd, margin >= need)

# ================================================================= PTC feeds
print("\n== short-safe 3.3 V feeds: Bourns MF-NSMF012-2 (Rev. V 07/17)")
IHOLD_70, IHOLD_23, ITRIP_23, RMIN, R1MAX, VMAX, IMAX, T_TRIP = 0.08, 0.12, 0.29, 1.35, 8.5, 30.0, 10.0, 0.20
ISENSOR = 3e-3    # XDB401 family, maker's page (xdbsensor.com), operating current <= 3 mA, read 2026-10-29
print("  sensor %.1f mA vs hold current at 70 degC %.0f mA: %.0fx ; drop across the PTC at R1max %.1f Ohm = %.1f mV" % (ISENSOR * 1e3, IHOLD_70 * 1e3, IHOLD_70 / ISENSOR, R1MAX, ISENSOR * R1MAX * 1e3))
ishort = VDDA_MAX / RMIN
print("  hard short at a header: %.2f A (3.6 V / %.2f Ohm) until it trips (<= %.2f s at 1.0 A or more, 23 degC) ; Imax %.0f A, Vmax %.0f V" % (ishort, RMIN, T_TRIP, IMAX, VMAX))
check("short current within Imax", ishort <= IMAX)
# isolating link in the same path (R540..R544): UNI-ROYAL Thick Film Chip Resistors data sheet Feb.12 2019 V.3, section 7 Ratings:
# 1206 jumper (value below 50 mOhm) rated current 2 A, maximum overload current 10 A (the 0603 jumper: 1 A and 2 A)
J1206_OVERLOAD, J0603_OVERLOAD = 10.0, 2.0
print("  link in the short-circuit path, 1206 jumper: overload rating %.0f A against %.2f A (a 0603 jumper's %.0f A would not do)" % (J1206_OVERLOAD, ishort, J0603_OVERLOAD))
check("1206 link overload rating covers the short current", J1206_OVERLOAD >= ishort)
check("a 0603 link would not (reason for the 1206)", J0603_OVERLOAD < ishort)
check("sensor current below the 70 degC hold current", ISENSOR < IHOLD_70)

print("\nSUMMARY: %d checks failed" % len(fails))
for f in fails:
    print("  FAILED:", f)
sys.exit(1 if fails else 0)
