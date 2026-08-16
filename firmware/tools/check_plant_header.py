#!/usr/bin/env python3
"""Fail when the plant-model seam's header is not structure-neutral.

The header is the whole point of the seam: if it names a structure, or a
quantity only one structure has, then every translation unit that includes it
depends on those equations, and a second structure stops being something you
implement and becomes something you negotiate with everything that consumes the
model.

Five things are checked, because each can pass while another is broken:

  * no structure's directory name appears in the header, and no include reaches
    into a structure's directory,
  * the header names no symbol a structure owns and reaches into no structure's
    record -- the state and parameter types a structure supplies are the one
    sanctioned crossing, and a field of either is not,
  * the header carries no function definition, so no equation can be hiding in
    it -- an interface declares operations and holds no arithmetic,
  * no vendor symbol appears in it, on the same reasoning as the hardware
    seam's header, and
  * it compiles on its own against a freestanding compiler with *each*
    structure's directory standing in for the one the build selects, in turn.

The last of those carries most of the weight. A header that quietly names a
field only the thermoblock structure has still compiles against the thermoblock
structure; it is compiling against every structure that makes neutrality
something the toolchain establishes rather than something a reader asserts.

Usage: check_plant_header.py <header> --plant-root <dir> [--cc clang]
"""

from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from freestanding import compiles_freestanding  # noqa: E402
import structure_symbols  # noqa: E402
from structure_symbols import STRUCTURE_HEADER, discover, supplied_types  # noqa: E402
from vendor_symbols import find_violations, strip_comments_and_strings  # noqa: E402

_FUNCTION_DEFINITION = re.compile(r"\)\s*\{")
_DECLARATION = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\([^;{]*\)\s*;", re.DOTALL)
_INCLUDE = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]', re.MULTILINE)


def structure_references(source: str, names: list[str]) -> list[str]:
    """Every place the header names a structure directory or reaches into one."""
    cleaned = strip_comments_and_strings(source)
    problems: list[str] = []

    for lineno, line in enumerate(cleaned.splitlines(), start=1):
        for name in names:
            if re.search(rf"\b{re.escape(name)}\b", line):
                problems.append(f"line {lineno}: names the '{name}' structure")

    for match in _INCLUDE.finditer(source):
        included = match.group(1).replace("\\", "/")
        parts = included.split("/")
        lineno = source[: match.start()].count("\n") + 1
        if len(parts) > 1 and any(part in names for part in parts[:-1]):
            problems.append(f"line {lineno}: includes '{included}' from inside a structure")

    return problems


def structure_symbol_references(header: str, source: str, plant_root: str, include_dir: str):
    """Every structure symbol the seam header names.

    The vocabulary is rebuilt with this header left out of what counts as
    neutral, so a name the header itself introduces cannot clear itself, and
    with each structure's supplied types removed, since naming those is what
    the seam is for. The header's own include of the structure header is
    blanked before scanning for the same reason -- it is the seam reaching its
    types, not a consumer reaching around itself.
    """
    strict: list = []
    for structure in discover(plant_root, include_dir, (os.path.basename(header),)):
        with open(structure.header, "r", encoding="utf-8") as handle:
            sanctioned = supplied_types(handle.read())
        strict.append(
            structure_symbols.Structure(
                name=structure.name,
                directory=structure.directory,
                header=structure.header,
                members=structure.members - sanctioned,
                declarations=structure.declarations - sanctioned,
            )
        )

    scanned = "\n".join(
        "" if re.match(rf'^\s*#\s*include\s*"{re.escape(STRUCTURE_HEADER)}"', line) else line
        for line in source.splitlines()
    )
    return structure_symbols.find_violations(header, scanned, strict)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("header", help="the seam header to check")
    parser.add_argument("--plant-root", required=True, help="the directory the structures live in")
    parser.add_argument(
        "--include-dir",
        default=None,
        help="the directory the seam's own headers live in (defaults to the header's own)",
    )
    parser.add_argument("--cc", default=os.environ.get("CC", "clang"), help="C compiler to use")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.header):
        print(f"check_plant_header: no such header: {args.header}", file=sys.stderr)
        return 2

    include_dir = args.include_dir or os.path.dirname(os.path.abspath(args.header))
    structures = discover(args.plant_root, include_dir)
    if len(structures) < 2:
        # Compiling against one structure cannot distinguish a neutral header
        # from one written for that structure, so a tree with fewer than two is
        # a tree this check cannot establish anything on.
        print(
            f"check_plant_header: {len(structures)} structure(s) under {args.plant_root} -- "
            "neutrality cannot be established against fewer than two",
            file=sys.stderr,
        )
        return 2

    with open(args.header, "r", encoding="utf-8") as handle:
        source = handle.read()

    failed = False

    problems = structure_references(source, [structure.name for structure in structures])
    if problems:
        failed = True
        print("check_plant_header: the seam header names a structure", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)

    reached = structure_symbol_references(args.header, source, args.plant_root, include_dir)
    if reached:
        failed = True
        print("check_plant_header: the seam header reaches into a structure", file=sys.stderr)
        for violation in reached:
            print(f"  {violation}", file=sys.stderr)

    cleaned = strip_comments_and_strings(source)
    definitions = [
        cleaned[: match.start()].count("\n") + 1 for match in _FUNCTION_DEFINITION.finditer(cleaned)
    ]
    if definitions:
        failed = True
        print(
            "check_plant_header: the seam header carries a function definition, so an "
            "equation can live in it",
            file=sys.stderr,
        )
        for lineno in definitions:
            print(f"  line {lineno}", file=sys.stderr)

    declared = sorted(set(_DECLARATION.findall(cleaned)))
    if not declared:
        failed = True
        print(
            "check_plant_header: the seam header declares no operation, so there is no "
            "seam to be neutral about",
            file=sys.stderr,
        )

    violations = find_violations(args.header, source)
    if violations:
        failed = True
        print("check_plant_header: the seam header names the vendor", file=sys.stderr)
        for violation in violations:
            print(f"  {violation}", file=sys.stderr)

    for structure in structures:
        ok, diagnostics = compiles_freestanding(args.header, args.cc, [structure.directory])
        if not ok:
            failed = True
            print(
                f"check_plant_header: the seam header does not compile standalone against "
                f"the '{structure.name}' structure",
                file=sys.stderr,
            )
            for line in diagnostics.splitlines():
                print(f"  {line}", file=sys.stderr)

    if failed:
        return 1

    print(
        f"check_plant_header: {args.header} declares {len(declared)} operation(s), names no "
        f"structure and compiles against all {len(structures)} of them "
        f"({', '.join(structure.name for structure in structures)})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
