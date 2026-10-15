#!/usr/bin/env python3
"""The placement view: a placed board's parts with each net's connections drawn straight between the pads they join, and the placement's measures.

A placement is judged by the connections it leaves unrouted: short, running
side by side and seldom crossing. A net's connections are the shortest
straight-line tree over the centres of its pads, the minimum spanning tree the
shared board geometry gives and the pre-order check's detour measure is taken
against. Copper already laid is ignored, in the image and in the measures, so a
board measures the same before routing and after it, and a placement changed on
a routed board can be measured again.

The image is drawn from a copy of the board holding its parts and none of its
tracks, arcs, vias or zones: the pads of each outer copper layer, each side's
fabrication, courtyard and silkscreen layers and the edge, with the connections
and the floorplan's regions drawn over them. Its rendering, caption, tiling,
resolution and refusals are the layout review views' own (board_views.py), so
it takes their dark background, a caption drawn into the image, three pixels
across the smaller of the board's minimum track width and minimum clearance,
and tiles within the size a reviewing model reads without downsampling.

The floorplan is read from the region table of layout-plan.md beside the
board: each region's rectangles, or none, and the parts listed in its Parts
column. A part's extent is the rectangle along the board's axes bounding its
courtyard, or its pads where it has no courtyard; a part is outside when that
extent is not covered by the union of the rectangles of the regions it is listed
in, and a part listed in no region is outside.

The measures are the total length of the connections and each net's length;
the crossings, two segments of different nets that intersect, touch or overlap,
in total and by net; and every part outside its regions. They are written as
text and as JSON beside the image, under an index of their own.

    board_placement.py --board B.kicad_pcb --project B.kicad_pro --out FOLDER

Every finding is one line of a fixed shape, a result line comes last, and the
exit status is the verdict: 0 when the view and its measures are written, 1
when the command is refused or its input cannot be read, 2 when it cannot run
at all, for example because a tool is missing.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import sys
import tempfile
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
import board_geometry  # noqa: E402
import board_views  # noqa: E402
import locked_copper  # noqa: E402
import sexpr  # noqa: E402
from board_check import CannotRun, clean  # noqa: E402
from board_geometry import CONTACT, Unreadable  # noqa: E402

Box = Tuple[float, float, float, float]

#: The layout plan beside the board, whose floorplan table gives each region's rectangles and parts.
PLAN = "layout-plan.md"

#: The layers the image draws, the lowest first: the parts of the back, then of the front, then the edge.
LAYERS = ("B.Cu", "B.Fab", "B.CrtYd", "B.SilkS", "F.Cu", "F.Fab", "F.CrtYd", "F.SilkS", "Edge.Cuts")
#: The forms a routed board's copper takes, left out of the copy the image is drawn from.
LAID = {"segment", "arc", "via", "zone"}

CONNECTION = ("#39ff14", "bright green")
REGION = ("#00e5ff", "cyan")
CONNECTION_PX = 2
REGION_PX = 2

#: One region rectangle as the floorplan writes it, (x1, y1)–(x2, y2), in millimetres.
NUMBER = r"([-+]?(?:\d+\.?\d*|\.\d+))"
RECTANGLE = re.compile(r"\(\s*" + NUMBER + r"\s*,\s*" + NUMBER + r"\s*\)\s*[–—-]\s*\(\s*" + NUMBER + r"\s*,\s*"
                       + NUMBER + r"\s*\)")
#: What may stand between two rectangles of one region.
BETWEEN = re.compile(r"(?:\s|,|;|\band\b)*")
#: One reference designator, as the Parts column lists it.
REFERENCE = re.compile(r"[A-Za-z][A-Za-z0-9_]*")


# --- The floorplan ------------------------------------------------------------------


def cells(line: str) -> List[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def floorplan(path: str) -> List[dict]:
    """Each region of the floorplan table in the layout plan at `path`: its name, its rectangles or None, its parts."""
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except FileNotFoundError as error:
        raise Unreadable(f"the board has no layout plan: {path} is missing, and the placement view reads each "
                         "region's bounds and parts from the floorplan table in it") from error
    except (OSError, UnicodeDecodeError) as error:
        raise Unreadable(f"the layout plan {path} cannot be read ({error})") from error
    start = next((index for index, line in enumerate(lines) if line.strip().startswith("|")
                  and cells(line)[:2] == ["Region", "Bounds"]), None)
    if start is None:
        raise Unreadable(f"the layout plan {path} holds no floorplan table, a table headed | Region | Bounds | "
                         "What it holds | Parts |")
    header = cells(lines[start])
    if "Parts" not in header:
        raise Unreadable(f"the floorplan table of {path} has no Parts column listing the reference designators of "
                         "the parts each region holds")
    column = header.index("Parts")
    separator = cells(lines[start + 1]) if start + 1 < len(lines) and lines[start + 1].strip().startswith("|") else []
    if len(separator) != len(header) or not all(re.fullmatch(r":?-+:?", cell) for cell in separator):
        raise Unreadable(f"the floorplan table of {path} has no separator row of dashes, |---|, under its header, so "
                         "its first region row cannot be told from a heading")
    regions = []
    for line in lines[start + 2:]:
        if not line.strip().startswith("|"):
            break
        row = cells(line)
        name = row[0] if row else ""
        what = f"the floorplan table of {path}, region row '{name}'"
        if len(row) != len(header):
            raise Unreadable(f"{what} has {len(row)} cells where its header has {len(header)}")
        regions.append({"name": name, "bounds": rectangles(row[1], what), "parts": parts(row[column], what)})
        if regions[-1]["bounds"] is None and regions[-1]["parts"]:
            raise Unreadable(f"{what} records the region as none and lists parts in it: "
                             f"{', '.join(regions[-1]['parts'])}; a region of no bounds holds no part")
    return regions


def rectangles(text: str, what: str) -> Optional[List[Box]]:
    """A region's rectangles, (x0, y0, x1, y1) each, or None for a region recorded as none."""
    if re.match(r"none\b", text, re.I):
        return None
    found = []
    for match in RECTANGLE.finditer(text):
        x1, y1, x2, y2 = (float(value) for value in match.groups())
        if x1 == x2 or y1 == y2:
            raise Unreadable(f"{what} gives the rectangle {match.group(0)}, which has no area")
        found.append((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
    if not found or not BETWEEN.fullmatch(RECTANGLE.sub("", text)):
        raise Unreadable(f"{what} gives its bounds as '{text}', not as none or as rectangles (x1, y1)–(x2, y2) in "
                         "millimetres")
    return found


def parts(text: str, what: str) -> List[str]:
    """The reference designators a Parts cell lists, comma-separated; none for an empty cell or 'none'."""
    if not text or text.lower() == "none":
        return []
    listed = []
    for entry in (part.strip() for part in text.split(",")):
        if not REFERENCE.fullmatch(entry):
            raise Unreadable(f"{what} lists '{entry}' in its Parts, which is not one reference designator; list each "
                             "part's reference, comma-separated, without ranges")
        if entry not in listed:
            listed.append(entry)
    return listed


# --- The measures --------------------------------------------------------------------


def footprints(layout: list) -> Dict[str, list]:
    """Each footprint on the board, by its reference; a footprint with no reference, or two sharing one, cannot be
    measured against the floorplan, which lists parts by reference, and stops the command."""
    found: Dict[str, list] = {}
    counts: Dict[str, int] = {}
    for node in sexpr.children(layout, "footprint"):
        name = board_geometry.reference(node).strip()
        counts[name] = counts.get(name, 0) + 1
        found[name] = node
    faults = ([f"{counts['']} footprint{'s' if counts[''] != 1 else ''} with no reference"] if "" in counts else [])
    faults += [f"{name} on {count} footprints" for name, count in sorted(counts.items(), key=lambda item:
                                                                         board_views.natural(item[0]))
               if name and count > 1]
    if faults:
        raise Unreadable(f"the board's footprints cannot be told apart by reference, and the floorplan lists each part "
                         f"by its own: {'; '.join(faults)}; give every footprint a reference of its own")
    return found


def connections(layout: list) -> Dict[str, List[Tuple[board_geometry.Pad, board_geometry.Pad]]]:
    """Each net joining two or more pads, with its connections: the edges of the shortest tree over its pad centres."""
    found = {}
    for net, held in board_geometry.net_pads(layout).items():
        if len(held) > 1:
            _, edges = board_geometry.spanning_tree([pad.centre for pad in held])
            found[net] = [(held[a], held[b]) for a, b in edges]
    return dict(sorted(found.items(), key=lambda item: board_views.natural(item[0])))


def cross(o, a, b) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def meet(a, b, c, d) -> bool:
    """Whether the segments a-b and c-d intersect, touch or overlap."""
    if min(a[0], b[0]) > max(c[0], d[0]) + CONTACT or min(c[0], d[0]) > max(a[0], b[0]) + CONTACT \
            or min(a[1], b[1]) > max(c[1], d[1]) + CONTACT or min(c[1], d[1]) > max(a[1], b[1]) + CONTACT:
        return False
    if cross(a, b, c) * cross(a, b, d) < 0 and cross(c, d, a) * cross(c, d, b) < 0:
        return True
    return min(board_geometry.distance_to_segment(c, a, b), board_geometry.distance_to_segment(d, a, b),
               board_geometry.distance_to_segment(a, c, d), board_geometry.distance_to_segment(b, c, d)) <= CONTACT


def crossings(joined: Dict[str, list]) -> Tuple[int, Dict[str, int]]:
    """How many pairs of segments of different nets meet, and how many each net's segments are in."""
    segments = [(net, a.centre, b.centre) for net, edges in joined.items() for a, b in edges]
    total, by_net = 0, {net: 0 for net in joined}
    for index, (net, a, b) in enumerate(segments):
        for other, c, d in segments[index + 1:]:
            if other != net and meet(a, b, c, d):
                total += 1
                by_net[net] += 1
                by_net[other] += 1
    return total, by_net


def extent(footprint: list) -> Box:
    """The rectangle along the board's axes bounding a part's courtyard, or its pads where it has no courtyard."""
    what = f"the footprint {board_geometry.reference(footprint) or '?'}"
    at = board_geometry.placement(footprint, what)
    points = []
    for shape in footprint[1:]:
        if sexpr.head(shape).startswith("fp_") and sexpr.head(shape) != "fp_text" and \
                any(board_views.on_layer(shape, layer) for layer in ("F.CrtYd", "B.CrtYd")):
            points += courtyard_points(shape, at, what)
    if not points:
        for pad in board_geometry.footprint_pads(footprint, {}):
            half = (pad.size[0] / 2, pad.size[1] / 2)
            points += [(pad.centre[0] + dx, pad.centre[1] + dy) for dx, dy in
                       (board_geometry.turned((sx * half[0], sy * half[1]), pad.angle) for sx in (-1, 1) for sy in (-1, 1))]
    if not points:
        points = [at[:2]]
    return (min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points))


def courtyard_points(shape: list, at, what: str) -> List[Tuple[float, float]]:
    """The points bounding one courtyard shape on the board, a rectangle by all four corners and a circle by its
    centre and radius, so a part turned to any angle is bounded whole."""
    kind = sexpr.head(shape)[3:]
    if kind == "rect":
        (x0, y0), (x1, y1) = (board_geometry.xy(sexpr.child(shape, key), what) for key in ("start", "end"))
        return [board_geometry.placed(corner, at) for corner in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    if kind == "circle":
        centre = board_geometry.placed(board_geometry.xy(sexpr.child(shape, "center"), what), at)
        edge = board_geometry.placed(board_geometry.xy(sexpr.child(shape, "end"), what), at)
        radius = math.dist(centre, edge)
        return [(centre[0] - radius, centre[1] - radius), (centre[0] + radius, centre[1] + radius)]
    return [board_geometry.placed(point, at) for point in board_views.shape_points(shape, what)]


def steps(low: float, high: float, edges: Sequence[float]) -> List[float]:
    """The middle of each stretch from `low` to `high` that `edges` cut it into, or the one point where they are one."""
    if high - low <= CONTACT:
        return [(low + high) / 2]
    cuts = sorted({low, high} | {edge for edge in edges if low + CONTACT < edge < high - CONTACT})
    return [(a + b) / 2 for a, b in zip(cuts, cuts[1:])]


def covered(box: Box, held: Sequence[Box]) -> bool:
    """Whether the union of the rectangles `held` covers `box`: every cell the rectangles' edges cut it into lies in one."""
    xs = steps(box[0], box[2], [edge for rect in held for edge in (rect[0], rect[2])])
    ys = steps(box[1], box[3], [edge for rect in held for edge in (rect[1], rect[3])])
    return all(any(rect[0] - CONTACT <= x <= rect[2] + CONTACT and rect[1] - CONTACT <= y <= rect[3] + CONTACT
                   for rect in held) for x in xs for y in ys)


def outside(placed: Dict[str, list], regions: List[dict]) -> List[dict]:
    """Every part whose extent the rectangles of the regions it is listed in do not cover, a part listed in none among
    them."""
    found = []
    for name in sorted(placed, key=board_views.natural):
        listed = [region for region in regions if name in region["parts"]]
        box = extent(placed[name])
        if not covered(box, [rect for region in listed for rect in region["bounds"] or []]):
            found.append({"reference": name, "regions": [region["name"] for region in listed], "extent_mm": box})
    return found


def rounded(value: float) -> float:
    return float(board_views.mm_text(value))


def measures(layout: list, regions: List[dict]) -> dict:
    """The placement's measures: its connections' lengths, their crossings, and every part outside its regions."""
    joined = connections(layout)
    total, by_net = crossings(joined)
    nets = [{"net": net, "pads": len({id(pad) for edge in edges for pad in edge}),
             "length_mm": rounded(sum(math.dist(a.centre, b.centre) for a, b in edges)), "crossings": by_net[net]}
            for net, edges in joined.items()]
    return {
        "total_length_mm": rounded(sum(math.dist(a.centre, b.centre) for edges in joined.values() for a, b in edges)),
        "crossings": total,
        "nets": nets,
        "outside": [dict(part, extent_mm=dict(zip(("x0", "y0", "x1", "y1"), (rounded(v) for v in part["extent_mm"]))))
                    for part in outside(footprints(layout), regions)],
    }


def measured_placement(board: str, plan: str, layout: list, regions: List[dict]) -> dict:
    """The placement's measures as its measures files give them, with the board and each region as read; a part the
    floorplan at `plan` lists that is not on the board stops the command."""
    placed = footprints(layout)
    for region in regions:
        for name in region["parts"]:
            if name not in placed:
                raise Unreadable(f"the floorplan table of {plan} lists {name} in the region '{region['name']}', and "
                                 f"no part on the board {board} has that reference")
    return dict(board=os.path.realpath(board), **measures(layout, regions),
                regions=[{"name": region["name"], "bounds": bounds_text(region), "parts": region["parts"]}
                         for region in regions])


def measure_lines(measured: dict) -> List[str]:
    """The lines of measures.txt, each field cleaned so nothing in it can break its line."""
    text = [f"BOARD | {measured['board']}",
            f"LENGTH | total | {board_views.mm_text(measured['total_length_mm'])} mm",
            f"CROSSINGS | total | {measured['crossings']}",
            f"OUTSIDE | total | {len(measured['outside'])}"]
    text += [f"NET | {net['net']} | {net['pads']} pads | length {board_views.mm_text(net['length_mm'])} mm | "
             f"{net['crossings']} crossings" for net in measured["nets"]]
    text += [f"OUTSIDE | {part['reference']} | {outside_detail(part)}" for part in measured["outside"]]
    text += [f"REGION | {region['name']} | {region['bounds']} | {', '.join(region['parts']) or 'none'}"
             for region in measured["regions"]]
    return [clean_line(line) for line in text]


# --- The view ----------------------------------------------------------------------------


def bounds_text(region: dict) -> str:
    if region["bounds"] is None:
        return "none"
    return ", ".join(f"({board_views.mm_text(x0)}, {board_views.mm_text(y0)})–({board_views.mm_text(x1)}, "
                     f"{board_views.mm_text(y1)})" for x0, y0, x1, y1 in region["bounds"])


def overlay(joined: Dict[str, list], regions: List[dict], scale: float) -> str:
    """The floorplan's regions as dashed outlines, each named, and every net's connections as straight lines over
    them, in board coordinates, their strokes and lettering sized in pixels at `scale`."""
    px = 1 / scale
    drawn = []
    for region in regions:
        for x0, y0, x1, y1 in region["bounds"] or []:
            drawn.append(f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" fill="none" '
                         f'stroke="{REGION[0]}" stroke-width="{REGION_PX * px}" '
                         f'stroke-dasharray="{10 * px} {6 * px}"/>'
                         f'<text x="{x0 + 4 * px}" y="{y0 + (board_views.FONT_PX + 2) * px}" '
                         f'font-family="{board_views.FONT_FAMILY}" font-size="{board_views.FONT_PX * px}" '
                         f'fill="{REGION[0]}">{board_views.escape(region["name"])}</text>')
    for edges in joined.values():
        for a, b in edges:
            drawn.append(f'<line x1="{a.centre[0]}" y1="{a.centre[1]}" x2="{b.centre[0]}" y2="{b.centre[1]}" '
                         f'stroke="{CONNECTION[0]}" stroke-width="{CONNECTION_PX * px}" stroke-linecap="round"/>')
    return "".join(drawn)


def unrouted(layout: list) -> list:
    """The board without its tracks, arcs, vias and zones: its parts as they are placed."""
    return [node for node in layout if not (isinstance(node, list) and sexpr.head(node) in LAID)]


def placement(board: str, project: str, out: str, kicad_cli: str, resvg: str, stream) -> int:
    """Render the placement view of the board and write its measures into `out`; the exit status."""
    refusals = board_views.working_refusals(board, project, out)
    if refusals:
        return locked_copper.refused(refusals, "REFUSED | no placement view was written", stream)
    layout = locked_copper.read_layout(board)
    figures, refusals = board_views.minimums(locked_copper.read_project(project), project)
    if refusals:
        return locked_copper.refused(refusals, "REFUSED | no placement view was written", stream)
    plan = os.path.join(os.path.dirname(os.path.abspath(board)), PLAN)
    regions = floorplan(plan)
    measured = measured_placement(board, plan, layout, regions)
    placed = footprints(layout)

    scale = board_views.PIXELS_PER_FEATURE / min(figures)
    carried = board_views.layer_table(layout)
    with tempfile.TemporaryDirectory(prefix="board-placement-") as work:
        ready = os.path.join(work, "out")
        os.makedirs(ready)
        copy, _ = board_views.stage(board, project, work)
        parts_only = unrouted(locked_copper.read_layout(copy))
        with open(copy, "w", encoding="utf-8") as handle:
            handle.write(sexpr.dump(parts_only) + "\n")
        copy = os.path.relpath(copy, work)
        fonts: Dict[str, str] = {}
        plotted = {layer: board_views.plot(kicad_cli, work, copy, layer, f"layer-{index}.svg", board, fonts)
                   for index, layer in enumerate(LAYERS) if layer in carried}
        areas = board_views.rule_areas(layout, carried)
        outline = board_views.outline_bounds(layout) if "Edge.Cuts" in carried else None
        frame = board_views.board_frame(outline, plotted, areas,
                                        [rect for region in regions for rect in region["bounds"] or []]
                                        + [extent(node) for node in placed.values()])
        if frame is None:
            raise Unreadable(f"the board {board} holds nothing to draw: no outline, part or region")
        names = board_views.Names()
        files = dict(zip(("index_text", "index_json"), names.claim("index", [".txt", ".json"])))
        files.update(zip(("measures_text", "measures_json"), names.claim("measures", [".txt", ".json"])))
        renderer = board_views.Renderer(resvg, work, ready, scale, frame, plotted, board_views.layer_colours(carried),
                                        [], areas, fonts, names)
        joined = connections(layout)
        renderer.flat("placement", LAYERS,
                      {"view": "placement", "regions": measured["regions"]},
                      ["placement view: each net's connections drawn straight between the pads they join, the "
                       "shortest straight-line tree over the net's pad centres, with no copper laid",
                       f"connections in {CONNECTION[1]}",
                       f"floorplan regions as {REGION[1]} dashed outlines, each named: "
                       + board_views.named([f"{region['name']} {bounds_text(region)}" for region in regions])],
                      overlay=overlay(joined, regions, scale))
        renderer.write()
        header = {
            "board": measured["board"],
            **board_views.index_fields(scale, figures, fonts, renderer.absent, areas),
            "measures": {"text": files["measures_text"], "json": files["measures_json"]},
        }
        write_outputs(ready, files, header, renderer.images, measured)
        os.makedirs(out, exist_ok=True)
        for name in sorted(os.listdir(ready)):
            shutil.move(os.path.join(ready, name), os.path.join(out, name))
    board_views.report_substitutions(fonts, renderer.absent, False, stream)
    for part in measured["outside"]:
        print(f"OUTSIDE | {part['reference']} | {outside_detail(part)}", file=stream)
    print(f"MEASURES | length {board_views.mm_text(measured['total_length_mm'])} mm | {measured['crossings']} "
          f"crossings | {len(measured['outside'])} parts outside their regions", file=stream)
    board_views.report_resolution(scale, figures, stream)
    print(f"RESULT | WRITTEN | {len(renderer.images)} images, their index and the placement's measures | {clean(out)}",
          file=stream)
    return 0


def outside_detail(part: dict) -> str:
    box = part["extent_mm"]
    where = board_views.covers((box["x0"], box["y0"], box["x1"], box["y1"]))
    if not part["regions"]:
        return f"listed in no region of the floorplan; its extent covers {where}"
    return f"listed in {', '.join(part['regions'])}; its extent covers {where}, which those regions' bounds do not hold"


def write_outputs(folder: str, files: Dict[str, str], header: dict, images: List[dict], measured: dict) -> None:
    """The index and the measures, each as text and JSON, into `folder` under the names `files` gives them."""
    board_views.write_index(folder, files, header, images, False,
                            after_limit=[f"MEASURES | {files['measures_text']} | {files['measures_json']}"])
    with open(os.path.join(folder, files["measures_text"]), "w", encoding="utf-8") as handle:
        handle.write("\n".join(measure_lines(measured)) + "\n")
    with open(os.path.join(folder, files["measures_json"]), "w", encoding="utf-8") as handle:
        json.dump(measured, handle, indent=1)
        handle.write("\n")


def clean_line(line: str) -> str:
    """A line whose fields, a net's name among them, cannot break it."""
    return " | ".join(clean(field) for field in line.split(" | "))


def main(argv: Optional[List[str]] = None, out=sys.stdout) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--kicad-cli", default="kicad-cli", help="KiCad's command-line tool (default: kicad-cli on the search path)")
    parser.add_argument("--resvg", default="resvg", help="the resvg rasteriser (default: resvg on the search path)")
    parser.add_argument("--board", required=True, help="the layout file (.kicad_pcb), with its layout-plan.md beside it")
    parser.add_argument("--project", required=True, help="the layout's own project file (.kicad_pro)")
    parser.add_argument("--out", required=True, help="the folder to write the view and its measures into: new or empty, and outside every design's folder")
    args = parser.parse_args(argv)
    try:
        board_check.require_python()
        version = board_check.require_kicad(args.kicad_cli)
        board_views.require_resvg(args.resvg)
        with tempfile.TemporaryDirectory(prefix="board-placement-kicad-") as home:
            board_check.KICAD_ENVIRONMENT = board_check.isolate_kicad(args.kicad_cli, version, home)
            board_views.english(home)
            try:
                return placement(args.board, args.project, args.out, args.kicad_cli, args.resvg, out)
            finally:
                board_check.KICAD_ENVIRONMENT = None
    except Unreadable as error:
        print(f"UNREADABLE | {clean(str(error))}", file=out)
        print("RESULT | FAIL | the input cannot be read, so no placement view was written", file=out)
        return 1
    except CannotRun as error:
        print(f"CANNOT RUN | {clean(str(error))}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
