# Stage 0 (coffee) prompt templates

Adapt the bracketed parts; keep the rules verbatim. Shared preamble for every prompt:

> Worktree: `<WT>`. Prefix every shell command with `cd <WT> &&`, because the shell's working directory does not persist. Engine binary: `./engine/staircase`. Always pass `--format json` and read the whole payload. On an unknown command or flag run `./engine/staircase capabilities <cmd> --format json`; never guess. Read the graph through the engine, never by reading `specs/`. Report node IDs, `file:line` and short quotes, not file dumps. You run headless: your session ends the moment you stop calling tools, so never run a command in the background and never end a turn to wait for one. Run everything in the foreground with a real time bound on any long command, and finish the whole job in one go.
>
> This repository is a coffee machine's replacement controller: requirements and delivery in the graph, firmware under `firmware/` (PlatformIO host, emulation and target builds, Python tools with their own tests), and the machine's record under `docs/sunbeam-em7000/` with a working design folder `controller-design/` beside it. Sources govern; derived views follow them (`DEC-MACHINE-RECORD-FOLDER-PER-MACHINE`). The complete verification is `task fw:verify`.

---

## 0. Slicing homework (mid-tier, read-only)

> Task about to be sliced: `<TSK-ID>`. Do not author anything. Decide what can be sliced into solutions now.
>
> 1. `show <TSK-ID>` and `show <TSK-ID>.C<N>` for every criterion; `show` every requirement criterion it `targets` in full; `trace <TSK-ID>` up to the personas and journeys.
> 2. **Applicable decisions.** Cross-cutting decisions and definitions beyond the lineage, found with `query "<topic>" --mode hybrid` for each surface and behaviour the task touches. Give the id and one line on why each binds.
> 3. **Open decisions.** Every design choice, convention, spec question or operator-held fact the task leaves open, including any the task text names as open. For each: settled by `<node id + quote>`, `UNSETTLED`, `OPERATOR` (a fact or design choice only the operator can give), or `WAITS-ON <work id>`.
> 4. **Decidable slices.** Propose the solution leaves that can be written now: for each, what it delivers, where it lands (`file:line` in firmware or the machine record), the decisions it depends on, and how each criterion would be verified (test, inspection, analysis). List separately the leaves held by a `WAITS-ON`.
>
> Output: sections Applicable decisions, Open decisions, Decidable slices, Held leaves. Under 80 lines.

---

## 1. Readiness pass (reasoning tier, effort high, read-only)

> Solution under review: `<SOL-ID>`. Decide whether it is ready to build: every decision settled, discovery left to implementation. You may read `docs/` to locate the surfaces the solution's locus and interfaces name; cite `file:line`, don't dump.
>
> Do not treat the solution text as the plan to follow. Treat it as one proposal, and decide from the graph and the repository where and how this work should land.
>
> 1. `show <SOL-ID>` and `show <SOL-ID>.C<N>` for every criterion. `trace <SOL-ID>` up to the targeted requirement criteria; `show` each in full.
> 2. **Intent.** Trace on up to the personas and journeys the work serves; `show` the ones it reaches. State in two or three lines what outcome the work exists for and who consumes its output (a builder, an adopter on another machine and supply, an agent following a method).
> 3. **Repository-only reader.** Would a reader holding only the published repository, on a different machine and a different supply, be stranded by this work as specified, or by what it leaves out? Name the document that must carry what they need.
> 4. **Applicable decisions.** Beyond the solution's own lineage, find the cross-cutting decisions and definitions that govern what it touches: `query "<topic>" --mode hybrid` for each surface, behaviour and convention it adds or changes. For each: id, and one line on why it binds this solution.
> 5. **Surrounding work.** Siblings under the same parent, other solutions on the same requirement criteria, and `query "<behaviour>" --mode hybrid` for solutions elsewhere (finished or open) that already do, partly do, or will change the same thing. Report each overlap: id or `file:line`, and what it already covers.
> 6. **Placement.** Name the files the solution changes or creates (`file:line`) and record the existing-capability answer: reuse, extend, or create new, with the options rejected and why. Name any part already built elsewhere (a SPLIT or a premise correction, not a rebuild).
> 7. **Consumers of what changes.** For every fact, declaration or contract the solution changes, list every place that depends on or restates it: firmware parameters, generated records under `docs/` that pin input digests, simulation results, other documents in the machine's record and working folder. State for each whether a criterion of this leaf or another solution covers it.
> 8. **Open decisions.** Every design choice, spec question or operator-held fact the criteria leave open. For each: settled by `<node id + quote>`, `UNSETTLED`, or `OPERATOR` (only the owner can give it: their supply, circuit, a part, a design choice between workable options).
> 9. **Decidability.** Is every decision this solution needs makeable now, or does one depend on work not yet built?
>
> Output: `VERDICT: BUILD | UNSETTLED | SPLIT | DEFER`, then sections Intent, Repository-only reader, Applicable decisions, Surrounding work, Placement, Consumers of what changes, Open decisions, Decidability. Keep it under 110 lines.

## 2. Implement (reasoning tier, fresh every round)

> Implement `<SOL-ID>` in `<WT>`. Read the solution and each criterion in full (`show <SOL-ID>.C<N>`), the readiness report at `<path>` (where it and the graph disagree, the graph governs), and the preflight brief in the hand-off above. Treat the brief as a head start you check against the repository.
>
> Rules (non-negotiable):
> - Follow CLAUDE.md and the verification section of `.claude/skills/stage0-build-coffee/SKILL.md`. Every criterion gets a verification that would catch a real regression, of the kind its `verification` field names. Trace comments naming the criterion go on tests only, never in implementation code.
> - Verify only the work you changed, with the narrowest command that covers it (one PlatformIO test environment or suite, the one Python tool test, a CSV parse, the arithmetic shown). Never run `task fw:verify`; the gate runs it once.
> - If you change any input a generated record under `docs/` pins by digest, regenerate that record with its own tool in the same change.
> - Chase every fact you change through every document that restates it, in the machine's record and its working folder.
> - Honour every settled decision. Add no content, surface or behaviour beyond what the criteria and those decisions require.
> - `show` every node before you cite it.
> - If you find a defect that makes a criterion unachievable, **stop and report it** (`file:line`, which criterion, why). Never route around it.
> - Commit your work on the current branch before you submit (conventional commit referencing the criteria, ending with the co-author line the session gives), so the verified version is a real commit.
>
> Output: submit your `implement_slice` response yourself, exactly as the served `handover_instruction` directs, through the engine invocation in the hand-off, naming your own model id as the producing model and passing every flag `required_submission_flags` names. On a schema rejection (exit 5) or a `reparked` outcome, read the rejection or its validator_findings, correct your response and resubmit. Report back only the settled outcome it returns, plus changed files, the criterion → verification mapping, and any stop-and-report, never the response itself.

## 3. Fix round (reasoning tier, fresh every round)

> Fix the review findings for `<SOL-ID>` in `<WT>`. Inputs: the findings file `<path>` (every ISSUE so far, grouped by class), the readiness report `<path>`, and the diff `git diff origin/main...HEAD`.
>
> For **each class**: state the class in one line, then search your whole diff for every instance of it, not just the one the reviewer named, and fix the class structurally (change what produces it, not the instance). If a class cannot be fixed without a decision the readiness report and the graph do not settle, stop and report it instead of guessing.
>
> The implement prompt's rules apply. Commit before you submit. You are handed the router's Child hand-off for the new run's pending interrupt; submit that run's `implement_slice` response yourself exactly as its `handover_instruction` directs, naming your own model id and passing every flag `required_submission_flags` names. On a rejection, correct and resubmit.
>
> Output: report back only the settled outcome the submission returns, plus, per class, the instances found (`file:line`), the structural fix, and the verification added, never the response itself.
