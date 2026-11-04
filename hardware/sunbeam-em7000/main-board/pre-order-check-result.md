# Main board: final pre-order check result

Date: 5 November 2026. Commit checked: `200c0ae6` (the last design-file commit; later commits are records and graph only). Command: `task hw:verify`, run in a clean checkout of that commit, with the real, unsigned separation basis. Started 05:34 AEDT; the log was last written 08:03 AEDT, so the run took about 2 h 28 min. Exit status: 201 (task's own exit status 1). Closing line: `RESULT | FAIL | 1 of 6 designs failed`. The five proof designs pass; the main board fails with 2,042 violations.

This is the real record. A second run with a scratch top-level signature in a separate checkout unlocked nothing (the separation basis still reported 1 against 2, because its 98 exceptions were unsigned), so it is not a comparison and is not used here.

## Counts by rule

| Rule | Lines |
|---|---|
| clearance | 499 (capped list) |
| track_angle | 199 (capped list) |
| track_segment_length | 199 (capped list) |
| workmanship_direction | 179 |
| silk_overlap | 151 |
| designator_astray | 141 |
| workmanship_pad_entry | 140 |
| workmanship_pad_corner | 125 |
| workmanship_detour | 95 |
| silk_over_copper | 90 |
| track_width | 51 |
| hole_to_hole | 27 |
| silk_edge_clearance | 23 |
| test_point_courtyard | 23 |
| ground_return | 17 |
| workmanship_width | 14 |
| starved_thermal | 13 |
| pour_gap | 12 |
| derated_voltage | 10 |
| courtyards_overlap | 9 |
| track_not_centered_on_via | 5 |
| decoupling_via | 4 |
| footprint_symbol_mismatch | 3 |
| separation_basis | 2 |
| items_not_allowed | 2 |
| footprint_symbol_field_mismatch | 2 |
| via_dangling | 1 |
| isolated_copper | 1 |
| connection_width | 1 |
| lib_footprint_mismatch | 1 |
| sensing_clearance | 1 |
| reference_off_silkscreen | 1 |
| side_fiducials | 1 |
| Total | 2,042 |

The clearance, track_angle and track_segment_length figures are KiCad's capped lists (499, 199 and 199), and the annular_width list is capped the same way. Those four counts are not complete counts of the underlying items.

## Comparison with the earlier run on `e16d375b` (2,039)

The total rose by 3. The changes:

- footprint_symbol_mismatch: +3 lines, for R522, R572 and R576. The board carries the do-not-populate flag; the schematic symbol cannot be set with the available tools.
- NT601's footprint_symbol_mismatch is fixed.
- via_dangling: 2 to 1.
- footprint_symbol_field_mismatch: 1 to 2. D402's Description and U201's Datasheet differ between the board footprint and the schematic after commit `cdc3533d`; NT601's LCSC field is fixed.
- reference_off_silkscreen: +1, because NT601's reference is hidden.
- mains_barrier: 0 (it was 33 before the MAINS-5 re-route).

## Separation basis

Two separation_basis lines: `accepted_by` and `accepted_on` are missing from `hardware/sunbeam-em7000/separation-basis.yaml`. The basis is unsigned, so none of its figures is signed and none changes here.

## What this run does not cover

The mains-spacing rules did not run, because the basis is unsigned. The creepage, layer-separation and spacing-exception lines appear only with a signed basis. This record therefore says nothing about mains spacing.

The mains-spacing comparison with the earlier baseline rests on the creepage verification recorded in the next section, which ran against a signed scratch copy of the head board and not against the real, unsigned basis. It found no breach of a signed mains-to-low-voltage figure, and the same standing mains-to-mains shortfalls as every earlier board (recorded in the layout plan's open items).

## Creepage verification of the mains-to-low-voltage pair C601 pad 2 to K201 pin A2

What ran: an AI agent in a read-only session after the layout review's round 1 closed, with no change to any design file, on the board file as it stood at commit `502f317e`, whose design files are identical to those of `200c0ae6`, the commit the final check above ran on (`git diff 502f317e 200c0ae6` on the board's folder changes no KiCad file). It measured the same pair three ways, and the figures below are the agent's, not the owner's and not the layout reviewer's. The session's own report was not committed; this section is the record of its figures and of the runs that produced them.

The pair: C601 pad 2 (net AMC_AIN0N, neutral-referenced through the net tie NT601, Mains class) and K201 coil pin A2 (net POL_COIL_LO, low voltage), both on F.Cu. The signed mains-to-low-voltage figures are 3.0 mm clearance and 10.0 mm creepage along the surface.

| Method | Straight line | Surface path round the U601 slot arm | Margin to the signed 10.0 mm |
|---|---|---|---|
| Geometry from the board file (pad polygons, Edge.Cuts slot loops, shortest path through slot corners) | 9.870 mm | 10.414 mm | 0.414 mm |
| `board_geometry.route_length` on the same two pads | 9.865 mm | 10.4136 mm | 0.414 mm |
| `kicad-cli pcb drc` with a probe rule on a pruned copy of the board | | 10.4135 mm | 0.414 mm |

The path runs down the west end of the U601 slot arm (x 52.5 to 61.9, y 90.3 to 91.5) and back out: C601's copper stands level with the arm's end but 1.0 mm above it, so the shortest way round is 2.2 mm along the arm's end wall and 8.21 mm on to the K201 pad edge. The clearance, 9.87 mm straight, is far over the signed 3.0 mm.

Commands, as run (from `hardware/tools`, the board file and tools of that commit):

- `route_length`: with `board_check` and `board_geometry` imported, the board read with `sexpr.parse_one`, `bc.layer_items(tree, bc.copper_layers(tree), bc.hole_footprints(tree))` giving the pads, `bg.Detours(bg.barrier_slots(tree))` giving the slots, then `d = bg.shape_distance(pad_c601_2.shape, pad_k201_a2.shape, 11)` and `bg.route_length(pad_c601_2.shape, pad_k201_a2.shape, slots, 10.0, d)`, which returned `(10.413618..., 1)`. The same run was repeated for this record on the board file now in the folder and gave the same figures.
- `kicad-cli pcb drc`: a copy of the board pruned to x 40 to 80 mm, y 66 to 103 mm (keeping K201, whose origin lies outside that box), beside the project file and a one-rule `.kicad_dru` file, `(rule "probe creepage 16" (condition "A.hasNetclass('Mains') && !B.hasNetclass('Mains')") (constraint creepage (min 16mm)))`, run as `kicad-cli pcb drc --format json --output out.json main-board.kicad_pcb` with KiCad 10.0.7. The 16 mm threshold is a probe that makes KiCad report the actual creepage of every pair under it; it reported this pair as `actual 10.4135 mm`. The same run with the U601 slot lines deleted reported creepage violations across the whole U601 pad area, so KiCad's creepage test is slot-aware.

Every other same-layer mains to low-voltage pair on the whole board: the nearest were 10.207 mm by surface path (a LINE1 track at F.Cu (25.5, 106.25) to (22.5, 106.25), against a ground pour, and the net NEUTRAL pour on In2 against the fiducial FID1 in plan view) and 10.209 mm (J101 pin 1 against the ground planes); then 10.292 mm (the pump snubber tracks against FID1). None is under the signed 10.0 mm by surface path, and the smallest straight-line distance on the board is 4.64 mm (U711 pin 4 to U602 pin 3, across a slot), over the signed 3.0 mm. This enumeration was the agent's own geometry over 563 mains-class copper items against 5,914 others, every pair under 10.6 mm straight (1,678 pairs); its tables were not committed.

The pre-order check does not report this pair because `layer_separation` judges only pairs whose copper shares no layer, and C601 pad 2 and K201 pin A2 share F.Cu; KiCad's own creepage rule judges same-layer pairs and reports nothing at 10.414 mm.

### Reconciling `route_length` with the layout reviewer's 9.96 mm

The layout review (findings 1.42 and 1.75) records 9.96 mm for this pair, stated there as measured with `board_geometry.route_length` and a corner search. That figure is not reproduced: `route_length` on the board file returns 10.4136 mm for this pair (the run above), and no mains to low-voltage pair on any layer of the board lies between 9.9 and 10.4 mm by surface path. Where 9.96 mm came from is not established; it is not the figure of this board's slot geometry. The 10.414 mm figure stands, by the three methods in the table. The words "Owner's measurement after the round" in those two findings are in a frozen round and mean this post-round verification by the agent, not a measurement by the owner; the layout review's closing prose carries the correction.

`route_length` does have a real defect at slot junctions, recorded in the layout plan's open items and carried by the maintenance solution `SOL-PRE-ORDER-CHECK-CREEPAGE-PATH-HOLDS-AT-SLOT-JUNCTIONS`: for pads of U601 against pad 3 of D205 it lets a path pass through the junction corner of the U601 bar and arm, at about (61.9, 90.3), and returns 9.179 mm (pad 10) and 9.773 mm (pad 9) where the paths round the arm's west end are 15.5 mm and 16.0 mm. The defect is over-conservative and hides no breach, and it does not touch the C601 and K201 pair, whose path round the arm's end does not pass the junction. The two short figures appear only in the creepage work's earlier baseline, never in the pre-order check's report.

## Critical-routing history check

`task hw:history -- --board hardware/sunbeam-em7000/main-board/main-board.kicad_pcb --routed`, run on 5 November 2026 at the head of this branch (the board file unchanged since `502f317e`), took about 26 seconds and exited 1 with `RESULT | FAIL | 71 of 94 checks failed` at first and `68 of 94` once a scratch-path edit to the layout plan's frozen sections (which broke three other checks) was reverted; the 68 are the standing fails. Of them, 25 are `pass 1 verdicts` lines and 43 are `pass 2 verdicts` lines, each reading "pass N's fail for <item> has no later verdict with the commit that put it right": a critical-routing checklist item judged a fail in a pass, with no later verdict on the item citing the commit that fixed it. The other 26 checks pass, among them the placement section, the four placement candidates, each pass's board-judged commit (critical copper all locked) and each pass as it stood before its router commit. The fails are the layout plan's recorded verdicts and are not re-judged here; the check reads 68 of 94 until each is fixed or the plan records a later verdict. An earlier run by an AI agent on `502f317e` recorded the same 68 (25 and 43).

## Board hygiene round at `502f317e`

An AI agent ran a hygiene round on the board and committed only `main-board.kicad_pcb` at `502f317e`: do-not-populate attributes on R522, R572 and R576, NT601's bill-of-materials attribute and LCSC field, and one dangling via (103.2, 98.6, net HEAT_C_LED_K) removed. The agent compared the result with the baseline board by s-expression diff: only those four footprints and that one via differ. Its connectivity, locked-copper and mains-copper results (no unconnected items, no pad without a net, every locked critical item present, locked and unchanged, no mains-copper finding) came from throwaway scripts and from `hw:copper-compare` against a record taken for the purpose; neither the scripts nor that record was committed, so those results are stated here as the agent's report and not as a figure a reader can rerun from this repository. The committed gate for the same board is the final pre-order check above.

## Known and not fixed

Three parity nits are new in this run: the D402 Description and U201 Datasheet field differences, and NT601's hidden reference. They are listed as known and not fixed. Fixing them changes a design file after the layout review's closing round and would need a third full check. They are recorded as one open item in `layout-plan.md`.
