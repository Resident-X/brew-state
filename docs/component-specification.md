# Component specification and list

**This file is local, like `reference-machine.md` and `controller-io.md`.** It answers the question
those two leave open: given every channel the machine needs, what property must each part have, does
a candidate controller actually serve them all at once, and what does the whole come to.

It is written by hand in this slice. `DEL-COMPONENT-SPECIFICATION.C6` — regenerating this document
and its list from the graph — is a later criterion of the parent task and is not attempted here.

Three rules govern what may appear below.

**Parts are specified by property, not by part number.** Each switched load names what its device has
to do, carry, dissipate and fail into. A named part is an example that satisfies the row, never the
row itself. This is deliberate and it is what makes the document usable: a part recovered from
another machine can be held against a property, but not against someone else's part number.

**Every figure traces to a declaration.** Currents are derived from the measured element resistances
in `reference-machine.md` § Heating and load at the supply span that document declares. Nothing here
introduces a figure that section does not carry, and where a figure cannot be derived the row says so
rather than estimating.

**Nothing here selects the machine's controller.** `DEC-PREHARDWARE-TARGET-FAMILY` and
`DEC-HEATER-DRIVE-GATED-BY-SUPERVISION` both leave that open, answered later against measured plant
parameters. What this document does is show that a candidate is *adequate* — an input to that
selection, not the selection.

## What the supply is, and what changes off it

Everything below is stated against a declared supply rather than against this machine's. The
reference build runs at 230–240 V, 50 Hz (`reference-machine.md` § Supply), on a circuit assumed to
be 10 A. Two things follow for an adopter elsewhere, and both are properties of their supply rather
than of this design:

- **Frequency sets the switching cadence, not the control period.** Heater devices are specified as
  commandable once per supply half-cycle. That is 100 commands per second at 50 Hz and 120 at 60 Hz;
  the device requirement is identical either way, and `DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM` carries
  the residual forward so a non-integer number of half-cycles per control step behaves exactly as an
  integer number does.
- **Voltage sets the current, and the current sets the device.** These elements are fixed
  resistances, so halving the supply halves the current and quarters the power: the same two
  elements on 120 V would draw about 2.3 A and 2.6 A and deliver roughly a quarter of their rated
  heat, which is a different machine rather than the same one on a different plug. An adopter
  building to the same *heating* on a 120 V supply needs 120 V-rated elements instead, and
  `reference-machine.md` § What depends on these values records where that lands: the same installed
  heating at 120 V is over 16 A, so concurrent brew and steam is unavailable there regardless.
  Either way every current and dissipation figure below is recomputed from the adopter's own supply
  and element resistances; none of them is inherited.

`REQ-MACHINE-CONFIGURATION-001.C8` rules a nameplate-derived frequency inadmissible as the declared
value, and this machine's 50 Hz is inferred from a pump nameplate. It stands as provisional until
measured, and nothing below depends on its exact value.

## What each switched load needs of its device

Six mains loads, each specified by property. Currents are computed from the measured cold
resistances in `reference-machine.md` § Heating and load across the declared 230–253 V span (230 V
nominal, 240 V, and 253 V at the +10 % top of the permitted range); a cold resistance gives the
higher current if these elements behave as metal heating elements ordinarily do, resistance rising
with temperature. **That coefficient is assumed, not declared** — no document here gives one for
either element. It is called out because the whole direction of the sizing case turns on it: were
either element to fall in resistance when hot, the worst case would be the hot reading rather than
the cold one, and every figure in this table would be a floor rather than a ceiling.

| Load | Commanded how often | Carries continuously | Must dissipate | Must fail into | OEM device — the floor to clear |
|---|---|---|---|---|---|
| Coffee thermoblock element | Once per supply half-cycle. This is the requirement that retires the OEM device: `DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM` converts a commanded level into an energise-or-idle decision taken every half-cycle, and a mechanical relay cannot be commanded at that rate or survive being asked to | 4.36 A at 230 V, 4.55 A at 240 V, 4.80 A at 253 V, from the measured 52.7 Ω | At full duty, the device's own forward drop times that current — of the order of 6 W at the top of the supply span, taking a triac's on-state drop at 1.2–1.4 V. **That drop is a device-class figure taken from ordinary practice, not from any declaration here**, and it is the only unsourced quantity in this table; a candidate device's own datasheet replaces it, and the heatsink follows from that number rather than from this one. Mounted so that heat leaves it at the ambient inside a machine that is itself heating, not at bench ambient | **De-energised.** `OBL-ELECTRICAL-THERMAL-SAFETY-001.C2` requires a hung controller to de-energise rather than hold a heater on, and a device whose dominant failure is a short does not provide this by itself — see the regression note below | Mechanical relay, Hongfa `HF3FD/012HST`, 12 V DC coil, signal `CFHET`. On/off only. Its *dominant* failure is an open contact, though a relay switching this current can also weld shut — no document here declares a failure distribution for this part. Recorded as the floor a replacement must clear, not as a specification inherited |
| Steam thermoblock element | Once per supply half-cycle, as above | 4.89 A at 230 V, 5.11 A at 240 V, 5.38 A at 253 V, from the measured 47.0 Ω. That reading is a *lower bound* on the element's resistance — the bench could not isolate it and a parallel path can only pull a reading down — so these currents are a conservative ceiling rather than a central estimate, which is the right direction for sizing a device | Of the order of 7 W at full duty at the top of the span, on the same basis | **De-energised**, on the same criterion and with the same caveat | Mechanical relay, Hongfa `HF3FD/012HST`, 12 V DC coil, signal `SMHET`. Identical to the coffee side |
| Coffee pump | At a firing instant within the cycle. `DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM` retains the phase-capable arrangement rather than replacing it, so this channel's device is already adequate and the requirement is to keep it, not to buy it | Not derivable from the declared figures. 48 W (Ulka EP5) is a real-power rating and the load is a solenoid pump, so its VA exceeds its watts by a power factor no document here gives. 0.21 A at 230 V is the real-power floor, not the current the device must carry | Not derivable for the same reason. The OEM device carries it today, which bounds the question without answering it | **De-energised.** A pump left running is not the thermal hazard a heater is, but it is a water hazard and the same criterion reaches it | `MOC3021` opto-triac driver into a triac, signal `CFPUM`. Phase-capable; this is the floor and it is already met |
| Steam pump | As the coffee pump | Same basis, 22 W (JYPC-4) giving a 0.096 A real-power floor at 230 V | Same basis | **De-energised** | `MOC3021` opto-triac driver into a triac, signal `SMPUM` |
| Two-way solenoid valve (`2T0607W`) | Once per delivery. Nothing requires this channel to modulate; it opens and closes | **Not established.** `reference-machine.md` records the coil as mains AC and states plainly that its VA is not given by any document. A device cannot be finally sized against this row until that is measured | Not established, for the same reason | **De-energised.** This matters more than the current does: `reference-machine.md` § Protection records the hypothesis that the brew valve vents to the drip tray when de-energised, which would make the de-energised state the venting state | Mechanical relay, Hongfa `HF32FA/012HSL`, 12 V DC coil, signal `CFVAL`. Adequate for a per-delivery channel |
| Three-way diverter valve (`3T0618W`) | Once per delivery | **Not established**, as above | Not established | **De-energised** | Mechanical relay, Hongfa `HF32FA/012HSL`, 12 V DC coil, signal `HTVAL` |

### Isolation, which every row above shares

`OBL-ELECTRICAL-THERMAL-SAFETY-001.C6` applies to all six loads and is stated once here rather than
repeated per row, because the requirement does not vary between them: the barrier between the
mains-referenced switching device and everything the controller, its sensing and the operator can
reach must hold under fault as well as in service, and under the water, steam and repeated thermal
cycling the machine actually runs in rather than under bench conditions.

For every one of the six, that means the device is commanded across an isolating barrier and never
by a direct electrical connection to a controller pin. On the four channels switched by an
opto-triac the optocoupler *is* that barrier and the requirement is a property of the part chosen,
so the driver is named alongside the triac rather than treated as an accessory to it. On the two relay-switched valve channels the relay's own coil-to-
contact separation provides it. The two heater channels are the consequential ones: they carry the
largest current in the machine, they are the channels moving from a relay to a semiconductor, and
their gate drive is where a lost barrier would put mains onto the controller's own ground.

Creepage and clearance on the board carrying these devices are a layout question this document does
not settle, and no declared figure of this design bounds them. The jurisdiction whose wiring rules
apply is AS/NZS 3000 (`reference-machine.md` § Supply), which is a local assumption an adopter
replaces along with the voltage and the frequency.

### The regression this specification makes visible

Meeting the half-cycle requirement on the two heater channels means replacing a mechanical relay with
a semiconductor device, and that is a regression in failure mode, not only a change of part. A relay's
dominant failure is an open contact — not its only one, since contacts switching this current do weld
— whereas a shorted junction is a triac's ordinary way of dying rather than its unlucky one. On a heater channel the
difference is the whole of `OBL-ELECTRICAL-THERMAL-SAFETY-001.C2`: a shorted triac holds the element
energised with no command and no way for the controller to intervene, which is precisely the state
that criterion exists to forbid.

This is recorded here rather than solved here. The answer is not a better triac — it is a series
element that removes power independently of the switching device, which is what
`REQ-SAFETY-CHAIN-001.C2` and `.C3` already require of the proof-of-life interlock. That interlock is
out of scope for this slice by the solution's own wording and still has no covering work in the
graph. What this document adds is that it is no longer only an unbuilt requirement: choosing the
device the actuation scheme demands actively worsens the failure mode it protects against, so the two
are coupled in a way they were not when the heaters were switched by relays.

Both elements sit downstream of a per-block series thermostat and a one-shot thermal device, neither
of which the controller can reach (`DEC-HEATER-DRIVE-GATED-BY-SUPERVISION`). Those bound the hazard;
they do not satisfy the criterion, which is about the controller's own failure rather than the
temperature's.

## What the supply-timing front end needs

| Property | Requirement | OEM circuit — the floor to clear |
|---|---|---|
| What it presents | Both crossings of every cycle. `DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM` resolves half-cycles, and a scheme resolving half-cycles cannot be timed against a reference reporting every second one | A `PC817` optocoupler fed from the line through a `1N4007` and a 120 kΩ 1 W resistor. **Half-wave** — one conduction window per cycle. This is the floor and the OEM circuit does not meet it |
| Isolation | A barrier separating the mains-referenced side from every low-voltage circuit and operator-reachable control, holding under fault and under the water, steam and thermal cycling the machine actually runs in, per `OBL-ELECTRICAL-THERMAL-SAFETY-001.C6` | The `PC817`'s optical barrier. Adequate in kind; a replacement provides its own on the same footing |
| What it is read as | An input, not a clock. The supply's period is measured from it, and an edge arriving outside a plausible window — or not arriving — is a supply fault to report rather than smooth over | The OEM routed it to an interrupt pin of `U3`. Adequate in kind |
| Phase accuracy | **Not established and not bounded.** The offset between a true crossing and a detected edge is real in any diode-and-resistor front end, and no declared figure of this design bounds it. `DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM` explicitly declines to invent one | Unknown for the OEM circuit too |

A full-wave presentation is the only property here the OEM circuit fails. It is met by rectifying
both half-cycles ahead of the optocoupler, or by a back-to-back arrangement, or by an integrated
zero-cross detector part. Which is a part-selection question and is settled in the list below rather
than here.

## Does a candidate controller serve every channel at once

The assessment below is made in interface resources, not in connector count, because
`REQ-HARDWARE-HEADROOM-001.C2` and `DEL-COMPONENT-SPECIFICATION.C4` both rule that a count of spare
pins argues nothing: what matters is whether the capture channels, conversion inputs and interrupt
lines the enumeration collectively demands are *simultaneously* available.

### What the enumeration demands

Totalled across both tables of `controller-io.md`. One total is given. A second column here previously costed the alternative of
reaching that panel over the machine's existing two-wire link, which `DEC-U8-BOARD-RETENTION-UNVERIFIED`
left open. That option no longer arises: inspection of the panel board places no controller on the panel, and the owner's account places both microcontrollers on the main board and finds the panel passive, so the two wires connect two chips this project replaces rather than
two boards, and the panel board is retained, but carries no controller to speak to. The column is struck rather than costed.

| Resource | Count | (struck) | Notes |
|---|---|---|---|
| Analogue conversion inputs | 4 | — | Coffee, steam and wand temperature, plus the steam-path pressure transducer that `DEC-STEAM-PRESSURE-SENSOR-ADDED` adds and which is not yet fitted |
| Timer input capture | 1 | — | Flow meter. Its signal is established digital: a pulse train pulled up to the 5 V rail and landing on a general-purpose port pin. Whether the output is open-drain or push-pull, and the K-factor, both stay open |
| Timer compare outputs | 5 | — | Both pumps, provisioned for a firing instant within the cycle; the panel's anode rail gate, whose modulation is how indicator brightness varies; and the two gauge step clocks, which need an even rate to sweep smoothly rather than stutter |
| External-interrupt pins | 1 | — | Mains zero-cross, on both edges |
| Plain digital inputs | 5 | — | Tank level, the two control-knob microswitches, and the two mains-presence sense channels on the heating elements. The panel's keys are not here: they share lines with the indicators and are counted in the row below |
| Plain digital outputs | 14 | — | Two heater channels, two valve channels, the buzzer, the water indicator on the gauge assembly, the panel's five shared lines, and the two gauge direction lines plus the driver reset. The panel's five are bidirectional — each sinks its indicator group's current and is read as an input once the anode rail is blanked — so eight indicator elements and five keys together cost five pins. See [`connector-pinouts.md`](connector-pinouts.md) |
| Stepper driver channels | 2 timer + 3 digital | — | The two gauges, through a `VID66-08` on the gauge assembly rather than into the windings. If that board is retained the driver is inherited: the controller supplies a direction level and a step clock per gauge plus a shared reset. The step clocks need timer channels — an uneven rate reads as needle stutter. Retaining an out-of-production driver is an obtainability risk, distinct from the unknown-condition question `OBL-PHYSICAL-CONFIGURATION-001.C3` asks, not a saving |
| Serial peripherals | 0 | — | The two-wire operator link this row costed is not an inter-board link and cannot be retained; a display link is a separate question this table does not settle |
| **Pin total** | **30** | — | Summing the pin costs above: 4 + 1 + 5 + 1 + 5 + 14. The gauge lines are counted in the timer and digital-output rows rather than in a row of their own. The controller I/O bill of materials reaches a higher figure for the same machine because it also carries the brew-path pressure channel no decision has yet added and a display link |

### What the candidate provides

The candidate assessed is the **STM32F407VGT6** in LQFP100 — the exact part
`DEC-PREHARDWARE-TARGET-FAMILY` nominates for the pre-hardware target build, so the board the list
buys and the board definition the target build compiles against are the same one. Figures are the
manufacturer's (ST datasheet `DS8626`). The pin-compatible VET6 differs only in carrying 512 KB of
flash instead of 1 MB; it is not assessed here, because choosing it would narrow the compute envelope
`DEC-HEATER-DRIVE-GATED-BY-SUPERVISION` asks to be sized generously and would do so on no evidence,
the compute demand being unquantified in both directions.

| Resource | Provided | Demanded | Remaining |
|---|---|---|---|
| General-purpose I/O | 82 raw; about 78 usable | 30 | About 48. The raw count includes the SWD pins and PH0/PH1, which carry the HSE crystal — and `DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM` requires a crystal-derived control period, so those two are spoken for by this design rather than optional |
| 12-bit ADC units / external channels | 3 units. ADC1 and ADC2 bring out 16 external channels each in this package; ADC3 brings out fewer, several of its inputs sitting on a port LQFP100 does not carry | 4 channels, on one unit | Ample, and the three units can convert concurrently if a later channel needs it |
| 16-bit timers | 12 in total: 2 advanced motor-control, 8 general-purpose, and 2 basic with no I/O channels at all | 6 channels (5 compare, 1 capture) | Ample — but the usable pool for these channels is the 10 with I/O, not 12 |
| 32-bit general-purpose timers | 2 | 0 | Both free |
| External interrupt lines | 16 | 1 | 15, with the constraint below |
| Flash / RAM | 1 MB / 192 KB | Not stated by the enumeration | Unquantified — see below |
| Core | Cortex-M4 at 168 MHz | Not stated by the enumeration | Unquantified — see below |
| Output logic level, gauge-driver lines | 3.3 V I/O. `VOH` is guaranteed to `VDD` − 0.4 V — about 2.9 V — at rated sink current, rising close to the rail at light load, but the guarantee is the figure a board is chosen against | 5 lines clearing the retained `VID66-08`'s 3.15 V `VIH` | **Not cleared on guaranteed figures** — see below. Resolved either by five level shifters or by a bench measurement of `VOH` into a ~10 µA load |

**Simultaneity holds, and the resource that would bite first is named.** No two channels contend for
the same unit at these counts: the four conversion inputs fit one ADC with twelve channels to spare,
the six timer channels fit inside two general-purpose timers let alone ten, and the
thirty pins fit inside seventy-eight. Fitting them on one timer is not the same as placing them
there: a flow-pulse input capture, two mains-phased compare outputs, two gauge step clocks and an indicator rail gate would share a
prescaler and a time base.
With ten I/O-capable timers available there is no reason to accept it. The one resource with a structural constraint rather than a
numeric one is the external-interrupt block: this part has sixteen lines, but line *n* serves pin *n*
of exactly one port at a time, so sixteen interrupt-driven channels cannot be placed arbitrarily. One
channel is demanded, so the constraint does not bind — but it is the resource that would bind first
if a later channel wanted its own interrupt, and it is invisible to a pin count.

**One row is not cleared, and it is a channel rather than a count.** Every numeric row has room to
spare. The row that does not clear is the last: this part's outputs are 3.3 V, and the gauge driver
retained by `DEC-DEVICE-RETENTION-BOUNDARY` guarantees nothing below a 3.15 V input high. On
guaranteed figures — `VOH ≥ VDD − 0.4 V`, about 2.9 V — the five gauge lines are not driven reliably.

This does not defeat the candidate, and it is recorded here rather than in a discarded note because
it is not that kind of finding. In practice a 3.3 V CMOS output into the ~10 µA these inputs leak sits
within millivolts of the rail and would clear 3.15 V comfortably; what is missing is a guarantee, not
a mechanism. Two things close it: five level shifters on the gauge lines, cheap but a part on the
board — or a bench measurement of this part's `VOH` into that load, which converts a typical into an
established figure for this design. Either is admissible. Choosing neither, and specifying the board
as though the row were clear, is what this table exists to prevent.

It is also a cost that belongs to **retention** rather than to the gauges: a controller driving the
movements directly sets its own thresholds and the row disappears. That trade sits with
`DEC-DEVICE-RETENTION-BOUNDARY`, not here.

### Room for the channels the graph anticipates

| Anticipated channel | Where it comes from | Costs |
|---|---|---|
| Brew-path pressure transducer | `REQ-MEASUREMENT-001.C7` requires brew pressure measured rather than inferred; no decision has yet added a part | 1 conversion input |
| Current sensing | Recorded in `controller-io.md` § Channels not enumerated as not fitted and not decided | 1–2 conversion inputs |
| Weight-based endpoint control | Named in `REQ-HARDWARE-HEADROOM-001` as the immediate deferred capability | 2 digital pins to a load-cell amplifier |
| Direct group-head instrumentation | Named in the same requirement as the general case | 1–2 conversion inputs |
| Real-time clock | Not fitted, not decided | 0 pins running off the internal low-speed oscillator, 2 with the 32.768 kHz crystal that anything wanting to timestamp would need — the internal oscillator drifts too far to be useful for that |

Roughly five further conversion inputs and two digital pins. Against twelve unused channels on one
ADC unit and forty-eight unused pins, every anticipated channel fits without displacing a current one,
which is what `REQ-HARDWARE-HEADROOM-001.C1` and `DEL-COMPONENT-SPECIFICATION.C4` ask to be shown.

### What this assessment does not establish

- **Compute and memory are unquantified on both sides.** The enumeration states no RAM, flash or
  clock requirement, and measuring the control law's actual execution time is on-target work under a
  later phase. 1 MB and 192 KB are recorded as what the part provides, not as what the design needs.
  No headroom claim is made about them in either direction; taking the larger-flash variant is a
  refusal to narrow an unmeasured envelope, not a claim that the smaller one is insufficient.
- **A specific board's usable subset is narrower than the part's.** These figures are the
  microcontroller's. A purpose-built development board spends pins on its own function — onboard
  memory, camera and display headers, an Ethernet footprint — and its spare capacity is spare for
  that function first. Whichever board is bought, the pins it actually brings out to a connector must
  be checked against this table from its own schematic before the purchase closes. That check is
  named in the list below rather than assumed here.
- **This is not a selection.** `DEC-PREHARDWARE-TARGET-FAMILY` and
  `DEC-HEATER-DRIVE-GATED-BY-SUPERVISION` both state in terms that controller selection is answered
  later against measured plant parameters, and `REQ-HARDWARE-HEADROOM-001` frames the choice as one
  still to be made. An assessment showing a candidate adequate is an input to that decision, and
  buying a board under the worst-case envelope the second of those decisions describes does not make
  it.

## The component list

This is a specification, not a shopping list. Each row states what a part on that channel has to
satisfy and what the OEM device already achieves, so a candidate — bought new, taken off this
machine, or recovered from a donor machine — can be held against the row and judged. **Which part
serves a channel, and where it comes from, is the builder's decision and is recorded once made.**
Nothing below chooses on their behalf, and no row is closed by this document.

**Declared spend: 250 USD**, covering what the retrofit adds and excluding the machine it is added
to. This is the figure `REQ-COST-DISCIPLINE-001.C5` and `DEL-COMPONENT-SPECIFICATION.C5` require to
be written down rather than held in anyone's head, and it is the figure an adopter replaces with
their own — currency, market and what they paid for their machine are all theirs.
`REQ-COST-DISCIPLINE-001.C6` asks that the running total be *weighed* against it as decisions land,
not that it be treated as a trip point.

### Provenance classes

Three, and they differ on more than price. The class is recorded per channel when the part is
chosen; it is not predicted here.

- **Reused** — already carried by this machine, whether it stays where it is or is recovered off a
  board being replaced. Costs nothing, and has demonstrated it survives this machine's environment,
  which is more than a datasheet establishes (`REQ-COST-DISCIPLINE-001.C1`). A part coming off the
  OEM control board is reuse on this definition: it loses its board, not its history.
- **Salvaged** — taken from a different machine. Costs nothing and has demonstrated *neither* a
  datasheet nor survival here, so a salvaged row records how the part was verified against its
  specification before it is admitted. What that verification has to reach is set by what the
  channel's failure costs, not by what the part costs (`REQ-COST-DISCIPLINE-001.C4`).
- **Bought** — new, carrying its datasheet and its price.

### What each channel requires

| Channel | Must satisfy | Capability floor already achieved | Part chosen | Provenance | Cost |
|---|---|---|---|---|---|
| Controller | Every row of the resource assessment above, simultaneously, with room for the anticipated channels. Checked against the specific board's own schematic, since a board's usable pins are fewer than its microcontroller's | None — the machine carries no part serving this | *undecided* | *undecided* | |
| Coffee element switching | Commandable once per supply half-cycle; carries 4.80 A at the top of the declared span; dissipates of the order of 6 W at full duty, at the machine's internal ambient; commanded across an isolating barrier; does **not** reach the de-energised state on failure by itself, so the channel depends on the series interlock discussed above | Hongfa `HF3FD/012HST` relay: isolated, fails open, but cannot be commanded per half-cycle. Clears every property except the one that matters most here | *undecided* | *undecided* | |
| Steam element switching | As above, at 5.38 A and of the order of 7 W | Hongfa `HF3FD/012HST` relay, same reading | *undecided* | *undecided* | |
| Heater gate drive, both channels | Firing at the zero crossing in hardware rather than at an instant the controller estimates, which removes this channel's exposure to the unbounded edge-versus-crossing offset; isolation between the controller pin and the mains-referenced gate | None on this channel — the OEM relay needed no gate drive | *undecided* | *undecided* | |
| Coffee pump switching | A firing instant placed within the cycle; isolated gate drive; de-energised on failure. Current not derivable — 48 W is real power on an inductive load and no source gives the power factor | `MOC3021` opto-triac into a triac. Phase-capable: this channel's floor is already at the requirement | *undecided* | *undecided* | |
| Steam pump switching | As above; 22 W on the same basis | `MOC3021` opto-triac into a triac | *undecided* | *undecided* | |
| Two-way valve switching | Per-delivery switching of a mains AC coil whose VA no document establishes; isolated; de-energised on failure, which on this channel may also be the venting state | Hongfa `HF32FA/012HSL` relay. Adequate for a per-delivery channel | *undecided* | *undecided* | |
| Three-way valve switching | As above | Hongfa `HF32FA/012HSL` relay | *undecided* | *undecided* | |
| Supply-timing front end | Both crossings of every cycle; a barrier holding under fault and under water, steam and thermal cycling; read as an input rather than followed as a clock | `PC817` optocoupler on a half-wave feed. Isolation adequate; **fails the both-crossings property**, which is the one this design added | *undecided* | *undecided* | |
| Coffee, steam and wand temperature sensing | Analogue resistance, NTC, at the accuracy `controller-io.md` states per channel | `EM70025`, `EM70020` and the wand disc sensor, fitted and working | *undecided* | *undecided* | |
| Flow sensing | A pulse train on a general-purpose port pin, pulled up to the 5 V rail; open-drain versus push-pull, and the K-factor, stay open | The fitted OEM meter | *undecided* | *undecided* | |
| Steam-path pressure sensing | Analogue conversion; range and accuracy not yet specified, the part not yet selected | None — added by decision, never fitted | *undecided* | *undecided* | |
| Gauge drive, both gauges | Two direction levels, two step clocks needing timer channels, and a shared reset — **all five clearing a 3.15 V input threshold**, which is the retained driver's guaranteed `VIH` and does not relax with its supply. A 5 V drive clears it outright; a 3.3 V part qualifies only if its own `VOH` guarantee reaches 3.15 V at the current these inputs draw, and otherwise the channel carries five level shifters. Figures and their provenance in [`connector-pinouts.md`](connector-pinouts.md). The controller does not provide stepper drive: the `VID66-08` sits on the gauge assembly, which is retained, so the driver is inherited. That is not a saving — the part is out of production, which makes an unobtainable device a single point of failure on a channel with no fallback, and is an obtainability risk, distinct from the unknown-condition question `OBL-PHYSICAL-CONFIGURATION-001.C3` asks. Specifying a controller that could drive the movements directly keeps both options | OEM `VID66-08` on the gauge assembly, two-channel, serving both gauges today and inherited rather than bought | *undecided* | *undecided* |  |
| Heater mains-presence confirm, both elements | Two isolated AC-sense inputs reporting whether mains actually reached each element, which distinguishes a relay that did not close, a welded contact and an open thermal cutout from a command that was obeyed. Reinforced isolation, mains-crossing | OEM `LTV814` AC-input optocoupler through a 120 kΩ 1 W resistor, fitted and working | *undecided* | *undecided* | |
| Low-water indication, visual | One output sinking an indicator cathode on the gauge assembly, whose anode rail is the button panel's gated rail extended over the gauge harness | The fitted indicator, retained with the gauge assembly | *undecided* | *undecided* | |
| Operator panel — keys, indicators, buzzer | Five bidirectional lines carrying both the key pairs and the indicator cathodes, one timer output gating the anode rail, and one buzzer output — seven pins for the whole panel. The keys are ten switches in five parallel pairs; the indicators are eight elements in five groups. Pinout in [`connector-pinouts.md`](connector-pinouts.md) | The OEM panel board, retained as a passive assembly | *undecided* | *undecided* | |
| Low-voltage supply | Whatever the chosen controller and gate drives need, isolated from the mains side | The OEM board's own supply, on a board being replaced | *undecided* | *undecided* | |
| Wiring, connectors, mains-rated terminals | Rated for the currents above; mains-referenced runs separated from low-voltage per `OBL-ELECTRICAL-THERMAL-SAFETY-001.C6`; AS/NZS 3000 in this jurisdiction | Existing loom, condition unassessed | *undecided* | *undecided* | |

### Against the declared figure

| | |
|---|---|
| Channels specified | 18 |
| Channels whose part is decided | 0 |
| Bought to date | 0 |
| Reused to date | 0 |
| Salvaged to date | 0 |
| **Declared spend** | **250** |
| **Remaining** | **250** |

Nothing has been decided, so nothing has been spent and no departure from the reused-or-commodity
default is yet owed a justification under `REQ-COST-DISCIPLINE-001.C2`. The total is kept running as
rows close because `REQ-COST-DISCIPLINE-001.C6` judges a channel decided late against what is left,
not against the headroom the first channel enjoyed.

Two rows are worth reading against `REQ-COST-DISCIPLINE-001.C4` before they are decided. The heater
channels' parts are cheap and their failure is a hazard, which is exactly the combination that
criterion says to weigh — and the answer is not a dearer triac, since failing shorted is a property
of the device class rather than of its price. It is the series interlock. That, the relief question
on the steam side, and whatever the panel decision settles all sit outside this list and will draw on
the declared figure.
