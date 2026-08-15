---
name: staircase-tree
description: "Status-map navigator. Calls `staircase tree [NODE]` and presents its work-breakdown structure directly: each node's delivery-readiness state from the unified walk, finished-by-default progress, rollup counts, cross-boundary blocker annotation, and per-node satisfaction-cascade coverage state selectable by chain. `--open` hides finished work; `--depth N` bounds descent; `--chain delivery|requirement` selects the coverage view. Use to see where a scope stands — the structural progress map. For what to work on next, use /staircase-queue; for graph health metrics, use /staircase-status."
---

# Staircase Tree

Answers: **Where does everything stand under this scope?**

The engine computes the whole status map in one call. This skill calls `staircase tree [NODE]` and presents the result — it never reconstructs the tree from `list`, `trace`, and `gaps`, and never re-derives coverage or readiness state. The command is the source. Read the whole JSON payload into context — it is self-describing, so take each value together with the inline meaning shipped beside it. See the graph-reads rule in CLAUDE.md.

CLI: `./engine/staircase`. Reads from `.staircase/index.db`, which the apply pipeline keeps fresh on every `author --confirm`.

## The single surface

`staircase tree` projects the one unified delivery-chain walk the next-action surface ranks, so the structural view and the next-work view never disagree about a node's state. Each node carries:

- its **delivery-readiness state** — finished / ready / blocked / review-, seal-, or decompose-pending — drawn from the same classification `staircase next` uses;
- a **rollup** of its descendants' readiness counts (on aggregation nodes);
- a **cross-boundary annotation** when a prerequisite outside the rendered scope blocks an in-scope node, so a blocker is never hidden by the scope edge;
- its **satisfaction-cascade coverage state** for the selected chain — covered / partial / uncovered / violated — so release progress and specification satisfaction are visible without conflation.

Finished work shows by default so the tree doubles as a progress map.

| Ask | Invocation |
|---|---|
| Where does this scope stand? | `staircase tree <NODE>` |
| Survey the top of the graph (roadmap forest) | `staircase tree` |
| Only what's left to do | `staircase tree <NODE> --open` |
| Just the top levels | `staircase tree <NODE> --depth N` |
| Requirement-satisfaction view instead of release progress | `staircase tree <NODE> --chain requirement` |
| Machine-readable for an agent or a renderer | `staircase tree <NODE> --format json` |

Flags are exactly: positional `[NODE]` (a delivery-chain node ID, or omit for the roadmap forest), `--open`, `--depth N` (0 = unbounded), `--chain delivery|requirement` (default delivery), plus the persistent `--format` / `--config` / `--db`.

## Step 1 — Confirm the index exists

If `.req.yaml` files have been edited outside the apply path (manual edits, `git pull`), run `./engine/staircase build specs/` once. Otherwise skip — the index is current.

## Step 2 — Call the surface

```bash
# Where does an epic stand — full breakdown, finished work included as a progress map.
./engine/staircase tree DEL-EPIC-X

# Only outstanding work, top two levels.
./engine/staircase tree DEL-EPIC-X --open --depth 2

# Requirement-coverage view: how satisfied is the specification this work targets.
./engine/staircase tree DEL-EPIC-X --chain requirement

# The roadmap forest, machine-readable.
./engine/staircase tree --format json
```

**Shell pattern:** if a downstream shell script needs the JSON, write the payload to a tempfile and let a tool read the whole file; never capture it into a shell variable and re-echo, because node `title` fields contain literal newlines that a re-echo splits.

## Step 3 — Present the answer

The text output is already a coloured ASCII tree — present it directly. When working from `--format json`, render the `data.tree` structure as an ASCII tree, preserving each node's state, rollup counts, cross-boundary `blocked_by` annotation, and `coverage` chip. Do not collapse, re-rank, or re-derive — the structure and every annotation are the command's answer.

## Key Rules

- **The command is the source.** Call `staircase tree` and present its output. Never reconstruct the tree or its coverage from `list` / `trace` / `gaps`.
- **One chain at a time.** Coverage state names a single chain so completion timescales are not conflated. `--chain delivery` is release progress; `--chain requirement` is specification satisfaction.
- **Structure, not next-action.** The tree shows where things stand. For *which* work to pick up next — the leverage-ranked decision and the bottleneck — defer to `/staircase-queue` (`staircase next`). Do not pick work by reading position in the tree; it has no leverage ordering.
- **Optimistic discovery.** Attempt the canonical invocation first; consult `./engine/staircase --format json capabilities tree` only on failure.
- **Read from `.staircase/index.db`.** The apply pipeline commits projection freshness on `author --confirm`, so the project index reflects the current graph state.
