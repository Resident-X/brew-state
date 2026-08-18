#!/usr/bin/env python3
"""Fail when the artefact a machine would run does not carry the model.

Everything else about this is established before the artefact exists: which
structure the build selects, which description it renders, that the description
is the one the verification tier is pinned to. None of that survives contact
with the linker on its own. A linker discards what nothing reaches, and at this
point in the work nothing on the machine drives the model yet -- the estimator
and the control law that will are separate deliverables -- so the equations are
exactly what it would drop.

An artefact that dropped them looks like a success. The build passes, the
checks that ran before it passed, and the maths those equations call into stops
being needed, so a toolchain that could never have resolved it answers nothing
and appears to have answered. That is why this asks the artefact rather than
the build: the operations the seam declares are present in it, and the bytes it
carries are the description the tier verified and no other.

Which operations to look for is read out of the seam header through the same
module the build step that retains them reads, so the two cannot come to
disagree about what the model consists of.

Usage: check_target_carries_model.py --project <dir> --include-dir <dir>
                                     --params-dir <dir>
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_environments  # noqa: E402
import plant_seam_operations  # noqa: E402

#: Symbol listers to try, in order. The first that runs decides.
LISTERS = (["nm"], ["llvm-nm"])

#: What a parameter description is called.
DESCRIPTION_SUFFIX = ".params"


def defined_symbols(artefact: str) -> set[str]:
    """Every symbol the artefact defines, with any platform prefix removed."""
    for lister in LISTERS:
        try:
            result = subprocess.run(
                lister + [artefact], capture_output=True, text=True, check=False
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
            # `U` is undefined and `u`/`w` are its weak forms: a symbol the
            # artefact refers to and does not have. Reading one as defined would
            # report the model present in an artefact that is still waiting for
            # it.
            if len(kind) != 1 or kind in ("U", "u", "w"):
                continue
            names.add(name[1:] if name.startswith("_") else name)
        return names

    raise SystemExit(f"check_target_carries_model: no symbol lister could inspect {artefact}")


def descriptions_in(params_dir: str) -> list[str]:
    """Every parameter description in the tree, by path."""
    if not os.path.isdir(params_dir):
        return []
    return [
        os.path.join(params_dir, entry)
        for entry in sorted(os.listdir(params_dir))
        if entry.endswith(DESCRIPTION_SUFFIX)
    ]


def read_bytes(path: str) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


def check(project: str, include_dir: str, params_dir: str) -> tuple[list[str], list[str]]:
    """Every way an artefact for a machine fails to carry the model, and what was read."""
    declared = build_environments.load(project)
    environments = build_environments.machine_environments(declared)
    if not environments:
        return [
            "no environment builds an artefact for a machine, so this gate has nothing to "
            "cover and would report success having inspected nothing"
        ], []

    pinned, problems = build_environments.pinned_description(declared)
    if problems:
        return problems, []

    pinned_path = os.path.join(project, pinned)
    if not os.path.isfile(pinned_path):
        return [f"the verification tier is pinned to {pinned}, which is not there"], []
    verified = read_bytes(pinned_path)

    operations = plant_seam_operations.operations(include_dir)

    inspected: list[str] = []
    for environment in environments:
        artefact = environment.artefact(project)
        if not os.path.exists(artefact):
            problems.append(
                f"{environment.name}: no artefact at {artefact}. It has to be built before "
                "what it carries can be read"
            )
            continue
        inspected.append(artefact)

        defined = defined_symbols(artefact)
        missing = [name for name in operations if name not in defined]
        if missing:
            problems.append(
                f"{artefact}: does not define {', '.join(missing)}, so the machine would run "
                "an artefact the model was discarded from"
            )

        image = read_bytes(artefact)
        if not verified:
            problems.append(
                f"{pinned} is empty, so every artefact carries it and this would report on "
                "nothing"
            )
            continue
        if image.count(verified) != 1:
            problems.append(
                f"{artefact}: carries the {len(verified)} bytes of {pinned} "
                f"{image.count(verified)} time(s), not once"
            )
        for other in descriptions_in(os.path.join(project, params_dir)):
            if os.path.abspath(other) == os.path.abspath(pinned_path):
                continue
            # An empty description is in every image. Reading that as a second
            # description carried would fail the gate for a file with nothing in
            # it, naming the artefact rather than the empty file.
            other_bytes = read_bytes(other)
            if other_bytes and other_bytes in image:
                problems.append(
                    f"{artefact}: also carries {os.path.relpath(other, project)}, so which "
                    "description the machine is running on is settled by neither the build "
                    "nor anything readable off the machine"
                )

    return problems, inspected


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="the PlatformIO project directory")
    parser.add_argument("--include-dir", required=True, help="the directory the seam lives in")
    parser.add_argument(
        "--params-dir", default="params", help="the descriptions, relative to the project"
    )
    args = parser.parse_args(argv)

    try:
        problems, inspected = check(args.project, args.include_dir, args.params_dir)
    except build_environments.ConfigurationError as error:
        print(f"check_target_carries_model: {error}", file=sys.stderr)
        return 2
    except plant_seam_operations.NoSeamOperations as error:
        print(f"check_target_carries_model: {error}", file=sys.stderr)
        return 2

    if problems:
        print(
            "check_target_carries_model: an artefact a machine would run does not carry the "
            "model it was built to carry",
            file=sys.stderr,
        )
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print(
        f"check_target_carries_model: {', '.join(inspected)} define every operation the plant "
        "seam declares and carry the pinned description once and no other"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
