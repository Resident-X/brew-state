---
name: staircase-evidence
description: "Records verification evidence linking test results, analyses, or demonstrations to specific criteria. Creates evidence nodes with method, result, artifact reference, and criterion linkage via satisfies. Use AFTER implementation to record proof that criteria are satisfied."
allowed-tools: "Read Write Edit Glob Grep Bash"
---

# Record Evidence

Answers: **Record that these tests/analyses verify these criteria.**

Creates evidence nodes linking verification results to specific criteria. Evidence closes the build loop — proof that criteria are satisfied, violated, or need re-verification.

When you run an engine read (`--format json`), read the whole payload into context — it is self-describing, so take each value together with the inline meaning shipped beside it. See the graph-reads rule in CLAUDE.md.

## Authoring path

Every evidence node ships through `staircase author create --type evidence` — the single plan-apply mutation path established by `DEC-EVIDENCE-CLI-CONSOLIDATION` and the retirement of `staircase evidence submit` under `SOL-CLI-EVIDENCE-SUBMIT-RETIRE`. The CLI validates each intent against the `EvidenceModule.ValidateMutation` typebehaviour hook (method/result enum policy, required `observed_at`, single `satisfies` target that resolves to a criterion, `status: active` enforced on first write) and writes the resulting `.req.yaml` file via the projection adapter chain.

Do **not** hand-write evidence `.req.yaml` files directly and do **not** invoke any retired evidence-specific command. The skill's only authoring surface is `staircase author create --type evidence`.

## Arguments

- `$0` — Mode: `tests` (scan source files for criterion references), `manual` (specify criteria directly), or a path to a test output file
- `$1` — (optional) Scope: node ID to limit scanning (e.g., `SOL-PARSE-SERDE`)

## Modes

### Auto Mode (`tests`)

Scan implementation and test files for criterion references, then create evidence nodes.

**Step 1 — Find files with criterion references:**
```
Grep pattern="[A-Z]+-[A-Z0-9-]+\.C[0-9]+" in tests/, crates/*/tests/, crates/*/src/, src/, ui/
glob: *.rs, *.go, *.ts, *.spec.ts
output_mode: files_with_matches
```

**Step 2 — Extract criterion references from doc comments:**
- Go pattern: `// {ID}.C{N}:` in test functions
- TS pattern: `// {ID}.C{N}:` in test functions
- Map each test function name → criterion ID(s) it verifies

**Step 3 — Run tests and capture results:**
- Go: `go test ./... 2>&1`
- TypeScript: `npx vitest run 2>&1`
- Parse PASS/FAIL per test function name

**Step 4 — For each criterion with test coverage, create an evidence node** via `staircase author create --type evidence` (see Evidence Fields and Authoring Command below).

**Step 5 — Report** what was recorded and what remains uncovered.

### Manual Mode (`manual`)

Create evidence from direct specification.

**Step 1 — Collect from user or context:**
- Which criterion IDs?
- Method: test, demonstration, analysis, inspection, or federated
- Result: pass or fail
- Artifact: URI or file path to the external evidence artifact

**Step 2 — Verify each criterion exists:**
```
./engine/staircase show {CRITERION-ID} --format json
```

**Step 3 — Create evidence node** via `staircase author create --type evidence` (see Evidence Fields and Authoring Command below).

### File Mode (test output path)

Parse a test output file (e.g., `go test` output, JUnit XML).

1. Read the file
2. Parse pass/fail per test function
3. Match test function names to criterion IDs via doc comment patterns
4. Create evidence nodes as in auto mode

## Evidence Fields

```yaml
id: EVD-REQ-PARSE-001.C1-TEST
type: evidence
title: "Parser unit tests — valid YAML (REQ-PARSE-001.C1)"
status: active          # active | resolved | expired | superseded
result: pass            # pass | fail
method: test            # test | demonstration | analysis | inspection | federated
observed_at: "2026-04-02T10:00:00Z"
valid_until: "until-superseded"    # or date, or milestone ID
artifact: "ci://pipeline/staircase-core/run/142#test-parse-valid"
version: 1

text: |
  TestParseValidRequirement passes. Reads a valid .req.yaml fixture
  and asserts the resulting Node has correct fields.

links:
  - target: REQ-PARSE-001.C1
    type: satisfies
```

**Status lifecycle (evidence only — not draft/approved/deprecated):**
- `active` — current, participating in satisfaction cascade
- `resolved` — negative evidence that has been addressed (add `resolution` and `resolved_by` fields)
- `expired` — validity elapsed, criterion returns to unknown
- `superseded` — replaced by newer evidence

**`valid_until` patterns:**
- `until-superseded` — binary criteria: stays active until explicitly superseded
- `"2026-09-01"` — date-bounded: periodic review, security scans, pen tests
- Milestone ID — expires when that milestone is reached

**`artifact` patterns:**
- CI URL: `ci://pipeline/staircase-core/run/142#test-name`
- File path: `crates/staircase-core/tests/parser_test.rs::test_valid_yaml`
- Document URL: `https://wiki.example.com/reviews/2026-04-01`
- Audit record: `audits://q1-2026/access-control-review`

**Federated evidence** (`method: federated`):
- Add `source_instance` (URL of the source Staircase instance)
- Add `source_criterion` (criterion ID in the source graph)
- The local criterion is satisfied by the remote instance's satisfaction state

## ID Generation

- `EVD-{CRITERION-ID}-{METHOD}` — e.g., `EVD-REQ-PARSE-001.C1-TEST`
- If multiple evidence items exist for same criterion+method, append `-{N}` — e.g., `EVD-REQ-PARSE-001.C1-TEST-2`
- Glob `specs/evidence/EVD-{CRITERION-ID}-{METHOD}*.req.yaml` to detect collisions

## Authoring command

Every evidence node ships through `staircase author create --type evidence`. The mutation engine validates the intent against `EvidenceModule.ValidateMutation`, persists the row, and writes the projection `.req.yaml` via the configured adapter chain. The CLI never accepts a hand-written file path for evidence — pass the fields as flags instead.

Required structured flags (any missing flag rejects before reaching the engine):
- `--id` — the evidence node ID, e.g. `EVD-REQ-PARSE-001.C1-TEST`
- `--title` — a human-readable title
- `--method` — one of `test | demonstration | analysis | inspection | federated`
- `--result` — `pass` or `fail`
- `--observed-at` — RFC 3339 UTC timestamp (e.g. `2026-04-02T10:00:00Z`)
- `--link <criterion-id>:satisfies` — the criterion this evidence satisfies (exactly one)
- `--confirm` — apply the create (preview-only without it)

Optional flags:
- `--text "<body>"` or `--text-file <path>` for the narrative
- `--valid-until "<date|until-superseded|<milestone-id>>"`
- `--artifact "<scalar>"` (legacy single-string, bridges to `kind: external, reference: <value>`) OR the variant-aware artifact flags (`--artifact-kind external|composition|inline` plus the variant-specific siblings — `--artifact-reference`, `--artifact-version`, `--artifact-verifier`, `--artifact-retrieval-at`, `--artifact-cite`)
- `--observation-window "<duration>"` for periodic-revalidation methods

The CLI defaults `status: active` on create — no `--status` flag.

Worked example:

```bash
./engine/staircase author create --type evidence \
  --id EVD-REQ-PARSE-001.C1-TEST \
  --title "Parser unit tests — valid YAML (REQ-PARSE-001.C1)" \
  --method test --result pass \
  --observed-at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --valid-until "until-superseded" \
  --artifact "engine/parse/parse_test.go::TestParseValidRequirement" \
  --link "REQ-PARSE-001.C1:satisfies" \
  --text "TestParseValidRequirement passes. Reads a valid .req.yaml fixture and asserts the resulting Node has correct fields." \
  --confirm
```

`--format json` exchanges the text envelope for the standard `authorResult` JSON shape; the created node appears in `changes[0].node`.

Validation rejections (missing required slot, satisfies target unresolved or not a criterion, non-UTC or future `observed_at`, `valid_until` malformed) surface either as an `error.missing_flags` envelope (for CLI pre-check rejections) or as a `findings[]` array with `severity: error` on the relevant field (for `EvidenceModule.ValidateMutation` rejections). Both shapes set `applied: false` and exit non-zero.

## Post-Evidence Report

```markdown
## Evidence Recorded

| Criterion | Method | Result | Evidence ID |
|-----------|--------|--------|-------------|
| REQ-PARSE-001.C1 | test | pass | EVD-REQ-PARSE-001.C1-TEST |
| REQ-PARSE-001.C2 | test | pass | EVD-REQ-PARSE-001.C2-TEST |
| REQ-PARSE-001.C3 | test | fail | EVD-REQ-PARSE-001.C3-TEST |

## Still Uncovered (Unknown satisfaction state)

| Criterion | Parent | Suggestion |
|-----------|--------|-----------|
| REQ-PARSE-001.C4 | REQ-PARSE-001 | Needs demonstration — run CLI and show output |

## Violated (Active negative evidence)

| Criterion | Evidence | Resolution |
|-----------|---------|-----------|
| REQ-PARSE-001.C3 | EVD-REQ-PARSE-001.C3-TEST | Fix parser error handling, re-run tests |
```

## Resolving Negative Evidence

When a failing criterion is fixed:

1. Create new positive evidence via `staircase author create --type evidence` (see Authoring command above) with fresh `observed_at`.
2. Mark the prior negative evidence as resolved via `staircase author update --id <old-evd-id>` setting the resolution/resolved_by fields the schema declares for evidence. Inspect `staircase author update --help` for the current evidence-field flag set; fields the CLI surfaces appear there. Apply with `--confirm`.
3. The cascade re-evaluates: violated → satisfied.

## Validate After Authoring

`staircase author create` validates the evidence intent through the engine (`EvidenceModule.ValidateMutation` plus structural schema checks) before writing. A successful `--confirm` exit means the node satisfies the schema, the satisfies target resolves to a real criterion, and the timestamp/result/method enums are valid. Re-running `./engine/staircase validate` over the project surface is the cross-graph check — run it once after a batch of authorings to confirm no other graph invariants regressed.

For ad-hoc inspection of a freshly-authored evidence node:
```
./engine/staircase show {EVIDENCE-ID} --format json
```
The output carries every schema-declared evidence field (status, result, method, observed_at, valid_until, artifact, satisfies link target) so the skill can confirm the node landed as intended.

## Key Rules

- **Evidence is the only thing that satisfies criteria.** Code existing is not evidence. Tests passing is.
- **One evidence node per criterion per claim.** Multiple evidence nodes may reference the same artifact.
- **`satisfies` not `evidences`.** The v2 link type is deprecated — always use `satisfies`.
- **Evidence has its own status lifecycle.** Use active/resolved/expired/superseded, never draft/approved/deprecated.
- **`artifact` is mandatory for test and CI evidence.** Humans and auditors need to find the source.
- **Timestamp is mandatory and must be UTC.** `observed_at` records when verification happened. Always run `date -u +"%Y-%m-%dT%H:%M:%SZ"` (the `-u` flag forces UTC/GMT regardless of local timezone) and use the result verbatim. Never truncate to the hour, use a local-date midnight value, or omit `-u` (which would embed local time such as AEDT instead of UTC). Future-UTC timestamps and non-UTC timestamps are rejected by `satisfy.computeValidity` and the evidence will not participate in the satisfaction cascade.
- **Method hierarchy:** test > demonstration > analysis > inspection. Prefer stronger methods when available.
- **Evidence files go in `specs/evidence/`** — one file per evidence node.
