#!/usr/bin/env python3
"""The schematic review as a caller of the review kit command (review_run.py --caller schematic).

A schematic review round is judged by forks of one shared context. The units are the area headings of the circuit practice
catalogue in the review folder's own method, found as the layout caller finds its own, and one for the free pass over the whole
schematic, which belongs to no area. The pin-voltage item selects every net and the derating item every part, so their areas
are the largest units; an item that selects every net, part or sheet stays in its area's unit and is not split.

The review folder is the one schematic_review_folder.py writes. The shared context holds the method's schematic review, drawing
convention and circuit practice catalogue sections (the method extract), the round file, the check's report, the netlist, the
records the round reads and the earlier rounds of the review record, and the schematic's own files. A unit's prompt names its own
items and holds its own area; none is in the shared context. The drawing of each sheet is in the folder's sheets folder and a
reviewer opens the ones an item needs. A reviewer is granted the read tools and WebFetch, which fetches a published document at
its address and writes nothing, since a datasheet is opened at its address and never recalled.

The round's own fields, its number, the commit judged, the command the netlist was exported with and the records read, come from
the round file, because the merge has no model to write them; a folder whose round file lacks them, or is another review's, or
whose netlist names parts or sheets other than the schematic's, is refused when the declaration is resolved, before any session
starts. The checks receive the merged tables alone, so what the round judges, and the nets, parts and sheets of the schematic,
are read once, when the declaration is resolved, and held for them.

The answer's Verdicts table is keyed by Item and Net or part, one row for each pair an item selects and one row, with `none`,
for an item that selects nothing; replicas are merged any fail per pair. Its Findings table holds the method's columns and the
item that raised each. The merge fails an item with no verdict row, a row for something that is no item of the checklist, a net,
part or sheet that no item's rows name, a row naming a net, part or sheet that does not exist, an item that selects nothing and
also selects something, a pass or fail with nothing under Rests on, a not applicable or fail with nothing under Why, a fail that
cites no finding of its own item or of an earlier round, a finding of an item that does not fail, a finding not raised by its
item, a severity outside the catalogue's four, a Closed by the reviewer wrote, and a cannot judge still held.

A cannot judge is resolved within the round: the folder command's add-view mode puts a view in the added-views folder, or its
add-document mode a text file holding the figure in the added-documents folder, and records the item, the net, part or sheet
when it is given, the Why and the file in a resolutions file there; the unit is run again with --rerun, and the row the render
writes records `cannot judge, then <verdict>` with the file added in Rests on. The render writes the round as the method gives
it in round-<n>.md, to be appended below the record's earlier rounds and committed by whoever started the round.
"""

from __future__ import annotations

import os
import re
import sys
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)

import board_review_history  # noqa: E402
import review_catalogue  # noqa: E402
import review_folder  # noqa: E402
import schematic_facts  # noqa: E402
import schematic_review_folder  # noqa: E402
from review_kit import results  # noqa: E402
from review_kit.merge import Refused  # noqa: E402

ReviewFolderProblem = review_folder.ReviewFolderProblem
SECTION = review_folder.CIRCUIT_SECTION
#: The unit for the whole-schematic free pass, and the checklist entry its findings are raised against. The entry belongs to no
#: catalogue item; it is the checklist's last, so the merge numbers the free pass's findings after the items'.
FREE_PASS_UNIT = "free-pass"
FREE_PASS_ENTRY = review_folder.FREE_PASS_ITEM
#: What the record's Raised by cell says of a finding of the free pass.
FREE_PASS_LABEL = "free pass"
#: The Net or part cell of an item that selects nothing on this board.
NONE = "none"
VERDICTS = ("pass", "fail", "not applicable", "cannot judge")
VERDICT_TABLE = ["Item", "Net or part", "Verdict", "Rests on", "Why"]
KEY = ["Item", "Net or part"]
#: The findings table as a reviewer returns it: the method's columns and the Item column, which says which checklist entry raised
#: the finding and is the merge's own, not written into the record.
FINDING_TABLE = ["Finding", "Item", "Raised by", "Severity", "What and where", "Closed by"]
RECORD_FINDING_TABLE = [column for column in FINDING_TABLE if column != "Item"]
SEVERITIES = ("safety", "function", "quality", "cosmetic")
CITATION = re.compile(r"(?<![\w.])[Ff]inding (?P<round>\d+)\.(?P<number>\d+)\b")
#: Words in a Why that mean the unit asked for a published document rather than a sheet or view.
DOCUMENT_WORDS = ("datasheet", "document", "standard", "specification", "application note")
#: The one name the render writes, a round number the round file checked and nothing else.
RENDERED = re.compile(r"round-[1-9][0-9]*\.md")
PRODUCER = "task hw:schematic-review-folder"
#: The folder of views rendered during the round, and of documents added, which the declaration lists as added during the round.
ADDED = [f"{review_folder.ADDED_VIEWS}/*", f"{review_folder.ADDED_DOCUMENTS}/*"]
#: The files of the design folder the shared context holds: the records and the earlier rounds, and the schematic's own files.
DOCUMENT_SUFFIXES = (".md", ".yaml", ".kicad_sch", ".kicad_sym")
#: How many names of a kind a refusal lists before it counts the rest.
LISTED = 10
#: What a model's output is expected to be for an item that selects every net, part or sheet, per name.
TOKENS_PER_NAME = 45

#: The small-tier model both replicas run on, a full model id. The check is run with --model set to it, so that the review's own
#: shared context is the replicas' and none is built for a model no replica uses.
SMALL_MODEL = "claude-haiku-5-5"

#: Plain data the kit reads: the variants a unit's replicas take in turn (the prompt as declared, and the terse hunt for
#: failures with the items the other way round, both on the small-tier model) and the replicas by stakes. The design loop's round
#: has two.
replica_policy = {
    "variants": [{"id": "full", "model": SMALL_MODEL},
                 {"id": "hunt", "item_order": "reversed", "terse": True, "model": SMALL_MODEL}],
    "replicas": {"low": 1, "normal": 2, "high": 2},
}
retrieval = True
#: The most reviewers at once: the layout caller's, the largest number the live runs ran with no call refused for a rate limit.
bound = 30
#: The review's time target in seconds, so the planner sizes groups well clear of the bound.
WALL_SECONDS = 350

#: What the checks hold of the round: the units, the items each judges, the nets, parts and sheets of the schematic, the round's
#: label and the cannot judge resolutions its folder records.
ROUND: Dict[str, Any] = {}


# --- The folder ---------------------------------------------------------------------------------


read_text = review_catalogue.read_text


def design_path(review: str) -> str:
    return review_folder.design_in(review)


def schematic_round(review: str) -> Dict[str, Any]:
    """The round's own fields from the round file, which must be a schematic review's and no other review's."""
    round_ = review_folder.read_round(review)
    if not review_folder.is_schematic_fields(round_["fields"]):
        raise ReviewFolderProblem(f"the round file in the review folder {review} has the fields {', '.join(round_['fields'])}, "
                                  f"not a schematic review's {', '.join(review_folder.SCHEMATIC_FIELDS)}; write the folder with "
                                  "schematic_review_folder.py (task hw:schematic-review-folder)")
    return round_


def areas(review: str) -> List[Tuple[str, str, List[str]]]:
    """Each area heading of the method's circuit practice catalogue, in order: its code, its name and its items' identifiers. An
    area that holds no item is refused, since a unit judges at least one."""
    found = review_catalogue.areas(review, SECTION)
    empty = [code for code, _, items in found if not items]
    if empty:
        raise ReviewFolderProblem(f"the circuit practice catalogue in the method of the review folder {review} has the area "
                                  f"{', '.join(empty)} with no item (`#### <ID>. ` heading), so there is nothing for its unit to judge")
    return found


def checklist(review: str) -> List[str]:
    """The checklist: the catalogue's items in the method's order, then the free pass's entry, which findings of no item are
    raised against."""
    try:
        return [item for _, _, ids in areas(review) for item in ids] + [FREE_PASS_ENTRY]
    except ReviewFolderProblem as error:
        raise Refused([str(error)])


def unit_items(review: str) -> Dict[str, List[str]]:
    """Each unit of the round and the items it judges, in the order the units run: one for each area, then the free pass."""
    found = {f"area-{code}": list(ids) for code, _, ids in areas(review)}
    found[FREE_PASS_UNIT] = [FREE_PASS_ENTRY]
    return found


def unit_of(item: str, units: Dict[str, List[str]]) -> Optional[str]:
    for unit, ids in units.items():
        if item in ids:
            return unit
    return None


def schematic_names(review: str) -> schematic_facts.Names:
    """The nets, parts and sheets the round judges: the nets and parts of the folder's netlist and the sheets of the schematic's
    own files. A netlist whose parts or sheets are not the schematic's is refused, since the folder command refuses to write one."""
    design = design_path(review)
    try:
        project = schematic_facts.design_name(os.listdir(os.path.join(review, design)))
        netlist = schematic_facts.netlist_names(read_text(review, schematic_facts.NETLIST_FILE, "netlist"), project,
                                                f"the netlist {schematic_facts.NETLIST_FILE} in the review folder {review}")
        parts, sheets = schematic_facts.folder_schematic(os.path.join(review, design), project)
    except schematic_facts.FactsProblem as error:
        raise ReviewFolderProblem(f"{error}; write the folder with the folder command")
    for what, held, schematic in (("parts", netlist.parts, parts), ("sheets", netlist.sheets, sheets)):
        if held != schematic:
            raise ReviewFolderProblem(f"the netlist in the review folder {review} names {what} other than the schematic's "
                                      f"({', '.join(sorted(held ^ schematic)[:LISTED])}); write the folder with the folder command "
                                      "from the commit's own netlist")
    return schematic_facts.Names(netlist.nets, netlist.parts, sheets)


def sheet_drawings(review: str, names: schematic_facts.Names) -> Dict[str, str]:
    """Each sheet's drawing in the folder by sheet name; a sheet with no drawing is refused naming it."""
    design = schematic_facts.design_name(os.listdir(os.path.join(review, design_path(review))))
    found, lacking = {}, []
    for sheet in sorted(names.sheets):
        name = schematic_review_folder.drawing_name(design, sheet)
        if os.path.isfile(os.path.join(review, schematic_review_folder.SHEETS, name)):
            found[sheet] = f"{schematic_review_folder.SHEETS}/{name}"
        else:
            lacking.append(sheet)
    if lacking:
        raise ReviewFolderProblem(f"the review folder {review} holds no drawing for the sheet {', '.join(lacking)} in "
                                  f"{schematic_review_folder.SHEETS}/; write the folder with the folder command")
    return found


# --- The declaration ----------------------------------------------------------------------------


def shared_documents(review: str) -> Dict[str, Dict[str, Any]]:
    """The artefacts of the shared context, by name: the method extract, the round file, the check's report, the netlist, the
    records and earlier rounds, and the schematic's own files. A file the folder command always writes and the folder lacks is
    named as missing."""
    design = design_path(review)
    found: Dict[str, Dict[str, Any]] = {}

    def add(path: str, kind: str = "text", producer: Optional[str] = None) -> None:
        entry: Dict[str, Any] = {"kind": kind, "source": path}
        if producer:
            entry["producer"] = producer
        found[path] = entry

    for path in (review_folder.METHOD_EXTRACT, schematic_facts.NETLIST_FILE):
        if not os.path.isfile(os.path.join(review, path)):
            raise ReviewFolderProblem(f"the review folder {review} holds no {path}, which the shared context holds; write the "
                                      "folder with the folder command")
        if path == review_folder.METHOD_EXTRACT:
            add(path, "extract", PRODUCER)
        else:
            add(path)
    held = read_text(review, review_folder.METHOD_EXTRACT, "method extract")
    for heading in schematic_review_folder.extract_lacks(held):
        raise ReviewFolderProblem(f"the method extract {review_folder.METHOD_EXTRACT} in the review folder {review} has no "
                                  f"`## {heading}` section, which the shared context needs; write the folder with the folder command")
    for path in (review_folder.ROUND_FILE, review_folder.CHECK_REPORT):
        if not os.path.isfile(os.path.join(review, path)):
            raise ReviewFolderProblem(f"the review folder {review} holds no {path}, which the shared context holds; write the "
                                      "folder with the folder command")
        add(path)
    base = os.path.join(review, design)
    names = sorted(os.path.relpath(os.path.join(directory, name), base).replace(os.sep, "/")
                   for directory, _, files in os.walk(base) for name in files
                   if name.endswith(DOCUMENT_SUFFIXES) and os.path.isfile(os.path.join(directory, name)))
    if not any(name.endswith(".kicad_sch") for name in names):
        raise ReviewFolderProblem(f"the review folder {review} holds no schematic (.kicad_sch) in {design}, which the shared "
                                  "context holds")
    for name in names:
        add(f"{design}/{name}")
    return found


PREFACE = """You are one reviewer of a round of a schematic review of a finished schematic. You did not draw it, and you have no \
notes from whoever did. Work from the shared context above this message and the files in this folder. The shared context holds \
the method's "Schematic review" and "Schematic drawing convention" sections and the whole circuit practice catalogue \
(method-extract.md), round.json (the round's number, the commit judged, the command the netlist was exported with and the records \
read), the pre-order check's report (check-report.txt), the netlist exported from the schematic ({netlist}), the records the round \
reads and the schematic's own files in {design}/{earlier}. The drawing of each sheet is in {sheets}/, one file for each sheet: \
{drawings}. You can read and search the folder and fetch a published document at its address; you cannot run a command, draw a \
sheet or write anything.

Follow the "Schematic review" section of the method, steps 2 and 3, as written. Read each item's Applies when against the netlist \
and the schematic and list the nets, parts and sheets it selects; an item whose condition the schematic meets applies and cannot be \
marked as not applying. A datasheet is opened at its address, never recalled: fetch it, or find it from the manufacturer or \
publisher the record names, and record its document number and revision in Rests on. A rating you cannot source counts as absent \
and fails the item. Where an item needs a document or a sheet drawing that is not in the folder, give the row `cannot judge` and \
write in Why `needs <the document or sheet>: <why what you have does not show it>`.{added}"""

DISCIPLINE = (
    "Name a net exactly as the netlist writes it, with its leading slash where it has one; name a part by its reference "
    "designator; name a sheet as the sheet list above names it, the root sheet by the design's name.")

OUTPUT = """Verdicts has one row for each item of your unit together with each net, part or sheet the item selects, and one row, \
with `none` in Net or part and the verdict not applicable, for an item that selects nothing on this board, with the columns \
{verdicts}. Item is the item's identifier; Net or part is one net, one reference designator or one sheet, or `none`. Verdict is \
one of pass, fail, not applicable or cannot judge, as step 3 gives them. Rests on cites what the verdict was reached from: the \
sheet and the net or reference designator, each datasheet by document number, revision and section or page, each record by path \
and key. Why is the reason against the item's Applies when for not applicable, `finding {round}.<n>`, the number of the finding \
the row raises in your Findings table, or the number of an earlier round's finding closed by a reason, written with that round's \
own number, for fail, and what is missing and where it will be found for cannot judge.

Findings has the columns {findings}. Number your findings 1, 2, 3 in the order you raise them, in Finding, as whole numbers. Item \
is the checklist entry that raised the finding: the item's identifier, or {sentinel} for a finding of the free pass. Raised by is \
the same item's identifier, or `{label}` for a finding of the free pass. Severity is one of {severities}: the item's own, or, for a \
finding of the free pass, chosen by the catalogue's definitions. What and where says what is wrong, with the sheet and the net or \
reference designator that show it. Closed by is left as "". Raise at least one finding for each item that fails and none for an \
item that does not fail. Write a finding of this round wherever you cite it as `finding {round}.<n>`, with your own number, and \
never write an earlier round's finding in that form with this round's number."""

FREE_PASS_SCOPE = """This unit judges no catalogue item. Look over the whole schematic once for anything else wrong with it that \
no item of the catalogue asks about, and record each thing seen as a finding whose Item is {sentinel} and whose Raised by is \
`{label}`. The one item below stands for this pass: give it one Verdicts row with Net or part `none`, Verdict `pass` when you \
raise no finding and `fail` when you raise any (its Why `finding {round}.<n>` for the first), Rests on the sheets you looked over \
and Why the one line saying what you looked for."""

AREA_TEMPLATE = """{preface}

Your unit: {unit}

{scope}
{items}
{resolved}
{discipline}

{area}

{output}

{schema}"""

FREE_PASS_TEMPLATE = """{preface}

Your unit: {unit}

{scope}
{items}

{discipline}

{output}

{schema}"""

SCHEMA = {
    "tables": [
        {"name": "Verdicts", "columns": VERDICT_TABLE, "key": KEY, "verdict_column": "Verdict", "verdicts": list(VERDICTS)},
        {"name": "Findings", "columns": FINDING_TABLE, "key": "Item", "numeric": ["Finding"]},
    ],
    "findings": {"table": "Findings", "number": "Finding", "citations": [["Verdicts", "Why"]], "citation": CITATION.pattern},
}


def preface(review: str, round_: Dict[str, Any], resolutions: Sequence[Dict[str, str]], drawings: Dict[str, str]) -> str:
    design = design_path(review)
    earlier = ""
    if round_["number"] > 1:
        earlier = (f" This is round {round_['number']}: the earlier rounds of the review record are in {design}/"
                   f"{schematic_review_folder.RECORD}, and a verdict row may cite a finding an earlier round raised and closed by "
                   "a reason, written `finding <that round>.<n>`.")
    added = ""
    if any(entry["kind"] == "view" for entry in resolutions):
        added += (f" Views added during the round to resolve a cannot judge are in {review_folder.ADDED_VIEWS}/; they are not "
                  "part of the shared context, so open them with Read.")
    if any(entry["kind"] == "document" for entry in resolutions):
        added += (f" Documents added during the round to resolve a cannot judge are in {review_folder.ADDED_DOCUMENTS}/; they "
                  "are not part of the shared context, so open them with Read.")
    sheets = "; ".join(f"{name} is {path}" for name, path in drawings.items())
    return PREFACE.format(design=design, netlist=schematic_facts.NETLIST_FILE, earlier=earlier,
                          sheets=schematic_review_folder.SHEETS, drawings=sheets, added=added)


def output_spec(round_: Dict[str, Any]) -> str:
    return OUTPUT.format(verdicts=", ".join(VERDICT_TABLE), findings=", ".join(FINDING_TABLE), round=round_["number"],
                         sentinel=FREE_PASS_ENTRY, label=FREE_PASS_LABEL, severities=", ".join(SEVERITIES))


def resolved_text(listed: Sequence[str], resolutions: Sequence[Dict[str, str]]) -> str:
    """What a unit run again is told of the views and documents added for its items' cannot judge, none for a unit with no
    such item."""
    lines = []
    for entry in resolutions:
        if entry["item"] not in listed:
            continue
        about = f" (about {entry['target']})" if entry.get("target") else ""
        if entry["kind"] == "document":
            lines.append(f"- {entry['item']}{about}: it was `cannot judge` because {entry['why']} The document added for it is "
                         f"{entry['document']} (the figure comes from: {entry['source']}). Open it with Read and judge the "
                         "item again against the figure it holds.")
        else:
            lines.append(f"- {entry['item']}{about}: it was `cannot judge` because {entry['why']} The view added for it is "
                         f"{entry['view']} (rendered with: {entry['command']}). Open it with Read and judge the item again.")
    return ("\nItems whose cannot judge was resolved by an added view or document:\n" + "\n".join(lines) + "\n") if lines else ""


def unit_values(review: str, round_: Dict[str, Any], units: Dict[str, List[str]], resolutions: Sequence[Dict[str, str]],
                drawings: Dict[str, str]) -> Dict[str, Dict[str, str]]:
    """The values each unit's template is filled with: its preface, scope, area block and output form."""
    given = preface(review, round_, resolutions, drawings)
    blocks = review_catalogue.catalogue_split(review, SECTION)[1]
    found: Dict[str, Dict[str, str]] = {}
    for unit, listed in units.items():
        if unit == FREE_PASS_UNIT:
            found[unit] = {"preface": given, "discipline": DISCIPLINE, "output": output_spec(round_),
                           "scope": FREE_PASS_SCOPE.format(sentinel=FREE_PASS_ENTRY, label=FREE_PASS_LABEL, round=round_["number"])}
            continue
        scope = ("This round is full. Judge each of these items, in the order given, and give each the rows of its Verdicts: one for "
                 "every net, part or sheet it selects, or one with `none` when it selects nothing:")
        area = ("The catalogue section for your area follows. The other areas of the catalogue are in the shared context for "
                "reference; judge only your items.\n\n" + blocks[unit[len("area-"):]])
        found[unit] = {"preface": given, "scope": scope, "resolved": resolved_text(listed, resolutions),
                       "discipline": DISCIPLINE, "area": area.rstrip(), "output": output_spec(round_)}
    return found


def selects_all(review: str) -> Dict[str, str]:
    """The items whose Applies when says they select every net, every part or every sheet, with what they select every one of."""
    found: Dict[str, str] = {}
    blocks = review_catalogue.catalogue_split(review, SECTION)[1]
    for block in blocks.values():
        for part in re.split(r"(?m)^(?=#### )", block):
            item = review_catalogue.ITEM.match(part)
            every = re.search(r"selects every (net|part|sheet)", part)
            if item and every:
                found[item.group(1)] = every.group(1)
    return found


def expected_tokens(listed: Sequence[str], every: Dict[str, str], names: schematic_facts.Names) -> int:
    """The output a unit is expected to give: a verdict row for each item, a row for each net, part or sheet an item that selects
    every one of them judges, and a little over for findings."""
    size = {"net": len(names.nets), "part": len(names.parts), "sheet": len(names.sheets)}
    return 200 + 130 * len(listed) + TOKENS_PER_NAME * sum(size[every[item]] for item in listed if item in every)


def build_declaration(review: str) -> Dict[str, Any]:
    round_ = schematic_round(review)
    method = read_text(review, review_folder.METHOD_EXTRACT, "method extract")
    for heading in schematic_review_folder.extract_lacks(method):
        raise ReviewFolderProblem(f"the method extract in the review folder {review} has no `## {heading}` section, which the "
                                  "shared context needs")
    units = unit_items(review)
    names = schematic_names(review)
    drawings = sheet_drawings(review, names)
    resolutions = review_folder.read_resolutions(review)
    documents = shared_documents(review)
    values = unit_values(review, round_, units, resolutions, drawings)
    every = selects_all(review)
    ROUND.clear()
    ROUND.update({"units": {unit: list(listed) for unit, listed in units.items()}, "resolutions": resolutions, "names": names,
                  "label": str(round_["number"]), "earlier": set(earlier_findings(review))})
    declared = {unit: {"items": list(listed), "template": "free-pass" if unit == FREE_PASS_UNIT else "area",
                       "needs": sorted(documents), "expected_output_tokens": expected_tokens(listed, every, names),
                       "values": values[unit]} for unit, listed in units.items()}
    return {"artefacts": documents, "templates": {"area": AREA_TEMPLATE, "free-pass": FREE_PASS_TEMPLATE}, "units": declared,
            "schema": SCHEMA, "deny": ["designer-notes*", "session*"], "budget": {"wall_s": WALL_SECONDS},
            "added_during_round": list(ADDED)}


def declaration(review: str) -> Dict[str, Any]:
    """The declaration of the round in the review folder: its units, the shared context and the tables. The round's fields are
    checked here, before any session starts, since the checks receive the merged tables alone."""
    try:
        return build_declaration(review)
    except (ReviewFolderProblem, schematic_facts.FactsProblem) as error:
        raise Refused([str(error)])


# --- The checks ---------------------------------------------------------------------------------


def listed(names: Sequence[str]) -> str:
    shown = ", ".join(names[:LISTED])
    return shown + (f" and {len(names) - LISTED} more" if len(names) > LISTED else "")


def pair(row: Dict[str, Any]) -> str:
    return f"{row['Item']} on {row['Net or part']}"


def cited(row: Dict[str, Any], label: str) -> Tuple[List[int], List[Tuple[str, int]]]:
    """The findings of this round, by number, and of earlier rounds, by round and number, a row's Why cites."""
    here: List[int] = []
    before: List[Tuple[str, int]] = []
    for match in CITATION.finditer(str(row["Why"])):
        number = int(match.group("number"))
        if match.group("round") == label:
            here.append(number)
        else:
            before.append((match.group("round"), number))
    return here, before


def cannot_judge_problem(row: Dict[str, Any], units: Dict[str, List[str]]) -> str:
    unit = unit_of(row["Item"], units)
    asks = re.match(r"needs (.+?):", row["Why"])
    where = f"unit {unit}" if unit else "the unit that judged it"
    wanted = asks.group(1) if asks else repr(row["Why"])
    added = [entry for entry in ROUND["resolutions"] if entry["item"] == row["Item"]
             and entry.get("target") in (None, row["Net or part"])]
    target = f" --cannot-judge-target {row['Net or part']}" if row["Net or part"] != NONE else ""
    if added:
        what = "document" if added[-1]["kind"] == "document" else "view"
        action = (f"the folder already holds a {what} added for this item, so run {where} again with --rerun; add another only "
                  "if the one added is not what the Why asks for")
    else:
        action = (f"render that sheet or view, add it with the folder command's --add-view{target} and run {where} again with "
                  "--rerun")
        if any(word in row["Why"].lower() for word in DOCUMENT_WORDS):
            action += (f", or run {where} again with --rerun if the document can be retrieved; if it cannot be fetched from an "
                       "address, write the figure it asks for into a text file and add it with the folder command's "
                       "`--add-document <review folder> --document <file> --source <where the figure comes from> "
                       f"--cannot-judge-item {row['Item']}{target} --cannot-judge-why <the Why>`, then run {where} again with "
                       "--rerun")
    return (f"item {row['Item']} on {row['Net or part']} is still cannot judge, and the method resolves it within the round; its "
            f"Why asks for {wanted}: {action}")


def row_problems(rows: Sequence[Dict[str, Any]], units: Dict[str, List[str]], names: schematic_facts.Names) -> List[str]:
    """What is wrong with the verdict rows one by one: the item, the cell and the cells the verdict needs."""
    known = set(names.nets) | set(names.parts) | set(names.sheets)
    expected = {item for listed_items in units.values() for item in listed_items}
    found = []
    for row in rows:
        item, cell, verdict = row["Item"], row["Net or part"], row["Verdict"]
        if item not in expected:
            found.append(f"a verdict row for {item}, which this round does not judge; a verdict is accepted only for an item of "
                         "the checklist")
            continue
        if item == FREE_PASS_ENTRY:
            if cell != NONE:
                found.append(f"the free pass's row names {cell!r}, not `{NONE}`; the free pass judges the whole schematic")
            continue
        if cell != NONE and cell not in known:
            found.append(f"the row {pair(row)} names {cell!r}, which is no net, part or sheet of the netlist and the schematic; "
                         "name a net as the netlist writes it, a part by its reference designator and a sheet as the sheet list "
                         f"names it, and run unit {unit_of(item, units)} again with --rerun")
        if verdict in ("pass", "fail") and not str(row["Rests on"]).strip():
            found.append(f"the row {pair(row)} is {verdict} and cites nothing under Rests on, which a {verdict} rests on; run unit "
                         f"{unit_of(item, units)} again with --rerun")
        if verdict in ("not applicable", "fail") and not str(row["Why"]).strip():
            found.append(f"the row {pair(row)} is {verdict} and gives no Why; run unit {unit_of(item, units)} again with --rerun")
    return found


def item_problems(rows: Sequence[Dict[str, Any]], units: Dict[str, List[str]]) -> List[str]:
    """Every item has a verdict row, and an item that selects nothing selects nothing else."""
    counts = Counter(row["Item"] for row in rows)
    nothing = {row["Item"] for row in rows if row["Net or part"] == NONE}
    found = []
    for unit, items in units.items():
        for item in items:
            if counts[item] == 0:
                found.append(f"item {item} has no verdict row; every item the round judges has at least one"
                             f" (judge it in unit {unit} and run that unit again with --rerun)")
            elif item in nothing and item != FREE_PASS_ENTRY and counts[item] > 1:
                found.append(f"item {item} has a `{NONE}` row, which says it selects nothing on this board, and {counts[item] - 1} "
                             f"more row(s) for what it selects; run unit {unit} again with --rerun")
    return found


def coverage_problems(rows: Sequence[Dict[str, Any]], names: schematic_facts.Names) -> List[str]:
    """Every net and part the netlist holds and every sheet the schematic holds is named by a row of some item."""
    named = {row["Net or part"] for row in rows if row["Item"] != FREE_PASS_ENTRY}
    found = []
    for what, held in (("net", names.nets), ("part", names.parts), ("sheet", names.sheets)):
        lacking = sorted(set(held) - named)
        if lacking:
            found.append(f"{len(lacking)} {what}{'s' if len(lacking) != 1 else ''} appear in no item's rows: {listed(lacking)}; the "
                         "items that select every net, part and sheet judge each of them, so run the unit of the item that "
                         "should have named them again with --rerun")
    return found


def finding_problems(rows: Sequence[Dict[str, Any]], findings: Sequence[Dict[str, Any]], label: str,
                     earlier: Set[Tuple[str, int]]) -> List[str]:
    """Each fail cites a finding of its own item, or of an earlier round; each finding names an item that fails, is raised by
    that item and carries a severity of the catalogue's four; a Closed by is the designer's alone."""
    found = []
    by_number = {finding["Finding"]: finding for finding in findings}
    failing = {row["Item"] for row in rows if row["Verdict"] == "fail"}
    for row in rows:
        if row["Verdict"] != "fail":
            continue
        here, before = cited(row, label)
        if not here and not [mark for mark in before if mark in earlier]:
            found.append(f"the row {pair(row)} fails and cites no finding of this round or of an earlier round; its Why is "
                         f"`finding {label}.<n>`, the number of the finding it raises, so run its unit again with --rerun")
        for number in here:
            if number in by_number and by_number[number]["Item"] != row["Item"]:
                found.append(f"the row {pair(row)} cites finding {number}, which names item {by_number[number]['Item']}; a "
                             "verdict cites only findings of its own item")
    for item in sorted(failing, key=[row["Item"] for row in rows].index):
        if not any(finding["Item"] == item for finding in findings) and not any(
                [mark for mark in cited(row, label)[1] if mark in earlier]
                for row in rows if row["Item"] == item and row["Verdict"] == "fail"):
            found.append(f"item {item} fails and no finding names it; the fail raises a finding naming the item and what and "
                         "where, so run its unit again with --rerun")
    for finding in findings:
        number = finding["Finding"]
        if finding["Item"] not in failing:
            found.append(f"finding {number} names item {finding['Item']}, which does not fail in this round; a finding belongs to a "
                         "fail, so run the unit that raised it again with --rerun")
        expected = FREE_PASS_LABEL if finding["Item"] == FREE_PASS_ENTRY else finding["Item"]
        if str(finding["Raised by"]).strip() != expected:
            found.append(f"finding {number} is raised by {str(finding['Raised by'])!r}, not {expected!r}, the item that raised "
                         "it; run its unit again with --rerun")
        if finding["Severity"] not in SEVERITIES:
            found.append(f"finding {number} has the severity {finding['Severity']!r}, outside {list(SEVERITIES)}; run its unit "
                         "again with --rerun")
        if not str(finding["What and where"]).strip():
            found.append(f"finding {number} says nothing under What and where; run its unit again with --rerun")
        if str(finding["Closed by"]).strip():
            found.append(f"finding {number} has a Closed by, which the designer writes and the reviewer never does; run its unit "
                         "again with --rerun")
    return found


def resolution_problems(rows: Sequence[Dict[str, Any]], units: Dict[str, List[str]]) -> List[str]:
    expected = {item for items in units.values() for item in items}
    found = []
    for entry in ROUND["resolutions"]:
        item, target = entry["item"], entry.get("target")
        held = [row for row in rows if row["Item"] == item]
        if item not in expected:
            found.append(f"the folder records a cannot judge for {item!r}, which is not an item this round judges; the item was "
                         "mistyped when the view or document was added, so add it again with the item's exact name")
        elif not held:
            found.append(f"the folder records a cannot judge for {item}, which has no verdict row in this round; run the unit "
                         "that judges it again with --rerun")
        elif target is not None and not any(row["Net or part"] == target for row in held):
            found.append(f"the folder records a cannot judge for {item} on {target!r}, which has no verdict row in this round; run "
                         f"unit {unit_of(item, units)} again with --rerun, or add the view or document again with the net, part "
                         "or sheet the row names")
    return found


def checks(tables: Dict[str, Any]) -> List[str]:
    """What the merge refuses: an item with no verdict row, a verdict for an item the round does not judge, a net, part or sheet
    no item's rows name, a row naming one that does not exist, an item that selects nothing and also something, a row without the
    cells its verdict rests on, a recorded cannot judge without a row, a cannot judge still held, and the faults of the findings."""
    if not ROUND:
        return ["the schematic caller's checks ran before its declaration was resolved for a review folder, so the items the round "
                "judges and the schematic's nets, parts and sheets are not known; resolve the declaration first"]
    units, names, label = ROUND["units"], ROUND["names"], ROUND["label"]
    rows, findings = tables["Verdicts"]["rows"], tables["Findings"]["rows"]
    found = row_problems(rows, units, names) + item_problems(rows, units) + coverage_problems(rows, names)
    found += resolution_problems(rows, units)
    found += [cannot_judge_problem(row, units) for row in rows if row["Verdict"] == "cannot judge"]
    return found + finding_problems(rows, findings, label, ROUND.get("earlier", set()))


# --- The round's label and its earlier findings ----------------------------------------------------


def round_label(review: str) -> str:
    return str(schematic_round(review)["number"])


def earlier_findings(review: str) -> List[Tuple[str, int]]:
    """The (round, number) pairs of the findings the review folder's earlier rounds hold, none for a first round."""
    path = os.path.join(design_path(review), schematic_review_folder.RECORD)
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
    """A verdict row as the record gives it; one that resolves a cannot judge records `cannot judge, then <verdict>`, each view or
    document added for it in Rests on after what the reviewer cited, and the Why of the cannot judge before the reviewer's own."""
    if not entries:
        return row
    added = [f"`{entry['document' if entry['kind'] == 'document' else 'view']}`" for entry in entries]
    asked = " ".join(f"Cannot judge: {entry['why']}." for entry in entries)
    return {**row, "Verdict": f"cannot judge, then {row['Verdict']}", "Rests on": "; ".join([str(row["Rests on"])] + added),
            "Why": f"{asked} {row['Why']}"}


def render(review: str, tables: Dict[str, Any]) -> Dict[str, str]:
    """The merged round as the method gives it, written as round-<n>.md: the round heading, the opening fields, the Verdicts
    table, and the Findings table or the line saying no finding was raised."""
    try:
        round_ = schematic_round(review)
        resolutions = review_folder.read_resolutions(review)
        order = {item: index for index, item in enumerate(checklist(review))}
    except ReviewFolderProblem as error:
        raise Refused([str(error)])
    number = round_["number"]
    name = f"round-{number}.md"
    if isinstance(number, bool) or not isinstance(number, int) or not RENDERED.fullmatch(name):
        raise Refused([f"the round number {number!r} does not give a file name of the form round-<n>.md; write the folder with the "
                       "folder command"])
    rows = sorted((row for row in tables["Verdicts"]["rows"] if row["Item"] != FREE_PASS_ENTRY),
                  key=lambda row: (order[row["Item"]], row["Net or part"] != NONE, row["Net or part"]))
    made = []
    for row in rows:
        entries = [entry for entry in resolutions if entry["item"] == row["Item"] and entry.get("target") in (None, row["Net or part"])]
        made.append(verdict_row(row, entries))
    text = [f"## Round {number}", "", f"- **Schematic judged**: {round_['commit']}",
            "- **Netlist**: the command as it was run:", "", "```", round_["netlist"], "```", "",
            "- **Records read**: each record by path, with the separation basis record's `accepted_on` where the board declares "
            "mains:", ""]
    text += [f"  - {record}" for record in round_["records"]]
    text += ["", "### Verdicts", ""] + results.table_lines(VERDICT_TABLE, made)
    findings = tables["Findings"]["rows"]
    text += ["", "### Findings", ""]
    if findings:
        text += results.table_lines(RECORD_FINDING_TABLE, [
            {**row, "Finding": f"{number}.{row['Finding']}",
             "Raised by": FREE_PASS_LABEL if row["Item"] == FREE_PASS_ENTRY else row["Item"]} for row in findings])
    else:
        text += [board_review_history.NO_FINDINGS]
    return {name: "\n".join(text) + "\n"}
