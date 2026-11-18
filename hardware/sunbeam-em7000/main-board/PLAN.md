# Main board v2: restart of the low-voltage half (plan)

**Naming note (2026-11-17).** This plan was written while the board was called v2 and its folder `main-board-v2/`. The first design never reached `main`, so the board is now called v1 and its folder is `main-board/`; `DEC-BOARD-VERSION-NAMING-V2-WORKING-NAME` records why. The text below keeps the working names "v1" (the earlier, frozen first design) and "v2" (this board) as they were when the plan was written, and the paths in the commands now read `main-board/`.

Written 2026-11-10 on branch `req/DEL-MAINTENANCE/pre-order-check-fixes` (HEAD 4b64810b plus the uncommitted U201/U203 schematic change). This is a plan, not a record the check reads. It decides the order of work, the cheap go/no-go tests that run before expensive work, and where a finding sends the work back.

## Recommendation

1. Restart placement and routing of the low-voltage half in a new design folder, `hardware/sunbeam-em7000/main-board-v2/`, which becomes the board's permanent home. v1 (`main-board/`) is frozen as a git tag and removed from the tree on this branch, so only one design is ever checked.
2. Adopt pin map A (SPI3, I2C4, FLOW_IN on TIM2_CH3, selects and HX711 lines on PD0 to PD7 as first adopted; routing then moved seven signals, and `controller-pin-table.md` states the final assignment) now, with two changes: ANODE_GATE stays on PB5, and AMC_RESET goes to a freed plain GPIO (PC8 or PC9) instead of PB4. Settle it before placement, because placement is scored against it. The schematic review round is owed anyway for the U201/U203 change, so the pin map rides in that same round.
3. Stay at six layers. Four layers would reopen the signed separation basis, the fabrication notes and via fill to save about 32 to 52 USD. Route as if the board were four layers (F.Cu and B.Cu, In3 as a spare), so the choice can be revisited later on evidence.
4. Order of work: freeze and seed, then a scratch go/no-go, then schematic and pin map, then floorplan and records, then placement, then rules, then mains copper and critical routing, then the rest, then one review cycle, then close-out. Nothing expensive (schematic edits, the review round, Konnect placement) starts until the go/no-go has passed on scratch.

## Decisions taken in this plan

| Question | Decision | Why |
|---|---|---|
| Folder | `hardware/sunbeam-em7000/main-board-v2/`, permanent. The KiCad file stem stays `main-board` (`main-board.kicad_pro`, `.kicad_sch`, `.kicad_pcb`, `circuit-proof/main-board.cir`). | `task hw:history` (`hardware/tools/board_history.py`) reads every version of the board file at its path and judges the placement section against the first commit with a footprint and the first commit with copper. At the old path those are v1 commits from weeks ago, so a re-placed board at `main-board/` can never pass. A new path starts a clean history. Renaming v2 back to `main-board/` at the end would merge the two histories again and fail the same way, so v2 keeps its folder. |
| v1 at the end | Removed from the tree on this branch (in the seed phase, not at the end), frozen as the local tag `main-board-v1-final` on the commit just before removal (commit e8615c82; the tag is not published). | `board_check.py` checks every tracked `.kicad_pro` (`discover()`), so two tracked boards double every full check (about 2.5 h to about 5 h). v1 also cannot pass parity once U203, R208 and C206 are in the shared schematic. A worktree of the tag gives read access for comparisons. Pushing the tag needed the owner's go-ahead; none was given and the tag is not published (see Questions for the owner, item 3). |
| Pin map | Pin map A with the two changes above. | See the next section. |
| Layer count | Six, same stack-up, same In1 ground and In2 mains pours; amended 2026-11-12: In2 also carries a `+3V3` pour over the low-voltage digital area (`layout-plan.md` Stack). | Safety first: no separation re-proof, no change to the signed basis. The pilot (a scratch report kept outside the repository) put 1 to 3% of routed length on inner layers, so six layers gives margin, not cost risk. |
| Via drill (0.2 vs 0.3 mm, quote pending) | A parameter. Every ordinary via is 0.3/0.6 mm whatever the quote says. Only the vias inside exposed pads (U620, U621 and any other exposed pad) wait on the quote. | A larger drill never costs more and the pilot never needed 0.2 mm. At six layers JLC fills vias up to 0.55 mm across by default, so 0.3/0.6 vias are left open, which is fine away from pads. Exposed-pad vias must be filled or tented: 0.2/0.5 (filled by default) if the quote shows 0.2 mm is free, otherwise 0.3/0.6 with paid filling, otherwise moved out of the pad. That is a late, local swap of about 18 vias, applied in phase 6 before those parts are locked. |
| Vias in SMD pads | None, except exposed thermal pads. | v1 needed an owner acceptance for six. v2 designs them out. It becomes a board item (below). |
| Via drill update (owner, 2026-11-10) | The quote shows 0.2 mm drills add about $50 and force the 4-wire test, as a capability price, not per hole. Once chosen, 0.2 mm is usable anywhere it helps. Filled vias must have a pad of at most 0.5 mm (JLCPCB leaves larger ones open). | Owner's live quote. Whether 0.2 mm is chosen at all is decided in phase 3 on the escape evidence; the 0.5 mm limit is read as the pad, the safe reading. |
| Harness headers J791 and J821 | Pin 1 stays pin 1 and the way order is fixed. Each socket may be rotated to any angle. | Owner 2026-11-10: the swap from the old machine stays backwards compatible and others can reuse the design. Reordering is a last resort needing his sign-off. |
| One-sided assembly | Every assembled part on F.Cu. Test pads only on B.Cu. | Owner decision 2026-11-07, carried from v1. It becomes a board item. |
| 1 mm minimum run (WORK-5) | Kept as written, pad-to-via stubs included. Superseded 2026-11-11: see the next row. | The pilot's density loss came from facing pad rows and parts in the MCU's lanes, which placement fixes (board items below). Residual stubs fall under the owner-signed severity policy, counted from the final board. |
| Minimum run 0.5 mm and U401 ground stubs 0.2 mm (owner, 2026-11-11) | `Jogs` (`track_segment_length`, WORK-5) is 0.5 mm, not 1 mm; the 135 degree corner rule (WORK-4) is unchanged. The six ground pin stubs of U401 (pads 10, 19, 26, 49, 74 and 99) may be 0.2 mm wide instead of the `Ground` class's 0.45 mm, by the rule `U401 ground pin stubs` in `main-board.kicad_dru`. Safety and performance are not touched. | Both figures were the plan's own, challenged under the standing instruction. The U401 pin pitch is 0.5 mm, so stubs under 1 mm are unavoidable, and a 0.5 mm segment is within normal fabrication practice (minimum track and space 0.09 mm). A 0.45 mm stub cannot coexist with the 0.2 mm pad clearance on a 0.5 mm pitch, and a 0.2 mm stub into the ground plane carries one pin's small ground current. |
| Routing tools | Exploration and the go/no-go use scratch tools outside the repo (the pilot's `rt/router2.cpp`, `gen_spec.py --esc`, `place.py`, `apply.py`). The committed board follows the method: Konnect in the main session for placement and critical nets, Freerouting through `task hw:freerouting` and KiCad's exporter/importer for the rest, KiCad scripting only for what the method's "What Konnect cannot do" list allows. | The method (`docs/board-design-method.md`, Placement step 2 and Routing step 2) names Konnect. A scripted placement or route in the committed board would be a method change. Scratch geometry is used as a drawing guide that Konnect follows. |
| Branch and PR | Keep the current branch, so the eight parked WF-BUILD runs are not disturbed. One PR at the end, merged by a merge commit, never squashed or rebased. No rebase or force-push after the first v2 placement commit. | Any earlier PR's board tier would judge v1, which has not passed a full check since its last edits. The history checks cite commits, and a rewrite drops them. |

## Pin map A: adopt now

**What it buys.** OPINION2's scoring (straight-line, today's destinations): at (95, 60) rotated 180, wrong-side pins go from 19 to 15, length from 2145 to 1964 mm, and crossings from 276 to 191. At the best grid point (100, 75) it reaches 5 wrong-side pins and 147 crossings. The pilot was run on pin map A with the MCU at (100, 75) rot 180 (a scratch file kept outside the repository). Where nets completed, they came out at 20 to 40% of as-built length (for example PT1_CS 36.8 mm and 0 vias, against 175 mm and 7 vias). So pin map A is already the evidence base. Keeping today's pins would mean re-running the probe on a placement nobody has tested.

**What it reopens.** All of this is bounded, and most of it is owed anyway:
- **Schematic.** `31-controller.kicad_sch` (the labels sit on the MCU pins, so every moved net is a label and no-connect move there), and the rename SPI2 to SPI3 of three nets in `main-board.kicad_sch`, E1 and E3. The other label sheets keep their net names and are not touched. Then `schematic-spec.yaml` and `sheets/*.yaml`. `PHASE2-CHANGE-LIST.md` lists every item.
- **Pin records.** `controller-pin-table.md`, `pin-allocation.yaml` and `pin-limits.yaml` (comments only; every limit is the same 6 V FT figure). `controller-input-map.yaml` holds converter inputs only and does not change.
- **Proofs** in `circuit-proof.md` and `circuit-verdicts.md`:
  - the reset and boot-ROM state of every moved pin;
  - the bootloader case: SPI3 is a bootloader slave port, so the proof must show the converters' outputs on PC11 cannot fight the bootloader (each select is held high by a pull-up);
  - PB12 is FT_u, so VALVE_3W_DRV must see no 5 V pull-up;
  - FLOW_IN on PB10 is FT_f.
- **Firmware: no cost.** No `firmware_channel` binds a pin today.
- **Graph.** DEL-HW-MAIN-BOARD-DESIGNED.C27 and SOL-FW-SPI2-PORT-RUNS-SLOW-EDGES-AND-A-LOW-CLOCK change SPI2 to SPI3. Their limits get re-derived from the v2 signal study.
- **Review.** A schematic review round, which the U201/U203 change already forces.

**Changes to OPINION2's table.**
- ANODE_GATE stays on PB5. PA7 is TT and uses up a spare ADC pin.
- AMC_RESET goes to PC8 or PC9, whichever scores better in phase 1, not PB4. PB4 powers up as NJTRST with a pull-up, which adds a proof row for no routing gain.
- Pins that keep their place (OPINION2 "Must stay"): PA8, PA9, PA10, PA11, PA12, PA13, PA14, PB3, the oscillator pins, the ADC pins, KEY1 to KEY5, and PD14/PD15.

**Sequencing.** The pin map is tested on scratch in phase 1 by net remapping (as the pilot did), so no schematic edit is spent before the go/no-go. Phase 2 commits it to the schematic. Phase 4 places against it.

## Folder and tooling facts this plan relies on

- `task hw:verify` runs `board_check.py --root .`, which finds designs from git's tracked `.kicad_pro` files. There are no subset flags. A tracked schematic or layout with no project beside it fails `design_discovery`.
- The round gate's board tier (`BOARD_READS` in `firmware/tools/round_gate.py` covers `hardware/`) runs on any change under `hardware/`. A KiCad file in the working tree that git does not track fails the round. So every scratch copy lives outside the worktree (outside the repository).
- `separation-basis.yaml` and `controller-part.yaml` sit in the machine folder `hardware/sunbeam-em7000/` and apply to every design under it. The design-folder records (`pin-allocation.yaml`, `parts-specification.yaml`, `catalogue-extract.yaml`, `derating-policy.yaml`, `pin-limits.yaml`, `board-rules.yaml`, `manufacturer-limits.yaml`, `schematic-spec.yaml`, `controller-input-map.yaml`) are found by the nearest-folder rule, so v2 carries its own copies.
- `task hw:history -- --board main-board.kicad_pcb` (run from the v2 folder) needs, in this order of commits:
  1. `layout-plan.md` floorplan and plan, `circuit-proof.md`, its netlist and inputs, and `bring-up-provision.md`, all before the first commit whose board holds a footprint;
  2. at least two candidates in commits of their own;
  3. the placement section committed before the first copper;
  4. critical copper all locked before the router's commit.
- `task hw:review-history -- --folder hardware/sunbeam-em7000/main-board-v2` judges `layout-review.md` from its own history. A new file starts at round 1. The closing round must be full.
- Every layout review round needs the full pre-order check (method, Layout review step 8). That is about 2.5 h each time, so rounds are the expensive unit.
- Paths that name `main-board/` outside the folder and must follow the move in the same change:
  - tests: `hardware/tools/tests/test_main_board_schematic_records.py`, `test_derating_policy_record.py`, `test_circuit_proof_sheet_generator.py`, `test_separation_basis_record.py` (its same-part pad-pair table of the committed layout);
  - docs: `docs/sunbeam-em7000/controller-board-cost-estimate.md`, `controller-board-design-constraints.md`, `controller-board-division.md`;
  - graph prose in DEC-MAIN-BOARD-RESIDUAL-RISKS-ACCEPTED-BY-OWNER and SOL-PRE-ORDER-CHECK-PLATED-HOLE-OF-A-LOW-VOLTAGE-PART-IS-MEASURED-ROUND-THE-SLOTS.

  Evidence nodes cite v1 at a commit and stay as they are. Firmware reads no main-board path. `controller-board-design-constraints.md` is in the emulation reads, so the closing gate runs emulation.

## Phases

Tier names follow CLAUDE.md. "Skill would pick" is what `/stage0-build`, `/staircase-wf` or the engine's `recommended_tier` would name. "Chosen" is the owner's rule (Sonnet 5.5 medium by default, Opus only for class-of-miss reasoning, Haiku for deterministic runs). Konnect work runs only in the main session.

### Phase 0: freeze and seed (about 2 h)

**Purpose.** Bank the verified U201/U203 change, freeze v1, and open v2 with a clean history.

**Steps.**
1. Commit the uncommitted U201/U203 change (sheet 102, its proofs, records and the two docs) in `main-board/` as it stands. The change is verified, and committing it keeps its trail.
2. Tag `main-board-v1-final` (local only, on commit e8615c82; not published).
3. Create `main-board-v2/` by copying the schematic, sheets, libraries, library tables, rules files and every record. The v2 board file is v1's board with every footprint, track, via and copper zone removed: outline, stack-up, board settings, net classes and text variables only, so the board holds no footprint and no copper yet. Add this PLAN.md.
4. Remove `main-board/` from the tree.
5. Update the test, doc and graph-prose paths listed above.
6. Commit.

**Inputs.** The worktree as it stands.

**Output.** One commit holding the U201 change on v1, the tag, and one seed commit.

**Tier.** Skill would pick mid-tier. Chosen: Haiku for the copy/strip script and path edits, with a Sonnet medium cold read of the diff.

**Forward tests (minutes).**
- `task hw:reads` lists `main-board-v2/` and nothing under `main-board/`.
- `kicad-cli sch erc` on the v2 schematic is clean, apart from the known U203/R208/C206 board-absent parity, which only the board check sees.
- `pytest` on the four path-updated tests passes.
- The v2 board file holds zero footprints and zero copper items (a pcbnew count).

**Rework backwards.** None possible. This is the base.

**Common-cause check on failure.** A test failing after the move is a missed path, not a design change: `git grep` the old path before touching anything else.

### Phase 1: scratch go/no-go on the re-placed hardest area (about 6 to 10 h, mostly agent time)

**Purpose.** Prove, before any committed design work, that the re-placed low-voltage half routes cleanly on six layers. Everything here runs outside the repository, on copies.

**Inputs.**
- `placed_A06` with pin map A;
- the pilot's three placement fixes;
- U203, R208 and C206 placed beside U201;
- AMC_RESET on PC8/PC9;
- the pilot router with its two bugs fixed: same-net re-crossing, and ground-stub vias too close together (hole_to_hole).

**Output.** A pass/fail verdict with figures, a scratch placement (positions table), and the escape and crop-DRC results. The verdict and figures are copied into the phase 4 candidate's "Why" text. The scratch files themselves are never committed.

**Tier.** Skill would pick mid-tier (implement). Chosen: Sonnet 5.5 high. High effort is justified because it is hard geometry with a custom router, and the pilot needed it. Not Opus: this is engineering iteration, not class-of-miss reasoning.

**Forward tests and criteria.** See "Early go/no-go" below.

**Rework backwards.** None yet. A fail here sends work to the fallbacks below, never into the repo.

**Common-cause check on failure.** Route each failing net alone on an empty copy. If it still fails, the cause is placement, so fix placement. If it routes alone, the cause is ordering, so improve rip-up or hand-route it. Group the failures by cause (lane blocked, facing rows, via sites) before fixing any single one.

### Phase 2: schematic and pin map (about 6 to 10 h, plus a review that runs alongside phase 3)

**Purpose.** Commit pin map A and the U201/U203 schematic to v2, with every record and proof that depends on pins.

**Steps.**
1. Main session (Konnect): move the 25 labels and the 10 no-connect marks in `31-controller`, and rename the three SPI nets in `main-board`, E1 and E3, as `PHASE2-CHANGE-LIST.md` orders them.
2. Sub-agent: rebuild `schematic-spec.yaml` and `sheets/*.yaml` with `spec-tools/build_spec.py`.
3. Sub-agent: update `controller-pin-table.md`, `pin-allocation.yaml` and `pin-limits.yaml`.
4. Sub-agent: write the proof rows (reset/boot state of each moved pin, the SPI3 bootloader-slave case, PB12 5 V exposure), then re-export the netlist (`circuit-proof/main-board.cir`).
5. Run schematic review round 8 as one full round over the pin map and U201/U203 delta, and the whole checklist, because it must close the schematic review. Use fresh reviewers in hand-built group sessions, since the review kit refuses this board.

**Inputs.** The phase 1 pass, the AF table check (a scratch script kept outside the repository, run against DS12110 Table 9), and AN2606.

**Output.** The committed schematic and records. Round 8 is recorded in `schematic-review.md`, which is copied into v2 with rounds 1 to 7 intact.

**Tier.** Skill would pick mid-tier for the records and reasoning-tier for the proof readiness. Chosen: Sonnet medium for records and proofs, Sonnet medium reviewers, Haiku for ERC/netlist/test runs. No Opus.

**Forward tests (minutes).**
- The AF legality script.
- `kicad-cli sch erc`.
- `kicad-cli sch export netlist` compared with `cmp` (method, Proving step 4).
- `test_main_board_schematic_records.py`.
- A pin-limits pass through a scratch `board_check.py` run: the check runs whole, so do it in a scratch clone and read only the `pin_limits`/`pin_allocation` lines. Run it once, detached.

**Rework backwards.**

| Finding | Re-enter | Narrowest re-entry |
|---|---|---|
| An AF or boot-state fault on a moved pin | Phase 2 | Move that one pin to a freed plain GPIO on the same package side. Re-run the phase 1 escape study for that side only (minutes). |
| A review finding that adds or changes a part | Phase 2 | Fix it before the floorplan is committed. After phase 3 it is a plan append (allowed). |
| A finding that changes a mains part | Stop | Reopens the separation basis. Tell the owner. |

**Common-cause check on failure.** Does the same fault apply to every pin moved for the same reason (all the SPI3 pins, all the PD selects)? Sweep the class before fixing one.

### Phase 3: floorplan, plan and pre-placement records (about 4 to 6 h)

**Purpose.** Commit what the method requires before the first footprint.

**Steps.**
1. Write the `layout-plan.md` floorplan.
   - The mains region rectangles are copied byte for byte from v1.
   - The low-voltage, analogue and digital regions are redrawn around the phase 1 placement, with the MCU near (100, 75) at 180, the converter cell south, the analogue island east, and the drivers between the MCU's west side and the barrier.
   - The panel drivers sit by J791/J821.
   - The connector table keeps every fixed connector and J862, and moves J401/J402 to their pins' side.
2. Fill the plan table, one row per catalogue item. Mains rows are carried, low-voltage rows rewritten.
3. Write the board's own items. Carry v1's BOARD items, and add these as baseline items, so the review judges them:
   - an MCU escape channel of at least 2.5 mm from the pad ends, each capacitor in its own supply pin's lane;
   - facing pad rows of U620/U621 and U630/U631 at least 4.5 mm apart, or staggered;
   - no part in the lanes of U601's low-voltage pins;
   - no via in an SMD pad other than an exposed thermal pad;
   - every assembled part on F.Cu.
4. Bring `circuit-proof.md` and `bring-up-provision.md` up to date and commit them in the same window.
5. Set the board minimums in the project file and the two rows of `design-rules.md` (method, Placement step 1).

**Inputs.** Phases 1 and 2.

**Output.** One commit, before any footprint.

**Tier.** Skill would pick mid-tier. Chosen: Sonnet medium for drafting, plus a Haiku run of the method's Planning step 3 cross-checks against the netlist.

**Forward tests (minutes).**
- The Planning step 3 cross-checks (every netlist part in exactly one region list, the connector table complete, one plan row per catalogue item).
- `task hw:history` before placement: it reports `before first track` and must not fail `first placement` on a board with no footprint.

**Rework backwards.**

| Finding | Re-enter | Narrowest re-entry |
|---|---|---|
| A floorplan error found after the first footprint commit | Phase 3 on a fresh branch from the phase 3 commit | The method (Planning step 3) allows no in-place fix. This is why phase 1 settles placement on scratch first. |

**Common-cause check on failure.** Is the same region boundary wrong for several parts? Then the region is wrong, not the parts.

### Phase 4: placement in v2 (about 8 to 12 h, main session)

**Purpose.** At least two committed candidates, measured and judged, then one chosen (here three were committed and candidate 3 chosen).

**Steps.**
1. Main session places the fixed parts first, at their v1 coordinates: the connectors, the reed J862, the mounting holes and every mains-region and barrier-column part. A scratch script compares each with the tag and must report zero difference.
2. Place the low-voltage half from the phase 1 positions table with Konnect's move and rotate tools. That is candidate 1: the A2 placement of Phase 1c, committed as `a3b135f0` with every footprint and no copper.
3. Candidate 2 is commit `b69ea664`: candidate 1 with the crystals Y401 and Y402 turned 180 degrees, TP406 moved to (117.8, 77.75) so it is off C414's pad and R545 moved to (88.8, 37.4) turned 180 degrees so it is off J861's courtyard. An annealed variant of candidate 1, found by a metric search over small parts, was evaluated in scratch only and is not a committed candidate; the placement section records it as evidence.
3a. Candidate 3 is commit `eebfd2bd`: candidate 2 with ten parts moved (C502, C408 to C411, R504, C414, R672, TP406 on B.Cu and R545) so U401 pins 21 (+3V3A) and 20 (VREF+) have an exit, as a scratch hand-route proof showed (no vias, 12.5 and 10.0 mm). It is the chosen candidate and the placement frozen for routing. Routing tasks it carries into the critical routing, in order: the power-net trunks (+3V3, +3V3A, +5V) first; the HSE and LSE crystal group, not yet routed on candidate 3, with vias as needed and the HSE nets held to 25 mm total per net and the LSE nets to 15 mm; C501, still about 30.9 mm from U401 pin 15; the VREF+ remote pads R302.2 and TP402; and two ground vias for each of C408 to C411.
4. Render with `task hw:placement` from each commit (method, Placement step 4), give the verdicts, choose, and commit the placement section.
5. Run `task hw:history`.

**Inputs.** Phase 3 and the phase 1 table.

**Output.** The chosen placement, committed before any copper.

**Tier.** Konnect: main session. Skill would pick mid-tier. Chosen: main session for Konnect moves. Sonnet medium sub-agents for the verdict tables from the rendered views. Haiku for the render and measure runs.

**Forward tests.**
- `task hw:placement`: zero `OUTSIDE` lines; length and crossings at or below phase 1's figures.
- The pilot escape study on the committed board: 0 pins fail at 2.5 mm.
- A crop DRC (pilot pattern: cropped copy, project rules file, about 10 s): zero courtyard overlaps; separation clean for U203, R208, C206, C609, C610 and C612 against mains pads.
- The fixed-part position diff against the tag is empty.
- `task hw:history` passes.

**Rework backwards.**

| Finding | Re-enter | Narrowest re-entry |
|---|---|---|
| A part outside its region | Phase 4 | Make another candidate. Never widen a region after the first footprint. |
| A placement verdict fails on a planned item | Phase 4 | New candidate. The plan row is amended only before the first footprint. |
| An escape regression against phase 1 | Phase 4 | Compare the two positions tables. The difference is the cause. |

**Common-cause check on failure.** Diff the committed positions against the phase 1 table before moving anything. A transfer error (rotation convention, side) usually affects a whole class of parts.

### Phase 5: rules before routing (about 2 h)

**Purpose.** Rules and classes for the new geometry.

**Steps.**
1. Update `design-rules.md` and `main-board.kicad_dru`:
   - the region rule areas and `Low voltage/Analog sensing/Digital region parts` bounds follow the new floorplan;
   - the mains rows are unchanged;
   - the via sizes are 0.3/0.6 by default, plus the exposed-pad parameter;
   - the crystal keep-clear rules follow Y401/Y402.
2. Use the critical classes as v1, with SPI3 nets in the class v1 put SPI2 in.
3. Run `task hw:rules-confirm`.
4. Close and reopen the board (method, Rules steps 3 and 4).

**Tier.** Skill would pick mid-tier. Chosen: Sonnet medium, plus Haiku for the confirm run.

**Forward test.** `task hw:rules-confirm` reports `RESULT | CONFIRMED`, with every class non-empty.

**Rework backwards.**

| Finding | Re-enter | Narrowest re-entry |
|---|---|---|
| A class empty or mis-assigned | Phase 5 | The class is the cause. Re-check the whole class list. |
| A mains rule that differs from v1 | Stop | Mains figures are never changed. Restore the row from the tag. |

**Common-cause check on failure.** Diff the mains rule rows and mains region bounds against the tag before anything else.

### Phase 6: mains copper restored, then critical nets by hand (about 12 to 20 h, main session; the longest phase)

**Purpose.** Carry the mains copper over unchanged, with a proof, then hand-route every critical low-voltage net, hardest area first.

**Steps.**
1. Record v1's Mains-class copper with `task hw:copper-record`, run in a detached worktree of the commit e8615c82 (marked by the local, unpublished tag `main-board-v1-final`), with the record written outside every design folder.
2. In v2, copy every mains-class track, via and zone from the tag with KiCad scripting on the closed board, keeping each item's uuid and lock. Commit. This is the first-copper commit.
3. Run `task hw:copper-compare` against the v1 record. It matches by uuid first, so it must report no missing, changed or added item. That makes "mains copper unchanged" a tool result, not a claim.
4. In Konnect, in this order, each block followed by a crop DRC:
   - the MCU decoupling ring and crystals;
   - the SPI3, selects, HX711 and AMC lines (the phase 1 hardest area, using phase 1's geometry as the guide);
   - the sense nets;
   - power and ground drops;
   - USB;
   - the barrier-adjacent low-voltage copper (U601 low-voltage side, U602, U701, U711, U301 DC side, K201/K731/K741 coil drives, U201/U203).
5. Apply the exposed-pad via sizes once the quote is in.
6. Lock with `task hw:copper-lock`.
7. Run the critical-routing checklist (method, Routing step 4).
8. Run `task hw:history`.

**Tier.** Konnect: main session. Skill would pick mid-tier. Chosen: main session for drawing, Sonnet medium for the critical-routing checklist judgement, Haiku for the lock, record, compare and crop-DRC runs.

**Forward tests.**
- `hw:copper-compare` on the mains copper is clean.
- A crop DRC after each block shows zero new clearance, `track_segment_length`, `track_angle` and `hole_to_hole` lines.
- A pcbnew connectivity count of the block's nets reads zero unconnected (seconds; never a full `kicad-cli pcb drc`).

**Rework backwards.**

| Finding | Re-enter | Narrowest re-entry |
|---|---|---|
| A critical net cannot be routed without breaking a rule | Phase 4 | The placement section is frozen after first copper, so a part move is now a layout change the review judges. Move the fewest parts, re-run the crop DRC and the escape study for that side, and record it for review round 1. |
| A mains compare difference | Phase 6, before anything else | Restore from the tag. Never edit mains copper by hand. |

**Common-cause check on failure.** Before fixing, list every crop-DRC line by rule and by part. Several lines at one part means placement. Lines spread across one rule means a rule or class setting.

### Phase 7: the rest, then cleanup (about 6 to 10 h)

**Purpose.** Route the non-critical nets and bring workmanship to the catalogue.

**Steps.**
1. Run `task hw:copper-record`.
2. Export with rule areas removed in memory (method, Routing step 6), then route with `task hw:freerouting` and import.
3. Run `task hw:copper-compare`.
4. Clean up `track_angle` and short-segment lines, and silk and designators, by scripted or Konnect edits as the method allows.
5. Assign pad pin types (method workaround).

**Tier.** Skill would pick mid-tier. Chosen: Haiku for export, route, import and compare. Sonnet medium for the cleanup decisions. Main session for Konnect edits.

**Forward tests.**
- `hw:copper-compare` clean.
- The pcbnew unconnected count is zero.
- A whole-board crop DRC split into four quadrants (each a short run) gives counts by rule, which must be at or below the phase 1 per-area figures.
- `task hw:history -- --board main-board.kicad_pcb --routed` passes.

**Rework backwards.**

| Finding | Re-enter | Narrowest re-entry |
|---|---|---|
| Unrouted nets | Phase 6 | Read the `.dsn` keepouts first (method). If a critical lock blocks a channel, re-enter phase 6 for that block only. |
| Router detours longer than about 2x straight-line | Phase 7 | Hand-route those nets. Never re-place, unless the placement view shows the cause. |

**Common-cause check on failure.** Group the unrouted or detoured nets by the area they cross. A shared choke point is a placement or lock problem, not a router setting.

### Phase 8: pre-order check and layout review (about 10 to 16 h, three full check runs of about 2.5 h each)

**Purpose.** Close the layout review on a full round, with the pre-order check passing.

**Steps.**
1. Round 1, full. Run `task hw:views`, then the full `task hw:verify` in a scratch clone of the committed branch: detached, nice, with a Monitor on exit, using the pattern of a scratch script kept outside the repository. Then fresh reviewers judge every checklist item from the views.
2. Fix by class sweep, not by instance (SOL-BOARD-REVIEW-LOOP-PROPORTIONATE).
3. Round 2, narrow, over the changed regions. It needs another full check run.
4. Round 3, full, the closing round, on the final design files.
5. Write `severity-policy.yaml` and `workmanship-acceptance.yaml` with counts from the last run on unchanged design files. YAML records are not design files for `hw:review-history`, so writing them does not reopen the round.
6. Run `task hw:review-history`.

**Tier.** Skill would pick mid-tier reviewers, and reasoning-tier for "class-of-miss" readiness. Chosen: Sonnet medium reviewers fanned out in groups, Haiku for the check runs and renders, Sonnet medium for fixes. Use Opus only if round 1 shows a finding class that recurs across areas and needs a class-of-miss diagnosis.

**Forward tests.** Before each 2.5 h run, the crop DRC and connectivity count must be clean. Never spend a full run to find what a crop finds.

**Rework backwards.**

| Finding | Re-enter | Narrowest re-entry |
|---|---|---|
| A safety finding (separation, fusing, insulation) | Phase 6 or 4, wherever its cause is | A safety finding never closes by reason without the owner's own `accepted_by`. |
| A workmanship finding caused by part positions | Phase 4 logic (move parts) | Close by a placement change naming the parts moved and the before/after measures (method, Layout review step 7). |
| A planned item not met in round 1 | Phase 3 plan row, by its trace | Amend the method item only if the row, followed as written, would not have met the item (Layout review step 6). |
| A finding in a full round after a narrow round | The next round | Every new round needs a full check, so batch all fixes before starting it. |

**Common-cause check on failure.** For each finding, ask "where else does this class occur?" and sweep before the next round. One unswept class costs a whole 2.5 h round.

### Phase 9: close-out (about 8 to 12 h, gate about 3 h)

**Purpose.** Bring records, the graph and the gate in line with v2, then raise one PR.

**Steps.**
1. Records:
   - `pre-order-check-result.md`;
   - `traceability.md`;
   - `bring-up-provision.md` test-point notes (TEST-1 reach);
   - `fabrication-notes.md` (unchanged at six layers apart from the exposed-pad via note);
   - `signal-study.md` redone from the v2 board (its scripts were never committed, so rebuild them in scratch, or commit them under `main-board-v2/` this time);
   - `coil-pin-paths.md` re-measured on v2 (relays and mains copper unchanged, so the figures should repeat);
   - `separation-basis.yaml` exceptions checked for staleness (remove any the v2 check no longer needs, as C606 was; no re-signing for a removal);
   - `derating-policy.yaml` unchanged.
2. Graph amendments (list below), by a later authoring agent.
3. Submit the held runs, then ONE `task check:round`. Its board tier runs `hw:verify` and `hw:test:round` (about 2.5 to 3 h): detached with a log and Monitor. Emulation runs because the constraints doc changed.
4. WF-REVIEW each run.
5. Blind review of the PR.
6. Ask the owner before pushing, then push and raise the PR (merge commit only).
7. JLCPCB re-export from the final commit (Haiku), with a BOM and CPL diff against the quote the owner downloaded (the second quote's BOM and CPL files).

**Tier.** Skill would pick mid-tier. Chosen: Sonnet medium for records and graph authoring, Haiku for the gate, export and diff, and a fresh Sonnet medium blind reviewer.

**Forward tests.**
- `hw:test:round`'s path-updated tests, run alone, before the gate.
- `staircase validate` and `lint` after authoring.

**Rework backwards.**

| Finding | Re-enter | Narrowest re-entry |
|---|---|---|
| The gate's board tier fails on something round 3's run did not show | — | It cannot, unless a design file changed after round 3. `hw:review-history`'s `closing round` check catches that first. |

## Early go/no-go (phase 1)

The scope is the hardest area: the MCU ring, the measurement cell (U620, U621, U630, U631), the AMC lines to U601's low-voltage side, the I2C pairs, the reed line, and the U201/U203 interlock buffer. That is about 92 nets plus about 83 ground drops, on six layers, with In1 never routed, using the project's own rules (0.2 mm tracks including 3V3, 0.45 for 5 V, 0.2 mm clearance, 0.3/0.6 vias, 45° corners, strict 1 mm runs).

**Pass criteria (all must hold).**
1. MCU escape: 0 of 62 signal pins fail at a 2.5 mm box (pilot as placed: 19 failing).
2. Every scope connection routed, with no net partial, and every ground drop placed.
3. A crop DRC with the project rules file, against the unrouted crop, shows 0 new lines of each of these: clearance, `track_segment_length`, `track_angle`, `hole_to_hole`, courtyard overlap. The `via_dangling` lines that come from the removed zones are the known artifact and are excluded.
4. Inner signal layers carry at most 10% of the scope's routed length, and In2 carries no low-voltage track inside the mains region.
5. No via in an SMD pad except exposed pads.
6. The SPI3 trunk is at most 69 mm along copper from the MCU pin to its farthest load, and every select and HX711 line is at most 60 mm. The 69 mm is the ringing rule of `signal-study.md` (a line is long when its delay exceeds a sixth of the edge time: 69 mm at the fastest, 2.5 ns, GPIO edges), so it holds whatever the firmware does. It is the binding limit, not timing: at 6.05 ps/mm and a 4 MHz clock the read-back timing would allow about 2700 mm. The 60 mm planning target sits about 13% under it so that hand-routing detours still land inside it, and is 1.3 times the pilot's best 45 mm; it is a plan choice, kept for the selects and HX711 lines and as the placement and hand-routing target for the trunk. The firmware's 5 ns edge limit (`DEL-HW-MAIN-BOARD-DESIGNED.C27`) would stretch the ringing figure to about 137 mm, and the plan does not rely on it because that criterion is re-derived in phase 9. The pilot's completed ones were 28 to 45 mm, against 118 to 196 mm as built.
7. U203, R208, C206 and the moved C609/C610/C612 sit at least the signed 10 mm creepage and 3 mm clearance from mains copper, by the crop's `Mains separation` rule.

**On a fail, in order.**
1. Run the common-cause split (alone versus in combination). Fix the placement defects the alone-runs show (lanes, facing rows, via sites) and re-run.
2. Swap plain GPIOs within the facing side (selects, HX711 lines, the AMC_DRDY EXTI line), with no AF risk. Re-run the escape study.
3. Move the MCU along OPINION2's preferred band (y 60 to 75), or try the second-best grid point.
4. Allow In3 as a second routing layer for the measurement cell (still six layers, no cost).
5. If it still fails, stop. Report to the owner with the figures, and fall back to OPINION's targeted fixes on v1 (decoupling and crystal capacitors, HX711 and select re-pin, U791 channel permute, panel drivers by J791/J821). In that case delete v2 and restore v1 from the tag.

## Phase 1 outcome (2026-11-10): accepted as a conditional go

Evidence: a scratch handoff note and README kept outside the repository (never committed). Pin map A with AMC_RESET on PC8 (pin 65) and ANODE_GATE on PB5 (pin 91), MCU at (100, 75) rotated 180, U203, R208 and C206 beside U201, the router with in-search own-net crossing avoidance.

| Criterion | Result | Reading |
|---|---|---|
| 1 Escape | Pass: 0 of 62 fail at 2.5 mm (pilot 19) | The placement fixes work. |
| 2 Every connection routed | Fail as a count: 84.5% routed against the pilot's 49%; 60 of 387 connections failed | 33 of the 40 failing nets route fully alone on an empty board, and all 78 ground drops do. So 33 failures are ordering and congestion, which a hand route in phase 6 resolves. Seven nets fail even alone (8 connections): PT1_BIAS, PT2_BIAS, WT1_INA_P, USB_DM, +3V3, +3V3A, +5V. Four are enclosed pads (placement), two are lane-arrival geometry, one is search exhaustion. Four MCU GND pins (26, 49, 74, 99) need longer ground necks. |
| 3 Crop DRC lines | Pass for clearance, `track_segment_length`, `hole_to_hole` and courtyard overlap (0 routing-attributed lines); `track_angle` fail was 10 lines | The 10 were 5 events where a later connection of a net crossed its own earlier track inside the router's own-net exemption around terminals. `kicad-cli` confirmed that rejecting own-net crossings gives 0 new `track_angle` lines. It is a router artefact, not a placement defect. |
| 4 Inner layers | Pass: 5.5% of routed length | |
| 5 No via in an SMD pad | Pass: 0 outside the exposed-pad vias | |
| 6 SPI3 length | Fail against 60 mm: MISO 64.3 mm, MOSI 70.9 mm; PT1_CS 27, AMC_CS 31, WT1_CLK 32, WT2_CLK 12 mm pass; PT2_CS and the WT data lines were incomplete | The pin to U621 is about 20 mm straight, so the excess is router detour (the 1 mm run rule and 45 degree turns make octagon loops), not distance. Criterion 6 is restated above as what it is. |
| 7 Mains separation | Pass: 0 lines for U203, R208, C206, C609, C610 and C612 | |

**Decision.** Criteria 2, 3 and 6 are accepted as a conditional go. The failures are ordering, a router exemption and detour length, and each has a named cure below. Nothing in them says the placement is wrong. The scratch router is a floor, not a ceiling: phase 6 draws the critical nets by hand in Konnect, so the 33 ordering failures are never the committed board's problem.

**Adopted.** Pin map A with two changes: AMC_RESET on PC8 and ANODE_GATE on PB5. `PHASE2-CHANGE-LIST.md` holds the exact per-pin change list. The S-side swap of pins 81 to 88 (`pinswap.json`) gave no gain (73 to 80 failures against 58) and is not adopted, so the selects and HX711 lines keep the order pin map A gives them.

**Carried to later phases as explicit objectives.**
- Phase 4 placement: free the four enclosed pads (D401, C409, J635, TP622) with at least 0.8 mm of clear ring and check each with a route-alone run; leave the two lane-arrival nets (PT1_BIAS at U620 pins 1 and 2, +3V3 at U401 pin 75) a straight lane approach; lengthen the necks of MCU GND pins 26, 49, 74 and 99.
- Phase 6: route +3V3A, +5V, USB_DM, PT1_BIAS, PT2_BIAS and WT1_INA_P first by hand (the seven nets that fail alone), then the SPI3 trunk at 60 mm or less.
- 3V3 tracks are 0.2 mm, not 0.3 mm: `design-rules.md` (`Supply3V3` track width) and `main-board.kicad_dru` say 0.2, and a 0.3 mm track cannot leave a 0.5 mm pitch pad at 0.2 mm clearance.

## Escalation ladder

When a test fails, take the cheapest rung that can change the verdict. A rung is left only when it has been tried, or when its "can fix" column says it cannot touch the failing cause. A loop at a rung is time-boxed to 60 minutes of wall clock or 3 laps, whichever comes first, and ends sooner when the next lap cannot change the verdict (the last lap moved no count, or the failing set is the same nets as the lap before). Then go up one rung. Every rung ends with the common-cause split of phase 1: route each failing net alone on an empty copy first, to tell ordering from placement.

| Rung | Lever | Cost | Can fix | Cannot fix |
|---|---|---|---|---|
| 1 | Net order (route the failing nets first, `--first`, re-run) | minutes | Failures that route alone: ordering and congestion | A net that fails alone |
| 2 | Local nudge (move one part by under 1 mm, widen a ring, lengthen a neck) | minutes | An enclosed pad, a blocked lane, a neck too short | A channel too narrow for its nets |
| 3 | Pin swap (plain GPIOs on the same side: selects, HX711 lines, AMC_DRDY) | an hour; it touches the schematic and every pin record | Crossings and lane order among the swapped nets | Supply, USB, probe and ADC nets, which do not move |
| 4 | Part move (one cell or one part group: a converter, a header, a driver) | hours | A facing-row or via-site conflict inside one cell | A fault of the MCU position |
| 5 | Region move (MCU along y 60 to 75, or the converter cell turned) | half a day; reruns placement | A whole side's wrong-side pins or crossings | A fault with the floorplan |
| 6 | Floorplan (a region boundary redrawn) | a day; a fresh branch from the phase 3 commit | A region too small for its parts | Nothing |

Rungs 3 to 6 each need a reason a lower rung could not give. A move up is written into the handoff with the failing nets and the evidence. Past rung 6, or when the common-cause split shows a fault no rung touches, stop and report, as the fallbacks above say.

## Long agents: handoff and delegation

- Every long agent writes a `HANDOFF.md` before its context passes about 400k tokens, and again when its task changes phase. It holds the state (what is done, the best result and where its files are), the commands that reproduce it, the decisions and constraints in force, the open failures with their causes, and the next step. The next agent starts from it and re-reads nothing else cold.
- Deterministic runs (the router, crop DRC and connectivity sweeps, alone-runs, schematic export and compare) go to Haiku sub-agents, which run them, return the counts and file paths, and judge nothing. The long agent keeps the geometry and the decisions and stays small.
- At most four heavy workers run at once, under `nice`.

## What carries over and what is re-proved

| Item | Carries over unchanged | Re-proved because position or net topology changes | Minimum delta test |
|---|---|---|---|
| Mains region parts, barrier column (U601, U602, U701, U711, U301, K201, K731, K741), tabs J101 to J110, reed J862 | Positions, footprints, mains copper | — | Position diff against the tag (script). `hw:copper-compare` of Mains-class copper against v1's record. |
| `separation-basis.yaml` (accepted by the owner on 2026-11-18; the acceptances of 2026-11-06 and 2026-11-07 are superseded on every entry by it), MAINS-2 deviation | Yes, while the mains copper compare is clean | Exception staleness only | The v2 full check's `spacing_exception` lines. Remove stale ones without re-signing. |
| Schematic findings 7.17, 7.35, 7.45 (part ratings of mains parts, carried to bring-up) | Yes. They are about part ratings, not positions, and nothing they name moves. | — | None. Restated in the PR summary. |
| `derating-policy.yaml`, `parts-specification.yaml` (apart from U203, R208, C206), `catalogue-extract.yaml` | Yes | Catalogue refresh before 2026-11-13 (stock dates) | `board_check` record lines in the round 1 run. |
| `circuit-proof.md` value rows | Yes, apart from the pin rows | Pin rows: reset/boot state of moved pins, SPI3 bootloader-slave case, PB12 5 V exposure | Rerun of the affected scripts. Netlist `cmp`. |
| `circuit-verdicts.md` | Yes, apart from moved pins | Moved-pin verdicts | Phase 2 review round 8. |
| `error-budget.md` | Yes, because no analogue pin moves | — | None. If a phase 1 swap touches an ADC pin, rerun that channel's row. |
| `leak-detection.md` | Yes (datasheet arithmetic) | — | None. |
| `signal-study.md` | No | Whole study (routed lengths change) | Rerun the SPI3, MISO timing and crystal start-up sections on v2. Re-derive C27's limits. |
| `coil-pin-paths.md` | Probably | Re-measure on v2 | One scripted measurement run. |
| `layout-plan.md` | Mains rows of the floorplan and plan | All low-voltage regions, rows, placement and critical routing | `hw:history`. Planning step 3 cross-checks. |
| `design-rules.md`, `main-board.kicad_dru` | Mains rows and figures | Region bounds, via sizes, crystal keep-clears | `hw:rules-confirm`. Diff of mains rows against the tag. |
| `bring-up-provision.md`, `bring-up/A.yaml` | Rail, link and test-point lists | Test point reach (TEST-1), bays on B.Cu | Round 1 verdict on TEST-1 and TEST-5. |
| `layout-review.md` | No. A new file in v2, rounds from 1. | All | `hw:review-history`. |
| `pre-order-check-result.md`, `traceability.md` | No | Rewritten from the final run | The final run's lines. |
| `schematic-review.md` | Rounds 1 to 7 as recorded | Round 8 (full, closing) | Round 8. |
| `fabrication-notes.md` | Laminate, coat, six layers, ENIG | Exposed-pad via note after the quote | Inspection. |
| `open-items.md` | Owner items | Lines that name v1 positions or "all R and C are Basic" (stale) | Inspection. |

## HANDOVER steps 1 to 9, and what happens to each

| Step | Fate |
|---|---|
| 1 Amend the U201 node to "owner's ordering call" | Superseded. U201 is now two series SN74AHCT1G14DCKR gates (U201 and U203), with R208 and C206. The node is rewritten to state that change and its proof, and closes as built, not awaiting a decision. The owner's sourcing note no longer applies, since the old part's stock was the issue. |
| 2 Implement responses for the seven-clamp run and the stock-swap leaf | Still stands, rewritten against v2. The part changes (BAT54SW, stocked beads, 59 k feed, 100 nF merges) carry through the schematic. The v1 coordinates in the seven-clamp leaf do not. Amend that leaf to position-free criteria (part, F.Cu, no via in an SMD pad), cancel its run, re-review, start a new run at the end. The stock-swap leaf has no coordinates, so it gets its new run as planned. |
| 3 `severity-policy.yaml` and `workmanship-acceptance.yaml` | Still stands, written in phase 8 from the final v2 run, placed in `main-board-v2/`, signed on the standing instruction. v1's expected counts (pour_gap 7, decoupling_via 4 and the rest) are void. |
| 4 One full pre-order check | Absorbed into phase 8: one run per review round, the last giving the counts. |
| 5 Scoped layout review | Dropped for v1. Replaced by v2's rounds 1 to 3. |
| 6 Submit held responses, one `check:round` | Still stands, in phase 9. |
| 7 Ask, push, PR | Still stands, in phase 9. Merge commit only. |
| 8 Follow-ups | Still stand, except two that are absorbed: R630/R631 land-pattern check (do it in phase 3, since the footprint is placed fresh) and the layout-plan MFG-10 note (rewritten in v2's plan). Finding 7.34 and the other node follow-ups are authored in phase 9. |
| 9 JLCPCB re-export | Still stands, from the final commit. |

## Parked WF-BUILD runs and graph amendments (for a later engine-only authoring agent)

**Held runs.**

| Run | Leaf | Action |
|---|---|---|
| crun-43e8d5d4564070b8 | net-pair C1 matches the signed record | Mains only. Submit as held, after confirming the v2 check reports the same seven entries. |
| crun-aea8dd3b36f41f80, crun-264012c0e1edf27d, crun-4fd93cfb276b035f, crun-2d8a5b97d9bdab24, crun-6b7851e2ad1c7df9 | Pre-order check tooling leaves | Board-independent (synthetic fixtures). Submit as held. The policy file for crun-6b7851e2ad1c7df9 is written in phase 8 under `main-board-v2/`. |
| crun-91fa40ab42696920 | C606 exception removed | Mains, unchanged. Submit as held. |
| crun-aeeb44f140c71d75 | Seven clamps and back-side parts | Leaf amended to position-free form. Cancel, re-review the brief, new run, response written against v2. |
| (none yet) | Stock-swap leaf | New run at the end, as HANDOVER planned. |

**Graph amendments.** Read each node with `show` first, bump the version once per node on this branch, and use `--actor david`.
- **SOL-MAIN-BOARD-U201-INTERLOCK-BUFFER-HAS-NO-STOCKED-EQUIVALENT-AWAITS-OWNER-DECISION.** Retitle and rewrite: U201 and U203 are two series SN74AHCT1G14DCKR, with R208 100 k and C206 100 n. Replace the criterion with ones the built change meets (proof decks re-run, records updated, placed on the board).
- **SOL-HW-MAIN-BOARD-PROVEN-AND-LAID-OUT.** Add to "Settled for the build": the board is re-placed and re-routed in `hardware/sunbeam-em7000/main-board-v2/`; v1 is frozen at commit e8615c82 (local tag `main-board-v1-final`, not published) and removed; the mains copper is carried over unchanged, proved by the copper compare; six layers. Its brief confirmation goes stale, so re-review it.
- **DEL-HW-MAIN-BOARD-DESIGNED.C27 and SOL-FW-SPI2-PORT-RUNS-SLOW-EDGES-AND-A-LOW-CLOCK.** Change SPI2 to SPI3. Replace the 4 MHz and 5 ns limits with the v2 signal study's figures. If the study shows no limit is needed, supersede rather than amend.
- **SOL-MAIN-BOARD-BACK-SIDE-PARTS-AND-VIAS-IN-PADS-MOVED-BY-THE-PLACEMENT-METHOD.** Position-free criteria, as above.
- **SOL-MAIN-BOARD-FIVE-GROUND-VIAS-IN-SMD-PADS-AWAIT-OWNER-DECISION.** State that the owner's acceptance applied to v1 and that v2 has no via in an SMD pad other than exposed pads. Retitle away from "AWAIT".
- **DEC-MAIN-BOARD-RESIDUAL-RISKS-ACCEPTED-BY-OWNER.**
  - Items (z11), (z12), (z13), (z15) and (z16) name v1 counts and parts. Restate each from the final v2 run, or mark it void for v2.
  - Add one item recording the restart and pin map A.
  - (z14), plated-hole spacing at 1.5 mm, stands.
  - Update the folder path in its prose.
- **SOL-PRE-ORDER-CHECK-PLATED-HOLE-OF-A-LOW-VOLTAGE-PART-IS-MEASURED-ROUND-THE-SLOTS.** Update the folder path in its prose.
- **New DEL-MAINTENANCE child.** Pin map A adopted on the main board: SPI3, I2C4, TIM2_CH3 and the PD-port selects, with proofs, records and schematic review round 8. Trace it to the criterion the pin change restores routing quality against, REQ-BOARD-LAYOUT-PRACTICE-001.C1. Read it before linking.
- **Follow-ups HANDOVER step 8 already lists.** Finding 7.34, the BOM value-text grouping, the PinCoverageProof test, the "33 exceptions" title, evidence for the SMD-pad leaf, the "anticipated/could" wording for probes and load cells, the Basic-first rule, the stale open-items line, and the catalogue refresh. Each still stands.
- **SOL-HW-REVIEW-KIT-MAIN-BOARD-PLANS-WITHIN-THE-BUDGET.** Check whether its premise (the main board's folders) still holds at the new path.

## Time, cost and status checks

| Phase | Wall clock (rough) | Long-running parts worth a 30-minute check |
|---|---|---|
| 0 Freeze and seed | 2 h | — |
| 1 Go/no-go | 6 to 10 h | The router agent: check at 30 min, then every 30 min (transcript tail, last route counts). |
| 2 Schematic, pin map, review round 8 | 6 to 10 h, plus 3 to 5 h of review alongside phase 3 | Review group sessions. |
| 3 Floorplan and records | 4 to 6 h | — |
| 4 Placement | 8 to 12 h | — (main session) |
| 5 Rules | 2 h | — |
| 6 Mains restore and critical routing | 12 to 20 h | — (main session). Crop DRC runs are seconds. |
| 7 Rest and cleanup | 6 to 10 h | Freerouting run. |
| 8 Three review rounds | 10 to 16 h, of which about 7.5 h is check machine time | Each 2.5 h check (Monitor on exit, check at 30 min), each reviewer fan-out. |
| 9 Close-out and gate | 8 to 12 h, of which the gate is about 3 h | The gate (Monitor plus a 30-minute log tail). |
| Total | about 65 to 100 h over several sessions | |

## Risks

- **Amending without propagating.** The pin map touches about 11 sheets, 4 pin records, 2 proofs, the signal study and two graph nodes (C27 and the SPI2 firmware leaf). The folder move touches 4 tests, 3 docs and 2 nodes' prose. Guard: a `git grep` for every moved pin name and the old path, plus `staircase query` for SPI2/PB13/PB14/PB15, before phase 2 and phase 9 close.
- **Wrong axis.** Judging the restart by length and crossings, when the failures the pilot found were lane conflicts and facing pad rows. The go/no-go judges escape and completed routing, not straight-line scores.
- **Assumed, not required.** "Mains copper unchanged" stated in prose across records. Guard: `hw:copper-compare` against v1's record makes it a tool result. The same goes for "J862 and the connectors keep their positions": a position diff against the tag, not a claim.
- **History-check trap.** Squashing, rebasing, or committing a footprint before the floorplan voids `hw:history`, with no in-place fix. Guard: forward test in phase 3, and merge-commit only.
- **Single most likely failure.** Moving the scratch placement into the committed board by hand in Konnect changes positions or rotations slightly, so the committed candidate no longer routes the way the probe did. Expensive phase 6 work then meets the lane conflicts again. Guard: a scripted positions diff between the phase 1 table and each committed candidate, and the escape study re-run on the committed board, before any copper.

## Questions for the owner

1. **Exposed-pad vias.** When the live quote breakdown comes, does a 0.2 mm drill with a 0.5 mm pad show any surcharge at six layers, and what does via filling (POFV) cost? Only the about 18 exposed-pad vias depend on it, and they are applied late in phase 6.
2. **Panel cable pin order.** Is the pin order on J791 and J821 fixed by the panel cables you keep? The plan assumes yes and places the drivers to suit the cable.
3. **The v1 tag.** May the tag `main-board-v1-final` be pushed to origin with the PR, so the frozen v1 stays reachable after the folder is removed?

   *Answered (note of 2026-11-18, the question above kept as asked).* The first design never reached `main` and the board is named v1 in its place (owner's decision of 2026-11-17, `DEC-BOARD-VERSION-NAMING-V2-WORKING-NAME`). No push of the tag was authorised: it exists only in the local repository, on commit e8615c82, and `git ls-remote --tags origin` lists none. The frozen first design is read from that commit only.

## Deferred to close-out (lean pass, 2026-11-10)

- `circuit-proof.md` and `circuit-verdicts.md`: pin and SPI3 rows (change list section 5.3) and the new rows (a) to (g).
- Proof script re-runs and their logs: `E_spi_bus`, `C_front_ends`, `C_gen_decks`, `b_supply_protection` (PD7 to PB11, PC6 to PB10).
- Schematic review round 8 (`schematic-review.md`).
- E2 sheet text note naming `MAINS_PRES_S (PD7)`: becomes PB11, needs a text edit Konnect cannot make.
- Graph amendments (change list section 7): C27 and the SPI2 port solution to SPI3, `DEL-HW-BRING-UP.C21` re-point, the `DEL-MAINTENANCE` child for pin map A.
- Spice netlist export (`circuit-proof/main-board.cir`) from the finished schematic.
- `signal-study.md`: rename SPI2 to SPI3 with the phase 9 redo.

## Phase 1b outcome (2026-11-10): the Phase 1 placement re-run with the four carried board items as hard constraints

Evidence: a scratch handoff note kept outside the repository (never committed). The annealer carried (a) to (d) as distance and keep-out constraints, and an independent script (`check_abcd.py`, real courtyards, not the optimiser's inflated ones) measured them afterwards. Pin map A as adopted, MCU rotated 180 degrees, MCU position free (grid of (106..112, 70..80) tried; (108, 79) chosen), the north band (y 4 to 34) opened to the annealer and the router, the reed box and its two pad exits modelled as router obstacles. Sensing set = the 121 parts the committed `analog sensing region parts` rule lists, minus the isolated-converter cell (U601, Y601, C609 to C612, R609, R613 to R615, which are held to D4 only); the test points TP602 and TP609 stay in the set. Controller block = U401, C401 to C407, C412, C413, Y401, Y402. Bodies: the module's fab outline (29.6, 48.75)-(82.0, 75.95), K201's courtyard (19.8, 96.4)-(60.6, 107.5).

**Result in one line.** The four items cannot all hold inside the plan's floorplan rectangles. Two further rules collide with them and one is a plan inconsistency. The strict placement routes worse than Phase 1 and the relaxed one routes at parity with the Phase 1 placement re-run on the same router. Neither meets criterion 6.

**Infeasibilities and the nearest relaxation.**
1. Sensing parts 20 mm from the module and the relay (BOARD-11). The plan's analog-sensing rectangles are 2702 mm2; the part of them that is 20 mm or more from both bodies and outside the reed box is 1989 mm2, against 1302 mm2 of sensing courtyards before lanes, gaps and the U601 cell (65 % at best). With the north band opened, every other part of (a) to (d) holds and the annealer finds no overlap-free arrangement except by parking J630 (WT1 load-cell header) in the north band at (93.5, 27.3), about 70 mm from its amplifier. That is the strict placement (S). The nearest relaxation that gives an overlap-free south converter cell is 20 mm to 17.5 mm (2.5 mm) for the sensing parts: at 18.5 mm two seeds left one or two overlaps, at 17.5 mm one seed has none (R); 19 parts of R stand under 20 mm, the nearest TP609 and TP602 (17.50), J525 (17.51), FB301 (17.52), R301 (17.56), C646 (17.58) and U631 (18.63). v1 stood the cell parts 17.1 mm from the relay (C647) and 8 sensing refs under 20 mm, so 17.5 mm is v1's actual standard, not a new one. Cost of relaxing: the thermal margin of the precision parts, to be judged against A8 (a modelled assumption, not a measurement). The alternative cost of not relaxing: a floorplan change that adds the north band to `analog sensing`, the load-cell header 70 mm from its amplifier and a longer analog run, and a route about 3 points worse.
2. Crystal keep-clear (CLOCK-4) against J761. U401 x of 106 or more (the 15 mm rule) puts the east-side crystals at x 119 to 121; J761 (courtyard (128.2, 58.7)-(131.8, 85.1), not on the exempt list) is then 5.0 mm (Y401) and 6.2 mm (Y402) from them against 10 mm, and J862 is 9.2 to 10 mm. Both placements show the two `Crystal keep-clear` courtyard lines. Relaxations: add J761 to the exempt list (crystal to J761 10 mm to about 5 mm; J761 carries the heater and wall-board stage lines), or U401 x of 100 to 104 (the controller block from 15 mm to about 13 mm, which is v1's 12.9 mm). Rotating U401 to put its pins 1 to 25 south or north was not tried and would redo the pin-side assignment.
3. SENSE-5 (U302 is a heat source that sensing parts stand 20 mm from) against FLOOR-3 (U302 in the cell (76, 48.4)-(100, 64)). The cell borders the island and the north-east headers: 27 sensing parts (S) and 31 (R) stand under 20 mm from U302, the nearest 7.2 mm (J571, R) and 9.7 mm (J503, S). The plan's own rectangles put the island 0 to 14 mm from the cell, so one of the two rows is wrong. Not constrained in the trial; reported.
4. The reed box has two pad exits: J862 pin 1 is GND at (122, 91.5) and pin 2 is TANK_LEVEL at (122, 111.5). The routed tracks touching the box in R are TANK_LEVEL only (5 segments); no vias.

**Margins measured independently (R, the relaxed placement `pl_r4`; S, the strict `pl_n2e`).**

| Item | Requirement | S | R |
|---|---|---|---|
| (a) sensing parts to module and relay bodies | 20 mm | min 20.50 (J620, TP609), none under 20 | min 17.50, 19 parts under 20 (relaxed 2.5 mm) |
| (a) U401 block to module body | 15 mm | min 15.62 (C402), U401 17.28 | min 15.62 (C412), U401 17.28 |
| (a) K731, K741, U701, U711, U601 (fixed, unchanged) | the record's 15 mm / D4 | K731 0.76 mm, U701 13.67 mm, K741 35.91, U711 27.27 from the module; U601 6.94 mm from K201 | same |
| (b) reed box | empty but J862 | no part, no via, tracks only TANK_LEVEL at its exit; nearest part 0.2 mm outside | same |
| (c) U302 in the cell | courtyard inside (76, 48.4)-(100, 64) | (86.13, 56.0)-(94.92, 63.19), 1.65 mm from JP301, 8.31 mm from U401; C304 and C305 10.06 and 11.53 mm from the tab | (85.51, 55.51)-(94.3, 62.7), 1.15 mm from JP301, 9.06 mm from U401; C304 and C305 11.11 and 10.41 mm from the tab |
| (d) D401 | within 5 mm of J402 | pads 1 and 3 to J402 pins 1 and 2: 4.69 and 4.63 mm | 3.93 and 4.90 mm |
| (d) D402 | beside J402 pin 5 | 3.85 mm | 3.24 mm |

**v1 on the same four items** (commit e8615c82, local tag `main-board-v1-final`, not published; positions read from its board with the v2 footprints, so approximate): sensing parts 17.1 mm from the relay at the nearest cell part and 8 refs under 20 mm (TP602, TP609 at 4.3 and 1.8 mm are the U601 cell); U401 21.6 mm from the module but its block 12.9 mm (C406), so (a) was not met; (b) met, no part in the box; (c) not comparable, U302 at (80, 40) 5.2 mm from the module and 9.2 mm from U401, C304 and C305 3.5 and 4.9 mm from the tab (BOARD-2's 10 mm not met); (d) met, D401 pads 2.8 and 5.6 mm from J402, D402 2.8 mm. The constrained v2 is therefore a stricter test than v1 passed on (a) and (c), and R is at v1's own level on (a).

**Routing results** (same router and recipe throughout; main window x 66 to 133, y 4 to 128, interlock window routed after; one pass of the Phase 1 recipe with `--gndfirst`, `--inner 4.5`, net orders prio, rand 1 and rand 2; control = the Phase 1 placement `pl_final` re-routed once with this router, main window only).

| Criterion | Phase 1 reported | Control (Phase 1 placement, this router) | S strict | R relaxed |
|---|---|---|---|---|
| 1 Escape at 2.5 mm | 0 of 62 fail | not re-run | 0 of 62 | 0 of 62 |
| 2 Connections routed | 84.5 %, 60 of 387 failed | 80.7 % and 79.5 % (68 and 72 of 352 failed, main only) | 79.1 %, 81 of 388 failed (main 80 of 353, interlock 1) | 82.4 %, 68 of 386 failed (main 66 of 351, interlock 2) |
| 2 Alone-failing nets | 7 | not run | 5: BREW_SCL, PT2_BIAS, SPI2_MOSI, +5V, +3V3 | 7: PT2_BIAS, +5V, +3V3, FLOW_IN, PT2_RTDINP, PT2_FORCEP, PT1_FORCEP |
| 3 Crop DRC, routing-attributed | clearance, `track_segment_length`, `hole_to_hole`, courtyard 0; `track_angle` 10 | not run | clearance 0, `track_segment_length` 0, `hole_to_hole` 0, courtyard 0, `track_angle` 12 lines (6 events) | clearance 1 (+3V3 via 0.47 mm from FID3 against 0.6), `hole_to_hole` 1 (two +3V3 vias 0.31 mm), `track_angle` 8 lines (4 events, PT2_BIAS and +3V3, both nets that fail alone), courtyard 0 |
| 4 Inner-layer share | 5.5 % | 4.9 % and 5.1 % | 6.5 % | 10.6 % (over the 10 % limit) |
| 5 Via in SMD pad | 0 | 0 | 0 | 0 by the criteria script; the crop DRC shows 1 GND via touching test point TP623 (a `shorting_items` and a `hole_clearance` line) |
| 6 SPI3 trunk along copper (limit 69 mm, selects 60 mm) | MISO 64.3, MOSI 70.9 | MISO 64.9 and 71.9, MOSI 67.3 (rand 1) | MISO 74.2 (single run; 97.1 in another), MOSI 102.6 | MOSI 76.1 (MISO 75.9 in the previous run of R); selects PT1_CS 37.5, PT2_CS 40.8, AMC_CS 24.6, WT2_CLK 18.5, WT2_DATA 13.1; SCK, MISO, WT1 lines incomplete |
| 7 Mains separation (U203, R208, C206, C609, C610, C612) | 0 | not run | 0 | 0 |

The failing sets are noisy by about plus or minus 8 connections between orderings and between small placement nudges (R ran 66 to 85 over six runs), `--first` with the failing nets and the router's REPAIR pass each moved a count by 1 or less, so the ladder was stopped at rung 2 after one loop. Phase 1's 60 came from several rounds on the same machinery; the control shows this router at the same placement gives 68 to 72 in one pass, so the figures above and Phase 1's 60 are not on the same footing. Alone-failing causes are the Phase 1 classes: enclosed pads (TP622, TP623, R522, J635 in R; BREW_SCL, +5V, PT2_BIAS, MOSI in S) and lane arrival (U620 and U621 pin 3, U401 pin 75).

**Reading.** The constrained, relaxed v2 routes at parity with the unconstrained Phase 1 placement on the same router (66 to 74 failures against 68 to 72), so the four items cost the route almost nothing once the south converter cell may stand 17.5 mm, as in v1. The strict version costs about 14 connections, the load-cell header 70 mm from its amplifier and a MISO trunk near 100 mm. Criterion 6 fails in both and fails against the control as well, so it is not caused by the constraints; the SPI3 trunk is longer in R than in the control by about 4 to 11 mm because the converter cell moved south-east. This does not undermine the v2 case against v1, whose own (a) was not met, but it moves two floorplan rows.

**Recommended next step.** Rung 6 of the ladder, written as graph and plan changes before Phase 3 closes: (1) draw `analog sensing` to the part of its rectangles that is 17.5 mm or more from the module and relay and extend it into the north band (80, 2)-(124, 34) for the north-east header cells, or accept 20 mm and the J630 move; (2) decide the crystal rule against J761 (exempt it, or hold U401 at x 104 and the block at about 13 mm); (3) settle FLOOR-3 against SENSE-5. Then take (108, 79) or the nearest point the decision allows into Phase 4. The relaxed placement `pl_r4` is the scratch candidate; D401 stands 4.9 mm from J402 pin 2 in it, the 5 mm limit with 0.1 mm to spare.

## Phase 1c outcome (2026-11-10): the Phase 1b relaxed placement re-run with the controller moved west and the low-voltage connectors freed

Evidence: a scratch handoff note kept outside the repository (never committed); same annealer, router, window and recipe as Phase 1b, so the routing rows compare like for like. Owner decisions modelled: sensing distance from the module and relay 17.5 mm (the annealer asks 17.6 so the independent measurement lands at or above 17.5); U401 centred at (104, 79) turned 180 degrees; J791 and J821 free in the box x 104 to 129, y 2 to 34.5 for their pin 1, rotation free; every other low-voltage connector, harness header and link position (J401, J402, J501 to J503, J520 to J525, J570, J571, J620 to J635, J761, J861, JP302, JP401, JP402, JP761, JP791, JP821) free on the board part x 66.3 and up that the router window covers; the mains tab pads, mains-region and barrier-column parts, JP301 and the reed J862 fixed; reed box, U302 cell, D401 and D402 near J402 as Phase 1b; crystals held 10 mm from every part the rules file does not exempt, J761 and J862 included; Q821, Q822 and R821 within 8 mm of J821 (R821's anchor to U401 pin 91 removed). U520 is an SN74LVC1G17 Schmitt buffer between `FLOW_F` and `FLOW_IN` (the flow input), so it follows J520, not J791.

**Result in one line.** All the owner's constraints hold together in one overlap-free placement (`pl_a2s5`, variant A), the CLOCK-4 10 mm to J761 is met without an exemption, and the route is at parity with Phase 1b R (66, 67 and 73 connections failed of 351 on the main window over three net orders, against R's 66 to 85) with cleaner DRC lines. Criterion 6 (SPI3 trunk) still fails. Freeing the connectors helped feasibility, not the route count.

| Item | Requirement | A (reed fixed) |
|---|---|---|
| Sensing parts to module and relay | 17.5 mm | min 17.60 (J625, J627, TP609, TP602), none under 17.5, 15 parts under 20 |
| U401 to module body | about 13 mm (decision 2) | U401 13.28; its other block parts 15.51 or more (C407 nearest) |
| Crystals to J761 / J862 | 10 mm | Y401 10.50 / 10.00, Y402 14.22 / 10.04; no unexempt part nearer than 10; crop DRC courtyard lines 0 |
| Reed box | empty but J862 | no part, no via; nearest part 0.2 mm outside |
| U302 cell | courtyard inside (76, 48.4)-(100, 64) | (83.66, 55.51)-(92.45, 62.70): margins 7.66 left, 7.55 right, 7.11 top, 1.30 bottom; JP301 gap 1.15; C304 and C305 10.73 and 12.31 mm from the tab |
| D401, D402 to J402 | 5 mm, 4 mm | D401 4.90 and 4.90 (margin 0.10), D402 3.99 (margin 0.01); J402 at (77.33, 84.81) |
| Q821, Q822, R821 to J821 | close | courtyard gaps 6.29, 6.28, 3.78 mm (Phase 1b 27 to 40 mm) |
| Connector access | on the board, mating face clear | all courtyards on the board (least edge margin 0.8 mm), no courtyard overlap (crop DRC 0), harness entry from above in every case; courtyards 0.4 mm apart for J620/J625 and the link positions J622, J627, J628 beside J625, 0.9 mm for J524/J630 and J861/JP301, 1.4 mm or more elsewhere |

| Criterion | Phase 1b R | A |
|---|---|---|
| 1 Escape at 2.5 mm | 0 of 62 | 0 of 62 |
| 2 Connections routed | 82.4 %, 68 of 386 (main 66 of 351) | main 66 of 351 (prio), 67, 73; interlock 2 of 27; 82.0 % overall for the prio run |
| 2 Alone-failing nets | 7 | 6 at the default search cap (+5V, ANODE_GATE, BREW_SCL, FLOW_IN, BREW_AN, PT2_BIAS); ANODE_GATE and BREW_AN route alone at a larger cap, 4 are geometric |
| 3 Crop DRC, routing-attributed | clearance 1, hole_to_hole 1, track_angle 8, courtyard 2 (crystal keep-clear), segment length 0 | clearance 0, hole_to_hole 0, track_segment_length 0, courtyard 0, track_angle 14 lines |
| 4 Inner-layer share | 10.6 % | 8.4 %, 8.8 %, 4.9 % |
| 5 Via in SMD pad | 0 (one DRC shorting line at TP623) | 0 |
| 6 SPI3 trunk along copper (69 mm limit) | MOSI 76.1, MISO 75.9 | MISO 66.6, 74.6 (complete in one run), MOSI 84.7 (one run), SCK never complete; selects PT1_CS 40.6, AMC_CS 21.3; WT2_DATA 12.8, WT2_CLK 32.5; WT1 lines incomplete |
| 7 Mains separation | 0 | 0 (no `Mains separation` line for U203, R208, C206, C609, C610, C612) |

**Where the connectors ended.** J791 (128.14, 19.08) turned 270, 6.6 mm from (129, 12.5), pin 1 north, 1.7 mm from the right edge. J821 (111.64, 31.04) turned 270, 17.7 mm from (129, 34.5), pin 1 north, 18.2 mm from the right edge. J761 (128.46, 63.55), 3.4 mm moved, right edge 1.8 mm. J521 and J522 stay within 2 mm of the bottom edge. The top-entry harness headers moved inward: J501 (94.49, 28.25), J520 (87.31, 26.27), J523 (105.17, 28.18), J525 (102.09, 14.91), J861 (95.18, 42.65) in the north interior; J502 (121.27, 63.55), J503 (123.49, 51.47), J570 (118.55, 53.53), J571 (105.75, 55.10) east; J524 (109.94, 93.33), J620 (95.89, 105.32), J625 (81.14, 106.01), J630 (105.08, 92.43), J635 (103.79, 110.32) south. The layout plan's low-voltage harness enters from the right edge and the plan gives an edge only to J761, J791, J821, J521 and J522; the others are "top-entry, interior". Of the five, only J821 is now away from its edge (18 mm), so the right-edge harness assumption needs the owner's attention for the panel cable alone; the interior headers are 6 to 35 mm from the right edge and their harnesses must be laid across the board to reach it.

**Freeing the connectors and moving the controller west.** Moving U401 to x 104 takes U401 itself from 17.28 mm to 13.28 mm from the module (the rest of its block holds 15.5 mm) and brings the crystals' strict 10 mm into play. With the Phase 1b connector positions and every other decision held, six annealer seeds found no overlap-free placement (best one courtyard overlap, U630 with J630, and the crystal 9.0 mm from J761); with the connectors free one of four seeds did. So the freedom was needed for feasibility and did not change the route count (A 66, 67, 73 failed against R 66 to 85), the inner share or the SPI3 trunk length; it cleaned the DRC lines (crystal keep-clear and both clearance and hole-spacing lines at zero), at the price of ANODE_GATE standing 62 mm long (R821 now beside J821, its gate pin on the south side of U401), which the router finds only with a larger search cap.

**Variant B, reed moved 5 mm right to (127, 91.5).** Two of four seeds overlap-free (one of four for A). The box then contains FID3 at (129, 117.6), so FID3 must move 0.2 mm down, and the reed stands 5 mm from the right edge instead of 10. Routed (`pl_b1s3x`): 70 and 76 failed of 361 against A's 66 to 73 of 351; inner share 6.9 and 7.7 %. Straight-line U401 to U621 on the SPI3 bus averages 31.5 mm over four seeds against 35.6 mm for A, but the routed SPI3 trunks stay incomplete or long. It does not clearly help and is not recommended.

**Recommended next step.** Take variant A as the scratch candidate (reed fixed). Decide the two floorplan rows it moves: the controller block to the module at 13.3 mm for U401 itself (decision 2 as taken), and the panel connector J821 inside the board rather than on the right edge. SPI3 trunks still need a hand route or a closer converter cell; the rung-6 floorplan change in Phase 1b stands.

## Findings from the proof rows (2026-11-10), carried to close-out

- FLOW_IN on PB10 meets the bootloader's USART3_TX (AN2606 Rev 70 Table 135, set as an input only on a version 0x91 bootloader): with a 0x90 bootloader and the flow meter output low, U520 pin 4 and PB10 are two outputs on one net with no series part, 1.35 V unabsorbed at 20 mA (circuit-verdicts.md FLOW_IN row). CLOSED 2026-11-10 by the owner's decision of a series resistor: R545, 220 ohm 0603 (LCSC C22962), between U520 pin 4 (net FLOW_BUF) and FLOW_IN on sheet 52; the contention current is at most 3.6 V / 216.8 ohm = 16.6 mA in either polarity against the pin's 20 mA (circuit-proof.md row `FLOW_IN on PB10`, circuit-verdicts.md rows R545, net FLOW_BUF and net FLOW_IN, now PASS). The bootloader version is still read at bring-up.
- The bootloader also drives other connected pins: SPI4_MISO PE13 (KNOB_HOT), SPI1_MISO PA6 (BREW_AN) and USART2_TX PA2 (an analogue input). No record is known to cover them; check before close-out.
- The change list's claim that PB7 is unconnected is stale: PB7 is BREW_SDA (I2C4_SDA).
- The spice export warns "schematic has annotation errors" (exit 0); not yet investigated.
- Pre-existing record inconsistencies found while adding R545, not caused by it: the stated group B row (39/13/6) and the stated PASS total in circuit-verdicts.md do not match a recount of the committed file (recount after R545: totals 425 PASS / 113 FINDING / 6 N/A, group B 38 PASS / 12 FINDING); `test_board_net_pair_exceptions` fails to import `test_board_spacing_exceptions` under `python3 -m unittest hardware.tools.tests...`. Settle both at close-out.
