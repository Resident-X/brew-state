> **Status: open findings from a blind review. Working material, not authoritative.**
>
> Produced 2026-08-16 by a six-agent blind review of the requirement graph at commit `8859d0d`
> (287 nodes), per CLAUDE.md Rule 7. Each agent read the graph cold with one lens; the leak and
> comprehension agents were denied `thoughts/` and the parts sketch so they could not be primed.
>
> Tier 1 (safety and correctness) was fixed in `8859d0d`. **Everything below is still open.**
> Delete a finding when it is closed; delete this file when all of them are.
>
> Every claim here was spot-checked against the graph before being written down. No false
> positives were found in the sample checked, but these are agent findings and the reasoning
> should be re-verified before acting on any of them.

# Open findings — Tiers 2 and 3

## Tier 2 — the open-source promise does not hold yet

These break the published-repo promise rather than the machine. `OBL-OPEN-SOURCE-MAINTAINABILITY-001`
and `PER-ADOPTER-001` both assert things the graph does not currently deliver.

**T2.1 — The reference machine is never described.** No node states the architecture. It is
reverse-engineerable only from `DEF-THERMOBLOCK`'s closing line and the preambles of
`REQ-POWER-BUDGET-001`, `REQ-BREW-TEMP-001` and `REQ-SAFETY-CHAIN-001.C1`. `PER-ADOPTER-001.C2/.C3`
promise different things to same-architecture and different-architecture adopters, and a reader
cannot tell which they are in. An HX-machine owner would read *"two otherwise independent control
loops"* as a bug in their own build. **Closes with:** a node stating the reference architecture, or
a marked context document the graph points at.

**T2.2 — The five things the graph demands be marked as local are themselves unstated.**
`OBL-OPEN-SOURCE-MAINTAINABILITY-001.C3` names them: supply voltage, mains frequency, wiring rules,
protection trip points, and this machine's thermal characteristics. None appears anywhere in the
graph, marked or unmarked. `PER-ADOPTER-001.C1/.C4` repeat the demand. **Closes with:** a declared
machine-configuration requirement deriving from `PER-ADOPTER-001.C4`.

**T2.3 — The external-authority obligation never names its authority.**
`OBL-ELECTRICAL-THERMAL-SAFETY-001` is the graph's only `authority: external` node and says only
*"domestic wiring rules"*. BS 7671, AS/NZS 3000 and the NEC differ materially on protective earthing,
isolation and circuit rating. An external obligation whose authority cannot be cited is not checkable
by the adopter it exists for.

**T2.4 — Energy figures are inconsistent and unmarked.** *"roughly two and a quarter kilowatts"*
(`OBL-ELECTRICAL-THERMAL-SAFETY-001`, `DEC-NO-REMOTE-ACTUATION`) versus *"two kilowatts"*
(`OBL-VERIFICATION-DISCIPLINE-001`, `REQ-EXTERNAL-MONITORING-001.C1`), neither marked as
machine-specific. `OBL-ELECTRICAL-THERMAL-SAFETY-001.C3`'s *"approach the limit of an ordinary
domestic circuit"* is true at 230 V and false at 120 V, where the figure is already over.

**T2.5 — Mains frequency appears in no requirement**, though *"actuation on this machine is tied to
the mains waveform"* is stated as fact in four places and required by none. 50 vs 60 Hz changes the
control period and the modulation scheme. Related: nothing requires mains-synchronous actuation at
all — it is assumed throughout.

## Tier 3a — implementation leaks

**T3.1 — `REQ-SAFETY-CHAIN-001.C4`** — *"A device **downstream of** all resettable protection…"*.
Series topology stated as the requirement, forecloses a latching interlock or a non-restoring element
acting on the enabling path. The parent `OBL-ELECTRICAL-THERMAL-SAFETY-001.C4` states the same
property cleanly, so this is a re-mechanisation on the way down. **Proposed:** *"Once the
non-restoring protection has operated, no other protective element resetting can return power to the
load, and restoration requires a person."*

**T3.2 — `OBL-REALTIME-DISCIPLINE-001` body** — *"…shares a processor with flow counting, **watchdog
servicing** and **two sensor channels on one bus**."* Three leaks: a named mechanism the graph
avoids elsewhere (`REQ-SAFETY-CHAIN-001.C2/.C3` say *"proof of life"*), a count that
`REQ-EXTENSIBILITY-001.C3` requires to be extensible, and interface topology. **Proposed:**
*"…flow counting, liveness signalling and the sensor channels, several of which contend for the same
interface."*

**T3.3 — `OBL-REALTIME-DISCIPLINE-001.C3`** — *"**Interrupt priority and handler ordering** are
assigned deliberately."* Presupposes an interrupt-driven architecture; forecloses a polled superloop,
cooperative scheduler or time-triggered cyclic executive. Sibling `.C5` already shows the abstract
form (*"concurrent contexts"*). **Proposed:** *"Where correctness depends on the relative ordering of
concurrent activities, that ordering is chosen and stated rather than inherited from a default."*

**T3.4 — `REQ-MODEL-STRUCTURE-SEAM-001.C3`** — build-time structure selection is a deliberate
instruction, **not** a leak. The defect is that its trade-off reasoning (dispatch cost vs storage vs
safety) sits in a criterion body with **no decision node recording it**. **Closes with:** a decision,
not a weakened criterion.

Lower priority, same family: `OBL-VERIFICATION-DISCIPLINE-001.C6` body names register-level
interaction, interrupt priority and bus timing; `REQ-BENCH-INTERFACE-001.C2` prescribes *"timestamped
by the machine's own clock"* where its parent journey states the property better; `PER-BUILDER-001`
body names *"a serial link"*.

## Tier 3b — chain structure

**T3.5 — `REQ-STORED-DATA-INTEGRITY-001` derives-from `OBL-CONTROLLER-FAULT-RESPONSE-001.C1`.**
That obligation is titled *"actuation faults"* and C1 is specifically about actuator confirmation.
Stored-data corruption does not belong under it. Its other two parents fit well. **Closes with:**
drop the link.

**T3.6 — `REQ-MACHINE-INTERFACE-001` derives-from `REQ-EXTENSIBILITY-001.C2`.** C2 is explicitly
about adding **outputs**; this requirement is about interface **consumers**, and already carries its
own `.C5` for that. **Closes with:** drop the link.

Also: `REQ-EXTENSIBILITY-001` → `OBL-VERIFICATION-DISCIPLINE-001.C3` is a thin link with no rationale
explaining it. `REQ-PREENERGISATION-VERIFICATION-001.C3` is a near-verbatim restatement of
`OBL-VERIFICATION-DISCIPLINE-001.C5` with no link between them — add the derives-from or drop one.

## Tier 3c — testability

**T3.7 — `REQ-ELECTRICAL-INSTALL-001.C4`** is `verification: analysis` while its own body says *"the
judgement is made against the assembled condition in service rather than against the figure on the
datasheet"* — which analysis cannot establish. Should be `test`.

**T3.8 — `OBL-ELECTRICAL-THERMAL-SAFETY-001.C6`** is `inspection`, but its text extends the claim to
*"under fault"* and through water, steam and thermal cycling. Eyeballing clearances once does not
establish that. Should be `test`, or split the static and stressed claims.

**T3.9 — `REQ-MEASUREMENT-001.C1`** is `analysis` for an empirical absolute-accuracy claim. Arguably
`test`, since the project explicitly declines to trust datasheet figures elsewhere.

**T3.10 — `rate` and `periodic` are used zero times** across all criteria (at review: 172 `binary`,
40 `threshold`). Every rate-shaped claim is folded into `threshold`. Either a deliberate decision or
an accident of habit — worth settling either way.

## Tier 3d — internal consistency

**T3.11 — `REQ-OPERATOR-FEEDBACK-001.C4` contradicts its own parent.** It says *"anything detectable
before delivery starts is refused rather than reported"*; parent `JRN-SERVE-GROUP-001.C4` says an
unsustainable pace is **reported**, not refused. A pace limit is detectable beforehand. Refusing
mid-run is what `PER-OPERATOR-001.C5` exists to prevent. The axis should be **quality shortfall
(refuse) vs time shortfall (slow and report)**, not preventable vs unpreventable.

**T3.12 — `PER-ADOPTER-001.C1/.C4/.C5` restate `OBL-OPEN-SOURCE-MAINTAINABILITY-001` at lower
priority.** Near-verbatim in places. The same assertion is simultaneously `must` and `should`, so a
reader triaging by priority gets two answers. The obligation should own all three; the persona's
defensible content is `.C2/.C3`, the two-promises criteria.

**T3.13 — Priority inversion.** `REQ-MODEL-STRUCTURE-SEAM-001` (`must`) derives from
`PER-ADOPTER-001.C2/.C3` (`should`), and its `.C5` is purely adopter-facing yet `must`. The persona's
own rationale ranks the adopter below the builder.

**T3.14 — `REQ-MACHINE-INTERFACE-001.C4`** — *"Nothing in a delivery waits on anything outside the
machine"* — plainly forecloses `REQ-GRAVIMETRIC-ENDPOINT-001.C1`, whose weight is measured at the
cup. Intent is clearly "no consumer of the interface surface"; say that.

**T3.15 — `DEF-COMMISSIONING`** says commissioning establishes the model's **structure** as well as
its parameters, but `REQ-MODEL-STRUCTURE-SEAM-001.C3` makes structure a build-time property and
`REQ-MODEL-COMMIT-001.C3` persists parameters only. No node gives commissioning a means to change
structure.

**T3.16 — `DEF-DRAW`** defines a draw as operator-terminated, which excludes an espresso — but
`JRN-SERVE-LONG-BLACK-001.C3` calls the espresso and the hot water *"its own draws"*. Separately,
*"draw"* is used for electrical current in `DEF-SUPPLY-BUDGET` and `REQ-POWER-BUDGET-001.C1`, the
latter bare and unqualified.

## Tier 3e — coverage gaps

**T3.17 — No espresso endpoint control anywhere.** `DEF-DELIVERY` says a delivery *"has a command, an
outcome, and an endpoint at which it stops"*; `JRN-PULL-SHOT-001` step 5 says the machine ends the
shot at the recipe's endpoint; no criterion asserts it and no requirement implements it. Worse,
`REQ-GRAVIMETRIC-ENDPOINT-001.C2` (a `could`) falls back to *"the endpoint the machine would have
used without the capability"* — **which is defined nowhere**. Also: rate control exists for hot water
and steam but not for espresso, and flow appears only as a disturbance input, never as a commanded
output.

**T3.18 — `JRN-OPERATE-INTERFACE-001.C3` and `.C4` are orphaned.** `.C3` (feedback reaching an
operator not looking at the interface) is named in the journey's own rationale as *"the one that
shapes the design"*. It also implies a non-visual annunciator and an acknowledge input, neither of
which any requirement asserts. *"Acknowledge"* appears nowhere in the requirement layer.

**T3.19 — Records require "when" with no time base declared.** `REQ-DELIVERY-RECORD-001.C2/.C3`,
`JRN-CORRECT-DRIFT-001.C5` and `REQ-EXTERNAL-MONITORING-001.C2` all need ordering or elapsed time;
`REQ-STARTUP-STATE-001`'s own rationale concedes *"a machine without a running clock cannot know
that"*. Nothing declares whether the answer is ordering-only or wall-clock, and nothing bounds
retention volume.

**T3.20 — No EMC or interference criterion** on `REQ-ELECTRICAL-INSTALL-001`, despite kW-level
switching sharing an enclosure with a precision temperature front end and an analogue pressure
channel. Currently caught only after the fact by `REQ-MEASUREMENT-001.C3`.

**T3.21 — Empty tank / dry run is caught only reactively** by `REQ-ACTUATION-CONFIRMATION-001.C5`.
Nothing refuses a delivery before it starts on a known-empty reservoir, and the water-level input the
donor machine already provides is used by no requirement.

**T3.22 — No idle timeout on locally reached readiness.** `REQ-SCHEDULED-READINESS-001.C3` (a
`could`) requires an unused *scheduled* readiness period to end unattended, while ordinary local
readiness — the state the machine occupies most of the time — has no timeout anywhere. The asymmetry
looks accidental.

**T3.23 — The "don't re-plumb for preheat" choice has no decision node**, though the graph's shape
depends on it: it is why `REQ-POWER-BUDGET-001` and `REQ-SEQUENCE-CONSISTENCY-001` must handle
concurrent brew and steam at all. Consequences are covered; the choice is not recorded.

**T3.24 — Firmware image integrity is out of scope of `REQ-STORED-DATA-INTEGRITY-001`**, which covers
parameters and configuration. `REQ-MAINTENANCE-ACCESS-001.C2` gates the firmware path without
requiring the result to be verified or recoverable.

**T3.25 — Vocabulary.** *"resting state"* is used five times across three chains and never defined —
and if it equals `DEF-SAFE-STATE` then scheduled readiness violates it, while if it does not, the
difference is nowhere stated. *"the coffee side"* / *"the steam side"* are used as proper nouns across
seven nodes, undefined. *"channel"* carries two senses: a sensing signal path and a spending unit in
`REQ-COST-DISCIPLINE-001`. (`DEF-READINESS` was added in Tier 1 and is no longer a gap.)

**T3.26 — No entry point.** `specs/_document.yaml` says only *"Coffee requirement graph"*. Nothing
tells a newcomer where to start reading, which is the thing `PER-ADOPTER-001.C5` asks for.

## The three patterns behind these

Worth carrying forward, because they will recur:

1. **Amending without propagating.** Both remote-readiness contradictions came from revising a
   decision and not chasing its consequences. T3.11 and T3.14 are the same shape.
2. **Wrong axis.** Electrical contention drawn where thermal contention was the issue;
   preventable-vs-unpreventable drawn where quality-vs-time was the issue.
3. **Assumed, not required.** Flow sensing, mains-synchronous actuation, the reference architecture
   and the mains environment were all load-bearing and asserted by no node. T2.1, T2.5 and T3.17
   are all instances.
