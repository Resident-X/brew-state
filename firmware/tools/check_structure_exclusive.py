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

Which structures are covered is discovered rather than given. Every structure
in the source tree is covered, and the artefact carrying each one is found from
the build's own configuration -- so a structure added without a line being added
here cannot go unchecked, and a structure nobody builds an artefact for is
reported rather than passed over. Discovering nothing at all is a failure, on
the same terms: a gate covering an empty set reports success in exactly the way
a gate nobody ran does.

Usage: check_structure_exclusive.py --project <dir> --plant-root <dir> --include-dir <dir>
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_environments  # noqa: E402
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


def problems_in(
    executable: str,
    structure: str,
    exclusive: dict[str, frozenset[str]],
) -> list[str]:
    """Every way the artefact fails to carry exactly the structure it names."""
    present = defined_symbols(executable)
    problems: list[str] = []

    for symbol in sorted(exclusive[structure]):
        if symbol not in present:
            problems.append(
                f"{executable}: {symbol}: the '{structure}' structure the build names is not "
                "in the artefact"
            )

    for name in sorted(exclusive):
        if name == structure:
            continue
        for symbol in sorted(exclusive[name]):
            if symbol in present:
                problems.append(
                    f"{executable}: {symbol}: the '{name}' structure survived into the artefact"
                )

    return problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="the PlatformIO project directory")
    parser.add_argument("--plant-root", required=True, help="the directory the structures live in")
    parser.add_argument(
        "--include-dir", required=True, help="the directory the seam's own headers live in"
    )
    args = parser.parse_args(argv)

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

    try:
        declared = build_environments.load(args.project)
    except build_environments.ConfigurationError as error:
        print(f"check_structure_exclusive: {error}", file=sys.stderr)
        return 2

    # Every artefact carrying a structure, not the first one found for it: two
    # environments can build the same structure, and the second is as capable
    # of carrying another structure's symbols as the first.
    covered: dict[str, list[str]] = {}
    for environment in build_environments.artefact_environments(declared):
        structure = environment.structure(names)
        if structure is not None:
            covered.setdefault(structure, []).append(environment.artefact(args.project))

    # An empty subject set and a structure nobody builds are findings rather
    # than states this cannot look at: the artefacts are missing from what the
    # build *declares*, which is a hole in the coverage itself. A declared
    # artefact that has not been built yet is the other thing, and is below.
    if not covered:
        print(
            "check_structure_exclusive: no environment builds an artefact carrying a structure, "
            "so this gate has nothing to cover and would report success without checking anything",
            file=sys.stderr,
        )
        return 1

    uncovered = [name for name in names if name not in covered]
    if uncovered:
        print(
            "check_structure_exclusive: these structures are built by no environment, so "
            "nothing establishes what an artefact carrying them would carry",
            file=sys.stderr,
        )
        for name in uncovered:
            print(f"  {name}", file=sys.stderr)
        return 1

    missing = [path for paths in covered.values() for path in paths if not os.path.exists(path)]
    if missing:
        # A declared artefact that has not been built yet is a state this
        # cannot look at, unlike an artefact the build never declares.
        print("check_structure_exclusive: these artefacts have not been built", file=sys.stderr)
        for path in missing:
            print(f"  {path}", file=sys.stderr)
        return 2

    problems: list[str] = []
    for structure in names:
        for path in covered[structure]:
            problems.extend(problems_in(path, structure, exclusive))

    if problems:
        print(
            "check_structure_exclusive: an artefact does not carry exactly the structure it names",
            file=sys.stderr,
        )
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print(
        "check_structure_exclusive: "
        + "; ".join(
            f"{path} carries {len(exclusive[structure])} symbol(s) of '{structure}' and none "
            "of any other"
            for structure in names
            for path in covered[structure]
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
