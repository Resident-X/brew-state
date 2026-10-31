"""Round-1 schematic review fixes on the logic supply and the wall-board inputs: +5V over-voltage (finding 1.1), regulator output
capacitor bias (1.6), 3.3 V supervisor (1.13), mains-presence input network (1.2, 1.4, 1.9), USB discharge residue (owner level 4),
and the unfitted pump snubbers and module inrush thermistor (owner decision b).

Sources (each read 2026-10-29; maxima unless the line says typical):
  IRM-20     Mean Well IRM-20 series specification IRM-20-SPEC 2025-11-21 (https://www.meanwell.com/Upload/PDF/IRM-20/IRM-20-SPEC.PDF): 5 V 4 A,
             overload 115 to 160 % rated power (hiccup), over voltage 5.75 to 6.75 V with "Protection type: Shut off o/p voltage, clamping by zener
             diode" (clamp voltage and energy not stated), inrush 40 A typical cold start at 230 Vac, input 0.4 A typical at 230 Vac.
  LT1963A    Analog Devices LT1963A series, 1963aff (LCSC C459918): IN and OUT +/-20 V; output 3.200 to 3.400 V; Table 1 ESR; 10 uF output capacitor.
  AP7361C    Diodes Incorporated DS37274 Rev. 5-2 (October 2020), the part replaced: input absolute maximum 6.5 V, recommended 2.2 to 6.0 V.
  Taiyo Yuden LMK212BBJ226MG-T (MSASL21GBB5226MTNA01) spec sheet and electrical characteristics data 23GBB06 (LCSC C92811): 22 uF +/-20 % X5R
             10 V 0805, -55 to +85 degC, +/-15 % temperature characteristic; DC bias plot (dC/C against 0 to 10 V, read by eye): about -40 % at 3.4 V
             and -47 % at 4 V; capacitance-temperature plot -13 % at 85 degC.
  TLV803S    Texas Instruments TLV803 data sheet, English SBVS157C (September 2015; LCSC C132016 hosts the Chinese ZHCS187C of the same revision):
             VIT- 2.87 / 2.93 / 2.99 V (-40 to 125 degC), hysteresis 40 mV typical, delay td 120 / 200 / 280 ms, VDD 1.1 to 6 V (7 V absolute),
             VOL 0.4 V at 2 mA (3.3 V) and 0.2 V at 500 uA, IOH 100 nA, IDD 9 / 15 uA at 2 V, power-up reset valid from 1.1 V, RESET open drain.
  DS12110    STMicroelectronics DS12110 Rev 11 (January 2026): Table 109 (VIN on FT pins: min(min(VDD, VDDA, VDD33USB, VBAT) + 4.0, 6) V),
             Table 110 (IINJ(PIN) -5 / +0 mA, positive injection "not possible and does not occur below the maximum value"), Table 116 (BOR3
             falling 2.54 / 2.61 / 2.68 V, PVD6 falling 2.69 / 2.76 / 2.83 V), Table 147 (VIL 0.3 VDD, VIH 0.7 VDD, FT leakage +/-250 nA, 1500 nA
             above VDD up to 5.5 V; PE15 and PD7 are FT_h).
  DS4260     STMicroelectronics USBLC6-2 DS4260 Rev 7 (December 2021), web.archive.org/web/20251214101807/https://www.st.com/resource/en/datasheet/usblc6-2.pdf:
             IEC 61000-4-2 level 4, 15 kV air and 8 kV contact in the features (Table 1 prints 15 kV for contact: a contradiction; either meets level 4),
             VCL 12 V at 1 A and 17 V at 5 A (8/20 us), 3.5 pF maximum between I/O and GND.
  Ruilon     NTC series sheet, version A6, revised 2023-10-16 (LCSC C3790): NTC10D-9 10 ohm at 25 degC, 2 A, 0.46 ohm residual, 150 uF at 240 V.
  WeEn       BTA204S-600B Rev.02: VDRM 600 V (the record's sheet; sheets/700-pump-drives.yaml).
Run: python3 -I b_supply_protection.py
"""

# ---- (1) +5V over-voltage, finding 1.1 ---------------------------------------------------
print("(1) +5V over-voltage")
ovp_lo, ovp_hi, i_src, i_over = 5.75, 6.75, 4.0, 4.0 * 1.60
vmax_old, vmax_new = 6.5, 20.0
print("    module trip %.2f to %.2f V; it can source %.1f A rated and up to %.1f A in overload; the part replaced (AP7361C) takes %.1f V absolute maximum: %.2f V over at the module's upper trip"
      % (ovp_lo, ovp_hi, i_src, i_over, vmax_old, ovp_hi - vmax_old))
# a shunt clamp must stay off at the rail's top (5.25 V + 0.1 V ripple/2) and hold under the old limit at the source's current
v_rail_top = 5.25
print("    clamp A, a zener at 5.6 V holding the rail under 6.5 V at %.1f A: dissipation %.1f W (%.1f W at the %.1f A overload), and its tolerance (5 %%) puts 5.32 V on a 5.25 V rail"
      % (i_src, 5.6 * i_src, 5.6 * i_over, i_over))
print("    clamp B, a TVS of the SMF6.0A class (the project's D402: VBR 6.67 to 7.37 V, VC 10.3 V at 19.4 A): conducts from %.2f V, above the old part's %.1f V, and at 4 A sits at about %.1f V"
      % (6.67, vmax_old, 7.37 + 4.0 * (10.3 - 7.37) / 19.4))
print("    neither clamp holds %.1f V from a %.0f A source with one SMD part; the module's own diode clamp and shut-down is its protection. Chosen: a regulator whose absolute maximum input is above the trip" % (vmax_old, i_src))
print("    LT1963AEST-3.3: IN %.0f V absolute maximum -> margin %.2f V over %.2f V, %.1f V over the USB path's 10.3 V clamp level" % (vmax_new, vmax_new - ovp_hi, ovp_hi, vmax_new - 10.3))
print("    other parts on +5V, +5V_WB and +5V_GAUGE at %.2f V (module trip, on the module's cable position the D402 level is 10.3 V):" % ovp_hi)
parts = [
    ("U302 LT1963A input", 20.0, "IN +/-20 V (LT1963A absolute maximum ratings)"),
    ("U201 74AHCT1G17 VCC", 7.0, "Nexperia 74AHC1G17/74AHCT1G17 Rev. 4 (15 Sep 2023) Table 5 limiting values, VCC -0.5 to +7.0 V"),
    ("U791 SN74HCT541 VCC", 7.0, "Texas Instruments SCLS306C absolute maximum 7 V"),
    ("K201 coil, HF115F-Q/005", 7.5, "Hongfa HF115F-Q coil data: 5 V coil, maximum voltage 7.5 V for a short period, 62 ohm"),
    ("K731 K741 coils, HF32FA-G/005", 8.5, "Hongfa HF32FA-G 2026 Rev 1.00 coil data (circuit-proof.md valve coil row)"),
    ("Q822 AO3401A gate to source", 12.0, "AO3401A Rev 3.1: VGS +/-12 V; gate swings 0 to 5.25 V against a source on +5V, 6.75 V at most"),
    ("C303 10 uF X5R", 10.0, "rated voltage"),
    ("C302 47 uF electrolytic, C792 47 uF", 16.0, "rated voltage"),
    ("C671 C676 10 uF", 25.0, "rated voltage (CL21A106KAYNNNE)"),
    ("C201 C301 C791 100 nF", 50.0, "rated voltage"),
    ("D205 D206 BAS116, D731 D741 1N4148WS", 75.0, "reverse voltage 75 V (circuit-proof.md rows)"),
]
for name, lim, src in parts:
    ok = lim > ovp_hi
    print("      %-38s limit %5.1f V  margin %6.2f V  %s  (%s)" % (name, lim, lim - ovp_hi, "holds" if ok else "FAILS", src))
print("      HX711 U630 U631 (AVDD on +5V): the maker's sheet (Avia V2.0) states no absolute maximum; not shown (schematic-review.md 1.3, open item)")
print("      LED stages R703 R713 R763 R773 (180 ohm): IF = (6.75 - 0)/180 = %.1f mA at most against the opto-triac's 60 mA absolute maximum" % (6.75 / 180 * 1e3))
print("      U201 and U791 keep 0.25 V; the module shuts its output down on the trip; off-board loads on the 5 V pins (sensors, gauge, wall board, buzzer) are the makers' and are not rated here")

# ---- (2) regulator output capacitors, finding 1.6 -----------------------------------------
print("(2) regulator output capacitance (LT1963A: stable with 10 uF, ceramic allowed, ESR 0 ohm at 3.3 V from Table 1)")
c0, tol, bias_34, temp_85 = 22.0, 0.20, 0.45, 0.13
c_one = c0 * (1 - tol) * (1 - bias_34) * (1 - temp_85)
print("    one 22 uF X5R 10 V 0805: -20 %% tolerance, -%.0f %% at 3.4 V (plot reads -40 %%; -45 %% allows the reading), -%.0f %% at 85 degC: %.1f uF" % (bias_34 * 100, temp_85 * 100, c_one))
print("    one part against 10 uF: %s; two in parallel (C304, C305): %.1f uF, %.2fx the 10 uF" % ("short" if c_one < 10 else "holds", 2 * c_one, 2 * c_one / 10))
print("    the part's rating is 85 degC: regulator dissipation below puts its tab well above the 70 degC air, so the capacitors sit at least 10 mm from the tab")
print("    cable-power inrush: nominal 2 x 22 = 44 uF at 0 V bias; at +20 %% %.1f uF" % (2 * c0 * 1.2))

# ---- (3) reset supervisor, finding 1.13 ----------------------------------------------------
print("(3) reset supervisor TLV803S on +3V3")
vit_lo, vit_typ, vit_hi, vhys = 2.87, 2.93, 2.99, 0.040
rail_min = 3.200
loads = [("HX711 DVDD (Avia pin table)", 2.6), ("oscillator Y601 and MAX31865 in the E records", 2.97), ("AMC131M02 DVDD (SBASA56 6.4)", 3.0)]
print("    threshold %.2f to %.2f V falling (%.2f typical, +%.0f mV hysteresis typical: release %.2f typical); regulator output at least %.3f V: margin %.2f V (no spurious reset)"
      % (vit_lo, vit_hi, vit_typ, vhys * 1e3, vit_typ + vhys, rail_min, rail_min - vit_hi))
for name, vmin in loads:
    print("    %-48s minimum %.2f V: threshold window %+.2f to %+.2f V from it" % (name, vmin, vit_lo - vmin, vit_hi - vmin))
print("    controller: BOR3 falling %.2f to %.2f V, PVD6 falling %.2f to %.2f V (DS12110 Table 116): the supervisor's lowest trip %.2f V is %.2f V above PVD6's highest %.2f V, so reset asserts before BOR3 acts and before the controller leaves the PVD6 range"
      % (2.54, 2.68, 2.69, 2.83, vit_lo, vit_lo - 2.83, 2.83))
print("    window not covered for a load of 3.0 V minimum: a rail in %.2f to 3.00 V is not reset on a part at the window's low end (up to %.2f V). A 3.08 V-class threshold (MAX803 T grade, its sheet not read here) would put the window's top within a tenth of a volt of the regulator's lowest output %.3f V and risk a reset on a load-step dip; the 2.93 V grade keeps %.2f V" % (vit_lo, 3.0 - vit_lo, rail_min, rail_min - vit_hi))
print("    reset timing: asserted while VDD < VIT- and for %.0f to %.0f ms after VDD >= VIT- + 0.2 V; with the controller's NRST pull-up and C418 the release adds at most 7.6 ms (circuit-proof.md, Reset row)" % (120, 280))
print("    NRST level held: VOL 0.4 V at 2 mA; the controller's pull-up is 3.4 V / 30 kohm = %.0f uA, so VOL <= 0.2 V (500 uA row) against VIL 0.3 VDD = %.2f V (3.3 V)" % (3.4 / 30e3 * 1e6, 0.3 * 3.3))
print("    pull-up limits of the supervisor sheet: 10 kohm to 1 Mohm; the controller's 30 to 50 kohm is inside; leakage IOH 100 nA x 50 kohm = %.1f mV" % (100e-9 * 50e3 * 1e3))

# ---- (4) mains-presence inputs, findings 1.2, 1.4, 1.9 ----------------------------------------
print("(4) mains-presence inputs PE15 and PD7 (FT_h), series R764/R774 27 kohm and pull-down R765/R775 82 kohm")
rs, rp = 27e3, 82e3
k = rp / (rs + rp)
k_hi = rp * 1.01 / (rs * 0.99 + rp * 1.01)
k_lo = rp * 0.99 / (rs * 1.01 + rp * 0.99)
v_wb = 5.125
print("    divider %.4f (%.4f to %.4f with 1 %% parts)" % (k, k_lo, k_hi))
print("    wall board high at the top of +5V_WB %.3f V: pin %.2f V (%.2f V at the 1 %% extreme) against the 4.0 V limit with VDD absent (Table 109: min(VDD+4.0, 6)): margin %.2f V"
      % (v_wb, v_wb * k, v_wb * k_hi, 4.0 - v_wb * k_hi))
print("    with VDD present the limit is 6 V: a wall board driving up to 6.75 V (module trip) gives %.2f V; positive injection does not occur below the maximum (Table 110), so no clamp current flows" % (6.75 * k_hi))
print("    double fault, module trip with VDD absent: %.2f V against 4.0 V (not covered; the module shuts down on the trip)" % (6.75 * k_hi))
vih = 0.7 * 3.4
print("    wall board must drive high at least VIH / k = %.2f / %.4f = %.2f V (VIH 0.7 VDD at VDD 3.4 V); a 5 V-class output meets it, a 3.3 V output with VOH under %.2f V does not" % (vih, k_lo, vih / k_lo, vih / k_lo))
vil = 0.3 * 3.2
print("    wall board absent or off: pin = leakage x 82 kohm = 0.25 uA x 82 kohm = %.0f mV (1.5 uA above VDD: %.0f mV) against VIL %.2f V: reads low, hysteresis %.0f mV typical" % (0.25e-6 * rp * 1e3, 1.5e-6 * rp * 1e3, vil, 250))
print("    wall board output low at up to 0.4 V reaches the pin at %.2f V; load on the wall board output at 5.125 V: %.0f uA" % (0.4 * k, v_wb / (rs + rp) * 1e6))
print("    power: 5.125 V across 109 kohm is %.2f mW (R764 %.2f mW, R765 %.2f mW) against 100 mW parts" % (v_wb ** 2 / (rs + rp) * 1e3, (v_wb / (rs + rp)) ** 2 * rs * 1e3, (v_wb / (rs + rp)) ** 2 * rp * 1e3))
print("    the pins must be plain floating inputs in firmware: Table 109 note 4, internal pull resistors off above 4 V")

# ---- (5) USB discharge residue at the clamp, owner level 4 --------------------------------------
print("(5) USB static discharge, owner level 4 (8 kV contact, 15 kV air); USBLC6-2SC6 DS4260 Rev 7")
print("    clamp: level 4 15 kV air and 8 kV contact in the features (Table 1 prints 15 kV contact: contradiction, either meets level 4); VCL 12 V at 1 A and 17 V at 5 A (8/20 us); 3.5 pF maximum")
print("    residue at PA11 and PA12: the clamp's own table gives %.0f V at 5 A, against the controller's 6 V DC limit (4 V with VDD absent): %.0f V over; the controller sheet states no pulse withstand, so the residue is not bounded by it" % (17, 17 - 6))
print("    8 kV contact through 330 ohm is 24 A: DS4260 2.1 gives 31.2 V with pin 5 open, about 23.0 V with D402 on the VBUS node (b_usb_power.py (e)); the 8/20 us table figure does not cover 24 A at 1 ns")

# ---- (6) unfitted options on the mains side ------------------------------------------------------
print("(6) pump snubber (R706 C701, R716 C711) and module inrush thermistor RT301, both not fitted")
v_rms, v_pk, f_lo, f_hi, c_sn, r_sn = 253.0, 253.0 * 2 ** 0.5, 50.0, 60.0, 100e-9, 100.0
import math
i_50 = v_rms * 2 * math.pi * f_lo * c_sn
i_60 = v_rms * 2 * math.pi * f_hi * c_sn
print("    snubber 100 ohm + 100 nF X2 (C101's part, 310 VAC): leakage with the triac off %.2f mA at 50 Hz, %.2f mA at 60 Hz; R dissipates %.1f mW; at turn-on from %.0f V crest: %.1f A peak, %.1f mJ"
      % (i_50 * 1e3, i_60 * 1e3, i_60 ** 2 * r_sn * 1e3, v_pk, v_pk / r_sn, 0.5 * c_sn * v_pk ** 2 * 1e3))
print("    the triac's VDRM is 600 V against the %.0f V crest of the supply: the rule is to fit the snubber only if the scope reads over 600 V at turn-off (bring-up)" % v_pk)
r_src = 230 * 2 ** 0.5 / 40.0
print("    thermistor NTC10D-9: module 40 A typical at 230 Vac implies %.1f ohm; at %.0f V crest %.1f A bare, %.1f A with 10 ohm added (-%.0f %%)"
      % (r_src, v_pk, v_pk / r_src, v_pk / (r_src + 10), 100 * (1 - (r_src) / (r_src + 10))))
print("    steady state: 0.46 ohm residual at 0.4 A (typical, 230 Vac) is %.2f V and %.2f W; the sheet's 2 A maximum steady current is 5x the module's 0.4 A; its 150 uF limit at 240 V against the module's input capacitance, which the module sheet does not state" % (0.46 * 0.4, 0.46 * 0.4 ** 2))
print("    link position: 1206 0 ohm chip rated 2 A with 10 A overload (UNI-ROYAL sheet, duration not stated) against 40 A typical inrush: a wire link is drawn instead")
