#!/usr/bin/env python3
"""Fail when a build of the plant model could compute differently on another host.

The plant model's recorded trajectory and the analysis records generated from it
are compared byte for byte, so one expression has to give one answer wherever it
is built. Two things the build can do to that are judged here, each on what the
build produced rather than on how the sources and the build file spell it:

  * Undefined symbols. Every symbol a plant object leaves for the linker must be
    defined by one of this project's own objects or be on a short, exact list of
    routines whose result no host can round differently. The elementary
    functions the host's maths library would define are not on it, so reaching
    for one fails however the call is spelled.
  * Fused multiply-add. The flags of every plant translation unit are read from
    the compile command the build really runs, the last contraction setting
    must be `off` and none of the flags that license rearranging arithmetic may
    appear; and the disassembly of the plant objects must hold none of the fused
    instructions of the architecture, which establishes the pin by its effect.
    On a build for a core with no floating-point unit the arithmetic is library
    calls, there is no instruction to fuse, and the scan finds nothing to look
    at; it says so rather than reporting a clean result it did not earn.

Covered are the environments whose source filter includes the plant, except
those declared to be refused or built for the mutation sweep. The mutation
sweep's own build is compiled only by the sweep, through a toolchain this check
does not require; the flags it adds are held by a test of the script that adds
them.

Usage: check_plant_arithmetic.py --project <dir>
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shlex
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_environments  # noqa: E402
import check_direct_calls  # noqa: E402
import check_sanitizers  # noqa: E402

#: Where the plant's sources are, within a project's `src/`.
PLANT_DIRECTORY = "plant"

#: Undefined symbols matched by prefix: the sanitizer and stack-protector
#: runtime, which computes nothing the plant does, and the soft-float routines of
#: the target's runtime, each of which is IEEE 754 arithmetic or a comparison.
EXACT_PREFIXES = ("__asan_", "__ubsan_", "__sanitizer_", "__stack_chk_", "__aeabi_f")

#: Undefined symbols matched exactly. Each is correctly rounded or a bit
#: operation, so no host can give a different last bit.
#:
#: `strtof` is on it because newlib's is correctly rounded (it converts through
#: gdtoa) and the parameters are parsed once, at load.
EXACT_SYMBOLS = frozenset(
    {
        "sqrtf", "fmaxf", "fminf", "memcpy", "memset", "memcmp", "strlen", "strtof",
        "__errno", "__error", "__errno_location",
        "__aeabi_i2f", "__aeabi_ui2f",
    }
)

#: Flags that let the compiler rearrange arithmetic, so one expression stops
#: giving one answer. A closed set the compilers document.
RELAXING_FLAGS = frozenset(
    {
        "-ffast-math", "-Ofast", "-ffp-model=fast", "-ffp-model=aggressive",
        "-funsafe-math-optimizations", "-fassociative-math", "-freciprocal-math",
        "-ffinite-math-only", "-fno-signed-zeros", "-fapprox-func",
        "-fcx-limited-range", "-mrecip",
    }
)

PIN = "-ffp-contract=off"
CONTRACTION_PREFIX = "-ffp-contract="

#: The fused multiply-add instructions of each architecture, as a mnemonic
#: followed by whitespace or the end of the line, and the instructions that show
#: the scan was looking at floating-point arithmetic at all.
ARCHITECTURES = {
    "arm64": (
        re.compile(r"(?<![\w.<])(?:fmadd|fmsub|fnmadd|fnmsub|fmla|fmls)(?!\w)"),
        re.compile(r"(?<![\w.<])(?:fadd|fsub|fmul|fdiv)(?!\w)"),
    ),
    "x86-64": (
        re.compile(r"(?<![\w.<])vf(?:n?m)(?:add|sub)\d*(?:ss|sd|ps|pd)(?![\w.])"),
        re.compile(r"(?<![\w.<])v?(?:add|sub|mul|div)(?:ss|sd)(?![\w.])"),
    ),
    "cortex-m4": (
        re.compile(r"(?<![\w.<])(?:vfma|vfms|vfnma|vfnms)(?:\.\w+)?(?![\w.])"),
        re.compile(r"(?<![\w.<])(?:vadd|vsub|vmul|vdiv)(?:\.\w+)?(?![\w.])"),
    ),
}


def architecture_of(environment: build_environments.Environment, machine: str) -> str:
    """Which instruction set one environment's objects are written in."""
    if not environment.is_host:
        return "cortex-m4"
    return "arm64" if machine.lower() in ("arm64", "aarch64") else "x86-64"


def covered(declared: list[build_environments.Environment]) -> list[build_environments.Environment]:
    """The environments that compile the plant and are built, rather than refused or swept."""
    refused = {e.name for e in build_environments.refused_environments(declared)}
    swept = {e.name for e in build_environments.mutation_environments(declared)}
    return [
        environment
        for environment in declared
        if f"{PLANT_DIRECTORY}/" in environment.source_filter
        and environment.name not in refused
        and environment.name not in swept
    ]


def is_allowed(symbol: str, leading_underscore: bool) -> bool:
    """Whether an undefined symbol is one of the routines every host computes alike."""
    name = symbol[1:] if leading_underscore and symbol.startswith("_") else symbol
    return name in EXACT_SYMBOLS or name.startswith(EXACT_PREFIXES)


def undefined_findings(
    label: str, undefined: set[str], defined_here: set[str], leading_underscore: bool
) -> list[str]:
    """Every undefined symbol that is neither the project's own nor on the exact list."""
    return [
        f"{label}: leaves '{symbol}' for the linker, which is neither defined by this "
        "project's own objects nor a routine every host computes alike"
        for symbol in sorted(undefined - defined_here)
        if not is_allowed(symbol, leading_underscore)
    ]


def flag_findings(source: str, arguments: list[str]) -> list[str]:
    """What is wrong with the flags one plant translation unit is really compiled with."""
    findings = [f"{source}: compiled with {flag}, which licenses rearranging arithmetic"
                for flag in arguments if flag in RELAXING_FLAGS]
    settings = [flag for flag in arguments if flag.startswith(CONTRACTION_PREFIX)]
    if not settings or settings[-1] != PIN:
        findings.append(
            f"{source}: the last contraction setting is "
            f"{settings[-1] if settings else 'absent'}, not {PIN}"
        )
    return findings


def plant_flag_findings(database: list[dict], project: str, environment: str) -> list[str]:
    """The flag findings for every plant source in one environment's compile database."""
    plant_root = os.path.realpath(os.path.join(project, "src", PLANT_DIRECTORY))
    findings: list[str] = []
    inspected = 0
    for entry in database:
        source = os.path.realpath(os.path.join(entry.get("directory", project), entry["file"]))
        if not source.startswith(plant_root + os.sep):
            continue
        inspected += 1
        arguments = entry.get("arguments") or shlex.split(entry["command"])
        findings += flag_findings(
            f"{environment}: {os.path.relpath(source, project)}", list(arguments)
        )
    if inspected == 0:
        findings.append(f"{environment}: no plant translation unit is compiled, so there are no flags to read")
    return findings


def fused_findings(label: str, disassembly: str, architecture: str) -> tuple[list[str], int]:
    """Each fused multiply-add in a disassembly, and how many arithmetic instructions it held."""
    fused, arithmetic = ARCHITECTURES[architecture]
    found = [
        f"{label}: fused multiply-add: {line.strip()}"
        for line in disassembly.splitlines()
        if fused.search(line)
    ]
    return found, sum(1 for line in disassembly.splitlines() if arithmetic.search(line))


def toolchain_tool(compiler: str, tool: str) -> str:
    """The binutils program of the compiler's own toolchain, or the host's own.

    A cross compiler is `<prefix>-gcc` beside `<prefix>-nm` and `<prefix>-objdump`;
    the host compiler has no such prefix, and the host's own program reads its objects.
    """
    name = os.path.basename(compiler)
    if name.endswith("-gcc"):
        candidate = os.path.join(os.path.dirname(compiler), f"{name[:-len('gcc')]}{tool}")
        if os.path.exists(candidate):
            return candidate
    return tool


def disassembly_of(obj: str, objdump: str, host: bool) -> str:
    if host:
        return check_direct_calls._disassembler_output(obj).stdout
    result = subprocess.run(
        [objdump, "-d", "--no-show-raw-insn", obj], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise check_sanitizers.CannotInspect(f"{objdump} could not read {obj}: {result.stderr.strip()}")
    return result.stdout


def objects_in(directory: str) -> list[str]:
    return check_direct_calls.collect_objects([directory])


def scan_note(environment: str, architecture: str, arithmetic: int) -> str:
    """What the fused-instruction scan of one environment looked at, said plainly."""
    if arithmetic:
        return f"{environment}: {arithmetic} {architecture} floating-point instructions scanned, none fused"
    return (
        f"{environment}: the fused-instruction scan is vacuous here -- the objects hold no "
        f"{architecture} floating-point instruction (soft-float: the arithmetic is library "
        "calls), so there is nothing to fuse; the flags and the undefined symbols are still judged"
    )


def check_environment(
    project: str, environment: build_environments.Environment, pio: str, machine: str
) -> tuple[list[str], list[str], list[str]]:
    """The problems found in one environment, what could not be looked at, and notes."""
    try:
        database = check_sanitizers.compile_commands(project, environment.name, pio)
    except check_sanitizers.CannotInspect as error:
        return [], [f"{environment.name}: {error}"], []

    problems = plant_flag_findings(database, project, environment.name)

    build_directory = os.path.join(environment.build_directory(project), "src")
    plant_objects = objects_in(os.path.join(build_directory, PLANT_DIRECTORY))
    if not plant_objects:
        return problems, [f"{environment.name}: no plant object under {build_directory} -- not built"], []

    compiler = next(
        (
            (entry.get("arguments") or shlex.split(entry["command"]))[0]
            for entry in database
            if os.path.realpath(os.path.join(entry.get("directory", project), entry["file"])).startswith(
                os.path.realpath(os.path.join(project, "src", PLANT_DIRECTORY)) + os.sep
            )
        ),
        "gcc",
    )
    nm = toolchain_tool(compiler, "nm")
    objdump = toolchain_tool(compiler, "objdump")
    leading_underscore = environment.is_host and sys.platform == "darwin"
    architecture = architecture_of(environment, machine)

    try:
        defined_here, _ = check_direct_calls.symbols_of(
            objects_in(build_directory), nm, check_direct_calls.ANY_DEFINITION
        )
        arithmetic = 0
        for obj in plant_objects:
            label = f"{environment.name}: {os.path.relpath(obj, project)}"
            _, undefined = check_direct_calls.symbols_of([obj], nm)
            problems += undefined_findings(label, undefined, defined_here, leading_underscore)
            fused, held = fused_findings(label, disassembly_of(obj, objdump, environment.is_host), architecture)
            problems += fused
            arithmetic += held
    except (check_sanitizers.CannotInspect, SystemExit) as error:
        return problems, [f"{environment.name}: {error}"], []

    note = scan_note(environment.name, architecture, arithmetic)
    return problems, [], [note]


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
        print(f"check_plant_arithmetic: {error}", file=sys.stderr)
        return 2

    subjects = covered(declared)
    if not any(environment.is_host for environment in subjects) or all(e.is_host for e in subjects):
        print(
            "check_plant_arithmetic: the build declares no host and no target environment "
            "compiling the plant, so this gate would report success without looking at anything",
            file=sys.stderr,
        )
        return 1

    problems: list[str] = []
    blockers: list[str] = []
    notes: list[str] = []
    for environment in subjects:
        found, blocked, noted = check_environment(project, environment, args.pio, platform.machine())
        problems += found
        blockers += blocked
        notes += noted

    if problems:
        print("check_plant_arithmetic: a build of the plant could compute differently on another host", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    if blockers:
        print("check_plant_arithmetic: the plant's arithmetic could not be established", file=sys.stderr)
        for blocker in blockers:
            print(f"  {blocker}", file=sys.stderr)
        return 2

    for note in notes:
        print(f"check_plant_arithmetic: {note}")
    print(
        f"check_plant_arithmetic: {', '.join(e.name for e in subjects)} compile the plant with "
        f"{PIN} last, no flag that rearranges arithmetic, no fused instruction and no undefined "
        "symbol outside the exact list"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
