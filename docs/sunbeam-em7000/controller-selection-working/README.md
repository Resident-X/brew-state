# Controller selection — working documents

Working drafts from an in-flight controller and mains-parts selection. **Not baselined, not
traced to any criterion, and not evidence for anything.** They are committed so the reasoning
survives the branch, because the graph currently has no way to hold a solution in a
pre-flight state waiting on an operator to physically build it.

Read them as a snapshot of a decision in progress, not as a record of one taken.

## Status of each file

| File | Status |
|---|---|
| `control-system-bom.csv` | **Current.** Parts, dimensions, rails, current, cost, and where each item physically lives. |
| `part-numbers.csv` | **Current.** Orderable part numbers, search terms, and the specific variant trap for each. |
| `heater-drive-and-supply-timing.md` | **Current for the heaters.** Why the heater SSRs need no phase reference, the burst scheme, and the BL0942 energy-metering case. Its zero-cross discussion pre-dates the move to the Standard pump dimmer, which brings a Z-C reference back for the pumps; see the position note at its top. Carries an unauthored graph revision. |
| `mains-inlet-protection.md` | **Current.** The inlet fuse / filter / surge chain, why each part, and the variant traps that make the obvious part numbers the wrong ones. |
| `temperature-sensing-front-end.md` | **Current.** NTC vs PT1000, the calibration approach, and why the MAX31865 boards were dropped. Carries one unmeasured claim. |
| `passive-and-drive-components.csv` | **Current.** Per-channel pull-ups, dividers, ADC filtering, gate drive and decoupling — everything needed beyond the purchased modules. Two rows are safety-critical. |
| `h743-header-pinout.csv` | **Current and verified.** The board's full 92-position header map with the onboard peripheral sitting on each pin, recovered from WeAct's own Altium library and cross-checked against their schematic. |
| `h743-pin-allocation.csv` | **Current and verified.** Channel-by-channel peripheral requirements for the H743 with pins assigned and every AF number, ADC channel and timer channel checked against the ST datasheet (DS12110, Table 9/10). Replaces the retired allocation. |
| `module-interconnect.csv` | **Current and re-derived.** Board name generalised to "Controller". Every explicit pin now matches `h743-pin-allocation.csv`'s verified H743 assignment; the XDB401 rows use the two-bus I2C1/I2C2 design, matching the BOM. |
| `wiring-and-connectors.csv` | **Current.** Wire gauge/insulation, crimp connectors, crimp tools and heat shrink for every branch (signal, 5V DC, mains trunk/pump/valve, and the heater branches' high-temperature requirement), plus the mains distribution/daisy-chain hardware question. AU-sourced. Fills the gap found when checking the BOM for completeness — `control-system-bom.csv`/`part-numbers.csv` cover components, not the wire/connector/tool layer between them. |

## Controller board

The controller is the WeAct MiniSTM32H743 (STM32H743VIT6), chosen for its 16-bit ADCs. Every pin,
timer, ADC and EXTI assignment in `h743-pin-allocation.csv` is checked against the ST datasheet
(DS12110). The board also carries a 0.96" ST7735 TFT, a microSD slot, 8MB QSPI plus 8MB SPI flash
and a DVP camera port; none of it is used, and it costs pins and height rather than function. The
header is two columns of 22 rows on each long edge at 2.54 mm pitch (WeAct BoardShape V12 drawing;
the Zephyr 2×40 figure does not apply), 88 holes plus a 4-pin SWD header, which is the 92 positions
of the header map. The 74HCT541 on the gauge lines is kept, and its
5V-tolerance analysis is to be rechecked against the H743's FT pin set. The hardware seam keeps the
control logic and tests away from the target layer, which is still real work.

## What is settled

- Controller: **WeAct MiniSTM32H743 (STM32H743VIT6)**, chosen for its 16-bit ADCs. 40.64 × 66.88 mm,
  with a 1A onboard DC-DC. The CI-enforced hardware seam holds 97.5% of firmware source and 100% of
  tests away from the target layer, which is still real work.
- Heaters: 2× EARU SSR-40DA zero-cross SSRs, heatsinked. Semiconductors are required because half-cycle
  burst-fire is; the OEM's mechanical relays could not be commanded per half-cycle.
- Pumps: **two RBdimmer 4A 1-channel modules, STANDARD (Z-C/DIM) variant**, one per pump. The
  controller times the triac from the module's Z-C output and fires it with a DIM pulse, so
  phase-angle and whole-cycle burst are both available. Screw terminals AC-N / AC-L in / AC-L
  load. MOC3021 confirmed random-phase from the board photo, so genuine phase-cut. BT136S at 4A
  against 0.1–0.22A pump current needs no heatsink. 50 × 16 mm, height to be measured.
- Valves: 4-channel mechanical relay module. Mechanical is not a preference — espresso
  solenoid coils draw 17–61 mA against a BTA16 holding current of 60 mA max, so a triac
  cannot reliably latch on them. The OEM's split (triac for pumps, relay for valves) was the
  same physics.
- Pressure: 2× XDB401, 3.3V supply / I2C output, G1/4.
- Supply: one 5V isolated mains module. The board's own DC-DC makes 3.3V, 1A max. **Mean Well
  IRM-10-5** (10W/2A) on a small hand-cut carrier Worst-case 5V load is about 0.53A (many items estimated); the IRM's derating curve
  (read from the spec sheet) is 100% to 50°C, about 75% at 60°C, about 50% at 70°C, which leaves
  the 2A part comfortable and the 1A part marginal at 60°C. No external parts are required; the
  T2A fuse and output caps are recommended. Enclosure ambient is itself unmeasured.
- Mains inlet protection: **Schaffner FN9222-10-06** filter, separate **T10A slow-blow** on
  active, **RN3404** MOV L–N downstream of the fuse. The machine's own protective chain
  interrupts on temperature only, and an AU plug is unfused, so nothing today answers a
  partial fault in the 8–15A band. No panel switch — AU outlets are switched, and a switch is
  not isolation for servicing. See `mains-inlet-protection.md`.

## Options rejected, and why

- MAX31865 RTD boards: the H743's 16-bit ADC with a ratiometric divider and a calibrated PT1000 meets the accuracy need. An Adafruit 3648 stays a fallback only.
- STM32F407 boards, including the MKS Robin Nano: a 12-bit ADC (about 2.2 °C resolution on the NTCs), and the Robin Nano takes only 12–24V in.
- I2C multiplexer: two separate I2C buses instead; the XDB401 address is also programmable in EEPROM.
- DimmerLink dimmer variant and a separate zero-cross detector: the Standard dimmer's Z-C is the phase and period reference.
- Fotek SSR-25DA and Crydom D2425: counterfeit Foteks are endemic, and the Crydom is about AUD 140 each against about AUD 15.
- HLK-10M05 and the HLK 3.3V and 5V modules, and the IRM-05-5: the Mean Well IRM-10-5 has documented approvals and derating, and the IRM-05-5 is marginal at 60 °C against a 0.53A load.
- The 2-channel mechanical relay module: the 4-channel costs AUD 0.70 more and gives headroom.

## What is open

- **The pump drive scheme itself is not settled.** The OEM steam pump 'thumps', which points to
  whole-cycle bursts, and one hobbyist report puts it at about 0.3 s on / 0.5 s off (unconfirmed).
  Pure phase-angle at the steam pump's low flow (about 0.43 g/s, 26 ml/min, from the 1126 W
  element) against steam backpressure may stall a vibratory pump. The Standard dimmer can do
  either; a bench step test (weigh output per 60 s at stepped power, then bursts) decides it.
- **The accuracy-vs-speed axis for temperature sensing.** The documents weigh accuracy against
  repeatability; the live trade is accuracy against response time, and nothing in the graph rules
  on it.
- **Recalibration as a maintenance activity**, which follows from choosing a sensor that drifts.
- The mainboard's own height, an estimate; 25 mm of cavity makes it worth measuring.
- The dimmer module's height — screw-terminal block plus PCB, not measured (footprint 50 × 16 mm).
- Valve count and placement. The machine already has a three-way diverter (group or hot water
  outlet, never closed) and a two-way on a second coffee block outlet that opens to the drain
  (owner statement, not yet confirmed on the machine; see `reference-machine.md`). The vent
  policy is the controller's to set. Decided 2026-10-11: the 2-way is normally open and is energised
  closed only for the 30-40 s shot, so it is open at the end of the brew to relieve the group pressure,
  open whenever the block heats with no possible flow path, and open for cleaning, faults and power loss. Not yet in the graph (one query found no clear owning node; not exhaustive).
- **Temperature sensing and the brew pressure tap.** Working position as of 2026-10-06: one
  calibrated PT1000 spike probe in the water at the block outlet before the 3-way valve (the key
  sensor; PA4), the block NTCs kept as casing sensors and calibrated against it under flow, two flat
  PT1000 chips as commissioning tools only (temporary puck-inlet probe on PA1, plus a spare), no
  MAX31865 (fallback; Adafruit 3648 is the PT1000 board). Brew pressure tap before the block between
  the OPV and the block, no capillary (a tap after the block was considered: the gain is only the
  block, valve and tube drop, estimated hundredths of a bar and unmeasured, against thermal mass on
  the controlled temperature path and loss of the OPV-node check; a tee on the second-outlet branch,
  which is a dead end while the vent is closed, is the cheap way to test it); steam tap on the steam side, a normal hairpin-clip tee between the steam block and the manual steam knob valve with a 100-150 mm downhill PTFE drop leg (not the cold side). Pending: the real maximum hot-side steam pressure (the steam OPV caps it only if no check valve lies between it and the block (to be inspected)), the PTFE rating at about 150 degC and the OEM tube size, a
  lifted-bracket check of how the NTCs are mounted, machine-side thread sizes, the XDB401 I2C
  variant's output rate and thread (probably NSA2302), the commissioning tests listed in
  `temperature-sensing-front-end.md`, and the graph decisions it names. Nothing authored in the graph.
- The over-pressure relief valves (brew and steam) and the membrane pulsation dampers (brew: retained;
  steam: not fitted, decided 2026-10-11). All are BOM items whether or not the OEM fits them. Each OPV's setpoint and the
  matching sensor's full scale are a coordinated pair, not two independent choices; the steam OPV
  is on the pump (about 4-5 bar per the owner) and caps the hot side only if no check valve lies between it and the block (to be inspected).
- Whether a measured supply period is admissible evidence for the supply frequency.
  `reference-machine.md` § Supply records 50 Hz as inferred from a pump nameplate, which
  `REQ-MACHINE-CONFIGURATION-001.C8` does not admit, leaving it provisional until measured. The
  Standard dimmer's Z-C capture is a measurement of the machine's own supply and costs nothing to
  take, but no accuracy is published for it, so whether it discharges that criterion is unsettled.
- Whether a surge-suppression criterion should exist at all. Nothing in the graph requires
  transient protection — `OBL-ELECTRICAL-THERMAL-SAFETY-001.C8` is about fault current, and a
  transient is not one. The MOV would be fitted on judgement alone. Unauthored; see
  `mains-inlet-protection.md` § Graph gap.
- Whether the machine has a hard mains switch at all. The five front-panel keys are
  enumerated as logic channels, not a mains break. Establish by inspection.
- The proof-of-life interlock, deferred. Downstream zero-cross sensing can verify the master
  relay opened, but cannot be the trip path: `REQ-SAFETY-CHAIN-001` requires the chain to owe
  nothing to the controller or firmware.
