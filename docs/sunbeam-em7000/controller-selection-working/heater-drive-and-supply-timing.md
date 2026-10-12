# Heater drive and supply timing — working notes

Working draft from the same in-flight selection as the rest of this directory. **Not baselined,
not traced to any criterion, and not evidence for anything.** It records a working-through of
whether the controller needs a zero-cross reference at all, and what replaces it if not.

**Position update, 2026-10-05.** The pumps moved from the RBdimmer DimmerLink variant to the
**Standard** variant (Z-C/DIM), so the controller now has a both-crossings Z-C input after all, for
the pumps. What stands: the **heater** argument below — the SSRs align themselves, phase is not
needed, the period is — is unchanged, and no separate zero-cross detector is bought. What changes:
the supply **period** now comes from the Z-C capture (and the BL0942), not from DimmerLink's
`AC_PERIOD` register; over DimmerLink's UART only 50 or 60 was available anyway. Statements
below that name DimmerLink as the pump device or as the period source are superseded by this
note.

**It also records a change the graph has not yet been told about.** See § What this owes the
graph — nothing has been authored.

## The question

`DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM` requires a detection front end presenting **both
crossings of each cycle**, and explicitly rejects leaving alignment to the switching device
because that "costs the ability to say how many half-cycles were actually delivered."

Every switching device in the current selection handles its own alignment: the heater SSRs are
zero-cross type (EARU SSR-40DA, replacing the Fotek SSR-25DA on counterfeit-provenance grounds —
**this property must be confirmed on EARU's own datasheet, because the argument below rests on it**), the RBdimmer pump dimmers (DimmerLink at the time of writing, since superseded by the Standard variant — see the position update above) fired their own triacs from an onboard
Cortex-M0+, and the valve relays are per-delivery on/off with no phase relationship at all.
So: is the reference still needed?

## The cancellation argument — no, not for phase

Assert at time t0 at phase φ into a half-cycle. A zero-cross SSR starts conducting at the next
crossing, so it is late by `(T/2 − φ)`. De-assert after commanded duration D; it stops at the
next crossing after that. Conduction time is:

```
conduction = D − ((φ + D) mod T/2) + φ
```

If **D is an integer multiple of T/2**, then `(φ + N·T/2) mod T/2 = φ`, and this collapses to:

```
conduction = D − φ + φ = D
```

**Exactly D, for any φ.** The late start and the late stop are the same lateness and they
cancel. N half-cycles are delivered regardless of where the assert landed.

If D is *not* an integer multiple, the result is N or N+1 half-cycles depending on φ — bounded
at ±1, averaging to the commanded value as φ walks. But that case need not arise, because D can
be chosen as a whole number of *measured* half-periods.

**So the decision conflated two requirements.** What the scheme needs is the supply's **period**,
not its **phase**:

- **Period** is needed to choose D and to avoid the beat between the controller's crystal and the
  supply. Without it, a 200.00 ms window against a true 10.002 ms half-period walks slowly and
  occasionally delivers 19 or 21 half-cycles instead of 20 — a slow few-percent ripple at the beat
  frequency. Setting D from the measured period removes it.
- **Phase** is not needed, by the argument above.

Period is available from the Standard dimmer's Z-C capture and from the BL0942 if fitted. (It was
previously quoted from DimmerLink registers 0x20, 0x21–0x22; that variant is dropped.)

## What the four claimed uses of a zero-cross channel are worth

| Claim in the decision | Held against the selected parts |
|---|---|
| The energy account — knowing half-cycles delivered | Exact without it, per the cancellation argument, provided D is a whole number of half-periods |
| Supply-fault detection — an edge outside a plausible window, or missing | **The one real casualty.** BL0942 RMS voltage covers it more directly than counting edges |
| Period measured rather than inherited from a nameplate | Already served by the Z-C capture, or the BL0942 |
| Safety-relevant marking | `controller-io.md` marks it so "not because it switches anything, which it does not, but because it is the only mains-referenced *sensing* channel." That is about the channel's isolation barrier being a place mains could bridge. **Removing the channel removes the hazard** — an argument *for* dropping it |

## The drive scheme

**GPIO, not a bus.** The SSRs are driven directly from timer-backed GPIO. No serial link is in
the timing path. The BL0942's UART carries only integrated scalars, where latency is irrelevant.
That split — *timing on pins, measurements on buses* — is why the bus-latency objection that
rules out zero-cross-over-I²C does not touch the metering.

**Window.** 1 s is the tidy choice: 100 half-cycles at 50 Hz, so 1 % duty resolution in whole
half-cycles. Compute N from the measured period so the scheme stays frequency-agnostic (120 at
60 Hz).

**Spread the conducting cycles; do not fire contiguous blocks.** An accumulator that adds the
commanded duty each half-period, fires on overflow and carries the remainder — delta-sigma. Same
delivered duty, but the thermal ripple collapses and the modulation moves away from the ~8–10 Hz
human flicker-sensitivity peak instead of parking near it at ~1 Hz.

This is *exactly* what the decision already specifies — "a decision, taken once per supply
half-cycle, to energise the channel or leave it idle... the residual a level leaves between whole
half-cycles is carried forward rather than discarded." The residual-carrying scheme **is** the
spreading scheme. The only departure is that the half-period boundaries come from a free-running
accumulator clocked at the measured period, rather than from a locked edge: a constant unknown
offset from the true crossings, identical delivered counts.

**Spread at whole-cycle (20 ms) granularity** rather than single half-cycles, to keep DC balance
clean and stay inside what a zero-cross SSR switches comfortably.

**Ripple sanity check** (order of magnitude only — the block mass is not established). At ~0.5–0.8 kg
of aluminium and ~1000 W, heating is roughly 1.5–2 K/s with no flow, so contiguous 50 %-duty bursts
would give ~0.9–1.9 K peak-to-peak at a 1 s window and roughly double at 2 s. That matters against
the "few degrees" margin the `REQ-MEASUREMENT-001` margin note describes. Spreading removes almost
all of it, and in any case the worst ripple occurs at 50 % duty, which is heat-up, when it matters
least; steady-state idle sits at maybe 5–10 % duty.

**Flicker is worth a bench observation.** Burst-firing 1.1–1.2 kW at a few hertz produces supply
voltage flicker — the phenomenon EN61000-3-3 addresses. Not a blocker, but choose the window
deliberately and watch whether lights elsewhere in the house respond.

## BL0942 energy metering — a separate, stronger case

Adopting the BL0942 for **energy measurement** stands on its own merits, independent of the
zero-cross question.

**Why measure rather than infer.** Delivered power is not the commanded duty times a nominal
figure. `component-specification.md` already spans 230 V / 240 V / 253 V, and power goes as V², so
that range alone is **+21 %**; a full supply tolerance is wider still. Element resistance drift is a
much weaker term — nichrome-class alloys run around 85 ppm/°C, roughly 1 % over a 100 °C rise — but
the *measured* resistance is itself uncertain: `component-specification.md` records the steam
element's 47.0 Ω as a **lower bound**, because the bench could not isolate it.

**Where it pays.** Not the temperature loop, which already rejects supply variation through
feedback. The case is the **model-based state reconstruction**: an observer driven by heat input
takes a 21 %-plus systematic error straight into its estimate, and no downstream feedback repairs a
wrong input to an open-loop observer. *(Contingent on the estimator actually integrating heat input
— `SOL-UNMEASURED-STATE-RECONSTRUCTION` has not been read against this claim.)*

Secondary: quantitative per-channel **actuation confirmation**, replacing the OEM's binary
LTV814 mains-presence bit — distinguishing a welded contact, an open thermal cutout and a partially
failed element rather than just "current or no current."

**Zero-cross is NOT available over its UART.** Established from the datasheet: ZX is hardware
**pin 9**, its function selected by the `OT_FUNX` register (0x18). The only ZX-related register bits
are `I_ZX_LTH_F` [8] and `V_ZX_LTH_F` [9], which flag that the signal is *below* the detection
threshold — a fault indication, not a crossing event. Independently, the packet is 23 bytes and the
datasheet states this "takes about 48 ms when 4800 bps is used" — 2.4 mains cycles per packet, and
~6 ms even at 38400 baud. A 10 ms boundary cannot be represented in that stream.

**A figure the graph currently lacks.** The datasheet declares a **ZX output delay of 570 µs**
(5.7 % of a half-cycle at 50 Hz). `DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM` states that the phase
offset between a true crossing and a detected edge is a quantity "no declared figure bounds and
which this decision does not invent." This is such a figure. Whether it is typical or maximum is
not clear from the table's layout — confirm before relying on it.

**Placement: upstream of the SSR, not downstream.**

The tempting argument is to put the meter after the SSR so the triac's on-state drop is excluded
and only element energy is counted. `component-specification.md` puts that drop at 1.2–1.4 V, "of
the order of 6 W" per channel — against 230 V and ~1100 W, **0.57 %** of delivered energy, which is
about the BL0942's own energy accuracy. It is not worth what it costs.

Current does not care where the shunt sits: it is a **series circuit**, so the shunt reads element
current identically before the SSR, after it, or in the neutral return. Only the **voltage** channel
has a preference, and downstream placement breaks three things:

- **Period measurement** — now the one supply quantity the whole drive scheme depends on, since the
  cancellation argument holds only while D is a whole number of measured half-periods. A period
  cannot be measured from a waveform absent for most of the duty cycle (steady-state idle runs at
  perhaps 5–10 %).
- **Supply monitoring** — RMS voltage would report a duty-weighted figure rather than supply
  voltage, and that reading is what replaces edge-based fault detection in the revision below.
- **ZX**, if pin 9 is ever brought out — intermittent, so useless as a reference.

Subtler: the BL0942's calibration-free frequency tracking expects a continuous line, and will lose
lock on a waveform that collapses to zero for whole half-cycles.

**If the 0.57 % matters, correct it in firmware** — subtract `I × V_drop` using the datasheet figure
or a bench characterisation. The triac drop is roughly constant and weakly current-dependent. Zero
hardware cost.

Keep the proportions in view: this part exists to fix a **±21 %** error from supply variation.
Trading away period measurement to recover **0.57 %** would be repairing the third decimal place by
breaking the first.

Upstream placement means the module is live whenever the machine is plugged in — as it must be, to
monitor continuously. That makes the isolation test below more important, not less.

If the module is a four-terminal pass-through (L in / L out / N in / N out) its voltage tap is
internal and the sense points cannot be separated, which settles the question. If it exposes the
voltage sense separately, V upstream with the shunt anywhere is equivalent and not worth the extra
wiring.

**Blocked on isolation.** The BL0942 is inherently mains-referenced: the current channel is a
differential input across a 1–2 mΩ shunt in the mains path, and the voltage channel is a resistor
divider off the mains. A current transformer would isolate the current channel but not the chip.
So its UART and ZX pins sit at mains potential unless the specific module carries a barrier.

**Acceptance test, before connecting anything:** out of circuit, measure resistance between every
header pin and every mains terminal, all combinations. Isolated reads open (tens of megohms). Any
low reading means common reference and a live header. Look also for a routed slot in the PCB under
the optocoupler separating the ground pours. **Treat as non-isolated until this passes.**

Note the structural tension: bringing ZX across a barrier needs its own isolator channel, which a
module built around a single TX optocoupler will not have. So on a cheap module, "isolated" and
"ZX available" are close to mutually exclusive. Getting both means building a small board —
BL0942 + dual digital isolator + isolated DC-DC. Both heaters see the same mains phase, so two
meters would need only **one** isolated ZX channel.

## Consequence: the separate zero-cross detector is not needed

`part-numbers.csv` still carries a zero-cross detector row marked
`[REQUIRED if DimmerLink chosen]`. That row has now been retired in `part-numbers.csv`
(marked NOT NEEDED): the Standard pump dimmer's Z-C is the reference, and the heaters need none.
The graph revision below is still owed.

## Snubbing, by channel

Three switching channels, three different answers — worth stating together because the same
prebuilt RC+MOV module suits exactly one of them.

| Channel | Switch | Snubber? |
|---|---|---|
| Heaters | SSR (semiconductor, zero-cross) | **None.** Resistive load, no contacts to arc, and the dv/dt case applies to inductive loads only. Most SSRs carry an internal snubber regardless |
| Valve solenoids | Mechanical relay contacts | **Yes** — 100 nF + 220 R with a 10D471K, one per channel. Mains-AC coils are inductive and the contacts arc |
| Pumps | Triac, phase-cut | **Not this module, and probably none at all** |

**Valve relays.** 220 R is preferred over the 100 R originally specified: it limits the capacitor's
discharge into closing contacts to 1.5 A at 325 V peak rather than 3.3 A. The 470 V varistor is
correct *here* — across open contacts a MOV must stay non-conducting at normal line peak — even
though the mains-inlet MOV is deliberately the lower 275 V / 431 class. Same family, opposite
answer, because the jobs differ.

**A consequence to remember:** 100 nF is 31.8 kΩ at 50 Hz, so ~7 mA flows with the contacts open,
leaving roughly 36 V across a 5.9 kΩ solenoid coil permanently. Far too little to hold a valve in,
but **"de-energised" is no longer zero** — which matters to the fail-safe vent hypothesis in
`reference-machine.md` § Protection, to `REQ-FAULT-RESPONSE-001.C1`, and to whether a valve is
safely isolated for servicing merely because its relay is open.

**Pumps — why not the same part.** A 100 nF snubber passes ~7.2 mA, and a BT136's holding current
is only ~10–25 mA by grade. That is close enough to risk the triac latching permanently on. Triac
snubbers are correspondingly smaller — about 39 R + 10 nF or 100 R + 47 nF, 0.7–3.4 mA — and fit
MT1–MT2 rather than across a switch. A second reason: any RC across a phase-cut triac leaks current
to the load during the off part of the cycle, costing the bottom of the control range.

**And probably none is needed.** Commutation stress scales with load current, and the `(dI/dt)c`
and `(dV/dt)c` figures that cause commutation failure on inductive loads are specified at the
device's rated 4 A. The pump draws 0.1–0.22 A — about 5 % — so the margin is large. The open item
is only to *confirm* what the RBdimmer board already fits (a "102"/1 nF marking sits near the
triac but cannot be identified from a photo), not to add parts pre-emptively. If insurance is ever
wanted, the right fix is a **snubberless** triac (`BTA`-xxx-`BW`), which solves commutation by
construction without leaking current around the switch.

## What this owes the graph

**Nothing has been authored. This file is not the record.**

`DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM` does not merely omit this — it *rules* on it, requiring a
both-crossings front end and rejecting device-level alignment by name. Building this way makes the
graph describe a machine that is not being built.

The revision is narrower than it first appeared. Most of the decision survives intact:

- **Keep** the per-half-cycle residual-carrying layer below the seam, exactly as written — it is
  the spreading scheme, and it is right.
- **Keep** the crystal-derived control period.
- **Replace** "the detection front end presents both crossings of each cycle" with a requirement
  that the supply's **period** is measured.
- **Justify** with the cancellation argument, stating that it holds only while D is a whole number
  of measured half-periods.
- **State the contingency**: this rests on the SSRs remaining zero-cross type. A random-phase
  replacement reopens the whole question. This is not hypothetical — the heater SSR has already
  been changed once (Fotek SSR-25DA to EARU SSR-40DA) for reasons unrelated to switching
  behaviour, and the zero-cross property was carried across on the generic `SSR-xxDA` class spec
  rather than verified against EARU's own datasheet. **Verify before the revision is authored.**
- **Record what is given up**: edge-level supply-fault detection, and its replacement by RMS
  voltage measurement — which makes the BL0942 (or an equivalent) load-bearing rather than
  optional, and that is a new dependency the decision must state.

`SOL-CONTROLLER-AND-MAINS-PARTS-DOWN-SELECT.C2` names "the supply-timing front end" as a thing
specified by property, and `controller-io.md` carries a zero-cross sensing row. Both move with the
decision — this is the *amending without propagating* pattern `CLAUDE.md` names, and the propagation
has not been done.

Two further items surfaced and are also unauthored:

- **DC injection.** Odd numbers of half-cycles inject a DC component into the supply; industrial
  integral-cycle controllers use whole cycles to avoid it. The decision's rationale weighs the beat,
  the account, the flywheel and the supply-fault case, but does not mention DC at all. That looks
  like a gap in it rather than something it decided against.
- **Voltage flicker** from burst-firing kilowatt loads is not addressed by any criterion.
