# Staircase Skills

Workflow skills for the Staircase requirement graph. Each skill is one step — they chain naturally but work independently.

Skills delegate to the `./engine/staircase` CLI for every query and mutation. The CLI reads from `.staircase/index.db`, which the apply pipeline keeps fresh on every `author --confirm`.

## Workflow

```
status/tree -> queue -> explore -> discuss -> wf (triage) -> author -> plan -> build -> evidence -> review -> validate
     ^                                                                                                            |
     +------------------------------------------------------------------------------------------------------------+
```

After a slice ships, **closure** runs: `/staircase-attest` records that the composition meets each newly review-ready criterion (or honestly leaves it as a finding), and `/staircase-seal` closes any aggregation deliverable whose cascade the slice completed. This is the slice's true end — see Step 12 of `/staircase-build`.

## Quick Reference

| Skill | Question it answers | When to use |
|-------|--------------------|-|
| `/staircase-status` | Where are we? Is the plan still valid? | Start of session, after completing work, checking drift |
| `/staircase-queue` | What should I work on next? What can run in parallel? | Picking the next slice, dispatching parallel agents |
| `/staircase-tree` | Show me the graph as a progress tree from any node | Visual navigation, roadmap overview, drilling into a phase/milestone/solution |
| `/staircase-explore` | Help me understand this area/node/topic | Before making decisions, understanding context |
| `/staircase-discuss` | Let's think this through — what does it mean, what should change? | Multi-turn discussion loop; reasons in the conversation, delegates every graph-fact step to the engine |
| `/staircase-wf` | Drive any library workflow from natural-language intent | Triage, authoring, planning, review — the generic router picks and drives the workflow |
| `/staircase-author` | Create/update/deprecate a node in the graph | Writing requirements, deliverables, criteria, decisions, evidence |
| `/staircase-plan` | How do we build this? Break it down. | Roadmapping, milestone decomposition, solution slicing |
| `/staircase-build` | Am I ready to code? What are the criteria? | Pre-flight before implementation |
| `/staircase-evidence` | Record that tests verify criteria | After implementation, closing the build loop |
| `/staircase-attest` | Does the composition meet this criterion's intent? Record it. | Post-merge closure of a review-ready criterion (Tier 1/2) |
| `/staircase-seal` | Close out a milestone/epic/roadmap as a deliberate act | A seal-ready aggregation deliverable; finalising a milestone/epic/roadmap |
| `/staircase-review` | Is this node good quality? | Checking clarity, testability, compliance |
| `/staircase-validate` | Is the graph structurally healthy? | After any change, before PRs |

## v3 Model

Five node types: **requirement**, **deliverable**, **criterion**, **evidence**, **decision**.

Two chains with attestation bridges:
- **Requirement chain** (timeless WHAT): obligation -> SN -> REQ
- **Delivery chain** (temporal WHEN): roadmap -> milestone -> epic -> task -> solution

Solutions (`type: deliverable, category: solution`) are in the delivery chain. Cross-chain connections use `targets` (planning intent: deliverable → requirement criterion) and attestation (evidence satisfying requirement criteria).

Key link types:
- `derives-from` — spec/temporal decomposition (targets criteria, not nodes)
- `satisfies` — evidence makes one claim about one criterion (replaces v2 `evidences`)
- `targets` — deliverable planning intent toward requirement criteria
- `justified-by` — rationale link from requirements/deliverables to decisions

## Common Flows

**Start a new session:**
```
/staircase-status           -> see coverage, plan health across both chains, what's next
```

**"I think we need X":**
```
/staircase-discuss          -> think it through — options, prior decisions, what "done" looks like
/staircase-wf               -> triage the observation via the runtime (typed disposition + draft recommendation)
/staircase-author           -> create the nodes if proceeding
/staircase-validate         -> confirm graph is healthy
```

**Plan from scratch (big graph, no roadmap):**
```
/staircase-plan             -> detects no roadmap, creates top-level phases (deliverable nodes)
/staircase-plan RM-*.C1     -> decomposes Phase 1 into milestones
/staircase-plan MS-*        -> decomposes milestone into solutions
```

**Build a slice:**
```
/staircase-queue            -> pick the next action (kind=build → SOL-*)
/staircase-build SOL-*      -> pre-flight check + build brief (both chains verified)
(implement code and tests)
/staircase-evidence tests   -> scan tests, create evidence nodes with satisfies links
(PR → merge)
/staircase-attest REQ-*.Cn  -> attest criteria the slice made review-ready (or record a finding)
/staircase-seal MS-*        -> seal any deliverable whose cascade the slice completed
/staircase-status           -> confirm progress
```

**Close out a criterion or deliverable (steady-state, no full slice):**
```
/staircase-attest <crit>    -> Tier 1/2 attestation of a single review-ready criterion
/staircase-seal <deliv>     -> Tier 3 seal of a seal-ready milestone/epic/roadmap
```

**Roadmap from scratch (or full replanning):**
```
/staircase-status           -> see the full graph shape, what exists, what's missing
/staircase-plan             -> detects no roadmap (or you say "start fresh"), creates top-level phases
/staircase-plan RM-*.C1     -> decompose Phase 1 into milestones
/staircase-plan MS-*        -> decompose a milestone into solution slices
/staircase-validate         -> confirm graph health after all nodes created
```

**Priorities shifted, rethink the roadmap:**
```
/staircase-status           -> drift assessment shows which phases are stale/clean/unplanned
/staircase-discuss          -> "should we reprioritise X?" — think through the impact on both chains
/staircase-plan RM-*.C2     -> replan just the affected phase
    — or —
/staircase-plan             -> full replan if drift is fundamental
/staircase-validate         -> confirm health
```

**Review before PR:**
```
/staircase-review recent    -> review all draft nodes
/staircase-validate         -> structural health check
```

## Design Principles

1. **Skills provide value to the agent, not just process.** Each skill's output is a context package that feeds the next step — not a report for a human.
2. **Detect before acting.** Skills check what exists and adapt (e.g., `/staircase-plan` detects whether you need a roadmap, milestones, or solutions).
3. **The CLI is the single surface for queries and mutations.** Skills delegate every read and every write to `./engine/staircase`; they never read or write `.req.yaml` files directly. The engine validates each mutation through the plan-apply path.
4. **One skill per workflow step.** No overlap, clear boundaries.
5. **Two-chain awareness.** Every skill understands requirement chain (timeless WHAT) and delivery chain (temporal WHEN), bridged by `targets` links (planning intent) and attestation (verification).
