#!/usr/bin/env python3
"""Fail when a plant structure does not say whether its equations describe a machine.

Some structures behind this seam are an account of how a real espresso machine of
some architecture behaves. Others exist to give the seam's own checks a second
subject, and their arithmetic is arithmetic about nothing. Both compile, link and
pass tests, so the difference is invisible to anything that reads the tree.

It is not invisible to anything that draws a conclusion from the model's
arithmetic. The mutation sweep next door alters every operator and comparison in
the swept sources in turn and asks whether a test notices; that question is only
worth asking of equations that mean something, because a surviving mutant in a
structure describing no machine reports no gap and a killed one is no evidence
against one. So the sweep has to know which structures are which, and the only
answer that does not depend on somebody remembering is one the tree carries.

So every structure under the plant root defines PLANT_STRUCTURE_MACHINE_CLAIM in
its own header, as one of the values the vocabulary header declares, and this
check fails the build when one does not. It runs over the whole tree rather than
over the structure a build selected, so a structure nobody compiles cannot sit
there unanswered -- and a structure added later cannot reach the seam without
answering, which is the whole point: the population the sweep draws from follows
the tree, and a structure arriving without a claim would silently either join it
or be left out of it.

Three things are checked, because each can pass while another is broken:

  * the vocabulary itself still draws its line where it should -- at whether the
    equations describe a machine, and at nothing else. A vocabulary that has
    grown a term for how closely, or for how far a structure has been verified,
    would have every structure answering a different question from the one the
    sweep asks,
  * every structure declares a claim, exactly once, and from that vocabulary, and
  * at least one structure claims to describe a machine. A tree where none does
    is a tree the sweep can draw no population from at all, and it is worth
    reporting here -- where it is cheap -- as well as where the sweep meets it.

The check fails rather than passes when it cannot find what it is meant to
inspect: no plant root, no structures, no vocabulary. A check that inspects
nothing must not report success.

What is deliberately not checked is whether a structure's claim about itself is
true. For the machine-describing case that is the same question as whether its
equations are right, which no build-time check reaches and which verification
against hardware is what settles.

Usage: check_machine_claim.py --plant-root <dir> --include-dir <dir>
"""

from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check_support_status import Uninspectable, definitions  # noqa: E402
from structure_symbols import Structure, discover  # noqa: E402
from vendor_symbols import strip_comments_and_strings  # noqa: E402

#: The header the vocabulary is declared in, relative to the include directory.
VOCABULARY_HEADER = "plant_machine_claim.h"

#: The type the vocabulary's values belong to.
VOCABULARY_TYPE = "plant_machine_claim_t"

#: The macro every structure defines to declare what its equations are about.
CLAIM_MACRO = "PLANT_STRUCTURE_MACHINE_CLAIM"

#: The claim that puts a structure's arithmetic in the sweep's population, and
#: the claim that keeps it out.
#
# These two names are the whole of the distinction, so -- unlike the structures'
# own symbols, which are read out of the structures because that set grows --
# they are named here. The vocabulary is required to declare exactly them, in
# either order, so renaming one in the header fails this check loudly instead of
# quietly changing which structures the sweep draws mutants from.
DESCRIBES_NO_MACHINE = "PLANT_DESCRIBES_NO_MACHINE"
DESCRIBES_A_MACHINE = "PLANT_DESCRIBES_A_MACHINE"

_ENUM_BODY = re.compile(r"\benum\b[^;{]*\{([^}]*)\}\s*" + VOCABULARY_TYPE + r"\s*;", re.DOTALL)
_ENUMERATOR = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)")


def vocabulary(path: str) -> list[str]:
    """The values the vocabulary header declares, in declaration order.

    Read out of the header rather than listed here, so the check and the
    structures cannot disagree about what the words are -- only about which one
    a structure is entitled to.
    """
    if not os.path.isfile(path):
        raise Uninspectable(f"no vocabulary header at {path}")

    with open(path, "r", encoding="utf-8") as handle:
        cleaned = strip_comments_and_strings(handle.read())

    body = _ENUM_BODY.search(cleaned)
    if body is None:
        raise Uninspectable(
            f"{path} declares no {VOCABULARY_TYPE}, so there is no vocabulary for a structure "
            "to draw its claim from"
        )

    values: list[str] = []
    for entry in body.group(1).split(","):
        name = _ENUMERATOR.match(entry)
        if name is not None:
            values.append(name.group(1))
    return values


def vocabulary_problems(values: list[str]) -> list[str]:
    """Every way the declared vocabulary stops drawing the line it should.

    The distinction is binary: these equations describe a machine, or they
    describe none. A third term would describe a judgement no build-time check
    can make and would give an arriving structure somewhere vague to sit, from
    which whether the sweep draws mutants from it is undecided. A missing term
    leaves a structure with nothing to say.
    """
    problems: list[str] = []
    declared = set(values)

    for required in (DESCRIBES_NO_MACHINE, DESCRIBES_A_MACHINE):
        if required not in declared:
            problems.append(f"declares no '{required}', so no structure can say it")

    for extra in sorted(declared - {DESCRIBES_NO_MACHINE, DESCRIBES_A_MACHINE}):
        problems.append(
            f"declares '{extra}', which draws a distinction beyond whether the equations "
            "describe a machine"
        )

    if len(values) != len(declared):
        problems.append("declares a value more than once")

    return problems


def structure_claim(header: str, values: list[str]) -> tuple[list[str], str | None]:
    """One structure's claim, and every way it fails to state one.

    The claim is returned only when it is usable, so a structure whose header is
    at fault contributes nothing to the population a caller derives -- a
    structure whose claim cannot be read is not thereby a structure describing
    no machine.
    """
    with open(header, "r", encoding="utf-8") as handle:
        source = handle.read()

    declared = definitions(source, CLAIM_MACRO)

    if not declared:
        return [
            f"defines no {CLAIM_MACRO}, so it reaches the seam without saying whether its "
            "equations describe a machine, and nothing drawing on the model's arithmetic can "
            "tell whether a conclusion about this structure would mean anything"
        ], None
    if len(declared) > 1:
        lines = ", ".join(str(lineno) for lineno, _, _ in declared)
        return [
            f"defines {CLAIM_MACRO} {len(declared)} times (lines {lines}), so which it claims "
            "is unclear"
        ], None

    lineno, value, _ = declared[0]
    if value not in values:
        return [
            f"line {lineno}: claims '{value or '(nothing)'}', which is not one of the declared "
            f"values ({', '.join(values)})"
        ], None

    return [], value


def claims(
    structures: list[Structure], values: list[str]
) -> tuple[dict[str, str], list[str]]:
    """Every structure's claim by name, and every way the tree failed to state one.

    This is the one reader of the declaration. The mutation sweep derives its
    population through it rather than reading the macro itself, so there is no
    second interpretation of what a structure claimed that could drift from this
    one.

    Problems are returned rather than raised so a caller sees all of them at
    once, and so a caller that must refuse on any of them -- as the sweep must,
    because a structure whose claim is unreadable must not be quietly left out
    of the population -- can do so without losing the detail.
    """
    claimed: dict[str, str] = {}
    problems: list[str] = []
    for structure in structures:
        found, claim = structure_claim(structure.header, values)
        problems.extend(f"{structure.header}: {problem}" for problem in found)
        if claim is not None:
            claimed[structure.name] = claim
    return claimed, problems


def machine_describing(claimed: dict[str, str]) -> list[str]:
    """The structures whose equations describe a machine, in name order."""
    return sorted(name for name, claim in claimed.items() if claim == DESCRIBES_A_MACHINE)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plant-root", required=True, help="the directory the structures sit in")
    parser.add_argument(
        "--include-dir", required=True, help="the directory the shared vocabulary sits in"
    )
    args = parser.parse_args(argv)

    if not os.path.isdir(args.plant_root):
        # Distinct from an empty plant root only in how it happened; both leave
        # the check with no structure to have inspected.
        print(f"check_machine_claim: no plant root at {args.plant_root}", file=sys.stderr)
        return 2

    vocabulary_path = os.path.join(args.include_dir, VOCABULARY_HEADER)
    try:
        values = vocabulary(vocabulary_path)
    except Uninspectable as absent:
        print(f"check_machine_claim: {absent}", file=sys.stderr)
        return 2

    failed = False

    problems = vocabulary_problems(values)
    if problems:
        failed = True
        print(
            "check_machine_claim: the vocabulary no longer draws its line at whether the "
            "equations describe a machine",
            file=sys.stderr,
        )
        for problem in problems:
            print(f"  {vocabulary_path}: {problem}", file=sys.stderr)

    structures = discover(args.plant_root, args.include_dir)
    if not structures:
        # A tree with no structures is a tree this check establishes nothing on.
        # Reporting success would say every structure has answered.
        print(
            f"check_machine_claim: no structures under {args.plant_root} -- there is nothing "
            "to have carried a claim",
            file=sys.stderr,
        )
        return 2

    claimed, problems = claims(structures, values)
    if problems:
        failed = True
        print(
            "check_machine_claim: a structure does not say whether its equations describe a "
            "machine",
            file=sys.stderr,
        )
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)

    describing = machine_describing(claimed)
    if not describing and not problems:
        # Reported here as well as in the sweep, because it is cheap here and
        # because the two failures are different: this one says the tree has
        # nothing whose arithmetic a conclusion could be drawn from, which is
        # wrong about the tree rather than wrong about one run of a tool.
        failed = True
        print(
            "check_machine_claim: no structure claims to describe a machine, so the plant model "
            "carries no arithmetic any conclusion about a machine could be drawn from -- and "
            "anything deriving a population from these claims would have an empty one",
            file=sys.stderr,
        )

    if failed:
        return 1

    summary = ", ".join(f"{name} {claim}" for name, claim in sorted(claimed.items()))
    print(
        f"check_machine_claim: all {len(claimed)} structure(s) say whether their equations "
        f"describe a machine ({summary})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
