#!/usr/bin/env python3
"""PT1000 front end figures (sheet "In-stream temperature converters"): range against the reference resistor, the wait the maker
prescribes after the bias is enabled, and the error contributors, for the reference resistor R640/R645 = 4.02 kohm.
Run: python3 -I E_pt_budget.py
Sources: MAX31865 Rev 3 (7/15), Analog Devices (Maxim), https://www.analog.com/media/en/technical-documentation/data-sheets/max31865.pdf (the maker's sheet,
copy hosted by the catalogue entry C118474), read 2026-10-29: Recommended DC Operating Conditions (RREF 350 ohm to 10 kohm; RCABLE 0-50 ohm per lead),
Electrical Characteristics (ADC full-scale error +/-1 LSB, INL +/-1 LSB, offset error -3..+3 LSB, input leakage, VBIAS 1.95-2.06 V, IOUT), Note 4 (10.5 time
constants), Applications Information (1 ms more for the protection devices), Detailed Description (RREF = 4 x R0; Callendar-Van Dusen, IEC 751 constants).
Panasonic ERA3AEB4021V sheet values are the catalogue's: 4.02 kohm, +/-0.1 %, +/-25 ppm/K (catalogue entry C491130, read 2026-10-29).
"""
A, B = 3.9083e-3, -5.775e-7
R0, RREF = 1000.0, 4020.0
TOL_REF, TCR_REF = 0.001, 25e-6
VBIAS_MAX, VBIAS_MIN = 2.06, 1.95
LSB_OHM = RREF / 32768.0            # one ADC code in ohms of RTD resistance

def rt(t):                           # PT1000 above 0 degC (IEC 751, MAX31865 Detailed Description)
    return R0 * (1 + A * t + B * t * t)

def drt(t):                          # ohm per degC
    return R0 * (A + 2 * B * t)

print(f"RREF {RREF:.0f} ohm; one code = {LSB_OHM:.4f} ohm; at 0 degC {LSB_OHM/drt(0):.4f} degC per code, at 150 degC {LSB_OHM/drt(150):.4f}")
print("full scale: RRTD/RREF must stay below 1 (an input above the reference produces full scale, Detailed Description):")
for t in (0, 100, 125, 150, 200):
    print(f"  {t:4d} degC: RTD {rt(t):8.2f} ohm, ratio {rt(t)/RREF:.4f}  code {rt(t)/RREF*32768:8.0f}")
t = 0.0
while rt(t) < RREF:
    t += 0.1
print(f"  ratio reaches 1 at about {t:.0f} degC (the earlier design's rating floor was 125 degC, 150 degC preferred)")
print()
print("bias conditions (VBIAS 1.95-2.06 V; IOUT 0.2-5.75 mA allowed):")
for rtd, label in ((0.0, "RTD shorted"), (rt(0), "0 degC"), (rt(150) + 100, "150 degC, 50 ohm leads")):
    i = VBIAS_MAX / (RREF + rtd)
    print(f"  {label:26s} bias current {i*1e3:.3f} mA, RTD self-heating {i*i*max(rtd,1e-9)*1e3:.3f} mW, RTD voltage {i*rtd:.3f} V (limit VBIAS)")
print()
print("wait after enabling the bias (Note 4: >= 10.5 time constants of the input RC network, plus 1 ms for the protection devices):")
for rcab, label in ((0.0, "4-wire / short leads"), (50.0, "2-wire, 50 ohm per lead (maker's maximum)")):
    rth = rt(150) + 2 * rcab
    tau = rth * 10e-9
    print(f"  {label:42s}: tau = {rth:.0f} ohm x 10 nF = {tau*1e6:.1f} us, 10.5 tau = {10.5*tau*1e6:.0f} us, wait {10.5*tau*1e3 + 1.0:.2f} ms")
print()
print("error contributors in degC (INFORMATION: no sensing-error figure is declared for an in-stream probe, controller-io.md; the accuracy part of the row fails on that):")
print(f"  {'T degC':>8} {'RREF 0.1 %':>11} {'RREF TCR 25ppm/K x 45 K':>25} {'ADC offset +-3 LSB':>19} {'FS +-1 LSB':>11} {'INL +-1 LSB':>12}")
for tt in (0.0, 100.0, 150.0):
    e_tol = TOL_REF * rt(tt) / drt(tt)
    e_tcr = TCR_REF * 45 * rt(tt) / drt(tt)
    e_off = 3 * LSB_OHM / drt(tt)
    e_fs = 1 * LSB_OHM / drt(tt) * (rt(tt) / RREF)   # full-scale error scales with the reading
    e_inl = 1 * LSB_OHM / drt(tt)
    print(f"  {tt:8.0f} {e_tol:11.3f} {e_tcr:25.3f} {e_off:19.3f} {e_fs:11.3f} {e_inl:12.3f}")
print("  sum at 150 degC, linear, all contributors at once: %.3f degC" % (TOL_REF*rt(150)/drt(150) + TCR_REF*45*rt(150)/drt(150) + 3*LSB_OHM/drt(150) + (rt(150)/RREF)*LSB_OHM/drt(150) + LSB_OHM/drt(150)))
print("  the maker's front-page total accuracy, 0.5 degC (0.05 % of full scale), is stated for the maker's own conditions and is not applied to a PT1000 here")
print()
print("2-wire cable: each ohm in the loop reads as %.2f degC at 0 degC for a PT1000 (3.85 ohm per degC); 50 ohm per lead is a %.1f degC error uncorrected" % (1.0 / drt(0), 100.0 / drt(0)))
