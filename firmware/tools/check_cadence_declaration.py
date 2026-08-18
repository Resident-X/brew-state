#!/usr/bin/env python3
"""Fail when a cadence figure has no origin, or has more than one home.

Four numbers decide what the control loop's timing and its behaviour without a
reading amount to: the interval between steps, the multiple of it past which a
step is late, the window a reconstruction may go unobserved for, and the
distance it may travel while it does. Two of them are properties of the control
loop and are the same on every machine, so they live as single definitions in
the source. Two are properties of a machine and live in that machine's limits
declaration, which varies with it.

What both kinds have in common is the way they go wrong. A figure like this
enters a tree as a bare constant with nothing asserting it and nothing to check
it against, and that is the shape a load-bearing number takes just before
everybody starts treating it as settled -- so each is required to account for
where it came from. And a figure spelled in two places stops agreeing with
itself the first time either is touched, silently, on exactly the timing
question nobody re-reads -- so each is required to have one home and no more.

This checks both. It does not check that a figure is right: whether ten
milliseconds is short enough for the disturbances this machine sees is a
sufficiency question that no reading of the source can settle, and the account
each figure carries is what lets a reader challenge it instead.

Usage: check_cadence_declaration.py --include-dir <dir> --source-dir <dir>
                                    --declaration <file>
"""

from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check_parameter_origins import load_vocabulary  # noqa: E402

#: The figures that live as a definition in the source, and the macro each is
#: defined as. Named here rather than discovered, for the reason the origin
#: check names its kinds: a check reading its list of what must be declared out
#: of the thing it is inspecting would agree with any edit to it.
COMPILED_IN = {
    "step-interval-ms": "CONTROL_STEP_INTERVAL_MS",
    "late-step-multiple": "CONTROL_STEP_LATE_MULTIPLE",
}

#: The figures that live in a machine's limits declaration, and the fragment of
#: an identifier that would spell one if somebody defined it in the source
#: instead. A definition of one of these is not a duplicate of a constant -- it
#: is a per-machine figure that has stopped varying with the machine, which is
#: worse, because it would go on reading as declared in every limits file while
#: the software ignored all of them.
#:
#: They account for themselves beside their values rather than here, which is
#: why this file carries no line for them and refuses one that appears. Whether
#: every machine's declaration actually carries them, with an origin, is the
#: limits check's question and not this one's -- one figure, one check.
DECLARED_AS_DATA = {
    "loss-tolerance-window-ms": "LOSS_TOLERANCE_WINDOW",
    "excursion-bound-milli-c": "EXCURSION_BOUND",
}

#: What the source is scanned for. A definition whose value is a string is a
#: word rather than a figure -- the vocabulary header spells each of these to
#: name it in a declaration -- so those are not what this is looking for.
#:
#: Blanks are spelled as spaces and tabs rather than as \s, and the value as
#: anything but a newline, because \s matches a line ending: against a valueless
#: definition followed immediately by another -- an include guard above the
#: figure it guards -- the name would take the guard and the value would take
#: the whole of the next line. The figure below it would then be invisible, and
#: this check would report it as defined nowhere, or fail to see a second home
#: for it, while reading a file that plainly contains one.
_DEFINE = re.compile(
    r"^[ \t]*#[ \t]*define[ \t]+([A-Za-z_][A-Za-z0-9_]*)[ \t]+([^\n]+?)[ \t]*$", re.MULTILINE
)

_SOURCE_SUFFIXES = (".c", ".h")


def definitions(*directories: str) -> dict[str, list[str]]:
    """Every non-string definition in the tree, and the files defining each."""
    found: dict[str, list[str]] = {}
    for directory in directories:
        for root, _, names in os.walk(directory):
            for name in sorted(names):
                if not name.endswith(_SOURCE_SUFFIXES):
                    continue
                path = os.path.join(root, name)
                with open(path, "r", encoding="utf-8") as handle:
                    source = handle.read()
                for macro, value in _DEFINE.findall(source):
                    if value.startswith('"'):
                        continue
                    found.setdefault(macro, []).append(path)
    return found


def inspect(path: str, origin_words: frozenset[str]) -> tuple[dict[str, int], list[str]]:
    """What the declaration accounts for, and everything wrong with how it does.

    A line is a figure's name, the origin marker, a kind, and an account. It
    carries no value: the value lives at the figure's one home, and writing it
    here as well would be the second site this whole check exists to prevent --
    the one that goes stale silently, because nothing compiles this file.
    """
    problems: list[str] = []
    accounted: dict[str, int] = {}

    if not os.path.isfile(path):
        return {}, [f"no cadence declaration at {path}, so no figure accounts for itself"]

    with open(path, "r", encoding="utf-8") as handle:
        lines = handle.read().splitlines()

    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        name, marker, rest = line.partition("@")
        name = name.strip()
        if not name:
            problems.append(f"{path}:{number}: '{line}' names no figure")
            continue
        if name in DECLARED_AS_DATA:
            problems.append(
                f"{path}:{number}: '{name}' varies with the machine and accounts for itself "
                "beside its value in that machine's limits declaration. An account here as "
                "well would be a second one, and the two would stop agreeing the first time "
                "either was corrected"
            )
            continue
        if name not in COMPILED_IN:
            problems.append(
                f"{path}:{number}: '{name}' is not a figure the cadence rests on, so nothing "
                "reads what this line accounts for"
            )
            continue
        if name in accounted:
            problems.append(
                f"{path}:{number}: '{name}' was already accounted for on line "
                f"{accounted[name]}"
            )
            continue
        accounted[name] = number

        if not marker:
            problems.append(
                f"{path}:{number}: '{name}' records no origin, so it is a number with nothing "
                "asserting it -- which is the shape one takes just before it is treated as "
                "settled"
            )
            continue

        words = rest.split()
        kind = words[0] if words else ""
        if kind not in origin_words:
            problems.append(
                f"{path}:{number}: '{name}' records its origin as '{kind}', which is not one "
                f"of {sorted(origin_words)}"
            )
        elif not words[1:]:
            problems.append(
                f"{path}:{number}: '{name}' records a kind and no account of what the figure "
                "was arrived at from, so it can be neither reproduced nor challenged"
            )

    for name in sorted(COMPILED_IN):
        if name not in accounted:
            problems.append(
                f"{path}: '{name}' accounts for itself nowhere, so where it came from is not "
                "answerable from anything but somebody's memory"
            )

    return accounted, problems


def homes(defined: dict[str, list[str]]) -> list[str]:
    """Everything wrong with where the figures live."""
    problems: list[str] = []

    for figure, macro in sorted(COMPILED_IN.items()):
        where = defined.get(macro, [])
        if not where:
            problems.append(
                f"'{figure}' is accounted for as {macro} and defined nowhere, so the "
                "declaration describes a figure the software does not have"
            )
        elif len(where) > 1:
            problems.append(
                f"{macro} is defined in {', '.join(sorted(where))}. A cadence figure spelled "
                "in two places stops agreeing with itself the first time either is touched, "
                "and nothing about the running machine says which one it ran on"
            )

    for figure, fragment in sorted(DECLARED_AS_DATA.items()):
        offenders = sorted(
            {path for macro, paths in defined.items() if fragment in macro for path in paths}
        )
        if offenders:
            problems.append(
                f"'{figure}' belongs to a machine's limits declaration and is defined in "
                f"{', '.join(offenders)}. A per-machine figure compiled in has stopped varying "
                "with the machine it describes, while going on reading as declared in every "
                "limits file the tree ships"
            )

    return problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-dir", required=True, help="where the seam's headers live")
    parser.add_argument("--source-dir", required=True, help="where the sources live")
    parser.add_argument("--declaration", required=True, help="the cadence declaration to read")
    args = parser.parse_args(argv)

    vocabulary, origin_problems = load_vocabulary(args.include_dir)
    if vocabulary is None:
        print("check_cadence_declaration: the origin vocabulary could not be read", file=sys.stderr)
        for problem in origin_problems:
            print(f"  {problem}", file=sys.stderr)
        return 2

    for directory in (args.include_dir, args.source_dir):
        if not os.path.isdir(directory):
            print(f"check_cadence_declaration: no such directory: {directory}", file=sys.stderr)
            return 2

    accounted, problems = inspect(args.declaration, vocabulary.words)
    if not accounted and problems:
        print("check_cadence_declaration: there was no declaration to inspect", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 2

    problems.extend(homes(definitions(args.include_dir, args.source_dir)))

    if problems:
        print(
            "check_cadence_declaration: a cadence figure has no origin, or has more than one "
            "home",
            file=sys.stderr,
        )
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print(
        f"check_cadence_declaration: {len(accounted)} cadence figure(s) account for themselves "
        "and each has one home"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
