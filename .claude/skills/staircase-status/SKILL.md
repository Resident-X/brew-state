---
name: staircase-status
description: "Requirement and delivery chain health dashboard. Reports graph shape, requirement chain coverage by priority, delivery chain phase and milestone health, planning coverage via targets links, and drift indicators. Use when checking overall project health, reviewing coverage metrics, or assessing whether the plan is still valid. For the actionable work queue — what to build next — use /staircase-queue instead."
---

# Staircase Status

Answers: **Where are we? Is the plan still valid?**

Health metrics for both chains. For the work queue (what to build, what's blocked), use `/staircase-queue`.

CLI: `./engine/staircase`. Reads from the project's `.staircase/index.db`, which the apply pipeline keeps fresh on every `author --confirm`.

## Response shape

Read the whole JSON payload into context — it is self-describing, so take each value together with the inline meaning shipped beside it. See the graph-reads rule in CLAUDE.md.

Per the engine's per-consumer projection mapping, `gaps` returns the leanest **identity tier**; `summary` (including `top_gaps`), `list`, and the resolved link-target blocks of `show` return the **compact tier** (identity plus a few type-specific state fields); only `show`'s primary subject emits full prose (`text`, `rationale`, link narrative, and criteria children). Which fields each tier carries is the engine's live contract — read it from `staircase capabilities <command> --format json`, and read the payload raw rather than memorising a field list here.

## Step 1 — Confirm the binary exists

Binary missing: `cd engine && go build -o staircase ./cmd/staircase && cd ..`. If `.req.yaml` files were edited outside the apply path (manual edits, git pull), run `./engine/staircase build specs/` once.

## Step 2 — Parallel data fetch

Issue all in parallel:

```bash
# Full-graph coverage
./engine/staircase --format json gaps

# Node counts by type/category/status
./engine/staircase summary --format json

# All deliverables (roadmaps, milestones, solutions)
./engine/staircase list --type deliverable --format json

# Roadmap IDs (needed for Step 5 phase loading)
./engine/staircase list --type deliverable --category roadmap --format json

# Priority distribution (transitional Grep — absorbs when summary exposes priority)
Grep ^priority: must$   specs/**/*.req.yaml  output_mode:count
Grep ^priority: should$ specs/**/*.req.yaml  output_mode:count
Grep ^priority: could$  specs/**/*.req.yaml  output_mode:count
```

## Step 3 — Graph Summary

From `summary` → `data.counts.by_type` and `by_status`. Priority counts from Grep.

```markdown
## Graph Summary

| Type        | Count | | Status     | Count | | Priority | Count |
|-------------|-------|-|------------|-------|-|----------|-------|
| requirement | N     | | active     | N     | | must     | N     |
| deliverable | N     | | deprecated | N     | | should   | N     |
| criterion   | N     | |            |       | | could    | N     |
| evidence    | N     |
| decision    | N     |
| **Total**   | **N** |
```

## Step 4 — Requirement Chain Coverage

From `gaps`: `{status, shape_version, data: {gaps[], covered[], violated[], total}}` (canonical envelope — the coverage report is under `data`).

Compute: `implicit = total − len(covered) − len(violated) − len(gaps)` (criteria with child requirements and no direct evidence — covered via decomposition, not a gap).

Coverage % = `(direct + implicit) / total`.

Derive priority for `covered[]` and `violated[]` entries by stripping `.C<N>` from the criterion ID to get the parent ID, then reading `priority:` from the parent file.

```markdown
## Requirement Chain Coverage

| Priority | Criteria | Direct ev. | Via decomp | Gaps | Violated | Coverage |
|----------|----------|------------|------------|------|----------|----------|
| must     | N        | N          | N          | N    | N        | X%       |
| should   | N        | N          | N          | N    | N        | X%       |
| Total    | N        | N          | N          | N    | N        | X%       |
```

**These are health metrics. They are not a task list.**

## Step 5 — Delivery Chain Health

Roadmap IDs come from the Step 2 `list --category roadmap` fetch. For each roadmap:

```bash
./engine/staircase show <roadmap-id> --format json
  → phase criterion IDs from data.criteria[].id
```

Map milestones to phases: Grep `target: RM-*` in `specs/deliverables/` to find which milestones target which phase criterion.

Per milestone, in parallel:

```bash
./engine/staircase --format json gaps --scope <milestone-id>
  → direct   = len(data.covered)
  → violated = len(data.violated)
  → gaps     = len(data.gaps)
  → total    = data.total
```

The covered/gaps/total numbers here mix REQ-*.C* and SOL-*.C* criteria. They reflect how much of the requirement space the milestone addresses — **not how much implementation work remains**. Use them as health indicators only.

Phase status (apply most specific):
- **COMPLETE** — gaps == 0 && violated == 0 && total > 0
- **REQ BLOCKED** — violated > 0
- **IN PROGRESS** — covered > 0 && gaps > 0
- **PLANNED** — milestones exist, covered == 0
- **UNPLANNED** — no milestones for this phase

```markdown
## Delivery Chain Health
_Covered/Gaps mix REQ-*.C* and SOL-*.C* criteria — requirement-chain health signal, not work remaining._

| Phase | Title                  | Milestones | Covered | Gaps | Violated | Status      |
|-------|------------------------|------------|---------|------|----------|-------------|
| C1    | Close the floor        | 5          | 91      | 79   | 0        | IN PROGRESS |
| C2    | Workflow MVP           | 4          | 0       | 58   | 0        | PLANNED     |
```

## Step 6 — Planning Coverage (targets links)

Transitional simulation until `staircase plan-coverage` ships:

```pseudocode
Grep "type: targets" across specs/deliverables/**/*.req.yaml
  → collect all target criterion IDs
Cross-reference with must-priority REQ-*.C* criteria
  → untargeted = must criteria with no deliverable claiming them
```

```markdown
## Planning Coverage

|               | Targeted | Untargeted | Coverage |
|---------------|----------|------------|----------|
| must criteria | N        | N          | X%       |
| should        | N        | N          | X%       |
```

## Step 7 — Drift Assessment

If any phase is REQ BLOCKED: list `criterion_id`, failing evidence method, and `observed_at` for each violation.

If must-priority criteria have no `targets` link: list them — they are planned gaps.

Recommend: **patch requirement-graph violations** (fix broken evidence links or re-evaluate failed criteria), **replan** (`/staircase-plan`), or check the work queue (`/staircase-queue`).

## Discovery Discipline

Attempt canonical invocations directly. On unknown-command or unknown-flag failure:

```bash
./engine/staircase --format json capabilities <command-path>
```

Read returned `flags[]` and retry once. Full `capabilities` (no arg) only when targeted query fails.

## Key Rules

- **Health metrics, not task list.** `gaps[]` at any scope is a coverage indicator. It does not determine what implementation work remains.
- **`covered + violated + gaps ≠ total`.** Implicit (decomposition) = total − covered − violated − gaps. Always compute and report separately.
- **No work queue here.** Use `/staircase-queue` for the WSJF-ranked next-action list and parallel-agent assignment.
- **Both chains every time.** Requirement chain coverage AND delivery chain health in every status report.
- **Read from `.staircase/index.db`.** The apply pipeline commits projection freshness on `author --confirm`, so the project index reflects the current graph state.
