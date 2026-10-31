# Bring-up provision: Sunbeam EM7000 main controller board

Test points, isolating links, first-power current limiting and the pin classification of every connector, terminal, header and tab of the main board, kept to the method in `docs/board-design-method.md` ("Designing for bring-up and a second spin"). It is committed before any footprint is placed, and every row is cross-checked against the schematic specification (`schematic-spec.yaml`, generated into the KiCad schematic) and its exported netlist in the commit before placement.

Part references are those of `schematic-spec.yaml`. A test point is a one-pin pad part (`Connector:TestPoint`, `main-board:TestPoint_Pad_D1.0mm_Tight`) whose pin is on the net it tests. An isolating link is a two-pin part: a 0 ohm resistor, or a 2-pin 2.54 mm header with a shunt jumper, or two plated holes that take a wire link, a lamp or a resistor. Mains-referenced links (JP101) are in the `Mains` net class with the rest of the mains copper.

Where the method requires a rating for a link on a path that carries a protective device's fault current, the link's conductor row is in `circuit-proof.md`; a link whose rating or conductor row is not met there is listed in `open-items.md` and the row below stays open until the source it names is amended.

## Provisions

| Rail, producer-only net, key signal or first power | Net | Test point | Isolating link | What it is for |
|---|---|---|---|---|
| Rail Mains live (LINE) | LINE_IN, LINE_F, LINE, LINE1 | TP101, TP102, TP103, TP104 | JP101 | Produced by the retained mains lead at tab 2 (J102). Source side: J102 -> LINE_IN (TP101) -> fuse F101 (the series protective part) -> LINE_F (TP102) -> JP101 pin 1. Load side: JP101 pin 2 -> LINE (TP103: module through its series link JP303 on the Logic supply sheet, timing front end, voltage measurement, varistor RV101, X2 capacitor C101, discharge strings, interlock contact pin 14) and, through the interlock contact K201, LINE1 (TP104) to tab 1 (J101), which leaves the board for the loads. Opening JP101 separates the source side from every load. JP101 is a wire link in service (1.5 mm2) and carries up to 15 A in the fuse's band. |
| Rail Module mains feed (LINE_MOD) | LINE, LINE_MOD | TP103 | JP303 | Mains-referenced feed of the logic supply module U301 pin 1, between net LINE (after the first-power link JP101, TP103 on the source side) and LINE_MOD. JP303 is a wire link in service (two plated holes, 7.0 mm between pad edges, the footprint of JP101) and carries the module's 0.4 A typical at 230 Vac. RT301 (Ruilon NTC10D-9, 10 ohm cold, C3790) is an unfitted alternative across the same two nets: Bring-up step (logic supply step 8): at the first cold start from mains watch the entry fuse F101; fit RT301 in place of JP303 (remove the link, never fit both) only if F101 opens at a cold start, and say so in the bring-up record; if it does not open, leave RT301 unfitted. Both parts and LINE_MOD are mains class. |
| Rail +5V | +5V_MOD, +5V | TP301 | JP301 | Produced by U301 (Mean Well IRM-20-5, 5 V +/-2.5 %, rated 4 A, 2 A at 70 degC); source side holds the module's +Vo, C301 (100 nF), C302 (47 uF) and TP301. JP301 is a three-way selector (1 +5V_MOD, 2 +5V, 3 USB_VBUS_F): its one shorting jumper on pins 1-2 is the service position; a 22 ohm 5 W resistor's leads soldered to pins 1 and 2 in place of the jumper limit the rail's draw to 233 mA into a short. Power leaves the board through other sheets' connectors (sensor headers, relay coils, gauge harness, wall board), none enter by them. |
| Rail USB cable power | USB_VBUS_F, +5V | TP413 | JP301 | Bench power from the panel cable with mains disconnected. J402.5 (USB_VBUS) passes D402 (SMF6.0A to GND) and F401 (0.50 A hold PTC) to USB_VBUS_F (TP413, protected VBUS), which goes straight to pin 3 of the selector JP301 and nowhere else. The selector's one shorting jumper joins +5V to the module (pins 1-2, as drawn) or to USB_VBUS_F (pins 2-3), never both; it is the only thing that stops the cable and the module feeding each other, and the board never sources current into the cable. Order: (1) mains disconnected at the plug and the entry switch off; (2) move the JP301 jumper from pins 1-2 to pins 2-3; (3) read TP413 against GND with the cable plugged in, then +5V (about 4.35 V at the 0.32 A bench load: circuit-proof.md, USB power rows) and +3V3_REG at TP302; (4) with a series ammeter or a USB power meter on the cable, record the current at plug-in before the host configures the board and while it loads firmware, and watch TP413 on an oscilloscope at plug-in: the peak must stay under 6.0 V, the 3.3 V regulator's recommended input maximum (the fuse output is the rail, no blocking element sits between) (the unit-load rows of circuit-proof.md ask for it); (5) load firmware over the cable or J401. To return to mains operation: unplug the cable, move the jumper back to pins 1-2, and only then connect mains. Silkscreen beside JP301: 1-2 MODULE (MAINS), 2-3 USB ONLY (MAINS OFF). |
| Rail +3V3 | +3V3_REG, DBG_VTREF, +3V3_DBG, +3V3 | TP302, TP405 | JP302, JP402 | Two sources. Regulator: U302 (LT1963AEST-3.3#TRPBF, 20 V input rating) from +5V, with C303 at its input and C304 and C305 (22 uF X5R each) at its output on +3V3_REG, TP302 and JP302 (1x2 header and jumper). Supervisor U402 (TLV803S) watches +3V3 and holds NRST low below 2.87 to 2.99 V. Debug probe: J401.1 VTref on DBG_VTREF with TP405, then R402 (1 kohm, the current-limit means) to +3V3_DBG and JP402 (1x2 header and jumper). Open JP302 to measure +3V3_REG unloaded (but see the 5 V pull-up rule in notes below); open JP402 to remove the probe path. Pins through which power leaves: sensor and header 3V3 pins on other sheets. |
| Rail +3V3A | +3V3A_FB, +3V3A | TP303 | R301 | Derived from +3V3 by FB301 (600 ohm at 100 MHz, 0.50 ohm DC) onto +3V3A_FB with TP303; R301 (0 ohm, 1 A rated) is the isolating link. Feeds VDDA (pin 21) with C408 and C409 and the VREF+ link R302; any analogue front end that takes the converter's supply takes +3V3A. |
| Rail VREF+ | +3V3A, VREF+ | TP403, TP402 | R302 | Reference rail for the three ADCs: pin 20 with C410 (100 nF) and C411 (1 uF), tied to +3V3A through R302 (0 ohm, AN4938 Table 9 star point). TP403 on the source side (+3V3A), TP402 on the pin side to read what the converter sees. Opening R302 lets firmware use the internal reference buffer (2.5 V class) instead; the pin is then driven by the part. |
| Rail STMD_3V3 | STMD_3V3_SRC, STMD_3V3 | TP523 | R540 | 3.3 V feed of the digital steam-path pressure transducer: +3V3 through the PTC F520 to the test point and link R540, then pin 2 or 1 of J521; the PTC and the link are the only parts on the source side |
| Rail BRWD_3V3 | BRWD_3V3_SRC, BRWD_3V3 | TP526 | R541 | 3.3 V feed of the digital brew-path pressure transducer: +3V3 through the PTC F521 to the test point and link R541, then pin 2 or 1 of J522; the PTC and the link are the only parts on the source side |
| Rail SPAREA_3V3 | SPAREA_3V3_SRC, SPAREA_3V3 | TP528 | R542 | 3.3 V feed of the spare analogue input header: +3V3 through the PTC F522 to the test point and link R542, then pin 2 or 1 of J523; the PTC and the link are the only parts on the source side |
| Rail BREWA_3V3 | BREWA_3V3_SRC, BREWA_3V3 | TP530 | R543 | 3.3 V feed of the brew-path analogue header: +3V3 through the PTC F523 to the test point and link R543, then pin 2 or 1 of J524; the PTC and the link are the only parts on the source side |
| Rail SPAN2_3V3 | SPAN2_3V3_SRC, SPAN2_3V3 | TP532 | R544 | 3.3 V feed of the second spare analogue header: +3V3 through the PTC F524 to the test point and link R544, then pin 2 or 1 of J525; the PTC and the link are the only parts on the source side |
| Rail +5V_WB | +5V, +5V_WB | TP761 | JP761 | LED supply of the heater wall board's two opto-triac LEDs, taken from +5V; leaves the board on WB_LV10 pin 1 (power-leaving). Test point TP761 is on the load side: open JP761 and read the resistance from TP761 to GND before power; the source side is read at the +5V test point (owner B) |
| Rail +5V_GAUGE | +5V, +5V_GAUGE | TP791 | JP791 | supply of the retained gauge assembly through SP2 contact 1 (power-leaving) and the 47 uF latch-up capacitor C792; close JP791 with the +5V rail off (the capacitor charges from the rail) |
| Rail ANODE_RAIL | ANODE_SW, ANODE_RAIL | TP821 | JP821 | gated and modulated anode rail of the panel's eight indicators and the gauge assembly's low-water indicator (CON2 pin 7, SP2 contact 7, power-leaving); produced by Q822 from +5V, held off by R823 and R824, bled by R825; TP821 on the switch drain (source side of JP821) |
| Rail PT1 excitation return (FORCE-) | PT1_FORCEN_SRC, PT1_FORCEN | TP690 | R690 | The MAX31865 symbol types FORCE- (pin 9) power_out, so by the method's rule the net is a rail. Produced by U620 pin 9 (the sink of the excitation current); the source side carries that pin, the link R690 (0 ohm) and the test point. Load side: the probe header and the 3-wire/4-wire jumper. Opening the link disconnects the probe's return from the converter. Power leaves the board only as the excitation current out of FORCE+. |
| Rail PT2 excitation return (FORCE-) | PT2_FORCEN_SRC, PT2_FORCEN | TP691 | R691 | The MAX31865 symbol types FORCE- (pin 9) power_out, so by the method's rule the net is a rail. Produced by U621 pin 9 (the sink of the excitation current); the source side carries that pin, the link R691 (0 ohm) and the test point. Load side: the probe header and the 3-wire/4-wire jumper. Opening the link disconnects the probe's return from the converter. Power leaves the board only as the excitation current out of FORCE+. |
| Producer-only VCAP | VCAP | TP401 | — | Producer-only net: made by U401 pins 48 and 73 (core regulator output); capacitors C412, C413 |
| Producer-only AMC_DCDC_OUT | AMC_DCDC_OUT | TP605 | — | Producer-only net: made by U601; capacitors C603, C604; bead F601. isolated DC/DC output of the AMC131M02, mains-referenced; the datasheet's EMI bead F601 sits between it and AMC_HLDO_IN |
| Producer-only AMC_DCDC_HGND | AMC_DCDC_HGND | TP606 | — | Producer-only net: made by U601; capacitors C603, C604; bead F602. return of the isolated DC/DC output (pin DCDC_HGND), joined to HGND (the net AMC_HGND, which the net tie NT601 joins to NEUTRAL) through bead F602 |
| Producer-only AMC_HLDO_IN | AMC_HLDO_IN | TP607 | — | Producer-only net: made by U601; capacitors C605, C606; bead F601. input of the high-side LDO, after the bead |
| Producer-only AMC_HLDO_OUT | AMC_HLDO_OUT | TP608 | — | Producer-only net: made by U601; capacitors C607, C608. high-side LDO output, 2.6 to 3.2 V unloaded; powers the converter's input stage only (GPO unused) |
| Producer-only AMC_DCDC_CAP | AMC_DCDC_CAP | TP609 | — | Producer-only net: made by U601; capacitors C612. primary-side LDO output on the low-voltage side, 3.5 V absolute maximum |
| Producer-only PT1_BIAS | PT1_BIAS | TP620 | — | Producer-only net: made by U620; capacitors none; part the datasheet requires: R640. MAX31865 bias output (2.0 V nominal) tied to REFIN+ and the top of the reference resistor R640 |
| Producer-only PT2_BIAS | PT2_BIAS | TP622 | — | Producer-only net: made by U621; capacitors none; part the datasheet requires: R645. as PT1_BIAS for the second converter |
| Key signal: Carried: retained tab and link current ratings (row M18) | LINE1 | TP104 | — | Dongguan Bozhong publishes no rating for tabs J101 J102 J103 J106 to J110 or for the link JP101. Bring-up step, mains connected after the first-power steps: thermocouple on each joint and on its lead 100 mm along, 30 minutes at the machine full load; rise over the surrounding air at most 40 K (110 degC cap less the 70 degC air assumed). Limit and source: open-items.md, Bring-up measurements carried. |
| Key signal: Carried: C0G ceramics of the interlock (row M7) |  |  | — | Before mains, LCR meter: C202 and C204 at least 70 nF; C203 and C205 4.4547 to 4.9645 nF. Limit and source: open-items.md, Bring-up measurements carried. |
| Key signal: Interlock output: live to the loads | LINE1 | TP104 | — | interlock contact: live only when the drive holds the coil (compare TP104 with TP103) |
| Key signal: Proof-of-life output ahead of the buffer input series resistor R207 | POL_OUT | TP203 | — | interlock: high and low phase widths (at least 25 us each) and the 10 ms refresh are measured here |
| Key signal: Buffer output | POL_BUF | TP204 | — | interlock: the edges both channels see |
| Key signal: Channel A gate | POL_GATE_A | TP201 | — | interlock channel A: held level with the output toggling and held; read against 1.8 V |
| Key signal: Channel B gate | POL_GATE_B | TP202 | — | interlock channel B |
| Key signal: Coil low end | POL_COIL_LO | TP205 | — | interlock: coil voltage = TP206 minus TP205; read at pick-up and held level, and falling under 0.5 V within the interval when the controller stops |
| Key signal: Coil high end (+5V at the relay) | +5V | TP206 | — | interlock: the supply the coil sees (must stay at or above 4.75 V under the coil's load) |
| Key signal: Neutral on the plug side of the shunt | NEUTRAL_IN | TP105 | — | mains entry / shunt |
| Key signal: Neutral pour above the shunt | NEUTRAL | TP106 | — | mains entry / shunt: every load's return and the measurement reference |
| Key signal: Neutral on the plug side of the shunt, voltage pad | NEUTRAL_IN | TP107 | — | mains entry / shunt: second pad on the plug side of R105, read with TP108 for the voltage across the shunt (TP105 and TP106 carry the current) |
| Key signal: Neutral pour above the shunt, voltage pad | NEUTRAL | TP108 | — | mains entry / shunt: second pad on the neutral pour beside R105, read with TP107 for the voltage across the shunt |
| Key signal: Carried: Y402 shunt capacitance C0 (row M3) | LSE_IN |  | — | Before mains: LCR meter at 1 kHz on a spare Y402 from the same reel, C0 at most 2.58 pF; then firmware sweeps LSEDRV 00 to 11 and records the lowest setting at which LSERDY sets; it must set at 11. Limit and source: open-items.md, Bring-up measurements carried. |
| Key signal: Carried: crystal drive levels (rows M4 and M5) | HSE_IN | TP406 | — | Y401: Vrms at the crystal node with a probe of 10 pF or less, at most 0.82 V rms (drive level 100 uW max at ESR 80 ohm, C0 + CL 27 pF, 8 MHz). Y402 cannot be probed at home: worst case assumed, LSEDRV chosen as the lowest that starts it, 0.5 uW limit unproven. Limit and source: open-items.md, Bring-up measurements carried. |
| Key signal: Carried: VCAP capacitance (row M8) | VCAP | TP401 | — | Before mains: C412 and C413 by LCR meter and by the charge-time method at 1.4 V; reading times 0.85 at least 1.76 uF (secant reading at least 2.07 uF), each at most 2.64 uF. Limit and source: open-items.md, Bring-up measurements carried. |
| Key signal: Carried: supervisor window and load-step dip (row M19) | NRST | TP404 | — | Bench supply on +3V3 with JP302 open: falling threshold 2.87 to 2.99 V and td 120 to 280 ms; +3V3 at TP302 stays at or above 3.0 V while all peripherals are enabled and while 0.293 A is switched on the rail. Limit and source: open-items.md, Bring-up measurements carried. |
| Key signal: Carried: module inrush and entry fuse I2t (row M11) | LINE_MOD | TP103 | — | Shunt R105 (TP105 to TP106) with an isolated or differential probe, single-shot at the first current-limited connection and at the first cold start with the lamp removed: integral of i squared dt at most 50 A2s (10 percent of the fuse 500 A2s), F101 intact at ten cold starts; otherwise fit RT301 in place of JP303. Limit and source: open-items.md, Bring-up measurements carried. |
| Key signal: Carried: C302 reverse voltage (row M17) | +5V_MOD | TP301 | — | Scope, DC-coupled, minimum held, across C302 through JP301 moves, cable plug-in and removal, and mains on and off: no reverse voltage beyond the 50 mV resolution. Limit and source: open-items.md, Bring-up measurements carried. |
| Key signal: Carried: ceramics of the controller and logic supply (rows M7 and M10) |  |  | — | Before mains, LCR meter: C414 and C415 19.0 to 21.0 pF and C416 and C417 4.45 to 4.95 pF on spares from the same reel; C303 and C418 by the charge-time method at least 50 percent of nominal. Limit and source: open-items.md, Bring-up measurements carried. |
| Key signal: reset | NRST | TP404 | — | controller reset: SW401, C418, internal pull-up; also J401.10 and the open-drain output of the supervisor U402 (TLV803S): low while +3V3 is under 2.87 to 2.99 V and for 120 to 280 ms after it recovers |
| Key signal: HSE clock | HSE_IN | TP406 | — | 8 MHz oscillator Y401. No pin is free for a buffered clock output (MCO1 is PA8, the steam pump gate; MCO2 is PC9, a load-cell clock), so the clock is read at the crystal node with a probe of 10 pF or less; the pad (1.5 mm) and probe load the oscillator and move the frequency by a fraction of the load capacitance, so measure frequency to a few hundred ppm only; remove the probe for any accuracy check. A firmware alternative with no probing: the controller counts HSE against another clock. |
| Key signal: LSE clock | LSE_IN | none | — | 32.768 kHz oscillator Y402: no test point, a pad on a 12.5 pF crystal node would shift the frequency by a visible fraction; the block is judged by the RTC running in firmware (LSERDY flag). LSE is an anticipated function with no requirement relying on it |
| Key signal: serial-wire data | SWDIO | TP407 | — | debug and programming: the header pin is the access point; test point pad added so a probe reaches the net without the header |
| Key signal: serial-wire clock | SWCLK | TP408 | — | debug and programming: the header pin is the access point; test point pad added so a probe reaches the net without the header |
| Key signal: serial-wire output | SWO | TP409 | — | trace output, PB3 (optional); test point pad added so a probe reaches the net without the header |
| Key signal: boot mode | BOOT0 | TP410 | — | boot strap: R401 pull-down, JP401 to +3V3; the jumper pin is the access point; test point pad added so a probe reaches the net without the header |
| Key signal: USB data plus | USB_DP | TP411 | — | panel-cable USB port, PA12: J402.1 and the ESD clamp D401; test point pad added so a probe reaches the net without the header |
| Key signal: USB data minus | USB_DM | TP412 | — | panel-cable USB port, PA11: J402.2 and the ESD clamp D401; test point pad added so a probe reaches the net without the header |
| Key signal: proof-of-life output | POL_OUT | TP203 | — | PC7: the interlock drive's input, through R207 to the buffer; its test point belongs to the interlock block that consumes it |
| Key signal: Carried: filter capacitors C501 C502 C503 C520 C522 C523 C524 C570 C571 (row M6) |  |  | — | Before mains: LCR meter and the charge-time method at the working voltage; each from 80 pF to 59.5 nF. Limit and source: open-items.md, Bring-up measurements carried. |
| Key signal: Carried: sensor 3.3 V feed capacitance and plug-in dip (row M13) | STMD_3V3 | TP523 | — | LCR meter at each sensor header feed pin with the sensor connected; scope on +3V3 (TP302) and on the feed (TP523, TP526, TP528, TP530, TP532) at plug-in: +3V3 stays at or above 3.0 V and the feed charges through at most 2.67 A for at most 0.20 s. Limit and source: open-items.md, Bring-up measurements carried. |
| Key signal: Carried: I2C bus far end (row M20) | STM_SCL | TP521 | — | Line capacitance at most 400 pF (LCR meter, sensor and cable connected, unpowered); on TP521, TP522, TP524 and TP525 rise time 30 to 70 percent at most 1000 ns and low level at most 0.4 V. Limit and source: open-items.md, Bring-up measurements carried. |
| Key signal: Carried: flow meter output levels (row M21) | FLOW_IN | TP520 | — | Flow meter connected, flowing and stopped: low level at most 0.940 V, high level at least 2.52 V. Limit and source: open-items.md, Bring-up measurements carried. |
| Key signal: NTC_COF | NTC_COF | TP501 | — | coffee-block thermistor divider and filter (PC0) |
| Key signal: NTC_STM | NTC_STM | TP502 | — | steam-block thermistor divider and filter (PC1) |
| Key signal: NTC_WAND | NTC_WAND | TP503 | — | wand thermistor divider and filter (PC4) |
| Key signal: FLOW_IN | FLOW_IN | TP520 | — | flow-meter input after the link or buffer (PC6) |
| Key signal: STM_SCL | STM_SCL | TP521 | — | steam-path I2C clock (PB8) |
| Key signal: STM_SDA | STM_SDA | TP522 | — | steam-path I2C data (PB9) |
| Key signal: BREW_SCL | BREW_SCL | TP524 | — | brew-path I2C clock (PB10) |
| Key signal: BREW_SDA | BREW_SDA | TP525 | — | brew-path I2C data (PB11) |
| Key signal: STMP_AN | STMP_AN | TP527 | — | steam-path analogue fallback after scaling and filter (PC5) |
| Key signal: BREW_AN | BREW_AN | TP529 | — | brew-path analogue fallback after scaling and filter (PA6) |
| Key signal: SPARE_AN2 | SPARE_AN2 | TP531 | — | second spare analogue after scaling and filter (PA0) |
| Key signal: CURR1_AN | CURR1_AN | TP570 | — | current sensor 1 after scaling and filter (PA2) |
| Key signal: CURR2_AN | CURR2_AN | TP571 | — | current sensor 2 after scaling and filter (PA3) |
| Key signal: Carried: pump gate resistor pulse (row M14) | PUMP_C_GATE_R | TP702 | — | Before mains: R704 R705 R714 R715 200 ohm +/-1 percent. At the first current-limited connection with the pump commanded: isolated probe across R704 and R714, at most 200 V across one resistor, pair peak current at most 1 A; after ten minutes of pump running the values are within 1 percent of the first reading. Limit and source: open-items.md, Bring-up measurements carried. |
| Key signal: Carried: snubber resistor pulse (row M15) | PUMP_C_SNUB | TP702 | — | Only if R706 C701 or R716 C711 is fitted: worst case assumed 3.6 A and 6.4 mJ per turn-on; after ten minutes of pump running, cold and mains off, each resistor within 1 percent of 100 ohm and not discoloured. Limit and source: open-items.md, Bring-up measurements carried. |
| Key signal: Carried: pump triac turn-off voltage staging (row M16) | PUMP_S_MT2 | TP712 | — | Read at TP702 and TP712 first at the first current-limited connection with the lamp, then with the lamp removed and the pump at full load; the full-load reading is compared with 600 V. Limit and source: open-items.md, Bring-up measurements carried. |
| Key signal: Carried: C792 reverse voltage (row M17) | +5V_GAUGE | TP791 | — | Scope, DC-coupled, minimum held, across C792 through JP791 closed and opened and mains on and off: no reverse voltage beyond the 50 mV resolution. Limit and source: open-items.md, Bring-up measurements carried. |
| Key signal: Carried: key line levels with the panel connected (row M23) | KEY1 | TP831 | — | Panel connected, indicators lit and unlit, on TP831 to TP835: pressed at most 0.940 V, released at least 2.520 V. Limit and source: open-items.md, Bring-up measurements carried. |
| Key signal: Carried: knob filter capacitors C861 C862 C863 (row M9) | KNOB_HOT | TP861 | — | Before mains: LCR meter and the charge-time method at 3.6 V, each at least 90 nF. Limit and source: open-items.md, Bring-up measurements carried. |
| Key signal: PUMP_C_GATE | PUMP_C_GATE | TP701 | — | coffee pump drive stage control input (PA9) |
| Key signal: PUMP_S_GATE | PUMP_S_GATE | TP711 | — | steam pump drive stage control input (PA8) |
| Key signal: Coffee pump triac MT2 | PUMP_C_MT2 | TP702 | — | mains-referenced: coffee pump triac T701 MT2 against NEUTRAL (TP106). Bring-up step: with the pump running from the controller, scope this node with an isolated or differential probe, never an earthed lead, at the instant the triac turns off (the pump's current zero, and at a stop command); if the voltage across the triac exceeds its 600 V rating (VDRM, WeEn BTA204S-600B Rev.02), fit the snubber R706 (100 ohm, 2512) and C701 (100 nF X2) across MT2 and MT1 and repeat; otherwise leave them unfitted (owner decision of 2026-10-29) |
| Key signal: Steam pump triac MT2 | PUMP_S_MT2 | TP712 | — | mains-referenced: steam pump triac T711 MT2 against NEUTRAL (TP106). Bring-up step: as TP702 for the steam pump; fit R716 (100 ohm, 2512) and C711 (100 nF X2) only if the turn-off voltage exceeds 600 V |
| Key signal: VALVE_2W_DRV | VALVE_2W_DRV | TP731 | — | two-way valve relay coil driver control input (PD4) |
| Key signal: VALVE_3W_DRV | VALVE_3W_DRV | TP741 | — | three-way valve relay coil driver control input (PD5) |
| Key signal: HEAT_C_DRV | HEAT_C_DRV | TP762 | — | coffee heater LED drive control input (PD2) |
| Key signal: HEAT_S_DRV | HEAT_S_DRV | TP772 | — | steam heater LED drive control input (PD3) |
| Key signal: GAUGE_RST | GAUGE_RST | TP792 | — | gauge buffer input, driver reset |
| Key signal: GAUGE_STEP1 | GAUGE_STEP1 | TP793 | — | gauge buffer input, gauge A step clock |
| Key signal: GAUGE_DIR1 | GAUGE_DIR1 | TP794 | — | gauge buffer input, gauge A direction |
| Key signal: GAUGE_STEP2 | GAUGE_STEP2 | TP795 | — | gauge buffer input, gauge B step clock |
| Key signal: GAUGE_DIR2 | GAUGE_DIR2 | TP796 | — | gauge buffer input, gauge B direction |
| Key signal: ANODE_GATE | ANODE_GATE | TP822 | — | anode rail gate control input (PB5) |
| Key signal: BUZZER | BUZZER | TP823 | — | buzzer stage control input (PE1) |
| Key signal: LOWWATER_K | LOWWATER_K | TP824 | — | low-water indicator sink control input (PE0) |
| Key signal: KEY1 | KEY1 | TP831 | — | panel key line PWR (PE2): key level and indicator sink |
| Key signal: KEY2 | KEY2 | TP832 | — | panel key line MAN (PE3) |
| Key signal: KEY3 | KEY3 | TP833 | — | panel key line ONE (PE4) |
| Key signal: KEY4 | KEY4 | TP834 | — | panel key line TWO (PE5) |
| Key signal: KEY5 | KEY5 | TP835 | — | panel key line PRG (PE6) |
| Key signal: KNOB_HOT | KNOB_HOT | TP861 | — | hot-water knob microswitch input (PE13) |
| Key signal: KNOB_STEAM | KNOB_STEAM | TP862 | — | steam knob microswitch input (PE14) |
| Key signal: TANK_LEVEL | TANK_LEVEL | TP863 | — | tank reed input (PE12) |
| Key signal: Carried: HX711 supply at the pin (row M1) | +5V |  | — | Module position: multimeter on VSUP of U630 and U631 at the first current-limited connection and at full load, scope held for the first second after mains on; at most 5.5 V (module 5.125 V at most). Worst case assumed above 5.5 V: module trip 6.75 V, D402 clamp 10.3 V. Limit and source: open-items.md, Bring-up measurements carried. |
| Key signal: Carried: HX711 input source resistance and sampling draw (row M2) | WT1_INA_P | TP671 | — | Before mains: legs R670 R671 R675 R676 100 ohm +/-1 percent, C670 and C675 0.1 uF +/-10 percent. Bench supply, mains off, bridge simulator: 100 conversions as built and with 1 kohm legs, mean shift at most one standard deviation. Limit and source: open-items.md, Bring-up measurements carried. |
| Key signal: Carried: load-cell and probe input capacitance (row M12) | WT2_INA_P | TP673 | — | LCR meter at the connector with the sensor and cable connected, unpowered: load cell at most 3.75 uF across the inputs; probe sensor at most 0.50 uF (from 10.5 R C + 1 ms within the 10 ms control step). Limit and source: open-items.md, Bring-up measurements carried. |
| Key signal: Carried: zero-crossing optocoupler timing (row M22) | ZC_IN | TP630 | — | Isolated or differential probe on TP603: assert delay 0.068 to 0.781 ms and release lead 0.296 to -0.008 ms after the true crossing, spread at most 12.8 degrees of the 50 Hz cycle; first current-limited connection. Limit and source: open-items.md, Bring-up measurements carried. |
| Key signal: Carried: ceramics of the measurement front ends (rows M7, M9 and M10) |  |  | — | Before mains, LCR meter: C601 and C602 4.23 to 5.17 nF; C640 and C645 at most 11 nF; C630 0.6 to 1.4 nF; C603 to C608, C612, C670, C672, C675 and C677 by the charge-time method at least 50 percent of nominal. Limit and source: open-items.md, Bring-up measurements carried. |
| Key signal: Carried: air temperature at U601 beside the interlock relay (row M25) |  |  | — | Thermocouple 2 mm from the body of U601 on the relay side, machine at full load for 30 minutes and again idle, once the earlier steps pass, mains present; air at most 125 degC, the part's ambient limit. Limit and source: open-items.md, Bring-up measurements carried, and the owner's acceptance (h). |
| Key signal: converter data ready | AMC_DRDY | TP601 | — | AMC131M02: falls when a new pair of readings is ready; shows the converter is clocked, enabled and converting |
| Key signal: converter clock | AMC_CLKIN | TP602 | — | AMC131M02 clock after the 33 ohm termination: 8.000 MHz, 45 to 55 % duty |
| Key signal: divider tap | VMEAS_DIV | TP603 | — | mains voltage divider: about 0.30 V peak at 253 V rms, in phase with the line; mains-referenced, measure with an isolated instrument |
| Key signal: shunt channel input | AMC_AIN1P | TP604 | — | supply current channel after its filter: 21 mV peak at 15 A rms; mains-referenced |
| Key signal: shared SPI2 data out | SPI2_MISO | TP610 | — | replies of the AMC131M02 and both MAX31865 converters |
| Key signal: zero-crossing edge | ZC_IN | TP630 | — | supply-timing front end: two falling edges per cycle (100 a second at 50 Hz); the delay against the line is read live |
| Key signal: probe 1 sense node | PT1_RTDINP | TP621 | — | converter 1 RTDIN+: about 0.59 V with a 150 degC probe, 0.41 V at 0 degC |
| Key signal: probe 2 sense node | PT2_RTDINP | TP623 | — | converter 2 RTDIN+ |
| Key signal: weight 1 data | WT1_DATA | TP670 | — | HX711 channel 1 DOUT: high idle, low when a result is ready |
| Key signal: weight 1 signal | WT1_INA_P | TP671 | — | HX711 channel 1 INA+ after the filter: 2.4 V common mode with the bridge connected |
| Key signal: weight 2 data | WT2_DATA | TP672 | — | HX711 channel 2 DOUT |
| Key signal: weight 2 signal | WT2_INA_P | TP673 | — | HX711 channel 2 INA+ after the filter |
| First power: J102.1 / LINE_IN (tab 2, live) | J102.1 / LINE_IN (tab 2, live) | — | JP101 | Means: a lamp (a 60 W to 100 W 230 V incandescent lamp, or a 230 V halogen of the same rating) with its two leads fitted in JP101's two through-hole pads in place of the wire link; the lamp is upstream of everything the input feeds (between the pin and the lamp are only F101, TP101 and TP102) Limited current: Short on the board: 253 V / hot lamp resistance. 60 W lamp: R = 230 V squared / 60 W = 882 ohm, 253 / 882 = 0.287 A; 100 W lamp: 529 ohm, 0.478 A (circuit-proof/A_calcs.out). Cold-filament inrush is larger for some tens of milliseconds and its ratio is not read from a source here, so it is not stated; F101 stays in series as protection. The lamp is not a fuse: it is the means, and it limits a short to those figures. |
| First power: J103.1 / NEUTRAL_IN (tab 3, neutral) | J103.1 / NEUTRAL_IN (tab 3, neutral) | — | JP101 | Means: the same lamp in JP101: tab 3 is the other end of the same supply loop, so no current can enter at tab 3 beyond what the lamp lets leave at tab 2 (the live is the only path by which the supply can drive a short through the board) Limited current: As the row above, 0.287 A (60 W) to 0.478 A (100 W) at 253 V. The method asks every supply input for its own means; whether a second position in the neutral return is wanted is an owner decision (open-items.md, first power). |
| First power: J401.1 DBG_VTREF | J401.1 DBG_VTREF | — | JP402 | Means: R402, 1 kohm +/-1 %, on the board, in series between J401.1 (with TP405) and JP402; nothing but TP405 lies between the pin and R402 Limited current: I = V / R402: a probe that sources 5.0 V on VTref into a short on +3V3 gives 5.0 V / 1 kohm = 5.0 mA (5.5 mA at 5.5 V, 3.6 mA at 3.6 V); with the link open nothing flows |
| First power: U301.1 and U301.2 LINE and NEUTRAL (mains) | U301.1 and U301.2 LINE and NEUTRAL (mains) | — | owner A's position, not this sheet's | Means: the first-power means of the board's mains entry (owner A), which sits upstream of net LINE; the module takes LINE_MOD (LINE through the link JP303) and NEUTRAL and adds no means of its own. Interface requirement for the lead: the net the module taps must be on the load side of that means. If A's means is a lamp or resistor in the link between the entry fuse and net LINE, it limits the module's cold-start inrush too; if the module tap is on the fuse's own load-side clip ahead of that link, the module is not limited and the lead places a means here Limited current: not computed here: the means is owner A's and its arithmetic is A's row; the module's cold start is 40 A typical at 230 Vac (IRM-20 sheet), typical only (inrush row of circuit-proof.md) |

## Pins of every connector, terminal, header and tab

| Pin | Net | Class | Why |
|---|---|---|---|
| J101.1 | LINE1 | power_leaving | tab 1: the board feeds the live, after the interlock contact, to every load's fixed lead by the retained daisy-chain wire; nothing is fed in through it |
| J102.1 | LINE_IN | supply_input | tab 2: the retained mains lead's live conductor (brown, from the plug); powers the module, the controller and every load through F101 and JP101 |
| J103.1 | NEUTRAL_IN | supply_input | tab 3: the retained mains lead's neutral (blue, from the plug); the return of the same supply, through the shunt R105 to NEUTRAL |
| J106.1 | COFVALVE | signal | tab 6: the two-way valve coil's switched side to relay K_V1; the coil is fed from LINE1 (tab 1), so power reaches this pin only through the board's own LINE1, not from outside |
| J107.1 | COFFPUMP | signal | tab 7: coffee pump's switched side to the pump drive; fed from LINE1 |
| J108.1 | STEAMPUMP | signal | tab 8: steam pump's switched side to the pump drive; fed from LINE1 |
| J109.1 | HOTVALVE | signal | tab 9: three-way valve coil's switched side to relay K_V2; fed from LINE1 |
| J110.1 | NEUTRAL | signal | WB_RET landing: the heater wall board's return wire (the heater current's return from the triacs) onto the neutral pour above the shunt; the wall board is passive and fed from LINE1 |
| J401.1 | DBG_VTREF | supply_input | Cortex Debug VTref: a probe senses the target voltage here and some probes can also source power on it; classed a supply input and reaches +3V3 only through R402 (1 kohm) and JP402 |
| J401.2 | SWDIO | signal | serial-wire data, PA13 |
| J401.3 | GND | ground | ground |
| J401.4 | SWCLK | signal | serial-wire clock, PA14 |
| J401.5 | GND | ground | ground |
| J401.6 | SWO | signal | serial-wire output, PB3 |
| J401.7 | no connect | signal | key position of the Cortex Debug 10-pin header; no contact |
| J401.8 | no connect | signal | NC/TDI, JTAG data in, not used with serial wire |
| J401.9 | GND | ground | GND detect, grounded on the target |
| J401.10 | NRST | signal | target reset from the probe |
| J402.1 | USB_DP | signal | USB D+ from the panel cable, PA12 |
| J402.2 | USB_DM | signal | USB D- from the panel cable, PA11 |
| J402.3 | GND | ground | USB return from the panel cable |
| J402.4 | USB_SHIELD | signal | cable shield; reaches GND only through R403 (1 MOhm) and C419 (4.7 nF) in parallel, so a panel connector shell touching earthed metal cannot tie earth to controller ground |
| J402.5 | USB_VBUS | supply_input | the cable's VBUS for bench power; reaches the board only through D402, F401 and the cable position of the selector JP301, which is open as drawn; carries no mains-referenced net |
| J501.1 | NTC_COF_SENS | signal | coffee block thermistor, divider node; the thermistor has no polarity |
| J501.2 | GND | ground | thermistor return |
| J502.1 | NTC_STM_SENS | signal | steam block thermistor, divider node; the thermistor has no polarity |
| J502.2 | GND | ground | thermistor return |
| J503.1 | NTC_WAND_SENS | signal | steam wand disc thermistor, divider node; the thermistor has no polarity |
| J503.2 | GND | ground | thermistor return |
| J520.1 | +5V | power_leaving | 5 V supply of the flow meter (record: pin 1 VCC5); unfused; nothing can power the board through it |
| J520.2 | GND | ground | flow-meter ground |
| J520.3 | FLOW_RAW | signal | flow-meter pulse output, up to 5.25 V |
| J521.1 | STMD_3V3 | power_leaving | 3.3 V supply of the digital pressure transducer through the PTC and link; nothing can power the board through it |
| J521.2 | GND | ground | transducer ground |
| J521.3 | STM_SCL_X | signal | I2C clock |
| J521.4 | STM_SDA_X | signal | I2C data |
| J522.1 | BRWD_3V3 | power_leaving | 3.3 V supply of the digital pressure transducer through the PTC and link; nothing can power the board through it |
| J522.2 | GND | ground | transducer ground |
| J522.3 | BREW_SCL_X | signal | I2C clock |
| J522.4 | BREW_SDA_X | signal | I2C data |
| J523.1 | +5V | power_leaving | 5 V supply of an analogue sensor; unfused |
| J523.2 | SPAREA_3V3 | power_leaving | 3.3 V supply of an analogue sensor through the PTC and link |
| J523.3 | GND | ground | sensor ground |
| J523.4 | SPAREA_RAW | signal | analogue sensor output, up to 5.5 V |
| J524.1 | +5V | power_leaving | 5 V supply of an analogue sensor; unfused |
| J524.2 | BREWA_3V3 | power_leaving | 3.3 V supply of an analogue sensor through the PTC and link |
| J524.3 | GND | ground | sensor ground |
| J524.4 | BREWA_RAW | signal | analogue sensor output, up to 5.5 V |
| J525.1 | +5V | power_leaving | 5 V supply of an analogue sensor; unfused |
| J525.2 | SPAN2_3V3 | power_leaving | 3.3 V supply of an analogue sensor through the PTC and link |
| J525.3 | GND | ground | sensor ground |
| J525.4 | SPAN2_RAW | signal | analogue sensor output, up to 5.5 V |
| J570.1 | +5V | power_leaving | 5 V supply of the current sensor; unfused |
| J570.2 | CURR1_SIG | signal | current sensor output |
| J570.3 | GND | ground | current sensor return |
| J571.1 | +5V | power_leaving | 5 V supply of the current sensor; unfused |
| J571.2 | CURR2_SIG | signal | current sensor output |
| J571.3 | GND | ground | current sensor return |
| J620.1 | PT1_FORCEP | signal | FORCE+ lead of probe 1: carries the converter's bias current out to the probe (0.36 to 0.51 mA), not a supply input |
| J620.2 | PT1_RTDINP | signal | RTDIN+ sense lead of probe 1 |
| J620.3 | PT1_RTDINN | signal | RTDIN- sense lead of probe 1 |
| J620.4 | PT1_FORCEN | signal | FORCE- return lead of probe 1 (switched to ground inside the converter) |
| J622.1 | PT1_FORCEP | signal | 2-wire link, FORCE+ side |
| J622.2 | PT1_RTDINP | signal | 2-wire link, RTDIN+ side |
| J623.1 | PT1_RTDINN | signal | 2-wire and 3-wire link, RTDIN- side |
| J623.2 | PT1_FORCEN | signal | 2-wire and 3-wire link, FORCE- side |
| J625.1 | PT2_FORCEP | signal | FORCE+ lead of probe 2 |
| J625.2 | PT2_RTDINP | signal | RTDIN+ sense lead of probe 2 |
| J625.3 | PT2_RTDINN | signal | RTDIN- sense lead of probe 2 |
| J625.4 | PT2_FORCEN | signal | FORCE- return lead of probe 2 |
| J627.1 | PT2_FORCEP | signal | 2-wire link, FORCE+ side, probe 2 |
| J627.2 | PT2_RTDINP | signal | 2-wire link, RTDIN+ side, probe 2 |
| J628.1 | PT2_RTDINN | signal | 2-wire and 3-wire link, RTDIN- side, probe 2 |
| J628.2 | PT2_FORCEN | signal | 2-wire and 3-wire link, FORCE- side, probe 2 |
| J630.1 | +5V | power_leaving | excitation E+ of load cell 1: the board supplies the bridge (about 14 mA at 350 ohm, assumed); nothing can power the board through it |
| J630.2 | GND | ground | excitation return E- of load cell 1 |
| J630.3 | WT1_SN_RAW | signal | A- signal lead of load cell 1 |
| J630.4 | WT1_SP_RAW | signal | A+ signal lead of load cell 1 |
| J630.5 | GND | ground | cable shield of load cell 1 |
| J635.1 | +5V | power_leaving | excitation E+ of load cell 2 |
| J635.2 | GND | ground | excitation return E- of load cell 2 |
| J635.3 | WT2_SN_RAW | signal | A- signal lead of load cell 2 |
| J635.4 | WT2_SP_RAW | signal | A+ signal lead of load cell 2 |
| J635.5 | GND | ground | cable shield of load cell 2 |
| J761.1 | +5V_WB | power_leaving | LED supply of the wall board's two opto-triac LEDs, through JP761 from +5V; nothing can power the board through it |
| J761.2 | HEAT_C_LED_K | signal | coffee opto-triac LED return, sunk by Q761 through R763 |
| J761.3 | HEAT_S_LED_K | signal | steam opto-triac LED return, sunk by Q771 through R773 |
| J761.4 | GND | ground | return |
| J761.5 | MAINS_PRES_C_J | signal | mains-presence confirm from the wall board, header side (net MAINS_PRES_C_J): through R764 (27 kohm) to PE15, which R765 (82 kohm) holds low with the wall board absent; the wall board must drive at least 3.2 V when on and at most 5.5 V |
| J761.6 | MAINS_PRES_S_J | signal | mains-presence confirm from the wall board, header side (net MAINS_PRES_S_J): through R774 (27 kohm) to PD7, which R775 (82 kohm) holds low with the wall board absent; the wall board must drive at least 3.2 V when on and at most 5.5 V |
| J761.7 |  | signal | spare, not connected |
| J761.8 |  | signal | spare, not connected |
| J761.9 |  | signal | spare, not connected |
| J761.10 |  | signal | spare, not connected |
| J791.1 | +5V_GAUGE | power_leaving | supply of the retained VID66-08 gauge driver through JP791 from +5V |
| J791.2 | GND | ground | return |
| J791.3 | GAUGE_RST_B | signal | driver reset, buffered, held low by R806 |
| J791.4 | GAUGE_STEP1_B | signal | FA, gauge A step clock, buffered |
| J791.5 | GAUGE_DIR1_B | signal | DIRA, gauge A direction, buffered |
| J791.6 | LOWWATER_CATHODE | signal | WAT, low-water indicator cathode, sunk by Q824 |
| J791.7 | ANODE_RAIL | power_leaving | gated anode rail that lights the low-water indicator, from Q822 through JP821 |
| J791.8 | GAUGE_DIR2_B | signal | DIRB, gauge B direction, buffered |
| J791.9 | GAUGE_STEP2_B | signal | FB, gauge B step clock, buffered |
| J821.1 | BUZZER_P | power_leaving | buzzer drive side: +5V through R828 (100 ohm), switched on its return by Q823 |
| J821.2 | BUZZER_N | signal | buzzer return, sunk by Q823 |
| J821.3 | KEY1 | signal | PWR key pair and one indicator cathode |
| J821.4 | KEY2 | signal | MAN key pair and two indicator cathodes |
| J821.5 | KEY3 | signal | ONE key pair and one indicator cathode |
| J821.6 | KEY4 | signal | TWO key pair and two indicator cathodes |
| J821.7 | ANODE_RAIL | power_leaving | gated anode rail for all indicator elements, from Q822 through JP821 |
| J821.8 | KEY5 | signal | PRG key pair and two indicator cathodes |
| J821.9 | GND | ground | switch common |
| J861.1 | KNOB_HOT | signal | hot-water microswitch lead (red), pulled up |
| J861.2 | GND | ground | hot-water microswitch's other lead |
| J861.3 | KNOB_STEAM | signal | steam microswitch lead (red), pulled up |
| J861.4 | GND | ground | steam microswitch's other lead |
| J862.1 | GND | ground | reed element lead 1 (a contact has no polarity) |
| J862.2 | TANK_LEVEL | signal | reed element lead 2, pulled up |
| JP301.1 | +5V_MOD | signal | selector, module side; power reaches it only through the module |
| JP301.2 | +5V | signal | selector, common (the rail's load side) |
| JP301.3 | USB_VBUS_F | signal | selector, cable side; reached only from the fuse F401 output, which is this net |
| JP302.1 | +3V3_REG | signal | isolating link, source side |
| JP302.2 | +3V3 | signal | isolating link, load side |
| JP303.1 | LINE | supply_input | module feed link, line side, net LINE after the first-power link JP101 and the entry fuse; mains-referenced |
| JP303.2 | LINE_MOD | signal | module feed link, module side, the module's live pin only; mains-referenced |
| JP401.1 | BOOT0 | signal | boot strap jumper; not a supply path |
| JP401.2 | +3V3 | signal | boot strap jumper, tied to the 3.3 V rail; power reaches it only from the rail |
| JP402.1 | +3V3_DBG | signal | isolating link of the debug source, source side |
| JP402.2 | +3V3 | signal | isolating link, load side |
| RT301.1 | LINE | supply_input | inrush thermistor, line side (not fitted), the same net as JP303.1; mains-referenced |
| RT301.2 | LINE_MOD | signal | inrush thermistor, module side (not fitted), the same net as JP303.2; mains-referenced |
| U301.1 | LINE_MOD | supply_input | mains live feed of the logic supply module, from net LINE through the link JP303 (or the unfitted thermistor RT301), upstream of the interlock contact (the module keeps power when the contact opens); mains-referenced |
| U301.2 | NEUTRAL | supply_input | mains neutral feed of the module, from the neutral pour above the shunt; mains-referenced |
| U301.3 | GND | ground | module -Vo, the low-voltage ground |
| U301.4 | +5V_MOD | signal | module +Vo: the rail's producer, a board-internal net; the module is a part, not a connector |
