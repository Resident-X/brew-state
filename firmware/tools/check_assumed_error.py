#!/usr/bin/env python3
"""Fail when a parameter description carries a value with no assumed error.

The design is established against a description of a machine nobody has
measured, and every value in it is wrong by some amount. That is not a defect:
until the machine is on a bench, a figure read off a diagram or estimated from a
casting is the best there is. What is a defect is the amount going unstated,
because the margins the design holds are then sized against an uncertainty that
exists only in the head of whoever chose them. Nobody else can check it, the
author cannot check it a year later, and nothing can be revisited when
identification lands better or worse than it was sized for.

A convention that depends on remembering is not a discipline. An assumed error
decays at exactly the moment it matters most -- under time pressure, adding one
more coefficient -- and the failure leaves no trace at the point of use, because
a bare number reveals nothing about whether anyone ever decided how far out it
might be. So this runs as part of the build rather than as something a reviewer
might notice.

Four things are checked, because each can pass while another is broken:

  * the vocabulary is one a description can actually be written in -- the marker
    exists, and it is not the marker that already introduces something else. Two
    annotations sharing one marker would not be two annotations; the first would
    swallow the second and every value would read as accounted for,
  * every coefficient a structure requires appears in each description that
    claims a machine, and carries an assumed error against it,
  * the figure is one a value can be out by: a number, not negative, and finite.
    A marker with nothing behind it is the worst of the three, because it reads
    as declared to anyone skimming and says nothing at all, and
  * something was actually inspected. A tree in which every description exempts
    itself has established nothing, and neither has one with no descriptions in
    it at all.

The exemption is the one the origin check already honours, read from the same
vocabulary: a description that says in the file that it describes no real
machine is not asked how wrong it is, because there is nothing for it to be
wrong about. It follows what a description claims rather than which structure it
belongs to.

Judging whether a declared error is honest is a review question and is not
attempted here, and comparing one against a figure measured on the machine is
characterisation work that has not happened. What the build can establish is
that a figure exists, that it is a figure, and that it is one somebody could
have meant.

Usage: check_assumed_error.py --plant-root <dir> --include-dir <dir>
                              --params-dir <dir>
"""

from __future__ import annotations

import argparse
import math
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# The origin check owns the reading of a description's structure -- which files
# belong to a structure, which coefficients that structure requires, and how a
# description says it describes no machine. Reading any of that a second way
# here would be a second opinion about what a description is, and the two would
# eventually disagree about which files were inspected at all.
from check_parameter_origins import (  # noqa: E402
    _DEFINE_CHAR,
    descriptions_for,
    load_vocabulary,
    read,
    required_coefficients,
)
from structure_symbols import discover  # noqa: E402

#: The header the assumed-error marker is declared in, relative to the includes.
BUDGET_HEADER = "plant_budget.h"

#: The macro declaring what introduces an assumed error against a value.
MARKER_MACRO = "PLANT_BUDGET_MARKER"


def load_marker(include_directory: str, origin_marker: str) -> tuple[str | None, list[str]]:
    """Read what introduces an assumed error, and say what is wrong if it cannot."""
    path = os.path.join(include_directory, BUDGET_HEADER)
    if not os.path.isfile(path):
        return None, [
            f"no assumed-error vocabulary at {path}, so no description can be inspected"
        ]

    characters = dict(_DEFINE_CHAR.findall(read(path)))
    marker = characters.get(MARKER_MACRO)
    if marker is None:
        return None, [
            f"{path}: declares no {MARKER_MACRO}, so an assumed error cannot be recognised"
        ]
    if marker == origin_marker:
        return None, [
            f"{path}: declares {MARKER_MACRO} as '{marker}', which is already what introduces an "
            "origin. One marker cannot introduce two annotations -- the account of an origin runs "
            "to the end of the line, so it would swallow every assumed error and every value "
            "would read as carrying one"
        ]
    return marker, []


class Description:
    """One description, read for what it says about how wrong its values are."""

    def __init__(self, path: str, vocabulary, marker: str):
        self.path = path
        self.exempt = False
        #: Coefficient name -> (line number, the text after the marker or None).
        self.values: dict[str, tuple[int, str | None]] = {}

        for number, raw in enumerate(read(path).splitlines(), start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith(vocabulary.marker):
                # A statement the description makes about itself. Only the
                # exemption is of interest here; a statement it is not entitled
                # to make is the origin check's finding, and reporting it twice
                # would have one edit clear two failures that are one failure.
                if line[1:].strip() == vocabulary.exemption:
                    self.exempt = True
                continue
            if "=" not in line:
                continue
            name, remainder = line.split("=", 1)
            #
            # The annotations are read in the order the grammar fixes: an
            # origin's account is free text running to the end of the line, so
            # a marker inside it is prose rather than a second annotation. A
            # description writing the two the other way round therefore reads
            # here as carrying no assumed error, which is what it is: the figure
            # is inside somebody's sentence about a service manual.
            #
            accounted = remainder.split(vocabulary.marker, 1)[0]
            declared: str | None = None
            if marker in accounted:
                declared = accounted.split(marker, 1)[1].strip()
            self.values[name.strip()] = (number, declared)


# The numerals `strtof` accepts, and nothing else.
#
# The loader reads a figure with `strtof` into a C float; this check reads the
# same figure with Python's `float`. The two are not the same grammar, and the
# places they disagree are the places a description passes the gate and is then
# refused by the machine that has to run it -- which is the one failure this
# check exists to prevent. Python accepts digit separators (`0_2` is two), and
# accepts any Unicode decimal digit (a full-width `1` is one); `strtof` accepts
# neither. `strtof` accepts a hexadecimal significand (`0x1p-3` is an eighth);
# Python does not.
#
# So the token is matched against the C grammar before it is converted, rather
# than converted and then judged. Matching first is what makes the two agree on
# what a numeral even is, instead of agreeing only about the numbers they both
# happen to parse. `inf` and `nan` are matched here because `strtof` accepts
# them too -- they are refused below, with a reason that says what is wrong with
# them rather than that they could not be read.
_C_NUMERAL = re.compile(
    r"""^[+-]?(
          (?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?
        | 0[xX](?:[0-9a-fA-F]+\.?[0-9a-fA-F]*|\.[0-9a-fA-F]+)(?:[pP][+-]?[0-9]+)?
        | (?:inf|infinity|nan)
        )$""",
    re.VERBOSE | re.IGNORECASE,
)


def inadmissible(figure: str) -> str | None:
    """Why this text is not an error a value could be out by, or None if it is."""
    if not figure:
        return (
            "carries the marker with no figure behind it, which reads as declared and says "
            "nothing. Give the fraction of the value the design assumes it may be out by"
        )
    if _C_NUMERAL.match(figure) is None:
        return (
            f"declares its assumed error as '{figure}', which is not a number the machine's own "
            "loader would read. A digit separator, or a digit that is not one of the ten this "
            "grammar spells, reads here and is refused there -- so it is refused here too"
        )
    fraction = float.fromhex(figure) if _is_hexadecimal(figure) else float(figure)
    if math.isnan(fraction):
        return (
            f"declares its assumed error as '{figure}', which is not a number at all -- what a "
            "spreadsheet that divided by zero emits, and what every comparison against it "
            "silently answers false to"
        )
    if fraction < 0.0:
        return (
            f"declares its assumed error as '{figure}'. The figure is how far either side of the "
            "value the machine may sit, and there is no distance shorter than none"
        )
    if math.isinf(fraction):
        return (
            f"declares its assumed error as '{figure}'. A value that may be wrong by an unbounded "
            "amount is one nothing can be designed against, which is a finding about the "
            "description rather than a wide margin"
        )
    if not _representable(fraction):
        return (
            f"declares its assumed error as '{figure}', which is a real number but not one the "
            "single precision the model is carried in can hold. It arrives at the loader as "
            "infinity and is refused there, so it is refused here rather than passing a gate the "
            "machine then fails"
        )
    return None


def _is_hexadecimal(figure: str) -> bool:
    """Whether this numeral is the hexadecimal form, which `float` cannot read."""
    return figure[1:3].lower().startswith("0x") or figure[:2].lower() == "0x"


def _representable(fraction: float) -> bool:
    """Whether this number survives being narrowed to the width the model uses."""
    try:
        return not math.isinf(struct.unpack("<f", struct.pack("<f", fraction))[0])
    except OverflowError:
        return False


def inspect(description: Description, coefficients: list[str]) -> list[str]:
    """What is wrong with one description that claims a machine."""
    problems: list[str] = []
    for coefficient in coefficients:
        if coefficient not in description.values:
            problems.append(
                f"{description.path}: '{coefficient}' is required by the structure and is not "
                "in this description"
            )
            continue
        number, declared = description.values[coefficient]
        if declared is None:
            problems.append(
                f"{description.path}:{number}: '{coefficient}' carries no assumed error. Record "
                "how far out the design is entitled to assume this value may be, as a fraction "
                "of it"
            )
            continue
        wrong = inadmissible(declared)
        if wrong is not None:
            problems.append(f"{description.path}:{number}: '{coefficient}' {wrong}")
    return problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plant-root", required=True, help="the directory the structures live in")
    parser.add_argument("--include-dir", required=True, help="the directory the seam headers are in")
    parser.add_argument("--params-dir", required=True, help="the directory the descriptions are in")
    args = parser.parse_args(argv)

    vocabulary, problems = load_vocabulary(args.include_dir)
    if vocabulary is None:
        for problem in problems:
            print(f"check_assumed_error: {problem}", file=sys.stderr)
        return 2

    marker, problems = load_marker(args.include_dir, vocabulary.marker)
    if marker is None:
        for problem in problems:
            print(f"check_assumed_error: {problem}", file=sys.stderr)
        return 2

    if not os.path.isdir(args.params_dir):
        print(f"check_assumed_error: no descriptions at {args.params_dir}", file=sys.stderr)
        return 2

    structures = discover(args.plant_root, args.include_dir)
    if not structures:
        print(
            f"check_assumed_error: no structures under {args.plant_root}, so nothing declares "
            "which coefficients a description owes an assumed error for",
            file=sys.stderr,
        )
        return 2

    findings: list[str] = []
    inspected = 0
    seen_any_description = False

    for structure in structures:
        directory = os.path.join(args.plant_root, structure.name)
        coefficients = required_coefficients(directory)
        if not coefficients:
            findings.append(
                f"{directory}: declares no parameter table, so what its descriptions have to "
                "state an assumed error for cannot be established"
            )
            continue
        for path in descriptions_for(structure.name, args.params_dir):
            seen_any_description = True
            description = Description(path, vocabulary, marker)
            if description.exempt:
                continue
            findings.extend(inspect(description, coefficients))
            inspected += 1

    if not seen_any_description:
        print(
            f"check_assumed_error: no descriptions under {args.params_dir} belong to any "
            "structure, so nothing was inspected",
            file=sys.stderr,
        )
        return 1
    if inspected == 0:
        print(
            "check_assumed_error: every description exempts itself, so no value's assumed error "
            "was inspected. A tree in which nothing claims a machine establishes nothing about "
            "how wrong the description the design is reasoned against may be",
            file=sys.stderr,
        )
        return 1

    for finding in findings:
        print(f"check_assumed_error: {finding}", file=sys.stderr)
    if findings:
        return 1

    print(
        f"check_assumed_error: {inspected} description(s) claiming a machine, every value "
        "carrying the error the design assumes for it"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
