#!/usr/bin/env python3
"""Fail when an environment compiles the control logic without the estimator.

The control logic drives from a reconstructed state, so it references the
estimator seam. An environment that compiles one without the other does not
link -- but it does not fail until something asks it to build, and the
environment most likely to be forgotten is the one nobody builds by hand. The
target build is exactly that: a host environment is exercised on every run of
the tests, and the one for the board is not.

Which environments are subject is discovered from the build file rather than
listed here, on the same terms every other gate discovers its subjects. A list
has to be extended when an environment is added, and the one that is forgotten
is inspected by nobody while looking exactly like one that passed.

Environments the build declares must not build -- the deliberately
misconfigured ones -- are exempt: they are required to be refused, and requiring
them to be well-formed first would be requiring two contradictory things of the
same declaration.

Usage: check_estimator_compiled.py --project <dir>
       [--control-dir control] [--estimator-dir estimator]
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_environments  # noqa: E402
import filter_terms  # noqa: E402


def compiles(environment: build_environments.Environment, directory: str) -> bool:
    """Whether this environment's source filter ends up including `directory`.

    The filter is walked in order rather than searched for a prefix, because a
    term taking a directory wholesale includes what is under it and a later term
    can take it back out again. Reading only the additions would report a
    directory compiled that the build drops.
    """
    included = False
    for sign, normalised in filter_terms.terms(environment.source_filter):
        if filter_terms.covers(normalised, directory):
            included = sign == "+"
    return included


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="the directory the build file lives in")
    parser.add_argument("--control-dir", default="control", help="under the source root")
    parser.add_argument("--estimator-dir", default="estimator", help="under the source root")
    args = parser.parse_args(argv)

    try:
        environments = build_environments.load(args.project)
    except build_environments.ConfigurationError as fault:
        print(f"check_estimator_compiled: {fault}", file=sys.stderr)
        return 2

    refused = {
        environment.name
        for environment in build_environments.refused_environments(environments)
    }
    subjects = [
        environment
        for environment in environments
        if environment.name not in refused and compiles(environment, args.control_dir)
    ]

    if not subjects:
        print(
            "check_estimator_compiled: no environment compiles the control logic, so the "
            "check would pass without inspecting anything",
            file=sys.stderr,
        )
        return 2

    missing = [
        environment.name
        for environment in subjects
        if not compiles(environment, args.estimator_dir)
    ]
    if missing:
        print(
            "check_estimator_compiled: these environments compile the control logic without "
            "the estimator it drives from, so they cannot link",
            file=sys.stderr,
        )
        for name in missing:
            print(f"  {name}", file=sys.stderr)
        print("  add the estimator sources to each environment's build_src_filter", file=sys.stderr)
        return 1

    print(
        f"check_estimator_compiled: {len(subjects)} environment(s) compiling the control logic "
        "compile the estimator beside it"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
