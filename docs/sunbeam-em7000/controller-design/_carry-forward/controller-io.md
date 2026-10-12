# Carry-forward log: controller-io.md, controller-io-bom.csv, control-board-electrical-requirements.csv

Old files: `docs/sunbeam-em7000/controller-io.md`, `controller-io-bom.csv`, `control-board-electrical-requirements.csv` (unchanged on disk). New files: the same names in `controller-design/`. Authority order used: `decisions.md` (2026-10-12), then the current design CSVs, then `reference-machine.md` / `connector-pinouts.md` (read only), then the old text. Note: the old files contained no F407, 4-ADC or 30-pin claims (searched); the only stale claim of the listed kinds was the Hongfa relay part numbers, which are removed (the OEM relays are now described only as mechanical relays, as found). The two old CSVs had a plain header row and no comment rows, so none were carried. "Not re-read" means the node or file was not available in the inputs and the old claim is kept as written.

## controller-io.md

| Section / row group | Disposition | What and why |
| --- | --- | --- |
| Title and opening paragraphs (local file, one question, provenance rule) | CARRIED UNCHANGED | Wording kept; one "Refreshed 2026-10-12" paragraph added (see NEW) |
| Scope paragraph (what was out of scope: part choice, pin assignment) | UPDATED | The design has since chosen parts and pins, so the scope sentence now says they are recorded but not reopened; cost and plumbing stay out of scope, with the pressure-path parts now tabulated (D15). `SOL-CONTROLLER-CHANNEL-ENUMERATION`, `SOL-CHANNEL-MEASUREMENT-FIGURES`, `DEC-PLUMBING-LEFT-AS-BUILT` kept |
| Paragraph on `SOL-CHANNEL-ENUMERATION-CORRECTED` (element types, coil class, gauge interface; zero-cross, keys, LEDs found) | CARRIED UNCHANGED | Still true history; `DEC-U8-BOARD-RETENTION-UNVERIFIED` kept |
| Paragraph on five rows brought current (`SOL-CONTROLLER-AND-MAINS-PARTS-DOWN-SELECT`, `DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM`) | UPDATED | Kept, with the half-cycle / 60 Hz reasoning verbatim, plus a statement that the reference now comes from the dimmer Z-C and the heaters are zero-cross SSRs, and that the DEC has not been amended (revision owed, per `h743-pin-allocation.csv`) |
| NEW: "Refreshed 2026-10-12" paragraph | NEW | States the design basis (D1-D20) and the status vocabulary of `decisions.md` |
| What the control needs of each channel: sources list, `@estimated` marking rules, cost ordering | CARRIED UNCHANGED | Verbatim; firmware file and constant names not re-verified |
| NEW: note that sensing-error declarations predate the outlet probe | NEW | D9 makes a PT1000 the key sensor; whether the declarations are re-valued is unresolved (to confirm) |
| "No row claims a multiple of the step interval" paragraph | CARRIED UNCHANGED | |
| "Five channels are not provisioned that way" | UPDATED | Now seven groups: adds the two BL0942 meters (about 48 ms UART packet, `module-interconnect.csv`); the mains-presence confirms are kept in the list while D20 is undecided |
| What the retrofit keeps (three layers, `DEC-DEVICE-RETENTION-BOUNDARY`, `OBL-PHYSICAL-CONFIGURATION-001.C1/.C3`) | UPDATED | Layer text kept. Conditioning-network sentence now records the chosen dividers, pull-ups and pull-downs. The "button pull-ups" correction paragraph rewritten to the sheet 3-3 reading (1 kΩ in series with the switch, 47 Ω at the pin, no pull-up drawn; disagrees with the earlier text; meter check to confirm) per F14. Carrier-board sentence now names the H743-on-perfboard design. Harness reuse added (D18) |
| NEW: Realised by (design summary) table and pin budget | NEW | Channel-to-pin map and verification state from `h743-pin-allocation.csv` and `h743-header-pinout.csv`; header geometry corrections (2x22 per edge, not 2x40) |
| Sensing: coffee thermoblock NTC | UPDATED | Retention "Open" resolved to Retained as casing sensor (D10). Divider now 4.7 kΩ low-TCR ratiometric (was 10 kΩ 1%); the "peak near 85-90 °C" kept as OEM-divider fact and marked not re-derived. Accuracy, resolution, update-rate figures carried with a note that they predate D9 |
| Sensing: steam thermoblock NTC, steam wand NTC | UPDATED | Same as above (D10) |
| NEW: outlet water PT1000 | NEW | D9; rating, tee fitting, divider, PA4 (ADC channel not verified). Accuracy and resolution cells say not established rather than invent a figure |
| NEW: commissioning PT1000 chips | NEW | D11; PA1 (ADC channel not verified) |
| Sensing: water level (S6/WAT) | UPDATED | Pin PE9, ground-switched with 1 kΩ and 47 Ω per sheet 3-3; figures carried |
| Sensing: flow meter | UPDATED | Signal text carried; added PA8 TIM1_CH1, the unresolved 5 V-tolerance / MCO1 caveat and the pull-up/RC reservation. `DEC-FLOW-SENSED-UPSTREAM-OF-PUMP` kept |
| Sensing: knob microswitches S7/S8 | UPDATED | Pins PE15 / PC6; S8 as steam-mode switch and candidate interlock |
| Sensing: panel keys | UPDATED | Pull-up claim corrected (F14); pins PE4-PE8; ten-switch / five-signal explanation carried |
| Sensing: mains zero-cross | UPDATED | Source is now the dimmer module Z-C on PA10 (D3); the OEM `PC817` half-wave front end kept only as machine-as-found and marked replaced. "Both crossings" claim replaced by one edge per half-cycle (believed full-wave, to scope). Safety marking kept |
| Sensing: coffee / steam mains-presence confirm | UPDATED | Marked under review (D20, Recommended not decided); old "Retained" retention changed to Replaced because the OEM sense arrangement sits on the replaced board; pin unassigned |
| NEW: BL0942 energy meters (two rows) | NEW | D17; PC7 / PA3; isolation blocked; safety marking left undecided |
| Sensing: steam-path pressure transducer | UPDATED | Was "not established, not fitted, part not selected, analogue"; now XDB401 0.5 MPa I2C on I2C2 (D12, D14), still not fitted. The ±0.2 bar / 0.4 bar derivations carried; datasheet ±0.05 bar added for comparison. `DEC-STEAM-PRESSURE-SENSOR-ADDED`, `REQ-MEASUREMENT-001.C8` kept |
| NEW: brew-path pressure transducer | NEW | D12, D13; I2C1; graph link to `REQ-MEASUREMENT-001.C7` not re-read (to confirm) |
| Prose after sensing table: nothing measures the brew path downstream | CARRIED UNCHANGED | With a sentence that the additions do not close it |
| Prose: flow meter signal settled, drive style open | CARRIED UNCHANGED | `CZ1` pin detail and PA8 tolerance condition added |
| Actuation: coffee / steam heater switching | UPDATED | Signal and class rewritten for the EARU SSR-40DA via ULN2003A (D2); accuracy / resolution / rate cells carried; Hongfa part number removed; relay kept as capability floor. Whole-cycle burst versus the DEC's per-half-cycle wording flagged. Zero-cross type of the EARU part to confirm |
| Actuation: coffee / steam pump | UPDATED | RBdimmer Standard (D3), PA9 / PD8, branch fuse, pull-downs; D4 open for steam pump; D16 no steam damper. Granularity reasoning carried |
| Actuation: two-way valve | UPDATED | Normally open vent (D6), mechanical relay module and snubber (D5), PD7; Hongfa relay part number removed; safety marking changed to "to confirm" with the reason |
| Actuation: three-way valve | UPDATED | Never closed (F1), relay channel 2, PD10 |
| Actuation: espresso and milk gauges | UPDATED | Driver description carried; 74HCT541 level-up (D19) now clears the 3.15 V threshold; open items added: roles of PD0/1/4/5/6 not recorded, timer step clocks not met by "plain GPIO", allocation analysis flagged RE-CHECK |
| NEW: gauge driver reset | NEW | Was only in the old CSV (O9), not in the .md; pull-down not on the passive list (to confirm) |
| Actuation: panel LED indicators | UPDATED | Series resistors 330 / 300 Ω; sink current now estimated at about 8 mA (was 10-15 mA in the CSV, "not established" in the md); pin-sink check |
| NEW: indicator anode-rail gate | NEW | Was only in the old CSV (O12); `Q7` copy on PB5, D18 Recommended |
| Actuation: panel buzzer | UPDATED | `Q8` copy on PB4 (D18), `NJTRST` caveat, magnetic-versus-piezo still open |
| Actuation: low-water indicator | UPDATED | PA0, open-drain, two elements on one cathode |
| "On the schematic tags" paragraph | UPDATED | Tag pairing still not guessed; owner-statement roles and relay channel numbers added |
| Protective devices: three thermostats | CARRIED UNCHANGED | Pump thermostat gains a to-confirm note on the "thermal protector" in `module-interconnect.csv` |
| Protective devices: thermal fuse | UPDATED | 240 °C from the parts list (F12, published unverified) alongside the as-found "rating not established" |
| Protective devices: coffee-side `RELIEF ADAPTER BRASS` | UPDATED | Owner statement F4: extension tube, not a relief; as-found text kept; "Yes" safety marking withdrawn conditionally |
| Protective devices: espresso pump relief | UPDATED | Manual's marketing claim kept against owner statement F8 (no OPV); conflict marked to confirm |
| Protective devices: steam-side relief ("None documented", count 0) | UPDATED | Superseded by owner statement F6 / F7 and D15: a retained steam OPV on the pump, conditionally capping the block.. `module-interconnect.csv` now reads RETAINED, so no stale row remains |
| NEW rows: brew OPV, brew damper, no steam damper, internal check valves, mains inlet chain | NEW | D15, D16, F9, D8; deferred interlock noted from the BOM and `DEC-HEATER-DRIVE-GATED-BY-SUPERVISION` |
| "Every row above is retained" paragraph and thermostat resettable-or-one-shot paragraph | CARRIED UNCHANGED | Scoped to the thermostats and fuse, since the table now also holds Added rows |
| Compute: control law and estimator, 100 Hz tick (`DEL-SIM-ESTIMATOR`) | CARRIED UNCHANGED | Chosen controller stated (D1, part facts from `part-numbers.csv`); on-target execution time still out of scope |
| Compute: operator interface options | UPDATED | Options and the dead "third future" kept; pin costs now named (seven for the panel, six for the gauge assembly, thirteen total); three ground-switched inputs additional; board TFT unused |
| Channels not enumerated: brew-path pressure | DROPPED as an absence | Now a row; the false "no decision has added one" is removed. The as-found "not fitted" fact is kept in a replacement row with `SOL-BREW-PRESSURE-RATIONALE-CORRECTED` and `DEC-PROFILE-COMMANDS-FLOW` |
| Channels not enumerated: current sensing | UPDATED | As-found "not fitted" kept; the replacement adds heater current via BL0942 (D17) |
| Channels not enumerated: real-time clock | CARRIED UNCHANGED | Reworded to say none of the design inputs adds one |
| What depends on this enumeration | UPDATED | All rows kept; brew-pressure entry dropped; two rows added (derived CSV views; heater, pump and zero-cross rows reaching `DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM`). `component-specification.md` references kept and flagged as owed a re-read |

## controller-io-bom.csv

| Row group | Disposition | What and why |
| --- | --- | --- |
| T-A1 to T-A3 (NTC baseline) | UPDATED | Option text changed to "NTC casing sensors (kept)" (D10); 4.7 kΩ low-TCR divider and 16-bit ADC; pin choice PC0/PC1/PC4 with mapping unrecorded |
| T-B0 to T-B4 (MAX31865 SPI, chip selects, DRDY) | DROPPED | D10: no MAX31865; the PT1000 channels are on ADC dividers |
| NEW T-C1 outlet PT1000, T-C2 commissioning chips | NEW | D9, D11 |
| P1 steam pressure | UPDATED | Was analogue ADC, "Decided not fitted", part not selected; now I2C2 XDB401, Chosen, not yet fitted |
| P2 brew pressure | UPDATED | Was analogue, Proposed; now I2C1 XDB401, Chosen (D12, D13) |
| D1 keys, D2 knobs, D3 tank level, D4 flow meter | UPDATED | Pins and resources added; D1 pull-up wording corrected (F14); D4 level-handling caveat added; ten-switch explanation carried |
| D5 zero-cross | UPDATED | Status "Fitted (half-wave - MUST REPLACE)" becomes Replaced by the dimmer Z-C on PA10; half-wave OEM detail kept as superseded |
| D6, D7 mains-presence confirms | UPDATED | Marked under review (D20); `REQ-ACTUATION-CONFIRMATION-001.C2` text kept |
| NEW D8, D9 BL0942 meters | NEW | D17 |
| O1, O2 heaters | UPDATED | EARU SSR-40DA via ULN2003A (D2); measured element figures kept; "prefer a zero-crossing optotriac or a 25 A SSR" recommendation dropped as superseded |
| O3, O4 pumps | UPDATED | Dimmer module (D3); OEM `Z0409NF` stage named as replaced |
| O5, O6 valves | UPDATED | Relay module (D5), normally-open 2-way (D6); "Relay coil needs a 12 V rail" dropped (5 V coils); Hongfa part numbers removed |
| O7, O8, O9 gauges and reset | UPDATED | Old notes carried; 74HCT541 (D19) and the open items added |
| O10, O12, O11, O13 indicators, rail gate, buzzer, low-water | UPDATED | Old notes carried; pins, `Q7` / `Q8` copies (D18) and sink-current estimate added |
| U1 display link | CARRIED UNCHANGED | Note that the board's TFT is unused |
| NEW O14 spare relay channels | NEW | PD14 / PD15 |

## control-board-electrical-requirements.csv

| Row | Disposition | What and why |
| --- | --- | --- |
| E1 ground-switched inputs | UPDATED | Pull-up claim corrected per F14; pins added |
| E2 indicator outputs | UPDATED | Current estimate, `Q7` stage, open-drain 5 V tolerance; the OBSERVED-not-traced rail-sharing caveat carried |
| E3 stepper channels | UPDATED | Long driver analysis carried; 74HCT541 added; open items added |
| E4 annunciator | UPDATED | `Q8` stage and pin |
| E5 temperature front end, Option A | UPDATED | Now the retained NTC casing sensors; no longer mutually exclusive with E6 |
| E6 temperature front end, Option B (MAX31865) | UPDATED | Replaced by the PT1000 ADC channels; the MAX31865 content is DROPPED (D10) |
| E7 pressure inputs | UPDATED | Analogue 0.5-4.5 V / 5 V excitation requirement dropped for two I2C XDB401 units |
| E8 flow meter | UPDATED | PA8 tolerance condition and reserved parts |
| E9 zero-cross | UPDATED | "Requires a NEW front end" replaced by the dimmer Z-C (D3); status now Replaced |
| E10 heaters | UPDATED | MOC3063-class optotriac / external-SSR suggestion replaced by the chosen SSR and ULN2003A; elements and 5 A fuse facts carried; OEM `Z0409NF` pump-class remark dropped |
| E11 pumps | UPDATED | Dimmer module; "snubber required" replaced by the BOM's "do not add pre-emptively, never fit the valve modules to the triacs" |
| E12 valves | UPDATED | Mechanical relay module, normally-open vent, snubbers; 12 V coil rail requirement dropped |
| E13 heater mains-presence sense | UPDATED | Under review (D20) |
| NEW E19 heater energy metering | NEW | D17 |
| E14 display link | CARRIED UNCHANGED | |
| E18 low-water indicator | UPDATED | Pin and open-drain requirement |
| E15 inter-board links | UPDATED | Panel-breakout bus idea dropped for the perfboard design; mains-boundary crossings listed; D21 recommended not decided |
| E16 logic power supply | UPDATED | Mean Well IRM-10-5 and its 5 V budget replace the old at-least-10 W budget; the old per-load watt figures and the "12 V if relay coils retained" line are dropped |
| NEW E20 mains inlet protection | NEW | D8 |
| E17 analogue integrity | UPDATED | References E5 / E6 only; ratiometric reference added |

## Items that could not be resolved from the inputs

- Which NTC is on PC0, PC1 or PC4.
- Whether the firmware sensing-error declarations are re-valued for the outlet PT1000.
- Whether the EARU SSR is zero-cross (its own datasheet), and its isolation rating.
- Whether whole-cycle SSR burst is consistent with `DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM`'s per-half-cycle decision (revision owed).
- Whether the five gauge pins can supply two timer step clocks; no reset pull-down appears on the passive list.
- Whether the PC6 optional BL0942 TX collides with S8 on PC6.
- Whether the graph links the brew pressure channel to `REQ-MEASUREMENT-001.C7`.
- Mains-presence confirm replacement (D20), and whether the BL0942 meters are safety-relevant.
- Whether the 2-way vent should carry the safety marking.
- Brew pump relief device (manual claim versus owner statement), and the steam OPV capping question (F7).

## Post-review fixes

Applied after a review of the refreshed files; earlier entries above are superseded where they disagree.

1. **Valve relay rationale restored.** The "contacts fail open" reason is gone from the two-way valve row, BOM O5 and E12. The original reasoning is back: espresso solenoid coils draw 17-61 mA against a BTA16's maximum holding current of 60 mA, so a triac cannot reliably latch, and the OEM's triac-for-pumps, relay-for-valves split was the same physics (old `controller-selection-working/README.md`). "Contacts can weld" is kept; the vent being fail-safe (normally open, D6) is stated as a separate point.
2. **5 V budget.** E16 labels 0.53 A as the typical-based budget and adds the worst case with the VID6608 datasheet maximum (76 mA typical, 200 mA maximum, both doubled as the old E16 did): about 0.66 to 0.86 A. "143 mA valve coils" corrected to relay-module coil current (2 x 71.4 mA). The mapping of the ~75 mA gauge-board term to the typical figure is not recorded in the BOM mA column.
3. **Steam pressure row.** Restored the basis for the 0.2 bar figure (target is the middle of the band; an absolute error above half the span puts the held state outside it), the `ready-pressure-bar` 100 milli-bar caveat, and the caveat that no bench has established what pressure a steamed jug is spoiled at. The steam OPV is now called the pressure guarantee only conditionally: it caps the block only if no check valve lies between it and the block (F7, to be inspected), otherwise the 200 C thermostat bounds it at about 15.5 bar absolute. The "+/-0.2 bar / 0.4 bar derivations carried" log claim is now accurate.
4. **Stale statements removed:** the claim that `module-interconnect.csv` still carries a row calling the steam OPV NEW (it now reads RETAINED), here and in the open-items list; "component-specification.md was not re-read in this refresh"; "gate transistor is not yet a BOM row" (it is one) in the I/O file and BOM O12.
5. **Links** to `reference-machine.md` and `connector-pinouts.md` now point to the parent folder. "In this slice" wording removed.
6. **OPEN DECISION: heater switching cadence (whole-cycle versus half-cycle)** marked on both heater rows (Signal, Peripheral class and Resolution cells) and BOM O1/O2; not chosen.
7. **OPEN DECISION: steam heater with the knob shut** added where `ready-temperature-c` is described, with F10 and the open trapped-pressure case; not chosen.
8. **Small facts restored** in the BOM: O1 "the 1000 W circuit-diagram label is superseded by that measurement"; O2 "do not inherit the coffee channel's 4.4 A".
9. **D18 wording:** the two open-drain 2N5401 stages now read "to be verified 5V-tolerant (PB4, PB5; see open-items.md section B)".
