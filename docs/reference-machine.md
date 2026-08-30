# Reference machine declaration

**This file is local. Everything in it is specific to one machine on one supply in one jurisdiction.**

This is the declaration `REQ-MACHINE-CONFIGURATION-001` requires. The requirement graph in `specs/` is deliberately written without these values so that it survives being read by someone with a different machine. If you are rebuilding this elsewhere, replace this file — you should not need to edit a requirement.

Every value below carries its provenance, because they are not all the same kind of fact. Some are read off a document, some off the machine, and some are not established at all.

## The machine

Sunbeam Café Series **EM7000**, dual thermoblock espresso machine, AU/NZ market.

Two independently heated thermoblocks. One serves espresso **and** hot water; the other serves steam only.

Hot water is drawn off the **coffee** thermoblock. Its outlet passes through a three-way solenoid valve that sends flow either to the group head or to the hot water outlet. *(Provenance: traced on the machine with the case open. Stated in neither the service manual nor the instruction manual — the service manual contains no hydraulic schematic at all.)*

The consequence matters: espresso and hot water are mutually exclusive in the **plumbing**, not only in the thermal budget. No control strategy undoes that.

## Supply

| Value | Figure | Provenance |
|---|---|---|
| Supply voltage | 230–240 V AC | Instruction manual, given as an installation instruction rather than a ratings table |
| Mains frequency | 50 Hz | **Inferred** from a pump part marked `230V 50HZ`. Not stated as a machine rating anywhere |
| Circuit rating | 10 A assumed | Project assumption — the rating of an ordinary AU domestic outlet |
| Wiring authority | AS/NZS 3000 | Jurisdiction of the machine's market |

## Heating and load

| Value | Figure | Provenance |
|---|---|---|
| Coffee thermoblock element | 1004 W at 230 V, 1093 W at 240 V | Measured: 52.7 Ω cold, 20.3 °C ambient, converted at the declared supply |
| Steam thermoblock element | 1126 W at 230 V, 1226 W at 240 V | Measured: 47.0 Ω cold, 20.3 °C ambient — see note below on isolation |
| Steam pump | 22 W (JYPC-4) | Service manual parts list |
| Coffee pump | 48 W (Ulka EP5) | Manufacturer spec sheet for the fitted type |
| Mains fuse (control supply) | 5 A | Circuit diagram |
| **Total installed heating** | **2130 W at 230 V, 2319 W at 240 V** | Sum of the two measured elements |

**The coffee element's rating was disputed; a cold resistance reading measures and resolves it, in the manual's favour.** The service manual's circuit diagram gave both elements as 1000 W. The machine's owner recalled the coffee element as 1200 W and the steam element as 1000 W, and believed the manual to describe a variant — a service manual describing a variant is exactly the failure `REQ-MACHINE-CONFIGURATION-001.C5` exists to keep visible. 52.7 Ω does not admit a 1200 W element on this supply, so the manual's figure stands. What the reading also settled, and what neither document claimed, is that the two elements are *not* equally rated: the steam side's 47.0 Ω draws meaningfully more than the coffee side's 52.7 Ω, so the total installed heating this machine actually carries is higher than either previous figure (2000 W manual-equal, or 2200 W disputed-recollection).

The steam reading carries one further caveat. The bench could not get the element off the circuit to read it in isolation, and a parallel path across it — a thermostat, most likely — can only pull a resistance reading down, never up. So 47.0 Ω is a lower bound on the true element resistance, and the 1126–1226 W it produces is a conservative ceiling on the steam side's power rather than a central estimate.

Both elements together draw roughly **9.3 A at 230 V, 9.7 A at 240 V**. With both pumps running as well the worst case is about **2.39 kW, 9.95 A at 240 V**, essentially the full 10 A a domestic circuit provides:

| | Installed heating | Worst case with both pumps, at 240 V | At 253 V (230 V nominal, +10%) |
|---|---|---|---|
| Measured: 52.7 Ω / 47.0 Ω | 2319 W | 2.39 kW, 9.95 A | 2.65 kW, **10.5 A** |

At the top of the permitted supply range the measured total now exceeds a 10 A circuit on the arithmetic alone. That does not mean this machine trips a breaker every time brew and steam run together: `REQ-POWER-BUDGET-001` already requires the controller to plan within the budget rather than discover it by reaching it, evaluated against exactly this kind of pessimistic, worst-of-span figure. What it does mean is that this document's earlier claim — that concurrent brew and steam is simply *available* on this supply — no longer holds unconditionally. Whether a given draw is available is a question the controller's budget arbitration answers; it is not a standing property of the supply the way it looked when the elements were assumed equally rated at 1000 W each.

## Protection

| Device | Figure | Provenance |
|---|---|---|
| Coffee thermoblock thermostat | 110 °C nominal (95–110 °C, ±3) | Parts list |
| Steam thermochamber thermostat | 200 °C ±5 (180–200 °C) | Parts list |
| Pump thermostat | 110 °C | Parts list |
| Thermal fuse | Fitted; **rating not established** | Only its mounting bracket is itemised. Establish by inspection |
| Over-pressure relief, coffee side | A `RELIEF ADAPTER BRASS` is fitted to the coffee thermoblock; **setting and function not established** | Service manual parts list. Establish what it is and at what pressure it acts |
| Over-pressure relief, espresso pump | Instruction manual claims the pump is "fitted with a pressure relief system"; **device, location and setting not established** | Instruction manual, in marketing prose rather than a specification. May be internal to the pump, in which case it protects the pump and nothing else, and it leaves with the pump if the pump is substituted |
| Over-pressure relief, steam side | **None documented anywhere** | Neither document lists a relief part for the steam thermochamber. Its 200 °C thermostat is an over-temperature device and does not discharge a pressure obligation |
| Resettable vs one-shot | **Not established** for any of the three thermostats | Establish |

**Reading the parenthetical spans.** The `(95–110 °C, ±3)` and `(180–200 °C)` figures beside the coffee and steam thermostats are the parts-catalogue range the thermostat part number is manufactured in, not this specific fitted device's own tolerance — the parts list identifies the 110 °C / 200 °C variant as fitted, and the `±3` / `±5` alongside it is that variant's own manufacturing spread. `DEC-PROTECTION-TRIP-POINTS-FROM-PARTS-LIST-LOW-TOLERANCE-END` records this reading and why: a 95 °C or 180 °C worst case would make the margin note below, and the saturation-pressure table further down, both wrong about the same number, and would leave this machine unable to reach its own shipped brew target.

**Margin note.** The coffee block's commanded target sits below its 110 °C thermostat, and the ±3 °C tolerance means the worst-case margin is a few degrees. That margin is what `REQ-MEASUREMENT-001.C1` is written against, and it is the reason absolute accuracy matters more than repeatability on this channel.

**Pressure note — the open one.** `OBL-ELECTRICAL-THERMAL-SAFETY-001.C5` requires the pressure this machine can generate to be **contained or released** without anything electrical having to act, and that guarantee to hold unpowered, with a sensor lying, and with nothing having recognised a hazard. Containment by adequate strength is an admissible answer; so is a relief device. What is not admissible is a guarantee that depends on something noticing.

**The level to design against is not the pump's.** On a heated mass with its outlet shut, pressure is set by saturation at whatever temperature the protection permits. The two sides differ by an order of magnitude:

| | Protection permits | Saturation pressure | Dominant source |
|---|---|---|---|
| Coffee side | 110 °C | ≈1.4 bar absolute | the pump, at up to 15 bar |
| Steam side | 200 °C (+5 tolerance) | ≈15.5 bar absolute, ≈17 bar at tolerance | thermal, by a wide margin |

*(Saturation figures from standard steam tables; worth confirming against a reference before they size anything.)*

**So the two sides need different answers.** On the coffee side the pump dominates by more than tenfold, and a working-pressure cap plus a vessel rated above it with margin designs the hazard out — no device left to fail, nothing to test periodically, nothing that leaves when a part is substituted. On the steam side thermal generation dominates, no OPV sits in that path at all, and water flashing to steam is roughly a 1600× expansion, so a trapped volume with a kilowatt entering it does not need long.

Three traps to avoid when this is settled. A relief internal to the pump protects the pump, not the heated masses, and leaves with the pump when it is substituted. A working-pressure cap — the OPV `DEC-PROFILE-COMMANDS-FLOW` relies on — bounds a pressure *source*, not a blockage *location*: a restriction between the heated mass and the cap leaves the trapped volume on the wrong side of it. And a thermostat is an over-temperature device; the obligation separates pressure from temperature deliberately, because a blocked outlet raises pressure while every electrical part behaves exactly as commanded.

This is the largest unevidenced safety claim in the project. It is not resolvable from either manufacturer document and needs the machine opened.

**Hypothesis, not established.** The brew solenoid may vent to the drip tray in its de-energised position, which is standard espresso practice and would explain the absence of a dedicated relief part. If so it is a genuine fail-safe vent: losing power, or losing the controller's proof of life, opens the vent path without anything having to decide.

It would still not meet the criterion. During a delivery the valve is deliberately held energised, which is exactly when pressure is highest, so a rise that firmware has not recognised is a rise nothing vents — the case the criterion names in its own wording. It is also on the brew path only, and it addresses hydraulic pressure, which the pump's own maximum already bounds. The uncovered case is thermal: heating against a blocked outlet with no flow, which on the steam side is the normal operating mode with the wand shut.

To confirm at the machine: the parts list places the three-way valve (`3T0618W`) near the hot water arm and a two-way (`2T0607W`) on the thermoblock, while the schematic drives them as `COF VALVE` and `HOT VALVE`. Which of the two is the brew-and-vent valve, and whether either vents at all, is not established.

**On substitution.** The pumps in particular are expected to change as the design settles. `OBL-PHYSICAL-CONFIGURATION-001` is the obligation that applies: a substituted component silently changes the safety case its predecessor was part of, and the pump relief above is exactly that hazard in miniature.

## Already fitted

Sensing:

- Coffee thermoblock temperature sensor, on the block itself — **NTC type**, a two-wire lead assembly. *(Provenance: service manual parts list, thermoblock assembly, `COFFEE NIC WIRE L=505MM RED 2P/2C`, Sunbeam part no. `EM70025`. `NIC` is read as `NTC`: an artefact of the scanned document rather than a part class, and the reading the two sibling sensors below corroborate — the wand sensor's line names `NTC` outright, the steam block's names a thermistor, which is the family rather than that specific class.)*
- Steam thermoblock temperature sensor, on the block itself — **NTC type**. *(Provenance: service manual parts list, thermo-chamber assembly, `Steam SOLEPLATE THERMISTOR SR6000 wire`, Sunbeam part no. `EM70020`, which names it a thermistor directly.)*
- Steam wand temperature sensor, in the wand itself -- a metal conduction disc on the wand's exterior, isolated from the wand body by an O-ring, wired today to drive the milk-temperature gauge below directly rather than read digitally. *(Provenance: owner's direct account of the physical wand, not yet bench-verified.)* **NTC type** — of the three this is the one the parts list labels `NTC` in as many letters. *(Provenance of the type: service manual parts list, steam arm assembly, `Steam Arm NTC WIRE L=780MM WHITE 2P/2C`, Sunbeam part no. `EM70024`.)* **Hypothesis, not established:** the disc lags real milk temperature, and is believed to respond to both the wand's own internal heat and the milk it contacts externally, with external contact suspected to dominate the faster response -- but the relative weight and lag of each path has not been characterised, and nothing here establishes whether the O-ring's isolation is adequate to make this a usable milk-temperature reading at all.
- Water level sensor in the tank (magnet/reed type)
- Flow meter in the water path, wired to the OEM controller -- fitted roughly 5-7 cm ahead of the coffee (Ulka EP5) pump, which serves both the brew and hot-water paths, on the suction line drawing from the tank. It sits below the tank's water level, so the suction line stays flooded rather than needing to self-prime by lift. No meter is fitted on the steam path. *(Provenance: owner's direct account of the physical machine, not yet bench-verified.)* **Its interface type is not established**, and one reading of the circuit diagram argues against the obvious assumption: on sheet 3-3 the meter's pair appears to reach `U8` through a resistor network at pins labelled as analogue inputs, rather than at a counter or an edge-triggered pin as a pulse output would. That is a reading of a scan and nothing more — it is recorded here as a question a bench check settles in minutes, not as a finding. It is not an idle question: `SOL-FLOW-METER-READING-AT-CONTROLLER.C1` is the work that establishes this meter's signal type and scaling from its markings or a datasheet, and `.C2` branches on the answer — an analogue output substitutes a real ADC input into a table the firmware already carries, while a pulse or frequency train needs timer input capture and a pulse counter that read path does not have today. So this observation is something that work would take in, and if it holds it revises the pulse-train expectation `.C2` currently calls typical for the class. If it holds it also places the meter's channel on `U8`'s board, which would bring it inside the retention question recorded below; the reading is nowhere near firm enough to state that as more than a conditional.
- Two microswitches, one on each control knob
- Eight pushbuttons on the operator-interface panel, `S1` to `S8`, each held up through a 1 kΩ resistor into `U8`, the second Holtek microcontroller (`HT66F50-28SOP`). *(Provenance: service manual circuit diagram, sheet 3-3.)* **These are not the two knob microswitches above** — those are itemised on the L-panel and R-panel assemblies, rated 250 V 3 A each, and are a separate physical control surface from this membrane panel. The count of eight is certain. Their labels read, left to right, `PWR`, `MAN`, `ONE`, `TWO`, `PRG`, `WAT`, `HOT`, `STM` — power, manual, one cup, two cups, program, water, hot water, steam — which is the best reading available off the scan rather than a beyond-doubt one, since several individual letters are marginal. The debounce interval the panel expects is **not established**; the schematic shows the pull-ups and no timing.
- Mains zero-cross detection, on the OEM control board. The line (`ACL`) reaches a `PC817` optocoupler through a `1N4007` diode and a 120 kΩ 1 W resistor, and the optocoupler's output drives the interrupt pin of `U3`, the Holtek `HT48R065-16NSOP` that also drives both heaters, both pumps and both valves. *(Provenance: service manual circuit diagram, sheet 3-1 — the same sheet as the machine's low-voltage supply, but a circuit separate from it.)* It is listed here because it is a channel the machine already carries, not because the part survives: the board it sits on is one of the three being replaced. What it establishes is that the OEM design gave its controller a mains-phase reference, which is what both phase control and burst firing need to place a switching instant, and that a replacement controller wanting either has to provide that reference itself. This project has since committed to burst firing: `DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM` converts commanded levels into a per-half-cycle energise-or-idle decision, so the phase reference is now an unconditional requirement on a replacement controller rather than a conditional one. The same decision makes the half-wave feed described below insufficient on its own terms, since a scheme resolving half-cycles cannot be timed against a reference reporting every second crossing. The half-wave feed means the OEM detector sees one conduction window per mains cycle rather than a symmetric edge at each crossing; the exact relationship between that window's edges and the true crossing is **not established**.

**Nothing measures the brew path downstream of the coffee block.** That is a
property of the list above rather than a separate claim — there is no sensor at
the group, in the delivery line, or anywhere between the block and the puck — and
it is load-bearing well beyond this document. The temperature an extraction is
judged by is the water's at the group, so on this machine that temperature is not
measured at all and can only be reconstructed from the block's. `firmware/params/thermoblock.md`
sets out what that costs: the coefficient relating the two sits downstream of the
only sensor, so nothing the machine reads depends on it, and no run of the machine
as it stands can narrow it or notice it drifting.

Where within the block each temperature sensor is bonded is **not established**,
and the plant model does not distinguish it — the block is one uniform
temperature there. That is recorded as an omission in the same file. What the
list above does establish is the part the design leans on: the sensor is on the
block and not in the stream.

**What the parts list settles about the three sensors, and what it does not.** It settles the class: all three are NTC thermistors on two-wire leads, which is what the firmware's conversion path and the controller's analogue front end have to suit, and it replaces a type that until now was assumed rather than read. It settles nothing electrical. No beta value, no base resistance at any reference temperature, and no tolerance class appears against any of the three lines — a parts list identifies a part to order, not a part to model. So the ±2 °C accuracy the control declarations carry for the two block channels — the coffee and steam blocks; no such figure is declared for the wand disc, and `controller-io.md` deliberately declines to borrow either one for it — remains an estimate of the class rather than a figure read off this part, and the curve any firmware converts through is still to be established, by datasheet if the part can be identified further or by bench characterisation if it cannot.

Actuation:

- Two pumps — one coffee, one steam
- Two solenoid valves — one on the coffee block, one three-way diverter. Both coils are **mains AC**: the circuit diagram puts each valve coil in series with the line (`ACL`) on the switched side of its own relay's contacts, so the coil is energised at supply voltage and not from a stepped-down DC rail. *(Provenance: service manual circuit diagram, sheet 3-2. Unlike the switching devices tabulated below, this is a property of the valve parts themselves rather than of the board that drives them, and it survives the board's replacement.)* The coils' VA is **not established**; no document gives it.
- Two stepper-driven analogue gauges (espresso "resistance to pour", milk temperature), both driven by a `VID66-08` two-channel stepper motor driver IC on the operator-interface board, wired to the two motors (`MOT1` and `MOT2`) and commanded over direct control lines from `U8`. *(Provenance: service manual circuit diagram, sheet 3-3.)* This settles a previously open alternative: the gauges are reached through a dedicated driver IC, not by a step-and-direction pulse train into bare motor windings, and not over a serial link to a separate driver board.
- Roughly ten LED elements on the operator-interface panel, each behind its own ~300 Ω series resistor off an output pin of `U8`, grouped into about six indicator functions: `PWR` (one element), `MIN` (two, possibly a single two-colour indicator), `ONE` (one), `TWO` (two), `PRG` (two) and `WATER` (two). *(Provenance: service manual circuit diagram, sheet 3-3.)* **Both counts are the best reading of the scan rather than hard figures** — a recount, at the panel or against a cleaner copy of the sheet, is worth doing before either number sizes anything. Forward current per element is **not established**; the series resistors are drawn without a supply rail this reading could pin them against.

**What the OEM boards switch each mains load with.** The machine carries six mains loads — the two elements of the heating section above, the two pumps, and the two valve coils — and the OEM design drives every one of them the same way: a small transistor stage off a `U3` output signal, switching the input side of a relay or an opto-triac driver, whose output side carries the line to the load. The devices differ by load:

| Load | OEM switching device | Signal |
|---|---|---|
| Coffee thermoblock element | Mechanical relay, Hongfa `HF3FD/012HST`, 12 V DC coil | `CFHET` |
| Steam thermoblock element | Mechanical relay, Hongfa `HF3FD/012HST`, 12 V DC coil | `SMHET` |
| Coffee pump | `MOC3021` opto-triac driver into a triac | `CFPUM` |
| Steam pump | `MOC3021` opto-triac driver into a triac | `SMPUM` |
| Solenoid valve, schematic tag `COF VALVE` | Mechanical relay, Hongfa `HF32FA/012HSL`, 12 V DC coil | `CFVAL` |
| Solenoid valve, schematic tag `HOT VALVE` | Mechanical relay, Hongfa `HF32FA/012HSL`, 12 V DC coil | `HTVAL` |

*(Provenance: service manual circuit diagram, sheet 3-2. The two valve rows are named by schematic tag rather than by part number, because which tag drives which physical valve is not established — the same open pairing the Protection section above turns on.)* This table is **evidence of what the OEM hardware does, not a specification for this project** — the same reading the note on sources applies to OEM control behaviour, extended to the parts that behaviour was built out of. What it does establish is a capability split worth knowing before anything is chosen: the two pumps are driven through opto-triacs into triacs, which is phase-control capable, while the two elements are switched by plain mechanical relays, which can be on or off and nothing between. So whatever the OEM firmware did with a heater, it did on or off, at whatever cadence a relay tolerates; and the zero-cross channel above has an obvious use on the pumps, though a relay is also commanded at a crossing to spare its contacts, so the reference being there does not settle which load it was for. What the OEM firmware actually did with any of them is not established and is not the point — none of it constrains what this project drives them with. Relay coil currents, contact ratings and triac ratings are **not established**; the schematic names the parts and not their operating points.

**The operator-interface board is enumerated as channels, not adopted as a part.** The eight buttons, the LED elements and the two gauge steppers all sit on `U8`'s board, which reaches `U3`'s board over two wires. The flow meter may sit there too — the sheet-3-3 reading noted against it above appears to bring its pair into `U8` — and if that reading holds, the same retention question reaches that channel as well; it is not firm enough to list the meter here as more than a possibility. Whether a replacement controller could speak that link and keep the board — rather than rewire every one of those channels onto itself — is open, and `DEC-U8-BOARD-RETENTION-UNVERIFIED` records it as such: neither Holtek part's firmware nor the link's protocol is documented anywhere, the question is answerable on the bench with a logic analyser and nobody has answered it, and until somebody does the project assumes full replacement. So the channels above are declared as things a controller must be able to serve directly. That is the conservative reading of an open question, not a finding against retention.

**Not fitted:** pressure transducer on either path; current sensing; real-time clock.

**Planned addition, not yet fitted.** `DEC-STEAM-PRESSURE-SENSOR-ADDED` records the decision to add a steam-path pressure transducer, made because `REQ-MEASUREMENT-001.C8` requires steam pressure measured rather than inferred from temperature. Simulation work assuming this channel exists is proceeding ahead of the physical fitting; the line above stays accurate to the machine as documented until that fitting happens and this note is replaced with a provenance entry of its own.

Other figures: water tank 3 L, from the machine's EM7000 specification; espresso pump rated 15 bar, the Ulka EP5's nameplate figure, consistent across independent listings but not read from a manufacturer datasheet held here; steam pump rated 4 bar, a nameplate-type figure for the JYPC-4 family whose datasheets range 1.5–7.0 bar across variants — which variant is fitted is not confirmed, so this figure is not established to the precision the other two carry.

## Thermal and hydraulic characteristics

**Partially established.** The two element ratings are now measured — see the heating-and-load section above for the readings and the figures they produced. Everything else here — thermal mass, loss coefficients, pump characteristics, outlet geometry — remains to be measured during commissioning per `JRN-COMMISSION-PLANT-001`, not adopted from datasheets, which is what `REQ-MACHINE-CONFIGURATION-001.C3` requires of all of them.

The plant model needs figures for the rest before that happens, so `firmware/params/thermoblock.params` carries estimates for them, each recording what it was estimated from. An estimate recorded as an estimate is not a characteristic established by this section, and reading one back as though it were is exactly what recording the origin against each value exists to prevent. Read the origins in that file rather than this paragraph for which values are which: what the build guarantees is that every value there carries one and that the words are a fixed set, not what any particular value's origin currently says.

When commissioning establishes one of the rest on the bench, the measurement is recorded here and that value's origin in the description becomes `measured`, the same way the two element ratings just did.

## What depends on these values

If you replace this file, these are the parts of the graph your substitution reaches. Without this table you can swap the numbers but cannot discover what you have changed, which is most of what the declaration is for.

| Declared value | What depends on it |
|---|---|
| Supply voltage, circuit rating | `OBL-ELECTRICAL-THERMAL-SAFETY-001.C3`, `REQ-POWER-BUDGET-001`, `JRN-SERVE-GROUP-001.C2` and `.C5` |
| Mains frequency | `REQ-MACHINE-CONFIGURATION-001.C4`, `OBL-REALTIME-DISCIPLINE-001` |
| Element ratings | `REQ-POWER-BUDGET-001`, `OBL-ELECTRICAL-THERMAL-SAFETY-001.C3` |
| Thermostat trip points | `REQ-MEASUREMENT-001.C1`, `REQ-BREW-TEMP-001`, `REQ-SAFETY-CHAIN-001.C3` |
| Which mass serves hot water | `REQ-HOT-WATER-001` and `.C4`, `JRN-SERVE-LONG-BLACK-001`, `DEF-COFFEE-SIDE` |
| Warm-up time | `REQ-SCHEDULED-READINESS-001` and `.C5`, `DEC-NO-REMOTE-ACTUATION` |
| Sensing already fitted | `REQ-MEASUREMENT-001.C4`, `.C5`, `.C6`, `.C7`, `.C8`, `REQ-WATER-SUPPLY-001.C2`, `REQ-ACTUATION-CONFIRMATION-001.C5` |
| Wiring authority | `OBL-ELECTRICAL-THERMAL-SAFETY-001.C9`, `REQ-ELECTRICAL-INSTALL-001` |

The clearest case is the supply. At 240 V the two measured elements together draw about 9.95 A with both pumps running — essentially the whole of a 10 A circuit, rather than the roughly 330 W of headroom the manual's figures suggested — and at 253 V the arithmetic exceeds it outright. At 120 V the same installed heating is over 16 A, so concurrency is simply unavailable there regardless — which does not change any requirement, but does change what the machine can be asked for, and makes `DEC-PLUMBING-LEFT-AS-BUILT` a decision worth re-reading rather than inheriting.

## What is not declared here

Anything not listed above is not declared. A statement that depends on such a value is depending on an assumption, which is exactly what `OBL-OPEN-SOURCE-MAINTAINABILITY-001.C3` exists to prevent.

## A note on sources

Two Sunbeam documents were consulted: a service manual (Issue A, June 2012 — parts lists, exploded views, circuit diagram sheets 3-1 to 3-3) and a user instruction manual. Neither is reproduced here and neither is redistributed with this repository — they are the manufacturer's. What appears above are individual figures about one physical machine. Where a statement above cites a sheet or a part line, it cites where the figure was read, so that a reader holding the same document can check it and a reader without one can see exactly what is being leaned on.

The OEM control electronics — two Holtek microcontrollers across three boards — are **assumed** replaced entirely. That is the project's current working assumption and not a settled fact: `DEC-U8-BOARD-RETENTION-UNVERIFIED` leaves open whether a replacement controller could speak the two-wire link between the OEM boards and keep the one carrying the buttons, LED indicators and gauge steppers, and it holds full replacement as the default only until a bench capture answers that. OEM control *behaviour* is not a specification for this project either way; it is only evidence of what the hardware is capable of.

That reading now has to carry named parts as well as behaviour, because this document names some. The relays, the opto-triacs and the zero-cross optocoupler above are what the OEM boards were built out of: they establish what this machine's loads have been switched with and what timing reference its controller was given, and they specify nothing about what switches them next. The one place a part named off the schematic settles a machine fact rather than an OEM one is the solenoid coils' voltage class, which belongs to the valves and not to the board driving them — which is why it is stated as established fact in *Already fitted* while the switching devices tabulated beside it are marked as evidence and nothing more.
