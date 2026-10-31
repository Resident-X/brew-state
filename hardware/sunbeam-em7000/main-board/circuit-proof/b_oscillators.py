"""Crystal load capacitors and start-up gain for the controller's HSE and LSE oscillators.

Every input is a datasheet figure, named beside it. Run: python3 -I b_oscillators.py
"""
import math

# ---- HSE: YXC YSX530GA 8 MHz, JLCPCB C115962 (maker datasheet "YSX530GA Glass Sealed", read 2026-10-29,
#      https://datasheet.lcsc.com/datasheet/pdf/ebcc38d6e2fe9beef0d4f07c78c8d1d4.pdf)
f_hse = 8e6
cl_hse = 20e-12            # catalogue listing C115962: "8MHZ ... 20PF" (load capacitance, 20 pF option of the datasheet's CL row)
esr_hse_max = 80.0         # datasheet ESR table, 8-16 MHz: 80 ohm max
c0_hse_max = 7e-12         # datasheet: shunt capacitance C0 7 pF max (YXC X50328MSB2GI, read 2026-10-29)
# DS12110 Rev 11 Table 131 (rev V section): Gmcritmax 1.5 mA/V
gm_max_hse = 1.5e-3
# ST AN4938 Rev 7 s4.1.2: PCB + MCU pin capacitance "10 pF can be used as a rough estimate"
c_stray = 10e-12
c1 = c2 = 20e-12           # C414, C415: Samsung CL10C200JB8NNNC, C0G, +/-5 %, C1648
tol = 0.05

def cl_eff(c1, c2, cs):
    return c1 * c2 / (c1 + c2) + cs

print("HSE")
print("  C1=C2 needed for CL=20 pF with 10 pF stray: %.2f pF" % (2 * (cl_hse - c_stray) * 1e12))
nom = cl_eff(c1, c2, c_stray)
lo = cl_eff(c1 * (1 - tol), c2 * (1 - tol), c_stray)
hi = cl_eff(c1 * (1 + tol), c2 * (1 + tol), c_stray)
print("  CL nominal %.2f pF, with caps -5%% %.2f pF, +5%% %.2f pF (stray held at 10 pF)" % (nom * 1e12, lo * 1e12, hi * 1e12))
w = 2 * math.pi * f_hse
gm_crit = 4 * esr_hse_max * w ** 2 * (c0_hse_max + cl_hse) ** 2
print("  gm_crit (crystal) = 4*ESRmax*(2*pi*f)^2*(C0max+CL)^2 = %.3f mA/V" % (gm_crit * 1e3))
print("  limit Gmcritmax = %.1f mA/V, ratio limit/gm_crit = %.2f, pass=%s" % (gm_max_hse * 1e3, gm_max_hse / gm_crit, gm_crit <= gm_max_hse))
# largest total load (C0max + CL) the MCU can start for this ESR
cmax = math.sqrt(gm_max_hse / (4 * esr_hse_max * w ** 2))
print("  largest (C0+CL) the MCU can start at ESRmax: %.1f pF -> CL may rise to %.1f pF" % (cmax * 1e12, (cmax - c0_hse_max) * 1e12))
print("  CL at the high corner (%.2f pF) gives gm_crit %.3f mA/V" % (hi * 1e12, 4 * esr_hse_max * w ** 2 * (c0_hse_max + hi) ** 2 * 1e3))

# ---- LSE: Seiko Epson FC-135 12.5 pF, JLCPCB C32346 (Q13FC13500004, maker sheet read 2026-10-29,
#      https://datasheet.lcsc.com/datasheet/pdf/d4d1bd2e87b2e72a8e8e7fe7d590f4c0.pdf)
f_lse = 32768.0
cl_lse = 12.5e-12
esr_lse_max = 70e3         # R1 max 70 kohm
c0_lse_typ = 1.0e-12       # C0 typ 1 pF -- the sheet gives no maximum
# DS12110 Rev 11 Table 132: Gmcritmax by LSEDRV[1:0]
gm_lse = {"00 low": 0.5e-6, "01 medium low": 0.75e-6, "10 medium high": 1.7e-6, "11 high": 2.7e-6}
c1l = c2l = 4.7e-12        # C416, C417: FH 0603CG4R7C500NT, C0G, +/-0.25 pF, C1669
print("LSE")
print("  CL1=CL2 for CL=12.5 pF with 10 pF stray: %.2f pF (4.7 pF fitted)" % (2 * (cl_lse - c_stray) * 1e12))
print("  CL nominal with 4.7 pF: %.2f pF; at -0.25 pF %.2f; at +0.25 pF %.2f" % (
    cl_eff(c1l, c2l, c_stray) * 1e12, cl_eff(c1l - .25e-12, c2l - .25e-12, c_stray) * 1e12, cl_eff(c1l + .25e-12, c2l + .25e-12, c_stray) * 1e12))
wl = 2 * math.pi * f_lse
gmc = 4 * esr_lse_max * wl ** 2 * (c0_lse_typ + cl_lse) ** 2
print("  gm_crit at C0 typ 1.0 pF, CL 12.5 pF, ESR 70 kohm = %.3f uA/V" % (gmc * 1e6))
for k, v in gm_lse.items():
    cmx = math.sqrt(v / (4 * esr_lse_max * wl ** 2))
    print("  LSEDRV %-15s Gmcritmax %.2f uA/V: ok=%s ; largest (C0+CL) %.2f pF -> C0 may be up to %.2f pF at CL 12.5" % (
        k, v * 1e6, gmc <= v, cmx * 1e12, (cmx - cl_lse) * 1e12))
print("  drive level: crystal maximum 0.5 uW (sheet); oscillator amplitude not stated in DS12110 -> not computable")
