#!/usr/bin/env python3
"""Turn a board's exported production files into what the method's ordering step reads.

KiCad's command-line tool exports the position file, the parts list, the Gerber
layers and the drill file, and the method's ordering step names those commands.
Three things it cannot do are done here:

    production_files.py placement --positions <KiCad position export, CSV> --out <placement file, CSV>
    production_files.py render --gerbers <folder of exported Gerber and drill files> --out <new or empty folder> [--resvg ...]
    production_files.py footprints --board <layout, .kicad_pcb> --out <new or empty folder> [--kicad-cli ...] [--resvg ...]

`placement` writes the assembler's placement file from the position export:
the columns the manufacturer's record gives for it, Designator, Mid X, Mid Y,
Layer and Rotation, in millimetres and degrees counter-clockwise. The export's
coordinates agree with the Gerber files it was exported with, so they are kept as
they are; only the columns, the side's name and the rotation's range change. How
the assembler reads the file is what its own preview shows, and the method's
ordering step checks that.

`render` draws every Gerber layer and the drill file from the exported files
themselves, each into a PNG of its own in one common frame, so a layer that is
shifted, mirrored or empty shows against the others and against the design's
own views. KiCad's command-line tool reads no Gerber file, so the drawing is
gerbonara's, at the exact version it names, turned into an SVG and rasterised
with resvg. The folder also holds an index of every image, as text and as JSON.

`footprints` draws every distinct footprint the board carries at rotation 0, the
way its library draws it, with its pad numbers and its first-pin and polarity
marking, so the placement file's rotation of a part can be read against the
marking it turns. The drawing is made from the footprint the board holds: a
footprint placed turned or on the bottom side is turned or flipped back first.
KiCad's command-line tool draws it into an SVG, rasterised with resvg, and the
folder also holds an index of every image, as text and as JSON, that gives the
rule for reading a rotation against a drawing.

Each step is reported on one line, a RESULT line comes last, and the exit status
is 0 when the output is written, 1 when the command is refused, and 2 when it
cannot run, for example because gerbonara, KiCad's command-line tool or resvg is missing.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import warnings
from typing import Dict, List, Optional, Tuple

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import board_views  # noqa: E402
import sexpr  # noqa: E402

#: The one gerbonara version the drawings are made with.
GERBONARA = "1.6.3"
INSTALL = (f"Install gerbonara {GERBONARA} (an Apache-licensed Python library) into a virtual environment, "
           f"`python3 -m venv <folder>` then `<folder>/bin/python -m pip install gerbonara=={GERBONARA}`, and run this "
           "command with that environment's Python (set GERBONARA_PYTHON=<folder>/bin/python for the task commands).")
#: The columns of KiCad's position export, as `kicad-cli pcb export pos --format csv` writes them.
POSITION_COLUMNS = ["Ref", "Val", "Package", "PosX", "PosY", "Rot", "Side"]
#: The assembler's placement file's columns, as the manufacturer's record gives them.
PLACEMENT_COLUMNS = ["Designator", "Mid X", "Mid Y", "Layer", "Rotation"]
SIDES = {"top": "Top", "bottom": "Bottom"}
PIXELS_PER_MM = 16
#: Space round the drawn layers, in millimetres.
MARGIN_MM = 1.0
#: KiCad's name for each layer gerbonara names by side and use.
USES = {("top", "copper"): "F.Cu", ("bottom", "copper"): "B.Cu", ("top", "mask"): "F.Mask", ("bottom", "mask"): "B.Mask",
        ("top", "silk"): "F.SilkS", ("bottom", "silk"): "B.SilkS", ("top", "paste"): "F.Paste", ("bottom", "paste"): "B.Paste",
        ("mechanical", "outline"): "Edge.Cuts"}
DRILL = "drill"
#: The order the layers are drawn and listed in, whatever order the export is discovered in: the sides' layers, the inner copper, the outline, then the drill files.
SIDE_ORDER = ["F.Cu", "F.Mask", "F.SilkS", "F.Paste", "B.Cu", "B.Mask", "B.SilkS", "B.Paste"]


class Refused(Exception):
    """The command will not go on, for the reason given."""


def number(text: str, what: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise Refused(f"{what} is {text!r}, not a number") from None
    if value != value or value in (float("inf"), float("-inf")):
        raise Refused(f"{what} is {text!r}, not a finite number")
    return value


def figure(value: float) -> str:
    """A coordinate or an angle as the placement file writes it: four decimals at most, no trailing zeros, no negative zero."""
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def read_positions(path: str) -> List[Dict[str, str]]:
    try:
        with open(path, encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
    except OSError as error:
        raise Refused(f"the position export {path} cannot be read ({error})") from None
    if not rows or not any(cell.strip() for row in rows for cell in row):
        raise Refused(f"the position export {path} is empty")
    if rows[0] != POSITION_COLUMNS:
        raise Refused(f"the position export {path} has the columns {','.join(rows[0])}, not KiCad's "
                      f"{','.join(POSITION_COLUMNS)}")
    found = []
    for line, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue
        if len(row) != len(POSITION_COLUMNS):
            raise Refused(f"line {line} of {path} has {len(row)} columns, not {len(POSITION_COLUMNS)}")
        found.append(dict(zip(POSITION_COLUMNS, row)))
    if not found:
        raise Refused(f"the position export {path} lists no part")
    return found


def placement_rows(positions: List[Dict[str, str]]) -> List[List[str]]:
    """The placement file's rows, in the export's order, from the position export's rows."""
    seen = set()
    rows = []
    for row in positions:
        reference = row["Ref"].strip()
        if not reference:
            raise Refused("a row of the position export names no designator")
        if reference.lower() in seen:
            raise Refused(f"the position export lists {reference} twice")
        seen.add(reference.lower())
        side = row["Side"].strip().lower()
        if side not in SIDES:
            raise Refused(f"{reference} is on the side {row['Side']!r}, which is neither top nor bottom")
        x = number(row["PosX"], f"{reference}'s PosX")
        y = number(row["PosY"], f"{reference}'s PosY")
        angle = number(row["Rot"], f"{reference}'s Rot") % 360
        rows.append([reference, figure(x), figure(y), SIDES[side], figure(angle)])
    return rows


def read_placement_file(path: str) -> List[List[str]]:
    """The rows of a placement file in the assembler's columns, as the conversion writes it, in the file's order: a Refused
    naming the file when it cannot be read as UTF-8 text, lacks the columns, holds no part, holds a row of another width, a
    blank designator or a designator twice (without regard to case)."""
    try:
        with open(path, encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        raise Refused(f"the placement file {path} cannot be read ({error})") from None
    if not rows or rows[0] != PLACEMENT_COLUMNS:
        raise Refused(f"the placement file {path} has the columns {','.join(rows[0]) if rows else 'none'}, not "
                      f"{','.join(PLACEMENT_COLUMNS)}")
    found, seen = [], set()
    for line, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue
        if len(row) != len(PLACEMENT_COLUMNS):
            raise Refused(f"line {line} of the placement file {path} has {len(row)} columns, not {len(PLACEMENT_COLUMNS)}")
        if not row[0].strip():
            raise Refused(f"line {line} of the placement file {path} names no designator")
        if row[0].strip().casefold() in seen:
            raise Refused(f"the placement file {path} lists {row[0].strip()} twice")
        seen.add(row[0].strip().casefold())
        found.append([cell.strip() for cell in row])
    if not found:
        raise Refused(f"the placement file {path} lists no part")
    return found


def write_placement(path: str, rows: List[List[str]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        writer.writerow(PLACEMENT_COLUMNS)
        writer.writerows(rows)


def placement(positions: str, out: str, stream=None) -> int:
    stream = stream or sys.stdout
    if os.path.isdir(out):
        print(f"REFUSED | {out} is a folder", file=stream)
        print("RESULT | REFUSED | nothing was written", file=stream)
        return 1
    if os.path.exists(out):
        print(f"REFUSED | {out} already exists; give a new file name", file=stream)
        print("RESULT | REFUSED | nothing was written", file=stream)
        return 1
    try:
        rows = placement_rows(read_positions(positions))
    except Refused as error:
        print(f"REFUSED | {board_check.clean(str(error))}", file=stream)
        print("RESULT | REFUSED | nothing was written", file=stream)
        return 1
    write_placement(out, rows)
    print(f"PARTS | {len(rows)} parts | {sum(row[3] == 'Bottom' for row in rows)} on the bottom side", file=stream)
    print(f"RESULT | WRITTEN | {out}", file=stream)
    return 0


# --- Drawing the layers -----------------------------------------------------------------------


def gerbonara_version() -> Optional[str]:
    try:
        import gerbonara
    except ImportError:
        return None
    return getattr(gerbonara, "__version__", None)


def require_gerbonara() -> None:
    found = gerbonara_version()
    if found is None:
        raise board_check.CannotRun(f"gerbonara could not be imported by {sys.executable}. {INSTALL}")
    if found != GERBONARA:
        raise board_check.CannotRun(f"gerbonara {found} is installed for {sys.executable}, not the version {GERBONARA} "
                                    f"the drawings are made with. {INSTALL}")


def layer_name(key: Tuple[str, str]) -> str:
    """KiCad's name for the layer gerbonara keys by side and use, so an image is named as the design's own view of it."""
    inner = re.match(r"inner_(\d+)$", key[0])
    if inner and key[1] == "copper":
        return f"In{inner.group(1)}.Cu"
    return USES.get(key, "-".join(key))


def layer_rank(name: str) -> Tuple[int, int, str]:
    """Where a layer of this name stands in the listing: the sides' layers, the inner copper in ascending layer number, the outline, the drill files, then any other layer by name."""
    if name in SIDE_ORDER:
        return (0, SIDE_ORDER.index(name), "")
    inner = re.match(r"In(\d+)\.Cu$", name)
    if inner:
        return (1, int(inner.group(1)), "")
    if name == "Edge.Cuts":
        return (2, 0, "")
    if name == DRILL:
        return (3, 0, "")
    return (4, 0, name)


def in_listing_order(drawn: list) -> list:
    """The (name, layer, source) entries in the order the images and both forms of the index list them; entries of one rank keep to their source's file name, so the order does not depend on how the export was discovered."""
    return sorted(drawn, key=lambda item: (layer_rank(item[0]), os.path.basename(str(item[2] or ""))))


def caption(svg: str, text: str) -> str:
    """`text` drawn in the top left corner of an SVG gerbonara wrote, in the units of its view box."""
    box = re.search(r'viewBox="([-\d.e+]+) ([-\d.e+]+) ([-\d.e+]+) ([-\d.e+]+)"', svg)
    x, y, size = float(box.group(1)), float(box.group(2)), 1.4
    label = (f'<text x="{x + 0.6:g}" y="{y + 0.6 + size:g}" font-size="{size}" font-family="monospace" fill="#c00000" '
             f'stroke="white" stroke-width="0.25" paint-order="stroke">{board_views.escape(text)}</text>')
    return svg[:svg.rindex("</svg>")] + label + "\n</svg>\n"


def inside(path: str, folder: str) -> bool:
    path, folder = os.path.realpath(path), os.path.realpath(folder)
    return os.path.commonpath([path, folder]) == folder


def render(gerbers: str, out: str, resvg: str, stream=None) -> int:
    stream = stream or sys.stdout
    problems = []
    if not os.path.isdir(gerbers):
        problems.append(f"{gerbers} is not a folder")
    if os.path.isfile(out):
        problems.append(f"{out} is a file")
    elif os.path.isdir(out) and os.listdir(out):
        problems.append(f"{out} already holds files; give a new or empty folder")
    if os.path.isdir(gerbers) and inside(out, gerbers):
        problems.append(f"{out} is inside the Gerber folder {gerbers}")
    if problems:
        for why in problems:
            print(f"REFUSED | {board_check.clean(why)}", file=stream)
        print("RESULT | REFUSED | nothing was written", file=stream)
        return 1
    try:
        require_gerbonara()
        board_views.require_resvg(resvg)
    except board_check.CannotRun as error:
        print(f"CANNOT RUN | {board_check.clean(str(error))}", file=sys.stderr)
        return 2
    if not any(os.path.isfile(os.path.join(gerbers, name)) for name in os.listdir(gerbers)):
        print(f"REFUSED | {board_check.clean(gerbers)} holds no Gerber or drill file", file=stream)
        print("RESULT | REFUSED | nothing was written", file=stream)
        return 1
    from gerbonara import LayerStack
    from gerbonara.utils import MM

    with warnings.catch_warnings(record=True) as warned:
        warnings.simplefilter("always")
        try:
            stack = LayerStack.open(gerbers)
        except Exception as error:  # gerbonara raises its own and several standard errors for an unreadable file
            print(f"REFUSED | the files in {gerbers} cannot be read as Gerber and drill files ({board_check.clean(str(error))})",
                  file=stream)
            print("RESULT | REFUSED | nothing was written", file=stream)
            return 1
        layers = [(layer_name(key), key, layer) for key, layer in stack.graphic_layers.items()]
        drills = list(stack.drill_layers)
    if not layers and not drills:
        print(f"REFUSED | {gerbers} holds no Gerber or drill file", file=stream)
        print("RESULT | REFUSED | nothing was written", file=stream)
        return 1
    frame = None
    for _, _, layer in layers + [(DRILL, None, drill) for drill in drills]:
        box = layer.bounding_box(MM, None)
        if box is None:
            continue
        (x0, y0), (x1, y1) = box
        frame = (x0, y0, x1, y1) if frame is None else (min(frame[0], x0), min(frame[1], y0), max(frame[2], x1), max(frame[3], y1))
    if frame is None:
        print(f"REFUSED | every file in {gerbers} is empty", file=stream)
        print("RESULT | REFUSED | nothing was written", file=stream)
        return 1
    bounds = ((frame[0] - MARGIN_MM, frame[1] - MARGIN_MM), (frame[2] + MARGIN_MM, frame[3] + MARGIN_MM))
    width_mm, height_mm = bounds[1][0] - bounds[0][0], bounds[1][1] - bounds[0][1]
    width_px = int(round(width_mm * PIXELS_PER_MM))
    os.makedirs(out, exist_ok=True)
    images = []
    drawn = [(name, layer, layer.original_path if hasattr(layer, "original_path") else "") for name, _, layer in layers]
    drawn += [(DRILL, drill, getattr(drill, "original_path", "")) for drill in drills]
    drawn = in_listing_order(drawn)
    with tempfile.TemporaryDirectory(prefix="production-render-") as scratch:
        for name, layer, source in drawn:
            file = f"layer-{name}.png"
            svg = layer.to_svg(force_bounds=bounds, margin=0, fg="black", bg="white")
            text = caption(str(svg), f"{name}  {os.path.basename(str(source or ''))}")
            path = os.path.join(scratch, f"{name}.svg")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            result = subprocess.run([resvg, "-w", str(width_px), path, os.path.join(out, file)], capture_output=True, text=True)
            if result.returncode != 0:
                shutil.rmtree(out, ignore_errors=True)
                print(f"CANNOT RUN | resvg could not draw {name} ({board_check.clean((result.stdout + result.stderr).strip())})",
                      file=sys.stderr)
                return 2
            images.append({"file": file, "layer": name, "source": os.path.basename(str(source or "")),
                           "px_per_mm": PIXELS_PER_MM})
    header = {"gerbers": os.path.basename(os.path.normpath(gerbers)), "gerbonara": GERBONARA, "px_per_mm": PIXELS_PER_MM,
              "frame_mm": {"x_min": round(bounds[0][0], 4), "y_min": round(bounds[0][1], 4),
                           "x_max": round(bounds[1][0], 4), "y_max": round(bounds[1][1], 4)},
              "frame_note": "the Gerber files' own frame, Y up: a point of the design's own editor coordinates (x, y) is at (x, -y)"}
    notes = sorted({str(item.message).replace(gerbers + os.sep, "") for item in warned})
    write_index(out, header, images, notes)
    for note in notes:
        print(f"NOTE | gerbonara: {board_check.clean(note)}", file=stream)
    print(f"FRAME | x {header['frame_mm']['x_min']} to {header['frame_mm']['x_max']} mm, y {header['frame_mm']['y_min']} to "
          f"{header['frame_mm']['y_max']} mm | {PIXELS_PER_MM} px/mm", file=stream)
    print(f"RESULT | WRITTEN | {len(images)} images and their index | {out}", file=stream)
    return 0


def write_index(out: str, header: dict, images: List[dict], notes: List[str]) -> None:
    frame = header["frame_mm"]
    lines = [f"GERBERS | {header['gerbers']}",
             f"FRAME | x {frame['x_min']} to {frame['x_max']} mm, y {frame['y_min']} to {frame['y_max']} mm | "
             f"{PIXELS_PER_MM} px/mm | every image is drawn in this one frame",
             f"NOTE | {header['frame_note']}"]
    lines += [f"NOTE | gerbonara: {board_check.clean(note)}" for note in notes]
    lines += [f"IMAGE | {image['file']} | layer {image['layer']} | read from {image['source']}" for image in images]
    with open(os.path.join(out, "index.txt"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    with open(os.path.join(out, "index.json"), "w", encoding="utf-8") as handle:
        json.dump({**header, "notes": notes, "images": images}, handle, indent=2)
        handle.write("\n")


# --- Drawing the footprints -------------------------------------------------------------------

#: The layers a footprint's drawing shows: copper with its pad numbers, the legend that carries the first-pin and polarity marks, the fabrication layer's outline and the courtyard.
FOOTPRINT_LAYERS = "F.Cu,F.SilkS,F.Fab,F.CrtYd"
#: Pixels along the longer edge of a footprint's drawing, caption band included.
FOOTPRINT_LONG_EDGE_PX = 800
#: Space round a footprint's drawing, as a fraction of its longer edge, so that its outermost lines are not cut off.
FOOTPRINT_MARGIN = 0.1
#: Nodes holding a point in the footprint's own frame, whose Y changes sign when the footprint is turned back from the bottom side.
POINTS = ("xy", "start", "end", "mid", "center", "pos", "offset", "c1", "c2", "c3", "c4")
#: What a drawing's footprint keeps of the board's copy: not the board's own identity (its uuid, nets, properties and texts) or its models.
DROPPED = ("property", "fp_text", "fp_text_box", "model", "path", "sheetname",
           "sheetfile", "locked", "teardrops", "embedded_files", "at", "layer")
#: What a footprint's items carry that only the board's copy of it has, at any depth.
IDENTITY = ("uuid", "net", "tstamp", "pinfunction", "pintype")
ROTATION_RULE = ("Each drawing is the footprint at rotation 0, as seen from above, X to the right and Y down on the page. A part "
                 "on the Top side at Rotation R in the placement file is the drawing turned R degrees counter-clockwise on the "
                 "page, about the origin of the footprint: at 90 what stands at the top of the drawing is at the left, at 180 "
                 "it is at the bottom, at 270 it is at the right. The placement file's rotation is the counter-clockwise turn "
                 "from the footprint as the library draws it.")
BOTTOM_RULE = ("A part on the Bottom side is the drawing flipped over to the back of the board; the manufacturer's record gives "
               "no frame for a bottom-side part, so where its marking lies is what the assembler's preview shows.")


def flipped_layer(name: str) -> str:
    return "B." + name[2:] if name.startswith("F.") else "F." + name[2:] if name.startswith("B.") else name


def decimals(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def angle_between(value: float) -> str:
    return decimals((value + 180) % 360 - 180 if (value + 180) % 360 != 0 else 180)


def unturned(node: list, rotation: float, bottom: bool) -> None:
    """`node`, a part of a footprint held as the board places it, turned back in place to the footprint as its library draws it.

    A footprint's items are held in its own frame, which a bottom-side footprint has flipped about its X axis, and a
    pad's angle holds the footprint's own turn. So a flipped footprint's Y is changed in sign, its layers, its mirrored
    texts and its chamfered corners are exchanged, and its angles are negated; every angle has the footprint's turn taken out.
    """
    if not isinstance(node, list):
        return
    keyword = sexpr.head(node)
    if keyword == "at" and len(node) >= 3:
        if bottom:
            node[2] = decimals(-float(node[2]))
        if len(node) >= 4:
            turn = float(node[3]) - rotation
            node[3] = angle_between(-turn if bottom else turn)
    elif bottom and keyword in POINTS and len(node) >= 3:
        node[2] = decimals(-float(node[2]))
    elif bottom and keyword in ("layer", "layers"):
        node[1:] = [sexpr.Quoted(flipped_layer(item)) if isinstance(item, sexpr.Quoted) else item for item in node[1:]]
    elif bottom and keyword == "chamfer":
        node[1:] = [item.replace("top_", "bottom_") if item.startswith("top_") else item.replace("bottom_", "top_", 1)
                    if item.startswith("bottom_") else item for item in node[1:]]
    elif bottom and keyword == "justify":
        node[1:] = [item for item in node[1:] if item != "mirror"]
    for item in node[1:]:
        unturned(item, rotation, bottom)


def stripped(node: list) -> None:
    """`node` without the board's own identity, its uuids and nets, at every depth."""
    if isinstance(node, list):
        node[:] = [item for item in node if sexpr.head(item) not in IDENTITY]
        for item in node:
            stripped(item)


def library_footprint(held: list, version: str) -> list:
    """The footprint `held`, as a board holds it placed, as a library file draws it: at rotation 0 on the top side."""
    layer = sexpr.child(held, "layer")
    bottom = layer is not None and str(layer[1]).startswith("B.")
    at = sexpr.child(held, "at")
    rotation = float(at[3]) if at is not None and len(at) >= 4 else 0.0
    kept = copy.deepcopy([item for item in held[2:] if sexpr.head(item) not in DROPPED + IDENTITY])
    for item in kept:
        stripped(item)
        unturned(item, rotation, bottom)
    name = str(held[1]).split(":", 1)[-1]
    return ["footprint", sexpr.Quoted(name), ["version", version],
                    ["layer", sexpr.Quoted("F.Cu")]] + kept


def board_footprints(board: str) -> Dict[str, dict]:
    """Each distinct footprint the board carries, by lib id: its drawing's tree and the designators placed with it, in the board's order."""
    try:
        with open(board, encoding="utf-8") as handle:
            tree = sexpr.parse_one(handle.read())
    except (OSError, UnicodeDecodeError, sexpr.SexprError) as error:
        raise Refused(f"the board {board} cannot be read ({error})") from None
    if sexpr.head(tree) != "kicad_pcb":
        raise Refused(f"{board} is not a KiCad layout")
    version = sexpr.child(tree, "version")
    if version is None or len(version) < 2:
        raise Refused(f"{board} states no file version")
    found: Dict[str, dict] = {}
    for held in sexpr.children(tree, "footprint"):
        if len(held) < 2 or not isinstance(held[1], str) or not held[1]:
            raise Refused("a footprint of the board has no name")
        reference = next((str(item[2]) for item in sexpr.children(held, "property") if len(item) > 2 and item[1] == "Reference"), "")
        if not reference:
            raise Refused(f"a footprint of the board, {held[1]}, has no reference")
        layer = sexpr.child(held, "layer")
        top = layer is not None and str(layer[1]).startswith("F.")
        entry = found.get(str(held[1]))
        if entry is None:
            found[str(held[1])] = {"held": held, "top": top, "used": [reference]}
        else:
            entry["used"].append(reference)
            if top and not entry["top"]:
                entry["held"], entry["top"] = held, True
    for entry in found.values():
        entry["tree"] = library_footprint(entry["held"], str(version[1]))
    return found


def drawing_name(lib_id: str) -> str:
    return "footprint-" + re.sub(r"[^A-Za-z0-9._-]", "_", lib_id) + ".png"


def captioned(svg: str, text: str) -> Tuple[str, float, float]:
    """The footprint's SVG with a caption band added above the drawing, and the new width and height in millimetres."""
    box = re.search(r'viewBox="([-\d.e+]+) ([-\d.e+]+) ([-\d.e+]+) ([-\d.e+]+)"', svg)
    x, y, width, height = (float(box.group(n)) for n in range(1, 5))
    edge = max(width, height) * FOOTPRINT_MARGIN
    x, y, width, height = x - edge, y - edge, width + 2 * edge, height + 2 * edge
    size = min(width / (len(text) * 0.62), max(width, height) / 14)
    band = size * 2.2
    svg = svg.replace(box.group(0), f'viewBox="{x:g} {y - band:g} {width:g} {height + band:g}"', 1)
    svg = re.sub(r'width="[-\d.]+mm" height="[-\d.]+mm"', f'width="{width:g}mm" height="{height + band:g}mm"', svg, count=1)
    label = (f'<text x="{x + size * 0.3:g}" y="{y - band + size * 1.5:g}" font-size="{size:g}" font-family="monospace" '
             f'fill="#c00000">{board_views.escape(text)}</text>')
    return svg[:svg.rindex("</svg>")] + label + "\n</svg>\n", width, height + band


def footprints(board: str, out: str, kicad_cli: str, resvg: str, stream=None) -> int:
    stream = stream or sys.stdout
    problems = []
    if not os.path.isfile(board):
        problems.append(f"{board} is not a file")
    if os.path.isfile(out):
        problems.append(f"{out} is a file")
    elif os.path.isdir(out) and os.listdir(out):
        problems.append(f"{out} already holds files; give a new or empty folder")
    if problems:
        for why in problems:
            print(f"REFUSED | {board_check.clean(why)}", file=stream)
        print("RESULT | REFUSED | nothing was written", file=stream)
        return 1
    try:
        board_check.require_kicad(kicad_cli)
        board_views.require_resvg(resvg)
    except board_check.CannotRun as error:
        print(f"CANNOT RUN | {board_check.clean(str(error))}", file=sys.stderr)
        return 2
    try:
        found = board_footprints(board)
        names = {}
        for lib_id in found:
            if drawing_name(lib_id) in names:
                raise Refused(f"the footprints {names[drawing_name(lib_id)]} and {lib_id} would be drawn into one file")
            names[drawing_name(lib_id)] = lib_id
    except Refused as error:
        print(f"REFUSED | {board_check.clean(str(error))}", file=stream)
        print("RESULT | REFUSED | nothing was written", file=stream)
        return 1
    if not found:
        print(f"REFUSED | {board_check.clean(board)} carries no footprint", file=stream)
        print("RESULT | REFUSED | nothing was written", file=stream)
        return 1
    images = []
    with tempfile.TemporaryDirectory(prefix="production-footprints-") as scratch:
        library = os.path.join(scratch, "library.pretty")
        drawn = os.path.join(scratch, "drawn")
        os.makedirs(library)
        os.makedirs(drawn)
        for entry in found.values():
            name = str(entry["tree"][1])
            with open(os.path.join(library, f"{name}.kicad_mod"), "w", encoding="utf-8") as handle:
                handle.write(sexpr.dump(entry["tree"]) + "\n")
        result = subprocess.run([kicad_cli, "fp", "export", "svg", "--layers", FOOTPRINT_LAYERS, "--sketch-pads-on-fab-layers",
                                 "--output", drawn, library], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"CANNOT RUN | kicad-cli could not draw the footprints ({board_check.clean((result.stdout + result.stderr).strip())})",
                  file=sys.stderr)
            return 2
        os.makedirs(out, exist_ok=True)
        for lib_id, entry in found.items():
            svg_path = os.path.join(drawn, f"{entry['tree'][1]}.svg")
            if not os.path.isfile(svg_path):
                shutil.rmtree(out, ignore_errors=True)
                print(f"CANNOT RUN | kicad-cli drew no image of the footprint {lib_id}", file=sys.stderr)
                return 2
            with open(svg_path, encoding="utf-8") as handle:
                svg, width, height = captioned(handle.read(), f"{lib_id}  rotation 0")
            with open(svg_path, "w", encoding="utf-8") as handle:
                handle.write(svg)
            scale = FOOTPRINT_LONG_EDGE_PX / max(width, height)
            file = drawing_name(lib_id)
            result = subprocess.run([resvg, "--background", "white", "-w", str(int(round(width * scale))), svg_path,
                                     os.path.join(out, file)], capture_output=True, text=True)
            if result.returncode != 0:
                shutil.rmtree(out, ignore_errors=True)
                print(f"CANNOT RUN | resvg could not draw {lib_id} ({board_check.clean((result.stdout + result.stderr).strip())})",
                      file=sys.stderr)
                return 2
            images.append({"file": file, "footprint": lib_id, "used_by": entry["used"], "px_per_mm": round(scale, 2)})
    write_footprint_index(out, os.path.basename(board), images)
    print(f"FOOTPRINTS | {len(images)} footprints | {sum(len(image['used_by']) for image in images)} parts", file=stream)
    print(f"RESULT | WRITTEN | {len(images)} images and their index | {out}", file=stream)
    return 0


def write_footprint_index(out: str, board: str, images: List[dict]) -> None:
    lines = [f"BOARD | {board}", f"RULE | {ROTATION_RULE}", f"RULE | {BOTTOM_RULE}",
             "NOTE | each drawing shows the footprint's copper with its pad numbers, its legend, its fabrication outline and its "
             "courtyard; a first pin is the pad numbered 1, and its mark is the legend's or the fabrication outline's, "
             "beside it"]
    lines += [f"IMAGE | {image['file']} | footprint {image['footprint']} | {image['px_per_mm']} px/mm | carried by "
              f"{', '.join(image['used_by'])}" for image in images]
    with open(os.path.join(out, "index.txt"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    with open(os.path.join(out, "index.json"), "w", encoding="utf-8") as handle:
        json.dump({"board": board, "rotation_rule": ROTATION_RULE, "bottom_rule": BOTTOM_RULE, "images": images}, handle, indent=2)
        handle.write("\n")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    convert = commands.add_parser("placement", help="write the assembler's placement file from KiCad's position export")
    convert.add_argument("--positions", required=True, help="the position export, as kicad-cli pcb export pos --format csv writes it")
    convert.add_argument("--out", required=True, help="the placement file to write, a new file")
    draw = commands.add_parser("render", help="draw every exported Gerber layer and the drill file into one frame")
    draw.add_argument("--gerbers", required=True, help="the folder the Gerber and drill files were exported into")
    draw.add_argument("--out", required=True, help="the folder to write the images and their index into, new or empty")
    draw.add_argument("--resvg", default="resvg", help="the resvg rasteriser (default: resvg on the search path)")
    drawing = commands.add_parser("footprints", help="draw every footprint the board carries at rotation 0")
    drawing.add_argument("--board", required=True, help="the board layout, .kicad_pcb")
    drawing.add_argument("--out", required=True, help="the folder to write the images and their index into, new or empty")
    drawing.add_argument("--kicad-cli", default="kicad-cli", help="KiCad's command-line tool (default: kicad-cli on the search path)")
    drawing.add_argument("--resvg", default="resvg", help="the resvg rasteriser (default: resvg on the search path)")
    args = parser.parse_args(argv)
    if args.command == "footprints":
        return footprints(os.path.abspath(args.board), os.path.abspath(args.out), args.kicad_cli, args.resvg)
    if args.command == "placement":
        return placement(os.path.abspath(args.positions), os.path.abspath(args.out))
    return render(os.path.abspath(args.gerbers), os.path.abspath(args.out), args.resvg)


if __name__ == "__main__":
    sys.exit(main())
