#!/usr/bin/env python3
"""How a term of a build's source filter is read.

A filter is a sequence of `+<path>` and `-<path>` terms, and two things in this
tree need to know what path a term names: the check that reports which plant
structure a build compiles, and the reader that reports which environments
produce a host artefact. They ask different questions of the answer, but the
answer is the same one, and it lives here so there is one of it.

There was not, and the two copies did not drift: they were written the same and
were both wrong, which is what a copy does before it ever gets the chance. Each
removed the leading `./` that means "from here" with `lstrip("./")`, which
removes every leading `.` and `/` rather than that prefix, so
`../plant/thermoblock/` arrived at `plant/thermoblock` -- a directory the build
did not name, reported as one it did. The check whose whole job is to refuse a
build that has not settled which structure it compiles reported one it had not.
"""

from __future__ import annotations

import re

#: One `+<path>` or `-<path>` term. The sign and the path are separate answers:
#: a later term can take back what an earlier one added, so a caller reading
#: only the additions would report what the filter no longer says.
TERM = re.compile(r"([+-])\s*<([^>]*)>")

#: What a path means when it is written relative to where the filter is read
#: from. Removed as a prefix -- the whole of it or none of it.
_HERE = "./"

#: A run of separators where one was meant. `a//b` is `a/b` to every filesystem
#: this runs on, and collapsing it before the prefixes are removed is what keeps
#: `.//x` reading as `./` followed by `x` rather than as `./` followed by a root.
_RUN_OF_SEPARATORS = re.compile(r"/{2,}")


def path_of(term: str) -> str:
    """The path a filter term names, in the one form every caller compares against.

    Separators are made forward-slashed and runs of them collapsed, surrounding
    whitespace goes, a trailing slash goes because a directory is the same
    directory with or without one, and a leading `./` goes because it says only
    that the path is relative -- which every path in a filter already is. A term
    that is only `.` names the root itself, and is the empty path every caller
    reads as "everything".

    Nothing else goes. A term naming somewhere other than under the filter's own
    root is left saying so, which is the whole of what this function had wrong.
    """
    path = _RUN_OF_SEPARATORS.sub("/", term.strip().replace("\\", "/"))
    while path.startswith(_HERE):
        path = path[len(_HERE) :]
    path = path.rstrip("/")
    return "" if path == "." else path


def terms(source_filter: str) -> list[tuple[str, str]]:
    """Every term of the filter, in order, as (sign, path)."""
    return [(sign, path_of(path)) for sign, path in TERM.findall(source_filter)]
