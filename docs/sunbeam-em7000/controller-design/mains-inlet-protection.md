# Mains inlet protection

Refreshed 2026-10-12 from `decisions.md` (which supersedes older text), the current design data in this folder, and the earlier working note of the same name. **Not baselined, not traced to any criterion, and not evidence for anything.** It records why the inlet parts and the 5 V supply were chosen and, more usefully, which variants of them are wrong, because most of the cost of this decision was spent discovering that the obvious part numbers are the wrong ones.

Chosen parts (`decisions.md`): inlet is the Schaffner FN9222-15-06 with a T10A slow-blow on the active and an RN3404 MOV (D8, Chosen; filter and trunk rated above the fuse by `DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE`). The supply is one Mean Well IRM-10-5 on a hand-cut single-sided copper-clad carrier, a recommended (not required) T2A slow-blow fuse, and an output of 100 nF and 47-100 uF (D7, Chosen).

## The problem this addresses

The retrofit's protective chain interrupts on **temperature** and nothing else. The machine carries three thermostats (110 °C coffee, 200 °C steam, 110 °C pump) and, per the parts list, a thermal fuse said to be a 240 °C steam-block part. That is a published, unverified derived view: `reference-machine.md` § Protection records the fuse as fitted with its rating not established, and its location is not established. A short, an insulation breakdown, or a partial fault is not a thermal event and none of it responds. `OBL-ELECTRICAL-THERMAL-SAFETY-001.C8` already states this in exactly those terms.

Upstream is an ordinary domestic circuit breaker. In an AU installation the plug is unfused, so "upstream" means a 16 or 20 A MCB; the build declares up to 20 A (`reference-machine.md` § Supply, project assumption). That leaves a band uncovered: a chafed conductor, an SSR failing part-shorted, carbon tracking across a damp terminal, or a solenoid coil shorting turn-to-turn draws something like 8-15 A indefinitely. That is below the breaker's threshold and well above what melts insulation. The T10A inlet fuse below narrows that band rather than closing it: a slow-blow fuse carries about one and a half times its rating, about 15 A, for half an hour or more before it opens (`DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE`; the T10A's own curve was not read here), so a fault between 10 A and about 15 A is cleared only slowly and one below 10 A not at all. *(See Open items: the machine's own worst-case draw, at 253 V, the declared span's top, is itself about 10.5 A, over 10 A.)*

The sharper form of the same point, and what `REQ-ELECTRICAL-INSTALL-001.C7` is asking for: **a 20 A breaker permits 20 A through every conductor the retrofit adds.** A local 10 A fuse is what makes it admissible to wire internal branches for that fuse, including its slow-blow overload band, rather than for the breaker's rating. A branch with no fuse of its own is wired for the 10 A fuse, not for its load's draw: the two heater branches are, so their conductors, board copper carrying heater current included, are rated for the inlet fuse rather than for the element (`DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE`). Only a branch with its own smaller fuse, the pumps' and the valves', may be wired for that fuse instead.

Separately, the phase-cut pump dimmer is a broadband noise source sharing an enclosure with the NTC and PT1000 dividers feeding the controller's 16-bit ADCs. `REQ-ELECTRICAL-INSTALL-001.C8` requires precision sensing to hold its stated accuracy *while the switched loads operate*. An inlet filter is how that is made achievable rather than discovered to have failed at test time. (No MAX31865 front end is fitted: D10.)

## Why this is not solved by buying a better PSU

Every part on the mains side needs this, not just the 5 V supply. A PSU module's own onboard fuse, filter and (if fitted) MOV protect **that module's primary only**. The SSRs, the pump dimmers' BT136S-600E triacs, and the mains-coil solenoids are fed from elsewhere and are covered by none of it, and a 600 V triac is considerably more surge-vulnerable than a flyback front end.

So the protection belongs **once, at the machine inlet**, upstream of everything.

## The chain

```
mains ──► FN9222-15-06 (IEC C14 inlet + EMI filter) ──► L ──► [T10A slow-blow] ──┬──► SSRs, dimmers,
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
| Inlet + filter | Schaffner **FN9222-15-06** | C14 inlet (coupler rating of the 15 A part UNVERIFIED) and EMI filter in the panel cut-out, no fuseholder. Rated 15 A @ 50 °C (`DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE`). 10 A part's figures, not rechecked for 15 A: Cx 0.1 µF, Cy 2.2 nF, L 0.225 mH @ 10 A, leakage 373 µA @ 250 V/50 Hz. ENEC/CQC/UL/CSA, IP40 |
| Fuse | Panel-mount M205 holder, **T10A slow-blow**, on active | Interrupts, below the breaker's threshold, a sustained fault the breaker does not, but slowly near its rating: it carries about 15 A for half an hour or more before it opens (`DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE`), so everything downstream that relies on it alone is rated for that band. Slow-blow is mandatory: the 5 V module's cold-start inrush is 40 A at 230 Vac, on top of heater switching |
| Surge | Jaycar **RN3404**, 275 Vac, 6500 A, 190 J, 24 mm disc, L-N | Nothing else in the machine responds to a transient |

Downstream branch protection that the T10A does not provide: a 1-2 A slow-blow fuse in each pump dimmer's AC-L in feed (protects the 4 A triac and the thin pump leads), and a single shared TR5 slow-blow (e.g. T500mA) on the valves' common switched-active feed, and a T2A slow-blow in the live feed to the 5 V supply (below; recommended, not required). The trunk conductor from inlet through the T10A is at least 1.5 mm² and rated well above 10 A (see `wiring-and-connectors.csv`).

**Order is load-bearing.** The MOV sits **downstream of the fuse**. Its designed failure mode is a short; upstream of the fuse a failed MOV is an unfused arc across the mains. Downstream, it blows the fuse and the machine goes dark. The RN3404 is a plain disc with no thermal disconnect, so this is load-bearing, not optional. A thermally-protected TMOV from element14/Mouser is the better part if the freight is already being paid.

**Lead length is load-bearing.** MOV clamping at real surge rates is dominated by lead inductance, not by the disc: roughly 1 nH/mm, and at 1 kA/µs a sloppy 50 mm loop adds hundreds of volts on top of the 710 V clamp. Mount it hard against the fuse holder terminals, total loop under ~25 mm.

**The filter itself ends up fused only by the upstream breaker.** That is normal for this part class: its components are X2/Y2 safety capacitors designed to fail safely plus a wire-wound choke, and Schaffner build the entire unfused-inlet category on that basis.

**L-N only.** L-E and N-E modes leak to earth continuously and are an RCD nuisance-trip generator. Multi-mode protection is a switchboard SPD's job, not an appliance's.

## Decided: inlet chain rating margin

`DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE` (Chosen): the chain is rated above its fuse and the valve and pump branches are fused.

- Filter: Schaffner **FN9222-15-06**, 15 A at 50 °C, same family, in place of the 10 A part. Whether its appliance coupler stays IEC C14 (10 A) is **UNVERIFIED**; check the datasheet, since a 10 A coupler would still cap the inlet.
- Trunk downstream of the T10A: at least 1.5 mm², rated well above 10 A (Jaycar WB1568, 2 mm², 20 A), in place of the 1.0 mm² WB1565.
- T10A slow-blow inlet fuse unchanged. It now protects conductors rated above it, not equal to it.
- Valve branches (0.75 mm² flex): one shared subminiature TR5 slow-blow fuse (250 Vac) on their common switched-active feed, sized to coil inrush; the coil current is recorded in `connector-pinouts.md` (at most 64.6 mA rms steady and 101.4 mA rms inrush per coil at 253 V), and the fuse's rating is the board design's to record, so T500mA is an example only. Series (Littelfuse 372 or Schurter MSF 250) to confirm. No fuse was seen on either pump branch along the visible loom at the board end (the far ends of the pump leads were not recorded), so each pump branch gains a 1-2 A slow-blow fuse of its own, sized to that pump's running current (at most 0.38 A coffee and 0.17 A steam at 253 V) and its start surge.
- Upstream breaker is declared as up to 20 A (project assumption).

Facts that still matter: the filter derates above 50 °C and the enclosure ambient is unmeasured (earlier estimate for the 5 V supply's surroundings 45-60 °C); the machine's own worst case is about 10.5 A, at 253 V, the declared span's top (`reference-machine.md` § Heating and load); a slow-blow fuse carries more than its rating for a long time before it opens (the T10A curve was not read here). The true rating of 0.75 mm² flex is still unchecked against the applicable standard (one reviewer believes 7.5 A in AU, unverified); the valve fuse is sized to the coils, not the flex.

## Variant traps

This is the part worth keeping. Every one of these is a part number that looks right and is not.

| Trap | What happens | Correct choice |
|---|---|---|
| **`B` suffix = medical** | Y-capacitors deleted entirely (leakage 373 µA → 2 µA) to meet IEC/EN 60601-1. The Y-caps *are* the common-mode filtering, the exact mechanism needed against the dimmer. Pays a premium to remove the feature | No suffix letter |
| **`A` suffix = low leakage** | Cy 2.2 nF → 0.47 nF. Exists for installations stacking many filters on one RCD. 373 µA against a 30 mA RCD is ~1 % of threshold | No suffix letter |
| **`Z` suffix = built-in MOV** | Tidy, and factory lead lengths are ideal. But a MOV is a **consumable** that degrades silently; an internal one cannot be inspected or renewed without scrapping the module. Its energy rating is not separately specified. Also forces the `U` mounting style and drops P→N hipot from 1000 Vac to 250 Vac | Plain filter + discrete RN3404 |
| **`S`/`S1` snap-in, `HI` hot inlet** | Other FN9222 suffixes (part-numbers) | No suffix letter |
| **FN9260 vs FN9222** | FN9260 is the *same filter* with a twin fuseholder (fuses neutral too), at roughly 2.5× the price. FN261 is the same again with a single fuseholder. Only worth it to avoid a second panel hole | FN9222 + separate holder: cheaper, gives single-pole active fusing, and a chassis holder is easier to service than an inlet drawer |
| **Generic `CW2B-10A-T` etc.** | AliExpress equivalents at ~AUD 8. Hollow housings with no choke or caps fitted are a known failure in this category, and the naming drifts between sellers (`CW1B`/`CW1D`/`CW2B`/`CW2C` used interchangeably; the `-T` suffix is undocumented) | Defensible *only* with an arrival check: internal photos, measure L-N capacitance, ring out the choke and the earth tab. Buy by the photo, not the part number |
| **MOV `471` vs `431`** | `14D471K`/`20D471K` are 300 Vac rated and clamp at 775 V. The `431` parts are 275 Vac and clamp at 710 V, more sensitive to the surges that matter at 230 V. RN3400 is the 17.5 mm/115 J step down | 275 Vac rated |
| **Non-mains fuse holders** | Many cheap panel holders are 250 V **DC** automotive parts with exposed terminals | 250 Vac, 10 A, shrouded or insulated terminals |

## 5 V supply: Mean Well IRM-10-5 (chosen)

The supply is the **IRM-10-5** (10 W / 2 A), sized on load rather than headroom instinct. Rejected on the way: the HLK-10M05 and the IRM-05-5 (5 W / 1 A, marginal against the derated load at 60 °C), both superseded by the IRM-10-5, which has the same case, pins and curve shape as the IRM-05-5.

- **Load.** The typical-based budget is about **0.53 A** (117 mA H743 + about 39 mA of 3V3 loads + 143 mA relay-module coils + about 29 mA SSR drive + about 100 mA indicators + about 75 mA gauge board + about 30 mA buzzer; many items estimated, unmeasured). The 143 mA is the relay module's coil current (2 x 71.4 mA, one coil per valve channel fitted; the BOM's 286 mA is all four coils), not the valve solenoid current, which is on the mains side. An earlier ~450 mA figure omitted the panel, gauge board and buzzer.
- **Worst case with datasheet maximums.** The 0.53 A is not a worst case for the gauge stepper driver. The 75 mA gauge-board figure matches the VID6608 datasheet's 76 mA typical (the BOM current column has no gauge-board row, so this mapping is inferred); the datasheet maximum is 200 mA, and it does not say whether the figures are per driver channel or per device. The earlier `control-board-electrical-requirements.csv` E16 therefore doubled both. Substituting 200 mA for 75 mA gives 0.53 - 0.075 + 0.200 = about 0.66 A; substituting a doubled 400 mA gives about 0.86 A. So the worst case is about **0.66 to 0.86 A**, which is 66 % to 86 % of the IRM-10-5's 1.0 A at 70 °C (44 % to 57 % of 1.5 A at 60 °C).
- **Derating** (read off the Mean Well IRM-05 and IRM-10 spec sheets; chart values, approximate): 100 % load up to 50 °C ambient, about 75 % at 60 °C, about 50 % at 70 °C. For the IRM-10-5 that is 2 A, 1.5 A at 60 °C, 1.0 A at 70 °C, so the 0.53 A typical-based budget is about 35 % of the derated rating at 60 °C and 53 % at 70 °C. The basis for judging derating at 60 °C is the earlier **estimate** that the internal ambient near the boiler will be 45-60 °C (an estimate, not a measurement; the ambient inside the enclosure is unmeasured).
- **Approvals** are real and documented: IEC/UL/EN 62368-1 and EN61558. Isolation 4.2 kVac I/P-O/P. EN55032 Class B **without additional components**. Efficiency 77 % typical (against 71 % for the IRM-05-5).
- **Surge immunity** EN61000-4-5 **Level 3, 1 kV L-N only**: it is a Class II design with no FG pin, so there is no line-to-earth path at all. Another reason the inlet MOV is not optional.
- **Internal fuse: not established (the spec sheets read do not mention one).** Nothing here claims an internal fuse; confirm in the user manual. The external T2A slow-blow below is recommended, not required, since the upstream T10A does not protect the wire or a fault inside the module.
- **Switching frequency** is 65 kHz, the same ballpark as an open-frame board. The size advantage is potting and dense assembly, not frequency. Cold-start inrush is 40 A at 230 V.
- **Source.** element14 / Mouser / RS AU. Do not buy Mean Well on AliExpress: counterfeits, and the approvals are the entire reason for choosing it.

### Carrier and fitting

The IRM has four 1.0 mm pins that are not on a 2.54 mm grid (38.5 mm between the AC/L-AC/N column and the -V/+V column; 10.75 mm AC/L to AC/N; 8 mm -V to +V), so a perfboard will not take it. It sits on a **blank single-sided copper-clad FR4 board** (about 70 x 30 mm), holes drilled from a 1:1 print of the datasheet footprint, the copper cut into islands and each island meter-checked for isolation. The module needs no external input or output parts; nothing else is required on the carrier.

- **Gap width matters.** Remove a band of copper at least 4-5 mm wide between the AC/L and AC/N islands, and between either and anything else on the mains side (slot the board if you can); a 1 mm cut leaves far too little creepage at 230 V. About 1 mm is fine only between the 5 V +V and -V islands. Mains in at one end and 5 V out at the other: the module's own 38.5 mm pin separation keeps primary and secondary apart.
- **T2A slow-blow fuse** (5x20 mm, PCB-mount holder with cover, 250 VAC, shrouded; many cheap holders are 12 V/DC automotive) in the live feed, bridging the cut between the AC/L-in island and the module island. Recommended, not required. Slow-blow because of the 40 A inrush.
- **Output capacitors** 47-100 µF 16 V low-ESR (or polymer) across +V/-V close to the pins, with a 100 nF ceramic: the datasheet measures its 200 mVp-p ripple limit with 0.1 µF + 47 µF across the output, so this pair makes the rated figure hold. Not required for the module to run.
- **Terminals.** 5.08 mm PCB screw terminal blocks rated 300 V or more for mains in; read the rating on the datasheet of the part bought.
- **Cover and coating.** Insulating cover over the mains terminals (touch protection). Acrylic conformal coat is recommended because the box is not sealed, but **it does not replace creepage**: the gaps and the pin separation must stand on their own. Kapton tape is for masking only, not as a mains barrier.
- A community PCB for the IRM family exists (theslowdiyer.wordpress.com, Gerbers, licence not stated, no creepage figures, pin match to the IRM-10 not verified); mounted rotated 90 degrees it would stand the module on its 25.4 mm edge, so check its height plus the board against the usable height above the board (23.4 mm within about 2 mm of a wall, and at least 28 mm where the original tallest part stood: `reference-machine.md § Controller enclosure as found`) before relying on it.

### Rejected: the open-frame AliExpress 5 V module

A generic open-frame 5 V/2 A board was considered and rejected. It is better than the category floor (input fuse, apparent MOV, common-mode choke, optocoupler feedback, real bobbin transformer with an isolation slot), but:

- **Open frame at 230 V** inside a machine that holds water under pressure and vibrates.
- **The 2 A rating is a peak figure**; honest continuous output is nearer 1 A.
- **No traceable approval**, no datasheet, no creepage spec.
- Silkscreen suggests a shared multi-voltage PCB (a `DC-12` marking near the output pads), so a mis-shipped variant is a live risk.

It is also **not smaller**: ~66 x 40 x 25 mm ≈ 66 cm³, against the IRM-10-5's 45.7 x 25.4 x 21.5 mm ≈ 25 cm³. Encapsulated modules win on volume; open-frame boards only look compact.

## Panel switch: not fitted, deliberately

A switched inlet variant (`CW2B`, Schurter `DD` series) was considered and rejected:

- **AU GPOs are switched.** A panel rocker duplicates a switch that already exists on every outlet.
- **Neither is isolation for servicing.** Working inside means *unplug*, a visible break nobody can flip back. Both wall and panel switches are single-pole and leave neutral connected. A panel rocker actively invites the wrong habit.
- **It is another 10 A series contact**, a wear item in the main path, and it costs panel depth.

If reach turns out to be the problem during firmware work, an **inline switched IEC lead** is the answer: a few dollars, switch where the hand is, no panel depth consumed.

**Open:** no hard mains switch was found in the machine documents. What is recorded is the operator panel (ten tact switches in five parallel pairs, so five key signals; eight indicator elements) plus three ground-switched inputs on their own wires (the tank level sensor and the two knob microswitches `S7` hot water and `S8` steam, rated 250 V 3 A each), all enumerated as *logic* channels the controller reads directly (`SOL-CHANNEL-ENUMERATION-CORRECTED.C4`; to confirm the node's current wording against `reference-machine.md`, which corrected the earlier count of eight pushbuttons). These are momentary inputs, not a mains break. If that is the whole picture, then once the control board is replaced the machine's only mains break is the plug, and "off" becomes whatever the firmware decides. **Establish by inspection.**

## Sourcing split

The reasoning is the same one already applied to the future solenoid valves in `control-system-bom.csv`: the failure mode is a spec sheet that does not describe the part in the box, and it bites hardest on components whose only job is to be true under fault conditions.

| Class | Where | Why |
|---|---|---|
| Protective devices whose datasheet *is* the product: inlet filter, 5 V PSU | element14 / Mouser / RS AU / Fastron | Derating curves and surge levels are the thing being bought |
| Compliant commodity: MOV, fuses, holders, wire, enclosures | **Jaycar** | Under the EESS a Responsible Supplier is legally accountable for compliance and must hold test records for 10 years. An AliExpress RCM logo is a JPEG |
| Modules: controller, relays, breakouts | Core Electronics | Already the BOM's channel |
| Inspectable low-consequence hardware: standoffs, perfboard, heatsinks | AliExpress | Consequences of a bad part are visible and cheap |

## Open items

- **FN9222 dimension letters not mapped.** The datasheet's dimension table gives A 48, B 22.4, C 40 ±0.2, D 38.25, E 27.8, G 20.1, N 21.5, P 28.5 for the 10-15 A types, but the drawing that assigns those letters to length/width/depth and to the panel cut-out was not parsed. The BOM carries 48 x 38.25 x 27.8 mm from letters A/D/E, unconfirmed. **Confirm the mapping and the cut-out against the drawing before cutting the panel.**
- **FN9222 termination type** (output tabs or screws) is not recorded in the inputs; to confirm against the datasheet (it decides the trunk crimp terminals).
- **Fuse and filter sizing against the machine's own draw** (decided: see Decided: inlet chain rating margin, above). `reference-machine.md` § Heating and load puts the worst case at 253 V, the declared span's top: both elements at about 10.18 A, and about **10.5 A** with both pumps running. The 15 A filter and the 20 A trunk sit above that figure and the T10A fuse protects them; the open points are the 15 A filter's coupler rating (IEC C14 is 10 A), its termination type, and the TR5 valve fuse series, all **to confirm**.
- **Thermal fuse rating** in the machine: thermal fuse said by the parts list to be 240 °C and on the steam block (a published, unverified derived view; `reference-machine.md` § Protection records the rating and location as not established).
- **Whether the machine has a hard mains switch at all**: not established, see above.
- **IRM-10-5 internal fuse**: not established (the spec sheets read do not mention one); confirm in the user manual.
- **Enclosure ambient** for the IRM-10-5 derating: unmeasured.
- **MOV is a consumable with no in-circuit test.** Worth a build note to renew it after any nearby lightning event or supply disturbance, since a degraded disc gives no indication.
- **SSR mounting: proposed, not decided.** The BOM's user note proposes trying the SSRs mounted direct to the side wall to avoid heatsinks. Thermal conflict: each SSR dissipates about 5-6.5 W, and the IRM-10-5 derates from 100 % at 50 °C ambient (about 75 % at 60 °C), so heat from the SSRs raises the ambient the 5 V module is judged against. If it is tried, the 5 V module belongs on the *opposite* side of the enclosure. The wall is plastic and unearthed as found (reference-machine.md § Controller enclosure as found); do not rely on it as a bonded or earthed surface until that is established by inspection.

## Graph gap

**No criterion anywhere requires surge or transient suppression.** A search across the graph for surge, varistor, transient and EMC coverage returned nothing that asserts it (as of the earlier note; not re-searched in this refresh). The protective chain per `OBL-ELECTRICAL-THERMAL-SAFETY-001.C8` is explicitly about *fault current*, interrupted upstream; a transient is neither.

So the MOV in this chain would be fitted because it is obviously sensible, with nothing in the graph asserting it and nothing to stop a later revision quietly dropping it. That is the *assumed, not required* pattern named in `CLAUDE.md`, and it is unresolved. Whether it belongs as a new criterion on `REQ-ELECTRICAL-INSTALL-001` or on `OBL-ELECTRICAL-THERMAL-SAFETY-001` has not been decided, and nothing has been authored (`decisions.md`: nothing in this folder is in the graph yet).

The fuse and the filter are in better shape: `REQ-ELECTRICAL-INSTALL-001.C7` already requires the upstream protection to be declared and the wiring rated for it, and `.C8` already requires sensing accuracy to hold under load. Both were `verdict: unknown` at the earlier note and neither has been discharged.
