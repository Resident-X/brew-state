#!/usr/bin/env python3
"""Flat layer views of one board, for the web page: one image per layer plus the three whole-board stacks.

usage: layer_views.py BOARD.kicad_pcb PROJECT.kicad_pro OUT_DIR

Uses the repository's board_views.py helpers (staging the copy, refilling its zones with KiCad, plotting each
layer with `kicad-cli pcb export svg`, the frame of the view) and draws each layer itself: the layer's copper in
its own colour on a light background, holes left as background, the board outline faint beneath the copper.
Writes one PNG per view into a scratch folder, then the JPEGs (macOS sips) into OUT_DIR, and a text index.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile

TOOLS = os.environ.get("BOARD_TOOLS", "<repo>/hardware/tools")  # the repository checkout's hardware/tools folder
sys.path.insert(0, TOOLS)

import board_views as bv  # noqa: E402

KICAD_CLI = os.environ.get("KICAD_CLI", "kicad-cli")
WIDTH_PX = int(os.environ.get("WIDTH_PX","1200"))
BACKGROUND = "#f6f5f1"
EDGE_FAINT = "#8a8f8c"
#: The stack the whole-board views are drawn in, bottom first, so the front copper is on top.
STACK = ["B.Cu", "In4.Cu", "In3.Cu", "In2.Cu", "In1.Cu", "F.Cu"]
COLOURS = {
    "F.Cu": "#c83a3a", "B.Cu": "#2f6fc4",
    "In1.Cu": "#e0a030", "In2.Cu": "#3fa36a", "In3.Cu": "#8a5cc8", "In4.Cu": "#2fb0b0",
    "F.SilkS": "#1d2421", "B.SilkS": "#b0357a", "Edge.Cuts": "#b08a00",
}


def body(svg_path: str, colour: str) -> str:
    """A KiCad layer plot's drawing, recoloured: its ink in `colour`, its holes in the page background."""
    with open(svg_path, encoding="utf-8") as handle:
        text = handle.read()
    start = text.index(">", text.index("<svg")) + 1
    inner = text[start:text.rindex("</svg>")]
    inner = re.sub(r"#[fF]{6}\b", BACKGROUND, inner)
    inner = re.sub(r"#(?![fF]{6}\b)[0-9A-Fa-f]{6}\b", colour, inner)
    return f"<g>{inner}</g>"


def image(work: str, name: str, frame, parts: list) -> str:
    """Compose the parts (already-drawn SVG groups) over the frame, on the background, and rasterise to PNG."""
    x0, y0, x1, y1 = frame
    width_mm, height_mm = x1 - x0, y1 - y0
    height_px = round(WIDTH_PX * height_mm / width_mm)
    svg = os.path.join(work, f"{name}.svg")
    with open(svg, "w", encoding="utf-8") as handle:
        handle.write(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH_PX}" height="{height_px}" '
            f'viewBox="{x0} {y0} {width_mm} {height_mm}">'
            f'<rect x="{x0}" y="{y0}" width="{width_mm}" height="{height_mm}" fill="{BACKGROUND}"/>'
            + "".join(parts) + "</svg>")
    png = os.path.join(work, f"{name}.png")
    bv.rasterise("resvg", svg, png)
    return png


def jpeg(png: str, jpg: str) -> None:
    subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "70", png, "--out", jpg],
                   check=True, capture_output=True)


def main(argv: list) -> int:
    board, project, out = argv
    os.makedirs(out, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="layers-", dir=os.environ.get("WORK_DIR")) as work:
        staged, _ = bv.stage(board, project, work)
        copy = os.path.relpath(staged, work)
        refilled = bv.locked_copper.read_layout(os.path.join(work, copy))
        carried = bv.layer_table(refilled)
        fonts: dict = {}
        plotted = {}
        for index, layer in enumerate(carried):
            if layer in COLOURS or re.fullmatch(r"In\d\.Cu", layer) or layer in ("F.Cu", "B.Cu"):
                plotted[layer] = bv.plot(KICAD_CLI, work, copy, layer, f"plot-{index}.svg", board, fonts)
        outline = bv.outline_bounds(refilled)
        frame = bv.board_frame(outline, plotted, [])
        if fonts:
            print("fonts substituted:", fonts)
        colours = dict(COLOURS)
        for layer in plotted:
            colours.setdefault(layer, "#888888")
        edge = body(plotted["Edge.Cuts"], EDGE_FAINT) if "Edge.Cuts" in plotted else ""

        def copper_parts(layers):
            return [body(plotted[layer], colours[layer]) for layer in layers if layer in plotted]

        views = {
            "full-board": (STACK + ["F.SilkS", "B.SilkS"], True),
            "top": (["F.Cu", "F.SilkS"], True),
            "bottom": (["B.Cu", "B.SilkS"], True),
            "layer-F.Cu": (["F.Cu"], True),
            "layer-In1.Cu": (["In1.Cu"], True),
            "layer-In2.Cu": (["In2.Cu"], True),
            "layer-In3.Cu": (["In3.Cu"], True),
            "layer-In4.Cu": (["In4.Cu"], True),
            "layer-B.Cu": (["B.Cu"], True),
            "layer-F.SilkS": (["F.SilkS"], False),
            "layer-B.SilkS": (["B.SilkS"], False),
            "layer-Edge.Cuts": (["Edge.Cuts"], False),
        }
        made = []
        for name, (layers, with_edge) in views.items():
            if name == "layer-Edge.Cuts":
                parts = [body(plotted["Edge.Cuts"], colours["Edge.Cuts"])]
            else:
                parts = ([edge] if with_edge and edge else []) + copper_parts(layers)
                if name in ("full-board", "top", "bottom"):
                    parts = [edge] + copper_parts(layers)
            png = image(work, name, frame, parts)
            dest = os.path.join(out, name + ".jpg")
            jpeg(png, dest)
            made.append((name, os.path.getsize(dest)))
        for name, size in made:
            print(f"{name}.jpg {size} bytes")
        print("frame mm", [round(v, 3) for v in frame], "layers", carried)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
