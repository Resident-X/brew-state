# Arithmetic behind the proof rows of the mains entry and the interlock relay. Run: python3 -I A_calcs.py
import math
print("== Copper cross-section per width (copper weight to thickness: 1 oz/ft2 = 305.15 g/m2; copper density 8.96 g/cm3 -> 34.06 um; 0.5 oz 17.03 um)")
t1 = 305.15 / 8960 * 1e3   # um
print("1 oz  nominal thickness from the weight definition: %.2f um (JLCPCB states weights only; the thinnest finished thickness is not stated)" % t1)
K, BETA = 226.0, 234.5
def k(thi, thf): return K * math.sqrt(math.log((thf + BETA) / (thi + BETA)))
print("check of the method's own example: theta_i 90, theta_f 250 -> k = %.1f A s^0.5/mm2 (method states 143)" % k(90, 250))
widths = {"link region K_IL.a side, narrowest": 5.75, "entry-fuse load-side clip region": 6.0, "neutral pour and shunt lands": 7.0}
print("\n== k2 S2 (A2 s) at S = width x 34.06 um (1 oz) and 17.03 um (0.5 oz inner), for ILLUSTRATIVE theta pairs (no source states them: not results)")
for name, w in widths.items():
    for lab, t in (("1 oz", t1), ("0.5 oz", t1 / 2)):
        S = w * t / 1000
        row = []
        for thi, thf in ((85, 183), (105, 217), (130, 250)):
            row.append("(%d,%d): k=%.0f k2S2=%.0f" % (thi, thf, k(thi, thf), k(thi, thf) ** 2 * S * S))
        print("%-38s %.2f mm x %s = S %.4f mm2 | %s" % (name, w, lab, S, " | ".join(row)))
print("\n== Largest let-through a conductor could withstand = k2 S2 (same grid), so the fuse sheet's figure at 6 kA must be at or under it")
print("Fuse sheet (SETfuse SCT520(P) V1.0): average melting I2t of the 10 A rating 500 A2s at 10 x 10 A; pre-arcing only. Clearing time and let-through at 6 kA: NOT STATED.")
print("Rated breaking capacity of the 10 A rating: UL 10 kA at 250 VAC (covers 6 kA, 1.67x); CQC/TUV 2 kA at 250 VAC (6000/2000 = %.1f x short)" % (6000 / 2000))
print("\n== Relay contact against the series current (Hongfa HF115F-Q 2024 Rev 1.00)")
for lab, I in (("steady, both elements+pumps+valves", 10.96), ("with valve inrush", 11.03), ("fuse overload band 1.5 x 10 A", 15.0)):
    print("%-38s %.2f A : 20 A @250 VAC x%.2f ; VDE 18 A @105 C x%.2f ; VDE 16 A @125 C x%.2f" % (lab, I, 20 / I, 18 / I, 16 / I))
print("voltage 440 VAC / 358 V peak = %.2f ; 440/253 = %.2f ; switching power 5000 VA / (253 x 15 = %.0f VA) = %.2f ; / (253 x 10.96 = %.0f) = %.2f" % (440/358, 440/253, 253*15, 5000/(253*15), 253*10.96, 5000/(253*10.96)))
print("\n== Varistor 14D471K (Ruilon 14D series A3, 2023-10-27)")
print("stays off: lowest varistor voltage 423 V vs 358 V peak = %.2f ; max allowable 300 VAC vs 253 = %.2f ; 385 VDC vs 358 V peak = %.2f" % (423/358, 300/253, 385/358))
print("clamp 775 V at 50 A (8/20 us) vs the 2.5 kV category-II surge (separation basis): %.2f x lower; 1725/4500 = %.2f ohm source impedance at which the 4500 A is met" % (2500/775, (2500-775)/4500))
print("open interlock contact: 1000 VAC between open contacts = %.0f V peak vs 775 V clamp = %.2f" % (1000*math.sqrt(2), 1000*math.sqrt(2)/775))
print("\n== X2 capacitor discharge (KNSCHA MPX104K31C3KN15600: 0.1 uF +-10 %, 310 VAC rated; PSMA/How2Power article: below 34 V peak within 1 s after plug removal)")
Cmax = 0.1e-6 * 1.10
Rtol = 1.01 + 0.006   # 1 % + 100 ppm/C x 60 K
Vpk = 253 * math.sqrt(2)
for lab, Rn in (("two strings of 2 x 1 Mohm in parallel", 1.0e6), ("one string open", 2.0e6), ("one resistor shorted in one string, other string intact", 1.0e6 * 2 / 3)):
    R = Rn * Rtol
    tau = R * Cmax
    v1 = Vpk * math.exp(-1.0 / tau)
    print("%-55s R=%.3f Mohm tau=%.3f s V(1 s)=%.3g V ; time to 34 V = %.3f s ; power at 253 V = %.1f mW" % (lab, R/1e6, tau, v1, tau * math.log(Vpk / 34), 253**2 / R * 1e3))
print("stored energy at the peak: 0.5 x 0.1 uF x (358 V)^2 = %.2f mJ (record: 6.4 mJ)" % (0.5 * 0.1e-6 * Vpk**2 * 1e3))
print("resistor working voltage: each of 2 in series sees at most %.0f V peak vs UNI-ROYAL 1206 maximum working voltage 200 V" % (Vpk / 2))
print("\n== Shunt WSK25121L000FEA (Vishay Dale doc 30108, 04-Apr-2022): P70 1.0 W; TCR +-250 ppm/C (1.0 to 2.9 mohm); operating -65..+170 C")
for I in (10.96, 11.01, 15.0):
    print("I = %5.2f A: P = %.3f W vs required 0.25 W: rated 1.0 W at 70 C = x%.2f" % (I, I*I*1e-3, 1.0/(I*I*1e-3)))
print("resistance at 85 C: 1.0 mohm +-1 %% +-250 ppm x 60 K = +-%.2f %%" % (1 + 250e-6*60*100))
print("\n== First power: lamp in the live link position JP101 (supply 253 V, 230 V lamps of 60 W and 100 W)")
for P in (60, 100):
    Rh = 230**2 / P
    print("%d W / 230 V lamp: hot resistance %.0f ohm ; short-circuit steady current at 253 V ~ %.0f V / %.0f ohm = %.3f A (lamp at its rating; cold-filament inrush not sourced here)" % (P, Rh, 253, Rh, 253/Rh))
