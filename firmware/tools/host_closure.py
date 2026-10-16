#!/usr/bin/env python3
"""Run the host tier in a tree holding only the files the build round declares it reads.

The build round skips the host tier for a branch that changes none of the paths
round_gate.HOST_READS declares. That is safe only while those paths are the
whole of what the tier reads: a host test that began reading a document, a
board design or anything else outside them would then fail on main without the
round that changed it ever running the tier. This builds a temporary tree from
the files git tracks under exactly those paths, runs the host tier's tasks in
it, and fails when any of them fails, so such a read fails the complete
verification at night. It is not part of the round.

The paths are taken from the round gate, not restated, so there is one
declaration of them. A declared entry that selects no tracked file fails the run,
naming it: a stale declaration (a file renamed or removed) would otherwise
leave the tree short of what the round believes the tier reads, and a set that
selects nothing at all builds a tree with nothing in it, which would pass every
host test for free.

The tree is a git repository of its own: a tooling test runs git against the
tree it is in. The files are committed in it with a fixed identity and signing
off, given on the command line so no configuration of the real repository or of
the user is read or written.

Only files git tracks are copied, because the check runs against main at night.
A new file not yet committed is therefore absent from the tree until it is
committed; --include-untracked also takes the files git neither tracks nor
ignores, so a branch can be probed before it is committed. The number of files
copied is printed.

The tasks are named by the task runner, which hands them to this script, as it
does for the round gate and the complete verification.

Usage: host_closure.py --task <executable> --host <task> [--host <task> ...]
                       [--path <path> ...] [--repo <dir>] [--include-untracked]
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

import round_gate
import task_gate

LABEL = "host closure"


#: The identity and settings the tree's one commit is made with, as options of
#: the command so nothing is read from or written to any configuration.
IDENTITY = "host-closure"
EMAIL = "host-closure@example.invalid"
COMMIT_OPTIONS = (
    "-c", f"user.name={IDENTITY}", "-c", f"user.email={EMAIL}",
    "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null",
)


def tracked_under(
    repo: str, paths: tuple[str, ...], include_untracked: bool = False
) -> tuple[list[str] | None, str]:
    """The files git tracks under the paths, or None and why they could not be listed.

    A path ending in "/" covers everything beneath it, as in round_gate.reads;
    any other is one file. Each is handed to git as a literal path, so no
    character in it is read as a pattern. With include_untracked the files git
    neither tracks nor ignores are listed too.
    """
    specs = [f":(literal){path}" for path in paths]
    found: set[str] = set()
    for flags in (("--cached",), ("--others", "--exclude-standard")) if include_untracked else (("--cached",),):
        try:
            listed = subprocess.run(
                ["git", "-C", repo, "ls-files", *flags, "-z", "--", *specs],
                capture_output=True, text=True, check=False,
            )
        except OSError as error:
            return None, f"git could not be run ({error})"
        if listed.returncode != 0:
            return None, listed.stderr.strip() or "git ls-files failed"
        found.update(path for path in listed.stdout.split("\0") if path)
    return [path for path in sorted(found) if round_gate.reads(path, paths)], ""


def make_repository(tree: str) -> str:
    """Make the tree a git repository holding its files in one commit; "" or why it could not be."""
    # An identity in the environment would outrank the options, so it is set there too.
    environment = {
        **os.environ,
        "GIT_AUTHOR_NAME": IDENTITY, "GIT_COMMITTER_NAME": IDENTITY,
        "GIT_AUTHOR_EMAIL": EMAIL, "GIT_COMMITTER_EMAIL": EMAIL,
    }
    for arguments in (("init", "-q"), ("add", "-A"), (*COMMIT_OPTIONS, "commit", "-q", "-m", "host closure")):
        try:
            done = subprocess.run(
                ["git", "-C", tree, *arguments], capture_output=True, text=True, check=False,
                env=environment,
            )
        except OSError as error:
            return f"git could not be run ({error})"
        if done.returncode != 0:
            what = "commit" if "commit" in arguments else arguments[0]
            return f"git {what} failed ({done.stderr.strip()})"
    return ""


def copy_into(repo: str, tree: str, files: list[str]) -> list[str]:
    """Copy the files into the tree, keeping their layout, and return those not in the working tree.

    A file git tracks but the working tree lacks has nothing to copy; it is
    named, not silently dropped, because the run then judges a smaller tree
    than the one declared.
    """
    absent = []
    for path in files:
        source = os.path.join(repo, path)
        if not os.path.lexists(source):
            absent.append(path)
            continue
        target = os.path.join(tree, path)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if os.path.islink(source):
            os.symlink(os.readlink(source), target)
        else:
            shutil.copy2(source, target)
    return absent


def close(
    task: str, host: list[str], paths: tuple[str, ...], repo: str, include_untracked: bool = False,
) -> int:
    """Run the host tasks in a tree of the tracked files under the paths; return the exit status."""
    declared = ", ".join(paths)
    kind = "tracked or untracked" if include_untracked else "tracked"
    files, problem = tracked_under(repo, paths, include_untracked)
    if files is None:
        task_gate.say(
            f"HOST CLOSURE FAILED: the files git tracks under the declared paths ({declared}) "
            f"could not be listed: {problem}"
        )
        return 1
    if not files:
        task_gate.say(
            f"HOST CLOSURE FAILED: the declared paths ({declared}) select no file git tracks "
            f"in {repo}, so a tree built from them holds nothing and could show nothing. A set "
            "that selects nothing fails the run rather than passing it."
        )
        return 1
    stale = [path for path in paths if not any(round_gate.reads(file, (path,)) for file in files)]
    if stale:
        task_gate.say(
            f"HOST CLOSURE FAILED: {len(stale)} declared path(s) select no file git "
            f"{'tracks or leaves untracked' if include_untracked else 'tracks'} in {repo}, so the "
            "declaration is stale and the tree built is not the one the round believes the tier reads:"
        )
        for path in stale:
            task_gate.say(f"    {path}")
        task_gate.say("Correct HOST_READS in round_gate.py: remove or rename each entry named above.")
        return 1
    with tempfile.TemporaryDirectory(prefix="host-closure-") as tree:
        absent = copy_into(repo, tree, files)
        task_gate.say(
            f"{LABEL}: copied {len(files) - len(absent)} {kind} file(s) under the declared paths "
            f"({declared}) into a tree at {tree}, and nothing else."
        )
        if absent:
            task_gate.say(
                f"HOST CLOSURE FAILED: {len(absent)} file(s) git tracks under the declared paths "
                "are missing from the working tree, so the tree built is not the declared one:"
            )
            for path in absent:
                task_gate.say(f"    {path}")
            return 1
        problem = make_repository(tree)
        if problem:
            task_gate.say(f"HOST CLOSURE FAILED: the tree could not be made a git repository: {problem}")
            return 1
        for name in host:
            status = task_gate.run(task, name, tree, LABEL, "host tier, in the tree of declared paths")
            if status != 0:
                task_gate.say()
                task_gate.say(
                    f"HOST CLOSURE FAILED: {name} failed (exit status {status}) in a tree holding "
                    f"only the files under {declared}. A task failing here that passes in the "
                    "full tree reads something outside those paths: either read only what is "
                    "declared, or add the path to HOST_READS in round_gate.py so the round runs "
                    "the tier when it changes."
                )
                return 1
    task_gate.say()
    task_gate.say(
        f"HOST CLOSURE PASSED: {', '.join(host)} ran and passed in a tree holding only the "
        f"{len(files)} {kind} file(s) under {declared}."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--task", required=True, help="the task runner executable")
    parser.add_argument("--host", action="append", required=True, help="a host-tier task, in order")
    parser.add_argument(
        "--path", action="append", default=None,
        help="a path the host tier is declared to read (default: round_gate.HOST_READS)",
    )
    parser.add_argument("--repo", default=os.getcwd(), help="the repository root (default: here)")
    parser.add_argument(
        "--include-untracked", action="store_true",
        help="also copy the files git neither tracks nor ignores, to probe a branch before it is committed",
    )
    arguments = parser.parse_args(argv)
    paths = tuple(arguments.path) if arguments.path is not None else round_gate.HOST_READS
    return close(arguments.task, arguments.host, paths, arguments.repo, arguments.include_untracked)


if __name__ == "__main__":
    sys.exit(main())
