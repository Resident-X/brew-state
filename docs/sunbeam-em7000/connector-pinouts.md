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

## What this record is, and which part of it wins

This folder is one machine's record: a Sunbeam Café Series `EM7000`. Everything in it describes that
machine or what a replacement controller owes it. Material that holds for any machine of this shape
lives outside the folder. Someone fitting a different machine replaces this folder and keeps the rest;
`DEC-MACHINE-RECORD-FOLDER-PER-MACHINE` is why it is arranged that way.

Three documents describe the machine and two are cut from them:

| Document | Role |
|---|---|
| `reference-machine.md` | The declared configuration — what is fitted, and the measured values |
| `connector-pinouts.md` | This file. What each connector and harness carries |
| `controller-io.md` | The channel enumeration — every channel a controller must serve |
| `controller-io-bom.csv` | **Derived.** Every channel with its pin cost, quantity and retention state |
| `control-board-electrical-requirements.csv` | **Derived.** The same surface as requirement groups, in the terms a board is chosen by |

**The two spreadsheets are derived views, not sources of record.** They are cut from the enumeration
and this file for sourcing a controller, and where they disagree with what they were cut from, the
source wins and the spreadsheet is the thing that gets corrected. A disagreement between them and the
enumeration is a defect in them, not an open question.

## What outranks what

Where a physical board and the service manual disagree, **the board wins**. The manual has now been
caught three times putting the wrong designator on the right part — once on switches (`S1`–`S10` on
the panel are not the `S1`–`S8` the circuit diagram numbers), once on resistors (`R62`/`R63` on the
panel are LED series resistors, not the 47 Ω line resistors carrying those numbers on the main-board
sheet), and once **on the integrated circuits themselves**.

That third one is the worst of them and is set out in full below. Briefly: the manual's `U8` and `U9`
are **swapped** relative to the boards. Its topology has been broadly right and its labelling
repeatedly wrong, which is the pattern to expect from it: read it for how a circuit works, not for
what anything is called.

### `U8` and `U9` are swapped, and one of them names a graph node

On the physical boards, **`U9` is the `HT66F50`** microcontroller and **`U8` is the `VID66-08`**
stepper driver. The service manual's circuit diagram has them the other way round. *(Provenance:
**Traced** — the machine was opened and the parts read off the boards.)*

This is not a cosmetic difference, because a designator was already load-bearing in this project. The
decision node `DEC-U8-BOARD-RETENTION-UNVERIFIED` is named for the microcontroller, and takes its
`U8` from the manual. Under board numbering that identifier now points at the stepper driver, which
the decision is not about. **Wherever `U8` appears in the graph or in prose in this project, it means
the `HT66F50` microcontroller** — the manual's numbering — *except* where a sentence explicitly quotes
the board silkscreen, which `reference-machine.md` and `controller-io-bom.csv` each do once and label
as such. The node keeps its identifier because renaming it would break every reference for no gain.

That is a deliberate exception to the rule this section opens with. Everywhere else the board wins;
here the project stays on the manual's numbering because an identifier already in use is worth more
as a stable handle than as an accurate description. The exception is named rather than quietly taken,
because an unnamed one is indistinguishable from an oversight. Anyone reading a board is on the other
convention, and this paragraph is the only place that reconciles them — so prefer the part number to
either designator whenever it actually matters.

Every row below carries its own provenance and its own confidence. **Traced** means somebody had the
hardware in front of them and established the claim from it directly — either by following the copper
or by reading a part off the board it is soldered to. Those are different acts and the rows say which,
but they share what makes the grade strong: the machine itself answered, not a document about it.
**Read** means it comes off a scan or a datasheet and nobody has confirmed it against the machine.
**Observed** means somebody watched the running machine do it. **Inferred** means it follows from
other rows rather than from any of those.

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

## Grades in this file and the shared vocabulary

This file's own grades (*Traced*, *Read*, *Observed*, *Inferred*) were written before the shared table of evidence grades in `controller-board-design-constraints.md` § Evidence grades gained the grade **inspected**. They map onto the shared vocabulary in one correspondence, so a figure here and a figure there can be compared. **No row already in this file is regraded**: the rows keep the words they carry, and a row cited elsewhere takes the grade this table gives it. Rows written or corrected by the as-found inspection of 2026-10-19 use the shared vocabulary directly.

| This file's word | Shared grade | What distinguishes it |
|---|---|---|
| **Traced**, by following copper or reading a resistance with an instrument | **measured** | An instrument read it, on this machine |
| **Traced**, by reading a part, a marking or a mounting off a physical board | **inspected** | Eyes read it, on this machine, with no instrument |
| **Read** off the service manual's circuit diagram | **schematic** | A document about the machine, not the machine |
| **Read** off the service manual's parts list | **parts list** | As above |
| **Read** off a datasheet | **published unverified** | The manufacturer's claim for a part number, not established on the fitted part |
| **Observed**: someone watched the running machine | **owner statement** | One person at one moment, not an inspection of the unplugged machine |
| **Inferred** | **inferred** | Follows from other rows, which it names; no stronger than they are |

Where a row still carries one of the older words, the rows map as follows. *Traced* → **measured**: the panel's switch pairing and the panel-side components reached from each panel contact, followed on the spare-part panel board (§ Front panel, *Switch pairing* and the pin-map rows that cite them). *Traced* → **inspected**: the `VID66-08` and its decoupling capacitor read off the gauge assembly, and the conclusion that the driver is on that assembly. *Read* → **published unverified**: the `VID6608` datasheet figures. *Read* → **schematic**: the figures read off sheet 3-3, including § Main-board sheet 3-3 read from the page images and the series resistances taken from it. *Observed* → **owner statement**: that the water indicator follows the gated rail, and the owner's earlier count of the gauge harness's conductors, which the nine-way connector replaces. *Inferred* → **inferred**: the JST PH family, the rail topology and the gauge harness's conductor allocation beyond what the owner's map read.

The shared grades **measured**, **inspected** and **owner statement** are kept distinct: a pin map that the inspection read by continuity is *measured*, a first pin read off a housing by eye is *inspected*, and neither is levelled with the other. The inspection items cited as `B1.map`, `C2.T1.label` and the like are items of the as-found inspection of 2026-10-19, made by the machine's owner with the machine unplugged throughout; `reference-machine.md` § Controller enclosure as found says how they were taken, and each entry here restates what its item asked so it reads without the sheet. A photograph taken for the inspection is cited by the item it supports. Eight are committed under `photos/` (`photos/README.md` lists them), released by the owner to the public domain, and are cited by path where their items are; the others are cited by item only and are not reproduced.

## Front panel button and indicator board — 9-way connector

Board silkscreen: `EM7000 Panel V1.0`, `MAX120330`. The board carries ten switches, eight indicator
elements and no active parts. Its counterpart circuitry — the pull-ups, the rail-gating transistor,
the buzzer's drive stage — is all on the main board.

### The connector, and how pin 1 is defined

On the main board the panel's harness ends in the header silkscreened `CON2` (the gauge assembly's is `SP2`, below). It reaches the board in the low-voltage bundle, through the cut-away in the cavity's right wall at Y = 103.5 mm (`reference-machine.md` § Controller enclosure as found, *Where each harness enters the cavity*). The housing is unmarked, off-white to very light brown, with nine contacts, **all nine filled, each by a red wire**: wire colour identifies nothing here, only position does. Its pitch is **1.96 mm ±0.1 mm** and its pins are 0.5 mm thick (inspection items `B1.fam`, `B1.pitch`, `B1.ways`; measured for the pitch, pin thickness and way count, inspected for the housing; the photographs supporting `B1.fam` show both headers side by side, one of them `photos/gauge-connector-sp2.jpg`).

**Family: inferred.** A 2.0 mm pitch, nine-way, 0.5 mm-pin header of this shape is consistent with the JST PH family (header `B9B-PH-K`, mating housing `PHR-9`), and that identification is the author's inference, not the owner's: the owner reported only that pin 1 "aligns with jst standard". It rests on the measured pitch, way count and pin size, and on the housing's look; it is not read off a marking, because the housing carries none. The pitch, way count and pin size are the identification this record stands on. A test fit of a `PHR-9` housing would settle the family.

**Pin 1 carries no mark.** It is defined here by its position and by the signal on it, so a reader can find it without a mark: **pin 1 is the contact nearest the bottom edge of the main board**, the board held in the datum orientation of `reference-machine.md` § Controller enclosure as found (X to the right, Y up, the component face towards the viewer). Confirm it by signal: with a meter, pin 1 is the contact that reaches the buzzer-drive transistor `Q8` (its collector, per sheet 3-3) and pin 2 the contact that reaches the 100 Ω resistor `R59`, which the main board's silkscreen shows beside it. The owner's reason for this end is that, in their words, it "aligns with jst standard" (the owner names no family or part number), and that the main-board resistor numbers beside the pins then fall in step with the pin number. *(Grade: inspected for the position; measured for the signal map below; inspection item `B1.pin1`.)*

### Pin map

Each contact that carries a channel carries the channel `controller-io.md` names, by the name of its row there: pins 3 to 6 and 8 the `PWR`, `MAN`, `ONE`, `TWO` and `PRG` lines, each both a key (the row "Operator-panel keys (`PWR`, `MAN`, `ONE`, `TWO`, `PRG`)") and its indicators (the row "Operator-panel LED indicators"); pin 7 the shared anode rail those indicators are lit from, which that same "Operator-panel LED indicators" row describes and gives no row of its own; pins 1 and 2 the row "Panel buzzer"; pin 9 the switch common, which is ground and carries no channel. The owner's map, worked out on the existing board by finding which silkscreened resistor or transistor each contact reaches (inspection item `B1.map`, **measured**, the main-board designators in brackets as read, checked against the manual's sheet 3-3):

| Pin | Carries | Through | Grade |
|---|---|---|---|
| 1 | Buzzer terminal on the drive side | direct — the drive transistor `Q8` is on the main board | measured |
| 2 | Buzzer terminal on the return side | direct, to the main board's `R59` (100 Ω to ground) | measured |
| 3 | `PWR` group: two switches in parallel, and one indicator cathode | switches via `R41` (1 kΩ); indicator via `R31`; reaches the main board at `R69` | measured; the panel-side components traced earlier (*Traced*) |
| 4 | `MAN` group: two switches in parallel, and two indicator cathodes | switches via `R42`; indicators via `R30` and `R32`; main board `R68` | measured; as above |
| 5 | `ONE` group: two switches in parallel, and one indicator cathode | switches via `R43`; indicator via `R33`; main board `R67` | measured; as above |
| 6 | `TWO` group: two switches in parallel, and two indicator cathodes | switches via `R44`; indicators via `R62` and `R34`; main board `R66` | measured; as above |
| 7 | Indicator common `+V` — the anode rail for every group | gated on the main board by `Q7` (`VCC5` through `Q7`) | measured; `Q7` read from sheet 3-3 |
| 8 | `PRG` group: two switches in parallel, and two indicator cathodes | switches via `R45`; indicators via `R63` and `R35`; main board `R65` | measured; as above |
| 9 | Switch common — the grounded leg of all ten switches, `GND` | direct | measured |

**This is the earlier map counted from the other end.** An earlier version of this file gave pin 1 as the switch common and pin 9 as a buzzer terminal, and said which pin was number 1 was not established. The signals and their order are unchanged; the numbering is reversed, now that pin 1 is defined. **The buzzer's terminal order, previously unestablished, is now read:** pin 1 is on the transistor side and pin 2 on the ground-return side.

The inspection did not read which contact closes to which when a key is pressed (item `B1.keys`), nor which buzzer terminal reaches which pin beyond the map above (item `B1.buzz`): the owner's answer is that the new board does not see either, because the two switches of a key are in parallel and either half gives the same signal, and that the buzzer's pins are already determined by the map. The map is what the new board is built against.

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

The harness has nine conductors. *(Provenance: the gauge assembly's connector is a nine-way
housing, inspected 2026-10-19 — inspection items `B2.ways`, `B2.count` — which replaces the owner's
earlier count of the physical harness, **Observed**. The assembly is a preassembled sandwich that
could not be taken apart, so the conductors were not recounted inside it; the nine contacts are the
count.)* That number
is load-bearing for everything below — two of the conclusions in this section follow from *and there
are nine* and from nothing else — so it is worth stating separately from the reasoning it feeds.

### The connector, and how pin 1 is defined

On the main board the gauge assembly's harness ends in the header silkscreened `SP2`, beside `CON2` (the button panel's). It is **the same type as the panel's**: unmarked, off-white to very light brown, nine ways, 1.96 mm pitch, 0.5 mm pins, the family inferred as JST PH on the same basis (inspection items `B2.fam`, `B2.pitch`, `B2.ways`, grades as for the panel connector above; the photograph supporting `B1.fam`, `photos/gauge-connector-sp2.jpg`, shows both). It reaches the board in the low-voltage bundle through the right wall's cut-away (`reference-machine.md` § Controller enclosure as found). It is **fitted rotated 180° from the panel's**, so **pin 1 is the contact nearest the top edge of the main board**, the board in the datum orientation of `reference-machine.md` § Controller enclosure as found (inspection item `B2.pin1`, inspected). Confirm it by signal: pin 1 is the `VCC5` supply conductor and pin 2 ground. The housing carries no mark of its own; the position and the signal define pin 1, as for the panel.

The machine has since been opened, so this section is no longer uniformly inferred. **What the
driver is and where it sits is now traced.** How the nine conductors are allocated between the
driver, the indicator and the rail is still inferred, and is marked as such row by row.

**The stepper driver is on this board, not on the main board — confirmed by opening the machine.**
The `VID66-08` and its decoupling capacitor were read off the gauge assembly directly. *(Provenance:
**Traced** — parts identified on the physical board.)* This was previously carried as an inference
from the parts' absence from photographs of the main-board spare, and it was the weakest claim in
this section and the premise several others stood on. It now stands on its own.

One discrepancy is recorded rather than reconciled: the decoupling capacitor is **`C17`** on the
board, where the circuit diagram sheet draws `C16` in that position. Whether the sheet is mis-numbered, or
whether both capacitors exist, is not established — and the `U8`/`U9` swap is not evidence either way,
since transposing two designators between two parts is a different error from an off-by-one on a
single one. Nothing here depends on which.

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
reaches this assembly too, on contact 7: brightness is modulated globally across
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

| Contact | Carries | Reaches | Grade |
|---|---|---|---|
| 1 | `VCC5` — `VID66-08` supply | the 5 V rail | measured (main-board side) |
| 2 | Ground | ground | measured (main-board side) |
| 3 | `RST` — driver reset | `RST` of the `VID66-08`; `PC0`, pin 10 of the 28-pin `HT66F50` | measured to the microcontroller; the function at the driver is schematic |
| 4 | `FA` — gauge A step clock | `FA` of the `VID66-08`; `PC6`, pin 12 of the `HT66F50`. The sheet labels this wire `ACLK` | as above |
| 5 | `DIRA` — gauge A direction | `DIRA`; `PC1`, pin 9 of the `HT66F50`. The sheet labels this wire `ADIR` | as above |
| 6 | `WAT` — the water indicator's cathode line | the main board's `R46` pad at 150 Ω and its `R36` pad at about 0 Ω (below) | measured |
| 7 | `VCC5` through `Q7` — the gated anode rail that powers the water indicator | `Q7` on the main board | measured; that the lamp follows the rail is **observed** |
| 8 | `DIRB` — gauge B direction | `DIRB`; `PC2`, pin 20. The sheet labels this wire `BDIR` | as for contact 3 |
| 9 | `FB` — gauge B step clock | `FB`; `PC3`, pin 19. The sheet labels this wire `BCLK` | as for contact 3 |

*(Inspection item `B2.map`: the owner's map, read on the existing board's main-board side by finding which pins each contact reaches, with the manual's sheet 3-3 for the driver's pin names. The record gives the `HT66F50` pin numbers the owner read and does not give the `VID66-08`'s control-pin numbers, which no source held in this repository states (sheet 3-3 does give its `VDD` pins, 16 and 8, below). The far end — each conductor's route inside the gauge assembly to the driver — could not be read because the assembly cannot be taken apart, so that half rests on the sheet and on the nine-conductor count closing exactly.)*

**Which channels these are,** by the names of their rows in `controller-io.md`. Contacts 4 and 5 (`FA`, `DIRA`) serve the row "Espresso "resistance to pour" gauge" (`MOT1`) and contacts 8 and 9 (`DIRB`, `FB`) the row "Milk-temperature gauge" (`MOT2`). Contact 3 (`RST`) is shared by both of those rows' channels: `controller-io.md` has no row of its own for the driver's reset and names it only in its closing tally of the gauge assembly's six pins ("a driver reset"). Contact 6 is the row "Low-water indicator". Contact 7 is the anode rail described in the row "Operator-panel LED indicators", which that row says also reaches the low-water indicator over this harness. Contacts 1 and 2 carry no channel: they are the supply and ground of the assembly.

**This replaces an earlier, inferred allocation**, which had direction and step swapped on gauge A, the water indicator's cathode at conductor 8 and the rail at 9, and `DIRB`, `FB` at 6 and 7. That allocation was inferred from the nesting of the sheet's labels and not read off the board; the owner's map governs, and the sheet's own names for the four step and direction wires (`ACLK`, `ADIR`, `BDIR`, `BCLK`) agree with it.

**What the water indicator's line carries.** The owner measured **150 Ω from contact 6 to the main board's `R46` pad and about 0 Ω to its `R36` pad**, which the owner notes does not match the circuit diagram (item `B2.map`). The owner's reading, a guess and not a finding, is that the `R36` resistor was put on the main board rather than on the gauge assembly, and that the assembly's two water elements are wired in series so that 150 Ω is what the line needs where the sheet's parallel arrangement would give each element 300 Ω. What is recorded is the measurement; its identification is **pending**, settled by `SOL-HW-RETAINED-DEVICE-REMAINING-CHARACTERISTICS-RECORDED` (§ What each retained device imposes on whatever drives or reads it, *Series resistances inherited on the front assemblies*).

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
`VID6608` datasheet, Hong Kong VID Company, revision 1, 2022, read. The part number is read off the board itself; that
the fitted part matches this *revision* of the datasheet is not established, and a second-sourced or
older variant could carry different thresholds.)*

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
lines must clear a 3.15 V input threshold that a 3.3 V part is not guaranteed to reach. The gated anode rail reaches this assembly too, on contact 7, but it
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

### What the inspection settled, and what it left

The rail question is settled the other way round from an earlier reading of this section: the water
lamp dims in step with the power element, so both front assemblies hang off the one gated rail. With
that, the conductor count closes exactly and the six-or-seven pin question is closed at **six** — the
totals elsewhere in this project are built on six and need no spare held against this.

**Six is settled, and the premise it stood on is now traced rather than inferred.** The driver is on
this assembly; the machine was opened and the part read off the board. The question that would have
changed the whole channel — whether a 16-pin part is there at all, and so whether the controller owes
six logic pins or eight phase-drive lines and a driver in the parts list — is closed.

What remains changes no count. Where the driver's two supply pins are joined is one node either way.
Whether the fitted part matches the datasheet revision read here is worth knowing before its
thresholds are relied on, but it would move a figure rather than a channel.

## The other retained harnesses

Every harness below reaches the main board in the low-voltage bundle that enters the cavity through the cut-away in the right wall, 33 mm wide and centred at Y = 103.5 mm (`reference-machine.md` § Controller enclosure as found, *Where each harness enters the cavity*). Their shortest wire reaches 40 mm into the cavity and their longest 65 mm. Grades are the shared ones. Each entry cites the inspection item it was read against.

### Knob microswitches: hot water and steam

**One harness and one connector serve both switches.** The housing is unmarked and white, four ways, pitch **1.95 mm ±0.1 mm**, pins 0.5 mm thick (inspection items `B3.fam`, `B3.pitch`, `B3.ways`, `B4.fam` to `B4.ways`; measured for the pitch and count, inspected for the housing; the photograph supporting `B3.fam` shows it). The family is not identified; the pitch, way count and pin size are the identification, and they match the panel and gauge headers' class (a 2.0 mm family) within the pitch tolerance, which is not an identification.

**Pin 1 carries no mark.** It is the contact nearest the right edge of the main board, the board in the datum orientation of `reference-machine.md` § Controller enclosure as found (the owner's convention, taken from the panel connector's: inspection item `B3.pin1`, inspected), and it is the hot-water microswitch's red lead.

| Pin | Lead | Goes to | Grade |
|---|---|---|---|
| 1 | Red | Hot-water knob microswitch (`S7`, `HOT`), one terminal | measured (inspection item `B3.map`) |
| 2 | Black | Hot-water knob microswitch (`S7`, `HOT`), the other terminal | measured |
| 3 | Red | Steam knob microswitch (`S8`, `STM`), one terminal | measured |
| 4 | Black | Steam knob microswitch (`S8`, `STM`), the other terminal | measured |

**Channel.** Both switches serve the row "Control-knob microswitches (`S7` hot water, `S8` steam)" in `controller-io.md`, one signal per knob: pins 1 and 2 the hot-water switch (`S7`), pins 3 and 4 the steam switch (`S8`).

Each switch is read through two conductors, so a switch's polarity is not an interface property: a contact has no polarity. Which lead of a switch is the grounded one was not recorded.

### Flow meter

Header `CZ1` on the main board: unmarked, white, **three ways, pitch 2.54 mm, 0.63 mm pins** (inspection items `B6.fam`, `B6.pitch`, `B6.ways`; measured for pitch, pin thickness and count, inspected for the housing; photograph supporting `B6.fam`). The family is not identified. **Pin 1 is the contact at the square pad**, on the left side of the board, the board in the datum orientation (item `B6.pin1`, inspected).

| Pin | Lead | Carries | Grade |
|---|---|---|---|
| 1 | Red | `VCC5`, the 5 V supply | measured (inspection item `B6.map`) |
| 2 | Yellow | Ground | measured |
| 3 | Black | Signal, to `PC4`, pin 18 of the 28-pin `HT66F50` | measured |

**Channel.** The signal on pin 3 is the row "Flow meter (water path, suction line ahead of coffee pump)" in `controller-io.md`; pins 1 and 2 are its supply and ground, which that row does not count as channels.

**2 kΩ was read between pin 1 and pin 3** on the main board, which matches the sheet's `R51` pull-up from the signal to `VCC5` (measured, same item). That resistor is on the board being replaced: it is part of the conditioning the new board chooses and not a property of the meter.

### Temperature sensors

Three headers on the main board take the three two-wire leads. Each is unmarked white, **two ways, pitch 2.54 mm, 0.63 mm pins**, of the same type as the flow meter's; the coffee sensor's is silkscreened `RT1` (inspection items `B12.fam` to `B14.map`; measured, inspected; the headers are shown close up in the photograph supporting `B12.map`, `photos/ntc-two-pin-headers.jpg`). **Pin 1 is the square solder pad.** The steam-wand sensor's connector is fitted rotated 180° from the other two, so its pin 1 is at the opposite end; the coffee connector's silkscreen `RT1` is the only designator the inspection read, and which of `RT2` and `RT3` the steam-block and steam-wand headers carry was not recorded.

| Connector | Pin | Lead | Goes to |
|---|---|---|---|
| Coffee thermoblock temperature sensor | 1, 2 | black, black | the two terminals of the coffee thermistor |
| Steam thermoblock temperature sensor | 1, 2 | as the coffee sensor (item `B13.map`) | the two terminals of the steam-block thermistor |
| Steam wand temperature sensor (conduction disc, wand exterior) | 1, 2 | as the coffee sensor (item `B14.map`) | the two terminals of the wand thermistor |

**Channels.** The three headers serve, in the table's order, the rows "Coffee thermoblock temperature sensor", "Steam thermoblock temperature sensor" and "Steam wand temperature sensor (conduction disc, wand exterior)" in `controller-io.md`; each sensor is one channel across its two pins.

*(Grade: inspected, for the lead colours and the terminal order: the leads are two-terminal NTC thermistors and either terminal order works, as the owner notes. The parts list names the coffee lead red and the wand lead white; the owner read black at the connector's contacts, and the two are not reconciled here; nothing depends on it.)*

### Tank water-level sensor: no harness

The level sensor has no harness and no connector. Its reed element is **mounted with its body on the back face of the main board** at the position `reference-machine.md` § Controller enclosure as found gives, its leads 20 mm apart through holes, and is covered with insulating compound; the board's silkscreen outlines it `WAT` (inspection items `B5.fam`, `B5.pitch`, `B5.ways`, `B5.pin1`, `B5.map`; inspected, measured for the pitch). It is two terminals, so there is no pin 1. Both terminals reach the board's own copper: nothing leaves the board for it. It passes to the replaced side with the board, and a replacement provides the level channel at that position (`DEC-DEVICE-RETENTION-BOUNDARY`, version 3).

## Mains terminals and the mains lead arrangement

### The nine terminals

All mains wiring meets the original board at nine 6.3 mm male tabs on its left edge, each mated with a fully insulated, blue-sleeved female push-on terminal on the wire (inspected, from the photographs supporting items `C0.entry`, `C1` and `C2.T1.label`: `photos/mains-bundle-entry.jpg` and `photos/mains-terminals-with-ruler.jpg`). The tab is **6.36 mm ±0.1 mm wide** (item `C0.tab`, measured), its centre about **8.2 mm ±1 mm** from the board's left edge (the owner's "approx" estimate in the note to item `C0.reach.max`, owner statement; the tolerance is this record's, set from the ruler photograph supporting `C0.y0`, `photos/mains-terminals-with-ruler.jpg`, in which the centres of the silkscreen slot outlines read 8.7 mm from the edge, inside it). Silkscreen names each, and numbering from the bottom of the board going up (the board in the datum orientation) gives the order below. The wires are braided and bundled with cable ties along the left side, split out at their terminals, and cross the board's left edge between Y = 10 mm (the lowest) and Y = 110 mm (the highest), ±1 mm (inspection items `C0.y0`, `C0.y1`, measured: positions of the wires where they cross the edge, not of the tabs). The bundle enters the cavity at the tabs: the whole left side of the cavity is open except 8 mm at the top and 8 mm at the bottom of that side, and each wire enters where its tab is (owner statement, 2026-10-20, item `L2`, ±2 mm; `reference-machine.md` § Where each harness enters the cavity). The height of each tab's centre is read from the photograph supporting `C0.y0`, `photos/mains-terminals-with-ruler.jpg`, which has a rule in frame, and is given in the table below.

| # | Silkscreen | Wire colour | What the lead goes to | Tab-centre Y: board-edge frame (datum frame) | Grade |
|---|---|---|---|---|---|
| 1 | `LINE1` | red | Out to the machine's loads: it daisy-chains to the pumps, the valves and the thermoblocks as the fixed wire. It reads 0 Ω to `LINE` on the board | 12.0 mm (14.5 mm) | inspected (the routing); measured (the 0 Ω); the datum-frame figure inferred (adds the inferred 2.5 mm offset) |
| 2 | `LINE` | brown | The mains active, in from "mains in" (the owner's words, item `C2.T1.feed`); no device between mains in and `LINE` is named, and the device upstream of mains in is unread | 20.6 mm (23.1 mm) | measured, by continuity to mains in; the datum-frame figure inferred (adds the inferred 2.5 mm offset) |
| 3 | `NEUTRAL` | blue | The mains neutral | 29.4 mm (31.9 mm) | inspected; the datum-frame figure inferred (adds the inferred 2.5 mm offset) |
| 4 | `STMHEATER` | black | The **steam thermoblock element**, through the steam thermostat wired in series | 51.6 mm (54.1 mm) | inspected; the datum-frame figure inferred (adds the inferred 2.5 mm offset) |
| 5 | `COFHEATER` | red | The **coffee thermoblock element**, through the coffee thermostat wired in series | 65.1 mm (67.6 mm) | inspected; the datum-frame figure inferred (adds the inferred 2.5 mm offset) |
| 6 | `COFVALVE` | brown | The **two-way coffee valve** (`2T0607W`), which connects the coffee block's second outlet to the drain | 78.1 mm (80.6 mm) | inspected; the datum-frame figure inferred (adds the inferred 2.5 mm offset) |
| 7 | `COFFPUMP` | white | The **coffee pump** (Ulka EP5), through the pump thermostat wired in series | 90.4 mm (92.9 mm) | inspected; the datum-frame figure inferred (adds the inferred 2.5 mm offset) |
| 8 | `STEAMPUMP` | black | The **steam pump** (JYPC-4) | 100.4 mm (102.9 mm) | inspected; the datum-frame figure inferred (adds the inferred 2.5 mm offset) |
| 9 | `HOTVALVE` | blue | The **three-way valve** (`3T0618W`), which routes the coffee block's outlet to the group or the hot-water outlet | 110.4 mm (112.9 mm) | inspected; the datum-frame figure inferred (adds the inferred 2.5 mm offset) |

*(Inspection items `C2.T1.label` and `C2.T1.dest`; the labels are legible in `photos/mains-terminals-with-ruler.jpg`; the owner read the table off the board and the loom, `C2.T2.*` to `C2.T9.*` referring back to it.)* **Tab-centre heights (inspected, read off the ruler photograph supporting `C0.y0`, `photos/mains-terminals-with-ruler.jpg`, ±1 mm in the board-edge frame, ±1.5 mm in the datum frame).** The rule lies along the board's left edge with its zero at the board's bottom edge, and the board-edge figure is the rule's reading at the centre of each tab's silkscreen slot outline; the ±1 mm is the rule's 0.5 mm graduation, the parallax between the rule and the board, and the judgement of a centre by eye. The datum figure adds 2.5 mm, the offset between the rule's zero and the datum wall, which is inferred from the photograph's own mounting holes: it reads mounting point 1's centre at 3.5 mm and point 3's at 121.5 mm against the 6.5 mm and 123.5 mm of `reference-machine.md` § Controller enclosure as found, offsets of 3.0 mm and 2.0 mm, mean 2.5 mm, and the spread is why the datum tolerance is wider. The owner's lowest and highest crossings, 10 mm and 110 mm, do not say which of the two frames they were read in; they are carried as given, and the highest tab's board-edge reading, 110.4 mm, agrees with the owner's 110 mm in the board-edge frame. The owner's 10 mm differs from the lowest tab's centre (12.0 mm) by 2 mm, because it is where the wires cross the board's edge, not a tab position. The channels `controller-io.md` names for the load terminals, by the names of its rows: terminal 4 "Steam thermoblock element switching", terminal 5 "Coffee thermoblock element switching", terminal 6 "Two-way solenoid valve, on the coffee thermoblock (`2T0607W`)", terminal 7 "Coffee pump", terminal 8 "Steam pump", terminal 9 "Three-way diverter solenoid valve, near the hot water arm (`3T0618W`)". Terminals 1 to 3 are the mains supply and carry no channel. There is **no tenth terminal** and **no earth terminal**: the earth conductor is not terminated on the control board. A green-and-yellow braided conductor runs in the mains bundle past the board's left edge (inspected, the photograph supporting item `C0.entry`, `photos/mains-bundle-entry.jpg`), and the board has no tenth terminal for it (item `C2.T10`, not applicable); the owner's statement is that it goes to the machine's metal parts in the top section of the machine (`reference-machine.md` § Controller enclosure as found, *What the walls are made of*; owner statement). This also settles which tag drives which physical valve: `COFVALVE` drives the two-way valve and `HOTVALVE` the three-way, which an earlier reading of the circuit diagram's tags left open.

**How each load's leads terminate.** At the board, every load's lead ends in the insulated female push-on terminal above, on the tab named. At the device, the three-way valve coil ends in male blade tabs (inspected, from the photograph supporting item `D2.v`, `photos/three-way-valve-coil-marking.jpg`, which shows three blade surfaces: one face-on, one behind it and one edge-on below, so it does not establish that there are exactly two; a coil carries two connections, and what the third blade is, an earth tab for instance, was not identified, so the valve's earth arrangement is not established by this record); the two-way coil's are inferred to be the same, since the photograph supporting `D1.v`, `photos/two-way-valve-coil-marking.jpg`, shows only the label. The width of the valve spades and how the far end of each pump and element lead terminates were not recorded, and the board's fit does not need them: the harness is reused as it is, and only the female spade on the board end matters, whose tab width is the 6.36 mm above (owner statement, 2026-10-20, item `L4`; out of scope for the controller board's fit, not pending). The wires which the nine terminals carry are the only mains conductors that reach the original board.

### The source of each live feed

**The original board takes one live feed, not two.** The two terminals named `LINE` and `LINE1` read 0 Ω between them on the board (inspection item `C2.T1.feed`, measured, machine unplugged): they are one node. `LINE` is wired to "mains in", the owner's words for the point where the machine's supply enters, found by continuity, and the owner names no device between mains in and `LINE`, and the device upstream of it is unread (the record carries only the owner's words "mains in"); `LINE1` is the same node leaving the board for the loads, the wire the owner describes as the fixed one that daisy-chains round to them. The owner's reading is that it is a pass-through so that unplugging the board leaves nothing live that is still connected elsewhere. So the board's two "live" terminals are an inlet and its onward outlet, not two supplies: the second live feed the working documents asked about is the first one leaving the board, not a second source.

**What was seen of fuses, and that no thermostat is shared.** The owner saw **no fuse along the visible loom at the board end except `F1`**, the board's own 5 A fuse marked `F5A 250V` (`reference-machine.md` § Heating and load, *Mains fuse*), and no thermostat shared between loads (item `C3.feeds`, inspected; the owner's words are "no fuses that I can see except F1"). The owner confirms that `F1` is the only fuse found, 5 A, near the `LINE` tab, and that no thermal fuse was seen along the visible loom or on the board: none seen at the board end, none found by the owner (owner statement, 2026-10-20, item `L5`; `reference-machine.md` § Protection, *Thermal fuse*). A fuse inside a heater assembly would not be visible from the loom and is not part of what the board wires, and the far ends of the pumps' and elements' leads are out of scope for the board's fit (item `L4`), so a fuse beyond the visible loom is neither seen nor excluded. **Neither pump branch was seen to carry a fuse of its own** along the visible loom (items `C5.cof`, `C5.stm`, both none, inspected, with the same limits): the working design's earlier reading that the pumps already carried branch fuses is not supported by what was seen. The three thermostats are in series with their own loads' leads, not shared: the steam element's, the coffee element's and the coffee pump's (items `C2.T1.label`, `C6`, inspected). **That the steam pump carries none is inferred, not seen:** the owner's label for the first terminal says "coffee pump via series thermostat on pump" (item `C2.T1.label`) and names the coffee pump alone as the one in series with the pump thermostat (item `C6`, "Coffee pump - in series with coffee pump white wire"), and the parts list itemises a single pump thermostat; the far ends of the pumps' leads were not recorded, so a thermostat at the steam pump's far end is not excluded by anything read.

**How the owner's thermostat note was read.** The note to item `C2.T1.label` says the thermostats are "wired in series to mains brown wire". It is read here as each thermostat sitting in series with its own load's lead, as the table above has it for terminals 4, 5 and 7, and not as one thermostat on the brown `LINE` wire, because a thermostat on `LINE` would be shared by every load, against the owner's finding that none is shared (item `C3.feeds`) and the owner naming no device between mains in and `LINE`. The owner has not confirmed this reading; it is the record's.

**Which conductor of a load the original board's switching device interrupts is not established**, and it constrains nothing the floorplan uses. The circuit diagram draws each relay contact on the line side (`reference-machine.md` § Heating and load, the table of what the OEM boards switch each load with); the owner's trace shows `LINE1` going to the loads as the fixed wire and terminals 4 to 9 as the switched leads, which reads as switching on each load's other lead, and the two readings are not reconciled here. That trace of each load's other lead, made with the machine unplugged, is **pending**, settled by `SOL-HW-RETAINED-DEVICE-REMAINING-CHARACTERISTICS-RECORDED`. Which conductor the replacement boards' switches interrupt is a design choice of the board that carries them, made with that trace in hand.

## What each retained device imposes on whatever drives or reads it

For each retained device, the constraint a replacing board must meet, by device class. **Nothing in this section was measured with the machine energised.** A current comes from a device's marking or datasheet; where neither gives one it is a bound with its derivation shown. Sources and grades are the shared ones. The margin a design applies, and the circuits that meet these characteristics, are the design's, not this record's.

A mark of **pending** names the work that will settle it, `SOL-HW-RETAINED-DEVICE-REMAINING-CHARACTERISTICS-RECORDED`, which records each characteristic below that the first recording could not establish, each with its value, unit, grade and source, in the entry the mark stood in, and removes the mark in the same change.

### Solenoid valves: the two coils

| Entry | Two-way valve coil (`2T0607`) | Three-way valve coil (`3T0618`) | Grade and source |
|---|---|---|---|
| Marking | JLT `SV(X)T`, AC 230 V 50 Hz, 9–13.5 VA, TA 120 °C, TF 140 °C, insulation class H, ED 100 %, IP00, VDE-marked | As the two-way, type `3T0618`, date code `16 J 26` | inspected; the photographs supporting items `D1.v` (`photos/two-way-valve-coil-marking.jpg`) and `D2.v` (`photos/three-way-valve-coil-marking.jpg`) (some characters are worn; the type and the 9–13.5 VA are legible on both) |
| **Coil voltage** | 230 V AC, mains | 230 V AC, mains | inspected, `D1.v`, `D2.v` |
| Cold resistance | 2.496 kΩ at 25 °C | 2.497 kΩ at 25 °C | measured, `D1.r`, `D1.t`, `D2.r`, `D2.t` |
| **Steady current**, at the top of the span (253 V) | at most **64.6 mA rms** | at most **64.6 mA rms** | inferred, below |
| **Inrush current**, at the top of the span | at most **101.4 mA rms**, **143.3 mA** peak | at most **101.3 mA rms**, **143.3 mA** peak | inferred, below |

Both coils together: at most 129 mA rms steady and 203 mA rms inrush, if both are energised at once.

*Steady current:* the marking gives 9–13.5 VA at 230 V, so 13.5 ÷ 230 = 58.7 mA at the marking's upper end. A coil's current is proportional to its supply, so at 253 V it is 58.7 mA × 253 ÷ 230 = **64.6 mA**. The marking does not say which end of its range is the holding figure, so the upper end is taken. *Inrush current:* a bound, **253 V ÷ the cold resistance**: 253 ÷ 2496 Ω = 101.4 mA rms, and 253 × √2 ÷ 2496 Ω = 143.3 mA for the first half-cycle's peak. It overstates an inductive coil's current, whose impedance exceeds its resistance, and the resistance read cold is the lowest the coil has; it does not understate it. A device must switch an inductive load at mains voltage and carry the inrush bound for the first half-cycles.

### Pumps: running current

| Entry | Coffee pump (Ulka EP5) | Steam pump (JYPC-4) | Grade and source |
|---|---|---|---|
| Nameplate voltage | 230 V | AC 220–240 V | inspected, items `D3.v`, `D4.v`; the nameplate gives no current (`D3.a`, `D4.a`) |
| Nameplate power | 48 W | 22 W | inspected, `D3.w`, `D4.w` |
| Resistance read, one probe polarity | open | open | measured, `D3.rf`, `D4.rf` |
| Resistance read, probes swapped | 15.17 MΩ | 19.13 MΩ | measured, `D3.rr`, `D4.rr` |
| **Running current at the top of the span (253 V)** | at most **0.38 A rms** | at most **0.174 A rms** | inferred, below |

**The coil's resistance cannot be read**: both polarities read open or in the megohms, which is what a series diode does to a meter whose test voltage is below the junction's threshold, so a diode in series with the coil hides it (inferred from the two readings). The bound is therefore worked from the nameplate power: **current = nameplate power ÷ (253 V × a power-factor floor of 0.5)**. Coffee: 48 ÷ (253 × 0.5) = **0.3794 A, taken as 0.38 A**. Steam: 22 ÷ (253 × 0.5) = **0.174 A**. The power-factor floor, 0.5, is a **project assumption, to replace** with a measured figure when one exists; the nameplate powers are inspected figures. The nameplate states its power at its rated voltage, 230 V (coffee) and 220–240 V (steam), and the bound takes it at 253 V as the criterion for it directs; a coil whose power rose with the square of its supply would instead draw 0.46 A (coffee, from 230 V) and 0.19 A (steam, taking the 240 V end of its 220–240 V), which a design margin accounts for and this record does not. The working design's earlier figure of 0.1–0.22 A for both pumps is superseded.

### Heating elements: resistance

| Element | Resistance | Conditions | Grade and source |
|---|---|---|---|
| Coffee thermoblock element | 52.7 Ω; **52.9 Ω** on the second reading | 20.3 °C ambient; 25.4 °C ambient | measured; `reference-machine.md` § Heating and load, and inspection items `D5.r`, `D5.t` |
| Steam thermoblock element | 47.0 Ω; **47.2 Ω** on the second reading | 20.3 °C ambient; 25.4 °C ambient | measured; as above, `D6.r`, `D6.t`. Both are lower bounds, as the steam caveat in `reference-machine.md` says |

The figures that follow from them, the currents and the power across the span, are `reference-machine.md`'s and `component-specification.md`'s, and stand: they use the lower, first readings, which give the higher current.

### Keys and microswitches: contact type and rating

| Device | Contact type | Rating | Grade and source |
|---|---|---|---|
| Each of the ten panel key switches | A momentary single-pole tact switch of the four-pad surface-mount form, no printing on the body (item `D8.keys`, inspected; the photograph supporting it shows four pads) | **Pending**, settled by `SOL-HW-RETAINED-DEVICE-REMAINING-CHARACTERISTICS-RECORDED` — no printed rating | inspected (the type); pending (the rating) |
| Each of the two knob microswitches | Two terminals read, a red and a black lead each (above). Whether the contact closes or opens when the knob is turned is **pending**, settled by `SOL-HW-RETAINED-DEVICE-REMAINING-CHARACTERISTICS-RECORDED` | 250 V, 3 A each | parts list (the rating, `reference-machine.md` § Already fitted); pending (the form) |

The panel's switches carry a 5 V logic signal through a 1 kΩ resistor to ground and nothing else; a replacing input must treat each as a dry contact to ground wanting a pull-up, which is all the retained key imposes (`DEC-DEVICE-RETENTION-BOUNDARY`).

### Temperature sensing elements

| Element | Resistance at the reference temperature | Curve constant | Grade and source |
|---|---|---|---|
| Coffee thermoblock temperature sensor | 97.7 kΩ at 25.4 °C | **Pending**, settled by `SOL-HW-RETAINED-DEVICE-REMAINING-CHARACTERISTICS-RECORDED` | measured, items `D7.cof.r`, `D7.cof.t`; no printing on sensor or lead (`D7.cof.mark`, inspected) |
| Steam thermoblock temperature sensor | 95.8 kΩ at 25.4 °C | **Pending**, settled by `SOL-HW-RETAINED-DEVICE-REMAINING-CHARACTERISTICS-RECORDED` | measured, `D7.stm.r`, `D7.stm.t`, `D7.stm.mark` |
| Steam wand temperature sensor (conduction disc, wand exterior) | 98.3 kΩ at 25.4 °C | **Pending**, settled by `SOL-HW-RETAINED-DEVICE-REMAINING-CHARACTERISTICS-RECORDED` | measured, `D7.wand.r`, `D7.wand.t`, `D7.wand.mark` |

The three are consistent with 100 kΩ nominal at 25 °C, which the panel sheet's divider also reads. The reading was taken with a multimeter beside the machine (the owner's note on `D7.cof.t`). No marking gives a curve constant.

### Flow meter

**Supply: 5 V** (`VCC5`, pin 1) from the board, read by continuity and sheet 3-3 (measured, inspected as above); the meter's own permitted supply range was not read. **Output: a digital pulse train on pin 3**, held up on the original board by 2 kΩ to 5 V; whether it is open-drain or push-pull is **pending**, settled by `SOL-HW-RETAINED-DEVICE-REMAINING-CHARACTERISTICS-RECORDED`. The constraint on a replacing input is that it reads that pulse train, pulled up if the output is open-drain, which is what a pull-up of that kind implies.

### Buzzer

**Type: pending**, settled by `SOL-HW-RETAINED-DEVICE-REMAINING-CHARACTERISTICS-RECORDED` (a magnetic sounder, which needs a drive waveform, or a self-driving piezo, which needs only a level). **Drive as the original board gave it:** the buzzer's two terminals are on the panel harness at pins 1 and 2; pin 1 is on the collector of a 2N5401 PNP stage from the 5 V rail, pin 2 returns through 100 Ω to ground, with no diode across the buzzer on the drawing, and the stage sounds the buzzer when its input is pulled low (schematic, sheet 3-3, and the measured map above; *the stage is on the replaced board, so the drive is the replacement's to design*, and whatever it is it must suit the type once recorded).

### Gauge driver: input thresholds

The driver is the `VID66-08`, two channels, on the retained gauge assembly. **The constraint is the datasheet's figure: `VIH` at least 3.15 V and `VIL` at most 1.35 V**, absolute across a `VDD` of 4.5–5.5 V, on all five control lines (`RST`, `FA`, `DIRA`, `FB`, `DIRB`) (published unverified, read at source: *VID6608* datasheet, Hong Kong VID Company, revision 1, 2022, as § The gauge driver's control lines above sets out in full). **The revision of the fitted part is unread:** the gauge assembly is a preassembled sandwich that could not be taken apart, so the marking on the chip beyond the part number was not read, and the figures are the datasheet's for the part number the service documents name (item `D10.ic`; the part number itself is confirmed on the gauge board). A replacing design meets the datasheet figure with margin. Nothing is held pending for the thresholds.

### Panel indicator elements and the low-water indicator

| Entry | Value | Grade and source |
|---|---|---|
| Eight panel indicator elements, forward voltage | **Pending**, settled by `SOL-HW-RETAINED-DEVICE-REMAINING-CHARACTERISTICS-RECORDED` | — |
| Low-water indicator elements (two, sharing a cathode), forward voltage | **Pending**, settled by `SOL-HW-RETAINED-DEVICE-REMAINING-CHARACTERISTICS-RECORDED` | — |
| Current the original drive gave each | Worked from the forward voltage, so **pending** with it, settled by `SOL-HW-RETAINED-DEVICE-REMAINING-CHARACTERISTICS-RECORDED`: the anode rail is `VCC5` through `Q7`, each element then has its series resistor and a sink on its line | inferred from the circuit, which sheet 3-3 draws |
| The anode rail | `VCC5` through `Q7` (a `2N5401` PNP), gated and modulated on the replaced board, reaching the panel at pin 7 and the gauge assembly at contact 7 | measured (the reach), schematic (the part) |

### Protective-chain devices whose wiring reaches the board

Three devices' wiring reaches the board: the two thermoblock thermostats and the coffee pump's thermostat. Each is in series with its load's lead, at the terminal in § Mains terminals. **What each contact carries** is its load's current: for the coffee element at most **4.80 A** at 253 V, for the steam element at most **5.38 A** (a ceiling, from the lower-bound resistance), and for the coffee pump at most **0.38 A** (all inferred, from the figures above). **Their contact ratings are pending**, settled by `SOL-HW-RETAINED-DEVICE-REMAINING-CHARACTERISTICS-RECORDED`. No lead of the nine-lead table or of the harnesses enumerated here goes to an over-pressure relief, so none is wired to the board (inferred from those tables; what a relief is and does is not established, `reference-machine.md` § Protection). No thermal fuse was seen on the board or along the visible loom (owner statement, 2026-10-20, item `L5`; `reference-machine.md` § Protection), so none is recorded in any of the nine leads; one inside a heater assembly would not be wired to the board.

### Series resistances inherited on the front assemblies

| Where | Resistance | Grade and source |
|---|---|---|
| Panel, each key pair | 1 kΩ in series with the pair (`R41` to `R45`) | schematic (sheet 3-3); the same positions were read on the spare-part panel board (an earlier *Traced* reading) |
| Panel, each indicator element | 330 Ω for the `PWR` element, 300 Ω for the others | schematic (sheet 3-3); **the values on this machine's own panel were not read, and are pending**, settled by `SOL-HW-RETAINED-DEVICE-REMAINING-CHARACTERISTICS-RECORDED` |
| Gauge assembly, the water indicator's line | **150 Ω** from contact 6 to the main board's `R46` pad, about 0 Ω to its `R36` pad | measured (§ Gauge and water-indicator board); what the 150 Ω is, **pending**, settled by `SOL-HW-RETAINED-DEVICE-REMAINING-CHARACTERISTICS-RECORDED` |
| Gauge assembly, the stepper driver's control lines | None drawn: the control lines go straight to the microcontroller; `R52` and `R53`, 10 kΩ, pull `ACLK` and `BCLK` up to `MVCC` on the main board | schematic (sheet 3-3) |

### Classes this list does not name

The retained gauge stepper motors, `MOT1` and `MOT2`, are driven by the retained driver and not by the controller: they impose nothing on the replacing board. The tank reed's element is on the board being replaced; if it is lifted and reused it imposes a contact rating on the channel that reads it. Its body is covered in white insulating compound and no marking could be read (item `D8.reed.mark`, inspected), so that rating is **pending**, settled by `SOL-HW-RETAINED-DEVICE-REMAINING-CHARACTERISTICS-RECORDED`.

## Open

- Where the `VID66-08`'s two supply pins are joined — on the main board or on the gauge assembly.
  They are one node either way, so this changes no count.
- Whether the sheet's `C16` and the board's `C17` are the same part under two numbers, or two parts.
- The fitted driver's datasheet revision is unread, because the gauge assembly could not be taken apart;
  the constraint is the datasheet figure, which a replacing design meets with margin, so nothing is
  held pending for the thresholds (§ What each retained device imposes, *Gauge driver*).
- **Pending, each settled by `SOL-HW-RETAINED-DEVICE-REMAINING-CHARACTERISTICS-RECORDED`:** the
  buzzer's type; the forward voltage of each panel indicator element and of the low-water elements,
  with the series resistance on this machine's panel and what the water line's 150 Ω is; the contact
  rating of each panel key and the contact form of each knob microswitch; the tank reed element's
  rating; the flow meter's output type; the temperature sensing elements' curve constant; the contact
  ratings of the three thermostats; and which conductor of each load the original board's switching device interrupts.
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

## Main-board sheet 3-3 read from the page images (2026-10-12)

Read directly from the rendered service-manual page 25 (circuit diagram sheet 3-3) at 200 and 400 dpi.
The manual's labelling is unreliable (see above), so the physical boards still win; this records what the
drawing shows. Rail voltages are not printed: `VCC5` is read as 5 V because the `MC34063` feedback
divider on sheet 3-1 is 3 kΩ over 1 kΩ on a 1.25 V reference, and `VCC12` as 12 V from its name.

- **Buzzer stage.** `Q8`, `2N5401` PNP, emitter on `VCC5`. Base through `R57` 1 kΩ from `U8` pin 11 (`PC7`), with `R58` 10 kΩ from the base to `VCC5`. Collector to the buzzer `BZ`, whose other side goes through `R59` 100 Ω to ground. **No diode across the buzzer** and no value or polarity on its symbol. The stage is active-low: the output pulls the base low to sound it.
- **Anode-rail gate.** `Q7`, `2N5401` PNP, emitter on `VCC5`, base through `R39` 2 kΩ from `U8` pin 15 (`PD1`), `R40` 100 kΩ from the base to `VCC5`. The collector is the shared anode rail for every indicator. Nothing on the drawing shows PWM, though it is how the lamp is observed to ramp.
- **Indicators.** Series resistors: `R30`, `R31` 330 Ω for `PWR`, and 300 Ω for every other element (`R32A` to `R36B`). Each group's cathode node joins its key line.
- **Keys and switches.** Each `S1` to `S5` has a 1 kΩ (`R41` to `R45`) in series between the line and the switch, whose other side goes to `MGND`; `S6`, `S7` and `S8` (`WAT`, `HOT`, `STM`) likewise through `R46` to `R48`. Each line then reaches the MCU through a 47 Ω (`R62` to `R69`). **No pull-up resistor or pull-up rail is drawn on any of these lines**, so the OEM appears to rely on the MCU's own pull-ups. **This disagrees with the earlier text above that reads the sheet's 1 kΩ resistors as pull-ups:** on the drawing they sit between the line and ground, in series with the switch. Which reading is right on the physical board is to be checked with a meter (a pressed key should read about 1 kΩ plus 47 Ω to ground at the main-board connector).
- **Gauge driver.** `U9` `VID66-08`, both `VDD` pins on `VCC5` with `C16` 104. Control lines go straight to the MCU with no series resistors; `R52` and `R53` 10 kΩ pull two of them (`ACLK` and `BCLK`) up to `MVCC`. Which MCU line is `RST`, `DIRA`, `FA`, `DIRB` and `FB` was inferred from the label nesting when this was read; it is now read off the board (§ Gauge and water-indicator board, the contact table).
- **Rails.** `MVCC` (the MCU rail) is `VCC5` through jumper `JP1` and diode `D11` (1N5817). How `Q9` gates it is unreadable.
- **Thermistors.** `RT1` to `RT3` are 100 kΩ, each with a 10 kΩ 1% resistor (`R54` to `R56`) up to `MVCC` and a 104 capacitor to ground.
- **Flow meter `CZ1`.** Pin 1 `VCC5`, pin 2 ground, pin 3 signal, with `R51` 2 kΩ from the signal to `VCC5`.

