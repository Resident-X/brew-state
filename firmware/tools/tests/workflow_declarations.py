"""Reading the hosted workflows the way the checks over them need to.

Two suites inspect `.github/workflows/`: the sweep's, for what its hosted run
may pull in and when it may start, and the complete verification's, for the
nightly that calls the sweep. They read the same declarations and have to agree
on what a reference to other code is, so the reading lives here once rather
than as two copies that drift apart the next time a workflow gains a new kind
of reference.

A `uses:` line names one of two things. A remote action or workflow,
`owner/repo[/path]@ref`, is fetched from somewhere else on the day the run
starts, so it is held to a full commit digest with the release it was in a
trailing comment. A local one is read from the very commit the run was started
on, so it has no ref to pin and is not a way for unchosen code to come in: the
dedicated self-repository form `$/path`, which the workflow linter asks for,
or the older `./path` it replaces. Anything that is neither is refused rather
than waved through, since a check that skips what it cannot classify passes in
exactly the way a check nobody ran does.
"""

from __future__ import annotations

import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
WORKFLOWS = os.path.join(REPO, ".github", "workflows")

#: Read from the same commit as the workflow naming it.
LOCAL = re.compile(r"^[.$]/[\w./-]+$")
#: Fetched from elsewhere, pinned to the full digest a release points at.
REMOTE = re.compile(r"^[\w.-]+/[\w.-]+(?:/[\w./-]+)?@[0-9a-f]{40}$")


def workflows():
    """Each workflow file's name and text, in name order."""
    for name in sorted(os.listdir(WORKFLOWS)):
        if name.endswith((".yml", ".yaml")):
            with open(os.path.join(WORKFLOWS, name), encoding="utf-8") as handle:
                yield name, handle.read()


def uses(declared: str):
    """Every `uses:` value in a workflow, trailing comment included."""
    for line in declared.splitlines():
        stripped = line.strip().lstrip("- ").strip()
        if stripped.startswith("uses:"):
            yield stripped[len("uses:"):].strip()


def is_local(used: str) -> bool:
    return bool(LOCAL.match(used.split("#", 1)[0].strip()))


def unpinned(used: str) -> str | None:
    """Why a `uses:` value could pull in code nobody chose, or None when it cannot."""
    reference, marker, comment = used.partition("#")
    reference = reference.strip()
    if LOCAL.match(reference):
        return None
    if "@" not in reference:
        return f"'{used}' is neither a path in this repository nor a remote reference with a version"
    if not REMOTE.match(reference):
        return f"'{used}' is pinned to a moving reference rather than a digest"
    if not (marker and comment.strip()):
        return f"'{used}' is a digest with nothing saying which release it is"
    return None


def triggers(declared: str) -> list[str]:
    """The event names in a workflow's top-level `on:` block."""
    lines = declared.splitlines()
    if "on:" not in lines:
        raise ValueError("the workflow declares no top-level 'on:' block")
    events = []
    for line in lines[lines.index("on:") + 1:]:
        if line and not line[0].isspace() and not line.startswith("#"):
            break
        match = re.match(r"^  ([\w-]+):", line)
        if match:
            events.append(match.group(1))
    return events
