# Layout plan of the layout review proof design

`review-proof` is a throwaway four-layer board, 92 mm by 60 mm, made only to prove the layout review step of `docs/board-design-method.md`: it carries at least one part for every area of the layout practice catalogue, so each area has something a review can judge. It is marked not for manufacture and is never ordered. Its figures are read from `constraints.md`, its synthetic constraints record, and `separation-basis.yaml`, its synthetic separation basis record, both beside it; its rules are in `design-rules.md`.

U1 stands for a power phototriac, Vishay VO3526, a six-pin DIP with pin 5 removed, drawn with a symbol and footprint of that pinout. Its datasheet's application note (Vishay, *VO3526 Power Phototriac Design Considerations*, Application Note 33, document 81937) states that its heat leaves through its leads into the board, which is what brings it under `POWER-5`.

## Floorplan

| Region | Bounds | What it holds |
|---|---|---|
| mains | (0, 0)–(28, 60) | J1, the mains input and switched-load terminal; U1's load side, pins 4 and 6; the `MAINS_L` and `MAINS_SW` tracks and copper areas |
| low voltage | (28, 0)–(56, 60) | J2, the 5 V supply input, and D1, its suppressor; U2, the 3.3 V regulator, with C1 and C2; J4, the load connector; U1's LED side, pins 1 to 3, with R4; the `+5V` trunk; TP1 and TP2; TP3 and TP4 on the load return |
| analog sensing | (56, 28)–(92, 60) | R1, the load-current shunt; U3, its amplifier, with R2, R3, FB1 and C3; TP5 and TP6 |
| digital | (56, 0)–(92, 28) | U4, the controller, with C4; Y1, its crystal, with C5 and C6 |

| Connector | Edge | Position |
|---|---|---|
| J1 | left | (6, 24) |
| J2 | top | (37, 3.5) |
| J4 | bottom | (37, 55.5) |

## Plan

| Item | Applies | How the layout meets it, or why it does not apply |
|---|---|---|
| FLOOR-1 | yes | Each part within its region above. U3 and its parts in analog sensing, at the far end of the board from U4 and Y1 and from the switching part U1; U4 beside U2, which feeds it. |
| FLOOR-2 | yes | U3's output `AMP_OUT` is the one analog signal that reaches the digital region, at U4's converter input pin 14; it runs on B.Cu straight up x 68.6 mm from U3 to U4. The only digital track leaving the digital region, `LED_DRV`, runs on B.Cu down x 64 mm to y 26 mm and along y 26 mm to U1, outside the analog sensing region. |
| FLOOR-3 | yes | J2 at the top edge, U2 at (44, 14), 13 mm from it, and U4 at (72, 14), 28 mm from U2 along the `+3V3` trunk at y 15.1 mm, with the ground planes on In1.Cu and In2.Cu spanning all three. The analog supply `+3V3A` is taken from `+3V3` through FB1 at U3. |
| POWER-1 | yes | Custom rules `Power track width` (0.4 mm), `Ground track width` (0.4 mm), `Supply track width` (0.2 mm) and `Mains track width` (0.2 mm) in `design-rules.md`, each read from `constraints.md`'s currents. |
| POWER-2 | yes | `+5V` a straight 0.8 mm trunk from J2 to J4 down x 37 mm, branching at y 16.3 mm to U2's input; `LOAD_RTN` 0.8 mm from J4 straight to R1; `MAINS_L` and `MAINS_SW` 1.0 mm straight from J1 to U1. |
| POWER-3 | yes | No power path changes layer: `+5V`, `LOAD_RTN`, `+3V3` and the mains nets carry their current on F.Cu end to end; the vias on `+5V` (TP1), `+3V3` (TP2) and `LOAD_RTN` (TP3, TP4) carry only a test point's probe. |
| POWER-4 | yes | U4's exposed pad (pad 21) sits on its land with four 0.3 mm thermal vias in it, each joined solidly to the ground planes on In1.Cu and In2.Cu and to the ground pour on B.Cu. |
| POWER-5 | yes | U1's load-side pads, pins 4 and 6, each joined to a copper area on both F.Cu and B.Cu, `MAINS_SW` from y 8 to 20.3 mm and `MAINS_L` from y 22.6 to 34 mm, x 2 to 26.3 mm, stopping 4.7 mm short of U1's low-voltage pads. |
| GROUND-1 | yes | `GND` a plane on In1.Cu and In2.Cu and a pour on F.Cu and B.Cu, each over the whole low-voltage part of the board from x 32.8 mm; every ground pad joined to the planes by a via of its own, or tracked to a pad that has one. |
| GROUND-2 | yes | Every F.Cu signal track runs over the unbroken In1.Cu plane, every B.Cu track over the unbroken In2.Cu plane; nothing is routed on In1.Cu or In2.Cu. |
| GROUND-3 | yes | One ground, the In1.Cu and In2.Cu planes, under both the analog sensing and the digital regions, with no split. |
| GROUND-4 | no | No part in the schematic has separate analog and digital ground pins: U4 has one ground pin, pin 8, and its exposed pad. |
| DECOUPLE-1 | yes | C4 (100 nF) at U4's supply pin 15, the `+3V3` trunk reaching C4's pad before the pin; C3 (100 nF) at U3's supply pin 5; C1 (1 µF) at U2's input pin 3 and C2 (1 µF) at its output tab. No via between any of them and its pin. |
| DECOUPLE-2 | yes | Each decoupling capacitor's ground pad joined straight to the F.Cu ground pour and through its own via to the planes beside the pad: C4 at (67.4, 18.6), C3 at (72.7, 41.7), C1 at (40.85, 22.6), C2 at (50, 17.4). |
| DECOUPLE-3 | no | No switching converter in the schematic: U2 is a linear regulator. |
| DECOUPLE-4 | no | No switching converter in the schematic. |
| DECOUPLE-5 | no | No snubber in the schematic. |
| SENSE-1 | yes | The sense track `LOAD_RTN` to U3's input leaves R1's pad 1 at its own top end, apart from the load-current track entering the pad from the left; R3, the gain resistor, returns to R1's ground pad 2 by its own track. |
| SENSE-2 | no | No filter at a converter input and no reference capacitor in the schematic: `AMP_OUT` goes straight to U4's pin 14, and U4 uses its supply as reference. |
| SENSE-3 | yes | R2, the feedback resistor, and R3, the gain resistor, beside U3's inverting input, pin 4, by tracks of 3 mm and less. |
| SENSE-4 | yes | The sensing nets `AMP_FB` and `AMP_OUT` and the sense part of `LOAD_RTN` within the analog sensing region, away from the crystal, U1 and the mains region; `AMP_OUT` leaves it only to reach U4. |
| SENSE-5 | yes | U3, R1, R2 and R3 in the analog sensing region; U2, the regulator, and U1, the switching part, in the low-voltage region more than 20 mm away. |
| CLOCK-1 | yes | Y1 at U4's oscillator pins 2 and 5, tracks under 10 mm; C5 at Y1's pad 1 (`XTAL1`, the input), C6 at Y1's pad 2; `XTAL1` and `XTAL2` routed apart, on opposite sides of U4's pins 3 and 4. |
| CLOCK-2 | yes | The F.Cu ground pour under Y1, C5 and C6, joined to the planes by the capacitors' ground vias at (86.5, 9.75) and (86.5, 18.25); no other circuit's current passes there. |
| CLOCK-3 | yes | Y1 at (80, 14); no part but U4 and its own C4, C5 and C6 within 25 mm of it, and every connector more than 40 mm away. |
| MAINS-1 | yes | The `Mains separation` rule of `design-rules.md`, at the separation basis record's 3 mm clearance and 4 mm creepage. |
| MAINS-2 | yes | All `Mains` copper within the mains region, x below 28 mm, on every layer, and no low-voltage copper below x 28 mm. U1, the part that bridges the barrier, straddles x 28 mm, its mains pins at x 24.19 mm and its low-voltage pins at x 31.81 mm. The ground planes and pours start at x 32.8 mm. |
| MAINS-3 | yes | No copper on any layer between U1's mains pins (x 24.19 mm) and its low-voltage pins (x 31.81 mm). |
| MAINS-4 | yes | U1's two sides are 7.62 mm apart centre to centre, 6.02 mm pad edge to pad edge, above the separation basis record's 4.0 mm creepage, so no slot is cut. |
| CONN-1 | yes | D1 on the `+5V` line 5.7 mm from J2's pin 1, the trunk running straight from J2's pin through D1's pad and on to U2; D1's ground pad straight to its via. |
| CONN-2 | yes | U4, the board's only leadless part, at (72, 14), more than 10 mm from every connector and board edge; the board has no mounting holes. |
| CONN-3 | yes | J1 at the left edge, J2 at the top edge and J4 at the bottom edge, each facing off the board, their cables leaving away from U4 and Y1. |
| TEST-1 | yes | Every test point a dedicated 1.0 mm pad on B.Cu, at least 2.5 mm from every other, with no part body on B.Cu. |
| TEST-2 | yes | All six test points on B.Cu, which carries no part; every part is on F.Cu. |
| TEST-3 | yes | R1's net `LOAD_RTN` carries TP3 and TP4, its ground net TP5 and TP6, all within 8 mm of R1. |
| MFG-1 | yes | Every board-wide minimum in `design-rules.md` set to JLCPCB's stated limit for 4 layers at 2 oz, each row naming the page and the date it was read. |
| MFG-2 | yes | U4's exposed pad pasted through the footprint's four openings, together about 65 % of the pad. |
| MFG-3 | yes | The four vias in U4's exposed pad land drilled 0.3 mm, within 0.33 mm. |
| EMI-1 | yes | Every supply track on F.Cu runs over the In1.Cu ground plane, every B.Cu track over In2.Cu, from source to part. |
| EMI-2 | yes | The nets switching faster than 50 kHz are `XTAL1` and `XTAL2`, running only between U4, Y1, C5 and C6, more than 7 mm from every board edge. |
| EMI-3 | yes | C1 on `+5V`, the line J2 brings onto the board, is U2's input capacitor, placed at U2's input pin as `DECOUPLE-1` requires; its ground joins the F.Cu pour and the planes through its via. |
| EMI-4 | yes | FB1 in `+3V3` beside U3, C3 between FB1 and U3's supply pin 5, the bead in the supply only. |
| EMI-5 | no | No resistor in series with a controller pin: U4's pin 11 drives U1's LED directly, and R4 is in the LED's return to ground at U1. |

### The board's own items

| Item | Applies when | Asks | Passes | Fails, as the views show it | Judged on | Kind | Severity | Source | How the layout meets it |
|---|---|---|---|---|---|---|---|---|---|
| none | | | | | | | | | |
