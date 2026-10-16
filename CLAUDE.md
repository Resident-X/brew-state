## How we work — dogfooding the thesis

This project uses Staircase, which is: **disciplined, requirement-driven, complete-the-first-time
engineering produces better software, faster, that stays maintainable.** Every PR is evidence for
or against that.

- **Criteria-driven, not TDD.** The acceptance criteria in `.req.yaml` files *are* the test spec.
  Every criterion gets at least one test that would **catch a real regression** — not a smoke test
  that only proves the code runs. Cover edge cases, error paths, empty/malformed input, and both
  text **and** JSON output formats.
- **Trace in tests, never in code.** Put `/// REQ-*.Cn: <criterion text>` doc comments on the test
  functions that verify them. **Never** put requirement IDs as comments in implementation code —
  they rot on refactor and `grep` over tests is the coverage signal.
- **No deferred work.** No TODOs, no "future work", no stubs, no tech debt pushed to a later slice.
  If the slice says build it, build it completely and correctly now. Genuine discoveries are carried
  forward by authoring the correct nodes into the graph.
- **The graph is the only durable record — PR prose is not.** Nothing re-reads old PR text, but
  `query`/`show` reach every node forever, so a finding written only into a PR body is lost at merge.
  Before closing out a slice, check whether a mid-build discovery (defect, limitation, open question) is
  already covered by an existing node; search the graph and sibling `DEL-MAINTENANCE` items first. If
  not, author one — a `DEL-MAINTENANCE` child for a defect in already-sealed work, a new/amended
  criterion for something no criterion ever required. A defect in the criterion being built is fixed in
  place, not filed. A PR may *summarize* what the graph now says, but
  the graph entry has to exist first.
- **Requirements are the baselined final state.** An incomplete requirement is *wrong*, not a
  placeholder for a future solution. Deferred work still needs a requirement in the graph.
- **Emergent, corrective, and BAU work goes in `DEL-MAINTENANCE`.** It is a **continuous lane**
  (`attributes.closure: continuous`, `attributes.role: maintenance`): never itself sealed, excluded
  from the seal surfaces, its state only ever the rollup of the work it holds. Defects, cleanup,
  patching, and remediation of already-sealed work that fell short all land here as a **child task or
  solution**, each tracing to the requirement criterion whose behaviour it restores; a child that can't
  name that criterion is unscoped, not maintenance. The lane carries a **single cascade criterion**
  (`DEL-MAINTENANCE.C1`, `closes_by: cascade`); don't add a criterion per item. It sits outside the
  roadmap's phases — reach it by name, not by walking the tree. Supersede when the criterion said the
  *wrong* thing; use this lane when the behaviour, not the spec, needs correcting. See
  `DEC-MAINTENANCE-CONTINUOUS-LANE`.
- **Synthetic fixtures only.** Engine tests must use generic IDs (`REQ-TEST-001`, `TST-*`) and
  synthetic tempdir projects — never real requirement IDs from `specs/`. The reason is decoupling,
  not secrecy: tests that name real nodes break every time the graph is legitimately edited. The
  engine never reads skill files; tests never couple to `.claude/skills/`.
- **This repo is public domain and open source.** Anything committed is published — write it to be
  read by someone rebuilding this on a different machine, in a different country, on a different
  mains voltage. That is also the discipline test: requirements that name mechanism don't travel.

## How this project verifies

- **Trace-comment form.** The criterion id and its text head the test that verifies it: a `/// SOL-X.C2: <criterion text>` doc comment on a C test function, a `# SOL-X.C2: <criterion text>` comment opening a Python test. A machine-record document citing the criteria its figures come from is content, not a trace comment.
- **Verification by kind.** A criterion verified by `test` gets a test. One verified by `inspection` or `analysis` gets a stated check of the delivered artefact against each clause, with the arithmetic shown for analysis.
- **Three tiers before energisation** (`DEC-SIM-VERIFICATION-TOOLCHAIN`):
  - **Host.** `task fw:build`, `fw:check`, `fw:test`, `fw:run`: the control logic, estimator and plant model compiled for the host and run under sanitizers, plus the build-time checks. Memory and undefined-behaviour defects are caught here and only here.
  - **Emulation.** `task fw:emulate`: the target build's own artefact under emulation against modelled peripherals.
  - **Target.** Worst-case timing on the real, un-energised board. A bench step, not a task.
- **Mutation.** `task fw:sweep` alters the plant model's arithmetic and requires a test to notice. In full it is part of the complete verification that runs nightly; a build round's gate runs it only restricted to the plant lines the branch changes, never in full. `task fw:mutate` (seeded property breaks) runs on demand, when a check is added or reworked. `DEC-VERIFICATION-ROUND-TARGETED-NIGHTLY-FULL` sets when each runs.
- **Gates.** Verification runs at two cadences (`DEC-VERIFICATION-ROUND-TARGETED-NIGHTLY-FULL`):
  - **Round.** `task check:round` is the build round's gate, run once per round; its exit status is the verdict. Tiers, in order:
    - **Host** (`fw:build`, `fw:check`, `fw:test`, `fw:run`): always, in full.
    - **Emulation** (`fw:emulate`): only when the branch changes a path the emulation reads (`EMULATION_READS` in `firmware/tools/round_gate.py`). The branch is measured from its merge-base with the local remote-tracking `origin/main`, counting uncommitted edits and new files. When it cannot tell what changed, including when there is no remote-tracking `origin/main`, emulation runs anyway.
    - **Board** (`hw:verify`, the pre-order check of every board design; `hw:test:round`, the board tooling's tests without those that run the seeded-fault proof): only when the branch changes a tracked KiCad file anywhere, anything under `hardware/`, anything a board design reads (its sheets, library tables and libraries, and the separation basis record it is held to), the board check's tooling, the round gate's own code, or `Taskfile.yml`, as emulation does. It is judged on changed paths alone (`BOARD_READS` in `firmware/tools/round_gate.py` and the files `task hw:reads` lists): it runs when the changed paths or the files the designs read cannot be listed, not on unknown changed lines alone. A branch touching none of those paths, a firmware-only branch that leaves `Taskfile.yml` alone included, needs no KiCad, rasteriser or font. A KiCad design file in the working tree but not tracked by git fails the round, naming it, since the check finds only tracked designs; a missing or too-old KiCad, rasteriser or monospaced font stops the round naming the tool rather than skipping the tier.
    - **Changed-lines mutation sweep**: `fw:sweep` restricted to the mutants on the lines the branch changes in the sweep's population (same merge-base), judged against the triage record as the full sweep judges them, with every judgement about a changed file checked against that file's current mutants. A branch changing no such line runs no sweep and needs no mutation toolchain; one that does needs LLVM 19 and Mull and fails without them. A change whose lines cannot be told fails the round after the host, emulation and board tiers run. The round never runs the full sweep.
    - **Selection is a time saver, not a trust boundary.** A stale remote-tracking `origin/main` can mis-measure a branch; that is kept rare by branching from a freshly fetched `main`, not checked for. A change that escapes the selection meets the reviews before merge and the nightly after.
    - **Closing lines**, printed after the sweep, state the whole verdict: which tiers ran, why one was skipped or not reached, and whether the sweep ran, was skipped, was not reached or could not run, with the changed lines it covered and whether it found a problem or could not look.

    The round gate is the only verification a change gets before it merges; this project has no separate pull-request gate.
  - **Nightly.** `task fw:verify` declares the complete verification: every tier the round can skip, emulation and the board gates (`hw:verify`, `hw:test:round`) unconditionally, and the full mutation sweep. It runs nightly against `main`, on a hosted runner with KiCad, the rasteriser and a monospaced font installed. The board check's seeded-fault proof (`task hw:prove`, and the full `task hw:test` that includes its tests) runs on demand, in neither gate; the hardware notes (`hardware/README.md`) say where the tooling tests are split.

  A build round's gate runs `check:round` and not `fw:verify`. Long gates outrun a single shell call's ten-minute limit: start the gate detached with its output and exit status captured to a log, then poll the log with repeated bounded foreground calls until the exit line appears, and never end a headless session while it runs.
- **Generated records pin their inputs.** The analysis records under `docs/` (protection margin, parameter dominance, stability, identifiability) print the sha256 of each file they were generated from, and an emulation test fails when one goes stale. A change to any of those inputs (the `firmware/params/` descriptions and declarations), even a comment, regenerates the affected records with their own tools in the same change.
- **Machine-record and hardware-design work** lands in `docs/sunbeam-em7000/` and its `controller-design/` working folder. Sources govern and derived views are corrected to match (`DEC-MACHINE-RECORD-FOLDER-PER-MACHINE`). A changed fact is chased through every document that restates it, and through any firmware parameter or simulation result that depends on it.

## Editing the graph

- **Author via the engine, never hand-write `.req.yaml`.** Use the
  `/staircase-author` skill — it handles IDs, placement, link wiring, validation, and discipline
  lint. Direct file edits are an escape hatch only (e.g. fixing a link blocked by a
  pre-existing-link validation error).
- `staircase author` does **not** bump `version:` automatically — a substantive content change needs
  a deliberate bump. Pass `--bump-version` on `author update` to increment by exactly one (engine-computed,
  recorded, refused on a sealed node, mutually exclusive with `--full`). Bump once per uncommitted
  session (N→N+1 from the committed baseline), not per edit. Deprecating a node does **not** bump version.
- Per-discipline authoring rules (criterion shape, decision shape, leak detection, etc.) live in
  **engine lint families**, and the operative rule data ships **inside the binary** — reach it with
  `staircase lint explain`, not a filesystem path. It is never duplicated into this file or the
  skills. When authoring or reviewing nodes, read the rules and run `staircase lint` /
  `/staircase-review` rather than reasoning about discipline from memory.
- `author create --criteria-file <yaml|json>` writes a parent and all its criteria as one atomic
  change-set, auto-assigning `.C1..Cn` and wiring `criterion-of`. Use it instead of creating criteria
  one at a time. It is create-time only: `author update` refuses it, so criteria for an existing parent
  go in one by one with `author create --type criterion --id <PARENT>.C<n> --link <PARENT>:criterion-of`.
- `authority:` and `managed:` have **no CLI flags**. Setting them needs the direct-file-edit escape
  hatch; `validate` accepts them but `show` does not project them.
- **Read a node before you link to it.** Every `targets`, `justified-by`, `derives-from`,
  `depends-on` and `addresses` edge — and every node id named in `text:` or `rationale:` prose —
  requires that you have read the target with `show <id>` **in this session**. A title, a `list`
  row, a `query` hit, or a subagent's paraphrase is not grounds to cite a node. Titles are lossy:
  `DEC-PLUMBING-LEFT-AS-BUILT` reads as "no plumbing changes ever" but rules only on water-path
  *re-routing*; citing it from the title produced a link that contradicted the fitted pressure sensing
  `REQ-MEASUREMENT-001.C7`/`.C8` require. Batch the `show` calls for everything you intend to link
  *before* authoring.

- Authoring through the engine **inserts into the index itself** — no reindex step is owed. Run
  `task sc:index` only after using the direct-file-edit escape hatch, to pick the change back up.
- To edit one sentence inside a long `text:`/`rationale:`, pull the current field out with
  `show --format json`, substitute, and write it back with `--text-file`/`--rationale-file`. The
  engine stays the writer and the version/event trail stays intact; hand-editing the file to avoid
  retyping the field is the escape hatch, not the shortcut.

## Using the engine CLI

- **Read the graph through the engine, never by reading the files.** `show <id>` projects a node
  with its criteria and the meaning of each enumerated value; `query "<terms>"` searches every node;
  `trace <id>` walks the chain; `links <id> --direction inbound|outbound --type <t>` lists edges.
  `grep`/`cat` over `specs/**.req.yaml` returns raw YAML without those projections and misses nodes
  whose wording differs from your term. The only legitimate direct read is a field `show` does not
  project (`authority:`, `managed:`).
- **`staircase capabilities --format json` is the map** of every command, flag and projection level.
  Read it when you don't know the surface rather than guessing flags.
- **Return raw JSON. Don't filter it.** Envelopes are self-describing (`legend`, `*_meaning`, inline
  glosses); piping through `jq`/`python` throws that away. Filter only for one specific known value.
- **Rule lookup is two steps.** `staircase lint explain <family>` errors but ships
  `data.known_rules[]`; `staircase lint explain <rule-id>` then returns the rule's `advice`,
  `suggested_action` and before/after `examples`.
- **`lint` clean ≠ discipline clean.** The prose-quality and implementation-leak families are
  `pass: ai_assisted` and can report zero warnings while real problems stand. Exit status reports
  sweep completeness, not findings, and warnings never affect it. Read the rules and self-check.
- **Decision authoring gotchas.** `--chosen` must exactly match an entry in `options_considered`, so
  pass the winning option as a bare `--option` alongside the `--option-rejected "opt::reason"` entries.
  `graph.decision_authoring.title_as_statement` appears to want a copula (*"Remote interfaces **are**
  limited to…"* passes, *"…**bring** the machine to readiness"* fires); possibly a detector limitation,
  so don't contort a good title more than once.
- Flag facts that cost a retry otherwise: `links` takes `--direction inbound|outbound` (not
  incoming/outgoing) and requires `--type`; `sufficiency` requires a node argument; `--project` is
  accepted only on `wf ensure-capture|submit-turn|list-sessions|resume-session` and rejected elsewhere.
- Pass `--actor` on every mutation (or set `default_actor` in `.staircase/config.yaml`), otherwise
  events record the OS user as `system-fallback`.

## Repo etiquette

- **Skills are installed, not tracked.** `task sc:init` (or `sc:update`) installs the upstream skills into
  `.claude/skills/` at `STAIRCASE_REF` (floats on upstream `main`); git ignores them. A skill this repository owns is
  named `repo-*` — the sync leaves those alone and git tracks them. Run `task sc:update` to move to the current upstream `main`.
- **Agent tier is chosen here, not by the upstream workflow skills.** The synced skills are
  reinstalled verbatim from upstream and cannot be edited here, so this rule overrides every tier they
  or the engine name: the engine's `recommended_tier`, the `no_hint` fallback, `/stage0-build`'s tier
  column, and `/staircase-wf`'s tier→model table (use it only to look up a model's exact id once the
  tier is chosen). Choose by what the task actually is, and name that before each dispatch:
  - `small-fast` (Haiku): graph reads, code reads, simple code writes, test runs, classifications and minor judgement.
  - `mid-tier` (Sonnet): moderate consideration, reasoning or acting, such as a readiness pass, implementing, fixing and reviewing.
  - `reasoning-tier` (Opus): only really complex understanding and reasoning on complicated topics.

  When unsure between two tiers, take the lower and escalate only on evidence from the work.
- Branch: `req/{REQ-ID}/{short-slug}`. Never push to `main`; PRs only. The tracked
  `.githooks/pre-push` hook refuses it, but it is a catch for the mistake, not enforcement: it is inert
  until `task repo:hooks` points `core.hooksPath` at that directory (`task sc:init` and `task sc:update`
  both do), `--no-verify` bypasses it, and `main` carries no server-side protection rule. `git fetch`
  fresh `main` before branching; never branch from stale local `main`.
- Commit messages and PR titles reference the criteria they advance:
  `feat(component): description [REQ-ID.C1, .C2]`.
- PR body needs a **"Why"** section (motivation, not just what changed), a criteria-resolved
  checklist, and test evidence. Don't hard-wrap prose in markdown — let the renderer wrap it.
- **Blind review before every PR, including pure graph-authoring** (Rule 7). Launch a fresh-context
  agent that reads the slice/criteria/journeys and the diff cold, and present its
  ISSUE / PASS / SUGGESTION findings before fixing anything. No PR skips this.
- **Three failure patterns this graph has actually produced**, worth looking for by name in any
  review: *amending without propagating* (a decision is revised and its consequences are not chased
  through the nodes that depended on it); *wrong axis* (the distinction is drawn where the component
  sits rather than where the consequence lands — electrical contention drawn where the issue was
  thermal, preventable-vs-unpreventable drawn where the issue was quality-vs-time); and
  *assumed, not required* (something load-bearing is stated as fact in prose across several nodes
  and asserted by no criterion — flow sensing, mains-synchronous actuation and the reference machine
  itself all reached that state).

## Known engine gaps

- **Deprecation is one-way through the CLI.** There is no `author restore`; reversing a mistaken
  deprecation needs the direct-file-edit escape hatch then `task sc:index`. So check first: resolve
  criterion IDs with `show <PARENT>.Cn` individually, never from titles in a glob or directory listing
  (file order is not `.C1..Cn` order). `validate` won't catch a wrong retirement, because a live
  requirement deriving from a deprecated criterion is not a dangling link.
- **`allocated-to` is unusable.** The schema says `valid_targets: [component]` with "external IDs, not
  graph nodes", but no `component` node type exists and the validator rejects any such link as
  dangling. Requirement-to-component allocation (what `OBL-PHYSICAL-CONFIGURATION-001` would use)
  cannot be wired, and pointing at a definition or requirement node fails `valid_targets` instead.
