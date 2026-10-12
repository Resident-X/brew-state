# Carry-forward log: heater drive, mains inlet, wiring

Old files (in `controller-selection-working/`) refreshed into `controller-design/` on 2026-10-12, in authority order against `decisions.md`, the current design CSVs, then `reference-machine.md` and `connector-pinouts.md`. Nothing outside `controller-design/` was changed; the graph was not touched.

## heater-drive-and-supply-timing.md

| Old section | Disposition |
|---|---|
| Header / "not baselined" notice | UPDATED: dated 2026-10-12, points at `decisions.md`; states nothing is in the graph |
| Position update 2026-10-05 (stacked note) | UPDATED: merged into the body ("Where the design stands", question, period source); the DimmerLink period-register text dropped (see below) |
| "It also records a change the graph has not yet been told about" | CARRIED UNCHANGED in substance, now in "What this owes the graph" |
| The question | UPDATED: DimmerLink wording replaced by the Standard dimmer; the Fotek reduced to a one-clause why-not; the zero-cross confirmation on EARU's datasheet kept as a contingency |
| Cancellation argument | CARRIED UNCHANGED (equations, 200 ms / 10.002 ms beat example). Period source updated to Z-C capture and BL0942; Z-C full-wave belief and the ~100 edges/s acceptance test added from part-numbers |
| Four claimed uses of a zero-cross channel (table) | UPDATED: supply-fault row now also names loss of Z-C/AC-N as a fault (module-interconnect); "Already served by DimmerLink" wording replaced |
| The drive scheme (GPIO, window, spreading, ripple, flicker) | CARRIED UNCHANGED (all numbers kept, including the unmeasured block-mass caveat) |
| BL0942 energy metering (why measure, where it pays, ZX not over UART, 570 µs, upstream placement, isolation test) | CARRIED UNCHANGED. UPDATED: D17 status added (Chosen; no BOM row; isolation to be measured), D20 mains-presence replacement marked Recommended / not decided, UART pins PC7/PA3 added, the "cheap module" ZX remark reduced to one line because the Z-C now supplies the reference |
| Consequence: separate zero-cross detector not needed | DROPPED as a section: the part-numbers row is already retired; one sentence in "Where the design stands" says no separate detector is bought |
| Snubbing, by channel | CARRIED UNCHANGED (all figures kept). UPDATED: "DimmerLink at the time" removed; X2 capacitor rating, BT136S-600E not-snubberless reading, "two fitted" valve snubbers, D6 normally-open vent, D4 open steam-pump scheme added |
| What this owes the graph | UPDATED: wording re-stated for the Standard dimmer (both-crossings reference present again for the pumps, per module-interconnect); the "Fotek changed once" sentence reduced to the contingency; DC-injection and flicker items kept; node IDs kept |
| Heater drive electrics (ULN2003A, SSR input, heatsink) | NEW (from D2, BOM, passive-and-drive-components, module-interconnect): the old note did not describe the drive |
| Open items list | NEW (collects unmeasured and unconfirmed items already stated in the inputs) |
| Fotek SSR-25DA, HLK, DimmerLink, separate zero-cross detector, F407/Robin Nano | DROPPED (superseded; Fotek retained as a one-clause why-not). F407 / Robin Nano were not mentioned in this file |

## mains-inlet-protection.md

| Old section | Disposition |
|---|---|
| Header / "snapshot of a decision in progress" | UPDATED: dated, D7/D8 stated as Chosen |
| The problem this addresses | UPDATED: thermal fuse now 240 °C steam block thermal fuse (parts list, rating published unverified, F12) instead of "unestablished rating"; MAX31865 removed (D10); pointer to the worst-case-draw open item added. 8-15 A band, `OBL-ELECTRICAL-THERMAL-SAFETY-001.C8`, `REQ-ELECTRICAL-INSTALL-001.C7`/`.C8` kept |
| Why not a better PSU | UPDATED: "the dimmer's BTA16" corrected to the BT136S-600E fitted on the RBdimmer (BOM) |
| The chain (diagram, table, order, lead length, filter fused by breaker, L-N only) | CARRIED UNCHANGED. Added: 24 mm disc, ENEC/UL listings, TMOV note, downstream 1-2 A and T2A branch fuses, trunk rating pointer |
| Variant traps | CARRIED UNCHANGED. Added from part-numbers: S/S1/HI suffixes, FN9260 fuses neutral too, `-T` undocumented, RN3400, buy-by-photo |
| Rejected: open-frame AliExpress 5 V module | CARRIED UNCHANGED; volume comparison re-based on the IRM-10-5 (same case, ≈25 cm³) |
| 5 V supply: open, changed from the BOM (HLK-10M05, IRM-05-5 recommendation) | UPDATED: now the chosen IRM-10-5 (D7). HLK-10M05 and IRM-05-5 reduced to one line. Load 0.53 A worst case, derating 1.5 A / 1.0 A, 35 % / 53 %, Level 3 1 kV, 65 kHz, 40 A inrush kept. DROPPED: the IRM-05-5 "~450 mA, 71 % efficiency, ~2 W in the brick, 29 → 25 cm³" arguments, TÜV/BSMI listing, and the "internal T2A/L 300 V fuse" claim (the BOM says the spec sheets read show none) |
| Carrier / fitting detail | NEW in this file (summarised from the BOM carrier, terminal, fuse and capacitor rows): pin spacings, 4-5 mm gap, T2A fuse, 47-100 µF + 100 nF, 5.08 mm 300 V terminals, coat not a substitute for creepage |
| Panel switch not fitted | CARRIED UNCHANGED. UPDATED: "eight pushbuttons and ~10 LED elements" replaced by the corrected panel inventory from `reference-machine.md` (ten tact switches in five pairs, eight indicators, three ground-switched inputs); `SOL-CHANNEL-ENUMERATION-CORRECTED.C4` kept with a to-confirm note |
| Sourcing split | CARRIED UNCHANGED (added: no Mean Well from AliExpress) |
| Open items | UPDATED: IRM-05-5 derating item (struck through in the old file) dropped as resolved and folded into the supply section; FN9222 letters, thermal-fuse rating, hard-switch, MOV consumable, thermal placement conflict kept; FN9222 termination, IRM internal fuse, enclosure ambient, worst-case-draw sizing added |
| Graph gap | CARRIED UNCHANGED, with a note that the graph search was not repeated in this refresh |

## wiring-and-connectors.csv

| Row group | Disposition |
|---|---|
| Header comment | UPDATED: 5 V load now ~0.53 A worst case estimated against the IRM-10-5's 2 A (was "~450 mA measured against 1 A"); pump/valve currents stated (were "mA-level"); heater figures 4.80 / 5.38 A (BOM) |
| Signal hookup wire (WH3009) | UPDATED: dimmer logic-wire rules (under 30 cm, twisted Z-C + GND, ferrite) and BL0942 not-connected-until-isolated added; high-temperature caveat flagged |
| 5 V DC distribution wire | UPDATED: figures per the BOM (see header) |
| DuPont crimp kit + tool | UPDATED note only: lists the module-side connections it serves |
| Mains flex (WB1562) | UPDATED: "mA-level" corrected to 0.1-0.22 A pump; branch fuse noted |
| Mains trunk (WB1565) | CARRIED UNCHANGED (1.0 mm², 10 A matches T10A). Sizing caveat added (see inconsistency 1) |
| Heater branch wire (FIT0584 16 AWG silicone) | CARRIED UNCHANGED (substitution warnings kept). Load figures and the heatsink-or-wall note added; requirement stands either way |
| Crimp tool TH1829 | CARRIED UNCHANGED |
| Crimp terminals PT4530 | UPDATED: the barrel-colour rule contradicted itself (the 1.0 mm² trunk would have gone in a blue 1.5-2.5 mm² barrel, loose). Trunk moved to red; heater 1.5 mm² stays blue |
| Heat shrink (general, mains-rated), Wago 221, DIN terminal blocks, twist+tape (not acceptable), closed-end connector | CARRIED UNCHANGED |
| Earth bonding | NEW: required by the inlet chain (earth unbroken to chassis stud); conductor and stud not named, marked to confirm |
| Landing connectors: OEM panel (9-way), gauge (9-way), flow meter CZ1, NTC plugs, PT1000 probes, XDB401 sensors | NEW: the BOM perfboard row requires a landing for every harness and no wiring row existed. Part and pitch left TBD / to confirm because no input records the OEM connector types |

No rows were dropped. The drain hose and PTFE drop-leg tube are plumbing and were not added.

## Inconsistencies found and not resolved (to confirm)

1. **Worst-case draw versus the 10 A chain.** `reference-machine.md`: both elements about 9.3 A at 230 V, worst case with both pumps 9.95 A at 240 V and 10.5 A at 253 V. The T10A fuse, the FN9222 (10 A at 50 °C) and the WB1565 trunk (10 A) all sit at that figure, and the "8-15 A uncovered band" starts below it. D8 is Chosen and `REQ-POWER-BUDGET-001` plans within the budget, so left as is; adequacy at the top of the supply range, and in-enclosure derating of the cable, are to confirm.
2. **IRM-10-5 internal fuse.** Old text said T2A internal; the BOM says the spec sheets read show none. Kept as unconfirmed; the external T2A is retained. Confirm in the user manual.
3. **OEM connector types and pitches** (panel, gauge, flow meter CZ1, NTC plugs) are recorded in neither `connector-pinouts.md` nor `reference-machine.md`. The new landing-connector rows have no part numbers. Panel pin-1 orientation and buzzer terminal order are also not established.
4. **XDB401 and PT1000 probe connectors** are not recorded; PVC-class hookup wire and PVC mains flex have no stated temperature rating near the thermoblocks and 140 C-class valves.
5. **Ferrules** for stranded conductors in the SSR, dimmer and PCB screw terminals are not required or specified by any input.
6. **FN9222 termination type** (tabs or screws) is not in the inputs, so the trunk terminal on the filter side cannot be matched.
7. **Earth bonding conductor and chassis stud** not named in the inputs.
8. **EARU SSR-40DA**: zero-cross type, package and dimensions unconfirmed (carried, load-bearing).
9. **`SOL-CHANNEL-ENUMERATION-CORRECTED.C4`** cited by the old inlet note for an enumeration that `reference-machine.md` has since corrected (eight pushbuttons recorded as ten switches in five pairs); the node was not read in this task (read-only `show` was not used), so whether its text still matches is to confirm.
10. **BL0942 ZX delay 570 µs**: typical or maximum not established. BL0942 module isolation and ZX availability unmeasured; D20 undecided.
11. **Graph gap on surge suppression**: the earlier search result was not repeated.

## Post-review fixes

Applied after a review of the three refreshed files. Earlier entries above that quote 4.80 / 5.38 A or "no internal fuse claim" are superseded by this section.

1. **Heater currents labelled by voltage.** The 4.80 A (coffee) and 5.38 A (steam) figures are the 253 V values. At 230 V they are 4.36 A and 4.89 A (230/52.7, 230/47.0; 253/52.7 = 4.80, 253/47.0 = 5.38, checked against `component-specification.md`). Corrected in `wiring-and-connectors.csv` (header and heater-branch row) and `heater-drive-and-supply-timing.md`.
2. **Enclosure ambient estimate restored** in `mains-inlet-protection.md`: the old note's "internal ambient near the boiler will be 45-60 °C", marked an estimate and unmeasured, as the basis for judging derating at 60 °C.
3. **OPEN DECISION: inlet chain rating margin** added to `mains-inlet-protection.md`, with matching flags on the trunk and valve-branch rows of `wiring-and-connectors.csv`. Covers the 10 A trunk equal to its T10A fuse, the FN9222 at 10 A at 50 °C, the machine's own 9.95 A at 240 V and 10.5 A at 253 V, and the 0.75 mm² flex described as 10A-class with no branch fuse (true rating unverified; one reviewer believes 7.5 A in AU). No parts changed.
4. **SSR mounting** reworded everywhere in these files to "proposed, not decided: try mounting direct to the metal side wall", with the thermal conflict (about 5-6.5 W per SSR against the IRM-10-5 derating from 100 % at 50 °C) and "no source says the wall is earthed". Note: `system-design.md` (outside this task) still says the SSRs are bonded to the earthed metal side wall and needs the same change.
5. **OPEN DECISION: heater switching cadence** added to `heater-drive-and-supply-timing.md` (whole-cycle here; half-cycle in the BOM, `controller-io.md`, `component-specification.md`). The "1 % duty resolution in whole half-cycles" inconsistency fixed: 1 % per half-cycle, 2 % per whole cycle over a 1 s, 50 Hz window.
6. **Snubber residual recomputed:** 100 nF at 50 Hz is 31.8 kΩ; with 220 Ω and the 5.9 kΩ coil |Z| is about 32.4 kΩ, current about 7.1 mA, coil voltage about 42 V (was about 36 V from about 7 mA). Conclusion kept (too little to hold a valve in; still inferred, bench to confirm).
7. **5 V budget restated:** 0.53 A is the typical-based budget. With the VID6608 maximum (200 mA, or a doubled 400 mA as the old E16 did) the worst case is about 0.66 to 0.86 A, up to about 86 % of the IRM-10-5's 1.0 A at 70 °C. The mapping of the 75 mA gauge-board figure to the VID6608 76 mA typical is inferred (the BOM current column has no gauge-board row). Derating figures kept.
8. **"143 mA valve coils"** corrected: it is the relay module coil current (2 x 71.4 mA), not valve solenoid current.
9. **T2A fuse** stated as recommended, not required. **IRM-10-5 internal fuse** stated as not established (the spec sheets read do not mention one); no claim of an internal T2A fuse is made. Note: `control-system-bom.csv` row for the IRM-10-5 still says "internal T2A fuse" and contradicts its own T2A row (outside this task).

Dropped or rewritten without a log entry in the first pass, recorded now:

- **Four-uses table, "Safety-relevant marking" row** of `heater-drive-and-supply-timing.md` was rewritten, and the old line "Removing the channel removes the hazard" was dropped, because the pump dimmer's Z-C brings a mains-referenced sensing channel back.
- **Four-uses table, supply-fault row** was changed (it now also names loss of Z-C or AC-N as a fault).
- **"Meter the output before connecting anything"** (from the rejected open-frame supply section of the old inlet note) was dropped as harmless: the rejected supply is not fitted.
