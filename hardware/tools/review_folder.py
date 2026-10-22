#!/usr/bin/env python3
"""Write the review folder of a committed board, for a judged review to read, and add a view to it.

A judged review reads a folder that holds what the layout review step gives a
reviewer and nothing of the designer's reasoning. For a board committed in a
repository this command writes it, outside the repository: the board's design
files as the commit holds them, with its plan, its rules table and the records
those name; the method and the hardware notes; the rendered views and the
placement view; the pre-order check's report; two extracts written from the
commit, the layout facts (the positions, pads, segments, vias and zones of the
board file) and the method's sections a layout review needs; and one round file
that holds the round's own fields. It holds no session or notes file and no other
file the commit does not hold. For a round after the first it also holds the earlier
rounds of the board's review record as the commit holds them, since a verdict
row may cite a finding an earlier round closed by a reason, and for a first
round it holds no review record.

    review_folder.py --repo <repository> --commit <commit> --design <board folder from the root>
                     --out <new folder> --views <views folder> --placement <placement folder>
                     --check-report <file> --number N --kind full|narrow --view-command <text>...
                     --check-line <line>... [--item ITEM=reason... --region <text>... --others <text>]
                     [--documents-repo <repository> [--documents-commit <commit>]]
                     [--round-fields number,kind,commit,views,check] [--json]
    review_folder.py --review critical-routing --repo <repository> --commit <commit> --design <board folder from the root>
                     --out <new folder> --views <views folder> [--placement <placement folder>] --number N
                     --view-command <text>... [--documents-repo <repository> [--documents-commit <commit>]] [--json]
    review_folder.py --add-view <folder> --view <file> --view-command <text>
                     --cannot-judge-item <item> --cannot-judge-why <text> [--json]
    review_folder.py --add-document <folder> --document <text file> --source <where the figure comes from>
                     --cannot-judge-item <item> --cannot-judge-why <text> [--json]

The round's fields are the set --round-fields names, which is a parameter of the
command: the layout review's are its number, kind, the commit judged (taken from
--commit), the commands the views were rendered with and the pre-order check's
lines, and another review whose round has no kind or check lines names its own
set. A narrow round, one whose kind is narrow, also gives its listed items, each
with the reason the changed regions touch it, its changed regions and the line
saying why every other item is not judged; a full round gives none of them. A
missing or malformed field refuses the command, naming it.

--review critical-routing writes the folder the critical-routing check reads, the check step 4 of the method's routing section
makes before the router runs. Its round fields are the pass number, the commit judged and the views, and no more: the round
file holds no kind and no check lines. The method extract adds the routing section to the layout review's sections. The
placement view is taken only when --placement is given, and the pre-order check's report not at all, since that check is not
run at this step and --check-report, --kind, --check-line, --item, --region and --others are refused. A pass after the first
copies no review record, its earlier passes being in the plan the commit holds. --add-view and --add-document serve this
folder as they serve a layout folder; its checklist is the catalogue's items and the plan's board items, with no comparison
with the plan. The layout review is the default.

--add-view puts a view the starter rendered into the added-views folder of a
folder this command wrote and records, in a resolutions file there, the item whose
cannot judge asked for the view, with that Why, the view and the command that
rendered it, so the merge can build the row from them once the unit is judged
again. The round file is not rewritten and nothing of the shared context changes.
It refuses a view that does not exist and a folder this command did not write.

--add-document is the same for a cannot judge whose Why asks for a document the folder
lacks and the plan gives no address to fetch it from: it puts a text file holding the
figure or passage into the added-documents folder of a folder this command wrote and
records in the same resolutions file the item, the Why, the document and the source
the figure comes from. It refuses a file that does not exist, is not UTF-8 text or is
larger than 64 KiB, an empty or multi-line source, a name the folder already holds, an
item the folder's checklist does not hold and a folder this command did not write.

Each cause is reported on one line beginning REFUSED, a RESULT line comes last,
and the exit status is 0 when the folder is written, 1 when the command refuses
and 2 when git is missing. --json prints the same facts as one JSON document.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)

import board_check  # noqa: E402
import board_review_history  # noqa: E402
import review_seed  # noqa: E402
import sexpr  # noqa: E402

REPO = review_seed.REPO
#: The round file, in the review folder's root, and the marker that says this command wrote it.
ROUND_FILE = "round.json"
TOOL = "review-folder"
ADDED_VIEWS = "added-views"
#: The folder of a production-files review folder that holds the assembler's preview as supplied.
PREVIEW = "preview"
#: The folder of a review folder that holds the text files added to resolve a cannot judge that needed a document.
ADDED_DOCUMENTS = "added-documents"
#: The largest text file the add-document mode takes.
DOCUMENT_LIMIT = 64 * 1024
#: The checklist entry of the comparison with the plan and the free pass, which no catalogue item or plan row names.
COMPARISON_ITEM = "PLAN-AND-FREE-PASS"
#: The file of the added-views folder that records each cannot judge a view was added for.
RESOLUTIONS = "resolutions.json"
#: The extracts written into the folder from the commit: the layout facts, and the method's sections a layout review needs.
LAYOUT_FACTS = "layout-facts.txt"
METHOD_EXTRACT = "method-extract.md"
METHOD = "docs/board-design-method.md"
#: The method's sections in the method extract, in the order it holds them; the last is the whole layout practice catalogue.
METHOD_SECTIONS = ("Layout review", "Layout review views", "Layout practice catalogue")
#: The section of the method that holds the critical-routing check, which the critical-routing folder's extract adds.
ROUTING_SECTION = "Routing: critical nets by hand and locked, then the rest"
#: The section of the method that holds the catalogue a folder's items are taken from.
CATALOGUE_SECTION = "Layout practice catalogue"
#: The reviews the folder command writes a folder for, the layout review being the default.
LAYOUT = "layout"
CRITICAL_ROUTING = "critical-routing"
REVIEWS = (LAYOUT, CRITICAL_ROUTING)
#: The method's sections each review's extract holds, in order.
REVIEW_SECTIONS = {LAYOUT: METHOD_SECTIONS, CRITICAL_ROUTING: (ROUTING_SECTION,) + METHOD_SECTIONS}
CHECK_REPORT = review_seed.REPORT
VIEWS = review_seed.VIEWS
PLACEMENT = review_seed.PLACEMENT
#: A board's review record, in the board's own folder.
RECORD = board_review_history.RECORD
#: The folders of a review folder that hold no design.
NOT_DESIGN = (VIEWS, PLACEMENT, ADDED_VIEWS, ADDED_DOCUMENTS)
KINDS = ("full", "narrow")
#: The layout review's round fields, in the order a round file gives them.
LAYOUT_FIELDS = ("number", "kind", "commit", "views", "check")
#: The critical-routing check's pass fields: the pass number, the commit judged and the views, in the order a round file gives them.
CRITICAL_FIELDS = ("number", "commit", "views")
def is_production_fields(fields: Sequence[str]) -> bool:
    """Whether a round file's fields are the production-files check's, the one test of that folder's review."""
    return list(fields) == list(PRODUCTION_FIELDS)


def is_critical_routing_fields(fields: Sequence[str]) -> bool:
    """Whether a round file's fields are a critical-routing pass's; the one test of a folder's review, since a layout folder
    may be written with any documented subset of its fields."""
    return list(fields) == list(CRITICAL_FIELDS)


def critical_round_extra_keys(content: Dict[str, Any]) -> List[str]:
    """The keys of a critical-routing pass's round file that the pass does not own: any key outside the tool, the fields and
    the fields' own values, such as a kind, check lines or listed items, which only a layout round has."""
    return sorted(key for key in content if key not in ("tool", "fields") + CRITICAL_FIELDS)


#: The round fields each review's folder has.
REVIEW_FIELDS = {LAYOUT: LAYOUT_FIELDS, CRITICAL_ROUTING: CRITICAL_FIELDS}
#: The fields of a layout round and of a critical-routing pass, which are subsets of one list.
LAYOUT_FIELD_NAMES = ("number", "kind", "commit", "views", "check")
#: The production-files check's fields, in the order its round file gives them: the commit judged, the tools and the commands the
#: files were exported and drawn with, and the line saying what the assembler's preview is.
PRODUCTION_FIELDS = ("commit", "tools", "commands", "preview")
#: Every field a set may name.
FIELD_NAMES = LAYOUT_FIELD_NAMES + ("tools", "commands", "preview")
#: The fields a narrow round adds to its set when the set has a kind.
NARROW_FIELDS = ("items", "regions", "others")
#: What a line of the pre-order check's report that a round states begins with.
CHECK_LINE = re.compile(r"(DESIGN|FIGURE|VIOLATION) \|")
COMMIT = re.compile(r"[0-9a-f]{7,64}")
PLAIN_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class Refused(Exception):
    """The command will not go on, for the causes given."""

    def __init__(self, causes: Sequence[str]):
        super().__init__("; ".join(causes))
        self.causes = list(causes)


class ReviewFolderProblem(Exception):
    """A review folder a judged review cannot be run on, with what to do about it."""


#: The one file of the fabrication folder that is no layer: the job file, which the render draws no image of.
JOB_FILE_SUFFIX = ".gbrjob"


def unlisted_fabrication_files(gerbers: str, images: Any) -> List[str]:
    """The files of the fabrication folder `gerbers`, by path from it, that no entry of the layer images index names as its
    `source`, the job file apart. The index is the one authority for which layers get a row, so a Gerber or drill file it does
    not list would be judged by no unit and named by no record. Names are compared without case."""
    listed = {entry["source"].casefold() for entry in images if isinstance(entry, dict) and isinstance(entry.get("source"), str)} \
        if isinstance(images, list) else set()
    found = []
    for directory, _, names in os.walk(gerbers):
        for name in names:
            path = os.path.relpath(os.path.join(directory, name), gerbers).replace(os.sep, "/")
            if not name.casefold().endswith(JOB_FILE_SUFFIX) and path.casefold() not in listed:
                found.append(path)
    return sorted(found)


# --- The round's fields -------------------------------------------------------------------------


def one_line(value: Any) -> bool:
    """Whether `value` is non-empty text of one line."""
    return isinstance(value, str) and bool(value.strip()) and "\n" not in value and "\r" not in value


def round_problems(values: Dict[str, Any], fields: Sequence[str] = LAYOUT_FIELDS) -> List[str]:
    """Why the round's fields are not the set `fields` asks for, each naming the field: one missing or not of its form,
    a narrow round's listed items, changed regions or why-others line missing, or a full round's present."""
    found: List[str] = []
    number, kind = values.get("number"), values.get("kind")
    if "number" in fields and (isinstance(number, bool) or not isinstance(number, int) or number < 1):
        found.append(f"the round's number is {number!r}; give a whole number of one or more")
    if "kind" in fields and kind not in KINDS:
        found.append(f"the round's kind is {kind!r}; give `full` or `narrow`, in lowercase")
    if "commit" in fields and not (isinstance(values.get("commit"), str) and COMMIT.fullmatch(values["commit"])):
        found.append(f"the commit judged is {values.get('commit')!r}; give the commit's hexadecimal id")
    if "views" in fields:
        views = values.get("views")
        if not isinstance(views, list) or not views or not all(one_line(view) and "```" not in view for view in views):
            found.append(f"the views are {views!r}; give each command a view was rendered with as one line of text, and "
                         "at least one")
    if "check" in fields:
        lines = values.get("check")
        if not isinstance(lines, list) or not lines or not all(one_line(line) and CHECK_LINE.match(line) and "```" not in line
                                                               for line in lines):
            found.append(f"the pre-order check's lines are {lines!r}; give the board's DESIGN line and every FIGURE and "
                         "VIOLATION line under it, each as one line of the report and at least the DESIGN line")
        elif sum(line.startswith("DESIGN |") for line in lines) != 1:
            found.append("the pre-order check's lines hold no DESIGN line, or more than one; give the board's one DESIGN line")
    if "tools" in fields and not (one_line(values.get("tools")) and "```" not in values["tools"]):
        found.append(f"the tools are {values.get('tools')!r}; give the versions of the export and drawing tools as one line of text")
    if "commands" in fields:
        commands = values.get("commands")
        if not isinstance(commands, list) or not commands or not all(one_line(line) and "```" not in line for line in commands):
            found.append(f"the commands are {commands!r}; give each command the files were exported or drawn with as one line "
                         "of text, and at least one")
    if "preview" in fields and not (one_line(values.get("preview")) and "```" not in values["preview"]):
        found.append(f"the preview line is {values.get('preview')!r}; give what the assembler's preview is, with its date, as "
                     "one line of text")
    if "kind" in fields and kind == "narrow":
        found += narrow_problems(values)
    elif "kind" not in fields or kind == "full":
        given = [name for name in NARROW_FIELDS if values.get(name) not in (None, [], "")]
        if given:
            found.append(f"a round that is not narrow gives {', '.join(given)}, which only a narrow round has; leave them out")
    return found


def narrow_problems(values: Dict[str, Any]) -> List[str]:
    found = []
    items = values.get("items")
    if not isinstance(items, list) or not items or not all(
            isinstance(entry, dict) and one_line(entry.get("item")) and one_line(entry.get("reason")) for entry in items):
        found.append(f"a narrow round's listed items are {items!r}; give each item with the reason the changed regions or "
                     "nets touch it, and at least one")
    elif len({entry["item"] for entry in items}) != len(items):
        found.append("a narrow round lists an item twice; list each item once")
    regions = values.get("regions")
    if not isinstance(regions, list) or not regions or not all(one_line(region) for region in regions):
        found.append(f"a narrow round's changed regions are {regions!r}; name each floorplan region and net the fix commits "
                     "change, from those commits, and at least one")
    if not one_line(values.get("others")):
        found.append(f"a narrow round's line saying why every other item is not judged is {values.get('others')!r}; give it")
    return found


def read_round(folder: str) -> Dict[str, Any]:
    """The round file of a review folder this command wrote, its fields checked against the set it names."""
    path = os.path.join(folder, ROUND_FILE)
    try:
        with open(path, encoding="utf-8") as handle:
            content = json.load(handle)
    except (OSError, ValueError, RecursionError) as error:
        raise ReviewFolderProblem(f"the review folder's round file {path} cannot be read ({error}); write the folder with "
                                  "the folder command, which writes it")
    fields = content.get("fields") if isinstance(content, dict) else None
    if (not isinstance(content, dict) or content.get("tool") != TOOL or not isinstance(fields, list)
            or not all(name in FIELD_NAMES for name in fields)):
        raise ReviewFolderProblem(f"the round file {path} is not one the folder command wrote; write the folder with it")
    if any(name in PRODUCTION_FIELDS[1:] for name in fields) and not is_production_fields(fields):
        raise ReviewFolderProblem(f"the round file {path} mixes the production-files check's fields with another review's; "
                                  "write the folder with the folder command")
    if is_production_fields(fields):
        stray = sorted(key for key in content if key not in ("tool", "fields") + tuple(PRODUCTION_FIELDS))
        if stray:
            raise ReviewFolderProblem(f"the round file {path} holds {', '.join(stray)}, which the production-files check's round "
                                      f"file does not have (it holds {', '.join(PRODUCTION_FIELDS)}); write the folder with the "
                                      "folder command")
    problems = round_problems(content, fields)
    if problems:
        raise ReviewFolderProblem(f"the round file {path} holds fields that are missing or malformed: " + "; ".join(problems))
    extra = critical_round_extra_keys(content) if is_critical_routing_fields(fields) else []
    if extra:
        raise ReviewFolderProblem(f"the round file {path} is a critical-routing pass's but holds {', '.join(extra)}, which a pass "
                                  "does not have; write the folder with the folder command's --review critical-routing")
    return content


def design_in(folder: str) -> str:
    """The folder, from the review folder's root, of the one board design a review folder holds: the folder of its one
    KiCad project file, outside the views folders."""
    found = []
    for directory, names, files in os.walk(folder):
        if directory == folder:
            names[:] = [name for name in names if name not in NOT_DESIGN]
        found += [os.path.relpath(directory, folder) for name in files if name.endswith(".kicad_pro")]
    if len(found) != 1:
        raise ReviewFolderProblem(f"the review folder {folder} holds {len(found)} KiCad project files outside its views; it "
                                  "must hold the one design under review, so write it with the folder command")
    return found[0]


def read_resolutions(folder: str) -> List[Dict[str, str]]:
    """The cannot judge resolutions the add-view and add-document modes recorded in a review folder, in the order they were
    added; none when nothing was added. Each is an item, the Why of its cannot judge and either the view added for it with
    the command that rendered it or the document added for it with its source; an entry with no kind is a view, and every
    entry comes back with its kind. The file added must be a file of the folder."""
    path = os.path.join(folder, ADDED_VIEWS, RESOLUTIONS)
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            content = json.load(handle)
    except (OSError, ValueError, RecursionError) as error:
        raise ReviewFolderProblem(f"the resolutions file {path} cannot be read ({error}); add the views and documents again "
                                  "with the folder command's --add-view and --add-document")
    entries = content.get("resolutions") if isinstance(content, dict) and content.get("tool") == TOOL else None
    keys = {"view": ("item", "why", "view", "command"), "document": ("item", "why", "document", "source")}
    if not isinstance(entries, list) or not all(
            isinstance(entry, dict) and entry.get("kind", "view") in keys
            and all(one_line(entry.get(key)) for key in keys[entry.get("kind", "view")]) for entry in entries):
        raise ReviewFolderProblem(f"the resolutions file {path} holds {entries!r:.100}, which is not a list of an item, a Why "
                                  "and a view with its command or a document with its source each; add them with the folder "
                                  "command's --add-view and --add-document")
    for entry in entries:
        kind = entry.get("kind", "view")
        if not os.path.isfile(os.path.join(folder, entry[kind])):
            raise ReviewFolderProblem(f"the resolutions file {path} names the {kind} {entry[kind]}, which the folder does not "
                                      f"hold; add the {kind} again with the folder command's --add-{kind}")
    return [{**entry, "kind": entry.get("kind", "view")} for entry in entries]


# --- The extracts written from the commit -------------------------------------------------------


class FactsError(ValueError):
    """The board file cannot be read for the layout facts."""


def method_section(text: str, heading: str) -> Optional[str]:
    """The method's `## <heading>` section, up to the next level-two heading; None when the method has none."""
    found = re.search(r"^## " + re.escape(heading) + r"[ \t]*\n.*?(?=^## |\Z)", text, re.M | re.S)
    return found.group(0).rstrip() + "\n" if found else None


def missing_sections(text: str, review: str = LAYOUT) -> List[str]:
    """The sections the review's extract holds that the method text lacks."""
    return [heading for heading in REVIEW_SECTIONS[review] if method_section(text, heading) is None]


def method_extract(text: str, review: str = LAYOUT) -> str:
    """The method's sections the review needs, as the extract the shared context holds: for the layout review its layout
    review section, its views section and the whole layout practice catalogue, and for the critical-routing check the
    routing section before them; a method that lacks one is a refusal naming it."""
    lacking = missing_sections(text, review)
    if lacking:
        raise Refused([f"the method {METHOD} has no `## {heading}` section, which the review's shared context holds; give "
                       "documents that hold it" for heading in lacking])
    needs = "a layout review" if review == LAYOUT else "the critical-routing check"
    return ("METHOD EXTRACT from " + METHOD + f": the sections of the method that {needs} needs, in this order.\n\n"
            + "\n".join(method_section(text, heading) for heading in REVIEW_SECTIONS[review]))


def millimetres(value: Any) -> str:
    text = ("%.4f" % float(value)).rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def reference_key(reference: str):
    found = re.match(r"([A-Za-z]+)(\d+)", reference)
    return (found.group(1), int(found.group(2)), reference) if found else (reference, 0, reference)


def layout_facts(text: str, name: str) -> str:
    """The positions, pads, segments, vias and zones of a layout file, as plain text a reviewer reads a distance from: no
    judgement, millimetres in board coordinates, the same text for the same file. A file that cannot be read is a FactsError."""
    try:
        root = sexpr.parse_one(text)
        return facts_text(root, name)
    except (sexpr.SexprError, ValueError, IndexError, TypeError) as error:
        raise FactsError(f"the layout file {name} cannot be read for the layout facts ({error}); commit a layout file KiCad "
                         "wrote")


def net_name(node: Any, names: Dict[str, str]) -> str:
    """The net a pad, segment, via or zone belongs to: KiCad writes `(net <id> "<name>")` or `(net "<name>")`."""
    if node is None or len(node) < 2:
        return "-"
    if len(node) > 2:
        return str(node[2])
    return names.get(str(node[1]), str(node[1]))


def facts_text(root: list, name: str) -> str:
    kids, kid = sexpr.children, sexpr.child
    f = millimetres
    names = {str(n[1]): str(n[2]) for n in kids(root, "net") if len(n) > 2}
    out = [f"LAYOUT FACTS extracted from {name} (millimetres, board coordinates, y grows downward; angles in degrees as in "
           "the file). Pad positions are absolute (footprint position and rotation applied); a pad's rot is its absolute orientation as the file writes it.", "", "== BOARD =="]
    for layers in kids(root, "layers")[:1]:
        out.append("layers: " + ", ".join(f"{l[1]}({l[2]})" for l in layers[1:] if isinstance(l, list) and len(l) > 2))
    for g in root[1:]:
        if isinstance(g, list) and sexpr.head(g) in ("gr_line", "gr_rect", "gr_arc", "gr_circle", "gr_poly"):
            layer = kid(g, "layer")
            if layer and layer[1] == "Edge.Cuts":
                start, end = kid(g, "start"), kid(g, "end")
                out.append(f"{g[0]} Edge.Cuts " + (f"({f(start[1])},{f(start[2])})-({f(end[1])},{f(end[2])})" if start and end else ""))
    out += ["", "== FOOTPRINTS (reference | library id | layer | at x,y,rot | value) =="]
    parts = []
    for fp in kids(root, "footprint"):
        reference = value = ""
        for p in kids(fp, "property"):
            if p[1] == "Reference":
                reference = str(p[2])
            if p[1] == "Value":
                value = str(p[2])
        for t in kids(fp, "fp_text"):
            if len(t) > 2 and t[1] == "reference" and not reference:
                reference = str(t[2])
            if len(t) > 2 and t[1] == "value" and not value:
                value = str(t[2])
        at, layer = kid(fp, "at"), kid(fp, "layer")
        rotation = float(at[3]) if len(at) > 3 else 0.0
        parts.append((reference, str(fp[1]), str(layer[1]), float(at[1]), float(at[2]), rotation, value, fp))
    parts.sort(key=lambda part: (reference_key(part[0]), part[1], part[3], part[4]))
    for reference, library, layer, x, y, rotation, value, fp in parts:
        out.append(f"{reference} | {library} | {layer} | at {f(x)},{f(y)},{f(rotation)} | {value}")
    out += ["", "== PADS (per footprint: pad number | absolute x,y | shape size w x h | layers | net) =="]
    for reference, library, layer, x, y, rotation, value, fp in parts:
        out.append(f"{reference} ({layer}):")
        angle = math.radians(rotation)
        for pad in kids(fp, "pad"):
            at = kid(pad, "at")
            px, py = float(at[1]), float(at[2])
            ax = x + px * math.cos(angle) + py * math.sin(angle)
            ay = y - px * math.sin(angle) + py * math.cos(angle)
            turned = float(at[3]) if len(at) > 3 else 0.0
            size, layers = kid(pad, "size"), kid(pad, "layers")
            out.append(f"  {pad[1]} | {f(ax)},{f(ay)} | {pad[3] if len(pad) > 3 else ''} {f(size[1])}x{f(size[2])}"
                       f"{' rot ' + f(turned) if turned % 360 else ''} | {' '.join(map(str, layers[1:])) if layers else ''} | "
                       f"{net_name(kid(pad, 'net'), names)}")
    out += ["", "== TRACK SEGMENTS per net (start -> end | width | layer) =="]
    segments: Dict[str, list] = {}
    for s in kids(root, "segment"):
        start, end = kid(s, "start"), kid(s, "end")
        segments.setdefault(net_name(kid(s, "net"), names), []).append(
            (str(kid(s, "layer")[1]), f(start[1]), f(start[2]), f(end[1]), f(end[2]), f(kid(s, "width")[1])))
    for net in sorted(segments):
        out.append(f"{net}:")
        for layer, x1, y1, x2, y2, width in sorted(segments[net]):
            out.append(f"  {layer} | ({x1},{y1}) -> ({x2},{y2}) | w {width}")
    out += ["", "== VIAS (x,y | size/drill | layers | net) =="]
    vias = []
    for v in kids(root, "via"):
        at, layers = kid(v, "at"), kid(v, "layers")
        vias.append((net_name(kid(v, "net"), names), float(at[1]), float(at[2]), f(kid(v, "size")[1]), f(kid(v, "drill")[1]),
                     "-".join(map(str, layers[1:])) if layers else ""))
    for net, x, y, size, drill, layers in sorted(vias):
        out.append(f"{net} | {f(x)},{f(y)} | {size}/{drill} | {layers}")
    out += ["", "== ZONES (name | net | layers | clearance | min thickness | connect | outline bbox and vertices | filled polygons count) =="]
    for z in kids(root, "zone"):
        zone_name = kid(z, "name")
        named = kid(z, "net_name")
        net = str(named[1]) if named and len(named) > 1 else net_name(kid(z, "net"), names)
        layers = kid(z, "layer") or kid(z, "layers")
        polygon = kid(z, "polygon")
        pts = kid(polygon, "pts") if polygon else None
        xy = [(float(p[1]), float(p[2])) for p in kids(pts, "xy")] if pts else []
        box = (f"bbox ({f(min(p[0] for p in xy))},{f(min(p[1] for p in xy))})-({f(max(p[0] for p in xy))},"
               f"{f(max(p[1] for p in xy))})") if xy else ""
        vertices = " ".join(f"({f(p[0])},{f(p[1])})" for p in xy)
        connect = kid(z, "connect_pads")
        clearance = kid(connect, "clearance") if connect else None
        thickness = kid(z, "min_thickness")
        out.append(f"{zone_name[1] if zone_name else '-'} | net {net}"
                   f" | {' '.join(map(str, layers[1:])) if layers else ''} | clearance {f(clearance[1]) if clearance else '-'}"
                   f" | min thickness {f(thickness[1]) if thickness else '-'} | {'keepout' if kid(z, 'keepout') else 'copper pour'}"
                   f" | {box} | vertices {vertices} | filled polygons {len(kids(z, 'filled_polygon'))}")
    out += ["", "== OTHER GRAPHICS (non-Edge.Cuts gr_ items: type layer endpoints) =="]
    for g in root[1:]:
        if isinstance(g, list) and sexpr.head(g).startswith("gr_") and sexpr.head(g) != "gr_text":
            layer = kid(g, "layer")
            if layer and layer[1] != "Edge.Cuts":
                start, end = kid(g, "start"), kid(g, "end")
                out.append(f"{g[0]} {layer[1]} " + (f"({f(start[1])},{f(start[2])})-({f(end[1])},{f(end[2])})" if start and end else ""))
    return "\n".join(out) + "\n"


# --- The command --------------------------------------------------------------------------------


def git(repo: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)


#: The arguments a critical-routing folder has no use for, by the flag that gives each: its pass has no kind, no check lines
#: and no listed items, and the pre-order check is not run at the step, so it has no report.
NOT_OF_CRITICAL_ROUTING = (("kind", "--kind", "a pass has no kind"), ("check_line", "--check-line", "a pass has no check lines"),
                           ("check_report", "--check-report", "the pre-order check is not run at this step, so a pass has no report"),
                           ("item", "--item", "a pass lists no items"), ("region", "--region", "a pass lists no regions"),
                           ("others", "--others", "a pass has no line saying why other items are not judged"))


def review_refusals(args: argparse.Namespace, review: str, fields: Sequence[str]) -> List[str]:
    """Why the arguments are not those of the review the folder is written for."""
    if review == LAYOUT:
        return []
    found = [f"the critical-routing folder takes no {flag}: {why}; leave it out" for name, flag, why in NOT_OF_CRITICAL_ROUTING
             if getattr(args, name) not in (None, [])]
    if not is_critical_routing_fields(fields):
        found.append(f"the critical-routing folder's round fields are {', '.join(CRITICAL_FIELDS)}, not {', '.join(fields)}; "
                     "leave --round-fields out")
    return found


def refusals(args: argparse.Namespace, out: str, repo: str, documents_repo: str, values: Dict[str, Any],
             fields: Sequence[str], review: str = LAYOUT) -> List[str]:
    found = []
    for name, where in (("repository", repo), ("documents repository", documents_repo)):
        if review_seed.inside(out, where):
            found.append(f"the review folder {out} is inside the {name} {where}; a reviewer working there could read the "
                         "design as committed and the earlier rounds' verdicts, so give a folder outside it")
    if os.path.isfile(out):
        found.append(f"the review folder {out} is a file; give a new or empty folder")
    elif os.path.isdir(out) and os.listdir(out):
        found.append(f"the review folder {out} already holds files; give a new or empty folder")
    unknown = [name for name in fields if name not in LAYOUT_FIELD_NAMES]
    if unknown:
        found.append(f"the round fields {', '.join(unknown)} are not fields of a round; the fields are {', '.join(LAYOUT_FIELD_NAMES)}")
    else:
        found += round_problems(values, fields)
    given = [("views", args.views)] + ([("placement view", args.placement)] if review == LAYOUT or args.placement else [])
    for name, path in given:
        if not os.path.isfile(os.path.join(path, "index.txt")):
            found.append(f"the {name} folder {path} is missing or holds no index.txt; render it with the command the "
                         "round's first step names, and give that folder")
    if review == LAYOUT and not os.path.isfile(args.check_report):
        found.append(f"the pre-order check's report {args.check_report} does not exist; run the check and give its report")
    return found


def committed_board(repo: str, commit: str, design: str) -> Dict[str, Any]:
    """The commit's full id and the design's given files, or the causes the commit holds no board."""
    resolved = git(repo, "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}")
    if resolved.returncode != 0:
        raise Refused([f"the commit {commit} is not in the repository {repo}; give a commit it holds"])
    sha = resolved.stdout.strip()
    files = review_seed.design_files(repo, sha, design)
    projects = [name for name in files if "/" not in name and name.endswith(".kicad_pro")]
    layouts = [name for name in files if "/" not in name and name.endswith(".kicad_pcb")]
    if len(projects) != 1 or len(layouts) != 1:
        raise Refused([f"the commit {commit} holds no board at {design}: it needs the design folder's one KiCad project and "
                       f"its one layout, and holds {len(projects)} projects and {len(layouts)} layouts there"])
    return {"sha": sha, "files": files}


def earlier_rounds(text: str, number: int) -> Optional[str]:
    """The record's text up to the first heading of a round numbered `number` or more, as recorded; None when it holds no
    earlier round."""
    kept, earlier = [], False
    for _, line, fenced in board_review_history.record_lines(text)[0]:
        mark = None if fenced else board_review_history.ROUND.fullmatch(line)
        if mark:
            if int(mark.group(1)) >= number:
                break
            earlier = True
        kept.append(line)
    return "\n".join(kept).rstrip("\n") + "\n" if earlier else None


def earlier_numbers(text: str, number: int) -> List[int]:
    """The numbers of the round headings the record holds before the first one numbered `number` or more, as recorded."""
    found: List[int] = []
    for _, line, fenced in board_review_history.record_lines(text)[0]:
        mark = None if fenced else board_review_history.ROUND.fullmatch(line)
        if mark:
            if int(mark.group(1)) >= number:
                break
            found.append(int(mark.group(1)))
    return found


def round_content(fields: Sequence[str], values: Dict[str, Any]) -> Dict[str, Any]:
    """The round file's content: the marker, the field set and the values of the fields in it (and a narrow round's own)."""
    return {"tool": TOOL, "fields": list(fields), **{key: values[key] for key in values
            if key in fields or key in NARROW_FIELDS and values[key] not in (None, [], "")}}


def settled(content: Dict[str, Any]) -> str:
    return json.dumps(content, indent=1, sort_keys=True) + "\n"


def write_folder(args: argparse.Namespace, out: str, repo: str, documents_repo: Optional[str], fields: Sequence[str],
                 review: str = LAYOUT) -> Dict[str, Any]:
    """The review folder, or a refusal naming every cause."""
    values: Dict[str, Any] = {"number": args.number, "kind": args.kind, "views": args.view_command or [],
                              "check": args.check_line or []}
    if "kind" in fields and args.kind == "narrow":
        values["items"] = [pair_of(entry) for entry in args.item or []]
        values["regions"], values["others"] = args.region or [], args.others
    else:
        values["items"], values["regions"], values["others"] = args.item or [], args.region or [], args.others
    causes: List[str] = []
    board: Dict[str, Any] = {}
    try:
        board = committed_board(repo, args.commit, args.design)
        values["commit"] = board["sha"]
    except Refused as error:
        causes += error.causes
        values["commit"] = "0" * 7  # a commit that does not exist is the cause; the field itself is not reported twice
    causes += review_refusals(args, review, fields)
    causes += refusals(args, out, repo, documents_repo or REPO, values, fields, review)
    record = None
    if board and review == LAYOUT and "number" in fields and isinstance(args.number, int) and args.number > 1:
        held = review_seed.archived(repo, board["sha"], f"{args.design.rstrip('/')}/{RECORD}")
        text = next(iter(held.values()), b"").decode("utf-8", errors="replace")
        record = earlier_rounds(text, args.number)
        if record is None:
            causes.append(f"round {args.number} cites the earlier rounds of the review record, and the commit's {RECORD} "
                          "holds none; commit the record with the earlier rounds before the round")
        else:
            missing = sorted(set(range(1, args.number)) - set(earlier_numbers(text, args.number)))
            if missing:
                causes.append(f"round {args.number} cites the earlier rounds of the review record, which must hold rounds 1 to "
                              f"{args.number - 1}, and the commit's {RECORD} lacks round "
                              + ", ".join(str(n) for n in missing) + "; commit the record with every earlier round before the round")
    try:
        documents = review_seed.documents(documents_repo, args.documents_commit)
    except review_seed.Refused as error:
        causes.append(str(error))
        documents = None
    extracts: Dict[str, str] = {}
    if board:
        layout = next(name for name in board["files"] if "/" not in name and name.endswith(".kicad_pcb"))
        try:
            extracts[LAYOUT_FACTS] = layout_facts(board["files"][layout].decode("utf-8"), layout)
        except (FactsError, UnicodeDecodeError) as error:
            causes.append(str(error))
    if documents and METHOD in documents:
        try:
            extracts[METHOD_EXTRACT] = method_extract(documents[METHOD].decode("utf-8"), review)
        except Refused as error:
            causes += error.causes
        except UnicodeDecodeError:
            causes.append(f"the method {METHOD} is not UTF-8 text; give documents that hold it")
    if causes:
        raise Refused(causes)
    os.makedirs(out, exist_ok=True)
    try:
        written = review_seed.copy_commit(out, repo, board["sha"], args.design, documents_repo, args.documents_commit)
        if record is not None:
            with open(os.path.join(out, args.design, RECORD), "w", encoding="utf-8") as handle:
                handle.write(record)
        shutil.copytree(args.views, os.path.join(out, VIEWS))
        if review == LAYOUT or args.placement:
            shutil.copytree(args.placement, os.path.join(out, PLACEMENT))
        if review == LAYOUT:
            shutil.copyfile(args.check_report, os.path.join(out, CHECK_REPORT))
        for extract, text in extracts.items():
            with open(os.path.join(out, extract), "w", encoding="utf-8", newline="") as handle:
                handle.write(text)
        content = round_content(fields, values)
        with open(os.path.join(out, ROUND_FILE), "w", encoding="utf-8") as handle:
            handle.write(settled(content))
        review_seed.same_time(out)
    except BaseException:
        shutil.rmtree(out, ignore_errors=True)
        raise
    return {"result": "WRITTEN", "folder": out, "commit": board["sha"], "design": args.design,
            "design_files": written, "documents": sorted(documents), "extracts": sorted(extracts), "round": {key: content.get(key) for key in fields}}


def pair_of(entry: str) -> Dict[str, str]:
    """A listed item given as ITEM=reason; one that is not of the form gives an entry the field check refuses."""
    item, _, reason = entry.partition("=")
    return {"item": item.strip(), "reason": reason.strip()}


def held_folder(folder: str, causes: List[str]) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
    """The round file and the resolutions of a folder this command wrote; a cause is added when it cannot be added to."""
    try:
        return read_round(folder), read_resolutions(folder)
    except ReviewFolderProblem as error:
        causes.append(f"{folder} is not a review folder the command wrote and can add to: {error}")
        return {}, []


def record_resolution(folder: str, held: List[Dict[str, str]], entry: Dict[str, str]) -> None:
    """The resolutions file of the folder with one more entry, replaced whole so a failure leaves the earlier file. A view
    is recorded without a kind, as it always was."""
    os.makedirs(os.path.join(folder, ADDED_VIEWS), exist_ok=True)
    entries = [{key: value for key, value in one.items() if not (key == "kind" and value == "view")} for one in held + [entry]]
    scratch = os.path.join(folder, ADDED_VIEWS, RESOLUTIONS + ".part")
    with open(scratch, "w", encoding="utf-8") as handle:
        handle.write(settled({"tool": TOOL, "resolutions": entries}))
    os.replace(scratch, os.path.join(folder, ADDED_VIEWS, RESOLUTIONS))


def known_items(folder: str) -> Set[str]:
    """The items the folder's checklist holds, as far as the folder can tell: the catalogue's in its method extract, the
    plan's board items and, for a layout review's folder, the comparison with the plan, which a critical-routing folder
    lacks. Empty when the folder holds no catalogue item, so the checklist is not known."""
    try:
        with open(os.path.join(folder, METHOD_EXTRACT), encoding="utf-8") as handle:
            section = method_section(handle.read(), CATALOGUE_SECTION) or ""
        catalogue = set(re.findall(r"(?m)^#### ([A-Z]+-\d+)\. ", section))
        with open(os.path.join(folder, design_in(folder), "layout-plan.md"), encoding="utf-8") as handle:
            own = set(re.findall(r"(?m)^\|\s*(BOARD-[1-9][0-9]*)\s*\|", handle.read()))
        comparison = set() if is_critical_routing_fields(read_round(folder)["fields"]) else {COMPARISON_ITEM}
    except (OSError, UnicodeDecodeError, ReviewFolderProblem):
        return set()
    return (catalogue | own | comparison) if catalogue else set()


def add_document(args: argparse.Namespace) -> Dict[str, Any]:
    """A text file added to a folder this command wrote, with the cannot judge it resolves and where its figure comes from;
    or a refusal naming every cause. The file goes to the added-documents folder and the resolution to the resolutions
    file; the round file is not rewritten."""
    folder = os.path.abspath(args.add_document)
    causes: List[str] = []
    content, held = held_folder(folder, causes)
    document = os.path.abspath(args.document) if args.document else None
    if document is None or not os.path.isfile(document):
        causes.append(f"the document {args.document} does not exist; write the figure or passage into a text file, then give it")
    else:
        name = os.path.basename(document)
        if os.path.getsize(document) > DOCUMENT_LIMIT:
            causes.append(f"the document {name} is larger than {DOCUMENT_LIMIT // 1024} KiB; give only the figure or passage "
                          "the Why asks for")
        else:
            try:
                with open(document, "rb") as handle:
                    handle.read().decode("utf-8")
            except UnicodeDecodeError:
                causes.append(f"the document {name} is not UTF-8 text; give the figure or passage as a text file")
        if not PLAIN_NAME.fullmatch(name):
            causes.append(f"the document's file name {name!r} is not a plain name of letters, digits, dots, dashes and "
                          "underscores; rename it")
        elif os.path.lexists(os.path.join(folder, ADDED_DOCUMENTS, name)):
            causes.append(f"the folder already holds an added document named {name}; give the new document another name")
    for what, value in (("where the figure comes from (--source)", args.source),
                        ("the item whose cannot judge asked for the document (--cannot-judge-item)", args.cannot_judge_item),
                        ("the cannot judge's Why (--cannot-judge-why)", args.cannot_judge_why)):
        if not one_line(value):
            causes.append(f"{what} is missing or not one line of text")
    if content and one_line(args.cannot_judge_item):
        known = known_items(folder)
        if known and args.cannot_judge_item.strip() not in known:
            causes.append(f"the item {args.cannot_judge_item.strip()!r} is not on the folder's checklist; give the item's exact name")
    if causes:
        raise Refused(causes)
    name = os.path.basename(document)
    os.makedirs(os.path.join(folder, ADDED_DOCUMENTS), exist_ok=True)
    shutil.copyfile(document, os.path.join(folder, ADDED_DOCUMENTS, name))
    entry = {"kind": "document", "item": args.cannot_judge_item.strip(), "why": args.cannot_judge_why.strip(),
             "document": f"{ADDED_DOCUMENTS}/{name}", "source": args.source.strip()}
    record_resolution(folder, held, entry)
    return {"result": "ADDED", "folder": folder, "document": entry["document"], "item": entry["item"]}


def add_view(args: argparse.Namespace) -> Dict[str, Any]:
    """A view added to a folder this command wrote, with the cannot judge it resolves; or a refusal naming every cause. The
    view goes to the added-views folder and the resolution to the file there; the round file is not rewritten."""
    folder = os.path.abspath(args.add_view)
    causes: List[str] = []
    content, held = held_folder(folder, causes)
    if content and "views" not in content["fields"]:
        causes.append("the folder's round fields hold no views, so it has no Views field to add the view to")
    view = os.path.abspath(args.view) if args.view else None
    if view is None or not os.path.isfile(view):
        causes.append(f"the view {args.view} does not exist; render it, then give the file")
    elif not PLAIN_NAME.fullmatch(os.path.basename(view)) or os.path.basename(view) == RESOLUTIONS:
        causes.append(f"the view's file name {os.path.basename(view)!r} is not a plain name of letters, digits, dots, dashes "
                      "and underscores, or is the name of the resolutions file; rename it")
    elif os.path.lexists(os.path.join(folder, ADDED_VIEWS, os.path.basename(view))):
        causes.append(f"the folder already holds an added view named {os.path.basename(view)}; give the new view another name")
    command = args.view_command[0] if args.view_command and len(args.view_command) == 1 else None
    for what, value in (("the command the view was rendered with (one --view-command)", command),
                        ("the item whose cannot judge asked for the view (--cannot-judge-item)", args.cannot_judge_item),
                        ("the cannot judge's Why (--cannot-judge-why)", args.cannot_judge_why)):
        if not one_line(value):
            causes.append(f"{what} is missing or not one line of text")
    if causes:
        raise Refused(causes)
    name = os.path.basename(view)
    os.makedirs(os.path.join(folder, ADDED_VIEWS), exist_ok=True)
    shutil.copyfile(view, os.path.join(folder, ADDED_VIEWS, name))
    entry = {"item": args.cannot_judge_item.strip(), "why": args.cannot_judge_why.strip(), "view": f"{ADDED_VIEWS}/{name}",
             "command": command.strip()}
    record_resolution(folder, held, entry)
    return {"result": "ADDED", "folder": folder, "view": f"{ADDED_VIEWS}/{name}", "item": entry["item"]}


def finish(report: Dict[str, Any], as_json: bool, out_stream) -> int:
    status = {"WRITTEN": 0, "ADDED": 0, "REFUSED": 1, "CANNOT RUN": 2}[report["result"]]
    if as_json:
        json.dump(report, out_stream, indent=1)
        out_stream.write("\n")
        return status
    clean = board_check.clean
    for why in report.get("refusals", []):
        print(f"REFUSED | {clean(why)}", file=out_stream)
    if report["result"] == "WRITTEN":
        round_ = report["round"]
        print(f"FOLDER | {clean(report['folder'])} | commit {report['commit']} | design {clean(report['design'])}", file=out_stream)
        print("ROUND | " + " | ".join(f"{key} {clean(str(round_[key]))}" for key in round_), file=out_stream)
        print(f"RESULT | WRITTEN | {clean(report['folder'])}", file=out_stream)
    elif report["result"] == "ADDED":
        print(f"RESULT | ADDED | {clean(report.get('view') or report['document'])} | cannot judge of {clean(report['item'])}",
              file=out_stream)
    else:
        print(f"RESULT | {report['result']} | {clean(report['detail'])}", file=out_stream)
    return status


def main(argv: Optional[List[str]] = None, out=sys.stdout) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", help="the repository holding the board")
    parser.add_argument("--commit", help="the commit that holds the board, which is the commit the round judges")
    parser.add_argument("--design", help="the board's folder, by its path from the repository's root")
    parser.add_argument("--out", help="the review folder to write, new or empty, outside the repository")
    parser.add_argument("--views", help="the folder the views command rendered the views into")
    parser.add_argument("--placement", help="the folder the placement command rendered the placement view into")
    parser.add_argument("--check-report", help="the pre-order check's report on the board")
    parser.add_argument("--documents-repo", help="the repository the method and the hardware notes are taken from (default: this one)")
    parser.add_argument("--documents-commit", help="the commit of --documents-repo they are taken from (default: HEAD)")
    parser.add_argument("--review", choices=REVIEWS, default=LAYOUT,
                        help="the review the folder is written for: layout (the default) or critical-routing, whose pass has "
                             "the fields number, commit and views, no check report and an optional placement view")
    parser.add_argument("--round-fields", default=None,
                        help="the round's fields, from number, kind, commit, views and check (default: all five for the layout "
                             "review, the layout review's; number, commit and views for critical-routing)")
    parser.add_argument("--number", type=int, help="the round's number")
    parser.add_argument("--kind", help="the round's kind, full or narrow")
    parser.add_argument("--view-command", action="append", help="a command a view was rendered with, as run; repeat for each")
    parser.add_argument("--check-line", action="append", help="a line of the pre-order check's report to state in the round; repeat for each")
    parser.add_argument("--item", action="append", help="a narrow round's listed item as ITEM=reason; repeat for each")
    parser.add_argument("--region", action="append", help="a narrow round's changed region or net, named from the fix commits; repeat for each")
    parser.add_argument("--others", help="a narrow round's line saying why every other item is not judged")
    parser.add_argument("--add-view", help="a review folder this command wrote, to add a rendered view to")
    parser.add_argument("--view", help="the rendered view file to add")
    parser.add_argument("--add-document", help="a review folder this command wrote, to add a text file holding a figure to")
    parser.add_argument("--document", help="the text file to add, holding the figure or passage a cannot judge's Why asks for")
    parser.add_argument("--source", help="where the figure in the document comes from, as one line")
    parser.add_argument("--cannot-judge-item", help="the item whose cannot judge asked for the view or document")
    parser.add_argument("--cannot-judge-why", help="that cannot judge's Why")
    parser.add_argument("--json", action="store_true", help="print the report as one JSON document")
    args = parser.parse_args(argv)
    try:
        if args.add_view and args.add_document:
            parser.error("--add-view and --add-document are separate modes; give one")
        if args.add_view:
            report = add_view(args)
        elif args.add_document:
            report = add_document(args)
        else:
            required = ("repo", "commit", "design", "out", "views") + (
                ("placement", "check_report") if args.review == LAYOUT else ())
            missing = [f"--{name.replace('_', '-')}" for name in required if not getattr(args, name)]
            if missing:
                parser.error(f"{', '.join(missing)} {'is' if len(missing) == 1 else 'are'} required")
            fields = [name.strip() for name in (args.round_fields or ",".join(REVIEW_FIELDS[args.review])).split(",")
                      if name.strip()]
            report = write_folder(args, os.path.abspath(args.out), os.path.abspath(args.repo),
                                  os.path.abspath(args.documents_repo) if args.documents_repo else None, fields, args.review)
    except Refused as error:
        report = {"result": "REFUSED", "refusals": error.causes, "detail": "nothing was written"}
    except FileNotFoundError as error:
        if error.filename == "git":
            report = {"result": "CANNOT RUN", "refusals": [], "detail": "git is not on the search path; install it"}
        else:
            raise
    return finish(report, args.json, out)


if __name__ == "__main__":
    sys.exit(main())
