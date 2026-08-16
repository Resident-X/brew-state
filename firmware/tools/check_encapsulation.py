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

#: Suffixes of files a build can turn into a control-logic translation unit.
#: This is deliberately wider than what the control logic uses today, because
#: the build filter takes a whole directory rather than a list of files.
SOURCE_SUFFIXES = (
    ".c", ".h",
    ".cc", ".cpp", ".cxx", ".c++",
    ".hh", ".hpp", ".hxx", ".h++",
    ".s", ".S", ".asm", ".inc", ".ipp", ".tpp", ".def",
)

#: Assembly translation units. Control logic written in assembly is reaching
#: the core or a peripheral directly whatever it names, so its presence is the
#: violation -- there is nothing above the seam for it to be doing.
ASSEMBLY_SUFFIXES = (".s", ".asm")

#: Suffixes a build never compiles, so a file carrying one is not inspected.
#: Everything else is, whatever its name -- a check that skips what it does not
#: recognise is a check that a new kind of source file walks straight past.
NON_SOURCE_SUFFIXES = (".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini", ".csv")


def is_source(name: str) -> bool:
    """Whether a file has to be inspected.

    A file is inspected unless its suffix is one a build never compiles. The
    rule is that way round on purpose: listing what to inspect means a source
    kind nobody thought of -- a C++ or assembly translation unit dropped into a
    directory the build filter takes wholesale -- is skipped in silence.
    """
    lowered = name.lower()
    if lowered.endswith(tuple(suffix.lower() for suffix in NON_SOURCE_SUFFIXES)):
        return False
    if name.startswith("."):
        return False
    return True


def collect_sources(roots: list[str]) -> list[str]:
    """Every file under the given files or directories that has to be inspected."""
    sources: list[str] = []
    for root in roots:
        if os.path.isfile(root):
            sources.append(root)
            continue
        for directory, _subdirs, files in os.walk(root):
            for name in sorted(files):
                if is_source(name):
                    sources.append(os.path.join(directory, name))
    return sorted(sources)


def scan(roots: list[str]) -> list[Violation]:
    """Report every vendor symbol reached from the given sources."""
    violations: list[Violation] = []
    for path in collect_sources(roots):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                source = handle.read()
        except (UnicodeDecodeError, OSError):
            # A file that cannot be read cannot be cleared either.
            violations.append(
                Violation(path, 1, os.path.basename(path), "file the check cannot read")
            )
            continue
        if path.lower().endswith(ASSEMBLY_SUFFIXES):
            violations.append(
                Violation(path, 1, os.path.basename(path), "assembly translation unit")
            )
        violations.extend(find_violations(path, source))
    return violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", help="files or directories to check")
    args = parser.parse_args(argv)

    for root in args.roots:
        if not os.path.exists(root):
            print(f"check_encapsulation: no such path: {root}", file=sys.stderr)
            return 2

    sources = collect_sources(args.roots)
    if not sources:
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
