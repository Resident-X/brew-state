# Controller boards: the division of the circuitry and the floorplan of each board

**This file is local, like `controller-board-function-forms.md`, which it sits beside.** It gives every function that record gives a form to one board or one off-board assembly, with the reason; compares three ways of dividing the circuitry between boards and says which the comparison supports; draws a dimensioned block-level floorplan of each board against the enclosure as found; and records where each retained harness lands, where the proof-of-life interlock sits and what carries mains as a result, and where each anticipated channel kind is given room or why it is not. An adopter fitting a different machine replaces this file along with the records it is derived from.

## Owner intent carried in

Each row is a statement the owner made that shaped this record: what they said, when, what it changed in the division, and the section that holds the consequence. A later reader should not have to rediscover any of it from the sessions that produced it. The dates are 2026 and the statements are quoted short or paraphrased.

| Statement | Date | What it changed in the division | Where this record holds it |
|---|---|---|---|
| A board need not be a rectangle; an elbow that wraps round another board is allowed | 2026-10-12 | The outline is stored as a polygon and checked as one; division B's mains board carries a bay for the module's DC end; the narrow elbow controller board was weighed and dropped for want of fixings | § The owner's starting points; § Candidate divisions; the outline in § Appendix |
| Hand-solder only the parts that drive assembly cost; the tank reed is fitted by hand and left off the order | 2026-10-12 and 2026-10-19 | The reed is not counted in the manufacturer's assembly and has its hand access marked; the through-hole parts that raise the cost are priced as hand-fitted | § The tank reed; § What the owner fits by hand |
| The extended-part fee against hand-sourcing the parts: "if reasonable I might just pay" (2026-10-23), then decided: the owner hand-solders the through-hole parts that drive the assembly cost, and the manufacturer assembles only the surface-mount parts | 2026-10-25 | The main board's baseline is the manufacturer's assembly of its surface-mount parts alone, five Extended types; the other fourteen Extended types are bought and fitted by the owner, and the record states the fee, what hand-fitting avoids and what it saves | § What the owner fits by hand |
| Heater switches go at the bottom next to the pumps, with a cut through the side plastic that bonds the heat plate to the metal wall | 2026-10-04 | The two heater triacs are on an off-board wall board bolted to the machine's metal wall | § Every function has one owner; § The heater wall board |
| Same connectors, so each harness replugs straight in, with extra connectors for new sensors | 2026-10-12 | Every retained harness has a header of its own plug family, pitch and pin-1 orientation; the anticipated sensors have headers | § Every retained harness reaches its connector; § The anticipated channel kinds |
| A measurement of heater power, voltage, frequency and total current may be wanted, to detect a runaway and to calibrate over temperature; show the allocation first and remove kinds by priority | 2026-10-12 | The kinds are all given a place first and removed in a stated order, by arithmetic; the total supply current has a shunt in the neutral return, read through the voltage measurement's isolating part (as of 2026-10-24); frequency is read from the one timing front end | § The anticipated channel kinds |
| The zero crossing is one measurement on one board, shared by all | 2026-10-12 | `TIMING` and `IN_COND` serve every channel and both crossings; no second zero-crossing circuit is drawn | § Every function has one owner; § The anticipated channel kinds |
| A spare analogue input is wanted, and the steam transducer's connector is to be shared with it or split from it | 2026-10-12 and 2026-10-23 | A spare analogue header and circuit; the transducer's digital header and the analogue spare are two connectors | § The anticipated channel kinds |
| The original harness reaches only the original tab, so heater current comes out of the enclosure from that tab, and a small copper bridge goes out to the wall board and back | 2026-10-24 | First drawn as the element leads staying on tabs 4 and 5 with a piggyback terminal each and a wire out from it, and the return coming back to a piggyback on tab 3. **Replaced the same day** by the first and second rows after the one on the logic supply module (tabs 4 and 5 removed, in-line blade joiners, a landing for the return) | § The path of the heater current |
| The wall cut is accepted, kept as small as the passage needs; how the wall board is supported is decided later, in its own design task | 2026-10-24 | The least opening was stated for the owner to confirm (D11), which the owner accepted as preliminary on 2026-10-28 (the row below that starts "The owner accepted the wall cut as preliminary"); no support is fixed here, only the distances a support must give | § The heater wall board, *The wall cut, and the owner's acceptance* |
| The owner asked why the wires need to touch the wall and said "The wires will be going from the cavity next door the other direction or from above. I'll just route them where needed."; the owner asked whether the triacs are through hole soldered to the board and not extended on wires ("I assume the triacs are through hole soldered to the board right? You aren't talking about extending the triacs via wires right?", a question and an assumption, not an assertion); the owner said of the wall cut "It doesn't really matter right now, this is the easiest board to reconfigure to another dimension like wider and shorter", and later "Probably not that big, but I'm not convinced it needs to be that big", wanting a preliminary design of the whole board now with the board's dimensions rearranged later if need be; no acceptance of the cut size is given in these statements, the owner's acceptance as preliminary coming later the same day (the row below that starts "The owner accepted the wall cut as preliminary"; grade: owner statement, as said and no more) | 2026-10-28 | The record's reading, not the owner's words: the owner routes the conductors where needed, so no conductor is taken to cross the machine's wall and no passage is drawn; the owner's question takes through-hole soldering, with the leads straight into the pads, as the intended form; the board standing perpendicular to the wall, the heat spreader (the bracket's standing leg) lying parallel to it and the triac tab faces bolted to it are the record's reading of the drawn design. The wall cut is the window alone, 2400.0 mm² in one place (30.0 mm tall by a provisional 80.0 mm long), with no passage, and the opening in the plastic that admits the unit is 89.0 × 45.0 mm = 4005.0 mm²; the 79.8 mm² passage and the 14.5 × 5.5 mm size recorded earlier were an assumption of this record and not an owner statement, and are withdrawn; the three element conductors are the owner's to route and are unmeasured; the owner's acceptance of the cut as preliminary is the row below that starts "The owner accepted the wall cut as preliminary" (D11) | § The heater wall board, *The wall cut, and the owner's acceptance*; § The heater wall assembly, judged, *The element harness* |
| The bracket is the heat spreader, an L bracket that both holds the PCB rigid for installation and spreads the triacs' heat ("It doesn't have to be this, just seemed easy."); about 25 to 30 mm of height is available for it ("maybe 25-30mm"), and the owner asked for the least length of wall cut at 25 mm tall that gives good heat performance ("a wall cut of 25 X what ever is the minimum that gives us good heat performance is what I need to know"; the length table of § The heater wall assembly, judged, answers it, and the answer is the record's); the owner later said that the owner will tell a heat spreader maximum and build to that size, which the owner has not yet measured ("I'll tell you a heat spreader max, we will build to that size"; "if later we need to limit max dual power time, fine"); both heaters will likely only ever be on at full power together for about 2 minutes at most, then maintain temperature at much lower power, the idle draw unknown ("we haven't built our system yet"); about 80 mm is available perpendicular to the wall (an estimate, unmeasured); the wall is the external steel and an internal plastic layer that the owner will cut through and mount the spreader into, with perhaps 5 mm between them (unmeasured; replaced the same day by about 10 mm, the next row); the aluminium spreader is screwed with thermal paste to a stainless steel wall 2.5 mm thick that is the side of the machine, the entire side and not just the spreader's patch; the owner said "the 70 is in the controller are, not where this wall board sits. That will basically be ambient room, maybe we say 45 for some heating on a hot day" (grade: owner statement, as said and no more; the aluminium, the paste, the stainless steel and its thickness are the owner's, and the aluminium's properties, the steel's conductivity and the paste's resistance are stated figures of this record; the operating profile is an expectation, not a requirement, and nothing enforces it; the 45 °C is a working figure, not a measurement) | 2026-10-28 | No separate spreader beside the window is drawn; the bracket's standing leg is the spreader, its window 30.0 mm tall and 80.0 mm long as a provisional drawn default (the owner's later estimate, the next row) until the owner's measured maximum length replaces it (D11); the wall assembly is judged at 45 °C and, as the conservative case, 70 °C | § The heater wall assembly, judged, *The heat*; § The heater wall board, *The wall cut, and the owner's acceptance* |
| The owner could probably mount an 80 × 30 to 35 mm spreader ("I could probably mount an 80 x 30-35 mm spreader"), and the distance from the cut plastic wall to the stainless mounting surface is approximately 10 mm, replacing the earlier estimate of perhaps 5 mm (grade: owner statement, as said and no more; both are estimates from drawings of what the owner thinks is behind the wall, unmeasured, and the owner finds out the real figures when cutting) | 2026-10-28 | The standing leg is drawn 80.0 mm long and 30.0 mm tall, the low end of the owner's 30 to 35 mm, and the window is 30.0 × 80.0 mm = 2400.0 mm², as provisional drawn defaults held as data values (`window_l`, `top_z`) that the owner's measurement replaces (D11); the 35 mm height is carried as the other choice with its own table row; the gap to the stainless is carried as about 10 mm, an owner estimate, unmeasured; the 80 × 30 to 35 mm is the spreader, not shown to be the opening in the plastic that admits the unit, which is 89.0 × 45.0 mm = 4005.0 mm² and is the owner's open measurement and decision (D11) | § The heater wall board, *The bracket*, *The wall cut, and the owner's acceptance*; § The heater wall assembly, judged, *The heat*, *Owner measurements* |
| The owner accepted the wall cut as preliminary, to be revisited when the owner cuts and measures: the operator offered the option 'Accept the cut as preliminary: you would say something like "accepted as preliminary, to be revisited when I cut"' and the owner replied "Do 1", which chose it; earlier the same day the owner had said the cut size "doesn't really matter right now" and wanted a preliminary design of the board itself with the board's dimensions rearranged later if need be (grade: owner statement, as said and no more) | 2026-10-28 | D11 is decided and leaves the pending list, its number not reused. The figures accepted as preliminary are the provisional ones: the window 30.0 × 80.0 mm = 2400.0 mm² in one place and the opening in the plastic that admits the unit 89.0 × 45.0 mm = 4005.0 mm². This is not an acceptance of a final size: the owner's measured maximum spreader and the real opening replace the figures when known, and the board's dimensions are rearranged then. The acceptance is recorded in the graph as evidence for the wall-cut criterion by the operator; the script holds the acceptance wording and the figures together and cannot prove the acceptance exists | § The heater wall board, *The wall cut, and the owner's acceptance*; § The heater wall assembly, judged, *The wall cut: the reason for the larger cut*, *Owner measurements* |
| Off-board means not installed in the enclosure with the boards; it may be made as a section that snaps off one of them | 2026-10-24 | The definition used for every owner of a function; the wall board's own board and break-away forms are both costed | § Every function has one owner; § The heater wall board |
| The wall board may be a break-away section whose cost is shared in the panel | 2026-10-24 | Costed against its own board, with the saving stated; the record keeps its own board and leaves the choice open (an owner decision pending, § Owner decisions pending, D9) | § The heater wall board |
| Mains and low voltage may share a board, with the creepage held on the board | 2026-10-24 | Division A, one board, holds the signed 3.0 mm clearance and 10.0 mm creepage by distance and by milled slots | § Zones and the barrier; § Candidate divisions |
| Compare one board of about the enclosure's width that meets the mounting points against two or three boards | 2026-10-24 | The three candidate divisions A, B and C with their costs, fixings and fit | § Candidate divisions |
| 1 oz copper is a cost matter and depends on the current each path drives | 2026-10-24 | Both boards are 1 oz, the heater path is wide pours, and where 1 oz cannot carry a path, 2 oz and off-board wiring are weighed | § Layer counts, *Copper weight*; § Copper that carries the heater current |
| The lid screws at points 1 and 2 are required | 2026-10-24 | The board is held at all four points, the lid screws at points 1 and 2 among them; the four tabs nearest the fixings, three at point 1 and one at point 3, move to clear the fixing rule | § The fixing rule and the tabs that move |
| The board is held at all four of the machine's mounting points as the original is, with a screw and a hole at point 3 as at the other three | 2026-10-26 | A hole at point 3, drawn as the other three are; mains copper keeps 13.25 mm from its centre; tab 9 moves down 1.9 mm to meet it. An earlier version of this record read an owner decision of 2026-10-24 of no screw and no hole at point 3, the board resting on the boss; the owner did not decide that, and the reading is withdrawn | § The fixing rule and the tabs that move, *Point 3* |
| Mains copper on the wall board stays at least 5.0 mm from the edge that lies against the metal wall | 2026-10-24 | Every mains rectangle of the wall board, and every part body and mains lead end, stands 5.0 mm in from the wall edge, which keeps the 4.1 mm basic creepage of the basis's interpolated row (4.0 mm at 250 V and 5.0 mm at 320 V, 253 V working voltage) with 0.9 mm in hand, applied to an earth bond that the basis says is not measured; the wall-to-copper barrier is reported as one the basis does not list. The same row's reading of the triac leads bent and the board standing off the wall on plastic standoffs is replaced by the next row | § The heater wall board, *Mains copper and the metal wall* |
| The heater triacs stand on a right-angle heat-spreader bracket, one leg fixed to the board by two mounts and the other bolted to the metal wall, so that the board and the triacs are fitted and removed as one unit with no lead bent, folded or re-bent; this replaces the owner row of 2026-10-24 that read the triac leads bent and the board standing off the wall by at least 5.0 mm on plastic standoffs | 2026-10-26 | The bracket, its two mounts on two ears of the board, its lift, the order of fitting and removal, the wall cut recomputed for its leg; the 5.0 mm standoff, its assumption and the statement that no metal fixing joins the board to the wall are withdrawn | § The heater wall board, *The bracket* |
| The relay's contact heat is budgeted at 0.5 W at 10.18 A with the coil at its full drive, and bring-up measures the closed-contact drop at about 10 A | 2026-10-24 | Contact heat is stated as an assumption beside the datasheet's unsourced worst case; the relay has a heat row; the coil is fed only through the proof-of-life path, with nothing that keeps it above drop-out beyond the removal interval after proof of life stops, and bring-up records the coil below 0.5 V in each rest state of the controller | § The interlock block, *The coil's feed*; § Heat |
| Whether the interlock relay needs a reduced-hold coil drive was left to this record | 2026-10-24 | Dropped: by the record's own estimate the drive saves nothing (0.98 W at the full drive against 1.01 W held, since the contact heating at about 10 A dominates and rises as the coil force falls), and a hold stage with storage of its own is a latch risk against the proof-of-life requirement; the requirement that the coil is fed only through the proof-of-life path stays | § The interlock block; § Options considered and dropped |
| The master interlock relay goes on the main board, in the `LINE` to `LINE1` link, so that it cuts the live feed of every load, heaters, pumps and valves, and not the heaters alone; the owner asked why it was not there, was told the reasons given in this row and in § Options considered and dropped, and approved | 2026-10-24 | `K_IL` moved from the wall board's common return to the main board; the wall board lost the relay, its coil pocket and the coil conductors of its low-voltage cable; the main board's mains column was re-ordered to put the relay between tabs 1 and 2; the logic supply and the timing front end are fed from `LINE` and `NEUTRAL` upstream of the contact so that the controller keeps power when it opens; the reserved valve position (kind 6) was not kept for want of room, and the owner has since removed it by choice (rows below). **The reasons it moved:** in the common return it cut the two heaters only, while the pumps and the valves keep their live feed from `LINE1` by the retained daisy-chain wires; `LINE1` is the one conductor of the main board from which every load's live lead is fed, so one relay in its link cuts them all; and the coil no longer needs a conductor across the cable to the wall board. **That every load's live lead is fed from `LINE1` rests on the owner's visual trace, not on a measurement, and bring-up checks it by continuity** (§ Reported for the board design tasks, item 32) | § The heater path, the interlock and the wall board; § The main board's floorplan, *The mains-side blocks*; § The anticipated channel kinds, kind 6 |
| The 70 °C enclosure air is probably not real: the owner expects to insulate the thermoblocks | 2026-10-24 | 70 °C stays the assumed figure for every grade and distance, said plainly, and the 5 V rail is also sized at 50 °C; bring-up replaces both, and the relay choice is not proven until the bring-up measurement of its body | § What the division is weighed against; § Heat; § The logic supply against this board; § The interlock block |
| The tab slack of about 10 mm is the owner's estimate; accept what is left once the fixing rule is met | 2026-10-24 | The margin rule (3.0 mm extent, 0.25 mm drawing tolerance, 13.25 mm to every hole centre) is an obligation on the board design task; the four tabs move 6.9, 7.0 and 7.5 mm up and 1.9 mm down and leave 3.1, 3.0, 2.5 and 8.1 mm of the slack (the first three moved 9.7, 9.3 and 9.3 mm and left 0.3, 0.7 and 0.7 mm while every pad was drawn a 7.0 mm square); the owner measures the real slack of each lead with a rule before ordering | § The fixing rule and the tabs that move |
| All nine tab blades stand with their wide face parallel to X, along the bottom edge | 2026-10-24 | A tab's pad is the blade's section with an annulus, 7.0 mm along X and 1.45 mm along Y, and not a 7.0 mm square; the cut-back of the two pads either side of the open interlock contact is gone; every distance that rested on the square (the gaps between pads, the distances to the fixings, the tab positions, the slack left, the tab strip and the link copper) is recomputed | § The fixing rule and the tabs that move; § Zones and the barrier |
| Heater current sensing may sit on the wall board, or at the common feed on the mains board for the total current | 2026-10-24 | First drawn on the wall board, in the common return, with an isolated output on the wall board's low-voltage cable. **Replaced the same day** by the owner's measurement-set row below (one sensor for the total current, the wall board's dropped) | § The anticipated channel kinds, kind 9 |
| The tallest part on the original board is the AC/DC module, measured at 28 mm | 2026-10-24 | The ceiling the record already used stands: 27.9 mm in the interior and 23.3 mm within about 2 mm of a wall | § What the division is weighed against |
| The tank reed was remeasured: its lower lead is 15.3 mm above the original board's bottom edge and 121.25 mm from its left edge | 2026-10-24 | The reed's lower lead is at the recorded (122, 17.5) and its upper lead 20 mm above, midpoint (122, 27.5); the earlier hand-access rectangle was dropped for a body strip and a radius round each pad | § The tank reed |
| The original board measures 133.2 × 125.1 mm (±0.2, perhaps not exactly square) | 2026-10-24 | This record's outline stays X 1.0 to 132.0, Y 2.0 to 127.0 (131.0 × 125.0 mm): the datum is the cavity wall and the original board's own edges are inferred, not measured | § The main board's floorplan, *Outline, fixings and margins* |
| The interlock relay is to stand at least A8's 15 mm from the logic-supply module, and A8 applies to the relay as a heat source of about 1 W against every part that derates | 2026-10-24 | The relay dissipates 0.98 W, or 1.03 W with its coil at the low end of its tolerance, so it is a source in A8's own terms; the module stands 20.0 mm from its body and the voltage measurement, an 85 °C part, 15.0 mm from it, directly below the module; the two sensing blocks within 20 mm of it (`BREW_A_C`, `PT1_C`) moved right, and the analogue region holds its blocks with kind 5 in it at the spacing the drawing keeps (the earlier record's 1.5 mm gap had it over capacity until kind 5 was removed; see the measurement-set row below); the module moved up 3.3 mm and the microcontroller block is drawn at its estimate to stay 15.0 mm from it; of the five mains-side parts rated to 85 °C two hold 15 mm from both sources and three do not, with the arithmetic of why | § Heat; § The anticipated channel kinds |
| The spare valve relay place, kind 6, is not wanted | 2026-10-24 | Kind 6 is recorded as **not reserved by the owner's choice (2026-10-24)** and not for fit; no criterion is named, because none is weakened; its block, its tenth tab and the step of the removal order that held it are gone | § The anticipated channel kinds, kind 6 |
| The valves do not need a 20 A relay: their coils draw 0.129 A steady and 0.203 A at inrush together | 2026-10-24 | `K_V1` and `K_V2` are the Hongfa HF32FA-G/005-HSL1 (17.6 × 10.1 × 12.7 mm, 5 V coil, 10 A contacts, 1.61 USD) in place of the HF115F-Q (3.21 USD); `K_IL` stays the HF115F-Q, which carries 10.96 A | § The valve relays; § The mains-side blocks |
| Relay contacts rated 250 V AC as their maximum switching voltage are accepted at the 253 V top of the span (1.2 % over), because the supply voltage is measured and the control can refuse to run well above the span; blocking the 358 V peak while off and the reinforced coil-to-contact isolation still apply, and a semiconductor switch is not covered | 2026-10-24 | The 250 V part is allowed for the valve relays; the constraints record carries the acceptance in *Rated for the supply* and the script reads it from there; this record checks the open-contact rating against 358 V and the coil-to-contact rating against the 4.0 kV target | § The valve relays |
| The supply voltage is measured, and the control refuses to run well above the span; the refusal threshold is a control-design number above 253 V (260 V is an example) and is not 250 V, since the grid can exceed 250 V | 2026-10-24 | Kind 1 is **required**, not anticipated: `REQ-MEASUREMENT-001.C10` makes the supply voltage that sets heater and pump delivery known to the control to a declared accuracy, and one measurement serves that and the cut-out. It is given an isolated measurement `VMEAS` at the zone boundary and a conditioning block `VM_C`; the accuracy is declared by the sensing task (`DEL-SENSOR-NECESSITY-PROVEN.C2` computes how necessary it is) and the threshold by the control design, and neither is set here | § The anticipated channel kinds, kind 1 |
| Both weight channels are kept; weight is last to go | 2026-10-24 | Kind 2 keeps both load-cell channels and stands last in the removal order; its footprint is redone with real parts (an HX711-class SOP-16 amplifier, five passives, a 5-way header) and the regions are redrawn, since the header strips and the analogue region were zones this record drew and not physical limits | § The anticipated channel kinds |
| The pumps are 48 W and 22 W on their nameplates | 2026-10-24 | The sizing currents 0.46 A and 0.19 A at 253 V stand (the constraints record carries them as the sizing values, the nameplate voltage's square-law scaling of the running current; its assumed power-factor floor of 0.5 on the nameplate power at 253 V gives the smaller 0.379 A and 0.174 A, which are not used); they are the pump part of the 10.96 A behind `K_IL`, of the 5 V rail's relay and drive loads, and of the shared-fuse proposal | § The interlock block; § The fuses |
| Is a smaller logic-supply module enough, and could one fuse serve the pumps? | 2026-10-24 | Asked, not decided (owner decisions pending, § Owner decisions pending, D5 and D6). The module stays the IRM-20-5: the smaller IRM-10-5 has 1.06 times this board's 5 V load at 70 °C against the 2.0 the forms record calls adequate, and 2.13 times at 50 °C. The fuses stay as `DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE` arranges them, and one shared fuse is put to the owner as a decision pending (§ Owner decisions pending, D5) | § The logic supply against this board; § The fuses |
| The main board's tabs 4 and 5, the element lead landings, do nothing now that the mains-presence confirms are on the wall board and no heater current runs through board copper there: remove them. The retained element leads keep their female terminals and plug onto in-line insulated male-to-male 6.3 mm blade joiners placed by the owner, strapped or clipped to something, and a new wire runs from each joiner to the wall board's blade terminals `OUT_S` and `OUT_C`. The wall board's return comes to a dedicated pad on the main board tied to the `NEUTRAL` copper, not to a piggyback crimp | 2026-10-24 | Tabs 4 and 5 are gone and the main board keeps seven harness tabs (1, 2 and 3 moved; 6 to 9 as found); the `STMHEATER` and `COFHEATER` leads are not changed (nothing cut, lengthened or re-terminated) and meet a joiner where they met a tab; the return lands on a landing that takes the tab part's own blade, beside tab 3, in a 7.0 mm pour of `NEUTRAL` that the heater return crosses; the pads' hold-out rules and the 8.0 mm channel kept for their leads are gone | § The path of the heater current; § Every retained harness reaches its connector; § The heater wall board |
| Use the freed left-edge room: move the voltage measurement `VMEAS` there, away from the interlock relay's heat; put one current sensor in the `LINE` to `LINE1` link beside the relay's contact end (13 × 8 mm and 48 mm² of conditioning), sensing the total supply current, 10.96 A with every load on, and drop the heater current sensor from the wall board so that no isolated signal crosses the cable; frequency stays from the zero-cross front end, voltage from `VMEAS`, current from the link sensor. Re-attempt the 85 °C layout the room might allow, and report whether kind 5 fits again | 2026-10-24 | The three measurements and their interfaces are stated (§ The anticipated channel kinds, *Voltage, frequency and total current*). **Two of the placements do not hold under this record's own rules and are drawn differently, for the owner to confirm (owner decisions pending, § Owner decisions pending, D3 and D4).** The 13 × 8 mm isolated sensor cannot stand in the link (its low-voltage pocket has no exit, and its length needs the relay moved 3.0 mm, which costs 85.2 mm² of the analogue region), so the total current is sensed by a shunt in the `NEUTRAL` return at tab 3's pad, which carries the same current, and read as a second channel of `VMEAS`'s isolating part; and `VMEAS` stays under the module, because the pocket of a barrier part must stand at the zone boundary. Kind 5 fits, with 123.0 mm² of the analogue region to spare at the spacing the drawing keeps (the region's top edge is also corrected from Y 30.1, where the module once stood, to Y 31.0); the 85 °C parts hold no better than before, with the arithmetic of why in § Heat | § The anticipated channel kinds; § Heat; § The path of the heater current; § Options considered and dropped |
| The heater wall board is hand-soldered by the owner, so its size and its part count are to be minimal ("less is more": fewer parts to get wrong, and a smaller board) | 2026-10-24 | The board's body is 57.0 × 42.5 mm = 2 422.5 mm² and, with the two mounting ears of the bracket, 2 662.5 mm², with 39 hand joints and five Extended types (the triac, the opto-triac, the blade terminal, the header and the varistor): the sensor, the two confirms and the two snubbers are gone, the header is three ways, and the gate network is counted from the maker's figure | § The heater wall board; § What the owner fits by hand |
| Drop the two mains-presence confirms from the populated board on the condition that the sensing design (the supply current, and each heater's resistance modelled over temperature and calibrated one at a time: 4.80 A coffee against 5.38 A steam, with the pumps and valves adding about 0.8 A) resolves a stuck-on triac, a triac that fails to close and an open element; if it does not, they go back. Keep the places unpopulated only if the board stays at the minimal outline, with the unpopulated pads' copper held to the separation rules as if fitted; the main board's confirm inputs stay reserved and the cable keeps its spare ways | 2026-10-24 | **The condition is only partly met, so whether the confirms stay off the board is an owner decision pending (§ Owner decisions pending, D2).** They are left off the drawn board for now, the owner's wish for a minimal board that is hand-soldered, on a condition that is met for a stuck-on triac and for "no heater current when commanded" and **is not met** for telling a triac that fails to close from an open element, which the supply current cannot tell apart; both give the same safe response (the heater power removed or held off). **Recommendation: keep them dropped and revisit when the sensing task proves the current check.** Putting them back costs two places of two parts each (four parts), 12 hand joints and a board 23.5 % larger (57.0 × 52.5 mm, 2 992.5 mm²), checked as a second layout; `IN_COND`'s two inputs stay reserved | § The heater wall board; § Reported for the board design tasks, item 29 |
| The board as found switches the neutral side of every load, so a confirm across an element's switched lead and the neutral reads on when the switch is open and off when the triac conducts; the forms record's wording and its leakage bound seem to assume a live-side switch | 2026-10-24 | The polarity is stated (stuck-on reads off while commanded off, failed-to-close reads on while commanded on, an open element reads off), the forms record's bound of about 22 nF on the snubber capacitor is re-derived for this topology (it falls away), and the departure is entered in the table of disagreements; the forms record is not edited | § The heater wall board, *The mains-presence confirm*; § What this record's words depart from in the forms record |
| The pump drives carry no snubber and no varistor: say so plainly and why, check them against the EMC and surge criteria and against the turn-off voltage of an inductive vibratory pump, and say so if the check cannot be closed from sourced figures | 2026-10-24 | Stated, with the check; it cannot be closed from sourced figures and is an open item for the design task | § The pump drives |
| None of the four fixings can be touched: points 1 and 2, the lid screws, are recessed deep in a slot in the lid, and points 3 and 4, which carry no lid screw, are inside the closed case behind another panel | 2026-10-24 | Nothing in the geometry: the 10.0 mm mounting-hole rule applies as written to every fixing. The owner's choice between moving the four tabs 6.9, 7.0 and 7.5 mm up and 1.9 mm down (3.1, 3.0, 2.5 and 8.1 mm of slack left) and amending the rule for fixings that cannot be reached is an owner decision pending (§ Owner decisions pending, D1) | § The fixing rule and the tabs that move |
| Could tabs 1 to 3 be re-ordered now that tabs 4 and 5 are gone? | 2026-10-24 | No: the order stays (`LINE1`, `LINE`, `NEUTRAL`), because a re-order would need about 18 mm more lead reach against the owner's slack of about 10 mm (the figures of that discussion, not recomputed here); the owner measures the real lead reach if a re-order is wanted | § The fixing rule and the tabs that move |
| The owner proposed to carry the fuse and a varistor on the main board at the mains entry, at tabs 2 and 3, the varistor hard against the fuse and downstream of it, in place of the appliance inlet | 2026-10-24 | Decided by the owner (the proposal was owner decision D16, and where the entry assembly was mounted was D14; both are withdrawn from the pending list) | § The fuses |
| The machine keeps its existing fixed mains lead: no appliance inlet, no [earlier design: bought inlet filter] and no [earlier design: mains-entry assembly]; the fuse and the varistor are on the main board, and emission suppression is decided there (an X2 capacitor, no choke; § The fuses) | Decided by the owner | The mains entry's function is owned by the main board and the off-board assemblies are two, the heater wall board and the steam-path assembly; `DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE` is amended to it; the entry fuse holder and the varistor are drawn at tabs 2 and 3 | § Every function has one owner; § The fuses |

## Options considered and dropped

Each is an option this record weighed. The reason is the one that decided it, with the figure where there is one; the graph holds the criteria and this file holds the arithmetic. A figure marked *computed here* is printed by the script of § Appendix.

| Option | Why it was dropped, or left open |
|---|---|
| A narrow controller board along the right edge, possibly an elbow | It would carry points 2 and 4, which lie on one line 117 mm apart, and leave the mains side on a board with two fixings on one line, points 1 and 3 (§ Candidate divisions) |
| Division B, a mains board and a low-voltage board | Dearer by about 20 USD at block level (the board fee at an area other than 103 × 103 mm is inferred, so only the whole dollar is stated) and each board is held by fewer fixings than A12 asks |
| Division C, a three-board split | Dearer by about 21 USD at block level even with its two small boards at the lowest band's price; its controller board has no fixing of its own |
| No hole at point 3, the board resting on the plastic boss | Dropped: the original board is held at all four points, a rest supports but does not hold against lift (A12), and the owner did not decide it; the hole costs one tab a 1.9 mm move (§ The fixing rule and the tabs that move) |
| The wall board as a section that breaks off the main board | Saves 2.34 USD of fabrication and ties every respin of the safety-critical wall board to the four-layer main board's order; left open as the owner's choice (an owner decision pending, § Owner decisions pending, D9) |
| 2 oz copper for the heater return on the main board | 36.40 USD more at two layers in the lowest band and unmeasured at four; off-board wiring adds nothing to the board (an owner decision pending, § Owner decisions pending, D13) |
| **The heater return carried on main-board copper from the heater terminals to tab 3** (this record's earlier reading) | It would have needed 5.72 mm of 1 oz copper where the channel between the tab pads and the blocks leaves 5.0 mm; with tabs 4 and 5 gone the return lands beside tab 3 and crosses only a 7.0 mm pour, 8.5 mm long (§ The path of the heater current) |
| The wall board edge-on to the wall with its mains copper at the edge | The board does stand edge-on with the bracket, its wall edge flush with the bracket's outer face, and the mains copper at the edge is dropped: the signed basis gives no mains-to-metal distance for copper over a board edge, so the copper stays 5.0 mm in from the edge and the bracket stands 5.0 mm clear of it in three dimensions; the drawn 5.0 mm keeps the 4.1 mm basic creepage and no more is claimed |
| Holding 10.0 mm of copper to the wall edge | It would grow the board by 5 mm more for a distance the basis does not sign for mains copper to metal, where the basic creepage, 4.1 mm, is the figure it gives |
| A basic mains-to-earth pair signed in the basis | An amendment outside this slice; the wall-to-copper barrier is reported instead (an owner decision pending, § Owner decisions pending, D15) |
| The proof-of-life contact on a low-voltage signal line | A shorted triac bypasses it, so it does not remove power |
| **The interlock relay on the wall board, in the heaters' common return** (this record's first placement) | Dropped on the owner's approval of 2026-10-24 for the main board. It cut the two heaters and left the pumps and the valves live from `LINE1`; its coil needed a conductor across the cable to the wall board; and it put a 0.9 W part 10.0 mm from the steam triac (4.84 W) against A8's 15 mm, with the current sensor 12.0 mm from the coffee triac against 20 mm |
| **Spreading the triacs 4.0 mm and moving the sensor 7.2 mm** to hold A8 with the relay on the wall board | Dropped with the relay: the wall board would have grown to 95 mm wide and about 68 deep (the figures of the round-2 homework ruling, not recomputed here). With the relay gone the sensor stands 20.5 mm from the coffee triac on an 80 × 57 mm board |
| **Accepting the sensor 12.0 mm from the coffee triac against a restated A8** | No record holds a thermal model that would show 12 mm acceptable; the sensor is placed to the 20 mm instead |
| **The interlock relay in the top relay place of the main board**, level with the top of the stack where `K_V2` stands (the fallback) | The link from tab 2 to the relay and back to tab 1 would be two runs of 92 mm of 7.0 mm pour, 26.4 squares, 12.9 mΩ and 1.55 W at 10.96 A against the 0.5 W link budget (computed here); the re-ordered column puts the relay between tabs 1 and 2 instead |
| **A reserved fourth relay place, `K_SPARE`, for a further switched output (kind 6)** | Not kept: it was first lost for room (the bottom 14.5 mm of the stack holds the timing front end, which needs 13.0 mm between neighbours), and the owner then removed it by choice on 2026-10-24, so kind 6 is recorded as not reserved by the owner's choice (2026-10-24) (§ The anticipated channel kinds, row 6) |
| **A 7.0 mm square pad for every tab** (this record's earlier drawing) | The owner reads every blade with its wide face parallel to X, so a pad is 7.0 mm along X and 1.45 mm along Y, the blade's section and an annulus; the square left 1.3 mm between the pads of tabs 1 and 2 and again between those of tabs 2 and 3, and moved the three tabs nearest point 1 by 9.7, 9.3 and 9.3 mm against the 6.9, 7.0 and 7.5 mm they move now |
| **Holding every 85 °C part 15 mm from both heat sources, the module and `K_IL`** | The five mains-side parts rated to 85 °C (the valve relays, the pump opto-triacs and the voltage measurement's isolating part) need 55.2 mm along the barrier column and 31.1 mm of it stands 15 mm from both sources (computed here), so at most three fit there; counting every position of the module, every split of the parts above or below it and every order, three hold only if `K_V1` stands between the two sources, and the two arrangements built that do so each break a rule (§ Heat); the drawn stack holds two (`K_V2`, `P_S`) and reports `K_V1`, `P_C` and `VMEAS` as not held, each against the module |
| **`VMEAS` between the interlock relay and the module** (this record's earlier place) | It stood 4.0 mm from the interlock relay against A8's 15 mm, which the owner does not accept for an 85 °C part; it now stands directly below the module, 15.0 mm from the relay's body, which raised the module 3.3 mm and left the microcontroller block 31.1 mm of height to keep 15.0 mm from the module (§ Heat) |
| **`K_V1` between the interlock relay and the module, with `VMEAS` above the module** | It is the one family of arrangements that holds a third 85 °C part (`P_C`), and the two built here each break a rule: with the module at its lowest, no trace from tab 6 reaches the relay's contact copper keeping 5.0 mm from the other nets and `WT1_C` stands 18.3 mm from the module against A8's 20; with the module where it stood and the shared fuse in the gap beside the relay, no trace reaches the pad of tab 3 from the rest of the `LINE` and `NEUTRAL` copper (all computed here, § Heat) |
| The mains-presence confirm on the main board | It would put two barrier parts at the main board's boundary and two more mains conductors in the cable |
| One connector for the steam transducer shared with the spare input | It would put 5 V on the digital pair's connector (§ Every function has one owner) |
| **The 13 × 8 mm isolated current sensor in the link beside the relay's contact end** (the owner's placement of 2026-10-24) | Not drawn. Its primary is 8 mm long in the direction of the current and the room between the pad of tab 2 (right edge X 12.0) and the relay's contact copper (X 17.0) is 5.0 mm, so the relay would move 3.0 mm to the right; the three sensing blocks nearest it (`PT1_C`, `BREW_A_C`, `WT1_C`) would then stand 17.3, 17.0 and 17.0 mm from its body against A8's 20, and the analogue region would lose 85.2 mm² of capacity, 1 189.7 to 1 104.5 (56.8 mm² at 2.0 mm), all computed here. Its low-voltage pocket would stand in the pad column, where no pocket has an exit: every line from it to the low-voltage zone crosses the taps from `LINE` and `NEUTRAL` to the module's and the voltage measurement's pads, and the surface rules need slots the whole way |
| **A shunt in the link on the `LINE` side, read by a second barrier part** | Not drawn. The shunt (7.0 mm long) still does not fit the 5.0 mm between the pad and the contact copper without moving the relay; its reference is `LINE`, which is 253 V from the voltage divider's `NEUTRAL`, so one isolating part with two inputs that share a reference cannot read both; and a second barrier part needs another 5.0 mm of the boundary column, which has none to give (§ Heat) |
| **`VMEAS` moved into the left column the tabs 4 and 5 left** | Not drawn. It would stand 17.5 mm or more from the module and 15 mm or more from the relay, which holds A8, but its pocket would have no route to the low-voltage zone: the zone boundary is 44 mm away, the taps to the module's pads run up the same column, and a pocket that stands anywhere but the zone boundary needs 20.3 mm of clear width between mains copper or slots all the way (§ Heat) |
| **Piggyback terminals on tabs 3, 4 and 5 for the wall board's wires** | Dropped on 2026-10-24: once the confirms moved to the wall board the pads of tabs 4 and 5 did nothing and the heater current ran through no board copper there; the retained leads plug onto in-line joiners and the return has a landing of its own (§ The path of the heater current) |
| **A copper bridge on the main board for the heater current, out to the wall board and back** | Dropped with the two pads: the heater return crosses only the pour from its landing to the pad of tab 3 (§ Copper that carries the heater current) |
| **A heater current sensor on the wall board** | Dropped by the owner on 2026-10-24: one sensor reads the total current, and no isolated signal crosses the cable (§ The anticipated channel kinds, kind 9) |
| **The two mains-presence confirms populated on the wall board** | Dropped on the condition of 2026-10-24 (§ The heater wall board, *The mains-presence confirm*): 12 hand joints, one Extended type and about 220 mm² saved; they go back if the sensing design does not resolve the faults |
| **The confirm places kept on the wall board, not populated** | Not kept: they grow the board from 57.0 × 42.5 mm to 57.0 × 52.5 mm (+570 mm², +23.5 %), because four mains ends then fill the row, so the header can no longer stand in the middle of it and moves above them; the board price stays 4.00 USD in the band, and a respin to add them later costs about that. Whether they come back is an owner decision pending (§ Owner decisions pending, D2; § The heater wall board, *The mains-presence confirm*) |
| **A snubber across each heater triac** | Dropped on 2026-10-24: the load is resistive, so the commutating current falls at 2.4 to 2.9 A/ms against the 7 A/ms the triac's (dV/dt)c is rated at, with 0.11 to 0.14 V/µs of reapplied voltage against its 10 V/µs (§ The heater wall board, *Snubbers and varistors*); each is also a path around the open triac |
| **A re-ordered tab column** | Not drawn: a re-order would need about 18 mm more lead reach against about 10 mm of slack (the owner's figures of 2026-10-24, not recomputed here); the order `LINE1`, `LINE`, `NEUTRAL` stays |
| Leaving the supply voltage as a removable, anticipated kind | `REQ-MEASUREMENT-001.C10` requires the supply voltage to be known to the control, and the owner requires it: kind 1 is given a place and is not in the removal order (§ The anticipated channel kinds) |
| Standard assembly instead of Economic | Dearer at the 5 unique Extended types the manufacturer places, 57.84 against 25.06 USD; the two cross at 26 (§ What the owner fits by hand) |
| The earlier 11.1 × 29.0 mm reed hand-access rectangle | It had no source; replaced by a body strip and a radius round each pad |
| **A reduced-hold coil drive for the interlock relay (the economiser)** | Dropped on 2026-10-24: by the record's own estimate it saves nothing (0.98 W at the full drive against 1.01 W held, since the contact heating at about 10 A dominates and rises as the coil force falls), and a hold stage with storage of its own is a latch risk against the proof-of-life requirement (§ The interlock block); the coil is fed at its full drive only through the proof-of-life path |
| **The 20 A HF115F-Q for the valve relays** (this record's earlier choice) | Replaced on 2026-10-24: the valve coils draw 0.129 A steady and 0.203 A at inrush together, the 10 A contacts of the small relay carry them 78 and 49 times over, and the HF32FA-G/005-HSL1 is 17.6 × 10.1 mm and 1.61 USD against 41.0 × 12.7 mm and 3.21 USD (§ The valve relays) |
| **The valve relays level with their tabs, at X 17 to 58 mm** | A short relay there would have its coil end 31 mm in from the zone boundary, so a low-voltage trace from it would have to keep 10.0 mm from mains copper all round; the relays stand at the zone boundary, X 44.5 to 62.1, and their mains leads run 35 and 37 mm from the tab pads (§ The mains-side blocks) |
| **The IRM-10-5 as the logic supply** | 1.06 times this board's 5 V load at 70 °C against the 2.0 the forms record calls adequate; it would give 2.13 times at 50 °C, which is not measured, so the module stays the IRM-20-5 and the smaller one is the owner's to take up once bring-up has measured the air (an owner decision pending, § Owner decisions pending, D6); it would save 264 mm² (1 425 against 1 161) and 2.5 mm of height (§ The logic supply against this board) |
| **One shared fuse for both pumps, or for the pumps and the valves** | Not drawn: `DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE` fuses each pump branch on its own so that a fault in one does not stop the other, and the record keeps that arrangement; sharing is an owner decision pending (§ Owner decisions pending, D5; § The fuses) |
| **A 12 × 12 mm allowance for each weight circuit, and four header strips of 1 530 mm² of capacity** | Replaced: each weight circuit is drawn from the amplifier's sheet and A4 at 19.0 × 7.2 mm, and the regions are the rectangles the blocks are drawn in, 1 634.5 and 1 491.0 mm² with the gap counted (§ The anticipated channel kinds) |

## Owner decisions pending

**This is the one list of the decisions that are the owner's and are not made.** Each item gives the question, what this record draws meanwhile, and where the record holds the consequence; every other mention in this record points here, and nothing in this list is settled elsewhere. A decision the owner has made is in § Owner intent carried in; D10, the extended-part fee against hand-sourcing the parts (2026-10-25), D14, where the [earlier design: mains-entry assembly] is mounted, and D16, the fuse and a varistor on the main board in place of the appliance inlet (the machine keeps its mains lead; the owner's ruling is in § Owner intent carried in), and D11, the size of the wall cut, which the owner accepted as preliminary on 2026-10-28, to be revisited when the owner cuts and measures (the row of § Owner intent carried in that starts "The owner accepted the wall cut as preliminary"; its figures and consequences stay in the table below), are four of them, and their numbers are not reused. The script checks that each item is stated here with its words "Owner decision pending", that the section it concerns points to it, and that no other mention of a decision pending lacks the pointer.

**D1. The tab moves, or an amendment of the 10.0 mm fixing rule.** Owner decision pending: keep the moves of the four tabs nearest the fixings at points 1 and 3, tabs 1 to 3 up 6.9, 7.0 and 7.5 mm, which leave 3.1, 3.0 and 2.5 mm of the owner's 10 mm of lead slack, and tab 9 down 1.9 mm, which leaves 8.1 mm, or amend the 10.0 mm mounting-hole rule (`DEC-BOARD-PRE-ORDER-RULE-READINGS`) for fixings that cannot be touched, which the owner alone can do and which is outside this slice. None of the four fixings can be touched (the owner, 2026-10-24). *Drawn meanwhile:* the rule as written and the four moves; the exception is not taken. The owner measures the real slack of the four leads with a rule before the board is ordered. *Held in:* § The fixing rule and the tabs that move.

**D2. Whether the two mains-presence confirms come back onto the wall board.** Owner decision pending: the confirms are left off the drawn board (the owner's wish for a minimal, hand-soldered board) on the condition that the sensing design resolves a stuck-on triac, a triac that fails to close and an open element; the condition is met for a stuck-on triac and for "no heater current when commanded" and is not met for telling a triac that fails to close from an open element. *Recommendation:* keep them dropped and revisit when the sensing task proves the current check. *Cost of adding them back:* two places of two parts each (four parts), 12 hand joints and a board 23.5 % larger; `IN_COND`'s two inputs stay reserved. *Held in:* § The heater wall board, *The mains-presence confirm*.

**D3. Where the supply current is sensed.** Owner decision pending: the owner confirms the placement drawn, a shunt in the neutral return at the pad of tab 3 read as the second channel of the voltage measurement's isolating part, or asks for the relay to move so that the owner's 13 × 8 mm isolated sensor stands in the `LINE` to `LINE1` link. The owner's own placement does not hold under this record's rules: it costs analogue-region capacity, puts three sensing blocks under A8's 20 mm and leaves the sensor's pocket without an exit. The drawn placement also assumes an isolating part with two inputs on one reference, which no record names. *Held in:* § The anticipated channel kinds, *Voltage, frequency and total current*.

**D4. The voltage measurement's place and the 85 °C stack.** Owner decision pending: the drawn stack keeps `VMEAS` directly under the module, 15.0 mm from the interlock relay (the owner's figure for an 85 °C part against a source of about 1 W), and holds two of the five 85 °C parts 15 mm from the module; the third what-if holds three at the price of the voltage measurement's distance from the relay and a part of the analogue region, and keeps kind 5. The drawn stack is the default. *Held in:* § Heat; § Reported for the board design tasks, item 19.

**D5. One shared fuse for both pumps, or for the pumps and the valves.** Owner decision pending: the proposal replaces the three fuse holders that `DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE` arranges (a fuse for each pump and one for the two valves) by one. It is not drawn; it gives up the independence of the two pumps and returns two holders' area. No smaller approved fuse that meets the 6 kA was found. *Held in:* § The fuses.

**D6. The smaller IRM-10-5 as the logic supply.** Owner decision pending: whether to take the IRM-10-5 once bring-up has measured the air. The module stays the IRM-20-5 meanwhile: the IRM-10-5 has 1.06 times this board's 5 V load at 70 °C against the 2.0 the forms record calls adequate, and 2.13 times at 50 °C, which is not measured. *Held in:* § The logic supply against this board.

**D7. Whether the two wall-board varistors stay.** Owner decision pending: they are kept, being the only surge clamp any record draws on the heater branch; dropping both would save four joints, and the board-entry varistor (the owner's ruling, § The fuses) is now sourced, 775 V at 50 A, which does not bring the branch under the 600 V the triac blocks; the wall varistors, 775 V at 10 A, do not either, but are a second clamp at the triac, and the branch is not judged inside the makers' ratings with or without them (absent: the triac's and opto-triac's microsecond withstand) (§ The heater wall assembly, judged, *The surge clamps*). *Held in:* § The heater wall board, *Snubbers and varistors*.

**D8. A blade terminal or a solder pad for the return landing.** Owner decision pending: the landing takes the tab part's own blade, so the return wire ends in a female push-on; a solder pad would remove a blade and two hand joints. The blade is drawn. *Held in:* § The path of the heater current, *The return landing*.

**D9. The wall board as its own board, or a section that breaks off the main board.** Owner decision pending: the record keeps its own board, 2.34 USD dearer at best and decoupled from the main board's respins; the section is the owner's starting point and stays open. *Held in:* § The heater wall board, the comparison of forms.

**D12. The removal-order priority of kinds 3, 4 and 5.** Owner decision pending: of the three, one can keep its place; the drawn order removes kinds 3 and 4 and keeps kind 5, the second current channel, which senses a safety-relevant quantity, and the owner may reorder. Weight (kind 2) is last and kinds 1 and 6 are outside the order by the owner's decisions. *Held in:* § The anticipated channel kinds.

**D13. 2 oz copper against off-board wiring.** Owner decision pending: no path needs more than 1 oz now, so the weighing decides nothing here; its figures stay for the owner, and this record takes 1 oz and no wiring on the board. *Held in:* § Layer counts, *Copper weight*; § Copper that carries the heater current.

**D15. A basic mains-to-earth pair in the separation basis.** Owner decision pending: the basis lists the triac's insulated tab to the metal wall and signs no distance for mains copper toward that wall; this record applies the basic creepage of the basis's interpolated row, 4.1 mm (the same row selection as for mains copper of different nets, A3), and reports the wall-to-copper barrier as unlisted. Signing a basic mains-to-earth pair is an amendment outside this slice, and the earth bond it relies on is not measured. *Held in:* § The heater wall board, *Mains copper and the metal wall*.

**What each of these choices would change if it went the other way.** The list above names, for the decisions the main board's and the heater wall assembly's judgements touch, the choice drawn meanwhile. This table adds the other choice and what it would change, so that the consequence is carried with the drawn board. Every row is a consequence only: redrawing the board to the choice not drawn is not done here.

| | Drawn meanwhile | The other choice | What it would change | Held in |
|---|---|---|---|---|
| D1 | The 10.0 mm rule as written; the four tab moves | The owner amends the rule for fixings that cannot be reached | Tabs 1 to 3 and 9 are redrawn from the distance that replaces 10.0 mm. At the as-found places, which stand 6.38 mm (tab 1) and 11.38 mm (tab 9) from their fixings, the harness keeps its whole 10 mm of lead slack where the moves leave 3.1, 3.0, 2.5 and 8.1 mm. The amended figure is signed in the basis and the pre-order rule, and the link, the fuse holder and the relay stack, which hang from the tab positions, are redrawn. The owner's measurement of the four leads' slack with a rule, before the board is ordered, is what shows whether the moves are possible at all | § The fixing rule and the tabs that move |
| D2 | The two mains-presence confirms are left off the drawn board | The two confirms come back onto the wall board | Two places of two parts each (an AC-input optocoupler and a 120 kΩ resistor), four parts and 12 more hand joints; the board grows from 57.0 × 42.5 mm = 2 422.5 mm² to 57.0 × 52.5 mm = 2 992.5 mm², 570.0 mm² or 23.5 % more, with a six-way header and a T of slots, still 4.00 USD in the lowest band; the places' parts stand across the driver's way to the tab screws, so the screws are turned before the places are fitted; a confirm added after the board is made costs a respin of the 4.00 USD board. The confirm would tell a triac that fails to close from an open element, which the supply current cannot; both give the same safe response | § The heater wall board, *The mains-presence confirm* |
| D3 | A shunt in the neutral return at tab 3, read as the second channel of the voltage measurement's isolating part | The relay moves so the owner's 13 × 8 mm isolated sensor stands in the `LINE` to `LINE1` link | The analogue region loses capacity, three sensing blocks stand under A8's 20 mm, and the sensor's pocket has no exit. The condition that reopened D3, that no isolating part carries two channels on one reference, is not met: § The interlock block, *Barriers the signed basis does not list*, finds one. The drawn placement stands | § The anticipated channel kinds, *Voltage, frequency and total current* |
| D4 | The drawn 85 °C stack, `VMEAS` 15.0 mm from the relay and two of five 85 °C parts 15 mm from the module | The third what-if: three of the five held 15 mm from the module | `VMEAS` is carried at a greater distance from the relay and a part of the analogue region is given up, and kind 5 stays. The part found for `VMEAS` is rated to 125 °C by its sheet, so A21's 85 °C figure for it is cautious, not wrong, and the stack is unchanged by that finding | § Heat; § Reported for the board design tasks, item 19 |
| D5 | Three fuse holders, as the decision arranges | One holder for both pumps, or for the pumps and the valves | 432 mm² of holder area returns; a fault in one pump branch drops both pumps and the valves; the one fuse is sized for the pair's start surge and the coils' inrush together, so a fault in the smaller pump's branch clears at a higher current | § The fuses |
| D6 | The IRM-20-5 | The IRM-10-5, if bring-up measures cool enough air | 1.06 times this board's 5 V load at 70 °C against the 2.0 required (the IRM-20-5: 2.13), and the IRM-10-5 is 2.13 times at 50 °C, which is not measured; the module's body shrinks from 52.4 × 27.2 mm to 45.7 × 25.4 mm, 1 425 − 1 161 = 264 mm² (P1, P7), and its block and A8's distances are redrawn | § The logic supply against this board |
| D7 | The two wall-board varistors stay | Drop both, with the board-entry varistor as the only clamp | Four joints and two parts are saved. The entry varistor's maximum clamp is 775 V at 50 A (`controller-board-design-constraints.md` § Mains entry: fuse, surge clamp and suppression judged), over the 600 V the triac blocks (P3; the opto-triac blocks 800 V, P4, and the triac's 600 V governs), which the wall varistors (775 V at 10 A) do not bring under 600 V either; they are a second clamp at the triac, without the trunk, fuse and relay between, and the branch is not judged inside the makers' ratings with or without them (absent: the triac's and opto-triac's microsecond withstand): they stay; the kept part is the 07D471K, whose own rating is read (§ The heater wall assembly, judged, *The surge clamps*) | § The heater wall board, *Snubbers and varistors* |
| D8 | The landing takes the tab part's own blade | A solder pad | One blade and two hand joints are removed, the pour is unchanged, and the return wire ends soldered where it ended in a female push-on | § The path of the heater current, *The return landing* |
| D9 | The wall board is its own board, 2 662.5 mm² with its ears | A section that breaks off the main board | Fabrication falls from 4.00 USD to 1.66 USD, 6.60 × 2 662.5 / 10 609, saving 2.34 USD (an area-proportional inference, not a quote); a respin of the section takes the four-layer main board's order with it, about 48 USD at block level against 4.00 USD, and the record rates a respin of this assembly likely (the bracket's wall and cavity fit, the bracket as the heat spreader and the tab rating rest on measurements not yet taken); the break line carries no copper and the section's header keeps 10.0 mm from its own mains copper; assembly joins the main board's order. Whichever way it is drawn the heater board has no controller, no interlock and no reserved headroom | § The heater wall board, the comparison of forms |
| D11 | The cut is 2400.0 mm² in one place (30.0 mm tall by a provisional 80.0 mm long; the window alone, which exposes the steel; no passage), and the opening in the plastic that admits the unit is 89.0 × 45.0 mm = 4005.0 mm² (u −16.0 to 73.0 by z −10.0 to 35.0 from the component face), recorded with its reason; **accepted as preliminary by the owner on 2026-10-28 (the reply "Do 1"), to be revisited when the owner cuts and measures; decided, not pending** | The owner, on cutting and measuring, sets another length for the window or finds the plastic cannot be cut to the unit's envelope: the accepted figures are provisional and are replaced then | The 410 mm² in three places the owner accepted held only before the bracket. Were the larger cut declined when the owner cuts, the design would return to the triacs past the board's edge with their leads bent, or on the wall at a distance with six mains wires, the two forms the bracket replaced (§ The heater wall board, *The bracket*), and the owner's intent of 2026-10-26 (no lead bent, no joint desoldered) is given up; or the owner sets another length for the window, a shorter one needing a lower sink ambient or failing the continuous-full-power case and a longer one holding at a higher ambient (the length table of § The heater wall assembly judged, *The heat*; at 30.0 mm tall, 40, 50, 60, 100 and 120 mm cut 1200.0, 1500.0, 1800.0, 3000.0 and 3600.0 mm², and the 35.0 mm height at 80 mm cuts 2800.0 mm²), which the owner's measured maximum spreader length settles. The tab hole cannot be lowered: 17.25 mm is the least that keeps each triac's lead shoulders clear of the board. If the plastic cannot be cut to the unit's envelope, the unit is reshaped: the lead ends behind the board (up to 8.4 mm, trimmed after soldering) give first, the ears' 2.0 mm over the board leg second | § The heater wall board, *The wall cut, and the owner's acceptance* |
| D12 | Kinds 3 and 4 removed, kind 5 kept | The owner reorders the three | One other kind keeps its place and its header; kind 5's header `CURR2_H` (7.5 × 10.1 mm, 76 mm² drawn) and conditioning `CURR2_C` (6.0 × 8.0 mm, 48 mm²) are what the displaced kind would take or give up | § The anticipated channel kinds |
| D15 | The basis's basic creepage, 4.1 mm (the interpolated row), is applied between mains copper and the earth-bonded wall and bracket; the barrier is reported as one the signed basis does not list | The owner signs a basic mains-to-earth pair in the basis | The 4.1 mm is replaced by the signed figure: the wall-edge strip (v 0 to 5.0, drawn 0.9 mm over the 4.1 mm), the bracket's lift (5.0 mm, drawn at the same figure) and the mount distances are re-derived from it. A smaller figure lowers the lift and the copper's start and enlarges the window by 80.0 mm² for each millimetre with the leg's top held; a larger one does the reverse. The basis amendment is the owner's to sign and is not made here; the earth bond is not measured | § The heater wall board, *Mains copper and the metal wall* |
| D13 | 1 oz, no off-board wiring | 2 oz copper | Half the width for each ampere, 2.86 mm for 15 A, at 36.40 USD more for two layers in the lowest band and an unmeasured price at four layers; no path needs it now | § Layer counts, *Copper weight*; § Copper that carries the heater current |

## How this record is built, and what it decides

**This is a derived view, and its sources govern.** Every figure is read off a source named beside it: a row of `reference-machine.md`, `connector-pinouts.md`, `controller-board-function-forms.md`, `controller-board-design-constraints.md`, `component-specification.md`, `hardware/sunbeam-em7000/separation-basis.yaml` or `docs/board-manufacturer-jlcpcb.md`; a manufacturer's sheet (P1 to P14 of § Sources read, each read on 2026-10-24); an owner statement with its date; or a decision in the graph. Where this file and one of those disagree, the source is right and this file is corrected. Grades are those of `controller-board-design-constraints.md` § Evidence grades, with three more used here: **computed**, arithmetic on named figures that is shown; **estimate**, a block area or footprint that no sheet or record fixes yet, marked in its row; and **assumption**, a value this record chose where no fact exists, numbered A1 to A33 in § Assumptions with its basis, which the project replaces when the fact is read. Nothing here is graded better than the weakest figure it rests on.

**One data block holds the geometry, and the script checks what it can.** Every rectangle, position and rule of both floorplans, the tabs, the reed, the slots, the heater path, the interlock's link, the anticipated kinds and the cost inputs are in the one `floorplan-data` block of § Appendix. The script of that appendix **re-derives the floorplan geometry, the wall cut's areas and the tables from that block**: it computes every distance, path, area and total of those, compares the tables of this file with it, and compares what it prints with the expected output beside it, so a prose table and the data cannot drift apart unseen. The heat and tab-hole arithmetic of § The heater wall assembly, judged is in prose and is checked by hand: its thermal inputs are stated and not sourced, and the script would only re-run the prose formulas. **It does not make the data right.** Three kinds of figure are held differently. A figure with a source record is **read from that record and compared**, and the script fails if the row is missing or differs: the separation basis (the signed clearance and creepage, the basic creepage that is half the reinforced one, and the signed mains-to-mains clearance, terminal clearance and creepage), the nine tabs, seven drawn and two removed (names, positions, blade width and thickness), the four mounting points and the cavity, the reed's lead positions, intrusion 1, the maker's limits (the least slot, the copper-to-slot and board-edge distances, the lowest band, the slot-density charge, the recommended annular ring, the track width tolerance), the load currents, the top and peak of the supply span, the breaking capacity a fuse must have, the owner's acceptance of a relay's maximum switching voltage (its figure, its date, its attribution to the owner's statement and the top of the span it names, each of which must equal the data), the unit prices of the two relay types and the gauge drivers' phase current. A figure with none is an **assumption**, and where the data block holds it as a number its row of § Assumptions carries a `name=value` token that the data must equal (A1, A2, A8, A14 to A17, A20, A22, A24, A28, A30 and A31: 31 tokens): a token missing, doubled or unequal fails. The other assumptions (A3 to A7, A9 to A13, A18, A19, A21, A23, A25 to A27, A29 and A32) fix part sizes, rules and bookkeeping that the data holds only as drawn rectangles and rules, and a change to one of them is seen by the script only through the tables it compares and the distances it computes. The owner of every function is checked to be non-blank, a declared board or assembly, and the one the owner table names. **The limit:** an edit made to both an assumption's row and the data passes, and so does an edit to a figure no source and no token covers; that is a visible prose change for a reviewer to read, and not something the script can see. **What is counted, not typed:** the header pins and header types (each header block carries its ways and pitch), the joints of every part (a relay's or the module's are its pins), the number of Extended types and their fee, the current sensors on the 5 V rail (one for each kept kind that carries one), the capacities of the regions and the kinds' areas are counted by the script from the blocks and compared with the prose, so a count stated in the text and not in the data cannot go stale unseen. A change to a figure is made in the data block and the tables are corrected to what the script prints.

**What this record decides, and what it leaves.** It decides who owns each function, the division, each board's outline, fixings and block placement, the form of the heater wall board, the path of the heater current and the place of the interlock, the connector of every retained harness and the tabs that move, each anticipated kind's place, and which parts the owner fits by hand. It does not draw schematics or select parts: the part fitted is the design task's for the board or assembly that carries it, and every part named below proves a footprint and a rating, nothing more. It does not estimate the chosen division's cost in detail, which the cost estimate does from the charges recorded in `docs/board-manufacturer-jlcpcb.md`; the figures here are the block-level comparison the choice rests on. It chooses the interlock's mechanism, a relay with a two-channel drive (§ The interlock block, *The drive*), and does not choose that drive's parts. It does not choose how the wall board is supported beyond the bracket drawn in § The heater wall assembly, judged, or the faston tabs' maker, whose rating is absent (§ *The element harness*); § Reported for the board design tasks lists what each task is handed.

## How to read the coordinates

Every position on the main board is in the datum of `reference-machine.md` § Datum and axes: millimetres from the inside lower-left corner of the cavity, looking into it at the component face, X to the right and Y up. **Left** is the vertical edge where the mains wiring enters, X = 0; **right** is the edge the low-voltage bundle enters through, X = 133.5. A block is a rectangle written as its X range, its Y range and its size. The heater wall board has a frame of its own, in § The heater wall board: **u** along the edge that lies against the machine's wall and **v** away from that wall. The tables below are checked against the data block by the script of § Appendix, so a builder holding this repository and a Python interpreter can repeat every fit, distance and reach check made here.

## What the division is weighed against

| Input | Value | Source |
|---|---|---|
| Inside size of the cavity | 133.5 mm along X by 130.5 mm along Y, each ±0.5 mm; floor to the rim the lid closes onto 34.5 mm ±0.5; the lid's inside face is 28.87 mm ±1.0 above the floor | `reference-machine.md` § Usable envelope (items `A1.1`, `A1.2`, `A2`, `A2.lid`; measured; the 28.87 mm inferred) |
| The original board | 133.2 × 125.1 mm, each ±0.2 (the owner's caliper remeasurement of 2026-10-24, board out of the machine; it may not be exactly square), 1.5 mm thick (1.5 to 1.6), on 4 mm standoffs, top face 5.5 mm above the floor; it filled the cavity along X. The datum is the cavity wall and the original board's own edges were not measured against it, so they are inferred | `reference-machine.md` § Original board and its mounting |
| Height above a board's top face | 28 mm for a part anywhere but within about 2 mm of a wall, 23.4 mm within about 2 mm of a wall, both from the original's top face, 33.5 mm above the floor; the 28 mm is the tallest part on the original board, its AC/DC module, measured at 28 mm ±0.5 (owner, 2026-10-24) | `reference-machine.md` § Across the lid, and the ceiling to work to |
| This record's board | 1.6 mm FR-4, the manufacturer's default, on the same 4 mm standoffs: top face 5.6 mm above the floor, so **27.9 mm** and **23.3 mm** (33.5 − 5.6; 28.87 − 5.6) | computed; `docs/board-manufacturer-jlcpcb.md` § Price bands, *The quote's default options* |
| Intrusion 1, on the floor | Corner at (58, 0); 47.5 mm along X; 20 mm of straight edge along Y, then a half circle of the 47.5 mm width, so it reaches Y = 43.75 (centre (81.75, 20), radius 23.75); 3.5 mm ±0.2 high, which leaves 0.5 mm nominal (−0.2 to 1.2) under a board on 4 mm standoffs | `reference-machine.md` § Intrusions into the cavity (item `A3.1`; measured) |
| Intrusion 2, on the floor | A strip along the wall at Y = 0: X 0 to 133.5, Y 0 to 3; 1.85 mm ±0.2 high | same (item `A3.2`) |
| Mounting points | 1 at (6.5, 6.5), hole 3.15 mm; 2 at (126.7, 6.5), 3.1 mm; 3 at (6.5, 123.5), 3.1 mm; 4 at (127, 123.5), 3.1 mm; each ±0.5 mm, an M3 × 5 mm pan-head screw into a plastic boss. **This record's board has a hole at each of the four points**, point 3 drawn as the other three are (3.1 mm), and is held at all four as the original is. **None of the four fixings can be touched** (the owner, 2026-10-24): points 1 and 2 are the lid screws, recessed deep in a slot in the lid, and points 3 and 4, which carry no lid screw, are inside the closed case behind another panel | `reference-machine.md` § Mounting points; owner statement |
| The lid | Screwed down through the board's mounts 1 and 2, which the lid's two screw bosses align with; points 3 and 4 carry no lid screw; the boss and screw sizes were not read; the owner requires the lid screws at points 1 and 2 | same, *The lid is screwed down through the board's lower two mounts* (owner statement, 2026-10-20, item `L1`; 2026-10-24) |
| Low-voltage harnesses | One bundle through a cut-away in the right wall centred at X = 133.5, Y = 103.5 (±1 mm), 33 mm wide; shortest wire 40 mm (the two knob microswitches), longest 65 mm (the steam-block and steam-wand temperature sensors), each ±5 mm | `reference-machine.md` § Where each harness enters the cavity (items `B0.*`) |
| Mains harness | Along the left edge; the whole left side of the cavity is open from Y = 8 to Y = 122.5 (±2 mm); nine tabs, centres X = 8.5 ±1, at Y = 13.6, 22.3, 30.6, 52.9, 66.2, 79.1, 91.4, 101.2 and 111.4 (±1); each 6.36 mm wide, 0.81 mm thick, standing 9.9 mm clear of the board; the owner states the cable slack leaves a fit need of about 10 mm. Tabs 4 and 5 (Y 52.9 and 66.2, the element leads) are not used by this record's board (§ The path of the heater current) | `reference-machine.md` same section; `connector-pinouts.md` § The nine terminals |
| Tank reed element | Through-hole; **lower lead at X = 122.0 mm, Y = 17.5 mm, upper lead 20 mm above it at Y = 37.5, midpoint (122.0, 27.5), each ±1**; long axis along Y; body on the back face (inferred); fitted by the owner by hand and left off the order. The owner's caliper reading of 2026-10-24 (lower hole 15.3 mm above the original board's bottom edge, 121.25 mm from its left edge) fits it; the original board's edges were inferred, not measured, against the datum | `reference-machine.md` § Where each location-dependent part is mounted, *The tank reed and its float* |
| Supply and element currents | 216 to 253 V, 358 V peak; coffee element 4.80 A, steam element 5.38 A rms at 253 V, both 10.18 A; both pumps 0.46 A and 0.19 A at their sizing values (nameplates 48 W and 22 W) and both valve coils 0.129 A steady and 0.203 A at their inrush, so **10.96 A** behind the interlock relay and 11.03 A at the coils' inrush; about 15 A for half an hour in the entry fuse's overload band | `controller-board-design-constraints.md` § Supply budget, § Upstream protection and fault current |
| Separation basis | Reinforced insulation, mains to low voltage: **3.0 mm clearance, 10.0 mm creepage**, accepted by the owner 2026-10-23 and unsigned since the record gained the mains-to-mains figures, until the owner accepts the revised record; its table row for basic insulation at 320 V, pollution degree 3, is **5.0 mm** creepage, which the file states as the basic figure that the reinforced one doubles. For mains copper of different nets the file signs **1.5 mm clearance, 2.0 mm between the terminals of a part and 4.1 mm creepage**, the creepage interpolated at 253 V between its 250 V row (4.0 mm) and its 320 V row (5.0 mm) and rounded up, a deliberate 0.1 mm over the standard's own rounded 4.0 mm, and the same 4.1 mm ahead of and downstream of the entry fuse F101; the file lists the shortfalls the owner is to accept as exceptions, unsigned until the owner accepts the record (A3) | `hardware/sunbeam-em7000/separation-basis.yaml` |
| Distance the board check holds from a fixing to mains copper | The larger of the signed clearance and creepage, 10.0 mm, from each mounting hole's pad copper and courtyard to every mains pad, track, via and pour fill, on every layer | `DEC-BOARD-PRE-ORDER-RULE-READINGS`, *Mounting holes* |
| Air temperature parts are graded to | 70 °C, a project assumption. **The owner thinks 70 °C will not be real and expects to insulate the thermoblocks; this record keeps 70 °C as the assumed figure** (and sizes the 5 V rail at 50 °C as well), so every grade and distance below is on the cautious side, and bring-up measures the real air; **the heater wall assembly is the exception: it is judged at 45 °C, the owner's working figure of 2026-10-28 for the air at that board (the 70 °C being the controller area's), and at 70 °C as the conservative case** | `controller-board-design-constraints.md` § Enclosure air temperature; owner statement, 2026-10-24 |
| Declared spend | 250 USD, covering what the retrofit adds | `component-specification.md` § The component list |
| Board maker's bands and charges | The lowest fabrication band is a single board within 102 × 102 mm (2 layers 4.00 USD, 4 layers 8.00 USD, 5 boards); at 103 × 103 mm it is 9.20 USD (2 layers) and 31.60 USD (4 layers); above that the price is read at the quote. Economic assembly: setup 8.18 USD, stencil 1.53 USD, hand-soldering labour 3.58 USD an order, 0.0164 USD a hand-soldered joint, 3.07 USD feeder loading for each unique Extended part an order, 0.0016 USD a machine-placed joint, two boards at least. Standard assembly: setup 25.56 USD, stencil 8.21 USD, 16.42 USD of fixtures for one to 29 boards, and 1.53 USD feeder loading for each unique Basic, Preferred or Extended part | `docs/board-manufacturer-jlcpcb.md` § Price bands and the fabrication order, § Assembly limits, § Assembly charges, § Parts library classes and their fees (read 2026-10-13) |
| Track width for a current | At least 0.381 mm for each ampere of the highest continuous current a power net carries, at 1 oz | `docs/board-design-method.md` POWER-1 (TI SNVA021C § 5) |

## Assumptions

Each is a value this record needed and no record holds. A change to one is made here, with its dependants in the same change. A `name=value` token in a row is the figure the data block must equal; the script reads it from here and fails if it is missing, doubled or unequal, so a figure that no source holds cannot change in the data without a change in this table.

| No. | Assumption and basis | Where it bites |
|---|---|---|
| A1 | The extent of a mounting fixing, its pad and courtyard, is a circle of radius **E = 3.0 mm** (`E=3.0`) about the hole centre. This is **an obligation on the board design task, not an estimate**: the footprint is drawn with pad and courtyard inside radius E, and a stock M3 footprint that is larger is not used. The lid screw's head, 6.0 mm across (the ISO 7045 maximum for M3; the machine record gives only "M3 × 5 mm Phillips pan-head"), lies inside it. Sensitivity: at a courtyard radius of 3.45 mm (no footprint is chosen) mains copper would need 13.70 mm, tab 1 would move 10.1 mm and exceed the owner's 10 mm | Mains copper stays E + 10.0 + 0.25 = **13.25 mm** from every hole centre (the drawing tolerance is `draw_tol=0.25` mm, stated once); parts stay `lid_keep=3.5` mm from points 1, 2 and 4 |
| A2 | A mains tab's pad is the section of its blade with an annulus all round: the blade is 6.36 mm wide along X and 0.81 mm thick along Y (both read from the connector record), standing with its wide face parallel to X (the owner's reading of 2026-10-24, all nine blades), and the annulus is `tab_ring=0.32` mm, at least the maker's recommended 0.20 mm for a plated hole on a multilayer board (read from the maker's record): the pad is 7.0 mm along X and 1.45 mm along Y. The bought board-mounted tab's own footprint is not read; the design task draws it inside this pad or enlarges the pad and re-runs the distances. The landing for the wall board's return wire takes the same board-mounted blade and the same pad | The tab-to-fixing distance, the gaps between pads and the tab strip |
| A3 | Mains copper of different nets keeps **1.5 mm in a straight line and 4.1 mm by surface path round the milled slots**, **for every pair in the data**, the seven tab pads, the return landing's pad, the neutral pour, the shunt's two lands, the two link pours and the pumps' and valves' `NEUTRAL` pieces included: no pair is excused for belonging to one block or one strip. The figures are those the basis signs for mains to mains: the 1.5 mm clearance of the 2.5 kV row of its clearance table (the terminals of a part are held to 2.0 mm, 0.5 mm more for movement and assembly, a drafter's reading of a household-appliance standard footnote that the owner is to check, and the data's rectangles are not the pads of a part), and the 4.1 mm creepage, which is the linear interpolation at the working voltage, 253 V rms, of the basis's 250 V row (4.0 mm) and 320 V row (5.0 mm) at pollution degree 3, material group IIIa, rounded up to 4.1 mm, 0.1 mm over the standard's own rounded 4.0 mm; the same 4.1 mm applies ahead of the entry fuse and downstream of it, since no basis shows the fuse clearing a tracking fault between the pair. The basic mains-to-earth pair (D15) takes its creepage from the same row selection. The shortfalls that parts' own pad pitches force are the basis's accepted exceptions, each for the one pair of pads it names and unsigned until the owner accepts the record: the pump triacs T701 and T711 at 1.08 mm, the shunt R105 at 1.65 mm and the 1206 series resistors at 1.8 mm; the data's rectangles do not model those pitches. **A pair across the open interlock contact, `LINE` against `LINE1`, keeps the signed reinforced pair, 3.0 mm and 10.0 mm by surface path round a slot, and takes no credit for the relay's own contact gap** (P2 gives 1 000 VAC between open contacts, which is not used). Between the two pieces of mains copper of `TIMING` and of `VMEAS` lie the series resistors and the optocoupler's input pins, which bridge the gap; their own pad pitches are not modelled, which is reported (§ Reported for the board design tasks, item 3). There is no other exemption in the data: for each optocoupler its own pins are checked pin to pin round its slot, on both boards, the unpopulated confirm places included | Spacing of the mains blocks and of the tab pads; the eight milled slots |
| A4 | Support-part allowance: a 0603-class passive 10.8 mm² (a 3.0 × 1.8 mm courtyard, 5.4 mm², times 2 for escape and routing); a small-signal transistor 18 mm²; a diode 10 mm²; a voltage clamp 8 mm² | Every low-voltage block's drawn area |
| A5 | A header's footprint is its row, (ways − 1) × pitch + 4.5 mm (+ 5.0 mm for three ways or more at 2.54 mm pitch), by 7.0 mm deep (7.5 mm at 2.54 mm pitch); the maker's sheets for the JST families are not read here. **The load-cell headers `WT1_H` and `WT2_H` are taken at 2.0 mm pitch, like the other 2.0 mm harness headers of this board, an assumption**: the load cells' cable connector is not chosen, and at 2.54 mm this rule gives 15.2 × 7.5 mm for five ways, not the 7.0 × 12.5 mm that the owner gives and 2.0 mm gives, which would change the header regions' demand and the steps that remove kinds 3 and 4 | Every connector rectangle |
| A6 | A 5 × 20 mm fuse holder with its clips is 24 × 9 mm, no more than 15 mm high (a 20 mm cartridge and two 2 mm clips; the catalogue entry's own outline is not read). `DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE` names subminiature slow-blow fuses, which are smaller than a 5 × 20 mm cartridge; no sourced one meets the 6 kA the constraints record assumes (§ The fuses) | The three fuse holders |
| A7 | Small mains parts: a DIP-6 opto-triac footprint is 10 × 9 mm on the main board (body 8.51 × 6.35 mm, rows 7.62 mm apart, P4); on the wall board, with its rows along u, 10 × 11 mm; a DIP-4 or SMD-4 optocoupler with a 120 kΩ resistor 10 × 11 mm for a mains-presence confirm place on the wall board (not populated) and an SMD-4 part 10 × 5 mm on the main board (its own sheet is not re-read); a DPAK triac 10 × 8 mm; a varistor 10 × 6 mm, its two ends 2.5 mm wide and 5.0 mm apart; the shunt of the neutral return, two resistors side by side across the 7.0 mm of the copper, 7.0 mm long in the direction of the current with a 3.2 mm body between two lands of 1.9 mm, so 7.0 × 7.0 mm = 49 mm². **This geometry is an assumption and its source is still needed**: a standard 2512 is 6.3 × 3.2 mm with its terminals at the 3.2 mm ends, which puts about 7.4 mm along the current and not 7.0, so the drawn geometry needs a part with its terminals along the 6.3 mm sides (a long-side-termination part) or lands drawn about 0.4 mm farther apart; the design task selects the part and reads its land pattern, and the script repeats the distances from the data | The pump strips, the timing block and the wall board |
| A8 | Heat placement. **Two heat sources of a watt or more:** the logic-supply module (1.25 W at this board's load) and the interlock relay `K_IL` (0.98 W at its nominal coil, 1.03 W with the coil at the low end of its tolerance, so a source by A8's own figure of `heat_w=1.0` W, and by the owner's instruction of 2026-10-24). **No part that derates**, a part rated to 85 °C or less, that is 15 K or less over the assumed 70 °C air, within `heat_class=15.0` mm of either source (`heat_mcu=15.0` mm for the microcontroller, rated to 85 °C), **and no precision sensing block within `heat_sense=20.0` mm** of either; likewise `heat_opto=20.0` mm for the wall board's opto-triacs and the unpopulated confirm places' optocouplers (rated to 85 °C), from the triac bodies; the interlock relay, rated to 125 °C, stands **`heat_relay=15.0` mm** from the module, the owner's figure, whatever its class. A part's class is its rated ambient limit less the air: the valve relays 85 °C (P6); the pump opto-triacs and `VMEAS`'s isolating part 85 °C (A21); the timing optocoupler LTV-814S 100 °C (P12), 30 K over the air and so outside the class, which `TIMING` is listed as. The record holds no thermal model of the enclosure, so these are placement rules and not predictions. The script tests every distance, and the parts that stand under the rule are named in the data as reported and each must be under it (§ Heat). **Heat sources against each other:** the two heater triacs, 4.25 W and 4.84 W on one metal wall, are held 10.0 mm apart by A31, an assumption that the wall board's thermal judgement (§ The heater wall assembly, judged, *The heat*) did not replace | § Heat |
| A9 | The two knob microswitches are dry contacts that want a pull-up and a filter capacitor each; the retention decision says a retained contact "wants a pull-up", and no record holds the knob inputs' values | `FE_KNOB` |
| A10 | A mains conductor of the element harness is 1.5 mm² (the trunk's minimum, `DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE`); the metal wall is not located in this machine record. The 3.5 mm across over its insulation, and the 14.5 × 5.5 mm passage derived from it, an earlier assumption of this record, are withdrawn: no conductor passes the wall | The element harness wires |
| A11 | Joint counts for the assembly charges are counted from the blocks and not typed: a fuse holder with its clips 4, a tab 2, a relay or the module its pins (the interlock relay 6, its two 1.3 mm coil holes and four 1.5 mm contact holes, P2; a valve relay 4, two coil and two contact pins, P6; the module 4, P1), a header its ways, and on the wall board a triac 3, an opto-triac 6 with the two resistors of its gate network 4 (360 Ω and 330 Ω, Figure 12 of P4), a varistor 2, a blade terminal 2 and its header its ways; a confirm place not populated adds an optocoupler 4 and its resistor 2 if it is fitted; the shunt's resistors on the main board are placed by the machine | § What the owner fits by hand |
| A12 | A board is held by at least three fixings that do not lie on one line; a rest on a boss supports but does not hold against lift, so a board on two fixings and a rest, or on one, needs a third fixing that the machine record does not hold | § Candidate divisions |
| A13 | Every header type, and the shunt of the neutral return, is an Extended part of the manufacturer's catalogue: **read, and no longer assumed.** The seven header families and the shunt were searched in the manufacturer's library on 2026-10-25 (`controller-board-cost-estimate.md` § What the library class allows) and no Basic or Preferred part was found for any of them. The 1.95 mm four-way header of `KNOB` is the one family not identified: the library holds no entry for it (searched again on 2026-10-26 under five keywords, the answers being LEDs, fuses and card sockets), so its class is the class every header the search returned has, and not a reading of its own part. The 120 kΩ mains-sense resistor of the timing front end, C5126146, is read as Extended on the same date and is counted | The Extended counts: 19 types, the 7 header types and the shunt among them; the headers are hand-fitted, so none of the 21.49 USD they would cost is charged |
| A14 | The interlock relay's closed-contact heat is budgeted at **0.5 W at 10.18 A** (`relay_contact_w=0.5`) with the coil at its full drive of `relay_coil_w=0.4` W (5 V across 62 Ω): 4.8 mΩ, a drop of 49 mV, and 0.58 W at the 10.96 A the relay carries. The coil is fed at its full drive and nothing else (the reduced-hold drive is dropped); with the coil at the low end of its tolerance, 55.8 Ω, it dissipates 0.448 W. The sheet's 100 mΩ maximum is a qualification bound at 1 A and 6 VDC, not a figure at current, and taken at 10.18 A it would be 10.4 W, shown beside the budget as the unsourced worst case. Bring-up measures the drop at about 10 A (§ The interlock block) | § The interlock block; § Heat |
| A15 | A trace's route is searched for a trace of width `trace_w=0.30` mm (0.381 mm for each ampere of the largest current a lead carries, 0.46 A for a pump, is 0.18 mm, so 0.30 mm has room), at the maker's ±20 % track width tolerance (read from the maker's record), so a half width of 0.18 mm, and with half a grid cell, 0.25 mm, in addition, since the centreline is snapped to a grid of 0.5 mm: a route that exists holds every distance with 0.43 mm to spare, and the maker's own minimum track, 0.10 mm, is not the figure used | The route search of § Every retained harness reaches its connector |
| A16 | The shunt of the neutral return loses `sensor_mohm=1.0` mΩ in the path, a budget for a part not chosen and not a fact: 0.12 W at the 11.01 A the neutral carries with every load on, 0.23 W at 15 A | § The path of the heater current; § The anticipated channel kinds, kind 9 |
| A17 | The tank reed's keep-out is a body strip `strip_w=4.0` mm wide between the two pads (the element and its insulating compound) and a hand-access zone of `hand_r=5.0` mm radius round each pad, for the iron and a finger; no source gives either figure. The reed's lower lead is held within `reed_tol=1.0` mm of the recorded position, the criterion's own figure | § The tank reed |
| A18 | A region holds a set of blocks when two things hold. **The area**, the necessary condition: the sum of each block's area grown by the spacing the drawing keeps, 0.3 mm in the header regions and 0.4 mm in the analogue region, does not exceed the union of the region's rectangles grown the same way; the spacing is the drawn one and no larger allowance (the earlier record counted a 1.5 mm gap that the drawing does not keep). The drawn blocks stand 0.3 mm or more apart in the header regions and 0.4 mm in the analogue region, and the script holds the spacing to what the capacity counts. **For the headers, an arrangement**: an exhaustive search of every placement of the headers, each turned or not, finds out whether one exists; the drawn columns are one arrangement and not a limit. No block of another class lies in a region now. The regions are the rectangles the kept blocks are drawn in, and the script checks that each block lies inside the union of its region's rectangles | § The anticipated channel kinds |
| A19 | The screw and boss at point 3 are those of points 1, 2 and 4: an M3 × 5 mm pan-head screw into a plastic circular boss (`reference-machine.md`, items `A5.1.f` and `A5.3.f`, the latter read "same"), a 3.1 mm hole, on the same 4 mm standoff; the boss's top diameter is recorded for no point, so no lead end, solder joint or heavy part lies within 3.5 mm of the centre of any hole | § The fixing rule and the tabs that move, *Point 3* |
| A20 | The copper of the link from tab 2 through the relay to tab 1 loses at most **`link_loss_w=0.5` W** at the machine's steady supply current, 10.96 A with every load on (and at the heaters' 10.18 A). The figure is a budget and not a fact: it is the heat the link may add beside the relay's own, and the script computes the link's loss from its regions and fails above it | § The interlock block |
| A21 | The pump opto-triac `MOC3052M` of `P_C` and `P_S` and the isolating part of `VMEAS` are taken as rated to 85 °C: the wall board's opto-triac MOC3083 is rated to 85 °C (S16 of the forms record), the pump part's own range is not re-read, and `VMEAS`'s part is not chosen; each is placed as an 85 °C part against A8, and a different rating, once the part is chosen, changes its row | § Heat |
| A22 | The heater triacs stand on a right-angle bracket that the owner makes or sources (it is not in the catalogue and is not priced), assumed cut and machined from 5.0 mm plate of one metal, so that **both legs are 5.0 mm thick**. One leg lies along the board's wall-edge strip, v 0 to 5.0, **`lift=5.0` mm** clear of the board's component face on plastic spacers at its two mounts; the other, the standing leg and the heat spreader (owner statement, 2026-10-28), stands from it to 35.0 mm above the board (14.8 mm over the highest tab top, 17.25 + 2.95 = 20.2 mm, from the package drawing's dimensions L, A and a2 (P3) and the board's fixing; § The heater wall board, *The heater wall assembly, judged*), its outer face on the metal wall, 30.0 mm tall and **80.0 mm long** (provisional drawn defaults, `top_z` and `window_l`, the length centred on the board, replaced by the owner's measured maximum spreader; the owner's estimate is 80 × 30 to 35 mm and the leg's face is the low end of that height), and its inner face, at v = 5.0, carrying the two tab faces; two wall bolts through it at u = −2.5 and 59.5, each 9.0 mm in from an end of the leg. The metal is aluminium, as the owner said (owner statement, 2026-10-28: "The aluminium spreader will be screwed with thermal paste to a stainless steel wall"); its conductivity and heat capacity are stated figures of this record. The standing leg is 5.0 mm thick so that the tab faces stand where the blocks stand, 5.0 mm in from the wall edge. The board leg lies along u −15.0 to 72.0 (87.0 mm), so that its two mounts stand on the ears. The bracket is earthed through the wall, an earth bond that the basis says is not measured, so it is held to mains copper at the basic creepage, 4.1 mm, in three dimensions, and the lift is drawn at 5.0 mm, 0.9 mm over that, over the copper under the strip's inner edge. The mount screws and spacers are plastic. **This record's reading of the board against the wall:** edge-on, its wall edge flush with the bracket's outer face; the owner's intent is the bracket and the unit fitted as one, and edge-on follows from one leg bolted to the wall and the other fixed to the board, which the owner did not say in those words. **Not claimed:** the heights of the varistors above the board, the depth of the plastic wall in front of the metal, and any distance from the metal to a lead end or joint on the back face (the owner's measurements, § The heater wall board, *The heater wall assembly, judged*, *Owner measurements*) | § The heater wall board, *The bracket*; *Mains copper and the metal wall* |
| A23 | The interlock relay's contact terminals, read from the vertical-terminal drawing of P2 (the outline views and the PCB layout, on 2026-10-24; the sheet's text does not say which holes belong to which terminal, so this is the drawing's reading, the two feet of the end view standing 7.56 mm apart across the body and each foot's two legs 5 mm apart in the side view): the relay has **two contact terminals, 7.56 mm apart across its 12.7 mm body**, each a 6.3 mm quick-connect blade (0.8 mm thick, its wide face along the body's length) standing on **two Ø1.5 mm holes (+0.1 mm) 5.0 mm apart along the length**, the four holes of the sheet's 4 × Ø1.5; the two coil holes, 2 × Ø1.3, are 7.56 mm apart across the body and 2.5 mm in from the coil end, 37.5 mm from the second column of contact holes, and the far contact column is 1.0 mm in from the end of the 41 mm length. The layout is a bottom view and the terminals are symmetric about the body's axis, so the mirror to the component side changes nothing. The contact copper is drawn 8.0 mm along X, the legs 1.0 mm in from its left edge and 2.0 mm from its right, and its two halves stand 3.0 mm apart; each leg stands at least 1.0 mm (the hole's 0.8 mm radius and the 0.20 mm annulus the maker recommends) inside its copper | The relay's contact rectangles |
| A24 | Copper at 1 oz is 35 µm of annealed copper at 1.72 × 10⁻⁸ Ω·m: **`sheet_mohm=0.491` mΩ** for each square (the published resistivity of the metal, not a datasheet's figure) | Every resistance of a copper region |
| A25 | The logic supply module's mains copper is two pads, one about each AC pin, each **6.0 mm square** (the pins are 1.0 mm, P1, which leaves a ring of 2.5 mm); the middle of the module's AC end carries no copper | The module's mains rectangles `MODULE.n` and `MODULE.l`; the valve relays' leads |
| A26 | A valve relay's contact copper is the 2.76 mm end of its body that holds the contact pins and **8.85 mm tall** (the two contact pins 6.35 mm apart, P6, each with a pad ring of 0.97 mm, the 1.3 mm hole of the sheet's PCB layout and the 0.32 mm annulus of A2, and 0.28 mm more), centred on the body's 10.1 mm width, so it stands 0.625 mm in from each side of the body; its coil pocket is the 3.2 mm end that holds the coil pins, the body's full 10.1 mm width; the sheet's drawing gives the two columns of holes 15.24 mm apart (P6), which leaves 11.64 mm between the copper and the pocket against the signed 10.0 mm creepage; which end is which is chosen so that the contact end faces the tab pads | The valve relays' rectangles |
| A27 | A weight circuit is the amplifier's SOP-16L courtyard, 11.0 × 7.4 mm = 81 mm² (body 9.9 × 3.9 mm and lead span 6.0 mm, P11, with 0.7 mm of land and courtyard assumed each side), and five passives of A4's 10.8 mm² (the sheet's Figure 1: the 10 µF analogue-supply capacitor, the 0.1 µF reference capacitor, a 0.1 µF at the digital supply, and two for the bridge inputs; the external PNP and its two resistors of that figure are left out because the 5 V rail feeds the analogue supply): 135.4 mm², drawn as a row 19.0 × 7.2 mm = 136.8 mm² (11.0 mm of amplifier, 8.0 mm of passives) | The two weight circuits |
| A28 | The 5 V rail's loads that no record or sheet fixes: each opto-triac LED is driven at `opto_led_ma=15` mA (the forms record brackets it between 5 and 60 mA; four LEDs, two heater and two pump), the panel's indicators and buzzer take `panel_ma=60` mA, the flow meter `flow_ma=15` mA, each pressure transducer `pressure_ma=10` mA (two), each in-stream probe converter `probe_ma=2` mA (two), each current sensor `sense_ma=10` mA (three), each load-cell bridge is `loadcell_ohm=350` Ω across the 5 V (two), the voltage measurement's isolated output stage takes `vm_out_ma=5` mA, and the headers, pull-ups and thermistor dividers together `misc_ma=10` mA. None is read from a sheet; each is replaced when the part is chosen | § The logic supply against this board |
| A29 | The voltage measurement `VMEAS` is drawn as `TIMING` is, a strip 5.0 mm deep (the 2512 resistors' and the optocoupler's courtyards of A7) with its mains copper in two pieces, `VMEAS.N` on `NEUTRAL` and `VMEAS.L` on `LINE`, 6.5 mm apart, one side of a slot and a pocket on the other: a series divider of two 1 W 2512 resistors on `LINE` (A7's 9 × 5 mm each) and an isolating part astride the slot, its first input across the divider and `NEUTRAL`, **its second input across the shunt of the neutral return (kind 9), which stands at `NEUTRAL`'s potential, so the two inputs share the part's input reference**; the parts bridge the gap between the pieces, 37.5 × 5.0 mm = 188 mm², an estimate; no isolating part is chosen, none with two input channels is named, and no figure for one is read (§ Reported for the board design tasks, item 20) | `VMEAS`; kinds 1 and 9 |
| A30 | The logic supply module's input current is found at an input power factor of `module_pf=0.5`, the project's floor for the pumps (`controller-board-design-constraints.md`), because no sheet read here gives the IRM-20's: 4.70 W out at 79 % is 5.9 W in, 0.05 A at 253 V; it is the part of the neutral's current that the link does not carry | § The path of the heater current |
| A31 | The two heater triacs stand at least **`heat_triac=10.0`** mm apart, body to body, on the one metal wall that is each one's heatsink: about one tab face's width (10.4 mm, P3). It is an assumption and not a sourced figure: no record or sheet gives how far the heat of a tab face spreads in the wall, so the figure only keeps the two faces from sharing one footprint; the thermal judgement of the wall is § The heater wall assembly, judged, *The heat* (`DEL-HW-PARTITION-AND-FEASIBILITY.C5`), and it did not replace this figure: it keeps the 10.0 mm body separation as the stated assumption and treats the two triacs as 9.09 W on one leg, so no spacing is derived from the wall's spreading | § The heater wall board, *Heat*; § Reported for the board design tasks, item 30 |
| A32 | The two pumps' returns join the neutral pour on an inner layer of the four-layer main board. The script searches for a surface trace from each pump's `NEUTRAL` piece (`P_C.N`, `P_S.N`) to the pour and finds none, so the data gives the join as an inner layer and the script requires that no surface route exist for them; that an inner layer can carry the join, with the signed distances kept from mains copper of other nets on that layer and from the planes, **is not shown here**. The same holds for the join of `HOTVALVE` (tab 9 to `K_V2`), for which the script finds no surface route since the hole at point 3 and shows a route clear of every hole, slot and low-voltage block on a layer of their own, and no more. The same holds for the line side of the entry fuse, the net `LINE_IN` from the pad of tab 2 to the fuse's line-side clip `F_IL.i`, which the pad's neighbours shut in on the surface; that run carries the whole supply up to the fuse's rating, so its width is the link's, which is not shown here either | § The path of the heater current; § The fuses; § Reported for the board design tasks, items 5 and 31 |
| A33 | The entry varistor is the 14D471K of the cost record (C8852), a disc of 14 mm drawn 14.0 mm along X by 5.0 mm thick and 21 mm high, with its pads 7.5 mm apart along X and staggered 3.0 mm along Y, 2.0 mm each (the catalogue's pad records, `controller-board-cost-estimate.md` § Mains entry); the maker's sheet is not read, so the thickness, the height and the lead length are assumptions the design task replaces from it. The entry fuse's own resistance is not in the link's copper | The entry varistor `RV_IL`; § The fuses |

## Every function has one owner

An **off-board assembly** is one not installed in the enclosure with the boards; it may still be made as a section that snaps off one of them. There are two: the heater wall board and the steam-path assembly. The machine keeps its existing fixed mains lead, so there is no appliance inlet and no [earlier design: mains-entry assembly]; the mains entry's fuse and varistor are on the main board. Everything else is on **the main board**, the one board in the enclosure (§ Candidate divisions says why it is one). The first column is the heading of the forms record, § The record of forms, word for word; the script compares it with that record's headings, and a function left out fails. The second column names the function's owner and no other, and the script compares it with the owner in the data block: a blank owner, one that is not a declared board or assembly, or a board named in this column that the data does not give fails. Two functions are split across boards on purpose and the data says why. The reasons rest on the figures of § What the division is weighed against and on the cited sections.

| Function (forms record) | Owner | Why this owner |
|---|---|---|
| Controller | Main board, `MCU` | The one controller serves every channel, so every block reaches it; the bundle of low-voltage harnesses enters on the right, and the controller sits 15.0 mm from the logic supply, A8's figure and the one heat source of a watt or more on the board bar the interlock relay (§ Heat), in the upper right of the board. `DEC-CONTROLLER-BASELINE-STM32H743` |
| Coffee element switching and steam element switching | Heater wall board (off-board) | The owner's plan is to bolt the two triacs to the machine's metal wall, outside the enclosure (`controller-board-design-constraints.md` § Enclosure air temperature, *Premises*; owner statements, 2026-10-04 and 2026-10-23). Each triac dissipates 4.25 W (coffee) and 4.84 W (steam) at full duty and 17.1 W in the 15 A overload band (`controller-board-function-forms.md` § Parts off the boards); outside, that heat goes into the wall and not into air the other parts are graded to. The board as found switches the neutral side of every load, the active conductor reaching each load by the retained `LINE1` daisy-chain (`connector-pinouts.md` § The source of each live feed), so the switch sits in the element's neutral-side path, between the element lead and the neutral, and the element lead keeps its female terminal and plugs onto an in-line blade joiner placed by the owner instead of a tab (§ The path of the heater current) |
| Heater gate drive, both channels | Main board, `DRV_HEAT` | The split the forms record sets: one small transistor per channel sinks the opto-triac's LED current from the 5 V rail, and the cable between the boards carries that current and nothing at mains potential. The opto-triac it drives is part of the heater switch and is on the heater wall board |
| Coffee pump switching and steam pump switching | Main board, `P_C` and `P_S` | The pump leads end on tabs 7 and 8, which stay where they are; each drive (fuse, snubberless triac, random-phase opto-triac) sits level with its tab so the switched lead is short, and the opto-triac's low-voltage side lies at the zone boundary |
| Two-way valve switching and three-way valve switching | Main board, `K_V1` and `K_V2` | The valve leads end on tabs 6 and 9; one small relay each (the HF32FA-G/005-HSL1, § The valve relays), standing at the zone boundary with a mains lead of 35 and 37 mm from its tab pad, and the shared fuse `VFUSE` in the column left of the module. A relay's coil pins are 15.24 mm from its contact pins and its coil pocket 11.64 mm from its contact copper, against the signed 10.0 mm creepage |
| Supply-timing front end | Main board, `TIMING` and `IN_COND` | One AC-input optocoupler on `LINE` and `NEUTRAL` serves every channel and both crossings; it stays a single measurement on one board, as the forms record has it and as the owner asked |
| Coffee, steam and wand temperature sensing | Main board, `FE_NTC` and the three thermistor headers | The headers are retained connectors on the right; the dividers sit 23.8 mm from the logic supply and 75.8 mm from the interlock relay (§ Heat) |
| Flow sensing | Main board, `FE_FLOW` and header `CZ1` | As above, on the right |
| Steam-path pressure sensing | The steam-path assembly (off-board) | The forms record decides the transducer is bought and sits in the steam path, and that the form is not chosen on a part; the assembly's design is its task's. Its two headers, `STM_D` (digital) and `SPARE_A` (analogue), are on the main board and are the connectors of that harness. The headers are **split**, as the forms record sets: the digital header's two signal lines sit on pins that carry an I²C and a UART function and its supply is 3V3, while the analogue spare takes 5V, 3V3, GND and a filtered input; sharing one connector would put 5 V on the digital pair's connector |
| Gauge drive, both gauges | Main board, `FE_GAUGE` and header `SP2` | The buffer sits between the controller and the five lines to the retained `VID66-08`, which is on the retained gauge assembly |
| Heater mains-presence confirm | Heater wall board; **no places on the drawn board**, two (`PRES_S` and `PRES_C`) on a second layout, **not populated** | The owner's wish of 2026-10-24 for a minimal hand-soldered board, to drop the two confirms from the populated board on the condition that the sensing design resolves a stuck-on triac, a triac that fails to close and an open element, **a condition only partly met, so an owner decision pending** (§ Owner decisions pending, D2; § The heater wall board, *The mains-presence confirm*). The function stays assigned to the wall board, where the confirm taps each element's switched node, `OUT_S` or `OUT_C`, and the neutral at the `RET` pad through 120 kΩ and 1 W, so that a later add-back needs two small parts at each place; the places are checked as a second layout, 23.5 % larger, and are not on the drawn board. Its two low-voltage outputs would return to `IN_COND` on the main board, whose inputs stay reserved |
| Low-water indication, visual | Main board, `FE_WATER` | One transistor sinking the retained indicator's cathode, reached through `SP2` |
| Operator panel: keys, indicators, buzzer | Main board, `FE_PANEL` and header `CON2` | The seven lines are three transistors and five resistors; the panel is a retained passive assembly |
| Low-voltage supply (the logic supply) | Main board, `MODULE` | The bought module straddles the zone boundary, mains pins on the mains side and 5 V pins on the low-voltage side, 45 mm apart (P1); it stays the IRM-20-5 against this board's 5 V load (§ The logic supply against this board). **Its mains pins are fed from `LINE` and `NEUTRAL` upstream of the interlock contact**, so the controller keeps power when the relay opens (§ The interlock block) |
| Wiring, connectors, mains-rated terminals | Main board and wall board, each its own | One connector per recorded retained connector, on the board the harness reaches (§ Harnesses): the main board the seven tabs it keeps, the return landing, the seven harness headers, the heater wall board's low-voltage header and the anticipated headers; the wall board its three blade terminals and its three-way header. The function is split because no one board carries the connectors of both harnesses |
| Proof-of-life interlock | Main board: the relay `K_IL` and its drive `POL` | The forms record asks for a series element in each heater's supply path that removes power whatever the switching device does. The heaters' supply, and that of every pump and valve, is the one conductor `LINE1` that the retained daisy-chain wires feed to each load (`connector-pinouts.md` § The source of each live feed), and its only source on the board is the link from tab 2 to tab 1. The contact sits in that link, so a shorted triac is cut off with the rest, and so is every other load, on the premise that every load's live lead comes from `LINE1`, which rests on the owner's visual trace and is checked at bring-up (§ The path of the heater current; § Reported for the board design tasks, item 32). The coil is driven by `POL` beside it and is unenergised when the controller stops |
| Mains entry protection | Main board | The machine keeps its existing fixed mains lead and fits no appliance inlet and no [earlier design: bought inlet filter] (the owner's ruling, § Owner intent carried in; `DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE`). The 10 A slow-blow fuse and a varistor are carried on the main board where the lead's conductors land, at tabs 2 and 3, the varistor hard against the fuse and downstream of it, as the original board carried its own protection at its entry. The fuse needs a 10 A holder, because the board's 5 × 20 mm holder is listed for 6.3 A (`controller-board-design-constraints.md` § Manufacturer stock and price, per channel, *Wiring, connectors, mains-rated terminals*). The entry's emission suppression is decided in § The fuses and in `controller-board-design-constraints.md` § Mains entry: an X2 capacitor, no choke. The fuse holder and the varistor are drawn in the floorplan at tabs 2 and 3; the capacitor is not drawn, its place left to the main board design (§ The fuses) |

Three channels are not rows of the forms record and are assigned here so none is left out: the **tank level** (the reed element, `REED`, on the main board, hand-fitted at the position the machine record gives), the **control-knob microswitch inputs** (header `KNOB`, `FE_KNOB`) and the **supply voltage measurement** that `REQ-MEASUREMENT-001.C10` requires (the isolated measurement `VMEAS` and its conditioning `VM_C`, § The anticipated channel kinds, kind 1). No USB connector is placed: no function in the forms record needs one, and the programming header is part of the `MCU` block.

## The owner's starting points

Each is an input weighed, not a mandate.

| Starting point | Followed or departed from | Reason |
|---|---|---|
| Both boards inside the existing controller enclosure | Followed for the main board; departed from for the wall board | The wall board is outside by the owner's plan, so the triacs can bear on the metal wall. The division has one board in the enclosure, not two |
| Mains connections on the left, low-voltage harnesses on the right | Followed | The seven tabs it keeps are on the left edge at X = 8.5; the seven harness headers are at the right, X 113.6 to 131.5, and the anticipated headers and the wall board's low-voltage header at X 88 to 131.5, Y 34 to 75; the zone boundary lies between (X 61 to 71) |
| Heater switches off-board | Followed; the interlock relay is not on the wall board | The two heater triacs and their opto-triacs are on the wall board; the confirms are not on the drawn board (an owner decision pending, § Owner decisions pending, D2) and the current is sensed on the main board. The interlock relay is on the main board, in the link that feeds every load, so it cuts the pumps and the valves as well (owner's approval, 2026-10-24) |
| Valve relays and pump drive on a mains board, or on a board shared with the low-voltage circuitry with the basis's clearance and creepage held on the board | The second | One board. The signed 3.0 mm and 10.0 mm are held by distance, and by milled slots between every low-voltage pocket and the mains copper that stands nearer than 10.0 mm (§ Zones and the barrier); mains copper of different nets is held apart by the signed 1.5 mm and 4.1 mm of path, and across the open interlock contact by the signed reinforced pair |
| The controller board as narrow as it can be, possibly an elbow | Departed from | There is no separate controller board. A narrow board along the right edge would carry mounting points 2 and 4, which lie on one line, 117 mm apart, and would leave the mains side on a board held by one fixing (§ Candidate divisions) |
| The heater wall board a section that breaks off another board | Departed from, left open | Its own board. As a section it saves 2.34 USD of fabrication and would tie every respin of the safety-critical wall board to a respin of the four-layer main board (§ The heater wall board); the owner may still choose the section (an owner decision pending, § Owner decisions pending, D9) |
| Each board within the lowest price band, weighed against one board of about the enclosure's width that meets the mounting points | Followed for the wall board (57.0 × 42.5 mm, inside 102 × 102); departed from for the main board | Mounting points 1 and 2, which the lid screws hold, are 120.2 mm apart in X, and the mains-side blocks span 124.1 mm in Y (the pads of the seven tabs alone 90.4 mm); no board that carries them lies within 102 mm, so the band is not available to it and its price is read at the quote |
| The layer count chosen per board, with a ground plane favoured under the sensing | Followed | § Layer counts |

## Candidate divisions

All three divide the same circuitry and leave the heater wall board as it is; the in-enclosure boards differ. Fabrication is for five boards, leaded HASL, 1.6 mm, 1 oz, at the charges read on 2026-10-13. A board within 102 × 102 mm has the maker's published band price; above it the maker publishes no table: its price is the engineering fee plus a board fee, the maker's two published points at 103 × 103 mm give the fee for that area (2 layers 4.00 + 5.20 USD, 4 layers 25.00 + 6.60 USD), and **the board fee at any other area is inferred here as proportional to it**, which is an inference and not a published figure; the engineering fee, the band prices, the assembly charges and the connector parts are published. Every figure is block level; the cost estimate (`controller-board-cost-estimate.md`) carries the inferred board fee, and the design task's quoted order re-reads it at the quote.

**Outlines.** Division A's board is 131.0 × 125.0 mm. Division B's mains board is 69 mm wide and 125 mm high with a 15 × 27 mm bay for the module's DC end, 69 × 125 = 8 625 plus 15 × 27 = 405, **9 030 mm²**; its low-voltage board is 59 mm wide and 125 mm high less the same bay, 59 × 125 = 7 375 less 405, **6 970 mm²**; the 3 mm between them is not counted, and the two total 16 000 mm². Division C keeps B's mains board; its controller board is **60 × 60 mm** (3 600 mm²) and its front-end board **50 × 60 mm** (3 000 mm²), both inside 102 × 102 mm, so each takes the maker's published band price (8.00 USD at four layers, 4.00 USD at two) and not the inferred fee. A's and B's boards are over 125 mm along Y and are outside the band.

| | A: one board spanning the enclosure | B: a mains board and a low-voltage board | C: a three-board split |
|---|---|---|---|
| Boards, layers, outline | One, 4 layers, 131.0 × 125.0 = 16 375 mm² | Mains board 2 layers, 69 mm wide plus a 15 × 27 mm bay for the module's DC end, 9 030 mm²; low-voltage board 4 layers, 6 970 mm²; 3 mm between | Mains board as B (2 layers, 9 030 mm²); controller board 4 layers, 60 × 60 mm, 3 600 mm²; front-end board 2 layers, 50 × 60 mm, 3 000 mm² |
| Fabrication, estimated (certain part) | 25.00 + 6.60 × 16 375 / 10 609 = **35.0** USD (25.00) | 8.43 + 29.34 = **38.0** USD (29.00) | 8.43 + 8.00 + 4.00 = **20.5** USD (16.00) |
| Assembly charges that grow with the order count | Setup and stencil 9.71 USD; hand-soldering labour 3.58 USD | Two orders: 19.42 USD; labour 7.16 USD; one Extended header type on both orders, 3.07 USD | Three orders: 29.13 USD; labour 10.74 USD; two such duplicates, 6.14 USD |
| Inter-board connector parts | None | One link of 24 conductors: eight 5-way headers at 0.0855 USD (C157991) = 0.68 USD, and 40 hand-soldered joints = 0.66 USD; the mating housings and cable are not priced in the catalogue records | Two links: 1.37 USD of parts and 1.31 USD of joints |
| Total of the three rows above | **48.5** USD | **69.0** USD, 20.5 more | **69.0** USD, 20.5 more |
| Fixings each board holds (the machine's bosses are points 1 to 4, and each takes a screw here) | One board on all four points | The mains board on points 1 and 3, two fixings on one line; the low-voltage board on points 2 and 4, two fixings on one line | The mains board as B; the front-end board on points 2 and 4; **the controller board on none** |
| Fit | Blocks fill 10 833 of 16 375 mm² (66 %) | 10 833 of 15 690 mm² (69 %) after a 3 mm gap and two link headers of about 155 mm², but each board is held by fewer fixings than A12 asks | Not shown: a board with no boss of its own carries no recorded fixing |
| Separation | The signed 3.0 and 10.0 mm held on one board, by distance and by slots | Unchanged: the barrier parts' low-voltage pockets still sit on the mains board; the gap adds distance the basis does not count | As B |
| Bring-up | Low-voltage circuits are brought up with the module, relays and fuse holders unfitted (all through-hole, fitted last); 5 V is fed at the module's two DC pads | The low-voltage board has no mains copper at all | As B |

**What the comparison supports: A.** Three reasons, in the order of their weight. C's two small boards take the maker's published band price (20.5 USD of fabrication for C, of which 12.00 USD is the published band prices and the rest the inferred fee of its mains board), which brings C level with B; A is still the cheapest of the three by about 20 USD, and the weighing below holds on the new figures.

1. **Fixings.** The board check holds mains copper at least the signed 10.0 mm from a mounting hole's pad and courtyard (`DEC-BOARD-PRE-ORDER-RULE-READINGS`), which with the obligation E = 3.0 mm and the 0.25 mm drawing tolerance (A1) means 13.25 mm from the hole's centre. The pad of tab 9 stood 11.4 mm from point 3 and the pad of tab 1 6.4 mm from point 1 (§ The fixing rule and the tabs that move). All four of the machine's points take a screw, so a board is held at each corner of the cavity; any division that puts the mains circuits on their own board leaves that board on the two points of the left half, 1 and 3, which lie on one line, where A12 asks three fixings that do not. Division A is the only one in which a board is held at three or more points that do not lie on a line: all four. The heavy parts, the module and the interlock relay, stand inside the rectangle the four points make; what stands in the corner at point 3 is the two pump strips' small parts and the two valve relays, 17.6 × 10.1 mm each, the nearer of them 38.0 mm from the point 3 centre.
2. **Cost.** A is the cheapest at block level by about 20.5 USD (B and C), 8 % of the 250 USD declared spend each. The ranking does not depend on the inferred board-fee slope: A's area exceeds B's two boards' by 375 mm² (the 3 mm gap), about 0.23 USD at the maker's four-layer slope, while B adds 3.07 + 9.71 + 3.58 USD of fixed assembly charges, a second engineering fee of at least 4.00 USD and the link parts; and C's gap to A is made of the setup, stencil and labour of its two extra orders (26.58 USD more than A's), its duplicate Extended fees (6.14 USD) and its links (2.68 USD), against the 14.76 USD of fabrication it saves (exact figures: the table rounds to the half dollar, since the board fee at an area other than the maker's two published points is inferred and supports no finer figure).
3. **Fit.** One outline spends the cavity best: B and C give up the gap and the link headers out of the same cavity.

**Charges common to the three.** The Extended-part feeder fees, 15.35 USD for the 5 unique types the manufacturer places on the main board and none for the 14 the owner fits (§ What the owner fits by hand), the hand-soldered joints, 143 at 0.0164 USD = 2.35 USD, and a few hundred machine-placed joints at 0.0016 USD, about 1 USD (the count is not yet known), do not differ between the three beyond the duplicates counted above. The heater wall board's own costs and the cables to it are the same in every division and are left out.

**What A costs, and what it gives up.** A's four layers are bought for the whole outline, including the mains zone that does not need them: against two layers at the same area the fee is 23.0 USD higher (35.0 against 12.0 USD; at 103 × 103 mm the maker's own figures differ by 22.40 USD). Its re-spin is one board: a change to the mains circuits re-spins the low-voltage circuits and the other way round. The low-voltage circuits share a board with mains copper, 10.3 mm or more from it. The staged build above is what takes the sting out of the last point.

## Layer counts

| Board | Layers | Reason |
|---|---|---|
| Main board | **4**: top, an inner ground plane under the low-voltage circuits, an inner supply plane, bottom | The owner favours a ground plane under the sensing; the thermistor dividers and the two RTD converters read to ±2 °C and better on a board that also switches two pumps and drives relays. The controller's maker asks for low-impedance supply connections, "typically achieved with thick track widths and, preferably, the use of dedicated power supply planes in multilayer PCBs" (P5 § 7.4). The four-layer fee exceeds a two-layer one by 23.0 USD at this area; a two-layer board with a pour is the fallback if the cost estimate finds the spend too thin, and the floorplan holds either. The planes are pulled back at least 10.0 mm from every mains copper edge on every layer |
| Heater wall board | **2** | All through-hole except the current sensor, mains and its own low-voltage drive; no sensing of a small signal, so no ground plane to favour. Two layers is the 4.00 USD band price. Its copper is 1 oz |

**Copper weight.** Both boards use 1 oz finished outer copper, the maker's introductory price, wherever wide tracks or pours carry the current: the `LINE` to `LINE1` link (its narrowest region 5.75 mm, against the 5.72 mm that 15 A needs), the neutral return's pour and shunt lands (7.0 mm) and every region of the wall board's heater path (7.0 mm against 5.72 mm). **No place needs more now.** One place did when the heater return was to cross the main board from the heater terminals to tab 3: it would have needed 5.72 mm and had 5.0 mm between the tab pads and the relay contact ends, and heavier copper (2 oz, which halves the width) was weighed against off-board wiring for it, at **36.40 USD more** for 2 oz at two layers in the lowest band (40.40 USD against 4.00 USD, read; the four-layer price at this outline is unmeasured). With tabs 4 and 5 gone the return lands beside tab 3 and crosses a pour 7.0 mm wide (§ Copper that carries the heater current), so the weighing no longer decides anything; its figure stays here for the owner (an owner decision pending, § Owner decisions pending, D13).

## The fixing rule and the tabs that move

**Finding.** The lid screws hold the board at points 1 and 2 (the owner requires them) and screws hold it at points 3 and 4, so the board is held at all four of the machine's mounting points as the original is; none of the four fixings can be touched (below). The board check holds mains copper at least 10.0 mm from a mounting hole's pad and courtyard whether or not the fixing is bonded to protective earth (`DEC-BOARD-PRE-ORDER-RULE-READINGS`). The rule measures the **footprint's pad and courtyard**, not the screw head, and no footprint is chosen. This record therefore makes the extent an obligation on the board design task: **the mounting footprint is drawn with pad and courtyard inside a circle of radius E = 3.0 mm about the hole centre, and a stock M3 footprint that is larger is not used** (A1). The margin rule follows: every mains rectangle keeps E + 10.0 + 0.25 = **13.25 mm** from each hole centre, the 0.25 mm being the drawing tolerance, stated once. A tab's pad is 7.0 mm along X and 1.45 mm along Y about its centre (A2), the blade standing with its wide face parallel to X (the owner's reading of 2026-10-24), so the pad's X range holds the hole's X and the distance is measured straight up from the pad's lower edge: the centre stays 0.725 mm further than the rule asks. Whether a lid screw can be reached from outside the machine depended on which face of the lid its head is on, which the machine record does not say; the owner has since said that none of the four can be touched (below), and the rule holds the distance either way.

The original board does not meet it: the pad of its tab 1 stands 6.38 mm from the point 1 centre and that of its tab 2 15.07 mm, and the pad of its tab 9, at Y 111.4 with its upper edge at 112.125, stands 11.38 mm below the point 3 centre at Y 123.5, 1.87 mm short. The nine tabs are read as found (`reference-machine.md`, ±1 mm); the three nearest point 1 and the one nearest point 3 move.

| Tab | As found, Y (mm) | Pad edge from the nearest fixing, as found (mm) | Pad edge from the nearest fixing, now (mm) | This record's Y | Move (mm) | Slack left of the owner's 10 mm (mm) | Lead |
|---|---|---|---|---|---|---|---|
| 1 | 13.6 | 6.38 | 13.27 | **20.5** | +6.9 | 3.1 | `LINE1`, red |
| 2 | 22.3 | 15.07 | 22.07 | **29.3** | +7.0 | 3.0 | `LINE`, brown |
| 3 | 30.6 | 23.38 | 30.88 | **38.1** | +7.5 | 2.5 | `NEUTRAL`, blue |
| 9 | 111.4 | 11.38 | 13.28 | **109.5** | -1.9 | 8.1 | `HOTVALVE`, blue |
| 6 to 8 | as found | 21.6 or more (tab 8 from point 3) | | unchanged | none | | the other three (tabs 4 and 5 are removed, § The path of the heater current) |

Tab 1 must clear the fixing: its pad's lower edge stays 13.25 mm from the hole centre, so its centre is at least 6.5 + 13.25 + 0.725 = 20.475 mm up and is drawn at **20.5**. Tab 2 must stay at least the as-found minimum pitch of 8.3 mm above it, and the link sets more: the copper of `LINE1` must be 5.775 mm wide from the pad's lower edge to its upper edge at 25.55 mm (the width 15 A needs, § Copper that carries the heater current), the gap across the open contact is 3.0 mm, and the pad of tab 2 must stand inside the `LINE` copper above it, so tab 2 is at least 29.225 mm up and is drawn at **29.3**. Tab 3 follows by the same rule: the pad of tab 3 stands 3.0 mm above the upper edge of the `LINE` copper, 34.3 mm (its 5.75 mm of width above the gap), and 5.0 mm from it by path round the slot `SL_LN`, so tab 3 is at 38.1 mm, **not because of the fixing, which it clears, but because tabs 1 and 2 take its place**. The script tests that each moved tab is needed: brought 0.5 mm back toward where it was found, any of the four breaks a rule of this record. The tabs' X, 8.5 mm, is unchanged. Each tab pad is 7.0 mm along X and 1.45 mm along Y at its centre (A2): the pad of tab 1 is Y 19.775 to 21.225, that of tab 2 Y 28.575 to 30.025 and that of tab 3 Y 37.375 to 38.825, and the pads of tabs 1 and 2 stand 7.35 mm apart, those of tabs 2 and 3 7.35 mm, with no cut-back on any side. The strip that holds the seven pads, the return landing's pad, the neutral pour with the shunt's lands and the two link pours (X 5.0 to 17.0) is derived from them: Y 19.8 to 110.2. The least distance of any mains copper from a hole centre is 13.27 mm at point 1, the lower edge of the pad of tab 1 and of the `LINE1` pour that holds it, and 13.28 mm at point 3, the upper edge of the pad of tab 9, against the rule's 13.25; the script checks every mains rectangle against every hole.

**Tab 9 must clear point 3.** Its pad's upper edge stays 13.25 mm from the hole centre at (6.5, 123.5), so its centre is at most 123.5 − 13.25 − 0.725 = 109.525 mm up and is drawn at **109.5**, 1.9 mm below where it was found; the pad is Y 108.775 to 110.225. Tab 8 then stands exactly the as-found minimum pitch of 8.3 mm below it, at 101.2 mm (109.5 − 8.3), where it was found, so **tabs 7 and 8 do not move**: the script's check of pitch finds 8.3 mm, and moving tab 8 down further changes no route below. **Two routes break with the move, and the record gives the two nets as inner-layer joins.** A trace of a mains net keeps the same 13.25 mm from a hole as a pad does, on every layer, so the circle that a trace's centreline must stay outside, 13.68 mm about point 3, closes the way between the hole and the steam-pump strip `P_S` for the lead of tab 9 to the three-way valve relay `K_V2`; and tab 9's pad at 109.5 mm narrows the way between it and the coffee-pump strip `P_C` for the lead of tab 8 to `P_S`. The route search finds no surface route for `HOTVALVE` from tab 9 to `K_V2` or for `STEAMPUMP` from tab 8 to `P_S`, with tab 9 at 109.5 mm and moved no further, tab 8 moved down to the pitch (100.2 or 99.7 mm), or `P_S` moved right (the way for `STEAMPUMP` does not open). Moving the left end of `P_S` 4 mm and that of `P_C` 1 mm to the right opens both, which leaves `P_S`'s copper 22.5 mm long against its 24.0 mm fuse holder (A6), and the strips' right ends stand against their drivers, so neither is taken. The two nets are therefore joined on an inner layer, as the pumps' returns are (§ The path of the heater current): the script shows that each has no surface route and that a route clear of every hole, slot and low-voltage block exists on a layer of its own (`HOTVALVE` 36 mm, `STEAMPUMP` 10 mm), and does not show that the inner layer can carry them with the signed distances kept from the other copper of that layer, which is the design task's (§ Reported for the board design tasks, item 31).

**This is a harness change, named as the machine record asks any moved tab to be, for each of four tabs.** The leads of tabs 1 to 3 are `LINE1` (red, out to the loads), `LINE` (brown, in from the plug) and `NEUTRAL` (blue); the lead of tab 9 is `HOTVALVE` (blue, to the three-way valve). What forces each is the fixing distance the new boards are held to and the original was not: point 1 for tabs 1 to 3, with tabs 2 and 3 following tab 1 by the pitch and the link, and point 3 for tab 9, whose pad is 1.87 mm inside the distance. The leads are not cut, lengthened or re-terminated: each female push-on terminal fits the tab 6.9, 7.0 and 7.5 mm further up, or, for tab 9, 1.9 mm further down. The owner states that the cable slack leaves a fit need of about 10 mm (`connector-pinouts.md` § The nine terminals, owner statement, 2026-10-20), so the moves leave **3.1, 3.0, 2.5 and 8.1 mm** of it. The owner accepts what is left of the first three (2026-10-24) and **measures the real slack of each of the four leads with a rule before the board is ordered**; that measurement is the owner's and is not made here. If one is short, a push-on extender at the tab, a female and male spade in one piece, keeps the harness unmodified. If neither serves, the remedy lies outside this record: the signed figure governs the fixing, and the owner alone amends it. Nothing here changes `hardware/sunbeam-em7000/separation-basis.yaml`. The tab's height is the recorded 9.9 mm clear of the board only if the bought tab gives it: the board-mounted tab in § What the owner fits by hand is the proving candidate, and its blade height clear of the board is not read (its drawing, P15, gives the blade length, 14.3 mm, and not the height it stands), so the layout task reads it; a tab that does not stand at the recorded height is a harness change of its own.

**The fixings cannot be touched.** The owner states (2026-10-24) that none of the four fixings can be touched: points 1 and 2 are the lid screws, recessed deep in a slot in the lid, and points 3 and 4, which carry no lid screw, are inside the closed case behind another panel. The 10.0 mm rule of `DEC-BOARD-PRE-ORDER-RULE-READINGS` applies whether or not the fixing is bonded, and this record applies it as written and does not change it. **Owner decision pending (§ Owner decisions pending, D1):** the four tab moves above, 6.9, 7.0 and 7.5 mm up and 1.9 mm down, which leave 3.1, 3.0, 2.5 and 8.1 mm of the owner's 10 mm of lead slack, or an amendment of the rule for fixings that cannot be reached, which is the owner's and outside this slice; the moves are drawn, and if the rule is amended the four tabs are redrawn from the fixing distance that replaces it and the figures of this section are recomputed.

**Point 3.** The board is held at point 3 by a screw in a hole, as at the other three points: an M3 × 5 mm pan-head screw into the plastic boss (A19), a hole 3.1 mm across at (6.5, 123.5) as the machine record gives it, drawn with its pad and courtyard inside the same radius E = 3.0 mm (A1). The hole stands 5.5 mm from the left edge and 3.5 mm from the top, 0.5 mm over E, as point 4 stands from its edges, and no lead end, joint or heavy part comes within the 3.5 mm that every hole keeps clear (A19). The nearest mains copper is the upper edge of the pad of tab 9, 13.28 mm from the centre after tab 9's move, and the next, the steam-pump strip, stands 16.45 mm away. **No tenth tab is drawn:** the earlier floorplan reserved one for the added device (kind 6), and the owner has removed the reserved relay place by choice (§ The anticipated channel kinds, row 6). Points 1 and 2 are the lid screws and stay; points 3 and 4 keep their screws. Points 2 and 4 are 71.4 and 72.1 mm from the nearest mains copper.

**How the four points hold the board, and what is not analysed.** The board is 131.0 × 125.0 mm and 1.6 mm thick, fixed by one screw at each of the machine's four mounting points, (6.5, 6.5), (126.7, 6.5), (6.5, 123.5) and (127.0, 123.5), the corners of a rectangle 120.2 mm by 117.0 mm, on bosses 4 mm high. Three fixings that do not lie on one line hold a board against lift and sideways movement (A12), and four hold it at each corner of the rectangle, as the original board was held, so no point of the board is a rest. **What has not been analysed is the board's stiffness:** its deflection between the points under its own weight, under the weight of the module and the relays, under the lid's clamp at points 1 and 2 and under the push-on loads of the seven tabs on its left edge, which fall between points 1 and 3, 117.0 mm apart; no sheet read here gives the board's modulus or the masses of the large parts, and no stiffness analysis is made (the owner's measurement of the real boss heights and the bring-up fit of the lid are where it would first show).

## The main board's floorplan

### Outline, fixings and margins

The outline is a polygon in the data and here a rectangle, **X 1.0 to 132.0 and Y 2.0 to 127.0: 131.0 × 125.0 mm, 16 375 mm²**, square corners, 1.6 mm thick. The cavity is 133.5 × 130.5 mm (±0.5), so the margins are 1.0 mm at the left (where the wall is open from Y = 8 to 122.5), 1.5 mm at the right, 2.0 mm at the bottom and 3.5 mm at the top; with the cavity's ±0.5 mm and the maker's ±0.2 mm on a routed outline the least are 0.8 mm at the right and 2.8 mm at the top. **The board fits the envelope**, and every block and tab pad stands at least 0.3 mm inside the board's edge, the maker's recommended figure for components to the edge (`docs/board-manufacturer-jlcpcb.md` § Hole-to-hole and clearances to holes and edges). The original board measures 133.2 × 125.1 mm (±0.2, perhaps not exactly square; owner, 2026-10-24); this outline is smaller on purpose and is not copied from it. The datum is the cavity wall, and the original board's own edges were not measured against it but inferred, so nothing here rests on where they were.

| Fixing | Hole centre (mm) | Hole | Edge distances (mm) | Nearest part (distance from the centre, mm) |
|---|---|---|---|---|
| Point 1, lid screw | (6.5, 6.5) | 3.15 mm | 5.5 left, 4.5 bottom | Mains copper 13.27 (the lower edge of the pad of tab 1 and of its link pour) |
| Point 2, lid screw | (126.7, 6.5) | 3.1 mm | 5.3 right, 4.5 bottom | `REED` keep-out 6.0 (its lower pad's centre is 12.0); mains copper 71.4 |
| Point 4 | (127.0, 123.5) | 3.1 mm | 5.0 right, 3.5 top | `SP2` 5.0; mains copper 72.1 |
| Point 3 | (6.5, 123.5) | 3.1 mm | 5.5 left, 3.5 top | Mains copper 13.28 (the upper edge of the pad of tab 9); the steam-pump strip 16.45 |

Each edge distance exceeds the 3.0 mm extent E (A1) by at least 0.5 mm. The **lid-screw clearance** is held as a 3.5 mm part-free circle about all four points (A19); the lid's own boss and screw sizes were not read, so the clearance a lid screw needs to pass is **unconfirmed** and is the design task's to check on the lid.

### Zones and the barrier

Mains copper occupies the left of the board and the low-voltage circuits the right. Between them lies the **barrier**, a band at least 10.0 mm wide that the barrier parts bridge: the logic-supply module, the three relays, the two pump opto-triacs, the timing optocoupler and the voltage measurement's isolating part. Each barrier part's low-voltage side is a **pocket** (a rectangle in the tables), and the signed distances hold between every pocket and every mains rectangle, not only between a part's own two sides.

**Mains against low voltage.** For every pair of a low-voltage conductor and a mains conductor the board keeps a straight distance of at least the signed 3.0 mm clearance **and** a shortest path over the board's surface, taken round the milled slots, of at least the signed 10.0 mm creepage. A part's own body bridging its two sides is the only exception, and for the four strips whose isolating part straddles a slot (`TIMING`, `VMEAS` and the two pump drives) the part's own pins are checked pin to pin instead. A slot's ends lie far enough past the facing copper that the path round them reaches 10.0 mm; the script measures the path and does not assume it.

**Mains against mains (A3).** Mains copper of different nets, every pair in the data, keeps the signed 1.5 mm in a straight line and the signed basic creepage, 4.1 mm (the basis's 250 V and 320 V rows interpolated at 253 V and rounded up), by surface path round the slots; the shortfalls the parts' own pad pitches force are the basis's accepted exceptions, unsigned until the owner accepts the record (A3). **Across the open interlock contact**, the copper on `LINE` and on `LINE_IN` (the line before the entry fuse, which a bridge would bypass the interlock from as surely) against the copper on `LINE1`, the pair is the signed reinforced one, **3.0 mm straight and 10.0 mm by path, and no credit is taken for the relay's own contact gap** (the 1 000 VAC the sheet gives between open contacts is not used): a bridge there would defeat the interlock. It is held by **one slot, `SL_LINK`**, 1.0 mm wide, running from the board's left edge to X = 31.0 between the two tab pads (7.35 mm apart), between the two link pours and between the relay's two contact halves (3.0 mm apart, each on its own terminal of the relay, 7.56 mm apart: A23). A slot that reaches the board's edge cannot be walked round at that end, so the path round its right end is the one that counts, and the script measures it. The rule is the one rule for every pair: the seven tab pads and the return landing's pad are held to it against each other and against the link pours and the neutral pour (the pads of tabs 1 to 3 stand 7.35 mm apart, so none needs a slot), and a second slot, `SL_LN`, between the `LINE_IN` pour `LK_L` (the lead's line conductor before the entry fuse) and the pad of tab 3 and the shunt's first land above it (3.075 and 4.5 mm apart) holds the 4.1 mm by path; it ends at X = 16.5, 0.5 mm short of the entry fuse's load-side clip. The mains copper of the timing strip, the voltage measurement and the module is on `LINE` and `NEUTRAL` upstream of the contact, in a piece for each net, and is held to the same pair against the `LINE1` copper.

**The slots.** There are eight, each 1.0 mm wide (the maker's smallest non-plated slot, which the script reads from its record) and none within 0.2 mm of any copper or pocket (the maker's copper-to-slot figure, read the same way); where the board carries a part over a slot, the part's body bridges it:

| Slot | X (mm) | Y (mm) | Length (mm) | What it separates |
|---|---|---|---|---|
| `SL_LINK` | 1.0 to 31.0 | 26.55 to 27.55 | 30.0 | The `LINE` and `LINE_IN` copper from the `LINE1` copper: the two tab pads, the two link pours and the relay's two contact halves. It is open at the board's left edge, and the relay body stands over it |
| `SL_LN` | 1.0 to 16.5 | 35.30 to 36.30 | 15.5 | The `LINE_IN` pour `LK_L` from the pad of tab 3 (`NEUTRAL`) and from the shunt's first land above it; it is open at the board's left edge, and ends short of the entry fuse's load-side clip |
| `SL_VM` | 62.0 to 63.0 | 43.40 to 58.40 | 15.0 | The voltage measurement's mains pin from its low-voltage pin and its pocket from its own mains copper; the isolating part straddles it, and a slot closed at both ends is walked round at both |
| `SL_VP` | 36.0 to 67.5 | 91.10 to 92.10 | 31.5 | `K_V1`'s contact copper and its pocket from the coffee-pump strip's mains copper above them |
| `SL_PP` | 17.0 to 57.5 | 103.10 to 104.10 | 40.5 | The two pump strips' mains copper from each other |
| `SL_PV` | 36.0 to 67.5 | 115.10 to 116.10 | 31.5 | The steam-pump strip's mains copper from `K_V2`'s contact copper and pocket above it |
| `SL_PUMPS` | 57.5 to 58.5 | 91.10 to 116.10 | 25.0 | The pump strips' mains pins from their own low-voltage pins, and each strip's pocket from the strip beside it; the two optocouplers straddle it, and it joins `SL_VP` and `SL_PV` |
| `SL_TIM` | 57.3 to 58.3 | 2.00 to 12.50 | 10.5 | The timing strip's mains pin from its low-voltage pin; it is open at the board's bottom edge, and the optocoupler straddles it |

Counted from the data, the eight slots are 200 mm of slot path, and for five boards of 0.0164 m² each that is 12.2 m of slot path per m² of board, against 80 m per m² (the maker's figure, read by the script) before the maker charges for routing slots (`docs/board-manufacturer-jlcpcb.md` § Price bands and the fabrication order, *Extra charge for routing slots*), so no charge arises. 4 pocket-to-mains pairs stand under 10.0 mm apart in a straight line, from 4.2 mm; every one is held by a slot, the least surface path being 12.9 mm. The isolating parts' own pins, mains row against low-voltage row, are 15.8 mm (`TIMING`), 12.9 mm (`VMEAS`) and 58.3 mm (`P_C` and `P_S`, where the slot network closes the way round) apart round the slots. A slot is not drawn for the module's or the relays' own two sides: the module's mains pads and its pocket are 37.6 mm apart, `K_IL`'s contact copper and pocket 25.0 mm, and a valve relay's 11.64 mm (A26). 15 pairs of mains copper of different nets, from different parts, stand nearer than the creepage their rule asks, 11 of them across the open contact; every one is held by distance or by a slot, the least surface path being 7.3 mm.

Three rules hold between blocks, and the script of § Appendix checks all three:

- a low-voltage block lies 10.0 mm or more from every mains copper rectangle (the least, 10.3 mm);
- a pocket lies 3.0 mm or more from the mains copper of any block and, round the slots, 10.0 mm or more by surface path (the least, 4.2 mm straight and 12.9 mm by path);
- mains copper of different nets lies 1.5 mm or more apart and 4.1 mm or more by path (the least, 3.0 mm straight and 7.3 mm by path), and across the open interlock contact 3.0 mm and 10.0 mm (A3; the least straight, 3.0 mm); the tab pads and the link pours are in this rule like any other copper, with no exemption.

### The mains-side blocks

Mains copper is drawn as the rectangle each block's mains parts must stay inside; the body is the part's whole footprint, its low-voltage end included. The block `TABSTRIP` is derived by the script from the seven tab pads, the return landing's pad, the neutral pour with the shunt's lands and the two link pours. **The stack runs up the board in tab order for the link relay and the pump drives.** The timing front end lies along the bottom edge, below the link, where it holds the signed 10.0 mm from the `LINE1` copper above it; the relay `K_IL` is centred on Y = 27.05, the middle of the 3.0 mm gap across the open contact between the two link pours; the entry fuse holder `F_IL` stands along X directly above the relay's contact half, with the varistor `RV_IL` against its upper edge, and the shared valve fuse holder stands in the column above them, 5.0 mm higher than it stood before the entry parts were drawn; the voltage measurement stands directly below the module, 15.0 mm above the relay's body; the module stands **20.0 mm above `K_IL`'s body**, the voltage measurement between them, which A8 asks of a part that derates (15 mm); and above the module stand the first valve relay, the two pump drives and the second valve relay, packed up to the board's top edge. A valve relay's mains copper is inset 0.625 mm from its body (A26), so it keeps 3.0 mm from the copper beside it with 2.4 mm between bodies. **The pump drives stand at the levels of their tabs, their lower edges 1.7 mm and 3.9 mm above the tab centres; the valve relays do not.** A valve relay's coil pocket must reach the zone boundary, because a low-voltage trace from it has to keep 10.0 mm from every mains conductor (the widest gap between mains copper along the stack is 10.3 mm and such a trace needs 20.3 mm to pass, computed in § Heat), so the small relay stands at X 44.5 to 62.1 and its mains lead runs from the tab pad across the stack, 35 mm for tab 6 and 37 mm for tab 9 (the shortest routes the script finds, which keep 5.0 mm from every other net with the trace's half width and a margin, A15). The pump drives start at X 20.0 so that the leads of tabs 7 and 8 have routes between the pad column and the strips. The runs of any length are those two valve leads and the `LINE` and `NEUTRAL` taps that the module, the timing front end and the voltage measurement need (§ Every retained harness reaches its connector).

| Block | Function | X (mm) | Y (mm) | Size (mm) | Area (mm²) | What it holds, and its allowance |
|---|---|---|---|---|---|---|
| `TABSTRIP` | Seven 6.3 mm tab pads and the return landing on the left edge, the neutral pour with its shunt, and the two link pours | 5.0 to 17.0 | 19.8 to 110.2 | 12.0 × 90.4 | 1085 | The seven tab pads and the landing's pad, each 7.0 mm along X and 1.45 mm along Y (A2) about X = 8.5 (X 5.0 to 12.0); the shunt `I_SHUNT` (Y 38.825 to 45.825) with its two lands of 1.9 mm, `I_SHUNT.a` on the pad of tab 3 and `I_SHUNT.b` on the pour, and the neutral pour `LK_N` (`NEUTRAL`, X 5.0 to 12.0, Y 45.825 to 49.0) that holds the landing's pad (Y 45.875 to 47.325); and the two link pours `LK_L` (`LINE_IN`, the lead's line conductor before the entry fuse, X 5.0 to 12.0, Y 28.55 to 34.3, holding the pad of tab 2 and no longer reaching the relay's contact half) and `LK_L1` (`LINE1`, X 5.0 to 17.0, Y 19.775 to 25.55, holding the pad of tab 1 and joining it to the relay's contact half); the strip is the envelope of the pads, the neutral pour and the two link pours, not one copper pour |
| `TIMING` | Supply-timing front end: AC-input optocoupler and its series resistors | 19.8 to 65.3 | 2.5 to 9.5 | 45.5 × 7.0 | 319 | SMD-4 optocoupler 10 × 5 (A7) 50 + two 1 W series resistors (2512, courtyard 9 × 5) 90 = 140 mm² in 45.5 × 7 mm, upstream of the contact and 10.3 mm from the `LINE1` copper above it; its mains copper is in two pieces, `TIMING.L` on `LINE` (X 19.8 to 29.0) and `TIMING.N` on `NEUTRAL` (X 37.0 to 55.3), 8.0 mm apart, the parts bridging the gap; its pocket and the slot `SL_TIM` stand at its right end; the optocoupler is rated to 100 °C (P12), 30 K over the air, outside A8's 85 °C class |
| `K_IL` | Relay K_IL, the proof-of-life interlock, in the link from tab 2 to tab 1: contact end left, coil end right | 17.0 to 58.0 | 19.8 to 34.3 | 41.0 × 14.5 (14.525) | 596 | HF115F-Q/005-1H, vertical-terminal variant, 41.0 mm long and 12.7 mm wide, 15.7 mm high (P2): its body at Y 20.7 to 33.4, centred on the 27.05 mm of the gap between the two link pours, its contact terminals 7.56 mm apart at Y 23.27 and 30.83 (A23); the block is drawn 14.525 mm tall (Y 19.775 to 34.3, the lower edge of the pad of tab 1, so 595.5 mm², shown as 596) to hold the contact copper that stands beyond the body: `K_IL.a` on `LINE`, Y 28.55 to 34.3, and `K_IL.b` on `LINE1`, Y 19.8 to 25.55, each X 17.0 to 25.0; its heat rectangle is its body, X 17.0 to 58.0 and Y 20.7 to 33.4 |
| `F_IL` | Entry fuse holder, 10 A: the lead's line conductor from tab 2 enters its right clip and leaves its left clip | 17.0 to 41.0 | 34.3 to 43.3 | 24.0 × 9.0 | 216 | 24 × 9 mm holder (A6) for the 10 A 5 × 20 mm fuse, 15 mm high at most, stood along X on the upper edge of `K_IL`'s block (Y 34.3); its copper is its two clips, the load-side clip `F_IL.o` (`LINE`, X 17.0 to 23.0, 6.0 mm wide, meeting `K_IL.a` along Y = 34.3 and carrying the link on from the fuse) and the line-side clip `F_IL.i` (`LINE_IN`, X 35.0 to 40.0, 10.04 mm from `K_IL`'s coil pocket and 5.1 mm from `VMEAS.N`), 12.0 mm apart; the line side is joined to the pad of tab 2 on an inner layer (A32, 23 mm), because the pad is shut in by the copper of the other nets on the surface |
| `RV_IL` | Entry varistor, the 14 mm disc, across the fused line and the neutral | 17.2 to 31.2 | 43.3 to 48.3 | 14.0 × 5.0 | 70 | The 14D471K disc of the cost record's § Mains entry, drawn 14.0 mm along X and 5.0 mm thick (A33), with its pads 7.5 mm apart along X and staggered 3.0 mm along Y, 2.0 mm each; it stands against the fuse holder's upper edge, 0.0 mm from it, and 0.1 mm below `VMEAS`; its line pad `RV_IL.l` (`LINE`, X 19.5 to 21.5, Y 43.3 to 45.3) touches the fuse's load-side clip `F_IL.o`, so it is on the piece of copper that holds the clip and 0.0 mm from it, and its neutral pad `RV_IL.n` (`NEUTRAL`, X 27.0 to 29.0, Y 46.3 to 48.3) stands 5.6 mm from the line pad and 5.0 mm from the clip; no suppression part is drawn |
| `VFUSE` | Shared fuse holder for both valve branches | 17.0 to 26.0 | 50.5 to 74.5 | 9.0 × 24.0 | 216 | 24 × 9 mm holder (assumption A6) turned to stand along Y in the column left of the module, 5.0 mm higher than before the entry parts were drawn so that its neutral clip keeps the basic creepage from the varistor's line pad; its copper is its two clips, the neutral clip `VFUSE.n` (`NEUTRAL`, Y 50.5 to 55.5, 5.2 mm from the varistor's line pad, which takes the valves' return) and the relay-side clip `VFUSE.v` (Y 69.5 to 74.5) |
| `VMEAS` | Supply-voltage measurement (kind 1) and the shunt channel of the supply-current measurement (kind 9): a series divider and an isolating part with low-voltage outputs | 32.5 to 70.0 | 48.4 to 53.4 | 37.5 × 5.0 | 188 | A strip like `TIMING`, 5.0 mm deep (A29): two 1 W 2512 series resistors and the isolating part; the mains copper in two pieces, `VMEAS.N` (`NEUTRAL`, X 32.5 to 43.5) beside the module's neutral pad and `VMEAS.L` (`LINE`, X 50.0 to 60.0), the slot `SL_VM` at X 62.0 to 63.0 and the pocket X 65.0 to 70.0; the part is not chosen, and the barrier is one the basis does not list (§ The anticipated channel kinds, kind 1); it stands directly below the module, 0.0 mm from it, and 15.0 mm from the interlock relay's body; its isolating part also takes the second channel, the shunt of the neutral return (A29, kind 9) |
| `MODULE` | Logic supply, IRM-20-5: AC pins left, DC pins right | 32.5 to 84.9 | 53.4 to 80.6 | 52.4 × 27.2 | 1425 | 52.4 × 27.2 mm, 24 mm high (P1); AC pins at X = 35.9, Y = 56.6 (N) and 77.4 (L), DC pins at X = 80.9, Y = 56.6 and 64.6, 12.9 and 20.9 mm above the top of intrusion 1 at that X; its mains copper is the two 6.0 mm pads about the AC pins (A25), `MODULE.n` on `NEUTRAL` and `MODULE.l` on `LINE`, and its mains pins are fed from `LINE` and `NEUTRAL` upstream of the contact; 20.0 mm from `K_IL`'s body |
| `K_V1` | Relay K_V1, two-way valve (tab 6): contact end left, coil end right | 44.5 to 62.1 | 80.6 to 90.7 | 17.6 × 10.1 | 178 | Hongfa HF32FA-G/005-HSL1, 17.6 × 10.1 mm, 12.7 mm high (P6): contact pins 0.96 mm and coil pins 1.4 mm from the ends of the body, 15.24 mm apart (A26); the contact copper is X 44.5 to 47.26 and Y 81.225 to 90.075 (8.85 mm tall) and the pocket X 58.9 to 62.1, the body's full 10.1 mm; the body stands on the module's, 0.0 mm from it, and the relay is an 85 °C part not held from the module (§ Heat); the lead to the pad of tab 6 runs 35 mm |
| `P_C` | Coffee-pump drive: fuse holder, DPAK triac, DIP-6 opto-triac with its slot | 20.0 to 65.5 | 93.1 to 102.1 | 45.5 × 9.0 | 410 | 24 × 9 holder (A6) 216 + 10 × 8 triac (A7) 80 + 10 × 9 opto-triac (A7) 90 = 386 mm² in 45.5 × 9 mm, leaving 24 mm² for two gate and series resistors (A4, 10.8 mm² each); its lower edge 1.7 mm above the centre of tab 7, the lead running 9 mm to its copper; its opto-triac straddles the slot `SL_PUMPS`; 12.5 mm from the module (§ Heat), not held; its mains copper is two pieces, `P_C` on `COFFPUMP` (X 20.0 to 46.5) and `P_C.N` on `NEUTRAL`, the triac's MT1 end (X 51.5 to 55.5), 5.0 mm apart, whose join to the neutral pour is on an inner layer (A32) |
| `P_S` | Steam-pump drive | 20.0 to 65.5 | 105.1 to 114.1 | 45.5 × 9.0 | 410 | As `P_C`; the lead of tab 8 (pad Y 100.475 to 101.925) runs 10 mm to the strip's copper; 24.5 mm from the module; its pieces are `P_S` (X 20.0 to 46.5) and `P_S.N` (X 51.5 to 55.5) |
| `K_V2` | Relay K_V2, three-way valve (tab 9): contact end left, coil end right | 44.5 to 62.1 | 116.5 to 126.6 | 17.6 × 10.1 | 178 | As `K_V1` (its contact copper X 44.5 to 47.26, Y 117.125 to 125.975); the lead to the pad of tab 9 runs 37 mm; 38.0 mm from the point 3 centre |

Rectangles inside the blocks, for the checks: the mains copper of `MODULE` is two pads of 6.0 mm square about the AC pins, X 32.9 to 38.9 and Y 53.6 to 59.6 (`NEUTRAL`) and 74.4 to 80.4 (`LINE`) (the AC pins at X = 35.9, Y = 56.6 and 77.4; A25); its low-voltage pocket is X 76.5 to 84.9, Y 53.9 to 67.9 (the DC pins at X = 80.9, Y = 56.6 and 64.6). The pins are read from P1's bottom-view drawing (AC/N 3.2 mm and AC/L 24.0 mm from one long edge, −V 3.2 and +V 11.2 mm from the same edge, the AC and DC pins 45 mm apart) and mirrored to the component side with the AC pins at the left. `K_IL`'s mains rectangles are its two contact halves, X 17.0 to 25.0 (8.0 mm wide: A23), 3.0 mm apart, with the four legs at X = 18.0 and 23.0 and Y = 23.27 and 30.83, and its pocket is its coil end, X 50.0 to 58.0, with the coil holes at X = 55.5, 7.56 mm apart across the body (P2). A valve relay's mains rectangle is its contact end, X 44.5 to 47.26, and its pocket its coil end, X 58.9 to 62.1, with the coil pins at X = 60.7, 7.6 mm apart, and the contact pins at X = 45.46, 6.35 mm apart (P6; A26). Each pump strip's mains copper is in two pieces, the pump's switched lead from X 20.0 to 46.5 and, 5.0 mm beyond it, the triac's `NEUTRAL` end `P_C.N` or `P_S.N` from X 51.5 to 55.5, and its pocket is X 60.5 to 65.5; the shared fuse holder's copper is its two clips, `VFUSE.n` on `NEUTRAL` (Y 50.5 to 55.5) and `VFUSE.v` on the valves' side (Y 69.5 to 74.5), X 17.0 to 26.0; the entry fuse holder's is its load-side clip `F_IL.o` on `LINE` (X 17.0 to 23.0) and its line-side clip `F_IL.i` on `LINE_IN` (X 35.0 to 40.0), Y 34.3 to 43.3, and the varistor's is its line pad `RV_IL.l` on `LINE` (X 19.5 to 21.5, Y 43.3 to 45.3) and its neutral pad `RV_IL.n` on `NEUTRAL` (X 27.0 to 29.0, Y 46.3 to 48.3); the timing strip's mains copper is X 19.8 to 29.0 and 37.0 to 55.3 and its pocket X 60.3 to 65.3. **The interlock relay's length.** The datasheet's drawing gives 41 mm overall for the vertical-terminal variant (the ordering code without the 3) and 45 mm for the horizontal-terminal variant, whose 41 mm is the span to its terminal's holes and 31.5 mm to the back of its body (P2); the floorplan draws 41.0 mm and **requires the vertical-terminal variant**, since the horizontal variant's quick-connect tabs would stand a further 4 mm toward the tab pads, to X 13.0, over the link pours, where nothing here draws them.

### The low-voltage blocks

| Block | Function | X (mm) | Y (mm) | Size (mm) | Area (mm²) | Allowance and basis |
|---|---|---|---|---|---|---|
| `MCU` | Controller, STM32H743VIT6, decoupling, crystals, reset, boot, programming header, 3.3 V regulator | 72.0 to 104.3 | 95.6 to 126.7 | 32.3 × 31.1 | 1005 | Estimate: LQFP-100 land 17.5 × 17.5 mm (306) + 40 passives (432) + HSE and LSE crystals (66) + programming header (70) + reset switch and boot link (60) + regulator and its two capacitors (68) = 1 002 mm², drawn 1 005 (A4, P5): the one block drawn with no allowance, because the board's top edge and the 15.0 mm it keeps from the module leave it 31.1 mm of height; it had 87 mm² of margin before the voltage measurement moved under the module |
| `CON2` | Panel harness header CON2, 9 ways, 2.0 mm pitch | 124.5 to 131.5 | 76.0 to 96.5 | 7.0 × 20.5 | 144 | Footprint (A5) |
| `SP2` | Gauge harness header SP2, 9 ways, 2.0 mm pitch | 124.5 to 131.5 | 98.0 to 118.5 | 7.0 × 20.5 | 144 | Footprint (A5) |
| `KNOB` | Knob microswitch header, 4 ways, 1.95 mm pitch | 113.6 to 124.0 | 108.0 to 115.0 | 10.4 × 7.0 | 73 | Footprint (A5) |
| `FLOW` | Flow meter header CZ1, 3 ways, 2.54 mm pitch | 113.9 to 124.0 | 98.0 to 105.5 | 10.1 × 7.5 | 76 | Footprint (A5) |
| `TEMP_C` | Coffee-block thermistor header RT1, 2 ways, 2.54 mm | 117.0 to 124.0 | 86.0 to 93.5 | 7.0 × 7.5 | 53 | Footprint (A5) |
| `TEMP_S` | Steam-block thermistor header, 2 ways, 2.54 mm | 117.0 to 124.0 | 76.0 to 83.5 | 7.0 × 7.5 | 53 | Footprint (A5) |
| `TEMP_W` | Wand thermistor header, 2 ways, 2.54 mm, fitted rotated 180 degrees | 114.0 to 121.0 | 119.0 to 126.5 | 7.0 × 7.5 | 53 | Footprint (A5) |
| `DRV_K1` | Coil driver for K_V1: transistor, flyback diode, pull-down | 65.5 to 72.0 | 80.6 to 90.7 | 6.5 × 10.1 | 66 | 3 passives and a transistor and a diode: 18 + 10 + 3 × 10.8 = 60 mm², drawn 66 to sit against the relay pocket, 10.3 mm from the mains copper of `P_C` |
| `DRV_K2` | Coil driver for K_V2 | 65.5 to 72.0 | 116.5 to 126.6 | 6.5 × 10.1 | 66 | As `DRV_K1` |
| `DRV_PC` | LED drive for the coffee pump's opto-triac | 66.0 to 72.0 | 93.1 to 102.1 | 6.0 × 9.0 | 54 | Transistor, base resistor, pull-down, LED resistor: 18 + 3 × 10.8 = 50 mm², drawn 54 |
| `DRV_PS` | LED drive for the steam pump's opto-triac | 66.0 to 72.0 | 105.1 to 114.1 | 6.0 × 9.0 | 54 | As `DRV_PC` |
| `DRV_TIM` | Output conditioning of the timing optocoupler | 66.5 to 72.5 | 2.7 to 8.7 | 6.0 × 6.0 | 36 | Two passives: 22 mm², drawn 36 |
| `FE_GAUGE` | Gauge drive: octal buffer, five pull-downs, two decoupling capacitors | 72.0 to 93.5 | 80.6 to 92.6 | 21.5 × 12.0 | 258 | SOIC-20 courtyard 15 × 11 = 165 + 7 × 10.8 = 76: 241 mm², drawn 258 (R3 § Gauge drive) |
| `DRV_HEAT` | LED-drive stages for the two heater opto-triacs | 94.0 to 102.5 | 79.8 to 91.8 | 8.5 × 12.0 | 102 | 2 × (transistor 18 + 3 passives 32) = 100 mm², drawn 102 |
| `FE_PANEL` | Operator panel: gate switch for the anode rail, five key pull-ups, buzzer switch | 105.0 to 115.0 | 75.0 to 91.0 | 10.0 × 16.0 | 160 | The forms record's three transistors and five resistors: 3 × 18 + 5 × 10.8 = 108, plus three base and pull-down resistors 32: 140 mm², drawn 160 |
| `FE_NTC` | Three thermistor dividers with filter capacitors | 105.5 to 113.5 | 92.5 to 106.5 | 8.0 × 14.0 | 112 | Three passives per channel (R2 of the forms record, SBAA338): 9 × 10.8 = 97 mm², drawn 112 |
| `FE_FLOW` | Flow input: pull-up, series resistor, filter capacitor, Schmitt buffer footprint and its link | 105.0 to 113.0 | 107.5 to 117.5 | 8.0 × 10.0 | 80 | 3 × 10.8 + 25 + 10.8 = 68 mm², drawn 80 |
| `FE_STMD` | Steam-transducer digital header protection: two series resistors, two pull-ups, two clamps | 105.0 to 113.0 | 118.5 to 126.5 | 8.0 × 8.0 | 64 | 4 × 10.8 + 2 × 8 = 59 mm², drawn 64 |
| `POL` | Proof-of-life circuit that drives K_IL's coil: a buffer, two charge-pump channels and two series FETs (*The drive*) | 70.5 to 82.5 | 31.0 to 43.0 | 12.0 × 12.0 | 144 | Estimate: 19 parts: one buffer 8, two FETs 16, four pump diodes 20, four clamp parts 20, eight passives 32 = 96 mm², with a third for routing 128 mm², drawn 144; marked an estimate, the parts are the schematic leaf's |
| `BREW_D_C` | Brew-path pressure, digital header protection | 87.5 to 97.5 | 31.0 to 39.0 | 10.0 × 8.0 | 80 | 59 mm², drawn 80 |
| `FE_KNOB` | Knob microswitch inputs: two pull-ups and two filter capacitors | 71.0 to 79.0 | 43.5 to 49.5 | 8.0 × 6.0 | 48 | 43 mm², drawn 48 |
| `FE_WATER` | Tank-level input conditioning and the low-water indicator sink | 108.5 to 116.5 | 32.0 to 40.0 | 8.0 × 8.0 | 64 | Reed pull-up and filter 22 + transistor 18 + two resistors 22 = 62 mm², drawn 64 |
| `IN_COND` | Input conditioning for the zero crossing, and the two mains-presence inputs, which stay reserved | 98.0 to 108.0 | 31.0 to 39.0 | 10.0 × 8.0 | 80 | Six passives: 65 mm², drawn 80 |
| `WB_LV10` | Header for the heater wall board's low-voltage cable, 10 ways, 2.54 mm | 123.7 to 131.2 | 44.5 to 72.5 | 7.5 × 28.0 | 210 | Footprint (A5) |
| `STM_D` | Steam-transducer digital header, 4 ways (3V3, GND, SCL, SDA) | 93.0 to 100.5 | 65.3 to 77.9 | 7.5 × 12.6 | 95 | Footprint (A5) |
| `BREW_D` | Brew-path pressure digital header, 4 ways | 108.1 to 115.6 | 44.5 to 57.1 | 7.5 × 12.6 | 95 | Footprint (A5) |
| `PT1_H` | In-stream probe 1 header, 4 ways | 115.9 to 123.4 | 44.5 to 57.1 | 7.5 × 12.6 | 95 | Footprint (A5) |
| `BREW_A` | Brew-path pressure analogue header, 4 ways | 108.1 to 115.6 | 57.4 to 70.0 | 7.5 × 12.6 | 95 | Footprint (A5) |
| `PT2_H` | In-stream probe 2 header, 4 ways | 115.9 to 123.4 | 57.4 to 70.0 | 7.5 × 12.6 | 95 | Footprint (A5) |
| `SPARE_A` | Spare analogue header for the steam transducer's analogue fallback, 4 ways (5V, 3V3, GND, input) | 85.2 to 92.7 | 44.5 to 57.1 | 7.5 × 12.6 | 95 | Footprint (A5) |
| `SPARE_AN2_H` | Second spare analogue header, 4 ways | 85.2 to 92.7 | 57.4 to 70.0 | 7.5 × 12.6 | 95 | Footprint (A5) |
| `CURR1_H` | Current-sensing header, first channel, 3 ways | 93.0 to 100.5 | 44.5 to 54.6 | 7.5 × 10.1 | 76 | Footprint (A5) |
| `CURR2_H` | Current-sensing header, second channel, 3 ways, 2.54 mm | 93.0 to 100.5 | 54.9 to 65.0 | 7.5 × 10.1 | 76 | Footprint (A5); kind 5, in the column of `CURR1_H`, 0.3 mm from it and from `STM_D` |
| `WT1_H` | Weight channel 1 load-cell header, 5 ways, 2.0 mm | 100.8 to 107.8 | 44.5 to 57.0 | 7.0 × 12.5 | 88 | Footprint (A5, at the 2.0 mm pitch it assumes for these headers; the owner gives 7.0 × 12.5 mm); kind 2 |
| `WT2_H` | Weight channel 2 load-cell header, 5 ways, 2.0 mm | 100.8 to 107.8 | 57.3 to 69.8 | 7.0 × 12.5 | 88 | As `WT1_H` |
| `PT1_C` | In-stream temperature converter 1: RTD-to-digital converter, reference resistor, capacitors | 76.5 to 90.5 | 3.0 to 13.0 | 14.0 × 10.0 | 140 | SSOP-20 courtyard 72 + 6 × 10.8 = 137 mm², drawn 140; in the analogue region, 20.0 mm from the interlock relay |
| `PT2_C` | In-stream temperature converter 2 | 91.0 to 105.0 | 3.0 to 13.0 | 14.0 × 10.0 | 140 | As `PT1_C` |
| `FE_SPAREA` | Spare analogue input (the steam transducer's analogue fallback): divider, filter, series resistor, clamp | 105.5 to 115.5 | 3.0 to 11.0 | 10.0 × 8.0 | 80 | 4 × 10.8 + 8 = 51 mm², drawn 80; in the analogue region |
| `BREW_A_C` | Brew-path pressure, analogue fallback: divider, filter, clamp | 78.0 to 88.0 | 14.5 to 22.5 | 10.0 × 8.0 | 80 | 51 mm², drawn 80; in the analogue region, 20.0 mm from the interlock relay |
| `SPARE_AN2_C` | A second spare analogue input: divider, filter, clamp | 88.4 to 97.8 | 14.5 to 22.5 | 9.4 × 8.0 | 75 | 51 mm², drawn 75 (it was 80; the margin is 47 % instead of 57 %, to leave kind 5 its row); in the analogue region |
| `CURR1_C` | Current-sensing channel 1: burden and filter | 98.2 to 104.2 | 14.5 to 22.5 | 6.0 × 8.0 | 48 | 3 × 10.8 = 32 mm², drawn 48 as 6 × 8 mm; in the analogue region |
| `I_C` | Supply current measurement (kind 9): conditioning of the isolated shunt channel | 104.6 to 110.6 | 14.5 to 22.5 | 6.0 × 8.0 | 48 | 3 × 10.8 = 32 mm², drawn 48; conditions the isolated output of `VMEAS`'s shunt channel; in the analogue region |
| `CURR2_C` | Current-sensing channel 2: burden and filter | 111.0 to 117.0 | 14.5 to 22.5 | 6.0 × 8.0 | 48 | 3 × 10.8 = 32 mm², drawn 48 as 6 × 8 mm; in the analogue region; kind 5 |
| `WT1_C` | Weight channel 1: HX711-class amplifier (SOP-16L) and its passives | 78.0 to 97.0 | 22.9 to 30.1 | 19.0 × 7.2 | 137 | The amplifier's courtyard 11.0 × 7.4 = 81 mm² and five passives 54 mm² = 135.4 mm², drawn 136.8 as a row (A27, P11); in the analogue region, 20.0 mm or more from the module and 20.0 mm or more from the interlock relay; kind 2 |
| `WT2_C` | Weight channel 2: HX711-class amplifier and its passives | 97.5 to 116.5 | 22.9 to 30.1 | 19.0 × 7.2 | 137 | As `WT1_C` |
| `VM_C` | Supply-voltage measurement: conditioning of the isolated output | 116.0 to 122.7 | 3.0 to 10.2 | 6.7 × 7.2 | 48 | A divider, a filter capacitor and a clamp: 3 × 10.8 = 32 mm², drawn 48 as `I_C` is; in the analogue region, 20.0 mm or more from the module and from the interlock relay; the isolated signal reaches it from the pocket of `VMEAS` over a low-voltage trace of about 60 mm; kind 1 |
| `REED` | Tank reed element pads, hand-fitted, with its body strip and hand access | 117.0 to 127.0 | 12.5 to 42.5 | 10.0 × 30.0 | 300 | Pads at (122.0, 17.5) and (122.0, 37.5), 20.0 mm apart along Y; the rectangle is the bounding box of the keep-out of § The tank reed (a body strip and 5.0 mm round each pad, A17), not a part |

**Block areas and their allowance.** The allowance for the support parts that no part selection has yet named is stated in every row: a block's drawn area is the sum of its named parts' footprints and the allowance for its support passives (A4), plus a margin of 8 to 70 %, the larger where a block is drawn to the height of the part beside it. Its basis is the counts of the reference designs the forms record cites: **ST AN4938 Rev 7, Tables 8 and 9** give the controller's reference design 23 mandatory passives (20 of 100 nF, one of 4.7 µF, two of 2.2 µF) and 17 optional ones (five 10 kΩ, one 0 Ω, four 100 nF, two 1.5 pF, three 1 µF, two 3.9 pF) that is 40 passives, the number used for `MCU`, the two crystals counted apart (that table is for the TFBGA240; the 100-lead package has fewer supply pins, so 40 is an upper bound; P5); **TI SBAA338** gives three passives per thermistor channel; and the forms record states the per-channel passives of the flow input, the panel (three transistors and five resistors), the heater drive stages and the low-water stage. A row whose basis is not one of those is marked as an estimate there. The part-level regions of each block are the board design task's.

**The sum of the blocks.** The mains-side bodies total 5 289 mm² (the strip of the tab pads, the neutral pour and the link pours 1 085.4 and the eleven blocks 4 203.3) and the low-voltage blocks 5 244 mm²; with the reed's keep-out box, 300 mm², that is **10 833 mm² of the 16 375 mm² outline, 66 %**, leaving 5 542 mm² for routing, the slots and the spacing between blocks. That free area is not usable for low-voltage circuits as its size suggests: most of it lies in the mains zone, where a low-voltage block must stand 10.0 mm from mains copper, and the rest is bounded by the two heat sources' 20 mm keep-out for sensing blocks (A8), the lead-end rule along the intrusions, the reed's hand access and the lid-screw circles. These, not the free area, decide what fits (§ The anticipated channel kinds).

### Heights, the underside, and hand access

| Part | Height above the board (mm) | Ceiling here (mm) | Margin |
|---|---|---|---|
| `MODULE` IRM-20-5 | 24.0 (P1) | 27.9; it lies 32.5 mm or more from every edge, so the 23.3 mm limit does not apply | 3.9 mm |
| Relays `K_V1`, `K_IL`, `K_V2` | 15.7 for `K_IL` (P2), 12.7 for the valve relays (P6) | 27.9; the left end of `K_IL` is 17.0 mm from the open left side | 12.2 mm |
| Tabs and the return landing | The blade stands 9.9 mm clear (`connector-pinouts.md`); the bought tab's drawing (P15) gives the blade length, 14.3 mm, and not the height it stands, so that height is unread and the layout task reads it | 27.9 | 18.0 mm above the bare blade |
| Fuse holders | 15 at most (A6) | 27.9 | 12.9 mm |
| Harness headers on the right, within 2 mm of the right wall | Under 15 (the makers' sheets are not read; A5) | 23.3 | At least 8.3 mm |

The tallest part on the original board was measured at 28 mm and the machine record calls it its AC/DC module; the ceiling of 27.9 mm stands on that height, and the replacement module is 24.0 mm. The original board's circuit diagram shows a transformer `T1` (230 V, 9 V, 2.5 VA) as its control supply and no AC/DC module, so the part measured as the tallest is probably `T1` (inferred); the ceiling is the measured height whichever part it is.

**Underside.** Economic assembly places one side, so nothing is fitted on the back; only through-hole lead ends reach it. With the 4 mm standoffs and a 1.6 mm board, a lead end protrudes by the part's pin length less the board (P1: the module's pins are 3.5 ±1 mm below its body, so 1.9 mm, 0.9 to 2.9) against 0.5 mm (−0.2 to 1.2) of room over intrusion 1 and 2.15 mm (1.45 to 2.85) over intrusion 2. **No lead end is placed over either.** The checks: the module's DC pins at (80.9, 56.6) and (80.9, 64.6) lie 12.9 and 20.9 mm above the top of intrusion 1 at X = 80.9, Y = 43.7; the interlock relay's coil holes at X = 55.5 lie 2.5 mm left of intrusion 1's corner at X = 58 and the valve relays' pins are 35 mm or more above it, and the script holds any lead end beside the straight edge at least the intrusion's position tolerance, ±0.5 mm (`reference-machine.md`), from it (the nearest lead end beside it is the reed's lower pad, 16.5 mm beyond its far face); every through-hole header lies either at X = 105.5 or more, where there is no intrusion, or at Y = 44.5 or more (the intrusion's top is 43.5 mm at X = 85.2 and falls to the right); and the through-hole parts nearest the bottom wall are the reed's lower pad (Y = 17.5) and tab 1 (Y = 19.8), 14.5 mm above intrusion 2. The through-hole parts' lead ends are at least 1.0 mm outside both intrusions in the script's check.

### The tank reed

The element's lower lead is at (122.0, 17.5) and its upper lead 20.0 mm above it at (122.0, 37.5), so its midpoint is at (122.0, 27.5), **0 mm from the recorded position, inside the 1 mm tolerance** (`reference-machine.md`, remeasured by the owner on 2026-10-24: the lower hole 15.3 mm above the original board's bottom edge and 121.25 mm from its left edge). The script takes the element's midpoint from the two pads and checks it against the record. It is through-hole, with its body on the back face as on the original (inferred in the machine record). The lower pad is 12.0 mm from point 2's centre.

**Its keep-out** replaces an earlier hand-access rectangle that had no source. It is a body strip 4.0 mm wide along the 20 mm between the pads (the element and its insulating compound) and a hand-access zone of **5.0 mm radius round each pad**, for the iron and a finger. Both are assumptions (A17), stated as such; the zone's bounding box is X 117.0 to 127.0, Y 12.5 to 42.5, centred on the midpoint, and it clears the point 2 lid-screw circle by 2.5 mm. **Nothing lies in it**: the script checks every block, tab pad and fixing against the strip and the two circles. Two blocks stood in the new zone and moved: the wall board's header `WB_LV10` and the spare analogue header `SPARE_A` (their places are in the table of the low-voltage blocks). The reed is hand-fitted and is not counted in the manufacturer's assembly. Over the back face at X = 122 there is no intrusion (intrusion 1 ends at X = 105.5).

### Heat

The heat sources of a watt or more on the main board are two. **The logic supply**: the module's own derating curve reaches 50 % of its rated current at 70 °C (P1), so the most it delivers there is 10 W at 5 V; at its typical 79 % efficiency (P1) it dissipates 10 / 0.79 − 10 = **2.66 W** (5.32 W at its full 20 W, which the curve does not allow at 70 °C), and it dissipates **1.25 W at this board's load** of 0.94 A, 4.70 W out (§ The logic supply against this board). That figure takes the sheet's typical efficiency, which is given at rated load, over a load of 23 % of its rated 20 W, where the sheet gives none: it is flat-efficiency and an estimate, and a loss that falls in proportion to the load from 5.32 W at rated load to the sheet's 0.1 W at no load gives 1.32 W, 0.08 W more; either is over A8's watt. **The interlock relay** dissipates its coil, 0.4 W at its nominal 62 Ω (0.448 W with the coil 10 % under, at 55.8 Ω), and its contacts, which carry all of the machine's current: 0.58 W at the budgeted 4.8 mΩ and 10.96 A, so 0.98 W, and **1.03 W with the coil at the low end of its tolerance**: a source by A8's own figure, and by the owner's instruction of 2026-10-24 whatever the arithmetic. The valve relays' coils are 0.23 W each (P6) and the pump triacs carry 0.46 A and 0.19 A rms; none reaches a watt. The microcontroller and the regulator's dissipation are not recorded and sit inside the `MCU` block. The 70 °C air is an assumption; **the owner thinks it will not be real and expects to insulate the thermoblocks, and this record keeps 70 °C** so that the distances below stay on the cautious side.

| Part or block | From the module's body (mm) | From the interlock relay's body (mm) | Rule (A8) | Held |
|---|---|---|---|---|
| `MCU` | 15.0 | 63.8 | 15 | Yes |
| `FE_NTC`, the thermistor dividers | 23.8 | 75.8 | 20 | Yes |
| `PT1_C`, `PT2_C`, the RTD converters | 40.4, 40.9 | 20.0, 33.9 | 20 | Yes |
| `BREW_A_C`, `SPARE_AN2_C`, analogue inputs | 30.9, 31.1 | 20.0, 30.4 | 20 | Yes |
| `CURR1_C`, `I_C`, `CURR2_C`, current inputs | 33.6, 36.6, 40.4 | 40.2, 46.6, 53.0 | 20 | Yes |
| `WT1_C`, `WT2_C`, `VM_C`, the weight and voltage circuits | 23.3, 26.5, 53.2 | 20.0, 39.5, 58.9 | 20 | Yes |
| `FE_SPAREA`, the analogue fallback | 47.1 | 48.5 | 20 | Yes |
| `FE_GAUGE`, `POL`, `DRV_HEAT`, digital stages | 0.0, 10.4, 9.1 | 49.2, 12.5, 58.7 | None: no part there derates or senses | Not applicable |
| The 85 °C part `K_V1`, the two-way valve relay | 0.0 | 47.2 | 15 | **Not held** (from the module) |
| The 85 °C part `K_V2`, the three-way valve relay | 35.9 | 83.1 | 15 | Held |
| The 85 °C part `P_C`, the coffee pump's opto-triac | 12.5 | 59.7 | 15 | **Not held** (from the module) |
| The 85 °C part `P_S`, the steam pump's opto-triac | 24.5 | 71.7 | 15 | Held |
| The 85 °C part `VMEAS`, the voltage measurement's isolating part | 0.0 | 15.0 | 15 | **Not held** (from the module; held from the relay, as the owner requires) |
| The interlock relay `K_IL`, against the module | 20.0 | | 15 (the owner's figure) | **Held** |
| `TIMING`, the timing optocoupler, outside the class (100 °C, 30 K over the air, P12) | 43.9 | 11.2 | None: no distance is claimed | Outside the class |

**The interlock relay is held from the module and is now a source itself.** `K_IL` stands 20.0 mm from the module's body; the voltage measurement, 15.0 mm above the relay's body, stands between them, directly below the module. The two sensing blocks that stood within 20 mm of the relay, `BREW_A_C` (10.0 mm) and `PT1_C` (16.9 mm), moved right to 20.0 mm and 20.0 mm, which the analogue region holds, with kind 5, at the spacing the drawing keeps (§ The anticipated channel kinds); the weight and voltage circuits stand 20.0 mm or more from it. The relay choice is still not proven until the bring-up measurement (§ The interlock block). The script tests the microcontroller, every sensing block and every 85 °C part against both sources, and the heat lists name every low-voltage block: one that is in none of them fails.

**The parts rated to 85 °C.** A8 asks 15 mm of every part that derates. Besides the microcontroller, the mains-side parts rated to 85 °C are the valve relays (−40 to 85 °C, P6), the pump opto-triacs (taken as 85 °C, A21) and the voltage measurement's isolating part (not chosen, 85 °C assumed, A21). A valve relay's own rise is about 61 K at the rated coil voltage by the sheet's temperature-rise line (read off the plot; the sheet does not say for which coil, standard or sensitive), which puts its winding at 146 °C at an 85 °C ambient against 155 °C for its insulation class F, and its coil is energised only while its valve is open, once per delivery, with contacts that carry 0.13 A. `TIMING`'s optocoupler (Lite-On LTV-814S) is rated to 100 °C (P12), 30 K over the air against the 15 K of the class, so it is listed outside the class with its distances and no claim. Against the two sources, **three of the five stand under 15 mm, each from the module: `K_V1` against the module's body (0.0 mm), `VMEAS` directly below it (0.0 mm) and `P_C` 12.5 mm above it**; `P_S` (24.5 mm) and `K_V2` (35.9 mm) hold, and all five hold from the relay. The entry varistor `RV_IL` is not among the five: its temperature class is not read (A33), so it is not counted as an 85 °C part (§ Reported for the board design tasks, item 33).

**Why they cannot all hold, computed.** A barrier part's pocket stands at the zone boundary: a low-voltage trace to a pocket inside the mains zone needs a channel across the stack. Kept 10.0 mm from every mains conductor by distance alone, a trace needs 20.3 mm between mains copper (2 × 10.0 mm and the trace) and the widest gap between mains copper along the stack is 10.3 mm; with a slot down each side the rules ask only 3.0 mm straight and 10.0 mm by path, which that gap would give, but a channel from the left column to the low-voltage zone divides the mains copper above it from the mains copper below it, and the `LINE` and `NEUTRAL` taps feed pieces on both sides (the module's pads above, the timing front end and the link below), so they would have to cross it, on a layer where the planes are pulled back 10.0 mm from mains copper as well. No pocket is drawn inside the mains zone. Along the boundary, the stretch that stands 15 mm or more from both sources is Y 2.3 to 5.7 and Y 95.6 to 126.7, 31.1 mm; the five parts need 55.2 mm there (10.1 + 10.1 + 9.0 + 9.0 + 5.0 and four gaps of 3.0 mm), so at most 3 of them fit. The script counts every arrangement of the five along the column: each position of the module from 15 mm above the relay's body, each split of the parts above or below it, each order, with the four parts that are fed from a tab in tab order (a lead cannot pass another net's copper in the 8.0 mm channel between the pads and the stack) and `VMEAS` no nearer the relay than 15 mm. **At most 3 hold, and every arrangement that holds 3 stands K_V1 between the two sources.** The drawn stack holds 2. The two arrangements that hold 3 with K_V1 between the sources, built in the data as the first two what-ifs, hold K_V2, P_C, P_S and K_V2, P_C, P_S. The first, with the module at its lowest and `VMEAS` above it, breaks two rules that decide it: WT1_C stands 18.3 mm from the module against A8's 20, and the region AR_b stands 17.4 mm from the module (a trace from tab 6 to the relay's contact copper exists, since only the shared fuse's two clips are copper and not the holder's whole body). The second, with the module where it stood and `K_V1` and the shared fuse in the gap between the sources, breaks two that decide it: no trace reaches the pad of tab 3 from the rest of the `LINE` and `NEUTRAL` copper, because the fuse closes the way out between itself and the pad column, and the region AR_b stands 19.1 mm from the module. With the entry parts drawn, each of the three what-ifs also runs into them, because the gap the arrangements use is where the entry fuse holder and the varistor stand: the script reports those collisions among the rules each breaks (the first breaks 4 rules in all, the second 13, the third 3), and they are a consequence of the entry parts' place and not a further reason against the arrangements. **The record finds no arrangement that holds 3 and meets every rule, and does not prove there is none**: another place for the shared fuse or for `VMEAS` is the owner's to ask for (§ Reported for the board design tasks, item 19).

**The room tabs 4 and 5 left does not help the 85 °C parts.** The two pads and the 8.0 mm channel kept for their leads are gone, which leaves the left column X 5.0 to 17.0 free of mains copper from Y 49.0, the top of the neutral pour, to Y 78.4, the foot of the pad of tab 6: 29.4 mm. A part there would stand 15.5 mm from the module, whose body starts at X 32.5, and above Y 48.4 15 mm or more from the relay, so it would hold A8 against both sources. But every barrier part has a low-voltage pocket whose traces need a route to the low-voltage zone, 44 mm or more to the right, and the argument above shuts that route: no pocket is drawn in the column, and the stretch of the boundary that stands 15 mm from both sources stays 31.1 mm against the 55.2 mm that the five parts need. What the room does give is the neutral return's landing and shunt (§ The path of the heater current), and the fuse holder `VFUSE` its clearance from the pad column.

**Three of the five can hold, at a price (the third what-if).** The module can stand 3.3 mm lower, at Y 50.1, the lowest the sensing blocks allow, if the voltage measurement leaves the gap under it. The third what-if puts it in the gap the module left: P_C then stands 15.8 mm from the module and holds, as K_V2 (39.2 mm) and P_S (27.8 mm) do; K_V1 then stands 3.3 mm from the module and VMEAS then stands 0.0 mm from the module, and the voltage measurement would then stand 11.7 mm from the relay's body against the owner's 15; and the region AR_b stands 19.1 mm from the module, so its top edge would return to Y 30.1: cut back to Y 30.1, its capacity falls from 1 189.7 to 1 154.3 mm² against the 1 066.7 the drawn blocks need, 87.6 mm² spare, so kind 5 stays. The third what-if holds K_V2, P_C, P_S: three parts, and fails two (K_V1, VMEAS), at a cost of 3.3 mm of VMEAS's distance from the relay and 35.4 mm² of the analogue region; the drawn one holds two (K_V2, P_S) and fails three (K_V1 and VMEAS, 0.0 mm from the module each, and P_C, 12.5 mm). **The record draws the arrangement that keeps the owner's 15 mm for VMEAS and keeps kind 5; the choice between the two is the owner's (an owner decision pending, § Owner decisions pending, D4)** (§ Reported for the board design tasks, item 19).

**Bring-up measures the body of `K_V1`, `P_C`'s opto-triac and `VMEAS`'s isolating part beside the running module against 85 °C**, and the part is moved or changed if it exceeds that; the module dissipates 1.25 W at this board's load, and the owner expects the air to be cooler than the assumed 70 °C. If `K_V1` is the one that fails, the HF115F-Q (125 °C, 41.0 mm long against the 17.6 mm of the HF32FA-G) is the stated fallback, and it is not a swap: the column holds no 41 mm stretch for it, so the valve column would be redrawn.

### The logic supply against this board

The module's size rests on the 5 V this board's own loads draw; the 0.66 to 0.86 A of the working design was a scale only and not this board's budget (`controller-board-function-forms.md` § Low-voltage supply). The table sums them, and each row says what it is read from. Relay coils are taken at the low end of the sheets' ±10 % tolerance on the coil resistance, so at their highest current, the controller at the sheet's maximum for its busiest state, and each load no record fixes is an assumption with a token in A28.

| Load | mA at 5 V | Grade and source |
|---|---|---|
| K_IL coil | 89.6 | Sheet: 62 Ω ±10 % (P2): 80.6 mA at 62 Ω and 89.6 mA at 55.8 Ω, the low end of the tolerance, which is the figure used; the full drive and nothing else (the reduced-hold drive is dropped) |
| Valve relay coils | 102.9 | Sheet: two coils of 108 Ω ±10 % (P6): 46.3 mA each at 108 Ω and 51.4 mA each at 97.2 Ω, which is the figure used |
| Controller | 439.0 | Sheet: STM32H743 at 480 MHz, regulator mode VOS0, all peripherals enabled, code in ITCM, 439 mA at a junction of 85 °C and 226 mA typical at 25 °C (P10, Table 119); passed through a linear 3.3 V regulator, so the 5 V rail carries all of it (the constraints record prices an AMS1117-3.3) |
| Gauge drivers | 72.0 | Record: about 18 mA a phase at 5 V in a 280 Ω coil, four phases, a conditional bound and not a measurement (`connector-pinouts.md` § Gauge and water-indicator board, *What the driver's control lines ask for*) |
| Weight amplifiers | 3.0 | Sheet: 1.5 mA each in normal operation, two (P11) |
| Load-cell excitation | 28.6 | Assumption (A28): two bridges of 350 Ω across 5 V |
| Opto-triac LED drives | 60.0 | Assumption (A28): four LEDs, two heater and two pump, at 15 mA, inside the 5 to 60 mA of the forms record |
| Panel indicators and buzzer | 60.0 | Assumption (A28) |
| Flow meter | 15.0 | Assumption (A28) |
| Pressure transducers | 20.0 | Assumption (A28), two |
| In-stream probe converters | 4.0 | Assumption (A28), two |
| Current sensors | 30.0 | Assumption (A28), three: the first channel's, the second channel's (kind 5) and the supply current's (kind 9) |
| Voltage measurement output | 5.0 | Assumption (A28) |
| Headers, pull-ups and dividers | 10.0 | Assumption (A28) |
| **Total** | **939 mA** (0.94 A) | 726 mA with the controller at its typical 226 mA |

| Module | At 70 °C: current and times the load | At 50 °C: current and times the load | Footprint (mm²) | Notes |
|---|---|---|---|---|
| IRM-20-5 | 2.0 A, **2.13** | 3.6 A, **3.83** | 1425 | 52.4 × 27.2 × 24 mm, 4 A rated; the sheet's chart for the 5 V model holds 100 % to 45 °C and 50 % at 70 °C (P1), so 90 % at 50 °C by the straight line between; 79 % efficient typically |
| IRM-10-5 | 1.0 A, **1.06** | 2.0 A, **2.13** | 1161 | 45.7 × 25.4 × 21.5 mm, 2 A rated; the chart holds 100 % to 50 °C and 50 % at 70 °C (P7); 77 % efficient typically, not the 82 % of the 12 V and higher models |

**The choice.** The forms record calls 2.3 times adequate and 1.16 times thin (§ Low-voltage supply), and the owner's figure is 2 times. At 70 °C the IRM-20-5 has 2.13 times this board's load and the IRM-10-5 has 1.06, so the smaller module does not reach 2 and **the module stays the IRM-20-5**; the script fails if the chosen module has under 2.0 times, and fails if the smaller one reaches it, so the record is corrected on the day it does. At 50 °C, which the owner expects once the thermoblocks are insulated, the IRM-10-5 would have 2.13 times, and would save 264 mm² (1 425 against 1 161) and 2.5 mm of height. **The air is not measured**, so the smaller module is the owner's to take up after bring-up has measured it (an owner decision pending, § Owner decisions pending, D6); taking it up changes the module's block, pins and heat rows and the forms record's disagreement list (§ What this record's words depart from in the forms record). The controller's 439 mA is its figure with every peripheral on at full speed, which the firmware is not expected to reach; at its typical 226 mA the budget is 726 mA and the IRM-10-5 would have 1.38 times at 70 °C, still under 2. The IRM-20-5 delivers 4.70 W at this load and dissipates 4.70 / 0.79 − 4.70 = 1.25 W, an estimate at 79 % that the sheet gives only at rated load (§ Heat).

### The checks, stated

The script of § Appendix reads the data block and the source records and prints, for the main board: the sources it compared and the assumption tokens; the outline and its margins; the heights against the ceiling; the tabs' pitch, moves and slack and the strip derived from the pads; the least mains-copper distance to every mounting hole, **13.27 mm** against the rule's 13.25, and that each moved tab is needed; the distance of every mains rectangle from each of the four holes; the reed's lead positions and keep-out, clear of every block; the least distance from a low-voltage block to mains copper, **10.3 mm** (rule 10.0); the pocket pairs and the least surface path round the slots, **12.9 mm** (rule 10.0); the isolating parts' pin paths; the slot path per board; every pair of mains copper of different nets, the tab pads and the link pours included, and those across the open contact; the interlock relay's terminals against the sheet's drawing; the interlock's link, its loss, its taps and the loads behind it against its rating; the neutral return (the landing's pad, the pour, the shunt's lands, their widths against 15 A, the landing's pitch from the tabs, the shunt's loss, and the neutral taps leaving the pour above the shunt); the shortest routes of a trace, with its half width and a margin, from the first piece of a net to each of the others; each retained harness header within its reach of the cut-away (§ Harnesses); the heat distances against both sources, with the 85 °C class listed, the arithmetic of why they cannot all hold, the count of every arrangement and the three what-ifs that hold a third part, the analogue regions' distance from both sources and their top edge, and the relay moved right to make room for a sensor 8 mm long; the removal steps of § The anticipated channel kinds and the kinds kept or removed against the blocks drawn; the valve relay's ratings against the loads and the supply; the 5 V rail's budget against both modules; the shared fuse's arithmetic and the breaking capacities found; the function and harness coverage against their source records; the parts, joints and header types counted from the blocks, and the cost totals. **It is a consistency check, not a proof that the inputs are right**: it fails when its arithmetic breaks a rule this record states, when a figure that has a source record differs from it, when an assumption differs from its token, or when a table of this file differs from the data. It does not say the sources are right, and an edit made to an assumption's row and to the data together passes (§ How this record is built).

## The heater path, the interlock and the wall board

### The path of the heater current, and what carries mains

The board as found switches the neutral side of every load: `LINE1` reaches each load by the retained daisy-chain wire and the load's other lead ends on its tab (`connector-pinouts.md` § The source of each live feed). `LINE1` is also a pass-through on the board as found: nothing else on the board connects to it, and the script holds that sentence of the connector record. **The supply path of every heater, and of every pump and valve, is therefore** as the data block's ordered link and the wall board's chain list it, for the steam element:

`LINE` (tab 2) → the pad of tab 2, inside the pour **`LK_L`** (net `LINE_IN`, before the fuse) → an inner-layer run (A32) to the line-side clip **`F_IL.i`** of the entry fuse holder → **the 10 A entry fuse** → its load-side clip **`F_IL.o`** (net `LINE`) → the relay's contact half **`K_IL.a`**, through its two legs → **the contact of `K_IL`** → the contact half **`K_IL.b`** → the link pour **`LK_L1`** that holds the pad of tab 1 (`LINE1`) → the retained daisy-chain wire to the element's fixed lead → the element → its series thermostat → the element lead's female terminal, **plugged onto an in-line insulated male-to-male blade joiner** (*The joiners*, below) → a new wire to blade terminal `OUT_S` on the wall board → copper **S1** → triac `TRI_S` → copper **S2** → the common-return pour **RC** → the `RET` pad, a blade terminal → a wire back to the main board's **return landing `WB_RET`** → the neutral pour **`LK_N`** → the **shunt `I_SHUNT`** → the pad of tab 3 → the retained `NEUTRAL` lead's female terminal.

The coffee element goes through its own joiner, `OUT_C`, copper S1, `TRI_C` and copper **S3** into the same pour RC and from there along the same path: `RET`, the wire back, the landing, the shunt and the pad of tab 3. **The contact opens the live feed**, so it lies in series with each heater's supply path and also in the supply path of each pump and each valve coil, whose live leads come from the same `LINE1` wire. **The taps**: the module's AC pins, the timing front end's input and the voltage measurement's input leave the chain downstream of the entry fuse and upstream of the contact, at the fuse's load-side clip `F_IL.o` on `LINE` and at the neutral pour `LK_N`, above the shunt, on `NEUTRAL` (the `taps` of the data block), so the controller keeps power when the contact opens. **The short copper region that bridges the heater current out and back is the wall board's S1 to `RET`**, no run longer than 7.0 mm and 26.0 mm of copper in all from an element's blade terminal through its triac to the return pad (the steam and the coffee path alike), none across the board. The retained element lead keeps its female terminal and plugs onto a joiner, so **the heater current touches the main board's copper in two places only**: the link between the pads of tabs 2 and 1, and the neutral return from the landing to the pad of tab 3. The link is 4.30 squares from the entry fuse's load-side clip through the relay's two contact halves to the pad of tab 1, which pass the machine's whole supply, 10.96 A with both elements, both pumps at their sizing currents and both valve coils (4.80 + 5.38 + 0.46 + 0.19 + 0.129 A) and 15 A in the fuse's overload band, in regions at least 5.75 mm wide against the 5.72 mm that 15 A needs at 0.381 mm for each ampere. The neutral return is the landing's pad (X 5.0 to 12.0, Y 45.875 to 47.325) in a pour 7.0 mm wide, then the shunt, then the pad of tab 3; it carries the heaters' 10.18 A and every other load's return, **11.01 A** in all with every load on (the link's 10.96 A and the module's 0.05 A, A30) and 15 A in the overload band, in copper 7.0 mm wide against the 5.72 mm that 15 A needs. The earlier ideas of a copper bridge on the board, out to the wall board and back, and of piggyback terminals on tabs 3, 4 and 5 are dropped (§ Options considered and dropped).

**Every load's return joins the neutral pour above the shunt.** The heaters' return arrives at the landing `WB_RET`. Each pump's triac ends, at its MT1 end, on a `NEUTRAL` piece of its strip, `P_C.N` and `P_S.N` (X 51.5 to 55.5, 5.0 mm from the strip's own copper, which now ends at X 46.5); the two valves' return runs through their shared fuse, whose neutral clip `VFUSE.n` (Y 50.5 to 55.5, 5.0 mm from the neutral pour) takes it, while its relay-side clip `VFUSE.v` stands at Y 69.5 to 74.5; and the module's neutral pad `MODULE.n` is the sixth. The data block lists the six returns (`return.branches`), each with the copper it ends on and the copper it joins, and the script checks that each ends on `NEUTRAL` copper, that **each joins the neutral pour `LK_N`, above the shunt, and none joins at the pad of tab 3, on the plug side**, where the shunt could not read its current and a stuck-on triac would not show, and that the returns joined above the shunt add up to every load's return, 11.01 A, no more and no less: a return left out, or moved to the pad of tab 3, fails it, and so does a shunt that is not in the data, which the script refuses by name. Four of the six join by copper on the surface: the heaters' through the landing's own pour, the valves' across the 5.0 mm between `VFUSE.n` and the pour, the module's by its tap from the pour. **The two pumps' do not**: the script searches for a surface trace from each piece to the pour that keeps the basic creepage from every other net and the signed 10.0 mm from low-voltage blocks, and **no surface route exists for `P_C.N` and `P_S.N`** (the channel between the tab pads and the strips is 8.0 mm wide, and a trace needs the basic creepage and its own half width from the copper on each side), so the data gives their join as an inner layer of the four-layer board and the script requires that no surface route exist for them. That an inner layer can carry it, with the signed distances kept on that layer, is **an assumption (A32) and not a check** of this record; it is the main board's design task's (§ Reported for the board design tasks, item 31).

**Which board carries mains as a result.** The main board carries mains in its left zone (the seven tabs and the return landing, the link, the neutral pour and its shunt, the relay's contact end, the module's input, the voltage measurement, the pump and valve circuits) and low voltage in its right; the heater wall board carries mains and the low voltage that drives its parts. They are joined by **two cables that do not meet**: three mains conductors (the two element wires from their joiners and the return to the landing, out through the left of the cavity) and a low-voltage cable of three conductors in use (from `WB_LV10` at the right of the board, out through the right cut-away with the bundle). **The cable carries no coil drive**, since the relay is on the main board, and no signal from a sensor, since the current is sensed on the main board. Its signals, counted from the records, are the two LED lines of the heater opto-triacs and their 5 V supply: **three conductors**. The main board's ten-way header stays, with seven ways spare (four if the confirm places are ever fitted, which need three more), and the wall board's header is three ways. Neither cable crosses the board and neither passes the other.

**The joiners.** Each retained element lead keeps its female push-on terminal (nothing cut, lengthened or re-terminated) and plugs onto one blade of an in-line, insulated, male-to-male 6.3 mm blade joiner; a new wire with a female terminal at each end runs from the joiner's other blade to the wall board's `OUT_S` or `OUT_C`. The joiner is strapped or clipped to something fixed where the owner places it, so that the wire to the wall board is short and the joint does not hang on the lead or on the wire; the owner chooses the anchor (a cable tie to the loom, or a clip on the case wall), which this record does not place because the machine record holds neither the wall cut nor the leads' present ends. **The lead's reach is unknown**: the length of each element lead from where it left the old board's tab 4 or 5 to the thermoblock is not recorded, and the owner measures it with a rule; if a lead does not reach the joiner's place, the joiner stays at the lead's end and the new wire is lengthened by the shortfall (a wire of at least 1.5 mm², A10), so the joiner's place never moves the lead. The joiner's insulation and its current rating, 15 A in the overload band, are judged in § The heater wall assembly, judged, *The element harness*: no maker's rating was found, so the rating is absent.

**The return landing.** The wall board's return wire ends on a landing `WB_RET` of the main board: a pad of the tab's own section, 7.0 mm along X and 1.45 mm along Y (A2), at Y 46.6 in the `NEUTRAL` pour `LK_N`, 8.5 mm from tab 3 (the least tab pitch is 8.3 mm, so two female housings do not touch), taking the same board-mounted blade as the tabs (C20626104), so the return wire ends in a female push-on like the others. It is the eighth blade on the board but not a harness tab: no retained lead lands on it. The owner asked for a pad tied to the `NEUTRAL` copper and not a piggyback on tab 3's blade. If a solder pad for the wire is preferred it removes a blade and two hand joints and leaves the pour as it is; the choice is an owner decision pending (§ Owner decisions pending, D8; § Reported for the board design tasks, item 6).

**Why the contact is where it is.** A shorted triac holds its element energised whatever the controller commands, so only a series element that removes power independently of the switching device protects: it must lie in every path that powers a heater. The conductor that feeds each heater's hot side is `LINE1`, and its only source on the board is the link from `LINE` (tab 2), so one contact there cuts both heaters and a shorted triac holds nothing: its element has no live feed. The varistor lies across the triac on the wall board and is no path round the contact; the logic supply and the timing front end are tapped upstream of the contact, on the side that stays live. A block on the low-voltage LED line that drives the opto-triac would not meet this, because a shorted triac bypasses the line. The contact opens one pole, the live, upstream of the daisy-chain; the neutral side of each load keeps its switch and returns to `NEUTRAL`, so with the contact open **no load has a live feed, provided that `LINE1` is the one conductor through which every load's live lead is fed**. **That premise is not shown by the images and has not been measured.** It rests on the owner's visual trace of the unplugged board (2026-10-20), which `connector-pinouts.md` grades inspected and says the photographs do not independently show (§ The source of each live feed: the runs from the other six tabs were not followed through, and the per-terminal links are "not shown by the images"), and on the hardwired daisy-chain from `LINE1` to each load's fixed lead. The claim that the interlock cuts every load is therefore an inference from that trace, and **it is not proven until the bring-up continuity check** that `DEL-HW-BRING-UP.C4` now requires: with the relay open and the machine unplugged, by meter, from the supply live (`LINE`, the plug's L pin) to the live lead of each heater, each pump and each valve coil, there is no continuity (§ Reported for the board design tasks, item 32). The safety requirement that power to the heaters is available only while the controller is demonstrably running is met by this placement on that premise: the relay is in series with each heater's supply path, and the continuity check is what shows the premise on this machine.

**What the loads do with everything cut.** The constraints record gives every output one state to fail into: not heating, not pumping and not holding any output energised (`controller-board-design-constraints.md` § Output failure states, `DEF-SAFE-STATE`). With the live feed removed the two heaters are de-energised, which is the state each heater switch must fail into, and the interlock is what gives it where the switch alone cannot; both pumps stop, de-energised; both valve coils are de-energised, which is their required state. **Whether de-energised is also the two-way valve's open-to-drain, venting state is not established** (the constraints record states the same, and `reference-machine.md` § Protection holds a de-energised vent as a hypothesis), so this record states the required fail state and claims no venting state. The controller, the logic supply and the timing front end keep power through the taps upstream of the contact, so the controller stays up to see the cut.

### Copper that carries the heater current

The rule for the copper is 0.381 mm for each ampere of the highest continuous current at 1 oz (`docs/board-design-method.md` POWER-1): 1.83 mm for the coffee element's 4.80 A, 2.05 mm for the steam element's 5.38 A, 3.88 mm for both elements' 10.18 A, **4.18 mm for the 10.96 A of the whole supply** at the link, and **5.72 mm for the 15 A of the fuse's overload band**, which the heater branches' board copper is rated for (`controller-board-design-constraints.md` § Upstream protection and fault current). The regions on the wall board are 7.0 mm wide throughout, and so are the neutral pour and the shunt's lands on the main board, so each exceeds the 5.72 mm. The link's regions on the main board are 5.75 to 6.0 mm wide (the pours that hold the pads, the contact halves and the fuse's load-side clip, between the fixing distance and the 3.0 mm pair across the open contact), so the narrowest, `K_IL.a`, exceeds the 5.72 mm by 0.03 mm (the region from the entry fuse's load-side clip is 6.0 mm wide); the script tests every region at 15 A. At 1 oz the sheet resistance is 1.72 × 10⁻⁸ Ω·m / 35 µm = 0.491 mΩ for each square (computed; the resistivity is the published figure for annealed copper, not a datasheet's; A24). The regions are the rectangles of the data block, in the order of the chain; the script computes each region's squares, resistance and dissipation from them and takes the longest run from the same list.

**Temperature rise, an estimate.** The rule above states no temperature rise. By the IPC-2221 formula for an outer layer, I = 0.048 · ΔT^0.44 · A^0.725 (A in square mils, ΔT in kelvin), the narrowest link region, 5.75 mm of 1 oz copper (312 mil²), rises about 18 K at 10.96 A and about 36 K at 15 A, and the 7.0 mm regions about 13 K and 26 K, on outer copper with the planes pulled back 10.0 mm from every mains copper edge, so that no plane carries heat away. The constants are the standard's own and are not read from a sheet in this repository, so these figures are estimates, which the script computes from the constants in its data; the design task judges the rise against the board material's limit.

| Region (wall board frame) | Length (mm) | Width (mm) | Squares | Resistance (mΩ) |
|---|---|---|---|---|
| **S1**, `OUT_S` pad edge (u = 8.0) to the steam triac's near lead (u = 13.7); and its mirror for the coffee element, the coffee triac's near lead (u = 43.3) to the `OUT_C` pad edge (u = 49.0) | 5.7 | 7.0 | 0.81 | 0.40 |
| **S2**, the steam triac's far lead (u = 18.7) to the common-return pour (u = 25.0) | 6.3 | 7.0 | 0.90 | 0.44 |
| **S3**, the coffee triac's far lead (u = 38.3) to the pour's far edge (u = 32.0) | 6.3 | 7.0 | 0.90 | 0.44 |
| **RC**, the common-return pour, u 25.0 to 32.0, v 5.0 to 12.0, where the two element paths meet | 7.0 | 7.0 | 1.00 | 0.49 |
| **RET**, the return terminal's 7.0 mm pad, v 12.0 to 19.0, on the same copper | 7.0 | 7.0 | 1.00 | 0.49 |

| Path | Copper in it | Resistance (mΩ) | Current | Dissipation | At 15 A |
|---|---|---|---|---|---|
| Steam element | S1 + S2 | 0.40 + 0.44 = 0.84 | 5.38 A | **24 mW** | 189 mW |
| Coffee element | S1 + S3 | 0.40 + 0.44 = 0.84 | 4.80 A | **19 mW** | 189 mW |
| Both, in the common return | RC + RET | 0.49 + 0.49 = 0.98 | 10.18 A | **102 mW** | 221 mW |

The wall board has no sensor in the return now: the supply current is sensed on the main board, by the shunt in the neutral return, whose own loss is budgeted at 1.0 mΩ (A16): 0.12 W at the 11.01 A the neutral carries with every load on and 0.23 W at 15 A. The relay's contact is on the main board and adds nothing here. The longest run is RC, 7.0 mm, 12 % of the board's 57 mm width, and the copper from a blade terminal to the return pad is 26.0 mm in the steam path and in the coffee path. **No run crosses the board.** Dissipation in the copper is 145 mW with both elements on (102 mW in the common return, 24 and 19 mW in the two element paths) and 189 to 221 mW per path in the 15 A band, against the triacs' 4.25 and 4.84 W.

**Heavier copper against off-board wiring.** The division's costing asks for the weighing wherever 1 oz cannot carry a path, and no path needs it now: the return that was to cross the 5.0 mm channel from the heater terminals to tab 3 lands beside tab 3 in a pour 7.0 mm wide, and every copper region of both boards is wide enough for 15 A at 1 oz. What was weighed stays for the owner (an owner decision pending, § Owner decisions pending, D13): 2 oz copper halves the width needed, 2.86 mm at 15 A, at 36.40 USD more for two layers in the lowest band (40.40 USD against 4.00 USD, read) and an unmeasured price at four layers, while off-board wiring adds nothing to the board. This record takes 1 oz and no wiring on the board.

The faston tab, the joiner and the wall board's blade terminals are rated by their maker; no rating of theirs was found in a maker's document, so each rating is absent and the carried 15 A stands unmet by any source (§ The heater wall assembly, judged, *The element harness*).

### The interlock block, its size and its place

The block is the relay `K_IL`, drawn as a Hongfa HF115F-Q, one form A, with the 5 V coil, ordering code `HF115F-Q/005-1H` by P2's ordering table (coil voltage 005, contact arrangement 1H, vertical quick-connect terminals, AgNi contacts), placed **on the main board, in the link between tab 2 (`LINE`) and tab 1 (`LINE1`)**, so that it is in series with the live feed of every load. **Its size rests on the worst-case series contact rating for the current of every load behind it, and does not wait for the proof-of-life interval.**

**The part, its ordering code, and what the records do not hold.** P2's ordering table makes the coil voltage a code in the part number: `005` is the 5 V coil (62 Ω ±10 %, pick-up 3.5 V at most) and `012` the 12 V coil (360 Ω ±10 %, pick-up 8.4 V at most). Every coil figure of this record, the 62 Ω, the 0.4 W, the 89.6 mA on the 5 V rail and the `POL` drive from that rail, is for the 5 V code, `HF115F-Q/005-1H`, and a 12 V coil would not pick up from the 5 V rail (8.4 V against 5 V). The forms record's catalogue row for the family, C5318991, is `HF115F-Q/012-1H`, the **12 V** coil, so it is not the part this record draws. **The 5 V variant's catalogue number and price are not recorded: the design task must match a stocked part; the estimate uses the 12 V part's price** (3.2119 USD at one to nine, read in the forms record) and its Extended class, assumed to hold for the 5 V variant. The forms record names the HF115F-Q only for the valve switch and leaves the interlock's mechanism and parts to the design task (`DEL-HW-PARTITION-AND-FEASIBILITY.C5`; § What this record's words depart from in the forms record): **this record chooses the interlock's mechanism**: this relay as the series element, driven by the two-channel circuit of *The drive*, below. A series element of another kind that meets the same figures replaces the relay.

| Basis | Figure | Source |
|---|---|---|
| Ordering code | `HF115F-Q/005-1H`: coil code 005 (5 V), contact arrangement 1H (one form A), vertical quick-connect terminals (no terminal code 3), AgNi contacts (no code T). The forms record's catalogue row, C5318991, is `HF115F-Q/012-1H`, the 12 V coil; **the 5 V variant's catalogue number and price are not recorded** | P2 ordering information; `controller-board-function-forms.md` |
| Contact rating | 20 A at 250 VAC; UL 20 A at 277 VAC; 440 VAC and 300 VDC maximum switching voltage; 5 000 VA maximum switching power; 1 000 VAC between open contacts, which this record does not use | P2 |
| Loads behind the contact | Both elements 4.80 + 5.38 = **10.18 A** rms at 253 V; both pumps 0.46 + 0.19 = 0.65 A at their sizing values (their starting current is not recorded); both valve coils 0.129 A steady and 0.203 A at their inrush: **10.96 A steady and 11.03 A at the coils' inrush**; 15 A in the entry fuse's overload band | `controller-board-design-constraints.md` § Supply budget; § Upstream protection and fault current |
| Margin on current | 20 / 10.96 = **1.82**; 20 / 11.03 = 1.81; 20 / 15 = **1.33** | computed |
| Safety approval ratings (VDE), one form A, AgNi | 18 A at 250 VAC at 105 °C and 16 A at 250 VAC at 125 °C of ambient (12 A at 400 VAC at 105 °C); UL 20 A at 277 VAC. Margins on the 10.96 A the contact carries: 18 / 10.96 = **1.64** and 16 / 10.96 = **1.46**; on the 15 A of the overload band: 18 / 15 = 1.20 and 16 / 15 = **1.07** | P2; computed |
| Margin on voltage | 440 / 358 = **1.23** on the peak; 440 / 253 = 1.74 on the rms | computed |
| Margin on switching power | 5 000 / 2 773 = **1.80** (10.96 A at 253 V); 5 000 / 3 795 = 1.32 at 15 A | computed |
| Coil | 5 V, 62 Ω ±10 %: 80.6 mA and 400 mW at 62 Ω, 89.6 mA and 0.448 W at 55.8 Ω, the low end of the tolerance; pick-up 3.5 V at most, drop-out 0.5 V at least; ambient to 125 °C; temperature rise 55 K at the rated voltage, 137.5 K for each watt | P2; computed |
| Contact resistance | 100 mΩ at most, initial, at 1 A and 6 VDC: a qualification bound, not a figure at 10 A | P2 |
| Electrical endurance | 3 × 10⁴ operations at 20 A, 277 VAC, resistive load, room temperature, 1 s on and 9 s off; mechanical 1 × 10⁷. **The sheet gives no figure for an inductive load**, and the loads behind the contact include two pump motors and two valve coils | P2 |
| Contact heat | **Budgeted at 0.5 W at 10.18 A with the coil at its full drive** (4.8 mΩ, a drop of 49 mV; 0.58 W at 10.96 A and 1.1 W at 15 A), an assumption (A14). The unsourced worst case, the 100 mΩ bound taken at current, is 10.4 W at 10.18 A and 22.5 W at 15 A | A14; computed |
| Link copper | 4 regions from the entry fuse's load-side clip to the contact legs and back to the centre of tab 1, **4.30 squares = 2.11 mΩ**, the narrowest 5.75 mm; the fuse's own resistance and the inner-layer run before it are not in the figure (A32) | computed |
| Link loss | **0.22 W at 10.18 A**, **0.25 W at 10.96 A**, 0.48 W at 15 A, against the budget of 0.5 W (A20); the copper is under the budget at 15 A as well, without the fuse and the inner-layer run, which the figure leaves out | computed |
| Footprint and height | 29 × 12.7 mm body; 41 mm overall with the vertical terminal, 45 mm with the horizontal terminal; 15.7 mm high; PCB holes 2 of 1.3 mm (the coil, 7.56 mm apart across the body) and 4 of 1.5 mm (the contacts, two pairs 5 mm apart along the body, the pairs 7.56 mm apart across it), 37.5 mm from the coil holes to the second column of contact holes (A23) | P2 |

**Opening under load.** The contact opens on a fault or when the controller stops, with the heaters' resistive 10.18 A, which the sheet's endurance figure covers at 20 A, and with the pumps' and coils' small inductive currents, 0.65 A and 0.13 A, which the sheet does not rate. **The contact life under the inductive part is unsourced and is left to bring-up**: bring-up opens the relay with the pumps and the valves running and reads the closed-contact drop again afterwards. At the sheet's 3 × 10⁴ operations, ten operations a day would last 8.2 years (30 000 / 3 650, arithmetic); how many operations a day the mechanism makes is the design task's. The pumps' starting current is not recorded either, and is left to bring-up.

**The heat row.** The relay dissipates its coil, 0.4 W at 62 Ω (0.448 W at 55.8 Ω), and its contacts: 0.98 W in all, 0.58 W of it in the contacts at 10.96 A, and 1.03 W with the coil at the low end of its tolerance. The datasheet's own rise leaves no room: 55 K at 0.4 W is 137.5 K for each watt, so at the assumed 70 °C air the coil alone brings the body to 125 °C, the limit of the datasheet's ambient range, before any contact heat, and 0.98 W at the same 137.5 K for each watt would put the body at 70 + 135 = 205 °C, 80 K past the 125 °C limit. That arithmetic is a pessimistic bound, since the contact pins carry heat into wide copper rather than through the coil, and the datasheet gives no figure for it; but it is not a margin, and **the relay choice is not proven until the bring-up measurement.** The sheet's safety-approval (VDE) rating for this variant, one form A with AgNi contacts, is 18 A at 250 VAC at 105 °C and 16 A at 125 °C of ambient (P2), against the 10.96 A the contact carries and the 15 A of the overload band: 1.64 and 1.46 times the steady current, and 1.20 and 1.07 times the 15 A. The body stands at or above the 125 °C ambient limit at the assumed 70 °C air with the coil alone, so the 16 A figure is the one to lean on, and the sheet rates ambient and not body. **The device that carries the safety claim therefore has no sourced thermal margin at the coil drive it is held at** (the full 5 V, for as long as proof of life lasts). **Sourced:** the 20 A at 250 VAC rating, the 440 VAC and 300 VDC maximum, the 100 mΩ qualification bound at 1 A, the coil data, the 55 K coil rise, the VDE ratings above and the 125 °C ambient limit. **Estimated here, not sourced:** the 4.8 mΩ and the 0.5 W of contact heat (A14), the 0.98 W in all, and any body temperature. A reduced-hold coil drive was weighed and is dropped: it saved nothing by the estimate the record made of it (§ Options considered and dropped). Bring-up measures, with the contact closed at about 10 A, the drop across the contact with a meter and the body temperature: **over about 50 mV** (the 0.5 W of A14 over 10.18 A is 49 mV) means the relay is moved or changed. The 70 °C is the assumed air, which the owner thinks will not be real; it is kept so that this arithmetic stays cautious.

**The coil's feed**, a requirement on the main board's design task, in these words: *the coil is fed only through the proof-of-life path. No level, timer, charge store or latch keeps the coil above the relay's drop-out voltage for longer than the removal interval after proof of life stops. This holds whatever level the controller's output rests at: high, low or floating. Bring-up stops the controller in each rest state and records the coil voltage falling below 0.5 V within the interval.* That bring-up check is `DEL-HW-BRING-UP.C14`. The reason is that requirement's second sentence: what counts as demonstrating the controller is running must not be satisfiable by a controller that has stopped making progress, and a feed with storage of its own could outlast one.

**The logic supply keeps power when the contact opens.** The module's AC pins, the timing front end's input and the voltage measurement's input are fed from `LINE` and `NEUTRAL` **upstream of the contact**: from the entry fuse's load-side clip `F_IL.o` on the `LINE` side, and from the neutral pour `LK_N` above the shunt, not from the pad of tab 3, which is on the plug side of it. The data block names both taps; the script checks that each tapped block is on the net `LINE`, that nothing on the main board but the link's own copper, the pad of tab 1 and the pour that holds it, is on the `LINE1` net (the connector record's sentence that nothing else on the board connects to `LINE1` is what it is held to), and that the `LINE`-and-`NEUTRAL` pieces of the module's two pads, of the voltage measurement and of the timing strip each have a route for a trace from the first, the longest 54 mm, which keeps the signed 10.0 mm from the `LINE1` copper. **The route is shown for the two nets as one group, with no clearance kept between a `LINE` and a `NEUTRAL` trace**: it shows that a corridor for a trace exists, and the two traces side by side, 5.0 mm apart, are the design task's (§ Reported for the board design tasks, item 11). Where the tap meets the link is the design task's.

Drawn on the main board, the block is 41.0 × 14.525 mm (`K_IL`: its 41 mm length by 12.7 mm of body and up to 0.93 mm of contact copper beyond the body at each side), centred on the 3.0 mm gap between the two link pours, with its contact end's two halves, `K_IL.a` on `LINE` and `K_IL.b` on `LINE1`, 3.0 mm apart over the slot `SL_LINK` (A23); its coil end is the low-voltage pocket of the mains-side table, and the coil is driven by `POL` 12.5 mm from it. The coil is unenergised when the drive is lost or the controller's proof of life stops, so the contact is open in each; there is no cable between the drive and the coil to come loose. The circuit that decides when is *The drive*, below, to the removal interval of 100 ms, chosen, whose arithmetic is in `controller-board-design-constraints.md` § Interlock removal time and drive (`DEC-PROOF-OF-LIFE-INTERLOCK-IN-FIRST-HARDWARE`).

**The series element, judged.** The worst-case series current is every load behind the contact together: 10.96 A steady and 11.03 A at the coils' inrush at 253 V, and 15 A in the entry fuse's overload band (the table above). The rating is read from the maker's current document, Hongfa HF115F-Q 2024 Rev. 1.00 (re-read 2026-10-27; the printed revision is the one read on 2026-10-24): 20 A at 250 VAC, 440 VAC and 300 VDC maximum switching voltage, 5 000 VA maximum, and for the one form A AgNi contact the approval ratings 18 A at 250 VAC at 105 °C and 16 A at 250 VAC at 125 °C of ambient. Margins: 20 / 15 = **1.33** and 16 / 15 = **1.07** at the overload band, 20 / 10.96 = 1.82 and 16 / 10.96 = 1.46 steady, 440 / 358 = 1.23 on voltage, 5 000 / 3 795 = 1.32 on power at 15 A. **The relay is rated for the worst-case load currents**, and the judgement does not wait for the removal interval. The worst case rests on the 15 A band of the entry fuse, not on a measured load: the pumps' starting current is not recorded (item 10 of § Reported for the board design tasks), so a starting surge above the sizing currents is bounded only by the fuse's band, and the 1.33 margin is against 15 A. What is not sourced is stated above and is not part of the rating: the contact heat (A14), the inductive-load endurance, and the 5 V variant's catalogue number and price, for which an open search on 2026-10-27 found no entry (§ Reported for the board design tasks, item 7). The contact is operated on a trip and when the controller stops, not in normal running, so the 3 × 10⁴ operations of the sheet's endurance are spent only there.

**The drive.** The mechanism is a two-channel drive that needs a rising edge of the proof of life to hold either channel, and a single fault in it removes power or leaves a second channel to remove it, except three: the coil's low terminal shorted to ground and the buffer oscillating of itself hold the contact closed as a weld of the contact would, and a clamp zener shorted on a coil above 0.71 H removes later than the interval; all three are bounded in the same way, under `DEC-CHAIN-FAULT-BOUNDED-BY-INDEPENDENT-ELEMENT` (*Every single fault of the interlock*, below). The arithmetic is in `controller-board-design-constraints.md` § Interlock removal time and drive; the circuit is:

- **The signal.** The controller's proof-of-life output goes to one buffer `U_PL` on the 5 V rail, with its input held low by two 100 kΩ resistors in parallel. A level on the output, high, low or floating, is a level at the buffer's output.
- **Each channel** (`A` and `B`, identical and independent) has a coupling capacitor from the buffer to a node; a Schottky diode from that node to ground; a silicon diode from that node to the channel's gate node; a 4.7 nF reservoir and a 5.6 MΩ bleed from that gate node to ground; and an N-channel FET whose gate is that node. A level cannot cross the capacitor, so a channel is fed only by edges: each rising edge pumps charge into its reservoir, the bleed lets it go, and the gate stands above the FET's threshold for 15.3 ms at least after an edge and below it within 69.7 ms at most.
- **The two FETs are in series** below the coil, `Q_A` source to ground and `Q_B` source on the drain of `Q_A`, so the coil is fed only while both channels are held. The coil's other end is the 5 V rail.
- **The coil's clamp** is two branches in parallel across the coil, each a diode in series with a 12 V zener, so the coil's energy leaves through the zener quickly and a single open branch leaves the other.

**Parts and cost of the added channel.** One channel is six parts (coupling capacitor, two diodes, reservoir, bleed, FET). The drive is 19 parts: the buffer, two pull-downs, twelve in the two channels and four in the clamp. Counted as the buffer 1, the two pull-downs 2, each channel 6 and each clamp branch 2, a one-channel drive of the same circuit would be 11 parts (1 + 2 + 6 + 2), so the second channel and the doubled clamp add **8 parts**, none larger than a SOT-23 package or a 0603 passive. Their prices are not read: each is a part of a class the manufacturer's library lists, and its price and class (Basic, Preferred or Extended) are read where it is named by the schematic leaf. The bound that follows from the per-type fee this record already reads, 3.07 USD for each Extended type (§ What the owner fits by hand), is **at most six more Extended types** (buffer, FET, Schottky, silicon diode, zener, clamp diode), 18.42 USD at the worst and none if the parts are Basic. The 3.07 USD is the figure read; the six is a count of the drive's distinct part types.

**Options rejected, and why.**

| Option | Why not |
|---|---|
| One channel with paired coupling capacitors in series | A shorted coupling capacitor is covered, but a shorted FET, a bleed that opens (the gate then keeps its charge) and the reservoir's leakage each hold the coil, and no part remains to remove it |
| Two FETs in series fed from one charge pump and one reservoir | A single open bleed, or a shorted coupling capacitor with the buffer high, holds both FETs: the shared node is one part of a kind that fails closed |
| A retriggerable timer or watchdog integrated circuit in each channel | The fixed timeout need not match the chosen interval, and an integrated circuit's internal failures cannot be taken as open, short and stuck at the pins with a failure-mode table that no sheet read gives; two of them cost more than 19 passives and small parts |
| The pump driven from the controller's 3.3 V pin directly, without `U_PL` | The pump's output is then at most 3.135 − 0.35 − 0.75 = 2.04 V above the gate, against the FET's 1.8 V: the gate stays up for 23.6 ms × ln(2.04 / 1.8) = 2.9 ms, under the 10 ms control step, so the contact would drop out in normal running |
| A second series contact, or a contact monitor with a latch on `LINE1` | Both need a second relay place or a sense strip the sealed floorplan does not have, and the graph rules the floorplan stays one contact (`REQ-SAFETY-CHAIN-001.C8`: the hazard may be bounded by an independent element of the chain) |
| A reduced-hold coil drive | Dropped earlier for saving nothing (§ Options considered and dropped); the drive here holds the coil at its full voltage |

**Every single fault of the interlock.** Each part is failed open, short and stuck, and each outcome is one of: **removed** (heater power is removed), **bounded by a named independent element** (the hazard, a coil that stays energised after proof of life stops, is bounded by an element of the chain that does not depend on the drive), or **detected by the chain's own means** (the machine is held until a person attends). None is detected: nothing on the board senses the drive's channels or the contact. Where the remaining channel removes the power, the outcome is **removed by the remaining channel**, and the faulted channel is **latent and not detected**: the interlock is then one channel and a second fault in the other channel combines with it; the bring-up reading of each channel's gate level at its test point, with the output toggling and with it held, is what finds a fault visible at a gate, an open bleed or a shorted coupling capacitor (`DEL-HW-BRING-UP.C14`; the drawing carries a test point on each gate); a drain-to-source short of one channel's switch shows at no gate and stays undetected. Two faults are neither removed by the drive nor by a remaining channel: the coil's low terminal shorted to ground and the buffer oscillating of itself; a third, a shorted zener on a coil above 0.71 H, is removed later than the interval (*Clamp branch*, below). All three are **bounded by the series thermostats and the non-restoring device** exactly as the weld is (*The weld, bounded*), latent and not detected, under `DEC-CHAIN-FAULT-BOUNDED-BY-INDEPENDENT-ELEMENT`: a fault that leaves the contact held closed as a weld would, with the triacs still switching, needs a second fault to become a hazard, and the same independent elements bound it. This follows the same logic as the weld and is the same decision; a drive with one channel above the coil would remove the short and is recorded below as the option not taken.

| Part | Open | Short | Stuck |
|---|---|---|---|
| Controller's output (not a part of the interlock) | Floating: the pull-downs hold the buffer's input low: removed | To rail or ground: a level: removed | High or low: a level: removed (the firmware must not toggle it from a timer or interrupt, `DEL-HW-BRING-UP.C9`) |
| `U_PL` | Input open: the pull-downs hold it low: removed | Output to rail or ground, input to either: a level: removed | Output stuck high or low: a level: removed |
| Pull-down `R_pd1`, `R_pd2` | One open: the other holds the input: removal intact | Input held low: no edge: removed | — |
| Coupling capacitor `C_cx` | No edge reaches channel `x`: its gate decays: removed | The buffer's level reaches the node: with the output high the silicon diode charges the gate and channel `x` stays on: **removed by the remaining channel `y`, latent and not detected** (`Q_y` is independent of `x`'s parts and of the controller); with the output low: removal intact | — |
| Clamp diode `D_x1` | No restore: no net charge transfer: removed | Node held at ground: no pumping: removed | — |
| Pump diode `D_x2` | No charge path: removed | The node feeds the gate directly, still only from edges: a level decays: removed | — |
| Reservoir `C_rx` | Gate capacitance only: the gate falls in 5.656 MΩ × 0.3 nF = 1.7 ms, under the 12 ms refresh: removed | Gate held low: removed | — |
| Bleed `R_bx` | The gate keeps its charge: **removed by the remaining channel `y`, latent and not detected** | Gate held low: removed | — |
| FET `Q_x` | Drain-source open: removed | Drain-source short: channel `x` conducts always: **removed by the remaining channel `y` (`Q_y`), latent and not detected**; gate-source short: removed | Gate open or gate-drain short: the gate may hold: **removed by the remaining channel `y`, latent and not detected** |
| The midpoint of the FET stack | Open: removed | To ground bypasses `Q_A`, to the coil bypasses `Q_B`: **removed by the remaining channel, latent and not detected** | — |
| The coil's low terminal and `Q_B`'s drain node (the one node joining the coil to the FET stack) | Open: the coil is unpowered: removed | **Shorted to ground: bypasses both channels at once, the coil is held whatever the controller does: not removed, not detected: bounded by the series thermostats and the non-restoring device, as the weld is (below). Latent.** Shorted to the 5 V rail: no voltage across the coil: removed | — |
| The drive's own supply feed: the 5 V to `U_PL`'s supply pin and to the coil's high terminal, and any decoupling capacitor on the buffer (a part of the schematic leaf's, not counted in the 19) | A feed open: the buffer has no supply and no output swing beyond what its input protection passes, and only the controller's own edges reach it: removed; the coil's high terminal open: unpowered: removed. A decoupling capacitor open: removal intact | A feed or a capacitor shorted to ground: the rail or the buffer's supply is lost: no edge, or no coil voltage: removed | — |
| Clamp branch (diode `D_fbk`, zener `Z_fbk`) | A branch open: the other clamps: removal intact | Diode short: the zener conducts forward across the coil and the coil is starved: removed. **Zener short: the diode alone clamps at 0.7 V and the coil decays slower: removed only for a coil of at most 0.71 H, otherwise later than the interval and bounded:** 0.7 V clamp gives (L / 55.8) × ln((5.25 + 0.7) / (0.41 + 0.7)) = L × 30.1 ms per henry, so the removal time is 78.7 + 30.1 L ms, within 100 ms only for a coil of at most 0.71 H and 129 ms at 1.68 H; the coil's inductance is open, and the owner's LCR-meter measurement of the coil settles which: at 0.71 H or under the row is removed; above it the removal is later than the interval, latent and not detected, and bounded by the series thermostats and the owed non-restoring device like the weld (*The weld, bounded*, `DEC-CHAIN-FAULT-BOUNDED-BY-INDEPENDENT-ELEMENT`) | — |
| Relay coil | Open: removed | Turns shorted: more current, still released when the drive lets go: removed | — |
| **Relay contact** | Failed open: the heaters lose supply: removed | — | **Welded or the armature stuck: not removed by the drive: bounded, below** |
| Coil-to-contact insulation | — | Breakdown is a barrier fault, judged under *Barriers the signed basis does not list*, not a hold-on mode | — |
| The 5 V rail | Lost or low: the coil is unpowered: removed | Rail over its band: the channels' gates still decay without edges: removal intact | — |

A solder bridge between the two gate nodes leaves each bleed in parallel with the other: removed. A bridge from a gate node to the 5 V rail is the bleed-open row. The one element common to both channels is `U_PL`, and its failures at its pins are levels, removed; a buffer that oscillated of itself, with no input edge, would feed both channels and hold the contact closed, and is **not removed and not detected**: it needs a feedback path from output to input, a supply or layout fault and not a failure of a pin, which the Schmitt input's hysteresis and the 100 kΩ pull-downs make improbable and do not exclude. **Its outcome is bounded by the series thermostats and the non-restoring device, as the weld is, and it is latent**; it is the same state as the coil's low terminal shorted to ground, and the same residual as *What the circuit cannot tell*, below. Neither is worse than the weld: the contact is closed in each and the bound is the same; they differ only in that the hold ends when the 5 V rail is lost, which a weld does not.

**A cheaper removal of the coil's low-terminal short, recorded and not taken.** The short bypasses both channels because both FETs lie below the coil. A drive with one channel above the coil (a P-channel FET in the 5 V feed, its gate pumped below the rail by a mirrored pump) and one below would leave the coil's low terminal bypassing only the lower channel, and the coil's high terminal bypassing only the upper, so each short would be removed by the remaining channel. The cost: the part count stays 19, with one P-channel FET of a new type in place of one N-channel, a pump arithmetic that is not this one (the rail-referenced gate and the diodes' polarity reversed, so the timeout, removal time and refresh margin of C1 are all to be derived again), and the drive's area and cost not re-read. It needs no new contact and no re-floorplan, but its arithmetic is a new derivation and is not made here; the drive stays as drawn, and the schematic leaf may take it if the thermostats and the non-restoring device are judged an insufficient bound, which is the condition that would trigger taking it.

**The weld, bounded.** A weld of the contact, or a stuck armature, is not removed by the drive, because the floorplan keeps one contact in the feed (the other faults the drive does not remove, under *Every single fault of the interlock*, are bounded by the same elements). It leaves the heaters' supply closed but not energised: the triacs still switch, so the weld alone is harmless and **latent**; it matters when a second fault, a shorted triac or a hung controller with a gate held on, puts the machine on its protective devices. Two bound it:

| Element | What it bounds | State |
|---|---|---|
| The coffee block's series thermostat, 110 °C nominal (95 to 110 °C, ±3), wired in series with the element's lead at `COFHEATER`, and the steam chamber's, 200 °C ±5 (180 to 200 °C), at `STMHEATER` (`reference-machine.md` § Protection) | The temperature of its own block, whatever the weld, the triac and the controller do: each opens its element's circuit at its trip. It does not hold the element off after opening: whether each resets is not established (`reference-machine.md` § Protection, *Resettable vs one-shot*), so a resetting one cycles the element at its trip | Fitted on the machine as found |
| The non-restoring protective device that keeps power off once operated, which `DEL-BENCH-SAFETY-CHAIN-INSPECTION.C7` identifies from the machine's facts or supplies as a device in series with each heated load at its block | Holds each heated load off after it has operated until a person intervenes, which bounds a thermostat that cycles or fails | **Owed and not yet fitted.** No thermal fuse was seen along the loom or on the board and the owner found none (`reference-machine.md` § Protection, *Thermal fuse*). Until it is fitted the weld is bounded by the thermostats alone |

The contact makes and breaks with the triacs off, except on a trip: in normal running it carries current and is not switched, which lowers the likelihood of a weld. That is a likelihood and not part of the argument above.

**Every load's live lead.** The premise on the machine's retained wiring is that `LINE1` (tab 1) is daisy-chained by the retained wire to one side of every load, nothing else on the board connects to it, and each load's other lead lands on tabs 4 to 9 and returns through that load's switch to `NEUTRAL`. The design feeds tab 1 from the switched side of the contact (`K_IL.b`, the pour `LK_L1`), so the interlock cuts each load's live lead:

| Load | Tab of its other lead | Live lead the design feeds from the switched side | Switch on the other lead |
|---|---|---|---|
| Steam thermoblock element | 4, `STMHEATER` | The element's fixed lead, by the retained daisy-chain wire from tab 1 | `TRI_S` on the wall board |
| Coffee thermoblock element | 5, `COFHEATER` | The element's fixed lead, by the same wire | `TRI_C` on the wall board |
| Two-way coffee valve | 6, `COFVALVE` | The coil's fixed lead, by the same wire | `K_V1` |
| Coffee pump | 7, `COFFPUMP` | The pump's fixed lead, by the same wire; the pump thermostat is in series with the lead on tab 7 | `P_C` |
| Steam pump | 8, `STEAMPUMP` | The pump's fixed lead, by the same wire | `P_S` |
| Three-way valve | 9, `HOTVALVE` | The coil's fixed lead, by the same wire | `K_V2` |

**The premise is the owner's visual trace of the unplugged original board, 2026-10-20, graded inspected** (`connector-pinouts.md` § The source of each live feed): the photographs do not independently show the per-terminal links, the far ends of the pump and element leads were not recorded, and which blades of the three-way valve's coil carry the supply is not established. It is not measured. The continuity measurement of each load's live lead on the built board, with the relay open and the machine unplugged, is bring-up's (`DEL-HW-BRING-UP.C4`), named there and not done here.

**Barriers the signed basis does not list.** The basis names seven barriers; three that this record reports are none of them: the interlock's coil-to-contact barrier, the voltage measurement's isolating part, and the wall-to-mains-copper barrier (§ The heater wall board, *Mains copper and the metal wall*). **This record does not change the basis, and never relaxes a distance to fit a part.** The signed figures are 3.0 mm clearance and 10.0 mm creepage, mains to low voltage, reinforced, at pollution degree 3 and material group IIIb, with 4.0 kV the reinforced impulse (`hardware/sunbeam-em7000/separation-basis.yaml`). The two parts are judged against them:

| | Interlock relay, coil to contact | Voltage measurement's isolating part |
|---|---|---|
| Part | Hongfa HF115F-Q/005-1H, 2024 Rev. 1.00, read 2026-10-27 | Texas Instruments AMC131M02, SBASA56, September 2023 (the Internet Archive's copy of the maker's sheet), read 2026-10-27; LCSC C31423783 |
| Creepage against 10.0 mm | "Over 8 mm", no figure stated above 8: the lower bound is 2.0 mm, 20 %, under; the actual is not stated, so **not shown** | 8.0 mm at least: the lower bound is 2.0 mm, 20 %, under; the actual is not stated, so **not shown** |
| Clearance against 3.0 mm | Not stated: **open** | 8.0 mm at least: 2.7 times, **met** |
| Impulse against 4.0 kV | Surge between coil and contacts 10 kV (1.2/50 µs): 2.5 times; 5 000 VAC for one minute is 7.07 kV peak, 1.77 times (test voltages, not a working isolation voltage) | Maximum impulse 7 700 V peak in air: 1.93 times; maximum surge 10 000 V peak in oil: 2.5 times |
| Working voltage against 358 V peak | No working isolation voltage is stated: **open** | Maximum working isolation voltage 1 700 V peak: 4.7 times |
| Material and pollution | Not stated | Comparative tracking index at least 600 V, material group I; the sheet's pollution degree is 2 |
| Rated ambient | To 125 °C | −40 to 125 °C |
| Verdict | **Not shown to meet the basis**: creepage is not shown to reach the signed figure from the part's own lower bound; clearance and working voltage are open | **Not shown to meet the basis on creepage**; every other figure met |

*The isolating part also carries the shunt.* The AMC131M02 is two simultaneous-sampling ΔΣ ADCs with differential inputs, referenced to one high-side ground, in a 20-pin wide-body SOIC, with an integrated isolated supply from a single 3.3 V or 5 V rail; its inputs, per the sheet's § 6.3 recommended operating range (SBASA56), run from the high-side ground less 1.3 V to plus 2.7 V at gain 1, 2 or 4 and from less 1.3 V to plus 0.9 V at gain 8 to 128 (the less 1.6 V to plus 2.7 V of § 6.1 is the absolute maximum, not the operating range), its differential input is ±1.2 V divided by the gain, and its gain runs from 1 to 128. The 21.2 mV shunt channel below needs a gain of up to 32 to stay inside the ±37.5 mV that gain gives, and any gain of 8 or more puts its inputs in the +0.9 V row, so the shunt's neutral side is held at the high-side ground (the shunt is in the neutral return) and stays well under it; One channel reads the voltage divider off `LINE` against `NEUTRAL` and the other the shunt in the neutral return, 15 mV rms at 15 A across 1 mΩ (21.2 mV peak), which is the shunt as the second current channel: no second barrier part is needed, and the drawn placement of D3 stands. The divider's ratio and the gain are the schematic leaf's. **What it changes in the floorplan: the part's output is digital** (a serial interface to the controller), not the isolated analogue signal that the conditioning blocks `VM_C` and `I_C` assume. The two blocks become the serial link and a decoupling, which should free area; the floorplan's rows and the pocket of `VMEAS`, which holds the 20-pin package, are the schematic leaf's to redraw, and the unlisted barrier is carried to it with the creepage not shown above (§ Reported for the board design tasks, item 2).

**The owner's acts before either part is ordered.** The owner re-declares the basis, adding the interlock relay's coil-to-contact barrier and the voltage measurement's isolating part as barriers of their own with the creepage, clearance and working voltage each part's maker gives; or chooses parts that meet the signed 10.0 mm and 3.0 mm. Signing is the owner's and is not done here. The maker's clearance and working isolation voltage for the HF115F-Q are asked of the maker; the AMC131M02's 8.0 mm creepage is the package's own, and a wide-body package of the same family with a larger creepage is the other route.

### The valve relays

The valve relays `K_V1` and `K_V2` switch the two valve coils, which draw 0.129 A rms steady and 0.203 A rms at inrush together (`controller-board-design-constraints.md` § Supply budget), against the 10.96 A that `K_IL` carries. A 20 A relay is oversize for them, and this record replaces the forms record's HF115F-Q for them by the **Hongfa HF32FA-G/005-HSL1**, the 5 V sensitive-coil part of the OEM's own family that the constraints record already priced (C91370, Extended, 3 671 in stock and 1.6115 USD at one to nine on 2026-10-13). The interlock relay stays the HF115F-Q. Every figure of the table is from P6 (2026 Rev. 1.00, read 2026-10-24) unless it names another source.

| Basis | Figure | Source |
|---|---|---|
| Contact rating | 10 A at 250 VAC resistive; maximum switching current 10 A; maximum switching power 2 500 VA; AgSnO2 contacts; contact resistance 70 mΩ at most, initial, at 1 A and 6 VDC | P6 |
| Maximum switching voltage | **250 VAC**, so the 253 V top of the span is 1.2 % over it: **accepted by the owner for relay contacts on 2026-10-24**, on the ground that the supply voltage is measured and the control refuses to run well above the span; the constraints record carries the acceptance in *Rated for the supply* and the script reads it there. Blocking the 358 V peak while off and the reinforced coil-to-contact isolation still apply, and a semiconductor switch is not covered | P6; `controller-board-design-constraints.md` |
| Margin on current | 10 / 0.129 = **78** steady and 10 / 0.203 = 49 at inrush; the sheet's endurance is 1.5 × 10⁴ operations at 10 A and 250 VAC resistive at 85 °C, 1 s on and 9 s off, and 1 × 10⁶ mechanical, with **no figure for an inductive load**, which a valve coil is (unsourced, left to bring-up) | P6; computed |
| Margin on voltage | Open contacts 1 000 VAC for one minute = 1 414 V peak against the 358 V that must be blocked while off: **3.95** | P6; computed |
| Isolation | Coil to contacts 5 000 VAC for one minute = **7.07 kV** peak against the 4.0 kV reinforced target (the forms record's comparison, which judges test voltage only and never calls a part adequate); creepage and clearance "over 8 mm" and "meets VDE 0700, 0631 reinforce insulation", which is under the signed 10.0 mm creepage as the interlock relay's "over 8 mm" is (§ Reported for the board design tasks, item 2) | P6 |
| Coil | 5 V sensitive coil, 108 Ω ±10 %, **46.3 mA** and **231 mW** at 5 V (51.4 mA at 97.2 Ω, the low end of the tolerance, which the 5 V rail's budget uses); pick-up 3.75 V at most, drop-out 0.25 V at least, 8.5 V at most; operate 8 ms and release 4 ms at most | P6; computed |
| Outline | 17.6 × 10.1 mm, 12.7 mm high, pins 3.6 mm below the board, the two columns of holes 15.24 mm apart; ambient −40 to **85 °C** | P6 |
| Self-heating | The sheet's temperature-rise line reads about 61 K at the rated coil voltage (47 K at 80 %), read off the plot; the sheet does not say for which coil it is drawn. At the 85 °C ambient limit that is 146 °C against 155 °C for insulation class F (P6 lists the class); the coil is energised only while its valve is open | P6; read off the plot |
| Price | 1.6115 USD against 3.2119 USD, the forms record's price for the HF115F-Q/012-1H (C5318991), the only variant of that family priced in the records: **3.20** USD less for the two, in the same Extended class and at the same fee | `controller-board-design-constraints.md`, `controller-board-function-forms.md` (read 2026-10-13) |

**What changes in the floorplan.** The relay is 17.6 mm long where the HF115F-Q was 41 mm, so it no longer spans from the tab pad to the zone boundary: it stands at the boundary and its mains lead crosses the stack (§ The mains-side blocks). Its coil takes 46 mA each, 92.6 mA for both, against 161 mA for two HF115F-Q coils; the shared fuse `VFUSE` is unchanged, and the coil drive is a low-side transistor and a flyback diode as the forms record has it (`DRV_K1`, `DRV_K2`). **What it costs in heat.** The sheet's ambient limit is 85 °C against the HF115F-Q's 125 °C, so a valve relay is a part that derates, and the stack puts `K_V1` on the module's body (§ Heat, which shows why not every 85 °C part can hold 15 mm): not held, with the bring-up measurement as the claim and the HF115F-Q as the fallback. **The extended-part count** rises by one type, 3.07 USD, which the two relays' saving of 3.20 USD at the unit price roughly pays (§ What the owner fits by hand).

### The pump drives

**The two pump drives, `P_C` and `P_S`, carry no snubber and no varistor, and this record says so plainly.** Each is a random-phase opto-triac (onsemi MOC3052M, P14) driving a snubberless triac (WeEn BTA204S-600B, P13) in series with the pump and its branch fuse, and nothing lies across the triac or across the pump's line.

**Why none.** The forms record chose a snubberless triac so that an inductive pump's turn-off needs no snubber, which would be a path around the off triac. P13 rates the BTA204S-600B at a commutating current rate of at least 6 A/ms at 125 °C, 400 V and 4 A rms, with a commutating voltage rate of 20 V/µs and no snubber (its "snubberless condition"), and calls it a "series B" triac that commutates the full rated current at the maximum junction temperature without the aid of one. The pump's own rate of change of current at its current zero, **for a full sine**, is 2π × 50 Hz × (0.46 A × √2) = 204 A/s = 0.20 A/ms for the coffee pump and 0.08 A/ms for the steam pump (0.19 A), 29 and 71 times under the rating. **But each pump has a series diode (the owner's statement; inferred from meter behaviour), so its current is a half wave**, whose peak is twice its rms and not √2 times it: 2π × 50 Hz × (2 × 0.46 A) = 289 A/s, so the rates are 0.29 A/ms and 0.12 A/ms, 21 and 50 times under the rating, and the margin on the commutating rate is **21 times at the least, not 29**. P14 says a random-phase driver "can allow snubberless operation" where the load is resistive and the noise on the line is under its guaranteed dv/dt, 1 000 V/µs at least, and asks that the static dv/dt and the commutating dv/dt be considered for an inductive load.

**The check against the EMC and surge criteria and the turn-off voltage, as far as the sheets close it.** (1) *Blocking:* the triac and the opto-triac both block 600 V (P13, P14) against 358 V peak, a margin of 1.68, 242 V above the peak. (2) *Turn-off:* a triac turns off at its current zero, so what is left in the pump's inductance then is the energy at the holding current, ½ L I_H² with I_H at most 30 mA (P13), and the voltage across the triac after turn-off follows the source, 358 V at the most; the series diode in each pump (the owner's statement; inferred from meter behaviour) blocks the other half-cycle. (3) *Surge:* a surge reaching `LINE1` is the one the basis assigns (2.5 kV basic, 4.0 kV reinforced; `REQ-ELECTRICAL-INSTALL-001.C10`, judged from makers' ratings), through the branch fuse and the pump's coil; the opto-triac's 1 A is a single-cycle rating and the triac's 25 A (P13) a 20 ms one, and no sheet read gives either a rating for a 1.2/50 µs pulse. **What does not close, and is an open item for the design task:** that each pump has a series diode at all, which the half-wave margin above assumes (the owner's statement, inferred from meter behaviour and not measured; with no diode the full-sine margins of 29 and 71 times apply); the pump coil's inductance, and the series diode's voltage rating, which together set the voltage the triac sees as the diode blocks and the current falls to zero; the commutating dV/dt of the real circuit (the sheet's 20 V/µs is a test condition, not this circuit's); the conducted emission of a random-phase edge at an arbitrary phase against the limits that govern household appliances, which this record does not quote because the standard is declared for the jurisdiction and no figure is taken from memory (`OBL-ELECTROMAGNETIC-COMPATIBILITY-001`); and the surge withstand of the drive and of the diode judged from the makers' ratings. The obligation states its limits as met by design and by analysis, because the builder has no instrument that measures emissions, so the design task closes these by analysis and says what it could not. **The margins are judged in `controller-board-design-constraints.md` § Pump drives: surge and emission margins**, which marks each figure read or open, with the owner's act that settles it: the pump coils' inductance and the series diodes' rating, measured with an LCR meter and read from the diode, are the open ones, and an assumed figure counts as open.

### The fuses

Each pump branch has its own fuse holder and the two valve branches share one, as `DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE` arranges: the decision reasons that the two pumps serve different water paths, so that a fault in one should not stop the other, and that both valves serve one, so that one fuse is enough. The floorplan draws that arrangement: `P_C`, `P_S` and `VFUSE`, three holders of 24 × 9 mm = 216 mm² each (A6).

**Owner decision pending (§ Owner decisions pending, D5): one shared fuse for both pumps, or for the pumps and the valves.** The proposal replaces the three holders by one, and is not drawn. The figures are the script's:

| Item | Figure |
|---|---|
| Load behind a shared fuse | 0.46 + 0.19 + 0.129 = **0.779** A steady and 0.46 + 0.19 + 0.203 = **0.853** A with the coils' inrush at 253 V, under the 1 A that the proposal allows (the pumps at their sizing currents; their start surge is not recorded) |
| Space saved | Two holders of 24 × 9 mm = **432** mm², which the pump strips would give back; the record does not spend it, and both strips keep their size until the owner decides |
| What it still protects | The pump flex, which was found with no fuse along the loom at the board end: one fuse in front of both branches opens on a fault in either, so it protects each pump's flex as a branch fuse of its own would, at the rating of the pair |
| What it gives up | A fault in one branch drops both pumps and the valves, where the decision keeps the pumps apart so that a fault in one does not stop the other; the heaters are on the entry fuse and are unaffected; and the fuse rating, sized for the pair's start surge and the coils' inrush together, is higher than either pump's own, so a fault in the smaller pump's branch is cleared at a higher current |

**A smaller approved holder or fuse.** The decision names subminiature slow-blow fuses; the board's holder is the 5 × 20 mm one of the forms record's proving candidate (C3131, listed 250 V and 6.3 A). The constraints record assumes a prospective fault current of 6 kA and requires every fuse and breaker in the chain to break at least that. **None of the options this script holds does.** Sourced: a 5.2 × 20 mm ceramic time-lag, 0.5 to 12 A, **1 500 A** at 250 V AC (P8); a 5 × 20 mm glass time-lag, **35 A** or ten times its rating at 250 V AC (P9); and the same maker's 6.3 × 32 mm ceramic, 10 000 A at 125 V AC but 200 to 1 500 A at 250 V AC by rating (P8's family). A retailer's listing gives a subminiature radial time-lag (Schurter MXT 250) at 100 A; that figure was not read at the maker's sheet. The shortfall is the same for the entry fuse, which the chain also asks 6 kA of; it is the project assumption's to replace. None of them makes the holder smaller: a 5.2 × 20 mm cartridge is no shorter than a 5 × 20 mm one. The script fails if a sourced option reaches the 6 kA, so this statement is corrected on the day one is found. The SETfuse SCT520 time-lag sheet (document version V1.0, 2024-2026, from the LCSC part page of C22447834), read on 2026-10-28 and not one of the script's sources, prints 10 kA at 250 VAC under UL for its 10 A rating, which would cover the 6 kA, and 2 kA under CQC and TUV, 3.0 times short; the SCF520 fast-acting sheet prints 1 500 A at 300 VAC under UL and 5 kA at 250 VAC and 3 kA at 300 VAC under CQC and TUV. Which approval body's figure governs is open, with the acts that settle it, in `controller-board-design-constraints.md` § Mains entry: fuse, surge clamp and suppression judged, *Breaking capacity against the project's fault-level assumption*.

**The mains entry: the retained lead, and the fuse and varistor at tabs 2 and 3 (decided by the owner).** The machine keeps its existing fixed mains lead; no appliance inlet and no [earlier design: bought inlet filter] are fitted. The 10 A slow-blow fuse and a varistor are carried on the main board where the lead's conductors land, at tabs 2 and 3, the varistor hard against the fuse and downstream of it, as the original board carried its own protection at its entry. `DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE` records the arrangement. Upstream of the fuse the lead is protected only by the building's circuit breaker, declared as up to 20 A; the fuse protects everything downstream, the trunk and both heaters included. Four things stay stated here:

- **The 10 A holder.** The board's 5 × 20 mm holder is listed 250 V and 6.3 A, so the entry fuse needs a 10 A holder; the pump and valve holders above are not one. The clip priced for it is rated up to 10 A by its sheet, under the 15 A overload band, and the fuse priced is fast-acting: both are judged in `controller-board-design-constraints.md` § Mains entry: fuse, surge clamp and suppression judged.
- **The 6 kA shortfall.** The fuse is as short of the 6 kA the constraints record assumes as the options above on the lower approval-body figure: the plain SCT520 10 A is 2 kA against 6 000 A on the CQC and TUV figure, 3.0 times short, and 10 kA on the UL figure, which would cover it, and the fast-acting SCF520 10 A priced is 5 kA on CQC and TUV, 1.2 times short; which figure governs is open, and the project assumption is the one to replace, by the owner's reading of the breaking capacity marked on the circuit breaker or an installer's prospective fault current, and the constraints record says what each figure settles.
- **The varistor.** The original board's varistor is `RV1`, marked `VDR-14N471K` (14 mm, 470 V), across the live and neutral at its mains entry with the X2 capacitor `C1` (`reference-machine.md`, from the circuit diagram); the owner checks that disc on the original board before the part is chosen.
- **Emission suppression.** The [earlier design: bought inlet filter]'s suppression is lost with it. Whether the entry needs an X2 capacitor or a common-mode choke in its place is decided by the main board's design against the emission criteria (`OBL-ELECTROMAGNETIC-COMPATIBILITY-001`), and if it is needed it goes on the main board. **The decision is made** in `controller-board-design-constraints.md` § Mains entry: fuse, surge clamp and suppression judged: an X2 capacitor of 0.1 µF across line and neutral and no choke; where it stands and its discharge are left to the main board design.

**Where the entry parts stand.** The entry fuse holder `F_IL` stands at X 17.0 to 41.0 and Y 34.3 to 43.3, along X on the upper edge of `K_IL`'s block, 24 × 9 mm (A6). It is in series between the pad of tab 2 and everything else the lead's line feeds: its line-side clip `F_IL.i` (X 35.0 to 40.0) is on the new net `LINE_IN`, the lead's line conductor before the fuse, and its load-side clip `F_IL.o` (X 17.0 to 23.0) is on `LINE`, meeting `K_IL.a` along Y = 34.3, so the link, the taps to the module, the timing front end and the voltage measurement, and the varistor are all downstream of it. `LINE_IN` holds only the pad of tab 2 in the pour `LK_L` (X 5.0 to 12.0) and the line-side clip; it is held to the basic 3.0 mm and 5.0 mm from every other net and to the signed 3.0 mm and 10.0 mm from the `LINE1` copper, as `LINE` is. The varistor `RV_IL` stands against the fuse holder's upper edge (X 17.25 to 31.25, Y 43.3 to 48.3, the disc drawn 14.0 × 5.0 mm, A33): its line pad `RV_IL.l` is on the piece of copper that holds the fuse's load-side clip, 0.0 mm from the clip, and its neutral pad `RV_IL.n` is on `NEUTRAL`; the script holds the line pad to that piece and to within 5.0 mm of the clip, so a varistor on the line side of the fuse, or away from it, fails. The tabs do not move, and tabs 1 to 3 keep the slack of § The fixing rule and the tabs that move. To make room, the shared valve fuse holder `VFUSE` stands 5.0 mm higher in its column and the slot `SL_LN` ends at X = 16.5, short of the fuse's load-side clip; the outline is unchanged. **The line side is joined to the pad of tab 2 on an inner layer** (A32): the pad is shut in on the surface by the pad of tab 3 above it, the `LINE1` pour below it and the relay's contact half beside it, and the script finds no surface route to the fuse and shows an inner-layer route of 23 mm clear of every hole, slot and low-voltage block. That run carries the whole supply up to the fuse's rating, so its width (the link's, 5.72 mm for 15 A) and its signed distances on its own layer are the main board design task's to show, as are the fuse's own resistance and heat (§ Reported for the board design tasks, item 5). The cost record prices the parts (§ Mains entry), and the division's counted joints and part types do not include them. No suppression part is drawn: the entry needs one, an X2 capacitor and no choke, as decided above, and its place is the main board design's. The decision on the wall-board varistors (D7) depends on the board-entry varistor.

### The heater wall board

**Form: its own board.** The comparison, at the maker's charges read on 2026-10-13:

| | Its own board | A section that breaks off the main board |
|---|---|---|
| Fabrication | Inside the lowest band: a body of 57.0 × 42.5 mm and two mounting ears along its wall edge, 89.0 mm over all, 2 layers, five boards, **4.00 USD**; through the maker's own application, read at 2 layers in the band, 2.00 USD | The main board is outside the band already, so the section adds only its area to the panel's board fee, at the panel's four layers: 6.60 × 2 662.5 / 10 609 = **1.66** USD (inferred): saves 2.34 USD, or costs 0.34 USD less than the application's price |
| What a respin costs | The wall board's own order, 4.00 USD | The four-layer main board's order with it, at block level about 48 USD with its assembly (§ Candidate divisions) |
| Where the section joins | | Along the main board's left edge, outside the cavity; the break line carries no copper; the section's low-voltage header lies 10.0 mm or more from its own mains copper as it does as a board, and the only copper near the join is the main board's tab strip, which is mains copper, 4.0 mm in from the left edge at X = 1.0. Copper keeps 0.2 mm from a routed break line (`docs/board-manufacturer-jlcpcb.md` § Hole-to-hole and clearances to holes and edges); nothing is energised while the two are joined |
| Assembly | Hand-fitted by the owner, or one order of its own | Shares the main board's assembly order; hand-fitting is not forced |
| Respin likelihood | High: the bracket as the heat spreader, the interface between tab and bracket and between bracket and wall and the bracket's own drawing are judged on paper only, and the faston rating is absent, the wall, the cavity and the leads' reach being unmeasured | The wall board's changes are coupled to a board that has no reason to change |

The decision, subject to owner decision D9: **its own board**, 2.34 USD dearer at best and decoupled from the main board's order; the owner's starting point was a section "to cut fabrication cost", and the saving is that 2.34 USD (it was 1.16 USD before the board shrank). The section stays open as the owner's choice (an owner decision pending, § Owner decisions pending, D9). **The wall board no longer carries the interlock relay**: it carries only the two triacs with their opto-triacs and gate networks, two varistors, three blade terminals and a three-way header.

**Outline and blocks.** The wall board's body is **57.0 × 42.5 mm**, 2 422.5 mm², with two mounting ears along its wall edge (§ *The bracket*) that make it 89.0 mm over all and 2 662.5 mm², two layers, 1 oz, inside the 102 × 102 mm band. Its frame: **u** runs along the edge that lies nearest the machine's metal wall and **v** away from it, from the corner at the left of the steam side. It is all through-hole, since the current sensor that was its one surface-mount part is gone. **The triacs stand 14.2 mm apart** (their tab faces 24.6 mm apart) and the opto-triacs stand 20.0 mm from the triac bodies, the closest A8 allows. **Why this size:** the two rows set the width alike, 55.0 mm each from the first part to the last: the triac row from the steam blade terminal to the coffee one, and the opto-triac row, where each opto-triac is 10.0 mm wide and stands 10.0 mm clear of the header (a low-voltage part, which must stand 10.0 mm from every mains rectangle) that sits between them; the depth is the 20.0 mm from the triac bodies (v 10.5) to the opto-triacs, their 11.0 mm and 1.0 mm to the edge. The board was shaped by the sensor, the confirms, the snubbers and a common-return pour that ran up its middle to the sensor; with them gone it is the board the other rules set.

| Block | Function | u (mm) | v (mm) | Size (mm) | Area (mm²) | Basis |
|---|---|---|---|---|---|---|
| `OUT_S` | Steam element out: 6.3 mm blade terminal, wire from the steam lead's joiner | 1.0 to 8.0 | 5.0 to 12.0 | 7.0 × 7.0 | 49 | 7.0 × 7.0 pad, 5.0 mm in from the wall edge |
| `TRI_S` | Steam triac BTA16-600BRG, insulated TO-220AB, tab bolted to the bracket's leg, leads straight to the pads | 11.0 to 21.4 | 5.0 to 10.5 | 10.4 × 5.5 | 57 | B 10.4 × C 4.6 mm body (P3); the body is bolted to the bracket's leg and its leads go straight down to the pads, whose land is 5.5 mm deep; near lead at u = 13.7 on `S1`, far lead at u = 18.7 on `S2` |
| `MOV_S` | Steam varistor across the triac | 1.0 to 11.0 | 17.0 to 23.0 | 10.0 × 6.0 | 60 | 10 × 6 mm (A7), its ends 2.5 mm wide on the element side (u 1.0 to 3.5) and the return side (u 8.5 to 11.0), 5.0 mm apart, and 5.0 mm from the copper of the triac row; it stands clear of the driver's way to the tab screw at u = 16.2, which is u 13.2 to 19.2 |
| `OPTO_S` | Steam zero-cross opto-triac MOC3083, DIP-6, rows along u, with the two resistors of its gate network | 1.0 to 11.0 | 30.5 to 41.5 | 10.0 × 11.0 | 110 | 10 × 11 mm, rows along u 7.62 mm apart (body 8.51 × 6.35 mm, P4); 20.0 mm from the triac body, A8; mains end v 30.5 to 34.0, low-voltage end v 38.0 to 41.5; it straddles the slot `WS_STEAM` |
| `TRI_C` | Coffee triac | 35.6 to 46.0 | 5.0 to 10.5 | 10.4 × 5.5 | 57 | As `TRI_S`; near lead at u = 43.3 on `S1`, far lead at u = 38.3 on `S3` |
| `MOV_C` | Coffee varistor across the triac | 46.0 to 56.0 | 17.0 to 23.0 | 10.0 × 6.0 | 60 | 10 × 6 mm, its return end u 46.0 to 48.5 and its element end u 53.5 to 56.0 |
| `OUT_C` | Coffee element out: blade terminal, wire from the coffee lead's joiner | 49.0 to 56.0 | 5.0 to 12.0 | 7.0 × 7.0 | 49 | 7.0 × 7.0 pad |
| `OPTO_C` | Coffee zero-cross opto-triac | 46.0 to 56.0 | 30.5 to 41.5 | 10.0 × 11.0 | 110 | As `OPTO_S`; it straddles `WS_COFFEE` |
| `WB3` | Low-voltage cable header, 3 ways, 2.54 mm | 21.0 to 35.6 | 32.0 to 39.5 | 14.6 × 7.5 | 110 | Footprint (A5); 10.0 mm from every mains rectangle, between the two opto-triacs (10.0 mm from each mains end) |

The mains copper of each block is the rectangle of its row, or, where a part has two ends on different nets, the two end rectangles (the varistors across the triacs: `.a` on the element's side, `.b` on the return); its low-voltage pocket is the far end of the rectangle, and the copper regions S1 to S3, RC and `RET` are further mains rectangles of the data block. Each opto-triac's mains end is its rectangle's near 3.5 mm (v 30.5 to 34.0) and its pocket the far 3.5 mm (v 38.0 to 41.5). The script of § Appendix checks that every block lies inside the outline, that none overlaps another, that every mains rectangle lies at least the basic creepage, 4.1 mm, from the wall edge, that mains copper of different nets from different parts lies 1.5 mm or more apart and 4.1 mm or more by surface path round the slots (the triac's two leads and the two ends of each varistor are the parts' own spacing, the basis's accepted exceptions; the least between different parts is 5.0 mm), that every pocket lies 3.0 mm or more from mains copper and by surface path round the slots 10.0 mm or more, that the low-voltage header lies 10.0 mm or more from every mains rectangle, that the opto-triacs keep their 20 mm from the triacs, and that the largest dimension, 57 mm, is inside the lowest band's 102 mm. It runs the same checks on the second layout, with the places of the confirms (below).

**The slots.** Two slots, each 1.0 mm wide and none within 0.2 mm of copper or a pocket, serve the same rule as on the main board; the part over a slot bridges it, and each slot is open at a board edge, where a path cannot turn round its end:

| Slot | u (mm) | v (mm) | Length (mm) | What it separates |
|---|---|---|---|---|
| `WS_STEAM` | 0.0 to 13.0 | 35.5 to 36.5 | 13.0 | The steam opto-triac's mains pins from its low-voltage pins; open at the left edge |
| `WS_COFFEE` | 44.0 to 57.0 | 35.5 to 36.5 | 13.0 | The same for the coffee side; open at the right edge |

Counted from the data, that is 26 mm of slot path, 9.8 m of slot path per m² of board against the maker's 80 m per m². No pocket stands under 10.0 mm from mains copper in a straight line (the nearest is 15.0 mm), so the slots hold only the opto-triacs' own pins, 12.1 mm apart round the slot. A tap from `RET` to a confirm place, if the places are ever fitted, is routed above the slot's ends (the design task's).

**The bracket.** The owner's intent (2026-10-26) is that the triac leads are not bent or folded: both triacs stand on a right-angle heat-spreader bracket whose one leg is fixed to the board by two mounts and whose other leg bolts to the metal wall, so that the board and the triacs are fitted to the machine and removed from it as one unit, with each fixing screw reached by a driver, without desoldering any joint and without bending or re-bending a lead. The bracket is cut and machined by the owner or sourced by the owner; it is not in the catalogue and is not priced here (a few dollars at most, an estimate whose basis is the owner's own fabrication), and its figures are A22's. **The board stands edge-on to the wall, its wall edge flush with the outer face of the bracket's leg.** In the board's frame (u along the wall edge, v away from it) the two legs lie in one strip, v 0.0 to 5.0 and 5.0 mm thick: the **board leg** lies along u −15.0 to 72.0 (87.0 mm) `lift=5.0` mm clear of the component face, on plastic spacers at the two mounts; the **standing leg** rises from it to 35.0 mm above the component face and is the heat spreader (owner statement, 2026-10-28), with its outer face (v = 0) on the metal wall, 30.0 mm tall (from the lift of 5.0 mm to 35.0 mm: the low end of the owner's estimated 30 to 35 mm, the 35 mm height being the other choice) and **80.0 mm long** (u −11.5 to 68.5, centred on the board's 57.0 mm width), and its inner face (v = 5.0) carrying the two tab faces, which stand there 24.6 mm apart centre to centre (u = 16.2 and 40.8). **The 80.0 × 30.0 mm is a provisional drawn default**, the owner's estimated maximum ("I could probably mount an 80 x 30-35 mm spreader", 2026-10-28, estimated from drawings of what the owner thinks is behind the wall and unmeasured), held as data values (`window_l` and `top_z`) to be replaced by the owner's measured maximum spreader, which the owner accepted as preliminary (D11; § *The wall cut, and the owner's acceptance*). Each triac stands upright with its tab face on the standing leg and its three leads straight down into the pads; an M3 screw through each tab's hole holds the face on the leg. No lead is bent, folded or re-bent, in fitting or in removal: the tab hole sits 17.25 mm above the component face on the leg, from the package drawing and the board's fixing (§ *The heater wall assembly, judged*, *The bracket*).

**The two mounts are mounting holes, as every other hole is.** The wall edge carries two ears, each 16.0 mm wide and 7.5 mm deep, one at each end (u −16.0 to 0.0 and 57.0 to 73.0, v 0.0 to 7.5), and a hole 3.1 mm across on each at (−12.5, 4.0) and (69.5, 4.0). Each hole stands **13.54 mm from the nearest mains copper**, the pad of the blade terminal `OUT_S` or `OUT_C`, against the 13.25 mm that every mounting hole of this record keeps (the signed 10.0 mm, the extent E = 3.0 mm and the 0.25 mm drawing tolerance, A1), and 3.5 mm from the edge of its ear, E and 0.5 mm, as the main board's holes stand from its edges. The ears carry nothing else; they carry the board leg's two mounts and no longer set the standing leg's length (80.0 mm against the board's 57.0 mm width). The standing leg's ends, u −11.5 and 68.5, stand 1.0 mm in from the mounts' centres, so each mount hole (3.1 mm across, its edge at u −10.95 and 67.95) reaches 0.55 mm under the standing leg's end: the mounts' screws enter the board leg from the board's back face, and how the one bracket is drilled and tapped there is the bracket's drawing, the design task's. The owner said that the wall board is the easiest board to reconfigure to another dimension like wider and shorter; a wider rectangular board is therefore allowed, as this record's reading, and is left to the layout leaf, and the drawn outline and the ears' mount holes stay as they are here. The board's outline is a polygon, 89.0 mm over all along the wall edge and 42.5 mm deep, **2 662.5 mm²**, inside the lowest price band's 102 mm. Each mount's plastic screw is reached by a driver from the back face of the ear, which carries nothing there.

**The earth-bonded bracket keeps the basic creepage from mains copper.** The bracket is earthed through the wall, a bond the basis says is not measured, so it keeps the basis's basic creepage, 4.1 mm (A3, the same row selection as for mains copper of different nets), from every mains rectangle in three dimensions: the strip's plan edge is 0.0 mm from the nearest copper (the triacs' lands begin at v = 5.0, where the strip ends) and the strip stands 5.0 mm clear above the board, so the nearest mains copper is 5.00 mm from the bracket and no nearer, 0.9 mm over the rule. The lift is drawn at 5.0 mm and a lift under 4.1 mm fails the script.

**The order of fitting and of removal.** Fitting, the board and the triacs going in as one unit: (1) solder the board's back-face joints, every joint but the two triacs' six, with the board on the bench; (2) fix the board leg to the board through the two ears with the plastic spacers and screws, from the back face; (3) bolt each triac's tab face to the standing leg with its M3 screw and solder its three joints on the component face, where the iron reaches them; (4) put the unit to the metal wall through the cut and bolt the standing leg to the wall with two bolts through it at u = −2.5 and 59.5, each reached from the board's side along v; (5) plug the female push-on terminals on the tabs. Removal is the same steps in the reverse order, steps (5) and (4) taking the unit out whole: nothing is desoldered and no lead is bent or re-bent, since the triacs travel with the board on the bracket. **A failed triac is replaced on the bench** by unscrewing its tab and desoldering its three joints; that is a repair of the removed unit and not fitting or removal of it. The script holds the driver's way to each screw free: a path 6.0 mm wide along v from each tab screw (at its tab face's centre) and from each wall bolt to the board's far edge crosses no part body of the drawn board, and each mount's extent has no part within E of its centre. The second layout, with the confirm places, does not keep the tab screws' way free: its two optocoupler places and its six-way header stand across it, so fitting the places later needs the tab screws turned first, one more cost of D2. **Where the wall bolts stand.** The bolts stand at u = −2.5 and 59.5, 9.0 mm in from each end of the 80.0 mm standing leg (the rule held is 5.0 mm or more), 18.7 mm or more from the nearest tab screw and 62.0 mm from each other, with the driver's 6.0 mm way along v clear of every part body. Within the board's 57.0 mm width there is no such place: the part bodies in the way (the terminals `OUT_S` and `OUT_C`, the triacs, the varistors, the opto-triacs and the header) cover u 1.0 to 56.0 with no gap. A 60 mm leg centred on the board (u −1.5 to 58.5) would put its bolts, 5 mm in from its ends, at u = 3.5 and 53.5, under the bodies of `OUT_S` and `OUT_C`, so **60 mm cannot hold two tab screws 24.6 mm apart and two clear wall bolts**; the least leg that can has its bolts at u = −2.5 and 59.5, the nearest places the way keeps 0.5 mm clear of those bodies (they end at u = 1.0 and 56.0), and so is 72.0 mm long. The provisional 80.0 mm leg is 8.0 mm longer, so the bolts keep those places, nearest the tab screws and 9.0 mm in from the leg's ends; a place anywhere from u = −6.5 to −2.5 and from 59.5 to 63.5 would be as clear and 5.0 mm or more in from the ends, and the nearer places hold the leg to the wall closest to the triacs' tab faces.

**Why the bracket, against two other forms.** The owner's other two readings of the triacs' mounting are weighed here and not drawn:

| | The bracket (drawn) | The triacs past the board's short edge, their leads folded to the pads | The triacs on the wall at a distance, joined to the board by insulated wires |
|---|---|---|---|
| The leads | Straight, from the triac down to its pads | Each triac's leads are bent from the wall to the pads at fitting, and bent back at removal, so a lead is re-bent each time the board is fitted or removed | Straight on the triac; each of the three leads of a triac is joined to the board by an insulated mains wire |
| Fitted and removed as one unit with no joint desoldered and no lead re-bent | Yes | No: the leads bend again at every removal and each bend work-hardens a lead | No: the six wires are soldered at both ends, so a board removal desolders or unplugs six joints; no mains-rated connector for them is in any catalogue record read |
| Board | Body 57.0 × 42.5 mm with two ears, 89.0 mm over all | About 10 mm shorter, in the same price band (`controller-board-cost-estimate.md`) | Smaller by the triac row, with six wire pads |
| Cost | The bracket, unpriced, a few dollars at most | None added | Six insulated mains wires and their joints, unpriced |
| Standing | Drawn, with the owner's intent | Not drawn: it fails the criterion's "without re-bending a lead" | Not drawn: it fails "without desoldering" |

**The depth the bracket adds, unconfirmed.** Along the wall's normal the unit is the board's 42.5 mm and the bracket adds nothing to it: its strip lies inside the board's own 5.0 mm wall strip. Along the board's thickness the board leg stands 5.0 mm clear of the component face and the standing leg rises to 35.0 mm, 14.8 mm over the highest tab top (20.2 mm, § *The heater wall assembly, judged*, *The bracket*), so the unit stands 1.6 + 35.0 = 36.6 mm from its back face to the top of the leg, and the triacs' lead ends stand a further 6.4 to 8.4 mm behind the back face. Along the wall it is 87.0 mm long (the board leg) against the board's 57.0 mm, 15.0 mm more at one end and 15.0 mm at the other (the ears and the board leg's mounts), and its standing leg is 80.0 mm long. Along the wall's normal the unit is 42.5 mm against the owner's estimate of about 80 mm available (unmeasured), 37.5 mm to spare on that estimate. **Whether this stays within the cavity is unconfirmed, and is for the owner to check at assembly**: the machine record does not locate the metal wall or the plastic wall the owner plans to cut and gives no free height at that place, so no figure here fits the unit to a space. **The gap in front of the steel, about 10 mm by the owner's estimate** (2026-10-28, from drawings, unmeasured; the owner finds out when cutting): the standing leg is 5.0 mm thick and sits on the steel inside the cut, so it fits the gap with about 5 mm left between its inner face and the plane of the plastic wall (it would have just filled the earlier estimate of about 5 mm). The triacs' bodies, bolted to that inner face, stand at v 5.0 to 10.5 mm in the data, so on the estimate they reach the plane of the plastic wall and stand 0.5 mm past it at the most: they are in the opening of the cut and not behind plastic only if the window's outline covers them, and it does over all but the lowest 0 to 1 mm of each body (the window runs from 5.0 mm above the component face and the plastic's lower face stands 4.0 to 5.0 mm above it), which the owner checks when cutting. Each driver's way to a tab screw or a wall bolt runs along v at a height inside the window, so it passes the plastic wall through the cut and not through the plastic. Of the unit's 42.5 mm along the wall's normal, about 10 mm stands in the gap and about 32.5 mm stands in front of the plastic wall; the owner's estimate of about 80 mm perpendicular to the wall does not say whether it is counted from the steel or from the plastic, so the spare is 37.5 mm from the steel or 47.5 mm from the plastic, unmeasured either way. **The opening in the plastic is stated in § *The wall cut, and the owner's acceptance*:** the unit crosses the plane of the plastic wall as one piece, board edge-on, so the board's own section (57.0 mm wide, 1.6 mm thick, with the lead ends behind it) passes through the plastic as well as the leg; that is the 89.0 × 45.0 mm = 4005.0 mm² opening, larger than the window, and the window (the leg's face on the steel) is the smaller part of it.

**Mains copper and the metal wall.** The basis lists one place the metal wall enters: the triac's insulated tab to the machine's metal wall, basic insulation to earth (`heater-switch` in `hardware/sunbeam-em7000/separation-basis.yaml`). It gives no distance for mains copper over a board edge toward that wall, and its signed pair, 3.0 mm and 10.0 mm, is the reinforced one for mains to low voltage. The wall board's mains copper therefore keeps a distance this record sets: **at least 4.1 mm from the board edge that lies against the metal wall**, the basis's basic creepage, interpolated at 253 V between its 250 V and 320 V rows at pollution degree 3 and rounded up (4.1 mm, which exceeds the 1.5 mm clearance), applied between mains copper and the earth-bonded wall, a bond that the basis says is not measured (the owner measures it at bring-up); the script reads the 4.1 mm from the basis, and the drawn strip is 5.0 mm, 0.9 mm over it. The board stands edge-on, its wall edge flush with the bracket's outer face (A22), so the edge against the wall is the edge at v = 0 and the copper is 5.0 mm from the metal in the plane of the board. Every mains rectangle, every part body and every mains lead end of the data block starts at v = 5.0 or more, the drawn strip (the script checks all three against the 4.1 mm rule, with no exceptions), which, with the rest, makes the body 42.5 mm deep and 57.0 mm wide, and the board with its ears 89.0 mm over all, inside the 102 × 102 mm band. **The one metal that joins the board to the wall is the bracket**, which is earth-bonded through the wall and held 5.0 mm, drawn, from mains copper in three dimensions (§ *The bracket*), 4.1 mm being the rule; the mount screws and spacers are plastic, and no other metal fixing joins the board to the wall. **This wall-to-copper barrier is one the signed basis does not list**, and this record reports it as such without changing the basis (§ The interlock block). Whether the owner amends the basis to sign a basic mains-to-earth pair is an owner decision pending (§ Owner decisions pending, D15).

**The wall cut, and the owner's acceptance.** The cut is one window that exposes the metal under the bracket's standing leg, the whole outer face of the leg, **80.0 mm long and 30.0 mm high** (from the lift of 5.0 mm to the leg's top at 35.0 mm above the board's face), **2400.0 mm² in one place**, and nothing else: there is no passage in the wall for the mains conductors, because the owner said the wires will go from the cavity next door the other direction or from above and that the owner will route them where needed (owner statement, 2026-10-28), which this record reads as no conductor crossing the wall; § *The heater wall assembly, judged*, *The element harness*). **The opening in the plastic that admits the unit is a second figure, 89.0 × 45.0 mm = 4005.0 mm²**, beside the window: the unit goes into the machine as one piece with the board edge-on, so its whole cross-section passes the plastic wall, which stands about 10 mm in front of the steel (owner estimate), and the smallest rectangle in that plane that admits it without tilting runs along the wall from u −16.0 to 73.0 (89.0 mm: the board's mount ears; the board leg at −15.0 to 72.0, the standing leg at −11.5 to 68.5 and the board at 0.0 to 57.0 lie inside it) and across from z −10.0 to 35.0 mm about the board's component face (45.0 mm: the leg's top at 35.0 mm, 1.6 + 35.0 = 36.6 mm from the back face, down to the lowest triac lead end, 1.6 + 8.4 = 10.0 mm below that face; the lead ends stand 6.4 to 8.4 mm behind the back face). The window is the part of the cut that exposes the steel under the leg's face; the plastic opening is the part that lets the unit through. **The owner's estimate of 80 × 30 to 35 mm is the spreader, not shown to be the plastic opening.** Whether the plastic can be cut to the unit's envelope is the owner's open measurement and decision, revisited with the acceptance below. If it cannot, the unit must be reshaped: the lead ends behind the board give first (the leads are not cut, and the owner may trim them after soldering; trimmed, the height falls toward the 36.6 mm to the leg's top), and the ears' 2.0 mm over the board leg (89.0 against 87.0 mm) second; the leg's top does not give without shortening the spreader. The heights of the varistors above the board are not claimed (A22). The 80.0 mm length and the 30.0 mm height are the owner's estimated maximum (owner statement, 2026-10-28: "I could probably mount an 80 x 30-35 mm spreader", estimated from drawings of what the owner thinks is behind the wall and unmeasured); 30.0 mm is the low end of the owner's 30 to 35 mm, and 35.0 mm is the other choice (2800.0 mm² at 80.0 mm). **The 80.0 mm length and the 30.0 mm height are provisional drawn defaults**, held as data values (`window_l` and `top_z`) and to be replaced by the owner's measured maximum spreader, when the preliminary acceptance below is revisited (D11); the length holds two tab screws 24.6 mm apart and two clear wall bolts (§ *The order of fitting and of removal*), which a 60 mm leg cannot, and 72 mm is the least that does. **The other choices of length and their cut areas, at 30.0 mm tall:** 40 mm, 1200.0 mm²; 50 mm, 1500.0 mm²; 60 mm, 1800.0 mm²; 100 mm, 3000.0 mm²; 120 mm, 3600.0 mm²; and the 35.0 mm height at 80 mm, 2800.0 mm². A shorter window needs a lower sink ambient or fails the continuous-full-power case; a longer one holds at a higher ambient (§ *The heater wall assembly, judged*, *The heat*, which gives each length's steady power and time at full power). Before the bracket the cut was 410 mm² in three: two windows each at least 10.4 × 15.9 mm = 165 mm² under the two tab faces, and the passage; the leg's whole face is now on the metal, so the window is larger and the two windows are one (§ *The heater wall assembly, judged*, *The wall cut: the reason for the larger cut*). The low-voltage cable does not use the window; it leaves by the right cut-away that the bundle already has. The machine record does not locate the metal wall or the plastic wall the owner plans to cut, so this record does not place the cut against the cavity. **The owner accepted the wall cut, kept as small as the passage needs**, as the division's acceptance criteria record it on 2026-10-24, resting on the owner's plan of 2026-10-04 and 2026-10-23 to cut away the plastic side wall at the bottom of the machine near the pumps, so that the heat plate's bond to the metal wall is reached (`controller-board-design-constraints.md` § Enclosure air temperature, *Premises*; owner statements); that acceptance was given for the 410 mm² and the figure above is not that figure; the reason for the larger cut is recorded beside it in § *The heater wall assembly, judged*. **On 2026-10-28 the owner accepted the wall cut as preliminary, to be revisited when the owner cuts and measures** (D11): the operator offered the option 'Accept the cut as preliminary: you would say something like "accepted as preliminary, to be revisited when I cut"' and the owner replied "Do 1", which chose it (owner statement, recorded as said and no more). **The figures so accepted are the provisional ones: the window of 2400.0 mm² in one place (30.0 × 80.0 mm) and the opening in the plastic that admits the unit, 89.0 × 45.0 mm = 4005.0 mm².** This is not an acceptance of a final size: the owner's measured maximum spreader and the real opening replace these figures when known, and the board's dimensions are rearranged then. The owner had said earlier the same day that the size of the cut does not matter right now, the wall board being the easiest to reconfigure to another dimension, and later "Probably not that big, but I'm not convinced it needs to be that big", wanting a preliminary design of the whole board now with the dimensions rearranged later if need be. The acceptance is the owner's reply "Do 1" of 2026-10-28 and is recorded in the graph as evidence for the wall-cut criterion by the operator; the script holds the acceptance wording and the figures together, not the acceptance, and cannot prove it exists, and recording a changed acceptance means changing the data, the script and this record together, a visible diff. **How the wall board is supported** is the bracket (A22): the two mounts on the ears and the two wall bolts through the standing leg. What stays the design task's is the bracket's drawing, the spacers and screws, and the footprint of each mounting hole, which stays inside E (A1).

**Heat.** The two triacs dissipate 4.25 W and 4.84 W each (`controller-board-function-forms.md` § Parts off the boards) and lie 14.2 mm apart, body to body. **They share one bracket and, through it, one metal wall**: both tab faces lie on the bracket's one standing leg, which is each one's heatsink and carries the heat to the wall, so each heats the leg the other sits on, and the nearer they stand the more of one's heat the other's face feels. The sheets give the junction's side of that and nothing of the wall's: the triac's junction-to-case resistance is 2.1 K/W (P3, in the forms record), so the junction stands 8.9 K and 10.2 K over its case at the two dissipations, and with the junction held under 125 °C the case may stand at 116.1 °C and 114.8 °C. At 70 °C, the conservative case (the constraints record's enclosure figure; the wall board's own air is the room's, 45 °C by the owner's working figure of 2026-10-28), the bracket, the wall and the interfaces may then rise 44.8 K over the air for the 4.84 W triac: **9.3 K/W from the tab face to the air if it heats the wall alone, and 4.9 K/W if both heat it at once** (9.09 W together). The sheets give neither the interface's nor the wall's resistance, so whether the bracket and the wall are that good a sink is judged in § The heater wall assembly, judged, *The heat*, against two ceilings, with the interface compound, the bracket as the spreader and the steel wall counted. The script holds the two bodies at least 10.0 mm apart (A31, an assumption, 4.2 mm under the 14.2 mm drawn) and prints the arithmetic above from the forms record's figures. The relay is not on this board, so no part of it dissipates a watt but the triacs; the opto-triacs, whose operating range ends at 85 °C (P4; `controller-board-function-forms.md` § Parts off the boards, S16), lie 20.0 mm from the triac bodies, the 20 mm of A8 held (`heat_opto`), and the script tests that distance for the unpopulated places too. **Hand access.** Every joint of the board but the two triacs' six is on its back face, which carries no part but the triacs, so the owner's iron reaches them before the board is mounted; the triacs' joints are on the component face, where the iron reaches them with the triacs bolted to the bracket's leg and the unit on the bench.

**The mains-presence confirm: polarity, the condition it was dropped on, and the places.** *Polarity.* The board as found switches the neutral side of every load, and `LINE1` reaches each element's fixed lead by the daisy chain (`connector-pinouts.md`, *Which conductor of a load the original board's switching device interrupts: the neutral side*), so on the wall board an element's switched lead `OUT_x` goes to its triac and the triac to the neutral at `RET`, and the board has no `LINE` feed. A confirm across `OUT_x` and `RET` (an AC-input optocoupler through 120 kΩ, 1.8 mA at the span's bottom) therefore reads **on when the triac is open and the element intact**, since the node floats up to line through the element's 47.0 to 52.7 Ω, and **off when the triac conducts**, since the node then stands at the triac's on-state drop, 1.55 V at most at 22.5 A (P3, Table 2). Stuck-on reads off while commanded off, failed-to-close reads on while commanded on, an open element reads off, and so does everything with the interlock open, since nothing then reaches `LINE1`. The forms record's wording, "on while mains reaches the element", and its section *The heater switch's leakage against the mains-presence confirm* assume a live-side switch, where the node would stand at neutral through the element when the triac is open; the table of disagreements records it and the forms record is not edited. *The leakage bound, re-derived.* With the triac open and the element intact, the leakage and any snubber current run from the node to neutral beside the confirm's branch and through the element: a 0.1 µF capacitor would pass 7.9 mA at 253 V and drop 0.37 V across 47.0 Ω, which the confirm does not feel against the 253 V at the node; with the element open the node is fed from nothing, so neither the snubber nor the triac's leakage (5 µA at 25 °C, 2 mA at 125 °C, P3) can raise it. The forms record's bound of about 22 nF therefore falls away for this topology. *The condition.* The owner's wish was a minimal board that is hand-soldered, and the two confirms were to be dropped from the populated board on the condition that the sensing design resolves a stuck-on triac, a triac that fails to close and an open element. The design reads the supply current (the shunt in the neutral return, 11.01 A with every load on, 15 A in the overload band) with the supply voltage (`VMEAS`) and each heater's resistance modelled over temperature and calibrated one heater at a time (the coffee element 4.80 A and the steam element 5.38 A at 253 V, 4.10 A and 4.60 A at 216 V), the pumps and valves adding at most 0.46 + 0.19 + 0.129 = 0.78 A (0.67 A at 216 V), known from what is commanded. *Stuck-on* (current while commanded off): the extra current is 4.10 A at the least, against at most 0.78 A of error if the model of the pumps and valves were wrong by all of their current, so a threshold anywhere in the 3.3 A between them resolves it, and a sensing error of ±1.6 A (11 % of the 15 A band) is allowed. **Resolved.** *Failed-to-close and open element* (no heater current when commanded on): the deficit is the same 4.10 A or more, resolved as "the commanded heater draws nothing". **Not resolved apart:** a triac that does not close and an element that is open both draw nothing; both want the same response (heater off, interlock open, fault flagged) and neither is a hazard, but the confirm by its polarity would have told them apart (failed-to-close reads on, open reads off). *Which heater:* the two currents differ by 0.58 A at 253 V and 0.49 A at 216 V, so naming the heater from the total needs the sensing error and the model of the pumps and valves under ±0.24 A, 1.6 % of the band; the response, cutting both, does not need the name. **The condition is therefore only partly met**: it is met for the hazard and for "no current when commanded", and **not for the split between a triac that fails to close and an open element**, which is a diagnosis. **Owner decision pending (§ Owner decisions pending, D2): whether the two confirms come back.** They stay dropped for now, the owner's wish for a minimal board that is hand-soldered, and a triac that fails to close and an open element give the same safe response, the heater power removed or held off, so no hazard waits on the answer. **Recommendation: keep them dropped, and revisit when the sensing task has proved the current check** (`DEL-SENSOR-NECESSITY-PROVEN.C2`). **What adding them back costs:** two places of two parts each (an optocoupler and a 120 kΩ resistor), four parts, 12 more hand joints, and a board 23.5 % larger, 57.0 × 52.5 mm in place of 57.0 × 42.5 mm. A stuck-at-zero reading of the supply current would hide a stuck-on triac, so the block thermistors, which read a rising temperature with the heater commanded off, are the second channel the control can use; the sensing task declares the accuracy (`DEL-SENSOR-NECESSITY-PROVEN.C2`). *The places.* Kept unpopulated they obey the separation rules as if fitted. They are drawn as a second layout in the data (`wall_dnp`) and the script runs every wall check on it: **57.0 × 52.5 mm = 2 992.5 mm² against 57.0 × 42.5 = 2 422.5 mm², 570.0 mm² or 23.5 % more**, 10.0 mm deeper, with a six-way header (42 joints fitted against 39) and a T of slots across the row; fitted later they add 12 joints and one Extended type. Four mains ends then fill the row the optocouplers stand in, each 5.0 mm from the next, so the header, which must stand 10.0 mm from mains copper, can no longer stand in the middle of it and moves above them. The board price stays 4.00 USD in the band. The owner's test was that the board stay at the minimal outline; it does not, so the places are not on the drawn board, and adding the confirm later costs a respin of this 4.00 USD board. The main board's two `IN_COND` inputs stay reserved and the cable keeps its spare ways.

**Snubbers and varistors, reviewed.** *The snubbers are dropped.* The triac is the BTA16-600BRG, which P3 lists as the standard four-quadrant "B" type (marking BTA16-600B) and not a Snubberless™ one (those are the ...BW types), whatever the forms record and the brief call it. P3 rates it for a static dV/dt of at least 400 V/µs at 125 °C and for a commutating (dV/dt)c of at least 10 V/µs at a (dI/dt)c of 7 A/ms. On a resistive load the current and the voltage reach zero together: at the steam element's 5.38 A the current falls at 2π × 50 Hz × 5.38 A × √2 = 2.39 A/ms (2.87 A/ms at 60 Hz), 2.9 times under the 7 A/ms (2.4 times at 60 Hz), and the voltage reapplied at that instant rises at 2π × 50 Hz × 358 V = 0.113 V/µs (0.135 V/µs at 60 Hz) against 10 V/µs, 88 times under (74 times). The opto-triac MOC3083M (P4) is a zero-cross part (inhibit voltage 20 V at most) with a static dv/dt of 600 V/µs at least, and its sheet's own hot-line circuit says its 39 Ω and 0.01 µF snubber "may or may not be necessary depending upon the particular triac and load use". A snubber is also a path around the off triac, and each costs two parts and four hand joints. **Both are dropped.** What the snubber would have bought is protection against line transients faster than the 400 V/µs static rating: a transient that reached the triac through the element's 47.0 Ω can turn the off triac on for the rest of the half-cycle, at most 10 ms, 13.6 J into the steam element at 253 V, a nuisance and not a hazard, which the supply-current check and the element's thermostat bound. *The emissions and flicker criteria* (`OBL-ELECTROMAGNETIC-COMPATIBILITY-001.C1` and `.C2`) are not affected: a zero-cross opto-triac fires within 20 V of the zero, a step of at most 20 V / 47.0 Ω = 0.43 A into the element, and the triac turns off at its current zero, so the heaters add no edge that a snubber would have softened; flicker and harmonics follow from the firing pattern the control sets, not from a snubber. No limit is quoted: the standard is declared for the jurisdiction and this record takes no figure from memory. *The varistors are kept.* The surge criterion (`REQ-ELECTRICAL-INSTALL-001.C10`) asks the protection to be rated for the surge that the basis's overvoltage category assigns, a rated impulse of 2.5 kV basic and 4.0 kV reinforced (`separation-basis.yaml`), judged from the makers' ratings. The devices on a heater branch are the triac, which blocks 600 V and takes 700 V non-repetitively for 10 ms (P3, VDSM = VDRM + 100 V), and the opto-triac, which blocks 800 V and carries 1 A for a single cycle (P4) through the 360 Ω of its gate network: a 2.5 kV surge across the branch would drive up to 2 500 V / 360 Ω = 6.9 A through the opto-triac, 6.9 times its single-cycle rating, and 2 500 V / 47.0 Ω = 53 A through the triac, a third of its 160 A. The sheets give no rating for a microsecond pulse, so neither can be judged within makers' ratings with or without a varistor, and a clamp that keeps the opto-triac within 1 A would have to stand at 360 V, which is the line's peak; the maker's own noisy-environment circuit puts a varistor beside the snubber "to protect the power triac and driver from transient overvoltages > VDRM max" (P14, Figure 8). What can be said is that these two varistors are the only surge clamp any record draws on the heater branch, and that the board-entry varistor, decided but not yet drawn, will be the only other clamp on the mains path. **They stay** (two parts, four hand joints, 120 mm², standing in the room the 20 mm heat rule leaves, so the outline would not shrink without them). *Owner decision pending (§ Owner decisions pending, D7):* drop both, which saves four joints; the board-entry varistor's clamp is sourced, 775 V at 50 A, over the triac's 600 V and 700 V, and the branch is not judged inside the makers' ratings with or without the wall varistors (absent: the triac's and opto-triac's microsecond withstand), so the judgement of the varistor's clamp is made in § The heater wall assembly, judged, *The surge clamps*, and the wall board's design task is not left to make it.

### The heater wall assembly, judged

This section judges the parts, the heat, the bracket, the harness and the surge clamps of the heater wall assembly, and carries the owner's pending questions to what each would change. It is analysis on paper: no KiCad project is opened and no design record is written under `hardware/sunbeam-em7000/`, the board's YAML records, its derating policy among them, belonging to the schematic and layout task. Each figure is read from a maker's document named in § Sources read (P3, P4, P17 and P18, read on 2026-10-28), from this record's own data, or is stated as an assumption with its reason. **A rating that could not be read from a maker's current document is absent, and the carried 15 A stands.** The enclosure air figure of 70 °C is an assumption that bring-up measures (`controller-board-design-constraints.md` § Enclosure air temperature; `DEL-HW-BRING-UP.C13`), and the owner said on 2026-10-28 that the 70 is in the controller area and not where this wall board sits, where the air will basically be ambient room: the triacs stand outside the enclosure on the metal wall (the owner's plan of 2026-10-23), in room air, for which the owner's working figure is 45 °C, stated and not measured. This section is judged at 45 °C and, as the record's conservative case, at 70 °C.

**The parts.** The targets are those of `controller-board-function-forms.md` § The heater switch against the carried-forward properties; the peak of the supply span's top is 253 V × √2 = 358 V.

| Part | Rating read (maker's document) | Against the load | Why this part |
|---|---|---|---|
| Triac BTA16-600BRG, insulated TO-220AB (P3, Rev 11, May 2018) | VDRM and VRRM 600 V by the "600" code, VDSM 700 V for 10 ms; IT(RMS) 16 A at Tc = 86 °C; ITSM 160 A (20 ms); I²t 144 A²s; Tj 125 °C at most; Rth(j-c) 2.1 °C/W; Rth(j-a) 60 °C/W; IGT 50 mA at most (B grade); insulated tab 2 500 VRMS | Blocking 600 / 358 = 1.68 times the peak, over the forms record's 11 % margin rule; steady current 5.38 / 16 = 0.34 (steam) and 4.80 / 16 = 0.30 (coffee) of IT(RMS); the 15 A overload band is 15 / 16 = 0.94 and is held only until the fuse clears; dissipation 4.25 W and 4.84 W (forms record) | It meets every target the forms record sets; the four-quadrant B grade is the catalogue's part; the sheet's BW grade is the alternative |
| Opto-triac MOC3083M (P4, Rev. 2, September 2022); the Lite-On MOC3083 (C10797) is the stocked equivalent | VDRM 800 V; ITSM 1 A; inhibit voltage 20 V at most; IFT 5 mA at most; IDRM1 500 nA at most; VISO 4 170 VACRMS for 1 minute; operating −40 to +85 °C; junction −40 to +100 °C | Blocking 800 / 358 = 2.23 times the peak; with a gate resistor of 360 Ω a trigger at the line's peak would pass (358 − 1.3) / 360 = 0.99 A of the 1 A, but a zero-cross part fires only below its 20 V inhibit, so the gate current is at most 20 / 360 = 0.056 A; the 85 °C range is 40 K above the wall assembly's 45 °C (owner's working figure) and 15 K above 70 °C, the record's conservative case, and the part stands 20.0 mm from the triac bodies (A8) | The zero-cross part the forms record requires, confirmed on the maker's document; the triac's 600 V governs the branch, not the opto-triac's 800 V |

**The shares this judgement is made against.** Two shares are stated for the board's derating policy, which the schematic and layout task writes down and carries **unchanged**, so that it does not reopen this judgement. They are not read from any document and are given as stated reasons: the **temperature share** is 0.8 of the maker's junction limit in degrees Celsius, 0.8 × 125 = 100 °C, a conventional 25 K margin for an ambient and a wall nobody has measured; the **current share** for a switching part is 0.5 of its rated current at its case temperature, 8 A for the triac, and for a connector or joiner it is the carried 15 A against the rating once a maker's rating is read (none is). The steady element currents sit inside both: 0.34 and 0.30 against 0.5.

**The heat.** The two ceilings are the maker's absolute junction limit, **125 °C** (P3, Table 1), and one lower ceiling, **100 °C**, the temperature share above, whose reason is stated and not sourced. The junction stands P × Rth(j-c) over its case: 4.25 × 2.1 = 8.9 K (coffee) and 4.84 × 2.1 = 10.2 K (steam); 9.09 W together.

**What the owner said on 2026-10-28 that redesigns the assembly.** Each is an owner statement or question, recorded as said and no more; the owner gave them in session. A design consequence drawn from one is labelled as this record's reading.

1. *The bracket is the heat spreader.* An L bracket that both holds the PCB rigid for installation and spreads the triacs' heat: "It doesn't have to be this, just seemed easy." An earlier reading drew a separate aluminium plate beside the window; the owner's 2.5 mm stainless wall (item 4) makes the sideways path through the steel to such a plate poor, which is why the bracket itself is the spreader and the plate is dropped from the drawn design.
2. *Height, length and the operating profile.* About 25 to 30 mm of height is available for the spreader, and the owner asked for the least length of wall cut at 25 mm tall that gives good heat performance ("a wall cut of 25 X what ever is the minimum that gives us good heat performance is what I need to know"): that is the owner's question, answered by the length tables below and not a length the owner gave. Later the owner said they will tell a heat spreader maximum and build to that size, which the owner has not yet measured: "I'll tell you a heat spreader max, we will build to that size", and "If later we need to limit max dual power time, fine". The owner said both heaters will likely only ever be on at full power together for about 2 minutes at most, then maintain temperature at much lower power, and that the idle draw is unknown: "we haven't built our system yet". This is an **expectation of the operating profile, not a requirement, and nothing enforces it.** About 80 mm is available perpendicular to the wall (the owner's estimate, unmeasured). The owner later gave an estimate of the maximum spreader (item 6).
3. *The wall is two layers.* The external steel and an internal plastic layer that the owner will cut through and mount the spreader into; there may be about 5 mm between them, unmeasured (the owner finds out when cutting); the owner later replaced this with about 10 mm (item 6).
4. *The spreader and the steel.* "The aluminium spreader will be screwed with thermal paste to a stainless steel wall that is 2.5 mm thick that is the side of the machine", and the steel wall is the entire side of the machine (a large sheet, not only the spreader's patch). The aluminium, the paste, the stainless steel and its 2.5 mm are the owner's; the aluminium's conductivity and heat capacity, the steel's conductivity and the paste's resistance are this record's stated figures, and Wakefield 120 (P17) is only the record's stand-in for a paste's resistance: the owner's paste is not shown to be that product.
5. *The air at this board.* "No, the 70 is in the controller are, not where this wall board sits. That will basically be ambient room, maybe we say 45 for some heating on a hot day" (the owner's working figure, stated, not measured; the room is up to 35 °C, the top of the span in `reference-machine.md` § Ambient).
6. *The spreader maximum and the gap.* "I could probably mount an 80 x 30-35 mm spreader", and the distance from the cut plastic wall to the stainless mounting surface is approximately 10 mm, replacing the earlier estimate of about 5 mm. Both are estimates from drawings of what the owner thinks is behind the wall, unmeasured; the owner finds out when cutting. The drawn default is the owner's maximum at the low end of the height, 80.0 × 30.0 mm, with 35 mm carried as the other choice.
7. *The wires and the soldering.* The owner asked why the wires need to touch the wall and said "The wires will be going from the cavity next door the other direction or from above. I'll just route them where needed.", and asked "I assume the triacs are through hole soldered to the board right? You aren't talking about extending the triacs via wires right?" The owner asked and did not assert; this record's reading is that the triacs are through-hole soldered and that no conductor needs to cross the wall, from which the passage in the wall is withdrawn.
8. *The size of the cut.* "It doesn't really matter right now, this is the easiest board to reconfigure to another dimension like wider and shorter." Later: "Probably not that big, but I'm not convinced it needs to be that big. I want to stop this back and forth, I want a preliminary design of the board itself that gets all the components worked out etc and if we have to rearrange later to change the board dimensions that is easy enough." The owner accepted the cut as preliminary later the same day, the figures provisional until the owner cuts and measures (D11; § The heater wall board, *The wall cut, and the owner's acceptance*).

**The ambient.** The primary ambient of this section is therefore **45 °C** (item 5, owner's working figure), and 70 °C is not the air at the opto-triacs or at the board's parts here. The constraints record's enclosure figure is 70 °C (`controller-board-design-constraints.md` § Enclosure air temperature), so the same arithmetic is also stated at **70 °C as the record's conservative case**, labelled as such: the wall board is not in the controller's air, and the premise that the heater switches stand outside the enclosure (the owner's plan of 2026-10-23) still holds.

| | 125 °C ceiling | 100 °C ceiling |
|---|---|---|
| Case may stand at (coffee, steam) | 125 − 8.9 = 116.1 °C; 125 − 10.2 = 114.8 °C | 100 − 8.9 = 91.1 °C; 100 − 10.2 = 89.8 °C |
| Permitted rise over 45 °C air, steam | 69.8 K | 44.8 K |
| Permitted rise over 70 °C air, steam (conservative case) | 44.8 K | 19.8 K |
| Tab-to-air resistance, steam alone, at 45 °C (at 70 °C) | 69.8 / 4.84 = 14.4 K/W (9.3) | 44.8 / 4.84 = 9.3 K/W (4.1) |
| Tab-to-air resistance, both triacs on the one wall, at 45 °C (at 70 °C) | 69.8 / 9.09 = 7.7 K/W (4.9) | 44.8 / 9.09 = 4.9 K/W (2.2) |
| Of that, the interface compound's share, steam | 4.84 × 0.50 = 2.4 K | 2.4 K |
| Leg to air for 9.09 W, at 45 °C (at 70 °C) | 67.4 / 9.09 = **7.42 K/W** (4.67) | 42.4 / 9.09 = **4.67 K/W** (1.92) |

The compound between each tab face and the leg is Wakefield's 120 series, 0.50 °C/W for a TO-220 (P17); that figure is at 0.9 N·m and the triac's own sheet gives a recommended torque of 0.55 N·m and a maximum of 0.70 N·m, so it is typical and not a worst case; each 0.1 K/W more at the steam triac costs 0.5 K. The insulated tab needs no insulating pad.

**The path and the model.** The heat of each junction crosses, in series: the junction-to-case resistance (2.1 K/W, from the sheet); the compound between the tab face and the bracket's standing leg (0.50 K/W per triac); the leg itself, aluminium, 5.0 mm through its thickness; the film of thermal paste between the leg's outer face and the steel; and the steel wall, which spreads the heat sideways as a fin and gives it to room air from its outer face by natural convection and radiation. The wall is modelled (stated, not sourced) as a semi-infinite fin from a rectangular contact patch H × L on a large sheet, one face exposed: **conductance G = h × (H × L) + P × √(h × k × t)**, with P = 2 × (H + L) the patch's perimeter, h the film coefficient, k the steel's conductivity and t its thickness, and **R_wall = 1 / G**. The patch is the window, H = 30.0 mm and L its length. The leg's own terms are the bracket's conduction, 5 mm over the face H × L at 15 W/(m·K) (stated, a floor under any metal; the conductivity of aluminium is far higher), and the paste film, 0.002 in (stated) at 0.05 K·in²/W per 0.001 in (P17), so 0.1 / (the face in in²). Worked at the drawn L = 80 mm and H = 30.0 mm: the face is 30.0 × 80.0 = 2 400 mm² = 3.720 in²; the bracket 0.005 / (15 × 2.400 × 10⁻³) = 0.139 K/W and the film 0.1 / 3.720 = 0.027 K/W, together 0.17 K/W; for the wall, at h = 10, h × H × L = 10 × 0.030 × 0.080 = 0.0240 W/K, √(10 × 15 × 0.0025) = 0.612 W/(m·K), P = 2 × (0.030 + 0.080) = 0.220 m, so G = 0.0240 + 0.220 × 0.612 = 0.1587 W/K and R_wall = **6.30 K/W**; at h = 5, 0.0120 + 0.220 × 0.433 = 0.1073 W/K and R_wall = **9.32 K/W**. The model counts neither the steel's heat storage nor its transient spreading, both of which lengthen the times below, and it takes the outer face as open to room air, which is unmeasured.

| Input | Value | Grade |
|---|---|---|
| Junction to case | 2.1 K/W (AC) | sourced (P3) |
| Compound, tab face to leg | 0.50 K/W per TO-220, typical | sourced, weakest (P17 is a distributor's print of a 2007 catalogue page, not the maker's current document); the owner's paste is not shown to be that product |
| Steam triac's share of the total dissipation | 4.84 / 9.09 = 0.5325 (the forms record's dissipations) | sourced (forms record, from P3) |
| Wall material and thickness | stainless steel, 2.5 mm, the entire side of the machine | owner statement (items 3 and 4) |
| Steel conductivity k | 15 W/(m·K), a common-grade figure; the grade is unknown | stated, not read from any document |
| Film coefficient h of the outer face, natural convection and radiation | 10 (best) and 5 (worst) W/(m²·K), one face exposed | stated, an engineering range |
| Bracket material and conduction | aluminium, 5.0 mm; conduction at a floor of 15 W/(m·K) | material: owner statement (item 4); conductivity: stated, not read from any document |
| Paste film between leg and steel | 0.002 in, at P17's 0.05 K·in²/W per 0.001 in as a stand-in | the paste is the owner's (item 4); the film and its resistance are stated |
| Aluminium density and specific heat | 2 700 kg/m³ and 900 J/(kg·K) | stated |
| Leg volume for the heat capacity | L × 35 mm × 5 mm, the 35.0 mm being the leg's height over the board's component face (about 42.5 J/K per 100 mm of length) | stated |
| Ambient at the wall board | 45 °C (and 70 °C, the conservative case) | owner's working figure (item 5); 70 °C is the project's assumption |
| Operating profile | about 2 minutes at full power on both, then much lower power; idle draw unknown | owner statement (item 2), an expectation and not a requirement |

**Steady state, and the time to the ceiling.** With the steam triac carrying 0.5325 of the total P and the compound and junction terms in series with the leg, the hotter junction stands at **T_j = T_a + P × (R_wall + R_bracket + R_film) + P × 0.5325 × (0.50 + 2.1)**, that is T_a + P × (R_path + 1.385). The steady total power a ceiling permits is **P_ss = (T_ceiling − T_a) / (R_path + 1.385)**, and since a triac's dissipation is its on-state loss and scales with the fraction of half-cycles it conducts, P_ss / 9.09 W is the largest mean duty, the same on both, the assembly holds without limit; no idle duty is assumed, because the owner has not built or measured the control, so P_ss is given as the permitted fraction. For the time both heaters can run at full power (9.09 W) from a start at the ambient, the leg's heat capacity is lumped, C = 2 700 × 900 × (L × 0.035 × 0.005), the time constant is τ = (R_wall + R_bracket + R_film) × C, and T_j(t) = T_a + 9.09 × (R_wall + R_bracket + R_film) × (1 − e^(−t/τ)) + 9.09 × 0.5325 × 2.6; solving for the ceiling gives t = −τ × ln(1 − X / (9.09 × R_path)) with X = T_ceiling − T_a − 12.59 K, and the assembly holds without limit when X is at or over 9.09 × R_path. At the drawn 80 mm, H = 30.0 mm and h = 10: C = 34.0 J/K, R_path = 6.30 + 0.17 = 6.47 K/W, τ = 220 s, P_ss at 125 °C and 45 °C = 80 / (6.47 + 1.385) = 10.19 W, T_j after 2 minutes = 45 + 58.8 × (1 − e^(−120/220)) + 12.6 = 82.3 °C, and 125 °C is never reached (X = 67.4 K is over 9.09 × R_path = 58.8 K), while the time to 100 °C is −220 × ln(1 − 42.4 / 58.8) = 281 s.

At 45 °C (the primary ambient). T_j at 2 min is the hotter junction after 120 s of full power from the ambient; the cut is 30.0 mm × L; 80 mm is the drawn default (the owner's estimated maximum), the others the lengths the owner may build to.

| L (mm) | Cut (mm²) | h | R_wall (K/W) | Leg terms (K/W) | Steady total power at 125 °C | at 100 °C | Time at full power to 125 °C | to 100 °C | T_j at 2 min (°C) |
|---|---|---|---|---|---|---|---|---|---|
| 40 | 1 200.0 | 10 | 10.23 | 0.33 | 6.70 W (74 %) | 4.60 W (51 %) | 218 s | 105 s | 104 |
| 40 | 1 200.0 | 5 | 15.01 | 0.33 | 4.78 W (53 %) | 3.29 W (36 %) | 172 s | 95 s | 109 |
| 50 | 1 500.0 | 10 | 8.85 | 0.27 | 7.62 W (84 %) | 5.24 W (58 %) | 326 s | 139 s | 96 |
| 50 | 1 500.0 | 5 | 13.02 | 0.27 | 5.45 W (60 %) | 3.75 W (41 %) | 231 s | 122 s | 99 |
| 60 | 1 800.0 | 10 | 7.80 | 0.22 | 8.51 W (94 %) | 5.85 W (64 %) | 529 s | 178 s | 90 |
| 60 | 1 800.0 | 5 | 11.50 | 0.22 | 6.10 W (67 %) | 4.20 W (46 %) | 300 s | 152 s | 93 |
| **80** | **2 400.0** | 10 | 6.30 | 0.17 | 10.19 W (112 %), holds | 7.01 W (77 %) | holds, no limit | 281 s | 82 |
| **80** | **2 400.0** | 5 | 9.32 | 0.17 | 7.36 W (81 %) | 5.06 W (56 %) | 491 s | 218 s | 84 |
| 100 | 3 000.0 | 10 | 5.28 | 0.13 | 11.76 W (129 %), holds | 8.09 W (89 %) | holds, no limit | 455 s | 78 |
| 100 | 3 000.0 | 5 | 7.84 | 0.13 | 8.55 W (94 %) | 5.88 W (65 %) | 904 s | 298 s | 79 |
| 120 | 3 600.0 | 10 | 4.55 | 0.11 | 13.23 W (146 %), holds | 9.10 W (100 %), holds | holds, no limit | holds, no limit | 74 |
| 120 | 3 600.0 | 5 | 6.76 | 0.11 | 9.69 W (107 %), holds | 6.66 W (73 %) | holds, no limit | 399 s | 76 |

The same arithmetic at **70 °C, the record's conservative case** (the wall board is not in that air). Steady power and time are for the same cells; "holds" means it is under the ceiling at full power for ever.

| L (mm) | h | Steady total power at 125 °C | at 100 °C | Time at full power to 125 °C | to 100 °C | T_j at 2 min (°C) |
|---|---|---|---|---|---|---|
| 40 | 10 | 4.60 W (51 %) | 2.51 W (28 %) | 105 s | 36 s | 129 |
| 40 | 5 | 3.29 W (36 %) | 1.79 W (20 %) | 95 s | 35 s | 134 |
| 50 | 10 | 5.24 W (58 %) | 2.86 W (31 %) | 139 s | 46 s | 121 |
| 50 | 5 | 3.75 W (41 %) | 2.04 W (22 %) | 122 s | 44 s | 124 |
| 60 | 10 | 5.85 W (64 %) | 3.19 W (35 %) | 178 s | 56 s | 115 |
| 60 | 5 | 4.20 W (46 %) | 2.29 W (25 %) | 152 s | 53 s | 118 |
| **80** | 10 | 7.01 W (77 %) | 3.82 W (42 %) | 281 s | 77 s | 107 |
| **80** | 5 | 5.06 W (56 %) | 2.76 W (30 %) | 218 s | 73 s | 109 |
| 100 | 10 | 8.09 W (89 %) | 4.41 W (49 %) | 455 s | 101 s | 103 |
| 100 | 5 | 5.88 W (65 %) | 3.21 W (35 %) | 298 s | 93 s | 104 |
| 120 | 10 | 9.10 W (100 %), holds | 4.96 W (55 %) | holds, no limit | 126 s | 99 |
| 120 | 5 | 6.66 W (73 %) | 3.63 W (40 %) | 399 s | 115 s | 101 |

The other choice of height, **35.0 mm** (the leg's top at 40.0 mm above the component face; the cut is 2 800.0 mm² at 80 mm; the leg's heat capacity is taken at its height of 40 mm, 38.9 J/K at 80 mm), at the same 80 mm, at 45 °C:

| L (mm) | Cut (mm²) | h | R_wall (K/W) | Leg terms (K/W) | Steady total power at 125 °C | at 100 °C | Time at full power to 125 °C | to 100 °C | T_j at 2 min (°C) |
|---|---|---|---|---|---|---|---|---|---|
| **80** | **2 800.0** | 10 | 5.92 | 0.14 | 10.74 W (118 %), holds | 7.38 W (81 %) | holds, no limit | 346 s | 80 |
| **80** | **2 800.0** | 5 | 8.80 | 0.14 | 7.74 W (85 %) | 5.32 W (59 %) | 614 s | 256 s | 81 |

and at 70 °C, the conservative case:

| L (mm) | h | Steady total power at 125 °C | at 100 °C | Time at full power to 125 °C | to 100 °C | T_j at 2 min (°C) |
|---|---|---|---|---|---|---|
| **80** | 10 | 7.38 W (81 %) | 4.03 W (44 %) | 346 s | 90 s | 105 |
| **80** | 5 | 5.32 W (59 %) | 2.90 W (32 %) | 256 s | 84 s | 106 |

The lengths that hold **continuous full power** (9.09 W on both triacs, the steady case) are the least L with T_j at or under the ceiling, at H = 30.0 mm: at 45 °C, **67 mm at h = 10 and 110 mm at h = 5 for 125 °C, and 120 mm and 189 mm for 100 °C**; at 70 °C, 120 mm and 189 mm for 125 °C, and 326 mm and 496 mm for 100 °C. At H = 35.0 mm the least lengths are 61 mm and 103 mm for 125 °C and 112 mm and 180 mm for 100 °C at 45 °C, and 112 mm and 180 mm for 125 °C and 311 mm and 479 mm for 100 °C at 70 °C. At H = 25.0 mm, the owner's own height, the least lengths are **74 mm at h = 10 and 117 mm at h = 5 for 125 °C, and 129 mm and 199 mm for 100 °C** at 45 °C, and 129 mm and 199 mm for 125 °C and 342 mm and 514 mm for 100 °C at 70 °C (the model's answer to the owner's question at the owner's own height; the drawn window stays 30.0 mm tall, the low end of the owner's later estimate of 30 to 35 mm, and a 25.0 mm window at 80 mm would be 2000.0 mm²). The owner's 2-minute expectation (120 s) is inside every cell of the 45 °C table for the 125 °C ceiling (the least is 172 s), and for the 100 °C ceiling from 50 mm up (122 s at the least); at 70 °C, the conservative case, it is inside the 125 °C ceiling from 50 mm up (122 s at the least) and outside the 100 °C ceiling at every length shown but 120 mm (126 s at h = 10; 115 s at h = 5).

**Verdict at the provisional size, 80.0 × 30.0 mm.** The records' worst-case operating point for the heater switches is **continuous full power on both triacs**, the stuck-on or unbounded case, which the interlock and the element cutoffs bound; the owner's 2-minute expectation is not enforced by anything, so that is the point judged. **At 80 × 30 mm and 45 °C, continuous full power on both triacs holds against the maker's 125 °C ceiling at the favourable air coefficient only, and does not hold at the poor coefficient or against the stated 100 °C.** The steady hotter junction is 116.4 °C at h = 10 (10.19 W permitted of the 9.09 W) and 143.8 °C at h = 5 (7.36 W permitted), against 125 °C, so it holds at h = 10 and fails at h = 5 by 18.8 K; against the stated 100 °C it fails at both, by 16.4 K and 43.8 K (7.01 W and 5.06 W permitted). At 70 °C, the conservative case, it holds at neither: the steady junction is 141.4 °C at h = 10 and 168.8 °C at h = 5, and 7.01 W and 5.06 W are permitted against 125 °C. The least length that holds continuous full power at 45 °C is **67 mm at h = 10** against 125 °C, and 110 mm at h = 5; 120 mm and 189 mm against 100 °C. At the 35.0 mm height and 80 mm it is the same in kind (the steady junction is 112.7 °C at h = 10 and 138.9 °C at h = 5 at 45 °C; 10.74 W and 7.74 W are permitted against 125 °C): it holds at h = 10 against 125 °C and at neither coefficient against 100 °C. Short of continuous full power the assembly holds the duty shown in the tables (at 80 × 30 mm and 45 °C, full duty at h = 10 and 81 % at h = 5 against 125 °C, and 77 % and 56 % against 100 °C), and it holds full power on both for the time shown: without limit against 125 °C at h = 10, 491 s at h = 5, and against 100 °C 281 s at h = 10 and 218 s at h = 5. **The maximum dual full-power time is carried as an output limit for the control work and bring-up** (`DEL-HW-BRING-UP.C13`): 491 s against the maker's ceiling and 218 s against the stated one, at 80 × 30 mm and 45 °C, the least of the two coefficients (218 s and 73 s at 70 °C, the conservative case); it is a limit the control would have to hold if the continuous case were not otherwise bounded, **not one this record imposes**. These are bounds on a model whose inputs are stated and not measured, not predictions. **The highest ambient at which each verdict holds**, at 80 × 30 mm, from the same model (T_a = T_ceiling − P × (R_path + 1.385) for continuous full power, 9.09 W on both triacs, R_path = 6.47 K/W at h = 10 and 9.49 K/W at h = 5): continuous full power holds up to **53.6 °C of air at h = 10 and 26.2 °C at h = 5 against the maker's 125 °C**, and up to **28.6 °C at h = 10 and 1.2 °C at h = 5 against the stated 100 °C**; so the owner's 45 °C working figure is under the first of these only, and the 70 °C conservative case is over all four. The 2-minute full-power run (120 s from the ambient, both triacs at 9.09 W, the junction at T_a + P × R_path × (1 − e^(−120/τ)) + 12.6 K, τ = 220 s at h = 10 and 323 s at h = 5) stays under the ceiling up to **87.7 °C of air at h = 10 and 85.6 °C at h = 5 against 125 °C**, and up to **62.7 °C and 60.6 °C against 100 °C**, which is over the 45 °C working figure for both ceilings and over the 70 °C conservative case for the 125 °C ceiling only. These are bounds on the model, with every input stated or unmeasured, not predictions, and not a measured ambient; the table below carries them.

| At 80 × 30 mm, highest air temperature | 125 °C ceiling | 100 °C ceiling |
|---|---|---|
| Continuous full power, h = 10 (h = 5) | 53.6 °C (26.2 °C) | 28.6 °C (1.2 °C) |
| 2-minute full-power run from the ambient, h = 10 (h = 5) | 87.7 °C (85.6 °C) | 62.7 °C (60.6 °C) |

**The window size is a provisional drawn default** (§ *The wall cut, and the owner's acceptance*): the owner's measured maximum spreader replaces it, and every row of the tables above follows by the arithmetic shown.

**The opto-triacs and the board's parts.** The opto-triacs (rated to 85 °C, P4) lie 20.0 mm from the triac bodies; they and the board's parts are judged against the wall assembly's ambient, the 45 °C working figure, where the 85 °C rating is 40 K over the air, and also against 70 °C, the record's conservative case, where it is 15 K; the varistors' 105 °C (P18) are 60 K and 35 K over. The bracket's inner face is hotter than the air: in the lumped model the leg stands at T_a + 9.09 × R_path × (1 − e^(−t/τ)), 70 °C after 2 minutes at 80 × 30 mm and h = 10 (72 °C at h = 5) from 45 °C, and 104 °C and 131 °C at the continuous steady state, so the air between the leg and the opto-triacs, which this record does not compute, is not shown to stay under 85 °C at continuous full power. Bring-up reads the opto-triacs' body temperature with both heaters at full power.

**The heat the assembly passes into the enclosure.** Up to the whole 9.09 W of the pair (12 W for the bought relays the triacs replace, forms record) could reach the enclosure's air through the wall; that is a bound and not an estimate, since the share is unmeasured, and the enclosure's own thermal resistance is unmeasured, so no rise is computed. The enclosure figure excludes it (constraints record, *Premises*), so the heat adds to the parts' derating on the main board; bring-up measures the air with the heaters running.

**Conditional on what the owner has not measured.** Every verdict above rests on: the 45 °C working figure itself (bring-up measures the air at the wall board); the steel's grade and conductivity; whether the outer face is open to room air; whether a thermoblock's bond warms the steel near where the spreader goes (the owner's statement of 2026-10-23 says the heat plate bonds to this metal wall); the real gap between the steel and the plastic (about 10 mm by the owner's estimate); and the paste film; and the model's own simplification of the leg's lateral spreading. The leg is treated as isothermal over its face with only through-thickness conduction (0.17 K/W with the paste film at 80 × 30 mm), so the constriction of the heat from two tab faces of about 10 mm each way into the 5 mm leg is not counted. An estimate, not a derivation: with no sideways spreading at all, all the heat crossing only the two tab areas (2 × 10 × 10 = 200 mm²) at an aluminium conductivity of about 150 W/(m·K) (a typical figure, stated and not read from a document) is 0.005 / (150 × 200 × 10⁻⁶) = 0.17 K/W, against the model's 0.14 K/W for the leg's conduction, so at most about 0.03 K/W more, or 0.03 × 9.09 = 0.3 K of the 8.6 K (0.95 K/W) of junction margin the verdict at h = 10 against 125 °C has (116.4 °C against 125 °C), about 3 %. The model's own 15 W/(m·K) is a floor taken from the stainless steel and is far below aluminium's, which is why the isothermal leg is the reasonable reading; at 15 W/(m·K) with no spreading the same 200 mm² would be 1.67 K/W and would consume the margin, which is not the reading for aluminium. None is assumed closed.

**The bracket.** The bracket is the one drawn in § *The bracket*: two legs in one 5.0 mm strip, the board leg 87.0 mm long and the standing leg, the heat spreader, 80.0 mm long (provisional) and 30.0 mm tall, an aluminium plate (the owner's stated material) the owner cuts or buys, not in the catalogue and not priced (A22). *The tab hole's height on the standing leg is 17.25 mm above the board's component face*, from the package drawing (P3, Figure 13 and Table 6: A, the tab top to the plastic's lower face, 15.20 to 15.90 mm; L, the tab top to the hole's centre, 2.65 to 2.95 mm; a2, the lead length below the plastic, 13.0 to 14.0 mm; a1, the wider lead part, 3.75 mm typical; I, the hole 3.73 to 3.88 mm across) and the board's fixing (1.6 mm board, the leads straight through it). Two limits fix it. The plastic's lower face stands at z = h + L − A over the component face for a hole height h: at least h − 13.25 mm. It must clear the wider lead part, 3.75 mm, with 0.25 mm over: h − 13.25 ≥ 4.0, so **h ≥ 17.25 mm**. The leads must reach through the board: the highest lead end is at h − 12.25 − 13.0, which must be at or under −1.6 mm, so **h ≤ 23.65 mm**. The lowest height keeps the cut least: h = 17.25 mm. Then the plastic's lower face stands 4.0 to 5.0 mm above the board, the tab tops stand 19.9 to 20.2 mm, so the standing leg rises to **35.0 mm**, 14.8 mm over the highest tab top, which makes its outer face 30.0 mm tall from the lift of 5.0 mm (the low end of the owner's estimated 30 to 35 mm), and the lead ends stand 6.4 to 8.4 mm behind the back face (the leads are not cut, and the owner may trim them after soldering; that is not required). The hole through the leg is tapped M3 in the 5 mm strip, at u = 16.2 and 40.8 mm, the sheet's recommended torque 0.55 N·m. *Spacers:* two plastic standoffs at the ears' mounts, 5.0 mm long at the least (the lift is drawn at 5.0 mm, 0.9 mm over the 4.1 mm creepage distance to the nearest copper, so a spacer shorter than 4.1 mm fails the script's check), with plastic M3 screws, reached from the back face. *Interfaces:* the compound of P17 between each tab face and the leg, and the thermal paste between the bracket's outer face and the steel, which the owner screws it to (owner statement, 2026-10-28). *Making or sourcing the physical bracket is out of scope.*

**The element harness.** The three element conductors (the steam and coffee wires and the return) are routed by the owner where needed, which the owner said will be from the cavity next door the other direction or from above (owner statement, 2026-10-28); they terminate on the wall board's blade terminals; their reach and routing are the owner's measurement and are unmeasured. They do not pass the wall cut, which is the window alone. Each lead keeps its female push-on (nothing cut, lengthened or re-terminated, `DEC-DEVICE-RETENTION-BOUNDARY`):

| Lead | Termination | Rating | Reach |
|---|---|---|---|
| Steam element lead (`STMHEATER`) and coffee element lead (`COFHEATER`), retained | Its own female 6.3 mm push-on onto one blade of an in-line insulated male-to-male joiner | Absent (the lead's terminal is the original's; no maker's document) | Unmeasured; the owner measures it with a rule |
| The two in-line joiners | Male-to-male 6.3 × 0.8 mm insulated blades, strapped or clipped where the owner places them | **Absent**: no maker's document read | Placed by the owner; at the lead's end if the lead falls short |
| The wires to `OUT_S` and `OUT_C` | A wire of at least 1.5 mm² (A10) with a female push-on at each end | **Absent**: no maker's document read for the wire's terminals | The lead's shortfall plus the run to the pad, unmeasured |
| The return wire, `RET` to the main board's landing `WB_RET` | The same wire and terminals | **Absent** | Unmeasured |
| The wall board's three blades `OUT_S`, `OUT_C`, `RET` (C20626104, 6.3 × 0.8 mm, the drawing of P15 read on 2026-10-26) | Board-mounted blade, soldered | **Absent**: the drawing gives its dimensions, no current | On the board |

The three conductors do not pass the wall cut. The steady 5.38 A is 0.36 of the carried 15 A. **No blade terminal's or joiner's current rating was found in a maker's document**: the maker's site refused the automated fetch and the catalogue pages link none, so every rating above is absent. This is an open condition on those parts, and not a requirement this record asserts: the drawn harness is carried at 15 A, each unsourced rating is open, and a part is not ordered or fitted on this record until its rating is sourced from the maker's current document at 15 A or more at 70 °C, or the owner accepts the part. The criteria that require the terminals' ratings with their source and every part within its derated rating stay open against these parts. A search summary of one maker's miniature 250 receptacle gave 7 A continuous and 14 A intermittent; it is not a document read here and is not counted, and if it is right the miniature part is below the carried 15 A and the part must change.

**The surge clamps.** The two wall varistors **are kept**. Dropping them leaves the entry varistor, the 14D471K, as the only clamp, and the surge rating relied on would be the entry varistor's, read in `controller-board-design-constraints.md` § Mains entry: fuse, surge clamp and suppression judged: **775 V at 50 A, 4 500 A withstanding surge, 148 J, 300 VAC**. That clamp, 775 V, is 775 / 600 = 1.29 times the triac's 600 V and over its 700 V non-repetitive figure (P3), so the heater branch is not brought under what the triac blocks and the opto-triac's 800 V does not govern (the triac's 600 V does); the wall varistors, 775 V at 10 A, do not bring it under 600 V either. They are kept as a second clamp at the triac, in parallel with the entry varistor and without the trunk, fuse and relay between them. A transient over 600 V (the sheet's non-repetitive 700 V is for 10 ms) usually fires the off triac early for at most the rest of the half-cycle, 13.6 J into the steam element, a nuisance; through the 47.0 Ω element 775 V is about 16 A against the triac's 160 A; damage by breakdown or by dI/dt is not rated on any sheet read, and the opto-triac's 1 A is a single-cycle rating against 775 V / 360 Ω = 2.15 A for microseconds, also not rated. The branch is not judged inside the makers' ratings with or without the varistors (absent: the triac's and opto-triac's microsecond withstand); a triac that fails short is the interlock's and the cutoffs' case. The kept part's own rating (P18, 07D471K): **300 VAC against the 253 V span top, 1.19 times; V1mA 423 to 517 V against the 358 V peak, 1.18 times; clamp 775 V at 10 A; surge 1 200 A (8/20 µs); 29 J (10/1000 µs); 0.25 W; −40 to +105 °C**. For a 2.5 kV surge (the basis's overvoltage category II) the current is (2 500 − 775) / Z; the source impedance is not read here (the constraints record leaves it open), so the part is met for Z of at least 1 725 / 1 200 = 1.44 Ω, and at 2 Ω, a figure not read, the current is 863 A at most, taking 775 V; the real clamp at that current is higher and not read, so the voltage on the branch is above 775 V (open) and the margin is at least 1.39 under 1 200 A. The clamp at currents under 10 A is on the sheet's curve and not in the text read, and neither the triac nor the opto-triac has a microsecond rating on its sheet, so the 775 V figure is the sheet's and the clamp at the surge current is open: the act is to ask the maker. Buying and fitting are out of scope.

**The wall cut: the reason for the larger cut.** The cut is **2400.0 mm² in one place** (30.0 × 80.0 mm, both provisional) against the 410 mm² in three places the owner accepted before the bracket. The reasons: (1) the bracket's whole standing leg lies on the metal and is the heat spreader (owner statement, 2026-10-28), so the two 165 mm² windows under the tab faces become one window as long as the leg; and (2) the leg's face is 30.0 mm tall, the low end of the owner's estimated 30 to 35 mm, which clears the tab holes, 17.25 mm above the board, the least that keeps the lead shoulders clear of the board (§ *The bracket*). There is no third part: this record earlier assumed a 14.5 × 5.5 mm passage of 79.8 mm² for the three conductors (1428.2 mm² in two places), and that was an assumption of this record, not an owner statement; the owner said on 2026-10-28 that the wires will go from the cavity next door the other direction or from above and that the owner will route them where needed, which this record reads as no passage, and the passage is withdrawn. **The opening in the plastic that admits the unit is 89.0 × 45.0 mm = 4005.0 mm²** (u −16.0 to 73.0 by z −10.0 to 35.0 about the component face; § *The wall cut, and the owner's acceptance*), larger than the window because the whole unit, board edge-on, passes the plastic and not the leg's face alone; the owner's 80 × 30 to 35 mm is the spreader and is not shown to be that opening. An earlier reading of the package drawing took the dimension A as the tab top to the lead end and gave a leg of 15.9 mm and a cut of 1028.1 mm² (with a passage); the drawing shows A to be the tab top to the plastic's lower face, and the figure is corrected. A window of 87.0 × 15.5 mm = 1348.5 mm² followed, with the standing leg as long as the board leg; the owner's redesign of 2026-10-28 (the bracket is the spreader, 25 mm tall, a length to be told) replaced it. **Owner statements, 2026-10-28** (grade: owner statement, recorded as said and no more): (a) the owner asked why the wires need to touch the wall and said they will be going from the cavity next door the other direction or from above, "I'll just route them where needed"; (b) the owner asked whether the triacs are through hole soldered to the board and not extended on wires, an assumption put as a question; (c) the size of the wall cut "doesn't really matter right now", the wall board being the easiest board to reconfigure to another dimension like wider and shorter, and later "Probably not that big, but I'm not convinced it needs to be that big", the owner wanting a preliminary design of the whole board now with the dimensions rearranged later if need be; no acceptance is given in this statement; (d) offered the option 'Accept the cut as preliminary: you would say something like "accepted as preliminary, to be revisited when I cut"', the owner replied "Do 1", which chose it, so the owner accepted the cut as preliminary, to be revisited when the owner cuts and measures. **This record's reading of them, not the owner's words:** no conductor need cross the machine's wall, so no passage is drawn; the triacs are through-hole soldered, their leads straight into the pads; the board stands perpendicular to the wall, with the heat spreader (the bracket's standing leg) parallel to it and the triac tab faces bolted to it. **The owner accepted the cut as preliminary on 2026-10-28** (§ *The wall cut, and the owner's acceptance*, D11): the figures above are provisional and are replaced by the owner's measurements, and the board's dimensions are rearranged then.

**The outline.** The outline is this record's input and the owner may change it once the layout can be seen. If so, this record is amended first, and the bracket's length, the window and the cut figure follow; a change made after this judgement closes is re-derived by the schematic and layout task, with the owner's acceptance renewed for the figure then current, and a rework of a closed figure of this section is a child of the maintenance lane.

**Owner measurements.** Each is the owner's to take, with what it settles, and none is assumed: the maximum spreader length the owner will build to (it replaces the provisional 80.0 × 30.0 mm and the cut figure, D11); the element conductors' routing, from the cavity next door or from above, and their reach to the joiners and to the board's blade terminals (the joiners' place and any lengthened wire); the plastic wall's depth in front of the metal and the real gap between it and the steel, about 10 mm by the owner's estimate (whether the unit's reach and the cut leave room, and the window's real size), and whether the plastic can be cut to the unit's envelope, 89.0 × 45.0 mm = 4005.0 mm² (the owner's open measurement and decision, D11); the cavity fit (the unit's 36.6 mm height from its back face to the top of the leg plus 6.4 to 8.4 mm of lead ends behind the board, its 87.0 mm along the wall, and its 42.5 mm along the wall's normal against the owner's estimate of about 80 mm); the steel's grade and conductivity, whether its outer face is open to room air, and whether a thermoblock's bond warms it near the spreader (each of the heat verdicts rests on them); and the earth bond to the wall (D15). The air at the wall board and h are measured at bring-up (`DEL-HW-BRING-UP.C13`).

## Every retained harness reaches its connector

A retained harness lands on a connector placed where it enters the cavity and reaches it as found. **A low-voltage harness reaches** when its connector lies within that harness's recorded reach of the cut-away, and where no reach is recorded for it within the bundle's recorded minimum. The reach is measured as a straight line from the cut-away's centre, (133.5, 103.5), to the connector's **farthest corner** (the opening is 33 mm wide, so the distance to its nearest point is also given), and is held to the recorded reach less its ±5 mm. A straight line is a lower bound of a wire's length; the machine record holds no slack for the low-voltage side. The script checks every harness the connector record lists against a connector of the data block.

| Harness | Connector as found; as read | This record's connector: board, footprint, first pin | First pin and orientation as found | Reach (recorded → limit held), farthest corner, nearest point of the opening |
|---|---|---|---|---|
| Operator panel | `CON2`, 9 ways, 1.96 mm ±0.1, 0.5 mm pins; JST PH family *inferred* (header `B9B-PH-K`, housing `PHR-9`) | Main board, `CON2`: X 124.5 to 131.5, Y 76.0 to 96.5; row along Y at X = 128.0; **pin 1 at (128.0, 78.25)**, pin 9 at (128.0, 94.25) | Pin 1 nearest the bottom edge of the board (inspected) | No per-harness reach: bundle minimum 40 → **35**; **28.9** mm; 2.0 mm |
| Gauge assembly | `SP2`, 9 ways, same type, fitted rotated 180° from `CON2` | `SP2`: X 124.5 to 131.5, Y 98.0 to 118.5; **pin 1 at (128.0, 116.25)**, pin 9 at (128.0, 100.25) | Pin 1 nearest the top edge (inspected) | 40 → **35**; **17.5**; 2.0 |
| Knob microswitches, hot water `S7` and steam `S8` | One four-way, 1.95 mm ±0.1, 0.5 mm pins; family not identified | `KNOB`: X 113.6 to 124.0, Y 108.0 to 115.0; row along X at Y = 111.5; **pin 1 at (121.73, 111.5)**, pin 4 at (115.88, 111.5) | Pin 1 nearest the right edge, the hot-water switch's red lead (inspected) | The shortest wire, 40, is these two: 40 → **35**; **23.0**; 9.5 |
| Flow meter | `CZ1`, 3 ways, 2.54 mm, 0.63 mm pins; family not identified | `FLOW`: X 113.9 to 124.0, Y 98.0 to 105.5; row along X at Y = 101.75; **pin 1 at (116.41, 101.75)**, pin 3 at (121.49, 101.75) | Pin 1 the contact at the square pad, on the left; 5 V on pin 1, signal on pin 3 (inspected) | 40 → **35**; **20.4**; 9.5 |
| Coffee-block thermistor | `RT1`, 2 ways, 2.54 mm, 0.63 mm pins | `TEMP_C`: X 117.0 to 124.0, Y 86.0 to 93.5; row along Y at X = 120.5; **pin 1 (square pad) at (120.5, 88.48)**, pin 2 at (120.5, 91.02) | Pin 1 the square pad; either order works, a thermistor has no polarity (owner) | 40 → **35**; **24.1**; 9.5 |
| Steam-block thermistor | 2 ways, same | `TEMP_S`: X 117.0 to 124.0, Y 76.0 to 83.5; pin 1 at (120.5, 78.48), pin 2 at (120.5, 81.02) | As above | Longest wire, 65, is this sensor's: 65 → **60**; **32.1**; 10.1 |
| Steam-wand thermistor | 2 ways, same, fitted rotated 180° | `TEMP_W`: X 114.0 to 121.0, Y 119.0 to 126.5; **pin 1 at (117.5, 124.02)**, pin 2 at (117.5, 121.48) | Pin 1 at the opposite end from the other two | Longest wire, 65, is this sensor's: 65 → **60**; **30.2**; 12.5 |

Every connector reaches as found. Each header mates the **plug family, pitch and pin-1 orientation** the harness already has, so each plugs in without a new crimp: the pitch, way count and pin thickness above are the identification, and a test fit of the housing settles a family only inferred (`connector-pinouts.md`); the header part is the design task's. The row direction of `FLOW` and of the thermistor headers is not recorded. `KNOB`'s row lies along X because its pin 1 is described as nearest the right edge, and `CON2`'s and `SP2`'s along Y because theirs are nearest the bottom and the top; `FLOW`'s along X is a reading of "on the left side", and the thermistors' along Y is arbitrary, a thermistor having no polarity. **The owner confirms `FLOW`'s pin 1 with a meter at the first fitting**, since a reversed plug puts 5 V on the signal line. No low-voltage harness changes.

**The mains harness reaches as found when the board keeps each tab at its recorded position and height; a tab that moves is a harness change, named and justified.** All seven tabs the board keeps are at X = 8.5 mm, as found.

| Tab | Silkscreen, lead | As found, Y (mm) | This record, Y (mm) | Change | What it carries on this board |
|---|---|---|---|---|---|
| 1 | `LINE1`, red | 13.6 | **20.5** | **+6.9, named** (§ The fixing rule and the tabs that move) | Out to the loads: the link's output from `K_IL`'s second contact half, through the pour `LK_L1` that holds the pad |
| 2 | `LINE`, brown | 22.3 | **29.3** | **+7.0, named** | The mains in: the pad sits in the pour `LK_L`, on the net `LINE_IN`, which an inner layer joins to the entry fuse's line-side clip; the fuse's load-side clip feeds the link's input to `K_IL`'s first contact half and the taps to the module and the timing front end, upstream of the contact |
| 3 | `NEUTRAL`, blue | 30.6 | **38.1** | **+7.5, named**, to give tabs 1 and 2 their room | The neutral of the whole machine: the shunt reads its current; the pumps', the valves', the module's and the heaters' returns reach the pad through the pour and the shunt |
| 4 | `STMHEATER`, black | 52.9 | no tab | **Removed** (the owner, 2026-10-24); the lead is not changed | The steam element lead keeps its female terminal and plugs onto an in-line blade joiner; a wire runs from the joiner to `OUT_S` |
| 5 | `COFHEATER`, red | 66.2 | no tab | **Removed** (the owner, 2026-10-24); the lead is not changed | The coffee element lead keeps its female terminal and plugs onto an in-line blade joiner; a wire runs from the joiner to `OUT_C` |
| 6 | `COFVALVE`, brown | 79.1 | 79.1 | None | The two-way valve, switched by `K_V1`, whose contact copper a 35 mm lead reaches |
| 7 | `COFFPUMP`, white | 91.4 | 91.4 | None | The coffee pump, from `P_C` |
| 8 | `STEAMPUMP`, black | 101.2 | 101.2 | None | The steam pump, from `P_S` |
| 9 | `HOTVALVE`, blue | 111.4 | **109.5** | **-1.9, named** (§ The fixing rule and the tabs that move) | The three-way valve, switched by `K_V2`, whose contact copper a 37 mm lead reaches; the join is on an inner layer |

**The heater element leads no longer land on the board**: tabs 4 and 5 are removed (the owner, 2026-10-24) and each lead keeps its female terminal and plugs onto an in-line blade joiner placed by the owner (§ The path of the heater current, *The joiners*), so no lead is changed. The conductors from there to the wall board are routed by the owner (§ The heater wall assembly, judged, *The element harness*) and do not pass the wall cut. **No harness changes except the four named**: nothing is cut, lengthened or re-terminated. The return wire of the wall board ends on a landing of the main board, not on a retained lead. The graph's `SOL-HW-BOARD-DIVISION-AND-FLOORPLAN.C2`, `.C3` and `.C4` already say it so, all amended in place (item 26 of § Reported for the board design tasks lists what each carries). **Each valve and pump lead runs from its tab to its own block** (9 and 10 mm for the pumps, 35 and 37 mm for the valves, which cross the stack), and the script finds the shortest route a trace can take, on a grid of half a millimetre, that keeps the basic creepage (4.1 mm) from the copper of every other net, the signed 10.0 mm from every low-voltage block and pocket (and from the `LINE1` copper for `LINE`), the hole keep-out of each fixing and the board edge, and crosses no slot. **Every one of those distances is held with the trace's half width and a margin in addition** (A15: a trace of 0.30 mm at the maker's ±20 % width tolerance, half 0.18 mm, and half a grid cell, 0.25 mm, 0.43 mm in all), so a route that exists holds its distances with 0.43 mm to spare, and the route of the steam pump's lead, which held only by a margin under 0.25 mm before the half width was counted, holds with it. The clearance round each piece of copper is the straight distance, so a corner is cleared in a circle and not in a square, and where a slot lies between a point and the copper the straight clearance (1.5 mm from the copper of another net, 3.0 mm from a low-voltage block) is kept and the creepage is the path round the slot, which the pair rules of the record measure for the copper itself. A net whose pieces touch needs none. The traces themselves are the design task's.

| Net | Between | Shortest route |
|---|---|---|
| COFVALVE | the pad of tab 6 and the contact end of `K_V1` | 35 mm |
| HOTVALVE | the pad of tab 9 and the contact end of `K_V2` | inner layer, 36 mm (no surface route) |
| COFFPUMP | the pad of tab 7 and `P_C` | 9 mm |
| LINE_IN | the pad of tab 2 in the pour `LK_L` and the entry fuse's line-side clip `F_IL.i` | inner layer, 23 mm (no surface route) |
| STEAMPUMP | the pad of tab 8 and `P_S` | 10 mm |
| LINE and NEUTRAL | the first of the pieces of the pair (the pad of tab 3 with the shunt's first land) and, in turn, `K_IL.a` with the fuse's load-side clip `F_IL.o`, the pad of tab 3 and the shunt's first land, the neutral pour `LK_N`, the valves' neutral clip `VFUSE.n`, the timing strip's, the voltage measurement's and each of the module's two pads, and the varistor's neutral pad, all on `LINE` and `NEUTRAL` downstream of the entry fuse and upstream of the contact, the two nets taken as one group (the longest of the routes); the two pumps' `NEUTRAL` pieces are left out, for no surface route exists to them (§ The path of the heater current) | 49 mm |

The route of `LINE_IN` is on an inner layer because the pad of tab 2 is shut in by the copper of the other nets on the surface (the pad of tab 3 above, the `LINE1` pour below and the relay's contact half beside it) and the script finds no surface route to the fuse (A32). The route of `HOTVALVE` is on an inner layer because the hole at point 3 and the move of tab 9 leave no surface route (§ The fixing rule and the tabs that move), while `STEAMPUMP` has a surface route under the signed mains-to-mains figures; their lengths are the shortest route clear of every hole, slot and low-voltage block, with the copper of the other layers not modelled. The last row is the longest of the routes of that group: the supply for the module, the timing front end and the voltage measurement. It shows that a route for the set exists and that it keeps the signed pair from the `LINE1` copper; **it is not the routing of the taps**, from `F_IL.o` (net `LINE`) and from the neutral pour `LK_N`, which is the design task's, and **the two nets are routed as one group**: a `LINE` trace and a `NEUTRAL` trace side by side would need 5.0 mm between them, which the search does not keep (§ Reported for the board design tasks, item 11).

**Mains and low voltage are kept apart across the whole floorplan.** Every low-voltage block lies 10.0 mm or more from mains copper (10.3 mm the least); every barrier part's low-voltage pocket lies at least 3.0 mm from the mains copper of any block and 10.0 mm or more from it by surface path round the eight milled slots (12.9 mm the least), and no pocket is left to distance alone: 4 pairs stand nearer than 10.0 mm straight and each is held by a slot; low-voltage traces cross the barrier only at those parts; the mains harness enters on the left and the low-voltage on the right; and the two cables to the wall board leave on opposite sides of the cavity and meet only at the wall board, whose own low-voltage header lies 10.0 mm or more from its mains copper (10.0 mm) and whose pockets are slotted in the same way.

## The anticipated channel kinds

**The kinds** are every row of `component-specification.md` § Room for the channels the graph anticipates (the brew-path pressure transducer, current sensing, weight-based endpoint control, direct group-head instrumentation, the two in-stream temperature probes, the real-time clock), a further switched output such as another valve, further temperature and pressure inputs of the kinds already in use, a measurement of the supply voltage, of its frequency and of the total supply current (which control may use to detect a runaway or to calibrate the machine over temperature), and a spare analogue input. The mains zero crossing stays a single measurement on one board that every function shares, and has no place of its own here. **Three kinds are fixed by the owner, not by the arithmetic below:** kind 6 is removed by choice (2026-10-24); kind 1, the supply voltage, is required by `REQ-MEASUREMENT-001.C10` and is never removed; and kind 2, weight, is kept, with both load-cell channels, and is last in the removal order. **Every kind was given its place first**, at the block size of its row, in the region its kind belongs to: low-voltage circuits and headers on the right, mains-side parts at the barrier. The regions are the rectangles the blocks are drawn in. The header regions are **H_A** (X 85.0 to 105.0, Y 44.5 to 78.0) and **H_B** (X 105.0 to 131.5, Y 44.5 to 74.5), where a through-hole header can stand: no lead end lies over an intrusion, which puts a header at Y 44.5 or more there. The analogue circuit region is three rectangles, **AR_a** (X 76.5 to 117.0, Y 3.0 to 13.0), **AR_b** (X 78.0 to 117.0, Y 13.0 to 31.0) and **AR2** (X 117.0 to 123.2, Y 3.0 to 11.5), the part of the board 20 mm or more from the module's body and from the interlock relay's body, which is A8's rule for sensing circuits against the two heat sources, outside the reed's keep-out and the lid-screw circle of point 2. AR_b ends at Y 31.0, where the low-voltage blocks of other classes (`POL`, `BREW_D_C` and `IN_COND`) begin; the module's body less 20 mm would allow Y 33.4, and the earlier record kept Y 30.1, where the module stood before it moved up 3.3 mm for the voltage measurement (the script now computes the edge from the rules and fails if it differs). The earlier record sized four header strips (1 530.0 mm²) and an analogue region (1 113.8 mm²) by the blocks that happened to sit in them, and took them for limits; they were zones this record had drawn. They are redrawn here as the rectangles that the rules leave free, and a region holds a set of blocks when two things hold (A18). **The area**, the necessary condition: the blocks' areas, each grown by the spacing the drawing keeps (0.3 mm in the header regions and 0.4 mm in the analogue region, and no larger allowance), do not exceed the union of the region's rectangles grown the same way, **1 489.1 mm²** for headers and **1 189.7 mm²** for circuits. **For the headers, an arrangement**: the script searches every placement of the headers in the header regions, each header turned or not, each kept 0.3 mm from the next, and finds out whether one exists. No block of another class lies in a region now (`DRV_TIM` stands outside the analogue region). The binding rules are these, by assumption and not by the free area of the outline, which is 5 542 mm² and mostly on the mains side where a low-voltage block may not stand: the two heat sources' 20 mm for sensing circuits (A8); the header regions' lead-end rule over the intrusions; the reed's hand-access keep-out (A17); the lid-screw circles (A1); and the 10.0 mm that every low-voltage block keeps from mains copper. The kinds that may be removed go in the order of the second column of the table of kinds below, and the table of steps counts the demand after each removal, **stopping at the first step where both regions fit**, the headers by area and by an arrangement. **None is silently dropped**: every kind has a row. Removing a kind removes its block and its place on the board only; its pins stay free on the controller (`component-specification.md` § Where each function lands). **No place requires re-selecting a part already bought**: nothing is bought (`controller-board-design-constraints.md` § Purchases ahead of verification), and every place keeps the controller, the module, the relays and the triacs as the forms record proves them.

| Step | Header regions: demand (mm²) | Over capacity (mm²) | Analogue region: demand (mm²) | Over capacity (mm²) | What the step does |
|---|---|---|---|---|---|
| step 0 | 1650.9 | 161.8 | 1261.6 | 71.8 | Every kind has been given its place in turn and nothing is removed; the header area is over capacity, and the analogue region is over as well |
| step 1 | 1436.4 | 0.0 | 1174.2 | 0.0 | Kind 3 removed (two two-way thermistor headers, one four-way pressure header and one circuit): both areas fit, and no arrangement of the headers exists, because kind 4's two three-way headers cannot be placed |
| step 2 | 1274.2 | 0.0 | 1066.7 | 0.0 | Kind 4 removed (two three-way headers and two circuits): both areas fit and an arrangement of the headers exists and is drawn: **the removal stops here** |

The allocation therefore removes kinds 3 and 4 and keeps kind 5, the second current-sensing channel, and kind 2, weight, both load-cell channels of it. **Neither removed kind can be placed, alone or together, and what stops them is the headers.** The owner asked that every kind be given its place first and be removed only if it truly cannot fit, so each was tried at the spacing the drawing keeps, and not at the 1.5 mm gap the earlier record counted, which the drawing does not hold. The drawn kinds fill 1 274.2 mm² of the header regions' 1 489.1 and 1 066.7 mm² of the analogue region's 1 189.7. *Kind 3 alone* needs 214.5 of the 214.9 mm² the header regions have spare and 87.4 of the 123.1 the analogue region has, so it fits by area; *kind 4 alone* needs 162.2 of the 214.9 and 107.5 of the 123.1, so it fits by area; *both together* need 376.7 mm² of headers against 214.9 and 194.9 mm² of circuits against 123.1, which neither region holds (step 0). Area is the necessary condition only, and the headers are rectangles. The script searches every placement of the headers in the header regions: the drawn twelve have one (the drawing), **kind 3's three headers added to them leave 0.4 mm² of slack and no arrangement exists, and kind 4's two three-way headers added leave 52.6 mm² of slack and no arrangement exists either**, which is why step 1 does not stop the removal. **Of kinds 3, 4 and 5, one can be given its place and the other two cannot**: removing kinds 3 and 4 fits, removing kinds 3 and 5 fits, removing kinds 4 and 5 fits, removing only kind 3 does not fit, removing only kind 4 does not fit and removing only kind 5 does not fit, so which of the three keeps its place is the removal order's choice and the owner's to reorder (an owner decision pending, § Owner decisions pending, D12); the order below keeps kind 5, the second current channel, which senses a safety-relevant quantity, and gives up the further inputs and the group-head channels. What the drawing fixes is that the twelve headers stand in 6 columns of the two header regions, 0.3 mm apart; the search does not rest on it, since it places every header at every position and turn, and the columns are what the regions' width allows (the regions are 46.5 mm wide and seven headers side by side need 7 × 7.0 mm and six spacings, 50.8 mm). The rule they would weaken is **the fit**: the header regions are the rectangles that the lead-end rule over the intrusions, the 10.0 mm from mains copper, the reed's keep-out and the lid-screw circles leave free for a through-hole header. **Kind 5 fits.** The analogue region has 123.0 mm² spare after the drawn kinds; its top edge is Y 31.0, where `POL`, `BREW_D_C` and `IN_COND` begin, and not the Y 30.1 where the module stood before it moved up 3.3 mm. **If the voltage measurement leaves the gap under the module and the module drops 3.3 mm** (the third what-if of § Heat) **the edge returns to Y 30.1, 35.4 mm² of the capacity goes and 87.6 mm² stay: kind 5 stays.** The shown allocation is the result after kinds 3 and 4 are removed, kind 6 is not reserved by the owner's choice (2026-10-24) (row 6), and kind 1 is given a place whatever the arithmetic (row 1). The script derives the table above and the kinds' areas below from the data block, and fails if a removed kind has a block drawn, if a kept kind lacks one, if the allocation does not fit at the step it stops at, or if an arrangement of the headers is claimed that the search does not find. It prints the arrangement it finds, or that none exists, for each step and for each removed kind alone; the 12 headers stand in 6 columns of the two header regions.

| Kind | Removal order (first removed first) | Kind | Place | Where: block, header position, first pin | Interface: loading carried now → added | Block area (mm²) |
|---|---|---|---|---|---|---|
| 1 | Not in the order: required | Supply voltage measurement | **Given.** `REQ-MEASUREMENT-001.C10` requires the supply voltage that sets heater and pump delivery to be known to the control to a declared accuracy, and one measurement serves that and the control's cut-out above the span (a threshold above 253 V that the control design sets, 260 V for example, and not 250 V, which the grid can exceed). The accuracy is declared by the sensing task, with the other sensing figures, and not by this record; `DEL-SENSOR-NECESSITY-PROVEN.C2` computes how necessary it is. The isolating part is a **barrier the basis does not list** and is reported like the others (§ The interlock block; § Reported for the board design tasks, item 1), judged by the forms record's *Barrier parts* method: its test voltage against the 4.0 kV reinforced target, with no part chosen and no rating read. It stands directly below the module, 15.0 mm from the interlock relay's body, which the owner asks of an 85 °C part against a source of about 1 W (§ Heat); that raised the module 3.3 mm. Its isolating part also reads the supply current's shunt as a second channel (kind 9) | `VMEAS` (X 32.5 to 70.0, Y 48.4 to 53.4) in the stack at the zone boundary, on `LINE` and `NEUTRAL` upstream of the contact, and `VM_C` (X 116.0 to 122.7, Y 3.0 to 10.2) in the analogue region; no connector | **One conversion input**, PB1 (ADC12_INP5): with the nine pins already used (the four current channels' PC0, PC1, PC4 and PC5, and PA0, PA1, PA2, PA3 and PA6 of kinds 7, 8, 9, 5 and 12) and this one, 10 of the 16 conversion pins are used and 6 remain (PA4, PA5, PA7, PB0 and the analogue-only PC2_C and PC3_C); one isolated, conditioned signal reaches it from the pocket of `VMEAS`; it adds 5 mA to the 5 V rail (A28) | 236 |
| 2 | 4, last | Weight-based endpoint, two load-cell amplifiers | **Given.** Both channels, as the owner asked; the footprint is the HX711 sheet's SOP-16L amplifier and five passives, 137 mm² a channel, in place of the earlier 12 × 12 mm allowance of 144 mm² (A27) | `WT1_H` (X 100.8 to 107.8, Y 44.5 to 57.0) and `WT2_H` (Y 57.3 to 69.8), five ways at 2.0 mm (an assumption, A5), 7.0 × 12.5 mm, first pin at the lower end; circuits `WT1_C` (X 78.0 to 97.0) and `WT2_C` (X 97.5 to 116.5), Y 22.9 to 30.1 | Two digital pins each, data and clock: PC8, PC9, PC11, PC12, which `component-specification.md` already places (its weight row), so none is taken from the 26 digital pins that remain after the placed functions; no shared bus; each channel adds 14.3 mA of bridge excitation and 1.5 mA of amplifier to the 5 V rail | 449 |
| 3 | 1 | Further temperature and pressure inputs of the kinds in use | **Not given one.** The weakened criterion is **the fit**, bound by the header regions: alone, the kind needs 214.5 of the 214.9 mm² the header regions have spare and 87.4 of the 123.1 the analogue region has, which the areas allow, and **no arrangement of the headers exists** (§ above): its two two-way headers and its four-way one cannot be placed at the 0.3 mm spacing the drawing keeps | If given: two two-way thermistor headers, one four-way pressure header and one circuit | If given: two conversion inputs (PA4, PA5) and one on the second I²C bus of kind 12 | 280 |
| 4 | 2 | Direct group-head instrumentation, two channels | **Not given one.** The weakened criterion is **the fit**, bound by the header regions: alone, the kind needs 162.2 of the 214.9 mm² the header regions have spare and 107.5 of the 123.1 the analogue region has, which the areas allow, and **no arrangement of the headers exists** (§ above): its two three-way headers cannot be placed at the 0.3 mm spacing the drawing keeps | If given: two three-way headers and two circuits | If given: two conversion inputs (PA7, PB0) | 248 |
| 5 | 3 | A second current-sensing channel | **Given**: the allocation stops at step 2, before it (it is third in the order), and it fits with 123.0 mm² of the analogue region to spare (§ above) | `CURR2_H` (X 93.0 to 100.5, Y 54.9 to 65.0), three ways, first pin at the lower end, in the column of `CURR1_H`; circuit `CURR2_C` (X 111.0 to 117.0, Y 14.5 to 22.5) in the analogue region | A conversion input on PA3 (ADC12_INP15), and 10 mA on the 5 V rail (A28) | 124 |
| 6 | Not in the order: removed by the owner's choice | A further switched output, such as another valve | **Not reserved, by the owner's choice** (2026-10-24), and not for want of room: no criterion is named, because none is weakened. The relay place that was reserved for it (`K_SPARE`) had been lost for room when the interlock relay moved to the main board, and the owner has now removed the kind; its block, its tenth tab and its step of the removal order are gone | None | None | 0 |
| 7 | Not in the order: fixed | A spare analogue input | **Given** | `SPARE_AN2_H` (X 85.2 to 92.7, Y 57.4 to 70.0), four ways, first pin at the lower end; circuit `SPARE_AN2_C` | A conversion input on PA0 (ADC1_INP16), one of the 16 | 170 |
| 8 | Not in the order: fixed | Current sensing, first channel | **Given** | `CURR1_H` (X 93.0 to 100.5, Y 44.5 to 54.6), three ways, first pin at the lower end; circuit `CURR1_C` | A conversion input on PA2 (ADC12_INP14) | 124 |
| 9 | Not in the order: fixed | Total supply current measurement | **Given**, as a shunt in the neutral return and a second channel of `VMEAS`'s isolating part. The owner's placement, a 13 × 8 mm isolated sensor in the `LINE` to `LINE1` link beside the relay's contact end, is weighed and not drawn (below; § Options considered and dropped) | The shunt `I_SHUNT` (X 5.0 to 12.0, Y 38.8 to 45.8) between the pad of tab 3 and the neutral pour; `VMEAS` (X 32.5 to 70.0, Y 48.4 to 53.4) reads it; `I_C` (X 104.6 to 110.6, Y 14.5 to 22.5) in the analogue region conditions the isolated output | A conversion input on PA1 (ADC1_INP17) | 97 (49 + 48) |
| 10 | Not in the order: fixed | Real-time clock | **Given**, inside `MCU` | The 32.768 kHz crystal and its two load capacitors are counted in the `MCU` block's allowance (they are optional parts of P5 Table 9) | PC14 and PC15 (OSC32); no further pin | 0 beyond `MCU` |
| 11 | Not in the order: fixed (`DEC-IN-STREAM-PROBES-ANTICIPATED`) | In-stream temperature, two PT1000 probes | **Given** | `PT1_H` (X 115.9 to 123.4, Y 44.5 to 57.1) and `PT2_H` (X 115.9 to 123.4, Y 57.4 to 70.0), four ways each, first pin at the lower end; circuits `PT1_C` and `PT2_C` | SPI2 on PB13, PB14, PB15, chip selects PB12 and PD8; the bus carries none now and gains two converters, **24 µs for an exchange of three bytes at 1 MHz, 0.24 % of the 10 ms step each** (an assumed clock and size, `component-specification.md` § Where each function lands) | 469 |
| 12 | Not in the order: fixed | Brew-path pressure transducer | **Given**, digital and analogue | `BREW_D` (X 108.1 to 115.6, Y 44.5 to 57.1) with `BREW_D_C`, and `BREW_A` (X 108.1 to 115.6, Y 57.4 to 70.0) with `BREW_A_C`; four ways each, first pin at the lower end | A second I²C bus, I2C2 on PB10 and PB11, which also carry a UART: no device now, one transducer added, **0.65 ms of the 10 ms step at 100 kbit/s, 6.5 %, and 1.6 % at 400 kbit/s** for a seven-byte exchange (an assumed bound); and PA6 (ADC12_INP3) for the analogue fallback | 349 |
| — | Not removable | Supply frequency measurement | **Given, shared** | The timing front end `TIMING` and `IN_COND`: its output is read on both edges, so the supply's period is measured from it | PA10, capture on both edges (TIM1_CH3); adds nothing | 0 |

**Voltage, frequency and total current, where each goes.** Three measurements, three interfaces. *Frequency* is read from the one timing front end (`TIMING`, `IN_COND`), which is also the zero crossing: one shared measurement on one board, nothing added; its output is captured on both edges (PA10, TIM1_CH3) and the supply's period is the time between like edges. *Supply voltage* (row 1) is read by `VMEAS`, a series divider on `LINE` and `NEUTRAL` taken upstream of the contact so that the control still reads the supply with the interlock open, through the first channel of the isolating part, and conditioned by `VM_C`, 53.2 mm from the module and 58.9 mm from the interlock relay, to one conversion input (PB1). *Total supply current* is sensed by the shunt `I_SHUNT` in the neutral return at the pad of tab 3, where every load's return passes (the heaters' 10.18 A, the pumps' and valves' 0.78 A and the module's 0.05 A: 11.01 A with every load on, which is the link's 10.96 A and the module's current), and read as the second channel of `VMEAS`'s isolating part, the shunt standing at `NEUTRAL`'s potential, which the divider's input is also referred to; `I_C` conditions the isolated output to one conversion input (PA1). The interface is one isolated analogue pair per channel from one barrier part to two conversion inputs, PB1 and PA1, and the capture on PA10; the heater wall board carries none of the three. **Why not in the link, where the owner placed it.** The owner asked for one sensor in the `LINE` to `LINE1` link beside the relay's contact end, a 13 × 8 mm isolated part with 48 mm² of conditioning, and for the wall board's sensor to go. Under this record's own rules that part cannot stand there: (1) its primary is 8 mm long in the direction of the current and there are 5.0 mm between the pad of tab 2 and the relay's contact copper, so the relay moves 3.0 mm, and the sensing blocks nearest it then stand 17.3, 17.0, 17.0 from the relay against A8's 20 (`PT1_C`, `BREW_A_C`, `WT1_C`, in mm) while the analogue region loses 85.2 mm² of capacity (1 189.7 to 1 104.5; 56.8 mm² for a 2.0 mm move), computed here; (2) its low-voltage pocket, 3 mm beyond the primary, would stand in the pad column, where no pocket has an exit: the argument of § Heat applies, and every line from it to the low-voltage zone crosses the `LINE` and `NEUTRAL` taps; (3) a shunt in the link instead stands at `LINE`'s potential, 253 V from the divider's `NEUTRAL`, so one isolating part with two inputs that share a reference could not read both, and a second barrier part would need 5.0 mm of the boundary column that has none to give. The neutral carries the same current, a shunt there shares `VMEAS`'s reference, adds no barrier part and moves nothing. **The owner confirms this, or asks for the relay to move** (an owner decision pending, § Owner decisions pending, D3), which costs the 85.2 mm² above (kind 5 stays) and puts three sensing blocks under A8's 20 mm, and does not remove the pocket's missing exit. The conditioning `I_C` and the interface are the same either way. The allocation of the cable's conductors is the wall board's design task's.

The steam-path pressure transducer's own connector is **split from the spare input**, as the forms record sets: `STM_D` (digital, X 93.0 to 100.5, Y 65.3 to 77.9) and `SPARE_A` (analogue, X 85.2 to 92.7, Y 44.5 to 57.1) are two four-way headers, not one. The digital header's two signal lines sit on I²C and UART pins and its supply is 3V3; the analogue spare takes 5V, 3V3, GND and a filtered input so that a sensor rated for either supply is fed in its own specification; one connector shared between them would put 5 V on the digital pair's header, and the spare would no longer serve a second analogue sensor. **The removal order is a recommendation for the owner to reorder** (an owner decision pending, § Owner decisions pending, D12): its basis is that a kind a decision or a requirement already backs stays whatever the arithmetic (the PT1000 pair, `DEC-IN-STREAM-PROBES-ANTICIPATED`; the brew-path transducer, which a requirement asks to be measured; the supply voltage, which `REQ-MEASUREMENT-001.C10` requires); that a kind that senses a safety-relevant quantity (the heater current detects a runaway) stands above one that serves calibration or an endpoint; that the biggest and least decided blocks go first, except that the owner has put weight, both channels, last of all. The order is therefore the further inputs (3), the group-head channels (4), the second current channel (5), and weight (2); kind 1 is outside it because a requirement asks for it, and kind 6 because the owner removed it.

## What the owner fits by hand, and what the extended parts cost

**The decision, made on 2026-10-25 (D10).** The owner hand-solders the through-hole parts that drive the assembly cost, and the manufacturer assembles only the surface-mount parts (§ Owner intent carried in). This record's baseline is that decision: the main board's surface-mount parts are placed by the manufacturer, **5 unique Extended types** among them, and the 14 Extended types that are through-hole are bought apart from the manufacturer's order and fitted by the owner, one set for one machine. The manufacturer's order does not hold them, and no figure below charges for them.

Economic assembly is chosen over Standard: the main board meets its limits (layer count 4, thickness 1.6 mm, a single board of 131 × 125 mm, 0.5 mm lead pitch against 0.40, one side placed) and it is cheaper at this part count. Economic costs 8.18 + 1.53 USD fixed and 3.07 USD feeder loading for each unique Extended part. Standard costs 25.56 + 8.21 + 16.42 USD fixed (single-sided, two fixtures for one to 29 boards) and **1.53 USD feeder loading for each unique Basic, Preferred or Extended part**, not for the Extended parts alone (`docs/board-manufacturer-jlcpcb.md` § Parts library classes and their fees). At the 5 unique Extended types the manufacturer places and no Basic type, Economic is 25.06 USD and Standard 57.84 USD; each Basic or Preferred type adds 1.53 USD to Standard and nothing to Economic. The two cross at 26.3 unique Extended types if there are no Basic or Preferred types, and later for every one there is, so the conclusion holds at 5, and would hold at all 19: were every type placed by the manufacturer, Economic would be 68.04 USD and Standard 79.26 USD (computed from the charges above; `docs/board-manufacturer-jlcpcb.md` § Assembly limits and § Assembly charges).

| Part type, the proving candidates of the forms record | Class | Fee an order (USD) | Where |
|---|---|---|---|
| STM32H743VIT6, C114409 | Extended | 3.07 | Machine-placed |
| Logic-supply module IRM-20-5, C6280121 | Extended | 3.07 | Through-hole, fitted by the owner |
| Pump opto-triac MOC3052M, C8965 | Extended | 3.07 | DIP-6, through-hole, fitted by the owner |
| Pump triac BTA204S-600B, C256462 | Extended | 3.07 | Machine-placed |
| Interlock relay HF115F-Q/005-1H, 5 V coil; its catalogue number is not recorded, so it is priced and classed as the 12 V variant, C5318991 | Extended, **assumed** (as the 12 V variant) | 3.07 | Through-hole, fitted by the owner |
| Valve relay HF32FA-G/005-HSL1, C91370 | Extended | 3.07 | Through-hole, fitted by the owner |
| AC-input optocoupler LTV-814S, C108051 | Extended | 3.07 | Machine-placed |
| Mains-sense resistor of the supply-timing front end, 120 kΩ 2512, C5126146 | Extended (read 2026-10-25) | 3.07 | Machine-placed |
| Fuse holder 5 × 20 mm, C3131 | Extended | 3.07 | Through-hole, fitted by the owner |
| Fuse clip, C3130 | Extended | 3.07 | Through-hole, fitted by the owner |
| 6.3 mm tab, board-mounted, C20626104 | Extended (read 2026-10-26) | 3.07 | Through-hole, fitted by the owner |
| Shunt resistor of the neutral return, 2512, 1 mΩ class, not chosen | Extended (read 2026-10-25: no Basic or Preferred 2512 shunt in 241 rows) | 3.07 | Machine-placed |
| 7 header types for the harnesses and the anticipated channels, counted from the blocks by ways and pitch (4-way 1.95 mm, 5-way 2.0 mm, 9-way 2.0 mm, 2-way 2.54 mm, 3-way 2.54 mm, 4-way 2.54 mm, 10-way 2.54 mm) | Extended (read 2026-10-25; the 1.95 mm family has no catalogue entry, A13) | 7 × 3.07 | Through-hole, fitted by the owner |
| **19 types** | | **58.33** | |

The main board has nineteen unique Extended types, 5 placed by the manufacturer and 14 fitted by the owner, headers included. The 120 kΩ mains-sense resistor, an Extended part of the supply-timing front end (`TIMING`), is one of the five; the pump opto-triac, a DIP-6 through-hole part, is the owner's. **The manufacturer charges 5 × 3.07 = 15.35 USD of feeder loading**, 25.06 USD of assembly fixed charges and loading together (Economic assembly's 8.18 USD of setup and 1.53 USD of stencil with it), before the parts themselves and the machine-placed joints. The owner's 14 types would have cost 14 × 3.07 = 42.98 USD of feeder loading at the manufacturer, 21.49 USD of it, the 7 header types, which the catalogue lists as Extended (A13); the 19 types would have been 58.33 USD, 23 % of the 250 USD declared spend. **Hand-sourcing** a part type means the owner buys it elsewhere, leaves it off the order and solders it; it avoids the type's 3.07 USD and the manual joints the manufacturer would charge for it. It is practical only for the through-hole types; fitting an LQFP-100 at 0.5 mm, a DPAK or a four-pin SMD optocoupler by hand is not offered. The through-hole types are 14 (the module, the pump opto-triac, the two relay types, the two fuse parts, the tab and 7 headers): their 14 × 3.07 = 42.98 USD, plus the manual charges of the main board's 143 joints (A11: the module 4, the pump opto-triacs 12, the interlock relay 6, two valve relays 8, three holders 12, the seven tabs and the return landing 16, 85 header pins) at 0.0164 USD = 2.35 USD, plus the 3.58 USD hand-soldering labour: **48.91 USD saved** against the manufacturer fitting them as well. The shunt, which the machine places, adds an Extended type but no hand joint. The parts' own prices and their postage are priced in `controller-board-cost-estimate.md`.

**The tab that fits the harness.** The harness's female push-on terminals mate with the original board's nine tabs, each **6.36 mm ±0.1 wide and 0.81 mm thick** (`connector-pinouts.md` § The nine terminals, item `C0.tab`, measured with calipers, owner statement of 2026-10-20, the owner's 6.35 mm agreeing). The part the record first chose for the seven tabs and the return landing, C20626100 (BTC-3-PCB485005D), is titled **4.8 × 0.5 mm** in the manufacturer's catalogue, a short-leg solder-in blade 1.5 mm narrower and 0.31 mm thinner than the harness's; "6.3" appears only in the footprint library's name for it and in the blade-width attribute, which the catalogue gives as 6.3 mm for every part of the family, the 4.8 and 5.2 mm ones included. It does not match the blade the harness needs and is replaced. The replacement is **C20626104** (BTC-3-PCB634908T), whose maker's drawing gives a blade **6.3 ±0.2 mm wide and 0.8 mm thick (+0, −0.03)** for the 0.8 mm 250-series female terminal (P15): 6.3 mm against the harness's 6.36 mm, inside its ±0.1, and 0.8 mm against 0.81. It is a flat solder-in blade with a barbed leg and an anti-reverse positioning feature, Extended, 14 453 in stock, 0.0374 USD for one to 99 and 0.0295 USD from 100 (P16, read 2026-10-26), through-hole like the part it replaces. **Every figure that follows from the part is recomputed:** the part's class and the fee are unchanged (Extended, 3.07 USD, one type), the pad is the blade's section from the connector record and not the part's (A2), and the unit price moves from 0.0351 to 0.0374 USD, which `controller-board-cost-estimate.md` carries. What the drawing's views do not give as read here is the blade's height above the board (the recorded 9.9 mm) or its footprint's hole size, which stay the design task's (A2; § Reported for the board design tasks, item 6).

**What is hand-fitted in this record, and what it saves.**

| Part | Why the owner fits it | Saved against the manufacturer fitting it |
|---|---|---|
| Tank reed element, two joints | The owner's statement that the reed is fitted by hand at the recorded position and left off the order (`reference-machine.md`); it is not in the catalogue records read | Up to 3.10 USD: the 3.07 USD of an Extended part if it is one, and two joints at 0.0164 USD; the catalogue was not searched for it |
| The whole heater wall board | A small all-through-hole mains assembly whose triacs the owner bolts to the bracket in any case and which the owner solders by hand, so its size and part count are kept minimal (2026-10-24); hand-fitting is not forced, since the board may be made as a section sharing the main board's assembly | **29.28 USD**: five unique Extended types (the triac BTA16-600BRG C9100, the opto-triac MOC3083 C10797, the blade terminal C20626104 that the main board's table also lists, the three-way header, and the varistor 07D471K C49072860, all read as Extended on 2026-10-25) at 3.07 = 15.35 USD; its 39 joints (A11: triacs 6, opto-triacs 12, their gate networks 8, varistors 4, terminals 6, header 3) at 0.0164 = 0.64 USD; labour 3.58 USD; setup 8.18 USD and stencil 1.53 USD for an order of its own. The varistor is read as Extended (`controller-board-cost-estimate.md` § What the library class allows, 2026-10-25). **The reading moves no figure of the baseline**, because the wall board is entirely hand-fitted: its order carries no assembly and no feeder loading, so only this comparison with the manufacturer fitting it moves |

On the main board the manufacturer places the surface-mount parts only; the module, the pump opto-triacs, the relays, the fuse holders and clips, the tabs and the headers are the owner's, so the mains-barrier joints, the module's and the relays', are the owner's hand joints; the staged build keeps them last.

## Reported for the board design tasks

1. **Three barriers are not among the basis's seven.** The interlock relay's coil-to-contact barrier (the valve-switch kind of insulation at another place), the wall-to-mains-copper barrier and the voltage measurement's isolating part, which now takes the supply current's shunt as a second channel, are unlisted (§ The interlock block, *Barriers the signed basis does not list*, which judges the first and the third against the signed figures: neither is shown to reach the 10.0 mm creepage, and the owner re-declares the basis before either part is ordered); the valve relays' own barrier is the listed valve-switch kind, with another part. This record does not change the basis; the design task of the board that carries each reports it or raises the amendment with the owner. The wall board keeps its mains copper, its part bodies and its mains lead ends 5.0 mm from the wall edge, which stands flush with the outer face of the bracket's leg on the metal wall; the rule is the basis's basic creepage, 4.1 mm, applied to an earth bond that the basis says is not measured, and the drawn 5.0 mm keeps it with 0.9 mm in hand; the bracket, earthed through the wall, is held to the same 4.1 mm from mains copper in three dimensions and drawn 5.0 mm from it (A22).
2. **Parts' own spacing is under 10.0 mm, or unread.** The relays' creepage is "over 8 mm" (P2 and P6), the opto-triac's external creepage and clearance are 7 mm or more, 10 mm or more only in the 0.4-inch lead-spacing option (P4), and the voltage measurement's isolating part, the AMC131M02, states 8.0 mm creepage and clearance at least (§ The interlock block). The board's distances are held by slots and gaps; whether a part whose body gives less than the signed creepage forms the reinforced barrier is the fitted-part check's, together with the working isolation voltage no sheet gives.
3. **Mains-to-mains spacing is signed in the basis, and the shortfalls the parts force are listed there as unsigned exceptions.** This record holds the signed 1.5 mm straight and 4.1 mm by path between mains copper of different nets, every pair in the data, the seven tab pads, the return landing and the link pours included (A3), and the signed 3.0 mm and 10.0 mm across the open interlock contact; on the wall board the two ends of each varistor and the copper either side of each triac are held to it as any other pair, the unpopulated confirm places' copper included. **`TIMING` and `VMEAS` are held to it as two pieces of mains copper each**, with the series resistors and the optocoupler's input pins bridging the gap between them; those parts' own pad pitches are not modelled; the basis lists the shortfalls of the pump triacs (1.08 mm), the shunt (1.65 mm) and the 1206 series resistors (1.8 mm) as exceptions for the owner to accept, and no sheet is read for the 2512 resistors or for `VMEAS`'s isolating part, which the design task checks against the sheets of the parts it chooses. The mains-to-low-voltage shortfalls of the bought parts are listed there as further unsigned exceptions: U601, U701 and U711 (one pair of pads each) and the four pad pairs of U602, each at the board's own pad gap and not at a published figure (§ The four parts judged against the signed figures); K201, K731 and K741 have no entry, their short figures being inside the part.
4. **The fixing distance forces four tabs to move**, tabs 1 to 3 up 6.9, 7.0 and 7.5 mm and tab 9 down 1.9 mm, and leaves 3.1, 3.0, 2.5 and 8.1 mm of the owner's 10 mm slack (§ The fixing rule and the tabs that move). The footprint of each mounting hole is drawn inside E = 3.0 mm; a larger stock footprint is not used. The owner measures each of the four leads' slack with a rule before ordering and, if one is short, uses a push-on extender at the tab; the measurement is the owner's. **None of the four fixings can be touched, and the owner's choice between these moves and amending the rule for such fixings is an owner decision pending** (§ Owner decisions pending, D1; § The fixing rule and the tabs that move). The boss tops are read on the machine for all four points; no tenth tab is drawn. The lid boss's and screw's sizes are unread.
5. **The entry fuse holder and the varistor are drawn at tabs 2 and 3.** The machine keeps its fixed mains lead and the owner has decided that the 10 A fuse and a varistor sit on the main board at tabs 2 and 3 (§ The fuses); the fuse holder `F_IL` (24 × 9 mm) and the 14 mm varistor `RV_IL` are in the data and the drawing, and the net `LINE_IN` joins the pad of tab 2 to the fuse's line side on an inner layer (A32). The width of that run (as wide as the link, 5.72 mm for 15 A), its insulation from the surface copper above it, the signed distances on its layer, and the fuse's own resistance and heat are not shown here and are the main board design's to show. The 10 A holder, the owner's check of the original board's varistor and the placing of the suppression part are the main board design's: the entry needs an X2 capacitor, decided in `controller-board-design-constraints.md` § Mains entry: fuse, surge clamp and suppression judged, which also finds the fuse the cost record prices is fast-acting and the fuse clip rated 10 A against the 15 A overload band; no suppression part is drawn yet.
6. **The faston tabs, the joiners and the wall board's blade terminals** carry up to 15 A; their rating is absent, no maker's document having been found for any of them (§ The heater wall assembly, judged, *The element harness*); the bought board-mounted tab's blade height against the recorded 9.9 mm, the joiners' insulation, the element conductors' routing and reach to the joiners and the board (unmeasured, the owner's) and the choice between a blade and a solder pad for the return landing (§ The path of the heater current) stay open.
7. **The interlock's mechanism is chosen, and the ceiling is pending.** The mechanism is the two-channel drive of *The drive* in § The interlock block. Its removal interval is chosen, 100 ms, counted from the controller's last valid proof of life to the interlock's contact opening (`controller-board-design-constraints.md` § Proof-of-life removal interval); the ceiling it must sit under rests on a casting peak the control does not yet hold and is pending there. `POL`'s area is an estimate, 128 mm² of 19 parts against the 144 mm² drawn. **The coil's feed is for the main board's design to meet**, in the words of § The interlock block: the coil is fed only through the proof-of-life path, and no level, timer, charge store or latch keeps it above drop-out for longer than the removal interval after proof of life stops, in any rest state of the controller; bring-up stops the controller in each rest state and records the coil voltage below 0.5 V. There is no reduced-hold drive (§ Options considered and dropped).
8. **The tab blades are read: all nine stand with their wide face parallel to X** (the owner, 2026-10-24). The bought board-mounted tab's own footprint is not read, so the pad is the blade's section with an annulus (A2); the design task draws the footprint inside it, or enlarges the pad and re-runs the distances, which the script repeats from the data.
9. **The interlock relay's heat is budgeted, not sourced, and the relay is a heat source.** The contact heat is 0.5 W at 10.18 A with the coil at its full drive (A14), 0.98 W in all and 1.03 W with the coil at the low end of its tolerance; A8 applies to it against every part that derates and every sensing block, and the script tests it (§ Heat); bring-up measures the closed-contact drop at about 10 A (over 50 mV moves or changes the relay) and the body temperature. The sheet's VDE ratings for the variant, 18 A at 105 °C and 16 A at 125 °C of ambient, are the only sourced figures that fall with temperature (1.46 and 1.07 times the 10.96 A and the 15 A at 125 °C): the relay has no sourced thermal margin at the held coil drive. The 70 °C air the arithmetic uses is assumed; the owner thinks it will not be real.
10. **What opening the contact does to its life is unsourced.** The pumps' starting current and the contact's endurance under the pump motors and valve coils are in no record; bring-up opens the relay with them running and reads the closed-contact drop again.
11. **The taps from `LINE` and `NEUTRAL` to the module and the timing front end** are the design task's to route. The record shows a route from the first piece of the pair to each of the others, 49 mm the longest, that keeps 10.0 mm from the `LINE1` copper and 5.0 mm from every other net; **it takes `LINE` and `NEUTRAL` as one group**, so the 5.0 mm that a `LINE` trace and a `NEUTRAL` trace need between them is not kept, and a route for the two side by side is not shown; where each tap leaves the link and the neutral pour is the task's.
12. **The interlock relay's contact terminals** are drawn from the sheet's drawing (A23): two terminals 7.56 mm apart across the body, each on two holes 5.0 mm apart along it, so the two contact halves stand 3.0 mm apart over the slot; a valve relay's contact and coil ends are the sheet's two columns of holes, 15.24 mm apart (A26).
13. **The wall board's design task is handed** the bracket as drawn in § The heater wall assembly, judged, *The bracket* (the owner makes or sources the bracket, which is not in the catalogue and is not priced; the varistors' height, the depth of the plastic wall in front of the metal and the depth the bracket adds are unread, § The heater wall board, *The bracket*); the three-way cable's conductors (the LED supply and the two returns) and whether the cable stays ten conductors; the varistors as judged: the entry varistor's clamp is sourced (775 V at 50 A) and does not bring the branch under the triac's 600 V, the triac's and opto-triac's microsecond withstand is absent, so the branch is not judged inside the makers' ratings with or without the wall varistors, which are kept (§ The heater wall assembly, judged, *The surge clamps*; D7); and the wall-plus-interface resistance each triac needs, which is judged (item 30). If the confirm places are ever fitted, the tap of each from `RET` is routed above the slot's end, and the driver's way to the tab screws is then crossed by their parts.
14. **The headers' parts** are not read: the 9-way family is inferred, the others unidentified; a test fit settles them. The heights of the headers and fuse holders are not read.
15. **The forms record's bound on the snubber capacitor, about 22 nF, assumes a live-side switch** and falls away for this board's neutral-side switch (§ The heater wall board, *The mains-presence confirm*); no snubber is fitted.
16. **No path needs two-ounce copper now** (§ Copper that carries the heater current); its price at four layers at this outline stays unmeasured.
17. **No USB connector** is placed. The basis lists one among the touchable parts; none of the forms record's functions needs one.
18. **Assumptions A1 to A33** are for the project to replace as each fact is read. A1 and A2 set the tab moves; A6 and A7 set the pump strips' widths; A13 to A24 are the earlier rounds', of which A15 (the trace width) and A21 (the 85 °C class members) are this round's: the header class, the relay's contact heat, the sensor's loss, the reed keep-out, the fit bookkeeping, the screw and boss at point 3, the link budget, the bracket, the relay's contact terminals and the sheet resistance; A25 to A30 are the module's pads, the valve relay's copper and pocket, the weight circuit, the 5 V rail's loads, the voltage measurement's block and the module's power factor; A31 and A32 are the least distance between the heater triacs and the pumps' inner-layer join.
19. **The 85 °C parts nearest the module are not held.** `K_V1` stands on the module's body (0.0 mm), `VMEAS` directly below it (0.0 mm, and 15.0 mm from the relay) and `P_C` 12.5 mm above it, against A8's 15 mm; at most three of the five can hold and the drawn stack holds two; the arrangements that hold three each break a rule and none that meets every rule was found, which is unproved (§ Heat, computed). Bring-up measures the three bodies beside the running module against 85 °C; if `K_V1` fails, the HF115F-Q is its stated fallback and needs the column redrawn (§ Heat). **Owner decision pending (§ Owner decisions pending, D4):** the third what-if holds three (K_V2, P_C, P_S) at the price of the voltage measurement's distance from the relay (11.7 mm against the owner's 15) and 35.4 mm² of the analogue region, which keeps kind 5 (87.6 mm² remain); the drawn stack keeps the 15 mm and holds two.
20. **The voltage measurement's accuracy and cut-out belong to other tasks.** The accuracy is declared by the sensing task with the other sensing figures (`REQ-MEASUREMENT-001.C10`) and the refusal threshold above 253 V by the control design; neither is set here. The isolating part, its rating and the barrier report (item 1) are the main board's design task's, and `VMEAS`'s area is an estimate (A29). **The isolating part has two input channels that share the `NEUTRAL` reference** (the voltage divider and the shunt): the AMC131M02 is two such channels in one package (§ The interlock block, *Barriers the signed basis does not list*), so no barrier part of the shunt's own is needed and the placement of the current sensing does not reopen; its output is digital, which the floorplan's `VM_C` and `I_C` blocks do not yet reflect.
21. **The valve relays.** The 250 V maximum switching voltage is the owner's acceptance for relay contacts (§ The valve relays); the contact life under a valve coil is unsourced and left to bring-up; the contact terminals are read from the drawing (A26); and the mains leads of 35 and 37 mm are the design task's to route.
22. **Owner decisions pending** are listed once, in § Owner decisions pending, D1 to D16 (D10, D11, D14 and D16 are decided), and not here; one of them concerns the fuses (D5) and one the smaller IRM-10-5 (D6). No smaller approved fuse meeting the 6 kA was found.
23. **The 5 V rail's assumed loads** (A28) are replaced as the parts are chosen; the controller's share is its sheet figure through a linear regulator, and a switching regulator would take less of the rail.
24. **The microcontroller block has no allowance.** It is drawn at its 1 002 mm² estimate (1 005 mm²) because the board's top edge and the 15.0 mm it keeps from the module leave it 31.1 mm of height; if the part layout needs more, the module or the stack moves, not the heat rule.
25. **Kind 5, the second current-sensing channel, is given its place** (§ The anticipated channel kinds): it fits with 123.0 mm² of the analogue region spare at the spacing the drawing keeps; the region's top edge was corrected from Y 30.1 to Y 31.0, and if the module is lowered (the third what-if of § Heat) the edge returns to Y 30.1 and 87.6 mm² remain.
26. **The criteria this record was built against are all amended in place, and none departs from it** (version 2 of each). `SOL-HW-BOARD-DIVISION-AND-FLOORPLAN.C2` carries the joiner arrangement (each element lead keeps its female terminal and plugs onto an in-line blade joiner, and the current returns by a new wire to a neutral landing on the main board) and now says "a snubber, where one is fitted", which this record's wall board and pump drives satisfy by fitting none; `.C3` carries the joiner arrangement and the wall cut; `.C4` says the total *supply* current, which this record senses (10.96 A with every load on and 11.01 A in the neutral, kind 9, by the shunt in the neutral return), and lets a kind be recorded as not reserved by the owner's choice with its date, which kind 6 is. `DEL-SENSOR-NECESSITY-PROVEN.C2` carries the supply current in the same words, and `DEL-HW-BRING-UP.C4` requires the continuity check of item 32. **The existing records this solution edits** (`reference-machine.md`, `controller-board-design-constraints.md` and `controller-design/component-specification.md`) change only to carry the owner's measurements, statements and acceptances (the reed's position and the caliper readings, the original board's protection parts, the acceptance of a 250 V relay at the top of the span); none of them is a figure of this record's own.
27. **The heater triac is not a Snubberless™ part.** The BTA16-600BRG is the standard four-quadrant "B" type (P3, Table 9: marking BTA16-600B, IGT 50 mA, static dV/dt 400 V/µs at least); the forms record's and the brief's "snubberless" is the ...BW type (BTA16-600BWRG). The arithmetic of § The heater wall board shows the B type enough on a resistive load; the design task may choose the ...BW part of the same family and package if it wants the margin.
28. **The pump drives carry no snubber and no varistor, and the check against the EMC and surge criteria is not closed** from sourced figures (§ The pump drives): the margins on the commutating rate, 21 and 50 times, assume each pump's series diode, which is the owner's statement and not measured; the pump coil's inductance, the series diode's rating, the circuit's commutating dV/dt, the conducted emission and the surge withstand are the design task's, closed by analysis; each has the owner's act that settles it in `controller-board-design-constraints.md` § Pending marks.
29. **The round 5 owner decisions pending are in § Owner decisions pending, D1 to D4, D7 and D8:** the tab moves against amending the 10.0 mm rule (D1); whether the two confirms come back (D2); the current sensing's placement (D3); the voltage measurement's distance from the relay against a third held 85 °C part (D4; item 19); the two varistors (D7); and a blade or a solder pad for the return landing (D8).
30. **The two heater triacs share one metal wall** (§ The heater wall board, *Heat*): 4.25 W and 4.84 W, 14.2 mm apart body to body, against an assumed least of 10.0 mm (A31). The sheets allow the junction rise (8.9 K and 10.2 K) and the case limit (116.1 °C and 114.8 °C); they give no interface or wall resistance, so the wall-plus-interface resistance to the air that each triac needs is 9.3 K/W alone and 4.9 K/W with both on, at 70 °C air, the record's conservative case, at the maker's 125 °C ceiling; § The heater wall assembly, judged, *The heat* works it at 45 °C, the owner's working figure for the air at the wall board, and at 70 °C, against that ceiling and a stated lower one, with the bracket as the spreader and the 2.5 mm stainless wall as a fin, and states for each window length the steady power it holds and the time it holds both heaters at full power. At the provisional 80.0 × 30.0 mm it holds continuous full power at 45 °C against 125 °C at the favourable air coefficient and not at the poor one nor against the stated 100 °C (67 mm at the favourable coefficient and 110 mm at the poor one are the least lengths that hold it against 125 °C). Every verdict there is conditional on the steel's grade and conductivity, the air at the board, the outer face being open to room air, the gap between the steel and the plastic and the paste film, all unmeasured and the owner's.
31. **The pumps' returns, the net of tab 9 and the entry fuse's line side join on an inner layer** (A32; § The path of the heater current; § The fixing rule and the tabs that move): the script finds no surface route for `P_C.N` or `P_S.N`, and none for `HOTVALVE` from tab 9 to `K_V2` since the hole at point 3 and the move of tab 9 (`STEAMPUMP` from tab 8 to `P_S` has a surface route of 10 mm under the signed mains-to-mains figures), so each of those joins is an inner layer of the four-layer board, which the main board's design task shows, keeping the signed distances on that layer and from the point 3 hole; the script shows a route for the tab net clear of every hole, slot and low-voltage block, and not clear of the other copper of the layer. The valves' and the heaters' returns, and the module's, join by surface copper; the line side of the entry fuse is the fourth, `LINE_IN` (item 5).
32. **The interlock cuts every load only if every load's live lead is fed from `LINE1`, which is the owner's visual trace and not a measurement.** `connector-pinouts.md` grades the trace inspected and says the images do not show the links of terminals 4 to 9 (§ The source of each live feed); this record's claim that "no load has a live feed" with the contact open rests on it (§ The path of the heater current, *Why the contact is where it is*). **Open until bring-up, and not waived by any design task:** the continuity check that `DEL-HW-BRING-UP.C4` requires. With the relay open and the machine unplugged, by meter, from the supply live (`LINE`, the plug's L pin) to the live lead of each heater element, each pump and each valve coil, there is no continuity; any reading of continuity means a load has a live feed past the relay, and the interlock does not cut it. The same check is repeated after any change to the loom or the board that touches a live lead.
33. **The entry varistor's temperature class is not read, and the 85 °C rule is not applied to it.** The 14D471K's sheet is unread (A33), so whether it is an 85 °C part is unconfirmed. As drawn, `RV_IL` stands 5.3 mm from the module's body and 9.9 mm from the interlock relay's body, against A8's 15 mm if the part proves to be an 85 °C part. Whether to choose a part of a higher class or to place it differently is the main board design task's, as is the entry fuse holder's own temperature class (item 5).
34. **Two open items from the judged bought parts** (§ The four parts judged against the signed figures). The relays' part-internal creepage and absent clearances, and U602's unpublished creepage and clearance, are the owner's to accept, change or find a figure for. K201's contact pads 13 and 14 stand 5.06 mm apart across the open contact and are held at 10.0 mm creepage with no exception allowed, so the layout must slot between them or otherwise reach the figure.

## What this record's words depart from in the forms record

The forms record is not edited here. Where its words differ from this division, it is the reasons below that govern until the forms record is corrected.

| The forms record says | This record | Why |
|---|---|---|
| The wall board has faston tabs for the live feed and the element lead, and a cable to the controller board that carries low voltage only | The wall board has a blade terminal for each element's wire and one for the return; there are **two** cables, three mains conductors and a three-way low-voltage cable (the LED supply and two returns), which carries no coil drive and no sensor signal; the live feed is not on the wall board | The retained harness must not change: each element's other lead reaches a joiner and the `LINE1` daisy-chain reaches the fixed lead directly, so the switch is in the neutral-side path and the board as found switches that side |
| The interlock is on the controller board, in series with each heater's supply path | **Agreed in effect, and wider.** It is on the main board (the controller board of that record), in the one link from tab 2 to tab 1 through which every load's live lead is fed (`LINE1` by the retained daisy-chain wires), so it is in series with **each heater's supply path and with every pump's and valve's**, not with the two heaters' alone; a shorted triac, whose element has no live feed, is cut off with the rest | The owner's approval of 2026-10-24: the relay in the heaters' common return on the wall board cut the heaters only and needed its coil conductors in the cable; the forms record's own words, a series element in each heater's supply path, are met either way. The forms record is not edited here and its words stand until its owner corrects them |
| No place for the mains-presence confirm | **The drawn wall board has no confirm place.** A second layout, with the two places unpopulated, is checked by the script and is 23.5 % larger; the owner's condition for dropping the confirms is only partly met, which is an owner decision pending (§ Owner decisions pending, D2) | § The heater wall board, *The mains-presence confirm*; § Every function has one owner |
| The heater wall board's triacs "bolt to the machine's metal wall"; the spreader between triac and wall, the triacs' mounting and any insulating interface between tab and wall are the assembly task's (§ Parts off the boards) | The two triacs' tab faces are bolted to the standing leg of a right-angle bracket that is bolted to the metal wall and fixed to the board by two mounts; the bracket's standing leg is the spreader that the forms record left to the assembly task (owner statement, 2026-10-28), and the heat reaches the wall through it | The owner's intent of 2026-10-26: no lead bent or folded, and the board and the triacs fitted and removed as one unit (§ The heater wall board, *The bracket*); the thermal interfaces of the tab faces to the bracket and of the bracket to the wall are judged (§ The heater wall assembly, judged, *The bracket*). The forms record's wording, which left these to the assembly task, is brought up to date |
| Valve relays and pump drives on the mains board | On the main board; there is no separate mains board | § Candidate divisions |
| **Two retained harnesses change, the leads of the coffee and the steam element** (`COFHEATER`, terminal 5, and `STMHEATER`, terminal 4), which end at the wall board's faston tabs; "the only retained harnesses that change are the two element leads" (§ Wiring, connectors, mains-rated terminals, *Harness*, and *Drop-in*) | **Four different retained harnesses change, the leads of tabs 1, 2, 3 and 9** (`LINE1`, `LINE`, `NEUTRAL`, `HOTVALVE`), each fitting its tab 6.9, 7.0 and 7.5 mm further up and, for tab 9, 1.9 mm further down; **the element leads do not change**: tabs 4 and 5 are removed, and each lead keeps its female terminal and plugs onto an in-line insulated male-to-male 6.3 mm blade joiner placed by the owner, with nothing cut, lengthened or re-terminated, and a new wire runs from the joiner to the wall board's `OUT_S` or `OUT_C` | The forms record's words stay accurate in their own terms, that the element leads end at the wall board's blade terminals, by way of the new wire: the original harness reaches only the original tab, and the owner removed the two tabs because they carried nothing once the confirms moved to the wall board and no heater current ran through board copper there (2026-10-24); the fixing rule forces tabs 1 to 3 and tab 9 to move (§ The fixing rule and the tabs that move) |
| The heater switch's section on leakage: the mains-presence confirm "reports whether mains reached the element", reads "on while mains reaches the element", and the snubber capacitor is bounded at about 22 nF because, with the element open between the confirm's tap and the neutral, the snubber's current runs in the confirm's branch | **The board as found switches the neutral side of every load** (`connector-pinouts.md`), so the confirm across an element's switched lead and the neutral reads **on when the triac is open and the element intact, and off when the triac conducts**: stuck-on reads off while commanded off, failed-to-close reads on while commanded on, an open element reads off, and so does the whole board with the interlock open. The 22 nF bound falls away: with the element open the node is fed from nothing, and with it intact the snubber's current runs through the element; the confirm is not populated in any case | The forms record's reading is of a live-side switch, where the node stands at the neutral through the element when the triac is open; the arithmetic is in § The heater wall board, *The mains-presence confirm*. The forms record is not edited |
| The heater switch: "an insulated-tab snubberless triac, a snubber (a resistor and capacitor across the triac) and a MOV", the triac the BTA16-600BRG (S17) | The BTA16-600BRG is the **standard four-quadrant "B" type**, not a Snubberless™ one (P3, Table 9); **no snubber is fitted**, the varistor is kept, and the opto-triac's gate network is two resistors (360 Ω and 330 Ω, Figure 12 of P4) | A resistive load commutates a standard triac with 2.9 times the margin on dI/dt and 88 times on dV/dt (§ The heater wall board, *Snubbers and varistors*); the forms record is not edited |
| The valve relays' proving candidate is the HF115F-Q, and the HF32FA-G "does not meet *Rated for the supply*" with its 250 VAC maximum switching voltage under the 253 V top of the span (§ Two-way and three-way valve switching) | **The valve relays are the HF32FA-G/005-HSL1**; the interlock relay stays the HF115F-Q | The forms record allows "a different relay ... once its own datasheet's voltage rating is sourced and meets the target"; the owner accepted a 250 VAC contact rating at the top of the span for relay contacts on 2026-10-24 (`controller-board-design-constraints.md`, *Rated for the supply*), and the sheet's 1 000 VAC between open contacts and 5 000 VAC coil to contacts meet the blocking and isolation figures that the acceptance leaves in force (§ The valve relays). The forms record is not edited |
| The IRM-10-5 "is not the proving candidate, its margin at 70 °C being thin", and the IRM-20-5 has 2.3 times the earlier design's 0.86 A | **Agreed**, on this board's own load: the IRM-20-5 stays, with 2.13 times a 0.94 A budget at 70 °C; the IRM-10-5 has 1.06 times at 70 °C and 2.13 at 50 °C | The forms record's load was a scale only; the budget here is summed from the sheets of the parts the board carries (§ The logic supply against this board). The forms record is not edited |
| The [earlier design: mains inlet filter] is a "bought" module of the decision's chain; no mounting place is stated and nothing is said of where its fuse is held (§ [earlier design: Mains inlet filter]) | There is no [earlier design: inlet filter]: the machine keeps its fixed mains lead and the **10 A fuse and a varistor are on the main board** at tabs 2 and 3; the function is renamed *Mains entry protection* here and in the forms record | The decision `DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE` was amended to the retained lead after the forms record's row was written, and the forms record's heading and row are brought to it (§ Every function has one owner) |
| The HF115F-Q is the proving candidate of the **valve** switch (§ Two-way and three-way valve switching), and the interlock's mechanism and parts are the design task's (§ Proof-of-life interlock) | The interlock block is **drawn as an HF115F-Q relay**, the 5 V coil `HF115F-Q/005-1H`, and the valve relays are the HF32FA-G; this record chooses the interlock's mechanism, the two-channel drive of *The drive* in § The interlock block, and leaves its parts to the schematic leaf | The block needs a footprint, a contact rating and a heat to be sized with, and the relay family that the forms record already proves for a 20 A contact is the one used; a series element of another kind that meets the same figures replaces it. The forms record is not edited |

## The bought parts' creepage and clearance, as their makers publish them

This section records what the makers' documents say, read on **2026-10-31**; it compares nothing with the signed figures of `hardware/sunbeam-em7000/separation-basis.yaml`, which is the judging step's. A figure no document gives is **absent**, and none is estimated or taken from a similar part.

**The names.** The owner's acceptance of bought-part creepage and the graph name the four parts by their designators in the schematic's numbering: K201, K731, K741 and U602. This record has not drawn the schematic, and names the same parts by block: K201 is `K_IL` (HF115F-Q/005-1H, the interlock relay), K731 and K741 are `K_V1` and `K_V2` (HF32FA-G/005-HSL1, C91370), and U602 is the optocoupler of `TIMING` (LTV-814S, C108051). The mapping is by the part number and its use, and no KiCad file in the tree carries the schematic designators. For each relay the mains side is the contact terminals and the low-voltage side the coil pins (`K_IL` § The interlock block, `K_V1` § The valve relays); for U602 the mains side is the LED pins 1 and 2 (the copper pieces `TIMING.L` and `TIMING.N`) and the low-voltage side the phototransistor pins 3 and 4 (P12, p. 5, "1. Anode, Cathode 3. Emitter / 2. Cathode, Anode 4. Collector").

| Part | Quantity | Figure | Document | Page, section | Day read | The document's words |
|---|---|---|---|---|---|---|
| K201, `K_IL` | Creepage | **over 8 mm**, no upper figure; the sheet does not say between which conductors | P2, Hongfa HF115F-Q, 2024 Rev. 1.00 | p. 1, Features | 2026-10-31 | "Creepage distance >8mm" |
| K201, `K_IL` | Clearance | **absent**: pp. 1 to 3 hold no clearance figure | P2 | pp. 1 to 3, text and the page 1 image searched | 2026-10-31 | none |
| K201, `K_IL` | Coil to contacts | **no distance**; 5 000 VAC for one minute, surge 10 kV (1.2 / 50 µs), and the claim that it meets VDE 0700 and 0631 for reinforced insulation | P2 | p. 1, Characteristics and Features | 2026-10-31 | "Between coil & contacts 5000VAC 1min"; "Surge voltage (between coil & contacts) 10kV (1.2 / 50µs)"; "Meeting VDE 0700, 0631 reinforce insulation" |
| K731, K741, `K_V1`, `K_V2` | Creepage and clearance | **over 8 mm, one combined figure** for "creepage/clearance", not split and not tied to a pair of conductors; the same in both copies | P6, Hongfa HF32FA-G, 2026 Rev. 1.00 (sheet page 89), read from the page rendered as an image (`pdftoppm -r 100`, and its Features list again at 220 dpi, the text layer being unreliable on some extractors, which return the symbol as a fullwidth sign) | p. 1, Features | 2026-10-31 | "Creepage/clearance distance>8mm" |
| K731, K741 | Creepage and clearance, the copy the catalogue hosts | **over 8 mm, the same combined figure** | P19, Hongfa HF32FA-G, 2020 Rev. 1.00 (sheet page 77), rendered as an image | p. 1, Features | 2026-10-31 | "Creepage/clearance distance>8mm" |
| K731, K741 | Clearance on its own | **absent**: no separate figure in either copy, pp. 1 to 3 | P6, P19 | pp. 1 to 3 | 2026-10-31 | none |
| K731, K741 | Coil to contacts | **no distance**; 5 000 VAC for one minute and the claim of reinforced insulation to VDE 0700 and 0631; the drawing's 15.24 mm between the coil pins and the contact pins (the "1" of HSL1, against 12.7 mm for the other termination) is the pin pitch of the PCB layout and not a creepage figure | P6 | p. 1, Characteristics and Features; p. 2, PCB layout | 2026-10-31 | "Between coil & contacts 5000VAC 1min"; "5kV dielectric strength (between coil and contacts)"; "Meets VDE 0700, 0631 reinforce insulation" |
| U602, `TIMING` | Creepage, input to output | **absent** | P12, Lite-On LTV-814 / 824 / 844 (M, S, S-TA1), document BNS-OD-C131/A4, 13 pages, no revision or date printed (the file's creation date is 2003-04-21), the copy the catalogue hosts for C108051 | all 13 pages, searched for creep, clear, distance, insulation and tracking | 2026-10-31 | none |
| U602, `TIMING` | Clearance, input to output | **absent** | P12 | the same | 2026-10-31 | none |
| U602, `TIMING` | What the sheet gives | 5 000 Vrms for one minute and an isolation resistance of 5×10¹⁰ Ω at least; the LTV-814S outline has a 2.54 ±0.25 mm lead pitch, a 7.62 ±0.3 mm body width and a 10.16 ±0.3 mm lead span, a drawing of the package that states no creepage or clearance | P12 | p. 1 Features; p. 8 Absolute Maximum Rating, note *1; p. 9 Electro-optical characteristics; p. 5 Outline Dimensions (image) | 2026-10-31 | "High input-output isolation voltage ( Viso = 5,000Vrms )"; "Isolation Resistance Riso 5×10^10 1×10^11 Ω" |

The two HF32FA-G copies carry the same figure; P6 is the revision this record has cited since 2026-10-24, and P19 is the copy the catalogue hosts for the part it lists. The catalogue's own feature field for C91370 reads "Creepage/clearance distance > 8mm", a catalogue copy and not a maker document.

**The maker's safety certificates, searched for the figures the sheets omit** (the clearance of K201 and the creepage and clearance of U602, and the separate clearance of K731 and K741), 2026-10-31. **Result: none found for any of them.**

| Search | What it held | Result |
|---|---|---|
| The certificate numbers the sheets print | HF115F-Q: UL E134517, VDE 116934, CQC17002168381. HF32FA-G, 2026 sheet: UL E134517, VDE 40006182, CQC09002028689 and CQC23001382245; the 2020 copy: UL E134517, VDE 40006182, CQC17002175721. LTV-814: UL E113898, TUV R9653630, CSA CA91533-1, FIMKO 193422-01, NEMKO P96103013, DEMKO 303986, SEMKO 9646047/01-30, VDE 094722 (P12, p. 1) | The numbers only, with no date and no distance |
| Hongfa's product certification query (hongfa.com, service/certificate, keywords HF115F-Q and HF32FA-G) | Returns the certificate numbers above and says the certificate file is to be asked of the business representative | None found: no certificate file, report or distance published |
| Hongfa's product pages for both relays | Offer the datasheet and the substance declarations (RoHS, REACH, POPs, TSCA) and a file named GR1005.pdf, which was not opened and which its listing does not describe as a certificate; the only creepage text is the feature line quoted above | None found |
| UL (E134517, E113898) | The listing host answered HTTP 403 and the other UL host did not connect | **Not read**: could not be searched, so no figure and no statement that UL's file is silent |
| VDE (40006182, 116934, 094722) | The certificate page returned 404 and no public listing was found | None found |
| CQC | The site returned a stub that holds no search | None found; not searchable from here |
| The catalogue's pages for C91370 and C108051 | The datasheet links and the feature text quoted above; the only certificate files are the catalogue's own company ones | None found |
| Lite-On's own site for the LTV-814 | Its download and search pages answered with a "Request Rejected" page; the address tried was a guess and not a link, so no maker page for the part was reached and no newer revision than the catalogue's copy was read | **Not read**: no maker page reached; none found |

A figure of these parts that appears in no document above is therefore absent, and the three that the search could not reach (UL's listing, and Lite-On's site, for the two) are searches not made and not searches found empty.

### The four parts judged against the signed figures

Read against the signed 10.0 mm creepage and 3.0 mm clearance of `hardware/sunbeam-em7000/separation-basis.yaml` (`mains_to_low_voltage`), on 2026-10-31, from the table above. A figure the table calls absent counts as absent, not as adequate, and none is estimated. The relays' own short figure is inside the part, and the board check measures only the gap between pads on the board, so no exception entry can express it; the four U602 pad pairs can, because the board's pad gap is measurable. Neither is signed.

| Part | Quantity | Published figure | Signed figure | Arithmetic | Verdict | Where it sits |
|---|---|---|---|---|---|---|
| K201 | Creepage | over 8 mm, no upper figure | 10.0 mm | 8.0 mm at least, short by up to 2.0 mm (20 %); not shown to meet | Owner's choice (below, K201, K731 and K741) | Carried by the owner's acceptance (e) of 2026-10-29, which states "over 8 mm"; no entry |
| K201 | Clearance | absent | 3.0 mm | absent counts as absent, not adequate | Owner's choice (below) | No entry |
| K731 and K741 | Creepage | over 8 mm, one combined "creepage/clearance" figure | 10.0 mm | 8.0 mm at least, short by up to 2.0 mm (20 %); not shown to meet | Owner's choice (below) | Carried by acceptance (e), "K201 and K731/K741 over 8 mm"; no entry |
| K731 and K741 | Clearance | absent as its own figure (the combined figure is not split) | 3.0 mm | absent counts as absent, not adequate | Owner's choice (below) | No entry |
| U602 | Creepage | absent | 10.0 mm | absent counts as absent, not adequate; the board's own pad gap is 9.0 mm of row spacing less 1.3 mm of pad depth, 7.7 mm for the facing pairs 1-4 and 2-3 and 7.77 mm for the diagonals 1-3 and 2-4, short of 10.0 mm by 2.3 mm (23 %); the maker states nothing, so the 7.7 mm is the board's, not a creepage | Excepted in draft, unsigned: owner to decide | Four unsigned entries in the basis, 7.6 mm each (0.1 mm under the smallest gap, clear of rounding) |
| U602 | Clearance | absent | 3.0 mm | absent counts as absent; the board's own pad gap, 7.7 mm, is over 3.0 mm, so the check reports no clearance shortfall and no entry is drafted | Met on the board; the part's own figure absent | None |

**K201, K731 and K741: open for the owner.** The part-internal figures (K201's creepage over 8 mm and clearance absent; K731 and K741's combined over 8 mm and separate clearance absent) cannot be excused by an entry. The board's own gaps meet 10.0 mm and 3.0 mm on the layout in progress (K731 and K741: 13.05 mm from each contact pad to each coil pad; K201: about 30 mm), so the check reports no shortfall there, and an entry for a pair with no shortfall is refused. Whether a part whose published figure is under the signed one forms the reinforced barrier is the owner's to settle: accept the figure as published, change the part, or find a published figure. *Recommendation:* accept K201, K731 and K741. Each is a certified relay whose maker states reinforced insulation to VDE 0700 and 0631 and 5 000 VAC from coil to contacts (P2, P6), the board adds its own slots between the coil and contact rows, and the acceptance (e) already covers the over-8 mm figure on the grounds of the sealed enclosure, the slots, the planned conformal coat and nothing mains-referenced being touchable. The absent clearances stay absent; they are not read as 3.0 mm met.

**U602: open for the owner.** The maker publishes no creepage or clearance, only 5 000 Vrms for one minute. The four entries state the board's own pad gap and say in so many words that it is not a published creepage; they are drafts, unsigned. The owner decides: accept this distance, change the part, or find a published figure. *Recommendation:* accept it on the part's 5 000 Vrms rating and the sealed enclosure, or else choose a part whose maker publishes a creepage. If the main-board layout cuts a slot between U602's pad rows the measured gap grows and the entries are confirmed or dropped by the layout leaf's check.

**Open layout item (not an exception).** On K201 the two contact pads 13 and 14, on the nets `LINE1` and `LINE`, stand 5.06 mm apart across the open contact (centres 7.56 mm, pads 2.5 mm across). That pair is held at the reinforced 3.0 mm and 10.0 mm figures, and the basis allows no exception for it, so it is a violation until the layout slots between the pads or otherwise reaches 10.0 mm. The main-board layout leaf owns it.

## Sources read

Every address was opened on **2026-10-24**, except P15 and P16, opened on 2026-10-26, and P17 and P18, opened on 2026-10-28, which is also the date P3 and P4 were read again for § The heater wall assembly, judged, and the figures read from its text or drawing, and P19, opened on 2026-10-31, the day P2, P6 and P12 were read again for § The bought parts' creepage and clearance, as their makers publish them; the retailer's listing of a radial fuse mentioned in § The fuses was not a sheet and is not listed.

| No. | Document | Revision printed | Address |
|---|---|---|---|
| P1 | Mean Well IRM-20 series specification, *Mechanical Specification* and derating curve; dimensions 52.4 × 27.2 × 24 mm, pins, efficiency (typ.) 79 % at 5 V, 4.2 kVac withstand | File `IRM-20-SPEC 2025-11-21` | https://www.meanwell.com/Upload/PDF/IRM-20/IRM-20-SPEC.PDF (the forms record's S1) |
| P2 | Hongfa HF115F-Q: outline 29 × 12.7 × 15.7 mm and the drawing of both terminal variants (41 mm and 45 mm), PCB layout, contact ratings, electrical endurance, dielectric strength between open contacts, coil data (pick-up, drop-out, power, temperature rise), creepage | 2024 Rev. 1.00 | https://source.hongfa.com/Uploads/Product/PDF/HF115F-Q_en.pdf (S8) |
| P3 | STMicroelectronics DS2114, BTA16 family, Table 1 *Absolute maximum ratings*, Tables 2 to 4 (static characteristics, standard and Snubberless™ types), Table 6 *TO-220AB Insulated and non Insulated package mechanical data* and Table 9 *Ordering information* | Rev 11, May 2018 | The Internet Archive's copy of https://www.st.com/resource/en/datasheet/bta16.pdf (S17) |
| P4 | onsemi MOC3083M/D: package PDIP6 8.51 × 6.35 mm, 2.54 mm pitch; external creepage and clearance; absolute maximum ratings, static dv/dt, inhibit voltage and Figure 12 *Hot-Line Switching Application Circuit* | Rev. 2, September 2022 | https://www.onsemi.com/download/data-sheet/pdf/moc3083m-d.pdf (S16) |
| P5 | STMicroelectronics AN4938, § 7.4 *Decoupling*, Tables 8 and 9 | Rev 7, October 2024 | The Internet Archive's copy of https://www.st.com/resource/en/application_note/an4938-getting-started-with-stm32h74xig-and-stm32h75xig-mcu-hardware-development-stmicroelectronics.pdf (R3) |
| P6 | Hongfa HF32FA-G: outline 17.6 × 10.1 × 12.7 mm and the PCB layout, contact ratings, maximum switching voltage, coil data of the sensitive 5 V coil, dielectric strength, creepage, ambient range | 2026 Rev. 1.00 | https://source.hongfa.com/Uploads/Product/PDF/HF32FA-G_en.pdf (S9 of the forms record) |
| P7 | Mean Well IRM-10 series specification: 45.7 × 25.4 × 21.5 mm, pins, 2 A at 5 V, efficiency 77 % at 5 V, derating curve | File `IRM-10-SPEC 2025-08-08` | https://www.meanwell.com/Upload/PDF/IRM-10/IRM-10-SPEC.PDF (S2 of the forms record) |
| P8 | Multicomp Pro 5.2 × 20 mm time-lag ceramic cartridge fuse: interrupting rating 1 500 A at 250 V AC from 0.5 to 12 A; and the same maker's 6.3 × 32 mm ceramic sheet (200 A to 1 500 A at 250 V AC, 10 000 A at 125 V AC) | Farnell datasheets 2842926 and 2842928 | https://www.farnell.com/datasheets/2842926.pdf and https://www.farnell.com/datasheets/2842928.pdf |
| P9 | Multicomp Pro 5 × 20 mm time-lag glass cartridge fuse: 250 V AC, breaking capacity 35 A or ten times the rating | Farnell datasheet 3665666, V1.0 (2021-12-20) | https://www.farnell.com/datasheets/3665666.pdf |
| P10 | STMicroelectronics DS12110, STM32H742xI/G and STM32H743xI/G, *Electrical characteristics (rev V)*, Table 119: supply current in Run mode, 480 MHz, VOS0, all peripherals enabled, code in ITCM | Rev 11, January 2026 | The Internet Archive's copy of https://www.st.com/resource/en/datasheet/stm32h743vi.pdf (the machine record's source for the controller) |
| P11 | AVIA Semiconductor HX711, 24-bit ADC for weigh scales: SOP-16L package (body 9.9 × 3.9 mm, lead span 6.0 mm), supply 2.6 to 5.5 V, under 1.5 mA in normal operation, the typical application of its Figure 1 | V2.0 | https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/73/HX711.pdf (a copy of the maker's sheet) |
| P12 | Lite-On LTV-814 series, AC-input optocoupler (the LTV-814S is the surface-mount part): operating temperature −30 to +100 °C, 5 000 Vrms isolation | The copy hosted by the part's catalogue entry C108051 | https://datasheet.lcsc.com/datasheet/pdf/bc51d065248a46be93525386c92657f3.pdf |
| P13 | WeEn BTA204S-600B, 3Q Hi-Com triac: quick reference data (VDRM 600 V, IT(RMS) 4 A, ITSM 25 A, IH, IGT) and dynamic characteristics (dVD/dt, dIcom/dt) | Rev.02, 19 March 2025 | https://www.ween-semi.com/datasheet/BTA204S-600B.pdf (S7 of the forms record) |
| P14 | onsemi MOC3051M, MOC3052M, MOC3053M random-phase triac driver: absolute maximum ratings (VDRM 600 V, ITSM 1 A), static dv/dt, and the applications information on snubberless operation and Figures 8 and 9 | MOC3052M/D, Rev. 4, September 2022 | https://www.onsemi.com/download/data-sheet/pdf/moc3052m-d.pdf (S5 of the forms record) |
| P15 | Dongguan Bozhong Electrical Co., Ltd, drawing of the board-mounted tab `BTC-3-PCB634908T` (catalogue number C20626104): blade width B 6.3 ±0.2 mm, thickness T 0.8 mm (+0, −0.03), blade length A 14.3 ±0.2 mm, mating terminal "250 female, T = 0.8"; the catalogue's own title for the part reads 6.2 × 0.8 mm | Rev. A1, 2021-10-12 | The datasheet linked from the part's page, https://jlcpcb.com/partdetail/BZXC-BTC_3PCB634908T/C20626104, read 2026-10-26 |
| P16 | The manufacturer's parts library search service: the class, stock and price of C20626104 and of the other tabs of its family (C20626100 to C20626104; 4.8, 5.2 and 6.2 mm titles, 0.5 and 0.8 mm), and the search for a 1.95 mm header, which holds no entry; the classes of the seven header families, the shunt, the 120 kΩ resistor and the varistor C49072860 were read on 2026-10-25 and are recorded with their dates in `controller-board-cost-estimate.md` § What the library class allows | The service's answer on the date read | https://jlcpcb.com/parts, read 2026-10-26 (and 2026-10-25) |
| P17 | Wakefield Thermal Solutions, 120 series silicone thermal joint compound, catalogue page 64 (WTS001, 2007 print): typical case-to-sink resistance of a TO-220 0.50 °C/W at 0.9 N·m, 0.05 °C/W per 0.001 in film per square inch, conductivity 0.735 W/(m·K) at 36 °C, −40 to +200 °C; the copy read is a distributor's hosting of the maker's page, a distributor's print and not the maker's own file, so the 0.50 °C/W is the weakest-sourced figure in the heat paragraph of § The heater wall assembly, judged | WTS001 p. 64 | https://datasheet.chipsmall.com/120-5/485006.pdf |
| P18 | Zhuhai Hongjiacheng Technology, 07D series metal oxide varistor datasheet: 07D471K 300 VAC, 385 VDC, V1mA 423 to 517 V, clamp 775 V at 10 A (8/20 µs), withstanding surge 1 200 A (8/20 µs), 29 J (10/1000 µs), 0.25 W, −40 to +105 °C; the datasheet the part's catalogue page lists (C49072860) | Rev 1.2 | https://datasheet.lcsc.com/datasheet/pdf/772241be5b206a26b470227ece5bac36.pdf |
| P19 | Hongfa HF32FA-G, the copy the catalogue hosts for C91370: the same sheet as P6 in its earlier revision; creepage and clearance, read from the page rendered as an image | 2020 Rev. 1.00 | https://datasheet.lcsc.com/datasheet/pdf/8e13dd8e9e4af7eb5d7a6a986163e68f.pdf, the datasheet linked from https://www.lcsc.com/product-detail/C91370.html |

Records read as sources: `reference-machine.md`, `connector-pinouts.md`, `controller-board-function-forms.md`, `controller-board-design-constraints.md`, `component-specification.md`, `hardware/sunbeam-em7000/separation-basis.yaml`, `docs/board-manufacturer-jlcpcb.md`, `docs/board-design-method.md`. Decisions: `DEC-DEVICE-RETENTION-BOUNDARY`, `DEC-BOARD-SEPARATION-BASIS-RECORD`, `DEC-BOARD-PRE-ORDER-RULE-READINGS`, `DEC-PROOF-OF-LIFE-INTERLOCK-IN-FIRST-HARDWARE`, `DEC-IN-STREAM-PROBES-ANTICIPATED`, `DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE`, `DEC-CONTROLLER-BASELINE-STM32H743`, `DEC-BOARD-MANUFACTURER-JLCPCB`. Owner statements: those of § Owner intent carried in, and the lid, mains-entry and slack statements of 2026-10-20, as the machine record cites them. Nothing in this record rests on `controller-design/`, the earlier design.

## Appendix: the checks

One data block and one script. The data block holds every rectangle, position and rule of both floorplans and the inputs of the cost comparison; the script reads it from this file, computes every distance, surface path, area, resistance and total from it, compares the tables of this file with it, and compares what it prints with the expected output below. A builder holding this repository and any Python 3 interpreter repeats every check made here:

```
python3 -I -c "import re,sys; t=open(sys.argv[1]).read(); open(sys.argv[2],'w').write(re.search(r'^\`\`\`python\n(.*?)^\`\`\`', t, re.S|re.M).group(1))" docs/sunbeam-em7000/controller-board-division.md checks.py
python3 -I checks.py docs/sunbeam-em7000/controller-board-division.md main
python3 -I checks.py docs/sunbeam-em7000/controller-board-division.md wall
python3 -I checks.py docs/sunbeam-em7000/controller-board-division.md --tables
python3 -I checks.py docs/sunbeam-em7000/controller-board-division.md --selftest
```

`main` and `wall` print the figures quoted in the sections above and end with `all main board checks pass` or `all wall board checks pass`, or with `FAIL:` and each breach, and a non-zero status. `--tables` prints every cell of a table of this file as the data generates it and reports each that the file does not hold. `--selftest` perturbs the data, the text of the source records, the assumption tokens and the record's own text, and requires, for each perturbation, a message of the check it targets: every perturbation names that check, and a mismatch of a table of this file, which a producer can regenerate to match the data, does not count, nor does a message of another check that the perturbation happens to break. The script reads the separation basis, `connector-pinouts.md`, `reference-machine.md`, `controller-board-function-forms.md`, `controller-board-design-constraints.md`, `controller-board-cost-estimate.md` and `docs/board-manufacturer-jlcpcb.md` from their places in this repository. Of the cost record it reads only the figures this check counts or computes, each wherever the cost record restates it: the outline, its coordinates and its area in every unit; the slot count, path and density of both boards; the Extended types, their split and their feeder loading; the header types and ways; the joints; the heater wall board's body, span, area, types and joints; the main board's fabrication price and that of its two-layer fallback; and the counts of the parts the blocks fit that the parts tables restate. The manufacturer's charges, the totals built from them and the quantities the blocks do not give as a physical count (the clips, the 120 kΩ resistors and the wall board's parts, which a block's fit entry counts once however many it stands for) are not read. **Its checks are a consistency check, not a guard of the inputs** (§ How this record is built): the figures that have a source are compared with it, the assumptions are compared with their tokens, and the rest is the record's own arithmetic. The checks are these fifteen:

| Guard | What it holds | A perturbation the selftest makes |
|---|---|---|
| 1. Outline, ceiling | The outline polygon lies inside the cavity with its tolerances; every block lies inside the outline, at least the maker's board-edge distance (read from the maker's record) from its edge, and none overlaps another; every height is under its ceiling | The outline shrunk 7 mm on the right, so blocks lie outside it; the module made 30 mm high; the edge distance weakened to 0 |
| 2. Tabs, against the connector record | Every tab's name, as-found position, blade width and blade thickness equals the connector record's, and every row of that record is either drawn or listed as removed, with its name and as-found position (a tab both drawn and removed, or neither, fails); the pitch is at least the least as-found pitch; the X is unchanged; a pad is the blade's section with an annulus at least the maker's recommended ring; the strip is derived from the pads, the return landing's pad, the neutral pour with its shunt and the two link pours; the moves and the slack left are computed and the tables hold them; **each moved tab is needed**: brought 0.5 mm back toward its as-found place, any of them breaks a rule; **a tab the connector record has and the board does not draw is the owner's removal**, which the owner-intent table of the record states with its date: a tab the decision names that is drawn or not listed as removed, a tab listed as removed that no decision names, or a decision missing from the table, fails | A tab moved 0.3 mm toward the fixing; **tab 9 brought back to its as-found place, inside the fixing distance of point 3**; **a tab moved 3.1 mm with its as-found position moved with it**; the second or third tab moved 0.5 mm beyond what the rules need; the blade's thickness changed in the data, and in the connector record; the pads of two nets brought together with the pitch rule weakened; the pad of the removed tab 4 restored; **tab 4 drawn and taken off the removed list, which fails by the owner's decision and not by a path length; the owner's row taken out of the table, or its date changed**; a removed tab lost track of, or renamed; **a drawn tab left out of the data, which the connector record names and the board neither draws nor lists as removed** |
| 3. Every hole, against the machine record | The four mounting points and the cavity equal the machine record's rows, each point refused by name if the data lacks it; mains copper is at least E + 10.0 + 0.25 mm from every hole centre, point 3's included, and every body keeps its keep-out from it | A hole moved under a tab; **the hole at point 3 left out, and the hole at point 1**; a mounting-point row and the cavity width changed in the record; the lid keep-out weakened to 1.0 mm |
| 4. The reed | The lower lead is within the tolerance of the machine record's sentence, which the script reads, and the upper lead is its recorded pitch above; the keep-out is centred on the midpoint, inside the outline, and clear of every block, tab pad and lid-screw circle | The reed moved 2 mm; the sentence removed from the record; the tolerance widened to 5 mm; a block placed in its keep-out |
| 5. Creepage | The basis is read from `separation-basis.yaml`. Every pocket is at least 3.0 mm straight and 10.0 mm by surface path round the slots from every mains rectangle; each optocoupler's pins are 10.0 mm apart round their slot; **mains copper of different nets, every pair in the data, the tab pads, the return landing, the neutral pour, the shunt's lands and the link pours included, on the wall board the unpopulated confirm places' copper as well, and no pair excused for sharing a block**, is the signed 1.5 mm and the basic 4.1 mm apart, and across the open interlock contact, `LINE` and `LINE_IN` against `LINE1`, 3.0 mm and 10.0 mm; the interlock relay's terminals: each leg stands inside its copper by the hole's radius and the maker's ring, the coil pocket is the 12.7 mm body centred on the two contact terminals; no slot cuts copper, none is narrower than the maker's least, none is nearer copper than the maker's figure; the slot density is under the maker's | A slot shortened, on each board and for the slot between the link and the neutral pad; the signed creepage changed in the basis or in the data; the relay's two contacts 1.5 mm apart, or on one net; a relay leg moved out of its copper; two tab pads brought together; the two ends of a varistor 2 mm apart; an unpopulated confirm place's mains copper brought to 1.0 mm from the other's |
| 6. The wall edge and the bracket | Every mains rectangle of the wall board, the unpopulated confirm places' included, **every part body, and the mains lead ends of the opto-triacs**, is at least the basic creepage from the edge against the wall, with no exceptions; **each of the bracket's two mounts is E + 10.0 + 0.25 mm from every mains rectangle and E + 0.5 mm from the outline, and no part body lies within E of one; the bracket has two mounting ears and two mounts, each mount on its own ear, and the heat figures name the two triacs the board fits, no more and no fewer; the legs lie on the wall edge's strip, stand the lift clear of the board and keep the basic creepage from every mains rectangle in three dimensions; each triac's tab face lies on the standing leg; the two wall bolts stand inside the standing leg, 5.0 mm in from its ends and a driver's width from the tab screws and from each other; the driver's way, 6.0 mm wide along v, to each tab screw and each wall bolt crosses no part body of the drawn board; the wall cut and the unit's depth are computed from the legs, and the cut's areas are counted figures the record must state** | A mains rectangle moved to 3.0 mm, and a confirm place's; **a part body moved within 5 mm of the edge with its copper left where it was; an opto-triac's mains pins moved within 5 mm of it; a mount brought within 13.25 mm of mains copper; the lift made 3 mm; the standing leg stood 1 mm off the triac faces; a part put in the driver's way to a tab screw, and to a wall bolt; one ear, one mount or both mounts left out; a mount off its ear; a triac left out of the heat figures; the standing leg made short of the steam triac; the wall cut's window made taller** |
| 7. The heater path and the link | The wall board's chains are contiguous from the element to the return and share their copper after the triacs; every region is wide enough for 15 A; the squares, resistance, dissipation and longest run are computed. On the main board the link passes **the contact of `K_IL`, by its value and not only that a contact is named, standing between the relay's two halves on `LINE` and on `LINE1`**, and runs from the pour that holds the `LINE` tab's pad to the one that holds the `LINE1` tab's through that contact, each region lies inside its mains rectangle, is wide enough for 15 A, and the loss is under the budget at the steady supply current; the taps are on the net `LINE`, and the neutral taps leave the pour above the shunt; **the link begins with the entry fuse, whose load-side clip on `LINE` holds the link's first region and whose line-side clip is on the net of the pad of tab 2, which an inner layer joins to that pad, which no tap leaves and which the open contact names as upstream; the fuse holder is the 10 A holder's 24 × 9 mm; the varistor's line pad is on `LINE`, on the same piece of copper as the load-side clip and within 5.0 mm of it, and its neutral pad is on `NEUTRAL`;** the `LINE1` net reaches only the relay's contact copper, the link pour and the pad of tab 1; **the neutral return runs from the pad of tab 3 through the shunt's two lands to the pour that holds the landing's pad, each touching the next and wide enough for 15 A, the landing a tab pitch from the nearest tab, and the voltage measurement has the `NEUTRAL` piece the shunt channel shares;** the loads behind the relay (read from the constraints record) are under its rating; **every load's return, the heaters' at the landing and the pumps', the valves' and the module's, ends on `NEUTRAL` copper and joins the neutral pour above the shunt and none at the pad of tab 3, the returns joined above the shunt add up to every load's return (11.01 A), and a data block with no shunt is refused by name** | A link of a chain removed; a region narrowed; the logic supply tapped from the `LINE1` net; the shunt moved off the return path (its second land lifted off the pour); the neutral tapped from the pad of tab 3, below the shunt; the least tab pitch raised so that the landing stands short of it; the shunt's first land narrowed to 4 mm; **a pump's return, and the valves' return, joined at the pad of tab 3 on the plug side; a return left out; a return ended on copper of another net; the shunt taken away, or given no part; the contact of another relay named in the link, no contact named, or the contact between the wrong two regions; the varistor's line pad put on the line side of the fuse, moved 1.2 mm off the fuse's piece of copper and still within the distance, and moved 12 mm away; the fuse taken out of the link, its load-side clip put on the net of the pad of tab 2, its holder shortened to 20 mm; a tap from the line before the fuse; the line before the fuse taken off the inner-layer list, and left out of the open contact's upstream nets** |
| 8. Coverage and owners | The functions assigned equal the forms record's headings; every owner is non-blank, a declared board or assembly, and the one the owner table names, and no function is in the table twice; every harness heading of the connector record has a connector; every kind has a row; the kinds removed or kept agree with the blocks drawn and with the step the allocation stops at, the first at which the areas fit at the spacing drawn and an exhaustive search finds an arrangement of the headers, the least spacing drawn is no less than the spacing the capacity counts, every block of a kept kind lies inside its region, and kind 6 has no block; **a kind the data marks required cites a requirement criterion in the record's row, says required, and stands outside the removal order, and a row that says required is marked in the data; every kind of the record's table is in the data and no kind of the data is without a row, so a required kind deleted from the data is refused by name, and so is a data block that marks no kind required** | A function dropped; an owner blanked, or one the record does not declare; a harness dropped; a block of a removed kind drawn; a circuit block of the kept kind 5 taken away; kind 6 recorded as given; a kind kept that the regions cannot hold; a block drawn outside its region; **the required mark removed from the supply voltage kind; the supply voltage kind, which is required, deleted from the data; every required mark deleted** |
| 9. Heat | The controller, the sensing blocks and the opto-triacs (and, on the second wall layout, the unpopulated confirm places' optocouplers) keep their distances (A8) from **both heat sources, the module and the interlock relay**, each a source of a watt or more by the script's own figures; every low-voltage block is in a heat list; the 85 °C class's members are rated 15 K or less over the air and the parts listed outside it more; the 85 °C parts that stand under 15 mm from a source are the ones the data reports as not held, no more and no fewer, and `VMEAS` holds 15 mm from the relay; the arithmetic of why they cannot all hold, the count of every arrangement of them along the barrier column, and **the three what-if arrangements that hold a third part, each of which must break a rule**; the interlock relay keeps 15 mm from the module; **each analogue region keeps 20 mm from both sources, holds no block of another class and reaches as far as the rules leave it free**; and the relay moved right by the 3.0 mm and the 2.0 mm that a sensor 8 mm long would need is computed, with the sensing blocks it then breaks and the capacity it costs; **the two heater triacs stand at least the assumed 10.0 mm apart on their one wall (A31), and the junction rise, case limit and the wall's resistance each triac needs are computed from the forms record's figures** | An opto-triac moved to 9.5 mm from a triac; the opto-triac rule weakened to 10 mm; the analogue region stopped at Y 30.1 where the module once stood, and drawn over the relay's keep-out; the module moved 7.5 mm toward the interlock relay; the voltage measurement moved 8 mm toward the relay; a sensing block moved to 10 mm from the relay; the list of sensing blocks emptied; a part that holds reported as not held, and one that does not hold left out of the report; the voltage measurement accepted as not held from the relay; a 125 °C part left in the 85 °C class; the relay weakened to under a watt; **the coffee triac moved to 7.2 mm from the steam triac; the least distance raised to 20 mm** |
| 10. Routes | Every net whose copper is in separate pieces has a route for a trace of the width of A15 at the maker's tolerance, with half a grid cell in addition, that keeps its distances (where a slot lies between a point and the copper, the signed clearance straight and the creepage round the slot) and crosses no slot; **the pumps' returns, which join by an inner layer, are left out of the search, and each is shown to have no surface route; a return that has one and is called inner fails; the nets of tabs 8 and 9 and the line before the entry fuse are given as inner-layer joins and treated the same, each with a route clear of every hole, slot and low-voltage block shown on a layer of its own** | A slot drawn across a valve's channel; the trace widened until a lead has no route; the margin dropped; **the valves' return, which has a surface route, called an inner-layer join; a net with a surface route called an inner-layer join; a net without one taken off the inner-layer list** |
| 11. Assumptions | Every `name=value` token of the Assumptions table equals the data, once, and the script knows every token | Each of the 31 tokens changed in the data and in the record's row |
| 12. The selftest | Each perturbation of the data, of the text of the source records, of the tokens and of the record's own text names the check it targets, and counts as caught only when a message of that check is produced, so a check that stops checking is itself caught; a message about a table of the record does not count, and nor does a message of another check that the perturbation breaks by the way. A perturbation of a counted figure is caught by the counted-figure check, which names the figure | Every perturbation above (129 of the data in all), 69 changes to the record's own text (43 named: the confirm polarity, the owner's row that removes tabs 4 and 5 and its date, the series diode, the coil's feed requirement in three ways, the interlock relay's ordering code, catalogue number and thermal margin, the premise that the interlock cuts every load and its bring-up check, the wall board's orientation, a pending decision left without its pointer to the list, a pending decision that the list does not hold, a decision stated twice, the owner's measurement of the slack, the stiffness not analysed, the screw at point 3, the bracket's depth left for the owner to check, the harness blade's width and thickness, the two off-board assemblies, the entry fuse holder's place, its load side, the varistor's line pad and the inner-layer join of its line side in the fuses section, the entry parts' place in the reported items, the earlier wording of a missing place put back in the fuses section, in the reported items, in the owner table, as parts absent from the data and as separate work, the entry fuse and varistor at tabs 2 and 3, the 10 A holder, the 6 kA shortfall, the owner's check of the original board's varistor, emission suppression left to the main board design, an unmarked [earlier design: inlet filter], an unmarked [earlier design: mains-entry assembly], the plural and the hyphenated spellings of the two terms, a marker broken so a marked citation stands unmarked and an unmarked [earlier design: inlet filter] inside a plain fenced block; and, for each of the 13 pending owner decisions, its words called "Decision made" and its pointer taken out), and 20 changes to the source records' text (the forms record's triac dissipation, junction-to-case resistance and the price that stands for the interlock relay, a tab, a tab's thickness, a mounting point, the basis, the reed, the cavity, the maker's edge distance, annular ring and track tolerance, a load current, the connector record's statement about `LINE1`, the valve relay's price, the owner's acceptance withdrawn, its figure changed to 240 V, its label taken off and its owner taken out, the breaking capacity the chain needs) |
| 13. The valve relays, the rail and the fuses | The valve relay's contact rating against the coils' inrush, its open-contact peak against the 358 V blocked, its coil-to-contact peak against the 4.0 kV target, its switching voltage equal to the figure the owner accepted in the constraints record (not merely under it), and its price and the 12 V variant's price that stands for the interlock relay's (the 5 V variant's is not recorded) against the records; the 5 V budget summed from the sheets (each coil at the low end of its resistance tolerance) and the assumptions, the chosen module at 2.0 times or more at 70 °C and the smaller module under it; the shared fuse's load under 1 A and no sourced fuse reaching the breaking capacity | The switching voltage made 230 V, and 240 V; the open contacts made 200 V; the smaller module counted adequate; the rail loaded beyond the module; a coil taken at its nominal resistance; a fuse found at 6 kA |
| 14. What is counted | The header pins and header types (by ways and pitch), the joints of every part, the Extended types, those the manufacturer places and those the owner fits, and their fee, the current sensors on the rail, the kinds' areas, and the wall board's Extended types, joints and saving are counted from the blocks and must equal what the text and the tables state | A pin added to a header; a header's pitch changed, in a harness header and in the weight headers; a joint added to the module; a fuse holder taken out of a pump strip; the 120 kΩ mains-sense resistor left out of the part types; the pump opto-triac made a surface-mount part again (each changes a count the record states, and the counted-figure check names it) |
| 15. Required statements, the pending owner decisions and the relay's ratings | The statements the record must keep, word for word: the coil's feed requirement, the confirm polarity, the pump drives' series diode, the interlock relay's 5 V ordering code and that its catalogue number and price are not recorded, that it has no sourced thermal margin, that the claim that the interlock cuts every load rests on the owner's trace and is not proven until the bring-up continuity check, that this check is among the open items, the wall board's orientation to the wall, the owner's measurement of the four leads' slack before the order, that the board's stiffness is not analysed, that all four points carry a screw, that the bracket's depth in the cavity is left for the owner to check at assembly, the harness blade's width and thickness, the two off-board assemblies (the heater wall board and the steam-path assembly), where the entry fuse holder and the varistor stand, the fuse in series on `LINE` with the varistor's line pad on the piece that holds its load-side clip, and the line side joined on an inner layer (in § The fuses, and the place in the reported items), and the decided mains entry in § The fuses: the fuse and varistor at tabs 2 and 3, the 10 A holder against the board's 6.3 A holder, the 6 kA shortfall, the owner's check of the original board's varistor and emission suppression left to the main board design (the check holds that each is present; a contradicting statement added beside one is not refused, except the earlier wording of the entry parts' place, a missing place, parts absent from the data and the drawing, or placing left as separate work, which is refused wherever the prose says it); the relay's safety-approval (VDE) ratings against the current it carries and its overload band; the copper's temperature-rise estimate, from the constants of the data; every pending owner decision stated once in the record's list with its title and its words, pointed to from the section it concerns, and no other mention of one without the pointer | Each statement taken out or reworded; the coil's feed paragraph deleted; each of the 12 pending decisions called made and not pending, and its pointer taken out; a pending decision mentioned with no pointer; a decision stated twice; a decision dropped from the data, retitled, or given a home that does not point to it; the owner acceptance marker taken out of D11's item, its row or the wall cut paragraph, or the cut figure changed in D11's item or row (the script holds the figure and the marker together and cannot prove an acceptance exists: recording it changes the data, the script and the record together); the ratings taken out, or the highest-ambient rating put under the overload band |
| 16. The earlier design, named only when marked | The record's prose, outside the fenced blocks that are this script, the data, the expected output and the block of commands (named by their labels, each once; they hold the terms as code and output, and any other fenced block, a block never closed included, is read like prose), names neither a [earlier design: mains-entry assembly] nor an [earlier design: inlet filter], since the machine keeps its fixed mains lead; where the record deliberately cites the earlier design or the owner's ruling by those words, the cited words stand inside the marker `[earlier design: ...]` (a bracketed inline tag with no closing bracket inside it, so it survives a table cell), and any other occurrence, in any case, in the plural, with a hyphen, a slash or a space between the words, and across a line break, fails. That the marker is used only to cite the earlier design is a reviewer's judgement: the check cannot tell whether the wrapped words truthfully cite it, and it is a spelling check, so a paraphrase, an abbreviation or an unusual separator (an underscore, a dot, a non-breaking hyphen) is likewise left to the reviewer, as is "entry assembly" without "mains" | An unmarked [earlier design: inlet filter] and an unmarked [earlier design: mains-entry assembly] put back; a marker broken so a marked citation stands unmarked; an unmarked [earlier design: inlet filter] inside a plain fenced block; the plural [earlier design: mains-entry assemblies]; a hyphenated [earlier design: inlet-filter] |

### The data

One block holds the geometry of both boards and every input the checks use that no source record holds. Rectangles are `[x0, y0, x1, y1]`; the main board is in the datum frame and the wall board in its own `u`, `v` frame. A mains rectangle is `[id, rectangle, net]`; a net written `LINE|NEUTRAL` is on both.

```floorplan-data
{
  "note": "All lengths in millimetres. A rectangle is [x0, y0, x1, y1] (main board: datum frame; wall board: u along the wall edge, v away from it).",
  "basis": {"clearance": 3.0, "creepage": 10.0, "m_clearance": 1.5, "m_terminal": 2.0, "m_creepage": 4.1, "band": 102.0, "edge_min": 0.3},
  "maker": {"ring": 0.2},
  "cavity": {"w": 133.5, "h": 130.5, "tol": 0.5, "maker_tol": 0.2},
  "ceiling": {"interior": 27.9, "edge": 23.3, "edge_band": 2.0},
  "fixing": {"E": 3.0, "draw_tol": 0.25, "lid_keep": 3.5},
  "outline": [[1.0, 2.0], [132.0, 2.0], [132.0, 127.0], [1.0, 127.0]],
  "holes": {"P1": [6.5, 6.5], "P2": [126.7, 6.5], "P3": [6.5, 123.5], "P4": [127.0, 123.5]},
  "cut_centre": [133.5, 103.5],
  "tabs": {
    "x": 8.5,
    "ring": 0.32,
    "blade": 6.36,
    "thick": 0.81,
    "pitch": 8.3,
    "joints": 2,
    "slack_estimate": 10.0,
    "height": 9.9,
    "list": [
      {"n": 1, "name": "LINE1", "y": 20.5, "found": 13.6},
      {"n": 2, "name": "LINE", "net": "LINE_IN", "y": 29.3, "found": 22.3},
      {"n": 3, "name": "NEUTRAL", "y": 38.1, "found": 30.6},
      {"n": 6, "name": "COFVALVE", "y": 79.1, "found": 79.1},
      {"n": 7, "name": "COFFPUMP", "y": 91.4, "found": 91.4},
      {"n": 8, "name": "STEAMPUMP", "y": 101.2, "found": 101.2},
      {"n": 9, "name": "HOTVALVE", "y": 109.5, "found": 111.4}
    ],
    "removed": [{"n": 4, "name": "STMHEATER", "found": 52.9}, {"n": 5, "name": "COFHEATER", "found": 66.2}],
    "removal": {"row": "The main board's tabs 4 and 5", "date": "2026-10-24"}
  },
  "reed": {"recorded": [122.0, 17.5], "lower": [122.0, 17.5], "pitch": 20.0, "tol": 1.0, "hand_r": 5.0, "strip_w": 4.0},
  "intrusions": {
    "one_x0": 58.0,
    "one_x1": 105.5,
    "one_straight": 20.0,
    "one_cx": 81.75,
    "one_r": 23.75,
    "two_y1": 3.0,
    "one_h": 3.5,
    "two_h": 1.85,
    "lead_room": 0.5,
    "pos_tol": 0.5
  },
  "slot_width_min": 1.0,
  "slot_copper": 0.2,
  "slot_density": 80.0,
  "trace": {"w": 0.3, "tol": 0.2},
  "loads": {"coffee": 4.8, "steam": 5.38, "coffee_pump": 0.46, "steam_pump": 0.19, "coil_steady": 0.129, "coil_inrush": 0.203, "overload": 15.0},
  "relay": {"rating_a": 20.0, "endurance_ops": 30000, "coil_ohm": 62.0, "coil_tol": 0.1, "rise_k": 55.0, "ambient_c": 125.0, "vde": [[105.0, 18.0], [125.0, 16.0]]},
  "copper_rise": {"k": 0.048, "area_exp": 0.725, "rise_exp": 0.44, "oz_um": 35.0},
  "open_contact": {"nets": ["LINE", "LINE1"], "upstream": ["LINE_IN"]},
  "entry": {"fuse": "F_IL", "line": "F_IL.i", "load": "F_IL.o", "varistor": "RV_IL", "varistor_line": "RV_IL.l", "varistor_neutral": "RV_IL.n", "against_mm": 5.0},
  "owner_decisions": [
    {"id": "D1", "title": "The tab moves, or an amendment of the 10.0 mm fixing rule", "home": "The fixing rule and the tabs that move"},
    {"id": "D2", "title": "Whether the two mains-presence confirms come back onto the wall board", "home": "The heater wall board"},
    {"id": "D3", "title": "Where the supply current is sensed", "home": "The anticipated channel kinds"},
    {"id": "D4", "title": "The voltage measurement's place and the 85 °C stack", "home": "Heat"},
    {"id": "D5", "title": "One shared fuse for both pumps, or for the pumps and the valves", "home": "The fuses"},
    {"id": "D6", "title": "The smaller IRM-10-5 as the logic supply", "home": "The logic supply against this board"},
    {"id": "D7", "title": "Whether the two wall-board varistors stay", "home": "The heater wall board"},
    {"id": "D8", "title": "A blade terminal or a solder pad for the return landing", "home": "The path of the heater current"},
    {"id": "D9", "title": "The wall board as its own board, or a section that breaks off the main board", "home": "The heater wall board"},
    {"id": "D12", "title": "The removal-order priority of kinds 3, 4 and 5", "home": "The anticipated channel kinds"},
    {"id": "D13", "title": "2 oz copper against off-board wiring", "home": "Layer counts"},
    {"id": "D15", "title": "A basic mains-to-earth pair in the separation basis", "home": "The heater wall board"}
  ],
  "link": {
    "budget_w": 0.5,
    "strip": [{"id": "LK_L", "rect": [5.0, 28.55, 12.0, 34.3], "net": "LINE_IN"}, {"id": "LK_L1", "rect": [5.0, 19.775, 17.0, 25.55], "net": "LINE1"}],
    "chain": [
      {"fuse": "F_IL"},
      {"id": "F_IL.o from the fuse to K_IL.a", "in": "F_IL.o", "rect": [17.0, 34.3, 23.0, 38.8], "axis": "y"},
      {"id": "K_IL.a to its legs", "in": "K_IL.a", "rect": [17.0, 28.55, 23.0, 34.3], "axis": "x"},
      {"contact": "K_IL"},
      {"id": "K_IL.b from its legs", "in": "K_IL.b", "rect": [17.0, 19.775, 23.0, 25.55], "axis": "x"},
      {"id": "LK_L1 from X = 17 to the tab centre", "in": "LK_L1", "rect": [8.5, 19.775, 17.0, 25.55], "axis": "x"}
    ],
    "taps": [
      {"from": "F_IL.o", "net": "LINE", "to": ["MODULE", "TIMING", "VMEAS"]},
      {"from": "LK_N", "net": "NEUTRAL", "to": ["MODULE", "TIMING", "VMEAS"]}
    ]
  },
  "return": {
    "landing": {"id": "WB_RET", "y": 46.6, "net": "NEUTRAL"},
    "pour": {"id": "LK_N", "rect": [5.0, 45.825, 12.0, 49.0], "net": "NEUTRAL"},
    "shunt": {
      "id": "I_SHUNT",
      "rect": [5.0, 38.825, 12.0, 45.825],
      "lands": [["I_SHUNT.a", [5.0, 38.825, 12.0, 40.725]], ["I_SHUNT.b", [5.0, 43.925, 12.0, 45.825]]],
      "fit": [["shunt", 0]],
      "parts": 2
    },
    "module_pf": 0.5,
    "branches": [
      {"load": "coffee element", "amps": "coffee", "via": "WB_RET", "joins": "LK_N", "layer": "surface"},
      {"load": "steam element", "amps": "steam", "via": "WB_RET", "joins": "LK_N", "layer": "surface"},
      {"load": "coffee pump", "amps": "coffee_pump", "via": "P_C.N", "joins": "LK_N", "layer": "inner"},
      {"load": "steam pump", "amps": "steam_pump", "via": "P_S.N", "joins": "LK_N", "layer": "inner"},
      {"load": "valve coils", "amps": "coil_steady", "via": "VFUSE.n", "joins": "LK_N", "layer": "surface"},
      {"load": "logic supply", "amps": "module", "via": "MODULE.n", "joins": "LK_N", "layer": "surface"}
    ]
  },
  "fallback": {"anchor": "K_V2", "width": 7.0},
  "mains_blocks": [
    {
      "id": "TIMING",
      "fn": "Supply-timing front end: AC-input optocoupler and its series resistors",
      "body": [19.8, 2.5, 65.3, 9.5],
      "mains": [["TIMING.L", [19.8, 2.5, 29.0, 9.5], "LINE"], ["TIMING.N", [37.0, 2.5, 55.3, 9.5], "NEUTRAL"]],
      "pockets": [[60.3, 2.7, 65.3, 8.7]],
      "pins": [],
      "h": 5.0,
      "dip": {"centre": [57.8, 6.0], "row": 5.0, "pin_dy": 1.27, "pins": 2},
      "fit": [["ac_opto", 0], ["sense_res", 0]]
    },
    {
      "id": "K_IL",
      "fn": "Relay K_IL, the proof-of-life interlock, in the LINE to LINE1 link: contact end left, coil end right",
      "body": [17.0, 19.775, 58.0, 34.3],
      "mains": [["K_IL.a", [17.0, 28.55, 25.0, 34.3], "LINE"], ["K_IL.b", [17.0, 19.775, 25.0, 25.55], "LINE1"]],
      "pockets": [[50.0, 20.7, 58.0, 33.4]],
      "pins": [[18.0, 23.27], [23.0, 23.27], [18.0, 30.83], [23.0, 30.83], [55.5, 23.27], [55.5, 30.83]],
      "h": 15.7,
      "heat": [17.0, 20.7, 58.0, 33.4],
      "terminals": {"centre_y": 27.05, "pitch_y": 7.56, "legs_x": [18.0, 23.0], "hole": 1.6, "coil_x": 55.5, "body_w": 12.7},
      "fit": [["k_il", "pins"]]
    },
    {
      "id": "F_IL",
      "fn": "Entry fuse holder, 10 A: the lead's line conductor from tab 2 enters its right clip and leaves its left clip",
      "body": [17.0, 34.3, 41.0, 43.3],
      "mains": [["F_IL.o", [17.0, 34.3, 23.0, 43.3], "LINE"], ["F_IL.i", [35.0, 34.3, 40.0, 43.3], "LINE_IN"]],
      "pockets": [],
      "pins": [],
      "h": 15.0
    },
    {
      "id": "RV_IL",
      "fn": "Entry varistor, 14 mm disc across the fused line and the neutral",
      "body": [17.25, 43.3, 31.25, 48.3],
      "mains": [["RV_IL.l", [19.5, 43.3, 21.5, 45.3], "LINE"], ["RV_IL.n", [27.0, 46.3, 29.0, 48.3], "NEUTRAL"]],
      "pockets": [],
      "pins": [],
      "h": 21.0
    },
    {
      "id": "VFUSE",
      "fn": "Shared fuse holder for both valve branches",
      "body": [17.0, 50.5, 26.0, 74.5],
      "mains": [["VFUSE.v", [17.0, 69.5, 26.0, 74.5], "VFUSE"], ["VFUSE.n", [17.0, 50.5, 26.0, 55.5], "NEUTRAL"]],
      "pockets": [],
      "pins": [],
      "h": 15.0,
      "fit": [["holder", 4], ["clip", 0]]
    },
    {
      "id": "VMEAS",
      "fn": "Supply-voltage measurement: series divider on LINE and NEUTRAL, an isolating part and its low-voltage output",
      "body": [32.5, 48.4, 70.0, 53.4],
      "mains": [["VMEAS.N", [32.5, 48.4, 43.5, 53.4], "NEUTRAL"], ["VMEAS.L", [50.0, 48.4, 60.0, 53.4], "LINE"]],
      "pockets": [[65.0, 48.4, 70.0, 53.4]],
      "pins": [],
      "h": 5.0,
      "dip": {"centre": [62.5, 50.9], "row": 3.81, "pin_dy": 2.54, "pins": 3},
      "hot": [58.0, 48.4, 68.0, 53.4]
    },
    {
      "id": "MODULE",
      "fn": "Logic supply, IRM-20-5: AC pins left, DC pins right",
      "body": [32.5, 53.4, 84.9, 80.6],
      "mains": [["MODULE.n", [32.9, 53.6, 38.9, 59.6], "NEUTRAL"], ["MODULE.l", [32.9, 74.4, 38.9, 80.4], "LINE"]],
      "pockets": [[76.5, 53.9, 84.9, 67.9]],
      "pins": [[35.9, 56.6], [35.9, 77.4], [80.9, 56.6], [80.9, 64.6]],
      "h": 24.0,
      "fit": [["module", "pins"]]
    },
    {
      "id": "K_V1",
      "fn": "Relay K_V1, two-way valve (tab 6): contact end left, coil end right",
      "body": [44.5, 80.6, 62.1, 90.7],
      "mains": [["K_V1", [44.5, 81.225, 47.26, 90.075], "COFVALVE"]],
      "pockets": [[58.9, 80.6, 62.1, 90.7]],
      "pins": [[60.7, 81.85], [60.7, 89.45], [45.46, 82.475], [45.46, 88.825]],
      "h": 12.7,
      "pad_hole": 1.3,
      "fit": [["valve_relay", "pins"]]
    },
    {
      "id": "P_C",
      "fn": "Coffee-pump drive: fuse holder, DPAK triac, DIP-6 opto-triac with its slot",
      "body": [20.0, 93.1, 65.5, 102.1],
      "mains": [["P_C", [20.0, 93.1, 46.5, 102.1], "COFFPUMP"], ["P_C.N", [51.5, 93.1, 55.5, 102.1], "NEUTRAL"]],
      "pockets": [[60.5, 93.1, 65.5, 102.1]],
      "pins": [],
      "h": 15.0,
      "dip": {"centre": [58.0, 97.6], "row": 3.81, "pin_dy": 2.54, "pins": 3},
      "hot": [53.0, 93.1, 63.0, 102.1],
      "fit": [["holder", 4], ["clip", 0], ["pump_triac", 0], ["pump_opto", 6]]
    },
    {
      "id": "P_S",
      "fn": "Steam-pump drive",
      "body": [20.0, 105.1, 65.5, 114.1],
      "mains": [["P_S", [20.0, 105.1, 46.5, 114.1], "STEAMPUMP"], ["P_S.N", [51.5, 105.1, 55.5, 114.1], "NEUTRAL"]],
      "pockets": [[60.5, 105.1, 65.5, 114.1]],
      "pins": [],
      "h": 15.0,
      "dip": {"centre": [58.0, 109.6], "row": 3.81, "pin_dy": 2.54, "pins": 3},
      "hot": [53.0, 105.1, 63.0, 114.1],
      "fit": [["holder", 4], ["clip", 0], ["pump_triac", 0], ["pump_opto", 6]]
    },
    {
      "id": "K_V2",
      "fn": "Relay K_V2, three-way valve (tab 9): contact end left, coil end right",
      "body": [44.5, 116.5, 62.1, 126.6],
      "mains": [["K_V2", [44.5, 117.125, 47.26, 125.975], "HOTVALVE"]],
      "pockets": [[58.9, 116.5, 62.1, 126.6]],
      "pins": [[60.7, 117.75], [60.7, 125.35], [45.46, 118.375], [45.46, 124.725]],
      "h": 12.7,
      "pad_hole": 1.3,
      "fit": [["valve_relay", "pins"]]
    }
  ],
  "lv_blocks": [
    {
      "id": "MCU",
      "fn": "Controller, STM32H743VIT6, decoupling, crystals, reset, boot, programming header, 3.3 V regulator",
      "rect": [72.0, 95.6, 104.3, 126.7],
      "tht": false,
      "fit": [["mcu", 0]]
    },
    {
      "id": "CON2",
      "fn": "Panel harness header CON2, 9 ways, 2.0 mm pitch",
      "rect": [124.5, 76.0, 131.5, 96.5],
      "tht": true,
      "h": 15.0,
      "conn": {"ways": 9, "pitch": 2.0}
    },
    {
      "id": "SP2",
      "fn": "Gauge harness header SP2, 9 ways, 2.0 mm pitch",
      "rect": [124.5, 98.0, 131.5, 118.5],
      "tht": true,
      "h": 15.0,
      "conn": {"ways": 9, "pitch": 2.0}
    },
    {
      "id": "KNOB",
      "fn": "Knob microswitch header, 4 ways, 1.95 mm pitch",
      "rect": [113.6, 108.0, 124.0, 115.0],
      "tht": true,
      "h": 15.0,
      "conn": {"ways": 4, "pitch": 1.95}
    },
    {
      "id": "FLOW",
      "fn": "Flow meter header CZ1, 3 ways, 2.54 mm pitch",
      "rect": [113.9, 98.0, 124.0, 105.5],
      "tht": true,
      "h": 15.0,
      "conn": {"ways": 3, "pitch": 2.54}
    },
    {
      "id": "TEMP_C",
      "fn": "Coffee-block thermistor header RT1, 2 ways, 2.54 mm",
      "rect": [117.0, 86.0, 124.0, 93.5],
      "tht": true,
      "h": 15.0,
      "conn": {"ways": 2, "pitch": 2.54}
    },
    {
      "id": "TEMP_S",
      "fn": "Steam-block thermistor header, 2 ways, 2.54 mm",
      "rect": [117.0, 76.0, 124.0, 83.5],
      "tht": true,
      "h": 15.0,
      "conn": {"ways": 2, "pitch": 2.54}
    },
    {
      "id": "TEMP_W",
      "fn": "Wand thermistor header, 2 ways, 2.54 mm, fitted rotated 180 degrees",
      "rect": [114.0, 119.0, 121.0, 126.5],
      "tht": true,
      "h": 15.0,
      "conn": {"ways": 2, "pitch": 2.54}
    },
    {"id": "DRV_K1", "fn": "Coil driver for K_V1: transistor, flyback diode, pull-down", "rect": [65.5, 80.6, 72.0, 90.7], "tht": false},
    {"id": "DRV_K2", "fn": "Coil driver for K_V2", "rect": [65.5, 116.5, 72.0, 126.6], "tht": false},
    {"id": "DRV_PC", "fn": "LED drive for the coffee pump's opto-triac", "rect": [66.0, 93.1, 72.0, 102.1], "tht": false},
    {"id": "DRV_PS", "fn": "LED drive for the steam pump's opto-triac", "rect": [66.0, 105.1, 72.0, 114.1], "tht": false},
    {"id": "DRV_TIM", "fn": "Output conditioning of the timing optocoupler", "rect": [66.5, 2.7, 72.5, 8.7], "tht": false},
    {
      "id": "FE_GAUGE",
      "fn": "Gauge drive: octal buffer, five pull-downs, two decoupling capacitors",
      "rect": [72.0, 80.6, 93.5, 92.6],
      "tht": false
    },
    {"id": "DRV_HEAT", "fn": "LED-drive stages for the two heater opto-triacs", "rect": [94.0, 79.8, 102.5, 91.8], "tht": false},
    {
      "id": "FE_PANEL",
      "fn": "Operator panel: gate switch for the anode rail, five key pull-ups, buzzer switch",
      "rect": [105.0, 75.0, 115.0, 91.0],
      "tht": false
    },
    {"id": "FE_NTC", "fn": "Three thermistor dividers with filter capacitors", "rect": [105.5, 92.5, 113.5, 106.5], "tht": false},
    {
      "id": "FE_FLOW",
      "fn": "Flow input: pull-up, series resistor, filter capacitor, Schmitt buffer footprint and its link",
      "rect": [105.0, 107.5, 113.0, 117.5],
      "tht": false
    },
    {
      "id": "FE_STMD",
      "fn": "Steam-transducer digital header protection: two series resistors, two pull-ups, two clamps",
      "rect": [105.0, 118.5, 113.0, 126.5],
      "tht": false
    },
    {
      "id": "POL",
      "fn": "Proof-of-life circuit that drives K_IL's coil: a buffer, two charge-pump channels and two series FETs",
      "rect": [70.5, 31.0, 82.5, 43.0],
      "tht": false
    },
    {"id": "BREW_D_C", "fn": "Brew-path pressure, digital header protection", "rect": [87.5, 31.0, 97.5, 39.0], "tht": false},
    {"id": "FE_KNOB", "fn": "Knob microswitch inputs: two pull-ups and two filter capacitors", "rect": [71.0, 43.5, 79.0, 49.5], "tht": false},
    {"id": "FE_WATER", "fn": "Tank-level input conditioning and the low-water indicator sink", "rect": [108.5, 32.0, 116.5, 40.0], "tht": false},
    {
      "id": "IN_COND",
      "fn": "Input conditioning for the zero crossing and the two mains-presence inputs",
      "rect": [98.0, 31.0, 108.0, 39.0],
      "tht": false
    },
    {
      "id": "WB_LV10",
      "fn": "Header for the heater wall board's low-voltage cable, 10 ways, 2.54 mm",
      "rect": [123.7, 44.5, 131.2, 72.5],
      "tht": true,
      "h": 15.0,
      "region": "hdr",
      "conn": {"ways": 10, "pitch": 2.54}
    },
    {
      "id": "STM_D",
      "fn": "Steam-transducer digital header, 4 ways (3V3, GND, SCL, SDA)",
      "rect": [93.0, 65.3, 100.5, 77.9],
      "tht": true,
      "h": 15.0,
      "region": "hdr",
      "conn": {"ways": 4, "pitch": 2.54}
    },
    {
      "id": "BREW_D",
      "fn": "Brew-path pressure digital header, 4 ways",
      "rect": [108.1, 44.5, 115.6, 57.1],
      "tht": true,
      "h": 15.0,
      "region": "hdr",
      "kind": 12,
      "conn": {"ways": 4, "pitch": 2.54}
    },
    {
      "id": "PT1_H",
      "fn": "In-stream probe 1 header, 4 ways",
      "rect": [115.9, 44.5, 123.4, 57.1],
      "tht": true,
      "h": 15.0,
      "region": "hdr",
      "kind": 11,
      "conn": {"ways": 4, "pitch": 2.54}
    },
    {
      "id": "BREW_A",
      "fn": "Brew-path pressure analogue header, 4 ways",
      "rect": [108.1, 57.4, 115.6, 70.0],
      "tht": true,
      "h": 15.0,
      "region": "hdr",
      "kind": 12,
      "conn": {"ways": 4, "pitch": 2.54}
    },
    {
      "id": "PT2_H",
      "fn": "In-stream probe 2 header, 4 ways",
      "rect": [115.9, 57.4, 123.4, 70.0],
      "tht": true,
      "h": 15.0,
      "region": "hdr",
      "kind": 11,
      "conn": {"ways": 4, "pitch": 2.54}
    },
    {
      "id": "SPARE_A",
      "fn": "Spare analogue header for the steam transducer's analogue fallback, 4 ways (5V, 3V3, GND, input)",
      "rect": [85.2, 44.5, 92.7, 57.1],
      "tht": true,
      "h": 15.0,
      "region": "hdr",
      "conn": {"ways": 4, "pitch": 2.54}
    },
    {
      "id": "SPARE_AN2_H",
      "fn": "Second spare analogue header, 4 ways",
      "rect": [85.2, 57.4, 92.7, 70.0],
      "tht": true,
      "h": 15.0,
      "region": "hdr",
      "kind": 7,
      "conn": {"ways": 4, "pitch": 2.54}
    },
    {
      "id": "CURR1_H",
      "fn": "Current-sensing header, first channel, 3 ways",
      "rect": [93.0, 44.5, 100.5, 54.6],
      "tht": true,
      "h": 15.0,
      "region": "hdr",
      "kind": 8,
      "conn": {"ways": 3, "pitch": 2.54}
    },
    {
      "id": "PT1_C",
      "fn": "In-stream temperature converter 1: RTD-to-digital converter, reference resistor, capacitors",
      "rect": [76.5, 3.0, 90.5, 13.0],
      "tht": false,
      "region": "ana",
      "kind": 11
    },
    {"id": "PT2_C", "fn": "In-stream temperature converter 2", "rect": [91.0, 3.0, 105.0, 13.0], "tht": false, "region": "ana", "kind": 11},
    {
      "id": "FE_SPAREA",
      "fn": "Spare analogue input (the steam transducer's analogue fallback): divider, filter, series resistor, clamp",
      "rect": [105.5, 3.0, 115.5, 11.0],
      "tht": false,
      "region": "ana"
    },
    {
      "id": "BREW_A_C",
      "fn": "Brew-path pressure, analogue fallback: divider, filter, clamp",
      "rect": [78.0, 14.5, 88.0, 22.5],
      "tht": false,
      "region": "ana",
      "kind": 12
    },
    {
      "id": "SPARE_AN2_C",
      "fn": "A second spare analogue input: divider, filter, clamp",
      "rect": [88.4, 14.5, 97.8, 22.5],
      "tht": false,
      "region": "ana",
      "kind": 7
    },
    {
      "id": "CURR1_C",
      "fn": "Current-sensing channel 1: burden and filter",
      "rect": [98.2, 14.5, 104.2, 22.5],
      "tht": false,
      "region": "ana",
      "kind": 8
    },
    {
      "id": "I_C",
      "fn": "Heater current measurement: its conditioning on the main board",
      "rect": [104.6, 14.5, 110.6, 22.5],
      "tht": false,
      "region": "ana",
      "kind": 9
    },
    {
      "fn": "Weight channel 1 load-cell header, 5 ways, 2.0 mm",
      "tht": true,
      "h": 15.0,
      "rect": [100.8, 44.5, 107.8, 57.0],
      "id": "WT1_H",
      "region": "hdr",
      "kind": 2,
      "conn": {"ways": 5, "pitch": 2.0}
    },
    {
      "fn": "Weight channel 2 load-cell header, 5 ways, 2.0 mm",
      "tht": true,
      "h": 15.0,
      "rect": [100.8, 57.3, 107.8, 69.8],
      "id": "WT2_H",
      "region": "hdr",
      "kind": 2,
      "conn": {"ways": 5, "pitch": 2.0}
    },
    {
      "id": "WT1_C",
      "fn": "Weight channel 1: HX711-class amplifier (SOP-16) and its passives",
      "rect": [78.0, 22.9, 97.0, 30.1],
      "tht": false,
      "region": "ana",
      "kind": 2
    },
    {
      "id": "WT2_C",
      "fn": "Weight channel 2: HX711-class amplifier (SOP-16) and its passives",
      "rect": [97.5, 22.9, 116.5, 30.1],
      "tht": false,
      "region": "ana",
      "kind": 2
    },
    {
      "id": "VM_C",
      "fn": "Supply voltage measurement: conditioning of the isolated output",
      "rect": [116.0, 3.0, 122.7, 10.2],
      "tht": false,
      "region": "ana",
      "kind": 1
    },
    {
      "id": "CURR2_C",
      "fn": "Current-sensing channel 2: burden and filter",
      "rect": [111.0, 14.5, 117.0, 22.5],
      "tht": false,
      "region": "ana",
      "kind": 5
    },
    {
      "id": "CURR2_H",
      "fn": "Current-sensing header, second channel, 3 ways",
      "rect": [93.0, 54.9, 100.5, 65.0],
      "tht": true,
      "h": 15.0,
      "region": "hdr",
      "kind": 5,
      "conn": {"ways": 3, "pitch": 2.54}
    }
  ],
  "reed_block_fn": "Tank reed element pads, hand-fitted, with its body strip and hand access",
  "slots": [
    {"id": "SL_LINK", "rect": [1.0, 26.55, 31.0, 27.55]},
    {"id": "SL_LN", "rect": [1.0, 35.3, 16.5, 36.3]},
    {"id": "SL_TIM", "rect": [57.3, 2.0, 58.3, 12.5]},
    {"id": "SL_VM", "rect": [62.0, 43.4, 63.0, 58.4]},
    {"id": "SL_VP", "rect": [36.0, 91.1, 67.5, 92.1]},
    {"id": "SL_PP", "rect": [17.0, 103.1, 57.5, 104.1]},
    {"id": "SL_PV", "rect": [36.0, 115.1, 67.5, 116.1]},
    {"id": "SL_PUMPS", "rect": [57.5, 91.1, 58.5, 116.1]}
  ],
  "route_groups": {"LINE": "LINE|NEUTRAL", "NEUTRAL": "LINE|NEUTRAL"},
  "inner_nets": ["HOTVALVE", "LINE_IN"],
  "reach": {"CON2": 35, "SP2": 35, "KNOB": 35, "FLOW": 35, "TEMP_C": 35, "TEMP_S": 60, "TEMP_W": 60},
  "heat": {
    "sources": ["MODULE", "K_IL"],
    "source_w": 1.0,
    "air_c": 70.0,
    "class_k": 15.0,
    "limits": {"mcu": 15.0, "sense": 20.0, "relay": 15.0, "opto": 20.0, "class": 15.0, "triac": 10.0},
    "mcu": ["MCU"],
    "sense": ["FE_NTC", "PT1_C", "PT2_C", "BREW_A_C", "SPARE_AN2_C", "CURR1_C", "I_C", "FE_SPAREA", "WT1_C", "WT2_C", "VM_C", "CURR2_C"],
    "digital": ["FE_GAUGE", "POL", "DRV_HEAT"],
    "other": ["DRV_K1", "DRV_K2", "DRV_PC", "DRV_PS", "DRV_TIM", "FE_PANEL", "FE_FLOW", "FE_STMD", "BREW_D_C", "FE_KNOB", "FE_WATER", "IN_COND"],
    "class85": [
      {"id": "K_V1", "limit_c": 85.0},
      {"id": "K_V2", "limit_c": 85.0},
      {"id": "P_C", "limit_c": 85.0},
      {"id": "P_S", "limit_c": 85.0},
      {"id": "VMEAS", "limit_c": 85.0}
    ],
    "outside": [{"id": "TIMING", "limit_c": 100.0}],
    "accepted": [["K_V1", "MODULE"], ["P_C", "MODULE"], ["VMEAS", "MODULE"]],
    "required_held": [["VMEAS", "K_IL"]]
  },
  "regions": {
    "gap": {"hdr": 0.3, "ana": 0.4},
    "alternatives": [[3, 4], [3, 5], [4, 5], [3], [4], [5]],
    "hdr": [{"id": "H_A", "rect": [85.0, 44.5, 105.0, 78.0]}, {"id": "H_B", "rect": [105.0, 44.5, 131.5, 74.5]}],
    "ana": [
      {"id": "AR_a", "rect": [76.5, 3.0, 117.0, 13.0]},
      {"id": "AR_b", "rect": [78.0, 13.0, 117.0, 31.0]},
      {"id": "AR2", "rect": [117.0, 3.0, 123.2, 11.5]}
    ],
    "strip_h": 7.0,
    "other": {},
    "top_of": "AR_b",
    "relay_bound": ["AR_a", "AR_b"]
  },
  "kinds": [
    {"n": 1, "name": "Supply voltage measurement", "blocks": ["VMEAS", "VM_C"], "fixed": true, "required": true},
    {"n": 2, "name": "Weight-based endpoint, two load-cell amplifiers", "blocks": ["WT1_H", "WT2_H", "WT1_C", "WT2_C"], "rank": 4},
    {
      "n": 3,
      "name": "Further temperature and pressure inputs of the kinds in use",
      "hdr": [[7.0, 7.5], [7.0, 7.5], [7.5, 12.6]],
      "ana": [[10.0, 8.0]],
      "rank": 1
    },
    {
      "n": 4,
      "name": "Direct group-head instrumentation, two channels",
      "hdr": [[7.5, 10.1], [7.5, 10.1]],
      "ana": [[6.0, 8.0], [6.0, 8.0]],
      "rank": 2
    },
    {"n": 5, "name": "A second current-sensing channel", "rank": 3, "sensor": true, "blocks": ["CURR2_H", "CURR2_C"]},
    {"n": 6, "name": "A further switched output, such as another valve", "none": true, "fixed": true},
    {"n": 7, "name": "A spare analogue input", "blocks": ["SPARE_AN2_H", "SPARE_AN2_C"], "fixed": true},
    {"n": 8, "name": "Current sensing, first channel", "blocks": ["CURR1_H", "CURR1_C"], "fixed": true, "sensor": true},
    {"n": 9, "name": "Total supply current measurement", "blocks": ["I_C"], "fixed": true, "sensor": true, "shunt": true},
    {"n": 10, "name": "Real-time clock", "blocks": [], "fixed": true},
    {"n": 11, "name": "In-stream temperature, two PT1000 probes", "blocks": ["PT1_H", "PT2_H", "PT1_C", "PT2_C"], "fixed": true},
    {"n": 12, "name": "Brew-path pressure transducer", "blocks": ["BREW_D", "BREW_A", "BREW_D_C", "BREW_A_C"], "fixed": true}
  ],
  "functions": [
    {"name": "Controller", "owner": "main"},
    {"name": "Coffee element switching and steam element switching", "owner": "wall"},
    {"name": "Heater gate drive, both channels", "owner": "main"},
    {"name": "Coffee pump switching and steam pump switching", "owner": "main"},
    {"name": "Two-way valve switching and three-way valve switching", "owner": "main"},
    {"name": "Supply-timing front end", "owner": "main"},
    {"name": "Coffee, steam and wand temperature sensing", "owner": "main"},
    {"name": "Flow sensing", "owner": "main"},
    {"name": "Steam-path pressure sensing", "owner": "steam path"},
    {"name": "Gauge drive, both gauges", "owner": "main"},
    {"name": "Heater mains-presence confirm", "owner": "wall"},
    {"name": "Low-water indication, visual", "owner": "main"},
    {"name": "Operator panel: keys, indicators, buzzer", "owner": "main"},
    {"name": "Low-voltage supply (the logic supply)", "owner": "main"},
    {
      "name": "Wiring, connectors, mains-rated terminals",
      "owner": "main and wall",
      "split": "each board carries the connectors of the harnesses that reach it"
    },
    {"name": "Proof-of-life interlock", "owner": "main"},
    {"name": "Mains entry protection", "owner": "main"}
  ],
  "extra_channels": ["Tank level (the reed element)", "Control-knob microswitch inputs"],
  "harnesses": [
    {"source": "Front panel button and indicator board", "connector": "CON2"},
    {"source": "Gauge and water-indicator board", "connector": "SP2"},
    {"source": "Knob microswitches", "connector": "KNOB"},
    {"source": "Flow meter", "connector": "FLOW"},
    {"source": "Temperature sensors", "connector": "TEMP_C TEMP_S TEMP_W"},
    {"source": "The nine terminals", "connector": "tabs 1 to 9"}
  ],
  "wall": {
    "size": [57.0, 42.5],
    "bracket": {
      "lift": 5.0,
      "window_l": 80.0,
      "board_leg_u": [-15.0, 72.0],
      "leg_v": [0.0, 5.0],
      "top_z": 35.0,
      "bolts": [-2.5, 59.5],
      "bolt_end": 5.0,
      "mounts": [[-12.5, 4.0], [69.5, 4.0]],
      "ears": [[-16.0, 0.0, 0.0, 7.5], [57.0, 0.0, 73.0, 7.5]],
      "board_t": 1.6,
      "lead_behind": [6.4, 8.4],
      "driver": 6.0
    },
    "blocks": [
      {
        "id": "OUT_S",
        "fn": "Steam element out: 6.3 mm blade terminal, wire from the in-line blade joiner of the steam element lead",
        "body": [1.0, 5.0, 8.0, 12.0],
        "mains": [["OUT_S", [1.0, 5.0, 8.0, 12.0], "S"]],
        "pockets": [],
        "fit": [["terminal", 2]]
      },
      {
        "id": "TRI_S",
        "fn": "Steam triac BTA16-600BRG, insulated TO-220AB, straight leads, tab bolted to the bracket's leg",
        "body": [11.0, 5.0, 21.4, 10.5],
        "mains": [],
        "pockets": [],
        "fit": [["triac", 3]]
      },
      {"id": "TRI_C", "fn": "Coffee triac", "body": [35.6, 5.0, 46.0, 10.5], "mains": [], "pockets": [], "fit": [["triac", 3]]},
      {
        "id": "OUT_C",
        "fn": "Coffee element out: blade terminal, wire from the in-line blade joiner of the coffee element lead",
        "body": [49.0, 5.0, 56.0, 12.0],
        "mains": [["OUT_C", [49.0, 5.0, 56.0, 12.0], "C"]],
        "pockets": [],
        "fit": [["terminal", 2]]
      },
      {
        "id": "MOV_S",
        "fn": "Steam varistor across the triac",
        "body": [1.0, 17.0, 11.0, 23.0],
        "mains": [["MOV_S.a", [1.0, 17.0, 3.5, 23.0], "S"], ["MOV_S.b", [8.5, 17.0, 11.0, 23.0], "R"]],
        "pockets": [],
        "fit": [["varistor", 2]]
      },
      {
        "id": "MOV_C",
        "fn": "Coffee varistor across the triac",
        "body": [46.0, 17.0, 56.0, 23.0],
        "mains": [["MOV_C.a", [53.5, 17.0, 56.0, 23.0], "C"], ["MOV_C.b", [46.0, 17.0, 48.5, 23.0], "R"]],
        "pockets": [],
        "fit": [["varistor", 2]]
      },
      {
        "id": "OPTO_S",
        "fn": "Steam zero-cross opto-triac MOC3083, DIP-6, rows along u",
        "body": [1.0, 30.5, 11.0, 41.5],
        "mains": [["OPTO_S.m", [1.0, 30.5, 11.0, 34.0], "OPTO_S"]],
        "pockets": [["OPTO_S.l", [1.0, 38.0, 11.0, 41.5]]],
        "fit": [["opto_triac", 6], ["gate_resistor", 4]],
        "dip": {"centre": [6.0, 36.0], "row": 3.81, "pin_dy": 2.54, "pins": 3, "axis": "u", "slot": "WS_STEAM"}
      },
      {
        "id": "OPTO_C",
        "fn": "Coffee zero-cross opto-triac",
        "body": [46.0, 30.5, 56.0, 41.5],
        "mains": [["OPTO_C.m", [46.0, 30.5, 56.0, 34.0], "OPTO_C"]],
        "pockets": [["OPTO_C.l", [46.0, 38.0, 56.0, 41.5]]],
        "fit": [["opto_triac", 6], ["gate_resistor", 4]],
        "dip": {"centre": [51.0, 36.0], "row": 3.81, "pin_dy": 2.54, "pins": 3, "axis": "u", "slot": "WS_COFFEE"}
      }
    ],
    "lv": [
      {
        "id": "WB3",
        "fn": "Low-voltage cable header, 3 ways, 2.54 mm",
        "rect": [21.0, 32.0, 35.6, 39.5],
        "conn": {"ways": 3, "pitch": 2.54},
        "fit": [["header", "ways"]]
      }
    ],
    "copper": [
      {"id": "S1s", "rect": [8.0, 5.0, 13.7, 12.0], "net": "S"},
      {"id": "S2", "rect": [18.7, 5.0, 25.0, 12.0], "net": "R"},
      {"id": "S3", "rect": [32.0, 5.0, 38.3, 12.0], "net": "R"},
      {"id": "S1c", "rect": [43.3, 5.0, 49.0, 12.0], "net": "C"},
      {"id": "RC", "rect": [25.0, 5.0, 32.0, 12.0], "net": "R"},
      {"id": "RET", "rect": [25.0, 12.0, 32.0, 19.0], "net": "R", "fit": [["terminal", 2]]}
    ],
    "slots": [{"id": "WS_STEAM", "rect": [0.0, 35.5, 13.0, 36.5]}, {"id": "WS_COFFEE", "rect": [44.0, 35.5, 57.0, 36.5]}],
    "sheet_mohm": 0.491,
    "axes": {"S1s": "u", "S2": "u", "S3": "u", "S1c": "u", "RC": "v", "RET": "v"},
    "chains": {"steam": ["S1s", "TRI_S", "S2", "RC", "RET"], "coffee": ["S1c", "TRI_C", "S3", "RC", "RET"]},
    "table_keys": [["S1", "S1s"], ["S2", "S2"], ["S3", "S3"], ["RC", "RC"], ["RET", "RET"]],
    "budgets": {"relay_contact_w": 0.5, "sensor_mohm": 1.0, "relay_coil_w": 0.4},
    "heat": {"triacs": {"TRI_S": 4.84, "TRI_C": 4.25}, "thermal": {"rth_jc": 2.1, "tj_max": 125.0}, "opto": ["OPTO_S", "OPTO_C"]}
  },
  "wall_dnp": {
    "size": [57.0, 52.5],
    "bracket": {
      "lift": 5.0,
      "window_l": 80.0,
      "board_leg_u": [-15.0, 72.0],
      "leg_v": [0.0, 5.0],
      "top_z": 35.0,
      "bolts": [-2.5, 59.5],
      "bolt_end": 5.0,
      "mounts": [[-12.5, 4.0], [69.5, 4.0]],
      "ears": [[-16.0, 0.0, 0.0, 7.5], [57.0, 0.0, 73.0, 7.5]],
      "board_t": 1.6,
      "lead_behind": [6.4, 8.4],
      "driver": 6.0
    },
    "blocks": [
      {
        "id": "OUT_S",
        "fn": "Steam element out: 6.3 mm blade terminal, wire from the in-line blade joiner of the steam element lead",
        "body": [1.0, 5.0, 8.0, 12.0],
        "mains": [["OUT_S", [1.0, 5.0, 8.0, 12.0], "S"]],
        "pockets": [],
        "fit": [["terminal", 2]]
      },
      {
        "id": "TRI_S",
        "fn": "Steam triac BTA16-600BRG, insulated TO-220AB, straight leads, tab bolted to the bracket's leg",
        "body": [11.0, 5.0, 21.4, 10.5],
        "mains": [],
        "pockets": [],
        "fit": [["triac", 3]]
      },
      {"id": "TRI_C", "fn": "Coffee triac", "body": [35.6, 5.0, 46.0, 10.5], "mains": [], "pockets": [], "fit": [["triac", 3]]},
      {
        "id": "OUT_C",
        "fn": "Coffee element out: blade terminal, wire from the in-line blade joiner of the coffee element lead",
        "body": [49.0, 5.0, 56.0, 12.0],
        "mains": [["OUT_C", [49.0, 5.0, 56.0, 12.0], "C"]],
        "pockets": [],
        "fit": [["terminal", 2]]
      },
      {
        "id": "MOV_S",
        "fn": "Steam varistor across the triac",
        "body": [1.0, 17.0, 11.0, 23.0],
        "mains": [["MOV_S.a", [1.0, 17.0, 3.5, 23.0], "S"], ["MOV_S.b", [8.5, 17.0, 11.0, 23.0], "R"]],
        "pockets": [],
        "fit": [["varistor", 2]]
      },
      {
        "id": "MOV_C",
        "fn": "Coffee varistor across the triac",
        "body": [46.0, 17.0, 56.0, 23.0],
        "mains": [["MOV_C.a", [53.5, 17.0, 56.0, 23.0], "C"], ["MOV_C.b", [46.0, 17.0, 48.5, 23.0], "R"]],
        "pockets": [],
        "fit": [["varistor", 2]]
      },
      {
        "id": "OPTO_S",
        "fn": "Steam zero-cross opto-triac MOC3083, DIP-6, rows along u",
        "body": [1.0, 30.5, 11.0, 41.5],
        "mains": [["OPTO_S.m", [1.0, 30.5, 11.0, 34.0], "OPTO_S"]],
        "pockets": [["OPTO_S.l", [1.0, 38.0, 11.0, 41.5]]],
        "fit": [["opto_triac", 6], ["gate_resistor", 4]],
        "dip": {"centre": [6.0, 36.0], "row": 3.81, "pin_dy": 2.54, "pins": 3, "axis": "u", "slot": "WS_L"}
      },
      {
        "id": "OPTO_C",
        "fn": "Coffee zero-cross opto-triac",
        "body": [46.0, 30.5, 56.0, 41.5],
        "mains": [["OPTO_C.m", [46.0, 30.5, 56.0, 34.0], "OPTO_C"]],
        "pockets": [["OPTO_C.l", [46.0, 38.0, 56.0, 41.5]]],
        "fit": [["opto_triac", 6], ["gate_resistor", 4]],
        "dip": {"centre": [51.0, 36.0], "row": 3.81, "pin_dy": 2.54, "pins": 3, "axis": "u", "slot": "WS_R"}
      },
      {
        "id": "PRES_S",
        "fn": "Steam mains-presence confirm place, not populated: AC-input optocoupler and its 120 kOhm 1 W resistor",
        "body": [16.0, 30.5, 26.0, 41.5],
        "mains": [["PRES_S.m", [16.0, 30.5, 26.0, 34.0], "PRES_S"]],
        "pockets": [["PRES_S.l", [16.0, 38.0, 26.0, 41.5]]],
        "fit": [],
        "dip": {"centre": [21.0, 36.0], "row": 3.81, "pin_dy": 1.27, "pins": 2, "axis": "u", "slot": "WS_L"},
        "dnp": [["confirm_opto", 4], ["confirm_resistor", 2]]
      },
      {
        "id": "PRES_C",
        "fn": "Coffee mains-presence confirm place, not populated",
        "body": [31.0, 30.5, 41.0, 41.5],
        "mains": [["PRES_C.m", [31.0, 30.5, 41.0, 34.0], "PRES_C"]],
        "pockets": [["PRES_C.l", [31.0, 38.0, 41.0, 41.5]]],
        "fit": [],
        "dip": {"centre": [36.0, 36.0], "row": 3.81, "pin_dy": 1.27, "pins": 2, "axis": "u", "slot": "WS_R"},
        "dnp": [["confirm_opto", 4], ["confirm_resistor", 2]]
      }
    ],
    "lv": [
      {
        "id": "WB6",
        "fn": "Low-voltage cable header, 6 ways, 2.54 mm",
        "rect": [17.0, 44.0, 39.2, 51.5],
        "conn": {"ways": 6, "pitch": 2.54},
        "fit": [["header", "ways"]]
      }
    ],
    "copper": [
      {"id": "S1s", "rect": [8.0, 5.0, 13.7, 12.0], "net": "S"},
      {"id": "S2", "rect": [18.7, 5.0, 25.0, 12.0], "net": "R"},
      {"id": "S3", "rect": [32.0, 5.0, 38.3, 12.0], "net": "R"},
      {"id": "S1c", "rect": [43.3, 5.0, 49.0, 12.0], "net": "C"},
      {"id": "RC", "rect": [25.0, 5.0, 32.0, 12.0], "net": "R"},
      {"id": "RET", "rect": [25.0, 12.0, 32.0, 19.0], "net": "R", "fit": [["terminal", 2]]}
    ],
    "slots": [
      {"id": "WS_L", "rect": [0.0, 35.5, 29.0, 36.5]},
      {"id": "WS_M", "rect": [28.5, 29.0, 29.5, 43.5]},
      {"id": "WS_R", "rect": [29.0, 35.5, 57.0, 36.5]}
    ],
    "sheet_mohm": 0.491,
    "axes": {"S1s": "u", "S2": "u", "S3": "u", "S1c": "u", "RC": "v", "RET": "v"},
    "chains": {"steam": ["S1s", "TRI_S", "S2", "RC", "RET"], "coffee": ["S1c", "TRI_C", "S3", "RC", "RET"]},
    "table_keys": [["S1", "S1s"], ["S2", "S2"], ["S3", "S3"], ["RC", "RC"], ["RET", "RET"]],
    "budgets": {"relay_contact_w": 0.5, "sensor_mohm": 1.0, "relay_coil_w": 0.4},
    "heat": {"triacs": {"TRI_S": 4.84, "TRI_C": 4.25}, "thermal": {"rth_jc": 2.1, "tj_max": 125.0}, "opto": ["OPTO_S", "OPTO_C", "PRES_S", "PRES_C"]}
  },
  "cost": {
    "fee": {
      "eng2": 4.0,
      "eng4": 25.0,
      "slope2": 5.2,
      "slope4": 6.6,
      "ref_area": 10609.0,
      "band2": 4.0,
      "band4": 8.0,
      "boards": 5,
      "band": 102.0,
      "setup": 8.18,
      "stencil": 1.53,
      "labour": 3.58,
      "joint_hand": 0.0164,
      "joint_machine": 0.0016,
      "ext_econ": 3.07,
      "ext_std": 1.53,
      "setup_std": 25.56,
      "stencil_std": 8.21,
      "fixtures_std": 16.42
    },
    "A": {"boards": [{"name": "one board", "layers": 4, "w": 131.0, "h": 125.0}], "orders": 1, "dup_ext": 0, "links": 0},
    "B": {
      "boards": [
        {"name": "mains board", "layers": 2, "w": 69.0, "h": 125.0, "bay": [15.0, 27.0], "bay_sign": 1},
        {"name": "low-voltage board", "layers": 4, "w": 59.0, "h": 125.0, "bay": [15.0, 27.0], "bay_sign": -1}
      ],
      "orders": 2,
      "dup_ext": 1,
      "links": 1
    },
    "C": {
      "boards": [
        {"name": "mains board", "layers": 2, "w": 69.0, "h": 125.0, "bay": [15.0, 27.0], "bay_sign": 1},
        {"name": "controller board", "layers": 4, "area": 3600.0, "w": 60.0, "h": 60.0},
        {"name": "front-end board", "layers": 2, "area": 3000.0, "w": 50.0, "h": 60.0}
      ],
      "orders": 3,
      "dup_ext": 2,
      "links": 2
    },
    "link_parts": 0.684,
    "link_joints": 40
  },
  "parts": {
    "main": [
      {"n": "STM32H743VIT6", "id": "C114409", "cls": "Extended", "tht": false, "tag": "mcu"},
      {"n": "Logic-supply module IRM-20-5", "id": "C6280121", "cls": "Extended", "tht": true, "tag": "module"},
      {"n": "Pump opto-triac MOC3052M", "id": "C8965", "cls": "Extended", "tht": true, "tag": "pump_opto"},
      {"n": "Pump triac BTA204S-600B", "id": "C256462", "cls": "Extended", "tht": false, "tag": "pump_triac"},
      {"n": "Interlock relay HF115F-Q/005-1H, 5 V coil (catalogue number not recorded; priced and classed as the 12 V variant C5318991)", "id": "", "cls": "Extended", "tht": true, "tag": "k_il"},
      {"n": "Valve relay HF32FA-G/005-HSL1", "id": "C91370", "cls": "Extended", "tht": true, "tag": "valve_relay"},
      {"n": "AC-input optocoupler LTV-814S", "id": "C108051", "cls": "Extended", "tht": false, "tag": "ac_opto"},
      {"n": "Fuse holder 5 x 20 mm", "id": "C3131", "cls": "Extended", "tht": true, "tag": "holder"},
      {"n": "Fuse clip", "id": "C3130", "cls": "Extended", "tht": true, "tag": "clip"},
      {"n": "6.3 mm tab, board-mounted", "id": "C20626104", "cls": "Extended", "tht": true, "tag": "tab"},
      {"n": "Shunt resistor, 2512, 1 mohm class (not chosen)", "id": "", "cls": "Extended", "tht": false, "tag": "shunt"},
      {"n": "Mains-sense resistor 120 kohm, 2512", "id": "C5126146", "cls": "Extended", "tht": false, "tag": "sense_res"}
    ],
    "wall": [
      {"n": "Triac BTA16-600BRG", "id": "C9100", "cls": "Extended", "tags": ["triac"]},
      {"n": "Opto-triac MOC3083", "id": "C10797", "cls": "Extended", "tags": ["opto_triac"]},
      {"n": "6.3 mm tab, board-mounted (the main board's part)", "id": "C20626104", "cls": "Extended", "tags": ["terminal"]},
      {"n": "Header, 3 ways, 2.54 mm", "id": "", "cls": "Extended", "tags": ["header"]},
      {"n": "Varistor 07D471K", "id": "C49072860", "cls": "Extended", "tags": ["varistor"]},
      {"n": "Gate resistors", "id": "", "cls": "Basic", "tags": ["gate_resistor"]}
    ]
  },
  "pump_drive": {"rating_a_ms": 6.0, "mains_hz": 50.0},
  "valve_relay": {
    "part": "HF32FA-G/005-HSL1",
    "jlc": "C91370",
    "body": [17.6, 10.1, 12.7],
    "coil_ohm": 108.0,
    "rating_a": 10.0,
    "max_v": 250.0,
    "span_top": 253.0,
    "peak": 358.0,
    "open_contact_vac": 1000.0,
    "coil_contact_vac": 5000.0,
    "target_kv": 4.0,
    "price": 1.6115,
    "k_il_price": 3.2119,
    "count": 2,
    "coil_tol": 0.1,
    "rise_k": 61.0,
    "ambient_c": 85.0,
    "insulation_c": 155.0
  },
  "rail": {
    "volts": 5.0,
    "controller_ma": 439.0,
    "controller_typ_ma": 226.0,
    "gauge": {"phases": 4, "phase_ma": 18.0},
    "hx711_ma": 1.5,
    "hx711_count": 2,
    "assumed": {
      "opto_led_ma": 15.0,
      "opto_leds": 4,
      "panel_ma": 60.0,
      "flow_ma": 15.0,
      "pressure_ma": 10.0,
      "pressure_count": 2,
      "probe_ma": 2.0,
      "probe_count": 2,
      "sense_ma": 10.0,
      "sense_count": 3,
      "loadcell_ohm": 350.0,
      "loadcell_count": 2,
      "vm_out_ma": 5.0,
      "misc_ma": 10.0
    },
    "modules": [
      {"name": "IRM-20-5", "amps": 4.0, "at70": 0.5, "at50": 0.9, "w": 52.4, "d": 27.2, "h": 24.0, "eff": 0.79, "chosen": true, "no_load_w": 0.1},
      {"name": "IRM-10-5", "amps": 2.0, "at70": 0.5, "at50": 1.0, "w": 45.7, "d": 25.4, "h": 21.5, "eff": 0.77}
    ],
    "adequate": 2.0
  },
  "fuse": {
    "holder": [24.0, 9.0],
    "holders": 3,
    "share_limit_a": 1.0,
    "required_a": 6000.0,
    "options": [{"name": "5 x 20 glass time-lag", "break_a": 35.0}, {"name": "5.2 x 20 ceramic time-lag", "break_a": 1500.0}]
  },
  "what_if": [
    {
      "name": "with the module at its lowest, the voltage measurement above it and K_V1 between the sources",
      "mains_blocks": {
        "VMEAS": {
          "body": [32.5, 75.6, 70.0, 80.6],
          "mains": [["VMEAS.L", [32.5, 75.6, 43.5, 80.6], "LINE"], ["VMEAS.N", [50.0, 75.6, 60.0, 80.6], "NEUTRAL"]],
          "pockets": [[65.0, 75.6, 70.0, 80.6]],
          "dip": {"centre": [62.5, 78.1], "row": 3.81, "pin_dy": 2.54, "pins": 3},
          "hot": [58.0, 75.6, 68.0, 80.6]
        },
        "MODULE": {
          "body": [32.5, 48.4, 84.9, 75.6],
          "mains": [["MODULE.n", [32.9, 48.6, 38.9, 54.6], "NEUTRAL"], ["MODULE.l", [32.9, 69.4, 38.9, 75.4], "LINE"]],
          "pockets": [[76.5, 48.9, 84.9, 62.9]],
          "pins": [[35.9, 51.6], [35.9, 72.4], [80.9, 51.6], [80.9, 59.6]]
        },
        "K_V1": {
          "body": [44.5, 38.3, 62.1, 48.4],
          "mains": [["K_V1", [44.5, 38.925, 47.26, 47.775], "COFVALVE"]],
          "pockets": [[58.9, 38.3, 62.1, 48.4]],
          "pins": [[60.7, 39.55], [60.7, 47.15], [45.46, 40.175], [45.46, 46.525]]
        }
      },
      "lv_blocks": {
        "MCU": {"rect": [72.0, 92.3, 105.0, 125.3]},
        "DRV_K1": {"rect": [65.5, 38.3, 72.0, 48.4]},
        "FE_GAUGE": {"rect": [72.0, 79.8, 93.5, 91.8]},
        "POL": {"rect": [72.5, 31.0, 84.3, 43.0]},
        "FE_KNOB": {"rect": [84.4, 39.1, 93.5, 44.4]}
      },
      "slots": [
        {"id": "SL_LINK", "rect": [1.0, 26.55, 31.0, 27.55]},
        {"id": "SL_LN", "rect": [1.0, 35.3, 16.5, 36.3]},
        {"id": "SL_TIM", "rect": [57.3, 2.0, 58.3, 12.5]},
        {"id": "SL_VP", "rect": [36.0, 91.1, 67.5, 92.1]},
        {"id": "SL_PP", "rect": [17.0, 103.1, 57.5, 104.1]},
        {"id": "SL_PV", "rect": [36.0, 115.1, 67.5, 116.1]},
        {"id": "SL_PUMPS", "rect": [57.5, 91.1, 58.5, 116.1]},
        {"id": "SL_VM", "rect": [62.0, 70.6, 63.0, 85.6]},
        {"id": "SL_VMH", "rect": [36.0, 35.3, 69.0, 36.3]}
      ],
      "heat": {"accepted": [["K_V1", "MODULE"], ["K_V1", "K_IL"], ["VMEAS", "MODULE"]]}
    },
    {
      "name": "with the module where it stood, K_V1 and the shared fuse in the gap between the sources and the voltage measurement above the module",
      "mains_blocks": {
        "VFUSE": {"body": [17.0, 37.9, 41.0, 46.9], "mains": [["VFUSE.n", [17.0, 37.9, 22.0, 46.9], "NEUTRAL"], ["VFUSE.v", [36.0, 37.9, 41.0, 46.9], "VFUSE"]]},
        "VMEAS": {
          "body": [32.5, 77.3, 70.0, 82.3],
          "mains": [["VMEAS.L", [32.5, 77.3, 43.5, 82.3], "LINE"], ["VMEAS.N", [50.0, 77.3, 60.0, 82.3], "NEUTRAL"]],
          "pockets": [[65.0, 77.3, 70.0, 82.3]],
          "dip": {"centre": [62.5, 79.8], "row": 3.81, "pin_dy": 2.54, "pins": 3},
          "hot": [58.0, 77.3, 68.0, 82.3]
        },
        "MODULE": {
          "body": [32.5, 50.1, 84.9, 77.3],
          "mains": [["MODULE.n", [32.9, 50.3, 38.9, 56.3], "NEUTRAL"], ["MODULE.l", [32.9, 71.1, 38.9, 77.1], "LINE"]],
          "pockets": [[76.5, 50.6, 84.9, 64.6]],
          "pins": [[35.9, 53.3], [35.9, 74.1], [80.9, 53.3], [80.9, 61.3]]
        },
        "K_V1": {
          "body": [44.5, 40.0, 62.1, 50.1],
          "mains": [["K_V1", [44.5, 40.625, 47.26, 49.475], "COFVALVE"]],
          "pockets": [[58.9, 40.0, 62.1, 50.1]],
          "pins": [[60.7, 41.25], [60.7, 48.85], [45.46, 41.875], [45.46, 48.225]]
        }
      },
      "lv_blocks": {
        "MCU": {"rect": [72.0, 92.3, 105.0, 125.3]},
        "DRV_K1": {"rect": [65.5, 40.0, 72.0, 50.1]},
        "FE_GAUGE": {"rect": [72.0, 79.8, 93.5, 91.8]},
        "POL": {"rect": [72.5, 31.0, 84.5, 43.0]},
        "FE_KNOB": {"rect": [72.5, 43.5, 80.5, 49.5]}
      },
      "slots": [
        {"id": "SL_LINK", "rect": [1.0, 26.55, 31.0, 27.55]},
        {"id": "SL_LN", "rect": [1.0, 35.3, 60.0, 36.3]},
        {"id": "SL_VF", "rect": [42.4, 37.0, 43.4, 51.0]},
        {"id": "SL_VN", "rect": [25.0, 47.9, 42.4, 48.9]},
        {"id": "SL_TIM", "rect": [57.3, 2.0, 58.3, 12.5]},
        {"id": "SL_VM", "rect": [62.0, 72.3, 63.0, 87.3]},
        {"id": "SL_PP", "rect": [17.0, 103.1, 57.5, 104.1]},
        {"id": "SL_PV", "rect": [36.0, 115.1, 67.5, 116.1]},
        {"id": "SL_PUMPS", "rect": [57.5, 91.1, 58.5, 116.1]}
      ],
      "heat": {"accepted": [["K_V1", "MODULE"], ["K_V1", "K_IL"], ["VMEAS", "MODULE"]]}
    },
    {
      "name": "with the module lowered 3.3 mm to the lowest the sensing blocks allow and the voltage measurement 11.7 mm from the interlock relay, in the gap the module left",
      "mains_blocks": {
        "VMEAS": {
          "body": [32.5, 45.1, 70.0, 50.1],
          "mains": [["VMEAS.N", [32.5, 45.1, 43.5, 50.1], "NEUTRAL"], ["VMEAS.L", [50.0, 45.1, 60.0, 50.1], "LINE"]],
          "pockets": [[65.0, 45.1, 70.0, 50.1]],
          "dip": {"centre": [62.5, 47.6], "row": 3.81, "pin_dy": 2.54, "pins": 3},
          "hot": [58.0, 45.1, 68.0, 50.1]
        },
        "MODULE": {
          "body": [32.5, 50.1, 84.9, 77.3],
          "mains": [["MODULE.n", [32.9, 50.3, 38.9, 56.3], "NEUTRAL"], ["MODULE.l", [32.9, 71.1, 38.9, 77.1], "LINE"]],
          "pockets": [[76.5, 50.6, 84.9, 64.6]],
          "pins": [[35.9, 53.3], [35.9, 74.1], [80.9, 53.3], [80.9, 61.3]]
        }
      },
      "lv_blocks": {},
      "slots": [
        {"id": "SL_LINK", "rect": [1.0, 26.55, 31.0, 27.55]},
        {"id": "SL_LN", "rect": [1.0, 35.3, 16.5, 36.3]},
        {"id": "SL_TIM", "rect": [57.3, 2.0, 58.3, 12.5]},
        {"id": "SL_VM", "rect": [62.0, 40.1, 63.0, 55.1]},
        {"id": "SL_VP", "rect": [36.0, 91.1, 67.5, 92.1]},
        {"id": "SL_PP", "rect": [17.0, 103.1, 57.5, 104.1]},
        {"id": "SL_PV", "rect": [36.0, 115.1, 67.5, 116.1]},
        {"id": "SL_PUMPS", "rect": [57.5, 91.1, 58.5, 116.1]}
      ],
      "heat": {"accepted": [["K_V1", "MODULE"], ["VMEAS", "MODULE"], ["VMEAS", "K_IL"]], "required_held": []}
    }
  ]
}
```

### The script

```python
"""Consistency checks for controller-board-division.md.

    python3 -I checks.py RECORD main          main board, functions, harnesses, kinds and costs
    python3 -I checks.py RECORD wall          heater wall board
    python3 -I checks.py RECORD --tables      print the cells the record's tables are generated from, and report each that differs
    python3 -I checks.py RECORD --selftest    perturb the data, the sources, the tokens and the record's own text and require each to be caught by the check it targets

RECORD is the path of the markdown record. The script re-derives the floorplan geometry, the wall cut's areas and the tables from its own floorplan-data block (the heat and tab-hole arithmetic of § The heater wall assembly, judged is in prose and is checked by hand), compares
the tables of the record with it, and compares what each command prints with the expected-output block beside the script. It does
not make the data right: a figure that has a source record (the separation basis, the nine tabs, the mounting holes and cavity, the
reed's position, the maker's limits, the load currents) is read from that record and compared, and the figures that have none are
the record's assumptions, each carrying a `name=value` token in its row of the Assumptions table that the data must equal. A change
made to both an assumption's row and the data passes; that is a prose change a reader sees. The forms record, the connector record,
the machine record, the constraints record, the maker's record and the basis are read from the folders the record is in.
"""
import copy, heapq, itertools, json, math, os, re, sys

EPS = 1e-9

# ---------------------------------------------------------------- reading the record
def blocks_of(text, label):
    return re.findall(r'^```' + re.escape(label) + r'\n(.*?)^```', text, re.S | re.M)

def load(path):
    text = open(path, encoding='utf-8').read()
    found = blocks_of(text, 'floorplan-data')
    if len(found) != 1:
        raise SystemExit('FAIL: the record must hold exactly one floorplan-data block, found %d' % len(found))
    return text, json.loads(found[0])

def section(text, title):
    """The text under the first heading that contains `title`, up to the next heading of the same or a higher level."""
    lines = text.split('\n')
    for i, ln in enumerate(lines):
        m = re.match(r'^(#+) (.*)$', ln)
        if m and title in m.group(2):
            out = []
            for ln2 in lines[i + 1:]:
                m2 = re.match(r'^(#+) ', ln2)
                if m2 and len(m2.group(1)) <= len(m.group(1)):
                    break
                out.append(ln2)
            return '\n'.join(out)
    return None

def table_rows(sec):
    rows = {}
    for ln in (sec or '').split('\n'):
        if not ln.startswith('|') or re.match(r'^\|[\s:|-]+\|$', ln):
            continue
        cells = [c.strip() for c in ln.strip().strip('|').split('|')]
        rows.setdefault(re.sub(r'[`*]', '', cells[0]), cells)
    return rows

PROSES = []

class Prose:
    """Cells the record's tables must hold, generated from the data. A row is found by its first cell: the key itself, or the
    key followed by a space or a comma."""

    def __init__(self, text, register=True):
        self.text, self.want, self.labels = text, [], {}
        if register:
            PROSES.append(self)

    def expect(self, heading, key, col, value, label=None):
        self.want.append((heading, key, col, value))
        if label:
            self.labels[(heading, key, col, value)] = label

    def mention(self, heading, value, label=None):
        """A figure the text of a section must state, outside any table: a cell with no row and no column."""
        self.want.append((heading, None, None, value))
        if label:
            self.labels[(heading, None, None, value)] = label

    def present(self, heading, phrase, what):
        """A statement of the record that the script requires word for word: if it is gone, a check names it."""
        self.mention(heading, phrase, 'required statement missing (%s)' % what)

    def counted(self, heading, value, what, key=None, col=None):
        """A figure the script counts from the blocks, which the text of the section (or the cell of a row) must state."""
        (self.mention(heading, value, 'counted figure not stated (%s)' % what) if key is None else self.expect(heading, key, col, value, 'counted figure not stated (%s)' % what))

    def check(self):
        bad, cache = [], {}
        for w in self.want:
            heading, key, col, value = w
            label = self.labels.get(w)
            if key is None:
                body = re.sub(r'[`*]', '', section(self.text, heading) or '')
                if value not in body:
                    bad.append(('%s: "%s" lacks %s' % (label, heading, value)) if label else 'table in "%s": the text lacks %s' % (heading, value))
                continue
            rows = cache.setdefault(heading, table_rows(section(self.text, heading)))
            hit = [k for k in rows if k == key or k.startswith(key + ' ') or k.startswith(key + ',')]
            if not hit:
                bad.append(('%s: "%s" has no row %s' % (label, heading, key)) if label else 'table in "%s" has no row %s' % (heading, key))
            elif col >= len(rows[hit[0]]) or value not in re.sub(r'[`*]', '', rows[hit[0]][col]):
                bad.append(('%s: "%s", row %s, column %d lacks %s' % (label, heading, key, col + 1, value)) if label else 'table in "%s", row %s, column %d lacks %s' % (heading, key, col + 1, value))
        return bad

# ---------------------------------------------------------------- the sources the figures are read from
SOURCE_FILES = (
    ('basis', ('..', '..', 'hardware', 'sunbeam-em7000', 'separation-basis.yaml')),
    ('pinouts', ('connector-pinouts.md',)),
    ('machine', ('reference-machine.md',)),
    ('forms', ('controller-board-function-forms.md',)),
    ('constraints', ('controller-board-design-constraints.md',)),
    ('maker', ('..', 'board-manufacturer-jlcpcb.md')),
    ('cost', ('controller-board-cost-estimate.md',)),
)

def source_texts(record_dir):
    return {k: open(os.path.join(record_dir, *p), encoding='utf-8').read() for k, p in SOURCE_FILES}

def num(s):
    return float(s)

def parse_sources(texts):
    """The figures of the source records this record's data must equal. Every lookup is by the row's own words; a row that is
    missing or does not parse is a failure, never a default."""
    src, bad = {}, []

    def need(key, pattern, text, flags=0, what=None):
        m = re.search(pattern, text, flags)
        if not m:
            bad.append('source: %s not found' % (what or key))
            return None
        return m

    m = need('basis', r'^mains_to_low_voltage:\s*\n\s+clearance_mm:\s*([0-9.]+)\s*\n\s+creepage_mm:\s*([0-9.]+)', texts['basis'], re.M, 'the separation basis row mains_to_low_voltage')
    if m:
        src['clearance'], src['creepage'] = num(m.group(1)), num(m.group(2))
    m = need('basic', r'([0-9.]+) mm basic, doubled to ([0-9.]+) mm for reinforced', texts['basis'], 0, 'the separation basis creepage row (basic, doubled for reinforced)')
    if m:
        src['basic'] = num(m.group(1))
        if 'creepage' in src and (abs(2 * src['basic'] - num(m.group(2))) > EPS or abs(num(m.group(2)) - src['creepage']) > EPS):
            bad.append('source: the basis creepage row is not the basic figure doubled')

    m = need('mains_to_mains', r'^mains_to_mains:\s*\n\s+clearance_mm:\s*([0-9.]+)\s*\n\s+terminal_clearance_mm:\s*([0-9.]+)\s*\n\s+creepage_mm:\s*([0-9.]+)\s*\n\s+creepage_ahead_of_fuse_mm:\s*([0-9.]+)', texts['basis'], re.M, 'the separation basis row mains_to_mains')
    if m:
        src['m_clearance'], src['m_terminal'], src['m_creepage'], src['m_ahead'] = (num(m.group(i)) for i in (1, 2, 3, 4))

    tabs = {}
    for ln in (section(texts['pinouts'], 'The nine terminals') or '').split('\n'):
        cells = [c.strip() for c in ln.strip().strip('|').split('|')]
        if ln.startswith('|') and len(cells) >= 5 and cells[0].isdigit():
            ym = re.fullmatch(r'([0-9.]+) mm', cells[4])
            if ym:
                tabs[int(cells[0])] = (cells[1].strip('`'), num(ym.group(1)))
    if sorted(tabs) != list(range(1, 10)):
        bad.append('source: the connector record\'s nine terminals did not parse (found %s)' % sorted(tabs))
    src['tabs'] = tabs
    for what, pattern in (('LINE1 as a pass-through', r'nothing else on the board connects to `LINE1`'),
                          ('LINE1 daisy-chained to every load', r'`LINE1`, the active, daisy-chains to one side of every pump, valve and thermoblock element'),
                          ('the neutral side of every load switched', r'the original board switches the neutral side of every load')):
        if not re.search(pattern, texts['pinouts']):
            bad.append('source: the connector record no longer says %s' % what)
    m = need('slack', r'fit need of about ([0-9.]+) mm', texts['pinouts'], 0, 'the owner\'s fit need of the tab slack')
    if m:
        src['slack'] = num(m.group(1))
    m = need('tab_height', r'stands \*\*([0-9.]+) mm clear of the board\*\*|stands ([0-9.]+) mm clear of the board', texts['pinouts'], 0, 'the tabs\' height')
    if m:
        src['tab_height'] = num(m.group(1) or m.group(2))
    m = need('tab_width', r'\*\*([0-9.]+) mm ±0\.1 mm wide\*\*', texts['pinouts'], 0, 'the tab width')
    if m:
        src['tab_width'] = num(m.group(1))
    m = need('tab_thick', r'\*\*([0-9.]+) mm thick\*\*', texts['pinouts'], 0, 'the tab thickness')
    if m:
        src['tab_thick'] = num(m.group(1))

    machine = texts['machine']
    for key, pattern in (('cavity_w', r'^\| Inside length along X, wall to wall \| ([0-9.]+) mm \| ±([0-9.]+) mm'), ('cavity_h', r'^\| Inside width along Y, wall to wall \| ([0-9.]+) mm \| ±([0-9.]+) mm')):
        m = need(key, pattern, machine, re.M, 'the cavity row ' + key)
        if m:
            src[key] = (num(m.group(1)), num(m.group(2)))
    holes = {}
    for m in re.finditer(r'^\| ([1-4]) \| ([0-9.]+) mm \| ([0-9.]+) mm \| ([0-9.]+) mm \|', machine, re.M):
        holes[int(m.group(1))] = (num(m.group(2)), num(m.group(3)))
    if sorted(holes) != [1, 2, 3, 4]:
        bad.append('source: the machine record\'s four mounting points did not parse (found %s)' % sorted(holes))
    src['holes'] = holes
    m = need('reed', r'with its lower lead at X = ([0-9.]+) mm, Y = ([0-9.]+) mm in the datum[^.]*?upper lead ([0-9.]+) mm above that', machine, re.S, 'the reed\'s lead positions')
    if m:
        src['reed'] = (num(m.group(1)), num(m.group(2)), num(m.group(3)))
    m = need('intr', r'^\| 1 \| ([0-9.]+) mm, ([0-9.]+) mm \| ([0-9.]+) mm along X, then ([0-9.]+) mm of straight edge', machine, re.M, 'the row of intrusion 1')
    if m:
        src['intr1'] = tuple(num(m.group(i)) for i in range(1, 5))
    m = need('intr_tol', r'±([0-9.]+) mm in position and size', machine, 0, 'the intrusions\' position tolerance')
    if m:
        src['intr_tol'] = num(m.group(1))

    maker = texts['maker']
    for key, pattern, what in (('slot_min', r'^\| Minimum non-plated slot width \| ([0-9.]+) mm', 'the maker\'s least non-plated slot'),
                               ('slot_copper', r'^\| Copper to a routed board edge or routed slot \| ([0-9.]+) mm', 'the maker\'s copper to a routed slot'),
                               ('edge_min', r'^\| Traces and components to board edge, recommended \| More than ([0-9.]+) mm', 'the maker\'s components to the edge'),
                               ('band', r'^\| Board-size threshold of the lowest price band \| A single board within or equal to ([0-9.]+) × ([0-9.]+) mm', 'the maker\'s lowest band'),
                               ('ring_ml', r'^\| PTH annular ring \| ([0-9.]+) mm recommended, [0-9.]+ mm absolute minimum \| Multilayer boards, 1 oz', 'the maker\'s recommended annular ring on a multilayer board'),
                               ('track_tol', r'^\| Track width tolerance \| ±([0-9.]+) %', 'the maker\'s track width tolerance'),
                               ('slot_density', r'Slots 0\.8–1\.0 mm wide: [0-9.]+ USD per metre of slot path above ([0-9.]+) m per m²', 'the maker\'s slot-density charge')):
        m = need(key, pattern, maker, re.M, what)
        if m:
            src[key] = num(m.group(1))
    if 'track_tol' in src:
        src['track_tol'] /= 100.0

    sb = section(texts['constraints'], 'Supply budget') or ''
    loads = {}
    for key, pattern in (('coffee', r'\| Coffee thermoblock element \| ([0-9.]+) A'), ('steam', r'\| Steam thermoblock element \| ([0-9.]+) A'),
                         ('coffee_pump', r'\*\*([0-9.]+) A rms\*\* \(coffee pump\) and \*\*|\| ([0-9.]+) A rms \(coffee pump\) and'),
                         ('steam_pump', r'\(coffee pump\) and ([0-9.]+) A rms \(steam pump\)'),
                         ('coil_steady', r'At most ([0-9.]+) A rms steady together'), ('coil_inrush', r'inrush at most ([0-9.]+) A rms together'),
                         ('overload', r'[Aa]bout ([0-9]+) A for half an hour')):
        m = re.search(pattern, sb) or (re.search(pattern, texts['constraints']) if key == 'overload' else None)
        if not m:
            bad.append('source: the constraints record\'s supply budget has no %s figure' % key)
        else:
            loads[key] = num([g for g in m.groups() if g][0])
    src['loads'] = loads
    m = need('gauge', r'phase current lands near ([0-9.]+) mA', texts['pinouts'], 0, 'the gauge drivers\' phase current')
    if m:
        src['gauge_ma'] = num(m.group(1))
    cons = texts['constraints']
    m = need('span', r'^\| Supply voltage span \| ([0-9.]+)–([0-9.]+) V AC', cons, re.M, 'the constraints record\'s supply voltage span')
    if m:
        src['span_top'] = num(m.group(2))
    m = need('peak', r'^\| Peak working voltage \| ([0-9.]+) V \|', cons, re.M, 'the constraints record\'s peak working voltage')
    if m:
        src['peak'] = num(m.group(1))
    m = need('break', r'^\| Breaking capacity each fuse and breaker in the chain must have \| At least the prospective fault current, ([0-9.]+) kA', cons, re.M, 'the constraints record\'s breaking capacity')
    if m:
        src['breaking_a'] = num(m.group(1)) * 1000.0
    m = need('accept', r'\*\*Owner acceptance, ([0-9]{4}-[0-9]{2}-[0-9]{2}):\*\* a relay whose contacts are rated ([0-9.]+) V AC as their maximum switching voltage is accepted at the ([0-9.]+) V top of the span.{0,300}?on the owner\'s statement', cons, re.S, 'the owner\'s dated acceptance of a relay rated at its maximum switching voltage at the top of the span')
    if m:
        src['accepted_date'] = m.group(1)
        src['accepted_v'] = num(m.group(2))
        src['accepted_top'] = num(m.group(3))
    m = need('vprice', r'C91370, HF32FA-G/005-HSL1, Hongfa \(5 V coil\) \| [^|]*\| Extended \| ([0-9 ]+) \| ([0-9.]+) USD \(1–9\)', cons, 0, 'the constraints record\'s row for the HF32FA-G/005-HSL1')
    if m:
        src['valve_price'] = num(m.group(2))
    forms = texts['forms']
    m = need('triac_w', r'Coffee, [0-9.]+ A rms, [0-9.]+ A mean: [^*]*\*\*([0-9.]+) W\*\*\. Steam, [0-9.]+ A rms, [0-9.]+ A mean: [^*]*\*\*([0-9.]+) W\*\*', forms, 0, 'the forms record\'s dissipation of the heater triac at the element currents')
    if m:
        src['triac_w'] = (num(m.group(1)), num(m.group(2)))
    m = need('rth', r'Rth\(j-c\) ([0-9.]+) °C/W \(AC\), TO-220AB insulated; .{0,120}?Tj maximum ([0-9.]+) °C', forms, re.S, 'the forms record\'s junction-to-case resistance and junction limit of the heater triac')
    if m:
        src['rth_jc'], src['tj_max'] = num(m.group(1)), num(m.group(2))
    m = need('kprice', r'HF115F-Q/012-1H relay, count 2 \| C5318991 \| Extended \| ([0-9 ]+) \| ([0-9.]+) \(1–9\)', texts['forms'], 0, 'the forms record\'s row for the HF115F-Q')
    if m:
        src['relay_price'] = num(m.group(2))
    return src, bad

def check_sources(D, src):
    """The data against the figures read from the records."""
    bad = []
    def eq(what, a, b):
        if a is None or b is None or abs(a - b) > EPS:
            bad.append('%s is %s in the data and %s in its source' % (what, a, b))
    if 'clearance' in src:
        eq('the signed clearance', D['basis']['clearance'], src['clearance'])
        eq('the signed creepage', D['basis']['creepage'], src['creepage'])
    if 'm_clearance' in src:
        eq('the signed mains-to-mains clearance', D['basis']['m_clearance'], src['m_clearance'])
        eq('the signed mains-to-mains terminal clearance', D['basis']['m_terminal'], src['m_terminal'])
        eq('the signed mains-to-mains creepage', D['basis']['m_creepage'], src['m_creepage'])
        eq('the signed mains-to-mains creepage ahead of the entry fuse', D['basis']['m_creepage'], src['m_ahead'])
    if 'cavity_w' in src:
        eq('the cavity width', D['cavity']['w'], src['cavity_w'][0])
        eq('the cavity height', D['cavity']['h'], src['cavity_h'][0])
        eq('the cavity tolerance', D['cavity']['tol'], src['cavity_w'][1])
    tabs = src.get('tabs', {})
    seen = set()
    for x in D['tabs']['list']:
        n = x['n']
        seen.add(n)
        if n not in tabs:
            bad.append('tab %d is not in the connector record' % n)
            continue
        if x['name'] != tabs[n][0]:
            bad.append('tab %d is named %s in the data and %s in the connector record' % (n, x['name'], tabs[n][0]))
        eq('tab %d as found' % n, x['found'], tabs[n][1])
    for r in D['tabs'].get('removed', []):
        n = r['n']
        if n in seen:
            bad.append('tab %d is drawn in the data and is also listed as removed' % n)
        seen.add(n)
        if n not in tabs:
            bad.append('removed tab %d is not in the connector record' % n)
        elif r['name'] != tabs[n][0]:
            bad.append('removed tab %d is named %s in the data and %s in the connector record' % (n, r['name'], tabs[n][0]))
        else:
            eq('removed tab %d as found' % n, r['found'], tabs[n][1])
    bad += ['the connector record\'s tab %d is neither drawn nor listed as removed in the data' % n for n in tabs if n not in seen]
    if len(tabs) == 9:
        eq('the least as-found tab pitch', D['tabs']['pitch'], min(b[1] - a[1] for a, b in zip([tabs[n] for n in range(1, 9)], [tabs[n] for n in range(2, 10)])))
    for key, v in (('slack_estimate', 'slack'), ('height', 'tab_height')):
        if v in src:
            eq('the tabs\' ' + key, D['tabs'][key], src[v])
    if 'tab_width' in src:
        eq('the tab width', D['tabs']['blade'], src['tab_width'])
    if 'tab_thick' in src:
        eq('the tab thickness', D['tabs']['thick'], src['tab_thick'])
    if 'ring_ml' in src:
        if D['tabs']['ring'] < src['ring_ml'] - EPS:
            bad.append('the tab pad\'s annulus is %g mm, under the maker\'s recommended %g mm' % (D['tabs']['ring'], src['ring_ml']))
        eq('the maker\'s recommended annular ring', D['maker']['ring'], src['ring_ml'])
    if 'track_tol' in src:
        eq('the maker\'s track width tolerance', D['trace']['tol'], src['track_tol'])
    holes = src.get('holes', {})
    if len(holes) == 4:
        for name, n in (('P1', 1), ('P2', 2), ('P3', 3), ('P4', 4)):
            if tuple(D['holes'].get(name, ())) != holes[n]:
                bad.append('mounting hole %s is %s in the data and %s in the machine record' % (name, tuple(D['holes'].get(name, ())), holes[n]))
    if 'reed' in src:
        if tuple(D['reed']['recorded']) != src['reed'][:2]:
            bad.append('the reed\'s recorded lower lead is %s in the data and %s in the machine record' % (tuple(D['reed']['recorded']), src['reed'][:2]))
        eq('the reed\'s lead pitch', D['reed']['pitch'], src['reed'][2])
    if 'intr1' in src:
        i = D['intrusions']
        eq('intrusion 1 corner X', i['one_x0'], src['intr1'][0])
        eq('intrusion 1 length along X', i['one_x1'] - i['one_x0'], src['intr1'][2])
        eq('intrusion 1 straight edge', i['one_straight'], src['intr1'][3])
    if 'intr_tol' in src:
        eq('the intrusions\' position tolerance', D['intrusions']['pos_tol'], src['intr_tol'])
    for key, got in (('slot_min', D['slot_width_min']), ('slot_copper', D['slot_copper']), ('edge_min', D['basis']['edge_min']), ('band', D['basis']['band']), ('slot_density', D['slot_density'])):
        if key in src:
            eq('the maker\'s ' + key, got, src[key])
    vr = D['valve_relay']
    if 'span_top' in src:
        eq('the top of the supply span', vr['span_top'], src['span_top'])
    if 'peak' in src:
        eq('the peak working voltage', vr['peak'], src['peak'])
    if 'breaking_a' in src:
        eq('the breaking capacity a fuse must have', D['fuse']['required_a'], src['breaking_a'])
    if 'gauge_ma' in src:
        eq('the gauge drivers\' phase current', D['rail']['gauge']['phase_ma'], src['gauge_ma'])
    if 'accepted_v' in src:
        eq('the valve relay\'s maximum switching voltage, the figure the owner accepted', vr['max_v'], src['accepted_v'])
        eq('the top of the supply span the owner\'s acceptance names', vr['span_top'], src['accepted_top'])
    if 'valve_price' in src:
        eq('the valve relay\'s unit price', vr['price'], src['valve_price'])
    if 'relay_price' in src:
        eq('the unit price of the 12 V variant that stands for the 5 V interlock relay (its own price is not recorded)', vr['k_il_price'], src['relay_price'])
    wt = D['wall']['heat']
    if 'triac_w' in src:
        eq('the coffee triac\'s dissipation', wt['triacs'].get('TRI_C'), src['triac_w'][0])
        eq('the steam triac\'s dissipation', wt['triacs'].get('TRI_S'), src['triac_w'][1])
    if 'rth_jc' in src:
        eq('the triac\'s junction-to-case resistance', wt['thermal']['rth_jc'], src['rth_jc'])
        eq('the triac\'s junction limit', wt['thermal']['tj_max'], src['tj_max'])
    L = src.get('loads', {})
    cur = D['loads']
    for key in ('coffee', 'steam', 'coffee_pump', 'steam_pump', 'coil_steady', 'coil_inrush', 'overload'):
        if key in L:
            eq('the load current ' + key, cur[key], L[key])
    return bad

# ---------------------------------------------------------------- the assumptions' tokens
TOKENS = {
    'E': lambda D: D['fixing']['E'],
    'draw_tol': lambda D: D['fixing']['draw_tol'],
    'lid_keep': lambda D: D['fixing']['lid_keep'],
    'tab_ring': lambda D: D['tabs']['ring'],
    'trace_w': lambda D: D['trace']['w'],
    'reed_tol': lambda D: D['reed']['tol'],
    'hand_r': lambda D: D['reed']['hand_r'],
    'strip_w': lambda D: D['reed']['strip_w'],
    'heat_mcu': lambda D: D['heat']['limits']['mcu'],
    'heat_sense': lambda D: D['heat']['limits']['sense'],
    'heat_relay': lambda D: D['heat']['limits']['relay'],
    'heat_opto': lambda D: D['heat']['limits']['opto'],
    'heat_class': lambda D: D['heat']['limits']['class'],
    'heat_triac': lambda D: D['heat']['limits']['triac'],
    'heat_w': lambda D: D['heat']['source_w'],
    'lift': lambda D: D['wall']['bracket']['lift'],
    'relay_contact_w': lambda D: D['wall']['budgets']['relay_contact_w'],
    'relay_coil_w': lambda D: D['wall']['budgets']['relay_coil_w'],
    'sensor_mohm': lambda D: D['wall']['budgets']['sensor_mohm'],
    'link_loss_w': lambda D: D['link']['budget_w'],
    'sheet_mohm': lambda D: D['wall']['sheet_mohm'],
    'module_pf': lambda D: D['return']['module_pf'],
    'opto_led_ma': lambda D: D['rail']['assumed']['opto_led_ma'],
    'panel_ma': lambda D: D['rail']['assumed']['panel_ma'],
    'flow_ma': lambda D: D['rail']['assumed']['flow_ma'],
    'pressure_ma': lambda D: D['rail']['assumed']['pressure_ma'],
    'probe_ma': lambda D: D['rail']['assumed']['probe_ma'],
    'sense_ma': lambda D: D['rail']['assumed']['sense_ma'],
    'loadcell_ohm': lambda D: D['rail']['assumed']['loadcell_ohm'],
    'vm_out_ma': lambda D: D['rail']['assumed']['vm_out_ma'],
    'misc_ma': lambda D: D['rail']['assumed']['misc_ma'],
}

TOKEN_PATHS = {'E': ('fixing', 'E'), 'draw_tol': ('fixing', 'draw_tol'), 'lid_keep': ('fixing', 'lid_keep'), 'tab_ring': ('tabs', 'ring'), 'trace_w': ('trace', 'w'),
               'reed_tol': ('reed', 'tol'), 'hand_r': ('reed', 'hand_r'), 'strip_w': ('reed', 'strip_w'), 'heat_mcu': ('heat', 'limits', 'mcu'), 'heat_sense': ('heat', 'limits', 'sense'),
               'heat_relay': ('heat', 'limits', 'relay'), 'heat_opto': ('heat', 'limits', 'opto'), 'heat_class': ('heat', 'limits', 'class'), 'heat_triac': ('heat', 'limits', 'triac'),
               'heat_w': ('heat', 'source_w'), 'lift': ('wall', 'bracket', 'lift'), 'relay_contact_w': ('wall', 'budgets', 'relay_contact_w'), 'relay_coil_w': ('wall', 'budgets', 'relay_coil_w'),
               'sensor_mohm': ('wall', 'budgets', 'sensor_mohm'), 'link_loss_w': ('link', 'budget_w'), 'sheet_mohm': ('wall', 'sheet_mohm'), 'module_pf': ('return', 'module_pf'),
               'opto_led_ma': ('rail', 'assumed', 'opto_led_ma'), 'panel_ma': ('rail', 'assumed', 'panel_ma'), 'flow_ma': ('rail', 'assumed', 'flow_ma'), 'pressure_ma': ('rail', 'assumed', 'pressure_ma'),
               'probe_ma': ('rail', 'assumed', 'probe_ma'), 'sense_ma': ('rail', 'assumed', 'sense_ma'), 'loadcell_ohm': ('rail', 'assumed', 'loadcell_ohm'), 'vm_out_ma': ('rail', 'assumed', 'vm_out_ma'),
               'misc_ma': ('rail', 'assumed', 'misc_ma')}

def check_tokens(text, D, record_tokens=None):
    """Every assumption token of the record's Assumptions table against the data, and every token the script knows against the
    record: a token missing from the record, present twice, or unequal to the data is a failure."""
    bad, found = [], {}
    sec = section(text, 'Assumptions') or ''
    for name, val in re.findall(r'`([A-Za-z_]+)=(-?[0-9.]+)`', sec):
        found.setdefault(name, []).append(float(val))
    for name, vals in found.items():
        if name not in TOKENS:
            bad.append('the Assumptions table carries a token the script does not know: %s' % name)
    for name, get in TOKENS.items():
        vals = found.get(name, [])
        if len(vals) != 1:
            bad.append('assumption token %s appears %d times in the Assumptions table, once is required' % (name, len(vals)))
        elif abs(vals[0] - get(D)) > EPS:
            bad.append('assumption token %s is %g in the table and %g in the data' % (name, vals[0], get(D)))
    return bad

# ---------------------------------------------------------------- geometry
def rd(a, b):
    return math.hypot(max(b[0] - a[2], a[0] - b[2], 0), max(b[1] - a[3], a[1] - b[3], 0))
def ov(a, b):
    return a[0] < b[2] - EPS and b[0] < a[2] - EPS and a[1] < b[3] - EPS and b[1] < a[3] - EPS
def pt(p):
    return (p[0], p[1], p[0], p[1])
def grow(r, d):
    return (r[0] - d, r[1] - d, r[2] + d, r[3] + d)
def area(r):
    return (r[2] - r[0]) * (r[3] - r[1])
def inside(r, o):
    return r[0] >= o[0] - EPS and r[1] >= o[1] - EPS and r[2] <= o[2] + EPS and r[3] <= o[3] + EPS
def bbox_of(poly):
    return (min(p[0] for p in poly), min(p[1] for p in poly), max(p[0] for p in poly), max(p[1] for p in poly))
def poly_area(poly):
    n = len(poly)
    return abs(sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n))) / 2
def in_poly(p, poly):
    x, y, c = p[0], p[1], False
    for i in range(len(poly)):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % len(poly)]
        if abs((x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)) < 1e-9 and min(x0, x1) - EPS <= x <= max(x0, x1) + EPS and min(y0, y1) - EPS <= y <= max(y0, y1) + EPS:
            return True
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            c = not c
    return c
def rect_in_poly(r, poly):
    corners = [(r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3])]
    return all(in_poly(c, poly) for c in corners) and not any(r[0] + EPS < v[0] < r[2] - EPS and r[1] + EPS < v[1] < r[3] - EPS for v in poly)
def seg_rect(p, q, r):
    """Distance from the segment pq to rectangle r (0 when they meet)."""
    if crosses(p, q, r) or in_rect(p, r) or in_rect(q, r):
        return 0.0
    corners = [(r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3])]
    def to_seg(c):
        dx, dy = q[0] - p[0], q[1] - p[1]
        t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((c[0] - p[0]) * dx + (c[1] - p[1]) * dy) / (dx * dx + dy * dy)))
        return math.hypot(c[0] - p[0] - t * dx, c[1] - p[1] - t * dy)
    return min([to_seg(c) for c in corners] + [rd(pt(p), r), rd(pt(q), r)])
def in_rect(p, r):
    return r[0] <= p[0] <= r[2] and r[1] <= p[1] <= r[3]
def in_union(r, rects):
    """True when rectangle r lies wholly inside the union of the rectangles."""
    xs = sorted({r[0], r[2]} | {x for q in rects for x in (q[0], q[2]) if r[0] < x < r[2]})
    for a, b in zip(xs, xs[1:]):
        mid = (a + b) / 2
        cur = r[1]
        for lo, hi in sorted((q[1], q[3]) for q in rects if q[0] <= mid <= q[2]):
            if lo <= cur + EPS:
                cur = max(cur, hi)
        if cur < r[3] - EPS:
            return False
    return True
def edge_distance(r, poly):
    return min(seg_rect(poly[i], poly[(i + 1) % len(poly)], r) for i in range(len(poly)))
def rng(a, b):
    return '%.1f to %.1f' % (a, b)
def size(r):
    return '%.1f × %.1f' % (r[2] - r[0], r[3] - r[1])
def sq(x):
    return '%d' % int(x + 0.5)
def half(x):
    """A cost to the nearest half dollar: the board fee at an area other than the maker's two published points is inferred, which supports no finer figure."""
    return math.floor(x * 2 + 0.5) / 2

def crosses(p, q, r):
    """True when the segment pq passes through the interior of rectangle r."""
    x0, y0, x1, y1 = r
    dx, dy, t0, t1 = q[0] - p[0], q[1] - p[1], 0.0, 1.0
    for pp, qq in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if abs(pp) < EPS:
            if qq <= EPS:
                return False
        else:
            t = qq / pp
            if pp < 0:
                if t > t1:
                    return False
                t0 = max(t0, t)
            else:
                if t < t0:
                    return False
                t1 = min(t1, t)
    return t1 - t0 > EPS

def edge_points(r, step, near=None, limit=None):
    x0, y0, x1, y1 = r
    nx, ny = max(int(round((x1 - x0) / step)), 1), max(int(round((y1 - y0) / step)), 1)
    pts = []
    for i in range(nx + 1):
        x = x0 + (x1 - x0) * i / nx
        pts += [(x, y0), (x, y1)]
    for j in range(ny + 1):
        y = y0 + (y1 - y0) * j / ny
        pts += [(x0, y), (x1, y)]
    if near is not None:
        pts = [p for p in pts if rd(pt(p), near) < limit]
    return pts

def surface_path(a, b, slots, limit, outline=None):
    """Shortest path over the board surface from rectangle a to rectangle b, round the slot rectangles (a slot is not crossed).
    Sampled every 0.25 mm along the facing edges and 0.1 mm to the slot corners: exact to about 0.1 mm. Pairs the straight line
    of which already exceeds `limit` are not worth measuring. A slot corner that lies on the board's outline is not a point a path
    can turn round, because beyond it there is no board."""
    def free(p, q):
        x0, x1, y0, y1 = min(p[0], q[0]), max(p[0], q[0]), min(p[1], q[1]), max(p[1], q[1])
        for sl in slots:
            if sl[2] <= x0 or sl[0] >= x1 or sl[3] <= y0 or sl[1] >= y1:
                continue
            if crosses(p, q, sl):
                return False
        return True
    # the shortest straight segment between the rectangles: when it crosses no slot it is the surface path
    def facing(lo_a, hi_a, lo_b, hi_b):
        if hi_a < lo_b:
            return hi_a, lo_b
        if hi_b < lo_a:
            return lo_a, hi_b
        mid = (max(lo_a, lo_b) + min(hi_a, hi_b)) / 2
        return mid, mid
    xa, xb = facing(a[0], a[2], b[0], b[2])
    ya, yb = facing(a[1], a[3], b[1], b[3])
    if free((xa, ya), (xb, yb)):
        return math.hypot(xa - xb, ya - yb)
    best = math.inf
    for p in edge_points(a, 0.25, b, limit):
        for q in edge_points(b, 0.25, a, limit):
            d = math.hypot(p[0] - q[0], p[1] - q[1])
            if d < best and free(p, q):
                best = d
    if not slots:
        return best
    ob = bbox_of(outline) if outline else None
    on_edge = lambda c: ob is not None and (abs(c[0] - ob[0]) < EPS or abs(c[0] - ob[2]) < EPS or abs(c[1] - ob[1]) < EPS or abs(c[1] - ob[3]) < EPS)
    cs = [c for c in ((s[i], s[j]) for s in slots for i in (0, 2) for j in (1, 3)) if not on_edge(c)]
    fa, fb = edge_points(a, 0.1), edge_points(b, 0.1)
    da = [min([math.hypot(p[0] - c[0], p[1] - c[1]) for p in fa if free(p, c)] or [math.inf]) for c in cs]
    db = [min([math.hypot(p[0] - c[0], p[1] - c[1]) for p in fb if free(p, c)] or [math.inf]) for c in cs]
    dist, done = list(da), [False] * len(cs)
    queue = [(d, i) for i, d in enumerate(dist)]
    heapq.heapify(queue)
    while queue:
        d, i = heapq.heappop(queue)
        if done[i]:
            continue
        done[i] = True
        for j in range(len(cs)):
            if not done[j] and free(cs[i], cs[j]):
                nd = d + math.hypot(cs[i][0] - cs[j][0], cs[i][1] - cs[j][1])
                if nd < dist[j]:
                    dist[j] = nd
                    heapq.heappush(queue, (nd, j))
    return min(best, min(dist[i] + db[i] for i in range(len(cs))))

def slot_rects(slots):
    return [tuple(s['rect']) for s in slots]

def dip_paths(blocks, slots, limit, outline=None):
    """Pin-to-pin surface path round the slots of each opto-coupler: its mains row against its low-voltage row."""
    out = {}
    for b in blocks:
        d = b.get('dip')
        if not d:
            continue
        cx, cy = d['centre']
        offs = [(k - (d['pins'] - 1) / 2) * d['pin_dy'] for k in range(d['pins'])]
        if d.get('axis') == 'u':
            mp, lp = [(cx + o, cy - d['row']) for o in offs], [(cx + o, cy + d['row']) for o in offs]
        else:
            mp, lp = [(cx - d['row'], cy + o) for o in offs], [(cx + d['row'], cy + o) for o in offs]
        out[b['id']] = min(surface_path(pt(a), pt(c), slots, limit, outline) for a in mp for c in lp)
    return out

def mains_of(b):
    """A block's mains rectangles as (id, rect, net) triples."""
    return [(m[0], tuple(m[1]), m[2]) for m in b['mains']]

def pair_rule(items, slots, bas, reinforced, outline=None, own=()):
    """Every pair of mains rectangles on different nets keeps the signed mains-to-mains clearance straight and the signed basic creepage
    by surface path round the slots; a pair across the open interlock contact keeps the signed reinforced creepage, with no credit for anything but
    copper and slots. `items` are (id, rect, net, owner). No pair is excused for sharing an owner: the only exemptions are the
    pairs named in `own`, each a part's own pin pitch from its sheet (the record's data gives each with its sheet and its pitch)."""
    bad, least_s, least_p, n, n_re = [], math.inf, math.inf, 0, 0
    own = {frozenset(p) for p in own}
    for i, (a, ra, na, oa) in enumerate(items):
        for b, rb, nb, ob in items[i + 1:]:
            if na == nb or frozenset((a, b)) in own:
                continue
            across = bool(reinforced) and ((upstream_of(reinforced, na) and nb == reinforced[1]) or (upstream_of(reinforced, nb) and na == reinforced[1]))
            need = bas['creepage'] if across else bas['m_creepage']
            want = bas['clearance'] if across else bas['m_clearance']
            d = rd(ra, rb)
            least_s = min(least_s, d)
            if d < want - EPS:
                bad.append('mains copper %s and %s are %.2f mm apart, the clearance is %.1f' % (a, b, d, want))
            if d < need - EPS:
                n += 1
                n_re += 1 if across else 0
                L = surface_path(ra, rb, slots, need, outline)
                least_p = min(least_p, L)
                if L < need - 0.05:
                    bad.append('surface path of %.1f mm between mains copper %s and %s, the rule is %.1f' % (L, a, b, need))
    return bad, least_s, least_p, n, n_re

# ---------------------------------------------------------------- main board model
def reed_zone(D):
    r = D['reed']
    lo, up, h = r['lower'], [r['lower'][0], r['lower'][1] + r['pitch']], r['hand_r']
    box = (lo[0] - h, lo[1] - h, lo[0] + h, up[1] + h)
    strip = (lo[0] - r['strip_w'] / 2, lo[1], lo[0] + r['strip_w'] / 2, up[1])
    return lo, up, box, strip

def reed_hits(D, rect):
    lo, up, box, strip = reed_zone(D)
    h = D['reed']['hand_r']
    return rd(rect, pt(lo)) < h or rd(rect, pt(up)) < h or ov(rect, strip)

def tab_pads(D, found=False):
    """The pad of each tab: the blade's section (its width along X, its thickness along Y, the blade standing with its wide face
    parallel to X) with the annulus all round: a rectangle of blade + 2 ring by thickness + 2 ring about the tab's centre."""
    t = D['tabs']
    hx = t['blade'] / 2 + t['ring']
    hy = t['thick'] / 2 + t['ring']
    out = {}
    for x in t['list']:
        y = x['found'] if found else x['y']
        out[x['n']] = (t['x'] - hx, y - hy, t['x'] + hx, y + hy)
    return out

def tab_nets(D):
    return {x['n']: x.get('net', x['name']) for x in D['tabs']['list']}

def upstream_of(reinforced, net):
    """True when the net, or one of the nets written joined by | in it, lies on the supply side of the open interlock contact: the line net that
    the contact opens and every net upstream of it, the entry fuse's line side included."""
    return any(u in net.split('|') for u in reinforced[0])

def landing_pad(D):
    """The pad of the return landing: the same section as a tab's pad (the landing takes the same board-mounted blade) about the tab column."""
    t = D['tabs']
    hx = t['blade'] / 2 + t['ring']
    hy = t['thick'] / 2 + t['ring']
    y = D['return']['landing']['y']
    return (t['x'] - hx, y - hy, t['x'] + hx, y + hy)

def return_items(D):
    """The mains copper of the neutral return as (id, rect, net, owner): the landing's pad, the pour that holds it and the shunt's two lands."""
    R = D['return']
    items = [(R['landing']['id'], landing_pad(D), R['landing']['net'], R['landing']['id']),
             (R['pour']['id'], tuple(R['pour']['rect']), R['pour']['net'], R['pour']['id'])]
    items += [(i, tuple(r), 'NEUTRAL', R['shunt']['id']) for i, r in R['shunt']['lands']]
    return items

def padname(k):
    return 'the return landing' if k == 'R' else 'the pad of tab %d' % k

def main_items(D):
    """Every mains rectangle of the main board as (id, rect, net, owner): each tab pad and each link region with its own id as its
    owner, then each block's rectangles with the block as owner. No pair is excused for sharing an owner."""
    pads = tab_pads(D)
    nets = tab_nets(D)
    items = [('tab %d' % n, r, nets[n], 'tab %d' % n) for n, r in pads.items()]
    items += [(l['id'], tuple(l['rect']), l['net'], l['id']) for l in D['link']['strip']]
    items += return_items(D)
    for b in D['mains_blocks']:
        items += [(i, r, net, b['id']) for i, r, net in mains_of(b)]
    return items

def main_model(D):
    pads = tab_pads(D)
    pads['R'] = landing_pad(D)
    links = [tuple(l['rect']) for l in D['link']['strip']] + [r for _, r, _, _ in return_items(D)]
    strip = bbox_of([(p[0], p[1]) for p in list(pads.values()) + links] + [(p[2], p[3]) for p in list(pads.values()) + links])
    bodies, pockets = {'TABSTRIP': strip}, []
    for b in D['mains_blocks']:
        bodies[b['id']] = tuple(b['body'])
        pockets += [(b['id'], tuple(p)) for p in b['pockets']]
    for b in D['lv_blocks']:
        bodies[b['id']] = tuple(b['rect'])
    bodies['REED'] = reed_zone(D)[2]
    return pads, strip, bodies, main_items(D), pockets

CELL = 0.5

def trace_reach(D):
    """How far a trace's centreline must stand from the copper of another net, a slot, a hole's keep-out or the board edge, beyond the
    distance the rule asks of the copper: the trace's half-width at the maker's width tolerance, and half a grid cell (the centreline
    is snapped to the grid), so a route that exists holds its distances with that margin."""
    t = D['trace']
    return t['w'] / 2 * (1 + t['tol']) + CELL / 2


def corridors(D, items, pockets, outline, slots, keep, bas, reinforced, only=None, skip=()):
    """For every net whose mains copper is in more than one separate piece, the shortest route of a trace from the first piece to each of the others (the longest is reported): over a
    grid of half a millimetre, eight ways, never within the basic creepage of the copper of another net, within the signed creepage
    of a low-voltage block or a pocket, within the hole keep-out of a fixing or across a slot. A net whose pieces touch needs none.
    The result is the length in millimetres, or None where no route exists."""
    ob = bbox_of(outline)
    ext = trace_reach(D)
    nx, ny = int((ob[2] - ob[0]) / CELL) + 1, int((ob[3] - ob[1]) / CELL) + 1
    def cells(r, strict=True):
        i0, i1 = int(math.ceil((r[0] - ob[0]) / CELL - 1e-9)), int(math.floor((r[2] - ob[0]) / CELL + 1e-9))
        j0, j1 = int(math.ceil((r[1] - ob[1]) / CELL - 1e-9)), int(math.floor((r[3] - ob[1]) / CELL + 1e-9))
        for j in range(max(j0, 0), min(j1, ny - 1) + 1):
            for i in range(max(i0, 0), min(i1, nx - 1) + 1):
                x, y = ob[0] + i * CELL, ob[1] + j * CELL
                if not strict or (r[0] + 1e-6 < x < r[2] - 1e-6 and r[1] + 1e-6 < y < r[3] - 1e-6):
                    yield j * nx + i
    base = bytearray(nx * ny)
    em = D['basis']['edge_min'] + ext
    for k in cells((ob[0] - 1, ob[1] - 1, ob[2] + 1, ob[3] + 1), False):
        x, y = ob[0] + (k % nx) * CELL, ob[1] + (k // nx) * CELL
        if x < ob[0] + em or x > ob[2] - em or y < ob[1] + em or y > ob[3] - em:
            base[k] = 1
    for ctr in D['holes'].values():
        for k in cells((ctr[0] - keep - ext, ctr[1] - keep - ext, ctr[0] + keep + ext, ctr[1] + keep + ext), False):
            if math.hypot(ob[0] + (k % nx) * CELL - ctr[0], ob[1] + (k // nx) * CELL - ctr[1]) < keep + ext:
                base[k] = 1
    for s in slots:
        for k in cells(grow(s, D['slot_copper'] + ext)):
            base[k] = 1
    def slot_between(p, q):
        x0, x1, y0, y1 = min(p[0], q[0]), max(p[0], q[0]), min(p[1], q[1]), max(p[1], q[1])
        for sl in slots:
            if sl[2] <= x0 or sl[0] >= x1 or sl[3] <= y0 or sl[1] >= y1:
                continue
            if crosses(p, q, sl):
                return True
        return False
    def near(r, d, clear=None):
        """The cells a trace's centreline may not use for the copper (or block) r: nearer than the clearance (the signed one, or
        `clear` for mains copper of another net) by straight distance, or nearer than d by straight distance with no slot between the cell and the copper (a slot makes the surface path
        the longer way round, which the pair rules of the record measure); the distance is straight and not a square grown by d."""
        dmin = (bas['clearance'] if clear is None else clear) + ext
        for k in cells(grow(r, d), False):
            x, y = ob[0] + (k % nx) * CELL, ob[1] + (k // nx) * CELL
            dd = rd(r, (x, y) * 2)
            if dd < dmin - 1e-6:
                yield k
            elif dd < d - 1e-6:
                q = (min(max(x, r[0]), r[2]), min(max(y, r[1]), r[3]))
                if not slot_between((x, y), q):
                    yield k
    for b in D['lv_blocks']:
        for k in near(tuple(b['rect']), bas['creepage'] + ext):
            base[k] = 1
    for _, p in pockets:
        for k in near(p, bas['creepage'] + ext):
            base[k] = 1
    by_net = {}
    groups = D.get('route_groups', {})
    for i, r, net, o in items:
        by_net.setdefault(groups.get(net, net), []).append((i, r))
    out, missed = {}, []
    for net, rects in by_net.items():
        if (only is not None and net not in only) or net in skip:
            continue
        comps = []
        for i, r in rects:
            hit = [c for c in comps if any(rd(r, q) < 1e-6 for _, q in c)]
            merged = [(i, r)] + [m for c in hit for m in c]
            comps = [c for c in comps if c not in hit] + [merged]
        if len(comps) < 2:
            continue
        blocked = bytearray(base)
        for n2, rr in by_net.items():
            if n2 != net:
                reinf = (upstream_of(reinforced, net) and n2 == reinforced[1]) or (upstream_of(reinforced, n2) and net == reinforced[1])
                for _, r in rr:
                    for k in near(r, (bas['creepage'] if reinf else bas['m_creepage']) + ext, bas['clearance'] if reinf else bas['m_clearance']):
                        blocked[k] = 1
        corridors.grid = getattr(corridors, 'grid', {})
        corridors.grid[net] = (bytes(blocked), nx, ny, ob, [[r for _, r in c] for c in comps])
        start = {k for _, r in comps[0] for k in cells(r, False) if not blocked[k]}
        worst = 0.0
        for comp in comps[1:]:
            goal = {k for _, r in comp for k in cells(r, False) if not blocked[k]}
            dist = {k: 0.0 for k in start}
            heap = [(0.0, k) for k in start]
            heapq.heapify(heap)
            found = None
            while heap:
                d, k = heapq.heappop(heap)
                if d > dist.get(k, math.inf):
                    continue
                if k in goal:
                    found = d
                    break
                x, y = k % nx, k // nx
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                    a, b = x + dx, y + dy
                    if not (0 <= a < nx and 0 <= b < ny) or blocked[b * nx + a]:
                        continue
                    if dx and dy and (blocked[y * nx + a] or blocked[b * nx + x]):
                        continue
                    nd = d + CELL * (math.sqrt(2) if dx and dy else 1.0)
                    if nd < dist.get(b * nx + a, math.inf):
                        dist[b * nx + a] = nd
                        heapq.heappush(heap, (nd, b * nx + a))
            if found is None:
                worst = None
                missed.append('%s: from %s to %s' % (net, '+'.join(i for i, _ in comps[0]), '+'.join(i for i, _ in comp)))
                break
            worst = max(worst, found)
        out[net] = worst
    corridors.missed = missed
    return out

def intrusion_top(D, x):
    i = D['intrusions']
    if x < i['one_x0'] or x > i['one_x1']:
        return 0.0
    return i['one_straight'] + math.sqrt(max(i['one_r'] ** 2 - (x - i['one_cx']) ** 2, 0))

def intrusion_side(D, x, y):
    """How far a lead end lies to the side of intrusion 1's straight edges, when it lies beside them; None otherwise."""
    i = D['intrusions']
    if y > i['one_straight'] or (i['one_x0'] <= x <= i['one_x1']):
        return None
    return min(abs(x - i['one_x0']), abs(x - i['one_x1']))

def kind_area(D, bodies, k):
    if 'area' in k:
        return k['area']
    a = sum(area(bodies[n]) for n in k.get('blocks', []) if n in bodies)
    a += sum(area(tuple(b['body'])) for b in D['wall']['blocks'] if b['id'] in k.get('wall', []))
    a += k.get('extra_area', 0.0)
    if k.get('shunt'):
        a += area(tuple(D['return']['shunt']['rect']))
    a += sum(w * h for reg in ('hdr', 'ana') for w, h in k.get(reg, []))
    return a

def removal_order(D):
    return [k['n'] for k in sorted((k for k in D['kinds'] if 'rank' in k), key=lambda k: k['rank'])]

def union_grown_area(rects, g):
    """The area of the union of the rectangles, each grown by g on its high sides: what blocks that are each grown by g the same way can fill."""
    gr = [(r[0], r[1], r[2] + g, r[3] + g) for r in rects]
    xs = sorted({v for r in gr for v in (r[0], r[2])})
    total = 0.0
    for a, b in zip(xs, xs[1:]):
        cur, hi = 0.0, None
        for lo, up in sorted((r[1], r[3]) for r in gr if r[0] <= a and r[2] >= b):
            if hi is None or lo > hi:
                cur += up - lo
                hi = up
            elif up > hi:
                cur += up - hi
                hi = up
        total += cur * (b - a)
    return total

def region_capacity(D):
    """What each class of region can hold: the union of its rectangles grown by the spacing the drawing keeps in that class (A18)."""
    g = D['regions']['gap']
    cap = {k: union_grown_area([tuple(r['rect']) for r in D['regions'][k]], g[k]) for k in ('hdr', 'ana')}
    boxes = {b['id']: b['rect'] for b in D['lv_blocks']}
    for reg, ids in D['regions'].get('other', {}).items():
        cap[reg] -= sum((boxes[i][2] - boxes[i][0] + g[reg]) * (boxes[i][3] - boxes[i][1] + g[reg]) for i in ids)
    return cap

def region_demand(D, removed):
    """What the blocks of the kinds not removed need in each class of region, each block grown by the spacing of its class; a kind that
    is not drawn gives its block sizes (the `hdr` and `ana` lists of its row)."""
    g = D['regions']['gap']
    dem = {'hdr': 0.0, 'ana': 0.0}
    for b in D['lv_blocks']:
        if b.get('region') and b.get('kind') not in removed:
            r = b['rect']
            dem[b['region']] += (r[2] - r[0] + g[b['region']]) * (r[3] - r[1] + g[b['region']])
    for k in D['kinds']:
        if k['n'] not in removed:
            for reg in ('hdr', 'ana'):
                dem[reg] += sum((w + g[reg]) * (h + g[reg]) for w, h in k.get(reg, []))
    return dem

def header_blocks(D, removed):
    """The sizes (width, height) of every header the kinds not removed need: the blocks drawn and the sizes a kind not drawn lists."""
    out = [(b['rect'][2] - b['rect'][0], b['rect'][3] - b['rect'][1]) for b in D['lv_blocks'] if b.get('region') == 'hdr' and b.get('kind') not in removed]
    for k in D['kinds']:
        if k['n'] not in removed:
            out += [tuple(x) for x in k.get('hdr', [])]
    return out

ARRANGEMENTS = {}

def arrangement(D, reg, blocks):
    """Whether every block of `blocks` (width, height), each turned or not, can be placed inside the rectangles of the class `reg` with
    the spacing of that class kept between blocks, whatever the blocks' places are now. An exhaustive search over every placement that
    is pushed down and to the left against another block or the floor: each block and each rectangle's top grown by the spacing on
    its high sides, in steps of 0.1 mm; the lowest, leftmost free stretch of the floor takes one of the blocks left (in either
    turn) or is given up, the area given up never over what the region has beyond the blocks; a state met again with no less area
    given up is not searched again. The rectangles must stand in a row on one floor, touching, which is how the header regions are
    drawn; None is returned for any other shape. True when an arrangement exists."""
    g = D['regions']['gap'][reg]
    G = int(round(g * 10))
    rs = sorted((tuple(x['rect']) for x in D['regions'][reg]), key=lambda r: r[0])
    if any(abs(r[1] - rs[0][1]) > EPS for r in rs) or any(abs(a[2] - b[0]) > EPS for a, b in zip(rs, rs[1:])):
        return None
    u = lambda v: int(round(v * 10))
    segs, start = [], 0
    for r in rs:
        end = u(r[2] - rs[0][0]) + G
        segs.append((start, end, u(r[3] - rs[0][1]) + G))
        start = end
    width = segs[-1][1]
    items = sorted((u(w) + G, u(h) + G) for w, h in blocks)
    key = (tuple(segs), tuple(items))
    if key in ARRANGEMENTS:
        return ARRANGEMENTS[key]
    types = sorted(set(items))
    counts = [items.count(x) for x in types]
    slack = sum((e - s) * c for s, e, c in segs) - sum(w * h for w, h in items)
    top = lambda x0, x1: min(c for s, e, c in segs if s < x1 and e > x0)
    seen = {}
    def merge(sky):
        out = []
        for s in sky:
            if out and out[-1][2] == s[2] and out[-1][1] == s[0]:
                out[-1] = (out[-1][0], s[1], s[2])
            else:
                out.append(s)
        return out
    def solve(sky, waste):
        if not any(counts):
            return True
        k = (tuple(sky), tuple(counts))
        if k in seen and seen[k] <= waste:
            return False
        seen[k] = waste
        i = min(range(len(sky)), key=lambda j: (sky[j][2], sky[j][0]))
        x0, x1, y = sky[i]
        for t_, (w, h) in enumerate(types):
            if not counts[t_]:
                continue
            for iw, ih in {(w, h), (h, w)}:
                if iw <= x1 - x0 and y + ih <= top(x0, x0 + iw):
                    ns = list(sky)
                    ns[i:i + 1] = [(x0, x0 + iw, y + ih)] + ([(x0 + iw, x1, y)] if x1 > x0 + iw else [])
                    counts[t_] -= 1
                    ok = solve(merge(ns), waste)
                    counts[t_] += 1
                    if ok:
                        return True
        lower = [sky[j][2] for j in (i - 1, i + 1) if 0 <= j < len(sky)]
        if lower and waste + (x1 - x0) * (min(lower) - y) <= slack:
            ns = list(sky)
            ns[i] = (x0, x1, min(lower))
            return solve(merge(ns), waste + (x1 - x0) * (min(lower) - y))
        return False
    ARRANGEMENTS[key] = slack >= 0 and solve([(0, width, 0)], 0)
    return ARRANGEMENTS[key]

def allocation(D):
    """The removal steps: demand and overflow of the header regions and the analogue regions, each block counted with the spacing the
    drawing keeps in its class against the regions counted the same way (A18). Step 0 removes nothing; each later step removes the next
    kind of the removal order; the allocation stops at the first step where both classes fit, and the headers fit only when an
    arrangement of them exists, the area being no more than the necessary condition. Returns the capacity, the steps as
    (step, kind removed or None, demand), the index of the step it stops at (None if no step fits) and, for each step, the
    state of the search for an arrangement of the headers: 'over' (the area is over, not searched), 'none' or 'found'."""
    cap = region_capacity(D)
    steps, removed, stop, arr = [], set(), None, {}
    def at(n, gone):
        dem = region_demand(D, removed)
        steps.append((n, gone, dem))
        if dem['hdr'] > cap['hdr'] + EPS:
            arr[n] = 'over'
        else:
            arr[n] = 'found' if arrangement(D, 'hdr', header_blocks(D, removed)) else 'none'
        return arr[n] != 'none' and arr[n] != 'over' and dem['ana'] <= cap['ana'] + EPS
    if at(0, None):
        stop = 0
    for n in removal_order(D):
        if stop is not None:
            break
        removed.add(n)
        if at(len(steps), n):
            stop = len(steps) - 1
    return cap, steps, stop, arr

def stack_gap(D):
    ys = sorted((b['body'][1], b['body'][3]) for b in D['mains_blocks'])
    return max(ys[i + 1][0] - ys[i][1] for i in range(len(ys) - 1)), ys

def fabrication(c, board):
    f = c['fee']
    w, h = board['w'], board['h']
    a = board_area(board)
    if w <= f['band'] and h <= f['band']:
        v = f['band4'] if board['layers'] == 4 else f['band2']
        return v, v, True
    eng, slope = (f['eng4'], f['slope4']) if board['layers'] == 4 else (f['eng2'], f['slope2'])
    return eng + slope * a / f['ref_area'], eng, False

def board_area(board):
    """A board's area: its width by its height, plus or minus the bay for the module's DC end."""
    bay = board.get('bay')
    return board['w'] * board['h'] + (board.get('bay_sign', 1) * bay[0] * bay[1] if bay else 0.0)

def costs(D):
    c, res = D['cost'], {}
    f = c['fee']
    for name in 'ABC':
        d = c[name]
        fab = [fabrication(c, b) for b in d['boards']]
        asm, lab, dup = d['orders'] * (f['setup'] + f['stencil']), d['orders'] * f['labour'], d['dup_ext'] * f['ext_econ']
        lp, lj = d['links'] * c['link_parts'], d['links'] * c['link_joints'] * f['joint_hand']
        res[name] = dict(fab=sum(x[0] for x in fab), lines=[(b['name'], x[0], x[2]) for b, x in zip(d['boards'], fab)],
                         asm=asm, lab=lab, dup=dup, lp=lp, lj=lj, total=sum(x[0] for x in fab) + asm + lab + dup + lp + lj)
    return res

# ---------------------------------------------------------------- owners of the functions
OWNER_LABELS = {'main': 'main board', 'wall': 'wall board', 'steam path': 'steam-path assembly'}

def check_decisions(D, text):
    """Every owner decision still pending is stated once, in the record's list of them, with its words; the section it concerns points to it;
    and no other mention of a decision pending in the record lacks the pointer to the list."""
    ds = D.get('owner_decisions') or []
    if not ds:
        return ['the data lists no owner decisions pending']
    body = section(text, 'Owner decisions pending')
    if body is None:
        return ['the record has no section "Owner decisions pending"']
    bad, items = [], {}
    for ln in body.split('\n'):
        m = re.match(r'^\*\*(D[0-9]+)\. (.*?)\.\*\* (.*)$', ln)
        if m:
            items.setdefault(m.group(1), []).append(m)
    for i_ in sorted(set(items) - {d['id'] for d in ds}):
        bad.append('the record lists an owner decision %s that the data does not' % i_)
    for d in ds:
        found = items.get(d['id'], [])
        if len(found) != 1:
            bad.append('the owner decision %s is stated %d times in the list of owner decisions pending, once is required' % (d['id'], len(found)))
            continue
        m = found[0]
        if m.group(2) != d['title']:
            bad.append('the owner decision %s is titled "%s" in the record and "%s" in the data' % (d['id'], m.group(2), d['title']))
        if not m.group(3).startswith('Owner decision pending'):
            bad.append('the owner decision %s does not state "Owner decision pending" in the record\'s list' % d['id'])
        home = re.sub(r'\*', '', section(text, d['home']) or '')
        if not re.search(r'Owner decisions pending, %s(?![0-9])' % d['id'], home):
            bad.append('the section "%s" does not point to the owner decision %s' % (d['home'], d['id']))
    outside = re.sub(r'^```.*?^```', '', text, flags=re.S | re.M).replace(body, '', 1)
    for m in re.finditer(r'(?i)(?<!§ Owner )decisions? pending', outside):
        line_start, line_end = outside.rfind('\n', 0, m.start()) + 1, outside.find('\n', m.end())
        if outside[line_start] != '#' and not re.search(r'Owner decisions pending, D[0-9]', outside[m.start():min(m.end() + 200, line_end if line_end >= 0 else len(outside))]):
            bad.append('the record mentions an owner decision pending without pointing to the list: "%s"' % outside[max(m.start() - 40, line_start):m.end() + 30])
    return bad

def check_removal_decision(D, text):
    """A tab of the connector record that the board does not draw is removed by the owner's decision, which the owner-intent table of the
    record states with its date: the tabs the decision names are not drawn and are listed as removed, and a tab listed as removed is one
    the decision names."""
    bad, tb = [], D['tabs']
    rm = tb.get('removal') or {}
    rows = table_rows(section(text, 'Owner intent carried in'))
    hit = [cells for key, cells in rows.items() if rm.get('row') and key.startswith(rm['row'])]
    if not hit:
        return ['the owner-intent table of the record has no row that starts "%s", the owner\'s decision that removes the tabs the data lists as removed' % rm.get('row')]
    cells = hit[0]
    if len(cells) < 2 or cells[1] != rm['date']:
        bad.append('the owner-intent row of the removed tabs is dated %s and the data says %s' % (cells[1] if len(cells) > 1 else 'nothing', rm['date']))
    if 'remove' not in cells[0].lower():
        bad.append('the owner-intent row "%s" does not say the tabs are removed' % rm['row'])
    named = {int(n) for n in re.findall(r'[0-9]+', rm['row'])}
    drawn = {x['n'] for x in tb['list']}
    listed = {x['n'] for x in tb.get('removed', [])}
    for n in sorted(named):
        if n in drawn:
            bad.append('tab %d is drawn, and the owner decided on %s to remove it' % (n, rm['date']))
        if n not in listed:
            bad.append('tab %d is not listed as removed in the data, and the owner decided on %s to remove it' % (n, rm['date']))
    for n in sorted(listed - named):
        bad.append('tab %d is listed as removed and no owner decision of the record removes it' % n)
    return bad

def check_owners(D, text):
    """C1: every function of the forms record has one non-blank owner, a board or an off-board assembly the record declares, and
    the owner table of the record names exactly that owner and no other; a function the record splits across boards says so."""
    bad = []
    rows = {}
    for ln in (section(text, 'Every function has one owner') or '').split('\n'):
        if ln.startswith('|') and not re.match(r'^\|[\s:|-]+\|$', ln):
            cells = [c.strip() for c in ln.strip().strip('|').split('|')]
            rows.setdefault(re.sub(r'[`*]', '', cells[0]), []).append(cells)
    for name, found in rows.items():
        if len(found) > 1:
            bad.append('the owner table holds the function %s %d times' % (name, len(found)))
    for f in D['functions']:
        owner = (f.get('owner') or '').strip()
        parts = [p.strip() for p in owner.split(' and ')] if owner else []
        if not parts or any(p not in OWNER_LABELS for p in parts):
            bad.append('the function %s has the owner "%s", which is blank or not a board or assembly the record declares' % (f['name'], owner))
            continue
        if len(parts) > 1 and not f.get('split'):
            bad.append('the function %s has %d owners and gives no reason for splitting it' % (f['name'], len(parts)))
        row = rows.get(f['name'])
        if not row:
            continue
        cell = re.sub(r'[`*]', '', row[0][1] if len(row[0]) > 1 else '').lower()
        for key, label in OWNER_LABELS.items():
            if (label in cell) != (key in parts):
                bad.append('the owner cell of %s %s "%s" and the data %s it' % (f['name'], 'names' if label in cell else 'does not name', label, 'does not give' if label in cell else 'gives'))
    return bad

def part_counts(D):
    """From the blocks: the count and joints of each part tag, the header types as (ways, pitch) with the number of each, and the
    header pins. A block's fit lists its parts as [tag, joints]; a relay's or the module's joints are its pins; a tab has two."""
    counts, types, pins = {}, {}, 0
    def add(tag, joints, n=1):
        c, j = counts.get(tag, (0, 0))
        counts[tag] = (c + n, j + joints * n)
    for b in D['mains_blocks']:
        for tag, j in b.get('fit', []):
            add(tag, len(b['pins']) if j == 'pins' else j)
    for b in D['lv_blocks']:
        for tag, j in b.get('fit', []):
            add(tag, j)
        if b.get('conn'):
            k = (b['conn']['ways'], b['conn']['pitch'])
            types[k] = types.get(k, 0) + 1
            pins += b['conn']['ways']
    add('tab', D['tabs']['joints'], len(D['tabs']['list']) + 1)
    for tag, j in D['return']['shunt'].get('fit', []):
        add(tag, j)
    return counts, types, pins

def wall_counts(D):
    """The wall board's parts by tag, from the blocks, the copper regions and the header: (count, joints)."""
    W, counts = D['wall'], {}
    for b in W['blocks'] + W['copper'] + W['lv']:
        for tag, j in b.get('fit', []):
            c, jj = counts.get(tag, (0, 0))
            counts[tag] = (c + 1, jj + (b['conn']['ways'] if j == 'ways' else j))
    return counts

def rows_of_kinds(text):
    """The table of kinds of the record, by its first cell, with the raw cells (backticks kept so the criterion ids can be found)."""
    rows = {}
    for ln in (section(text, 'The anticipated channel kinds') or '').split('\n'):
        if ln.startswith('|') and not re.match(r'^\|[\s:|-]+\|$', ln):
            cells = [c.strip() for c in ln.strip().strip('|').split('|')]
            rows.setdefault(cells[0], cells)
    return rows

def apply_what_if(D, wi):
    """A copy of the data with the what-if's blocks, slots and heat lists in place of the drawn ones."""
    d = copy.deepcopy(D)
    d.pop('what_if', None)
    for key in ('mains_blocks', 'lv_blocks'):
        for b in d[key]:
            b.update(copy.deepcopy(wi[key].get(b['id'], {})))
    d['slots'] = copy.deepcopy(wi['slots'])
    d['heat'].update(copy.deepcopy(wi['heat']))
    return d

def max_held(D, bas, ob, gap=None):
    """Every way of standing the parts of the 85 C class along the barrier column: the module (a heat source) at every position from
    the interlock relay's 15 mm up, each part above or below it, each order, the parts that are fed from a tab in the order of their
    tabs (a lead cannot pass another net's copper in the channel), a part below the module no nearer the interlock relay than the
    rule where the record requires it, and the parts packed with the clearance between their copper: the most parts that hold 15 mm
    from both sources, and the arrangements that hold that many."""
    ht, lim = D['heat'], D['heat']['limits']
    mbx = {b['id']: b for b in D['mains_blocks']}
    il = tuple(mbx['K_IL']['heat'])
    mod = tuple(mbx['MODULE']['body'])
    mh = mod[3] - mod[1]
    ids = [p['id'] for p in ht['class85']]
    hot = {n: (tuple(mbx[n]['hot']) if mbx[n].get('hot') else tuple(mbx[n]['body'])) for n in ids}
    size = {n: hot[n][3] - hot[n][1] for n in ids}
    inset = {n: min(m[1][1] - mbx[n]['body'][1] for m in mbx[n]['mains']) for n in ids}
    gap = bas['clearance'] if gap is None else gap
    gp = lambda a, b: max(gap - inset[a] - inset[b], 0.0)
    tab_y = {x['name']: x['y'] for x in D['tabs']['list']}
    supply = {x['name'] for x in D['tabs']['list'] if x['name'] in {m[2] for b in D['mains_blocks'] for m in b['mains']} and x['n'] > 3}
    fed = {n: tab_y[mbx[n]['mains'][0][2]] for n in ids if mbx[n]['mains'][0][2] in supply}
    top, floor = ob[3] - bas['edge_min'], il[3] + gap
    required = {tuple(x) for x in ht.get('required_held', [])}
    cls = lim['class']
    best, sets = 0, []
    ym = il[3] + lim['relay']
    while ym + mh <= top + EPS:
        mtop = ym + mh
        for mask in range(1 << len(ids)):
            above = [n for i, n in enumerate(ids) if mask >> i & 1]
            below = [n for n in ids if n not in above]
            tab_a, tab_b = [n for n in above if n in fed], [n for n in below if n in fed]
            if tab_a and tab_b and max(fed[n] for n in tab_b) > min(fed[n] for n in tab_a):
                continue
            for pa in itertools.permutations(above):
                if [n for n in pa if n in fed] != sorted([n for n in pa if n in fed], key=lambda n: -fed[n]):
                    continue
                y, prev, pos = top, None, []
                for n in pa:
                    if prev is not None:
                        y -= gp(prev, n)
                    y0 = y - size[n]
                    pos.append((n, y0))
                    y, prev = y0, n
                if pos and pos[-1][1] < mtop - EPS:
                    continue
                held_a = [n for n, y0 in pos if y0 >= mtop + cls - EPS]
                for pb in itertools.permutations(below):
                    if [n for n in pb if n in fed] != sorted([n for n in pb if n in fed], key=lambda n: -fed[n]):
                        continue
                    y, prev, posb = ym, None, []
                    for n in pb:
                        if prev is not None:
                            y -= gp(prev, n)
                        y0 = y - size[n]
                        posb.append((n, y0))
                        y, prev = y0, n
                    if posb and posb[-1][1] < floor - EPS:
                        continue
                    if any(y0 < il[3] + cls - EPS for n, y0 in posb if (n, 'K_IL') in required):
                        continue
                    held_b = [n for n, y0 in posb if y0 >= il[3] + cls - EPS and y0 + size[n] <= ym - cls + EPS]
                    k = len(held_a) + len(held_b)
                    if k > best:
                        best, sets = k, []
                    if k == best and len(sets) < 40:
                        sets.append((round(ym, 2), tuple(pa), tuple(pb), tuple(held_a + held_b)))
        ym += 0.2
    return best, sets

def held_parts(D):
    """The parts of the 85 C class that stand the rule's distance from every heat source."""
    mbx = {b['id']: b for b in D['mains_blocks']}
    rect = lambda n, key: tuple(mbx[n].get(key) or mbx[n]['body'])
    return sorted(p['id'] for p in D['heat']['class85'] if all(rd(rect(sname, 'heat'), rect(p['id'], 'hot')) >= D['heat']['limits']['class'] - EPS for sname in D['heat']['sources']))

def kept_sensor_kinds(D):
    """The current sensors on the rail: one for each kind that carries a sensor and has a block drawn."""
    drawn = {b['id'] for b in D['lv_blocks']}
    return sum(1 for k in D['kinds'] if k.get('sensor') and any(n in drawn for n in k.get('blocks', [])))

def rail_rows(D):
    """The 5 V rail's loads in mA, each coil at the low end of its resistance tolerance, and the total at the controller's maximum and typical."""
    ra, rl, vr, il = D['rail']['assumed'], D['rail'], D['valve_relay'], D['relay']
    v5 = rl['volts']
    rows = [('K_IL coil', 1000.0 * v5 / (il['coil_ohm'] * (1 - il['coil_tol']))),
            ('Valve relay coils', 1000.0 * v5 / (vr['coil_ohm'] * (1 - vr['coil_tol'])) * vr['count']),
            ('Controller', rl['controller_ma']),
            ('Gauge drivers', rl['gauge']['phases'] * rl['gauge']['phase_ma']),
            ('Weight amplifiers', rl['hx711_ma'] * rl['hx711_count']),
            ('Load-cell excitation', 1000.0 * v5 / ra['loadcell_ohm'] * ra['loadcell_count']),
            ('Opto-triac LED drives', ra['opto_led_ma'] * ra['opto_leds']),
            ('Panel indicators and buzzer', ra['panel_ma']),
            ('Flow meter', ra['flow_ma']),
            ('Pressure transducers', ra['pressure_ma'] * ra['pressure_count']),
            ('In-stream probe converters', ra['probe_ma'] * ra['probe_count']),
            ('Current sensors', ra['sense_ma'] * kept_sensor_kinds(D)),
            ('Voltage measurement output', ra['vm_out_ma']),
            ('Headers, pull-ups and dividers', ra['misc_ma'])]
    total = sum(v for _, v in rows)
    return rows, total, total - rl['controller_ma'] + rl['controller_typ_ma']

# ---------------------------------------------------------------- the main board
EARLIER_DESIGN_TERMS = ((r'mains[\s-]*entry[\s-]*assembl', 'mains-entry assembly'), (r'inlet[\s/-]*filter', 'inlet filter'))

# The fenced blocks that hold the terms as code and output, by their info string (each stripped once), and the one bare block of commands.
CODE_FENCES = ('python', 'floorplan-data', 'expected-main', 'expected-wall')
COMMANDS_OPENING = 'python3 -I -c "import re,sys;'

def prose_outside_code(text):
    """The record with only its script, data, expected-output and commands blocks taken out. A fence is read line by line: an opening fence
    runs to the next bare fence line. A block not on the list, a second block of a listed label, and a block never closed stay in the text."""
    lines, out, i, seen = text.split('\n'), [], 0, set()
    while i < len(lines):
        line = lines[i]
        if not line.startswith('```'):
            out.append(line)
            i += 1
            continue
        label = line[3:].strip()
        close = next((j for j in range(i + 1, len(lines)) if lines[j].rstrip() == '```'), None)
        known = close is not None and ((label in CODE_FENCES and label not in seen) or
                                        (label == '' and lines[i + 1].startswith(COMMANDS_OPENING) and 'commands' not in seen))
        if known:
            seen.add(label if label else 'commands')
            i = close + 1
        else:
            i += 1
    return '\n'.join(out)

def check_earlier_design_terms(text):
    """The machine keeps its fixed mains lead, so the record's prose names no mains-entry assembly and no inlet filter except inside a marked
    note of the earlier design, `[earlier design: ...]`. The script, the data, the expected output and the block of commands hold the terms as
    code and output and are not read; every other fenced block is read like prose. The check cannot tell whether the words inside a marker
    truthfully cite the earlier design: that the marker is used only for a citation is the reviewer's judgement."""
    prose = prose_outside_code(text)
    prose = re.sub(r'\[earlier design: [^\]]*\]', '', prose)
    prose = re.sub(r'\s+', ' ', re.sub(r'[`*]', '', prose)).lower()
    return ['earlier design named without its marker (%s): the term stands outside an [earlier design: ...] note' % label
            for term, label in EARLIER_DESIGN_TERMS if re.search(term, prose)]

STALE_ENTRY = ((r'\bno place\b[^.|\n]{0,200}\b(?:drawn|floorplan)\b', 'no place for the entry parts is drawn'),
               (r'\bhave no place\b', 'the entry parts have no place'),
               (r'\bnot in the data or the drawing\b', 'the entry parts are not in the data or the drawing'),
               (r'\bplacing (?:them|the parts) changes the main board.s floorplan\b', 'placing the entry parts is separate work'))

def check_entry_statements(text):
    """The entry fuse holder and the varistor are drawn, so the record's prose, outside the script, the data, the expected output and the
    block of commands, states no place missing for them and no work left to place them."""
    prose = prose_outside_code(text)
    return ['stale statement of the entry parts\' place (%s): the floorplan draws them at tabs 2 and 3' % label for term, label in STALE_ENTRY if re.search(term, prose, re.I)]

NUMBER_WORDS = {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five', 6: 'six', 7: 'seven', 8: 'eight', 9: 'nine', 10: 'ten',
                11: 'eleven', 12: 'twelve', 13: 'thirteen', 14: 'fourteen', 15: 'fifteen', 16: 'sixteen', 17: 'seventeen', 18: 'eighteen', 19: 'nineteen'}

def spaced(x, places=0):
    """A number as the cost record writes it: thousands apart by a space."""
    return '{:,.{}f}'.format(x, places).replace(',', ' ')

def wall_outline(ears, w, h):
    """The heater wall board's outline with the bracket's ears, its area and its span over the ears."""
    outline = [(ears[0][0], 0.0), (ears[1][2], 0.0), (ears[1][2], ears[1][3]), (w, ears[1][3]), (w, h), (0.0, h), (0.0, ears[0][3]), (ears[0][0], ears[0][3])]
    return outline, poly_area(outline), ears[1][2] - ears[0][0]

def wall_figures(D):
    """The heater wall board's body, span, area and slot path as the cost record restates them."""
    w, h = D['wall']['size']
    _, wa, span = wall_outline([tuple(e) for e in D['wall']['bracket']['ears']], w, h)
    plen = sum(max(s['rect'][2] - s['rect'][0], s['rect'][3] - s['rect'][1]) for s in D['wall']['slots'])
    return dict(w=w, h=h, span=span, area=wa, slot=plen, slot_density=plen * 1000.0 / wa)

def check_cost_record(cost, fig):
    """The figures the cost record restates that this check counts or computes: the outline, its coordinates and area in every unit, the slot
    count, path and density of each board, the Extended types, their split and their feeder loading, the header types and ways, the joints,
    the heater wall board's body, span, area, types and joints, the fabrication price of the main board and of its two-layer fallback, and the
    counts of the parts the blocks fit. Each statement is found by its own words wherever the cost record makes it, every instance must equal
    the figure counted here, and a statement that is not there at all is a failure. Prices that are the manufacturer's charges are not read:
    this check does not count them."""
    text = re.sub(r'[`*]', '', cost)
    area_s = spaced(fig['area'])
    ref_s = spaced(fig['ref_area'])
    word = lambda n: NUMBER_WORDS.get(n, str(n))
    f2 = lambda x: '%.2f' % x
    c = fig['counts']
    wanted = [
        ('the slot path and its metres per square metre', r'([0-9.]+) mm of slot path, ([0-9.]+) m of slot path per m²', ('%.0f' % fig['slot'], '%.1f' % fig['slot_density'])),
        ('the outline and area of the priced board', r'4 layers, ([0-9.]+) × ([0-9.]+) mm \(([0-9 ]+) mm²\)', ('%.1f' % fig['w'], '%.1f' % fig['h'], area_s)),
        ('the outline of the configuration priced', r'one 4-layer board of ([0-9.]+) × ([0-9.]+) mm', ('%.1f' % fig['w'], '%.1f' % fig['h'])),
        ('the area in the fabrication price', r'× ([0-9 ]+[0-9]) / 10 609', (area_s,)),
        ('the area in the shipping weight', r'× ([0-9 ]+[0-9]) / 10 000', (area_s,)),
        ('the Extended types and their split', r'main board has ([0-9]+) unique Extended types, ([0-9]+) placed by the manufacturer and ([0-9]+) fitted by the owner', (str(fig['types']), str(fig['placed']), str(fig['hand']))),
        ('the Extended types as the division record counts them', r'counts the same ([0-9]+) Extended types, ([0-9]+) machine-placed and ([0-9]+) hand-fitted', (str(fig['types']), str(fig['placed']), str(fig['hand']))),
        ('the types the manufacturer places', r'unique Extended types the manufacturer places is ([0-9]+):', (str(fig['placed']),)),
        ('the types and joints the division record counts', r'\(([0-9]+) Extended types, ([0-9]+) of them fitted by the owner, and ([0-9]+) joints\)', (str(fig['types']), str(fig['hand']), str(fig['joints']))),
        ('the layers of the priced board', r'one ([0-9]+)-layer board of', (str(fig['layers']),)),
        ('the layers of the main board section', r'One board, ([0-9]+) layers,', (str(fig['layers']),)),
        ('the number of slots', r'The (\w+) slots are [0-9.]+ mm of slot path', (word(fig['slots']),)),
        ('the area in square centimetres in the large-board charge', r'\(it is ([0-9.]+) cm²\)', (f2(fig['area'] / 100),)),
        ('the area in square centimetres against the large-board limit', r'Neither applies: ([0-9.]+) cm² against', (f2(fig['area'] / 100),)),
        ('the outline coordinates and area after the entry parts', r'outline is still ([0-9.]+) × ([0-9.]+) mm \(X ([0-9.]+) to ([0-9.]+), Y ([0-9.]+) to ([0-9.]+)\), ([0-9 ]+) mm²',
         ('%.1f' % fig['w'], '%.1f' % fig['h'], '%.1f' % fig['x0'], '%.1f' % fig['x1'], '%.1f' % fig['y0'], '%.1f' % fig['y1'], area_s)),
        ('the slot path density of the main and the wall board', r'at ([0-9.]+) and ([0-9.]+) m per m² against the', ('%.1f' % fig['slot_density'], '%.1f' % fig['wall']['slot_density'])),
        ('the Extended types the manufacturer places, in words', r'the (\w+) Extended types \(the microcontroller', (word(fig['placed']),)),
        ('the through-hole Extended types', r'([0-9]+) through-hole Extended types', (str(fig['hand']),)),
        ('the Extended types of the hand-fitted table', r'Hand-fitted parts of the ([0-9]+) types', (str(fig['hand']),)),
        ('the Extended types of the hand-fitted table after the entry parts', r'the ([0-9]+) types of the hand-fitted table', (str(fig['hand']),)),
        ('the feeder loading of the types the manufacturer places', r'([0-9]+) types × ([0-9.]+) \| ([0-9.]+) \|', (str(fig['placed']), f2(fig['ext_econ']), f2(fig['placed'] * fig['ext_econ']))),
        ('the header types', r'(?:and|the|All|The) (\w+) header (?:types|families)', (word(fig['header_types']),)),
        ('the header types of the 2.54 mm pitch', r'the (\w+) 2\.54 mm header types', (word(fig['header_254']),)),
        ('the header part numbers a break-away strip removes', r'removes (\w+) purchased part numbers', (word(fig['header_254'] - 1),)),
        ('the header types and ways', r'Headers for the harnesses, (\w+) types, ([0-9]+) ways', (word(fig['header_types']), str(fig['header_pins']))),
        ('the header ways in the hand-fitted row', r'\| ([0-9]+) ways \| ([0-9]+) ways \|', (str(fig['header_pins']), str(fig['header_pins']))),
        ('the header ways priced', r'estimate: ([0-9]+) × 0\.0204', (str(fig['header_pins']),)),
        ('the pins of the pump opto-triac placed by the manufacturer', r'its ([0-9]+) hand-soldered pins on two boards would be ([0-9.]+) USD', (str(c['pump_opto'][1]), f2(2 * c['pump_opto'][1] * fig['joint_machine']))),
        ('the tabs of the main board', r'\((\w+) tabs and the return landing\)', (word(fig['tabs'] - 1),)),
        ('the joints of the wall board', r'with the ([0-9]+) joints a board of', (str(fig['wall_joints']),)),
        ('the Extended types of the wall board', r'The (\w+) Extended types for this board', (word(fig['wall_types']),)),
        ('the wall board body and span in the configuration', r'([0-9.]+) × ([0-9.]+) mm body with the bracket\'s two mounting ears \(([0-9.]+) mm over all, ([0-9 ]+\.[0-9]) mm²\)',
         ('%.1f' % fig['wall']['w'], '%.1f' % fig['wall']['h'], '%.1f' % fig['wall']['span'], spaced(fig['wall']['area'], 1))),
        ('the wall board body and span in its section', r'([0-9.]+) × ([0-9.]+) mm body with the bracket\'s two mounting ears along its wall edge, ([0-9.]+) mm over all and ([0-9 ]+\.[0-9]) mm²',
         ('%.1f' % fig['wall']['w'], '%.1f' % fig['wall']['h'], '%.1f' % fig['wall']['span'], spaced(fig['wall']['area'], 1))),
        ('the wall board area in the shipping weight', r'× ([0-9 ]+\.[0-9]) / 10 000', (spaced(fig['wall']['area'], 1),)),
        ('the main board fabrication price working', r'([0-9.]+) \+ ([0-9.]+) × ([0-9 ]+[0-9]) / ([0-9 ]+[0-9]) = ([0-9.]+) \+ ([0-9.]+) = ([0-9.]+) USD\. Grade',
         (f2(fig['eng4']), f2(fig['slope4']), area_s, ref_s, f2(fig['eng4']), f2(fig['fab'] - fig['eng4']), f2(fig['fab']))),
        ('the two-layer fallback fabrication price working', r'is ([0-9.]+) \+ ([0-9.]+) × ([0-9 ]+[0-9]) / ([0-9 ]+[0-9]) = ([0-9.]+) \+ ([0-9.]+) = ([0-9.]+) USD by the same inference, ([0-9.]+) USD less',
         (f2(fig['eng2']), f2(fig['slope2']), area_s, ref_s, f2(fig['eng2']), f2(fig['fab2'] - fig['eng2']), f2(fig['fab2']), f2(fig['fab'] - fig['fab2']))),
        ('the main board fabrication price in the first order', r'Fabrication ([0-9.]+) \+ assembly', (f2(fig['fab']),)),
        ('the main board fabrication price in the table by board', r'\| Main board, with the mains-entry parts \| ([0-9.]+) \|', (f2(fig['fab']),)),
        ('the main board fabrication price after the entry parts', r'([0-9.]+) USD for fabrication', (f2(fig['fab']),)),
        ('the main board fabrication price among the marks', r'\| ([0-9.]+) USD inferred, § Main board', (f2(fig['fab']),)),
        ('the saving of the two-layer fallback', r'\| ([0-9.]+) \| ([0-9.]+) − ([0-9.]+); loses', (f2(fig['fab'] - fig['fab2']), f2(fig['fab']), f2(fig['fab2']))),
        ('the shunt count and build quantity', r'Shunt resistor, 2512[^|]*\| none \| Extended \| ([0-9]+) \| ([0-9]+) \|', (str(c['shunt'][0]), str(fig['built'] * c['shunt'][0]))),
        ('the main-board tabs in the build quantities', r'\| C20626104 \| 2 / 4 \| ([0-9]+) main,', (str(c['tab'][0]),)),
    ]
    for part, tag in (('C114409', 'mcu'), ('C256462', 'pump_triac'), ('C108051', 'ac_opto')):
        wanted.append(('the count and build quantity of %s in the parts the manufacturer places' % part, r'\| %s \| Extended \| ([0-9]+) \| ([0-9]+) \|' % part, (str(c[tag][0]), str(fig['built'] * c[tag][0]))))
        wanted.append(('the build quantity of %s in the numbers read' % part, r'\| %s \| [0-9]+ / [0-9]+ \| ([0-9]+) \|' % part, (str(fig['built'] * c[tag][0]),)))
    for part, tag in (('C6280121', 'module'), ('C8965', 'pump_opto'), ('C5318991', 'k_il'), ('C91370', 'valve_relay'), ('C3131', 'holder'), ('C20626104', 'tab')):
        wanted.append(('the count of %s in the parts the owner fits' % part, r'\| %s \| Extended \| ([0-9]+) \|' % part, (str(c[tag][0]),)))
        if tag != 'tab':
            wanted.append(('the one set\'s count of %s in the numbers read' % part, r'\| %s \| [0-9]+ / [0-9]+ \| ([0-9]+) \|' % part, (str(c[tag][0]),)))
    bad = []
    for what, pattern, want in wanted:
        found = [m.groups() for m in re.finditer(pattern, text)]
        if not found:
            bad.append('the cost record does not state %s: the statement the check reads is gone' % what)
        for got in found:
            if tuple(got) != want:
                bad.append('the cost record states %s as %s, the division record\'s check counts %s' % (what, ' / '.join(got), ' / '.join(want)))
    return bad

def check_main(D, text, out, record_dir, src=None, route=True, need=False, whatif=False, proof=False, cost=None):
    bad, prose = [], Prose(text, register=need or whatif)
    if src is None:
        src, sbad = parse_sources(source_texts(record_dir))
        bad += sbad
    bad += check_sources(D, src)
    bad += check_tokens(text, D)
    bad += check_removal_decision(D, text)
    bad += check_earlier_design_terms(text)
    bad += check_entry_statements(text)
    shunt = D.get('return', {}).get('shunt')
    if not shunt or not shunt.get('lands') or not shunt.get('rect') or shunt.get('parts', 0) < 1:
        return bad + ['the neutral return has no current shunt (the data\'s return.shunt is missing, or has no lands, no rectangle or no part), so the supply current has nothing to read it and the record\'s claim that a shunt carries every load\'s return has nothing behind it']
    cav, bas, fx, tb = D['cavity'], D['basis'], D['fixing'], D['tabs']
    bas = dict(bas, basic=bas['m_creepage'])
    keep = fx['E'] + bas['creepage'] + fx['draw_tol']
    pads, strip, bodies, items, pockets = main_model(D)
    mains = [(i, r) for i, r, _, _ in items]
    outline = [tuple(p) for p in D['outline']]
    ob = bbox_of(outline)
    heading = 'The mains-side blocks'
    out.append('sources: separation basis %.1f / %.1f mm (signed clearance and creepage), mains to mains %.1f / %.1f / %.1f mm (clearance, terminal clearance and basic creepage), %d tabs, %d mounting points, the cavity, the reed, intrusion 1, the maker\'s limits and %d load currents read from their records and equal to the data' % (
        bas['clearance'], bas['creepage'], bas['m_clearance'], bas['m_terminal'], bas['basic'], len(src.get('tabs', {})), len(src.get('holes', {})), len(src.get('loads', {}))))
    out.append('assumption tokens: %d of the Assumptions table equal to the data' % len(TOKENS))

    # guard 1: the outline in the cavity, every body in the outline, every height under its ceiling
    mk = cav['maker_tol']
    limit = (mk, mk, cav['w'] - cav['tol'] - mk, cav['h'] - cav['tol'] - mk)
    if not all(limit[0] <= p[0] <= limit[2] and limit[1] <= p[1] <= limit[3] for p in outline):
        bad.append('the outline lies outside the cavity of %.1f x %.1f mm (each +/-%.1f, routed outline +/-%.1f)' % (cav['w'], cav['h'], cav['tol'], mk))
    nominal = (ob[0], cav['w'] - ob[2], ob[1], cav['h'] - ob[3])
    least = min(ob[0] - mk, cav['w'] - cav['tol'] - ob[2] - mk, ob[1] - mk, cav['h'] - cav['tol'] - ob[3] - mk)
    oa = poly_area(outline)
    out.append('outline %.1f x %.1f mm = %.0f mm2; margins left %.1f right %.1f bottom %.1f top %.1f mm, least with tolerances %.1f mm' % (
        ob[2] - ob[0], ob[3] - ob[1], oa, *nominal, least))
    for n, r in bodies.items():
        if not rect_in_poly(r, outline):
            bad.append('%s lies outside the outline' % n)
    for n, r in pads.items():
        if not rect_in_poly(r, outline):
            bad.append('%s lies outside the outline' % padname(n))
    for i, r, _, o in items:
        if not rect_in_poly(r, outline):
            bad.append('the mains copper %s lies outside the outline' % i)
        elif o in bodies and not inside(r, bodies[o]):
            bad.append('the mains copper %s lies outside the body of %s' % (i, o))
    names = list(bodies)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if ov(bodies[a], bodies[b]):
                bad.append('%s and %s overlap' % (a, b))
    edge = min(edge_distance(r, outline) for r in list(bodies.values()) + list(pads.values()))
    if edge < bas['edge_min'] - EPS:
        bad.append('a block or pad stands %.2f mm from the board edge, the least allowed is %.1f' % (edge, bas['edge_min']))
    sums = (sum(area(bodies[b['id']]) for b in D['mains_blocks']) + area(strip), sum(area(tuple(b['rect'])) for b in D['lv_blocks']), area(bodies['REED']))
    out.append('%d blocks inside the outline, the nearest %.1f mm from its edge, none overlapping: mains-side %.0f + low-voltage %.0f + reed keep-out %.0f = %.0f mm2, %.0f %% of the outline' % (
        len(bodies), edge, *sums, sum(sums), sum(sums) / oa * 100))
    thou = lambda x: '{:,.0f}'.format(x).replace(',', ' ')
    prose.mention('The low-voltage blocks', 'The mains-side bodies total %s mm²' % thou(sums[0]))
    prose.mention('The low-voltage blocks', 'the low-voltage blocks %s mm²' % thou(sums[1]))
    prose.mention('The low-voltage blocks', '%s mm² of the %s mm² outline, %.0f %%' % (thou(sum(sums)), thou(oa), sum(sums) / oa * 100))
    prose.mention('The low-voltage blocks', 'leaving %s mm² for routing' % thou(oa - sum(sums)))
    prose.mention('Candidate divisions', 'Blocks fill %s of %s mm² (%.0f %%)' % (thou(sum(sums)), thou(oa), sum(sums) / oa * 100))
    prose.mention('Candidate divisions', '%s of 15 690 mm² (%.0f %%)' % (thou(sum(sums)), sum(sums) / 15690.0 * 100))
    c = D['ceiling']
    heights = [(b['id'], tuple(b['body']), b['h'], 'mains') for b in D['mains_blocks']] + [(b['id'], tuple(b['rect']), b['h'], 'lv') for b in D['lv_blocks'] if b.get('h')]
    heights.append(('TABS', strip, tb['height'], 'tab'))
    margins = {}
    for n, r, h, kind in heights:
        wall = min(r[0], r[1], cav['w'] - r[2], cav['h'] - r[3])
        ceiling = c['edge'] if wall <= c['edge_band'] + EPS else c['interior']
        if h > ceiling:
            bad.append('%s stands %.1f mm high under a ceiling of %.1f mm' % (n, h, ceiling))
        key = 'MODULE' if n == 'MODULE' else 'Relays' if n.startswith('K_') else 'Tabs' if n == 'TABS' else 'Fuse holders' if n in ('VFUSE', 'P_C', 'P_S') else 'Harness headers' if kind == 'lv' else None
        if key:
            margins[key] = min(margins.get(key, 99), ceiling - h)
    out.append('heights: %d parts, least margin %.1f mm' % (len(heights), min(margins.values())))
    for key, m in margins.items():
        prose.expect('Heights, the underside, and hand access', key, 3, '%.1f' % m)

    # guard 2: the tabs, against the connector record's rows
    tl = sorted(tb['list'], key=lambda x: x['y'])
    pitch = min(tl[i + 1]['y'] - tl[i]['y'] for i in range(len(tl) - 1))
    if pitch < tb['pitch'] - EPS:
        bad.append('tab pitch %.2f mm, least allowed %.1f' % (pitch, tb['pitch']))
    moves = {x['n']: x['y'] - x['found'] for x in tb['list']}
    for n, m in moves.items():
        if abs(m) > tb['slack_estimate']:
            bad.append('tab %d moves %.1f mm, past the owner\'s estimate of %.0f mm' % (n, m, tb['slack_estimate']))
    named = sorted(n for n, m in moves.items() if abs(m) > EPS)
    slack = {n: tb['slack_estimate'] - abs(moves[n]) for n in named}
    out.append('tabs: %d pads and the return landing inside the outline, least pitch %.1f mm, moves %s mm, slack left %s mm, strip X %.1f to %.1f Y %.1f to %.1f' % (
        len(pads) - 1, pitch, ' '.join('%+.1f' % moves[n] for n in named), ' '.join('%.1f' % slack[n] for n in named), strip[0], strip[2], strip[1], strip[3]))
    found_pads = tab_pads(D, found=True)
    fixing = 'The fixing rule and the tabs that move'
    for n in named:
        x = [t for t in tb['list'] if t['n'] == n][0]
        prose.expect(fixing, str(n), 1, '%.1f' % x['found'])
        nearest = min(D['holes'].values(), key=lambda c: rd(pt(c), found_pads[n]))
        prose.expect(fixing, str(n), 2, '%.2f' % rd(pt(nearest), found_pads[n]))
        prose.expect(fixing, str(n), 3, '%.2f' % rd(pt(nearest), pads[n]))
        prose.expect(fixing, str(n), 4, '%.1f' % x['y'])
        prose.expect(fixing, str(n), 5, '%+.1f' % moves[n])
        prose.expect(fixing, str(n), 6, '%.1f' % slack[n])
        prose.expect('Every retained harness reaches its connector', str(n), 2, '%.1f' % x['found'])
        prose.expect('Every retained harness reaches its connector', str(n), 3, '%.1f' % x['y'])

    # guard 3: every hole against mains copper and bodies
    near = {}
    for h, ctr in D['holes'].items():
        near[h] = min(rd(pt(ctr), r) for _, r in mains)
        if near[h] < keep - EPS:
            bad.append('mains copper %.2f mm from %s, the rule is %.2f' % (near[h], h, keep))
        for n, r in list(bodies.items()) + [(padname(k), v) for k, v in pads.items()]:
            if rd(pt(ctr), r) < fx['lid_keep'] - EPS:
                bad.append('%s lies inside the %.1f mm keep-out of %s' % (n, fx['lid_keep'], h))
    out.append('mains copper to the mounting holes, rule %.2f mm: %s' % (keep, ', '.join('%s %.2f' % (h, m) for h, m in near.items())))
    for h, ctr in D['holes'].items():
        row = {'P1': 'Point 1, lid screw', 'P2': 'Point 2, lid screw', 'P3': 'Point 3', 'P4': 'Point 4'}[h]
        prose.expect('Outline, fixings and margins', row, 1, '(%.1f, %.1f)' % tuple(ctr))
        prose.expect('Outline, fixings and margins', row, 3, ('%.1f left' % (ctr[0] - ob[0])) if ctr[0] < 60 else ('%.1f right' % (ob[2] - ctr[0])))
        prose.expect('Outline, fixings and margins', row, 4, ('%.2f' if h in ('P1', 'P3') else '%.1f') % near[h])
    lo, up, box, strip_zone = reed_zone(D)

    # guard 4: the reed
    rd_ = D['reed']
    if math.hypot(lo[0] - rd_['recorded'][0], lo[1] - rd_['recorded'][1]) > rd_['tol'] + EPS:
        bad.append('the reed\'s lower lead (%.1f, %.1f) is more than %.1f mm from the recorded (%.1f, %.1f)' % (*lo, rd_['tol'], *rd_['recorded']))
    mid = (lo[0], (lo[1] + up[1]) / 2)
    if math.hypot((box[0] + box[2]) / 2 - mid[0], (box[1] + box[3]) / 2 - mid[1]) > 0.05:
        bad.append('the reed keep-out is not centred on the element\'s midpoint')
    for p in (lo, up):
        if not in_poly(p, outline):
            bad.append('a reed pad lies outside the outline')
    for n, r in [(a, b) for a, b in bodies.items() if a != 'REED'] + [(padname(k), v) for k, v in pads.items()]:
        if reed_hits(D, r):
            bad.append('%s lies inside the reed keep-out' % n)
    for h, ctr in D['holes'].items():
        if min(math.hypot(ctr[0] - p[0], ctr[1] - p[1]) for p in (lo, up)) < rd_['hand_r'] + fx['lid_keep'] - EPS:
            bad.append('the reed keep-out reaches the lid-screw circle of %s' % h)
    out.append('reed: lower lead (%.1f, %.1f), upper lead (%.1f, %.1f), midpoint (%.1f, %.1f), keep-out X %.1f to %.1f Y %.1f to %.1f, clear of every block' % (
        *lo, *up, *mid, box[0], box[2], box[1], box[3]))
    prose.expect('The low-voltage blocks', 'REED', 2, rng(box[0], box[2]))
    prose.expect('The low-voltage blocks', 'REED', 3, rng(box[1], box[3]))

    # guard 5: mains against low voltage, and mains against mains, by straight distance and by the surface path round the slots
    slots = D['slots']
    sr = slot_rects(slots)
    sc = D['slot_copper']
    for s in slots:
        r = tuple(s['rect'])
        if min(r[2] - r[0], r[3] - r[1]) < D['slot_width_min'] - EPS:
            bad.append('slot %s is narrower than %.1f mm' % (s['id'], D['slot_width_min']))
        if not inside(r, (ob[0], ob[1], ob[2], ob[3])) or not rect_in_poly(r, outline):
            bad.append('slot %s lies outside the outline' % s['id'])
        for n, rr in mains + pockets + [(b['id'], tuple(b['rect'])) for b in D['lv_blocks']] + [(padname(k), v) for k, v in pads.items()]:
            if ov(grow(r, sc), rr):
                bad.append('slot %s cuts the copper of %s' % (s['id'], n))
    lv_least = min(rd(tuple(b['rect']), r) for b in D['lv_blocks'] for _, r in mains)
    for b in D['lv_blocks']:
        d = min(rd(tuple(b['rect']), r) for _, r in mains)
        if d < bas['creepage'] - EPS:
            bad.append('the low-voltage block %s is %.1f mm from mains copper' % (b['id'], d))
    dips = {b['id'] for b in D['mains_blocks'] if b.get('dip')}
    straight, path, pairs = math.inf, math.inf, 0
    for a, m in [(o, r) for _, r, _, o in items]:
        for b, p in pockets:
            if a == b and a in dips:
                continue
            d = rd(m, p)
            straight = min(straight, d)
            if d < bas['clearance'] - EPS:
                bad.append('the pocket of %s is %.2f mm from the mains copper of %s, the clearance is %.1f' % (b, d, a, bas['clearance']))
            if d < bas['creepage'] - EPS:
                pairs += 1
                L = surface_path(m, p, sr, bas['creepage'], outline)
                path = min(path, L)
                if L < bas['creepage'] - 0.05:
                    bad.append('surface path of %.1f mm between the mains copper of %s and the pocket of %s, creepage is %.1f' % (L, a, b, bas['creepage']))
    pins = dip_paths(D['mains_blocks'], sr, 12.0, outline)
    for n, L in pins.items():
        path = min(path, L)
        if L < bas['creepage'] - 0.05:
            bad.append('opto-coupler %s: pin-to-pin surface path of %.1f mm, creepage is %.1f' % (n, L, bas['creepage']))
    out.append('low voltage to mains copper: least %.1f mm of %.1f; pockets to mains copper: least straight %.1f mm of %.1f, %d pairs under %.1f mm straight all held by slots, least surface path %.1f mm of %.1f' % (
        lv_least, bas['creepage'], straight, bas['clearance'], pairs, bas['creepage'], path, bas['creepage']))
    out.append('opto-coupler pin-to-pin paths round the slots: ' + ', '.join('%s %.1f mm' % (n, L) for n, L in pins.items()))
    plen = sum(max(s['rect'][2] - s['rect'][0], s['rect'][3] - s['rect'][1]) for s in slots)
    if plen * 1000.0 / oa > D['slot_density']:
        bad.append('slot path of %.1f m per m2 reaches the maker\'s %.0f m per m2' % (plen * 1000.0 / oa, D['slot_density']))
    out.append('slots: %d of %.0f mm of slot path = %.1f m per m2 of board, against %.0f' % (len(slots), plen, plen * 1000.0 / oa, D['slot_density']))
    reinforced = ([D['open_contact']['nets'][0]] + list(D['open_contact'].get('upstream', [])), D['open_contact']['nets'][1])
    names = {x['name'] for x in tb['list']}
    if D['open_contact']['nets'][0] not in names or reinforced[1] not in names:
        bad.append('the open contact is between nets %s that are not among the tabs the connector record names' % D['open_contact']['nets'])
    pb, mm, pp, npairs, nre = pair_rule(items, sr, bas, reinforced, outline)
    bad += pb
    across = min(rd(ra, rb) for a, ra, na, oa in items for b, rb, nb, ob in items if upstream_of(reinforced, na) and nb == reinforced[1])
    zb = 'Zones and the barrier'
    prose.mention(zb, 'the eight slots are %.0f mm of slot path' % plen)
    prose.mention(zb, '%.1f m of slot path per m²' % (plen * 1000.0 / oa))
    prose.mention(zb, '%d pocket-to-mains pairs stand under %.1f mm apart in a straight line, from %.1f mm' % (pairs, bas['creepage'], straight))
    prose.mention(zb, 'every one is held by a slot, the least surface path being %.1f mm' % path)
    prose.mention(zb, 'are %.1f mm (TIMING), %.1f mm (VMEAS) and %.1f mm (P_C and P_S' % (pins['TIMING'], pins['VMEAS'], pins['P_C']))
    prose.mention(zb, '%d pairs of mains copper of different nets, from different parts, stand nearer than the creepage their rule asks, %d of them across the open contact' % (npairs, nre))
    prose.mention(zb, 'held by distance or by a slot, the least surface path being %.1f mm' % pp)
    prose.mention(zb, 'every mains copper rectangle (the least, %.1f mm)' % lv_least)
    prose.mention(zb, '(the least, %.1f mm straight and %.1f mm by path)' % (straight, path))
    prose.mention(zb, '(the least, %.1f mm straight and %.1f mm by path)' % (mm, pp))
    out.append('mains copper of different nets, from different parts: least straight %.1f mm of %.1f, %d pairs under the basic creepage of %.1f mm by straight line, all held by distance or slots, least surface path %.1f mm of %.1f (%d of them across the open interlock contact, where the rule is the signed %.1f mm: least straight %.1f mm)' % (
        mm, bas['m_clearance'], npairs, bas['basic'], pp, bas['basic'], nre, bas['creepage'], across))

    # the interlock's link: the copper between tab 2 and tab 1 through the relay's contact, its loss and its taps
    L = D['link']
    cur, bud = D['loads'], L
    behind = cur['coffee'] + cur['steam'] + cur['coffee_pump'] + cur['steam_pump']
    total_steady = behind + cur['coil_steady']
    total_inrush = behind + cur['coil_inrush']
    tabs_by_net = {x['name']: x['n'] for x in tb['list']}
    ids = {i: (r, net) for i, r, net, _ in items}
    regions, prev, squares = [], None, 0.0
    for k, step in enumerate(L['chain']):
        if 'contact' in step or 'fuse' in step:
            prev = None
            continue
        r = tuple(step['rect'])
        host = ids.get(step['in'])
        if host is None or not inside(r, host[0]):
            bad.append('the link region %s does not lie inside the mains copper %s' % (step['id'], step['in']))
        if prev is not None and rd(prev, r) > 1e-6:
            bad.append('the link region %s does not touch the one before it' % step['id'])
        length, width = ((r[2] - r[0]), (r[3] - r[1])) if step['axis'] == 'x' else ((r[3] - r[1]), (r[2] - r[0]))
        if width < 0.381 * cur['overload'] - EPS:
            bad.append('the link region %s is %.2f mm wide, %.2f A needs %.2f' % (step['id'], width, cur['overload'], 0.381 * cur['overload']))
        squares += length / width
        regions.append((step['id'], length, width))
        prev = r
    contacts = [(i_, s['contact']) for i_, s in enumerate(L['chain']) if 'contact' in s]
    if len(contacts) != 1 or contacts[0][1] != 'K_IL':
        bad.append('the link passes %s, and the interlock\'s contact is the one of K_IL, between the copper on LINE and the copper on LINE1' % (('the contact of %s' % ', '.join(repr(c) for _, c in contacts)) if contacts else 'no relay contact'))
    else:
        i_c = contacts[0][0]
        around = [L['chain'][i_c - 1].get('in') if i_c > 0 else None, L['chain'][i_c + 1].get('in') if i_c + 1 < len(L['chain']) else None]
        if around != ['K_IL.a', 'K_IL.b']:
            bad.append('the contact of K_IL does not stand between its two halves, K_IL.a on LINE and K_IL.b on LINE1, in the link: it stands between %s and %s' % tuple(around))
    k_il_part = [b for b in D['mains_blocks'] if b['id'] == 'K_IL']
    if not k_il_part or not any(t == 'k_il' for t, _ in k_il_part[0].get('fit', [])):
        bad.append('the block K_IL is not fitted with the interlock relay part')
    first, last = [s for s in L['chain'] if 'rect' in s][0], [s for s in L['chain'] if 'rect' in s][-1]
    E = D['entry']
    fuse_steps = [i_ for i_, s in enumerate(L['chain']) if 'fuse' in s]
    if fuse_steps != [0] or L['chain'][0]['fuse'] != E['fuse']:
        bad.append('the link does not begin with the entry fuse %s: it passes %s' % (E['fuse'], ', '.join(repr(L['chain'][i_]['fuse']) for i_ in fuse_steps) if fuse_steps else 'no fuse'))
    host = ids.get(last['in'])
    pad = pads[tabs_by_net['LINE1']]
    if host is None or host[1] != 'LINE1' or not inside(pad, host[0]) or abs(last['rect'][0] - tb['x']) > EPS:
        bad.append('the link does not end at the LINE1 tab\'s pad: its end region %s does not hold the pad of that tab and its centre' % last['id'])
    if first['in'] != E['load'] or ids.get(first['in'], (None, None))[1] != 'LINE':
        bad.append('the link does not leave the entry fuse from its load-side piece %s on the net LINE: its first region %s is in %s' % (E['load'], first['id'], first['in']))
    fb_ = [b for b in D['mains_blocks'] if b['id'] == E['fuse']]
    if not fb_:
        bad.append('the entry fuse %s is not a block of the floorplan' % E['fuse'])
    else:
        fbody = tuple(fb_[0]['body'])
        fdims = sorted((fbody[2] - fbody[0], fbody[3] - fbody[1]))
        if abs(fdims[0] - min(D['fuse']['holder'])) > EPS or abs(fdims[1] - max(D['fuse']['holder'])) > EPS:
            bad.append('the entry fuse holder %s is %.1f x %.1f mm, the 10 A holder is %.1f x %.1f (A6)' % (E['fuse'], fdims[1], fdims[0], max(D['fuse']['holder']), min(D['fuse']['holder'])))
        fm = {m[0]: (tuple(m[1]), m[2]) for m in fb_[0]['mains']}
        line_net = tab_nets(D)[tabs_by_net['LINE']]
        if E['line'] not in fm or fm[E['line']][1] != line_net:
            bad.append('the entry fuse\'s line-side clip %s is not on %s, the net of the pad of tab %d' % (E['line'], line_net, tabs_by_net['LINE']))
        if E['load'] not in fm or fm[E['load']][1] != 'LINE':
            bad.append('the entry fuse\'s load-side clip %s is not on the net LINE that the link and the taps are on' % E['load'])
        if E['load'] in fm and E['line'] in fm and rd(fm[E['load']][0], fm[E['line']][0]) < D['fuse']['holder'][1] - EPS:
            bad.append('the entry fuse\'s two clips stand %.1f mm apart, under the holder\'s width' % rd(fm[E['load']][0], fm[E['line']][0]))
        tap_pad = pads[tabs_by_net['LINE']]
        side = [(i_, r_) for i_, r_, n_, o_ in items if n_ == line_net and inside(tap_pad, r_)]
        if not side:
            bad.append('the pad of tab %d does not lie inside copper of the net %s that the entry fuse\'s line-side clip is joined to' % (tabs_by_net['LINE'], line_net))
        if line_net not in reinforced[0]:
            bad.append('the pad of tab %d is on %s, which the open contact\'s upstream nets %s do not name, so its copper would be held to the basic creepage from LINE1' % (tabs_by_net['LINE'], line_net, reinforced[0]))
        if line_net not in D.get('inner_nets', []):
            bad.append('the pad of tab %d and the fuse\'s line-side clip are on the net %s, which the data does not give as joined by an inner layer' % (tabs_by_net['LINE'], line_net))
        if any(t_['net'] == line_net for t_ in L['taps']):
            bad.append('a tap leaves the net %s upstream of the entry fuse' % line_net)
        vb = [b for b in D['mains_blocks'] if b['id'] == E['varistor']]
        if not vb:
            bad.append('the entry varistor %s is not a block of the floorplan' % E['varistor'])
        else:
            vm_ = {m[0]: (tuple(m[1]), m[2]) for m in vb[0]['mains']}
            vl, vn = vm_.get(E['varistor_line']), vm_.get(E['varistor_neutral'])
            if vl is None or vn is None:
                bad.append('the entry varistor %s lacks its line pad %s or its neutral pad %s' % (E['varistor'], E['varistor_line'], E['varistor_neutral']))
            else:
                if vl[1] != 'LINE':
                    bad.append('the varistor\'s line pad %s is on the net %s and not on the net LINE downstream of the fuse' % (E['varistor_line'], vl[1]))
                if vn[1] != 'NEUTRAL':
                    bad.append('the varistor\'s neutral pad %s is on the net %s and not on NEUTRAL' % (E['varistor_neutral'], vn[1]))
                piece = {E['load']}
                grew = True
                same = [(i_, r_) for i_, r_, n_, o_ in items if n_ == 'LINE']
                while grew:
                    grew = False
                    for i_, r_ in same:
                        if i_ not in piece and any(rd(r_, r2_) < 1e-6 for j_, r2_ in same if j_ in piece):
                            piece.add(i_)
                            grew = True
                if E['varistor_line'] not in piece:
                    bad.append('the varistor\'s line pad %s is not on the same piece of copper as the entry fuse\'s load-side clip %s: it is on %s' % (E['varistor_line'], E['load'], 'the net ' + vl[1] if vl[1] != 'LINE' else 'a separate piece of LINE'))
                against = rd(vl[0], fm[E['load']][0]) if E['load'] in fm else math.inf
                if against > E['against_mm'] + EPS:
                    bad.append('the varistor\'s line pad stands %.1f mm from the fuse\'s load-side clip, the limit for hard against the fuse is %.1f' % (against, E['against_mm']))
                out.append('entry fuse %s: %.1f x %.1f mm holder, 10 A, in series between the pad of tab %d (%s) and the link (LINE); varistor %s, its line pad on the fuse\'s load-side piece %.1f mm from the clip (limit %.1f) and its neutral pad on NEUTRAL, %.1f mm from the line pad' % (
                    E['fuse'], fdims[1], fdims[0], tabs_by_net['LINE'], line_net, E['varistor'], against, E['against_mm'], rd(vl[0], vn[0])))
    kil = [b for b in D['mains_blocks'] if b['id'] == 'K_IL'][0]
    tm = kil['terminals']
    ring = D['maker']['ring']
    lower, upper = tm['centre_y'] - tm['pitch_y'] / 2, tm['centre_y'] + tm['pitch_y'] / 2
    cop = {m[0]: tuple(m[1]) for m in kil['mains']}
    for name, y, net in (('K_IL.b', lower, 'LINE1'), ('K_IL.a', upper, 'LINE')):
        rect = cop[name]
        if [m[2] for m in kil['mains'] if m[0] == name][0] != net:
            bad.append('the contact terminal at Y %.2f is on %s, which is not the net %s of the interlock\'s %s side' % (y, name, net, 'input' if net == 'LINE' else 'output'))
        for lx in tm['legs_x']:
            r_ = tm['hole'] / 2 + ring
            if not (rect[0] <= lx - r_ + EPS and lx + r_ <= rect[2] + EPS and rect[1] <= y - r_ + EPS and y + r_ <= rect[3] + EPS):
                bad.append('the leg at (%.2f, %.2f) of the interlock relay\'s contact terminal does not stand %.2f mm (its hole\'s radius and the maker\'s annular ring) inside the copper %s' % (lx, y, r_, name))
            if [lx, y] not in [list(p) for p in kil['pins']] and not any(abs(p[0] - lx) < EPS and abs(p[1] - y) < EPS for p in kil['pins']):
                bad.append('the leg at (%.2f, %.2f) of the interlock relay is not among its pins' % (lx, y))
    for p in ([(tm['coil_x'], tm['centre_y'] - tm['pitch_y'] / 2), (tm['coil_x'], tm['centre_y'] + tm['pitch_y'] / 2)]):
        if not any(abs(q[0] - p[0]) < EPS and abs(q[1] - p[1]) < EPS for q in kil['pins']):
            bad.append('the coil pin at (%.2f, %.2f) of the interlock relay is not among its pins' % p)
    if len(kil['pins']) != 2 * len(tm['legs_x']) + 2:
        bad.append('the interlock relay has %d pins in the data, the sheet has %d holes' % (len(kil['pins']), 2 * len(tm['legs_x']) + 2))
    hp = kil['pockets'][0]
    if abs((hp[3] - hp[1]) - tm['body_w']) > EPS or abs((hp[1] + hp[3]) / 2 - tm['centre_y']) > EPS:
        bad.append('the interlock relay\'s coil pocket is not the %g mm body centred on the contact terminals' % tm['body_w'])
    if not inside(tuple(kil['heat']), tuple(kil['body'])):
        bad.append('the interlock relay\'s heat rectangle lies outside its block')
    out.append('interlock relay terminals (P2): contact tabs %.2f mm apart across the body, each on two %g mm holes %g mm apart along it (X %s), at Y %.2f on LINE1 and %.2f on LINE; coil holes at X %g; every leg stands %.2f mm inside its copper' % (
        tm['pitch_y'], tm['hole'], abs(tm['legs_x'][1] - tm['legs_x'][0]), ' and '.join('%g' % x for x in tm['legs_x']), lower, upper, tm['coil_x'], tm['hole'] / 2 + ring))
    r_link = squares * D['wall']['sheet_mohm']
    loss = lambda i: r_link * i * i / 1000.0
    narrow = min(w for _, _, w in regions)
    if loss(cur['coffee'] + cur['steam']) > L['budget_w'] + EPS:
        bad.append('the link\'s copper loses %.2f W at %.2f A, the budget is %.1f W' % (loss(cur['coffee'] + cur['steam']), cur['coffee'] + cur['steam'], L['budget_w']))
    if loss(total_steady) > L['budget_w'] + EPS:
        bad.append('the link\'s copper loses %.2f W at %.2f A, the budget is %.1f W' % (loss(total_steady), total_steady, L['budget_w']))
    out.append('link LINE to LINE1 through K_IL: %d copper regions, %.2f squares = %.2f mohm, narrowest %.2f mm (15 A needs %.2f); loss %.2f W at %.2f A, %.2f W at %.2f A (all loads steady), %.2f W at %.0f A, against a budget of %.1f W' % (
        len(regions), squares, r_link, narrow, 0.381 * cur['overload'], loss(cur['coffee'] + cur['steam']), cur['coffee'] + cur['steam'], loss(total_steady), total_steady, loss(cur['overload']), cur['overload'], L['budget_w']))
    sec_il = 'The interlock block, its size and its place'
    prose.expect(sec_il, 'Link copper', 1, '%.2f squares' % squares)
    prose.expect(sec_il, 'Link copper', 1, '%.2f mΩ' % r_link)
    prose.expect(sec_il, 'Link loss', 1, '%.2f W at %.2f A' % (loss(cur['coffee'] + cur['steam']), cur['coffee'] + cur['steam']))
    prose.expect(sec_il, 'Link loss', 1, '%.2f W at %.2f A' % (loss(total_steady), total_steady))
    prose.expect(sec_il, 'Link loss', 1, '%.2f W at %.0f A' % (loss(cur['overload']), cur['overload']))
    fb = D['fallback']
    fb_run = (bodies[fb['anchor']][1] + bodies[fb['anchor']][3]) / 2 - (pads[tabs_by_net['LINE']][1] + pads[tabs_by_net['LINE']][3]) / 2
    fb_sq = 2 * fb_run / fb['width']
    fb_loss = fb_sq * D['wall']['sheet_mohm'] * total_steady ** 2 / 1000.0
    out.append('dropped option, the relay in the top relay place (%s): two runs of %.0f mm of %.1f mm pour, %.1f squares = %.1f mohm, %.2f W at %.2f A against the budget of %.1f W' % (
        fb['anchor'], fb_run, fb['width'], fb_sq, fb_sq * D['wall']['sheet_mohm'], fb_loss, total_steady, L['budget_w']))
    prose.expect('Options considered and dropped', 'The interlock relay in the top relay place', 1, '%.2f W at %.2f A' % (fb_loss, total_steady))
    prose.expect('Options considered and dropped', 'The interlock relay in the top relay place', 1, '%.1f squares' % fb_sq)
    if fb_loss <= L['budget_w']:
        bad.append('the relay in the top relay place would lose %.2f W in its link, inside the budget, and the option is recorded as dropped for its loss' % fb_loss)
    taps = []
    for t in L['taps']:
        host = ids.get(t['from'])
        if host is None or host[1] != t['net']:
            bad.append('the tap from %s is not on the net %s' % (t['from'], t['net']))
        for to in t['to']:
            if to not in bodies:
                bad.append('the tap %s feeds %s, which is not a block' % (t['from'], to))
            elif t['net'] not in [n for _, _, n2, o2 in items if o2 == to for n in n2.split('|')]:
                bad.append('the block %s is not on the net %s that the tap %s gives it' % (to, t['net'], t['from']))
            taps.append((t['net'], to))
    if any(net == 'LINE1' for net, _ in taps):
        bad.append('a tap leaves the LINE1 net, which the interlock contact cuts')
    on_line1 = sorted({o for i, r, net, o in items if 'LINE1' in net.split('|')})
    if on_line1 != sorted(['K_IL', 'tab %d' % tabs_by_net['LINE1'], 'LK_L1']):
        bad.append('the LINE1 net reaches %s, the connector record has nothing else on the board connect to LINE1' % on_line1)
    out.append('taps upstream of the contact: %s; the LINE1 net reaches only %s' % (', '.join('%s to %s' % (n, t) for n, t in taps), ' and '.join(on_line1)))
    rl = D['relay']
    margin = lambda i: rl['rating_a'] / i
    out.append('relay K_IL behind it: %.2f A steady and %.2f A with the valve coils at their inrush (%.2f A of elements, %.2f A of pumps), against %.0f A: margins %.2f and %.2f, %.2f at the %.0f A overload band; electrical endurance %d operations at %.0f A resistive (P2)' % (
        total_steady, total_inrush, cur['coffee'] + cur['steam'], cur['coffee_pump'] + cur['steam_pump'], rl['rating_a'], margin(total_steady), margin(total_inrush), margin(cur['overload']), cur['overload'], rl['endurance_ops'], rl['rating_a']))
    wb = D['wall']['budgets']
    el = cur['coffee'] + cur['steam']
    v5 = D['rail']['volts']
    r_contact = wb['relay_contact_w'] / el ** 2 * 1e3
    contact_w = r_contact * total_steady ** 2 / 1e3
    coil_nom, coil_low = v5 ** 2 / rl['coil_ohm'], v5 ** 2 / (rl['coil_ohm'] * (1 - rl['coil_tol']))
    if abs(coil_nom - wb['relay_coil_w']) > 0.01:
        bad.append('the interlock relay\'s coil is %.3f W at %g ohm and 5 V, the budget says %g W' % (coil_nom, rl['coil_ohm'], wb['relay_coil_w']))
    il_nom, il_max = wb['relay_coil_w'] + contact_w, coil_low + contact_w
    out.append('relay K_IL heat: coil %.1f W (%.3f W with the coil %.0f %% under %g ohm); contacts %.1f W at %.2f A (%.1f mohm, %.0f mV; %.2f W at %.2f A), so %.2f W and %.2f W at the coil\'s low tolerance; unsourced worst case at 100 mohm: %.1f W at %.2f A' % (
        wb['relay_coil_w'], coil_low, rl['coil_tol'] * 100, rl['coil_ohm'], wb['relay_contact_w'], el, r_contact, r_contact * el, contact_w, total_steady, il_nom, il_max, 0.1 * el ** 2, el))
    # the neutral return: tab 3's pad, the shunt, the pour that holds the landing; every other neutral branch leaves the pour
    RT = D['return']
    lands = {i: tuple(r) for i, r in RT['shunt']['lands']}
    la, lb = [i for i, _ in RT['shunt']['lands']]
    pour, shr = tuple(RT['pour']['rect']), tuple(RT['shunt']['rect'])
    nt = tabs_by_net['NEUTRAL']
    if rd(pads[nt], lands[la]) > 1e-6:
        bad.append('the shunt\'s first land does not touch the pad of tab %d' % nt)
    if rd(lands[lb], pour) > 1e-6:
        bad.append('the shunt\'s second land does not touch the neutral pour')
    if not inside(pads['R'], pour):
        bad.append('the return landing\'s pad does not lie inside the neutral pour')
    if not (inside(lands[la], shr) and inside(lands[lb], shr)):
        bad.append('a shunt land lies outside the shunt')
    for nm, r in [(RT['pour']['id'], pour)] + list(lands.items()):
        if r[2] - r[0] < 0.381 * cur['overload'] - EPS:
            bad.append('the neutral return copper %s is %.2f mm wide, %.0f A needs %.2f' % (nm, r[2] - r[0], cur['overload'], 0.381 * cur['overload']))
    land_pitch = min(abs(RT['landing']['y'] - t['y']) for t in tb['list'])
    if land_pitch < tb['pitch'] - EPS:
        bad.append('the return landing stands %.2f mm from the nearest tab, the least pitch is %.1f' % (land_pitch, tb['pitch']))
    if RT['landing']['net'] != 'NEUTRAL' or RT['pour']['net'] != 'NEUTRAL':
        bad.append('the return landing and its pour are not on the net NEUTRAL')
    if not any(t['from'] == RT['pour']['id'] and t['net'] == 'NEUTRAL' for t in L['taps']):
        bad.append('the neutral taps do not leave from the pour above the shunt')
    _, rail_ma, _ = rail_rows(D)
    mod_ch = [m for m in D['rail']['modules'] if m.get('chosen')][0]
    module_a = D['rail']['volts'] * rail_ma / 1000.0 / mod_ch['eff'] / (RT['module_pf'] * D['valve_relay']['span_top'])
    pieces = {i: net for i, _, net, _ in items}
    amps_of = lambda key: module_a if key == 'module' else cur[key]
    plug_side = 'the pad of tab %d' % nt
    expected_loads = {'coffee', 'steam', 'coffee_pump', 'steam_pump', 'coil_steady', 'module'}
    if sorted(b['amps'] for b in RT['branches']) != sorted(expected_loads):
        bad.append('the returns the data gives are of %s, and the loads that return through the neutral are %s' % (sorted(b['amps'] for b in RT['branches']), sorted(expected_loads)))
    neutral_a = 0.0
    for b in RT['branches']:
        if pieces.get(b['via']) != 'NEUTRAL':
            bad.append('the return of the %s does not end on copper of the net NEUTRAL (%s is %s)' % (b['load'], b['via'], pieces.get(b['via'], 'not copper of the data')))
        if b.get('layer') not in ('surface', 'inner'):
            bad.append('the return of the %s gives no layer for its join to the neutral pour' % b['load'])
        if b['joins'] == RT['pour']['id']:
            neutral_a += amps_of(b['amps'])
        elif b['joins'] in (plug_side, 'tab %d' % nt):
            bad.append('the return of the %s joins at %s, on the plug side of the shunt: its current never passes the shunt, so a stuck-on triac would not show in the supply current' % (b['load'], plug_side))
        else:
            bad.append('the return of the %s joins at %s and not at the neutral pour %s above the shunt: its current would not pass the shunt' % (b['load'], b['joins'], RT['pour']['id']))
    if abs(neutral_a - (total_steady + module_a)) > 1e-9:
        bad.append('the shunt carries %.2f A of the returns that join above it and every load on returns %.2f A' % (neutral_a, total_steady + module_a))
    prose.mention('The path of the heater current', '%.2f A in all with every load on' % neutral_a)
    shunt_w = lambda i: wb['sensor_mohm'] * i * i / 1000.0
    vm = [b for b in D['mains_blocks'] if b['id'] == 'VMEAS'][0]
    if not any(m[2] == 'NEUTRAL' for m in vm['mains']):
        bad.append('VMEAS has no mains piece on NEUTRAL, the reference the shunt channel shares with the voltage divider')
    out.append('neutral return: the landing\'s pad at Y %.1f stands %.1f mm from the nearest tab; the shunt (%.1f mohm, %d parts side by side, X %.1f to %.1f, Y %.1f to %.1f) stands between the pad of tab %d and the pour, which is %.1f mm wide against the %.2f mm that %.0f A needs; the neutral carries %.2f A with every load on (the link\'s %.2f A and the module\'s %.2f A at the assumed power factor %.1f): shunt loss %.2f W, %.2f W at %.0f A' % (
        RT['landing']['y'], land_pitch, wb['sensor_mohm'], RT['shunt']['parts'], shr[0], shr[2], shr[1], shr[3], nt, pour[2] - pour[0], 0.381 * cur['overload'], cur['overload'],
        neutral_a, total_steady, module_a, RT['module_pf'], shunt_w(neutral_a), shunt_w(cur['overload']), cur['overload']))
    sec_h = 'The interlock block, its size and its place'
    prose.expect(sec_h, 'Contact heat', 1, '%.2f W' % contact_w)
    prose.expect(sec_h, 'Contact heat', 1, '%.1f W at %.2f A' % (0.1 * el ** 2, el))
    prose.expect(sec_h, 'Coil', 1, '%.3f W' % coil_low)
    if total_inrush > rl['rating_a'] or cur['overload'] > rl['rating_a']:
        bad.append('the loads behind K_IL exceed its contact rating')
    prose.expect('The interlock block, its size and its place', 'Margin on current', 1, '%.2f' % margin(total_steady))
    prose.expect('The interlock block, its size and its place', 'Margin on current', 1, '%.2f' % margin(cur['overload']))
    for ph in ('the coil is fed only through the proof-of-life path.', 'No level, timer, charge store or latch keeps the coil above the relay\'s drop-out voltage for longer than the removal interval after proof of life stops.',
               'This holds whatever level the controller\'s output rests at: high, low or floating.', 'Bring-up stops the controller in each rest state and records the coil voltage falling below 0.5 V within the interval.'):
        prose.present(sec_h, ph, 'the coil\'s feed requirement')
    vde = sorted(rl.get('vde') or [])
    if not vde:
        bad.append('the interlock relay has no safety-approval (VDE) rating in the data, and the record states its thermal margin from it')
    else:
        if vde[-1][1] < cur['overload'] - EPS:
            bad.append('the interlock relay\'s VDE rating at %g C of ambient is %g A, under the %g A of the overload band' % (vde[-1][0], vde[-1][1], cur['overload']))
        for t_, a_ in vde:
            prose.expect(sec_h, 'Safety approval ratings', 1, '%.2f' % (a_ / total_steady))
            prose.expect(sec_h, 'Safety approval ratings', 1, '%.2f' % (a_ / cur['overload']))
        prose.mention(sec_h, '%s times the steady current, and %s times the %.0f A' % (' and '.join('%.2f' % (a_ / total_steady) for _, a_ in vde), ' and '.join('%.2f' % (a_ / cur['overload']) for _, a_ in vde), cur['overload']))
        out.append('relay K_IL safety-approval ratings (P2): %s of ambient; margins %s on the %.2f A the contact carries and %s on the %.0f A of the overload band; the body stands at or above the %g C ambient limit with the coil alone, so the lowest rating is the one to lean on' % (
            ', '.join('%g A at %g C' % (a_, t_) for t_, a_ in vde), ' and '.join('%.2f' % (a_ / total_steady) for _, a_ in vde), total_steady, ' and '.join('%.2f' % (a_ / cur['overload']) for _, a_ in vde), cur['overload'], rl['ambient_c']))
    cr = D['copper_rise']
    mil = lambda mm: mm / 0.0254
    area_mil2 = lambda w_mm: mil(w_mm) * mil(cr['oz_um'] / 1000.0)
    rise_k = lambda amps, w_mm: (amps / (cr['k'] * area_mil2(w_mm) ** cr['area_exp'])) ** (1.0 / cr['rise_exp'])
    w_wide = pour[2] - pour[0]
    out.append('copper temperature rise, an estimate (IPC-2221 outer layer, planes pulled back): the narrowest link region %.2f mm (%.0f mil2) %.1f K at %.2f A and %.1f K at %.0f A; the %.1f mm regions %.1f K and %.1f K' % (
        narrow, area_mil2(narrow), rise_k(total_steady, narrow), total_steady, rise_k(cur['overload'], narrow), cur['overload'], w_wide, rise_k(total_steady, w_wide), rise_k(cur['overload'], w_wide)))
    cop_s = 'Copper that carries the heater current'
    prose.mention(cop_s, '(%.0f mil²)' % area_mil2(narrow))
    prose.mention(cop_s, 'about %.0f K at %.2f A and about %.0f K at %.0f A' % (rise_k(total_steady, narrow), total_steady, rise_k(cur['overload'], narrow), cur['overload']))
    prose.mention(cop_s, 'the %.1f mm regions about %.0f K and %.0f K' % (w_wide, rise_k(total_steady, w_wide), rise_k(cur['overload'], w_wide)))
    bad += check_decisions(D, text)
    prose.present(sec_h, 'HF115F-Q/005-1H', 'the interlock relay\'s 5 V ordering code')
    prose.present(sec_h, 'catalogue number and price are not recorded: the design task must match a stocked part; the estimate uses the 12 V part\'s price', 'the 5 V variant\'s catalogue number and price')
    prose.present(sec_h, 'no sourced thermal margin at the coil drive it is held at', 'the interlock relay\'s thermal margin')
    prose.present('The path of the heater current', 'it is not proven until the bring-up continuity check', 'the premise that the interlock cuts every load')
    prose.present('Reported for the board design tasks', 'there is no continuity', 'the bring-up continuity check')
    prose.present('Every function has one owner', 'There are two: the heater wall board and the steam-path assembly.', 'the two off-board assemblies')
    prose.present('The fuses', 'The entry fuse holder F_IL stands at X 17.0 to 41.0 and Y 34.3 to 43.3', 'the entry fuse holder\'s place in the floorplan')
    prose.present('The fuses', 'its load-side clip F_IL.o (X 17.0 to 23.0) is on LINE', 'the entry fuse in series, its load side on LINE')
    prose.present('The fuses', 'its line pad RV_IL.l is on the piece of copper that holds the fuse\'s load-side clip', 'the varistor\'s line pad on the fuse\'s load side')
    prose.present('The fuses', 'the script holds the line pad to that piece and to within %.1f mm of the clip' % E['against_mm'], 'the varistor\'s distance limit from the clip')
    prose.present('The fuses', 'The line side is joined to the pad of tab 2 on an inner layer', 'the fuse\'s line side joined to the pad of tab 2 on an inner layer')
    prose.present('Reported for the board design tasks', 'The entry fuse holder and the varistor are drawn at tabs 2 and 3.', 'the entry parts\' place, reported for the board design tasks')
    prose.present('The fuses', 'The 10 A slow-blow fuse and a varistor are carried on the main board where the lead\'s conductors land, at tabs 2 and 3', 'the entry fuse and varistor at tabs 2 and 3')
    prose.present('The fuses', 'so the entry fuse needs a 10 A holder', 'the entry fuse\'s 10 A holder')
    prose.present('The fuses', 'The fuse is as short of the 6 kA the constraints record assumes', 'the entry fuse\'s 6 kA shortfall')
    prose.present('The fuses', 'the owner checks that disc on the original board before the part is chosen', 'the owner\'s check of the original board\'s varistor')
    prose.present('The fuses', 'is decided by the main board\'s design against the emission criteria', 'emission suppression decided by the main board design')
    prose.present('Reported for the board design tasks', 'the owner\'s visual trace and not a measurement', 'the premise that the interlock cuts every load')
    prose.present('The heater wall board', 'edge-on to the wall, its wall edge flush with the outer face of the bracket\'s leg', 'the wall board\'s orientation to the wall')
    prose.present('The fixing rule and the tabs that move', 'measures the real slack of each of the four leads with a rule before the board is ordered', 'the owner\'s measurement of the slack')
    prose.present('The fixing rule and the tabs that move', 'no stiffness analysis is made', 'the board\'s stiffness not analysed')
    prose.present('The fixing rule and the tabs that move', 'fixed by one screw at each of the machine\'s four mounting points', 'the screw and hole at all four points')
    prose.present('The heater wall board', 'Whether this stays within the cavity is unconfirmed, and is for the owner to check at assembly', 'the bracket\'s depth left for the owner to check')
    prose.present('What the owner fits by hand', '6.36 mm ±0.1 wide and 0.81 mm thick', 'the harness blade\'s width and thickness')
    out.append('owner decisions pending: %d, each stated once in the record\'s list with its words, pointed to from the section it concerns, and no other mention of a decision pending without the pointer' % len(D['owner_decisions']))

    inner = {b['via'] for b in RT['branches'] if b.get('layer') == 'inner'}
    inner_nets = set(D.get('inner_nets', []))
    if route:
        runs = corridors(D, [x for x in items if x[0] not in inner], pockets, outline, sr, keep, bas, reinforced, skip=inner_nets)
        on_inner = {}
        for n_ in sorted(inner_nets):
            on_surface = corridors(D, [x for x in items if x[0] not in inner], pockets, outline, sr, keep, bas, reinforced, only={n_}).get(n_, 'no pieces')
            if on_surface is not None:
                bad.append('the net %s has %s on the surface, so the data should not give its join as an inner layer' % (n_, 'no separate pieces' if on_surface == 'no pieces' else 'a route of %.0f mm' % on_surface))
            below = corridors(D, [x for x in items if x[2] == n_], pockets, outline, sr, keep, bas, reinforced, only={n_}).get(n_, 'no pieces')
            if below is None or below == 'no pieces':
                bad.append('no inner-layer route exists for the net %s clear of the holes, the slots and the low-voltage blocks' % n_)
            else:
                on_inner[n_] = below
        if on_inner:
            out.append('nets joined by an inner layer, because no surface route exists for a trace to them beside the tab pads, the strips and the point 3 hole: %s; an inner-layer route clear of the holes, the slots and the low-voltage blocks, the copper of other layers not modelled, exists for each: %s' % (
                ', '.join(sorted(inner_nets)), ', '.join('%s %.0f mm' % (n_, v_) for n_, v_ in sorted(on_inner.items()))))
            for n_, v_ in on_inner.items():
                prose.expect('Every retained harness reaches its connector', n_, 2, 'inner layer, %.0f mm' % v_)
        for net, length in runs.items():
            if length is None:
                bad.append('no route exists for a trace of the net %s between its copper, round the slots, the other nets and the low-voltage blocks (%s)' % (net, '; '.join(m for m in corridors.missed if m.startswith(net + ':'))))
        shown = lambda n: n.replace('|', ' and ')
        out.append('traces between the separate pieces of one net, shortest route that keeps the basic creepage from other nets (the signed creepage from LINE1) and %.1f mm from low-voltage blocks, round the slots: %s' % (
            bas['creepage'], ', '.join('%s %s' % (shown(n), ('%.0f mm' % v) if v is not None else 'none') for n, v in sorted(runs.items()))))
        for n, v in runs.items():
            prose.expect('Every retained harness reaches its connector', shown(n), 2, '%.0f mm' % v if v is not None else 'none')
        if whatif or proof:
            for i_ in sorted(inner):
                run_i = corridors(D, [x for x in items if x[0] not in inner or x[0] == i_], pockets, outline, sr, keep, bas, reinforced).get('LINE|NEUTRAL')
                if run_i is not None:
                    bad.append('the return piece %s has a route of %.0f mm on the surface, so the data should not give its join as an inner layer' % (i_, run_i))
            out.append('returns joined by an inner layer, because no surface route exists for a trace to them beside the tab pads and the strips: %s' % (', '.join(sorted(inner)) or 'none'))
            prose.mention('The path of the heater current', 'no surface route exists for %s' % ' and '.join('`%s`' % i_ for i_ in sorted(inner)).replace('`', ''))

    # lead ends over the intrusions, harness reach, heat
    ends = [('%s pin' % b['id'], p) for b in D['mains_blocks'] for p in b['pins']] + [('a reed pad', lo), ('a reed pad', up)]
    for b in D['lv_blocks']:
        if b['tht']:
            r = b['rect']
            ends += [('%s lead end' % b['id'], (x, y)) for x in (r[0], r[2]) for y in (r[1], r[3])]
    it = D['intrusions']
    side = math.inf
    for n, (x, y) in ends:
        if y < intrusion_top(D, x) + 1.0 or y < it['two_y1'] + 1.0:
            bad.append('%s lies over an intrusion' % n)
        s = intrusion_side(D, x, y)
        if s is not None:
            side = min(side, s)
            if s < it['pos_tol'] - EPS:
                bad.append('%s lies %.2f mm from the side of intrusion 1, whose position is read to %.1f mm' % (n, s, it['pos_tol']))
    out.append('nearest lead end to the side of intrusion 1 (its position read to %.1f mm): %.1f mm' % (it['pos_tol'], side))
    cut = D['cut_centre']
    names_h = {'CON2': 'Operator panel', 'SP2': 'Gauge assembly', 'KNOB': 'Knob microswitches', 'FLOW': 'Flow meter', 'TEMP_C': 'Coffee-block thermistor',
               'TEMP_S': 'Steam-block thermistor', 'TEMP_W': 'Steam-wand thermistor'}
    reach = {}
    for n, lim in D['reach'].items():
        r = bodies[n]
        far = max(math.hypot(x - cut[0], y - cut[1]) for x in (r[0], r[2]) for y in (r[1], r[3]))
        reach[n] = (far, rd(r, (cut[0], cut[1] - 16.5, cut[0], cut[1] + 16.5)))
        if far > lim:
            bad.append('%s: farthest corner %.1f mm from the cut-away, limit %d' % (n, far, lim))
        prose.expect('Every retained harness reaches its connector', names_h[n], 4, '%.1f' % far)
        prose.expect('Every retained harness reaches its connector', names_h[n], 4, '%.1f' % reach[n][1])
    out.append('harness reach (farthest corner / nearest point of the opening, limit): ' + ', '.join('%s %.1f / %.1f of %d' % (n, v[0], v[1], D['reach'][n]) for n, v in reach.items()) + ' mm')
    ht = D['heat']
    lim = ht['limits']
    mbx = {b['id']: b for b in D['mains_blocks']}
    srect = lambda n: tuple(mbx[n]['heat']) if mbx[n].get('heat') else bodies[n]
    hrect = lambda n: tuple(mbx[n]['hot']) if n in mbx and mbx[n].get('hot') else bodies[n]
    srcs = ht['sources']
    classified = set(ht['mcu']) | set(ht['sense']) | set(ht['digital']) | set(ht['other'])
    for b in D['lv_blocks']:
        if not b['tht'] and b['id'] not in classified:
            bad.append('the low-voltage block %s has no heat class: it is not in the controller, sensing, digital or other list' % b['id'])
    for n in classified:
        if n not in bodies:
            bad.append('the heat lists name %s, which is not a block' % n)
    _, total_ma_r, _ = rail_rows(D)
    chm = [m for m in D['rail']['modules'] if m.get('chosen')][0]
    pout_r = D['rail']['volts'] * total_ma_r / 1000.0
    w_mod = pout_r / chm['eff'] - pout_r
    watts = {'MODULE': w_mod, 'K_IL': il_max}
    for sname in srcs:
        if watts.get(sname, 0.0) < ht['source_w'] - EPS:
            bad.append('%s dissipates %.2f W at most, under the %.1f W that makes it a source in A8' % (sname, watts.get(sname, 0.0), ht['source_w']))
    out.append('heat sources, A8 (%g W or more): the module %.2f W at this board\'s load; the interlock relay %.2f W, or %.2f W with its coil %.0f %% under nominal, held to A8 by the owner\'s instruction of 2026-10-24 as well' % (
        ht['source_w'], w_mod, il_nom, il_max, rl['coil_tol'] * 100))
    dmat = {}
    for sname in srcs:
        for n in ht['mcu'] + ht['sense'] + ht['digital']:
            dmat[(n, sname)] = rd(srect(sname), bodies[n])
        for p in ht['class85']:
            dmat[(p['id'], sname)] = rd(srect(sname), hrect(p['id']))
    for sname in srcs:
        for n in ht['mcu']:
            if dmat[(n, sname)] < lim['mcu'] - EPS:
                bad.append('%s is %.1f mm from the heat source %s, the rule is %g' % (n, dmat[(n, sname)], sname, lim['mcu']))
        for n in ht['sense']:
            if dmat[(n, sname)] < lim['sense'] - EPS:
                bad.append('%s, a sensing block, is %.1f mm from the heat source %s, the rule is %g' % (n, dmat[(n, sname)], sname, lim['sense']))
    air, ck = ht['air_c'], ht['class_k']
    accepted = {tuple(x) for x in ht['accepted']}
    not_held = {}
    for p in ht['class85']:
        if p['limit_c'] - air > ck + EPS:
            bad.append('%s is rated to %g C, %g K over the %g C air, which is outside the %g K class A8 holds at %g mm' % (p['id'], p['limit_c'], p['limit_c'] - air, air, ck, lim['class']))
        for sname in srcs:
            d = dmat[(p['id'], sname)]
            if d < lim['class'] - EPS:
                not_held[(p['id'], sname)] = d
                if (p['id'], sname) not in accepted:
                    bad.append('%s, rated to %g C, is %.1f mm from the heat source %s, the rule is %g, and the record does not report it as not held' % (p['id'], p['limit_c'], d, sname, lim['class']))
    for pair in accepted:
        if pair not in not_held:
            bad.append('the record reports %s as not held against %s but it is %.1f mm away, which holds' % (pair[0], pair[1], dmat.get(pair, math.nan)))
    for o in ht['outside']:
        if o['limit_c'] - air <= ck + EPS:
            bad.append('%s is rated to %g C, only %g K over the air, and is inside the class A8 holds at %g mm, so it cannot be listed outside it' % (o['id'], o['limit_c'], o['limit_c'] - air, lim['class']))
    rv_mod, rv_il = rd(srect('MODULE'), bodies['RV_IL']), rd(srect('K_IL'), bodies['RV_IL'])
    prose.present('Reported for the board design tasks', 'As drawn, RV_IL stands %.1f mm from the module\'s body and %.1f mm from the interlock relay\'s body, against A8\'s %g mm' % (rv_mod, rv_il, lim['class']), 'the entry varistor\'s distances from the two heat sources')
    prose.present('Heat', 'The entry varistor RV_IL is not among the five: its temperature class is not read (A33)', 'the entry varistor outside the five 85 C parts')
    out.append('entry varistor RV_IL, temperature class not read (A33), outside the 85 C class: %.1f mm from the module and %.1f mm from the interlock relay (A8 %g mm if it proves to be an 85 C part)' % (rv_mod, rv_il, lim['class']))
    pair_il = rd(srect('MODULE'), srect('K_IL'))
    if pair_il < lim['relay'] - EPS:
        bad.append('the interlock relay is %.1f mm from the module, the owner\'s figure is %g' % (pair_il, lim['relay']))
    fmt = lambda n, sname: '%.1f' % dmat[(n, sname)]
    out.append('heat from the module / from the interlock relay: controller %s / %s mm of %g; sensing blocks %.1f / %.1f mm or more of %g; digital stages %s mm from the module; the interlock relay from the module %.1f mm of %g (%s)' % (
        fmt('MCU', 'MODULE'), fmt('MCU', 'K_IL'), lim['mcu'], min([dmat[(n, 'MODULE')] for n in ht['sense']] or [0.0]), min([dmat[(n, 'K_IL')] for n in ht['sense']] or [0.0]), lim['sense'],
        ', '.join(fmt(n, 'MODULE') for n in ht['digital']), pair_il, lim['relay'], 'held' if pair_il >= lim['relay'] - EPS else 'not held'))
    out.append('mains-side parts rated to 85 C (%g K or less over the %g C air), from the module / from the interlock relay (rule %g): %s' % (
        ck, air, lim['class'], ', '.join('%s %.1f / %.1f mm (%s)' % (p['id'], dmat[(p['id'], 'MODULE')], dmat[(p['id'], 'K_IL')], 'held' if all(dmat[(p['id'], x)] >= lim['class'] - EPS for x in srcs) else 'not held') for p in ht['class85'])))
    for o in ht['outside']:
        for sname in srcs:
            dmat[(o['id'], sname)] = rd(srect(sname), hrect(o['id']))
    out.append('outside the class, by their sheets: %s' % ', '.join('%s %g C, %g K over the air, %.1f mm from the module and %.1f mm from the interlock relay' % (o['id'], o['limit_c'], o['limit_c'] - air, dmat[(o['id'], 'MODULE')], dmat[(o['id'], 'K_IL')]) for o in ht['outside']))
    # why they cannot all hold: the barrier column's free length against the frontage the parts need
    hot_rects = [hrect(p['id']) for p in ht['class85']]
    hx0, hx1 = min(r[0] for r in hot_rects), max(r[2] for r in hot_rects)
    ylo, yhi = ob[1] + bas['edge_min'], ob[3] - bas['edge_min']
    step, spans, cur_start, y = 0.05, [], None, ylo
    while y <= yhi + 1e-9:
        ok = all(rd((hx0, y, hx1, y), srect(sname)) >= lim['class'] - EPS for sname in srcs)
        if ok and cur_start is None:
            cur_start = y
        if not ok and cur_start is not None:
            spans.append((cur_start, y - step))
            cur_start = None
        y += step
    if cur_start is not None:
        spans.append((cur_start, yhi))
    free_len = max((b - a for a, b in spans), default=0.0)
    sizes = {p['id']: hrect(p['id'])[3] - hrect(p['id'])[1] for p in ht['class85']}
    gap = bas['clearance']
    best = (0, ())
    ids85 = list(sizes)
    for mask in range(1, 1 << len(ids85)):
        sel = [ids85[i] for i in range(len(ids85)) if mask >> i & 1]
        stack = sum(sizes[n] for n in sel) + gap * (len(sel) - 1)
        if stack <= free_len + EPS and len(sel) > best[0]:
            best = (len(sel), tuple(sel))
    need_all = sum(sizes.values()) + gap * (len(sizes) - 1)
    ys = sorted((r[1], r[3]) for i, r, _, o in items if o in mbx)
    merged = []
    for lo_, hi_ in ys:
        if merged and lo_ <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi_)
        else:
            merged.append([lo_, hi_])
    widest_gap = max((merged[i + 1][0] - merged[i][1] for i in range(len(merged) - 1)), default=0.0)
    lv_corridor = 2 * bas['creepage'] + D['trace']['w']
    if widest_gap >= lv_corridor - EPS:
        bad.append('the widest gap between mains copper along the stack is %.1f mm, enough for a low-voltage trace (%.1f mm), so a pocket need not stand at the boundary' % (widest_gap, lv_corridor))
    out.append('why they cannot all hold: a barrier part\'s pocket stands at the zone boundary, since a trace kept %g mm from mains copper by distance alone needs %.1f mm (2 x %g mm and the trace) to pass and the widest gap between mains copper along the stack is %.1f mm, and a slotted channel across the stack would divide the taps from one another; the boundary stays %g mm or more from both sources only over %s, %.1f mm; the %d parts need %.1f mm there with %g mm between them, so at most %d of them fit there' % (
        bas['creepage'], lv_corridor, bas['creepage'], widest_gap, lim['class'], ', '.join('Y %.1f to %.1f' % x for x in spans), free_len, len(sizes), need_all, gap, best[0]))
    if best[0] >= len(sizes):
        bad.append('all %d parts of the 85 C class fit the %.1f mm that clears the rule, and the record says they cannot' % (len(sizes), free_len))
    if len(not_held) and best[0] < len(sizes) - len({p for p, _ in not_held}):
        bad.append('the drawn stack holds fewer parts than the %d that fit' % best[0])
    held_drawn = held_parts(D)
    for pair in ht.get('required_held', []):
        if tuple(pair) in accepted:
            bad.append('%s must hold %g mm from %s and the record accepts it as not held' % (pair[0], lim['class'], pair[1]))
    if whatif:
        best_n, best_sets = max_held(D, bas, ob)
        below_sets = sorted({x[2] for x in best_sets})
        prose.mention('Heat', 'At most %d hold, and every arrangement that holds %d stands %s between the two sources' % (best_n, best_n, ' or '.join('+'.join(b) for b in below_sets)))
        prose.mention('Heat', 'The drawn stack holds %d' % len(held_drawn))
        held2s = []
        for wi in D['what_if']:
            D2 = apply_what_if(D, wi)
            msgs2 = [m for m in check_main(D2, text, [], record_dir, src, route=True, whatif=False) if not m.startswith('table in') and not m.startswith('assumption token') and not m.startswith('the Assumptions table') and not m.startswith('required statement missing') and not m.startswith('the cost record')]
            held2 = held_parts(D2)
            held2s.append(held2)
            out.append('what-if, %s: %s hold; it breaks %d rule%s of this record: %s' % (wi['name'], ', '.join(held2), len(msgs2), '' if len(msgs2) == 1 else 's', '; '.join(m[:150] for m in msgs2)))
            for m in msgs2:
                mm_ = re.match(r'(\w+), a sensing block, is ([0-9.]+) mm from the heat source MODULE', m)
                if mm_:
                    prose.mention('Heat', '%s stands %s mm from the module against A8\'s %g' % (mm_.group(1), mm_.group(2), lim['sense']))
                mm_ = re.match(r'the region (\w+) stands ([0-9.]+) mm from the heat source MODULE', m)
                if mm_:
                    prose.mention('Heat', 'the region %s stands %s mm from the module' % (mm_.group(1), mm_.group(2)))
            if wi is D['what_if'][-1]:
                m2 = {b['id']: b for b in D2['mains_blocks']}
                hr2 = lambda n: tuple(m2[n].get('hot') or m2[n]['body'])
                sr2 = lambda n: tuple(m2[n].get('heat') or m2[n]['body'])
                for pid in ('K_V1', 'P_C', 'VMEAS'):
                    prose.mention('Heat', '%s then stands %.1f mm from the module' % (pid, rd(sr2('MODULE'), hr2(pid))))
                prose.mention('Heat', 'the voltage measurement would then stand %.1f mm from the relay\'s body' % rd(sr2('K_IL'), hr2('VMEAS')))
            if len(held2) <= len(held_drawn):
                bad.append('the what-if %s holds %d parts, no more than the drawn stack\'s %d, so it is not an arrangement that holds more' % (wi['name'], len(held2), len(held_drawn)))
            if not msgs2:
                bad.append('the what-if %s holds %d parts of the 85 C class, more than the drawn stack\'s %d, and meets every rule of this record' % (wi['name'], len(held2), len(held_drawn)))
        out.append('the most the 85 C parts can hold along the barrier column, counted over every position of the module, every split above or below it and every order with the tab-fed parts in tab order: %d (%s); the drawn stack holds %d (%s); every arrangement that holds %d stands %s between the two sources' % (
            best_n, ', '.join('/'.join(x[3]) for x in best_sets[:1]), len(held_drawn), ', '.join(held_drawn), best_n, ' or '.join('+'.join(b) for b in below_sets)))
        prose.mention('Heat', 'The two arrangements that hold %d with K_V1 between the sources, built in the data as the first two what-ifs, hold %s and %s' % (best_n, ', '.join(held2s[0]), ', '.join(held2s[1])))
        prose.mention('Heat', 'The third what-if holds %s' % ', '.join(held2s[2]))
        if best_n < len(held_drawn):
            bad.append('the drawn stack holds %d parts of the 85 C class and the count says at most %d can' % (len(held_drawn), best_n))
    sec_why = 'Heat'
    prose.mention(sec_why, 'needs %.1f mm between mains copper' % lv_corridor)
    prose.mention(sec_why, 'the widest gap between mains copper along the stack is %.1f mm' % widest_gap)
    prose.present('The mains-side blocks', 'the widest gap between mains copper along the stack is %.1f mm' % widest_gap, 'the widest gap between mains copper, stated with the valve relay\'s coil pocket')
    n_assump = len([k for k in table_rows(section(text, 'Assumptions')) if re.fullmatch(r'A[0-9]+', k)])
    prose.present('How this record is built', 'numbered A1 to A%d in § Assumptions' % n_assump, 'the count of assumptions')
    prose.present('Reported for the board design tasks', 'Assumptions A1 to A%d' % n_assump, 'the count of assumptions')
    tap_live, tap_neutral = D['link']['taps'][0]['from'], D['link']['taps'][1]['from']
    prose.present('Every retained harness reaches its connector', 'it is not the routing of the taps, from %s (net LINE) and from the neutral pour %s' % (tap_live, tap_neutral), 'where the taps leave the link')
    prose.mention(sec_why, 'is %s, %.1f mm' % (' and '.join('Y %.1f to %.1f' % x for x in spans), free_len))
    prose.mention(sec_why, 'the five parts need %.1f mm there' % need_all)
    prose.mention(sec_why, 'so at most %d of them fit' % best[0])
    prose.expect('Options considered and dropped', 'Holding every 85 °C part', 1, '%.1f' % need_all)
    prose.expect('Options considered and dropped', 'Holding every 85 °C part', 1, '%.1f' % free_len)
    sec_heat = 'Heat'
    groups = (('MCU', ['MCU']), ('FE_NTC', ['FE_NTC']), ('PT1_C', ['PT1_C', 'PT2_C']), ('BREW_A_C', ['BREW_A_C', 'SPARE_AN2_C']),
              ('CURR1_C', [n for n in ('CURR1_C', 'I_C', 'CURR2_C') if n in ht['sense']]), ('WT1_C', ['WT1_C', 'WT2_C', 'VM_C']), ('FE_SPAREA', ['FE_SPAREA']), ('FE_GAUGE', ht['digital']))
    for key, group in groups:
        for n in group:
            if (n, 'MODULE') not in dmat:
                continue
            prose.expect(sec_heat, key, 1, '%.1f' % dmat[(n, 'MODULE')])
            prose.expect(sec_heat, key, 2, '%.1f' % dmat[(n, 'K_IL')])
    for p in ht['class85']:
        for col, sname in ((1, 'MODULE'), (2, 'K_IL')):
            prose.expect(sec_heat, 'The 85 °C part ' + p['id'], col, '%.1f' % dmat[(p['id'], sname)])
        prose.expect(sec_heat, 'The 85 °C part ' + p['id'], 4, 'Held' if all(dmat[(p['id'], x)] >= lim['class'] - EPS for x in srcs) else 'Not held')
    for o in ht['outside']:
        prose.expect(sec_heat, o['id'], 1, '%.1f' % dmat[(o['id'], 'MODULE')])
        prose.expect(sec_heat, o['id'], 2, '%.1f' % dmat[(o['id'], 'K_IL')])
        prose.expect(sec_heat, o['id'], 4, 'Outside the class')
    prose.expect(sec_heat, 'The interlock relay', 1, '%.1f' % pair_il)
    prose.expect(sec_heat, 'The interlock relay', 4, 'Held' if pair_il >= lim['relay'] - EPS else 'Not held')

    # the anticipated kinds: the removal steps and the places
    cap, steps, stop, arr = allocation(D)
    gp = D['regions']['gap']
    out.append('capacity with the spacing the drawing keeps counted (%.1f mm in the header regions, %.1f mm in the analogue region): header regions %.1f, analogue region %.1f' % (gp['hdr'], gp['ana'], cap['hdr'], cap['ana']))
    section_kinds = 'The anticipated channel kinds'
    words = {'over': 'not searched, the area is over', 'none': 'none exists', 'found': 'found'}
    phrase = {'over': 'the header area is over capacity', 'none': 'no arrangement of the headers exists', 'found': 'an arrangement of the headers exists and is drawn'}
    for n, gone, dem in steps:
        out.append('removal step %d%s: header regions %.1f (over %.1f), analogue region %.1f (over %.1f); arrangement of the headers: %s' % (
            n, (' (kind %d removed)' % gone) if gone else '', dem['hdr'], max(dem['hdr'] - cap['hdr'], 0), dem['ana'], max(dem['ana'] - cap['ana'], 0), words[arr[n]]))
        prose.expect(section_kinds, 'step %d' % n, 1, '%.1f' % dem['hdr'])
        prose.expect(section_kinds, 'step %d' % n, 2, '%.1f' % max(dem['hdr'] - cap['hdr'], 0))
        prose.expect(section_kinds, 'step %d' % n, 3, '%.1f' % dem['ana'])
        prose.expect(section_kinds, 'step %d' % n, 4, '%.1f' % max(dem['ana'] - cap['ana'], 0))
        prose.expect(section_kinds, 'step %d' % n, 5, phrase[arr[n]])
    removed_now = set(removal_order(D)[:stop]) if stop is not None else set(removal_order(D))
    drawn_dem = region_demand(D, removed_now)
    for k in D['kinds']:
        if k['n'] in removed_now and (k.get('hdr') or k.get('ana')):
            need_k = {reg: sum((w + gp[reg]) * (h + gp[reg]) for w, h in k.get(reg, [])) for reg in ('hdr', 'ana')}
            spare_k = {reg: cap[reg] - drawn_dem[reg] for reg in ('hdr', 'ana')}
            st = 'over' if need_k['hdr'] > spare_k['hdr'] + EPS else ('found' if arrangement(D, 'hdr', header_blocks(D, removed_now - {k['n']})) else 'none')
            out.append('kind %d alone, with the drawn kinds and no other kind given a place: header regions need %.1f of %.1f spare, analogue region %.1f of %.1f spare; arrangement of the headers: %s' % (
                k['n'], need_k['hdr'], spare_k['hdr'], need_k['ana'], spare_k['ana'], words[st]))
            prose.expect(section_kinds, str(k['n']), 3, '%.1f of the %.1f' % (need_k['hdr'], spare_k['hdr']))
            prose.expect(section_kinds, str(k['n']), 3, '%.1f of the %.1f' % (need_k['ana'], spare_k['ana']))
            prose.expect(section_kinds, str(k['n']), 3, phrase[st])
    names_k = lambda ns: ('only kind %d' % ns[0]) if len(ns) == 1 else ('kinds %s' % ' and '.join(str(n) for n in ns))
    for alt in D['regions'].get('alternatives', []):
        dm = region_demand(D, set(alt))
        fit_h = dm['hdr'] <= cap['hdr'] + EPS and bool(arrangement(D, 'hdr', header_blocks(D, set(alt))))
        fit_a = dm['ana'] <= cap['ana'] + EPS
        out.append('removing %s: header regions %.1f of %.1f and an arrangement of the headers %s; analogue region %.1f of %.1f; it %s' % (
            names_k(alt), dm['hdr'], cap['hdr'], 'exists' if fit_h else 'does not exist', dm['ana'], cap['ana'], 'fits' if fit_h and fit_a else 'does not fit'))
        prose.mention(section_kinds, 'removing %s %s' % (names_k(alt), 'fits' if fit_h and fit_a else 'does not fit'))
    if stop is None:
        bad.append('the allocation does not fit the regions after every removable kind has gone')
    for b in D['lv_blocks']:
        if b.get('region') and not in_union(tuple(b['rect']), [tuple(g['rect']) for g in D['regions'][b['region']]]):
            bad.append('%s lies outside its %s region' % (b['id'], b['region']))
    order = removal_order(D)
    removed = set(order[:stop]) if stop is not None else set(order)
    kinds_rows = {re.sub(r'[`*]', '', k): v for k, v in rows_of_kinds(text).items()}
    kind_nums = {k['n'] for k in D['kinds']}
    for key, row_ in kinds_rows.items():
        if key.isdigit() and int(key) not in kind_nums:
            bad.append('kind %s is in the record\'s table of kinds%s and is not in the data: a kind is never silently dropped' % (key, ', and its row says required,' if 'required' in row_[1].lower() else ''))
    for n_ in sorted(kind_nums):
        if str(n_) not in kinds_rows:
            bad.append('kind %d is in the data and has no row in the record\'s table of kinds' % n_)
    if not any(k.get('required') for k in D['kinds']):
        bad.append('the data marks no kind required, and the supply voltage measurement is required by the requirement its row of the record cites')
    for k in D['kinds']:
        drawn = [n for n in k.get('blocks', []) if n in bodies]
        undrawn_lists = bool(k.get('hdr') or k.get('ana'))
        if k['n'] in removed:
            if drawn or any(b.get('kind') == k['n'] for b in D['lv_blocks']):
                bad.append('kind %d is removed but a block of it is drawn' % k['n'])
        elif k.get('none'):
            if drawn or k.get('blocks') or undrawn_lists:
                bad.append('kind %d is recorded as not given a place but a block of it is drawn' % k['n'])
        elif len(drawn) != len(k.get('blocks', [])) or undrawn_lists:
            bad.append('kind %d is given a place but not all its blocks are drawn' % k['n'])
        prose.expect(section_kinds, str(k['n']), 6, sq(kind_area(D, bodies, k)))
        row = kinds_rows.get(str(k['n']))
        says_required = bool(row) and 'required' in row[1].lower()
        if k.get('required') and not (says_required and re.search(r'`REQ-[A-Z-]+-[0-9]+\.C[0-9]+`', row[3])):
            bad.append('kind %d is marked required in the data but its row of the record does not say required and cite the requirement criterion that requires it' % k['n'])
        if says_required and not k.get('required'):
            bad.append('the record\'s row of kind %d says required and the data does not mark it so' % k['n'])
        if k.get('required') and ('rank' in k or k['n'] in removed):
            bad.append('kind %d is required and stands in the removal order' % k['n'])
    for reg in ('hdr', 'ana'):
        for g in D['regions'][reg]:
            gr = tuple(g['rect'])
            for b in D['lv_blocks']:
                if b.get('region') != reg and ov(gr, tuple(b['rect'])):
                    bad.append('the region %s overlaps the block %s, which is not of its class' % (g['id'], b['id']))
            if reg == 'ana':
                for sname in srcs:
                    if rd(srect(sname), gr) < lim['sense'] - EPS:
                        bad.append('the region %s stands %.1f mm from the heat source %s, the sensing rule is %g' % (g['id'], rd(srect(sname), gr), sname, lim['sense']))
                if reed_hits(D, gr) or ov(gr, box):
                    bad.append('the region %s reaches the reed keep-out' % g['id'])
    top_id = D['regions'].get('top_of')
    if top_id:
        g = [g for g in D['regions']['ana'] if g['id'] == top_id][0]['rect']
        free_top, step_up = g[3], 0.05
        while free_top + step_up <= ob[3] and all(rd(srect(n), (g[0], g[1], g[2], free_top + step_up)) >= lim['sense'] - EPS for n in srcs) and not any(
                ov((g[0], g[1], g[2], free_top + step_up), tuple(b['rect'])) for b in D['lv_blocks'] if b.get('region') != 'ana'):
            free_top += step_up
        if abs(free_top - g[3]) > step_up + EPS:
            bad.append('the region %s ends at Y %.1f and the rules leave it free to Y %.1f' % (top_id, g[3], free_top))
        out.append('the region %s ends at Y %.1f, where the nearest block of another class stands and the module\'s body less %g mm is Y %.1f' % (top_id, g[3], lim['sense'], srect('MODULE')[1] - lim['sense']))
    least_gap = {}
    for reg in ('hdr', 'ana'):
        rs = [tuple(b['rect']) for b in D['lv_blocks'] if b.get('region') == reg]
        least_gap[reg] = min(rd(a_, b_) for i_, a_ in enumerate(rs) for b_ in rs[i_ + 1:])
    for reg in ('hdr', 'ana'):
        if least_gap[reg] < gp[reg] - EPS:
            bad.append('the blocks drawn in the %s regions stand %.1f mm apart at the least, under the %.1f mm spacing the capacity counts' % (reg, least_gap[reg], gp[reg]))
    out.append('least spacing between the blocks drawn in a region: header regions %.1f mm, analogue region %.1f mm, against the spacing the capacity counts (%.1f mm and %.1f mm)' % (least_gap['hdr'], least_gap['ana'], gp['hdr'], gp['ana']))
    prose.expect('Assumptions', 'A18', 1, '%.1f mm or more apart in the header regions and %.1f mm in the analogue region' % (least_gap['hdr'], least_gap['ana']))
    thou1 = lambda x: '{:,.1f}'.format(x).replace(',', ' ')
    hdr_blocks = [b for b in D['lv_blocks'] if b.get('region') == 'hdr']
    prose.mention(section_kinds, '%s mm² for headers and %s mm² for circuits' % (thou1(cap['hdr']), thou1(cap['ana'])))
    prose.mention(section_kinds, 'which is %s mm² and mostly on the mains side' % thou(oa - sum(sums)))
    prose.mention(section_kinds, 'the %d headers stand in %d columns' % (len(hdr_blocks), len({b['rect'][0] for b in hdr_blocks})))
    gap, ys = stack_gap(D)
    out.append('allocation fits at step %s, after the removal of kinds %s; the mains-side stack runs from Y %.1f to %.1f' % (
        stop, ', '.join(str(n) for n in order[:stop]) or 'none', ys[0][0], max(y[1] for y in ys)))

    if whatif:
        # the owner's placement of an isolated sensor in the link: the relay moves right to make room for a primary 8 mm long
        base_cap = cap['ana']
        for dx in (3.0, 2.0):
            D3 = copy.deepcopy(D)
            kb = [b for b in D3['mains_blocks'] if b['id'] == 'K_IL'][0]
            for key in ('body', 'heat'):
                kb[key][0] += dx
                kb[key][2] += dx
            for m_ in kb['mains']:
                m_[1][0] += dx
                m_[1][2] += dx
            for p_ in kb['pockets']:
                p_[0] += dx
                p_[2] += dx
            for p_ in kb['pins']:
                p_[0] += dx
            for g_ in D3['regions']['ana']:
                if g_['id'] in D3['regions'].get('relay_bound', []):
                    g_['rect'][0] += dx
            under = [(n, rd(tuple(kb['heat']), bodies[n])) for n in ht['sense'] if rd(tuple(kb['heat']), bodies[n]) < lim['sense'] - EPS]
            cap3 = region_capacity(D3)['ana']
            out.append('what-if, the interlock relay moved %.1f mm to the right to make room for a sensor 8 mm long between the pad of tab 2 and its contact copper: %s from the relay against A8\'s %g mm; the analogue region\'s capacity falls from %.1f to %.1f mm2, %.1f mm2 less' % (
                dx, ', '.join('%s %.1f mm' % x for x in under), lim['sense'], base_cap, cap3, base_cap - cap3))
            if dx == 3.0:
                prose.mention(section_kinds, 'then stand %s from the relay against A8\'s %g' % (', '.join('%.1f' % d for _, d in under), lim['sense']))
                prose.mention(section_kinds, 'loses %.1f mm² of capacity (%s to %s' % (base_cap - cap3, thou1(base_cap), thou1(cap3)))
            else:
                prose.mention(section_kinds, '%.1f mm² for a %.1f mm move' % (base_cap - cap3, dx))
        D4 = apply_what_if(D, D['what_if'][-1])
        m4 = {b['id']: b for b in D4['mains_blocks']}
        top4 = [g_ for g_ in D4['regions']['ana'] if g_['id'] == D4['regions']['top_of']][0]
        top4['rect'][3] = min(top4['rect'][3], m4['MODULE']['body'][1] - lim['sense'])
        cap4, dem4 = region_capacity(D4), region_demand(D4, removed)
        held4 = all(in_union(tuple(b['rect']), [tuple(g_['rect']) for g_ in D4['regions']['ana']]) for b in D4['lv_blocks'] if b.get('region') == 'ana' and b.get('kind') not in removed)
        out.append('what-if, the third arrangement with the region %s cut back to Y %.1f, where the module\'s body less %g mm stands: the analogue region\'s capacity falls from %.1f to %.1f mm2 against the %.1f the drawn blocks need, %.1f mm2 spare, and the blocks of the kept kinds %s inside it' % (
            top4['id'], top4['rect'][3], lim['sense'], base_cap, cap4['ana'], dem4['ana'], cap4['ana'] - dem4['ana'], 'all stand' if held4 else 'do not all stand'))
        if not held4 or cap4['ana'] < dem4['ana'] - EPS:
            bad.append('the third arrangement with the region cut back to Y %.1f does not hold the blocks of the kept kinds' % top4['rect'][3])
        prose.mention('Heat', 'cut back to Y %.1f, its capacity falls from %s to %s mm² against the %s the drawn blocks need, %s mm² spare' % (top4['rect'][3], thou1(base_cap), thou1(cap4['ana']), thou1(dem4['ana']), thou1(cap4['ana'] - dem4['ana'])))

    # the valve relays: the part, its ratings against the loads and the supply
    vr = D['valve_relay']
    sec_v = 'The valve relays'
    peak_open = vr['open_contact_vac'] * math.sqrt(2)
    peak_iso = vr['coil_contact_vac'] * math.sqrt(2)
    if vr['rating_a'] < cur['coil_inrush']:
        bad.append('the valve relay is rated %.1f A, below the coils\' inrush of %.3f A' % (vr['rating_a'], cur['coil_inrush']))
    if peak_open < vr['peak']:
        bad.append('the valve relay\'s open contacts give %.0f V peak, below the %.0f V it must block' % (peak_open, vr['peak']))
    if peak_iso < vr['target_kv'] * 1000.0:
        bad.append('the valve relay\'s coil to contacts gives %.0f V peak, below the %.1f kV target' % (peak_iso, vr['target_kv']))
    coil_a = D['rail']['volts'] / vr['coil_ohm']
    out.append('valve relays %s: %.1f A contacts against %.3f A steady and %.3f A at inrush (margins %.0f and %.0f); %.0f V maximum switching voltage against %.0f V at the top of the span (%.1f %% over, the owner\'s acceptance); open contacts %.0f V AC = %.0f V peak against %.0f V blocked (margin %.2f); coil to contacts %.0f V AC = %.2f kV against the %.1f kV target; coil %.0f ohm, %.1f mA and %.0f mW at %.0f V; %.4f USD against %.4f USD for the interlock relay type, %.2f USD less for two' % (
        vr['part'], vr['rating_a'], cur['coil_steady'], cur['coil_inrush'], vr['rating_a'] / cur['coil_steady'], vr['rating_a'] / cur['coil_inrush'], vr['max_v'], vr['span_top'],
        (vr['span_top'] / vr['max_v'] - 1) * 100, vr['open_contact_vac'], peak_open, vr['peak'], peak_open / vr['peak'], vr['coil_contact_vac'], peak_iso / 1000.0, vr['target_kv'],
        vr['coil_ohm'], coil_a * 1000, coil_a * D['rail']['volts'] * 1000, D['rail']['volts'], vr['price'], vr['k_il_price'], (vr['k_il_price'] - vr['price']) * vr['count']))
    prose.expect(sec_v, 'Margin on current', 1, '%.0f' % (vr['rating_a'] / cur['coil_steady']))
    prose.expect(sec_v, 'Margin on voltage', 1, '%.2f' % (peak_open / vr['peak']))
    prose.expect(sec_v, 'Isolation', 1, '%.2f kV' % (peak_iso / 1000.0))
    prose.expect(sec_v, 'Coil', 1, '%.1f mA' % (coil_a * 1000))
    prose.expect(sec_v, 'Coil', 1, '%.0f mW' % (coil_a * D['rail']['volts'] * 1000))
    prose.expect(sec_v, 'Price', 1, '%.2f' % ((vr['k_il_price'] - vr['price']) * vr['count']))

    # the pump drives: the current's rate of fall at its zero against the triac's commutating rating, for a full sine and for the half wave a series diode leaves
    pdv = D['pump_drive']
    sec_p = 'The pump drives'
    fall = lambda i, peak_factor: 2 * math.pi * pdv['mains_hz'] * peak_factor * i / 1000.0
    full = [fall(cur[k], math.sqrt(2)) for k in ('coffee_pump', 'steam_pump')]
    halfw = [fall(cur[k], 2.0) for k in ('coffee_pump', 'steam_pump')]
    out.append('pump drives: the current falls at its zero at %.2f and %.2f A/ms (coffee, steam) for a full sine, %.0f and %.0f times under the triac\'s %.0f A/ms; for the half wave of a series diode, whose peak is twice the rms, %.2f and %.2f A/ms, %.0f and %.0f times' % (
        full[0], full[1], pdv['rating_a_ms'] / full[0], pdv['rating_a_ms'] / full[1], pdv['rating_a_ms'], halfw[0], halfw[1], pdv['rating_a_ms'] / halfw[0], pdv['rating_a_ms'] / halfw[1]))
    prose.mention(sec_p, '%.2f A/ms for the coffee pump and %.2f A/ms for the steam pump' % (full[0], full[1]))
    prose.mention(sec_p, '%.0f and %.0f times under the rating' % (pdv['rating_a_ms'] / full[0], pdv['rating_a_ms'] / full[1]))
    prose.mention(sec_p, '%.2f A/ms and %.2f A/ms, %.0f and %.0f times under the rating' % (halfw[0], halfw[1], pdv['rating_a_ms'] / halfw[0], pdv['rating_a_ms'] / halfw[1]))
    prose.present(sec_p, 'series diode', 'the pump drives\' series diode')
    # the logic supply against this board's 5 V loads
    ra, rl = D['rail']['assumed'], D['rail']
    v5 = rl['volts']
    rows, total_ma, typ_ma = rail_rows(D)
    sec_r = 'The logic supply against this board'
    for key, v in rows:
        prose.expect(sec_r, key, 1, '%.1f' % v)
    prose.expect(sec_r, 'Total', 1, '%.0f mA' % total_ma)
    lines, chosen_margin = [], None
    for mdl in rl['modules']:
        m70, m50 = mdl['amps'] * mdl['at70'] * 1000.0 / total_ma, mdl['amps'] * mdl['at50'] * 1000.0 / total_ma
        lines.append('%s %.1f A at 70 C (%.2f times) and %.1f A at 50 C (%.2f times)' % (mdl['name'], mdl['amps'] * mdl['at70'], m70, mdl['amps'] * mdl['at50'], m50))
        prose.expect(sec_r, mdl['name'], 1, '%.2f' % m70)
        prose.expect(sec_r, mdl['name'], 2, '%.2f' % m50)
        prose.expect(sec_r, mdl['name'], 3, '%.0f' % (mdl['w'] * mdl['d']))
        if mdl.get('chosen'):
            chosen_margin = m70
            if m70 < rl['adequate'] - EPS:
                bad.append('the chosen module %s has %.2f times the 5 V budget at 70 C, the forms record calls %.1f adequate' % (mdl['name'], m70, rl['adequate']))
    smaller = [mdl for mdl in rl['modules'] if not mdl.get('chosen')]
    for mdl in smaller:
        if mdl['amps'] * mdl['at70'] * 1000.0 / total_ma >= rl['adequate'] - EPS:
            bad.append('the smaller module %s has %.2f times the budget at 70 C, at or over the %.1f that the record says it does not reach' % (mdl['name'], mdl['amps'] * mdl['at70'] * 1000.0 / total_ma, rl['adequate']))
    ch = [mdl for mdl in rl['modules'] if mdl.get('chosen')][0]
    pout = v5 * total_ma / 1000.0
    out.append('5 V rail: %s = %.1f mA with the controller at its maximum (%.1f mA at its typical %g mA); %s; the chosen %s delivers %.2f W at this load and dissipates %.2f W at %.0f %% efficiency (%.2f W at the 70 C current)' % (
        ', '.join('%s %.1f' % (k, v) for k, v in rows), total_ma, typ_ma, rl['controller_typ_ma'], '; '.join(lines), ch['name'], pout, pout / ch['eff'] - pout, ch['eff'] * 100,
        ch['amps'] * ch['at70'] * v5 / ch['eff'] - ch['amps'] * ch['at70'] * v5))
    prose.expect(sec_r, 'Total', 1, '%.2f' % (total_ma / 1000.0))
    sm = smaller[0]
    prose.mention(sec_r, 'at its typical %g mA the budget is %.0f mA and the IRM-10-5 would have %.2f times at 70 °C' % (rl['controller_typ_ma'], typ_ma, sm['amps'] * sm['at70'] * 1000.0 / typ_ma))
    prose.mention(sec_r, 'delivers %.2f W at this load and dissipates %.2f / %.2f − %.2f = %.2f W' % (pout, pout, ch['eff'], pout, pout / ch['eff'] - pout))
    rated_w = ch['amps'] * v5
    loss_rated = rated_w / ch['eff'] - rated_w
    loss_lin = ch['no_load_w'] + (loss_rated - ch['no_load_w']) * pout / rated_w
    out.append('module efficiency at this load: %.0f %% of its rated %.0f W; the sheet gives %.0f %% at rated load only, so the %.2f W above is flat-efficiency; a loss that falls in proportion to the load from %.2f W at rated load to the sheet\'s %.1f W at no load gives %.2f W, %.2f W more' % (
        pout / rated_w * 100, rated_w, ch['eff'] * 100, pout / ch['eff'] - pout, loss_rated, ch['no_load_w'], loss_lin, loss_lin - (pout / ch['eff'] - pout)))
    sec_hh = 'Heat'
    prose.mention(sec_hh, '%.2f W at this board\'s load' % w_mod)
    prose.mention(sec_hh, '%.2f W' % loss_lin)
    prose.mention(sec_hh, '%.0f %% of its rated' % (pout / rated_w * 100))
    il_k_per_w = D['relay']['rise_k'] / wb['relay_coil_w']
    il_body = ht['air_c'] + il_k_per_w * il_nom
    out.append('relay K_IL body, at the sheet\'s %g K for the coil\'s %g W (%.1f K for each watt): %.2f W would put it at %g + %.0f = %.0f C against the %g C of its ambient range, an upper bound with no allowance for heat leaving by the pins, and not a margin' % (
        D['relay']['rise_k'], wb['relay_coil_w'], il_k_per_w, il_nom, ht['air_c'], il_k_per_w * il_nom, il_body, D['relay']['ambient_c']))
    prose.mention(sec_il, '%.0f °C' % il_body)
    vr = D['valve_relay']
    vr_body = vr['ambient_c'] + vr['rise_k']
    if vr_body > vr['insulation_c'] + EPS:
        bad.append('the valve relay at its ambient limit of %g C and its own rise of %g K is %g C, over the %g C of its insulation class' % (vr['ambient_c'], vr['rise_k'], vr_body, vr['insulation_c']))
    out.append('valve relay own rise: about %g K at the rated coil voltage (the sheet\'s plotted line, read off the plot; it does not say for which coil), so %g C at its %g C ambient limit against %g C for insulation class F; %.0f mW of coil heat only while a valve is open' % (
        vr['rise_k'], vr_body, vr['ambient_c'], vr['insulation_c'], D['rail']['volts'] ** 2 / vr['coil_ohm'] * 1000))
    prose.mention(sec_hh, '%g K' % vr['rise_k'])
    # the fuses: the sharing proposal and the breaking capacity
    fu = D['fuse']
    area_holder = fu['holder'][0] * fu['holder'][1]
    shared_a = cur['coffee_pump'] + cur['steam_pump'] + cur['coil_steady']
    shared_inrush = cur['coffee_pump'] + cur['steam_pump'] + cur['coil_inrush']
    if shared_inrush > fu['share_limit_a'] + EPS:
        bad.append('the shared fuse would carry %.3f A, over the %.1f A the proposal allows' % (shared_inrush, fu['share_limit_a']))
    for o in fu['options']:
        if o['break_a'] >= fu['required_a'] - EPS:
            bad.append('the fuse option %s breaks %g A, which meets the %g A required; the record says none was found' % (o['name'], o['break_a'], fu['required_a']))
    out.append('fuses: %d holders of %.0f x %.0f mm = %.0f mm2 each; one shared fuse for both pumps and both valves would carry %.3f A steady and %.3f A at the coils\' inrush and save %.0f mm2; sourced breaking capacities %s against the %.0f A required' % (
        fu['holders'], fu['holder'][0], fu['holder'][1], area_holder, shared_a, shared_inrush, (fu['holders'] - 1) * area_holder,
        ', '.join('%s %g A' % (o['name'], o['break_a']) for o in fu['options']), fu['required_a']))
    sec_f = 'The fuses'
    prose.expect(sec_f, 'Space saved', 1, '%.0f' % ((fu['holders'] - 1) * area_holder))
    prose.expect(sec_f, 'Load behind a shared fuse', 1, '%.3f' % shared_a)
    prose.expect(sec_f, 'Load behind a shared fuse', 1, '%.3f' % shared_inrush)

    # functions, harnesses and kinds against their sources
    forms = open(os.path.join(record_dir, 'controller-board-function-forms.md'), encoding='utf-8').read()
    wanted = re.findall(r'^### (.*)$', forms.split('## The record of forms')[1].split('\n## ')[0], re.M)
    mine = [f['name'] for f in D['functions']]
    if sorted(mine) != sorted(wanted):
        bad.append('functions differ from the forms record\'s: %s' % sorted(set(mine) ^ set(wanted)))
    rows = table_rows(section(text, 'Every function has one owner'))
    for name in mine:
        if name not in rows:
            bad.append('the owner table has no row for %s' % name)
    bad += ['the owner table has a row the forms record does not: %s' % k for k in rows if k not in mine and k != 'Function (forms record)']
    bad += check_owners(D, text)
    pin = open(os.path.join(record_dir, 'connector-pinouts.md'), encoding='utf-8').read()
    heads = re.findall(r'^#{2,3} (.*)$', pin, re.M)
    others = re.findall(r'^### (.*)$', pin.split('## The other retained harnesses')[1].split('\n## ')[0], re.M)
    expected_heads = [h for h in heads if re.search(r'connector$|harness$', h) and not h.startswith('What') and 'no harness' not in h] + [h for h in others if 'no harness' not in h] + ['The nine terminals']
    for h in expected_heads:
        if not any(x['source'] in h for x in D['harnesses']):
            bad.append('the connector record\'s "%s" has no connector in the data' % h)
    for x in D['harnesses']:
        if not any(x['source'] in h for h in heads):
            bad.append('the data names a harness, "%s", that the connector record does not' % x['source'])
        bad += ['the connector %s of "%s" is not drawn' % (cn, x['source']) for cn in x['connector'].split() if cn not in bodies and cn not in ('tabs', 'to', '1', '9')]
    split = [f['name'] for f in D['functions'] if f.get('split')]
    out.append('functions: %d of the forms record\'s %d, each with one owner named in the owner table and no other (%d split across boards, each with its reason); connector record: %d harness headings, each with a connector' % (
        len(mine), len(wanted), len(split), len(set(expected_heads))))

    # costs
    cs, f = costs(D), D['cost']['fee']
    for name in 'ABC':
        x = cs[name]
        out.append('division %s: fabrication %.2f (%s), assembly charges %.2f, labour %.2f, duplicate Extended fees %.2f, link parts %.2f and joints %.2f, total %.2f USD' % (
            name, x['fab'], ', '.join('%s %.2f%s' % (n, v, ' band' if b else '') for n, v, b in x['lines']), x['asm'], x['lab'], x['dup'], x['lp'], x['lj'], x['total']))
        col = {'A': 1, 'B': 2, 'C': 3}[name]
        prose.expect('Candidate divisions', 'Total of the three rows above', col, '%.1f' % half(x['total']))
        prose.expect('Candidate divisions', 'Fabrication, estimated', col, '%.1f' % half(x['fab']))
        if name != 'A':
            prose.expect('Candidate divisions', 'Total of the three rows above', col, '%.1f more' % half(x['total'] - cs['A']['total']))
    for name in 'BC':
        for b in D['cost'][name]['boards']:
            if 'bay' in b:
                prose.expect('Candidate divisions', 'Boards, layers, outline', 'BC'.index(name) + 2, '{:,.0f}'.format(board_area(b)).replace(',', ' '))
    counts, header_types, header_pins = part_counts(D)
    pm = [p for p in D['parts']['main']]
    types_main = [(p['n'], p['cls'], p['tht'], counts.get(p['tag'], (0, 0))[1]) for p in pm]
    for p in pm:
        if counts.get(p['tag'], (0, 0))[0] < 1:
            bad.append('the part type %s has no block that holds one' % p['n'])
    ntypes = len(pm) + len(header_types)
    joints = sum(j for _, _, _, j in types_main) + header_pins
    tht_types = sum(1 for _, _, t, _ in types_main if t) + len(header_types)
    placed = ntypes - tht_types
    placed_fee = f['setup'] + f['stencil'] + f['ext_econ'] * placed
    placed_std = f['setup_std'] + f['stencil_std'] + f['fixtures_std'] + f['ext_std'] * placed
    all_econ = f['setup'] + f['stencil'] + f['ext_econ'] * ntypes
    all_std = f['setup_std'] + f['stencil_std'] + f['fixtures_std'] + f['ext_std'] * ntypes
    fixed = f['setup_std'] + f['stencil_std'] + f['fixtures_std']
    save_main = tht_types * f['ext_econ'] + joints * f['joint_hand'] + f['labour']
    out.append('header types by ways and pitch, from the blocks: %s; %d header pins' % (', '.join('%d-way %g mm x %d' % (k[0], k[1], v) for k, v in sorted(header_types.items(), key=lambda kv: (kv[0][1], kv[0][0]))), header_pins))
    out.append('Extended types of the main board: %d, of which %d are placed by the manufacturer (%d x %.2f = %.2f USD of feeder loading) and %d are fitted by the owner, headers included (%d x %.2f = %.2f USD that the manufacturer does not charge, %d header types of it = %.2f); hand-fitting the %d through-hole types and their %d joints saves %.2f USD against the manufacturer placing them as well' % (
        ntypes, placed, placed, f['ext_econ'], placed * f['ext_econ'], tht_types, tht_types, f['ext_econ'], tht_types * f['ext_econ'], len(header_types), len(header_types) * f['ext_econ'], tht_types, joints, save_main))
    out.append('Economic %.2f USD against Standard %.2f USD at the %d unique Extended types the manufacturer places and no Basic type; Standard adds %.2f for each Basic, Preferred or Extended type, so the two cross at %.1f Extended types with none; were all %d types placed by the manufacturer, Economic would be %.2f USD and Standard %.2f USD' % (
        placed_fee, placed_std, placed, f['ext_std'], (fixed - f['setup'] - f['stencil']) / (f['ext_econ'] - f['ext_std']), ntypes, all_econ, all_std))
    wcounts = wall_counts(D)
    wp = D['parts']['wall']
    wt = sum(1 for p in wp if p['cls'] == 'Extended' and all(wcounts.get(t, (0, 0))[0] for t in p['tags']))
    wj = sum(wcounts.get(t, (0, 0))[1] for p in wp for t in p['tags'])
    out.append('wall board hand-fitted: %d Extended types and %d joints save %.2f USD (its own order: %.2f setup and stencil, %.2f labour)' % (
        wt, wj, wt * f['ext_econ'] + wj * f['joint_hand'] + f['labour'] + f['setup'] + f['stencil'], f['setup'] + f['stencil'], f['labour']))
    sec_c = 'What the owner fits by hand, and what the extended parts cost'
    cross = (fixed - f['setup'] - f['stencil']) / (f['ext_econ'] - f['ext_std'])
    nwords = {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five', 6: 'six', 7: 'seven', 14: 'fourteen', 19: 'nineteen'}
    prose.counted(sec_c, '%s unique Extended types' % nwords.get(ntypes, str(ntypes)), 'the Extended types')
    prose.counted(sec_c, '%d placed by the manufacturer and %d fitted by the owner' % (placed, tht_types), 'the split of the Extended types')
    prose.counted(sec_c, '%d × %.2f = %.2f USD' % (placed, f['ext_econ'], placed * f['ext_econ']), 'the feeder loading the manufacturer charges')
    prose.counted(sec_c, '%d × %.2f = %.2f USD' % (tht_types, f['ext_econ'], tht_types * f['ext_econ']), 'the fee the owner\'s hand-fitting avoids')
    prose.counted(sec_c, '%.2f USD of it, the %d header types' % (len(header_types) * f['ext_econ'], len(header_types)), 'the header types')
    prose.counted(sec_c, '%.2f USD saved' % save_main, 'the hand-fitting saving')
    prose.counted(sec_c, '%d joints' % joints, 'the joints')
    prose.counted(sec_c, '%d header pins' % header_pins, 'the header pins')
    fee_, board_ = D['cost']['fee'], D['cost']['A']['boards'][0]
    bad += check_cost_record(source_texts(record_dir)['cost'] if cost is None else cost, dict(
        slot=plen, slot_density=plen * 1000.0 / oa, w=ob[2] - ob[0], h=ob[3] - ob[1], area=oa, types=ntypes, placed=placed, hand=tht_types, joints=joints,
        x0=ob[0], x1=ob[2], y0=ob[1], y1=ob[3], layers=board_['layers'], slots=len(slots), counts=counts, tabs=len(tb['list']) + 1,
        header_types=len(header_types), header_pins=header_pins, header_254=sum(1 for k in header_types if k[1] == 2.54),
        wall=wall_figures(D), wall_types=wt, wall_joints=wj, ext_econ=f['ext_econ'], joint_machine=f['joint_machine'], built=2,
        ref_area=fee_['ref_area'], eng4=fee_['eng4'], slope4=fee_['slope4'], eng2=fee_['eng2'], slope2=fee_['slope2'],
        fab=cs['A']['fab'], fab2=fabrication(D['cost'], dict(board_, layers=2))[0]))
    wsave = wt * f['ext_econ'] + wj * f['joint_hand'] + f['labour'] + f['setup'] + f['stencil']
    prose.counted(sec_c, '%.2f USD' % wsave, 'the wall board saving', 'The whole heater wall board', 2)
    prose.counted(sec_c, '%s unique Extended types' % nwords.get(wt, str(wt)), 'the wall board\'s Extended types', 'The whole heater wall board', 2)
    prose.counted(sec_c, '= %.2f USD' % (wt * f['ext_econ']), 'the wall board\'s Extended fee', 'The whole heater wall board', 2)
    prose.counted(sec_c, 'its %d joints' % wj, 'the wall board\'s joints', 'The whole heater wall board', 2)
    prose.mention(sec_c, 'Economic is %.2f USD and Standard %.2f USD' % (placed_fee, placed_std))
    prose.mention(sec_c, 'cross at %.1f unique Extended types' % cross)
    prose.mention(sec_c, 'Economic would be %.2f USD and Standard %.2f USD' % (all_econ, all_std))
    prose.counted(sec_c, '%d × %.2f' % (len(header_types), f['ext_econ']), 'the header types', '%d header types' % len(header_types), 2)
    prose.counted(sec_c, '%.2f' % (ntypes * f['ext_econ']), 'the Extended types and their fee', '%d types' % ntypes, 2)

    # the generated rows of the block tables
    for b in D['mains_blocks']:
        r = tuple(b['body'])
        for col, v in ((2, rng(r[0], r[2])), (3, rng(r[1], r[3])), (4, size(r)), (5, sq(area(r)))):
            prose.expect(heading, b['id'], col, v)
    for col, v in ((2, rng(strip[0], strip[2])), (3, rng(strip[1], strip[3])), (4, size(strip)), (5, sq(area(strip)))):
        prose.expect(heading, 'TABSTRIP', col, v)
    for b in D['lv_blocks']:
        r = tuple(b['rect'])
        for col, v in ((2, rng(r[0], r[2])), (3, rng(r[1], r[3])), (4, size(r)), (5, sq(area(r)))):
            prose.expect('The low-voltage blocks', b['id'], col, v)
    for col, v in ((4, size(box)), (5, sq(area(box)))):
        prose.expect('The low-voltage blocks', 'REED', col, v)
    if 'accepted_date' in src:
        prose.expect('Owner intent carried in', 'Relay contacts rated %g V AC' % vr['max_v'], 1, src['accepted_date'])
        prose.mention('The valve relays', 'accepted by the owner for relay contacts on %s' % src['accepted_date'])
    if need:
        for x in tb['list']:
            mv = x['y'] - x['found']
            if abs(mv) < EPS:
                continue
            d = copy.deepcopy(D)
            [t for t in d['tabs']['list'] if t['n'] == x['n']][0]['y'] -= math.copysign(0.5, mv)
            try:
                fails = [m for m in check_main(d, text, [], record_dir, src, route=False) if not m.startswith('table in') and not m.startswith('assumption token')]
            except Exception as e:
                fails = ['the model failed: %s' % type(e).__name__]
            if not fails:
                bad.append('tab %d is moved %+.1f mm and a tab 0.5 mm nearer its as-found place meets every rule of this record, so the move is more than a rule needs' % (x['n'], mv))
    bad += prose.check()
    return bad

# ---------------------------------------------------------------- the heater wall board
def wall_model(D):
    W = D['wall']
    mains = {}
    for b in W['blocks']:
        for n, r, net in b['mains']:
            mains[n] = (tuple(r), net, b['id'])
    for c in W['copper']:
        mains[c['id']] = (tuple(c['rect']), c['net'], c['id'])
    pockets = {n: (tuple(r), b['id']) for b in W['blocks'] for n, r in b['pockets']}
    bodies = {b['id']: tuple(b['body']) for b in W['blocks']}
    bodies.update({b['id']: tuple(b['rect']) for b in W['lv']})
    return mains, pockets, bodies

def copper_regions(D, mains):
    """Length, width, squares and resistance of each heater copper region, along its current axis."""
    W, reg = D['wall'], {}
    for cu in W['copper']:
        r = mains[cu['id']][0]
        length, width = ((r[2] - r[0]), (r[3] - r[1])) if W['axes'][cu['id']] == 'u' else ((r[3] - r[1]), (r[2] - r[0]))
        reg[cu['id']] = (length, width, length / width, length / width * W['sheet_mohm'])
    return reg

def check_wall(D, text, out, record_dir=None, src=None, nested=False):
    bad, prose = [], Prose(text, register=not nested)
    if src is None and record_dir is not None:
        src, sbad = parse_sources(source_texts(record_dir))
        bad += sbad
    if src is not None:
        bad += check_sources(D, src)
    bad += check_tokens(text, D)
    W, bas, f = D['wall'], dict(D['basis'], basic=D['basis']['m_creepage']), D['cost']['fee']
    mains, pockets, bodies = wall_model(D)
    w, h = W['size']
    board = (0.0, 0.0, w, h)
    bo = [(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)]
    sr = slot_rects(W['slots'])
    BR = W['bracket']
    ears = [tuple(e) for e in BR['ears']]
    if len(ears) != 2:
        return bad + ['the bracket has %d mounting ears, the wall board has two, one each side of it' % len(ears)]
    fitted = sorted(b['id'] for b in W['blocks'] if any(kind == 'triac' for kind, _ in b['fit']))
    if len(W['heat']['triacs']) != 2 or sorted(W['heat']['triacs']) != fitted:
        return bad + ['the heat figures name the triacs %s and the wall board fits the triacs %s, which must be the same two' % (sorted(W['heat']['triacs']), fitted)]
    if abs(ears[0][2]) > EPS or abs(ears[1][0] - w) > EPS or abs(ears[0][1]) > EPS or abs(ears[1][1]) > EPS or abs(ears[0][3] - ears[1][3]) > EPS:
        bad.append('the two mounting ears are not a pair on the wall edge, one each side of the board, of one depth')
    outline_w, wa, span_u = wall_outline(ears, w, h)
    out.append('wall board %g x %g mm and two mounting ears of %g x %g mm and %g x %g mm along its wall edge: %g mm over all, %.1f mm2' % (
        w, h, ears[0][2] - ears[0][0], ears[0][3], ears[1][2] - ears[1][0], ears[1][3], span_u, wa))
    if max(span_u, h) > bas['band']:
        bad.append('the wall board lies outside the lowest price band of %g mm' % bas['band'])
    for n, r in list(bodies.items()) + [(k, v[0]) for k, v in mains.items()]:
        if not inside(r, board):
            bad.append('%s lies outside the board' % n)
    names = list(bodies)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if ov(bodies[a], bodies[b]):
                bad.append('%s and %s overlap' % (a, b))
    edge = min(edge_distance(r, [(0, 0), (w, 0), (w, h), (0, h)]) for r in list(bodies.values()) + [v[0] for v in mains.values()])
    if edge < bas['edge_min'] - EPS:
        bad.append('a block stands %.2f mm from the board edge, the least allowed is %.1f' % (edge, bas['edge_min']))
    out.append('every block and mains rectangle lies %.1f mm or more inside the board edge (least allowed %.1f)' % (edge, bas['edge_min']))

    # guard 6: every mains rectangle keeps the basic creepage from the edge against the wall, and the board stands off by the owner's figure
    dw = bas['basic']
    for n, (r, net, own) in mains.items():
        if r[1] < dw - EPS:
            bad.append('mains copper %s is %.1f mm from the wall edge, the rule is %.1f' % (n, r[1], dw))
    near = min(r[1] for r, _, _ in mains.values())
    lead_v = []
    for b in W['blocks']:
        if b['body'][1] < dw - EPS:
            bad.append('the body of %s is %.1f mm from the wall edge, the rule is %.1f' % (b['id'], b['body'][1], dw))
        d_ = b.get('dip')
        if d_:
            cx_, cy_ = d_['centre']
            offs_ = [(k_ - (d_['pins'] - 1) / 2) * d_['pin_dy'] for k_ in range(d_['pins'])]
            for p_ in ([(cx_ + o_, cy_ - d_['row']) for o_ in offs_] if d_.get('axis') == 'u' else [(cx_ - d_['row'], cy_ + o_) for o_ in offs_]):
                lead_v.append(p_[1])
                if p_[1] < dw - EPS:
                    bad.append('a mains lead end of %s is %.1f mm from the wall edge, the rule is %.1f' % (b['id'], p_[1], dw))
    near_body = min(b['body'][1] for b in W['blocks'])
    out.append('mains copper to the wall edge: least %.1f mm of %.1f; part bodies least %.1f mm and mains lead ends of the opto-triacs least %.1f mm' % (
        near, dw, near_body, min(lead_v) if lead_v else math.inf))

    # the bracket: its two mounts, its legs against the mains copper, the triac tab faces, the driver's way to each screw, the wall cut
    keep_w = D['fixing']['E'] + D['basis']['creepage'] + D['fixing']['draw_tol']
    mounts = [tuple(m_) for m_ in BR['mounts']]
    if len(mounts) != 2:
        bad.append('the bracket has %d mounts, the wall board has two, one on each ear' % len(mounts))
    near_m = []
    for k_, m_ in enumerate(mounts):
        if k_ < len(ears) and not inside((m_[0], m_[1], m_[0], m_[1]), ears[k_]):
            bad.append('bracket mount %d does not lie on its ear' % (k_ + 1))
        dm = min(rd((m_[0], m_[1], m_[0], m_[1]), r) for r, _, _ in mains.values())
        near_m.append(dm)
        if dm < keep_w - EPS:
            bad.append('bracket mount %d is %.2f mm from mains copper, the rule is %.2f' % (k_ + 1, dm, keep_w))
        em_ = edge_distance((m_[0], m_[1], m_[0], m_[1]), outline_w)
        if em_ < D['fixing']['E'] + 0.5 - EPS:
            bad.append('bracket mount %d is %.2f mm from the board edge, the least is %.1f' % (k_ + 1, em_, D['fixing']['E'] + 0.5))
        for bn_, br_ in bodies.items():
            if rd((m_[0], m_[1], m_[0], m_[1]), br_) < D['fixing']['E'] - EPS:
                bad.append('%s lies inside the extent of bracket mount %d' % (bn_, k_ + 1))
    leg_v, lift, top_z, win_l = BR['leg_v'], BR['lift'], BR['top_z'], BR['window_l']
    bleg_u = BR['board_leg_u']
    leg_u = [w / 2 - win_l / 2, w / 2 + win_l / 2]
    leg = (bleg_u[0], leg_v[0], bleg_u[1], leg_v[1])
    sleg = (leg_u[0], leg_v[0], leg_u[1], leg_v[1])
    if not (inside(leg, (ears[0][0], 0.0, ears[1][2], ears[0][3])) and abs(leg_v[0]) < EPS):
        bad.append('the bracket\'s legs do not lie on the board\'s wall edge strip, inside the ears')
    if not inside(sleg, leg):
        bad.append('the standing leg does not lie within the board leg')
    for k_, m_ in enumerate(mounts):
        if not bleg_u[0] - EPS <= m_[0] <= bleg_u[1] + EPS:
            bad.append('bracket mount %d does not lie under the board leg' % (k_ + 1))
    stand = min(math.hypot(rd(leg, r), lift) for r, _, _ in mains.values())
    if stand < bas['basic'] - EPS:
        bad.append('the bracket stands %.2f mm in three dimensions from mains copper, the basic creepage is %.1f' % (stand, bas['basic']))
    faces = {k_: bodies[k_] for k_ in W['heat']['triacs']}
    for k_, r in faces.items():
        if abs(r[1] - leg_v[1]) > EPS or r[0] < leg_u[0] - EPS or r[2] > leg_u[1] + EPS:
            bad.append('the tab face of %s does not lie on the bracket\'s leg' % k_)
    others = {n_: r for n_, r in bodies.items() if n_ not in faces}
    reach = []
    screws = []
    for k_, r in sorted(faces.items()):
        cu = (r[0] + r[2]) / 2
        screws.append(cu)
        way = (cu - BR['driver'] / 2, r[3], cu + BR['driver'] / 2, h)
        crossed = [n_ for n_, o_ in others.items() if ov(way, o_)]
        if crossed and not nested:
            bad.append('the driver\'s way to the tab screw of %s is crossed by %s' % (k_, ', '.join(crossed)))
        reach.append('%s at u = %.1f' % (k_, cu))
    bolts = list(BR['bolts'])
    if len(bolts) != 2:
        bad.append('the bracket has %d wall bolts, the standing leg takes two' % len(bolts))
    for k_, b_ in enumerate(bolts):
        end_ = min(b_ - leg_u[0], leg_u[1] - b_)
        if end_ < BR['bolt_end'] - EPS:
            bad.append('wall bolt %d is %.2f mm from the end of the standing leg, the least held is %.1f' % (k_ + 1, end_, BR['bolt_end']))
        near_ = min(abs(b_ - x_) for x_ in screws + [y_ for j_, y_ in enumerate(bolts) if j_ != k_])
        if near_ < BR['driver'] - EPS:
            bad.append('wall bolt %d is %.2f mm from the nearest tab screw or wall bolt, the driver is %g mm wide' % (k_ + 1, near_, BR['driver']))
        way = (b_ - BR['driver'] / 2, leg_v[1], b_ + BR['driver'] / 2, h)
        crossed = [n_ for n_, o_ in others.items() if ov(way, o_)]
        if crossed:
            bad.append('the driver\'s way to wall bolt %d is crossed by %s' % (k_ + 1, ', '.join(crossed)))
    bolt_gap = min(abs(b_ - x_) for b_ in bolts for x_ in screws) if bolts else math.inf
    bolt_in = min(min(b_ - leg_u[0], leg_u[1] - b_) for b_ in bolts) if bolts else math.inf
    window = win_l * (top_z - lift)
    env_u = (min([e_[0] for e_ in ears] + [r_[0] for r_ in bodies.values()] + [0.0, bleg_u[0], leg_u[0]]), max([e_[2] for e_ in ears] + [r_[2] for r_ in bodies.values()] + [w, bleg_u[1], leg_u[1]]))
    env_z = (-(BR['board_t'] + max(BR['lead_behind'])), top_z)
    opening = (env_u[1] - env_u[0]) * (env_z[1] - env_z[0])
    opening_ph = '%.1f × %.1f mm = %.1f mm²' % (env_u[1] - env_u[0], env_z[1] - env_z[0], opening)
    out.append('bracket: board leg u %g to %g and standing leg u %g to %g (%g mm, the window), v %g to %g, standing %g mm clear of the board and %g mm high, %.2f mm in three dimensions from the nearest mains copper (basic creepage %.1f); mounts at %s, %s from mains copper (rule %.2f), %s from the board edge; wall bolts at u = %s, %.1f mm in from the leg\'s ends at the least and %.1f mm from the nearest tab screw at the least; tab faces on the leg at %s, a %g mm driver reaching each tab screw and each wall bolt from the board side with nothing in its way; wall cut %.1f mm2 (%g x %g mm) for the leg, in one place' % (
        bleg_u[0], bleg_u[1], leg_u[0], leg_u[1], win_l, leg_v[0], leg_v[1], lift, top_z, stand, bas['basic'], ', '.join('(%g, %g)' % m_ for m_ in mounts), ' and '.join('%.2f' % x_ for x_ in near_m), keep_w,
        ' and '.join('%.1f' % edge_distance((m_[0], m_[1], m_[0], m_[1]), outline_w) for m_ in mounts), ', '.join('%g' % b_ for b_ in bolts), bolt_in, bolt_gap, ' and '.join(reach), BR['driver'], window, win_l, top_z - lift))
    for ph_ in ('%.1f mm²' % window, '%.1f mm² in one place' % window):
        prose.counted('The heater wall board', ph_, 'the wall cut')
    out.append('plastic opening that admits the unit, without tilting: u %g to %g (%g mm) by z %g to %g (%g mm) from the board\'s component face, %.1f mm2; the window that exposes the steel under the leg is %.1f mm2' % (
        env_u[0], env_u[1], env_u[1] - env_u[0], env_z[0], env_z[1], env_z[1] - env_z[0], opening, window))
    prose.counted('The heater wall board', opening_ph, 'the plastic opening')
    prose.counted('Owner decisions pending', opening_ph, 'the plastic opening in D11', key='D11', col=1)
    wc_ = [ln_ for ln_ in (section(text, 'The heater wall board') or '').split('\n') if ln_.startswith('**The wall cut, and the owner')]
    if len(wc_) != 1:
        bad.append('the wall cut paragraph is stated %d times in the heater wall board section, once is required' % len(wc_))
    for ln_ in wc_:
        if opening_ph not in re.sub(r'[`*]', '', ln_):
            bad.append('counted figure not stated (the plastic opening in the wall cut paragraph)')
    acc_ = 'accepted as preliminary'
    cut_ph = '%.1f mm² in one place' % window
    for ln_ in wc_:
        for v_, w_ in ((acc_, 'the owner acceptance statement in the wall cut paragraph'), (cut_ph, 'the wall cut in the wall cut paragraph')):
            if v_ not in re.sub(r'[`*]', '', ln_):
                bad.append(('required statement missing (%s)' if v_ == acc_ else 'counted figure not stated (%s)') % w_)
    prose.counted('Owner decisions pending', cut_ph, 'the wall cut in D11', key='D11', col=1)
    prose.expect('Owner decisions pending', 'D11', 1, acc_, 'required statement missing (the owner acceptance statement in the D11 row)')
    ai_ = [c_ for k_, c_ in table_rows(section(text, 'Owner intent carried in') or '').items() if k_.startswith('The owner accepted the wall cut as preliminary')]
    if len(ai_) != 1:
        bad.append('the owner-intent table has %d rows that start "The owner accepted the wall cut as preliminary", once is required (the row carries the acceptance statement and the wall cut)' % len(ai_))
    for c_ in ai_:
        row_ = re.sub(r'[`*]', '', ' | '.join(c_))
        for v_, w_ in ((acc_, 'required statement missing (the owner acceptance statement in the owner-intent row of D11)'), (cut_ph, 'counted figure not stated (the wall cut in the owner-intent row of D11)'), (opening_ph, 'counted figure not stated (the plastic opening in the owner-intent row of D11)')):
            if v_ not in row_:
                bad.append(w_)
    items = [(n, r, net, own) for n, (r, net, own) in mains.items()]
    pb, mm, pp, npairs, _ = pair_rule(items, sr, bas, [], bo)
    bad += pb
    out.append('mains copper of different nets, from different parts: least straight %.1f mm of %.1f, %d pairs under the basic creepage of %.1f mm by straight line%s' % (
        mm, bas['m_clearance'], npairs, bas['basic'], ', all held by slots, least surface path %.1f mm' % pp if npairs else ''))

    # guard 5, wall board: pockets by straight distance and by surface path
    exempt = {b['id'] for b in W['blocks'] if b.get('dip')} | set(W.get('own_barrier', []))
    straight, path, pairs = math.inf, math.inf, 0
    for pn, (pr, own) in pockets.items():
        for mn, (mr, net, mown) in mains.items():
            if mown == own and own in exempt:
                continue
            d = rd(mr, pr)
            straight = min(straight, d)
            if d < bas['clearance'] - EPS:
                bad.append('pocket %s is %.2f mm from %s, the clearance is %.1f' % (pn, d, mn, bas['clearance']))
            if d < bas['creepage'] - EPS:
                pairs += 1
                L = surface_path(mr, pr, sr, bas['creepage'], bo)
                path = min(path, L)
                if L < bas['creepage'] - 0.05:
                    bad.append('surface path of %.1f mm between %s and pocket %s, creepage is %.1f' % (L, mn, pn, bas['creepage']))
    pins = dip_paths(W['blocks'], sr, 12.0, bo)
    for n, L in pins.items():
        path = min(path, L)
        if L < bas['creepage'] - 0.05:
            bad.append('opto-coupler %s: pin-to-pin surface path of %.1f mm, creepage is %.1f' % (n, L, bas['creepage']))
    header = min(rd(tuple(b['rect']), r) for b in W['lv'] for r, _, _ in mains.values())
    if header < bas['creepage'] - EPS:
        bad.append('the low-voltage header is %.1f mm from mains copper' % header)
    out.append('pockets: least straight %.1f mm of %.1f, %d pairs under %.1f mm straight all held by slots, least surface path %.1f mm of %.1f; the header is %.1f mm from mains copper' % (
        straight, bas['clearance'], pairs, bas['creepage'], path, bas['creepage'], header))
    out.append('opto-coupler pin-to-pin paths round the slots: ' + ', '.join('%s %.1f mm' % (n, L) for n, L in pins.items()))
    for s in W['slots']:
        r = tuple(s['rect'])
        if min(r[2] - r[0], r[3] - r[1]) < D['slot_width_min'] - EPS:
            bad.append('slot %s is narrower than %.1f mm' % (s['id'], D['slot_width_min']))
        if not inside(r, board):
            bad.append('slot %s lies outside the board' % s['id'])
        for n, rr in [(k, v[0]) for k, v in mains.items()] + [(k, v[0]) for k, v in pockets.items()] + [(b['id'], tuple(b['rect'])) for b in W['lv']]:
            if ov(grow(r, D['slot_copper']), rr):
                bad.append('slot %s cuts the copper of %s' % (s['id'], n))
    plen = sum(max(s['rect'][2] - s['rect'][0], s['rect'][3] - s['rect'][1]) for s in W['slots'])
    if plen * 1000.0 / wa > D['slot_density']:
        bad.append('slot path of %.1f m per m2 reaches the maker\'s %.0f m per m2' % (plen * 1000.0 / wa, D['slot_density']))
    out.append('slots: %d of %.0f mm of slot path = %.1f m per m2 of board, against %.0f' % (len(W['slots']), plen, plen * 1000.0 / wa, D['slot_density']))

    # guard 7: the heater path, from the ordered chains
    reg = copper_regions(D, mains)
    cur = dict(D['loads'], both=D['loads']['coffee'] + D['loads']['steam'])
    bud = W['budgets']
    chains = W['chains']
    for name, ids in chains.items():
        if len([x for x in ids if x.startswith('TRI_')]) != 1:
            bad.append('the %s path does not pass its triac once' % name)
        prev = None
        for x in ids:
            r = mains[x][0] if x in mains else mains['SENSE.p'][0] if x == 'SENSE' else bodies[x]
            if prev is not None and rd(prev, r) > 1e-6:
                bad.append('%s path: %s does not touch the copper before it' % (name, x))
            prev = r
    lists = list(chains.values())
    common = []
    while all(len(l) > len(common) for l in lists) and len({l[-1 - len(common)] for l in lists}) == 1:
        common.insert(0, lists[0][-1 - len(common)])
    own = {n: [x for x in ids[:len(ids) - len(common)] if x in reg] for n, ids in chains.items()}
    common = [x for x in common if x in reg]
    if not common:
        bad.append('the two heater paths share no copper after their triacs')
    onpath = {x for v in own.values() for x in v} | set(common)
    bad += ['copper region %s belongs to no heater path' % k for k in reg if k not in onpath]
    for k, v in reg.items():
        if v[1] < 0.381 * cur['overload'] - EPS:
            bad.append('%s is %.1f mm wide, 15 A needs %.2f' % (k, v[1], 0.381 * cur['overload']))
    mw = lambda ids, i: sum(reg[k][3] for k in ids) * i * i
    steam, coffee = own.get('steam', []), own.get('coffee', [])
    longest = max(reg.items(), key=lambda kv: kv[1][0])
    totals = {n: sum(reg[x][0] for x in own.get(n, []) + common) for n in chains}
    if longest[1][0] >= w / 2:
        bad.append('a run of %.1f mm crosses half the board' % longest[1][0])
    out.append('copper of the heater path: ' + ', '.join('%s %.1f x %.1f mm %.2f squares %.2f mohm' % (k, *reg[k]) for k in reg))
    out.append('copper dissipation: steam path %.0f mW at %.2f A and %.0f mW at %.0f A, coffee path %.0f mW at %.2f A and %.0f mW at %.0f A, common return %.0f mW at %.2f A and %.0f mW at %.0f A' % (
        mw(steam, cur['steam']), cur['steam'], mw(steam, cur['overload']), cur['overload'], mw(coffee, cur['coffee']), cur['coffee'], mw(coffee, cur['overload']), cur['overload'],
        mw(common, cur['both']), cur['both'], mw(common, cur['overload']), cur['overload']))
    out.append('longest run %s %.1f mm = %.0f %% of the %g mm width; copper run totals steam %.1f mm, coffee %.1f mm' % (longest[0], longest[1][0], longest[1][0] / w * 100, w, totals.get('steam', 0), totals.get('coffee', 0)))
    cop = 'Copper that carries the heater current'
    for key, rid in W['table_keys']:
        for col, v in ((1, '%.1f' % reg[rid][0]), (3, '%.2f' % reg[rid][2]), (4, '%.2f' % reg[rid][3])):
            prose.expect(cop, key, col, v)
    for key, ids, i in (('Steam element', steam, cur['steam']), ('Coffee element', coffee, cur['coffee']), ('Both, in the common return', common, cur['both'])):
        prose.expect(cop, key, 2, '%.2f' % sum(reg[k][3] for k in ids))
        prose.expect(cop, key, 4, '%.0f mW' % mw(ids, i))
        prose.expect(cop, key, 5, '%.0f mW' % mw(ids, cur['overload']))

    # heat: the triacs against the parts that derate and sense, with the limits the Assumptions table carries
    ht, lim = W['heat'], D['heat']['limits']
    tri = {k: bodies[k] for k in ht['triacs']}
    hot = {n: min(rd(bodies[n], r) for r in tri.values()) for n in ht['opto']}
    for n in ht['opto']:
        if hot[n] < lim['opto'] - EPS:
            bad.append('%s is %.1f mm from a triac, the rule is %g' % (n, hot[n], lim['opto']))
    ta = rd(*tri.values())
    if ta < lim['triac'] - EPS:
        bad.append('the two triacs stand %.1f mm apart on one metal wall, the assumed least is %g' % (ta, lim['triac']))
    out.append('heat: triacs %.1f mm apart (the assumed least %g); opto-coupler parts %.1f mm or more from them, rule %g' % (ta, lim['triac'], min(hot[n] for n in ht['opto']), lim['opto']))
    th, air_t, pw = ht['thermal'], D['heat']['air_c'], ht['triacs']
    rise_t = {k: v * th['rth_jc'] for k, v in pw.items()}
    room_t = {k: th['tj_max'] - rise_t[k] - air_t for k in pw}
    total_t = sum(pw.values())
    hot_k = max(pw, key=lambda k: pw[k])
    alone_t, shared_t = room_t[hot_k] / pw[hot_k], min(room_t.values()) / total_t
    if min(room_t.values()) <= 0:
        bad.append('a triac\'s junction rise over its case leaves no room under the junction limit at the assumed air temperature')
    out.append('triac heat: the two tab faces share one metal wall: %.2f W and %.2f W, %.2f W together; junction over case %.1f K and %.1f K at %g K/W; the case may stand at %.1f and %.1f C of the %g C limit, so at %g C air the wall and the tab interface may rise %.1f K over the air for the %.2f W triac: %.1f K/W from the tab face to the air if it heats the wall alone, %.1f K/W if both do' % (
        pw['TRI_C'], pw['TRI_S'], total_t, rise_t['TRI_C'], rise_t['TRI_S'], th['rth_jc'], th['tj_max'] - rise_t['TRI_C'], th['tj_max'] - rise_t['TRI_S'], th['tj_max'], air_t, room_t[hot_k], pw[hot_k], alone_t, shared_t))
    if nested is False:
        for ph in ('%.2f W and %.2f W' % (pw['TRI_C'], pw['TRI_S']), '%.1f K and %.1f K' % (rise_t['TRI_C'], rise_t['TRI_S']), '%.1f K/W' % alone_t, '%.1f K/W' % shared_t, '%.1f mm apart' % ta):
            prose.mention('The heater wall board', ph)
    for ph in ('reads on when the triac is open and the element intact', 'off when the triac conducts', 'failed-to-close reads on while commanded on', 'an open element reads off'):
        prose.present('The heater wall board', ph, 'the confirm polarity')
    wcount = wall_counts(D)
    wjoints = sum(j for _, j in wcount.values())
    out.append('hand-soldered joints of the board: %d (%s)' % (wjoints, ', '.join('%s %d' % (t, wcount[t][1]) for t in sorted(wcount))))
    section_wall = 'The heater wall board'
    for b in W['blocks']:
        r = tuple(b['body'])
        for col, v in ((2, rng(r[0], r[2])), (3, rng(r[1], r[3])), (4, size(r)), (5, sq(area(r)))):
            prose.expect(section_wall, b['id'], col, v)
    sec = f['slope4'] * wa / f['ref_area']
    out.append('wall board fabrication: own board %.2f USD in the band; as a section %.2f USD (inferred), %.2f less, or %.2f more than the maker\'s application price of 2.00 USD' % (f['band2'], sec, f['band2'] - sec, sec - 2.0))
    prose.expect(section_wall, 'Fabrication', 2, '%.2f' % sec)
    if 'wall_dnp' in D and not nested:
        D2 = copy.deepcopy(D)
        D2['wall'] = D2.pop('wall_dnp')
        sub_out = []
        sub_bad = [b for b in check_wall(D2, text, sub_out, record_dir, src, nested=True) if not b.startswith('table in')]
        V = D['wall_dnp']
        w2, h2 = V['size']
        dn = [b for b in V['blocks'] if b.get('dnp')]
        extra = {}
        for b in dn:
            for tag, j in b['dnp']:
                c0, j0 = extra.get(tag, (0, 0))
                extra[tag] = (c0 + 1, j0 + j)
        wc2 = wall_counts(D2)
        out.append('the board with the %d unpopulated confirm places: %g x %g mm = %g mm2, %+.1f %% against the drawn board; %d joints fitted, and %d more if the places are fitted; %s' % (
            len(dn), w2, h2, w2 * h2, (w2 * h2 / (w * h) - 1) * 100, sum(j for _, j in wc2.values()), sum(j for _, j in extra.values()), 'every check passes' if not sub_bad else 'it FAILS: ' + '; '.join(sub_bad)))
        bad += ['the board with the unpopulated places: ' + b for b in sub_bad]
    bad += prose.check()
    return bad

# ---------------------------------------------------------------- expected output, commands, selftest
def expected(text, label, out):
    found = blocks_of(text, label)
    if len(found) != 1:
        return ['the record has no expected-output block %s' % label]
    want = found[0].rstrip('\n').split('\n')
    if want != out:
        first = next(((a, b) for a, b in zip(want, out) if a != b), None)
        return ['the printed output differs from the block %s%s' % (label, (': "%s" against "%s"' % first) if first else ', in length')]
    return []

def run(cmd, text, D, record_dir):
    out = []
    bad = check_main(D, text, out, record_dir, need=True, whatif=True) if cmd == 'main' else check_wall(D, text, out, record_dir)
    return out, bad

def set_in(d, path, value):
    for k in path[:-1]:
        d = d[k]
    d[path[-1]] = value

def mb(d, i):
    return [b for b in d['mains_blocks'] if b['id'] == i][0]

def lvb(d, i):
    return [b for b in d['lv_blocks'] if b['id'] == i][0]

def slot(d, i):
    return [s for s in d['slots'] if s['id'] == i][0]

def move_block(d, i, dy):
    b = mb(d, i)
    b['body'][1] += dy
    b['body'][3] += dy
    for m in b['mains']:
        m[1][1] += dy
        m[1][3] += dy
    for p in b['pockets']:
        p[1] += dy
        p[3] += dy
    for key in ('hot', 'heat'):
        if b.get(key):
            b[key][1] += dy
            b[key][3] += dy

# Each perturbation of the data: (what, command, change, flags). A guard that stops guarding makes the selftest fail. The flags: 'route' runs the
# route search, 'need' the check that every moved tab is needed, and 'proof' the proof that a join called inner has no surface route. What each
# one targets is named in INTENDED, below.
def tab(d, n):
    return [t for t in d['tabs']['list'] if t['n'] == n][0]

def pad_header(d, i):
    lvb(d, i)['conn']['ways'] += 1

GUARDS = (
    ('move a tab 0.3 mm toward the fixing', 'main', lambda d: tab(d, 1).update(y=tab(d, 1)['y'] - 0.3)),
    ('move a tab 3.1 mm and its as-found position with it', 'main', lambda d: tab(d, 6).update(y=76.0, found=76.0)),
    ('move the third tab 0.5 mm beyond what the rules need', 'main', lambda d: tab(d, 3).update(y=tab(d, 3)['y'] + 0.5), 'need'),
    ('move the second tab 0.5 mm beyond what the rules need', 'main', lambda d: tab(d, 2).update(y=tab(d, 2)['y'] + 0.5), 'need'),
    ('bring the pads of two tabs of different nets together, the pitch rule weakened', 'main', lambda d: (d['tabs'].update(pitch=0.0), tab(d, 6).update(y=39.0))),
    ('widen a tab pad by a thicker blade in the data', 'main', lambda d: d['tabs'].update(thick=7.0)),
    ('shrink the outline by 7 mm on the right', 'main', lambda d: d.update(outline=[[1.0, 2.0], [125.0, 2.0], [125.0, 127.0], [1.0, 127.0]])),
    ('move the reed 2 mm', 'main', lambda d: d['reed'].update(lower=[120.0, 17.5])),
    ('shorten the slot between the link\'s two sides', 'main', lambda d: slot(d, 'SL_LINK')['rect'].__setitem__(2, 14.0)),
    ('shorten the slot between the live link and the neutral pad', 'main', lambda d: slot(d, 'SL_LN')['rect'].__setitem__(2, 6.0)),
    ('shorten the slot between the two pump strips', 'main', lambda d: slot(d, 'SL_PP')['rect'].__setitem__(2, 30.0)),
    ('shorten the slot between the voltage measurement\'s two sides', 'main', lambda d: slot(d, 'SL_VM')['rect'].__setitem__(3, 51.0)),
    ('drop a function', 'main', lambda d: d['functions'].pop()),
    ('blank the owner of a function', 'main', lambda d: d['functions'][0].update(owner='')),
    ('give a function an owner the record does not declare', 'main', lambda d: d['functions'][0].update(owner='cloud')),
    ('bring a block into the reed keep-out', 'main', lambda d: lvb(d, 'MCU').update(rect=[112.0, 20.0, 120.0, 28.0])),
    ('move a hole under a tab', 'main', lambda d: d['holes'].update(P1=[9.0, 9.0])),
    ('make the module 30 mm high', 'main', lambda d: mb(d, 'MODULE').update(h=30.0)),
    ('move the module 7.5 mm down toward the interlock relay', 'main', lambda d: move_block(d, 'MODULE', -7.5)),
    ('move the voltage measurement 8 mm down toward the interlock relay', 'main', lambda d: move_block(d, 'VMEAS', -8.0)),
    ('move a sensing block 10 mm from the interlock relay', 'main', lambda d: lvb(d, 'BREW_A_C').update(rect=[68.0, 14.5, 78.0, 22.5])),
    ('empty the list of sensing blocks', 'main', lambda d: d['heat'].update(sense=[])),
    ('report a part that holds as not held', 'main', lambda d: d['heat']['accepted'].append(['K_V2', 'MODULE'])),
    ('stop reporting a part that does not hold', 'main', lambda d: d['heat']['accepted'].pop(0)),
    ('accept the voltage measurement as not held from the interlock relay', 'main', lambda d: d['heat']['accepted'].append(['VMEAS', 'K_IL'])),
    ('rate the voltage measurement\'s part to 125 C and leave it in the 85 C class', 'main', lambda d: d['heat']['class85'][4].update(limit_c=125.0)),
    ('list a part rated to 85 C as outside the class', 'main', lambda d: d['heat']['outside'].append({'id': 'MCU', 'limit_c': 85.0})),
    ('weaken the interlock relay to under a watt', 'main', lambda d: d['heat'].update(source_w=1.2)),
    ('drop a harness connector', 'main', lambda d: d['harnesses'].pop()),
    ('weaken the lid keep-out to 1.0 mm', 'main', lambda d: d['fixing'].update(lid_keep=1.0)),
    ('weaken the least slot width to 0.2 mm', 'main', lambda d: d.update(slot_width_min=0.2)),
    ('weaken the edge distance to 0', 'main', lambda d: d['basis'].update(edge_min=0.0)),
    ('widen the reed tolerance to 5 mm', 'main', lambda d: d['reed'].update(tol=5.0)),
    ('weaken the signed creepage to 8.0 mm', 'main', lambda d: d['basis'].update(creepage=8.0)),
    ('weaken the signed mains-to-mains creepage to 3.0 mm', 'main', lambda d: d['basis'].update(m_creepage=3.0)),
    ('weaken the signed mains-to-mains clearance to 1.0 mm', 'main', lambda d: d['basis'].update(m_clearance=1.0)),
    ('bring the relay\'s two contacts 1.5 mm apart', 'main', lambda d: mb(d, 'K_IL')['mains'][1].__setitem__(1, [17.0, 19.775, 25.0, 27.05])),
    ('put the relay\'s two contacts on one net', 'main', lambda d: mb(d, 'K_IL')['mains'][0].__setitem__(2, 'LINE1')),
    ('move a relay leg out of its copper', 'main', lambda d: mb(d, 'K_IL')['terminals'].update(legs_x=[17.6, 23.0])),
    ('narrow a link region', 'main', lambda d: d['link']['chain'][1].update(rect=[17.0, 34.3, 19.45, 38.8])),
    ('put the varistor\'s line pad on the fuse\'s line side', 'main', lambda d: mb(d, 'RV_IL')['mains'][0].__setitem__(2, 'LINE_IN')),
    ('move the varistor 4 mm along X, off the fuse\'s piece of copper but within the distance', 'main', lambda d: mb(d, 'RV_IL')['mains'][0].__setitem__(1, [24.2, 43.8, 26.2, 45.8])),
    ('shrink the varistor\'s body 1 mm from the module so its stated distance is stale', 'main', lambda d: mb(d, 'RV_IL')['body'].__setitem__(3, 47.3)),
    ('raise the varistor distance limit in the data alone to 50 mm', 'main', lambda d: set_in(d, ['entry', 'against_mm'], 50.0)),
    ('move the varistor 12 mm away from the fuse', 'main', lambda d: mb(d, 'RV_IL')['mains'][0].__setitem__(1, [31.5, 43.3, 33.5, 45.3])),
    ('take the entry fuse out of the link', 'main', lambda d: d['link']['chain'].pop(0)),
    ('put the entry fuse\'s load-side clip on the net of the pad of tab 2', 'main', lambda d: mb(d, 'F_IL')['mains'][0].__setitem__(2, 'LINE_IN')),
    ('tap the logic supply from the line before the fuse', 'main', lambda d: d['link']['taps'][0].update(net='LINE_IN')),
    ('shorten the entry fuse holder to 20 mm', 'main', lambda d: mb(d, 'F_IL')['body'].__setitem__(2, 37.0)),
    ('take the line side of the fuse off the inner-layer list', 'main', lambda d: d['inner_nets'].remove('LINE_IN')),
    ('hold the line before the fuse to the basic creepage from LINE1 only', 'main', lambda d: d['open_contact'].pop('upstream')),
    ('tap the logic supply from the LINE1 net', 'main', lambda d: d['link']['taps'][0].update(net='LINE1')),
    ('draw a block of a kind that is removed', 'main', lambda d: d['lv_blocks'].append({'id': 'TH1_H', 'fn': 'x', 'rect': [85.2, 70.3, 92.2, 77.8], 'tht': True, 'h': 15.0, 'region': 'hdr', 'kind': 3, 'conn': {'ways': 2, 'pitch': 2.54}})),
    ('take the circuit block of the kept second current channel away', 'main', lambda d: (d.update(lv_blocks=[b for b in d['lv_blocks'] if b['id'] != 'CURR2_C']), d['heat']['sense'].remove('CURR2_C'))),
    ('restore tab 4 as drawn and take it off the removed list', 'main', lambda d: (d['tabs']['list'].append({'n': 4, 'name': 'STMHEATER', 'y': 52.9, 'found': 52.9}), d['tabs'].update(removed=[r for r in d['tabs']['removed'] if r['n'] != 4]))),
    ('restore the pad of the removed tab 4', 'main', lambda d: d['tabs']['list'].append({'n': 4, 'name': 'STMHEATER', 'y': 52.9, 'found': 52.9})),
    ('lose track of the removed tab 5', 'main', lambda d: d['tabs']['removed'].pop()),
    ('rename a removed tab', 'main', lambda d: d['tabs']['removed'][0].update(name='ELEMENT')),
    ('move the current shunt off the return path: lift its second land off the pour', 'main', lambda d: d['return']['shunt']['lands'][1][1].__setitem__(3, 44.9)),
    ('tap the neutral from the pad of tab 3, below the shunt', 'main', lambda d: d['link']['taps'][1].update(**{'from': 'tab 3'})),
    ('raise the least tab pitch to 9.0 mm, so the return landing stands short of it', 'main', lambda d: d['tabs'].update(pitch=9.0)),
    ('join a pump\'s return at the pad of tab 3, on the plug side of the shunt', 'main', lambda d: d['return']['branches'][2].update(joins='the pad of tab 3')),
    ('join the valves\' return at the pad of tab 3, on the plug side of the shunt', 'main', lambda d: d['return']['branches'][4].update(joins='tab 3')),
    ('leave a pump\'s return out of the neutral return', 'main', lambda d: d['return']['branches'].pop(3)),
    ('end a pump\'s return on copper of another net', 'main', lambda d: mb(d, 'P_C')['mains'][1].__setitem__(2, 'COFFPUMP')),
    ('call the valves\' return, which has a surface route, an inner-layer join', 'main', lambda d: d['return']['branches'][4].update(layer='inner'), 'route', 'proof'),
    ('take the current shunt away', 'main', lambda d: d['return'].pop('shunt')),
    ('give the current shunt no part', 'main', lambda d: d['return']['shunt'].update(parts=0)),
    ('narrow the shunt\'s first land to 4 mm', 'main', lambda d: d['return']['shunt']['lands'][0][1].__setitem__(2, 9.0)),
    ('stop the analogue region at Y 30.1, where the module once stood', 'main', lambda d: [r for r in d['regions']['ana'] if r['id'] == 'AR_b'][0]['rect'].__setitem__(3, 30.1)),
    ('draw the analogue region over the interlock relay\'s keep-out', 'main', lambda d: [r for r in d['regions']['ana'] if r['id'] == 'AR_b'][0]['rect'].__setitem__(0, 70.0)),
    ('draw a block for the further switched output that the owner removed', 'main', lambda d: [k for k in d['kinds'] if k['n'] == 6][0].update(blocks=['K_V1'])),
    ('keep a kind that the regions cannot hold', 'main', lambda d: [k for k in d['kinds'] if k['n'] == 3][0].pop('rank')),
    ('remove the required mark from the supply voltage kind', 'main', lambda d: [k for k in d['kinds'] if k['n'] == 1][0].pop('required')),
    ('draw a block outside its region', 'main', lambda d: lvb(d, 'WT1_C').update(rect=[78.0, 22.9, 97.0, 31.5])),
    ('make the valve relay\'s switching voltage 230 V', 'main', lambda d: d['valve_relay'].update(max_v=230.0)),
    ('make the valve relay\'s switching voltage 240 V', 'main', lambda d: d['valve_relay'].update(max_v=240.0)),
    ('give the valve relay\'s open contacts 200 V', 'main', lambda d: d['valve_relay'].update(open_contact_vac=200.0)),
    ('count a smaller module as adequate', 'main', lambda d: d['rail']['modules'][1].update(at70=1.2)),
    ('load the 5 V rail beyond the chosen module', 'main', lambda d: d['rail'].update(controller_ma=900.0)),
    ('take a coil at its nominal resistance', 'main', lambda d: d['relay'].update(coil_tol=0.0)),
    ('find a fuse that meets the breaking capacity', 'main', lambda d: d['fuse']['options'].append({'name': 'x', 'break_a': 6000.0})),
    ('add a pin to a header, the record\'s counts unchanged', 'main', lambda d: pad_header(d, 'WT1_H')),
    ('change the pitch of a header, the record\'s types unchanged', 'main', lambda d: lvb(d, 'KNOB')['conn'].update(pitch=2.54)),
    ('add a joint to the module, the record\'s joints unchanged', 'main', lambda d: mb(d, 'MODULE')['pins'].append([40.0, 60.0])),
    ('take a fuse holder out of the pump strip', 'main', lambda d: mb(d, 'P_C').update(fit=[['clip', 0], ['pump_triac', 0], ['pump_opto', 0]])),
    ('widen the trace until the two-way valve\'s lead has no route', 'main', lambda d: d['trace'].update(w=3.0), 'route'),
    ('change the trace width tolerance', 'main', lambda d: d['trace'].update(tol=0.0), 'route'),
    ('close the channel between a valve\'s tab and its relay with a slot', 'main', lambda d: d['slots'].append({'id': 'X', 'rect': [14.0, 56.0, 15.0, 100.0]}), 'route'),
    ('bring a mains rectangle within 5 mm of the wall edge', 'wall', lambda d: d['wall']['blocks'][0]['mains'][0][1].__setitem__(1, 3.0)),
    ('shorten the steam opto-triac\'s slot so its pins straddle the end', 'wall', lambda d: d['wall']['slots'][0]['rect'].__setitem__(2, 5.0)),
    ('break the heater path chain', 'wall', lambda d: d['wall']['chains']['steam'].pop(2)),
    ('narrow a heater copper region', 'wall', lambda d: d['wall']['copper'][1]['rect'].__setitem__(3, 8.0)),
    ('widen the coffee triac toward the steam triac, 8.6 mm from it', 'wall', lambda d: [b for b in d['wall']['blocks'] if b['id'] == 'TRI_C'][0].update(body=[30.0, 5.0, 46.0, 10.5])),
    ('move an opto-triac 9.5 mm from a triac', 'wall', lambda d: [b for b in d['wall']['blocks'] if b['id'] == 'OPTO_C'][0].update(body=[17.0, 20.0, 27.0, 31.0])),
    ('bring an unpopulated confirm place 1.0 mm from the other\'s mains copper', 'wall', lambda d: [b for b in d['wall_dnp']['blocks'] if b['id'] == 'PRES_C'][0]['mains'][0][1].__setitem__(0, 27.0)),
    ('bring an unpopulated confirm place within 5.0 mm of the wall edge', 'wall', lambda d: [b for b in d['wall_dnp']['blocks'] if b['id'] == 'PRES_S'][0]['mains'][0][1].__setitem__(1, 3.0)),
    ('weaken the opto-triac distance rule to 10 mm', 'wall', lambda d: d['heat']['limits'].update(opto=10.0)),
    ('relabel a copper region\'s net so it touches another', 'wall', lambda d: d['wall']['copper'][0].update(net='R')),
    ('bring the two ends of a varistor 1 mm apart', 'wall', lambda d: [b for b in d['wall']['blocks'] if b['id'] == 'MOV_S'][0]['mains'][1].__setitem__(1, [4.5, 17.0, 9.0, 23.0])),
    ('bring the two ends of a varistor 2 mm apart', 'wall', lambda d: [b for b in d['wall']['blocks'] if b['id'] == 'MOV_S'][0]['mains'][1].__setitem__(1, [5.5, 17.0, 9.0, 23.0])),
    ('move the body of a part of the wall board within 5 mm of the wall edge, its copper left where it was', 'wall', lambda d: [b for b in d['wall']['blocks'] if b['id'] == 'MOV_S'][0]['body'].__setitem__(1, 3.0)),
    ('move the mains pins of an opto-triac within 5 mm of the wall edge', 'wall', lambda d: [b for b in d['wall']['blocks'] if b['id'] == 'OPTO_S'][0]['dip'].update(centre=[6.0, 7.5])),
    ('name the contact of another relay in the link', 'main', lambda d: d['link']['chain'][2].update(contact='K_V1')),
    ('name no contact in the link', 'main', lambda d: d['link']['chain'][2].update(contact='')),
    ('put the contact of the link between the wrong two regions', 'main', lambda d: d['link']['chain'].insert(1, d['link']['chain'].pop(2))),
    ('delete the supply voltage kind, which is required, from the data', 'main', lambda d: d.update(kinds=[k for k in d['kinds'] if k['n'] != 1])),
    ('delete every kind that the record marks required, and its mark', 'main', lambda d: d.update(kinds=[dict((a, b) for a, b in k.items() if a != 'required') for k in d['kinds']])),
    ('take the safety-approval ratings out of the relay', 'main', lambda d: d['relay'].pop('vde')),
    ('rate the relay at its highest ambient under the overload band', 'main', lambda d: d['relay']['vde'][1].__setitem__(1, 10.0)),
    ('drop an owner decision from the data', 'main', lambda d: d['owner_decisions'].pop()),
    ('retitle an owner decision in the data', 'main', lambda d: d['owner_decisions'][0].update(title='A different decision')),
    ('give an owner decision a home that does not point to it', 'main', lambda d: d['owner_decisions'][0].update(home='Heat')),
    ('change the pitch of the weight headers to 2.54 mm, the record unchanged', 'main', lambda d: lvb(d, 'WT1_H')['conn'].update(pitch=2.54)),
    ('leave out the hole at point 3', 'main', lambda d: d['holes'].pop('P3')),
    ('bring tab 9 back to its as-found place, inside the fixing distance of point 3', 'main', lambda d: tab(d, 9).update(y=111.4)),
    ('call a net that has a surface route an inner-layer join', 'main', lambda d: d['inner_nets'].append('COFVALVE'), 'route'),
    ('take a net that has no surface route off the inner-layer list', 'main', lambda d: d['inner_nets'].remove('HOTVALVE'), 'route'),
    ('leave the 120 kohm mains-sense resistor out of the part types', 'main', lambda d: d['parts']['main'].pop()),
    ('make the pump opto-triac a surface-mount part again', 'main', lambda d: [p for p in d['parts']['main'] if p['tag'] == 'pump_opto'][0].update(tht=False)),
    ('bring a bracket mount within 13.25 mm of mains copper', 'wall', lambda d: d['wall']['bracket'].update(mounts=[[-9.0, 4.0], [69.5, 4.0]])),
    ('lift the bracket only 3 mm clear of the board', 'wall', lambda d: d['wall']['bracket'].update(lift=3.0)),
    ('stand the bracket\'s leg 1 mm off the triac faces', 'wall', lambda d: d['wall']['bracket'].update(leg_v=[0.0, 4.0])),
    ('leave one of the bracket\'s mounting ears out', 'wall', lambda d: d['wall']['bracket']['ears'].pop()),
    ('leave one of the bracket\'s mounts out', 'wall', lambda d: d['wall']['bracket']['mounts'].pop()),
    ('leave the bracket without mounts', 'wall', lambda d: d['wall']['bracket'].update(mounts=[])),
    ('put a bracket mount off its ear', 'wall', lambda d: d['wall']['bracket'].update(mounts=[[-12.5, 4.0], [69.5, 12.0]])),
    ('leave a triac out of the heat figures', 'wall', lambda d: d['wall']['heat']['triacs'].pop('TRI_C')),
    ('end the bracket\'s leg short of the steam triac', 'wall', lambda d: d['wall']['bracket'].update(window_l=30.0)),
    ('make the wall cut\'s window taller', 'wall', lambda d: d['wall']['bracket'].update(top_z=36.5)),
    ('lengthen the triac lead ends behind the board', 'wall', lambda d: d['wall']['bracket'].update(lead_behind=[6.4, 9.4])),
    ('widen the bracket\'s left mounting ear', 'wall', lambda d: d['wall']['bracket']['ears'][0].__setitem__(0, -20.0)),
    ('put a part in the driver\'s way to a wall bolt', 'wall', lambda d: d['wall']['bracket'].update(bolts=[10.0, 59.5])),
    ('leave a drawn tab out of the data', 'main', lambda d: d['tabs'].update(list=[x for x in d['tabs']['list'] if x['n'] != 7])),
    ('leave the hole at point 1 out', 'main', lambda d: d['holes'].pop('P1')),
    ('put a part in the driver\'s way to a tab screw', 'wall', lambda d: [b for b in d['wall']['blocks'] if b['id'] == 'OPTO_S'][0].update(body=[13.0, 30.5, 23.0, 41.5])),
)

# What each perturbation of the data targets: a pattern that a message of the check it aims at matches. A perturbation is caught only when such a
# message is produced. A message about a table of the record ('table in ...') never counts, since a producer can regenerate a table to match the
# data, and nor does a message of some other check that the perturbation happens to break. A perturbation with no entry here fails the selftest.
INTENDED = {
    'move a tab 0.3 mm toward the fixing': r'mains copper [0-9.]+ mm from P1, the rule is',
    'move a tab 3.1 mm and its as-found position with it': r'tab 6 as found is 76\.0 in the data and 79\.1 in its source',
    'move the third tab 0.5 mm beyond what the rules need': r'tab 3 is moved .* more than a rule needs',
    'move the second tab 0.5 mm beyond what the rules need': r'tab 2 is moved .* more than a rule needs',
    'bring the pads of two tabs of different nets together, the pitch rule weakened': r'mains copper tab [0-9] and tab [0-9] are 0\.00 mm apart',
    'widen a tab pad by a thicker blade in the data': r'the tab thickness is 7\.0 in the data and 0\.81 in its source',
    'shrink the outline by 7 mm on the right': r'CON2 lies outside the outline',
    'move the reed 2 mm': r"the reed's lower lead .* is more than 1\.0 mm from the recorded",
    "shorten the slot between the link's two sides": r'surface path of [0-9.]+ mm between mains copper LK_L and LK_L1, the rule is 10\.0',
    'shorten the slot between the live link and the neutral pad': r'between mains copper tab 3 and LK_L, the rule is 4\.1',
    'shorten the slot between the two pump strips': r'between mains copper P_C and P_S, the rule is 4\.1',
    "shorten the slot between the voltage measurement's two sides": r'opto-coupler VMEAS: pin-to-pin surface path',
    'drop a function': r"functions differ from the forms record's",
    'blank the owner of a function': r'the function Controller has the owner ""',
    'give a function an owner the record does not declare': r'the function Controller has the owner "cloud"',
    'bring a block into the reed keep-out': r'MCU lies inside the reed keep-out',
    'move a hole under a tab': r'mounting hole P1 is \(9\.0, 9\.0\) in the data',
    'make the module 30 mm high': r'MODULE stands 30\.0 mm high under a ceiling',
    'move the module 7.5 mm down toward the interlock relay': r"the interlock relay is [0-9.]+ mm from the module, the owner's figure is",
    'move the voltage measurement 8 mm down toward the interlock relay': r'VMEAS, rated to 85 C, is [0-9.]+ mm from the heat source K_IL',
    'move a sensing block 10 mm from the interlock relay': r'BREW_A_C, a sensing block, is 10\.0 mm from the heat source K_IL',
    'empty the list of sensing blocks': r'the low-voltage block .* has no heat class',
    'report a part that holds as not held': r'the record reports K_V2 as not held against MODULE',
    'stop reporting a part that does not hold': r'K_V1, rated to 85 C, is 0\.0 mm from the heat source MODULE.*does not report it as not held',
    'accept the voltage measurement as not held from the interlock relay': r'VMEAS must hold 15 mm from K_IL',
    "rate the voltage measurement's part to 125 C and leave it in the 85 C class": r'VMEAS is rated to 125 C',
    'list a part rated to 85 C as outside the class': r'MCU is rated to 85 C, only 15 K over the air',
    'weaken the interlock relay to under a watt': r'K_IL dissipates .* W at most, under the 1\.2 W that makes it a source in A8',
    'drop a harness connector': r'has no connector in the data',
    'weaken the lid keep-out to 1.0 mm': r'assumption token lid_keep',
    'weaken the least slot width to 0.2 mm': r"the maker's slot_min is 0\.2 in the data",
    'weaken the edge distance to 0': r"the maker's edge_min is 0\.0 in the data",
    'widen the reed tolerance to 5 mm': r'assumption token reed_tol',
    'weaken the signed creepage to 8.0 mm': r'the signed creepage is 8\.0 in the data and 10\.0 in its source',
    'weaken the signed mains-to-mains creepage to 3.0 mm': r'the signed mains-to-mains creepage is 3\.0 in the data and 4\.1 in its source',
    'weaken the signed mains-to-mains clearance to 1.0 mm': r'the signed mains-to-mains clearance is 1\.0 in the data and 1\.5 in its source',
    "bring the relay's two contacts 1.5 mm apart": r'mains copper K_IL\.a and K_IL\.b are 1\.50 mm apart',
    "put the relay's two contacts on one net": r'the contact terminal at Y 30\.83 is on K_IL\.a, which is not the net LINE',
    'move a relay leg out of its copper': r'does not stand 1\.00 mm .* inside the copper',
    'narrow a link region': r'the link region F_IL\.o from the fuse to K_IL\.a is 2\.45 mm wide',
    'put the varistor\'s line pad on the fuse\'s line side': r'the varistor.s line pad RV_IL\.l is on the net LINE_IN and not on the net LINE downstream of the fuse',
    'move the varistor 4 mm along X, off the fuse\'s piece of copper but within the distance': r'the varistor.s line pad RV_IL\.l is not on the same piece of copper as the entry fuse.s load-side clip F_IL\.o',
    'shrink the varistor\'s body 1 mm from the module so its stated distance is stale': r'required statement missing \(the entry varistor.s distances from the two heat sources\)',
    'raise the varistor distance limit in the data alone to 50 mm': r'required statement missing \(the varistor.s distance limit from the clip\)',
    'move the varistor 12 mm away from the fuse': r'the varistor.s line pad stands [0-9.]+ mm from the fuse.s load-side clip, the limit for hard against the fuse is 5\.0',
    'take the entry fuse out of the link': r'the link does not begin with the entry fuse F_IL: it passes no fuse',
    'put the entry fuse\'s load-side clip on the net of the pad of tab 2': r'the entry fuse.s load-side clip F_IL\.o is not on the net LINE that the link and the taps are on',
    'tap the logic supply from the line before the fuse': r'a tap leaves the net LINE_IN upstream of the entry fuse',
    'shorten the entry fuse holder to 20 mm': r'the entry fuse holder F_IL is 20\.0 x 9\.0 mm, the 10 A holder is 24\.0 x 9\.0',
    'take the line side of the fuse off the inner-layer list': r'the pad of tab 2 and the fuse.s line-side clip are on the net LINE_IN, which the data does not give as joined by an inner layer',
    'hold the line before the fuse to the basic creepage from LINE1 only': r'the pad of tab 2 is on LINE_IN, which the open contact.s upstream nets',
    'tap the logic supply from the LINE1 net': r'the tap from F_IL\.o is not on the net LINE1',
    'draw a block of a kind that is removed': r'kind 3 is removed but a block of it is drawn',
    'take the circuit block of the kept second current channel away': r'kind 5 is given a place but not all its blocks are drawn',
    'restore tab 4 as drawn and take it off the removed list': r'tab 4 is drawn, and the owner decided on 2026-10-24 to remove it',
    'restore the pad of the removed tab 4': r'tab 4 is drawn in the data and is also listed as removed',
    'lose track of the removed tab 5': r"the connector record's tab 5 is neither drawn nor listed as removed",
    'rename a removed tab': r'removed tab 4 is named ELEMENT in the data and STMHEATER',
    'move the current shunt off the return path: lift its second land off the pour': r"the shunt's second land does not touch the neutral pour",
    'tap the neutral from the pad of tab 3, below the shunt': r'the neutral taps do not leave from the pour above the shunt',
    'raise the least tab pitch to 9.0 mm, so the return landing stands short of it': r'the return landing stands 8\.50 mm from the nearest tab',
    "join a pump's return at the pad of tab 3, on the plug side of the shunt": r'the return of the coffee pump joins at the pad of tab 3, on the plug side of the shunt',
    "join the valves' return at the pad of tab 3, on the plug side of the shunt": r'the return of the valve coils joins at the pad of tab 3, on the plug side of the shunt',
    "leave a pump's return out of the neutral return": r'the returns the data gives are of',
    "end a pump's return on copper of another net": r'the return of the coffee pump does not end on copper of the net NEUTRAL',
    "call the valves' return, which has a surface route, an inner-layer join": r'the return piece VFUSE\.n has a route of [0-9]+ mm on the surface',
    'take the current shunt away': r'the neutral return has no current shunt',
    'give the current shunt no part': r'the neutral return has no current shunt',
    "narrow the shunt's first land to 4 mm": r'the neutral return copper I_SHUNT\.a is 4\.00 mm wide',
    'stop the analogue region at Y 30.1, where the module once stood': r'the region AR_b ends at Y 30\.1 and the rules leave it free to Y 31\.0',
    "draw the analogue region over the interlock relay's keep-out": r'the region AR_b stands 12\.0 mm from the heat source K_IL, the sensing rule',
    'draw a block for the further switched output that the owner removed': r'kind 6 is recorded as not given a place but a block of it is drawn',
    'keep a kind that the regions cannot hold': r'kind 3 is given a place but not all its blocks are drawn',
    'remove the required mark from the supply voltage kind': r"the record's row of kind 1 says required and the data does not mark it so",
    'draw a block outside its region': r'WT1_C lies outside its ana region',
    "make the valve relay's switching voltage 230 V": r'the figure the owner accepted is 230\.0 in the data and 250\.0 in its source',
    "make the valve relay's switching voltage 240 V": r'the figure the owner accepted is 240\.0 in the data and 250\.0 in its source',
    "give the valve relay's open contacts 200 V": r"the valve relay's open contacts give 283 V peak",
    'count a smaller module as adequate': r'the smaller module IRM-10-5 has [0-9.]+ times the budget at 70 C',
    'load the 5 V rail beyond the chosen module': r'the chosen module IRM-20-5 has [0-9.]+ times the 5 V budget at 70 C',
    'take a coil at its nominal resistance': r'K_IL dissipates 0\.98 W at most, under the 1\.0 W that makes it a source in A8',
    'find a fuse that meets the breaking capacity': r'the fuse option x breaks 6000 A, which meets',
    "add a pin to a header, the record's counts unchanged": r'counted figure not stated \(the header pins\)',
    "change the pitch of a header, the record's types unchanged": r'counted figure not stated \(the header types\)',
    "add a joint to the module, the record's joints unchanged": r'counted figure not stated \(the joints\)',
    'take a fuse holder out of the pump strip': r'counted figure not stated \(the joints\)',
    "widen the trace until the two-way valve's lead has no route": r'no route exists for a trace of the net COFVALVE',
    'change the trace width tolerance': r"the maker's track width tolerance is 0\.0 in the data",
    "close the channel between a valve's tab and its relay with a slot": r'no route exists for a trace of the net COFVALVE',
    'bring a mains rectangle within 5 mm of the wall edge': r'mains copper OUT_S is 3\.0 mm from the wall edge',
    "shorten the steam opto-triac's slot so its pins straddle the end": r'opto-coupler OPTO_S: pin-to-pin surface path',
    'break the heater path chain': r'steam path: RC does not touch the copper before it',
    'narrow a heater copper region': r'S2 is 3\.0 mm wide, 15 A needs',
    'widen the coffee triac toward the steam triac, 8.6 mm from it': r'the two triacs stand 8\.6 mm apart on one metal wall',
    'move an opto-triac 9.5 mm from a triac': r'OPTO_C is 9\.5 mm from a triac, the rule is 20',
    "bring an unpopulated confirm place 1.0 mm from the other's mains copper": r'the board with the unpopulated places: mains copper PRES_S\.m and PRES_C\.m are 1\.00 mm apart',
    'bring an unpopulated confirm place within 5.0 mm of the wall edge': r'the board with the unpopulated places: mains copper PRES_S\.m is 3\.0 mm from the wall edge',
    'weaken the opto-triac distance rule to 10 mm': r'assumption token heat_opto',
    "relabel a copper region's net so it touches another": r'mains copper OUT_S and S1s are 0\.00 mm apart',
    'bring the two ends of a varistor 2 mm apart': r'surface path of 2\.0 mm between mains copper MOV_S\.a and MOV_S\.b, the rule is 4\.1',
    'move the body of a part of the wall board within 5 mm of the wall edge, its copper left where it was': r'the body of MOV_S is 3\.0 mm from the wall edge',
    'move the mains pins of an opto-triac within 5 mm of the wall edge': r'a mains lead end of OPTO_S is',
    'bring the two ends of a varistor 1 mm apart': r'mains copper MOV_S\.a and MOV_S\.b are 1\.00 mm apart, the clearance is 1\.5',
    'name the contact of another relay in the link': r"the link passes the contact of 'K_V1'",
    'name no contact in the link': r"the link passes the contact of ''",
    'put the contact of the link between the wrong two regions': r'the contact of K_IL does not stand between its two halves',
    'delete the supply voltage kind, which is required, from the data': r"kind 1 is in the record's table of kinds, and its row says required, and is not in the data",
    'delete every kind that the record marks required, and its mark': r'the data marks no kind required',
    'take the safety-approval ratings out of the relay': r'the interlock relay has no safety-approval \(VDE\) rating',
    'rate the relay at its highest ambient under the overload band': r'the interlock relay.s VDE rating at 125 C of ambient is 10 A, under the 15 A',
    'drop an owner decision from the data': r'the record lists an owner decision D15 that the data does not',
    'retitle an owner decision in the data': r'the owner decision D1 is titled',
    'give an owner decision a home that does not point to it': r'the section "Heat" does not point to the owner decision D1',
    'change the pitch of the weight headers to 2.54 mm, the record unchanged': r'counted figure not stated \(the header types\)',
    'leave out the hole at point 3': r'mounting hole P3 is \(\) in the data',
    'bring tab 9 back to its as-found place, inside the fixing distance of point 3': r'mains copper [0-9.]+ mm from P3, the rule is',
    'call a net that has a surface route an inner-layer join': r'the net COFVALVE has a route of [0-9]+ mm on the surface',
    'take a net that has no surface route off the inner-layer list': r'no route exists for a trace of the net HOTVALVE',
    'leave the 120 kohm mains-sense resistor out of the part types': r'counted figure not stated \(the Extended types\)',
    'make the pump opto-triac a surface-mount part again': r'counted figure not stated \(the split of the Extended types\)',
    'bring a bracket mount within 13.25 mm of mains copper': r'bracket mount 1 is [0-9.]+ mm from mains copper, the rule is',
    'lift the bracket only 3 mm clear of the board': r'the bracket stands [0-9.]+ mm in three dimensions from mains copper',
    'stand the bracket\'s leg 1 mm off the triac faces': r'the tab face of TRI_S does not lie on the bracket.s leg',
    'leave one of the bracket\'s mounting ears out': r'the bracket has 1 mounting ears, the wall board has two',
    'leave one of the bracket\'s mounts out': r'the bracket has 1 mounts, the wall board has two',
    'leave the bracket without mounts': r'the bracket has 0 mounts, the wall board has two',
    'put a bracket mount off its ear': r'bracket mount 2 does not lie on its ear',
    'leave a triac out of the heat figures': r'the heat figures name the triacs \[.TRI_S.\] and the wall board fits the triacs \[.TRI_C., .TRI_S.\]',
    'end the bracket\'s leg short of the steam triac': r'the tab face of TRI_S does not lie on the bracket.s leg',
    'make the wall cut\'s window taller': r'counted figure not stated \(the wall cut\)',
    'lengthen the triac lead ends behind the board': r'counted figure not stated \(the plastic opening in the wall cut paragraph\)',
    'widen the bracket\'s left mounting ear': r'counted figure not stated \(the plastic opening in the wall cut paragraph\)',
    'put a part in the driver\'s way to a wall bolt': r'the driver.s way to wall bolt 1 is crossed by',
    'leave a drawn tab out of the data': r"the connector record.s tab 7 is neither drawn nor listed as removed",
    'leave the hole at point 1 out': r'mounting hole P1 is \(\) in the data',
    'put a part in the driver\'s way to a tab screw': r'the driver.s way to the tab screw of TRI_S is crossed by OPTO_S',
}

# Each perturbation of the record's own text: (what, old, new, intended). Every occurrence of old is replaced (old may be a function of the
# text). The data and the record then disagree, or a statement the script requires is gone, and the check that names it must fire.
TEXT_PERTURBATIONS = (
    ("take the acceptance statement out of D11's owner-intent row", lambda t: re.sub(r'(?m)^(\| The owner accepted the wall cut as preliminary.*)$', lambda m: m.group(1).replace('accepted as preliminary', 'noted'), t), None, r'required statement missing \(the owner acceptance statement in the owner-intent row of D11\)'),
    ("take D11's owner-intent row out of the table", lambda t: re.sub(r'(?m)^\| The owner accepted the wall cut as preliminary.*\n', '', t), None, r'the owner-intent table has 0 rows that start "The owner accepted the wall cut as preliminary", once is required'),
    ("take the acceptance statement out of the D11 row", '**accepted as preliminary by the owner on 2026-10-28', '**noted by the owner on 2026-10-28', r'required statement missing \(the owner acceptance statement in the D11 row\)'),
    ("take the acceptance statement out of the wall cut paragraph", lambda t: re.sub(r'(?m)^(\*\*The wall cut, and the owner.*)$', lambda m: m.group(1).replace('accepted as preliminary', 'noted'), t), None, r'required statement missing \(the owner acceptance statement in the wall cut paragraph\)'),
    ("change the cut figure in D11's owner-intent row", 'the window 30.0 × 80.0 mm = 2400.0 mm² in one place', 'the window 30.0 × 80.0 mm = 1028.1 mm² in one place', r'counted figure not stated \(the wall cut in the owner-intent row of D11\)'),
    ("change the plastic opening figure in D11's owner-intent row", 'the opening in the plastic that admits the unit 89.0 × 45.0 mm = 4005.0 mm². This is not', 'the opening in the plastic that admits the unit 89.0 × 43.0 mm = 3827.0 mm². This is not', r'counted figure not stated \(the plastic opening in the owner-intent row of D11\)'),
    ("change the plastic opening figure in the D11 row", 'and the opening in the plastic that admits the unit is 89.0 × 45.0 mm = 4005.0 mm² (u', 'and the opening in the plastic that admits the unit is 89.0 × 43.0 mm = 3827.0 mm² (u', r'counted figure not stated \(the plastic opening in D11\)'),
    ("change the plastic opening figure in the wall cut paragraph", lambda t: re.sub(r'(?m)^(\*\*The wall cut, and the owner.*)$', lambda m: m.group(1).replace('89.0 × 45.0 mm = 4005.0 mm²', '89.0 × 43.0 mm = 3827.0 mm²'), t), None, r'counted figure not stated \(the plastic opening in the wall cut paragraph\)'),
    ("change the cut figure in the D11 row", '| D11 | The cut is 2400.0 mm² in one place', '| D11 | The cut is 1028.1 mm² in one place', r'counted figure not stated \(the wall cut in D11\)'),
    ("change the cut figure in the wall cut paragraph", lambda t: re.sub(r'(?m)^(\*\*The wall cut, and the owner.*)$', lambda m: m.group(1).replace('2400.0 mm² in one place', '1028.1 mm² in one place'), t), None, r'counted figure not stated \(the wall cut in the wall cut paragraph\)'),
    ('take the confirm polarity statement out of the record', 'on when the triac is open and the element intact', 'something else', r'required statement missing \(the confirm polarity\)'),
    ("take the owner's removal of tabs 4 and 5 out of the owner-intent table", "The main board's tabs 4 and 5, the element lead landings", "The main board's two heater tabs, the element lead landings", r'the owner-intent table of the record has no row that starts'),
    ("change the date of the owner's removal of tabs 4 and 5", '| 2026-10-24 | Tabs 4 and 5 are gone', '| 2026-10-25 | Tabs 4 and 5 are gone', r'the owner-intent row of the removed tabs is dated 2026-10-25'),
    ("take the series diode out of the pump drives' margins", 'series diode', 'plain wire', r"required statement missing \(the pump drives' series diode\)"),
    ("take the no-storage sentence out of the coil's feed requirement", "No level, timer, charge store or latch keeps the coil above the relay's drop-out voltage for longer than the removal interval after proof of life stops.", 'Nothing more is said.', r"required statement missing \(the coil's feed requirement\)"),
    ("take the bring-up sentence out of the coil's feed requirement", 'Bring-up stops the controller in each rest state and records the coil voltage falling below 0.5 V within the interval.', 'Bring-up checks it.', r"required statement missing \(the coil's feed requirement\)"),
    ("delete the whole paragraph of the coil's feed requirement", lambda t: re.sub(r"\*\*The coil's feed\*\*.*?\n\n", '', t, count=1, flags=re.S), None, r"required statement missing \(the coil's feed requirement\)"),
    ("take the interlock relay's 5 V ordering code out of the record", 'HF115F-Q/005-1H', 'HF115F-Q', r"required statement missing \(the interlock relay's 5 V ordering code\)"),
    ("take the statement that the 5 V variant's catalogue number is not recorded out", 'catalogue number and price are not recorded: the design task must match a stocked part', 'catalogue number and price are recorded', r"required statement missing \(the 5 V variant's catalogue number and price\)"),
    ("take the statement that the interlock relay has no sourced thermal margin out", 'no sourced thermal margin at the coil drive it is held at', 'a thermal margin', r"required statement missing \(the interlock relay's thermal margin\)"),
    ('take the premise that the interlock cuts every load out of the record', 'it is not proven until the bring-up continuity check', 'it is proven', r'required statement missing \(the premise that the interlock cuts every load\)'),
    ('take the bring-up continuity check out of the open items', 'there is no continuity', 'there is some continuity', r'required statement missing \(the bring-up continuity check\)'),
    ("take the wall board's orientation out of the record", 'edge-on to the wall, its wall edge flush with the outer face of the bracket\'s leg', 'at some angle to the wall', r"required statement missing \(the wall board's orientation to the wall\)"),
    ("take the owner's measurement of the slack out of the record", 'measures the real slack of each of the four leads with a rule before the board is ordered', 'is told the real slack of each of the four leads', r"required statement missing \(the owner's measurement of the slack\)"),
    ("take the statement that the stiffness is not analysed out of the record", 'no stiffness analysis is made', 'the stiffness is found adequate', r"required statement missing \(the board's stiffness not analysed\)"),
    ("take the screw at point 3 out of the record", "fixed by one screw at each of the machine's four mounting points", "fixed by one screw at each of the machine's three mounting points, point 3 carrying no screw and no hole, the board resting on the plastic boss", r"required statement missing \(the screw and hole at all four points\)"),
    ("take the bracket's depth check out of the record", 'Whether this stays within the cavity is unconfirmed, and is for the owner to check at assembly', 'This stays within the cavity', r"required statement missing \(the bracket's depth left for the owner to check\)"),
    ("change the harness blade's width and thickness in the record", '6.36 mm ±0.1 wide and 0.81 mm thick', '4.8 mm wide and 0.5 mm thick', r"required statement missing \(the harness blade's width and thickness\)"),
    ("reintroduce an unmarked inlet filter in the fuses section", 'The [earlier design: bought inlet filter]\'s suppression is lost with it.', "The bought inlet filter's suppression is lost with it.", r'earlier design named without its marker \(inlet filter\)'),
    ("reintroduce an unmarked mains-entry assembly in the off-board count", 'no appliance inlet and no [earlier design: mains-entry assembly]', 'no appliance inlet and no mains-entry assembly', r'earlier design named without its marker \(mains-entry assembly\)'),
    ("break a marker so a marked citation is unmarked", '[earlier design: bought inlet filter]', '[earlier design bought inlet filter]', r'earlier design named without its marker \(inlet filter\)'),
    ("reintroduce mains-entry assemblies in the plural", 'no appliance inlet and no [earlier design: mains-entry assembly]', 'no appliance inlet and no mains-entry assemblies', r'earlier design named without its marker \(mains-entry assembly\)'),
    ("reintroduce a hyphenated inlet-filter", 'The [earlier design: bought inlet filter]\'s suppression is lost with it.', "The bought inlet-filter's suppression is lost with it.", r'earlier design named without its marker \(inlet filter\)'),
    ("put an inlet filter in a plain fenced block", lambda t: t.replace('## Appendix: the checks', '## Appendix: the checks\n\n```\nthe inlet filter is fitted\n```', 1), None, r'earlier design named without its marker \(inlet filter\)'),
    ("take the two off-board assemblies out of the record", 'There are two: the heater wall board and the steam-path assembly.', 'There are some.', r'required statement missing \(the two off-board assemblies\)'),
    ("take the entry fuse holder's place out of the fuses section", 'The entry fuse holder `F_IL` stands at X 17.0 to 41.0 and Y 34.3 to 43.3', 'The entry fuse holder stands in the floorplan', r"required statement missing \(the entry fuse holder's place in the floorplan\)"),
    ("take the fuse's load side out of the fuses section", 'its load-side clip `F_IL.o` (X 17.0 to 23.0) is on `LINE`', 'its load-side clip is on the net', r'required statement missing \(the entry fuse in series, its load side on LINE\)'),
    ("take the varistor's line pad out of the fuses section", "its line pad `RV_IL.l` is on the piece of copper that holds the fuse's load-side clip", "its line pad is drawn", r"required statement missing \(the varistor's line pad on the fuse's load side\)"),
    ("take the inner-layer join of the fuse's line side out of the fuses section", '**The line side is joined to the pad of tab 2 on an inner layer**', 'The line side is joined to the pad of tab 2', r"required statement missing \(the fuse's line side joined to the pad of tab 2 on an inner layer\)"),
    ("take the entry parts' place out of the reported items", 'The entry fuse holder and the varistor are drawn at tabs 2 and 3.', 'The entry fuse holder and the varistor are placed.', r"required statement missing \(the entry parts' place, reported for the board design tasks\)"),
    ("say again in the fuses section that no place is drawn for the entry parts", 'The entry fuse holder `F_IL` stands at X 17.0 to 41.0 and Y 34.3 to 43.3', 'No place for these parts is drawn in the floorplan. The entry fuse holder `F_IL` stands at X 17.0 to 41.0 and Y 34.3 to 43.3', r"stale statement of the entry parts' place \(no place for the entry parts is drawn\)"),
    ("say again in the reported items that the entry parts have no place", 'The entry fuse holder and the varistor are drawn at tabs 2 and 3.', 'The entry fuse holder and the varistor are drawn at tabs 2 and 3. They have no place drawn in the floorplan.', r"stale statement of the entry parts' place \(the entry parts have no place\)"),
    ("say again that the entry parts are not in the data or the drawing", 'are in the data and the drawing, and the net `LINE_IN`', 'are not in the data or the drawing, and the net `LINE_IN`', r"stale statement of the entry parts' place \(the entry parts are not in the data or the drawing\)"),
    ("say again in the owner table that the entry parts have no place yet", 'the entry fuse holder and the varistor are drawn at tabs 2 and 3 |', 'the entry parts have no place drawn in the floorplan yet |', r"stale statement of the entry parts' place \(no place for the entry parts is drawn\)"),
    ("say again that placing the entry parts is separate work", 'The tabs do not move, and tabs 1 to 3 keep', 'Placing them changes the main board\'s floorplan and is separate work. The tabs do not move, and tabs 1 to 3 keep', r"stale statement of the entry parts' place \(placing the entry parts is separate work\)"),
    ("take the fuse and varistor at tabs 2 and 3 out of the record", "land, at tabs 2 and 3", "land, at the tabs", r'required statement missing \(the entry fuse and varistor at tabs 2 and 3\)'),
    ("put the stale slot-path gap back in the mains-side blocks", 'the widest gap between mains copper along the stack is 10.3 mm and such a trace', 'the widest gap between mains copper along the stack is 11.2 mm and such a trace', r'required statement missing \(the widest gap between mains copper'),
    ("put the stale assumption count back in the record's method section", 'numbered A1 to A33 in § Assumptions', 'numbered A1 to A32 in § Assumptions', r'required statement missing \(the count of assumptions\)'),
    ("put the stale assumption count back in the reported items", 'Assumptions A1 to A33', 'Assumptions A1 to A32', r'required statement missing \(the count of assumptions\)'),
    ("put the taps back on the pour before the fuse", 'the taps**, from `F_IL.o` (net `LINE`)', 'the taps**, from `LK_L`', r'required statement missing \(where the taps leave the link\)'),
    ("take the 10 A holder out of the record", 'so the entry fuse needs a 10 A holder', 'so the entry fuse needs a holder', r"required statement missing \(the entry fuse's 10 A holder\)"),
    ("take the 6 kA shortfall out of the record", 'The fuse is as short of the 6 kA the constraints record assumes', 'The fuse meets the figure', r"required statement missing \(the entry fuse's 6 kA shortfall\)"),
    ("take the owner's check of the varistor out of the record", 'the owner checks that disc on the original board before the part is chosen', 'the part is chosen', r"required statement missing \(the owner's check of the original board's varistor\)"),
    ("take emission suppression out of the main board design's decision", "is decided by the main board's design against the emission criteria", "is decided elsewhere", r'required statement missing \(emission suppression decided by the main board design\)'),
    ('leave a decision pending without its pointer to the list', "the choice is an owner decision pending (§ Owner decisions pending, D8; § Reported for the board design tasks, item 6).", "the choice is an owner decision pending (§ Reported for the board design tasks, item 6).", r'the record mentions an owner decision pending without pointing to the list'),
    ('add a decision pending that the list does not hold', 'points 3 and 4 keep their screws.', 'point 3 is an owner decision pending.', r'the record mentions an owner decision pending without pointing to the list'),
    ('state a decision in the list twice', '**D2. Whether the two', '**D3. Whether the two', r'the owner decision D3 is stated 2 times'),
)

def decision_perturbations(D):
    out = []
    for d in D['owner_decisions']:
        i_ = d['id']
        out.append(('call decision %s made and not pending' % i_, lambda t, i_=i_: re.sub(r'(?m)^(\*\*%s\. .*?\.\*\* )Owner decision pending' % i_, r'\1Decision made', t), None, r'the owner decision %s does not state "Owner decision pending"' % i_))
        out.append(('take the pointer to decision %s out of the record' % i_, lambda t, i_=i_: re.sub(r'Owner decisions pending, %s(?![0-9])' % i_, 'elsewhere, %s' % i_, t), None, r'does not point to the owner decision %s(?![0-9])' % i_))
    return tuple(out)

# Each perturbation of the cost record's text, read by the division record's check: (what, old, new, intended).
COST_PERTURBATIONS = (
    ('change the cost record\'s slot path length', '200 mm of slot path, 12.2 m', '202 mm of slot path, 12.2 m', r'the cost record states the slot path and its metres per square metre as 202'),
    ('change the cost record\'s slot path density', '200 mm of slot path, 12.2 m', '200 mm of slot path, 12.3 m', r'the cost record states the slot path and its metres per square metre as 200 / 12\.3'),
    ('take the slot path out of the cost record', '200 mm of slot path, 12.2 m of slot path per m²', 'some slot path', r'the cost record does not state the slot path'),
    ('change the cost record\'s priced outline width', '4 layers, 131.0 × 125.0 mm', '4 layers, 130.0 × 125.0 mm', r'the cost record states the outline and area of the priced board as 130\.0'),
    ('change the cost record\'s priced area', '(16 375 mm²)', '(16 000 mm²)', r'the cost record states the outline and area of the priced board as 131\.0 / 125\.0 / 16 000'),
    ('change the cost record\'s outline of the configuration priced', 'one 4-layer board of 131.0 × 125.0 mm', 'one 4-layer board of 131.0 × 120.0 mm', r'the cost record states the outline of the configuration priced as 131\.0 / 120\.0'),
    ('change the area in the cost record\'s fabrication price', '6.60 × 16 375 / 10 609', '6.60 × 16 000 / 10 609', r'the cost record states the area in the fabrication price as 16 000'),
    ('change the area in the cost record\'s shipping weight', '0.170 × 16 375 / 10 000', '0.170 × 16 000 / 10 000', r'the cost record states the area in the shipping weight as 16 000'),
    ('change the cost record\'s split of the Extended types', 'main board has 19 unique Extended types, 5 placed by the manufacturer and 14 fitted', 'main board has 19 unique Extended types, 6 placed by the manufacturer and 13 fitted', r'the cost record states the Extended types and their split as 19 / 6 / 13'),
    ('change the cost record\'s count of Extended types the division record counts', 'counts the same 19 Extended types, 5 machine-placed', 'counts the same 18 Extended types, 5 machine-placed', r'the cost record states the Extended types as the division record counts them as 18'),
    ('change the cost record\'s count of types the manufacturer places', 'unique Extended types the manufacturer places is **5**:', 'unique Extended types the manufacturer places is **6**:', r'the cost record states the types the manufacturer places as 6'),
    ('change the cost record\'s joints', 'and 143 joints)', 'and 142 joints)', r'the cost record states the types and joints the division record counts as 19 / 14 / 142'),
    ('change the cost record\'s layers of the priced board', 'one 4-layer board of', 'one 2-layer board of', r'states the layers of the priced board as 2'),
    ('change the cost record\'s layers of the main board section', 'One board, 4 layers,', 'One board, 2 layers,', r'states the layers of the main board section as 2'),
    ('change the cost record\'s number of slots', 'The eight slots are', 'The nine slots are', r'states the number of slots as nine'),
    ('change the cost record\'s area in square centimetres in the large-board charge', '(it is 163.75 cm²)', '(it is 150.00 cm²)', r'states the area in square centimetres in the large-board charge as 150\.00'),
    ('change the cost record\'s area in square centimetres against the large-board limit', 'Neither applies: 163.75 cm² against', 'Neither applies: 150.00 cm² against', r'states the area in square centimetres against the large-board limit as 150\.00'),
    ('change the cost record\'s outline coordinates after the entry parts', '(X 1.0 to 132.0, Y 2.0 to 127.0)', '(X 1.0 to 132.0, Y 2.0 to 120.0)', r'states the outline coordinates and area after the entry parts as 131\.0 / 125\.0 / 1\.0 / 132\.0 / 2\.0 / 120\.0'),
    ('change the cost record\'s slot path density of the wall board', 'at 12.2 and 9.8 m per m²', 'at 12.2 and 10.7 m per m²', r'states the slot path density of the main and the wall board as 12\.2 / 10\.7'),
    ('change the cost record\'s slot path density of the main board among the marks', 'at 12.2 and 9.8 m per m²', 'at 12.3 and 9.8 m per m²', r'states the slot path density of the main and the wall board as 12\.3 / 9\.8'),
    ('change the cost record\'s Extended types the manufacturer places, in words', 'the five Extended types (the microcontroller', 'the four Extended types (the microcontroller', r'states the Extended types the manufacturer places, in words as four'),
    ('change the cost record\'s through-hole Extended types', '14 through-hole Extended types', '13 through-hole Extended types', r'states the through-hole Extended types as 13'),
    ('change the cost record\'s Extended types of the hand-fitted table', 'Hand-fitted parts of the 14 types', 'Hand-fitted parts of the 13 types', r'states the Extended types of the hand-fitted table as 13'),
    ('change the cost record\'s Extended types of the hand-fitted table after the entry parts', 'the 14 types of the hand-fitted table', 'the 13 types of the hand-fitted table', r'states the Extended types of the hand-fitted table after the entry parts as 13'),
    ('change the cost record\'s feeder loading of the types the manufacturer places', '5 types × 3.07 | 15.35', '5 types × 3.07 | 15.00', r'states the feeder loading of the types the manufacturer places as 5 / 3\.07 / 15\.00'),
    ('change the cost record\'s header types', 'and seven header types', 'and six header types', r'states the header types as six'),
    ('change the cost record\'s header types of the 2.54 mm pitch', 'the four 2.54 mm header types', 'the three 2.54 mm header types', r'states the header types of the 2\.54 mm pitch as three'),
    ('change the cost record\'s header part numbers a break-away strip removes', 'removes three purchased part numbers', 'removes two purchased part numbers', r'states the header part numbers a break-away strip removes as two'),
    ('change the cost record\'s header types and ways', 'seven types, 85 ways', 'seven types, 84 ways', r'states the header types and ways as seven / 84'),
    ('change the cost record\'s header ways in the hand-fitted row', '| 85 ways | 85 ways |', '| 85 ways | 84 ways |', r'states the header ways in the hand-fitted row as 85 / 84'),
    ('change the cost record\'s header ways priced', 'estimate: 85 × 0.0204', 'estimate: 84 × 0.0204', r'states the header ways priced as 84'),
    ('change the cost record\'s pins of the pump opto-triac', 'its 12 hand-soldered pins', 'its 10 hand-soldered pins', r'states the pins of the pump opto-triac placed by the manufacturer as 10'),
    ('change the cost record\'s tabs of the main board', '(seven tabs and the return landing)', '(six tabs and the return landing)', r'states the tabs of the main board as six'),
    ('change the cost record\'s joints of the wall board', 'with the 39 joints a board', 'with the 38 joints a board', r'states the joints of the wall board as 38'),
    ('change the cost record\'s Extended types of the wall board', 'The five Extended types for this board', 'The four Extended types for this board', r'states the Extended types of the wall board as four'),
    ('change the cost record\'s wall board body in the configuration', 'a 57.0 × 42.5 mm body', 'a 57.0 × 40.0 mm body', r'states the wall board body and span in the configuration as 57\.0 / 40\.0'),
    ('change the cost record\'s wall board span in its section', '89.0 mm over all and', '90.0 mm over all and', r'states the wall board body and span in its section as 57\.0 / 42\.5 / 90\.0'),
    ('change the cost record\'s wall board area in the configuration', '2 662.5 mm²), 2 layers', '2 600.0 mm²), 2 layers', r'states the wall board body and span in the configuration as 57\.0 / 42\.5 / 89\.0 / 2 600\.0'),
    ('change the cost record\'s wall board area in the shipping weight', '0.170 × 2 662.5 / 10 000', '0.170 × 2 600.0 / 10 000', r'states the wall board area in the shipping weight as 2 600\.0'),
    ('change the cost record\'s main board fabrication price working', '= 25.00 + 10.19 =', '= 25.00 + 10.00 =', r'states the main board fabrication price working as 25\.00 / 6\.60 / 16 375 / 10 609 / 25\.00 / 10\.00'),
    ('change the cost record\'s two-layer fallback fabrication price', '= 4.00 + 8.03 = 12.03 USD', '= 4.00 + 8.03 = 12.00 USD', r'states the two-layer fallback fabrication price working as .* / 12\.00 / '),
    ('change the cost record\'s two-layer fallback saving', '12.03 USD by the same inference, 23.16 USD less', '12.03 USD by the same inference, 23.00 USD less', r'states the two-layer fallback fabrication price working as .* / 23\.00'),
    ('change the cost record\'s main board fabrication price in the first order', 'Fabrication 35.19 + assembly', 'Fabrication 36.00 + assembly', r'states the main board fabrication price in the first order as 36\.00'),
    ('change the cost record\'s main board fabrication price in the table by board', '| Main board, with the mains-entry parts | 35.19 |', '| Main board, with the mains-entry parts | 36.00 |', r'states the main board fabrication price in the table by board as 36\.00'),
    ('change the cost record\'s main board fabrication price after the entry parts', '35.19 USD for fabrication', '36.00 USD for fabrication', r'states the main board fabrication price after the entry parts as 36\.00'),
    ('change the cost record\'s main board fabrication price among the marks', '| 35.19 USD inferred, § Main board', '| 36.00 USD inferred, § Main board', r'states the main board fabrication price among the marks as 36\.00'),
    ('change the cost record\'s saving of the two-layer fallback', '| 23.16 | 35.19 − 12.03;', '| 23.16 | 35.19 − 12.00;', r'states the saving of the two-layer fallback as 23\.16 / 35\.19 / 12\.00'),
    ('change the cost record\'s shunt count', '| none | Extended | 1 | 2 | 2 | 0.5000 |', '| none | Extended | 2 | 2 | 2 | 0.5000 |', r'states the shunt count and build quantity as 2 / 2'),
    ('change the cost record\'s main-board tabs in the build quantities', '| 2 / 4 | 8 main, 6 wall |', '| 2 / 4 | 7 main, 6 wall |', r'states the main-board tabs in the build quantities as 7'),
    ('change the cost record\'s count of the microcontroller', '| C114409 | Extended | 1 | 2 | 2 |', '| C114409 | Extended | 2 | 2 | 2 |', r'states the count and build quantity of C114409 in the parts the manufacturer places as 2 / 2'),
    ('change the cost record\'s build quantity of the pump triac in the numbers read', '| C256462 | 0 / 0 | 4 | 4 |', '| C256462 | 0 / 0 | 3 | 4 |', r'states the build quantity of C256462 in the numbers read as 3'),
    ('change the cost record\'s count of the AC-input optocoupler', '| C108051 | Extended | 1 | 2 | 4 |', '| C108051 | Extended | 1 | 3 | 4 |', r'states the count and build quantity of C108051 in the parts the manufacturer places as 1 / 3'),
    ('change the cost record\'s count of the valve relay owner fits', '| C91370 | Extended | 2 | 2 |', '| C91370 | Extended | 3 | 2 |', r'states the count of C91370 in the parts the owner fits as 3'),
    ('change the cost record\'s count of the fuse holder in the numbers read', '| C3131 | 2 / 0 | 3 | 3 |', '| C3131 | 2 / 0 | 4 | 3 |', r'states the one set\'s count of C3131 in the numbers read as 4'),
    ('change the cost record\'s count of the pump opto-triac owner fits', '| C8965 | Extended | 2 | 2 |', '| C8965 | Extended | 1 | 2 |', r'states the count of C8965 in the parts the owner fits as 1'),
    ('change the cost record\'s count of the interlock relay owner fits', '| C5318991 | Extended | 1 | 2 |', '| C5318991 | Extended | 2 | 2 |', r'states the count of C5318991 in the parts the owner fits as 2'),
    ('change the cost record\'s count of the supply module owner fits', '| C6280121 | Extended | 1 | 1 |', '| C6280121 | Extended | 2 | 1 |', r'states the count of C6280121 in the parts the owner fits as 2'),
    ('change the cost record\'s count of the tab owner fits', '| C20626104 | Extended | 8 | 12 |', '| C20626104 | Extended | 7 | 12 |', r'states the count of C20626104 in the parts the owner fits as 7'),
)

# Each perturbation of a source record's text: (what, source, old, new, intended). The record's data must then fail against it.
SOURCE_PERTURBATIONS = (
    ("change one tab's Y in the connector record", 'pinouts', '| 79.1 mm |', '| 76.0 mm |', r'tab 6 as found is 79\.1 in the data and 76\.0 in its source'),
    ('change the tab thickness in the connector record', 'pinouts', '**0.81 mm thick**', '**1.81 mm thick**', r'the tab thickness is 0\.81 in the data and 1\.81 in its source'),
    ('delete a mounting-point row of the machine record', 'machine', '| 3 | 6.5 mm | 123.5 mm |', '| 3 | 6.5 mm | gone |', r"the machine record's four mounting points did not parse"),
    ('change the signed creepage in the basis to 8.0', 'basis', 'clearance_mm: 3.0\n  creepage_mm: 10.0', 'clearance_mm: 3.0\n  creepage_mm: 8.0', r'the basis creepage row is not the basic figure doubled'),
    ('change the signed mains-to-mains creepage in the basis to 3.1', 'basis', '  creepage_mm: 4.1\n  creepage_ahead_of_fuse_mm: 4.1', '  creepage_mm: 3.1\n  creepage_ahead_of_fuse_mm: 4.1', r'the signed mains-to-mains creepage is 4\.1 in the data and 3\.1 in its source'),
    ('change the signed mains-to-mains clearance in the basis to 1.0', 'basis', '  clearance_mm: 1.5\n  terminal_clearance_mm: 2.0', '  clearance_mm: 1.0\n  terminal_clearance_mm: 2.0', r'the signed mains-to-mains clearance is 1\.5 in the data and 1\.0 in its source'),
    ('remove the reed sentence from the machine record', 'machine', 'with its lower lead at X = 122 mm', 'with its lower lead somewhere', r"the reed's lead positions not found"),
    ('move the cavity width in the machine record', 'machine', '| Inside length along X, wall to wall | 133.5 mm', '| Inside length along X, wall to wall | 130.0 mm', r'the cavity width is 133\.5 in the data and 130\.0 in its source'),
    ("change the maker's edge distance", 'maker', 'More than 0.3 mm', 'More than 0.1 mm', r"the maker's edge_min is 0\.3 in the data and 0\.1 in its source"),
    ("change the maker's recommended annular ring", 'maker', '| PTH annular ring | 0.20 mm recommended, 0.15 mm absolute minimum | Multilayer', '| PTH annular ring | 0.40 mm recommended, 0.15 mm absolute minimum | Multilayer', r"the tab pad's annulus is 0\.32 mm, under the maker's recommended 0\.4 mm"),
    ("change the maker's track width tolerance", 'maker', '| Track width tolerance | ±20 %', '| Track width tolerance | ±30 %', r"the maker's track width tolerance is 0\.2 in the data and 0\.3 in its source"),
    ("change the steam triac's dissipation in the forms record", 'forms', '4.114 + 0.724 = **4.84 W**', '4.114 + 0.724 = **5.84 W**', r"the steam triac's dissipation is 4\.84 in the data and 5\.84 in its source"),
    ("change the triac's junction-to-case resistance in the forms record", 'forms', 'Rth(j-c) 2.1 °C/W (AC)', 'Rth(j-c) 3.1 °C/W (AC)', r"the triac's junction-to-case resistance is 2\.1 in the data and 3\.1 in its source"),
    ('change a load current in the constraints record', 'constraints', '| Coffee thermoblock element | 4.80 A', '| Coffee thermoblock element | 4.00 A', r'the load current coffee is 4\.8 in the data and 4\.0 in its source'),
    ('say in the connector record that LINE1 feeds something else', 'pinouts', 'nothing else on the board connects to `LINE1`', 'a second device connects to `LINE1`', r'the connector record no longer says LINE1 as a pass-through'),
    ("change the valve relay's price in the constraints record", 'constraints', '1.6115 USD (1–9)', '2.6115 USD (1–9)', r"the valve relay's unit price is 1\.6115 in the data and 2\.6115 in its source"),
    ("change the 12 V variant's price that stands for the interlock relay in the forms record", 'forms', '| 3.2119 (1–9) |', '| 4.2119 (1–9) |', r"the unit price of the 12 V variant that stands for the 5 V interlock relay"),
    ("withdraw the owner's acceptance of a 250 V relay", 'constraints', 'is accepted at the 253 V top of the span', 'is not accepted at the 253 V top of the span', r"the owner's dated acceptance of a relay rated at its maximum switching voltage"),
    ('change the accepted maximum switching voltage to 240 V', 'constraints', 'a relay whose contacts are rated 250 V AC as their maximum', 'a relay whose contacts are rated 240 V AC as their maximum', r'the figure the owner accepted is 250\.0 in the data and 240\.0 in its source'),
    ("take the label from the owner's acceptance", 'constraints', '**Owner acceptance, 2026-10-24:**', '**Acceptance, 2026-10-24:**', r"the owner's dated acceptance of a relay rated at its maximum switching voltage"),
    ('take the owner out of the acceptance', 'constraints', "on the owner's statement that the machine's own retained parts", "on a statement that the machine's own retained parts", r"the owner's dated acceptance of a relay rated at its maximum switching voltage"),
    ('change the breaking capacity the chain needs', 'constraints', 'At least the prospective fault current, 6 kA', 'At least the prospective fault current, 10 kA', r'the breaking capacity a fuse must have is 6000\.0 in the data and 10000\.0 in its source'),
)

def selftest(text, D, record_dir):
    """Each perturbation of the data, of the record's own text, of a source record and of an assumption token must be caught by the check it
    targets: a message of that check, found by the pattern the perturbation names. A message about a table of the record does not count, and nor
    does a message of another check that the perturbation happens to break."""
    caught, total = 0, 0
    src0, _ = parse_sources(source_texts(record_dir))

    def verdict(name, bad, want):
        nonlocal caught, total
        total += 1
        hits = [b for b in bad if not b.startswith('table in') and re.search(want, b)]
        caught += 1 if hits else 0
        print('%-62s %s' % (name[:62], ('fires: ' + hits[0][:90]) if hits else 'DID NOT FIRE its check /%s/%s' % (want, (' (other: ' + bad[0][:60] + ')') if bad else ' (no message at all)')))

    for name, which, change, *flags in GUARDS:
        want = INTENDED.get(name)
        if want is None:
            total += 1
            print('%-62s DID NOT FIRE: no intended check is named for it' % name[:62])
            continue
        d = copy.deepcopy(D)
        change(d)
        try:
            bad = check_main(d, text, [], record_dir, src0, route='route' in flags, need='need' in flags, proof='proof' in flags) if which == 'main' else check_wall(d, text, [], record_dir, src0)
        except Exception as e:  # a perturbation that breaks the model outright is caught by no named check
            bad = ['the model failed on it: %s' % type(e).__name__]
        verdict(name, bad, want)
    for name, old, new, want in TEXT_PERTURBATIONS + decision_perturbations(D):
        t2 = old(text) if callable(old) else text.replace(old, new)
        if t2 == text:
            total += 1
            print('%-62s DID NOT FIRE: the text to perturb is not in the record' % name[:62])
            continue
        verdict(name, check_main(D, t2, [], record_dir, src0, route=False) + check_wall(D, t2, [], record_dir, src0), want)
    cost0 = source_texts(record_dir)['cost']
    for name, old, new, want in COST_PERTURBATIONS:
        if old not in cost0:
            total += 1
            print('%-62s DID NOT FIRE: the text to perturb is not in the cost record' % name[:62])
            continue
        verdict(name, check_main(D, text, [], record_dir, src0, route=False, cost=cost0.replace(old, new)), want)
    texts = source_texts(record_dir)
    for name, key, old, new, want in SOURCE_PERTURBATIONS:
        t = dict(texts)
        if old not in t[key]:
            total += 1
            print('%-62s DID NOT FIRE: the text to perturb is not in the source' % name[:62])
            continue
        t[key] = t[key].replace(old, new)
        src, sbad = parse_sources(t)
        verdict(name, sbad + check_sources(D, src), want)
    sec = section(text, 'Assumptions') or ''
    for name, token in sorted(TOKENS.items()):
        m = re.search(r'`%s=(-?[0-9.]+)`' % name, sec)
        if not m:
            continue
        for what, new in (('change the data', None), ('change the record\'s token', float(m.group(1)) + 1.0)):
            if new is None:
                d = copy.deepcopy(D)
                set_in(d, TOKEN_PATHS[name], TOKENS[name](D) + 1.0)
                bad = check_tokens(text, d)
            else:
                bad = check_tokens(text.replace('`%s=%s`' % (name, m.group(1)), '`%s=%g`' % (name, new), 1), D)
            verdict('token %s: %s' % (name, what), bad, r'assumption token %s ' % name)
    print('token perturbations: each of the %d assumption tokens changed in the data and in the record\'s row' % len(TOKENS))
    print('selftest: %d of %d perturbations caught by the check they target' % (caught, total))
    return caught == total

def main():
    cmd = sys.argv[2].lstrip('-') if len(sys.argv) > 2 else ''
    if cmd not in ('main', 'wall', 'tables', 'selftest'):
        raise SystemExit(__doc__)
    path = sys.argv[1]
    text, D = load(path)
    record_dir = os.path.dirname(os.path.abspath(path))
    if cmd == 'selftest':
        sys.exit(0 if selftest(text, D, record_dir) else 1)
    if cmd == 'tables':
        differ = run('main', text, D, record_dir)[1] + run('wall', text, D, record_dir)[1]
        cells = [w for p in PROSES for w in p.want]
        for heading, key, col, value in cells:
            print(('%s | %s | column %d | %s' % (heading, key, col + 1, value)) if key is not None else ('%s | text | %s' % (heading, value)))
        differ = [b for b in differ if b.startswith('table in')]
        print('%d generated cells compared with the record; %d differ%s' % (len(cells), len(differ), (': ' + '; '.join(differ)) if differ else ''))
        sys.exit(1 if differ else 0)
    out, bad = run(cmd, text, D, record_dir)
    bad += expected(text, 'expected-' + cmd, out)
    print('\n'.join(out))
    print('FAIL: ' + '; '.join(bad) if bad else 'all %s checks pass' % ('main board' if cmd == 'main' else 'wall board'))
    sys.exit(1 if bad else 0)

if __name__ == '__main__':
    main()
```

### Expected output

The main board:

```expected-main
sources: separation basis 3.0 / 10.0 mm (signed clearance and creepage), mains to mains 1.5 / 2.0 / 4.1 mm (clearance, terminal clearance and basic creepage), 9 tabs, 4 mounting points, the cavity, the reed, intrusion 1, the maker's limits and 7 load currents read from their records and equal to the data
assumption tokens: 31 of the Assumptions table equal to the data
outline 131.0 x 125.0 mm = 16375 mm2; margins left 1.0 right 1.5 bottom 2.0 top 3.5 mm, least with tolerances 0.8 mm
60 blocks inside the outline, the nearest 0.3 mm from its edge, none overlapping: mains-side 5289 + low-voltage 5244 + reed keep-out 300 = 10833 mm2, 66 % of the outline
heights: 31 parts, least margin 3.9 mm
tabs: 7 pads and the return landing inside the outline, least pitch 8.3 mm, moves +6.9 +7.0 +7.5 -1.9 mm, slack left 3.1 3.0 2.5 8.1 mm, strip X 5.0 to 17.0 Y 19.8 to 110.2
mains copper to the mounting holes, rule 13.25 mm: P1 13.27, P2 71.40, P3 13.28, P4 72.12
reed: lower lead (122.0, 17.5), upper lead (122.0, 37.5), midpoint (122.0, 27.5), keep-out X 117.0 to 127.0 Y 12.5 to 42.5, clear of every block
low voltage to mains copper: least 10.3 mm of 10.0; pockets to mains copper: least straight 4.2 mm of 3.0, 4 pairs under 10.0 mm straight all held by slots, least surface path 12.9 mm of 10.0
opto-coupler pin-to-pin paths round the slots: TIMING 15.8 mm, VMEAS 12.9 mm, P_C 58.3 mm, P_S 58.3 mm
slots: 8 of 200 mm of slot path = 12.2 m per m2 of board, against 80
mains copper of different nets, from different parts: least straight 3.0 mm of 1.5, 15 pairs under the basic creepage of 4.1 mm by straight line, all held by distance or slots, least surface path 7.3 mm of 4.1 (11 of them across the open interlock contact, where the rule is the signed 10.0 mm: least straight 3.0 mm)
entry fuse F_IL: 24.0 x 9.0 mm holder, 10 A, in series between the pad of tab 2 (LINE_IN) and the link (LINE); varistor RV_IL, its line pad on the fuse's load-side piece 0.0 mm from the clip (limit 5.0) and its neutral pad on NEUTRAL, 5.6 mm from the line pad
interlock relay terminals (P2): contact tabs 7.56 mm apart across the body, each on two 1.6 mm holes 5 mm apart along it (X 18 and 23), at Y 23.27 on LINE1 and 30.83 on LINE; coil holes at X 55.5; every leg stands 1.00 mm inside its copper
link LINE to LINE1 through K_IL: 4 copper regions, 4.30 squares = 2.11 mohm, narrowest 5.75 mm (15 A needs 5.71); loss 0.22 W at 10.18 A, 0.25 W at 10.96 A (all loads steady), 0.48 W at 15 A, against a budget of 0.5 W
dropped option, the relay in the top relay place (K_V2): two runs of 92 mm of 7.0 mm pour, 26.4 squares = 12.9 mohm, 1.55 W at 10.96 A against the budget of 0.5 W
taps upstream of the contact: LINE to MODULE, LINE to TIMING, LINE to VMEAS, NEUTRAL to MODULE, NEUTRAL to TIMING, NEUTRAL to VMEAS; the LINE1 net reaches only K_IL and LK_L1 and tab 1
relay K_IL behind it: 10.96 A steady and 11.03 A with the valve coils at their inrush (10.18 A of elements, 0.65 A of pumps), against 20 A: margins 1.82 and 1.81, 1.33 at the 15 A overload band; electrical endurance 30000 operations at 20 A resistive (P2)
relay K_IL heat: coil 0.4 W (0.448 W with the coil 10 % under 62 ohm); contacts 0.5 W at 10.18 A (4.8 mohm, 49 mV; 0.58 W at 10.96 A), so 0.98 W and 1.03 W at the coil's low tolerance; unsourced worst case at 100 mohm: 10.4 W at 10.18 A
neutral return: the landing's pad at Y 46.6 stands 8.5 mm from the nearest tab; the shunt (1.0 mohm, 2 parts side by side, X 5.0 to 12.0, Y 38.8 to 45.8) stands between the pad of tab 3 and the pour, which is 7.0 mm wide against the 5.71 mm that 15 A needs; the neutral carries 11.01 A with every load on (the link's 10.96 A and the module's 0.05 A at the assumed power factor 0.5): shunt loss 0.12 W, 0.23 W at 15 A
relay K_IL safety-approval ratings (P2): 18 A at 105 C, 16 A at 125 C of ambient; margins 1.64 and 1.46 on the 10.96 A the contact carries and 1.20 and 1.07 on the 15 A of the overload band; the body stands at or above the 125 C ambient limit with the coil alone, so the lowest rating is the one to lean on
copper temperature rise, an estimate (IPC-2221 outer layer, planes pulled back): the narrowest link region 5.75 mm (312 mil2) 17.8 K at 10.96 A and 36.4 K at 15 A; the 7.0 mm regions 12.9 K and 26.3 K
owner decisions pending: 12, each stated once in the record's list with its words, pointed to from the section it concerns, and no other mention of a decision pending without the pointer
nets joined by an inner layer, because no surface route exists for a trace to them beside the tab pads, the strips and the point 3 hole: HOTVALVE, LINE_IN; an inner-layer route clear of the holes, the slots and the low-voltage blocks, the copper of other layers not modelled, exists for each: HOTVALVE 36 mm, LINE_IN 23 mm
traces between the separate pieces of one net, shortest route that keeps the basic creepage from other nets (the signed creepage from LINE1) and 10.0 mm from low-voltage blocks, round the slots: COFFPUMP 9 mm, COFVALVE 35 mm, LINE and NEUTRAL 49 mm, STEAMPUMP 10 mm
returns joined by an inner layer, because no surface route exists for a trace to them beside the tab pads and the strips: P_C.N, P_S.N
nearest lead end to the side of intrusion 1 (its position read to 0.5 mm): 16.5 mm
harness reach (farthest corner / nearest point of the opening, limit): CON2 28.9 / 2.0 of 35, SP2 17.5 / 2.0 of 35, KNOB 23.0 / 9.5 of 35, FLOW 20.4 / 9.5 of 35, TEMP_C 24.1 / 9.5 of 35, TEMP_S 32.1 / 10.1 of 60, TEMP_W 30.2 / 12.5 of 60 mm
heat sources, A8 (1 W or more): the module 1.25 W at this board's load; the interlock relay 0.98 W, or 1.03 W with its coil 10 % under nominal, held to A8 by the owner's instruction of 2026-10-24 as well
entry varistor RV_IL, temperature class not read (A33), outside the 85 C class: 5.3 mm from the module and 9.9 mm from the interlock relay (A8 15 mm if it proves to be an 85 C part)
heat from the module / from the interlock relay: controller 15.0 / 63.8 mm of 15; sensing blocks 23.3 / 20.0 mm or more of 20; digital stages 0.0, 10.4, 9.1 mm from the module; the interlock relay from the module 20.0 mm of 15 (held)
mains-side parts rated to 85 C (15 K or less over the 70 C air), from the module / from the interlock relay (rule 15): K_V1 0.0 / 47.2 mm (not held), K_V2 35.9 / 83.1 mm (held), P_C 12.5 / 59.7 mm (not held), P_S 24.5 / 71.7 mm (held), VMEAS 0.0 / 15.0 mm (not held)
outside the class, by their sheets: TIMING 100 C, 30 K over the air, 43.9 mm from the module and 11.2 mm from the interlock relay
why they cannot all hold: a barrier part's pocket stands at the zone boundary, since a trace kept 10 mm from mains copper by distance alone needs 20.3 mm (2 x 10 mm and the trace) to pass and the widest gap between mains copper along the stack is 10.3 mm, and a slotted channel across the stack would divide the taps from one another; the boundary stays 15 mm or more from both sources only over Y 2.3 to 5.7, Y 95.6 to 126.7, 31.1 mm; the 5 parts need 55.2 mm there with 3 mm between them, so at most 3 of them fit there
what-if, with the module at its lowest, the voltage measurement above it and K_V1 between the sources: K_V2, P_C, P_S hold; it breaks 3 rules of this record: slot SL_VMH cuts the copper of F_IL.i; WT1_C, a sensing block, is 18.3 mm from the heat source MODULE, the rule is 20; the region AR_b stands 17.4 mm from the heat source MODULE, the sensing rule is 20
what-if, with the module where it stood, K_V1 and the shared fuse in the gap between the sources and the voltage measurement above the module: K_V2, P_C, P_S hold; it breaks 13 rules of this record: F_IL and VFUSE overlap; RV_IL and VFUSE overlap; slot SL_LN cuts the copper of F_IL.o; slot SL_LN cuts the copper of F_IL.i; slot SL_VN cuts the copper of RV_IL.n; mains copper F_IL.o and VFUSE.n are 0.00 mm apart, the clearance is 1.5; surface path of 0.0 mm between mains copper F_IL.o and VFUSE.n, the rule is 4.1; mains copper F_IL.i and VFUSE.v are 0.00 mm apart, the clearance is 1.5; surface path of 0.0 mm between mains copper F_IL.i and VFUSE.v, the rule is 4.1; mains copper RV_IL.l and VFUSE.n are 0.00 mm apart, the clearance is 1.5; surface path of 0.0 mm between mains copper RV_IL.l and VFUSE.n, the rule is 4.1; no route exists for a trace of the net LINE|NEUTRAL between its copper, round the slots, the other nets and the low-voltage blocks (); the region AR_b stands 19.1 mm from the heat source MODULE, the sensing rule is 20
what-if, with the module lowered 3.3 mm to the lowest the sensing blocks allow and the voltage measurement 11.7 mm from the interlock relay, in the gap the module left: K_V2, P_C, P_S hold; it breaks 2 rules of this record: surface path of 1.8 mm between mains copper F_IL.i and VMEAS.N, the rule is 4.1; the region AR_b stands 19.1 mm from the heat source MODULE, the sensing rule is 20
the most the 85 C parts can hold along the barrier column, counted over every position of the module, every split above or below it and every order with the tab-fed parts in tab order: 3 (K_V2/P_S/P_C); the drawn stack holds 2 (K_V2, P_S); every arrangement that holds 3 stands K_V1 between the two sources
capacity with the spacing the drawing keeps counted (0.3 mm in the header regions, 0.4 mm in the analogue region): header regions 1489.1, analogue region 1189.7
removal step 0: header regions 1650.9 (over 161.8), analogue region 1261.6 (over 71.8); arrangement of the headers: not searched, the area is over
removal step 1 (kind 3 removed): header regions 1436.4 (over 0.0), analogue region 1174.2 (over 0.0); arrangement of the headers: none exists
removal step 2 (kind 4 removed): header regions 1274.2 (over 0.0), analogue region 1066.7 (over 0.0); arrangement of the headers: found
kind 3 alone, with the drawn kinds and no other kind given a place: header regions need 214.5 of 214.9 spare, analogue region 87.4 of 123.1 spare; arrangement of the headers: none exists
kind 4 alone, with the drawn kinds and no other kind given a place: header regions need 162.2 of 214.9 spare, analogue region 107.5 of 123.1 spare; arrangement of the headers: none exists
removing kinds 3 and 4: header regions 1274.2 of 1489.1 and an arrangement of the headers exists; analogue region 1066.7 of 1189.7; it fits
removing kinds 3 and 5: header regions 1355.3 of 1489.1 and an arrangement of the headers exists; analogue region 1120.4 of 1189.7; it fits
removing kinds 4 and 5: header regions 1407.6 of 1489.1 and an arrangement of the headers exists; analogue region 1100.3 of 1189.7; it fits
removing only kind 3: header regions 1436.4 of 1489.1 and an arrangement of the headers does not exist; analogue region 1174.2 of 1189.7; it does not fit
removing only kind 4: header regions 1488.7 of 1489.1 and an arrangement of the headers does not exist; analogue region 1154.0 of 1189.7; it does not fit
removing only kind 5: header regions 1569.8 of 1489.1 and an arrangement of the headers does not exist; analogue region 1207.8 of 1189.7; it does not fit
the region AR_b ends at Y 31.0, where the nearest block of another class stands and the module's body less 20 mm is Y 33.4
least spacing between the blocks drawn in a region: header regions 0.3 mm, analogue region 0.4 mm, against the spacing the capacity counts (0.3 mm and 0.4 mm)
allocation fits at step 2, after the removal of kinds 3, 4; the mains-side stack runs from Y 2.5 to 126.6
what-if, the interlock relay moved 3.0 mm to the right to make room for a sensor 8 mm long between the pad of tab 2 and its contact copper: PT1_C 17.3 mm, BREW_A_C 17.0 mm, WT1_C 17.0 mm from the relay against A8's 20 mm; the analogue region's capacity falls from 1189.7 to 1104.5 mm2, 85.2 mm2 less
what-if, the interlock relay moved 2.0 mm to the right to make room for a sensor 8 mm long between the pad of tab 2 and its contact copper: PT1_C 18.2 mm, BREW_A_C 18.0 mm, WT1_C 18.0 mm from the relay against A8's 20 mm; the analogue region's capacity falls from 1189.7 to 1132.9 mm2, 56.8 mm2 less
what-if, the third arrangement with the region AR_b cut back to Y 30.1, where the module's body less 20 mm stands: the analogue region's capacity falls from 1189.7 to 1154.3 mm2 against the 1066.7 the drawn blocks need, 87.6 mm2 spare, and the blocks of the kept kinds all stand inside it
valve relays HF32FA-G/005-HSL1: 10.0 A contacts against 0.129 A steady and 0.203 A at inrush (margins 78 and 49); 250 V maximum switching voltage against 253 V at the top of the span (1.2 % over, the owner's acceptance); open contacts 1000 V AC = 1414 V peak against 358 V blocked (margin 3.95); coil to contacts 5000 V AC = 7.07 kV against the 4.0 kV target; coil 108 ohm, 46.3 mA and 231 mW at 5 V; 1.6115 USD against 3.2119 USD for the interlock relay type, 3.20 USD less for two
pump drives: the current falls at its zero at 0.20 and 0.08 A/ms (coffee, steam) for a full sine, 29 and 71 times under the triac's 6 A/ms; for the half wave of a series diode, whose peak is twice the rms, 0.29 and 0.12 A/ms, 21 and 50 times
5 V rail: K_IL coil 89.6, Valve relay coils 102.9, Controller 439.0, Gauge drivers 72.0, Weight amplifiers 3.0, Load-cell excitation 28.6, Opto-triac LED drives 60.0, Panel indicators and buzzer 60.0, Flow meter 15.0, Pressure transducers 20.0, In-stream probe converters 4.0, Current sensors 30.0, Voltage measurement output 5.0, Headers, pull-ups and dividers 10.0 = 939.1 mA with the controller at its maximum (726.1 mA at its typical 226 mA); IRM-20-5 2.0 A at 70 C (2.13 times) and 3.6 A at 50 C (3.83 times); IRM-10-5 1.0 A at 70 C (1.06 times) and 2.0 A at 50 C (2.13 times); the chosen IRM-20-5 delivers 4.70 W at this load and dissipates 1.25 W at 79 % efficiency (2.66 W at the 70 C current)
module efficiency at this load: 23 % of its rated 20 W; the sheet gives 79 % at rated load only, so the 1.25 W above is flat-efficiency; a loss that falls in proportion to the load from 5.32 W at rated load to the sheet's 0.1 W at no load gives 1.32 W, 0.08 W more
relay K_IL body, at the sheet's 55 K for the coil's 0.4 W (137.5 K for each watt): 0.98 W would put it at 70 + 135 = 205 C against the 125 C of its ambient range, an upper bound with no allowance for heat leaving by the pins, and not a margin
valve relay own rise: about 61 K at the rated coil voltage (the sheet's plotted line, read off the plot; it does not say for which coil), so 146 C at its 85 C ambient limit against 155 C for insulation class F; 231 mW of coil heat only while a valve is open
fuses: 3 holders of 24 x 9 mm = 216 mm2 each; one shared fuse for both pumps and both valves would carry 0.779 A steady and 0.853 A at the coils' inrush and save 432 mm2; sourced breaking capacities 5 x 20 glass time-lag 35 A, 5.2 x 20 ceramic time-lag 1500 A against the 6000 A required
functions: 17 of the forms record's 17, each with one owner named in the owner table and no other (1 split across boards, each with its reason); connector record: 6 harness headings, each with a connector
division A: fabrication 35.19 (one board 35.19), assembly charges 9.71, labour 3.58, duplicate Extended fees 0.00, link parts 0.00 and joints 0.00, total 48.48 USD
division B: fabrication 37.76 (mains board 8.43, low-voltage board 29.34), assembly charges 19.42, labour 7.16, duplicate Extended fees 3.07, link parts 0.68 and joints 0.66, total 68.75 USD
division C: fabrication 20.43 (mains board 8.43, controller board 8.00 band, front-end board 4.00 band), assembly charges 29.13, labour 10.74, duplicate Extended fees 6.14, link parts 1.37 and joints 1.31, total 69.12 USD
header types by ways and pitch, from the blocks: 4-way 1.95 mm x 1, 5-way 2 mm x 2, 9-way 2 mm x 2, 2-way 2.54 mm x 3, 3-way 2.54 mm x 3, 4-way 2.54 mm x 7, 10-way 2.54 mm x 1; 85 header pins
Extended types of the main board: 19, of which 5 are placed by the manufacturer (5 x 3.07 = 15.35 USD of feeder loading) and 14 are fitted by the owner, headers included (14 x 3.07 = 42.98 USD that the manufacturer does not charge, 7 header types of it = 21.49); hand-fitting the 14 through-hole types and their 143 joints saves 48.91 USD against the manufacturer placing them as well
Economic 25.06 USD against Standard 57.84 USD at the 5 unique Extended types the manufacturer places and no Basic type; Standard adds 1.53 for each Basic, Preferred or Extended type, so the two cross at 26.3 Extended types with none; were all 19 types placed by the manufacturer, Economic would be 68.04 USD and Standard 79.26 USD
wall board hand-fitted: 5 Extended types and 39 joints save 29.28 USD (its own order: 9.71 setup and stencil, 3.58 labour)
```

The heater wall board:

```expected-wall
wall board 57 x 42.5 mm and two mounting ears of 16 x 7.5 mm and 16 x 7.5 mm along its wall edge: 89 mm over all, 2662.5 mm2
every block and mains rectangle lies 1.0 mm or more inside the board edge (least allowed 0.3)
mains copper to the wall edge: least 5.0 mm of 4.1; part bodies least 5.0 mm and mains lead ends of the opto-triacs least 32.2 mm
bracket: board leg u -15 to 72 and standing leg u -11.5 to 68.5 (80 mm, the window), v 0 to 5, standing 5 mm clear of the board and 35 mm high, 5.00 mm in three dimensions from the nearest mains copper (basic creepage 4.1); mounts at (-12.5, 4), (69.5, 4), 13.54 and 13.54 from mains copper (rule 13.25), 3.5 and 3.5 from the board edge; wall bolts at u = -2.5, 59.5, 9.0 mm in from the leg's ends at the least and 18.7 mm from the nearest tab screw at the least; tab faces on the leg at TRI_C at u = 40.8 and TRI_S at u = 16.2, a 6 mm driver reaching each tab screw and each wall bolt from the board side with nothing in its way; wall cut 2400.0 mm2 (80 x 30 mm) for the leg, in one place
plastic opening that admits the unit, without tilting: u -16 to 73 (89 mm) by z -10 to 35 (45 mm) from the board's component face, 4005.0 mm2; the window that exposes the steel under the leg is 2400.0 mm2
mains copper of different nets, from different parts: least straight 5.0 mm of 1.5, 0 pairs under the basic creepage of 4.1 mm by straight line
pockets: least straight 15.0 mm of 3.0, 0 pairs under 10.0 mm straight all held by slots, least surface path 12.1 mm of 10.0; the header is 10.0 mm from mains copper
opto-coupler pin-to-pin paths round the slots: OPTO_S 12.1 mm, OPTO_C 12.1 mm
slots: 2 of 26 mm of slot path = 9.8 m per m2 of board, against 80
copper of the heater path: S1s 5.7 x 7.0 mm 0.81 squares 0.40 mohm, S2 6.3 x 7.0 mm 0.90 squares 0.44 mohm, S3 6.3 x 7.0 mm 0.90 squares 0.44 mohm, S1c 5.7 x 7.0 mm 0.81 squares 0.40 mohm, RC 7.0 x 7.0 mm 1.00 squares 0.49 mohm, RET 7.0 x 7.0 mm 1.00 squares 0.49 mohm
copper dissipation: steam path 24 mW at 5.38 A and 189 mW at 15 A, coffee path 19 mW at 4.80 A and 189 mW at 15 A, common return 102 mW at 10.18 A and 221 mW at 15 A
longest run RC 7.0 mm = 12 % of the 57 mm width; copper run totals steam 26.0 mm, coffee 26.0 mm
heat: triacs 14.2 mm apart (the assumed least 10); opto-coupler parts 20.0 mm or more from them, rule 20
triac heat: the two tab faces share one metal wall: 4.25 W and 4.84 W, 9.09 W together; junction over case 8.9 K and 10.2 K at 2.1 K/W; the case may stand at 116.1 and 114.8 C of the 125 C limit, so at 70 C air the wall and the tab interface may rise 44.8 K over the air for the 4.84 W triac: 9.3 K/W from the tab face to the air if it heats the wall alone, 4.9 K/W if both do
hand-soldered joints of the board: 39 (gate_resistor 8, header 3, opto_triac 12, terminal 6, triac 6, varistor 4)
wall board fabrication: own board 4.00 USD in the band; as a section 1.66 USD (inferred), 2.34 less, or -0.34 more than the maker's application price of 2.00 USD
the board with the 2 unpopulated confirm places: 57 x 52.5 mm = 2992.5 mm2, +23.5 % against the drawn board; 42 joints fitted, and 12 more if the places are fitted; every check passes
```
