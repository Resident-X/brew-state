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

Discovering none is a failure: running no environment reports success in
exactly the way running nothing does.

Usage: run_host_tests.py --project <dir> --pio <executable>
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_environments  # noqa: E402


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="the PlatformIO project directory")
    parser.add_argument(
        "--pio",
        default=os.environ.get("PIO", os.path.expanduser("~/.platformio/penv/bin/pio")),
        help="the PlatformIO executable",
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
