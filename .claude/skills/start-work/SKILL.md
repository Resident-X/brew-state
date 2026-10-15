---
name: start-work
description: Operator skill owned by this repository (it replaces the upstream start-work, which the skill sync skips) — the entry point for a build or slicing session on the coffee machine graph. Reads the latest nightly verification of main first (`task daily:status`), then asks the operator to pick a target from this project's open epics and phase tasks (DEL-CONTROLLER-HARDWARE first) before doing anything else, then sets up a fresh worktree off the latest main, asks `next` what is actionable, lets the operator pick, and routes the pick to /stage0-build (solutions) or slicing homework + /staircase-plan (tasks). Holds the operator's session policy: when to continue, when to pause, how to fan out. Use at the start of every delivery session.
---

# Start work — pick an item from `next` and route it

A **thin launcher** for this repository. Process rules live in the skills it routes to (`/stage0-build`, `/staircase-build`, `/staircase-plan`) and in CLAUDE.md. This file holds only the session steps and the operator's pause policy, never a copy of their rules.

This repository owns this skill under the upstream name: the upstream `start-work` offers the Staircase engine repository's epics as targets, so `task sc:sync-skills` skips it (the Taskfile's `REPO_SKILLS`) and this copy is tracked instead. Everything after the pick follows upstream: `/stage0-build` is used as the sync installs it.

## Steps (in order)

1. **Daily result, then target.** The session's very first action is one read of `task daily:status`: the latest nightly full verification of `main`. The command always exists, so the read is never conditional. Its first output line is the verdict word: `green`, `red`, `none` or `unknown`; it exits non-zero only for `unknown`. Show the result above the list. Do not investigate it: no log reads, no run views. A `red` result only adds an option 0, *fix the nightly failure*, carrying its run link, shown above the list; on that pick, investigate the run and target a corrective solution under `DEL-MAINTENANCE`. An `unknown` or `none` result is shown with its reason above the list, adds no option and does not delay the target question. Then ask the target question at once. Build its list from one read, `./engine/staircase tree DEL-BREW-STATE-DELIVERY --open --depth 1 --format json` from the main checkout, and run nothing else before the operator answers. The read comes before any fetch, so it reflects the main checkout's index and may lag `main`; that is acceptable for a menu, and step 4's `next` runs against the fresh worktree. Sessions idle here, and everything after the pick must see the `main` of the moment the operator picks. List, in this order:
   1. **Controller hardware** `DEL-CONTROLLER-HARDWARE`. Always first while it is open.
   2. **Maintenance** `DEL-MAINTENANCE`. Always listed. It is a continuous lane outside the roadmap's phases, so the tree read never shows it.
   3. Every other open child of the roadmap the tree read returns, in its phase order. Show each as `id — title` with its category (epic or task).
   4. **Other.** The operator names a node.

   If the tree read fails (no binary, no index), show options 1, 2 and Other and say why the rest is missing. Do not go and fix it before asking.
2. **Worktree (only after the pick).** `git fetch origin main` now, so the worktree includes everything merged since the session started; then `git worktree add -b <tmp-branch> ../coffee-wt-<random> origin/main`. The Bash tool's working directory falls back to the main checkout between calls, so prefix every command with `cd <worktree> &&`.
3. **Rebuild.** `task sc:init` in the worktree. It installs the engine, syncs the upstream skills, links the embedder and builds the index. The homework's hybrid search needs the embedder.
4. **Find work.** `./engine/staircase next <TARGET-ID> --format json`. Read the whole payload: it is self-describing, so take each value with the meaning shipped beside it.
5. **Choose.** Show the top 5 actionable items with their kind and ask the operator to pick:
   - `ready-build`: build a solution.
   - `awaiting-confirmation`: a solution whose brief must be confirmed before it can be built.
   - `slice-needed`: slice a task.

   The operator may name an item that is not in the five. Several `ready-build` items can run in parallel sessions; blocked items wait for their `depends-on`.
6. **Branch.** `git -C <worktree> branch -m req/<CHOSEN-ID>/<short-slug>`.
7. **Run. Do not skip; start it immediately:**
   - `ready-build` or `awaiting-confirmation` → `/stage0-build <SOL-ID>`. For `awaiting-confirmation`, its Step 1b confirms the brief before the build.
   - `slice-needed` → `/stage0-build` Step 0, then `/staircase-plan` on the task. **The session ends at the graph PR** (author → validate → blind review → PR). Building the new solutions is a new session started from `/start-work`. Never cross from slicing into code in one session.
8. **Close.** When the PR is raised, give the end-of-session summary. Name every engine or skill usage problem met during the session (a command that misbehaved, a skill step that did not fit this repository) so the operator can decide whether to report it upstream.

## Session policy

- **Continue automatically** when the path is clear, either obvious from the start or made clear by homework, and you are not recommending a model change. A model change is the operator's call (`/staircase-build`'s tier-inadequacy rule).
- **Facts and design choices are the operator's.** A fact only the operator holds (their supply, their circuit, a part on the bench) and a design choice between workable options (a margin, a part, a topology) are brought to them with a recommendation, never settled on their behalf. Homework supplies the facts the choice rests on.
- **Homework before any pause.** When something is unclear, blocked or contradictory with no obvious best-practice answer, fan out in parallel (foreground) to:
  - recent commits and PRs;
  - the personas and journeys the work serves;
  - related requirements and decisions, including cross-cutting ones found by `query`, not only the item's lineage;
  - the machine's record (`docs/sunbeam-em7000/`) and the relevant firmware.

  Pick each agent's model tier by its task and resolve it through `/staircase-wf`'s tier→model table. Tell every agent to discover with the engine CLI (`capabilities <cmd>` on an unknown flag), never guess commands, and report node IDs and conclusions, not file dumps. Tell each agent that time matters: do not spend time that can be avoided. Fan out again on specifics if the first pass raises new unknowns.
- **Then decide.** If the homework makes the correct choice clear (strategic, maintainable, reusing a shared seam where reasonable; correct, not easy), proceed, even if it differs from these steps. Pause only if it is still genuinely unclear, and bring a plain-language recommendation grounded in the graph and the work done, never a blind "which do you want?".
- **A failure that is not the slice's.** When a gate or check fails on something the branch did not touch, first `git fetch` and look at what has merged to `main` since the worktree was cut. Another session may already have fixed it, and a rebase clears it. Only if `main` still carries it, find or author the maintenance solution that owns it, and have the blocked solution `depends-on` it.
- **Hard stops** (`/stage0-build`): a finding class that recurs in a later review round, and the end of fix round 3 without a clean review. These signal a design problem; stop and bring a recommendation.
- **Token discipline.** Keep the main context light: delegate reading to fresh, narrowly-briefed agents and keep only their conclusions.
