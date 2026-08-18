#!/usr/bin/env python3
"""Fail when a build for a machine relaxes the settings it compiles our own sources under.

The plant model arrives on a target by being named in that environment's source
filter, which is what puts it under the flags the environment applies to this
project's own sources -- the same flags the control logic already there is
compiled under. Admitted any other way, or admitted with those flags emptied,
it would be the one part of the machine's software nobody's compiler is being
strict about, and nothing would say so.

The exemption a host test environment may hold has no counterpart here. That
exemption exists for an environment compiling sources which are not this
project's through the same path -- a test runner's generated support file -- and
a build for a machine compiles no such thing. Honoured here it would simply be a
way of turning the settings off on the artefact that gets energised.

What this does not ask is that the target's settings match the host tier's.
Widening them to carry the host analysis is the host tier's work and is
deliberately not asked for; what is asked is that whatever the target applies to
the code we wrote, it applies to all of it.

Usage: check_machine_build_settings.py --project <dir> --plant-root <dir>
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_environments  # noqa: E402
import filter_terms  # noqa: E402
import structure_symbols  # noqa: E402
from check_structure_selection import PLANT_PREFIX  # noqa: E402


def shared_directories(plant_root: str) -> list[str]:
    """The directories under the plant root that are not structures.

    The parameter loader lives in one of them. It is found rather than named
    because what makes a directory a structure is a header, and a second shared
    directory arriving later is shared on the same terms.
    """
    if not os.path.isdir(plant_root):
        raise SystemExit(f"check_machine_build_settings: no plant root at {plant_root}")
    return sorted(
        entry
        for entry in os.listdir(plant_root)
        if os.path.isdir(os.path.join(plant_root, entry))
        and not os.path.isfile(
            os.path.join(plant_root, entry, structure_symbols.STRUCTURE_HEADER)
        )
    )


def compiles(source_filter: str, path: str) -> bool:
    """Whether the filter compiles the given path, after every term is applied.

    Walked in order rather than searched, because a term taking a directory
    wholesale includes what is under it and a later term can take it back out
    again. Reading only the additions would report a directory compiled that a
    build has since excluded.

    What a term names, and what it covers, are both asked of the module that
    answers those for every caller. This asked both for itself once and got the
    same answers wrong the same way -- which is what a copy of a reading does,
    and why there is one of it.
    """
    included = False
    for sign, term in filter_terms.terms(source_filter):
        if filter_terms.covers(term, path):
            included = sign == "+"
    return included


def check(project: str, plant_root: str) -> tuple[list[str], list[str]]:
    """Every way a machine build's settings leave our own sources unchecked."""
    shared = shared_directories(plant_root)
    if not shared:
        return [
            f"no shared directory under {plant_root}, so there is nothing this could establish "
            "arrives under a machine build's settings"
        ], []
    environments = build_environments.machine_environments(build_environments.load(project))
    if not environments:
        return [
            "no environment builds for a machine, so this gate has nothing to cover and "
            "would report success having asked nothing"
        ], []

    problems: list[str] = []
    asked: list[str] = []
    for environment in environments:
        asked.append(environment.name)

        for directory in shared:
            if not compiles(environment.source_filter, PLANT_PREFIX + directory):
                problems.append(
                    f"{environment.name}: does not compile {PLANT_PREFIX}{directory}, so what "
                    "every structure shares -- the parameter loader among it -- either does "
                    "not reach the machine or reaches it by some path other than the filter, "
                    "which is what puts it under the settings this environment applies to our "
                    "own sources"
                )

        if not environment.source_flags.strip():
            problems.append(
                f"{environment.name}: applies no settings to this project's own sources, so "
                "the model and the control logic beside it are compiled with whatever the "
                "platform happens to default to"
            )

        exemption = environment.strict_flags_exemption
        if exemption:
            problems.append(
                f"{environment.name}: claims the exemption meant for a build compiling sources "
                f"that are not ours through the same path ({exemption}), which a build for a "
                "machine does not do -- so it is a way of turning the settings off"
            )

    return problems, asked


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="the PlatformIO project directory")
    parser.add_argument("--plant-root", required=True, help="the directory the structures live in")
    args = parser.parse_args(argv)

    try:
        problems, asked = check(args.project, args.plant_root)
    except build_environments.ConfigurationError as error:
        print(f"check_machine_build_settings: {error}", file=sys.stderr)
        return 2

    if problems:
        print(
            "check_machine_build_settings: a build for a machine relaxes the settings it "
            "compiles our own sources under",
            file=sys.stderr,
        )
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print(
        f"check_machine_build_settings: {', '.join(asked)} compile the plant model through the "
        "source filter under settings they apply to every source of ours, with no exemption"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
