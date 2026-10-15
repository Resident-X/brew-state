#!/usr/bin/env python3
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
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
import board_fixtures  # noqa: E402
import board_views  # noqa: E402
from board_fixtures import LAYER_TABLE, MINIMUM_MM, OUTLINE, footprint, hex_rgb, model, pad, project, uuid  # noqa: E402

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


# --- The proof board -------------------------------------------------------------------

#: A model the design keeps in its own folder: a red box 2 by 2 by 2 in VRML's units of 2.54 mm, which a model's
#: scale stretches upward.
MODEL = """#VRML V2.0 utf8
Shape { appearance Appearance { material Material { diffuseColor 0.9 0.05 0.05 } } geometry Box { size 2 2 2 } }
"""
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
              [model("${KIPRJMOD}/models/box.wrl")]),
    footprint("C1", 4, 20, [pad(1, 0, -1, "+3V3", "passive"), pad(2, 0, 1, "GND", "passive")]),
    footprint("C2", 56, 20, [pad(1, 0, -1, "+3V3", "passive"), pad(2, 0, 1, "GND", "passive")],
              [model("${KIPRJMOD}/models/missing.step")]),
    footprint("R1", 30, 12, [pad(1, 0, -1, "SIG_A", "passive"), pad(2, 0, 1, "+3V3", "passive")],
              [model("${KIPRJMOD}/models/box.wrl", hidden=True)]),
    footprint("U2", 45, 8, [pad(1, -1, 0, "SIG_A", "input"), pad(2, 1, 0, "SIG_B", "output")],
              [model("models/box.wrl", height=12)]),
    footprint("D1", 8, 8, [pad(1, -1, 0, "SIG_A", "passive"), pad(2, 1, 0, "SIG_B", "passive")],
              [model("${KIPRJMOD}/models/box.wrl")], "(attr smd dnp)"),
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
        self.write(os.path.join("models", "box.wrl"), MODEL)

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


# --- Reading the images -------------------------------------------------------------------


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


class Views(unittest.TestCase):
    """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""

    @classmethod
    def setUpClass(cls):
        cls.views = rendered()

    def setUp(self):
        result = self.views["result"]
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.out = self.views["design"].out
        self.index = self.views["index"]

    def images(self, view, **match):
        return [image for image in self.index["images"] if image["view"] == view
                and all(image.get(key) == value for key, value in match.items())]

    def pixels(self, image):
        cache = self.views["pixels"]
        if image["file"] not in cache:
            cache[image["file"]] = board_views.read_png(os.path.join(self.out, image["file"]))
        return cache[image["file"]]

    def tile_at(self, images, x, y):
        """The tile of a view covering the board point (x, y) in millimetres."""
        for image in images:
            box = image["region_mm"]
            if box["x0"] <= x < box["x1"] and box["y0"] <= y < box["y1"]:
                return image
        self.fail(f"no tile of {[image['file'] for image in images]} covers ({x}, {y}) mm")

    def colour_at(self, images, x, y):
        image = self.tile_at(images, x, y)
        box, scale = image["region_mm"], image["scale_px_per_mm"]
        _, _, rows = self.pixels(image)
        return rows[int((y - box["y0"]) * scale)][int((x - box["x0"]) * scale)][:3]

    def seen(self, images, x, y, colour, reach=0.1):
        """Whether the colour is drawn anywhere within `reach` millimetres of the board point (x, y)."""
        steps = [step / 30 for step in range(-round(reach * 30), round(reach * 30) + 1)]
        return any(self.partly(self.colour_at(images, x + dx, y + dy), colour) for dx in steps for dy in steps)

    def partly(self, found, colour):
        return board_fixtures.partly(found, colour, board_views.BACKGROUND)

    def near(self, found, colour, tolerance=40):
        return all(abs(a - b) <= tolerance for a, b in zip(found, hex_rgb(colour)))

    def layer_colour(self, layer):
        return board_views.LAYER_COLOURS[layer][0]

    def coverage(self, image, x, y_from, y_to, colour):
        """The pixels a colour covers down the column at board x between board y_from and y_to, partly covered
        pixels counted by how much of the colour they carry."""
        box, scale = image["region_mm"], image["scale_px_per_mm"]
        _, _, rows = self.pixels(image)
        column = int((x - box["x0"]) * scale)
        target = hex_rgb(colour)
        total = 0.0
        for row in range(round((y_from - box["y0"]) * scale), round((y_to - box["y0"]) * scale)):
            red = rows[row][column][0]
            total += (red - BACKGROUND[0]) / (target[0] - BACKGROUND[0])
        return total

    # --- Every view is written ---

    def test_every_view_is_written_as_a_png_on_a_dark_background(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        self.assertIn("RESULT | WRITTEN", self.views["result"].stdout)
        views = {image["view"] for image in self.index["images"]}
        self.assertEqual(views, {"layer", "assembly", "net", "class map", "crop", "3d"})
        written = sorted(name for name in os.listdir(self.out) if name.endswith(".png"))
        self.assertEqual(written, sorted(image["file"] for image in self.index["images"]))
        for image in self.index["images"]:
            with self.subTest(image=image["file"]):
                width, height, rows = self.pixels(image)
                corners = [rows[0][0][:3], rows[0][width - 1][:3], rows[height - 1][0][:3], rows[height - 1][width - 1][:3]]
                self.assertIn(BACKGROUND, corners, image["file"])
                dark = sum(1 for row in rows[::7] for pixel in row[::7] if sum(pixel[:3]) < 120)
                self.assertGreater(dark, 0.4 * len(rows[::7]) * len(rows[0][::7]), image["file"])

    def test_every_layer_the_board_carries_and_every_layer_holding_an_item_gets_an_image(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        layers = {image["layers"][0]["name"] for image in self.images("layer")}
        self.assertEqual(layers, set(board_views.REQUIRED_LAYERS) | {"Cmts.User", "Dwgs.User", "F.Fab", "F.CrtYd"})
        note = [image for image in self.images("layer") if image["layers"][0]["name"] == "Cmts.User"]
        self.assertTrue(note)
        lit = [self.colour_at(note, x / 10, y / 10) for x in range(270, 330, 2) for y in range(30, 50, 2)]
        self.assertTrue(any(sum(pixel) > 200 for pixel in lit), "the user-layer note is not drawn")

    def test_each_side_has_an_assembly_view_of_its_fab_silkscreen_and_courtyard_over_the_edge(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        for side, prefix in (("top", "F"), ("bottom", "B")):
            with self.subTest(side=side):
                images = self.images("assembly", side=side)
                self.assertTrue(images)
                self.assertEqual([layer["name"] for layer in images[0]["layers"]],
                                 ["Edge.Cuts", f"{prefix}.Fab", f"{prefix}.CrtYd", f"{prefix}.SilkS"])
        top = self.images("assembly", side="top")
        self.assertTrue(self.seen(top, 17.5, 20, self.layer_colour("F.CrtYd")), "U1's courtyard")
        self.assertTrue(self.seen(top, 18, 20, self.layer_colour("F.Fab")), "U1's fabrication outline")
        self.assertTrue(self.seen(top, 0, 20, self.layer_colour("Edge.Cuts")), "the board edge")
        self.assertTrue(self.seen(top, 20, 17, self.layer_colour("F.SilkS"), reach=0.6), "U1's reference")

    def test_the_three_dimensional_views_are_written_within_the_size_limit(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        solid = self.images("3d")
        self.assertEqual(sorted(image["file"] for image in solid), ["3d-angled.png", "3d-bottom.png", "3d-top.png"])
        for image in solid:
            with self.subTest(image=image["file"]):
                width, height = board_views.png_size(os.path.join(self.out, image["file"]))
                self.assertEqual(model_reads(width, height), (width, height))
                self.assertEqual((image["size_px"]["width"], image["size_px"]["height"]), (width, height))
                self.assertIn(image["direction"], image["caption"])
                self.assertIn(f"image {width} x {height} px", image["caption"])
                self.assertNotIn("px/mm", image["caption"])
                _, _, rows = self.pixels(image)
                board = sum(1 for row in rows[::5] for pixel in row[::5] if pixel[:3] != BACKGROUND)
                self.assertGreater(board, 100, "KiCad's render is not on the image")

    # --- A net's overlay ---

    def test_a_nets_overlay_holds_that_nets_copper_and_no_other(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        ground, power = self.images("net", net="GND"), self.images("net", net="+3V3")
        self.assertTrue(ground and power)
        self.assertEqual({image["net"] for image in self.images("net")}, {"GND", "+3V3"})
        blue, red = self.layer_colour("B.Cu"), self.layer_colour("F.Cu")
        self.assertTrue(self.near(self.colour_at(ground, 30, 35), blue), "the ground pour")
        self.assertTrue(self.near(self.colour_at(ground, 18, 21), red), "U1's ground pad")
        for x, y, what in ((30, 30, "the +3V3 track"), (35, 19, "SIG_A"), (18, 19, "U1's +3V3 pad")):
            found = self.colour_at(ground, x, y)
            self.assertFalse(self.near(found, blue) or self.near(found, red), f"{what} is drawn as ground: {found}")
        self.assertTrue(self.near(self.colour_at(power, 30, 30), blue), "the +3V3 track")
        self.assertFalse(self.near(self.colour_at(power, 30, 35), blue), "the ground pour is drawn as +3V3")
        self.assertNotEqual(self.colour_at(power, 30, 35), BACKGROUND, "the whole board is not drawn beneath the net")

    def test_a_nets_pour_is_drawn_with_the_fill_the_whole_board_gives_it(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        ground = self.images("net", net="GND")
        blue = self.layer_colour("B.Cu")
        for y in (30.4, 30.6, 29.4):
            with self.subTest(y=y):
                self.assertFalse(self.near(self.colour_at(ground, 30, y), blue),
                                 "the pour is refilled into the clearance the +3V3 track takes on the whole board")
        self.assertTrue(self.near(self.colour_at(ground, 30, 31.2), blue))

    def test_the_overlay_caption_names_each_layers_colour(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        for image in self.images("net"):
            with self.subTest(image=image["file"]):
                self.assertEqual(image["layers"], [{"name": "B.Cu", "colour": "blue"}, {"name": "F.Cu", "colour": "red"}])
                self.assertIn("layers B.Cu blue, F.Cu red", image["caption"])
                self.assertIn(f"net {image['net']}", image["caption"])
                self.assertIn(f"class {', '.join(image['classes'])}", image["caption"])

    # --- The class map ---

    def test_the_class_map_draws_each_critical_class_in_its_own_colour(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        mapped = self.images("class map")
        self.assertTrue(mapped)
        power, ground, sense = board_views.CLASS_COLOURS[:3]
        self.assertEqual(mapped[0]["classes"], [{"name": "Power", "colour": power[1]},
                                                {"name": "Ground", "colour": ground[1]},
                                                {"name": "Sense", "colour": sense[1]}])
        self.assertIn(f"Power {power[1]}, Ground {ground[1]}, Sense {sense[1]}", mapped[0]["caption"])
        self.assertTrue(self.near(self.colour_at(mapped, 30, 35), ground[0]), "the ground pour")
        found = self.colour_at(mapped, 35, 19)
        self.assertFalse(any(self.near(found, colour[0]) for colour in (power, ground, sense)), "SIG_A drawn as critical")

    def test_the_class_map_names_a_net_in_more_than_one_critical_class_and_draws_it_in_the_last_ones_colour(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        mapped = self.images("class map")
        power, sense = board_views.CLASS_COLOURS[0], board_views.CLASS_COLOURS[2]
        self.assertTrue(self.near(self.colour_at(mapped, 30, 30), sense[0]), "the +3V3 track, in Power and Sense")
        self.assertFalse(self.near(self.colour_at(mapped, 30, 30), power[0]))
        for image in mapped:
            with self.subTest(image=image["file"]):
                self.assertEqual(image["shared_nets"], {"+3V3": ["Power", "Sense"]})
                self.assertIn("nets in more than one critical class, drawn in the colour of the class named last: "
                              "+3V3 (Power, Sense)", image["caption"])
        overlay = self.images("net", net="+3V3")
        self.assertEqual(overlay[0]["classes"], ["Power", "Sense"])
        self.assertIn("class Power, Sense", overlay[0]["caption"])

    # --- Crops ---

    def test_each_crop_contains_its_circuit_and_its_decoupling_parts(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        crop = self.images("crop", circuit="U1")
        self.assertTrue(crop)
        self.assertEqual(crop[0]["supply_nets"], ["+3V3", "GND"])
        self.assertEqual(crop[0]["parts"], ["C1"])
        self.assertTrue(crop[0]["supply_nets_declared"] and crop[0]["decoupling_parts"])
        covered = self.covered(crop)
        for name, x, y, pad in (("U1", 20, 20, (18.3, 21)), ("C1", 4, 20, (4, 21))):
            with self.subTest(part=name):
                self.assertTrue(self.inside(covered, x, y), f"{name} is outside the crop {covered}")
                self.assertTrue(self.near(self.colour_at(crop, *pad), self.layer_colour("F.Cu")), f"{name}'s pad")
        for image in crop:
            self.assertIn("supply nets +3V3, GND", image["caption"])
            self.assertIn("decoupling parts, the two-pad parts across its supply nets nearer it than any other "
                          "circuit on them: C1", image["caption"])

    def covered(self, images):
        return (min(i["region_mm"]["x0"] for i in images), min(i["region_mm"]["y0"] for i in images),
                max(i["region_mm"]["x1"] for i in images), max(i["region_mm"]["y1"] for i in images))

    def inside(self, covered, x, y, reach=2.5):
        """Whether a part's outline, `reach` millimetres about (x, y), lies wholly within the covered region."""
        return covered[0] <= x - reach and x + reach <= covered[2] and covered[1] <= y - reach and y + reach <= covered[3]

    def touches(self, covered, x, y, reach=2.5):
        """Whether any of a part's outline, `reach` millimetres about (x, y), lies within the covered region."""
        return covered[0] < x + reach and x - reach < covered[2] and covered[1] < y + reach and y - reach < covered[3]

    def test_two_circuits_on_a_shared_rail_each_crop_only_their_own_decoupling_and_neither_spans_the_board(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        own = {"U1": ("C1", 4, 20, ("C2", 56, 20)), "U3": ("C2", 56, 20, ("C1", 4, 20))}
        for circuit, (part, x, y, (other, ox, oy)) in own.items():
            with self.subTest(circuit=circuit):
                crop = self.images("crop", circuit=circuit)
                self.assertTrue(crop)
                self.assertEqual(crop[0]["supply_nets"], ["+3V3", "GND"])
                self.assertEqual(crop[0]["parts"], [part])
                covered = self.covered(crop)
                self.assertTrue(self.inside(covered, x, y), f"{part} is outside {circuit}'s crop {covered}")
                self.assertFalse(self.touches(covered, ox, oy), f"{other} reaches into {circuit}'s crop {covered}")
                self.assertTrue(self.near(self.colour_at(crop, x, y + 1), self.layer_colour("F.Cu")), f"{part}'s pad")
                # The outline is 60 mm wide; a crop holding another circuit's decoupling on the rail spanned most of it.
                self.assertLess(covered[2] - covered[0], 30, f"{circuit}'s crop spans the board: {covered}")
                self.assertEqual(len(crop), 1, f"{circuit}'s crop is tiled, so it is larger than its circuit")
                self.assertNotIn(other, crop[0]["caption"])

    def test_a_circuit_whose_rails_only_candidates_sit_nearer_other_circuits_is_marked_as_having_no_decoupling(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        crop = self.images("crop", circuit="U4")
        self.assertTrue(crop)
        self.assertEqual((crop[0]["supply_nets"], crop[0]["parts"]), (["+3V3", "GND"], []))
        self.assertTrue(crop[0]["supply_nets_declared"])
        self.assertFalse(crop[0]["decoupling_parts"])
        covered = self.covered(crop)
        for other, x, y in (("C1", 4, 20), ("C2", 56, 20)):
            self.assertFalse(self.touches(covered, x, y), f"{other} reaches into U4's crop {covered}")
        marked = ("no decoupling parts: no two-pad part across its supply nets is nearer it than every other circuit "
                  "on them")
        with open(os.path.join(self.out, "index.txt"), encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        for image in crop:
            self.assertIn(marked, image["caption"])
            line = next(line for line in lines if line.startswith(f"IMAGE | {image['file']} |"))
            self.assertIn(marked, line)
        for circuit in ("U1", "U3"):
            self.assertNotIn("no decoupling parts", self.images("crop", circuit=circuit)[0]["caption"])

    def test_a_circuit_with_no_power_typed_pad_gets_its_crop_marked_as_declaring_no_supply_nets(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        crop = self.images("crop", circuit="U2")
        self.assertTrue(crop)
        self.assertFalse(crop[0]["supply_nets_declared"])
        self.assertEqual((crop[0]["supply_nets"], crop[0]["parts"]), ([], []))
        self.assertTrue(self.near(self.colour_at(crop, 44, 8), self.layer_colour("F.Cu")), "U2's pad")
        with open(os.path.join(self.out, "index.txt"), encoding="utf-8") as handle:
            line = next(line for line in handle if line.startswith(f"IMAGE | {crop[0]['file']} |"))
        self.assertIn("no supply nets declared", line)
        self.assertEqual({image["circuit"] for image in self.images("crop")}, {"U1", "U2", "U3", "U4"})

    # --- Resolution and size ---

    def test_each_crop_and_tile_meets_the_derived_resolution_and_is_read_without_downsampling(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        self.assertEqual(self.index["resolution"]["px_per_mm"], SCALE)
        flat = [image for image in self.index["images"] if image["view"] != "3d"]
        for image in flat:
            with self.subTest(image=image["file"]):
                width, height = board_views.png_size(os.path.join(self.out, image["file"]))
                self.assertEqual((width, height), (image["size_px"]["width"], image["size_px"]["height"]))
                read = model_reads(width, height)
                self.assertEqual(read, (width, height), "a reviewing model would downsample this image")
                box, content = image["region_mm"], image["content_px"]
                for pixels, span in ((content["width"], box["x1"] - box["x0"]), (content["height"], box["y1"] - box["y0"])):
                    read_scale = pixels * (read[0] / width) / span
                    self.assertGreaterEqual(read_scale * MINIMUM_MM, 3 - 1e-6)
                self.assertLessEqual(content["height"], height)

    def test_the_smallest_track_and_clearance_each_span_three_pixels_in_the_image(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        front = self.images("layer", layers=[{"name": "F.Cu", "colour": "red"}])
        image = self.tile_at(front, 35, 19)
        red = self.layer_colour("F.Cu")
        track = self.coverage(image, 35, 18.9, 19.1, red)
        gap = (19.2 - 19.0) * image["scale_px_per_mm"] - self.coverage(image, 35, 19.0, 19.2, red)
        # Antialiasing spreads each edge over the pixels it crosses, so the span is measured as the colour's total
        # coverage, which a pixel grid at the derived resolution makes three pixels exactly.
        self.assertGreater(track, 2.85, f"the minimum-width track spans {track:.2f} px")
        self.assertGreater(gap, 2.85, f"the minimum clearance spans {gap:.2f} px")

    def test_every_whole_board_view_larger_than_the_limit_is_tiled_and_its_tiles_cover_the_board(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        groups = {}
        for image in self.index["images"]:
            if image["view"] in ("layer", "assembly", "net", "class map"):
                groups.setdefault(image["file"].rsplit("-r", 1)[0], []).append(image)
        self.assertTrue(groups)
        for name, images in groups.items():
            with self.subTest(view=name):
                self.assertGreater(len(images), 1, "62 mm at 30 px/mm is wider than the long edge, so it is tiled")
                self.assertEqual(len(images), images[0]["tile"]["rows"] * images[0]["tile"]["columns"])
                self.assertLessEqual(min(i["region_mm"]["x0"] for i in images), 0)
                self.assertLessEqual(min(i["region_mm"]["y0"] for i in images), 0)
                self.assertGreaterEqual(max(i["region_mm"]["x1"] for i in images), 60)
                self.assertGreaterEqual(max(i["region_mm"]["y1"] for i in images), 40)
                for image in images:
                    self.assertIn(f"tile row {image['tile']['row']} of {image['tile']['rows']}", image["caption"])

    # --- Captions, index and facts ---

    def test_each_image_carries_its_caption_drawn_into_it(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        for image in self.index["images"]:
            with self.subTest(image=image["file"]):
                width, height, rows = self.pixels(image)
                top = (image["content_px"] if "content_px" in image else image["render_px"])["height"]
                lines = board_views.wrapped(image["caption"], width)
                needed = len(lines) * board_views.LINE_PX + 2 * board_views.CAPTION_PAD_PX
                if image["view"] == "3d":
                    self.assertGreaterEqual(height - top, needed)
                else:
                    self.assertEqual(height - top, needed)
                text = sum(1 for row in rows[top + 2:] for pixel in row if sum(pixel[:3]) > 450)
                self.assertGreater(text, 40 * len(lines), "no caption text is drawn")
                if image["view"] != "3d":
                    box = image["region_mm"]
                    self.assertIn(f"{board_views.scale_text(SCALE)} | board x {board_views.mm_text(box['x0'])} to "
                                  f"{board_views.mm_text(box['x1'])} mm, y {board_views.mm_text(box['y0'])} to "
                                  f"{board_views.mm_text(box['y1'])} mm", image["caption"])
                    for layer in image["layers"]:
                        self.assertIn(layer["name"], image["caption"])

    def test_the_index_lists_every_image_with_its_caption_fields_as_text_and_json(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        with open(os.path.join(self.out, "index.txt"), encoding="utf-8") as handle:
            text = handle.read().splitlines()
        self.assertEqual([line for line in text if line.startswith("IMAGE | ")],
                         [f"IMAGE | {image['file']} | {image['caption']}" for image in self.index["images"]])
        self.assertIn("RESOLUTION | 30 px/mm | 3 px across the smaller of the minimum track width 0.1 mm and the "
                      "minimum clearance 0.1 mm", text)
        self.assertIn("CLASS | Power | +3V3", text)
        self.assertIn("CLASS | Ground | GND", text)
        self.assertIn("CLASS | Sense | +3V3", text)
        self.assertEqual(self.index["resolution"]["min_track_width_mm"], MINIMUM_MM)
        self.assertEqual(self.index["image_limit"], {"long_edge_px": 1568, "patches": 1568, "patch_px": 28})
        self.assertEqual(self.index["critical_classes"], {"Power": ["+3V3"], "Ground": ["GND"], "Sense": ["+3V3"]})
        for image in self.index["images"]:
            fields = {"file", "view", "caption", "size_px"} | ({"direction", "zoom", "render_px"} if image["view"] == "3d" else
                                                              {"layers", "scale_px_per_mm", "region_mm", "tile",
                                                               "rule_areas", "absent_layers"})
            self.assertLessEqual(fields, set(image), image["file"])
        overlay = self.images("net", net="GND")[0]
        self.assertEqual((overlay["classes"], overlay["scale_px_per_mm"]), (["Ground"], SCALE))

    def test_the_fact_table_gives_each_nets_track_widths_vias_zones_and_class_as_text_and_json(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        facts = {fact["net"]: fact for fact in self.views["facts"]["nets"]}
        self.assertEqual(set(facts), {"+3V3", "GND", "SIG_A", "SIG_B"})
        self.assertEqual(facts["+3V3"], {"net": "+3V3", "classes": ["Power", "Sense"], "track_width_mm": {"min": 0.3, "max": 0.5},
                                         "vias": 1, "zones": []})
        self.assertEqual(facts["GND"], {"net": "GND", "classes": ["Ground"], "track_width_mm": None, "vias": 0,
                                        "zones": [{"layers": ["B.Cu"]}]})
        self.assertEqual(facts["SIG_A"], {"net": "SIG_A", "classes": ["Default"],
                                          "track_width_mm": {"min": 0.1, "max": 0.1}, "vias": 0, "zones": []})
        with open(os.path.join(self.out, "facts.txt"), encoding="utf-8") as handle:
            text = handle.read().splitlines()
        self.assertEqual(text, [
            "NET +3V3 | class Power, Sense | tracks 0.3 to 0.5 mm wide | 1 via | no zones",
            "NET GND | class Ground | no tracks | 0 vias | 1 zone on B.Cu",
            "NET SIG_A | class Default | tracks 0.1 to 0.1 mm wide | 0 vias | no zones",
            "NET SIG_B | class Default | tracks 0.1 to 0.1 mm wide | 0 vias | no zones",
        ])

    def test_the_render_leaves_the_design_folder_untouched(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        design = self.views["design"]
        self.assertEqual(sorted(os.listdir(design.folder)), ["models", "proof.kicad_pcb", "proof.kicad_pro"])
        with open(design.board, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), layout())

    # --- Nothing left out quietly ---

    def red(self, pixel):
        return pixel[0] > 140 and pixel[1] < 70 and pixel[2] < 70

    def test_a_model_the_design_keeps_in_its_own_folder_is_drawn_in_three_dimensions(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        unseen = {part["reference"]: part["reason"] for part in self.index["not_in_3d"]}
        self.assertEqual(unseen, {"C1": "no model", "C2": "model not found", "D1": "not populated",
                                  "J1": "no model", "R1": "model hidden", "R5": "no model", "U3": "no model",
                                  "U4": "no model"})
        top = self.images("3d", file="3d-top.png")[0]
        _, _, rows = self.pixels(top)
        across, down = top["render_px"]["width"], top["render_px"]["height"]
        reds = [x for row in rows[:down] for x, pixel in enumerate(row[:across]) if self.red(pixel)]
        # Seen from the top, x on the board runs across the image: U1's model, named through ${KIPRJMOD}, sits a
        # third of the way across, and U2's, named from the design's folder with no variable, three quarters.
        self.assertTrue(any(x < across * 0.5 for x in reds), "U1's model in the design's folder is not drawn")
        self.assertTrue(any(x > across * 0.6 for x in reds), "U2's model named from the design's folder is not drawn")

    def test_a_part_drawn_without_its_model_is_named_in_the_captions_the_index_and_the_report(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        missing = "KiCad cannot find its model: File not found: ${KIPRJMOD}/models/missing.step"
        report = self.views["result"].stdout.splitlines()
        self.assertIn(f"MODEL | C2 | {missing}; the three-dimensional views' captions and the index name it", report)
        # Whatever the reason a part is drawn without its model, the report names it, not only a model not found.
        for name, detail in (("C1", "it declares no model"), ("R1", "the design hides its model"),
                             ("D1", "marked do not populate, so the render leaves it out")):
            self.assertIn(f"MODEL | {name} | {detail}; the three-dimensional views' captions and the index name it",
                          report)
        for name in ("U1", "U2"):
            self.assertFalse(any(line.startswith(f"MODEL | {name} |") for line in report), name)
        with open(os.path.join(self.out, "index.json"), encoding="utf-8") as handle:
            unseen = json.load(handle)["not_in_3d"]
        self.assertEqual(sorted(line.split(" | ")[1] for line in report if line.startswith("MODEL | ")),
                         sorted(part["reference"] for part in unseen))
        with open(os.path.join(self.out, "index.txt"), encoding="utf-8") as handle:
            text = handle.read().splitlines()
        self.assertIn(f"NOT IN 3D | C2 | {missing}", text)
        self.assertIn("NOT IN 3D | C1 | it declares no model", text)
        self.assertIn("NOT IN 3D | R1 | the design hides its model", text)
        self.assertIn("NOT IN 3D | D1 | marked do not populate, so the render leaves it out", text)
        for image in self.images("3d"):
            with self.subTest(image=image["file"]):
                for words in ("drawn without a model KiCad cannot find: C2", "declaring none: C1",
                              "the design hiding it: R1", "marked do not populate: D1"):
                    self.assertIn(words, image["caption"])
                self.assertNotIn("U1", image["caption"])

    def test_a_three_dimensional_view_is_zoomed_out_until_no_part_reaches_its_frame(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        angled = self.images("3d", file="3d-angled.png")[0]
        self.assertLess(angled["zoom"], 1, "U2's 61 mm model runs out of the angled view at KiCad's own framing")
        self.assertIn(f"zoomed out to {angled['zoom']:.3g} so no part reaches the frame", angled["caption"])
        for image in self.images("3d"):
            with self.subTest(image=image["file"]):
                _, _, rows = self.pixels(image)
                across, down = image["render_px"]["width"], image["render_px"]["height"]
                edge = rows[0][:across] + rows[down - 1][:across] + [rows[y][x] for y in range(down)
                                                                     for x in (0, across - 1)]
                self.assertTrue(all(pixel[:3] == BACKGROUND for pixel in edge), "a part reaches the frame")
        _, _, rows = self.pixels(angled)
        tallest = min(y for y, row in enumerate(rows[:angled["render_px"]["height"]]) if any(map(self.red, row)))
        self.assertGreater(tallest, 0, "the top of U2's model is cut off")

    def test_a_rule_area_kicad_does_not_plot_is_drawn_and_named(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        for layer in ("Dwgs.User", "F.Cu"):
            with self.subTest(layer=layer):
                images = [image for image in self.images("layer") if image["layers"][0]["name"] == layer]
                self.assertTrue(self.seen(images, 53, 4, board_views.RULE_AREA[0], reach=0.3), "the hatching")
                self.assertTrue(self.seen(images, 50, 2.6, board_views.RULE_AREA[0], reach=0.3), "the outline")
                self.assertFalse(self.seen(images, 47, 4, board_views.RULE_AREA[0], reach=0.3), "outside it")
                for image in images:
                    self.assertEqual([area["name"] for area in image["rule_areas"]], ["KO1"])
                    self.assertIn("rule areas, which KiCad does not plot, drawn as bright orange dashed hatched "
                                  "outlines: KO1 on F.Cu, Dwgs.User (no tracks, vias or copper pour)", image["caption"])
        for image in self.images("layer"):
            if image["layers"][0]["name"] not in ("Dwgs.User", "F.Cu"):
                self.assertEqual(image["rule_areas"], [], image["file"])
        self.assertEqual([area["name"] for area in self.images("crop", circuit="U2")[0]["rule_areas"]], ["KO1"])
        self.assertEqual(self.images("crop", circuit="U1")[0]["rule_areas"], [], "KO1 is nowhere near U1")
        with open(os.path.join(self.out, "index.txt"), encoding="utf-8") as handle:
            self.assertIn("RULE AREA | KO1 | on F.Cu, Dwgs.User, no tracks, vias or copper pour; KiCad does not plot "
                          "it, so the views draw it as a bright orange dashed hatched outline", handle.read())

    def test_a_net_overlay_and_the_class_map_crossing_a_copper_rule_area_show_and_name_it(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        power = self.images("net", net="+3V3")
        self.assertTrue(self.near(self.colour_at(power, 49, 4), self.layer_colour("F.Cu")), "the +3V3 track")
        named = ("rule areas, which KiCad does not plot, drawn as bright orange dashed hatched outlines: KO1 on F.Cu, "
                 "Dwgs.User (no tracks, vias or copper pour)")
        for view, images in (("net +3V3", power), ("net GND", self.images("net", net="GND")),
                             ("class map", self.images("class map"))):
            with self.subTest(view=view):
                self.assertTrue(self.seen(images, 53, 5, board_views.RULE_AREA[0], reach=0.3), "the hatching")
                self.assertTrue(self.seen(images, 50, 2.6, board_views.RULE_AREA[0], reach=0.3), "the outline")
                self.assertFalse(self.seen(images, 46, 4, board_views.RULE_AREA[0], reach=0.3), "outside it")
                for image in images:
                    self.assertEqual([area["name"] for area in image["rule_areas"]], ["KO1"], image["file"])
                    self.assertIn(named, image["caption"], image["file"])

    def test_every_whole_board_view_frames_whatever_its_layers_hold_beyond_the_outline(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        groups = {}
        for image in self.index["images"]:
            if image["view"] in ("layer", "assembly", "net", "class map"):
                groups.setdefault(image["file"].rsplit("-r", 1)[0], []).append(image)
        for name, images in groups.items():
            with self.subTest(view=name):
                # J1's courtyard reaches x = 64.5 mm and the text below the board y = 45.75 mm, past the outline's
                # 60 by 40 mm.
                self.assertGreaterEqual(max(i["region_mm"]["x1"] for i in images), 64.5 + board_views.BOARD_MARGIN_MM)
                self.assertGreaterEqual(max(i["region_mm"]["y1"] for i in images), 45.7 + board_views.BOARD_MARGIN_MM)
        top = self.images("assembly", side="top")
        self.assertTrue(self.seen(top, 64.5, 12, self.layer_colour("F.CrtYd")), "J1's courtyard past the edge")
        self.assertTrue(self.seen(top, 64, 12, self.layer_colour("F.Fab")), "J1's fabrication outline past the edge")
        self.assertTrue(self.seen(top, 30, 45, self.layer_colour("F.SilkS"), reach=1.0), "the text below the board")
        silk = [image for image in self.images("layer") if image["layers"][0]["name"] == "F.SilkS"]
        self.assertTrue(self.seen(silk, 30, 45, self.layer_colour("F.SilkS"), reach=1.0), "the text below the board")
        courtyard = [image for image in self.images("layer") if image["layers"][0]["name"] == "F.CrtYd"]
        self.assertTrue(self.seen(courtyard, 64.5, 12, self.layer_colour("F.CrtYd")), "J1's courtyard past the edge")

    def test_turned_and_mirrored_items_kicad_plots_through_transforms_are_drawn_inside_the_frame(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        groups = {}
        for image in self.index["images"]:
            if image["view"] in ("layer", "assembly", "net", "class map"):
                groups.setdefault(image["file"].rsplit("-r", 1)[0], []).append(image)
        for name, images in groups.items():
            with self.subTest(view=name):
                # The mirrored back text's strokes reach x = -8.7 mm and the turned text's y = -6.06 mm, past the
                # outline's left and top edges at 0.
                self.assertLessEqual(min(i["region_mm"]["x0"] for i in images), -8.7 - board_views.BOARD_MARGIN_MM)
                self.assertLessEqual(min(i["region_mm"]["y0"] for i in images), -6.06 - board_views.BOARD_MARGIN_MM)
        for view, images in (("layer B.SilkS", [image for image in self.images("layer")
                                                if image["layers"][0]["name"] == "B.SilkS"]),
                             ("assembly bottom", self.images("assembly", side="bottom"))):
            with self.subTest(view=view):
                self.assertTrue(self.seen(images, -6, 20, self.layer_colour("B.SilkS"), reach=1.0), "the mirrored text")
        for view, images in (("layer F.SilkS", [image for image in self.images("layer")
                                                if image["layers"][0]["name"] == "F.SilkS"]),
                             ("assembly top", self.images("assembly", side="top"))):
            with self.subTest(view=view):
                self.assertTrue(self.seen(images, 30, -4, self.layer_colour("F.SilkS"), reach=1.0), "the turned text")
                self.assertTrue(self.seen(images, 35, 30, self.layer_colour("F.SilkS"), reach=0.6), "R5's reference")

    def test_a_font_kicad_substitutes_is_named_in_every_caption_the_index_and_the_report(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        substituted = self.index["fonts_substituted"]
        self.assertEqual([font["font"] for font in substituted], [NO_SUCH_FONT])
        instead = substituted[0]["drawn_in"]
        self.assertTrue(instead and instead != NO_SUCH_FONT)
        self.assertIn(f"FONT | {NO_SUCH_FONT} | KiCad cannot find this font and drew its text in {instead}",
                      self.views["result"].stdout)
        with open(os.path.join(self.out, "index.txt"), encoding="utf-8") as handle:
            self.assertIn(f"FONT | {NO_SUCH_FONT} | not found, so KiCad drew its text in {instead}", handle.read())
        for image in self.index["images"]:
            self.assertIn(f"fonts KiCad could not find, their text drawn in another: {NO_SUCH_FONT} drawn in "
                          f"{instead}", image["caption"], image["file"])

    def test_a_board_carrying_every_layer_names_none_as_missing(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        self.assertEqual(self.index["layers_not_carried"], [])
        self.assertNotIn("LAYER | ", self.views["result"].stdout)
        for image in self.index["images"]:
            self.assertNotIn("not carried by the board", image["caption"], image["file"])


class Lacking(unittest.TestCase):
    """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""

    def test_a_fabrication_or_courtyard_layer_the_board_does_not_carry_is_named_where_it_would_be_drawn(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        kept = [entry for entry in LAYER_TABLE if '"B.Fab"' not in entry and '"B.CrtYd"' not in entry]
        design = Design(layout(layers=kept))
        status, lines, errors = design.run()
        self.assertEqual(status, 0, lines + [errors])
        for layer in ("B.Fab", "B.CrtYd"):
            self.assertIn(f"LAYER | {layer} | the board does not carry this layer, so the views that show it leave it "
                          "out; the captions and the index name it", lines)
        with open(os.path.join(design.out, "index.json"), encoding="utf-8") as handle:
            index = json.load(handle)
        self.assertEqual(index["layers_not_carried"], ["B.Fab", "B.CrtYd"])
        bottom = [image for image in index["images"] if image["view"] == "assembly" and image["side"] == "bottom"]
        top = [image for image in index["images"] if image["view"] == "assembly" and image["side"] == "top"]
        self.assertTrue(bottom and top)
        for image in bottom:
            self.assertEqual(image["absent_layers"], ["B.Fab", "B.CrtYd"])
            self.assertEqual([layer["name"] for layer in image["layers"]], ["Edge.Cuts", "B.SilkS"])
            self.assertIn("B.Fab, B.CrtYd not carried by the board, so not drawn", image["caption"])
        for image in top:
            self.assertEqual(image["absent_layers"], [])
            self.assertNotIn("not carried", image["caption"])
        with open(os.path.join(design.out, "index.txt"), encoding="utf-8") as handle:
            self.assertIn("LAYER | B.Fab | not carried by the board, so the views that show it leave it out",
                          handle.read())


class Pieces(unittest.TestCase):
    """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""

    def test_the_copy_keeps_the_designs_names_and_finds_its_models_as_the_design_does_in_place(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        paths = ["${KIPRJMOD}/models/box.wrl", "$(KIPRJMOD)/models/box.wrl", "models/box.wrl", "models/nowhere.step",
                 "${KICAD10_3DMODEL_DIR}/Resistor_SMD.3dshapes/R_0603_1608Metric.step", "/elsewhere/part.step",
                 "kicad-embed://part.step"]
        parts = [footprint(f"P{index}", 5 + 5 * index, 30, [], [model(path)]) for index, path in enumerate(paths)]
        design = Design(layout(items=parts))
        with open(os.path.join(design.folder, "proof.kicad_dru"), "w", encoding="utf-8") as handle:
            handle.write("(version 1)\n")
        with tempfile.TemporaryDirectory(prefix="board-views-stage-") as work:
            staged, written = board_views.stage(design.board, design.project, work)
            self.assertEqual(os.path.basename(staged), "proof.kicad_pcb")
            self.assertEqual(sorted(os.listdir(os.path.dirname(staged))),
                             ["proof.kicad_dru", "proof.kicad_pcb", "proof.kicad_pro"])
            copied = board_views.locked_copper.read_layout(staged)
        found = [board_views.unquoted(board_views.sexpr.child(node, "model")[1])
                 for node in copied[1:] if board_views.sexpr.head(node) == "footprint"]
        box = os.path.join(os.path.abspath(design.folder), "models", "box.wrl")
        self.assertEqual(found, [box, box, box] + paths[3:])
        self.assertEqual(set(written), {box})
        self.assertIn(written[box], paths[:3])

    def test_kicad_is_set_to_report_in_english_whatever_it_was_set_to(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        design = Design()
        with tempfile.TemporaryDirectory(prefix="board-views-home-") as home:
            environment = board_check.isolate_kicad(KICAD_CLI, board_check.require_kicad(KICAD_CLI), home)
            common = os.path.join(home, os.listdir(home)[0], "kicad_common.json")
            with open(common, encoding="utf-8") as handle:
                settings = json.load(handle)
            settings["system"]["language"] = "Deutsch"
            with open(common, "w", encoding="utf-8") as handle:
                json.dump(settings, handle)
            board_views.english(home)
            with open(common, encoding="utf-8") as handle:
                self.assertEqual(json.load(handle)["system"]["language"], "English")
            result = subprocess.run([KICAD_CLI, "pcb", "export", "glb", "--no-board-body", "-o",
                                     os.path.join(design.root, "models.glb"), design.board], env=environment,
                                    capture_output=True, text=True, timeout=600)
        self.assertEqual(board_views.MODEL_NOT_ADDED.findall(result.stdout + "\n" + result.stderr),
                         [("C2", "File not found: ${KIPRJMOD}/models/missing.step")])
        with tempfile.TemporaryDirectory(prefix="board-views-home-") as empty:
            with self.assertRaises(board_check.CannotRun):
                board_views.english(empty)

    def test_nine_or_more_critical_classes_each_get_their_own_colour_named_apart_in_the_caption(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        self.assertEqual(board_views.class_colours(3), list(board_views.CLASS_COLOURS[:3]))
        for count in (len(board_views.CLASS_COLOURS) + 1, 12, 40, 600):
            with self.subTest(count=count):
                colours = board_views.class_colours(count)
                self.assertEqual(colours[:len(board_views.CLASS_COLOURS)], list(board_views.CLASS_COLOURS))
                self.assertEqual(len({value for value, _ in colours}), count, "two classes drawn alike")
                self.assertEqual(len({name for _, name in colours}), count, "two classes named alike")
                for value, name in colours[len(board_views.CLASS_COLOURS):]:
                    self.assertRegex(value, r"^#[0-9a-f]{6}$")
                    self.assertEqual(name, value, "a colour past the named ones is named by its hex value")
        classes = [f"Class{index}" for index in range(1, 10)]
        caption = board_views.colour_list([(name, colour[1]) for name, colour in
                                           zip(classes, board_views.class_colours(len(classes)))])
        named = caption.split(", ")
        self.assertEqual(len(named), 9)
        self.assertEqual(len({entry.split(" ", 1)[1] for entry in named}), 9, caption)
        self.assertNotIn("Class9 red", caption)

    def test_a_net_in_more_than_one_critical_class_is_named_on_the_class_map(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        membership = {"Power": {"+3V3", "+5V"}, "Sense": {"+3V3", "ADC"}, "Ground": {"GND"}}
        self.assertEqual(board_views.shared_nets(["Power", "Sense", "Ground"], membership),
                         {"+3V3": ["Power", "Sense"]})
        self.assertEqual(board_views.shared_nets(["Ground"], membership), {})

    def test_the_extent_of_a_plot_holds_everything_drawn_in_it_strokes_included(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        cases = (
            ('<path style="stroke-width:0.2;stroke-linejoin:round" d="M 1,2\n3,4\nZ" />', (0.9, 1.9, 3.1, 4.1)),
            # A mitred corner, the default, reaches up to the miter limit, by default 4, times the half-width.
            ('<path style="stroke:#000;stroke-width:0.2" d="M 0 0 L 1 0 L 1 1" />', (-0.4, -0.4, 1.4, 1.4)),
            ('<g transform="translate(5 0)"><path d="M 0 0 1 1" /></g>', (5, 0, 6, 1)),
            ('<path d="m 1 1 h 2 v 3 l -4 1" />', (-1, 1, 3, 5)),
            # Over the top of a circle of radius 5 about (5, 0), the arc reaches y = -5.
            ('<path d="M 0 0 A 5 5 0 0 1 10 0" />', (0, -5, 10, 0)),
            ('<path d="M 0 0 A 5 5 0 0 0 10 0" />', (0, 0, 10, 5)),
            ('<circle cx="70" cy="-3" r="2" />', (68, -5, 72, -1)),
            ('<rect x="-4" y="50" width="2" height="3" />', (-4, 50, -2, 53)),
            ('<polygon points="5,5 9,1 2,8" />', (2, 1, 9, 8)),
            ('<g style="stroke-width:1"><line x1="0" y1="0" x2="10" y2="0" /></g>', (-0.5, -0.5, 10.5, 0.5)),
        )
        with tempfile.TemporaryDirectory(prefix="board-views-extent-") as folder:
            path = os.path.join(folder, "layer.svg")
            for body, expected in cases:
                with self.subTest(body=body):
                    with open(path, "w", encoding="utf-8") as handle:
                        handle.write(f'<svg viewBox="0 0 297 210"><g transform="translate(0 0) scale(1 1)">{body}'
                                     '<text x="900" y="900" opacity="0">hidden</text></g></svg>')
                    found = board_views.drawn_extent(path)
                    for got, want in zip(found, expected):
                        self.assertAlmostEqual(got, want, places=3)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write('<svg viewBox="0 0 297 210"></svg>')
            self.assertIsNone(board_views.drawn_extent(path))
            for body in ('<path d="M 0 0 L 1" />', '<path d="3 4" />'):
                with self.subTest(body=body):
                    with open(path, "w", encoding="utf-8") as handle:
                        handle.write(f'<svg viewBox="0 0 297 210">{body}</svg>')
                    with self.assertRaises(board_views.Unreadable):
                        board_views.drawn_extent(path)

    def test_a_caption_names_at_most_its_share_and_leaves_the_rest_to_the_index(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        names = [f"R{index}" for index in range(1, board_views.CAPTION_NAMES + 4)]
        self.assertEqual(board_views.named(names[:3]), "R1, R2, R3")
        self.assertTrue(board_views.named(names).endswith(
            f"R{board_views.CAPTION_NAMES} and 3 more, which the index names"))

    def circuits(self, items):
        design = Design(layout(items=items))
        return {circuit["reference"]: circuit
                for circuit in board_views.circuits(board_views.locked_copper.read_layout(design.board))}

    def rail(self, reference, x, y, *extra):
        return footprint(reference, x, y, [pad(1, -2, -1, "+3V3", "power_in"), pad(2, -2, 1, "GND", "power_in"),
                                           pad(3, 2, 0, "SIG_A", "input"), *extra])

    def capacitor(self, reference, x, y):
        return footprint(reference, x, y, [pad(1, 0, -1, "+3V3", "passive"), pad(2, 0, 1, "GND", "passive")])

    def test_each_decoupling_part_on_a_shared_rail_belongs_only_to_the_circuit_nearest_it(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        found = self.circuits([self.rail("U1", 10, 10), self.capacitor("C1", 4, 10),
                               self.rail("U3", 90, 60), self.capacitor("C9", 96, 60)])
        self.assertEqual((found["U1"]["parts"], found["U3"]["parts"]), (["C1"], ["C9"]))
        self.assertLess(found["U1"]["bounds"][2], 20, "U1's crop reaches toward U3")
        self.assertGreater(found["U3"]["bounds"][0], 80, "U3's crop reaches toward U1")
        # With its own capacitor gone, U1 holds none: U3's is never shown as U1's.
        found = self.circuits([self.rail("U1", 10, 10), self.rail("U3", 90, 60), self.capacitor("C9", 96, 60)])
        self.assertEqual((found["U1"]["parts"], found["U3"]["parts"]), ([], ["C9"]))
        self.assertEqual(board_views.crop_fields(dict(found["U1"], side="top"))[-1],
                         "no decoupling parts: no two-pad part across its supply nets is nearer it than every other "
                         "circuit on them")

    def test_a_decoupling_part_goes_to_the_circuit_whose_nearest_pad_is_closest_not_whose_centre_is(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        # U1 is centred 17 mm from C1, but its supply pads reach to 2 mm from it; U2 is centred 7 mm away and its
        # nearest pad is 5 mm away.
        wide = footprint("U1", 20, 10, [pad(1, -15, -1, "+3V3", "power_in"), pad(2, -15, 1, "GND", "power_in"),
                                        pad(3, 5, 0, "SIG_A", "input")])
        found = self.circuits([wide, self.rail("U2", 10, 10), self.capacitor("C1", 3, 10)])
        self.assertEqual((found["U1"]["parts"], found["U2"]["parts"]), (["C1"], []))
        # Equally near two circuits, a part goes to the earlier reference, and to only one of them.
        found = self.circuits([self.rail("U2", 0, 0), self.rail("U10", 8, 0), self.capacitor("C1", 2, 20)])
        self.assertEqual((found["U2"]["parts"], found["U10"]["parts"]), (["C1"], []))

    def test_a_part_on_rails_another_circuit_does_not_share_is_never_its_decoupling(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        five = footprint("U5", 50, 10, [pad(1, -2, -1, "+5V", "power_in"), pad(2, -2, 1, "GND", "power_in"),
                                        pad(3, 2, 0, "SIG_A", "input")])
        # C1 is far nearer U5, but U5 is not on +3V3, so it is U1's.
        found = self.circuits([self.rail("U1", 10, 10), five, self.capacitor("C1", 48, 10)])
        self.assertEqual((found["U1"]["parts"], found["U5"]["parts"]), (["C1"], []))

    def test_a_two_pad_integrated_circuit_on_the_rail_is_never_another_circuits_decoupling(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        # U7 has two pads, one on each of U1's supply nets and right beside it, but is itself a circuit.
        own = footprint("U7", 14, 10, [pad(1, 0, -1, "+3V3", "power_in"), pad(2, 0, 1, "GND", "power_in")])
        found = self.circuits([self.rail("U1", 10, 10), own, self.capacitor("C1", 4, 10)])
        self.assertEqual((found["U1"]["parts"], found["U7"]["parts"]), (["C1"], []))
        self.assertLess(found["U1"]["bounds"][2], 13, "U1's crop is framed on U7")

    def test_a_part_with_both_pads_on_one_net_is_never_decoupling(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        # FB1 and C2 each sit beside U1 with both pads on one of its supply nets: neither is one rail and one return.
        bead = footprint("FB1", 4, 10, [pad(1, 0, -1, "+3V3", "passive"), pad(2, 0, 1, "+3V3", "passive")])
        grounded = footprint("C2", 16, 10, [pad(1, 0, -1, "GND", "passive"), pad(2, 0, 1, "GND", "passive")])
        found = self.circuits([self.rail("U1", 10, 10), bead, grounded])
        self.assertEqual(found["U1"]["parts"], [])
        self.assertEqual(board_views.crop_fields(dict(found["U1"], side="top"))[-1],
                         "no decoupling parts: no two-pad part across its supply nets is nearer it than every other "
                         "circuit on them")

    def test_a_crops_supply_nets_and_parts_are_capped_and_its_caption_still_tiles(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        circuit = {"reference": "U1", "side": "top", "supply_nets": [f"N{index}" for index in range(1200)],
                   "parts": [f"C{index}" for index in range(1200)]}
        fields = board_views.crop_fields(circuit)
        more = f"and {1200 - board_views.CAPTION_NAMES} more, which the index names"
        self.assertTrue(fields[1].startswith("supply nets N0, N1") and fields[1].endswith(more), fields[1])
        self.assertTrue(fields[2].endswith(more), fields[2])
        self.assertNotIn(f"C{board_views.CAPTION_NAMES}", fields[2].split(": ", 1)[1].split(" and ")[0])
        planned = board_views.tiles((0, 0, 10, 10), SCALE, lambda tile: " | ".join(fields), "the view crop-U1")
        self.assertEqual(len(planned), 1)
        self.assertTrue(board_views.fits(*planned[0]["size"]))

    def test_a_caption_too_tall_for_any_tile_is_refused_at_once_naming_the_view(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        caption = "parts on them " + ", ".join(f"C{index}" for index in range(1200))
        started = time.monotonic()
        with self.assertRaises(board_views.Unreadable) as raised:
            board_views.tiles((0, 0, 10, 10), SCALE, lambda tile: caption, "the view crop-U1")
        self.assertLess(time.monotonic() - started, 5, "the refusal came only after a search")
        self.assertIn("the caption of the view crop-U1 is", str(raised.exception))
        self.assertIn("no tile of it fits within the size limit", str(raised.exception))
        # A board region far larger than the limit, whose caption alone fits, is still tiled.
        planned = board_views.tiles((0, 0, 200, 200), SCALE, lambda tile: "short", "the view big")
        self.assertGreater(len(planned), 1)
        self.assertTrue(all(board_views.fits(*tile["size"]) for tile in planned))

    def test_a_crop_larger_than_the_size_limit_is_tiled_and_its_tiles_cover_it(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        with tempfile.TemporaryDirectory(prefix="board-views-crop-") as work:
            out = os.path.join(work, "out")
            os.makedirs(out)
            renderer = board_views.Renderer(RESVG, work, out, SCALE, (0, 0, 10, 10), {}, {}, [], [], {},
                                            board_views.Names())
            renderer.flat("crop-U9", [], {"view": "crop", "circuit": "U9"}, ["crop around U9 (top side)"],
                          around=(0, 0, 50, 50))
            renderer.write()
            images = renderer.images
            self.assertGreater(len(images), 1, "a crop larger than the size limit is not tiled")
            for image in images:
                width, height = board_views.png_size(os.path.join(out, image["file"]))
                self.assertTrue(board_views.fits(width, height), image["file"])
                self.assertEqual(image["scale_px_per_mm"], SCALE)
            margin = board_views.CROP_MARGIN_MM
            self.assertLessEqual(min(i["region_mm"]["x0"] for i in images), -margin)
            self.assertLessEqual(min(i["region_mm"]["y0"] for i in images), -margin)
            self.assertGreaterEqual(max(i["region_mm"]["x1"] for i in images), 50 + margin - 1e-9)
            self.assertGreaterEqual(max(i["region_mm"]["y1"] for i in images), 50 + margin - 1e-9)

    def test_the_fact_table_counts_a_copper_zone_held_inside_a_footprint(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        held = (f'(footprint "proof:Pad" (layer "F.Cu") (uuid {uuid()}) (at 30 30) '
                f'(property "Reference" "TP1" (at 0 -3 0) (layer "F.SilkS") (uuid {uuid()}) '
                '(effects (font (size 1 1) (thickness 0.15)))) '
                + pad(1, 0, 0, "GND", "passive") + " "
                + f'(zone (net "GND") (layers "F.Cu" "B.Cu") (uuid {uuid()}) (hatch edge 0.5) '
                '(connect_pads (clearance 0.5)) (min_thickness 0.25) (filled_areas_thickness no) '
                '(fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5)) '
                '(polygon (pts (xy 28 28) (xy 32 28) (xy 32 32) (xy 28 32)))) '
                + f'(zone (net "") (net_name "") (layer "F.Cu") (uuid {uuid()}) (hatch edge 0.5) '
                '(connect_pads (clearance 0)) (min_thickness 0.25) (filled_areas_thickness no) (keepout (tracks '
                'not_allowed) (vias allowed) (pads allowed) (copperpour allowed) (footprints allowed)) '
                '(fill (thermal_gap 0.5) (thermal_bridge_width 0.5)) '
                '(polygon (pts (xy 33 28) (xy 35 28) (xy 35 32) (xy 33 32)))))')
        top = (f'(zone (net "GND") (layer "B.Cu") (uuid {uuid()}) (hatch edge 0.5) (connect_pads (clearance 0.5)) '
               '(min_thickness 0.25) (filled_areas_thickness no) (fill yes (thermal_gap 0.5) (thermal_bridge_width '
               '0.5)) (polygon (pts (xy 2 2) (xy 10 2) (xy 10 10) (xy 2 10))))')
        design = Design(layout(items=[held, top]))
        facts = board_views.net_facts(board_views.locked_copper.read_layout(design.board), design.board,
                                      {"Ground": {"GND"}})
        self.assertEqual(facts, [{"net": "GND", "classes": ["Ground"], "track_width_mm": None, "vias": 0,
                                  "zones": [{"layers": ["B.Cu"]}, {"layers": ["B.Cu", "F.Cu"]}]}])
        self.assertEqual(board_views.fact_line(facts[0]),
                         "NET GND | class Ground | no tracks | 0 vias | 2 zones on B.Cu; B.Cu F.Cu")


class Transforms(unittest.TestCase):
    """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""

    def assertMaps(self, matrix, pairs):
        for point, expected in pairs:
            for got, want in zip(board_views.mapped(matrix, point), expected):
                self.assertAlmostEqual(got, want, places=9, msg=f"{point} -> {expected}")

    def extent(self, body):
        with tempfile.TemporaryDirectory(prefix="board-views-transform-") as folder:
            path = os.path.join(folder, "layer.svg")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 297 210">{body}</svg>')
            return board_views.drawn_extent(path)

    def assertExtent(self, body, expected):
        found = self.extent(body)
        self.assertIsNotNone(found, body)
        for got, want in zip(found, expected):
            self.assertAlmostEqual(got, want, places=6, msg=f"{body}: {found}")

    def test_a_turn_about_a_centre_keeps_the_centre_and_turns_about_it(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        # KiCad's form for a reference turned with its footprint.
        about = board_views.transform("rotate(-90.000000 35.0000 30.0000)")
        self.assertMaps(about, [((35, 30), (35, 30)), ((36, 30), (35, 29)), ((35, 31), (36, 30))])
        expected = board_views.compose(board_views.transform("translate(35 30)"),
                                       board_views.compose(board_views.transform("rotate(-90)"),
                                                           board_views.transform("translate(-35 -30)")))
        for got, want in zip(about, expected):
            self.assertAlmostEqual(got, want, places=9)
        self.assertMaps(board_views.transform("rotate(45 10 0)"),
                        [((11, 0), (10 + math.sqrt(0.5), math.sqrt(0.5)))])

    def test_a_mirror_with_a_translation_applies_the_translation_first(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        # KiCad's form for mirrored text anchored at x = 40.
        mirror = board_views.transform("scale(-1 1) translate(-80.000000 0)")
        self.assertMaps(mirror, [((40, 36), (40, 36)), ((42, 36), (38, 36)), ((0, 0), (80, 0))])
        self.assertMaps(board_views.transform("translate(10,0)scale(2)"), [((1, 1), (12, 2))])
        self.assertMaps(board_views.transform(" scale(3) , translate(1 2) "), [((0, 0), (3, 6))])

    def test_a_matrix_and_each_skew_map_points_as_svg_defines_them(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        self.assertMaps(board_views.transform("matrix(1 2 3 4 5 6)"), [((1, 1), (9, 12)), ((0, 0), (5, 6))])
        self.assertMaps(board_views.transform("matrix(1,2,3,4,5,6)"), [((1, 0), (6, 8))])
        self.assertMaps(board_views.transform("skewX(45)"), [((0, 1), (1, 1)), ((1, 0), (1, 0))])
        self.assertMaps(board_views.transform("skewY(45)"), [((1, 0), (1, 1)), ((0, 1), (0, 1))])
        self.assertMaps(board_views.transform("scale(2 3)"), [((1, 1), (2, 3))])
        self.assertMaps(board_views.transform(""), [((4, 5), (4, 5))])
        self.assertAlmostEqual(board_views.stretch(board_views.transform("scale(2 -3)")), 3)
        self.assertAlmostEqual(board_views.stretch(board_views.transform("rotate(30) scale(-1 1)")), 1)
        self.assertAlmostEqual(board_views.stretch(board_views.transform("skewX(45)")), (1 + math.sqrt(5)) / 2)

    def test_a_malformed_transform_is_refused(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        for text in ("rotate(1 2)", "scale()", "matrix(1 2 3 4 5)", "translate(1 2) twist(3)", "rotate(nan)",
                     "translate(1 2", "translate(1 x)"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    board_views.transform(text)
                with self.assertRaises(board_views.Unreadable):
                    self.extent(f'<g transform="{text}"><path d="M 0 0 L 1 1" /></g>')

    def test_nested_groups_compose_their_transforms_and_the_stroke_is_bounded_through_them(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        # A 2 by 1 box turned 90 degrees, then moved 10 mm right: x 9 to 10, y 0 to 2.
        self.assertExtent('<g transform="translate(10 0)"><g transform="rotate(90)">'
                          '<rect x="0" y="0" width="2" height="1" /></g></g>', (9, 0, 10, 2))
        # The element's own transform applies inside its group's.
        self.assertExtent('<g transform="scale(2)"><path transform="translate(1 1)" d="M 0 0 L 1 0" /></g>',
                          (2, 2, 4, 2))
        # A stroke 0.2 wide scaled by 2 reaches 0.2 past the scaled line.
        self.assertExtent('<g style="stroke:#000;stroke-width:0.2;stroke-linecap:round" transform="scale(2)">'
                          '<line x1="0" y1="0" x2="1" y2="0" /></g>', (-0.2, -0.2, 2.2, 0.2))
        # A circle turned and skewed still lies within its bounding box's mapped corners.
        found = self.extent('<g transform="rotate(30 5 5) skewX(10)"><circle cx="5" cy="5" r="1" /></g>')
        for angle in range(0, 360, 5):
            x, y = board_views.mapped(board_views.transform("rotate(30 5 5) skewX(10)"),
                                      (5 + math.cos(math.radians(angle)), 5 + math.sin(math.radians(angle))))
            self.assertTrue(found[0] <= x <= found[2] and found[1] <= y <= found[3], (angle, x, y, found))

    def test_each_element_is_bounded_by_its_own_stroke_and_not_the_widest_in_the_plot(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        self.assertExtent('<g style="stroke:#000;stroke-linecap:round">'
                          '<line x1="0" y1="0" x2="1" y2="0" style="stroke-width:2" />'
                          '<line x1="0" y1="10" x2="1" y2="10" stroke-width="0.2" /></g>', (-1, -1, 2, 10.1))
        # An unstroked element reaches no further than its outline.
        self.assertExtent('<g style="stroke:none;stroke-width:5"><rect x="0" y="0" width="1" height="1" /></g>',
                          (0, 0, 1, 1))
        # A stroke given no width is SVG's default 1 wide, and its reach is taken on every side.
        self.assertExtent('<line x1="0" y1="0" x2="1" y2="0" stroke="#000" />', (-0.5, -0.5, 1.5, 0.5))

    def test_kicads_hidden_text_is_passed_over_and_content_it_cannot_bound_is_refused(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        # KiCad's searchable copy of a mirrored text: transparent, so it draws nothing.
        self.assertExtent('<g style="fill:none;stroke:#000;stroke-width:0.2;stroke-linecap:round;'
                          'stroke-linejoin:round"><text x="40" y="36.75" transform="scale(-1 1) translate(-80 0)" '
                          'opacity="0" stroke-opacity="0">BACK</text><path d="M 42 35.9 L 41.8 36" /></g>',
                          (41.7, 35.8, 42.1, 36.1))
        self.assertIsNone(self.extent('<g opacity="0"><path d="M 0 0 L 9 9" /></g><title>t</title>'
                                      '<defs><path d="M 50 50 L 60 60" /></defs>'))
        self.assertExtent('<inkscape:thing xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" />'
                          '<path d="M 1 1 L 2 2" />', (1, 1, 2, 2))
        for body in ('<text x="1" y="1">visible</text>', '<use href="#a" />', '<svg x="0" y="0"><path d="M 0 0" /></svg>',
                     '<path d="M 0 0 L 1 1" style="stroke:#000;stroke-width:5%" />'):
            with self.subTest(body=body):
                with self.assertRaises(board_views.Unreadable):
                    self.extent(body)


#: An index header carrying one of every line the index writes, as the views command builds it.
FULL_HEADER = {
    "board": "/boards/proof.kicad_pcb",
    "critical_classes": {"Power": ["+3V3", "+5V"], "Ground": ["GND"]},
    "resolution": {"px_per_mm": 30.0, "pixels_per_feature": 3, "min_track_width_mm": 0.1, "min_clearance_mm": 0.125,
                   "rule": "pixels per millimetre = pixels per feature / the smaller of the minimum track width and "
                           "the minimum clearance"},
    "image_limit": {"long_edge_px": 1568, "patches": 1568, "patch_px": 28},
    "background": "#000000",
    "fonts_substituted": [{"font": "Proof Face", "drawn_in": "KiCad Font"}],
    "layers_not_carried": ["B.Fab", "F.CrtYd"],
    "rule_areas": [{"name": "KO1", "layers": ["F.Cu", "Dwgs.User"], "rules": ["no tracks", "no vias"],
                    "bounds_mm": {"x0": 1, "y0": 2, "x1": 3, "y1": 4}}],
    "not_in_3d": [{"reference": "U2", "reason": "no model", "detail": "declares no model"}],
}
FULL_IMAGES = [{"file": "layer-F.Cu.png", "caption": "layer view | F.Cu"},
               {"file": "net-GND-r1c1.png", "caption": "net GND | class Ground"}]
#: The index text the views command writes for FULL_HEADER and FULL_IMAGES, line for line.
FULL_INDEX = """BOARD | /boards/proof.kicad_pcb
RESOLUTION | 30 px/mm | 3 px across the smaller of the minimum track width 0.1 mm and the minimum clearance 0.125 mm
LIMIT | every image within a long edge of 1568 px and 1568 patches of 28 by 28 px
CLASS | Power | +3V3, +5V
CLASS | Ground | GND
FONT | Proof Face | not found, so KiCad drew its text in KiCad Font
LAYER | B.Fab | not carried by the board, so the views that show it leave it out
LAYER | F.CrtYd | not carried by the board, so the views that show it leave it out
RULE AREA | KO1 | on F.Cu, Dwgs.User, no tracks; no vias; KiCad does not plot it, so the views draw it as a bright orange dashed hatched outline
NOT IN 3D | U2 | declares no model
IMAGE | layer-F.Cu.png | layer view | F.Cu
IMAGE | net-GND-r1c1.png | net GND | class Ground
"""


class SharedIndex(unittest.TestCase):
    """SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: The placement view's form, resolution and captioning are taken from the views tool rather than copied."""

    def test_the_views_index_and_report_lines_are_unchanged_by_the_placement_view_sharing_them(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: The placement view's form, resolution and captioning are taken from the views tool rather than copied, so sharing them leaves the views' own index and report as they were, byte for byte.
        with tempfile.TemporaryDirectory(prefix="board-views-index-") as out:
            files = board_views.output_files(board_views.Names())
            board_views.write_outputs(out, files, FULL_HEADER, FULL_IMAGES, [])
            with open(os.path.join(out, "index.txt"), encoding="utf-8") as handle:
                self.assertEqual(handle.read(), FULL_INDEX)
            with open(os.path.join(out, "index.json"), encoding="utf-8") as handle:
                self.assertEqual(handle.read(), json.dumps(dict(FULL_HEADER, images=FULL_IMAGES), indent=1) + "\n")
        stream = io.StringIO()
        board_views.report_substitutions({"Proof Face": "KiCad Font"}, ["B.Fab"], True, stream)
        board_views.report_resolution(30.0, (0.1, 0.125), stream)
        self.assertEqual(stream.getvalue().splitlines(), [
            "FONT | Proof Face | KiCad cannot find this font and drew its text in KiCad Font; the captions and the "
            "index name it",
            "LAYER | B.Fab | the board does not carry this layer, so the views that show it leave it out; the captions "
            "and the index name it",
            "RESOLUTION | 30 px/mm | 3 px across the smaller of the minimum track width 0.1 mm and the minimum "
            "clearance 0.125 mm"])
        fields = board_views.index_fields(30.0, (0.1, 0.125), {"Proof Face": "KiCad Font"}, ["B.Fab", "F.CrtYd"],
                                          [dict(FULL_HEADER["rule_areas"][0], extra="dropped")])
        self.assertEqual(list(fields), ["resolution", "image_limit", "background", "fonts_substituted",
                                        "layers_not_carried", "rule_areas"])
        for key, value in fields.items():
            if key not in ("layers_not_carried", "background"):
                self.assertEqual(value, FULL_HEADER[key], key)
        self.assertEqual(fields["background"], board_views.BACKGROUND)
        self.assertEqual(fields["layers_not_carried"], ["B.Fab", "F.CrtYd"])
        frame = board_views.board_frame((0, 0, 10, 8), {}, FULL_HEADER["rule_areas"], [(-4, 2, 1, 3)])
        self.assertEqual(frame, board_views.grown((-4, 0, 10, 8), board_views.BOARD_MARGIN_MM))
        self.assertIsNone(board_views.board_frame(None, {}, [], []))


class OutputNames(unittest.TestCase):
    """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""

    def written(self, views):
        """Net views written through the renderer into a fresh folder, with the index and the fact table, as the
        command writes them: (the files in the folder, the index's images). Each view is (net, its extent in
        millimetres), a large extent tiled and a small one not."""
        with tempfile.TemporaryDirectory(prefix="board-views-names-") as work:
            out = os.path.join(work, "out")
            os.makedirs(out)
            names = board_views.Names()
            files = board_views.output_files(names)
            renderer = board_views.Renderer(RESVG, work, out, SCALE, (0, 0, 10, 10), {}, {}, [], [], {}, names)
            for net, extent in views:
                renderer.flat(f"net-{net}", [], {"view": "net", "net": net}, [f"net {net}"], around=extent)
            renderer.write()
            header = {"board": "proof.kicad_pcb", "critical_classes": {}, "fonts_substituted": [],
                      "layers_not_carried": [], "rule_areas": [], "not_in_3d": [],
                      "resolution": {"px_per_mm": SCALE, "pixels_per_feature": 3, "min_track_width_mm": MINIMUM_MM,
                                     "min_clearance_mm": MINIMUM_MM}}
            board_views.write_outputs(out, files, header, renderer.images, [])
            with open(os.path.join(out, files["index_json"]), encoding="utf-8") as handle:
                images = json.load(handle)["images"]
            with open(os.path.join(out, files["index_text"]), encoding="utf-8") as handle:
                listed = [line.split(" | ")[1] for line in handle.read().splitlines() if line.startswith("IMAGE | ")]
            self.assertEqual(listed, [image["file"] for image in images])
            return sorted(os.listdir(out)), images

    def assertDistinct(self, found, images, nets):
        """Every image is its own file, told apart from every other however letter case folds, listed once in the
        index, and each net's images are the ones its own views wrote."""
        files = [image["file"] for image in images]
        self.assertEqual(len({name.casefold() for name in found}), len(found), found)
        self.assertEqual(len({name.casefold() for name in files}), len(files), files)
        self.assertEqual(sorted(name for name in found if name.endswith(".png")), sorted(files))
        self.assertEqual({"index.txt", "index.json", "facts.txt", "facts.json"} - set(found), set())
        self.assertEqual(sorted({image["net"] for image in images}), sorted(nets))

    def test_two_nets_whose_names_differ_only_in_case_write_two_files_each_listed_once(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        small = (0, 0, 5, 5)
        found, images = self.written([("VCC", small), ("vcc", small), ("Vcc", small)])
        self.assertDistinct(found, images, ["VCC", "vcc", "Vcc"])
        self.assertEqual(len(images), 3, images)

    def test_a_tiled_net_beside_an_untiled_net_named_as_one_of_its_tiles_write_distinct_files(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        large, small = (0, 0, 80, 80), (0, 0, 5, 5)
        for order in ([("A", large), ("A-r1c1", small)], [("A-r1c1", small), ("A", large)]):
            with self.subTest(first=order[0][0]):
                found, images = self.written(order)
                self.assertDistinct(found, images, ["A", "A-r1c1"])
                tiled = [image for image in images if image["net"] == "A"]
                self.assertGreater(len(tiled), 1, "the large net was not tiled, so the test proves nothing")
                self.assertEqual(len([image for image in images if image["net"] == "A-r1c1"]), 1, images)
                self.assertEqual(len({image["file"].rsplit("-r", 1)[0] for image in tiled}), 1,
                                 "a tiled view's tiles do not share one stem")

    def test_a_view_named_as_the_index_or_the_fact_table_never_takes_their_names(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        names = board_views.Names()
        files = board_views.output_files(names)
        self.assertEqual(files, {"index_text": "index.txt", "index_json": "index.json",
                                 "facts_text": "facts.txt", "facts_json": "facts.json"})
        self.assertEqual(names.claim("INDEX", [".TXT"]), ["INDEX-2.TXT"])
        self.assertEqual(names.claim("view", [".png"]), ["view.png"])
        self.assertEqual(names.claim("VIEW", [".png"]), ["VIEW-2.png"])
        self.assertEqual(names.claim("view-2", [".png"]), ["view-2-2.png"])
        self.assertEqual(names.claim("view", ["-r1c1.png", "-r1c2.png"]), ["view-r1c1.png", "view-r1c2.png"])
        self.assertEqual(names.claim("View-r1c2", [".png"]), ["View-r1c2-2.png"])
        self.assertEqual(names.claim("a/b c", [".png"]), ["a_b_c.png"])
        self.assertEqual(names.claim("..", [".png"]), ["view-3.png"])


class RealBoard(unittest.TestCase):
    """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""

    def test_the_repositorys_kicad_authored_proof_board_renders(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        with tempfile.TemporaryDirectory(prefix="board-views-gate-proof-") as root:
            folder = os.path.join(root, "gate-proof")
            shutil.copytree(os.path.dirname(PROOF_PROJECT), folder)
            project_file = os.path.join(folder, "gate-proof.kicad_pro")
            with open(project_file, encoding="utf-8") as handle:
                data = json.load(handle)
            data["board"]["design_settings"]["rules"].update(min_track_width=0.2, min_clearance=0.2)
            with open(project_file, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2)
            out = os.path.join(root, "views")
            stream, errors = io.StringIO(), io.StringIO()
            with contextlib.redirect_stderr(errors):
                status = board_views.main(["--kicad-cli", KICAD_CLI, "--resvg", RESVG, "--board",
                                           os.path.join(folder, "gate-proof.kicad_pcb"), "--project", project_file,
                                           "--class", "Mains", "--out", out], out=stream)
            lines = stream.getvalue().splitlines()
            self.assertEqual(status, 0, lines + [errors.getvalue()])
            self.assertTrue(lines[-1].startswith("RESULT | WRITTEN | "), lines)
            with open(os.path.join(out, "index.json"), encoding="utf-8") as handle:
                index = json.load(handle)
            outline = board_views.outline_bounds(board_views.locked_copper.read_layout(
                os.path.join(folder, "gate-proof.kicad_pcb")))
            for image in index["images"]:
                self.assertTrue(os.path.isfile(os.path.join(out, image["file"])), image["file"])
            layers = [image for image in index["images"] if image["view"] == "layer"]
            self.assertTrue(layers)
            self.assertLessEqual(min(image["region_mm"]["x0"] for image in layers), outline[0])
            self.assertGreaterEqual(max(image["region_mm"]["x1"] for image in layers), outline[2])


class Refusals(unittest.TestCase):
    """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""

    def assertRefused(self, design, named, classes=("Power", "Ground"), out=None):
        status, lines, _ = design.run(classes, out)
        self.assertEqual(status, 1, lines)
        self.assertEqual(lines[-1], "RESULT | REFUSED | no views were written", lines)
        self.assertTrue(any(line.startswith("REFUSED | ") and named in line for line in lines), lines)
        self.assertFalse(os.path.exists(out or design.out), "the output folder was made")
        return lines

    def test_an_unknown_class_is_refused_by_name(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        design = Design()
        lines = self.assertRefused(design, "Sensing", classes=("Power", "Sensing"))
        self.assertIn("defines no net class of this name", "\n".join(lines))
        self.assertFalse(os.path.exists(design.out))

    def test_an_empty_class_is_refused_by_name(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        design = Design(project_text=project(classes=("Power", "Ground", "Sensing")))
        lines = self.assertRefused(design, "Sensing", classes=("Power", "Ground", "Sensing"))
        self.assertIn("KiCad places no net of the board in this class", "\n".join(lines))

    def test_a_class_named_twice_is_refused(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        lines = self.assertRefused(Design(), "REFUSED | Power, Ground, Power |", classes=("Power", "Ground", "Power"))
        self.assertIn("a critical class is named more than once", "\n".join(lines))
        self.assertEqual(sum(1 for line in lines if line.startswith("REFUSED | ")), 1, lines)

    def test_a_class_list_leaving_out_mains_on_a_board_declaring_mains_is_refused(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        design = Design(project_text=project(mains="present"))
        self.assertRefused(design, "REFUSED | Mains | MAINS is present")
        undeclared = Design(project_text=project(mains="maybe"))
        self.assertRefused(undeclared, "text_variables.MAINS")

    def test_a_missing_layer_is_refused_by_name(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        for layer in board_views.REQUIRED_LAYERS:
            with self.subTest(layer=layer):
                kept = [entry for entry in LAYER_TABLE if f'"{layer}"' not in entry]
                outline = OUTLINE if layer != "Edge.Cuts" else None
                lines = self.assertRefused(Design(layout(layers=kept, outline=outline)), f"REFUSED | {layer} | the board carries no {layer} layer")
                self.assertEqual(sum(1 for line in lines if line.startswith("REFUSED | ")), 1, lines)

    def test_an_edge_layer_holding_no_outline_is_refused(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        self.assertRefused(Design(layout(outline=None)), "REFUSED | Edge.Cuts | the board's edge layer holds no outline")

    def test_a_board_stating_no_minimum_a_zero_minimum_or_a_non_finite_one_is_refused_naming_the_figure(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        cases = (
            ({}, ["min_track_width", "min_clearance"]),
            ({"min_track_width": 0.1}, ["min_clearance"]),
            ({"min_clearance": 0.1}, ["min_track_width"]),
            ({"min_track_width": 0.1, "min_clearance": 0}, ["min_clearance"]),
            ({"min_track_width": 0, "min_clearance": 0.1}, ["min_track_width"]),
            ({"min_track_width": -0.1, "min_clearance": 0.1}, ["min_track_width"]),
            ({"min_track_width": "0.1", "min_clearance": 0.1}, ["min_track_width"]),
            ({"min_track_width": float("nan"), "min_clearance": 0.1}, ["min_track_width"]),
            ({"min_track_width": 0.1, "min_clearance": float("inf")}, ["min_clearance"]),
            ({"min_track_width": float("-inf"), "min_clearance": float("nan")}, ["min_track_width", "min_clearance"]),
        )
        for rules, named in cases:
            with self.subTest(rules=rules):
                status, lines, _ = Design(project_text=project(rules=rules)).run()
                self.assertEqual(status, 1, lines)
                refusals = [line for line in lines if line.startswith("REFUSED | ")]
                self.assertEqual(len(refusals), len(named), lines)
                for figure in named:
                    self.assertTrue(any(f"board.design_settings.rules.{figure} |" in line for line in refusals), lines)

    def test_an_output_folder_inside_a_design_folder_is_refused(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        design = Design()
        inside = os.path.join(design.folder, "views")
        self.assertRefused(design, "never kept in a design's folder", out=inside)
        self.assertFalse(os.path.exists(inside))
        other = os.path.join(design.root, "other")
        os.makedirs(os.path.join(other, "deeper"))
        with open(os.path.join(other, "other.kicad_pro"), "w", encoding="utf-8") as handle:
            handle.write("{}")
        self.assertRefused(design, "never kept in a design's folder", out=os.path.join(other, "deeper", "views"))

    def test_an_output_folder_that_already_holds_files_is_refused(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        design = Design()
        os.makedirs(design.out)
        with open(os.path.join(design.out, "old.png"), "w", encoding="utf-8") as handle:
            handle.write("old")
        status, lines, _ = design.run()
        self.assertEqual(status, 1, lines)
        self.assertTrue(any("already holds files" in line for line in lines), lines)
        self.assertEqual(os.listdir(design.out), ["old.png"])
        afile = os.path.join(design.root, "a-file")
        with open(afile, "w", encoding="utf-8") as handle:
            handle.write("x")
        status, lines, _ = design.run(out=afile)
        self.assertEqual(status, 1, lines)
        self.assertTrue(any("the output folder is a file" in line for line in lines), lines)

    def test_a_project_file_not_the_boards_own_is_refused(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        design = Design()
        stray = os.path.join(design.root, "stray.kicad_pro")
        shutil.copy2(design.project, stray)
        design.project = stray
        self.assertRefused(design, "give the board's own project file")

    def test_a_board_open_in_an_editor_is_refused(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        design = Design()
        lock = os.path.join(design.folder, "~proof.kicad_pcb.lck")
        with open(lock, "w", encoding="utf-8") as handle:
            handle.write("{}")
        lines = self.assertRefused(design, f"REFUSED | {lock} | KiCad's lock file shows {design.board} open in an editor")
        self.assertIn("drawn from the saved file", "\n".join(lines))
        os.remove(lock)
        with open(os.path.join(design.folder, "~other.kicad_pcb.lck"), "w", encoding="utf-8") as handle:
            handle.write("{}")
        status, lines, _ = design.run()
        self.assertEqual(status, 0, lines)

    def test_an_unreadable_board_fails_naming_it(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        for text in ("(kicad_pcb (version 20260206) (layers", "(kicad_sch (version 1))", "\x00\xff"):
            with self.subTest(text=text):
                design = Design(board_text=text)
                status, lines, _ = design.run()
                self.assertEqual(status, 1, lines)
                self.assertTrue(lines[0].startswith("UNREADABLE | ") and design.board in lines[0], lines)
                self.assertEqual(lines[-1], "RESULT | FAIL | the input cannot be read, so no views were written")
                self.assertFalse(os.path.exists(design.out))


def tool(folder: str, name: str, script: str) -> str:
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("#!/bin/sh\n" + script + "\n")
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    return path


class Tools(unittest.TestCase):
    """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""

    def cannot_run(self, **tools):
        design = Design()
        status, lines, errors = design.run(**tools)
        self.assertEqual(status, 2, lines)
        self.assertEqual(lines, [])
        self.assertTrue(errors.startswith("CANNOT RUN | "), errors)
        self.assertFalse(os.path.exists(design.out))
        return errors

    def test_a_missing_or_too_old_tool_stops_the_command_naming_it(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        with tempfile.TemporaryDirectory(prefix="board-views-tools-") as folder:
            errors = self.cannot_run(resvg="/nonexistent/resvg")
            self.assertIn("resvg was not found", errors)
            self.assertIn("https://github.com/linebender/resvg/releases", errors)
            self.assertIn("RESVG=/path/to/resvg", errors)
            for route in ("resvg-win64.zip", "brew install resvg", "cargo install resvg", "https://rustup.rs/"):
                self.assertIn(route, errors)
            errors = self.cannot_run(resvg=tool(folder, "old-resvg", 'echo "0.46.9"'))
            self.assertIn("older than the 0.47", errors)
            errors = self.cannot_run(resvg=tool(folder, "silent-resvg", "exit 3"))
            self.assertIn("did not report a resvg version", errors)
            errors = self.cannot_run(kicad_cli="/nonexistent/kicad-cli")
            self.assertIn("kicad-cli was not found", errors)
            errors = self.cannot_run(kicad_cli=tool(folder, "old-kicad", 'echo "9.0.4"'))
            self.assertIn("older than the 10.0", errors)

    def test_a_rasteriser_with_no_font_for_the_captions_stops_the_command(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        real = shutil.which(RESVG) or RESVG
        with tempfile.TemporaryDirectory(prefix="board-views-tools-") as folder:
            fontless = tool(folder, "fontless-resvg", f'exec "{real}" --skip-system-fonts "$@"')
            errors = self.cannot_run(resvg=fontless)
            self.assertIn("found no font to draw the captions with", errors)

    def test_the_task_locates_resvg_through_its_path_variable(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        design = Design()
        result = subprocess.run(["task", "hw:views", f"KICAD_CLI={KICAD_CLI}", "RESVG=/nonexistent/resvg", "--",
                                 *design.args()], cwd=REPO, capture_output=True, text=True, timeout=600)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CANNOT RUN | resvg was not found or could not be run at '/nonexistent/resvg'", result.stderr)
        self.assertFalse(os.path.exists(design.out))


class Documentation(unittest.TestCase):
    """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""

    def read(self, *path):
        with open(os.path.join(REPO, *path), encoding="utf-8") as handle:
            return handle.read()

    def test_the_command_its_views_and_its_tools_are_named_in_the_method_and_the_readme(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        readme, method = self.read("hardware", "README.md"), self.read("docs", "board-design-method.md")
        taskfile = self.read("Taskfile.yml")
        task = taskfile[taskfile.index("  hw:views:"):]
        task = task[:task.index("\n\n")]
        for name, text in (("README", readme), ("method", method), ("task", task)):
            with self.subTest(document=name):
                for words in ("task hw:views", "resvg", "RESVG=/path/to/resvg"):
                    self.assertIn(words, text)
        for name, text in (("README", readme), ("method", method)):
            with self.subTest(document=name):
                self.assertIn("https://github.com/linebender/resvg/releases", text)
                self.assertIn(f"resvg {board_views.MIN_RESVG[0]}.{board_views.MIN_RESVG[1]}", text)
                for route in ("resvg-win64.zip", "brew install resvg", "cargo install resvg", "https://rustup.rs/"):
                    self.assertIn(route, text)
                self.assertIn("1568", text)
        self.assertIn(f"resvg {board_views.MIN_RESVG[0]}.{board_views.MIN_RESVG[1]} or newer", task)
        tools = method[method.index("## Tools"):method.index("KiCad's bundled Python is the one")]
        for font in ("DejaVu Sans Mono", "https://dejavu-fonts.github.io/", "Menlo", "Consolas"):
            with self.subTest(font=font):
                self.assertIn(font, readme)
                self.assertIn(font, tools)
        self.assertIn("resvg and a monospaced font for the captions", method)
        for name, text in (("README", readme), ("method", method)):
            with self.subTest(document=name):
                self.assertIn("whose nearest pad is closest to it", text)
                self.assertIn("as having no decoupling parts", text)
                # A crop is widened to the narrowest image, so it can take in a neighbour's parts: the docs promise
                # only what is delivered, that a crop frames and names its own and draws the rest unnamed.
                self.assertIn(f"A crop is at least {board_views.MIN_WIDTH_PX} pixels wide", text)
                self.assertIn("A crop is framed on, and names, only its own circuit and that circuit's decoupling "
                              "parts", text)
                self.assertIn("drawn but not named", text)
                self.assertNotIn("never shows another circuit's decoupling", text)
                self.assertIn("not itself an integrated circuit, with its two pads on two different nets", text)
        self.assertIn("Each of them, whatever the reason, is also reported as a `MODEL` line", readme)
        self.assertNotIn("A model KiCad cannot find is also reported as a `MODEL` line", readme)
        self.assertIn("each part the three-dimensional views draw without its model, whatever the reason", method)
        views = readme[readme.index("## The layout review views"):]
        self.assertIn("a board KiCad's lock file shows open in an editor", views)
        self.assertIn("told apart even where letter case is not", views)
        for view in ("layer-<layer>", "assembly-top", "net-<net>", "classes", "crop-<reference>", "3d-top",
                     "3d-angled", "index.txt", "index.json", "facts.txt", "facts.json"):
            self.assertIn(view, readme)
        self.assertIn("pixels per millimetre = 3 / (the smaller of the board's minimum track width and minimum "
                      "clearance, in millimetres)", method)
        self.assertIn("https://platform.claude.com/docs/en/build-with-claude/vision, read on 2026-10-13", method)
        self.assertIn("1568 visual patches of 28 by 28 pixels", method)
        section = method[method.index("## Layout review views"):]
        for view in ("layer-<layer>", "assembly-top", "net-<net>", "classes", "crop-<reference>", "3d-angled"):
            self.assertIn(view, section)
        for fact in ("rule area", "cannot find", "zoomed out", "not carried", "reaching past the outline",
                     "every two-dimensional view that shows one of its layers", "do not draw rule areas",
                     "pcb export glb"):
            with self.subTest(fact=fact):
                self.assertIn(fact, readme)
                self.assertIn(fact, section)
        self.assertIn("KiCad 10.0", readme)


if __name__ == "__main__":
    unittest.main()
