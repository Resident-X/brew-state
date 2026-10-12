# Controller boards: design constraints

**This file is local, like `reference-machine.md`.** It holds what the replacement controller boards for this machine are designed against, each constraint with where it came from. An adopter fitting a different machine, or the same machine on a different supply, replaces this file along with the declaration it is derived from.

**This is a derived view, and its sources govern.** Nothing here is declared for the first time. Every figure is read off, or worked out from, a source named beside it: the machine's declared configuration (`reference-machine.md`), the channel enumeration (`controller-io.md`), the component specification (`component-specification.md`), a working design document in `controller-design/`, a requirement criterion, or a decision in the graph. Where this file and one of those disagree, the source is right and this file is corrected (`DEC-MACHINE-RECORD-FOLDER-PER-MACHINE`). To change a supply fact, change `reference-machine.md` § Supply and re-derive the figures here from it, never the other way round.

What is not here: choosing track widths, wire gauges, clearances or parts to meet these figures. That is design work, done against this file.

## Requirement-derived figures

The figures this project's requirements impose on the boards, reduced to what a board designer works to. Each entry gives its value with units, its evidence grade, the source a reader holding only this repository can follow, how the value was derived, and the requirement criterion or record entry it comes from. A figure that cannot yet be derived is marked **pending** instead of carrying a value.

### Evidence grades

Each value carries one of these grades. They are not levelled: a figure is no stronger than the weakest grade among the inputs it was derived from, and a derived figure says which input set its grade.

| Grade | Meaning |
|---|---|
| **measured** | Read with an instrument on this machine, the reading recorded with its conditions. |
| **owner statement** | Stated by the machine's owner from direct knowledge, dated, and not yet confirmed by inspection or by a document. |
| **schematic** | Read off the service manual's circuit diagram. |
| **parts list** | Read off the service manual's parts list. |
| **published unverified** | From a published source outside this repository — a standard, a datasheet, a photograph of the same model — cited by its address, whose text has not been checked at that source for this entry. |
| **inferred** | Worked out by reasoning or arithmetic from other entries, or estimated with no measurement behind it. The derivation is shown so the inference can be checked. |
| **unmeasured** | A quantity known to matter for which no value has been established. |
| **project assumption** | A value chosen where no fact exists, so that the design has something to work to. Every one is marked to replace: an adopter puts their own value in its place, and the project replaces it when the fact is established. |

A value that a decision in the graph fixes — a fuse rating, say — is a design choice rather than a fact about the machine. It carries no evidence grade; the entry names the decision instead.

**Pending** is a mark, not a grade. A pending entry names the work that will settle it, in words and by its node in the graph. The mark ends only when that work records the fact and its source. Any document derived from this file shows the mark, not a value.

A figure that a chosen part or a designed circuit fixes, such as a branch fuse's rating or a rail's budget, is settled by **the design task for the board that carries it**. Those tasks do not exist yet: the partition and feasibility task creates one for each board once the division between boards is chosen (`DEL-HW-PARTITION-AND-FEASIBILITY.C5`), and each applies the board design method to its board and proves the board before it is ordered (`DEL-CONTROLLER-HARDWARE.C3`). The partition and feasibility task's choice of form for each function (`DEL-HW-PARTITION-AND-FEASIBILITY.C1`) comes first and decides which parts there are to read figures from, but records only the form and its reason.

### Supply

Declared in `reference-machine.md` § Supply, and cited here rather than restated: the values below are that table's, and its provenance column is the source.

| Figure | Value | Grade | Source | Derivation | From |
|---|---|---|---|---|---|
| Supply voltage span | 216–253 V AC | published unverified | `reference-machine.md` § Supply, *Supply voltage* | The standard tolerance about the 230 V nominal, +10 % / −6 %. The top, 253 V, is the worst case for every current, dissipation and power figure below; the bottom, 216 V, is the least heat the elements deliver | `REQ-MACHINE-CONFIGURATION-001.C1` |
| Peak working voltage | 358 V | inferred | This table | 253 V × √2 = 357.8 V, at the top of the span | `REQ-MACHINE-CONFIGURATION-001.C1`, `OBL-ELECTRICAL-THERMAL-SAFETY-001.C6` |
| Mains frequency | 50 Hz | inferred | `reference-machine.md` § Supply, *Mains frequency* | Read off a pump's nameplate, not off this supply. Heater devices are commanded once per half-cycle, 100 times a second at this frequency (`component-specification.md` § What the supply is, and what changes off it). `REQ-MACHINE-CONFIGURATION-001.C8` asks for a value measured on this supply; until one is recorded, this one stands at its grade | `REQ-MACHINE-CONFIGURATION-001.C1`, `.C8` |
| Supplying circuit rating | 10 A | owner statement, 2026-10-12 | `reference-machine.md` § Supply, *Circuit rating* | — | `OBL-ELECTRICAL-THERMAL-SAFETY-001.C3`, `REQ-MACHINE-CONFIGURATION-001.C1` |
| Upstream protection | Circuit breaker, up to 20 A | project assumption, to replace | `reference-machine.md` § Supply, *Upstream protection* | The conservative end of what protects an AU socket-outlet circuit (`DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE`). An AU plug is unfused, so nothing between this breaker and the machine's own inlet fuse interrupts a fault | `REQ-ELECTRICAL-INSTALL-001.C7`, `OBL-ELECTRICAL-THERMAL-SAFETY-001.C8` |
| Prospective fault current at the outlet | 6 kA | project assumption, to replace | `reference-machine.md` § Supply, *Prospective fault current* | Bounded by the breaking capacity of the breaker protecting the circuit, which a compliant installation sizes for the fault level at the breaker; an outlet further down the same circuit sees less | `OBL-ELECTRICAL-THERMAL-SAFETY-001.C8`, `REQ-ELECTRICAL-INSTALL-001.C7` |
| Wiring authority | AS/NZS 3000 | inferred | `reference-machine.md` § Supply, *Wiring authority* | The machine is an AU/NZ-market model (`reference-machine.md` § The machine), and AS/NZS 3000 is the wiring rules of that jurisdiction | `OBL-ELECTRICAL-THERMAL-SAFETY-001.C9` |

### Supply budget

The sustained draw of everything the boards switch, at the top of the declared span, set against the supplying circuit's rating. This is the budget the controller plans within ahead of time. Keeping commanded draw inside it while running is the controller's arbitration (`REQ-POWER-BUDGET-001`) and is not a board figure.

The budget is spent against the circuit's rating, 10 A, not against the breaker's. The breaker protects the building's wiring. The rating is what the circuit is meant to carry (`OBL-ELECTRICAL-THERMAL-SAFETY-001.C3`, `DEF-SUPPLY-BUDGET`).

| Load the boards switch | Draw at 253 V | Grade | Source and derivation |
|---|---|---|---|
| Coffee thermoblock element | 4.80 A, 1215 W | inferred, from a measured 52.7 Ω | `component-specification.md` § What each switched load needs of its device, *Carries continuously*: 253 V / 52.7 Ω. The cold resistance gives the higher current if the element's resistance rises with temperature, as that section records |
| Steam thermoblock element | 5.38 A, 1362 W | inferred, from a measured 47.0 Ω | Same section: 253 V / 47.0 Ω. 47.0 Ω is a lower bound on the element's resistance, so this is a ceiling on its draw |
| Both elements together | 10.18 A, 2576 W | inferred | Sum of the two rows above |
| Both elements and both pumps | 10.5 A, 2.65 kW | inferred | `reference-machine.md` § Heating and load, the *At 253 V* column. The pumps' share is worked from their real-power ratings; their current is pending, below |
| Both solenoid valve coils | **Pending** — coil current not established | unmeasured | Settled by recording what each retained device imposes on its driver, which names the mains valve coils' voltage and current: `SOL-HW-MACHINE-AS-FOUND-FIT-RECORD.C4` |
| Both pumps, as current rather than real power | **Pending** — 48 W and 22 W are real-power ratings on inductive loads, and no source gives the power factor | the ratings: parts list (22 W, steam pump); published unverified (48 W, coffee pump, from the fitted type's spec sheet) | `component-specification.md` § What each switched load needs of its device, pump rows. Settled by the same record of retained-device characteristics: `SOL-HW-MACHINE-AS-FOUND-FIT-RECORD.C4` |
| Low-voltage supply, mains input | **Pending** — depends on the supply's form and on the rail budgets below | — | Settled by the design task for the board carrying the logic supply (`DEL-HW-PARTITION-AND-FEASIBILITY.C5`), from the part chosen once the partition and feasibility task decides the supply's form (`DEL-HW-PARTITION-AND-FEASIBILITY.C1`) |

| Budget figure | Value | Grade | Derivation | From |
|---|---|---|---|---|
| Sustained budget at the top of the span | 10 A, 2530 W | owner statement (the rating) | 10 A × 253 V | `OBL-ELECTRICAL-THERMAL-SAFETY-001.C3`, `REQ-POWER-BUDGET-001.C6` |
| Draw with every switched load on, at 253 V | at least 10.5 A, before the pending valve coils and low-voltage supply are added | inferred | Rows above | `REQ-POWER-BUDGET-001.C6` |
| Shortfall when everything runs at once | at least 0.46 A | inferred | 10.46 A − 10 A, where 10.46 A is the 10.5 A above before rounding: (2576 + 48 + 22) W / 253 V = 2646 W / 253 V | `OBL-ELECTRICAL-THERMAL-SAFETY-001.C3` |

So at the top of the span, both elements at full duty already draw 10.18 A, over the budget before any pump runs. Full concurrent heating is not within the budget there. What can run together is decided by the controller's arbitration, planned ahead of time against these 253 V figures (`REQ-POWER-BUDGET-001.C6`), not discovered by reaching them.

### Upstream protection and fault current

Which device interrupts a fault follows `DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE`. The 10 A slow-blow inlet fuse interrupts a fault anywhere downstream of the inlet. The upstream breaker protects the supply cord, the inlet and the inlet filter ahead of the fuse. Board copper carrying mains current is wiring throughout this section, held to the same figures as the conductor it continues.

The working design's account of the inlet chain is `controller-design/mains-inlet-protection.md` § The chain and § Decided: inlet chain rating margin.

| Conductor | Protection that interrupts its fault | Current it must carry until that protection acts | Fault current it must survive until that protection clears | Grade | From |
|---|---|---|---|---|---|
| Supply cord, appliance inlet, inlet filter (ahead of the inlet fuse) | Upstream breaker, up to 20 A (project assumption) | Up to 20 A sustained, which the breaker does not interrupt | Up to 6 kA (project assumption) | project assumption | `REQ-ELECTRICAL-INSTALL-001.C7`, `OBL-ELECTRICAL-THERMAL-SAFETY-001.C8` |
| Trunk from the inlet fuse to the branch points, and board copper carrying it | Inlet fuse, 10 A slow-blow (`DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE`) | About 15 A for half an hour or more: a slow-blow fuse carries one and a half times its rating that long before it opens (that decision's rationale; the fitted fuse's own curve has not been read) | Up to 6 kA | inferred (the current it carries); project assumption (the fault current, carried from the supply table) | `OBL-ELECTRICAL-THERMAL-SAFETY-001.C8`, `REQ-ELECTRICAL-INSTALL-001.C7` |
| Each heater branch, from the trunk through its switching device to the element, and board copper carrying it | Inlet fuse; the heater branches carry no fuse of their own | As the trunk: about 15 A for half an hour or more, against a normal 4.80 A (coffee) or 5.38 A (steam) at 253 V | Up to 6 kA | inferred (the current it carries); project assumption (the fault current, carried from the supply table) | `OBL-ELECTRICAL-THERMAL-SAFETY-001.C8`, `REQ-ELECTRICAL-INSTALL-001.C7` |
| Each pump branch, and board copper carrying it | Its own branch fuse (`DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE`), with the inlet fuse behind it | **Pending** — the branch fuse's rating follows the pump drive's form, which the partition and feasibility task reopens (`DEL-HW-PARTITION-AND-FEASIBILITY.C1`), and the pump current below. Settled by the design task for the board carrying the pump drive: `DEL-HW-PARTITION-AND-FEASIBILITY.C5` | Up to 6 kA | project assumption (the fault current, carried from the supply table) | `OBL-ELECTRICAL-THERMAL-SAFETY-001.C8` |
| Both valve branches, from their common switched feed, and board copper carrying it | One shared slow-blow fuse on the common feed, sized to the coils' inrush (`DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE`); board copper on this feed is sized for that fuse, not for the trunk | **Pending** — the fuse's rating follows the coils' current, which the record of retained-device characteristics settles (`SOL-HW-MACHINE-AS-FOUND-FIT-RECORD.C4`). The rating itself is chosen and recorded by the design task for the board carrying the valve feed: `DEL-HW-PARTITION-AND-FEASIBILITY.C5` | Up to 6 kA | project assumption (the fault current, carried from the supply table) | `OBL-ELECTRICAL-THERMAL-SAFETY-001.C8` |
| Low-voltage supply's mains feed, and board copper carrying it | The inlet fuse, unless the supply's form gives it a branch fuse | **Pending** — follows the logic supply's form (`DEL-HW-PARTITION-AND-FEASIBILITY.C1`). Settled by the design task for the board carrying the logic supply: `DEL-HW-PARTITION-AND-FEASIBILITY.C5` | Up to 6 kA | project assumption (the fault current, carried from the supply table) | `OBL-ELECTRICAL-THERMAL-SAFETY-001.C8` |
| Low-voltage conductors and board copper | The low-voltage supply's own output limit | **Pending** — follows the logic supply's form (`DEL-HW-PARTITION-AND-FEASIBILITY.C1`). Settled by the design task for the board carrying the logic supply (`DEL-HW-PARTITION-AND-FEASIBILITY.C5`); if the earlier design's supply module is kept, its output behaviour is the one stated in the carried-forward module properties (`SOL-HW-MODULE-PROPERTIES-CARRIED-FORWARD.C1`) | — | — | `OBL-ELECTRICAL-THERMAL-SAFETY-001.C8` |
| Any conductor fed by the original board's second live feed | **Pending** — why the original board takes two live feeds, and so what protects each, is not established. Settled by tracing each live feed to the device upstream of it in the machine-as-found record: `SOL-HW-MACHINE-AS-FOUND-FIT-RECORD.C3` | Pending | Pending | — | `OBL-ELECTRICAL-THERMAL-SAFETY-001.C8` |

Two further figures follow from the table and are owed by the design that meets it:

| Figure | Value | Grade | Derivation | From |
|---|---|---|---|---|
| Breaking capacity each fuse and breaker in the chain must have | At least the prospective fault current, 6 kA | project assumption (carried from the fault current) | A protective device that cannot break the fault it sees does not interrupt it | `OBL-ELECTRICAL-THERMAL-SAFETY-001.C8` |
| Time each protective device takes to clear, and the energy it lets through, at that fault current | **Pending** — a characteristic of the device fitted, read from that device's datasheet once it is chosen. Settled by the design task for each board, which the partition and feasibility task creates once the division between boards is chosen (`DEL-HW-PARTITION-AND-FEASIBILITY.C5`): it records, for the conductors its board carries, the clearing time and let-through of each protective device they rely on, and checks each conductor against them by calculation before layout, applying the board design method to its board. The board design method's pre-layout proof (`SOL-BOARD-PRE-LAYOUT-PROOF-AND-BRING-UP-PROVISION.C1`) defines that step but records no figure for this machine | — | — | `REQ-ELECTRICAL-INSTALL-001.C7` |

### Proof-of-life removal interval

The interval within which loss of the controller's proof of life must remove heater power. It is derived, not chosen, per `DEC-PROOF-OF-LIFE-INTERVAL-BOUNDED-BY-FIRST-PROTECTIVE-TRIP`. Each heater is taken fully on at the top of the declared span, starting from the highest temperature its casting reaches while the controller is holding it, across the plant model's declared corners, with the lower bound of its thermal mass. The interval is the time that heater takes to reach its retained protection's trip point, and the shorter of the two heaters sets it.

That starting temperature has not been derived yet, so the interval is pending.

| Figure | Value | Grade | Derivation | From |
|---|---|---|---|---|
| Proof-of-life removal interval | **Pending** — its starting point, each casting's peak temperature under control across the plant model's declared corners, is not yet derived. Settled by deriving that peak for each thermoblock from the plant model and then deriving the interval here from it, naming the heater that sets it: `SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED` (`.C1` the peak, `.C2` the interval) | — | The time for each heater, fully on at 253 V from its casting's peak under control and with the lower bound of its thermal mass, to reach its trip point; the shorter of the two | `REQ-SAFETY-CHAIN-001.C3`, `REQ-SAFETY-CHAIN-001.C2` |

The other inputs are settled, and are the ones the derivation will use:

| Input | Coffee thermoblock | Steam thermoblock | Grade | Source |
|---|---|---|---|---|
| Trip point | 107 °C | 195 °C | parts list | `reference-machine.md` § Protection: 110 °C ±3 and 200 °C ±5, each taken at the low end of its tolerance (`DEC-PROTECTION-TRIP-POINTS-FROM-PARTS-LIST-LOW-TOLERANCE-END`; accounted for as `CONTROL_PROTECTION_TRIP_C` and `STEAM_CONTROL_PROTECTION_TRIP_C` in `firmware/params/control.declaration`) |
| Element power at 253 V | 1215 W | 1362 W | inferred, from measured resistances | 253² / 52.7 Ω and 253² / 47.0 Ω (`reference-machine.md` § Heating and load) |
| Thermal mass, lower bound | 192 J/K | 216 J/K | inferred | `brew.thermal_mass_j_per_k` 320 J/K and `steam.thermal_mass_j_per_k` 360 J/K in `firmware/params/thermoblock.params`, each `@estimated` with a stated error of 0.4 of its value; lower bound = value × (1 − 0.4) |

Each of these, and what the arithmetic leaves out, errs toward a shorter time: each trip point is the low end of its tolerance, the power is taken at the element's cold resistance, which its rising resistance only lowers (and the steam element's 47.0 Ω is itself a lower bound), the thermal mass is its lower bound, and the arithmetic ignores both the loss to the room and the heat capacity of the water held in each block. The starting temperature is the one input that does not yet err that way, which is why the interval waits for it.

**Figures from the commanded temperature, which the casting's peak will replace.** Until the peak is derived, the only starting temperatures the graph declares are the highest the controller commands. They are shown here with the times they give, so the derivation has something to be checked against. They are not the interval. Each is an upper limit on its heater's time, which bounds the interval only from the side the interlock cannot use: an interlock timed to one of these figures could act after the trip it exists to pre-empt.

| Commanded temperature | Coffee thermoblock | Steam thermoblock | Grade | Source |
|---|---|---|---|---|
| Highest temperature commanded | 100 °C | 138.9 °C | inferred | Coffee: a brew target is refused at or above the saturation temperature `CONTROL_SATURATION_C`, accounted for in `firmware/params/control.declaration` and valued at `firmware/src/control/control.c:71`, so 100 °C bounds every admitted target from above. Steam: the loop has two phases, both declared `@estimated` in `firmware/params/steam_control.declaration`. While nothing is drawn it commands `ready-temperature-c`, 125 °C. During a draw it commands pressure instead, held inside a band whose top is `draw-pressure-ceiling-bar`, 1400 milli-bar. Converted through the declared saturation relation in `firmware/params/thermoblock.params` (`steam.saturation_temperature_c` 100 °C and `steam.pressure_bar_per_k` 0.036 bar/K), that ceiling is the higher of the two: 100 °C + 1.4 bar / 0.036 bar/K = 100 + 38.9 = 138.9 °C |

The times from the commanded temperature:

- Coffee: 192 J/K × (107 − 100) K = 1344 J; 1344 J / 1215 W = 1.1 s.
- Steam: 216 J/K × (195 − 138.9) K = 216 × 56.1 = 12 120 J; 12 120 J / 1362 W = 8.9 s.

Why these do not bound the interval from below, as the interlock needs: in both loops the casting runs hotter than the commanded figure, by an amount no declared figure fixes. The coffee loop drives the temperature of the water leaving the block, not the block itself, and the two are not a fixed offset apart (`firmware/src/control/control.h`). During a draw the steam loop drives pressure, and the block stands hotter than its measured pressure implies through the saturation relation, by the pressure the draw has cost the path (`steam.pressure_fall_bar_per_ml`, `@estimated`, in `firmware/params/thermoblock.params`). A casting that starts hotter starts nearer its trip point and reaches it sooner, so each time above is longer than that heater's real time, by an amount not yet known: an upper limit, not the interval. The coffee side shows how much that matters: it has 7 K between its commanded ceiling and its trip point, and each kelvin the casting stands above 100 °C takes 192 J/K / 1215 W = 0.16 s from its 1.1 s. Which heater sets the interval is likewise left to the derivation, because the two castings' excesses over their commanded figures are not the same.

Once derived, a measured thermal mass, a different trip point, or a change to what the controller commands or to the plant model's corners re-derives the interval; the basis does not change.

### Load currents

Each load's current while energised is stated in `component-specification.md` § What each switched load needs of its device, the *Carries continuously* column, from the measured element resistances in `reference-machine.md` § Heating and load. The values below are that table's, cited here, and a change made there governs. The loads are the retained devices of `DEC-DEVICE-RETENTION-BOUNDARY`.

| Load | Current at 253 V, the worst case | Grade | From |
|---|---|---|---|
| Coffee thermoblock element | 4.80 A | inferred, from a measured resistance | `REQ-MACHINE-CONFIGURATION-001.C6`, `REQ-POWER-BUDGET-001.C6` |
| Steam thermoblock element | 5.38 A, a ceiling | inferred, from a measured lower-bound resistance | `REQ-MACHINE-CONFIGURATION-001.C6`, `REQ-POWER-BUDGET-001.C6` |
| Coffee pump, steam pump | **Pending** — see the supply budget; settled in `SOL-HW-MACHINE-AS-FOUND-FIT-RECORD.C4` | — | `REQ-MACHINE-CONFIGURATION-001.C6` |
| Two solenoid valve coils | **Pending** — see the supply budget; settled in `SOL-HW-MACHINE-AS-FOUND-FIT-RECORD.C4` | — | `REQ-MACHINE-CONFIGURATION-001.C6` |

### Rail budgets

What the low-voltage rails must supply. The retained devices that draw from them are fixed by `DEC-DEVICE-RETENTION-BOUNDARY`: the gauge assembly with its stepper driver, the panel's indicator elements, the low-water indicator and the buzzer. The channel enumeration (`controller-io.md`) is what the controller and its front ends serve. No requirement criterion states a rail figure. The rails must serve every enumerated channel at once and leave the spare capacity `REQ-HARDWARE-HEADROOM-001.C2` asks of every interface in use.

| Figure | Value | Grade | Source and derivation |
|---|---|---|---|
| Rail budget, every rail | **Pending** — the controller, the drive stages and the supply that a budget is summed over are the forms the partition and feasibility task decides (`DEL-HW-PARTITION-AND-FEASIBILITY.C1`). Settled by the design task for the board carrying each rail's supply, summed over the parts the boards it feeds carry: `DEL-HW-PARTITION-AND-FEASIBILITY.C5`. The working design's budget, summed for the parts it chose, is in `controller-design/mains-inlet-protection.md` § 5 V supply, *Load* and *Worst case with datasheet maximums*. Many of its items are estimated, it stands only as long as those parts do, and it is not adopted here as a settled value | inferred (the working budget) | — |

### Sensing accuracy

The accuracy each sensing channel must hold is stated per channel in `controller-io.md` § Sensing channels, the *Accuracy* column, which names the declared figure each cell is read from. The boards' sensing front ends must not take a channel outside it, and must hold it with the switched loads operating (`REQ-ELECTRICAL-INSTALL-001.C8`). Bring-up measures it there (`DEL-HW-BRING-UP.C5`).

| Channel | Accuracy | Grade | From |
|---|---|---|---|
| Coffee thermoblock temperature | ±2 °C | inferred (`@estimated` at its source) | `REQ-MEASUREMENT-001.C1`, `.C4`, `REQ-ELECTRICAL-INSTALL-001.C8` |
| Steam thermoblock temperature | ±2 °C | inferred (`@estimated` at its source) | `REQ-MEASUREMENT-001.C1` and `.C4`, on the steam loop's own margin; `REQ-ELECTRICAL-INSTALL-001.C8` |
| Steam-path pressure | ±0.2 bar | inferred (`@estimated` at its source) | `REQ-MEASUREMENT-001.C8`, `REQ-ELECTRICAL-INSTALL-001.C8` |
| Steam wand temperature, flow meter | No accuracy is claimed for either channel anywhere in the graph, so none is imposed on the boards. The column records why no figure reaches them | — | `REQ-MEASUREMENT-001.C6` (flow resolution, stated in the same file's *Resolution* column) |
| Contact closures: tank level, knob microswitches, panel keys | Not applicable — two states, no continuous value | — | — |
| Mains zero-cross | Not bounded — the offset between a true crossing and a detected edge has no declared figure, and `DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM` declines to invent one | — | `REQ-MACHINE-CONFIGURATION-001.C4` |

### Inputs to the separation basis

The separation basis between mains-referenced and low-voltage circuitry is declared and signed for in the partition and feasibility task (`DEL-HW-PARTITION-AND-FEASIBILITY.C3`), which reads its distances from a published standard with the working voltage, pollution degree and material group stated. These are the inputs this graph supplies to it.

| Input | Value | Grade | Source and derivation | From |
|---|---|---|---|---|
| Working voltage | 253 V rms, 358 V peak | inferred | Top of the declared span, from the supply table above | `OBL-ELECTRICAL-THERMAL-SAFETY-001.C6` |
| What the barrier must survive | Any single insulation failure, under water, steam and repeated thermal cycling, without putting mains on anything a person or a low-voltage circuit can reach | inferred | Read from the two criteria named | `OBL-ELECTRICAL-THERMAL-SAFETY-001.C6`, `.C7` |
| Physical separation | Mains and low-voltage runs, terminations and the paths between them separated throughout | inferred | Read from the criterion named | `REQ-ELECTRICAL-INSTALL-001.C1` |
| Pollution degree the enclosure warrants | **Pending** — settled in declaring the separation basis: `DEL-HW-PARTITION-AND-FEASIBILITY.C3` | — | — | `REQ-ELECTRICAL-INSTALL-001.C2` |
| Laminate's tracking resistance (material group) | **Pending** — it sits at a material-group boundary. Settled in declaring the separation basis: `DEL-HW-PARTITION-AND-FEASIBILITY.C3` | — | — | `OBL-ELECTRICAL-THERMAL-SAFETY-001.C6` |
| Supply module's isolation rating | **Pending** — sources disagree (`DEL-HW-DESIGN-CONSTRAINTS.C2`). Settled by a reading of the manufacturer's current datasheet in the partition and feasibility task's choice of form: `DEL-HW-PARTITION-AND-FEASIBILITY.C1`. The isolation the module provided, and what it separated, belongs with the carried-forward module properties (`SOL-HW-MODULE-PROPERTIES-CARRIED-FORWARD.C1`); the rating itself is held here, once | — | — | `OBL-ELECTRICAL-THERMAL-SAFETY-001.C6` |

### Output failure states

Every output the boards drive fails into the safe state: not heating, not pumping, and not holding any output energised (`DEF-SAFE-STATE`). That includes reset, loss of the controller's supply, power-up before the pins are defined, and a cable between the boards or to a load's switch coming loose (`DEL-CONTROLLER-HARDWARE.C8`). The six mains loads' states are stated per load in `component-specification.md` § What each switched load needs of its device, the *Must fail into* column.

| Output | State it must fail into | Grade | From |
|---|---|---|---|
| Both heater switches | De-energised. A semiconductor switch's ordinary failure is a short, so the device alone does not give this. The proof-of-life interlock in series removes heater power within the proof-of-life removal interval above (pending), whatever the switching device does (`component-specification.md` § The regression this specification makes visible) | inferred | `OBL-ELECTRICAL-THERMAL-SAFETY-001.C2`, `REQ-SAFETY-CHAIN-001.C2`, `.C3` |
| Both pump drives | De-energised | inferred | `OBL-ELECTRICAL-THERMAL-SAFETY-001.C2`, `DEF-SAFE-STATE` |
| Both valve coils | De-energised. For the two-way valve this is also its open-to-drain, venting state (`reference-machine.md` § Protection, owner statements dated 2026-10-11) | inferred; the venting state is owner statement | `OBL-ELECTRICAL-THERMAL-SAFETY-001.C2`, `DEF-SAFE-STATE` |
| Panel indicator lines and anode rail gate, low-water indicator, buzzer, gauge driver lines | De-energised | inferred | `DEF-SAFE-STATE`, `DEL-CONTROLLER-HARDWARE.C8` |

### Pending marks

Every pending mark in this section, with the work that ends it.

| Pending figure | Settled by | Node |
|---|---|---|
| Supply module's isolation rating | A reading of the manufacturer's current datasheet, in the partition and feasibility task's choice of form | `DEL-HW-PARTITION-AND-FEASIBILITY.C1` |
| Laminate's tracking resistance (material group) | Declaring the separation basis | `DEL-HW-PARTITION-AND-FEASIBILITY.C3` |
| Pollution degree the enclosure warrants | Declaring the separation basis | `DEL-HW-PARTITION-AND-FEASIBILITY.C3` |
| Why the original board takes two live feeds, and what protects each | Tracing each live feed in the machine-as-found record | `SOL-HW-MACHINE-AS-FOUND-FIT-RECORD.C3` |
| Valve coil current | Recording what each retained device imposes on its driver | `SOL-HW-MACHINE-AS-FOUND-FIT-RECORD.C4` |
| Pump current | Recording what each retained device imposes on its driver | `SOL-HW-MACHINE-AS-FOUND-FIT-RECORD.C4` |
| Rail budgets; the low-voltage supply's mains input, feed protection and output limit; the pump-branch and valve-branch fuse ratings | The design task for the board that carries each, once the partition and feasibility task has decided each function's form (`DEL-HW-PARTITION-AND-FEASIBILITY.C1`) and, for the fuses, once the coil and pump currents above are recorded | `DEL-HW-PARTITION-AND-FEASIBILITY.C5` |
| Proof-of-life removal interval | Deriving each thermoblock's peak casting temperature under control from the plant model across its declared corners, then deriving the interval here from that peak | `SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED` |
| Each protective device's clearing time and let-through at the prospective fault, and each conductor checked against it | The design task for each board, created by the partition and feasibility task, applying the board method's pre-layout proof to that board before it is ordered (the method itself only defines the step) | `DEL-HW-PARTITION-AND-FEASIBILITY.C5` |
