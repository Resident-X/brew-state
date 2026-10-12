#!/usr/bin/env python3
"""The build round's gate: the host tier every time, emulation when it can matter.

A build round runs one gate, and it is the only verification a change gets
before it merges. The complete verification takes far longer than most changes
deserve, and most of that time is spent asking questions a given change cannot
have moved. So the round runs the part that can never be skipped in full -- every
build, every build-time check, every host test and every host executable under
the sanitizers, the only tier that catches memory and undefined-behaviour
defects -- and runs the emulation tier only when the branch touches something
the emulation reads. The full mutation sweep is not in the round at all; it runs
nightly against main, with the rest of the complete verification.

What the round runs is named by the task runner, which hands the tasks to this
script, so the commands behind each tier exist in one place and the round and
the complete verification cannot drift apart. What decides whether emulation
runs is declared here, once: EMULATION_READS.

What changed is measured from the branch's merge-base with the remote-tracking
main, against the working tree, so uncommitted edits and new files not yet
committed count as much as commits do. Measuring from main's tip instead would
charge the branch with everything main gained since it branched. When the base
cannot be resolved or the changed paths cannot be read, the gate cannot tell
what changed, and it runs the emulation tier rather than guessing that nothing
did.

Everything it decides is printed as a plain statement -- which tiers ran, which
was skipped and why, the paths it judged by -- so whoever reads the output can
report the gate's verdict without knowing how the tasks are laid out. The exit
status is the verdict.

Usage: round_gate.py --task <executable> --host <task> [--host <task> ...]
                     --emulation <task> [--emulation <task> ...] [--repo <dir>]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass, field


#: The remote-tracking branch a round is measured against.
BASE_REF = "origin/main"

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
    then says why.
    """

    base: str | None
    paths: list[str] | None
    problem: str = ""


@dataclass
class Scope:
    """Whether the emulation tier runs, and the statement of why."""

    run_emulation: bool
    reason: str
    judged: list[str] = field(default_factory=list)


def _git(repo: str, *arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", repo, *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


def _split(output: str) -> list[str]:
    return [path for path in output.split("\0") if path]


def changed(repo: str, base_ref: str = BASE_REF) -> Change:
    """The paths the branch changes since its merge-base with `base_ref`.

    The comparison is from the merge-base to the working tree, which takes in
    staged and unstaged edits, and new files git is not told to ignore are added
    to it. Renames are reported as a deletion and an addition, so a file moved
    out of a tree counts against the tree it left as well as the one it entered.
    """
    try:
        merge_base = _git(repo, "merge-base", "HEAD", base_ref)
    except OSError as error:
        return Change(None, None, f"git could not be run ({error})")
    if merge_base.returncode != 0:
        detail = merge_base.stderr.strip() or "no common ancestor"
        return Change(
            None, None, f"the merge-base of HEAD with {base_ref} could not be resolved ({detail})"
        )
    base = merge_base.stdout.strip()

    diff = _git(repo, "diff", "--name-only", "--no-renames", "--no-ext-diff", "-z", base)
    if diff.returncode != 0:
        return Change(
            base, None, f"the paths changed since {base} could not be read ({diff.stderr.strip()})"
        )
    untracked = _git(
        repo, "ls-files", "--others", "--exclude-standard", "--full-name", "-z", "--", ":/"
    )
    if untracked.returncode != 0:
        return Change(
            base, None, f"the files not yet committed could not be read ({untracked.stderr.strip()})"
        )
    return Change(base, sorted(set(_split(diff.stdout)) | set(_split(untracked.stdout))))


def scope(change: Change, base_ref: str = BASE_REF) -> Scope:
    """Whether the emulation tier runs for the change, and why."""
    if change.paths is None:
        return Scope(
            True,
            f"could not tell what changed: {change.problem}. "
            "Running the emulation tier rather than skipping it.",
        )
    against = f"measured from merge-base {change.base[:12]} with {base_ref}"
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


def _say(line: str = "") -> None:
    print(line, flush=True)


def _statement(heading: str, chosen: Scope) -> None:
    _say(f"{heading} {chosen.reason}")
    for path in chosen.judged:
        _say(f"    {path}")


def _run(task: str, name: str, tier: str, repo: str) -> int:
    _say(f"round gate: running {name} ({tier} tier)")
    try:
        status = subprocess.run([task, name], cwd=repo, check=False).returncode
    except OSError as error:
        _say(f"round gate: {name} could not be started ({error})")
        return 127
    _say(f"round gate: {name} {'passed' if status == 0 else f'FAILED with exit status {status}'}")
    return status


def gate(task: str, host: list[str], emulation: list[str], repo: str) -> int:
    """Run the round, print what it did and why, and return its exit status."""
    chosen = scope(changed(repo))
    _say("round gate: the host tier always runs; the emulation tier runs only for a change it reads.")
    _statement(
        "round gate: emulation tier WILL RUN, because" if chosen.run_emulation
        else "round gate: emulation tier WILL BE SKIPPED, because",
        chosen,
    )

    for name in host:
        status = _run(task, name, "host", repo)
        if status != 0:
            _say()
            _say(f"ROUND GATE FAILED: the host tier failed at {name} (exit status {status}).")
            _say("The gate stopped there. The emulation tier was NOT REACHED, so it neither passed nor failed.")
            return 1

    if not chosen.run_emulation:
        _say()
        _say(f"ROUND GATE PASSED: the host tier ran and passed ({', '.join(host)}).")
        _statement("The emulation tier was correctly SKIPPED, because", chosen)
        return 0

    for name in emulation:
        status = _run(task, name, "emulation", repo)
        if status != 0:
            _say()
            _say(f"ROUND GATE FAILED: the emulation tier failed at {name} (exit status {status}).")
            _say(f"The host tier ran and passed ({', '.join(host)}).")
            return 1

    _say()
    _say(
        f"ROUND GATE PASSED: the host tier ({', '.join(host)}) and the emulation tier "
        f"({', '.join(emulation)}) both ran and passed."
    )
    _statement("The emulation tier ran because", chosen)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--task", required=True, help="the task runner executable")
    parser.add_argument("--host", action="append", required=True, help="a host-tier task, in order")
    parser.add_argument("--emulation", action="append", required=True, help="an emulation-tier task, in order")
    parser.add_argument("--repo", default=os.getcwd(), help="the repository root (default: here)")
    arguments = parser.parse_args(argv)
    return gate(arguments.task, arguments.host, arguments.emulation, arguments.repo)


if __name__ == "__main__":
    sys.exit(main())
