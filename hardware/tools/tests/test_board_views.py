#!/usr/bin/env python3
"""The layout review views, rendered from a synthetic proof board against the real kicad-cli and resvg.

The proof board is written from text in a temporary directory outside the
repository: an integrated circuit with its supply pins typed and two decoupling
parts on its rails, a second circuit with no pin typed as power, two critical
classes, a ground pour on the back whose fill is cut around a power track, two
signal tracks at the board's minimum width and minimum clearance, a note on a
user layer, a rule area, a silkscreen text in a font no machine has, and parts
whose three-dimensional models are kept in the design's folder, missing, hidden
or not populated, a power track crossing the rule area, a net in two critical
classes, and a connector courtyard and a silkscreen text reaching past the board
outline. The views are rendered once, through the shipped task, and the
tests ask of the images, the index and the fact table what the criterion
needs; the refusals are driven through the command itself. Nothing is skipped
when a tool is absent: a command that cannot be exercised has not been shown
to work.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import math
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import board_views  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
KICAD_CLI = os.environ.get("KICAD_CLI") or "kicad-cli"
RESVG = os.environ.get("RESVG") or "resvg"
PROOF_PROJECT = os.path.join(REPO, "hardware", "proof", "gate-proof", "gate-proof.kicad_pro")

#: The critical classes the proof board's views are rendered with: +3V3 is in both Power and Sense.
CRITICAL = ("Power", "Ground", "Sense")

#: The proof board's minimum track width and minimum clearance, and so its resolution.
MINIMUM_MM = 0.1
SCALE = 3 / MINIMUM_MM

_SCRATCH = []
_RENDERED = {}


def setUpModule():
    board_check.require_kicad(KICAD_CLI)
    board_views.require_resvg(RESVG)


def tearDownModule():
    for scratch in _SCRATCH:
        scratch.cleanup()


# --- The proof board -------------------------------------------------------------------

_UUID = [0]


def uuid() -> str:
    _UUID[0] += 1
    return f'"00000000-0000-4000-8000-{_UUID[0]:012d}"'


def pad(number, x, y, net, pintype):
    return (f'(pad "{number}" smd roundrect (at {x} {y}) (size 1 0.6) (layers "F.Cu" "F.Mask" "F.Paste") '
            f'(roundrect_rratio 0.25) (net "{net}") (pintype "{pintype}") (uuid {uuid()}))')


def model(path, height=1, hidden=False):
    return (f'(model "{path}"{" (hide yes)" if hidden else ""} (offset (xyz 0 0 0)) (scale (xyz 1 1 {height})) '
            '(rotate (xyz 0 0 0)))')


def footprint(reference, x, y, pads, models=(), attributes=""):
    return (f'(footprint "proof:Part" (layer "F.Cu") (uuid {uuid()}) (at {x} {y}) {attributes}'
            f'(property "Reference" "{reference}" (at 0 -3 0) (layer "F.SilkS") (uuid {uuid()}) '
            '(effects (font (size 1 1) (thickness 0.15)))) '
            f'(fp_rect (start -2.5 -2.5) (end 2.5 2.5) (stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd") '
            f'(uuid {uuid()})) '
            f'(fp_rect (start -2 -2) (end 2 2) (stroke (width 0.1) (type solid)) (fill no) (layer "F.Fab") '
            f'(uuid {uuid()})) ' + " ".join(list(pads) + list(models)) + ")")


LAYER_TABLE = ['(0 "F.Cu" signal)', '(2 "B.Cu" signal)', '(13 "F.Paste" user)', '(15 "B.Paste" user)',
               '(5 "F.SilkS" user "F.Silkscreen")', '(7 "B.SilkS" user "B.Silkscreen")', '(1 "F.Mask" user)',
               '(3 "B.Mask" user)', '(17 "Dwgs.User" user "User.Drawings")', '(19 "Cmts.User" user "User.Comments")',
               '(25 "Edge.Cuts" user)', '(31 "F.CrtYd" user "F.Courtyard")', '(29 "B.CrtYd" user "B.Courtyard")',
               '(35 "F.Fab" user)', '(33 "B.Fab" user)']

OUTLINE = '(gr_rect (start 0 0) (end 60 40) (stroke (width 0.05) (type default)) (fill no) (layer "Edge.Cuts") (uuid "00000000-0000-4000-8000-0000000000e0"))'

#: A model the design keeps in its own folder: a red box 2 by 2 by 2 in VRML's units of 2.54 mm, which a model's
#: scale stretches upward.
MODEL = """#VRML V2.0 utf8
Shape { appearance Appearance { material Material { diffuseColor 0.9 0.05 0.05 } } geometry Box { size 2 2 2 } }
"""
MODEL_COLOUR = (230, 13, 13)

#: The font one silkscreen text asks for, which no machine has, so KiCad substitutes another.
NO_SUCH_FONT = "Board Views Proof Face"

#: The proof board's items: U1 has its supply pins typed and C1 and C2 across its rails; R1 has only one pad on
#: a rail; U2 has no pin typed as power. The ground pour on B.Cu is cut around the +3V3 track crossing it, so its
#: fill depends on another net's copper. SIG_A and SIG_B run at the minimum width, the minimum clearance apart.
#: U1's model is in the design's folder, named through ${KIPRJMOD}; U2's is the same file named from that folder
#: with no variable, stretched to 61 mm tall at the back of the board, so the angled view must zoom out to show
#: it whole; C1 declares no model, C2's model is nowhere, R1 hides its model and D1 is not populated. A rule area
#: on F.Cu and a user layer, which KiCad does not plot, crossed by a +3V3 track, and a silkscreen text in a font no
#: machine has follow. J1's courtyard and fabrication outline overhang the board's right edge, at x = 60 mm, to
#: 64.5 mm and 64 mm, and a silkscreen text sits below its bottom edge, at y = 40 mm, at y = 45 mm.
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
]


def layout(items=None, layers=None, outline=OUTLINE) -> str:
    table = "\n".join(f"\t\t{entry}" for entry in (LAYER_TABLE if layers is None else layers))
    body = "".join(f"\t{item}\n" for item in ([outline] if outline else []) + (ITEMS if items is None else items))
    return ('(kicad_pcb\n\t(version 20260206)\n\t(generator "pcbnew")\n\t(generator_version "10.0")\n'
            f'\t(general (thickness 1.6))\n\t(paper "A4")\n\t(layers\n{table}\n\t)\n' + body + ")\n")


def project(classes=("Power", "Ground"), assignments=None, mains="none", rules="default", patterns=()) -> str:
    """A project file defining `classes` beside Default, declaring MAINS as `mains`, with design rules `rules`, and
    assigning nets to classes by name and by `patterns` as well."""
    with open(PROOF_PROJECT, encoding="utf-8") as handle:
        data = json.load(handle)
    settings = data["net_settings"]
    default, template = settings["classes"][0], settings["classes"][1]
    settings["classes"] = [default] + [dict(copy.deepcopy(template), name=name, priority=index)
                                       for index, name in enumerate(classes)]
    settings["netclass_assignments"] = {"+3V3": "Power", "GND": "Ground"} if assignments is None else assignments
    settings["netclass_patterns"] = [{"netclass": netclass, "pattern": pattern} for netclass, pattern in patterns]
    data["text_variables"] = {"MAINS": mains}
    data["board"]["design_settings"]["rules"] = (
        {"min_track_width": MINIMUM_MM, "min_clearance": MINIMUM_MM} if rules == "default" else rules)
    return json.dumps(data, indent=1)


class Design:
    """The proof board and its project in their own folder, with a working folder outside it."""

    def __init__(self, board_text=None, project_text=None):
        scratch = tempfile.TemporaryDirectory(prefix="board-views-test-")
        _SCRATCH.append(scratch)
        self.root = scratch.name
        self.folder = os.path.join(self.root, "design")
        os.makedirs(self.folder)
        self.board = os.path.join(self.folder, "proof.kicad_pcb")
        self.project = os.path.join(self.folder, "proof.kicad_pro")
        self.out = os.path.join(self.root, "views")
        with open(self.board, "w", encoding="utf-8") as handle:
            handle.write(layout() if board_text is None else board_text)
        with open(self.project, "w", encoding="utf-8") as handle:
            handle.write(project() if project_text is None else project_text)
        os.makedirs(os.path.join(self.folder, "models"))
        with open(os.path.join(self.folder, "models", "box.wrl"), "w", encoding="utf-8") as handle:
            handle.write(MODEL)

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


def hex_rgb(colour: str):
    return tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))


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
        """Whether a pixel is the colour over the background, at least half covered: a thin line's antialiased
        pixels carry the colour in proportion to how much of them it covers."""
        target = hex_rgb(colour)
        spread = [t - b for t, b in zip(target, BACKGROUND)]
        cover = max((f - b) / s for f, b, s in zip(found, BACKGROUND, spread) if abs(s) > 60)
        return cover >= 0.5 and all(abs(f - (b + cover * s)) <= 16 for f, b, s in zip(found, BACKGROUND, spread))

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
        self.assertEqual(crop[0]["parts"], ["C1", "C2"])
        self.assertTrue(crop[0]["supply_nets_declared"])
        covered = (min(i["region_mm"]["x0"] for i in crop), min(i["region_mm"]["y0"] for i in crop),
                   max(i["region_mm"]["x1"] for i in crop), max(i["region_mm"]["y1"] for i in crop))
        for name, x, y, pad in (("U1", 20, 20, (18.3, 21)), ("C1", 4, 20, (4, 21)), ("C2", 56, 20, (56, 21))):
            with self.subTest(part=name):
                self.assertTrue(covered[0] <= x - 2.5 and x + 2.5 <= covered[2] and covered[1] <= y - 2.5
                                and y + 2.5 <= covered[3], f"{name} is outside the crop {covered}")
                self.assertTrue(self.near(self.colour_at(crop, *pad), self.layer_colour("F.Cu")), f"{name}'s pad")
        self.assertGreater(len(crop), 1, "a crop wider than the size limit is not tiled")
        for image in crop:
            self.assertIn("supply nets +3V3, GND", image["caption"])
            self.assertIn("parts on them C1, C2", image["caption"])

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
        self.assertEqual({image["circuit"] for image in self.images("crop")}, {"U1", "U2"})

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
                                  "J1": "no model", "R1": "model hidden"})
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
        self.assertIn(f"MODEL | C2 | {missing}", self.views["result"].stdout)
        for name in ("C1", "D1", "R1", "U1", "U2"):
            self.assertNotIn(f"MODEL | {name} |", self.views["result"].stdout)
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

    def test_a_net_in_more_than_one_critical_class_is_named_on_the_class_map(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        membership = {"Power": {"+3V3", "+5V"}, "Sense": {"+3V3", "ADC"}, "Ground": {"GND"}}
        self.assertEqual(board_views.shared_nets(["Power", "Sense", "Ground"], membership),
                         {"+3V3": ["Power", "Sense"]})
        self.assertEqual(board_views.shared_nets(["Ground"], membership), {})

    def test_the_extent_of_a_plot_holds_everything_drawn_in_it_strokes_included(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        cases = (
            ('<path style="stroke-width:0.2" d="M 1,2\n3,4\nZ" />', (0.9, 1.9, 3.1, 4.1)),
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
            for body in ('<g transform="translate(5 0)"><path d="M 0 0 1 1" /></g>', '<path d="M 0 0 L 1" />',
                         '<path d="3 4" />'):
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
            errors = self.cannot_run(resvg=tool(folder, "old-resvg", 'echo "0.47.9"'))
            self.assertIn("older than the 0.48", errors)
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
                self.assertIn("resvg 0.48", text)
                self.assertIn("1568", text)
        self.assertIn("resvg 0.48 or newer", task)
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
