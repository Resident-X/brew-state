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

What accuracy, resolution and update rate each channel needs was out of scope when
`SOL-CONTROLLER-CHANNEL-ENUMERATION` first wrote these tables, because the work those figures had
to be derived against — sensing error carried in the commanded margin — had not landed. It has
since, and `SOL-CHANNEL-MEASUREMENT-FIGURES` adds the three columns to both tables below. Still out
of scope: choosing a specific part or controller for any channel; the cost of anything; wiring,
fitting or pin assignment; and the machine's plumbing, which `DEC-PLUMBING-LEFT-AS-BUILT` already
leaves as the factory built it.

## What the control needs of each channel

The three added columns carry no figure invented for this document. Each is read off something this
design has already declared and committed to, and each cell names which one it took and which
requirement criterion that figure serves. There are four admissible sources and no others:

- **The delivery bands**, `firmware/params/tolerance.declaration`. `brew-temperature-band` (1000
  milli-c, i.e. ±1 °C, `@document`) is how far water reaching the coffee may sit from what was
  commanded; `flow-departure-band` (200 milli-ml-s, i.e. ±0.2 mL/s, `@estimated`) is the smallest
  departure a delivery is judged against.
- **The declared sensing error**, accounted for in `firmware/params/control.declaration` and valued
  in the control sources that file accounts for. That declaration deliberately carries no numbers —
  each figure has one definition, in the source, and one account, in the declaration — so both sites
  are named here: `CONTROL_SENSING_ERROR_C` on the brew channel (value `2.0f` at
  `firmware/src/control/control.c:114`) and `STEAM_CONTROL_SENSING_ERROR_C` on the steam channel
  (value `2.0f` at `firmware/src/control/steam_control.c:63`), both `@estimated` at 2 °C — the
  accuracy class a block-mounted domestic sensor ordinarily carries — and each already the figure
  its own loop's commanded margin is widened by.
- **The states and bands the steam path is held at**,
  `firmware/params/steam_control.declaration`. `draw-pressure-floor-bar` (1000 milli-bar,
  `@estimated`) and `draw-pressure-ceiling-bar` (1400 milli-bar, `@estimated`) are the two edges of
  the pressure band a draw is held inside; `ready-pressure-bar` (900 milli-bar, `@estimated`) is the
  threshold the feed pump is withheld below, and `ready-temperature-c` (125000 milli-c,
  `@estimated`) the block temperature the loop holds while nothing is drawn.
- **The control loop's step interval**, `CONTROL_STEP_INTERVAL_MS` in
  `firmware/src/control/control.h` (10 ms, i.e. 100 Hz), accounted for as `step-interval-ms`
  `@estimated` in `firmware/params/cadence.declaration`. Every update rate below is stated as that
  interval or as a stated whole multiple of it; the full account of the interval is in *Compute and
  operator-interface demand*, further down.

What a part costs is not among them. The parent task, `DEL-COMPONENT-SPECIFICATION`, applies cost to
a specification already settled rather than letting it shape one, and
`SOL-CHANNEL-MEASUREMENT-FIGURES.C2` carries that ordering into these columns by making a figure
whose named basis is a price inadmissible. So a figure adopted because a part happened to offer it
at a price is the case this ordering exists to exclude.

Every cell carries the marking its source carries: where a declaration marks its own value
`@estimated`, so does the cell, because a figure copied across without that marking would read as
established, which is exactly the failure those declarations exist to prevent. Where no admissible
declared figure reaches a channel, the cell says so rather than carrying a plausible number, and
where the quantity does not apply to the channel at all — the accuracy of a two-state contact
closure — the cell says that instead. This is the discipline the Signal and Peripheral class
columns already apply, extended to three more columns. Naming, against each cell recorded as not
yet derivable, the work that will settle it is `DEL-COMPONENT-SPECIFICATION.C3` and is not
attempted here.

No row claims a multiple of the step interval greater than one. A slower sub-cadence for a channel
that plainly does not need reading a hundred times a second would be a figure this design has not
declared anywhere, and inventing one is the thing the ordering above rules out; so every channel is
provisioned at one control step, which is the budget the compute section below already reasons
against.

## Sensing channels

| Channel | Signal | Peripheral class | Count | Safety-relevant | Accuracy | Resolution | Update rate | Source |
|---|---|---|---|---|---|---|---|---|
| Coffee thermoblock temperature sensor | Not established — element type (NTC, RTD, thermocouple) is not recorded by either manufacturer document | Not established — follows from signal type above | 1 | No — controller does not sit in the protective chain (see Protective devices below) | ±2 °C, `@estimated` — `CONTROL_SENSING_ERROR_C`, accounted for in `firmware/params/control.declaration` and valued `2.0f` at `firmware/src/control/control.c:114`; the same figure this loop's own commanded margin is already widened by rather than a second one derived here, so the specification and the margin cannot drift apart while both go on reading as derived from the same requirement. Serves `REQ-MEASUREMENT-001.C1`, where error eats directly into the gap between commanded target and protection trip point, and stays the one figure `.C4` requires be carried in that margin. Displaced by a bench characterisation of the part actually fitted, or by a decision settling which sensor this design specifies | ±1 °C — the `brew-temperature-band` itself (1000 milli-c, `@document`, `firmware/params/tolerance.declaration`), which is the distance a delivery is judged against. Stated as the band itself rather than as some fraction of it, because no declared figure of this design fixes how far inside a band a reading has to resolve. Serves `REQ-MEASUREMENT-001.C2`: a channel coarser than the band shows the loop no departure until the delivery has already left it, which is the control law answering an excursion after it has run rather than acting inside the timescale the disturbance sets. The band is a statement about the drink taken from the extraction literature, not a measurement of this machine | Every control step — ×1 of the 10 ms (100 Hz) `step-interval-ms`, `@estimated` in `firmware/params/cadence.declaration`. Serves `REQ-MEASUREMENT-001.C2`. The interval was chosen so the loop samples far faster than the brew path's thermal constants; whether 10 ms is sufficient for the disturbances this machine actually sees is not established | `reference-machine.md` § Already fitted |
| Steam thermoblock temperature sensor | Not established, same reason | Not established | 1 | No | ±2 °C, `@estimated` — `STEAM_CONTROL_SENSING_ERROR_C`, accounted for in `firmware/params/control.declaration` and valued `2.0f` at `firmware/src/control/steam_control.c:63`; the figure the steam loop's own commanded margin is widened by, and its own declaration rather than a reading of the brew channel's, so either may be revised without the other silently moving with it. Serves `REQ-MEASUREMENT-001.C1` and `.C4` on this loop. Its own account marks it the optimistic side of the estimate: the same accuracy class assumed across a wider span than it was estimated over, and an NTC's accuracy ordinarily loosens toward the top of its range. Displaced by the same two things the brew figure is | Not established. The bands in `firmware/params/tolerance.declaration` hold what is delivered to the cup — the brew-temperature band holds water reaching the coffee — and none of them is a distance the steam block's own temperature is judged by. Nor does `firmware/params/steam_control.declaration` reach it: `ready-temperature-c` is the target the loop holds this block at while nothing is drawn, and a target fixes where a block sits rather than how finely a departure from it has to be separated. Its draw-pressure band could be carried into kelvin through the pressure-per-kelvin slope, but that slope is declared in `firmware/params/thermoblock.params`, which is not an admissible source here, and the band it would convert is asserted during a draw — which is precisely when that declaration says pressure parts from the temperature that would otherwise imply it. So no admissible declared figure reaches this cell and none is written | Every control step — ×1 of the 10 ms (100 Hz) `step-interval-ms`, `@estimated`. Serves `REQ-MEASUREMENT-001.C2`, on the same footing and with the same open sufficiency as the coffee block above | `reference-machine.md` § Already fitted |
| Steam wand temperature sensor (conduction disc, wand exterior) | Not established. Wired today to drive the milk-temperature gauge directly rather than read digitally, so an analogue element of some kind is implied, but its type and levels are not recorded | Not established | 1 | No | Not derivable, and deliberately not `STEAM_CONTROL_SENSING_ERROR_C`: that figure is declared for the steam block's own sensor, and borrowing it here would state an accuracy for a channel whose relation to the quantity it stands for is itself unestablished. `reference-machine.md` § Already fitted records this disc as a hypothesis — the lag and the relative weight of its two heat paths uncharacterised, and the O-ring's isolation not shown adequate to make this a usable milk-temperature reading at all | Not derivable, same reason. No declared band holds milk temperature: the drinking-temperature floor and ceiling in `firmware/params/tolerance.declaration` bound the drink served at the drinking point, not the exterior of a wand | Every control step — ×1 of the 10 ms (100 Hz) `step-interval-ms`, `@estimated`. Serves `REQ-MEASUREMENT-001.C2`, and applies from the point this disc is read digitally at all; it drives the milk-temperature gauge directly today (Signal, above). Sufficiency of the interval is not established | `reference-machine.md` § Already fitted |
| Water level sensor (tank) | Digital — magnet/reed contact closure | Plain digital level | 1 | No | Not applicable — a magnet/reed contact closure has two states and no continuous value to be wrong about. What could be wrong is the level the contact changes state at, which is a property of the part fitted; no declared figure of this design bounds it, and none is invented here | Not applicable — one bit, above or below the trip level. There is no finer distinction for the channel to resolve | Every control step — ×1 of the 10 ms (100 Hz) `step-interval-ms`, `@estimated`. Serves `REQ-MEASUREMENT-001.C2`: the loop declares one cadence and this channel is sampled inside it like every other. Sufficiency of the interval is not established | `reference-machine.md` § Already fitted |
| Flow meter (water path, suction line ahead of coffee pump) | Not established. Meters of this class commonly present a pulse train, but this fitted part's output is not confirmed against a datasheet | Not established, pending confirmation — a pulse output would want counter or timer capture | 1 | No | Not established. `firmware/params/control.declaration` declares a sensing error for the two temperature channels and none for flow, and the departure band below is a distance between commanded and delivered rate rather than a bound on the meter's own error, so it cannot be spent twice. No admissible declared figure reaches this cell | ±0.2 mL/s, `@estimated` — `flow-departure-band` (200 milli-ml-s) in `firmware/params/tolerance.declaration`, about three per cent of full pump scale, which `firmware/params/thermoblock.params` puts at 7.0 mL/s (`pump.flow_ml_per_s`, `7.0 ~ 0.6`, `@estimated`) — itself a judgement for the pump type rather than a reading of the fitted part, carried with a spread that wide because the same figure has to cover an open path and a puck at working pressure. Taken from the smallest departure a delivery is judged by rather than from what a vane meter conveniently provides, which is what `REQ-MEASUREMENT-001.C6` asks for. The band is an estimate placed between two figures neither of which has been measured — above the ripple a vane meter is expected to show on a vibratory pump, below the shortfall a choked puck is expected to produce — so it is what the design is working to, not a figure a bench has held | Every control step — ×1 of the 10 ms (100 Hz) `step-interval-ms`, `@estimated`. Serves `REQ-MEASUREMENT-001.C2`. Sufficiency of the interval is not established | `reference-machine.md` § Already fitted; siting decided by `DEC-FLOW-SENSED-UPSTREAM-OF-PUMP` |
| Control-knob microswitches | Digital — contact closure | Plain digital level | 2 (one per knob) | No | Not applicable — a contact closure has two states per knob and no continuous value to be wrong about | Not applicable — one bit per knob, closed or open | Every control step — ×1 of the 10 ms (100 Hz) `step-interval-ms`, `@estimated`. Serves `REQ-MEASUREMENT-001.C2`: the loop declares one cadence, and no declared figure of this design gives an operator input a slower one. Sufficiency of the interval is not established | `reference-machine.md` § Already fitted |
| Steam-path pressure transducer | Not established — not yet physically fitted; typical transducers of this class present a ratiometric analogue output but this part has not been selected | Not established, pending part selection — analogue conversion is the expected class | 1 | No — the pressure guarantee is deliberately not permitted to depend on anything noticing (`reference-machine.md` § Protection, "Pressure note") | ±0.2 bar, `@estimated` — half the 400 milli-bar between `draw-pressure-floor-bar` (1000 milli-bar) and `draw-pressure-ceiling-bar` (1400 milli-bar) in `firmware/params/steam_control.declaration`, both marked `@estimated` there and the marking carried across. The target the draw phase drives to is not declared as a figure of its own: that file states it as the middle of the band, where a loop holds with equal room either side, so an absolute error greater than half the span puts the state actually held outside the band the loop reads itself as holding. Serves `REQ-MEASUREMENT-001.C8` — pressure in the steam path measured rather than inferred from temperature — since a reading that cannot be trusted to sit inside the band it is taken to assert has stopped measuring the divergence that criterion exists for. The same file puts `ready-pressure-bar` 100 milli-bar below the floor, a tighter distance, but it is not one this channel is judged against as the design stands: the ready-holding phase drives to the block's own measured temperature, and no figure is written here for a use this design has not adopted. Displaced by a bench characterisation of the part actually fitted, or by a revision of the band | 0.4 bar, `@estimated` — the width of that same draw band, floor to ceiling, in `firmware/params/steam_control.declaration`. Stated as the band itself rather than as a fraction of it, on the footing the coffee block's temperature resolution above is stated on: no declared figure of this design fixes how far inside a band a reading has to resolve. Serves `REQ-MEASUREMENT-001.C2`: a channel coarser than the span shows the loop no departure until the pressure has already left the band, and a draw is the disturbance this loop has least room to wait out. The band is one the design can hold rather than one a drinker has asked for — that file is explicit that no bench has established what pressure a steamed jug is actually spoiled at | Every control step — ×1 of the 10 ms (100 Hz) `step-interval-ms`, `@estimated`. Serves `REQ-MEASUREMENT-001.C2`, and is what the channel is provisioned against once fitted. Sufficiency of the interval is not established | Added by `DEC-STEAM-PRESSURE-SENSOR-ADDED`; not yet fitted |

**Nothing measures the brew path downstream of the coffee block** (`reference-machine.md` §
Already fitted) — that limit is inherited unchanged into this enumeration; no channel above
substitutes for it.

## Actuation channels

| Channel | Signal | Peripheral class | Count | Safety-relevant | Accuracy | Resolution | Update rate | Source |
|---|---|---|---|---|---|---|---|---|
| Coffee thermoblock element switching | Mains AC load switch command; on/off vs. phase-controlled drive not established | Plain digital level (if on/off) or modulated output (if phase-controlled) — not established which | 1 | **Yes** — anything that switches a heater is in the safety-marked set | Not applicable as an on/off command, which has two states and no continuous value to be wrong about. If the drive turns out to be phase-controlled instead — Signal, above, does not establish which — how far a commanded fraction may sit from the fraction delivered is not established: `firmware/params/control.declaration` declares sensing error on the two temperature channels and nothing about an actuation channel | Not applicable on the same split — the command distinguishes energised from not. If phase-controlled, the step a commanded fraction has to distinguish is not established: the bands in `firmware/params/tolerance.declaration` hold what is delivered to the cup, not what is commanded of a load | Every control step — ×1 of the 10 ms (100 Hz) `step-interval-ms`, `@estimated` in `firmware/params/cadence.declaration`. The command is issued inside the same step budget the sensing channels are sampled in, which is what `REQ-MEASUREMENT-001.C2` asks of a control law acting within the disturbance timescale. Whether 10 ms is sufficient for the disturbances this machine actually sees is not established | `reference-machine.md` § Heating and load; admissibility of controller-driven heater channels per `DEC-HEATER-DRIVE-GATED-BY-SUPERVISION` |
| Steam thermoblock element switching | Mains AC load switch command; on/off vs. phase-controlled drive not established | Plain digital level (if on/off) or modulated output (if phase-controlled) — not established which | 1 | **Yes** | Not applicable, or not established if phase-controlled, on exactly the split the coffee element above carries and for the same absent source | Not applicable, or not established if phase-controlled, same split as above. `firmware/params/steam_control.declaration` states this loop's gains and feedforward in permille of the steam element, but that is the unit its own figures are written in rather than a declared bound on how finely the drive has to be commanded | Every control step — ×1 of the 10 ms (100 Hz) `step-interval-ms`, `@estimated`. Serves `REQ-MEASUREMENT-001.C2` on the same footing as the coffee element, with the same open sufficiency | Same as above |
| Coffee pump | Not established — original OEM drive scheme (on/off vs phase-controlled) not recorded | Plain digital level or modulated output — not established which | 1 | No | Not established. No declared figure bounds how far the flow a commanded pump level actually produces sits from the level commanded: `firmware/params/control.declaration` declares sensing error on the two temperature channels only, and its own account of `CONTROL_DRAWN_PERMILLE_PER_K_PER_PUMP_PERMILLE` records the pump's flow-versus-level relation as an assumption no measurement has established | Fine enough to command inside the ±0.2 mL/s `flow-departure-band` (`firmware/params/tolerance.declaration`, `@estimated`), which is the band a delivery is judged by: a command step coarser than the band the loop is holding inside cannot be placed inside it. This is an actuation-side reading of that band rather than a measurement figure, and it names no requirement criterion of its own — `REQ-MEASUREMENT-001.C6` bounds what the flow *meter* resolves, not what a pump command must, and reading it as a bound on command granularity would claim more than it says. What that band is in permille of pump scale is not derivable here: the conversion runs through the flow-versus-level relation the control declaration records as unestablished | Every control step — ×1 of the 10 ms (100 Hz) `step-interval-ms`, `@estimated`. Serves `REQ-MEASUREMENT-001.C2`. Sufficiency of the interval is not established | `reference-machine.md` § Already fitted, § Heating and load (Ulka EP5, 48 W) |
| Steam pump | Not established, same reason | Plain digital level or modulated output — not established which | 1 | No | Not established, on the footing the coffee pump above is and with one source fewer: no band in `firmware/params/tolerance.declaration` holds the steam path's feed rate at all | Not established — the derivation available to the coffee pump above is not available here, because no declared band is a distance the steam side's feed rate is judged by. `firmware/params/steam_control.declaration` caps the level settled feed is commanded at (`sustainable-feed-rate`, 67 permille, `@estimated`) and states the interval it rises over, but a cap is a level rather than a distance, and neither fixes the step a command has to distinguish | Every control step — ×1 of the 10 ms (100 Hz) `step-interval-ms`, `@estimated`. Serves `REQ-MEASUREMENT-001.C2`. Sufficiency of the interval is not established | `reference-machine.md` § Already fitted, § Heating and load (JYPC-4, 22 W) |
| Two-way solenoid valve, on the coffee thermoblock (`2T0607W`) | Not established — coil voltage class (mains vs low-voltage DC) not recorded | Plain digital level (on/off coil drive) — coil voltage class not established | 1 | No — not in the explicit safety set below, though whether this or the diverter valve vents on de-energisation is an open hypothesis (`reference-machine.md` § Protection) not resolved by this enumeration | Not applicable — an on/off coil drive has two states and no continuous value to be wrong about | Not applicable — the command distinguishes energised from not, and there is no finer distinction to resolve | Every control step — ×1 of the 10 ms (100 Hz) `step-interval-ms`, `@estimated`. Serves `REQ-MEASUREMENT-001.C2`: the loop declares one cadence and this coil is commanded inside it like every other channel. Sufficiency of the interval is not established | `reference-machine.md` § Already fitted, § Protection |
| Three-way diverter solenoid valve, near the hot water arm (`3T0618W`) | Not established, same reason | Plain digital level (on/off coil drive) — coil voltage class not established | 1 | No | Not applicable, same reason as the two-way valve above | Not applicable, same reason | Every control step — ×1 of the 10 ms (100 Hz) `step-interval-ms`, `@estimated`. Serves `REQ-MEASUREMENT-001.C2`, same footing as the two-way valve above | Same as above |
| Espresso "resistance to pour" gauge | Stepper drive | Modulated output (step/direction pulse train, or driver-IC interface — not established which) | 1 | No | Not established — no declared figure of this design states how closely an operator-facing indication must follow the quantity it shows. The bands in `firmware/params/tolerance.declaration` hold the drink rather than the needle, and `firmware/params/control.declaration` declares no error for an actuation channel | Not established, same reason. A stepper's own step size is a property of the part fitted, and choosing a part is out of scope here | Every control step — ×1 of the 10 ms (100 Hz) `step-interval-ms`, `@estimated`. Serves `REQ-MEASUREMENT-001.C2`: this is the budget a step command is issued inside, not a claim about how fast a needle needs to move. Sufficiency of the interval is not established | `reference-machine.md` § Already fitted |
| Milk-temperature gauge | Stepper drive | Modulated output (step/direction pulse train, or driver-IC interface — not established which) | 1 | No | Not established, same reason as the espresso gauge above, and doubly so here: the quantity this needle shows is reached through the wand disc, whose own accuracy the sensing table records as not derivable | Not established, same reason | Every control step — ×1 of the 10 ms (100 Hz) `step-interval-ms`, `@estimated`. Serves `REQ-MEASUREMENT-001.C2`, and applies from the point a controller drives this gauge at all; the wand disc drives it directly today. Sufficiency of the interval is not established | `reference-machine.md` § Already fitted |

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
| Every row's accuracy, resolution and update rate | `DEL-COMPONENT-SPECIFICATION.C2`; `REQ-MEASUREMENT-001.C1`, `.C2`, `.C6`, `.C8`. These cells hold no figure of their own: a change to any of the four sources they read from — the delivery bands in `firmware/params/tolerance.declaration`, the declared sensing error accounted for in `firmware/params/control.declaration` and defined in the control sources, the steam path's declared states and bands in `firmware/params/steam_control.declaration`, the step interval accounted for in `firmware/params/cadence.declaration` — moves every cell that took its figure from it |
| Compute and operator-interface demand | `DEL-COMPONENT-SPECIFICATION.C4` (headroom on the interfaces chosen) |
| Channels not enumerated | Any future decision that adds a brew-side pressure channel, current sensing, or an RTC |
