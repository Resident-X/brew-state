#!/usr/bin/env python3
"""Run every host artefact the build declares, under the analysis it was built with.

A sanitizer reports nothing until the code runs. An environment verified to
compile and link instrumented and then never executed has been checked for the
wrong thing: the analysis it carries has produced no finding because it has
produced nothing at all.

So the artefacts are discovered rather than named, and each is run against the
parameter descriptions its own structure ships. An environment added later is
run because it exists, not because somebody remembered to add a line here, and
an artefact that exists with nothing to run it against is reported rather than
skipped.

The environments whose artefact leaves the entry point to the test runner are
not here: their artefact takes no description and there is nothing to hand it.
They are run, under the same analysis, by the task that runs the tests.

A parameter description belongs to the structure whose name its file carries --
`<structure>.params`, or `<structure>-<variant>.params` where a structure ships
more than one. Every description a structure ships is run, since a description
that is never run is a description nothing checks can be loaded.

Usage: run_host_artefacts.py --project <dir> --plant-root <dir> --include-dir <dir>
                             --params-dir <dir>
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_environments  # noqa: E402
from structure_symbols import discover  # noqa: E402

#: What a parameter description file is called.
DESCRIPTION_SUFFIX = ".params"

#: What separates a structure's name from the variant, where it ships several.
VARIANT_SEPARATOR = "-"


def descriptions_for(structure: str, params_directory: str) -> list[str]:
    """Every parameter description the named structure ships, in order.

    The match is on the whole of the structure's name, so a structure whose
    name is the beginning of another's does not quietly inherit its
    descriptions.
    """
    if not os.path.isdir(params_directory):
        return []

    found = []
    for entry in sorted(os.listdir(params_directory)):
        if not entry.endswith(DESCRIPTION_SUFFIX):
            continue
        stem = entry[: -len(DESCRIPTION_SUFFIX)]
        if stem == structure or stem.startswith(structure + VARIANT_SEPARATOR):
            found.append(os.path.join(params_directory, entry))
    return found


def unclaimed_descriptions(structures: list[str], params_directory: str) -> list[str]:
    """Every description no structure in the tree claims.

    A description whose name does not match a structure is one nothing runs,
    which is the same silence as an artefact nobody executes: a file that looks
    like part of the analysis and takes no part in it. Renaming a description
    out of the convention is the way that happens by accident.
    """
    if not os.path.isdir(params_directory):
        return []

    claimed = {
        path
        for structure in structures
        for path in descriptions_for(structure, params_directory)
    }
    return [
        os.path.join(params_directory, entry)
        for entry in sorted(os.listdir(params_directory))
        if entry.endswith(DESCRIPTION_SUFFIX)
        and os.path.join(params_directory, entry) not in claimed
    ]


def runs(
    project: str,
    environments: list[build_environments.Environment],
    structures: list[str],
    params_directory: str,
) -> tuple[list[tuple[str, str]], list[str]]:
    """The (artefact, description) pairs to run, and why any could not be made."""
    planned: list[tuple[str, str]] = []
    problems: list[str] = []

    for environment in environments:
        artefact = environment.artefact(project)
        if not os.path.exists(artefact):
            problems.append(f"{environment.name}: {artefact} has not been built")
            continue

        structure = environment.structure(structures)
        if structure is None:
            problems.append(
                f"{environment.name}: builds an artefact taking a parameter description but "
                "names no single structure, so which description to run it against is unknown"
            )
            continue

        descriptions = descriptions_for(structure, params_directory)
        if not descriptions:
            problems.append(
                f"{environment.name}: the '{structure}' structure ships no parameter "
                f"description under {params_directory}, so its artefact cannot be run"
            )
            continue

        planned.extend((artefact, description) for description in descriptions)

    return planned, problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="the PlatformIO project directory")
    parser.add_argument("--plant-root", required=True, help="the directory the structures live in")
    parser.add_argument(
        "--include-dir", required=True, help="the directory the seam's own headers live in"
    )
    parser.add_argument(
        "--params-dir", required=True, help="the directory the parameter descriptions live in"
    )
    args = parser.parse_args(argv)

    try:
        declared = build_environments.load(args.project)
    except build_environments.ConfigurationError as error:
        print(f"run_host_artefacts: {error}", file=sys.stderr)
        return 2

    environments = build_environments.artefact_environments(declared)
    if not environments:
        print(
            "run_host_artefacts: no environment builds a host artefact, so nothing would be "
            "run and the analysis would report success having analysed nothing",
            file=sys.stderr,
        )
        return 1

    structures = [structure.name for structure in discover(args.plant_root, args.include_dir)]

    unclaimed = unclaimed_descriptions(structures, args.params_dir)
    if unclaimed:
        print(
            "run_host_artefacts: these parameter descriptions belong to no structure in the "
            "tree, so nothing runs them -- a description is named for the structure it "
            "describes, as <structure>.params or <structure>-<variant>.params",
            file=sys.stderr,
        )
        for path in unclaimed:
            print(f"  {path}", file=sys.stderr)
        return 1

    planned, problems = runs(args.project, environments, structures, args.params_dir)
    if problems:
        print("run_host_artefacts: an artefact could not be run", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 2

    for artefact, description in planned:
        # Flushed before the run so the artefact's own output follows the line
        # naming it rather than arriving ahead of it in a redirected log.
        print(f"run_host_artefacts: {artefact} {description}", flush=True)
        # Paths are used as given rather than resolved against the project, so
        # the artefact sees the same description path the caller wrote.
        result = subprocess.run([artefact, description], check=False)
        if result.returncode != 0:
            print(
                f"run_host_artefacts: {artefact} exited {result.returncode} on {description}",
                file=sys.stderr,
            )
            return 1

    print(f"run_host_artefacts: {len(planned)} run(s) completed under the analysis")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
