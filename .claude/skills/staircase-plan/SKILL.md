---
name: staircase-plan
description: "Level-aware planning: creates top-level roadmaps from a bare graph, decomposes phases into milestones, or (at the slice level) hands off to the /staircase-wf router which drives WF-SLICE to decompose milestones into solution leaves. Detects what exists and starts at the right level. Delegates graph reads and scope queries to the canonical staircase CLI show, list, trace, summary, and gaps commands."
---

# Plan

Answers: **How do we build this? Break it down.**

A single planning skill that adapts to where you are in the delivery hierarchy. It detects what exists and starts at the right level — from strategic roadmapping down to solution slicing. Planning creates **deliverable** nodes (type: deliverable) in `specs/deliverables/` with `targets` links expressing delivery intent toward requirement criteria.

The authoritative data source for graph shape, scope overview, and chain traversal is the Go engine CLI at `./engine/staircase`. See REQ-CANONICAL-ENGINE-001.C5. Read the whole JSON payload into context — it is self-describing, so take each value together with the inline meaning shipped beside it. See the graph-reads rule in CLAUDE.md.

## Delegated vs Simulated Inventory

| Operation | Mechanism | Rationale |
|-----------|-----------|-----------|
| Graph shape: counts by type, category, status | `staircase summary --format json` | Canonical — ByType, ByCategory, ByStatus breakdown with optional scope. |
| List deliverables by category (roadmap, milestone, epic, solution) | `staircase list --type deliverable --format json` | Canonical — filtered enumeration of all matching nodes; solutions are `type: deliverable, category: solution` so they appear in this result. |
| Load individual node (with criteria and resolved links) | `staircase show <id> --format json` | Canonical — single call returns all fields, links, criteria children. |
| Scope context: what derives from a phase criterion | `staircase trace <id> --direction down --format json` | Canonical — walks criterion-of / derives-from downward, returning child requirements and milestones. |
| Milestone coverage (gaps / covered / violated) | `staircase --format json gaps --scope <ms-id>` | Canonical — three-state classifier scoped to a subtree. |
| Load requirement nodes for theme grouping | `staircase list --type requirement --format json` | Canonical — returns all requirements as compact rows; load details via `show` on demand. |
| Validate created links exist | `staircase --format json validate specs/` | Canonical — structural validation confirms all link targets resolve. |
| Capability discovery on CLI failure | `staircase --format json capabilities [path]` | Canonical — REQ-CLI-001.C5 / SOL-AI-TOOLING-CLI-DELEGATION.C3. |
| Active run detection for a workflow (e.g. WF-PLAN) | `staircase wf runs list --workflow <id> --format json` | Canonical — SOL-WF-RUNS-QUERY. Use this for run state discovery; never query the substrate directly. |
| Priority distribution (must / should / could) | `Grep` (transitional simulation) | CLI does not yet expose per-priority counts. Absorbs into `staircase summary` when priority breakdown is added to the summary command. |
| Planning coverage: which deliverables `targets` a criterion (reverse link cross-reference) | `staircase links <criterion-id> --type targets --direction inbound --format json` | Canonical — one-hop reverse link-relationship query; SOL-LINKS-COMMAND. |
| Roadmap/milestone listing for delivery chain mapping | `staircase list --type deliverable --format json` + `staircase show` on demand | Canonical — list returns IDs; show loads files only when needed. |

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

## Arguments

- `$0` — (optional) Scope:
  - No arg → assess current planning state and recommend
  - Feature keyword → find and decompose that area
  - Roadmap phase criterion ID (e.g., `RM-*.C2`) → decompose that phase into milestones
  - Milestone ID (e.g., `MS-*`) → decompose into solutions
- `$1` — (optional) Depth: `quick` (scope + sequencing), `standard` (full decomposition with nodes), `deep` (multi-perspective analysis + web research). Default: `standard`.

## Step 0 — Confirm the binary exists

The skill reads from `.staircase/index.db`, which the apply pipeline keeps fresh on every `author --confirm`. No pre-step is required.

If the binary does not exist, build it first:

```bash
cd engine && go build -o staircase ./cmd/staircase && cd ..
```

If `.req.yaml` files have been edited outside the apply path (manual edits, git pull), run `./engine/staircase build specs/` once to refresh the index.

## Level Detection

Before planning, detect what exists using a single summary call plus a list call:

```bash
# Graph shape: counts by type and category
./engine/staircase summary --format json

# Delivery structure: IDs and categories of all deliverables
./engine/staircase list --type deliverable --format json

# Solution listings (solutions are type: deliverable, category: solution — included in deliverable list above)
./engine/staircase list --type deliverable --category solution --format json
```

Run these three calls in parallel — they are independent. The `summary` JSON has `data.counts.by_category` — use the `deliverable` category breakdown to identify roadmap, milestone, and epic counts. The `list` response gives the actual IDs.

| What exists | What's missing | Auto-level |
|---|---|---|
| Requirements only | Roadmap, milestones, solutions | **Strategic** — create top-level roadmap |
| Roadmap + phases | Milestones for target phase | **Tactical** — decompose phase into milestones |
| Milestones | Solutions for target milestone | **Slice** — hand off to the `/staircase-wf` router, which drives WF-SLICE to decompose into solution leaves |
| Everything | Nothing | **Done** — report status, recommend `/staircase-build` |
| Everything | User says "replan" or "start fresh" | **Replan** — deprecate old delivery artifacts, create replacements |

If $0 specifies a scope, use it. Otherwise, detect and recommend.

## Two Chains in Planning

Planning operates primarily in the **delivery chain** but must reference the **requirement chain**:

- **Deliverables** (RM-*, MS-*, DEL-*) are `type: deliverable` in `specs/deliverables/`
- **`targets` links** express planning intent: deliverable → requirement criterion
- **Solutions** (SOL-*) are `type: deliverable, category: solution` — in the delivery chain
- Solutions `derives-from` deliverable criteria (within delivery chain); `targets` links express intent toward requirement criteria

## Replan Mode (replacing existing delivery artifacts)

### 1. Assess what's being replaced

```bash
# Load roadmap nodes — --all-statuses because replan needs deprecated roadmaps being replaced
./engine/staircase list --type deliverable --category roadmap --all-statuses --format json
# Then load each for full detail (show is exempt from status filtering)
./engine/staircase show <RM-ID> --format json

# Trace down from roadmap phase criteria to find milestones
# --all-statuses because deprecated milestones/solutions are what's being replaced
./engine/staircase trace <RM-CRITERION-ID> --direction down --all-statuses --format json
```

### 2. Preserve what's still valid

Evidence survives replanning — it links to requirement criteria, not delivery artifacts.
- **Requirement criteria unchanged?** → evidence still valid, delivery can change freely
- **Requirement criteria changed?** → flag affected evidence for re-verification

Identify reusable nodes from the trace output — solutions and milestones whose purpose still holds under new phasing.

### 3. Deprecate replaced nodes

Use `/staircase-author deprecate {ID}` for each replaced node. Process bottom-up: solutions first, then epics, then milestones, then roadmap phases.

### 4. Validate no orphans

After replanning:
```bash
./engine/staircase --format json validate specs/
```

Any dangling link targets will appear in the `findings[]` array.

## Strategic Level (no roadmap, or full replan)

### 1. Load the full graph landscape

```bash
# Graph overview: type/category/status counts + top gaps
./engine/staircase summary --format json

# All requirements (for theme grouping)
./engine/staircase list --type requirement --format json

# Decisions (for constraints)
./engine/staircase list --type decision --format json
```

Run in parallel. For the requirement list, load full detail for representative lead nodes (`show <id>`) rather than every node — start with one per prefix cluster.

**Priority distribution (transitional simulation):** The CLI does not yet expose per-priority counts. Issue in parallel:
```pseudocode
Grep ^priority: must$   across specs/**/*.req.yaml (output_mode: count)
Grep ^priority: should$ across specs/**/*.req.yaml (output_mode: count)
Grep ^priority: could$  across specs/**/*.req.yaml (output_mode: count)
```
These three Greps will be removed when `staircase summary` includes priority breakdown.

**If >20 requirements in scope:** Follow [PROGRESSIVE-DISCOVERY.md](PROGRESSIVE-DISCOVERY.md) before proceeding.

### 2. Group into themes

Cluster requirements by:
- ID prefix (REQ-PARSE-*, REQ-EVID-*, etc.) — visible in list output
- Shared dependencies — visible via `show` on representative nodes
- Persona alignment — filter list by category persona-goal
- Journey coverage — filter list by category journey

### 3. Sequence into phases

Order by:
1. **Dependency** — can't build B before A if B depends on A
2. **Priority** — must before should (but dependency overrides)
3. **Leverage** — phases unblocking the most downstream work go first
4. **Risk** — uncertain or complex phases earlier (fail fast)
5. **Dogfooding** — phases that let you use the tool on itself

### 4. Generate competing approaches (depth=deep only)

Produce 2-4 distinct phasing strategies. Score from perspectives:

| Perspective | Weight | Focus |
|------------|--------|-------|
| Developer (PER-DEVELOPER) | 1.5x | Fast setup, CLI/MCP, low ceremony |
| AI Agent (PER-AI-BUILDER) | 1.5x | Structured data, context efficiency |
| Tech Lead (PER-TECH-LEAD) | 1.0x | Traceability, decisions, architecture |
| Business Viability | 1.0x | Time to market, moat, revenue |
| Enterprise Evaluator | 1.0x | Data sovereignty, audit, RBAC, scale |

### 5. Create the roadmap

Create via `/staircase-author`:
1. **Roadmap node** (RM-*) — `type: deliverable, category: roadmap`, criteria are phases
2. **Phase criteria** — each describes a capability state ("the engine can parse and index .req.yaml files")
3. **`targets` links** on the roadmap — reference which requirement criteria each phase intends to address
4. Wire `derives-from` links to parent deliverable criteria if this is a child roadmap

### 6. Validate

```bash
./engine/staircase --format json validate specs/
```

Present the roadmap and recommend which phase to decompose next.

## Tactical Level (roadmap exists → milestones)

### 1. Load phase scope

```bash
# Load the phase criterion
./engine/staircase show <PHASE-CRITERION-ID> --format json

# What already derives from this phase (milestones, solutions)?
./engine/staircase trace <PHASE-CRITERION-ID> --direction down --format json

# Load the parent roadmap for targets links (requirement criteria this phase addresses)
./engine/staircase show <ROADMAP-ID> --format json
```

From the roadmap `show` output, extract `targets` links — these are the requirement criteria that should be satisfied in this phase.

Identify all requirement criteria that should be satisfied in this phase by loading the targeted criteria:
```bash
./engine/staircase show <TARGETED-CRITERION-ID> --format json
```
Issue these in parallel for all targeted criteria IDs.

### 2. Identify state gates

Milestones describe verifiable states, not tasks:
- "Parser handles all node types" not "implement parser"
- "Graph queries return results within 100ms" not "optimize queries"
- "Self-hosting: Staircase validates its own requirements" not "run validation"

### 3. Sequence milestones

- Walking skeleton first — thinnest end-to-end path
- Dependencies via `depends-on` links between milestones
- Phase gate milestone last — integration verification

### 4. Create milestone and epic nodes

Create via `/staircase-author`:
1. **Milestone nodes** (MS-*) — `type: deliverable, category: milestone`, criteria are state predicates
2. **Epic nodes** (DEL-*) — `type: deliverable, category: epic`, grouping shippable work
3. Wire: `derives-from` → phase criterion, `depends-on` between milestones for ordering
4. **`targets` links** on milestones/epics → specific requirement criteria they intend to address

### 5. Recommend further decomposition

For each created milestone, check sizing:
```bash
./engine/staircase --format json gaps --scope <MS-ID>
```

| Milestone | Scope | Recommendation |
|-----------|-------|---------------|
| MS-A | 3 requirements, 8 criteria | Right-sized for slicing |
| MS-B | 8 requirements, 25 criteria | Create sub-milestones or epics first |

## Slice Level (milestones exist → decompose toward solutions)

Slice-level decomposition is **driven by WF-SLICE through the `/staircase-wf` generic router** — not by bespoke logic in this skill. Per DEC-WF-SLICE-CONVERGE-AT-PARITY, WF-SLICE reached parity-of-correctness on the convergence benchmark (DEC-WF-SLICE-PARITY-BENCHMARK) and now owns the slice level: it enforces the just-in-time single-next-leaf discipline (DEC-JIT-SOLUTION-AUTHORING) through the plan/* staged-ratification gates, serving each blind executor only the bounded per-gate contract (DEC-WF-EXECUTOR-BOUNDED-CONTEXT). This skill frames the scope and hands off; it does not author decomposition content, elect a decomposition depth, or identify slices by hand.

### 1. Frame the scope (context for the hand-off)

Load the milestone and its coverage so the hand-off names the right target — these reads frame the intent, they do not author slices here:

```bash
./engine/staircase show <MS-ID> --format json          # milestone detail, targets links, criteria
./engine/staircase --format json gaps --scope <MS-ID>  # which targeted criteria still need authoring
```

If every targeted requirement criterion is already covered, there is nothing to slice — report that and stop. Otherwise continue to the hand-off.

### 2. HAND OFF — decomposition routes to the generic router

When there is genuine uncovered work under the milestone, **do not decompose it here** — hand off to the sibling skill **`/staircase-wf`** (the generic router), passing the natural-language intent (e.g. "decompose milestone `<MS-ID>` into the next buildable solution leaves"). Carry **no hardcoded workflow id and no hardcoded stage names**: the router resolves the intent to the WF-SLICE library workflow from the engine catalogue and drives its staged-ratification gates (scope + ratify). The router — not this skill — is the single driver of the run (REQ-WF-ROUTER-SKILL-001, DEC-WF-DISCOVERY-CLI-PRIMITIVE).

`/staircase-wf` is a **sibling skill invocation**, not a CLI command. Never assemble a `wf start` call here to launch the run yourself.

### 3. Confirm the hand-off landed

A hand-off is only real once the router reports a run handle carrying a `run_id`. Read that `run_id` back from `/staircase-wf`'s report before treating the decomposition as started; cross-check via `./engine/staircase wf runs list --format json` if needed. A hand-off narrated as done with no confirmed `run_id` has not landed — report that plainly rather than record a decomposition that never ran. The run terminates at an `approved_plan_id` with the ratified slices, deferrals (premise-pending), dependencies, and risk acceptances recorded; that terminal decomposition is the slice-level output.

### 4. Deferred-but-real work still needs a home

WF-SLICE defers a criterion whose upstream is not yet real as premise-pending — correct single-next-leaf discipline, not lost work. A deferred-but-real outcome still needs a requirement in the graph: route any such follow-on to `/staircase-author`; never leave it only in prose.

## Token Efficiency

- Use `list` for discovery — returns compact rows without full node detail
- Use `summary` for landscape counts — single call replaces N parallel Greps
- Graph-query commands emit per-consumer projection tiers. `gaps` is identity-tier (`{id, type, category}` only); `list`, `trace`, `summary`, `query`, and the resolved link-target blocks of `show` are compact-tier (identity plus type-specific fields). Drill into `show <id>` for `text`, `rationale`, full link narrative, or criteria children. Run `staircase capabilities <command> --format json` for the registered shape.
- Use `trace` for chain traversal — single call replaces recursive Grep+Read loops
- Batch parallel CLI calls when loading multiple nodes (they share the DB)

## Key Rules

- **CLI first, always.** Shape-of-graph via `staircase summary`, listings via `staircase list`, node detail via `staircase show`, chain traversal via `staircase trace`, coverage via `staircase gaps`. Grep only for the two transitional simulation rows listed in the inventory above.
- **Detect before planning.** Always check what exists first.
- **Two chains.** Deliverables (`type: deliverable`) live in `specs/deliverables/`; solutions (`type: deliverable, category: solution`) live in `specs/solutions/`. Chain boundary is absolute — `derives-from` stays within-chain.
- **`targets` for planning intent.** Deliverables `targets` requirement criteria to express what they intend to address.
- **WHAT/HOW alternation.** Requirement → criteria → requirement → criteria → ... at every level.
- **Milestone criteria are gate predicates, not work specs.** Per DEC-DELIVERY-DEPTH: milestone criteria assert graph state ("all contract tests pass"), not work ("export types to SDK packages"). Work descriptions belong on epics/tasks.
- **Criteria have no ordering.** C1, C2, C3 is identity, not sequence. Use `depends-on` between deliverables for ordering.
- **Requirement criteria drive solutions.** Solutions exist to satisfy requirement criteria (the WHAT). Milestone criteria are delivery context (the WHEN). Check `targets` links to find the requirement criteria; at the slice level the WF-SLICE router decomposes against those (this skill does not author the solution leaves by hand).
- **Check satisfaction before creating.** Always check if targeted requirement criteria already have solutions. Wire existing solutions to milestone criteria — don't recreate them.
- **Slice-level decomposition is WF-SLICE's, via the router.** At the slice level (milestone → solution leaves) this skill hands off to `/staircase-wf` (see `## Slice Level`); it does not author solutions by hand or elect a decomposition depth (DEC-WF-SLICE-CONVERGE-AT-PARITY). Depth expectations remain a gating-profile concern, handled by the workflow's staged gates, not a structural rule. Depth reasoning below applies only to the roadmap and phase-decomposition levels this skill still owns.
- **Solutions are delivery chain artefacts.** They name specific implementations with test-spec criteria. They `derives-from` deliverable criteria (within-chain) and use `targets` for requirement criteria (planning intent).
- **Reuse before creating.** Check list output for existing milestones, solutions, and roadmaps first.
- **Vertical slices only.** Every deliverable must produce observable, testable value.
- **Validate after every change.** `staircase validate` is the structural quality gate.
- **Optimistic discovery.** Attempt the canonical invocation first; consult `staircase capabilities <path>` only on failure.
- **Read from `.staircase/index.db`.** The apply pipeline commits projection freshness on `author --confirm`, so the project index reflects the current graph state. The skill never needs a side-car DB.
