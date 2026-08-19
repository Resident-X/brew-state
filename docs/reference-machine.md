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
| Coffee thermoblock element | 1000 W — **disputed, see below** | Circuit diagram, service manual p.24 — read at source |
| Steam thermoblock element | 1000 W | Circuit diagram, service manual p.24 — read at source |
| Steam pump | 22 W (JYPC-4) | Service manual parts list |
| Coffee pump | 48 W (Ulka EP5) | Manufacturer spec sheet for the fitted type |
| Mains fuse (control supply) | 5 A | Circuit diagram |
| **Total installed heating** | **2000 W** | Sum of the two elements |

Both elements together draw roughly **8.3 A at 240 V**. With both pumps running as well the worst case is about **2.07 kW, or 8.6 A**, inside a 10 A supply with roughly 330 W of headroom. Concurrent brew and steam is therefore *available* on this supply. It would not be at 120 V, where the same 2000 W is over 16 A.

**The coffee element's rating is disputed, and the concurrency conclusion above depends on it.** The service manual's circuit diagram gives both elements as 1000 W. The machine's owner recalls the coffee element being **1200 W** and the steam element 1000 W, and believes the manual to be wrong — a service manual describing a variant is exactly the failure `REQ-MACHINE-CONFIGURATION-001.C5` exists to keep visible, and neither reading has been established on this machine.

It is not a small difference, because the headroom above is what it eats:

| | Installed heating | Worst case with both pumps, at 240 V | At 253 V (230 V nominal, +10%) |
|---|---|---|---|
| Manual: 1000 + 1000 | 2000 W | 2.07 kW, 8.6 A | 9.1 A |
| Recollection: 1200 + 1000 | 2200 W | 2.27 kW, 9.5 A | **9.9 A** |

At the top of the permitted supply range the second reading leaves essentially nothing against a 10 A circuit. So *"concurrent brew and steam is available on this supply"* is a conclusion that holds on the manual's figures and is marginal on the owner's, and nothing downstream should treat it as settled until the elements are measured.

**Establish by measurement**, not by preferring one source to the other. Element power is a thermal characteristic of this machine, so `REQ-MACHINE-CONFIGURATION-001.C3` already requires it measured rather than adopted from a document; the reading is a resistance measurement across each element cold, which needs no bench rig and no energised machine. Until it happens, `firmware/params/thermoblock.params` carries the manual's figure with the dispute recorded against it, because the manual is the only citable source and a recollection is not one — that is a statement about provenance, not a judgement about which is right.

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

- Coffee thermoblock temperature sensor, on the block itself
- Steam thermoblock temperature sensor, on the block itself
- Steam wand temperature sensor, in the wand itself
- Water level sensor in the tank (magnet/reed type)
- Flow meter in the water path, wired to the OEM controller
- Two microswitches, one on each control knob

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

Actuation:

- Two pumps — one coffee, one steam
- Two solenoid valves — one on the coffee block, one three-way diverter
- Two stepper-driven analogue gauges (espresso "resistance to pour", milk temperature)

**Not fitted:** pressure transducer on either path; current sensing; real-time clock.

Other figures: water tank 3 L; espresso pump rated 15 bar; steam pump rated 4 bar.

## Thermal and hydraulic characteristics

**Not established.** These are to be measured during commissioning per `JRN-COMMISSION-PLANT-001`, not adopted from datasheets — which is what `REQ-MACHINE-CONFIGURATION-001.C3` requires.

The plant model needs figures for them before that happens, so `firmware/params/thermoblock.params` carries estimates, each recording what it was estimated from. An estimate recorded as an estimate is not a characteristic established by this section, and reading one back as though it were is exactly what recording the origin against each value exists to prevent. Read the origins in that file rather than this paragraph for which values are which: what the build guarantees is that every value there carries one and that the words are a fixed set, not what any particular value's origin currently says.

When commissioning establishes one of these on the bench, the measurement is recorded here and that value's origin in the description becomes `measured`. Until then, nothing in either place claims a measurement.

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

The clearest case is the supply. At 240 V the two elements together draw about 8.3 A and concurrent brew and steam fits inside a 10 A circuit. At 120 V the same 2000 W is over 16 A, so that concurrency is simply unavailable — which does not change any requirement, but does change what the machine can be asked for, and makes `DEC-PLUMBING-LEFT-AS-BUILT` a decision worth re-reading rather than inheriting.

## What is not declared here

Anything not listed above is not declared. A statement that depends on such a value is depending on an assumption, which is exactly what `OBL-OPEN-SOURCE-MAINTAINABILITY-001.C3` exists to prevent.

## A note on sources

Two Sunbeam documents were consulted: a service manual (parts lists, exploded views, circuit diagram) and a user instruction manual. Neither is reproduced here and neither is redistributed with this repository — they are the manufacturer's. What appears above are individual figures about one physical machine.

The OEM control electronics — two Holtek microcontrollers across three boards — are being replaced entirely. OEM control *behaviour* is not a specification for this project; it is only evidence of what the hardware is capable of.
