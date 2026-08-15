---
name: staircase-validate
description: "Structural health check: schema compliance, cross-reference integrity, link validity, chain boundary enforcement, orphan detection, and coverage gaps. Delegates structural validation, dangling-link detection, chain boundary enforcement, and coverage gap analysis to the canonical staircase CLI; Grep retained only for criterion parent cardinality and orphan detection not yet in the engine."
---

# Validate Graph Health

Answers: **Is the graph structurally healthy?**

This skill is the structural quality gate. Run after every graph change, before `/staircase-review`, and before opening a PR.

The authoritative data source is the Go engine CLI at `./engine/staircase`. Structural validation, link integrity, chain boundary enforcement, and coverage gap analysis are delegated to canonical CLI invocations producing JSON. Grep is used only for the two checks the engine does not yet cover.

## Response shape

Read the whole JSON payload into context — it is self-describing, so take each value together with the inline meaning shipped beside it. See the graph-reads rule in CLAUDE.md.

Per the engine's per-consumer projection mapping, `gaps` returns the leanest **identity tier** (so response size scales with criterion count, not title length); `validate` findings reference nodes by ID, and full prose is available via `show <id>`. Which fields each tier carries is the engine's live contract — read it from `staircase capabilities <command> --format json`, and read the payload raw rather than memorising a field list here.

## Delegated vs Simulated Inventory

| Operation | Mechanism | Rationale |
|-----------|-----------|-----------|
| Schema compliance (required fields, enum values, type registry) | `staircase --format json validate` | Canonical — `internal/validate` is the schema enforcer. |
| Link integrity (dangling targets, deprecated link types, allowed-link-types-per-source) | `staircase --format json validate` | Canonical — same single call. |
| Chain boundary enforcement (absolute — no node may `derives-from` across chains) | `staircase --format json validate` | Canonical — same single call. |
| Coverage gap analysis (gaps / covered / violated, three-state) | `staircase build` + `staircase --format json gaps` | Canonical — `internal/coverage` runs the three-state classifier. |
| Capability discovery on CLI failure | `staircase --format json capabilities [path]` | Canonical — REQ-CLI-001.C5 / SOL-AI-TOOLING-CLI-DELEGATION.C3. |
| Criterion parent cardinality (each criterion has exactly one `criterion-of`) | `Grep` (transitional simulation) | CLI validates that the `criterion-of` target exists, but does not enforce `count == 1`. To absorb under a future `staircase validate` check (engine ticket: criterion cardinality rule). |
| Orphan detection (nodes with no structural links) | `Grep` (transitional simulation) | CLI does not yet build a global incoming-link index. To absorb under the same engine ticket as cardinality, or under a future traversal capability — whichever ships first. |

Every row marked "transitional simulation" is a temporary Grep that will be deleted when the corresponding engine capability ships — per REQ-CANONICAL-ENGINE-001.C2 (same-slice transition). This skill is the registry of what remains to be absorbed.

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

## Step 1 — Run CLI validation

```bash
./engine/staircase --format json validate specs/
```

If the binary does not exist, build it first:

```bash
cd engine && go build -o staircase ./cmd/staircase && cd ..
```

The JSON payload is:

```
{
  "nodes":    <int>,
  "errors":   <int>,
  "warnings": <int>,
  "parse_errors": ["...", ...],                                      // optional, omitted when empty
  "findings":    [{"severity", "node_id", "field", "message"}, ...]  // optional, omitted when empty
}
```

`findings[]` carries every structural issue the CLI found (`severity` is `error` or `warning`). `parse_errors[]` is populated when a `.req.yaml` file could not be parsed at all. A clean graph emits only `{nodes, errors, warnings}` — JSON `omitempty` hides the arrays. Do **not** re-run the command in text mode to see findings; everything is in the JSON.

The CLI covers:
- **Schema compliance** — required fields per node type, enum values (type, status, category, priority, measurement_type, verification, result, method, risk_level), valid types from `.staircase/schema.yaml`
- **Link integrity** — dangling link targets, deprecated link types with migration guidance, allowed link types per source node type
- **Chain boundary enforcement** — chain boundary is absolute; no node may `derives-from` across chains; requirements cannot derive from deliverable criteria; deliverables cannot derive from requirement criteria

Any CLI error means the graph is structurally broken — fix those before running supplemental checks.

## Step 2 — Criterion parent cardinality (transitional simulation)

The CLI validates that each `criterion-of` link points to a real node, but does **not** enforce the cardinality rule that each criterion must have exactly one parent.

Do this in a single bulk Grep, not a per-file loop:

```pseudocode
# One grep gives the criterion-of count for every criterion file.
Grep for `type: criterion-of` across specs/**/*.C*.req.yaml (output_mode: count)
  → files where count == 0: ERROR "orphan criterion — no criterion-of link"
  → files where count >  1: ERROR "criterion has multiple parents — criterion-of must be 1:1"
```

Only Read the offending files (if any) to produce actionable node IDs and field paths.

## Step 3 — Orphan detection (transitional simulation)

Flag nodes with no structural links at all:
- Requirements with no `derives-from`, no `justified-by`, and no incoming `criterion-of` — WARNING (a top-level requirement with no criteria is almost always wrong)
- Deliverables with no `derives-from`, no `targets`, and no `depends-on` — WARNING
- Decisions with no `addresses` and no incoming `justified-by` — WARNING (nothing uses the decision)
- Evidence with no `satisfies` — ERROR (evidence without a criterion claim is invalid)

Build the incoming-link index in one bulk pass, not per-node:

```pseudocode
# One grep builds the full incoming-link index across the whole graph.
Grep for `^\s*- target:` across specs/**/*.req.yaml (output_mode: content, -B 1)
  → parse into a map: target_id → [source_files]

# Walk nodes once; the map lookup is local.
For each non-criterion node file (by type):
  Read file → collect outgoing link types
  incoming = map[node_id] or []
  Apply the type-specific orphan rule above
```

Steps 2 and 3 are independent — issue the two bulk Greps in parallel from a single message.

## Step 4 — Coverage gap analysis (delegated to CLI)

```bash
./engine/staircase --format json gaps
```

Reads from `.staircase/index.db`, which the apply pipeline keeps fresh on every `author --confirm`. If `.req.yaml` files have been edited outside the apply path (manual edits, git pull), run `./engine/staircase build specs/` once first.

The JSON payload is `{status, shape_version, data: {gaps[], covered[], violated[], total}}` (canonical envelope — the coverage report is under `data`). Each gap entry carries `parent_priority` so gaps can be bucketed directly:

- `priority: must` gaps → **critical gap**
- `priority: should` gaps → **significant gap**
- `priority: could` gaps → **minor gap**
- Active `violated[]` → **regression** (always highest priority to fix)

Do **not** grep criteria to compute coverage — the CLI is authoritative.

**Semantic reminder:** `len(covered) + len(violated) + len(gaps) ≠ total`. Criteria with child requirements but no direct evidence are implicitly covered via decomposition and are not in any of the three lists. `implicit = total - (len(covered) + len(violated) + len(gaps))`.

## Step 5 — Report

Combine CLI output with supplemental checks:

```markdown
## Graph Health: PASS / FAIL

### CLI Validation (staircase validate)
- Nodes: N
- Errors: N
- Warnings: N
[List any CLI findings here — severity, node_id, field, message]

### Criterion Cardinality
- Criteria checked: N
- Orphan criteria (0 parents): N
- Multi-parent criteria (>1 parents): N

### Orphan Detection
- Orphaned requirements: N
- Orphaned deliverables: N
- Orphaned decisions: N
- Orphaned evidence: N  (ERROR if >0)

### Coverage Gaps (staircase gaps)
| Priority | Criteria | Direct ev. | Via decomp | Gaps | Violated |
|----------|----------|------------|------------|------|----------|
| must     | N        | N          | N          | N    | N        |
| should   | N        | N          | N          | N    | N        |
| could    | N        | N          | N          | N    | N        |

Implicit (covered via decomposition): N
Total criteria: N

### Overall: PASS (zero errors) / FAIL (N errors)
```

## Step 6 — Suggest fixes

For each error, recommend the fix:
- **Dangling link** (CLI) → "Target doesn't exist. Create with `/staircase-author` or remove the link."
- **Wrong link target type** (CLI) → "Change `derives-from: REQ-X` to `derives-from: REQ-X.C1` — `derives-from` targets a criterion, not a requirement."
- **Deprecated link type** (CLI warning) → "Replace `evidences` with `satisfies`."
- **Missing required field** (CLI) → "Add `measurement_type: binary` to criterion."
- **Chain boundary violation** (CLI) → "Chain boundary is absolute. Restructure the derivation within the same chain, or use a `targets` link for cross-chain planning intent (deliverable → requirement criterion only)."
- **Orphan criterion** (Step 2) → "Add `criterion-of` link to parent, or deprecate if unused."
- **Multi-parent criterion** (Step 2) → "Remove all but one `criterion-of` link — each criterion must have exactly one parent."
- **Orphan evidence** (Step 3) → "Add a `satisfies` link to the criterion this evidence proves, or deprecate the evidence."
- **Critical gap** (Step 4) → "Must-priority criterion with no coverage. Run `/staircase-plan` to add a solution or `/staircase-evidence` if verification already exists."

## Key Rules

- **CLI first, always.** `staircase validate` for structure, `staircase gaps` for coverage. Grep only for the two checks listed in the inventory above.
- **Errors are binary.** Zero errors = PASS, any errors = FAIL.
- **Chain boundary is enforced by the CLI.** No node may `derives-from` across chains — the boundary is absolute. Cross-chain connections use `targets` (planning intent) or attestation (verification via evidence).
- **`satisfies` not `evidences`.** The CLI flags deprecated link types automatically.
- **Optimistic discovery.** Attempt the canonical invocation first; consult `staircase capabilities <path>` only on failure.
- **Never grep for coverage.** Do not grep `satisfies` or `derives-from` links to compute coverage — `staircase gaps` is the authoritative source. Manual cross-reference walks are the anti-pattern this skill replaces.
- **Run after every graph change.** This is the structural quality gate — it is the last check before `/staircase-review` and PR.
- **Read from `.staircase/index.db`.** The apply pipeline commits projection freshness on `author --confirm`, so the project index reflects the current graph state.
