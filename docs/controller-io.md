# Controller I/O enumeration

**This file is local, like `reference-machine.md`.** It answers one question: what does a
controller have to provide to serve every channel this machine already senses or drives, plus
every channel the graph has since decided to add? It is written by hand in this slice —
`DEL-COMPONENT-SPECIFICATION.C6` (regenerating a specification and purchase list from the graph)
is a later criterion of the parent task and is not attempted here.

Every row traces to one of two sources: the machine's declared configuration in
[`reference-machine.md`](reference-machine.md) — sensing and actuation recorded there as already
fitted — or a decision that added a channel, named against that decision rather than appearing
without provenance. A channel is not in this enumeration unless one of those two things put it
there; a channel a requirement wants but nothing has yet fitted or decided to fit is called out as
open, not invented into a row.

Out of scope, per `SOL-CONTROLLER-CHANNEL-ENUMERATION`: what accuracy, resolution or update rate
any channel needs (derived separately, against work — sensing error carried in the commanded
margin — that has not landed); choosing a specific part or controller for any channel; the cost of
anything; wiring, fitting or pin assignment; and the machine's plumbing, which `DEC-PLUMBING-LEFT-AS-BUILT`
already leaves as the factory built it.

## Sensing channels

| Channel | Signal | Peripheral class | Count | Safety-relevant | Source |
|---|---|---|---|---|---|
| Coffee thermoblock temperature sensor | Not established — element type (NTC, RTD, thermocouple) is not recorded by either manufacturer document | Not established — follows from signal type above | 1 | No — controller does not sit in the protective chain (see Protective devices below) | `reference-machine.md` § Already fitted |
| Steam thermoblock temperature sensor | Not established, same reason | Not established | 1 | No | `reference-machine.md` § Already fitted |
| Steam wand temperature sensor (conduction disc, wand exterior) | Not established. Wired today to drive the milk-temperature gauge directly rather than read digitally, so an analogue element of some kind is implied, but its type and levels are not recorded | Not established | 1 | No | `reference-machine.md` § Already fitted |
| Water level sensor (tank) | Digital — magnet/reed contact closure | Plain digital level | 1 | No | `reference-machine.md` § Already fitted |
| Flow meter (water path, suction line ahead of coffee pump) | Not established. Meters of this class commonly present a pulse train, but this fitted part's output is not confirmed against a datasheet | Not established, pending confirmation — a pulse output would want counter or timer capture | 1 | No | `reference-machine.md` § Already fitted; siting decided by `DEC-FLOW-SENSED-UPSTREAM-OF-PUMP` |
| Control-knob microswitches | Digital — contact closure | Plain digital level | 2 (one per knob) | No | `reference-machine.md` § Already fitted |
| Steam-path pressure transducer | Not established — not yet physically fitted; typical transducers of this class present a ratiometric analogue output but this part has not been selected | Not established, pending part selection — analogue conversion is the expected class | 1 | No — the pressure guarantee is deliberately not permitted to depend on anything noticing (`reference-machine.md` § Protection, "Pressure note") | Added by `DEC-STEAM-PRESSURE-SENSOR-ADDED`; not yet fitted |

**Nothing measures the brew path downstream of the coffee block** (`reference-machine.md` §
Already fitted) — that limit is inherited unchanged into this enumeration; no channel above
substitutes for it.

## Actuation channels

| Channel | Signal | Peripheral class | Count | Safety-relevant | Source |
|---|---|---|---|---|---|
| Coffee thermoblock element switching | Mains AC load switch command; on/off vs. phase-controlled drive not established | Plain digital level (if on/off) or modulated output (if phase-controlled) — not established which | 1 | **Yes** — anything that switches a heater is in the safety-marked set | `reference-machine.md` § Heating and load; admissibility of controller-driven heater channels per `DEC-HEATER-DRIVE-GATED-BY-SUPERVISION` |
| Steam thermoblock element switching | Mains AC load switch command; on/off vs. phase-controlled drive not established | Plain digital level (if on/off) or modulated output (if phase-controlled) — not established which | 1 | **Yes** | Same as above |
| Coffee pump | Not established — original OEM drive scheme (on/off vs phase-controlled) not recorded | Plain digital level or modulated output — not established which | 1 | No | `reference-machine.md` § Already fitted, § Heating and load (Ulka EP5, 48 W) |
| Steam pump | Not established, same reason | Plain digital level or modulated output — not established which | 1 | No | `reference-machine.md` § Already fitted, § Heating and load (JYPC-4, 22 W) |
| Two-way solenoid valve, on the coffee thermoblock (`2T0607W`) | Not established — coil voltage class (mains vs low-voltage DC) not recorded | Plain digital level (on/off coil drive) — coil voltage class not established | 1 | No — not in the explicit safety set below, though whether this or the diverter valve vents on de-energisation is an open hypothesis (`reference-machine.md` § Protection) not resolved by this enumeration | `reference-machine.md` § Already fitted, § Protection |
| Three-way diverter solenoid valve, near the hot water arm (`3T0618W`) | Not established, same reason | Plain digital level (on/off coil drive) — coil voltage class not established | 1 | No | Same as above |
| Espresso "resistance to pour" gauge | Stepper drive | Modulated output (step/direction pulse train, or driver-IC interface — not established which) | 1 | No | `reference-machine.md` § Already fitted |
| Milk-temperature gauge | Stepper drive | Modulated output (step/direction pulse train, or driver-IC interface — not established which) | 1 | No | `reference-machine.md` § Already fitted |

**On the schematic tags.** `reference-machine.md`'s parts list places the three-way valve
(`3T0618W`) near the hot water arm and the two-way valve (`2T0607W`) on the thermoblock, while the
circuit schematic drives two channels labelled `COF VALVE` and `HOT VALVE`. Which schematic tag
drives which physical valve — and therefore which of the two is the brew-and-vent valve the
Protection section's fail-safe-vent hypothesis turns on — is explicitly not established in the
source. This enumeration names the two valves by part number and known location only, and does not
guess the tag pairing.

## Protective devices (safety-relevant, not controller-addressable)

These act on temperature directly, in series with heater power, with no controller involvement
and no firmware able to reach them (`DEC-HEATER-DRIVE-GATED-BY-SUPERVISION`). They are enumerated
here — not as controller I/O, since they present no signal a controller reads or drives — because
`OBL-PHYSICAL-CONFIGURATION-001.C1` and `.C2` require every safety-relevant component identifiable
and distinguished from those whose failure does not bear on safety, and a substitution surfacing
what depended on it (`.C5`) starts from this row existing at all.

| Component | Peripheral class | Count | Safety-relevant | Source |
|---|---|---|---|---|
| Coffee thermoblock thermostat (110 °C nominal, 95–110 °C ±3) | None — electromechanical, in series with coffee heater power | 1 | **Yes** | `reference-machine.md` § Protection |
| Steam thermochamber thermostat (200 °C ±5) | None — electromechanical, in series with steam heater power | 1 | **Yes** | `reference-machine.md` § Protection |
| Pump thermostat (110 °C) | None — electromechanical; which pump it protects is not established | 1 | **Yes** | `reference-machine.md` § Protection |
| Thermal fuse | None — electromechanical, one-shot | Fitted; exact count not established — only its mounting bracket is itemised in the parts list | **Yes** | `reference-machine.md` § Protection |
| Over-pressure relief, coffee side (`RELIEF ADAPTER BRASS`, fitted to the coffee thermoblock) | None — mechanical; setting and function not established | 1 | **Yes** — this is the device the coffee-side pressure hazard is meant to discharge through, even though what it does is not yet established | `reference-machine.md` § Protection |
| Over-pressure relief, espresso pump | None — mechanical; instruction manual claims the pump is "fitted with a pressure relief system," device/location/setting not established. May be internal to the pump, in which case it protects the pump and not the heated masses, and leaves with the pump if substituted | Not established | **Yes** | `reference-machine.md` § Protection |
| Over-pressure relief, steam side | **None documented anywhere.** Neither manufacturer document lists a relief part for the steam thermochamber; its 200 °C thermostat is a temperature device and does not discharge a pressure obligation | 0 — no component fitted | N/A — recorded as an absence, not a component, because `reference-machine.md` § Protection calls the steam-side pressure question "the largest unevidenced safety claim in the project" | `reference-machine.md` § Protection |

Resettable vs. one-shot is not established for any of the three thermostats above, and the thermal
fuse's rating is not established either — both are recorded as open in `reference-machine.md` §
Protection and are not resolved here; they are named so a later substitution has something to
check against, per `OBL-PHYSICAL-CONFIGURATION-001.C3`.

## Compute and operator-interface demand

**Control law and estimator.** The estimator reconstructs the states the control law needs from
whatever the sensing channels above provide, produces a running comparison between predicted and
observed measurements, and delivers output at the rate the control law consumes it
(`DEL-SIM-ESTIMATOR`) — recurring, real-time arithmetic on every control tick, not a one-shot cost.
This competes with the sensing and actuation channels above for the same core and the same tick
budget.

The rate itself is a figure the control loop already commits to, not an invented one: the step
interval is declared once, at `firmware/src/control/control.h`'s `CONTROL_STEP_INTERVAL_MS` (10 ms,
i.e. 100 Hz), with its basis recorded in `firmware/params/cadence.declaration` as `@estimated` —
chosen so the loop samples far faster than the brew path's thermal time constants, which are
seconds rather than milliseconds. That file is explicit that the figure is an estimate, not a
validated sufficiency claim: "whether ten milliseconds is sufficient for the disturbances this
machine actually sees is a question for the control-law work rather than a claim made here." So
every channel above, and the estimator's own arithmetic, is provisioned against a 100 Hz tick —
each channel must be sampled, and each actuation command issued, inside that budget — while whether
10 ms is itself the right interval stays open. What stays genuinely out of scope here, per this
criterion's own boundary, is measuring the control law's actual execution time on target hardware —
that is on-target work under a later phase, and is a different question from the declared cadence
cited above.

**Operator interface.** The machine is reached one of two ways, and this enumeration states what
each spends without choosing between them:

- A colour panel driven from the controller directly, which spends the controller's own display
  drive and memory bandwidth.
- A separate display board reached over a serial link, which spends two pins (the serial
  interface) and pushes the panel's own cost onto a second part instead of the controller.

## Channels not enumerated

These are recorded as explicitly *not* fitted and *not* decided, so a reader does not mistake their
absence from the tables above for an oversight:

| Channel | Status | Source |
|---|---|---|
| Brew-path pressure transducer | Not fitted, and no decision has added one. `REQ-MEASUREMENT-001.C7` requires brew pressure measured rather than inferred from pump drive and remains open — no `addresses`, `derives-from` or `justified-by` link reaches it in the graph. `DEC-PROFILE-COMMANDS-FLOW`'s rationale previously stated as a consequence that "pressure is still measured, on both paths"; that overclaim is corrected (`SOL-BREW-PRESSURE-RATIONALE-CORRECTED`) and is not resolved by inventing a row here | `reference-machine.md` § Already fitted ("Not fitted: pressure transducer on either path"); `DEC-STEAM-PRESSURE-SENSOR-ADDED` covers the steam side only |
| Current sensing | Not fitted, no decision has added it | `reference-machine.md` § Already fitted |
| Real-time clock | Not fitted, no decision has added it | `reference-machine.md` § Already fitted |

## What depends on this enumeration

Mirrors the pattern `reference-machine.md` uses for its own declared values: if a row above
changes — a channel is added, removed, or its signal type is established — the following need
re-reading.

| This enumeration | What depends on it |
|---|---|
| Every row (existence, count, safety marking) | `OBL-PHYSICAL-CONFIGURATION-001.C1`, `.C2`; `DEL-COMPONENT-SPECIFICATION.C1` |
| Compute and operator-interface demand | `DEL-COMPONENT-SPECIFICATION.C4` (headroom on the interfaces chosen) |
| Channels not enumerated | Any future decision that adds a brew-side pressure channel, current sensing, or an RTC |
