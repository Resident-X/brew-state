#!/usr/bin/env python3
"""Fail the build when a model consumer reaches a plant structure directly.

The seam only makes a structure replaceable if nothing goes around it. A
consumer that includes a structure's own header, or names a field of its state
or parameter record, has bound itself to those equations, and the next
structure is then a rewrite of that consumer rather than an implementation of
an interface.

That property is verified by analysis, and an analysis that depends on someone
remembering to look is not repeatable -- so this runs as part of the build and
fails it, reporting the offending file, line and symbol so the violation is
actionable.

The structures themselves are exempt by construction: defining those symbols is
exactly their job, and the shared parameter loader beside them reaches a
structure's table because that is what makes one parser serve every structure.
Everything else under the source root is a consumer and is inspected.

The subject is the source root rather than a list of consumer directories on
purpose. A list has to be extended when a subsystem is added, and the one that
is forgotten is inspected by nobody while looking exactly like one that passed.

Usage: check_plant_encapsulation.py <source-root> [...] --plant-root <dir> --include-dir <dir>
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check_encapsulation import collect_sources  # noqa: E402
from structure_symbols import discover, find_violations  # noqa: E402
from vendor_symbols import Violation  # noqa: E402


def consumer_sources(roots: list[str], plant_root: str) -> list[str]:
    """Every source under the roots that is not part of a structure."""
    exempt = os.path.realpath(plant_root) + os.sep
    return [
        path for path in collect_sources(roots) if not os.path.realpath(path).startswith(exempt)
    ]


def scan(sources: list[str], structures: list) -> list[Violation]:
    """Report every structure symbol reached from the given sources."""
    violations: list[Violation] = []
    for path in sources:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                source = handle.read()
        except (UnicodeDecodeError, OSError):
            # A file that cannot be read cannot be cleared either.
            violations.append(
                Violation(path, 1, os.path.basename(path), "file the check cannot read")
            )
            continue
        violations.extend(find_violations(path, source, structures))
    return violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", help="files or directories to check")
    parser.add_argument("--plant-root", required=True, help="the directory the structures live in")
    parser.add_argument(
        "--include-dir", required=True, help="the directory the seam's own headers live in"
    )
    args = parser.parse_args(argv)

    for root in args.roots:
        if not os.path.exists(root):
            print(f"check_plant_encapsulation: no such path: {root}", file=sys.stderr)
            return 2

    structures = discover(args.plant_root, args.include_dir)
    if not structures:
        print(
            f"check_plant_encapsulation: no structures under {args.plant_root} -- the check "
            "would pass without having anything to detect",
            file=sys.stderr,
        )
        return 2

    owned = sum(len(s.members) + len(s.declarations) for s in structures)
    if owned == 0:
        print(
            "check_plant_encapsulation: the structures own no names, so the check would "
            "pass without inspecting anything",
            file=sys.stderr,
        )
        return 2

    sources = consumer_sources(args.roots, args.plant_root)
    if not sources:
        print(
            "check_plant_encapsulation: no consumer sources found -- the check would pass "
            "without inspecting anything",
            file=sys.stderr,
        )
        return 2

    violations = scan(sources, structures)
    if violations:
        print(
            "check_plant_encapsulation: a model consumer reaches a structure directly",
            file=sys.stderr,
        )
        for violation in violations:
            print(f"  {violation}", file=sys.stderr)
        print(
            f"  {len(violations)} violation(s); reach the model through "
            "include/plant_model.h instead",
            file=sys.stderr,
        )
        return 1

    print(
        f"check_plant_encapsulation: {len(sources)} source(s) clean against {owned} name(s) "
        f"owned by {len(structures)} structure(s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
