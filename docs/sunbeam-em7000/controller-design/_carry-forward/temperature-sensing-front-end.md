# Carry-forward log: temperature-sensing-front-end.md

Old file: controller-selection-working/temperature-sensing-front-end.md. New file: controller-design/temperature-sensing-front-end.md.

## Section disposition

| Old section | Disposition |
|---|---|
| Header / working position (keep NTCs, calibrate, delete MAX31865; one claim unmeasured) | DROPPED (superseded by the position update; the "not baselined" disclaimer is CARRIED UNCHANGED) |
| Position update 2026-10-06 | UPDATED into section 1: PA4/PA1 pins, D-numbers, 125 C probe rating, tee-as-elbow added; 3648/3328 note, 4.7k divider, whole-mains-cycle averaging carried unchanged |
| "Corrections to the comparison table" bullets | DROPPED (comparison itself dropped); the Class A verification bullet CARRIED UNCHANGED into section 2 |
| What the requirement actually is | CARRIED UNCHANGED (merged into section 1) |
| The axis the documents have not weighed | UPDATED: shortened, marked "to confirm" (unresolved) |
| The comparison (NTC vs PT1000 table) | DROPPED (predates current position; PT1000 is now the water probe, NTCs are casing sensors) |
| Why NTC wins on the arguments available | DROPPED (comparison argument); retention-boundary and drift-as-maintenance points kept in sections 1, 2, 8 |
| Calibration | UPDATED: three-point Steinhart-Hart and bracketing kept; "in a stirred bath with final cable, not in situ" DROPPED because it contradicts D10 (calibrated in place against the water probe under steady low flow) |
| Front-end electrical notes | CARRIED UNCHANGED (ratiometric, TCR, self-heating, 16-bit) into section 3; filtering and ferrite bead details NEW from passive-and-drive-components.csv / BOM |
| Consequence: MAX31865 not needed | DROPPED except a short "why not"; lead-resistance argument CARRIED UNCHANGED into section 2 |
| The open measurement (NTC speed hypothesis) | DROPPED as framed (NTC-vs-PT1000 speed comparison); the unmeasured accuracy-vs-speed question kept in section 1 and 8; wand-disc note CARRIED UNCHANGED |
| Water probe, group hardware and commissioning: hardware findings, loss estimate | CARRIED UNCHANGED (section 4) |
| Probe fitting | UPDATED (section 2): gland rating, insulation numbers NEW from BOM; the dropped sentence about the earlier "tee a few cm clear of the casing" is removed as history |
| Commissioning tests 1-7 | CARRIED UNCHANGED (section 6) |
| Pre-shot conditioning | CARRIED UNCHANGED (section 7) |
| Pressure taps | UPDATED (section 5): "OPV" in the brew tap is now the new brew OPV (base machine has none, F8); D-numbers, D22 rejection, vent/check-valve sentence NEW from decisions.md; steam OPV/check valve conditional, PTFE caveat, XDB401, NSA2302 carried |
| Graph | CARRIED UNCHANGED (section 8) |
| What this owes the graph | UPDATED: three bullets kept, "Nothing has been authored" kept |
| Sections 3 (pins, PA4/PA1, PC0/PC1/PC4) and the 5-channel count | NEW from h743-pin-allocation.csv and passive-and-drive-components.csv |

## Numeric claims dropped

- NTC vs PT1000 table: NTC accuracy uncalibrated +/-2-5 C; calibrated ~+/-0.1 C; PT1000 drift <0.05 C/yr; NTC sensitivity ~4 %/C vs PT1000 0.385 %/C; "~10x" noise immunity (also "10x worse"); 3 probes needed.
- PT1000 with 1 kOhm reference (superseded by 4.7k): 1000 ohm at 0 C to ~1370 ohm at 95 C; 1.650 V to 1.908 V; 258 mV over 95 C; 2.7 mV/C; 50 uV/LSB; 54 counts/C; ~14 ENOB, ~13 counts/C, ~0.075 C. (The 1 kOhm current figures 1.4 mA / 2.6 mW are kept, from the BOM.)
- MAX31865 deletion savings: AUD 54, 714 mm2, six pins, the SPI2 bus.
- "12-bit divider already gave ~0.035 C/count".
- Calibration: "Steinhart-Hart holds to ~0.01 C" is kept (not dropped); the in-bath calibration instruction is dropped.
- "ratio claim: NTC probably faster" (no number) and the "five seconds slower / 0.5 C more accurate" illustration.
- Earlier recommendation of 0.1% divider resistors (replaced by TCR specification).
- Probe rating 200 C (never stated in this old file; the stale value is replaced by 125 C or more / 150 C preferred per decisions.md).

## Contradictions and unresolved items

- None of the old statements contradicts decisions.md after the corrections above; the in-bath NTC calibration instruction was the only conflict and decisions.md D10 resolves it.
- To confirm: whether a check valve lies between the steam OPV and the block (F7); whether the brew pump has no OPV (F8); NTC beta; Class A claims on the probe and chips; PA4 and PA1 ADC channel assignments (marked not yet verified in h743-pin-allocation.csv); machine-side thread sizes; the XDB401 3.3 V variant's output rate and thread; the NSA2302 identification; PTFE rating at the hot-side maximum; the unmeasured accuracy-versus-speed question.
- The old text said "about 1090 ohm at room temperature" for a PT1000; carried unchanged, not rechecked against a PT1000 table (to confirm).

## Post-review fixes

- Restored the step-response method (drive the block from cold, record the NTC against a fast reference) in section 1, where the speed question is open. Old section "The open measurement" disposition is now UPDATED, not DROPPED as to the method.
- Restored the NTC mounting finding (silicone-boot plug, element in a slot on its flat face, screwed clamp bracket with compound ring onto a flat plate, no wetted pocket, inferred from photos, lifted-bracket check) in section 2.
- Added a heater-ripple estimate to section 3: 1.5-2 K/s x 0.5 s = 0.75-1.0 K; the 0.9-1.9 K figure is withdrawn. The reviewer's 0.4 to 1.0 K lower bound is not reproduced from the stated numbers. The old figure still stands in heater-drive-and-supply-timing.md (not edited here).
- Section 5 steam OPV: capping of block pressure stated as conditional on no check valve between OPV and block (to be inspected); hot-side rating rule stated once, with gauge and absolute labelled; sensor overload 7.5 bar gauge and burst 15 bar gauge.
- Steam tap: stated that the plan is the hairpin-clip tee with a downhill PTFE drop leg, not a capillary; capillary only the fallback.
- Tagged the 0.05 to 0.2 degC noise target as an estimate (unmeasured) and block inlet and outlet at opposite ends as [WEB], low confidence.
