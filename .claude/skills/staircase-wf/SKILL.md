---
name: staircase-wf
description: "Generic workflow router: reaches ANY library workflow from natural-language intent with no hardcoded workflow IDs or stage names. Derives intent tags, resolves via `wf list --intent`, disambiguates via `wf describe` briefs, starts the run, then drives a generic per-interrupt dispatch loop — reading each pending state's executor_brief + bounded input_data, resolving its recommended_tier to a model via one skill-local table, spawning a fresh subagent, and submitting the response via `wf interrupt`. Origin-agnostic: routes shipped, project-defined, and third-party workflows identically. Use to run any library workflow (authoring, triage, planning, review, …) when you want the engine catalogue — not a per-workflow surface — to pick and drive it."
---

# Generic Workflow Router — `/staircase-wf`

Answers: **which library workflow does this intent map to, and how do I drive it end-to-end?**

One thin skill that reaches *any* library workflow from natural-language intent. It carries **no hardcoded workflow IDs and no hardcoded stage names** — routing comes from the engine catalogue (`wf list` / `wf describe`) and every interrupt is dispatched from the state's own `executor_brief`, served by the engine. This replaces the per-workflow dispatcher pattern (a dispatcher SKILL.md that knew one workflow's stage names and shipped one stage-reference file per state); a new workflow or a new stage needs zero edits here.

Two things, and only two things, are skill-local by design (per `DEC-EXECUTOR-TIER-VOCABULARY`): the **tier→model table** below, and the ranking heuristic applied *over the engine-returned candidate set*. Everything else — the workflow set, each state's instructions, the tier recommendation — comes from the engine at runtime.

The authoritative data source is the Go engine CLI at `./engine/staircase`. All commands support `--format json`; always use it (the JSON envelopes are optimised for machine consumers). Read `data.*` off the `{status, shape_version, data}` envelope.

## Arguments

- `$ARGUMENTS` — natural-language intent describing what you want to do (e.g. "author a new requirement for rate limiting", "triage this observation", "review the changes on this branch"). Optional: if a run of some workflow is already active, the skill detects and resumes it regardless of arguments.

## Discovery discipline (optimistic, not eager)

This skill runs against a live, evolving engine; training-time knowledge of the CLI may not match the binary.

1. **Attempt the canonical invocation directly** — the commands here are known to work against the engine that shipped with this skill. Do not preface every run with a discovery step.
2. **On an unknown-command / unknown-flag failure**, consult the targeted capability listing and retry once:
   ```bash
   ./engine/staircase --format json capabilities <command-path>
   ```
3. **Only fall back to the full listing** (`capabilities` with no argument) when the targeted query doesn't resolve it — full listing is higher token cost.
4. **Never eagerly enumerate the full CLI surface at session start.**

## Step 0 — Confirm the binary and detect an active run

Build if missing (Go's cache makes this ~1s when nothing changed):

```bash
go build -C engine -o staircase ./cmd/staircase
```

The dispatch loop is **cross-process resumable** — a fresh session picks up exactly where a prior one left off. So the first thing to do, every invocation, is check for an already-running workflow before routing a new one:

```bash
./engine/staircase wf runs list --status running --format json
```

`data.runs[]` carries `{run_id, workflow_id, state_id, pending_state_id, started_at, ambient}`. `ambient` is engine-reported (`REQ-WF-ROUTER-SKILL-001.C4`) — true when the run's workflow declares itself a durable, long-lived background member (e.g. an ambient capture workflow) that advances on its own schedule independent of any caller intent; false for a caller-owned request-response run.

**Select the first run with `ambient == false` and a non-empty `pending_state_id`**, and jump straight to **Step 4 (Dispatch loop)** with that run — do not start a new one. **Never select an `ambient == true` run, regardless of its `pending_state_id`.** An ambient run is not the router's to drive — not when it is parked at an interrupt (submitting to it would hijack an unrelated caller intent onto the ambient run's own state), and not when it has settled between cycles with an empty `pending_state_id` (that is the ambient run idling, not a resumable interrupt, and `--status running` still reports it with an empty `pending_state_id` rather than hiding the row). An ambient run ends only by an explicit `wf cancel`, never by this router reaching a terminal for it. Only route a new workflow (Steps 1–3) when no non-ambient run is active to resume.

Keep `--status running`, not `--status all`: a terminal run's `pending_interrupt` row is not cleared by termination, so `--status all` can surface a **completed** run with a stale non-empty `pending_state_id` — selecting it would submit `wf interrupt` against a run that already finished. `--status running` excludes terminal rows by construction, which is exactly what Step 0's selection needs.

## Step 1 — Resolve intent to a candidate set

`wf list --intent` is an **exact-tag, conjunctive filter** — not a semantic matcher. The skill derives candidate intent tags from the caller's NL, then filters:

```bash
# Derive tags from the intent, then filter (repeat --intent to AND them)
./engine/staircase wf list --intent <tag> [--intent <tag> …] --format json
```

`data.workflows[]` entries carry `{id, category, origin, family?, intent_tags[], purpose, entry_contract_summary, terminal_output_summary, states[]}`. Note `family` is **optional** — not every workflow has it.

Tag derivation: pull the salient verb/noun from the intent ("author a requirement" → `author`, `create`; "triage this note" → `triage` or the tag the triage workflow advertises). Start broad (one tag) and narrow (add tags) if the set is large. If a tag guess returns nothing, widen — try a single more-general tag, or list unfiltered (`wf list` with no `--intent`) and match against `intent_tags` / `purpose` yourself.

**The engine supplies the candidate set; the skill's ranking is applied only over that set.** Never bake a workflow ID into the skill.

## Step 2 — Disambiguate via the workflow brief

For each candidate, read its brief to decide fit — never guess from the ID:

```bash
./engine/staircase wf describe <workflow-id> --format json
```

`data` carries: `id`, `category`, `origin`, `family`, `brief` (`{purpose, intent_tags, when_to_use, when_not_to_use, primary_caller}`), `entry_contract` (`{required_inputs[]: {name, schema}, requires_prerequisite[]}`), `terminal_output_schema.fields[]`, `state_count`, `interrupt_states[]`, and `executor_tier_hints` (`{per_state: {<state>: <tier>}, unique_tiers[]}`).

Read `brief.purpose`, `brief.when_to_use`, and `brief.when_not_to_use` — they are what distinguish two candidates. Rank the engine-returned set by fit to the caller's intent.

**On an empty or ambiguous candidate set, ask the caller to pick** from the described candidates rather than guessing. Present each as `id — brief.purpose` (one line each) and wait.

> **Origin-agnosticism (C1 / `REQ-WF-ROUTER-SKILL-001.C3`).** Never branch on a workflow's `origin` field. Shipped, project-defined, and signed third-party workflows route through Steps 1–4 identically — the only place `origin` is even read is if the caller explicitly asks to filter by it. The routing and dispatch logic must not change based on where a workflow came from.

## Step 3 — Start the run

Read the selected workflow's `entry_contract` (from Step 2's `describe`) and construct the required inputs from the caller's context. Inputs are a JSON object keyed by each `required_inputs[].name`; honour each field's `schema`.

**Discriminated-union subjects** are constructed by their `mode` discriminator. When a required input's schema has `type: "discriminated_union"` with a `discriminator` (commonly `mode`) and `variants`, pick the variant that matches the caller's subject and supply the discriminator plus that variant's required fields. Example — a `subject` with variants `observation_text` / `node_reference` / `draft_proposal`:

```json
{"subject": {"mode": "observation_text", "observation": "<the caller's note>"}}
```

Start the run, capturing `run_id`:

```bash
./engine/staircase wf start <workflow-id> --inputs '<json>' [--profile <p>] --format json
```

`data` is `{run_id, workflow_id, started_at}`. `--profile` sets the terminal gating profile; pass it only when the caller specifies one (the engine defaults otherwise).

## Step 4 — Dispatch loop (generic, per interrupt)

> **Three notes in this step are temporary engine-gap workarounds, not permanent router knowledge.** Where the `wf` surface does not yet self-describe its own responses, the skill compensates so a router works against the engine *as it is today*. Each is tracked as an emergent-defect node under `DEL-EPIC-MAINTENANCE` (the `wf` runtime self-describing its interrupt outcome, durable terminal drive, and validator-field vocabularies); when those land, delete the corresponding note here. The three: (a) reading a field's accepted vocabulary from the brief instead of the schema, (b) detecting a semantic rejection by diffing the pending state, and (c) keeping a `wf observe` sidecar alive so a terminal drive completes. They are marked **[engine-gap bridge]** inline.

The workflow is a state machine. Whenever it pauses at a state that needs an executor, the run **parks as a pending interrupt** — this includes every `llm`-action state (an `interrupt_states: []` in `describe` does **not** mean the run won't pause; `llm` states park too). Drive the loop until the run reaches a terminal state:

```bash
./engine/staircase wf runs get <run-id> --format json
```

`data` carries `{run_id, workflow_id, state_id, pending_state_id, input_data, output_schema, executor_brief?, started_at}`.

**Loop while `pending_state_id` is non-empty:**

1. **Read the bounded context** from `wf runs get`:
   - `input_data` — the `input_schema`-declared subset the state is authorised to see. Executors read it verbatim; no extra filtering.
   - `output_schema` — the shape the response must validate against.
   - `executor_brief` — the state's inline executor spec: `{objective, rules[], heuristics[], validator_summary}`, where `rules` / `heuristics` are `{value, origin}` records. **This is the entire instruction for the subagent** — there are no per-stage files. Note the key is **omitted** when a state declares no brief.

2. **Resolve the tier** from `wf state-info`, never from the `executor_brief` (which carries objective/rules/heuristics/validator content, not the tier):
   ```bash
   ./engine/staircase wf state-info <workflow-id> <pending_state_id> --format json
   ```
   `data.states[0]` carries `recommendation_status` and (when `recommendation_status == "recommended"`) `recommended_tier`. Resolve to a model via the **tier→model table** below. See **Un-hinted states** for the `recommendation_status != "recommended"` case — a parked interrupt can legitimately carry no engine recommendation.

3. **Spawn a fresh subagent** at that model, hydrated **only** with the `executor_brief` plus the bounded `input_data` (and the `output_schema` so it can self-validate). Passing conversation history or anything beyond the bounded context defeats reproducibility and breaks the bounded-execution guarantee. The subagent's job: produce a response that validates against `output_schema`.

   **The `executor_brief` is the complete spec — the subagent must not seek anything outside it.** *[engine-gap bridge]* In particular, a workflow-specific field may have a bare `output_schema` type (e.g. a `disposition` typed `{"type": "string"}`, or a custom type name) whose **valid values are named in the `executor_brief.objective`/`rules` prose**, not enumerated in the schema. The subagent reads its allowed vocabulary out of the brief; it does **not** read project files, test fixtures, or engine source to discover enum members. If the brief genuinely does not constrain a value, that value is the subagent's judgement to make from the brief's intent — not a signal to go hunting outside the bounded context.

4. **Submit the response** (note the flag is `--state-id`, and both it and `--response` are required):
   ```bash
   ./engine/staircase wf interrupt <run-id> --state-id <pending_state_id> --response '<subagent-output-json>' --format json
   ```
   **Two distinct rejection paths — handle both:**
   - **Schema rejection (exit 5).** The response didn't match `output_schema`. Read the field violations from the error, re-spawn the same subagent with the rejection appended as correction context, and resubmit.
   - **Semantic rejection (exit 0, `status: ok`, but the run re-parks at the *same* state).** *[engine-gap bridge]* A submission can be *schema*-valid yet fail the state's *validator* (e.g. a value not in the workflow's vocabulary, an out-of-scope reference, an empty list the state requires non-empty). The `wf interrupt` call returns success, but the next `wf runs get` shows the **same** `pending_state_id` with the same-shaped `input_data`, now carrying validator findings. Detect this by comparing the pending state before and after: if it did not advance, the submission was rejected. Read the findings — they surface in `wf runs get`'s `input_data` (e.g. a `__validator_findings__` field) and in the audit events via `wf observe` (`stage_rejection_field` / `stage_rejection_reason`) — then re-spawn the subagent with the finding as correction context and resubmit. Do **not** treat `wf interrupt` exit 0 as "accepted"; a re-park at the same state means rejected.

   A state may legitimately be **structurally unsatisfiable** for the given inputs (e.g. a decompose state that needs an in-scope criterion when the target has zero criteria). If no valid response exists after reading the findings, stop and report *why* to the caller — do not loop.

5. **Advance and repeat** — re-run `wf runs get`. When `pending_state_id` names a *new* state, the engine advanced; drive that interrupt. When it names the *same* state, see the semantic-rejection path above.

**Terminal** is an empty `pending_state_id` (or the workflow's defined already-terminal error). **Some workflows are cycles with no terminal state** — `wf runs list`'s `ambient` field says so (Step 0); an ambient run settles with an empty `pending_state_id` and no terminal payload between cycles, and is ended by an explicit `wf cancel`, not by reaching a terminal. This loop only ever drives a run Step 0 selected, which is never an ambient one.

**Keep a `wf observe` running while you drive the final interrupt to terminal.** *[engine-gap bridge]* A workflow's terminal-output validation and projection run in the run's live drive goroutine; if the last `wf interrupt` is a short-lived process that exits immediately, that drive can be **cut short and the run reports `run_failed` ("run failed in another process")** even though your response was valid. Start `wf observe <run-id>` as a background sidecar *before* (or concurrently with) submitting the interrupt that will reach terminal, and keep it alive until the run leaves the running set — the observe stream keeps a live adapter attached so `terminalResult` completes. This is the same discipline the engine's own CLI-journey tests use. Then read the terminal payload from that same `wf observe` stream (or re-run it on the completed run):

```bash
./engine/staircase wf observe <run-id> --format json
```

`wf observe` streams NDJSON events; a completed run ends in a `run_completed` event carrying `{terminal_state_id, outputs}` (present the terminal `outputs` to the caller), and a failed run ends in `run_failed`. On a **still-parked** (non-terminal) run, `wf observe` **blocks/streams live** rather than returning — so use it as the terminal reader on a run you have driven to completion, and as the background sidecar above; to *diagnose* a mid-run rejection without blocking, read `wf runs get` (which returns immediately) and, if you need the audit detail, run `wf observe` as a background process you stop once you've read the rejection events.

Because each invocation re-detects the active run (Step 0), the loop survives a process restart mid-run.

## Tier→model table

The engine names only abstract, vendor-neutral tiers (per `DEC-EXECUTOR-TIER-VOCABULARY`); this skill binds them to concrete models in this **single** table and nowhere else. The engine never names a model; the skill never hardcodes a tier list beyond this table. Update **only** this table when the model lineup changes — workflow definitions and engine config stay untouched.

| Tier             | Model                        |
|------------------|------------------------------|
| `small-fast`     | `claude-haiku-4-5`           |
| `mid-tier`       | `claude-sonnet-5`            |
| `reasoning-tier` | `claude-opus-4-8`            |

### Un-hinted states — the `no_hint` fallback

`wf state-info` returns `recommendation_status: "no_hint"` (and no `recommended_tier`) for a state that declares no `executor_hint`. Two kinds of state land here:

- **Non-LLM command/terminal states.** The engine executes these in-process; **no model runs there**, so the dispatch loop never spawns a subagent for them — they don't park needing an executor. Nothing to resolve.
- **An `llm`-action state that parks needing an executor but declares no hint.** This is reachable and load-legal: whether a state runs on a wired model or as a caller-filled interrupt is a runtime fact the engine's load layer cannot see, so it can never guarantee every dispatched interrupt carries a tier. The engine contract for `no_hint` is explicit: *"executor falls back to its own default"* — the engine deliberately delegates this one choice to the executor. So when the dispatch loop reaches an interrupt with `recommendation_status == "no_hint"`, apply the documented fallback: **treat it as `mid-tier`** and resolve `mid-tier` through the table above. (An `llm` state that is *intended* for autonomous dispatch should carry a hint — that omission is an authoring smell the workflow's own lint catches upstream, not something the router adjudicates; the router just needs a safe default for the case the load layer cannot rule out.)

`mid-tier` is the fallback because `DEC-EXECUTOR-TIER-VOCABULARY` names it "the default for states without strong hint signals either way." The fallback names a **tier**, not a model — so the model it resolves to stays user-editable in the single table (there is no second knob). Do **not** invent a different tier per state, and do **not** read a tier off `executor_brief`; the engine owns the recommendation when it makes one, and this table owns the single fallback and every model binding (C2 / `REQ-WF-ROUTER-SKILL-001.C2`).

Only `recommendation_status` values other than `"recommended"` and `"no_hint"` (e.g. an `unmappable_hint` — a *declared* hint that resolves to no tier) signal an authoring defect: the author declared a dispatch intent the engine could not honour. Surface those (report the workflow + state) rather than dispatching.

## Key rules

- **No hardcoded workflow knowledge (C1).** No workflow IDs, no stage/state names, no per-stage instruction files anywhere in this skill. Routing is catalogue-driven (`wf list` / `wf describe`); dispatch is `executor_brief`-driven per interrupt.
- **Tier from `wf state-info`, model from this one table (C2).** Never read the tier off `executor_brief`. Never bind a model anywhere but the table above. The engine owns routing; the skill owns only the model binding.
- **Origin-agnostic.** Never branch on `origin`. Shipped / project / third-party workflows route identically.
- **Bounded subagent context.** Each interrupt's subagent gets only the `executor_brief` + bounded `input_data` (+ `output_schema`). Nothing else.
- **Ask, don't guess, on ambiguity.** Empty or ambiguous candidate set → present the described candidates and let the caller pick.
- **Cross-process resumable.** Detect an active run first (Step 0); resume its dispatch loop instead of starting a new workflow.
- **Never drive an ambient run (C4).** Step 0 selects only a run with `ambient == false`. An `ambient == true` run — parked or idling between cycles — is never selected, never interrupted, never driven to terminal by this router.
- **Optimistic discovery.** Attempt the canonical invocation; consult `capabilities <path>` only on failure.
