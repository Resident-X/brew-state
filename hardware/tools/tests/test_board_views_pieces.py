#!/usr/bin/env python3
"""The layout review views, rendered from a synthetic proof board against the real kicad-cli and resvg: the pieces part.

One of the files the original test file is divided into by topic; the tests are unchanged and only live elsewhere.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
import time
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from board_fixtures import LAYER_TABLE  # noqa: E402
from board_fixtures import footprint  # noqa: E402
from board_fixtures import model  # noqa: E402
from board_fixtures import pad  # noqa: E402
from board_fixtures import uuid  # noqa: E402
import board_check  # noqa: E402
import board_views  # noqa: E402
from board_views_fixtures import Design, KICAD_CLI, RESVG, SCALE, layout, setUpModule, tearDownModule  # noqa: E402,F401


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
        paths = ["${KIPRJMOD}/models/box.step", "$(KIPRJMOD)/models/box.step", "models/box.step", "models/nowhere.step",
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
        box = os.path.join(os.path.abspath(design.folder), "models", "box.step")
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


class NetTilePieces(unittest.TestCase):
    """SOL-BOARD-REVIEW-NET-VIEWS-DRAW-ONLY-TILES-HOLDING-THE-NET.C1: Over a synthetic board of several critical nets whose grid is tiled, the views command writes, for each critical net, exactly the tiles of that net's whole-board grid whose board region meets the bounds of at least one element the board tool plotted of the net's filtered copy on any copper layer, and no other tile. Each track or arc is bounded with its width; each via, pad, copper shape on the net and each outline of a zone's fill is bounded separately, edges included. A tile whose only copper of the net is a pad, a via, the end of a track or a corner of a pour's fill is written. The grid is the one planned with the caption at its longest, so which tiles are left out never changes the grid. A written tile keeps the file name, board region, content pixel size, scale and faint whole-board background it has when every tile is written. A net with no plotted copper writes no tile. Tests fail when a written tile meets no element of its net, when a tile meeting one is not written, and when a written tile's name or region differs from the full grid's. A net that spans the board is written in every tile it touches. Out of scope: the layer, assembly, class-map, crop and three-dimensional views."""

    def boxes(self, body):
        with tempfile.TemporaryDirectory(prefix="board-views-boxes-") as folder:
            path = os.path.join(folder, "layer.svg")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 297 210">{body}</svg>')
            return board_views.drawn_boxes(path)

    def assertBoxes(self, found, expected):
        self.assertEqual(len(found), len(expected), found)
        for box, want in zip(found, expected):
            for got, value in zip(box, want):
                self.assertAlmostEqual(got, value, places=6, msg=f"{found}")

    def test_each_plotted_element_is_bounded_apart_with_its_stroke_and_each_subpath_of_a_path_is_its_own_box(self):
        """SOL-BOARD-REVIEW-NET-VIEWS-DRAW-ONLY-TILES-HOLDING-THE-NET.C1: Over a synthetic board of several critical nets whose grid is tiled, the views command writes, for each critical net, exactly the tiles of that net's whole-board grid whose board region meets the bounds of at least one element the board tool plotted of the net's filtered copy on any copper layer, and no other tile. Each track or arc is bounded with its width; each via, pad, copper shape on the net and each outline of a zone's fill is bounded separately, edges included. A tile whose only copper of the net is a pad, a via, the end of a track or a corner of a pour's fill is written. The grid is the one planned with the caption at its longest, so which tiles are left out never changes the grid. A written tile keeps the file name, board region, content pixel size, scale and faint whole-board background it has when every tile is written. A net with no plotted copper writes no tile. Tests fail when a written tile meets no element of its net, when a tile meeting one is not written, and when a written tile's name or region differs from the full grid's. A net that spans the board is written in every tile it touches. Out of scope: the layer, assembly, class-map, crop and three-dimensional views."""
        found = self.boxes('<g style="stroke:#000;stroke-width:0.2;stroke-linejoin:round" transform="translate(10 20)">'
                           '<path d="M 0 0 L 4 0" /><circle cx="1" cy="2" r="0.5" />'
                           '<path d="M 0 5 L 1 5 L 1 6 Z M 8 8 L 9 8 L 9 9 Z m 5 0 l 1 0 l 0 1 z" /></g>')
        self.assertBoxes(found, [(9.9, 19.9, 14.1, 20.1), (10.4, 21.4, 11.6, 22.6), (9.9, 24.9, 11.1, 26.1),
                                 (17.9, 27.9, 19.1, 29.1), (22.9, 27.9, 24.1, 29.1)])
        total = board_views.union(found)
        with tempfile.TemporaryDirectory(prefix="board-views-boxes-") as folder:
            path = os.path.join(folder, "layer.svg")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 297 210"><path d="M 0 0 L 1 1 M 5 5 L 6 6" /></svg>')
            self.assertEqual(board_views.drawn_extent(path), (0, 0, 6, 6), "the extent is the union of the boxes")
            self.assertEqual(board_views.drawn_boxes(path), [(0, 0, 1, 1), (5, 5, 6, 6)])
        self.assertEqual(board_views.path_subpaths("M 0 0 L 1 1 M 5 5 L 6 6 Z"), [[(0, 0), (1, 1)], [(5, 5), (6, 6)]])
        self.assertEqual(board_views.path_points("M 0 0 L 1 1 M 5 5 L 6 6 Z"), [(0, 0), (1, 1), (5, 5), (6, 6)])
        self.assertEqual(total, board_views.union(found))

    def test_a_plot_that_drew_nothing_has_no_boxes(self):
        """SOL-BOARD-REVIEW-NET-VIEWS-DRAW-ONLY-TILES-HOLDING-THE-NET.C1: Over a synthetic board of several critical nets whose grid is tiled, the views command writes, for each critical net, exactly the tiles of that net's whole-board grid whose board region meets the bounds of at least one element the board tool plotted of the net's filtered copy on any copper layer, and no other tile. Each track or arc is bounded with its width; each via, pad, copper shape on the net and each outline of a zone's fill is bounded separately, edges included. A tile whose only copper of the net is a pad, a via, the end of a track or a corner of a pour's fill is written. The grid is the one planned with the caption at its longest, so which tiles are left out never changes the grid. A written tile keeps the file name, board region, content pixel size, scale and faint whole-board background it has when every tile is written. A net with no plotted copper writes no tile. Tests fail when a written tile meets no element of its net, when a tile meeting one is not written, and when a written tile's name or region differs from the full grid's. A net that spans the board is written in every tile it touches. Out of scope: the layer, assembly, class-map, crop and three-dimensional views."""
        self.assertEqual(self.boxes(""), [])
        self.assertEqual(self.boxes('<g opacity="0"><path d="M 0 0 L 9 9" /></g>'), [])

    def test_a_tile_is_chosen_when_its_region_meets_a_box_edges_included_and_in_the_order_planned(self):
        """SOL-BOARD-REVIEW-NET-VIEWS-DRAW-ONLY-TILES-HOLDING-THE-NET.C1: Over a synthetic board of several critical nets whose grid is tiled, the views command writes, for each critical net, exactly the tiles of that net's whole-board grid whose board region meets the bounds of at least one element the board tool plotted of the net's filtered copy on any copper layer, and no other tile. Each track or arc is bounded with its width; each via, pad, copper shape on the net and each outline of a zone's fill is bounded separately, edges included. A tile whose only copper of the net is a pad, a via, the end of a track or a corner of a pour's fill is written. The grid is the one planned with the caption at its longest, so which tiles are left out never changes the grid. A written tile keeps the file name, board region, content pixel size, scale and faint whole-board background it has when every tile is written. A net with no plotted copper writes no tile. Tests fail when a written tile meets no element of its net, when a tile meeting one is not written, and when a written tile's name or region differs from the full grid's. A net that spans the board is written in every tile it touches. Out of scope: the layer, assembly, class-map, crop and three-dimensional views."""
        planned = board_views.tiles((0, 0, 62, 42), SCALE, lambda tile: "c")
        self.assertEqual([(t["row"], t["column"]) for t in planned], [(1, 1), (1, 2), (2, 1), (2, 2)])
        middle_x, middle_y = planned[0]["region"][2], planned[0]["region"][3]

        def chosen(*boxes):
            return [(t["row"], t["column"]) for t in board_views.tiles_holding(planned, boxes)]

        self.assertEqual(chosen(), [], "a net with no plotted copper holds no tile")
        # A lone pad, or the end of one track, well inside a tile.
        self.assertEqual(chosen((50, 30, 51, 31)), [(2, 2)])
        self.assertEqual(chosen((5, 5, 5.5, 5.5), (50, 30, 51, 31)), [(1, 1), (2, 2)])
        # A box that only touches the boundary meets both tiles either side, and one a hair short of it only one.
        self.assertEqual(chosen((middle_x, 5, middle_x + 1, 6)), [(1, 1), (1, 2)])
        self.assertEqual(chosen((middle_x - 1, 5, middle_x, 6)), [(1, 1), (1, 2)])
        self.assertEqual(chosen((middle_x + 1e-6, 5, middle_x + 1, 6)), [(1, 2)])
        self.assertEqual(chosen((middle_x - 1, 5, middle_x - 1e-6, 6)), [(1, 1)])
        self.assertEqual(chosen((5, middle_y, 6, middle_y)), [(1, 1), (2, 1)])
        self.assertEqual(chosen((middle_x, middle_y, middle_x, middle_y)), [(1, 1), (1, 2), (2, 1), (2, 2)],
                         "a point on the corner every tile shares")
        # A track across the board's middle, whose own corners lie in no tile it crosses, is in every tile it crosses.
        self.assertEqual(chosen((1, 20, 60, 22)), [(1, 1), (1, 2), (2, 1), (2, 2)])
        self.assertEqual(chosen((-50, -50, -40, -40), (100, 100, 110, 110)), [])

    def test_a_single_tile_grid_holds_copper_only_when_a_box_meets_it(self):
        """SOL-BOARD-REVIEW-NET-VIEWS-DRAW-ONLY-TILES-HOLDING-THE-NET.C1: Over a synthetic board of several critical nets whose grid is tiled, the views command writes, for each critical net, exactly the tiles of that net's whole-board grid whose board region meets the bounds of at least one element the board tool plotted of the net's filtered copy on any copper layer, and no other tile. Each track or arc is bounded with its width; each via, pad, copper shape on the net and each outline of a zone's fill is bounded separately, edges included. A tile whose only copper of the net is a pad, a via, the end of a track or a corner of a pour's fill is written. The grid is the one planned with the caption at its longest, so which tiles are left out never changes the grid. A written tile keeps the file name, board region, content pixel size, scale and faint whole-board background it has when every tile is written. A net with no plotted copper writes no tile. Tests fail when a written tile meets no element of its net, when a tile meeting one is not written, and when a written tile's name or region differs from the full grid's. A net that spans the board is written in every tile it touches. Out of scope: the layer, assembly, class-map, crop and three-dimensional views."""
        planned = board_views.tiles((0, 0, 10, 10), SCALE, lambda tile: "c")
        self.assertEqual(len(planned), 1)
        self.assertEqual(board_views.tiles_holding(planned, [(2, 2, 3, 3)]), planned)
        self.assertEqual(board_views.tiles_holding(planned, []), [])
        self.assertEqual(board_views.tiles_holding(planned, [(50, 50, 51, 51)]), [])


class NetTileLines(unittest.TestCase):
    """SOL-BOARD-REVIEW-NET-VIEWS-DRAW-ONLY-TILES-HOLDING-THE-NET.C2: For each critical net the index, in text and in JSON, lists the net, the rows and columns of its grid, the tiles written by row and column with the board region each covers, and the number of tiles left out because none of the net's copper is in them; each written tile's caption says that tiles with none of the net's copper are not written and gives the count, and the command's report states the number of images written. A net that wrote every tile of its grid states none left out. Over the synthetic board the text and JSON hold the same facts, a net with copper in one tile of a many-tile grid states the rest as left out, and the counts agree with the files in the output folder. A net with no copper on any copper layer is listed with no tile written, every tile left out and that reason, in the index and in the command's report. Out of scope: the image files themselves, which the first criterion covers."""

    GRID = {"net": "GND", "rows": 2, "columns": 3,
            "tiles_written": [{"file": "net-GND-r1c2.png", "row": 1, "column": 2,
                               "region_mm": {"x0": 10, "y0": 0, "x1": 20, "y1": 15}}],
            "tiles_left_out": 5, "reason": "tiles holding none of the net's copper"}

    def test_the_index_line_names_the_grid_each_tile_written_with_its_region_and_the_count_left_out(self):
        """SOL-BOARD-REVIEW-NET-VIEWS-DRAW-ONLY-TILES-HOLDING-THE-NET.C2: For each critical net the index, in text and in JSON, lists the net, the rows and columns of its grid, the tiles written by row and column with the board region each covers, and the number of tiles left out because none of the net's copper is in them; each written tile's caption says that tiles with none of the net's copper are not written and gives the count, and the command's report states the number of images written. A net that wrote every tile of its grid states none left out. Over the synthetic board the text and JSON hold the same facts, a net with copper in one tile of a many-tile grid states the rest as left out, and the counts agree with the files in the output folder. A net with no copper on any copper layer is listed with no tile written, every tile left out and that reason, in the index and in the command's report. Out of scope: the image files themselves, which the first criterion covers."""
        self.assertEqual(board_views.net_tile_line(self.GRID),
                         "NET TILES | GND | grid 2 rows x 3 columns | 1 of 6 tiles written: net-GND-r1c2.png (row 1, "
                         "column 2, board x 10 to 20 mm, y 0 to 15 mm) | 5 of 6 tiles left out: tiles holding none of "
                         "the net's copper")
        every = dict(self.GRID, rows=1, columns=1, tiles_left_out=0, reason=None)
        self.assertIn("| 1 of 1 tiles written: net-GND-r1c2.png", board_views.net_tile_line(every))
        self.assertTrue(board_views.net_tile_line(every).endswith("| none left out"))
        none = dict(self.GRID, tiles_written=[], tiles_left_out=6, reason="no copper on any copper layer")
        self.assertEqual(board_views.net_tile_line(none),
                         "NET TILES | GND | grid 2 rows x 3 columns | no tile written | 6 of 6 tiles left out: no copper "
                         "on any copper layer")

    def test_the_caption_field_states_that_tiles_without_the_nets_copper_are_not_written_and_the_count(self):
        """SOL-BOARD-REVIEW-NET-VIEWS-DRAW-ONLY-TILES-HOLDING-THE-NET.C2: For each critical net the index, in text and in JSON, lists the net, the rows and columns of its grid, the tiles written by row and column with the board region each covers, and the number of tiles left out because none of the net's copper is in them; each written tile's caption says that tiles with none of the net's copper are not written and gives the count, and the command's report states the number of images written. A net that wrote every tile of its grid states none left out. Over the synthetic board the text and JSON hold the same facts, a net with copper in one tile of a many-tile grid states the rest as left out, and the counts agree with the files in the output folder. A net with no copper on any copper layer is listed with no tile written, every tile left out and that reason, in the index and in the command's report. Out of scope: the image files themselves, which the first criterion covers."""
        self.assertEqual(board_views.left_out_field(3, 4),
                         "tiles with none of the net's copper are not written: 3 of 4 tiles left out")
        self.assertIn("0 of 4 tiles left out", board_views.left_out_field(0, 4))
