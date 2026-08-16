#!/usr/bin/env python3
"""Fail when a host build is not actually under analysis.

A build can link the sanitizer runtime while none of the code under analysis is
instrumented -- the executable then runs clean and reports nothing, and the
analysis stage looks like it passed. That failure is silent, so it is checked
for directly rather than assumed from the presence of a flag in the
configuration.

Two conditions are required together, because either alone can hold while this
project's sources go unanalysed:

  * every translation unit of this project's own is compiled with the sanitizer
    flags, with the flag that makes an undefined-behaviour finding abort rather
    than print and continue, and
  * the linked executable actually links a sanitizer runtime.

The strict warning settings are a second obligation with a different boundary,
checked here because it is the same compilation this already reads. They are
required wherever the build can scope flags to this project's sources alone.
Where it cannot -- an environment compiling the test runner's generated support
file through the same path -- the environment declares an exemption and the
reason with it, and the exemption is honoured only there: an environment that
does not compile foreign sources through that path could keep the settings, so
an exemption on one is a way of turning them off rather than an admission that
they cannot be held.

Which environments are covered is discovered rather than given. Every
environment `platformio.ini` declares for the host is covered, except those
declaring they must be refused rather than built: requiring a clean analysed
build of a configuration that must not build at all would contradict the
refusal. Discovering none at all is a failure, because a gate covering an
empty set reports success in exactly the way a gate nobody ran does.

Third-party sources keep the relaxed settings they already have: this looks
only at sources under the project's own src/ directory.

Usage: check_sanitizers.py --project <dir>
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_environments  # noqa: E402

#: What the code does when it runs is caught by these, and only when it runs:
#: the pair instruments the build, and the third makes a finding abort rather
#: than print and continue.
SANITIZER_FLAGS = (
    "-fsanitize=address,undefined",
    "-fno-sanitize-recover=all",
)

#: What the compiler can see without running anything. Required wherever the
#: build can apply them to this project's sources and to nothing else.
STRICT_FLAGS = (
    "-Werror",
    "-Wconversion",
    "-Wshadow",
    "-Wdouble-promotion",
)


def compile_commands(project: str, environment: str, pio: str) -> list[dict]:
    database_path = os.path.join(project, "compile_commands.json")
    if os.path.exists(database_path):
        os.remove(database_path)

    result = subprocess.run(
        [pio, "run", "-e", environment, "-t", "compiledb"],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    if not os.path.exists(database_path):
        raise SystemExit(
            f"check_sanitizers: no compilation database for '{environment}':\n"
            f"{result.stdout}\n{result.stderr}"
        )
    with open(database_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def runtime_linked(executable: str) -> bool | None:
    """Whether the executable pulls in a sanitizer runtime.

    None means no tool on this host could look. That is reported as a problem
    alongside the others rather than raised, because raising here discards
    every finding already collected -- a host missing an inspector would hide
    a genuine uninstrumented translation unit behind its own diagnostic.
    """
    inspected = False
    for command in (["otool", "-L", executable], ["ldd", executable], ["nm", executable]):
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        except FileNotFoundError:
            # Not every inspector exists on every host; the ones that do decide.
            continue
        if result.returncode != 0:
            continue
        inspected = True
        if "asan" in result.stdout or "ubsan" in result.stdout:
            return True
    if not inspected:
        return None
    return False


def required_flags(environment: build_environments.Environment) -> tuple[tuple[str, ...], list[str]]:
    """The flags this environment's sources must carry, and why any are missing.

    An environment declaring it cannot scope flags to this project's sources
    alone keeps the sanitizers and drops the warning settings. The declaration
    is honoured only where the build really does compile sources that are not
    this project's through that path -- which is what the test-runner option
    states -- so the exemption cannot be used to relax an environment that
    could hold them.
    """
    exemption = environment.strict_flags_exemption
    if not exemption:
        return SANITIZER_FLAGS + STRICT_FLAGS, []

    if not environment.runs_tests:
        return SANITIZER_FLAGS + STRICT_FLAGS, [
            f"'{environment.name}' claims an exemption from the strict warning settings "
            f"({exemption}), but it compiles no sources but this project's through that "
            "path, so it can carry them"
        ]

    return SANITIZER_FLAGS, []


def analysis_problems(
    database: list[dict],
    project: str,
    environment: build_environments.Environment,
) -> list[str]:
    """Every source of this project's own that is not under the full analysis.

    Separate from obtaining the compilation database so that the judgement can
    be exercised against a database standing in for a build, rather than only
    against whatever the host happens to compile today.
    """
    required, problems = required_flags(environment)

    # Every source this project compiles into the host build, not only the
    # control logic: an implementation of a seam that is not instrumented is
    # a hole in the same analysis.
    source_directory = os.path.realpath(os.path.join(project, "src"))

    inspected = 0
    for entry in database:
        source = os.path.realpath(os.path.join(entry.get("directory", project), entry["file"]))
        if not source.startswith(source_directory + os.sep):
            continue
        inspected += 1
        arguments = entry.get("arguments") or shlex.split(entry["command"])
        missing = [flag for flag in required if flag not in arguments]
        if missing:
            problems.append(
                f"{environment.name}: {os.path.relpath(source, project)}: compiled without "
                f"{', '.join(missing)} -- this translation unit is not under the analysis "
                "the rest of them are"
            )

    if inspected == 0:
        problems.append(
            f"no project translation unit is compiled in '{environment.name}', so the "
            "analysis stage has no subject"
        )

    return problems


def check(
    project: str,
    environment: build_environments.Environment,
    pio: str,
    linked: bool,
) -> list[str]:
    """Every reason this environment is not under the analysis it claims.

    `linked` says whether the environment produces an executable of its own.
    One that leaves the entry point to the test runner has nothing here to
    inspect for a runtime; it is run under the analysis by the test task
    instead, and its compilation is checked the same as any other.
    """
    database = compile_commands(project, environment.name, pio)
    problems = analysis_problems(database, project, environment)

    if not linked:
        return problems

    executable = environment.artefact(project)
    if not os.path.exists(executable):
        problems.append(f"{environment.name}: {executable} has not been built")
        return problems

    runtime = runtime_linked(executable)
    if runtime is None:
        problems.append(
            f"{environment.name}: no tool on this host could inspect {executable} for a "
            "sanitizer runtime"
        )
    elif not runtime:
        problems.append(f"{environment.name}: {executable} links no sanitizer runtime")

    return problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="the PlatformIO project directory")
    parser.add_argument(
        "--pio",
        default=os.environ.get("PIO", os.path.expanduser("~/.platformio/penv/bin/pio")),
        help="the PlatformIO executable",
    )
    args = parser.parse_args(argv)

    project = os.path.realpath(args.project)

    try:
        declared = build_environments.load(project)
    except build_environments.ConfigurationError as error:
        print(f"check_sanitizers: {error}", file=sys.stderr)
        return 2

    covered = build_environments.host_environments(declared)
    if not covered:
        print(
            "check_sanitizers: no environment producing a host artefact was found in "
            f"{build_environments.PROJECT_CONFIG}, so this gate has nothing to cover and "
            "would report success without checking anything",
            file=sys.stderr,
        )
        return 1

    linked = {environment.name for environment in build_environments.artefact_environments(declared)}

    problems: list[str] = []
    for environment in covered:
        problems.extend(check(project, environment, args.pio, environment.name in linked))

    if problems:
        print("check_sanitizers: a host build is not under analysis", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    for environment in build_environments.refused_environments(declared):
        print(
            f"check_sanitizers: '{environment.name}' is not covered -- {environment.must_not_build_reason}"
        )

    print(
        f"check_sanitizers: {', '.join(environment.name for environment in covered)} compile "
        "every source of this project's own under analysis, and every artefact of theirs links it"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
