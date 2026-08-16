"""Compiling one header on its own, against a compiler with no library behind it.

Both seams in this project make the same claim about their header: it needs
nothing beyond the freestanding headers it includes, so a translation unit that
includes it inherits no dependency it did not ask for. Reading the header
cannot establish that -- a header that quietly relies on an include path the
surrounding build happens to supply reads exactly like one that does not -- so
it is established by compiling the header alone with that include path taken
away.

This is the one implementation of that, shared by the hardware seam's header
check and the plant seam's.
"""

from __future__ import annotations

import os
import subprocess
import tempfile


def freestanding_include_dir(compiler: str) -> str:
    """The compiler's own header directory, which carries the freestanding set.

    C requires stdbool.h, stdint.h and stddef.h to be available in a
    freestanding environment, and the compiler -- not the C library -- supplies
    them. Pointing at that directory alone, with -nostdinc excluding everything
    else, is what makes "no vendor include path present" a real condition
    rather than an assertion.
    """
    result = subprocess.run(
        [compiler, "-print-file-name=include"], capture_output=True, text=True, check=False
    )
    path = result.stdout.strip()
    if result.returncode != 0 or not path or not os.path.isdir(path):
        raise SystemExit(
            f"freestanding: {compiler} did not report a usable freestanding include directory"
        )
    return path


def compiles_freestanding(
    header: str, compiler: str, include_dirs: list[str] | None = None
) -> tuple[bool, str]:
    """Compile a translation unit whose only content is this header.

    The include path is limited to the header's own directory plus whatever
    `include_dirs` names, so a header that quietly relies on a wider path fails
    here rather than passing because the surrounding build supplied one.

    `include_dirs` exists for a header whose types are supplied by whichever
    implementation the build selects: the seam header is neutral, and the
    directory named here stands in for the one the build would put on the path.
    Passing none is the stricter case and is what a header owing nothing to a
    selected implementation is held to.
    """
    with tempfile.TemporaryDirectory() as scratch:
        unit = os.path.join(scratch, "standalone.c")
        with open(unit, "w", encoding="utf-8") as handle:
            handle.write(f'#include "{os.path.abspath(header)}"\n')

        command = [
            compiler,
            "-std=c11",
            "-ffreestanding",
            "-fsyntax-only",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-nostdinc",
            "-I",
            freestanding_include_dir(compiler),
            "-I",
            os.path.dirname(os.path.abspath(header)),
        ]
        for directory in include_dirs or []:
            command.extend(["-I", os.path.abspath(directory)])
        command.append(unit)

        result = subprocess.run(command, capture_output=True, text=True, check=False)
        return result.returncode == 0, (result.stderr or result.stdout).strip()
