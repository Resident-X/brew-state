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

The mains-spacing comparison with the earlier baseline rests on the creepage verification (`.stage0/creep-report.md`), run with the repo's own functions against a signed scratch copy of the head board. It found no breach of a signed mains-to-low-voltage figure, and the same standing mains-to-mains shortfalls as every earlier board (recorded in the layout plan's open items).

## Known and not fixed

Three parity nits are new in this run: the D402 Description and U201 Datasheet field differences, and NT601's hidden reference. They are listed as known and not fixed. Fixing them changes a design file after the layout review's closing round and would need a third full check. They are recorded as one open item in `layout-plan.md`.
