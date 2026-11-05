# Lessons of the main board build, for the next board

This records what the main controller board's design taught, so that the next board (the heater wall board) starts from it. It is written for someone who has not seen the main board's work. It says what to do first, what went wrong and what it cost, what worked, which tool defects were found and where the graph carries them, and what is still open.

How to read the evidence. Each lesson ends with an `Evidence:` line. Where a file or a commit in this repository shows the fact, it is named. Where the fact is only in the build's working notes (a handover note, scratch reports and logs, none of them committed), the line says "working notes"; those figures could not be re-checked from the repository, so treat them as reported. Graph nodes are named by id and can be read with `show`.

The lessons were first drawn from memory and then checked against the record. Twelve were kept, four of them with corrected figures or wording (L7, L8, L10, L11), one sub-claim was dropped (the cherry-pick detail in L11), and ten were added (A1 to A10).

## Start here for the wall board

The leaf is `SOL-HW-HEATER-WALL-BOARD-PROVEN-AND-LAID-OUT`, under `DEL-HW-HEATER-WALL-BOARD-DESIGNED`. At the time of writing it is blocked on its prerequisites and has no folder under `hardware/sunbeam-em7000/` yet. The division record sizes the board at 57.0 x 42.5 mm with 39 hand joints: two heater triacs on a bracket, an opto-triac, a blade terminal, a varistor and a three-way header. The two mains-presence confirms, the current sensor and the snubbers are off it (the confirms may return if the owner decides so, `controller-board-division.md`, owner decision D2). It places no controller, no clock and no converter input.

Each step says whether the wall board can skip it, and why.

1. **Check that the prerequisites are built before anything else.** The leaf depends on the assembly judgements, the pre-order check for a board without a controller, the main board's schematic and its pin allocation record, and the pollution degree 2 basis. The engine refused to start the main board's layout leaf for exactly this reason (its dependent leaves were unbuilt). Keep. Evidence: A10.
2. **Reopen nothing the assembly judgements settled.** The parts, heat sinking, bracket, harness and surge-clamp figures, the temperature and current shares, and the owner's cut are inputs. Draw to them. Ask the owner a physical fact only if the outline changes. Skip any new physical analysis, because the dependency already did it. Evidence: leaf text, L12.
3. **Settle three policies in the plan before drawing.** (a) The severity of workmanship lines: which classes are cosmetic and which are errors (L9). (b) That plan rows are written only for what the geometry can meet, and are checked against it (A5). (c) That there is one frozen batch order for design changes (L3). Keep, all three.
4. **List the barriers the board forms and compare them with the signed basis.** `separation-basis.yaml` already lists a `heater-switch` barrier and is signed. A barrier it does not list is reported and the owner re-signs; a distance is never relaxed (leaf C5). Skip the scratch-signed copy the main board needed (L1, A1): the committed basis is signed, so the mains rules run on the real file from the first check. Make a scratch-signed copy again only if the wall board needs a new exception or barrier, and follow A1 when you do.
5. **Choose parts for creepage at schematic time.** A part's own geometry fixed the main board's hardest mains-to-mains pairs: opto-triac pin 5 at 0.76 mm, a 1206 resistor's pad gap of 1.8 mm, a triac tab-to-lead gap of 2.0 mm. Fixing those after layout was a package change or a slot through locked mains copper. Read the pad geometry of the opto-triac, triac and any resistor against 2.6 mm before the part is chosen. Keep (A7).
6. **Draw the schematic and prove the hold-off (C1, C2).** Heater switches must be off with the controller in reset, unpowered or disconnected, with no firmware acting. Run the proof scripts, then compare every proof constant with the schematic netlist by machine (L10). Skip the error budget and the signal study: the board has no sense input, clock or converter. Keep the machine comparison, which is small here.
7. **Resolve the header channels to the main board's pin allocation record (C4) and author the records (C3, C7, C8).** The pin allocation, parts, derating and pin-limit records and the catalogue extract. Grade every part against the enclosure air figure and the 253 V span. Expect derating exceptions for 250 V parts, and expect each to need an owner-signed entry in the derating policy (the main board's ten were drafted unsigned, then signed). Keep.
8. **Fix the laminate and coat wording first (C10, C11).** The main board found that a laminate index below 175 is no precondition at pollution degree 2 (L1). The wall leaf's C11 still states the old precondition. Amend it in place, before the build, and propagate (A4, Open questions).
9. **Floorplan and plan (C9).** Triac tab-hole height, bracket mounting, 5.0 mm of mains copper kept from the wall edge, and the leaf's one detail: the two board-mount holes reach 0.55 mm under the standing leg. Keep. Skip the layer-count and escape study: the main board needed it for a 444-footprint board with a many-pin controller and six signal classes (A3). Choose the layer count from the mains rules and hand soldering.
10. **Place, route by hand, lock.** Skip the fenced router passes, the discarded router copper and the batched redos (A3). With every net near mains, route by hand to the rules and run the standing gate set on a scratch copy after each piece (L5). Run the mains checks right after placement and again after routing (L2).
11. **Run the pre-order check once on the frozen design, then the views, then one review round.** Use the kit's `--plan-only` first. The wall board is small, so the kit may fit where the main board's did not (L7). Skip the hand-built group sessions unless the plan refuses.
12. **Orientation and marks.** Opto-triacs have pads that are symmetric under 180 degrees: add a pin-1 mark outside the body and the bring-up orientation check (A6). Keep.
13. **Blind review before the pull request, with the graph diffed against `main`.** Keep (L6).
14. **One `check:round`, once, on the final commit.** Keep. Set the tool path the gate's board tier needs before starting it (L11).

## What went wrong and what it cost

### L1. The riskiest result was learned last (kept, corrected)

The mains-spacing rules run only when the separation basis is signed. The board was routed, reviewed and judged for a long stretch with those rules not running; the first run that exercised them on the finished layout then forced a pass of design changes after the layout review round had closed its views. A scratch-signed check early (outside the repository, never committed) would have shown the shortfalls (five mains pad pairs just under 2.0 mm, four gate-resistor pairs at 1.8 mm, the fiducial clearance overrides, spare opto pins) while moving a part was cheap.

The laminate worry cost effort the same way. Maker datasheets were researched at length for a tracking index of 175 or more, and the criterion for it was marked not met. Only then were the standards read: at pollution degree 2 the creepage table has one "group III" column covering groups IIIa and IIIb, so an index below 175 changes no figure. The criterion was reworded and re-evidenced. Read the standard's column structure before building process around a material figure. Caution kept from the record: the standards were read through reproductions in certification reports, not the standards' own text (basis header, readings 1 to 4), so the owner or a test house confirms them if the machine is ever certified.

Evidence: `pre-order-check-result.md` ("the mains-spacing rules did not run, because the basis is unsigned"); `fabrication-notes.md` (the group III reading and the CTI table); commits `9a2a3268`, `52d5e92a`, `66cd6a53`; graph node `SOL-SEPARATION-BASIS-LAMINATE-CONDITION-NEEDS-NO-INDEX-AT-POLLUTION-DEGREE-2`; the signed-copy results in working notes.

### L2. Tool defects surfaced very late (kept)

The checks only showed their own faults when run on a signed copy of the finished board: the pad-text defect (86 exception lines looked unexplained), the mounting-hole rule (87 false lines for one-pin tab terminals), a net tie's graphic read as low-voltage copper (30 false layer-separation lines), and the derating rule's ten exceptions that had to be drafted. Each was found within hours of the first signed run and each took a fix commit plus a graph item. The lesson drawn: run the function-level checks on a scratch-signed copy right after placement and again after critical routing, not only on the finished board. (The record shows the late discovery; the earlier cadence is the remedy, not something the build did.)

Evidence: commit `579ca814` and nodes `SOL-PRE-ORDER-CHECK-READS-A-SURFACE-MOUNT-PAD-IN-KICADS-REPORT`, `SOL-PRE-ORDER-CHECK-MOUNTING-HOLE-LEAVES-A-PLATED-TERMINAL-ALONE`, `SOL-PRE-ORDER-CHECK-NET-TIE-COPPER-IS-THE-COPPER-OF-THE-NETS-IT-JOINS`; commit `cb7f9844` (derating drafts); the pass-4 plan in working notes.

### L3. Design changes after a review round are expensive, so batch them (kept)

Any change to a board file, or to any non-record file in the board's folder, after a layout review round faults the review-history check, forces a full pre-order check (99 to 148 minutes in the three runs recorded), a full render of the views (55 to 70 minutes) and a new review round. The main board's round 2 was left not closed (25 pass, 62 fail) and a further design pass (the plan's pass 4: fiducial rule, paste windows, test point moves, mounting-hole keep-outs, via keep-outs) was then applied after it. The review-history check therefore "fails only the closing round" on the final commit. Freeze design files; do all passes in one order (mains first, then performance, then router and workmanship, silk last); verify once.

Evidence: commits `ec570a3c` and then `b5213b97` to `c25f3af6` (later in history than the round); `4b782c4f` (message); `CLAUDE.md` gate timings; run times in working notes.

### L4. Frozen text cannot be edited, even to tidy it (kept)

The history check reads the layout plan's Placement section and both routing passes as they were recorded. Replacing scratch paths with placeholders (a tidy-up the blind review asked for) raised the failing count from 68 to 71 of 94, and changing "unsigned" to "signed" in one frozen row made it 69. Both had to be reverted. Put corrections in a new record or in a section the check does not freeze.

Evidence: commits `1e838567` and `fdc0e1b8` (messages); `cad6d308` (the change that was reverted).

### L5. Do the passes by script on a scratch copy, with a standing gate (kept)

What kept the late passes safe: each pass was a script on a scratch copy, gated by the same set every time (whole-board connectivity by pcbnew, the exact spacing and clearance checkers, the mains-barrier function, the inner-plane fill check, the locked-copper compare with re-record, placement totals, and the history check), applied to the live board and committed as one item per commit so a revert is easy. Heavy compute was capped at four workers. Pieces were bounded (a fresh agent per piece of roughly 80 to 100 tool calls) instead of open-ended variant loops. The pass-3 and pass-4 commits each carry before-and-after counts.

Evidence: commits `34164bd9`, `9eeff9f0`, `bb6cd62c`, `bc783865`, `b5213b97`, `87095ca4`, `c689afc1`, `b1f2d928`, `786b7673`, `c25f3af6`; gates and the piece-size rule in working notes.

### L6. Graph hygiene: never copy files from another branch over this one (kept)

Copying the first board branch's files over this branch silently rolled back newer graph content that `main` already held. One criterion lost a sentence and went back a version, another was deleted and its id was reused for different content. Only the blind review found it, and four restore commits followed. The record also shows four defects of unsealed main-board work filed in the maintenance lane, which the project rules reserve for sealed work; they were re-pointed at the main board task. Rules that follow: diff `specs/` against `main` before opening the pull request; never reuse an id; fix defects of unsealed work in place and use the maintenance lane only for sealed work. (The diff step is the remedy; the record shows the failure and the review catching it.)

Evidence: commits `8ec71ff8`, `0c143f88`, `47dd3835`; node `SOL-HW-CONTROLLER-BOARDS-ORDERED-AND-RECEIVED` (C3 and C4); `CLAUDE.md` ("Editing the graph"); the blind review's findings 1, 2 and 10 in working notes.

### L7. The review kit could not take the board (kept, corrected)

The layout caller refused the main board before any spend: its shared documents were 4,950,717 tokens against a 400,000-token budget, because the prior rounds' record and the view index were counted whole in every root. Rounds were then run as seven hand-built group sessions merged by "any fail stands". The merge refuses shape errors, so reviewers must be briefed on the exact form: a finding is cited as "finding N.M", a code span in a table cell must not hold a pipe, and every finding states an (x, y) place; thirteen format-only repairs were needed in round 2. An item fails if any one instance fails, so the item count barely moves while real lines fall.

Correction to the figures first drawn: between round 1 and round 2 the check's lines fell from 2,042 to 1,597 on the unsigned basis (a signed run of the same board gave 1,291), while failing items went from 61 to 62 and passing items from 26 to 25. Run `review_run.py --plan-only` before launching, and keep the earlier-rounds record and view index small, or extract them (the extract item is authored, not built).

Evidence: node `SOL-HW-REVIEW-KIT-SHARED-DOCUMENTS-HELD-AS-EXTRACTS` (its text holds the token figures); `layout-review.md` (round 2); `pre-order-check-result.md`; commit `ec570a3c`; the repair log and the signed run's totals in working notes.

### L8. Do not invent exceptions; fix first, accept last (kept, corrected)

Wording corrected. The build never drafted an exception against a mains-to-low-voltage figure: those held by design (nearest surface path 10.207 mm against 10.0 mm; the one pair a reviewer put at 9.96 mm measured 10.414 mm three ways). Mains-to-mains pairs that a part's own geometry forced were drafted as unsigned exceptions after cheaper fixes were tried: five pad pairs were moved clear; a milled slot between a 1206 resistor's pads or between opto pins was prototyped and rejected, because the slot needed seven locked mains tracks re-routed or could not fit; a longer resistor package was a schematic and parts change. What remained was signed by the owner, in writing, on 2026-11-05: 33 mains-pair exceptions and ten derating exceptions. Sixty-nine drafted entries that the signed run showed unused were pruned first.

Check the draft's own arithmetic, too: the first draft said the branch fuses would clear a triac tab-to-lead breakdown, but the fault current (0.46 A and 0.19 A) is below the fuse ratings (0.8 A and 0.5 A). The reasoning was corrected and the acceptance rewritten to say the interlock relay bounds it and is not independent of the controller.

Evidence: commits `25f060ea`, `07d4bc29`, `5841a9bb`, `8c875494`; `separation-basis.yaml`; `DEC-MAIN-BOARD-RESIDUAL-RISKS-ACCEPTED-BY-OWNER` (items (e), (i)); `pre-order-check-result.md` (the 10.414 mm measurement); the pass-1 and pass-4 reports in working notes.

### L9. The pre-order check has no way to accept a workmanship line (kept)

The check accepts a mains spacing shortfall only through a signed exception in the basis, and a derated position only through a signed derating entry. It has no such mechanism for workmanship or neatness rules, so it exits non-zero on any such line. The main board ended with the check red on those lines (router angle, segment length, pad entry, detour, silk, courtyards), the owner accepting that on the condition that no further change is a net gain across safety, then performance, then workmanship. A maintenance solution for a signed workmanship acceptance record was authored in the last commit and is not built. Decide before the wall board which line classes are cosmetic warnings and which are errors, so that it can end green.

Evidence: `DEC-MAIN-BOARD-RESIDUAL-RISKS-ACCEPTED-BY-OWNER` (item (o)); commit `443be725`; node `SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES`.

### L10. Evidence before claims: machine traceability, signal study, error budget (kept, corrected)

Done after layout and before ordering, they were cheap. The traceability pass compared every proof constant with the schematic netlist and re-ran the proof scripts: no part value differed, and it found one mismatch, in the flow-meter input, in three parts. The schematic and board disagreed on which parts were fitted (the records admitted that), the proof decks modelled a different configuration, and the sheet generator would have silently undone the fit when re-run (the last two were not admitted). The decks and generator were repaired and a test runs them in a copy. The signal study found three marginal items, each closed by a firmware setting or a bring-up reading, not copper. The error budget showed that better resistors matter in two places only, the mains voltage divider and the shunt. The first drawing said "one real mismatch the records admitted"; that is only part of it.

Evidence: `traceability.md`, `signal-study.md`, `error-budget.md`; commits `588e5880`, `3fcf8867`, `274ac8f0`; node `SOL-HW-MAIN-BOARD-SHEET-GENERATOR-REPRODUCES-COMMITTED-SHEETS`.

### L11. Process: tiers, monitors, one writer (kept, corrected)

Default to a mid-tier model at medium effort. Use high effort only for locked mains copper and safety wording, a small model for deterministic render and run jobs, and the reasoning tier only for read-only advice or a class of misses (it was used eight times, including the blind review; the first drawing said only the blind review). Announce the tier at every dispatch. Arm a monitor on every long job; monitors expire after 30 minutes and must be re-armed, and agents often end before their detached jobs. One writer per worktree at a time; work on a separate branch and worktree for parallel code work (the review-kit fix went on its own branch and merged as its own pull request). The "cherry-pick from a separate worktree" detail in the first drawing is dropped: the record shows nothing was cherry-picked. Timings seen locally: `hw:verify` 100 to 150 minutes, `hw:views` 55 to 70 minutes, `check:round` about an hour and it runs emulation whenever the Taskfile changes. The gate's board tier needs `KICAD_CLI` set.

Evidence: `CLAUDE.md` (tier and gate sections); working notes (the branch reconcile report says "nothing was cherry-picked"); commits `93bbca90` (the review-kit merge) and `ec570a3c`; tier and monitor lessons in working notes.

### L12. Owner interaction (kept)

The owner is not an electronics engineer: give short plain answers with a recommendation, and ask only for facts only the owner holds (signing, the fabrication account, physical facts). A decision delegated to the agent is recorded as the agent's, with the agent's evidence. The owner's own acceptance is entered only on explicit written instruction, and is stated as given: item (m) records "accepted on the agent's recommendation with the owner's agreement in session", item (n) is "recommended and recorded, not confirmed by the owner", item (o) separates the owner's words from the agent's assessment. The signed basis names both the owner and the agent that entered it.

Evidence: `DEC-MAIN-BOARD-RESIDUAL-RISKS-ACCEPTED-BY-OWNER` (items (h), (m), (n), (o)); `separation-basis.yaml` header; commits `5841a9bb` and `4b782c4f`.

### Lessons the record added

**A1. A scratch signature must be complete or it unlocks nothing.** The first signed attempts changed only the record's top-level fields, so the 98 exceptions stayed void and the rules reported nothing new. The check reads acceptance on the record and on every exception, and requires the record to be committed exactly as it stands (a scratch commit in a throwaway worktree). Evidence: `pre-order-check-result.md` ("a second run with a scratch top-level signature unlocked nothing"); the signed-check note in working notes.

**A2. Never trust a tool's "clean".** KiCad caps its report at 499 per rule for clearance and 199 for angle and segment length. The unconnected list was believed capped too, and at one point hid 224 of 723 open pads, mains pads among them; a later check found it uncapped (284 listed), so test a cap rather than assume it. Four "complete" claims were wrong because of how a tool was read. Use a whole-board connectivity gate, count with your own uncapped counter for any capped class, and say in each record which counts are floors. Evidence: `pre-order-check-result.md` ("not complete counts of the underlying items"); working notes (cap finding).

**A3. Decide the stack-up from an escape study, and keep the router away from critical copper.** The board was laid out on four layers, then moved to six after the 4-layer best was 69 open pads against 26 on six; the critical copper was locked, discarded and re-laid in batches. The first router pass produced no workmanship-clean net out of 90 and placed 144 items on a locked critical class, which the method forbids; its copper was removed. Plan the layer count and the pin escapes at placement. Evidence: commit `ec05ca97` (six layers); `fabrication-notes.md`; router and stack-up studies in working notes.

**A4. A change is chased through every record that restates it.** Removing twelve test points touched seven sheets, the board and about fifteen records; a laminate wording change reached the main board's criteria but not the wall board's. Evidence: commit `5231707b`; commit `66cd6a53` against `SOL-HW-HEATER-WALL-BOARD-PROVEN-AND-LAID-OUT.C11`; the stale-record finding in `schematic-review.md`; Open questions below.

**A5. Reviewers judge by the item's wording, and a recorded row does not turn a fail into a pass.** The history check closes a first-review fail only by a re-route and a re-judge that passes, so records cannot close it. Twenty-five routing fails in pass 1 and forty-three in pass 2 stand frozen (68 of 94), and several plan rows disagreed with the board (a "resistors at their pins" row, a "0.56 mm from the triac" row). Write only plan rows the geometry can meet and check each against the board before the first review. Evidence: commit `1e838567` (message); `layout-plan.md`; working notes (re-judge results).

**A6. Parts with 180-degree-symmetric pads need an orientation guard.** An adversarial safety review found that a rotated opto-triac or isolated converter would put mains pins on low-voltage pads, with no bring-up check. A pre-energisation orientation and isolation check and pin-1 marks outside the body were added. Evidence: `bring-up-provision.md` (the orientation and isolation check); `layout-plan.md` (row ORIENT-1); commit `55646e0f`; working notes (safety review).

**A7. Fix part-geometry shortfalls at part choice.** See Start-here step 5 and L8; the package alternative cost a schematic and parts change after layout. Evidence: `layout-plan.md` open rows; pass-1 and pass-4 reports in working notes.

**A8. Do not edit a frozen proof design, or put one board's notes in another's plan.** A proof design is keyed by the bytes of all its files; editing one invalidates its recorded baselines. The blind review found the main board's routing notes appended to a proof design's layout plan; they were moved and the proof file restored. Evidence: commit `7772630c`; `CLAUDE.md`; blind review in working notes.

**A9. Committed records should not name scratch paths.** Records carried machine-specific scratch paths and absolute locations. Frozen sections cannot be cleaned (L4), so write new records with placeholders from the start. Evidence: commit `cad6d308`; blind review finding 14.

**A10. Check build readiness before a leaf's run.** The engine's preflight stopped the main board's layout leaf because four dependent leaves were unbuilt, one of them the owner's own signing act, which must never be reworded to bypass the signature. The layout, records and reviews therefore ride in the pull request unattested. Evidence: working notes (the workflow run report); the leaf's `depends-on` links.

## What worked

- **Independent checks that do not share the tool's blind spots.** Whole-board connectivity by pcbnew, exact spacing and clearance checkers, and an uncapped counter were run beside the pre-order check on every pass. Evidence: L5, A2.
- **An adversarial safety review by a fresh reviewer.** It reproduced the 104 creepage items, confirmed no mains-to-low-voltage defect, and found the orientation hazard, a wrong fuse-bound argument, and a missing orientation check. Evidence: A6, L8.
- **Hand routing of critical nets to a plan, locked, compared with a copper record after every pass.** The comparison showed zero change on mains classes across redos. Evidence: commits `398482dd`, `d685d6b5`; pass reports in working notes.
- **Cheap margin where spacing allows.** Parallel mains copper on another layer, with vias, dropped a trunk rise from about 30 K to 6 to 11 K; same-layer widening was proven impossible by the exact checker. Evidence: working notes (neck round).
- **Records that state what ran.** The pre-order result names the commit, command, runtime, capped counts and what the run does not cover. Evidence: `pre-order-check-result.md`.
- **Blind review before the pull request.** It found eleven issues, seven of them graph propagation. Evidence: L6; working notes.
- **Owner acceptance recorded as the owner's, with the agent's view kept apart.** Evidence: L12.

## Tool and process defects found (with the maintenance nodes that carry them)

Maintenance nodes carry only defects of work that was already built. Defects of unsealed work were fixed in place (L6). The nodes below were authored on this branch and are not built unless stated.

- Pad text of a surface-mount pad in KiCad 10's report not read (exceptions never matched): `SOL-PRE-ORDER-CHECK-READS-A-SURFACE-MOUNT-PAD-IN-KICADS-REPORT`. Fixed in `579ca814`.
- Mounting-hole rule counts a one-pin plated terminal as a fixing: `SOL-PRE-ORDER-CHECK-MOUNTING-HOLE-LEAVES-A-PLATED-TERMINAL-ALONE`; plated hole of a low-voltage part not measured round slots: `SOL-PRE-ORDER-CHECK-PLATED-HOLE-OF-A-LOW-VOLTAGE-PART-IS-MEASURED-ROUND-THE-SLOTS`. The first fixed in `579ca814`.
- A net tie's graphic read as low-voltage copper: `SOL-PRE-ORDER-CHECK-NET-TIE-COPPER-IS-THE-COPPER-OF-THE-NETS-IT-JOINS`. Fixed in `579ca814`.
- A slot open to the board edge not read: `SOL-PRE-ORDER-CHECK-READS-A-SLOT-OPEN-TO-THE-BOARD-EDGE`.
- Creepage path runs through a slot junction (an over-conservative reading, 9.179 mm where the true path is 15.5 mm): `SOL-PRE-ORDER-CHECK-CREEPAGE-PATH-HOLDS-AT-SLOT-JUNCTIONS`.
- No way to accept a workmanship line: `SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES` (authored, not built).
- Exceptions must cover every reported shortfall pair, and must stay unsigned until the owner signs: `SOL-MAIN-BOARD-EXCEPTIONS-COVER-EVERY-REPORTED-SHORTFALL-PAIR`; the record's signature and the derating signatures: `SOL-SEPARATION-BASIS-RECORD-STANDS-SIGNED-ON-THE-FINISHED-LAYOUTS-EXCEPTION-SET`.
- The pump-triac exceptions follow the land drawn: `SOL-SEPARATION-BASIS-PUMP-TRIAC-EXCEPTIONS-FOLLOW-THE-LAND-DRAWN`. The laminate condition: `SOL-SEPARATION-BASIS-LAMINATE-CONDITION-NEEDS-NO-INDEX-AT-POLLUTION-DEGREE-2`.
- Review kit counts shared documents whole in every root: `SOL-HW-REVIEW-KIT-SHARED-DOCUMENTS-HELD-AS-EXTRACTS` (authored, not built).
- The Konnect tool cannot set a do-not-populate or in-bill flag on a schematic symbol, so three expected parity lines stay, and the fabrication bill must come from the board's attributes: `SOL-HW-DO-NOT-POPULATE-PARITY-LINES-ARE-LISTED-AND-BOARD-DRIVES-BILL`.
- The sheet generator would undo a committed decision when re-run: `SOL-HW-MAIN-BOARD-SHEET-GENERATOR-REPRODUCES-COMMITTED-SHEETS` (the generator was fixed in `274ac8f0`).
- A library footprint differing from the board's by a paste aperture: `SOL-HW-MAIN-BOARD-U601-LIBRARY-FOOTPRINT-MATCHES-BOARD`.
- The cost estimate states no quantities at six layers: `SOL-HW-BOARD-COST-ESTIMATE-STATES-QUANTITIES-AT-SIX-LAYERS`.
- Konnect works only in the main session, cannot delete vias or edit rule areas, and rewrites files with large diffs, so bulk edits run through pcbnew scripts under the project's "for what Konnect cannot do" rule. Evidence: working notes.

## Open questions

1. **KiCad's capped lists have no maintenance node that a search found.** The check should fail or split its run when a rule reaches the cap (499 for clearance, 199 for angle and segment length, and the annular and unconnected lists). The record lists it as owed. Search the graph, and author the node if none exists. (Evidence: A2.)
2. **The wall leaf's laminate criterion is out of step.** `SOL-HW-HEATER-WALL-BOARD-PROVEN-AND-LAID-OUT.C11` (version 1) still says a laminate below 175 is reported and the owner re-declares the basis. The main board's C16 (version 4) says that at pollution degree 2 this is not a precondition. Amend C11 in place before the build starts. Its coat criterion C10 already matches the main board's.
3. **The owner's severity policy for workmanship lines is a decision, not yet a mechanism.** Until the maintenance solution is built, the wall board's check cannot go green on any such line. Which classes are cosmetic is unwritten.
4. **First-review fails cannot be closed by reasoned records.** The history check closes only on a passing re-judgement, so the main board's 68 standing fails remain. The record lists "closure by reason for a first-review fail" and a "placement-time routability check" as graph items; a search found neither. Decide whether the method or the plan should change before a board this size.
5. **Do the kit extracts fit the wall board?** Run `--plan-only` on its review folder; if refused, the extract node blocks and the hand-built groups return.
6. **Standards readings are unverified.** The basis header's four readings (the 0.5 mm terminal allowance, the group III column, interpolation, the 253 V working voltage) rest on reproductions. They matter for the wall board's own creepage and are for the owner or a test house if the machine is certified.
7. **The wall board's own mains-pair exceptions are not drafted.** Choose parts so none is needed (Start-here step 5); if one is, it is a fresh owner acceptance.
8. **The mains-presence confirms may return.** If the owner decides so (division record D2), the board grows to 57.0 x 52.5 mm with a six-way header and a T of slots, and the criteria for the barrier and header change.
9. **Order-time questions from the main board are open and carry over to the wall board's order leaf:** the laminate maker's written identity and certificate, and, for six-layer main-board orders only, the via finish over 0.55 mm and the real fee.
