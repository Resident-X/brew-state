---
name: staircase-build
description: "Manages the full slice lifecycle from pre-flight check through PR creation. Use when implementing a requirement slice: runs pre-flight traceability checks and produces a build brief before coding, then quality gates, blind review, evidence recording, and PR creation after implementation."
---

# Build Slice Lifecycle

Answers: **Am I ready to code? What exactly do I need to build and test? And once built — have I verified, reviewed, evidenced, and shipped it properly?**

This skill covers the full slice lifecycle in three phases:

- **Pre-flight (Steps 0–7):** validates traceability and produces the build brief before any code is written.
- **Post-implementation (Steps 8–11):** runs quality gates, mandatory blind review, evidence recording, and PR creation after implementation is complete.
- **Cascade closure (Step 12):** attests the criteria and seals the deliverables that the slice's evidence just made closeable — folded into this PR when the cascade completes on the branch, or as an immediate post-merge follow-on when it needs other in-flight inputs. This is the slice's true end — "PR merged" is not "done".

Run Steps 0–7 BEFORE writing any implementation code. Run Steps 8–11 immediately after — do not skip ahead to the PR. Run Step 12 as soon as the slice's evidence makes a parent closeable — fold it into this PR when the cascade completes on the branch, defer to a post-merge follow-on only when other in-flight inputs are still needed. Do not leave the cascade the slice completed unclosed.

All graph data comes from the Go engine CLI at `./engine/staircase` via JSON output. No Grep+Read loops.

## Response shape

Read the whole JSON payload into context — it is self-describing, so take each value together with the inline meaning shipped beside it. See the graph-reads rule in CLAUDE.md.

Graph-query commands emit per-consumer projection tiers registered in `typebehaviour`. `gaps` returns the leanest **identity tier** (so response size scales with criterion count, not title length); `trace`, `summary`, `query`, `list`, and the resolved link-target blocks of `show` return the **compact tier** (identity plus a few type-specific state fields); the `next` surface returns its own self-describing envelope (an inline `legend` plus per-item meanings); only `show`'s primary subject emits full prose (`text`, `rationale`, link narrative, and criteria children). Which fields each tier carries is the engine's live contract — read it from `staircase capabilities <command> --format json`, and read the payload raw rather than memorising a field list here.

## Authoring delegation

If a slice requires drafting or revising a graph node (most commonly solution criteria during slice kickoff, or criterion text after a blind review finding), invoke `/staircase-author` rather than calling `./engine/staircase author create|update` directly. The author skill carries the per-discipline routing table and applies the rule data plugin guidance before the write reaches the CLI; calling the CLI directly bypasses the discipline check.

## Discovery Discipline (optimistic, not eager)

This skill runs against a live, evolving engine. The agent's training-time knowledge of the CLI's flags may not match the binary. The discipline is:

1. **Attempt the canonical invocation directly.** The commands in this skill are known to work against the engine version that shipped with this skill — do not preface every run with a discovery step.
2. **On unknown-command or unknown-flag failure**, consult the capability listing targeted at the failing command:
   ```bash
   ./engine/staircase --format json capabilities <command-path>
   ```
   Read the returned `flags[]` and `args[]` fields, update the invocation, and retry once.
3. **Only fall back to the full listing** (`capabilities` with no argument) when the targeted query does not resolve the failure — full listing is higher token cost and should not be the default.
4. **Never eagerly enumerate the full CLI surface at session start** unless the agent's training cutoff is known to predate the current engine version by a substantial margin (REQ-CANONICAL-ENGINE-001.C6 eager-cached clause). Eager full-surface discovery on every invocation is the anti-pattern this skill refuses.

The steady-state cost of this discipline is zero — discovery only runs when a command fails. The worst-case cost is one extra targeted `capabilities` call on the rare failure path.

## Arguments

- `$0` — What you're about to build: a solution ID (e.g., `SOL-PARSE-SERDE`), milestone ID, or description of the work.

## Step 0 — Confirm the binary exists

The skill assumes `./engine/staircase` is built and `.staircase/index.db` is current. The project's apply pipeline commits projection freshness on every `author --confirm`, so the index reflects the latest graph state without a pre-step.

If the binary does not exist, build it first:

```bash
cd engine && go build -o staircase ./cmd/staircase && cd ..
```

If `.req.yaml` files have been edited outside the apply path (e.g. manual edits, git pull), run `./engine/staircase build specs/` once to refresh the index.

## Step 1 — Load the target

**If $0 is a node ID:**

```bash
# Load the solution/milestone node — includes criteria children and resolved link titles
./engine/staircase show <ID> --format json

# Trace upward: parent requirements, criteria, decisions, obligations
./engine/staircase trace <ID> --direction up --format json
```

`show` returns `{status, data: {id, type, category, title, text, rationale, links, criteria: [{id, title, measurement_type}]}}`. Criteria children are in `data.criteria` — no separate glob needed.

`trace --direction up` returns `{status, data: {up: Node}}` where each `Node` carries compact `decisions: [{id, title, chosen, version}]` resolved from `justified-by` links. For decision `text` or `rationale`, run `show <DEC-ID>`.

Run both calls in parallel — they share the same DB and are independent.

**If $0 is a description:**

```bash
./engine/staircase query "<keywords>" --format json
```

Present matches and confirm scope before proceeding.

## Step 2 — Extract the build specification

From `show` output (`data.criteria`) and the trace output, synthesise:

```markdown
## Build Brief: {Solution Title} ({ID})

### Criteria to Implement

| # | Criterion | Text | Measurement | Verification |
|---|-----------|------|-------------|-------------|
| C1 | {ID}.C1 | {testable predicate} | binary | test |
| C2 | {ID}.C2 | {testable predicate} | threshold | test |

### Architectural Context

**Decisions:**
- DEC-X: {chosen option}  [from trace.up Node.decisions; `show <DEC-ID>` for rationale]

**Parent Requirements (requirement chain):**
- REQ-X: {title} — this solution satisfies criteria C1, C3  [from trace.up, requirement nodes]

**Delivery Context (delivery chain):**
- MS-X: {title} — this solution is part of milestone  [from trace.up, deliverable nodes]
- RM-Z.C1: {phase title} — roadmap phase

**Dependencies (must exist first):**
- SOL-A: {title} — satisfied? [check via gaps --scope below]
```

## Step 3 — Traceability check

The upward trace output identifies which chain each derives-from link belongs to:
- Nodes with IDs matching `REQ-*`, `SN-*`, `PER-*`, `OBL-*`, `JRN-*` → requirement chain
- Nodes with IDs matching `RM-*`, `MS-*`, `DEL-*` → delivery chain

```markdown
### Traceability

| Capability | Req Chain | Del Chain | Status |
|-----------|-----------|-----------|--------|
| {capability} | REQ-*.C1 | MS-*.C1 | TRACED |
```

**Chain warnings:**
- Solution's trace.up reaches no requirement criteria → WARNING: not traced to requirement chain
- Solution's trace.up reaches no deliverable criteria → WARNING: not placed in delivery chain

## Step 4 — Check for conflicts

```bash
# Find decisions related to the approach
./engine/staircase query "<keywords from solution text>" --format json
# Then load any relevant decisions
./engine/staircase show <DEC-ID> --format json
```

Flag any contradictions between the solution's approach and recorded decisions.

## Step 5 — Dependency check

For each `depends-on` link in `show` output:

```bash
./engine/staircase --format json gaps --scope <dep-id>
```

A dependency is satisfied when its `gaps` report shows `gaps == 0` and `violated == 0`. Flag any unsatisfied dependencies.

## Step 6 — Test specification

For each criterion in `show` output (`data.criteria`), produce **two** test categories:

### 6a — Verification tests (does it work now?)

For each criterion, specify the test that proves the criterion is satisfied in the current build:

```markdown
### Verification Tests

| Criterion | Test Function | What to Assert |
|-----------|--------------|----------------|
| {ID}.C1 | `TestValidYAMLParsed` | Node struct with correct fields |
| {ID}.C2 | `TestMalformedYAMLError` | Error contains file path and line |
```

### 6b — Regression tests (will it keep working?)

For each criterion, ask: **"If a future change broke this, what test would catch it?"** This is distinct from verification — verification proves current state, regression protection survives refactors.

Examples of regression tests that verification alone misses:
- **Migration slices:** import-level tests proving public packages remain importable after internal aliases are removed
- **Interface slices:** compile-time interface satisfaction checks (`var _ Interface = (*Impl)(nil)`)
- **Contract slices:** round-trip tests proving serialization format stability
- **Behavioural slices:** tests that assert specific error messages, output formats, or invariants that a subtle bug could silently change

```markdown
### Regression Tests

| Criterion | Test Function | What It Protects Against |
|-----------|--------------|--------------------------|
| {ID}.C1 | `TestPublicPackageImportable` | Future refactor accidentally unexports a type |
| {ID}.C2 | `TestRoundTripPreservesUnknownFields` | Tolerant reader regression |
```

If a criterion's verification test IS sufficient regression protection (e.g., a table-driven test covering edge cases), note that explicitly — don't leave it as an implicit assumption.

Every criterion must have at least one verification test AND either a regression test or an explicit note that the verification test is sufficient. A criterion without tests is not verified. A criterion without regression protection is tech debt.

### 6c — Property tests (graph engine packages)

Staircase is a graph engine — most internal packages contain traversal, aggregation, or serialisation logic. For any such package, specify `rapid.Check` property tests alongside the verification and regression tests:

```markdown
### Property Tests

| Criterion | Property Function | Invariant |
|-----------|-----------------|-----------|
| {ID}.C1 | `TestTraceNoDuplicates` | forAll(nodeSet) → trace results contain no duplicate IDs |
| {ID}.C2 | `TestCoverageInRange` | forAll(evidenceSet) → coverage ∈ [0.0, 1.0] |
| {ID}.C3 | `TestParseSerializeRoundtrip` | forAll(node) → parse(serialize(n)) == n |
```

If a package is purely CLI glue or output formatting with no graph logic, property tests are optional — note the absence explicitly.

Test conventions (Go):
- Test function names: `Test{Feature}{Scenario}`
- Doc comment: `// {ID}.C{N}: {criterion text}`
- Table-driven tests where multiple inputs test the same criterion
- Use `testify/assert` for assertions
- Property tests use `rapid.Check(t, func(t *rapid.T) { ... })` with testify assertions inside
- Regression tests that guard public API surface go in `tests/sdk/` or equivalent integration test packages

## Step 7 — Output verdict

```markdown
## Pre-flight: PASS / WARN / FAIL

- All criteria traced to requirement chain: YES/NO
- All criteria placed in delivery chain: YES/NO
- No untraced scope: YES/NO
- Dependencies satisfied: YES/NO
- No decision contradictions: YES/NO
- Verification tests cover all criteria: YES/NO
- Regression tests cover all criteria (or explicitly noted as covered by verification): YES/NO

### Recommendation: Proceed / Proceed with modifications / Do not proceed
```

## Step 8 — Quality gates

Run all quality gates after the implementation is complete. All must pass before proceeding to the blind review.

```bash
go build ./...          # Build succeeds
go test ./...           # All tests pass
go vet ./...            # Static analysis clean
golangci-lint run       # Linting — zero warnings
```

If any gate fails, fix the root cause and re-run until clean. Do not move to Step 9 with a failing gate.

## Step 9 — Blind review

**Mandatory. No PR without a completed blind review.**

Launch an isolated agent with no context from the implementation session. The reviewing agent reads the SOL-* solution node, requirement criteria, relevant user journeys, and all changed files fresh.

**What to hand the reviewing agent:**
- The SOL-* (or target) node ID
- The list of changed files
- Instructions to follow the blind review checklist from CLAUDE.md Rule 7 exactly

**The agent checks:**
1. Tests verify actual functionality — not just that code runs
2. Every criterion has regression protection (missing = ISSUE, not suggestion)
3. Every criterion has at least one test with a `// REQ-*.C*:` comment
4. Implementation is complete — no TODOs, deferred work, or partial implementations
5. Strategy is complete — happy path AND edge cases, end-to-end
6. All output formats (text AND JSON) include new fields and handle edge cases
7. Edge cases handled: malformed input, missing data, empty collections, tolerant reader compliance
8. Scope boundaries respected — nothing extra added, nothing required skipped
9. No coupling to proprietary requirement data in code or tests (use synthetic fixture IDs like `REQ-TEST-001`)
10. Code quality: functions do one thing, errors are actionable, no dead code, public API has doc comments
11. User journeys satisfied end-to-end
12. **Property tests present for graph engine packages.** Any package with traversal, aggregation, or serialisation logic must have at least one `rapid.Check` test. Missing property tests in graph packages = ISSUE, not suggestion. If the package is purely CLI glue, note the absence explicitly as a PASS.

**Process:**
1. Launch the blind review agent
2. Categorise every finding as ISSUE, PASS, or SUGGESTION
3. **Auto-apply all obvious fixes** — missing test comments, missing edge-case coverage, missing doc comments, scope-complete additions that the criterion clearly requires. Do not pause for user approval on these; just fix them and note what was changed.
4. **Stop for user decision** only when the fix requires a design choice: e.g. the correct behaviour is ambiguous, two valid approaches have different trade-offs, or a finding suggests the criterion itself may be wrong. Present these findings clearly and wait for direction before proceeding.
5. After all auto-fixes, re-run Step 8 quality gates. Only proceed to Step 10 once gates are clean and no design-decision ISSUEs remain open.

**Rule of thumb:** if a competent engineer would fix it without asking their manager, auto-apply it. If they'd want to talk it through first, stop.

## Step 10 — Record evidence

After quality gates pass and the blind review is clean, invoke `/staircase-evidence` to record verification evidence for all criteria addressed in this slice.

For each criterion covered:
- Method: `test` (for automated test coverage)
- Result: `pass`
- Artifact: the test function name(s) referencing the criterion
- Criterion: the criterion node ID (e.g., `SOL-PARSE-SERDE.C1`)

Run `/staircase-evidence` and confirm evidence nodes are created and linked via `satisfies` before proceeding.

## Step 11 — Create PR

Only after Steps 8–10 are complete, create the pull request.

**Branch naming:** `req/{REQ-ID}/{short-slug}` (or the pattern already used for this branch)

**PR title:** `feat(component): description [REQ-ID.C1, .C2]`

**PR body must include:**

```markdown
## Why
{Motivation — what problem this solves and why now}

## Criteria Resolved
- [x] {ID}.C1 — {criterion text}
- [x] {ID}.C2 — {criterion text}

## Test Evidence
- `go test ./...` passes — N new tests covering above criteria
- `grep -r "{REQ-ID}" *_test.go` shows test traceability

## Test plan
- [ ] Quality gates pass: `go build ./...`, `go test ./...`, `go vet ./...`, `golangci-lint run`
- [ ] Blind review complete — no open ISSUEs
- [ ] Evidence recorded via `/staircase-evidence`
```

Check each PR test plan box before telling the user the PR is ready.

## Step 12 — Close out the cascade

Recording the slice's own evidence (Step 10) can make **parent criteria newly review-ready** and **parent aggregation deliverables newly seal-ready** the moment their cascades complete. Closing those is the slice's true end. A slice that ships evidence but leaves the cascade it completed unclosed is the exact omission that lets a review/seal backlog accumulate — "PR merged" is not "done".

**The trigger is cascade completeness, not the merge.** Do not assume closure waits for `main`. The index on the slice branch already includes the evidence you recorded in Step 10, so the `next` surface on the branch tells you what is closeable right now — but you must ask it about the **specific parents this slice touched**, not the global queue. Trace up from each criterion you just evidenced to its parent deliverable(s), then query each parent **by intent**:

```bash
./engine/staircase build specs/                              # refresh the branch index (Step 10 already does this)
./engine/staircase --format json next <PARENT-ID>            # completion mode: foregrounds this parent's own seal/attest step
# or scope the objective to it:
./engine/staircase --format json next --throughput --scope <PARENT-ID>
```

**Do not check closure with a bare `next --scope` or with the global `next --throughput --top N`.** A bare `next --scope <id>` carries no intent, so it returns a routing **signpost** with zero actions — that emptiness is not "nothing is closeable". And the global `next --throughput` ranks by leverage and bounds to the top-K, so a lower-leverage seal-ready parent (e.g. a task whose seal frees little downstream work) is silently **omitted** from the window — its absence there is not evidence it is unsealed (check `bounds[].omitted`). `staircase tree <PARENT-ID>` reporting `state: seal-pending, kind: seal-ready` is the independent cross-check. Seal-readiness is decided by the parent's own aggregation-criterion cascade being complete — **not** by its `depends-on` siblings being sealed; `depends-on` gates when you can *build* the parent's work, not when you can *seal* it once its criteria are met.

Then decide where closure lands:

- **Fold into THIS slice PR (default when the cascade completes on the branch alone).** If the slice's contributing solution(s) are the only inputs the parent's cascade needed — the common case for a task sliced into a single solution — the parent is already seal-ready on the branch and the merge buys nothing. Attest/seal on the slice branch as a close-out commit and ship it in the same PR (one branch, one PR — not a separate close-out branch). This is what "seal the task when the completing solution lands" means.
- **Defer to an immediate post-merge follow-on (only when other in-flight inputs are still needed).** If the parent's cascade only completes once *other* PRs also merge, you cannot seal on the branch — those inputs are absent. Close out on fresh `main` after the merges (`git checkout main && git pull && ./engine/staircase build specs/`), on a short closure branch shipped via its own PR.

Either way, never push the attest/seal mutations directly to `main` — they ship through a PR like any other graph change, and a pure-graph closure PR still gets the Rule 7 blind review.

For each closeable item:

- **Newly review-ready criteria** (deliverable or requirement) → close each via `/staircase-attest`. Tier 1 (deliverable criterion) is mechanical; Tier 2 (requirement criterion) applies the final-state honesty checks and may legitimately record a finding — leaving the criterion review-ready — rather than attest. Do not attest a requirement criterion just to clear the queue.
- **Newly seal-ready aggregation deliverables** (any non-solution deliverable — `TSK-*` / `MS-*` / `DEL-*` / `RM-*`) whose cascade this slice completed → seal each via `/staircase-seal`. A task is an aggregation deliverable and seals exactly like a milestone or epic — so when a slice's evidence makes the parent **task** cascade-complete (its contributing solution(s) all done), seal the task too. Only the **solution** leaf is never sealed: it closes implicitly via its own `.Cn` criterion attestations above.

Walk leaf-up: attest the criteria first, then seal any deliverable they unblocked, then re-query **each parent by intent** (`next <parent-id>`, not the global queue) to catch a parent that became seal-ready in turn. Stop when no parent this slice touched surfaces a new seal/attest step.

## Key Rules

- **CLI first, always.** Node loading via `staircase show`, chain context via `staircase trace`, dependency coverage via `staircase gaps`. No Grep+Read loops for data loading.
- **Pre-flight runs BEFORE building.** Cheaper to catch problems before writing code.
- **Post-implementation steps are non-negotiable.** Quality gates → blind review → evidence → PR → post-merge closure. No shortcuts.
- **Closure is part of done.** The slice is not finished until every criterion its evidence made review-ready is attested (or honestly left as a finding) and every deliverable its cascade completed is sealed. Skipping Step 12 is how the closure backlog re-accumulates.
- **Blind review is blocking.** No PR without a completed review. Never fabricate user instructions to skip it.
- **Evidence before PR.** Every criterion must have an evidence node before the PR is raised.
- **Output is a build brief, not a report.** The implementing agent should be able to code directly from this output.
- **Both chains checked.** The upward trace surfaces both requirement chain and delivery chain parents from a single call.
- **Criteria are in show output.** `data.criteria` contains all criteria children — no separate glob needed.
- **Decisions are compact in trace output.** `Node.decisions` resolves `justified-by` links inline with `{id, title, chosen, version}`. Call `show <DEC-ID>` for full `text` or `rationale`.
- **Build it properly now.** If something can be solved correctly today, solve it today. Deferring to "future work" or "next slice" is only acceptable when the dependency genuinely does not exist yet — not because it is inconvenient. Lazy implementations that just pass the test but will need to be redone compound into technical debt. Ask: "would I be comfortable shipping this forever?" If no, fix it now.
- **Infrastructure is not scope creep.** Error types, test fixtures, build config are acceptable IF they support a traced capability.
- **Every criterion gets a test.** No exceptions. Both verification (works now) and regression protection (catches future breakage) must be addressed for every criterion.
- **Be honest about match confidence.** HIGH = criterion text directly describes this. MEDIUM = related. LOW = tangential.
- **Flag, don't block, on warnings.** Only FAIL on dependency violations or decision contradictions.
- **Optimistic discovery.** Attempt the canonical invocation first; consult `staircase capabilities <path>` only on failure.
- **Read from `.staircase/index.db`.** The apply pipeline commits projection freshness on `author --confirm`, so the project index reflects the current graph state. The skill never needs a side-car DB.
