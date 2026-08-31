# Lint sweep classification

**Snapshot `snap-1788169047025698000-70aada9c`, 792 warnings across 10 reporting rules, 11 rules skipped (no AI-grader executor shipped for them — see `staircase lint --format json` → `skipped[]`).** Re-run `./engine/staircase lint --format json` for the live sweep; this file records what each *reporting* rule means for this project as of the snapshot above, not a target count to chase down (SOL-LINT-SWEEP-PROJECT-FIT.C5). The count moves as the graph is worked even with no rule change: this slice's own evidence-authoring pushed `attested_criterion` from 327 to 332 (five new criteria — this SOL's own C1-C5 — became attested), which is the rule working as intended, not drift to chase.

Three groups, per SOL-LINT-SWEEP-PROJECT-FIT.C1: rules that fit this project (warnings are meaningful, whether or not any instance is a defect), rules that could fit if given this project's vocabulary through a real configuration surface, and rules that cannot be satisfied from inside this repository at all.

## Group 1 — fits this project

| Rule | Count | What the warnings mean here |
|---|---:|---|
| `graph.delivery_chain_immutability.attested_criterion` | 327 | Immutability notice on criteria whose parent requirement/deliverable has been attested. Working as intended — an attested criterion is frozen by design; this is not a defect. |
| `graph.delivery_chain_immutability.sealed_aggregation_criterion` | 68 | Same, for criteria under a sealed aggregation deliverable (task/milestone/epic/roadmap). Working as intended. |
| `graph.evidence_test_liveness.cited_test_non_go_artifact` | 152 | Evidence citing a Unity test suite or a Taskfile gate (e.g. `task fw:sweep`) rather than a Go test. `lint explain` states outright this is a legitimate test method for a non-Go project and needs no repair — the rule fires to flag "unverifiable by this liveness checker," not "broken." |
| `graph.dependency_wiring_completeness.unwired_prerequisite` | 38 (was 57) | A solution's prose names a graph node without a corresponding link. 19 of the original 57 location-hits were real gaps across 12 distinct missing links (see "Real defects fixed" below), now wired. The remaining 38 are deliberate contrastive/out-of-scope mentions ("rather than X", "confirmed unrelated to X", historical attribution) — read individually via `show <id>` for every one and confirmed not to name a real prerequisite. They stay flagged because this rule's disambiguating AI companion, `graph.dependency_wiring_completeness.mention_classification`, has no executor yet (`skipped[]`) — there is no way to tell the sweep "this mention is deliberate" until that companion ships. Re-triage is only needed if new solutions are authored with unlinked mentions, or when the companion rule gets an executor. |
| `graph.solution_criterion_authoring.missing_scope_boundary` | 10 | All 10 hits are real — the flagged criteria genuinely omit a scope-boundary sentence. All 10 are also `attested_criterion` hits (frozen). Per SOL-LINT-SWEEP-PROJECT-FIT.C4, an attested criterion is never edited in place; the remedy is supersession, a deliberate act with its own reasoning that is explicitly out of scope for a lint-classification slice. Nodes: `SOL-BREW-PRESSURE-RATIONALE-CORRECTED.C1`, `SOL-CROSS-TIER-CONVERTER-MARGIN-RECURS.C1`, `SOL-CROSS-TIER-CONVERTER-MARGIN-WIDENED.C1`, `SOL-DOMINANCE-RECORD-NAMES-THE-MODEL-AS-IT-STANDS.C1`/`.C2`, `SOL-ESTIMATOR-IDENTIFIABILITY-UNDER-DRIFT.C2`/`.C3`, `SOL-PLANT-STEAM-FEED-PUMP-WIRED.C1`, `SOL-PLANT-STEAM-FEED-SENSIBLE-HEAT.C2`, `SOL-READ-AHEAD-END-TEST-STILL-NEEDS-SAFE-SAMPLE.C1`. |

### Real defects fixed (SOL-LINT-SWEEP-PROJECT-FIT.C4)

12 missing links added via `staircase author update --add-link` after individually reading every source node and every target node with `show`:

| Source | Link | Target |
|---|---|---|
| `SOL-BREW-PRESSURE-RATIONALE-CORRECTED` | `justified-by` | `DEC-PROFILE-COMMANDS-FLOW` |
| `SOL-CROSS-TIER-CONVERTER-MARGIN-RECURS` | `depends-on` | `SOL-CROSS-TIER-CONVERTER-MARGIN-WIDENED` |
| `SOL-CROSS-TIER-CONVERTER-MARGIN-WIDENED` | `depends-on` | `SOL-HOT-WATER-BAND-HOLDS-RATE-YIELDS` |
| `SOL-CROSS-TIER-CONVERTER-MARGIN-WIDENED` | `depends-on` | `SOL-PLANT-MODEL-AGREES-ACROSS-TIERS` |
| `SOL-HELD-DELIVERY-REVALIDATED-ON-RESUME` | `depends-on` | `SOL-DELIVERY-INFEASIBLE-PROFILE-REFUSED` |
| `SOL-PLANT-STEAM-FEED-PUMP-WIRED` | `depends-on` | `SOL-PLANT-STEAM-DRAW-CHANNELS` |
| `SOL-POST-DRAW-DISTURBANCE-PROOF-RESTORED` | `depends-on` | `SOL-BREW-RECOVERS-AFTER-DRAW` |
| `SOL-POST-DRAW-DISTURBANCE-PROOF-RESTORED` | `depends-on` | `SOL-COURSE-COMMANDED-DELIVERY-HOLDS-THE-BAND` |
| `SOL-READ-AHEAD-END-TEST-STILL-NEEDS-SAFE-SAMPLE` | `depends-on` | `SOL-COMMANDED-COURSE-ACTED-ON-AHEAD-OF-EFFECT` |
| `SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR` | `depends-on` | `SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR` |
| `SOL-SIM-ROBUSTNESS-REFUSAL-HOLDS-WHEN-BELIEF-OVERSTATES-CAPABILITY` | `depends-on` | `SOL-SIM-ROBUSTNESS-SURVIVES-ARBITRARILY-WRONG-MODEL` |
| `SOL-SUCTION-LINE-METER-COST-DIFFERENTIAL` | `depends-on` | `SOL-SUCTION-LINE-PUMP-MARGIN` |

`DEC-PROFILE-COMMANDS-FLOW` is a decision, which the `unwired_prerequisite` rule's own explanation doesn't cover (it only names delivery-chain and requirement-chain cases) — `depends-on`'s schema `valid_targets: [requirement, deliverable]` rejects a decision target, so `justified-by` (`valid_targets: [decision]`) was used instead, per `.staircase/schema.yaml`. `staircase validate` reports 0 errors, 0 warnings after all twelve.

## Group 2 — could fit, given vocabulary

**Empty.** No config surface exists for any rule in this sweep. Checked `.staircase/config.yaml` (no lint/vocabulary/registry section), `.staircase/schema.yaml` (node-type schema only), and `staircase capabilities --format json` (`lint-config plan`/`apply` operate on numeric threshold maps; none of the reporting families expose a `thresholds` object, only `detection_shape`). Per SOL-LINT-SWEEP-PROJECT-FIT.C2, that absence is itself the finding — every rule that looked like it might belong here moved to Group 3 instead.

## Group 3 — cannot be satisfied here, raised upstream

| Rule | Count | Why this repo can't satisfy it |
|---|---:|---|
| `graph.infrastructure_reality.orphaned_seam_registry_entry` | 86 | Resolves against `engine/lint/infrastructurerealitydetector/seam_registry.yaml`, a file in the staircase engine's own Go source tree. This repo ships only the compiled `engine/staircase` binary — no Go source, no registry file to add an entry to. |
| `graph.infrastructure_reality.unresolved_backticked_token` | 87 | Same registry file, same reason — flags this project's own C identifiers and file paths against a registry this repo cannot reach. |
| `graph.infrastructure_reality.unresolved_camelcase_identifier` | 12 | Same. |
| `graph.decision_authoring.title_as_statement` | 4 | Detector requires a copula ("is"/"are") even though its own shipped examples use non-copula verbs (`stores`, `uses`). All 4 flagged titles (`DEC-MARGIN-COMBINES-DECLARED-ERROR-BY-WORST-CASE`, `DEC-PLANT-MUTATION-COVERAGE`, `DEC-READING-ANSWERS-FOR-THE-ELAPSED-INTERVAL`, `DEC-SENSING-ERROR-ADDS-TO-COMMANDED-MARGIN`) already read as resolution statements; this project's own CLAUDE.md already documents the same false positive. |
| `graph.evidence_test_liveness.cited_test_file_absent` | 3 | Fires on evidence citing `task fw:check (check_structure_exclusive)` / `task fw:sweep` — Taskfile-driven gates. Verified live: `firmware/tools/check_structure_exclusive.py`, the `fw:check` task and the `fw:sweep` task all exist and run today. Not dead citations — the same `task <name> (<subject>)` shape that `cited_test_non_go_artifact` already tolerates trips this sibling rule's file-path liveness check instead. |

**Raised:** [Resident-X/staircase#1218](https://github.com/Resident-X/staircase/issues/1218) — one consolidated issue covering all four rules above, since all four share the same root cause: detectors built against the engine's own Go-project conventions (an internal identifier registry, Go-test-file liveness checking, ADR-copula phrasing) applied uniformly to a consumer project that is neither Go nor structured like the engine's own repo.
