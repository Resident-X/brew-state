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
| Coffee thermoblock element | 1000 W | Circuit diagram, service manual p.24 — read at source |
| Steam thermoblock element | 1000 W | Circuit diagram, service manual p.24 — read at source |
| Steam pump | 22 W (JYPC-4) | Service manual parts list |
| Coffee pump | 48 W (Ulka EP5) | Manufacturer spec sheet for the fitted type |
| Mains fuse (control supply) | 5 A | Circuit diagram |
| **Total installed heating** | **2000 W** | Sum of the two elements |

Both elements together draw roughly **8.3 A at 240 V**. With both pumps running as well the worst case is about **2.07 kW, or 8.6 A**, inside a 10 A supply with roughly 330 W of headroom. Concurrent brew and steam is therefore *available* on this supply. It would not be at 120 V, where the same 2000 W is over 16 A.

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

**Pressure note — the open one.** `OBL-ELECTRICAL-THERMAL-SAFETY-001.C5` requires relief that acts on the pressure itself, works unpowered, and holds while a sensor is lying and while nothing has recognised a hazard. Nothing above establishes that any fitted device meets it, and the steam side has no documented relief at all.

Three things follow. A relief internal to the pump protects the pump, not the heated masses, and leaves with the pump if the pump is substituted. A working-pressure cap — an OPV of the kind `DEC-PROFILE-COMMANDS-FLOW` relies on — is not a safety device and does not discharge this obligation. And a thermostat is an over-temperature device; the obligation separates pressure from temperature deliberately, because a blocked outlet raises pressure while every electrical part behaves exactly as commanded.

This is the largest unevidenced safety claim in the project. It is not resolvable from either manufacturer document and needs the machine opened.

**On substitution.** The pumps in particular are expected to change as the design settles. `OBL-PHYSICAL-CONFIGURATION-001` is the obligation that applies: a substituted component silently changes the safety case its predecessor was part of, and the pump relief above is exactly that hazard in miniature.

## Already fitted

Sensing:

- Coffee thermoblock temperature sensor
- Steam thermoblock temperature sensor
- Steam wand temperature sensor, in the wand itself
- Water level sensor in the tank (magnet/reed type)
- Flow meter in the water path, wired to the OEM controller
- Two microswitches, one on each control knob

Actuation:

- Two pumps — one coffee, one steam
- Two solenoid valves — one on the coffee block, one three-way diverter
- Two stepper-driven analogue gauges (espresso "resistance to pour", milk temperature)

**Not fitted:** pressure transducer on either path; current sensing; real-time clock.

Other figures: water tank 3 L; espresso pump rated 15 bar; steam pump rated 4 bar.

## Thermal and hydraulic characteristics

**Not established.** These are to be measured during commissioning per `JRN-COMMISSION-PLANT-001`, not adopted from datasheets — which is what `REQ-MACHINE-CONFIGURATION-001.C3` requires.

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
| Sensing already fitted | `REQ-MEASUREMENT-001.C4`, `.C7`, `.C8`, `REQ-WATER-SUPPLY-001.C2` |
| Wiring authority | `OBL-ELECTRICAL-THERMAL-SAFETY-001.C9`, `REQ-ELECTRICAL-INSTALL-001` |

The clearest case is the supply. At 240 V the two elements together draw about 8.3 A and concurrent brew and steam fits inside a 10 A circuit. At 120 V the same 2000 W is over 16 A, so that concurrency is simply unavailable — which does not change any requirement, but does change what the machine can be asked for, and makes `DEC-PLUMBING-LEFT-AS-BUILT` a decision worth re-reading rather than inheriting.

## What is not declared here

Anything not listed above is not declared. A statement that depends on such a value is depending on an assumption, which is exactly what `OBL-OPEN-SOURCE-MAINTAINABILITY-001.C3` exists to prevent.

## A note on sources

Two Sunbeam documents were consulted: a service manual (parts lists, exploded views, circuit diagram) and a user instruction manual. Neither is reproduced here and neither is redistributed with this repository — they are the manufacturer's. What appears above are individual figures about one physical machine.

The OEM control electronics — two Holtek microcontrollers across three boards — are being replaced entirely. OEM control *behaviour* is not a specification for this project; it is only evidence of what the hardware is capable of.
