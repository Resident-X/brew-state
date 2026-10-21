#!/usr/bin/env python3
"""The layout review as a caller of the review kit command (review_run.py --caller layout).

A layout review round, full or narrow, is judged by forks of one shared context. The
units are the area headings of the layout practice catalogue in the review folder's
own method, one for the board's own items when the plan's table of them has rows,
and one for the comparison with the plan and the free pass over every view, which
belong to no one area. The areas the catalogue's own cross-references link are
declared coupled, so each coupled set is judged in one group; a narrow round's units
are the areas its listed items fall in, and each fork judges only the listed items.

The review folder is the one review_folder.py writes. The shared context holds the
method's layout review and views sections and the whole catalogue (the method
extract), the plan, the rules table and the records, the round file, the check's
report, the view and placement indexes, every rendered view and the placement view as
an image, and the layout facts the folder command extracted from the board file. A
unit's prompt names its own items and holds its own area; none is in the shared
context. A reviewer is granted the read tools and WebFetch, which fetches a published
document at its address and writes nothing, since a rule-kind item whose figure
rests on a document needs it.

The round's own fields, its number, kind, commit judged, views and the pre-order
check's lines, and for a narrow round its listed items, changed regions and why-others
line, are read from the round file, because the merge has no model to write them; a
round whose fields are missing or malformed is refused when the declaration is
resolved, before any session starts. The checks receive the merged tables alone, so
what the round judges is read once, when the declaration is resolved, and held for
them. They fail an item that has no verdict row or two, a verdict for an item the
round does not judge and a cannot judge still held, and the render writes the round as
the method gives it in round-<n>.md, to be appended below the record's earlier rounds
and committed by whoever started the round. Rule-kind items rest on the check's report
and the rules table as the method says; the merge does not judge them, or whether any
verdict is right.

A cannot judge is resolved within the round: the folder command's add-view mode puts
the view in the added-views folder and records the item, the Why and the view in a
resolutions file there, the unit is run again with --rerun, and the row the render
writes records the cannot judge, the view and the verdict reached, in that order.
"""

from __future__ import annotations

import os
import re
import sys
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence, Tuple

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)

import board_history  # noqa: E402
import board_placement  # noqa: E402
import board_review_history  # noqa: E402
import review_folder  # noqa: E402
from review_kit import results  # noqa: E402
from review_kit.merge import Refused  # noqa: E402

ReviewFolderProblem = review_folder.ReviewFolderProblem
METHOD = review_folder.METHOD
PLAN = "layout-plan.md"
#: The unit that compares the layout with the plan and makes the free pass, and the one for the board's own items.
PLAN_UNIT = "plan-and-free-pass"
OWN_UNIT = "board-items"
#: The checklist entry a finding of the comparison and the free pass is raised against: they belong to no item. It is the
#: checklist's last entry, so the merge numbers those findings after the item units' findings.
PLAN_ENTRY = "PLAN-AND-FREE-PASS"
AREA = re.compile(r"^### (.+) \(([A-Z]+)\)[ \t]*$")
ITEM = re.compile(r"^#### ([A-Z]+-\d+)\. ")
OWN_ITEM = re.compile(r"BOARD-[1-9][0-9]*")
VERDICTS = ("pass", "fail", "not applicable", "cannot judge")
VERDICT_TABLE = list(board_review_history.VERDICT_COLUMNS)
#: The findings table as a reviewer returns it: its Item column, which says which checklist entry raised the finding, is
#: the merge's own and is not written into the record.
FINDING_TABLE = ["Finding", "Item", "Raised by", "Severity", "What and where", "Rule", "Added as", "Planning shortfall", "Closed by"]
RECORD_FINDING_TABLE = [column for column in FINDING_TABLE if column != "Item"]
CITATION = re.compile(r"(?<![\w.])[Ff]inding (?P<round>\d+)\.(?P<number>\d+)\b")
VIEW_NAME = re.compile(r"\b((?:layer|net|crop|classes|assembly|3d|placement)[\w.+/-]*)")
POINT = re.compile(r"\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)")

#: The areas whose verdicts the layout reviews showed depend on another area's findings: power with mains, and the
#: manufacturing items with power. Each pair is judged in one group. A cross-reference between two areas of the catalogue does not make a
#: coupling, since the planner joins couplings transitively and coupling every linked pair leaves nine of twelve areas in one
#: group; a test fails when a coupling here has no cross-reference of the catalogue to support it.
COUPLED = (("POWER", "MAINS"), ("MFG", "POWER"))
#: Where the extracts the shared context holds come from.
PRODUCER = "task hw:review-folder"
#: The folder of views rendered during the round, which the declaration lists as added during the round.
ADDED = f"{review_folder.ADDED_VIEWS}/*"
IMAGES = (".png", ".jpg", ".jpeg")
#: The documents of the design folder the shared context holds are its .md and .yaml files.
DOCUMENT_SUFFIXES = (".md", ".yaml")

#: Plain data the kit reads: the variants a unit's replicas take in turn (the prompt as declared, and the terse hunt for
#: failures with the items and views the other way round) and the replicas by stakes.
replica_policy = {
    "variants": [{"id": "full"},
                 {"id": "hunt", "item_order": "reversed", "view_order": "reversed", "terse": True}],
    "replicas": {"low": 1, "normal": 2, "high": 3},
}
retrieval = True
#: The review's time target in seconds, so the planner sizes groups well clear of the bound the proof is held to.
WALL_SECONDS = 350

# --- The folder ---------------------------------------------------------------------------------

#: What the checks hold of the round they were resolved for: whether it is narrow, the items it judges, the unit each is
#: judged in and the cannot judge resolutions its folder records.
ROUND: Dict[str, Any] = {}


def read_text(review: str, path: str, what: str) -> str:
    try:
        with open(os.path.join(review, path), encoding="utf-8") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError) as error:
        raise ReviewFolderProblem(f"the review folder {review} holds no readable {what} ({path}: {error}); write the folder "
                                  "with the folder command")


def design_path(review: str) -> str:
    return review_folder.design_in(review)


def catalogue_split(review: str) -> Tuple[str, Dict[str, str]]:
    """The catalogue's introduction, the text before its first area heading, and each area's block by code: its heading
    line to the next area heading or the end of the catalogue."""
    text = read_text(review, METHOD, "method")
    section = board_history.LAYOUT_CATALOGUE.search(text)
    if section is None:
        raise ReviewFolderProblem(f"the method in the review folder {review} has no `## Layout practice catalogue` section, "
                                  "so there are no catalogue areas to take units from")
    lines = section.group(1).split("\n")
    starts = [index for index, line in enumerate(lines) if AREA.match(line)]
    if not starts:
        raise ReviewFolderProblem(f"the method in the review folder {review} has no catalogue area heading of the form "
                                  "`### <name> (<CODE>)`, so there are no units to take from it")
    intro = "\n".join(lines[:starts[0]]).strip()
    if not intro:
        raise ReviewFolderProblem(f"the layout practice catalogue in the method of the review folder {review} has no "
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


def areas(review: str) -> List[Tuple[str, str, List[str]]]:
    """Each area heading of the method's layout practice catalogue, in order: its code, its name and its items' identifiers."""
    text = read_text(review, METHOD, "method")
    section = board_history.LAYOUT_CATALOGUE.search(text)
    if section is None:
        raise ReviewFolderProblem(f"the method in the review folder {review} has no `## Layout practice catalogue` section, "
                                  "so there are no catalogue areas to take units from")
    found: List[Tuple[str, str, List[str]]] = []
    for line in section.group(1).split("\n"):
        heading, item = AREA.match(line), ITEM.match(line)
        if heading:
            found.append((heading.group(2), heading.group(1), []))
        elif item and found:
            found[-1][2].append(item.group(1))
    if not found:
        raise ReviewFolderProblem(f"the method in the review folder {review} has no catalogue area heading of the form "
                                  "`### <name> (<CODE>)`, so there are no units to take from it")
    return found


def own_items(review: str) -> List[str]:
    """The board's own items from the plan's table of them, none for the table's one `none` row."""
    design = design_path(review)
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


def checklist(review: str) -> List[str]:
    """The checklist: the catalogue's items in the method's order, then the board's own items, then the comparison with the
    plan and the free pass, which findings of no item are raised against."""
    try:
        items = [item for _, _, ids in areas(review) for item in ids]
        return items + own_items(review) + [PLAN_ENTRY]
    except ReviewFolderProblem as error:
        raise Refused([str(error)])


def unit_items(review: str, round_: Optional[Dict[str, Any]] = None) -> Dict[str, List[str]]:
    """Each unit of the round and the items it judges, in the order the units run."""
    given, own = areas(review), own_items(review)
    round_ = round_ or review_folder.read_round(review)
    known = {item for _, _, ids in given for item in ids} | set(own)
    if round_["kind"] == "narrow":
        listed = [entry["item"] for entry in round_["items"]]
        unknown = [item for item in listed if item not in known]
        if unknown:
            raise ReviewFolderProblem(f"the narrow round lists {', '.join(unknown)}, which {'is' if len(unknown) == 1 else 'are'} "
                                      "no item of the catalogue in the review folder's method or of the board's own items")
        found = {f"area-{code}": [item for item in listed if item in ids] for code, _, ids in given
                 if any(item in ids for item in listed)}
        if any(item in own for item in listed):
            found[OWN_UNIT] = [item for item in listed if item in own]
        return found
    found = {f"area-{code}": list(ids) for code, _, ids in given}
    if own:
        found[OWN_UNIT] = list(own)
    found[PLAN_UNIT] = [PLAN_ENTRY]
    return found


def unit_of(item: str, units: Dict[str, List[str]]) -> Optional[str]:
    for unit, ids in units.items():
        if item in ids:
            return unit
    return None


# --- The declaration ----------------------------------------------------------------------------


def shared_documents(review: str) -> Dict[str, Dict[str, Any]]:
    """The artefacts of the shared context, by name: the extracts, the round's records and indexes, the design's plan, rules
    table and records, and every rendered view and the placement view as an image. A file the folder command always writes
    and the folder lacks is named as missing."""
    design = design_path(review)
    found: Dict[str, Dict[str, Any]] = {}

    def add(path: str, kind: str = "text", producer: Optional[str] = None) -> None:
        entry: Dict[str, Any] = {"kind": kind, "source": path}
        if producer:
            entry["producer"] = producer
        found[path] = entry

    for extract in (review_folder.METHOD_EXTRACT, review_folder.LAYOUT_FACTS):
        if not os.path.isfile(os.path.join(review, extract)):
            raise ReviewFolderProblem(f"the review folder {review} holds no {extract}, which the shared context holds; write "
                                      "the folder with the folder command")
        add(extract, "extract", PRODUCER)
    held = read_text(review, review_folder.METHOD_EXTRACT, "method extract")
    for heading in review_folder.missing_sections(held):
        raise ReviewFolderProblem(f"the method extract {review_folder.METHOD_EXTRACT} in the review folder {review} has no "
                                  f"`## {heading}` section, which the shared context needs; write the folder with the folder command")
    for path in (review_folder.ROUND_FILE, review_folder.CHECK_REPORT, f"{review_folder.VIEWS}/index.txt",
                 f"{review_folder.PLACEMENT}/index.txt"):
        if not os.path.isfile(os.path.join(review, path)):
            raise ReviewFolderProblem(f"the review folder {review} holds no {path}, which the shared context holds; write the "
                                      "folder with the folder command")
        add(path)
    for path in (f"{review_folder.VIEWS}/facts.txt", f"{review_folder.PLACEMENT}/measures.txt"):
        if os.path.isfile(os.path.join(review, path)):
            add(path)
    names = sorted(name for name in os.listdir(os.path.join(review, design)) if name.endswith(DOCUMENT_SUFFIXES)
                   and os.path.isfile(os.path.join(review, design, name)))
    if PLAN not in names:
        raise ReviewFolderProblem(f"the review folder {review} holds no {PLAN} in {design}, which the shared context holds")
    for name in names:
        add(f"{design}/{name}")
    images = 0
    for folder in (review_folder.VIEWS, review_folder.PLACEMENT):
        for name in sorted(os.listdir(os.path.join(review, folder))):
            if name.lower().endswith(IMAGES) and os.path.isfile(os.path.join(review, folder, name)):
                add(f"{folder}/{name}", "image")
                images += 1
    if not images:
        raise ReviewFolderProblem(f"the review folder {review} holds no rendered view image (a PNG or JPEG in {review_folder.VIEWS}/ "
                                  f"or {review_folder.PLACEMENT}/), which the shared context holds; render the views")
    return found


PREFACE = """You are one reviewer of a round of a layout review of a finished printed circuit board. You did not design it, \
and you have no notes from whoever did. Work from the shared context above this message and the files in this folder. \
The shared context holds the method's layout review and views sections and the whole layout practice catalogue \
(method-extract.md), the board's plan ({plan}), its rules table (design-rules.md) and the records those name in \
{design}/, round.json (the round's number, its kind, the commit judged, the commands the views were rendered with and the \
pre-order check's lines), the pre-order check's report (check-report.txt), the view and placement indexes, every rendered \
view and the placement view as an image, and layout-facts.txt, which lists the positions, pads, segments, vias and zones of \
the layout file. You can read and search the folder and fetch a published document at its address; you cannot run a \
command, render a view or write anything.

Follow the "Layout review" section of the method, as written. Every view an item is judged on is among the images above; \
open nothing again that is already there. Where an item needs a view that is not among them, give it `cannot judge` and \
write in Why `needs <view>: <why the views rendered do not show it>`. For a rule-kind item whose figure rests on a \
published document, fetch it at the address the board's rules table gives, or find it from the manufacturer or publisher the \
row names, and judge the figure against it; a document you cannot fetch makes the item `cannot judge`.{earlier}{added}"""

DISCIPLINE = (
    "Before you judge an item, find in the shared context every view its Judged on names, on every tile whose board "
    "coordinates reach the place judged; Rests on may cite only views that are among them. Where an item asks whether a part "
    "stands beside, at, near or far from another, read both parts' positions and their pad positions from layout-facts.txt "
    "and state the distance in mm in Why; a view shows which parts to compare, not how far apart they are.")

OUTPUT = """Verdicts has one row for each item you judge, with the columns {verdicts}. Verdict is one of pass, fail, not \
applicable or cannot judge, as the method's step 2 gives them; Kind and Severity are the item's own; Rests on and Why are \
written as that step gives them. A fail's Why is `finding {round}.<n>`, the number of the finding it raises in your Findings \
table, or the number of the finding an earlier round raised and closed by a reason, written with that round's own number.

Plan and free pass has the one column Note: one row for each thing you record of the comparison with the plan and the free \
pass, one line each; leave it empty unless you see a plan row of your items the layout does not meet.

Findings has the columns {findings}. Number your findings 1, 2, 3 in the order you raise them, in Finding, as whole numbers. \
Item is the checklist entry that raised the finding: the item's identifier, or {sentinel} for a finding of the comparison \
with the plan or of the free pass. Raised by, Severity and What and where are as step 4 gives them, What and where naming \
the view by its name in the views' index and the board place as (x, y) in the board coordinates its caption states. Rule is \
your judgement as step 5 gives it, `yes` or `no` with the rule and its form or why none can state it. Added as and Closed \
by are left as "". Planning shortfall is step 6's: `—` when step 6 gives it, and otherwise the word `shortfall`, followed by \
why the plan row, followed as written, would not have met the item; write it from the row's text and the layout alone. Write \
a finding of this round wherever you cite it as `finding {round}.<n>`, with your own number, and never write an earlier \
round's finding in that form with this round's number."""

PLAN_SCOPE = """This unit judges no catalogue item. Compare the layout with {plan} as step 3 gives it: each region's bounds and \
what it holds, each connector's edge and position, each `yes` row of the plan table and each of the board's own items' How the \
layout meets it. Then make the free pass over every view. Record what you compared in Plan and free pass, and each plan row \
the layout does not meet and each free-pass sighting as a finding whose Item is {sentinel}. The one item below stands for this \
comparison: give it one Verdicts row with Kind `comparison`, Severity `—`, Verdict `pass` when you raise no finding and `fail` \
when you raise any (its Why `finding {round}.<n>` for the first), and Rests on the plan and the views you compared."""

AREA_TEMPLATE = """{preface}

Your unit: {unit}

{scope}
{items}
{resolved}
{discipline}

{area}

{output}

{schema}"""

PLAN_TEMPLATE = """{preface}

Your unit: {unit}

{scope}
{items}

{output}

{schema}"""

SCHEMA = {
    "tables": [
        {"name": "Verdicts", "columns": VERDICT_TABLE, "key": "Item", "verdict_column": "Verdict", "verdicts": list(VERDICTS)},
        {"name": "Plan and free pass", "columns": ["Note"]},
        {"name": "Findings", "columns": FINDING_TABLE, "key": "Item", "numeric": ["Finding"]},
    ],
    "findings": {"table": "Findings", "number": "Finding",
                 "citations": [["Verdicts", "Why"], ["Plan and free pass", "Note"]], "citation": CITATION.pattern},
}


def preface(review: str, round_: Dict[str, Any], resolutions: Sequence[Dict[str, str]]) -> str:
    design = design_path(review)
    earlier = ""
    if round_["number"] > 1:
        earlier = (f" This is round {round_['number']}: the earlier rounds of the review record are in {design}/"
                   f"{review_folder.RECORD}, and a verdict row may cite a finding an earlier round raised and closed by a "
                   "reason, written `finding <that round>.<n>`.")
    added = (f" Views rendered during the round to resolve a cannot judge are in {review_folder.ADDED_VIEWS}/; they are not "
             "among the images above, so open them with Read." if resolutions else "")
    return PREFACE.format(design=design, plan=PLAN, earlier=earlier, added=added)


def output_spec(round_: Dict[str, Any]) -> str:
    return OUTPUT.format(verdicts=", ".join(VERDICT_TABLE), findings=", ".join(FINDING_TABLE), round=round_["number"],
                         sentinel=PLAN_ENTRY)


def resolved_text(listed: Sequence[str], resolutions: Sequence[Dict[str, str]]) -> str:
    """What a unit run again is told of the views added for its items' cannot judge, none for a unit with no such item."""
    lines = []
    for entry in resolutions:
        if entry["item"] in listed:
            lines.append(f"- {entry['item']}: it was `cannot judge` because {entry['why']} The view added for it is "
                         f"{entry['view']} (rendered with: {entry['command']}). Open it with Read and judge the item again.")
    return ("\nItems whose cannot judge was resolved by an added view:\n" + "\n".join(lines) + "\n") if lines else ""


def unit_values(review: str, round_: Dict[str, Any], units: Dict[str, List[str]],
                resolutions: Sequence[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    """The values each unit's template is filled with: its preface, scope, area block and output form."""
    given = preface(review, round_, resolutions)
    blocks = catalogue_split(review)[1]
    reasons = {entry["item"]: entry["reason"] for entry in round_.get("items", [])}
    found: Dict[str, Dict[str, str]] = {}
    for unit, listed in units.items():
        if unit == PLAN_UNIT:
            found[unit] = {"preface": given, "scope": PLAN_SCOPE.format(plan=PLAN, sentinel=PLAN_ENTRY, round=round_["number"]),
                           "output": output_spec(round_)}
            continue
        if round_["kind"] == "narrow":
            scope = ("This round is narrow. Judge only the items below, each by the rules of step 2, and give a verdict to each "
                     "of them and to no other item. Each is listed for the reason given:\n"
                     + "".join(f"- {item}: {reasons[item]}\n" for item in listed) + "\nThe items:")
        else:
            scope = ("This round is full. Judge each of these items, in the order given, and give one verdict row to each of "
                     "them and to no other item:")
        if unit == OWN_UNIT:
            area = (f"These are the board's own items, in the table of them in {design_path(review)}/{PLAN}; each is judged on "
                    "its own Passes and Judged on.")
        else:
            block = blocks[unit[len("area-"):]]
            if round_["kind"] == "narrow":
                block = listed_items_only(block, listed)
            area = ("The catalogue section for your area follows. The other areas of the catalogue are in the shared context "
                    "for reference; judge only your items.\n\n" + block)
        found[unit] = {"preface": given, "scope": scope, "resolved": resolved_text(listed, resolutions),
                       "discipline": DISCIPLINE, "area": area.rstrip(), "output": output_spec(round_)}
    return found


def expected_tokens(unit: str, listed: Sequence[str]) -> int:
    """The output a unit is expected to give: a verdict row for each item and a little over for findings and notes."""
    return 900 if unit == PLAN_UNIT else 200 + 130 * len(listed)


def coupled_to(unit: str, units: Dict[str, List[str]]) -> List[str]:
    """The other units of the round the declaration couples a unit with: the area pairs of COUPLED whose two areas both have a
    unit in the round."""
    if not unit.startswith("area-"):
        return []
    code = unit[len("area-"):]
    others = []
    for first, second in COUPLED:
        for mine, theirs in ((first, second), (second, first)):
            if mine == code and f"area-{theirs}" in units:
                others.append(f"area-{theirs}")
    return sorted(set(others), key=list(units).index)


def build_declaration(review: str) -> Dict[str, Any]:
    round_ = review_folder.read_round(review)
    method = read_text(review, METHOD, "method")
    for heading in review_folder.METHOD_SECTIONS:
        if review_folder.method_section(method, heading) is None:
            raise ReviewFolderProblem(f"the method in the review folder {review} has no `## {heading}` section, which the "
                                      "shared context needs")
    units = unit_items(review, round_)
    resolutions = review_folder.read_resolutions(review)
    documents = shared_documents(review)
    values = unit_values(review, round_, units, resolutions)
    held = {"narrow": round_["kind"] == "narrow", "units": {unit: list(listed) for unit, listed in units.items()},
            "resolutions": resolutions}
    ROUND.clear()
    ROUND.update(held)
    declared = {}
    for unit, listed in units.items():
        declared[unit] = {"items": list(listed), "template": "plan" if unit == PLAN_UNIT else "area",
                          "needs": sorted(documents), "couples_with": coupled_to(unit, units),
                          "expected_output_tokens": expected_tokens(unit, listed), "values": values[unit]}
    return {"artefacts": documents, "templates": {"area": AREA_TEMPLATE, "plan": PLAN_TEMPLATE}, "units": declared,
            "schema": SCHEMA, "deny": ["designer-notes*", "session*"], "budget": {"wall_s": WALL_SECONDS},
            "added_during_round": [ADDED]}


def declaration(review: str) -> Dict[str, Any]:
    """The declaration of the round in the review folder: its units, the shared context and the tables. The round's fields are
    checked here, before any session starts, since the checks receive the merged tables alone."""
    try:
        return build_declaration(review)
    except ReviewFolderProblem as error:
        raise Refused([str(error)])


# --- The checks ---------------------------------------------------------------------------------


def note_problems(tables: Dict[str, Any]) -> List[str]:
    found = []
    for number, row in enumerate(tables["Plan and free pass"]["rows"], 1):
        if not isinstance(row["Note"], str) or not row["Note"].strip():
            found.append(f"the Plan and free pass table's row {number} is empty; a note says what was compared or seen")
    return found


def checks(tables: Dict[str, Any]) -> List[str]:
    """What the merge refuses: an item with no verdict row or two, a verdict for an item the round does not judge, a cannot
    judge still held, a recorded cannot judge for an item the round has no verdict row for, and a full round with no note of
    the comparison with the plan."""
    if not ROUND:
        return ["the layout caller's checks ran before its declaration was resolved for a review folder, so the items the round "
                "judges are not known; resolve the declaration first"]
    units, narrow = ROUND["units"], ROUND["narrow"]
    expected = [item for unit, listed in units.items() if unit != PLAN_UNIT for item in listed]
    judged = set(expected) | ({PLAN_ENTRY} if PLAN_UNIT in units else set())
    found = note_problems(tables)
    rows = tables["Verdicts"]["rows"]
    counts = Counter(row["Item"] for row in rows)
    for item in expected + ([PLAN_ENTRY] if PLAN_UNIT in units else []):
        unit = unit_of(item, units)
        if counts[item] == 0:
            found.append(f"item {item} has no verdict row; every item the round judges has exactly one"
                         + (f" (judge it in unit {unit} and run that unit again with --rerun)" if unit else ""))
        elif counts[item] > 1:
            found.append(f"item {item} has {counts[item]} verdict rows; every item the round judges has exactly one")
    for item in counts:
        if item not in judged:
            found.append(f"a verdict row for {item}, which this round does not judge; a verdict is accepted only for "
                         + ("an item the narrow round lists" if narrow else "an item of the checklist"))
    for entry in ROUND["resolutions"]:
        if entry["item"] not in judged:
            found.append(f"the folder records a cannot judge for {entry['item']!r}, which is not an item this round judges; "
                         "the item was mistyped when the view was added, so add the view again with the item's exact name")
        elif counts[entry["item"]] == 0:
            found.append(f"the folder records a cannot judge for {entry['item']}, which has no verdict row in this round; "
                         "run the unit that judges it again with --rerun")
    for row in rows:
        if row["Verdict"] == "cannot judge":
            unit = unit_of(row["Item"], units)
            asks = re.match(r"needs (.+?):", row["Why"])
            found.append(f"item {row['Item']} is still cannot judge, and the method resolves it within the round; its Why asks "
                         f"for {asks.group(1) if asks else repr(row['Why'])}: render that view, add it with the folder "
                         "command's --add-view and run "
                         + (f"unit {unit}" if unit else "the unit that judged it") + " again with --rerun")
    if PLAN_UNIT in units and not tables["Plan and free pass"]["rows"]:
        found.append(f"unit {PLAN_UNIT} gave no note of the comparison with the plan and the free pass, which a full round "
                     "records; run it again with --rerun")
    return found


# --- The place of a finding, the round's label and its earlier findings ---------------------------


def place(row: Dict[str, Any]) -> Optional[str]:
    """The view and the board place a finding's What and where cites, or None when it names either not at all."""
    text = str(row["What and where"])
    view, point = VIEW_NAME.search(text), POINT.search(text)
    if view is None or point is None:
        return None
    return f"{view.group(1).rstrip('.,;:')} ({float(point.group(1)):g}, {float(point.group(2)):g})"


def round_label(review: str) -> str:
    return str(review_folder.read_round(review)["number"])


def earlier_findings(review: str) -> List[Tuple[str, int]]:
    """The (round, number) pairs of the findings the review folder's earlier rounds hold, none for a first round."""
    path = os.path.join(design_path(review), review_folder.RECORD)
    if not os.path.isfile(os.path.join(review, path)):
        return []
    found = []
    for body in board_review_history.round_bodies(read_text(review, path, "review record")).values():
        header, rows = board_review_history.Round(body).findings
        for row in rows if "Finding" in header else []:
            mark = re.fullmatch(r"(\d+)\.(\d+)", dict(zip(header, row))["Finding"])
            if mark:
                found.append((mark.group(1), int(mark.group(2))))
    return found


# --- The rendered round -------------------------------------------------------------------------


def verdict_row(row: Dict[str, Any], entries: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """A verdict row as the record gives it; one that resolves a cannot judge records the cannot judge, then each view
    added for it, then the verdict reached, and the Why the unit gave it after the cannot judge's own."""
    if not entries:
        return row
    steps = [part for entry in entries for part in ("cannot judge", entry["view"])]
    asked = " ".join(f"Cannot judge: {entry['why']}." for entry in entries)
    return {**row, "Verdict": "; ".join(steps + [row["Verdict"]]), "Why": f"{asked} {row['Why']}"}


def render(review: str, tables: Dict[str, Any]) -> Dict[str, str]:
    """The merged round as the method gives it, written as round-<n>.md: the round heading, the opening fields, the Verdicts
    table, the Plan and free pass section and the Findings table or the line saying no finding was raised."""
    try:
        round_ = review_folder.read_round(review)
        resolutions = review_folder.read_resolutions(review)
        order = {item: index for index, item in enumerate(checklist(review))}
    except ReviewFolderProblem as error:
        raise Refused([str(error)])
    entries: Dict[str, List[Dict[str, Any]]] = {}
    for entry in resolutions:
        entries.setdefault(entry["item"], []).append(entry)
    rows = sorted((row for row in tables["Verdicts"]["rows"] if row["Item"] != PLAN_ENTRY), key=lambda row: order[row["Item"]])
    number = round_["number"]
    views = round_["views"] + [f"{entry['command']} (added view: {entry['view']})" for entry in resolutions]
    text = [f"## Round {number}", "", f"- **Board judged**: {round_['commit']}", "- **Views**: the commands the views were "
            "rendered with, as run, and any view rendered in the round to resolve a cannot judge, with its command:", "",
            "```", *views, "```", "", "- **Pre-order check**: the board's `DESIGN` line and every `FIGURE` and "
            "`VIOLATION` line under it:", "", "```", *round_["check"], "```", "", f"- **Round kind**: {round_['kind']}"]
    if round_["kind"] == "narrow":
        text += [f"- **Changed regions**: {'; '.join(round_['regions'])}", "- **Items judged**:"]
        text += [f"  - {entry['item']}: {entry['reason']}" for entry in round_["items"]]
        text += [f"- **Items not judged**: {round_['others']}"]
    text += ["", "### Verdicts", ""] + results.table_lines(VERDICT_TABLE, [verdict_row(row, entries.get(row["Item"], ())) for row in rows])
    notes = [" ".join(str(row["Note"]).split()) for row in tables["Plan and free pass"]["rows"]]
    text += ["", "### Plan and free pass", ""]
    text += [f"- {note}" for note in notes] or [
        "This round judges only the items it lists, and no comparison with the plan or free pass beyond them was made."]
    findings = tables["Findings"]["rows"]
    text += ["", "### Findings", ""]
    if findings:
        text += results.table_lines(RECORD_FINDING_TABLE, [{**row, "Finding": f"{number}.{row['Finding']}"} for row in findings])
    else:
        text += [board_review_history.NO_FINDINGS]
    return {f"round-{number}.md": "\n".join(text) + "\n"}
