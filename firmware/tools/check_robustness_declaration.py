#!/usr/bin/env python3
"""Fail when a behaviour the design commits to is not classified against a wrong model.

The plant model will be wrong, and the useful question is not by how much but
what still holds when it is. That question has two answers rather than one. Some
behaviours must hold however wrong the model turns out to be -- refusing what
cannot be delivered, reaching a safe state, staying inside the supply the
machine is fed from -- and others are permitted to get worse as the model does,
because they are how good the coffee is rather than whether the machine is fit
to be switched on.

Without the split, an identification that lands badly threatens every property
at once and nobody can say which ones still stand. With it, a bad fit has a
known blast radius rather than an unknown one.

The split is data rather than a paragraph because its consumer is a later
verification and not a reader. Prose cannot be checked for exhaustiveness,
cannot be diffed when a behaviour is added, and cannot fail a build when a
behaviour arrives carrying no class at all -- and an unclassified behaviour is
precisely the failure this exists to prevent, because it is the one that reads
as covered to everybody who looks at it. Nobody notices the absence of a
sentence.

Five things are checked, because each can pass while another is broken:

  * the vocabulary itself still draws its line where the requirement draws it --
    at what a wrong model is permitted to take away, and at nothing else. A
    vocabulary that has grown a term for a behaviour that mostly holds is the
    failure this check exists upstream of: it is a place for an unexamined
    property to sit, and every property put there is one nobody has to decide
    about,
  * every behaviour named in the declaration carries exactly one class from that
    vocabulary -- not none, not two, and not a word somebody typed here,
  * no behaviour is named twice, since two lines for one behaviour are two
    answers to the question this file exists to answer, and which of them
    applies is then whichever the reader's eye landed on,
  * every class has something in it, because a declaration where everything
    is invariant, or everything degrades, has drawn no line and taken no
    decision, and
  * there is a declaration at all, with something in it. An absent or empty
    artefact establishes nothing, and reporting success over one would say every
    behaviour had been classified.

What a behaviour costs, and whether a loop actually holds one across the
declared range of model error, is the robustness verification's question and is
not attempted here. There is no loop yet. What the build can establish is that
nothing the design commits to has arrived without somebody deciding which side
of the line it falls on.

Usage: check_robustness_declaration.py --include-dir <dir> --declaration <file>
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# The origin check owns the reading of an enumerated vocabulary out of a header.
# Reading one a second way here would be a second opinion about what a C enum
# says, and the two would eventually disagree about a header neither is wrong
# about.
from check_parameter_origins import _DEFINE_STRING, enumerators, read  # noqa: E402

#: The header the classes are declared in, relative to the include directory.
VOCABULARY_HEADER = "plant_robustness.h"

#: The type the classes belong to.
VOCABULARY_TYPE = "plant_robustness_kind_t"

#: The classes the requirement's distinction is made of.
#
# Named here rather than taken as "whatever the header declares", because the
# whole point of the vocabulary is which distinctions it draws and how many. A
# class added, removed or renamed moves where the lines between what must
# survive, what is guaranteed only inside the declared error, and what may
# degrade fall -- and that is a deliberate act rather than a detail. Reading the
# list from the header instead would make this check agree with any edit to it,
# which is the one thing it must not do.
REQUIRED_KINDS = (
    "PLANT_ROBUSTNESS_INVARIANT",
    "PLANT_ROBUSTNESS_BOUNDED",
    "PLANT_ROBUSTNESS_DEGRADING",
)

#: The enumerator that counts the classes rather than being one of them.
KIND_COUNT = "PLANT_ROBUSTNESS_KIND_COUNT"


def load_vocabulary(include_directory: str) -> tuple[dict[str, str] | None, list[str]]:
    """The class each kind is written as, or what is wrong with the vocabulary."""
    path = os.path.join(include_directory, VOCABULARY_HEADER)
    if not os.path.isfile(path):
        return None, [f"no robustness vocabulary at {path}, so no behaviour can be classified"]

    source = read(path)
    declared = [name for name in enumerators(source, VOCABULARY_TYPE) if name != KIND_COUNT]
    problems: list[str] = []
    if list(REQUIRED_KINDS) != declared:
        problems.append(
            f"{path}: the robustness vocabulary declares {declared or 'nothing'}, but the "
            f"distinction it exists to carry is exactly {list(REQUIRED_KINDS)} -- a class added, "
            "removed or renamed here changes what a wrong model is permitted to take away, and "
            "is a deliberate act rather than a detail"
        )

    strings = dict(_DEFINE_STRING.findall(source))
    kinds: dict[str, str] = {}
    for kind in REQUIRED_KINDS:
        macro = f"{kind}_WORD"
        if macro not in strings:
            problems.append(
                f"{path}: {kind} declares no word, so no behaviour can be written as one"
            )
        else:
            kinds[kind] = strings[macro]

    if problems:
        return None, problems
    return kinds, []


def inspect(path: str, words: dict[str, str]) -> tuple[list[str], dict[str, str]]:
    """What is wrong with the declaration, and what it classified successfully."""
    problems: list[str] = []
    #: Behaviour -> the class it carries, for the lines that carried exactly one.
    classified: dict[str, str] = {}
    seen: set[str] = set()

    for number, raw in enumerate(read(path).splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            problems.append(
                f"{path}:{number}: '{line}' is not `behaviour = class`. A line that is neither a "
                "comment nor a classification is a behaviour somebody meant to classify"
            )
            continue
        name, remainder = line.split("=", 1)
        behaviour = name.strip()
        classes = remainder.split()
        if not behaviour:
            problems.append(f"{path}:{number}: a class is declared against no behaviour")
            continue
        if behaviour in seen:
            problems.append(
                f"{path}:{number}: '{behaviour}' is declared more than once, so which class "
                "applies to it is whichever line the reader's eye landed on"
            )
            continue
        seen.add(behaviour)
        if not classes:
            problems.append(
                f"{path}:{number}: '{behaviour}' carries no class. Say whether it must hold "
                f"however wrong the model is, or is permitted to degrade with it: "
                f"{sorted(words.values())}"
            )
            continue
        if len(classes) > 1:
            problems.append(
                f"{path}:{number}: '{behaviour}' carries {len(classes)} classes "
                f"({' '.join(classes)}). The classification exists to say which side of the line "
                "a behaviour falls, and one that falls on both says nothing"
            )
            continue
        if classes[0] not in words.values():
            problems.append(
                f"{path}:{number}: '{behaviour}' is classified '{classes[0]}', which is not one "
                f"of {sorted(words.values())}. A further class is added to {VOCABULARY_HEADER} "
                "deliberately, not by being typed here"
            )
            continue
        classified[behaviour] = classes[0]

    return problems, classified


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--include-dir", required=True, help="the directory the vocabulary header is in"
    )
    parser.add_argument(
        "--declaration", required=True, help="the artefact the behaviours are declared in"
    )
    args = parser.parse_args(argv)

    words, problems = load_vocabulary(args.include_dir)
    if words is None:
        for problem in problems:
            print(f"check_robustness_declaration: {problem}", file=sys.stderr)
        return 2

    if not os.path.isfile(args.declaration):
        print(
            f"check_robustness_declaration: no declaration at {args.declaration}. The behaviours "
            "the design commits to are enumerated somewhere a build can read, or the split "
            "between what survives a wrong model and what does not exists only in prose",
            file=sys.stderr,
        )
        return 1

    findings, classified = inspect(args.declaration, words)

    if not classified and not findings:
        print(
            f"check_robustness_declaration: {args.declaration} declares no behaviour at all, so "
            "nothing was classified and nothing was established",
            file=sys.stderr,
        )
        return 1

    for kind, word in sorted(words.items()):
        if word not in classified.values():
            findings.append(
                f"{args.declaration}: no behaviour is declared '{word}'. A classification with a "
                f"class nothing falls into has drawn no line -- {kind} exists because some "
                "behaviours belong there, and a declaration saying none do is a decision nobody "
                "took"
            )

    for finding in findings:
        print(f"check_robustness_declaration: {finding}", file=sys.stderr)
    if findings:
        return 1

    counts = ", ".join(
        f"{sum(1 for c in classified.values() if c == word)} {word}"
        for word in sorted(words.values())
    )
    print(
        f"check_robustness_declaration: {len(classified)} behaviour(s) declared, each carrying "
        f"exactly one class ({counts})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
