#!/usr/bin/env python3
"""How a term of a build's source filter is read.

A filter is a sequence of `+<path>` and `-<path>` terms, and several things in
this tree need to know what a term names and what it covers: the check that
reports which plant structure a build compiles, the reader that reports which
environments produce a host artefact, and the check that reports whether a build
for a machine compiles the shared sources under its own settings. They ask
different questions of the answer, but the answer is the same one, and it lives
here so there is one of it.

How many callers there are is deliberately not stated. The count was wrong here
once already -- a third caller arrived in a branch written beside this one, and
prose saying "two" was true when written and false when merged.

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


#: A term naming everything beneath a directory rather than the directory. A
#: filter may write either, and they mean the same thing to the build.
_EVERYTHING_UNDER = "/*"


def covers(term: str, path: str) -> bool:
    """Whether a filter term takes in the given path, wholesale or exactly.

    Here rather than beside each caller for the reason the reading above is:
    the callers had a predicate each, written the same, and they had already
    begun to disagree -- one read `plant/*` as naming everything under `plant`
    and the other did not, so the same filter answered two ways depending on
    which gate asked.

    The term is what a caller already normalised through `path_of`; the path is
    whatever that caller is asking about. Neither is normalised again here,
    because a predicate that quietly re-reads its arguments is how the two got
    apart in the first place.
    """
    if term in ("", "*"):
        return True
    if term.endswith(_EVERYTHING_UNDER):
        term = term[: -len(_EVERYTHING_UNDER)]
        if term == "":
            return True
    return path == term or path.startswith(term + "/")
