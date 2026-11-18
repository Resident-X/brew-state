# Sweep log: heater wall board records, schematic review round 8

Dated 2026-11-19. One section per finding of round 8 (`schematic-review.md`, "Round 8"), recording the class sweep the correction owed (the class "stale or contradictory statements left behind by an incomplete sweep" recurred in rounds 5, 7 and 8). Scope of every search: `hardware/sunbeam-em7000/` and `docs/sunbeam-em7000/`, files `*.md`, `*.yaml`, `*.py`, `*.log`. `schematic-review.md` is searched too and its counts are given apart: its rounds 1 to 8 are frozen history (they quote what a round judged) except the Closed by cells, which are live records and were corrected where they were wrong. Searches are case-insensitive regular expressions run by a script over every line; counts are lines (matches in brackets where they differ) in the working tree after the corrections of this round. Classification: **fixed** (changed in this round), **legitimate** (stays, with the reason), **frozen** (history in a review round, not edited).

## 8.1 Records say the owner is to sign the W-3 residual (signed 2026-11-18, `owner-sign-off.md` W-3)

Search terms, three passes:

1. Phrase pass over the scope outside `schematic-review.md`: `to sign`, `owner's to sign`, `his to sign`, `asked to sign`, `asks the owner`, `for the owner to`, `owner to (sign|accept|decide|confirm)`, `awaiting`, `pending`, `unsigned`, `not yet signed`, `yet to (be )?sign`, `owner is asked`, `he is asked`, `are for the owner`, `is for the owner`, `on his behalf`, `on behalf of`, `signature`, `recommended .keep`, `recommended closed`, `not an acceptance`: 367 lines, filtered to the topic `W-3|W-5c|W-6|W-7|D7|RV911|RV921|varistor|340 W|stuck-on|2.0 A`: 30 lines (all classified below).
2. Exact stale phrasings before the corrections: `owner to sign|owner's to sign|for the owner to sign|signature pending` found 8 lines outside `schematic-review.md` before the corrections (counted on the committed tree, HEAD 08d3fd23), `recommended .keep|recommended closed` 4 lines, `asked to sign` 2 lines; after the corrections the same terms leave 1, 0 and 1 line (controller-board-division.md:153, 'the basis amendment is the owner's to sign', the owner's own act still to come, and open-items.md:16, followed in its cell by the W-4 acceptance), both legitimate.
3. Topic pass on `W-3` (28 matches outside `schematic-review.md`) and `D7` (450 matches, most of them the unrelated `D7.*` sensor items of `reference-machine.md` and the main board) read line by line for the stale statement.

Instances of the stale statement (owner still to sign something already signed): 8 lines, all fixed. The reviewer named 5; the sweep found 3 more.

| File:line | Statement | Class |
|---|---|---|
| heater-wall-board/circuit-proof.md:23 | row (d) Met cell, 'the residual risk is the owner's to sign (D7)' | fixed (named) |
| heater-wall-board/constraints-figures.md:17 | 'residual risk and the firmware stuck-on threshold for the owner to sign' | fixed (named) |
| docs/sunbeam-em7000/controller-board-division.md:127 | D7, 'are for the owner to sign'; also 'recommended closed as keep' | fixed (named) |
| docs/sunbeam-em7000/controller-board-division.md:148 | D7 row, 'for the owner to sign' | fixed (named) |
| docs/sunbeam-em7000/controller-board-division.md:1000 | 'is the owner's to sign' | fixed (named) |
| docs/sunbeam-em7000/controller-board-division.md:833 | 'D7 is recommended closed as keep, the owner's signature pending' | fixed (found by the sweep) |
| docs/sunbeam-em7000/controller-board-division.md:1137 | 'D7 recommended keep, the owner's signature pending' | fixed (found by the sweep) |
| docs/sunbeam-em7000/controller-board-division.md:153 | D15 row, 'the owner is asked to sign the entries' (same class for W-4, signed in his words 2026-11-18) | fixed (found by the sweep) |

An amendment note was added at docs/sunbeam-em7000/controller-board-division.md:137 (D15 heading line: the pair entries accepted, W-4; the basis re-declaration still to come). Not a stale statement, added so the D15 text agrees with line 153.

Remaining hits of pass 1 (topic-filtered, 27 lines: 26 not changed, and :127, changed above but whose 'Owner decision pending' label stays), each classified:

| File:line | Class and reason |
|---|---|
| heater-wall-board/constraints-figures.md:20 | legitimate: the new outer-face row; 'end-of-work list' is its own statement, not W-3 |
| heater-wall-board/open-items.md:3 | legitimate: says where a row says the owner is asked, `owner-sign-off.md` states what he accepted (an accurate pointer) |
| heater-wall-board/open-items.md:16 | legitimate: D15 'asked to sign' is followed in the same cell by 'Amended 2026-11-18: accepted by the owner (W-4)' |
| heater-wall-board/open-items.md:46 | legitimate: the basis re-declaration before ordering is the owner's act and is still to be done (W-8(a)) |
| heater-wall-board/open-items.md:94 | legitimate: the new outer-face paragraph |
| heater-wall-board/owner-sign-off.md:5 | legitimate: defines 'signed on behalf' (W-5a, W-5b, W-5d) |
| heater-wall-board/owner-sign-off.md:37 | legitimate: W-5b is signed on behalf and is on his end-of-work list |
| main-board/circuit-proof.md:246 | false hit: 'pending the lead's sum', a budget table |
| connector-pinouts.md:586, 587, 588 | false hits: 'Pending' beta value of sensors (`D7.*` items) |
| controller-board-cost-estimate.md:224 | false hit: a capacitor 'priced pending' the main board's decision |
| controller-board-design-constraints.md:139 | legitimate: points to the section 'Pending marks'; the source impedance is open |
| controller-board-division.md:55, 119, 247, 831 | legitimate: D2 (confirms) is genuinely pending |
| controller-board-division.md:60 | legitimate: D14 and D16 withdrawn from the pending list |
| controller-board-division.md:115 | legitimate: describes the record's own check of the 'Owner decision pending' label |
| controller-board-division.md:127 | legitimate for the label 'Owner decision pending' on D7 and D15 (137): the record's own check requires the words on every listed decision; each now carries an Amended note stating the signing |
| controller-board-division.md:778 | legitimate: D9 genuinely pending |
| controller-board-division.md:827 | legitimate: the wall cut window 'is not an acceptance of a final size' (D11, preliminary) |
| controller-board-division.md:1127 | legitimate: main board exceptions, other board |
| controller-board-division.md:1153 | frozen: a dated list of what round 5 left pending |
| controller-board-division.md:1289, 1292 | legitimate: describe the check's own statements |
| reference-machine.md:161 | false hit: beta value 'pending' for `D7.*` sensor items |

`schematic-review.md` (all rounds): the phrase pass finds 7 lines touching the topic (657, 671, 803, 941, 1082, 1084, 1110): all frozen round text quoting the stale statement as a finding or its sweep inputs. Lines 113, 237 (Closed by cells) carry no stale 'to sign'.

The same class sweep for W-6, W-7 and W-5c: `W-6|W-7` near `sign|ask|pending|await|behalf` outside `schematic-review.md`: no stale statement (hits are the accepted entries themselves and the 'Accept 1 2 and 3' citations in `circuit-proof.md`, `derating-policy.yaml`, `open-items.md`, `owner-sign-off.md`). W-5c is in section 8.3.

## 8.2 Wrong criterion citations

Search terms: `BRING-UP\.C13`, bare `C13` (not preceded by a letter or digit, so PC13 and C130 are not counted), `BRING-UP\.C11`, `BRING-UP\.C6`, `HEATER-WALL-BOARD-DESIGNED\.C19`, `four-wire`, and `names C13|cite C11|cite C6|name C13`. Criterion text read with `show` this round: `DEL-HW-BRING-UP.C6` (four-wire measurement from each touchable conductive part to the earth contact of the supply inlet at a stated test current, compared with the declared figure), `C11` (thermocouples record each hot part's temperature at sustained full heat and each settled reading, corrected to the top of the ambient span, is within the part's derated limit), `C13` (probes where the boards sit record the air temperature at sustained full heat; the highest settled reading, with the room temperature and instrument accuracy, is no higher than the figure the parts were graded to); `DEL-HW-HEATER-WALL-BOARD-DESIGNED.C19` (the record states the surge rating the heater branch relies on once the clamps are dropped, sourced from the entry varistor); `REQ-ELECTRICAL-INSTALL-001.C10`; `REQ-ACTUATION-CONFIRMATION-001.C10`.

Counts: bare `C13` 27 matches on 25 lines outside `schematic-review.md` (of which 16 lines are the main board's capacitor C13 and unrelated nodes, 1 is a main-board `DEL-HW-BRING-UP.C13` citation), 38 matches on 30 lines in `schematic-review.md`. `DEL-HW-BRING-UP.C13` citations outside `schematic-review.md`: 17 lines at HEAD, 16 now (owner-sign-off.md:53 no longer names C13 as the earth bond's criterion; it says C13 is not cited for it). Bare `C13` 25 lines at HEAD and now. `DEL-HW-HEATER-WALL-BOARD-DESIGNED.C19`: 2 lines outside `schematic-review.md` at HEAD and now (owner-sign-off.md:30 and 54, both now stating C19 is not asked of the carry), 6 lines in `schematic-review.md` (2 Closed by cells fixed, 4 are round 8 text quoting the error).

Every C13 citation outside `schematic-review.md`, with its subject (the subject is what the text is about; C13 asks for the enclosure air only):

| File:line | Subject | Class |
|---|---|---|
| heater-wall-board/circuit-proof.md:11 | the 70 degC enclosure air assumption | legitimate |
| heater-wall-board/constraints-figures.md:9 | enclosure air and, in the same cell, the part temperatures at the wall board | fixed: C13 for the air, C11 for the part temperatures (named) |
| heater-wall-board/derating-policy.yaml:19, 32 | enclosure air graded at 70 degC | legitimate |
| heater-wall-board/owner-sign-off.md:51 | 2.8 row: C11 for the opto-triac cases, C13 for the air figure | legitimate |
| heater-wall-board/owner-sign-off.md:53 | the 1.4 and 2.3 row said W-4 and bring-up-provision.md name C13 for the earth bond | fixed (named): W-4 names C6, bring-up-provision.md now names C6 |
| heater-wall-board/owner-sign-off.md:60 | 'Citations corrected' bullet said bring-up-provision.md and W-4 cite C11 and C6 | fixed (named): the bullet now states what each file cites |
| heater-wall-board/circuit-proof/W_margins.py:31 | enclosure air assumption | legitimate |
| main-board/error-budget.md:22 | enclosure air 70 degC measured at bring-up | legitimate |
| controller-board-design-constraints.md:341, 349, 446, 453 | enclosure air temperature (453 names C11 for the part temperatures beside it) | legitimate |
| controller-board-division.md:837 | enclosure air assumption | legitimate |
| controller-board-division.md:1006 | 'the air at the wall board and h are measured at bring-up (C13)': C13 asks for the air only, not h | fixed (found by the sweep): C13 for the air, C11 for the part temperatures, no criterion asks h itself |
| controller-board-function-forms.md:16, 273, 289 | enclosure air assumption | legitimate |
| main-board/circuit-proof.md:232, circuit-verdicts.md:593, schematic-spec.yaml:3469, sheets/E1-...yaml:26 | capacitor C13 or 'C13-class reading': not a criterion citation | false hits |
| main-board/schematic-review.md:4487, 6120, 7486 | `REQ-ELECTRICAL-INSTALL-001.C13`; capacitor C13 | false hits |

In `schematic-review.md`: C13 citations at 117, 135, 236, 241, 361, 362, 395, 400, 503, 504, 635, 636, 772, 773, 817, 830, 916, 917, 933, 959, 975, 1059, 1060, 1076, 1103, 1110 are frozen round text (lines 117, 241 and 400 give C11 and C13 for the opto-triac rise, correct; 236 and 395 give C13 for the earth bond in rounds 2 and 3 and are frozen history of the error the 'Citations corrected' bullet and finding 7.2 record; 940 and 1083, 1093 are findings text). The 7.2 Closed by cell now names its completion under 8.2 and this log.

Earth-bond statement found by the sweep beyond the reviewer's list: `bring-up-provision.md` row 25 (the earth-bond measurement) named no criterion and stated neither the four-wire method nor a test current, which `DEL-HW-BRING-UP.C6` asks. It now names C6, the four-wire method and a stated test current, so the corrected owner-sign-off statements are true.

`DEL-HW-HEATER-WALL-BOARD-DESIGNED.C19` (what it asks: the surge rating relied on once the clamps are dropped; the clamps are kept, D7): owner-sign-off.md:54 (carries cell and 'What the criterion asks' cell) fixed; owner-sign-off.md:30 (W-8(b), 'as before') fixed to say C19 is not asked of the carry and the carry rests on `REQ-ELECTRICAL-INSTALL-001.C10` and `REQ-ACTUATION-CONFIRMATION-001.C10`; schematic-review.md Closed by cells of 1.5 (line 113) and 2.4 (line 237) fixed the same way. Remaining C19 mentions in `schematic-review.md` (lines 955, 1076, 1083, 1098, round 8 text; earlier rounds' Verdicts) are round 8's own statement of the error. `circuit-proof.md:57, 60` and `controller-board-cost-estimate.md:346, 347` match `C19` as the main board's criterion `SOL-HW-MAIN-BOARD-PROVEN-AND-LAID-OUT.C19` and a part number: false hits.

## 8.3 W-5c contradicts itself and records no source

Search terms: `not an acceptance`, `W-5c`, `accepted it against|he accepted|facts for the owner`, `accept 2\.7`, `3\.9 (to|-) ?4\.5`, `7\.95|4\.88 to 5\.46`, `short of the steam|under either reading|either reading of ST`. Counts: `not an acceptance` 3 lines outside `schematic-review.md` (at HEAD: 4), 1 in it (round 8 text); `W-5c` 5 lines outside (owner-sign-off.md:5, 14, 29, 50 and circuit-proof.md:24), 35 in `schematic-review.md`; `accept 2.7` 1 line (owner-sign-off.md:29); `3.9 to 4.5` 1 line outside (owner-sign-off.md:29, marked superseded), 2 in `schematic-review.md`.

| File:line | Class and reason |
|---|---|
| owner-sign-off.md:29 | fixed (named): the 'facts for the owner (not an acceptance)' heading is gone; one statement of what he was shown (the 25 and 40 degC external-air basis, the steam-alone and both-on tables, the 7.95 A at 25 degC and 4.88 to 5.46 A at 40 degC current shares, the worst-case duty he named) and his reply "accept 2.7 with the bring-up case-temperature measurement and the cut-time checks of the wall's grade and thickness", accepted_by David Baker, accepted_on 2026-11-19, carried to `DEL-HW-BRING-UP.C11` and `DEL-HW-HEATER-WALL-BOARD-DESIGNED.C22`; the 3.9 to 4.5 A basis marked superseded |
| owner-sign-off.md:14 | fixed (found by the sweep): the 'Look at these first' bullet said the share is 'short of the steam element's current under either reading', true only of the superseded 45 degC basis (at 25 degC the share is 7.95 A against 5.38 A); it now gives the figures he was shown |
| owner-sign-off.md:5, 50 | legitimate: say he accepted W-5c in his words and carry it to C11 and C22 |
| circuit-proof.md:24 | legitimate: 'Owner-held (D11; W-5c)' sits in the superseded 45 degC history of row (e), labelled as history |
| controller-board-division.md:24, 827 | legitimate: 'not an acceptance of a final size' is the D11 cut window, a different statement |
| main-board/schematic-review.md:8279 | legitimate: main board M18, unrelated |
| circuit-proof/W_margins.log:54 and W_margins.py:197 | legitimate: the generated record's section (e) history for the 45 degC best case ('SHORT under either reading'); generated, not edited |

## Suggestion of round 8 (outer-face temperature of the wall at the patch)

Search before writing, on the committed tree: `outer face of the (steel|metal) wall|touchable.{0,40}wall|wall.{0,40}touchable|outer-face temperature|wall's outer face|external face` over the scope outside the main board: 5 lines (schematic-review.md:966, which is the reviewer's own note that no record gives it; controller-board-division.md:63, 860, 921, which concern the air at the outer face, not its temperature): no record stated the touchable temperature. Statement added to `constraints-figures.md` (table row) and `open-items.md` ("Bring-up measurements carried" section). Arithmetic: R_wall = 6.30 K/W at h = 10 (`controller-board-division.md`, § The heater wall assembly, judged, and `circuit-proof/W_margins.py` E_R_WALL), P = 9.09 W both triacs: 9.09 x 6.30 = 57.3 K over the external air, 82 degC at 25 degC and 97 degC at 40 degC; at h = 5, 9.09 x 9.32 = 84.7 K. The duty and the idle-hold power are unsourced. Not a carried finding and no criterion; for the owner's end-of-work list.
