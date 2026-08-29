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
carries are the files the tier verified and no others.

There is more than one such file, and each is asked the same question by the
same code. The description says what the machine is, the limits declaration says
what a reading off it may plausibly be, and the tolerance declaration says how
far from the temperature it was asked for a delivery may sit. A gate written to
ask about the first alone would leave the ones that arrived after it uncovered,
and an artefact missing either of those is silent in the same way: bounds nobody
supplied leave the estimator correcting toward a state the machine cannot be in,
and a band nobody supplied leaves every cup inside a tolerance that does not
exist.

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
from collections.abc import Callable
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_environments  # noqa: E402
import plant_seam_operations  # noqa: E402

#: Symbol listers to try, in order. The first that runs decides.
LISTERS = (["nm"], ["llvm-nm"])

#: What a parameter description is called.
DESCRIPTION_SUFFIX = ".params"

#: What a limits declaration is called.
LIMITS_SUFFIX = ".limits"

#: What the declarations that are not about a machine are called. The tolerance
#: declaration is one of several files under this suffix, and that is the point
#: of searching by it rather than a reason not to -- see TOLERANCE below.
DECLARATION_SUFFIX = ".declaration"


class Carried(NamedTuple):
    """One file an artefact has to be carrying, and how to find a rival to it."""

    #: What the file is, in words, for a message a reader has to act on.
    what: str
    #: What the verification tier is pinned to, read off the whole build.
    pinned_by: Callable[
        [list[build_environments.Environment]], tuple[str, list[str]]
    ]
    #: The suffix the tree writes files of this kind with, so a second one being
    #: carried can be found.
    siblings: str


#: Everything the artefact is asked about, in the order it is reported on.
#:
#: The tolerance declaration and the pump trim declaration are both searched
#: against the whole of the shared `.declaration` suffix, and the files they
#: share it with are the reason rather than an obstacle. The tree holds
#: exactly one statement of what a delivery is held to and exactly one
#: statement of how hard the trim corrects a rate gap, so a second file under
#: this suffix turning up inside an artefact is one of two things, and both
#: are findings. Either a rival declaration has been embedded beside the
#: pinned one, in which case which band -- or which gains -- the machine is
#: running on is settled by neither the build nor anything readable off the
#: machine, and the pinned one would go on reading as authoritative. Or one of
#: the declarations that is not meant to be embedded at all has reached the
#: image: nothing in the tree puts the cadence, control or robustness
#: declaration into an artefact, so an artefact carrying one is a build that
#: has started embedding files nobody decided to embed, which is exactly the
#: sort of thing a reader wants told to them while it is still one file rather
#: than a habit.
#:
#: The two share the suffix and are still asked about separately, on the same
#: terms every other pair here is: each answers a different question about
#: the machine, and collapsing them into one entry would report a divergence
#: in either as though it were the same finding.
CARRIED = (
    Carried("description", build_environments.pinned_description, DESCRIPTION_SUFFIX),
    Carried("limits declaration", build_environments.pinned_limits, LIMITS_SUFFIX),
    Carried("tolerance declaration", build_environments.pinned_tolerance, DECLARATION_SUFFIX),
    Carried("pump trim declaration", build_environments.pinned_pump_trim, DECLARATION_SUFFIX),
)


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


def files_in(params_dir: str, suffix: str) -> list[str]:
    """Every file of one kind in the tree, by path.

    An empty suffix answers nothing rather than everything, so that a kind with
    no rival to look for cannot be turned into a search matching every file in
    the directory -- which is how a check acquires findings about files nobody
    claimed the artefact was carrying.
    """
    if not suffix or not os.path.isdir(params_dir):
        return []
    return [
        os.path.join(params_dir, entry)
        for entry in sorted(os.listdir(params_dir))
        if entry.endswith(suffix)
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

    # What the tier is pinned to, for every file an artefact carries, before any
    # artefact is asked about. All of them are resolved before any is read, so a
    # tree that has forgotten two of them says so once rather than a run at a
    # time.
    problems: list[str] = []
    resolved: list[tuple[Carried, str, bytes]] = []
    for carried in CARRIED:
        pinned, pin_problems = carried.pinned_by(declared)
        if pin_problems:
            problems.extend(pin_problems)
            continue

        pinned_path = os.path.join(project, pinned)
        if not os.path.isfile(pinned_path):
            problems.append(
                f"the verification tier is pinned to the {carried.what} {pinned}, which is "
                "not there"
            )
            continue

        verified = read_bytes(pinned_path)
        if not verified:
            # Every image contains an empty run of bytes, so a file with nothing
            # in it would be found in each of them and the gate would report on
            # nothing while appearing to have looked.
            problems.append(
                f"the {carried.what} {pinned} is empty, so every artefact carries it and this "
                "would report on nothing"
            )
            continue

        resolved.append((carried, pinned, verified))
    if problems:
        return problems, []

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

        # Every path this artefact is legitimately pinned to carry, across every
        # `Carried` entry -- not only the one presently being asked about. Two
        # entries sharing a sibling suffix (the tolerance and pump trim
        # declarations both search the whole of `.declaration`) would otherwise
        # have each read the other's own pinned file as a rival beside it,
        # which is a divergence from nothing: both are meant to be in the
        # image, under their own names, and neither is a second answer to the
        # other's question.
        every_pinned_path = {os.path.abspath(os.path.join(project, p)) for _, p, _ in resolved}

        image = read_bytes(artefact)
        for carried, pinned, verified in resolved:
            if image.count(verified) != 1:
                problems.append(
                    f"{artefact}: carries the {len(verified)} bytes of the {carried.what} "
                    f"{pinned} {image.count(verified)} time(s), not once"
                )
            for other in files_in(os.path.join(project, params_dir), carried.siblings):
                if os.path.abspath(other) in every_pinned_path:
                    continue
                # An empty file is in every image. Reading that as a second one
                # carried would fail the gate for a file with nothing in it,
                # naming the artefact rather than the empty file.
                other_bytes = read_bytes(other)
                if other_bytes and other_bytes in image:
                    problems.append(
                        f"{artefact}: also carries {os.path.relpath(other, project)}, so which "
                        f"{carried.what} the machine is running on is settled by neither the "
                        "build nor anything readable off the machine"
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
        f"seam declares and carry the pinned {', '.join(entry.what for entry in CARRIED)} once "
        "each and no others"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
