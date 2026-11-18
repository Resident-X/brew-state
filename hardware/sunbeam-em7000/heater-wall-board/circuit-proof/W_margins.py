#!/usr/bin/env python3
"""Arithmetic of the heater wall board's value-critical circuits (LED drive path, gate network, hold-off,
varistor and surge, opto-triac temperature) for hardware/sunbeam-em7000/heater-wall-board/circuit-proof.md.

Run:  python3 -I W_margins.py > W_margins.log      (prints every figure the proof rows quote; exit 0 when no check fails)

Every constant names its source on its line. The main board's drive stage is re-derived with the same constants and
method as hardware/sunbeam-em7000/main-board/circuit-proof/D_margins.py section 5, with the wall board's onsemi
MOC3083M figures (MOC3083M/D Rev. 2, September 2022), the part the design change of 2026-11-18 fits (the main board's own
source for this stage is the same sheet). Triac: ST BTA16-800BWRG, DS2114 Rev 11 (May 2018).
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

# ---- (a) LED drive path with the onsemi MOC3083M figures (MOC3083M/D Rev. 2)
print("== (a) heater LED stage: main board R763/R773 = 180 ohm, Q761/Q771, +5V_WB, wall board onsemi MOC3083M LED")
VF_MAX = 1.5          # onsemi p.4: VF max 1.5 V at IF = 30 mA (the main board's figure for this stage)
IFT_MAX = 5e-3        # onsemi p.4: IFT max 5 mA, main terminal voltage 3 V
COLD = 1.5            # onsemi p.5 Fig. 3: IFT normalised to 25 degC reads 1.5 at -40 degC (read off the plot), as the main board carries it
AGEING = 1.20         # carried from the main board (onsemi MOC3052M/D worked example, 120 %); the MOC3083M/D sheet states none
IF_NEED = IFT_MAX * COLD * AGEING
IF_ABS = 60e-3        # onsemi p.3: IF continuous 60 mA (the sheet gives no derating curve for IF; the emitter power is derated)
PD_25, PD_SLOPE = 120e-3, 1.41e-3   # onsemi p.3: emitter power 120 mW at 25 degC, derate 1.41 mW/degC above 25 degC
TOPR_MAX = 85.0       # onsemi p.3: operating temperature -40 to +85 degC
TJ_MAX = 100.0        # onsemi p.3: junction temperature -40 to +100 degC
i_min = (V5_MIN - VF_MAX - rds_i) / (R_LED * (1 + TOL))
check("heater LED IF_min (cable resistance 0)", i_min >= IF_NEED,
      "IF_min %.2f mA vs needed %.2f mA (5 mA x1.5 x1.2): margin %.2f mA (x%.2f); the main board's own proof of this stage gives 17.87 mA vs 9.0 mA (x1.99)"
      % (i_min * 1e3, IF_NEED * 1e3, (i_min - IF_NEED) * 1e3, i_min / IF_NEED))
rc = (V5_MIN - VF_MAX - rds_i) / IF_NEED - R_LED * (1 + TOL)
check("heater LED cable allowance", rc > 0,
      "loop resistance the cable may add (+5V_WB conductor and LED-return conductor together) = %.0f ohm at the lowest rail (main board: 179 ohm)" % rc)
i_max = V5_MAX / (R_LED * (1 - TOL))
p_led = VF_MAX * (V5_MAX - VF_MAX) / (R_LED * (1 - TOL))
check("heater LED upper limits", i_max <= IF_ABS,
      "IF bound (VF=0) %.1f mA vs IF 60 mA (x%.2f); emitter power at VF 1.5 V %.1f mW (the maximum, the product VF x IF rising with VF over the range)" % (i_max * 1e3, IF_ABS / i_max, p_led * 1e3))
for t in (45.0, 70.0, 85.0):
    pd_t = PD_25 - PD_SLOPE * (t - 25.0)
    share = 0.75
    print("   emitter power limit at %.0f degC air: %.1f mW (120 mW less 1.41 mW/degC): the %.1f mW above is x%.2f under it; at the integrated-circuit class's power share 0.75 (%.1f mW) x%.2f"
          % (t, pd_t * 1e3, p_led * 1e3, pd_t / p_led, pd_t * share * 1e3, pd_t * share / p_led))
check("emitter power at 70 degC air within the class share", p_led <= 0.75 * (PD_25 - PD_SLOPE * (70.0 - 25.0)),
      "%.1f mW against 0.75 x %.1f mW = %.1f mW" % (p_led * 1e3, (PD_25 - PD_SLOPE * 45) * 1e3, 0.75 * (PD_25 - PD_SLOPE * 45) * 1e3))

# ---- (b) gate network
print("\n== (b) gate network R911+R912 / R921+R922 = 2 x 200 ohm 1206 (UNI-ROYAL C18002) in series")
ITSM = 1.0            # onsemi p.3: ITSM 1 A peak, single cycle 60 Hz sine (the Lite-On sheet's 100 us, 120 pps form is gone with that part)
R_G_NOM = 400.0
R_G_MIN = R_G_NOM * (1 - TOL)
ipk = VPK / R_G_MIN
check("opto-triac surge limit", ipk <= ITSM,
      "R = VPK / ITSM: minimum %.1f ohm; fitted %.0f ohm (-1%% = %.0f): peak %.3f A <= 1 A (x%.2f); the rating is a single 60 Hz cycle, so it bounds a longer pulse than the 100 us the Lite-On sheet gave" % (VPK / ITSM, R_G_NOM, R_G_MIN, ipk, ITSM / ipk))
VTM = 3.0             # onsemi p.4: VTM max 3.0 V at ITM 100 mA peak
IGT, VGT, IGM = 50e-3, 1.3, 4.0  # ST DS2114 Rev 11: IGT 50 mA max quadrants I-II-III and VGT 1.3 V max (Table 4 p.3, BW column), IGM 4 A at 20 us (Table 1 p.2)
VINH_MAX = 20.0       # onsemi p.4: inhibit voltage 20 V max
v_fire = VTM + IGT * R_G_NOM * (1 + TOL) + VGT
v_lo = 216 * math.sqrt(2)
ang = math.degrees(math.asin(v_fire / v_lo))
check("gate drive reaches IGT", v_fire < v_lo and ipk <= IGM,
      "line voltage that drives IGT max through %.0f ohm = %.1f V (%.1f deg after the crossing at 216 V rms); the opto fires below %.0f V, its gate current then keeps rising with the line (the opto stays latched, IH typ 0.5 mA); peak gate current %.2f A <= IGM 4 A (x%.1f)"
      % (R_G_NOM * (1 + TOL), v_fire, ang, VINH_MAX, ipk, IGM / ipk))
v_half = VPK / 2
# UNI-ROYAL V.3 (12 Feb 2019) p.5: RCWV = sqrt(rated power x resistance), never above the maximum working voltage (1206: 200 V);
# overload voltage 2.5 x RCWV or the maximum overload voltage (1206: 400 V), whichever is less; p.4 1/4 W at 70 degC; no pulse rating stated.
P_RATED, MAX_WORK, MAX_OVER = 0.25, 200.0, 400.0
rcwv = min(math.sqrt(P_RATED * 200.0), MAX_WORK)
v_over = min(2.5 * rcwv, MAX_OVER)
v_fire_res = IGT * 200.0 * (1 + TOL)   # voltage across one resistor at a firing, at IGT max, resistor +1 %
print("NOTE  1206 voltage rating of a 200 ohm part (UNI-ROYAL V.3 p.5, amended 2026-11-18, finding 4.2): RCWV = sqrt(%.2f W x 200 ohm) = %.2f V; overload voltage 2.5 x RCWV = %.1f V (the 200 V and 400 V figures are maxima, not the rating); dielectric 500 V; no pulse rating stated" % (P_RATED, rcwv, v_over))
print("NOTE  firing: %.1f V per resistor at IGT %.0f mA = x%.2f of RCWV and %.2f of the overload voltage, for the ramp below; surge case (false trigger at the line peak): %.1f V per resistor = x%.1f of RCWV and x%.1f of the overload voltage: NOT within the resistor's rating; the pulse capability is unsourced (basis: onsemi Fig. 12 p.7, the main board's identical network, rare and fail-safe)"
      % (v_fire_res, IGT * 1e3, v_fire_res / rcwv, v_fire_res / v_over, v_half, v_half / rcwv, v_half / v_over))
i_s = VPK / R_G_MIN
p_s = i_s ** 2 * (R_G_MIN / 2)
print("NOTE  surge case power in each resistor: %.3f A x %.1f V = %.0f W (x%.0f of the 250 mW rating) until the triac latches (microseconds, unsourced): %.0f uJ per us, %.1f mJ at 10 us, %.1f mJ at 100 us (durations assumed); with the 775 V clamp across the pair: %.2f A, %.1f V and %.0f W each"
      % (i_s, v_half, p_s, p_s / P_RATED, p_s, p_s * 10e-3, p_s * 100e-3, 775.0 / R_G_MIN, 775.0 / R_G_MIN * R_G_MIN / 2, (775.0 / R_G_MIN) ** 2 * R_G_MIN / 2))
p_fire = IGT ** 2 * 200 * (1 + TOL)
print("   power: during the firing ramp each resistor passes at most IGT %.0f mA: %.3f W for the ramp from the opto's turn-on (<= %.0f V) to the triac's latch (%.1f V), "
      "(%.1f - %.0f) V at the line's slope 2 pi f VPK = %.0f V/ms gives %.3f ms, %.2f mW average at 100 firings a second (250 mW rated; the share 0.6 gives 150 mW)"
      % (IGT * 1e3, p_fire, VINH_MAX, v_fire, v_fire, VINH_MAX, 2 * math.pi * 50 * VPK / 1000, (v_fire - VINH_MAX) / (2 * math.pi * 50 * VPK / 1000),
         p_fire * (v_fire - VINH_MAX) / (2 * math.pi * 50 * VPK / 1000) * 1e-3 * 100 * 1e3))
IL_I_III = 70e-3      # ST DS2114 Rev 11 Table 4 p.3, BW column: IL 70 mA max quadrants I and III (80 mA quadrant II)
i_latch = v_fire / 52.7
check("triac latches at firing", i_latch > IL_I_III,
      "main current at the firing point at least %.1f V / 52.7 ohm (the element's top resistance) = %.2f A against IL 70 mA max (x%.1f)" % (v_fire, i_latch, i_latch / IL_I_III))
irms_fault = (253 - VTM) / R_G_NOM
print("   gate-to-MT1 short fault (a shorted triac gate): %.2f A rms through the 400 ohm, peak %.2f A, %.0f W in the two resistors: they open; the heater stays off (fails off); the opto-triac's 1 A is a single-cycle rating and the time the resistors take to open is not sourced"
      % (irms_fault, VPK / R_G_NOM, irms_fault ** 2 * R_G_NOM))

# ---- (c) hold-off
print("\n== (c) hold-off in reset, unpowered and with the cable loose; no gate-MT1 resistor")
IDRM2 = 2e-3          # onsemi p.4: leakage in inhibited state 2 mA max, flows only with the LED at rated IFT (the commanded state) and VDRM applied
IDRM1 = 500e-9        # onsemi p.4: peak blocking current 500 nA max at VDRM 800 V, LED off, 25 degC
IGT_MIN = 0.05 * IGT  # ST DS2114 Rev 11 Table 4 note 1 p.3: minimum IGT guaranteed at 5 % of IGT max
VGD = 0.2             # ST DS2114 Rev 11 Table 4 p.3: VGD 0.2 V min, VD = VDRM, RL 3.3 kohm, Tj 125 degC
R_G = R_G_NOM * (1 + TOL)
v1 = IDRM1 * R_G
check("off-state leakage against the triac's trigger current", IDRM1 < IGT_MIN and v1 < VGD,
      "LED off: IDRM1 500 nA vs the triac's guaranteed minimum trigger current 5 %% x 50 mA = %.1f mA: x%.0f; the leakage's voltage across %.0f ohm = %.3f mV vs VGD 0.2 V min: x%.0f" % (IGT_MIN * 1e3, IGT_MIN / IDRM1, R_G, v1 * 1e3, VGD / v1))
# Amended 2026-11-18 (schematic review finding 2.11): the hot corner. IDRM1's maximum is stated at 25 degC only (the sheet's table is headed
# TA = 25 degC); the sheet gives no maximum above that. The sheet's Fig. 5 (p.5) is a typical curve, read off the plot at about 6 nA at 25 degC,
# 450 nA at 85 degC and 1500 nA at 100 degC (each read to within a factor of about 1.5); scaling the 25 degC maximum by those ratios is an
# inference, not a rated figure. The triac's trigger current falls when hot: ST DS2114 Rev 11 Fig. 9 (p.5, typical, read off the plot) reads
# IGT at Tj 125 degC at about 0.45 of its 25 degC value.
LEAK_25, LEAK_85, LEAK_100 = 6.0, 450.0, 1500.0   # nA, onsemi Fig. 5 typical curve, read off the plot [reading]
RATIO_85, RATIO_100 = LEAK_85 / LEAK_25, LEAK_100 / LEAK_25
IGT_HOT = 0.45        # ST DS2114 Rev 11 Fig. 9 p.5: IGT[125 degC] / IGT[25 degC], typical, read off the plot [reading]
igt_min_hot = IGT_MIN * IGT_HOT
for name, ratio in (("85 degC (the opto-triac's TOPR limit)", RATIO_85), ("100 degC (its junction maximum, outside TOPR)", RATIO_100)):
    i_hot = IDRM1 * ratio
    v_hot = i_hot * R_G
    print("   hot corner, opto-triac at %s, triac at 125 degC: IDRM1 scaled x%.0f = %.1f uA [inference from a typical curve]; against the triac's hot minimum trigger current 2.5 mA x %.2f = %.2f mA: x%.0f; across %.0f ohm %.1f mV against VGD 0.2 V (rated at 125 degC): x%.1f"
          % (name, ratio, i_hot * 1e6, IGT_HOT, igt_min_hot * 1e3, igt_min_hot / i_hot, R_G, v_hot * 1e3, VGD / v_hot))
    check("hold-off hot corner, " + name.split(" (")[0], i_hot < igt_min_hot and v_hot < VGD,
          "leakage %.1f uA < %.2f mA hot trigger current (x%.0f); %.1f mV < VGD 0.2 V (x%.1f)" % (i_hot * 1e6, igt_min_hot * 1e3, igt_min_hot / i_hot, v_hot * 1e3, VGD / v_hot))
print("   the 800 V test voltage of IDRM1 is above the 357.8 V peak the leakage sees on this board: no credit is taken for that")
print("   IDRM2 2 mA flows only while the LED is on and the line is above the inhibit voltage (the commanded state): it is not a hold-off figure. Against the minimum trigger current %.1f mA it is x%.2f; across %.0f ohm it is %.2f V. So a command that starts mid-half-cycle could fire before the next zero: a non-zero-cross turn-on, no hazard (the heater was commanded on)" % (IGT_MIN * 1e3, IGT_MIN / IDRM2, R_G, IDRM2 * R_G))
IDSS = 5e-6           # main board circuit-proof.md hold-off table (controller in reset row): Q off, LED current at most IDSS 5 uA
print("   LED current in reset / unpowered: at most %.0f uA (main board row), %.0f times under IFT max 5 mA; cable loose: +5V_WB or HEAT_x_LED_K open gives 0 A" % (IDSS * 1e6, IFT_MAX / IDSS))

# ---- (d) varistor 07D471K and the surge: the element is in series with the varistor
print("\n== (d) varistor 07D471K (Zhuhai Hongjiacheng Rev 1.2) across each triac; surge reaching the wall branch through the element")
V1MA_MIN, VAC_MAX, VCLAMP10A, E_RATED = 423.0, 300.0, 775.0, 29.0
VDRM_T, VDSM_T, VDRM_O = 800.0, 900.0, 800.0   # ST DS2114 Rev 11 (product summary p.1, Table 1 p.2: VDSM = VDRM + 100 V); onsemi p.3 VDRM 800 V
R_EL_MIN, R_EL_MAX = 47.0, 52.7                # division record: element 47.0 to 52.7 ohm
check("stays off in service", V1MA_MIN > VPK and VAC_MAX > 253,
      "V1mA min %.0f V vs peak %.1f V: x%.2f; 300 VAC vs 253 V: x%.2f" % (V1MA_MIN, VPK, V1MA_MIN / VPK, VAC_MAX / 253))
check("clamp under the triac and the opto-triac", VCLAMP10A < VDRM_T and VCLAMP10A < VDRM_O,
      "clamp %.0f V at 10 A vs triac VDRM %.0f V: %.0f V under (%.1f %%; VDSM %.0f V for 10 ms, %.0f V under) and vs opto-triac VDRM 800 V: %.0f V under (a thin margin at the sheet's 10 A point, comfortable at the 3 to 8 A of the table below)"
      % (VCLAMP10A, VDRM_T, VDRM_T - VCLAMP10A, 100 * (VDRM_T - VCLAMP10A) / VDRM_T, VDSM_T, VDSM_T - VCLAMP10A, VDRM_O - VCLAMP10A))
print("   the wall varistor is fed from the main board's entry clamp (14D471K) through the element, R_el %.1f to %.1f ohm; it never faces the generator's own source impedance, so the earlier 1200 A / 1.44 ohm arithmetic is moot" % (R_EL_MIN, R_EL_MAX))
print("   surge table (line to neutral, 2 ohm combination-wave source [unsourced: IEC 61000-4-5 not read]): inputs marked [unsourced] are engineering estimates, not read from a document")
rows = [
    ("1 kV", 1000.0, 720.0, 850.0, 700.0, "entry varistor voltage ~720 V [unsourced], entry clamp ~850 V [unsourced, 14D curve not read], wall varistor ~700 V at this current [unsourced]"),
    ("2.5 kV", 2500.0, 1100.0, 1100.0, 750.0, "entry clamp ~1000 to 1100 V [unsourced], wall varistor ~750 V [unsourced]"),
    ("2.5 kV, entry clamp 1300 V", 2500.0, 1300.0, 1300.0, 750.0, "entry clamp as bad as 1300 V [unsourced], wall varistor ~750 V [unsourced]"),
]
for name, vs, ve, vc, vw, note in rows:
    ie = (vs - ve) / 2.0
    iw = (vc - vw) / R_EL_MIN
    print("   %-28s entry varistor current (%.0f - %.0f)/2 = %.0f A; wall varistor current (%.0f - %.0f)/%.0f = %.1f A; triac sees %s; %s"
          % (name, vs, ve, ie, vc, vw, R_EL_MIN, iw, "at most 775 V (sheet point 775 V at 10 A)" if iw <= 10 else "about 780 V (just past the 10 A point)", note))
    check("wall varistor current in the surge, " + name, iw <= 12.0, "%.1f A, far under the 1200 A single-pulse rating (x%.0f)" % (iw, 1200.0 / iw))
e_surge = VCLAMP10A * 10.0 * 50e-6
check("wall varistor surge energy", e_surge < E_RATED, "775 V x 10 A x 50 us = %.2f J against the 29 J rating (10/1000 us) (x%.0f); an estimate, the pulse shape is not the rated one" % (e_surge, E_RATED / e_surge))
print("   no varistor, 800 V triac: the triac would see the entry clamp, 850 to 1100 V [unsourced], over its VDSM 900 V at 2.5 kV: it breaks over. The wall varistor is kept")
print("   opto-triac at the clamp voltage: it blocks 800 V (VDRM) and the clamp is at most 775 V, so it is not commanded to fire; a turn-on by dv/dt is not excluded (below), so the 775 V / 396 ohm = %.2f A through the gate network is a rare case that can arise (amended 2026-11-18, finding 4.2); if the branch passed 800 V it would break over into the triac gate, the benign way a triac turns on" % (VCLAMP10A / R_G_MIN))
i2t_event = 2.0 ** 2 * 2e-6
print("   I2t of that breakover event: 2 A^2 x 2 us [turn-on time unsourced] = %.1e A2s against the opto-triac's one cycle 1 A at 60 Hz, half-cycle I2t = 1 A^2 x 8.33 ms / 2 = %.1e A2s (x%.0f): a comparison by I2t is an inference, not a maker figure" % (i2t_event, 1.0 * 8.33e-3 / 2, 1.0 * 8.33e-3 / 2 / i2t_event))
p_worst = 253.0 ** 2 / (4 * R_EL_MIN)
i_worst = 253.0 / (2 * R_EL_MIN)
print("   varistor failed partly (fed through the element): worst dissipation at matched resistance, %.0f V rms: %.0f W at %.2f A rms, which no fuse clears; the stuck-on current threshold has to catch %.1f A (the open item: a threshold of 2.0 A or less)" % (253.0, p_worst, i_worst, i_worst))
check("partial-failure current above the carried threshold", i_worst > 2.0, "%.2f A against the firmware threshold the record asks (at most 2.0 A, x%.2f)" % (i_worst, i_worst / 2.0))

# Amended 2026-11-18 (schematic review finding 2.4): static dv/dt of the opto-triac against a surge front.
DVDT_MIN, DVDT_TYP = 600.0, 1500.0   # V/us, onsemi p.4: static dv/dt (IF = 0) 600 V/us min, 1500 V/us typ
FRONT = VCLAMP10A / 1.2             # V/us [unsourced: a 1.2 us front to the 775 V clamp, an estimate; IEC 61000-4-5 not read]
print("   opto-triac static dv/dt: %.0f V/us min, %.0f V/us typ (onsemi p.4). A front reaching %.0f V in 1.2 us [unsourced estimate] is about %.0f V/us: x%.2f against the minimum, x%.1f under the typical figure; a false trigger is therefore not excluded on the guaranteed figure"
      % (DVDT_MIN, DVDT_TYP, VCLAMP10A, FRONT, DVDT_MIN / FRONT, DVDT_TYP / FRONT))
ig_pk = VCLAMP10A / R_G_MIN
print("   if the opto-triac turns on by dv/dt (the sheet states no pulse withstand and no behaviour beyond the rating, so what follows is the ordinary thyristor mechanism, an inference): it fires the triac through the gate network, the safe way for a triac; gate current at most %.0f V / %.0f ohm = %.2f A peak until the triac conducts and its main voltage collapses (the time is unsourced, microseconds; ITSM 1 A is a 60 Hz single-cycle rating, so no sheet figure covers a pulse that short)" % (VCLAMP10A, R_G_MIN, ig_pk))
FREQ = 50.0           # the machine's supply: 100 firings a second in row (b) is 50 Hz
e_half = 253.0 ** 2 / R_EL_MIN * (1.0 / (2 * FREQ))
print("   consequence: the triac conducts until the current next passes zero, at most one half cycle of the element: %.0f W rms x %.0f ms = %.1f J at the 47.0 ohm steam element (253 V rms), %.1f A peak %.1f A rms [arithmetic from the element's resistance, not a maker figure]; the opto-triac's LED is off so the next half cycle is not fired: a nuisance conduction of at most one half cycle, no hazard"
      % (253.0 ** 2 / R_EL_MIN, 1000.0 / (2 * FREQ), e_half, VPK / R_EL_MIN, 253.0 / R_EL_MIN))

# ---- (e) triac current share against the sheet's current-against-case-temperature curve (finding 2.7); an addition 2026-11-18
print("\n== (e) triac current share, ST DS2114 Rev 11 Fig. 2 (p.4, dissipation against current) and Fig. 3 (p.4, IT(RMS) against case temperature, BTA curve)")
E_TJ_MAX, E_TC_RATED, E_I_RATED = 125.0, 86.0, 16.0   # ST DS2114 Rev 11 Table 1 p.2: Tj 125 degC; IT(RMS) 16 A at Tc 86 degC (BTA16 summary)
E_RTH_JC, E_VTO, E_RD = 2.1, 0.85, 0.025               # ST DS2114 Rev 11 Table 5 p.3 (2.1 K/W), Table 2 p.2 (0.85 V, 25 mohm)
E_P_STEAM = 4.84                                    # division record: dissipation at 5.38 A steam
E_TC_BEST = 116.4 - E_P_STEAM * E_RTH_JC               # the record's best-case steady junction 116.4 degC less Rth(j-c) x P
e_span = E_TJ_MAX - E_TC_RATED
e_chord = E_I_RATED * (E_TJ_MAX - E_TC_BEST) / e_span
print("   best-case case temperature %.1f degC (116.4 degC less %.2f W x %.1f K/W). Reading 1, a straight chord from 16 A at Tc 86 degC to 0 A at 125 degC (the reviewer's reading): %.1f A; the 0.5 current share is %.2f A" % (E_TC_BEST, E_P_STEAM, E_RTH_JC, e_chord, e_chord / 2))
e_pallow = (E_TJ_MAX - E_TC_BEST) / E_RTH_JC
e_model = (-E_VTO * 0.9 + math.sqrt((E_VTO * 0.9) ** 2 + 4 * E_RD * e_pallow)) / (2 * E_RD)
print("   Reading 2, the plot is concave, not straight, so the chord understates it: the dissipation that keeps Tj at 125 degC at that case temperature is %.2f W (%.1f K / %.1f K/W); solving P = VTO x 0.9 I + RD I^2 (0.9 = mean of |sine|, a derivation that reproduces the sheet's 4.84 W at 5.38 A and 18.6 W at 16 A) gives %.1f A, the 0.5 current share %.2f A; read directly off the curve at that case temperature about 8 to 9 A [reading]" % (e_pallow, E_TJ_MAX - E_TC_BEST, E_RTH_JC, e_model, e_model / 2))
print("NOTE  triac current share at the best-case case temperature: " + "the 0.5 share is %.2f A (chord) to %.2f A (model) against the steam element's 5.38 A: SHORT under either reading; the 8 A of row (e) is the rating at Tc 86 degC and is not the share at this case temperature. Owner-held (D11); recorded in owner-sign-off.md W-5" % (e_chord / 2, e_model / 2))

# ---- (f) opto-triac temperature (finding 1.9)
print("\n== (f) opto-triac worst-case temperature, onsemi MOC3083M/D Rev. 2")
SLOPE_TOTAL = 2.94e-3  # onsemi p.3: total device power 250 mW at 25 degC, derate 2.94 mW/degC: implies a junction-to-ambient resistance of 1/2.94 mW/degC = 340 K/W (a derivation from the sheet, not a stated thermal resistance)
r_ja = 1.0 / SLOPE_TOTAL
self_rise = p_led * r_ja
print("   sheet-implied junction-to-ambient %.0f K/W; the LED's %.1f mW (VF 1.5 V, IF %.1f mA at the top rail) heats the junction by about %.1f K (a derivation)" % (r_ja, p_led * 1e3, i_max * 1e3, self_rise))
for air in (45.0, 50.0, 70.0):
    amb_head = TOPR_MAX - air
    jshare = 0.88 * TJ_MAX
    j_head = jshare - self_rise - air
    print("   air %.0f degC: headroom to the TOPR ambient limit 85 degC = %.0f K for the neighbour rise (the triac leg 20.0 mm away, unmeasured); junction share 0.88 x 100 = %.0f degC leaves %.1f K after self-heating" % (air, amb_head, jshare, j_head))
print("NOTE  at 45 to 50 degC air (the owner's working figure for the wall board, 2026-10-28, unmeasured) 35 to 40 K of neighbour rise is permitted against the 85 degC ambient limit; the rise is not measured")
print("NOTE  at 70 degC air the neighbour rise permitted is 15 K (ambient limit) and %.1f K (junction share): the division record's A8 takes 15 K as the allowance for an 85 degC part, an assumption, unmeasured; DEL-HW-BRING-UP.C13 reads it" % (0.88 * TJ_MAX - self_rise - 70.0))

print("\nexit %d" % (1 if fails else 0))
sys.exit(1 if fails else 0)
