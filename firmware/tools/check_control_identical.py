#!/usr/bin/env python3
"""Fail when the control logic is not the same code in both environments.

Substitution is only a link-time fact if the control translation units really
are identical between the host build and the target build. Comparing the raw
sources cannot establish that: a macro defined by one environment and not the
other changes what the compiler sees while leaving every source file byte for
byte the same. So the comparison is made after preprocessing.

Two things make the comparison meaningful rather than noisy:

  * Only the text that came from the control sources and the seam header is
    compared. A translation unit also pulls in the freestanding headers, and
    those legitimately differ between a host compiler and a cross compiler --
    including them would make the check fail for a reason that says nothing
    about the control logic.
  * The text is compared as a token sequence rather than as characters, so the
    two preprocessors' differing whitespace habits are not mistaken for a
    difference in the code. A macro that expands differently still changes the
    tokens.

Usage: check_control_identical.py --project <dir> --env native --env stm32
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shlex
import subprocess
import sys

TOKEN = re.compile(
    r"""
      "(?:\\.|[^"\\])*"            # string literal
    | '(?:\\.|[^'\\])*'            # character literal
    | [A-Za-z_][A-Za-z0-9_]*       # identifier or keyword
    | \.?[0-9](?:[0-9A-Za-z_.]|[eEpP][+-])*   # preprocessing number
    | \S                           # any other single character
    """,
    re.VERBOSE,
)

LINE_MARKER = re.compile(r'^#\s+\d+\s+"([^"]*)"')


def compilation_database(project: str, environment: str, pio: str) -> list[dict]:
    """Build the environment and return the compiler command for each source.

    The commands come from the build itself rather than being reconstructed
    here, so the comparison uses exactly the flags and include paths each
    environment really compiles with.
    """
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
            f"check_control_identical: no compilation database for '{environment}':\n"
            f"{result.stdout}\n{result.stderr}"
        )

    with open(database_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def preprocess(entry: dict, project: str) -> str:
    """Preprocessed output for one translation unit, with line markers kept."""
    arguments = entry.get("arguments") or shlex.split(entry["command"])

    filtered: list[str] = []
    skip_next = False
    for argument in arguments:
        if skip_next:
            skip_next = False
            continue
        if argument == "-o":
            skip_next = True
            continue
        if argument == "-c" or argument.startswith("-o"):
            continue
        filtered.append(argument)
    filtered.insert(1, "-E")

    result = subprocess.run(
        filtered,
        cwd=entry.get("directory", project),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"check_control_identical: preprocessing {entry['file']} failed:\n{result.stderr}"
        )
    return result.stdout


def own_tokens(preprocessed: str, own_directories: list[str], base: str = ".") -> list[str]:
    """The token sequence contributed by the project's own sources.

    Line markers name the file each following run of text came from, so this
    walks them and keeps only the runs attributed to the directories that hold
    the control logic and the seam header.

    A compiler invoked from the project directory emits relative marker paths,
    so `base` is the directory those are relative to -- the directory the
    compiler ran in, not this process's working directory. Resolving them
    against the wrong directory matches nothing, and matching nothing is
    indistinguishable from two environments agreeing.
    """
    keeping = False
    tokens: list[str] = []

    for line in preprocessed.splitlines():
        marker = LINE_MARKER.match(line)
        if marker:
            path = os.path.realpath(os.path.join(base, marker.group(1)))
            keeping = any(
                path.startswith(directory + os.sep) or path == directory
                for directory in own_directories
            )
            continue
        if keeping:
            tokens.extend(TOKEN.findall(line))

    return tokens


def check(project: str, environments: list[str], pio: str) -> list[str]:
    own_directories = [
        os.path.realpath(os.path.join(project, "src", "control")),
        os.path.realpath(os.path.join(project, "include")),
    ]
    control_directory = own_directories[0]

    per_environment: dict[str, dict[str, list[str]]] = {}
    for environment in environments:
        database = compilation_database(project, environment, pio)
        units: dict[str, list[str]] = {}
        for entry in database:
            source = os.path.realpath(os.path.join(entry.get("directory", project), entry["file"]))
            if not source.startswith(control_directory + os.sep):
                continue
            units[os.path.relpath(source, project)] = own_tokens(
                preprocess(entry, project), own_directories, entry.get("directory", project)
            )
        per_environment[environment] = units

    return differences(environments, per_environment)


def differences(
    environments: list[str], per_environment: dict[str, dict[str, list[str]]]
) -> list[str]:
    """Compare each environment's token streams against the first environment's."""
    problems: list[str] = []
    reference_environment = environments[0]
    reference = per_environment[reference_environment]

    if not reference:
        return [f"no control translation unit was compiled in '{reference_environment}'"]

    # A unit whose own text contributed no tokens means the comparison saw
    # nothing -- two empty streams compare equal, which would report agreement
    # the check never established.
    for environment, units in per_environment.items():
        for unit, tokens in sorted(units.items()):
            if not tokens:
                problems.append(
                    f"{unit}: no text of its own survived preprocessing in "
                    f"'{environment}', so nothing was compared"
                )
    if problems:
        return problems

    for environment in environments[1:]:
        other = per_environment[environment]
        for unit in sorted(set(reference) | set(other)):
            if unit not in reference or unit not in other:
                present = reference_environment if unit in reference else environment
                problems.append(f"{unit}: compiled only in '{present}'")
                continue
            if reference[unit] != other[unit]:
                diff = difflib.unified_diff(
                    reference[unit],
                    other[unit],
                    fromfile=f"{unit} [{reference_environment}]",
                    tofile=f"{unit} [{environment}]",
                    lineterm="",
                    n=2,
                )
                problems.append(
                    f"{unit}: differs between '{reference_environment}' and '{environment}':\n"
                    + "\n".join(f"    {line}" for line in list(diff)[:40])
                )

    return problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="the PlatformIO project directory")
    parser.add_argument(
        "--env",
        dest="environments",
        action="append",
        required=True,
        help="an environment to compare; give at least two",
    )
    parser.add_argument(
        "--pio",
        default=os.environ.get("PIO", os.path.expanduser("~/.platformio/penv/bin/pio")),
        help="the PlatformIO executable",
    )
    args = parser.parse_args(argv)

    if len(args.environments) < 2:
        print("check_control_identical: give at least two environments", file=sys.stderr)
        return 2

    project = os.path.realpath(args.project)
    problems = check(project, args.environments, args.pio)

    if problems:
        print(
            "check_control_identical: the control logic is not identical across "
            "environments",
            file=sys.stderr,
        )
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print(
        "check_control_identical: every control translation unit preprocesses "
        f"identically across {', '.join(args.environments)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
