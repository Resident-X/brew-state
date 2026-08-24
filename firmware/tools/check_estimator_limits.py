#!/usr/bin/env python3
"""Fail when a machine would be built with a sensor channel nobody bounded.

A reading arrives through the hardware seam carrying a status that says whether
a sample was obtained, and if not, whether anything is fitted to have sampled.
It does not say whether the sample is possible, and those are different
failures with opposite consequences: a channel that reports nothing costs a
correction, and a channel that reports nine hundred degrees drags the
reconstruction toward a state the machine cannot be in. The second has no
symptom -- the estimator goes on running and the residual it reports looks
ordinary -- so what a reading may plausibly be is declared per machine, beside
the description of that machine, and this is the check that the declaration is
complete.

The failure worth preventing is not a wrong bound. It is a missing one. A
channel with no line would default to trusted, and a default reads as covered to
everybody who looks at the file: nothing about the running machine distinguishes
a channel nobody thought about from one somebody decided was fine. So every
structure in the tree carries its own declaration rather than inheriting one,
every channel the hardware seam reports carries a line in it, and a declaration
that leaves one out fails the build rather than the machine.

What it does not judge is whether a declared number is right. That is a review
question, and on a machine that has never been on a bench there is no measurement
to check it against; the origin each line carries is what makes the answer
challengeable by a reader instead.

Usage: check_estimator_limits.py --include-dir <dir> --plant-root <dir>
                                 --params-dir <dir>
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check_parameter_origins import (  # noqa: E402
    _DEFINE_STRING,
    enumerators,
    load_vocabulary,
    read,
)
from structure_symbols import discover  # noqa: E402

#: Where the shape of a limits declaration is declared, and the enum whose
#: members every declaration has to account for.
VOCABULARY_HEADER = "estimator_limits.h"
CHANNEL_HEADER = "hw_interface.h"
CHANNEL_TYPE = "hw_sensor_channel_t"

#: The enumerator that counts the channels rather than being one of them.
CHANNEL_COUNT = "HW_SENSOR_CHANNEL_COUNT"

#: The two figures a declaration carries that are not about any one channel.
#: Named here rather than discovered, for the reason the origin check names its
#: kinds rather than reading them: a check that took its list of what must be
#: declared from the same file it is inspecting would agree with any edit to it.
TOLERANCE_WINDOW = "ESTIMATOR_LIMITS_TOLERANCE_WINDOW_WORD"
EXCURSION_BOUND = "ESTIMATOR_LIMITS_EXCURSION_BOUND_WORD"
SCALAR_MACROS = (TOLERANCE_WINDOW, EXCURSION_BOUND)

#: What a limits declaration is called for the structure it belongs to.
LIMITS_SUFFIX = ".limits"

class Shape:
    """What a declaration must account for, read out of the headers."""

    def __init__(self, channels: dict[str, str], scalars: dict[str, str], marker: str):
        self.channels = channels
        self.scalars = scalars
        self.marker = marker

    @property
    def names(self) -> list[str]:
        return list(self.channels.values()) + list(self.scalars.values())


def load_shape(include_directory: str) -> tuple[Shape | None, list[str]]:
    """The words every declaration accounts for, and what is wrong with the headers.

    The channels come from the hardware seam and the words from the limits
    header, and the two are compared rather than one being trusted. A channel
    added to the seam and not given a word here would otherwise be a channel no
    declaration could name and no check could miss.
    """
    seam_path = os.path.join(include_directory, CHANNEL_HEADER)
    vocabulary_path = os.path.join(include_directory, VOCABULARY_HEADER)
    for path in (seam_path, vocabulary_path):
        if not os.path.isfile(path):
            return None, [f"no {os.path.basename(path)} at {path}, so nothing can be inspected"]

    channels = [
        name for name in enumerators(read(seam_path), CHANNEL_TYPE) if name != CHANNEL_COUNT
    ]
    if not channels:
        return None, [
            f"{seam_path}: declares no sensor channels, so this check would inspect every "
            "declaration against nothing and report success having established nothing"
        ]

    source = read(vocabulary_path)
    strings = dict(_DEFINE_STRING.findall(source))
    problems: list[str] = []

    worded: dict[str, str] = {}
    for channel in channels:
        # HW_SENSOR_BREW_TEMPERATURE is written as ESTIMATOR_LIMITS_BREW_TEMPERATURE_WORD.
        macro = "ESTIMATOR_LIMITS_" + channel[len("HW_SENSOR_") :] + "_WORD"
        if macro not in strings:
            problems.append(
                f"{vocabulary_path}: {channel} is a channel the estimator corrects against and "
                f"declares no word ({macro}), so no declaration can name it and no check of a "
                "declaration would notice it missing"
            )
        else:
            worded[channel] = strings[macro]

    scalars: dict[str, str] = {}
    for macro in SCALAR_MACROS:
        if macro not in strings:
            problems.append(f"{vocabulary_path}: {macro} declares no word")
        else:
            scalars[macro] = strings[macro]

    marker = strings.get("ESTIMATOR_LIMITS_RANGE_MARKER")
    if marker is None:
        problems.append(
            f"{vocabulary_path}: no range marker is declared, so a channel's low cannot be "
            "told from its high"
        )

    if problems:
        return None, problems
    return Shape(worded, scalars, str(marker)), []


def inspect(path: str, shape: Shape, origin_words: frozenset[str], exemption: str) -> list[str]:
    """Everything wrong with one declaration."""
    problems: list[str] = []
    seen: dict[str, int] = {}
    unaccounted: list[tuple[int, str]] = []
    exempt = False

    for number, raw in enumerate(read(path).splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("@"):
            if line[1:].strip() != exemption:
                problems.append(f"{path}:{number}: '{line}' is not a statement a declaration may make")
            else:
                exempt = True
            continue

        name, separator, rest = line.partition("=")
        name = name.strip()
        if not separator or not name:
            problems.append(f"{path}:{number}: '{line}' is not name = value")
            continue
        if name not in shape.names:
            problems.append(
                f"{path}:{number}: '{name}' is not something a limits declaration carries"
            )
            continue
        if name in seen:
            problems.append(
                f"{path}:{number}: '{name}' was already given on line {seen[name]}, so which "
                "of the two the machine runs on is not settled"
            )
            continue
        seen[name] = number

        figures, marker, account = rest.partition("@")
        if name in shape.channels.values():
            low, ranged, high = figures.partition(shape.marker)
            if not ranged:
                problems.append(
                    f"{path}:{number}: '{name}' carries no {shape.marker}, so it gives one "
                    "figure where a channel's admissible span needs two"
                )
                continue
            try:
                low_value = int(low.strip())
                high_value = int(high.strip())
            except ValueError:
                problems.append(f"{path}:{number}: '{name}' does not carry two whole numbers")
                continue
            if not all(-2147483648 <= figure <= 2147483647 for figure in (low_value, high_value)):
                problems.append(
                    f"{path}:{number}: '{name}' carries a bound outside what the loader can "
                    "hold, so this would pass the build and be refused by the machine"
                )
                continue
            if low_value >= high_value:
                problems.append(
                    f"{path}:{number}: '{name}' declares a low of {low_value} that is not "
                    f"below its high of {high_value}, so it admits no reading at all"
                )
        else:
            try:
                figure = int(figures.strip())
            except ValueError:
                problems.append(f"{path}:{number}: '{name}' does not carry a whole number")
                continue

            # The same span the loader admits, checked here rather than left to
            # the machine. A declaration this gate passes and the loader then
            # refuses is the build reporting success over a machine that will
            # not come up, which is precisely what the gate exists to prevent.
            admissible = (0, 4294967295) if name == shape.scalars[TOLERANCE_WINDOW] else (1, 2147483647)
            if not admissible[0] <= figure <= admissible[1]:
                problems.append(
                    f"{path}:{number}: '{name}' carries {figure}, which is outside the "
                    f"{admissible[0]} to {admissible[1]} the loader admits -- so this would "
                    "pass the build and be refused by the machine"
                )
                continue

        if marker:
            kind = account.split()[0] if account.split() else ""
            if kind not in origin_words:
                problems.append(
                    f"{path}:{number}: '{name}' records its origin as '{kind}', which is not "
                    f"one of {sorted(origin_words)}"
                )
            elif not account.split()[1:]:
                problems.append(
                    f"{path}:{number}: '{name}' records a kind and no account of what the "
                    "figure was arrived at from, so it can be neither reproduced nor challenged"
                )
        else:
            unaccounted.append((number, name))

    for name in shape.names:
        if name not in seen:
            problems.append(
                f"{path}: '{name}' carries no line, so it would take whatever a default "
                "happened to be -- which is the one state nothing about the running machine "
                "would distinguish from a figure somebody chose"
            )

    # Judged after the whole file is read, because the statement that exempts a
    # declaration from accounting for its figures is a statement about the file
    # and may be written below the figures it exempts.
    if not exempt:
        for number, name in unaccounted:
            problems.append(
                f"{path}:{number}: '{name}' carries no origin, and this declaration does not "
                f"state that it '{exemption}', so it is required to account for every figure "
                "it carries"
            )

    return problems


def check(include_directory: str, plant_root: str, params_directory: str) -> tuple[list[str], list[str]]:
    """Every declaration inspected, and everything wrong across all of them."""
    shape, problems = load_shape(include_directory)
    if shape is None:
        return problems, []

    vocabulary, origin_problems = load_vocabulary(include_directory)
    if vocabulary is None:
        return origin_problems, []

    structures = [structure.name for structure in discover(plant_root, include_directory)]
    if not structures:
        return [
            f"no plant structure under {plant_root}, so this check would inspect no "
            "declaration and report success having established nothing"
        ], []

    inspected: list[str] = []
    for structure in sorted(structures):
        path = os.path.join(params_directory, structure + LIMITS_SUFFIX)
        if not os.path.isfile(path):
            problems.append(
                f"the '{structure}' structure ships no {structure}{LIMITS_SUFFIX}, so a build "
                "against it has nothing saying what a reading off that machine may plausibly "
                "be -- and every channel would be believed whatever it reported"
            )
            continue
        inspected.append(path)
        problems.extend(inspect(path, shape, vocabulary.words, vocabulary.exemption))

    return problems, inspected


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-dir", required=True, help="where the seam's headers live")
    parser.add_argument("--plant-root", required=True, help="where the structures live")
    parser.add_argument("--params-dir", required=True, help="where the declarations live")
    args = parser.parse_args(argv)

    shape, shape_problems = load_shape(args.include_dir)
    if shape is None:
        print("check_estimator_limits: the declared shape could not be read", file=sys.stderr)
        for problem in shape_problems:
            print(f"  {problem}", file=sys.stderr)
        return 2

    problems, inspected = check(args.include_dir, args.plant_root, args.params_dir)
    if problems:
        print(
            "check_estimator_limits: a machine would be built with a channel nobody bounded",
            file=sys.stderr,
        )
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print(
        f"check_estimator_limits: {len(inspected)} declaration(s) bound every channel the "
        "estimator corrects against"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
