---
name: staircase-discuss
description: "Facilitated multi-turn discussion to think an idea, finding, bug, gap, or future direction through and work out what (if anything) should change in the graph. Use when the user wants to talk something over, weigh options, or decide whether/what to author before acting — not for a single-shot triage classification (that is /staircase-wf). Reasons in the conversation but delegates every graph-fact step (classifying, authoring, planning) to the engine."
---

# Discuss — think it through, then route the outcome to the runtime

Answers: **let's talk through this idea / finding / gap / direction — what does it mean, and what (if anything) should change in the graph?**

A **discussion loop**, not a classifier — one of the primary ways to work something out. You bring a half-formed thought; we go back and forth over options, tensions, prior decisions, and consequences until the shape is clear enough to act on. The reasoning lives in the conversation; the moment it crystallises into a concrete graph action, that action is driven through the engine, never faked in skill prose.

This surface is a **thin caller-side orchestrator** (`DEC-CONVERSATIONAL-SURFACE-CALLER-SIDE`): it deliberately opens a session, records each turn, hands off to bounded library workflows via the generic router as intent crystallises, and closes. It holds **no engine state of its own beyond one opaque session id** — no carrier file, no cursor, no run-id bookkeeping. Position lives in the engine turn store and is read back session-filtered.

## The one hard boundary (why this is not the old classifier)

The legacy `/staircase-discuss` read the graph and emitted a typed disposition/recommendation *itself* — a parallel classifier living in a skill. That is retired (`DEC-DISCUSS-SURFACE-DRIVES-WF-DISCUSS`, `DEC-INTERFACE-AS-CONTRACT`, `DEC-WF-DISCOVERY-CLI-PRIMITIVE`): reasoning that produces graph facts belongs in the engine.

This skill honours that boundary precisely:

- **Allowed here (interaction / conversation):** reasoning about the idea, weighing options, recalling relevant decisions/journeys, deciding what to explore next, and framing what a concrete outcome would be. Reading the graph **for context that informs the discussion** (`show`, `query`, `trace`, `/staircase-explore`) is fine — you are gathering understanding, not classifying.
- **Delegated to the runtime (never done in this skill):**
  - **Triage / classification of an observation into a typed disposition + draft recommendation** → route it to **`/staircase-wf`** for typed triage. Do not emit a disposition yourself.
  - **Authoring / changing / deprecating any node** → **`/staircase-author`**.
  - **Planning / decomposition** → **`/staircase-plan`**.
  - **Recording verification** → **`/staircase-evidence`**.

If a turn in the discussion would produce a graph fact, stop reasoning about the outcome and route it. The test: *am I about to state a disposition, or write/decide a node's content, from my own graph reading?* If yes, that goes through the engine.

## The session lifecycle

The discussion runs inside a **deliberately-opened session** that records every turn and can span several router hand-offs before it closes. The session is what makes this surface distinct from a single-shot triage and from the always-on ambient capture: it is opened by an explicit act, it crystallises across multiple runs, and it is closeable. The engine owns the durable **project-scoped ambient `WF-CAPTURE-CONVERSATION` run** — never a session entity (`DEC-WF-CAPTURE-SESSION-BOUNDARY`); the *session* is pure read-time provenance correlation over a caller-minted id stamped on each turn. The skill's only piece of session state is that id.

All engine reads/writes use `--format json`; read `data.*` off the `{status, shape_version, data}` envelope. Read the whole JSON payload into context — it is self-describing, so take each value together with the inline meaning shipped beside it. See the graph-reads rule in CLAUDE.md. `--project <p>` is the project name from `.staircase/config.yaml` (`project.name`).

`--project` is **not** a universal flag. It is accepted (and required) only on the four session/capture commands this skill drives — `wf ensure-capture`, `wf submit-turn`, `wf list-sessions`, `wf resume-session` — because those name the project's ambient capture scope directly. Run-scoped and read commands (`wf get`, `wf observe`, `show`, `query`, `trace`, and the like) resolve the project from `.staircase/config.yaml` and **reject** `--project` with `unknown flag: --project`. Do not add it to those calls. And never build a `wf start` CLI call yourself to hand off intent — crystallization always routes to `/staircase-wf` (§3), never a `wf start` command this skill assembles.

### 1. OPEN — a deliberate developer act

Opening is explicit; ambient capture is not a session. Two steps:

1. **Ensure capture is running.** `./engine/staircase wf ensure-capture --project <p> --format json`.
   - `data.action == "capture_disabled"` → the project has capture gated off. **Decline and stop** per `REQ-WF-DISCUSSION-SURFACE-001.C9`: no session is opened, no turns are recorded, no draft is emitted. Report the decline plainly. Do **not** mint an id or proceed.
   - `data.action == "started"` or `"already_active"` → capture is live; continue. (`already_active` is the common case — the ambient run is project-scoped and durable, so it is usually already up by the time a discussion opens.)
2. **Mint the session id mechanically.** Generate a collision-resistant id with a **command** — `uuidgen` (or an equivalent generator). **Never invent a string** like `"session-1"`: ids are caller-minted and **the engine does not enforce uniqueness**, so a reused id does not error — it silently **merges two conversations into one replay** under the shared ambient run, session-filtered on that colliding id. A guessable literal is the failure mode; a machine-minted uuid is not something a second caller would ever reproduce. The minted id is the **only** session state this skill holds. (The symptom this prevents shows up on resume — see §4: a window containing turns you never authored.)

   ```bash
   SESSION_ID="$(uuidgen)"
   ```

3. **Report the id to the developer** so it survives process death — it is the sole handle for resuming. **Write no carrier file.**

### 2. RECORD-BEFORE-DISTILL — every turn, before interpreting it

Record each raw turn **before** reasoning about it, so the verbatim utterance is durable provenance regardless of what the discussion later distils (`REQ-WF-DISCUSSION-SURFACE-001.C4`). The session id rides as first-class provenance via `--session`:

```bash
./engine/staircase wf submit-turn --project <p> --session "$SESSION_ID" \
  --speaker developer --text "<verbatim turn>" --format json
```

`--speaker` is `developer`, `ai`, or `system`. **Verify the echo:** `data.session_id` in the `SubmitTurnResult` must equal the id you passed. A silently-omitted or mismatched flag exiles the turn from every future session-filtered replay — check it, do not assume it.

**If `data.capture_disabled == true`, read `data.decline_cause` — do not assume capture was gated off.** On this surface the flag means only "no ambient run was active", which most often means the project's run **died**, not that capture is switched off. The turn was not captured, but it *is* recorded on the project's decline trail. Branch on `data.decline_recoverable`:

- **`true`** (e.g. `ambient_run_terminated`, `no_ambient_run_established`) → the turn is recoverable. Re-run `wf ensure-capture --project <p>`, then **resubmit the turn**. Do not stop; stopping here is what loses the dialogue permanently.
- **`false`** (e.g. `capture_not_enabled`, `engine_non_capture_tier`) → this is a configuration state and nothing you do in-session changes it. Treat it as a C9 decline and stop, reporting `data.decline_cause_gloss` verbatim.

Every declined turn is retrievable afterwards with `./engine/staircase wf list-declines --project <p> --format json`.

**Verbatim provenance is not guaranteed for very large turns.** A turn longer than **16 KiB (16384 bytes)** is stored **truncated** to that cap, and submit-turn still returns `status: ok` — truncation is not an error, so the `ok` alone does not prove the full text was kept. When the stored turn was truncated, the engine stamps the **original** byte length under the turn's `truncated_from_bytes` attribute. So when recording a large paste, do **not** assume the whole thing was stored: either keep the turn under 16 KiB by **splitting the paste across several turns**, or accept the truncation knowing `truncated_from_bytes` on the stored turn records what the full length was. Record-before-distill only preserves what actually fits — a silently-truncated turn is a broken provenance link the same way an exiled turn is.

Record the developer's turns and your own material replies alike, so a resumed session reconstructs both sides.

### 3. HANDOFF — crystallization routes to the generic router

When intent converges on a concrete graph action, **do not perform it here** — hand off to the sibling skill **`/staircase-wf`** (the generic router), passing the natural-language intent. Carry **no hardcoded workflow ids and no hardcoded stage names**: the router resolves which library workflow the intent maps to from the engine catalogue (`REQ-WF-DISCUSSION-SURFACE-001.C2`, `.C7`). A single session may sequence several such runs as the discussion clarifies different actions — recording turns throughout.

| The discussion concluded… | Hand off to |
|---|---|
| "this observation needs triaging into a typed disposition + draft" | `/staircase-wf` (it classifies, not you) |
| "we should author / change / deprecate node(s)" | `/staircase-author` |
| "this needs planning / decomposition" | `/staircase-plan` |
| "record that tests verify this" | `/staircase-evidence` |
| "nothing to change — already covered / out of scope / deferred" | say so, with the reason; no graph action |

`/staircase-wf` is a **sibling skill invocation**, not a CLI command. For deferred-but-real outcomes, remember the discipline: deferred work still needs a requirement in the graph — route it to `/staircase-author`, don't leave it only in the conversation.

**Confirm the hand-off actually landed before recording it as done — the same way RECORD verifies the echo.** A router hand-off is only crystallized once you have read back a real run handle from the router: the `/staircase-wf` hand-off starts a run and reports its handle, which carries a `run_id` (alongside a `workflow_id`). You read that `run_id` back from `/staircase-wf`'s report — **do not** build a `wf start` call yourself (§ opening note) — and can independently cross-check it via `./engine/staircase wf runs list --format json`. **Read the router's `run_id` back before recording the outcome turn.** A hand-off narrated as complete with **no confirmed `run_id`** is not a hand-off — it is a claimed run that may never have started, and recording it as done fabricates provenance for an action that did not happen. If no `run_id` came back, treat the hand-off as **not landed**: report that plainly and do not record it as crystallized. This is the crystallization-side mirror of RECORD's echo check — a run with no `run_id` is exactly as broken as a turn with no matching `session_id`.

### 4. RESUME — a fresh process re-grounds from the turn store

If the session id is not to hand (the process died and reopened), the engine turn store is the only durable home — there is **no carrier to reload**.

1. **Find the session** if you don't have the id: `./engine/staircase wf list-sessions --project <p> --format json` returns the project's distinct sessions as `data.sessions[]` of `{session_id, last_activity, turn_count}`, ordered **most-recently-active first** (so the session to resume is usually `data.sessions[0]`), alongside a self-describing `data.legend`. Pick the one to resume by its last-activity.
2. **Restore position in one read:** `./engine/staircase wf resume-session --project <p> --session "$SESSION_ID" --format json`. It returns, in a single call:
   - `data.window` — the most-recent (tail) bounded turn window, in **oldest-first order** (ascending within the window): read it top-to-bottom to replay the conversation chronologically — the last entry is the newest, not the first. Re-ground the discussion from these replayed turns.
   - `data.total_turns` — the session's full turn count (the window is bounded; this is the true size).
   - `data.ambient_run_id` — the run the session's turns are correlated on.
   - `data.ambient_run_active` — the ambient run's live flag.
   - `data.legend` — a self-describing map from each enumerated value token in this response to its one-line meaning (`DEC-READ-RESPONSE-MEANING-NOT-PROCEDURE`). It is dynamic — only tokens actually present are glossed — and always a present object. Read the meaning of a value from here; do not infer it.

   The window is **bounded to the most-recent 256 turns by default** (the turn store's page size). For a session longer than that, pass `--limit N` to widen or narrow the tail window; `data.total_turns` always reports the full length regardless of the bound, so compare it against the window size to know whether earlier turns were elided.

   **Never compute a cursor, compare run ids, or read inside any turn blob** — `resume-session` re-anchors the run and hands back the window, legend, and flag directly.

   **Watch the window for contamination.** Because the engine does not enforce session-id uniqueness (§1), a colliding id merges another caller's conversation into this same session-filtered replay with no error. The detectable symptom is right here in `data.window`: **turns you never authored** — an unfamiliar thread, speakers or content from a different discussion interleaved with yours. If the replayed window contains turns that are not part of this conversation, the session id collided; do **not** trust the merged window as your history. Report the contamination and re-open under a freshly-minted uuid rather than continuing on a poisoned id.
3. **Honour the Active flag — but do not read it as "capture is disabled".** If `data.ambient_run_active == false`, there is no ambient run to resume into. This is distinct from a genuinely-empty session (`total_turns == 0`), and it is **also** distinct from capture being gated off: the far more common cause is that the project's ambient run terminated. Do not report a capture-disabled state and stop. Re-run `wf ensure-capture --project <p>` first; if it returns `started` or `already_active`, capture is live again and you may resume. Only if `ensure-capture` itself returns `capture_disabled` is the project genuinely gated off — that is the surface where the token means what it says.
4. **Continue** by submitting further turns with the same `--session "$SESSION_ID"` (step 2, RECORD). Post-resume turns extend the same session; they never start a new one.

### 5. CLOSE — a deliberate developer act

Closing is an explicit act that ends the session: stop recording turns under `$SESSION_ID` and drop the id. **Do not cancel the shared project-scoped ambient capture run** — it is durable and project-wide; other work depends on it. Closing the session is purely the caller ceasing to use the id; there is no engine session to terminate.

## The loop, end to end

1. **OPEN** (§1) — ensure capture, mint the id, report it.
2. **Reflect** the user's opening thought back in a sentence so the framing is shared; **RECORD** it (§2).
3. **Gather context (read-only, to inform — not to classify).** Pull only what the discussion needs: `./engine/staircase show <id> --format json`, `query "<terms>"`, `trace <id>`, or `/staircase-explore` for a wider sweep. Surface prior decisions that bear on it, existing coverage, tensions — as discussion input, not a verdict.
4. **Discuss — the back-and-forth**, RECORDING each substantive turn (§2). Ask one thing at a time; do not stack questions. Push back with evidence when the direction has a problem — a working session, not a rubber stamp. Work through: what is really being asked and its scope; what options and trade-offs exist; whether any recorded decision constrains or conflicts with it; whether it is already covered; and what "done" looks like.
5. **Converge and HAND OFF** (§3) each concrete action to the router / authoring / planning / evidence skill.
6. **CLOSE** (§5) when the developer ends the discussion; or the process dies and a later **RESUME** (§4) re-grounds it.

## Weak-agent legibility

This lifecycle must be executable by a **weak (Haiku-class) agent** reading only this file — the session distinctness, the record-before-distill order, and the zero-arithmetic resume are the load-bearing behaviours. Before shipping a change to this skill, run a Haiku walkthrough of the full open → record → crystallize → resume → close lifecycle and confirm each step is followed from the prose alone.

## Related surfaces

- **`/staircase-wf`** — the generic router; where triage/classification and any other library workflow actually runs (the crystallization hand-off target).
- **`/staircase-explore`** — read-only graph navigation for broader context before or during a discussion.
- **`/staircase-author`** — create/update/deprecate nodes once the discussion concludes something should change.
