#!/usr/bin/env python3
"""Fail when the estimator's quantity-to-state pairing is incomplete or unsound.

The estimator corrects a state against a reading by pairing the quantity a
sensor channel measures with the state that observes it. Two things about that
pairing have to hold, and neither of them fails loudly on its own.

The first is completeness. Every quantity in the machine's vocabulary must be
answered by the pairing, either with a state or with a stated refusal. The
switch carries no default label so that a quantity added to the vocabulary and
left out of the pairing fails to compile -- but that guarantee lives in a
compiler flag and an absence, and an absence is exactly the kind of thing a
later edit removes without meaning to. This gate says out loud what -Wswitch is
relied on for, so that removing the reliance breaks something that names it.

The second is soundness, and the compiler cannot help at all. A quantity may be
refused only if no sensor channel measures it: a refused quantity that a
channel does reach is a channel whose reading is silently never corrected
against, and the estimator reports that identically to a channel nobody is
reading. Nothing downstream can tell the two apart, so a mis-paired channel
presents as a machine that has drifted rather than as one that is miswired --
which is the single fault the residual exists to distinguish.

The rates are the quantities this is really about. Neither the rate water is
drawn nor the rate steam is drawn is integrated by any structure -- one is
produced from a commanded level and the other is supplied from outside the
machine altogether -- so there is no state either could correct, and both are
refused. A later slice fitting an instrument to either one would add a channel
that measures it, and this gate is what makes that slice notice it must add a
state as well rather than silently getting no correction.

Usage: check_estimator_pairing.py --estimator <file> --include-dir <dir>
"""

from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check_parameter_origins import enumerators, read  # noqa: E402

QUANTITY_TYPE = "plant_quantity_t"
QUANTITY_COUNT = "PLANT_QUANTITY_COUNT"

_SIGNATURE = re.compile(r"^static\s+bool\s+%s\s*\(", re.MULTILINE)
_LABEL = re.compile(r"\bcase\s+([A-Za-z_][A-Za-z0-9_]*)\s*:|\bdefault\s*:")
_ASSIGNMENT = re.compile(r"\*\s*[A-Za-z_][A-Za-z0-9_]*\s*=")
_RETURN_FALSE = re.compile(r"\breturn\s+false\b")
_COMMENT_OR_LITERAL = re.compile(r"/\*.*?\*/|//[^\n]*|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'", re.DOTALL)
_TRAILING_COMMENT = re.compile(r"(?:/\*.*?\*/|//[^\n]*)\s*$", re.DOTALL)

DEFAULT_LABEL = "default"


def clean(text: str) -> str:
    """The code with comments and literals blanked, newlines kept.

    Every question this gate asks is about code, and asking it of the raw text
    lets prose answer. A comment mentioning a quantity would make it measured;
    a comment whose line begins `default:` would make the switch look
    unguarded; a quantity named in a log message would be read as one a channel
    supplies. Blanking rather than deleting keeps offsets and line structure
    intact, so what is found is found where it really is.
    """
    return _COMMENT_OR_LITERAL.sub(lambda m: " " * len(m.group(0)), text)


def body(source: str, function: str) -> str | None:
    """The body of the named file-local function, braces matched.

    Matched rather than ended at the first closing brace in the first column,
    because that convention is a formatting habit and not a rule of the
    language: a case wrapped in braces, or a nested block indented differently,
    ends the body early. Truncation is the dangerous direction here -- a body
    cut short contains fewer cases, and fewer cases is what this gate reads as
    nothing wrong.
    """
    signature = re.search(_SIGNATURE.pattern % re.escape(function), source, re.MULTILINE)
    if signature is None:
        return None
    opening = source.find("{", signature.end())
    if opening < 0:
        return None
    depth = 0
    scan = clean(source)
    for index in range(opening, len(source)):
        if scan[index] == "{":
            depth += 1
        elif scan[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1:index]
    return None


def groups(function_body: str) -> list[tuple[list[str], str]]:
    """Each run of labels sharing one body, with the body they share.

    Labels stack -- `case A: case B: return false;` gives both A and B the same
    body -- so they are grouped rather than read one at a time, and a label's
    body runs to the next label rather than to the next token. Reading only the
    token after the colon is what lets a brace, or a statement before the
    return, turn a refusal into something this gate cannot see.
    """
    stripped = clean(function_body)
    marks = list(_LABEL.finditer(stripped))
    collected: list[tuple[list[str], str]] = []
    for position, mark in enumerate(marks):
        name = mark.group(1) or DEFAULT_LABEL
        end = marks[position + 1].start() if position + 1 < len(marks) else len(stripped)
        shared = stripped[mark.end():end]
        if shared.strip() == "" and position + 1 < len(marks):
            collected.append(([name], ""))  # stacked onto the next label's body
            continue
        names = [name]
        walk = position - 1
        while walk >= 0 and collected and collected[walk][1] == "":
            names.insert(0, collected[walk][0][0])
            walk -= 1
        collected.append((names, shared))
    return [(names, shared) for names, shared in collected if shared != ""]


def refused(function_body: str) -> list[str]:
    """The quantities the pairing answers with a refusal rather than a state.

    A group refuses when its body returns false and assigns no state through
    the out-parameter. Both halves are asked: a body that assigns a state and
    then returns false somewhere down a branch is not a refusal, and neither is
    one that only happens to mention the word.
    """
    found = []
    for names, shared in groups(function_body):
        if _RETURN_FALSE.search(shared) and not _ASSIGNMENT.search(shared):
            found.extend(names)
    return found


def answered(function_body: str) -> list[str]:
    """Every label the pairing names at all, refusal or not."""
    return [name for names, _ in groups(function_body) for name in names]


def has_default(function_body: str) -> bool:
    """Whether a default label stands anywhere in the switch, wrapped or not."""
    return DEFAULT_LABEL in answered(function_body) or bool(
        re.search(r"\bdefault\s*:", clean(function_body))
    )


def mentions(function_body: str, name: str) -> bool:
    """Whether the code -- not its prose -- names this quantity as a whole word."""
    return bool(re.search(r"\b%s\b" % re.escape(name), clean(function_body)))


def commented(function_body: str, quantity: str) -> bool:
    """Whether a comment stands above this refusal, saying why it is one.

    Found against the raw body, since the comment is the subject. Either form
    of comment counts, and a label stacked under a comment that covers the run
    counts with it -- the rule is that a refusal carries a stated reason, not
    that it carries one in a particular syntax.
    """
    label = re.search(r"\bcase\s+%s\s*:" % re.escape(quantity), function_body)
    if label is None:
        return False
    preceding = function_body[:label.start()]
    while True:
        if _TRAILING_COMMENT.search(preceding):
            return True
        stacked = re.search(r"\bcase\s+[A-Za-z_][A-Za-z0-9_]*\s*:\s*$", preceding)
        if stacked is None:
            return False
        preceding = preceding[:stacked.start()]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--estimator", required=True, help="the file the pairing lives in")
    parser.add_argument("--include-dir", required=True, help="the directory the seam headers are in")
    parser.add_argument("--pairing", default="state_observed_by", help="the pairing function")
    parser.add_argument("--measurement", default="quantity_measured_by", help="the channel mapping")
    args = parser.parse_args(argv)

    source = read(args.estimator)
    vocabulary = [
        name
        for name in enumerators(read(os.path.join(args.include_dir, "plant_types.h")), QUANTITY_TYPE)
        if name != QUANTITY_COUNT
    ]
    if not vocabulary:
        print(
            "check_estimator_pairing: no quantities are declared, so this gate has nothing to "
            "cover and would report success without inspecting anything",
            file=sys.stderr,
        )
        return 2

    pairing = body(source, args.pairing)
    measurement = body(source, args.measurement)
    if pairing is None or measurement is None:
        print(
            f"check_estimator_pairing: {args.estimator} does not declare both "
            f"'{args.pairing}' and '{args.measurement}' as file-local functions, so this gate "
            "has nothing to cover and would report success without inspecting anything",
            file=sys.stderr,
        )
        return 2

    problems = []

    named = answered(pairing)
    unanswered = [name for name in vocabulary if name not in named]
    if unanswered:
        problems.append(
            f"{args.pairing} names nothing for {unanswered}. A quantity the pairing omits is "
            "one the compiler is being relied on to catch; say what it observes, or refuse it"
        )

    if has_default(pairing):
        problems.append(
            f"{args.pairing} carries a default label, so a quantity added to the vocabulary "
            "falls through it silently instead of failing the build"
        )

    turned_down = [name for name in refused(pairing) if name in vocabulary]
    observed = [name for name in named if name in vocabulary and name not in turned_down]
    measured = [name for name in vocabulary if mentions(measurement, name)]

    # The quantities paired with a state must be exactly the quantities some
    # channel measures, and the rule earns its keep in both directions.
    #
    # A quantity that is measured and refused is a channel whose reading is
    # never corrected against, reported identically to a channel nobody reads --
    # so a miswiring presents as a drifting machine, which is the one fault the
    # residual exists to tell apart.
    #
    # A quantity that is paired with a state and measured by nothing is the
    # converse, and is the more insidious of the two because it costs nothing
    # today: the pairing is unreachable, so no test can reach it either, and it
    # sits there asserting a relationship between a rate and a state nothing
    # keeps. It becomes wrong the moment an instrument is fitted, and it becomes
    # wrong silently, in the release that fits it rather than the one that wrote
    # it.
    reachable = sorted(name for name in turned_down if name in measured)
    if reachable:
        problems.append(
            f"{reachable} are refused by {args.pairing} but measured by {args.measurement}. "
            "A channel whose quantity is refused is never corrected against, and reports that "
            "identically to a channel nobody reads -- give each one a state, or stop measuring it"
        )

    unmeasured = sorted(name for name in observed if name not in measured)
    if unmeasured:
        problems.append(
            f"{unmeasured} are paired with a state by {args.pairing} but measured by no channel. "
            "A pairing nothing can reach is a claim no test can check and no reading can "
            "correct; refuse the quantity until something measures it"
        )

    unexplained = sorted(name for name in turned_down if not commented(pairing, name))
    if unexplained:
        problems.append(
            f"{unexplained} are refused by {args.pairing} with no comment above them. A "
            "refusal nobody wrote a reason for cannot be told from one nobody meant"
        )

    if problems:
        print(
            "check_estimator_pairing: the quantity-to-state pairing does not hold", file=sys.stderr
        )
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print(
        f"check_estimator_pairing: {len(vocabulary)} quantities answered -- "
        f"{len(observed)} paired with the state each measured one observes, "
        f"{len(turned_down)} refused with a reason and measured by nothing"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
