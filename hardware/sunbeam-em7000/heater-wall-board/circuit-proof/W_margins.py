#!/usr/bin/env python3
"""Arithmetic of the heater wall board's value-critical circuits (LED drive path, gate network, hold-off,
varistor) for hardware/sunbeam-em7000/heater-wall-board/circuit-proof.md.

Run:  python3 -I W_margins.py > W_margins.log      (prints every figure the proof rows quote; exit 0 when no check fails)

Every constant names its source on its line. The main board's drive stage is re-derived with the same constants and
method as hardware/sunbeam-em7000/main-board/circuit-proof/D_margins.py section 5, with the wall board's Lite-On
MOC3083 figures in place of the onsemi MOC3083M's.
"""
import math
import sys

fails = []


def check(name, ok, text):
    print(("PASS  " if ok else "FAIL  ") + name + ": " + text)
    if not ok:
        fails.append(name)


# ---- shared constants
V5_MIN, V5_MAX = 4.75, 5.25      # main-board D_margins.py: +5V rail 4.75..5.25 V (constraints record, 5 V rail +/-5 %)
TOL = 0.01                       # all resistors 1 %
R_LED = 180.0                    # main board R763 / R773 (sheet 720)
RDS_2V5 = 0.048                  # main board D_margins.py: AO3400A RDS(on) < 48 mOhm at 2.5 V, 25 degC
RDS_TJ = RDS_2V5 * (38.0 / 26.5)  # main board D_margins.py: x(38/26.5) for 125 degC
rds_i = 0.03 * RDS_TJ            # main board D_margins.py: drop of the sink at 30 mA
TEMP_AIR = 70.0                  # constraints record: enclosure air 70 degC (assumption until bring-up C13)
VPK = 253 * math.sqrt(2)         # separation-basis.yaml working voltage 253 V rms, 357.8 V peak

# ---- (a) LED drive path with the Lite-On MOC3083 figures (DS70-2001-027 Rev B)
print("== (a) heater LED stage: main board R763/R773 = 180 ohm, Q761/Q771, +5V_WB, wall board Lite-On MOC3083 LED")
VF_MAX = 1.4          # Lite-On p.6: VF max 1.4 V at IF = 20 mA
IFT_MAX = 5e-3        # Lite-On p.6: IFT max 5 mA, main terminal voltage 3 V
COLD = 1.5            # carried from the main board (onsemi MOC3083M/D Fig. 3, -40 degC normalised IFT 1.5); the Lite-On sheet's Fig. 3 starts at 20 degC and states no cold figure
AGEING = 1.20         # carried from the main board (onsemi MOC3052M/D worked example, 120 %); the Lite-On sheet gives none
IF_NEED = IFT_MAX * COLD * AGEING
IF_ABS = 50e-3        # Lite-On p.5: IF 50 mA
PD_25 = 120e-3        # Lite-On p.5: input power dissipation 120 mW at 25 degC (no derating figure on the sheet)
FIG1_FLAT_C, FIG1_END_C, FIG1_END_MA = 50.0, 100.0, 18.0  # Lite-On p.7 Fig. 1, read off the plot: 50 mA to 50 degC, falling straight to about 18 mA at 100 degC
if_derated_70 = IF_ABS - (IF_ABS - FIG1_END_MA * 1e-3) * (TEMP_AIR - FIG1_FLAT_C) / (FIG1_END_C - FIG1_FLAT_C)
FIG3_IFT_20C = 6.7e-3  # Lite-On p.7 Fig. 3, read off the plot: IFT about 6.7 mA at 20 degC falling to about 6.0 mA at 100 degC, at VP 6 V, RL 100 ohm (the table's 5 mA max is at 3 V)
i_min = (V5_MIN - VF_MAX - rds_i) / (R_LED * (1 + TOL))
check("heater LED IF_min (cable resistance 0)", i_min >= IF_NEED,
      "IF_min %.2f mA vs needed %.2f mA (5 mA x1.5 x1.2): margin %.2f mA (x%.2f). Main board with the onsemi figures: 17.87 mA vs 9.0 mA (x1.99)"
      % (i_min * 1e3, IF_NEED * 1e3, (i_min - IF_NEED) * 1e3, i_min / IF_NEED))
rc = (V5_MIN - VF_MAX - rds_i) / IF_NEED - R_LED * (1 + TOL)
check("heater LED cable allowance", rc > 0,
      "loop resistance the cable may add (+5V_WB conductor and LED-return conductor together) = %.0f ohm at the lowest rail (main board: 179 ohm)" % rc)
need_fig3 = FIG3_IFT_20C * AGEING
need_fig3_cold = FIG3_IFT_20C * COLD * AGEING
check("Fig. 3 sensitivity (no cold factor)", i_min >= need_fig3,
      "Fig. 3 reading 6.7 mA x1.2 = %.2f mA: margin x%.2f; with the carried cold factor 1.5 on top %.2f mA: margin x%.2f, cable allowance %.0f ohm"
      % (need_fig3 * 1e3, i_min / need_fig3, need_fig3_cold * 1e3, i_min / need_fig3_cold,
         (V5_MIN - VF_MAX - rds_i) / need_fig3_cold - R_LED * (1 + TOL)))
i_max = V5_MAX / (R_LED * (1 - TOL))
p_led = VF_MAX * (V5_MAX - VF_MAX) / (R_LED * (1 - TOL))
pd_70 = PD_25 * if_derated_70 / IF_ABS
check("heater LED upper limits", i_max <= IF_ABS and i_max <= if_derated_70,
      "IF bound (VF=0) %.1f mA vs 50 mA, and vs %.1f mA at %.0f degC air by Fig. 1 (x%.2f); emitter power at VF 1.4 V %.1f mW vs %.1f mW "
      "(120 mW scaled by Fig. 1's derating: the sheet states no power derating)"
      % (i_max * 1e3, if_derated_70 * 1e3, TEMP_AIR, if_derated_70 / i_max, p_led * 1e3, pd_70 * 1e3))
print("NOTE  IF bound %.1f mA against %.0f mA at 100 degC by Fig. 1: over; the opto-triac stands in 45 degC (owner) or 70 degC (conservative) air, not 100 degC" % (i_max * 1e3, FIG1_END_MA * 1.0))

# ---- (b) gate network
print("\n== (b) gate network R101+R102 / R201+R202 = 2 x 200 ohm 1206 (UNI-ROYAL C18002) in series")
ITSM = 1.0            # Lite-On p.5: peak repetitive surge current 1 A, PW 100 us, 120 pps
R_G_NOM = 400.0
R_G_MIN = R_G_NOM * (1 - TOL)
ipk = VPK / R_G_MIN
check("opto-triac surge limit", ipk <= ITSM,
      "R = VPK / ITSM: minimum %.1f ohm; fitted %.0f ohm (-1%% = %.0f): peak %.3f A <= 1 A (x%.2f)" % (VPK / ITSM, R_G_NOM, R_G_MIN, ipk, ITSM / ipk))
VTM = 3.0             # Lite-On p.6: VTM max 3.0 V at ITM 100 mA peak
IGT, VGT, IGM = 50e-3, 1.3, 4.0  # ST BTA16-600BRG as the schematic sheet cites it (Doc ID 7471 Rev 9): IGT 50 mA (quadrants I-II-III, B grade), VGT 1.3 V max (Table 4); IGM 4 A is the family figure of the main board's triac sheet, used here only as a bound and not read from this sheet
VINH_MAX = 20.0       # Lite-On p.6: inhibit voltage 20 V max
v_fire = VTM + IGT * R_G_NOM * (1 + TOL) + VGT
v_lo = 216 * math.sqrt(2)
ang = math.degrees(math.asin(v_fire / v_lo))
check("gate drive reaches IGT", v_fire < v_lo and ipk <= IGM,
      "line voltage that drives IGT max through %.0f ohm = %.1f V (%.1f deg after the crossing at 216 V rms); the opto fires below %.0f V, its gate current then keeps rising with the line (the opto stays latched, IH typ 0.4 mA); peak gate current %.2f A <= IGM"
      % (R_G_NOM * (1 + TOL), v_fire, ang, VINH_MAX, ipk))
v_half = VPK / 2
check("working voltage per 1206", v_half <= 200.0,
      "each resistor carries half of the peak: %.1f V vs 200 V rated (C18002 catalogue page): margin %.1f V (%.1f %%); class share 1" % (v_half, 200.0 - v_half, 100 * (200.0 - v_half) / 200.0))
p_fire = IGT ** 2 * 200 * (1 + TOL)
print("   power: during the firing ramp each resistor passes at most IGT %.0f mA: %.3f W for the ramp from the opto's turn-on (<= %.0f V) to the triac's latch (%.1f V), "
      "(%.1f - %.0f) V at the line's slope 2 pi f VPK = %.0f V/ms gives %.3f ms, %.2f mW average at 100 firings a second (250 mW rated; the share 0.6 gives 150 mW)"
      % (IGT * 1e3, p_fire, VINH_MAX, v_fire, v_fire, VINH_MAX, 2 * math.pi * 50 * VPK / 1000, (v_fire - VINH_MAX) / (2 * math.pi * 50 * VPK / 1000),
         p_fire * (v_fire - VINH_MAX) / (2 * math.pi * 50 * VPK / 1000) * 1e-3 * 100 * 1e3))
irms_fault = (253 - VTM) / R_G_NOM
print("   gate-to-MT1 short fault (a shorted triac gate): %.2f A rms through the 400 ohm, peak %.2f A, %.0f W in the two resistors: they open; the heater stays off (fails off); the opto-triac's 1 A is a 100 us rating and its single-cycle rating is not stated by the sheet"
      % (irms_fault, VPK / R_G_NOM, irms_fault ** 2 * R_G_NOM))

# ---- (c) hold-off
print("\n== (c) hold-off in reset, unpowered and with the cable loose; no gate-MT1 resistor")
IDRM2 = 500e-6        # Lite-On p.6: leakage in inhibited state 500 uA max (LED at rated IFT, rated VDRM, off state)
IDRM1 = 500e-9        # Lite-On p.6: peak blocking current 500 nA max at VDRM 800 V (LED off)
v2 = IDRM2 * R_G_NOM * (1 + TOL)
v1 = IDRM1 * R_G_NOM * (1 + TOL)
check("leakage x gate network against VGT", v2 < VGT,
      "IDRM2 500 uA x %.0f ohm = %.3f V vs VGT 1.3 V max: margin x%.2f; gate current 0.5 mA vs IGT 50 mA (x100). With the LED off the sheet's figure is IDRM1 500 nA: %.3f mV" % (R_G_NOM * (1 + TOL), v2, VGT / v2, v1 * 1e3))
IDSS = 5e-6           # main board circuit-proof.md hold-off table (controller in reset row): Q off, LED current at most IDSS 5 uA
print("   LED current in reset / unpowered: at most %.0f uA (main board row), %.0f times under IFT max 5 mA; cable loose: +5V_WB or HEAT_x_LED_K open gives 0 A" % (IDSS * 1e6, IFT_MAX / IDSS))

# ---- (d) varistor 07D471K
print("\n== (d) varistor 07D471K (Zhuhai Hongjiacheng Rev 1.2) across each triac")
V1MA_MIN, VAC_MAX, VCLAMP10A, I_SURGE = 423.0, 300.0, 775.0, 1200.0
check("stays off in service", V1MA_MIN > VPK and VAC_MAX > 253,
      "V1mA min %.0f V vs peak %.1f V: x%.2f; 300 VAC vs 253 V: x%.2f" % (V1MA_MIN, VPK, V1MA_MIN / VPK, VAC_MAX / 253))
print("   clamp %.0f V at 10 A vs triac VDRM 600 V: x%.2f over (VDSM 700 V for 10 ms: x%.2f over); vs opto-triac VDRM 800 V: %.0f V under (%.1f %%)"
      % (VCLAMP10A, VCLAMP10A / 600, VCLAMP10A / 700, 800 - VCLAMP10A, 100 * (800 - VCLAMP10A) / 800))
print("   2.5 kV surge (separation-basis overvoltage category II basic): current (2500 - 775) / Z; 1200 A is met for Z >= %.2f ohm; at 2 ohm (not read) %.0f A" % ((2500 - VCLAMP10A) / I_SURGE, (2500 - VCLAMP10A) / 2))
print("   opto-triac through the 396 ohm gate network at the clamp voltage: %.2f A against ITSM 1 A (100 us rating, microsecond withstand not stated)" % (VCLAMP10A / R_G_MIN))

print("\nexit %d" % (1 if fails else 0))
sys.exit(1 if fails else 0)
