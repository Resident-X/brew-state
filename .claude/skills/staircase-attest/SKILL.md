---
name: staircase-attest
description: "Records a Tier-1 or Tier-2 attestation that a contributing composition meets a criterion's intent, via `staircase attestation attest`. Use to close out a single review-ready criterion — a deliverable criterion (TSK/SOL/MS/DEL/RM-*.Cn, mechanical) or a requirement criterion (REQ/OBL/JRN-*.Cn, substantive). Use when an evidence event lands, when a historical criterion resurfaces as review-ready, or as the post-merge closure step after a slice ships. For sealing an aggregation deliverable (task/milestone/epic/roadmap), use staircase-seal instead."
allowed-tools: "Bash"
---

# Attest a Criterion

Answers: **Does the contributing composition genuinely meet this criterion's intent — and if so, record the attestation honestly?**

Attestation is the bridge act: an evidence node citing the contributing composition, recorded against one criterion. The CLI is the only mutation surface; this skill is workflow only — it never writes graph state directly. Read the whole JSON payload into context — it is self-describing, so take each value together with the inline meaning shipped beside it. See the graph-reads rule in CLAUDE.md.

## The two tiers this skill records

- **Tier 1 — deliverable-criterion attestation (mechanical).** A `TSK/SOL/MS/DEL/RM-*.Cn` criterion is a *test spec* of what the deliverable promised. If the contributing solution carries passing evidence, the attestation confirms it. Decision: almost always `attest`.
- **Tier 2 — requirement-criterion attestation (substantive).** A `REQ/OBL/JRN-*.Cn` criterion is the *final-state intent*. The composition may or may not reach it. Three honest outcomes — `attest`, `finding`, or `insufficient` (Step 5).

**Sealing an aggregation deliverable (Tier 3) is not this skill — use `/staircase-seal`.** Only the **solution** leaf is not sealable — it closes implicitly once its `.Cn` criteria are attested here. A **task** IS an aggregation deliverable: like a milestone or epic it is closed by a deliberate seal over its cascade (`/staircase-seal`), not implicitly. Seal eligibility is the single `category != solution` boundary (`IsAggregationDeliverable`), so attesting a task's `.Cn` criteria here does not close the task — the task still needs its own seal.

## Arguments

- `$0` — the criterion ID to attest (e.g. `REQ-PARSE-001.C1`, `SOL-PARSE-SERDE.C2`), or an isolation-domain ID (`MS-*`, `SOL-*`) whose review-ready criteria you want to walk one at a time.

## Discovery discipline

The commands below work against the engine version shipped with this skill. On unknown-flag failure, run `./engine/staircase --format json capabilities attestation attest` once and update the invocation. Do not eagerly enumerate the CLI surface at session start (`REQ-CANONICAL-ENGINE-001.C6`).

## Checklist

Copy and tick as you go:

```
Attest progress:
- [ ] Step 1 — Load the criterion and its composition
- [ ] Step 2 — Verify contributing evidence on disk (NOT the queue field)
- [ ] Step 3 — Tier-2 honesty checks (final-state read)
- [ ] Step 4 — Adversarial verification (independent refute pass)
- [ ] Step 5 — Decide: attest / finding / insufficient
- [ ] Step 6 — Compose the rationale
- [ ] Step 7 — Invoke attestation attest
- [ ] Step 8 — Confirm the criterion cleared review-ready
```

## Step 1 — Load the criterion and its composition

```bash
./engine/staircase --format json show <CRITERION-ID>
# Full composition for one criterion (every contributing input + its complete active_evidence_ids):
./engine/staircase --format json next --explain <CRITERION-ID>
```

`show` returns the criterion text — the intent you are attesting against. `next --explain <CRITERION-ID>` returns the criterion's full **composition** in `data.explain.composition[]`: each contributing input as `{id, title, active_evidence_ids[]}` — the input identifier and the complete enumeration of its load-bearing active evidence. That tells you which solution(s) to cite with `--input` in Step 7 and which evidence backs them. (The open-ended `staircase next` answer surfaces the criterion as a `review-ready` action so you can find it; `--explain` hydrates its full composition.) Either way, the evidence itself is read from disk in Step 2, not from the payload.

If `$0` is an isolation domain (`MS-*` / `SOL-*`), run `./engine/staircase --format json next --throughput --scope $0` and walk its `review-ready` actions individually.

## Step 2 — Verify contributing evidence on disk (MANDATORY)

**Read the evidence from `specs/evidence/`, not from the queue's composition payload alone.** The composition is the map; the filesystem is the territory.

```bash
ls specs/evidence/ | grep -i "<SOL-ID>"          # every EVD the contributing SOL has
./engine/staircase --format json show <EVD-ID>   # confirm result=pass, status=active, observed_at past-UTC, satisfies link
```

A criterion may only be recorded `finding` or `insufficient` AFTER confirming on disk that the load-bearing evidence is genuinely absent or weak. Trusting a summary field instead of the actual evidence files is how false "not done" verdicts get recorded.

Confirm the attestation does not already exist:

```bash
ls specs/evidence/EVD-<CRITERION-ID>-ATTEST*.req.yaml 2>/dev/null
```

If it exists, the criterion is already attested — stop.

## Step 3 — Tier-2 honesty checks

Tier 1 is mechanical — if the criterion is a deliverable criterion whose contributing evidence passes, skip to Step 5.

For a Tier-2 (requirement) criterion, answer three questions before deciding:

1. **Final-state read.** Re-read the criterion text. Strip the contributing-SOL framing. Does the composition reach the intent *as stated*, or only "what the SOL set out to do"?
2. **Composition still active?** Has direction shifted since the SOL was authored? If newer work has superseded it, the cited evidence may no longer reflect the tree.
3. **Acknowledged deferral vs unstated gap.** A deferral the SOL's scope boundary explicitly names is honest *if the rationale records it*. An unstated gap is not — that is a `finding`.

## Step 4 — Adversarial verification

The single most load-bearing control: a plausible-but-wrong attestation survives a friendly read and fails a hostile one. For any non-mechanical Tier-2 attest, get an **independent skeptical pass** before recording — re-examine the cited evidence against the current code with intent to *refute* the attest, ideally delegated to a fresh reviewer blind to your reasoning. Check: do the named test functions still exist? Do they assert the criterion's specific clause, or only its spirit?

Scale the rigour to the stakes — a mechanical Tier-1 confirmation needs none; a Tier-2 attest on a compliance-bearing criterion warrants one. The discriminator that resolves most disputes:

- Cited test **moved or renamed but still present** (a quick `rg` finds it elsewhere) → still `attest`; note the stale reference.
- A clause is **genuinely unverified** (no asserting test, or the test asserts something weaker) → `finding`.

## Step 5 — Decide

| Outcome | When | Action |
|---|---|---|
| `attest` | composition demonstrably reaches the intent (possibly a narrower scope, recorded in the rationale) | Steps 6–7 |
| `finding` | a real residual gap against the intent | do NOT attest — see below |
| `insufficient` | contributing evidence is too weak to judge | do NOT attest — see below |

**`finding` and `insufficient` have no separate command.** The honest mechanism is: do not attest. The criterion stays `review-ready` in the queue — that is the durable signal that the gap is open, and it reads as a requirement-health metric, not a work item. Surface the gap to the user: the criterion, the specific unmet clause, and what would close it. The criterion is trivially re-attestable later once superseding work lands. A met-but-unattested criterion is safe; a false attest is not.

## Step 6 — Compose the rationale

The rationale is the only durable artefact of the honesty check. If any slot would be empty, the wrong decision is being made.

**Tier 1:**

```
Tier 1 attestation of {CRITERION-ID}.

The deliverable criterion specifies: {one-sentence paraphrase}.

Contributing solution {SOL-ID} carries {EVD-ID} ({method}, result {result}, observed {observed_at}). It covers the test spec as written: {specific match between the evidence and the criterion}.

No residual gap against the deliverable criterion's scope.
```

**Tier 2:**

```
Tier 2 attestation of {CRITERION-ID}.

Final-state intent: {what the requirement criterion actually requires — not what the SOL set out to do}.

Composition: {SOL-IDs} with active evidence {EVD-IDs}.

Intent fit: {the specific match between the composition's behaviour and the intent; cite evidence references where the match is non-obvious}.

Acknowledged scope boundary: {the SOL's explicitly deferred scope, naming the follow-up task/REQ; or "none"}.

Decision: attest. No unstated gap against the criterion's final-state intent.
```

The scope-boundary slot is mandatory. Write "none" explicitly when the SOL covers the criterion fully, so the reader knows the absence is deliberate.

## Step 7 — Invoke attestation attest

Preview first (omit `--confirm` — preview exits non-zero and writes nothing), read back the constructed intent, then apply with `--confirm`.

```bash
./engine/staircase --format json attestation attest <CRITERION-ID> \
  --evidence-id "EVD-<CRITERION-ID>-ATTEST" \
  --attestor david --actor david \
  --method analysis \
  --input <CONTRIBUTING-INPUT-ID> [--input <ANOTHER-INPUT-ID>]... \
  --rationale "<the Step-6 rationale>" \
  --confirm
```

- `--method analysis` for both Tier 1 and Tier 2 — the attestor is reviewing prior evidence, not generating a new test artefact. (`--method test` is only for direct-evidence cases where the attestor is the one running the test.)
- `--evidence-id` convention: `EVD-<CRITERION-ID>-ATTEST`. The created node carries `result: pass`, an artifact of `kind: composition` whose `cites` slot enumerates the `--input` IDs, `attested_by: <attestor>`, and a `satisfies` link to the criterion.
- One `--input` per contributing input from the Step-1 composition. Zero inputs is rejected by the engine (empty `cites` slot fails schema validation), so a Tier-2 attest must cite the composing solution(s) explicitly.

## Step 8 — Confirm the criterion cleared review-ready

```bash
./engine/staircase --format json next --throughput --top <N>
```

The attested criterion must no longer appear as a `review-ready` action. If it still does, the attestation did not land — re-read the `attest` output for an error (a common cause is the `--evidence-id` colliding with an existing node, which means it was already attested). Any criterion still review-ready after this skill runs is a recorded finding by design, not an omission.

## Identity convention

All attestations use `--actor david --attestor david`: the user is the durable signing identity, Claude is the operator. `--attestor` is recorded on the evidence node's `attested_by`; `--actor` on the mutation envelope and every event the mutation produces. Omitting `--actor` falls back to the operating-system user with a stderr warning — always pass it explicitly.

## Key rules

- **Read evidence from disk, not a summary field.** The queue composition is the map; `specs/evidence/` is the source of truth. Never record a finding or insufficient without confirming the evidence is genuinely absent on disk.
- **Tier 2 is substantive, not mechanical.** The criterion is the final-state intent. Attest only what the composition actually reaches; name any narrower scope in the rationale.
- **A finding is a legitimate outcome, not a failure.** Leaving a criterion review-ready is the honest signal that intent is unmet — never attest just to clear the queue.
- **Adversarial verification is load-bearing for Tier 2.** A friendly read passes plausible-but-wrong attestations; a hostile one catches them.
- **Mutation stays in the CLI.** This skill never writes `.req.yaml` or substrate state by hand. The engine validates every intent before it persists.
- **One-way coupling with the engine.** The engine never reads this skill file. Drift between this skill's prose and the CLI flag set is caught by PR blind-review discipline; skill updates ride alongside CLI changes in the same PR.
