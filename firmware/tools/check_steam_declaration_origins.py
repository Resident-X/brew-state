#!/usr/bin/env python3
"""Fail when a figure of the steam control declaration is not honestly derived.

The declaration's ready, band and feed figures were once derived through the
affine saturation slope and the pressure-deficit coefficient, relations the
thermoblock's steam side no longer has. A figure whose account still names one
is a figure derived through a relation that is gone, and it reads as sourced
while resting on nothing. A figure with no origin at all is the same failure one
step earlier. Two things are refused:

  * a figure line carrying no origin annotation, an origin kind outside the
    declared vocabulary, or a kind with no account behind it,
  * a figure whose account names a retired relation, by the coefficient's name or
    by the words the old accounts used for it.

Only the account of a figure is read for the second: the comments around the
lines are free to say what was retired and why. What an account says is not
judged beyond that. Whether it is truthful is a review question.

Usage: check_steam_declaration_origins.py --include-dir <dir> --declaration <file>
"""

from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check_parameter_origins import load_vocabulary  # noqa: E402

#: What names a retired relation. The coefficients by name, and the phrases the
#: accounts that rested on them used. Matched case-insensitively against the
#: account only.
RETIRED = (
    "steam.pressure_bar_per_k",
    "steam.pressure_fall_bar_per_ml",
    "pressure_bar_per_k",
    "pressure_fall_bar_per_ml",
    "pressure-per-kelvin",
    "pressure per kelvin",
    "affine",
    "pressure deficit",
    "pressure-deficit",
    "per-kelvin slope",
    "saturation slope",
    "declared slope",
    "sag coefficient",
)

_FIGURE = re.compile(r"^[a-z][a-z0-9-]*[ \t]*=")


def problems(text: str, kinds: set[str]) -> list[str]:
    """Every refusal the declaration's figure lines earn, with its line number."""
    found: list[str] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#") or not _FIGURE.match(line):
            continue
        name = line.split("=", 1)[0].strip()
        marker = line.find("@")
        if marker < 0:
            found.append(f"line {number}: {name} carries no origin")
            continue
        parts = line[marker + 1:].split(None, 1)
        if not parts or parts[0] not in kinds:
            found.append(f"line {number}: {name} names an origin kind outside the vocabulary")
            continue
        account = parts[1].strip() if len(parts) > 1 else ""
        if not account:
            found.append(f"line {number}: {name} names an origin kind and no account of it")
            continue
        lowered = account.lower()
        for retired in RETIRED:
            if retired in lowered:
                found.append(
                    f"line {number}: {name} has an origin naming the retired relation "
                    f"'{retired}'; re-derive it from the orifice law, the saturation relation "
                    f"and the casting ceiling"
                )
                break
    return found


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-dir", required=True)
    parser.add_argument("--declaration", required=True)
    args = parser.parse_args(argv)

    if not os.path.isfile(args.declaration):
        print(f"check_steam_declaration_origins: no declaration at {args.declaration}",
              file=sys.stderr)
        return 2
    vocabulary, vocabulary_problems = load_vocabulary(args.include_dir)
    if vocabulary is None:
        for problem in vocabulary_problems:
            print(f"check_steam_declaration_origins: {problem}", file=sys.stderr)
        return 1
    kinds = set(vocabulary.words)
    with open(args.declaration, "r", encoding="utf-8") as handle:
        text = handle.read()

    figures = [l for l in text.splitlines() if _FIGURE.match(l.strip())]
    if not figures:
        print(f"check_steam_declaration_origins: {args.declaration} declares no figure at all, "
              "so there is nothing to have checked", file=sys.stderr)
        return 1

    found = problems(text, kinds)
    for finding in found:
        print(f"check_steam_declaration_origins: {finding}", file=sys.stderr)
    if found:
        return 1
    print(f"check_steam_declaration_origins: {len(figures)} figure(s), each with an origin and "
          "none naming a retired relation")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
