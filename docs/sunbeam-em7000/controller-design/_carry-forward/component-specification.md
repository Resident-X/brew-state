# Carry-forward: component-specification.md

Old file: `docs/sunbeam-em7000/component-specification.md`. New file: `controller-design/component-specification.md`. Status per section or table of the old file.

| Old section or table | Status | What and why |
|---|---|---|
| Title and opening paragraph | UPDATED | Question widened from "does a candidate serve" to "which part is selected, does it meet the property, what is open". Added the provenance tag legend and the list of input files |
| "Written by hand ... C6 later" paragraph | CARRIED UNCHANGED | `DEL-COMPONENT-SPECIFICATION.C6` still a later criterion (stated as such); added that `decisions.md` says none of its decisions is in the graph yet |
| Rule 1 "Parts specified by property, not by part number" | UPDATED | Reframed: property stated independently, selected part then held against it. Same intent (usable for a donor part) |
| Rule 2 "Every figure traces to a declaration" | CARRIED UNCHANGED | |
| Rule 3 "Nothing here selects the controller" | UPDATED | Controller now chosen (D1). Kept the reference to `DEC-PREHARDWARE-TARGET-FAMILY` and `DEC-HEATER-DRIVE-GATED-BY-SUPERVISION`; whether the former was revisited for the H743 marked to confirm. One-line note on why the F407 and the Hongfa relays were not used |
| What the supply is, and what changes off it | CARRIED UNCHANGED | Both bullets and the `REQ-MACHINE-CONFIGURATION-001.C8` paragraph kept. Added one sentence that the dimmer acceptance test (about 100 edges/s) depends on the inferred 50 Hz |
| Load table: intro (assumed resistance coefficient) | CARRIED UNCHANGED | |
| Load table, "Commanded / Carries / Must dissipate / Must fail into" columns | UPDATED | Currents and half-cycle reasoning unchanged. Dissipation: kept the 1.2-1.4 V estimate and added the BOM's 5-6 W estimate for the selected SSR. 2-way valve fail state changed from a hypothesis to decided: normally open, vents when de-energised (D6, F2). 3-way: added F1 (never closed; de-energised is the brew path). Added the BOM's replacement valve coil ratings (5-9 W, 8-9 W) and pump-current 0.1-0.22 A |
| Load table, "OEM device — the floor to clear" column | UPDATED | Moved into a note and to the as-found record in `reference-machine.md`. Hongfa part numbers and signal tags no longer appear as candidates; replaced by a short as-found description |
| Isolation shared across rows | UPDATED | Per-device barriers rewritten for the selected parts (SSR, dimmer module, relay module). Added BL0942 isolation gate and IRM-10-5 rating. Creepage paragraph kept with BOM figures added; AS/NZS 3000 note kept |
| The regression this specification makes visible | UPDATED | Triac replaced by SSR as the device of concern (the "semiconductor fails short" step marked inferred). Interlock status updated from the BOM and interconnect (deferred items named). Old claim "no covering work in the graph" kept as to confirm. Thermostat paragraph kept, with the parts-list trip temperatures added. `REQ-SAFETY-CHAIN-001.C2` and `.C3` kept |
| What the supply-timing front end needs (table) | UPDATED | Requirement column carried; OEM column kept as as-found; new "Selected design" column: Z-C of dimmer module #1 on PA10. Both-crossings met only if the module is full-wave (believed, unmeasured). Added the interconnect note that the graph revision is owed. The closing paragraph (rectify both half-cycles / integrated detector) DROPPED: the part question is answered by the dimmer module |
| Does a candidate controller serve every channel at once: intro | UPDATED | Retargeted to the selected controller; `REQ-HARDWARE-HEADROOM-001.C2` and `DEL-COMPONENT-SPECIFICATION.C4` kept |
| What the enumeration demands (table) | UPDATED | Replaced by a per-channel table from `h743-pin-allocation.csv`: 37 assigned pins (the old 30 pin total no longer applies). Struck-column paragraph (two-wire link, `DEC-U8-BOARD-RETENTION-UNVERIFIED`) shortened to one sentence |
| What the candidate provides (STM32F407 table) | DROPPED | F407 not used; its ST datasheet figures (`DS8626`), the VET6 variant remark and the pin-compatible discussion no longer apply |
| Replacement: assessment of the selected H743 | NEW | Resource table from the allocation file and header pinout (74 header GPIO, 37 assigned, 19 encumbered, 18 free), ADC, timer, serial, level and 5 V-tolerance rows. ST datasheet facts cited from the allocation file, not recomputed |
| Simultaneity paragraph and EXTI structural constraint | UPDATED / DROPPED | Simultaneity kept in new form, naming the unverified allocation rows. The F407-specific EXTI paragraph dropped: the design uses timer capture for flow and zero-cross, and the EXTI line mapping was an ST fact not to be recomputed. The shared-time-base worry kept as the TIM1/TIM3 sharing note |
| "One row is not cleared" (gauge VOH vs 3.15 V VIH) | UPDATED | Resolved by the 74HCT541 level-up buffer (D19). The retention-versus-gauge cost note and `DEC-DEVICE-RETENTION-BOUNDARY` kept. Added the allocation file's re-check note on the F407-based 5 V-tolerance analysis |
| Room for the channels the graph anticipates (table) | UPDATED | Brew pressure now designed (XDB401 on I2C1); current sensing now BL0942 (D17). Weight, group-head instrumentation and RTC kept as not designed. The old "five further conversion inputs and forty-eight unused pins" arithmetic DROPPED (F407 numbers); replaced with 18 free header GPIO and an unconfirmed ADC share |
| What this assessment does not establish | UPDATED | Compute and memory unquantified: kept, H743 figures substituted. "Board's usable subset" bullet: check now done via the header map, residual items listed. "This is not a selection" bullet DROPPED (selection exists as D1, not yet in graph) |
| The component list: intro, declared spend 250 USD | UPDATED | Intro now reports selection status. 250 USD and `REQ-COST-DISCIPLINE-001.C5/.C6`, `DEL-COMPONENT-SPECIFICATION.C5` carried. Added the currency mismatch (BOM in AUD) |
| Provenance classes | CARRIED UNCHANGED | |
| What each channel requires (18-row table) | UPDATED | Now 25 rows with columns Selected part, Class, Cost, Meets/open. All 18 old rows mapped; "Heater gate drive" now the ULN2003A; temperature row split into outlet water, NTC casing sensors, commissioning probes; mains-presence row kept as undecided (D20); other old rows carried with selected parts |
| New channel rows | NEW | Heater current and voltage metering (BL0942), outlet-water probe, commissioning probes, brew-path pressure, pressure containment (OPVs, dampers), tank level and knob switches, mains inlet protection |
| Against the declared figure (table and paragraphs) | UPDATED | Counts changed (25 specified, 24 selected); bought and reused counts to confirm; remaining not computed. `REQ-COST-DISCIPLINE-001.C2` and `.C4` paragraphs kept, re-aimed at the SSR and the deferred interlock |
| Open items collected | NEW | Twelve unresolved items gathered at the end |

## Post-review fixes

Applied after a review of the refreshed files; earlier entries above are superseded where they disagree.

1. **Valve relay rationale restored** in the two-way valve row: coils draw 17-61 mA against a BTA16's 60 mA maximum holding current, so a triac cannot reliably latch; contacts can weld; the vent being fail-safe (D6) is a separate point.
2. **5 V budget:** 0.53 A labelled as the typical-based budget, with the worst case at the VID6608 datasheet maximum (about 0.66 to 0.86 A); the 143 mA term is relay-module coil current (2 x 71.4 mA), not valve solenoid current.
3. **Steam OPV** called the pressure guarantee only conditionally on no check valve between it and the block (F7); otherwise the 200 C thermostat bounds the block at about 15.5 bar absolute.
4. **Stale statements corrected:** "internal T2A fuse is stated in D7" replaced (D7 names only an external recommended T2A and says an internal fuse is not established); "The four unverified items" corrected to five.
5. **OPEN DECISION: heater switching cadence (whole-cycle versus half-cycle)** marked wherever a half-cycle command rate is required (cadence bullet, both element rows, the load summary, open item 1); not chosen.
6. **D18 wording:** open-drain stages read "to be verified 5V-tolerant (PB4, PB5; see open-items.md section B)".
