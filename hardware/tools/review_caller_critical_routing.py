#!/usr/bin/env python3
"""The critical-routing check as a caller of the review kit command (review_run.py --caller critical_routing).

Step 4 of the method's routing section judges the layout checklist items that bear on the critical nets, with the board
still closed and before the router runs. Judged by unit, the units are the area headings of the layout practice catalogue in
the review folder's own method and one for the board's own items when the plan's table of them has rows; there is no unit for
a comparison with the plan or a free pass, which the step does not make. The areas the catalogue's cross-references link as
the layout caller finds them (power with mains, the manufacturing items with power) are judged in one group, since one
area's verdicts rest on the other's findings here as at the layout review.

Each reviewer gives every item of its unit one verdict row: pass, fail, not applicable or cannot judge for an item that bears
on the critical nets, and `bears on no critical net`, with the reason in Why, for one that does not. That verdict is last of
the five, so when replicas are merged with any fail standing an item one replica judged as bearing is judged. A fail raises a
finding naming the item and what and where, numbered by the kit; the render writes the finding's What and where into the
fail's Why, and the pass holds no findings table and no round number.

The review folder is the one review_folder.py writes with --review critical-routing: its round file holds the pass number,
the commit judged and the views, and no kind or check lines. The shared context holds the routing section, the layout review
sections and the whole catalogue (the method extract), the plan, the rules table and the records, the round file, the views'
index, every rendered view, the placement view when it was rendered, and the layout facts extract. A reviewer is granted the
read tools and WebFetch, as the layout caller's are. The pass number, the commit judged and the views come from whoever runs
the check, because the merge has no model to write them; a folder whose round file lacks them or is malformed is refused when
the declaration is resolved, before any session starts.

The checks receive the merged tables alone, so what the pass judges is read once, when the declaration is resolved, and held
for them. They fail an item that has no verdict row or two, a verdict for an item the pass does not judge, a cannot judge
still held, a fail with no finding, a finding of an item that does not fail, a reason missing for an item that bears on no
critical net, and a pass in which no item bears on a critical net. The render writes the pass as the method gives it in
pass-<n>.md (for the first pass under the section heading), to be appended below the layout plan's earlier passes and never in
place of one, and committed by whoever runs the check. A fail is rendered as a plain `fail` for the designer to put right in
the row before the router runs.

A cannot judge is resolved within the pass as the layout caller resolves one, through the folder command's add-view and
add-document modes and a re-run of the unit, and the row is written `cannot judge, then <verdict>`.
"""

from __future__ import annotations

import os
import re
import sys
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)

import board_history  # noqa: E402
import review_catalogue  # noqa: E402
import review_folder  # noqa: E402
from review_kit import results  # noqa: E402
from review_kit.merge import Refused  # noqa: E402

ReviewFolderProblem = review_folder.ReviewFolderProblem
METHOD = review_folder.METHOD
PLAN = review_catalogue.PLAN
#: The unit for the board's own items.
OWN_UNIT = "board-items"
#: The verdict of an item that bears on no critical net, listed below the pass's table with its reason. It is the last of the
#: verdicts, so the merge, which takes the first of the verdicts a fail does not decide, gives way to any other replica's.
NOT_BEARING = "bears on no critical net"
VERDICTS = ("pass", "fail", "not applicable", "cannot judge", NOT_BEARING)
VERDICT_TABLE = list(board_history.CRITICAL_TABLE)
FINDING_TABLE = ["Finding", "Item", "What and where"]
CITATION = re.compile(r"(?<![\w.])[Ff]inding (?P<number>\d+)\b")
#: Words in a Why that mean the unit asked for a published document rather than a view.
DOCUMENT_WORDS = ("datasheet", "document", "standard", "specification")
#: The couplings are the layout caller's, which the shared catalogue helpers state: power with mains and the manufacturing items
#: with power. A test fails when a coupling here has no cross-reference of the catalogue to support it.
COUPLED = review_catalogue.COUPLED
#: The one name the render writes, a pass number the round file checked and nothing else.
RENDERED = re.compile(r"pass-[1-9][0-9]*\.md")
SECTION = "Critical routing"
#: The folder of views rendered during the pass, and of documents added, which the declaration lists as added during the round.
ADDED = [f"{review_folder.ADDED_VIEWS}/*", f"{review_folder.ADDED_DOCUMENTS}/*"]
IMAGES = (".png", ".jpg", ".jpeg")
#: The documents of the design folder the shared context holds are its .md and .yaml files.
DOCUMENT_SUFFIXES = (".md", ".yaml")
PRODUCER = "task hw:review-folder"

#: The small-tier model both replicas run on, a full model id. The check is run with --model set to it, so that the review's own
#: shared context is the replicas' and none is built for a model no replica uses.
SMALL_MODEL = "claude-haiku-5-5"

#: Plain data the kit reads: the variants a unit's replicas take in turn (the prompt as declared, and the terse hunt for
#: failures with the items and views the other way round, both on the small-tier model) and the replicas by stakes. The design
#: loop's round has two.
replica_policy = {
    "variants": [{"id": "full", "model": SMALL_MODEL},
                 {"id": "hunt", "item_order": "reversed", "view_order": "reversed", "terse": True, "model": SMALL_MODEL}],
    "replicas": {"low": 1, "normal": 2, "high": 2},
}
retrieval = True
#: The most reviewers at once: the layout caller's, the largest number the live runs ran with no call refused for a rate limit.
bound = 30
#: The check's time target in seconds, so the planner sizes groups well clear of the bound.
WALL_SECONDS = 350

#: What the checks hold of the pass: the units, the item each judges and the cannot judge resolutions its folder records.
ROUND: Dict[str, Any] = {}


# --- The folder ---------------------------------------------------------------------------------


def design_path(review: str) -> str:
    return review_folder.design_in(review)


def checklist(review: str) -> List[str]:
    """The checklist: the catalogue's items in the method's order, then the board's own items."""
    try:
        return [item for _, _, ids in review_catalogue.areas(review) for item in ids] + review_catalogue.own_items(review)
    except ReviewFolderProblem as error:
        raise Refused([str(error)])


def unit_items(review: str) -> Dict[str, List[str]]:
    """Each unit of the pass and the items it judges, in the order the units run."""
    found = {f"area-{code}": list(ids) for code, _, ids in review_catalogue.areas(review)}
    own = review_catalogue.own_items(review)
    if own:
        found[OWN_UNIT] = list(own)
    return found


def unit_of(item: str, units: Dict[str, List[str]]) -> Optional[str]:
    for unit, ids in units.items():
        if item in ids:
            return unit
    return None


def pass_round(review: str) -> Dict[str, Any]:
    """The pass's own fields from the round file, which must be a critical-routing pass's and no other review's."""
    round_ = review_folder.read_round(review)
    if not review_folder.is_critical_routing_fields(round_["fields"]):
        raise ReviewFolderProblem(f"the round file in the review folder {review} has the fields {', '.join(round_['fields'])}, "
                                  f"not a critical-routing pass's {', '.join(review_folder.CRITICAL_FIELDS)}; write the folder "
                                  "with the folder command's --review critical-routing")
    return round_


# --- The declaration ----------------------------------------------------------------------------


def shared_documents(review: str) -> Dict[str, Dict[str, Any]]:
    """The artefacts of the shared context, by name: the extracts, the pass's records and indexes, the design's plan, rules table
    and records, every rendered view and the placement view, when it was rendered, as an image. A file the folder command always
    writes and the folder lacks is named as missing."""
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
    held = review_catalogue.read_text(review, review_folder.METHOD_EXTRACT, "method extract")
    for heading in review_folder.missing_sections(held, review_folder.CRITICAL_ROUTING):
        raise ReviewFolderProblem(f"the method extract {review_folder.METHOD_EXTRACT} in the review folder {review} has no "
                                  f"`## {heading}` section, which the shared context needs; write the folder with the folder command")
    for path in (review_folder.ROUND_FILE, f"{review_folder.VIEWS}/index.txt"):
        if not os.path.isfile(os.path.join(review, path)):
            raise ReviewFolderProblem(f"the review folder {review} holds no {path}, which the shared context holds; write the "
                                      "folder with the folder command")
        add(path)
    folders = [review_folder.VIEWS]
    if os.path.isdir(os.path.join(review, review_folder.PLACEMENT)):
        folders.append(review_folder.PLACEMENT)
        if not os.path.isfile(os.path.join(review, review_folder.PLACEMENT, "index.txt")):
            raise ReviewFolderProblem(f"the review folder {review} holds a placement folder with no {review_folder.PLACEMENT}/"
                                      "index.txt, which the shared context holds; write the folder with the folder command")
        add(f"{review_folder.PLACEMENT}/index.txt")
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
    for folder in folders:
        for name in sorted(os.listdir(os.path.join(review, folder))):
            if name.lower().endswith(IMAGES) and os.path.isfile(os.path.join(review, folder, name)):
                add(f"{folder}/{name}", "image")
                images += 1
    if not images:
        raise ReviewFolderProblem(f"the review folder {review} holds no rendered view image (a PNG or JPEG in {review_folder.VIEWS}/), "
                                  "which the shared context holds; render the views")
    return found


PREFACE = """You are one reviewer of the critical-routing check of a printed circuit board, step 4 of the routing section of \
the method. You did not design the board, and you have no notes from whoever did. Work from the shared context above this \
message and the files in this folder. The shared context holds the routing section, the layout review sections and the whole \
layout practice catalogue (method-extract.md), the board's plan ({plan}), its rules table (design-rules.md) and the records \
those name in {design}/, round.json (the pass's number, the commit judged and the commands the views were rendered with), the \
view index, every rendered view as an image{placement}, and layout-facts.txt, which lists the positions, pads, segments, vias \
and zones of the layout file. You can read and search the folder and fetch a published document at its address; you cannot \
run a command, render a view or write anything.

Follow step 4 of the routing section, as written. The board is closed and the router has not run: only the critical nets are \
routed, so judge each item over the copper a net in a critical class carries, its tracks, arcs, vias and zones and the way its \
routes run, and over nothing else. An item bears on the critical nets when what its Asks asks of the board is decided, wholly \
or in part, by that copper; workmanship items are judged like any other. Judge a judgement-kind item on the views its Judged \
on names. Judge a rule-kind item on its rows in the rules table alone, the row of every rule the item gives, each present \
with a figure the item's own figure and source bear out; the pre-order check is not run here, so the Why of such a verdict says \
that the item's measured half is judged by the pre-order check that step 8 runs after the router. Every view an item is judged \
on is among the images above; open nothing again that is already there. Where an item needs a view that is not among them, \
give it `cannot judge` and write in Why `needs <view>: <why the views rendered do not show it>`. For a rule-kind item whose \
figure rests on a published document, fetch it at the address the board's rules table gives, or find it from the manufacturer \
or publisher the row names; a document you cannot fetch makes the item `cannot judge`.{added}"""

DISCIPLINE = (
    "Where an item asks whether a part stands beside, at, near or far from another, or how far a route runs from a pad or a via, "
    "read the positions from layout-facts.txt and state the distance in mm in Why; a view shows which parts to compare, not how "
    "far apart they are.")

OUTPUT = """Verdicts has one row for each item of your unit, with the columns {verdicts}. For an item that bears on the critical \
nets, Verdict is one of pass, fail, not applicable or cannot judge, as step 4 and the layout review's step 2 give them; Kind \
and Severity are the item's own; Rests on and Why are written as that step gives them. For an item that bears on no critical \
net, Verdict is {not_bearing}, Rests on is `—`, and Why is the one line saying why no critical net's copper decides the item; \
never give such an item another verdict to avoid judging it, and never give {not_bearing} to an item a critical net's copper \
decides in part.

A fail's Why is `finding <n>`, the number of the finding it raises in your Findings table. Findings has the columns \
{findings}. Number your findings 1, 2, 3 in the order you raise them, in Finding, as whole numbers. Raise at least one finding \
for each fail and none for an item that does not fail; Item is the item's identifier, and What and where names the view by \
its name in the views' index and the board place as (x, y) in the board coordinates its caption states, and says what is \
wrong."""

AREA_TEMPLATE = """{preface}

Your unit: {unit}

{scope}
{items}
{resolved}
{discipline}

{area}

{output}

{schema}"""

SCHEMA = {
    "tables": [
        {"name": "Verdicts", "columns": VERDICT_TABLE, "key": "Item", "verdict_column": "Verdict", "verdicts": list(VERDICTS)},
        {"name": "Findings", "columns": FINDING_TABLE, "key": "Item", "numeric": ["Finding"]},
    ],
    "findings": {"table": "Findings", "number": "Finding", "citations": [["Verdicts", "Why"]], "citation": CITATION.pattern},
}


def preface(review: str, resolutions: Sequence[Dict[str, str]]) -> str:
    added = ""
    if any(entry["kind"] == "view" for entry in resolutions):
        added += (f" Views rendered during the pass to resolve a cannot judge are in {review_folder.ADDED_VIEWS}/; they are "
                  "not among the images above, so open them with Read.")
    if any(entry["kind"] == "document" for entry in resolutions):
        added += (f" Documents added during the pass to resolve a cannot judge are in {review_folder.ADDED_DOCUMENTS}/; they "
                  "are not part of the shared context, so open them with Read.")
    placed = " (the placement view among them)" if os.path.isdir(os.path.join(review, review_folder.PLACEMENT)) else \
        " (the placement view was not rendered)"
    return PREFACE.format(design=design_path(review), plan=PLAN, added=added, placement=placed)


def output_spec() -> str:
    return OUTPUT.format(verdicts=", ".join(VERDICT_TABLE), findings=", ".join(FINDING_TABLE), not_bearing=f"`{NOT_BEARING}`")


def resolved_text(listed: Sequence[str], resolutions: Sequence[Dict[str, str]]) -> str:
    """What a unit run again is told of the views and documents added for its items' cannot judge, none for a unit with no
    such item."""
    lines = []
    for entry in resolutions:
        if entry["item"] not in listed:
            continue
        if entry["kind"] == "document":
            lines.append(f"- {entry['item']}: it was `cannot judge` because {entry['why']} The document added for it is "
                         f"{entry['document']} (the figure comes from: {entry['source']}). Open it with Read and judge the "
                         "item again against the figure it holds.")
        else:
            lines.append(f"- {entry['item']}: it was `cannot judge` because {entry['why']} The view added for it is "
                         f"{entry['view']} (rendered with: {entry['command']}). Open it with Read and judge the item again.")
    return ("\nItems whose cannot judge was resolved by an added view or document:\n" + "\n".join(lines) + "\n") if lines else ""


def unit_values(review: str, units: Dict[str, List[str]], resolutions: Sequence[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    """The values each unit's template is filled with: its preface, scope, area block and output form."""
    given = preface(review, resolutions)
    blocks = review_catalogue.catalogue_split(review)[1]
    scope = (f"Judge each of these items, in the order given, and give one verdict row to each of them and to no other item: "
             f"a verdict for an item that bears on the critical nets, `{NOT_BEARING}` with the reason for one that does not:")
    found: Dict[str, Dict[str, str]] = {}
    for unit, listed in units.items():
        if unit == OWN_UNIT:
            area = (f"These are the board's own items, in the table of them in {design_path(review)}/{PLAN}; each is judged on "
                    "its own Passes and Judged on.")
        else:
            area = ("The catalogue section for your area follows. The other areas of the catalogue are in the shared context "
                    "for reference; judge only your items.\n\n" + blocks[unit[len("area-"):]])
        found[unit] = {"preface": given, "scope": scope, "resolved": resolved_text(listed, resolutions),
                       "discipline": DISCIPLINE, "area": area.rstrip(), "output": output_spec()}
    return found


def expected_tokens(listed: Sequence[str]) -> int:
    """The output a unit is expected to give: a verdict row for each item and a little over for findings."""
    return 200 + 130 * len(listed)


def coupled_to(unit: str, units: Dict[str, List[str]]) -> List[str]:
    """The other units of the pass the declaration couples a unit with: the area pairs of COUPLED whose two areas both have a
    unit in the pass."""
    return review_catalogue.coupled_to(unit, units, COUPLED)


def build_declaration(review: str) -> Dict[str, Any]:
    pass_round(review)
    method = review_catalogue.read_text(review, METHOD, "method")
    for heading in review_folder.REVIEW_SECTIONS[review_folder.CRITICAL_ROUTING]:
        if review_folder.method_section(method, heading) is None:
            raise ReviewFolderProblem(f"the method in the review folder {review} has no `## {heading}` section, which the "
                                      "shared context needs")
    units = unit_items(review)
    resolutions = review_folder.read_resolutions(review)
    documents = shared_documents(review)
    values = unit_values(review, units, resolutions)
    ROUND.clear()
    ROUND.update({"units": {unit: list(listed) for unit, listed in units.items()}, "resolutions": resolutions})
    declared = {unit: {"items": list(listed), "template": "area", "needs": sorted(documents),
                       "couples_with": coupled_to(unit, units), "expected_output_tokens": expected_tokens(listed),
                       "values": values[unit]} for unit, listed in units.items()}
    return {"artefacts": documents, "templates": {"area": AREA_TEMPLATE}, "units": declared, "schema": SCHEMA,
            "deny": ["designer-notes*", "session*"], "budget": {"wall_s": WALL_SECONDS}, "added_during_round": list(ADDED)}


def declaration(review: str) -> Dict[str, Any]:
    """The declaration of the pass in the review folder: its units, the shared context and the tables. The pass's fields are
    checked here, before any session starts, since the checks receive the merged tables alone."""
    try:
        return build_declaration(review)
    except ReviewFolderProblem as error:
        raise Refused([str(error)])


# --- The checks ---------------------------------------------------------------------------------


def cited(row: Dict[str, Any]) -> List[int]:
    return [int(match.group("number")) for match in CITATION.finditer(str(row["Why"]))]


def finding_problems(rows: Sequence[Dict[str, Any]], findings: Sequence[Dict[str, Any]]) -> List[str]:
    """Each fail needs a finding of its own item, and each finding an item that fails; a fail's Why cites only findings of
    its own item."""
    found = []
    by_number = {finding["Finding"]: finding for finding in findings}
    failing = {row["Item"] for row in rows if row["Verdict"] == "fail"}
    for item in sorted(failing, key=[row["Item"] for row in rows].index):
        if not any(finding["Item"] == item for finding in findings):
            found.append(f"item {item} fails and no finding names it; the fail raises a finding naming the item and what and "
                         "where, so run its unit again with --rerun")
    for finding in findings:
        if finding["Item"] not in failing:
            found.append(f"finding {finding['Finding']} names item {finding['Item']}, which does not fail in this pass; a finding "
                         "belongs to a fail, so run the unit that raised it again with --rerun")
        if not str(finding["What and where"]).strip():
            found.append(f"finding {finding['Finding']} says nothing under What and where, which the fail's Why is written from; "
                         "run its unit again with --rerun")
    for row in rows:
        for number in cited(row):
            if number in by_number and by_number[number]["Item"] != row["Item"]:
                found.append(f"item {row['Item']}'s Why cites finding {number}, which names item {by_number[number]['Item']}; "
                             "a verdict cites only findings of its own item")
    return found


def checks(tables: Dict[str, Any]) -> List[str]:
    """What the merge refuses: an item with no verdict row or two, a verdict for an item the pass does not judge, a cannot
    judge still held, a recorded cannot judge for an item the pass has no verdict row for, an item given as bearing on no
    critical net with no reason, a fail with no finding, a finding of an item that does not fail, and a pass in which no item
    bears on a critical net."""
    if not ROUND:
        return ["the critical-routing caller's checks ran before its declaration was resolved for a review folder, so the items "
                "the pass judges are not known; resolve the declaration first"]
    units = ROUND["units"]
    expected = [item for listed in units.values() for item in listed]
    rows = tables["Verdicts"]["rows"]
    counts = Counter(row["Item"] for row in rows)
    found = []
    for item in expected:
        unit = unit_of(item, units)
        if counts[item] == 0:
            found.append(f"item {item} has no verdict row; every item the pass judges has exactly one"
                         + (f" (judge it in unit {unit} and run that unit again with --rerun)" if unit else ""))
        elif counts[item] > 1:
            found.append(f"item {item} has {counts[item]} verdict rows; every item the pass judges has exactly one")
    for item in counts:
        if item not in expected:
            found.append(f"a verdict row for {item}, which this pass does not judge; a verdict is accepted only for an item of "
                         "the checklist")
    for entry in ROUND["resolutions"]:
        if entry["item"] not in expected:
            found.append(f"the folder records a cannot judge for {entry['item']!r}, which is not an item this pass judges; "
                         "the item was mistyped when the view or document was added, so add it again with the item's exact name")
        elif counts[entry["item"]] == 0:
            found.append(f"the folder records a cannot judge for {entry['item']}, which has no verdict row in this pass; "
                         "run the unit that judges it again with --rerun")
    for row in rows:
        if row["Verdict"] == "cannot judge":
            found.append(cannot_judge_problem(row, units))
        elif row["Verdict"] == NOT_BEARING and not " ".join(str(row["Why"]).split()).strip("—- "):
            found.append(f"item {row['Item']} is given as bearing on no critical net with no reason; the pass lists every such "
                         "item with the reason, so run its unit again with --rerun")
    if rows and all(row["Verdict"] == NOT_BEARING for row in rows) and not found:
        found.append("no item bears on a critical net in this pass, so the critical routing is judged against nothing; run the "
                     "units again with --rerun")
    return found + finding_problems(rows, tables["Findings"]["rows"])


def cannot_judge_problem(row: Dict[str, Any], units: Dict[str, List[str]]) -> str:
    unit = unit_of(row["Item"], units)
    asks = re.match(r"needs (.+?):", row["Why"])
    where = f"unit {unit}" if unit else "the unit that judged it"
    wanted = asks.group(1) if asks else repr(row["Why"])
    added = [entry for entry in ROUND["resolutions"] if entry["item"] == row["Item"]]
    if added:
        what = "document" if added[-1]["kind"] == "document" else "view"
        action = (f"the folder already holds a {what} added for this item, so run {where} again with --rerun; add another only "
                  "if the one added is not what the Why asks for")
    else:
        action = f"render that view, add it with the folder command's --add-view and run {where} again with --rerun"
        if any(word in row["Why"].lower() for word in DOCUMENT_WORDS):
            action += (f", or run {where} again with --rerun if the document can be retrieved; if the plan names no address to "
                       "fetch it from, write the figure it asks for into a text file and add it with the folder command's "
                       "`--add-document <review folder> --document <file> --source <where the figure comes from> "
                       f"--cannot-judge-item {row['Item']} --cannot-judge-why <the Why>`, then run {where} again with --rerun")
    return (f"item {row['Item']} is still cannot judge, and the method resolves it within the pass; its Why asks for "
            f"{wanted}: {action}")


# --- The rendered pass --------------------------------------------------------------------------


def one_line(value: Any) -> str:
    return " ".join(str(value).split())


def verdict_row(row: Dict[str, Any], entries: Sequence[Dict[str, Any]], findings: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """A verdict row as the plan's section gives it. A fail's Why is written from its findings' What and where; one that
    resolves a cannot judge is `cannot judge, then <verdict>`, its Rests on holding the view or document added and its Why the
    Why of the cannot judge before the reviewer's own."""
    why = str(row["Why"])
    rests = str(row["Rests on"])
    verdict = row["Verdict"]
    if verdict == "fail":
        by_number = {finding["Finding"]: str(finding["What and where"]).strip() for finding in findings
                     if finding["Item"] == row["Item"]}
        why = CITATION.sub(lambda match: by_number.get(int(match.group("number")), match.group(0)), why)
        left = [text for number, text in by_number.items() if number not in cited(row)]
        why = " ".join([why.strip()] + [f"Also: {text}" for text in left])
    if entries:
        added = [f"`{entry['document' if entry['kind'] == 'document' else 'view']}`" for entry in entries]
        verdict = f"cannot judge, then {verdict}"
        rests = "; ".join([rests] + added)
        why = " ".join([f"Cannot judge: {entry['why']}." for entry in entries] + [why])
    return {**row, "Verdict": verdict, "Rests on": rests, "Why": why}


def render(review: str, tables: Dict[str, Any]) -> Dict[str, str]:
    """The merged pass as the method gives it, written as pass-<n>.md: for the first pass the section heading, then the pass
    heading, the Board judged and Views fields, the verdict table with a row for every item that bears on a critical net, and
    below it every other item on a line of its own with its reason."""
    try:
        round_ = pass_round(review)
        resolutions = review_folder.read_resolutions(review)
        order = {item: index for index, item in enumerate(checklist(review))}
    except ReviewFolderProblem as error:
        raise Refused([str(error)])
    number = round_["number"]
    name = f"pass-{number}.md"
    if isinstance(number, bool) or not isinstance(number, int) or not RENDERED.fullmatch(name):
        raise Refused([f"the pass number {number!r} does not give a file name of the form pass-<n>.md; write the folder with "
                       "the folder command"])
    entries: Dict[str, List[Dict[str, Any]]] = {}
    for entry in resolutions:
        entries.setdefault(entry["item"], []).append(entry)
    rows = sorted(tables["Verdicts"]["rows"], key=lambda row: order[row["Item"]])
    findings = tables["Findings"]["rows"]
    views = round_["views"] + [f"{entry['command']} (added view: {entry['view']})" for entry in resolutions
                               if entry["kind"] == "view"]
    placed = os.path.isdir(os.path.join(review, review_folder.PLACEMENT))
    text = [f"## {SECTION}", ""] if number == 1 else []
    text += [f"### Pass {number}", "", f"- **Board judged**: {round_['commit']}",
             "- **Views**: the commands the views were rendered with, as run, and any view rendered in the pass to resolve a "
             "cannot judge, with its command" + ("" if placed else "; the placement view was not rendered") + ":", "",
             "```", *views, "```", ""]
    made = [(row["Verdict"], verdict_row(row, entries.get(row["Item"], ()), findings)) for row in rows]
    text += results.table_lines(VERDICT_TABLE, [row for verdict, row in made if verdict != NOT_BEARING]) + [""]
    text += [f"- `{row['Item']}`: {one_line(row['Why'])}" for verdict, row in made if verdict == NOT_BEARING]
    return {name: "\n".join(text).rstrip("\n") + "\n"}
