#!/usr/bin/env python3
"""Fail the build when it does not name exactly one plant structure.

A build that names none and falls back to a default, or names two and lets the
linker pick between duplicate definitions, has taken the choice of dynamics
away from the person building the artefact and hidden it in the build system.
That is run-time selection with extra steps, and it is the failure build-time
selection exists to make unreachable.

So the build stops. It stops before anything is compiled, so the message names
the problem rather than arriving as a duplicate-symbol error from the linker or
as a missing-type error from the first translation unit that got there.

A build that compiles no plant source at all is not a model build and is not
this check's business. A build that compiles the shared parameter loader but no
structure *is* a model build, and is exactly the "names none" case.

Counting is only half of what a build for a machine has to satisfy: a structure
declaring that its equations describe nothing would pass a count of one while
leaving the machine predicting nothing about itself. That half is asked by
check_machine_structure_selected.py, which runs alongside this one.

Usage: check_structure_selection.py --filter "<build src filter>" --plant-root <dir>
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import filter_terms  # noqa: E402
from structure_symbols import STRUCTURE_HEADER  # noqa: E402

#: The directory, relative to the source root, the structures live in.
PLANT_PREFIX = "plant/"


def structure_names(plant_root: str) -> list[str]:
    """Every structure directory under the plant root."""
    if not os.path.isdir(plant_root):
        raise SystemExit(f"check_structure_selection: no plant root at {plant_root}")
    return sorted(
        entry
        for entry in os.listdir(plant_root)
        if os.path.isfile(os.path.join(plant_root, entry, STRUCTURE_HEADER))
    )


def selected(source_filter: str, available: list[str]) -> tuple[set[str], bool]:
    """The structures a filter includes, and whether it touches the plant at all.

    A term naming the plant directory wholesale -- `+<plant/>` -- includes every
    structure in it, which is the two-structure case however many structures
    happen to be there today.
    """
    chosen: set[str] = set()
    touches_plant = False

    plant_root = PLANT_PREFIX.rstrip("/")
    for sign, normalised in filter_terms.terms(source_filter):
        # The plant directory itself, or something under it. A sibling whose
        # name merely begins with the same letters -- `plantation/` -- is a
        # different directory, and reading it as this one is the same mistake
        # as reading a set of leading characters as a prefix.
        if normalised != plant_root and not normalised.startswith(PLANT_PREFIX):
            continue
        touches_plant = True

        remainder = normalised[len(PLANT_PREFIX) :] if normalised.startswith(PLANT_PREFIX) else ""
        head = remainder.split("/")[0]

        if head in ("", "*"):
            named = set(available)
        elif head in available:
            named = {head}
        else:
            # A directory under the plant root that is not a structure -- the
            # shared parameter loader, for instance. It makes this a model
            # build without selecting anything.
            continue

        if sign == "+":
            chosen |= named
        else:
            chosen -= named

    return chosen, touches_plant


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--filter", required=True, help="the build's resolved source filter")
    parser.add_argument("--plant-root", required=True, help="the directory the structures live in")
    parser.add_argument("--env", default="", help="the environment name, for the message")
    args = parser.parse_args(argv)

    if not args.filter.strip():
        # An empty filter is a filter the caller could not resolve, not a build
        # that compiles nothing. Reporting "not a model build" for it would
        # turn every wiring mistake into a silent pass.
        print(
            "check_structure_selection: the build's source filter is empty, so which "
            "structure it selects cannot be established",
            file=sys.stderr,
        )
        return 2

    available = structure_names(args.plant_root)
    if not available:
        print(
            f"check_structure_selection: no structures under {args.plant_root}",
            file=sys.stderr,
        )
        return 2

    chosen, touches_plant = selected(args.filter, available)
    where = f" in '{args.env}'" if args.env else ""

    if not touches_plant:
        print(f"check_structure_selection: no plant source is compiled{where} -- not a model build")
        return 0

    if len(chosen) == 1:
        print(f"check_structure_selection: '{next(iter(chosen))}' selected{where}")
        return 0

    if not chosen:
        print(
            f"check_structure_selection: the build{where} compiles the plant model but names "
            "no structure, and there is no default to fall back to",
            file=sys.stderr,
        )
        print(f"  add exactly one of: {', '.join(available)}", file=sys.stderr)
        return 1

    print(
        f"check_structure_selection: the build{where} names {len(chosen)} structures, and the "
        "linker does not get to choose between them",
        file=sys.stderr,
    )
    print(f"  named: {', '.join(sorted(chosen))}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
