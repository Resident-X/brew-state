#!/usr/bin/env python3
"""Fail when a build that names the wrong number of plant structures succeeds.

The selection check refuses a build naming none and a build naming two. That
refusal is itself a property of the build, and a property nothing exercises is
a property that quietly stops holding -- a mis-wired pre-script, a check that
returns zero on the path nobody takes, and the refusal is gone with no symptom.

So the two configurations exist in the build file and this drives them. Each
must stop the build, and each must leave no artefact behind: a build that
reports failure while still producing something linkable has not refused, it
has complained.

The environments are named rather than discovered, because a name forgotten
here fails loudly: a configuration that must not build and is never driven is
one this gate says nothing about. What is checked, though, is that every
environment *declaring* it must not build is among them. That declaration is
what excuses an environment from the analysis gate, and an excuse nothing
exercises is a way out of both gates at once.

Usage: check_selection_refused.py --project <dir> --env <name> [--env <name> ...]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_environments  # noqa: E402


def artefact_paths(project: str, environment: str) -> list[str]:
    """Everything the build would leave behind for one environment."""
    build_dir = os.path.join(project, ".pio", "build", environment)
    if not os.path.isdir(build_dir):
        return []
    return [
        os.path.join(build_dir, name)
        for name in sorted(os.listdir(build_dir))
        if name in ("program", "program.exe", "firmware.elf", "firmware.bin")
    ]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="the PlatformIO project directory")
    parser.add_argument(
        "--env", action="append", required=True, dest="envs", help="an environment that must fail"
    )
    parser.add_argument(
        "--pio",
        default=os.environ.get("PIO", os.path.expanduser("~/.platformio/penv/bin/pio")),
        help="the PlatformIO executable",
    )
    args = parser.parse_args(argv)

    project = os.path.realpath(args.project)
    problems: list[str] = []

    try:
        declared = build_environments.load(project)
    except build_environments.ConfigurationError as error:
        print(f"check_selection_refused: {error}", file=sys.stderr)
        return 2

    undriven = [
        environment.name
        for environment in build_environments.refused_environments(declared)
        if environment.name not in args.envs
    ]
    if undriven:
        print(
            "check_selection_refused: these environments declare they must be refused, which "
            "excuses them from the gates that cover every host build, but nothing here drives "
            "them to establish that they are",
            file=sys.stderr,
        )
        for name in undriven:
            print(f"  {name}", file=sys.stderr)
        return 1

    for environment in args.envs:
        # A stale artefact from an earlier run would make the "no artefact"
        # condition pass or fail for the wrong reason.
        for path in artefact_paths(project, environment):
            os.remove(path)

        result = subprocess.run(
            [args.pio, "run", "-e", environment],
            cwd=project,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            problems.append(f"{environment}: the build succeeded rather than refusing")

        remaining = artefact_paths(project, environment)
        if remaining:
            problems.append(
                f"{environment}: left an artefact behind ({', '.join(os.path.basename(p) for p in remaining)})"
            )

        combined = f"{result.stdout}\n{result.stderr}"
        if "check_structure_selection" not in combined:
            problems.append(
                f"{environment}: stopped for some reason other than structure selection"
            )

    if problems:
        print("check_selection_refused: a misconfigured build was not refused", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print(f"check_selection_refused: {len(args.envs)} misconfigured build(s) refused")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
