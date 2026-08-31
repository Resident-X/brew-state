# Connector and harness pinouts

**This file is local, like `reference-machine.md`.** It is the reverse-engineering record: what each
connector on this machine actually carries, established by tracing physical boards and harnesses.

**It is normative about the operator interface.** `DEC-OPERATOR-INTERFACE-REPRODUCED` obliges the
retrofit to reproduce the interface this file describes, by reference rather than by restatement — so
the behaviours recorded here are things a replacement has to produce, and removing one is a deliberate
edit to this file rather than an absence nobody notices. What is preserved is what the operator
perceives, not the parts producing it: the gauge movements, the indicator elements and the sounder
stay replaceable, and a replacement driving them differently to the same visible and audible result
satisfies that decision.
`reference-machine.md` declares *what the machine has*; this file declares *how it is wired
together*. The graph does not carry this detail and should not — a criterion that named a pin would
rot the first time a harness changed. Nodes refer to this artefact instead.

## What outranks what

Where a physical board and the service manual disagree, **the board wins**. The manual has now been
caught twice reusing designators across boards — once on switches (`S1`–`S10` on the panel are not
the `S1`–`S8` the circuit diagram numbers) and once on resistors (`R62`/`R63` on the panel are LED
series resistors, not the 47 Ω line resistors carrying those numbers on the main-board sheet). Its
topology has been broadly right and its labelling repeatedly wrong, which is the pattern to expect
from it: read it for how a circuit works, not for what anything is called.

Every row below carries its own provenance and its own confidence. **Traced** means somebody
followed the copper. **Read** means it comes off a scan and nobody has confirmed it. **Inferred**
means it follows from other rows rather than from an observation. Nothing here is a specification —
it is a record of a machine that already exists.

## Front panel button and indicator board — 9-way connector

Board silkscreen: `EM7000 Panel V1.0`, `MAX120330`. The board carries ten switches, eight indicator
elements and no active parts. Its counterpart circuitry — the pull-ups, the rail-gating transistor,
the buzzer's drive stage — is all on the main board.

| Pin | Carries | Through | Provenance |
|---|---|---|---|
| 1 | Switch common — the grounded leg of all ten switches | direct | Traced |
| 2 | `PRG` group: two switches in parallel, and two indicator cathodes | switches via `R45` (1 kΩ); indicators via `R63` and `R35` | Traced |
| 3 | Indicator common `+V` — the anode rail for every group | gated on the main board by `Q7` | Traced; `Q7` read from sheet 3-3 |
| 4 | `TWO` group: two switches in parallel, and two indicator cathodes | switches via `R44`; indicators via `R62` and `R34` | Traced |
| 5 | `ONE` group: two switches in parallel, and one indicator cathode | switches via `R43`; indicator via `R33` | Traced |
| 6 | `MAN` group: two switches in parallel, and two indicator cathodes | switches via `R42`; indicators via `R30` and `R32` | Traced |
| 7 | `PWR` group: two switches in parallel, and one indicator cathode | switches via `R41`; indicator via `R31` | Traced |
| 8 | Buzzer terminal | direct — the drive transistor is on the main board | Traced; **terminal order not established** |
| 9 | Buzzer terminal | direct | Traced; **terminal order not established** |

**Pin numbering is provisional.** The allocation of signals to pins is traced; which physical pin is
numbered 1 is not, and nothing should be wired from this table without checking the connector's own
keying first.

### Switch pairing

Each key is a wide cap with a tact switch at either end and its indicator showing through the
centre, so an off-centre press still actuates and the cap cannot rock. The two switches of a pair
are wired **in parallel**, so the main board sees one signal per key and cannot distinguish which
half was pressed.

| Key | Switches | Indicator elements |
|---|---|---|
| `PWR` | `S1`, `S6` | 1 |
| `MAN` | `S2`, `S7` | 2 |
| `ONE` | `S3`, `S8` | 1 |
| `TWO` | `S4`, `S9` | 2 |
| `PRG` | `S5`, `S10` | 2 |

*(Provenance: physical spare-part board, traced. Five keys, ten switches, eight indicator elements.)*

**This is why the circuit diagram numbers only `S1`–`S8`.** That range is the **main board's** list of
ground-switched inputs, not the panel's list of switches: five arrive from this panel as parallel
pairs, and three — the sheet's `WAT`, `HOT` and `STM` — arrive from the tank level sensor and the two
knob microswitches, which are elsewhere in the machine and not on this board. The sheet draws those
three with plain switch symbols rather than pushbutton symbols, which is correct and was the clue.
There is no `S9`/`S10` on the sheet because the main board cannot see them.

### Each line does double duty, and the rail gate is what makes that work

A group's line carries both its switch pair and its indicator cathodes. The main board therefore
cannot tell *I am sinking this line to light the indicator* from *somebody pressed the key*, and must
blank the anode rail through `Q7` before reading. `Q7` is not an ornament or a brightness control
that happens to exist — **it is the multiplexing gate, and reading the panel depends on it.**

Two consequences follow, and both bear on a replacement:

- **Indicator brightness is modulated globally, not per line.** The `PWR` element ramping while the
  machine heats is the rail being modulated through `Q7`; only `PWR` is lit at that time, so global
  modulation presents as one element dimming. A replacement needs **one** timer output for the rail,
  not one per line. *(Inferred from the topology; confirm by watching whether two simultaneously-lit
  indicators ramp together.)*
- **The main board owes each shared line a pull-up**, since with the rail blanked the indicator path
  is open and only a pull-up lets a closure pull the line down through the panel's 1 kΩ. The sheet's
  main-board 1 kΩ pull-ups are consistent with that, but 1 kΩ against 1 kΩ puts a closed key at about
  2.5 V on a 5 V part — inside spec and not generous. A replacement should use a weaker pull-up.

### What this costs a replacement controller

| Resource | Count | For |
|---|---|---|
| Bidirectional line — sinks indicator current, reads as an input with a pull-up | 5 | One per key group |
| Timer output | 1 | Anode rail gate, for both blanking and brightness |
| Digital output | 1 | Buzzer drive stage |

**Seven pins for the whole panel**, plus a ground. Not the fourteen a separately-driven reading of
the enumeration gives. The three ground-switched inputs the machine has elsewhere — tank level, hot
water knob, steam knob — are additional and reach the board on their own wires.

## Gauge and water-indicator board — 9-way harness

This assembly is a sandwich of boards and gauge movements and cannot be opened without disassembly,
so what follows is **inferred** rather than traced. It is inferred from three things that agree, and
it replaces an earlier reading that fitted none of them.

**The stepper driver is on this board, not on the main board.** The `VID66-08` and its decoupling
capacitor appear on circuit-diagram sheet 3-3 and are **absent from photographs of the main-board
spare part**. The parts exist and are not on the main board, and this is the only other board they
could be on. *(Provenance: absence established from replacement-part photographs, which may not show
both sides of the board or the same revision; presence on this board not directly observed.)*

**The wire count only closes this way.** Two bipolar motors driven from the main board would need
eight phase conductors, and with the water indicator's cathode that is nine before any supply,
ground or rail conductor is counted. Driving the `VID66-08` locally needs seven signals, which leaves
room for the indicator inside the nine that exist.

**The water indicator is not on the gated rail — observed, not inferred.** Running the machine with a
low tank while it heats, the fill-tank lamp stays at constant brightness while the `PWR` element
ramps. The two are therefore on different rails: this lamp's anode ties to a supply on the gauge
board rather than to the `Q7`-gated anode rail the button panel uses. That is what frees the
conductor which makes the count work, and it is the one part of this section established by
observation rather than by inference. *(Provenance: owner's direct observation of the running
machine.)*

| Conductor | Carries | Provenance |
|---|---|---|
| 1 | `VID66-08` supply | Inferred |
| 2 | Ground | Inferred |
| 3 | `RST` — driver reset | Inferred |
| 4 | `DIRA` — gauge A direction | Inferred |
| 5 | `FA` — gauge A step | Inferred |
| 6 | `DIRB` — gauge B direction | Inferred |
| 7 | `FB` — gauge B step | Inferred |
| 8 | `WATER` indicator cathode | Inferred |
| 9 | **Not established** — see below | — |

**Two candidates for the ninth conductor**, and they cannot be told apart without opening the
assembly:

- **A second supply.** The circuit diagram draws `VDD` on both pin 16 and pin 8 of the `VID66-08`. If
  those are a logic supply and a motor supply fed separately, the ninth conductor is the second rail.
  This is the likelier of the two: two supply pins is ordinary for a motor driver.
- **A second indicator cathode.** The sheet draws `WATER` as two elements, `LED6A` and `LED6B`. If
  they are driven separately rather than paralleled, that is the ninth. This would break the pattern
  every paired group on the button panel follows, where both elements of a pair share one cathode
  line, which is why it is the weaker reading.

### What the driver's control lines ask for

The pin naming — `DIR` plus `F` — is the conventional direction-and-step-frequency pair, and the
requirements follow from that rather than from a datasheet, which nobody here holds.

`DIRA` and `DIRB` are levels, not waveforms: high picks one direction, low the other, sampled when
the step clock edges, static between steps. Ordinary outputs.

`FA` and `FB` are step clocks and want **timer outputs rather than software-toggled pins**. A needle
has inertia, so the step rate is bounded above by what the movement can follow before it stalls and
below by what still reads as a sweep rather than a stutter — and smooth motion needs an *even* rate.
Pulses timed in software jitter with whatever else the control loop is doing, and that jitter is
visible on a needle. The two channels are independent and both gauges can move at once, so that is
two timer channels, not one shared.

`RST` resets the driver's phase counter. It does not tell the controller where the needle is.

### The gauges home against end stops, and the machine shows you it

At power-on the machine sweeps both needles to full scale and back to zero. *(Provenance: owner's
direct observation of the running machine.)* Both movements therefore have hard end stops and the OEM
homes against them — which is how a stepper-driven gauge establishes a datum, since nothing in the
signal path reports needle position.

Three things follow:

- **A replacement owes the same routine.** Without homing, a step count is measured from an unknown
  origin and the needles read plausibly and wrongly, which is worse than reading nothing.
- **The movements tolerate being stalled against a stop**, since the OEM does it on every power-up.
- **The sweep is the measurement.** Counting steps between the two stops gives steps-per-sweep
  directly, which is the figure a reading has to be scaled to and which no document carries. It needs
  a controller driving the motors, not a meter — but it needs no disassembly.

The sweep is also operator-facing: it is the machine demonstrating at power-on that both gauges work.
Dropping it would remove a self-test nobody has written a requirement for, in the same way the
indicator ramp and the low-water lamp could be dropped without anything noticing.

### What this costs a replacement controller

| Resource | Count | For |
|---|---|---|
| Timer output | 2 | `FA` and `FB` — step clocks, one per gauge, needing an even rate |
| Digital output | 2 | `DIRA` and `DIRB` |
| Digital output | 1 | `RST` |
| Digital output | 1 | `WATER` indicator cathode |

**Six pins — but not six equivalent pins**, since two must be timer channels. And — if the board is retained — **no stepper driver in the parts list**. That is not
simply a saving. The `VID66-08` is long out of production, so retaining it makes an unobtainable part
a single point of failure on a channel with no fallback, which is an obtainability risk rather than the unknown-condition question `OBL-PHYSICAL-CONFIGURATION-001.C3` asks — that one is about a part arriving in a state nobody has established, and is answered by testing this driver, not by counting how many are left in the world. Specifying a controller that could
drive the motors directly, and using the retained driver only while it works, is the reading that
keeps both options.

### The water indicator is a channel in its own right

It is fitted, it is driven, and the enumeration did not carry it — the fourth such channel this
branch has found, after the two heater mains-presence senses and the buzzer. It is also the visual
half of a low-water annunciation whose audible half is the buzzer, which does sound on low water. A
replacement that keeps one and drops the other would degrade the annunciation without removing it,
which is the kind of partial loss nothing would notice.

### This board is not passive

The button panel carries no active parts. This one carries the stepper driver, so the two are not the
same kind of assembly and a statement about "the front panel" is true of one and false of the other.
It also means circuit-diagram sheet 3-3 spans **three** physical boards — main, button panel, gauge
board — which is the third time that sheet has grouped by function across a board boundary without
saying so.

### What would confirm it

The rail question is settled: the water lamp holds steady while the power element ramps, so the two
are on different rails. What remains needs the assembly opened far enough to see whether a 16-pin
part is present; whether the driver's two supply pins are tied together on the board or fed
separately; and whether the two `WATER` elements share a cathode. Only one of them changes what the channel costs a controller. If the ninth conductor is a second supply, the cost is the six pins tabulated above. If it is instead a second indicator cathode, the `WATER` elements are driven separately and the cost is seven. The likelier reading is the second supply, and the totals elsewhere in this project are built on it, so a controller specified against them should carry the spare pin rather than treat six as settled.

## Open

- Which physical pin is number 1 on the panel connector, and the buzzer's terminal order.
- Whether the gauge board's ninth conductor is a second supply or a second indicator cathode, and
  direct confirmation that the `VID66-08` is on that board at all.
- Whether the two `WATER` elements share a cathode line.
- Confirmation that button-panel indicator ramping is global rather than per line.
- The two gauge motors' step size, phase current and needle gearing. Steps-per-sweep is obtainable
  without disassembly by counting between the end stops; phase current and gearing are not.
- The driver's logic thresholds. The board supply is 5 V, so its inputs are probably 5 V CMOS, and a
  3.3 V controller may not clear them — a level-shifter question on five lines, and one that applies
  only to the retained-driver option.
- Minimum pulse width on the step clocks, whether they are edge- or level-triggered, and `RST`
  polarity.
