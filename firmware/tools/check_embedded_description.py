#!/usr/bin/env python3
"""Fail when a machine would be built carrying bytes nobody verified.

An artefact carries four files compiled in: the description of what the machine
is, the declaration of what a reading off that machine may plausibly be, the
band a delivery off it is held to, and the gains the pump trim corrects a rate
gap with. Each is one of the things about the machine's behaviour that cannot
be read back off it once it is running. Generating them from the files removes
the obvious way for them to go stale, but it does not establish that the
artefact and the host verification tier are pinned to the same files. A build
naming a different description, a generated file left behind by an incremental
build, and a second description sitting alongside the intended one each produce
a target carrying something the tier never saw.

None of those has a symptom. A machine predicting from coefficients that
describe a different variant is wrong in exactly the way a machine that has
drifted is wrong, and the residual that would eventually surface it cannot tell
the two apart. A machine believing readings a different machine's sensors could
produce is wrong the same way and just as quietly. A machine holding its
deliveries to a band nobody verified is quieter still: it makes coffee, and the
only evidence is in the cup. A machine trimming its pump with gains nobody
verified is the same failure again: it corrects toward the commanded rate, and
whether it does so the way the tier's own tests exercised is not something the
cup can tell either. So this is a build failure and not a warning, and it runs
before anything is compiled rather than against the artefact afterwards: an
artefact that should not exist is not made better by being inspected.

Every embedding is asked the same questions by the same code, and every message
names which one it is about. Written as separate checks they would answer
differently: the description would keep its refusals and the files that arrived
later would quietly acquire fewer.

What the tier is pinned to is read through the module that reads the build, and
what the artefact carries is read through the module that wrote it. This check
owns neither format.

Usage: check_embedded_description.py --project <dir> [--generated ENV=DIR]

`DIR` is the environment's generated directory -- the directory the build
renders into -- and not one file in it. Each embedding is then found under its
own name, which is the module that owns the format's answer rather than a
caller's, so a third file arriving later is compared without this invocation
changing.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_environments  # noqa: E402
import embedded_description  # noqa: E402


class Subject(NamedTuple):
    """One embedding, with the three things about it that live in the build file.

    The embedding itself says what is rendered and under what name. What it is
    called in an environment's declaration, how that declaration is read, and
    which macro pins the tier to it are all facts about the build rather than
    about the format, so they are joined to it here rather than restated at each
    of the questions below.
    """

    #: What the artefact carries, and the name the build renders it under.
    embedding: embedded_description.Embedding
    #: What an environment declaring it calls the option.
    option: str
    #: What that environment declares, read off it.
    declared: Callable[[build_environments.Environment], str]
    #: What the verification tier is pinned to, read off the whole build.
    pinned_by: Callable[[list[build_environments.Environment]], tuple[str, list[str]]]


#: Everything an artefact carries compiled in, in the order it is reported on.
SUBJECTS = (
    Subject(
        embedded_description.DESCRIPTION,
        build_environments.EMBEDDED_DESCRIPTION_OPTION,
        lambda environment: environment.embedded_description,
        build_environments.pinned_description,
    ),
    Subject(
        embedded_description.LIMITS,
        build_environments.EMBEDDED_LIMITS_OPTION,
        lambda environment: environment.embedded_limits,
        build_environments.pinned_limits,
    ),
    Subject(
        embedded_description.TOLERANCE,
        build_environments.EMBEDDED_TOLERANCE_OPTION,
        lambda environment: environment.embedded_tolerance,
        build_environments.pinned_tolerance,
    ),
    Subject(
        embedded_description.PUMP_TRIM,
        build_environments.EMBEDDED_PUMP_TRIM_OPTION,
        lambda environment: environment.embedded_pump_trim,
        build_environments.pinned_pump_trim,
    ),
)


def read_bytes(path: str) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


def rendered_directory(project: str, environment: build_environments.Environment) -> str:
    """Where this environment's build puts everything it renders.

    Derived rather than given, so a second board is compared without a caller
    naming its build directory, and through the module that owns the format, so
    this looks where the build wrote rather than where a second path agrees.
    """
    return os.path.join(
        environment.build_directory(project),
        embedded_description.GENERATED_DIRECTORY,
    )


def rendered_path(directory: str, embedding: embedded_description.Embedding) -> str:
    """One embedding's rendered file inside a generated directory.

    The name comes from the embedding rather than from the caller, which is what
    lets a run be handed a directory and still be looking at the same file the
    build wrote into it.
    """
    return os.path.join(directory, embedding.generated_name)


def check(project: str, generated: dict[str, str]) -> tuple[list[str], list[str]]:
    """Every way a machine build's embeddings diverge from what the tier is pinned to.

    `generated` maps an environment name to the generated directory to read for
    it.

    Which files each machine build declares is asked of every one of them,
    because that is answerable from the build file alone. The bytes are compared
    only for the environments a generated directory is offered for, because they
    are rendered by the build and only exist for the build that ran. This runs
    inside each machine build and is offered that build's own directory, so every
    artefact's bytes are compared as it is made -- and an environment offered
    here that does not build for a machine is refused rather than inspected,
    since it would be an answer about something that is not an artefact.
    """
    declared = build_environments.load(project)

    # What the tier is pinned to, for each thing an artefact carries, before any
    # artefact is asked about. All of them are resolved before any is compared: a
    # run that stopped at the first unresolved pin would report one omission and
    # leave the reader to discover the rest one run at a time.
    problems: list[str] = []
    pins: list[tuple[Subject, str]] = []
    for subject in SUBJECTS:
        path, pin_problems = subject.pinned_by(declared)
        if pin_problems:
            problems.extend(pin_problems)
            continue
        pins.append((subject, path))
    if problems:
        return problems, []

    resolved: list[tuple[Subject, str, bytes]] = []
    for subject, path in pins:
        pinned_path = os.path.join(project, path)
        if not os.path.isfile(pinned_path):
            problems.append(
                f"the verification tier is pinned to the {subject.embedding.description} "
                f"{path}, which is not there, so there is nothing for an artefact to be "
                "compared against"
            )
            continue
        resolved.append((subject, path, read_bytes(pinned_path)))
    if problems:
        return problems, []

    environments = build_environments.machine_environments(declared)
    if not environments:
        return [
            "no environment builds for a machine, so this gate has nothing to cover and "
            "would report success having compared nothing"
        ], []

    if not generated:
        # Nothing named, so every machine build is the subject and each is read
        # from where its own build put it. This is the run outside the build,
        # where the artefacts already exist and a board nobody named would
        # otherwise go uncompared.
        generated = {
            environment.name: rendered_directory(project, environment)
            for environment in environments
        }

    source_root = os.path.abspath(os.path.join(project, "src"))

    known = {environment.name for environment in environments}
    for name in sorted(set(generated) - known):
        problems.append(
            f"{name}: a generated embedding was offered for it, but it does not build an "
            "artefact for a machine, so there is nothing for those bytes to be carried by"
        )

    inspected: list[str] = []
    for environment in environments:
        directory = generated.get(environment.name)
        for subject, expected, verified in resolved:
            what = subject.embedding.description

            declared_file = subject.declared(environment)
            if not declared_file:
                problems.append(
                    f"{environment.name}: builds for a machine and declares no "
                    f"{subject.option}, so which {what} its artefact carries is not stated "
                    "anywhere"
                )
                continue
            if declared_file != expected:
                problems.append(
                    f"{environment.name}: declares it embeds the {what} {declared_file}, but "
                    f"the verification tier is pinned to {expected}, so the machine would "
                    f"carry a {what} the tier never verified"
                )
                continue

            if directory is None:
                # Not this run's subject. Its declaration has been checked above,
                # and its bytes are compared by its own build, which is the only
                # run that renders them.
                continue

            path = rendered_path(directory, subject.embedding)
            if os.path.abspath(path).startswith(source_root):
                problems.append(
                    f"{environment.name}: {path} is inside the source tree. The rendered "
                    f"{what} belongs under the build directory; a copy kept in the tree is "
                    "the second one this compares against one"
                )
                continue
            if not os.path.isfile(path):
                problems.append(
                    f"{environment.name}: no generated embedding of the {what} at {path}"
                )
                continue

            try:
                source, carried = embedded_description.decode(
                    read_bytes(path).decode("utf-8"), subject.embedding
                )
            except (embedded_description.MalformedEmbedding, UnicodeDecodeError) as error:
                problems.append(f"{environment.name}: {what}: {path}: {error}")
                continue

            inspected.append(f"{environment.name}'s {what}")
            if source != expected:
                problems.append(
                    f"{environment.name}: {path} was generated from {source}, not from the "
                    f"pinned {what} {expected}"
                )
            if carried != verified:
                problems.append(
                    f"{environment.name}: the {len(carried)} bytes of {what} it would embed "
                    f"are not the {len(verified)} bytes of {expected}, so the artefact and "
                    "the tier disagree about what the machine is"
                )

    return problems, inspected


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="the PlatformIO project directory")
    parser.add_argument(
        "--generated",
        action="append",
        default=[],
        metavar="ENV=DIR",
        help="the generated directory to read every embedding for one environment out of; "
             "without any, every machine build is read from where its own build put it",
    )
    args = parser.parse_args(argv)

    offered: dict[str, str] = {}
    for entry in args.generated:
        name, separator, directory = entry.partition("=")
        if not separator or not name or not directory:
            print(
                f"check_embedded_description: --generated wants ENV=DIR, not '{entry}'",
                file=sys.stderr,
            )
            return 2
        offered[name] = directory

    try:
        problems, inspected = check(args.project, offered)
    except build_environments.ConfigurationError as error:
        print(f"check_embedded_description: {error}", file=sys.stderr)
        return 2

    if problems:
        print(
            "check_embedded_description: a machine would be built carrying something the "
            "verification tier did not verify",
            file=sys.stderr,
        )
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print(
        f"check_embedded_description: {', '.join(inspected)} would embed what the "
        "verification tier is pinned to, byte for byte"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
