#!/usr/bin/env python3
"""Fail when a machine would be built carrying a description nobody verified.

The bytes an artefact embeds are the one thing about the model that cannot be
read back off the running machine. Generating them from the description file
removes the obvious way for them to go stale, but it does not establish that
the artefact and the host verification tier are pinned to the same file. A
build naming a different description, a generated file left behind by an
incremental build, and a second description sitting alongside the intended one
each produce a target carrying something the tier never saw.

None of those has a symptom. A machine predicting from coefficients that
describe a different variant is wrong in exactly the way a machine that has
drifted is wrong, and the residual that would eventually surface it cannot tell
the two apart. So this is a build failure and not a warning, and it runs before
anything is compiled rather than against the artefact afterwards: an artefact
that should not exist is not made better by being inspected.

What the tier is pinned to is read through the module that reads the build, and
what the artefact carries is read through the module that wrote it. This check
owns neither format.

Usage: check_embedded_description.py --project <dir> [--generated ENV=PATH]
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_environments  # noqa: E402
import embedded_description  # noqa: E402


def read_bytes(path: str) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


def rendered_path(project: str, environment: build_environments.Environment) -> str:
    """Where this environment's build puts what it renders.

    Derived rather than given, so a second board is compared without a caller
    naming its build directory, and through the module that owns the format, so
    this looks where the build wrote rather than where a second path agrees.
    """
    return os.path.join(
        environment.build_directory(project),
        embedded_description.GENERATED_DIRECTORY,
        embedded_description.GENERATED_NAME,
    )


def check(project: str, generated: dict[str, str]) -> tuple[list[str], list[str]]:
    """Every way a machine build's embedding diverges from the pinned description.

    `generated` maps an environment name to the generated file to read for it.

    Which description each machine build declares is asked of every one of them,
    because that is answerable from the build file alone. The bytes are compared
    only for the environments a generated file is offered for, because they are
    rendered by the build and only exist for the build that ran. This runs
    inside each machine build and is offered that build's own file, so every
    artefact's bytes are compared as it is made -- and an environment offered
    here that does not build for a machine is refused rather than inspected,
    since it would be an answer about something that is not an artefact.
    """
    declared = build_environments.load(project)
    pinned, problems = build_environments.pinned_description(declared)
    if problems:
        return problems, []

    pinned_path = os.path.join(project, pinned)
    if not os.path.isfile(pinned_path):
        return [
            f"the verification tier is pinned to {pinned}, which is not there, so there is "
            "nothing for an artefact to be compared against"
        ], []
    verified = read_bytes(pinned_path)

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
            environment.name: rendered_path(project, environment)
            for environment in environments
        }

    source_root = os.path.abspath(os.path.join(project, "src"))
    scanned_source_tree = {
        path for path in generated.values() if os.path.abspath(path).startswith(source_root)
    }

    known = {environment.name for environment in environments}
    for name in sorted(set(generated) - known):
        problems.append(
            f"{name}: a generated embedding was offered for it, but it does not build an "
            "artefact for a machine, so there is nothing for those bytes to be carried by"
        )

    inspected: list[str] = []
    for environment in environments:
        declared_description = environment.embedded_description
        if not declared_description:
            problems.append(
                f"{environment.name}: builds for a machine and declares no "
                f"{build_environments.EMBEDDED_DESCRIPTION_OPTION}, so which description its "
                "artefact carries is not stated anywhere"
            )
            continue
        if declared_description != pinned:
            problems.append(
                f"{environment.name}: declares it embeds {declared_description}, but the "
                f"verification tier is pinned to {pinned}, so the machine would carry a "
                "description the tier never verified"
            )
            continue

        path = generated.get(environment.name)
        if path is None:
            # Not this run's subject. Its declaration has been checked above, and
            # its bytes are compared by its own build, which is the only run that
            # renders them.
            continue
        if path in scanned_source_tree:
            problems.append(
                f"{environment.name}: {path} is inside the source tree. The rendered "
                "description belongs under the build directory; a copy kept in the tree is "
                "the second description this compares against one"
            )
            continue
        if not os.path.isfile(path):
            problems.append(f"{environment.name}: no generated embedding at {path}")
            continue

        try:
            source, carried = embedded_description.decode(read_bytes(path).decode("utf-8"))
        except (embedded_description.MalformedEmbedding, UnicodeDecodeError) as error:
            problems.append(f"{environment.name}: {path}: {error}")
            continue

        inspected.append(environment.name)
        if source != pinned:
            problems.append(
                f"{environment.name}: {path} was generated from {source}, not from the "
                f"pinned {pinned}"
            )
        if carried != verified:
            problems.append(
                f"{environment.name}: the {len(carried)} bytes it would embed are not the "
                f"{len(verified)} bytes of {pinned}, so the artefact and the tier disagree "
                "about what the machine is"
            )

    return problems, inspected


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="the PlatformIO project directory")
    parser.add_argument(
        "--generated",
        action="append",
        default=[],
        metavar="ENV=PATH",
        help="the generated embedding to read for one environment; without any, every "
             "machine build is read from where its own build put it",
    )
    args = parser.parse_args(argv)

    offered: dict[str, str] = {}
    for entry in args.generated:
        name, separator, path = entry.partition("=")
        if not separator or not name or not path:
            print(
                f"check_embedded_description: --generated wants ENV=PATH, not '{entry}'",
                file=sys.stderr,
            )
            return 2
        offered[name] = path

    try:
        problems, inspected = check(args.project, offered)
    except build_environments.ConfigurationError as error:
        print(f"check_embedded_description: {error}", file=sys.stderr)
        return 2

    if problems:
        print(
            "check_embedded_description: a machine would be built carrying a description "
            "the verification tier did not verify",
            file=sys.stderr,
        )
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print(
        f"check_embedded_description: {', '.join(inspected)} would embed the description the "
        "verification tier is pinned to, byte for byte"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
