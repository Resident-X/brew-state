#!/usr/bin/env python3
"""NOT FOR MANUFACTURE. The calculations behind circuit-proof.md, rows 1 to 5.

Run from the board's folder:  python3 circuit-proof/proof.py

Every part value is read from the committed netlist circuit-proof/method-proof.cir,
which is the schematic's own export. Every other input is a figure read from the
record named beside it (the constraints record, `constraints.md`, or a datasheet
named in `circuit-proof.md`); nothing here is a tool default or an estimate.
"""
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def netlist_values(path):
    """Each part's value as the netlist gives it, as a number in SI units."""
    scale = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3, "meg": 1e6}
    values = {}
    for line in open(path):
        fields = line.split()
        if len(fields) == 4 and re.fullmatch(r"[RC]\d+", fields[0]):
            m = re.fullmatch(r"([0-9.]+)(meg|[pnumk]?)", fields[3])
            values[fields[0]] = float(m.group(1)) * (scale[m.group(2)] if m.group(2) else 1.0)
    return values


V = netlist_values(os.path.join(HERE, "method-proof.cir"))
R1, C1, C2, C3 = V["R1"], V["C1"], V["C2"], V["C3"]
ok = True


def line(row, text, passed):
    global ok
    ok = ok and passed
    print(f"{row} | {text} | {'MET' if passed else 'NOT MET'}")


# ---- Inputs ---------------------------------------------------------------
# constraints.md
VIN_MIN, VIN_MAX = 4.75, 5.25          # supply input voltage, V
I_LED_MIN, I_LED_MAX = 1e-3, 5e-3      # status LED current, A
IRAIL = 0.1                            # logic rail continuous current, A

# MCP1700 data sheet DS20001826E, page 3, boldface (TJ -40 to +125 C) limits
VR = 3.3                               # nominal output of MCP1700T-3302E/TT, V
ACC = 0.03                             # output voltage regulation, +-3.0 %, at VIN = VR + 1 V, IL = 100 uA
LINE = 0.010                           # line regulation, +-1.0 %/V for (VR + 1) V <= VIN <= 6 V
LOAD = 0.015                           # load regulation, +-1.5 %, IL = 0.1 mA to 250 mA
DROPOUT_MAX = 0.350                    # dropout, 350 mV max at 250 mA; Note 1 adds VR + 3.0 %
VIN_ABS_MIN, VIN_ABS_MAX = 2.3, 6.0    # input operating voltage, V
IOUT_MAX = 0.250                       # maximum output current, A
COUT_MIN, ESR_MAX = 1.0e-6, 2.0        # section 5.2: 1.0 uF minimum, ESR 0 to 2.0 ohm
CIN_MIN = 1.0e-6                       # section 5.1: 1 uF for up to 100 mA

# MSPM0C1104 / MSPS003 data sheet SLASF90E, section 7
VDD_MIN, VDD_MAX = 1.62, 3.6           # 7.3 recommended supply voltage, V
VOL_COND_VDD = 2.7                     # 7.10.1 ODIO VOL condition: VDD >= 2.7 V
VOL_MAX = 0.45                         # 7.10.1 ODIO VOL, IOL,max = 8 mA, -40 to 125 C, V
IOL_MAX_SPEC = 8e-3                    # 7.10.1 the current VOL_MAX is stated for, A
VI_ODIO_MAX = 5.5                      # 7.1 absolute maximum on a 5 V-tolerant open-drain pin, V
CVDD_NOM, CVDD_TOL = 10e-6, 0.20       # 7.3 footnote 1: at least 10 uF, tolerance +-20 % or better

# Vishay VLMG1300 data sheet 82437 rev 1.6: VF max 2.4 V at IF = 20 mA, 25 C; note: VF measured to +-0.1 V
VF_HI = 2.4 + 0.1
IF_ABS_MAX = 30e-3                     # DC forward current, 30 mA

# Vishay CRCW0603 data sheet 20035 rev 14-Apr-2026
R_TOL = 0.01                           # +-1 %
R_TCR = 100e-6                         # +-100 ppm/K
R_TSPAN = 155 - (-55)                  # K, the data sheet's operating range; its TCR reference temperature is not stated
R_P_RATED = 0.1                        # W, rated dissipation P70, 0603

# KEMET part sheets and C1002 X7R data sheet
C2_TOL = 0.20                          # T520B157M006ATE025 tolerance 20 %
C1_TOL = 0.20                          # T520B476M010ATE035 tolerance 20 %
C2_DF, C2_DF_HZ = 0.08, 120.0          # dissipation factor 8 %, 120 Hz, 25 C
C3_TOL = 0.10                          # C0805C106K8RACTU, K = +-10 %
RATED = {"C1": 10.0, "C2": 6.3, "C3": 10.0}  # rated voltages, V

# ---- Rail range (also an input to row 1) --------------------------------------
line_effect = LINE * (VIN_MAX - (VR + 1.0))
vdd_min = VR * (1 - ACC - line_effect - LOAD)
vdd_max = VR * (1 + ACC + line_effect + LOAD)

# ---- Row 1: the status LED drive stage -----------------------------------------
r_min = R1 * (1 - R_TOL) * (1 - R_TCR * R_TSPAN)
r_max = R1 * (1 + R_TOL) * (1 + R_TCR * R_TSPAN)
vol_hi = VOL_MAX
i_max = VIN_MAX / r_min                         # VF and VOL at their lower bound, 0 V each
i_min = (VIN_MIN - VF_HI - vol_hi) / r_max
vf_allowed = VIN_MIN - vol_hi - I_LED_MIN * r_max
line("ROW1", f"R1 {R1:.0f} ohm; R1 min {r_min:.1f} max {r_max:.1f} ohm; I max {i_max*1e3:.3f} mA at 5.25 V with VF and VOL at 0 V; "
     f"I min {i_min*1e3:.3f} mA at 4.75 V with VF {VF_HI:.1f} V, VOL {vol_hi:.2f} V", I_LED_MIN <= i_min and i_max <= I_LED_MAX)
line("ROW1", f"largest VF the 1 mA minimum tolerates {vf_allowed:.3f} V, against the data sheet's {VF_HI:.1f} V at 25 C; "
     f"I max {i_max*1e3:.3f} mA <= VOL current limit {IOL_MAX_SPEC*1e3:.0f} mA and <= LED IF max {IF_ABS_MAX*1e3:.0f} mA",
     vf_allowed > VF_HI and i_max <= IOL_MAX_SPEC and i_max <= IF_ABS_MAX)
p_r1 = i_max ** 2 * r_max
line("ROW1", f"R1 dissipation {p_r1*1e3:.1f} mW at I max, against {R_P_RATED*1e3:.0f} mW rated", p_r1 <= R_P_RATED)

# ---- Row 2: the regulator's capacitors -------------------------------------------
c2_min = C2 * (1 - C2_TOL)
c1_min = C1 * (1 - C1_TOL)
esr_df = C2_DF / (2 * math.pi * C2_DF_HZ * c2_min)
line("ROW2", f"C2 {C2*1e6:.0f} uF min {c2_min*1e6:.0f} uF vs {COUT_MIN*1e6:.1f} uF; ESR bound from DF {esr_df:.3f} ohm vs {ESR_MAX:.1f} ohm; "
     f"C1 {C1*1e6:.0f} uF min {c1_min*1e6:.1f} uF vs {CIN_MIN*1e6:.1f} uF",
     c2_min >= COUT_MIN and esr_df <= ESR_MAX and c1_min >= CIN_MIN)
line("ROW2", f"C1 rated {RATED['C1']:.1f} V >= {VIN_MAX} V; C2 rated {RATED['C2']:.1f} V >= {vdd_max:.3f} V",
     RATED["C1"] >= VIN_MAX and RATED["C2"] >= vdd_max)

# ---- Row 3: the controller's supply capacitor --------------------------------------
line("ROW3", f"C3 {C3*1e6:.0f} uF nominal vs {CVDD_NOM*1e6:.0f} uF at least; tolerance +-{C3_TOL*100:.0f} % vs +-{CVDD_TOL*100:.0f} % or better; "
     f"rated {RATED['C3']:.0f} V >= {vdd_max:.3f} V",
     round(C3, 12) >= round(CVDD_NOM, 12) and C3_TOL <= CVDD_TOL and RATED["C3"] >= vdd_max)

# ---- Row 4: the 3.3 V rail against the regulator's and the controller's ranges ---------
vin_floor = VR * (1 + ACC) + DROPOUT_MAX
line("ROW4", f"VDD min {vdd_min:.3f} V max {vdd_max:.3f} V (line effect {line_effect*100:.2f} %); controller range {VDD_MIN}-{VDD_MAX} V; "
     f"VOL condition VDD >= {VOL_COND_VDD} V", VDD_MIN <= vdd_min and vdd_max <= VDD_MAX and vdd_min >= VOL_COND_VDD)
line("ROW4", f"U1 input {VIN_MIN}-{VIN_MAX} V within {VIN_ABS_MIN}-{VIN_ABS_MAX} V and VIN min >= VR + 3 % + 350 mV = {vin_floor:.3f} V; "
     f"rail current {IRAIL*1e3:.0f} mA <= {IOUT_MAX*1e3:.0f} mA", VIN_ABS_MIN <= VIN_MIN and VIN_MAX <= VIN_ABS_MAX
     and VIN_MIN >= vin_floor and IRAIL <= IOUT_MAX)

# ---- Row 5: the LED node on PA0 against the pin's limit -----------------------------------
line("ROW5", f"PA0 highest voltage {VIN_MAX} V (LED off, node pulled to +5V through R1 and D1) vs {VI_ODIO_MAX} V absolute maximum",
     VIN_MAX <= VI_ODIO_MAX)

print("RESULT | " + ("ALL MET" if ok else "NOT MET"))
sys.exit(0 if ok else 1)
