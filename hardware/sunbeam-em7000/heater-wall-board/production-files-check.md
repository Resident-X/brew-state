# Production-files check, heater wall board

**Status of this file:** the production-files check record of the heater wall board, written whole for the commit below; it supersedes the records judged at bd942f31 and at cf6735dd, which stay in the repository's history. The files exported for the order stay with the owner and are not committed.

**Board judged:** 478d3b05533e087e2a361d919ea488fc58f995f0 (the final committed board: the silk stroke widening of 8ee00b84, then copper passes 3 and 4 and the silk legend and label changes of the workmanship pass, all in the board file only; re-judge if a later commit changes the board, its footprints or its schematic)
**Tools:** kicad-cli 10.0.7; gerbonara 1.6.3; resvg 0.48.1 (README asks 0.47 or newer)
**Commands:** step 1: pcb export pos (csv, mm, both, exclude-dnp), production_files.py placement, sch export bom (group-by LCSC, exclude-dnp), pcb export gerbers (F.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,B.SilkS,Edge.Cuts), pcb export drill. Step 2: production_files.py render. Run 2026-11-20 from a detached worktree at 478d3b05, twice; the earlier set (bd942f31) was extracted first and is the comparison set.
**Preview:** not obtained. Bare-PCB order, no assembly: JLCPCB's assembled-board preview and placement preview do not exist for this order. Stand-in: the design's own assembly views and the footprint drawings at rotation 0, judged in the earlier draft; neither the placements nor the parts changed since (the placement file and the parts list are byte-identical to the bd942f31 set's). The placement file is not uploaded.

**Amended 2026-11-23, the assembler fits every part (owner decision of 2026-11-23; `assembler-fitting-record.md`).** The board file changed after the commit judged above, by attributes only: U911, U921, R911, R912, R921 and R922 lost `exclude_from_pos_files` and are `fitted_by: assembler`, so the placement file has 14 rows (H1 alone stays out, `fitted_by: none`) and the order is no longer bare-PCB. No copper, mask, drill, silk or outline changed (the layout rule check and the mains-copper compare are identical before and after, `assembler-fitting-record.md`), so the layer table below stands for the new commit. What this record said that no longer holds: the *Preview* line's "Bare-PCB order, no assembly" and "The placement file is not uploaded", and the note under *Parts* that the six surface-mount parts have no placement row. The six rows the change adds, as the placement step writes them from the committed design (U911 and U921 through the recorded overrides of `placement-overrides.yaml`, because the assembler's footprint for C899868 has its rows 9.20 mm apart against the board's 9.53 mm and every pad lands 0.165 mm off, past the 0.1 mm default; the four resistors fit by themselves):

| Part | Position (file) | Rotation (file) | Polarity or first pin | Catalogue part (record / parts list) | Note |
|---|---|---|---|---|---|
| R911 | 62, -38.5025 | 90 | none | C18002 / C18002 | fits the assembler's footprint by pad number within 0.1 mm |
| R912 | 62, -28.5025 | 90 | none | C18002 / C18002 | same |
| R921 | 51.5025, -72.5 | 180 | none | C18002 / C18002 | same |
| R922 | 38.6, -28.5025 | 90 | none | C18002 / C18002 | same |
| U911 | 60.64, -50.19 | 0 | pad 1 at board (58.10, 54.96) mm, the pin-1 dot's corner | C899868 / C899868 | override; 0.165 mm residual on every pad, across the rows |
| U921 | 60.64, -66.21 | 180 | pad 1 at board (63.18, 61.45) mm, the pin-1 dot's corner | C899868 / C899868 | override; 0.165 mm residual on every pad, across the rows |

The same 14 rows were uploaded to JLCPCB for the owner's test quote of 2026-11-23 (from a scratch copy of the board with the attribute removed); the operator read pin 1 of U911 and U921 in that preview at the board's pin 1. A full re-judgement of the per-part table against the assembler's preview of the order's own upload is owed at the order (`ordering-record.md`), as the method's step 3 asks.

### Parts
(8 rows = 8 placement rows. U911, U921, R911, R912, R921, R922 and H1 carry exclude_from_pos_files and are hand-fitted or a hole, so they have no placement row; they are checked under Catalogue part in the parts list only.)

| Part | Position (file / preview) | Rotation (file / preview) | Polarity or first pin (file / preview) | Catalogue part (record / parts list) | Verdict | Why |
|---|---|---|---|---|---|---|
| J911 | 44, -90.04 / n/a | 90 / n/a | none | C86469 / C86469 | matches | pads at (44,-87.5),(44,-92.58) in drill file; blade mounted vertically as assembly view |
| J921 | 32.6, -90.04 / n/a | 90 / n/a | none | C86469 / C86469 | matches | same, drills at x 32.6 |
| J941 | 24.5, -90.04 / n/a | 90 / n/a | none | C86469 / C86469 | matches | same, drills at x 24.5 |
| J931 | 63.18, -58.2 / n/a | 270 / n/a | pin 1 square pad at (63.18,-58.2) in B.Cu and masks; pins 2,3 run left / n/a | C2937625 / C2937625 | matches | drawing at 270 puts pin 2 left of pin 1, as drill and copper show |
| RV911 | 50.5, -40 / n/a | 180 / n/a | none | C49072860 / C49072860 | matches | drills (50.5,-40),(45.5,-37.5) |
| RV921 | 31, -42.5 / n/a | 180 / n/a | none | C49072860 / C49072860 | matches | drills (31,-42.5),(26,-40) |
| T911 | 54.66, -22.86 / n/a | 0 / n/a | pin 1 at origin, tab toward top edge / n/a | C10065 / C10065 | matches | drills 54.66, 57.2, 59.74; tab and silk bar side as assembly view |
| T921 | 30.06, -22.86 / n/a | 0 / n/a | same / n/a | C10065 / C10065 | matches | drills 30.06, 32.6, 35.14 |

Preview columns read n/a, not matches-against-preview, because no preview exists. Whoever approves payment must accept that, since the method's step 3 assumes assembly.

### Layers
| Layer | File | Compared with | Verdict | Why |
|---|---|---|---|---|
| F.Cu | heater-wall-board-F_Cu.gtl | render of the exported file, looked at, against the board's copper; differs from the bd942f31 file by the changes of copper passes 3 and 4 only (see comparison) | matches | pour, tracks and pads as the board has them, including the filled OUT_C wedge at the top right, the straightened U921 pin 4 track and the +5V_WB via; no missing, shifted or mirrored copper |
| B.Cu | heater-wall-board-B_Cu.gbl | same; differs from the bd942f31 file only by the +5V_WB via pad and its two tracks | matches | likewise; pin 1 square at x 63.18 |
| F.Mask | heater-wall-board-F_Mask.gts | render, looked at; identical to the bd942f31 file apart from the date lines | matches | openings at every pad, blade holes, M3 hole; the moved via has no opening on either mask (tented), as before |
| B.Mask | heater-wall-board-B_Mask.gbs | render, looked at; identical to the bd942f31 file apart from the date lines | matches | likewise |
| F.SilkS | heater-wall-board-F_Silkscreen.gto | render, looked at; differs from the bd942f31 file (reference labels now vertical, blade legends OUT_C, OUT_S, RET and COFFEE, STEAM, RETURN rotated, maker block moved) | matches | text reads correctly and in place (warning triangle and mains notice, J931 pin list, part references, BREW STATE title and maker block, STAIRCASE mark, outlines of the blades, varistors, opto-triacs and header; vertical labels read upward); no stroke under 0.15 mm (aperture table below); no paste layer |
| B.SilkS | heater-wall-board-B_Silkscreen.gbo | render, looked at; byte-identical to the bd942f31 file apart from the date lines | matches | only JLCJLCJLCJLC, reads backward in the top-down frame, correct for a back-side mark; one aperture, 0.150 mm |
| Edge.Cuts | heater-wall-board-Edge_Cuts.gm1 | render, outline numbers; byte-identical to the bd942f31 file apart from the date lines | matches | gerber bounding box 19.95..65.05 by -96.05..-20.95 mm, the 0.1 mm outline line included, so 45.0 by 75.0 on the line centres (x 20..65, y 21..96); two notches 1.5 mm wide with 0.75 mm round ends, open to the right edge |
| drill | heater-wall-board.drl | render; board's own pads and vias; differs from the bd942f31 file in one hole coordinate (the via) | matches | 21 holes: 0.3 x1, 0.6 x4, 1.0 x3, 1.1 x6, 1.4 x6 (plated), 3.2 x1 (non-plated); the board holds 20 drilled pads and 1 via, 21; the via is at (58.1, -56.65) in the file, in the Gerber frame, 0.15 mm from its place at bd942f31 |

### Silkscreen strokes
Aperture table, read from the exported files (every aperture is a circle; every one draws only lines, arcs and region outlines, none is flashed):

| File | Aperture | Diameter | Draws |
|---|---|---|---|
| F_Silkscreen.gto | D10 | 0.200 mm | 377 strokes |
| | D11 | 0.150 mm | 1653 strokes, plus the outlines of 5 regions |
| | D12 | 0.250 mm | 3 strokes |
| | D13 | 0.300 mm | 8 strokes |
| | D14 | 0.200001 mm | 6 strokes |
| B_Silkscreen.gbo | D10 | 0.150 mm | 88 strokes |

The aperture tables and stroke counts equal those of the bd942f31 set: the label and legend changes moved and turned strokes without adding a size. The smallest aperture in either file is 0.150 mm, the maker's minimum. The board's text is 1.0 mm high at 0.15 mm stroke and 1.5 mm high at 0.2 mm stroke (read from the board with pcbnew); its drawn silk lines are 0.15 and 0.25 mm.

### Comparison with the earlier set (exported at bd942f31, extracted from the order folder first)
Byte-identical apart from the creation-date lines: Edge_Cuts, F_Mask, B_Mask, B_Silkscreen, the job file, the placement file and the parts list (the last two outright). Different, and each explained:
- F_Cu: the +5V_WB via pad flash and the track that ends on it moved from (58.1, -56.8) to (58.1, -56.65); one F.Cu track end moved (56.575 to 55.05 at y -72.5, the U921 pin 4 track); the OUT_C front zone's outline changed (the wedge filled and the band edge straightened). These are copper passes 3 and 4.
- B_Cu: the same via pad flash and the two B.Cu tracks that end on it (12 diff lines, all the via and those tracks).
- drill: one line, T1 (the 0.3 mm via), Y -56.8 to Y -56.65; the other 20 holes unchanged; count 21.
- F_Silkscreen: reference labels vertical, blade legends rotated, maker block moved.
The masks are identical because the via is tented and the copper changes lie under the mask, not at a pad. The set is reproducible: a second export from the same commit matched the first file by file, ignoring only the date lines (the placement file, position export and parts list matched outright).

### Against the maker's limits (docs/board-manufacturer-jlcpcb.md, 2 layers, 1 oz)
| Figure | Measured | Limit | Result |
|---|---|---|---|
| Silkscreen line width | 0.150 mm smallest aperture | 0.15 mm | meets, no margin |
| Silkscreen text height | 1.0 mm smallest, 1.5 mm next | 1.0 mm | meets, no margin for the 1.0 mm text |
| Non-plated slots (the two outline notches) | 1.5 mm wide | 1.0 mm | meets; round ends, so no rectangular corner |
| Smallest drill | 0.3 mm (one via) | 0.15 mm range; 0.5 mm recommended plated hole | meets the range; below the recommended size, as in the earlier judgement |
| Non-plated hole | 3.2 mm | 0.5 mm | meets |
| Pad hole to pad hole, edge to edge | 1.44 mm smallest between pads (T911 and T921, pin to pin); the +5V_WB via to J931 pin 3 hole is 0.90 mm | 0.45 mm pad to pad; 0.20 mm via to via | meets |
| Annular ring, plated | 0.20 mm smallest (T911 and T921, 1.5 mm pad on 1.1 mm hole; the via 0.7 mm on 0.3 mm is 0.20 mm too) | 0.18 mm absolute minimum, 0.25 mm recommended | meets the minimum; under the recommended figure |
| Copper to routed edge or slot | 0.97 mm smallest (J931 pin 1 pad), read from KiCad's own edge-clearance check run at a 1.3 mm probe on the committed board, zones included | 0.20 mm | meets |
| Track width | 0.2 mm smallest (signal), 0.5 and 2.1 mm others | 0.10 mm | meets |
| Copper spacing, different nets | 0.60 mm smallest (J931 pin 2 to the +5V_WB back track), below the pad pitch pairs listed in the next paragraph | 0.10 mm track and space; 0.15 mm SMD pad to pad | meets |
| Via hole to track | the +5V_WB via sits 0.60 mm or more from different-net copper | 0.20 mm | meets |

The ring, hole-spacing, text-height and track-width figures are read from the committed board with KiCad's Python (pcbnew), not from the Gerber files; the edge and copper-spacing figures come from kicad-cli DRC runs on a scratch copy with probe rules (edge clearance 1.3 mm, clearance 3 mm) that list every pair under the probe.
KiCad's own DRC on the committed board reports 12 clearance violations and nothing else (no silkscreen, text, edge, hole or unconnected item). All 12 are part-pad pairs at 1.04 mm against the netclass's 1.5 mm (T911 and T921 pin pairs, U911 and U921 pin 5 against pins 4 and 6), the pairs the board's own separation-basis record carries as accepted. None involves the copper changed by passes 3 and 4.

### Findings
1. None blocks the order on the files. Silkscreen strokes are no longer a shortfall.
2. Observations carried from the earlier draft, unchanged: annular ring 0.20 mm (under the 0.25 mm recommendation, over the 0.18 mm minimum); the preview is absent because the order is bare-PCB. The DRC pairs are the accepted 1.04 mm pad pairs listed above.
3. The maker's checker may flag the 0.15 mm silkscreen, being exactly at its minimum, the 1.0 mm text, exactly at its minimum, and the 0.3 mm via under the 0.5 mm recommended plated hole size.
