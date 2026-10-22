#!/usr/bin/env python3
"""The ordering step's production-files check as a caller of the review kit command (review_run.py --caller production_files).

Steps 4 and 5 of the method's ordering section give a verdict to every placed part and to every fabrication layer, the drill
file and the outline, before the board is paid for. Judged by unit, the units are the placed parts grouped by the footprint the
footprint drawings' index gives each designator, at most PARTS_PER_UNIT rows a unit (a larger group is split into consecutive
chunks in the placement file's order, and every row is in exactly one unit), and one unit for every fabrication layer, the drill
file and the outline. A placed part whose designator no drawing lists is in a unit of its own, named for its footprint in the
parts list (`no-drawing` when the parts list names none); its prompt says no drawing exists, and the merge refuses any verdict
for it but `cannot judge`, since the method makes it a part whose first pin or polarity cannot be judged, which blocks the order.

The verdicts are the ordering step's three: `matches`, `differs` and `cannot judge`. A `cannot judge` is not resolved within the
check: it stands and blocks the order as every row that is not `matches` does, so the caller has no add-view or add-document mode.
The kit keeps one verdict table per answer in which every unit item has a row, so a reviewer gives its rows in one table, Verdicts,
that holds the columns of both of the record's tables; the merge checks them for the kind of row they are and the render writes
the record's Parts and Layers tables from them. Replicas are merged by the kit with any row that is not `matches` standing: the
check names `differs` as its fail verdict, which the kit holds as it holds a fail, so a `differs` stands over a `cannot judge` and a
`matches` from another replica and no repair turn, `cannot judge` turn or rerun clears it; the verdict list below is ordered
`differs`, `matches`, `cannot judge`, so a `cannot judge` stands over a `matches`.

The review folder is the one production_review_folder.py writes. Its round file holds the commit judged, the tools, the commands
and the line saying what the assembler's preview is, which the merge has no model to write, so they are read when the declaration
is resolved and a folder whose round file lacks them, is malformed, holds a key the production-files mode does not own, or is another
review's is refused before any session starts. A reviewer is granted the read tools only, no retrieval. The pre-order round's three
replicas judge each unit: a full and a hunt framing on the mid-tier model, and the third on the small-tier model.

The checks receive the merged tables alone, so what the check judges is read once, when the declaration is resolved, and held for
them. They fail a placement-file row with no row or two, a row for a part or layer the check does not judge, a verdict other than
`cannot judge` for a part with no drawing, a row left without the cells its kind of row has (a cell that is only a dash or n/a is missing), a row that is not `matches` with no
Why, a `differs` with no finding, a finding of a row that matches and a finding that says nothing. The render writes
production-files-check.md as the method's step 6 gives it, naming every row that is not `matches` and saying it blocks the order.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence, Tuple

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)

import production_files  # noqa: E402
import production_seed  # noqa: E402
import review_folder  # noqa: E402
from review_kit import results  # noqa: E402
from review_kit.merge import Refused  # noqa: E402

ReviewFolderProblem = review_folder.ReviewFolderProblem
#: The most placement-file rows one unit holds, the item count of the layout catalogue's largest areas.
PARTS_PER_UNIT = 10
PRODUCTION = production_seed.PRODUCTION
PLACEMENT_FILE = f"{PRODUCTION}/{production_seed.PLACEMENT_FILE}"
PARTS_FILE = f"{PRODUCTION}/{production_seed.PARTS_FILE}"
FOOTPRINTS = f"{PRODUCTION}/{production_seed.FOOTPRINTS}"
LAYERS = f"{PRODUCTION}/{production_seed.LAYERS}"
GERBERS = f"{PRODUCTION}/{production_seed.GERBERS}"
RECORD = production_seed.RECORD
PREVIEW = review_folder.PREVIEW
VIEWS = review_folder.VIEWS
PLACEMENT = review_folder.PLACEMENT
NO_DRAWING = "no-drawing"
LAYERS_UNIT = "layers"
OUTLINE = "Edge.Cuts"
DRILL = production_files.DRILL
IMAGES = (".png", ".jpg", ".jpeg")
#: The views of the design a layer is compared with, and the views a part's orientation is compared with, by file-name prefix.
LAYER_VIEWS = ("layer-",)
ASSEMBLY_VIEWS = ("assembly-", "3d-")

MATCHES, DIFFERS, CANNOT_JUDGE = "matches", "differs", "cannot judge"
#: The ordering step's three verdicts, in the order the merge reads them: the kit takes the fail verdict (`differs`) first, then a
#: `cannot judge`, then the verdict earliest in this list.
VERDICTS = (DIFFERS, MATCHES, CANNOT_JUDGE)
PART_COLUMNS = ["Position (file / preview)", "Rotation (file / preview)", "Polarity or first pin (file / preview)",
                "Catalogue part (record / parts list)"]
LAYER_COLUMNS = ["File", "Compared with"]
VERDICT_TABLE = ["Item"] + PART_COLUMNS + LAYER_COLUMNS + ["Verdict", "Why"]
PARTS_TABLE = ["Part"] + PART_COLUMNS + ["Verdict", "Why"]
LAYERS_TABLE = ["Layer"] + LAYER_COLUMNS + ["Verdict", "Why"]
FINDING_TABLE = ["Finding", "Item", "What and where"]
RECORD_FINDING_TABLE = FINDING_TABLE + ["Closed by"]
CITATION = re.compile(r"(?<![\w.])[Ff]inding (?P<number>\d+)\b")
#: The one name the render writes.
RENDERED = re.compile(r"production-files-check\.md")
RENDERED_NAME = "production-files-check.md"

#: The mid-tier and small-tier models the replicas run on, full model ids. Each model has a shared context of its own.
MID_MODEL = "claude-sonnet-5-5"
SMALL_MODEL = "claude-haiku-5-5"

#: Plain data the kit reads: the variants a unit's replicas take in turn (the prompt as declared and the terse hunt for failures
#: with the items and views the other way round, both on the mid-tier model, and the prompt as declared on the small-tier model) and
#: the replicas by stakes. The check is the last before payment, so its units carry high stakes, the pre-order round's three.
replica_policy = {
    "variants": [{"id": "full", "model": MID_MODEL},
                 {"id": "hunt", "item_order": "reversed", "view_order": "reversed", "terse": True, "model": MID_MODEL},
                 {"id": "small", "model": SMALL_MODEL}],
    "replicas": {"low": 1, "normal": 2, "high": 3},
}
STAKES = "high"
#: The verdict the check holds as the kit holds a fail: a `differs` stands over a `cannot judge` and over a `matches` when replicas merge, and no repair turn, cannot-judge turn or rerun clears it.
fail_verdict = DIFFERS
#: The most reviewers at once: the layout caller's, the largest number the live runs ran with no call refused for a rate limit.
bound = 30
#: The check's time target in seconds, so the planner sizes groups well clear of the bound.
WALL_SECONDS = 350

#: What the checks hold of the check they were resolved for: the parts and layers it judges, those without a drawing, and each
#: part's unit.
ROUND: Dict[str, Any] = {}


# --- The folder ---------------------------------------------------------------------------------


def read_json(review: str, path: str, what: str) -> Dict[str, Any]:
    try:
        with open(os.path.join(review, path), encoding="utf-8") as handle:
            content = json.load(handle)
    except (OSError, ValueError, RecursionError) as error:
        raise ReviewFolderProblem(f"the review folder {review} holds no readable {what} {path} ({error}); write the folder with "
                                  "the folder command")
    if not isinstance(content, dict) or not isinstance(content.get("images"), list):
        raise ReviewFolderProblem(f"the {what} {path} in the review folder {review} lists no images; draw it again with the "
                                  "ordering step's second step")
    return content


def production_round(review: str) -> Dict[str, Any]:
    """The check's own fields from the round file, which must be the production-files check's and no other review's."""
    round_ = review_folder.read_round(review)
    if not review_folder.is_production_fields(round_["fields"]):
        raise ReviewFolderProblem(f"the round file in the review folder {review} has the fields {', '.join(round_['fields'])}, "
                                  f"not the production-files check's {', '.join(review_folder.PRODUCTION_FIELDS)}; write the "
                                  "folder with the production-files folder command")
    return round_


def placement_rows(review: str) -> List[List[str]]:
    try:
        return production_files.read_placement_file(os.path.join(review, PLACEMENT_FILE))
    except production_files.Refused as error:
        raise ReviewFolderProblem(f"{error}; write the folder with the production-files folder command")


def parts_footprints(review: str) -> Dict[str, str]:
    """The footprint name the parts list gives each designator it lists."""
    path = os.path.join(review, PARTS_FILE)
    try:
        with open(path, encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            names = reader.fieldnames or []
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        raise ReviewFolderProblem(f"the parts list {PARTS_FILE} in the review folder {review} cannot be read ({error}); write "
                                  "the folder with the production-files folder command")
    if "Designator" not in names or "Footprint" not in names:
        raise ReviewFolderProblem(f"the parts list {PARTS_FILE} in the review folder {review} has the columns {', '.join(names)}, "
                                  "which lack Designator or Footprint; export it again with the ordering step's first step")
    found: Dict[str, str] = {}
    for row in rows:
        for designator in re.split(r"[,\s]+", str(row.get("Designator") or "").strip()):
            if designator and str(row.get("Footprint") or "").strip():
                found.setdefault(designator.casefold(), str(row["Footprint"]).strip())
    return found


def drawings(review: str) -> List[Dict[str, Any]]:
    """The footprint drawings the index lists, each with its file, footprint and the designators that carry it; a drawing whose
    file is missing, or a designator two drawings carry, is a refusal."""
    index = read_json(review, f"{FOOTPRINTS}/index.json", "footprint drawings index")
    found, carried = [], {}
    for entry in index["images"]:
        used = entry.get("used_by") if isinstance(entry, dict) else None
        if (not isinstance(entry, dict) or not isinstance(entry.get("file"), str) or not isinstance(entry.get("footprint"), str)
                or not isinstance(used, list) or not all(isinstance(name, str) for name in used)):
            raise ReviewFolderProblem(f"the footprint drawings index {FOOTPRINTS}/index.json in the review folder {review} lists "
                                      f"{entry!r:.100}, not a drawing with its file, footprint and designators; draw it again "
                                      "with the ordering step's second step")
        if not os.path.isfile(os.path.join(review, FOOTPRINTS, entry["file"])):
            raise ReviewFolderProblem(f"the footprint drawings index lists {entry['file']}, which the review folder {review} does "
                                      f"not hold in {FOOTPRINTS}/; write the folder with the production-files folder command")
        for name in used:
            if name.casefold() in carried and carried[name.casefold()] != entry["file"]:
                raise ReviewFolderProblem(f"the footprint drawings index lists {name} under two drawings, {carried[name.casefold()]} and "
                                          f"{entry['file']}; draw it again with the ordering step's second step")
            carried[name.casefold()] = entry["file"]
        found.append({"file": entry["file"], "footprint": entry["footprint"], "used_by": list(used)})
    return found


def layer_images(review: str) -> List[Dict[str, str]]:
    """The layer images the index lists in its order, each with its layer's name and file; the drill file and the outline must
    be among them, a layer twice (compared without case), an image the folder lacks or a Gerber or drill file in the fabrication
    folder that no entry names as its source is a refusal."""
    index = read_json(review, f"{LAYERS}/index.json", "layer images index")
    found, seen = [], set()
    for entry in index["images"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("file"), str) or not isinstance(entry.get("layer"), str):
            raise ReviewFolderProblem(f"the layer images index {LAYERS}/index.json in the review folder {review} lists {entry!r:.100}, "
                                      "not an image with its file and layer; draw it again with the ordering step's second step")
        if entry["layer"].casefold() in seen:
            raise ReviewFolderProblem(f"the layer images index lists the layer {entry['layer']} twice, so the check cannot give it "
                                      "one row; draw the layers again with the ordering step's second step")
        seen.add(entry["layer"].casefold())
        if not os.path.isfile(os.path.join(review, LAYERS, entry["file"])):
            raise ReviewFolderProblem(f"the layer images index lists {entry['file']}, which the review folder {review} does not "
                                      f"hold in {LAYERS}/; write the folder with the production-files folder command")
        found.append({"layer": entry["layer"], "file": entry["file"]})
    for needed, what in ((DRILL, "the drill file"), (OUTLINE, "the outline")):
        if needed.casefold() not in seen:
            raise ReviewFolderProblem(f"the layer images index lists no image of {what} ({needed}), so the check would not judge "
                                      "it; a layer the render lists no image for is not rendered and blocks the order, so draw the "
                                      "layers again with the ordering step's second step")
    unlisted = review_folder.unlisted_fabrication_files(os.path.join(review, GERBERS), index["images"])
    if unlisted:
        raise ReviewFolderProblem(f"the review folder {review} holds {GERBERS}/{unlisted[0]}"
                                  + (f" and {len(unlisted) - 1} more" if len(unlisted) > 1 else "")
                                  + f", which the layer images index lists as no image's source, so no unit would judge it and no "
                                  "row could name it; draw the layers again with the ordering step's second step")
    return found


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "x"


def part_units(review: str) -> Dict[str, Dict[str, Any]]:
    """The units of the placed parts, in the order they run: for each footprint in the order its first row stands in the
    placement file, its rows in that file's order in chunks of at most PARTS_PER_UNIT. A part no drawing lists is grouped
    by the footprint name of the parts list, or NO_DRAWING."""
    rows = placement_rows(review)
    carried = {name.casefold(): drawing for drawing in drawings(review) for name in drawing["used_by"]}
    named = parts_footprints(review)
    groups: Dict[Tuple[bool, str], Dict[str, Any]] = {}
    for row in rows:
        drawing = carried.get(row[0].casefold())
        key = (True, drawing["file"]) if drawing else (False, named.get(row[0].casefold(), NO_DRAWING))
        group = groups.setdefault(key, {"drawing": drawing, "footprint": drawing["footprint"] if drawing else key[1], "rows": []})
        group["rows"].append(row)
    units: Dict[str, Dict[str, Any]] = {}
    for number, group in enumerate(groups.values(), 1):
        chunks = [group["rows"][at:at + PARTS_PER_UNIT] for at in range(0, len(group["rows"]), PARTS_PER_UNIT)]
        prefix = ("fp" if group["drawing"] else "nodrawing") + f"{number}-{slug(group['footprint'])}"
        for chunk, rows_ in enumerate(chunks, 1):
            unit = prefix if len(chunks) == 1 else f"{prefix}-{chunk}"
            units[unit] = {"drawing": group["drawing"], "footprint": group["footprint"], "rows": rows_}
    return units


def design_record(review: str) -> str:
    """The folder's one parts specification record, by its path from the review folder's root."""
    found = []
    for directory, _, files in os.walk(review):
        found += [os.path.relpath(os.path.join(directory, name), review) for name in files if name.casefold() == RECORD.casefold()]
    if len(found) != 1:
        raise ReviewFolderProblem(f"the review folder {review} holds {len(found)} files named {RECORD}; it holds the one record of "
                                  "the design under review, so write it with the production-files folder command")
    return found[0].replace(os.sep, "/")


def images_in(review: str, folder: str, prefixes: Sequence[str] = ("",)) -> List[str]:
    path = os.path.join(review, folder)
    if not os.path.isdir(path):
        return []
    return sorted(f"{folder}/{name}" for name in os.listdir(path)
                  if name.casefold().endswith(IMAGES) and name.startswith(tuple(prefixes)) and os.path.isfile(os.path.join(path, name)))


def shared_documents(review: str, record: str, files: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    """The artefacts of the shared context by name: the production text files, the record, the round file and the indexes (a
    file the folder command always writes and the folder lacks is named as missing) and every image the units use."""
    found: Dict[str, Dict[str, Any]] = {}
    for path in (PLACEMENT_FILE, PARTS_FILE, record, review_folder.ROUND_FILE, f"{LAYERS}/index.txt", f"{FOOTPRINTS}/index.txt",
                 f"{VIEWS}/index.txt", f"{PLACEMENT}/index.txt"):
        if not os.path.isfile(os.path.join(review, path)):
            raise ReviewFolderProblem(f"the review folder {review} holds no {path}, which the shared context holds; write the "
                                      "folder with the production-files folder command")
        found[path] = {"kind": "text", "source": path}
    for path in files:
        found[path] = {"kind": "image", "source": path}
    return found


# --- The declaration ----------------------------------------------------------------------------

PREFACE = """You are one reviewer of the production-files check of a printed circuit board, steps 4 and 5 of the Ordering section of \
docs/board-design-method.md, made before the board is paid for. You did not design the board, and you have no notes from whoever \
did. Work from the shared context above this message and the files in this folder. The folder holds: the placement file \
{placement} and the parts list {parts}; the design's parts specification record {record}; the Gerber and drill files in \
{gerbers}/; the image of every fabrication layer and of the drill file in {layers}/, whose index.txt lists every image and the \
frame all of them share; the drawing of every footprint at rotation 0 in {footprints}/, whose index.txt lists every drawing and \
gives the rule for reading a placement file's rotation against it; the design's own rendered views in {views}/ and its placement \
view in {placement_view}/, each with an index.txt of its images and their captions; the assembler's preview, saved as supplied, \
in {preview}/; and round.json, which holds the commit judged, the tools, the commands and a line saying what the preview is. You \
can read and search the folder; you cannot run a command, upload a file or write anything, and the preview was obtained outside \
this check. Open every image you rely on, and read board coordinates from the captions and the indexes.

The verdict of every row is one of `matches`, `differs` or `cannot judge`. A row is `matches` only when none of what the step looks \
for is found. A row is `differs` when something is wrong; its Why is `finding <n>`, the number of the finding you raise for it in \
your Findings table. A row is `cannot judge` when the judgement needs something that is not in the folder; its Why says what it needs. \
A `cannot judge` is not resolved within this check, and every row that is not `matches` blocks the order."""

PARTS_BLOCK = """Your unit is {count} placed part{plural} of the footprint {footprint}, whose drawing at rotation 0 is \
{drawing}. Their rows in {placement}, as Designator, Mid X, Mid Y, Layer, Rotation:
{rows}

For each part, as step 4 gives them, judge: the position (the file's point lies on the part's own body or pads as the design \
draws them, and the preview shows the part there); the rotation (turn the footprint's drawing by the file's angle by the rule in \
{footprints}/index.txt, and the part's first pin, key or longer side lies where the design's assembly view has it and the preview \
shows it); the polarity or first-pin orientation (the mark in the preview and the drawing turned by the file's angle lie where the \
design's assembly view and its silkscreen put it; a part with no polarity states `none`); and the catalogue part (the parts list's \
row for the position carries the catalogue number, value and footprint the parts specification record maps the position to; the \
position is in the parts list and in the record). Compare with the preview in {preview}/ and the design's own views in {views}/ \
and {placement_view}/."""

NO_DRAWING_BLOCK = """Your unit is {count} placed part{plural} of the footprint {footprint}, which has no drawing in {footprints}/. \
A footprint of a placed part with no drawing is a part whose first pin or polarity cannot be judged, and blocks the order (step 2). \
Give every one of your rows the verdict `cannot judge` and no other, with Why `no drawing of the footprint {footprint}`, and fill \
the position, rotation and catalogue part cells from the placement file, the preview and the parts list as far as they can be read. \
Their rows in {placement}, as Designator, Mid X, Mid Y, Layer, Rotation:
{rows}"""

LAYERS_BLOCK = """Your unit is every fabrication layer, the drill file and the outline. Their images in {layers}/ are:
{images}

Open each image and the design's own view of the same layer in {views}/ (the layer-<layer> views, tile by tile where it is tiled; \
for the drill file, the holes of the copper views), and state what was compared in Compared with. As step 5 gives them, look for: \
missing content (no content on the exported layer where the design has copper, mask openings, legend or holes); shifted content \
(content at another place than in the design's view, read by the frame's coordinates against the view's captions, with the sign of \
Y the index states); and mirrored content (the design's reflected, legend text that reads backward, a pattern turned over). A \
layer matches only when none of the three is found. File is the Gerber or drill file the image was read from, as the index names it."""

OUTPUT = """Verdicts has one row for each item of your unit, with the columns {verdicts}. Item is the item's name as listed above. For \
a placed part, fill the four columns {part_columns} and write `—` in {layer_columns}; for a layer, fill {layer_columns} and write \
`—` in the four part columns. Never write `—` or n/a in a column of your own row's kind: a part with no polarity states `none`. Verdict is one of matches, differs or cannot judge.

Findings has the columns {findings}. Number your findings 1, 2, 3 in the order you raise them, in Finding, as whole numbers. Raise \
at least one finding for each row you give `differs`, naming the row in Item, and none for a row that matches; What and where says \
what is wrong and where, as the placement file's designator or the layer's board coordinates."""

UNIT_TEMPLATE = """{preface}

Your unit: {unit}

{scope}
{items}

{block}

{output}

{schema}"""

SCHEMA = {
    "tables": [
        {"name": "Verdicts", "columns": VERDICT_TABLE, "key": "Item", "verdict_column": "Verdict", "verdicts": list(VERDICTS)},
        {"name": "Findings", "columns": FINDING_TABLE, "key": "Item", "numeric": ["Finding"]},
    ],
    "findings": {"table": "Findings", "number": "Finding", "citations": [["Verdicts", "Why"]], "citation": CITATION.pattern},
}


def row_lines(rows: Sequence[Sequence[str]]) -> str:
    return "\n".join("- " + ", ".join(row) for row in rows)


def unit_values(review: str, record: str, parts: Dict[str, Dict[str, Any]], layers: Sequence[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    preface = PREFACE.format(placement=PLACEMENT_FILE, parts=PARTS_FILE, record=record, gerbers=GERBERS, layers=LAYERS,
                             footprints=FOOTPRINTS, views=VIEWS, placement_view=PLACEMENT, preview=PREVIEW)
    scope = ("Judge each of these items, in the order given, and give one verdict row to each of them and to no other item:")
    output = OUTPUT.format(verdicts=", ".join(VERDICT_TABLE), part_columns=", ".join(PART_COLUMNS),
                           layer_columns=" and ".join(LAYER_COLUMNS), findings=", ".join(FINDING_TABLE))
    found: Dict[str, Dict[str, str]] = {}
    for unit, held in parts.items():
        count = len(held["rows"])
        common = {"count": count, "plural": "" if count == 1 else "s", "footprint": held["footprint"], "placement": PLACEMENT_FILE,
                  "rows": row_lines(held["rows"]), "footprints": FOOTPRINTS, "preview": PREVIEW, "views": VIEWS,
                  "placement_view": PLACEMENT}
        block = PARTS_BLOCK.format(drawing=f"{FOOTPRINTS}/{held['drawing']['file']}", **common) if held["drawing"] else \
            NO_DRAWING_BLOCK.format(**common)
        found[unit] = {"preface": preface, "scope": scope, "block": block, "output": output}
    images = "\n".join(f"- {entry['layer']}: {LAYERS}/{entry['file']}" for entry in layers)
    found[LAYERS_UNIT] = {"preface": preface, "scope": scope, "output": output,
                          "block": LAYERS_BLOCK.format(layers=LAYERS, views=VIEWS, images=images)}
    return found


def expected_tokens(listed: Sequence[str]) -> int:
    """The output a unit is expected to give: a verdict row for each item and a little over for findings."""
    return 200 + 260 * len(listed)


def build_declaration(review: str) -> Dict[str, Any]:
    round_ = production_round(review)
    record = design_record(review)
    parts = part_units(review)
    layers = layer_images(review)
    designators = [row[0] for held in parts.values() for row in held["rows"]]
    names = [entry["layer"] for entry in layers]
    clash = sorted({name for name in designators if name.casefold() in {layer.casefold() for layer in names}})
    if clash:
        raise ReviewFolderProblem(f"the placement file names a part {clash[0]}, which is also the name of a fabrication layer; the "
                                  "check gives each part and layer one row by name, so the two cannot share one")
    preview = images_in(review, PREVIEW)
    if not preview:
        raise ReviewFolderProblem(f"the review folder {review} holds no preview image (a PNG or JPEG in {PREVIEW}/), which the "
                                  "shared context holds; save the assembler's preview as images and write the folder again")
    layer_views = images_in(review, VIEWS, LAYER_VIEWS)
    if not layer_views:
        raise ReviewFolderProblem(f"the review folder {review} holds no layer view image (a layer-<layer> PNG or JPEG in {VIEWS}/), "
                                  "which each layer is compared with; render the design's views")
    orientation = images_in(review, PLACEMENT) + images_in(review, VIEWS, ASSEMBLY_VIEWS)
    if not orientation:
        raise ReviewFolderProblem(f"the review folder {review} holds no placement or assembly view image, which each part's "
                                  "orientation is compared with; render the design's views and placement view")
    unit_images = {unit: preview + orientation + [f"{FOOTPRINTS}/{held['drawing']['file']}"] if held["drawing"] else
                   preview + orientation for unit, held in parts.items()}
    unit_images[LAYERS_UNIT] = layer_views + [f"{LAYERS}/{entry['file']}" for entry in layers]
    everything = sorted({path for paths in unit_images.values() for path in paths})
    documents = shared_documents(review, record, everything)
    values = unit_values(review, record, parts, layers)
    unit_items = {unit: [row[0] for row in held["rows"]] for unit, held in parts.items()}
    unit_items[LAYERS_UNIT] = names
    text = [PLACEMENT_FILE, PARTS_FILE, record, review_folder.ROUND_FILE, f"{LAYERS}/index.txt", f"{FOOTPRINTS}/index.txt",
            f"{VIEWS}/index.txt", f"{PLACEMENT}/index.txt"]
    ROUND.clear()
    ROUND.update({"parts": designators, "layers": names, "units": unit_items,
                  "nodrawing": {row[0]: held["footprint"] for held in parts.values() if not held["drawing"] for row in held["rows"]},
                  "round": round_})
    declared = {unit: {"items": list(listed), "template": "unit", "needs": sorted(text + unit_images[unit]),
                       "stakes": STAKES, "expected_output_tokens": expected_tokens(listed), "values": values[unit]}
                for unit, listed in unit_items.items()}
    return {"artefacts": documents, "templates": {"unit": UNIT_TEMPLATE}, "units": declared, "schema": SCHEMA,
            "deny": ["designer-notes*", "session*"], "budget": {"wall_s": WALL_SECONDS}}


def declaration(review: str) -> Dict[str, Any]:
    """The declaration of the check in the review folder: its units, the shared context and the tables. The folder's round file
    and files are checked here, before any session starts, since the checks receive the merged tables alone."""
    try:
        return build_declaration(review)
    except ReviewFolderProblem as error:
        raise Refused([str(error)])


def checklist(review: str) -> List[str]:
    """The items in the order findings are numbered by: the placed parts in the placement file's order, then the layers in the
    layer images index's order."""
    try:
        production_round(review)
        return [row[0] for row in placement_rows(review)] + [entry["layer"] for entry in layer_images(review)]
    except ReviewFolderProblem as error:
        raise Refused([str(error)])


# --- The checks ---------------------------------------------------------------------------------


def blank(value: Any) -> bool:
    return not " ".join(str(value).split()).strip()


#: Words a reviewer writes for "not applicable"; the prompt makes the dash the marker of the other kind of row's columns, and a
#: part's four comparisons and a layer's file and comparison are never not applicable (a part with no polarity states `none`).
PLACEHOLDER_WORDS = frozenset({"n/a", "na", "not applicable", "nil", "tbd", "unknown"})


def placeholder(value: Any) -> bool:
    """True for a cell that is empty, holds no letter or digit (a dash, dots, a slash) or is a not-applicable word."""
    text = " ".join(str(value).split()).casefold()
    return not any(character.isalnum() for character in text) or text in PLACEHOLDER_WORDS


def cited(row: Dict[str, Any]) -> List[int]:
    return [int(match.group("number")) for match in CITATION.finditer(str(row["Why"]))]


def finding_problems(rows: Sequence[Dict[str, Any]], findings: Sequence[Dict[str, Any]]) -> List[str]:
    """Each row that differs needs a finding of its own, each finding a row that is not a match, and a row's Why cites only
    findings of its own item."""
    found = []
    by_number = {finding["Finding"]: finding for finding in findings}
    verdicts = {row["Item"]: row["Verdict"] for row in rows}
    for item in [row["Item"] for row in rows if row["Verdict"] == DIFFERS]:
        if not any(finding["Item"] == item for finding in findings):
            found.append(f"item {item} differs and no finding names it; a row that differs raises a finding naming the item and "
                         "what and where, so run its unit again with --rerun")
    for finding in findings:
        if verdicts.get(finding["Item"]) in (None, MATCHES):
            found.append(f"finding {finding['Finding']} names item {finding['Item']}, which "
                         + ("is no item of this check" if finding["Item"] not in verdicts else "matches")
                         + "; a finding belongs to a row that is not a match, so run the unit that raised it again with --rerun")
        if blank(finding["What and where"]):
            found.append(f"finding {finding['Finding']} says nothing under What and where, which the row's Why is written from; "
                         "run its unit again with --rerun")
    for row in rows:
        for number in cited(row):
            if number in by_number and by_number[number]["Item"] != row["Item"]:
                found.append(f"item {row['Item']}'s Why cites finding {number}, which names item {by_number[number]['Item']}; "
                             "a verdict cites only findings of its own item")
    return found


def checks(tables: Dict[str, Any]) -> List[str]:
    """What the merge refuses: a placement-file row with no verdict row or two, a verdict row for a part or layer the check does
    not judge, a verdict other than cannot judge for a part with no drawing, a row without the cells its kind of row has, a row
    that is not a match with no Why, a differs with no finding, a finding of a row that matches and an empty finding.
    A cell a row must carry is missing when it is blank or a placeholder: no letter or digit, or n/a and the like."""
    if not ROUND:
        return ["the production-files caller's checks ran before its declaration was resolved for a review folder, so the parts and "
                "layers the check judges are not known; resolve the declaration first"]
    rows = tables["Verdicts"]["rows"]
    expected = ROUND["parts"] + ROUND["layers"]
    counts = Counter(row["Item"] for row in rows)
    found = []
    for item in expected:
        what = "a placement-file row" if item in ROUND["parts"] else "a fabrication layer, the drill file or the outline"
        if counts[item] == 0:
            found.append(f"{item} is {what} and has no verdict row; every part of the placement file and every layer has exactly "
                         "one, so judge it in its unit and run that unit again with --rerun")
        elif counts[item] > 1:
            found.append(f"{item} has {counts[item]} verdict rows; every part of the placement file and every layer has exactly one")
    for item in counts:
        if item not in expected:
            found.append(f"a verdict row for {item}, which is no part of the placement file and no layer, drill file or outline of "
                         "this check; a verdict is accepted only for an item the check judges")
    for row in rows:
        item, verdict = row["Item"], row["Verdict"]
        if verdict not in VERDICTS:
            found.append(f"item {item} has the verdict {verdict!r}, outside matches, differs and cannot judge")
        if item in ROUND["nodrawing"] and verdict != CANNOT_JUDGE:
            found.append(f"part {item} has the footprint {ROUND['nodrawing'][item]}, which has no drawing, and the verdict "
                         f"{verdict}; a part with no drawing is a part whose first pin or polarity cannot be judged, so its only "
                         "verdict is cannot judge, which blocks the order")
        needed = PART_COLUMNS if item in ROUND["parts"] else LAYER_COLUMNS if item in ROUND["layers"] else []
        empty = [column for column in needed if placeholder(row[column])]
        if empty:
            found.append(f"{'part' if item in ROUND['parts'] else 'layer'} {item} leaves {', '.join(empty)} empty or as a "
                         "placeholder such as —; the record gives a part's four comparisons (a part with no polarity states "
                         "none) and a layer's file and what it was compared with, so run its unit again with --rerun")
        if verdict != MATCHES and blank(row["Why"]):
            found.append(f"item {item} is {verdict} with no Why; the row says what is wrong and where, or what it needs, so run "
                         "its unit again with --rerun")
    return found + finding_problems(rows, tables["Findings"]["rows"])


# --- The rendered record ------------------------------------------------------------------------


def one_line(value: Any) -> str:
    return " ".join(str(value).split())


def verdict_row(row: Dict[str, Any], findings: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """A verdict row as the record gives it. A row that differs has its Why written from its findings' What and where."""
    why = str(row["Why"])
    if row["Verdict"] == DIFFERS:
        by_number = {finding["Finding"]: str(finding["What and where"]).strip() for finding in findings
                     if finding["Item"] == row["Item"]}
        why = CITATION.sub(lambda match: by_number.get(int(match.group("number")), match.group(0)), why)
        left = [text for number, text in by_number.items() if number not in cited(row)]
        why = " ".join([why.strip()] + [f"Also: {text}" for text in left])
    return {**row, "Why": why}


def render(review: str, tables: Dict[str, Any]) -> Dict[str, str]:
    """The merged check as the method's step 6 gives it, written as production-files-check.md: the Board judged, Tools, Commands
    and Preview lines from the round file, the Parts table (a row for every placed part), the Layers table (a row for every layer,
    the drill file and the outline), the Findings table and, naming every row that is not a match, what blocks the order."""
    if not ROUND:
        raise Refused(["the production-files caller rendered before its declaration was resolved for a review folder; resolve "
                       "the declaration first"])
    try:
        round_ = production_round(review)
        order = {item: index for index, item in enumerate(checklist(review))}
    except ReviewFolderProblem as error:
        raise Refused([str(error)])
    findings = tables["Findings"]["rows"]
    rows = sorted((verdict_row(row, findings) for row in tables["Verdicts"]["rows"]), key=lambda row: order[row["Item"]])
    parts = [{"Part": row["Item"], **{column: row[column] for column in PART_COLUMNS + ["Verdict", "Why"]}}
             for row in rows if row["Item"] in ROUND["parts"]]
    layers = [{"Layer": row["Item"], **{column: row[column] for column in LAYER_COLUMNS + ["Verdict", "Why"]}}
              for row in rows if row["Item"] in ROUND["layers"]]
    text = [f"- **Board judged**: {round_['commit']}", f"- **Tools**: {one_line(round_['tools'])}", "- **Commands**:", "",
            "```", *round_["commands"], "```", "", f"- **Preview**: {one_line(round_['preview'])}", "", "### Parts", ""]
    text += results.table_lines(PARTS_TABLE, parts) + ["", "### Layers", ""]
    text += results.table_lines(LAYERS_TABLE, layers) + ["", "### Findings", ""]
    text += results.table_lines(RECORD_FINDING_TABLE, [{**finding, "Closed by": "open: blocks the order"} for finding in findings])
    text += ["", "### Blocking the order", ""]
    blocking = [row for row in rows if row["Verdict"] != MATCHES]
    if blocking:
        text += [f"- {'Part' if row['Item'] in ROUND['parts'] else 'Layer'} `{row['Item']}` is `{row['Verdict']}`: "
                 f"{one_line(row['Why'])} It blocks the order until the design is corrected and the files are exported again."
                 for row in blocking]
    else:
        text += ["- Nothing blocks the order: every part of the placement file and every layer, the drill file and the outline "
                 "matches."]
    return {RENDERED_NAME: "\n".join(text).rstrip("\n") + "\n"}
