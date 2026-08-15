---
name: staircase-author
description: "Creates, updates, or deprecates any graph node (requirement, deliverable, criterion, evidence, decision). Handles ID generation, file placement, link wiring, validation, and applies per-discipline authoring guidance (routed through OBL-AUTHORING-DISCIPLINE-001 to the engine-shipped rule data plugins). Use when making changes to the requirement graph."
allowed-tools: "Read Write Edit Glob Grep Bash"
---

# Author Graph Nodes

Answers: **Create/update/deprecate this node in the graph.**

This is the only skill that writes `.req.yaml` files. It handles all five node types, ID generation, directory placement, link wiring, and validation.

## Discipline routing

Authoring guidance per discipline is composed from the engine-shipped tool-config rule data plugins, not from rules embedded in this skill's prose. The operative rule set for each discipline lives in `engine/lint/<discipline>detector/rules.yaml`; the cited DEC carries rationale only. Project-level commitment is recorded by `OBL-AUTHORING-DISCIPLINE-001` (slim compound obligation).

| Node shape | Discipline (family ID) | Rationale (DEC / OBL) | Rule data plugin |
|---|---|---|---|
| Criterion of solution | `graph.solution_criterion_authoring` | `DEC-SOLUTION-AS-BUILD-BRIEF` | `engine/lint/solutioncriteriondetector/rules.yaml` |
| Criterion of milestone or epic | `graph.milestone_criterion_authoring` | `DEC-MILESTONE-CRITERION-AS-DONE-WHEN` | `engine/lint/milestonecriteriondetector/rules.yaml` |
| Criterion of roadmap | `graph.roadmap_criterion_authoring` | `DEC-ROADMAP-PHASE-SHAPE` | `engine/lint/roadmapcriteriondetector/rules.yaml` |
| Criterion of requirement | `graph.implementation_leak` | `OBL-AUTHORING-DISCIPLINE-001` (rationale: `DEC-GRAPH-AUTHORING-DISCIPLINE`) | `engine/lint/leakdetector/rules.yaml` |
| Criterion of attested delivery-chain deliverable | `graph.delivery_chain_immutability` | `OBL-DELIVERY-CHAIN-IMMUTABILITY-001` (rationale: `DEC-DELIVERY-CHAIN-IMMUTABILITY`) | `engine/lint/deliverychainimmutabilitydetector/rules.yaml` |
| Decision node | `graph.decision_authoring` | `DEC-DECISIONS-ADR-SHAPE` | `engine/lint/decisiondetector/rules.yaml` |
| Evidence node | `graph.evidencing_pattern_compliance` | `DEC-EVIDENCE-PATTERNS` | `engine/lint/evidencepatterndetector/rules.yaml` |
| Epic deliverable | `graph.epic_cohesion` | `DEC-EPIC-COHESION-RULE` | `engine/lint/epiccohesiondetector/rules.yaml` |
| Persona requirement | `graph.persona_authoring` | `DEC-PERSONA-SHAPE` | `engine/lint/personadetector/rules.yaml` |
| Journey requirement | `graph.journey_authoring` | `DEC-JOURNEY-SHAPE` | `engine/lint/journeydetector/rules.yaml` |

### Cross-cutting routing

The cross-cutting surface lists rule data plugins that apply uniformly across criterion-shaped nodes regardless of parent category. It sits alongside the per-shape table above: when authoring or re-authoring a criterion, consult the per-shape table for the parent's structural discipline AND every applicable cross-cutting entry below.

| Applicability | Discipline (family ID) | Rationale (DEC) | Rule data plugin |
|---|---|---|---|
| All criterion-shaped nodes regardless of parent category | `graph.criterion_prose_quality` | `DEC-CRITERION-PROSE-QUALITY` | `engine/lint/criterionprosequalitydetector/rules.yaml` |

**Workflow integration** for create / update operations:

1. Draft the node's text and (for criteria) the criterion's text.
2. Identify the discipline by matching the node shape against the per-shape routing table above.
3. For criterion-shaped nodes, also collect every cross-cutting entry whose applicability predicate matches.
4. Read each rule data plugin at the listed paths; apply each rule's advice and before/after examples to the drafted text.
5. If any rule's predicate would fire on the draft, revise to the rule's after-shape; re-check.
6. Proceed to the CLI delegation step with the disciplined text.

**No rule text is duplicated into this skill.** The data plugins are the operative source — read them when needed. The DECs are cited for rationale only. Discipline keys above match the family identifiers from `./engine/staircase lint --families --format json`; if the tables drift from the registry, the registry is authoritative.

The authoritative data source is the Go engine CLI at `./engine/staircase`. Create, update, and deprecate operations are all delegated to canonical CLI invocations. The reasoning layer (ID generation, directory lookup, field decisions) is unchanged — only the write mechanism is delegated. See REQ-CANONICAL-ENGINE-001.C7.

## Delegated Inventory

| Operation | Mechanism | Rationale |
|-----------|-----------|-----------|
| create | Delegated — `staircase author create --confirm` | Canonical — `internal/mutation` handles file writing, schema validation, and link integrity. Layer A (ID generation, directory lookup) retained in skill. |
| update | Delegated — `staircase author update --confirm` (patch mode is default) | Canonical — patch semantics preserve unspecified fields. Use `--add-link` / `--remove-link` for link edits without rewriting the full link list. Use `--full` only when explicitly replacing every field. |
| deprecate | Delegated — `staircase author deprecate --confirm` | Canonical. Retiring a **bound contributor** (a deliverable sourcing `derives-from` edges into active aggregation criteria) is an atomic resolve-or-reject act per DEC-CONTRIBUTOR-BINDING-INTEGRITY: the engine fails the mutation closed and lists each unresolved edge with the exact flag to add (`--reanchor <crit>=<successor>`, `--close <crit>`, or `--keep <crit>`). Deprecating a non-contributor stays a plain status flip. |
| supersede | Delegated — `staircase author supersede --id <id> --with <successor> --confirm` | Canonical. Retires `<id>` in favour of `<successor>`: deprecates it, records the `supersedes` link from the successor, and resolves every sourced edge with the same `--reanchor/--close/--keep` flags — all in one fail-closed batch. Use this instead of deprecating and hand-adding a `supersedes` link via a separate update. |
| validate | Delegated — `staircase validate --format json specs/` | Canonical — `internal/validate` is the schema enforcer; it also fails on any orphaned retired-contributor edge. |

Every operation runs through the engine. There are no remaining simulation rows in this skill — the absorption obligation under REQ-CANONICAL-ENGINE-001.C2 is satisfied for the author surface.

## Actor identity on every mutation

Every create / update / deprecate / supersede records an **actor** on the mutation envelope and on every event it produces (REQ-MUTATION-ACTOR-001, DEC-MUTATION-ACTOR-IDENTITY). Supply it deliberately — the audit trail's WHO depends on it. Resolution precedence is:

1. **`--actor <id>`** — the caller names the actor for this invocation (recorded as `explicit`). Pass it when authoring on behalf of a specific operator, service account, or workflow.
2. **`default_actor` in `.staircase/config.yaml`** — the project's declared default operator, used when `--actor` is absent (recorded as `config-resolved`, no warning). Set this once for a solo project so routine authoring carries a real identity without a per-call flag:

   ```yaml
   # .staircase/config.yaml
   default_actor: alice
   ```

3. **operating-system user** — the last-resort fallback when neither is supplied (recorded as `system-fallback`, with a one-line stderr warning so the implicit choice is visible). Treat the warning as a prompt to set `--actor` or `default_actor`, not as normal steady state.

The `actor.type` value set is a schema-declared vocabulary (`actor_types:` in `schema.yaml`); a project extends it additively there, exactly as it extends `statuses` or `seal_outcomes`.

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

- `$0` — Action: `create`, `update`, `deprecate`, or `supersede`
- `$1` — For create: node type and title. For update/deprecate/supersede: node ID.
- Remaining args — field overrides or description of changes

## Create Mode

### 1. Determine target directory

| Type + Category | Directory |
|----------------|-----------|
| `requirement` + `obligation` | `specs/obligations/` |
| `requirement` + `persona-goal` | `specs/personas/` |
| `requirement` + `journey` | `specs/journeys/` |
| `deliverable` + `solution` | `specs/solutions/` |
| `requirement` + `functional` (or strategic, constraint, interface) | `specs/requirements/` |
| `deliverable` (any category: roadmap, milestone, epic, task) | `specs/deliverables/` |
| `criterion` | Same directory as parent node |
| `decision` | `specs/decisions/` |
| `evidence` | `specs/evidence/` |

### 2. Read `_document.yaml` in target directory for the prefix.

### 3. Generate ID

- Requirements: `PREFIX-SLUG-NNN` — Glob `*.req.yaml` in directory, find highest sequence, increment
- Solutions: `SOL-SLUG` — descriptive slug (e.g., `SOL-PARSE-SERDE`)
- Deliverables: prefix from `_document.yaml` + slug (e.g., `RM-ENGINE-2026`, `MS-INC-1`, `DEL-PARSER`)
- Criteria: `{PARENT-ID}.C{N}` — Grep for existing `.C{N}` files for this parent, increment
- Decisions: `DEC-SLUG` — descriptive slug
- Evidence: `EVD-{CRITERION-ID}-{METHOD}` — e.g., `EVD-REQ-PARSE-001.C1-TEST`

### 4. Read `.staircase/schema.yaml` for required fields and allowed values.

### 5. Prepare field content

See `docs/conventions.md` for complete format examples. See [link-type-guide.md](references/link-type-guide.md) for all 13 link types and chain boundary rules. The skill determines the correct field values; the CLI writes the file.

**All nodes:**
- `text` and `rationale` should be written to temporary files for `--text-file` / `--rationale-file` flags (avoids shell quoting issues with block scalars)
- `status` defaults to `active`, `version` defaults to `1`

**Requirements:**
- `priority`: must, should, could, wont
- `category`: functional, journey, obligation, persona-goal, strategic, constraint, interface
- Links: `derives-from` targeting a parent **criterion** (not requirement); `justified-by` targeting a decision

**Solutions** (`type: deliverable, category: solution`):
- `text` describes the architectural approach thoroughly
- Links: `derives-from` targeting deliverable criteria (delivery chain); `targets` linking to requirement criteria (planning intent, cross-chain)
- `justified-by` targeting the decision explaining the approach
- Criteria are test specifications

**Deliverables:**
- `category`: roadmap, milestone, epic, or task
- `priority` is optional (ordering comes from `depends-on` and roadmap phases)
- Links:
  - `derives-from` targeting deliverable criteria (within delivery chain)
  - `targets` targeting requirement criteria (planning intent — cross-chain, not `derives-from`)
  - `depends-on` for sequencing
  - `justified-by` for rationale

**Criteria:**
- `text`: testable predicate
- `measurement_type`: binary, threshold, rate, or periodic
- `verification`: test, demonstration, analysis, or inspection
- Links: exactly one `criterion-of` targeting the parent node

**Decisions:**
- `options_considered`: list of alternatives (at least 2)
- `chosen`: the selected option
- Links: `addresses` targeting the criterion or decision it informs
- For risks: `risk_level` (CLI flag: `--risk-level`). Note: `mitigation`, `mitigation_milestone`, and `expires` are schema fields but have no CLI flags yet — use Update Mode (Edit-in-place) to set these after creation.
- For assumptions: `validation_horizon` (CLI flag: `--validation-horizon`)

**Evidence:**
- `method`: test, demonstration, analysis, inspection, or federated
- `result`: pass or fail
- `observed_at`: ISO timestamp
- `valid_until`: expiry hint (e.g., `until-superseded`, `2026-09-01`)
- `observation_window`: observation window description (CLI flag: `--observation-window`)
- `artifact`: URI or path to the external artifact (CI URL, file path, doc URL)
- `status`: active, resolved, expired, or superseded (NOT draft/approved/deprecated)
- Links: `satisfies` targeting exactly one criterion

### 6. Delegate to CLI

Write text and rationale to temp files, then call the engine:

```bash
# Write long-form fields to temp files
echo "$TEXT_CONTENT" > /tmp/node-text.txt
echo "$RATIONALE_CONTENT" > /tmp/node-rationale.txt

# Create the node
./engine/staircase author create \
  --id <id> \
  --type <type> \
  --title "<title>" \
  --category <category> \
  --text-file /tmp/node-text.txt \
  --rationale-file /tmp/node-rationale.txt \
  --priority <priority> \
  --link <target>:<link-type> \
  --link <target>:<link-type> \
  --confirm \
  --format json
```

If the binary doesn't exist, build it first:

```bash
cd engine && go build -o staircase ./cmd/staircase && cd ..
```

The CLI handles file writing, schema validation, and link integrity checks. The skill does NOT write `.req.yaml` files directly for create operations — no Write tool, no Edit tool, no heredoc YAML construction.

**Criteria** use the same `author create` command with criterion-specific flags:

```bash
./engine/staircase author create \
  --id <PARENT-ID>.C<N> \
  --type criterion \
  --title "<testable predicate>" \
  --text-file /tmp/criterion-text.txt \
  --measurement-type binary \
  --verification test \
  --link <PARENT-ID>:criterion-of \
  --confirm \
  --format json
```

**Evidence** nodes:

```bash
./engine/staircase author create \
  --id EVD-<CRITERION-ID>-<METHOD> \
  --type evidence \
  --title "<description>" \
  --method <method> \
  --result <pass|fail> \
  --observed-at <ISO-timestamp> \
  --valid-until <expiry> \
  --artifact "<URI>" \
  --link <CRITERION-ID>:satisfies \
  --confirm \
  --format json
```

### 7. Run validation

Run the CLI validator to confirm the graph remains structurally sound:

```bash
./engine/staircase validate --format json specs/
```

The CLI checks: required fields, enum values, link type validity, dangling targets, chain boundaries, and deprecated link types.

If the CLI reports errors, fix them before completing. If it reports zero errors, the structural validation passes.

## Update Mode

Update is delegated to the CLI in patch mode (the default). Only fields supplied via flags are changed; every other field — including unspecified scalars, the rationale, links not named via `--add-link` / `--remove-link`, criteria children, and the version increment — is preserved by `internal/mutation`.

```bash
./engine/staircase author update --id <id> \
  --title "<new title>" \
  --text-file /tmp/new-text.txt \
  --add-link <target>:<link-type> \
  --remove-link <old-target>:<link-type> \
  --confirm --format json
```

Use `--text-file` and `--rationale-file` rather than inline `--text` / `--rationale` when the content uses YAML block scalars or contains shell-significant characters — the temp-file path avoids quoting issues.

**Link edits.** Prefer `--add-link` / `--remove-link` to nudge the link list without rewriting it. Use `--link` (replaces the entire link list) only when intentionally rewriting all links.

**Full overwrite.** Pass `--full` only when explicitly replacing every field (rare — usually a sign you should use `create` and `deprecate` separately). Patch mode is the right default.

**Validation.** The CLI runs schema and link integrity checks during the preview step. Any failures appear in the preview output and the change is not applied unless `--confirm` is given AND the preview is clean. Re-run `./engine/staircase validate --format json specs/` afterward to confirm the broader graph still passes.

## Deprecate / Supersede Mode

Both are delegated to the CLI. Plain deprecation marks the node `status: deprecated`:

```bash
./engine/staircase author deprecate --id <id> --confirm --format json
```

**Retiring a bound contributor is fail-closed.** When `<id>` is a deliverable that
sources `derives-from` edges into active aggregation criteria, the engine refuses the
mutation unless every such edge is resolved in the same call, and lists each unresolved
edge with the exact flag to copy (per DEC-CONTRIBUTOR-BINDING-INTEGRITY). Do not try to
pre-empt this by hand — run the bare command, read the rejection, and add the flag the
engine names:

- `--reanchor <crit>=<successor>` — repoint the contribution to a live successor (the
  successor must be an active deliverable; the engine adds the `derives-from` edge on it).
- `--close <crit>` — retire the parent criterion in the same op.
- `--keep <crit>` — leave the edge; admissible only when another active contributor remains.

**Supersession** is its own operation — prefer it over deprecating and hand-adding a
`supersedes` link separately. It deprecates `<id>`, records the `supersedes` link from the
successor, and carries the same edge resolutions, all atomically:

```bash
./engine/staircase author supersede --id <id> --with <successor> \
  --reanchor <crit>=<successor> --reason "<why>" --confirm --format json
```

Deliverable retirement also emits `retirement` + `re-anchor` lifecycle events; a re-run on an
already-retired, already-resolved node is a clean no-op. A `--reason` is required.

After retiring, run validation — it fails on any orphaned retired-contributor edge:

```bash
./engine/staircase validate --format json specs/
```

## Key Rules

- `derives-from` targets **criteria**, never requirements or deliverables directly
- `satisfies` replaces `evidences` — update any v2 files using the old name
- `criterion-of` is many:1 — each criterion has exactly one parent
- `targets` is deliverable → requirement criterion only (not deliverable criteria)
- `derives-from` is strictly within-chain — chain boundary is absolute, no exceptions
- Decisions must exist before requirements/deliverables that `justified-by` them
- IDs use the prefix from `_document.yaml` — never invent prefixes
- Always run CLI validation after changes
- **All mutations via CLI** — `./engine/staircase author create|update|deprecate|supersede --confirm` for writes, `./engine/staircase validate --format json specs/` for validation. The skill never writes `.req.yaml` files directly; the engine owns the mutation surface.
- **Supply the actor deliberately** — pass `--actor <id>`, or set `default_actor` in `.staircase/config.yaml` once, so mutations record a real identity rather than the OS-user `system-fallback`. See *Actor identity on every mutation* above.
