"""The layout review views, rendered from a synthetic proof board against the real kicad-cli and resvg.

The proof board is written from text in a temporary directory outside the
repository: three integrated circuits sharing one rail, two of them with a
decoupling part nearest them and one with none, a fourth circuit with no pin
typed as power, two critical
classes, a ground pour on the back whose fill is cut around a power track, two
signal tracks at the board's minimum width and minimum clearance, a note on a
user layer, a rule area, a silkscreen text in a font no machine has, and parts
whose three-dimensional models are kept in the design's folder, missing, hidden
or not populated, a power track crossing the rule area, a net in two critical
classes, a connector courtyard and a silkscreen text reaching past the board
outline, and a part turned 90 degrees, a text turned 45 degrees and a mirrored
back-side text, which KiCad plots through transforms. The views are rendered once, through the shipped task, and the
tests ask of the images, the index and the fact table what the criterion
needs; the refusals are driven through the command itself. Nothing is skipped
when a tool is absent: a command that cannot be exercised has not been shown
to work.
"""

from __future__ import annotations

import contextlib
import io
import json
import math
import os
import subprocess
import sys
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from board_fixtures import MINIMUM_MM  # noqa: E402
from board_fixtures import OUTLINE  # noqa: E402
from board_fixtures import footprint  # noqa: E402
from board_fixtures import hex_rgb  # noqa: E402
from board_fixtures import model  # noqa: E402
from board_fixtures import pad  # noqa: E402
from board_fixtures import project  # noqa: E402
from board_fixtures import uuid  # noqa: E402
import board_fixtures  # noqa: E402
import board_views  # noqa: E402


REPO = os.path.dirname(os.path.dirname(TOOLS))


KICAD_CLI = os.environ.get("KICAD_CLI") or "kicad-cli"


RESVG = os.environ.get("RESVG") or "resvg"


PROOF_PROJECT = board_fixtures.PROOF_PROJECT


#: The critical classes the proof board's views are rendered with: +3V3 is in both Power and Sense.
CRITICAL = ("Power", "Ground", "Sense")


#: The proof board's resolution, from its minimum track width and minimum clearance.
SCALE = 3 / MINIMUM_MM


_RENDERED = {}


def setUpModule():
    board_fixtures.require_tools(KICAD_CLI, RESVG)


def tearDownModule():
    board_fixtures.cleanup()


#: A model the design keeps in its own folder: a red box 5.08 mm on each side, in the STEP file beside this one, which a
#: model's scale stretches upward. It is STEP rather than VRML because KiCad's packages for Linux write nothing for a
#: VRML model to the three-dimensional export, the one the views draw from, where the author's build draws it.
MODEL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "box.step")


with open(MODEL_FILE, encoding="utf-8") as _handle:
    MODEL = _handle.read()


MODEL_COLOUR = (230, 13, 13)


#: The font one silkscreen text asks for, which no machine has, so KiCad substitutes another.
NO_SUCH_FONT = "Board Views Proof Face"


#: The proof board's items: U1, U3 and U4 share the +3V3 and GND rails, their supply pins typed, and C1 and C2
#: sit across those rails, C1 nearest U1 and C2 nearest U3, so neither is nearest U4; R1 has only one pad on a
#: rail; U2 has no pin typed as power. U3 and U4 declare no model. The ground pour on B.Cu is cut around the +3V3 track crossing it, so its
#: fill depends on another net's copper. SIG_A and SIG_B run at the minimum width, the minimum clearance apart.
#: U1's model is in the design's folder, named through ${KIPRJMOD}; U2's is the same file named from that folder
#: with no variable, stretched to 61 mm tall at the back of the board, so the angled view must zoom out to show
#: it whole; C1 declares no model, C2's model is nowhere, R1 hides its model and D1 is not populated. A rule area
#: on F.Cu and a user layer, which KiCad does not plot, crossed by a +3V3 track, and a silkscreen text in a font no
#: machine has follow. J1's courtyard and fabrication outline overhang the board's right edge, at x = 60 mm, to
#: 64.5 mm and 64 mm, and a silkscreen text sits below its bottom edge, at y = 40 mm, at y = 45 mm. R5 is placed
#: turned 90 degrees with its reference turned with it, a silkscreen text turned 45 degrees sits above the board's
#: top edge, at y = 0, about y = -4 mm, and a mirrored text on the back silkscreen sits left of its left edge, at
#: x = 0, about x = -6 mm: KiCad plots each of the three through a transform.
ITEMS = [
    footprint("U1", 20, 20, [pad(1, -2, -1, "+3V3", "power_in"), pad(2, -2, 1, "GND", "power_in"),
                             pad(3, 2, -1, "SIG_A", "input"), pad(4, 2, 1, "SIG_B", "output")],
              [model("${KIPRJMOD}/models/box.step")]),
    footprint("C1", 4, 20, [pad(1, 0, -1, "+3V3", "passive"), pad(2, 0, 1, "GND", "passive")]),
    footprint("C2", 56, 20, [pad(1, 0, -1, "+3V3", "passive"), pad(2, 0, 1, "GND", "passive")],
              [model("${KIPRJMOD}/models/missing.step")]),
    footprint("R1", 30, 12, [pad(1, 0, -1, "SIG_A", "passive"), pad(2, 0, 1, "+3V3", "passive")],
              [model("${KIPRJMOD}/models/box.step", hidden=True)]),
    footprint("U2", 45, 8, [pad(1, -1, 0, "SIG_A", "input"), pad(2, 1, 0, "SIG_B", "output")],
              [model("models/box.step", height=12)]),
    footprint("D1", 8, 8, [pad(1, -1, 0, "SIG_A", "passive"), pad(2, 1, 0, "SIG_B", "passive")],
              [model("${KIPRJMOD}/models/box.step")], "(attr smd dnp)"),
    footprint("U3", 48, 20, [pad(1, -2, -1, "+3V3", "power_in"), pad(2, -2, 1, "GND", "power_in"),
                             pad(3, 2, -1, "SIG_A", "input")]),
    footprint("U4", 38, 12, [pad(1, -2, -1, "+3V3", "power_in"), pad(2, -2, 1, "GND", "power_in"),
                             pad(3, 2, -1, "SIG_B", "input")]),
    f'(segment (start 4 19) (end 18 19) (width 0.3) (layer "F.Cu") (net "+3V3") (uuid {uuid()}))',
    f'(segment (start 24 19) (end 40 19) (width 0.1) (layer "F.Cu") (net "SIG_A") (uuid {uuid()}))',
    f'(segment (start 24 19.2) (end 40 19.2) (width 0.1) (layer "F.Cu") (net "SIG_B") (uuid {uuid()}))',
    f'(segment (start 5 30) (end 55 30) (width 0.5) (layer "B.Cu") (net "+3V3") (uuid {uuid()}))',
    f'(via (at 5 30) (size 0.8) (drill 0.4) (layers "F.Cu" "B.Cu") (net "+3V3") (uuid {uuid()}))',
    f'(zone (net "GND") (layer "B.Cu") (uuid {uuid()}) (hatch edge 0.5) (connect_pads (clearance 0.5)) '
    '(min_thickness 0.25) (filled_areas_thickness no) (fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5)) '
    '(polygon (pts (xy 2 25) (xy 58 25) (xy 58 38) (xy 2 38))))',
    f'(gr_text "KEEP OUT" (at 30 4 0) (layer "Cmts.User") (uuid {uuid()}) (effects (font (size 1.5 1.5) (thickness 0.2))))',
    f'(gr_text "FACE" (at 10 36 0) (layer "F.SilkS") (uuid {uuid()}) '
    f'(effects (font (face "{NO_SUCH_FONT}") (size 1.5 1.5) (thickness 0.2))))',
    f'(zone (net "") (net_name "") (layers "F.Cu" "Dwgs.User") (uuid {uuid()}) (name "KO1") (hatch edge 0.5) '
    '(connect_pads (clearance 0)) (min_thickness 0.25) (filled_areas_thickness no) (keepout (tracks not_allowed) '
    '(vias not_allowed) (pads allowed) (copperpour not_allowed) (footprints allowed)) (placement (enabled no) '
    '(sheetname "")) (fill (thermal_gap 0.5) (thermal_bridge_width 0.5)) '
    '(polygon (pts (xy 50 2) (xy 56 2) (xy 56 6) (xy 50 6))))',
    f'(segment (start 48 4) (end 58 4) (width 0.3) (layer "F.Cu") (net "+3V3") (uuid {uuid()}))',
    f'(footprint "proof:Connector" (layer "F.Cu") (uuid {uuid()}) (at 57 12) '
    f'(property "Reference" "J1" (at 0 -3 0) (layer "F.SilkS") (uuid {uuid()}) '
    '(effects (font (size 1 1) (thickness 0.15)))) '
    f'(fp_rect (start -1.5 -2.5) (end 7.5 2.5) (stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd") '
    f'(uuid {uuid()})) '
    f'(fp_rect (start -1 -2) (end 7 2) (stroke (width 0.1) (type solid)) (fill no) (layer "F.Fab") (uuid {uuid()})) '
    + pad(1, 0, -1, "SIG_A", "passive") + " " + pad(2, 0, 1, "SIG_B", "passive") + ")",
    f'(gr_text "OFF BOARD" (at 30 45 0) (layer "F.SilkS") (uuid {uuid()}) '
    '(effects (font (size 1.5 1.5) (thickness 0.2))))',
    f'(footprint "proof:Part" (layer "F.Cu") (uuid {uuid()}) (at 38 30 90) '
    f'(property "Reference" "R5" (at 0 -3 90) (layer "F.SilkS") (uuid {uuid()}) '
    '(effects (font (size 1 1) (thickness 0.15)))) '
    f'(fp_rect (start -1.5 -2) (end 1.5 2) (stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd") '
    f'(uuid {uuid()})) ' + pad(1, 0, -1, "SIG_A", "passive") + " " + pad(2, 0, 1, "SIG_B", "passive") + ")",
    f'(gr_text "TILT" (at 30 -4 45) (layer "F.SilkS") (uuid {uuid()}) '
    '(effects (font (size 1.5 1.5) (thickness 0.2))))',
    f'(gr_text "BACK" (at -6 20 0) (layer "B.SilkS") (uuid {uuid()}) '
    '(effects (font (size 1.5 1.5) (thickness 0.2)) (justify mirror)))',
]


def layout(items=None, layers=None, outline=OUTLINE) -> str:
    return board_fixtures.layout(ITEMS if items is None else items, layers, outline)


class Design(board_fixtures.Design):
    """The proof board and its project in their own folder, with a working folder outside it."""

    def __init__(self, board_text=None, project_text=None):
        super().__init__(layout() if board_text is None else board_text,
                         project() if project_text is None else project_text, prefix="board-views-test-")
        self.write(os.path.join("models", "box.step"), MODEL)

    def args(self, classes=("Power", "Ground"), out=None):
        found = ["--board", self.board, "--project", self.project, "--out", out or self.out]
        for name in classes:
            found += ["--class", name]
        return found

    def run(self, classes=("Power", "Ground"), out=None, kicad_cli=KICAD_CLI, resvg=RESVG):
        stream, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(errors):
            status = board_views.main(["--kicad-cli", kicad_cli, "--resvg", resvg, *self.args(classes, out)],
                                      out=stream)
        return status, stream.getvalue().splitlines(), errors.getvalue()


def rendered():
    """The proof board's views, rendered once through the shipped task: (design, task result, index, facts)."""
    if not _RENDERED:
        design = Design(project_text=project(classes=CRITICAL, patterns=[("Sense", "+3V3")]))
        result = subprocess.run(["task", "hw:views", f"KICAD_CLI={KICAD_CLI}", f"RESVG={RESVG}", "--",
                                 *design.args(CRITICAL)], cwd=REPO, capture_output=True, text=True, timeout=1800)
        index = facts = None
        if result.returncode == 0:
            with open(os.path.join(design.out, "index.json"), encoding="utf-8") as handle:
                index = json.load(handle)
            with open(os.path.join(design.out, "facts.json"), encoding="utf-8") as handle:
                facts = json.load(handle)
        _RENDERED.update(design=design, result=result, index=index, facts=facts, pixels={})
    return _RENDERED


BACKGROUND = hex_rgb(board_views.BACKGROUND)


def model_reads(width: int, height: int):
    """The size a reviewing model reads an image at, by the vendor's published rule: an image over either the
    1568-pixel long edge or 1568 patches of 28 by 28 pixels is downscaled, keeping its aspect ratio, to the largest
    size within both."""
    def within(w, h):
        return max(w, h) <= 1568 and math.ceil(w / 28) * math.ceil(h / 28) <= 1568
    if within(width, height):
        return width, height
    low, high = 0.0, 1.0
    for _ in range(60):
        middle = (low + high) / 2
        if within(max(1, math.floor(width * middle)), max(1, math.floor(height * middle))):
            low = middle
        else:
            high = middle
    return max(1, math.floor(width * low)), max(1, math.floor(height * low))


if __name__ == "__main__":
    unittest.main()
