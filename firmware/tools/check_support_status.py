#!/usr/bin/env python3
"""Fail when a plant structure does not say how far it has been verified.

A structure that compiles, links and passes the seam's tests has established
nothing about the machine it claims to describe. Whether anyone has run it
against that hardware is a separate fact, it is the fact an adopter needs before
trusting a structure, and it is the one thing a tree of structures will not tell
them unless each structure is made to say it.

So every structure under the plant root declares PLANT_STRUCTURE_SUPPORT_STATUS
in its own header, as one of the values the vocabulary header declares, and this
check fails the build when one does not. It runs over the whole tree rather than
over the structure a build selected, so a structure nobody compiles cannot sit
there unanswered -- and a structure added later cannot reach the seam without
answering.

Four things are checked, because each can pass while another is broken:

  * the vocabulary itself still draws its line where the requirement draws it --
    at whether hardware has verified the structure, and at nothing else. A
    vocabulary that has grown a term for how thoroughly, or for whose machine,
    is the failure this check exists upstream of: every structure would then
    carry a status from a vocabulary answering a different question,
  * every structure declares a status, exactly once, and from that vocabulary,
  * a structure claiming verification cites what was run against what, so the
    claimable end of the vocabulary costs evidence rather than confidence, and
  * the shared documentation an adopter reads before choosing a structure says
    the same thing the structure's own sources do. A status that is true in a
    header nobody opens and stale in the table everybody reads is worse than no
    status, because it is believed.

The check fails rather than passes when it cannot find what it is meant to
inspect: no structures, no vocabulary, no documented table. A check that
inspects nothing must not report success.

Usage: check_support_status.py --plant-root <dir> --include-dir <dir>
                               --documentation <file>
"""

from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structure_symbols import discover  # noqa: E402
from vendor_symbols import strip_comments_and_strings  # noqa: E402

#: The header the vocabulary is declared in, relative to the include directory.
VOCABULARY_HEADER = "plant_support.h"

#: The type the vocabulary's values belong to.
VOCABULARY_TYPE = "plant_support_status_t"

#: The macro every structure defines to declare its status.
STATUS_MACRO = "PLANT_STRUCTURE_SUPPORT_STATUS"

#: The macro a structure claiming verification defines to cite it.
EVIDENCE_MACRO = "PLANT_STRUCTURE_SUPPORT_EVIDENCE"

#: The value that costs evidence, and the value that does not.
#
# These two names are the whole of the distinction the requirement draws, so
# unlike the structures' own symbols -- which are read out of the structures,
# because that set grows -- they are named here. The vocabulary is required to
# declare exactly them, in either order, so renaming one in the header fails
# this check loudly instead of quietly switching the evidence rule off.
UNVERIFIED = "PLANT_SUPPORT_UNVERIFIED"
HARDWARE_VERIFIED = "PLANT_SUPPORT_HARDWARE_VERIFIED"

#: Cells that document an absence. None of them is a citation.
EMPTY_CELLS = frozenset(
    {"", "-", "--", "---", "–", "—", "?", "tbd", "n/a", "none", "not applicable"}
)

_ENUM_BODY = re.compile(r"\benum\b[^;{]*\{([^}]*)\}\s*" + VOCABULARY_TYPE + r"\s*;", re.DOTALL)
_ENUMERATOR = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)")
_STRING_LITERAL = re.compile(r'"((?:[^"\\]|\\.)*)"')
_TABLE_ROW = re.compile(r"^\s*\|(.+)\|\s*$")


class Uninspectable(Exception):
    """The check cannot see what it is meant to inspect.

    Distinct from a finding: a missing vocabulary or missing documentation is
    not a structure making a bad claim, it is the check having established
    nothing at all. Reported as its own exit status so a build cannot read it
    as "every structure answered".
    """


def vocabulary(path: str) -> list[str]:
    """The values the vocabulary header declares, in declaration order.

    Read out of the header rather than listed here, so the check and the
    structures cannot disagree about what the words are -- only about which one
    a structure is entitled to.
    """
    if not os.path.isfile(path):
        raise Uninspectable(f"no vocabulary header at {path}")

    with open(path, "r", encoding="utf-8") as handle:
        cleaned = strip_comments_and_strings(handle.read())

    body = _ENUM_BODY.search(cleaned)
    if body is None:
        raise Uninspectable(
            f"{path} declares no {VOCABULARY_TYPE}, so there is no vocabulary for a structure "
            "to draw its status from"
        )

    values: list[str] = []
    for entry in body.group(1).split(","):
        name = _ENUMERATOR.match(entry)
        if name is not None:
            values.append(name.group(1))
    return values


def vocabulary_problems(values: list[str]) -> list[str]:
    """Every way the declared vocabulary stops drawing the line it should.

    The requirement's distinction is binary: hardware has verified this
    structure, or it has not. A vocabulary carrying a third term describes
    evidence nobody has and invites a structure to claim it, and one missing a
    term leaves a structure with nothing to say. Either is a change to what the
    status means, which is a requirement's business rather than a header's.
    """
    problems: list[str] = []
    declared = set(values)

    for required in (UNVERIFIED, HARDWARE_VERIFIED):
        if required not in declared:
            problems.append(f"declares no '{required}', so no structure can say it")

    for extra in sorted(declared - {UNVERIFIED, HARDWARE_VERIFIED}):
        problems.append(
            f"declares '{extra}', which draws a distinction beyond whether hardware has "
            "verified the structure"
        )

    if len(values) != len(declared):
        problems.append("declares a value more than once")

    return problems


def _logical_lines(source: str) -> list[tuple[int, str]]:
    """The source's lines, with backslash continuations joined onto the first.

    Reported line numbers stay those of the line a directive begins on, which
    is where a reader looking for it will be.
    """
    joined: list[tuple[int, str]] = []
    pending: list[str] = []
    start = 1
    for lineno, line in enumerate(source.splitlines(), start=1):
        if not pending:
            start = lineno
        if line.endswith("\\"):
            pending.append(line[:-1])
            continue
        pending.append(line)
        joined.append((start, "".join(pending)))
        pending = []
    if pending:
        joined.append((start, "".join(pending)))
    return joined


def _strip_disabled(cleaned: str) -> str:
    """Blank the lines inside an `#if 0`, which the compiler never sees.

    A status the preprocessor discards is a status only a reader skimming the
    header would credit -- the same hole as a commented-out one, one syntax
    over. Nesting is tracked so an `#if` inside the disabled region does not
    end it early, and an `#else` at the region's own level re-enables what
    follows, because that branch is the one that compiles.
    """
    kept: list[str] = []
    disabled_at: int | None = None
    depth = 0
    for line in cleaned.splitlines():
        directive = line.strip()
        if re.match(r"^#\s*if\b", directive):
            depth += 1
            if disabled_at is None and re.match(r"^#\s*if\s+0\s*$", directive):
                disabled_at = depth
        elif re.match(r"^#\s*(else|elif)\b", directive) and disabled_at == depth:
            disabled_at = None
        elif re.match(r"^#\s*endif\b", directive):
            if disabled_at == depth:
                disabled_at = None
            depth = max(0, depth - 1)
        kept.append("" if disabled_at is not None else line)
    return "\n".join(kept)


def definitions(source: str, macro: str) -> list[tuple[int, str, str]]:
    """Every definition of one macro, as (line, value, original replacement).

    The directives are found in source with comments blanked and disabled
    regions removed -- so neither a commented-out nor an `#if 0` definition is
    one -- and `value` is read from that same blanked source, so a trailing
    comment is not part of what the structure claims. The original replacement
    is carried alongside because blanking removes the string literal a citation
    lives in, and only the citation needs it.
    """
    directive = re.compile(rf"^\s*#\s*define\s+{re.escape(macro)}\b(.*)$")
    cleaned = dict(_logical_lines(_strip_disabled(strip_comments_and_strings(source))))
    found: list[tuple[int, str, str]] = []
    for lineno, line in _logical_lines(source):
        blanked = directive.match(cleaned.get(lineno, ""))
        if blanked is None:
            continue
        original = directive.match(line)
        found.append((lineno, blanked.group(1).strip(), original.group(1) if original else ""))
    return found


def citation(replacement: str) -> str:
    """The text a citation carries, with its string literals joined."""
    return "".join(_STRING_LITERAL.findall(replacement)).strip()


def structure_status(header: str, values: list[str]) -> tuple[list[str], str | None]:
    """One structure's status, and every way it fails to answer for it.

    The status is returned only when it is usable, so a structure whose header
    is at fault contributes nothing to the comparison against the
    documentation -- there is no claim there yet to agree or disagree with.
    """
    with open(header, "r", encoding="utf-8") as handle:
        source = handle.read()

    problems: list[str] = []
    declared = definitions(source, STATUS_MACRO)

    if not declared:
        return [
            f"defines no {STATUS_MACRO}, so it reaches the seam without saying whether "
            "hardware has verified it"
        ], None
    if len(declared) > 1:
        lines = ", ".join(str(lineno) for lineno, _, _ in declared)
        return [
            f"defines {STATUS_MACRO} {len(declared)} times (lines {lines}), so which it "
            "claims is unclear"
        ], None

    lineno, value, _ = declared[0]
    if value not in values:
        return [
            f"line {lineno}: claims '{value or '(nothing)'}', which is not one of the declared "
            f"values ({', '.join(values)})"
        ], None

    cited = definitions(source, EVIDENCE_MACRO)
    if value == HARDWARE_VERIFIED:
        if not cited:
            problems.append(
                f"line {lineno}: claims {HARDWARE_VERIFIED} and defines no {EVIDENCE_MACRO}, "
                "so nothing says what was run against what"
            )
        elif len(cited) > 1:
            lines = ", ".join(str(where) for where, _, _ in cited)
            problems.append(f"defines {EVIDENCE_MACRO} {len(cited)} times (lines {lines})")
        else:
            cited_at, _, replacement = cited[0]
            text = citation(replacement)
            if not _STRING_LITERAL.search(replacement):
                problems.append(
                    f"line {cited_at}: cites '{replacement.strip()}', which is not text this "
                    f"check or an adopter can read -- {EVIDENCE_MACRO} carries the citation as "
                    "a string"
                )
            elif text.lower() in EMPTY_CELLS:
                problems.append(
                    f"line {cited_at}: cites '{text}', which says nothing about what was run "
                    "against what, so the claim rests on confidence rather than on a bench"
                )
    elif cited:
        problems.append(
            f"line {cited[0][0]}: defines {EVIDENCE_MACRO} while claiming '{value}', which "
            "reads as verification the structure is not claiming"
        )

    return problems, value


def documented(path: str, values: list[str]) -> dict[str, list[tuple[int, str, str]]]:
    """Every documented status: name -> [(line, status, evidence), ...].

    A row is any table row whose second cell names a declared value. That is
    what lets the documentation carry other tables without this check having to
    know where the status table sits in it.

    Rows are collected rather than collapsed, because two rows for one
    structure are two published claims and one of them is wrong. Keeping only
    the last would resolve, silently, the case the sources refuse outright.
    """
    if not os.path.isfile(path):
        raise Uninspectable(f"no documentation at {path}")

    with open(path, "r", encoding="utf-8") as handle:
        lines = handle.read().splitlines()

    rows: dict[str, list[tuple[int, str, str]]] = {}
    for lineno, line in enumerate(lines, start=1):
        match = _TABLE_ROW.match(line)
        if match is None:
            continue
        cells = [cell.strip().strip("`").strip() for cell in match.group(1).split("|")]
        if len(cells) < 2 or cells[1] not in values:
            continue
        evidence = cells[2].strip("`").strip() if len(cells) > 2 else ""
        rows.setdefault(cells[0], []).append((lineno, cells[1], evidence))
    return rows


def documentation_problems(
    claimed: dict[str, str],
    present: set[str],
    rows: dict[str, list[tuple[int, str, str]]],
    path: str,
) -> list[str]:
    """Every disagreement between the sources and the shared documentation.

    `claimed` carries the structures whose own header answered usably, which
    are the ones there is a claim to compare. `present` carries every structure
    in the tree, so a row for a structure whose header is separately at fault is
    not also reported as documenting one that does not exist.
    """
    problems: list[str] = []

    if not rows:
        return [
            f"{path} documents no structure's support status, so an adopter choosing one reads "
            "nothing about whether it has been verified"
        ]

    for name, entries in sorted(rows.items()):
        if len(entries) > 1:
            lines = ", ".join(str(lineno) for lineno, _, _ in entries)
            problems.append(
                f"{path}: documents the '{name}' structure {len(entries)} times (lines {lines}), "
                "so which status an adopter reads depends on where they stop"
            )

    for name, status in sorted(claimed.items()):
        entries = rows.get(name)
        if not entries:
            problems.append(f"{path}: no row for the '{name}' structure, which claims {status}")
            continue
        if len(entries) > 1:
            continue
        lineno, documented_status, evidence = entries[0]
        if documented_status != status:
            problems.append(
                f"{path}:{lineno}: documents the '{name}' structure as {documented_status} "
                f"while its own header claims {status}"
            )
        elif status == HARDWARE_VERIFIED and evidence.lower() in EMPTY_CELLS:
            problems.append(
                f"{path}:{lineno}: documents the '{name}' structure as {status} and cites "
                "nothing an adopter can read"
            )

    for name, entries in sorted(rows.items()):
        if name not in present:
            lineno, status, _ = entries[0]
            problems.append(
                f"{path}:{lineno}: documents a '{name}' structure as {status}, and the tree has "
                "no such structure"
            )

    return problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plant-root", required=True, help="the directory the structures live in")
    parser.add_argument(
        "--include-dir", required=True, help="the directory the seam's own headers live in"
    )
    parser.add_argument(
        "--documentation",
        required=True,
        help="the shared documentation an adopter reads before choosing a structure",
    )
    args = parser.parse_args(argv)

    if not os.path.isdir(args.plant_root):
        # Distinct from an empty plant root only in how it happened; both leave
        # the check with no structure to have inspected.
        print(f"check_support_status: no plant root at {args.plant_root}", file=sys.stderr)
        return 2

    vocabulary_path = os.path.join(args.include_dir, VOCABULARY_HEADER)
    try:
        values = vocabulary(vocabulary_path)
        rows = documented(args.documentation, values)
    except Uninspectable as absent:
        print(f"check_support_status: {absent}", file=sys.stderr)
        return 2

    failed = False

    problems = vocabulary_problems(values)
    if problems:
        failed = True
        print(
            "check_support_status: the vocabulary no longer draws its line at whether hardware "
            "has verified the structure",
            file=sys.stderr,
        )
        for problem in problems:
            print(f"  {vocabulary_path}: {problem}", file=sys.stderr)

    structures = discover(args.plant_root, args.include_dir)
    if not structures:
        # A tree with no structures is a tree this check establishes nothing
        # on. Reporting success would say every structure has answered.
        print(
            f"check_support_status: no structures under {args.plant_root} -- there is nothing "
            "to have carried a status",
            file=sys.stderr,
        )
        return 2

    claimed: dict[str, str] = {}
    for structure in structures:
        problems, status = structure_status(structure.header, values)
        if problems:
            failed = True
            print(
                f"check_support_status: the '{structure.name}' structure does not carry a "
                "usable support status",
                file=sys.stderr,
            )
            for problem in problems:
                print(f"  {structure.header}: {problem}", file=sys.stderr)
        if status is not None:
            claimed[structure.name] = status

    problems = documentation_problems(
        claimed, {structure.name for structure in structures}, rows, args.documentation
    )
    if problems:
        failed = True
        print(
            "check_support_status: the documentation and the structures do not agree",
            file=sys.stderr,
        )
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)

    if failed:
        return 1

    summary = ", ".join(f"{name} {status}" for name, status in sorted(claimed.items()))
    print(
        f"check_support_status: all {len(claimed)} structure(s) carry a declared support status, "
        f"documented in {args.documentation} ({summary})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
