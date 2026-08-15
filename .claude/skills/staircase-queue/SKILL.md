---
name: staircase-queue
description: "Delivery chain work queue. Calls `staircase next`, which answers only when given intent — a named target or a selected objective (`--throughput`); a bare call returns a static signpost routing to the modes, not a ranking. Presents the computed answer directly: the scope health rollup, the scoped bottleneck set (one gating item per disjoint dependency component, whose completion frees the most downstream work — and which may name an out-of-scope prerequisite when one blocks in-scope work), and the leverage-ranked actionable set. `--lanes` re-projects the same answer grouped by isolation domain for concurrent dispatch; `--explain <id>` drills into one item; naming one or more targets returns the ordered completion chain to finish them with shared work counted once. Use when deciding what to work on next or when launching parallel agent sessions. For graph health and coverage metrics, use /staircase-status instead."
---

# Staircase Queue

Answers: **What should I work on next, and why? What can I dispatch in parallel? What's the ordered plan to finish one or more targets?**

The engine computes the whole answer in one call. This skill calls `staircase next` and presents the result — it never re-ranks, re-scores, filters, or assembles a queue from other commands.

CLI: `./engine/staircase`. Reads from `.staircase/index.db`, which the apply pipeline keeps fresh on every `author --confirm`.

## The single surface

`staircase next` returns **one** self-describing answer. Every enumerated value carries its plain-language meaning inline (in each item and in the answer's `legend`), so you never guess what a `kind` or a `lane.basis` means. Read the whole JSON payload into context — it is self-describing, so take each value together with the inline meaning shipped beside it. See the graph-reads rule in CLAUDE.md. Blocked work does not enumerate as rows — it collapses into the `bottlenecks` set (one gating item per disjoint dependency component), so the critical-path view and the next-work view are one answer, not two tools.

**Intent is required.** `next` answers only when given intent — a named target (the completion mode) or a selected objective (`--throughput`). A bare `next` with neither returns a static **signpost** routing to the modes and to the status map (`staircase tree`), never a computed ranking, because "what is next" with no goal is ill-posed. A deployment may set `build_order.default_objective` to promote one bounded objective (e.g. `throughput`) as the bare-call default.

Ways to ask, all the same command:

| Ask | Invocation |
|---|---|
| What should I work on next? (throughput objective — highest-leverage unblockers) | `staircase next --throughput [--top N] [--scope <id>]` |
| What can N agents pick up in parallel? (grouped by isolation domain) | `staircase next --throughput --lanes [--top N] [--scope <id>]` |
| Tell me everything about one item before I start | `staircase next --explain <id>` |
| What's the ordered plan to finish these targets? | `staircase next <target>... [--top N]` |

Flags: positional `<target>...` (one or more, the completion mode), the objective selector `--throughput`, `--explain <id>`, `--scope <id>`, `--top N` (0 = no cap), `--lanes`, plus the persistent `--format` / `--config` / `--db`. There is no `--parallel` and no `--depth` — `--lanes` is the dispatch-lane grouping, and depth is not a control on this surface. An objective selects its own mode and does not combine with a named target or `--explain`; a named target combined with `--scope` is rejected (a target already carries its own reach); naming several targets unions their plans, counting shared work once.

## Step 1 — Confirm the index exists

If `.req.yaml` files have been edited outside the apply path (manual edits, `git pull`), run `./engine/staircase build specs/` once. Otherwise skip — the index is current.

## Step 2 — Call the surface

```bash
# Single next action — one worker, one decision (top defaults to the full ranked set; cap it).
./engine/staircase next --throughput --top 1 --format json

# Top 5 leverage-ranked options across all domains — browse and pick.
./engine/staircase next --throughput --top 5 --format json

# Narrow to one milestone, epic, or roadmap phase.
./engine/staircase next --throughput --top 5 --scope DEL-EPIC-X --format json

# Parallel dispatch — actionable set grouped into isolation-domain lanes, N per lane.
./engine/staircase next --throughput --lanes --top 3 --format json

# Drill into one item's full composition and downstream-unblock set.
./engine/staircase next --explain SOL-X --format json

# Ordered completion chain to finish one named target.
./engine/staircase next DEL-EPIC-X --top 10 --format json

# Ordered completion chain to finish SEVERAL targets at once — shared work counted once.
./engine/staircase next DEL-EPIC-X MS-Y --top 10 --format json
```

**Reading the answer:** read the whole `--format json` envelope into context — it is self-describing (foreground, bottlenecks, actions, and the `legend` that glosses every value), so take it entire rather than slicing one path out and losing the rest. If a downstream **shell script** genuinely needs to iterate items, write the payload to a tempfile first and let a tool read the whole file; never capture it into a shell variable and re-echo, because node `title` fields contain literal newlines that a re-echo splits.

## Step 3 — Read the response

Branch on `data.mode`:

- `mode: "signpost"` — a bare call with no intent. The surface computed nothing (no `health`, `actions`, or `bottlenecks`); `data.signpost` carries `message`, `modes[]` (each `{invocation, mode, meaning}` — the completion mode and every objective), and `orient` (the status-map route). Pick a mode and re-run — do not present a signpost as work.
- `mode: "throughput"` — the throughput objective (selected with `--throughput`). `data.actions[]` is the leverage-ranked set, and `data.bounds[]` reports each region's `returned`/`total`/`omitted` so a `--top`-capped menu states how much it dropped. With `--lanes`, `data.lanes[]` carries the same items grouped by `domain`.
- `mode: "completion"` — one or more targets named. `data.actions[]` is the ready set to finish them (shared work counted once), foregrounded by `data.foreground`; the blocked remainder collapses into `data.bottlenecks`.
- `mode: "explain"` — `--explain <id>`. `data.explain` carries the one item's full composition and transitive downstream-unblock set; `data.actions` is absent.

Every **computed** mode (throughput, completion, explain) carries `data.health` (the scope rollup), `data.foreground` (the single recommended action), and `data.legend` (the inline meaning of every `kind`, `lane_basis`, `closure`, and `in_flight` value). The signpost carries none of these — it computes nothing. Present the legend's meanings to the user; never invent your own. `data.bottlenecks` is present only when work is gated — an array with one entry per disjoint dependency component, highest-leverage first, omitted entirely when no item gates other work and nothing is blocked. Render one bottleneck line per entry; a scoped query's bottleneck may name an out-of-scope prerequisite.

### Throughput (`mode: "throughput"`)

```jsonc
{
  "status": "ok",
  "shape_version": "…",                // next-surface payload version; bumps when the wire shape changes
  "data": {
    "scope": "",                       // empty = whole graph; else the --scope id
    "mode": "throughput",
    "health": {                        // the scope rollup — counts by state
      "ready": 21, "blocked": 73, "review_pending": 62,
      "seal_pending": 2, "decompose_pending": 14
    },
    "bottlenecks": [                   // one gating item per disjoint dependency component
      {
        "node": "SOL-X",
        "unblocks": 10,                // count of items it directly/transitively frees
        "unblocks_weighted": 80,       // priority-weighted downstream impact
        "do_now": { "action": "build", "target": "SOL-X", "kind": "ready-build", "in_flight": false },
        "meaning": "the gating item of one independent dependency component whose completion frees the most weighted downstream work — there is one per disjoint component, and it may name an out-of-scope prerequisite; do_now is the nearest step available now toward it"
      }
    ],
    "legend": { "kind": { /* ... */ }, "lane_basis": { /* ... */ }, "closure": { /* ... */ }, "in_flight": { /* ... */ } },
    "actions": [
      {
        "rank": 1,
        "score": 352,                  // leverage-aware WSJF — already ranked
        "kind": "ready-build",
        "kind_meaning": "build this solution — every prerequisite is satisfied and its criteria need evidence",
        "target": "SOL-X",
        "title": "…",
        "priority": "must",
        "why": { "priority": 8, "unblocks": 10, "unblocks_weighted": 80, "effort": 2 },
        "unblocks_count": 10,
        "unblocks_sample": [ "SOL-A", "SOL-B" ],
        "composition": [                 // review/seal kinds: WHICH inputs close it, and how much evidence each has
          { "id": "SOL-A.C1", "evidence_count": 2 }
        ],
        "composition_total": 7,          // inputs before the per-row bound — exceeds the entries shown when bounded
        "lane": {
          "domain": "DEL-EPIC-X",
          "basis": "advisory",
          "basis_meaning": "dependency-independent but code overlap unverified — not proven safe"
        },
        "do": "build",
        "in_flight": false
      }
    ],
    "foreground": { "target": "SOL-X", "kind": "ready-build", "do": "build", "reason": "…" },  // the one recommended step
    "bounds": [                        // per-region row-cap accounting (every enumerable region)
      { "region": "actions", "k": 5, "returned": 5, "total": 21, "omitted": 16 }
    ]
  }
}
```

`--lanes` adds, alongside `actions`, a top-level `lanes` array: `[ { "domain": "DEL-EPIC-X", "items": [ /* same action shape */ ] } ]` — one entry per isolation domain, each recorded in `bounds[]` too. Dispatch one agent per lane so concurrent work does not contend.

### Signpost (`mode: "signpost"`, a bare call with no intent)

```jsonc
{
  "status": "ok",
  "data": {
    "mode": "signpost",
    "signpost": {
      "message": "next requires intent: name a target, or select an objective …",
      "modes": [
        { "invocation": "staircase next <target>", "mode": "completion", "meaning": "…" },
        { "invocation": "staircase next --throughput", "mode": "throughput", "meaning": "…" }
      ],
      "orient": { "invocation": "staircase tree [node]", "mode": "orient", "meaning": "where things stand — the status map" }
    }
  }
}
```

There is no `health`, `actions`, `bottlenecks`, or `foreground` — the signpost computes nothing. Route the user to the named mode (or set `build_order.default_objective` for a bare-call default); never present it as a work answer.

### Completion (`mode: "completion"`, one or more targets named)

```jsonc
{
  "status": "ok",
  "data": {
    "scope": "DEL-EPIC-X, MS-Y",       // every named target; shared work appears once
    "mode": "completion",
    "health": { /* … */ },
    "legend": { /* … */ },
    "foreground": { /* the leading ready step toward the targets */ },
    "actions": [ { /* same action shape as throughput — the ready set */ } ],
    "bottlenecks": [ { /* the blocked remainder, collapsed, one per disjoint component */ } ],
    "bounds": [ { "region": "actions", "k": 5, "returned": 2, "total": 9, "omitted": 7 } ]
  }
}
```

The ready set is `actions[]`; the blocked remainder never enumerates — it collapses into `bottlenecks[]`. When a region's `omitted > 0` (read it from `bounds[]`), say so — never present a truncated answer as complete.

### Parallel-safety honesty

Report `lane.basis` exactly as the engine warrants it, **always with its `basis_meaning` on the same line**. `advisory` means "dependency-independent but code overlap unverified — **not proven safe**" — never present an advisory lane as safe to parallelize. Only `deterministic` (disjoint graph footprints) or `provider` (a registered work-overlap provider result) is verified separateness.

## Step 4 — Present the result

The actions are **already ranked** — present them in order, as-is.

### Throughput

```markdown
## Top N next actions (leverage-ranked)

| # | Kind | Action | Score | Priority | Why | Parallel-safety |
|---|------|--------|-------|----------|-----|-----------------|
| 1 | build (ready-build) | SOL-X (domain DEL-Z) | 352 | must | unblocks 10 (weighted 80), effort 2 | advisory — not proven safe |
| 2 | attest (review-ready) | REQ-Y.C3 (domain DEL-Z) | 140 | must | contributing inputs complete | advisory — not proven safe |
| 3 | seal (seal-ready) | MS-Q (domain DEL-R) | 98 | must | every criterion closed, seal open | deterministic — safe to parallelize |

**Bottlenecks (one per independent component):**
- `SOL-X` — completing it frees 10 downstream items (weighted 80). Nearest step now: build `SOL-X`.
- `SOL-W` — frees 3 (weighted 12). Nearest step now: build `SOL-W`.

(When 16 of 21 are omitted under `--top`, state it: "showing 5 of 21; 16 omitted, raise --top".)
```

For a single action (`--top 1`), drop the table:

```markdown
**Next:** build `SOL-X` (domain `DEL-Z`) — score 352, must.
Why: unblocks 10 (weighted 80), effort 2. Parallel-safety: advisory — not proven safe.
**Bottleneck:** this is the bottleneck of its component — nothing higher-leverage is available.
```

### Parallel (`--lanes`)

One section per lane so callers see per-domain depth:

```markdown
## Per-lane ready work (one agent per lane, up to N each)

### Lane DEL-EPIC-X
| # | Kind | Action | Score | Why |
|---|------|--------|-------|-----|
| 1 | build | SOL-X | 352 | unblocks 10, effort 2 |
| 2 | build | SOL-X2 | 140 | unblocks 3, effort 1 |
```

### Completion (one or more targets named)

```markdown
## Plan to finish DEL-EPIC-X, MS-Y — 9 remaining (showing 2; 7 omitted, raise --top)

**Phase 1 — decompose** (lanes safe to parallelize: disjoint graph footprints)
1. decompose `MS-V` — slice it into solutions
2. decompose `TSK-W` — slice it into tasks

**Phase 2 — build** (after phase 1)
…
```

## Step 5 — Route by kind

`kind` is the next-step router:

| Kind | Meaning | Hand off to |
|---|---|---|
| `ready-build` | build this solution | `/staircase-build <solution-id>` |
| `review-ready` | attest this criterion | `/staircase-attest <criterion-id>` |
| `re-attest-needed` | attestation predates an evidence shift | `/staircase-attest <criterion-id>` |
| `seal-ready` | seal this deliverable | `/staircase-seal <deliverable-id>` |
| `seal-stale-review` | sealed but cascade no longer satisfies | `/staircase-seal` (review the seal) |
| `slice-needed` | decompose this deliverable | `/staircase-plan <deliverable-id>` |

The ranked list already names each item's contributing inputs and their evidence counts (`composition`), so choosing between candidates needs no extra call. For the evidence identifiers behind those counts, `staircase next --explain <id>` returns the hydrated composition (`data.explain.composition`) and the transitive downstream-unblock set (`data.explain.downstream_unblock`). Both are bounded to the same per-region K; add `--verbose` when a row reports a `composition_total` larger than the entries it shows.

## Discovery Discipline

Attempt the canonical invocation directly. On unknown-command or unknown-flag failure:

```bash
./engine/staircase --format json capabilities next
```

Read `commands[].flags[]` and `commands[].args[]`, update the invocation, and retry once.

## Key Rules

- **One call, one answer.** `staircase next` is the canonical work-discovery surface. Do not assemble a queue from gap reports, `list`, `trace`, or any other command.
- **Trust the ranking; present as-is.** The `score` is leverage-aware WSJF (priority-weighted transitive downstream impact ÷ remaining effort). The skill presents the ranked result; it never re-ranks, re-scores, filters, or post-processes the payload.
- **`--lanes` is the dispatch-lane projection.** Absent = a single flat leverage-ranked list. Present = the same set grouped by isolation domain for concurrent dispatch. Use flat to pick; use `--lanes` to dispatch. It is a lane grouping, not a hierarchy.
- **`--top` is the count axis.** It caps the actionable list (throughput) or the completion ready set (target mode), never past the per-region bound. `0` = use the per-region bound. The `bounds[]` entry for each region reports `returned`/`total`/`omitted` — surface the omission.
- **Blocked work lives in the bottleneck set, not the rows.** Do not enumerate blocked items — surface every entry of `bottlenecks[]` and its `do_now`. A scoped query may name an out-of-scope prerequisite as a bottleneck.
- **Several targets union once.** Naming multiple targets returns one combined answer with shared prerequisites counted once; `data.scope` lists them all. A target plus `--scope` is rejected.
- **Intent is required.** A bare `next` (no target, no objective) returns `mode: "signpost"`, not a ranking — route the user to a named mode, or set `build_order.default_objective`. Never present a signpost as work.
- **Self-description is the contract.** Present each item's `kind_meaning` and `lane.basis_meaning`; surface the `legend`. Never substitute your own interpretation of a `kind` or a safety basis.
- **Parallel-safety honesty is non-negotiable.** An `advisory` basis always travels with "not proven safe." Never report advisory work as safe to parallelize.
- **`kind` is the next-step skill router.** See Step 5.
- **Read from `.staircase/index.db`.** The apply pipeline commits projection freshness on `author --confirm`, so the index reflects the current graph state without a manual rebuild.
