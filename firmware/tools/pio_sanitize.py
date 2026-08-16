"""Compile and link the host build under memory and undefined-behaviour analysis.

The flags go on both the compile and the link step: a sanitizer applied only at
compile time links against no runtime and reports nothing.

The project's own sources are compiled through a separate construction
environment from the one that links, so the flags have to be applied to both.
Applying them only to the linking environment produces a binary that links the
sanitizer runtime while none of the code under analysis is instrumented --
which passes silently and analyses nothing.

-fno-sanitize-recover makes an undefined-behaviour finding abort the run rather
than print and continue, so a finding fails the build instead of scrolling past
in a log that ends in success. AddressSanitizer already aborts on its first
finding. -fno-omit-frame-pointer is what makes the reports name the frames that
led there.
"""

Import("env")  # noqa: F821 -- injected by SCons

SANITIZERS = ["-fsanitize=address,undefined", "-fno-sanitize-recover=all", "-fno-omit-frame-pointer"]

env.Append(CCFLAGS=SANITIZERS, LINKFLAGS=SANITIZERS)  # noqa: F821

try:
    Import("projenv")  # noqa: F821 -- present once the project sources are configured
except Exception:  # pragma: no cover -- absent only when no project sources are built
    projenv = None

if projenv is not None:
    projenv.Append(CCFLAGS=SANITIZERS, LINKFLAGS=SANITIZERS)
