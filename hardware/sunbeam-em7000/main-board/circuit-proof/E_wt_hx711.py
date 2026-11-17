#!/usr/bin/env python3
"""Load-cell amplifier figures (sheet "Load-cell amplifiers"): full-scale input, the input filter against the output rate, the
supply and level arithmetic, and the excitation load.  Run: python3 -I E_wt_hx711.py
Sources: Avia Semiconductor HX711 V2.0 (https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/73/HX711.pdf, a copy of the maker's sheet,
and the catalogue entry C6705483's copy), read 2026-10-29: Key Electrical Characteristics (full-scale differential input +/-0.5 (AVDD/GAIN); common-mode input
AGND+1.2 V to AVDD-1.3 V; output rate 10 / 80 SPS on the internal oscillator; supply 2.6-5.5 V; analog supply current 1.4 mA in the table and under 1.5 mA in the features list, including the regulator; 1.5 mA is used; digital 0.1 mA),
Power Supply Options, Fig. 4 reference PCB (R3 R4 100 ohm, C4 0.1 uF).  The record's +5V: IRM-20-5 +/-2.5 % (Mean Well IRM-20-SPEC 2025-11-21, Voltage Tolerance).
Bridge resistance: NO SOURCE.  The division record's rail budget assumes 350 ohm (division A28, an assumption it says each part's choice replaces).
"""
import math
AVDD_MIN, AVDD_MAX = 5.0 * 0.975, 5.0 * 1.025
print(f"+5V rail {AVDD_MIN:.3f} to {AVDD_MAX:.3f} V (IRM-20-5, +/-2.5 %)")
for gain in (128, 64):
    for avdd in (AVDD_MIN, 5.0, AVDD_MAX):
        fs = 0.5 * avdd / gain
        print(f"  gain {gain:3d}, AVDD {avdd:.3f} V: full scale +/-{fs*1e3:.2f} mV; as a ratio of the excitation: +/-{fs/avdd*1e3:.3f} mV/V")
print("  the ratio of full scale to excitation is 0.5/gain whatever AVDD is, because the load-cell excitation and the reference are the same node:")
print(f"  gain 128: +/-{0.5/128*1e3:.3f} mV/V; gain 64: +/-{0.5/64*1e3:.3f} mV/V (a cell's rated output, in mV/V at capacity, must lie inside this)")
print("  common-mode window: AGND+1.2 V to AVDD-1.3 V = %.3f to %.3f V at the low rail end; bridge midpoint = AVDD/2 = %.3f V: inside" % (1.2, AVDD_MIN - 1.3, AVDD_MIN / 2))
print()
rf = 100.0 + 100.0
cf = 100e-9
tau = rf * cf
print(f"input filter: R670+R671 = {rf:.0f} ohm, C670 = 100 nF (X7R, 10 %): tau {tau*1e6:.0f} us, corner {1/(2*math.pi*tau)/1e3:.1f} kHz")
print(f"  output period on the internal oscillator: 100 ms at 10 SPS, 12.5 ms at 80 SPS; one filter time constant is {100*tau/0.1:.3f} % of 100 ms")
print(f"  the filter settles to 1 part in 2^24 in {tau*math.log(2**24)*1e3:.2f} ms (= {tau*math.log(2**24)/0.0125*100:.1f} % of the 80 SPS period)")
print("  the sheet states no input bias current or input impedance, so the offset the 100 ohm legs produce cannot be calculated (not sourced)")
print()
print("digital interface:")
print("  DVDD from +3V3: DOUT swings 0 to DVDD, i.e. 0-3.3 V, into a controller pin whose VIH min is 0.7 VDD (DS12110 Rev 10 Table 60): HX711 output high level not stated (no VOH)")
print("  PD_SCK from a controller pin: VOH min VDD - 0.4 V at -8 mA (DS12110 Rev 10 Table 61) against the HX711 input high level: NOT STATED in V2.0")
print("  the sheet states: 'Digital power supply (DVDD) should be the same power supply as the MCU power supply' (Power Supply Options) and gives no VIH, VIL, VOH, VOL")
print("  PD_SCK high time T3 min 0.2 us, typ 1 us, max 50 us; low time T4 min 0.2 us; clock pulses 25 to 27 per conversion; power-down when PD_SCK high > 60 us")
print()
print("rail loads (maxima):")
print(f"  +5V : analog supply 1.5 mA x 2 = 3.0 mA; excitation at 350 ohm (ASSUMED): {AVDD_MAX/350*1e3:.1f} mA each, {2*AVDD_MAX/350*1e3:.1f} mA for two")
print("  +3V3: digital supply 0.1 mA x 2 = 0.2 mA; PD_SCK pull-downs: 0 (to GND) ; DOUT is an output")
