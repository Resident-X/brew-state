#!/usr/bin/env python3
"""Run the tests in every environment the build declares them for.

A forgotten test environment is the quietest failure in the tree. A forgotten
build leaves a missing artefact, and the gates that inspect artefacts stop on
it; tests that were never run leave nothing behind at all -- no output, no
warning, and a green build that establishes nothing about the structure whose
tests they were.

So the environments are discovered rather than named. An environment declaring
that this project's sources are compiled into the test runner alongside the
tests is one the runner can be pointed at, and every one of them is run. A
structure shipping tests brings its own such environment, and the tests run
because they exist.

Which structures those environments have to cover is discovered the same way.
Every structure in the source tree is required to have an environment running
tests against it, on the same terms the exclusivity gate requires one to have an
artefact: a structure nothing runs tests against is a structure the host tier
establishes nothing about, and with more than one test environment in the tree,
one of them silently ceasing to run is invisible in a count.

Discovering none is a failure: running no environment reports success in
exactly the way running nothing does.

Usage: run_host_tests.py --project <dir> --pio <executable> --plant-root <dir>
                         --include-dir <dir>
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_environments  # noqa: E402
from structure_symbols import discover  # noqa: E402


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="the PlatformIO project directory")
    parser.add_argument(
        "--pio",
        default=os.environ.get("PIO", os.path.expanduser("~/.platformio/penv/bin/pio")),
        help="the PlatformIO executable",
    )
    parser.add_argument(
        "--plant-root", required=True, help="the directory the structures sit in"
    )
    parser.add_argument(
        "--include-dir", required=True, help="the directory the seam's headers sit in"
    )
    args = parser.parse_args(argv)

    try:
        declared = build_environments.load(args.project)
    except build_environments.ConfigurationError as error:
        print(f"run_host_tests: {error}", file=sys.stderr)
        return 2

    environments = build_environments.test_environments(declared)
    if not environments:
        print(
            "run_host_tests: no environment in "
            f"{build_environments.PROJECT_CONFIG} compiles this project's sources into the "
            "test runner, so no test would run and this task would report success having "
            "run nothing",
            file=sys.stderr,
        )
        return 1

    structures = discover(args.plant_root, args.include_dir)
    if not structures:
        print(
            f"run_host_tests: no structures under {args.plant_root} -- there is nothing for a "
            "test environment to have been running tests against",
            file=sys.stderr,
        )
        return 1

    available = [structure.name for structure in structures]
    covered = {
        environment.structure(available)
        for environment in environments
        if environment.structure(available) is not None
    }
    uncovered = sorted(set(available) - covered)
    if uncovered:
        print(
            "run_host_tests: no environment runs tests against "
            f"{', '.join(uncovered)} -- a structure nothing is run against is one the host "
            "tier establishes nothing about, and a count of environments would not show it",
            file=sys.stderr,
        )
        return 1

    for environment in environments:
        print(f"run_host_tests: {environment.name}", flush=True)
        result = subprocess.run(
            [args.pio, "test", "-e", environment.name], cwd=args.project, check=False
        )
        if result.returncode != 0:
            print(
                f"run_host_tests: the tests in '{environment.name}' exited "
                f"{result.returncode}",
                file=sys.stderr,
            )
            return 1

    print(
        "run_host_tests: the tests ran in "
        f"{', '.join(environment.name for environment in environments)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
