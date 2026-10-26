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

**The controller is the one part this document selects.** `DEC-CONTROLLER-BASELINE-STM32H743`
baselines the family, and § The part selected below names the orderable part within it, its package and
its memory variant, shows that it serves every channel at once, and states what the choice means for the
firmware. Every other row of the list below stays a property to meet, not a part chosen.

## What the supply is, and what changes off it

Everything below is stated against a declared supply rather than against this machine's. The
reference build runs on a declared span of 216–253 V at 50 Hz, from a 10 A outlet behind an upstream
breaker declared as up to 20 A (`reference-machine.md` § Supply, which grades each). Two things follow for an adopter elsewhere, and both are properties of their supply rather
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

This machine's 50 Hz is the supply's nominal, taken from the standard governing that supply rather
than from a component's marking, as `REQ-MACHINE-CONFIGURATION-001.C9` requires. Nothing below depends
on its exact value: whatever depends on the supply's timing reads it live while the machine runs.

## What each switched load needs of its device

Six mains loads, each specified by property. Currents are computed from the measured cold
resistances in `reference-machine.md` § Heating and load at three points of the declared 216–253 V
span: 230 V nominal, 240 V, and 253 V, the span's top, which sets every current and dissipation a
device is sized for (its 216 V bottom sets the least heat delivered and no device rating); a cold resistance gives the
higher current if these elements behave as metal heating elements ordinarily do, resistance rising
with temperature. **That coefficient is assumed, not declared** — no document here gives one for
either element. It is called out because the whole direction of the sizing case turns on it: were
either element to fall in resistance when hot, the worst case would be the hot reading rather than
the cold one, and every figure in this table would be a floor rather than a ceiling.

| Load | Commanded how often | Carries continuously | Must dissipate | Must fail into | OEM device — the floor to clear |
|---|---|---|---|---|---|
| Coffee thermoblock element | Once per supply half-cycle. This is the requirement that retires the OEM device: `DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM` converts a commanded level into an energise-or-idle decision taken every half-cycle, and a mechanical relay cannot be commanded at that rate or survive being asked to | 4.36 A at 230 V, 4.55 A at 240 V, 4.80 A at 253 V, from the measured 52.7 Ω | At full duty, the device's own forward drop times that current — of the order of 6 W at the top of the supply span, taking a triac's on-state drop at 1.2–1.4 V. **That drop is a device-class figure taken from ordinary practice, not from any declaration here**, and it is the only unsourced quantity in this table; a candidate device's own datasheet replaces it, and the heatsink follows from that number rather than from this one. Mounted so that heat leaves it at the ambient inside a machine that is itself heating, not at bench ambient | **De-energised.** `OBL-ELECTRICAL-THERMAL-SAFETY-001.C2` requires a hung controller to de-energise rather than hold a heater on, and a device whose dominant failure is a short does not provide this by itself — see the regression note below | Mechanical relay, Hongfa `HF3FD/012HST`, 12 V DC coil, signal `CFHET`. On/off only. Its *dominant* failure is an open contact, though a relay switching this current can also weld shut — no document here declares a failure distribution for this part. Recorded as the floor a replacement must clear, not as a specification inherited |
| Steam thermoblock element | Once per supply half-cycle, as above | 4.89 A at 230 V, 5.11 A at 240 V, 5.38 A at 253 V, from the measured 47.0 Ω. That reading is a *lower bound* on the element's resistance — the bench could not isolate it and a parallel path can only pull a reading down — so these currents are a conservative ceiling rather than a central estimate, which is the right direction for sizing a device | Of the order of 7 W at full duty at the top of the span, on the same basis | **De-energised**, on the same criterion and with the same caveat | Mechanical relay, Hongfa `HF3FD/012HST`, 12 V DC coil, signal `SMHET`. Identical to the coffee side |
| Coffee pump | At a firing instant within the cycle. `DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM` retains the phase-capable arrangement rather than replacing it, so this channel's device is already adequate and the requirement is to keep it, not to buy it | 0.46 A rms at 253 V, the sizing value under an assumed 0.5 power-factor floor (the estimate taking the nameplate power at 253 V is 0.38 A). 48 W (Ulka EP5, nameplate) is a real-power rating on an inductive load behind a series diode (both pumps, inferred from the meter readings: open in one polarity, megohms in the other), so the current is worked from the power and a stated power-factor floor, a project assumption to replace; derivation and sources in [`connector-pinouts.md`](connector-pinouts.md) § Pumps: running current. 0.21 A at 230 V remains the real-power floor, not the current the device must carry | Not stated here: it follows from the device chosen and the current above. The OEM device carries it today | **De-energised.** A pump left running is not the thermal hazard a heater is, but it is a water hazard and the same criterion reaches it | `MOC3021` opto-triac driver into a triac, signal `CFPUM`. Phase-capable; this is the floor and it is already met |
| Steam pump | As the coffee pump | 0.19 A rms at 253 V, the sizing value on the same basis (nameplate 22 W, JYPC-4; the estimate taking the nameplate power at 253 V is 0.174 A); 0.096 A at 230 V is the real-power floor | Same basis | **De-energised** | `MOC3021` opto-triac driver into a triac, signal `SMPUM` |
| Two-way solenoid valve (`2T0607W`) | Once per delivery. Nothing requires this channel to modulate; it opens and closes | At most 64.6 mA rms steady at 253 V, from the coil's marking (230 V AC, 9–13.5 VA, inspected), and at most 101.4 mA rms (143.3 mA peak) in inrush, from 253 V over its cold resistance of 2.496 kΩ (measured); sources and derivation in [`connector-pinouts.md`](connector-pinouts.md) § What each retained device imposes on whatever drives or reads it | Follows from the device chosen and the currents above | **De-energised.** This matters more than the current does: `reference-machine.md` § Protection records the hypothesis that the brew valve vents to the drip tray when de-energised, which would make the de-energised state the venting state | Mechanical relay, Hongfa `HF32FA/012HSL`, 12 V DC coil, signal `CFVAL`. Adequate for a per-delivery channel |
| Three-way diverter valve (`3T0618W`) | Once per delivery | At most 64.6 mA rms steady and 101.4 mA rms (143.3 mA peak) inrush at 253 V, from the marking and the cold resistance of 2.497 kΩ, as above | Follows from the device chosen | **De-energised** | Mechanical relay, Hongfa `HF32FA/012HSL`, 12 V DC coil, signal `HTVAL` |

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

Both elements sit downstream of a per-block series thermostat, which the controller cannot reach
(`DEC-HEATER-DRIVE-GATED-BY-SUPERVISION`). Whether a one-shot thermal device is also fitted is not
established, and nothing here relies on one. The thermostat bounds the hazard; it does not satisfy
the criterion, which is about the controller's own failure rather than the temperature's.

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
| Analogue conversion inputs | 4 | — | Coffee, steam and wand temperature, plus the board's separate spare analogue input (5V, 3V3, GND and a filtered input), which is the analogue fallback for the steam-path pressure transducer that `DEC-STEAM-PRESSURE-SENSOR-ADDED` adds and which is not yet fitted. The transducer's baseline interface is I²C (`controller-board-function-forms.md` § Steam-path pressure sensing), counted in the serial peripherals row |
| Timer input capture | 1 | — | Flow meter. Its signal is established digital: a pulse train, which the factory board pulls up to 5 V, landing on a general-purpose port pin. The new board pulls the line up to 3.3 V (`controller-board-function-forms.md`, *Flow sensing*). Whether the meter's output is open-drain or push-pull is pending (not yet read; it is read when the board carrying the device is designed, and does not block the division of the circuitry into boards), and the K-factor stays open |
| Timer compare outputs | 5 | — | Both pumps, provisioned for a firing instant within the cycle; the panel's anode rail gate, whose modulation is how indicator brightness varies; and the two gauge step clocks, which need an even rate to sweep smoothly rather than stutter |
| External-interrupt pins | 1 | — | Mains zero-cross, on both edges |
| Plain digital inputs | 5 | — | Tank level, the two control-knob microswitches, and the two mains-presence sense channels on the heating elements. The panel's keys are not here: they share lines with the indicators and are counted in the row below |
| Plain digital outputs | 14 | — | Two heater channels, two valve channels, the buzzer, the water indicator on the gauge assembly, the panel's five shared lines, and the two gauge direction lines plus the driver reset. The panel's five are bidirectional — each sinks its indicator group's current and is read as an input once the anode rail is blanked — so eight indicator elements and five keys together cost five pins. See [`connector-pinouts.md`](connector-pinouts.md) |
| Stepper driver channels | 2 timer + 3 digital | — | The two gauges, through a `VID66-08` on the gauge assembly rather than into the windings. If that board is retained the driver is inherited: the controller supplies a direction level and a step clock per gauge plus a shared reset. The step clocks need timer channels — an uneven rate reads as needle stutter. Retaining an out-of-production driver is an obtainability risk, distinct from the unknown-condition question `OBL-PHYSICAL-CONFIGURATION-001.C3` asks, not a saving |
| Serial peripherals | 1 I²C bus | — | The steam-path pressure transducer's I²C bus, two pins, the baseline interface the operator settled on 2026-10-23; the same two signal lines can carry a UART, so the pins are chosen on a pair that carries both functions. The two-wire operator link this row costed is not an inter-board link and cannot be retained; a display link is a separate question this table does not settle |
| **Pin total** | **32** | — | Summing the pin costs above: 4 + 2 + 1 + 5 + 1 + 5 + 14. The gauge lines are counted in the timer and digital-output rows rather than in a row of their own. The controller I/O bill of materials reaches a higher figure for the same machine because it also carries the brew-path pressure channel no decision has yet added and a display link |

### The part selected

The controller is the **STM32H743VIT6** from STMicroelectronics: an Arm Cortex-M7 microcontroller in the 100-lead LQFP package (14 × 14 mm, 0.50 mm lead pitch), with 2 Mbyte of flash, for −40 to 85 °C ambient, supplied in trays or tubes. It is designed bare onto the controller board and assembled by the board manufacturer, not bought as a module (`controller-board-function-forms.md` § Controller). The family is the STM32H743, which `DEC-CONTROLLER-BASELINE-STM32H743` baselines; this section selects the part, its package and its memory variant within that family, and the sections below show that it serves every channel. The STM32F4 family that the firmware's target build still names was only ever a stand-in for verification: it is not the controller, and no figure in this document is taken from it.

**Source.** ST datasheet DS12110 Rev 11 (January 2026), *STM32H742xI/G STM32H743xI/G*, at https://www.st.com/resource/en/datasheet/stm32h743vi.pdf. st.com did not answer on 2026-10-23, so every figure below was read the same day from the Internet Archive's copy of ST's PDF. Grade: published unverified, read at source (`controller-board-design-constraints.md` § Evidence grades): the manufacturer's published claim, established on no part in hand. Table and section numbers are DS12110's. The sheet holds two electrical sections, one for silicon revision Y (Tables 11, 14, 51, 52) and one for revision V (Tables 109, 110, 112, the same tables in the same order); the figures used here are the same in both, so they hold for either revision, the JLCPCB listing not fixing which the stocked part is.

**Why the 100-lead package.** The family is offered in LQFP100, TFBGA100, LQFP144, UFBGA169, LQFP176, LQFP208, UFBGA176+25 and TFBGA240+25 (front page, Table 2). The ordering code's pin-count letter *V* is 100 pins, the smallest the family has (§ 9, Ordering information); there is no smaller package to take. The smallest package is the one chosen because it carries the demand with room to spare (below) and the board manufacturer assembles it. Its lead pitch is 0.50 mm (Table 208, LQFP100 mechanical data), against the 0.40 mm smallest IC lead pitch the manufacturer places (`docs/board-manufacturer-jlcpcb.md` § Assembly limits, *Smallest IC lead pitch placed*). The one other 100-pin package, TFBGA100, has the same 82 GPIO (Table 2), so it adds no resource. It is also a ball-grid part: the manufacturer's price for X-ray inspection, which it requires of BGA parts, is 1.64 USD per component inspected at one to ten components (`docs/board-manufacturer-jlcpcb.md` § Assembly charges, *X-ray inspection*, read 2026-10-13), about the 1.86 USD by which the TFBGA100 catalogue part (C964146, 8.8197 USD, read 2026-10-23) undercuts the LQFP100 (10.6814 USD, read 2026-10-24), and its 0.8 mm ball pitch (Table 210's title) asks of the board a ball escape the leaded part does not. So the saving is spent and the board gets harder for no gain.

**Why the 2 Mbyte variant.** The flash is the only difference between the *G* and *I* parts of the same package: 2 × 512 Kbytes against 2 × 1 Mbyte, with the same RAM, the same 82 GPIO and the same peripherals (Table 2). The compute and memory the control needs are not quantified by the channel enumeration, and measuring the control law on the target is later work, so no figure says that 1 Mbyte is enough. `REQ-HARDWARE-HEADROOM-001` is a constraint on foreclosing: a choice made once, early, on the least information the project will have, and costly to reverse once boards are made. The larger flash is the choice that forecloses less, and it costs nothing to take: the catalogue lists the 2 Mbyte part (C114409) at 10.6814 USD (read 2026-10-24; 10.6742 USD on 2026-10-23, with 3 287 in stock) and the 1 Mbyte part (STM32H743VGT6, C730183) at 12.0267 USD with 1 001 (read 2026-10-23). This is a refusal to narrow an unmeasured envelope, as `DEC-HEATER-DRIVE-GATED-BY-SUPERVISION` asks the board to be sized, and not a claim that the smaller variant would be insufficient. The temperature suffix 6 is rated to 85 °C ambient at maximum power dissipation (Table 14, § 9); the air inside the enclosure is assumed to be 70 °C until bring-up measures it (`controller-board-design-constraints.md` § Enclosure air temperature), which leaves 15 K on that assumption and no more than that.

**Catalogue entry the board record pins.** JLCPCB lists the part as C114409, *STM32H743VIT6*, Extended class, LQFP-100 (14 × 14), SMT assembly. On 2026-10-23 it was in stock at 3 287, and on 2026-10-24 at 10.6814 USD for 1–9 pieces (10.6742 USD the day before), read through the search service the library's own search page uses (`controller-board-design-constraints.md` § Manufacturer stock and price, per channel, *How each candidate was read*). The only other in-stock listing of the same chip is C5271084, *STM32H743VIT6TR*, the tape-and-reel packing (the ordering code's *TR*), 963 in stock at 12.568 USD. The build quantity is two boards, the assembly service's minimum (`controller-board-design-constraints.md` § Manufacturer stock and price, per channel, *Prices, breaks and the build quantity*), so a part is eligible when its stock covers two; both do, with margin. C114409 is pinned because its maker's part number is the tray part the datasheet's ordering code gives (no packing letter), because it has the larger stock and because it is the cheaper. The record is `hardware/sunbeam-em7000/controller-part.yaml`: it holds that part number, the catalogue number and the 80 port-pin names of the LQFP100 package from Table 9, and the pre-order board check fails a design whose controller carries any other catalogue number or whose pin allocation names a port pin the part does not have. When the catalogue stock falls below two at an order, the record is re-pinned to the other listing in a change of its own.

### What the selected part provides

| Resource | Provided | Demanded now | With the anticipated channels | Remaining |
|---|---|---|---|---|
| Core and clock | Arm Cortex-M7 with double-precision FPU and 16 Kbyte instruction and data caches, up to 480 MHz, 1027 DMIPS (front page). The 480 MHz is obtained on devices revision V (Table 2, note 3) | Not stated by the enumeration | Not stated | Unquantified — see below |
| Flash / RAM | 2 × 1 Mbyte flash (Table 2). RAM: 192 Kbytes of TCM (64 instruction and 128 data), 864 Kbytes of user SRAM (512 + 128 + 128 + 32 + 64) and 4 Kbytes in the backup domain (front page, Table 2) | Not stated | Not stated | Unquantified — see below |
| General-purpose I/O | 82 (Table 2): 80 named port pins (Table 9, LQFP100 column) and the two analogue-only pads PC2_C and PC3_C. 78 usable (76 digital pins and the two analogue-only pads) once PA13 and PA14 (serial-wire debug) and PH0 and PH1 (the crystal oscillator, which the crystal-derived control period spends) are taken | 32 | 32 + 13 digital + 5 conversion = 50 | 26 digital pins (20 rated for 5 V, 6 not) and, apart from them, the two analogue-only pads |
| 16-bit ADCs / external inputs | 3 converters, resolution configurable to 16, 14, 12, 10 or 8 bits (§ 3.17, Table 2). Table 9 routes 16 conversion inputs to the LQFP100 pins: 14 reach ADC1, 12 reach ADC2, 4 reach ADC3 (PC0, PC1, PC2_C, PC3_C) | 4 inputs | 9 inputs | 7 inputs on pins |
| Timers | 2 advanced-control (TIM1, TIM8), 10 general-purpose (TIM2–5, TIM12–17), 2 basic, 5 low-power, 1 high-resolution (Table 2, § 3.28). TIM2 and TIM5 are 32-bit, TIM1–5 and TIM8 have four channels, TIM12 and TIM15 two, the rest one | 7 channel uses (2 captures, 5 outputs) | Same | 4 timers used of 12 with I/O channels; the other 8 untouched |
| I²C | 4 interfaces to 1 Mbit/s on the fast-mode-plus pins (§ 3.30). Table 10 puts them on five LQFP100 pin pairs: I2C1 and I2C4 on PB6/PB7 and on PB8/PB9, I2C4 also on PD12/PD13, I2C2 on PB10/PB11 and I2C3 on PA8/PC9; each pin of the five pairs is a fast-mode-plus *_f* pin (Table 9) | 1 bus | 2 buses | 2 further pairs free (PB6/PB7 and PD12/PD13) |
| USART / UART / LPUART | 4 / 4 / 1 (Table 2) | 0 required; the I²C pairs also carry a UART | 0 required; a display link optional | Each of the two I²C pairs carries a UART, and PB6/PB7 carries a third |
| SPI | Up to six (§ 3.33, Table 2), to 150 Mbit/s, 8-byte FIFOs with DMA | 0 | 1 bus, 2 chip selects | SPI1, SPI3, SPI4 and SPI6 also reach LQFP100 pins (Table 10); every chip select is a free pin |
| External interrupt lines | The interrupt controller handles 89 event or interrupt lines, 28 configurable and 61 direct (§ 3.13); the I/O ports have interrupt capability (front page) | 1 (zero-cross, both edges) | 1 | The line count does not bind; the pin carrying the zero-cross reaches it |
| Operating supply | 1.71 to 3.6 V in this package (Table 2, note 5) | 3.3 V | 3.3 V | — |
| Output logic level, gauge-driver lines | 3.3 V I/O. `VOH` is guaranteed to `VDD` − 0.4 V, 2.9 V at 3.3 V, at −8 mA (Table 51); `VOL` 0.4 V at 8 mA. Each pin may sink or source 8 mA, 20 mA with a relaxed level (§ 6.3.15); the sum over the part is 140 mA each way (Table 110) | 5 lines clearing the retained `VID66-08`'s 3.15 V `VIH` | Same | **Closed by the designed buffer** — see below |

**Simultaneity holds, and the resource that would bind first is named.** The enumeration of this document totals 32 pins, and the anticipated channels add 13 digital pins and 5 conversion inputs (below); 50 of the 78 usable pins are placed, and every one lands on a pin that carries the function it needs (§ Where each function lands). No two channels contend for a unit: the nine conversion inputs sit on ADC1 and ADC2, which convert independently and can sample simultaneously (§ 3.17); the seven timer channels sit on four timers, with the zero-cross capture and the two pump gates on one time base because the pumps are fired at a delay from the crossing, and the flow capture, the gauge clocks and the indicator gate each on a timer of their own; the two I²C buses are on two interfaces; and the temperature converters' bus is on its own SPI. The resource with the least to spare is the pin pool's 5 V-tolerant subset, which the next section counts: 13 pins need it and 20 free ones have it. Conversion pins come next: 7 of 16 remain, and the two analogue-only pads serve ADC3 only.

**One row is not cleared by the part itself, and it is closed by the form already decided.** This part's outputs are 3.3 V, and its output-high guarantee, `VDD` − 0.4 V (2.9 V at 3.3 V), is below the 3.15 V that the gauge driver retained by `DEC-DEVICE-RETENTION-BOUNDARY` guarantees to read as high. Every numeric row has room to spare; this one is a channel, and the part does not clear it. `controller-board-function-forms.md` § Gauge drive, both gauges closes it by a buffer with TTL-level inputs and 5 V outputs between the controller and the five lines, so the row is not reopened here. The controller pins feeding that buffer are 3.3 V logic into TTL-level inputs and need no tolerance for 5 V.

### Room for the channels the graph anticipates

| Anticipated channel | Where it comes from | Costs |
|---|---|---|
| Brew-path pressure transducer | `REQ-MEASUREMENT-001.C7` requires brew pressure measured rather than inferred; `DEC-BREW-PRESSURE-SENSOR-IS-RETAINED-FOR-PRESSURE-MAP-AND-DRIFT` keeps a brew pressure sensor as the complement of the flow meter, so the channel stays and the part is not selected here. The same class and interface as the steam-path transducer: an XDB401-class transducer on a second I²C bus, since the part's address is fixed (`controller-design/decisions.md` D12) | 2 digital pins for the second bus; the analogue fallback through a spare analogue input costs 1 conversion input |
| Current sensing | Recorded in `controller-io.md` § Channels not enumerated as not fitted and not decided | 1–2 conversion inputs |
| Weight-based endpoint control | Named in `REQ-HARDWARE-HEADROOM-001` as the immediate deferred capability. Up to two load-cell channels, two HX711-class amplifiers on about four digital pins or one two-channel converter, for a drip-tray platform, so one single-point platform cell or two cells summed serve a cup placed anywhere on the tray. An external Bluetooth scale is the alternative and belongs to the display unit, which owns the network-facing surface (`DEC-NETWORK-SURFACE-IS-A-SEPARATE-DISPLAY-UNIT`). The open-source survey of 2026-10-23 is concepts only: Gaggiuino and GaggiMate (load cells with HX711-class amplifiers, plus Bluetooth scales), Decent openscale and ESPresso Scale (ADS1232, Bluetooth scales) | About 4 digital pins to up to two load-cell amplifiers |
| Direct group-head instrumentation | Named in the same requirement as the general case | 1–2 conversion inputs |
| In-stream temperature, brew outlet and steam outlet | `DEC-IN-STREAM-PROBES-ANTICIPATED`: two PT1000 probes, each read by an RTD-to-digital converter of the MAX31865 class on a shared SPI bus with one chip select each, the front end taking a 2-wire or 3-wire probe per channel so the probe bought decides. The earlier design carried a PT1000 outlet probe and a PT1000 with MAX31865 front-end option (`controller-design/control-system-bom.csv`, *PT1000 spike probe*; `controller-design/controller-io-bom.csv`, rows T-B*) | No conversion input; about 5 digital pins (three shared bus lines and two chip selects) |
| Real-time clock | Not fitted, not decided | 0 pins running off the internal low-speed oscillator, 2 with the 32.768 kHz crystal that anything wanting to timestamp would need — the internal oscillator drifts too far to be useful for that |

At most five further conversion inputs (the brew-path fallback 1, current sensing 1–2, group-head instrumentation 1–2) and thirteen digital pins (2 + 4 + 5 + 2). They are placed on the selected part in § Where each function lands. Against sixteen conversion pins on the package, of which the current channels take four, and 78 usable pins, of which they take 32, every anticipated channel fits without displacing a current one. After all of them 7 conversion pins and 28 pins are still unused (26 digital pins and the two analogue-only pads, which can serve only as conversion inputs), the conversion inputs being counted once, as pins of the same pool, which is what `REQ-HARDWARE-HEADROOM-001.C1` and `DEL-COMPONENT-SPECIFICATION.C4` ask to be shown. That the two I²C buses, the serial bus and the amplifiers' lines land on pins carrying the functions they need is shown there too, with the spare capacity on each interface (`REQ-HARDWARE-HEADROOM-001.C2`).

### Where each function lands

Each function is placed on a pin of the LQFP100 package, with the alternate function (AF) that carries it from Table 10 and the pin's I/O structure from Table 9 (*FT* is a 5 V-tolerant pin, *TT* a 3.3 V-tolerant one, Table 8; the suffixes are the analogue, high-speed low-voltage, fast-mode-plus and USB options). Where the function is a level or an input and needs no alternate function, the pin is a plain general-purpose pin. Every pin below is free after the current channels: none is assigned twice. The allocation is the part's, and which board connector each function reaches is the board design task's.

| Function | Pin (LQFP100 number) | Alternate or analogue function | I/O structure |
|---|---|---|---|
| **Current channels** | | | |
| Coffee thermoblock NTC | PC0 (15) | ADC123_INP10 | FT_a |
| Steam thermoblock NTC | PC1 (16) | ADC123_INP11 | FT_ha |
| Steam wand NTC | PC4 (32) | ADC12_INP4 | TT_a |
| Spare analogue input (the analogue fallback of the steam-path pressure transducer) | PC5 (33) | ADC12_INP8 | TT_a |
| Steam-path pressure transducer, I²C baseline (SCL, SDA) on a pair that also carries a UART | PB8 (95), PB9 (96) | I2C1_SCL, I2C1_SDA (AF4); also UART4_RX, UART4_TX (AF8) | FT_fh, FT_fh |
| Flow-meter pulses (input capture) | PC6 (63) | TIM8_CH1 (AF3) | FT_h |
| Mains zero-cross, both edges (input capture; interrupt line 10) | PA10 (69) | TIM1_CH3 (AF1) | FT_u |
| Coffee pump firing gate (compare) | PA9 (68) | TIM1_CH2 (AF1) | FT_u |
| Steam pump firing gate (compare) | PA8 (67) | TIM1_CH1 (AF1) | FT_fha |
| Gauge step clocks, two (compare) | PD14 (61), PD15 (62) | TIM4_CH3, TIM4_CH4 (AF2) | FT_h, FT_h |
| Indicator anode-rail gate (PWM, open-drain; 5 V) | PB5 (91) | TIM3_CH2 (AF2) | FT |
| Heater gate drive, coffee and steam (set once per half-cycle from the zero-cross interrupt) | PD2 (83), PD3 (84) | none (plain output) | FT_h, FT_h |
| Valve drive, two-way and three-way | PD4 (85), PD5 (86) | none | FT_h, FT_h |
| Gauge direction, two, and driver reset | PD0 (81), PD1 (82), PD6 (87) | none | FT_h ×3 |
| Operator panel, five key and indicator lines (bidirectional; 5 V) | PE2 (1), PE3 (2), PE4 (3), PE5 (4), PE6 (5) | none | FT_h ×5 |
| Low-water indicator cathode (open-drain; 5 V) | PE0 (97) | none | FT_h |
| Buzzer (open-drain; 5 V) | PE1 (98) | none | FT_h |
| Tank level, hot-water knob microswitch, steam knob microswitch | PE12 (42), PE13 (43), PE14 (44) | none (input) | FT_h ×3 |
| Mains presence, coffee and steam element | PE15 (45), PD7 (88) | none (input) | FT_h, FT_h |
| **Anticipated channels** | | | |
| Brew-path pressure transducer, second I²C bus on a pair that also carries a UART | PB10 (46), PB11 (47) | I2C2_SCL, I2C2_SDA (AF4); also USART3_TX, USART3_RX (AF7) | FT_f, FT_f |
| Brew-path pressure, analogue fallback | PA6 (30) | ADC12_INP3 | FT_a |
| Current sensing, one or two | PA2 (24), PA3 (25) | ADC12_INP14, ADC12_INP15 | FT_a, FT_ha |
| Direct group-head instrumentation, one or two | PA7 (31), PB0 (34) | ADC12_INP7, ADC12_INP9 | TT_a, FT_a |
| In-stream temperature converters, two, on one SPI bus: clock, data in, data out | PB13 (52), PB14 (53), PB15 (54) | SPI2_SCK, SPI2_MISO, SPI2_MOSI (AF5) | FT_u ×3 |
| The two converters' chip selects | PB12 (51), PD8 (55) | PB12 is also SPI2_NSS (AF5); PD8 plain output | FT_u, FT_h |
| Weight-based endpoint, two load-cell amplifiers, a data and a clock line each | PC8 (65), PC9 (66), PC11 (79), PC12 (80) | none (data in, clock out) | FT_h, FT_fh, FT_h, FT_h |
| Real-time clock crystal (32.768 kHz) | PC14 (8), PC15 (9) | OSC32_IN, OSC32_OUT | FT, FT |
| **Taken by the board itself** | | | |
| Serial-wire debug | PA13 (72), PA14 (76) | JTMS-SWDIO, JTCK-SWCLK (the function after reset, Table 9) | FT, FT |
| Crystal oscillator | PH0 (12), PH1 (13) | OSC_IN, OSC_OUT | FT, FT |

That is 32 pins for the current channels, and 18 for the anticipated ones (13 digital and 5 conversion), 50 in all. Against the criteria this section serves:

- **Two I²C-capable pin pairs, one at least also UART-capable.** There are two in use and both also carry a UART: PB8/PB9 (I2C1 with UART4) and PB10/PB11 (I2C2 with USART3). Two further pairs are free, PB6/PB7 (I2C1 or I2C4 with USART1, AF7) and PD12/PD13 (I2C4). The same two signal lines of the steam-path transducer can therefore be a UART without a pin change, as `controller-board-function-forms.md` § Steam-path pressure sensing asks.
- **An SPI bus with two chip selects.** SPI2 on PB13, PB14 and PB15 (AF5), with PB12 as its hardware chip select and PD8 as the second. A chip select is any free output, so a third converter costs one pin. The *_u* pins (PA9 to PA12 and PB12 to PB15, which this allocation uses for timers and the SPI bus) are supplied by VDD33USB, which Table 9 lists no pin for in this package, and they operate in the VDD range when no USB interface is used (Table 9, note 7; ST AN4938 § 2.1.2); this design uses none.
- **The load-cell amplifier lines.** Four free general-purpose pins, two per amplifier. Both amplifiers are read by driving the clock line and sampling the data line, which needs no peripheral.
- **Half-cycle and phase-angle actuation.** The heater gates are plain outputs set once per supply half-cycle from the zero-cross interrupt (the layer below the seam, `DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM`). The pump gates are compare outputs on TIM1, on the time base that also timestamps the zero-cross, so a firing delay is a compare value from a captured crossing. TIM1_CH4 (PA11) and the eight untouched general-purpose timers remain.

**Five-volt tolerance.** A pin that can be taken above the 3.3 V supply must be one the datasheet rates for it, and the rating is the operating one, the input voltage `VIN` row of the general operating conditions (Table 14 in the rev Y section, Table 112 in the rev V section, the same entries): an *FT* pin, and every I/O except BOOT0 and the *TT* pins, from −0.3 V to the lowest of `VDD`, `VDDA` and `VDD33USB` plus 3.6 V, and below 5.5 V; a *TT* pin from −0.3 V to `VDD` + 0.3 V; and above the lowest supply plus 0.3 V the pin's internal pull-up and pull-down must be off (note 3). Table 109 (Table 11 in rev Y) is the absolute-maximum stress table, a limit not to be reached in service, and it is not the rating relied on here; it adds that an *FT_a* pin used by an analogue peripheral is limited to 4 V (note 5), a condition none of the thirteen pins below meets. At a 3.3 V supply the operating limit is therefore 5.5 V, and the stress limit is the 6 V that Table 109's *Input voltage on FT_xxx pins* row gives, Min(lowest of `VDD`, `VDDA`, `VDD33USB` and `VBAT` + 4.0 V, 6 V); notes 3 and 4 there apply. The 5 V rail's worst case is 5.125 V, its nominal 5 V plus the 2.5 % that the logic-supply module's output is published within (`controller-board-design-constraints.md` § Low-voltage supply, *Output behaviour: rating, power-up and power-down*, the IRM-10 sheet; the IRM-20-5 sheet's own tolerance is not recorded there, so the figure is the IRM-10 sheet's and is re-read from the fitted module's sheet). That is 0.375 V below 5.5 V, so every 5 V-exposed use below stays inside the operating rating: the flow-meter line (only if the board pulls it to 5 V; the pin is rated either way), the key lines and the low-water cathode (anode rail), the buzzer and anode-gate stages, and the four load-cell data lines. A fault that lifts the rail is not an operating condition: the module's over-voltage shutdown acts at 5.75–6.75 V (same section, *Output behaviour: over-voltage*), above the 5.5 V operating limit and, at the top of that range, above the 6 V stress limit as well, so in that fault neither is shown to hold. The pins that can meet a level above 3.3 V are the nine below, and the four load-cell lines if the amplifiers are supplied from 5 V.

| Pin | Why it can meet 5 V | Structure (Table 9) |
|---|---|---|
| PC6 | The factory board pulls the flow-meter line up to 5 V through 2 kΩ (`controller-io.md`). The meter's output type, open-drain or push-pull, is still unread; PC6 is *FT_h*, so it is safe either way. The new board pulls the line up to 3.3 V (`controller-board-function-forms.md`, *Flow sensing*), which suits an open-drain output and is harmless to a push-pull one | FT_h |
| PE2, PE3, PE4, PE5, PE6 | Each key line is pulled toward the 5 V anode rail through its indicator elements while it is not sinking | FT_h ×5 |
| PE0 | The low-water indicator's cathode sits near the gated 5 V rail through its elements | FT_h |
| PE1 | The buzzer stage's base network ends on the 5 V rail | FT_h |
| PB5 | The anode-rail gate stage's base network ends on the 5 V rail | FT |
| PC8, PC9, PC11, PC12 | Conditional: a load-cell amplifier supplied from 5 V drives its data line to 5 V | FT_h, FT_fh, FT_h, FT_h |

All thirteen are rated, and 20 other pins with the rating are free (PA0, PA1, PA11, PA12, PA15, PB2, PB3, PB4, PB6, PB7, PC7, PC10, PC13, PD9, PD10, PD11, PD12, PD13, PE10, PE11). The earlier allocation could not be carried on this point: it put the five key lines on PE4 to PE8, and **PE7 and PE8 are *TT_ha* pins, rated 3.3 V only**; with the anode rail on, those two lines meet the 5 V rail through the indicator elements. The key lines are therefore moved to PE2 to PE6, five contiguous pins that are all *FT_h*. Their pull-ups are the external ones that `controller-board-function-forms.md` § Operator panel: keys, indicators, buzzer gives them, and the part's internal pull-up on them is left off, as note 4 requires. No level conversion is needed on any of the thirteen while the 5 V rail stays within the IRM-10 sheet's published 5 V +2.5 % worst case; the fitted module's own tolerance and over-voltage shutdown are to be re-read from its sheet, and whether a series resistor or a clamp is needed on the exposed inputs to survive a rail-high fault (shutdown at 5.75–6.75 V on the IRM-10 sheet, above the 5.5 V operating limit and possibly above the 6 V stress limit) is left to the board design task. The gauge lines do not need the rating: their buffer's inputs are TTL-level, driven from 3.3 V. PA4, PA5, PA7, PB1, PC4 and PC5, the *TT* pins that carry conversion inputs, take only the divided analogue levels the channel enumeration sets.

**Spare capacity on the interfaces in use.** Placing a function is not the same as leaving room on its interface, so the room is stated for each.

- **Timers.** Four timers carry the seven channels. TIM1 uses three of four channels, TIM4 two of four, TIM3 and TIM8 one each, so nine channels remain on the four, and TIM2, TIM5 and TIM12–TIM17 are untouched, two of them 32-bit.
- **Conversion.** Nine of the sixteen conversion pins are placed, all on ADC1 and ADC2, and the seven others remain: PA0, PA1, PA4, PA5, PB1, and PC2_C and PC3_C, the last two reaching ADC3 only. The converters resolve to 16 bits (§ 3.17).
- **Serial buses.** At the control step of 10 ms (`controller-io.md`), a transfer of the whole of a seven-byte exchange (a one-byte address and six data bytes) on an I²C bus takes 65 bit-times with nine clocks per byte and a start and stop condition: 0.65 ms at 100 kbit/s, which is 6.5 % of the step, and 0.16 ms at 400 kbit/s, 1.6 %. The bus carries one transducer, whose address is fixed (`controller-board-function-forms.md` § Steam-path pressure sensing), so the second bus is where a second one goes rather than a second address. The seven-byte exchange is an assumed bound; the transducer's own protocol is read by the design task for the board that carries it. The SPI bus is shared by two converters on separate chip selects; at a clock of 1 MHz, an exchange of an address byte and two data bytes takes 24 µs, 0.24 % of the step per converter. That clock and size are likewise a stated assumption.
- **Interrupt lines.** One line is used, and no other channel in the enumeration or among the anticipated asks for one.
- **Pins.** 26 digital pins remain: 20 rated for 5 V and 6 not (PA4, PA5, PB1, PE7, PE8, PE9). The two analogue-only pads, PC2_C and PC3_C, are separate and serve conversion inputs only, so they are no digital headroom. Of the 20 rated, PA11 and PA12 are the pair that carries USB full-speed, and PA15, PB3 and PB4 reset as debug-port pins (Table 9), so a function placed on them is placed with that in view. PC13 is a backup-domain pin whose output is limited to 3 mA (Table 52).

**Resolution of the channels read directly.** `REQ-HARDWARE-HEADROOM-001` asks that the controller not become the limit on how finely a directly read channel can be resolved, because the accuracy the control needs from each such channel is not yet established and reversing the choice means rebuying the boards. The channels this controller reads with its own converters are the three thermistor channels, the spare analogue input and the anticipated analogue channels (nine in all). The converters resolve to 16 bits where the stand-in family named by the baseline decision resolves 12; that is sixteen times as many codes across the same converter span, four more bits in hand. This is a statement of resolution, not of accuracy: the accuracy of a reading also depends on the converter's noise, its reference, the divider and the sensor, none of which this section assesses, and the accuracy the control needs is the measurement on the built machine that `controller-io.md` leaves pending. What it gives is that the converter is not the first thing a finer need would meet. A channel that needs more than any converter of this part offers is read by a dedicated converter, and room for one is held: the two in-stream temperature probes already are, each by an RTD-to-digital converter on SPI2 (`DEC-IN-STREAM-PROBES-ANTICIPATED`), whose bus has a free chip select pin for each further converter, and the load-cell amplifiers are likewise outside the part's own converters.

### The earlier pin allocation, as input only

The earlier design allocated pins on a bought module carrying this chip (`controller-design/h743-pin-allocation.csv`). It is input and nothing more: it was made for another channel set and for a board that spent pins on its own screen, card slot and flash, none of which the bare chip has. Each of its rows was re-read against DS12110 Table 9 (pin, structure, conversion input) and Table 10 (alternate function). The result, by row:

| Earlier row (pin it named) | Re-read against DS12110 | Disposition here |
|---|---|---|
| Coffee and steam heater gates (PB0, PB1; TIM3_CH3, TIM3_CH4, AF2) | Confirmed. PB0 and PB1 also carry conversion inputs (ADC12_INP9, ADC12_INP5) | Moved to PD2, PD3, plain outputs, to keep conversion pins for conversion |
| Coffee and steam pump gates (PA9 plain; PD8 plain) | PA9 is TIM1_CH2 (AF1), which the earlier row expected and had not verified: now verified. PD8 carries no timer channel | Pump gates on PA9 (TIM1_CH2) and PA8 (TIM1_CH1), both compare outputs; PD8 becomes a chip select |
| Heater energy meters (PC7, USART6_RX AF7; PA3, USART2_RX AF7) | Confirmed | Not carried: the meters are not kept (`controller-board-function-forms.md` § Heater mains-presence confirm) |
| Two pressure sensors on two I²C buses (PB8/PB9 on I2C1, PB10/PB11 on I2C2, AF4) | Confirmed. PB8/PB9 also carry I2C4 (AF6), UART4 (AF8) and PB10/PB11 carry USART3 (AF7) | Carried, with the roles swapped: the steam-path transducer on PB8/PB9, the brew-path one on PB10/PB11. Both pairs also carry a UART |
| Three thermistor channels (PC0, PC1, PC4) | Confirmed: ADC123_INP10, ADC123_INP11, ADC12_INP4. The earlier note that PC2 and PC3 do not exist on the 100-lead package is confirmed: only the analogue-only pads PC2_C and PC3_C (pins 17, 18), which reach ADC3 only | Carried |
| Three PT1000 channels, puck inlet, outlet and steam output (PA1, PA4, PA6), each marked *ADC channel not yet verified* | Verified: PA1 is ADC1_INP17, PA4 is ADC12_INP18 (and DAC1_OUT1), PA6 is ADC12_INP3 | The PT1000 probes are read by dedicated converters (`DEC-IN-STREAM-PROBES-ANTICIPATED`), so these three stay conversion pins; PA6 is placed as the brew-path analogue fallback |
| Valve relay module inputs (PD7, PD10, PD14, PD15) | All four are FT_h, so the earlier "still to be checked" is answered: rated for 5 V | Not carried: the module is replaced by a designed stage on two pins (PD4, PD5); PD14 and PD15 take the gauge step clocks |
| Gauge lines through the TTL-input buffer (PD0, PD1, PD4, PD5, PD6) | The earlier note asked for the buffer's 5 V analysis to be redone, since it was made for another part: done, no 5 V reaches these pins | PD0, PD1, PD6 carried as plain outputs; the step clocks move to timer outputs |
| Five key lines (PE4 to PE8) | PE4, PE5, PE6 are FT_h. **PE7 and PE8 are TT_ha: not rated for 5 V** | PE4 to PE6 carried; PE7 and PE8 replaced by PE2, PE3 (FT_h) |
| Anode-rail gate (PB5; TIM3_CH2 AF2, *AF not yet verified*) | Verified: TIM3_CH2 is AF2; PB5 is FT | Carried |
| Buzzer (PB4) | PB4 is FT, but it resets as NJTRST (Table 9) | Moved to PE1, which carries no debug function |
| Low-water indicator cathode (PA0) | PA0 is FT_a | Moved to PE0, to keep PA0 (ADC1_INP16) for conversion |
| Tank level (PE9), hot-water knob (PE15), steam knob (PC6) | PE9 is TT_ha, fit for a 3.3 V input; PE15 FT_h; PC6 FT_h | Moved to PE12, PE13, PE14, so the inputs sit together; PE15 is taken by a mains-presence input and PC6 by the flow meter |
| Flow meter (PA8; TIM1_CH1 AF1; *5 V tolerance to be checked*) | TIM1_CH1 on PA8 is AF1, confirmed. PA8 is FT_fha: rated for 5 V | Moved to PC6 (TIM8_CH1, AF3, FT_h) so that the zero-cross and pump gates share TIM1 and the flow capture has a timer of its own |
| Mains zero-cross (PA10; TIM1_CH3 AF1, *AF not yet verified*) | Verified: TIM1_CH3 is AF1 | Carried |
| Mains-presence confirm (*unassigned*) | — | PE15, PD7, plain inputs |
| Pins the module encumbered (screen, card slot, flash, camera header) | Not a property of the bare chip | Not carried; all of those pins are free on the board |

No row of the earlier allocation is carried on its own authority. Every row reused above was re-read in the datasheet and none is carried as *not verified*. The module's header map (`controller-design/h743-header-pinout.csv`) is not a datasheet matter and is not used.

### What this assessment does not establish

- **Compute and memory are unquantified on both sides.** The enumeration states no RAM, flash or clock requirement, and measuring the control law's actual execution time is on-target work under a later phase. 2 Mbyte, about 1 Mbyte of RAM and 480 MHz are recorded as what the part provides, not as what the design needs. No headroom claim is made about them in either direction; taking the larger flash is a refusal to narrow an unmeasured envelope.
- **A specific board's usable subset is narrower than the part's.** These figures are the microcontroller's. The pins that the board's own functions take, the debug port and the oscillator, are already subtracted above; the rest of the board's own needs (its reset and boot parts, programming header and decoupling) spend no port pin. The pin allocation of each board is authored by the design task for that board against this part, and the pre-order board check refuses a pin the part does not have.
- **The reference-manual behaviours are not read.** DS12110 states the pin functions, the structures and the electrical limits used above, but not the reset state of the debug-port pins, the switch between a *Pxy_C* pad and its *Pxy* pin, or how the interrupt lines are shared between ports. None of the placements above depends on any of the three, and the board task reads them from ST's reference manual for the part before it relies on them.
- **The selection is made, not provisional.** The part is selected here, within the family `DEC-CONTROLLER-BASELINE-STM32H743` baselines, and the board check holds every design to it. What later measurement of the plant parameters can still change is the margin, not the part: the headroom is what lets a later finding be absorbed without replacing the controller.

### What the selection means for the firmware

The firmware's target build, its hardware-backed implementation of the hardware seam and the emulation tier were built against an STM32F4 part that the project named only so a target build could exist before any controller was chosen. That part is not the controller. Each of the three names it today, and each must name the STM32H743 instead:

| Part of the firmware | Names today (a stand-in, not chosen) | Must name |
|---|---|---|
| The target build, `firmware/platformio.ini`, environment `stm32_base` | `board = genericSTM32F407VGT6` | A board definition for the STM32H743VI |
| The hardware-backed seam implementation, `firmware/src/hw/stm32/hw_stm32.c` and `hw_stm32_vectors.c` | The STM32F4 vendor header `stm32f4xx_hal.h`, the STM32F4 startup file `startup_stm32f407xx.s` named in the vectors file's comment, and the vector names of that part | The STM32H7 family's vendor header and the H743's startup file and vector names |
| The emulation tier, `firmware/emulation/` | The emulated machine `platform/brew_state_stm32f407.repl.in` (its F4 reset-and-clock, real-time-clock and flash-controller models), the peripheral models `peripherals/adc1.py` and `peripherals/tim3.py` written on the STM32F4 register maps, and `tools/pins.json`, which pins the STM32F407 register description | An H743 machine description, peripheral models written on the register maps of the H743's own register description from the manufacturer, and a pin to that description |

The control logic does not change: the seam, `firmware/include/hw_interface.h`, is vendor-free and takes a level per actuation channel, which is the property the seam exists to demonstrate. The delivery node that carries the change is `DEL-FIRMWARE-TARGET-ON-SELECTED-CONTROLLER`, which also re-records the emulation evidence on the new machine. The emulator itself stands; Renode supports the STM32H7 family (owner statement). Making the change is that node's work, not this selection's.

## The component list

This is a specification, not a shopping list. Each row states what a part on that channel has to
satisfy and what the OEM device already achieves, so a candidate — bought new, taken off this
machine, or recovered from a donor machine — can be held against the row and judged. **Which part
serves a channel, and where it comes from, is the builder's decision and is recorded once made.**
The controller is the one row so far closed, by § The part selected; no other row is closed by this
document.

**Declared spend: 250 USD**, covering what the retrofit adds and excluding the machine it is added
to, and, by the owner's answers of 2026-10-26, excluding what the owner sources himself (the
steam-path assembly) and not counting a second spin. This is the figure `REQ-COST-DISCIPLINE-001.C5` and `DEL-COMPONENT-SPECIFICATION.C5` require to
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
| Controller | Every row of the resource assessment above, simultaneously, with room for the anticipated channels. Checked against the specific board's own schematic, since a board's usable pins are fewer than its microcontroller's | None — the machine carries no part serving this | **STM32H743VIT6**, STMicroelectronics, LQFP100, 2 Mbyte flash; JLCPCB catalogue number C114409 (§ The part selected) | Bought | 10.68 USD for the part (10.6814 USD at 1–9 pieces) and 3.07 USD feeder loading per order under Economic assembly, so 13.75 USD for one machine's part; read 2026-10-24. At the build count of two it is 24.43 USD, counted in the main board's lines of `controller-board-cost-estimate.md` |
| Coffee element switching | Commandable once per supply half-cycle; carries 4.80 A at the top of the declared supply span; dissipates 4.25 W at full duty (17.1 W in the 15 A overload band; the sourced triac dissipation of `controller-board-function-forms.md` § Parts off the boards), in an ambient that is pending: on the owner's plan, 2026-10-23, the two heater switches are mounted outside the enclosure, on a designed wall board whose triacs bolt to the machine's metal wall (the form decided in `controller-board-function-forms.md` § Coffee element switching and steam element switching), as a device the retrofit adds, and each triac is judged against its rated temperature by the design task for the heater-switch assembly (`controller-board-function-forms.md` § Parts off the boards); the air inside the enclosure is graded to an assumed 70 °C until bring-up measures it (§ Enclosure air temperature; the room-temperature span is in `reference-machine.md` § Ambient); commanded across an isolating barrier; does **not** reach the de-energised state on failure by itself, so the channel depends on the series interlock discussed above | Hongfa `HF3FD/012HST` relay: isolated, fails open, but cannot be commanded per half-cycle. Clears every property except the one that matters most here | *undecided* | *undecided* | |
| Steam element switching | As above, at 5.38 A and 4.84 W at full duty (same source) | Hongfa `HF3FD/012HST` relay, same reading | *undecided* | *undecided* | |
| Heater gate drive, both channels | Firing at the zero crossing in hardware rather than at an instant the controller estimates, which removes this channel's exposure to the unbounded edge-versus-crossing offset; isolation between the controller pin and the mains-referenced gate | None on this channel — the OEM relay needed no gate drive | *undecided* | *undecided* | |
| Coffee pump switching | A firing instant placed within the cycle; isolated gate drive; de-energised on failure. Current 0.46 A rms at 253 V, the sizing value under an assumed 0.5 power-factor floor (nameplate 48 W; `connector-pinouts.md` § Pumps: running current) | `MOC3021` opto-triac into a triac. Phase-capable: this channel's floor is already at the requirement | *undecided* | *undecided* | |
| Steam pump switching | As above; 0.19 A rms at 253 V (nameplate 22 W), the sizing value on the same basis | `MOC3021` opto-triac into a triac | *undecided* | *undecided* | |
| Two-way valve switching | Per-delivery switching of a mains AC coil marked 9–13.5 VA, at most 64.6 mA rms steady and 101.4 mA rms inrush at 253 V; isolated; de-energised on failure, which on this channel may also be the venting state | Hongfa `HF32FA/012HSL` relay. Adequate for a per-delivery channel | *undecided* | *undecided* | |
| Three-way valve switching | As above | Hongfa `HF32FA/012HSL` relay | *undecided* | *undecided* | |
| Supply-timing front end | Both crossings of every cycle; a barrier holding under fault and under water, steam and thermal cycling; read as an input rather than followed as a clock | `PC817` optocoupler on a half-wave feed. Isolation adequate; **fails the both-crossings property**, which is the one this design added | *undecided* | *undecided* | |
| Coffee, steam and wand temperature sensing | Analogue resistance, NTC, at the accuracy `controller-io.md` states per channel | `EM70025`, `EM70020` and the wand disc sensor, fitted and working | *undecided* | *undecided* | |
| Flow sensing | A pulse train on a general-purpose port pin, which the factory board pulls up to 5 V; the output type (open-drain or push-pull) and the K-factor stay open; the new board pulls the line up to 3.3 V | The fitted OEM meter | *undecided* | *undecided* | |
| Steam-path pressure sensing | Analogue conversion; a bought transducer, the form decided in `controller-board-function-forms.md`, whose fitted part is selected by the design task for the board or assembly carrying it. Its range and accuracy bounds and the proof and burst pressures it must carry are stated in `controller-board-design-constraints.md` § Steam-path transducer pressure and § Sensing accuracy, and are checked against the part once chosen | None — added by decision, never fitted | *undecided* | *undecided* | |
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
| Channels whose part is decided | 1: the controller |
| Bought to date | See `controller-board-design-constraints.md` § Purchases ahead of verification, which states none |
| Reused to date | 0 |
| Salvaged to date | 0 |
| **Declared spend** | **250** |
| **Remaining, against what is bought** | **250.00** |
| Block-level estimate, the board orders (the main board with the mains-entry parts and the heater wall board; the controller's 24.43 inside it), first order: what the declared spend counts | 149.63 (89.51 a machine), on the owner's decision of 2026-10-25 to fit one set of the through-hole parts by hand and have the manufacturer assemble only the surface-mount parts |
| **Board orders, first order, against what remains** | **100.37 inside** |
| For information, outside the declared figure: the owner-sourced steam-path assembly | 46.40; the board orders and it, first order, 196.03 (135.91 a machine), 53.97 inside |
| For information, outside the declared figure: a likely second spin | board orders with it 299.26 (179.02 a machine), 49.26 over; with the steam rebuy as well, 366.75 (246.51 a machine), 116.75 over |

Nothing has been bought, so spend to date is 0 and 250.00 USD remains. The running total is the block-level estimate of `controller-board-cost-estimate.md`, which prices every board and off-board assembly the division names (the steam-path assembly as an owner-sourced line, shown apart) at its chosen outline and layer count (fabrication, assembly, parts, shipping, import tax and a likely second spin) and which replaces the 13.74 USD carried here before it for the controller alone, now inside the main board's parts. The count the declared spend takes is what the owner pays for the minimum order, 5 boards fabricated and 2 assembled for each board the manufacturer makes, with the cost per machine shown beside it. By the owner's answers of 2026-10-26 the declared spend counts the board orders: it excludes the items the owner sources (the steam-path assembly) and does not count a likely second spin. The board orders, first order, are 149.63 USD, 100.37 inside what remains, so the weighing is met and the figure stays 250 USD (`controller-board-cost-estimate.md` § Weighed against the declared spend). The owner-sourced assembly and a second spin are shown for information only. The machine carries no part serving the controller channel, so there is no reused part to depart from, and the controller is a catalogue part of a mainstream family; no other channel is decided yet, so no other departure from the reused-or-commodity
default is yet owed a justification under `REQ-COST-DISCIPLINE-001.C2`. The total is kept running as
rows close because `REQ-COST-DISCIPLINE-001.C6` judges a channel decided late against what is left,
not against the headroom the first channel enjoyed.

Two rows are worth reading against `REQ-COST-DISCIPLINE-001.C4` before they are decided. The heater
channels' parts are cheap and their failure is a hazard, which is exactly the combination that
criterion says to weigh — and the answer is not a dearer triac, since failing shorted is a property
of the device class rather than of its price. It is the series interlock. That, the relief question
on the steam side, and whatever the panel decision settles all sit outside this list and will draw on
the declared figure.
