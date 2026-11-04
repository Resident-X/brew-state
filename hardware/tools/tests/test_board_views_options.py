#!/usr/bin/env python3
"""The views command's two options that leave views out, and the selection of a group's views from a rendered folder.

A synthetic board is rendered against the real kicad-cli and resvg, once without the options and once with each, and the
tests compare what the three runs wrote. Selection reads the index of a folder already rendered and starts no program.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from board_fixtures import project, uuid  # noqa: E402
from board_views_fixtures import (KICAD_CLI, NET_TILE_CLASSES, NET_TILE_ITEMS, RESVG, Design, layout, setUpModule,  # noqa: E402,F401
                                  tearDownModule)
import board_check  # noqa: E402
import board_views  # noqa: E402
from review_kit import selection  # noqa: E402

#: A net that runs up the left side, along the bottom and up the right side: its copper reaches all four tiles of the 2 by 2
#: grid, and its only free track ends, the ones that are no joint, are in the two upper tiles.
THIN_ITEMS = [
    f'(segment (start 8 8) (end 8 34) (width 0.3) (layer "F.Cu") (net "THIN") (uuid {uuid()}))',
    f'(segment (start 8 34) (end 52 34) (width 0.3) (layer "F.Cu") (net "THIN") (uuid {uuid()}))',
    f'(segment (start 52 34) (end 52 8) (width 0.3) (layer "F.Cu") (net "THIN") (uuid {uuid()}))',
]

_RUNS = {}


def design():
    if "design" not in _RUNS:
        _RUNS["design"] = Design(layout(NET_TILE_ITEMS + THIN_ITEMS), project(assignments=dict(NET_TILE_CLASSES, THIN="Power")))
    return _RUNS["design"]


def rendered(name, *options):
    """The board's views written once with the options, in a folder of their own: (status, report lines, index, folder)."""
    if name not in _RUNS:
        found = design()
        out = os.path.join(found.root, name)
        stream, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(errors):
            status = board_views.main(["--kicad-cli", KICAD_CLI, "--resvg", RESVG, *found.args(out=out), *options], out=stream)
        index = None
        if status == 0:
            with open(os.path.join(out, "index.json"), encoding="utf-8") as handle:
                index = json.load(handle)
        _RUNS[name] = (status, stream.getvalue().splitlines(), index, out)
    return _RUNS[name]


def files(index):
    return {image["file"]: image for image in index["images"]}


def geometry(image):
    return (image["size_px"], image.get("scale_px_per_mm"), image.get("region_mm"), image.get("tile"))


class NonCopperTiles(unittest.TestCase):
    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C10: the views command offers an option that leaves out the whole-board tiles of layers that are not copper ... a test shows that the views written with each option are a subset of those written without it, that the options change no tile's name, size or scale, that the index states what was left out in text and in JSON
    def test_the_option_leaves_out_exactly_the_whole_board_tiles_of_layers_that_are_not_copper_and_changes_no_other_tile(self):
        status, _, full, _ = rendered("full")
        self.assertEqual(status, 0)
        status, lines, fewer, out = rendered("no-noncopper", "--no-noncopper-tiles")
        self.assertEqual(status, 0, lines)
        before, after = files(full), files(fewer)
        self.assertLess(set(after), set(before), "the views written with the option are a subset of those written without")
        left_out = set(before) - set(after)
        layers = {image["layers"][0]["name"] for name, image in before.items() if name in left_out}
        self.assertTrue(left_out and all(before[name]["view"] == "layer" for name in left_out))
        self.assertTrue(layers.isdisjoint({"F.Cu", "B.Cu"}), layers)
        self.assertEqual({image["layers"][0]["name"] for image in before.values() if image["view"] == "layer"} - layers,
                         {"F.Cu", "B.Cu"}, "the copper layers' tiles are all still written")
        for name, image in after.items():
            self.assertEqual(geometry(image), geometry(before[name]), f"{name} keeps its size, scale, region and place in its grid")
        for name in after:
            self.assertEqual(os.path.getsize(os.path.join(out, name)) > 0, True)
        self.assertEqual(sorted(fewer["layers_left_out"]), sorted(layers), "the index states, in JSON, the layers left out")
        with open(os.path.join(out, "index.txt"), encoding="utf-8") as handle:
            text = handle.read()
        for layer in layers:
            self.assertIn(f"LAYER LEFT OUT | {layer} | ", text)
            self.assertIn(f"LAYER LEFT OUT | {layer} | ", "\n".join(lines), "and the report")
        self.assertNotIn("net-", "".join(name for name in left_out), "no net view is left out by it")
        views_left = {image["view"] for name, image in before.items() if name in left_out}
        self.assertEqual(views_left, {"layer"})
        self.assertEqual({image["file"] for image in full["images"] if image["view"] != "layer"},
                         {image["file"] for image in fewer["images"] if image["view"] != "layer"})

    def test_without_the_option_the_index_names_no_layer_left_out(self):
        _, _, full, out = rendered("full")
        self.assertNotIn("layers_left_out", full)
        with open(os.path.join(out, "index.txt"), encoding="utf-8") as handle:
            self.assertNotIn("LAYER LEFT OUT", handle.read())


class ThinnedNets(unittest.TestCase):
    def grid(self, index, net):
        return next(entry for entry in index["net_tiles"] if entry["net"] == net)

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C10: an option stating the number of tiles above which a net's tiles are thinned to those that hold the net's pads, vias and ends, with no number given meaning no thinning ... a test shows that the views written with each option are a subset of those written without it, that the options change no tile's name, size or scale, that the index states what was left out in text and in JSON
    def test_a_net_over_the_number_is_thinned_to_the_tiles_holding_its_ends_and_every_tile_keeps_its_name_size_and_scale(self):
        _, _, full, _ = rendered("full")
        status, lines, thin, out = rendered("thin", "--thin-nets-over", "3")
        self.assertEqual(status, 0, lines)
        before, after = files(full), files(thin)
        self.assertLess(set(after), set(before))
        wide = [name for name, image in before.items() if image.get("net") == "THIN"]
        kept = [name for name in wide if name in after]
        self.assertEqual(len(wide), 4)
        self.assertEqual(sorted((before[name]["tile"]["row"], before[name]["tile"]["column"]) for name in kept), [(1, 1), (1, 2)],
                         "the two upper tiles hold the net's two free ends; the joints in the lower tiles are no end")
        for name, image in after.items():
            self.assertEqual(geometry(image), geometry(before[name]))
        left = set(before) - set(after)
        self.assertEqual(left, set(wide) - set(kept), "no view of any other net, or of any other view, is left out")
        entry = self.grid(thin, "THIN")
        self.assertEqual((entry["tiles_left_out"], entry["thinned"]), (2, True))
        self.assertIn("more than 3", entry["reason"])
        self.assertEqual(thin["thin_nets_over"], 3)
        with open(os.path.join(out, "index.txt"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("THIN NETS OVER | 3 | ", text)
        line = next(row for row in text.splitlines() if row.startswith("NET TILES | THIN |"))
        self.assertIn("2 of 4 tiles left out: net thinned: its copper reaches 4 tiles, more than 3", line)
        self.assertTrue(any(row.startswith("NET THINNED | THIN | ") for row in lines))
        caption = after[kept[0]]["caption"]
        self.assertIn("net thinned to tiles with its pads, vias, ends: 2 of 4 tiles left out", caption)
        self.assertEqual(self.grid(thin, "WIDE")["tiles_left_out"], 0, "a net whose ends are in every tile loses none")
        self.assertNotIn("thinned", self.grid(thin, "WIDE"))

    def test_no_number_or_a_number_the_net_does_not_exceed_thins_nothing(self):
        _, _, full, _ = rendered("full")
        status, _, same, _ = rendered("thin-four", "--thin-nets-over", "4")
        self.assertEqual(status, 0)
        self.assertEqual({name: geometry(image) for name, image in files(same).items()},
                         {name: geometry(image) for name, image in files(full).items()}, "four tiles is not more than four")
        self.assertNotIn("thin_nets_over", full, "with no number the index says nothing of thinning")

    def test_the_thinned_caption_is_no_longer_than_the_other_so_the_grid_is_the_one_every_tile_is_planned_with(self):
        for grid in (4, 9, 16, 100):
            for left in (0, 1, grid):
                self.assertLessEqual(len(board_views.left_out_field(left, grid, True)), len(board_views.left_out_field(left, grid)))

    def test_a_number_below_one_is_refused(self):
        stream = io.StringIO()
        status = board_views.main(["--board", "b", "--project", "p", "--class", "c", "--out", "o", "--thin-nets-over", "0"], out=stream)
        self.assertEqual(status, 1)
        self.assertIn("REFUSED | --thin-nets-over 0 is below 1", stream.getvalue())

    def test_the_anchors_are_pads_vias_and_free_track_ends_and_a_joint_is_none(self):
        from board_views import net_anchors
        layout_tree = board_views.locked_copper.read_layout(design().board)
        boxes = net_anchors(layout_tree, "THIN", design().board)
        self.assertEqual(sorted((x, y) for x, y, _, _ in boxes), [(8.0, 8.0), (52.0, 8.0)])
        lone = net_anchors(layout_tree, "LONE_PAD", design().board)
        self.assertEqual([(round(x, 3), round(y, 3)) for x, y, _, _ in lone], [(50.0, 32.0)])
        via = net_anchors(layout_tree, "LONE_VIA", design().board)
        self.assertEqual([(x, y) for x, y, _, _ in via], [(5.0, 35.0)])


class SelectionFromAnIndex(unittest.TestCase):
    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C10: the kit selects a per-group subset from an already-rendered folder's view index with no call to the renderer
    def test_a_selection_by_kind_net_class_layer_and_region_resolves_to_artefact_names_and_calls_no_renderer(self):
        _, _, index, out = rendered("full")
        with mock.patch.object(board_views, "views", side_effect=AssertionError("the renderer was called")), \
                mock.patch.object(board_views, "rasterise", side_effect=AssertionError("resvg was called")), \
                mock.patch.object(board_check, "run_kicad", side_effect=AssertionError("KiCad was called")), \
                mock.patch.object(subprocess, "run", side_effect=AssertionError("a program was started")):
            read = selection.read_index(os.path.dirname(out), os.path.join(os.path.basename(out), "index.json"))
            nets = selection.select(read, view="net", nets=["THIN"])
            by_class = selection.select(read, view="net", classes="Ground")
            layers = selection.select(read, view="layer", layers=["F.Cu", "B.Cu"])
            corner = selection.select(read, view="net", nets="WIDE", region=(0, 0, 10, 10))
            everything = selection.select(read, view=["layer", "net", "assembly", "class map", "crop", "3d"])
        names = {image["file"] for image in index["images"]}
        self.assertEqual(sorted(nets), sorted(f"views/{image['file']}" for image in index["images"] if image.get("net") == "THIN"))
        self.assertTrue(all(name.startswith("views/net-") for name in nets + by_class))
        self.assertTrue(by_class and all(name.startswith("views/net-") for name in by_class))
        self.assertEqual(len(layers), 8, "four tiles of each of the two copper layers")
        self.assertTrue(all(name.startswith(("views/layer-F.Cu", "views/layer-B.Cu")) for name in layers))
        self.assertEqual(len(corner), 1, "the one tile of the net that meets the corner region")
        self.assertEqual({name.split("/", 1)[1] for name in everything}, names)
        for name in nets + layers + corner:
            self.assertTrue(os.path.isfile(os.path.join(os.path.dirname(out), name.replace("views/", os.path.basename(out) + "/", 1))))

    def test_a_description_matching_no_image_is_refused_naming_it_unless_allowed(self):
        _, _, index, _ = rendered("full")
        with self.assertRaises(selection.EmptySelection) as refused:
            selection.select(index, view="net", nets="NO_SUCH_NET")
        self.assertIn("NO_SUCH_NET", str(refused.exception))
        self.assertEqual(selection.select(index, view="net", nets="NO_SUCH_NET", allow_empty=True), [])

    def test_a_selection_is_of_the_index_alone_and_the_module_imports_no_renderer(self):
        with open(selection.__file__, encoding="utf-8") as handle:
            source = handle.read()
        for forbidden in ("board_views", "subprocess", "resvg", "kicad"):
            self.assertNotIn(f"import {forbidden}", source)


if __name__ == "__main__":
    unittest.main()
