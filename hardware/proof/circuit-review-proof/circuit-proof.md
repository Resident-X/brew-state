# Circuit proof of the circuit review proof design

**NOT FOR MANUFACTURE.** The value-critical circuits of `circuit-review-proof`, a throwaway design made only to prove the schematic review of `docs/board-design-method.md`, each with its figure, where the figure comes from, how it is shown, the conditions it is shown under and the result. The constraints record is `constraints.md`. Every row is shown by a calculation written out below the table, from part values read in the schematic and datasheet limits read on 2026-10-18 from the addresses given.

## The circuits

| Circuit | What its values decide | Figure | Source of the figure | How shown | Conditions covered | Result | Met |
|---|---|---|---|---|---|---|---|
| 1. Heater drive stage, R5 U2 Q2 Q3 | The current in the phototriac's LED, set by R5 from `+5V` through U2's LED and the two series MOSFETs Q2 and Q3 | LED current at least 5 mA (the trigger current) and at most 60 mA | onsemi (Fairchild) MOC301XM, MOC302XM data sheet, Rev. 1.5, *Transfer Characteristics*, IFT maximum 5 mA for the MOC3023M, and *Absolute Maximum Ratings*, IF continuous 60 mA, at https://www.rlocman.ru/i/File/2018/05/22/MOC3023M-D.pdf (onsemi's own document, MOC3023M-D.pdf, served by a third party because onsemi's site refused the read) | Calculation, *Row 1* below | The `+5V` span 4.75 V to 5.25 V; R5's tolerance; U2's forward voltage at its datasheet maximum. Not covered: Q2 and Q3 on-resistance at the gate drive in use, see *Not bounded by a source* item 1 | Imax 16.1 mA; Imin 9.5 mA | yes on the datasheet's stated limits; item 1 is not bounded by a source |
| 2. Triac gate resistor, R2 U2 Q1 | That the phototriac's pulse through R2 stays within its derated surge rating and still turns Q1 on early in the half-cycle | Peak pulse current at most 0.7 A (U2's ITSM 1 A held to the integrated-circuit policy's share 0.7), at line peak and in the declared surge; and Q1 turned on within 18 degrees of the supply cycle after a zero crossing at 207 V | onsemi MOC301XM, MOC302XM data sheet Rev. 1.5, ITSM 1 A (PW = 100 µs, 120 pps) and VTM maximum 3.0 V; WeEn BTA16-600B data sheet Rev. 02 (30 May 2023), *Characteristics*, IGT maximum 70 mA and VGT maximum 1 V, at https://www.ween-semi.com/datasheet/BTA16-600B.pdf; the constraints record, heater trigger delay | Calculation, *Row 2* below | The mains peak 353.6 V; RV1's clamp of 710 V at 50 A for the declared surge; the lowest mains 207 V for the delay; R2's tolerance; IGT at its worst quadrant. Not covered: the clamp above U2's and Q1's repetitive off-state voltage, see *Not bounded by a source* item 10 | Ipk 0.325 A at line peak and 0.652 A in the surge; turn-on at 16.2 degrees | yes on the datasheets' stated limits; item 10 is not bounded by a source |
| 3. Mains tracks relying on F1 | Whether the narrowest mains track survives the fault until F1 clears it | k²S² at least the fuse's let-through I²t | Schurter SPT 5x20 data sheet, 0.5 A rating, pre-arcing time at 10 × In, at most 150 ms, at https://www.schurter.com/en/datasheet/typ_SPT_5x20.pdf; the constraints record (declared fault current, board material, solder, copper, track width) | Calculation, *Row 3* below | The declared fault current; copper at its minimum thickness; the board and solder temperatures | k²S² 4.46 A²s against 3.75 A²s | yes |
| 4. Wire link JP1 relying on F1 | Whether the isolating link in the mains line survives the same fault | k²S² at least the fuse's let-through I²t | As row 3 | Calculation, *Row 3* below | As row 3 | k²S² 14568 A²s against 3.75 A²s | yes |
| 5. Sense input filter, R13 C12 | How fast the reading at `/SENSE_ADC` settles after a step at J5 | Within 1/4096 of a step in at most 2 ms; and the current into the controller pin's protection diode, in the declared fault on J5, at most the data sheet's ±2 mA | The constraints record, sensor input settling, sensor source resistance, sense input range, resistor and capacitor tolerance; Texas Instruments MSPM0C1104 data sheet SLASF90E, *Absolute Maximum Ratings*, supported diode current ±2 mA | Calculation, *Row 5* below | Source resistance 100 ohm; R13 and C12 at the ends of their tolerance that settle slowest; the fault current with R13 at its lowest. Not covered: the converter's own sampling load, see item 2 | 1.064 ms; at most 1.10 mA into the pin's diodes | yes |
| 6. Status LED current, R7 D1 U4 | The current in D1, set by R7 from U4's output PA24 | LED current at least 0.2 mA and at most 6 mA | The constraints record, status LED current; Vishay VLMS1300, VLMO1300, VLMY130., VLMG1300 data sheet 82437 Rev. 1.6 (30-Mar-2023), VF maximum 2.4 V at 20 mA, at https://www.vishay.com/docs/82437/vlmo1300.pdf; Texas Instruments MSPM0C1104 data sheet SLASF90E (revised September 2026), *Digital IO Electrical Characteristics*, VOH minimum VDD − 0.45 V at 6 mA, https://www.ti.com/lit/ds/symlink/mspm0c1104.pdf | Calculation, *Row 6* below | The `+3V3` span from row 9; R7's tolerance; the output's high-level drop at its datasheet limit; the LED's forward voltage at its datasheet maximum. Not covered: item 3 | Imax 3.52 mA; Imin 0.267 mA | yes on the datasheets' stated limits; item 3 is not bounded by a source |
| 7. The regulator's capacitors, U3 C5 C7 C6 | Whether U3 is stable: its input and output capacitance | Output capacitance at least 1.0 µF with ESR 0 to 2.0 ohm; input capacitance at least 1 µF for a load up to 100 mA | Microchip MCP1700 data sheet DS20001826E (2018), § 5.2 *Output* and § 5.1 *Input*, https://ww1.microchip.com/downloads/en/DeviceDoc/MCP1700-Low-Quiescent-Current-LDO-20001826E.pdf | Calculation, *Row 7* below | Capacitance tolerance 20 % from the constraints record. Not covered: items 4 and 5 | C6 8 µF; input 38.4 µF | yes; items 4 and 5 are not bounded by a source |
| 8. The controller's supply capacitor, C8 U4 | Whether U4 gets the supply capacitance its datasheet requires | A capacitor between VDD and VSS of at least 10 µF, tolerance ±20 % or better | Texas Instruments MSPM0C1104 data sheet SLASF90E, *Recommended Operating Conditions*, CVDD 10 µF and its footnote 1 | Calculation, *Row 8* below | C8's nominal value; the 20 % tolerance of the constraints record; rated voltage. "Low-ESR" is not a figure, item 6 | 10 µF nominal, ±20 %; rated 10 V against 3.48 V | yes; item 6 is not a figure |
| 9. The 3.3 V rail against U3's and U4's ranges, U3 | Whether U3's output stays inside the supply range U4 is specified for, and U3 inside its own input range | U3's output between U4's 1.62 V and 3.6 V and at least 2.7 V; U3's input between 2.3 V and 6.0 V with at least VR + 3 % + 350 mV; the rail current within U3's 250 mA | The constraints record (5 V span, logic rail 0.1 A); the TI data sheet § 7.3 (VDD 1.62 V to 3.6 V) and § 7.10.1 (the output figures' condition VDD ≥ 2.7 V); the Microchip data sheet page 3 *DC Characteristics* (input 2.3 V to 6.0 V, 250 mA, dropout 350 mV maximum) | Calculation, *Row 9* below | The `+5V` span; U3's output accuracy ±3.0 %, line regulation ±1.0 %/V and load regulation ±1.5 % at their limits, added | VDD 3.120 V to 3.480 V | yes |
| 10. The controller's reset network, R8 C13 U4 | Whether U4's NRST has the pull-up and capacitor its maker's guide requires | A 47 kΩ pull-up to `+3V3` with a 10 nF capacitor to ground | Texas Instruments MSPM0 C-Series MCU Hardware Development Guide SLAAEG4C (revised March 2026), § 3.1 and Figure 3-1, https://www.ti.com/lit/pdf/slaaeg4: "The NRST reset pin is required to connect an external 47kΩ pullup resistor with a 10nF pulldown capacitor" | Comparison, *Row 10* below | R8 and C13 at their nominal values, the tolerances of the constraints record | R8 47 kΩ ±1 %, C13 10 nF ±20 % | yes |
| 11. The watchdog input's idle level, R14 U5 U4 | That U5's WDI is never left floating (a floating WDI disables its watchdog) while U4 is in reset or has not started | WDI held at a low level through R14 whenever U4's PA17 is not driving it; R14 times U5's low-level input current below 0.3 V | Texas Instruments TPS3820, TPS3823, TPS3824, TPS3825, TPS3828 data sheet SLVS165O (revised March 2025), *Terminal Functions* (WDI: "If left floating, the device generates pulses internally to prevent watchdog reset event") and *Electrical Characteristics* (IIL at WDI = 0.3 V, at most 190 µA); Texas Instruments MSPM0C1104 data sheet SLASF90E, *Digital IO Electrical Characteristics*, VOH minimum VDD − 0.45 V at 6 mA | Calculation, *Row 11* below | R14 at +1 %; U5's IIL at its maximum; PA17 driving high at 3.48 V | 0.19 V at U5's IIL; 3.5 mA from PA17 | yes |

## Row 1: the arithmetic

R5 (330 ohm), U2's LED and the two MOSFETs Q2 and Q3 are in series from `+5V` to ground: I = (Vs − VF − VDS) / R5.

- Vs 4.75 V to 5.25 V (constraints record). R5 = 330 ohm from the netlist; ±1 % gives 326.7 ohm to 333.3 ohm.
- VF is at most 1.50 V at 10 mA, MOC301XM, MOC302XM data sheet, *Emitter*, IF = 10 mA; its lower bound is 0 V.
- Maximum current: 5.25 V / 326.7 ohm = 16.1 mA, below the 60 mA continuous maximum. R5's power there is at most 16.1 mA² × 326.7 ohm = 0.084 W, below the resistor policy's 0.5 × 0.25 W = 0.125 W.
- Minimum current: the two FETs' on-resistance, at most 3.5 ohm each at VGS = 10 V and 0.22 A (Diodes Incorporated BSS138 data sheet DS30144 Rev. 25-2, *On Characteristics*, https://www.diodes.com/assets/Datasheets/BSS138.pdf), drop at most 2 × 3.5 ohm × 9.5 mA = 0.07 V: (4.75 − 1.50 − 0.07) V / 333.3 ohm = 9.5 mA, above 5 mA. The drop the two FETs can have while the current stays at 5 mA is (4.75 − 1.50) V − 5 mA × 333.3 ohm = 1.58 V, an on-resistance of 316 ohm for the pair.

## Row 2: the arithmetic

- The pulse the phototriac passes into the triac's gate at line peak is Vpk / R2 with R2 = 1.1 kΩ −1 % = 1089 ohm and Vpk = 250 V × √2 = 353.6 V: 0.325 A, below 0.7 A (ITSM 1 A at the policy's share 0.7).
- In the declared surge RV1 clamps at 710 V at 50 A (Vishay VDRS14T275BSE, 29081, clamping voltage at 50 A). If the surge reaches U2's output, the pulse into the gate is at most 710 V / 1089 ohm = 0.652 A, below 0.7 A.
- Q1 turns on when the voltage across the gate path exceeds IGT × R2 + VGT + VTM. IGT is at most 70 mA in the worst quadrant (T2− G+), R2 at most 1111 ohm, VGT at most 1 V, VTM at most 3.0 V: 0.070 A × 1111 ohm + 1 + 3.0 = 81.8 V. At the lowest mains, 207 V rms, the peak is 292.7 V and the angle is asin(81.8 / 292.7) = 16.2 degrees, below 18 degrees.

## Row 3: the arithmetic

The fault is the declared 5.0 A, which is 10 × In of the 0.5 A fuse. The Schurter data sheet gives the pre-arcing time at 10 × In as at most 150 ms (*Pre-Arcing Time*, 0.5 A to 0.8 A). The let-through energy to the end of pre-arcing is at most I² × t = 5.0² × 0.15 = 3.75 A²s.

The withstand is k² × S² with k = K × √(ln((θf + β) / (θi + β))), K = 226 A·s½/mm² and β = 234.5 °C for copper, the values IEC 60949 (1988) Table 1 gives and `docs/board-design-method.md` states.

- θi = 105 °C, the board material's maximum temperature in service of the constraints record. θf = 217 °C, the solder's lowest melting point of the constraints record, below the 288 °C for 20 s the laminate withstands (Shengyi S1141 data sheet, https://a-contract.ru/fileadmin/datasheets/base-material/S1141.pdf, *General Properties*, thermal stress 288 °C 20 s, no delamination), and held for longer than the fuse's 150 ms.
- k = 226 × √(ln(451.5 / 339.5)) = 226 × √0.2852 = 120.7 A·s½/mm².
- Track: S = 0.5 mm × 0.035 mm = 0.0175 mm², the narrowest mains track width times the least copper thickness of the constraints record. k² × S² = 14568 × 0.00030625 = 4.46 A²s, at least 3.75 A²s.
- Link JP1: a bare wire link of 1 mm² (the footprint library item `SolderWire-1sqmm`). k² × S² = 14568 × 1 = 14568 A²s, at least 3.75 A²s. The link is rated 300 V (the parts specification), above the 253 V rms across it open.

The width this row assumed, 0.5 mm, is the `Mains` net class track width in the project file.

## Row 5: the arithmetic

R13 = 4.7 kΩ + 1 % = 4.747 kΩ, plus the source resistance 100 ohm: 4.847 kΩ. C12 = 22 nF + 20 % = 26.4 nF. τ = 4.847 kΩ × 26.4 nF = 128.0 µs. To within 1/4096 of a step takes ln(4096) × τ = 8.318 × 128.0 µs = 1.064 ms, below 2 ms. The filter's corner, 1 / (2π × 4.653 kΩ × 17.6 nF) = 1.9 kHz at its lowest, is above the 10 Hz of interest.

In the declared fault, 5.25 V on J5 pin 1 with the board unpowered or powered, the current into the pin's protection diodes is at most 5.25 V / (4.653 kΩ + 100 ohm) = 1.10 mA, taking the diodes' drop and the rail as 0 V, below the ±2 mA supported diode current.

## Row 6: the arithmetic

- Maximum current: VDD 3.48 V over R7 − 1 % = 990 ohm with VF and the output drop at their lower bound of 0 V: 3.52 mA, below 6 mA, the load at which the output's high-level figure is stated.
- Minimum current: (3.12 V − 0.45 V − 2.4 V) / 1010 ohm = 0.267 mA, above 0.2 mA.

## Row 7: the arithmetic

- Output: C6 = 10 µF − 20 % = 8 µF, at least 1.0 µF.
- Input: C5 = 1 µF − 20 % = 0.8 µF and C7 = 47 µF − 20 % = 37.6 µF, both on `+5V`: 38.4 µF, at least 1 µF.

## Row 8: the arithmetic

C8 is 10 µF nominal, at least the 10 µF CVDD; its tolerance is 20 %, the ±20 % "or better" the footnote requires; its rating 10 V is above the 3.48 V of row 9.

## Row 9: the arithmetic

U3's output is 3.3 V × (1 ± (3.0 % + 0.95 % + 1.5 %)) = 3.120 V to 3.480 V, the line regulation 1.0 %/V times the highest distance 0.95 V from VR + 1 V = 4.3 V. This is inside 1.62 V to 3.6 V and above 2.7 V. U3's input 4.75 V to 5.25 V is inside 2.3 V to 6.0 V, and 4.75 V is at least 3.3 V × 1.03 + 0.35 V = 3.749 V. The rail current of 0.1 A is within 250 mA.

## Row 10: the arithmetic

R8 is 47 kΩ and C13 is 10 nF: the values the guide gives, with R8 between `+3V3` and NRST and C13 between NRST and ground. Both are on the net `/NRST` beside TP4 and J4 pin 4.

## Row 11: the arithmetic

- U5's WDI is `/WDI`, joined to U4's PA17 and to R14 to ground. While PA17 is an input (U4 in reset, or before its firmware has configured the pin) WDI is pulled to ground, a defined low level: the watchdog then times out and U5 asserts its reset, which holds the heater drive off through Q3, instead of the watchdog being disabled.
- U5's low-level input current at WDI = 0.3 V is at most 190 µA (SLVS165O): across R14 = 1.01 kΩ it raises the pin by at most 0.19 V, below the 0.3 V of that condition.
- With PA17 driving high at 3.48 V into R14 = 0.99 kΩ the current is 3.5 mA, below the 6 mA at which VOH is stated.

## Not bounded by a source

1. **Q2's and Q3's on-resistance at the gate drive in use.** The BSS138 data sheet bounds it at VGS = 10 V only. The gates are driven from the logic rail and from the watchdog output at 3.12 V or more. Row 1 tolerates 316 ohm for the pair, 45 times the 7 ohm that the 10 V figure gives.
2. **The converter's sampling load on `/SENSE_ADC`.** No figure is read from the controller's converter section for the charge its sampling draws through R13.
3. **The LED's forward voltage at 0.2 mA to 6 mA and over 0 °C to 50 °C.** The Vishay data sheet states it at 20 mA and 25 °C only. The minimum current tolerates a forward voltage up to 2.67 V.
4. **U3's output capacitor ESR.** The Microchip data sheet bounds it from 0 to 2.0 ohm; no ceramic capacitor data sheet is read that bounds an ESR, so C6's ESR has no sourced upper figure.
5. **Capacitance change with DC bias** on C5, C6 and C7.
6. **"Low-ESR" for C8.** The TI data sheet gives no figure for it.
7. **The fuse's arcing time.** The Schurter data sheet gives the pre-arcing time at 10 × In and no arcing time or maximum I²t; row 3 bounds the energy to the end of pre-arcing only.
8. **The board material's maximum temperature in service.** The 105 °C is this record's own synthetic figure; no laminate data sheet read states one.
9. **The heater's latching current.** BTA16-600B's latching current is at most 90 mA; with the heater at 833 ohm (250 V at 0.3 A) the triac latches at 75.0 V, 14.8 degrees at 207 V. The heater's resistance is not bounded from above by the constraints record.
10. **The surge clamp above the repetitive off-state voltage of U2 and Q1.** RV1 clamps at 710 V at 50 A (the declared surge), above U2's 400 V and Q1's 600 V repetitive peak off-state voltage; the data sheets state no non-repetitive off-state voltage that covers 710 V. Row 2 bounds the current into the gate path (0.652 A) and no more.

## Circuits considered and not listed

- **No zero-crossing detector**: the schematic carries none; the heater is driven by a random-phase phototriac.
- **R1 C4 snubber**: no data sheet read states a requirement for its values.
- **I2C pull-ups R11 R12, series R9 R10 and the clamp D2**: no figure for the bus's speed or capacitance is declared in the constraints record.
- **R6 and R3 pull-downs**: they set a default state and no figure depends on the value. R8, C13 and R14 are rows 10 and 11.
- **The watchdog U5**: no external timing component is fitted.
- **RV1, C1 to C3 across the mains**: they are parts of the mains port and no figure in the constraints record bounds them.

## Failure modes of the heater cut-off chain

The chain from the decision to the switching device is U4 PA2, R6, Q2, U5's reset output with R3, Q3, R5, U2, R2 and Q1 (nets `/HEAT_CMD`, `/WD_RESET`, `/SW_MID`, `/LED_K`, `/LED_A`, `/MAINS_OPTO_T2`, `/MAINS_TRIAC_G`). The protected output is the heater current at J2. The off-board protective chain of the constraints record (the heater assembly's own series thermostat and thermal fuse) acts on the heater's temperature with no part of this board involved. An outcome of "bounded" below means the heater can stay energised and only that chain ends it; "safe" means the heater is not energised; "detected" names the diagnostic. No row relies on the controller or its firmware noticing.

| Part | Mode | Effect on the heater | Outcome |
|---|---|---|---|
| U4 PA2 | stuck high | Q2 on; heater driven only if U5 also releases Q3 | safe while U5 holds `/WD_RESET` low; if U5 is also released, bounded |
| U4 PA2 | stuck low, or Hi-Z | R6 holds Q2 off | safe |
| R6 | open | Q2's gate floats when PA2 is Hi-Z; Q2 may conduct | bounded by U5 holding Q3 off while it asserts reset; U5 deasserts when healthy, so bounded |
| R6 | short | Q2's gate held low | safe |
| Q2 | open | LED path open | safe |
| Q2 | short | Q3 alone gates the heater: U5 still removes it when it asserts reset | safe while U5 asserts reset; with U5 healthy, bounded |
| U5 | RESET stuck high | Q3 stays on | bounded |
| U5 | RESET stuck low | Q3 off | safe |
| U5 | WDI floating | the watchdog is disabled by the part | detected by R14 holding WDI low: the watchdog times out and asserts reset; safe |
| R3 | open | Q3's gate floats when U5 is unpowered or Hi-Z; its reset output is push-pull | bounded while U5 is powered and its output is high; safe when U5 is unpowered, as it is then the only drive of Q3 |
| R3 | short | Q3's gate held low | safe |
| Q3 | open | LED path open | safe |
| Q3 | short | U5 no longer gates the heater; Q2 alone | bounded |
| R5 | open | no LED current | safe |
| R5 | short | LED current above 60 mA maximum, U2's LED fails open | safe on failure; the current is limited by Q2 and Q3 until it does |
| U2 | LED open | no trigger | safe |
| U2 | output short | Q1's gate fed continuously through R2 | bounded |
| R2 | open | no gate current | safe |
| R2 | short | the gate pulse rises to U2's ITSM, 1 A, at line peak | U2's output fails; its failure is open or short as the two rows above |
| Q1 | open | no current | safe |
| Q1 | short | heater energised; F1 (500 mA) does not open at 0.3 A | bounded |

A fault that leaves the chain looking healthy while it no longer protects is a short of Q1, Q3 or U2's output, or Q2 short with U5 healthy; each is bounded by the off-board protective chain, none is detected on the board, and the board has no test imposed before power reaches the load. The record states this and does not claim more.
