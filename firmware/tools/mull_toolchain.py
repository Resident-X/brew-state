#!/usr/bin/env python3
"""Find the compiler and the mutation plugin, and refuse a pair that cannot work.

The sweep needs a compiler that is not the one the host build ordinarily uses.
PlatformIO's native platform resolves its compiler by looking along PATH for
`cc`, and on a Mac that is Apple's Clang, which does not load an LLVM pass
plugin built against upstream LLVM. So the mutation build names its compiler
instead of inheriting one.

Naming it is not the same as hardcoding a path. Mull ships as a Homebrew keg on
one host and as a downloaded package on another, and the pass plugin sits at a
different place under each; a path that works on the machine it was written on
is the reason a verification tool ends up being something only its author can
run. Each tool here is looked for in turn -- what the caller named, then what
the environment names, then the places each packaging puts it -- and the first
one that is really there wins.

The version check is the part that earns its place. A pass plugin is loaded into
the compiler's own process and is built against one LLVM release; loading it
into a compiler from another release does not reliably fail, it misbehaves. So
the compiler's LLVM version and the runner's are read and compared, and a
mismatch is refused here with both versions named, rather than left to surface
as a mutant population that is quietly wrong.
"""

from __future__ import annotations

import os
import re
import subprocess

#: The LLVM release this sweep is built around. Mull is published per LLVM
#: release and the plugin is only loadable by the matching compiler, so the
#: number appears in the tool names as well as in what they report.
LLVM_MAJOR = 19

#: The scoping configuration, which decides which sources the mutant population
#: is drawn from. The plugin looks for it by this name in the working directory
#: the compiler runs in, and the runner looks for it again when it executes the
#: mutants, so both stages are told where it is outright.
CONFIG_NAME = "mull.yml"

#: What the environment may name each tool with, for a host that puts them
#: somewhere none of the candidates below expect.
CLANG_VARIABLE = "MULL_CLANG"
PLUGIN_VARIABLE = "MULL_IR_FRONTEND"
RUNNER_VARIABLE = "MULL_RUNNER"

#: Compilers to try, in order. The bare name is first so a host that has put the
#: right compiler on PATH is believed before any packaging layout is guessed at;
#: the rest are where Homebrew and the published Linux packages put it.
CLANG_CANDIDATES = (
    f"clang-{LLVM_MAJOR}",
    f"/opt/homebrew/opt/llvm@{LLVM_MAJOR}/bin/clang",
    f"/usr/local/opt/llvm@{LLVM_MAJOR}/bin/clang",
    f"/usr/lib/llvm-{LLVM_MAJOR}/bin/clang",
)

#: The pass plugin is a library rather than a program, so it is looked for as a
#: file rather than run. Homebrew's keg-only symlink comes before the versioned
#: Cellar path it points into, because the Cellar path carries Mull's own
#: release number and would go stale on the next upgrade.
PLUGIN_CANDIDATES = (
    f"/opt/homebrew/opt/mull@{LLVM_MAJOR}/lib/mull-ir-frontend-{LLVM_MAJOR}",
    f"/usr/local/opt/mull@{LLVM_MAJOR}/lib/mull-ir-frontend-{LLVM_MAJOR}",
    f"/usr/lib/mull-ir-frontend-{LLVM_MAJOR}",
    f"/usr/local/lib/mull-ir-frontend-{LLVM_MAJOR}",
    f"/usr/lib/llvm-{LLVM_MAJOR}/lib/mull-ir-frontend-{LLVM_MAJOR}",
)

#: The runner that executes the mutants a compiled artefact carries.
RUNNER_CANDIDATES = (f"mull-runner-{LLVM_MAJOR}",)

#: `clang version 19.1.7`, however the vendor prefixes it.
_CLANG_VERSION = re.compile(r"clang version (\d+)\.(\d+)\.(\d+)")

#: `LLVM: 19.1.7`, which is what the runner reports it was built against.
_RUNNER_LLVM_VERSION = re.compile(r"LLVM:\s*(\d+)\.(\d+)\.(\d+)")


class ToolchainError(Exception):
    """A tool the sweep needs is absent, or the ones present cannot work together."""


def _version_output(command: list[str]) -> str | None:
    """What a tool prints when asked its version, or None if it is not there."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except (FileNotFoundError, PermissionError, OSError):
        return None
    if result.returncode != 0:
        return None
    return f"{result.stdout}\n{result.stderr}"


def _candidates(explicit: str | None, variable: str, defaults: tuple[str, ...]) -> list[str]:
    """What to try: what the caller or the environment named, or else the usual places.

    A tool named outright is the only one tried. Falling back to a discovered
    one when the named one turns out to be unusable would answer a different
    question from the one that was asked -- somebody naming a compiler wants
    that compiler, and quietly building with another is how a sweep ends up
    reporting a mutant population from a toolchain nobody chose. The named one
    failing is reported as that, so it can be fixed.
    """
    named = []
    if explicit:
        named.append(explicit)
    from_environment = os.environ.get(variable, "").strip()
    if from_environment:
        named.append(from_environment)
    return named or list(defaults)


def clang_version(compiler: str) -> tuple[int, int, int] | None:
    """The LLVM release a compiler reports, or None if it is not a usable one.

    A compiler that is absent and one that does not report an LLVM version are
    the same answer here, because neither can load the plugin. Apple's Clang is
    the second case that matters: it reports its own numbering, which does not
    match any LLVM release, so it falls out here rather than being run.
    """
    output = _version_output([compiler, "--version"])
    if output is None:
        return None
    match = _CLANG_VERSION.search(output)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def runner_llvm_version(runner: str) -> tuple[int, int, int] | None:
    """The LLVM release the mutant runner was built against, or None if it is absent."""
    output = _version_output([runner, "--version"])
    if output is None:
        return None
    match = _RUNNER_LLVM_VERSION.search(output)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def find_clang(
    explicit: str | None = None, candidates: tuple[str, ...] = CLANG_CANDIDATES
) -> tuple[str, tuple[int, int, int]]:
    """The first compiler that is there and reports the LLVM release this needs."""
    tried = _candidates(explicit, CLANG_VARIABLE, candidates)
    for candidate in tried:
        version = clang_version(candidate)
        if version is not None and version[0] == LLVM_MAJOR:
            return candidate, version
    raise ToolchainError(
        f"no compiler reporting LLVM {LLVM_MAJOR} was found -- the mutation plugin is built "
        f"against that release and is not loadable by another. Tried: {', '.join(tried)}. "
        f"Set {CLANG_VARIABLE} to name one."
    )


def find_pass_plugin(
    explicit: str | None = None, candidates: tuple[str, ...] = PLUGIN_CANDIDATES
) -> str:
    """The first mutation pass plugin that is really on disk."""
    tried = _candidates(explicit, PLUGIN_VARIABLE, candidates)
    for candidate in tried:
        if os.path.isfile(candidate):
            return candidate
    raise ToolchainError(
        f"the mutation pass plugin mull-ir-frontend-{LLVM_MAJOR} was not found. "
        f"Tried: {', '.join(tried)}. Set {PLUGIN_VARIABLE} to name it."
    )


def find_runner(
    explicit: str | None = None, candidates: tuple[str, ...] = RUNNER_CANDIDATES
) -> tuple[str, tuple[int, int, int]]:
    """The first mutant runner that is there and reports the LLVM release it was built against."""
    tried = _candidates(explicit, RUNNER_VARIABLE, candidates)
    for candidate in tried:
        version = runner_llvm_version(candidate)
        if version is not None:
            return candidate, version
    raise ToolchainError(
        f"mull-runner-{LLVM_MAJOR} was not found. Tried: {', '.join(tried)}. "
        f"Set {RUNNER_VARIABLE} to name it."
    )


def compile_flags(plugin: str) -> list[str]:
    """What the compiler needs in order to leave mutants in what it produces.

    `-grecord-command-line` is not decoration: the runner reads the command line
    the compiler recorded in order to know how each translation unit was built,
    and without it the mutants are in the artefact but the runner cannot account
    for where they came from.
    """
    return [f"-fpass-plugin={plugin}", "-grecord-command-line"]


def _spell(version: tuple[int, int, int]) -> str:
    return ".".join(str(part) for part in version)


def resolved(
    clang: str | None = None,
    plugin: str | None = None,
    runner: str | None = None,
    warn=None,
) -> dict[str, object]:
    """Every tool the sweep needs, with the compiler and the runner on the same release.

    Agreement is required at the major version and only noted below it, because
    that is the granularity the plugin is actually published at: Mull builds one
    package per LLVM release line, and each distribution pairs it with its own
    build of that line. Those builds do not agree on a patch level across
    distributions -- the package for one names 19.1.1 where another names
    19.1.7 -- so refusing on the patch level would refuse pairs their own
    packagers intend to be used together, on hosts where the sweep runs fine.

    The difference that does matter is refused. A compiler from another release
    line cannot load the plugin, and Apple's Clang, which is what PATH resolves
    to on a Mac, reports a version naming no LLVM release at all and never gets
    this far.
    """
    compiler, compiler_version = find_clang(clang)
    pass_plugin = find_pass_plugin(plugin)
    mutant_runner, runner_version = find_runner(runner)

    if compiler_version[0] != runner_version[0]:
        raise ToolchainError(
            f"'{compiler}' is LLVM {_spell(compiler_version)} and '{mutant_runner}' was built "
            f"against LLVM {_spell(runner_version)}. The plugin is loaded into the compiler's own "
            "process, so a build made by one and read by the other reports a mutant population "
            "that is wrong rather than failing outright."
        )

    if compiler_version != runner_version and warn is not None:
        warn(
            f"'{compiler}' is LLVM {_spell(compiler_version)} and '{mutant_runner}' was built "
            f"against LLVM {_spell(runner_version)}. Same release line, so the plugin loads; "
            "noted because a mutant population that looks wrong is worth checking this first."
        )

    return {
        "clang": compiler,
        "clang_version": compiler_version,
        "plugin": pass_plugin,
        "runner": mutant_runner,
        "runner_version": runner_version,
        "compile_flags": compile_flags(pass_plugin),
    }
