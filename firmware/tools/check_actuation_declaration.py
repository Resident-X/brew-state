#!/usr/bin/env python3
"""Fail when a plant structure does not say which actuation channels it answers.

The actuation vocabulary belongs to the machine rather than to any structure, so
a structure of a given architecture will not answer every channel in it. Which
ones it does answer is therefore something the structure has to state: until it
does, a caller cannot tell an actuator this architecture does not have from one
it has and is failing to move, and those need opposite responses.

So every structure under the plant root defines
PLANT_STRUCTURE_ACTUATION_CHANNELS in its own header, over the channels the
shared vocabulary declares, and this check fails the build when one does not. It
runs over the whole tree rather than over the structure a build selected, so a
structure nobody compiles cannot sit there unanswered -- and a structure added
later cannot reach the seam without answering.

Three things are checked, because each can pass while another is broken:

  * every structure declares a set, exactly once,
  * the set is built from the shared vocabulary's channels rather than from
    names of its own, so a structure claiming to answer something that cannot be
    commanded is reported rather than left to be discovered by a caller whose
    command goes nowhere, and
  * the set names at least one channel, since a structure answering nothing
    responds to no command at all and has not stated a narrower architecture,
    it has stated a broken one.

The check fails rather than passes when it cannot find what it is meant to
inspect: no structures, or no vocabulary to read the channels out of. A check
that inspects nothing must not report success.

Usage: check_actuation_declaration.py --plant-root <dir> --include-dir <dir>
"""

from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check_support_status import Uninspectable, definitions  # noqa: E402
from structure_symbols import discover  # noqa: E402
from vendor_symbols import strip_comments_and_strings  # noqa: E402

#: The header the channels are declared in, relative to the include directory.
VOCABULARY_HEADER = "machine_actuation.h"

#: The type the channels belong to.
VOCABULARY_TYPE = "actuation_channel_t"

#: The enumerator that terminates the set rather than naming a channel of it.
#
# Named here rather than taken as "the last one", so that a channel appended
# after it -- which would be a channel the count does not cover -- is reported
# instead of silently becoming the terminator.
CHANNEL_COUNT = "ACTUATION_CHANNEL_COUNT"

#: The macro every structure defines to declare what it answers.
DECLARATION_MACRO = "PLANT_STRUCTURE_ACTUATION_CHANNELS"

#: The one operation a declaration is built from: the set containing a channel.
CHANNEL_BIT = "ACTUATION_CHANNEL_BIT"

_ENUM_BODY = re.compile(r"\benum\b[^;{]*\{([^}]*)\}\s*" + VOCABULARY_TYPE + r"\s*;", re.DOTALL)
_ENUMERATOR = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)")
_IDENTIFIER = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")


def vocabulary(path: str) -> list[str]:
    """The channels the vocabulary header declares, in declaration order.

    Read out of the header rather than listed here, so the check and the
    structures cannot disagree about what the channels are -- only about which
    of them a structure answers. The terminating count is not among them: it is
    how many there are, not one of them.
    """
    if not os.path.isfile(path):
        raise Uninspectable(f"no vocabulary header at {path}")

    with open(path, "r", encoding="utf-8") as handle:
        cleaned = strip_comments_and_strings(handle.read())

    body = _ENUM_BODY.search(cleaned)
    if body is None:
        raise Uninspectable(
            f"{path} declares no {VOCABULARY_TYPE}, so there is no vocabulary for a structure "
            "to state its channels from"
        )

    declared: list[str] = []
    for entry in body.group(1).split(","):
        name = _ENUMERATOR.match(entry)
        if name is not None:
            declared.append(name.group(1))

    if CHANNEL_COUNT not in declared:
        raise Uninspectable(
            f"{path} declares {VOCABULARY_TYPE} without a terminating {CHANNEL_COUNT}, so how "
            "many channels there are cannot be established"
        )
    return [name for name in declared if name != CHANNEL_COUNT]


def structure_problems(header: str, channels: list[str]) -> list[str]:
    """Every way one structure fails to state the channels it answers."""
    with open(header, "r", encoding="utf-8") as handle:
        source = handle.read()

    declared = definitions(source, DECLARATION_MACRO)

    if not declared:
        return [
            f"defines no {DECLARATION_MACRO}, so it reaches the seam without saying which "
            "actuation channels it answers"
        ]
    if len(declared) > 1:
        lines = ", ".join(str(lineno) for lineno, _, _ in declared)
        return [
            f"defines {DECLARATION_MACRO} {len(declared)} times (lines {lines}), so which "
            "channels it answers is unclear"
        ]

    lineno, value, _ = declared[0]
    problems: list[str] = []
    named = _IDENTIFIER.findall(value)
    answered = [name for name in named if name in channels]

    for name in named:
        if name in channels or name == CHANNEL_BIT:
            continue
        if name == CHANNEL_COUNT:
            problems.append(
                f"line {lineno}: names {CHANNEL_COUNT}, which counts the channels rather than "
                "being one of them"
            )
            continue
        problems.append(
            f"line {lineno}: names '{name}', which is not a channel the machine has "
            f"({', '.join(channels)}) -- a structure cannot answer a channel nothing can command"
        )

    if not problems and not answered:
        problems.append(
            f"line {lineno}: names no channel, so it answers nothing and no command reaches it"
        )

    if len(answered) != len(set(answered)):
        problems.append(f"line {lineno}: names a channel more than once")

    return problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plant-root", required=True, help="the directory the structures sit in")
    parser.add_argument(
        "--include-dir", required=True, help="the directory the shared vocabulary sits in"
    )
    args = parser.parse_args(argv)

    try:
        channels = vocabulary(os.path.join(args.include_dir, VOCABULARY_HEADER))
    except Uninspectable as absent:
        print(f"check_actuation_declaration: {absent}", file=sys.stderr)
        return 2

    if not channels:
        print(
            "check_actuation_declaration: the vocabulary declares no channel, so there is "
            "nothing for a structure to answer",
            file=sys.stderr,
        )
        return 2

    structures = discover(args.plant_root, args.include_dir)
    if not structures:
        # A tree with no structures is a tree this check establishes nothing
        # on. Reporting success would say every structure has answered.
        print(
            f"check_actuation_declaration: no structures under {args.plant_root} -- there is "
            "nothing to have stated a set of channels",
            file=sys.stderr,
        )
        return 2

    findings: list[str] = []
    for structure in structures:
        for problem in structure_problems(structure.header, channels):
            findings.append(f"  {structure.header}: {problem}")

    if findings:
        print(
            "check_actuation_declaration: a structure does not state which actuation channels "
            "it answers",
            file=sys.stderr,
        )
        for finding in findings:
            print(finding, file=sys.stderr)
        return 1

    print(
        f"check_actuation_declaration: {len(structures)} structure(s) state which of "
        f"{len(channels)} channel(s) they answer"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
