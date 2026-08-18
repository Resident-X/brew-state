#!/usr/bin/env python3
"""Fail when the plant's coefficients turn out to be code rather than data.

Adopting a machine of the same architecture is meant to be measurement work
rather than development work, and that is only true while changing a
coefficient does not mean changing the software. A coefficient quietly written
into the equations reads exactly like one loaded from a description -- right up
to the point where an adopter changes the description and nothing happens.

So this runs one linked artefact twice against two descriptions that differ in
a single coefficient and requires two different trajectories. It hashes the
executable either side of the pair as well: two runs producing different output
prove nothing if the artefact was rebuilt between them.

The limits declaration is held fixed across the pair and named once. What is
being established is that a coefficient is read rather than compiled in, so the
descriptions are what vary; varying anything else alongside them would leave
two runs differing for a reason this check could not attribute.

Usage: check_parameters_are_data.py <executable> --params <a> --params <b>
                                    --limits <declaration>
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys


def digest(path: str) -> str:
    """The content hash of the artefact, so a rebuild between runs is visible."""
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            hasher.update(block)
    return hasher.hexdigest()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", help="the linked executable to run")
    parser.add_argument(
        "--params",
        action="append",
        required=True,
        dest="descriptions",
        help="a parameter description to run against",
    )
    parser.add_argument(
        "--limits",
        required=True,
        help="the limits declaration to hold fixed across both runs",
    )
    args = parser.parse_args(argv)

    if not os.path.exists(args.executable):
        print(f"check_parameters_are_data: no such executable: {args.executable}", file=sys.stderr)
        return 2
    if len(args.descriptions) < 2:
        print(
            "check_parameters_are_data: two descriptions are needed -- one run cannot show "
            "that a coefficient is read rather than compiled in",
            file=sys.stderr,
        )
        return 2

    for path in args.descriptions:
        if not os.path.isfile(path):
            print(f"check_parameters_are_data: no such description: {path}", file=sys.stderr)
            return 2
    if not os.path.isfile(args.limits):
        print(
            f"check_parameters_are_data: no such limits declaration: {args.limits}",
            file=sys.stderr,
        )
        return 2

    before = digest(args.executable)
    outputs: list[tuple[str, str]] = []
    problems: list[str] = []

    for path in args.descriptions:
        result = subprocess.run(
            [os.path.abspath(args.executable), path, args.limits],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            problems.append(
                f"{path}: the run failed ({result.returncode}); "
                f"{result.stderr.strip() or 'no diagnostics'}"
            )
        outputs.append((path, result.stdout))

    after = digest(args.executable)
    if before != after:
        problems.append("the executable changed between the runs, so nothing is established")

    distinct = {output for _, output in outputs}
    if len(distinct) != len(outputs):
        problems.append(
            "two descriptions produced the same trajectory, so at least one coefficient "
            "is not being read from the description"
        )

    if problems:
        print("check_parameters_are_data: the plant's coefficients are not data", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print(
        f"check_parameters_are_data: {len(outputs)} description(s) gave {len(distinct)} distinct "
        f"trajectories from one unchanged artefact"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
