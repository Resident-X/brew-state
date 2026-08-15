# Review Criteria (v3)

## Five Node Types

The v3 model has five node types: **requirement**, **deliverable**, **criterion**, **evidence**, **decision**. Every node must be one of these. Categories are subsets within types — they don't affect engine behaviour but are mandatory on requirements and deliverables.

## Two Chains

- **Requirement chain** (timeless WHAT): obligation -> SN -> REQ, all via derives-from to criteria
- **Delivery chain** (temporal WHEN): roadmap -> milestone -> epic -> task -> solution, all via derives-from to deliverable criteria
- **Two bridges**: `targets` (deliverable → requirement criterion, planning intent) and attestation (evidence satisfying requirement criteria produced by delivery work)
- **Chain boundary is absolute**: No node crosses chains via `derives-from`. A requirement cannot derive-from a deliverable criterion. A deliverable cannot derive-from a requirement criterion.

## Clarity

**Good**: "The parser shall produce exactly one Node per .req.yaml file"
**Bad**: "The parser should handle files appropriately"
**Test**: Could two engineers independently implement this and arrive at the same behaviour?

## Testability (Criteria)

**Good**: "Malformed YAML produces an error containing the file path and line number"
**Bad**: "Errors are handled properly"
**Test**: Can you write a concrete assertion for this criterion?

## Link Completeness (v3)

- Every requirement **must** have `derives-from` -> **criterion** (not requirement or deliverable)
- Every deliverable **must** have `derives-from` -> **deliverable criterion** (not requirement criterion)
- Every solution **must** have `derives-from` -> deliverable criteria (within delivery chain); `targets` -> requirement criteria (planning intent)
- Every requirement/deliverable **should** have `justified-by` -> decision (when non-obvious)
- Every criterion **must** have exactly one `criterion-of` -> parent requirement or deliverable
- Every decision **should** have `addresses` -> criterion or decision
- Every evidence **must** have exactly one `satisfies` -> criterion
- `justified-by` is the ONLY link from requirements/deliverables to decisions
- Only use `depends-on` for real implementation or sequencing dependencies
- `targets` is only valid from deliverables to requirement criteria (planning intent)

## Chain Boundary Rules

| Source type | derives-from target | Valid? |
|------------|-------------------|--------|
| requirement | requirement criterion | YES |
| requirement | deliverable criterion | NO — chain violation |
| deliverable | deliverable criterion | YES |
| deliverable | requirement criterion | NO — use `targets` instead |

## Structural Rules

- `derives-from` targets **criteria**, never requirements or deliverables directly
- `criterion-of` is many:1 — each criterion belongs to exactly one parent
- `satisfies` is many:1 — each evidence targets one criterion
- Obligation requirements have `authority: external` or `authority: internal`, `managed: false`
- All requirement categories (`functional`, `solution`, `journey`, `interface`, `obligation`, `persona-goal`, `strategic`, `constraint`) are structurally identical — the engine treats them the same
- All deliverable categories (`roadmap`, `milestone`, `epic`, `task`) are structurally identical
- Evidence has its own status lifecycle: `active`, `resolved`, `expired`, `superseded`

## Deliverable Quality

### Roadmaps (category: roadmap)
- Criteria are **phases** describing capability states
- Each phase criterion should be decomposable into milestones
- `targets` links reference which requirement criteria each phase intends to address

### Milestones (category: milestone)
- Criteria are **state predicates** — verifiable conditions, not task descriptions
- "Parser handles all five node types" not "implement parser"
- Zero-duration assessment points — no dates (dates belong to roadmap phases)
- `derives-from` a roadmap phase criterion

### Epics (category: epic)
- Shippable units of work grouping solutions
- `targets` links to requirement criteria they intend to address
- `depends-on` for sequencing with other epics/milestones
- `derives-from` milestone criteria or roadmap phase criteria

### Tasks (category: task)
- Atomic work items (optional — many projects skip this level)
- `derives-from` epic criteria

## Criterion Quality

- **Measurement type is set** — binary, threshold, rate, or periodic
- **Text is a testable predicate** — not vague ("system performs well"), not a restatement of the parent
- **Verification method is appropriate** — test > demonstration > analysis > inspection
- **Scope is clear** — if scoped, the predicate is evaluable against the component registry
- **Parent type matches chain** — criterion on a requirement belongs to the requirement chain; criterion on a deliverable belongs to the delivery chain

## Decision Quality

- **Options were considered** — at least 2 alternatives listed
- **Rationale explains the trade-off** — not just "it's better"
- **Category is correct** — assumption needs `validation_horizon`, risk needs `risk_level` and response strategy
- **Addresses something** — links to the criterion or decision it informs
- **Persona decisions** describe the archetype, not just demographics

## Evidence Quality

- **One claim per criterion** — each evidence node satisfies exactly one criterion
- **Result is unambiguous** — `pass` or `fail`, nothing in between
- **Method is recorded** — test, demonstration, analysis, inspection, or federated
- **Artifact reference** — URI or path to the external artifact
- **Temporal fields** — `observed_at` set, `valid_until` if applicable
- **`satisfies` not `evidences`** — v3 uses `satisfies` (v2 `evidences` is deprecated)

## Journey Quality

- **Text is a behavioral scenario** — Cockburn-style main success scenario with extensions, not a static property statement
- **Extensions discovered** — each step should have "what could go wrong?" explored; each extension becomes a criterion
- **Criteria are properties, not behaviors** — "init completes in under 10 seconds" (testable property), not "user runs init" (behavioral step)
- **Criteria at splittable granularity** — each can independently anchor child requirements

## Solution Quality

- **Rich text** — architectural approach, interfaces, constraints described thoroughly
- **Delivery chain linked** — `derives-from` to the deliverable criterion (milestone or epic) that scopes this work
- **Requirement intent expressed** — `targets` links to the requirement criteria this solution addresses (planning intent)
- **Justified-by** — non-obvious approaches linked to the decision explaining why
- **Test-spec criteria** — criteria are close to test assertions, minimal translation needed

## Common Issues

1. **Solution masquerading as need**: stakeholder need says "use SQLite" instead of "queries return in <100ms"
2. **Untestable criteria**: "system performs well", "handles errors gracefully"
3. **Missing rationale**: requirement exists but no explanation of why
4. **derives-from targets requirement**: must target a criterion in v3
5. **Chain boundary violation**: any node derives-from a criterion from the opposite chain
6. **Missing criterion-of**: criterion exists but no link to parent
7. **Missing justified-by**: requirement without a decision justifying non-obvious choices
8. **Orphan criterion**: criterion with no parent link
9. **Behavior masquerading as criterion**: "user clicks search" instead of "search returns relevant results within 200ms"
10. **Journey without scenario**: journey text is a static property statement, not a step-by-step flow
11. **Thin solution text**: solution just names a technology without describing approach, interfaces, or constraints
12. **Partial traceability**: solution links to 2 of 5 criteria it actually touches
13. **Deliverable uses derives-from to requirement criterion**: should use `targets` for planning intent, not `derives-from`
14. **Solution missing delivery chain link**: solution has no `derives-from` to any deliverable criterion
15. **`evidences` instead of `satisfies`**: v2 link type, should be migrated to `satisfies`
16. **Milestone describes a task**: "implement parser" instead of "parser handles all five node types"
