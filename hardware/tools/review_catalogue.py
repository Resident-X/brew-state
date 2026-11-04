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
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)

import board_placement  # noqa: E402
import review_folder  # noqa: E402
from review_kit import selection  # noqa: E402

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


def own_table(review: str) -> Tuple[List[str], List[List[str]]]:
    """The header and the rows of the plan's table of the board's own items, each row as its cells."""
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
    rows = []
    for row in lines[start + 2:]:
        if not row.strip().startswith("|"):
            break
        rows.append(board_placement.cells(row))
    return header, rows


def own_items(review: str) -> List[str]:
    """The board's own items from the plan's table of them, none for the table's one `none` row."""
    path = os.path.join(review_folder.design_in(review), PLAN)
    header, rows = own_table(review)
    found, problems = [], []
    for cells in rows:
        if len(cells) != len(header):
            problems.append(f"the row {' | '.join(cells)[:80]!r} has {len(cells)} cells where the header has {len(header)}")
        elif cells[0].lower() == "none" and len(found) == 0 and not problems:
            continue
        elif not OWN_ITEM.fullmatch(cells[0]):
            problems.append(f"the row {' | '.join(cells)[:80]!r} gives its item as {cells[0]!r}, not BOARD-<n> or `none`")
        else:
            found.append(cells[0])
    if problems or len(set(found)) != len(found):
        raise ReviewFolderProblem(f"the table of the board's own items in the plan {path} cannot be read: "
                                  + "; ".join(problems or ["an item is given twice"]))
    return found


# --- What the items are judged on ----------------------------------------------------------------

JUDGED_ON = re.compile(r"^- \*\*Judged on:\*\*(.*)$", re.M)
BACKTICKED = re.compile(r"`([^`]+)`")
#: A name the pre-order check's lines give a rule: a lower-case word or words joined by underscores.
RULE_NAME = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)+")


def item_texts(review: str, heading: str = LAYOUT_SECTION) -> Dict[str, str]:
    """The text of each catalogue item by its identifier: its heading line to the next item or area."""
    found: Dict[str, str] = {}
    for part in re.split(r"(?m)^(?=#{3,4} )", section_body(review, heading)):
        item = ITEM.match(part)
        if item:
            found[item.group(1)] = part
    return found


def judged_on(review: str, items: Sequence[str], heading: str = LAYOUT_SECTION) -> List[str]:
    """The names, in the order the items give them, that the items are judged on: the backticked names of each catalogue item's
    *Judged on* line, and of the *Judged on* cell of each of the board's own items in the plan's table."""
    texts = item_texts(review, heading)
    own: Dict[str, str] = {}
    if any(OWN_ITEM.fullmatch(item) for item in items):
        header, rows = own_table(review)
        if "Judged on" in header:
            column = header.index("Judged on")
            own = {cells[0]: cells[column] for cells in rows if len(cells) == len(header)}
    found: List[str] = []
    for item in items:
        line = JUDGED_ON.search(texts[item]) if item in texts else None
        text = line.group(1) if line else own.get(item, "")
        found += BACKTICKED.findall(text)
    return list(dict.fromkeys(found))


def is_copper_layer(name: str) -> bool:
    return name.endswith(".Cu")


def views_for(review: str, names: Sequence[str]) -> List[str]:
    """The artefact names of the views a unit needs, chosen through the kit's selection from the review folder's view index for
    the names its items are judged on: `layer-<layer>` the whole-board tiles of that layer (every copper layer for a name such
    as `layer-<copper layer>`), `net-<net>` the tiles of that net (of every critical net for a name such as `net-<net>`),
    `classes` the class map, `crop-<reference>` that circuit's crop (every crop for a placeholder), `assembly-top` and
    `assembly-bottom` the assembly view of that side, `3d-<direction>` the three-dimensional view. A name that is no view
    (`facts.txt`, the check's report, `design-rules.md`) and `placement`, whose images are not in the index, name none. A view
    the index lacks is left out, since the board may carry no such layer, net or circuit."""
    index = selection.read_index(review)
    found = set()
    for name in names:
        kind, _, rest = name.partition("-")
        literal = bool(rest) and "<" not in rest
        if kind == "layer" and rest:
            layers = [rest] if literal else sorted({entry["name"] for image in index["images"] if image.get("view") == "layer"
                                                    for entry in image.get("layers", []) if is_copper_layer(entry["name"])})
            found.update(selection.select(index, view="layer", layers=layers, allow_empty=True))
        elif kind == "net" and rest:
            found.update(selection.select(index, view="net", nets=[rest] if literal else None, allow_empty=True))
        elif name == "classes":
            found.update(selection.select(index, view="class map", allow_empty=True))
        elif kind == "crop" and rest:
            found.update(selection.select(index, view="crop", fields={"circuit": rest} if literal else None, allow_empty=True))
        elif name in ("assembly-top", "assembly-bottom"):
            found.update(selection.select(index, view="assembly", fields={"side": rest}, allow_empty=True))
        elif kind == "3d" and rest:
            found.update(selection.select(index, view="3d", fields={"file": f"3d-{rest}.png"}, allow_empty=True))
    return sorted(found)


def declared_views(review: str, held: Iterable[str], names: Iterable[str]) -> List[str]:
    """The views `names` select, each checked to be an artefact the folder holds (`held`); an index that lists a view the folder
    lacks is refused naming it."""
    chosen = views_for(review, names)
    lacking = [name for name in chosen if name not in set(held)]
    if lacking:
        raise ReviewFolderProblem(f"the view index of the review folder {review} lists {lacking[0]}"
                                  + (f" and {len(lacking) - 1} more" if len(lacking) > 1 else "")
                                  + ", which the folder does not hold; write the folder again with the folder command")
    return chosen


def report_rules(report: str, pattern: "re.Pattern[str]") -> List[str]:
    """The rules the lines of a check's report are about, read with `pattern` (its `rule` group), in the order first met."""
    found = []
    for line in report.splitlines():
        match = pattern.search(line)
        if match:
            found.append(match.group("rule").strip())
    return list(dict.fromkeys(found))


def declared_rules(review: str, items: Sequence[str], known: Sequence[str] = (), heading: str = LAYOUT_SECTION) -> List[str]:
    """The check rules the items judge: the backticked names, in the *Passes* and *Fails* lines of each catalogue item of kind
    rule, of the form the check gives a rule or that the check's report names (`known`), sorted."""
    texts = item_texts(review, heading)
    found = set()
    for item in items:
        text = texts.get(item, "")
        if "**Kind:** rule" not in text:
            continue
        for line in re.findall(r"(?m)^- \*\*(?:Passes|Fails[^*]*):\*\*(.*)$", text):
            found.update(name for name in BACKTICKED.findall(line) if RULE_NAME.fullmatch(name) or name in known)
    return sorted(found)


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
