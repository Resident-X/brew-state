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
| heater-wall-board/constraints-figures.md:20 | fixed (round 9, finding 9.4): the row said 'the owner's end-of-work list', which held no such item; it now names item 4 of owner-sign-off.md 'For David to sign or confirm at the end of the work' |
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

Search before writing, on the committed tree: `outer face of the (steel|metal) wall|touchable.{0,40}wall|wall.{0,40}touchable|outer-face temperature|wall's outer face|external face` over the scope outside the main board: 5 lines (schematic-review.md:966, which is the reviewer's own note that no record gives it; controller-board-division.md:63, 860, 921, which concern the air at the outer face, not its temperature): no record stated the touchable temperature. Statement added to `constraints-figures.md` (table row) and `open-items.md` ("Bring-up measurements carried" section). Arithmetic: R_wall = 6.30 K/W at h = 10 (`controller-board-division.md`, § The heater wall assembly, judged, and `circuit-proof/W_margins.py` E_R_WALL), P = 9.09 W both triacs: 9.09 x 6.30 = 57.3 K over the external air, 82 degC at 25 degC and 97 degC at 40 degC; at h = 5, 9.09 x 9.32 = 84.7 K. The duty and the idle-hold power are unsourced. Not a carried finding and no criterion; an item for the owner to confirm or act on, item 4 of owner-sign-off.md 'For David to sign or confirm at the end of the work' (round 9, finding 9.4).

## 2026-11-19 round 9 (findings 9.1 to 9.4 and the record under 8.3)

Scope: every file under `hardware/sunbeam-em7000/` and `docs/sunbeam-em7000/` except `.kicad_*`, images and archives (the search was made after the corrections below, on the working tree). Method: the structure of `owner-sign-off.md` was rebuilt by a script that reads each entry's `accepted_by` and `accepted_on`, places it by who accepted and then by day, and writes the headings and the counts from that grouping, so no count in a heading is typed by hand (the result: 11 entries, 8 in the owner's own words, 4 on 2026-11-18 and 4 on 2026-11-19, and 3 signed on behalf). Then each pattern below was searched over the whole scope and every hit was classified. Groups: **live** (records and generated files other than those named separately), **osf** (`owner-sign-off.md`), **review** (`schematic-review.md`, frozen round text: a round's wording is the record of what was judged then and is not corrected, only the Closed by cells are), **sweep** (this file), **main** (`main-board/`, whose W-numbers, behalf signings and words are that board's own list and not this board's).

| Pattern | live lines (files) | osf | review | sweep | main | Classification |
|---|---|---|---|---|---|---|
| `W-1` | 10 (3) | 4 | 65 | 0 | 220 (3) | live: pointers to W-1 to W-4 as the owner's words of 2026-11-18 (accurate); main: the main board's own W-list, false hits |
| `W-2` | 7 (5) | 8 | 24 | 0 | 0 | accurate pointers (constraints-figures, layout-hedges, open-items, circuit-proof, derating) |
| `W-3` | 19 (5) | 6 | 172 | 4 | 0 | pointers accurate; the 340 W statements among them are the next row |
| `W-4` | 14 (6) | 9 | 135 | 6 | 0 | accurate pointers |
| `W-5` (any suffix) | 9 (4) | 23 | 129 | 8 | 0 | no bare `W-5` stands outside `owner-sign-off.md` line 5 (which names the split) and frozen round text; W_margins.py and W_margins.log (the bare `W-5`, finding 9.2b) fixed to name W-5c |
| `W-6` | 11 (3) | 6 | 92 | 2 | 0 | accurate pointers; the entry itself moved to the owner's-words section (9.1) |
| `W-7` | 11 (4) | 6 | 77 | 2 | 0 | accurate pointers |
| `W-8` | 1 (1) | 7 | 46 | 2 | 0 | open-items.md line 3 omitted W-8: fixed (9.2a) |
| `340 W` | 0 | 0 | 51 | 1 | 0 | after the corrections no live line says a bare 340 W; the review lines are round text and this file's one is the 9.3 row |
| `340.5` | 7 (5) | 1 | 20 | 0 | 0 | the corrected statements, each saying 340.5 W in the varistor, about as much again in the element, 681 W together where the element is named |
| `on his behalf` | 1 (1) | 3 | 11 | 1 | 1 | live: separation-basis.yaml (its own 2026-11-14 and 2026-11-18 entries, not this board); osf: the definition and W-5a, W-5b and W-5d only |
| `on the owner's behalf` | 7 (4) | 1 | 47 | 0 | 12 (8) | live: open-items.md 59 and 60 (W-5a, W-5b: correct), circuit-proof.md 58 and 112 (W-5b, correct), controller-board-division.md two lines about the 2026-11-14 basis signing (a different matter, correct) |
| `his own words`, `own words`, `in his words` | 5 (3) | 5 | 48 | 0 | 7 (3) | live: accurate (W-3, W-4, W-6, W-7 words with their day); two hits of controller-board-division.md are 'the forms record's own words' and a code docstring: false hits |
| `only words of his` | 0 | 0 | 2 | 0 | 0 | fixed (9.1a): the claim is gone from `owner-sign-off.md`; the two review hits are the finding text |
| `end-of-work`, `end of the work` | 2 (2) | 2 | 8 | 3 | 0 | the owner's list of items to confirm: now holds four items (W-5a, W-5b, W-5d and the outer-face figure); constraints-figures.md 20, open-items.md 94 and sweep-log.md 32 and 105 fixed (9.4) |
| `to sign` | 5 (3) | 1 | 7 | 12 | 1 | live: open-items.md 16 and controller-board-division.md 153 and 825 are D15 text followed by their Amended note (history, labelled); the rest are phrases in this file's own searches |

Fixed in this round, with the line counts: `owner-sign-off.md` (rebuilt, entries unchanged except the W-3 figure and the W-5c source sentence; the 'Look at these first' bullet for W-5c now names the section for behalf signings); `open-items.md` 4 lines (3, 26, 29, 94); `circuit-proof.md` 3 lines (23, 24, 72); `layout-hedges.md` 1 line (13); `controller-board-division.md` 1 line (1000); `constraints-figures.md` 1 line (20, two cells); `circuit-proof/W_margins.py` 2 lines (the section (d) print and the section (e) note; re-run with every result identical, the log differing in exactly those two note lines); `circuit-proof/W_margins.log` 2 lines; this file 2 rows. 15 lines in 8 files in all, besides the rebuilt record.

8.3 (the source of what David Baker was shown): `owner-sign-off.md` now ends with the section 'What was put to the owner before W-5c', which quotes the thermal-records message of 2026-11-19 verbatim, states the content of the earlier message of the same day and his three statements verbatim, says both were sent before his reply and that the figure files (commit 4d8469bc) precede it, and says the record cannot prove he read them while the session transcript holds both messages and his replies. W-5c cites that section.

## 2026-11-19 round 10 (findings 10.1 to 10.3 and the two plain errors of the suggestions)

Scope: every `.md`, `.yaml`, `.py` and `.log` file under `hardware/sunbeam-em7000/` and `docs/sunbeam-em7000/`, searched after the corrections below on the working tree, excluding this heater wall board's `schematic-review.md` (round text, frozen) and this file. Counts are lines (files).

| Pattern | Hits | Classification |
|---|---|---|
| `D11.{0,120}(accepted\|his words\|own words)` | 10 (4) | 3 hits in `circuit-proof.md`, `W_margins.py`, `W_margins.log` are the corrected text (D11 accepted as preliminary on 2026-10-28; finding 2.7 accepted 2026-11-19); the other 7 are `controller-board-division.md` (D11 row, owner-intent row, its own checks): correct, 2026-10-28 |
| `(accepted\|his words\|own words).{0,120}D11` | 8 (4) | `circuit-proof.md` row (e) corrected; `controller-board-division.md`, `controller-board-design-constraints.md`, `controller-board-function-forms.md`: the 2026-10-26 to 2026-10-28 cut acceptance, correct |
| `wall cut.{0,80}(accepted\|his words).{0,60}2026-11-19` | 2 (2) | the two W_margins notes, now corrected (fixed: 2 lines) |
| `D11.{0,200}2026-11-19` | 4 (4) | `circuit-proof.md` row (e), `W_margins.py`, `W_margins.log`: corrected, each now says 2026-10-28 for D11 and 2026-11-19 for finding 2.7; `open-items.md` 77: the revisit of the cut, no acceptance dated: correct |
| `2026-11-19.{0,200}D11` | 0 | none |
| `two readings` | 6 (6) | `owner-sign-off.md` 98 now says the two readings are not in message 1 (fixed); the other 5 are different matters (main-board M36, the bracket's two forms, component-specification, design constraints, connector pinouts): false hits |
| `h = 5.{0,60}(shown\|put to\|tables)` | 1 (1) | `owner-sign-off.md` 98, the corrected appendix line |
| `(shown\|put to him).{0,200}h = 5` | 7 (4) | `owner-sign-off.md` 19, 36 (fixed to message 1's content) and 98; `circuit-proof.md` 24, `constraints-figures.md` 12, `controller-board-division.md` 877, 969, 971: derived figures of the amendment, none says he was shown them: legitimate |
| `firmware reports` | 0 | the 10.3 sentence is gone |
| `same run` | 5 (4) | `bring-up-provision.md` 22 and 23 (23 is the corrected row), `constraints-figures.md` 20, `open-items.md` 94: other matters: legitimate |
| `2\.0 A.{0,80}(checked\|tested\|measured)` | 0 | no other statement says the 2.0 A threshold is tested at bring-up; `open-items.md` 29 states it as a design requirement with no firmware: legitimate |
| `\band and\b` | 0 | the `and and` of `owner-sign-off.md` 42 fixed; no other |

Fixed in this round, with line counts: `owner-sign-off.md` 4 lines (19, 36, 42, 98: what he was shown cut to message 1's content; the appendix says a subset, not the amendment's figures); `circuit-proof.md` 2 lines (24 D11 date; the Result paragraph cites W-5c as the owner's decision for row (e)); `circuit-proof/W_margins.py` 1 line (197) and `circuit-proof/W_margins.log` 1 line (54), `W_margins.py` re-run, output identical to the log; `bring-up-provision.md` 1 line (23: the threshold detection cannot be tested until the firmware of `REQ-ACTUATION-CONFIRMATION-001.C6` and `.C10` exists; bring-up measures the all-outputs-off current, `DEL-HW-BRING-UP.C23`, and reads a deliberately held-on heater's current as evidence for the firmware's thresholds). Total 9 lines in 5 files, plus 3 rows in `schematic-review.md`.

## 2026-11-19: the mounting form changed (flat spreader plate, plain four-hole board, printed case)

The class swept: statements of the earlier mounting form (two ears on the board's wall edge screwed to a bracket leg above the board, a two-leg bracket, a 13.25 mm earthed-fixing distance, a 57.0 x 42.5 mm body, blades between the triacs) left live in this folder after `DEC-HEATER-WALL-BOARD-IS-A-PLAIN-RECTANGLE-SCREWED-TO-A-PRINTED-CASE-ON-A-FLAT-SPREADER` and the owner's 2026-11-19 blade-edge constraint. Scope: every `*.md`, `*.yaml`, `*.py`, `*.log` and `*.yml` outside `.git`, case-insensitive regular expressions run line by line over the working tree after the corrections. Columns: files with a hit repo-wide (this folder's included); live lines in this folder outside the three frozen or dated records; lines in `schematic-review.md`, `owner-sign-off.md`, `sweep-log.md` (history, left as written). `layout-plan.md` is outside this change's scope and is counted in the first column only.

| Phrasing | Files, repo-wide | Live lines here | History lines here |
|---|---|---|---|
| `\bears?\b` | 12 | 6 | 7 |
| `two mounts` | 6 | 0 | 2 |
| `16 x 7.5` or `16.0 mm wide` | 3 | 1 | 1 |
| `89 mm` or `89.0` | 13 | 1 | 3 |
| `standing leg` | 16 | 3 | 0 |
| `board leg` | 5 | 1 | 1 |
| `\blift` | 39 | 0 | 3 |
| `57 x 42.5` or `57.0 x 42.5` | 9 | 4 | 1 |
| `13.25` | 12 | 3 | 1 |
| `bracket` | 80 | 5 | 28 |
| `\blegs?\b` | 70 | 5 | 1 |
| `along v` | 0 | 0 | 0 |
| `ear mount` | 0 | 0 | 0 |
| `mounting.hole` | 130 | 13 | 5 |
| `two mounting` | 8 | 2 | 2 |
| `between the (two )?triacs` | 4 | 2 | 6 |

What the live lines now are: every remaining live hit in this folder is an `Amended 2026-11-19` note naming the earlier form as superseded (`open-items.md`, `layout-hedges.md`, `constraints-figures.md`, `fabrication-notes.md`, the new part records), the legitimate TO-220 or blade "leg" (a terminal lead), or a mounting-hole record of the new form. The repo-wide files are other boards' records (the main board's lid-screw holes, the 13.25 mm main-board fixing rule, other leaf records), the division and constraints records (annotated, not rewritten), and `layout-plan.md` (not touched here). `circuit-proof/W_margins.py` and its log: "the triac leg 20.0 mm away" now reads "the triac 20.0 mm away", "bracket 0.139 K/W" reads "spreader plate 0.139 K/W"; the script was re-run and its log is unchanged otherwise.

## 2026-11-19: the wall board's mounting-hole count is the layout's, and no screw material is relied on

The class swept: statements that fix four mounting holes (or H1 to H4) as the wall board's count, or that rest a hole's clearance on the screw or its material, left live after the owner's direction of 2026-11-19 (the layout chooses the number and places of the holes, at least three; every hole keeps the pre-order check's `mounting_hole` distance from `Mains` copper whatever the screw; no exception is requested). Corrected in `sheets/300-low-voltage-header.yaml` (the four hole functions and the sheet note, with `schematic-spec.yaml` regenerated by `spec-tools/build_spec.py`), `parts-specification.yaml`, `open-items.md`, `layout-hedges.md` (hedges 13, 14, 15, 17 and the amendment note), `fabrication-notes.md`, `owner-sign-off.md`, and the `Amended 2026-11-19` notes of `docs/sunbeam-em7000/controller-board-division.md` (seven) and `controller-board-design-constraints.md` (two). Scope: `*.md` and `*.yaml` in this folder excluding this file, `schematic-review.md` and `layout-plan.md`, and the two docs named, case-insensitive, line by line, after the corrections. The docs column counts the two docs' whole text, which holds the main board's four machine mounting points and its plastic bosses (a different board, not amended).

| Phrasing | Live lines here | Lines in the two docs |
|---|---|---|
| `four (case\|mounting\|screw)[- ]` | 0 | 7 (main board) |
| `four[- ]hole` | 0 | 3 (main board, history) |
| `H1 to H4` | 19 (each states a starting set or the symbol names) | 9 |
| `nylon` | 2 (hedge 15 and open-items, stating the owner's refusal) | 0 |
| `metal screw\|plastic boss\|into the printed case.s boss` | 0 | 4 (main board) |

The change of count is a pinless-part change in the schematic that the main session makes and verifies with the parity check; the records name H1 to H4 only as the starting set. The wall-board-only run of the pre-order check gives 57 violations before and after this change, the same lines (the board layout is not yet placed), and `check_spec.py sheets` reports 0 errors and 0 warnings.

## 2026-11-19: round 12 findings 12.2 to 12.5 (parts counts, mounting form in two outside records, hedge summary)

The class swept: a record that counts or lists the board's parts as 14 where the netlist holds 21 (14 electrical parts plus H1 to H4 and FID1 to FID3), and a live statement of the earlier ear-and-bracket form outside an amended or history section. Fixed: `circuit-verdicts.md` (21 parts, parts rows 21, total 47 rows, seven sheet 3 rows), `circuit-proof.md` grading table (one not-applicable row for the seven, the heading sentence limited to electrical parts), `open-items.md` (the Rating and LCSC statement corrected; the in_bom exclusion carried to layout stays; 'every part is graded' says electrical), `layout-hedges.md` (hedge 1 void, hedge 2 limit dropped, the others stand), and amended notes added to `docs/sunbeam-em7000/controller-board-cost-estimate.md` (three sections), `controller-board-function-forms.md` (three sections) and `docs/board-design-lessons.md` (the wall board start section).

| Phrasing (docs, hardware, firmware; .md .yaml .py .txt .log, outside this log, schematic-review.md and layout-plan.md) | Files with a hit | Live hits left |
|---|---|---|
| `\bears?\b` | 10 | 0 (every hit is an amended note, history or the division record's annotated sections) |
| `two mounts` | 3 | 0 (division and constraints under their notes; reference-machine.md is the original machine's own lid mounts) |
| `57.0 x 42.5` | 8 | 0 (cost estimate and function forms now noted; board-design-lessons.md now noted) |
| `89.0 mm` | 3 | 0 |
| `standing leg`, `board leg`, `mounting ears` | 8, 3, 6 | 0 |
| `right-angle bracket`, `L bracket`, `2 662` | 3, 1, 2 | 0 |
| `14 parts` | 2 | 0 (circuit-proof.md says 14 electrical parts beside the seven; the cost estimate's 14 parts are priced parts of the whole project, a different count) |
| `40 rows`, `fourteen parts`, `ear mount` | 0 | 0 |

`controller-board-function-forms.md` is read by `firmware/emulation/tests/test_casting_peak.py` (prose guard on the removal-interval wording only); the cost estimate is pinned by no test, generated record or `HOST_READS` entry.

## 2026-11-19: the schematic dropped H2 to H4 and FID1 to FID3 and the four gate resistors are hand-fitted (15 parts)

The class swept: a record that counts the board's parts as 21, names H1 to H4 as a starting set or four holes, or states FID1 to FID3 as present, left live after the layout's decisions of 2026-11-19 (delegated by the owner): one mounting hole (H1) retained by a printed ledge and fingers or lid ribs, no fiducials, the four 1206 gate resistors R911, R912, R921 and R922 hand-fitted, the triacs on `heater-wall-board:TO-220-3_Vertical_Insulated_OvalPads`. Corrected in `sheets/100-coffee-heater-switch.yaml` (footprint, the custom footprint entry, resistors `hand: true`), `sheets/200-steam-heater-switch.yaml`, `sheets/300-low-voltage-header.yaml`, `schematic-spec.yaml` (regenerated by `spec-tools/build_spec.py`; `check_spec.py` 0 errors, 0 warnings, 15 parts), `parts-specification.yaml`, `open-items.md`, `layout-hedges.md`, `circuit-verdicts.md`, `circuit-proof.md`, `constraints-figures.md` and `fabrication-notes.md`. Scope: `*.md` and `*.yaml` in this folder excluding this file, `schematic-review.md` and `layout-plan.md`, case-insensitive, line by line, after the corrections. The docs under `docs/sunbeam-em7000/` hold earlier `Amended 2026-11-19` notes that name H1 to H4 as a starting set; they were outside this change and are not counted.

| Phrasing | Live lines | Files | What the live lines are |
|---|---|---|---|
| `H2` | 4 | 4 | each states that H2 to H4 were deleted |
| `H3` | 0 | 0 | (H3 appears only inside the range "H2 to H4", on lines counted under `H2` and `H4`) |
| `H4` | 4 | 4 | the same four lines |
| `FID` | 11 | 9 | each states that FID1 to FID3 were dropped, plus the lines of the generated `schematic-spec.yaml` that carry the sheet note and the totals |
| `fiducial` | 11 | 9 | the same lines (every one says none is carried, or the reason for dropping them) |
| `starting set` | 0 | 0 | |
| `21 parts` | 0 | 0 | |
| `four holes` | 0 | 0 | |
| `hand` | 73 | 13 | the hand-fitted parts: seven through-hole references and, new, R911, R912, R921, R922 (eleven in `hand_fitted_refs`); the rest are other uses of "hand" (hand-routed, by hand) |

The wall-board-only run of the pre-order check (a clone with the working tree, `/tmp/wl/wallonly.py`) gives 51 violations against 57 before: `missing_footprint` 21 to 15 (the six deleted parts), `parts_catalogue` 6 (RV911, RV921, T911, T921, U911, U921, unchanged), no `parts_part`, no new class; the other classes (`board_minimums`, `custom_rules`, `ignored_check`, `invalid_outline`, `mains_declaration`, `workmanship_figure`, `workmanship_rule`) belong to the board layout not yet placed. No record of this folder names a part the netlist no longer holds, except as a statement that it was deleted.

## 2026-11-19: W-9 added to the owner sign-off record (12 entries, W-1 to W-9, 9 in the owner's words)

Change: `owner-sign-off.md` gains W-9 (the owner's "1a/1b/1c. sign as accepted" of 2026-11-19 on the through-hole figures as first put, with his plate earth-point question and a marked re-confirmation owed if the package becomes the surface-mount part); its intro, section and subsection counts, "Look at these first" and the carried table are updated; `open-items.md` gains the W-9 reference in the re-declaration list and a carried "Plate earth point (case step)" item. Scope: `*.md` in this folder, line by line, after the change; `schematic-review.md` is frozen history and was not edited, its counts are given apart.

| Phrasing | Live lines (files) | In `schematic-review.md` | What the live lines are |
|---|---|---|---|
| `11 entries` | 1 (1: this file) | 4 | the line is the 2026-11-19 structure-rebuild record above, which states the count of that rebuild and stays as written; `owner-sign-off.md` now reads 12 entries |
| `W-1 to W-8` | 0 | 0 | the intro's range was changed to W-1 to W-9 |
| `8 are` | 1 (1: this file) | 2 | the same rebuild record; `owner-sign-off.md` now reads 9 are David Baker's own acceptance |
| `W-9` | 11 (3: `owner-sign-off.md` 9, `open-items.md` 2, this file counted apart) | 0 | the entry, the intro counts, the look-first bullet, two carried-table cells and row, the two open-items lines |

## 2026-11-19: the opto-triacs are the surface-mount MOC3083SR2M, pins 4 and 6 swapped, a bare-PCB order

The class swept: a record that names the through-hole MOC3083M (C23552, DIP-6, 7.62 mm row) as the board's opto-triac, puts pin 4 on OUT_C and OUT_S and pin 6 on the gate chain, or says an assembler places or lists a part, left live after the owner's decision (option A, 2026-11-19): U911 and U921 are the surface-mount onsemi MOC3083SR2M (LCSC C111561, CASE 646BY) on `heater-wall-board:SMDIP-6_W9.53mm_MOC3083SR2M`, pin 6 on OUT_C and OUT_S, pin 4 on HEAT_C_OPTO_MT and HEAT_S_OPTO_MT, the blades on the project symbol `heater-wall-board:TabBlade`, and every part hand-fitted on a bare-PCB order. Corrected in `sheets/100`, `200` and `400` (the custom symbol and footprint entries added; `schematic-spec.yaml` regenerated, `check_spec.py` 0 errors and 0 warnings, 15 parts), `parts-specification.yaml`, `pin-limits.yaml` (LCSC key C111561, the pin 4 and pin 6 domains exchanged), `circuit-proof.md`, `circuit-verdicts.md`, `constraints-figures.md`, `open-items.md` (three new open items: the owner's re-confirmation of W-9 1a, the wide pad lands, hand-soldering), `layout-hedges.md`, `fabrication-notes.md`; `owner-sign-off.md` keeps the owner's words and gains keeper's notes. `circuit-proof/W_margins.py` names the datasheet family only and is unchanged; rerun, 17 PASS, log identical. Scope: `*.md` and `*.yaml` in this folder (subfolders included, `catalogue-extract.yaml` and `schematic-spec.yaml` too) excluding this file, `schematic-review.md` and `layout-plan.md`, case-insensitive, line by line, after the corrections.

| Phrasing | Live lines | Files | What the live lines are |
|---|---|---|---|
| `MOC3083M` | 57 | 12 | the maker's family and document name (MOC3083M/D, the stock symbol `Relay_SolidState:MOC3083M`) and records of the earlier part, each with the package change stated |
| `C23552` | 13 | 7 | history or the amended notes naming the replaced number (the sign-off entries, the amended items) and `catalogue-extract.yaml`, which the layout agent edits and which still lists it |
| `DIP-6` | 34 | 7 | 30 are the substring inside `SMDIP-6` (the new footprint and sheet entries); the rest are history (W-2, W-9 words) or amended notes |
| `DIP6` | 0 | 0 | |
| `7.62` | 0 | 0 | |
| `pin 4` | 14 | 6 | the swapped assignment, the maker's pin diagram and the pin-limit domains |
| `pin 6` | 12 | 6 | the same, and the maker's Fig. 12 application circuit (stated as the maker's pin) |
| `MOC3083SR2M` | 43 | 11 | the fitted part |
| `assembler` | 0 | 0 | the one earlier hit (`layout-hedges.md`) now states the bare-PCB order |
| `hand-fitted` | 38 | 11 | the hand-fitted parts, now including the opto-triacs |

Not edited here: `catalogue-extract.yaml` and the separation basis (the layout agent's), the owner's recorded words in `owner-sign-off.md` (W-2, W-4, W-9; kept with dated notes), and `bring-up-provision.md` (it names U911 and U921 only by LED pin 1 and by case temperature, unaffected).

## 2026-11-19: round 14 findings closed, W-10 and the lid statement added to the owner sign-off record (13 entries, W-1 to W-10, 10 in the owner's words)

The class swept: a record that gives the opto-triac's creepage clause other than the drawn Rating field text, calls the drawn field still to be corrected, names the fitted part MOC3083M, states the package-change re-confirmation as a condition (an 'if'), says the other parts are through-hole or assembled by a service, counts the fitted parts as fifteen, places J911 or J921 at the left or the opto-triac's LED pins at the right, or counts the owner-sign-off entries as 12 (9 in his words).

| Phrasing | Live hits before | Live hits after | What each is |
|---|---|---|---|
| `if the package`, `package (changes\|becomes)`, `owed if` | 3 (`owner-sign-off.md` line 20, W-9 body, `open-items.md` line 40) | 0 | all three now say the package HAS changed and 1a is OWED now; the order must not proceed before it. `sweep-log.md` line 231 is this file's history of W-9's first form and stays as written |
| `all fifteen parts`, `every other part is through-hole`, `other assembled parts are through-hole` | 3 (`fabrication-notes.md`, `open-items.md`, `sheets/300` and its generated spec) | 0 | corrected to 14 fitted parts plus the hole H1 and the through-hole and surface-mount lists |
| `at the left` (J911, J921), `on the right edge as low voltage` | 2 sheet notes and their generated spec lines | 0 | corrected to what the sheets draw |
| `12 entries`, `9 are`, `W-1 to W-9`, `(9 entries)`, `(5 entries: ... W-9)` | 4 live lines in `owner-sign-off.md` | 0 | now 13 entries, W-1 to W-10, 10 in his words, 6 entries under 2026-11-19. This file's lines 229 to 237 are the history of the W-9 round and stay as written |
| `layout-hedges.md` line 25, 7 mm creepage stated as accepted | 1 | 0 | qualified: accepted on the through-hole MOC3083M figures (W-9 1a), re-confirmation owed on the SMT MOC3083SR2M |
| owner's lid statement (`lid`, `wall opening`) | 0 | 2 | W-10 (labelled a further statement, not a new acceptance) and the case-step requirements in `open-items.md` |

Not edited here: `catalogue-extract.yaml` line 19 (lists C23552 as the opto-triacs; the layout agent's), `docs/sunbeam-em7000/controller-board-division.md` line 2243 (the executable data block; the notes added to lines 797 and 856 say the data is the DIP form kept for history), and the owner's recorded words.

## 2026-11-19: the opto-triacs are the V-option MOC3083SVM (C899868), W-11 added to the owner sign-off record (14 entries, W-1 to W-11, 11 in the owner's words)

The class swept: a record that names the plain MOC3083SR2M (C111561) as the part fitted at U911 and U921, or says the 7 mm re-confirmation of W-9 1a is OWED, left live after the layout agent's choice of the V-option MOC3083SVM (C899868) under the owner's delegation of 2026-11-19 (`owner-sign-off.md` W-11). Fields only: no net, pin, footprint (name kept) or placement changed. Counts are of lines over `hardware/sunbeam-em7000/heater-wall-board/` and `docs/sunbeam-em7000/`, this file excluded, after the edits.

| Phrase | Lines | Of which live | What they are |
|---|---|---|---|
| `MOC3083SR2M` | 55 | 0 as the fitted part | 27 are the footprint name `SMDIP-6_W9.53mm_MOC3083SR2M`, kept; the rest are history: `schematic-review.md` rounds, W-9 / W-11 and the keeper's note, `open-items.md` and the `catalogue-extract.yaml` header naming the part first used, and the amended notes in the division, function-forms and design-constraints records |
| `C111561` | 28 | 0 as the fitted number | the number first used, named as replaced (`catalogue-extract.yaml`, `pin-limits.yaml`, `parts-specification.yaml` headers, W-11, amended notes) and the older review rounds |
| `C899868` | 38 | all | the fitted number: both schematics, the placed footprints on the board, the sheets, the generated `schematic-spec.yaml`, `parts-specification.yaml`, `pin-limits.yaml` (the key), `catalogue-extract.yaml` (the entry) and the amended records |
| `MOC3083SVM` | 58 | all | the fitted part's name, same places |
| `W-11` | 16 | all | the entry, the intro counts, the look-first bullet, the W-2 and W-9 keeper's notes, `open-items.md` and `layout-hedges.md` |
| `W-9 1a re-confirmation owed` / `OWED` | 0 live | 0 | now 'carried by W-11' in `owner-sign-off.md`, `open-items.md`, `layout-hedges.md`; `schematic-review.md` round 14 closing note and the earlier sections of this file stay as written (history) |
| `13 entries`, `W-1 to W-10`, `(10 entries)`, `(6 entries: ... W-10)` | 0 live | 0 | now 14 entries, W-1 to W-11, 11 in his words, 7 entries under 2026-11-19 |

`derating-policy.yaml` and `board-rules.yaml` name neither number and are unchanged. The sections of this file above are history and stay as written.

## 2026-11-19: the front OUT_C copper below U911 pin 6 deleted, the back OUT_C diagonal widened to 4.7 mm (workmanship review, copper pass 2)

The class swept: a record that states the old front-layer extent of OUT_C (the strip x 41.55 to 46.55, y 47.75 to 69.6, now deleted), the old 3.5 mm diagonal, or the single-layer rise of about 3.5 K, left live after the copper changed. Scope: `hardware/sunbeam-em7000/heater-wall-board/` and `docs/sunbeam-em7000/`, files `*.md` and `*.yaml`, regular expressions run line by line over the working tree after the corrections of this change; counts are lines.

| Phrase | Lines | Of which live | What they are |
|---|---|---|---|
| `69.6` / `69.65` | 6 | 0 stale | `layout-plan.md` 1 (Pass 1, the board as judged at its Board judged commit; a pass the router has run after is never changed), `layout-review.md` 5 (the reviewer's verdict rows and the finding's What and where, frozen; the corrected Closed by of 1.1 and 1.8, where `y 69.6 to 80.9` is still the B.Cu-only stretch under the spur) |
| `80.9` / `80.85` | 12 | 0 stale | `layout-plan.md` 1 (Pass 1), `layout-review.md` 4 (as above), `controller-board-division.md` 7 (the main board, not this one) |
| `x 41.55 to 46.55` | 3 | 0 stale | the strip width, still the back-layer strip's: `layout-plan.md` 2 (Pass 1 and the plan row), `layout-review.md` 1 |
| `about 3.5 K` | 1 | 1 fixed | `layout-review.md` finding 1.1 Closed by, now about 3.8 K at 4.7 mm and about 3.5 K at 5.0 mm, about 4 K for the run |
| `3.5 mm wide`, `3.54 mm` | 2 | 1 fixed | `layout-review.md` 1.1 (the diagonal, now 4.7 mm); `controller-board-division.md` 1 is the main board |
| `OUT_C front`, `front-layer OUT_C`, `front-layer strip` | 3 | 1 fixed | `layout-review.md`: 1.1 Closed by fixed; the other two are the reviewer's rows and What and where, frozen |
| `single-layer` | 8 | 0 stale | `layout-plan.md` 5 (plan rows R1 and Pass 1, frozen), `layout-review.md` 3 (frozen rows and the corrected 1.1) |
| `11.05 mm` | 4 | 0 stale | the plan's figure for the stretch, quoted against the board: `layout-plan.md` 2, `layout-review.md` 2 |

`board-rules.yaml`, `design-rules.md`, `fabrication-notes.md`, `circuit-proof.md` (its "about 3.5 A" is a rail current) and `owner-sign-off.md` quote none of the phrases. `open-items.md` gained the blade backing item and states the R1 stretch in no figure.

## 2026-11-19: the Staircase logo and maker line added to the front silk

The class swept: a record that lists the front silkscreen items or the legend, left without the maker mark. Scope: `hardware/sunbeam-em7000/heater-wall-board/` and `docs/sunbeam-em7000/`, `*.md` and `*.yaml`, lines matching `legend`, `silkscreen`, `silk legend`, `BREW STATE`, `MADE WITH`, `STAIRCASE`, after the change.

| Phrase | Lines | Of which live | What they are |
|---|---|---|---|
| `legend` | 4 | 0 stale | `layout-review.md` 3 (round 1 record, finding 1.10, frozen) and one main-board carry-forward note; no record lists the front silkscreen items |
| `BREW STATE` | 2 | 1 new | `fabrication-notes.md`, the new paragraph "Front silkscreen" (the only record that lists the items, now with the maker mark), and the `layout-review.md` finding 1.10 text (frozen) |
| `MADE WITH` | 5 | 1 new | `fabrication-notes.md` 1 (the new paragraph); the other 3 are unrelated prose in `docs/sunbeam-em7000/` and the paragraph's own heading line |
| `STAIRCASE` | 1 | 1 new | `fabrication-notes.md` |
| plan rows naming the silkscreen (`MFG-7`, `MFG-8`, `MFG-9`) | 3 | 0 stale | they judge the references' and text's reading and place, which the mark does not change; the KiCad rule check reports no silk line on the new board |

## 2026-11-19: layout review round 2, record findings 2.2, 2.3, 2.5 to 2.8

The class swept: a record that states a figure the board does not bear out. Scope: `hardware/sunbeam-em7000/heater-wall-board/` and `docs/sunbeam-em7000/`, `*.md` and `*.yaml`, run line by line over the working tree after the corrections; the outline read from the board's Edge.Cuts (x 20 to 65, y 21 to 96: 45.0 x 75.0 mm) and H1's distances measured from the board's copper (H1 centre to the OUT_S spur's rounded end 14.31 mm, to the OUT_S finger zone's corner 15.37 mm).

| Phrase | Lines | Of which live | What they are |
|---|---|---|---|
| `45 x 76`, `45.0 by 76`, `left edge (76.0 mm)` | 9 | 7 fixed | `fabrication-notes.md` Outline row, `constraints-figures.md`, `layout-hedges.md` 13, `open-items.md`, `sheets/300-low-voltage-header.yaml` and its generated `schematic-spec.yaml` fixed to 45 x 75; `layout-plan.md` WORK-9 baseline row kept and corrected by the amendment note, the note itself quotes it; the `schematic-review.md` and `controller-board-division.md` hits are other figures (76 mm2, 0.76 mm) |
| `14.25` | 1 | 1 fixed | `layout-plan.md` D1: 14.3 mm to the spur end, 15.4 mm to the finger zone's corner; Pass 1 and the review quote 14.25 (the layout agent's figure for the same end cap), frozen history |
| `11.05` | 7 | 1 fixed | R1 now states the built 47.5 mm run; the BOARD-4 row, Pass 1 and the review's rows quote the plan's baseline figure, frozen, with the amendment note |
| `about 4 K` | 1 | 1 fixed | `layout-review.md` finding 1.1 Closed by, now 3.8 K at the worst section |
| `no via`, `places no via` | 6 | 1 fixed | `constraints-figures.md` now states the one `+5V_WB` via; the others state that no Mains net has a via, true |
| `exclude_from_bom` | 3 | 2 fixed | `layout-hedges.md` 17 and `open-items.md` now state `exclude_from_pos_files` alone; `layout-plan.md` MFG-7 row is baseline, amendment note added |
| `MOC3083SR2M` | footprint name | kept | `fabrication-notes.md` "Part and footprint names" says why the footprint keeps the old name |

## 2026-11-19: front silk legend repositioned, back-side placeholder added (layout review round 2, findings 2.1 and 2.4)

The class swept: a record that states a silk position or the back face's content the board no longer has. Scope: `hardware/sunbeam-em7000/heater-wall-board/`, `docs/sunbeam-em7000/` and `docs/`, `*.md` and `*.yaml`, lines matching the phrases, after the corrections.

| Phrase | Lines | Of which live | What they are |
|---|---|---|---|
| `beside J931` | 4 | 0 stale | `layout-review.md` only: round 1 finding 1.10's record and round 2's findings 2.1 and 2.2 text, frozen; `fabrication-notes.md` now gives the real positions |
| `back face carries no text`, `back carries no text`, `B.SilkS holds no reference` | 4 | 2 fixed | `fabrication-notes.md` and the plan's `MFG-11` row fixed; the `MFG-7` and `MFG-8` plan rows are baseline, with an amendment note |
| `moved to x 41`, `x 41.0` | 2 | 1 fixed | the round 1 workmanship text, now saying it moved again to x 44.75; the other is finding 2.4's frozen text |
| `JLCJLCJLCJLC` | 0 before, 3 after | all new | `fabrication-notes.md`, the plan's `MFG-11` row and amendment note |

## 2026-11-19: front silk legend, hazard block and maker mark repositioned again (layout review round 3, findings 3.1 to 3.3)

The class swept: a record that states a silk position, size or enforcement the board no longer has. Scope: `hardware/sunbeam-em7000/heater-wall-board/` and `docs/sunbeam-em7000/`, `*.md` and `*.yaml`, lines matching the phrases after the corrections.

| Phrase | Lines | Of which live | What they are |
|---|---|---|---|
| pin-name columns at `x 52.6`, `54.1`, `55.6` | 1 | 0 stale | `layout-review.md`, round 2's closure of finding 2.1 and findings text, frozen history; `fabrication-notes.md` now states the header table |
| hazard block `44.75`, `y 58.6` | 2 real (9 other hits are `y 58.69`, a crop caption) | 0 stale | `layout-review.md` round 2 text and closure, frozen; `sweep-log.md` the earlier log entry |
| maker text `0.9`, `x 50.6`, `90.55` | 0 | 0 | the finding 3.2 text is in round 3, frozen; the notes state 1.0 mm at x 50.15 |
| logo `scale 0.45`, `y 64.6 centre` | 0 | 0 | `fabrication-notes.md` rewritten with scale 0.42 and the anchors with their justification |
| `layout rule check` enforcing silk text height | 1 | 1 fixed | `design-rules.md` row `Silkscreen text height`; the other 18 board-wide minimum rows keep the method's wording, KiCad does report them |
| silk text census | 38 texts | 0 under 1.0 mm or 0.15 mm | every `gr_text` and reference text on `F.SilkS` and `B.SilkS` of the board file |

## 2026-11-19: heater-switch part row and silk line width (layout review round 4, findings 4.1 and 4.2)

The class swept: a record that states the through-hole or stocked M part for the heater switches, or a silk figure as enforced. Scope: `hardware/sunbeam-em7000/heater-wall-board/` and `docs/sunbeam-em7000/`, `*.md` and `*.yaml`, lines matching the phrases, after the corrections.

| Phrase | Lines | Of which live | What they are |
|---|---|---|---|
| `through-hole, as above` | 0 | 0 | fixed in `constraints-figures.md` |
| `stocked part is the M`, `stocked part` | 4 | 1 fixed | `constraints-figures.md` fixed; the others are main-board documents (`controller-board-function-forms.md`, `component-specification.md`) about other parts |
| `M part`, `MOC3083M` with through-hole or stocked | 5 | 0 stale | `owner-sign-off.md` W-2 text (frozen history), `open-items.md`, `parts-specification.yaml` and `catalogue-extract.yaml` notes naming the replaced part, `constraints-figures.md` |
| `V-ordered` | 2 | 0 stale | `owner-sign-off.md` W-2 and W-11 text, frozen history |
| claim that the layout rule check enforces a silk figure | 1 | 1 fixed | `design-rules.md` row `Silkscreen line width`, now stating the accepted 29 strokes at 0.12 mm (**amended 2026-11-20**: the exception no longer stands, every silk stroke was widened to 0.15 mm after the production-files check; the row now states the census) |

## 2026-11-20: evidence-pass corrections (C7, C8, C11, C15 of the leaf)

The classes swept: a record that states the 45 degC working figure as live for the wall path (C7, C8); a record that states this board's own separation basis as unsigned, not yet drawn or not yet carrying the entries (C15, superseded by W-12). Scope: `hardware/sunbeam-em7000/heater-wall-board/` and `docs/sunbeam-em7000/`, `*.md` and `*.yaml`, counted after the corrections and excluding the review records and this log, which are history.

| Phrase | Lines (heater-wall-board and docs) | Stale, fixed by an amendment note | Rest |
|---|---|---|---|
| `45 degC`, `45 °C` | 15 in the wall folder outside the review records and this log; 27 in `docs/sunbeam-em7000/` | 7 (`circuit-proof.md` 28 and 35, `derating-policy.yaml` 20, `constraints-figures.md` 9, `fabrication-notes.md` coat sheet line, `controller-board-design-constraints.md` pending-marks spreader row, `controller-board-function-forms.md` 279 and 477) | other boards' figures (for example the IRM-20-5 chart), the 45 degree track angle; the rest of the division record was NOT all history (corrected by the round 5 sweep below) |
| `working figure`, `conservative case` | 10 | 5 (the same lines) | history or labelled superseded |
| `not yet in the basis`, `not yet signed`, `still to be drawn`, `still not edited`, `does not carry them` | 16 | 7 (`owner-sign-off.md` W-8, W-9 and the W-9 look-first bullet and the shared-basis table row, `open-items.md` rows (b) and (d), `constraints-figures.md` heater-switch row, `layout-hedges.md` amended note) | the shared basis does carry none of this board's entries (true, not edited), review records (history) |

Not amended, on purpose: `layout-plan.md` BOARD-13 row (the plan's rows are frozen history; the statement is of the plan's date), `sweep-log.md` line 35 (a log row of its own date).

C8: the revisit of the figure for the triacs, with its reason, is now in the controller boards' constraints record (`docs/sunbeam-em7000/controller-board-design-constraints.md`, Enclosure air temperature, amendment of 2026-11-20) as well as in `constraints-figures.md`. C11: `fabrication-notes.md` cites the document and revision for each preferred family and states the written request; the request has not been sent (an owner act, stated in the notes).

### Round 5 finding 5.1, the same class again (2026-11-20)

The earlier row above wrongly called the rest of `docs/sunbeam-em7000/` history labelled superseded: `controller-board-function-forms.md` line 287 and `controller-board-division.md` lines 24, 192 and 1168 stated the 45 degC working figure as live. Phrases swept after the corrections, scope `docs/` and `hardware/` `*.md` and `*.yaml` outside the review records, this log and `main-board/`: `45 degC` and `45 °C` (62 lines), `45 to 50` (4), `40 K` (11, of which 7 are the unrelated 40 K rise limits and the pump triac's 110 degC cap), `enclosure air` with a 45 figure (3), `working figure` (13), `conservative case` (12). Live statements found and given an `Amended 2026-11-20` note: 17 lines (division 24, 192, 839, 849, 856, 874, 931, 992, 996, 1168; function-forms 287; constraints record 357; wall `layout-hedges.md` 18, `bring-up-provision.md` 25, `open-items.md` 97, `circuit-proof.md` 11, `derating-policy.yaml` 32). Left unamended: `controller-board-division.md` 905 to 910 and 967 to 981 (the 45 degC history tables, labelled superseded at line 933 and by the 2026-11-19 amendment at 876), `controller-board-function-forms.md` 279 and 477 (amended in the first pass), the IRM-20-5 chart row, the 40 K rise limits of the blade and joiner step.

## 2026-11-20: the 1a re-confirmation, W-14 (blind review)

The class swept: a record that says the W-9 1a re-confirmation for the surface-mount part is owed, or carried by W-11, or on the owner's end-of-work list (W-11 only delegated the part choice; the owner re-confirmed in W-14, "Yes and go", 2026-11-20). Scope: `hardware/` and `docs/`, `*.md` and `*.yaml`, outside the review records. Phrases, counted as matching lines over `hardware/` and `docs/` including the review records (history, not amended): `re-confirm` 43, `carried by W-11` 12, `1a` with `confirm` 33; `owed` matches 927 lines of unrelated text and was read only where it sat with `re-confirmation` or `1a`. Live statements found and given an amendment note: 9 (`owner-sign-off.md` look-first W-9 bullet, W-2, W-9, the W-8 carry table row 1.3 and 2.2, the keeper's note, W-11; `open-items.md` rows (b), item 1 and the carried line; `layout-hedges.md` 25; `constraints-figures.md` 10). Left alone on purpose: `separation-basis.yaml` header (states the basis rests on W-9 1a, 1b, 1c and W-11, none as owed; a signed record, not edited), `parts-specification.yaml` comment 64 (names W-11 and W-9 1a as the part's source, not as owed), `layout-plan.md` (frozen plan).

## 2026-11-20: silk stroke widening (production-files check; supersedes the exception of finding 4.2)

The class swept: a record that states a silk stroke width below 0.15 mm, the 0.12 mm stock-library exception, or a silk figure that the board no longer has. Scope: `hardware/sunbeam-em7000/heater-wall-board/` and `docs/sunbeam-em7000/`, `*.md`, `*.yaml`, `*.py` and `*.log`, after the corrections and excluding `layout-review.md` and `schematic-review.md`, which are history (finding 4.2 and its Closed by text are frozen; this section and `design-rules.md` say the exception no longer stands). Phrases: `0.12`, `0.10`, `0.1 mm`, `stock library`, `accepted by reason`, `silk` with `width` or `stroke`, `stroke width`, `pin-1 dot`, `bolt`.

| Phrase | Lines | Of which live | What they are |
|---|---|---|---|
| the 0.12 mm exception, 29 strokes accepted | 2 | 2 fixed | `design-rules.md` row `Silkscreen line width` (now the census: 118 printed strokes, 0 under 0.15 mm) and the 2026-11-19 section above (annotated) |
| silk strokes stated as 0.15 mm or more | 1 | 1 fixed | `fabrication-notes.md` 'Front silkscreen' (stated for texts only; now texts and graphics, with the edge of the dots and the bolt) |
| `0.1 mm`, `0.10 mm` as a clearance, track or pour figure | many | 0 stale | `design-rules.md`, `layout-plan.md`, `manufacturer-limits.yaml`, `separation-basis.yaml`: copper and creepage figures, not silk |
| `0.12` elsewhere | 0 | 0 | none outside the review records |

Census of every `F.SilkS` and `B.SilkS` graphic and text of the board file, including inside footprints, before and after: before, 8 at 0.10 mm and 29 at 0.12 mm (37 below the minimum); after, none below 0.15 mm: graphics 79 at 0.15 mm and 1 at 0.25 mm, texts 30 at 0.15 mm and 8 at 0.2 mm. 15 hidden Value properties carry no thickness and are not printed.

## 2026-11-20: the review closes at Round 6, the silk widening and the pin-1 dots (layout review round 6, findings 6.1 and 6.2)

The classes swept: a record that says the layout review closes at Round 5 (6.1's surround, W-13), a record that says the 29 strokes at 0.12 mm are accepted, and a record that names the opto-triacs for all seven pin-1 dots. Scope: `hardware/` and `docs/`, `*.md` and `*.yaml`, review records outside round text read as history. Phrases: `closing round`, `closes at`, `close at`, `at round 5`, `without a round 6`, `round 6` (the wall board's folder: 3 lines outside the review records, all in `owner-sign-off.md` W-13 and its look-first and end-of-work lines, amended; the other boards' review proofs under `hardware/proof/` are other records); `0.12 mm` with `accepted` or `exception` (live statements: 0, `design-rules.md` already says the exception no longer stands); `pin-1 dots` (1 live statement, `design-rules.md`, reworded from the board file: `fp_circle` of the SMDIP-6 footprint at U911 and U921, `gr_circle` at (56.7, 54.95) and (64.45, 61.45), and the `Tab_TE_63849-1` footprint circles at J941, J921 and J911). Finding 4.2's own Closed by is frozen history and is not edited; round 6's row 6.1 supersedes it.

## 2026-11-20: critical routing pass 3, the leftover front OUT_C wedge filled, the U921 pin 4 track straightened, the +5V_WB via centred, reference labels aligned (workmanship review)

The class swept: a record that states the front OUT_C zone's extent past the finger (the 44.425 y edge and the corner at x 49.875, y 44.425), the HEAT_S_OPTO_MT track's route from R921 to U921 pin 4, the `+5V_WB` via's position (58.1, 56.8), or the positions of the T911, RV911, R911, R912 and R922 reference texts. Scope: `hardware/sunbeam-em7000/heater-wall-board/` and `docs/sunbeam-em7000/`, `*.md` and `*.yaml`, expressions run line by line over the working tree after the change, the sweeps of the earlier passes being history.

| Phrase | Lines | Of which live | What they are |
|---|---|---|---|
| `44.425`, `49.875` | 0 | 0 stale | no record states the old vertices |
| `44.4`, `46.4` | `layout-plan.md` 2 lines (Pass 1's rows MAINS-2, "the F.Cu finger of OUT_C (y 44.4 to 46.4)", frozen), `layout-review.md` 5 lines (rounds 1 to 3 and 6, frozen) | 0 stale | **Corrected 2026-11-20 (layout review round 7, finding 7.4): this row first said 0 outside the board file and that the plan and the review quote none of them, which was wrong.** All are frozen pass and round text, not edited; they describe the F.Cu finger of the board as it then stood, which the zone body ending at y 46.425 has replaced, and no live record states it |
| `wedge`, `ends at the finger`, `zone finger` | 1 | 0 stale | `design-rules.md` `MainsBranch` row: the spur "ends in a zone finger", still true of the zone with the wedge filled |
| `56.575`, `70.975`, `55.05` | 0 | 0 stale | no record states the HEAT_S_OPTO_MT track's vertices |
| `56.8`, `58.1, 56` | `layout-review.md` 8 lines (rounds 1 to 3, frozen) | 0 stale | **Corrected as the row above (finding 7.4): this row first said 0.** The via at (58.1, 56.8) of the frozen rounds; `design-rules.md` names the one via on `+5V_WB` and its sizes only and no live record states its position |
| `HEAT_S_OPTO_MT` | 0 describing the route | 0 stale | the net is named in lists of Mains-class nets only |
| `34.7`, `22.7`, `38.5`, `28.5`, `59.7`, `40.9` as reference positions | 0 before this change | 1 new | `fabrication-notes.md`, "Front silkscreen", now states the six reference positions |

The copper record of the committed board holds 22 locked items on 11 critical-class nets (21 before this change, one track added for the U921 pin 4 run), and the pre-order check, the rule check (12 clearance findings, none unconnected) and the silk census (80 graphics at 0.15 mm or more, 38 texts of 1.0 mm or more at strokes of 0.15 mm or more) are as before.

## 2026-11-20: critical routing pass 4, OUT_C front band edge straightened, blade legends and RV921 reference moved off the copper edges (layout review round 7, findings 7.1 and 7.2)

The class swept: a record that states the front OUT_C zone's right edge or left chamfer (x 58.4 and 58.1, 53.4, the 5.0 mm strip, the 8.8 mm body), the position or orientation of a blade legend, of the RV921 reference or of the maker mark (the names centred at x 24.5, 32.6 and 44.0 at y 80.3 and 82.3, x 46.55 and x 50.15), or a claim that silk stands clear of copper. Scope: `hardware/sunbeam-em7000/heater-wall-board/` and `docs/sunbeam-em7000/`, `*.md` and `*.yaml`, expressions run line by line over the working tree after the change; `layout-plan.md` (frozen pass and baseline text) and the rounds of `layout-review.md` and `schematic-review.md` are history and are not edited.

| Phrase | Lines | Of which live | What they are |
|---|---|---|---|
| `centred on x 24.5`, `y 80.3`, `y 82.3`, `x 50.15`, `46.55 to 49.6` | 4 in `fabrication-notes.md`, "Front silkscreen" | 4 fixed | now the blade legends' pairs read upward at their anchors, the maker lines at x 50.65 and the logo's span x 47.05 to 50.1; the board title block's `y 80.3 to 86` is the title block, not a legend, and stands |
| `53.4`, `58.4`, `58.1`, `5.0 mm strip`, `8.8 mm`, `4.31` | 0 outside the round 7 text and `layout-plan.md` | 0 stale | no live record states the band's edges or the left chamfer; the figures are in the frozen round text and the board file |
| `RV921` as a reference position | 0 before this change | 1 new | `fabrication-notes.md` now states (28.65, 35.7), reading upward |
| silk clear of copper | 2 | 2 new | `design-rules.md`, row `Silkscreen across copper edges`, and `fabrication-notes.md`: the 12 library-drawn part-body outlines that cross copper edges are accepted by reason (the silk census of this change: 118 silk objects, 12 crossing a copper edge, all of them library outlines) |

The copper record of the committed board holds 22 locked items on 11 critical-class nets and the compare against the record of the board before this change differs only in `OUT_C_F0`; the rule check reports 12 clearance findings and nothing unconnected, the same list as before; the silk census is 80 graphics at 0.15 mm or more and 38 texts of 1.0 mm or more at strokes of 0.15 mm or more, as before.

## 2026-11-20: the triac and blade fitting order added, the production-files check record committed

The class swept: a record that states an order of fitting the triacs, the blades or the plate that differs from "bolt the tabs to the plate, then solder the leads, blades last". Scope: `hardware/sunbeam-em7000/heater-wall-board/` and `docs/sunbeam-em7000/`, `*.md` and `*.yaml`, phrases `order of fitting`, `fit order`, `fitting order`, `fitting note`, `bolted`, `soldered first`, `before soldering`, `fit the blades` and `fitted last`. Result: `layout-hedges.md` hedge 9 (blades after the other parts, board supported) agrees; `fabrication-notes.md` "Home application steps" (every hand-fitted part fitted, the plate and triac mounting done and the heat compound applied, before the coat) agrees; `controller-board-division.md` has an order of fitting for the earlier bracket form, which its own amendment note of 2026-11-19 marks as that form's, so it states no live order; nothing else states one. `production-files-check.md` is now in the board folder (judged at 478d3b05).

## 2026-11-20: layout review round 9, the closing round named, the BOARD-8 distances stated (findings 9.1 and 9.2)

The classes swept: a record that names Round 8 as the closing round of the layout review; a record that states the opto-triac to triac distance as 20.7 mm or 20.73 mm or holds a figure out as meeting the 20.0 mm of hedge 8 for all three measures. Scope: `hardware/sunbeam-em7000/heater-wall-board/` and `docs/sunbeam-em7000/`, `*.md` and `*.yaml`, phrases `Round 8`, `closing round`, `20.7`, `20.73`, `45.33`, `BOARD-8`, `20.0 mm from`, `22.41`, `19.59`, `19.82`.

| Phrase | Lines | Of which live | What they are |
|---|---|---|---|
| `Round 8` in `owner-sign-off.md` | 5 | 5 fixed | the W-13 line, W-13's closing note, the keeper's note under W-16, item 8 and its Round 6 to 8 sentence: Round 9 is the closing round, Round 8 raised no finding and ran no views |
| `20.7`, `20.73` | `layout-plan.md` 3 lines (relaxation R3, the BOARD-8 rows of candidates 1 and 2), `layout-review.md` frozen rounds | 0 stale | baseline rows, not rewritten; `layout-plan.md` now carries an amendment note after layout review round 9 with the built figures |
| `BOARD-8` | `layout-plan.md` and `layout-review.md` (frozen rows); `owner-sign-off.md` 1 | 1 new | item 9 of the end-of-work list, the pass on body distance with the courtyard and pad figures under 20.0 mm |
| `20.0 mm from`, `20.0 mm of hedge 8` | `layout-hedges.md` 3 lines | 0 stale | the hedge's target, stated without a measured figure |
| `45.33`, `22.41`, `19.59`, `19.82`, `38.44` | `layout-plan.md` line 16 and the amendment note, `layout-review.md` rounds, `owner-sign-off.md` item 9 | 0 stale | the built figures, as the board file gives them |

## 2026-11-20: records name no round as the closing round

The class swept: a live record that names which round of the layout review is the closing round, which goes stale when another round is recorded (layout review findings 7.3 and 9.1). Scope: `hardware/sunbeam-em7000/heater-wall-board/` and `docs/sunbeam-em7000/`, `*.md` and `*.yaml`, phrases `closing round`, `closes at Round`, `close at Round`, `review closes`, `close of the review`, `Round N is the closing`. The round records of `layout-review.md` and the earlier sections of this file are history and are not edited.

| Phrase | Lines | Of which live | What they are |
|---|---|---|---|
| `closing round`, `closes at Round`, `review closes` in `owner-sign-off.md` | 4 | 4 fixed | the W-13 line of the first-look list, W-13's closing note, the keeper's note under W-16 and item 8 of the end-of-work list: each now says the closing round is the last round recorded in `layout-review.md` and carries no round number for it; the Round 5 mentions in W-13 are his words' history and stand |
| the same phrases elsewhere in the board folder and `docs/sunbeam-em7000/` | 0 | 0 | `hardware/README.md` describes the history command's closing-round check in general terms and names no round |

## 2026-11-20: four observations of layout review round 10, seen and not raised

Round 10 raised no finding. The reviewer saw these four and did not raise them; they are recorded here so that they are carried, none being a finding and none edited in the record it concerns.

- `layout-plan.md`, the `FLOOR-1` baseline row (line 43): it quotes the courtyard extents of U911 and U921 (U911 y 45.33 to 55.06) that differ from the built footprints' by up to 1.2 mm (U911's built courtyard is y 44.19 to 56.19). The row's claim, that each part stands inside the rectangles of its region, is still true. It is a frozen baseline row and is not covered by the amendment note after layout review round 9.
- `layout-review.md`, round 9, finding 9.1's Closed by: it says `owner-sign-off.md` names Round 9 as the closing round. That was true when written; the round number was removed from the live records in commit `026c8053`, and the Closed by is history and is not edited.
- `CONN-1` stays not applicable: the varistors are surge clamps, which `SURGE-1` lists apart from the connectors.
- `layout-hedges.md` hedge 17 says "H1 only" for the exclusion from the position file, while the six hand-fitted surface-mount parts (R911, R912, R921, R922, U911, U921) carry the same flag; line 33 of the same file and `open-items.md` say so, and no live statement is untrue.
