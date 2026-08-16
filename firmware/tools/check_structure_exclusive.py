#!/usr/bin/env python3
"""Fail when a linked artefact carries a plant structure it was not built for.

Selecting the structure when the artefact is built is what makes controlling a
machine with another architecture's dynamics unreachable rather than merely
unlikely. Reading the build configuration is not enough to establish it: a
filter can name one structure while the linker pulls in another's object, and
the symptom of running the wrong equations is a machine that is well outside
where it should be long before anything looks wrong.

So this inspects the artefact. It requires that every symbol unique to the
structure the build names is present in the executable, and that no symbol
unique to any other structure in the source tree is.

Only symbols *unique* to a structure can witness this. The operations every
structure implements are named identically by all of them -- that is what makes
them an interface -- so they cannot tell two artefacts apart. A structure with
no unique symbol is therefore a structure this check cannot see, and is
reported as a failure rather than passed over: that is the state in which the
check would pass unconditionally.

Usage: check_structure_exclusive.py <executable> --structure <name>
                                    --plant-root <dir> --include-dir <dir>
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structure_symbols import discover, exclusive_declarations  # noqa: E402

#: Symbol listers to try, in order. The first that runs decides.
LISTERS = (["nm"], ["llvm-nm"])


def defined_symbols(executable: str) -> set[str]:
    """Every symbol the executable defines, with any platform prefix removed.

    Mach-O prefixes C symbols with an underscore and ELF does not, so one
    leading underscore is stripped to give both hosts the same names.
    """
    for lister in LISTERS:
        try:
            result = subprocess.run(
                lister + [executable], capture_output=True, text=True, check=False
            )
        except FileNotFoundError:
            continue
        if result.returncode != 0:
            continue

        names: set[str] = set()
        for line in result.stdout.splitlines():
            fields = line.split()
            if len(fields) < 2:
                continue
            kind, name = fields[-2], fields[-1]
            if len(kind) != 1 or kind in ("U", "u"):
                continue
            names.add(name[1:] if name.startswith("_") else name)
        return names

    raise SystemExit(
        f"check_structure_exclusive: no symbol lister on this host could inspect {executable}"
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", help="the linked executable to inspect")
    parser.add_argument("--structure", required=True, help="the structure the build names")
    parser.add_argument("--plant-root", required=True, help="the directory the structures live in")
    parser.add_argument(
        "--include-dir", required=True, help="the directory the seam's own headers live in"
    )
    args = parser.parse_args(argv)

    if not os.path.exists(args.executable):
        print(f"check_structure_exclusive: no such executable: {args.executable}", file=sys.stderr)
        return 2

    structures = discover(args.plant_root, args.include_dir)
    if len(structures) < 2:
        print(
            f"check_structure_exclusive: {len(structures)} structure(s) under {args.plant_root} "
            "-- with fewer than two there is nothing to exclude and the check would pass "
            "unconditionally",
            file=sys.stderr,
        )
        return 2

    names = [structure.name for structure in structures]
    if args.structure not in names:
        print(
            f"check_structure_exclusive: '{args.structure}' is not one of the structures "
            f"({', '.join(names)})",
            file=sys.stderr,
        )
        return 2

    exclusive = exclusive_declarations(structures)
    blind = sorted(name for name, symbols in exclusive.items() if not symbols)
    if blind:
        print(
            "check_structure_exclusive: these structures declare no symbol unique to them, "
            "so their presence in an artefact cannot be detected",
            file=sys.stderr,
        )
        for name in blind:
            print(f"  {name}", file=sys.stderr)
        return 2

    present = defined_symbols(args.executable)
    problems: list[str] = []

    for symbol in sorted(exclusive[args.structure]):
        if symbol not in present:
            problems.append(
                f"{symbol}: the '{args.structure}' structure the build names is not in the artefact"
            )

    for name in names:
        if name == args.structure:
            continue
        for symbol in sorted(exclusive[name]):
            if symbol in present:
                problems.append(f"{symbol}: the '{name}' structure survived into the artefact")

    if problems:
        print(
            f"check_structure_exclusive: {args.executable} does not carry exactly the "
            f"'{args.structure}' structure",
            file=sys.stderr,
        )
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    others = [name for name in names if name != args.structure]
    print(
        f"check_structure_exclusive: {args.executable} carries "
        f"{len(exclusive[args.structure])} symbol(s) of '{args.structure}' and none of "
        f"{', '.join(others)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
