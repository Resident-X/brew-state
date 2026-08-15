---
name: staircase-review
description: "Quality review for requirement nodes: clarity, testability, completeness, link correctness, v3 model compliance including chain boundary rules, and per-discipline authoring guidance (routed through OBL-AUTHORING-DISCIPLINE-001 to the engine-shipped rule data plugins). Reviews single nodes or sets of changes. Delegates node loading and chain traversal to the canonical staircase CLI show, trace, and list commands."
---

# Review Quality

Answers: **Is this node/change good quality?**

Assesses nodes against quality criteria, v3 structural rules (five node types, two chains, chain boundary enforcement), and testability standards. Can review a single node or a batch of recently created/modified nodes.

## Discipline routing

Per-discipline authoring guidance is composed from the engine-shipped tool-config rule data plugins, not from rules embedded in this skill's prose. The operative rule set for each discipline lives in `engine/lint/<discipline>detector/rules.yaml`; the cited DEC carries rationale only. Project-level commitment is recorded by `OBL-AUTHORING-DISCIPLINE-001` (slim compound obligation).

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

The cross-cutting surface lists rule data plugins that apply uniformly across criterion-shaped nodes regardless of parent category. It sits alongside the per-shape table above: when reviewing a criterion, consult the per-shape table for the parent's structural discipline AND every applicable cross-cutting entry below.

| Applicability | Discipline (family ID) | Rationale (DEC) | Rule data plugin |
|---|---|---|---|
| All criterion-shaped nodes regardless of parent category | `graph.criterion_prose_quality` | `DEC-CRITERION-PROSE-QUALITY` | `engine/lint/criterionprosequalitydetector/rules.yaml` |

For every node authored or re-authored in the diff: identify the discipline by matching the node shape against the per-shape table; for criterion-shaped nodes, also collect every cross-cutting entry whose applicability predicate matches. Load each rule data plugin at the listed path, and verify each rule against the drafted text. Flag any violating rule as **ISSUE** in the review verdict and cite the rule ID (e.g., `graph.solution_criterion_authoring.missing_scope_boundary` or `graph.criterion_prose_quality.title_body_separation`) plus the rule's after-shape advice.

**No rule text is duplicated into this skill.** The data plugins are the operative source — read them when needed. The DECs are cited for rationale only. Discipline keys above match the family identifiers from `./engine/staircase lint --families --format json`; if the tables drift from the registry, the registry is authoritative.

The authoritative data source is the Go engine CLI at `./engine/staircase`. Node loading, chain traversal, and discovery of draft nodes are delegated to canonical CLI invocations producing JSON. See REQ-CANONICAL-ENGINE-001.C5.

## Response shape

Read the whole JSON payload into context — it is self-describing, so take each value together with the inline meaning shipped beside it. See the graph-reads rule in CLAUDE.md.

Graph-query commands emit per-consumer projection tiers registered in `typebehaviour`. `gaps` returns the leanest **identity tier** (so response size scales with criterion count, not title length); `trace`, `summary`, `query`, `list`, and the resolved link-target blocks of `show` return the **compact tier** (identity plus a few type-specific state fields); only `show`'s primary subject emits full prose (`text`, `rationale`, link narrative, and criteria children). Which fields each tier carries is the engine's live contract — read it from `staircase capabilities <command> --format json`, and read the payload raw rather than memorising a field list here.

## Delegated vs Simulated Inventory

| Operation | Mechanism | Rationale |
|-----------|-----------|-----------|
| Load node (all scalar fields, resolved links, criteria children) | `staircase show <id> --format json` | Canonical — single call returns everything; no secondary file reads needed. |
| Trace upward (parent requirements, decisions) | `staircase trace <id> --direction up --format json` | Canonical — resolves full ancestry; decisions inline as compact `{id, title, chosen, version}`. |
| Trace downward (dependents, evidence at criteria) | `staircase trace <id> --direction down --format json` | Canonical — walks the decomposition tree to evidence. |
| Find all draft nodes (batch review) | `staircase list --status draft --format json` | Canonical — filtered enumeration by status. |
| Structural validation (link integrity, chain boundaries, schema) | `staircase --format json validate specs/` | Canonical — structural errors identified by CLI are authoritative. |
| Capability discovery on CLI failure | `staircase --format json capabilities [path]` | Canonical — REQ-CLI-001.C5 / SOL-AI-TOOLING-CLI-DELEGATION.C3. |

All operations are delegated. No transitional simulation Greps remain in this skill.

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

- `$0` — What to review: a node ID, a comma-separated list of IDs, or `recent` (review all draft nodes).

## Step 0 — Confirm the binary exists

The skill reads from `.staircase/index.db`, which the apply pipeline keeps fresh on every `author --confirm`. No pre-step is required.

If the binary does not exist, build it first:

```bash
cd engine && go build -o staircase ./cmd/staircase && cd ..
```

If `.req.yaml` files have been edited outside the apply path (manual edits, git pull), run `./engine/staircase build specs/` once to refresh the index.

## Step 1 — Load the target(s)

**Single node:**

```bash
# Full node detail: all scalar fields, outgoing links with resolved titles, criteria children
./engine/staircase show <ID> --format json

# Full chain context: upward to roots (why?), downward to evidence (what proves this?)
./engine/staircase trace <ID> --format json
```

Run both calls in parallel — they are independent.

The `show` response includes:
- `data.links` — all outgoing links as `{type, target: <compact node projection>}`. Link types and target titles/IDs are inline; for full target prose call `show <LINKED-ID>`.
- `data.criteria` — all criterion children with `id`, `title`, `measurement_type`. No separate glob needed.

The `trace` response includes:
- `data.up.decisions` — compact decisions (`{id, title, chosen, version}`) resolved from `justified-by` links inline at each ancestor node. Call `show <DEC-ID>` for full `text` or `rationale`.
- `data.down` — the full decomposition tree down to evidence.

**Batch (`recent` or list):**

```bash
./engine/staircase list --status draft --format json
```

This replaces the prior `Grep ^status: draft$` scan. The response is an array of compact rows `{id, title, type, category, status}`. Load full detail for each via `show` and `trace` calls issued in parallel.

## Step 2 — Run structural validation

```bash
./engine/staircase --format json validate specs/
```

Any CLI findings (`errors[]` or `warnings[]`) apply to all nodes under review. CLI structural errors (broken links, chain boundary violations, wrong link types) must be fixed before the quality review can pass.

## Step 3 — Assess each node

Cite specific text from the `show` output. See [review-criteria.md](references/review-criteria.md) for detailed quality standards.

**For requirements:**
- **Clarity** — Could two engineers interpret it differently? Flag "appropriately", "properly", "correctly".
- **Completeness** — Required fields present? Rationale explains why? Correct category?
- **Links** — `derives-from` in `data.links` targeting a **criterion** (not requirement/deliverable)? `justified-by` targeting a decision?
- **Criteria** — `data.criteria` non-empty? Each criterion has `criterion-of` back-link (confirmed by non-empty `data.criteria` in show output).
- **Chain boundary** — All requirements derive from requirement criteria only. Check `data.links` `derives-from` targets: IDs matching RM-*.C*, MS-*.C*, DEL-*.C* are delivery-chain criteria and are a chain boundary violation.

**For deliverables:**
- **Category** — Correct category (roadmap, milestone, epic, task)?
- **State predicate** — Milestones describe verifiable states, not tasks?
- **Links** — `derives-from` in `data.links` targeting deliverable criteria? `targets` pointing to requirement criteria?
- **Criteria** — Roadmap criteria are phases? Milestone criteria are state predicates?
- **Chain boundary** — Deliverables only derive from deliverable criteria (IDs matching RM-*.C*, MS-*.C*, DEL-*.C*).

**For criteria:**
- **Testability** — Can you write a concrete test assertion? Flag vague predicates.
- **Measurement type** — Correct? (binary, threshold, rate, periodic)
- **Single parent** — Exactly one `criterion-of` link in `data.links`?
- **Parent type** — `criterion-of` target is a requirement OR deliverable (not another criterion)?
- **Not a behaviour** — Criteria are testable properties, not scenario steps.

**For decisions:**
- **Options** — At least 2 alternatives considered?
- **Rationale** — Trade-off explained, not just "it's better"?
- **Addresses** — Links to what it informs?
- **Category** — assumption needs `validation_horizon`, risk needs `risk_level` and response strategy?

**For evidence:**
- **Method** — Appropriate strength? (test > demonstration > analysis > inspection)
- **Result** — pass or fail, not ambiguous?
- **Temporal** — `observed_at` set? `valid_until` if applicable?
- **Artifact** — Reference to what was tested/analysed?
- **Link** — Exactly one `satisfies` link to a criterion in `data.links`?

**For solutions (type: deliverable, category: solution):**
- **Rich text** — Architectural approach described thoroughly?
- **Delivery chain linked** — `derives-from` in `data.links` includes deliverable criteria (MS-*.C*, DEL-*.C*)? (Error if missing)
- **Requirement intent expressed** — `targets` in `data.links` reference requirement criteria (REQ-*.C*, SN-*.C*)? (Warning if missing — planning intent should be stated)
- **Justified-by** — Non-obvious approach linked to a decision in `data.links`? Decision resolved with `title` via show.
- **Test-spec criteria** — `data.criteria` entries are close to test assertions?

**For journeys (category: journey):**
- **Scenario format** — Cockburn-style main success scenario with extensions?
- **Criteria are properties** — "Search returns results within 200ms" not "user clicks search"?
- **Extensions explored** — Each step has "what could go wrong?"?

## Step 4 — Output findings

```markdown
## Review: {ID} — PASS / NEEDS WORK / FAIL

### Findings

| # | Severity | Field | Issue | Suggested Fix |
|---|----------|-------|-------|---------------|
| 1 | ERROR | links | derives-from targets REQ-X (requirement, not criterion) | Change to REQ-X.C1 |
| 2 | ERROR | links | requirement derives-from deliverable criterion | Chain boundary violation — restructure within requirement chain or use `targets` for planning intent |
| 3 | WARNING | rationale | Missing — no explanation of why | Add rationale block |
| 4 | INFO | text | Could be more specific: "handles errors" | "Returns error containing file path and line number" |

### Verdict: PASS / NEEDS WORK / FAIL
- PASS: No errors, <=2 warnings
- NEEDS WORK: 1+ warnings that affect quality
- FAIL: Any structural errors (broken links, missing required fields, v3 violations, chain boundary violations)
```

For batch reviews, present a summary table then details per node.

## Key Rules

- **CLI first, always.** Node loading via `staircase show`, chain context via `staircase trace`, draft discovery via `staircase list --status draft`, structural checks via `staircase validate`. No Grep+Read loops.
- **Cite the node text.** Don't say "unclear" without quoting what's unclear — it's in `show` output.
- **Concrete rewrites.** Don't just flag problems — suggest the specific fix.
- **v3 structural rules are errors, not warnings.** `derives-from` targeting a requirement instead of a criterion is always FAIL. Chain boundary violations are always FAIL.
- **Testability is non-negotiable for criteria.** If you can't write a test for it, it fails.
- **Delivery chain for solutions.** Solutions must have `derives-from` to a deliverable criterion — flag as ERROR if missing. Check `data.links` for `targets` links to requirement criteria (WARNING if absent — planning intent should be stated).
- **Review against the criterion text, not your assumptions.** The criterion says what it says.
- **CLI structural validation first.** Run `staircase validate` before the quality review — fix structural errors before assessing quality.
- **Optimistic discovery.** Attempt the canonical invocation first; consult `staircase capabilities <path>` only on failure.
- **Read from `.staircase/index.db`.** The apply pipeline commits projection freshness on `author --confirm`, so the project index reflects the current graph state.
