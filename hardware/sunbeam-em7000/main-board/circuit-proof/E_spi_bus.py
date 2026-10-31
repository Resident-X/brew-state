#!/usr/bin/env python3
"""Shared SPI2 bus (U601 AMC131M02, U620 and U621 MAX31865) and the converter's clock: logic levels, timing and clock figures.
Run: python3 -I E_spi_bus.py
Sources (all read 2026-10-29)
  AMC131M02, Texas Instruments SBASA56 (September 2023), https://www.ti.com/lit/ds/symlink/amc131m02.pdf: 6.3 (digital input VIL/VIH, clock range, NDIV, duty),
      6.8 (VIL 0.2 DVDD, VIH 0.8 DVDD, VOL 0.2 DVDD at 1 mA, VOH 0.8 DVDD at 1 mA, CLOAD 15 typ 30 max pF), 6.9 timing requirements, 6.10 switching
      characteristics, 8.5.1 (SPI mode 1: CPOL = 0, CPHA = 1; data launched on SCLK rising, latched on falling)
  MAX31865, Analog Devices (Maxim) Rev 3 (7/15): Recommended DC Operating Conditions (VIL 0.3 DVDD, VIH 0.7 DVDD), Electrical Characteristics (VOH DVDD-0.4 V at
      1.6 mA, VOL 0.4 V at 1.6 mA), AC Electrical Characteristics SPI (tDC, tCDH, tCDD, tCL, tCH, SCLK 5.0 MHz, tCC, tCCH, tCWH, tCDZ; measured with 50 pF),
      Serial Interface (SPI modes 1 and 3; the part senses the idle clock polarity when CS falls)
  STM32H743, STMicroelectronics DS12110 Rev 10 (March 2023): Table 60 (VIL max 0.3 VDD, VIH min 0.7 VDD), Table 61 (VOL max 0.4 V at 8 mA, VOH min VDD-0.4 V at -8 mA),
      Table 106 (SPI master: fSCK 133 MHz max SPI1,2,3 at 2.7-3.6 V; tsu(MI) 2 ns, th(MI) 1 ns, tv(MO) 3 ns max, th(MO) 0 ns), Table 112 (VIN)
  SiTime SiT8008B Rev 1.08 (1 January 2023), https://www.sitime.com/datasheet/SiT8008: Table 1 (Vdd 3.3 V option 2.97-3.63 V; stability +/-25 ppm; duty 45-55 %;
      tr/tf 2 ns max; VOH 90 % Vdd at -4 mA; Idd 4.5 mA max no load at 20 MHz)
The rail: all three devices and the controller run from +3V3 (one net), so VDD = DVDD at every instant; its span is the controller sheet's.
"""
VDD_MIN, VDD_MAX = 3.0, 3.6   # the span every part on the net must tolerate; the intersection of the parts' limits below is what the rail must hold

print("== levels, every driver against every receiver, at VDD = DVDD = VDD_MIN and VDD_MAX (volts)")
drivers = {
    "MCU out (H743)": (lambda v: v - 0.4, lambda v: 0.4),
    "AMC DOUT/DRDY": (lambda v: 0.8 * v, lambda v: 0.2 * v),
    "MAX31865 SDO": (lambda v: v - 0.4, lambda v: 0.4),
}
receivers = {
    "MCU in (H743)": (lambda v: 0.7 * v, lambda v: 0.3 * v),
    "AMC SCLK/DIN/CS/CLKIN/SYNC": (lambda v: 0.8 * v, lambda v: 0.2 * v),
    "MAX31865 SCLK/SDI/CS": (lambda v: 0.7 * v, lambda v: 0.3 * v),
}
pairs = [("MCU out (H743)", "AMC SCLK/DIN/CS/CLKIN/SYNC"), ("MCU out (H743)", "MAX31865 SCLK/SDI/CS"),
         ("AMC DOUT/DRDY", "MCU in (H743)"), ("MAX31865 SDO", "MCU in (H743)")]
ok = True
for d, r in pairs:
    for v in (VDD_MIN, VDD_MAX):
        voh, vol = drivers[d][0](v), drivers[d][1](v)
        vih, vil = receivers[r][0](v), receivers[r][1](v)
        good = voh >= vih and vol <= vil
        ok &= good
        print(f"  {d:16s} -> {r:27s} VDD {v:.1f}: VOH {voh:.2f} >= VIH {vih:.2f} ({voh-vih:+.2f}), VOL {vol:.2f} <= VIL {vil:.2f} ({vil-vol:+.2f})  {'ok' if good else 'FAILS'}")
print("  levels:", "MET" if ok else "FAILS")
print("  note: the AMC's VOH/VOL are specified at 1 mA, the MAX31865's at 1.6 mA, the controller's at 8 mA; every receiver input here draws under 1 uA (AMC IIN +/-1 uA, MAX31865 IL +/-1 uA)")
print("  the 33 ohm series resistors drop %.1f uV at 1 uA: negligible" % (33 * 1e-6 * 1e6))
print()
print("== bus clock: the slowest receiver sets it")
f_max = 5.0e6                                   # MAX31865 tCLK 5.0 MHz; tCL = tCH = 100 ns
print(f"  MAX31865 SCLK <= 5.0 MHz (tCL = tCH = 100 ns min); AMC131M02 tc(SC) >= 40 ns (25 MHz); H743 SPI2 master <= 133 MHz: bus set to <= {f_max/1e6:.1f} MHz")
half = 0.5 / f_max
print(f"  at {f_max/1e6:.0f} MHz: half period {half*1e9:.0f} ns")
print()
print("== data timing at 5 MHz, mode 1 (SCLK idles low; the transmitter changes data on the rising edge, the receiver latches on the falling edge)")
t_rc_amc = 33.0 * 30e-12          # R613 x CLOAD max 30 pF
t_rc_mosi = 33.0 * (6e-12 + 20e-12)   # R611 x (AMC/MAX input 6 pF + an assumed 20 pF of track; the layout leaf holds the track to it)
print(f"  AMC DOUT -> MCU: tp(SCDO) 20 ns max + 33 ohm x 30 pF ({t_rc_amc*1e9:.2f} ns) + tsu(MI) 2 ns = {20+t_rc_amc*1e9+2:.1f} ns against a half period of {half*1e9:.0f} ns: margin {half*1e9-(20+t_rc_amc*1e9+2):.1f} ns")
print(f"  MAX31865 SDO -> MCU: tCDD 80 ns max (50 pF load) + tsu(MI) 2 ns = 82 ns against {half*1e9:.0f} ns: margin {half*1e9-82:.0f} ns; the load on MISO must stay within the 50 pF the maker measured at (layout constraint)")
print(f"  MCU MOSI -> AMC DIN: tv(MO) 3 ns max + 33 ohm RC {t_rc_mosi*1e9:.2f} ns against tsu(DI) 5 ns: setup margin {half*1e9-3-t_rc_mosi*1e9-5:.0f} ns; hold: th(MO) >= 0 and the data lasts one more half period {half*1e9:.0f} ns >= th(DI) 8 ns")
print(f"  MCU MOSI -> MAX31865 SDI: setup {half*1e9-3:.0f} ns >= tDC 35 ns; hold {half*1e9:.0f} ns >= tCDH 35 ns")
print(f"  SCLK high/low {half*1e9:.0f} ns >= AMC tw(SCH)=tw(SCL)=20 ns and MAX31865 tCH=tCL=100 ns (equal at 5 MHz exactly: a duty cycle under 50 % breaks the MAX31865's 100 ns, so the SPI kernel clock divider must give 50 %: a firmware constraint)")
print("  chip select: AMC td(CSSC) 16 ns and tw(CSH) 15 ns; MAX31865 tCC 400 ns CS-to-SCLK, tCWH 400 ns CS inactive, tCDZ 40 ns: the chip selects are plain outputs (PB12 may be hardware NSS); the firmware holds 400 ns")
print("  shared MISO: each slave's output is high-impedance when its CS is high (AMC 6.10 tp(CSDOZ) 75 ns; MAX31865 tCDZ 40 ns); one CS low at a time, the others held high by their 100 kohm pull-ups while the controller is in reset")
print()
print("== converter clock Y601 (SiT8008B 8.000 MHz) against AMC131M02 CLKIN")
f = 8.000e6
ndiv = 2
print(f"  fCLKIN {f/1e6:.3f} MHz +/-25 ppm: high-resolution range {1.4*ndiv:.1f} to {4.1*ndiv:.1f} MHz at NDIV = 2 (6.3): inside (modulator clock {f/ndiv/1e6:.3f} MHz; DCDC_FREQ range 3.768-4.100 MHz, code 0000b)")
period = 1 / f
for duty_min in (0.45,):
    th = period * duty_min
    print(f"  duty 45-55 % (6.3: 40-60 %): shortest of tw(CLH), tw(CLL) = {th*1e9:.1f} ns >= 49 ns (6.9): margin {th*1e9-49:.1f} ns")
print(f"  level: VOH 90 % of Vdd (-4 mA) against VIH 80 % of DVDD, same rail: ok (0.9 >= 0.8); VOL 10 % <= VIL 20 %: ok")
print(f"  rise/fall 2 ns max (20-80 %), with 33 ohm source termination (R609) and a short track; the sheet asks for a clock free of overshoot and glitches (9.4.1)")
print(f"  supply: the oscillator's Vdd range 2.97-3.63 V sets +3V3 >= 2.97 V; MAX31865 VDD/DVDD 3.0-3.6 V sets +3V3 in 3.0-3.6 V; AMC DVDD 3.0-5.5 V: the rail must hold 3.0 to 3.6 V (controller sheet)")
print(f"  current: SiT8008B 4.5 mA max (no load, measured at 20 MHz, so conservative at 8 MHz) + 15 pF x 3.63 V x 8 MHz = {15e-12*3.63*8e6*1e3:.2f} mA of load = {4.5+15e-12*3.63*8e6*1e3:.2f} mA")
print(f"  output sample rate with OSR 1024: {f/ndiv/1024/1e3:.4f} kSPS; per 50 Hz cycle {f/ndiv/1024/50:.2f} samples (not a whole number: the 8.192 MHz variant of the same family gives 80, but it is not in the catalogue)")
