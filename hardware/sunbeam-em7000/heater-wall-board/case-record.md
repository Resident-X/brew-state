# Case record, heater wall board

**What this records.** The printed case that holds the heater wall board against the machine's wall, the flat spreader plate it is screwed to, and what each of the case's twenty-one criteria asks to be stated or shown: the plate's clearance and creepage, the fit inside the plate's former outline, the plate, the lid and its removal, the fixings, what holds the board, the slot mouths, the backing under the blades, the earth bond, the order of fitting, the appearance, the printing, the openings, the seating range, the material, the receptacle boots, the installed orientation, the low-voltage cable's exit and the fit of the exported files to the board's own model. It replaces the earlier ear-and-bracket form for the plate's drawing, its spacers and its mounts (see *The plate*).

**Where the figures come from.** The model, the check program and the slicer runs live in `case/`. The figures below are read from `case/params.yaml` (every parameter there carries its source), `case/out/check.json` (the check at the nominal seating: 51 of 51 checks pass, with one finding reported and not counted), `case/out/check-range.json` (the same checks at the nominal seating and at all 64 extremes of the seating range: 52 of 52 pass, with two findings reported and not counted), `case/out/check-height-range.json` (the same checks, 52 of 52 pass, with the case rebuilt at the least and the greatest plate height, each at the nominal gap and at its two extremes) and `case/slice/*.json` (the slicer's summaries). `case/tests/test_case_record.py` compares the figures quoted here with those files and with a fresh build of the model, so the record cannot drift from them unnoticed.

**How each criterion is checked.** Twenty criteria of this case are verified by inspection: a stated check of the delivered model, drawings and this record against each clause. The twenty-first (C21, the exported case against the board's own model) is verified by test: `case/fit.py` reads the exported files and the board's own model and `case/tests/test_case_fit.py` holds it. Each section below is headed with its criterion's number and ends with that check, clause by clause, naming the check of `case/check.py`, the result of `case/fit.py` or the file that shows it. A clause the model does not show is said to be not shown.

**Grades used.** *Checked by model*: a figure the case model and its check program compute from the board's layout file, the package figures in `params.yaml` and the signed separation basis (`separation-basis.yaml`). *Assumed*: a figure no maker document gives, stated with its basis. *Unconfirmed*: a figure the owner measures on the delivered parts or at assembly. *Design owner's judgement*: a grading made by the designer of the case. *Judge's verdict*: the appearance verdicts, made by a judge who did not design the case. Nothing has been printed yet; every statement about printing is by slicer and geometry.

**Frame.** `u` runs across the board (0 to 45 mm), `v` away from the board's plate-side edge (0 to 75 mm at the blade end), `z` up from the board's component face, the board occupying z -1.6 to 0. Millimetres throughout. Installed, `+z` points down (see *Installed orientation*). This working frame is left-handed and never leaves the model: every exported file and every render is in the right-handed physical frame `X = u`, `Y = -v`, `Z = z` (see *The exported case against the board's own model*).

## The case

A tray, a lid and the spreader plate they are fixed to; no film or other loose part. The tray is fixed to the spreader plate by two screws, one in each pilaster, from the plate's back face into a heat-set insert in the pilaster, and holds the board by its one mounting hole H1 and by printed pillars, a backing rib under the three blades and a hold-down finger, so taking the lid off leaves the board held. The plate is a standard flat aluminium bar whose lower edge stands 6.0 mm above the board's component face, so no plate metal faces the board's edge; the tray's printed end wall fills the volume under it, up to a ledge on which the bar's lower edge rests. The lid closes the cavity on the component side, is held at the plate end by two toes under hooks on the pilasters and at the far end by one M3 x 10 countersunk screw, and holds nothing.

The outline is a soft pebble in plan, square at the plate end and rounded at the far end (far-corner radius 11.5 mm), with a 1.6 mm chamfer round the lid's face and round the tray's top. The lid's rim, a lip that drops outside the tray's walls, runs unbroken round both far corners; it has one window 8.7 mm wide at the far end, centred under the lid screw, where the tray's square tab (8.0 mm wide) stands flush with it, and one gate on the right side where the low-voltage cable leaves (see *The low-voltage cable's exit*). The lid face carries eight streamline grooves that part round the logo and the blade bays, four of them cut through as the air inlets, the logo, the three blade bays and a blind block of eight bars beside the bays. The tray's long walls carry one even row of outlet slits each. The tray's outer top face carries the logo and no opening.

## The plate's clearance and creepage over the board's tolerances (C1)

The drawing (`case/out/case-drawings.svg`) and the model (checks `c1.*`) carry the form the owner agreed on 2026-11-27 and `owner-sign-off.md` W-19 records: **the case holds the spreader plate's lower edge 6.0 mm above the board's component face**, the fallback this criterion offers, which restores the lift of W-9 1c. **No barrier is used**: the case carries no insulating film, coating, shim or other loose part, and no step of its assembly is needed for clearance or creepage to hold. The earlier bought-film form is gone from the model, the parameters, the exports and the checks.

- The plate is a standard flat aluminium bar, 85.0 mm long, 20 mm wide (its height installed) and 5.0 mm thick (*The plate*): its lower edge at z 6.000 and its upper edge at z 26.000 above the board's component face, 3.5 mm above the lid's top (z 22.55). The lower edge is the top of a ledge on the tray's end wall on which the bar rests, so it is fixed in the tray's own frame, 12.6 mm above the floor's underside (63 layers of 0.2 mm), and not in the board's; no plate metal faces the board edge, the pads or the lower leads. The case holds at any plate height from 16.8 to 27.5 mm (*The case inside the plate's former outline, and the wall opening*).
- Gap between the board edge and the plate, over three tolerances: the maker's tab-face-to-lead-centre range less the lead centre's fixed 1.86 mm from the board edge, 0.785 to 1.210 mm (ST DS2114 Rev 11 Table 6 p.9: c2 2.40 to 2.72 plus half of c1 0.49 to 0.70, `seating.tab_face_to_lead_centre_mm`); the board outline's routing tolerance, 0.2 mm at the fabricator's regular tier (0.1 mm at its precision tier; `docs/board-manufacturer-jlcpcb.md`, *Board outline tolerance*, published and unverified, `seating.outline_routing_mm`); and the play of a lead in its 1.1 mm drilled hole, 0.305 mm to either side at the thinnest lead (the 1.1 mm hole less c1 0.49, halved) and 0.20 mm at the thickest, which the assembler's soldering freezes (`seating.lead_play_mm`, an assumption: no assembler figure exists; the extreme is the lead against one side of its hole). The tolerances move the gap alike: 0.785 - 0.2 - 0.305 = 0.280 mm and 1.210 + 0.2 + 0.305 = 1.715 mm, 1.000 mm nominal. Each of the three figures is unconfirmed: the owner measures the delivered board. Measuring the delivered boards' real lead play and changing the board outline are out of scope.
- The plate's lower edge over two further tolerances, which move the edge and not the gap. The ledge's print allowance is 0.2 mm, one layer of the printer's 0.2 mm layer height (`plate.ledge_print_allowance_mm`, a design figure: the printed ledge may stand one layer under its drawn height and not above it). The board's thickness tolerance is 1.6 mm plus or minus 10 percent, 0.16 mm (`docs/board-manufacturer-jlcpcb.md`, *Board thickness tolerance*, published and unverified; a thicker board lifts the component face off the tray, so the fixed ledge stands that much lower against it). Each lowers the edge by up to its figure and they move it the same distance in the same direction, so the model takes them as one axis, `seating.plate_edge_offset_mm`, at 0 and -0.36 mm: the edge stands at least 6.0 - 0.2 - 0.16 = 5.64 mm above the face, against the 5.55 mm the leads need. A higher edge, from a thinner board, only moves the plate away from the pads and the leads; the tray screws, being on the tray like the ledge, move with it, so their distance to the bar's edge does not change, and the one distance it narrows, the tab hole's to the bar's lower edge, has 6.3 mm to spare (tab hole 15.3 mm at the least, less the 2.8 mm screw head radius, less the 6.16 mm edge). Only the adverse direction is taken. The model holds the tray screws at their stated height while the edge moves, which only widens their distance to a lower edge. Both figures are assumptions and unconfirmed: the owner measures the delivered board and the printed tray.
- Why the earlier form could not stand: the straight air from a pad edge to the plate is the pad-edge-to-board-edge distance of 1.010 mm plus the gap, which falls below the signed 1.5 mm wherever the gap falls below 0.49 mm, and a barrier is not credited against a clearance, which is an air distance; a 0.25 mm film could not be relied on to fit a gap that can be 0.28 mm.
- Why 6.0 mm: the bare lead's rear face stands at least 2.40 mm off the plate plane (c2 2.40 at its minimum) and its metal rises to the body underside, at most 4.55 mm (3.75 mm nominal), so 2.6 mm of straight air needs a lower edge at or above 4.55 + sqrt(2.6^2 - 2.40^2) = 5.550 mm; 6.0 mm clears it by 0.450 mm, and the lowest edge the two tolerances above leave, 5.64 mm, by 0.090 mm (a bare lead then stands 2.636 mm from the plate at the body maximum). At the nominal seating a bare lead stands 3.450 mm from the plate and at the body maximum 2.804 mm (the printed case solution's statement that its 6.0 mm fallback leaves the leads 3.4 mm from the plate is the nominal figure; at the body maximum the figure is 2.804 mm).
- Clearance and creepage are proved as the straight-line distance, in three dimensions and both copper layers, from every Mains-family pad edge, track, via and pour and from every bare lead to the plate solid and to the machine wall's plane: no creepage path is shorter than the straight line, so the one figure proves both. Nominal: 6.328 mm from the nearest pad edge (pad 1 of T911 on F.Cu) and 3.450 mm from a bare lead, 7.010 mm from the wall plane, against the basis's 2.6 mm creepage and 1.5 mm clearance. Over all 64 extremes of the six tolerances of *Seating range* the least is 5.819 mm from any Mains copper and 2.636 mm from a bare lead.
- The tray's printed end wall fills the volume the plate leaves, across the tray's full outer width at the plate end (u -8.50 to 56.00), from the floor's underside (z -6.60) up to a ledge at the plate's lower edge (z 6.00, 12.6 mm above the floor's underside): the bar's lower edge rests on the ledge, so the plate cannot sit lower than the ledge and the clearance is geometry and not drilling accuracy. The ledge is credited with no creepage and no clearance. Its board-side face stands 0.2 mm behind the plate plane over the cavity's width (`plate.end_wall_board_recess_mm`, a parameter apart from the ledge's height) and its back face stands 0.5 mm in front of the machine wall's plane, so only the plate touches the wall; the ledge's contact with the bar spans v -5.50 to -1.20, 4.3 mm of the bar's 5.0 mm thickness. Its sides and its back face carry the tray's own bottom chamfer, so the body's chamfer runs on round the wall. It is unfilled printed plastic. It stands 1.200 mm from the board and 2.210 mm from Mains copper at the nominal seating and 0.480 mm and 1.690 mm at the narrowest gap.
- W-10's barrier in the tray is not built (`owner-sign-off.md`, keeper's note to W-10): a printed wall of 0.8 mm cannot be guaranteed to fit a gap that can be 0.280 mm, and a film cannot be relied on to fit it.

**Check against the criterion.**

| Clause | Shown by | Result |
|---|---|---|
| the case's fixed base, never the lid, carries an insulating barrier wherever the basic creepage to the plate would not otherwise hold | not used: no barrier is credited, the plate's lower edge is raised instead; `c1.no_loose_part_or_coating` shows no film, coating, shim or loose part | held without a barrier |
| or the case holds the plate's lower edge 6.0 mm above the board, with the owner's decision | `c1.plate_lower_edge_raised` (z 6.000 against the 6.0 mm figure and the 5.550 mm the leads need); `owner-sign-off.md` W-19 | held; the owner's decision is W-19, signed on his behalf |
| the gap is stated over the maker's range, the outline routing tolerance and the leads' play, each with its source or marked as an assumption | `c1.gap_over_tolerances`; the second bullet; `case/params.yaml` | stated, each unconfirmed |
| clearance and creepage from every pad edge and bare lead to the plate hold the signed 1.5 mm and 2.6 mm | `c1.clearance_pad_to_plate`, `c1.creepage_pad_to_plate`, `c1.clearance_bare_lead_to_plate`, `c1.creepage_bare_lead_to_plate`, `c1.creepage_all_mains_copper`, `c1.straight_to_wall_plane` at the nominal seating; `c16.seating_range` at every extreme, `c16.plate_height_range` at both ends of the height range | held |
| the end wall stands clear of the board; the bar's lower edge is set by the ledge, and a plate below it cannot be seated | `c1.end_wall_stands_off`, `c1.plate_seated_on_ledge` (0.000 mm3 shared at the ledge, 12.9 mm3 at 0.05 mm below it, 3045.6 mm3 at the former position, z -7.025), `c1.plate_clear_of_end_wall` | held |
| the barrier is a creepage barrier only | no barrier is used | not applicable |

## The case inside the plate's former outline, and the wall opening (C2)

The case is 64.52 mm wide at the pilasters, 29.15 mm tall and 89.50 mm long (case extent u -8.71 to 56.21, z -6.60 to 22.55, v -5.50 to 84.00; the end wall's back face is v -5.50). The plate's former outline is u -18.75 to 66.25, z -7.025 to 22.975 (the 85.0 x 30.0 mm plate the case is drawn inside), kept as its own figure (`plate.former_height_mm`): the case lies inside it with 0.425 mm least margin (0.25 needed): 10.04 mm at each end and 0.425 mm above and below. The board, the blades and the parts lie inside it too, and so does the cable's exit (u 50.0). The plate itself is the 20 mm bar standing at the ledge (z 6.000 to 26.000), and its height does not move the former outline.

Only the plate touches the wall. The end wall's back face stands 0.500 mm in front of the machine wall's plane (v -6.000); no printed part comes within 0.5 mm of it.

The opening in the machine's plastic wall covers the plate and the tray's end wall together plus 1.5 mm each side (`plate.wall_opening_clearance_mm`): u -20.25 to 67.75 and z -8.10 to 27.50 at the 20 mm bar, 88.0 x 35.6 mm, and nothing else: the case, the blades and the harness all sit in the cavity behind it. It lies within the unit's opening in the plastic wall, z -10.0 to 35.0 about the component face (`docs/sunbeam-em7000/controller-board-division.md`, D11, accepted as preliminary by the owner and revisited when he cuts and measures; `plate.unit_opening_bottom_z_mm` and `plate.unit_opening_top_z_mm`), with 1.90 mm to spare below and 7.50 mm above. D11 states the opening's length as 88.0 mm, the 85 mm bar and the clearance each side, and says that its span along the wall is set by the case, which the model's opening follows; the model checks the opening's height against the unit's opening. Cutting the wall is out of scope.

**The plate-height range.** The case holds at any plate height from the least that keeps the case inside the plate's footprint to the greatest the unit's opening admits, with the lower edge unchanged at z 6.0. **The least is 16.8 mm** (`plate.height_min_mm`): the lid's top, z 22.55, plus the 0.25 mm margin (`plate.min_margin_mm`), less the 6.0 mm lower edge. **The greatest is 27.5 mm** (`plate.height_max_mm`): the opening's top, 35.0, less the 1.5 mm wall-opening clearance, less the 6.0 mm lower edge. The standard bar widths between them are **20 mm and 25 mm**; the case takes the 20 mm bar. `c2.plate_covers_case_top` fails a plate shorter than the least and `c2.wall_opening_within_unit_opening` a plate taller than the greatest (negative controls: 16.3 and 28.0 mm). `c16.plate_height_range` rebuilds the case at 16.8 mm and at 27.5 mm, each at the nominal gap and at the narrowest and the widest, six builds, and every check passes at each (`case/out/check-height-range.json`).

**Check against the criterion.**

| Clause | Shown by | Result |
|---|---|---|
| the case lies within the plate's former 80 by 30 mm outline in both directions across the wall | `c2.case_within_former_outline`, margins 10.04, 10.04, 0.425 and 0.425 mm | held |
| the opening covers the plate and the end wall plus the stated clearance each side and lies within the unit's opening in the plastic wall | `c2.wall_opening_stated`, 1.5 mm per side; `c2.wall_opening_within_unit_opening`, z -8.10 to 27.50 within -10.0 to 35.0; the drawing's end elevation | stated, held |
| the case's checks hold at the least and the greatest plate height, and the record states both heights and the standard bar sizes between them | `c2.plate_covers_case_top`; `c16.plate_height_range` (16.8 and 27.5 mm); the paragraph *The plate-height range* | held; 16.8 and 27.5 mm, 20 and 25 mm stock |
| no printed part comes within 0.5 mm of the machine wall's plane, so only the plate touches the wall | `c2.only_plate_touches_wall`, 0.500 mm | held |
| no larger opening is needed for the case, the blades or the harness | `c2.case_within_former_outline` (parts inside the outline), cable exit at u 50.0 inside the opening | held |

## The plate's length and the fixings in it (C3)

The plate is 85.0 mm long; the case is 64.52 mm wide at the pilasters; each end carries a 10.0 mm bolt zone holding one M4 bolt, with a 9.0 mm washer, at the plate's mid-height (z 16.00, 10.0 mm above the bar's lower edge). Length arithmetic: 64.52 + 2 x 10.0 = 84.52 <= 85.0 (margin 0.48 mm). The bolt zones stay 10.0 mm at each end, so the bar lengthens by exactly what the pilasters widened the case and the bolts stand where the zones put them. The plate's size is provisional until the owner cuts and measures the wall; the criterion holds at the figure then recorded.

**The tray screws and the wall bolts fit the narrower plate.** The two tray screws (one in each pilaster) stand at z 11.65 above the board face, 5.65 mm above the bar's lower edge: an insert hole at 19.5 mm would cut the lid toe's pocket (z 16.5 to 21.0) and break out of the 20.5 mm pilaster top. Each countersink (6.3 mm across) keeps at least 2.500 mm inside the plate's lower edge (z 11.65 - 3.15 = 8.50 against 6.0), the design figure `plate.screw_edge_distance_mm` being 0.5 mm, and its insert hole and head stand at least 2.255 mm from the pocket (needs 0.4) with the hole's top at z 14.48, under the pilaster's top by 6.02 mm (the wall round the hole is at least 2.0 mm). Each wall bolt's washer stands 5.50 mm inside the plate's height (z 11.50 to 20.50 in the plate's 6.0 to 26.0) and 0.55 mm clear of the case; at the least plate height, 16.8 mm, it stands 3.90 mm inside it.

**The insert and its hole.** One M3 heat-set insert, 5.7 mm long, is melted into each pilaster's end face in a hole 4.01 mm across and 6.7 mm deep (the maker's lower hole figure, with 1.0 mm under the insert for the plastic the iron displaces; printed as a tear-drop, because the hole lies in the layer plane), with at least 2.0 mm of printed wall round it (`case.insert_wall_min_mm`; least 2.000 mm to the outer face and to the cavity, 2.251 mm to the lid toe's pocket and 6.02 mm to the pilaster's top). A short M3 x 10 countersunk screw goes through the 5.0 mm bar and threads 5.0 mm into the insert, inside the insert's 5.7 mm and 1.7 mm short of the hole's floor, so the head seats in its countersink and the bar is clamped to the tray (`c3.tray_insert_seat`). **The insert maker's figures.** The hole and its depth are those of PEM (Penn Engineering) for its Type IUT M3 heat-stake insert in ABS (the IUTA, IUTB and IUTC straight-wall series and the flanged IUTF series state the same): hole 4.01 mm (+0.08), so 4.01 to 4.09 mm (`case.insert_hole_dia_mm` with its `min` and `max`), and minimum hole depth 6.5 mm (`case.insert_hole_depth_mm`, `min`); the model holds the hole at the lower figure, 4.01 mm, and the depth at 6.7 mm, and `c3.tray_insert_seat` refuses a hole outside 4.01 to 4.09 mm and a depth under 6.5 mm. PEM's Type IS symmetrical series states 3.99 mm (+0.08) and is not used. The figures were read on 2026-11-28 as web-search result text only: pemnet.com refuses automated fetch and no PDF was found, so no table was read directly (https://www.pemnet.com/products/product-finder/iutc-m3/, also `iuta-m3`, `iutb-m3` and `iutfc-m3`, and https://catalog.pemnet.com/item/ht-wall-thru-threaded-inserts-types-iuta-iutb-iutc/-staking-insert-straight-wall-thru-threaded-metric/iuta-m3), and the owner confirms it against the part he buys. The insert's length, 5.7 mm, is the design's own figure: PEM's Type IUT length was not captured, so 5.7 mm is the design's own figure and not PEM's, and the owner confirms it against the part he buys. The screw is the ISO 7046 M3 countersunk screw: its head is 5.5 mm across as made and its countersink in the bar's back face 6.3 mm across; the two tray screws stand 56.51 mm apart and at least 6.8 mm apart is required, the countersink and a 0.5 mm web of bar (`c3.tray_screw_heads_apart`).

**Check against the criterion.**

| Clause | Shown by | Result |
|---|---|---|
| the plate's length is not less than the case's outer width plus a bolt zone at each end, with the arithmetic shown | `c3.plate_length`; the plate drawing `case/out/plate-drawing.svg` | held, margin 0.50 mm |
| each tray screw's insert hole and head stand clear of the lid-toe pocket and keep the edge distance from the plate's edges; each wall bolt's washer fits within the plate | `c3.tray_screws_fit_plate`, `c3.wall_bolts_outside_case` | held |
| provisional until the wall is cut and measured | owner list, item 4 | stated |

## Lid removal (C4)

With the plate, case and board already placed at the wall opening, the lid is fitted and removed without removing the case or the plate. The sequence and the installed figures are in *Installed orientation*. The model sweeps the lid through 41 poses, tilted 3 degrees about its plate-end toe line and drawn out to a 90 mm slide, against the tray, plate, board, parts, blades and the frame of the wall opening (the plate outline plus clearance, framed 10.0 mm deep). The lid's clearances, by exact distance between the solids:

| Pose | Least clearance | Nearest |
|---|---|---|
| fitted | 0.187 mm | tray (0.400 mm to the plate, 4.950 mm to the opening frame) |
| whole sweep | 0.178 mm | tray, at a tilt of 0.9 degrees |

The check's floor is 0.05 mm. The lid and tray are swept without their vents, grooves and engraving, so they hold more material than the real parts and every distance is the same or smaller. The physical demonstration on a printed case belongs to the delivered-board leaf.

**Check against the criterion.**

| Clause | Shown by | Result |
|---|---|---|
| the lid is fitted and removed by sliding or angling with the plate, case and board placed at the opening | `c4.lid_sweep` | held |
| the swept path is clear of the opening, the plate and the case | `c4.lid_sweep`, least 0.178 mm | held |
| without removing the case or the plate | the sweep holds them in place | held |
| the model's lid clearances are stated | the table above | stated |

## Lid fixings (C5)

The lid has one screw, M3 x 10 countersunk, at u 23.75, v 80.50, at the far end: 81.5 mm from the wall plane (at least 20 is asked) and 68.8 mm from the opening frame, so it is not against the wall opening. The driver's approach is straight along the screw's axis from below the installed case, a 5.5 mm shaft with nothing in its way, and the head sits flush with the lid face. The plate end is retained without screws: two toes of the lid tuck under 45 degree hooks on the tray's pilasters (at u -6.8 and 54.3). Lifting the lid straight up 1.0 mm at the plate end drives each toe's barb into its hook (0.74 mm3 of interference each in the model), so the plate end is held.

**Check against the criterion.**

| Clause | Shown by | Result |
|---|---|---|
| every lid screw is where a driver reaches it with the case installed | `c5.lid_screw_reached`, `c5.fixings_reached_installed` | held |
| none right against the wall opening | 81.5 mm from the wall plane, 68.8 mm from the frame | held |
| the drawing states the driver's approach | `case-drawings.svg`: "lid screw, driven from +z" | stated |
| retention without screws is stated | `c5.retention_stated`, `c5.toes_hold_plate_end` | stated |

## What holds the board (C6)

The board is held by the tray alone: eleven printed pillars and the H1 boss carry its underside (13 seat points of the tray's own solid meet the underside plane within 0.02 mm, and their contact polygon holds the board's centroid), an M3 x 5 pan-head thread-forming screw through H1 (u 41.5, v 71.5) into a 2.6 mm pilot fixes it, the backing rib under the three blades carries the push-on load, a hold-down finger on the left wall stands its hook 0.85 mm over the board's edge at v 58.0, and locating ribs on the left and far walls locate it. The lid's underside is 16.9 mm from the board and touches nothing of it, so taking the lid off leaves the board held. The case is printable at home (see *Printing*) and fixed with ordinary screws.

**Check against the criterion.**

| Clause | Shown by | Result |
|---|---|---|
| held securely and stably by H1 and by a ledge, fingers or ribs of the tray | `c6.board_seat`, `c6.hold_down_and_h1` | held |
| nothing of the lid holds it | lid 16.9 mm from the board | held |
| the drawing states what holds the board | `case-drawings.svg`: "Board is held by: ..." | stated |
| printable at home, ordinary screws | *Printing* | held |

## Screws and mains copper (C7)

Each screw's centre and its least distance from mains copper in the board's design, on both copper layers, each screw swept as spheres of its shaft or head radius along its axis and each insert's hole swept with its 2.0 mm of wall (the insert is measured from the hole's axis out to the wall's outer face, whatever the screw is made of; the sphere is a model of the metal, exact toward the board's copper while the axis stands above the copper's higher plane by at least the tear-drop roof, the hole's radius times sqrt 2, plus the wall, 4.84 mm, which `copper_below_axis_mm` states for each insert, the roof itself standing above the axis, away from the board):

| Screw | Centre (u, v, z) | Least distance | Nearest mains copper | Figure it keeps |
|---|---|---|---|---|
| H1 screw | 41.50, 71.50, -1.30 | 11.46 mm | a track of the steam output, top copper | 2.6 mm |
| tab screw T921 | 12.60, -0.98, 16.50 | 13.70 mm | pad 2 of T921, top copper | 1.5 mm |
| tab screw T911 | 37.20, -0.98, 16.50 | 13.70 mm | pad 2 of T911, top copper | 1.5 mm |
| tray screw (u -4.505, z 11.65) | -4.51, -1.00, 11.65 | 11.62 mm | return zone, top copper | 3.0 mm |
| insert (u -4.505, z 11.65) | -4.51, 2.35, 11.65 | 9.10 mm | return zone, top copper | 2.6 mm |
| tray screw (u 52.005, z 11.65) | 52.01, -1.00, 11.65 | 13.40 mm | pad 2 of R912, top copper | 3.0 mm |
| insert (u 52.005, z 11.65) | 52.01, 2.35, 11.65 | 10.80 mm | pad 2 of R912, top copper | 2.6 mm |
| lid screw | 23.75, 80.50, 17.55 | 13.07 mm | coffee output zone, top copper | 10.0 mm |

The least margin over its figure is 3.07 mm, at the lid screw. H1 is the one screw that meets the board: its pad stands 12.65 mm (top) and 13.35 mm (bottom) and its courtyard 10.80 mm and 11.50 mm from mains copper, against 2.6 mm, the larger of the basis's clearance (1.5 mm) and creepage (2.6 mm). The tray screws and the lid screw do not meet the board and keep larger design figures, and each insert's hole and its wall keep the larger of the signed clearance and creepage, 2.6 mm, from mains copper, 9.10 mm at the nearest, so the distance holds whatever the screw is made of (the tear-drop's roof, which a sphere of the hole's radius and wall does not reach, stands above the axis, away from the board's copper, and each insert's axis stands 11.65 mm above the higher copper plane against the 4.84 mm that keeps it so); the tab screws stand in the earthed plate 16.5 mm above the board. The posts that meet the board are the tray's printed pillars, which are plastic. No safety property depends on a screw's material.

**Check against the criterion.**

| Clause | Shown by | Result |
|---|---|---|
| each screw or post that meets the board, and H1, keeps its pad and courtyard at the larger of the signed clearance and creepage from mains copper, on every layer | `c7.h1_pad_and_courtyard`, least 10.80 mm against 2.6 mm; `c7.screws_clear_of_mains_copper` | held |
| the drawing or model states each screw's centre and its distance from the nearest mains copper | the table above, from `c7.screws_clear_of_mains_copper` | stated |

## The slot mouths (C8)

No solid of the tray, the lid or a rib comes within 2.0 mm of either slot's open area, its mouth at the board's right edge (u 45) included. Slot A (board (51.0, 49.44) to (65.0, 50.94)) lies at v 28.44 to 29.94 in the case frame and slot B (board (51.0, 65.46) to (65.0, 66.96)) at v 44.46 to 45.96.

| Slot | Tray | Lid | Least |
|---|---|---|---|
| A | 3.000 mm | 17.86 mm | 3.000 mm |
| B | 3.000 mm | 17.52 mm | 3.000 mm |

The 3.0 mm is the right wall's inner face, which stands 3.0 mm off the board's edge for this reason.

**Check against the criterion.**

| Clause | Shown by | Result |
|---|---|---|
| no part of the tray, lid or rib crosses either slot's mouth | `c8.slot_mouths_clear`, least 3.000 mm against 2.0 mm | held |
| the drawing or model shows the clearance at each mouth | `case-drawings.svg`: "mouth 3.0 to wall (needs 2.0)" at each | shown |

## Backing under the blades (C9)

A rib of the tray, 1.6 mm wide and 3.8 mm deep, runs under the board at v 68.24 to 69.84, beneath J941, J921 and J911, and touches the board's underside over the whole of each blade's footprint width (5.6 mm2 of contact under each, contact fraction 1.0); it spans 8.1 and 11.4 mm between buttresses. The terminals push on along `-z`, into the board, from below when installed.

**Stiffness basis.** The push-on force is 75.6 N, the maker's maximum for a 6.3 mm tab (TE Product Specification 108-2043 Rev D, page 4, 17 lbf). The tray is taken as a cantilever from the plate end with the section it has at v 56 (area 457.3 mm2, second moment 26471 mm4, modulus 2000 MPa, the Ricoh Rapid Fab ASA sheet's 2010 MPa rounded down), loaded at its tip over a span of 70.04 mm. The pilasters stiffen the root, so the figure is conservative. Deflection at the blades: 75.6 x 70.04^3 / (3 x 2000 x 26471) = 0.164 mm. The 0.164 mm is the whole tray's flexure at the blades under the full push-on force and is not compared with anything: the board moves with the tray, and what matters to the triac leads is the motion of the board's triac end against the plate, which is 0.005 mm. That is compared with 0.05 mm, a design figure of this case (`material.allowed_board_motion_mm`: the displacement of the board's triac end against the plate under the maximum insertion force); no maker, assembler or standard figure for the load the soldered leads tolerate was found, so the 0.05 mm is the designer's allowance, not a derived limit. The physical push-on demonstration on a printed tray belongs to the delivered-board leaf.

**The tray root at the inserts' stance.** The 0.05 mm limit and the section above take the root as fixed; with the plate's lower edge at z 6.0 (the bar's height does not change the stance) and one heat-set insert in each pilaster at z 11.65, the root is re-judged in both directions. **Push-on.** The force acts along z at the blades, a lever of 70.04 mm from the plate end, so the root carries a moment of 75.6 x 70.04 = 5295 N mm. The tray's end face bears on the plate down to the plate's lower edge, where the end wall's ledge meets the bar's lower edge, which is the pivot; each insert is pulled in proportion to its height over the pivot, 5.65 mm for the insert at z 11.65, in two pilasters: k = 5295 / (2 x 5.65^2) = 82.94 N/mm, so each insert is pulled with 469 N, 0.689 of its allowance. **Pull-off.** The load reverses and the root turns about the pilaster's top, where the lid's hooks bear (z 20.5), 8.85 mm over the insert: 5295 / (2 x 8.85) = 299 N, 0.440 of the allowance. **The pull-out allowance used** for each insert is 680 N, PEM's lower moulded-ABS figure (`screws.tray_insert_pullout_N`; PEM gives 680 N for its Type IS series and 730 N for its Type IUT series, with torque-out 1.62 and 1.6 N m), read on 2026-11-28 as web-search result text only from the same product pages as the hole figures, which the owner confirms against the part he buys. It is an assumption for printed ASA in this layer direction: no maker publishes a figure for printed ASA, for a hole lying in the layer plane or for the 70 degC enclosure air, and the printed plastic's measured strength is out of scope. Printed-part tests of heat-set inserts in PLA and PETG give 1,170 to 1,775 N; they are other materials and are not the allowance. The root's rotation moves the board's triac end on top of the tray's flexure: the shear displacement under 469 N is 469 x 0.5 / (G x pi x 4.0 x 5.7) = 0.0044 mm with G = 2000 / (2 x (1 + 0.35)) = 741 MPa and 0.5 mm of plastic shearing about the insert's knurl, a rotation of 0.0044 / 5.65 = 7.8e-04 rad, which over the 10.0 mm from the plate end to the first pillar moves the triac end 0.0078 mm. The triac end moves 0.0048 + 0.0078 = 0.0126 mm pushing on, and 0.0048 + 0.0031 = 0.0079 mm pulling off (299 N over 8.85 mm), against the 0.05 mm limit the record already states (`c9.tray_root_tension_and_triac_end_motion`).

**The insert's height.** The insert stands at z 11.65 above the board's component face, inside the window the pocket floor, the countersink and the allowance leave, 9.9 to 11.66 mm for the tear-drop hole the case prints (a hole lying in the layer plane takes a tear-drop roof, which stands 2.005 x sqrt(2) = 2.84 mm above the axis, half of the 4.01 mm hole). Upper bound: the lid toe's pocket floor stands at z 16.5 (the pilaster top 20.5 less 4.0), less the 2.0 mm minimum wall (`case.insert_wall_min_mm`), less 2.84 mm, is 11.66 mm; a round hole would reach 12.5 mm, which this fixing does not use. Lower bound, from the countersink: the plate's lower edge 6.0 + 0.5 mm of edge distance + the countersink's 3.15 mm radius = 9.65 mm. Lower bound, from the allowance: 5295 N mm shared by two inserts is 2646 N mm each, and 2646 / 680 N = 3.89 mm over the pivot, so the insert stands at least 9.89 mm up. The push-on governs: 2646 / (z - 6.0) is 469 N at 11.65 mm, against 467 N at the bound and 407 N for a round hole at 12.5 mm; the pull-off load about the pilaster's top, 2646 / (20.5 - z), is at most 331 N across the window.

**The owner's proof load, with home kit.** The bar is clamped to a bench with the tray fitted, a luggage scale is hooked on the blade end and pulled along z to 15.5 kg, which is 151 N, twice the 75.6 N design load, in both directions. At 151 N each insert carries 937 N pushing on and 598 N pulling off. The proof therefore deliberately tests beyond the 680 N allowance, which is PEM's lower moulded-ABS figure (read as web-search result text only, the owner confirming it against the part he buys) and an assumption for the print; the lowest printed-part test result, 1,170 N, stands above it. A proof that fails (an insert pulls out or the tray visibly moves) falls back to the direct M3 x 16 screw with a 4 mm step low on each pilaster, which the decision names, keeps the pilaster width and the bar, and gives up the insert's wear resistance on removal. Bench measurement is the owner's; the printed plastic's measured strength is out of scope here.

**Check against the criterion.**

| Clause | Shown by | Result |
|---|---|---|
| rigid backing under the board beneath J911, J921 and J941 | `c9.backing_contact_and_stiffness`, contact fraction 1.0 under each | held |
| the drawing shows the push-on direction and the support | `case-drawings.svg`: "push-on -z", "backing rib (v 69.0) under J911, J921, J941 carries the push-on load to the floor" | shown |
| the model shows the contact and a stated stiffness basis (section and span) | the paragraph above | stated |
| the tray root's tension and the triac end's motion at the inserts' stance, with the pull-out allowance, hold the stated limits | *The tray root at the inserts' stance*, *The insert's height*, *The owner's proof load, with home kit*; `c9.tray_root_tension_and_triac_end_motion` | held by model, the allowance an assumption |
| a terminal pushed on does not move the board against the triac leads | 0.005 mm at the triac end against 0.05 mm, a design allowance with no external source | held by model, against the designer's own figure |

## The plate's earth bond (C10)

**Mechanism assumed.** The spreader plate is screwed to the machine's metal wall and is earthed through the wall to the machine's mains-inlet earth. The owner confirms that the wall is earthed to the inlet earth; until he does, this is an assumption. The owner's statement of 2026-11-21 (`open-items.md`) is that the plate's earth bond relies on the screws that fix the plate to the wall, not on the contact patch between plate and wall. The wall's inside face carries a finish of unknown kind (the owner's photographs and statement, `owner-sign-off.md`); the outside face is painted.

**Measurement.** The bring-up task holds the bond to a four-wire measurement: with mains removed, the resistance from the spreader plate to the earth contact of the supply inlet, at a test current a bench supply can deliver, stated with the reading and compared with the declared figure (`DEL-HW-BRING-UP.C6`, `bring-up-provision.md`; `REQ-ELECTRICAL-INSTALL-001.C6` asks the figure to come from the governing wiring authority or a cited, freely available derivation of it, and `REQ-PRODUCTION-GRADE-VERIFICATION-001.C9` asks the governing standard's test current for the production machine). No repository record yet states the declared resistance or the test current: they are declared with the reading in the bring-up record. Taking the measurement is out of scope here.

**Recommendation.** Fit a dedicated earth strap: a ring terminal under one wall bolt, wired to the machine's inlet earth. The inside face of the wall carries an unknown finish, and a bond that relies on a painted or passivated face is not known until it is measured. The strap makes the bond independent of that finish. The records already recommend a serrated (toothed) washer under one wall bolt with the finish scraped to bare metal in a small ring under it (`open-items.md`, `layout-hedges.md` item 10); the strap is in addition to that and costs a lug and a wire.

**Owner's decision.**

Owner's decision (strap or wall alone), in his words: ______  Date: ______

**Drawing.** The plate drawing (`case/out/plate-drawing.svg`) shows no strap, because none is decided. If the decision is a strap, the drawing is amended to carry it before the plate is made: the ring terminal sits under one of the wall bolts in the end zones outside the case (bolt centres u -13.75 and 61.25), so it stays clear of the case and the tray screws. The plate now takes one wall bolt at each end, two in all, where it took four: the bond rests on two bolts and the toothed-washer hedge, which `DEL-HW-BRING-UP.C6` measures and the owner confirms (`owner-sign-off.md` W-19, item 11).

**Check against the criterion.**

| Clause | Shown by | Result |
|---|---|---|
| the mechanism assumed, which the owner confirms | *Mechanism assumed* | stated; the owner's confirmation is open |
| the four-wire measurement the bring-up task holds it to | *Measurement* | stated |
| the owner's decision, strap or wall alone, with his words and the date | the field above | **open: the field is blank until the owner fills it** |
| the drawing shows the strap if there is one | *Drawing* | no strap is decided; the drawing shows none |

## Fitting and removal order (C11)

**Installation order**, from the bought bar to the unit bolted to the wall and the receptacles pushed on. The owner's actions are marked **Owner**; for each step that uses a tool the tool and the access the model shows are stated. Nothing in the order is loose: no film, coating, shim or other loose part, and no step whose omission leaves clearance or creepage short.

1. The assembler fits the board with both triacs seated on their lead shoulders (the triacs on their lead shoulders, leads soldered, none bent).
2. **Owner**: prints the tray and the lid in unfilled ASA (*The plate's material, and the case's*), the tray to the measured seating values, then sets one M3 heat-set insert in each pilaster's end face, flush and square, with a soldering iron and an insert tip pressed down on a flat plate, before the bar is fitted: a proud insert holds the tray off the bar. Tool: a printer, a soldering iron with an M3 insert tip, a flat plate and a square. Access: bench work on the tray alone.
3. **Owner**: buys the standard 20 x 5 mm flat aluminium bar and cuts it to 85 mm (a saw, the cut ends filed square), seats it on the tray's ledge against the tray's end faces, with the inserts set, and marks the two tray-screw holes from the printed tray (a scriber or transfer punch down each insert's bore). Takes it off, drills the two holes 3.4 mm and countersinks each from the back face (a 90 degree countersink, 6.3 mm across) until the head of an M3 countersunk screw sits flush with or just below the back face, checked with a straightedge across the face. Drills the two 4.5 mm wall-bolt holes at the bolt centres, 5.0 mm in from each end and 10.0 mm above the lower edge. Tools: a drill, 3.4 mm and 4.5 mm bits, a countersink, a scriber. Access: bench work on the bar alone, nothing of the case in the way.
4. **Owner**: measures the tab-hole height on the delivered board (calipers from the component face), then drills 2.5 mm and taps M3 through the bar from the triac side (the inner face) at that height less 6.0 mm, measured from the bar's lower edge: nominal 10.5 mm, range 9.3 to 11.3 mm (the drawing gives the distance). Tools: a drill, a 2.5 mm bit, an M3 tap and wrench, calipers. Access: bench work on the bar alone.
5. Bench: the tray is fixed to the bar with two M3 x 10 countersunk screws (one in each pilaster, at z 11.65) from the bar's back face into the inserts, the tray's end faces against the bar and the bar's lower edge on the ledge; there is no daylight at the ledge. Tool: a cross-recess driver of ISO 7046 M3 (a shaft of no more than 5.5 mm). Access: straight along the screw's axis from behind the bar, the bar off the wall (`c5.fixings_reached_installed`).
6. Thermal compound on the tab faces. The board is lowered straight into the tray (along -z, the triacs' tab faces meeting the bar) and fixed with an M3 x 5 thread-forming screw at H1, the lid off. Tool: a driver with a shaft of no more than 5.5 mm. Access: straight down the screw's axis from the component side with the lid off; the shaft stands 2.75 mm from the nearest part (`c5.fixings_reached_installed`).
7. Each triac tab is bolted to the bar with an M3 x 5 screw through the tab hole into the hole tapped through the bar, the lid off. Tool: a driver with a shaft of no more than 5.5 mm. Access: tilted 5.0 to 9.0 degrees up over the far-end wall, against a 12 degree limit, the shaft 0.39 mm from the nearest tray wall at the nominal seating (`c11.tab_screw_driver_reached`).
8. The low-voltage cable is plugged on its header and its wires laid in the notch in the right wall; the lid is fitted, toes under the hooks at the plate end, then the far end closed with its M3 x 10 countersunk screw. Tool: a driver with a shaft of no more than 5.5 mm. Access: straight along the screw's axis from below the installed case, with nothing in the way, 81.5 mm from the wall plane (`c5.lid_screw_reached`).
9. The unit, bar, case and board together, is offered to the wall opening and the bar is bolted to the wall with two M4 bolts, one at each end (centres u -13.75 and 61.25). Tool: a 3 mm hex key or a 5.5 mm hex bit on a hex-socket (socket-cap) head; a socket on a hex head does not fit, because each bolt axis stands 5.05 mm from the case's side and the washer 0.54 mm clear of it (`c3.wall_bolts_outside_case`). Access: along the bolt's axis from out from the wall, the lid on or off. **Owner**: cuts the wall opening and drills the wall; that step is out of scope of the case.
10. The receptacles are pushed on the blades from below through the bays in the lid, with the lid on (`c11.blade_terminals_reachable_lid_on`).

The ledge rules out bolting the tabs first: with the tabs bolted before the bar sits on its ledge, the ledge and the board's pillars would both try to set the height and the triac leads would take the difference. The failure is visible: the board or the bar will not seat and the tray screw does not line up with its insert.

**Silent failures the design does not prevent.** Four faults give no sign at assembly. A wrong-length tab screw: an M3 x 6 reaches 6.24 - 1.23 = 5.01 mm and lifts the bar off the wall (the check fixes only the specified length, tip at most 4.01 mm), and one shorter than M3 x 5 leaves too little thread. A skipped tab screw: the triac has no heat path to the bar and the case temperature at full power is the only sign (`DEL-HW-BRING-UP.C11` measures it). A countersunk head left proud: the bar stands off the wall by the height of the head, and the ledge does not prevent it, because it fixes the bar's edge and not its back face; the straightedge check of step 3 is the only guard. An insert left proud: it holds the tray off the bar, which shows as daylight at the ledge and as a bar that will not seat, so the insert is set flush before the bar is fitted (step 2).

**Removal** is the reverse: pull the receptacles, unbolt the bar from the wall and take the unit out whole; on the bench remove the lid screw, tilt and draw the lid out, unplug the cable, unbolt the tabs, remove H1's screw and lift the board. (The lid can also be removed with the unit on the wall and the cable in place, as in *Installed orientation* and *The low-voltage cable's exit*; it needs 4.75 mm clear below the case.) Nothing is desoldered and no lead is bent.

**Wall bolts stand outside the case, so the plate, case and board leave the wall as one unit.** The plate is 85.0 mm long; the case is 64.52 mm wide at the pilasters; each end carries a 10.0 mm bolt zone holding one M4 bolt at the plate's mid-height with a 9.0 mm washer (bolt centres u -13.75 and 61.25). Length arithmetic: 64.52 + 2 x 10.0 = 84.52 <= 85.0 (margin 0.48 mm). Each washer stands 0.54 mm clear of the case (0.5 asked), so the bolts are reached and removed with the case in place.

**Each triac tab screw is reached by a driver through the case.** With the lid off, a driver reaches each tab screw along a line rising toward `+v` at 5.5 degrees (nominal seating; 5.0 to 9.0 degrees across the seating range, against a 12 degree limit), the nearest tray wall 0.39 mm from the 5.5 mm shaft; at the nominal seating the line passes over the far-end wall.

**The blades stay reachable with the lid on.** Each blade stands inside its 8.9 x 14.89 mm bay in the lid and a line straight along the bay's axis reaches it, so a receptacle is pushed on and pulled off with the lid on.

**Check against the criterion.**

| Clause | Shown by | Result |
|---|---|---|
| the order in which the plate, case, board and lid are fitted and removed, the owner's actions marked, each tool step's tool and access, and the silent failures | *Installation order*, *Silent failures the design does not prevent*, *Removal* | stated |
| the wall bolts stand outside the case, so the unit leaves the wall whole | `c3.wall_bolts_outside_case`, washers 0.55 mm clear | held |
| each tab screw is reached by a driver through the case | `c11.tab_screw_driver_reached`, 5.5 degrees, 0.39 mm | held |
| the blades stay reachable with the lid on | `c11.blade_terminals_reachable_lid_on` | held |

## The plate (C12)

**Form.** A standard flat aluminium bar, **85.0 mm long, 20 mm wide (its height installed) and 5.0 mm thick**, nothing cut from it but its holes: its lower edge rests on the tray's end-wall ledge at z 6.0 mm above the board's component face and its upper edge stands at z 26.0, 3.5 mm above the lid's top (the drawing, `case/out/plate-drawing.svg`, is 1:1 from the case side and names the bar, its thickness and its length). Its only features are six holes: two M3 holes tapped through the whole plate from the triac side (2.5 mm tapping drill, 5.0 mm deep, no thread ending in the bar) at the triac tab-hole height, two M3 countersunk holes from the back face (head diameter 5.5 mm, countersink 6.3 mm across) for the tray screws, one at each pilaster's insert, at z 11.65, and two 4.5 mm holes for the M4 wall bolts, one at each end at the bar's mid-height (z 16.00) centred in the bolt zones.

**The tab holes' position and the tray holes' marking.** The drawing gives each tab hole's position as a distance from the bar's lower edge: the tab-hole height less the 6.0 mm lower edge, **10.5 mm nominal, 9.3 to 11.3 mm over the seating range**, measured on the delivered board before the bar is marked. The bar's two tray-screw holes are **marked from the printed tray with the bar seated on the ledge**, the inserts set flush and square before the bar is fitted (a proud insert holds the tray off the bar), so that the holes match the ledge by construction, and each countersunk head sits **flush with or below the bar's back face**: countersunk heads centre themselves, so a hole drilled off by some distance would either lift the bar off the ledge (visible at the seam) or leave the head proud by that distance and stand the bar off the wall. Drilling accuracy is out of scope.

**Size, and the standard bar.** The bar is at least 84.52 mm long with this case (64.52 + 2 x 10.0 = 84.52) and 20 mm wide, a standard stock width. The case holds at any height from **16.8 mm to 27.5 mm** with the lower edge unchanged (*The case inside the plate's former outline, and the wall opening*), and **the standard sizes between those ends are 20 mm and 25 mm**; the case takes the 20 mm bar, and the 25 mm bar passes the nominal checks too. The bar's thickness, 5.0 mm, is a standard stock thickness. **The stock's width tolerance is an assumption: it is to be read from the supplier's standard when the bar is sourced, and no figure is stated here.** At the 20 mm bar the stock's width tolerance, whatever the supplier's standard states, has 3.2 mm of room below it (down to the least height, 16.8 mm) and 7.5 mm above it (up to the greatest, 27.5 mm). The size is provisional until the owner cuts and measures the wall; the criterion holds at the figure then recorded.

**How it is made or sourced.** The plate is not in the catalogue and is not priced (`constraints-figures.md`). The owner buys standard 20 x 5 mm flat aluminium bar and cuts it to 85 mm, drills the six holes and taps the two tab holes M3 through, in the order of *Fitting and removal order*. It is a single flat part and needs no bending or machining beyond drilling, countersinking and tapping.

**Tab holes: a departure the owner has accepted on his behalf.** The owner's words of 2026-11-24 were that the plate's tab holes be "a short vertical slot or a hole about 1 mm oversize" so that the bolted tab loads no solder joint. The case takes holes tapped M3 through the whole plate from the triac side, at the measured height, relying on the tab hole's own slack (3.73 to 3.88 mm across for an M3 screw), because a slot or an oversize hole would let the plate stand off the wall and a countersink would put a screw head in the heat path (a slot or an oversize hole needs a nut on the face that lies on the wall, and that face is flat against the wall). The tab hole height is derived (16.5 mm, range 15.3 to 17.3) and is measured on the delivered board before the plate is marked; the bar's height holds the screw heads inside it at both ends of the range (5.9 mm from the nearest edge at the 20 mm bar over the whole tab-hole range, 6.7 mm at the nominal seating). The form is the case's choice, and `owner-sign-off.md` W-19 records the departure, signed on the owner's behalf; owner list item 3 asks him to confirm it.

**The triac screw's tip and thread.** The screw is M3 x 5. Over the screw's length tolerance (js15, +/- 0.24 mm, so 4.76 to 5.24 mm) and the tab's thickness range (1.23 to 1.32 mm, `triac.b2_mm`; the minimum is the figure read at the 2026-11-27 readiness pass and is to be confirmed against the sheet), the tip stands at most 5.24 - 1.23 = 4.01 mm inside the 5.0 mm plate, 0.99 mm short of its back face, so it never lifts the plate off the wall (an M3 x 6 would reach 6.24 - 1.23 = 5.01 mm), and engages at least 4.76 - 1.32 = 3.44 mm of thread, against the 3.0 mm the case states (1.0 x the screw diameter). At the 0.70 N m of `fabrication-notes.md` the clamp load is 0.70 / (0.2 x 3.0 mm) = 1167 N (nut factor 0.2); over the tap-drilled cylinder of the least engagement, pi x 2.5 x 3.44 = 27.0 mm2, it shears 43 MPa against the 70 MPa taken for the weakest common plate alloy (`c16.triac_screw_tip_and_engagement`).

**Interface materials.** Triac face to plate: thermal compound, as the thermal record assumed (a film of 0.027 K/W in `circuit-proof.md`); the compound is not in the catalogue and is not priced. Plate to wall: no separate interface material is specified; the bolted joint's resistance is stated as 0, 1 and 3 K/W in the thermal record with 3 K/W the stated limit. A serrated washer under one wall bolt is the practice the records name (`open-items.md`); whether the earth bond relies on it or on a strap is *The plate's earth bond*. The thermal analysis of the interface is the assembly judgement's and is out of scope.

**Depth the case and plate add behind the board, unconfirmed.** Behind the board's bare back the tray adds 5.0 mm (the tray's outer top face at z -6.6, the board's underside at z -1.6). Along the wall's normal the plate adds 5.0 mm (its inner face at v -1.0, its wall face at v -6.0) and the case then runs from v -5.5 to 84.0 (the end wall's back face is v -5.5), so the unit stands 90.0 mm from the plate's wall face to the far end. The figures are the model's and are unconfirmed: the owner checks the depth available at assembly.

**Order of fitting.** As in *Fitting and removal order*.

**What this replaces.** The earlier ear-and-bracket form recorded a two-leg bracket held to the board by two ears and two mounts with plastic spacers, 87.0 mm long board leg and 80.0 mm long standing leg. That form's bracket drawing, spacers and mounts were recorded in `docs/sunbeam-em7000/controller-board-division.md` (the owner's intent and decisions table, assumption A22, and the heater wall board section's paragraphs *The bracket*, *The two mounts*, *The order of fitting and of removal* and *The depth the bracket adds*, and the heater wall assembly's *The bracket*). The flat plate, the printed case and the board's single mounting hole replace all of them; the division record's own amendment notes say so and are history.

**Check against the criterion.**

| Clause | Shown by | Result |
|---|---|---|
| the plate's drawing, a flat plate with nothing cut from it | *Form*, `plate-drawing.svg` | stated |
| the plate is named as a standard flat aluminium bar of the height the case takes, its thickness and length, and its width tolerance is read or marked as an assumption | *Form*, *Size, and the standard bar*; `plate-drawing.svg` (title block) | stated; the tolerance is an assumption |
| the tray holes are marked from the printed tray on the ledge, the heads sit flush or below, and the tab holes are positioned from the lower edge | *The tab holes' position and the tray holes' marking*; `plate-drawing.svg` | stated |
| how the plate is made or sourced | *How it is made or sourced* | stated |
| the interface material of the triac faces to the plate and of the plate to the wall | *Interface materials* | stated |
| the depth added behind the board, graded unconfirmed | *Depth the case and plate add* | stated, unconfirmed |
| the order of fitting and removal | *Fitting and removal order* | stated |
| it replaces what the ear-and-bracket form recorded | *What this replaces* | stated |

## Appearance (C13)

**Who judged.** The look was judged by an independent judge who did not design the case: a separate reviewer given the criterion's words, the stated two-colour print method and the rendered images, and nothing else. The judge did not read this record or the model. The judge chose the rubric and judged the case four times: three times (before and after two polish passes made on the judge's findings) from images that predate the correction of the model's handedness (*The exported case against the board's own model*, C21), and a fourth time from images drawn in the right-handed frame the case is printed and fitted in. The first three judgements are kept as history; only the fourth was made from correctly-handed images, and the verdicts below rest on it. The judge judged it as installed, with the board, the receptacle boots, their wires and the cable drawn in it. The rubric and every verdict in this section are the judge's; the design owner's own earlier table is withdrawn. The owner chooses between the options offered and is not a gate.

**The rubric, and why each line belongs.** The case is a small box bolted under a metal plate inside a stainless espresso machine. It is seen when someone opens the machine and looks up at it, in poor light and at an angle, with the lid, the blade bays and the screw facing them; it is seen in photographs by people deciding whether to copy the project; and it comes off a cheap printer.

| # | Rubric line | Why it belongs |
|---|---|---|
| R1 | One calm shape: a single deliberate form with consistent radii and proportions that reads at arm's length | a small part looks designed when its outline is simple and confident |
| R2 | Belongs beside the machine: colour and form sit well against brushed aluminium and stainless, and the joint with the plate is clean | it is always seen with the plate |
| R3 | The seen face is the best face: the lid, as seen looking up, is a composed face | the lid is what a person actually looks at |
| R4 | Function shown as feature: vents, blade bays, screw, seam and clips share one visual language and none looks like a patch | the openings are fixed by safety and cannot be hidden |
| R5 | Survives shadow and angle: the graphics and the logo still read off-axis and in poor light | that is the only way it is ever seen installed |
| R6 | The logo is right: present, recognisable as the Staircase mark, in proportion, on the face that is seen | it is a requirement, and it is the project's signature |
| R7 | Honest as a print: it looks good as it comes off a cheap single-nozzle printer, and the pictures show what will print | copiers get the print, not the render |
| R8 | Good with the board in it: what shows through the openings looks intended | the case is judged as installed with its board |

**The logo.** The Staircase logo is the project's own asset, owner-held and used with the owner's permission. It is traced to a printable vector, `case/staircase-logo.svg`, kept with the case source, and engraved 0.4 mm deep in grooves 1.0 mm wide: 48.0 mm tall on the tray's outer top face and 29.0 mm tall on the lid face. The grooves are wide and shallow so that their floor stays in view to about 68 degrees off the face. On the tray top the logo stands 4.8 mm toward the plate from the centre of the face, because the floor is thickened under its grooves and that pad must stay out of the block the blade legs stand in. The lid face is seen from below when the machine is open; the tray's top face looks up into the machine. Both logos are set upright for a viewer standing in front of the wall facing it (the lid's with the wall at the bottom of the view, the tray top's with the wall at the top), and `fit.py` reads them back from the exported meshes. The picture `case/renders/directions/logo-preview.png`, which the logo tracing step writes from the owner-held raster, predates the present grooves and is not used in the judgement.

**The two forms.** Both forms share every dimension a safety criterion of this case fixes: they are the same geometry (check `c13.forms_share_dimensions`: the two lids are one geometry, and the tray is one part in both forms).

- *Single-colour*: one filament, every printed part the same colour. It is offered in two colours, by filament alone, with the same print files: **bone** (#e6e1d6, a warm off-white) and **stone** (#928e86, a mid warm grey).
- *Two-colour*: two filaments, a graphite tray (#2f3237) and a bone lid, and a colour change by filament swap at a layer, two swaps per part. Each part prints face down in its own colour to 0.4 mm, then three whole layers in the other colour, from 0.4 to 1.0 mm, then its own colour again. The logo's groove floors on both parts, and the floors of the lid's streamline grooves and block bars, lie in that band and take the second colour: three layers of bone lie over the tray logo's floor, enough for a pale filament to print opaque, and two or three layers of graphite over the lid's groove floors. A filament change colours a whole layer, so the band also shows as a pinstripe 0.6 mm high in the middle of each part's 1.6 mm chamfer (graphite on the bone lid, bone on the graphite tray) and on the wall of every lid opening it crosses (all 16 vents, the three bays and the screw's countersink). It crosses no outlet slit of the tray. No inlay part exists. The check `c13.swap_layers_stated_and_proved` holds the band to whole layers and proves every groove floor lies in it.

**The views.** Generated, not committed: `task hw:case:views` and `task hw:case:directions` write them under `case/renders/` and the tests draw their own set into a temporary folder; the repository keeps only the two sheets, the logo preview and two lit lid-on and lid-off pictures (`case/renders/lit/`). The tracked sheets and lit pictures were drawn on 2026-11-27, before the pilasters widened to 8.01 mm and the bar lengthened to 85 mm, and are the pictures the fourth judgement saw; they are not redrawn. 1600 x 1200, drawn from the model the checks ran on. Installed views, ten per form, in `directions/flow-<form>-<view>.png` with form `single` (bone), `stone` or `two`: `above`, `below`, `below-lit` (the below camera lit from the front and below, as the inside of an open machine is), `side`, `lid` (straight at the lid face, the wall at the bottom of the picture) and `top` (straight at the tray's top face, the wall at the top), and the logo close-ups `logo-lid-30`, `logo-lid-60`, `logo-top-30` and `logo-top-60`. Six more per form in `<form>-<view>.png`: `far-end`, `top`, `plate-end`, `underside`, `exploded` and `lid-off`. Two sheets: `directions/contact-sheet.png` and `directions/logo-sheet.png`. The two-colour form is drawn as it prints, cut at its swap layers. The receptacle boots, their wires and the cable in the views are assumed shapes and colours for the picture, not checked geometry.

**The judge's verdicts, fourth judgement, per form.** The criterion asks for each line as met or not met. The judge's scale has a middle verdict, *partly met*; it is recorded here as not met, with the judge's word beside it. The judge kept the rubric unchanged, since a mirror image of a good composition is still a good composition, and read the regenerated renders in `case/renders/` drawn after the handedness correction. The view named is the image that shows the line for that form; where the judge named the view in one form only, the same camera's image of the other form is listed and marked †.

| # | Bone | View | Stone | View | Two-colour | View | The judge's reason |
|---|---|---|---|---|---|---|---|
| R1 | met | `directions/flow-single-above.png` | met | `directions/flow-stone-above.png` | met | `directions/flow-two-above.png` | Unchanged by the correction: one calm shape. |
| R2 | not met (judge: partly met) | `directions/flow-single-above.png` | met | `directions/flow-stone-above.png` | met | `directions/flow-two-above.png` | Bone is still the pale appliance beside brushed metal. Stone and graphite sit with the metal. |
| R3 | met | `directions/flow-single-lid.png` | met | `directions/flow-stone-lid.png` | met | `directions/flow-two-lid.png` | The lid still composes: the bar block and bays form a band across the top and the logo stands upright beneath it. |
| R4 | met | `directions/flow-single-side.png` †, `directions/flow-single-above.png` † | met | `directions/flow-stone-side.png`, `directions/flow-stone-above.png` † | not met (judge: partly met) | `directions/flow-two-side.png`, `directions/flow-two-above.png` | Even louvres and a clean rim. The cable gate is still a loud dark gap in the bone rim, in two-colour only. |
| R5 | not met (judge: partly met) | `directions/flow-single-below.png` | not met (judge: partly met) | `directions/flow-stone-below.png` | met | `directions/flow-two-below.png` | One filament goes flat in shadow; two colours do not. |
| R6 | met | `directions/flow-single-lid.png`, `directions/flow-single-top.png`, `directions/logo-sheet.png` | met | `directions/flow-stone-lid.png`, `directions/flow-stone-top.png`, `directions/logo-sheet.png` | met | `directions/flow-two-lid.png`, `directions/flow-two-top.png`, `directions/logo-sheet.png` | Right way round and upright on both faces; stronger than in any earlier pass. |
| R7 | met | `directions/flow-single-lid.png` | met | `directions/flow-stone-lid.png` † | not met (judge: partly met) | `directions/flow-two-above.png` | The pictures now show the real part, which is the largest gain in honesty so far. The two-colour stripe still wants one real print. |
| R8 | met | `directions/flow-single-below-lit.png` | met | `directions/flow-stone-below-lit.png` | met | `directions/flow-two-below-lit.png`, `two-lid-off.png` | Boots and wires in the bays in the installed views; the real board reads right with the lid off. |

Score: bone meets 6 of 8, stone 7 of 8, two-colour 6 of 8. The lines recorded as not met are *partly met* in the judge's scale: bone partly meets 2 (R2, R5), stone 1 (R5) and two-colour 2 (R4, R7). No line was judged failed outright in any form.

**The judge's verdict per form.** *Two-colour: cool.* Still the one to lead with; the even louvres and the continuous bone rim fixed its weak side view, and the cable gate has put one new blemish on it. *Stone: good, and quietly cool.* A calm warm-grey object that belongs beside the metal; it is the single colour the judge recommends. *Bone: presentable, not cool.* Nothing is wrong with it; it looks like a pale utility box. **Good enough to publish: yes, all three**, leading with two-colour, naming stone as the one-filament choice and listing bone as an alternative.

**The logo, as the judge found it.** Recognisable as the Staircase mark in both forms on both faces, head-on and at 30 and 60 degrees off the face (`directions/logo-sheet.png`). In the fourth judgement it reads the right way round and upright on both faces: on the lid, with the wall at the bottom of the view, as a person standing in front of the machine and looking up sees it, and on the tray top with the wall at the top. The two logos therefore point opposite ways relative to the plate, which is correct: one is seen from below and one from above. In the single-colour form it reads by relief alone and is quiet; in the two-colour form it is graphite on bone on the lid and bone on graphite on the tray top. At the lid's 29 mm the middle of the mark merges into a few bolder shapes and is still the mark.

**How the verdicts moved.** First judgement (before any polish): bone met 1 line of 8 and two-colour 2. The judge's findings were that the logo was lost off-axis, the two-colour pictures did not show the swap layers, the far end of the lid was uncomposed, the through-vents were scattered and unequal left to right, the louvre row was uneven, the lid's rim was broken in three places and bone alone looked like office equipment. Second judgement (after the logo grooves were widened, the swap layers drawn and the far-end block added): bone met 3, two-colour 6. Third judgement (after the vents were mirrored, the outlets made one even row, the rim made continuous and stone offered): bone met 6, stone 7 and two-colour 6, the same score as the fourth, but made from mirror-image pictures. Fourth judgement (after the handedness correction, from correctly-handed images): the verdicts stand and the table above is its own. The judge found nothing worse; the logo reads better, because the lid's mark now stands upright and the band above it reads as a header.

**The board seen inside the case.** In the fourth judgement the board reads right. With the lid off, the two triacs sit on the plate (the pictures the judge saw showed an amber film in front of it; the case has since taken the form without a film, a change at the plate end that has not been re-judged and that touches neither the lid nor the tray's top face), the varistors and the two isolators are where the board's printed labels say, the three output tabs are at the far end and the low-voltage connector is on the side where the cable gate is; the board's printed text reads the right way round, which shows the pictures are no longer mirrored. With the lid on in the installed views, one boot stands in the small bay and two in the large one, matching the three tabs at that end, and the cable leaves through the gate beside its connector.

**Known cosmetic items, as the judge left them.** The fourth judgement lists the first three of these (the cable gate, the window under the screw and a real print) as what it would still change. None blocks publishing.

1. The cable gate is oversized and plain: 16.4 mm of the rim is open for a cable a few millimetres wide, square-ended, on one side only. It reads as a cable exit only because the cable is in it, and it is loud in the two-colour form. It is that long so that the lid can be drawn off with the cable in place (see *The low-voltage cable's exit*).
2. The window under the lid screw has a stepped left edge, so the far end is centred but not quite symmetric (`two-far-end.png`).
3. The two-colour pinstripe and the bone floor of the tray's logo are unproven on a real printer: expect a slightly stepped line and a little colour carry-over on the first swap layer. One print of each part settles it.
4. The single-colour forms go flat in shadow. The judge accepts this as the price of one filament.

**Check against the criterion.**

| Clause | Shown by | Result |
|---|---|---|
| the record states an appearance rubric chosen by the judge of the look | *The rubric* | stated |
| the Staircase logo, owner-held and used with permission, traced to a printable vector kept with the case source | *The logo*; `case/staircase-logo.svg`; `c13.logo_present_in_each_form` | held; the owner's confirmation that the vector may be published is owner list item 8 |
| recognisable in both colour forms, on a face seen when the machine is open | R6, met in every form; `c13.mark_on_lid` | held, by the judge |
| two forms sharing every safety-fixed dimension; single-colour in one filament; two-colour by filament swap with no more than two filaments | *The two forms*; `c13.forms_share_dimensions`, `c13.swap_layers_stated_and_proved` | held |
| each form judged from rendered views taken from at least three angles | *The views*; the table names at least five cameras per form | held |
| each rubric line recorded as met or not met per form with the view that shows it | the table, from the fourth judgement | recorded: 6, 7 and 6 of 8 met, the rest partly met and recorded as not met |
| the judge did not design the case and judges it as installed with its board in it | *Who judged* | stated |
| the owner may choose between options but is not a gate | owner list items 9 to 12 | stated |

## Printing (C14)

**Printer baseline.** A common low-cost open-frame FDM machine with a 220 x 220 mm bed (250 mm tall), a 0.4 mm nozzle and 0.2 mm layers; the owner's printer is one instance of it. Every printed part fits the bed in the stated orientation:

| Part | Print orientation | Size in print orientation (x, y, z) | Fits the 220 x 220 mm bed |
|---|---|---|---|
| tray | outer top face down on the bed | 64.92 x 89.50 x 27.10 mm | yes |
| lid, single-colour | face down on the bed | 64.92 x 84.60 x 5.85 mm | yes |
| lid, two-colour | face down on the bed | 64.92 x 84.60 x 5.85 mm | yes |

**Material.** ASA is the baseline. Printing it on an open-frame machine needs a draft shield and a brim against warping and cracking, and a cardboard box over the machine is the cheapest enclosure that keeps drafts off it (the slicer profile used here sets a 6 mm brim, a draft shield and a 245 degC nozzle with a 100 degC bed; the makers' sheets give 240 to 280 degC nozzle and 75 to 110 degC bed). ASA is also printed with ventilation, as its fumes are unpleasant. PETG, PLA and PC are not the baseline. PLA and PETG soften well below the plate temperatures of *The plate's material* (typical published glass transitions are about 55 to 65 degC for PLA and about 75 to 80 degC for PETG, general filament-maker figures that this record did not read from a maker's sheet, against a nominal plate temperature of 60.2 degC and a bound of 93.4 degC), and PC needs a nozzle near 270 to 310 degC and a heated enclosure that a common open-frame machine does not have (the PC figures too are general filament-maker practice, not read from a maker's sheet here).

**Supports, per part.** The stated print is with supports **off**, for every part. The slicer's result for each part, with the slicer named, is the check:

| Part | Slicer | Print time | Filament | Layers | Extent of the toolpath (brim and shield included) |
|---|---|---|---|---|---|
| tray | PrusaSlicer 2.9.7 | 5h 10m 58s | 42.66 g (39.87 cm3) | 136 | 73.18 x 97.74 x 27.00 mm |
| lid, single-colour | PrusaSlicer 2.9.7 | 1h 55m 30s | 13.87 g (12.96 cm3) | 29 | 73.19 x 92.87 x 5.60 mm |
| lid, two-colour | PrusaSlicer 2.9.7 | 1h 55m 30s | 13.87 g (12.96 cm3) | 29 | 73.19 x 92.87 x 5.60 mm |

The supports-off run generates no support material on any part, so none stands on the plate-end faces, the screw seats, the slot-mouth faces or the lid-fit faces, and no support remains on any part. The geometry check finds every overhang on the three parts bridgeable under the printer's rules (45 degree overhang limit, 3.5 mm bridge limit): the tray has 30 bridged roofs of spans 0.8, 2.0 and 2.7 mm, each lid 19 of spans 0.8, 1.55, 1.56, 1.57 and 2.36 mm, and none unbridgeable. Critical faces: the tray's plate-end faces (1), screw seats (4), slot-rule faces (1) and lid-fit faces (3); each lid's lid-fit faces (1) and screw seat (1); no critical face needs support. The tray's slot-rule face, the inner face of the right wall that stands off the slot mouths, is pierced by that wall's 15 outlet slits; each slit's roof is a 2.0 mm bridge. The two-colour lid is the same geometry and slices to the same figures; its two filament changes, after the layers that end at 0.4 and 1.0 mm, are made at the printer.

**Supports-auto diagnostic.** A second run asks the slicer to add support wherever it finds an overhang at the model's own 45 degree limit, only to show where a slicer would add some. It is not the stated print.

| Part | Support the slicer would add | Volume | Extra print time |
|---|---|---|---|
| tray | up to 6.6 mm above the bed, 31 places | 1838.1 mm3 (764.2 mm of filament) | +13m 50s |
| lid, single-colour | up to 2.4 mm above the bed, 12 places | 548.2 mm3 (227.9 mm of filament) | +4m 54s |
| lid, two-colour | up to 2.4 mm above the bed, 12 places | 548.2 mm3 (227.9 mm of filament) | +4m 55s |

Where the slicer would add support, and why each is accepted. Tray: the roofs of the 25 outlet slits (672.7 mm; each a 2.0 mm span anchored on both long sides, bridged); the 45 degree chamfer on the bed side (70.3 mm; a face at exactly 45 degrees, at the printer's limit, which prints without support); two sloped faces at or steeper than the limit (6.3 mm); and first-layer patches with no model face above them (15.1 mm). Lid: the bed-side chamfer (112.8 mm); the sloped walls of the vent slots with the 1.55 and 1.56 mm groove roofs beside them (100.0 mm, bridged); flat groove roofs (2.0 mm); and first-layer patches (13.2 mm). At the slicer's own detection threshold the totals fall to 704.1 mm on the tray and 60.0 mm on each lid. Every one of these places is accepted by the rule in `case/slice.py`: a face at or steeper than 45 degrees, or a roof no wider than the bridge limit anchored on both sides.

**The diagnostic entry on a critical face.** On each lid the diagnostic run would put support under one critical face, the lid screw's countersink cone, a screw seat: 0.39 mm of support filament under 0.54 mm2, facets at 45.0 to 45.2 degrees, none a flat roof (0.24 mm at the slicer's own threshold). A 90 degree countersink printed mouth down prints without support, and the stated print has none there. **The rule** (`critical_entry_problems` of `case/slice.py`) allows a diagnostic entry on a critical face only when every facet is at or steeper than the model's 45 degree limit and none is a roof, except that supported critical facets whose areas, summed over every entry of a part's run (a flat roof's included, so many small entries cannot each hide under the figure), are smaller than the noise area, 1.0 mm2 (`printer.noise_area_mm2`, the figure by which the region rule and the model's overhang check already set tessellation ripple aside), are not a problem; at or above that area the rule stands unchanged, entry by entry, so a flat roof or a facet flatter than the limit is still rejected there. The one entry, 0.54 mm2, is under it. **The entries move with the mesh.** The diagnostic run once put two entries under each lid, the screw seat's 0.32 mm and a zero-area flat sliver of the lid-fit faces, and before that 0.34 mm under the screw seat alone; the slicer's trace of support lands differently when the part's tessellation or position changes, as it did when the printed case's end wall moved the lid 0.25 mm toward the plate, and the geometry of the seat did not change. The design owner accepts the entry as a diagnostic entry, not a support that remains; the stated print, supports off, has no support on any part. The tray has no such entry; in 17 places the diagnostic support would stand flush beside a critical plane without being under it (15 beside the slot-rule face at the outlet slits, 2 beside a plate-end face).

**Fixings.** The case is assembled with ordinary screws: M3 x 10 countersunk (two, tray to plate, into heat-set inserts), M3 x 5 pan head (H1), M3 x 10 countersunk (lid), M3 x 5 pan head through the tab holes (two) and M4 wall bolts (two). No part needs post-print machining.

**Honest grade.** Sliced and checked by geometry, not yet printed.

**Check against the criterion.**

| Clause | Shown by | Result |
|---|---|---|
| the printer is stated as a common low-cost open-frame machine, 220 x 220 bed, 0.4 nozzle, 0.2 layers, the owner's being one instance | *Printer baseline* | stated |
| every printed part fits that bed in its stated orientation | `c14.bed_fit` | held |
| ASA is the baseline; what printing it open-frame needs; why PC, PETG and PLA are not | *Material* | stated |
| no support material on the plate-end faces, the screw seats, the slot mouths and the lid-fit faces | supports off: `case/slice/*.json` `supports_off.support_generated` false on every part; `c14.overhang` | held |
| the orientation and any support that remains are stated per part | the first table; no support remains | stated |
| a slicer's sliced result for each part is recorded as the check | the second table, `case/slice/*.json` | recorded |
| ordinary screws, no post-print machining | *Fixings* | stated |

## Openings and the enclosure (C15)

**Test-finger stand-in.** The standard jointed test finger (IEC 61032 probe B) is 12 mm in diameter and 80 mm long with two joints bending 90 degrees (Lisun data sheet, a secondary source); its tip radii were not found in a free source. The check therefore uses a rigid stand-in that is more penetrating than the probe's tip: a 12 mm cylinder with a 4.0 mm hemispherical tip and a 15 mm cone from the tip to the 12 mm cylinder. Nothing with a smaller opening than 4.0 mm admits the tip.

**With the three receptacles fitted** (the judged state, typical boot envelope; the largest common envelope is reported alongside), all 52 openings admit nothing:

| Opening kind | Count | Smaller dimension | Finger path and result | Drip path and result |
|---|---|---|---|---|
| lid vent (louvre) | 16 | 1.10 mm (1.56 mm at the face) | the 4.0 mm tip cannot enter; admits nothing; least remaining to mains copper 20.4 mm | no line within 15 degrees of vertical from outside enters |
| tray outlet slit | 25 | 2.0 mm | the tip cannot enter; admits nothing; least remaining to mains copper 3.0 mm | none enters |
| blade bay | 3 | 8.9 x 14.89 mm | boot fitted: the opening left round it admits a disc of 2.20 mm (typical) and 0.97 mm (largest common), under the 4.0 mm tip; 2.075 mm from the boot to the blade | none enters (the bays face down) |
| cable notch | 1 | 2.5 x 8.0 mm | the tip cannot enter; admits nothing; 21.6 mm to mains copper | none enters |
| finger slit | 2 | 0.8 x 8.0 mm | the tip cannot enter; admits nothing; 3.0 mm to copper | none enters |
| seam | 5 | 0.2 mm (four top seams) and 0.45 mm (lip) | the tip cannot enter; admits nothing | none enters |

The drip rule is a 15 degree cone about the installed vertical: a drip falls from above onto the tray's closed outer top face, the bare back's side. For each opening the check casts 25 lines within the cone from each of its sample points; a drip path is a line that leaves the case upward, and no opening has one. The blade bays and the cable notch are judged with the insulated receptacles and the cable fitted; the opening that remains round a fitted boot is the annular gap the table gives.

### Finding: with a receptacle removed a test finger can touch the bare blade

This is a finding, stated as one. It is not counted in any verdict.

With no receptacle fitted, the stand-in finger's tip, placed anywhere in the bays, comes within **-1.62 mm** of the blade at J941 and at J921 (it touches them) and **+1.05 mm** at J911 at the nominal seating. The bay is 8.9 x 14.89 mm, the gap the finger enters is 10.5 mm at J941 and J921 and 8.5 mm at J911, and the standing check (a finger placed in the bay with the case leaning) fails from a lean of +0.30 degrees. Across the seating range the figures are J941 and J921 -1.39 mm at lean -1 degree and -1.99 mm at +1 degree, and J911 +2.23 mm at -1 degree and -0.12 mm at +1 degree, reached in 64 of 64 extreme seatings.

Why. The boots of J941 and J921 need a shared bay: the two blades stand 8.1 mm apart, which leaves 0.30 mm between two boots, so no rib fits between them and the bay must be wide enough for a booted receptacle (8.9 mm across). A bay that size admits the finger to the bare blade when no receptacle is on it. Recessing the blades beyond the finger's reach would need about 9 mm more lid depth.

The owner accepted this residual on 2026-11-26: asked whether to judge finger safety with the three receptacles fitted and to record the bare blade as a stated residual (the machine never energised with a receptacle off a blade), he chose "Accept, state the rule (Recommended)". It is a service state inside the machine's own enclosure, behind a panel that takes a tool to remove. **The rule: the machine is never energised with a receptacle off a blade.**

**The enclosure the pollution-degree credit relies on.** The case is the enclosure that the separation basis's pollution-degree credit relies on (`separation-basis.yaml`: pollution degree 2, material group IIIa, household appliance interior, water, steam and condensation possible, boards protected against moisture by the enclosure with a conformal coat as a supporting measure). What the openings leave of it: 52 openings of six kinds. Free area: 210.8 mm2 of lid inlets (16 slots) plus 225.0 mm2 of tray outlets (25 slits) plus 139.9 mm2 left round the three fitted boots plus 20.0 mm2 of cable notch plus 12.8 mm2 of finger slits, about 609 mm2 in all, besides the narrow seams. What cannot enter: anything of 4 mm or more through the bays, and anything wider than the slots, slits and notches; a drip falling within 15 degrees of vertical. What can: air, fine dust, vapour, and condensate forming inside. The case is therefore an enclosure against touch and falling drips, not a seal. The credit (pollution degree 2) assumes only non-conductive pollution and occasional condensation; the openings do not keep out dust or vapour, so the credit rests on the machine's interior being that environment and on the case keeping out what a finger or a falling drip can carry in.

**Check against the criterion.**

| Clause | Shown by | Result |
|---|---|---|
| with the three receptacles fitted, every opening keeps a standard test finger off mains copper and bare mains metal | `c15.finger`, `c15.finger_blades_receptacle_fitted`, `c15.openings_enumerated`: 52 of 52 admit nothing | held |
| no opening lets a drip fall onto mains copper | `c15.drip` | held |
| the finger's and the drip's path stated for each opening | the table, per kind; `case/out/check.json` per opening | stated |
| the residual is stated with its figures (blade, bay width, gap, lean) as a finding, not a pass | *Finding*; `c15.finding_blades_no_receptacle` (kind finding, counted in no verdict) | stated |
| the rule that the machine is never energised with a receptacle off a blade | *Finding* | stated |
| the case is the enclosure the pollution-degree credit relies on, and what the openings leave of it | *The enclosure the pollution-degree credit relies on* | stated |

## Seating range (C16)

The delivered triacs' seating scatter is stated as a range, every figure **unconfirmed**; the owner measures the delivered board, and the tray is printed to the measured values.

| Quantity | Nominal | Range | Source |
|---|---|---|---|
| tab-hole height above the board face | 16.5 mm (derived) | 15.3 to 17.3 mm | body underside 3.75 mm (ST DS2114 Rev 11, Table 6 p.9, a1) plus the tab hole 12.75 mm above the body underside (A - L, p.9); the range follows the body-underside range |
| body underside above the board face | 3.75 mm | 2.55 to 4.55 mm | a1 3.75 typical; minimum I4 15.80 less (A - L) maximum 13.25; maximum a 0.8 mm design allowance for a part not pushed home |
| common lean of both triacs | 0 degrees | -1.0 to +1.0 degrees | a design allowance: three collinear leads do not square the part; no maker or assembler figure exists |
| difference of lean between the two triacs | 0 | 0 to 0.3 degrees | a stated limit that cannot be designed out; the owner has a joint reflowed beyond it; the model holds it at 0, and the range's lean axis is the common lean's -1.0 and +1.0 degrees; the combined 1.3 degrees the tray's height budget allows is not checked, because rebuilt there 18 of the 32 builds fail checks outside the plate clearance (boot clearance, backing contact, lead-to-tray clearance, slot clearance), carried by `SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-HOLDS-AT-THE-COMBINED-LEAN-ALLOWANCE` |
| tab face to lead centre | 2.86 mm | 2.645 to 3.07 mm | DS2114 Rev 11 Table 6 p.9: c2 2.40 to 2.72 plus half of c1 0.49 to 0.70 (`layout-plan.md`) |
| leads below the board | 2.0 mm | 0 to 2.0 mm | the owner trims the leads to 2.0 mm at most |
| board outline routing tolerance | 0 | -0.2 to +0.2 mm | the fabricator's regular tier, +/- 0.2 mm (`docs/board-manufacturer-jlcpcb.md`, published and unverified; 0.1 mm at its precision tier); it moves the board's edges and slot mouths and not the pads or the leads |
| lead play in its drilled hole | 0 | -0.305 to +0.305 mm | (1.1 mm hole less the lead's thickness 0.49 to 0.70) / 2, 0.305 to 0.20 mm to either side, frozen by soldering; an assumption, no assembler figure; it moves the triac, its tab face and the plate bolted to it and not the pads |
| plate lower edge below its nominal 6.0 mm | 0 | -0.36 to 0 mm | the ledge's print allowance, 0.2 mm (one layer of 0.2 mm, a design figure; the printed ledge may stand under its drawn height and not above it), plus the board's thickness tolerance, 1.6 mm plus or minus 10 percent, 0.16 mm (`docs/board-manufacturer-jlcpcb.md`, *Board thickness tolerance*, published and unverified): a thicker board lifts the component face off the tray, so the ledge stands that much lower against it; the two are one axis because each moves the edge the same distance in the same direction, and only the downward direction is taken (see *The plate's clearance and creepage over the board's tolerances*) |

**Two figures for the tab-hole height, and how they agree.** The model's nominal of 16.5 mm is the body underside 3.75 mm (a1) plus the tab hole's 12.75 mm above the body underside; it is a derived figure. The corrected records (`assembler-fitting-record.md`, `fabrication-notes.md`, `open-items.md`, `schematic-spec.yaml`) and the maker's drawing give the hole centre to the lead shoulder as I4, about 16.4 mm with a range of 15.8 to 16.8 mm (`params.yaml`, `triac.I4_mm`). The two differ by 0.1 mm. The model's range, 15.3 to 17.3 mm, is deliberately wider than I4's and covers it: its low end is I4's minimum less 0.5 mm for the spread of the body-to-hole figure and its high end allows 0.8 mm for a part not pushed home. The case is built and checked across the model's range, so a delivered board at I4's 15.8 to 16.8 mm is inside it.

The model is built at all 64 extremes of body height, lean, tab-face distance, outline routing tolerance, lead play and plate edge (`case/out/check-range.json`) and every check passes at each: the least straight line from any Mains copper to the plate is 5.819 mm and from a bare lead 2.636 mm, against 2.6 mm; the gap to the plate is 0.280 to 1.715 mm; the boot clearance is at least 0.54 mm; the lid sweep clearance is at least 0.178 mm; the driver reaches each tab screw at 5.0 to 9.0 degrees. The tray's board seat follows the lean, so the board is seated without loading the leads; the leads and blade legs stand off the tray by at least 1.18 mm at the nominal seating; and the plate's holes, tapped through, sit at the tab hole height, which the owner measures before the plate is marked. The case takes the tapped form: M3 holes tapped through the plate at the measured tab-hole height, with the tray printed to the measured values, and not slots or oversize holes. That departs from the owner's ruling of 2026-11-24 (a slot or a hole about 1 mm oversize); the reason is in *The plate*, and `owner-sign-off.md` W-19 records the departure, signed on the owner's behalf (owner list item 3 asks him to confirm it). The receptacle-off reach at the extremes is in the finding above.

**Check against the criterion.**

| Clause | Shown by | Result |
|---|---|---|
| the scatter is stated as a range of tab-hole height and lean | the table | stated |
| the seat, the plate and the plate's tab holes meet at the range's extremes without loading the leads | `c16.seating_range` (64 extremes, every check passes), `c16.seat_clear_of_leads_and_plate_hole` | held by model |
| the plate's tab holes are a short slot or an oversize hole, or tapped holes at the measured height with the tray printed to the measured values, and the record states which | the case takes tapped holes at the measured height with the tray printed to the measured values | **a departure from the owner's ruling of 2026-11-24; recorded in `owner-sign-off.md` W-19, signed on the owner's behalf; he is asked to confirm it (item 3)** |
| the range with its source is recorded as unconfirmed for the owner to check | the table and the first sentence | stated |

## The plate's material, and the case's (C17)

**Plate temperature.** From `circuit-proof.md` (*The narrower plate and the triacs' thermal judgement on it*, which repeats *The wall's material and the triacs' thermal judgement on it* at the plate the case takes): the triacs dissipate 9.09 W together, the plate being the 20 mm by 80.0 mm bar of aluminium 5 mm thick against a wall 2.5 mm thick of conductivity 110 W/(m.K), with the exposed face's heat-transfer coefficient h (W/(m2.K)). The wall's thermal resistance is R_wall = 1 / (h x H x L + P x sqrt(h x k x t)) with H = 0.020 m, L = 0.080 m, P = 2 x (H + L) = 0.200 m, t = 0.0025 m and k = 110: R_wall = 2.876 K/W at h = 10 and 4.123 K/W at h = 5. The plate temperature is T = T_air + 9.09 W x (R_wall + Rc), with Rc the bolted joint's resistance between plate and wall. The judgement was made for the 80 mm bar of the former plate and is not re-run for the 85 mm bar the case now takes: a longer bar of the same section has a smaller wall resistance (2.738 K/W at h = 10 for 85 mm against 2.876 K/W for 80 mm), so the figures below are the conservative ones.

| Case | Air | h | Rc | Arithmetic | Plate temperature |
|---|---|---|---|---|---|
| nominal | 25 degC | 10 | 1 K/W | 25 + 9.09 x (2.876 + 1) | 60.2 degC |
| hot bound | 40 degC | 10 | 3 K/W | 40 + 9.09 x (2.876 + 3) | 93.4 degC |
| hot, still air | 40 degC | 5 | 3 K/W | 40 + 9.09 x (4.123 + 3) | 104.8 degC |

All three are continuous full power on both triacs, which is the conservative bound. The real duty is about two minutes at full power on both and then much lower power (`controller-board-division.md`, operating profile), with the owner's worst case a start-up warm-up followed by steaming and brewing together; the warm-up duration is unsourced in these records. The plate is narrower than the 30 mm plate the earlier figures (57.5, 90.6 and 100.9 degC) were drawn for, and its temperatures are higher: the printed case has no film on it, so no rating of a film is asked.

**ASA heat deflection (0.45 MPa).** From makers' documents: 102.6 degC (Polymaker PolyLite ASA technical data sheet, V5.1, ISO 75), 98 degC (Ricoh Rapid Fab ASA FDM technical data sheet, 2019, ASTM D648) and 96 degC (an ASA filament technical data sheet, file `TDS_ASA_Filament.pdf`, unannealed, ASTM D648; the maker's name is not printed on the copy read): 96 to 103 degC.

**Grade (the design owner's).** ASA **holds** at the nominal case (60.2 degC) and at the 93.4 degC bound (margin 2.6 K to the lowest maker figure, 5.4 K at the former plate). ASA **does not hold** at the 104.8 degC bound, which lies above the makers' 96 to 103 degC band, nor on a stainless wall: the thermal record's stainless bounding case gives a wall resistance of 7.222 and 10.571 K/W at this plate, so 99.7 degC at the nominal air and 132.9 and 163.4 degC at the bounds. Only the parts of the case that touch the plate see the plate temperature: the pilaster end faces, the inserts and the end wall's ledge, on which the bar's lower edge rests (4.3 mm of the bar's thickness in contact); the rest of the case is cooler.

**Owner acceptance needed.** Accept ASA on the grounds that the 104.8 degC bound is continuous duty the machine does not run, or name another material. The acceptance rests on analysis alone: no bring-up criterion asks for the plate's temperature to be measured. If the owner wants it confirmed, a thermocouple on the plate at the bring-up's sustained full-heat run reads it; the design owner's threshold is 85 degC, 11 K under the lowest maker figure, above which the material is changed.

**The case's material, conductive filament excluded.** The tray, its end wall and the lid are printed in unfilled ASA; carbon-fibre, metal-filled and other conductive filament is not used, because the end wall stands within the signed clearance and creepage of the mains pads at the tolerance extremes: 0.480 mm from the board and 1.690 mm from Mains copper at the narrowest gap, inside the signed 2.0 mm terminal clearance and the 2.6 mm creepage (`c1.end_wall_stands_off`). The print settings and the choice among unfilled plastics are out of scope.

**Flame.** ASA is rated UL 94 HB (Ricoh sheet and the unnamed ASA sheet; the Polymaker sheet states none). The mains pads carry 10 A. No flame rating is asked of the case by any requirement. That is recorded as an owner item: accept HB, or name a flame-retardant filament. No film is used, so none is specified.

**Check against the criterion.**

| Clause | Shown by | Result |
|---|---|---|
| the temperature the case reaches at the plate, derived from the thermal records | *Plate temperature*: 60.2, 93.4 and 104.8 degC | derived, arithmetic shown |
| the material's heat-deflection temperature from its maker's document | *ASA heat deflection*: 96 to 103 degC, three sheets | stated |
| the material graded as holding or not holding | *Grade*: holds at 60.2 and 93.4 degC, does not hold at 104.8 degC | graded |
| where it does not hold, the owner acceptance needed | *Owner acceptance needed*; owner list item 5 | named; **the acceptance is open** |
| the flame rating against the pads' 10 A, and that no rating is asked, as an owner item | *Flame*; owner list item 6 | stated |

## The receptacle boots (C18)

**Envelopes used, assumed.** Width x thickness x length: **typical 10.5 x 7.8 x 22.0 mm** and **largest common 13.0 x 7.8 x 25.0 mm**. Sources: typical, the larger of Vogt 3906 (fully insulated receptacle, 1.5 to 2.5 mm2, sleeve width A 10.5, length 21; Vogt catalogue p.376, read from the drawing) and JST LVDDF2-250A (W 7.4, E 7.8, L 22.0; JST catalogue, fully insulated with straight insulation, text); largest common, the larger of Vogt 3933 (4 to 6 mm2, A 13, L 25; Vogt catalogue p.375) and JST LVDDF5.5-250A (E 7.8, L 25.0). No maker figure was found for a separate rubber boot over an uninsulated receptacle; the column meanings in the makers' tables (which letter is width and which thickness) are unconfirmed. These are assumed envelopes: the owner measures the boots he will fit.

**Push-on direction and clearances.** The receptacle is pushed on along `-z` from below and pulled off downward. The boot, swept from fully seated to fully withdrawn plus 10 mm, keeps **0.55 mm** to the lid and tray with the lid on and **1.10 mm** with it off (needs 0.5) at both envelopes, per blade: lid on 0.55 mm at J941, J921 and J911; lid off 1.10 mm (J941), 1.60 mm (J921) and 1.60 mm (J911) at typical, and 1.10, 1.46 and 1.46 mm at largest common. Boot-to-boot gaps: 0.30 mm between J941 and J921 and 3.60 mm between J921 and J911 at both envelopes.

**Wire bend room.** For the 3.4 mm wire, 5 x 3.4 mm = 17.0 mm (distributor guidance of 3 to 5 times the outside diameter; no maker figure). The boot's end stands 22.0 mm (typical) or 25.0 mm (largest) above the board face, so the boot and its bend need **16.45 mm** (typical) or **19.45 mm** (largest) below the lid face.

**The lid does not come off with receptacles fitted.** With typical receptacles on their blades the lid is free of the boots alone but a straight wire blocks it at a 5.75 mm slide; with the largest common envelope the boots alone block it at a 1.0 mm slide. Pull the receptacles first.

**No dimension another criterion fixes was reduced.** The blade bays were widened (6.5 x 11 to 8.9 x 14.89 mm) and the far wall moved out 1.5 mm to take the boots; the straight line from the nearest Mains copper to the plate (6.328 mm against 2.6), the bare lead's (3.450 mm against 2.6), the slot-mouth clearance (3.0 mm against 2.0), the plate-length arithmetic (84.52 against 85.0) and the case-to-plate margin (0.425 mm against 0.25) all still hold at the model's nominal and at all 64 seating extremes.

**Check against the criterion.**

| Clause | Shown by | Result |
|---|---|---|
| room round each blade for a receptacle with its boot, the boot's size and source stated | *Envelopes used* | stated, assumed |
| pushed on and pulled off along the stated direction, lid on and lid off, touching nothing | `c18.boot_clearance`: 0.55 and 1.10 mm against 0.5 | held by model |
| the wire leaving the boot has a stated bend room | *Wire bend room* | stated |
| the swept envelope is clear at the stated size and at the largest common size the record names | `c18.boot_clearance`, both envelopes | held by model |
| no dimension another criterion fixes is reduced | the last paragraph, each figure from its own check | held |

## Installed orientation (C19)

**Installed orientation, as the owner gave it.** The plate is vertical on the machine's wall. The board projects from it horizontally with its component side facing down. The tray holds the board's bare back, above the parts. The lid closes the underside and comes off downward. In the case frame `+z` is therefore down when installed, the blades point down, the receptacles push on from below, and gravity is `(0, 0, 1)` in the model (`installed:` in `params.yaml`). The case is judged in this orientation, not in the orientation it is printed in.

**Print orientation, stated separately.** Each part prints in the orientation of the table; none of these is the installed orientation.

| Part | Print orientation | Installed orientation |
|---|---|---|
| tray | outer top face down on the bed (floor down, as modelled) | on top, its outer top face up, holding the board's bare back above the parts |
| lid, single-colour form | face down on the bed (turned 180 degrees about u) | on the underside, its face down, coming off downward |
| lid, two-colour form | face down on the bed (turned 180 degrees about u) | on the underside, its face down, coming off downward |

The plate is cut from bar and does not print; no film is made.

**Lid removal, judged installed.** With the plate, case and board already placed at the wall opening, the lid comes off without removing the case or the plate: tilt the far end down 3 degrees about the plate-end toe line, draw the lid out away from the wall 7.8 mm to free the toes, then lower it away. During the tilt the far end drops 4.34 mm; the lowest point drops 4.75 mm when the toes are free, so 4.75 mm of clear space is needed below the case. The model sweeps the lid through 41 poses to a 90 mm slide against the tray, plate, board, parts, blades and the wall opening frame and finds a least clearance of 0.178 mm (worst obstacle the tray, at a tilt of 0.9 degrees), 0.187 mm in the fitted pose. The receptacles are pulled before the lid is lifted (see *The receptacle boots*); the low-voltage cable stays in place (see *The low-voltage cable's exit*).

**Reach of every fixing and each receptacle, judged installed.**

| Fixing | Driver or hand reaches it | Needs the lid off |
|---|---|---|
| lid screw (u 23.75, v 80.50) | from below, straight up the screw's axis, 81.5 mm from the wall plane and 68.8 mm from the opening frame, shaft 5.5 mm | no |
| board screw H1 (u 41.5, v 71.5) | from below, nearest tray 2.75 mm | yes |
| tab screws T921 and T911 (tapped M3 in the plate, u 12.60 and 37.20, z 16.50) | out from the wall, along the plate's face, 5.5 degrees below level at the nominal seating, nearest tray 0.39 mm | yes |
| two tray screws (M3 x 10 countersunk) | from behind the plate, with the plate off the wall | no |
| each blade receptacle | pushed on from below along `-z`, pulled off downward | no (the bays are open on the lid face) |

**Test finger and drip paths of every opening, judged installed.** Stated per opening kind in *Openings and the enclosure*. The drip rule is a 15 degree cone about the installed vertical: a drip falls from above and lands on the tray's closed outer top face, over the board's bare back (no opening, no part under it), which sheds it over the chamfered edges; no straight line within 15 degrees of vertical from outside enters any of the 52 openings, so none reaches the board's mains copper or a mains body. Water running down an outer wall face, and splash, are not modelled. The five other axis directions are reported as information only: with the case mounted lid up (`-z` down) the three blade bays would let a line reach the board, so the case is not to be mounted lid up.

**Heat release, judged installed.** Warm air rises past the board and leaves by the highest openings. The lid's 16 slots are the air inlets, low in the installed case, with 210.8 mm2 of free area; the 25 equal slits high in the two long tray walls are the outlets, with 225.0 mm2 of free area (outlet to inlet 1.067). The inlets are four of the lid's eight streamlines cut through, the middle two each side of the logo, four runs each between three bridges that line up across the lid, the two sides mirror images of each other. The outlets are slits 2.0 mm wide and 4.5 mm high on a 4.2 mm pitch, 15 in the right wall and 10 in the left on the same grid shifted half a pitch, so no sight line runs square through both walls. The vent areas were placed for convection, in low and out high, and were not sized by a thermal calculation: no figure of heat to be shed through them sized them. The inlet area was 230 mm2 before the vents were made mirror-symmetric for the look and is 211 mm2 now; that is owner list item 13. The lid's skin parameters were re-fitted when the pilasters widened (`skins.flow.lines.min_line_mm` 10.5) to keep the eight streamlines, sixteen vents and eight far-end bars the look was judged with; the look is not re-judged. The triacs' 9.09 W is taken by the plate and the machine's wall (see *The plate's material*), not by the case air; the parts that heat the case air are the board-side parts, judged against the enclosure air at 70 degC in `circuit-proof.md`.

**Check against the criterion.**

| Clause | Shown by | Result |
|---|---|---|
| the installed orientation as the owner gave it, four statements | the first paragraph; `installed:` in `params.yaml` | stated |
| the lid removal sweep stated for it | *Lid removal, judged installed*; `c4.lid_sweep` `installed_frame` | stated |
| the reach of every fixing and each receptacle | the table; `c5.fixings_reached_installed`, `c18.boot_clearance` | stated |
| the finger and drip paths of every opening, falling onto the bare back | *Test finger and drip paths*; `c15.drip`, `c15.finger` | stated |
| the heat release through the vents, warm air rising past the board | *Heat release, judged installed* | stated; not sized by calculation |
| each part's print orientation stated separately from its installed orientation | the table | stated |

## The low-voltage cable's exit (C20)

The board's three-way header J931 (pins at u 38.10, 40.64 and 43.18, v 37.2) takes a three-conductor cable from the main board. No record specifies that cable's wire: it is a new cable the owner makes (`schematic-review.md`, row CABLE-1).

**The exit, lid on.** The cable leaves through a notch in the top of the tray's right wall, 8.0 mm wide (v 33.2 to 41.2, centred on the header) and 2.5 mm high (z 18.0 to the wall's top at 20.5), 1.5 mm above the top of a mated housing. The lid's rim drops outside that wall, 0.3 mm off it, and would close the notch; so the rim has a gate over it, cut the full height of the rim, from v 25.0 to 41.4, 16.4 mm long. With the lid on, a line from each of five points across the notch runs outward through the gate to open air and meets nothing (`c4.cable_gate_follows_the_slide`). The exit is at u 50.0, inside the wall opening.

**The lid comes off with the cable in place.** The cable stays in the notch, which belongs to the tray; the gate travels with the lid. The lid is tilted 3 degrees and drawn 7.8 mm away from the wall to free its toes, so the gate leads the notch toward the plate by 8.2 mm (an 8.0 mm lead and the 0.2 mm seam). The model steps the slide in 0.1 mm poses and the gate spans the notch at every one.

**Clearance between the cable and the case's edges along that path.** The cable is taken as filling the notch, which is the largest it can be.

| Edge | Clearance | Where |
|---|---|---|
| the gate's far end, to the notch's far side | 0.20 mm | lid fitted (41.4 against 41.2) |
| the gate's plate end, to the notch's plate side | 0.41 mm | lid drawn out the full 7.8 mm (8.2 less 7.8 x cos 3 degrees) |
| the rim above and below the cable | none stands there | the gate is cut through the rim's full height |
| the lid's underside, over the notch | 0.45 mm above the wall's top when fitted; 1.98 mm further once tilted | 37.80 mm from the tilt line x sin 3 degrees |

The first two are the model's (`least_margin_mm` 0.20). The last is arithmetic from the model's tilt line (v -0.60) and is not a swept check: the model does not carry the cable as a solid. Three wires of 1.3 mm lie 3.9 mm wide in the 8.0 mm notch, so a real cable stands further from the gate's ends than the figures above. On refitting, the wires must lie in the notch before the lid is closed: a wire left on the wall's top beside the notch would be pinched in the 0.45 mm seam.

**Bend room, stated and recomputed.** The header stands upright, so the wires leave the top of the housing toward the lid and turn through 90 degrees toward the right wall. The room the case leaves for that turn, from the model: 3.65 mm from the housing's top (z 16.5, an assumed figure for a mated single-row housing on a 2.54 mm header) to the lid's thickened underside (z 20.15), which is the least over the header, and 4.8 to 9.9 mm from a pin to the wall's inner face (u 48.0). The stated bend room for this cable is **3 times the wire's outside diameter**, the low end of the distributor guidance this record uses for the blade wires (3 to 5 times; no maker figure), taken for a static, low-current signal wire. The case model recomputes the room on the built lid (`c20.cable_bend_room`): rays rise from the top of the mated housing over its whole footprint and the least height at which one meets the lid is the clearance, 3.65 mm. The largest wire outside diameter the bend room supports is that clearance over 3: 3.65 / 3 = 1.217 mm, **1.2 mm** to 0.1 mm rounded down. A raised wire exit or a thicker lid underside changes the figure, and the check reports the new figure (negative controls in the tests).

**Over the seating range.** The board's lean carries the housing with it, so the room changes with the lean: at the range's +1.0 degree (far end up) the housing's top stands higher under the lid and the room is 3.01 mm, which supports 3.01 / 3 = 1.005 mm, **1.0 mm** of wire; at -1.0 degree it is 4.25 mm (1.4 mm of wire). The worst case over the seating range, 3.01 mm and 1.0 mm, is the figure the owner's cable must meet; 1.2 mm is the figure at the nominal seating. The worst case is asserted by the test `test_c20_bend_room_over_the_seating_range_is_least_at_the_far_end_up_lean`, which builds the model at each end of the lean range, and by the controls that break the geometry; it is not a line of `case/out/check-range.json`. That file carries `c20.cable_bend_room` once, at the nominal seating (3.65 mm), and its eight extremes record only whether every check passed there (`all_pass`), not the bend room's figure.

| Wire outside diameter | Room needed, 3 x diameter | Room the case leaves | |
|---|---|---|---|
| 1.0 mm | 3.0 mm | 3.65 mm | within |
| 1.2 mm | 3.6 mm | 3.65 mm | within |
| 1.3 mm | 3.9 mm | 3.65 mm | 0.25 mm short |
| 1.5 mm | 4.5 mm | 3.65 mm | 0.85 mm short |

### Finding: the stated bend room supports wire of 1.0 mm outside diameter over the seating range

This is a finding, stated as one. The largest outside diameter of wire the bend room supports is 1.2 mm at the nominal seating and 1.0 mm at the worst lean of the seating range, figures the case model recomputes from the lid's clearance above the header's wire exit. With wire of 1.2 mm outside diameter or less the lid bends the cable no further than the stated room. With thicker wire, or a housing taller than 16.5 mm, the lid presses the wires into a tighter turn than 3 times their diameter. Neither the wire nor the housing is specified by any record. The cable carries the two opto-triac LED currents at 5 V; a tight bend is a matter of the wire's life at the crimp, not of heat. The owner confirms that his cable fits (owner list item 15). No case dimension was changed for this.

**No dimension another criterion fixes was reduced.** The gate is cut from the lid's rim, outside the tray's wall; the notch was already there. The lid sweep (0.178 mm), the slot-mouth clearance (3.000 mm against 2.0), the opening checks (the notch admits nothing; 52 of 52) and every other check hold with the gate in place.

**Check against the criterion.**

| Clause | Shown by | Result |
|---|---|---|
| the cable leaves the closed case | `c4.cable_gate_follows_the_slide`: 5 of 5 points across the notch open to the outside, lid on | held by model |
| the lid is fitted and removed with the cable in place | the same check: the gate spans the notch at every pose of the 7.8 mm slide | held by model |
| the model shows the cable's exit with the lid on | the same check; the renders draw it (`directions/flow-two-side.png`) | shown |
| the cable's own swept path as the lid slides | the cable does not move; the gate's travel over it is checked in 0.1 mm poses | shown, with the notch as the cable's envelope |
| the clearance between the cable and every case edge along that path | the table: 0.20 and 0.41 mm by model, the rest by arithmetic | stated; the lid underside figure is arithmetic, not a swept check |
| no part of the lid or tray traps or bends the cable beyond the bend room the record states | *Bend room, stated* and the finding | the model states the largest wire the room supports, 1.2 mm outside diameter at the nominal seating and 1.0 mm over the seating range (`c20.cable_bend_room`, recomputed from the lid's clearance of 3.65 mm nominal and 3.01 mm worst); **whether the owner's cable fits is his to confirm, owner item 15** |
| no dimension another criterion fixes is reduced | the last paragraph | held |

## The exported case against the board's own model (C21)

**The model frame is left-handed.** The case is built in a working frame of `u = x_pcb - ox` across the board, `v = y_pcb - oy` away from the plate-side edge and `z` up from the component face. KiCad's y runs down the screen in the top view, so `(u, v, z)` is a left-handed frame. Distances, areas and volumes are the same in it as in the object, so every check of `check.py` is unaffected, but a mesh written out in it is a mirror image of the case that fits the board. Until this criterion was written every exported STL, STEP and 3MF, and every render, was such a mirror image. It was found by fitting the old exports to the board's own three-dimensional model: the only fit was the reflection in the Y axis, with a residual of 0.000 mm, and the best proper rotation left the exports more than 10 mm out (more than 30 mm with the lid face up).

**The physical frame, and the one reflection.** Everything that leaves the model is written in the right-handed physical frame `X = u`, `Y = -v`, `Z = z`, reached by a single reflection at the boundary (`case.PHYSICAL`, `case.physical`, `case.physical_mesh`). It is the frame in which `kicad-cli pcb export step` writes the board (`X = x_pcb`, `Y = -y_pcb`, the component face toward `+Z`). The exports are the STEP and STL of every part, the print STLs (the physical STLs turned by the print rotation, a proper rotation), the 3MFs and the plate drawing. The renders and the 2D drawings are drawn from the same frame. The STEP files are written from the same physical shapes, but no test reads one; the tests read the STL, print STL and 3MF files.

**How the board's model is placed.** The board's own model is exported from `heater-wall-board.kicad_pcb` with the output origin at the layout's own origin (`--user-origin 0x0mm`) and cached in `case/board-model/` with the layout file's sha256 (`task hw:case:board-model` regenerates it; the tests fail, naming that task, when the layout file has changed since). `fit.py` moves it to the exported case by a translation alone, taken from the board model itself: the board body's low-X, high-Y corner goes to the origin, and its component face, the plane the tops of the surface-mount pads make, goes to `Z = 0`. No rotation and no reflection is applied, and a board model whose component face looked toward `-Z` is refused, because placing it would take a reflection, the very error this check exists to find. The check reads the files in `case/out/` as a printer or viewer reads them and the board's model; it uses no `(u, v)` of the case model to judge anything. It places the board at the nominal seating (lean 0); the handedness of the exports does not depend on the lean.

**The fit, against the board's own model.** `python fit.py` (`task hw:case:fit`) names every result with its figure, expectation and tolerance. Tolerances follow what the meshes resolve: a hole located from a section of an STL is good to about 0.02 mm, so a position is held to 0.05 mm; a distance from sampled surface points to 0.1 mm; the volume two solids may share to 0.5 mm3. 28 of 28 results pass.

| Result | Measured | Tolerance |
|---|---|---|
| `pilot_on_h1_axis` | 0.000 mm | 0.050 mm |
| `bays_hold_blade_pad_holes_lid_single` | 3 of 3 blades inside a bay | none outside |
| `bays_centred_on_blades_across_x_lid_single` | 0.000 mm | 0.050 mm |
| `no_bay_without_blade_lid_single` | 0 bays without a blade | none |
| `bays_hold_blade_pad_holes_lid_two` | 3 of 3 blades inside a bay | none outside |
| `bays_centred_on_blades_across_x_lid_two` | 0.000 mm | 0.050 mm |
| `no_bay_without_blade_lid_two` | 0 bays without a blade | none |
| `plate_inner_face_at_tab_face_distance` | 1.000 mm | 0.020 mm |
| `plate_beyond_the_plate_side_edge` | 1.000 mm | 0.020 mm |
| `tapped_holes_on_triac_middle_leads` | 0.000 mm | 0.050 mm |
| `tapped_holes_at_tab_hole_height` | 0.000 mm | 0.050 mm |
| `slot_mouths_clear_air` | 3.000 mm (at least 2.0) | 0.100 mm |
| `tray_right_wall_at_slot_mouths` | 3.000, 3.000 mm | 0.050 mm |
| `board_body_clear_of_tray` | 0.000 mm3 shared | 0.500 mm3 |
| `board_body_clear_of_lid_single` | 0.000 mm3 shared | 0.500 mm3 |
| `board_body_clear_of_lid_two` | 0.000 mm3 shared | 0.500 mm3 |
| `board_body_clear_of_plate` | 0.000 mm3 shared | 0.500 mm3 |
| `board_lies_on_its_seats` | 0.000 mm2 of tray above the underside | 0.020 mm |
| `logo_reads_right_way_round_lid_single` | 0.950 intersection over union | at least 85 per cent, and 0.4 above every other reading |
| `logo_reads_right_way_round_lid_two` | 0.950 intersection over union | at least 85 per cent, and 0.4 above every other reading |
| `logo_reads_right_way_round_tray_top` | 0.936 intersection over union | at least 85 per cent, and 0.4 above every other reading |
| `exports_watertight_with_outward_winding` | 0 parts failing | none |
| `print_stl_is_the_stl_turned_tray` | at most 0.000 % | 0.5 % and 0.05 mm |
| `print_stl_is_the_stl_turned_lid_single` | at most 0.000 % | 0.5 % and 0.05 mm |
| `print_stl_is_the_stl_turned_lid_two` | at most 0.000 % | 0.5 % and 0.05 mm |
| `3mf_single_objects_are_the_stls` | at most 0.000 % | 0.5 % and 0.05 mm |
| `3mf_two_objects_are_the_stls` | at most 0.000 % | 0.5 % and 0.05 mm |
| `swap_bands_inside_their_base_parts` | 0.000, 0.000, 0.000 mm2 | 0.050 mm2 |

The bays are the lid's openings over the three blades (two bays, one holding two blades, in each lid form), located from a section of the lid at the blades' height and compared with the blades' pad holes in the board's model. The tab faces are the plate's inner face against the triac lead row. The tapped holes, which run through the whole plate, are located in a section of the plate half way through it, the pilot in a section of the tray, all against the board's holes and pads. The last six rows show that the print STLs and the 3MF objects are the same shapes as the exported STLs (volume, area, centre of mass, bounds and inertia, the largest relative difference being the figure shown), and that each swap band lies inside its base part. They are tessellation noise only, no figure of the earlier check moved by more than that.

**Negative controls.** The same functions are handed the exported meshes mirrored in one axis about the board's centre line, with the windings corrected so that only the handedness differs, and the logo check is handed the mirrored artwork. Each must fail the results that locate a feature, and does.

| Control | Fails | Which |
|---|---|---|
| exports mirrored in X | 14 | `pilot_on_h1_axis`, `bays_hold_blade_pad_holes_lid_single`, `bays_centred_on_blades_across_x_lid_single`, `no_bay_without_blade_lid_single`, `bays_hold_blade_pad_holes_lid_two`, `bays_centred_on_blades_across_x_lid_two`, `no_bay_without_blade_lid_two`, `tapped_holes_on_triac_middle_leads`, `tapped_holes_at_tab_hole_height`, `slot_mouths_clear_air`, `tray_right_wall_at_slot_mouths`, `logo_reads_right_way_round_lid_single`, `logo_reads_right_way_round_lid_two`, `logo_reads_right_way_round_tray_top` |
| exports mirrored in Y | 12 | `pilot_on_h1_axis`, `bays_hold_blade_pad_holes_lid_single`, `bays_centred_on_blades_across_x_lid_single`, `no_bay_without_blade_lid_single`, `bays_hold_blade_pad_holes_lid_two`, `bays_centred_on_blades_across_x_lid_two`, `no_bay_without_blade_lid_two`, `plate_inner_face_at_tab_face_distance`, `plate_beyond_the_plate_side_edge`, `logo_reads_right_way_round_lid_single`, `logo_reads_right_way_round_lid_two`, `logo_reads_right_way_round_tray_top` |
| the logo's artwork mirrored | 3 | `logo_reads_right_way_round_lid_single`, `logo_reads_right_way_round_lid_two`, `logo_reads_right_way_round_tray_top` |

The results that locate a feature along X (the tapped holes, the slot mouths and the right wall) fail under the mirror in X, those along Y (the plate's face) under the mirror in Y, and the pilot, the bays and the logo under both.

**The logo reads the right way round.** The viewer it is derived for stands in front of the wall the plate is on, facing it. In the physical frame the wall is toward `+Y` and, installed, gravity is `+Z`, so the viewer's forward is `+Y`, up is `-Z` and right is `-X`. The lid's face looks down, seen from below with the wall at the bottom of the view: the artwork's right runs along `-X` and its up along `-Y`. The tray's outer top face looks up, seen from above with the wall at the top of the view: right along `-X`, up along `+Y`. `fit.py` cuts the grooves from the exported mesh at mid groove depth and compares them, by intersection over union on a raster after a search over offsets, with the engraving made from the artwork and with its two mirror images and its half turn. The lid's grooves read 0.950 against the artwork and 0.275, 0.300 and 0.338 against the X mirror, the Y mirror and the half turn; the tray top's read 0.936 against 0.201, 0.191 and 0.244. The reading must reach 85 per cent and beat each other by 0.4. This turned the lid's logo half a revolution from the earlier renders, which were drawn with the wall toward the top of the lid view; the owner list says so (item 9).

**Renders and drawings.** `render.py` draws the model's meshes through the same reflection (a test holds them equal to the exported STLs) and writes its cameras, lights and up vectors in the physical frame, and the 2D drawings are drawn as true views from the side they name. Every render before this change was a mirror image and is now the true view. In addition, the views straight at a logo face are drawn as the installed viewer in front of the wall sees them: the `lid` view and the lid logo close-ups (`logo-lid-30` and `logo-lid-60`) now have the wall at the bottom of the picture, which is what a viewer under the machine sees, where they had it at the top; the `top` view and the tray logo close-ups have the wall at the top, with `+u` to the left in both. The case drawings' plan is drawn from the lid side with the plate at the top, where it had been drawn with the plate at the bottom and was a mirror of its own label.

**The checks that stay as they were, and why.** Some existing checks are stated in terms where a reflection could matter. Each is stated in the board's own axes or along `z`, so none changes: the lid slides along `v` and the sweep's clearances are distances; the cable gate and notch are at the header's side of the board (high `u`, the header J931 at `u` 38.10 to 43.18); the hold-down finger, the boots over the blades, the slot mouths and the tab holes are placed from board features by their `(u, v)`, and the fit above checks that they land on those features in the exported files; the drip and gravity rules and the installed orientation are along `+z`, which the reflection in `v` leaves alone. The names *left wall* (low `u`) and *right wall* (high `u`) are as seen from the lid side with the plate at the top, the way the board's layout is drawn, and mean the same walls as before.

**Limits.** The fit is made at the nominal seating, lean 0. The handedness of the exports does not depend on the lean, and the lean-dependent features are the subject of *Seating range* (C16), checked in the model at the 64 extremes. The board's model carries the board body, its holes and slots and the pads as thin solids; the footprints carry no component models, so the check places no part body and the triacs' own bodies are not compared. The logo check reads the artwork the case was built from; whether the artwork is the Staircase mark is the judge's (C13).

**Check against the criterion.**

| Clause | Shown by | Result |
|---|---|---|
| the exported meshes are right-handed physical shapes | the physical frame and its single reflection; `exports_watertight_with_outward_winding` (watertight, consistently wound, positive signed volume) and the print and 3MF results, all read from the STL, print STL and 3MF files | held by test for the STL, print STL and 3MF files; the STEP files are written by the same export from the same physical shapes, are not committed (they are regenerated by the export task), and the tests check that their names are among the export's written files but read no STEP geometry |
| each case feature that depends on a board feature lies on it within a stated tolerance, against the board's own model exported from its KiCad file | the fit table: the bays, the triac tab faces and lead pad holes, the mounting-hole pilot and the slot mouths, each at 0.05 mm or its stated tolerance | held by test |
| the logo reads the right way round when the lid is viewed from below in the installed orientation | `logo_reads_right_way_round_lid_single`, `logo_reads_right_way_round_lid_two` and `logo_reads_right_way_round_tray_top`, with each mirror image and the half turn beaten by 0.4 | held by test |
| the check runs on the exported files and the board's exported model, not on the case model's own frame, and a control that mirrors one exported axis makes it fail | *How the board's model is placed* and *Negative controls*: the mirror in X fails 14 results, the mirror in Y 12 and the mirrored artwork 3 | held by test |
| the renders and the record's views are drawn from the same physical frame | *Renders and drawings*; the scene of `render.py` is the exported STLs, and its cameras are in the physical frame; the plan drawing's outline and pillars and the plate drawing's tapped holes are each compared with the exported meshes, each against a copy of the drawing mirrored in X or Y that must fail | held by test for the renders, the plan and the plate drawing; the side and end elevations of `case-drawings.svg` are not compared with the meshes by any test; the pictures themselves are not judged again |

## Owner list

1. Earth strap: decide a dedicated earth strap or the wall alone, and write his words and the date in the field of *The plate's earth bond*. The recommendation is a strap.
2. Measure the delivered triacs' seating: each tab-hole height, lean and the difference between the two; trim the leads to 2.0 mm; the tray is printed to the measured values.
3. Confirm the tapped M3 tab holes in the plate, tapped through at the measured height, in place of the slot or oversize hole he ruled on 2026-11-24, recorded and signed on his behalf in `owner-sign-off.md` W-19, or say otherwise.
4. Plate size: a standard 20 x 5 mm flat aluminium bar cut to 85 mm (at least 84.5 mm; lower edge 6.0 mm above the board face on the tray's ledge, upper edge 26.0 mm; the case holds from 16.8 to 27.5 mm, standard widths 20 and 25 mm; read the stock's width tolerance from the supplier's standard when the bar is sourced), provisional until the wall is cut and measured; two countersunk M3 holes from the back face for the tray at z 11.65, marked from the printed tray with the bar on the ledge, the inserts set flush first, and one M4 wall bolt at each end; the earth bond now rests on two bolts (W-19).
5. Plate temperature: accept ASA on the grounds that the 104.8 degC bound is continuous duty the machine does not run, or name another material. No bring-up criterion measures the plate; say whether it is to be read at bring-up, with 85 degC as the threshold for changing the material.
6. Flame rating: ASA is HB and no rating is asked of the case; accept HB or name a flame-retardant filament.
7. Measure the boots he will fit; the envelopes are assumed.
8. Confirm that the traced logo vector may be published in the public repository.
9. Say which face he sees with the machine open: the logo is on both the tray top and the lid. The lid logo is set upright for a viewer in front of the wall looking up at the lid, half a revolution from the earlier renders; the signs in `Engraving.placed` of `logo.py` reverse that if he looks from elsewhere.
10. Colour: two-colour, or single-colour in stone or in bone. The judge leads with two-colour and recommends stone for one filament.
11. Two-colour: accept the pinstripe on each chamfer and the two filament changes per part (at 0.4 and 1.0 mm) as a feature, or say otherwise. One print of each part proves the stripe and the tray logo's bone floor.
12. Outline: the far-corner radius is 11.5 mm (it was 13), a slightly squarer far end, so that the lid's rim runs unbroken round both corners.
13. Inlet area: the lid's inlets are 205 mm2 (they were 230) so that the vents are mirror images; the outlets are 225 mm2. Say so if the area is wanted back: the route is a 1.2 mm slot, which thins the web between slots to 0.85 mm.
14. Cable gate: the lid's rim is open for 16.4 mm on the right side so that the cable leaves and the lid comes off with the cable in place. The judge finds it oversized and plain; accept it, or ask for it to be dressed.
15. Cable: confirm that your three-way cable fits. The case's bend room supports wire of 1.0 mm outside diameter at most over the seating range, 1.2 mm at the nominal seating (3 times the diameter in the 3.01 mm worst, 3.65 mm nominal, the lid leaves above a 16.5 mm housing, recomputed by the case model); no record specifies the wire or the housing.
16. The receptacle boots, their wires and the cable drawn in the renders are assumed shapes and colours; they follow items 7 and 15.
17. The receptacle-off residual and its rule (never energise with a receptacle off a blade) were accepted by the owner on 2026-11-26 (his answer: "Accept, state the rule (Recommended)"); listed here for the record.
18. Check the depth the case and plate add behind the board at assembly.
19. The physical demonstrations (lid removal, terminal push-on) belong to the delivered-board leaf.
