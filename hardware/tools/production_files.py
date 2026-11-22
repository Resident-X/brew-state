#!/usr/bin/env python3
"""Turn a board's exported production files into what the method's ordering step reads.

KiCad's command-line tool exports the position file, the parts list, the Gerber
layers and the drill file, and the method's ordering step names those commands.
Three things it cannot do are done here:

    production_files.py fetch-footprints --board <layout, .kicad_pcb> --out <folder outside the repository> --fitting <parts specification record> [--format text|json]
    production_files.py placement --positions <KiCad position export, CSV> --board <layout> --assembler-footprints <folder> --fitting <parts specification record> --out <new or empty folder> [--overrides <record>] --unavailable <record> [--format text|json]
    production_files.py parts-list --schematic <root schematic> --board <layout> --fitting <parts specification record> --catalogue <catalogue extract> --out <new or empty folder> --unavailable <record> [--format text|json]
    production_files.py render --gerbers <folder of exported Gerber and drill files> --out <new or empty folder> [--resvg ...]
    production_files.py footprints --board <layout, .kicad_pcb> --out <new or empty folder> [--kicad-cli ...] [--resvg ...]

`fetch-footprints` keeps the assembler's published footprint of each catalogue number the board's
assembler-fitted parts carry, once for each number and a second apart, in a folder outside the repository.

`placement` writes the assembler's placement file in the assembler's own footprint frame, as two sets from the one
design: the full set, every part the parts specification record gives to the assembler, through-hole parts included, and the
surface-mount set. The columns are the manufacturer's record's, Designator, Mid X, Mid Y, Layer and Rotation. A part's
row is found by matching the board's pads to the assembler's footprint by pad number: the rotation, counter-clockwise in
degrees, and the position of the assembler's footprint origin that bring the one onto the other. The position export names
which parts are placed and is checked against the board; its own origin and rotation are not carried through. A part whose
pads cannot all be matched is refused by name and enters only through a recorded per-part override with its reason.

`parts-list` writes the parts list in the same two sets, one row for each catalogue number with one comment. The comment
is the one the board's catalogue extract holds for the number, so it does not depend on how the schematic spells a
position's value (a net label, a cartridge rating). It refuses a number whose extract entry is missing or has no comment,
and a number the extract holds twice, naming the number. A position whose fitted_by is `none` (a hole, a fiducial, a net
tie) is in neither set.

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
import datetime
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import warnings
from typing import Dict, List, Optional, Tuple

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import board_views  # noqa: E402
import schematic_facts  # noqa: E402
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


# --- The assembler's footprint frame, the two file sets and the parts list ----------------------

#: How far, in millimetres, a part's pads may stand from the assembler's footprint after the fit before the part is refused.
FIT_TOLERANCE_MM = 0.1
#: The assembler's published footprint source (the component service its parts library is drawn from) and its units: its
#: footprint shapes are in units of 0.01 inch (10 mil, 0.254 mm), with Y running down from the footprint's own origin.
FOOTPRINT_SERVICE = "https://easyeda.com/api/products/{lcsc}/components?version=6.4.19.5"
FOOTPRINT_UNIT_MM = 0.254
#: Seconds between two requests to the service: one a second, a pace no page of the service states a limit below.
FETCH_PACE_SECONDS = 1.0
SET_FILES = {"placement": ("placement-full.csv", "placement-smd.csv"), "parts": ("parts-list-full.csv", "parts-list-smd.csv")}
PARTS_COLUMNS = ["Comment", "Designator", "Footprint", "JLCPCB Part #"]
OVERRIDE_KEYS = ("reference", "x", "y", "rotation", "reason")


class BoardPart:
    """One footprint of a board layout as the ordering step reads it: the pads' places in the export's frame (Y up, as the
    Gerber files are), its side, its catalogue number and how it is mounted."""

    def __init__(self, reference, side, x, y, rotation, lcsc, mount, excluded, dnp, pads):
        self.reference, self.side, self.x, self.y, self.rotation = reference, side, x, y, rotation
        self.lcsc, self.mount, self.excluded, self.dnp, self.pads = lcsc, mount, excluded, dnp, pads


def export_frame(x: float, y: float) -> Tuple[float, float]:
    """An editor point in the frame of the position export and the Gerber files: Y runs up there and down in the editor."""
    return x, -y


def row_angle(theta: float) -> float:
    """The angle the placement file carries for the turn found: counter-clockwise, as the manufacturer's record gives it."""
    return theta


def row_position(part: BoardPart, shift: Tuple[float, float]) -> Tuple[float, float]:
    """The point the placement file carries for the part: where the assembler's footprint origin lands, which is not the
    board footprint's own origin unless the two footprints share one."""
    return shift


def turn(point: Tuple[float, float], theta: float, shift: Tuple[float, float], mirror: bool) -> Tuple[float, float]:
    """A point of the assembler's footprint (Y up) put on the board by the placement row: mirrored in X for the bottom side,
    turned counter-clockwise by `theta` degrees about the footprint's origin, then shifted to the row's point."""
    x, y = (-point[0] if mirror else point[0]), point[1]
    angle = math.radians(theta)
    return (x * math.cos(angle) - y * math.sin(angle) + shift[0], x * math.sin(angle) + y * math.cos(angle) + shift[1])


def board_parts(path: str) -> Dict[str, BoardPart]:
    """Every footprint of the layout by reference: Refused when the file cannot be read, or a footprint has no reference, a
    side other than the front or the back copper, or a reference twice."""
    try:
        with open(path, encoding="utf-8") as handle:
            tree = sexpr.parse_one(handle.read())
    except (OSError, UnicodeDecodeError, sexpr.SexprError, IndexError, RecursionError) as error:
        raise Refused(f"the board {path} cannot be read ({error})") from None
    found: Dict[str, BoardPart] = {}
    for footprint in sexpr.children(tree, "footprint"):
        props = {str(p[1]): str(p[2]) for p in sexpr.children(footprint, "property") if len(p) > 2}
        reference = props.get("Reference", "").strip()
        if not reference:
            raise Refused(f"the board {path} holds a footprint with no Reference")
        if reference in found:
            raise Refused(f"the board {path} holds the reference {reference} twice")
        layer = sexpr.child(footprint, "layer")
        side = {"F.Cu": "top", "B.Cu": "bottom"}.get(str(layer[1]) if layer and len(layer) > 1 else "")
        if side is None:
            raise Refused(f"{reference} is on a layer that is neither F.Cu nor B.Cu")
        at = sexpr.child(footprint, "at")
        try:
            fx, fy = float(at[1]), float(at[2])
            frot = float(at[3]) if len(at) > 3 else 0.0
            attr = [str(word) for word in (sexpr.child(footprint, "attr") or [])[1:]]
            pads: Dict[str, List[Tuple[float, float]]] = {}
            for pad in sexpr.children(footprint, "pad"):
                place = sexpr.child(pad, "at")
                px, py = float(place[1]), float(place[2])
                angle = math.radians(frot)
                editor = (fx + px * math.cos(angle) + py * math.sin(angle), fy - px * math.sin(angle) + py * math.cos(angle))
                pads.setdefault(str(pad[1]), []).append(export_frame(*editor))
        except (TypeError, ValueError, IndexError):
            raise Refused(f"{reference}'s place or one of its pads cannot be read as numbers") from None
        mount = "smd" if "smd" in attr else "through_hole" if "through_hole" in attr else ""
        found[reference] = BoardPart(reference, side, fx, -fy, frot, props.get("LCSC", "").strip(), mount,
                                     "exclude_from_pos_files" in attr, "dnp" in attr, pads)
    return found


def read_assembler_footprint(folder: str, lcsc: str) -> Dict[str, List[Tuple[float, float]]]:
    """The pads of the assembler's footprint for a catalogue number, by pad number, in the assembler's frame (millimetres, Y
    up, from the footprint's origin), from the file `fetch-footprints` kept: Refused when it is missing or unreadable."""
    path = os.path.join(folder, f"{lcsc}.json")
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        raise Refused(f"no footprint of the assembler's is kept for {lcsc} in {folder}; run fetch-footprints") from None
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise Refused(f"the assembler's footprint file {path} cannot be read ({error})") from None
    pads: Dict[str, List[Tuple[float, float]]] = {}
    try:
        if data["lcsc"] != lcsc:
            raise ValueError(f"it is for {data['lcsc']}")
        for key in ("source", "read_on"):
            if not isinstance(data.get(key), str) or not data[key].strip():
                raise ValueError(f"it states no {key}, which every kept footprint carries")
        for pad in data["pads"]:
            number = str(pad["number"]).strip()
            x, y = float(pad["x"]), float(pad["y"])
            if not number or not (math.isfinite(x) and math.isfinite(y)):
                raise ValueError("a pad has no number or a place that is not a finite number")
            pads.setdefault(number, []).append((x, y))
        if not pads:
            raise ValueError("it lists no pad")
    except (KeyError, TypeError, ValueError) as error:
        raise Refused(f"the assembler's footprint file {path} is not a footprint ({error})") from None
    return pads


def landing_error(theta: float, shift: Tuple[float, float], part: BoardPart, assembler: Dict[str, List[Tuple[float, float]]]) -> float:
    """The farthest any pad of the assembler's footprint, put on the board by the row `theta`, `shift`, lies from the nearest
    unused pad of the same number the board has; infinity where the pad numbers or their counts differ."""
    mirror = part.side == "bottom"
    if {n: len(p) for n, p in assembler.items()} != {n: len(p) for n, p in part.pads.items()}:
        return float("inf")
    worst = 0.0
    for number, points in assembler.items():
        free = list(part.pads[number])
        for point in points:
            landed = turn(point, theta, shift, mirror)
            near = min(free, key=lambda other: math.dist(other, landed))
            free.remove(near)
            worst = max(worst, math.dist(near, landed))
    return worst


def fit_part(part: BoardPart, assembler: Dict[str, List[Tuple[float, float]]], tolerance: float = FIT_TOLERANCE_MM):
    """The rotation (counter-clockwise degrees in 0 to 360) and the shift that bring the assembler's footprint onto the part's
    pads, matched by pad number, with the farthest pad's distance left over. Refused, naming the part, when its pad numbers
    differ from the assembler's, no rotation fits within `tolerance`, or the pads fix no rotation."""
    here, there = sorted(part.pads), sorted(assembler)
    if here != there:
        raise Refused(f"{part.reference}'s pads cannot all be matched: the board has the pad numbers {', '.join(here)} and the "
                      f"assembler's footprint {', '.join(there)}")
    if {n: len(p) for n, p in part.pads.items()} != {n: len(p) for n, p in assembler.items()}:
        raise Refused(f"{part.reference}'s pads cannot all be matched: the board and the assembler's footprint have a different "
                      "number of pads under one pad number")
    mirror = part.side == "bottom"
    source = [(-p[0] if mirror else p[0], p[1]) for number in there for p in assembler[number]]
    target = [p for number in there for p in part.pads[number]]
    centre = lambda points: (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))  # noqa: E731
    cs, ct = centre(source), centre(target)
    candidates = [0.0, 90.0, 180.0, 270.0, part.rotation % 360]
    # The turn between the two centred pad sets, number by number, where the pads fix one.
    cross = dot = 0.0
    for number in there:
        a = centre([(-p[0] if mirror else p[0], p[1]) for p in assembler[number]])
        b = centre(part.pads[number])
        a, b = (a[0] - cs[0], a[1] - cs[1]), (b[0] - ct[0], b[1] - ct[1])
        cross += a[0] * b[1] - a[1] * b[0]
        dot += a[0] * b[0] + a[1] * b[1]
    if math.hypot(cross, dot) > 1e-9:
        candidates.insert(0, math.degrees(math.atan2(cross, dot)) % 360)
    best = None
    for theta in candidates:
        moved = turn(cs, theta, (0.0, 0.0), False)
        shift = (ct[0] - moved[0], ct[1] - moved[1])
        error = landing_error(theta, shift, part, assembler)
        if error <= tolerance:
            gap = abs((theta - part.rotation + 180) % 360 - 180)
            if best is None or (round(error, 6), round(gap, 3)) < (round(best[2], 6), round(best[3], 3)):
                best = (theta, shift, error, gap)
    if best is None:
        raise Refused(f"{part.reference}'s pads cannot all be matched: no turn of the assembler's footprint brings every pad "
                      f"within {tolerance} mm of the board's")
    theta = best[0] % 360
    theta = round(theta) % 360 if abs(theta - round(theta)) < 1e-6 else theta
    return theta, best[1], best[2]


def load_yaml(path: str, what: str):
    """The parsed YAML of a record; PyYAML is loaded here and not at the top, because the render command runs under a
    gerbonara environment that holds no PyYAML. Refused when the file cannot be read or parsed."""
    try:
        import yaml
    except ImportError:
        raise board_check.CannotRun(f"PyYAML could not be imported by {sys.executable}, which the {what} needs") from None
    try:
        with open(path, encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise Refused(f"the {what} {path} cannot be read ({error})") from None


def fitting_record(path: str) -> Dict[str, dict]:
    """The positions of a parts specification record by reference: Refused when it cannot be read or lists no position."""
    data = load_yaml(path, "parts specification record")
    positions = data.get("positions") if isinstance(data, dict) else None
    if not isinstance(positions, list) or not positions or not all(isinstance(p, dict) and isinstance(p.get("reference"), str)
                                                                    for p in positions):
        raise Refused(f"the parts specification record {path} lacks positions, a list of entries each naming a reference")
    return {entry["reference"]: entry for entry in positions}


def availability_record(path: Optional[str]) -> set:
    """The catalogue numbers the assembler's catalogue lists as unavailable for assembly, from the order-date reading the
    record at `path` holds (its source and the date read are required). The record is required: without it a part the
    assembler cannot supply would stand in both sets."""
    if path is None:
        raise Refused("--unavailable is required: give the order-date record of catalogue numbers the assembler lists as "
                      "unavailable for assembly (an empty list where none), so no part it cannot supply enters either set")
    data = load_yaml(path, "availability record")
    listed = data.get("unavailable") if isinstance(data, dict) else None
    if (not isinstance(listed, list) or not all(isinstance(n, str) and n.strip() for n in listed)
            or not all(data.get(key) is not None and str(data[key]).strip() for key in ("source", "read_on"))):
        raise Refused(f"the availability record {path} lacks unavailable (a list of catalogue numbers, empty where none), "
                      "source or read_on, each non-blank text")
    return {n.strip() for n in listed}


def catalogue_comments(path: str) -> Tuple[Dict[str, str], List[str]]:
    """The comment of each catalogue number the catalogue extract at `path` holds, and the numbers it holds more than once.
    Refused when the extract cannot be read or lists no entries."""
    data = load_yaml(path, "catalogue extract")
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
        raise Refused(f"the catalogue extract {path} lacks entries, a list of entries each carrying an lcsc number")
    comments: Dict[str, str] = {}
    twice: List[str] = []
    for index, entry in enumerate(entries):
        number = entry.get("lcsc")
        if not isinstance(number, str) or not number.strip():
            raise Refused(f"the catalogue extract {path} entry {index} (counting from 0) has no lcsc number, or one that is not "
                          f"non-blank text ({number!r})")
        number = number.strip()
        if number in comments or number in twice:
            if number not in twice:
                twice.append(number)
            continue
        text = entry.get("comment")
        blank = text is None or (isinstance(text, str) and not text.strip())
        if not blank and board_check.comment_problem(text):
            raise Refused(f"the catalogue extract holds for {number} a comment that is {board_check.comment_problem(text)}")
        comments[number] = text.strip() if isinstance(text, str) else ""
    return comments, twice


def classify(reference: str, part: Optional[BoardPart], entry: Optional[dict], unavailable: set) -> Tuple[str, str]:
    """Which file sets a position is in, `both` (the full set and the surface-mount set), `full` (the full set only) or
    `none`, and why. Refused, naming the position, when its place in the sets cannot be told."""
    if part is None:
        raise Refused(f"{reference} is not on the board")
    if entry is None:
        raise Refused(f"the parts specification record lists no position for {reference}")
    if entry.get("fitted") == board_check.NOT_FITTED:
        return "none", "not fitted (do not populate)"
    fitter = entry.get("fitted_by")
    if fitter not in board_check.FITTED_BY_VALUES:
        raise Refused(f"the parts specification record gives {reference} no fitted_by of {' or '.join(board_check.FITTED_BY_VALUES)}"
                      + (f", only {fitter!r}" if fitter is not None else ""))
    stated = entry.get("lcsc")
    lcsc = stated.strip() if isinstance(stated, str) else ""
    if part.lcsc != lcsc:
        raise Refused(f"{reference}'s catalogue number is {part.lcsc or 'absent'} on the board and {lcsc or 'absent'} in the "
                      "parts specification record")
    mismatch = board_check.fitter_problem(fitter, stated)
    if mismatch:
        raise Refused(f"the parts specification record gives {reference} {mismatch}")
    if fitter == board_check.NOT_A_PART:
        return "none", "not a part to be fitted"
    if fitter == "owner":
        return "none", "fitted by the owner"
    if lcsc in unavailable:
        return "none", f"{lcsc} is unavailable for assembly"
    if part.excluded:
        raise Refused(f"{reference} is marked for the assembler but its footprint is excluded from the position files, so no "
                      "placement row can be written for it; mark it fitted by the owner")
    if part.mount == "smd":
        return "both", "surface-mount"
    if part.mount == "through_hole":
        return "full", "through-hole"
    raise Refused(f"{reference} is marked for the assembler but its footprint is neither surface-mount nor through-hole")


def new_folder(out: str) -> Optional[str]:
    if os.path.isfile(out):
        return f"{out} is a file"
    if os.path.isdir(out) and os.listdir(out):
        return f"{out} already holds files; give a new or empty folder"
    return None


def report(stream, fmt: str, result: str, refused: List[str], lines: List[str], document: dict) -> int:
    """The command's report in the format asked for: text lines or one JSON document with the same facts."""
    if fmt == "json":
        print(json.dumps({"result": result, "refused": refused, **document}, indent=2), file=stream)
    else:
        for why in refused:
            print(f"REFUSED | {board_check.clean(why)}", file=stream)
        for line in lines:
            print(line, file=stream)
    return 1 if result == "REFUSED" else 0


def read_overrides(path: Optional[str]) -> Dict[str, dict]:
    """The recorded per-part overrides by reference: each states the reference, x, y, rotation and a non-blank reason."""
    if path is None:
        return {}
    data = load_yaml(path, "overrides record")
    listed = data.get("overrides") if isinstance(data, dict) else None
    if not isinstance(listed, list):
        raise Refused(f"the overrides record {path} lacks overrides, a list that is empty where none")
    found: Dict[str, dict] = {}
    for index, entry in enumerate(listed):
        where = f"overrides[{index}] of {path}"
        if not isinstance(entry, dict) or set(entry) != set(OVERRIDE_KEYS):
            raise Refused(f"{where} is not a mapping of exactly the keys {', '.join(OVERRIDE_KEYS)}")
        if not isinstance(entry["reason"], str) or not entry["reason"].strip():
            raise Refused(f"{where} gives no reason; a part's override states why its pads cannot be matched")
        for key in ("x", "y", "rotation"):
            if isinstance(entry[key], bool) or not isinstance(entry[key], (int, float)) or not math.isfinite(entry[key]):
                raise Refused(f"{where}.{key} is {entry[key]!r}, not a finite number")
        if not isinstance(entry["reference"], str) or entry["reference"] in found:
            raise Refused(f"{where} names no reference, or one already overridden")
        found[entry["reference"]] = entry
    return found


def placement(positions: str, board: str, footprints: str, record: str, out: str, overrides: Optional[str] = None,
              unavailable: Optional[str] = None, fmt: str = "text", stream=None, tolerance: float = FIT_TOLERANCE_MM) -> int:
    """Write the full set and the surface-mount set of the placement file into the new or empty folder `out`, each row in the
    assembler's own footprint frame."""
    stream = stream or sys.stdout
    problems: List[str] = []
    rows: Dict[str, List[str]] = {}
    omitted: List[dict] = []
    used: List[dict] = []
    try:
        why = new_folder(out)
        if why:
            raise Refused(why)
        exported = placement_rows(read_positions(positions))
        parts, entries, gone = board_parts(board), fitting_record(record), availability_record(unavailable)
        replaced = read_overrides(overrides)
        modes: Dict[str, str] = {}
        for row in exported:
            reference = row[0]
            try:
                part = parts.get(reference)
                modes[reference], reason = classify(reference, part, entries.get(reference), gone)
                if modes[reference] == "none":
                    omitted.append({"reference": reference, "reason": reason})
                    continue
                side = SIDES["bottom" if part.side == "bottom" else "top"]
                if row[3] != side or math.dist((float(row[1]), float(row[2])), (part.x, part.y)) > 0.01:
                    raise Refused(f"the position export and the board disagree on {reference}: the export places it on the "
                                  f"{row[3]} at ({row[1]}, {row[2]}), the board on the {side} at ({figure(part.x)}, {figure(part.y)})")
                try:
                    theta, shift, _ = fit_part(part, read_assembler_footprint(footprints, part.lcsc), tolerance)
                except Refused as error:
                    if reference not in replaced:
                        raise Refused(f"{error}; it enters the file only through a recorded override with its reason") from None
                    given = replaced.pop(reference)
                    rows[reference] = [reference, figure(given["x"]), figure(given["y"]), side, figure(given["rotation"] % 360)]
                    used.append({"reference": reference, "reason": given["reason"].strip()})
                    continue
                if reference in replaced:
                    raise Refused(f"the override for {reference} is stale: its pads match the assembler's footprint, so the "
                                  "file takes the fitted row and the override is removed")
                x, y = row_position(part, shift)
                row_out = [reference, figure(x), figure(y), side, figure(row_angle(theta) % 360)]
                landed = landing_error(float(row_out[4]), (float(row_out[1]), float(row_out[2])), part,
                                       read_assembler_footprint(footprints, part.lcsc))
                if landed > tolerance + 0.001:
                    raise Refused(f"{reference}'s row ({', '.join(row_out[1:])}) does not land the assembler's footprint on the "
                                  f"board's pads: its farthest pad is {landed:.3f} mm away")
                rows[reference] = row_out
            except Refused as error:
                problems.append(str(error))
        for reference in sorted(set(replaced) - {r for r in rows}):
            problems.append(f"the override for {reference} names a part that is not placed in the full set")
        listed = {row[0] for row in exported}
        for reference, entry in entries.items():
            if reference not in listed and entry.get("fitted_by") == "assembler" and entry.get("fitted") != board_check.NOT_FITTED:
                problems.append(f"{reference} is marked for the assembler but the position export lists no row for it")
    except Refused as error:
        problems.append(str(error))
    if problems:
        return report(stream, fmt, "REFUSED", problems, ["RESULT | REFUSED | nothing was written"], {"written": []})
    full = [rows[row[0]] for row in exported if row[0] in rows]
    smd = [rows[ref] for ref in (row[0] for row in exported) if ref in rows and modes[ref] == "both"]
    os.makedirs(out, exist_ok=True)
    names = SET_FILES["placement"]
    write_placement(os.path.join(out, names[0]), full)
    write_placement(os.path.join(out, names[1]), smd)
    lines = [f"SET | full | {len(full)} parts | {names[0]}", f"SET | smd | {len(smd)} parts | {names[1]}"]
    if tolerance != FIT_TOLERANCE_MM:
        lines.append(f"NOTE | the pad-match tolerance is {tolerance} mm, not the default {FIT_TOLERANCE_MM} mm; a larger figure weakens the check that each part's pads land on the board's")
    lines += [f"OMITTED | {item['reference']} | {item['reason']}" for item in omitted]
    lines += [f"OVERRIDE | {item['reference']} | {item['reason']}" for item in used]
    lines.append(f"RESULT | WRITTEN | {out}")
    return report(stream, fmt, "WRITTEN", [], lines, {"out": out, "sets": {"full": full, "smd": smd}, "omitted": omitted,
                                                       "overrides": used, "tolerance": tolerance})


def natural(reference: str) -> list:
    return [int(piece) if piece.isdigit() else piece for piece in re.split(r"(\d+)", reference)]


def schematic_parts(root: str) -> Dict[str, Dict[str, str]]:
    """Every placed part of the schematic whose root file is `root`, sheets below it included, by reference: its Value,
    Footprint and LCSC texts. A part drawn not to be in the bill of materials, or do not populate, is left out. Refused where
    a file cannot be read or one reference is drawn with two sets of fields."""
    project = os.path.splitext(os.path.basename(root))[0]
    found: Dict[str, Dict[str, str]] = {}

    def walk(path: str, ancestry: Tuple[str, ...]) -> None:
        try:
            with open(path, encoding="utf-8") as handle:
                tree = sexpr.parse_one(handle.read())
        except (OSError, UnicodeDecodeError, sexpr.SexprError, IndexError, RecursionError) as error:
            raise Refused(f"the schematic file {path} cannot be read ({error})") from None
        for symbol in sexpr.children(tree, "symbol"):
            flags = {str(sexpr.head(node)): str(node[1]) for node in symbol if sexpr.head(node) in ("in_bom", "dnp") and len(node) > 1}
            if flags.get("in_bom") == "no" or flags.get("dnp") == "yes":
                continue
            fields = {str(p[1]): str(p[2]) for p in sexpr.children(symbol, "property") if len(p) > 2}
            for reference in schematic_facts.references(symbol, project):
                if reference.startswith("#"):
                    continue
                fresh = {"Value": fields.get("Value", ""), "Footprint": fields.get("Footprint", ""),
                         "LCSC": fields.get("LCSC", "").strip()}
                if reference in found and found[reference] != fresh:
                    raise Refused(f"{reference} is drawn with two different sets of fields")
                found[reference] = fresh
        if path in ancestry:
            return
        for sheet in sexpr.children(tree, "sheet"):
            target = schematic_facts.sheet_file_of(sheet)
            if target is None:
                raise Refused(f"a sheet of {path} names no one file")
            walk(os.path.normpath(os.path.join(os.path.dirname(path), target)), ancestry + (path,))

    walk(root, ())
    return found


def parts_list(schematic: str, board: str, record: str, catalogue: str, out: str, unavailable: Optional[str] = None,
               fmt: str = "text", stream=None) -> int:
    """Write the full set and the surface-mount set of the parts list into the new or empty folder `out`: one row for each
    catalogue number with the one comment the catalogue extract `catalogue` holds for it, the designators of the set's positions that carry it, the footprint and the number."""
    stream = stream or sys.stdout
    problems: List[str] = []
    members: Dict[str, str] = {}
    omitted: List[dict] = []
    drawn: Dict[str, Dict[str, str]] = {}
    try:
        why = new_folder(out)
        if why:
            raise Refused(why)
        drawn = schematic_parts(schematic)
        parts, entries, gone = board_parts(board), fitting_record(record), availability_record(unavailable)
        for reference in sorted(drawn, key=natural):
            try:
                if not drawn[reference]["LCSC"]:
                    raise Refused(f"{reference} carries no LCSC field in the schematic; state a catalogue number, or the word "
                                  f"{board_check.NO_CATALOGUE_NUMBER} for a part the assembler does not place")
                if reference in entries and reference in parts and drawn[reference]["LCSC"] != str(entries[reference].get("lcsc", "")).strip():
                    raise Refused(f"{reference}'s catalogue number is {drawn[reference]['LCSC']} in the schematic and "
                                  f"{entries[reference].get('lcsc', 'absent')} in the parts specification record")
                members[reference], reason = classify(reference, parts.get(reference), entries.get(reference), gone)
                if members[reference] == "none":
                    omitted.append({"reference": reference, "reason": reason})
            except Refused as error:
                problems.append(str(error))
        for reference, entry in entries.items():
            if reference not in drawn and entry.get("fitted_by") == "assembler" and entry.get("fitted") != board_check.NOT_FITTED:
                problems.append(f"{reference} is marked for the assembler but the schematic draws no such part")
        comments, twice = catalogue_comments(catalogue)
        for number in sorted(twice):
            problems.append(f"the catalogue extract holds the catalogue number {number} more than once; keep one entry, with one comment, for each number")
        for number in sorted({drawn[ref]["LCSC"] for ref, mode in members.items() if mode != "none"}):
            if number not in twice and not comments.get(number):
                problems.append(f"the catalogue extract holds {'no comment' if number in comments else 'no entry'} for the catalogue number "
                                f"{number}, which the parts list needs one comment for")
    except Refused as error:
        problems.append(str(error))
    if problems:
        return report(stream, fmt, "REFUSED", problems, ["RESULT | REFUSED | nothing was written"], {"written": []})

    def rows(wanted: Tuple[str, ...]) -> List[List[str]]:
        groups: Dict[str, List[str]] = {}
        for reference, mode in members.items():
            if mode in wanted:
                groups.setdefault(drawn[reference]["LCSC"], []).append(reference)
        found = []
        for number, refs in groups.items():
            refs.sort(key=natural)
            first = drawn[refs[0]]
            found.append([comments[number], ", ".join(refs), first["Footprint"], number])
        return sorted(found, key=lambda row: natural(row[1].split(", ")[0]))

    sets = {"full": rows(("both", "full")), "smd": rows(("both",))}
    os.makedirs(out, exist_ok=True)
    for name, key in zip(SET_FILES["parts"], ("full", "smd")):
        with open(os.path.join(out, name), "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(PARTS_COLUMNS)
            writer.writerows(sets[key])
    lines = [f"SET | {key} | {len(sets[key])} rows | {name}" for key, name in zip(("full", "smd"), SET_FILES["parts"])]
    lines += [f"OMITTED | {item['reference']} | {item['reason']}" for item in omitted]
    lines.append(f"RESULT | WRITTEN | {out}")
    return report(stream, fmt, "WRITTEN", [], lines, {"out": out, "sets": sets, "omitted": omitted})


def footprint_from_service(text: str, lcsc: str) -> dict:
    """The kept form of the assembler's footprint for a catalogue number from the service's answer: its pads by number in
    millimetres, Y up, from the footprint's own origin. Refused when the answer holds no footprint with a pad."""
    try:
        answer = json.loads(text)
        detail = answer["result"]["packageDetail"]["dataStr"]
        origin = (float(detail["head"]["x"]), float(detail["head"]["y"]))
        pads = []
        for shape in detail["shape"]:
            fields = shape.split("~")
            if fields[0] == "PAD":
                pads.append({"number": fields[8].strip(), "x": round((float(fields[2]) - origin[0]) * FOOTPRINT_UNIT_MM, 4) + 0.0,
                             "y": round((origin[1] - float(fields[3])) * FOOTPRINT_UNIT_MM, 4) + 0.0})
    except (KeyError, TypeError, ValueError, IndexError):
        raise Refused(f"the service's answer for {lcsc} holds no footprint it can be read from") from None
    if not pads or any(not pad["number"] for pad in pads):
        raise Refused(f"the service's answer for {lcsc} holds no pad, or a pad with no number")
    return {"lcsc": lcsc, "source": FOOTPRINT_SERVICE.format(lcsc=lcsc), "read_on": datetime.date.today().isoformat(), "pads": pads}


def fetch_service(lcsc: str) -> str:
    import urllib.request
    request = urllib.request.Request(FOOTPRINT_SERVICE.format(lcsc=lcsc), headers={"User-Agent": "board-tooling"})
    try:
        with urllib.request.urlopen(request, timeout=30) as answer:
            return answer.read().decode("utf-8")
    except (OSError, ValueError) as error:
        raise Refused(f"the service gave no footprint for {lcsc} ({error})") from None


def fetch_footprints(board: str, out: str, record: str, pace: float = FETCH_PACE_SECONDS, fmt: str = "text",
                     stream=None, fetch=fetch_service, sleep=time.sleep) -> int:
    """Keep the assembler's footprint for each catalogue number the board's assembler-fitted parts carry, once for each number, `pace` seconds apart, in the folder `out`, which stands outside
    the repository: a number already kept is not fetched again."""
    stream = stream or sys.stdout
    problems: List[str] = []
    fetched: List[str] = []
    kept: List[str] = []
    try:
        if inside(out, os.path.dirname(os.path.dirname(TOOLS))):
            raise Refused(f"{out} is inside the repository; the assembler's footprints are kept outside it")
        parts = board_parts(board)
        entries = fitting_record(record)
        numbers = sorted({part.lcsc for part in parts.values() if board_check.is_numbered(part.lcsc) and not part.dnp
                          and entries.get(part.reference, {}).get("fitted_by") == "assembler"
                          and entries[part.reference].get("fitted") != board_check.NOT_FITTED})
        os.makedirs(out, exist_ok=True)
        for number in numbers:
            target = os.path.join(out, f"{number}.json")
            if os.path.isfile(target):
                kept.append(number)
                continue
            if fetched:
                sleep(pace)
            try:
                kept_form = footprint_from_service(fetch(number), number)
            except Refused as error:
                problems.append(str(error))
                continue
            with open(target, "w", encoding="utf-8") as handle:
                json.dump(kept_form, handle, indent=2)
                handle.write("\n")
            fetched.append(number)
    except Refused as error:
        problems.append(str(error))
    if problems:
        return report(stream, fmt, "REFUSED", problems, ["RESULT | REFUSED | not every footprint is kept"], {"fetched": fetched, "kept": kept})
    lines = [f"FOOTPRINTS | {len(fetched)} fetched | {len(kept)} already kept | {out}", f"RESULT | WRITTEN | {out}"]
    return report(stream, fmt, "WRITTEN", [], lines, {"fetched": fetched, "kept": kept, "out": out})


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
    convert = commands.add_parser("placement", help="write the assembler's placement file, in its own footprint frame, as a full set and a surface-mount set")
    convert.add_argument("--positions", required=True, help="the position export, as kicad-cli pcb export pos --format csv writes it")
    convert.add_argument("--board", required=True, help="the board layout, .kicad_pcb, the export was made from")
    convert.add_argument("--assembler-footprints", required=True, help="the folder fetch-footprints kept the assembler's footprints in")
    convert.add_argument("--fitting", required=True, help="the board's parts specification record, parts-specification.yaml")
    convert.add_argument("--overrides", help="the record of per-part overrides, each with its reason")
    convert.add_argument("--unavailable", help="required: the order-date record of catalogue numbers the assembler lists as unavailable for assembly (empty list where none)")
    convert.add_argument("--tolerance", type=float, default=FIT_TOLERANCE_MM, help="the farthest a pad may stand from the assembler's footprint, in millimetres")
    convert.add_argument("--format", choices=("text", "json"), default="text", help="the report's form")
    convert.add_argument("--out", required=True, help="the folder to write placement-full.csv and placement-smd.csv into, new or empty")
    listing = commands.add_parser("parts-list", help="write the assembler's parts list as a full set and a surface-mount set")
    listing.add_argument("--schematic", required=True, help="the root schematic, .kicad_sch")
    listing.add_argument("--board", required=True, help="the board layout, .kicad_pcb")
    listing.add_argument("--fitting", required=True, help="the board's parts specification record, parts-specification.yaml")
    listing.add_argument("--catalogue", required=True, help="the board's catalogue extract, catalogue-extract.yaml, whose comment for each number is the parts list's comment")
    listing.add_argument("--unavailable", help="required: the order-date record of catalogue numbers the assembler lists as unavailable for assembly (empty list where none)")
    listing.add_argument("--format", choices=("text", "json"), default="text", help="the report's form")
    listing.add_argument("--out", required=True, help="the folder to write parts-list-full.csv and parts-list-smd.csv into, new or empty")
    keep = commands.add_parser("fetch-footprints", help="keep the assembler's published footprint of each catalogue number the board uses, outside the repository")
    keep.add_argument("--board", required=True, help="the board layout, .kicad_pcb")
    keep.add_argument("--fitting", required=True, help="the parts specification record; only the assembler-fitted parts' numbers are kept")
    keep.add_argument("--pace", type=float, default=FETCH_PACE_SECONDS, help="seconds between two requests")
    keep.add_argument("--format", choices=("text", "json"), default="text", help="the report's form")
    keep.add_argument("--out", required=True, help="the folder to keep the footprints in, outside the repository")
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
    try:
        if args.command == "placement":
            return placement(os.path.abspath(args.positions), os.path.abspath(args.board), os.path.abspath(args.assembler_footprints),
                             os.path.abspath(args.fitting), os.path.abspath(args.out), args.overrides and os.path.abspath(args.overrides),
                             args.unavailable and os.path.abspath(args.unavailable), args.format, tolerance=args.tolerance)
        if args.command == "parts-list":
            return parts_list(os.path.abspath(args.schematic), os.path.abspath(args.board), os.path.abspath(args.fitting),
                              os.path.abspath(args.catalogue), os.path.abspath(args.out), args.unavailable and os.path.abspath(args.unavailable), args.format)
        if args.command == "fetch-footprints":
            return fetch_footprints(os.path.abspath(args.board), os.path.abspath(args.out), os.path.abspath(args.fitting),
                                    args.pace, args.format)
    except board_check.CannotRun as error:
        print(f"CANNOT RUN | {board_check.clean(str(error))}", file=sys.stderr)
        return 2
    return render(os.path.abspath(args.gerbers), os.path.abspath(args.out), args.resvg)


if __name__ == "__main__":
    sys.exit(main())
