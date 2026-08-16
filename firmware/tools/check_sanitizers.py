#!/usr/bin/env python3
"""Fail when the host build is not actually under analysis.

A build can link the sanitizer runtime while none of the code under analysis is
instrumented -- the executable then runs clean and reports nothing, and the
analysis stage looks like it passed. That failure is silent, so it is checked
for directly rather than assumed from the presence of a flag in the
configuration.

Two conditions are required together, because either alone can hold while this
project's sources go unanalysed:

  * every translation unit of this project's own is compiled with the sanitizer
    flags, with the flag that makes an undefined-behaviour finding abort rather
    than print and continue, and with the strict warning settings that make a
    conversion or a shadowed name a failure rather than a note, and
  * the linked executable actually links a sanitizer runtime.

The warning settings are required here rather than left to the build file for
the same reason the sanitizer flags are: dropping one from the configuration is
invisible, and the build stays green while the analysis has quietly narrowed.
Enlarging the subject -- adding a directory of sources -- must not be able to
narrow it either, which is what the "no translation unit inspected" condition
below is for.

Third-party sources keep the relaxed settings they already have: this looks
only at sources under the project's own src/ directory.

Usage: check_sanitizers.py --project <dir> --env native --executable <path>
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys

#: The analysis every source of this project's own reaches the host artefact
#: under. The sanitizer pair catches what the code does when it runs; the
#: warning settings catch what the compiler can see without running it.
REQUIRED_COMPILE_FLAGS = (
    "-fsanitize=address,undefined",
    "-fno-sanitize-recover=all",
    "-Werror",
    "-Wconversion",
    "-Wshadow",
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


def runtime_linked(executable: str) -> bool:
    """Whether the executable pulls in a sanitizer runtime."""
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
        raise SystemExit(
            "check_sanitizers: no tool on this host could inspect "
            f"{executable} for a sanitizer runtime"
        )
    return False


def analysis_problems(database: list[dict], project: str, environment: str) -> list[str]:
    """Every source of this project's own that is not under the full analysis.

    Separate from obtaining the compilation database so that the judgement can
    be exercised against a database standing in for a build, rather than only
    against whatever the host happens to compile today.
    """
    problems: list[str] = []

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
        missing = [flag for flag in REQUIRED_COMPILE_FLAGS if flag not in arguments]
        if missing:
            problems.append(
                f"{os.path.relpath(source, project)}: compiled without {', '.join(missing)} "
                "-- this translation unit is not under the analysis the rest of them are"
            )

    if inspected == 0:
        problems.append(
            f"no project translation unit is compiled in '{environment}', so the "
            "analysis stage has no subject"
        )

    return problems


def check(project: str, environment: str, executable: str, pio: str) -> list[str]:
    problems = analysis_problems(compile_commands(project, environment, pio), project, environment)

    if not runtime_linked(executable):
        problems.append(f"{executable}: links no sanitizer runtime")

    return problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="the PlatformIO project directory")
    parser.add_argument("--env", default="native", help="the host environment to inspect")
    parser.add_argument("--executable", required=True, help="the linked host executable")
    parser.add_argument(
        "--pio",
        default=os.environ.get("PIO", os.path.expanduser("~/.platformio/penv/bin/pio")),
        help="the PlatformIO executable",
    )
    args = parser.parse_args(argv)

    project = os.path.realpath(args.project)
    if not os.path.exists(args.executable):
        print(f"check_sanitizers: no such executable: {args.executable}", file=sys.stderr)
        return 2

    problems = check(project, args.env, args.executable, args.pio)
    if problems:
        print("check_sanitizers: the host build is not under analysis", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print(
        f"check_sanitizers: '{args.env}' compiles every source of this project's own and "
        "links under analysis"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
