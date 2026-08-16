#!/usr/bin/env python3
"""Fail when a call through the hardware seam is not a direct call.

Selecting the implementation at build time is what keeps an indirect call out
of the control path. If the seam were a struct of function pointers or a
virtual dispatch table, every peripheral operation would become an indirect
call, and the timing claim the real-time obligation bounds would have to be
re-established against it.

Reading the header is not enough to establish that: a header can declare free
functions while a build still routes them through a pointer. So this check
disassembles the linked executable, finds the functions the control
translation units defined, and requires that every seam operation those
translation units reference is reached by a direct call, with no indirect call
anywhere on a control-path call site.

It fails rather than passes when it cannot find what it is meant to inspect --
no control functions in the disassembly, or no seam references at all -- since
a check that inspects nothing must not report success.

Usage: check_direct_calls.py <executable> --header <hw_interface.h> --objects <dir-or-obj> [...]
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

# `bl <symbol>` on arm64, `callq <addr> <symbol>` on x86-64. A branch to a bare
# address is control flow inside the function, not a call to another function.
DIRECT_CALL = re.compile(
    r"^\s*(?:bl|call|callq)\s+(?:0x[0-9a-f]+\s+)?"
    r"(?:<(?P<angled>[A-Za-z_][A-Za-z0-9_.$]*)>|(?P<plain>_[A-Za-z0-9_.$]+))\s*$"
)

# `blr x8` / `br x8` on arm64 and their pointer-authenticated forms `blraa`,
# `blraaz`, `braa`; `callq *%rax` / `jmpq *(%rax)` on x86-64.
INDIRECT_CALL = re.compile(r"^\s*(?:blra[abz]*|bra[abz]*|blr|br|call|callq|jmp|jmpq)\s+[*xw]")

# A tail call: the last operation reached by jumping straight to another symbol.
DIRECT_TAIL_CALL = re.compile(
    r"^\s*(?:b|jmp|jmpq)\s+(?:0x[0-9a-f]+\s+)?"
    r"(?:<(?P<angled>[A-Za-z_][A-Za-z0-9_.$]*)>|(?P<plain>_[A-Za-z0-9_.$]+))\s*$"
)

SYMBOL_LABEL = re.compile(r"^(_[A-Za-z0-9_.$]+):\s*$")

# A function declaration at file scope: `uint32_t hw_monotonic_millis(void);`.
# Matching declarations rather than a name prefix keeps the check tied to what
# the header actually declares, so renaming the seam's operations cannot
# quietly narrow what is inspected.
HEADER_FUNCTION = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*[A-Za-z0-9_ \t*]*?\b([A-Za-z_][A-Za-z0-9_]*)\s*\([^;{)]*\)\s*;",
    re.MULTILINE,
)

OBJECT_SUFFIXES = (".o", ".obj")


def seam_symbols(header_path: str) -> set[str]:
    """The linker symbols for the operations the seam header declares."""
    with open(header_path, "r", encoding="utf-8") as handle:
        source = handle.read()
    names = set(HEADER_FUNCTION.findall(source))
    if not names:
        raise SystemExit(f"check_direct_calls: no seam operations declared in {header_path}")
    # Mach-O prefixes C symbols with an underscore; ELF does not, so accept both.
    return names | {f"_{name}" for name in names}


def collect_objects(roots: list[str]) -> list[str]:
    objects: list[str] = []
    for root in roots:
        if os.path.isfile(root):
            objects.append(root)
            continue
        for directory, _subdirs, files in os.walk(root):
            for name in sorted(files):
                if name.endswith(OBJECT_SUFFIXES):
                    objects.append(os.path.join(directory, name))
    return sorted(objects)


def symbols_of(objects: list[str]) -> tuple[set[str], set[str]]:
    """Functions the objects define, and symbols they leave for the linker."""
    defined: set[str] = set()
    undefined: set[str] = set()

    for obj in objects:
        result = subprocess.run(["nm", obj], capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise SystemExit(f"check_direct_calls: nm failed on {obj}: {result.stderr.strip()}")
        for line in result.stdout.splitlines():
            fields = line.split()
            if len(fields) == 2 and fields[0] == "U":
                undefined.add(fields[1])
            elif len(fields) == 3 and fields[1] in ("T", "t"):
                # Compiler-generated module constructors are not control logic.
                if not fields[2].startswith(("_asan.", "_ubsan.", "ltmp")):
                    defined.add(fields[2])

    return defined, undefined


def _disassembler_output(executable: str) -> subprocess.CompletedProcess:
    """Run whichever disassembler this host has.

    Neither tool is present everywhere -- otool ships with the Apple toolchain,
    objdump with binutils and LLVM -- so each is tried and a missing one is not
    an error. Having none at all is, since the check would otherwise inspect
    nothing.
    """
    attempts = (
        (["otool", "-tV", executable], "(__TEXT,__text)"),
        (["objdump", "-d", "--no-show-raw-insn", executable], "<"),
        (["llvm-objdump", "-d", "--no-show-raw-insn", executable], "<"),
    )

    for command, expected in attempts:
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        except FileNotFoundError:
            continue
        if result.returncode == 0 and expected in result.stdout:
            return result

    raise SystemExit(
        f"check_direct_calls: no disassembler on this host could read {executable}"
    )


def disassemble(executable: str) -> dict[str, list[str]]:
    """The executable's text section, split into one instruction list per symbol."""
    result = _disassembler_output(executable)

    functions: dict[str, list[str]] = {}
    current: str | None = None
    for raw in result.stdout.splitlines():
        label = SYMBOL_LABEL.match(raw) or re.match(r"^[0-9a-f]+ <(_?[^>]+)>:\s*$", raw)
        if label:
            current = label.group(1)
            functions[current] = []
            continue
        if current is None:
            continue
        # Strip the leading address column, leaving the instruction.
        instruction = re.sub(r"^\s*[0-9a-f]+:?\s*", "", raw)
        if instruction.strip():
            functions[current].append(instruction)

    return functions


def check(executable: str, header: str, object_roots: list[str]) -> list[str]:
    """Report every reason the seam's calls are not provably direct."""
    problems: list[str] = []

    objects = collect_objects(object_roots)
    if not objects:
        return [f"no object files found under {', '.join(object_roots)}"]

    defined, undefined = symbols_of(objects)
    if not defined:
        return [f"no control functions defined by {len(objects)} object file(s)"]

    seam = seam_symbols(header)
    referenced = sorted(undefined & seam)
    if not referenced:
        return [
            "the control objects reference no seam operation, so there is "
            "nothing to prove direct"
        ]

    functions = disassemble(executable)
    reached: set[str] = set()
    inspected = 0

    for symbol in sorted(defined):
        body = functions.get(symbol)
        if body is None:
            problems.append(f"{symbol}: defined by the control objects but absent from {executable}")
            continue
        inspected += 1

        for instruction in body:
            if INDIRECT_CALL.match(instruction):
                problems.append(
                    f"{symbol}: indirect call on a control-path call site: "
                    f"{instruction.strip()}"
                )
                continue
            direct = DIRECT_CALL.match(instruction) or DIRECT_TAIL_CALL.match(instruction)
            if direct is None:
                continue
            target = direct.group("angled") or direct.group("plain")
            if target in seam:
                reached.add(target)

    if inspected == 0:
        problems.append(f"no control function was found in {executable} to inspect")

    for symbol in referenced:
        if symbol not in reached:
            problems.append(
                f"{symbol}: referenced by the control objects but reached by no "
                "direct call in the linked executable"
            )

    return problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", help="the linked host executable")
    parser.add_argument("--header", required=True, help="the seam header declaring the operations")
    parser.add_argument(
        "--objects",
        required=True,
        nargs="+",
        help="object files, or directories of them, built from the control sources",
    )
    args = parser.parse_args(argv)

    for path in [args.executable, args.header, *args.objects]:
        if not os.path.exists(path):
            print(f"check_direct_calls: no such path: {path}", file=sys.stderr)
            return 2

    problems = check(args.executable, args.header, args.objects)
    if problems:
        print("check_direct_calls: the seam is not reached by direct calls", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print("check_direct_calls: every seam operation the control logic uses is a direct call")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
