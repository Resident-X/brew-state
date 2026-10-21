#!/usr/bin/env python3
"""The layout review as a caller of the review fan-out command (review_fan_out.py --caller layout).

A layout review round, full or narrow, is judged by one reviewer for each area
heading of the layout practice catalogue in the review folder's own method, one
for the board's own items when the plan's table of them has rows, and one for the
comparison with the plan and the free pass over every view, which belong to no one
area. A narrow round's units are the areas its listed items fall in, and each
reviewer judges only the listed items of its area; a narrow round that falls in
one area is one unit, which the command judges in its setup session.

The review folder is the one review_folder.py writes. The round's own fields, its
number, kind, commit judged, views and the pre-order check's lines, and for a
narrow round its listed items, changed regions and why-others line, are read from
the round file there, because the merge has no model to write them. The merge
gives every item of a full round, or every listed item of a narrow one, exactly one
verdict row, refuses a round whose fields are missing or malformed and one that
still holds a cannot judge, numbers this round's findings with the item units'
findings in the checklist's order and the comparison and free-pass unit's after,
in its own order, reports findings that cite one view and board place and keeps
both, and writes the round as the method gives it in round-<n>.md, to be appended
below the record's earlier rounds and committed by whoever started the round. Rule
kind items rest on the check's report and the rules table as the method says; the
merge does not judge them, or whether any verdict is right.

A reviewer is granted the read tools and WebFetch, which fetches a published
document at its address and writes nothing, since a rule-kind item whose figure
rests on a document needs it; the setup session keeps the read tools alone.
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

ReviewFolderProblem = review_folder.ReviewFolderProblem
METHOD = "docs/board-design-method.md"
PLAN = "layout-plan.md"
#: The unit that compares the layout with the plan and makes the free pass, and the one for the board's own items.
PLAN_UNIT = "plan-and-free-pass"
OWN_UNIT = "board-items"
#: The checklist entry a finding of the comparison and the free pass is raised against: they belong to no item.
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

SETUP_PROMPT = (
    "The documents and records of this review follow, for the sessions that continue from this one. In this session judge "
    "nothing and open nothing beyond them. Take the method's layout review sections and the plan in full; the catalogue "
    "section for your area comes with your unit.")

#: What a unit with items is told after its item list: the views and positions its verdicts rest on are read in its own session.
DISCIPLINE = (
    "Before you judge an item, open in this session every view its Judged on names, on every tile whose board coordinates "
    "reach the place judged; the documents above are the method and the records, not views, and Rests on may cite only "
    "views you opened. Where an item asks whether a part stands beside, at, near or far from another, read both parts' "
    "positions and their pad positions from the layout file (the `(footprint`, `(at` and the net's segments) and state the "
    "distance in mm in Why; a view shows which parts to compare, not how far apart they are.")

#: The records at the review folder's root the setup session is given after the method's extracts, in this order, each where it exists.
ROOT_DOCUMENTS = ("round.json", "check-report.txt", "views/index.txt", "views/facts.txt", "placement/index.txt",
                  "placement/measures.txt")
#: The design folder's documents given first, in this order, before its other .md and .yaml files.
DESIGN_DOCUMENTS = ("layout-plan.md", "design-rules.md", "layout-review.md")
#: The method sections every unit needs, by heading, and the label each is given in the setup.
REVIEW_SECTION = "Layout review"
VIEWS_SECTION = "Layout review views"
CATALOGUE_HEADING = "Layout practice catalogue"


def method_section(review: str, heading: str) -> str:
    """The method's `## <heading>` section in the review folder, up to the next level-two heading, by heading."""
    text = read_text(review, METHOD, "method")
    found = re.search(r"^## " + re.escape(heading) + r"[ \t]*\n.*?(?=^## |\Z)", text, re.M | re.S)
    if found is None:
        raise ReviewFolderProblem(f"the method in the review folder {review} has no `## {heading}` section, which every "
                                  "unit's setup needs")
    return found.group(0).rstrip() + "\n"


def catalogue_split(review: str) -> Tuple[str, Dict[str, str]]:
    """The catalogue's introduction, the text before its first area heading, and each area's block by code: its heading
    line to the next area heading or the end of the catalogue."""
    text = read_text(review, METHOD, "method")
    section = board_history.LAYOUT_CATALOGUE.search(text)
    if section is None:
        raise ReviewFolderProblem(f"the method in the review folder {review} has no `## {CATALOGUE_HEADING}` section, "
                                  "so there are no catalogue areas to take units from")
    lines = section.group(1).split("\n")
    starts = [index for index, line in enumerate(lines) if AREA.match(line)]
    if not starts:
        raise ReviewFolderProblem(f"the method in the review folder {review} has no catalogue area heading of the form "
                                  "`### <name> (<CODE>)`, so there are no units to take from it")
    intro = "\n".join(lines[:starts[0]]).strip()
    if not intro:
        raise ReviewFolderProblem(f"the layout practice catalogue in the method of the review folder {review} has no "
                                  "introduction before its first area heading, which every unit's setup needs")
    blocks = {}
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        blocks[AREA.match(lines[start]).group(2)] = "\n".join(lines[start:end]).strip() + "\n"
    return f"## {CATALOGUE_HEADING}\n\n{intro}\n", blocks


def listed_items_only(block: str, listed: Sequence[str]) -> str:
    """An area's block with only the items of `listed`: its heading and the text before its first item, then each listed
    item's own text, so a narrow round's prompt names no item the round does not judge."""
    parts = re.split(r"(?m)^(?=#### )", block)
    kept = [parts[0]] + [part for part in parts[1:] if (ITEM.match(part) and ITEM.match(part).group(1) in listed)]
    return "".join(kept).rstrip() + "\n"


def SETUP_DOCUMENTS(review: str) -> List[Any]:
    """What every unit needs, the same for every unit: the method's layout review section, its views section and the
    catalogue's introduction as (label, text) extracts, then the paths, relative to the review folder, of the records."""
    extracts = [(f"{METHOD} (section: {REVIEW_SECTION})", method_section(review, REVIEW_SECTION)),
                (f"{METHOD} (section: {VIEWS_SECTION})", method_section(review, VIEWS_SECTION)),
                (f"{METHOD} (section: {CATALOGUE_HEADING}, introduction only; each unit's prompt holds the area it judges)",
                 catalogue_split(review)[0])]
    found = [path for path in ROOT_DOCUMENTS if os.path.isfile(os.path.join(review, path))]
    design = design_path(review)
    named = [path for path in DESIGN_DOCUMENTS if os.path.isfile(os.path.join(review, design, path))]
    others = sorted(name for name in os.listdir(os.path.join(review, design)) if name.endswith((".md", ".yaml"))
                    and name not in DESIGN_DOCUMENTS and os.path.isfile(os.path.join(review, design, name)))
    return extracts + found + [os.path.normpath(os.path.join(design, name)) for name in named + others]

TOOLS = ("Read", "Glob", "Grep", "WebFetch")
#: The most reviewers at once: the full unit count until the live demonstration sets it from what that run observes.
BOUND = 14

TABLES = {
    "Verdicts": {"columns": VERDICT_TABLE, "verdict_column": "Verdict", "verdicts": VERDICTS},
    "Plan and free pass": {"columns": ["Note"]},
    "Findings": {"columns": FINDING_TABLE},
}


# --- The folder ---------------------------------------------------------------------------------


def read_text(review: str, path: str, what: str) -> str:
    try:
        with open(os.path.join(review, path), encoding="utf-8") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError) as error:
        raise ReviewFolderProblem(f"the review folder {review} holds no readable {what} ({path}: {error}); write the folder "
                                  "with the folder command")


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


def checklist(review: str) -> List[str]:
    """The checklist: the catalogue's items in the method's order, then the board's own items, then the comparison with the
    plan and the free pass, which findings of no item are raised against."""
    items = [item for _, _, ids in areas(review) for item in ids]
    return items + own_items(review) + [PLAN_ENTRY]


def unit_items(review: str) -> Dict[str, List[str]]:
    """Each unit of the round and the items it judges, in the order the units run."""
    given, own = areas(review), own_items(review)
    round_ = review_folder.read_round(review)
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
    found[PLAN_UNIT] = []
    return found


def units(review_folder_path: str) -> List[str]:
    return list(unit_items(review_folder_path))


# --- The prompts --------------------------------------------------------------------------------

PREFACE = """You are one reviewer of a round of a layout review of a finished printed circuit board. You did not design \
it, and you have no notes from whoever did. Work only from the files in this folder. You can read and search them, and \
fetch a published document at its address; you cannot run a command, render a view or write anything.

Follow the "Layout review" section of docs/board-design-method.md, as written, for the board design in {design}/ \
(its project, schematic, layout and rules files, its {plan} and its design-rules.md, and every record those name). The \
round's own fields are in round.json: its number, its kind, the commit judged, the commands the views were rendered with \
and the pre-order check's lines. The views the method names are rendered already: views/ (views/index.txt lists every \
image with its caption fields, and views/facts.txt gives every net's facts), placement/ (placement/index.txt and \
placement/measures.txt), {added}and the pre-order check's report is check-report.txt. Open each image a verdict rests on \
and read the board coordinates from its caption. Where an item needs a view that is not among them, give it `cannot \
judge` and write in Why `needs <view>: <why the views rendered do not show it>`. For a rule-kind item whose figure rests on \
a published document, fetch it at the address the board's rules table gives, or find it from the manufacturer or \
publisher the row names, and judge the figure against it; a document you cannot fetch makes the item `cannot judge`.{earlier}
"""

OUTPUT = """Return exactly one JSON object and nothing else: {{"tables": {{"Verdicts": [...], "Plan and free pass": [...], \
"Findings": [...]}}}}. Each table is a list of rows, each row an object with every column of its table and no other, each \
cell text or a number, never null, true or false, and no cell holds a line break or a vertical bar.

- Verdicts has the columns {verdicts}. Verdict is one of pass, fail, not applicable or cannot judge, as the method's step \
2 gives them; Kind and Severity are the item's own; Rests on and Why are written as that step gives them. A fail's Why is \
`finding {round}.<n>`, the number of the finding it raises in your Findings table, or the number of the finding an earlier \
round raised and closed by a reason, written with that round's own number.
- Plan and free pass has the one column Note: one row for each thing you record of the comparison with the plan and the \
free pass, one line each.
- Findings has the columns {findings}. Number your findings 1, 2, 3 in the order you raise them, in Finding, as whole \
numbers. Item is the checklist entry that raised the finding: the item's identifier, or {sentinel} for a finding of the \
comparison with the plan or of the free pass. Raised by, Severity and What and where are as step 4 gives them, What and \
where naming the view by its name in the views' index and the board place as (x, y) in the board coordinates its caption \
states. Rule is your judgement as step 5 gives it, `yes` or `no` with the rule and its form or why none can state it. \
Added as and Closed by are left as "". Planning shortfall is step 6's: `—` when step 6 gives it, and otherwise the word \
`shortfall`, followed by why the plan row, followed as written, would not have met the item; write it from the row's text \
and the layout alone. Write a finding of this round wherever you cite it as `finding {round}.<n>`, with your own number, \
and never write an earlier round's finding in that form with this round's number.
"""


def design_path(review: str) -> str:
    return review_folder.design_in(review)


def prompt_preface(review: str, round_: Dict[str, Any]) -> str:
    design = design_path(review)
    added = "added-views/ (views rendered during the round to resolve a cannot judge), " if os.path.isdir(
        os.path.join(review, review_folder.ADDED_VIEWS)) else ""
    earlier = ""
    if round_["number"] > 1:
        earlier = (f" This is round {round_['number']}: the earlier rounds of the review record are in {design}/"
                   f"{review_folder.RECORD}, and a verdict row may cite a finding an earlier round raised and closed by a "
                   "reason, written `finding <that round>.<n>`.")
    return PREFACE.format(design=design, plan=PLAN, added=added, earlier=earlier)


def output_spec(round_: Dict[str, Any]) -> str:
    return OUTPUT.format(verdicts=", ".join(VERDICT_TABLE), findings=", ".join(FINDING_TABLE), round=round_["number"],
                         sentinel=PLAN_ENTRY)


def unit_prompt(unit: str, review_folder_path: str) -> str:
    """The unit's prompt: the unit, the items it judges and, in a narrow round, only the listed items of its area."""
    found = unit_items(review_folder_path)
    if unit not in found:
        raise ReviewFolderProblem(f"{unit!r} is not a unit of this round; the units are {', '.join(found)}")
    round_ = review_folder.read_round(review_folder_path)
    text = prompt_preface(review_folder_path, round_) + f"\nYour unit: UNIT={unit}\n"
    if unit == PLAN_UNIT:
        text += ("\nYou judge no item. Compare the layout with layout-plan.md as step 3 gives it: each region's bounds and "
                 "what it holds, each connector's edge and position, each `yes` row of the plan table and each of the board's "
                 "own items' How the layout meets it. Then make the free pass over every view. Record what you compared "
                 "in Plan and free pass, and each plan row the layout does not meet and each free-pass sighting as a finding. "
                 "Return an empty Verdicts table.\n")
    else:
        listed = found[unit]
        if round_["kind"] == "narrow":
            reasons = {entry["item"]: entry["reason"] for entry in round_["items"]}
            text += ("\nThis round is narrow. Judge only these items, each by the rules of step 2, and give a verdict to "
                     "each of them and to no other item:\n" + "".join(f"- {item}: {reasons[item]}\n" for item in listed))
        else:
            text += ("\nThis round is full. Judge each of these items, in this order, and give one verdict row to each of them "
                     "and to no other item: " + ", ".join(listed) + ".\n")
        text += "\n" + DISCIPLINE + "\n"
        if unit.startswith("area-"):
            block = catalogue_split(review_folder_path)[1][unit[len("area-"):]]
            if round_["kind"] == "narrow":
                block = listed_items_only(block, listed)
            text += ("\nThe catalogue section for your area follows. The other areas of the catalogue are not given to you; "
                     "judge only your items.\n\n" + block + "\n")
        if unit == OWN_UNIT:
            text += (f"These are the board's own items, in the table of them in {design_path(review_folder_path)}/{PLAN}; "
                     "each is judged on its own Passes and Judged on.\n")
        text += "\nReturn an empty Plan and free pass table unless you see a plan row of your items the layout does not meet.\n"
    return text + "\n" + output_spec(round_)


def single_prompt(review_folder_path: str) -> str:
    """The prompt of one reviewer judging the whole round, as the method has it done without units."""
    round_ = review_folder.read_round(review_folder_path)
    text = prompt_preface(review_folder_path, round_)
    scope = ("every item of the checklist: every item of the \"Layout practice catalogue\" in that document together with the "
             "board's own items in the plan" if round_["kind"] == "full" else
             "only the items round.json lists, each by the rules of step 2")
    return (text + f"\nJudge {scope}, then compare the layout with the plan and make the free pass over every view. Return the "
            f"round as the record the method's steps lay out, in Markdown: the heading `## Round {round_['number']}`, the "
            "opening lines round.json gives, `### Verdicts` with one row for each item judged, `### Plan and free pass` in "
            "prose, and `### Findings` with one row for each finding, numbered `<round>.<n>`, or the line `This round raises "
            "no finding.` Leave Added as and Closed by empty, give Rule your judgement as step 5 gives it, and write Planning "
            "shortfall as step 6 gives it. Return nothing but the record.\n")


# --- The merge ----------------------------------------------------------------------------------


def unit_of(item: str, given: Sequence[Tuple[str, str, List[str]]]) -> Optional[str]:
    for code, _, ids in given:
        if item in ids:
            return f"area-{code}"
    return OWN_UNIT if OWN_ITEM.fullmatch(item) else None


def note_problems(tables: Dict[str, Any]) -> List[str]:
    found = []
    for number, row in enumerate(tables["Plan and free pass"]["rows"], 1):
        if not isinstance(row["Note"], str) or not row["Note"].strip():
            found.append(f"the Plan and free pass table's row {number} is empty; a note says what was compared or seen")
    return found


def CHECK(review: str, order: Sequence[str], tables: Dict[str, Any]) -> List[str]:
    """What the merge refuses: round fields that are missing or malformed, an item with no verdict row or two, a verdict for
    an item the round does not judge, a cannot judge still held, a recorded cannot judge for an item the round has no verdict row for, and a full round with no note of the comparison."""
    try:
        round_ = review_folder.read_round(review)
        given = areas(review)
        expected = ([entry["item"] for entry in round_["items"]] if round_["kind"] == "narrow"
                    else [item for _, _, ids in given for item in ids] + own_items(review))
    except ReviewFolderProblem as error:
        return [str(error)]
    found = note_problems(tables)
    rows = tables["Verdicts"]["rows"]
    counts = Counter(row["Item"] for row in rows)
    for item in expected:
        if counts[item] == 0:
            unit = unit_of(item, given)
            found.append(f"item {item} has no verdict row; every item the round judges has exactly one"
                         + (f" (judge it in unit {unit} and run that unit again with --rerun)" if unit else ""))
        elif counts[item] > 1:
            found.append(f"item {item} has {counts[item]} verdict rows; every item the round judges has exactly one")
    for item in counts:
        if item not in expected:
            found.append(f"a verdict row for {item}, which this round does not judge; a verdict is accepted only for "
                         + ("an item the narrow round lists" if round_["kind"] == "narrow" else "an item of the checklist"))
    for entry in round_.get("cannot_judge", []):
        if entry["item"] not in expected:
            found.append(f"the folder records a cannot judge for {entry['item']!r}, which is not an item this round judges; "
                         "the item was mistyped when the view was added, so add the view again with the item's exact name")
        elif counts[entry["item"]] == 0:
            found.append(f"the folder records a cannot judge for {entry['item']}, which has no verdict row in this round; "
                         "run the unit that judges it again with --rerun")
    for row in rows:
        if row["Verdict"] == "cannot judge":
            unit = unit_of(row["Item"], given)
            asks = re.match(r"needs (.+?):", row["Why"])
            found.append(f"item {row['Item']} is still cannot judge, and the method resolves it within the round; its Why asks "
                         f"for {asks.group(1) if asks else repr(row['Why'])}: render that view, add it with the folder "
                         "command's --add-view and run "
                         + (f"unit {unit}" if unit else "the unit that judged it") + " again with --rerun")
    if round_["kind"] == "full" and not tables["Plan and free pass"]["rows"]:
        found.append(f"unit {PLAN_UNIT} gave no note of the comparison with the plan and the free pass, which a full round "
                     "records; run it again with --rerun")
    return found


CITATION = re.compile(r"(?<![\w.])[Ff]inding (?P<round>\d+)\.(?P<number>\d+)\b")
VIEW_NAME = re.compile(r"\b((?:layer|net|crop|classes|assembly|3d|placement)[\w.+/-]*)")
POINT = re.compile(r"\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)")


def place_of(row: Dict[str, Any]) -> Optional[str]:
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
    path = os.path.join(review_folder.design_in(review), review_folder.RECORD)
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


FINDINGS = {"table": "Findings", "number": "Finding", "item": "Item", "checklist": checklist,
            "citations": [("Verdicts", "Why"), ("Plan and free pass", "Note")], "citation": CITATION,
            "round": round_label, "earlier": earlier_findings, "key": place_of}


# --- The rendered round -------------------------------------------------------------------------


def table_cell(value: Any) -> str:
    """A cell as the record's table can hold it: each run of line breaks becomes one space and each run of vertical bars
    one slash with a single space either side, so `a | b` is written `a / b`."""
    text = re.sub(r"[ \t]*[\r\n]+[ \t]*", " ", str(value))
    return re.sub(r"\s*\|(?:\s*\|)*\s*", " / ", text).strip()


def table_lines(columns: Sequence[str], rows: Sequence[Dict[str, Any]]) -> List[str]:
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    return lines + ["| " + " | ".join(table_cell(row[column]) for column in columns) + " |" for row in rows]


def verdict_row(row: Dict[str, Any], entries: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """A verdict row as the record gives it; one that resolves a cannot judge records the cannot judge, then each view the
    round's starter added for it, then the verdict reached, and the Why the unit gave it after the cannot judge's own."""
    if not entries:
        return row
    steps = [part for entry in entries for part in ("cannot judge", entry["view"])]
    asked = " ".join(f"Cannot judge: {entry['why']}." for entry in entries)
    return {**row, "Verdict": "; ".join(steps + [row["Verdict"]]), "Why": f"{asked} {row['Why']}"}


def RENDER(review: str, tables: Dict[str, Any]) -> Dict[str, str]:
    """The merged round as the method gives it, written as round-<n>.md: the round heading, the opening fields, the Verdicts
    table, the Plan and free pass section and the Findings table or the line saying no finding was raised."""
    round_ = review_folder.read_round(review)
    order = {item: index for index, item in enumerate(checklist(review))}
    entries: Dict[str, List[Dict[str, Any]]] = {}
    for entry in round_.get("cannot_judge", []):
        entries.setdefault(entry["item"], []).append(entry)
    rows = sorted(tables["Verdicts"]["rows"], key=lambda row: order[row["Item"]])
    number = round_["number"]
    text = [f"## Round {number}", "", f"- **Board judged**: {round_['commit']}", "- **Views**: the commands the views were "
            "rendered with, as run, and any view rendered in the round to resolve a cannot judge, with its command:", "",
            "```", *round_["views"], "```", "", "- **Pre-order check**: the board's `DESIGN` line and every `FIGURE` and "
            "`VIOLATION` line under it:", "", "```", *round_["check"], "```", "", f"- **Round kind**: {round_['kind']}"]
    if round_["kind"] == "narrow":
        text += [f"- **Changed regions**: {'; '.join(round_['regions'])}", "- **Items judged**:"]
        text += [f"  - {entry['item']}: {entry['reason']}" for entry in round_["items"]]
        text += [f"- **Items not judged**: {round_['others']}"]
    text += ["", "### Verdicts", ""] + table_lines(VERDICT_TABLE, [verdict_row(row, entries.get(row["Item"], ())) for row in rows])
    notes = [" ".join(str(row["Note"]).split()) for row in tables["Plan and free pass"]["rows"]]
    text += ["", "### Plan and free pass", ""]
    text += [f"- {note}" for note in notes] or [
        "This round judges only the items it lists, and no comparison with the plan or free pass beyond them was made."]
    findings = tables["Findings"]["rows"]
    text += ["", "### Findings", ""]
    if findings:
        text += table_lines(RECORD_FINDING_TABLE, [{**row, "Finding": f"{number}.{row['Finding']}"} for row in findings])
    else:
        text += [board_review_history.NO_FINDINGS]
    return {f"round-{number}.md": "\n".join(text) + "\n"}
