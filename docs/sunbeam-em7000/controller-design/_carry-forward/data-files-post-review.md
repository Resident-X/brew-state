# Data files post-review: change log

Review fixes applied to the six CSV files in `controller-design/` (control-system-bom, part-numbers, passive-and-drive-components, h743-pin-allocation, h743-header-pinout, module-interconnect). Edits were made with Python's csv module: CRLF line endings kept, every row's column count equal to its header (module-interconnect.csv is now 4 columns throughout). Sources used: `decisions.md`, `hydraulic-lines.md`, `reference-machine.md`, `connector-pinouts.md`, and `control-board-electrical-requirements.csv` (for channel codes). Item numbers refer to the review list.

Rows are identified by their first-column text (the Item, Role, Channel or Designator value). Column is given by name where the file has a header, otherwise by index.

## control-system-bom.csv

- Row `EARU SSR-40DA solid state relay` (column: Note): item1: stale FET drive text replaced by D2 ULN2003A drive
- Row `EARU SSR-40DA solid state relay` (column: Rail): item1: Rail was "3V3 ctrl"
- Row `XDB401 3.3V I2C` (column: Note): item5: STEAM tap is a PTFE drop leg (D14), capillary is the fallback
- Row `XDB401 3.3V I2C` (column: Note): item5: D13 is Agreed, not "not yet confirmed by the owner"
- Row `XDB401 3.3V I2C` (column: Note): item2: burst/overload labelled gauge vs absolute; OPV made conditional
- Row `[RETAINED] Mechanical OPV, steam line (directly on the steam pump outl` (column: Note): item2: removed contradiction with the owner statement (downstream of the pump check valve, F6); open question narrowed to the block side
- Row `[RETAINED] Mechanical OPV, steam line (directly on the steam pump outl` (column: Note): item2: pressure-containment claim made conditional
- Row `Adaptors to land the pressure sensors on G1/4 BSP: tee branch thread t` (column: Note): item3: adaptor rating
- Row `Mean Well IRM-10-5 [CHOSEN]` (column: Note): item4: IRM internal fuse stated as not established
- Row `Mean Well IRM-10-5 [CHOSEN]` (column: Note): item4: removed T2A-internal vs no-internal contradiction
- Row `Fuse 1-2A slow-blow, 250VAC, one per dimmer module (AC-L in feed)` (whole row): item4: new row, fuses for the dimmer branches
- Row `Fuse holder for the dimmer branch fuse, 250VAC, with cover or shroud` (whole row): item4: new row, holders for the dimmer branch fuses
- Row `[RETAINED] Tank level sensor (reed/magnet), schematic S6 / WAT` (column: Note): item5: stale cross-reference
- Row `[RETAINED] Manual steam knob valve (2-way) with microswitch S8` (column: Note): item5: stale cross-reference
- Row `WeAct MiniSTM32H743 (STM32H743VIT6)` (column: Note): item5: ~80 GPIO -> 74 header GPIO
- Row `WeAct MiniSTM32H743 (STM32H743VIT6)` (column: Note): item5: ~42 -> 37 assigned
- Row `XDB401 3.3V I2C` (column: Dim_status): item5: Dim_status was "thread confirmed"
- Row `XDB401 3.3V I2C` (column: Note): item5: thread unconfirmed
- Row `[NEW] 2N5401 PNP transistor, TO-92` (column: Channel): item10: Channel "E1/E8" -> "E2/E4" (electrical-requirements Refs)
- Row `PT1000 spike probe, stainless, for the water at the block outlet (3mm ` (column: Channel): item10: Channel "E5 outlet water" -> "E6 outlet water" (electrical-requirements Refs)
- Row `Tee fitting for the water probe at the block outlet (before the 3-way ` (column: Channel): item10: Channel "E5 outlet water" -> "E6 outlet water" (electrical-requirements Refs)
- Row `[NEW] Compression gland adaptor for the water probe (3mm sheath into t` (column: Channel): item10: Channel "E5 outlet water" -> "E6 outlet water" (electrical-requirements Refs)
- Row `Silicone sleeving or high-temperature foam for the probe stub and fitt` (column: Channel): item10: Channel "E5 outlet water" -> "E6 outlet water" (electrical-requirements Refs)
- Row `PT1000 thin-film flat chip, Class A claimed, welded leads, rated 250C ` (column: Channel): item10: Channel "E5 commissioning" -> "E6 commissioning" (electrical-requirements Refs)
- Row `Resistor 4.7k LOW-TCR (25ppm/C or better) metal film, through-hole` (column: Channel): item10: Channel "E5 sensor dividers" -> "E5/E6 sensor dividers" (electrical-requirements Refs)
- Row `Perfboard (buffer + sensor dividers + connector landings)` (column: Channel): item10: Channel "E3/E5 passives" -> "E3/E5/E6 passives" (electrical-requirements Refs)
- Row `[RETAINED] Coffee thermoblock with its NTC (EM70025)` (column: Channel): item10: Channel "E1 coffee block" -> "E5 coffee block" (electrical-requirements Refs)
- Row `[RETAINED] Steam thermoblock with its thermistor (EM70020)` (column: Channel): item10: Channel "E2 steam block" -> "E5 steam block" (electrical-requirements Refs)
- Row `[RETAINED] Steam wand with its NTC disc (EM70024)` (column: Channel): item10: Channel "E3 wand" -> "E5 wand" (electrical-requirements Refs)
- Row `[RETAINED] Brass extension tube ('RELIEF ADAPTER BRASS' in the parts l` (column: Channel): item10: Channel "E1 coffee block" -> "water path" (electrical-requirements Refs)
- Row `[RETAINED] Tank level sensor (reed/magnet), schematic S6 / WAT` (column: Channel): item10: Channel "water path" -> "E1 water path" (electrical-requirements Refs)
- Row `[RETAINED] Flow meter on the suction line, about 5-7 cm ahead of the c` (column: Channel): item10: Channel "water path" -> "E8 water path" (electrical-requirements Refs)
- Row `[RETAINED] Manual steam knob valve (2-way) with microswitch S8` (column: Channel): item10: Channel "steam path" -> "E1 steam path" (electrical-requirements Refs)
- Row `Resistor 4.7k, 1/4W 1% metal film, through-hole` (column: Channel): item10: Channel "E7/BL0942" -> "E7/E19" (electrical-requirements Refs)
- Row `Resistor 100R, 1/4W 1% metal film, through-hole` (column: Channel): item10: Channel "E10/E11" -> "E4/E9/E11" (electrical-requirements Refs)
- Row `Resistor 1k, 1/4W 1% metal film, through-hole` (column: Channel): item10: Channel "E1/E8" -> "E2/E4/E8" (electrical-requirements Refs)
- Row `Resistors 2k, 100k and 47R, 1/4W 1% metal film, through-hole` (column: Channel): item10: Channel "E1/E8" -> "E1/E2/E18" (electrical-requirements Refs)
- Row `Capacitor 100nF, ceramic X7R 50V, 5.08mm lead pitch` (column: Channel): item10: Channel "E5/E3/all" -> "E5/E6/E3/all" (electrical-requirements Refs)
- Row `IC socket, DIP-20, machined or dual-wipe` (column: Channel): item10: Channel "E3/E10" -> "E3" (electrical-requirements Refs)
- Row `Resistor 1k, 1/4W 1% metal film, through-hole` (column: Qty): item11: qty 5 -> 12 to cover the stated maximum need of 12
- Row `Resistor 1k, 1/4W 1% metal film, through-hole` (column: Note): item11: note matches quantity
- Row `Resistor 100R, 1/4W 1% metal film, through-hole` (column: Qty): item11: qty 3 -> 4 to cover the stated maximum need of 4
- Row `Resistor 100R, 1/4W 1% metal film, through-hole` (column: Note): item11: note matches quantity
- Row `RC snubber + MOV module (100nF/220R + 10D471K)` (column: Note): item11: 7 mA / 36 V -> about 7.1 mA / 42 V
- Row `ULN2003A 7-channel driver breakout board (SSR drive)` (column: Note): item11: 24 mA stated as SSR control current

## part-numbers.csv

- Row `Heater SSR` (column: Watch out for): item1: stale FET drive text replaced by D2 ULN2003A drive
- Row `OPV, steam line [RETAINED]` (column: Watch out for): item2: conditional added
- Row `Fuse + holder (IRM feed) [RECOMMENDED]` (column: Watch out for): item4: "recommended, not required" made explicit
- Row `Fuse + holder (dimmer branch)` (whole row): item4: new row, dimmer branch fuse and holder
- Row `Controller board` (column: Watch out for): item5: 2x22 confirmed
- Row `Pressure transducer` (column: Confidence): item5: Confidence was "confirmed"
- Row `Pressure transducer` (column: Watch out for): item5: thread unconfirmed
- Row `General resistors` (column: Part number): item11: quantities match the BOM rows

## module-interconnect.csv

- Row `EARU SSR-40DA #1 / Load terminals (2x)` (whole row): item9: 6 fields merged to 4 (Notes = "Physical wiring; screw terminals; no soldering"); same defect as the OPV rows, on the SSR load-terminal rows
- Row `EARU SSR-40DA #2 / Load terminals (2x)` (whole row): item9: 6 fields merged to 4 (Notes = "Physical wiring; screw terminals; no soldering"); same defect as the OPV rows, on the SSR load-terminal rows
- Row `Mechanical OPV (steam line) - RETAINED` (whole row): item9: 6 fields merged to 4 (Wires To = plumbing part, line and position; Notes = the former sixth field)
- Row `Mechanical OPV (brew line) - NEW` (whole row): item9: 6 fields merged to 4 (Wires To = plumbing part, line and position; Notes = the former sixth field)
- Row `Mechanical OPV (steam line) - RETAINED` (column: Notes): item2: pressure-containment claim made conditional
- Row `Mechanical OPV (steam line) - RETAINED` (column: Notes): item9: removed "Specific part not yet chosen/priced" (contradicts retained)
- Row `XDB401 3.3V I2C #2 (steam) - LOCKED IN` (column: Notes): item2: OPV ceiling made conditional
- Row `XDB401 3.3V I2C #2 (steam) - LOCKED IN` (column: Notes): item2: gauge labelled; clipping acceptability made conditional
- Row `NTC divider resistors (one per NTC, on the perfboard)` (column: Notes): item5: removed old-controller board names
- Row `4ch opto-isolated MECHANICAL relay module (solenoids) / COM/NO/NC ch1 + RC snubber` (column: Notes): item11: snubber 7 mA / 36 V -> about 7.1 mA / 42 V
- Row `4ch opto-isolated MECHANICAL relay module (solenoids) / COM/NO/NC ch2 + RC snubber` (column: Notes): item11: snubber 7 mA / 36 V -> about 7.1 mA / 42 V
- Row `POWER ARCHITECTURE - CHOSEN` (column: Notes): item11: 29 mA vs 24 mA reconciled
- Row `ULN2003A 7-channel breakout (SSR drive) - control cavity` (column: Notes): item11: 24 mA stated as SSR control current, cross-referenced to 29 mA budget

## passive-and-drive-components.csv

- Row `Operator LED indicators (on the key lines and the water indicator)` (column: Notes / what to verify): item5: gate/buzzer transistor now a BOM row
- Row `Gauge drive via 74HCT541` (whole row): item8: new row
- Row `Heater SSR gate drive` (column: Notes / what to verify): item11: 24 mA vs 29 mA reconciled

## h743-pin-allocation.csv

- Row `Indicator anode-rail gate (blanking and brightness for every indicator` (column: Notes): item5: stale cross-reference
- Row `# PIN ASSIGNMENT for the WeAct MiniSTM32H743 (STM32H743VIT6, LQFP100).` (column: Channel): item7: header note lists all pins owing a 5V-tolerance check
- Row `Valve relay drive` (column: Notes): item7: 5V tolerance + relay polarity
- Row `Water indicator cathode (low-water, two elements sharing one cathode)` (column: Notes): item7: 5V tolerance
- Row `Operator key lines (bidirectional: sink indicator current, read as inp` (column: Notes): item7: 5V tolerance
- Row `Buzzer drive` (column: Notes): item7: PB4 restated (already noted in the constraint column)
- Row `Indicator anode-rail gate (blanking and brightness for every indicator` (column: Notes): item7: 5V tolerance
- Row `Flow meter` (column: Notes): item7: PA8 restated with the others
- Row `Gauge drive lines` (column: Notes): item8: step clocks may need timer outputs

## h743-header-pinout.csv

- Row `# WeAct MiniSTM32H743 header pinout, recovered from Hardware/STM32H7xx` (column: Designator): item6: 5-pin -> 4-pin SWD header, 88+4=92 mapping, inferred items marked
- Row `89` (column: Onboard peripheral / status): item6: status text added
- Row `90` (whole row): item6: new row for designator 90
- Row `91` (whole row): item6: new row for designator 91
- Row `92` (column: Onboard peripheral / status): item6: status text added

## Judgement calls and things not done

- Item 11, SSR drive current: the 29 mA in the 5V budget (module-interconnect.csv, power architecture row) is explained as the 24 mA SSR control current plus about 5 mA of unitemised allowance. The 5 mA breakdown is not in any source read; it is an unexplained remainder and is labelled as such. Either itemise it or change the budget to 24 mA.
- Item 9: the SSR load-terminal rows in module-interconnect.csv (EARU #1 and #2, Load terminals) also had 6 fields; they were merged to 4 the same way as the two OPV rows.
- Item 10: the review named the 2N5401 and the outlet PT1000, but the BOM codes for the thermoblock, steam thermoblock and wand NTC rows (E1/E2/E3) and others were also wrong against `control-board-electrical-requirements.csv`; all were changed (listed above). The brass extension tube is not an electrical channel and now reads `water path`.
- Item 6: designators 90 and 91 are INFERRED as SWDIO and SWCLK from the drawing's pin order (GND, CLK, DIO, 3.3V) and the parsed 89 (3V3) and 92 (GND). Designators 3, 7 and 10 remain unparsed and unverified.
- Item 8: the RST pull-down or pull-up value and direction are left as "to confirm" because the VID66-08 datasheet was not read for this pass. `control-board-electrical-requirements.csv` E3 says the datasheet asks for a pull-down; that was not adopted because the instruction was to leave direction unverified. The BOM resistor quantities do not include this part.
- Item 4: the dimmer-branch fuse rows are estimates (price, 5x20mm form factor, mounting style); nothing was looked up.
- Item 2: the gauge conversions (about 14.5 and 16 bar gauge, about 16 bar absolute burst) are arithmetic from the given absolute figures and a 1 bar atmosphere.
- Not changed, outside the six files: `control-board-electrical-requirements.csv` E12 still says `~7 mA ... ~36 V` for the snubber (should be about 7.1 mA and 42 V), and E10/E16 still carry the 24 mA versus 29 mA figures without the reconciliation; `mains-inlet-protection.md` and the other prose files were not touched.
- Not changed: the 3-way and 2-way solenoid valve rows still show `thread confirmed` for 1/8 BSP (not in the review list). The BOM adaptor row title still says `G1/4 BSP` although the sensor thread is now marked unconfirmed.
