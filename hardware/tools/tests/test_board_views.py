#!/usr/bin/env python3
"""The layout review views, rendered from a synthetic proof board against the real kicad-cli and resvg.

The proof board is written from text in a temporary directory outside the
repository: an integrated circuit with its supply pins typed and two decoupling
parts on its rails, a second circuit with no pin typed as power, two critical
classes, a ground pour on the back whose fill is cut around a power track, two
signal tracks at the board's minimum width and minimum clearance, and a note on
a user layer. The views are rendered once, through the shipped task, and the
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


def footprint(reference, x, y, pads):
    return (f'(footprint "proof:Part" (layer "F.Cu") (uuid {uuid()}) (at {x} {y}) '
            f'(property "Reference" "{reference}" (at 0 -3 0) (layer "F.SilkS") (uuid {uuid()}) '
            '(effects (font (size 1 1) (thickness 0.15)))) '
            f'(fp_rect (start -2.5 -2.5) (end 2.5 2.5) (stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd") '
            f'(uuid {uuid()})) '
            f'(fp_rect (start -2 -2) (end 2 2) (stroke (width 0.1) (type solid)) (fill no) (layer "F.Fab") '
            f'(uuid {uuid()})) ' + " ".join(pads) + ")")


LAYER_TABLE = ['(0 "F.Cu" signal)', '(2 "B.Cu" signal)', '(13 "F.Paste" user)', '(15 "B.Paste" user)',
               '(5 "F.SilkS" user "F.Silkscreen")', '(7 "B.SilkS" user "B.Silkscreen")', '(1 "F.Mask" user)',
               '(3 "B.Mask" user)', '(17 "Dwgs.User" user "User.Drawings")', '(19 "Cmts.User" user "User.Comments")',
               '(25 "Edge.Cuts" user)', '(31 "F.CrtYd" user "F.Courtyard")', '(29 "B.CrtYd" user "B.Courtyard")',
               '(35 "F.Fab" user)', '(33 "B.Fab" user)']

OUTLINE = '(gr_rect (start 0 0) (end 60 40) (stroke (width 0.05) (type default)) (fill no) (layer "Edge.Cuts") (uuid "00000000-0000-4000-8000-0000000000e0"))'

#: The proof board's items: U1 has its supply pins typed and C1 and C2 across its rails; R1 has only one pad on
#: a rail; U2 has no pin typed as power. The ground pour on B.Cu is cut around the +3V3 track crossing it, so its
#: fill depends on another net's copper. SIG_A and SIG_B run at the minimum width, the minimum clearance apart.
ITEMS = [
    footprint("U1", 20, 20, [pad(1, -2, -1, "+3V3", "power_in"), pad(2, -2, 1, "GND", "power_in"),
                             pad(3, 2, -1, "SIG_A", "input"), pad(4, 2, 1, "SIG_B", "output")]),
    footprint("C1", 4, 20, [pad(1, 0, -1, "+3V3", "passive"), pad(2, 0, 1, "GND", "passive")]),
    footprint("C2", 56, 20, [pad(1, 0, -1, "+3V3", "passive"), pad(2, 0, 1, "GND", "passive")]),
    footprint("R1", 30, 12, [pad(1, 0, -1, "SIG_A", "passive"), pad(2, 0, 1, "+3V3", "passive")]),
    footprint("U2", 45, 8, [pad(1, -1, 0, "SIG_A", "input"), pad(2, 1, 0, "SIG_B", "output")]),
    f'(segment (start 4 19) (end 18 19) (width 0.3) (layer "F.Cu") (net "+3V3") (uuid {uuid()}))',
    f'(segment (start 24 19) (end 40 19) (width 0.1) (layer "F.Cu") (net "SIG_A") (uuid {uuid()}))',
    f'(segment (start 24 19.2) (end 40 19.2) (width 0.1) (layer "F.Cu") (net "SIG_B") (uuid {uuid()}))',
    f'(segment (start 5 30) (end 55 30) (width 0.5) (layer "B.Cu") (net "+3V3") (uuid {uuid()}))',
    f'(via (at 5 30) (size 0.8) (drill 0.4) (layers "F.Cu" "B.Cu") (net "+3V3") (uuid {uuid()}))',
    f'(zone (net "GND") (layer "B.Cu") (uuid {uuid()}) (hatch edge 0.5) (connect_pads (clearance 0.5)) '
    '(min_thickness 0.25) (filled_areas_thickness no) (fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5)) '
    '(polygon (pts (xy 2 25) (xy 58 25) (xy 58 38) (xy 2 38))))',
    f'(gr_text "KEEP OUT" (at 30 4 0) (layer "Cmts.User") (uuid {uuid()}) (effects (font (size 1.5 1.5) (thickness 0.2))))',
]


def layout(items=None, layers=None, outline=OUTLINE) -> str:
    table = "\n".join(f"\t\t{entry}" for entry in (LAYER_TABLE if layers is None else layers))
    body = "".join(f"\t{item}\n" for item in ([outline] if outline else []) + (ITEMS if items is None else items))
    return ('(kicad_pcb\n\t(version 20260206)\n\t(generator "pcbnew")\n\t(generator_version "10.0")\n'
            f'\t(general (thickness 1.6))\n\t(paper "A4")\n\t(layers\n{table}\n\t)\n' + body + ")\n")


def project(classes=("Power", "Ground"), assignments=None, mains="none", rules="default") -> str:
    """A project file defining `classes` beside Default, declaring MAINS as `mains`, with design rules `rules`."""
    with open(PROOF_PROJECT, encoding="utf-8") as handle:
        data = json.load(handle)
    settings = data["net_settings"]
    default, template = settings["classes"][0], settings["classes"][1]
    settings["classes"] = [default] + [dict(copy.deepcopy(template), name=name, priority=index)
                                       for index, name in enumerate(classes)]
    settings["netclass_assignments"] = {"+3V3": "Power", "GND": "Ground"} if assignments is None else assignments
    settings["netclass_patterns"] = []
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
        design = Design()
        result = subprocess.run(["task", "hw:views", f"KICAD_CLI={KICAD_CLI}", f"RESVG={RESVG}", "--",
                                 *design.args()], cwd=REPO, capture_output=True, text=True, timeout=1800)
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
        self.assertEqual(layers, set(board_views.REQUIRED_LAYERS) | {"Cmts.User", "F.Fab", "F.CrtYd"})
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
                self.assertEqual(image["layers"], [{"name": "F.Cu", "colour": "red"}, {"name": "B.Cu", "colour": "blue"}])
                self.assertIn("F.Cu red, B.Cu blue", image["caption"])
                self.assertIn(f"net {image['net']}", image["caption"])
                self.assertIn(f"class {', '.join(image['classes'])}", image["caption"])

    # --- The class map ---

    def test_the_class_map_draws_each_critical_class_in_its_own_colour(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        mapped = self.images("class map")
        self.assertTrue(mapped)
        power, ground = board_views.CLASS_COLOURS[0], board_views.CLASS_COLOURS[1]
        self.assertEqual(mapped[0]["classes"], [{"name": "Power", "colour": power[1]}, {"name": "Ground", "colour": ground[1]}])
        self.assertIn(f"Power {power[1]}, Ground {ground[1]}", mapped[0]["caption"])
        self.assertTrue(self.near(self.colour_at(mapped, 30, 30), power[0]), "the +3V3 track")
        self.assertTrue(self.near(self.colour_at(mapped, 30, 35), ground[0]), "the ground pour")
        found = self.colour_at(mapped, 35, 19)
        self.assertFalse(self.near(found, power[0]) or self.near(found, ground[0]), "SIG_A drawn as critical")

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
                top = image["content_px"]["height"] if "content_px" in image else height - (
                    len(board_views.wrapped(image["caption"], width)) * board_views.LINE_PX + 2 * board_views.CAPTION_PAD_PX)
                lines = board_views.wrapped(image["caption"], width)
                self.assertEqual(height - top, len(lines) * board_views.LINE_PX + 2 * board_views.CAPTION_PAD_PX)
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
        self.assertEqual(self.index["resolution"]["min_track_width_mm"], MINIMUM_MM)
        self.assertEqual(self.index["image_limit"], {"long_edge_px": 1568, "patches": 1568, "patch_px": 28})
        self.assertEqual(self.index["critical_classes"], {"Power": ["+3V3"], "Ground": ["GND"]})
        for image in self.index["images"]:
            fields = {"file", "view", "caption", "size_px"} | ({"direction"} if image["view"] == "3d" else
                                                              {"layers", "scale_px_per_mm", "region_mm", "tile"})
            self.assertLessEqual(fields, set(image), image["file"])
        overlay = self.images("net", net="GND")[0]
        self.assertEqual((overlay["classes"], overlay["scale_px_per_mm"]), (["Ground"], SCALE))

    def test_the_fact_table_gives_each_nets_track_widths_vias_zones_and_class_as_text_and_json(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        facts = {fact["net"]: fact for fact in self.views["facts"]["nets"]}
        self.assertEqual(set(facts), {"+3V3", "GND", "SIG_A", "SIG_B"})
        self.assertEqual(facts["+3V3"], {"net": "+3V3", "classes": ["Power"], "track_width_mm": {"min": 0.3, "max": 0.5},
                                         "vias": 1, "zones": []})
        self.assertEqual(facts["GND"], {"net": "GND", "classes": ["Ground"], "track_width_mm": None, "vias": 0,
                                        "zones": [{"layers": ["B.Cu"]}]})
        self.assertEqual(facts["SIG_A"], {"net": "SIG_A", "classes": ["Default"],
                                          "track_width_mm": {"min": 0.1, "max": 0.1}, "vias": 0, "zones": []})
        with open(os.path.join(self.out, "facts.txt"), encoding="utf-8") as handle:
            text = handle.read().splitlines()
        self.assertEqual(text, [
            "NET +3V3 | class Power | tracks 0.3 to 0.5 mm wide | 1 via | no zones",
            "NET GND | class Ground | no tracks | 0 vias | 1 zone on B.Cu",
            "NET SIG_A | class Default | tracks 0.1 to 0.1 mm wide | 0 vias | no zones",
            "NET SIG_B | class Default | tracks 0.1 to 0.1 mm wide | 0 vias | no zones",
        ])

    def test_the_render_leaves_the_design_folder_untouched(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        design = self.views["design"]
        self.assertEqual(sorted(os.listdir(design.folder)), ["proof.kicad_pcb", "proof.kicad_pro"])
        with open(design.board, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), layout())


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

    def test_a_board_stating_no_minimum_or_a_zero_minimum_is_refused_naming_the_figure(self):
        """SOL-BOARD-REVIEW-RENDER-VIEWS.C1: One task-runner command renders every layout review view of a board from its design files."""
        cases = (
            ({}, ["min_track_width", "min_clearance"]),
            ({"min_track_width": 0.1}, ["min_clearance"]),
            ({"min_clearance": 0.1}, ["min_track_width"]),
            ({"min_track_width": 0.1, "min_clearance": 0}, ["min_clearance"]),
            ({"min_track_width": 0, "min_clearance": 0.1}, ["min_track_width"]),
            ({"min_track_width": -0.1, "min_clearance": 0.1}, ["min_track_width"]),
            ({"min_track_width": "0.1", "min_clearance": 0.1}, ["min_track_width"]),
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
        self.assertIn("KiCad 10.0", readme)


if __name__ == "__main__":
    unittest.main()
