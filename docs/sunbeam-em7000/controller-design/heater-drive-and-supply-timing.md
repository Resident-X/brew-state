# Heater drive and supply timing

Refreshed 2026-10-12 from `decisions.md` (which supersedes older text), the current design data in this folder, and the earlier working note of the same name. **Not baselined, not traced to any criterion, and not evidence for anything.** It records whether the controller needs a zero-cross reference for the heaters, what drives the heaters, how the burst scheme works, why the BL0942 energy meters are fitted, and how each switching channel is snubbed. Nothing here is in the graph yet (`decisions.md`).

Status words follow `decisions.md`: Chosen, Owner decision, Agreed, Recommended, Owner statement, Parts list, Schematic, Published unverified, Inferred, Unmeasured.

## Where the design stands

| Item | State | Status |
|---|---|---|
| Heaters | Two EARU SSR-40DA zero-cross SSRs, low-side driven by one ULN2003A breakout (buy 2, fit 1), SSR control + to 5V, 10k pull-downs at the breakout inputs | Chosen (D2) |
| Pumps | Two RBdimmer 4A Standard (Z-C/DIM) modules, one shared Z-C on PA10, DIM on PA9 (coffee) and PD8 (steam), 10k DIM pull-downs, 1-2 A slow-blow branch fuse per module | Chosen (D3) |
| Valves | 4-channel mechanical relay module, two RC snubbers (one per valve) | Chosen (D5) |
| Energy metering | Two BL0942 isolated energy-meter modules in series upstream of each SSR | Chosen (D17); no BOM row yet; isolation to be measured |
| Heater phase reference | None. The SSRs align themselves; the controller needs the supply **period**, not the phase | Argued below |
| Supply period source | The shared Z-C capture on PA10 (from the coffee-pump dimmer), and the BL0942 | Chosen (D3, D17) |

The pump dimmers are the Standard variant, so the controller has a both-crossings Z-C input after all, for the pumps. The heater argument below is unaffected. No separate zero-cross detector is bought.

## The question

`DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM` requires a detection front end presenting **both crossings of each cycle**, and explicitly rejects leaving alignment to the switching device because that "costs the ability to say how many half-cycles were actually delivered."

The heater SSRs are zero-cross type and align themselves, and the valve relays are per-delivery on/off with no phase relationship at all. The pump dimmers are fired by the controller from the Z-C pulse. So: is a reference still needed for the heaters?

**Contingency.** The heater argument rests on the SSRs being zero-cross. The generic SSR-40DA class is zero-cross, but the property is **load-bearing** and has **not been confirmed on EARU's own datasheet** (BOM, part-numbers). To confirm before the graph revision is authored. A random-phase part reopens the whole question. (EARU replaced the Fotek SSR-25DA because counterfeit Foteks are endemic and fakes are grossly over-rated; the zero-cross property was carried across on the class spec rather than verified.)

## The cancellation argument: no, not for phase

Assert at time t0 at phase φ into a half-cycle. A zero-cross SSR starts conducting at the next crossing, so it is late by `(T/2 − φ)`. De-assert after commanded duration D; it stops at the next crossing after that. Conduction time is:

```
conduction = D − ((φ + D) mod T/2) + φ
```

If **D is an integer multiple of T/2**, then `(φ + N·T/2) mod T/2 = φ`, and this collapses to:

```
conduction = D − φ + φ = D
```

**Exactly D, for any φ.** The late start and the late stop are the same lateness and they cancel. N half-cycles are delivered regardless of where the assert landed.

If D is *not* an integer multiple, the result is N or N+1 half-cycles depending on φ, bounded at ±1 and averaging to the commanded value as φ walks. That case need not arise, because D can be chosen as a whole number of *measured* half-periods.

**So the decision conflated two requirements.** What the scheme needs is the supply's **period**, not its **phase**:

- **Period** is needed to choose D and to avoid the beat between the controller's crystal and the supply. Without it, a 200.00 ms window against a true 10.002 ms half-period walks slowly and occasionally delivers 19 or 21 half-cycles instead of 20, a slow few-percent ripple at the beat frequency. Setting D from the measured period removes it.
- **Phase** is not needed, by the argument above.

Period comes from the Z-C capture on PA10 and from the BL0942. Z-C is believed full-wave (an edge every half-cycle) by inference from the vendor library; the acceptance test on arrival is about 100 edges/s on a 50 Hz supply, not 50. Output type, pulse width and polarity of Z-C are not published and are to be scoped on arrival.

## What the four claimed uses of a zero-cross channel are worth

| Claim in the decision | Held against the selected parts |
|---|---|
| The energy account: knowing half-cycles delivered | Exact for the heaters without a phase reference, per the cancellation argument, provided D is a whole number of half-periods |
| Supply-fault detection: an edge outside a plausible window, or missing | The one real casualty for the heaters. BL0942 RMS voltage covers it more directly than counting edges. The shared Z-C also gives an edge-window check: loss of Z-C or of AC-N removes the pump timing reference, so firmware stops firing and raises a fault (module-interconnect) |
| Supply timing read live, with the nominal frequency declared (REQ-MACHINE-CONFIGURATION-001.C9) | Served by the Z-C capture and the BL0942 |
| Safety-relevant marking | `controller-io.md` marks the zero-cross channel so "not because it switches anything, which it does not, but because it is the only mains-referenced *sensing* channel." That is about the channel's isolation barrier being a place mains could bridge. The pump dimmer module's optical isolation (the vendor page states no isolation figure, read 2026-10-13) is to be measured, not assumed |

## Heater drive electrics

- **EARU SSR-40DA**, 40 A part against element currents of 4.36 A (coffee, 52.7 Ω) and 4.89 A (steam, 47.0 Ω) at 230 V, rising to 4.80 A and 5.38 A at 253 V (`component-specification.md`; 230/52.7 = 4.36, 253/52.7 = 4.80, 230/47.0 = 4.89, 253/47.0 = 5.38). The BOM's 4.80 A and 5.38 A are the 253 V figures. Control input 3-32 VDC at 7.5-12 mA. 3.3 V is the bottom of that range and an STM32 pin sourcing 12 mA sags below its rail, so the SSR is **not** driven from a 3V3 GPIO.
- **ULN2003A 7-channel breakout** sinks each SSR control input from the 5V rail (SSR control + to 5V, control - to OUT1 for the coffee heater and OUT2 for the steam heater). IN1/IN2 come from PB0/PB1, about 24 mA total. The Darlington drops about 1 V, so each SSR sees about 4 V, above its 3 V minimum. **Unmeasured; measure it.** Low-side drive means a lost wire turns the SSR off.
- **Safety.** A floating or reset GPIO must leave the heater off (`OBL-ELECTRICAL-THERMAL-SAFETY-001.C2`). A 10k pull-down across each used input and GND is fitted at the breakout board's own header pins, so it still holds if the controller cable comes off. SAFETY-CRITICAL until the breakout's floating-input behaviour is measured. Unknown on the breakout: the GND/VCC jumper header's function, and whether the LEDs load the outputs.
- **SSR input series resistor: not needed.** A 3-32 VDC input at 7.5-12 mA implies a built-in limiter (owner's judgement); first bench check is that the control current sits near 7.5-12 mA.
- **Heatsink.** The junction drop, not the current rating, sets dissipation: about 5-6 W per channel for the 40 A part (BOM estimate, not confirmed for EARU's package), against about 0.1 W for the OEM relays' coarse on/off. That dissipation is the price of burst firing (cadence is an open decision). **Proposed, not decided: try mounting the SSRs direct to the side wall** (BOM user note) instead of on heatsinks. The wall is plastic and unearthed as found (reference-machine.md § Controller enclosure as found). The thermal side conflicts: each SSR dissipates about 5-6.5 W, which would be conducted into the wall and the enclosure air, and the IRM-10-5 5 V supply derates from 100 % load at 50 °C ambient (`mains-inlet-protection.md`). Mounting on a wall that is also the 5 V supply's ambient raises that ambient. Owner to decide after a thermal test. *Superseded 2026-10-23:* the owner's plan is to mount the heater switches outside the enclosure on the machine's metal wall (`controller-board-design-constraints.md` § Enclosure air temperature).

## The drive scheme

**GPIO, not a bus.** The SSRs are driven directly from timer-backed GPIO. No serial link is in the timing path. The BL0942's UART carries only integrated scalars, where latency is irrelevant. That split, *timing on pins, measurements on buses*, is why the bus-latency objection that rules out zero-cross-over-I²C does not touch the metering.

**Window.** 1 s is the tidy choice: 100 half-cycles (50 whole cycles) at 50 Hz. Duty resolution is 1 % if the decision is taken per half-cycle and 2 % if it is taken per whole 20 ms cycle, which is the granularity this document's scheme uses (next paragraphs). Compute N from the measured period so the scheme stays frequency-agnostic (120 half-cycles at 60 Hz).

**Spread the conducting cycles; do not fire contiguous blocks.** An accumulator that adds the commanded duty each half-period, fires on overflow and carries the remainder, delta-sigma. Same delivered duty, but the thermal ripple collapses and the modulation moves away from the ~8-10 Hz human flicker-sensitivity peak instead of parking near it at ~1 Hz.

This is exactly what the decision already specifies: "a decision, taken once per supply half-cycle, to energise the channel or leave it idle... the residual a level leaves between whole half-cycles is carried forward rather than discarded." The residual-carrying scheme **is** the spreading scheme. The only departure is that the half-period boundaries come from a free-running accumulator clocked at the measured period, rather than from a locked edge: a constant unknown offset from the true crossings, identical delivered counts.

**Spread at whole-cycle (20 ms) granularity** rather than single half-cycles, to keep DC balance clean and stay inside what a zero-cross SSR switches comfortably.

**OPEN DECISION: heater switching cadence.** This document's scheme is whole-cycle (20 ms) bursts. `control-system-bom.csv`, `controller-io.md` and `component-specification.md` read the cadence as half-cycle ("once per supply half-cycle"; "the price of burst firing (cadence is an open decision)"). The facts: a whole-cycle burst delivers an even number of half-cycles, so the net DC component is zero; a zero-cross SSR switches at zero crossings, so the minimum conduction it can deliver is one half-cycle; single half-cycles (odd counts) can inject a DC component into the supply (see "What this owes the graph"). The choice sets duty resolution (2 % per cycle against 1 % per half-cycle at a 1 s, 50 Hz window) and what `DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM` is read to require. Not decided here; owner to decide, then align the four documents.

**Ripple sanity check** (order of magnitude only; the block mass is not established, unmeasured). At ~0.5-0.8 kg of aluminium and ~1000 W, heating is roughly 1.5-2 K/s with no flow, so contiguous 50 %-duty bursts would give about 0.75-1.0 K peak-to-peak at a 1 s window (1.5-2 K/s x 0.5 s on; an earlier 0.9-1.9 K figure was not reproducible from these numbers and is withdrawn) and roughly double at 2 s. That matters against the "few degrees" margin the `REQ-MEASUREMENT-001` margin note describes. Spreading removes almost all of it, and the worst ripple occurs at 50 % duty, which is heat-up, when it matters least; steady-state idle sits at maybe 5-10 % duty.

**Flicker is worth a bench observation.** Burst-firing 1.1-1.2 kW at a few hertz produces supply voltage flicker, the phenomenon EN61000-3-3 addresses. Not a blocker, but choose the window deliberately and watch whether lights elsewhere in the house respond.

## BL0942 energy metering: a separate, stronger case

Two BL0942 modules (D17, Chosen; no BOM row yet; isolation to be measured), one per heater. Adopting them for **energy measurement** stands on its own merits, independent of the zero-cross question.

**Why measure rather than infer.** Delivered power is not the commanded duty times a nominal figure. The declared supply span is 216–253 V (`reference-machine.md` § Supply), and power goes as V², so delivered power moves by about **−12 % to +21 %** about its 230 V value, about 37 % from the bottom of the span to the top. Element resistance drift is a much weaker term (nichrome-class alloys run around 85 ppm/°C, roughly 1 % over a 100 °C rise), but the *measured* resistance is itself uncertain: `component-specification.md` records the steam element's 47.0 Ω as a **lower bound**, because the bench could not isolate it.

**Where it pays.** Not the temperature loop, which already rejects supply variation through feedback. The case is the **model-based state reconstruction**: an observer driven by heat input takes a 21 %-plus systematic error straight into its estimate, and no downstream feedback repairs a wrong input to an open-loop observer. *(Contingent on the estimator actually integrating heat input; `SOL-UNMEASURED-STATE-RECONSTRUCTION` has not been read against this claim.)*

Secondary: quantitative per-channel **actuation confirmation**. The OEM's binary LTV814 mains-presence bit on CFSIG/SMSIG would be replaced by the BL0942 current reading (D20, **Recommended, not decided**: it loses localisation of "did not close" versus "open downstream"; `controller-io.md` marks mains presence safety-relevant, so decide before retiring that row). The reading distinguishes a welded contact, an open thermal cutout and a partially failed element rather than just "current or no current."

**Zero-cross is NOT available over its UART.** Established from the datasheet: ZX is hardware **pin 9**, its function selected by the `OT_FUNX` register (0x18). The only ZX-related register bits are `I_ZX_LTH_F` [8] and `V_ZX_LTH_F` [9], which flag that the signal is *below* the detection threshold, a fault indication, not a crossing event. Independently, the packet is 23 bytes and the datasheet states this "takes about 48 ms when 4800 bps is used", 2.4 mains cycles per packet, and ~6 ms even at 38400 baud. A 10 ms boundary cannot be represented in that stream. ZX is not brought out on the module header.

**A figure the graph currently lacks.** The datasheet declares a **ZX output delay of 570 µs** (5.7 % of a half-cycle at 50 Hz). `DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM` states that the phase offset between a true crossing and a detected edge is a quantity "no declared figure bounds and which this decision does not invent." This is such a figure. Whether it is typical or maximum is not clear from the table's layout; to confirm before relying on it.

**Placement: upstream of the SSR, not downstream.**

The tempting argument is to put the meter after the SSR so the triac's on-state drop is excluded and only element energy is counted. `component-specification.md` puts that drop at 1.2-1.4 V, "of the order of 6 W" per channel, against 230 V and ~1100 W, **0.57 %** of delivered energy, which is about the BL0942's own energy accuracy. It is not worth what it costs.

Current does not care where the shunt sits: it is a **series circuit**, so the shunt reads element current identically before the SSR, after it, or in the neutral return. Only the **voltage** channel has a preference, and downstream placement breaks three things:

- **Period measurement**, the one supply quantity the whole drive scheme depends on, since the cancellation argument holds only while D is a whole number of measured half-periods. A period cannot be measured from a waveform absent for most of the duty cycle (steady-state idle runs at perhaps 5-10 %).
- **Supply monitoring**: RMS voltage would report a duty-weighted figure rather than supply voltage, and that reading is what replaces edge-based fault detection for the heaters.
- **ZX**, if pin 9 is ever brought out: intermittent, so useless as a reference.

Subtler: the BL0942's calibration-free frequency tracking expects a continuous line, and will lose lock on a waveform that collapses to zero for whole half-cycles.

**If the 0.57 % matters, correct it in firmware**: subtract `I × V_drop` using the datasheet figure or a bench characterisation. The triac drop is roughly constant and weakly current-dependent. Zero hardware cost.

Keep the proportions in view: this part exists to fix a **±21 %** error from supply variation. Trading away period measurement to recover **0.57 %** would be repairing the third decimal place by breaking the first.

Upstream placement means the module is live whenever the machine is plugged in, as it must be to monitor continuously. That makes the isolation test below more important, not less.

If the module is a four-terminal pass-through (L in / L out / N in / N out) its voltage tap is internal and the sense points cannot be separated, which settles the question. If it exposes the voltage sense separately, V upstream with the shunt anywhere is equivalent and not worth the extra wiring.

**UART wiring.** Coffee heater meter TX to PC7 (USART6_RX, AF7); steam heater meter TX to PA3 (USART2_RX, AF7), both confirmed against DS12110 (h743-pin-allocation). Free-running mode is TX-only, so RX alone may suffice (to confirm whether the module needs commands; PC6 or PA2 would then be the TX pins). Optional 4.7k pull-ups on the module RX line (0-2), moot until isolation is established.

**Blocked on isolation.** The BL0942 is inherently mains-referenced: the current channel is a differential input across a 1-2 mΩ shunt in the mains path, and the voltage channel is a resistor divider off the mains. A current transformer would isolate the current channel but not the chip. So its UART and ZX pins sit at mains potential unless the specific module carries a barrier. Its VCC/GND connect to the controller 3V3/GND **only if the module is isolated**.

**Acceptance test, before connecting anything:** out of circuit, measure resistance between every header pin and every mains terminal, all combinations. Isolated reads open (tens of megohms). Any low reading means common reference and a live header. Look also for a routed slot in the PCB under the optocoupler separating the ground pours. **Treat as non-isolated until this passes.**

Note the structural tension: bringing ZX across a barrier needs its own isolator channel, which a module built around a single TX optocoupler will not have. So on a cheap module, "isolated" and "ZX available" are close to mutually exclusive. Getting both means building a small board: BL0942 + dual digital isolator + isolated DC-DC. Both heaters see the same mains phase, so two meters would need only **one** isolated ZX channel. With the Z-C from the pump dimmer in place, ZX is not needed by the design.

## Snubbing, by channel

Three switching channels, three different answers. The same prebuilt RC+MOV module suits exactly one of them.

| Channel | Switch | Snubber? |
|---|---|---|
| Heaters | SSR (semiconductor, zero-cross) | **None.** Resistive load, no contacts to arc, and the dv/dt case applies to inductive loads only. Most SSRs carry an internal snubber regardless |
| Valve solenoids | Mechanical relay contacts | **Yes**: 100 nF + 220 R with a 10D471K, one per channel, two fitted. Mains-AC coils are inductive and the contacts arc |
| Pumps | Triac, phase-cut | **Not this module, and probably none at all** |

**Valve relays.** 220 R is preferred over the 100 R originally specified: it limits the capacitor's discharge into closing contacts to 1.5 A at 325 V peak rather than 3.3 A. The 470 V varistor is correct *here*, because across open contacts a MOV must stay non-conducting at normal line peak, even though the mains-inlet MOV is deliberately the lower 275 V / 431 class. Same family, opposite answer, because the jobs differ. The capacitor needs an X2 rating (across mains contacts).

**A consequence to remember:** 100 nF is 31.8 kΩ at 50 Hz, so with the contacts open about 7.2 mA flows through the snubber (230 V over 100 nF at 31.8 kΩ, 220 Ω and the coil's 2.5 kΩ cold resistance in series, 2.496 kΩ and 2.497 kΩ measured (`../connector-pinouts.md`): |Z| = √((220 + 2496)² + 31 831²) ≈ 31.9 kΩ, 230 ÷ 31.9 kΩ = 7.2 mA), leaving roughly 18 V across the solenoid coil permanently if the coil is taken as its cold resistance (7.2 mA × 2.5 kΩ), which is the lower bound. The coil is inductive: its marking, 9–13.5 VA at 230 V (`../connector-pinouts.md`), gives a sealed-coil impedance of 230² ÷ VA = 3.92–5.88 kΩ, so the same series loop carries 7.95–8.63 mA and leaves about 31–51 V across the coil, 13–22 % of line. The plunger-open state lies between these and is not recorded, so the residual is 8–22 % of line. Whether that holds a valve in is **not established**: no drop-out or holding voltage is recorded for these coils, so the residual of up to about 51 V (22 % of line) is neither shown to be too little nor shown to be enough, and the assumption that it is too little is unverified (to confirm on the bench, since the vent valve's fail-safe state rests on it). **"De-energised" is also no longer zero**, which matters to the fail-safe vent hypothesis in `reference-machine.md` § Protection, to `REQ-FAULT-RESPONSE-001.C1`, and to whether a valve is safely isolated for servicing merely because its relay is open. The 2-way vent valve is normally open and is energised closed whenever the coffee pump is pumping through the block (the 30-40 s shot; also hot water; the pre-shot flush; dry-fill and identification runs) (D6, Owner decision), so the residual voltage is inferred not to close it; to confirm on the bench.

**Pumps: why not the same part.** A 100 nF snubber passes ~7.2 mA, and a BT136's holding current is only ~10-25 mA by grade. That is close enough to risk the triac latching permanently on. Triac snubbers are correspondingly smaller (about 39 R + 10 nF or 100 R + 47 nF, 0.7-3.4 mA) and fit MT1-MT2 rather than across a switch. A second reason: any RC across a phase-cut triac leaks current to the load during the off part of the cycle, costing the bottom of the control range.

**And probably none is needed.** Commutation stress scales with load current, and the `(dI/dt)c` and `(dV/dt)c` figures that cause commutation failure on inductive loads are specified at the device's rated 4 A. The pump's current is 0.46 A (coffee) or 0.19 A (steam) at 253 V, the sizing values under an assumed 0.5 power-factor floor (`../connector-pinouts.md` § Pumps: running current; the estimate taking the nameplate power at 253 V is 0.38 A / 0.174 A); either way it is under 12 % of the rating, so the margin is large (EP5 pump 48 W, JYPC-4 22 W; nameplates, inspected). The fitted triac reads BT136S-600E from the board photo: the W suffix denotes snubberless, B/C/D/E are gate-sensitivity grades, so it appears **not** to be snubberless. The open item is only to *confirm* what the RBdimmer board already fits (a "102"/1 nF marking sits near the triac but cannot be identified from a photo), not to add parts pre-emptively. If insurance is ever wanted, the right fix is a **snubberless** triac (`BTA`-xxx-`BW`), which solves commutation by construction without leaking current around the switch. The steam-pump drive scheme (phase-angle versus burst) is open (D4), to be settled on the bench.

## What this owes the graph

**Nothing has been authored. This file is not the record.** (`decisions.md`: nothing in this folder is in the graph yet.)

`DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM` does not merely omit the cancellation argument; it *rules* on it, requiring a both-crossings front end and rejecting device-level alignment by name. Building the heaters this way makes the graph describe a machine that is not being built. The module-interconnect record states the revision as owed, and notes that the both-crossings reference is now present again for the pumps through the Standard dimmer's Z-C, while the zero-cross enumeration row has not been re-read or amended.

The revision is narrow. Most of the decision survives intact:

- **Keep** the per-half-cycle residual-carrying layer below the seam, exactly as written. It is the spreading scheme, and it is right.
- **Keep** the crystal-derived control period.
- **Replace**, for the heaters, "the detection front end presents both crossings of each cycle" with a requirement that the supply's **period** is measured.
- **Justify** with the cancellation argument, stating that it holds only while D is a whole number of measured half-periods.
- **State the contingency**: this rests on the SSRs remaining zero-cross type, to be verified on EARU's own datasheet **before the revision is authored**.
- **Record what is given up for the heaters**: edge-level supply-fault detection, and its replacement by RMS voltage measurement, which makes the BL0942 (or an equivalent) load-bearing rather than optional, a new dependency the decision must state.

`SOL-CONTROLLER-AND-MAINS-PARTS-DOWN-SELECT.C2` names "the supply-timing front end" as a thing specified by property, and `controller-io.md` carries a zero-cross sensing row. Both move with the decision. This is the *amending without propagating* pattern `CLAUDE.md` names, and the propagation has not been done.

Two further items surfaced and are also unauthored:

- **DC injection.** Odd numbers of half-cycles inject a DC component into the supply; industrial integral-cycle controllers use whole cycles to avoid it. The decision's rationale weighs the beat, the account, the flywheel and the supply-fault case, but does not mention DC at all. That looks like a gap in it rather than something it decided against.
- **Voltage flicker** from burst-firing kilowatt loads is not addressed by any criterion.

## Open items

- EARU SSR-40DA zero-cross type, package dimensions and heatsink need: unconfirmed (datasheet).
- SSR control voltage with the ULN2003A in circuit (about 4 V expected) and control current: unmeasured.
- ULN2003A breakout: floating-input behaviour, GND/VCC jumper function, LED loading: unmeasured.
- BL0942 module isolation: unmeasured; blocks connection. No BOM row yet.
- BL0942 ZX delay (570 µs): typical or maximum not established.
- Z-C output type, pulse width, polarity, full-wave edge rate: scope on arrival.
- Pump triac snubber fitted or not: verify on the RBdimmer board.
- Steam pump drive scheme (D4): bench test.
- D20 (BL0942 replaces mains-presence confirm): Recommended, not decided.
