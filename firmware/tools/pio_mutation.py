"""Compile the host test build so that it carries mutants of its own arithmetic.

Three things have to be true of this build that are not true of the ordinary
one, and each is done here rather than in the build file because each is a
property of the mutation toolchain rather than of the project.

The compiler is named rather than inherited. PlatformIO's native platform finds
its compiler along PATH, which on a Mac is Apple's Clang; the mutation pass is
an LLVM plugin and Apple's Clang will not load it. So the compiler discovered
for this release is substituted for both compiling and linking, and the whole
environment is built by it -- mixing two compilers across a link is its own
class of problem, and there is nothing to gain here by mixing them.

The optimiser is turned off. Mutating a comparison and then letting the
optimiser fold the comparison away produces a mutant that is not in the
artefact, which is indistinguishable in the result from a mutant the tests
killed. The ordinary host build compiles at -O1; here that would inflate the
score with mutants nothing ever ran.

The analysis is absent, and that is the point rather than an omission. The
environment leaves the sanitizer script out of its `extra_scripts`, so this is
the one host build compiled without it. A mutant that makes the program read out
of bounds would be stopped by AddressSanitizer whether or not any test asserts
anything about it, and counting that as caught would credit the test suite with
noticing something the analysis noticed. The question this build exists to
answer is what the tests catch, so it is asked with nothing else watching. The
same translation units are compiled under the analysis by the environment this
one extends, so nothing goes unanalysed by leaving it off here.
"""

import os
import sys

Import("env")  # noqa: F821 -- injected by SCons

# Resolved from PROJECT_DIR rather than from this file's own path: a script run
# by the build system is exec'd rather than imported, so it has no __file__ to
# take a directory from.
PROJECT_DIR = env.subst("$PROJECT_DIR")  # noqa: F821
sys.path.insert(0, os.path.join(PROJECT_DIR, "tools"))

import mull_toolchain  # noqa: E402

try:
    toolchain = mull_toolchain.resolved(
        warn=lambda note: sys.stderr.write(f"pio_mutation: {note}\n")
    )
except mull_toolchain.ToolchainError as error:
    sys.stderr.write(f"pio_mutation: {error}\n")
    env.Exit(2)  # noqa: F821
    raise

#: Where the scoping configuration lives. The plugin reads it from the working
#: directory the compiler is run in, which is the project directory, but naming
#: it outright means a build started from somewhere else still mutates the same
#: sources rather than silently mutating everything.
CONFIG = os.path.join(PROJECT_DIR, mull_toolchain.CONFIG_NAME)

MUTATION_FLAGS = toolchain["compile_flags"] + ["-O0"]


def without_optimisation(flags):
    """The same flags with any optimisation setting removed.

    The setting is dropped wherever it came from rather than assumed to be the
    one the build file currently writes, so that changing the ordinary build's
    optimisation cannot quietly start folding mutants away in this one.
    """
    return [flag for flag in flags if not str(flag).startswith("-O")]


def instrument(construction):
    """Point one construction environment at the mutation toolchain."""
    construction.Replace(CC=toolchain["clang"], LINK=toolchain["clang"])
    construction.Replace(CCFLAGS=without_optimisation(construction.get("CCFLAGS", [])))
    construction.Append(CCFLAGS=MUTATION_FLAGS, LINKFLAGS=MUTATION_FLAGS)
    construction["ENV"]["MULL_CONFIG"] = CONFIG


# The project's own sources are compiled through a separate construction
# environment from the one that links, so both are pointed at the compiler. The
# link step matters as much as the compile: a build whose objects carry mutants
# and whose link step ran under a different compiler is one whose failure comes
# out as a missing symbol rather than as anything about mutants.
instrument(env)  # noqa: F821

try:
    Import("projenv")  # noqa: F821 -- present once the project sources are configured
except Exception:  # pragma: no cover -- absent only when no project sources are built
    projenv = None

if projenv is not None:
    instrument(projenv)
