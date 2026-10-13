#!/usr/bin/env python3
"""The layout review views: every image a layout review judges a board on, rendered from the board's own files.

An image of one layer shows no net names, so a ground drawn as a thin trace
looks like any other track. The review is therefore given, besides an image of
every layer, views that show each critical net against the board, the critical
classes against each other, each integrated circuit with the parts on its
supply nets close enough to judge, each side as it is assembled, and the
assembled board in three dimensions, with a table of the facts a picture
cannot carry: each net's track widths, vias, zones and classes.

Every view is drawn from a temporary copy of the board whose zones KiCad has
refilled and saved, so a pour is drawn as the board's copper leaves it. The copy
keeps the design's own file names, and every model path the design's folder
anchors is written out in full, so the copy reads as the design does in place. A
net's copper is taken from a filtered copy of that refilled board holding only
the net's tracks, arcs, vias, zones and pads, which KiCad plots without
refilling, so a pour is never drawn into space the filter emptied. KiCad's
command-line export draws each layer as a vector image in board coordinates, and
resvg turns each view into a PNG on a dark background, with a caption drawn into
it.

Nothing is left out quietly. KiCad does not plot rule areas, so the command
draws them itself. A part KiCad draws without its model, a font KiCad
substitutes, and a fabrication or courtyard layer the board does not carry are
each named in the captions of the views they touch, in the index and in the
command's report. A three-dimensional view is zoomed out until no part reaches
its frame.

The resolution is the board's own: three pixels across the smaller of its
minimum track width and minimum clearance, read from its design rules. Every
image is kept within the size at which no reviewing model downsamples it, the
standard tier of the vendor's published limits, and a two-dimensional view
larger than that is cut into tiles. Each caption, and the index of every image,
states its layers, its net or class, its scale and the board coordinates it
covers.

Which nets are in which class is asked of KiCad, with the refusals the
locked-copper check makes, and the output folder is a working folder, refused
inside any design's folder and refused when it already holds files.

    board_views.py --board B.kicad_pcb --project B.kicad_pro --class NAME [--class NAME ...] --out FOLDER

Every finding is one line of a fixed shape, a result line comes last, and the
exit status is the verdict: 0 when every view is written, 1 when the command is
refused or its input cannot be read, 2 when it cannot run at all, for example
because a tool is missing.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from typing import Dict, List, Optional, Sequence, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
import locked_copper  # noqa: E402
import sexpr  # noqa: E402
from board_check import CannotRun, clean  # noqa: E402
from locked_copper import Unreadable  # noqa: E402

#: The first resvg the command was exercised with.
MIN_RESVG = (0, 48)

#: Pixels across the smallest track width and the smallest clearance.
PIXELS_PER_FEATURE = 3

#: The largest image no reviewing model downsamples: the standard tier of the
#: vendor's published limits, a long edge of 1568 pixels and 1568 visual
#: patches of 28 by 28 pixels.
LONG_EDGE_PX = 1568
PATCHES = 1568
PATCH_PX = 28

#: The layers every board carries, the edge layer holding its outline.
REQUIRED_LAYERS = ("F.Cu", "B.Cu", "F.Mask", "B.Mask", "F.Paste", "B.Paste", "F.SilkS", "B.SilkS", "Edge.Cuts")

BACKGROUND = "#101010"
CAPTION_COLOUR = "#e8e8e8"
RULE_COLOUR = "#606060"
FONT_FAMILY = "DejaVu Sans Mono, Menlo, Consolas, Liberation Mono, Courier New, monospace"
FONT_PX = 15
LINE_PX = 20
#: A generous width for one character of the caption's monospaced font, so a
#: wrapped line never runs past the image's edge.
CHAR_PX = FONT_PX * 0.62
CAPTION_PAD_PX = 8
#: The narrowest two-dimensional image, so a caption stays readable on a crop of
#: a small part: a narrower view is widened to show more of the board.
MIN_WIDTH_PX = 640
BOARD_MARGIN_MM = 1.0
CROP_MARGIN_MM = 1.5

#: Each layer's colour, by name, on the dark background.
LAYER_COLOURS = {
    "F.Cu": ("#e04848", "red"), "B.Cu": ("#4a86e8", "blue"),
    "F.Mask": ("#c050c0", "magenta"), "B.Mask": ("#30a8a0", "teal"),
    "F.Paste": ("#c8c8c8", "light grey"), "B.Paste": ("#8890b0", "slate"),
    "F.SilkS": ("#f4f4f4", "white"), "B.SilkS": ("#f0a0c8", "pink"),
    "Edge.Cuts": ("#f0e040", "yellow"),
    "F.Fab": ("#d0a870", "tan"), "B.Fab": ("#7890d0", "steel blue"),
    "F.CrtYd": ("#ff70ff", "violet"), "B.CrtYd": ("#60e8ff", "sky blue"),
}
#: Colours for inner copper and for every other layer, taken in turn.
OTHER_COLOURS = (("#e0b040", "amber"), ("#40c080", "green"), ("#b070f0", "purple"), ("#40c8c8", "cyan"),
                 ("#e08040", "orange"), ("#a0a0ff", "lavender"), ("#90d040", "lime"), ("#d07070", "rose"))
#: Each critical class's colour on the class map, taken in the order the classes are named.
CLASS_COLOURS = (("#ff5050", "red"), ("#50a0ff", "blue"), ("#ffd040", "yellow"), ("#50e080", "green"),
                 ("#e070ff", "violet"), ("#40e0e0", "cyan"), ("#ff9040", "orange"), ("#c0c0c0", "grey"))
#: The whole board, drawn faint beneath a net or the class map.
FAINT = ("#9a9a9a", "faint grey", 0.35)
#: Rule areas, which KiCad does not plot, drawn by the command as dashed, hatched outlines in this colour.
RULE_AREA = ("#ff8c1a", "bright orange")
RULE_RESTRICTIONS = (("tracks", "tracks"), ("vias", "vias"), ("pads", "pads"), ("copperpour", "copper pour"),
                     ("footprints", "footprints"))

#: A three-dimensional view is first rendered this many pixels along its longer side, to find the zoom at which
#: no part reaches the frame: the render must leave this many pixels clear on every side, and each try zooms out
#: by the step.
PROBE_PX = 240
PROBE_CLEAR_PX = 4
ZOOM_STEP = 0.8
ZOOM_TRIES = 15

#: How many references a caption names before it leaves the rest to the index.
CAPTION_NAMES = 40

#: KiCad's own words, read in English: the command sets KiCad's language so they are always these.
FONT_SUBSTITUTED = re.compile(r"Font '([^'\n]*)' not found; substituting '([^'\n]*)'")
MODEL_NOT_ADDED = re.compile(r"Could not add 3D model for (.*?)\.[ \t]*\n[ \t]*([^\n]*)")

#: The three-dimensional views: name, how KiCad is asked to render it, and the direction a caption states.
VIEWS_3D = (
    ("top", ["--side", "top"], "seen from the top"),
    ("bottom", ["--side", "bottom"], "seen from the bottom, so left and right are mirrored"),
    ("angled", ["--side", "top", "--rotate", "-45,0,45"],
     "seen from above at an angle: the board tilted 45 degrees about its X axis and turned 45 degrees about its "
     "vertical axis"),
)

#: The top-level forms of a layout that hold no item drawn on a layer.
HEADER_FORMS = {"version", "generator", "generator_version", "general", "paper", "title_block", "layers", "setup",
                "property", "net", "net_class", "embedded_fonts", "embedded_files"}
COPPER_FORMS = {"segment", "arc", "via", "zone"}

TOOL_HELP = "see hardware/README.md for what the command needs and where to get it"


# --- Tools ------------------------------------------------------------------------


def png_size(path: str) -> Tuple[int, int]:
    """A PNG's width and height in pixels, from its header."""
    with open(path, "rb") as handle:
        head = handle.read(24)
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        raise ValueError(f"{path} is not a PNG image")
    return struct.unpack(">II", head[16:24])


def read_png(path: str) -> Tuple[int, int, List[List[Tuple[int, int, int, int]]]]:
    """A PNG of 8-bit RGB or RGBA, non-interlaced, as its width, height and rows of (r, g, b, a) pixels."""
    with open(path, "rb") as handle:
        data = handle.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} is not a PNG image")
    at, header, compressed = 8, None, b""
    while at < len(data):
        length, kind = struct.unpack(">I4s", data[at:at + 8])
        body = data[at + 8:at + 8 + length]
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            compressed += body
        at += 12 + length
    width, height, depth, colour, _, _, interlace = header
    if depth != 8 or colour not in (2, 6) or interlace:
        raise ValueError(f"{path} is not an 8-bit RGB or RGBA PNG without interlacing")
    channels = 4 if colour == 6 else 3
    raw = zlib.decompress(compressed)
    stride = width * channels
    rows, previous = [], bytearray(stride)
    for row in range(height):
        kind = raw[row * (stride + 1)]
        line = bytearray(raw[row * (stride + 1) + 1:(row + 1) * (stride + 1)])
        for i in range(stride):
            left = line[i - channels] if i >= channels else 0
            up = previous[i]
            corner = previous[i - channels] if i >= channels else 0
            if kind == 1:
                line[i] = (line[i] + left) & 0xFF
            elif kind == 2:
                line[i] = (line[i] + up) & 0xFF
            elif kind == 3:
                line[i] = (line[i] + (left + up) // 2) & 0xFF
            elif kind == 4:
                guess = left + up - corner
                near = min((abs(guess - left), 0, left), (abs(guess - up), 1, up), (abs(guess - corner), 2, corner))
                line[i] = (line[i] + near[2]) & 0xFF
        rows.append([tuple(line[i:i + channels]) + ((255,) if channels == 3 else ())
                     for i in range(0, stride, channels)])
        previous = line
    return width, height, rows


def require_resvg(resvg: str) -> str:
    """resvg at its minimum version, able to draw a caption's text; its version string."""
    how = (f"Install resvg {MIN_RESVG[0]}.{MIN_RESVG[1]} or newer, one prebuilt program for each common operating "
           "system, from https://github.com/linebender/resvg/releases (or with cargo install resvg). If it is "
           "installed off the search path, run the task with RESVG=/path/to/resvg.")
    try:
        result = subprocess.run([resvg, "--version"], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise CannotRun(f"resvg was not found or could not be run at '{resvg}' ({error}). {how}") from error
    found = board_check.version_tuple(result.stdout)
    if result.returncode != 0 or found is None:
        raise CannotRun(f"'{resvg}' did not report a resvg version (exit {result.returncode}: "
                        f"{(result.stdout + result.stderr).strip()[:200]}). {how}")
    if found < MIN_RESVG:
        raise CannotRun(f"resvg at '{resvg}' is version {result.stdout.strip()}, older than the "
                        f"{MIN_RESVG[0]}.{MIN_RESVG[1]} the command needs. {how}")
    with tempfile.TemporaryDirectory(prefix="board-views-font-") as work:
        probe = os.path.join(work, "probe.svg")
        with open(probe, "w", encoding="utf-8") as handle:
            handle.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="120" height="30" viewBox="0 0 120 30">'
                         f'<text x="4" y="22" font-family="{FONT_FAMILY}" font-size="{FONT_PX}" '
                         f'fill="{CAPTION_COLOUR}">Caption 0.2 mm</text></svg>')
        image = os.path.join(work, "probe.png")
        rasterise(resvg, probe, image)
        _, _, rows = read_png(image)
    if not any(pixel[:3] != (16, 16, 16) for row in rows for pixel in row):
        raise CannotRun(f"resvg at '{resvg}' found no font to draw the captions with, so every image would lose "
                        "the facts its caption carries. Install a monospaced font, such as DejaVu Sans Mono "
                        f"(https://dejavu-fonts.github.io/), where resvg finds the system's fonts ({TOOL_HELP}).")
    return result.stdout.strip()


def rasterise(resvg: str, svg: str, png: str) -> None:
    try:
        result = subprocess.run([resvg, "--background", BACKGROUND, svg, png], capture_output=True, text=True,
                                timeout=board_check.KICAD_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise CannotRun(f"resvg could not be run on {svg} ({error}) ({TOOL_HELP}).") from error
    if result.returncode != 0 or not os.path.exists(png):
        raise CannotRun(f"resvg could not turn {svg} into an image (exit {result.returncode}: "
                        f"{' '.join((result.stdout + result.stderr).split())[:300]}) ({TOOL_HELP}).")


def english(home: str) -> None:
    """KiCad's own configuration in `home` set to report in English.

    KiCad translates what it reports, and the command reads two of its reports,
    a font it substitutes and a model it cannot find, so it fixes the language
    they are written in rather than miss them on a machine set to another.
    """
    try:
        found = [os.path.join(home, name, "kicad_common.json") for name in os.listdir(home)]
        path = next(path for path in found if os.path.isfile(path))
        with open(path, encoding="utf-8") as handle:
            settings = json.load(handle)
        settings.setdefault("system", {})["language"] = "English"
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(settings, handle, indent=2)
    except (OSError, ValueError, StopIteration, AttributeError) as error:
        raise CannotRun(f"KiCad's own configuration in {home} could not be set to report in English ({error}), so the "
                        f"command could not read which fonts and models KiCad leaves out ({TOOL_HELP}).") from error


def kicad(command: List[str], cwd: str, what: str) -> str:
    """Run a KiCad command in the command's own configuration, failing by name when it fails; what KiCad said."""
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=board_check.KICAD_TIMEOUT_S,
                                env=board_check.KICAD_ENVIRONMENT)
    except subprocess.TimeoutExpired as error:
        raise Unreadable(f"KiCad did not {what} within {board_check.KICAD_TIMEOUT_S} s") from error
    if result.returncode != 0:
        raise Unreadable(f"KiCad could not {what} (exit {result.returncode}: "
                         f"{' '.join((result.stdout + ' ' + result.stderr).split())[:300]})")
    return result.stdout + "\n" + result.stderr


def substituted(said: str) -> Dict[str, str]:
    """Each font KiCad says it could not find, with the font it drew that text in instead."""
    return {font: instead for font, instead in FONT_SUBSTITUTED.findall(said)}


# --- Reading the board ---------------------------------------------------------------


def layer_table(layout: list) -> List[str]:
    """The layers the board carries, by their canonical names, in the order its layer table gives them."""
    table = sexpr.child(layout, "layers")
    return [str(entry[1]) for entry in (table[1:] if table else []) if isinstance(entry, list) and len(entry) > 1]


def copper_order(layers: Sequence[str]) -> List[str]:
    """The copper layers, front first and back last."""
    inner = sorted((name for name in layers if re.fullmatch(r"In\d+\.Cu", name)), key=lambda name: int(name[2:-3]))
    return [name for name in ("F.Cu",) if name in layers] + inner + [name for name in ("B.Cu",) if name in layers]


def expand(name: str, carried: Sequence[str]) -> List[str]:
    """The layers a layer name in an item stands for, wildcards resolved against the layers the board carries."""
    if name.startswith("*."):
        return [layer for layer in carried if layer.endswith(name[1:])]
    if name.startswith("F&B."):
        return [layer for layer in (f"F.{name[4:]}", f"B.{name[4:]}") if layer in carried]
    return [name] if name in carried else []


def held_layers(layout: list, carried: Sequence[str]) -> Set[str]:
    """Every layer the board carries that holds any item."""
    held: Set[str] = set()

    def visit(node):
        if not isinstance(node, list):
            return
        if sexpr.head(node) in ("layer", "layers"):
            for name in node[1:]:
                if isinstance(name, str):
                    held.update(expand(str(name), carried))
        for part in node[1:]:
            visit(part)

    for node in layout[1:]:
        if isinstance(node, list) and sexpr.head(node) not in HEADER_FORMS:
            visit(node)
    return held


def number(node, index: int, what: str) -> float:
    try:
        return float(node[index])
    except (TypeError, ValueError, IndexError) as error:
        raise Unreadable(f"{what} is {sexpr.dump(node)}, not a position in millimetres") from error


def xy(node, what: str) -> Tuple[float, float]:
    if not isinstance(node, list) or len(node) < 3:
        raise Unreadable(f"{what} has no position where KiCad writes one")
    return number(node, 1, what), number(node, 2, what)


def arc_points(start, mid, end) -> List[Tuple[float, float]]:
    """Points along the arc through start, mid and end, close enough together for its bounds."""
    (ax, ay), (bx, by), (cx, cy) = start, mid, end
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return [start, mid, end]
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    radius = math.hypot(ax - ux, ay - uy)
    first, through, last = (math.atan2(p[1] - uy, p[0] - ux) for p in (start, mid, end))
    sweep = (last - first) % (2 * math.pi)
    if (through - first) % (2 * math.pi) > sweep:
        sweep -= 2 * math.pi
    return [(ux + radius * math.cos(first + sweep * i / 64), uy + radius * math.sin(first + sweep * i / 64))
            for i in range(65)]


def shape_points(node: list, what: str) -> List[Tuple[float, float]]:
    """The points bounding one graphic shape, in the coordinates it is written in."""
    kind = sexpr.head(node)[3:]
    if kind in ("line", "rect"):
        return [xy(sexpr.child(node, "start"), what), xy(sexpr.child(node, "end"), what)]
    if kind == "circle":
        centre = xy(sexpr.child(node, "center"), what)
        edge = xy(sexpr.child(node, "end"), what)
        radius = math.hypot(edge[0] - centre[0], edge[1] - centre[1])
        return [(centre[0] - radius, centre[1] - radius), (centre[0] + radius, centre[1] + radius)]
    if kind == "arc":
        return arc_points(*(xy(sexpr.child(node, key), what) for key in ("start", "mid", "end")))
    if kind in ("poly", "curve"):
        points = []
        for part in (sexpr.child(node, "pts") or [])[1:]:
            if sexpr.head(part) == "xy":
                points.append(xy(part, what))
            elif sexpr.head(part) == "arc":
                points += arc_points(*(xy(sexpr.child(part, key), what) for key in ("start", "mid", "end")))
        return points
    return []


def placement(footprint: list, what: str) -> Tuple[float, float, float]:
    at = sexpr.child(footprint, "at")
    x, y = xy(at, what)
    return x, y, number(at, 3, what) if len(at) > 3 else 0.0


def placed(point: Tuple[float, float], at: Tuple[float, float, float]) -> Tuple[float, float]:
    """A footprint's own point in board coordinates, turned as KiCad turns it."""
    x, y, angle = at
    cos, sin = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    return x + point[0] * cos + point[1] * sin, y - point[0] * sin + point[1] * cos


def on_layer(node: list, layer: str) -> bool:
    found = sexpr.child(node, "layer")
    return found is not None and len(found) > 1 and str(found[1]) == layer


def outline_bounds(layout: list) -> Optional[Tuple[float, float, float, float]]:
    """The bounds of every shape on the edge layer, the board's outline, or None when it holds none."""
    points: List[Tuple[float, float]] = []
    for node in layout[1:]:
        if sexpr.head(node).startswith("gr_") and on_layer(node, "Edge.Cuts"):
            points += shape_points(node, "a board outline shape")
        elif sexpr.head(node) == "footprint":
            at = placement(node, "a footprint")
            for part in node[1:]:
                if sexpr.head(part).startswith("fp_") and on_layer(part, "Edge.Cuts"):
                    points += [placed(point, at) for point in shape_points(part, "a footprint's outline shape")]
    if not points:
        return None
    return (min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points))


def reference(footprint: list) -> str:
    for node in sexpr.children(footprint, "property"):
        if len(node) > 2 and str(node[1]) == "Reference":
            return str(node[2])
    for node in sexpr.children(footprint, "fp_text"):
        if len(node) > 2 and str(node[1]) == "reference":
            return str(node[2])
    return ""


def footprint_bounds(footprint: list) -> Tuple[float, float, float, float]:
    """The bounds of a footprint's shapes and pads on the board."""
    at = placement(footprint, f"the footprint {reference(footprint) or '?'}")
    what = f"the footprint {reference(footprint) or '?'}"
    points = [at[:2]]
    for part in footprint[1:]:
        if sexpr.head(part).startswith("fp_"):
            points += [placed(point, at) for point in shape_points(part, what)]
        elif sexpr.head(part) == "pad":
            centre = placed(xy(sexpr.child(part, "at"), f"a pad of {what}"), at)
            size = sexpr.child(part, "size")
            reach = math.hypot(number(size, 1, f"a pad of {what}"), number(size, 2, f"a pad of {what}")) / 2 \
                if size is not None and len(size) > 2 else 0.0
            points += [(centre[0] - reach, centre[1] - reach), (centre[0] + reach, centre[1] + reach)]
    return (min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points))


def union(boxes) -> Tuple[float, float, float, float]:
    boxes = list(boxes)
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def grown(box, margin: float) -> Tuple[float, float, float, float]:
    return box[0] - margin, box[1] - margin, box[2] + margin, box[3] + margin


def pads(footprint: list, table: Dict[str, str]) -> List[Tuple[str, str]]:
    """Each of a footprint's pads as its (net, pin type)."""
    found = []
    for pad in sexpr.children(footprint, "pad"):
        kind = sexpr.child(pad, "pintype")
        found.append((locked_copper.item_net(pad, table, f"a pad of {reference(footprint) or '?'}"),
                      str(kind[1]).split("+")[0] if kind is not None and len(kind) > 1 else ""))
    return found


def natural(text: str):
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", text)]


def circuits(layout: list) -> List[dict]:
    """Each integrated circuit, a footprint whose reference begins with U, with its supply nets and the parts on them.

    Its supply nets are the nets on its pads typed as power input or power
    output; the parts on them are the two-pad parts with both pads on those
    nets, the decoupling pattern of one rail and one return.
    """
    table = locked_copper.net_table(layout)
    footprints = [node for node in layout[1:] if sexpr.head(node) == "footprint"]
    found = []
    for footprint in footprints:
        name = reference(footprint)
        if not name.startswith("U"):
            continue
        supply = sorted({net for net, kind in pads(footprint, table) if net and kind in ("power_in", "power_out")})
        parts = []
        for other in footprints:
            held = pads(other, table)
            if other is not footprint and supply and len(held) == 2 and all(net in supply for net, _ in held):
                parts.append(other)
        side = sexpr.child(footprint, "layer")
        found.append({
            "reference": name,
            "side": "bottom" if side is not None and len(side) > 1 and str(side[1]) == "B.Cu" else "top",
            "supply_nets": supply,
            "parts": sorted((reference(part) for part in parts), key=natural),
            "bounds": union(footprint_bounds(node) for node in [footprint] + parts),
        })
    return sorted(found, key=lambda circuit: natural(circuit["reference"]))


def minimums(project: dict, path: str) -> Tuple[Optional[Tuple[float, float]], List[Tuple[str, str]]]:
    """The board's minimum track width and minimum clearance from its design rules, or why either is missing."""
    rules = board_check.setting(project, "board", "design_settings", "rules")
    rules = rules if isinstance(rules, dict) else {}
    figures, refusals = [], []
    for key, what in (("min_track_width", "minimum track width"), ("min_clearance", "minimum clearance")):
        value = rules.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            said = "states none" if value is None else f"states {json.dumps(value)}"
            refusals.append((f"{path} board.design_settings.rules.{key}",
                             f"the board's design rules {said} for its {what}, and the views' resolution is three "
                             f"pixels across the smaller of its minimum track width and minimum clearance; set the "
                             f"{what} in Board Setup to the manufacturer's figure"))
        else:
            figures.append(float(value))
    return (tuple(figures) if not refusals else None), refusals


def only_nets(layout: list, nets: Set[str]) -> list:
    """The board holding only the tracks, arcs, vias, zones, pads and copper shapes on `nets`, fills as they are."""
    table = locked_copper.net_table(layout)

    def ours(node) -> bool:
        return bool(sexpr.children(node, "net")) and locked_copper.item_net(node, table, "an item") in nets

    kept = [layout[0]]
    for node in layout[1:]:
        kind = sexpr.head(node)
        if not isinstance(node, list) or kind in HEADER_FORMS:
            kept.append(node)
        elif kind in COPPER_FORMS or kind.startswith("gr_"):
            if ours(node):
                kept.append(node)
        elif kind == "footprint":
            parts = [part for part in node[1:] if sexpr.head(part) in ("pad", "zone") or sexpr.head(part).startswith("fp_")]
            mine = [part for part in parts if ours(part)]
            if mine:
                kept.append([node[0]] + [part for part in node[1:] if not isinstance(part, list)
                                         or sexpr.head(part) in ("layer", "uuid", "at")] + mine)
    return kept


def net_facts(layout: list, path: str, classes: Dict[str, Set[str]]) -> List[dict]:
    """Every net on the board with its track width range, via count, zones and classes."""
    items = locked_copper.copper(layout, path)
    facts = []
    for net in sorted(board_check.layout_nets(layout), key=natural):
        widths = [item["width"] for item in items if item["net"] == net and item["kind"] in ("track", "arc")]
        facts.append({
            "net": net,
            "classes": [name for name in classes if net in classes[name]],
            "track_width_mm": {"min": min(widths) / 1e6, "max": max(widths) / 1e6} if widths else None,
            "vias": sum(1 for item in items if item["net"] == net and item["kind"] == "via"),
            "zones": [{"layers": item["layers"]} for item in items if item["net"] == net and item["kind"] == "zone"],
        })
    return facts


def unquoted(text: str) -> str:
    return re.sub(r"\\(.)", r"\1", str(text))


def quoted(text: str) -> sexpr.Quoted:
    return sexpr.Quoted(text.replace("\\", "\\\\").replace('"', '\\"'))


def in_place(path: str, folder: str) -> str:
    """A model path as KiCad finds it for the design in `folder`, written out in full where the folder anchors it.

    KiCad reads ${KIPRJMOD} as the design's folder, and looks first in that
    folder for a path that names no variable, alias or scheme; a copy of the
    design elsewhere finds the same file only when those are written out.
    """
    anchored = re.match(r"\$[{(]KIPRJMOD[)}]", path)
    if anchored:
        return os.path.abspath(folder) + path[anchored.end():]
    if path and not path.startswith(("$", ":")) and "://" not in path and not os.path.isabs(path):
        candidate = os.path.join(os.path.abspath(folder), path)
        if os.path.exists(candidate):
            return candidate
    return path


def stage(board: str, project: str, work: str) -> Tuple[str, Dict[str, str]]:
    """A copy of the design in a folder of `work` that reads as the design does in place.

    The layout, its project file and its custom rules keep the design's own
    names, so a text variable naming the project or the file reads as it does in
    place, and every model path the design's folder anchors is written out in
    full. Returns the copy's layout and, for each model path written out, the
    path as the design writes it.
    """
    folder = os.path.join(work, "design")
    os.makedirs(folder)
    layout = locked_copper.read_layout(board)
    source = os.path.dirname(os.path.abspath(board))
    written: Dict[str, str] = {}
    for footprint in sexpr.children(layout, "footprint"):
        for model in sexpr.children(footprint, "model"):
            if len(model) > 1 and isinstance(model[1], str):
                path = unquoted(model[1])
                found = in_place(path, source)
                if found != path:
                    model[1] = quoted(found)
                    written[found] = path
    staged = os.path.join(folder, os.path.basename(board))
    with open(staged, "w", encoding="utf-8") as handle:
        handle.write(sexpr.dump(layout) + "\n")
    shutil.copy2(project, os.path.join(folder, os.path.basename(project)))
    rules = os.path.splitext(board)[0] + ".kicad_dru"
    if os.path.exists(rules):
        shutil.copy2(rules, os.path.join(folder, os.path.basename(rules)))
    return staged, written


def glb_names(path: str) -> Set[str]:
    """The names of the nodes in a binary glTF file, which KiCad gives the reference of each part it drew."""
    try:
        with open(path, "rb") as handle:
            data = handle.read()
        length, kind = struct.unpack("<I4s", data[12:20])
        if data[:4] != b"glTF" or kind != b"JSON":
            raise ValueError("not a binary glTF file")
        nodes = json.loads(data[20:20 + length]).get("nodes", [])
    except (OSError, ValueError, struct.error) as error:
        raise Unreadable(f"KiCad's three-dimensional export {path} cannot be read ({error})") from error
    return {str(node["name"]) for node in nodes if isinstance(node, dict) and "name" in node}


def left_out_in_3d(layout: list, said: str, drawn: Set[str], written: Dict[str, str]) -> List[dict]:
    """Each part the three-dimensional views leave out or draw without a model, and why.

    `said` is what KiCad reported loading the board's models, `drawn` the
    references of the parts it drew any model for, and `written` the model
    paths written out in full, mapped back to the paths the design writes.
    """
    missing: Dict[str, List[str]] = {}
    for name, why in MODEL_NOT_ADDED.findall(said):
        for full, original in written.items():
            why = why.replace(full, original)
        missing.setdefault(name, []).append(why.strip())
    found = []
    for footprint in (node for node in layout[1:] if sexpr.head(node) == "footprint"):
        name = reference(footprint) or "?"
        attributes = sexpr.child(footprint, "attr")
        models = sexpr.children(footprint, "model")
        hidden = [model for model in models if "hide" in model[2:] or any(
            sexpr.head(part) == "hide" and len(part) > 1 and str(part[1]) == "yes" for part in model[2:])]
        if attributes is not None and "dnp" in [str(part) for part in attributes[1:]]:
            found.append({"reference": name, "reason": "not populated",
                          "detail": "marked do not populate, so the render leaves it out"})
        elif not models:
            found.append({"reference": name, "reason": "no model", "detail": "it declares no model"})
        elif len(hidden) == len(models):
            found.append({"reference": name, "reason": "model hidden", "detail": "the design hides its model"})
        elif name in missing:
            found.append({"reference": name, "reason": "model not found",
                          "detail": "KiCad cannot find its model: " + "; ".join(missing.pop(name))})
        elif name not in drawn:
            found.append({"reference": name, "reason": "model not found",
                          "detail": "KiCad drew none of its models: "
                                    + ", ".join(unquoted(model[1]) for model in models if len(model) > 1)})
    return sorted(found, key=lambda part: natural(part["reference"]))


def rule_areas(layout: list, carried: Sequence[str]) -> List[dict]:
    """Every rule area on the board, its own or a footprint's, with its layers, restrictions and outline."""
    zones = [node for node in layout[1:] if sexpr.head(node) == "zone"]
    zones += [part for node in layout[1:] if sexpr.head(node) == "footprint" for part in node[1:]
              if sexpr.head(part) == "zone"]
    found = []
    for zone in zones:
        keepout = sexpr.child(zone, "keepout")
        if keepout is None:
            continue
        layers = []
        for form in sexpr.children(zone, "layer") + sexpr.children(zone, "layers"):
            for name in form[1:]:
                layers += [layer for layer in expand(str(name), carried) if layer not in layers]
        refused = [words for key, words in RULE_RESTRICTIONS
                   if (sexpr.child(keepout, key) or [None, None])[1:2] == ["not_allowed"]]
        placement = sexpr.child(zone, "placement")
        placing = placement is not None and (sexpr.child(placement, "enabled") or [None, None])[1:2] == ["yes"]
        rules = [f"no {', '.join(refused[:-1])}{' or ' if len(refused) > 1 else ''}{refused[-1]}"] if refused else []
        rules += ["a placement area"] if placing else []
        outlines = []
        for polygon in sexpr.children(zone, "polygon"):
            points = []
            for part in (sexpr.child(polygon, "pts") or [])[1:]:
                if sexpr.head(part) == "xy":
                    points.append(xy(part, "a rule area's outline"))
                elif sexpr.head(part) == "arc":
                    points += arc_points(*(xy(sexpr.child(part, key), "a rule area's outline")
                                           for key in ("start", "mid", "end")))
            if points:
                outlines.append(points)
        if not outlines:
            continue
        bounds = (min(p[0] for o in outlines for p in o), min(p[1] for o in outlines for p in o),
                  max(p[0] for o in outlines for p in o), max(p[1] for o in outlines for p in o))
        named = sexpr.child(zone, "name")
        found.append({"name": unquoted(named[1]) if named is not None and len(named) > 1 and str(named[1]) else
                      f"unnamed, at {covers(bounds)}", "layers": layers, "rules": rules or ["no restriction"],
                      "outlines": outlines, "bounds_mm": {"x0": bounds[0], "y0": bounds[1], "x1": bounds[2],
                                                         "y1": bounds[3]}})
    return found


def side_layers(wanted: Sequence[str], plotted) -> Tuple[List[str], List[str]]:
    """The layers a view wants that the board carries, in order, and those it does not carry."""
    return [layer for layer in wanted if layer in plotted], [layer for layer in wanted if layer not in plotted]


def shared_nets(classes: Sequence[str], membership: Dict[str, Set[str]]) -> Dict[str, List[str]]:
    """Each net in more than one of the critical classes, with those classes in the order they are named."""
    shared: Dict[str, List[str]] = {}
    for name in classes:
        for net in membership[name]:
            shared.setdefault(net, []).append(name)
    return {net: names for net, names in sorted(shared.items(), key=lambda item: natural(item[0])) if len(names) > 1}


# --- Drawing ---------------------------------------------------------------------


def layer_colours(layers: Sequence[str]) -> Dict[str, Tuple[str, str]]:
    """A colour for every layer, the named ones fixed and the rest taken in turn."""
    colours, spare = {}, list(OTHER_COLOURS)
    for index, name in enumerate(layer for layer in layers if layer not in LAYER_COLOURS):
        colours[name] = spare[index % len(spare)]
    return dict(colours, **{name: LAYER_COLOURS[name] for name in layers if name in LAYER_COLOURS})


def drawing(svg_path: str, colour: str, opacity: float = 1.0) -> str:
    """The body of a layer KiCad plotted, recoloured: its copper in `colour` and its holes in the background."""
    with open(svg_path, encoding="utf-8") as handle:
        text = handle.read()
    opening = text.index("<svg")
    body = text[text.index(">", opening) + 1:text.rindex("</svg>")]
    body = re.sub(r"#[fF]{6}\b", BACKGROUND, body)
    body = re.sub(r"#(?![fF]{6}\b)[0-9A-Fa-f]{6}\b", colour, body)
    return f'<g opacity="{opacity}">{body}</g>' if opacity < 1 else f"<g>{body}</g>"


def escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def wrapped(caption: str, width: int) -> List[str]:
    """The caption's lines at the width of the image, broken between words."""
    room = max(10, int((width - 2 * CAPTION_PAD_PX) // CHAR_PX))
    lines, line = [], ""
    for word in caption.split(" "):
        while len(word) > room:
            if line:
                lines.append(line)
                line = ""
            lines.append(word[:room])
            word = word[room:]
        if line and len(line) + 1 + len(word) > room:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}" if line else word
    return lines + ([line] if line else [])


def caption_height(caption: str, width: int) -> int:
    return len(wrapped(caption, width)) * LINE_PX + 2 * CAPTION_PAD_PX


def fits(width: int, height: int) -> bool:
    """Whether a reviewing model reads an image of this size without downsampling it."""
    return max(width, height) <= LONG_EDGE_PX and math.ceil(width / PATCH_PX) * math.ceil(height / PATCH_PX) <= PATCHES


def caption_svg(caption: str, width: int, top: int) -> str:
    lines = wrapped(caption, width)
    spans = "".join(f'<tspan x="{CAPTION_PAD_PX}" y="{top + CAPTION_PAD_PX + (index + 1) * LINE_PX - 5}">'
                    f"{escape(line)}</tspan>" for index, line in enumerate(lines))
    return (f'<line x1="0" y1="{top + 0.5}" x2="{width}" y2="{top + 0.5}" stroke="{RULE_COLOUR}" stroke-width="1"/>'
            f'<text font-family="{FONT_FAMILY}" font-size="{FONT_PX}" fill="{CAPTION_COLOUR}" '
            f'xml:space="preserve">{spans}</text>')


def mm_text(value: float) -> str:
    return board_check.coordinate(value)


def scale_text(scale: float) -> str:
    return f"{mm_text(scale)} px/mm"


def shown(region: Tuple[float, float, float, float], scale: float) -> Tuple[float, float, float, float]:
    """The region a view shows: one narrower than the narrowest image is widened about its centre, so the view
    shows more of the board rather than a squeezed caption."""
    x0, y0, x1, y1 = region
    if math.ceil((x1 - x0) * scale - 1e-9) >= MIN_WIDTH_PX:
        return region
    middle = (x0 + x1) / 2
    return middle - MIN_WIDTH_PX / scale / 2, y0, middle + MIN_WIDTH_PX / scale / 2, y1


def tiles(region: Tuple[float, float, float, float], scale: float, caption_for) -> List[dict]:
    """The region as it is shown cut into the fewest equal tiles that each fit, with their captions, at `scale`
    pixels per millimetre."""
    x0, y0, x1, y1 = shown(region, scale)
    width, height = max(MIN_WIDTH_PX, math.ceil((x1 - x0) * scale - 1e-9)), math.ceil((y1 - y0) * scale - 1e-9)
    count = 0
    while True:
        count += 1
        for columns in range(1, count + 1):
            if count % columns:
                continue
            rows = count // columns
            across, down = math.ceil(width / columns), math.ceil(height / rows)
            if columns > 1 and across < MIN_WIDTH_PX:
                continue
            planned = []
            for row in range(rows):
                for column in range(columns):
                    box = (x0 + column * across / scale, y0 + row * down / scale,
                           x0 + (column + 1) * across / scale, y0 + (row + 1) * down / scale)
                    tile = {"region": box, "row": row + 1, "column": column + 1, "rows": rows, "columns": columns,
                            "content": (across, down)}
                    tile["caption"] = caption_for(tile)
                    tile["size"] = (across, down + caption_height(tile["caption"], across))
                    planned.append(tile)
            if all(fits(*tile["size"]) for tile in planned):
                return planned
        if count > 10000:
            raise Unreadable(f"the region {region} cannot be cut into tiles that fit at {scale_text(scale)}")


def covers(region) -> str:
    x0, y0, x1, y1 = region
    return f"board x {mm_text(x0)} to {mm_text(x1)} mm, y {mm_text(y0)} to {mm_text(y1)} mm"


def colour_list(entries: Sequence[Tuple[str, str]]) -> str:
    return ", ".join(f"{name} {colour}" for name, colour in entries)


def named(names: Sequence[str]) -> str:
    """The names, up to as many as a caption carries, the rest left to the index."""
    if len(names) <= CAPTION_NAMES:
        return ", ".join(names)
    return f"{', '.join(names[:CAPTION_NAMES])} and {len(names) - CAPTION_NAMES} more, which the index names"


def on_stack(areas: List[dict], stack: Sequence[str], region) -> List[dict]:
    """The rule areas on any of the layers in `stack` that reach into `region`."""
    x0, y0, x1, y1 = region
    return [area for area in areas if set(area["layers"]) & set(stack) and area["bounds_mm"]["x0"] < x1
            and area["bounds_mm"]["x1"] > x0 and area["bounds_mm"]["y0"] < y1 and area["bounds_mm"]["y1"] > y0]


def rule_area_drawing(areas: List[dict], scale: float) -> str:
    """The rule areas as dashed, hatched outlines in board coordinates, their strokes sized in pixels at `scale`."""
    if not areas:
        return ""
    px = 1 / scale
    shapes = "".join(f'<polygon points="{" ".join(f"{x},{y}" for x, y in outline)}" fill="url(#rule-area-hatch)" '
                     f'stroke="{RULE_AREA[0]}" stroke-width="{2 * px}" stroke-dasharray="{8 * px} {5 * px}"/>'
                     for area in areas for outline in area["outlines"])
    return (f'<defs><pattern id="rule-area-hatch" patternUnits="userSpaceOnUse" width="{10 * px}" '
            f'height="{10 * px}" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="{10 * px}" '
            f'stroke="{RULE_AREA[0]}" stroke-width="{1.5 * px}"/></pattern></defs>{shapes}')


def rule_area_field(areas: List[dict]) -> str:
    return (f"rule areas, which KiCad does not plot, drawn as {RULE_AREA[1]} dashed hatched outlines: "
            + named([f"{area['name']} on {', '.join(area['layers'])} ({'; '.join(area['rules'])})" for area in areas]))


def rule_area_entries(areas: List[dict]) -> List[dict]:
    return [{"name": area["name"], "layers": area["layers"], "rules": area["rules"], "bounds_mm": area["bounds_mm"]}
            for area in areas]


def absent_field(absent: Sequence[str]) -> str:
    return f"{', '.join(absent)} not carried by the board, so not drawn"


class Renderer:
    """Writes each image of the views and keeps the index of them."""

    def __init__(self, resvg: str, work: str, out: str, scale: float, notes: List[str]):
        self.resvg, self.work, self.out, self.scale = resvg, work, out, scale
        #: What every caption carries besides its own fields: what KiCad drew differently from the design.
        self.notes = notes
        self.images: List[dict] = []
        self.names: Set[str] = set()

    def stem(self, wanted: str) -> str:
        stem = re.sub(r"[^A-Za-z0-9._+-]+", "_", wanted).strip("._") or "view"
        candidate, index = stem, 1
        while candidate in self.names:
            index += 1
            candidate = f"{stem}-{index}"
        self.names.add(candidate)
        return candidate

    def raster(self, svg_text: str, name: str) -> None:
        svg = os.path.join(self.work, name + ".svg")
        with open(svg, "w", encoding="utf-8") as handle:
            handle.write(svg_text)
        rasterise(self.resvg, svg, os.path.join(self.out, name + ".png"))

    def flat(self, wanted: str, region, drawings: str, entry: dict, describe) -> None:
        """A two-dimensional view of `region`, tiled where it does not fit, each tile with its caption."""
        stem = self.stem(wanted)

        def caption_for(tile):
            fields = describe() + [scale_text(self.scale), covers(tile["region"])]
            if tile["rows"] * tile["columns"] > 1:
                fields.append(f"tile row {tile['row']} of {tile['rows']}, column {tile['column']} of {tile['columns']}")
            return " | ".join(fields + self.notes)

        planned = tiles(region, self.scale, caption_for)
        for tile in planned:
            name = stem if len(planned) == 1 else f"{stem}-r{tile['row']}c{tile['column']}"
            across, down = tile["content"]
            width, height = tile["size"]
            x0, y0, x1, y1 = tile["region"]
            self.raster(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
                        f'viewBox="0 0 {width} {height}"><rect width="{width}" height="{height}" fill="{BACKGROUND}"/>'
                        f'<svg x="0" y="0" width="{across}" height="{down}" viewBox="{x0} {y0} {x1 - x0} {y1 - y0}" '
                        f'preserveAspectRatio="none" overflow="hidden">{drawings}</svg>'
                        f'{caption_svg(tile["caption"], width, down)}</svg>', name)
            self.images.append(dict(entry, file=name + ".png", caption=tile["caption"],
                                    scale_px_per_mm=self.scale,
                                    region_mm={"x0": x0, "y0": y0, "x1": x1, "y1": y1},
                                    content_px={"width": across, "height": down},
                                    size_px={"width": width, "height": height},
                                    tile={"row": tile["row"], "column": tile["column"], "rows": tile["rows"],
                                          "columns": tile["columns"]}))

    def solid(self, wanted: str, raw: str, entry: dict, box: Tuple[int, int, int], fields: List[str]) -> None:
        """A three-dimensional render placed on the dark background with its caption, within the size limit."""
        name = self.stem(wanted)
        across, down, band = box
        height = down + band
        caption = " | ".join(fields + [f"image {across} x {height} px"])
        width, shown = png_size(raw)
        ratio = min(1.0, across / width, down / shown)
        w, h = width * ratio, shown * ratio
        self.raster(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                    f'width="{across}" height="{height}" viewBox="0 0 {across} {height}">'
                    f'<rect width="{across}" height="{height}" fill="{BACKGROUND}"/>'
                    f'<image x="{(across - w) / 2}" y="{(down - h) / 2}" width="{w}" height="{h}" '
                    f'xlink:href="{escape(os.path.basename(raw))}" href="{escape(os.path.basename(raw))}"/>'
                    f'{caption_svg(caption, across, down)}</svg>', name)
        self.images.append(dict(entry, file=name + ".png", caption=caption,
                                render_px={"width": across, "height": down},
                                size_px={"width": across, "height": height}))


def solid_box(aspect: float, captions: List[List[str]]) -> Tuple[int, int, int]:
    """The largest render of the board's aspect, its width, height and caption band, that fits within the size limit.

    The band is the deepest any of the captions needs at that width, so every
    three-dimensional view is the same size; a board too tall to fit at the
    narrowest width is rendered shorter, and KiCad's render is placed within it.
    """
    def band(across: int) -> int:
        return max(caption_height(" | ".join(fields + ["image 0000 x 0000 px"]), across) for fields in captions)

    for across in range(LONG_EDGE_PX, MIN_WIDTH_PX - 1, -8):
        down = max(1, round(across / aspect))
        if fits(across, down + band(across)):
            return across, down, band(across)
    down = LONG_EDGE_PX
    while not fits(MIN_WIDTH_PX, down + band(MIN_WIDTH_PX)):
        down -= 8
        if down < PROBE_PX:
            raise Unreadable("the three-dimensional views' captions leave no room for the render within the size limit")
    return MIN_WIDTH_PX, down, band(MIN_WIDTH_PX)


def reaches_frame(path: str, clear: int) -> bool:
    """Whether anything KiCad rendered on a transparent background lies within `clear` pixels of the image's edge."""
    width, height, rows = read_png(path)
    return any(rows[y][x][3] for y in range(height) for x in range(width)
               if min(x, y, width - 1 - x, height - 1 - y) < clear)


def render(kicad_cli: str, work: str, board_file: str, how: List[str], size: Tuple[int, int], zoom: float,
           name: str, board: str) -> Tuple[str, str]:
    """KiCad's render of the board at `size` and `zoom` on a transparent background; its path and what KiCad said."""
    raw = os.path.join(work, name)
    if os.path.exists(raw):
        os.remove(raw)
    said = kicad([kicad_cli, "pcb", "render", *how, "-w", str(size[0]), "-h", str(size[1]), "--zoom", f"{zoom:.6g}",
                  "--background", "transparent", "-o", raw, board_file], work, f"render {board} in three dimensions")
    if not os.path.exists(raw):
        raise Unreadable(f"KiCad wrote no three-dimensional render of {board}")
    return raw, said


def framing(kicad_cli: str, work: str, board_file: str, how: List[str], aspect: float, board: str,
            direction: str) -> Tuple[float, str]:
    """The largest zoom, no more than 1, at which no part of the board reaches the render's frame.

    KiCad frames a render on the board, so a tall part seen at an angle can
    run out of the image; the view is zoomed out until it does not. The zoom is
    found on a small render, which KiCad frames the same way at any size.
    """
    least = 4 * PROBE_CLEAR_PX
    size = (PROBE_PX, max(least, round(PROBE_PX / aspect))) if aspect >= 1 else \
        (max(least, round(PROBE_PX * aspect)), PROBE_PX)
    zoom, said = 1.0, ""
    for _ in range(ZOOM_TRIES):
        probe, heard = render(kicad_cli, work, board_file, how, size, zoom, "probe.png", board)
        said += heard
        if not reaches_frame(probe, PROBE_CLEAR_PX):
            return zoom, said
        zoom *= ZOOM_STEP
    raise Unreadable(f"KiCad's three-dimensional render of {board} {direction} still reaches the edge of the image "
                     f"zoomed out to {zoom / ZOOM_STEP:.3g}, so no view of it would show the whole board")


# --- The command --------------------------------------------------------------------


def views(board: str, project: str, classes: Sequence[str], out: str, kicad_cli: str, resvg: str, stream) -> int:
    """Render every view of the board into `out`; the exit status."""
    refusals = []
    folder = locked_copper.design_folder(out, board)
    if folder is not None:
        refusals.append((out, "the views are working files and are never kept in a design's folder, where they could "
                              f"be committed and copied as part of the design; {folder} holds a design's project file, "
                              "so write them outside it"))
    if os.path.lexists(out) and not os.path.isdir(out):
        refusals.append((out, "the output folder is a file; name a new folder, or an empty one"))
    elif os.path.isdir(out) and os.listdir(out):
        refusals.append((out, "the output folder already holds files, which an index of these views would not "
                              "describe; name a new folder, or an empty one"))
    why = locked_copper.own_project(board, project)
    if why is not None:
        refusals.append((project, why))
    if refusals:
        return locked_copper.refused(refusals, "REFUSED | no views were written", stream)
    layout, refusals = locked_copper.named_classes(board, project, classes)
    settings = locked_copper.read_project(project)
    figures, missing = minimums(settings, project)
    refusals += missing
    carried = layer_table(layout)
    refusals += [(layer, f"the board carries no {layer} layer, and every board carries both outer copper layers, "
                         "both masks, both pastes, both silkscreens and an edge layer holding its outline; add it in "
                         "Board Setup") for layer in REQUIRED_LAYERS if layer not in carried]
    outline = outline_bounds(layout) if "Edge.Cuts" in carried else None
    if "Edge.Cuts" in carried and outline is None:
        refusals.append(("Edge.Cuts", "the board's edge layer holds no outline, so the board has no extent to draw; "
                                      "draw the board outline on Edge.Cuts"))
    if refusals:
        return locked_copper.refused(refusals, "REFUSED | no views were written", stream)
    probed = list(classes) + sorted(name for name in locked_copper.defined_classes(settings, layout)
                                    if name not in classes and not locked_copper.UNWRITABLE & set(name))
    membership = locked_copper.members(kicad_cli, board, project, layout, probed)
    refusals = locked_copper.empty_classes({name: membership[name] for name in classes})
    if refusals:
        return locked_copper.refused(refusals, "REFUSED | no views were written", stream)

    smallest = min(figures)
    scale = PIXELS_PER_FEATURE / smallest
    copper = copper_order(carried)
    with tempfile.TemporaryDirectory(prefix="board-views-") as work:
        ready = os.path.join(work, "out")
        os.makedirs(ready)
        copy, written = stage(board, project, work)
        copy = os.path.relpath(copy, work)
        report, why = board_check.run_kicad([kicad_cli, "pcb", "drc", "--refill-zones", "--save-board", "--format",
                                             "json", copy], work)
        if report is None:
            raise Unreadable(f"KiCad could not refill and save the zones of a copy of {board}: {why}")
        refilled = locked_copper.read_layout(os.path.join(work, copy))
        held = held_layers(refilled, carried)
        drawn = [layer for layer in carried if layer in REQUIRED_LAYERS or layer in copper or layer in held]
        drawn = copper + [layer for layer in drawn if layer not in copper]
        colours = layer_colours(carried)
        fonts: Dict[str, str] = {}
        plotted: Dict[str, str] = {}
        for index, layer in enumerate(drawn):
            plotted[layer] = plot(kicad_cli, work, copy, layer, f"layer-{index}.svg", board, fonts)
        for layer in ("F.Fab", "B.Fab", "F.CrtYd", "B.CrtYd"):
            if layer in carried and layer not in plotted:
                plotted[layer] = plot(kicad_cli, work, copy, layer, f"extra-{layer}.svg", board, fonts)
        areas = rule_areas(refilled, carried)
        notes = ["fonts KiCad could not find, their text drawn in another: "
                 + named([f"{font} drawn in {instead}" for font, instead in sorted(fonts.items())])] if fonts else []
        region = shown(grown(outline, BOARD_MARGIN_MM), scale)
        renderer = Renderer(resvg, work, ready, scale, notes)
        faint = "".join(drawing(plotted[layer], FAINT[0], FAINT[2]) for layer in reversed(copper)) \
            + drawing(plotted["Edge.Cuts"], FAINT[0], FAINT[2])
        absent: List[str] = []

        def marked(entry: dict, stack: Sequence[str], missing: Sequence[str],
                   seen=region) -> Tuple[dict, str, List[str]]:
            """The entry, drawing and caption fields of a view's rule areas and the layers the board lacks."""
            here = on_stack(areas, stack, seen)
            fields = ([rule_area_field(here)] if here else []) + ([absent_field(missing)] if missing else [])
            absent.extend(layer for layer in missing if layer not in absent)
            return (dict(entry, rule_areas=rule_area_entries(here), absent_layers=list(missing)),
                    rule_area_drawing(here, scale), fields)

        for layer in drawn:
            entry, areas_drawn, fields = marked({"view": "layer",
                                                 "layers": [{"name": layer, "colour": colours[layer][1]}]}, [layer], [])
            renderer.flat(f"layer-{layer}", region, drawing(plotted[layer], colours[layer][0]) + areas_drawn, entry,
                          lambda layer=layer, fields=fields: [f"layer {layer}", f"drawn in {colours[layer][1]}"]
                          + fields)

        for side, prefix in (("top", "F"), ("bottom", "B")):
            stack, missing = side_layers(("Edge.Cuts", f"{prefix}.Fab", f"{prefix}.CrtYd", f"{prefix}.SilkS"), plotted)
            entries = [(layer, colours[layer][1]) for layer in stack]
            entry, areas_drawn, fields = marked(
                {"view": "assembly", "side": side,
                 "layers": [{"name": name, "colour": colour} for name, colour in entries]}, stack, missing)
            renderer.flat(f"assembly-{side}", region, "".join(drawing(plotted[layer], colours[layer][0])
                                                              for layer in stack) + areas_drawn, entry,
                          lambda side=side, entries=entries, fields=fields: [
                              f"assembly view of the {side} side, seen from the top",
                              f"layers {colour_list(entries)}"] + fields)

        critical = {}
        for name in classes:
            for net in membership[name]:
                critical.setdefault(net, []).append(name)
        net_drawings: Dict[str, Dict[str, str]] = {}
        for index, net in enumerate(sorted(critical, key=natural)):
            copy_name = f"net-{index}.kicad_pcb"
            with open(os.path.join(work, copy_name), "w", encoding="utf-8") as handle:
                handle.write(sexpr.dump(only_nets(refilled, {net})) + "\n")
            net_drawings[net] = {layer: plot(kicad_cli, work, copy_name, layer, f"net-{index}-{layer}.svg", board,
                                             fonts) for layer in copper}
            entries = [(layer, colours[layer][1]) for layer in copper]
            renderer.flat(f"net-{net}", region,
                          faint + "".join(drawing(net_drawings[net][layer], colours[layer][0])
                                          for layer in reversed(copper)),
                          {"view": "net", "net": net, "classes": critical[net],
                           "layers": [{"name": name, "colour": colour} for name, colour in entries],
                           "beneath": f"the whole board's copper and edge in {FAINT[1]}"},
                          lambda net=net, entries=entries: [
                              f"net {net}", f"class {', '.join(critical[net])}",
                              f"its copper on {colour_list(entries)}",
                              f"over the whole board's copper and edge in {FAINT[1]}"])

        class_colours = {name: CLASS_COLOURS[index % len(CLASS_COLOURS)] for index, name in enumerate(classes)}
        mapped = "".join(drawing(net_drawings[net][layer], class_colours[name][0])
                         for name in classes for net in sorted(membership[name], key=natural)
                         for layer in reversed(copper))
        entries = [(name, class_colours[name][1]) for name in classes]
        shared = shared_nets(classes, membership)
        overlap = ["nets in more than one critical class, drawn in the colour of the class named last: "
                   + named([f"{net} ({', '.join(names)})" for net, names in shared.items()])] if shared else []
        renderer.flat("classes", region, faint + mapped,
                      {"view": "class map", "classes": [{"name": name, "colour": colour} for name, colour in entries],
                       "layers": [{"name": layer} for layer in copper], "shared_nets": shared,
                       "beneath": f"the whole board's copper and edge in {FAINT[1]}"},
                      lambda: ["class map", f"classes {colour_list(entries)}",
                               f"copper on {', '.join(copper)}",
                               f"over the whole board's copper and edge in {FAINT[1]}"] + overlap)

        for circuit in circuits(refilled):
            prefix = "B" if circuit["side"] == "bottom" else "F"
            order = copper if circuit["side"] == "bottom" else list(reversed(copper))
            stack, missing = side_layers(order + [f"{prefix}.Fab", f"{prefix}.SilkS", "Edge.Cuts"], plotted)
            entries = [(layer, colours[layer][1]) for layer in stack]
            declared = bool(circuit["supply_nets"])
            supply = (f"supply nets {', '.join(circuit['supply_nets'])}" if declared else
                      "no supply nets declared: no pad is typed power input or power output")
            parts = (f"parts on them {', '.join(circuit['parts'])}" if circuit["parts"] else
                     "no two-pad part with both pads on them") if declared else "so no parts on supply nets are shown"
            cropped = shown(grown(circuit["bounds"], CROP_MARGIN_MM), scale)
            entry, areas_drawn, fields = marked(
                {"view": "crop", "circuit": circuit["reference"], "side": circuit["side"],
                 "supply_nets_declared": declared, "supply_nets": circuit["supply_nets"], "parts": circuit["parts"],
                 "layers": [{"name": name, "colour": colour} for name, colour in entries]}, stack, missing, cropped)
            renderer.flat(f"crop-{circuit['reference']}", cropped,
                          "".join(drawing(plotted[layer], colours[layer][0]) for layer in stack) + areas_drawn, entry,
                          lambda circuit=circuit, entries=entries, supply=supply, parts=parts, fields=fields: [
                              f"crop around {circuit['reference']} ({circuit['side']} side)", supply, parts,
                              f"layers {colour_list(entries)}"] + fields)

        glb = os.path.join(work, "models.glb")
        said = kicad([kicad_cli, "pcb", "export", "glb", "--no-dnp", "--no-board-body", "-o", glb, copy], work,
                     f"load the three-dimensional models of {board}")
        unseen = left_out_in_3d(refilled, said, glb_names(glb), written)
        aspect = (outline[2] - outline[0]) / max(outline[3] - outline[1], 1e-6)
        zooms = {}
        for name, how, direction in VIEWS_3D:
            zooms[name], heard = framing(kicad_cli, work, copy, how, aspect, board, direction)
            fonts.update(substituted(heard))
        left_out = []
        for reason, words in (("model not found", "drawn without a model KiCad cannot find"),
                              ("no model", "drawn without a model, declaring none"),
                              ("model hidden", "drawn without a model, the design hiding it"),
                              ("not populated", "not drawn, marked do not populate")):
            these = [part["reference"] for part in unseen if part["reason"] == reason]
            if these:
                left_out.append(f"{words}: {named(these)}")
        fields = {name: [f"three-dimensional view {name}", direction]
                  + ([f"zoomed out to {zooms[name]:.3g} so no part reaches the frame"] if zooms[name] < 1 else [])
                  + (left_out or ["every part drawn with its model"]) + notes
                  for name, _, direction in VIEWS_3D}
        box = solid_box(aspect, list(fields.values()))
        for name, how, direction in VIEWS_3D:
            raw, heard = render(kicad_cli, work, copy, how, box[:2], zooms[name], f"render-{name}.png", board)
            renderer.solid(f"3d-{name}", raw, {"view": "3d", "direction": direction, "zoom": zooms[name]}, box,
                           fields[name])

        facts = net_facts(refilled, board, membership)
        header = {
            "board": os.path.realpath(board),
            "critical_classes": {name: sorted(membership[name], key=natural) for name in classes},
            "resolution": {
                "px_per_mm": scale, "pixels_per_feature": PIXELS_PER_FEATURE,
                "min_track_width_mm": figures[0], "min_clearance_mm": figures[1],
                "rule": "pixels per millimetre = pixels per feature / the smaller of the minimum track width and "
                        "the minimum clearance",
            },
            "image_limit": {"long_edge_px": LONG_EDGE_PX, "patches": PATCHES, "patch_px": PATCH_PX},
            "background": BACKGROUND,
            "fonts_substituted": [{"font": font, "drawn_in": instead} for font, instead in sorted(fonts.items())],
            "layers_not_carried": absent,
            "rule_areas": rule_area_entries(areas),
            "not_in_3d": unseen,
        }
        write_outputs(ready, header, renderer.images, facts)
        os.makedirs(out, exist_ok=True)
        for name in sorted(os.listdir(ready)):
            shutil.move(os.path.join(ready, name), os.path.join(out, name))
    locked_copper.class_lines(classes, membership, stream)
    for font, instead in sorted(fonts.items()):
        print(f"FONT | {font} | KiCad cannot find this font and drew its text in {instead}; the captions and the "
              "index name it", file=stream)
    for layer in absent:
        print(f"LAYER | {layer} | the board does not carry this layer, so the views that show it leave it out; the "
              "captions and the index name it", file=stream)
    for part in unseen:
        if part["reason"] == "model not found":
            print(f"MODEL | {part['reference']} | {part['detail']}, so the three-dimensional views draw it without "
                  "that model; their captions and the index name it", file=stream)
    print(f"RESOLUTION | {scale_text(scale)} | {PIXELS_PER_FEATURE} px across the smaller of the minimum track width "
          f"{mm_text(figures[0])} mm and the minimum clearance {mm_text(figures[1])} mm", file=stream)
    print(f"RESULT | WRITTEN | {len(renderer.images)} images, their index and the per-net fact table | {clean(out)}",
          file=stream)
    return 0


def plot(kicad_cli: str, work: str, board_file: str, layer: str, name: str, board: str, fonts: Dict[str, str]) -> str:
    """One layer of a board in `work` plotted as a vector image in board coordinates; its path.

    Each font KiCad says it substituted is added to `fonts`.
    """
    path = os.path.join(work, name)
    said = kicad([kicad_cli, "pcb", "export", "svg", "--mode-single", "--layers", layer, "--page-size-mode", "1",
                  "--exclude-drawing-sheet", "--black-and-white", "--drill-shape-opt", "2", "-o", path, board_file],
                 work, f"plot {layer} of {board}")
    fonts.update(substituted(said))
    if not os.path.exists(path):
        raise Unreadable(f"KiCad wrote no plot of {layer} of {board}")
    return path


def fact_line(fact: dict) -> str:
    widths = fact["track_width_mm"]
    tracks = (f"tracks {mm_text(widths['min'])} to {mm_text(widths['max'])} mm wide" if widths else "no tracks")
    zones = (f"{len(fact['zones'])} zone{'s' if len(fact['zones']) != 1 else ''} on "
             + "; ".join(" ".join(zone["layers"]) for zone in fact["zones"])) if fact["zones"] else "no zones"
    return " | ".join([f"NET {fact['net']}", f"class {', '.join(fact['classes']) or 'none'}", tracks,
                       f"{fact['vias']} via{'s' if fact['vias'] != 1 else ''}", zones])


def write_outputs(folder: str, header: dict, images: List[dict], facts: List[dict]) -> None:
    resolution = header["resolution"]
    lines = [f"BOARD | {header['board']}",
             f"RESOLUTION | {scale_text(resolution['px_per_mm'])} | {resolution['pixels_per_feature']} px across the "
             f"smaller of the minimum track width {mm_text(resolution['min_track_width_mm'])} mm and the minimum "
             f"clearance {mm_text(resolution['min_clearance_mm'])} mm",
             f"LIMIT | every image within a long edge of {LONG_EDGE_PX} px and {PATCHES} patches of {PATCH_PX} by "
             f"{PATCH_PX} px"]
    lines += [f"CLASS | {name} | {', '.join(nets)}" for name, nets in header["critical_classes"].items()]
    lines += [f"FONT | {font['font']} | not found, so KiCad drew its text in {font['drawn_in']}"
              for font in header["fonts_substituted"]]
    lines += [f"LAYER | {layer} | not carried by the board, so the views that show it leave it out"
              for layer in header["layers_not_carried"]]
    lines += [f"RULE AREA | {area['name']} | on {', '.join(area['layers'])}, {'; '.join(area['rules'])}; KiCad does "
              f"not plot it, so the views draw it as a {RULE_AREA[1]} dashed hatched outline"
              for area in header["rule_areas"]]
    lines += [f"NOT IN 3D | {part['reference']} | {part['detail']}" for part in header["not_in_3d"]]
    lines += [f"IMAGE | {image['file']} | {image['caption']}" for image in images]
    with open(os.path.join(folder, "index.txt"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    with open(os.path.join(folder, "index.json"), "w", encoding="utf-8") as handle:
        json.dump(dict(header, images=images), handle, indent=1)
        handle.write("\n")
    with open(os.path.join(folder, "facts.txt"), "w", encoding="utf-8") as handle:
        handle.write("".join(fact_line(fact) + "\n" for fact in facts))
    with open(os.path.join(folder, "facts.json"), "w", encoding="utf-8") as handle:
        json.dump({"board": header["board"], "nets": facts}, handle, indent=1)
        handle.write("\n")


def main(argv: Optional[List[str]] = None, out=sys.stdout) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--kicad-cli", default="kicad-cli", help="KiCad's command-line tool (default: kicad-cli on the search path)")
    parser.add_argument("--resvg", default="resvg", help="the resvg rasteriser (default: resvg on the search path)")
    parser.add_argument("--board", required=True, help="the layout file (.kicad_pcb)")
    parser.add_argument("--project", required=True, help="the layout's own project file (.kicad_pro)")
    parser.add_argument("--class", dest="classes", action="append", required=True, metavar="NAME",
                        help="a critical net class, as the design names it; give each one")
    parser.add_argument("--out", required=True, help="the folder to write the views into: new or empty, and outside every design's folder")
    args = parser.parse_args(argv)
    try:
        board_check.require_python()
        version = board_check.require_kicad(args.kicad_cli)
        require_resvg(args.resvg)
        with tempfile.TemporaryDirectory(prefix="board-views-kicad-") as home:
            board_check.KICAD_ENVIRONMENT = board_check.isolate_kicad(args.kicad_cli, version, home)
            english(home)
            try:
                return views(args.board, args.project, args.classes, args.out, args.kicad_cli, args.resvg, out)
            finally:
                board_check.KICAD_ENVIRONMENT = None
    except Unreadable as error:
        print(f"UNREADABLE | {clean(str(error))}", file=out)
        print("RESULT | FAIL | the input cannot be read, so no views were written", file=out)
        return 1
    except CannotRun as error:
        print(f"CANNOT RUN | {clean(str(error))}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
