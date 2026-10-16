# Layout plan of the method proof design

**NOT FOR MANUFACTURE.** `method-proof` is a throwaway four-layer board, 40 mm by 30 mm, from (100, 100) to (140, 130) in board coordinates, made only to prove `docs/board-design-method.md`. It is marked not for manufacture and is never ordered. Its figures are read from `constraints.md`, its synthetic constraints record, and the manufacturer's stated limits, `docs/board-manufacturer-jlcpcb.md`. It carries no mains.

The stack is F.Cu, In1.Cu, In2.Cu and B.Cu, 1 oz each. In1.Cu and In2.Cu are each a solid `GND` plane over the whole board; F.Cu and B.Cu carry the tracks and a `GND` pour each. Every surface-mount part and every connector is on F.Cu. The four test points, TP1 to TP4, are dedicated pads on B.Cu, so the tall parts, the connectors and the link headers, are on the side no probe lands on.

The layer-by-layer plan of the nets: `+5V_IN`, `+5V`, `/+3V3_REG` and `+3V3` are tracks on F.Cu, with a short stub to a test point's pad through a via where it changes layer; `GND` is the planes and the pours, each ground pad reaching In1.Cu and In2.Cu through its own vias; `/LED_K`, `/LED_A` and `/PA1_HDR` are short tracks on F.Cu. Net classes: `Power` holds `/+5V_IN` and `+5V`, `Supply` holds `/+3V3_REG` and `+3V3`, `Ground` holds `GND`, and every other net is in `Default`. The critical classes are `Power`, `Supply` and `Ground`.

## Floorplan

| Region | Bounds | What it holds | Parts |
|---|---|---|---|
| mains | none: the board carries no mains | nothing | none |
| low voltage | (100, 100)–(119, 130) | J1, the 5 V supply input, with its link JP1 and test point TP1; U1, the 3.3 V regulator, with its capacitors C1 and C2, its link JP2 and test point TP2; J2, the output header, with its filter capacitors C5 and C4; a mounting hole at the left edge | J1, JP1, TP1, U1, C1, C2, JP2, TP2, J2, C5, C4, H1 |
| analog sensing | none: the schematic carries no sensing front end | nothing | none |
| digital | (119, 100)–(140, 130) | U2, the controller, with its supply capacitor C3 and the rail's test point TP3; D1, the status LED, with its resistor R1 and test point TP4, which U2's PA0 drives; J3, the PA1 header; two mounting holes at the right edge | U2, C3, TP3, R1, D1, TP4, J3, H2, H3 |

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
| TEST-1 | yes | TP1 to TP4 each a dedicated 1.0 mm pad on B.Cu, at least 2.5 mm apart centre to centre, at least 1.0 mm from any part's body, and at least 2.0 mm from any part taller than 2.6 mm; none a surface-mount part's land. |
| TEST-2 | yes | All four test points on B.Cu, and every part taller than 6.4 mm, J1, J2, J3, JP1 and JP2, on F.Cu. |
| TEST-3 | no | No resistor used to measure current in the schematic: R1 sets an LED's current and nothing reads its voltage. |
| TEST-4 | no | No resistor used to measure current in the schematic. |
| MFG-1 | yes | The board-wide minimums of Board Setup set to JLCPCB's stated limits for four layers at 1 oz, each with its row in `design-rules.md`, naming this item and the capability page and its date. |
| MFG-2 | no | No part in the schematic has an exposed pad on its underside. |
| MFG-3 | no | No part in the schematic has an exposed pad on its underside. |
| MFG-4 | yes | `PASTE_OVER_VIA_MM2` set to 0 in `design-rules.md`; no via is placed under a paste opening, the vias at the capacitors' ground pads standing beside the pads. |
| MFG-5 | yes | The `Ground pad reliefs` rule of `design-rules.md` on class `Ground`, with no exempt pad, the board having no exposed pad. |
| MFG-6 | yes | The pre-order check's `MFG-6` figure, the board's minimum clearance, with every pour stopping at least that far from copper of its own net that it does not touch. |
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
