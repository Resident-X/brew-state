#!/usr/bin/env python3
"""Fail when a figure the control logic rests on is not accounted for.

The control law rests on numbers nobody has measured: a proportional gain, an
integral gain, a feedforward gain, and the bands a delivery is held to. Each is
a choice somebody made against the reference description and the behaviour asked
of the loop, and a choice nobody wrote down is indistinguishable from a number
that was always there. The failure this prevents is not a wrong figure -- no
reading of the source can tell a good gain from a bad one -- but a figure with
nothing asserting it, which is the state a load-bearing number is in just before
everybody starts treating it as settled.

Three things are checked, because each can pass while another is broken:

  * every definition the control logic carries accounts for itself, in the
    control declaration or in the cadence declaration beside it. A gain added
    during a tuning
    session, or a bound typed into a parser, arrives as a bare number otherwise
    -- and the tree goes on reading as fully accounted for, because a
    declaration listing four figures looks the same whether the source has four
    or five,
  * every figure accounted for has exactly one home. A figure defined nowhere
    means the declaration describes software that does not exist; a figure
    defined twice stops agreeing with itself the first time either site is
    touched, and nothing about the running machine says which one it ran on,
  * every band a delivery is held to is declared, carries an origin, and has
    not grown a second home in the source. They are the figures here that live
    as data rather than as definitions, because they are the criteria
    trajectories are accepted against and a requirement that can only be varied
    by recompiling is one nobody varies. A definition spelling one would go on
    reading as declared in the tolerance file while the software held deliveries
    to the other one.

What a figure should be is not checked. Whether thirty permille per kelvin is
the right proportional gain for this machine is a question no reading of the
source can settle, and the account each figure carries is what lets a reader
challenge it instead.

The two scans have deliberately different reach. Which figures the control law
rests on is a question about the control logic, so accounting is asked of those
directories alone -- a constant in a plant structure is a coefficient of a
machine and answers for itself elsewhere. Whether a band has grown a second home
is a question about the whole tree: a band spelled anywhere, in an entry point
as readily as in the loop, is the copy the software would hold deliveries to
while the declaration went on reading as authoritative.

A header is part of the source it declares, and is named one at a time rather
than swept up. What the delivery loader bounds a copy of a band's name with sits
in the shared include directory because a caller has to see it, not because it
belongs with the seam vocabularies beside it -- and a bound of exactly that kind
inside the loader's own source is accounted for here already, so leaving the
header out would make the same figure answerable or not according to which file
it was typed into. The include directory as a whole is nevertheless not
scanned: it also carries the actuation full scale and the bounds the plant
vocabulary puts on a parameter's name, which are figures of a machine and of
another loader and are answered for under their own checks. Asking this
declaration for those would draw the line where a file happens to sit rather
than where the figure belongs, and would collect accounts here that the reader
who could challenge them will never look at.

Usage: check_control_declaration.py --include-dir <dir> --source-dir <dir>
                                    [--source-header <file>]
                                    --declaration <file> --tolerance <file>
                                    --tree-dir <dir> [--tree-dir <dir>]
"""

from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_cadence_declaration  # noqa: E402
from check_parameter_origins import load_vocabulary  # noqa: E402

#: Where the figures that answer for the rate the loop runs at account for
#: themselves, for a message that has to tell a reader which file to go and read.
CADENCE_DECLARATION = "params/cadence.declaration"

#: Figures the control logic defines that account for themselves in another
#: declaration, and where. The cadence figures answer for the rate the loop runs
#: at rather than for what it does at that rate, and they are accounted for
#: beside each other where that question is answered.
#:
#: Which macros those are is taken from the check that owns them rather than
#: restated here. This file's own argument is that a fact written down twice
#: stops agreeing with itself the first time either copy is touched, and a list
#: of cadence macros typed into this module would be exactly that copy: it would
#: go on excusing a macro the cadence check had been taught to call something
#: else, and the figure would be accounted for nowhere while both checks
#: reported success.
#:
#: The cadence declaration itself is still not read, which is a separate point.
#: It names its figures in its own vocabulary rather than by macro, and a check
#: that translated between the two would be asserting a mapping nothing else in
#: the tree holds.
#:
#: Whether each is really accounted for, and really has one home, is the cadence
#: check's question and not this one's -- one figure, one check. What is enforced
#: here is only that it is not answered for twice.
ACCOUNTED_ELSEWHERE = {
    macro: CADENCE_DECLARATION for macro in check_cadence_declaration.COMPILED_IN.values()
}

#: The bands the tolerance declaration is required to carry, and the fragment of
#: an identifier that would spell one if somebody defined it in the source
#: instead. Named here rather than discovered, for the reason the origin check
#: names its kinds: a check reading its list of what must be declared out of the
#: thing it is inspecting would agree with any edit to it.
#: Each band's entry carries the identifier fragment that would spell it if
#: somebody defined it in the source instead, the word for the unit it is stated
#: in, and the widest half-width it may be declared at.
#:
#: The unit and the bound restate what the loader in
#: src/delivery/delivery_tolerance.c holds. That restatement is deliberate and is
#: the same one this module already makes about whole numbers and about zero: the
#: point of the gate is to refuse at build time exactly what the machine would
#: refuse at start-up, and a gate that had to be told the answer by the thing it
#: is checking could not fail before the machine did. The two are held together
#: by the tests below, which run this check against declarations the C loader is
#: separately required to refuse.
BANDS = {
    "brew-temperature-band": ("TEMPERATURE_BAND", "milli-c", 20000),
    "flow-departure-band": ("FLOW_DEPARTURE_BAND", "milli-ml-s", 7000),
    "post-draw-match-band": ("POST_DRAW_MATCH_BAND", "milli-c", 2000),
}

#: What the source is scanned for.
#:
#: Blanks are spelled as spaces and tabs rather than as \s, and the value as
#: anything but a newline, because \s matches a line ending: against a valueless
#: definition followed immediately by another -- an include guard above the
#: figure it guards -- the name would take the guard and the value would take
#: the whole of the next line.
#:
#: A value continued with a backslash is taken whole, all the same, because the
#: preprocessor takes it whole. A definition whose name sits on one line and
#: whose figure sits on the next reads to a scan that stops at the first line
#: ending as a value of one backslash: no digit, no figure, nothing to account
#: for -- while the number itself is compiled in and load-bearing exactly as if
#: it had been written on one line. That is the sharpest way past this check
#: there is, because it needs no intent: a long expression wrapped for the sake
#: of the line length would escape it just as completely as one wrapped to hide.
_DEFINE = re.compile(
    r"^[ \t]*#[ \t]*define[ \t]+([A-Za-z_][A-Za-z0-9_]*)[ \t]+"
    r"((?:[^\n]*\\\n)*[^\n]+?)[ \t]*$",
    re.MULTILINE,
)

_DIGIT = re.compile(r"[0-9]")

#: A comment inside a definition's value, in either spelling, including one left
#: unterminated by the end of the value the scan took.
_COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*|/\*.*", re.DOTALL)

#: What a band may be written as. Spelled here rather than left to the integer
#: parser, which accepts separating underscores and a leading plus that the
#: loader reading this same file in C does not, and would let a figure through
#: the gate that the machine then refuses to start on.
_WHOLE_NUMBER = re.compile(r"^-?[0-9]+$")

_SOURCE_SUFFIXES = (".c", ".h")


def carries_a_figure(value: str) -> bool:
    """Whether a definition introduces a number of its own.

    A definition built only out of other names and operators introduces no
    figure: it restates ones that are accounted for already, and requiring a
    second account for it would ask somebody to write down where a subtraction
    came from. A definition carrying a digit is a number somebody chose, whether
    it stands alone or sits inside an expression.

    What a comment beside the value says is not part of the value. A definition
    written as a sum of names that are accounted for already, with a note after
    it saying what the sum comes to, carries a digit and introduces no figure,
    and asking for an account of it would make this check answer for prose --
    the one place in a source file where a number is not a number the software
    runs on. So comments are taken off before the digit is looked for. Nothing
    hides behind that: a figure spelled inside a comment is not compiled, and
    one spelled outside a comment is still found however much commentary sits
    beside it.

    A definition whose value is a string is a word rather than a figure -- the
    vocabulary headers spell each of these to name it in a declaration -- so
    those are not what this is looking for.
    """
    if value.startswith('"'):
        return False
    return _DIGIT.search(_COMMENT.sub(" ", value)) is not None


def definitions(*paths: str) -> dict[str, list[str]]:
    """Every figure-carrying definition in the given files, and the files defining each.

    A path is a directory to walk or a single file to read. The second form is
    what lets a header be asked the same question as the source it declares
    without the whole of a shared include directory being asked with it, which
    would collect accounts here for figures belonging to other people's checks.
    """
    found: dict[str, list[str]] = {}
    for path in paths:
        if os.path.isfile(path):
            files = [path]
        else:
            files = [
                os.path.join(root, name)
                for root, _, names in os.walk(path)
                for name in sorted(names)
                if name.endswith(_SOURCE_SUFFIXES)
            ]
        for source_path in files:
            with open(source_path, "r", encoding="utf-8") as handle:
                source = handle.read()
            for macro, value in _DEFINE.findall(source):
                if not carries_a_figure(value):
                    continue
                found.setdefault(macro, []).append(source_path)
    return found


def accounted_in(path: str, origin_words: frozenset[str]) -> tuple[dict[str, int], list[str]]:
    """What a declaration accounts for, and everything wrong with how it does.

    A line is a figure's name, the origin marker, a kind, and an account. It
    carries no value: the value lives at the figure's one home in the source,
    and writing it here as well would be the second site this check exists to
    prevent -- the one that goes stale silently, because nothing compiles a
    declaration.
    """
    problems: list[str] = []
    accounted: dict[str, int] = {}

    with open(path, "r", encoding="utf-8") as handle:
        lines = handle.read().splitlines()

    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        name, marker, rest = line.partition("@")
        name = name.strip()
        if not name:
            problems.append(f"{path}:{number}: '{line}' names no figure")
            continue
        if "=" in name:
            problems.append(
                f"{path}:{number}: '{name}' carries a value. The value lives at the figure's "
                "one home in the source, and a second copy here is the site that goes stale "
                "silently, because nothing compiles this file"
            )
            continue
        if name in accounted:
            problems.append(
                f"{path}:{number}: '{name}' was already accounted for on line {accounted[name]}"
            )
            continue
        accounted[name] = number

        if not marker:
            problems.append(
                f"{path}:{number}: '{name}' records no origin, so it is a number with nothing "
                "asserting it -- which is the shape one takes just before it is treated as "
                "settled"
            )
            continue

        words = rest.split()
        kind = words[0] if words else ""
        if kind not in origin_words:
            problems.append(
                f"{path}:{number}: '{name}' records its origin as '{kind}', which is not one "
                f"of {sorted(origin_words)}"
            )
        elif not words[1:]:
            problems.append(
                f"{path}:{number}: '{name}' records a kind and no account of what the figure "
                "was arrived at from, so it can be neither reproduced nor challenged"
            )

    return accounted, problems


def homes(accounted: dict[str, int], defined: dict[str, list[str]]) -> list[str]:
    """Everything wrong with where the control logic's figures live."""
    problems: list[str] = []

    for macro in sorted(defined):
        if macro in ACCOUNTED_ELSEWHERE:
            continue
        if macro not in accounted:
            problems.append(
                f"{macro} is defined in {', '.join(sorted(defined[macro]))} and accounts for "
                "itself nowhere. A figure the control law rests on with nothing asserting it "
                "cannot be challenged, because there is nothing to challenge it against"
            )

    for figure in sorted(accounted):
        if figure in ACCOUNTED_ELSEWHERE:
            problems.append(
                f"'{figure}' is accounted for here and in {ACCOUNTED_ELSEWHERE[figure]}. Two "
                "accounts of one figure are two answers to the question a declaration exists "
                "to answer, and they will eventually disagree about which is current"
            )
            continue
        where = defined.get(figure, [])
        if not where:
            problems.append(
                f"'{figure}' is accounted for and defined nowhere, so the declaration "
                "describes a figure the software does not have"
            )
        elif len(where) > 1:
            problems.append(
                f"{figure} is defined in {', '.join(sorted(where))}. A figure spelled in two "
                "places stops agreeing with itself the first time either is touched, and "
                "nothing about the running machine says which one it ran on"
            )

    return problems


def unusable_band(name: str, figure: str) -> str | None:
    """Why a declared band is not a distance a delivery could be held to, if it is not.

    The figure is read here rather than merely found to be present, because what
    this gate reports is that the band is declared -- and a tolerance file saying
    `wide`, or `0`, or `-100`, carries a band that reads as declared to everybody
    who sees that success line and is refused by the loader the moment the
    machine is switched on. A gate that passes on a declaration the software will
    not accept is worse than no gate at all: it moves the discovery from the
    build, where somebody is looking at the file and can fix it, to start-up,
    where the machine simply does not come up and the file nobody is looking at
    is the reason.

    What is refused is what the loader refuses, for the reasons the loader gives.
    A value that is not a whole number followed by the word for its unit cannot
    be read at all. A unit that is not the one this build holds the band in is a
    figure measuring the wrong quantity, and reading it would hold deliveries to
    a band orders of magnitude away from the one declared. A band of nothing is
    not a tight tolerance but a criterion no delivery could ever meet, which is
    why the loader refuses it rather than holding every cup to it. A negative
    band is not a distance. And a band wider than its own bound has stopped being
    a criterion at all, because it accepts everything the machine can do.

    What a good band would be is still not judged. Whether one degree is the
    right window for this drink is a bench question, and the account beside the
    figure is what lets a reader challenge it.
    """
    _, expected_unit, widest = BANDS[name]

    parts = figure.split()
    if len(parts) != 2:
        return (
            f"'{name}' is declared as '{figure}', which is not a whole number followed by "
            f"the word for its unit. The loader refuses a band it cannot read, so this is "
            "a band reading as declared here on a machine that never comes up"
        )

    figure, unit = parts
    if unit != expected_unit:
        return (
            f"'{name}' is declared in '{unit}', but this build holds it in "
            f"'{expected_unit}'. A figure in the wrong unit is not a loose band, it is a "
            "band measuring the wrong quantity, and the loader refuses it rather than "
            "holding deliveries to it"
        )

    if not _WHOLE_NUMBER.match(figure):
        return (
            f"'{name}' is declared as '{figure}', which is not a whole number of "
            f"{expected_unit}. The loader refuses a band it cannot read, so this is a band "
            "reading as declared here on a machine that never comes up"
        )

    milli_c = int(figure)
    if milli_c == 0:
        return (
            f"'{name}' is declared as nothing at all. A band of zero is not a tight "
            "tolerance, it is a criterion no delivery could ever meet, and the loader "
            "refuses it rather than holding every cup to it"
        )
    if milli_c < 0:
        return (
            f"'{name}' is declared as {milli_c}. A band is a half-width rather than a "
            "direction, and there is no distance from the figure a band is measured "
            "against that is less than none"
        )
    if milli_c > widest:
        return (
            f"'{name}' is declared as {milli_c} {expected_unit}, which is wider than the "
            f"{widest} the loader admits for it. Past that a band has stopped being a "
            "criterion -- it accepts everything the machine can do -- so the loader "
            "refuses the declaration outright and a band nobody could exceed becomes a "
            "machine that will not start"
        )
    return None


def bands(path: str, origin_words: frozenset[str], defined: dict[str, list[str]]) -> list[str]:
    """Everything wrong with the bands a delivery is held to.

    Unlike the figures above, a band carries its value here. The check is
    therefore the other way round: the value must be present in the data and
    absent from the source, because a band that is compiled in cannot be varied
    without a rebuild, and a design whose tolerance nobody has varied is one
    whose cost nobody has established.
    """
    problems: list[str] = []

    with open(path, "r", encoding="utf-8") as handle:
        lines = handle.read().splitlines()

    declared: dict[str, int] = {}
    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        name, separator, rest = line.partition("=")
        name = name.strip()
        if not separator:
            problems.append(f"{path}:{number}: '{line}' is not a band and a value")
            continue
        if name not in BANDS:
            problems.append(
                f"{path}:{number}: '{name}' is not a band anything in this build holds a "
                "delivery to, so nothing reads what this line declares"
            )
            continue
        if name in declared:
            problems.append(
                f"{path}:{number}: '{name}' was already declared on line {declared[name]}"
            )
            continue
        declared[name] = number

        figure, marker, annotation = rest.partition("@")
        if not figure.strip():
            problems.append(f"{path}:{number}: '{name}' carries no value")
        else:
            unusable = unusable_band(name, figure.strip())
            if unusable:
                problems.append(f"{path}:{number}: {unusable}")
        if not marker:
            problems.append(
                f"{path}:{number}: '{name}' records no origin, so what the design is holding "
                "itself to rests on nothing anybody can challenge"
            )
            continue

        words = annotation.split()
        kind = words[0] if words else ""
        if kind not in origin_words:
            problems.append(
                f"{path}:{number}: '{name}' records its origin as '{kind}', which is not one "
                f"of {sorted(origin_words)}"
            )
        elif not words[1:]:
            problems.append(
                f"{path}:{number}: '{name}' records a kind and no account of what the figure "
                "was arrived at from, so it can be neither reproduced nor challenged"
            )

    for name in sorted(BANDS):
        if name not in declared:
            problems.append(
                f"{path}: '{name}' is declared nowhere. A band left undeclared is not a wide "
                "band, it is a criterion nothing holds a delivery to"
            )

    for name, (fragment, _unit, _widest) in sorted(BANDS.items()):
        offenders = sorted(
            {path for macro, paths in defined.items() if fragment in macro for path in paths}
        )
        if offenders:
            problems.append(
                f"'{name}' is declared as data and is defined in {', '.join(offenders)}. A band "
                "compiled in cannot be varied without a rebuild, and it would go on reading as "
                "declared in the tolerance file while the software held deliveries to the other "
                "one"
            )

    return problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-dir", required=True, help="where the seam's headers live")
    parser.add_argument(
        "--source-dir",
        required=True,
        action="append",
        help="a directory whose figures must account for themselves; repeatable",
    )
    parser.add_argument(
        "--source-header",
        action="append",
        default=[],
        help="a header whose figures the sources above rest on; repeatable",
    )
    parser.add_argument(
        "--declaration", required=True, help="the control declaration to read"
    )
    parser.add_argument("--tolerance", required=True, help="the tolerance declaration to read")
    parser.add_argument(
        "--tree-dir",
        required=True,
        action="append",
        help="a directory searched for a band that has grown a second home; repeatable",
    )
    args = parser.parse_args(argv)

    vocabulary, origin_problems = load_vocabulary(args.include_dir)
    if vocabulary is None:
        print("check_control_declaration: the origin vocabulary could not be read", file=sys.stderr)
        for problem in origin_problems:
            print(f"  {problem}", file=sys.stderr)
        return 2

    for directory in [*args.source_dir, *args.tree_dir]:
        if not os.path.isdir(directory):
            print(f"check_control_declaration: no such directory: {directory}", file=sys.stderr)
            return 2

    for header in args.source_header:
        if not os.path.isfile(header):
            print(
                f"check_control_declaration: no header to scan at {header}. A header named "
                "here and absent from the tree is a file whose figures nothing asks about, "
                "while the invocation goes on reading as though it did",
                file=sys.stderr,
            )
            return 2

    if not os.path.isfile(args.declaration):
        print(
            f"check_control_declaration: there was no declaration to inspect at "
            f"{args.declaration}. Reporting success over an absent one would say every figure "
            "the control law rests on had been accounted for",
            file=sys.stderr,
        )
        return 2

    # The same reasoning, about the other absent artefact. An absent tolerance
    # declaration is not a build with a wide band in it; it is a build whose
    # deliveries are held to nothing, and reporting anything but a stop over one
    # would say the band had been declared.
    if not os.path.isfile(args.tolerance):
        print(
            f"check_control_declaration: there was no tolerance declaration to inspect at "
            f"{args.tolerance}. A band left undeclared is not a wide band, it is a criterion "
            "nothing holds a delivery to",
            file=sys.stderr,
        )
        return 2

    accounted, problems = accounted_in(args.declaration, vocabulary.words)

    defined = definitions(*args.source_dir, *args.source_header)
    problems.extend(homes(accounted, defined))
    problems.extend(bands(args.tolerance, vocabulary.words, definitions(*args.tree_dir)))

    if problems:
        print(
            "check_control_declaration: a figure the control logic rests on is not accounted "
            "for, or does not have one home",
            file=sys.stderr,
        )
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    here = len(defined) - sum(1 for macro in defined if macro in ACCOUNTED_ELSEWHERE)
    print(
        f"check_control_declaration: {here} control figure(s) account for themselves here and "
        f"each has one home, and {len(BANDS)} band(s) are declared as data"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
