#!/usr/bin/env python3
"""Fail when a parameter description carries a value it cannot account for.

The design is established against a description of the machine long before the
machine has been measured, and the values in it are not all the same kind of
fact. Some are read off a document, some are estimated because nothing states
them, and later some will be measured on the bench. An estimate that cannot be
told apart from a measurement is the more dangerous of the two, because it is
trusted like the measurement it resembles.

A convention that depends on remembering is not a discipline. Provenance decays
at exactly the moment it matters most -- under time pressure, adding one more
coefficient -- and the failure leaves no trace at the point of use, because a
bare number reveals nothing about whether it ever had an account. So this runs
as part of the build rather than as something a reviewer might notice.

Five things are checked, because each can pass while another is broken:

  * the vocabulary itself still draws its line where the requirement draws it --
    at how a figure was arrived at, and at nothing else. A vocabulary that has
    grown a term for how good a figure is, or for who supplied it, is the
    failure this check exists upstream of: estimates and measurements could then
    carry words that no longer separate them,
  * every coefficient a structure requires appears in each description that
    claims a machine, and carries an origin from that vocabulary with an account
    behind it,
  * a description exempts itself only by saying so, in the file, in the words
    the vocabulary declares for it,
  * the statement of what a description represents names every coefficient and
    every quantity, so that adding a coefficient to a structure and leaving the
    statement behind fails here rather than silently leaving a reader without a
    unit or a relation for it, and
  * something was actually inspected. A tree in which every description exempts
    itself has established nothing, and neither has one with no descriptions in
    it at all.

Judging whether a recorded origin is truthful is a review question and is not
attempted here. What the build can establish is that an account exists, that it
says which kind of fact it is, and that it says something.

Usage: check_parameter_origins.py --plant-root <dir> --include-dir <dir>
                                  --params-dir <dir>
"""

from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_environments  # noqa: E402
from structure_symbols import discover  # noqa: E402

#: The header the origin vocabulary is declared in, relative to the include directory.
VOCABULARY_HEADER = "plant_origin.h"

#: The type the vocabulary's kinds belong to.
VOCABULARY_TYPE = "plant_origin_kind_t"

#: The header the quantities the seam exposes are declared in.
QUANTITY_HEADER = "plant_types.h"

#: The type those quantities belong to.
QUANTITY_TYPE = "plant_quantity_t"

#: What a parameter description file is called, and what separates a structure's
#: name from the variant where it ships more than one. The same convention the
#: artefact runner reads, because a description neither of them claims is one
#: nothing inspects.
DESCRIPTION_SUFFIX = ".params"
VARIANT_SEPARATOR = "-"

#: What a description's statement of what it represents is called.
STATEMENT_SUFFIX = ".md"

#: The macro a build environment names its reference description with.
#
# An environment naming one is saying that this is the description its artefact
# and its tests are exercised against, which is exactly the description that
# must not exempt itself: were it to, every value the design is reasoned against
# would stop owing an account while this check went on passing on the strength
# of some other file. Read out of the build rather than named here, because
# which description that is belongs to the build.
REFERENCE_MACRO = "REFERENCE_DESCRIPTION_PATH"

_REFERENCE_FLAG = re.compile(
    r"-D\s*" + REFERENCE_MACRO + r"\s*=\s*[\"']*([^\"'\s]+)[\"']*"
)

#: The kinds the requirement's distinction is made of.
#
# Unlike the coefficients -- which are read out of the structures, because that
# set grows -- these three are named here. The vocabulary is required to declare
# exactly them, so renaming one, dropping one, or adding a fourth fails this
# check loudly instead of quietly moving where the line between an estimate and
# a measurement falls.
REQUIRED_KINDS = ("PLANT_ORIGIN_DOCUMENT", "PLANT_ORIGIN_ESTIMATED", "PLANT_ORIGIN_MEASURED")

#: The enumerator that counts the kinds rather than being one of them.
KIND_COUNT = "PLANT_ORIGIN_KIND_COUNT"

_ENUM_BODY = re.compile(r"\benum\b[^;{]*\{([^}]*)\}\s*%s\s*;", re.DOTALL)
_ENUMERATOR = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)")
_DEFINE_STRING = re.compile(
    r'^\s*#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)\s+"([^"]*)"\s*$', re.MULTILINE
)
_DEFINE_CHAR = re.compile(r"^\s*#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)\s+'(.)'\s*$", re.MULTILINE)
_SPEC_TABLE = re.compile(r"plant_parameter_spec_t\s+[A-Za-z_][A-Za-z0-9_]*\s*\[\s*\]\s*=\s*\{")
_STRING_LITERAL = re.compile(r'"([^"]*)"')


def read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def enumerators(source: str, type_name: str) -> list[str]:
    """The enumerators of the named enum type, in declaration order."""
    body = re.search(_ENUM_BODY.pattern % re.escape(type_name), source, re.DOTALL)
    if body is None:
        return []
    found = []
    for entry in body.group(1).split(","):
        name = _ENUMERATOR.match(entry)
        if name is not None:
            found.append(name.group(1))
    return found


class Vocabulary:
    """The origin kinds, the word each is written as, and the two markers."""

    def __init__(self, kinds: dict[str, str], marker: str, exemption: str):
        self.kinds = kinds
        self.marker = marker
        self.exemption = exemption

    @property
    def words(self) -> frozenset[str]:
        return frozenset(self.kinds.values())


def load_vocabulary(include_directory: str) -> tuple[Vocabulary | None, list[str]]:
    """Read the vocabulary, and report what is wrong with it rather than assuming it."""
    path = os.path.join(include_directory, VOCABULARY_HEADER)
    if not os.path.isfile(path):
        return None, [f"no origin vocabulary at {path}, so no description can be inspected"]

    source = read(path)
    declared = [name for name in enumerators(source, VOCABULARY_TYPE) if name != KIND_COUNT]
    problems: list[str] = []
    if list(REQUIRED_KINDS) != declared:
        problems.append(
            f"{path}: the origin vocabulary declares {declared or 'nothing'}, but the "
            f"distinction it exists to carry is exactly {list(REQUIRED_KINDS)} -- a kind added, "
            "removed or renamed here changes where the line between an estimate and a "
            "measurement falls, and is a deliberate act rather than a detail"
        )

    strings = dict(_DEFINE_STRING.findall(source))
    characters = dict(_DEFINE_CHAR.findall(source))

    kinds: dict[str, str] = {}
    for kind in REQUIRED_KINDS:
        macro = f"{kind}_WORD"
        if macro not in strings:
            problems.append(f"{path}: {kind} declares no word, so no description can write it")
        else:
            kinds[kind] = strings[macro]

    marker = characters.get("PLANT_ORIGIN_MARKER")
    if marker is None:
        problems.append(f"{path}: no marker is declared, so an origin cannot be recognised")
    exemption = strings.get("PLANT_ORIGIN_NO_MACHINE_DECLARATION")
    if exemption is None:
        problems.append(
            f"{path}: no exemption statement is declared, so a description that claims no "
            "machine has no way to say so"
        )

    if problems:
        return None, problems
    return Vocabulary(kinds, str(marker), str(exemption)), []


def required_coefficients(structure_directory: str) -> list[str]:
    """The coefficient names a structure's parameter table declares, in order.

    Read out of the structure rather than listed here, because that set grows
    with every coefficient anyone adds -- and a coefficient added to a structure
    without an origin behind it is precisely what this check exists to catch.
    """
    names: list[str] = []
    for entry in sorted(os.listdir(structure_directory)):
        if not entry.endswith(".c"):
            continue
        source = read(os.path.join(structure_directory, entry))
        opening = _SPEC_TABLE.search(source)
        if opening is None:
            continue
        depth = 0
        end = opening.end() - 1
        for position in range(opening.end() - 1, len(source)):
            if source[position] == "{":
                depth += 1
            elif source[position] == "}":
                depth -= 1
                if depth == 0:
                    end = position
                    break
        names.extend(_STRING_LITERAL.findall(source[opening.end() : end]))
    return names


def references_named_by_the_build(project: str) -> dict[str, str]:
    """Every description an environment names as the one it is exercised against.

    Keyed by the resolved file name, valued by the environments naming it, so a
    failure can say which build's claim is the one going unmet.
    """
    named: dict[str, str] = {}
    for environment in build_environments.load(project):
        for flag in ("build_flags", "build_src_flags"):
            for match in _REFERENCE_FLAG.finditer(environment.get(flag)):
                path = match.group(1).replace("$PROJECT_DIR/", "").replace("${PROJECT_DIR}/", "")
                named.setdefault(os.path.basename(path), environment.name)
    return named


def descriptions_for(structure: str, params_directory: str) -> list[str]:
    """Every description the named structure ships, in order.

    The match is on the whole of the structure's name, so a structure whose name
    is a prefix of another's does not collect the other's descriptions.
    """
    found = []
    for entry in sorted(os.listdir(params_directory)):
        if not entry.endswith(DESCRIPTION_SUFFIX):
            continue
        stem = entry[: -len(DESCRIPTION_SUFFIX)]
        if stem == structure or stem.startswith(structure + VARIANT_SEPARATOR):
            found.append(os.path.join(params_directory, entry))
    return found


class Description:
    """One description, read as the loader reads it."""

    def __init__(self, path: str, vocabulary: Vocabulary):
        self.path = path
        self.exempt = False
        #: Coefficient name -> (line number, origin kind or None, account or None).
        self.values: dict[str, tuple[int, str | None, str | None]] = {}
        self.problems: list[str] = []

        for number, raw in enumerate(read(path).splitlines(), start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith(vocabulary.marker):
                statement = line[1:].strip()
                if statement == vocabulary.exemption:
                    self.exempt = True
                else:
                    self.problems.append(
                        f"{path}:{number}: '{statement}' is not a statement a description is "
                        f"entitled to make -- the only one is '{vocabulary.exemption}'"
                    )
                continue
            if "=" not in line:
                continue
            name, remainder = line.split("=", 1)
            kind: str | None = None
            account: str | None = None
            if vocabulary.marker in remainder:
                _, annotation = remainder.split(vocabulary.marker, 1)
                parts = annotation.strip().split(None, 1)
                kind = parts[0] if parts else ""
                account = parts[1].strip() if len(parts) > 1 else ""
            self.values[name.strip()] = (number, kind, account)


def inspect(description: Description, coefficients: list[str], vocabulary: Vocabulary) -> list[str]:
    """What is wrong with one description that claims a machine."""
    problems = list(description.problems)
    for coefficient in coefficients:
        if coefficient not in description.values:
            problems.append(
                f"{description.path}: '{coefficient}' is required by the structure and is not "
                "in this description"
            )
            continue
        number, kind, account = description.values[coefficient]
        if kind is None:
            problems.append(
                f"{description.path}:{number}: '{coefficient}' carries no origin. Record where "
                f"the figure came from, as one of {sorted(vocabulary.words)} and an account "
                "behind it"
            )
        elif kind not in vocabulary.words:
            problems.append(
                f"{description.path}:{number}: '{coefficient}' declares its origin as '{kind}', "
                f"which is not one of {sorted(vocabulary.words)}. A further kind is added to "
                f"{VOCABULARY_HEADER} deliberately, not by being typed here"
            )
        elif not account:
            problems.append(
                f"{description.path}:{number}: '{coefficient}' is recorded as '{kind}' with no "
                "account behind it. Say what it was read from, estimated from or measured on, "
                "in enough detail to be reproduced or challenged"
            )
    return problems


def check_statement(
    structure: str, coefficients: list[str], quantities: list[str], params_directory: str
) -> list[str]:
    """The statement of what a description represents names everything it carries."""
    path = os.path.join(params_directory, structure + STATEMENT_SUFFIX)
    if not os.path.isfile(path):
        return [
            f"no statement at {path}: a description that claims a machine says what its "
            "quantities stand for and how they relate, or it is a list of numbers nobody can "
            "check against one"
        ]
    statement = read(path)
    missing = [name for name in coefficients + quantities if name not in statement]
    if missing:
        return [
            f"{path}: names nothing for {missing}. A quantity the statement omits is one a "
            "reader has no unit or relation for, and cannot tell from an oversight"
        ]
    return []


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plant-root", required=True, help="the directory the structures live in")
    parser.add_argument("--include-dir", required=True, help="the directory the seam headers are in")
    parser.add_argument("--params-dir", required=True, help="the directory the descriptions are in")
    parser.add_argument(
        "--project",
        help="the directory the build file is in, read for the description each environment "
        "is exercised against",
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="there is no build file to read, and the descriptions are to be inspected without "
        "asking which one anything is exercised against",
    )
    args = parser.parse_args(argv)

    #
    # One of the two has to be said out loud. Leaving the build optional would
    # mean a caller that quietly dropped --project got the weaker check and no
    # sign of it -- and the weaker check is precisely the one that passes while
    # the description a build reasons against exempts itself.
    #
    if bool(args.project) == bool(args.no_build):
        print(
            "check_parameter_origins: give --project, so the description each environment is "
            "exercised against can be read out of the build, or --no-build to say there is no "
            "build to read. Silently doing without it is how the weaker check becomes the one "
            "that runs",
            file=sys.stderr,
        )
        return 2

    vocabulary, problems = load_vocabulary(args.include_dir)
    if vocabulary is None:
        for problem in problems:
            print(f"check_parameter_origins: {problem}", file=sys.stderr)
        return 1

    quantity_header = os.path.join(args.include_dir, QUANTITY_HEADER)
    if not os.path.isfile(quantity_header):
        print(
            f"check_parameter_origins: no quantity vocabulary at {quantity_header}",
            file=sys.stderr,
        )
        return 1
    quantities = [
        name
        for name in enumerators(read(quantity_header), QUANTITY_TYPE)
        if not name.endswith("_COUNT")
    ]
    if not quantities:
        print(
            f"check_parameter_origins: {quantity_header} enumerates no quantities, so what a "
            "description has to account for cannot be established",
            file=sys.stderr,
        )
        return 1

    if not os.path.isdir(args.params_dir):
        print(
            f"check_parameter_origins: no descriptions at {args.params_dir}",
            file=sys.stderr,
        )
        return 1

    structures = discover(args.plant_root, args.include_dir)
    if not structures:
        print(
            f"check_parameter_origins: no structures under {args.plant_root}, so nothing "
            "declares which coefficients a description owes an origin for",
            file=sys.stderr,
        )
        return 1

    references = references_named_by_the_build(args.project) if args.project else {}

    findings: list[str] = []
    inspected = 0
    seen_any_description = False
    exempted: dict[str, str] = {}
    #: The descriptions this run actually opened and held to account.
    accounted: set[str] = set()

    for structure in structures:
        directory = os.path.join(args.plant_root, structure.name)
        coefficients = required_coefficients(directory)
        if not coefficients:
            findings.append(
                f"{directory}: declares no parameter table, so what its descriptions have to "
                "account for cannot be established"
            )
            continue
        claiming = []
        for path in descriptions_for(structure.name, args.params_dir):
            seen_any_description = True
            description = Description(path, vocabulary)
            if description.exempt:
                findings.extend(description.problems)
                exempted[os.path.basename(path)] = path
                continue
            claiming.append(description)
            findings.extend(inspect(description, coefficients, vocabulary))
            accounted.add(os.path.basename(path))
            inspected += 1
        if claiming:
            findings.extend(
                check_statement(structure.name, coefficients, quantities, args.params_dir)
            )

    for name, environment in sorted(references.items()):
        if name in exempted:
            findings.append(
                f"{exempted[name]}: '{environment}' is exercised against this description, and it "
                "claims no machine. The description a build reasons against is the one whose "
                "values have to account for themselves; exempting it leaves nothing inspected "
                "that matters while this check goes on passing on another file's strength"
            )
        elif name not in accounted:
            #
            # Not "is the file there" but "did this check open it". A
            # description belonging to no structure is never parsed, so asking
            # only whether it exists would let a build be reasoned against a
            # file this check has never read -- which is the same hole as the
            # exempt one, reached from the other side.
            #
            findings.append(
                f"{args.params_dir}: '{environment}' is exercised against '{name}', which is not "
                "among the descriptions inspected here. Either nothing supplies it, or it belongs "
                "to no structure in the tree and so has no coefficient set to account for -- "
                "either way the build reasons against a description nothing has checked"
            )

    if not seen_any_description:
        print(
            f"check_parameter_origins: no descriptions under {args.params_dir} belong to any "
            "structure, so nothing was inspected",
            file=sys.stderr,
        )
        return 1
    if inspected == 0:
        print(
            "check_parameter_origins: every description exempts itself, so no value's origin "
            "was inspected. A tree in which nothing claims a machine establishes nothing about "
            "the provenance of the description the design is reasoned against",
            file=sys.stderr,
        )
        return 1

    for finding in findings:
        print(f"check_parameter_origins: {finding}", file=sys.stderr)
    if findings:
        return 1

    print(
        f"check_parameter_origins: {inspected} description(s) claiming a machine, every value "
        "accounted for"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
