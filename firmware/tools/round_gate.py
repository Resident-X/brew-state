#!/usr/bin/env python3
"""The build round's gate: the host tier every time, emulation when it can matter,
and the mutants on the plant lines the branch changes.

A build round runs one gate, and it is the only verification a change gets
before it merges. The complete verification takes far longer than most changes
deserve, and most of that time is spent asking questions a given change cannot
have moved. So the round runs the part that can never be skipped in full -- every
build, every build-time check, every host test and every host executable under
the sanitizers, the only tier that catches memory and undefined-behaviour
defects -- and runs the emulation tier only when the branch touches something
the emulation reads.

After those, the round runs the mutation sweep restricted to the mutants on the
lines the branch changes in the sweep's population, so new plant arithmetic
meets mutation testing before it merges rather than at the next nightly run. It
never runs the full sweep: that runs nightly against main, with the rest of the
complete verification. Which files are in the population is the sweep's own
derivation from the tree, so this script hands it every changed line and the
sweep keeps the ones it draws mutants from. A branch that changes no line there
runs no sweep and does not need the mutation toolchain. A branch that does, on
a host without the toolchain, fails the round. The sweep is not reached when an
earlier tier fails.

What the round runs is named by the task runner, which hands the tasks to this
script, so the commands behind each tier exist in one place and the round and
the complete verification cannot drift apart. What decides whether emulation
runs is declared here, once: EMULATION_READS.

What changed is measured from the branch's merge-base with the remote-tracking
main, against the working tree, so uncommitted edits and new files not yet
committed count as much as commits do. Measuring from main's tip instead would
charge the branch with everything main gained since it branched. The
remote-tracking main is taken as the repository holds it, not fetched. A copy
left behind by the remote can mis-measure a branch, so it is kept rare by
branching from a freshly fetched main rather than checked for here. The base is named by its full reference, which a local
branch cannot shadow. When the base cannot be resolved, or the changed paths or
the changed lines cannot be read, or the lines of a changed C source or header
cannot, the gate cannot tell what changed, and it runs the emulation tier rather
than guessing that nothing did.

The changed lines come from the same measurement: a changed line is a line on
the new side of a zero-context diff from that merge-base to the working tree,
and every line of a new file not yet committed. A file counts as changed when it
has any hunk at all, one that only deletes lines and a file deleted outright
included, because the sweep's judgements about a file are tied to its lines and
a deletion moves or removes them. The diff options and environment that shape
a hunk are pinned; a content filter a repository declares in its gitattributes
is the repository's own and is applied, and this repository declares none for
the sweep's sources. When those
lines cannot be told, the host and emulation tiers still run as they do for any
change the gate cannot measure, and the sweep step then fails the round, saying
why and what to do: it cannot clear the change as touching no plant line, and
the round never runs the full sweep in place of the restricted one. A path whose
own lines alone cannot be read is handed to the sweep as such, and fails the
round only when it is in the sweep's population; a document no sweep draws from
going unread does not.

The selection is a cost measure, not a trust boundary. It guards its
measurement against git state that is unusually configured; it does not
defend against whoever rewrites the hooks, configuration or references of
the tree it runs in, who controls the gate itself. A change that escapes the
selection meets the reviews before it merges and the nightly complete
verification after.

Everything it decides is printed as a plain statement -- which tiers ran, which
was skipped and why, the paths it judged by, whether the sweep ran, was skipped,
was not reached or could not run, and when it ran how many changed lines it
covered and whether it found a problem or could not look -- so whoever reads the
output can report the gate's verdict without knowing how the tasks are laid out.
The closing lines come after the sweep, so they state the whole round's verdict.
The exit status is the verdict.

Usage: round_gate.py --task <executable> --host <task> [--host <task> ...]
                     --emulation <task> [--emulation <task> ...]
                     --sweep <task> [--repo <dir>]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field

import task_gate


#: The remote whose main a round is measured against, and the branch on it that
#: is main.
REMOTE = "origin"
MAIN = "main"

#: The remote-tracking branch a round is measured against, as written in what
#: the gate says.
BASE_REF = f"{REMOTE}/{MAIN}"

#: Every path the emulation tier reads, from the repository root. An entry
#: ending in "/" covers everything beneath it. The firmware tree is taken whole
#: -- sources, headers, parameter descriptions and declarations, the build
#: configuration, the tooling the build and the suite load, and the suite -- so
#: a change that reaches emulated behaviour without touching a source still
#: meets the tier. The records under docs/ are here because the emulation suite
#: fails when one goes stale against the inputs it pins, and the Taskfile
#: because it is what runs the suite.
EMULATION_READS = (
    "firmware/",
    "docs/protection-margin.md",
    "docs/parameter-dominance.md",
    "docs/parameter-identifiability.md",
    "docs/parameter-stability.md",
    "Taskfile.yml",
)


def reads(path: str, triggers: tuple[str, ...] = EMULATION_READS) -> bool:
    """Whether the emulation tier reads the path, a repository-relative one."""
    return any(
        path.startswith(entry) if entry.endswith("/") else path == entry
        for entry in triggers
    )


@dataclass
class Change:
    """What the branch changes since its merge-base, or why that is unknown.

    `paths` is None exactly when what changed could not be told, and `problem`
    then says why. `head` and `base` are the commits measured between, as far
    as they were resolved.

    `lines` maps every changed path whose lines could be read to the new-side
    lines it changes, an empty list for a path whose hunks only delete. It is
    None when the changed lines could not be told at all, and `lines_problem`
    then says why; the paths can be known while the lines are not, and the
    change then counts as one the gate cannot tell, which runs the emulation
    tier whatever the paths are. `unreadable` maps each changed path whose own
    lines alone could not be read to why: whether that leaves a line of the
    sweep's population untold is the sweep's to say, since the population is
    its derivation. `root` is the repository's top level the paths are relative
    to.
    """

    head: str | None
    base: str | None
    paths: list[str] | None
    problem: str = ""
    lines: dict[str, list[int]] | None = None
    lines_problem: str = ""
    root: str | None = None
    unreadable: dict[str, str] = field(default_factory=dict)

    @property
    def lines_unknown_because(self) -> str:
        """Why the changed lines could not be told, or "" when they were."""
        if self.paths is None:
            return self.problem
        return self.lines_problem if self.lines is None else ""


@dataclass
class Scope:
    """Whether the emulation tier runs, and the statement of why."""

    run_emulation: bool
    reason: str
    judged: list[str] = field(default_factory=list)


#: What every diff the change is measured by asks git for, so the paths come out
#: whole and from the top level whatever the user's or the repository's
#: configuration would make of them: no relative paths, no renames, no
#: external diff program.
PATH_DIFF = ("--no-relative", "--no-renames", "--no-ext-diff")

#: What the diff the changed lines are read from asks for besides, each against
#: a setting that would otherwise move or hide a hunk: no context and no
#: context joining hunks (diff.interHunkContext), git's default algorithm and
#: hunk placement (diff.algorithm, diff.indentHeuristic), the content itself
#: rather than a conversion of it (textconv) or a "binary files differ" in place
#: of its hunks (a -diff attribute), and no colour before a hunk's header. A
#: content filter the repository declares in its gitattributes is not a diff
#: option and is applied; this repository declares none for the sweep's sources.
LINE_DIFF = PATH_DIFF + (
    "-U0", "--inter-hunk-context=0", "--diff-algorithm=myers", "--indent-heuristic",
    "--no-textconv", "--text", "--no-color",
)

#: Settings of the environment that reshape a diff whatever its command line
#: says -- GIT_DIFF_OPTS overrides -U itself -- and are dropped before git runs.
RESHAPING_ENVIRONMENT = ("GIT_DIFF_OPTS",)


def _git(repo: str, *arguments: str, text: bool = True) -> subprocess.CompletedProcess:
    environment = {
        name: value for name, value in os.environ.items() if name not in RESHAPING_ENVIRONMENT
    }
    return subprocess.run(
        ["git", "-C", repo, *arguments],
        capture_output=True, text=text, check=False, env=environment,
    )


def _split(output: str) -> list[str]:
    return [path for path in output.split("\0") if path]


def changed(repo: str, remote: str = REMOTE, main: str = MAIN) -> Change:
    """The paths the branch changes since its merge-base with the remote's main.

    The remote's main is read from the repository's remote-tracking reference,
    by its full name. The comparison is from the merge-base to the working tree, which takes in staged
    and unstaged edits, and new files git is not told to ignore are added to it.
    Renames are reported as a deletion and an addition, so a file moved out of a
    tree counts against the tree it left as well as the one it entered.
    """
    try:
        return _measure(repo, remote, main)
    except OSError as error:
        return Change(None, None, None, f"git could not be run ({error})")


def _measure(repo: str, remote: str, main: str) -> Change:
    tracking = f"refs/remotes/{remote}/{main}"
    named = f"{remote}/{main}"

    resolved = _git(repo, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")
    if resolved.returncode != 0:
        return Change(None, None, None, "HEAD could not be resolved to a commit")
    head = resolved.stdout.strip()

    if _git(repo, "rev-parse", "--verify", "--quiet", f"{tracking}^{{commit}}").returncode != 0:
        return Change(
            head, None, None,
            f"there is no remote-tracking {named} ({tracking}) to measure from",
        )

    merge_base = _git(repo, "merge-base", head, tracking)
    if merge_base.returncode != 0:
        detail = merge_base.stderr.strip() or "no common ancestor"
        return Change(
            head, None, None, f"the merge-base of HEAD with {named} could not be resolved ({detail})"
        )
    base = merge_base.stdout.strip()

    diff = _git(repo, "diff", "--name-only", *PATH_DIFF, "-z", base)
    if diff.returncode != 0:
        return Change(
            head, base, None,
            f"the paths changed since {base} could not be read ({diff.stderr.strip()})",
        )
    untracked = _git(
        repo, "ls-files", "--others", "--exclude-standard", "--full-name", "-z", "--", ":/"
    )
    if untracked.returncode != 0:
        return Change(
            head, base, None,
            f"the files not yet committed could not be read ({untracked.stderr.strip()})",
        )
    tracked = _split(diff.stdout)
    new = _split(untracked.stdout)
    change = Change(head, base, sorted(set(tracked) | set(new)))
    try:
        change.root, change.lines, change.unreadable = _lines(repo, base, tracked, new)
    except LinesUnknown as error:
        change.lines_problem = str(error)
    return change


class LinesUnknown(Exception):
    """The lines a branch changes could not be told."""


#: A zero-context hunk's header: where it starts on the new side, and how many
#: lines it covers there, one when the count is left out.
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def _lines(
    repo: str, base: str, tracked: list[str], new: list[str]
) -> tuple[str, dict[str, list[int]], dict[str, str]]:
    """The top level, the new-side lines each changed path changes, and the paths unread.

    A tracked path's lines are read from its own zero-context diff from the
    base to the working tree, named as a literal path from the top level so no
    character in it is read as a pattern, with the options and environment that
    shape a hunk pinned by LINE_DIFF and RESHAPING_ENVIRONMENT; a content filter
    the repository declares in its gitattributes is applied, as git applies it.
    Only the hunk headers are read, which say where each hunk sits on the new
    side and how long it is there; a hunk that only deletes has no length there
    and contributes no line, though its path still counts as changed. A new
    file's lines are all of them. A path whose own lines cannot be read is set
    apart with why, rather than leaving every other path's lines untold.
    """
    top = _git(repo, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        raise LinesUnknown(
            f"the repository's top level could not be resolved ({top.stderr.strip()})"
        )
    root = top.stdout.strip()

    lines: dict[str, list[int]] = {}
    unreadable: dict[str, str] = {}
    for path in tracked:
        # Read as bytes: the hunks carry the file's own content, which need not
        # be in any one encoding, and only the headers are read.
        diff = _git(repo, "diff", *LINE_DIFF, base, "--", f":(top,literal){path}", text=False)
        if diff.returncode != 0:
            unreadable[path] = (
                f"the lines {path} changes since {base} could not be read "
                f"({diff.stderr.decode(errors='replace').strip()})"
            )
            continue
        changed: list[int] = []
        for line in diff.stdout.decode(errors="replace").splitlines():
            hunk = _HUNK.match(line)
            if hunk:
                start = int(hunk.group(1))
                count = 1 if hunk.group(2) is None else int(hunk.group(2))
                changed.extend(range(start, start + count))
        lines[path] = sorted(set(changed))
    for path in new:
        full = os.path.join(root, path)
        if not os.path.isfile(full):
            lines[path] = []
            continue
        try:
            with open(full, "rb") as handle:
                content = handle.read()
        except OSError as error:
            unreadable[path] = f"the new file {path} could not be read ({error})"
            continue
        count = content.count(b"\n") + (1 if content and not content.endswith(b"\n") else 0)
        lines[path] = list(range(1, count + 1))
    return root, lines, unreadable


#: What the sweep draws mutants from: C sources and headers. A path of any other
#: kind is never in its population, so its lines going unread leaves no line of
#: the population untold; which of these a given one is in, the sweep decides.
SWEPT_SUFFIXES = (".c", ".h")


def could_be_swept(path: str) -> bool:
    """Whether a path is of a kind the sweep's population can hold."""
    return path.endswith(SWEPT_SUFFIXES)


def unread_sources(change: Change) -> list[str]:
    """The changed paths of a kind the sweep draws from whose lines could not be read."""
    return sorted(path for path in change.unreadable if could_be_swept(path))


def scope(change: Change, base_ref: str = BASE_REF) -> Scope:
    """Whether the emulation tier runs for the change, and why."""
    at = f"HEAD {change.head}" if change.head else "HEAD"
    unknown = change.lines_unknown_because
    if unknown:
        return Scope(
            True,
            f"could not tell what changed at {at}: {unknown}. "
            "Running the emulation tier rather than skipping it.",
        )
    untold = unread_sources(change)
    if untold:
        return Scope(
            True,
            f"could not tell which lines {len(untold)} changed source(s) change at {at}, so "
            "whether the branch changes a line in the sweep's population cannot be told yet. "
            "Running the emulation tier rather than skipping it:",
            [f"{path}: {change.unreadable[path]}" for path in untold],
        )
    against = (
        f"measured from merge-base {change.base} with {base_ref} "
        f"to {at} and the working tree"
    )
    read = [path for path in change.paths if reads(path)]
    if read:
        return Scope(
            True,
            f"the branch changes {len(read)} path(s) the emulation tier reads, {against}:",
            read,
        )
    if not change.paths:
        return Scope(False, f"the branch changes nothing, {against}.")
    return Scope(
        False,
        f"none of the {len(change.paths)} changed path(s) is one the emulation tier reads, "
        f"{against}. Changed paths judged:",
        list(change.paths),
    )


LABEL = "round gate"


def _say(line: str = "") -> None:
    task_gate.say(line)


def _statement(heading: str, chosen: Scope) -> None:
    _say(f"{heading} {chosen.reason}")
    for path in chosen.judged:
        _say(f"    {path}")


def _run(task: str, name: str, tier: str, repo: str) -> int:
    return task_gate.run(task, name, repo, LABEL, f"{tier} tier")


#: What the sweep's restricted mode writes back for the round to read: the
#: outcome it reached, settled by the sweep from its own exit status. The exit
#: status the round sees cannot say it: a sweep that found nothing to sweep and
#: one that swept and passed both exit 0, and the task runner between the two
#: need not pass a failing status through unchanged.
PASSED = "passed"
SKIPPED = "skipped"
FOUND = "found-a-problem"
NOT_LOOKED = "could-not-look"

#: What to do about a change whose lines the round cannot tell.
UNMEASURABLE_REMEDY = (
    f"To let the round measure the change, fetch the remote's main (git fetch {REMOTE} {MAIN}) "
    f"so the remote-tracking {BASE_REF} exists and shares history with this branch, and make "
    "sure git can read the working tree; then run the round again. The round runs neither a "
    "restricted nor the full sweep in place of a change it cannot measure."
)

NOT_REACHED = "The mutation sweep was NOT REACHED, so it neither passed nor failed."

#: Where the sweep is told, through the environment, that the round asked for
#: it and where its account goes. The sweep refuses to start without the
#: changed lines when this is set, rather than run the full sweep.
ROUND_ACCOUNT_VARIABLE = "MULL_SWEEP_ROUND_ACCOUNT"


@dataclass
class Sweep:
    """What the sweep step concluded: whether it fails the round, and how to say so.

    `verdict` is the clause the closing verdict line carries, and `detail` the
    statement after it.
    """

    failed: bool
    verdict: str
    detail: str


def _covered(account: dict) -> str:
    lines, files = account.get("lines"), account.get("files")
    if isinstance(lines, int) and isinstance(files, int):
        return f" of the {lines} changed plant line(s) in {files} file(s)"
    return ""


def read_account(path: str) -> dict | None:
    """The account the sweep wrote, or None when it wrote none that can be read."""
    try:
        with open(path, encoding="utf-8") as handle:
            account = json.load(handle)
    except (OSError, ValueError):
        return None
    return account if isinstance(account, dict) else None


def concluded(status: int, account: dict | None) -> Sweep:
    """What the sweep step concluded from the account the sweep wrote and its exit status.

    The sweep's own distinction between finding a problem and being unable to
    look is kept, and the two are worded apart so neither is reported as the
    other. The exit status is held to the account: a pass needs both, and an
    account that is missing, or that disagrees with the status, is a sweep the
    round cannot read, which fails it.
    """
    account = account or {}
    outcome = account.get("outcome")
    detail = str(account.get("detail") or "").strip()
    if status == 0 and outcome == SKIPPED:
        return Sweep(
            False,
            "the mutation sweep was correctly SKIPPED, because the branch changes no line in the "
            "sweep's population",
            "The mutation sweep was correctly SKIPPED: " + (detail or "no changed line is in it."),
        )
    if status == 0 and outcome == PASSED:
        return Sweep(
            False,
            f"the mutation sweep{_covered(account)} ran and passed",
            "The mutation sweep ran and passed: " + (detail or "every survivor is accounted for."),
        )
    if status != 0 and outcome == FOUND:
        if account.get("state") == "ran":
            return Sweep(
                True,
                f"the mutation sweep{_covered(account)} FOUND A PROBLEM (exit status {status})",
                (
                    "This is a finding, not a failure to look: the sweep's report above names each "
                    "unreviewed survivor, gap or stranded judgement. " + detail
                ).strip(),
            )
        return Sweep(
            True,
            f"the mutation sweep FOUND A PROBLEM before drawing any mutant (exit status {status})",
            "This is a finding, not a failure to look: the sweep's output above says what it "
            "found in the population it derives.",
        )
    if status != 0 and outcome == NOT_LOOKED:
        if account.get("lines_unknown"):
            return Sweep(
                True,
                f"the mutation sweep COULD NOT RUN (exit status {status}), because the round could "
                "not tell which plant lines the branch changes",
                detail or "Its output above names the source whose lines could not be read.",
            )
        if account.get("toolchain_missing"):
            return Sweep(
                True,
                f"the mutation sweep COULD NOT RUN (exit status {status}): the branch changes lines "
                "in the sweep's population and the mutation toolchain the sweep needs is MISSING "
                "on this host",
                "The sweep could not look, so it neither passed nor found a problem. "
                + (detail or "Its output above says which tool was not found."),
            )
        return Sweep(
            True,
            f"the mutation sweep COULD NOT LOOK (exit status {status}), so it neither passed nor "
            "found a problem",
            detail or "Its output above says why.",
        )
    return Sweep(
        True,
        f"the mutation sweep COULD NOT RUN: it exited with status {status} and left no account the "
        "round can read of whether it swept, skipped or found a problem",
        "This is the sweep being unable to look, not a finding. Its output above is all there is.",
    )


def write_changed_lines(path: str, change: Change) -> None:
    """Write the changed lines where the sweep's restricted mode reads them.

    The top level is given with them because the paths are relative to it and
    the sweep runs from its own project directory below it. The paths whose
    lines could not be read go with them, so the sweep -- whose population it
    is -- can refuse to run when one of them is in it.
    """
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(
            {"root": change.root, "base": change.base, "head": change.head, "files": change.lines,
             "unreadable": change.unreadable},
            handle, sort_keys=True,
        )


def sweep_step(task: str, name: str, repo: str, change: Change) -> Sweep:
    """Run the sweep over the lines the branch changes, or fail when they cannot be told."""
    unknown = change.lines_unknown_because
    if unknown:
        _say(
            f"round gate: NOT running {name} (mutation sweep): the round could not tell which "
            f"plant lines the branch changes ({unknown})"
        )
        return Sweep(
            True,
            "the mutation sweep COULD NOT RUN, because the round could not tell which plant lines "
            "the branch changes",
            f"Cause: {unknown}. {UNMEASURABLE_REMEDY}",
        )
    with tempfile.TemporaryDirectory() as handover:
        changed_lines = os.path.join(handover, "changed-lines.json")
        account_path = os.path.join(handover, "sweep-account.json")
        write_changed_lines(changed_lines, change)
        lines = sum(len(changed) for changed in change.lines.values())
        _say(
            f"round gate: running {name} (mutation sweep) over the {lines} changed line(s) in "
            f"{len(change.lines)} changed path(s); the sweep keeps the ones in its population"
        )
        # The account's place goes in the environment as well as the
        # arguments: the arguments reach the sweep only if its task forwards
        # them, and the environment reaches it regardless, so a restriction lost
        # on the way is refused by the sweep rather than run as the full sweep.
        status = task_gate.invoke(
            task, name, repo, LABEL,
            ("--", "--changed-lines", changed_lines, "--changed-lines-result", account_path),
            env={**os.environ, ROUND_ACCOUNT_VARIABLE: account_path},
        )
        account = read_account(account_path)
    _say(f"round gate: {name} exited with status {status}")
    return concluded(status, account)


def gate(task: str, host: list[str], emulation: list[str], sweep: str, repo: str) -> int:
    """Run the round, print what it did and why, and return its exit status."""
    change = changed(repo)
    chosen = scope(change)
    _say(
        "round gate: the host tier always runs; the emulation tier runs only for a change it "
        "reads; then the mutation sweep runs over the mutants on the plant lines the branch "
        "changes, and never over the full population."
    )
    _statement(
        "round gate: emulation tier WILL RUN, because" if chosen.run_emulation
        else "round gate: emulation tier WILL BE SKIPPED, because",
        chosen,
    )
    if change.lines_unknown_because:
        _say(
            "round gate: the round cannot tell which plant lines the branch changes "
            f"({change.lines_unknown_because}). The host and emulation tiers still run, and the "
            "sweep step will then FAIL the round."
        )
    elif unread_sources(change):
        _say(
            "round gate: the lines of a changed source could not be read. The host and emulation "
            "tiers still run, and the sweep then FAILS the round if that source is in its "
            "population."
        )

    for name in host:
        status = _run(task, name, "host", repo)
        if status != 0:
            _say()
            _say(f"ROUND GATE FAILED: the host tier failed at {name} (exit status {status}).")
            _statement(
                "The gate stopped there. The emulation tier was NOT REACHED, so it neither passed "
                "nor failed. Had the host tier passed, it would have "
                + ("run, because" if chosen.run_emulation else "been skipped, because"),
                chosen,
            )
            _say(NOT_REACHED)
            return 1

    if chosen.run_emulation:
        for name in emulation:
            status = _run(task, name, "emulation", repo)
            if status != 0:
                _say()
                _say(
                    f"ROUND GATE FAILED: the emulation tier failed at {name} (exit status {status})."
                )
                _say(f"The host tier ran and passed ({', '.join(host)}).")
                _say(NOT_REACHED)
                return 1

    outcome = sweep_step(task, sweep, repo, change)

    _say()
    if chosen.run_emulation:
        tiers = (
            f"the host tier ({', '.join(host)}) and the emulation tier ({', '.join(emulation)}) "
            "both ran and passed"
        )
    else:
        tiers = f"the host tier ran and passed ({', '.join(host)})"
    if outcome.failed:
        _say(f"ROUND GATE FAILED: {outcome.verdict}.")
        _say(tiers[0].upper() + tiers[1:] + ".")
    else:
        _say(f"ROUND GATE PASSED: {tiers}, and {outcome.verdict}.")
    if chosen.run_emulation:
        _statement("The emulation tier ran because", chosen)
    else:
        _statement("The emulation tier was correctly SKIPPED, because", chosen)
    _say(outcome.detail)
    return 1 if outcome.failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--task", required=True, help="the task runner executable")
    parser.add_argument("--host", action="append", required=True, help="a host-tier task, in order")
    parser.add_argument("--emulation", action="append", required=True, help="an emulation-tier task, in order")
    parser.add_argument(
        "--sweep", required=True,
        help="the mutation sweep's task, run restricted to the lines the branch changes",
    )
    parser.add_argument("--repo", default=os.getcwd(), help="the repository root (default: here)")
    arguments = parser.parse_args(argv)
    return gate(arguments.task, arguments.host, arguments.emulation, arguments.sweep, arguments.repo)


if __name__ == "__main__":
    sys.exit(main())
