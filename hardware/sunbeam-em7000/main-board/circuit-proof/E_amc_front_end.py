#!/usr/bin/env python3
"""Supply measurement front end (sheet "Supply voltage and current measurement"):
range, element stress, input-fault current, filter corner and the error contributors of the two
AMC131M02 input channels.  Prints every figure the proof rows quote.  Run: python3 -I E_amc_front_end.py

Part values are the schematic's (R601..R608, C601, C602, U601).  Every other input is named with
its source on the line that sets it.
"""
import math

# ---- values from the schematic (sheet E1) -------------------------------------------------
R_HI = [300e3, 300e3, 300e3]        # R601, R602, R603  FRC2512F3003TS, 1 %, 100 ppm/K (Fosan FJ-JS-3001-V3.0, p.4-5)
R_LO = 750.0                        # R604  0603WAF7500T5E, 1 %, 100 ppm/K (UNI-ROYAL 0603 series)
R_F0P = 49.9                        # R605
R_F0N = 49.9                        # R606
R_F1P = 330.0                       # R607
R_F1N = 330.0                       # R608
C_F = 4.7e-9                        # C601, C602  C0G, +/-10 % (IHHEC C0805N472K050T) [datasheet 9.1.2 Fig. 9-1: 4.7 nF]
TOL_R = 0.01
TCR = 100e-6                        # per K, FRC2512 (1 Mohm-range note: 100 ppm/K for 10 ohm..10 Mohm, 2512, p.5); 0603 UNI-ROYAL 100 ppm/K

# ---- sourced inputs ----------------------------------------------------------------------
V_RMS_MAX = 253.0                   # constraints record, Supply: 216-253 V ac
V_RMS_MIN = 216.0
V_PK_MAX = V_RMS_MAX * math.sqrt(2) # 357.8 V (separation-basis: 358 V peak)
VREF = 1.2                          # AMC131M02 SBASA56 6.8 Internal reference voltage; 6.3 VIN = +/-VREF/Gain
ZIND_MIN_LOW_GAIN = 275e3           # SBASA56 6.8, differential input impedance, gain 1/2/4, minimum
ZIND_MIN_HIGH_GAIN = 1e6            # same, gain 8 to 128
ABS_P_LOW_GAIN = 2.7                # SBASA56 6.3, AINx - HGND max, gain 1/2/4
ABS_N = -1.3                        # SBASA56 6.3, min
ABS_P_HIGH_GAIN = 0.9               # gain 8..128
I_IN_MAX = 10e-3                    # SBASA56 6.1: continuous input current, all pins except supply, +/-10 mA
HLDO_OUT_MAX = 3.2                  # SBASA56 6.8, high-side LDO output, no external load, max
ABS_N_AMR = -1.6                    # SBASA56 6.1: AINx min HGND - 1.6 V
FUSE_FAULT_A = 6000.0               # constraints record, Upstream protection: 6 kA project assumption
R_SHUNT = 1.0e-3                    # division record: neutral return shunt "1 mohm class" (owner A's part, not yet chosen)
I_SUPPLY_MAX_RMS = 15.0             # constraints record, Upstream protection: about 15 A for half an hour (fuse band)
I_ALL_LOADS_RMS = 11.01             # division record, Voltage, frequency and total current: neutral current, every load on
GAIN_I = 32                         # chosen: +/-37.5 mV (SBASA56 9.2.2.2)
GAIN_V = 1

VARISTOR_CLAMP = 775.0              # constraints record, Mains entry: 14D471K max clamping voltage 775 V at 50 A
R_MAX_WORKING_V = 200.0             # FRC2512, Fosan FJ-JS-3001-V3.0 p.4: 2512 max working voltage 200 V
R_MAX_OVERLOAD_V = 400.0            # same table, max overload voltage 400 V (5 s test at 2.5 x rated, p.6)
R_RATED_W_70C = 1.0                 # same table, 1 W at 70 degC ambient
AIR_C = 70.0                        # constraints record, Enclosure air temperature (assumed)
T_DERATE_ZERO_C = 155.0             # derating curve p.5: 100 % to 70 degC, 0 at 155 degC

def par(a, b):
    return a * b / (a + b)

def ratio(rhi, rlo, rf_p, rf_n, zind):
    """Differential voltage at AIN0P-AIN0N per volt of line, DC/50 Hz (capacitor open)."""
    zload = rf_p + zind + rf_n
    node = par(rlo, zload) / (sum(rhi) + par(rlo, zload))     # LINE -> VMEAS_DIV
    return node * zind / zload                                # through R605, R606

print("== channel 0 (supply voltage): divider and range")
nom = ratio(R_HI, R_LO, R_F0P, R_F0N, ZIND_MIN_LOW_GAIN)
print(f"nominal ratio with ZIND = {ZIND_MIN_LOW_GAIN/1e3:.0f} kohm (min): {nom:.6e}  (1 : {1/nom:.1f})")
nom_inf = ratio(R_HI, R_LO, R_F0P, R_F0N, 1e12)
print(f"nominal ratio with an ideal input:                 {nom_inf:.6e}")
# range corner: every tolerance end that raises the ratio.  ratio rises with R604 and falls with R601..R603 and with
# ZIND (loading), so the high corner is R_LO +1 %, R_HI -1 %, ZIND at the larger of nothing-stated (ideal -> highest ratio);
# temperature: all resistors at air temperature + 45 K (70 degC air from 25 degC), common TCR, so a ratio of two resistors of
# like TCR moves only through the difference; take the whole 100 ppm/K on R_LO opposite R_HI (worst).
dT = AIR_C - 25.0
hi = ratio([r * (1 - TOL_R) * (1 - TCR * dT) for r in R_HI], R_LO * (1 + TOL_R) * (1 + TCR * dT), R_F0P, R_F0N, 1e12)
lo = ratio([r * (1 + TOL_R) * (1 + TCR * dT) for r in R_HI], R_LO * (1 - TOL_R) * (1 - TCR * dT), R_F0P, R_F0N, ZIND_MIN_LOW_GAIN)
print(f"worst-high ratio (R_LO +1 %, R_HI -1 %, opposite TCR over +{dT:.0f} K, ideal input): {hi:.6e}")
print(f"worst-low  ratio (reverse, ZIND at its 275 kohm minimum):                          {lo:.6e}")
vpk_hi = V_PK_MAX * hi
vpk_nom = V_PK_MAX * nom
print(f"differential input at {V_RMS_MAX:.0f} V rms = {V_PK_MAX:.1f} V peak: nominal {vpk_nom*1e3:.1f} mV, worst-high {vpk_hi*1e3:.1f} mV peak")
fs = VREF / GAIN_V
print(f"full scale +/-VREF/Gain = +/-{fs:.3f} V at gain {GAIN_V}: worst-high uses {100*vpk_hi/fs:.1f} % of full scale, headroom {fs/vpk_hi:.2f}x")
print(f"line peak that reaches full scale (worst-high ratio): {fs/hi:.0f} V peak = {fs/hi/math.sqrt(2):.0f} V rms")
print(f"absolute input: AIN0P peak {vpk_hi*1e3:.1f} mV against +{ABS_P_LOW_GAIN} V / {ABS_N} V (gain {GAIN_V}): inside")
print("range figure (reads 253 V rms = 358 V peak with every tolerance high): MET" if vpk_hi < fs else "FAILS")

print("\n== channel 0: element stress (limiting element voltage, power at 70 degC air)")
r_each_min = R_HI[0] * (1 - TOL_R)
v_each_rms = V_RMS_MAX * r_each_min / (3 * r_each_min + R_LO * (1 + TOL_R))
p_each = v_each_rms ** 2 / r_each_min
print(f"each of R601..R603 at 253 V rms: {v_each_rms:.1f} V rms ({v_each_rms*math.sqrt(2):.1f} V peak) against {R_MAX_WORKING_V:.0f} V max working: {100*v_each_rms/R_MAX_WORKING_V:.0f} %")
print(f"each: power {p_each*1e3:.1f} mW against {R_RATED_W_70C*1e3:.0f} mW at 70 degC ambient: {100*p_each/R_RATED_W_70C:.1f} %")
v_clamp_each = VARISTOR_CLAMP / 3
print(f"entry varistor clamp {VARISTOR_CLAMP:.0f} V across the chain: {v_clamp_each:.0f} V each against {R_MAX_OVERLOAD_V:.0f} V max overload (5 s); above the {R_MAX_WORKING_V:.0f} V working figure for the transient; the maker states no microsecond surge rating")
v_one_shorted = V_RMS_MAX / 2
print(f"one of the three shorted: {v_one_shorted:.0f} V rms across each remaining: {100*v_one_shorted/R_MAX_WORKING_V:.0f} % of 200 V (two in the chain would leave one at {V_RMS_MAX:.0f} V, over 200 V)")
p_lo = (V_PK_MAX * hi / math.sqrt(2) / 1) ** 2 / R_LO
print(f"R604: {V_PK_MAX*hi/math.sqrt(2)*1e3:.1f} mV rms, {p_lo*1e6:.1f} uW against 100 mW")
print(f"derating curve at 70 degC air: {100*(T_DERATE_ZERO_C-AIR_C)/(T_DERATE_ZERO_C-70):.0f} % of rating (flat to 70 degC); the part's own rise at 24 mW is {100*p_each/R_RATED_W_70C:.1f} % of the 1 W it is rated for")

print("\n== channel 0: fault, R604 open (divider mid-node floats up to the line through R601-R603 and R605)")
i_open = (V_PK_MAX - 0.0) / sum(R_HI)
print(f"current into AIN0P through 900 kohm at {V_PK_MAX:.0f} V peak: {i_open*1e3:.3f} mA against {I_IN_MAX*1e3:.0f} mA continuous: {100*i_open/I_IN_MAX:.1f} %")

print("\n== channel 1 (supply current): range")
vpk_15 = I_SUPPLY_MAX_RMS * math.sqrt(2) * R_SHUNT
vpk_11 = I_ALL_LOADS_RMS * math.sqrt(2) * R_SHUNT
fs1 = VREF / GAIN_I
print(f"15 A rms = {I_SUPPLY_MAX_RMS*math.sqrt(2):.2f} A peak across {R_SHUNT*1e3:.1f} mohm: {vpk_15*1e3:.2f} mV peak; 11.01 A rms: {vpk_11*1e3:.2f} mV peak")
print(f"full scale at gain {GAIN_I}: +/-{fs1*1e3:.1f} mV: 15 A uses {100*vpk_15/fs1:.0f} % (headroom {fs1/vpk_15:.2f}x); the current that reaches full scale: {fs1/R_SHUNT/math.sqrt(2):.1f} A rms")
print(f"gain >= 8 absolute range HGND {ABS_N} V .. +{ABS_P_HIGH_GAIN} V: shunt voltage {vpk_15*1e3:.1f} mV about NEUTRAL: inside")
# the ZIND loading of the 330 + 330 ohm series: gain 32 -> 1 Mohm min
loss = 1 - ZIND_MIN_HIGH_GAIN / (ZIND_MIN_HIGH_GAIN + R_F1P + R_F1N)
print(f"series 330 + 330 ohm against ZIND 1 Mohm min: gain error {100*loss:.3f} % (not a figure of the record, reported for the sensing task)")
gain32_ok = vpk_15 < fs1
print("range figure (reads 15 A rms, the fuse overload band, without clipping): MET" if gain32_ok else "FAILS")

print("\n== channel 1: fault, 6 kA through the shunt (prospective; the fuse limits it, its peak let-through is not stated)")
v_fault = FUSE_FAULT_A * R_SHUNT
rser = R_F1P + R_F1N
i_pos = (v_fault - HLDO_OUT_MAX) / rser            # clamp diode to HLDO_OUT, forward drop taken as zero (worst)
i_neg = (v_fault + ABS_N_AMR) / rser               # reverse: inputs clamp near HGND - 1.6 V at worst
print(f"prospective voltage across {R_SHUNT*1e3:.1f} mohm at 6 kA: {v_fault:.2f} V")
print(f"positive: (6.00 - {HLDO_OUT_MAX}) / {rser:.0f} = {i_pos*1e3:.2f} mA; negative: (6.00 - 1.6) / {rser:.0f} = {i_neg*1e3:.2f} mA against {I_IN_MAX*1e3:.0f} mA continuous")
print("input current figure (<= 10 mA, SBASA56 6.1): MET" if max(i_pos, i_neg) < I_IN_MAX else "FAILS")
r_min = (v_fault - 1.6) / (2 * I_IN_MAX)
print(f"least series resistance per leg for 6 V: {r_min:.0f} ohm; with 49.9 ohm legs: negative-direction current would be {(v_fault-1.6)/(2*49.9)*1e3:.1f} mA (over 10 mA)")
r_shunt_max = (I_IN_MAX * rser + 1.6) / FUSE_FAULT_A
print(f"largest shunt that keeps 330 ohm legs inside 10 mA at 6 kA: {r_shunt_max*1e3:.2f} mohm")

print("\n== anti-alias filters (SBASA56 9.1.2: a low-pass in front of each channel input; Fig. 9-1: 50 ohm + 4.7 nF)")
r_src0 = par(R_LO, sum(R_HI))   # divider Thevenin
tau0 = (r_src0 + R_F0P + R_F0N) * C_F
tau1 = (R_F1P + R_F1N) * C_F
for name, tau in (("channel 0 (divider source impedance %.0f ohm + 49.9 + 49.9)" % r_src0, tau0), ("channel 1 (330 + 330)", tau1)):
    fc = 1 / (2 * math.pi * tau)
    ph50 = math.degrees(math.atan(2 * math.pi * 50 * tau))
    mag50 = 1 / math.sqrt(1 + (2 * math.pi * 50 * tau) ** 2)
    ph60 = math.degrees(math.atan(2 * math.pi * 60 * tau))
    print(f"{name}: tau {tau*1e6:.3f} us, corner {fc/1e3:.1f} kHz, at 50 Hz: gain {mag50:.8f}, phase {ph50:.4f} deg ({tau*1e6:.2f} us); at 60 Hz phase {ph60:.4f} deg")
dphase = math.degrees(math.atan(2 * math.pi * 50 * tau0)) - math.degrees(math.atan(2 * math.pi * 50 * tau1))
print(f"phase difference between the channels at 50 Hz: {dphase:.4f} deg (AMC phase calibration registers can trim; no phase figure is declared)")
print(f"supply frequency of the record (50 Hz nominal, 60 Hz alternate): corners {1/(2*math.pi*tau0)/60:.0f}x and {1/(2*math.pi*tau1)/60:.0f}x above 60 Hz")
print("C0G tolerance +/-10 %: tau moves +/-10 %; corner stays above 60 Hz by more than 700x")

print("\n== divider accuracy contributors (INFORMATION: no accuracy figure is declared for the supply voltage; the row fails on that)")
# ratio error from tolerances: R_LO +1 %, R_HI -1 % each
e_tol = (hi / nom_inf) - 1
e_tol_lo = (lo / nom_inf) - 1
print(f"resistor tolerance (1 %) and TCR (100 ppm/K over +{dT:.0f} K), ratio against ideal nominal: {100*e_tol:+.3f} % / {100*e_tol_lo:+.3f} %")
load = 1 - nom / nom_inf
print(f"ZIND loading (275 kohm min): {100*load:.3f} % low, bounded below only by the minimum the sheet gives (no maximum impedance is stated)")
print("AMC131M02 channel 0: gain error +/-0.2 % at 25 degC, drift 8 typ / 25 max ppm/K, offset +/-330 uV max at 25 degC, THD -94 dB max (SBASA56 6.8)")
print(f"offset 330 uV against {V_PK_MAX*nom*1e3:.0f} mV signal at 253 V: {100*330e-6/(V_PK_MAX*nom):.2f} % of peak")
