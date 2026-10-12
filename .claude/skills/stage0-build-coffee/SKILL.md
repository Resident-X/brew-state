---
name: stage0-build-coffee
description: Operator skill for this repository — wraps /staircase-build with the quality and cost discipline the upstream workflows do not yet enforce, adapted to this project's verification (the firmware's host, emulation and mutation tiers behind `task fw:verify`, and inspection or analysis for machine-record and hardware-design work). A pre-build readiness pass that settles decisions into the solution, a narrow implementer that never runs the full gate, a review given the diff and the applicable decisions, a class-based fix loop with a round budget, and a per-dispatch metrics log. Use for every solution build in this repository.
---

# Stage 0 build (coffee) — operator discipline around /staircase-build

Answers: **how do I build one solution in this repository so it completes first time, at low cost, while the upstream workflows do not yet enforce that themselves?**

This is an **operator skill**, not a product skill. It replaces the upstream `stage0-build`, which is written for the Staircase engine's own repository: it names that repository's gate tasks and retires its steps against that repository's graph. The steps here bridge gaps in the upstream workflows (`WF-BUILD`, `WF-REVIEW`) as this project's pinned engine serves them. When a `task sc:update` brings an engine whose served brief does a step's job, trim that step here in the same PR that bumps `STAIRCASE_REF`. A judgement step (a review, a readiness check) is trimmed only after the engine's version has run beside it for three builds without missing an ISSUE class the step found.

It **wraps** `/staircase-build`: Phases A–E there still apply unchanged. This skill only adds work before, inside, and around them.

## The principle it enforces

**Decisions are settled before any work is written; discovery is left to implementation.** A decision is a design choice, a convention, a spec question the criteria leave open, or a fact only the operator holds (their supply, their circuit, a part on the bench). Discovery is exact functions, test shapes, table layouts and edge cases found while doing the work. If a solution needs a decision that cannot be made until something else is built, it is **not buildable yet**: split or defer it. Never build it and let review find the gap. A fact or a design choice the operator owns is brought to them with a recommendation, never settled on their behalf.

## What each step bridges

| Step | The gap in the upstream workflow |
|---|---|
| 0. Slicing homework | The slicer reports decisions it cannot settle but cannot settle them |
| 1. Readiness pass | Preflight does not search for cross-cutting decisions beyond the leaf's own links, nor for overlapping work elsewhere |
| 2. Narrow implementer | The served implement brief does not carry this project's verification commands |
| 3. Gate once, as `fw:verify` | The gate worker is told to find "the project's complete verification", and the upstream skills it can read name tasks this repository does not have |
| 4. Review with diff + decisions | The reviewer is served neither the diff nor decisions settled only in solution prose |
| 5. Class-based fix loop | There is no fix-cycle path: each round is a new run |
| 5b. Blind review before elevation | The project's Rule 7 blind review is not part of `WF-REVIEW` |
| 6. Metrics log | No whole-run cost measurement |

## This project's verification (every step that tests or judges uses it)

CLAUDE.md is the source; this summarises what the build steps need from it.

- **The criteria are the test spec.** Every criterion gets at least one verification that would catch a real regression: edge cases, error paths, empty or malformed input, not a smoke test that only shows the code runs. A criterion verified by `test` gets a test. One verified by `inspection` or `analysis` gets a stated check of the delivered artefact against each clause, with the arithmetic shown for analysis.
- **Trace in tests, never in code.** The criterion id and its text sit in the comment heading the test that verifies it: a `/// SOL-X.C2: <criterion text>` doc comment on a C test function, a `# SOL-X.C2: <criterion text>` comment opening a Python test. Never put requirement ids in implementation code. A machine-record document citing the criteria its figures come from is content, not a trace comment.
- **Three tiers before energisation** (`DEC-SIM-VERIFICATION-TOOLCHAIN`):
  - **Host.** `task fw:build`, `fw:check`, `fw:test`, `fw:run`: the control logic, estimator and plant model compiled for the host, run under sanitizers, plus the build-time checks. Memory and undefined-behaviour defects are caught here and only here.
  - **Emulation.** `task fw:emulate`: the target build's own artefact under emulation against modelled peripherals. Logic, peripheral-interaction and timing-structure defects.
  - **Target.** Worst-case timing on the real, un-energised board. A bench step, not a task.
- **Mutation.** `task fw:sweep` alters the plant model's arithmetic and requires a test to notice; it is part of the full gate. `task fw:mutate` (seeded property breaks) runs on demand only, and the hosted mutation sweep (`.github/workflows/mutation-sweep.yml`) runs on manual dispatch only.
- **The complete verification is `task fw:verify`.** It is the only complete verification the Taskfile declares, it has no separate build-round tier, and it took over forty minutes on 2026-10-13, about thirteen of them before the mutation sweep and the rest in it. It runs once per round as the gate (Step 3) and nowhere else. No pull-request CI and no scheduled run of `main` exist, so the round gate is the only pre-merge verification.
- **Generated records pin their inputs.** The analysis records under `docs/` (protection margin, parameter dominance, stability, identifiability) print the sha256 of each file they were generated from, and an emulation test fails when one goes stale. A change to any of those inputs (the `firmware/params/` descriptions and declarations), even a comment, regenerates the affected records with their own tools in the same change.
- **Machine-record and hardware-design work** lands in `docs/sunbeam-em7000/` and its `controller-design/` working folder. Per `DEC-MACHINE-RECORD-FOLDER-PER-MACHINE`, sources govern and derived views are corrected to match. Every changed fact is chased through every document that restates it. No board rule-check task exists yet. When one is added it belongs in the verification this section names, and `task --list` shows it.
- **Synthetic fixtures.** Tests that read the graph use generic ids (`REQ-TEST-001`, `TST-*`) and tempdir projects, never real node ids from `specs/`.

## Metrics log (used by every step)

One JSON object per line, appended to a single file shared by all worktrees:

```bash
LOG="$(git rev-parse --path-format=absolute --git-common-dir)/../.staircase/stage0-metrics.jsonl"
```

Row fields: `ts`, `sol` (solution id), `round` (1 = first build), `step`, `model` (exact id), `input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `output_tokens`, `cost_usd`, `wall_s`, `findings` (object: class → count, `review` and `blind-review` rows only), `notes`. Every row records the effort level in `notes` as `effort=<level>`.

| `step` | The dispatch |
|---|---|
| `slicing` | Step 0 slicing homework |
| `readiness` | Step 1 readiness pass |
| `brief-review` | Step 1b brief review |
| `premise` | WF-BUILD's `verify_slice_premise` executor |
| `implement` | Step 2 implementer, round 1 |
| `gate` | Step 3 run-and-report worker |
| `review` | Step 4 `reviewer_review` |
| `fix` | Step 5 fix agent |
| `blind-review` | Step 5b blind review |
| `homework` | Any other fan-out agent |
| `orchestrator` | The operator session itself, logged once at close-out (Step 6) |

Dispatch the agents this skill spawns **headless** so the usage split is real. Write the prompt to `<worktree>/.stage0/<step>.prompt` (`.stage0/` is git-ignored scratch), then from the worktree run:

```bash
claude -p --model <exact-model-id> --effort <level> --output-format json [--permission-mode acceptEdits] \
  --allowedTools "<tools>" < .stage0/<step>.prompt > .stage0/<step>.out.json
```

- The output is a JSON array of events. The last element with `"type": "result"` carries `result` (the agent's report), `usage` and `total_cost_usd`. Copy those into the log row.
- Tools: slicing homework, readiness and review use `Read Grep Glob Bash` (Bash for the read-only engine CLI; the prompt forbids writes). Implement and fix use `Read Grep Glob Write Edit Bash` with `--permission-mode acceptEdits`. The gate worker uses `Bash Read Grep Glob` with no permission mode.
- Take the model id from `/staircase-wf`'s tier→model table, and set `--effort` explicitly:

| Dispatch | Tier | Effort |
|---|---|---|
| Slicing homework | mid-tier | `medium` |
| Readiness pass | reasoning-tier | `high` |
| Brief review, premise, review | reasoning-tier | `high` |
| Implement, fix | reasoning-tier | `high` |
| Gate worker | mid-tier | `medium` |

- **A foreground Bash call stops at ten minutes.** Run any dispatch that can take longer (implement, and always the gate) with `run_in_background` and a timeout of at least two hours, and act on its completion notification. A dispatch killed by a timeout leaves the run parked where it was: check `git status` for a half-made edit, restore it, and dispatch again with the longer limit.
- If a result is missing its promised output, treat the dispatch as incomplete, check the tree for a leftover temporary edit and restore it, then dispatch a fresh narrow agent for the remainder, telling it what the partial run did and did not finish. If you must use the Agent tool instead of headless, record its token total in `input_tokens`, leave the cache fields `null`, and say so in `notes`.

Readiness and slicing use hybrid search. `task sc:init` links the embedder; without it the query response states its degradation reason.

## Step 0 — Slicing homework (before slicing a task)

Only when `next` shows a task as `slice-needed`.

1. Spawn a fresh **mid-tier** agent with the slicing prompt in [references/prompts.md](references/prompts.md) for the task.
2. Settle every `UNSETTLED` decision before slicing: fan out homework and, if it makes the answer clear, author the decision node through `/staircase-author` and continue. If it is still genuinely unclear, or it is a fact or design choice the operator owns, pause and bring the operator a recommendation grounded in the graph (or open `/staircase-discuss`).
3. Slice what is decidable through `/staircase-plan`. Every solution the slicer materialises goes through Step 1 before it is built.

## Step 1 — Readiness pass (after `/staircase-build` Phase A, before Phase B)

Run `/staircase-build` Phase A first: the worktree and branch must exist, because this step commits a graph change into it. Then spawn one fresh **reasoning-tier** agent with the readiness prompt in [references/prompts.md](references/prompts.md). It is read-only. Save its report to `<worktree>/.stage0/<SOL>-readiness.md`.

Act on its verdict:

- **BUILD**: write every settled decision the solution does not already link, the locus, and the placement (reuse, extend or new, with the rejected options) into the solution through `/staircase-author` (`author update --bump-version`; CLAUDE.md: "Bump once per uncommitted session (N→N+1 from the committed baseline), not per edit"). Criteria gain the settled decision as text, not as a pointer to the report. Commit, then Step 1b.
- **UNSETTLED**: settle each decision as Step 0 item 2 directs, commit, and run Step 1 again on the corrected brief.
- **SPLIT / DEFER**: a decision depends on work not yet built. Split the decidable part into its own solution, or wire the solution `depends-on` the missing work, through `/staircase-author`.

A settled decision often reaches past the leaf: a changed declaration has consumers elsewhere (firmware parameters, simulation results, working documents). Chase each one when you settle it. Cover it with a criterion on this leaf, or with a solution that owns it (a `DEL-MAINTENANCE` child for already-sealed work). Preflight stops with `preflight-uncovered` on any consumer nothing covers.

## Step 1b — Confirm the brief (before every WF-BUILD run on a changed leaf)

WF-BUILD admits only a leaf whose recorded brief confirmation matches the leaf and its criteria as they stand. `show <SOL-ID> --format json` reads the confirmation state.

- **When:** after Step 1's graph commit, and again after any later edit to the leaf or its criteria.
- **How:** drive `WF-REVIEW` through `/staircase-wf` with the brief subject `{kind: brief, leaf_id: <SOL-ID>}`, its executor at reasoning-tier headless.
- **On a pass:** commit what the engine wrote: `git add 'specs/**/<SOL-ID>*.req.yaml' specs/.events/`. Then check that `git status --short` is empty.
- **Hold under an enforcing profile.** The graph does not record who wrote a node, so a profile that enforces reviewer independence refuses both the brief review and build admission: `next` shows the leaf as `independence-shortfall`, and a run start exits with `insufficient_independence`. This project runs the engine's default profile, which does not enforce it. Never pass `--profile` naming an enforcing profile; if `next` shows `independence-shortfall`, the configured profile has changed, so stop and take it to the operator.
- **On findings:** each is a defect in the brief. Fix it through `/staircase-author`, commit, and review again. A finding class that comes back on the next review is a design problem: take it to `/staircase-discuss`.

## Step 2 — Drive WF-BUILD; narrow implementer

Run `/staircase-build` Phase B: `wf start WF-BUILD` with `target_id` the slice's parent, `slice_id` the solution and `artifact_version` the current `HEAD`.

**If preflight stops before `implement_slice`**, the run's terminal output names why in `build_outcome`:
- `premise-contradicted`, or `preflight-uncovered` with a `premise_correction`: the proposed patch is a proposal the engine never applies. Review it, author it through `/staircase-author`, commit, confirm the brief again (Step 1b), and start a new WF-BUILD run.
- `preflight-uncovered` with no correctable patch, or `preflight-open-decision`: settle as Step 1 directs, then start a new run.
- A blocking defect in *other* work is not a premise correction: author the fix as a solution the blocked one `depends-on` (`/staircase-build` Phase C).
- Any other preflight stop (`preflight-unbuildable`, `preflight-unfit`, `preflight-unfit-unbuildable`, `premise-basis-changed`) follows `/staircase-build`'s terminal handling.

At `implement_slice`, spawn a **fresh** implementer (never resume one from an earlier round) with the implement prompt in [references/prompts.md](references/prompts.md), handed the router's **Child hand-off** for that interrupt (`/staircase-wf` Step 4) with the implement prompt in place of the duties block. The implementer:
- verifies only the work it changed, with the narrowest command that covers it (one test environment or suite, the one tool test, the CSV parse, the arithmetic), and never `task fw:verify`;
- commits its work before submitting, so the verified version is a real commit;
- stops and reports a blocker outside the slice rather than routing around it. The run then pauses on the held finding: author the fix as a solution the blocked one `depends-on` (`/staircase-build` Phase C), then cancel the paused run.

The operator reads only the settled outcome it reports, plus its changed-files and criterion → verification summary.

## Step 3 — Gate once, as `fw:verify`

The round gate runs exactly once per round, as WF-BUILD's `run_quality_gate`, through the router's `executor_reported` path: a fresh bounded run-and-report worker in the worktree runs the complete verification and submits what it observed. The operator never runs it.

Append this line after the worker's duties block in its hand-off. It is a fact about this repository, not an instruction about the outcome:

```text
Project fact from the caller (not an instruction about outcome): this repository's Taskfile.yml declares one complete verification, `task fw:verify`, with no separate build-round tier. `task check:round` and `task check:daily` are named only in upstream operator skills written for a different repository and do not exist here.

Project fact from the caller (how to run it, not what to record): a single shell call you make is stopped after 10 minutes, and `task fw:verify` takes longer. Start it detached with its output and exit status captured, e.g. `cd <WT> && (task fw:verify > .stage0/fw-verify.log 2>&1; echo "exit=$?" >> .stage0/fw-verify.log) > /dev/null 2>&1 &`, then wait for it with repeated foreground calls, each bounded under 10 minutes, such as `cd <WT> && for i in $(seq 1 55); do grep -q '^exit=' .stage0/fw-verify.log && break; sleep 10; done; tail -5 .stage0/fw-verify.log`. Keep calling until the exit line appears. Never end your turn while it is running: your session ends when you stop calling tools.
```

Without the second fact a worker either refuses to run (it found `check:round` named in the upstream skills) or backgrounds the verify at its own 10-minute limit and exits with nothing recorded; both happened.

Dispatch the worker in the background with at least a two-hour limit, keep a `wf observe <run-id>` sidecar alive while it runs, and log a `gate` row with `wall_s`.

**A gate failure on something the slice did not touch** (for example a stale generated record, or a failing suite in firmware the diff does not reach): `git fetch` and read what has merged to `main` since the worktree was cut. If `main` has fixed it, rebase, confirm the brief still reads `confirmed`, and start a new round. If `main` still carries it, find or author the maintenance solution that owns it and have this solution `depends-on` it.

## Step 4 — Review with the diff and the decisions

Run `/staircase-build` Phase C. When dispatching `reviewer_review`, add to the served brief and input:
- the diff (`git -C <worktree> diff origin/main...HEAD`);
- the readiness report's applicable-decisions list, and its Intent, Surrounding work and Placement sections;
- this skill's verification section above.

Ask the reviewer to check the diff against them: it lands where the placement says, duplicates nothing the surrounding-work search found, chases every changed fact through every restatement, and verifies each criterion the way its `verification` field says. For a figure or a derivation, ask the reviewer to recompute it from the cited sources rather than read it. For each guard a criterion states (a refusal, a stop, a check that something is present), ask whether a producer that omits, skips or substitutes what the guard requires is refused on every path. Ask the reviewer to give every ISSUE a **class** (short kebab-case, e.g. `unchased-restatement`, `unsourced-figure`, `tested-around-blocker`) plus the decision or criterion it breaks. Log the deviation in `notes` (`"review given diff+decisions (stage0)"`).

## Step 5 — Class-based fix loop

Keep `<worktree>/.stage0/<SOL>-findings.md`: every ISSUE from every round, grouped by class. For each fix round:

- Spawn a **fresh** fix agent with the fix prompt: the findings file, the diff, the readiness report. It fixes **each class structurally**, searching its whole diff for every other instance of the class, not only the one named.
- Each round is a new WF-BUILD run on the same worktree and branch. Do not re-run Step 1 unless a finding changed a decision: pass the existing readiness report to the fix agent. If the round changed the leaf or its criteria, confirm the brief again (Step 1b) first. Discard the previous run's held evidence drafts (`wf list-proposals <old-run-id> --scope in_scope`, then `wf discard-proposal <draft-id>`), so only the final run's drafts are elevated.
- A class that reappears in a later round is a design problem, not a fix: stop and take it to `/staircase-discuss`.
- **Hard stop after round 3.** Report to the operator with the findings file; do not start round 4. A round whose only failure was a gate failure the slice did not cause (Step 3) does not count.
- Re-review with a new WF-REVIEW run against the new WF-BUILD `run_id`, given the delta (`git diff <last-reviewed-sha>..HEAD`) and the findings file. A criterion whose guarantee rests on any changed part is judged again in full.

## Step 5b — Blind review, then elevate

After WF-REVIEW passes and before `/staircase-build` Phase D, run the Rule 7 blind review: a fresh reasoning-tier agent, foreground, given only the solution's criteria, the journeys they trace to, `git diff origin/main...HEAD`, and the path of any uncommitted demonstration record. Give it no readiness report, no checklist and no earlier verdict. Log it as a `blind-review` row with its ISSUE classes, naming in `notes` each class WF-REVIEW also found (`also-in-wf-review=`) and each it missed (`missed-by-wf-review=`). An ISSUE is a new fix round (Step 5), and its re-review is followed by this step again.

Elevate evidence only once this step passes, and only from the final WF-BUILD run's drafts. Before the elevated evidence is first committed, convert a demonstration draft that cites a record file to inline evidence (`author update --id <EVD> --artifact-kind inline --text-file <record>`, its first line stating the verified commit) and delete the record file. Evidence, once written, is never edited: a correction is new evidence, not an edit.

## Step 6 — Close out

`/staircase-build` Phases D–E unchanged. A push runs no gate: the round gate is the only pre-merge verification. Log the operator session itself as one `orchestrator` row:

```bash
.claude/skills/stage0-build-coffee/references/session-usage.sh <session-transcript.jsonl> <build-start-ts>
```

The transcript is `~/.claude/projects/<project-dir>/<session-id>.jsonl`; `<build-start-ts>` is the `ts` of the solution's first row in the log. It prints the token split and `cost_usd` for this session's own turns since then, one entry per model, and a floor for the Agent-tool subagents it spawned. Log one row per model entry, then a final `notes` row summarising rounds, total cost including the orchestrator row, and the classes seen. In the end-of-session summary, compare against earlier rows in the log, and name every engine or skill step that did not fit this repository.

## Key rules

- The graph is the durable home. Readiness reports and findings files are scratch; anything a later step or session needs goes into a node.
- Fresh agents, bounded prompts. Never resume a large implementer; never let a large context wait on a long command.
- Foreground consumption for every agent whose output you need; background with a long limit for any dispatch that can outlast ten minutes.
- Engine reads use `--format json`: read the whole payload, and take each value with the meaning shipped beside it.
