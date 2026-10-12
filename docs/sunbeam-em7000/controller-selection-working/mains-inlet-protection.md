# Mains inlet protection — working notes

Working draft from the same in-flight selection as the rest of this directory. **Not baselined,
not traced to any criterion, and not evidence for anything.** It records why the inlet parts were
chosen and — more usefully — which variants of them are wrong, because most of the cost of this
decision was spent discovering that the obvious part numbers are the wrong ones.

Read it as a snapshot of a decision in progress, not as a record of one taken.

## The problem this addresses

The retrofit's protective chain interrupts on **temperature** and nothing else. The machine
carries three thermostats (110 °C coffee, 200 °C steam, 110 °C pump) and a thermal fuse of
unestablished rating — see `reference-machine.md` § Protection. A short, an insulation
breakdown, or a partial fault is not a thermal event and none of it responds.
`OBL-ELECTRICAL-THERMAL-SAFETY-001.C8` already states this in exactly those terms.

Upstream is an ordinary domestic circuit breaker. In an AU installation the plug is unfused, so
"upstream" means a 16 or 20 A MCB. That leaves a band uncovered: a chafed conductor, an SSR
failing part-shorted, carbon tracking across a damp terminal, or a solenoid coil shorting
turn-to-turn draws something like 8–15 A indefinitely. That is below the breaker's threshold and
well above what melts insulation.

The sharper form of the same point, and what `REQ-ELECTRICAL-INSTALL-001.C7` is asking for: **a
20 A breaker permits 20 A through every conductor the retrofit adds.** A local 10 A fuse is what
makes it admissible to wire internal branches for the machine's actual draw rather than for the
breaker's rating.

Separately, the phase-cut pump dimmer is a broadband noise source sharing an enclosure with NTC
dividers and (conditionally) MAX31865 front ends. `REQ-ELECTRICAL-INSTALL-001.C8` requires
precision sensing to hold its stated accuracy *while the switched loads operate*. An inlet filter
is how that is made achievable rather than discovered to have failed at test time.

## Why this is not solved by buying a better PSU

Every part on the mains side needs this, not just the 5 V supply. A PSU module's own onboard
fuse, filter and (if fitted) MOV protect **that module's primary only**. The SSRs, the dimmer's
BTA16, and the mains-coil solenoids are fed from elsewhere and are covered by none of it — and a
600 V triac is considerably more surge-vulnerable than a flyback front end.

So the protection belongs **once, at the machine inlet**, upstream of everything.

## The chain

```
mains ──► FN9222-10-06 (IEC C14 inlet + EMI filter) ──► L ──► [T10A slow-blow] ──┬──► SSRs, dimmer,
                                                       N ──────────────────────┬─┼──► valves, 5V PSU
                                                                               │ │
                                                                         ┌─────┴─┴─────┐
                                                                         │  MOV L–N    │  RN3404
                                                                         │ leads <25mm │
                                                                         └─────────────┘

earth: C14 inlet earth pin ──► chassis bonding stud, unbroken (Class I)
```

| Position | Part | Why |
|---|---|---|
| Inlet + filter | Schaffner **FN9222-10-06** | C14 inlet and EMI filter in the panel cut-out. Cx 0.1 µF, Cy 2.2 nF, L 0.225 mH @ 10 A, leakage 373 µA @ 250 V/50 Hz. Rated 10 A @ 50 °C |
| Fuse | Panel-mount M205 holder, **T10A slow-blow**, on active | Covers the 8–15 A band the breaker does not. Slow-blow is mandatory: the 5 V module's cold-start inrush is 40 A at 230 Vac, on top of heater switching |
| Surge | Jaycar **RN3404**, 275 Vac, 6500 A, 190 J, L–N | Nothing else in the machine responds to a transient |

**Order is load-bearing.** The MOV sits **downstream of the fuse**. Its designed failure mode is a
short; upstream of the fuse a failed MOV is an unfused arc across the mains. Downstream, it blows
the fuse and the machine goes dark.

**Lead length is load-bearing.** MOV clamping at real surge rates is dominated by lead inductance,
not by the disc — roughly 1 nH/mm, and at 1 kA/µs a sloppy 50 mm loop adds hundreds of volts on
top of the 710 V clamp. Mount it hard against the fuse holder terminals, total loop under ~25 mm.

**The filter itself ends up fused only by the upstream breaker.** That is normal for this part
class: its components are X2/Y2 safety capacitors designed to fail safely plus a wire-wound choke,
and Schaffner build the entire unfused-inlet category on that basis.

**L–N only.** L–E and N–E modes leak to earth continuously and are an RCD nuisance-trip generator.
Multi-mode protection is a switchboard SPD's job, not an appliance's.

## Variant traps

This is the part worth keeping. Every one of these is a part number that looks right and is not.

| Trap | What happens | Correct choice |
|---|---|---|
| **`B` suffix = medical** | Y-capacitors deleted entirely (leakage 373 µA → 2 µA) to meet IEC/EN 60601-1. The Y-caps *are* the common-mode filtering — the exact mechanism needed against the dimmer. Pays a premium to remove the feature | No suffix letter |
| **`A` suffix = low leakage** | Cy 2.2 nF → 0.47 nF. Exists for installations stacking many filters on one RCD. 373 µA against a 30 mA RCD is ~1 % of threshold | No suffix letter |
| **`Z` suffix = built-in MOV** | Tidy, and factory lead lengths are ideal. But a MOV is a **consumable** that degrades silently — an internal one cannot be inspected or renewed without scrapping the module. Its energy rating is not separately specified. Also forces the `U` mounting style and drops P→N hipot from 1000 Vac to 250 Vac | Plain filter + discrete RN3404 |
| **FN9260 vs FN9222** | FN9260 is the *same filter* with a twin fuseholder, at roughly 2.5× the price. FN261 is the same again with a single fuseholder | FN9222 + separate holder — cheaper, gives single-pole active fusing, and a chassis holder is easier to service than an inlet drawer |
| **Generic `CW2B-10A-T` etc.** | AliExpress equivalents at ~AUD 8. Hollow housings with no choke or caps fitted are a known failure in this category, and the naming drifts between sellers (`CW1B`/`CW1D`/`CW2B`/`CW2C` used interchangeably) | Defensible *only* with an arrival check: internal photos, measure L–N capacitance, ring out the choke and the earth tab |
| **MOV `471` vs `431`** | `14D471K`/`20D471K` are 300 Vac rated and clamp at 775 V. The `431` parts are 275 Vac and clamp at 710 V — more sensitive to the surges that matter at 230 V | 275 Vac rated |
| **Non-mains fuse holders** | Many cheap panel holders are 250 V **DC** automotive parts with exposed terminals | 250 Vac, 10 A, shrouded or insulated terminals |

## Rejected: the open-frame AliExpress 5 V module

A generic open-frame 5 V/2 A board was considered and rejected. It is better than the category
floor — input fuse, apparent MOV, common-mode choke, optocoupler feedback, real bobbin transformer
with an isolation slot — but:

- **Open frame at 230 V** inside a machine that holds water under pressure and vibrates.
- **The 2 A rating is a peak figure**; honest continuous output is nearer 1 A.
- **No traceable approval**, no datasheet, no creepage spec.
- Silkscreen suggests a shared multi-voltage PCB (a `DC-12` marking near the output pads), so a
  mis-shipped variant is a live risk. Meter the output before connecting anything.

It is also **not smaller**: ~66 × 40 × 25 mm ≈ 66 cm³, against the IRM-05-5's 45.7 × 25.4 × 21.5 mm
≈ 25 cm³. Encapsulated modules win on volume; open-frame boards only look compact.

## 5 V supply — open, changed from the BOM

`control-system-bom.csv` still carries **HLK-10M05** (10 W / 2 A). The working recommendation is
was **Mean Well IRM-05-5** (5 W / 1 A) and is now the **IRM-10-5** (10 W / 2 A, same case and pins — see the derating note under Open items), on measured load rather than headroom instinct (the ~450 mA figure below omits the panel, gauge board and buzzer; the revised worst case is about 0.53 A):

- Actual 5 V draw is ~450 mA (117 controller + 286 relay coils + sensors and SSR
  drive). 1 A is ~2× that.
- Volume drops from ~29 cm³ to ~25 cm³, and 5 W parts are physically smaller across the board.
- Approvals are real and documented: IEC/UL/EN 62368-1, EN61558-1/-2-16, TÜV, BSMI. Withstand
  4.2 kVac I/P–O/P. Internal T2A/L 300 V fuse. EN55032 Class B **without additional components**.
- Surge immunity EN61000-4-5 **Level 3, 1 kV L–N only** — it is a Class II design with no FG pin,
  so there is no line-to-earth path at all. Another reason the inlet MOV is not optional.

**Not yet confirmed against the derating curve.** At 71 % efficiency it dissipates ~2 W in a potted
brick, and internal ambient near the boiler will be 45–60 °C. The 1 A rating falls with ambient.
450 mA very probably still fits; the curve has not been read.

Note also that the IRM runs at **65 kHz**, the same ballpark as the open-frame board. Its size
advantage is potting and dense assembly, not switching frequency.

## Panel switch — not fitted, deliberately

A switched inlet variant (`CW2B`, Schurter `DD` series) was considered and rejected:

- **AU GPOs are switched.** A panel rocker duplicates a switch that already exists on every outlet.
- **Neither is isolation for servicing.** Working inside means *unplug* — a visible break nobody
  can flip back. Both wall and panel switches are single-pole and leave neutral connected. A panel
  rocker actively invites the wrong habit.
- **It is another 10 A series contact** — a wear item in the main path, and it costs panel depth.

If reach turns out to be the problem during firmware work, an **inline switched IEC lead** is the
answer: a few dollars, switch where the hand is, no panel depth consumed.

**Open:** no hard mains switch was found in the machine documents. What is recorded is eight
front-panel pushbuttons and ~10 LED elements, all enumerated as *logic* channels the controller
reads directly (`SOL-CHANNEL-ENUMERATION-CORRECTED.C4`) — momentary inputs, not a mains break. If
that is the whole picture, then once the control board is replaced the machine's only mains break
is the plug, and "off" becomes whatever the firmware decides. **Establish by inspection.**

## Sourcing split

The reasoning is the same one already applied to the future solenoid valves in
`control-system-bom.csv`: the failure mode is a spec sheet that does not describe the part in the
box, and it bites hardest on components whose only job is to be true under fault conditions.

| Class | Where | Why |
|---|---|---|
| Protective devices whose datasheet *is* the product — inlet filter, 5 V PSU | element14 / Mouser / RS AU / Fastron | Derating curves and surge levels are the thing being bought |
| Compliant commodity — MOV, fuses, holders, wire, enclosures | **Jaycar** | Under the EESS a Responsible Supplier is legally accountable for compliance and must hold test records for 10 years. An AliExpress RCM logo is a JPEG |
| Modules — controller, relays, breakouts | Core Electronics | Already the BOM's channel |
| Inspectable low-consequence hardware — standoffs, perfboard, heatsinks | AliExpress | Consequences of a bad part are visible and cheap |

## Open items

- **FN9222 dimension letters not mapped.** The datasheet's dimension table gives A 48, B 22.4,
  C 40 ±0.2, D 38.25, E 27.8, G 20.1, N 21.5, P 28.5 for the 10–15 A types, but the drawing that
  assigns those letters to length/width/depth and to the panel cut-out was not parsed. **Confirm
  the mapping and the cut-out against the drawing before cutting the panel.**
- ~~**IRM-05-5 derating curve** at 45–60 °C internal ambient — not read.~~ **Read** from the Mean Well IRM-05 and IRM-10 spec sheets (values read off the chart, approximate): 100 % load up to 50 °C ambient, about 75 % at 60 °C, about 50 % at 70 °C. Both parts share the same curve shape, footprint and pin positions; the IRM-05-5 is 1 A (0.75 A at 60 °C, 0.5 A at 70 °C) and the IRM-10-5 is 2 A (1.5 A at 60 °C, 1.0 A at 70 °C). The ambient in the enclosure is itself unmeasured.
- **Thermal fuse rating** in the machine — fitted, rating not established (`reference-machine.md`).
- **Whether the machine has a hard mains switch at all** — not established, see above.
- **MOV is a consumable with no in-circuit test.** Worth a build note to renew it after any
  nearby lightning event or supply disturbance, since a degraded disc gives no indication.
- **Thermal placement conflict.** The BOM's user note proposes mounting the SSRs direct to the
  metal side wall to avoid heatsinks. If that happens, the 5 V module belongs on the *opposite*
  side of the enclosure — its rating derates against exactly that ambient.

## Graph gap

**No criterion anywhere requires surge or transient suppression.** A search across the graph for
surge, varistor, transient and EMC coverage returns nothing that asserts it. The protective chain
per `OBL-ELECTRICAL-THERMAL-SAFETY-001.C8` is explicitly about *fault current*, interrupted
upstream — a transient is neither.

So the MOV in this chain would be fitted because it is obviously sensible, with nothing in the
graph asserting it and nothing to stop a later revision quietly dropping it. That is the
*assumed, not required* pattern named in `CLAUDE.md`, and it is unresolved. Whether it belongs as
a new criterion on `REQ-ELECTRICAL-INSTALL-001` or on `OBL-ELECTRICAL-THERMAL-SAFETY-001` has not
been decided, and nothing has been authored.

The fuse and the filter are in better shape — `REQ-ELECTRICAL-INSTALL-001.C7` already requires the
upstream protection to be declared and the wiring rated for it, and `.C8` already requires sensing
accuracy to hold under load. Both are `verdict: unknown` and neither has been discharged.
