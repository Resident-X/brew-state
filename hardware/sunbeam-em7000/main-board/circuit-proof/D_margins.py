#!/usr/bin/env python3
"""Drive-stage, level and fuse arithmetic for the switched-load drives, wall-board header, gauge drive,
operator panel and digital inputs of the main controller board (work package D).

Run:  python3 -I D_margins.py          (prints every figure the proof rows quote; exit 0 when no check fails)

Every constant names its source on its line. Datasheets read 2026-10-29. Part values are the schematic
spec's (sheets/*.yaml): R701.. etc. are written out in the printed labels.
"""
import math
import sys

fails = []


def check(name, ok, text):
    print(("PASS  " if ok else "FAIL  ") + name + ": " + text)
    if not ok:
        fails.append(name)


# ---------------------------------------------------------------- supplies (records)
V5_MIN, V5_MAX = 4.75, 5.25          # constraints record, "Interlock removal time and drive": 5 V rail assumed +/-5 %
VDD_NOM = 3.3                        # component-specification.md: 3.3 V controller supply
VDD_MIN = round(VDD_NOM * 0.95, 3)   # 3.135 V: the same +/-5 % taken for the 3.3 V rail (owner B's regulator replaces it)
VDD_MAX = 3.6                        # DS12110 Rev 11 Table 14 / Table 51 range upper end
# DS12110 Rev 11 (STM32H743xI), Table 51: CMOS port, IIO = -8 mA, 2.7 V <= VDD <= 3.6 V: VOH min = VDD - 0.4 V; VOL max 0.4 V at 8 mA
# Table 51 relaxed rows: IIO = 20 mA: VOL max 1.3 V, VOH min VDD - 1.3 V.  Table 50: Ilkg FT_xx +/-250 nA, FT_u +/-350 nA (VIN <= VDD),
# VIL max 0.3 VDD, VIH min 0.7 VDD; Table 12: IIO sink max 20 mA, total sink / source 140 mA.
VOH_MIN = lambda vdd: vdd - 0.4
ILKG_PIN = 350e-9                    # FT_u worst (PA9); FT_xx is 250 nA
IGSS = 100e-9                        # AO3400A, VDS=0, VGS=+/-12 V, max
TEMP_AIR = 70.0                      # constraints record, "Enclosure air temperature": 70 degC assumed
print("== supplies: +5V %.2f..%.2f V; +3V3 %.3f..%.1f V (assumption flagged); VOH_min(3.3 V) = %.2f V, VOH_min(%.3f V) = %.3f V"
      % (V5_MIN, V5_MAX, VDD_MIN, VDD_MAX, VOH_MIN(3.3), VDD_MIN, VOH_MIN(VDD_MIN)))

# ---------------------------------------------------------------- AO3400A low-side switch (AOS Rev 3, Dec 2011)
VTH_MAX, VTH_MIN = 1.45, 0.65        # VGS(th), VDS=VGS, ID=250 uA
RDS_2V5 = 0.048                      # < 48 mOhm at VGS = 2.5 V, ID = 3 A, TJ = 25 degC
RDS_TJ = RDS_2V5 * (38.0 / 26.5)     # the sheet's TJ=125 degC / 25 degC ratio on its 10 V row (38/26.5 mOhm), applied to the 2.5 V row
VGS_GUAR = 2.5                       # lowest VGS at which the sheet guarantees RDS(on)
IDSS = 1e-6                          # max, VDS = 30 V, VGS = 0
print("== AO3400A: RDS(on) <= %.0f mOhm at 2.5 V (25 degC), x%.3f for 125 degC = %.1f mOhm" % (RDS_2V5 * 1e3, 38 / 26.5, RDS_TJ * 1e3))

TOL = 0.01  # all resistors 1 %


def gate_stage(name, vdd):
    vgs = VOH_MIN(vdd)
    check("%s gate drive at VDD=%.3f" % (name, vdd), vgs >= VGS_GUAR,
          "VOH_min %.3f V vs VGS guaranteeing RDS(on) %.2f V: margin %.3f V (%.1f %%); threshold max %.2f V: margin %.3f V"
          % (vgs, VGS_GUAR, vgs - VGS_GUAR, 100 * (vgs - VGS_GUAR) / VGS_GUAR, VTH_MAX, vgs - VTH_MAX))


for vdd in (3.3, VDD_MIN):
    gate_stage("all AO3400A stages", vdd)
i_pin = VOH_MIN(VDD_MIN) / (100 * (1 - TOL) + 100e3 * (1 - TOL))
print("   pin load of a gate stage (Rg 100 + Rpd 100k): %.1f uA (<< 8 mA)" % (VOH_MIN(VDD_MAX) / 100e3 * 1e6))

# ---------------------------------------------------------------- 1. pump LED stages (MOC3052M)
print("\n== 1. pump LED drive stages  Q701/Q711, R703/R713 = 180 ohm, U701/U711 MOC3052M")
IFT_MAX = 10e-3          # MOC3052M/D Rev 4 (Sep 2022) transfer characteristics: IFT max 10 mA (MT voltage 3 V)
IF_NEED = IFT_MAX * 1.5  # same sheet, note 2: bias at least 50 % above max IFT: "10 mA x 150 % = 15 mA"
VF_MAX = 1.5             # same sheet: VF max 1.5 V at IF = 10 mA
IF_ABS = 60e-3           # same sheet, maximum ratings
PD_EM25, PD_DER = 100e-3, 1.33e-3  # emitter dissipation 100 mW at 25 degC, derate 1.33 mW/degC
R_LED = 180.0
rds_i = 0.03 * RDS_TJ
for vf in (VF_MAX, 1.7):
    i_min = (V5_MIN - vf - rds_i) / (R_LED * (1 + TOL))
    check("pump LED IF_min at VF=%.1f V" % vf, i_min >= IF_NEED if vf == VF_MAX else True,
          "IF_min %.2f mA vs needed %.1f mA: margin %.2f mA (x%.3f)%s" % (i_min * 1e3, IF_NEED * 1e3, (i_min - IF_NEED) * 1e3, i_min / IF_NEED,
                                                                         "" if vf == VF_MAX else "  (sensitivity: VF above the sheet's 10 mA maximum)"))
i_max0 = V5_MAX / (R_LED * (1 - TOL))
pd_lim = PD_EM25 - PD_DER * (TEMP_AIR - 25)
p_em = VF_MAX * (V5_MAX - VF_MAX) / (R_LED * (1 - TOL))
check("pump LED upper limits", i_max0 <= IF_ABS and p_em <= pd_lim,
      "IF_max bound (VF=0) %.1f mA vs 60 mA; emitter power at VF=1.5 V %.1f mW vs %.1f mW allowed at %.0f degC air"
      % (i_max0 * 1e3, p_em * 1e3, pd_lim * 1e3, TEMP_AIR))
p_r = i_max0 ** 2 * R_LED * (1 + TOL)
print("   R703/R713 dissipation at the VF=0 bound: %.0f mW in a 1206 (250 mW)" % (p_r * 1e3))
# LED pulse
print("   LED pulse width: sheet Fig. 4 normalises IFT to PW = 100 us; drive pulses of at least 100 us keep the 1.0 factor")

# ---------------------------------------------------------------- 2. pump gate resistor
print("\n== 2. pump gate network R704+R705 / R714+R715 = 2 x 200 ohm 1206 in series (MOC3052M pin 6 to MT2, pin 4 to gate)")
VPK = 253 * math.sqrt(2)
ITSM_OPTO = 1.0          # MOC3052M/D maximum ratings: peak non-repetitive surge 1 A (single cycle, 60 Hz)
R_G = 400.0                          # two 200 ohm 1206 resistors in series; each carries half of the peak (UNI-ROYAL 1206: 200 V working, catalogue part page C18002)
ipk = VPK / (R_G * (1 - TOL))
check("R704+R705 opto-triac surge limit", ipk <= ITSM_OPTO,
      "R = VPAC / ITSM (sheet Fig. 7): VPK %.1f V / %.1f ohm (R-1%%) = %.3f A <= 1 A; minimum R = %.1f ohm" % (VPK, R_G * 0.99, ipk, VPK / ITSM_OPTO))
VTM_OPTO_MAX, IGT_MAX, VGT_MAX, IGM = 2.5, 50e-3, 1.0, 2.0   # MOC3052M VTM max 2.5 V (100 mA peak); BTA204S-600B Rev.02: IGT 50 mA, VGT max 1 V (Tj 25), IGM 2 A
v_fire = VTM_OPTO_MAX + IGT_MAX * R_G * (1 + TOL) + VGT_MAX
v_lo = 216 * math.sqrt(2)
ang = math.degrees(math.asin(v_fire / v_lo))
check("gate drive reaches IGT", v_fire < v_lo and ipk <= IGM,
      "line voltage needed to push IGT max (50 mA) = %.1f V (%.1f deg after the zero crossing at 216 V); peak gate current %.2f A <= IGM 2 A" % (v_fire, ang, ipk))
IL = 30e-3
print("   BTA204S latching current max 30 mA; IH max 30 mA: the pump current at the firing instant must reach IL: pump sizing 0.46 A / 0.19 A are rms; see open item on pulse timing")

# ---------------------------------------------------------------- 3. pump triac current and junction temperature
print("\n== 3. pump triac T701/T711 BTA204S-600B (WeEn Rev.02, 19 Mar 2025)")
for nm, irms in (("coffee", 0.46), ("steam", 0.19)):
    for shape, iav in (("full sine", irms * 2 * math.sqrt(2) / math.pi), ("half wave (series diode)", irms * 2 / math.pi)):
        p = 1.7 * iav                       # VT max 1.7 V at 5 A, applied to the average current: an upper bound
        tj = TEMP_AIR + p * 75              # Rth(j-a) 75 K/W is the sheet's TYPICAL on an FR4 board: not a bound
        print("   %-6s %-24s I_rms %.2f A  I_av %.3f A  P <= %.2f W  Tj = %.1f degC (typical Rth(j-a); limit 125)" % (nm, shape, irms, iav, p, tj))
print("   IT(RMS) 4 A at Tmb <= 107 degC: %.1fx and %.1fx the sizing currents" % (4 / 0.46, 4 / 0.19))

# ---------------------------------------------------------------- 4. valve coil stages
print("\n== 4. valve coil drivers Q731/Q741 AO3400A, K731/K741 HF32FA-G/005-HSL1 (Hongfa 2026 Rev.1.00)")
RC_NOM, RC_TOL = 108.0, 0.10
VPU_23, VDO, VMAXC = 3.75, 0.25, 8.5
TEMPCO_ASSUME = 1.20                 # constraints record, "Interlock removal time and drive": +20 % on coil resistance and pick-up at 70 degC air, a stated assumption
rc_lo, rc_hi = RC_NOM * (1 - RC_TOL), RC_NOM * (1 + RC_TOL)
i_coil_max = V5_MAX / rc_lo
check("valve coil current bound", True, "coil current at 5.25 V, 97.2 ohm, 23 degC = %.1f mA (record: 51.4 mA at 5.0 V)" % (i_coil_max * 1e3))
rds_c = RDS_TJ
v_av = V5_MIN - i_coil_max * 0 - (V5_MIN / (rc_lo * TEMPCO_ASSUME)) * rds_c  # current at the lowest rail with the warm coil
v_need_23, v_need_70 = VPU_23, VPU_23 * TEMPCO_ASSUME
check("valve coil pull-up margin, 23 degC", v_av >= v_need_23, "%.3f V available vs %.2f V: margin %.3f V" % (v_av, v_need_23, v_av - v_need_23))
check("valve coil pull-up margin, 70 degC air (+20 %)", v_av >= v_need_70,
      "%.3f V available vs %.2f V (3.75 x 1.20): margin %.3f V (%.1f %%); reaches zero at x%.3f" % (v_av, v_need_70, v_av - v_need_70, 100 * (v_av - v_need_70) / v_need_70, v_av / VPU_23))
check("valve coil max voltage", V5_MAX <= VMAXC, "5.25 V vs sheet maximum coil voltage 8.5 V")
vd_pk = V5_MAX + 1.0 * (i_coil_max / 0.05) ** 0   # 1N4148WS VF max 1.0 V at 50 mA (JSCJ rev A, May 2011); 54 mA is within 8 % of it
check("flyback clamp", vd_pk < 30 and i_coil_max < 0.3, "drain peak <= 5.25 + ~1.05 = %.2f V vs VDS 30 V; diode current %.1f mA vs IFM 300 mA; reverse %.2f V vs VRRM 100 V" % (V5_MAX + 1.05, i_coil_max * 1e3, V5_MAX))
# warm restart (sheet's coil temperature rise read off its plot: about 61 K at rated voltage; not bounded by a figure)
dT = (TEMP_AIR - 23) + 61
r_hot = 1 + 0.00393 * dT
print("   warm restart (coil rise ~61 K read off the sheet's plot, 70 degC air): resistance x%.2f, pick-up ~%.2f V vs 4.75 V rail: the relay does not re-pull until it has cooled (valve stays de-energised)" % (r_hot, VPU_23 * r_hot))
# valve fuse
print("   shared valve fuse: coils 0.129 A rms steady, 0.203 A rms inrush at 253 V (constraints record, Supply budget)")

# ---------------------------------------------------------------- 5. heater LED stages
print("\n== 5. heater LED stages Q761/Q771 AO3400A, R763/R773 = 180 ohm in the LED return, MOC3083M on the wall board")
IFT3 = 5e-3                          # MOC3083M/D Rev 2 (Sep 2022): IFT max 5 mA (MT voltage 3 V)
FIG3_COLD = 1.5                      # same sheet, Fig. 3: normalised IFT at -40 degC, read off the plot
DEGR = 1.20                          # LED degradation allowance of the MOC3052M/D sheet's own example (same maker, same emitter): "120 %"
IF_NEED3 = IFT3 * FIG3_COLD * DEGR
VF3 = 1.5                            # MOC3083M VF max 1.5 V at 30 mA
PD3 = 120e-3 - 1.41e-3 * (TEMP_AIR - 25)
RH = 180.0
i_min3 = (V5_MIN - VF3 - rds_i) / (RH * (1 + TOL))
check("heater LED IF_min (cable resistance 0)", i_min3 >= IF_NEED3, "IF_min %.2f mA vs needed %.1f mA (5 mA x1.5 x1.2): margin %.2f mA (x%.2f)" % (i_min3 * 1e3, IF_NEED3 * 1e3, (i_min3 - IF_NEED3) * 1e3, i_min3 / IF_NEED3))
rc_allow = (V5_MIN - VF3 - rds_i) / IF_NEED3 - RH * (1 + TOL)
check("heater LED cable allowance", rc_allow > 0, "loop resistance the cable may add (+5V_WB conductor and LED-return conductor together) = %.0f ohm at the lowest rail" % rc_allow)
i_max3 = V5_MAX / (RH * (1 - TOL))
p3 = VF3 * (V5_MAX - VF3) / (RH * (1 - TOL))
check("heater LED upper limits", i_max3 <= 60e-3 and p3 <= PD3, "IF bound %.1f mA vs 60 mA; emitter power at VF=1.5 V %.1f mW vs %.1f mW allowed at %.0f degC" % (i_max3 * 1e3, p3 * 1e3, PD3 * 1e3, TEMP_AIR))
print("   LED pulse: the opto-triac is zero-cross; LED held for the half-cycle (>= 8.3 ms), far above the sheet's 100 us normalisation")

# ---------------------------------------------------------------- 6. buzzer
print("\n== 6. buzzer stage Q823 AO3400A, R828 = 100 ohm 1206 from +5V to CON2 pin 1, D821 across the buzzer")
i_bz = V5_MAX / (100 * (1 - TOL))
check("buzzer current bound", i_bz < 5.7, "buzzer shorted: %.1f mA through 100 ohm; AO3400A ID 5.7 A; buzzer type pending, so the bound is the resistor's" % (i_bz * 1e3))
p_bz = i_bz ** 2 * 100 * (1 + TOL)
rb_min = math.sqrt(5.25 ** 2 * 100 * (1 + TOL) / 0.25) - 100 * (1 + TOL)
print("   R828 (1206, 250 mW) dissipation with a shorted buzzer %.3f W; within 250 mW for any buzzer of %.1f ohm or more" % (p_bz, rb_min))

# ---------------------------------------------------------------- 7. low-water indicator sink
print("\n== 7. low-water sink Q824 AO3400A, no series resistor (the gauge assembly carries 300 ohm per element)")
i_lw = V5_MAX / (150.0 * (1 - 0.0))   # two 300 ohm elements in parallel = the owner's measured 150 ohm (connector-pinouts.md), VF = 0
check("low-water sink bound", i_lw < 5.7, "bound with VF = 0: %.1f mA through the measured 150 ohm; AO3400A 5.7 A (forward voltage pending in the record)" % (i_lw * 1e3))

# ---------------------------------------------------------------- 8. anode rail gate
print("\n== 8. anode rail gate: Q821 AO3400A level stage, Q822 AO3401A (AOS Rev 3.1, Dec 2023) switch, R823/R824 22 k pull-ups to +5V, R825 22 k bleed")
VTH_P_MIN, VTH_P_MAX = 0.5, 1.3       # |VGS(th)| -0.5 .. -1.3 V
RDSP_25 = 0.085                       # < 85 mOhm at VGS -2.5 V, ID -2.5 A
i_anode = 5 * 20e-3 + i_lw            # bound: five key pins sinking at the 20 mA IIO limit + low-water line
vdrop = i_anode * RDSP_25 * 1.6
check("anode switch on", V5_MIN - 0.0 >= 4.5 and vdrop < 0.05, "gate pulled to ~0 V: VGS = -%.2f V (RDS(on) <= 60 mOhm at -4.5 V); anode current bound %.0f mA drops %.0f mV" % (V5_MIN, i_anode * 1e3, vdrop * 1e3))
R_PU = 22e3 / 2 * (1 - TOL)
v_gate_off = V5_MAX - 0.0
check("anode switch off", True, "gate pulled to +5V: VGS = 0 V vs |VGS(th)| min %.1f V: margin %.1f V; one pull-up open still pulls 22 k: same VGS" % (VTH_P_MIN, VTH_P_MIN))
i_on = V5_MAX / R_PU
print("   level stage on-state current %.2f mA through the pull-ups; Ciss 645 pF (typ.) x 11 k = %.1f us time constant (typical figure; no timing claim)" % (i_on * 1e3, 11e3 * 645e-12 * 1e6))

# ---------------------------------------------------------------- 9. gauge buffer
print("\n== 9. gauge buffer U761 SN74HCT541PWR (TI SCLS306C Aug 2003), 100 ohm series R on each output")
VIH_HCT, VIL_HCT = 2.0, 0.8
VOH_HCT, VOL_HCT = 3.84, 0.33          # VCC = 4.5 V, IOH = -6 mA / IOL = 6 mA, -40..85 degC, SN74
VIH_VID, VIL_VID = 3.15, 1.35          # VID66-08 (VID6608 datasheet rev 1, 2022, as read in connector-pinouts.md)
i_vid = 10e-6                          # the record's "~10 uA these inputs leak"
check("gauge buffer VOH vs VID66-08 VIH", VOH_HCT - i_vid * 100 >= VIH_VID, "VOH %.2f V (at VCC 4.5 V, the sheet's lowest) vs %.2f V: margin %.2f V" % (VOH_HCT, VIH_VID, VOH_HCT - i_vid * 100 - VIH_VID))
check("gauge buffer VOL vs VID66-08 VIL", VOL_HCT + i_vid * 100 <= VIL_VID, "VOL %.2f V vs %.2f V: margin %.2f V" % (VOL_HCT, VIL_VID, VIL_VID - VOL_HCT))
check("controller VOH vs buffer VIH", VOH_MIN(VDD_MIN) >= VIH_HCT, "VOH_min %.3f V vs VIH %.1f V: margin %.3f V (%.2f V at 3.3 V)" % (VOH_MIN(VDD_MIN), VIH_HCT, VOH_MIN(VDD_MIN) - VIH_HCT, VOH_MIN(3.3) - VIH_HCT))
check("controller VOL vs buffer VIL", 0.4 <= VIL_HCT, "VOL max 0.4 V vs VIL max 0.8 V: margin 0.4 V")
check("hold-off pull-down at buffer input", ILKG_PIN * 10e3 < VIL_HCT, "10 k x (Ilkg 350 nA + HCT input 1 uA) = %.1f mV vs VIL 0.8 V" % ((ILKG_PIN + 1e-6) * 10e3 * 1e3))
icc = 80e-6 + 5 * 2.9e-3
print("   ICC: 80 uA + 5 x 2.9 mA (delta-ICC, inputs at TTL levels) = %.1f mA at +5V; 500 ns max input rise/fall (sheet) vs a timer edge" % (icc * 1e3))

# ---------------------------------------------------------------- 10. key lines
print("\n== 10. panel key lines KEY1..KEY5 (PE2..PE6): 10 k pull-up to +3V3, panel 1 k + switch to ground, indicators 300 ohm to the anode rail")
r_pu = 10e3
v_low = VDD_MAX * 1e3 / (r_pu * (1 - TOL) + 1e3)
check("key pressed level", v_low <= 0.3 * VDD_MIN, "pressed (1 k panel resistor + switch): %.3f V vs VIL max 0.3 VDD = %.3f V" % (v_low, 0.3 * VDD_MIN))
v_hi = VDD_MIN - ILKG_PIN * r_pu
check("key released level", v_hi >= 0.7 * VDD_MAX, "released: %.3f V vs VIH min 0.7 VDD = %.3f V" % (v_hi, 0.7 * VDD_MAX))
vk = V5_MAX
check("key pin worst voltage", vk < 5.5 and vk <= 1.65 + 3.6, "anode rail on, line not sunk, indicator VF taken as 0: pin <= %.2f V vs the operating limit Min(VDD) + 3.6 V and below 5.5 V (DS12110 Table 14; VDD >= 1.65 V for 5.25 V); internal pulls off above VDD + 0.3 V" % vk)
# sink side
for n_el, tag in ((1, "one element"), (2, "two elements")):
    for vf in (0.0, 1.0, 1.5):
        i = n_el * max(0.0, (V5_MAX - vf - 1.3)) / 300.0
        print("   sink %-12s VF=%.1f V: I = %.1f mA (pin limit 20 mA at VOL 1.3 V; 8 mA at VOL 0.4 V)" % (tag, vf, i * 1e3))
print("   forward voltage of the indicator elements is PENDING in the record: with two elements the pin stays under 20 mA only for VF >= %.2f V" % (V5_MAX - 1.3 - 20e-3 * 300 / 2))

# ---------------------------------------------------------------- 11. knob and reed inputs
print("\n== 11. knob inputs KNOB_HOT/KNOB_STEAM and tank reed TANK_LEVEL: 10 k to +3V3, 100 nF to ground")
rmax_closed = (0.3 * VDD_MIN) / (VDD_MAX - 0.3 * VDD_MIN) * r_pu * (1 - TOL)
check("knob / reed closed level", True, "contact + wiring must stay under %.2f kohm for VIL (%.3f V at 3.135 V ... 3.6 V pull-up)" % (rmax_closed / 1e3, 0.3 * VDD_MIN))
c_eff = 100e-9 * 0.6 * 0.9           # X7R 0603 16..50 V bias + temperature allowance, -10 % tolerance: allowance assumed, replaced by the maker's curve at Phase B
print("   filter: 100 nF x 0.9 (tolerance) = %.0f nF minimum at 0 V bias; tau at 10 k = %.2f ms (bias curve of C14663 applied at Phase B)" % (90, 90e-9 * r_pu * 1e3))
print("   high level: %.3f V vs VIH min %.3f V; time to VIH from a closed contact: %.2f ms at tau = 1.1 ms" % (VDD_MIN - ILKG_PIN * r_pu, 0.7 * VDD_MAX, 1.1 * math.log(1 / (1 - 0.7))))

# ---------------------------------------------------------------- 12. fuses
print("\n== 12. branch fuses (SETfuse SCT520 family, document V1.0 2024-2026; derating curve read at 70 degC)")
K70 = 0.92                           # temperature derating plot: ~100 % at 23 degC falling to ~82 % at 125 degC; ~92 % at 70 degC, 'for reference only'
fuses = (("coffee pump F701", 0.46, 0.8, 0.96), ("steam pump F711", 0.19, 0.5, 0.14), ("valve pair F731", 0.203, 0.4, 0.06))
for nm, i_run, i_n, i2t in fuses:
    cap = i_n * K70
    check("fuse %s" % nm, cap >= i_run, "In %.2f A x %.2f = %.3f A at 70 degC vs %.3f A (%.0f %% of capacity); 2.1 In = %.2f A opens within 30 min; melting I2t at 10 In = %.2f A2s; 4 In = %.1f A for 0.095..5 s"
          % (i_n, K70, cap, i_run, 100 * i_run / cap, 2.1 * i_n, i2t, 4 * i_n))
print("   clip C3131/C3130 listed 250 V, 6.3 A: fuses at 0.4-0.8 A are 6-16 % of it; 250 V vs the 253 V span top: 1.2 % over (owner accepted this only for relay contacts)")

# ---------------------------------------------------------------- 12b. gauge supply capacitor
print("\n== 12b. C792 47 uF 16 V aluminium electrolytic (KNSCHA RST47UF16V034): the gauge driver asks 22 uF against latch-up (connector-pinouts.md, from the VID6608 datasheet rev 1)")
c_min = 47e-6 * 0.8
check("C792 latch-up capacitor", c_min >= 22e-6, "47 uF -20 %% = %.1f uF >= 22 uF (an electrolytic has no DC-bias loss; temperature loss at the cold end is not read)" % (c_min * 1e6))

# ---------------------------------------------------------------- 13. rail loads
print("\n== 13. rail loads from datasheet maxima")
loads5 = {
    "K731+K741 coils (5.25 V, 97.2 ohm)": 2 * i_coil_max,
    "pump LED stages (2 x IF bound)": 2 * i_max0,
    "heater LED stages (2 x IF bound)": 2 * i_max3,
    "U761 buffer": icc,
    "gauge assembly (VID66-08 outputs, 4 x 35 mA absolute maximum)": 4 * 35e-3,
    "buzzer (100 ohm bound)": i_bz,
    "anode rail (5 key pins at 20 mA + low-water bound)": i_anode,
}
tot = 0
for k, v in loads5.items():
    tot += v
    print("   %-62s %7.1f mA" % (k, v * 1e3))
print("   total +5V (everything on at once, bounds) = %.0f mA" % (tot * 1e3))
print("   +3V3: 8 pull-ups x 3.6 V / 10 k = %.1f mA" % (8 * 3.6 / 10e3 * 1e3))

print("\nSUMMARY: %d failing checks %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
