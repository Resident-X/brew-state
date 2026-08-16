#!/usr/bin/env python3
"""Fail when the hardware seam's header is not vendor-neutral.

The header is the whole point of the seam: if a signature in it names a HAL
handle, a CMSIS register type or a macro the build system injects, then every
translation unit that includes it inherits a dependency on the target, and the
control logic is no longer separable from the hardware.

Two things are checked, because either alone can pass while the property is
broken:

  * no vendor symbol appears anywhere in the header, and
  * the header compiles on its own against a freestanding compiler with no
    vendor include path present, which is what proves it needs nothing beyond
    the freestanding headers it includes.

Usage: check_header_neutral.py <header> [--cc clang]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vendor_symbols import find_violations  # noqa: E402


def compiles_freestanding(header: str, compiler: str) -> tuple[bool, str]:
    """Compile a translation unit whose only content is this header.

    The include path is deliberately limited to the header's own directory, so
    a header that quietly relies on a vendor include path fails here rather
    than passing because the surrounding build supplied one.
    """
    with tempfile.TemporaryDirectory() as scratch:
        unit = os.path.join(scratch, "standalone.c")
        with open(unit, "w", encoding="utf-8") as handle:
            handle.write(f'#include "{os.path.abspath(header)}"\n')

        result = subprocess.run(
            [
                compiler,
                "-std=c11",
                "-ffreestanding",
                "-fsyntax-only",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-nostdinc",
                "-I",
                _freestanding_include_dir(compiler),
                "-I",
                os.path.dirname(os.path.abspath(header)),
                unit,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0, (result.stderr or result.stdout).strip()


def _freestanding_include_dir(compiler: str) -> str:
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
            f"check_header_neutral: {compiler} did not report a usable freestanding "
            "include directory"
        )
    return path


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("header", help="the seam header to check")
    parser.add_argument("--cc", default=os.environ.get("CC", "clang"), help="C compiler to use")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.header):
        print(f"check_header_neutral: no such header: {args.header}", file=sys.stderr)
        return 2

    with open(args.header, "r", encoding="utf-8") as handle:
        violations = find_violations(args.header, handle.read())

    failed = False
    if violations:
        failed = True
        print("check_header_neutral: the seam header names the vendor", file=sys.stderr)
        for violation in violations:
            print(f"  {violation}", file=sys.stderr)

    ok, diagnostics = compiles_freestanding(args.header, args.cc)
    if not ok:
        failed = True
        print(
            "check_header_neutral: the seam header does not compile standalone "
            "against a freestanding compiler",
            file=sys.stderr,
        )
        for line in diagnostics.splitlines():
            print(f"  {line}", file=sys.stderr)

    if failed:
        return 1

    print(f"check_header_neutral: {args.header} is vendor-neutral and compiles standalone")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
