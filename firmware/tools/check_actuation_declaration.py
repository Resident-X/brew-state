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

Four things are checked, because each can pass while another is broken:

  * every structure declares a set, exactly once,
  * the set is built out of the shared vocabulary's channels, each one through
    the operation that turns a channel into the set containing it -- so a
    structure claiming to answer something that cannot be commanded is reported
    rather than left to be discovered by a caller whose command goes nowhere,
    and so is a channel named bare, which is an ordinary-looking declaration
    whose value is the channel's index rather than the set containing it, and
  * the set names at least one channel, since a structure answering nothing
    responds to no command at all and has not stated a narrower architecture,
    it has stated a broken one, and
  * no other header beside the vocabulary enumerates a channel of it. Two lists
    that must agree eventually do not, and the state this replaced -- the same
    channels enumerated in one seam and named again in the other, kept in step
    by a comment -- would otherwise be reachable again by writing it back.

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
#: One channel named through the operation that makes the set containing it.
_CHANNEL_OF_BIT = re.compile(
    re.escape(CHANNEL_BIT) + r"\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)"
)


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


def second_list_problems(include_dir: str, channels: list[str]) -> list[str]:
    """Every header beside the vocabulary that enumerates one of its channels.

    A second enumeration is the state this vocabulary exists to end. It is
    looked for by enumerator rather than by type name, because a copy made by
    renaming the type is still a copy, and the names are what a reader and a
    consumer would have to keep in step by hand.
    """
    problems: list[str] = []
    for entry in sorted(os.listdir(include_dir)):
        if not entry.endswith(".h") or entry == VOCABULARY_HEADER:
            continue
        path = os.path.join(include_dir, entry)
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as handle:
            cleaned = strip_comments_and_strings(handle.read())
        for body in re.finditer(r"\benum\b[^;{]*\{([^}]*)\}", cleaned, re.DOTALL):
            named = sorted(set(_IDENTIFIER.findall(body.group(1))) & set(channels))
            if named:
                problems.append(
                    f"  {path}: enumerates {', '.join(named)}, which {VOCABULARY_HEADER} "
                    "already enumerates -- two lists of the machine's channels have to be "
                    "kept in step by hand, and eventually are not"
                )
    return problems


def channels_named(value: str, channels: list[str]) -> list[str]:
    """The channels one declaration names, in the order it names them.

    Read off the macro's replacement text rather than off the set it evaluates
    to, because the set is a number and this has to answer which channels went
    into it. A name that is not a channel of the shared vocabulary is not one of
    these; what to say about it is the caller's question, and the two callers
    ask different things of the answer.
    """
    return [name for name in _IDENTIFIER.findall(value) if name in channels]


def channels_answered(source: str, channels: list[str]) -> list[str]:
    """The channels a structure's header declares it answers, or none.

    None is the answer for a header that declares no set or declares more than
    one, because neither states an architecture a reader could act on. Saying so
    by returning nothing keeps this readable by a caller that is not the one
    reporting on the declaration itself -- that caller gets its own failure from
    the check whose subject that is, and would otherwise get two reports of one
    fault worded differently.
    """
    declared = definitions(source, DECLARATION_MACRO)
    if len(declared) != 1:
        return []
    return channels_named(declared[0][1], channels)


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
    answered = channels_named(value, channels)
    # Which channels are named through the operation that makes a set of one.
    through_the_operation = _CHANNEL_OF_BIT.findall(value)

    for name in answered:
        if name not in through_the_operation:
            problems.append(
                f"line {lineno}: names '{name}' bare rather than through "
                f"{CHANNEL_BIT}, so the set it declares is that channel's index rather than "
                "the set containing it -- which answers whichever channels that index happens "
                "to have the bits of"
            )

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

    findings: list[str] = second_list_problems(args.include_dir, channels)
    for structure in structures:
        for problem in structure_problems(structure.header, channels):
            findings.append(f"  {structure.header}: {problem}")

    if findings:
        print(
            "check_actuation_declaration: the machine's actuation channels are not one set "
            "every structure states its answer from",
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
