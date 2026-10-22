#!/usr/bin/env python3
"""The catalogue helpers the callers of the review kit share: the areas and items of a practice catalogue in a review
folder's method, the board's own items from its plan, and the couplings between areas.

A caller reads the catalogue of one method section, named by its heading, from the method the review folder holds. Every
catalogue of the method heads an area `### <name> (<CODE>)` and an item `#### <ID>. `, so one reading serves them all; a
caller passes the heading of the section it takes its units from. The functions raise `ReviewFolderProblem`, naming what
is missing, which a caller turns into the kit's refusal.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Dict, List, Optional, Sequence, Tuple

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)

import board_placement  # noqa: E402
import review_folder  # noqa: E402

ReviewFolderProblem = review_folder.ReviewFolderProblem
METHOD = review_folder.METHOD
#: The heading of the layout practice catalogue, the section the layout review and the critical-routing check take their units from.
LAYOUT_SECTION = "Layout practice catalogue"
#: The board's plan, in the design folder of a review folder.
PLAN = "layout-plan.md"
AREA = re.compile(r"^### (.+) \(([A-Z]+)\)[ \t]*$")
ITEM = re.compile(r"^#### ([A-Z]+-\d+)\. ")
OWN_ITEM = re.compile(r"BOARD-[1-9][0-9]*")

#: The areas whose verdicts the layout reviews showed depend on another area's findings: power with mains, and the
#: manufacturing items with power. Each pair is judged in one group. A cross-reference between two areas of the catalogue does not make a
#: coupling, since the planner joins couplings transitively and coupling every linked pair leaves nine of twelve areas in one
#: group; a test fails when a coupling a caller states has no cross-reference of the catalogue to support it.
COUPLED = (("POWER", "MAINS"), ("MFG", "POWER"))


def read_text(review: str, path: str, what: str) -> str:
    try:
        with open(os.path.join(review, path), encoding="utf-8") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError) as error:
        raise ReviewFolderProblem(f"the review folder {review} holds no readable {what} ({path}: {error}); write the folder "
                                  "with the folder command")


def section_body(review: str, heading: str) -> str:
    """The text of the method's `## <heading>` section, after its heading line, up to the next second-level heading."""
    text = read_text(review, METHOD, "method")
    found = re.search(r"^## " + re.escape(heading) + r"[ \t]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if found is None:
        raise ReviewFolderProblem(f"the method in the review folder {review} has no `## {heading}` section, "
                                  "so there are no catalogue areas to take units from")
    return found.group(1)


def no_area(review: str) -> ReviewFolderProblem:
    return ReviewFolderProblem(f"the method in the review folder {review} has no catalogue area heading of the form "
                               "`### <name> (<CODE>)`, so there are no units to take from it")


def catalogue_split(review: str, heading: str = LAYOUT_SECTION) -> Tuple[str, Dict[str, str]]:
    """The catalogue's introduction, the text before its first area heading, and each area's block by code: its heading
    line to the next area heading or the end of the catalogue."""
    lines = section_body(review, heading).split("\n")
    starts = [index for index, line in enumerate(lines) if AREA.match(line)]
    if not starts:
        raise no_area(review)
    intro = "\n".join(lines[:starts[0]]).strip()
    if not intro:
        raise ReviewFolderProblem(f"the {heading.lower()} in the method of the review folder {review} has no "
                                  "introduction before its first area heading, which the shared context needs")
    blocks = {}
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        blocks[AREA.match(lines[start]).group(2)] = "\n".join(lines[start:end]).strip() + "\n"
    return intro, blocks


def listed_items_only(block: str, listed: Sequence[str]) -> str:
    """An area's block with only the items of `listed`: its heading and the text before its first item, then each listed
    item's own text, so a narrow round's prompt names no item the round does not judge."""
    parts = re.split(r"(?m)^(?=#### )", block)
    kept = [parts[0]] + [part for part in parts[1:] if (ITEM.match(part) and ITEM.match(part).group(1) in listed)]
    return "".join(kept).rstrip() + "\n"


def areas(review: str, heading: str = LAYOUT_SECTION) -> List[Tuple[str, str, List[str]]]:
    """Each area heading of the method's catalogue section, in order: its code, its name and its items' identifiers."""
    found: List[Tuple[str, str, List[str]]] = []
    for line in section_body(review, heading).split("\n"):
        area, item = AREA.match(line), ITEM.match(line)
        if area:
            found.append((area.group(2), area.group(1), []))
        elif item and found:
            found[-1][2].append(item.group(1))
    if not found:
        raise no_area(review)
    return found


def own_items(review: str) -> List[str]:
    """The board's own items from the plan's table of them, none for the table's one `none` row."""
    design = review_folder.design_in(review)
    path = os.path.join(design, PLAN)
    lines = read_text(review, path, f"plan ({PLAN})").splitlines()
    start = next((index for index, line in enumerate(lines) if line.strip().startswith("|")
                  and board_placement.cells(line)[:2] == ["Item", "Applies when"]), None)
    if start is None:
        raise ReviewFolderProblem(f"the plan {path} holds no table of the board's own items, headed `| Item | Applies when | ...`; "
                                  "it cannot be read, so the board's own items cannot be told")
    header = board_placement.cells(lines[start])
    divider = board_placement.cells(lines[start + 1]) if start + 1 < len(lines) and lines[start + 1].strip().startswith("|") else []
    if len(divider) != len(header) or not all(re.fullmatch(r":?-+:?", cell) for cell in divider):
        raise ReviewFolderProblem(f"the table of the board's own items in the plan {path} has no divider row under its header")
    found, problems = [], []
    for row in lines[start + 2:]:
        if not row.strip().startswith("|"):
            break
        cells = board_placement.cells(row)
        if len(cells) != len(header):
            problems.append(f"the row {row.strip()[:80]!r} has {len(cells)} cells where the header has {len(header)}")
        elif cells[0].lower() == "none" and len(found) == 0 and not problems:
            continue
        elif not OWN_ITEM.fullmatch(cells[0]):
            problems.append(f"the row {row.strip()[:80]!r} gives its item as {cells[0]!r}, not BOARD-<n> or `none`")
        else:
            found.append(cells[0])
    if problems or len(set(found)) != len(found):
        raise ReviewFolderProblem(f"the table of the board's own items in the plan {path} cannot be read: "
                                  + "; ".join(problems or ["an item is given twice"]))
    return found


def coupled_to(unit: str, units: Dict[str, List[str]], couplings: Sequence[Tuple[str, str]] = COUPLED) -> List[str]:
    """The other units of the round that `couplings` couple a unit with: the area pairs whose two areas both have a unit in
    the round."""
    if not unit.startswith("area-"):
        return []
    code = unit[len("area-"):]
    others = []
    for first, second in couplings:
        for mine, theirs in ((first, second), (second, first)):
            if mine == code and f"area-{theirs}" in units:
                others.append(f"area-{theirs}")
    return sorted(set(others), key=list(units).index)
