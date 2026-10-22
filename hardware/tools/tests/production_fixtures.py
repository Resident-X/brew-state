#!/usr/bin/env python3
"""Synthetic repositories and production-files folders for the production-files caller's and folder command's tests.

Nothing here is a real design, order or specification: the board is placeholder text, the placement file lists parts with
made-up designators, the drawings and layer images are small generated pictures and every figure is made up. No KiCad,
gerbonara and no model is used.
"""

from __future__ import annotations

import io
import json
import os
import sys

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import layout_fixtures as fx  # noqa: E402
import production_review_folder  # noqa: E402
import review_kit_fixtures as kit_fx  # noqa: E402

DESIGN = fx.DESIGN
#: Twelve resistors of one footprint (so one group splits into ten and two), two capacitors, one chip, and three parts with no
#: drawing: two the parts list names a footprint for and one it does not.
RESISTORS = [f"R{n}" for n in range(1, 13)]
CAPACITORS = ["C1", "C2"]
CHIP = ["U1"]
ODD = ["X1", "X2"]
BARE = ["Y1"]
PLACED = RESISTORS + CAPACITORS + CHIP + ODD + BARE
LAYERS = ["F.Cu", "B.Cu", "F.Mask", "B.Mask", "F.SilkS", "B.SilkS", "Edge.Cuts", "drill"]
DRAWINGS = [("footprint-Lib_R_0603.png", "Lib:R_0603", RESISTORS), ("footprint-Lib_C_0603.png", "Lib:C_0603", CAPACITORS),
            ("footprint-Lib_U_8.png", "Lib:U_8", CHIP)]
RECORD = "parts-specification.yaml"
MANUFACTURER = "# Synthetic manufacturer record\n\nColumns of the placement file.\n"


def placement_text(parts=PLACED) -> str:
    rows = ["Designator,Mid X,Mid Y,Layer,Rotation"]
    rows += [f"{name},{10 + 2 * at},{-5 - at},{'Bottom' if name == 'C2' else 'Top'},{90 * (at % 4)}" for at, name in enumerate(parts)]
    return "\n".join(rows) + "\n"


def parts_text() -> str:
    return ("Comment,Designator,Footprint,LCSC\n"
            f"10k,\"{', '.join(RESISTORS)}\",Lib:R_0603,C0001\n100n,\"C1, C2\",Lib:C_0603,C0002\nchip,U1,Lib:U_8,C0003\n"
            "odd,\"X1, X2\",Lib:Odd_1,C0004\nbare,Y1,,C0005\n")


def layers_index() -> dict:
    return {"gerbers": "gerbers", "images": [{"file": f"layer-{name}.png", "layer": name, "source": f"{name}.gbr"} for name in LAYERS]}


def footprints_index() -> dict:
    return {"board": "board.kicad_pcb", "images": [{"file": file, "footprint": lib, "used_by": used, "px_per_mm": 10}
                                                   for file, lib, used in DRAWINGS]}


def make_work(root: str, parts=PLACED) -> str:
    """A work folder as the ordering step's first two steps leave it."""
    work = os.path.join(root, "work")
    fx.write(os.path.join(work, "placement.csv"), placement_text(parts))
    fx.write(os.path.join(work, "parts-list.csv"), parts_text())
    for name in ("board-F_Cu.gtl", "board.drl"):
        fx.write(os.path.join(work, "gerbers", name), "G04 synthetic*\n")
    for folder, index in (("layers", layers_index()), ("footprints", footprints_index())):
        fx.write(os.path.join(work, folder, "index.json"), json.dumps(index))
        fx.write(os.path.join(work, folder, "index.txt"), "\n".join(f"IMAGE | {image['file']}" for image in index["images"]) + "\n")
        for image in index["images"]:
            fx.write(os.path.join(work, folder, image["file"]), kit_fx.png(60, 40, 90))
    return work


def make_inputs(root: str) -> dict:
    """The repository, the work folder, the views, the placement view and the preview folders and the command's other inputs."""
    repo = fx.make_repo(root, extra={RECORD: "parts: synthetic\n"})
    fx.write(os.path.join(repo, "docs", "board-manufacturer-jlcpcb.md"), MANUFACTURER)
    fx.git(repo, "add", "-A")
    fx.git(repo, "commit", "-q", "-m", "the manufacturer's record")
    views = os.path.join(root, "views-in")
    fx.write(os.path.join(views, "index.txt"), "layer-F.Cu-r1c1.png\nassembly-top-r1c1.png\n")
    fx.write(os.path.join(views, "layer-F.Cu-r1c1.png"), kit_fx.png(200, 120, 30))
    fx.write(os.path.join(views, "assembly-top-r1c1.png"), kit_fx.png(200, 120, 40))
    placement = os.path.join(root, "placement-in")
    fx.write(os.path.join(placement, "index.txt"), "placement.png\n")
    fx.write(os.path.join(placement, "placement.png"), kit_fx.png(160, 100, 60))
    preview = os.path.join(root, "preview-in")
    fx.write(os.path.join(preview, "preview-top.png"), kit_fx.png(180, 110, 70))
    return {"repo": repo, "work": make_work(root), "views": views, "placement": placement, "preview": preview}


COMMANDS = ["kicad-cli pcb export pos --format csv --units mm --side both --exclude-dnp --output <work>/positions.csv board.kicad_pcb",
            "python3 hardware/tools/production_files.py render --gerbers <work>/gerbers --out <work>/layers"]
TOOLS_LINE = "kicad-cli 9.9.9, gerbonara 1.6.3, resvg 0.45.1"
PREVIEW_NOTE = "the assembler's preview of both sides, saved 2030-01-02, the synthetic assembler"


def argv(inputs: dict, out: str, commit: str = "HEAD", extra=()) -> list:
    arguments = ["--repo", inputs["repo"], "--commit", commit, "--design", DESIGN, "--out", out, "--work", inputs["work"],
                 "--views", inputs["views"], "--placement", inputs["placement"], "--preview", inputs["preview"],
                 "--preview-note", PREVIEW_NOTE, "--tools", TOOLS_LINE, "--documents-repo", inputs["repo"]]
    for command in COMMANDS:
        arguments += ["--command", command]
    return arguments + list(extra)


def run(arguments: list):
    out = io.StringIO()
    status = production_review_folder.main(arguments, out=out)
    return status, out.getvalue()


def write_folder(root: str, inputs: dict = None) -> str:
    """A production-files review folder written by the folder command from synthetic inputs; its path."""
    inputs = inputs or make_inputs(root)
    out = os.path.join(root, "review-folder")
    status, text = run(argv(inputs, out))
    assert status == 0, text
    return out
