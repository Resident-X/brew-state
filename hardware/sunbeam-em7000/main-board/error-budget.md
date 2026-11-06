# Would better resistors help the main board's measurements?

A study of the main board's final design, board commit `c25f3af6`, from the repository's records alone.
Sources, all in this folder unless a path is given: `parts-specification.yaml` (PS), `circuit-proof.md` (CP, line numbers) and
`circuit-proof/*.log` (E_amc_front_end, E_pt_budget, C_front_ends), `circuit-verdicts.md` (CV), `docs/sunbeam-em7000/controller-io.md` (IO),
`docs/sunbeam-em7000/controller-board-design-constraints.md` (CON), `traceability.md`.

## Provenance

Produced 2026-11-05 from board commit c25f3af6, by Claude agents; models, no physical measurement. No board has been built: every figure below is datasheet arithmetic on the repository's own records, and the study's own arithmetic is marked as such. Line numbers cite the records as they stood at that commit.

"Worst case" means every part at its limit at once; the real error is usually smaller (my estimate: about a third for sums of independent parts).

## 0. Short answer

- Better resistors matter in **two places**: the **mains voltage divider** (R601-R604) and the **current shunt R105**. Everywhere else they do not change the answer by 20 %.
- Both only pay off **if the owner declares an accuracy for supply voltage / current** (none exists: CP 341, 344) and, for the shunt, **if a bring-up gain and offset calibration is also done**. When this study was made the repo provided no such calibration (section 2); the graph now carries one (`DEL-HW-BRING-UP.C22` for the bring-up step and `DEL-HW-MAIN-BOARD-DESIGNED.C28` for the firmware that applies the stored values), and the calibrated figures below (about 1.0 % for voltage, 1.6 % for current) are what C22 holds the calibrated channels to.
- The RTD channels already have 0.1 % / 25 ppm references (R640, R645). The NTC and pressure paths are limited by things resistors do not touch.

## 1. Assumptions used (all from the repo)

- **Temperature swing: 25 to 70 degC = 45 K.** 70 degC enclosure air is an *assumption* (CON "Enclosure air temperature", CP line ~330); the bring-up step `DEL-HW-BRING-UP.C13` measures it. 25 degC is where a bring-up calibration would be done (my assumption).
- Present resistors: UNI-ROYAL 1 %, 100 ppm/K (PS). Upgrade case: 0.1 %, 25 ppm/K thin film. The repo names Yageo RT0603BRD0710KL (C95204, 10 k, Extended) as a 0.1 %/25 ppm 0603 part, 0.0328 USD each plus an Extended-part setup fee of 3.07 USD (CON line 783), and Panasonic ERA3AEB4021V (C491130) already fitted on R640/R645.
- **Ageing: unknown** for every part (no load-life figure is in the repo). All numbers below leave it out.
- No bring-up measurement exists; no board is built (traceability.md section 0). All figures are datasheet arithmetic.

## 2. Does the plan provide a bring-up calibration?

- `DEL-HW-BRING-UP.C5` ("sensing accuracy is measured in the machine with the loads switching"): **measures** each channel against the graph's figure, by precision resistors at the connector or a calibrated probe. It says nothing about writing a correction. Verdict today: unknown.
- `open-items.md` item 4: "pick tighter divider parts ... **or accept a gain calibration at bring-up**" for supply voltage and current. Undecided; E1.2 and E1.5 stay unmet.
- `REQ-DRIFT-CORRECTION-001`: the machine corrects drift in its *plant-model parameters* in service, with no bench. I found no criterion saying it trims ADC or AMC gain and offset.
- `docs/sunbeam-em7000/controller-design/temperature-sensing-front-end.md` (module-era, "superseded in part", not baselined): calibrate NTCs in place against the water probe, three-point Steinhart-Hart. It also says "calibration absorbs initial tolerance (it solves for gain) but not drift; specify by TCR".
- **Verdict at the time of the study: a calibration is a stated option and a stated intent for the NTCs, but no baselined step applied it.** So both columns are given below. Since then `DEL-HW-BRING-UP.C22` requires a gain and offset calibration of the mains voltage and current channels on the built board with the stored values recorded, and `DEL-HW-MAIN-BOARD-DESIGNED.C28` requires the firmware to apply stored gain and offset values to those two channels; the NTC, pressure and RTD channels are still not covered.
  Calibration removes: initial tolerance, converter gain error and offset at the calibration temperature. It cannot remove: drift with temperature, ageing, noise.

## 3. Path by path

Error terms in the units of each path. "Now" = parts as drawn. "Better" = 0.1 %, 25 ppm/K (shunt: see 3.6). "Cal" = after a gain and offset calibration at 25 degC.

### 3.1 Coffee and steam NTCs (R501/R502, R503/R504; PC0, PC1). Requirement: +-2 degC (CON 383-384, `@estimated`)
- (a) Divider top R501, R503: 10 k, 1 %, 100 ppm/K. R502, R504: 1 k, 1 %, 100 ppm/K (series filter, no DC effect). VREF+ is +3V3A, so the divider is ratiometric (supply tolerance cancels).
- (b) At 88 degC, beta 3950 K, front end alone (C_front_ends.log, CP 273): 1 % tolerance **0.33 degC**, resistor drift **0.15**, clamp-diode leakage **0.56** (BAT54S 2 uA, 25 degC figure only; the 70 degC figure is in no source, so 0.56 is probably low). ADC offset and gain: typical only, 25 LSB = 0.05 degC, no maximum published. Noise: unknown. **NTC element: beta and tolerance class unknown** (pending, IO 153); the module-era note of "+-2-5 degC uncalibrated, about 0.1 calibrated" is unsourced.
- (c) Front end: now **1.05 degC**; better **0.63** (tolerance 0.03, drift 0.04, leakage 0.56). Cal: now about 0.7 (drift + leakage), better about 0.6. Whole channel: unknown, because the element is.
- Verdict: **no**. Uncalibrated, better R501/R503 cut the front end 40 %, but that is only 0.42 degC of a channel whose element error is larger and unknown (the change passes 20 % of the total only if the element is under about 1 degC, implausible uncalibrated). Calibrated, the gain is 15 %. The biggest front-end term (leakage) is not a resistor.

### 3.2 Wand NTC (R505/R506; PC4): no accuracy required (CON 386). Same parts. **Does not matter.**

### 3.3 Pressure, steam path, digital I2C (M4). Requirement +-0.775 bar, binding +-0.25 bar (CON 385, IO 163)
- (a) No resistor is in the measurement (R523-R526 are bus series and pull-ups). (b) The sensor's own accuracy: +-1 % of full scale for the XDB401 family (CON 574), +-0.05 bar on the 5 bar range the working design chose. (c) 0.05 bar now and with better resistors; calibration irrelevant. **Does not matter.** Brew path (M5): no accuracy required.

### 3.4 Pressure, analogue fallback (R531-R535, R537/R538 scaling, 10 k over 20 k; not the baseline sensor)
- (a) 10 k and 20 k, 1 %, 100 ppm/K; ratio 0.667. (b) Ratio error +0.96 / -0.97 % (1.08 % of span), from tolerance and 45 K drift (C_front_ends.log, CP 281). Transducer 1 % of full scale. A 5 V ratiometric sensor read against a 3.3 V reference also carries the 5 V rail tolerance (+-2.5 %, IRM-20): by my arithmetic about 0.07 bar at 2 bar on a 7 bar sensor. Resistors cannot fix that.
- (c) 7 bar sensor: now **0.146 bar**, better **0.081 bar** (front end 0.159 % of span); 10 bar: 0.209 vs 0.116; 25 bar: 0.523 vs 0.29. Cal removes tolerance but not the rail term.
- Verdict: **no** for the 5 to 11.9 bar range any plausible sensor has (both pass +-0.25 bar already: CP 281). It matters only for a 12 to 21.6 bar sensor, which the repo does not propose.

### 3.5 AMC131M02 channel 0, mains voltage (R601-R603 300 k, R604 750 ohm, R605/R606 49.9 ohm, C601). No accuracy declared.
- (a) R601, R602, R603: FOJAN FRC2512F3003TS, 300 k, 1 %, 100 ppm, 2512, 200 V working (PS). R604: 750 ohm, 1 %, 100 ppm, 0603. R605/R606: 49.9 ohm, 1 %, 100 ppm (their effect is below 0.001 %: they sit in front of 275 k minimum).
- (b) Terms (E_amc_front_end.log): resistor tolerance 2.0 % (R604 +1 %, high side -1 %) plus drift 0.9 % (100 ppm x 45 K x 2, opposite signs, worst case) plus converter input loading 0.31 % (275 k minimum; no maximum given) = **+2.94 / -3.15 %**. AMC: gain error +-0.2 % at 25 degC; drift 8 typ / 25 max ppm/K (0.11 % over 45 K); offset 330 uV max, 0.11 % of peak at 253 V (SBASA56 6.8, as quoted in CP 341). Self-heating of the divider: 24 mW in a 1 W part, 2.4 % of its rated rise, so under 0.03 % (my arithmetic). Noise and ageing: unknown.
- (c) Total, worst case:

| | Now | Better |
|---|---|---|
| Uncalibrated | 3.15 + 0.2 + 0.11 + 0.11 = **3.6 %** | 0.43 + 0.31 + 0.2 + 0.11 + 0.11 = **1.2 %** |
| Calibrated (gain, offset) | 0.9 + 0.11 = **1.0 %** | 0.225 + 0.11 = **0.34 %** |

  With 0.1 %/50 ppm parts: uncalibrated 1.6 %, calibrated 0.56 %. Offset drift: unknown.
- Verdict: **yes, if a figure of about 1 % or better is wanted.** Better parts cut the total by 66 % (uncalibrated) or 66 % (calibrated). The calibration is the cheaper first step, but it cannot remove the 0.9 % drift term, and 1 % parts cannot meet 1 % over temperature (CP 341 says the same).

### 3.6 AMC131M02 channel 1, mains current (shunt R105; R607/R608 470 ohm, C602). No accuracy declared.
- (a) **R105**: Vishay WSK25121L000FEA, 1 mohm, **1 %**, **TCR +-250 ppm/K**, 2512 **4-terminal already** (Kelvin pins 2 and 3), P70 1.0 W, -65 to +170 degC (PS, CV line 45). R607/R608: 470 ohm, 1 %, 100 ppm (CP 343, 344): against 1 Mohm input they cost 0.094 % gain; their tolerance and drift change that by under 0.001 %. **They do not matter.**
- (b) Shunt self-heating (I^2 x 1 mohm): **15 A: 0.225 W; 11.01 A: 0.121 W**; a single heater (4.8-5.4 A, division record) 23-29 mW. The repo gives only P70 = 1.0 W and the +170 degC limit, not the derating curve or thermal resistance (**unknown**). If the curve falls straight from 1.0 W at 70 degC to 0 W at 170 degC (my assumption), the rise is 100 K/W: **22.5 K at 15 A, 12.1 K at 11 A, about 2.5 K for one heater.** Over 25 degC: swing 67.5 K / 57 K / 47.5 K, so 250 ppm gives **1.69 % / 1.43 % / 1.19 %**. AMC channel 1: gain error **+-1 %** at 25 degC (channel 0 is +-0.2 %), drift 25 ppm/K max (0.14-0.17 %), offset 330 uV max = **2.1 % of the 15.6 mV peak at 11 A** (4.7 % at 5 A); offset can be zeroed at no current. Shunt tolerance 1 %. Thermal EMF, offset drift, noise: unknown.
- (c) Total at 11 A, worst case:

| | Now | Better (0.5 %, 50 ppm/K) |
|---|---|---|
| Uncalibrated | 1 + 1 + 0.07 + 1.43 + 0.14 + 2.1 = **5.7 %** | 0.5 + 1 + 0.07 + 0.29 + 0.14 + 2.1 = **4.1 %** |
| Calibrated (gain, offset) | 1.43 + 0.14 = **1.6 %** | 0.29 + 0.14 = **0.43 %** |

  (15 A: calibrated 1.8 % vs 0.5 %.) With the shunt at 100 ppm/K: calibrated 0.8 %.
- Verdict: **yes, but only together with a calibration.** Uncalibrated the shunt is 1.4 of 5.7 %, the converter's gain and offset dominate (28 % gain from a better shunt, borderline). Calibrated, the shunt's drift is 90 % of what is left and a better one cuts the total by 73 %.

### 3.7 RTD channels, MAX31865 U620/U621 (R640/R645 4.02 k reference). No range or accuracy declared (CP 351)
- (a) **R640, R645: 4.02 k, 0.1 %, 25 ppm/K thin film (Panasonic ERA3AEB4021V), already the better class.** Other parts: R641/R646 100 k pull-ups, links; not in the signal.
- (b) At 150 degC (E_pt_budget.log): reference tolerance **0.42 degC**, drift **0.47** (25 ppm x 45 K), converter terms 0.15 (offset +-3 LSB, gain +-1, INL +-1; one code 0.031 degC); sum 1.04 degC. Maker's front-page 0.5 degC is for the maker's conditions, not applied. A 2-wire lead of 50 ohm reads 25.6 degC high uncorrected; the probe's own class: unknown (none selected).
- (c) Now 1.04 degC, cal about 0.62 (drift and converter left). Going below 0.1 %/25 ppm (for example 0.01 %, 5 ppm) would reach about 0.2 degC: outside the 25-50 ppm class asked and availability is **unknown** from the repo. Verdict: **no change** (already in class); a calibration removes the 0.42 term.

### 3.8 Paths where resistors do not set the accuracy (verdict: **no**)
- **Flow (R520 pull-up 10 k, R521 1 k; PC6):** digital pulses, no accuracy imposed (CON 386); resolution +-0.2 mL/s comes from the meter's K-factor, which is unknown.
- **Tank level and knob switches (R861-R863), keys (R831-R835), mains-presence (R764/R765, R774/R775), zero-cross (R630/R631 LED feed):** threshold or timing inputs; the proofs give margins (CP 309, 323, 327) not accuracy. Zero-cross delay 0.07-0.78 ms, no requirement figure.
- **Load cells, HX711 (R670/R671 100 ohm series filter):** no cell chosen, no figure, HX711 accuracy and levels unknown (CP 354, 357); the 100 ohm resistors are in series with the bridge input and set no gain. **Unknown; resistors not the limit.**
- **ADC reference (+3V3A, R301/R302 0 ohm links):** ratiometric for the NTCs. The converter's gain, offset and total error are typical-only in DS12110: no maximum in the repo.

## 4. Summary of the 20 % test

| Path | Change from better resistors | Over 20 %? |
|---|---|---|
| Mains voltage, uncalibrated / calibrated | 3.6 to 1.2 % / 1.0 to 0.34 % | **yes** |
| Mains current (shunt), calibrated | 1.6 to 0.43 % | **yes** |
| Mains current, uncalibrated | 5.7 to 4.1 % (28 %) | yes, but poor value without calibration |
| Coffee and steam NTC | front end 1.05 to 0.63 uncalibrated (40 %), 15 % calibrated; total unknown | no |
| Analogue pressure fallback | 0.146 to 0.081 bar at 7 bar, both inside +-0.25 | no (already passes) |
| Digital pressure, RTD, flow, level, keys, zero-cross, mains-presence, load cells | none or already in class | no |

## 5. What to buy, for the worthwhile paths

Same footprints and pads, so **no layout change**. Each swap needs the proof rows that name it to be re-checked (value unchanged; only tolerance and TCR change). Availability in the JLCPCB catalogue was **unknown from the repo** for the first two; it was searched on 2026-11-05 and the result is stated after the list.

1. **R601, R602, R603** (now FOJAN FRC2512F3003TS, C2960835): 300 kohm, **0.1 %**, **<= 25 ppm/K** (50 ppm/K acceptable if 0.56 % calibrated is enough), footprint `R_2512_6332Metric`, **>= 200 V maximum working voltage** and 1 W (the stress rows E1.3 are 84.3 V rms and 24 mW), same 3-in-series arrangement. A matched network is not needed.
2. **R604** (now UNI-ROYAL 0603WAF7500T5E, C23241): 750 ohm, **0.1 %**, **<= 25 ppm/K**, thin film, `R_0603_1608Metric`, 100 mW. This is the low leg of the ratio and its tolerance counts as much as the whole high leg.
3. **R105** (now Vishay WSK25121L000FEA, C4248455): 1 mohm, **tolerance 1 % is acceptable if the gain is calibrated, else 0.5 %**, **TCR <= 50 ppm/K (100 ppm/K at most)**, **4-terminal (Kelvin) 2512 with the same land pattern `R_WSK2512_4T` and the same pin 2/3 sense assignment**, >= 1.0 W at 70 degC, **at least 15 A for 30 minutes**. It is a mains-side part on the entry sheet: confirm the land pattern matches before ordering, and re-check the R105 rows (CV line 45, CP 129-137 fault conductors). Alloy 4-terminal shunts of 50 ppm/K class exist in general; a specific drop-in is **unknown** from the repo.
4. **Not worth buying:** R501/R503 (C95204 10 k 0.1 %/25 ppm is the repo's identified part, if the owner wants the 40 % uncalibrated gain anyway), R531-R538, R607/R608, R605/R606, R640/R645 (already right).

**Availability, searched 2026-11-05 in the JLCPCB catalogue:** no 300 kohm or 750 ohm 0.1 % or 25 ppm/K part is in stock in the same footprints, so there is no drop-in upgrade of R601 to R604; the 50 ppm/K 1 mohm shunts that exist are 1206 or 2010, which change the footprint of R105 (a layout and mains-spacing change, since R105 is a mains-side part). The calibration is therefore the way the repo reaches the calibrated figures with the parts as drawn.

Also needed with the upgrades, none of which is a resistor: a **bring-up gain and offset step for AMC channels 0 and 1** (now `DEL-HW-BRING-UP.C22` and `DEL-HW-MAIN-BOARD-DESIGNED.C28`; section 2), and a declared supply-voltage and supply-current accuracy in CON "Sensing accuracy" (CP 341, 344). Without a declared figure the upgrades cannot be called met.
