# Link Type Guide (v3)

## All 13 Link Types

| Link Type | Source | Target | Cardinality | Purpose |
|-----------|--------|--------|-------------|---------|
| `derives-from` | requirement | requirement criterion | many:many | Spec decomposition within requirement chain |
| `derives-from` | deliverable | deliverable criterion | many:many | WBS decomposition within delivery chain |
| `criterion-of` | criterion | requirement OR deliverable | many:1 | Criterion belongs to exactly one parent |
| `satisfies` | evidence | criterion | many:1 | Each evidence makes one claim about one criterion |
| `justified-by` | requirement OR deliverable | decision | many:many | Rationale — why this node exists |
| `targets` | deliverable | requirement criterion | many:many | Planning intent before evidence exists |
| `depends-on` | requirement OR deliverable | requirement OR deliverable | many:many | Sequencing / build dependency |
| `addresses` | decision | criterion OR decision | many:many | Decision addresses a concern |
| `allocated-to` | requirement OR deliverable | component (external ID) | many:many | Accountability — which component owns this |
| `scoped-to` | evidence | component (external ID) | many:1 | Evidence scope — which component was tested |
| `supersedes` | req, del, OR decision | same type | 1:1 | This node replaces the target |
| `conflicts-with` | requirement OR deliverable | requirement OR deliverable | many:many | Symmetric conflict (write in both files) |

## Chain Boundary Rules

Two chains exist: **requirement chain** (timeless WHAT) and **delivery chain** (temporal WHEN). The boundary is absolute — no node crosses via `derives-from`.

- Requirements (`derives-from`) must stay within the requirement chain
- Deliverables (`derives-from`) must stay within the delivery chain
- Solutions (`type: deliverable, category: solution`) are in the **delivery chain** — they `derives-from` deliverable criteria (same chain)
- `targets` is the planning bridge: deliverable → requirement criterion (cross-chain planning intent, NOT a derivation)

```
Requirement chain:   REQ → REQ.C ←─── targets ───── DEL
                                                      ↑
Delivery chain:      RM  → RM.C  → MS  → MS.C → SOL → SOL.C
```

## Common Patterns

**Requirement decomposition:**
```yaml
# Correct: derives-from targets a CRITERION, not the requirement
links:
  - target: SN-TRACE-001.C1     # criterion
    type: derives-from
```

**Solution (delivery chain — derives-from deliverable criterion, targets requirement criterion):**
```yaml
links:
  - target: MS-INC-1.C1         # delivery chain criterion (derives-from, within-chain)
    type: derives-from
  - target: REQ-PARSE-001.C1    # requirement chain criterion (targets, planning intent)
    type: targets
  - target: DEC-PARSE-SERDE
    type: justified-by
```

**Deliverable planning:**
```yaml
# targets = planning intent (deliverable → requirement criterion)
links:
  - target: REQ-PARSE-001.C1    # requirement criterion only
    type: targets
  - target: MS-INC-1            # milestone dependency
    type: depends-on
```

**Evidence satisfying a criterion:**
```yaml
links:
  - target: REQ-PARSE-001.C1
    type: satisfies             # replaces v2 'evidences'
```

**Criterion membership:**
```yaml
links:
  - target: REQ-TRACE-001       # exactly one parent
    type: criterion-of
```

## Deprecated Link Types

| Deprecated | Migrates To | Notes |
|------------|-------------|-------|
| `evidences` | `satisfies` | v2 naming — import converts automatically |
| `complies-with` | `derives-from` | v1 obligation tracing |

## Key Rules

- `derives-from` always targets **criteria**, never requirements or deliverables directly
- `criterion-of` is many:1 — each criterion has exactly one parent (no shared criteria)
- `satisfies` is many:1 — each evidence targets one criterion (multiple evidence nodes can reference the same external artifact)
- `justified-by` targets **decisions only** — not requirements, not criteria
- `targets` targets **requirement criteria only** — not deliverable criteria
- Links are written in the **source file** — the file that "has" the relationship
- No node may cross the chain boundary via `derives-from` — the boundary is absolute
