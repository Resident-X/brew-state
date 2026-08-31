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
followed the copper. **Read** means it comes off a scan or a datasheet and nobody has confirmed it
against the machine. **Observed** means somebody watched the running machine do it. **Inferred**
means it follows from other rows rather than from any of those.

They are not ranked in that order. **Traced** is the strongest: copper does not change while you look
away. **Read** comes next and travels furthest — a datasheet figure is a manufacturer's guarantee, and
several of the tightest numbers in this document are Read rather than Traced — but it describes a part
number, not necessarily the part fitted, which is why every Read row here says which. **Inferred** is
as strong as the rows beneath it and no stronger; it fails silently when one of those is wrong.
**Observed** sits below Traced and is the grade to treat most carefully, because what it records is
one person watching one thing at one moment — and the one claim in this document that had to be
withdrawn was an observed one. Its failure mode is not dishonesty but sampling: a null result, a
*nothing happened*, is what a mistimed glance produces for free. Nothing here is a specification —
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

The harness has nine conductors. *(Provenance: **Observed** — owner's count of the physical
harness.)* That number
is load-bearing for everything below — two of the conclusions in this section follow from *and there
are nine* and from nothing else — so it is worth stating separately from the reasoning it feeds.

This assembly is a sandwich of boards and gauge movements and cannot be opened without disassembly,
so what follows is **inferred** rather than traced. It is inferred from three things that agree, and
it replaces an earlier reading that fitted none of them.

**The stepper driver is on this board, not on the main board.** The `VID66-08` and its decoupling
capacitor appear on circuit-diagram sheet 3-3 and are **absent from photographs of the main-board
spare part**. The parts exist and are not on the main board, and this is the only other board they
could be on. *(Provenance: absence established from replacement-part photographs, which may not show
both sides of the board or the same revision; presence on this board not directly observed.)*

**The wire count only closes this way, and it closes exactly.** Two bipolar motors driven from the
main board would need eight phase conductors. Add the water indicator's cathode and the anode rail
that lights it and that is ten, before any supply or ground conductor is counted. Driving the
`VID66-08` locally needs seven conductors — supply, ground, `RST`, and a direction and a step line
per channel — which leaves exactly two for the indicator's cathode and its rail. Nine, with nothing
spare.

**The water indicator is on the gated rail, like every other indicator on the machine.** Running the
machine with a low tank, the fill-tank lamp dims and brightens in step with the button panel's
elements. *(Provenance: owner's direct observation of the running machine, correcting an earlier
observation of the same machine that read the lamp as holding steady.)* So the `Q7`-gated anode rail
reaches this assembly too, and that is the ninth conductor: brightness is modulated globally across
both front assemblies, from one gate, and no indicator this record carries sits outside it. That is
an **Observed** claim and it is one person watching one machine once — better founded than the
observation it replaces, for the reason below, but not traced.

That correction is worth recording rather than quietly applying. The earlier observation was taken
to overturn the reading this section has now returned to — that the water elements share a cathode
like every other paired group — and to invent a second supply rail in its place, so an entire
accounting was rebuilt around it.

**The second observation is the better one, and for a reason worth stating rather than assuming.**
Seeing a lamp *change* is a positive attestation: something happened, and it was seen. Seeing a lamp
*not change* is a null result, and a mistimed glance produces one for free — the ramp is slow, and a
few seconds spent looking at the wrong moment is indistinguishable from constant brightness. The two
observations are not symmetric, and it is not merely that the later one is later.

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
| 9 | `Q7`-gated indicator anode rail, shared with the button panel | Inferred; that the rail reaches this assembly is **observed** |

**Two things now settled**, which an earlier reading of this section left open. They rest on
different evidence, so each names its own:

- **The two `WATER` elements share a cathode.** The sheet draws `WATER` as `LED6A` and `LED6B`. Were
  they driven separately the harness would need a tenth conductor, and there are nine. That also puts
  them on the pattern every paired group on the button panel follows, where both elements of a pair
  share one cathode line, rather than breaking it.
- **There is no second supply rail.** The circuit diagram draws `VDD` on both pin 16 and pin 8 of the
  `VID66-08` and ties them to the same `VCC5` net, and the datasheet lists both pins under one
  undifferentiated supply function with no separate logic and motor domains. Two supply pins, one
  node, one conductor. Where that node is physically joined — on the main board or on this assembly —
  is **not established**, and nothing here needs it to be. A redundant second conductor to the same
  node would be possible but has no reason to exist: worst case is a few hundred milliamps over
  40 cm.

### What the driver's control lines ask for

The pin naming — `DIR` plus `F` — is the conventional direction-and-step-frequency pair, and what
follows is now read from the part's datasheet rather than inferred from the naming. *(Provenance:
`VID6608` datasheet, Hong Kong VID Company, revision 1, 2022, read. That the fitted part matches this
revision is inferred from the circuit diagram's marking, not traced — a second-sourced or older
variant could carry different thresholds.)*

`DIRA` and `DIRB` are levels, not waveforms: high picks one direction, low the other, sampled when
the step clock edges, static between steps. Ordinary outputs.

`FA` and `FB` are step clocks and want **timer outputs rather than software-toggled pins**. A needle
has inertia, so the step rate is bounded above by what the movement can follow before it stalls and
below by what still reads as a sweep rather than a stutter — and smooth motion needs an *even* rate.
Pulses timed in software jitter with whatever else the control loop is doing, and that jitter is
visible on a needle. The two channels are independent and both gauges can move at once, so that is
two timer channels, not one shared.

`RST` resets the driver's phase counter. It does not tell the controller where the needle is. It is
**active low and shared across both channels** — one pin serves both movements, so neither can be
reset alone. The datasheet asks that it be held low while `VDD` rises and released about a
millisecond after the supply settles, which a replacement owes at power-on.

Rising edges on `FA`/`FB` advance one microstep, fixed in silicon at 1/12° of shaft rotation, with
all sixteen pins accounted for and none left to select a different mode. Pulses must be at least
**450 ns** either side, `DIR` must be stable **100 ns** before a step edge, and `RST` released
**100 ns** before one. A glitch filter discards anything under 20 ns, which is a floor on how short a
real pulse may be as well as a defence against noise.

The silicon accepts 1.1 MHz. The datasheet's **7.2 kHz** (600°/s) ceiling is a property of the
movements rather than the driver, and it is quoted there against the `VID29` motors the part is sold
to drive — **that `MOT1` and `MOT2` are `VID29` movements is not established**, so treat 7.2 kHz as
the companion motors' figure and not yet as this machine's. The same caveat carries the load
characteristics: at the `VID29` family's ~280 Ω coil and a 5 V rail, phase current lands near 18 mA,
which the driver's ±35 mA absolute maximum independently bounds. That is a conditional bound rather
than a measurement, and it is the nearest thing to a phase-current figure this project holds.

None of the timing is demanding for a timer peripheral; it is recorded so a replacement is not
specified against guesses.

**The logic thresholds are the one figure that constrains board choice.** `VIH` is a minimum of
**3.15 V** and `VIL` a maximum of **1.35 V**, both stated as absolute volts across the whole
`VDD` = 4.5–5.5 V range rather than as a fraction that relaxes with supply.

**The datasheet also says, in prose, that sub-`VDD` drive is what the part is for.** Its inputs carry
a level shifter, described as allowing "operation of the circuit at a higher supply voltage (`VDD`)
than the circuits driving the inputs", so the motors can be run at a higher torque than the logic
rail would allow. That passage points the opposite way from the paragraph above and is quoted here
because it does: a reader with the datasheet will find it, and a section that had omitted it would
deserve to lose their trust.

The two reconcile, and the reconciliation is the useful part. The level shifter is *why* `VIH` does
not scale with `VDD` — it decouples the threshold from the motor supply, which is exactly what lets
`VDD` rise for torque while the driving logic stays put. What it does not do is move the guaranteed
number. 3.15 V is where the DC table puts it, it is `0.7 × 4.5 V` and so was evidently taken at the
bottom of the supply range, and nothing in the prose lowers it further.

**So the honest reading is narrower than "this part needs 5 V logic".** Sub-`VDD` drive is intended
and ordinary. But the threshold a driver must clear is 3.15 V and does not relax, which leaves a 3.3 V
part 150 mV of margin at best — and margin only if its own `VOH` guarantee reaches that far. Many do
not: a common specification is `VOH ≥ VDD − 0.4 V` at rated sink current, about 2.9 V on a 3.3 V rail,
which is *below* the threshold. Real `VOH` into the ~10 µA these inputs leak will sit far closer to
the rail than that, but "far closer" is typical behaviour and not a guaranteed figure, and a board is
specified against guarantees. The datasheet also conditions its timing figures on an input swing of
`VSS` to `VDD`, so the pulse widths above are not underwritten for a partial-swing drive either.

**What retention actually obliges, then, is a check rather than a rail.** 5 V drive clears the
threshold outright and needs no argument. A 3.3 V part is admissible if its own `VOH` guarantee exceeds
3.15 V at the current these inputs draw. If it does not, there are two ways out short of abandoning the
part: five level shifters, cheap but parts on the board and a line in the budget — or a bench
measurement. Two different things can be measured, and the second is the more useful. Measuring the
*controller's* `VOH` into a ~10 µA load turns a typical into a figure established for this design.
Measuring the *driver's* actual switching threshold does more, because 3.15 V is `0.7 × 4.5 V` and was
plainly taken at the bottom of the supply range: the real threshold is likely well below the
guaranteed one, and establishing that would retire the question rather than work around it. This is a cost of retention rather than
of the gauges: a replacement driving the movements directly sets its own thresholds.

The datasheet also asks for an external pull-down on `RST` to hold it low through start-up, and for
100 nF decoupling with 22 µF against latch-up — board-level parts a replacement owes if it re-supplies
this assembly, not just firmware ordering.

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

**Six pins — but not six equivalent pins**, since two must be timer channels and all five driver
lines must clear a 3.15 V input threshold that a 3.3 V part is not guaranteed to reach. The gated anode rail reaches this assembly too, on the ninth conductor, but it
is the same timer output already counted for the button panel — a second connector pin, not a second
controller pin. And — if the board is retained — **no stepper driver in the parts list**. That is not
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

The rail question is settled the other way round from an earlier reading of this section: the water
lamp dims in step with the power element, so both front assemblies hang off the one gated rail. With
that, the conductor count closes exactly and the six-or-seven pin question is closed at **six** — the
totals elsewhere in this project are built on six and need no spare held against this.

**Six is settled only on the premise that the driver is on this assembly**, and that premise is the
section's weakest. Two questions remain. Where the driver's two supply pins are joined changes no
count at all. Whether a 16-pin part is actually on the board changes *everything*: if it is not, the
channel costs eight phase-drive lines and a stepper driver in the parts list rather than six logic
pins. That claim still rests wholly on absence from a photograph of the main-board spare, which is
the one place this section would most repay a screwdriver.

## Open

- Which physical pin is number 1 on the panel connector, and the buzzer's terminal order.
- Direct confirmation that the `VID66-08` is on the gauge assembly at all, which currently rests on
  its absence from photographs of the main-board spare.
- Where the `VID66-08`'s two supply pins are joined — on the main board or on the gauge assembly.
  They are one node either way, so this changes no count.
- Confirmation that the fitted driver matches the datasheet revision read here, rather than being an
  older or second-sourced variant with different thresholds.
- The needle-referred step and the gearing behind it. The *shaft* step is settled at 1/12°; what is
  open is the gearing between shaft and needle, and therefore how far a needle moves per step.
  Steps-per-sweep is obtainable without disassembly by counting between the end stops; the gearing
  itself is not.
- Whether `MOT1` and `MOT2` are `VID29`-family movements, which is what the datasheet's 7.2 kHz speed
  ceiling and ~280 Ω coil figures are quoted against. Phase current follows from that identification
  and is bounded meanwhile by the driver's ±35 mA maximum.
- Whether a specific candidate controller's `VOH` clears the driver's 3.15 V `VIH`, if a 3.3 V part
  is chosen and level shifting is to be avoided. The threshold itself is no longer open; which parts
  meet it is a selection question.
