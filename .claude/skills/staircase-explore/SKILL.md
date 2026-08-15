---
name: staircase-explore
description: "Interactive graph exploration: search by topic, trace WHAT/HOW chains across both requirement and delivery chains, understand context around any node or area. Delegates search and traversal to the canonical staircase CLI query, trace, and show commands."
---

# Explore the Requirement Graph

Answers: **Help me understand this area/node/topic.**

Combines search, trace, and context into guided exploration. The output is a context package that informs whatever comes next — discussion, planning, or building.

The authoritative data source is the Go engine CLI at `./engine/staircase`. Keyword search, chain traversal, and node detail are delegated to canonical CLI invocations producing JSON. See REQ-CANONICAL-ENGINE-001.C5.

## Response shape

Read the whole JSON payload into context — it is self-describing, so take each value together with the inline meaning shipped beside it. See the graph-reads rule in CLAUDE.md.

Graph-query commands emit per-consumer projection tiers registered in `typebehaviour`. `gaps` returns the leanest **identity tier** (so response size scales with criterion count, not title length); `trace`, `summary`, `query`, `list`, and the resolved link-target blocks of `show` return the **compact tier** (identity plus a few type-specific state fields); only `show`'s primary subject emits full prose (`text`, `rationale`, link narrative, and criteria children). Which fields each tier carries is the engine's live contract — read it from `staircase capabilities <command> --format json`, and read the payload raw rather than memorising a field list here.

## Delegated vs Simulated Inventory

| Operation | Mechanism | Rationale |
|-----------|-----------|-----------|
| Keyword search (by topic, question, ID prefix) | `staircase query <term> --format json` | Canonical — ranked search with token budget and pagination; drill into `show <id>` for prose. |
| Node detail (all scalar fields, resolved link titles, criteria children) | `staircase show <id> --format json` | Canonical — single call returns everything; no secondary lookups needed. |
| Chain traversal (upward to roots, downward to evidence, with decisions inline) | `staircase trace <id> --format json` | Canonical — bidirectional walk with cycle detection, decisions resolved via justified-by links. |
| Coverage state (gaps / covered / violated per criterion) | `staircase --format json gaps --scope <id>` | Canonical — three-state classifier from `internal/coverage`. |
| Capability discovery on CLI failure | `staircase --format json capabilities [path]` | Canonical — REQ-CLI-001.C5 / SOL-AI-TOOLING-CLI-DELEGATION.C3. |
| Reverse `targets` lookup (deliverables planning to address a criterion) | `Grep` (transitional simulation) | CLI does not yet expose reverse link traversal for `targets` links. Absorbs into a future `staircase trace --links targets` or `staircase list --targets <id>`. |

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

- `$0` — What to explore: a node ID (e.g., `REQ-PARSE-001`), a topic keyword (e.g., "evidence"), or a question (e.g., "what requirements cover authentication?")

## Step 0 — Confirm the binary exists

The skill reads from `.staircase/index.db`, which the apply pipeline keeps fresh on every `author --confirm`. No pre-step is required.

If the binary does not exist, build it first:

```bash
cd engine && go build -o staircase ./cmd/staircase && cd ..
```

If `.req.yaml` files have been edited outside the apply path (manual edits, git pull), run `./engine/staircase build specs/` once to refresh the index.

## Step 1 — Find the starting point

**If $0 is a node ID:**

```bash
./engine/staircase show <ID> --format json
```

The JSON payload is `{status, data: {id, type, category, title, status, priority, version, text, rationale, links: [{type, target: <compact node projection>}], criteria: [{id, title, measurement_type}]}}`. The primary subject carries full prose; link target blocks are compact (`{id, type, category, title, status}` plus type-specific fields). For a linked node's `text` or `rationale`, call `show <LINKED-ID>`.

**If $0 is a keyword or question:**

```bash
./engine/staircase query <term> --format json
```

The JSON payload is `{status, data: {total, returned, budget_consumed, nodes: [{id, title, type, category, status, ...type-specific}]}}`. Drill into `show <id>` for `text`, `rationale`, links, and criteria.

To narrow by type or category, append a type qualifier to the query term (e.g., `"evidence type:criterion"` or `"REQ-PARSE"`), or run `staircase list --type <type> --format json` for a filtered enumeration.

Present top results and let the user pick a focus, or continue with the most relevant match.

## Step 2 — Trace the full context

For the focus node, run the bidirectional trace:

```bash
./engine/staircase trace <ID> --format json
```

The JSON payload is:
```
{
  status,
  data: {
    start_id, direction,
    up: Node,    // upward chain to roots (why does this exist?)
    down: Node,  // downward tree to evidence (what proves this?)
    warnings
  }
}
```

where each `Node` carries `{id, type, category, title, derives_via, decisions: [{id, title, chosen, version}], evidence: [{id, result, method, observed_at}], children, parents}`.

- **Upward** — `up.parents` walks the WHAT/HOW chain to root (obligations, persona-goals).
- **Downward** — `down.children` walks the decomposition tree to evidence at leaf criteria.
- **Decisions** — compact at each node from `justified-by` links; call `show <DEC-ID>` for full `text`/`rationale`.

For targeted traversal, pass `--direction up` (why does this exist?) or `--direction down` (what proves this?).

## Step 3 — Two-chain context (for solutions)

Solutions (`type: deliverable, category: solution`) are in the delivery chain. The trace upward follows `derives-from` to deliverable criteria; `targets` links point to requirement criteria as planning intent (not derivation).

- **Delivery chain** — the upward trace reaches deliverable criteria (MS-*.C*, DEL-*.C*, RM-*.C*) via `derives-from`.
- **Requirement intent** — `targets` links in `staircase show` output identify which requirement criteria this solution addresses.

The trace direction indicates chain membership for all nodes:
- Requirements (OBL, PER, SN, REQ, JRN): requirement chain — trace upward toward obligations/persona-goals
- Deliverables (RM, MS, DEL, SOL): delivery chain — trace upward toward roadmap phases

**Lateral context** — all outgoing link types (justified-by, depends-on, conflicts-with) appear in `staircase show` output as compact link target blocks (`{id, type, category, title, status, ...}`). For a linked node's `text` or `rationale`, call `show <LINKED-ID>`.

**Planning intent (targets)** — to find which deliverables have declared intent to address this criterion, run the transitional simulation:
```pseudocode
Grep for `target: {ID}` across specs/deliverables/**/*.req.yaml (output_mode: content, -B 1)
  → filter to hits whose preceding line is `type: targets`
```
This Grep will be removed when the CLI exposes reverse link traversal.

## Step 4 — Coverage state

```bash
./engine/staircase --format json gaps --scope <ID>
```

The JSON payload is `{status, shape_version, data: {gaps[], covered[], violated[], total}}` (canonical envelope — the coverage report is under `data`). Each entry in `gaps[]` carries `criterion_id`, `parent_id`, `parent_priority`, `suggested_action`. Coverage by decomposition: `implicit = total - len(covered) - len(violated) - len(gaps)`.

For a compact coverage overview (counts + top gaps):

```bash
./engine/staircase summary --scope <ID> --format json
```

Do **not** grep `satisfies` or `derives-from` links to compute coverage — `staircase gaps` is authoritative.

## Step 5 — Present the context package

```markdown
## [Node Title] ({ID})

**Chain:** Requirement / Delivery / Both (solution)
**Why it exists:** {trace-to-root summary from up.parents}
**What it requires:** {criteria summary with coverage state from gaps}
**Decisions:** {justified-by decisions with `chosen` — from trace.up Node.decisions; `show <DEC-ID>` for rationale}
**Dependencies:** {depends-on links with titles — from show output}
**Downstream:** {what derives from this, solutions, evidence — from trace.down}
**Delivery context:** {roadmap phase, milestone, epic — from trace.up delivery chain nodes}
**Gaps:** {uncovered criteria from gaps report}
```

## Step 6 — Suggest next actions

Based on what was found:
- Gaps found → "Run `/staircase-wf` to triage the gap (typed disposition + draft recommendation from the runtime)"
- Ready to build → "Run `/staircase-build {SOL-ID}` to start implementation"
- Needs planning → "Run `/staircase-plan {ID}` to decompose"
- Quality concern → "Run `/staircase-review {ID}` to check quality"

## Key Rules

- **CLI first, always.** Search via `staircase query`, traverse via `staircase trace`, load detail via `staircase show`, compute coverage via `staircase gaps`. Grep only for the reverse-targets lookup listed in the inventory above.
- **Progressive detail.** Compact results from `query`/`list`/`trace`/`gaps`/`summary`; drill into `show <id>` for `text`, `rationale`, and full link narrative.
- **Token-bounded.** The `query` command enforces a `--budget` token ceiling and returns `next_offset` for pagination. Use it rather than loading all matching files.
- **Always show the WHY.** The upward trace to root is not optional — context without motivation is useless.
- **Two-chain awareness.** For solutions, always show both requirement chain and delivery chain context from the trace output.
- **End with actionable suggestions.** Exploration that doesn't lead somewhere is wasted work.
- **Optimistic discovery.** Attempt the canonical invocation first; consult `staircase capabilities <path>` only on failure.
- **Read from `.staircase/index.db`.** The apply pipeline commits projection freshness on `author --confirm`, so the project index reflects the current graph state.
