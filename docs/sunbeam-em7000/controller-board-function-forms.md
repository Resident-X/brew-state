# Controller boards: the form of each function

**This file is local, like `controller-board-design-constraints.md`, which it sits beside.** It records, for every function the replacement electronics serve, whether it is a circuit the project designs or a module it buys, and why. An adopter fitting a different machine, or the same machine on a different supply, replaces this file along with the declaration it is derived from.

**This is a derived view, and its sources govern.** Every figure is read off a source named beside it: a manufacturer's datasheet cited by address and the revision or date it carries, with the day it was read; a row of the component specification or the constraints record; an owner statement with its date; or a decision in the graph. Where this file and one of those disagree, the source is right and this file is corrected. Grades are those of `controller-board-design-constraints.md` § Evidence grades. Every datasheet figure below is graded **published unverified, read at source**: it is the manufacturer's published claim, read in the manufacturer's own document on 2026-10-23, and established on no part in hand (nothing has been bought: `controller-board-design-constraints.md` § Purchases ahead of verification, owner statement 2026-10-15).

**What this record selects and what it does not.** It decides each function's form. For every part that forms a mains barrier, and for the steam-path transducer, it states what the part must carry and proves the form feasible with one candidate whose figures are sourced. It does not select the part that is fitted: the design task for the board or assembly that carries a part does, against the targets here, from the board manufacturer's catalogue where there is one (`DEL-HW-PARTITION-AND-FEASIBILITY.C5`). It does not select the microcontroller part, which `DEL-HW-PARTITION-AND-FEASIBILITY.C7` selects before any board's pin allocation. Nothing in `controller-design/` is selected by this record: that folder is the earlier design, read as input and history.

## What each form is weighed against

| Input | Value | Source |
|---|---|---|
| Declared spend | 250 USD, covering what the retrofit adds | `component-specification.md` § The component list |
| Nothing already bought to weigh as an option | No sample, instrument or earlier-design part was bought | `controller-board-design-constraints.md` § Purchases ahead of verification (owner statement, 2026-10-15) and § Carried-forward module properties, *None of its parts were bought* (owner statement, 2026-10-13) |
| Supply the barriers and switches are rated for | 216–253 V AC, 50 Hz nominal; 253 V rms and 358 V peak at the top | `controller-board-design-constraints.md` § Supply |
| Air temperature parts are graded to | 70 °C, **project assumption, to replace**; the room-temperature span's top (35 °C) is an owner statement and the 35 K rise is unmeasured; bring-up measures it | `controller-board-design-constraints.md` § Enclosure air temperature; `DEL-HW-BRING-UP.C13` |
| Height above a board for a part | 28 mm across the board, an owner allowance resting on the earlier supply module's top; 23.4 mm within about 2 mm of a wall | `reference-machine.md` § Controller enclosure as found, *Across the lid, and the ceiling to work to* |
| Board maker | JLCPCB, assembling from its public catalogue, Basic and Preferred parts first | `DEC-BOARD-MANUFACTURER-JLCPCB`; `docs/board-manufacturer-jlcpcb.md` |
| What the retained devices impose and what the earlier design's modules supplied unstated | The carried-forward constraints named *Mains barrier*, *Held off undriven*, *Rated for the supply*, *Leakage current* and *Interface between replaced parts*, and each module's rows | `controller-board-design-constraints.md` § Carried-forward module properties |

## The record of forms

Each row names the component specification's own row for the channel (`component-specification.md` § What each channel requires), whose *Must satisfy* and *Capability floor already achieved* columns are the specification the form is judged against; they are cited and not restated. A reason names what about the function makes the form better. *Reference* is a published design the form follows, or where one was looked for and not found. *Properties* are the carried-forward rows (`controller-board-design-constraints.md` § Carried-forward module properties) the form is shown to meet, by a sourced figure where a part is named and otherwise by the requirement the design task for the board is held to. *Firmware* is the effect on the firmware already written, at the hardware seam (`firmware/include/hw_interface.h`, `firmware/include/machine_actuation.h`) and the target build (`firmware/platformio.ini`, environment on `genericSTM32F407VGT6`).

Source numbers (S1…) are in § Sources read. Prices and stock are in § Availability and price.

### Controller

| | |
|---|---|
| Row | *Controller* |
| Form | **Designed** onto the controller board and assembled by the board manufacturer. The earlier design's WeAct MiniSTM32H743 module is **not kept**. The part is expected within the STM32F4 family the target build nominates; which part is selected by `DEL-HW-PARTITION-AND-FEASIBILITY.C7` |
| Reason | Every module in the catalogue for this channel is a development board (`controller-board-design-constraints.md` § Manufacturer stock and price, per channel, *Controller*: two boards, wave-soldered by hand, and no stocked candidate for the earlier module), and the project's boards are designed for this project rather than hand-wired around a bought controller module (`DEL-CONTROLLER-HARDWARE`). A bare microcontroller in the catalogue costs 4.93 USD to 6.15 USD for the F407 parts against 6.51 USD and 8.14 USD for the two F407 boards, and it is placed by machine. A board's usable pins are fewer than the part's because it spends pins on its own functions (`component-specification.md` § What this assessment does not establish); a part on the controller board spends none |
| Hardware already bought | None (owner statements above), so none is weighed |
| Reference | ST AN4488, *Getting started with STM32F4xxxx MCU hardware development* (R3): power decoupling, reset, boot and clock for the F4 family |
| Properties | *Controller module* rows: **Isolation** none, so none to carry; **Output behaviour from power-up** and **supply rising, failing or absent** and **Default states: what runs at reset**: stated as *Held off undriven* and the reset-strap constraint, which the board design task meets in its schematic against the selected part's datasheet; the rest are set aside as interfaces between replaced parts |
| Firmware | The seam is vendor-free (`firmware/include/hw_interface.h`) and takes a level per actuation channel, so the form changes nothing above it. The target build names the F4 family; the form needs no H7 target, because the H743 module is dropped. If the part `.C7` selects is in the nominated family the target build is unaffected; if not, `.C7` states the effect and supersedes the nomination |

### Coffee element switching and steam element switching

| | |
|---|---|
| Rows | *Coffee element switching*, *Steam element switching* |
| Form | **Bought**: one zero-cross solid-state relay per element, in one replaceable package, bolted with thermal paste to a heatsink on the machine's wall. The relay and its heatsink are a device the retrofit adds; § Parts off the boards gives the drop-in and thermal judgement. Proving candidate: Carlo Gavazzi RA2425-D06 (S3) |
| Reason | The floor, the Hongfa `HF3FD/012HST` relay, cannot be commanded every half-cycle (`component-specification.md`, the row's *Commanded how often*), which is the requirement that retires it. The circuit the project would otherwise build is an opto-triac, a triac and a snubber, with a heatsink and its mounting designed in. A bought relay is that circuit in one package with the isolation rating published by its maker (4000 VACrms input to output, S3), the zero-cross behaviour published (S3), and the heatsink sized from the maker's own table of heatsink resistance against load and ambient (S3), rather than from a device-class figure. **It is not cheaper in parts.** The candidate is 69.00 USD each at one US distributor (§ Availability and price), 138 USD for two, 55 % of the declared spend, against about 1.3 USD each for the designed equivalent from the catalogue rows already read (`controller-board-design-constraints.md` § Manufacturer stock and price, per channel, *Coffee and steam element switching*: C9100 0.8416 USD, C77950 0.2165 USD, snubber capacitor C105759 0.0467 USD and resistor C2930459 0.027 USD, C361579 0.1463 USD). The form is the operator's choice (the solution text), recorded here with that cost shown, as `REQ-COST-DISCIPLINE-001.C2` and `.C4` ask of a departure on a channel whose failure is a hazard |
| Hardware already bought | None |
| Reference | Carlo Gavazzi's installation instructions for the RA family (S4) and the heatsink table in S3. No published project reference design for a retrofit espresso machine was found: looked in the maker's documents and in the search made on 2026-10-23 for espresso-machine heater switching with a panel-mount SSR, whose results were forum posts and listings |
| Properties | See § The heater switch against the carried-forward properties |
| Firmware | None at the seam: the heater channels keep taking a level. The layer below the seam decides once per half-cycle (`DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM`); § The heater switch and the per-half-cycle decision says how the relay's own zero-cross turn-on sits under that |

### Heater gate drive, both channels

| | |
|---|---|
| Row | *Heater gate drive, both channels* |
| Form | **Designed**: a low-side transistor stage on the controller board, one per element, from the 5 V rail to the relay's control input, with a pull-down at its gate. The earlier design's ULN2003A breakout is **not kept** |
| Reason | The relay's control input needs at least 3 VDC to pick up and has a 1.5 kΩ input impedance (S3). A 3.3 V controller pin guarantees `VOH` of `VDD` − 0.4 V, about 2.9 V (`component-specification.md` § What the candidate provides, *Output logic level*), which is below the 3 V pick-up, so a pin cannot drive the input directly. One small transistor per channel, from the 5 V rail, clears it and holds the relay off with its gate pulled down. The breakout adds an unconfirmed jumper header and indicator LEDs (`controller-board-design-constraints.md` § Heater switch drive) for a function one transistor serves |
| Hardware already bought | None |
| Reference | None found. Looked in: the Carlo Gavazzi datasheet and installation instructions (S3, S4), which give the input range and no drive circuit, and onsemi AND8116/D (R4), which gives a low-side bipolar driver for relay coils, the same stage |
| Properties | *Heater switch drive* rows: **Isolation** none, the barrier being the relay's (§ Barrier parts); **Default states**: *Held off undriven*, met by the gate pull-down and by the 5 V rail's absence leaving the input unpowered; output rating and thresholds set aside as an interface between replaced parts |
| Firmware | None |

### Coffee pump switching and steam pump switching

| | |
|---|---|
| Rows | *Coffee pump switching*, *Steam pump switching* |
| Form | **Designed**, on the mains board: a random-phase opto-triac driving a snubberless triac, one pair per pump. The RBdimmer modules are **not kept**. Proving candidates: onsemi MOC3052M (S5) and WeEn BTA204S-600B (S7) |
| Reason | The pump keeps the phase-capable arrangement the original controller gave it, commandable both each half-cycle and by phase angle within a half-cycle (`DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM`; the row's floor, the OEM `MOC3021` into a triac). A random-phase opto-triac can fire at any point in the half-cycle, which a zero-cross part cannot, so the form serves whichever modulation the ripple simulation selects. The RBdimmer is not in the catalogue (`controller-board-design-constraints.md`, *Phase-control dimmer module*: no stocked candidate), publishes no isolation voltage and no pulled-down input, and the triac it fits is not established (§ Carried-forward module properties, *Pump drive modules*); the discrete pair costs 0.59 USD + 0.85 USD per pump from the catalogue and every figure of it is in a datasheet. The triac is a snubberless part, so a pump's inductive turn-off needs no snubber across the triac, which would be a path around it |
| Hardware already bought | None |
| Reference | onsemi AN-3003 (R1, Rev. 4.07, 10/6/06), whose *Logic to Inductive Load Interface* figure is this circuit |
| Properties | **Mains barrier**: opto-triac `VISO` 4170 VACRMS for one minute (S5); target § Barrier parts. **Rated for the supply**: blocking 600 V against 358 V peak; the triac carries 4 A rms against 0.46 A and 0.19 A (S5, S7). **Turning off an inductive load**: the triac's published commutating rate is `dIcom/dt` at least 6 A/ms at 125 °C, 400 V, 4 A rms, snubberless (S7); the pump's own rate at its current zero is 2π × 50 Hz × (0.46 A × √2) = 204 A/s = 0.20 A/ms, thirty times below it (arithmetic on the sizing current of § Supply budget, at the 50 Hz nominal). **Held off undriven**: the opto-triac conducts only with LED current, peak blocking current at most 100 nA at 600 V with none (S5); the board's LED drive stage is a low-side stage with its input pulled down. The 400 V opto-triac of the earlier design's family, MOC3021M (S6), blocks 400 V against 358 V peak, an 11 % margin, which is why the proving candidate is the 600 V part. **Failure**: § Output failure states, *Both pump drives*, is the interlock's, not the drive's. The branch fuse's rating is the board task's mark |
| Firmware | None: the pump channels keep taking a level, and the pump's firing instant is below the seam (the actuation table maps each channel to a timer output, `firmware/src/hw/stm32/hw_stm32.c`) |

### Two-way valve switching and three-way valve switching

| | |
|---|---|
| Rows | *Two-way valve switching*, *Three-way valve switching* |
| Form | **Designed**, on the mains board: one relay per valve, a low-side coil driver transistor and a flyback diode. The Songle four-channel module and the two RC-and-varistor snubber modules are **not kept**. No snubber is fitted across the contacts. Proving candidate: Hongfa HF115F-Q (S8) |
| Reason | A valve is switched once per delivery and nothing requires it to modulate, so a relay, whose open state is the de-energised state, is the form that fails into the state the row requires without a part that can fail short. The Songle module is not in the catalogue and its polarity and default state are unconfirmed (§ Carried-forward module properties, *Valve relay module and its driver*). The snubber modules put 7.2–8.6 mA through an open contact and leave 18–51 V on the coil, and a failed varistor holds the coil energised, both of which that section sets aside as not to be inherited. The relay of the floor and of the earlier design, Hongfa HF32FA-G, carries a maximum switching voltage of **250 VAC** (S9), below the 253 V top of the declared span, so it does not meet *Rated for the supply*; the HF115F-Q's is 440 VAC and its contact rating 20 A 250 VAC, UL 20 A 277 VAC (S8), at 3.21 USD against 1.67 USD for the HF32FA-G. A different relay may be fitted once its own datasheet's voltage rating is sourced and meets the target |
| Hardware already bought | None |
| Reference | TE Connectivity's coil-drive application note 13C9132 and onsemi AND8116/D (R4) for the coil driver and its flyback diode, which TE's note weighs against release time (a diode across the coil slows contact release) so the clamp across the coil is the board task's choice. Both located 2026-10-23 and not read in full |
| Properties | **Mains barrier**: coil to contacts 5000 VAC for one minute, surge 10 kV 1.2/50 µs, creepage over 8 mm (S8). **Rated for the supply**: contacts rated against 253 V and the coil currents of § Supply budget as above. **Held off undriven**: a relay with its coil unenergised is open; its drive is a low-side transistor with its base or gate pulled down, so a floating or reset-state line leaves it off, the property the Songle module left unestablished. **Output failure**: the de-energised state is § Output failure states, *Both valve coils*. Coil voltage: the datasheet offers 5 V (62 Ω) to 60 V coils (S8); the coil's voltage follows the rail budget, the board task's |
| Firmware | None |

### Supply-timing front end

| | |
|---|---|
| Row | *Supply-timing front end* |
| Form | **Designed**: one AC-input optocoupler, two antiparallel emitters, fed from the line through a series resistor, read as an edge input; one front end serves the timing of every channel and replaces the RBdimmer's zero-cross output. Candidate: Lite-On LTV-814 (S10) |
| Reason | The floor, a `PC817` on a half-wave feed, reports one crossing per cycle, and a scheme that resolves half-cycles cannot be timed against a reference reporting every second one (`DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM`; the row's *What it presents*). An AC-input optocoupler conducts on both half-cycles with no rectifier, so it is the smallest circuit with the property, and it is the part class the OEM already uses on its mains-sensing inputs. The RBdimmer's zero-cross output is unspecified in type, polarity and width (§ Carried-forward module properties, *Pump drive modules*) |
| Hardware already bought | None |
| Reference | None found for a both-crossings AC-input optocoupler front end in a manufacturer's application note. Looked in: Microchip, TI and onsemi application notes by search on 2026-10-23, whose results were a Microchip single-edge zero-crossing note, TI SDAA140 (a rectifier-and-clamp circuit, not an optocoupler), patents and a forum thread, none a published design for both crossings. The LTV-814's own datasheet (S10) is the basis: its emitters are antiparallel (`IF` ± in every row) |
| Properties | **Mains barrier**: 5000 Vrms for one minute (S10); target § Barrier parts. Zero-cross output: one edge per half-cycle, both crossings, by the part's antiparallel emitters; its type, polarity and width are the board's own design, which is why none is read from a module. Phase accuracy: not established and not bounded, as the row says and `DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM` declines to invent; the detection threshold delays an edge by an amount the series resistor sets, which the firmware reads live rather than relies on |
| Firmware | The front end is an input to the layer below the seam; the seam is unchanged. It reads the supply's period live (`DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM`) |

### Coffee, steam and wand temperature sensing

| | |
|---|---|
| Row | *Coffee, steam and wand temperature sensing* |
| Form | **Designed**, on the controller board: a resistor divider and filter capacitor per channel into a conversion input, with the divider supplied from the converter's own supply. The sensing elements stay off the board, as fitted; whether they are retained is left open by `DEC-DEVICE-RETENTION-BOUNDARY` and is not decided here |
| Reason | The elements are fitted NTC resistances; a divider and capacitor is all the function needs, from three passives per channel that the catalogue stocks as Basic parts at 0.0022 USD (`controller-board-design-constraints.md` § Manufacturer stock and price, per channel, *Coffee, steam and wand temperature sensing*). No bought module is a form of this channel. The divider resistor's tolerance is the board task's, set by the ±2 °C the record holds (§ Sensing accuracy) |
| Hardware already bought | The fitted elements, retained by default (the row's floor) |
| Reference | TI SBAA338, *Monitoring NTC thermistor circuit with single-ended ADC* (R2): a ratiometric divider into one ADC input, with the divider powered from the converter's supply |
| Properties | None carried: the machine's own probes are not a module of the earlier design (`controller-board-design-constraints.md` § Which rows are modules) |
| Firmware | None |

### Flow sensing

| | |
|---|---|
| Row | *Flow sensing* |
| Form | **Designed**: a pull-up to the 5 V rail and a Schmitt-trigger buffer to the controller's capture input |
| Reason | The meter's output is a pulse train held up to 5 V on the original board by 2 kΩ (`connector-pinouts.md`); one resistor and one single-gate buffer (0.07 USD, `controller-board-design-constraints.md`, *Flow sensing*) take it to a 3.3 V input. Whether the output is open-drain or push-pull is not yet read, so the pull-up is fitted and a push-pull output tolerates it |
| Hardware already bought | The fitted meter, retained (the row's floor) |
| Reference | None found as a manufacturer note for a Hall flow meter into a 3.3 V input. Looked in: manufacturer notes and the TI and community pages returned by search on 2026-10-23, which gave a single-gate Schmitt buffer as the single-chip form, in a thread and not a design |
| Properties | None carried |
| Firmware | None: one capture channel, as the enumeration states |

### Steam-path pressure sensing

| | |
|---|---|
| Row | *Steam-path pressure sensing* |
| Form | **Bought**: a pressure transducer with a ratiometric 0.5–4.5 V output plumbed into the steam path, read through a conversion input with divider conditioning on the controller board. § The steam-path transducer holds the targets and the candidate |
| Reason | No stocked transducer exists in the catalogue (`controller-board-design-constraints.md`, *Steam-path pressure sensing*), and a transducer that meets steam under 5 bar gauge is a wetted, pressure-rated part that cannot be designed from board components. A ratiometric analogue output reads on a conversion input the enumeration already has (`component-specification.md` § What the enumeration demands, *Analogue conversion inputs*), against the earlier design's I²C part whose address and conversion scheme no requirement fixes |
| Hardware already bought | None |
| Reference | None found as a published design for a steam transducer on a flash generator. Looked in: manufacturer datasheets for the candidates of § The steam-path transducer, which are component documents |
| Properties | *Pressure sensors* rows: **Isolation** from the water path, § Barrier parts; **Accuracy** ±0.775 bar and the binding ±0.25 bar, § The steam-path transducer; **Overload and burst**, § The steam-path transducer; the rest set aside |
| Firmware | The seam already enumerates the steam-pressure channel (`HW_SENSOR_STEAM_PRESSURE`); the analogue read does not change it |

### Gauge drive, both gauges

| | |
|---|---|
| Row | *Gauge drive, both gauges* |
| Form | **Designed**: a buffer with TTL-level inputs and 5 V outputs between the controller and the five lines to the retained `VID66-08` driver |
| Reason | Five lines must clear the driver's 3.15 V input-high threshold, which a 3.3 V pin's guaranteed `VOH` (about 2.9 V) does not (the row, and `component-specification.md` § What the candidate provides). The row's two closures are five level shifters or a bench measurement of `VOH`. A buffer powered from the 5 V rail drives 5 V and clears the threshold outright, a guarantee where a measurement would be a typical; two quad buffers or one octal cost 0.23–0.51 USD, and the board needs no instrument to close the row |
| Hardware already bought | The gauge assembly with its driver, retained |
| Reference | None found beyond the buffer's own datasheet: the earlier design chose the 74HCT541 for this (`controller-design/control-system-bom.csv`), and TI's SN74HCT541 datasheet gives its TTL-level inputs and 5 V outputs. Looked in: the datasheets of the catalogue's candidates |
| Properties | **Held off undriven**: pull-downs at the buffer's inputs, so the driver's reset and direction lines stay off while the controller is in reset |
| Firmware | None |

### Heater mains-presence confirm

| | |
|---|---|
| Row | *Heater mains-presence confirm, both elements* |
| Form | **Designed**: the OEM's arrangement, an AC-input optocoupler through a 120 kΩ 1 W resistor on each element. The earlier design's energy meters are **not kept**. Candidate: Lite-On LTV-814 (S10) |
| Reason | The row's floor, the OEM `LTV814` through 120 kΩ 1 W, is fitted and working, so it is the reused and commodity default (`REQ-COST-DISCIPLINE-001.C1`), at 0.14 USD per optocoupler. The meters were the working design's choice, no requirement or decision needs them, and their serial pins sit at mains potential (`controller-board-design-constraints.md`, *Energy meters*) |
| Hardware already bought | None |
| Reference | The OEM circuit itself (`component-specification.md`, the row's floor), read from the service manual's circuit diagram |
| Properties | **Mains barrier**: 5000 Vrms (S10); the row's *reinforced isolation* is the basis's to judge (§ Barrier parts). 120 kΩ at 253 V dissipates 253² / 120 000 = 0.53 W against 1 W. The heater switch's off-state leakage against this input is § The heater switch's leakage against the mains-presence confirm |
| Firmware | None: two plain digital inputs, as the enumeration states |

### Low-water indication, visual

| | |
|---|---|
| Row | *Low-water indication, visual* |
| Form | **Designed**: one small-signal transistor sinking the indicator's cathode on the controller board |
| Reason | The indicator is retained on the gauge assembly and its anode rail is the panel's gated rail (the row); a transistor at 0.0178 USD (Basic, `controller-board-design-constraints.md`, *Low-water indication, visual*) is the whole function |
| Hardware already bought | The fitted indicator, retained |
| Reference | None found. Looked in: the same manufacturer notes searched for the relay and buffer stages, none giving an indicator sink as a separate design |
| Properties | **Held off undriven**: the transistor's gate pulled down |
| Firmware | None |

### Operator panel: keys, indicators, buzzer

| | |
|---|---|
| Row | *Operator panel — keys, indicators, buzzer* |
| Form | **Designed**: the controller serves the panel's seven lines directly: a P-channel switch on the anode rail, pull-ups on the five key lines, a switch for the buzzer. No panel controller is retained or spoken to |
| Reason | The panel is a passive assembly with no controller on it, so the replacement serves its channels directly and retaining a panel board is not an option (`DEC-U8-BOARD-RETENTION-UNVERIFIED`; `connector-pinouts.md`). The row's seven lines are three transistors and five resistors, all Basic parts (`controller-board-design-constraints.md`, *Operator panel — keys, indicators, buzzer*) |
| Hardware already bought | The OEM panel board, retained as a passive assembly |
| Reference | None found. Looked in: the panel's own wiring record (`connector-pinouts.md`), the only description of this circuit |
| Properties | **Held off undriven** on the gated rail and the buzzer |
| Firmware | None |

### Low-voltage supply (the logic supply)

| | |
|---|---|
| Row | *Low-voltage supply* |
| Form | **Bought**: a certified, encapsulated AC-DC module soldered on the controller board. The hand-cut carrier board is **not kept**, and neither is the Mean Well IRM-10-5 as the proving candidate. Proving candidate: Mean Well IRM-20-5 (S1), 5 V 4 A |
| Reason | Mains isolation is a barrier, and a module that carries its maker's published withstand voltage and safety approvals gives it where a designed converter needs a transformer whose winding insulation the catalogue does not state (`controller-board-design-constraints.md`, *Low-voltage supply*: no stocked candidate, 16 in-stock `EE16` results none stating a rating). The module is rated with margin over the logic-supply budget: at 70 °C the IRM-20-5 carries 50 % of 4 A, 2 A (the derating curve of S1, read off the chart, the line shared by the 3.3 V and 5 V models, which falls to 50 % at 70 °C; approximate), where the IRM-10-5 carries 50 % of 2 A, 1 A at the same temperature (S2), against the earlier design's 0.66 to 0.86 A worst case for the loads it chose (`controller-design/system-design.md` § 8. Power, a scale only: the rail budget is the board task's mark). That is 2.3 times the 0.86 A against 1.16 times, the margin `controller-board-design-constraints.md` § Enclosure air temperature calls thin. The cost is 1.16 USD more (§ Availability and price) and 2.5 mm more height (24 mm against 21.5 mm), within the 28 mm ceiling and not within 23.4 mm of a wall |
| Hardware already bought | None |
| Reference | Mean Well's installation manual for the open-frame and PCB families that include IRM (R5, 2023.11.21), and the IRM-20 datasheet's block diagram and derating curve (S1). The datasheet points to a further installation manual (`http://www.meanwell.com/manual.html`) that was not read |
| Properties | *Logic supply* rows: **Isolation**, Class II and no earth pin, withstand voltage 4.2 kVac input to output and 100 MΩ at 500 VDC, § Barrier parts (S1); **Leakage**, under 0.25 mA at 277 V AC, set aside; **Overload**, hiccup at 115–160 % of rated power (S1), the limit's value is the board task's mark; **Input range** 85–305 V AC, 47–440 Hz, which covers 216–253 V at 50 Hz (S1); **Inrush**, cold start 40 A typical at 230 V (S1), whose feed protection is the board task's mark; **Default states**: no output unpowered. The carrier's own gaps and fuse were choices of the earlier design and are set aside |
| Firmware | None |

### Wiring, connectors, mains-rated terminals

| | |
|---|---|
| Row | *Wiring, connectors, mains-rated terminals* |
| Form | **Designed**: the headers, terminals and fuse holders each board carries are designed onto it, one per recorded retained connector, by the design task for the board that carries the connector |
| Reason | The retained harnesses are reused as found, and the connector each ends in is recorded (`connector-pinouts.md`). The matching header is a catalogue part that depends on which board the connector lands on, which no earlier choice fixes, so it is the board task's |
| Hardware already bought | The existing loom |
| Reference | None found as a design; the connector families are recorded in `connector-pinouts.md` |
| Properties | None carried: the headers and terminals are single parts |
| Harness | Two retained harnesses change, the leads of the coffee and the steam element (`COFHEATER`, terminal 5, and `STMHEATER`, terminal 4, `connector-pinouts.md` § Mains terminals): they end at the wall relay and no longer at the board, because a load switched by a device mounted elsewhere cannot keep a harness that ended at the old board (`REQ-RETROFIT-FIT-001`, the parent's rationale). The change is to those two leads and no other: the pump and valve leads end at the board's tabs as before. The element harness to the wall is the assembly task's design (`DEL-HW-PARTITION-AND-FEASIBILITY.C5`) |
| Firmware | None |

### Proof-of-life interlock

| | |
|---|---|
| Function | The interlock that removes heater power when the controller stops, built into the first controller hardware (`DEC-PROOF-OF-LIFE-INTERLOCK-IN-FIRST-HARDWARE`) |
| Form | **Designed**, on the controller board, in series with each heater's supply path: no bought watchdog or timer module. The mechanism and its parts are the design task's (`DEL-HW-PARTITION-AND-FEASIBILITY.C5`), to a removal interval `DEL-HW-INTERLOCK-INTERVAL-DERIVED` derives |
| Reason | A shorted semiconductor switch holds the element energised with no command, which no device choice prevents (`component-specification.md` § The regression this specification makes visible); only a series element that removes power independently does. A timer or watchdog module has a fixed timeout that the interval, once derived, may not match (the earlier design's deferred module recorded its timeout as coarse, `controller-design/control-system-bom.csv`, *Watchdog module [DEFERRED]*), and the interval is not yet derivable (`controller-board-design-constraints.md` § Proof-of-life removal interval). Its dependence on a derived figure is what makes a designed circuit better: its timing is set to the figure rather than to a module's |
| Hardware already bought | None |
| Reference | None found as a published design. Looked in: manufacturer application notes by search on 2026-10-23, whose results were a Fluke calibration-bath description (an independent watchdog monitoring the processor, with a hardware cutout) and a heater-control blog; neither is a circuit |
| Properties | The earlier design provided nothing here (`controller-board-design-constraints.md` § Nothing in the earlier design provided): no property is carried |
| Firmware | The firmware must keep the proof of life alive in whatever way the board's mechanism needs; that is stated by the board task with the mechanism, and nothing is written here |

### Mains inlet filter

| | |
|---|---|
| Function | The appliance inlet and EMI filter, a module of the earlier design (`controller-board-design-constraints.md` § Mains inlet filter) |
| Form | **Bought**: the inlet filter, as `DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE` settles it, rated 15 A at 50 °C, the next rating up in the same filter family as the 10 A part |
| Reason | The decision settles it: the chain is rated above its 10 A fuse. This record reopens the module and finds nothing it adds: the filter has no control input, no barrier and no output, so there is no property to carry |
| Hardware already bought | None |
| Reference | The decision's own account of the chain; the filter's figures are the working design's and have not been rechecked for the 15 A part (`controller-board-design-constraints.md`, *Mains inlet filter*, *Rating*) |
| Properties | None provided |
| Firmware | None |

## Every module of the earlier design, reopened by name

None was kept by default (`controller-board-design-constraints.md` § Carried-forward module properties). The earlier design is `controller-design/control-system-bom.csv` and its companions.

| Module of the earlier design | Reopened as | Outcome |
|---|---|---|
| WeAct MiniSTM32H743, the controller module | *Controller* | Not kept; microcontroller designed onto the board |
| EARU SSR-40DA, the heater switches | *Coffee and steam element switching* | Not kept: no maker's datasheet, so its isolation rating and zero-cross type count as absent. A relay of this class from a maker that publishes both may be fitted once its own figures are sourced and meet § The heater switch against the carried-forward properties |
| ULN2003A breakout, the heater switch drive | *Heater gate drive* | Not kept; one transistor per channel |
| RBdimmer, the pump dimmers, one zero-cross output shared | *Coffee and steam pump switching*, *Supply-timing front end* | Not kept; opto-triac and triac designed, front end designed |
| Songle four-channel module, the valve relay module and its driver | *Two-way and three-way valve switching* | Not kept; relay and driver designed |
| RC-and-varistor snubber modules across the valve contacts | *Two-way and three-way valve switching* | Not kept; set aside as not to be inherited |
| XDB401, the two pressure sensors | *Steam-path pressure sensing* | Not kept: no withstand voltage is published for it; the brew-path transducer was added by no decision |
| Mean Well IRM-10-5 and its hand-cut carrier, the logic supply | *Low-voltage supply* | Carrier not kept; the IRM-10-5 is not the proving candidate, its margin at 70 °C being thin |
| BL0942 energy meters | *Heater mains-presence confirm* | Not kept |
| Schaffner FN9222-15-06, the inlet filter | *Mains inlet filter* | Kept as the decision settles |

## Parts off the boards

A part placed off the boards or outside the enclosure is the heater switching assembly on the machine's wall: each element's relay (S3) and its heatsink. The owner's plan, 2026-10-23, is to mount the two switches directly on the machine's metal wall at the bottom near the pumps, by cutting away the plastic side wall (`controller-board-design-constraints.md` § Enclosure air temperature, *Premises*; owner statement; the plan is not a decision of the graph).

**Drop-in.** The assembly is **a device the retrofit adds**, and so falls outside `REQ-RETROFIT-FIT-001`'s scope, which says "Devices the retrofit adds bring their own connections and are outside it". The reason is specific: the original relays sat on the board being replaced, and the heatsink and its 5–7 W dissipation exist only because `DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM` brings in a semiconductor switch in place of the relay that could not be commanded every half-cycle. The replacement boards themselves still drop into the machine as found: the board's fit is the record of `reference-machine.md` § Controller enclosure as found, which the assembly takes no space from, and the only retained harnesses that change are the two element leads (§ Wiring, connectors, mains-rated terminals, *Harness*). The pumps, valves and every other retained device keep the harnesses they have.

**Thermal judgement.** Each relay is judged against its rated temperature by the design task for the heater-switch assembly (`DEL-HW-PARTITION-AND-FEASIBILITY.C5`), which sizes the heatsink against the relay's own thermal table, judges the assembly thermally against the enclosure air temperature the constraints record holds, **70 °C, a project assumption to replace that bring-up measures** (`DEL-HW-BRING-UP.C13`), and records the heat the assembly passes into the enclosure through the shared wall, which is not estimated here (`controller-board-design-constraints.md` § Enclosure air temperature, *Premises*: unmeasured). The 70 °C is cited as an assumption and the judgement is not read as resting on a measured figure. What this record gives that task, from the candidate's datasheet (S3):

| Quantity | Value | Source |
|---|---|---|
| Relay operating temperature range | −20 °C to +70 °C; junction at most 125 °C | S3, *Thermal Specifications* |
| Margin of that range against the assumed 70 °C | None: the range's top equals the assumption. If the air the assembly sits in is hotter than 70 °C, the relay is outside its range | This record, by comparison |
| Heatsink thermal resistance the datasheet's table requires at 70 °C ambient, coffee element, 4.80 A: the table's 5 A row | 6.7 K/W, dissipating 5 W | S3, *Heatsink Dimensions*, RA..25 |
| The same for the steam element, 5.38 A: the table's 7.5 A row, the one above it | 4.2 K/W, dissipating 7 W | S3, as above |
| The same to carry the overload band the inlet fuse leaves, about 15 A (`controller-board-design-constraints.md` § Upstream protection and fault current, *Each heater branch*): the table's 15 A row | 1.9 K/W, dissipating 16 W | S3, as above |
| Heat the two relays pass into the wall at their normal currents | At most 5 W + 7 W = 12 W | S3, rows above |
| Relay's surge and fusing figures against the fault current | 325 Ap non-repetitive for 10 ms; I²t at most 525 A²s | S3 *Output Specifications*. Checked against the inlet fuse's let-through when that is recorded (§ Pending marks, *Each protective device's clearing time and let-through*) |

The heatsink's fitted thermal resistance, the wall's, and the mounting are the assembly task's, and the heatsink the catalogue stocks, C361579, states no thermal resistance (`controller-board-design-constraints.md`, *Coffee and steam element switching*), so it is not offered.

### The heater switch against the carried-forward properties

| Property (*Heater switches* rows) | Candidate RA2425-D06 (S3) | Met |
|---|---|---|
| Isolation: *Mains barrier* | Input to output at least 4000 VACrms; output to case at least 4000 VACrms; insulation resistance at least 10¹⁰ Ω | Sourced; judged against the basis in § Barrier parts |
| Zero-cross turn-on, load-bearing and unconfirmed in the earlier design | "Zero switching"; zero-voltage turn-on at most 20 V | Confirmed on the maker's datasheet |
| *Rated for the supply* | Operational voltage 24–280 VACrms (covers 253 V); blocking at least 650 Vp (against 358 V peak); 25 A AC-51 (against 4.80 A and 5.38 A); repetitive overload at most 55 A for 1 s | Met; current at the heatsink's temperature is the table above |
| Current while off | Off-state leakage at most 3 mArms at rated voltage and frequency | Recorded; § The heater switch's leakage |
| Failure | A shorted junction is a semiconductor switch's ordinary failure; not claimed otherwise by S3 | Covered by the interlock (§ Proof-of-life interlock) |
| Input thresholds and default state | 3–32 VDC; pick-up at least 3 VDC, drop-out at most 1 VDC; reverse at most 32 VDC; input impedance 1.5 kΩ; control pulse at least 0.5 ms | Off with no control current: *Held off undriven*, § Heater gate drive |

### The heater switch and the per-half-cycle decision

`DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM` rejects leaving the alignment to the switching device's own internal synchronisation, because it costs the ability to say how many half-cycles were delivered. A zero-cross relay seems to do that and does not contradict the decision, for this reason. The layer below the seam still takes the decision once per supply half-cycle, and still carries the residual. What the relay's internal zero-cross turn-on changes is only when within a half-cycle the output begins; it does not choose whether a half-cycle is delivered. The layer times each change of the relay's control input against the supply-timing front end (§ Supply-timing front end), which presents both crossings, and places the change inside the half-cycle that precedes the one it governs, clear of the crossing. The relay then turns on at the next zero (zero-voltage turn-on at most 20 V, which at the 358 V peak is 3.2 degrees, 0.18 ms at 50 Hz) and turns off at the next current zero after the input is removed, so a half-cycle that has begun is delivered whole. The count of delivered half-cycles is therefore the count of half-cycles for which the input was asserted at its start, which is what the energy account is kept in. This is what `component-specification.md`'s *Heater gate drive* row asks: firing at the zero crossing in hardware rather than at an instant the controller estimates.

The relay's own timing from its datasheet (S3): response on pick-up at most 1/2 cycle; response on drop-out at most 1/2 cycle; control pulse at least 0.5 ms. At the 50 Hz nominal a half-cycle is 10 ms, so a change placed anywhere in the preceding half-cycle with the pulse at least 0.5 ms clear of the crossing takes effect at the intended crossing and no later. At 60 Hz a half-cycle is 8.33 ms; the requirement is the same in half-cycles. The placement figures are the layer's, below the seam, and the datasheet gives no tighter figure.

### The heater switch's leakage against the mains-presence confirm

With the relay off, S3 bounds its leakage at 3 mArms. The confirm's input sits across the element's terminal and neutral through the 120 kΩ resistor.

- With the element intact, that leakage flows through the element, 52.7 Ω (coffee) or 47.0 Ω (steam, a lower bound; `reference-machine.md` § Heating and load), and the node stands at at most 3 mA × 52.7 Ω = 0.16 V. The confirm's branch then carries at most 0.16 V / 120 kΩ = 1.3 µA, against (216 − about 1.2) V / 120 kΩ = 1.8 mA rms at the bottom of the span with mains present, a ratio over one thousand: leakage does not read as mains.
- With the element open-circuit between the confirm's tap and neutral, the datasheet's bound does not exclude all of the leakage flowing in the confirm's branch: 3 mA against the 1.8 to 2.1 mA rms of mains present. With the relay off and the element open the confirm can therefore read present. That reading is the fault the channel exists to flag (mains reaching an element with no command), and an open element is itself a fault, so the confirm's tap position and threshold, which separate the two, are the board's and the assembly task's design (`DEL-HW-PARTITION-AND-FEASIBILITY.C5`), shown against this bound.

## Barrier parts

Each part forming a mains barrier, with the rating it must carry as a design target, and one candidate that proves the form feasible with a figure sourced from its maker.

**The design target.** The rating a barrier's part must carry is set by the declared separation basis: at or above what the barrier's declared insulation type, basic or reinforced, requires at the declared working voltage and overvoltage category (`DEC-BOARD-SEPARATION-BASIS-RECORD`, the paragraph beginning "This holds for parts the build buys"), read from the signed basis record by `DEL-HW-PARTITION-AND-FEASIBILITY.C3`. This record states the inputs it gives that basis: working voltage 253 V rms, 358 V peak (`controller-board-design-constraints.md` § Inputs to the separation basis). The number of kilovolts the basis assigns each barrier does not yet exist and is not invented here; **until the basis states it, the candidate figures below are recorded and no barrier is called adequate against a number that is not yet declared.** A part whose rating cannot be sourced is recorded as absent. The two non-isolation figures, blocking and operating voltage, the *Rated for the supply* constraint fixes at 358 V peak and 253 V rms.

| Barrier | Part form | Candidate, with its sourced rating | Not sourced, so recorded as absent |
|---|---|---|---|
| Supply module, mains to every low-voltage rail | Bought module | Mean Well IRM-20-5: withstand voltage input to output 4.2 kVac; isolation resistance 100 MΩ at 500 VDC, 25 °C, 70 % RH; Class II (S1, file `IRM-20-SPEC 2025-11-21`). The IRM-10 sheet of the earlier design gives the same figures (S2, file `IRM-10-SPEC 2025-08-08`). The constraints record held this rating as disputed (`DEL-HW-DESIGN-CONSTRAINTS.C2`); the figure here is the maker's current published one, read at source, with the revision above | The test duration of the withstand voltage is not stated on either sheet |
| Each heater switch | Bought relay | Carlo Gavazzi RA2425-D06: input to output at least 4000 VACrms, output to case at least 4000 VACrms (S3, *Isolation*, sheet dated 06.10.2025) | The EARU SSR-40DA of the earlier design: absent. The test duration of the 4000 VACrms is not stated on S3 |
| Each pump drive | Designed opto-triac | onsemi MOC3052M: input to output isolation voltage 4170 VACRMS, 60 Hz, one minute, described as an internal device dielectric breakdown rating (S5, Rev. 4, September 2022) | A working isolation voltage: the datasheet gives only the test voltage |
| The supply-timing front end, and each mains-presence confirm | Designed AC-input optocoupler | Lite-On LTV-814: isolation voltage 5000 Vrms (S10, Rev. K, effective 01/05/2019), measured AC for one minute at 40–60 % RH; isolation resistance 5×10¹⁰ Ω at 500 VDC | A working isolation voltage |
| Each valve switch | Designed relay | Hongfa HF115F-Q: coil to contacts 5000 VAC for one minute; open contacts 1000 VAC for one minute; surge coil to contacts 10 kV 1.2/50 µs; insulation resistance 1000 MΩ at 500 VDC (S8, 2024 Rev. 1.00). The HF32FA-G, the floor's family, gives the same 5000 VAC and a maximum switching voltage of 250 VAC (S9, 2026 Rev. 1.00) | The open-contact figure is 1000 VAC, below the coil-to-contact figure, so a barrier that relies on open contacts is not given by this part |
| Pressure sensors' insulation from the water path | Bought transducer | Ashcroft S1: insulation withstand voltage 500 Vac; insulation resistance over 100 MΩ at 100 VDC (S11, Rev I, 19 May 2026) | The duration and the test points of the 500 Vac. The earlier design's XDB401 gives insulation resistance over 100 MΩ at 500 V and no withstand voltage (`controller-board-design-constraints.md`, *Pressure sensors*): absent. For the other transducers read, see § The steam-path transducer |

## The steam-path transducer

**What the part must carry**, from the recorded basis (`controller-board-design-constraints.md` § Steam-path transducer pressure, whose figures are cited and not restated here):

| Target | Value | Basis row |
|---|---|---|
| In-service pressure it must survive | 5 bar gauge | *In-service pressure the transducer must survive*, inferred |
| Proof pressure | At least 7.5 bar gauge | *Proof pressure the part must carry*, project assumption, to replace |
| Burst pressure | At least 10 bar gauge | *Burst pressure the part must carry*, project assumption, to replace |
| Full scale | At least 2.0 bar gauge and at most 25 bar | *Lower bound on the part's range*, *Upper bound on the part's full scale* |

**Candidate**, checked against it: Ashcroft S1, 316L fittings, range code 100 (0–100 psi, 6.895 bar), ratiometric 0.5–4.5 Vdc on a 5 Vdc ± 0.5 Vdc supply (S11).

| Check | Datasheet figure | Result |
|---|---|---|
| Proof | 2× full scale for the range, 13.8 bar | At least 7.5 bar: met, 1.84 times |
| Burst | 5× full scale, 34.5 bar | At least 10 bar: met, 3.4 times |
| Full scale | 6.895 bar | Within 2.0 bar to 25 bar, and above the 5 bar in-service pressure so the part does not clip in service |
| Accuracy | ±1.0 % of span (±0.5 % optional): ±0.069 bar | Inside the binding ±0.25 bar (`controller-board-design-constraints.md` § Steam-path transducer pressure, *Upper bound on the part's full scale*), ignoring thermal error outside 0–85 °C, where the sheet adds ±2.0 % of span |
| Insulation | Withstand 500 Vac; resistance over 100 MΩ at 100 VDC | § Barrier parts |
| Media and ambient temperature | Media −40 °C to +125 °C; ambient −40 °C to +125 °C | See below |

**The basis states no media temperature.** The recorded basis is a pressure basis; nothing in the record gives a temperature the transducer's wetted part must survive. Saturated steam at the casting ceiling, near 150 °C (`controller-board-design-constraints.md` § Steam-path transducer pressure, *Saturation bound at the casting ceiling*), is above the candidate's 125 °C media limit. This record cannot judge the fit on a figure the basis does not carry, and states the gap rather than calling the candidate adequate: no part of the steam path's plumbing, such as a length that cools the steam before the transducer, is decided here.

**Other transducers read and not proving candidates**, each from its maker's datasheet, 2026-10-23:

| Part | Why it does not prove the form |
|---|---|
| Honeywell PX3 series (S12) | The maker states it is not recommended for media involving water or saturated air such as steam and vapor |
| WIKA A-10 (S13, PE 81.60, 02/2026) | Medium limit 80 °C, or 100 °C in the extended range; overpressure limit 2 times for ranges at or above 1.6 bar; **no burst pressure is published** in that sheet, so burst is absent; insulation voltage DC 500 V |
| Danfoss MBS 3000 (S14, 2020.12) | Media temperature −40 to 85 °C; overload and burst each 6 × full scale; insulation resistance over 100 MΩ at 500 VDC and no withstand voltage published, so the insulation rating is absent |
| Nidec P-7100-103G (S15) | Meets proof and burst (maximum pressure 2.0 MPa, break-down 3.0 MPa for the 0–1.0 MPa range) and gives a dielectric strength of 500 VAC for 60 s, but its operating range is −20 to 70 °C and no steam statement is given; price listings seen on 2026-10-23 for the family ran from 116 USD to 314 USD per part, high against the declared spend |
| XDB401 (the earlier design's) | Insulation resistance only; no withstand voltage published |

## Availability and price

JLCPCB's public parts library, read through the search service its library page uses (`https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList/v2`) with in-stock results only on **2026-10-23**, graded published unverified, read at source. Unit prices are in USD at the smallest break; the build quantity is the count times 2 and falls within that break (`controller-board-design-constraints.md` § Manufacturer stock and price, per channel). Stock moves by the hour.

| Candidate | JLCPCB part | Class | Stock | Unit price (break) | Source address |
|---|---|---|---|---|---|
| IRM-20-5 logic supply, count 1 | C6280121 | Extended | 2 607 | 6.3797 (1–9) | https://jlcpcb.com/partdetail/MW_MEAN_WELL_Enterprises-IRM_205/C6280121 |
| MOC3052M opto-triac, count 2 | C8965 | Extended | 5 359 | 0.5888 (1–9) | https://jlcpcb.com/partdetail/onsemi-MOC3052M/C8965 |
| BTA204S-600B triac, count 2 | C256462 | Extended | 4 745 | 0.8537 (1–49) | https://jlcpcb.com/partdetail/WeEnSemiconductors-BTA204S_600B118/C256462 |
| HF115F-Q/012-1H relay, count 2 | C5318991 | Extended | 18 | 3.2119 (1–9) | https://jlcpcb.com/partdetail/6075917-HF115F_Q_0121H/C5318991 |
| HF32FA-G/012-HSL1 relay, for comparison | C183617 | Extended | 1 597 | 1.6698 (1–9) | https://jlcpcb.com/partdetail/195021-HF32FA_G_012HSL1/C183617 |
| LTV-814S-TA1-A optocoupler, count 3 (one front end, two confirm) | C108051 | Extended | 14 500 | 0.1361 (1–49) | https://jlcpcb.com/partdetail/LiteOn-LTV_814S_TA1A/C108051 |

The HF115F-Q's 18 in stock covers the build quantity of 4; a larger build needs a later read. The assembly type of each part above was not re-read.

**Bought items the catalogue does not stock**, each read on 2026-10-23:

| Item | Availability and price | Source |
|---|---|---|
| Carlo Gavazzi RA2425-D06, count 2 | 69.00 USD each at one US distributor, 138 USD for two; stock not shown on that page. Other listings seen in search results the same day: RS Components UK 64.17 GBP ex VAT with 79 in stock, element14 Singapore 93.40 SGD with 109 in stock, RS New Zealand 115.81 NZD ex GST, indicative and not read at the page | https://www.instrumart.com/products/all-part-numbers/48736 (read); RS and element14 listings by search result only |
| Heatsink for each relay | Not read. The assembly task selects it against the table above and records its price and stock. The one heatsink the catalogue stocks states no thermal resistance and is not offered | `controller-board-design-constraints.md`, *Coffee and steam element switching* |
| Ashcroft S1 transducer, count 1 | **No price and no stock found.** Searches on 2026-10-23 returned the datasheet and distributor pages for other Ashcroft transducer models only, with no S1 listing; Ashcroft's own contact line is in the datasheet. Recorded as absent, not guessed | S11 |
| The earlier design's controller module, pump dimmers, valve relay module | Not bought; no stocked candidate (`controller-board-design-constraints.md` § Manufacturer stock and price, per channel). Recorded as dropped | — |

A designed isolated converter was not chosen, so its transformer's required insulation is not stated: the logic supply is a module whose withstand voltage is sourced (§ Barrier parts).

## Sources read

Every address was opened on **2026-10-23** and the figures read from its text, except where a row says otherwise. The revision is the one the document prints.

| No. | Document | Revision or date printed | Address |
|---|---|---|---|
| S1 | Mean Well IRM-20 series specification | File `IRM-20-SPEC 2025-11-21` | https://www.meanwell.com/Upload/PDF/IRM-20/IRM-20-SPEC.PDF |
| S2 | Mean Well IRM-10 series specification | File `IRM-10-SPEC 2025-08-08` | https://www.meanwell.com/Upload/PDF/IRM-10/IRM-10-SPEC.PDF |
| S3 | Carlo Gavazzi RA 24..06, RA 48..12 datasheet | "Specifications are subject to change without notice (06.10.2025)" | https://www.gavazziautomation.com/fileadmin/images/PIM/DATASHEET/ENG/SSR_RA.pdf |
| S4 | Carlo Gavazzi solid state relay installation instructions, RA family | No revision printed | https://www.gavazziautomation.com/fileadmin/images/PIM/MANUALS/ENG/SSR_IL_RA.pdf |
| S5 | onsemi MOC3052M, 6-pin DIP random-phase triac driver (also MOC3051M) | MOC3052M/D, Rev. 4, September 2022 | https://www.onsemi.com/download/data-sheet/pdf/moc3052m-d.pdf |
| S6 | onsemi MOC3023M, covering the MOC3021M | MOC3023M/D, Rev. 3, June 2023 | https://www.onsemi.com/download/data-sheet/pdf/moc3023m-d.pdf |
| S7 | WeEn BTA204S-600B, 3Q Hi-Com triac | Rev. 02, 19 March 2025 | https://www.ween-semi.com/datasheet/BTA204S-600B.pdf |
| S8 | Hongfa HF115F-Q | 2024 Rev. 1.00 | https://source.hongfa.com/Uploads/Product/PDF/HF115F-Q_en.pdf |
| S9 | Hongfa HF32FA-G | 2026 Rev. 1.00 | https://source.hongfa.com/Uploads/Product/PDF/HF32FA-G_en.pdf |
| S10 | Lite-On LTV-814, 824, 844 | Revision K, effective date 01/05/2019 | https://optoelectronics.liteon.com/upload/download/DS-70-96-0013/LTV-8X4%20series%20RevK.PDF |
| S11 | Ashcroft S1 pressure transducer | `S1_transducer_ds_RevI_19-May-26` | https://www.ashcroft.com/wp-content/uploads/2026/05/datasheet-s1-pressure-transducer-oem-ashcroft.pdf |
| S12 | Honeywell PX3 series heavy duty pressure transducers | File created 2022-10-15; no revision printed | https://prod-edam.honeywell.com/content/dam/honeywell-edam/sps/siot/ja/products/sensors/pressure-sensors/industrial-pressure-sensors/px3-series/documents/sps-siot-heavy-duty-pressure-px3-series-datasheet-32313757-ciid-159273.pdf |
| S13 | WIKA pressure sensor A-10, data sheet PE 81.60 | 02/2026 | https://www.wika.com/media/Data-sheets/Pressure/Pressure-sensors/ds_pe8160_en_co.pdf |
| S14 | Danfoss pressure transmitter MBS 3000 and MBS 3050 | 2020.12, AI308930736185en-000201 | https://assets.danfoss.com/documents/latest/156946/AI308930736185en-000201.pdf |
| S15 | Nidec Components P-7100 catalogue | File modified 2025-03-10; no revision printed | https://www.nidec-components.com/e/catalog/pressure-sensor/p-7100.pdf |

Published reference designs and where they were looked for:

| No. | Document | Read |
|---|---|---|
| R1 | onsemi application note AN-3003, random-phase triac drivers, REV. 4.07, 10/6/06 | https://www.onsemi.com/pub/collateral/an-3003.pdf, read |
| R2 | TI SBAA338, *Monitoring NTC thermistor circuit with single-ended ADC* | https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/73/sbaa338_5F00_monitoringTempTEC.pdf, read |
| R3 | ST AN4488, *Getting started with STM32F4xxxx MCU hardware development*, Rev 7 (October 2018) per the search result | https://www.st.com/resource/en/application_note/an4488-getting-started-with-stm32f4xxxx-mcu-hardware-development-stmicroelectronics.pdf. **Not read**: st.com did not answer on 2026-10-23; the title and revision are from a search result and the current revision may differ |
| R4 | TE Connectivity, *Proper Coil Drive is Critical to Good Relay and Contactor Performance*, 13C9132; onsemi AND8116/D | https://www.te.com/commerce/DocumentDelivery/DDEController?Action=srchrtrv&DocNm=13C9132_Coil_Drive_AppNote&DocType=CS&DocLang=EN and https://www.onsemi.com/download/application-notes/pdf/and8116-d.pdf. **Located by search, not read in full** |
| R5 | Mean Well installation manual, open-frame PCB type, families including IRM | https://www.meanwell.com/Upload/PDF/PCB_EN.pdf, 2023.11.21, read |

## Pending marks this record ended

`controller-board-design-constraints.md` § Pending marks held each of these against the choice of form, and now records the value and source, or re-points the part that belongs to a board or assembly's design task:

| Mark | Ended by |
|---|---|
| Supply module's isolation rating (and the register row) | § Barrier parts: 4.2 kVac, S1 |
| Whether the wall mount keeps the retrofit within `REQ-RETROFIT-FIT-001`, and where each switch is judged against its rated temperature | § Parts off the boards |
| The barrier rating of each part in *Mains barrier*, and the pressure sensors' insulation | § Barrier parts; the number each barrier needs is the basis's (`DEL-HW-PARTITION-AND-FEASIBILITY.C3`) |
| The steam-path transducer's part, availability, price, and its proof, burst and full-scale check | § The steam-path transducer, § Availability and price |
| Availability and price of each bought module the catalogue does not stock | § Availability and price |
| The heatsink for each heater switch | The form is a bought heatsink on the wall; sizing and thermal resistance re-pointed to the assembly task (`DEL-HW-PARTITION-AND-FEASIBILITY.C5`) |
| The transformer of a designed isolated converter | Not chosen: the logic supply is a bought module |

The marks held against the design task of a board (rail budgets, branch fuse ratings, the logic supply's mains input, feed protection, output limit and inrush, protective clearing times, headers) stay with their tasks.
