#!/usr/bin/env python3
"""The placement view and its measures, rendered from a throwaway board against the real kicad-cli and resvg.

The board is written from text in a temporary folder outside the repository,
with a layout plan beside it whose floorplan table gives each region's
rectangles and parts. Every connection, length and crossing it should measure
is worked out by hand below, from the pad centres the parts are placed at, so
the tests hold the command to a placement known in advance rather than to its
own arithmetic. The view is rendered once through the shipped task; the stops,
the refusals, a routed copy and a worse placement are driven through the
command itself. Nothing is skipped when a tool is absent: a command that cannot
be exercised has not been shown to work.
"""

from __future__ import annotations

import contextlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
import board_fixtures  # noqa: E402
import board_placement  # noqa: E402
import board_views  # noqa: E402
from board_fixtures import MINIMUM_MM, footprint, pad, project, uuid  # noqa: E402

REPO = board_fixtures.REPO
KICAD_CLI = os.environ.get("KICAD_CLI") or "kicad-cli"
RESVG = os.environ.get("RESVG") or "resvg"
REVIEW_PROOF = os.path.join(REPO, "hardware", "proof", "review-proof")

_RENDERED = {}


def setUpModule():
    board_fixtures.require_tools(KICAD_CLI, RESVG)


def tearDownModule():
    board_fixtures.cleanup()


# --- The throwaway placement --------------------------------------------------------------


def part(reference, x, y, pads, angle=0, courtyard=(-2.5, -2.5, 2.5, 2.5)):
    """A part whose pads are (number, x, y, net) of its own, turned with it."""
    return footprint(reference, x, y, [pad(number, px, py, net, "passive", angle) for number, px, py, net in pads],
                     angle=angle, courtyard=courtyard)


def parts(r1_turned=False):
    """The board's parts. With `r1_turned`, R1 is turned half round, so its pads face away from the pads they join."""
    return [
        part("J1", 5, 10, [(1, 0, -1, "A"), (2, 0, 1, "GND")]),
        part("R1", 20, 10, [(1, 0, -1, "A"), (2, 0, 1, "GND")], angle=180 if r1_turned else 0),
        part("U3", 40, 10, [(1, -2, -1, "S"), (2, -2, 1, "GND"), (3, 2, -1, "T")]),
        part("D1", 48, 10, [(1, -2, -1, "S"), (2, 2, 1, "NC1")]),
        part("C2", 45, 34, [(1, 0, -1, "T"), (2, 0, 1, "NC6")]),
        part("Q1", 10, 30, [(1, 2, 0, "H"), (2, 0, 2, "NC2")]),
        part("Q2", 17, 22, [(1, 0, 2, "V"), (2, 2, 0, "NC3")]),
        part("Q3", 24, 30, [(1, -2, 0, "H")]),
        part("Q4", 17, 38.5, [(1, 0, -2, "V")], courtyard=None),
        part("U1", 30, 30, [(1, -2, 0, "NC4"), (2, 2, 0, "W")]),
        part("U2", 52, 30, [(1, -2, 0, "W"), (2, 2, 0, "NC5")]),
    ]


#: Every connection the placement leaves, worked out by hand: each net's shortest tree over its pad centres, as
#: pairs of pad centres. GND's three pads lie on one line, so its tree runs J1 to R1 to U3, its two segments
#: meeting at R1's pad.
CONNECTIONS = {
    "A": [((5, 9), (20, 9))],
    "GND": [((5, 11), (20, 11)), ((20, 11), (38, 11))],
    "H": [((12, 30), (22, 30))],
    "S": [((38, 9), (46, 9))],
    "T": [((42, 9), (45, 33))],
    "V": [((17, 24), (17, 36.5))],
    "W": [((32, 30), (50, 30))],
}
#: The crossings: H and V cross at (17, 30); S runs through T's pad centre at (42, 9), where T's connection begins;
#: T crosses W at (44.625, 30). GND's two segments touch at R1's pad and are never counted against each other.
CROSSINGS = {"A": 0, "GND": 0, "H": 1, "S": 1, "T": 2, "V": 1, "W": 1}
#: The parts outside their regions: C2 is listed in digital and placed in analog sensing, and D1 is listed in none.
#: U1 straddles low voltage and analog sensing, listed in both, and Q4, which has no courtyard, is held to its pad.
OUTSIDE = {"C2": ["digital"], "D1": []}

PLAN = """# Layout plan

## Floorplan

| Region | Bounds | What it holds | Parts |
|---|---|---|---|
| mains | none: the board carries no mains | nothing | none |
| low voltage | (0, 0)–(30, 40) | the connector, its resistor and the crossing pair | {low} |
| analog sensing | (30, 20)–(45, 40), (45, 20)–(60, 40) | the two-sided part and its partner | U1, U2 |
| digital | (30, 0)–(60, 20) | the controller and its capacitor | U3, C2 |

| Connector | Edge | Position |
|---|---|---|
| J1 | left | (5, 9) |
"""
LOW = "J1, R1, Q1, Q2, Q3, Q4, U1"


def plan(low=LOW, **replace):
    text = PLAN.replace("{low}", low)
    for old, new in replace.items():
        text = text.replace(old, new)
    return text


#: Copper a routed copy of the board carries: a track of each two-pad net and of GND, a via and a ground zone.
ROUTING = [
    f'(segment (start 5 9) (end 20 9) (width 0.25) (layer "F.Cu") (net "A") (uuid {uuid()}))',
    f'(segment (start 5 11) (end 38 11) (width 0.25) (layer "F.Cu") (net "GND") (uuid {uuid()}))',
    f'(segment (start 12 30) (end 22 30) (width 0.25) (layer "F.Cu") (net "H") (uuid {uuid()}))',
    f'(segment (start 17 24) (end 17 28) (width 0.25) (layer "F.Cu") (net "V") (uuid {uuid()}))',
    f'(via (at 17 28) (size 0.8) (drill 0.4) (layers "F.Cu" "B.Cu") (net "V") (uuid {uuid()}))',
    f'(segment (start 17 28) (end 17 36.5) (width 0.25) (layer "B.Cu") (net "V") (uuid {uuid()}))',
    f'(arc (start 32 30) (mid 41 25) (end 50 30) (width 0.25) (layer "F.Cu") (net "W") (uuid {uuid()}))',
    f'(zone (net "GND") (layer "B.Cu") (uuid {uuid()}) (hatch edge 0.5) (connect_pads (clearance 0.5)) '
    '(min_thickness 0.25) (filled_areas_thickness no) (fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5)) '
    '(polygon (pts (xy 2 2) (xy 58 2) (xy 58 18) (xy 2 18))))',
]


class Placed(board_fixtures.Design):
    """The throwaway board, its project and its layout plan, with a working folder for the placement view."""

    def __init__(self, items=None, plan_text=None, project_text=None):
        super().__init__(board_fixtures.layout(parts() if items is None else items),
                         project(assignments={}) if project_text is None else project_text,
                         prefix="board-placement-test-", out="placement")
        if plan_text is not False:
            self.write("layout-plan.md", plan() if plan_text is None else plan_text)

    def args(self, out=None):
        return ["--board", self.board, "--project", self.project, "--out", out or self.out]

    def run(self, out=None, kicad_cli=KICAD_CLI, resvg=RESVG):
        stream, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(errors):
            status = board_placement.main(["--kicad-cli", kicad_cli, "--resvg", resvg, *self.args(out)], out=stream)
        return status, stream.getvalue().splitlines(), errors.getvalue()

    def read(self, name, out=None):
        with open(os.path.join(out or self.out, name), encoding="utf-8") as handle:
            return json.load(handle) if name.endswith(".json") else handle.read()


def rendered():
    """The placement, rendered once through the shipped task: (design, task result, index, measures)."""
    if not _RENDERED:
        design = Placed()
        result = subprocess.run(["task", "hw:placement", f"KICAD_CLI={KICAD_CLI}", f"RESVG={RESVG}", "--",
                                 *design.args()], cwd=REPO, capture_output=True, text=True, timeout=900)
        index = measures = None
        if result.returncode == 0:
            index, measures = design.read("index.json"), design.read("measures.json")
        _RENDERED.update(design=design, result=result, index=index, measures=measures, pixels={})
    return _RENDERED


def by_net(measures):
    return {net["net"]: net for net in measures["nets"]}


class Placement(unittest.TestCase):
    """SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: One command draws a placement's unrouted connections and measures them."""

    @classmethod
    def setUpClass(cls):
        cls.placed = rendered()

    def setUp(self):
        result = self.placed["result"]
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.design, self.index, self.measures = self.placed["design"], self.placed["index"], self.placed["measures"]

    def pixels(self, image):
        cache = self.placed["pixels"]
        if image["file"] not in cache:
            cache[image["file"]] = board_views.read_png(os.path.join(self.design.out, image["file"]))
        return cache[image["file"]]

    def colour_at(self, x, y):
        for image in self.index["images"]:
            box, scale = image["region_mm"], image["scale_px_per_mm"]
            if box["x0"] <= x < box["x1"] and box["y0"] <= y < box["y1"]:
                return self.pixels(image)[2][int((y - box["y0"]) * scale)][int((x - box["x0"]) * scale)][:3]
        self.fail(f"no image covers ({x}, {y}) mm")

    def seen(self, x, y, colour, reach=0.1):
        """Whether the colour is drawn anywhere within `reach` millimetres of the board point (x, y)."""
        steps = [step / 30 for step in range(-round(reach * 30), round(reach * 30) + 1)]
        return any(board_fixtures.partly(self.colour_at(x + dx, y + dy), colour, board_views.BACKGROUND)
                   for dx in steps for dy in steps)

    def test_each_connection_is_drawn_straight_between_the_pads_it_joins_and_no_other(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: One command renders an image of the board's parts with each net's connections drawn as straight lines between the pads they join, the minimum spanning tree over its pad centres.
        green = board_placement.CONNECTION[0]
        for net, edges in CONNECTIONS.items():
            for (ax, ay), (bx, by) in edges:
                for share in (0.2, 0.5, 0.8):
                    at = (ax + share * (bx - ax), ay + share * (by - ay))
                    with self.subTest(net=net, at=at):
                        self.assertTrue(self.seen(*at, green), f"{net}'s connection is not drawn at {at}")
        # Pads of different nets, and pads one part carries on two nets, are never joined, and a connection stops at
        # the pads it joins: A's runs no further than R1's pad at x = 20 mm towards U3's pad on S at x = 38 mm.
        for at in ((14.5, 27), (5, 10), (19.5, 33.25), (30, 30), (21.5, 9)):
            with self.subTest(between=at):
                self.assertFalse(self.seen(*at, green), f"a connection is drawn at {at}, between pads it does not join")

    def test_the_regions_are_drawn_and_named_and_a_region_recorded_as_none_is_read(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: The floorplan's region rectangles are drawn and named on it; a region whose bounds are recorded as none is read as a region with no rectangle.
        cyan = board_placement.REGION[0]
        edge = [self.seen(30, y / 2, cyan, reach=0.05) for y in range(2, 38)]
        self.assertGreater(sum(edge), len(edge) / 2, "the boundary at x = 30 mm between regions is not drawn")
        self.assertTrue(any(board_fixtures.partly(self.colour_at(x / 20, y / 20), cyan, board_views.BACKGROUND)
                            for x in range(4, 60) for y in range(3, 12)), "the low voltage region is not named on it")
        for image in self.index["images"]:
            self.assertIn("floorplan regions as cyan dashed outlines, each named: mains none, low voltage (0, 0)–(30, "
                          "40), analog sensing (30, 20)–(45, 40), (45, 20)–(60, 40), digital (30, 0)–(60, 20)",
                          image["caption"])
        self.assertEqual(self.measures["regions"], [
            {"name": "mains", "bounds": "none", "parts": []},
            {"name": "low voltage", "bounds": "(0, 0)–(30, 40)", "parts": LOW.split(", ")},
            {"name": "analog sensing", "bounds": "(30, 20)–(45, 40), (45, 20)–(60, 40)", "parts": ["U1", "U2"]},
            {"name": "digital", "bounds": "(30, 0)–(60, 20)", "parts": ["U3", "C2"]}])

    def test_the_measures_are_those_of_the_known_placement(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: The measures are the total length of the connections and each net's length, the crossings in total and by net, and every part outside its regions, a part listed in two regions outside only when it leaves both and a part listed in none outside.
        lengths = {net: sum(math.dist(a, b) for a, b in edges) for net, edges in CONNECTIONS.items()}
        self.assertEqual([net["net"] for net in self.measures["nets"]], list(CONNECTIONS))
        for net, measured in by_net(self.measures).items():
            with self.subTest(net=net):
                self.assertAlmostEqual(measured["length_mm"], lengths[net], places=3)
                self.assertEqual(measured["crossings"], CROSSINGS[net])
                self.assertEqual(measured["pads"], len({pad for edge in CONNECTIONS[net] for pad in edge}))
        self.assertAlmostEqual(self.measures["total_length_mm"], sum(lengths.values()), places=3)
        self.assertEqual(self.measures["crossings"], sum(CROSSINGS.values()) // 2)
        self.assertEqual({part["reference"]: part["regions"] for part in self.measures["outside"]}, OUTSIDE)
        c2 = next(part for part in self.measures["outside"] if part["reference"] == "C2")
        self.assertEqual(c2["extent_mm"], {"x0": 42.5, "y0": 31.5, "x1": 47.5, "y1": 36.5}, "C2's extent is its courtyard")
        report = self.placed["result"].stdout
        self.assertIn("OUTSIDE | C2 | listed in digital", report)
        self.assertIn("OUTSIDE | D1 | listed in no region of the floorplan", report)
        self.assertIn(f"MEASURES | length {board_views.mm_text(sum(lengths.values()))} mm | 3 crossings | 2 parts "
                      "outside their regions", report)

    def test_the_text_and_json_measures_agree(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: The measures are written as text and as JSON, and the two agree.
        lines = self.design.read("measures.txt").splitlines()
        fields = [line.split(" | ") for line in lines]
        self.assertEqual(fields[0], ["BOARD", self.measures["board"]])
        self.assertIn(["LENGTH", "total", f"{board_views.mm_text(self.measures['total_length_mm'])} mm"], fields)
        self.assertIn(["CROSSINGS", "total", str(self.measures["crossings"])], fields)
        self.assertIn(["OUTSIDE", "total", str(len(self.measures["outside"]))], fields)
        nets = [row for row in fields if row[0] == "NET"]
        self.assertEqual(len(nets), len(self.measures["nets"]))
        for row, net in zip(nets, self.measures["nets"]):
            self.assertEqual(row, ["NET", net["net"], f"{net['pads']} pads", f"length {board_views.mm_text(net['length_mm'])} mm",
                                   f"{net['crossings']} crossings"])
        outside = [row[1] for row in fields if row[0] == "OUTSIDE" and row[1] != "total"]
        self.assertEqual(outside, [part["reference"] for part in self.measures["outside"]])
        regions = [row for row in fields if row[0] == "REGION"]
        self.assertEqual(regions, [["REGION", region["name"], region["bounds"], ", ".join(region["parts"]) or "none"]
                                   for region in self.measures["regions"]])

    def test_the_view_takes_the_review_views_form_and_its_index_names_it_placement(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: The command writes into an output folder of its own under its own index as text and JSON naming the image placement, on a dark background, with a caption drawn into the image, at the resolution the board-wide minimums give, in tiles within the views' size limits.
        written = sorted(os.listdir(self.design.out))
        images = self.index["images"]
        self.assertEqual(written, sorted(["index.txt", "index.json", "measures.txt", "measures.json"]
                                         + [image["file"] for image in images]))
        self.assertGreater(len(images), 1, "a 60 mm board at 30 px/mm is wider than the limit, so it is tiled")
        self.assertEqual({image["view"] for image in images}, {"placement"})
        for image in images:
            self.assertRegex(image["file"], r"^placement-r\d+c\d+\.png$")
            self.assertIn(f"IMAGE | {image['file']} | {image['caption']}", self.design.read("index.txt"))
        self.assertEqual(self.index["resolution"]["px_per_mm"], 3 / MINIMUM_MM)
        self.assertEqual(self.index["measures"], {"text": "measures.txt", "json": "measures.json"})
        background = board_fixtures.hex_rgb(board_views.BACKGROUND)
        for image in images:
            with self.subTest(image=image["file"]):
                width, height, rows = self.pixels(image)
                self.assertEqual((width, height), (image["size_px"]["width"], image["size_px"]["height"]))
                self.assertTrue(board_views.fits(width, height), "a tile is over the size limit")
                self.assertEqual(rows[height - 1][0][:3], background)
                caption = rows[image["content_px"]["height"] + 2:]
                self.assertTrue(any(sum(pixel[:3]) > 500 for row in caption for pixel in row), "no caption drawn in")
                self.assertIn("30 px/mm", image["caption"])
                self.assertIn("connections in bright green", image["caption"])
        top, bottom = min(image["region_mm"]["y0"] for image in images), max(image["region_mm"]["y1"] for image in images)
        left, right = min(image["region_mm"]["x0"] for image in images), max(image["region_mm"]["x1"] for image in images)
        self.assertTrue(left <= 0 and top <= 0 and right >= 60 and bottom >= 40, "the tiles do not cover the board")

    def test_the_design_folder_is_left_untouched(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: The command writes into an output folder of its own.
        self.assertEqual(sorted(os.listdir(self.design.folder)), ["layout-plan.md", "proof.kicad_pcb", "proof.kicad_pro"])


class Placements(unittest.TestCase):
    """SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: One command draws a placement's unrouted connections and measures them."""

    def written(self, design):
        status, lines, errors = design.run()
        self.assertEqual(status, 0, lines + [errors])
        return design.read("measures.json")

    def test_a_routed_copy_measures_and_draws_the_same_as_the_unrouted_original(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: Copper already laid is ignored, so a routed copy of a board measures the same as the unrouted original.
        original, routed = Placed(), Placed(items=parts() + ROUTING)
        before, after = self.written(original), self.written(routed)
        self.assertNotEqual(before.pop("board"), after.pop("board"))
        self.assertEqual(after, before)
        first, second = original.read("index.json"), routed.read("index.json")
        self.assertEqual([image["file"] for image in first["images"]], [image["file"] for image in second["images"]])
        for image in first["images"]:
            self.assertEqual(board_views.read_png(os.path.join(original.out, image["file"])),
                             board_views.read_png(os.path.join(routed.out, image["file"])),
                             f"{image['file']} draws the routed copy's copper")

    def test_a_worse_placement_of_the_same_parts_measures_worse(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: A worse placement of the same parts measures worse.
        good, worse = self.written(Placed()), self.written(Placed(items=parts(r1_turned=True)))
        # R1 turned half round brings A to its far pad and GND to its near one, so the two connections cross.
        self.assertGreater(worse["total_length_mm"], good["total_length_mm"])
        self.assertEqual(worse["crossings"], good["crossings"] + 1)
        self.assertEqual((by_net(worse)["A"]["crossings"], by_net(worse)["GND"]["crossings"]), (1, 1))
        self.assertAlmostEqual(by_net(worse)["A"]["length_mm"], math.dist((5, 9), (20, 11)), places=3)
        self.assertAlmostEqual(by_net(worse)["GND"]["length_mm"], math.dist((5, 11), (20, 9)) + math.dist((20, 9), (38, 11)),
                               places=3)

    def test_the_repositorys_review_proof_design_is_measured_with_every_part_in_its_regions(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: The command reads each region's rectangle and the parts it holds from the floorplan table in the board's layout plan.
        with tempfile.TemporaryDirectory(prefix="board-placement-review-proof-") as root:
            folder = os.path.join(root, "review-proof")
            os.makedirs(folder)
            for name in ("review-proof.kicad_pcb", "review-proof.kicad_pro", "review-proof.kicad_dru", "layout-plan.md"):
                shutil.copy2(os.path.join(REVIEW_PROOF, name), folder)
            out = os.path.join(root, "placement")
            stream = io.StringIO()
            status = board_placement.main(["--kicad-cli", KICAD_CLI, "--resvg", RESVG, "--board",
                                           os.path.join(folder, "review-proof.kicad_pcb"), "--project",
                                           os.path.join(folder, "review-proof.kicad_pro"), "--out", out], out=stream)
            lines = stream.getvalue().splitlines()
            self.assertEqual(status, 0, lines)
            with open(os.path.join(out, "measures.json"), encoding="utf-8") as handle:
                measured = json.load(handle)
            self.assertEqual(measured["outside"], [], "a part of the clean proof design is outside its regions")
            listed = {name for region in measured["regions"] for name in region["parts"]}
            self.assertEqual(listed, set(board_placement.footprints(
                board_views.locked_copper.read_layout(os.path.join(folder, "review-proof.kicad_pcb")))))


class Geometry(unittest.TestCase):
    """SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: One command draws a placement's unrouted connections and measures them."""

    def test_segments_meet_when_they_cross_touch_or_overlap_and_not_otherwise(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: A crossing is two segments of different nets that intersect, touch or overlap.
        meet = board_placement.meet
        self.assertTrue(meet((0, 0), (10, 0), (5, -5), (5, 5)), "a crossing")
        self.assertTrue(meet((0, 0), (10, 0), (5, 0), (5, 5)), "one ends on the other")
        self.assertTrue(meet((0, 0), (10, 0), (10, 0), (12, 3)), "end to end")
        self.assertTrue(meet((0, 0), (10, 0), (4, 0), (14, 0)), "overlapping along one line")
        self.assertFalse(meet((0, 0), (10, 0), (11, 0), (14, 0)), "apart along one line")
        self.assertFalse(meet((0, 0), (10, 0), (0, 1), (10, 1)), "side by side")
        self.assertFalse(meet((0, 0), (10, 10), (6, 4), (10, 0)), "short of the other")

    def test_a_box_is_covered_only_by_the_union_of_the_rectangles_holding_all_of_it(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: A part is outside when its extent is not covered by the union of the rectangles of the regions it is listed in.
        covered = board_placement.covered
        halves = [(0, 0, 10, 10), (10, 0, 20, 10)]
        self.assertTrue(covered((8, 2, 12, 8), halves), "across the seam of two rectangles")
        self.assertFalse(covered((8, 2, 12, 8), halves[:1]), "past the edge of one")
        self.assertFalse(covered((8, 8, 12, 12), halves), "past the edge of both")
        self.assertFalse(covered((1, 1, 19, 9), [(0, 0, 9, 10), (11, 0, 20, 10)]), "over a gap between them")
        self.assertTrue(covered((0, 0, 10, 10), halves[:1]), "exactly on its edges")
        self.assertFalse(covered((1, 1, 2, 2), []), "by no rectangle")


class Stops(unittest.TestCase):
    """SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: One command draws a placement's unrouted connections and measures them."""

    def assertStopped(self, design, named):
        status, lines, _ = design.run()
        self.assertEqual(status, 1, lines)
        self.assertTrue(lines[0].startswith("UNREADABLE | ") and all(words in lines[0] for words in named), lines)
        self.assertEqual(lines[-1], "RESULT | FAIL | the input cannot be read, so no placement view was written")
        self.assertFalse(os.path.exists(design.out), "the output folder was made")
        return lines

    def test_a_missing_floorplan_stops_the_command_naming_it(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: A missing floorplan stops the command with a message naming it.
        design = Placed(plan_text=False)
        self.assertStopped(design, [os.path.join(design.folder, "layout-plan.md"), "is missing"])
        self.assertStopped(Placed(plan_text="# Layout plan\n\nNo table.\n"), ["holds no floorplan table"])
        no_parts = ("# Layout plan\n\n| Region | Bounds | What it holds |\n|---|---|---|\n"
                    "| mains | none: the board carries no mains | nothing |\n| low voltage | (0, 0)–(60, 40) | all |\n")
        self.assertStopped(Placed(plan_text=no_parts), ["has no Parts column"])

    def test_a_region_row_that_cannot_be_read_stops_the_command_naming_it(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: A region row that cannot be read stops the command with a message naming it.
        cases = (
            ({"(30, 0)–(60, 20)": "(30, 0) to (60, 20)"}, ["region row 'digital'", "(30, 0) to (60, 20)"]),
            ({"(30, 0)–(60, 20)": "(30, 0)–(60, 20) and the rest"}, ["region row 'digital'"]),
            ({"(30, 0)–(60, 20)": "(30, 0)–(30, 20)"}, ["region row 'digital'", "has no area"]),
            ({"| U3, C2 |": "| U3 C2 |"}, ["region row 'digital'", "'U3 C2'", "without ranges"]),
            ({"| U1, U2 |": "| U1, U2 | extra |"}, ["region row 'analog sensing'", "5 cells where its header has 4"]),
        )
        for replace, named in cases:
            with self.subTest(replace=replace):
                self.assertStopped(Placed(plan_text=plan(**replace)), named)
        for listed in ("Q1–Q4, J1, R1, U1", "Q1-Q4, J1, R1, U1"):
            with self.subTest(listed=listed):
                self.assertStopped(Placed(plan_text=plan(low=listed)), ["region row 'low voltage'", listed.split(",")[0],
                                                                       "without ranges"])

    def test_a_floorplan_table_without_its_separator_row_stops_the_command_rather_than_losing_a_region(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: A region row that cannot be read stops the command with a message naming it, so a table whose first region row would be taken for its separator row stops rather than losing that region.
        for separator in ("", "|---|---|---|\n", "| a | b | c | d |\n"):
            with self.subTest(separator=separator):
                self.assertStopped(Placed(plan_text=plan(**{"|---|---|---|---|\n": separator})),
                                   ["has no separator row", "under its header"])
        self.assertStopped(Placed(plan_text=plan().split("|---|---|---|---|")[0].rstrip() + "\n"),
                           ["has no separator row"])
        aligned = Placed(plan_text=plan(**{"|---|---|---|---|": "|:---|---:|:---:|---|"}))
        regions = board_placement.floorplan(os.path.join(aligned.folder, "layout-plan.md"))
        self.assertEqual([region["name"] for region in regions], ["mains", "low voltage", "analog sensing", "digital"])

    def test_a_footprint_without_a_reference_or_sharing_one_stops_the_command_naming_each(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: A board that cannot be read stops the command with a message naming it: footprints with no reference, or sharing one, cannot be measured against the floorplan's parts, so each such reference is named with how many footprints carry it rather than merged.
        twin = part("R1", 25, 5, [(1, 0, -1, "NC7")])
        blank = part("", 25, 15, [(1, 0, -1, "NC8")])
        lines = self.assertStopped(Placed(items=parts() + [twin, blank, part("  ", 26, 15, [(1, 0, 0, "NC9")])]),
                                   ["2 footprints with no reference", "R1 on 2 footprints",
                                    "give every footprint a reference of its own"])
        self.assertNotIn("Q1", lines[0])
        self.assertStopped(Placed(items=parts() + [blank]), ["1 footprint with no reference"])
        self.assertStopped(Placed(items=parts() + [twin, part("Q1", 25, 25, [(1, 0, 0, "NC9")])]),
                           ["Q1 on 2 footprints; R1 on 2 footprints"])

    def test_a_part_listed_in_a_region_recorded_as_none_stops_the_command(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: A part listed in a region recorded as none stops the command with a message naming it.
        self.assertStopped(Placed(plan_text=plan(**{"| nothing | none |": "| nothing | J1 |"})),
                           ["region row 'mains'", "records the region as none and lists parts in it: J1"])

    def test_a_listed_part_not_on_the_board_stops_the_command(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: A listed part that is not on the board stops the command with a message naming it.
        self.assertStopped(Placed(plan_text=plan(low=LOW + ", R9")), ["lists R9 in the region 'low voltage'",
                                                                     "no part on the board"])


class Refusals(unittest.TestCase):
    """SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: One command draws a placement's unrouted connections and measures them."""

    def assertRefused(self, design, named, out=None):
        status, lines, _ = design.run(out)
        self.assertEqual(status, 1, lines)
        self.assertEqual(lines[-1], "RESULT | REFUSED | no placement view was written", lines)
        self.assertTrue(any(line.startswith("REFUSED | ") and named in line for line in lines), lines)
        return lines

    def test_a_board_open_in_an_editor_is_refused(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: The command takes the views' refusal of a board open in an editor.
        design = Placed()
        lock = design.write("~proof.kicad_pcb.lck", "{}")
        self.assertRefused(design, f"REFUSED | {lock} | KiCad's lock file shows {design.board} open in an editor")
        self.assertFalse(os.path.exists(design.out))

    def test_a_board_stating_no_minimum_or_a_zero_one_is_refused_naming_the_figure(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: The command takes the views' refusal of an unset minimum, its resolution coming from the board-wide minimum track width and clearance.
        for rules, named in (({}, ["min_track_width", "min_clearance"]), ({"min_track_width": 0.1}, ["min_clearance"]),
                             ({"min_track_width": 0, "min_clearance": 0.1}, ["min_track_width"])):
            with self.subTest(rules=rules):
                design = Placed(project_text=project(assignments={}, rules=rules))
                lines = self.assertRefused(design, "board.design_settings.rules.")
                self.assertEqual(sorted(line.split(" | ")[1].rsplit(".", 1)[1] for line in lines if line.startswith("REFUSED | ")),
                                 sorted(named))
                self.assertFalse(os.path.exists(design.out))

    def test_an_output_folder_inside_a_design_folder_holding_files_or_a_file_is_refused(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: The command writes into an output folder of its own, never one the views command writes, and takes the views' refusals of an output folder inside a design's folder or already holding files.
        design = Placed()
        inside = os.path.join(design.folder, "placement")
        self.assertRefused(design, "never kept in a design's folder", out=inside)
        self.assertFalse(os.path.exists(inside))
        views = os.path.join(design.root, "views")
        os.makedirs(views)
        with open(os.path.join(views, "index.txt"), "w", encoding="utf-8") as handle:
            handle.write("the views' own index\n")
        self.assertRefused(design, "already holds files", out=views)
        self.assertEqual(os.listdir(views), ["index.txt"])
        afile = os.path.join(design.root, "a-file")
        with open(afile, "w", encoding="utf-8") as handle:
            handle.write("x")
        self.assertRefused(design, "the output folder is a file", out=afile)

    def test_a_project_file_not_the_boards_own_is_refused(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: The command takes the views' refusals.
        design = Placed()
        stray = os.path.join(design.root, "stray.kicad_pro")
        shutil.copy2(design.project, stray)
        design.project = stray
        self.assertRefused(design, "give the board's own project file")

    def test_a_missing_rasteriser_stops_the_command_naming_it(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: The hardware tools' guide names the tools the command needs.
        design = Placed()
        status, lines, errors = design.run(resvg="/nonexistent/resvg")
        self.assertEqual((status, lines), (2, []))
        self.assertIn("CANNOT RUN | resvg was not found", errors)
        self.assertFalse(os.path.exists(design.out))


class Documentation(unittest.TestCase):
    """SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: One command draws a placement's unrouted connections and measures them."""

    def read(self, *path):
        with open(os.path.join(REPO, *path), encoding="utf-8") as handle:
            return handle.read()

    def test_the_guide_describes_the_command_as_it_describes_the_views_command(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C1: The hardware tools' guide describes the command as it describes the views command: its task, its outputs and their names, its measures, its refusals and stops, and the tools it needs.
        readme = self.read("hardware", "README.md")
        section = readme[readme.index("## The placement view"):]
        section = section[:section.index("\n## ")]
        for words in ("task hw:placement -- --board <board>.kicad_pcb --project <board>.kicad_pro --out <folder>",
                      "`placement`", "`index.txt`", "`index.json`", "`measures.txt`", "`measures.json`",
                      "minimum spanning tree", "Copper already laid is ignored", "total length", "each net's length",
                      "crossing", "intersect, touch or overlap", "outside", "courtyard", "listed in no region",
                      "a board KiCad's lock file shows open in an editor", "no minimum track width",
                      "an output folder inside any design's folder", "already holds files", "is missing",
                      "cannot be read", "recorded as `none`", "not on the board", "resvg", "KiCad", "`CANNOT RUN`",
                      "`UNREADABLE`", "`REFUSED`", "-r<row>c<column>"):
            with self.subTest(words=words):
                self.assertIn(words, section)
        taskfile = self.read("Taskfile.yml")
        task = taskfile[taskfile.index("  hw:placement:"):]
        task = task[:task.index("\n\n")]
        for words in ("board_placement.py", "RESVG", "KICAD_CLI", "resvg 0.47 or newer", "layout-plan.md"):
            self.assertIn(words, task)
        test = taskfile[taskfile.index("  hw:test:"):]
        self.assertIn("the placement view", test.splitlines()[1], "hw:test's description names the tools it tests")
        self.assertIn("`task hw:placement`", readme[:readme.index("## The locked-copper check")])


#: The items C2 names as judged at placement: those whose Asks question asks where a part sits, and MAINS-2.
PLACEMENT_ITEMS = {"FLOOR-1", "FLOOR-3", "POWER-2", "DECOUPLE-1", "DECOUPLE-3", "DECOUPLE-4", "DECOUPLE-5", "SENSE-2",
                   "SENSE-3", "SENSE-5", "CLOCK-1", "CLOCK-3", "MAINS-2", "CONN-1", "CONN-2", "CONN-3", "CONN-4", "TEST-2",
                   "EMI-3", "EMI-4", "EMI-5", "TEST-1", "WORK-1", "FLOOR-5"}


def section(text, heading, level="## "):
    """The text of the section headed `heading`, up to the next heading of its level."""
    start = text.index(f"{level}{heading}\n")
    after = text.find(f"\n{level}", start + len(level))
    return text[start:after if after >= 0 else len(text)]


class Method(unittest.TestCase):
    """SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C2: A board's placement is chosen from several candidates, each measured and judged before any track is drawn."""

    def setUp(self):
        with open(os.path.join(REPO, "docs", "board-design-method.md"), encoding="utf-8") as handle:
            self.method = handle.read()

    def test_the_catalogue_names_the_placement_view_on_exactly_the_items_judged_at_placement(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C2: The catalogue marks the items judged at placement by naming the placement view in their Judged on line.
        items = re.findall(r"^#### ([A-Z]+-\d+)\. .*?^- \*\*Judged on:\*\* (.*?)$", self.method, re.M | re.S)
        self.assertEqual(len(items), len(re.findall(r"^#### [A-Z]+-\d+\. ", self.method, re.M)))
        self.assertEqual({item for item, line in items if "`placement`" in line}, PLACEMENT_ITEMS)
        test_1 = dict(items)["TEST-1"]
        self.assertIn("`placement`, for its spacing from part bodies", test_1)
        read = section(self.method, "How an item is read", "### ")
        self.assertIn("the placement view, `placement`", read)
        self.assertIn("is judged at [placement](#placement) too", read)

    def test_the_placement_step_sits_between_planning_and_the_rules_and_says_how_to_choose(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C2: A placement step between planning the layout and the rules places the fixed parts first, produces at least two candidates each committed before it is rendered, measures and judges each, and records the choice before any track.
        order = [self.method.index(f"\n## {name}\n") for name in ("Planning the layout", "Placement", "Rules before routing")]
        self.assertEqual(order, sorted(order))
        placement = section(self.method, "Placement")
        steps = re.findall(r"^### (\d+)\. ", placement, re.M)
        self.assertEqual(steps, ["1", "2", "3", "4", "5", "6"])
        for words in ("min_track_width", "`MFG-1`", "`design-rules.md`", "each connector, terminal and header",
                      "each mounting hole, and the mains region's parts", "the main integrated circuit of each block "
                      "before the parts that serve it", "turned so its pins face the pins they join",
                      "at least two candidate", "committed in a commit of its own before it is rendered",
                      "task hw:placement -- --board <board>.kicad_pcb --project <board>.kicad_pro --out",
                      "git worktree add --detach", "Never commit it", "| Item | Verdict | Rests on | Why |",
                      "is not chosen", "never a fixed weighting of the measures", "`## Placement`", "**Commit**",
                      "**Renders**", "**Measures**", "**Chosen**", "and before any track, arc, via or pour is drawn. Its purpose",
                      "### 6. Choose one, and record the placement before any track, arc, via or pour\n",
                      "in a fenced code block below the field",
                      "a section committed empty, or in part, and filled in after the first track does not pass",
                      "task hw:history -- --board <board>.kicad_pcb", "`before first track`", "`RESULT | PASS`",
                      "- `first track`:", "- `placement section`:", "- `placement items`:", "- `candidates`:",
                      "- `candidate <n> commit`:", "- `candidate <n> measures`:", "- `candidate <n> verdicts`:",
                      "- `distinct candidates`:", "- `chosen`:", "- `parts at first track`, or `parts at HEAD`",
                      "- `first placement`:", "- `plan before placement`:",
                      "merges into the main line without rewriting that history",
                      "never squashed, rebased or force-pushed", "The command judges the record's shape and order",
                      "from that commit's board against the floorplan as `<T>^` holds it",
                      "as one whose commit widens a region is, fails", "or in a merge commit none of whose parents"):
            with self.subTest(words=words):
                self.assertIn(words, placement)
        for words in ("git log --reverse", "git worktree add --detach <work folder>/before-track", "awk '/^## /",
                      "cmp <work folder>", "python3 -c", "git merge-base --is-ancestor"):
            with self.subTest(gone=words):
                self.assertNotIn(words, placement, "the history cross-checks are the command's, not prose recipes")

    def test_the_method_says_an_excluded_symbol_is_no_floorplan_part_and_a_failed_compare_rewrites_the_pass(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C2: Amend the method's planning step so it states that a symbol marked excluded from the board is absent from the netlist in the schematic tool's native format, is not a part for the floorplan and is listed in no region, so the plan's cross-check and the placement command's stop on a listed part that is not on the board agree, and so that the amendment for a part added after placement appends the part to its region's parts and changes no bound. Amend the routing step's instruction to repeat from step 2 after a failed compare so that it says the pass with no router commit is rewritten in place, not a further pass appended, since only the last pass may have none and a pass the router has run after is never changed. Amend the method's step 6 description of the history command so it states each behaviour the command now has, with its check labels.
        planning = section(self.method, "Planning the layout")
        for words in ("Every part in the schematic's netlist is listed in at least one region",
                      "A symbol marked excluded from the board is absent from the netlist in the schematic tool's native "
                      "format", "it is not a part for the floorplan and is listed in no region, and listing it fails the "
                      "second cross-check below", "a symbol marked excluded from the board is not in the netlist, so a "
                      "region that lists one fails this cross-check, and the placement command's stop on a listed part "
                      "that is not on the board never meets one",
                      "by amending the floorplan, which appends the part to its region's Parts and changes no bound, no "
                      "other part and no other region", "and that change is committed before the part is placed"):
            with self.subTest(words=words):
                self.assertIn(words, planning)
        self.assertNotIn("Every part on the schematic", planning, "the loose wording is replaced by the netlist's")
        routing = section(self.method, "Routing: critical nets by hand and locked, then the rest")
        compare = section(routing, "7. Compare the imported board with the record", "### ")
        for words in ("correct the cause, and repeat from step 2. The repeat rewrites in place the pass that has no "
                      "router commit, the last, and appends no further pass",
                      "only the last pass may have no router commit, so a pass appended after one that has no router commit "
                      "fails `pass <k> before router`, where <k> is that earlier pass, the one with no router commit, and a "
                      "pass the router has run after is never changed"):
            with self.subTest(words=words):
                self.assertIn(words, compare)
        record = section(routing, "4. Check the critical routing against the catalogue, before the router runs", "### ")
        self.assertIn("the pass that has no router commit is then rewritten in place", record)
        self.assertIn("step 7 of this section sends the work back to step 2 when a comparison fails", record)
        self.assertNotIn("; step 7 sends the work back", record, "a bare step 7 reads as the layout review's")
        placement = section(self.method, "Placement")
        for words in ("a copper pour, `<T>`", "a rule area, a zone carrying a keepout, carries no net and is no copper",
                      "the first commit whose board holds a footprint, `<P>`, from the history alone and never from the "
                      "section", "The one difference allowed is a reference appended to a region's parts, with no bound "
                      "changed and no reference removed or moved between regions",
                      "in a commit after `<P>^`: a reference listed once, dropped, placed and listed again fails",
                      "A part added after placement began and before the first track, pour, arc or via is committed is "
                      "amended into the plan before it is placed", "A part appended to the plan only after that "
                      "first copper is not compared: it is planned and placed, and the section is left as it is. A part "
                      "appended before that first copper and placed after it is compared still, by the same rule: the "
                      "plan in the commit before the one that places it must list it", "place every part alike",
                      "however their board files differ in a text label or an identifier",
                      "with the references the plan appended left out where that commit's board does not hold them",
                      "before any track, arc, via or copper pour is drawn",
                      "and before any track, arc, via or pour is drawn, run it"):
            with self.subTest(step6=words):
                self.assertIn(words, placement)
        for words in ("Between the first footprint on the board and the first track, pour, arc or via committed, the "
                      "floorplan can only gain appended parts, so a floorplan error found during placement, a bound that "
                      "is wrong, a part in the wrong region or a region missing, has no in-place fix: the work restarts "
                      "from a fresh branch, with the floorplan corrected and committed before any footprint is placed",
                      "A part added after the choice and before the first track, pour, arc or via is committed means "
                      "recording a new candidate that includes it and recording the placement section again",
                      "After the first track, pour, arc or via is committed the recorded section is frozen, and the "
                      "floorplan is held to the commit before the first placement only as it stood in the commit "
                      "before that first copper, so a part appended to it after that copper is not compared: it is "
                      "only planned, by amending the floorplan as above, and placed, and the recorded section is left "
                      "as it is. A part appended before that first copper and placed after it is compared still: the "
                      "plan in the commit before the one that places it must list it",
                      "committed before its footprint first appears on the board and kept in the plan until then"):
            with self.subTest(planning=words):
                self.assertIn(words, planning)

    def test_the_minimums_move_before_placement_and_the_floorplan_lists_each_regions_parts(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C2: The floorplan table gains a Parts column, the planning cross-checks every part is listed, the minimums move before placement, and the proof design's plan is migrated.
        planning = section(self.method, "Planning the layout")
        self.assertIn("| Region | Bounds | What it holds | Parts |", planning)
        self.assertIn("comma-separated and without ranges", planning)
        self.assertIn("is listed in both", planning)
        self.assertIn("every part in the netlist is listed in the Parts column of at least one region, and every "
                      "reference that column lists is a part in the netlist", planning)
        rules = section(self.method, "1. Write every rule and net class down, with its figure and source", "### ")
        self.assertIn("were written before placement ([Placement](#placement), step 1)", rules)
        with open(os.path.join(REVIEW_PROOF, "layout-plan.md"), encoding="utf-8") as handle:
            plan_text = handle.read()
        regions = board_placement.floorplan(os.path.join(REVIEW_PROOF, "layout-plan.md"))
        self.assertEqual([region["name"] for region in regions], ["mains", "low voltage", "analog sensing", "digital"])
        self.assertIn("| Region | Bounds | What it holds | Parts |", plan_text)
        self.assertEqual([name for region in regions for name in region["parts"] if name == "U1"], ["U1", "U1"],
                         "U1 spans the mains boundary, so both regions list it")

    def test_the_review_judges_on_the_placement_view_and_the_seeded_review_is_given_it(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C2: The layout review's list of views gains the placement view, its rendering step and cross-check run the placement command into its own uncommitted folder, and a verdict cites it by its index name.
        views = section(self.method, "Layout review views")
        self.assertIn("(`placement`)", views)
        self.assertIn("task hw:placement -- --board <board>.kicad_pcb --project <board>.kicad_pro --out "
                      "<work folder>/<board>-placement", views)
        self.assertIn("the placement view's is its own, beside the views' and never the same. Never commit either.", views)
        review = section(self.method, "Layout review")
        self.assertIn("render its placement view into a folder of its own beside them", review)
        self.assertIn("the `task hw:views` command and the `task hw:placement` command as they were run", review)
        self.assertIn("or for the placement view the name the placement command's index gives it", review)
        self.assertIn("Render the placement view again from the round's commit with the round's `task hw:placement` "
                      "command", review)
        self.assertIn("its placement view and measures in a folder of their own", review)

    def test_critical_routing_is_checked_against_the_catalogue_before_the_router(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C3: After the critical nets are routed and locked and before the router runs, the views are rendered and every catalogue item bearing on those nets is judged and recorded in a critical routing section committed before the router, with a history cross-check; a rule-kind item is judged on its rules table rows alone.
        routing = section(self.method, "Routing: critical nets by hand and locked, then the rest")
        steps = re.findall(r"^### (\d+)\. (.*)$", routing, re.M)
        self.assertEqual([title.split(",")[0] for _, title in steps][2:6],
                         ["Close the board", "Check the critical routing against the catalogue",
                          "Record the critical-class copper", "Export"])
        self.assertEqual([number for number, _ in steps], [str(n) for n in range(1, 9)])
        check = section(routing, "4. Check the critical routing against the catalogue, before the router runs", "### ")
        for words in ("render the review views with `task hw:views`", "The placement view is not rendered here",
                      "only when an item that bears on the critical nets names `placement` in its *Judged on*",
                      "or else that the placement view was not rendered", "workmanship items included",
                      "`## Critical routing`", "under the heading `### Pass 1`", "only ever appended",
                      "a pass the router has run after is never changed",
                      "| Item | Kind | Severity | Verdict | Rests on | Why |", "on its rows in the rules table alone",
                      "measured half is judged by the pre-order check that step 8 runs after the router",
                      "A `fail` is put right before the router runs", "`fail, then pass at <commit>`",
                      "Commit the section before the router runs", "task hw:history -- --board <board>.kicad_pcb",
                      "whose layout holds at least one track, arc or via and every one of them locked",
                      "`router not yet run`", "the router leaves its copper unlocked",
                      "Step 8 runs the command again once the router's commit is made, with `--routed`",
                      "or in a merge commit, so no one commit is `<R>`",
                      "with `--routed`, the last pass has none, so the router's copper is not committed, or is locked",
                      "as `<R>^` holds the catalogue and the board's own items",
                      "as a merge bringing such copper in from another line of history does",
                      "A router, or any step, that locked its own copper would read as the router not having run",
                      "A net routed by hand and committed before it was locked comes before `<B>`",
                      "- `critical routing section`:", "- `pass <k> board judged`:", "- `pass <k> before router`:",
                      "- `pass <k> verdicts`:", "Removing the router's copper between them passes",
                      "so the branch merges without rewriting it"):
            with self.subTest(words=words):
                self.assertIn(words, check)
        for words in ("-G '^## Critical routing$'", "<section commit>", "after one whose tracks are all locked",
                      "git rev-list", "awk '/^## /", "cmp <work folder>", "python3 -c"):
            with self.subTest(gone=words):
                self.assertNotIn(words, check)
        self.assertNotRegex(self.method, r"step [4-7] of routing does|\(step 7 of routing\)")
        final = section(routing, "8. Run the board's own rule checks, then reopen the board", "### ")
        for words in ("this is the router's commit", "task hw:history -- --board <board>.kicad_pcb --routed",
                      "decides both the placement section",
                      "fails `pass <k> before router` rather than passing as `router not yet run`"):
            with self.subTest(final=words):
                self.assertIn(words, final)
        self.assertNotIn("must not say", final, "the router having run is held by --routed, not by the reader")

    def test_the_floorplan_says_every_footprint_is_a_part_on_the_schematic_and_the_catalogue_names_each_use(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C2: The floorplan lists every part against the schematic, and a part listed in no region is outside, so a footprint the schematic does not carry is reported outside and no chosen placement holds one; the minimums the views' resolution reads are written at placement.
        planning = section(self.method, "Planning the layout")
        self.assertIn("every footprint on the board, mounting holes, fiducials and logos among them, is a part drawn on "
                      "the schematic", planning)
        self.assertIn("a footprint the schematic does not carry is listed in no region, and the command reports it "
                      "outside", planning)
        views = section(self.method, "Layout review views")
        self.assertIn("from step 1 of [Placement](#placement)", views)
        self.assertNotIn("step 1 of [Rules before routing]", views)
        catalogue = section(self.method, "Layout practice catalogue")
        self.assertIn("It is used five times on every board", catalogue)
        for words in ("([Placement](#placement), step 5)", "([Rules before routing](#rules-before-routing), step 1)",
                      "([Routing](#routing-critical-nets-by-hand-and-locked-then-the-rest), step 4)"):
            self.assertIn(words, catalogue)
        anchors = set(re.findall(r"\]\(#([a-z0-9-]+)\)", self.method))
        headings = {re.sub(r"[^a-z0-9 -]", "", title.lower()).replace(" ", "-")
                    for title in re.findall(r"^#+ (.*)$", self.method, re.M)}
        self.assertEqual(anchors - headings, set(), "a link names a section the method does not have")

    def test_a_placement_caused_workmanship_finding_is_closed_at_the_placement(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C4: A finding against a workmanship item caused by where parts sit is closed by changing the placement, re-routing what it affects and repeating the placement measures, and its record names the change and the measures before and after.
        close = section(self.method, "7. Close every finding", "### ")
        for words in ("A workmanship finding caused by placement is closed at the placement",
                      "never by reshaping the route around the parts as they stand", "re-route what the change affects",
                      "render the placement view and its measures again", "the placement's measures before and after it",
                      "A finding whose cause is the route alone is corrected in the copper",
                      "Remove the router's copper the change affects rather than editing it",
                      "commit a critical re-route only once it is locked", "appended below the earlier passes, which "
                      "stay as they are", "run `task hw:history -- --board <board>.kicad_pcb --routed` as step 8 of routing does",
                      "or the router's copper is not committed, or is locked",
                      "a `FAIL` on `pass <n> board judged` means", "on `pass <n> before router`, that an earlier pass "
                      "was changed"):
            with self.subTest(words=words):
                self.assertIn(words, close)
        review = section(self.method, "Layout review")
        self.assertIn("is closed by a change to the placement, naming each part moved or turned and the measures before "
                      "and after it", review)


if __name__ == "__main__":
    unittest.main()
