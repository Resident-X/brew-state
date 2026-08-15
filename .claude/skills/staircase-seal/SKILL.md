---
name: staircase-seal
description: "Closes out an aggregation deliverable (task, milestone, epic, or roadmap) with a deliberate-act seal event via `staircase seal`. Use when the `staircase next` surface surfaces a deliverable as seal-ready, when accepting risk on an incomplete aggregation criterion with explicit waivers, or when a caller asks to seal, close, or finalise a task/milestone/epic/roadmap."
allowed-tools: "Bash"
---

# Seal Aggregation Deliverable

Answers: **Close out this aggregation deliverable — task, milestone, epic, or roadmap — as a deliberate act, recording outcome, reviewer, rationale, composition, and waivers.**

The seal event is the closure surface for aggregation deliverables per `DEC-SEAL-AS-DELIBERATE-ACT`. The CLI is the mutation surface; this skill is workflow only — it never writes graph state directly. Read the whole JSON payload into context — it is self-describing, so take each value together with the inline meaning shipped beside it. See the graph-reads rule in CLAUDE.md.

## Arguments

- `$0` — Deliverable ID to seal (e.g., `MS-SEAL-RUNTIME`, `DEL-EPIC-AGGREGATION-SEAL`).

## Discovery discipline

The commands below are known to work against the engine version that shipped with this skill. On unknown-flag failure, run `./engine/staircase --format json capabilities seal` once and update the invocation. Do not eagerly enumerate the CLI surface at session start (`REQ-CANONICAL-ENGINE-001.C6`).

## Checklist

Copy and tick as you go:

```
Seal progress:
- [ ] Step 1 — Load deliverable, confirm aggregation category
- [ ] Step 2 — Cascade-completeness check
- [ ] Step 3 — In-flight solution detection
- [ ] Step 4 — Governance gate (profile + reviewer)
- [ ] Step 5 — Compose outcome and waivers
- [ ] Step 6 — Invoke seal
- [ ] Step 7 — Surface composition snapshot and follow-ups
```

## Step 1 — Load deliverable (grounds `JRN-SEAL-DELIVERABLE.C1`)

```bash
./engine/staircase --format json show <DELIVERABLE>
```

Confirm `data.category` is an aggregation deliverable — any non-solution deliverable level: `task`, `milestone`, `epic`, or `roadmap` (plus any custom level a project declares). Seal eligibility is the single `category != solution` boundary (`IsAggregationDeliverable`), not a fixed level enumeration: the engine refuses only the `solution` leaf and non-deliverable nodes. A `task` seals exactly like a milestone or epic — closing its own aggregation criteria by cascade over the contributing solution(s).

## Step 2 — Cascade-completeness check (grounds `JRN-SEAL-DELIVERABLE.C1`, `JRN-SEAL-DELIVERABLE.C4`)

```bash
./engine/staircase --format json gaps --scope <DELIVERABLE>
```

Branch:

- Every aggregation criterion `covered` → `outcome=delivered` is admissible.
- One or more aggregation criteria show `gap` or `violated` → caller must either close them first or proceed with `outcome=risk-accepted` and one `--waiver` per non-cascade-complete aggregation criterion.

## Step 3 — In-flight solution detection (grounds `JRN-SEAL-DELIVERABLE.C3`, `JRN-SEAL-DELIVERABLE.C6`)

"In-flight" means an active targeting solution whose criteria are not all cascade-satisfied. The engine's authoritative enumeration is the `seal` command's own refusal message: it names every in-flight solution by ID when it refuses `outcome=delivered`. The structural pre-flight that mirrors the engine's view:

```bash
# 1. List targeting solution children of the deliverable.
./engine/staircase --format json trace <DELIVERABLE> --direction down
# Filter the trace for nodes where type=deliverable, category=solution,
# status=active. These are the candidates.

# 2. For each candidate solution, ask the engine for its satisfaction state.
./engine/staircase --format json gaps --scope <SOL-ID>
# A solution with any criterion in status=gap or status=violated is in-flight.
# A solution with all criteria covered is satisfied and does not block the seal.
```

Do not invent a custom "no pass evidence" heuristic — satisfaction is the cascade walk the engine performs; matching it by hand drifts from the engine. If pre-flight enumeration ever disagrees with the seal command's refusal, the seal command's refusal is authoritative.

Outcome × in-flight matrix:

| Outcome | In-flight present? | Required handling |
|---|---|---|
| `delivered` | no | proceed |
| `delivered` | yes | seal refuses unless `--cancel-inflight` is passed; named solutions are deprecated atomically with the seal |
| `risk-accepted` | no | proceed with waivers per Step 5 |
| `risk-accepted` | yes | engine cancels in-flight solutions atomically without `--cancel-inflight`; the waiver list documents the deliberate cancellation |

**Surface the in-flight list to the caller BEFORE invocation** so cancellation is an explicit decision, not a side-effect of a refusal retry.

### When `--cancel-inflight` is the right call

Pass `--cancel-inflight` with `--outcome=delivered` **only** when:

- The in-flight solutions are no longer worth completing because the deliverable is closing now (scope retired, replaced by a successor, abandoned).
- The cancelled scope is genuinely covered by the rest of the contributing-input cascade — every aggregation criterion is `covered` without those solutions.
- The caller has reviewed each in-flight solution by ID and accepts that its targeting REQ-parent will need re-attestation.

Do **not** pass `--cancel-inflight` when:

- Any in-flight solution is still actively contributing value — finish it first, then seal.
- An in-flight solution targets an aggregation criterion that is otherwise un-covered. The right closure is `--outcome=risk-accepted` with an explicit waiver naming that criterion, not silent cancellation under `delivered`.
- The caller is unsure why the solution is in-flight. Investigate via `staircase show <SOL-ID>` and the contributing inputs before cancelling.

### What cancellation does

Either path (`--cancel-inflight` with `delivered`, or implicit cancellation under `risk-accepted`):

- Cancelled solutions transition to `status=deprecated, deprecation_reason=cancelled-on-seal`. The `.req.yaml` files are rewritten — these changes land on disk and need a real commit. See the `--no-export` notes below for the development-mode caveat.
- Every `REQ-parent` attestation whose composition snapshot cited those solutions is flagged for re-attestation per `JRN-SEAL-DELIVERABLE.C6`.
- The `data.cancelled_solutions` array in the seal command's JSON response names every solution that was deprecated by this seal.

## Step 4 — Governance gate (grounds `DEC-GOVERNANCE-SLIDER`)

The governance profile is supplied per invocation via `--profile`. **The flag default is `solo` — meaning a regulated or team project will silently seal under `solo` if `--profile` is omitted.** The skill MUST establish which profile applies before composing the invocation:

1. Ask the operator which profile the project runs under. If unknown, surface the project's effective policy by inspecting `.staircase/config.yaml` (no `governance` key today means the engine has no project-level default — every seal supplies its own profile).
2. Refuse to compose the invocation without a confirmed profile name; do not fall back to the `solo` default implicitly on a project where the operator has not confirmed solo.

Profile reviewer-independence rules:

| Profile | Rule |
|---|---|
| `solo` | Self-seal admissible. Reviewer may be the contributing-input author. |
| `team` | Reviewer must be distinct from every contributing-input attestor. |
| `regulated` | Reviewer must be an independent verifier (no prior author or attestor role on the contributing inputs). |

The engine enforces this on invocation. The skill's job is to surface the active rule and validate the proposed reviewer identity against it **before** running the command, so the operator hears it from the skill rather than from a refusal.

## Step 5 — Compose outcome and waivers (grounds `JRN-SEAL-DELIVERABLE.C4`)

**For `outcome=delivered`:**

```
--outcome delivered
--reviewer <identity>
--rationale "<why this deliverable is delivered>"
[--cancel-inflight]
```

`--rationale` (or `--rationale-file`) is required; one of the two must be non-empty.

**For `outcome=risk-accepted`:**

```
--outcome risk-accepted
--reviewer <identity>
--rationale "<why risk acceptance is the right closure>"
--waiver "criterion-id=<AGG-CRITERION>,rationale=<why this is acceptable>"
[--waiver ...]
```

One `--waiver` per non-cascade-complete aggregation criterion. Per-waiver rationale must be non-empty (`REQ-SEAL-COMMAND-001.C2`). The engine refuses the seal if any non-cascade-complete aggregation criterion is missing from the waiver list.

## Step 6 — Invoke seal (grounds `JRN-SEAL-DELIVERABLE.C2`)

```bash
./engine/staircase --format json seal <DELIVERABLE> \
  --profile <solo|team|regulated> \
  --outcome <delivered|risk-accepted> \
  --reviewer <identity> \
  --rationale <text> \
  [--waiver criterion-id=<id>,rationale=<text>]... \
  [--cancel-inflight] \
  [--no-export]
```

Success response (`status=ok`) carries the seal payload under `data`, in
the same `{status, shape_version, data}` envelope every other command emits
(`show`, `author`, `validate`, …) — the seal command is **not** an exception.
Read every payload field from `data.<field>`, never from the top level:

```json
{
  "status": "ok",
  "shape_version": "<hash>",
  "data": {
    "event_id": "<uuid>",
    "deliverable_id": "<id>",
    "outcome": "delivered|risk-accepted",
    "reviewer": "<identity>",
    "actor_id": "<identity>",
    "actor_type": "<explicit|config-resolved|system-fallback>",
    "rationale": "<text>",
    "composition_snapshot": ["<input-id>", ...],
    "waivers": [{ "criterion_id": "<id>", "rationale": "<text>" }],
    "timestamp": "<RFC3339>",
    "schema_version": "<n>",
    "cancelled_solutions": ["<sol-id>", ...],
    "profile": "<active-profile>"
  }
}
```

**A blank/`null` read is not a failed seal.** If a field parsed from the top
level (e.g. `event_id` instead of `data.event_id`) comes back empty, the seal
almost certainly still applied — re-parse under `data` and confirm state with
`staircase show <DELIVERABLE>` (`data.lifecycle.seal_state == "sealed"`)
BEFORE retrying. A blind retry hits the `re-seal refused: seal_state="sealed"`
error, which reads like a new failure but is really proof the first seal
succeeded.

Error response (`status=error`) carries a top-level `error` string (no `data`
block). The common refusal paths — in-flight solutions without
`--cancel-inflight`, missing waivers, reviewer rejected by profile, and the
already-sealed re-seal refusal above — name the offending item in the `error`.

## Step 7 — Surface composition snapshot and follow-ups (grounds `JRN-SEAL-DELIVERABLE.C2`, `JRN-SEAL-DELIVERABLE.C7`)

Surface to the caller:

1. **Composition snapshot** — every contributing input ID active at seal time. The seal is reproducible from this list alone.

2. **Cancelled solutions** — read from the response's `data.cancelled_solutions` array. Each cancelled solution's targeting REQ-parent attestation is now flagged for re-attestation; the caller is responsible for following through on those re-attestations.

3. **Cascade re-check after cancellation** (`JRN-SEAL-DELIVERABLE.C6` — cascade contribution withdrawal). When `cancelled_solutions` is non-empty, every parent deliverable that cited those solutions through the cascade has lost a contributing input. Re-run gaps against the parent epic to surface any criterion that fell out of coverage:

   ```bash
   ./engine/staircase --format json gaps --scope <PARENT-EPIC>
   ```

   New `gap` entries here are scope the project must close before the parent epic can itself be sealed.

4. **Downstream depends-on impact** (`JRN-SEAL-DELIVERABLE.C7`). The journey calls for two distinct flag propagations on downstream depends-on successors:

   - `risk-accepted` → successors marked **predecessor-waived** (acknowledge / re-plan / cascade-accept).
   - Cancellation paths (`--cancel-inflight` under `delivered`, or implicit cancellation under `risk-accepted`) → cancelled-solution successors are **predecessor-broken** (downstream seal blocked until the link is retargeted via supersession, removed, or the downstream itself deprecated).

   The engine's reverse-depends-on enumeration is not yet a CLI surface — it lands with `MS-SEAL-PROPAGATION` together with the flag emission. Until that ships, surface to the caller:

   - The deliverable ID that was just sealed and its outcome.
   - The `cancelled_solutions` list (each cancelled solution may itself have downstream depends-on successors that are now predecessor-broken).
   - A note that the caller must inspect candidate sibling deliverables (peer milestones within the same epic, peer epics within the same roadmap) via `staircase show <PEER-ID>` and check whether any have a `depends-on` link targeting the sealed deliverable or a cancelled solution.

   Do not attempt to write propagation flags by hand or edit successor `.req.yaml` files from this skill — propagation state is the engine's responsibility once `MS-SEAL-PROPAGATION` lands.

5. **Sealed-criteria immutability is now active** (`JRN-SEAL-DELIVERABLE.C5`). Substantive-field edits on this deliverable's aggregation criteria will be refused by the author surface. Further work covering waived criteria goes through parent-deliverable supersession, not in-place editing.

## `--no-export` development affordance (grounds `SOL-SEAL-SKILL-WORKFLOW.C3`, `DEC-SEAL-EVENT-FILE-PROJECTION`)

**What it does.** Writes the seal event to the SQLite substrate only; suppresses the append to `specs/.events/seal_events.jsonl`.

**What it does NOT do.** It does **not** suppress side-effects of `--cancel-inflight` or risk-accepted cancellation. In-flight solution status transitions to `deprecated` are written to `.req.yaml` files regardless — those changes persist and must be reverted by hand (`git checkout <file>`) if the experiment is to be discarded cleanly.

**When to use it.** Only during local development experimentation — shaping a seal invocation against a throwaway deliverable on a scratch branch. Never on shared-graph state intended to survive.

**Cleanup path.** The next `./engine/staircase build` replays the JSONL projection back into the substrate from project sources; it will not see the unexported event, and the substrate will be reconstructed without it. The event is intentionally discarded on rebuild — that is the safety property of the flag. Any `.req.yaml` cancellations from `--cancel-inflight` still need a separate `git checkout`.

**Do not pass `--no-export` on a real closure.** A sealed deliverable that never reached the JSONL projection will not survive a fresh checkout or a teammate's rebuild.

## Key rules

- **Aggregation only.** Seal is for any aggregation deliverable — `task`, `milestone`, `epic`, `roadmap` (the `category != solution` boundary). Only the `solution` leaf and non-deliverable nodes refuse.
- **Composition snapshot is the source of truth.** The seal event captures every contributing input ID at seal time; the seal is reproducible from that list alone.
- **Waivers are not soft.** Risk-accepted criteria are sealed-immutable like delivered ones. Further work covering them requires supersession of the parent deliverable, not editing in place.
- **One-way coupling with the engine.** The engine never reads this skill file. Drift between this skill's prose and the CLI flag set is caught by PR blind-review discipline. Skill updates ride alongside CLI changes in the same PR.
- **Mutation stays in the CLI.** This skill orchestrates the seal; it never writes `.req.yaml`, `.events/`, or substrate state by hand.
