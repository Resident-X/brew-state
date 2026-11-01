# Layout plan of the method proof design

**NOT FOR MANUFACTURE.** `method-proof` is a throwaway four-layer board, 40 mm by 30 mm, from (100, 100) to (140, 130) in board coordinates, made only to prove `docs/board-design-method.md`. It is marked not for manufacture and is never ordered. Its figures are read from `constraints.md`, its synthetic constraints record, and the manufacturer's stated limits, `docs/board-manufacturer-jlcpcb.md`. It carries no mains.

The stack is F.Cu, In1.Cu, In2.Cu and B.Cu, 1 oz each. In1.Cu and In2.Cu are each a solid `GND` plane over the whole board; F.Cu and B.Cu carry the tracks and a `GND` pour each. Every surface-mount part and every connector is on F.Cu. The four test points, TP1 to TP4, are dedicated pads on B.Cu, so the tall parts, the connectors and the link headers, are on the side no probe lands on.

The layer-by-layer plan of the nets: `+5V_IN`, `+5V`, `/+3V3_REG` and `+3V3` are tracks on F.Cu, with a short stub to a test point's pad through a via where it changes layer; `GND` is the planes and the pours, each ground pad reaching In1.Cu and In2.Cu through its own vias; `/LED_K`, `/LED_A` and `/PA1_HDR` are short tracks on F.Cu. Net classes: `Power` holds `/+5V_IN` and `+5V`, `Supply` holds `/+3V3_REG` and `+3V3`, `Ground` holds `GND`, and every other net is in `Default`. The critical classes are `Power`, `Supply` and `Ground`.

## Floorplan

| Region | Bounds | What it holds | Parts |
|---|---|---|---|
| mains | none: the board carries no mains | nothing | none |
| low voltage | (100, 100)–(119, 130) | J1, the 5 V supply input, with its link JP1 and test point TP1; U1, the 3.3 V regulator, with its capacitors C1 and C2, its link JP2 and test point TP2; J2, the output header, with its filter capacitors C5 and C4; a mounting hole at the left edge; a fiducial near the bottom edge | J1, JP1, TP1, U1, C1, C2, JP2, TP2, J2, C5, C4, H1, FID1 |
| analog sensing | none: the schematic carries no sensing front end | nothing | none |
| digital | (119, 100)–(140, 130) | U2, the controller, with its supply capacitor C3 and the rail's test point TP3; D1, the status LED, with its resistor R1 and test point TP4, which U2's PA0 drives; J3, the PA1 header; two mounting holes at the right edge; two fiducials, one at the top edge and one below the controller | U2, C3, TP3, R1, D1, TP4, J3, H2, H3, FID2, FID3 |

| Connector | Edge | Position |
|---|---|---|
| J1 | left | (103, 104) |
| J2 | left | (103, 114) |
| J3 | right | (137, 112) |
| JP1 | none: a link position, reached with a shunt or a resistor's leads and a soldering iron | (110, 104) |
| JP2 | none: a link position, reached with a shunt or a resistor's leads and a soldering iron | (113, 122) |

## Plan

| Item | Applies | How the layout meets it, or why it does not apply |
|---|---|---|
| FLOOR-1 | yes | Each part's courtyard within the bounds of the region the floorplan lists it in: the supply input, the regulator, its capacitors, the links and the output header with its filter capacitors in low voltage (x below 119 mm); U2, its capacitor, the LED stage and the PA1 header in digital (x from 119 mm). |
| FLOOR-2 | no | No sensing front end feeding a converter in the schematic: U2's converter is unused and its analog input pins carry no net. |
| FLOOR-3 | yes | J1 at the left edge, U1 beside it at about x 115 mm, 13 mm from J1 and about 10 mm from U2, U2 at about x 129 mm; between them only C1, C2, JP1, JP2 and the `+3V3` track, with the In1.Cu and In2.Cu `GND` planes under all three. There is no analog supply to take from the digital one. |
| FLOOR-4 | yes | One rule area named for the low voltage region and one for the digital region, each at its bounds on every copper layer, and the rules `Low voltage region parts` and `Digital region parts` of `design-rules.md`, each letting in the parts the floorplan lists in its region and no other footprint. The mains and analog sensing regions are `none` and have no rule area. |
| POWER-1 | yes | Custom rules in `design-rules.md`: `Power track width` on `Power`, 0.381 mm × 0.5 A = 0.19 mm, written 0.2 mm; `Supply track width` on `Supply`, 0.381 mm × 0.1 A = 0.038 mm, written 0.2 mm; `Ground track width` on `Ground`, which returns the supply input's 0.5 A, written 0.2 mm; each current read from `constraints.md`. |
| POWER-2 | yes | `/+5V_IN` a straight track from J1's pin 1 to JP1's pin 1 and TP1; `+5V` from JP1's pin 2 through C1's pad to U1's pin 3, and on to J2's pin 1 and to R1, at a width above the 0.2 mm minimum wherever there is room; `/+3V3_REG` from U1's pin 2 through C2's pad to JP2's pin 1 and TP2; `+3V3` from JP2's pin 2 to C3's pad and U2's pin 9, to U2's pin 4 and J2's pin 2. No detour and no neck narrower than the rest of a track. |
| POWER-3 | yes | The power paths run on F.Cu end to end and change layer only to the planes: the `GND` return of the 0.5 A supply input leaves J1's pin 2 for the planes through three vias, 0.5 A over 200 mA being three, and the `GND` of the 0.1 A rail through one; the test points' stubs on `/+5V_IN`, `+5V`, `/+3V3_REG` and `+3V3` carry no load current. |
| POWER-4 | no | No part in the schematic has an exposed pad meant to carry heat into the board: U1 is a SOT-23, U2 a TSSOP-20. |
| POWER-5 | no | No part in the schematic switches a load through a lead or pad that carries heat into the board. |
| GROUND-1 | yes | `GND` the planes on In1.Cu and In2.Cu over the whole board, and a pour on F.Cu and on B.Cu, joined to the planes through vias at each ground pad and along the board; every ground pad joined to the pours through thermal reliefs, as MFG-5 holds. |
| GROUND-2 | yes | Every track on F.Cu runs over the unbroken In1.Cu plane and every track on B.Cu over the unbroken In2.Cu plane; nothing is routed on In1.Cu or In2.Cu, and the only openings in the planes are single clearance rings round vias and through-hole pins, none merged into a slot: the J1, J2, J3, JP1 and JP2 pins are 2.5 mm or more apart. |
| GROUND-3 | no | No sensing front end feeding a converter in the schematic. |
| GROUND-4 | no | No part in the schematic has separate analog and digital ground pins: U2 has one ground pin, VSS, pin 7. |
| DECOUPLE-1 | yes | C3 (10 µF) at U2's supply pin 9 within 3 mm, with `+3V3` reaching C3's pad first and then the pin; C1 (47 µF) at U1's input pin 3, `+5V` reaching C1's pad first and then the pin; C2 (150 µF) at U1's output pin 2, `/+3V3_REG` reaching C2's pad first and then the pin; each capacitor the only one on its pin and no via between a capacitor and its pin. |
| DECOUPLE-2 | yes | Each capacitor's ground pad joined straight to the F.Cu `GND` pour and through two vias of its own beside the pad to the planes; C3's ground side at U2's pin 7 (VSS), and C1's and C2's ground sides at U1's pin 1. |
| DECOUPLE-3 | no | No switching converter in the schematic: U1 is a linear regulator. |
| DECOUPLE-4 | no | No switching converter in the schematic. |
| DECOUPLE-5 | no | No snubber in the schematic. |
| SENSE-1 | no | No current-sense resistor in the schematic. |
| SENSE-2 | no | No filter at a converter's input and no reference capacitor in the schematic. |
| SENSE-3 | no | No operational or instrumentation amplifier in the schematic. |
| SENSE-4 | no | No sensing front end in the schematic. |
| SENSE-5 | no | No sensing front end in the schematic. |
| CLOCK-1 | no | No crystal or ceramic resonator in the schematic: U2 runs from its internal oscillator. |
| CLOCK-2 | no | No crystal or ceramic resonator in the schematic. |
| CLOCK-3 | no | No crystal or ceramic resonator in the schematic. |
| CLOCK-4 | no | No crystal or ceramic resonator in the schematic. |
| MAINS-1 | no | No mains-referenced net in the schematic, so the board declares `MAINS` `none`. |
| MAINS-2 | no | No mains-referenced net in the schematic. |
| MAINS-3 | no | No part in the schematic has pins on both a mains-referenced net and a net outside the `Mains` class. |
| MAINS-4 | no | No part in the schematic has pins on both a mains-referenced net and a net outside the `Mains` class. |
| MAINS-5 | no | No part in the schematic has pins on both a mains-referenced net and a net outside the `Mains` class; `BARRIER_COPPER_MM2` is still set, to 0, as the rules section requires of every board. |
| CONN-1 | no | No transient-voltage or electrostatic-discharge suppressor in the schematic. |
| CONN-2 | no | No leadless package in the schematic: U1 is a SOT-23 and U2 a TSSOP-20, both leaded. |
| CONN-3 | yes | J1 and J2, the cable connectors, at the left edge, J3 at the right edge, each facing off the board, their cables leaving away from U2: J1 and J2 about 25 mm from U2, J3 the PA1 header beside it. |
| CONN-4 | yes | H1 at the left edge between J2 and the board's corner, near (103.5, 126), H2 at the right edge near (137, 102.5) and H3 at the right edge near (137, 127.5): three holes in a triangle that holds the board without rocking, the left edge carrying J1 and J2 and the right edge carrying J3, each with copper cleared from it by the copper-to-hole minimum, none within a part's courtyard and none beside a leadless package, the board having none. |
| TEST-1 | yes | TP1 to TP4 each a dedicated 1.0 mm pad on B.Cu, at least 2.5 mm apart centre to centre and at least 2.0 mm from any part taller than 2.6 mm; none a surface-mount part's land. |
| TEST-2 | yes | All four test points on B.Cu, and every part taller than 6.4 mm, J1, J2, J3, JP1 and JP2, on F.Cu. |
| TEST-3 | no | No resistor used to measure current in the schematic: R1 sets an LED's current and nothing reads its voltage. |
| TEST-4 | no | No resistor used to measure current in the schematic. |
| TEST-5 | yes | `TEST_COURTYARD_MM` 1 in `design-rules.md`; every test pad, TP1 to TP4, stands at least 1.0 mm from the courtyard of every part on either side, TP3 at (120.4, 110.4) the closest, from U2's. |
| MFG-1 | yes | The board-wide minimums of Board Setup set to JLCPCB's stated limits for four layers at 1 oz, each with its row in `design-rules.md`, naming this item and the capability page and its date. |
| MFG-2 | no | No part in the schematic has an exposed pad on its underside. |
| MFG-3 | no | No part in the schematic has an exposed pad on its underside. |
| MFG-4 | yes | `PASTE_OVER_VIA_MM2` set to 0 in `design-rules.md`; no via is placed under a paste opening, the vias at the capacitors' ground pads standing beside the pads. |
| MFG-5 | yes | The `Ground pad reliefs` rule of `design-rules.md` on class `Ground`, with no exempt pad, the board having no exposed pad. |
| MFG-6 | yes | The pre-order check's `MFG-6` figure, the board's minimum clearance, with every pour stopping at least that far from copper of its own net that it does not touch. |
| MFG-10 | yes | The pre-order check's `side_fiducials` rule, which reads no project text variable; the front side, the only side with assembled surface-mount parts (TP1 to TP4 on the back are left out of the position file), carries three fiducials, FID1 at (112, 125), FID2 at (126, 104) and FID3 at (127, 120), each a 1 mm bare-copper pad with a 2 mm mask opening, at least 4 mm from the board edge and clear of every courtyard, pad and track, standing in an L across the board. |
| EMI-1 | yes | Each supply track on F.Cu runs over the In1.Cu `GND` plane, and each `GND` return reaches the planes beside the part it serves, so supply and ground enclose little area. |
| EMI-2 | yes | U2 is the board's only controller. No net of this board switches faster than 50 kHz: PA0 holds an LED steady and PA1 is an input, so there is no noisy net, and no track runs along the board edge. |
| EMI-3 | yes | C5, from `+5V` to ground, and C4, from `+3V3` to ground, are the filter capacitors of the lines that leave the board at J2 pins 1 and 2: each sits at its connector pin, within 3 mm of it, with its supply pad on the pin's track and its ground side joined to the F.Cu `GND` pour and through two vias to the planes by a connection no longer than three times its width. C1 and C3 are the regulator's and the controller's supply capacitors, placed by DECOUPLE-1 at U1 and U2. |
| EMI-4 | no | No ferrite bead in the schematic. |
| EMI-5 | yes | R1, the resistor in series with U2's PA0 through D1, with D1 beside U2's pins 11 and 12 at the bottom right of the part, both within 6 mm of pin 11, `/LED_K` running from pin 11 to D1's cathode straight and short. |
| WORK-1 | yes | Connected parts sit together in the order the circuit runs: J1, JP1, U1 with C1 and C2, JP2, then U2 with C3, R1 and D1 and J3 at the far edge; each part turned so its pads face the pads it joins, and no connection crossing another on F.Cu. |
| WORK-2 | yes | `WORK_DETOUR_RATIO` set to 1.3 in `design-rules.md`; each net routed direct, at 45 degrees and along the axes, branching at its pads. |
| WORK-3 | yes | Each route leaves its pad, turns as few times as it needs and arrives; no loop, no double-back and no needless change of layer. |
| WORK-4 | yes | The `Corners` rule of `design-rules.md`, `track_angle` 135, and `WORK_PAD_ANGLE_DEG` set to 90. |
| WORK-5 | yes | The `Jogs` rule of `design-rules.md`, `track_segment_length` 1 mm. |
| WORK-6 | yes | KiCad's `track_dangling` check, reported unaided; no track ends free. |
| WORK-7 | yes | KiCad's `via_dangling` check, reported unaided; every via joins copper on two layers or more. |
| WORK-8 | yes | `WORK_NECK_MM` set to 1 in `design-rules.md`; each track at least its class's width except where it enters a pad. |
| WORK-9 | yes | `WORK_ANGLE_TOLERANCE_DEG` set to 0.1 in `design-rules.md`; every track along the board's edges or at 45 degrees to them. |
| WORK-10 | yes | U2's leads, 1.5 mm long and 0.4 mm wide, are the board's pads more than twice as long as wide; every track enters one along its long axis from its end. `WORK_PAD_ENTRY_RATIO` set to 2 in `design-rules.md`. |

## Board's own items

| Item | Applies when | Asks | Passes | Fails, as the views show it | Judged on | Kind | Severity | Source | How the layout meets it |
|---|---|---|---|---|---|---|---|---|---|
| none | | | | | | | | | |

## Placement

### Candidate 1

- **Commit**: dde774a022b491d99912a08fcd8bf60d17c9786e
- **Renders**: from the repository's root, `git worktree add --detach <work folder>/method-proof-candidate-1 dde774a022b491d99912a08fcd8bf60d17c9786e`, then `(cd <work folder>/method-proof-candidate-1/hardware/proof/method-proof && task hw:placement -- --board method-proof.kicad_pcb --project method-proof.kicad_pro --out <work folder>/method-proof-placement-1)`, then `git worktree remove <work folder>/method-proof-candidate-1`
- **Measures**:

```
LENGTH | total | 139.8227 mm
CROSSINGS | total | 8
OUTSIDE | total | 0
```

| Item | Verdict | Rests on | Why |
|---|---|---|---|
| FLOOR-1 | pass | `placement-r1c1.png` and `placement-r2c1.png`, whole board; the OUTSIDE total, 0 | Every part lies within its region: the measures list no part outside, the supply input, regulator, links and output header at x below 119 mm and the controller, its capacitor, the LED stage and the PA1 header from 119 mm. |
| FLOOR-3 | pass | `placement-r1c1.png` and `placement-r2c1.png`, whole board; the LENGTH total, 139.8227 mm | J1 at the left edge, U1 about 13 mm from it and U2 about 10 mm from U1, with only C1, C2, JP1 and JP2 between; the supply crosses the board in one run. |
| POWER-2 | pass | `placement-r1c1.png` and `placement-r2c1.png`, whole board; the NET lines of /+5V_IN and +5V | The 0.5 A path J1, JP1, C1, U1 and C5 is the shortest the part positions allow; the long +5V run to R1 carries the LED current only, 5 mA. |
| DECOUPLE-1 | pass | `placement-r1c1.png` and `placement-r2c1.png`, the places of C1, C2 and C3 | C3 sits beside U2's pins 7 and 9 on their side, C1 beside U1's input pin and C2 beside its output pin, each the only capacitor on its pin and its connection a short straight line. |
| DECOUPLE-3 | not applicable | the plan table's row for DECOUPLE-3 | No switching converter in the schematic: U1 is a linear regulator. |
| DECOUPLE-4 | not applicable | the plan table's row for DECOUPLE-4 | No switching converter in the schematic. |
| DECOUPLE-5 | not applicable | the plan table's row for DECOUPLE-5 | No snubber in the schematic. |
| SENSE-2 | not applicable | the plan table's row for SENSE-2 | No filter at a converter input and no reference capacitor in the schematic. |
| SENSE-3 | not applicable | the plan table's row for SENSE-3 | No operational or instrumentation amplifier in the schematic. |
| SENSE-5 | not applicable | the plan table's row for SENSE-5 | No sensing front end in the schematic. |
| CLOCK-1 | not applicable | the plan table's row for CLOCK-1 | No crystal or ceramic resonator in the schematic. |
| CLOCK-3 | not applicable | the plan table's row for CLOCK-3 | No crystal or ceramic resonator in the schematic. |
| MAINS-2 | not applicable | the plan table's row for MAINS-2 | No mains-referenced net in the schematic. |
| CONN-1 | not applicable | the plan table's row for CONN-1 | No transient-voltage or electrostatic-discharge suppressor in the schematic. |
| CONN-2 | not applicable | the plan table's row for CONN-2 | No leadless package in the schematic: U1 is a SOT-23 and U2 a TSSOP-20. |
| CONN-3 | pass | `placement-r1c1.png` and `placement-r2c1.png`, the left and right edges | J1 and J2 at the left edge and J3 at the right edge, each facing off the board; U2 stands 20 mm or more from J1 and J2 and no connector faces across it. |
| CONN-4 | pass | `placement-r1c1.png` and `placement-r2c1.png`, the left and right edges | H1 at the left edge below J2, H2 and H3 at the right edge above and below J3: three holes in a triangle, each clear of every courtyard and none beside a leadless package, the board having none. |
| TEST-1 | fail | `placement-r1c1.png`, TP1 beside J1 and JP1, x 106 to 109 mm, y 105 to 109 mm | TP1 stands about 0.5 mm from J1's body and 0.7 mm from JP1's, both taller than 2.6 mm, short of the 2.0 mm the item asks; TP2 stands 1.7 mm from JP2. |
| TEST-2 | pass | `placement-r1c1.png` and `placement-r2c1.png`, the test points in blue and the connectors in white | All four test points on B.Cu and every part taller than 6.4 mm, J1, J2, J3, JP1 and JP2, on F.Cu. |
| EMI-3 | pass | `placement-r2c1.png`, J2, C4 and C5 at the left edge | C5 and C4 each beside the J2 pin of their rail, within 3 mm of it. |
| EMI-4 | not applicable | the plan table's row for EMI-4 | No ferrite bead in the schematic. |
| EMI-5 | pass | `placement-r1c1.png` and `placement-r2c1.png`, U2's pins 11 and 12 and the LED stage under them | R1 and D1 under U2's pin 11 within about 6 mm of it, /LED_K a short straight connection to D1's cathode. |
| WORK-1 | pass | `placement-r1c1.png` and `placement-r2c1.png`, whole board; the CROSSINGS total, 8, and the LENGTH total, 139.8227 mm | Connected parts stand together in the order the circuit runs and each is turned so its pads face the pads it joins; the 8 crossings are the GND and +5V trees across the regulator cluster, and no arrangement tried, candidates 1 to 5, kept them below 8. |

### Candidate 2

- **Commit**: 976a86b760c2d64dc36f0eaaa36f7b3dd9917ac9
- **Renders**: from the repository's root, `git worktree add --detach <work folder>/method-proof-candidate-2 976a86b760c2d64dc36f0eaaa36f7b3dd9917ac9`, then `(cd <work folder>/method-proof-candidate-2/hardware/proof/method-proof && task hw:placement -- --board method-proof.kicad_pcb --project method-proof.kicad_pro --out <work folder>/method-proof-placement-2)`, then `git worktree remove <work folder>/method-proof-candidate-2`
- **Measures**:

```
LENGTH | total | 141.1616 mm
CROSSINGS | total | 8
OUTSIDE | total | 0
```

| Item | Verdict | Rests on | Why |
|---|---|---|---|
| FLOOR-1 | pass | `placement-r1c1.png` and `placement-r2c1.png`, whole board; the OUTSIDE total, 0 | Every part lies within its region: the measures list no part outside, the supply input, regulator, links and output header at x below 119 mm and the controller, its capacitor, the LED stage and the PA1 header from 119 mm. |
| FLOOR-3 | pass | `placement-r1c1.png` and `placement-r2c1.png`, whole board; the LENGTH total, 141.1616 mm | J1 at the left edge, U1 about 13 mm from it and U2 about 10 mm from U1, with only C1, C2, JP1 and JP2 between; the supply crosses the board in one run. |
| POWER-2 | pass | `placement-r1c1.png` and `placement-r2c1.png`, whole board; the NET lines of /+5V_IN and +5V | The 0.5 A path J1, JP1, C1, U1 and C5 is the shortest the part positions allow; the long +5V run to R1 carries the LED current only, 5 mA. |
| DECOUPLE-1 | pass | `placement-r1c1.png` and `placement-r2c1.png`, the places of C1, C2 and C3 | C3 sits beside U2's pins 7 and 9 on their side, C1 beside U1's input pin and C2 beside its output pin, each the only capacitor on its pin and its connection a short straight line. |
| DECOUPLE-3 | not applicable | the plan table's row for DECOUPLE-3 | No switching converter in the schematic: U1 is a linear regulator. |
| DECOUPLE-4 | not applicable | the plan table's row for DECOUPLE-4 | No switching converter in the schematic. |
| DECOUPLE-5 | not applicable | the plan table's row for DECOUPLE-5 | No snubber in the schematic. |
| SENSE-2 | not applicable | the plan table's row for SENSE-2 | No filter at a converter input and no reference capacitor in the schematic. |
| SENSE-3 | not applicable | the plan table's row for SENSE-3 | No operational or instrumentation amplifier in the schematic. |
| SENSE-5 | not applicable | the plan table's row for SENSE-5 | No sensing front end in the schematic. |
| CLOCK-1 | not applicable | the plan table's row for CLOCK-1 | No crystal or ceramic resonator in the schematic. |
| CLOCK-3 | not applicable | the plan table's row for CLOCK-3 | No crystal or ceramic resonator in the schematic. |
| MAINS-2 | not applicable | the plan table's row for MAINS-2 | No mains-referenced net in the schematic. |
| CONN-1 | not applicable | the plan table's row for CONN-1 | No transient-voltage or electrostatic-discharge suppressor in the schematic. |
| CONN-2 | not applicable | the plan table's row for CONN-2 | No leadless package in the schematic: U1 is a SOT-23 and U2 a TSSOP-20. |
| CONN-3 | pass | `placement-r1c1.png` and `placement-r2c1.png`, the left and right edges | J1 and J2 at the left edge and J3 at the right edge, each facing off the board; U2 stands 20 mm or more from J1 and J2 and no connector faces across it. |
| CONN-4 | pass | `placement-r1c1.png` and `placement-r2c1.png`, the left and right edges | H1 at the left edge below J2, H2 and H3 at the right edge above and below J3: three holes in a triangle, each clear of every courtyard and none beside a leadless package, the board having none. |
| TEST-1 | fail | `placement-r1c1.png`, TP1 beside J1 and JP1, x 105 to 109 mm, y 105 to 110 mm | TP1 stands about 0.5 mm from J1's body and 0.7 mm from JP1's, both taller than 2.6 mm, short of the 2.0 mm the item asks. |
| TEST-2 | pass | `placement-r1c1.png` and `placement-r2c1.png`, the test points in blue and the connectors in white | All four test points on B.Cu and every part taller than 6.4 mm, J1, J2, J3, JP1 and JP2, on F.Cu. |
| EMI-3 | pass | `placement-r2c1.png`, J2, C4 and C5 at the left edge | C5 and C4 each beside the J2 pin of their rail, within 3 mm of it. |
| EMI-4 | not applicable | the plan table's row for EMI-4 | No ferrite bead in the schematic. |
| EMI-5 | pass | `placement-r1c1.png` and `placement-r2c1.png`, U2's pins 11 and 12 and the LED stage under them | R1 and D1 under U2's pin 11 within about 6 mm of it, /LED_K a short straight connection to D1's cathode. |
| WORK-1 | pass | `placement-r1c1.png` and `placement-r2c1.png`, whole board; the CROSSINGS total, 8, and the LENGTH total, 141.1616 mm | Connected parts stand together in the order the circuit runs and each is turned so its pads face the pads it joins; the 8 crossings are the GND and +5V trees across the regulator cluster, and no arrangement tried, candidates 1 to 5, kept them below 8. |

### Candidate 3

- **Commit**: 828d8c0d2863b81a39fc374ed65cf20224a0ce01
- **Renders**: from the repository's root, `git worktree add --detach <work folder>/method-proof-candidate-3 828d8c0d2863b81a39fc374ed65cf20224a0ce01`, then `(cd <work folder>/method-proof-candidate-3/hardware/proof/method-proof && task hw:placement -- --board method-proof.kicad_pcb --project method-proof.kicad_pro --out <work folder>/method-proof-placement-3)`, then `git worktree remove <work folder>/method-proof-candidate-3`
- **Measures**:

```
LENGTH | total | 147.5881 mm
CROSSINGS | total | 10
OUTSIDE | total | 0
```

| Item | Verdict | Rests on | Why |
|---|---|---|---|
| FLOOR-1 | pass | `placement-r1c1.png` and `placement-r2c1.png`, whole board; the OUTSIDE total, 0 | Every part lies within its region: the measures list no part outside, the supply input, regulator, links and output header at x below 119 mm and the controller, its capacitor, the LED stage and the PA1 header from 119 mm. |
| FLOOR-3 | pass | `placement-r1c1.png` and `placement-r2c1.png`, whole board; the LENGTH total, 147.5881 mm | J1 at the left edge, U1 about 13 mm from it and U2 about 10 mm from U1, with only C1, C2, JP1 and JP2 between; the supply crosses the board in one run. |
| POWER-2 | pass | `placement-r1c1.png` and `placement-r2c1.png`, whole board; the NET lines of /+5V_IN and +5V | The 0.5 A path J1, JP1, C1, U1 and C5 is the shortest the part positions allow; the long +5V run to R1 carries the LED current only, 5 mA. |
| DECOUPLE-1 | pass | `placement-r1c1.png` and `placement-r2c1.png`, the places of C1, C2 and C3 | C3 sits beside U2's pins 7 and 9 on their side, C1 beside U1's input pin and C2 beside its output pin, each the only capacitor on its pin and its connection a short straight line. |
| DECOUPLE-3 | not applicable | the plan table's row for DECOUPLE-3 | No switching converter in the schematic: U1 is a linear regulator. |
| DECOUPLE-4 | not applicable | the plan table's row for DECOUPLE-4 | No switching converter in the schematic. |
| DECOUPLE-5 | not applicable | the plan table's row for DECOUPLE-5 | No snubber in the schematic. |
| SENSE-2 | not applicable | the plan table's row for SENSE-2 | No filter at a converter input and no reference capacitor in the schematic. |
| SENSE-3 | not applicable | the plan table's row for SENSE-3 | No operational or instrumentation amplifier in the schematic. |
| SENSE-5 | not applicable | the plan table's row for SENSE-5 | No sensing front end in the schematic. |
| CLOCK-1 | not applicable | the plan table's row for CLOCK-1 | No crystal or ceramic resonator in the schematic. |
| CLOCK-3 | not applicable | the plan table's row for CLOCK-3 | No crystal or ceramic resonator in the schematic. |
| MAINS-2 | not applicable | the plan table's row for MAINS-2 | No mains-referenced net in the schematic. |
| CONN-1 | not applicable | the plan table's row for CONN-1 | No transient-voltage or electrostatic-discharge suppressor in the schematic. |
| CONN-2 | not applicable | the plan table's row for CONN-2 | No leadless package in the schematic: U1 is a SOT-23 and U2 a TSSOP-20. |
| CONN-3 | pass | `placement-r1c1.png` and `placement-r2c1.png`, the left and right edges | J1 and J2 at the left edge and J3 at the right edge, each facing off the board; U2 stands 20 mm or more from J1 and J2 and no connector faces across it. |
| CONN-4 | pass | `placement-r1c1.png` and `placement-r2c1.png`, the left and right edges | H1 at the left edge below J2, H2 and H3 at the right edge above and below J3: three holes in a triangle, each clear of every courtyard and none beside a leadless package, the board having none. |
| TEST-1 | fail | `placement-r1c1.png`, TP1 beside J1 and JP1, x 106 to 109 mm, y 105 to 109 mm | TP1 stands about 0.5 mm from J1's body and 0.7 mm from JP1's, both taller than 2.6 mm, short of the 2.0 mm the item asks. |
| TEST-2 | pass | `placement-r1c1.png` and `placement-r2c1.png`, the test points in blue and the connectors in white | All four test points on B.Cu and every part taller than 6.4 mm, J1, J2, J3, JP1 and JP2, on F.Cu. |
| EMI-3 | pass | `placement-r2c1.png`, J2, C4 and C5 at the left edge | C5 and C4 each beside the J2 pin of their rail, within 3 mm of it. |
| EMI-4 | not applicable | the plan table's row for EMI-4 | No ferrite bead in the schematic. |
| EMI-5 | pass | `placement-r1c1.png` and `placement-r2c1.png`, U2's pins 11 and 12 and the LED stage under them | R1 and D1 under U2's pin 11 within about 6 mm of it, /LED_K a short straight connection to D1's cathode. |
| WORK-1 | fail | `placement-r1c1.png` and `placement-r2c1.png`, U2 and the LED stage on the second; the CROSSINGS total, 10, and the LENGTH total, 147.5881 mm | Moving U2 and the LED stage 4 mm down lengthens the +5V run to R1 and the GND tree and adds two crossings over candidate 1 (10 against 8), where keeping them up kept the connections short. |

### Candidate 4

- **Commit**: 9b09982c95c8ebc2936f5484b9b5593c6f1be3f6
- **Renders**: from the repository's root, `git worktree add --detach <work folder>/method-proof-candidate-4 9b09982c95c8ebc2936f5484b9b5593c6f1be3f6`, then `(cd <work folder>/method-proof-candidate-4/hardware/proof/method-proof && task hw:placement -- --board method-proof.kicad_pcb --project method-proof.kicad_pro --out <work folder>/method-proof-placement-4)`, then `git worktree remove <work folder>/method-proof-candidate-4`
- **Measures**:

```
LENGTH | total | 143.1642 mm
CROSSINGS | total | 8
OUTSIDE | total | 0
```

| Item | Verdict | Rests on | Why |
|---|---|---|---|
| FLOOR-1 | pass | `placement-r1c1.png` and `placement-r2c1.png`, whole board; the OUTSIDE total, 0 | Every part lies within its region: the measures list no part outside, the supply input, regulator, links and output header at x below 119 mm and the controller, its capacitor, the LED stage and the PA1 header from 119 mm. |
| FLOOR-3 | pass | `placement-r1c1.png` and `placement-r2c1.png`, whole board; the LENGTH total, 143.1642 mm | J1 at the left edge, U1 about 13 mm from it and U2 about 10 mm from U1, with only C1, C2, JP1 and JP2 between; the supply crosses the board in one run. |
| POWER-2 | pass | `placement-r1c1.png` and `placement-r2c1.png`, whole board; the NET lines of /+5V_IN and +5V | The 0.5 A path J1, JP1, C1, U1 and C5 is the shortest the part positions allow; the long +5V run to R1 carries the LED current only, 5 mA. |
| DECOUPLE-1 | pass | `placement-r1c1.png` and `placement-r2c1.png`, the places of C1, C2 and C3 | C3 sits beside U2's pins 7 and 9 on their side, C1 beside U1's input pin and C2 beside its output pin, each the only capacitor on its pin and its connection a short straight line. |
| DECOUPLE-3 | not applicable | the plan table's row for DECOUPLE-3 | No switching converter in the schematic: U1 is a linear regulator. |
| DECOUPLE-4 | not applicable | the plan table's row for DECOUPLE-4 | No switching converter in the schematic. |
| DECOUPLE-5 | not applicable | the plan table's row for DECOUPLE-5 | No snubber in the schematic. |
| SENSE-2 | not applicable | the plan table's row for SENSE-2 | No filter at a converter input and no reference capacitor in the schematic. |
| SENSE-3 | not applicable | the plan table's row for SENSE-3 | No operational or instrumentation amplifier in the schematic. |
| SENSE-5 | not applicable | the plan table's row for SENSE-5 | No sensing front end in the schematic. |
| CLOCK-1 | not applicable | the plan table's row for CLOCK-1 | No crystal or ceramic resonator in the schematic. |
| CLOCK-3 | not applicable | the plan table's row for CLOCK-3 | No crystal or ceramic resonator in the schematic. |
| MAINS-2 | not applicable | the plan table's row for MAINS-2 | No mains-referenced net in the schematic. |
| CONN-1 | not applicable | the plan table's row for CONN-1 | No transient-voltage or electrostatic-discharge suppressor in the schematic. |
| CONN-2 | not applicable | the plan table's row for CONN-2 | No leadless package in the schematic: U1 is a SOT-23 and U2 a TSSOP-20. |
| CONN-3 | pass | `placement-r1c1.png` and `placement-r2c1.png`, the left and right edges | J1 and J2 at the left edge and J3 at the right edge, each facing off the board; U2 stands 20 mm or more from J1 and J2 and no connector faces across it. |
| CONN-4 | pass | `placement-r1c1.png` and `placement-r2c1.png`, the left and right edges | H1 at the left edge below J2, H2 and H3 at the right edge above and below J3: three holes in a triangle, each clear of every courtyard and none beside a leadless package, the board having none. |
| TEST-1 | fail | `placement-r1c1.png`, TP1 beside J1 and JP1, x 106 to 109 mm, y 105 to 109 mm | TP1 stands about 0.5 mm from J1's body and 0.7 mm from JP1's, both taller than 2.6 mm, short of the 2.0 mm the item asks; TP2 stands 1.7 mm from JP2. |
| TEST-2 | pass | `placement-r1c1.png` and `placement-r2c1.png`, the test points in blue and the connectors in white | All four test points on B.Cu and every part taller than 6.4 mm, J1, J2, J3, JP1 and JP2, on F.Cu. |
| EMI-3 | pass | `placement-r2c1.png`, J2, C4 and C5 at the left edge | C5 and C4 each beside the J2 pin of their rail, within 3 mm of it. |
| EMI-4 | not applicable | the plan table's row for EMI-4 | No ferrite bead in the schematic. |
| EMI-5 | pass | `placement-r1c1.png` and `placement-r2c1.png`, U2's pins 11 and 12 and the LED stage under them | R1 and D1 under U2's pin 11 within about 6 mm of it, /LED_K a short straight connection to D1's cathode. |
| WORK-1 | pass | `placement-r1c1.png` and `placement-r2c1.png`, whole board; the CROSSINGS total, 8, and the LENGTH total, 143.1642 mm | Connected parts stand together in the order the circuit runs and each is turned so its pads face the pads it joins; the 8 crossings are the GND and +5V trees across the regulator cluster, and no arrangement tried, candidates 1 to 5, kept them below 8. |

### Candidate 5

- **Commit**: dfe9ea3127f015d268407244c3f34e6e175a71e6
- **Renders**: from the repository's root, `git worktree add --detach <work folder>/method-proof-candidate-5 dfe9ea3127f015d268407244c3f34e6e175a71e6`, then `(cd <work folder>/method-proof-candidate-5/hardware/proof/method-proof && task hw:placement -- --board method-proof.kicad_pcb --project method-proof.kicad_pro --out <work folder>/method-proof-placement-5)`, then `git worktree remove <work folder>/method-proof-candidate-5`
- **Measures**:

```
LENGTH | total | 141.0259 mm
CROSSINGS | total | 9
OUTSIDE | total | 0
```

| Item | Verdict | Rests on | Why |
|---|---|---|---|
| FLOOR-1 | pass | `placement-r1c1.png` and `placement-r2c1.png`, whole board; the OUTSIDE total, 0 | Every part lies within its region: the measures list no part outside, the supply input, regulator, links and output header at x below 119 mm and the controller, its capacitor, the LED stage and the PA1 header from 119 mm. |
| FLOOR-3 | pass | `placement-r1c1.png` and `placement-r2c1.png`, whole board; the LENGTH total, 141.0259 mm | J1 at the left edge, U1 about 13 mm from it and U2 about 10 mm from U1, with only C1, C2, JP1 and JP2 between; the supply crosses the board in one run. |
| POWER-2 | pass | `placement-r1c1.png` and `placement-r2c1.png`, whole board; the NET lines of /+5V_IN and +5V | The 0.5 A path J1, JP1, C1, U1 and C5 is the shortest the part positions allow; the long +5V run to R1 carries the LED current only, 5 mA. |
| DECOUPLE-1 | pass | `placement-r1c1.png` and `placement-r2c1.png`, the places of C1, C2 and C3 | C3 sits beside U2's pins 7 and 9 on their side, C1 beside U1's input pin and C2 beside its output pin, each the only capacitor on its pin and its connection a short straight line. |
| DECOUPLE-3 | not applicable | the plan table's row for DECOUPLE-3 | No switching converter in the schematic: U1 is a linear regulator. |
| DECOUPLE-4 | not applicable | the plan table's row for DECOUPLE-4 | No switching converter in the schematic. |
| DECOUPLE-5 | not applicable | the plan table's row for DECOUPLE-5 | No snubber in the schematic. |
| SENSE-2 | not applicable | the plan table's row for SENSE-2 | No filter at a converter input and no reference capacitor in the schematic. |
| SENSE-3 | not applicable | the plan table's row for SENSE-3 | No operational or instrumentation amplifier in the schematic. |
| SENSE-5 | not applicable | the plan table's row for SENSE-5 | No sensing front end in the schematic. |
| CLOCK-1 | not applicable | the plan table's row for CLOCK-1 | No crystal or ceramic resonator in the schematic. |
| CLOCK-3 | not applicable | the plan table's row for CLOCK-3 | No crystal or ceramic resonator in the schematic. |
| MAINS-2 | not applicable | the plan table's row for MAINS-2 | No mains-referenced net in the schematic. |
| CONN-1 | not applicable | the plan table's row for CONN-1 | No transient-voltage or electrostatic-discharge suppressor in the schematic. |
| CONN-2 | not applicable | the plan table's row for CONN-2 | No leadless package in the schematic: U1 is a SOT-23 and U2 a TSSOP-20. |
| CONN-3 | pass | `placement-r1c1.png` and `placement-r2c1.png`, the left and right edges | J1 and J2 at the left edge and J3 at the right edge, each facing off the board; U2 stands 20 mm or more from J1 and J2 and no connector faces across it. |
| CONN-4 | pass | `placement-r1c1.png` and `placement-r2c1.png`, the left and right edges | H1 at the left edge below J2, H2 and H3 at the right edge above and below J3: three holes in a triangle, each clear of every courtyard and none beside a leadless package, the board having none. |
| TEST-1 | pass | `placement-r1c1.png` and `placement-r2c1.png`, TP1 to TP4 in blue | Every test point is a dedicated pad on the back, at least 2.5 mm from the next, at least 1.0 mm from every part body and 2.0 mm or more from J1, JP1 and JP2, the taller parts: TP1 2.0 mm from J1 and 2.1 mm from JP1, TP2 2.6 mm from JP2. |
| TEST-2 | pass | `placement-r1c1.png` and `placement-r2c1.png`, the test points in blue and the connectors in white | All four test points on B.Cu and every part taller than 6.4 mm, J1, J2, J3, JP1 and JP2, on F.Cu. |
| EMI-3 | pass | `placement-r2c1.png`, J2, C4 and C5 at the left edge | C5 and C4 each beside the J2 pin of their rail, within 3 mm of it. |
| EMI-4 | not applicable | the plan table's row for EMI-4 | No ferrite bead in the schematic. |
| EMI-5 | pass | `placement-r1c1.png` and `placement-r2c1.png`, U2's pins 11 and 12 and the LED stage under them | R1 and D1 under U2's pin 11 within about 6 mm of it, /LED_K a short straight connection to D1's cathode. |
| WORK-1 | pass | `placement-r1c1.png` and `placement-r2c1.png`, whole board; the CROSSINGS total, 9, and the LENGTH total, 141.0259 mm | Connected parts stand together in the order the circuit runs and each is turned so its pads face the pads it joins; the 9 crossings are the GND and +5V trees across the regulator cluster, and no arrangement tried, candidates 1 to 5, kept them below 8. |

**Chosen**: 5. Candidates 1 to 4 each fail `TEST-1`: TP1 stands about 0.5 mm from J1's body and 0.7 mm from JP1's, both taller than 2.6 mm, where candidate 5, with JP1 moved 3 mm right, passes it (TP1 2.0 mm from J1 and 2.1 mm from JP1, TP2 2.6 mm from JP2). Candidate 5's LENGTH total, 141.0259 mm, is 1.2 mm above candidate 1's 139.8227 mm and 6.6 mm below candidate 3's 147.5881 mm, and its CROSSINGS total, 9, is one above the 8 of candidates 1, 2 and 4, a one-crossing cost no candidate that passes `TEST-1` avoided. `kicad-cli pcb drc` run on each candidate's commit reports `courtyards_overlap` for candidates 1 and 3 (U2 with C3, JP1 with C1, R1 with D1) and for candidate 2 (U2 with C3, R1 with D1), and none for candidates 4 and 5. Candidate 3 also fails `WORK-1`, with 10 crossings and the longest connections. Candidate 5 is chosen.

## Critical routing

### Pass 1

**Board judged**: 3a72c6d003548d13b4f553962d43fc4c378df588

**Views**: `task hw:views -- --board method-proof.kicad_pcb --project method-proof.kicad_pro --class Power --class Supply --class Ground --out /Users/david/.claude/method-proof-work/w4/method-proof-views` and `task hw:placement -- --board method-proof.kicad_pcb --project method-proof.kicad_pro --out /Users/david/.claude/method-proof-work/w4/method-proof-placement`, the placement view rendered because FLOOR-3, POWER-2, DECOUPLE-1 and WORK-1 name it in their Judged on.

| Item | Kind | Severity | Verdict | Rests on | Why |
|---|---|---|---|---|---|
| FLOOR-3 | judgement | quality | pass | `classes-r1c1.png` and `classes-r2c1.png`, `net-GND-r1c1.png` and `net-GND-r2c1.png`, `net-+5V-r1c1.png` and `net-+5V-r2c1.png`, `net-+3V3-r1c1.png` and `net-+3V3-r2c1.png`, `assembly-top-r1c1.png` and `assembly-top-r2c1.png` and `assembly-bottom-r1c1.png` and `assembly-bottom-r2c1.png`, `placement-r1c1.png` and `placement-r2c1.png`; whole board | J1 and J2 at the left edge, U1 beside them and U2 about 9 mm to the right, the digital region next to the low-voltage one; the ground is four zones on F.Cu, In1.Cu, In2.Cu and B.Cu spanning all three, and the supply reaches U1 first and U2 through the +3V3 strips; the board has no analog region. |
| POWER-1 | rule | function | pass | `design-rules.md` rows Power track width, Supply track width, Ground track width and Net class Power, Supply and Ground; `facts.txt` | Power 0.2 mm is at least 0.381 mm times 0.5 A, 0.19 mm; Supply 0.2 mm is at least 0.381 mm times 0.1 A; Ground 0.2 mm is at least 0.381 mm times 0.5 A, each read from `constraints.md`; the class tracks are 0.5, 0.3 and 0.3 mm wide in `facts.txt`, and KiCad's rule check reports no track_width violation on the locked copper. The pre-order check is not run here, since the board is not fully routed: the item's measured half is judged by the pre-order check that step 8 of routing runs after the router. |
| POWER-2 | judgement | function | pass | `net-+5V-r1c1.png` and `net-+5V-r2c1.png`, `net-_+5V_IN-r1c1.png` and `net-_+5V_IN-r2c1.png`, `net-+3V3-r1c1.png` and `net-+3V3-r2c1.png`, `net-_+3V3_REG-r1c1.png` and `net-_+3V3_REG-r2c1.png`, `facts.txt`, `classes-r1c1.png` and `classes-r2c1.png`, `placement-r1c1.png` and `placement-r2c1.png` | The +5V and +3V3 paths are wide F.Cu pours and 0.5 and 0.3 mm tracks between parts that stand together, with no detour and no neck; no power net in `facts.txt` has a width range reaching the 0.09 mm minimum. |
| POWER-3 | judgement | function | pass | `net-GND-r1c1.png` and `net-GND-r2c1.png`, `net-+5V-r1c1.png` and `net-+5V-r2c1.png`, `net-_+5V_IN-r1c1.png` and `net-_+5V_IN-r2c1.png`, `facts.txt` | The 0.5 A loop reaches the ground planes through three vias at J1 pin 2 and three at J2 pin 3, 0.5 A over 200 mA rounded up; the power nets change layer only to reach test points and the 5 mA LED branch, and 0.1 A of the logic rail needs one via. |
| POWER-4 | judgement | function | not applicable | `layout-plan.md` plan table row for POWER-4 | The schematic has no part with an exposed pad: U1 is a SOT-23 and U2 a TSSOP-20. |
| POWER-5 | judgement | function | not applicable | `layout-plan.md` plan table row for POWER-5 | The schematic has no part that switches a load. |
| GROUND-1 | judgement | function | pass | `net-GND-r1c1.png` and `net-GND-r2c1.png`, `layer-F.Cu-r1c1.png` and `layer-F.Cu-r2c1.png`, `layer-In1.Cu-r1c1.png` and `layer-In1.Cu-r2c1.png`, `layer-In2.Cu-r1c1.png` and `layer-In2.Cu-r2c1.png`, `layer-B.Cu-r1c1.png` and `layer-B.Cu-r2c1.png`, `facts.txt` | `facts.txt` gives GND four zones, on F.Cu, B.Cu, In1.Cu and In2.Cu; the planes cover the board unbroken across both regions, joined to the outer pours through 11 vias. |
| GROUND-2 | judgement | function | pass | `layer-F.Cu-r1c1.png` and `layer-F.Cu-r2c1.png`, `layer-In1.Cu-r1c1.png` and `layer-In1.Cu-r2c1.png`, `layer-In2.Cu-r1c1.png` and `layer-In2.Cu-r2c1.png`, `layer-B.Cu-r1c1.png` and `layer-B.Cu-r2c1.png`, `net-GND-r1c1.png` and `net-GND-r2c1.png`, `net-+5V-r1c1.png` and `net-+5V-r2c1.png`, `net-+3V3-r1c1.png` and `net-+3V3-r2c1.png` | No track runs on In1.Cu or In2.Cu; the F.Cu tracks lie over In1.Cu and the B.Cu tracks over In2.Cu, each a solid plane under them with only the 0.6 mm via clearances cut in it, none merging into a slot. |
| GROUND-3 | judgement | function | not applicable | `layout-plan.md` plan table row for GROUND-3 | The schematic has no sensing front end or converter. |
| GROUND-4 | judgement | function | not applicable | `layout-plan.md` plan table row for GROUND-4 | The schematic has no part with separate analog and digital ground pins: U1 has one ground pin and U2 one, VSS. |
| DECOUPLE-1 | judgement | function | pass | `crop-U1.png`, `crop-U2.png`, `placement-r1c1.png` and `placement-r2c1.png` | The crop captions name C1, C2 and C5 for U1 and C3 and C4 for U2; each stands beside its part, the supply reaching the capacitor and on to the pin by a pour or a short track with no via between them. |
| DECOUPLE-2 | judgement | function | pass | `crop-U1.png`, `crop-U2.png`, `net-GND-r1c1.png` and `net-GND-r2c1.png` | Each capacitor's ground pad lies in the F.Cu ground pour with a ground via within 1.2 mm and the planes beneath, so the loop encloses little area. |
| DECOUPLE-3 | judgement | function | not applicable | `layout-plan.md` plan table row for DECOUPLE-3 | The schematic has no switching converter. |
| DECOUPLE-4 | judgement | function | not applicable | `layout-plan.md` plan table row for DECOUPLE-4 | The schematic has no switching converter. |
| DECOUPLE-5 | judgement | function | not applicable | `layout-plan.md` plan table row for DECOUPLE-5 | The schematic has no snubber. |
| MFG-4 | rule | quality | pass | `design-rules.md` row Paste over a via | The row holds 0 mm², the item's own figure; every via of the critical nets lies in copper clear of a pad and its paste opening. The pre-order check is not run here, since the board is not fully routed: the item's measured half is judged by the pre-order check that step 8 of routing runs after the router. |
| MFG-5 | rule | quality | pass | `design-rules.md` row Ground pad reliefs | The row holds the rule in the item's form on the Ground class; KiCad's rule check reports no starved_thermal violation on the locked copper. The pre-order check is not run here, since the board is not fully routed: the item's measured half is judged by the pre-order check that step 8 of routing runs after the router. |
| MFG-6 | rule | quality | pass | `design-rules.md` row Pour gap | The row holds 0.09 mm, the minimum clearance MFG-1 holds to the manufacturer's limit. The pre-order check is not run here, since the board is not fully routed: the item's measured half is judged by the pre-order check that step 8 of routing runs after the router. |
| EMI-1 | judgement | quality | pass | `classes-r1c1.png` and `classes-r2c1.png`, `net-GND-r1c1.png` and `net-GND-r2c1.png`, `net-+5V-r1c1.png` and `net-+5V-r2c1.png`, `net-+3V3-r1c1.png` and `net-+3V3-r2c1.png` | Every supply track and pour has the In1.Cu or In2.Cu ground plane directly beneath it, from J1 to U2. |
| EMI-2 | judgement | quality | pass | `layer-F.Cu-r1c1.png` and `layer-F.Cu-r2c1.png`, `layer-In1.Cu-r1c1.png` and `layer-In1.Cu-r2c1.png`, `layer-In2.Cu-r1c1.png` and `layer-In2.Cu-r2c1.png`, `layer-B.Cu-r1c1.png` and `layer-B.Cu-r2c1.png`, `net-GND-r1c1.png` and `net-GND-r2c1.png`, `net-+5V-r1c1.png` and `net-+5V-r2c1.png`, `net-+3V3-r1c1.png` and `net-+3V3-r2c1.png`, `net-_+5V_IN-r1c1.png` and `net-_+5V_IN-r2c1.png`, `net-_+3V3_REG-r1c1.png` and `net-_+3V3_REG-r2c1.png` | No critical net runs along the board edge: the nearest track, the +5V_IN run at y 103.5 mm, is 3.5 mm inside it. |
| WORK-1 | judgement | quality | pass | `assembly-top-r1c1.png` and `assembly-top-r2c1.png` and `assembly-bottom-r1c1.png` and `assembly-bottom-r2c1.png`, `layer-F.Cu-r1c1.png` and `layer-F.Cu-r2c1.png`, `layer-In1.Cu-r1c1.png` and `layer-In1.Cu-r2c1.png`, `layer-In2.Cu-r1c1.png` and `layer-In2.Cu-r2c1.png`, `layer-B.Cu-r1c1.png` and `layer-B.Cu-r2c1.png`, `net-GND-r1c1.png` and `net-GND-r2c1.png`, `net-+5V-r1c1.png` and `net-+5V-r2c1.png`, `placement-r1c1.png` and `placement-r2c1.png`; the LENGTH total, 143.6795 mm, and the CROSSINGS total, 11 | The critical nets join parts that stand together, and the placement view's 11 crossings are of the ground, +5V, +3V3 and /+3V3_REG trees, which the planes and pours carry with no copper crossing. |
| WORK-2 | rule | quality | pass | `design-rules.md` row Route length | The row holds 1.3 from `WORK_DETOUR_RATIO`, the item's own figure. The pre-order check is not run here, since the board is not fully routed: the item's measured half is judged by the pre-order check that step 8 of routing runs after the router. |
| WORK-3 | judgement | quality | pass | `layer-F.Cu-r1c1.png` and `layer-F.Cu-r2c1.png`, `layer-In1.Cu-r1c1.png` and `layer-In1.Cu-r2c1.png`, `layer-In2.Cu-r1c1.png` and `layer-In2.Cu-r2c1.png`, `layer-B.Cu-r1c1.png` and `layer-B.Cu-r2c1.png`, `net-+5V-r1c1.png` and `net-+5V-r2c1.png`, `net-+3V3-r1c1.png` and `net-+3V3-r2c1.png`, `net-_+5V_IN-r1c1.png` and `net-_+5V_IN-r2c1.png`, `net-_+3V3_REG-r1c1.png` and `net-_+3V3_REG-r2c1.png`, `classes-r1c1.png` and `classes-r2c1.png` | The critical tracks run straight with 45-degree corners and no doubling back; they change layer only to reach a test point on the back, and the +5V branch to R1 crosses to the back once to pass the +3V3 strips and returns once at R1. |
| WORK-4 | rule | quality | pass | `design-rules.md` row Corners | The row holds 135 in the rules file, which KiCad loaded; KiCad's rule check reports no track_angle violation on the locked copper. The pre-order check is not run here, since the board is not fully routed: the item's measured half is judged by the pre-order check that step 8 of routing runs after the router. |
| WORK-5 | rule | cosmetic | pass | `design-rules.md` row Jogs | The row holds 1 mm in the rules file, which KiCad loaded; KiCad's rule check reports no track_segment_length violation. The pre-order check is not run here, since the board is not fully routed: the item's measured half is judged by the pre-order check that step 8 of routing runs after the router. |
| WORK-6 | rule | quality | pass | `design-rules.md` row Stubs | KiCad reports a track end joined to nothing unaided, and its rule check reports none. The pre-order check is not run here, since the board is not fully routed: the item's measured half is judged by the pre-order check that step 8 of routing runs after the router. |
| WORK-7 | rule | quality | pass | `design-rules.md` row Unconnected vias | KiCad reports a via joined on one layer only unaided, and its rule check reports none. The pre-order check is not run here, since the board is not fully routed: the item's measured half is judged by the pre-order check that step 8 of routing runs after the router. |
| WORK-8 | rule | quality | pass | `design-rules.md` rows Necks and Net class Power, Supply and Ground | Each critical track is at its class's width, 0.5, 0.3 and 0.3 mm in `facts.txt`, and the supply and power pours are one zone each. The pre-order check is not run here, since the board is not fully routed: the item's measured half is judged by the pre-order check that step 8 of routing runs after the router. |
| WORK-9 | rule | cosmetic | pass | `design-rules.md` row Track directions | Every critical track lies along the board's edges or at 45 degrees to them. The pre-order check is not run here, since the board is not fully routed: the item's measured half is judged by the pre-order check that step 8 of routing runs after the router. |
| WORK-10 | rule | quality | pass | `design-rules.md` row Pad entries | The one critical track on a U2 pad, the ground track at pin 7, enters it along its long axis from its end; no critical track meets U1's long pads, the regulator output's pad being joined by a pour that covers its centre. The pre-order check is not run here, since the board is not fully routed: the item's measured half is judged by the pre-order check that step 8 of routing runs after the router. |

- `FLOOR-1`: Where parts sit, judged at placement; it asks nothing of a critical net's copper.
- `FLOOR-2`: The schematic has no sensing front end, so it applies to no net.
- `FLOOR-4`: It asks of the rules file and the part positions, not of any critical net's copper.
- `SENSE-1`: The schematic has no current-sense resistor.
- `SENSE-2`: The schematic has no converter input filter.
- `SENSE-3`: The schematic has no amplifier.
- `SENSE-4`: The schematic has no sensing front end.
- `SENSE-5`: The schematic has no sensing front end.
- `CLOCK-1`: The schematic has no crystal or resonator.
- `CLOCK-2`: The schematic has no crystal or resonator.
- `CLOCK-3`: The schematic has no crystal or resonator.
- `CLOCK-4`: The schematic has no crystal or resonator.
- `MAINS-1`: The board declares no mains.
- `MAINS-2`: The board declares no mains.
- `MAINS-3`: The board declares no mains.
- `MAINS-4`: The board declares no mains.
- `MAINS-5`: The board declares no mains.
- `CONN-1`: The schematic has no suppressor.
- `CONN-2`: The schematic has no leadless package.
- `CONN-3`: It asks where a cable lies over the parts, not of any critical net's copper.
- `CONN-4`: It asks where the mounting holes sit, not of any critical net's copper.
- `TEST-1`: It asks how a probe reaches a test point, which no critical net's copper decides.
- `TEST-2`: It asks which side a test point and the tall parts are on, which no critical net's copper decides.
- `TEST-3`: The schematic has no current-measuring resistor.
- `TEST-4`: The schematic has no current-measuring resistor.
- `MFG-1`: It holds the board-wide minimums to the manufacturer's limits, which no critical net's copper decides.
- `MFG-2`: The schematic has no part with an exposed pad.
- `MFG-3`: The schematic has no part with an exposed pad.
- `EMI-3`: It asks of a line that leaves the board through a capacitor to ground; no critical net's copper decides it.
- `EMI-4`: The schematic has no ferrite bead.
- `EMI-5`: It asks of a series resistor on a controller pin, a signal no critical class carries.

### Pass 2

**Board judged**: c528169c9be5876a982c2719f9d99d8864dc09c1

**Views**: `task hw:views -- --board method-proof.kicad_pcb --project method-proof.kicad_pro --class Power --class Supply --class Ground --out /Users/david/.claude/method-proof-work/w5/method-proof-views` and `task hw:placement -- --board method-proof.kicad_pcb --project method-proof.kicad_pro --out /Users/david/.claude/method-proof-work/w5/method-proof-placement`, the placement view rendered because FLOOR-3, POWER-2, DECOUPLE-1 and WORK-1 name it in their Judged on.

| Item | Kind | Severity | Verdict | Rests on | Why |
|---|---|---|---|---|---|
| FLOOR-3 | judgement | quality | pass | `classes-r1c1.png` and `classes-r2c1.png`, `net-GND-r1c1.png` and `net-GND-r2c1.png`, `net-+5V-r1c1.png` and `net-+5V-r2c1.png`, `net-+3V3-r1c1.png` and `net-+3V3-r2c1.png`, `assembly-top-r1c1.png` and `assembly-top-r2c1.png` and `assembly-bottom-r1c1.png` and `assembly-bottom-r2c1.png`, `placement-r1c1.png` and `placement-r2c1.png`; whole board | J1 and J2 at the left edge, U1 beside them and U2 about 9 mm to the right, the digital region next to the low-voltage one; the ground is four zones on F.Cu, In1.Cu, In2.Cu and B.Cu spanning all three, and the supply reaches U1 first and U2 through the +3V3 strips; the board has no analog region. |
| POWER-1 | rule | function | pass | `design-rules.md` rows Power track width, Supply track width, Ground track width and Net class Power, Supply and Ground; `facts.txt` | Power 0.2 mm is at least 0.381 mm times 0.5 A, 0.19 mm; Supply 0.2 mm is at least 0.381 mm times 0.1 A; Ground 0.2 mm is at least 0.381 mm times 0.5 A, each read from `constraints.md`; the class tracks are 0.5, 0.3 and 0.3 mm wide in `facts.txt`, and KiCad's rule check reports no track_width violation on the locked copper. The pre-order check is not run here, since the board is not fully routed: the item's measured half is judged by the pre-order check that step 8 of routing runs after the router. |
| POWER-2 | judgement | function | pass | `net-+5V-r1c1.png` and `net-+5V-r2c1.png`, `net-_+5V_IN-r1c1.png` and `net-_+5V_IN-r2c1.png`, `net-+3V3-r1c1.png` and `net-+3V3-r2c1.png`, `net-_+3V3_REG-r1c1.png` and `net-_+3V3_REG-r2c1.png`, `facts.txt`, `classes-r1c1.png` and `classes-r2c1.png`, `placement-r1c1.png` and `placement-r2c1.png` | The +5V and +3V3 paths are wide F.Cu pours and 0.5 and 0.3 mm tracks between parts that stand together, with no detour and no neck; no power net in `facts.txt` has a width range reaching the 0.09 mm minimum. |
| POWER-3 | judgement | function | pass | `net-GND-r1c1.png` and `net-GND-r2c1.png`, `net-+5V-r1c1.png` and `net-+5V-r2c1.png`, `net-_+5V_IN-r1c1.png` and `net-_+5V_IN-r2c1.png`, `facts.txt` | The 0.5 A loop reaches the ground planes through three vias at J1 pin 2 and three at J2 pin 3, 0.5 A over 200 mA rounded up, among the 20 ground vias `facts.txt` counts; the power nets change layer only to reach test points and the 5 mA LED branch, and 0.1 A of the logic rail needs one via. |
| POWER-4 | judgement | function | not applicable | `layout-plan.md` plan table row for POWER-4 | The schematic has no part with an exposed pad: U1 is a SOT-23 and U2 a TSSOP-20. |
| POWER-5 | judgement | function | not applicable | `layout-plan.md` plan table row for POWER-5 | The schematic has no part that switches a load. |
| GROUND-1 | judgement | function | pass | `net-GND-r1c1.png` and `net-GND-r2c1.png`, `layer-F.Cu-r1c1.png` and `layer-F.Cu-r2c1.png`, `layer-In1.Cu-r1c1.png` and `layer-In1.Cu-r2c1.png`, `layer-In2.Cu-r1c1.png` and `layer-In2.Cu-r2c1.png`, `layer-B.Cu-r1c1.png` and `layer-B.Cu-r2c1.png`, `facts.txt` | `facts.txt` gives GND four zones, on F.Cu, B.Cu, In1.Cu and In2.Cu; the planes cover the board unbroken across both regions, joined to the outer pours through 20 vias. |
| GROUND-2 | judgement | function | pass | `layer-F.Cu-r1c1.png` and `layer-F.Cu-r2c1.png`, `layer-In1.Cu-r1c1.png` and `layer-In1.Cu-r2c1.png`, `layer-In2.Cu-r1c1.png` and `layer-In2.Cu-r2c1.png`, `layer-B.Cu-r1c1.png` and `layer-B.Cu-r2c1.png`, `net-GND-r1c1.png` and `net-GND-r2c1.png`, `net-+5V-r1c1.png` and `net-+5V-r2c1.png`, `net-+3V3-r1c1.png` and `net-+3V3-r2c1.png` | No track runs on In1.Cu or In2.Cu; the F.Cu tracks lie over In1.Cu and the B.Cu tracks over In2.Cu, each a solid plane under them with only the 0.6 mm via clearances cut in it, none merging into a slot. |
| GROUND-3 | judgement | function | not applicable | `layout-plan.md` plan table row for GROUND-3 | The schematic has no sensing front end or converter. |
| GROUND-4 | judgement | function | not applicable | `layout-plan.md` plan table row for GROUND-4 | The schematic has no part with separate analog and digital ground pins: U1 has one ground pin and U2 one, VSS. |
| GROUND-5 | rule | function | pass | `design-rules.md` row Plated hole spacing, `layer-In1.Cu-r1c1.png`, `layer-In1.Cu-r2c1.png`, `layer-In2.Cu-r1c1.png`, `layer-In2.Cu-r2c1.png` | The row holds 1.35 mm, the item's arithmetic from the 1.7 mm pads with 1.0 mm drills, the 0.25 mm thermal-relief gap, the 0.2 mm Power clearance and the 0.2 mm zone thickness; KiCad's rule check reports no hole_to_hole violation of it on the locked copper, and the rule is shown to fire at 1.6 mm. The pre-order check is not run here, since the board is not fully routed: the item's rule is KiCad's, judged by the pre-order check that step 8 of routing runs after the router. |
| DECOUPLE-1 | judgement | function | pass | `crop-U1.png`, `crop-U2.png`, `placement-r1c1.png` and `placement-r2c1.png` | The crop captions name C1, C2 and C5 for U1 and C3 and C4 for U2; each stands beside its part, the supply reaching the capacitor and on to the pin by a pour or a short track with no via between them: the +5V tap to R1's feed is at (113, 107.9) on the JP1 branch of the pour, outside the box C1's pad and U1's input pin span. |
| DECOUPLE-2 | judgement | function | pass | `crop-U1.png`, `crop-U2.png`, `net-GND-r1c1.png` and `net-GND-r2c1.png` | Each capacitor's ground pad lies in the F.Cu ground pour with two ground vias of its own within 1.7 mm and the planes beneath, so the loop encloses little area. |
| DECOUPLE-3 | judgement | function | not applicable | `layout-plan.md` plan table row for DECOUPLE-3 | The schematic has no switching converter. |
| DECOUPLE-4 | judgement | function | not applicable | `layout-plan.md` plan table row for DECOUPLE-4 | The schematic has no switching converter. |
| DECOUPLE-5 | judgement | function | not applicable | `layout-plan.md` plan table row for DECOUPLE-5 | The schematic has no snubber. |
| DECOUPLE-6 | rule | function | pass | `design-rules.md` row Decoupling vias; `crop-U1.png`, `crop-U2.png` | The row holds none, the item's own figure; no via of C1's, C2's, C3's, C4's or C5's supply net lies in the box its pad spans with the pin it decouples. The pre-order check is not run here, since the board is not fully routed: the item's measured half is judged by the pre-order check that step 8 of routing runs after the router. |
| MFG-4 | rule | quality | pass | `design-rules.md` row Paste over a via | The row holds 0 mm², the item's own figure; every via of the critical nets lies in copper clear of a pad and its paste opening. The pre-order check is not run here, since the board is not fully routed: the item's measured half is judged by the pre-order check that step 8 of routing runs after the router. |
| MFG-5 | rule | quality | pass | `design-rules.md` row Ground pad reliefs | The row holds the rule in the item's form on the Ground class; KiCad's rule check reports no starved_thermal violation on the locked copper. The pre-order check is not run here, since the board is not fully routed: the item's measured half is judged by the pre-order check that step 8 of routing runs after the router. |
| MFG-6 | rule | quality | pass | `design-rules.md` row Pour gap | The row holds 0.09 mm, the minimum clearance MFG-1 holds to the manufacturer's limit. The pre-order check is not run here, since the board is not fully routed: the item's measured half is judged by the pre-order check that step 8 of routing runs after the router. |
| EMI-1 | judgement | quality | pass | `classes-r1c1.png` and `classes-r2c1.png`, `net-GND-r1c1.png` and `net-GND-r2c1.png`, `net-+5V-r1c1.png` and `net-+5V-r2c1.png`, `net-+3V3-r1c1.png` and `net-+3V3-r2c1.png` | Every supply track and pour has the In1.Cu or In2.Cu ground plane directly beneath it, from J1 to U2. |
| EMI-2 | judgement | quality | pass | `layer-F.Cu-r1c1.png` and `layer-F.Cu-r2c1.png`, `layer-In1.Cu-r1c1.png` and `layer-In1.Cu-r2c1.png`, `layer-In2.Cu-r1c1.png` and `layer-In2.Cu-r2c1.png`, `layer-B.Cu-r1c1.png` and `layer-B.Cu-r2c1.png`, `net-GND-r1c1.png` and `net-GND-r2c1.png`, `net-+5V-r1c1.png` and `net-+5V-r2c1.png`, `net-+3V3-r1c1.png` and `net-+3V3-r2c1.png`, `net-_+5V_IN-r1c1.png` and `net-_+5V_IN-r2c1.png`, `net-_+3V3_REG-r1c1.png` and `net-_+3V3_REG-r2c1.png` | No critical net runs along the board edge: the nearest track, the +5V_IN run at y 103.5 mm, is 3.5 mm inside it. |
| WORK-1 | judgement | quality | pass | `assembly-top-r1c1.png` and `assembly-top-r2c1.png` and `assembly-bottom-r1c1.png` and `assembly-bottom-r2c1.png`, `layer-F.Cu-r1c1.png` and `layer-F.Cu-r2c1.png`, `layer-In1.Cu-r1c1.png` and `layer-In1.Cu-r2c1.png`, `layer-In2.Cu-r1c1.png` and `layer-In2.Cu-r2c1.png`, `layer-B.Cu-r1c1.png` and `layer-B.Cu-r2c1.png`, `net-GND-r1c1.png` and `net-GND-r2c1.png`, `net-+5V-r1c1.png` and `net-+5V-r2c1.png`, `placement-r1c1.png` and `placement-r2c1.png`; the LENGTH total, 143.6795 mm, and the CROSSINGS total, 11 | The critical nets join parts that stand together, and the placement view's 11 crossings are of the ground, +5V, +3V3 and /+3V3_REG trees, which the planes and pours carry with no copper crossing. |
| WORK-2 | rule | quality | pass | `design-rules.md` row Route length | The row holds 1.3 from `WORK_DETOUR_RATIO`, the item's own figure. The pre-order check is not run here, since the board is not fully routed: the item's measured half is judged by the pre-order check that step 8 of routing runs after the router. |
| WORK-3 | judgement | quality | pass | `layer-F.Cu-r1c1.png` and `layer-F.Cu-r2c1.png`, `layer-In1.Cu-r1c1.png` and `layer-In1.Cu-r2c1.png`, `layer-In2.Cu-r1c1.png` and `layer-In2.Cu-r2c1.png`, `layer-B.Cu-r1c1.png` and `layer-B.Cu-r2c1.png`, `net-+5V-r1c1.png` and `net-+5V-r2c1.png`, `net-+3V3-r1c1.png` and `net-+3V3-r2c1.png`, `net-_+5V_IN-r1c1.png` and `net-_+5V_IN-r2c1.png`, `net-_+3V3_REG-r1c1.png` and `net-_+3V3_REG-r2c1.png`, `classes-r1c1.png` and `classes-r2c1.png` | The critical tracks run straight with 45-degree corners and no doubling back; they change layer only to reach a test point on the back, and the +5V branch to R1 crosses to the back once to pass the +3V3 strips and returns once at R1. |
| WORK-4 | rule | quality | pass | `design-rules.md` row Corners | The row holds 135 in the rules file, which KiCad loaded; KiCad's rule check reports no track_angle violation on the locked copper. The pre-order check is not run here, since the board is not fully routed: the item's measured half is judged by the pre-order check that step 8 of routing runs after the router. |
| WORK-5 | rule | cosmetic | pass | `design-rules.md` row Jogs | The row holds 1 mm in the rules file, which KiCad loaded; KiCad's rule check reports no track_segment_length violation. The pre-order check is not run here, since the board is not fully routed: the item's measured half is judged by the pre-order check that step 8 of routing runs after the router. |
| WORK-6 | rule | quality | pass | `design-rules.md` row Stubs | KiCad reports a track end joined to nothing unaided, and its rule check reports none. The pre-order check is not run here, since the board is not fully routed: the item's measured half is judged by the pre-order check that step 8 of routing runs after the router. |
| WORK-7 | rule | quality | pass | `design-rules.md` row Unconnected vias | KiCad reports a via joined on one layer only unaided, and its rule check reports none. The pre-order check is not run here, since the board is not fully routed: the item's measured half is judged by the pre-order check that step 8 of routing runs after the router. |
| WORK-8 | rule | quality | pass | `design-rules.md` rows Necks and Net class Power, Supply and Ground | Each critical track is at its class's width, 0.5, 0.3 and 0.3 mm in `facts.txt`, and the supply and power pours are one zone each. The pre-order check is not run here, since the board is not fully routed: the item's measured half is judged by the pre-order check that step 8 of routing runs after the router. |
| WORK-9 | rule | cosmetic | pass | `design-rules.md` row Track directions | Every critical track lies along the board's edges or at 45 degrees to them. The pre-order check is not run here, since the board is not fully routed: the item's measured half is judged by the pre-order check that step 8 of routing runs after the router. |
| WORK-10 | rule | quality | pass | `design-rules.md` row Pad entries | The one critical track on a U2 pad, the ground track at pin 7, enters it along its long axis from its end; no critical track meets U1's long pads, the regulator output's pad being joined by a pour that covers its centre. The pre-order check is not run here, since the board is not fully routed: the item's measured half is judged by the pre-order check that step 8 of routing runs after the router. |

- `FLOOR-1`: Where parts sit, judged at placement; it asks nothing of a critical net's copper.
- `FLOOR-2`: The schematic has no sensing front end, so it applies to no net.
- `FLOOR-4`: It asks of the rules file and the part positions, not of any critical net's copper.
- `FLOOR-5`: It asks where a connector stands, which no critical net's copper decides.
- `SENSE-1`: The schematic has no current-sense resistor.
- `SENSE-2`: The schematic has no converter input filter.
- `SENSE-3`: The schematic has no amplifier.
- `SENSE-4`: The schematic has no sensing front end.
- `SENSE-5`: The schematic has no sensing front end.
- `CLOCK-1`: The schematic has no crystal or resonator.
- `CLOCK-2`: The schematic has no crystal or resonator.
- `CLOCK-3`: The schematic has no crystal or resonator.
- `CLOCK-4`: The schematic has no crystal or resonator.
- `MAINS-1`: The board declares no mains.
- `MAINS-2`: The board declares no mains.
- `MAINS-3`: The board declares no mains.
- `MAINS-4`: The board declares no mains.
- `MAINS-5`: The board declares no mains.
- `CONN-1`: The schematic has no suppressor.
- `CONN-2`: The schematic has no leadless package.
- `CONN-3`: It asks where a cable lies over the parts, not of any critical net's copper.
- `CONN-4`: It asks where the mounting holes sit, not of any critical net's copper.
- `TEST-1`: It asks how a probe reaches a test point, which no critical net's copper decides.
- `TEST-2`: It asks which side a test point and the tall parts are on, which no critical net's copper decides.
- `TEST-3`: The schematic has no current-measuring resistor.
- `TEST-4`: The schematic has no current-measuring resistor.
- `MFG-1`: It holds the board-wide minimums to the manufacturer's limits, which no critical net's copper decides.
- `MFG-2`: The schematic has no part with an exposed pad.
- `MFG-3`: The schematic has no part with an exposed pad.
- `MFG-7`: It asks which layer a reference designator is on, which no critical net's copper decides.
- `EMI-3`: It asks of a line that leaves the board through a capacitor to ground; no critical net's copper decides it.
- `EMI-4`: The schematic has no ferrite bead.
- `EMI-5`: It asks of a series resistor on a controller pin, a signal no critical class carries.

Load-cell amplifiers, round 2c-e5, local nets (unsigned; the Sense class is not locked). `WT1_INA_N`, `WT1_INA_P`, `WT1_VBG`, `WT2_INA_N` and `WT2_INA_P` are routed pad to pad on F.Cu, with no clearance shortfall and every segment at 0, 45 or 90 degrees. Test points re-sited: `TP671` (WT1_INA_P) from (102, 101.5) to (87.9, 123.2) on the B side, tapped through a 0.6 mm via at (88.8, 122.3) beside `R670.2`, because the B.Cu `PT1_RTDINN`, `PT1_RTDINP` and `PT1_FORCEP` lanes close every other pocket near that net; `TP673` (WT2_INA_P) stays and is tapped through a via at (87.75, 107.5) from the F.Cu lane at x 88.4. `WT2_INA_N` joins `R676.2` (east of `U631`) to `U631.7` through two 0.6 mm vias, at (93.2, 107.17) and (100.5, 106.98), and a B.Cu run along y 106.02, because the +5V trunk at x 94.05 closes the channel between the pin columns on F.Cu. Detours above 1.3 times the straight line: `WT1_VBG` U630.6 to C672.1 1.38, `WT2_INA_N` C675.2 to U631.7 1.39, `WT2_INA_P` C675.1 to R675.2 1.40.

Load-cell amplifiers, round 2c-e6, WT1 raw lines (unsigned; the Sense class is not locked). `WT1_SP_RAW` (J630.4 to R670.1) and `WT1_SN_RAW` (J630.3 to R671.1) are routed on F.Cu with no via, no clearance shortfall and every segment at 0, 45 or 90 degrees. Both leave the header to the east, clear of the B.Cu PT1 and PT2 lane wall at x 108 to 112, and run round the south of the J521 and J522 connectors. They cannot run adjacent: the strip between the connector pads and the Ground via at (101.5, 124.62) takes one track at y 121.7 and one at y 125.35, and no more. Detours above 1.3 times the straight line: `WT1_SP_RAW` 47.2 mm for 30.1 mm (1.57) and `WT1_SN_RAW` 65.3 mm for 27.7 mm (2.36). The two lines differ in length by 18 mm, above the 5 mm aim; bring-up checks the bridge reading noise.
