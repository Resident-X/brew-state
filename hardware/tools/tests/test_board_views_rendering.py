#!/usr/bin/env python3
"""The layout review views, rendered from a synthetic proof board against the real kicad-cli and resvg: the rendering part.

One of the files the original test file is divided into by topic; the tests are unchanged and only live elsewhere.
"""

from __future__ import annotations

import json
import os
import sys
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from board_fixtures import MINIMUM_MM  # noqa: E402
from board_fixtures import hex_rgb  # noqa: E402
from board_fixtures import pad  # noqa: E402
import board_fixtures  # noqa: E402
import board_views  # noqa: E402
from board_views_fixtures import BACKGROUND, NO_SUCH_FONT, SCALE, layout, model_reads, rendered, setUpModule, tearDownModule  # noqa: E402,F401


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
