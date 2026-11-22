# Varistor footprint correction: inspection record

Records the checks behind `SOL-MAIN-BOARD-VARISTOR-FOOTPRINT-MATCHES-ITS-STAGGERED-LEADS.C2` and `.C3`. The change is commit `0cc89e51` with the follow-ups `bcb756c2` and `3c1ed988`, judged against `54e5ba51` (the main it branched from).

## What changed

- Footprint `RV_Disc_14D471K_P7.5mm`: pad 1 at (0, 0), pad 2 moved from (7.5, 0) to (7.5, 3.0); drill 1.1 mm and pad 2.1 mm kept; body, courtyard and silk redrawn around the pair (17.0 by 6.2 mm).
- RV101: pad 1 (LINE) from (15.5, 62.6) to (15.5, 64.1), pad 2 (NEUTRAL) from (8.0, 62.6) to (8.0, 61.1), rotation 180 degrees as before. The body and courtyard stand where they stood, so no other part moved.
- The locked In2 `NEUTRAL pour In2 north` outline: its west strip reaches y 59.5 where it reached y 61.0, four vertices, so pad 2 stays inside the pour. The chain sources (`layout-chain/neutral_pour.py`, `chamfer_corners.json`) draw the same outline.
- The reference text of RV101 is centred over the body, and the library footprint carries the same text position.

## C2: the layout rule check and the courtyards

- The layout rule check run with `kicad-cli` on the board with refilled zones and the full creepage rules: 294 violations before the change and 294 after, 0 unconnected items both times, an identical set matched on type and items, none naming RV101.
- A second, independent run on the committed fills: 412 violations before and 412 after, 0 unconnected items, an identical set.
- Courtyard gaps of RV101: C101 0.50 mm, R630 0.94 mm, R631 1.14 mm, J106 7.6 mm; unchanged from before. No courtyard overlap.
- Renders of F.Cu with silk, F.Fab and courtyard, B.Cu and In2 over x 0 to 45 mm, y 50 to 100 mm, before and after, read by a reviewer: the body stands square to the board edges, the pads sit at the midpoint of the body, the silk clears both pads by 0.49 mm, only the RV101 block and the pour edge differ.

## C3: separation and creepage (millimetres, edge to edge)

The basis is `separation-basis.yaml`: 1.5 straight, 2.0 pad to pad, 2.6 creepage between mains nets; 3 and 10 to low-voltage copper.

| Pair | Before | After |
|---|---|---|
| RV101 pad 1 to pad 2, every layer | 5.400 | 5.978 |
| Pad 1 to the ZC_N1 track, F.Cu | 3.252 | 4.313 |
| Pad 1 to the In2 NEUTRAL pour | 2.75 | 2.75 |
| Pad 1 to the ENTRY NEUTRAL F.Cu zone | 10.55 | 9.10 |
| Pad 2 to the LINE B.Cu strip and F.Cu zone | 6.95 and 8.45 | 6.95 and 9.92 |
| The two pads to the nearest low-voltage copper | 36.96 | 38.08 |
| The added pour strip (x 1.5 to 11.5, y 59.5 to 61.0) to other-net copper on any layer | not applicable | nothing within 4 |
| F101 pad 2 to RV101 pad 1 (centres) | 37.3 | 36.4 |

- The mains-copper comparison of `locked_copper.py` from the before commit to the after commit reports three changed items (the pour zone and the two pads), none added, missing or unlocked; every mains item stays locked (169 segments, 73 vias, 25 zones).
- `task hw:verify` passes on all seven designs, and the board tests (`task hw:test:round`) pass: 125 modules, 3728 tests.
- The signed record of the entry-filter distance (`owner-sign-off.md`, S-75) is annotated with the move and the pour extension.

## Not changed

The lead offset is 3.0 mm, the assembler's footprint for the part. The Bourns drawing of the like 14 mm disc gives 3.2 mm typical and the fitted maker's drawing gives no figure; the 0.2 mm difference sits inside the clearance of a 1.1 mm hole for a 0.8 mm lead. The owner should check the part sits square on the first hand fit.
