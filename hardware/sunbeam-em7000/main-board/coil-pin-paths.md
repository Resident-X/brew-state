# Relay coil pins: straight-line and slot-aware distances to Mains copper

A measurement record for the main board. It answers one question: do the 16 `mounting_hole` lines in the pre-order check's final result, all on the coil pins of three bought relays, show a mains separation shortfall, or are they the straight-line rule measuring something the held figures do not describe?

Measured on commit `1f9f8357`, read only, from a clean checkout of `main-board.kicad_pcb`.

## Answer

The 16 lines are an artefact of the rule, not a breach. Every one of the 16 pairs meets the held figures: 3.0 mm straight clearance (smallest 6.122 mm) and 10.0 mm creepage along the shortest surface path that goes round the barrier slots (smallest 10.763 mm, largest 29.218 mm). No board change is needed. The acceptance in `DEC-MAIN-BOARD-RESIDUAL-RISKS-ACCEPTED-BY-OWNER` item (e) does not cover these lines, and does not need to: the figures are carried by the path measurement here.

## The figures held and what the rule measured

The held figures for the mains-to-low-voltage pair are 3.0 mm clearance, measured straight, and 10.0 mm creepage, measured along the shortest path over the board surface that crosses no barrier slot (round the slot ends). See `design-rules.md`, "Mains separation, how the declared figures are met", and `separation-basis.yaml`.

The check's mounting-hole rule applies `hole_clearance (min 10mm)` from any through-hole pad not on a Mains-class net to any Mains-class copper. The 10 is the larger of the signed clearance and creepage. KiCad measures it as a straight line from the drilled hole edge, on any layer, ignoring slots. The three relay coil pins (K741 A1 on +5V, K201 A2 on POL_COIL_LO, K731 A2 on VALVE_2W_COIL_K) are plated holes of parts, so the rule treats them like mounting fixings and reports pads, tracks, vias and a pour that lie 6.6 to 9.9 mm away in a straight line but on the far side of a slot. The slot-aware creepage rule (`mains_layer_separation` and KiCad's own creepage constraint) reports nothing on these pins.

## Method

Distances are copper edge to copper edge. "Straight" is from the pin's pad edge (annular ring, present on every layer) to the Mains copper in plan view, any layer. "Path" is the shortest in-board route between the two copper outlines that does not enter a slot; the slots cut every layer, so the path does not depend on layer. Each slot is an obstacle, with the path going round its ends, as the check and the basis do; no credit is taken for the groove contour.

Four independent measurements:

1. Own geometry (shapely, with a purpose-written reader for the board file: pads, tracks, vias, stored zone fills, Edge.Cuts with four closed cut-outs) and an exact visibility-graph shortest path. Its straight figures reproduce the check's hole-edge figures to 0.001 mm on all 16 lines.
2. A grid shortest-path search over the same surface at 0.05 and 0.1 mm, with no assumed bend points. It agrees on 16 of 16 pairs within 0.01 to 0.35 mm, and is never shorter by more than 0.03 mm on a pair near 10 mm.
3. The check's own path code (`board_geometry.route_length`). Identical to 0.001 mm on the 11 K741 and K201 pairs. On the K731 pairs it reports 2.7 to 5.3 mm longer, because it accepts only end legs under its 10 mm reach, so there it is an upper bound and still above 10 mm.
4. `kicad-cli pcb drc` (10.0.7) with added `clearance` and `creepage` rules of 30 mm between each of the three pins and Mains-class copper, on a trimmed copy of the board. Clearance matches the own geometry to 0.0004 mm on four pairs (rows 1, 2, 3, 5). Creepage matches to 0.001 mm on four pairs (K201 to C601 pad 2 at 10.4135 mm; rows 3, 10, 14). KiCad's creepage differs on three pairs (rows 13, 15, 16: 19.93 against 23.96, 29.57 against 29.22, 22.79 against 14.14); all are above 10 mm, so no verdict changes. KiCad reports only a subset of item pairs for the rule, hence the blank cells.

## Table

K201 A2: 1.4 mm drill, 2.2 mm pad. K741 A1 and K731 A2: 1.0 mm drill, 2.0 mm pad. Margin is path minus 10.0 mm. "Log gap" is the check's straight hole-edge figure.

| # | Coil pin (net) | Mains copper named in the log | Mains net | Layer | Log gap, hole edge (mm) | Straight, pad edge (mm) | Path round slots (mm) | Margin (mm) |
|---|---|---|---|---|---|---|---|---|
| 1 | K741 A1 (+5V) | track, 22.99 mm long | PUMP_S_OPTO_MT | In2.Cu | 8.0323 | 7.532 | 22.659 | +12.659 |
| 2 | K741 A1 (+5V) | track, 1.1314 mm long | PUMP_S_OPTO_MT | In2.Cu | 6.9977 | 6.498 | 22.036 | +12.036 |
| 3 | K741 A1 (+5V) | via at (53.49, 13.9) | PUMP_S_OPTO_MT | all | 6.7727 | 6.273 | 21.811 | +11.811 |
| 4 | K741 A1 (+5V) | track, 1.36 mm long | PUMP_S_OPTO_MT | F.Cu | 6.9977 | 6.498 | 22.036 | +12.036 |
| 5 | K201 A2 (POL_COIL_LO) | track, 4.645 mm long | AMC_AIN0N | F.Cu | 8.5279 | 8.128 | 10.763 | +0.763 |
| 6 | K201 A2 (POL_COIL_LO) | track, 1.445 mm long | AMC_AIN0P | F.Cu | 9.7862 | 9.387 | 13.847 | +3.847 |
| 7 | K201 A2 (POL_COIL_LO) | track, 2.85 mm long | AMC_AIN0P | F.Cu | 9.8883 | 9.488 | 11.762 | +1.762 |
| 8 | K201 A2 (POL_COIL_LO) | track, 0.3536 mm long | AMC_AIN0P | F.Cu | 9.8883 | 9.488 | 13.491 | +3.491 |
| 9 | K741 A1 (+5V) | pad 4 of U711 | PUMP_S_TRIAC_G | F.Cu | 9.8543 | 9.354 | 27.563 | +17.563 |
| 10 | K741 A1 (+5V) | pad 5 of U711 | unconnected (NC) | F.Cu | 8.0156 | 7.516 | 25.024 | +15.024 |
| 11 | K741 A1 (+5V) | pad 6 of U711 | PUMP_S_OPTO_MT | F.Cu | 6.6220 | 6.122 | 22.488 | +12.488 |
| 12 | K201 A2 (POL_COIL_LO) | pad 10 of U601 | AMC_AIN0N | F.Cu | 8.2600 | 7.860 | 13.655 | +3.655 |
| 13 | K731 A2 (VALVE_2W_COIL_K) | NEUTRAL pour fill | NEUTRAL | In2.Cu | 7.3703 | 6.870 | 23.959 | +13.959 |
| 14 | K731 A2 (VALVE_2W_COIL_K) | pad 4 of U701 | PUMP_C_TRIAC_G | F.Cu | 7.1268 | 6.627 | 26.689 | +16.689 |
| 15 | K731 A2 (VALVE_2W_COIL_K) | pad 5 of U701 | unconnected (NC) | F.Cu | 8.7355 | 8.236 | 29.218 | +19.218 |
| 16 | K201 A2 (POL_COIL_LO) | pad 9 of U601 | AMC_AIN0P | F.Cu | 9.5294 | 9.130 | 14.142 | +4.142 |

Net names are shortened from their sheet paths (for example `/Pump drives/PUMP_S_OPTO_MT`).

All routes from K741 A1 go round the top end of the C-shaped slot at (52.48, 3.0) through the 1.0 mm corridor between the slot end and the board edge; all routes from K731 A2 go round the lower end of the same slot at (52.48, 49.0) and (53.68, 49.0).

## Thin margin to keep

The tightest pair of these three relay pins is not one of the 16 lines: K201 A2 to C601 pad 2 (AMC_AIN0N) is 10.414 mm by path, a margin of 0.414 mm (4.1 percent). Its straight hole-edge figure is 10.264 mm, over the rule's 10 mm, so the check prints no line for it. The next nearest are AMC_AIN0N tracks at 10.668, 10.756 and 10.763 mm. The path runs from the pin ring to the slot-arm end corner at (52.5, 91.5), 8.21 mm, then 2.2 mm to C601 pad 2. No change to the board should bring K201, C601 or that copper nearer.

## Caveats

- Zone fill is the stored fill in the committed file; the check refills. Its figure for the NEUTRAL fill (7.3703 mm) equals the own geometry (7.3704 mm), so the fill is unchanged near the pin.
- Circles are approximated by 32-sided polygons, which is non-conservative by up to 0.005 mm.
- The creepage differences with KiCad on rows 13, 15 and 16 are explained above and all lie above 10 mm.
- This record measures the committed commit only; a later change to the board copper near these pins needs the measurement repeated.
