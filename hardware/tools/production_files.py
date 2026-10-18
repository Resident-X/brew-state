#!/usr/bin/env python3
"""Turn a board's exported production files into what the method's ordering step reads.

KiCad's command-line tool exports the position file, the parts list, the Gerber
layers and the drill file, and the method's ordering step names those commands.
Two things it cannot do are done here:

    production_files.py placement --positions <KiCad position export, CSV> --out <placement file, CSV>
    production_files.py render --gerbers <folder of exported Gerber and drill files> --out <new or empty folder> [--resvg ...]

`placement` writes the assembler's placement file from the position export:
the columns the manufacturer's record gives for it, Designator, Mid X, Mid Y,
Layer and Rotation, in millimetres and degrees counter-clockwise. The export's
coordinates are already in the frame of the Gerber files it was exported with,
the frame the assembler lays the placement on, so they are kept as they are; only
the columns, the side's name and the rotation's range change.

`render` draws every Gerber layer and the drill file from the exported files
themselves, each into a PNG of its own in one common frame, so a layer that is
shifted, mirrored or empty shows against the others and against the design's
own views. KiCad's command-line tool reads no Gerber file, so the drawing is
gerbonara's, at the exact version it names, turned into an SVG and rasterised
with resvg. The folder also holds an index of every image, as text and as JSON.

Each step is reported on one line, a RESULT line comes last, and the exit status
is 0 when the output is written, 1 when the command is refused, and 2 when it
cannot run, for example because gerbonara or resvg is missing.
"""

from __future__ import annotations

import argparse
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
    args = parser.parse_args(argv)
    if args.command == "placement":
        return placement(os.path.abspath(args.positions), os.path.abspath(args.out))
    return render(os.path.abspath(args.gerbers), os.path.abspath(args.out), args.resvg)


if __name__ == "__main__":
    sys.exit(main())
