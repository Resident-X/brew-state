#!/usr/bin/env python3
"""Fail when a build for a machine does not carry equations describing a machine.

Counting the structures a build compiles is not enough. A build naming exactly
one structure passes that count whether the structure it named describes the
machine or describes nothing at all, and the fixture structure -- which exists
so the exclusivity checks have a second subject, and whose own header says its
equations describe no machine -- would satisfy it. A machine built against
those equations predicts nothing about itself, and there is no symptom: the
predictions are wrong in the way a machine that has drifted is wrong.

So the claim is asked for as well as the count. Which environments are asked is
discovered from the platform each one names rather than from a list here: an
environment that is not building for the host is building something that will
be energised, and every one of those has to carry a model of itself. The
environments declared to be refused are left out, because a build required to
fail is not an artefact anybody gets.

The claim itself is read through the gate that owns that declaration, so this
cannot come to disagree with what that gate passes.

Usage: check_machine_structure_selected.py --project <dir> --plant-root <dir>
                                           --include-dir <dir>
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_environments  # noqa: E402
import check_machine_claim  # noqa: E402
import structure_symbols  # noqa: E402


def machine_describing(plant_root: str, include_dir: str) -> tuple[list[str], list[str]]:
    """The structures whose equations describe a machine, and why the tree may not say.

    An unreadable claim is a problem rather than a structure describing nothing.
    Read the other way it would take a structure out of the answer silently,
    which is the failure this check exists to prevent arrived at one step later.
    """
    structures = structure_symbols.discover(plant_root, include_dir)
    if not structures:
        return [], [f"no structures under {plant_root}, so no build could select one"]

    vocabulary_path = os.path.join(include_dir, check_machine_claim.VOCABULARY_HEADER)
    values = check_machine_claim.vocabulary(vocabulary_path)
    problems = [
        f"{vocabulary_path}: {problem}"
        for problem in check_machine_claim.vocabulary_problems(values)
    ]

    claimed, faults = check_machine_claim.claims(structures, values)
    problems.extend(faults)
    return check_machine_claim.machine_describing(claimed), problems


def check(project: str, plant_root: str, include_dir: str) -> tuple[list[str], list[str]]:
    """Every way a machine build fails to carry a machine's equations, and what was asked."""
    describing, problems = machine_describing(plant_root, include_dir)
    if problems:
        return problems, []

    available = [
        entry
        for entry in sorted(os.listdir(plant_root))
        if os.path.isfile(os.path.join(plant_root, entry, structure_symbols.STRUCTURE_HEADER))
    ]

    environments = build_environments.machine_environments(build_environments.load(project))
    if not environments:
        return [
            "no environment builds for a machine, so this gate has nothing to cover and "
            "would report success having asked nothing"
        ], []

    asked: list[str] = []
    for environment in environments:
        asked.append(environment.name)
        structure = environment.structure(available)
        if structure is None:
            problems.append(
                f"{environment.name}: builds for a machine but selects no single plant "
                "structure, so it would be energised carrying no model of itself or two"
            )
            continue
        if structure not in describing:
            problems.append(
                f"{environment.name}: selects the '{structure}' structure, whose header does "
                f"not declare {check_machine_claim.CLAIM_MACRO} as "
                f"{check_machine_claim.DESCRIBES_A_MACHINE}, so the machine would run "
                "equations that claim nothing about it"
            )

    return problems, asked


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="the PlatformIO project directory")
    parser.add_argument("--plant-root", required=True, help="the directory the structures live in")
    parser.add_argument("--include-dir", required=True, help="the directory the seam lives in")
    args = parser.parse_args(argv)

    try:
        problems, asked = check(args.project, args.plant_root, args.include_dir)
    except build_environments.ConfigurationError as error:
        print(f"check_machine_structure_selected: {error}", file=sys.stderr)
        return 2

    if problems:
        print(
            "check_machine_structure_selected: a build for a machine does not carry a "
            "machine's equations",
            file=sys.stderr,
        )
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print(
        f"check_machine_structure_selected: {', '.join(asked)} each select one structure "
        "declaring that its equations describe a machine"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
