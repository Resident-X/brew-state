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
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Compiling a header on its own is a property both seams' headers claim, so the
# implementation lives beside them rather than in either check.
from freestanding import compiles_freestanding  # noqa: E402
from vendor_symbols import find_violations  # noqa: E402


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
