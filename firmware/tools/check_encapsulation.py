#!/usr/bin/env python3
"""Fail the build when control logic reaches a vendor symbol directly.

The seam only encapsulates the target if nothing behind it names the target.
That property is verified by analysis, and an analysis that depends on someone
remembering to look is not repeatable -- so this runs as part of the build and
fails it, reporting the offending file, line and symbol so the violation is
actionable.

The implementations under src/hw are exempt by construction: naming vendor
symbols is exactly their job.

Usage: check_encapsulation.py <directory-or-file> [...]
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vendor_symbols import Violation, find_violations  # noqa: E402

SOURCE_SUFFIXES = (".c", ".h")


def collect_sources(roots: list[str]) -> list[str]:
    """Every C source and header under the given files or directories, sorted."""
    sources: list[str] = []
    for root in roots:
        if os.path.isfile(root):
            sources.append(root)
            continue
        for directory, _subdirs, files in os.walk(root):
            for name in sorted(files):
                if name.endswith(SOURCE_SUFFIXES):
                    sources.append(os.path.join(directory, name))
    return sorted(sources)


def scan(roots: list[str]) -> list[Violation]:
    """Report every vendor symbol reached from the given sources."""
    violations: list[Violation] = []
    for path in collect_sources(roots):
        with open(path, "r", encoding="utf-8") as handle:
            violations.extend(find_violations(path, handle.read()))
    return violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", help="files or directories to check")
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="succeed when the roots contain no source files",
    )
    args = parser.parse_args(argv)

    for root in args.roots:
        if not os.path.exists(root):
            print(f"check_encapsulation: no such path: {root}", file=sys.stderr)
            return 2

    sources = collect_sources(args.roots)
    if not sources and not args.allow_empty:
        print(
            "check_encapsulation: no C sources found -- the check would pass "
            "without inspecting anything",
            file=sys.stderr,
        )
        return 2

    violations = scan(args.roots)
    if violations:
        print("check_encapsulation: control logic reaches the vendor directly", file=sys.stderr)
        for violation in violations:
            print(f"  {violation}", file=sys.stderr)
        print(
            f"  {len(violations)} violation(s); reach hardware through "
            "include/hw_interface.h instead",
            file=sys.stderr,
        )
        return 1

    print(f"check_encapsulation: {len(sources)} source(s) clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
