# Mains entry protection (working note; the file keeps its earlier name)

> **[Source the custom board draws on, written for the bought-module design. Module choices in it are history; this folder loses where it disagrees with the graph or the record documents. Role and precedence: README.md.]**

**Status: the machine keeps its existing fixed mains lead.** The owner's ruling (`DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE`) is that no appliance inlet and no bought inlet filter is fitted: the lead's conductors land on the main board's mains tabs 2 and 3, where the 10 A slow-blow fuse and a varistor sit, the varistor hard against the fuse and downstream of it, as the original board carried its own protection at its entry. Whether the entry also needs emission suppression, in place of the filter's, is the main board design's decision. The note below was written for an inlet and a filter; those passages are removed or rewritten here, and what remains is the reasoning about the fuse, the varistor and the chain's ratings.

Refreshed 2026-10-12 from `decisions.md` (which supersedes older text), the current design data in this folder, and the earlier working note of the same name. **Not baselined, not traced to any criterion, and not evidence for anything.** It records why the entry fuse and varistor and the 5 V supply were chosen and, more usefully, which variants of them are wrong, because most of the cost of this decision was spent discovering that the obvious part numbers are the wrong ones.

Chosen parts (`decisions.md`): the retained fixed mains lead, then a T10A slow-blow on the active and a varistor across line and neutral downstream of it, on the main board at tabs 2 and 3 (D8, Chosen; the trunk rated above the fuse by `DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE`). The supply is one Mean Well IRM-10-5 on a hand-cut single-sided copper-clad carrier, a recommended (not required) T2A slow-blow fuse, and an output of 100 nF and 47-100 uF (D7, Chosen).

## The problem this addresses

The retrofit's protective chain interrupts on **temperature** and nothing else. The machine carries three thermostats (110 °C coffee, 200 °C steam, 110 °C pump) and, per the parts list, a thermal fuse said to be a 240 °C steam-block part. That is a published, unverified derived view: `reference-machine.md` § Protection records none seen at the board end and none found by the owner (owner statement, 2026-10-20), so no rating, location or count is recorded. A short, an insulation breakdown, or a partial fault is not a thermal event and none of it responds. `OBL-ELECTRICAL-THERMAL-SAFETY-001.C8` already states this in exactly those terms.

Upstream is an ordinary domestic circuit breaker. In an AU installation the plug is unfused, so "upstream" means a 16 or 20 A MCB; the build declares up to 20 A (`reference-machine.md` § Supply, project assumption). That leaves a band uncovered: a chafed conductor, an SSR failing part-shorted, carbon tracking across a damp terminal, or a solenoid coil shorting turn-to-turn draws something like 8-15 A indefinitely. That is below the breaker's threshold and well above what melts insulation. The T10A entry fuse below narrows that band rather than closing it: a slow-blow fuse carries about one and a half times its rating, about 15 A, for half an hour or more before it opens (`DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE`; the T10A's own curve was not read here), so a fault between 10 A and about 15 A is cleared only slowly and one below 10 A not at all. *(See Open items: the machine's own worst-case draw, at 253 V, the declared span's top, is itself about 10.5 A, over 10 A.)*

The sharper form of the same point, and what `REQ-ELECTRICAL-INSTALL-001.C7` is asking for: **a 20 A breaker permits 20 A through every conductor the retrofit adds.** A local 10 A fuse is what makes it admissible to wire internal branches for that fuse, including its slow-blow overload band, rather than for the breaker's rating. A branch with no fuse of its own is wired for the 10 A fuse, not for its load's draw: the two heater branches are, so their conductors, board copper carrying heater current included, are rated for the entry fuse rather than for the element (`DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE`). Only a branch with its own smaller fuse, the pumps' and the valves', may be wired for that fuse instead.

Separately, the phase-cut pump dimmer is a broadband noise source sharing an enclosure with the NTC and PT1000 dividers feeding the controller's 16-bit ADCs. `REQ-ELECTRICAL-INSTALL-001.C8` requires precision sensing to hold its stated accuracy *while the switched loads operate*. No inlet filter is fitted, the machine's lead being retained; whether the entry needs emission suppression to make that achievable rather than discovered to have failed at test time is the main board design's decision. (No MAX31865 front end is fitted: D10.)

## Why this is not solved by buying a better PSU

Every part on the mains side needs this, not just the 5 V supply. A PSU module's own onboard fuse, filter and (if fitted) MOV protect **that module's primary only**. The SSRs, the pump dimmers' BT136S-600E triacs, and the mains-coil solenoids are fed from elsewhere and are covered by none of it, and a 600 V triac is considerably more surge-vulnerable than a flyback front end.

So the protection belongs **once, at the machine's mains entry on the main board**, upstream of everything.

## The chain

```
mains ──► retained fixed lead ──► tab 2 (L) ──► [T10A slow-blow] ──┬──► SSRs, dimmers,
                                  tab 3 (N) ───────────────────┬─┼──► valves, 5V PSU
                                                               │ │
                                                         ┌─────┴─┴─────┐
                                                         │ varistor    │  L–N, hard against
                                                         │ leads <25mm │  the fuse, downstream
                                                         └─────────────┘

earth: the lead's earth core ──► chassis bonding stud, unbroken (Class I)
```

| Position | Part | Why |
|---|---|---|
| Lead | The machine's existing fixed mains lead, retained | A fixed cord with a standard Australian 10 A plug, marked 7.5-10 A 250 V, landing on the main board's tabs 2 and 3. Protected upstream by the building's breaker, declared up to 20 A. No appliance inlet and no filter is fitted; the filter's emission suppression is not replaced unless the main board's design decides it needs it |
| Fuse | 5 × 20 mm holder rated 10 A on the main board (the board's 5 × 20 mm holder is listed 6.3 A, so this one is a different part), **T10A slow-blow**, on active | Interrupts, below the breaker's threshold, a sustained fault the breaker does not, but slowly near its rating: it carries about 15 A for half an hour or more before it opens (`DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE`), so everything downstream that relies on it alone is rated for that band. Slow-blow is mandatory: the 5 V module's cold-start inrush is 40 A at 230 Vac, on top of heater switching |
| Surge | Varistor across line and neutral, downstream of the fuse. The original board carried a 14 mm, 470 V one (`reference-machine.md`, *Mains-entry surge and filter parts on the original board*); the part for this board is chosen after the owner checks that disc. The earlier design's candidate was the Jaycar **RN3404**, 275 Vac, 6500 A, 190 J, 24 mm disc | Nothing else in the machine responds to a transient |

Downstream branch protection that the T10A does not provide: a 1-2 A slow-blow fuse in each pump dimmer's AC-L in feed (protects the 4 A triac and the thin pump leads), and a single shared TR5 slow-blow (e.g. T500mA) on the valves' common switched-active feed, and a T2A slow-blow in the live feed to the 5 V supply (below; recommended, not required). The trunk conductor from the entry fuse onward is at least 1.5 mm² and rated well above 10 A (see `wiring-and-connectors.csv`).

**Order is load-bearing.** The MOV sits **downstream of the fuse**. Its designed failure mode is a short; upstream of the fuse a failed MOV is an unfused arc across the mains. Downstream, it blows the fuse and the machine goes dark. The RN3404 is a plain disc with no thermal disconnect, so this is load-bearing, not optional. A thermally-protected TMOV from element14/Mouser is the better part if the freight is already being paid.

**Lead length is load-bearing.** MOV clamping at real surge rates is dominated by lead inductance, not by the disc: roughly 1 nH/mm, and at 1 kA/µs a sloppy 50 mm loop adds hundreds of volts on top of the 710 V clamp. Mount it hard against the fuse holder terminals, total loop under ~25 mm.

**L-N only.** L-E and N-E modes leak to earth continuously and are an RCD nuisance-trip generator. Multi-mode protection is a switchboard SPD's job, not an appliance's.

## Decided: chain rating margin

`DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE` (Chosen): the chain is rated above its fuse and the valve and pump branches are fused.

- Lead: the existing fixed mains lead is retained and no filter or inlet is fitted (the owner's ruling; the 15 A filter this bullet once named is dropped).
- Trunk downstream of the T10A: at least 1.5 mm², rated well above 10 A (Jaycar WB1568, 2 mm², 20 A), in place of the 1.0 mm² WB1565.
- T10A slow-blow entry fuse unchanged. It now protects conductors rated above it, not equal to it.
- Valve branches (0.75 mm² flex): one shared subminiature TR5 slow-blow fuse (250 Vac) on their common switched-active feed, sized to coil inrush; the coil current is recorded in `connector-pinouts.md` (at most 64.6 mA rms steady and 101.4 mA rms inrush per coil at 253 V), and the fuse's rating is the board design's to record, so T500mA is an example only. Series (Littelfuse 372 or Schurter MSF 250) to confirm. No fuse was seen on either pump branch along the visible loom at the board end (the far ends of the pump leads were not recorded, and the board's fit does not need them: the harness is reused as it is, owner statement, 2026-10-20), so each pump branch gains a 1-2 A slow-blow fuse of its own, sized to that pump's running current (0.46 A coffee and 0.19 A steam at 253 V, the sizing values under an assumed 0.5 power-factor floor; `connector-pinouts.md` § Pumps: running current) and its start surge.
- Upstream breaker is declared as up to 20 A (project assumption).

Facts that still matter: the room is declared at 10 to 35 °C and the humidity inside the enclosure as condensing (`reference-machine.md` § Ambient), and the air temperature inside the enclosure (the room plus the enclosure's rise) is unmeasured (earlier estimate for the 5 V supply's surroundings 45-60 °C, replaced as the derating basis by the assumed 70 °C of `controller-board-design-constraints.md` § Enclosure air temperature, which bring-up replaces in turn with the measured figure); the machine's own worst case is about 10.5 A, at 253 V, the declared supply span's top (`reference-machine.md` § Heating and load); a slow-blow fuse carries more than its rating for a long time before it opens (the T10A curve was not read here). The true rating of 0.75 mm² flex is still unchecked against the applicable standard (one reviewer believes 7.5 A in AU, unverified); the valve fuse is sized to the coils, not the flex.

## Variant traps

This is the part worth keeping. Every one of these is a part number that looks right and is not. The filter variants that stood here are removed with the filter.

| Trap | What happens | Correct choice |
|---|---|---|
| **MOV `471` vs `431`** | `14D471K`/`20D471K` are 300 Vac rated and clamp at 775 V. The `431` parts are 275 Vac and clamp at 710 V, more sensitive to the surges that matter at 230 V. RN3400 is the 17.5 mm/115 J step down | 275 Vac rated |
| **Non-mains fuse holders** | Many cheap panel holders are 250 V **DC** automotive parts with exposed terminals | 250 Vac, 10 A, shrouded or insulated terminals |

## 5 V supply: Mean Well IRM-10-5 (chosen)

The supply is the **IRM-10-5** (10 W / 2 A), sized on load rather than headroom instinct. Rejected on the way: the HLK-10M05 and the IRM-05-5 (5 W / 1 A, marginal against the derated load at 60 °C), both superseded by the IRM-10-5, which has the same case, pins and curve shape as the IRM-05-5.

- **Load.** The typical-based budget is about **0.53 A** (117 mA H743 + about 39 mA of 3V3 loads + 143 mA relay-module coils + about 29 mA SSR drive + about 100 mA indicators + about 75 mA gauge board + about 30 mA buzzer; many items estimated, unmeasured). The 143 mA is the relay module's coil current (2 x 71.4 mA, one coil per valve channel fitted; the BOM's 286 mA is all four coils), not the valve solenoid current, which is on the mains side. An earlier ~450 mA figure omitted the panel, gauge board and buzzer.
- **Worst case with datasheet maximums.** The 0.53 A is not a worst case for the gauge stepper driver. The 75 mA gauge-board figure matches the VID6608 datasheet's 76 mA typical (the BOM current column has no gauge-board row, so this mapping is inferred); the datasheet maximum is 200 mA, and it does not say whether the figures are per driver channel or per device. The earlier `control-board-electrical-requirements.csv` E16 therefore doubled both. Substituting 200 mA for 75 mA gives 0.53 - 0.075 + 0.200 = about 0.66 A; substituting a doubled 400 mA gives about 0.86 A. So the worst case is about **0.66 to 0.86 A**, which is 66 % to 86 % of the IRM-10-5's 1.0 A at 70 °C (44 % to 57 % of 1.5 A at 60 °C).
- **Derating** (read off the Mean Well IRM-05 and IRM-10 spec sheets; chart values, approximate): 100 % load up to 50 °C ambient, about 75 % at 60 °C, about 50 % at 70 °C. For the IRM-10-5 that is 2 A, 1.5 A at 60 °C, 1.0 A at 70 °C, so the 0.53 A typical-based budget is about 35 % of the derated rating at 60 °C and 53 % at 70 °C. The basis for judging derating is now the assumed 70 °C of `controller-board-design-constraints.md` § Enclosure air temperature; the earlier basis, kept as history, was the **estimate** that the internal ambient near the boiler will be 45-60 °C (an estimate, not a measurement; the air temperature inside the enclosure is unmeasured, and only the room's span is declared, in `reference-machine.md` § Ambient).
- **Approvals** are real and documented: IEC/UL/EN 62368-1 and EN61558. Isolation 4.2 kVac I/P-O/P. EN55032 Class B **without additional components**. Efficiency 77 % typical (against 71 % for the IRM-05-5).
- **Surge immunity** EN61000-4-5 **Level 3, 1 kV L-N only**: it is a Class II design with no FG pin, so there is no line-to-earth path at all. Another reason the entry varistor is not optional.
- **Internal fuse: not established (the spec sheets read do not mention one).** Nothing here claims an internal fuse; confirm in the user manual. The external T2A slow-blow below is recommended, not required, since the upstream T10A does not protect the wire or a fault inside the module.
- **Switching frequency** is 65 kHz, the same ballpark as an open-frame board. The size advantage is potting and dense assembly, not frequency. Cold-start inrush is 40 A at 230 V.
- **Source.** element14 / Mouser / RS AU. Do not buy Mean Well on AliExpress: counterfeits, and the approvals are the entire reason for choosing it.

### Carrier and fitting

The IRM has four 1.0 mm pins that are not on a 2.54 mm grid (38.5 mm between the AC/L-AC/N column and the -V/+V column; 10.75 mm AC/L to AC/N; 8 mm -V to +V), so a perfboard will not take it. It sits on a **blank single-sided copper-clad FR4 board** (about 70 x 30 mm), holes drilled from a 1:1 print of the datasheet footprint, the copper cut into islands and each island meter-checked for isolation. The module needs no external input or output parts; nothing else is required on the carrier.

- **Gap width matters.** Remove a band of copper at least 4-5 mm wide between the AC/L and AC/N islands, and between either and anything else on the mains side (slot the board if you can); a 1 mm cut leaves far too little creepage at 230 V. About 1 mm is fine only between the 5 V +V and -V islands. Mains in at one end and 5 V out at the other: the module's own 38.5 mm pin separation keeps primary and secondary apart.
- **T2A slow-blow fuse** (5x20 mm, PCB-mount holder with cover, 250 VAC, shrouded; many cheap holders are 12 V/DC automotive) in the live feed, bridging the cut between the AC/L-in island and the module island. Recommended, not required. Slow-blow because of the 40 A inrush.
- **Output capacitors** 47-100 µF 16 V low-ESR (or polymer) across +V/-V close to the pins, with a 100 nF ceramic: the datasheet measures its 200 mVp-p ripple limit with 0.1 µF + 47 µF across the output, so this pair makes the rated figure hold. Not required for the module to run.
- **Terminals.** 5.08 mm PCB screw terminal blocks rated 300 V or more for mains in; read the rating on the datasheet of the part bought.
- **Cover and coating.** Insulating cover over the mains terminals (touch protection). Acrylic conformal coat is recommended because humidity inside the enclosure is declared as condensing until measured (`reference-machine.md` § Ambient), but **it does not replace creepage**: the gaps and the pin separation must stand on their own. Kapton tape is for masking only, not as a mains barrier.
- A community PCB for the IRM family exists (theslowdiyer.wordpress.com, Gerbers, licence not stated, no creepage figures, pin match to the IRM-10 not verified); mounted rotated 90 degrees it would stand the module on its 25.4 mm edge, so check its height plus the board against the usable height above the board (23.4 mm within about 2 mm of a wall, and 28 mm elsewhere, an owner allowance resting on the AC/DC module's top, a single point: `reference-machine.md § Controller enclosure as found`) before relying on it.

### Rejected: the open-frame AliExpress 5 V module

A generic open-frame 5 V/2 A board was considered and rejected. It is better than the category floor (input fuse, apparent MOV, common-mode choke, optocoupler feedback, real bobbin transformer with an isolation slot), but:

- **Open frame at 230 V** inside a machine that holds water under pressure and vibrates.
- **The 2 A rating is a peak figure**; honest continuous output is nearer 1 A.
- **No traceable approval**, no datasheet, no creepage spec.
- Silkscreen suggests a shared multi-voltage PCB (a `DC-12` marking near the output pads), so a mis-shipped variant is a live risk.

It is also **not smaller**: ~66 x 40 x 25 mm ≈ 66 cm³, against the IRM-10-5's 45.7 x 25.4 x 21.5 mm ≈ 25 cm³. Encapsulated modules win on volume; open-frame boards only look compact.

## Panel switch: not fitted, deliberately

A switched appliance-inlet variant (`CW2B`, Schurter `DD` series) was considered and rejected; the machine fits no inlet at all:

- **AU GPOs are switched.** A panel rocker duplicates a switch that already exists on every outlet.
- **Neither is isolation for servicing.** Working inside means *unplug*, a visible break nobody can flip back. Both wall and panel switches are single-pole and leave neutral connected. A panel rocker actively invites the wrong habit.
- **It is another 10 A series contact**, a wear item in the main path, and it costs panel depth.

If reach turns out to be the problem during firmware work, a switch in the fixed lead is the answer, outside the enclosure.

**Settled by inspection, owner statement 2026-10-20:** the machine's own mains lead is a fixed cord with a standard Australian 10 A plug with an earth pin, marked 7.5-10 A 250 V, with no switch and no appliance inlet between the plug and the board (`../connector-pinouts.md` § The source of each live feed); a detachable inlet is not fitted: the owner has ruled that the machine keeps this lead. **The reading below stands:** no hard mains switch was found in the machine documents. What is recorded is the operator panel (ten tact switches in five parallel pairs, so five key signals; eight indicator elements) plus three ground-switched inputs on their own wires (the tank level sensor and the two knob microswitches `S7` hot water and `S8` steam, rated 250 V 3 A each), all enumerated as *logic* channels the controller reads directly (`SOL-CHANNEL-ENUMERATION-CORRECTED.C4`; to confirm the node's current wording against `reference-machine.md`, which corrected the earlier count of eight pushbuttons). These are momentary inputs, not a mains break. If that is the whole picture, then once the control board is replaced the machine's only mains break is the plug, and "off" becomes whatever the firmware decides. The inspection above found no switch in the lead either.

## Sourcing split

The reasoning is the same one already applied to the future solenoid valves in `control-system-bom.csv`: the failure mode is a spec sheet that does not describe the part in the box, and it bites hardest on components whose only job is to be true under fault conditions.

| Class | Where | Why |
|---|---|---|
| Protective devices whose datasheet *is* the product: 5 V PSU | element14 / Mouser / RS AU / Fastron | Derating curves and surge levels are the thing being bought |
| Compliant commodity: MOV, fuses, holders, wire, enclosures | **Jaycar** | Under the EESS a Responsible Supplier is legally accountable for compliance and must hold test records for 10 years. An AliExpress RCM logo is a JPEG |
| Modules: controller, relays, breakouts | Core Electronics | Already the BOM's channel |
| Inspectable low-consequence hardware: standoffs, perfboard, heatsinks | AliExpress | Consequences of a bad part are visible and cheap |

## Open items

- **Fuse sizing against the machine's own draw** (decided: see Decided: chain rating margin, above). `reference-machine.md` § Heating and load puts the worst case at 253 V, the declared span's top: both elements at about 10.18 A, and about **10.5 A** with both pumps running (the pumps taken at their real power; at their sizing currents, `connector-pinouts.md` § Pumps: running current, about 10.8 A). The 20 A trunk sits above that figure and the T10A fuse protects it; the open point is the TR5 valve fuse series, **to confirm**.
- **Thermal fuse rating** in the machine: thermal fuse said by the parts list to be 240 °C and on the steam block (a published, unverified derived view; `reference-machine.md` § Protection records none seen at the board end and none found by the owner, so no rating is recorded for this machine).
- **Whether the machine has a hard mains switch at all**: not established, see above.
- **IRM-10-5 internal fuse**: not established (the spec sheets read do not mention one); confirm in the user manual.
- **Enclosure ambient** for the IRM-10-5 derating: the air temperature inside the enclosure is unmeasured, and the design grades to an assumed 70 °C (`controller-board-design-constraints.md` § Enclosure air temperature); the room's span (10 to 35 °C) and the humidity inside the enclosure (condensing) are declared in `reference-machine.md` § Ambient.
- **MOV is a consumable with no in-circuit test.** Worth a build note to renew it after any nearby lightning event or supply disturbance, since a degraded disc gives no indication.
- **SSR mounting: proposed, not decided.** Superseded: the air temperature the parts are graded to is now the project assumption of `controller-board-design-constraints.md` § Enclosure air temperature, and the owner's plan of 2026-10-23 is to mount the heater switches outside the enclosure on the machine's metal wall (cutting away the plastic side wall), so this proposal and the 45-60 °C estimate are not the basis. The rest of this entry is the earlier proposal, kept as history. The BOM's user note proposes trying the SSRs mounted direct to the side wall to avoid heatsinks. Thermal conflict: each SSR dissipates about 5-6.5 W, and the IRM-10-5 derates from 100 % at 50 °C ambient (about 75 % at 60 °C), so heat from the SSRs raises the ambient the 5 V module is judged against. If it is tried, the 5 V module belongs on the *opposite* side of the enclosure. The wall is plastic and unearthed as found (reference-machine.md § Controller enclosure as found); do not rely on it as a bonded or earthed surface until that is established by inspection.

## Graph gap

**No criterion anywhere requires surge or transient suppression.** A search across the graph for surge, varistor, transient and EMC coverage returned nothing that asserts it (as of the earlier note; not re-searched in this refresh). The protective chain per `OBL-ELECTRICAL-THERMAL-SAFETY-001.C8` is explicitly about *fault current*, interrupted upstream; a transient is neither.

So the MOV in this chain would be fitted because it is obviously sensible, with nothing in the graph asserting it and nothing to stop a later revision quietly dropping it. That is the *assumed, not required* pattern named in `CLAUDE.md`, and it is unresolved. Whether it belongs as a new criterion on `REQ-ELECTRICAL-INSTALL-001` or on `OBL-ELECTRICAL-THERMAL-SAFETY-001` has not been decided, and nothing has been authored (`decisions.md`: nothing in this folder is in the graph yet).

The fuse is in better shape: `REQ-ELECTRICAL-INSTALL-001.C7` already requires the upstream protection to be declared and the wiring rated for it, and `.C8` already requires sensing accuracy to hold under load. Both were `verdict: unknown` at the earlier note and neither has been discharged.
