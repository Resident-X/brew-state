#!/usr/bin/env python3
"""The layout review views, rendered from a synthetic proof board against the real kicad-cli and resvg: the commands part.

One of the files the original test file is divided into by topic; the tests are unchanged and only live elsewhere.
"""

from __future__ import annotations

import ast
import contextlib
import io
import json
import os
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import time
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from board_fixtures import LAYER_TABLE  # noqa: E402
from board_fixtures import MINIMUM_MM  # noqa: E402
from board_fixtures import OUTLINE  # noqa: E402
from board_fixtures import project  # noqa: E402
import board_check  # noqa: E402
import board_views  # noqa: E402
from board_views_fixtures import Design, KICAD_CLI, PROOF_PROJECT, REPO, RESVG, SCALE, layout, setUpModule, tearDownModule  # noqa: E402,F401


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


def glb_bytes(names=("U1", "C2")) -> bytes:
    """A binary glTF file holding one node per name, as KiCad writes its three-dimensional export."""
    body = json.dumps({"asset": {"version": "2.0"}, "nodes": [{"name": name} for name in names]}).encode()
    body += b" " * (-len(body) % 4)
    return b"glTF" + struct.pack("<II", 2, 20 + len(body)) + struct.pack("<I4s", len(body), b"JSON") + body


#: What a stand-in for KiCad's command-line tool says when it ends the export with a non-zero status.
STAND_IN_CAUSE = "Could not add 3D model for C2. No such file models/missing.step"


#: The shell lines that find the file a command is asked to write, after -o, as $out.
FIND_OUTPUT = 'out=""; prev=""\nfor arg in "$@"; do [ "$prev" = "-o" ] && out="$arg"; prev="$arg"; done\n'


class ExportStatus(unittest.TestCase):
    """SOL-BOARD-GATES-PASS-ON-HOSTED-RUNNER.C2: The board tooling's tests that the nightly runs, namely the view renderer's tests, the seeded review folder's tests and the check task's whole-repository test, pass on a hosted Ubuntu runner with the KiCad and fonts that workflow installs. The runner's KiCad is a different build from the author's, and where its command-line tool reports a non-zero status while still writing the artefact asked for, the tooling decides from what it actually wrote and reports the cause, rather than failing every render on the status alone, and a non-zero status with no artefact or an unreadable one is still reported as unreadable with its cause."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="board-views-status-")
        self.addCleanup(self.folder.cleanup)
        self.glb = os.path.join(self.folder.name, "models.glb")
        self.count = 0

    def export(self, writes: str, status: int, glb=True, tolerated=None) -> str:
        """The wrapper's account of a stand-in tool that runs `writes`, says STAND_IN_CAUSE and exits with `status`."""
        self.count += 1
        script = FIND_OUTPUT + f"{writes}\necho '{STAND_IN_CAUSE}' >&2\nexit {status}"
        command = [tool(self.folder.name, f"kicad-cli-{self.count}", script), "pcb", "export", "glb", "-o", self.glb,
                   "board.kicad_pcb"]
        return board_views.kicad(command, self.folder.name, "load the models of the board",
                                 glb=self.glb if glb else None, tolerated=tolerated)

    def writing(self, data: bytes) -> str:
        """The shell line that writes `data` to the file the tool was asked for."""
        path = os.path.join(self.folder.name, f"artefact-{self.count}.bin")
        with open(path, "wb") as handle:
            handle.write(data)
        return f"cp '{path}' \"$out\""

    def test_a_non_zero_status_with_a_readable_export_is_used_and_the_cause_kept(self):
        # SOL-BOARD-GATES-PASS-ON-HOSTED-RUNNER.C2: where its command-line tool reports a non-zero status while still writing the artefact asked for, the tooling decides from what it actually wrote and reports the cause, rather than failing every render on the status alone
        tolerated = []
        said = self.export(self.writing(glb_bytes()), 3, tolerated=tolerated)
        self.assertIn(STAND_IN_CAUSE, said)
        self.assertEqual(board_views.glb_names(self.glb), {"U1", "C2"})
        self.assertEqual(tolerated, [{"exit_status": 3, "said": STAND_IN_CAUSE}])

    def test_a_non_zero_status_with_no_export_is_unreadable_naming_the_status_and_the_cause(self):
        # SOL-BOARD-GATES-PASS-ON-HOSTED-RUNNER.C2: a non-zero status with no artefact or an unreadable one is still reported as unreadable with its cause
        tolerated = []
        with self.assertRaises(board_views.Unreadable) as raised:
            self.export(":", 3, tolerated=tolerated)
        self.assertIn(f"KiCad could not load the models of the board (exit 3: {STAND_IN_CAUSE}) and wrote no export",
                      str(raised.exception))
        self.assertEqual(tolerated, [])

    def test_a_non_zero_status_with_an_empty_export_is_unreadable_naming_the_status_and_the_cause(self):
        # SOL-BOARD-GATES-PASS-ON-HOSTED-RUNNER.C2: a non-zero status with no artefact or an unreadable one is still reported as unreadable with its cause
        with self.assertRaises(board_views.Unreadable) as raised:
            self.export(': > "$out"', 1)
        self.assertIn(f"(exit 1: {STAND_IN_CAUSE}) and wrote an empty export", str(raised.exception))

    def test_a_non_zero_status_with_a_corrupt_export_is_unreadable_naming_the_status_the_cause_and_the_fault(self):
        # SOL-BOARD-GATES-PASS-ON-HOSTED-RUNNER.C2: a non-zero status with no artefact or an unreadable one is still reported as unreadable with its cause
        not_json = b"glTF" + struct.pack("<II", 2, 28) + struct.pack("<I4s", 4, b"JSON") + b"{{{{"
        for what, data in (("text", b"this is not a model"), ("a cut-off file", glb_bytes()[:30]),
                           ("a JSON chunk that is not JSON", not_json)):
            with self.subTest(what=what), self.assertRaises(board_views.Unreadable) as raised:
                self.export(self.writing(data), 2)
            message = str(raised.exception)
            self.assertIn(f"(exit 2: {STAND_IN_CAUSE}) and wrote an export that cannot be read: ", message)
            self.assertIn("KiCad's three-dimensional export", message)

    def test_a_zero_status_is_not_reported_as_tolerated(self):
        # SOL-BOARD-GATES-PASS-ON-HOSTED-RUNNER.C2: where its command-line tool reports a non-zero status while still writing the artefact asked for, the tooling decides from what it actually wrote and reports the cause; an export that ended with status zero has no status to report
        tolerated = []
        said = self.export(self.writing(glb_bytes()), 0, tolerated=tolerated)
        self.assertIn(STAND_IN_CAUSE, said)
        self.assertEqual(tolerated, [])

    def test_a_leftover_export_from_an_earlier_run_does_not_stand_for_this_one(self):
        # SOL-BOARD-GATES-PASS-ON-HOSTED-RUNNER.C2: a non-zero status with no artefact or an unreadable one is still reported as unreadable with its cause
        with open(self.glb, "wb") as handle:
            handle.write(glb_bytes())
        with self.assertRaises(board_views.Unreadable) as raised:
            self.export(":", 1)
        self.assertIn("and wrote no export", str(raised.exception))

    def test_every_other_command_stays_strict_on_status_whatever_it_wrote(self):
        # SOL-BOARD-GATES-PASS-ON-HOSTED-RUNNER.C2: only the three-dimensional export is decided from what it wrote; a non-zero status from any other command is still reported as unreadable with its cause
        tolerated = []
        with self.assertRaises(board_views.Unreadable) as raised:
            self.export(self.writing(glb_bytes()), 3, glb=False, tolerated=tolerated)
        self.assertEqual(str(raised.exception), f"KiCad could not load the models of the board (exit 3: {STAND_IN_CAUSE})")
        self.assertEqual(tolerated, [])

    def test_a_timeout_is_not_tolerated_even_when_an_export_was_written(self):
        # SOL-BOARD-GATES-PASS-ON-HOSTED-RUNNER.C2: a non-zero status with no artefact or an unreadable one is still reported as unreadable with its cause; a command that did not finish has no status to decide from
        was, board_check.KICAD_TIMEOUT_S = board_check.KICAD_TIMEOUT_S, 1
        try:
            with self.assertRaises(board_views.Unreadable) as raised:
                self.export(self.writing(glb_bytes()) + "\nsleep 5", 0)
        finally:
            board_check.KICAD_TIMEOUT_S = was
        self.assertEqual(str(raised.exception), "KiCad did not load the models of the board within 1 s")




class OneLimitOnAKiCadRun(unittest.TestCase):
    """SOL-PRE-ORDER-CHECK-KICAD-RUN-LIMIT-FITS-A-POURED-BOARD.C1: The constant KICAD_TIMEOUT_S in hardware/tools/board_check.py equals 7200, and a test reads it and shows that hardware/tools/board_views.py applies that same constant to its KiCad runs and defines no limit of its own."""

    def sources(self):
        for name in ("board_views.py", "locked_copper.py"):
            with open(os.path.join(TOOLS, name), encoding="utf-8") as handle:
                yield name, ast.parse(handle.read())

    def sleeper(self, name: str):
        folder = tempfile.TemporaryDirectory(prefix="board-views-limit-")
        self.addCleanup(folder.cleanup)
        return tool(folder.name, name, "exec sleep 30"), folder.name

    def shorten(self, seconds: int) -> None:
        was, board_check.KICAD_TIMEOUT_S = board_check.KICAD_TIMEOUT_S, seconds
        self.addCleanup(setattr, board_check, "KICAD_TIMEOUT_S", was)

    def test_the_limit_is_7200_seconds(self):
        # SOL-PRE-ORDER-CHECK-KICAD-RUN-LIMIT-FITS-A-POURED-BOARD.C1: The constant KICAD_TIMEOUT_S in hardware/tools/board_check.py equals 7200
        self.assertEqual(board_check.KICAD_TIMEOUT_S, 7200)

    def test_the_views_tool_defines_no_limit_of_its_own_and_passes_the_constant_to_every_run(self):
        # SOL-PRE-ORDER-CHECK-KICAD-RUN-LIMIT-FITS-A-POURED-BOARD.C1: board_views.py applies that same constant to its KiCad runs and defines no limit of its own
        probes = []
        passed = 0
        for name, tree in self.sources():
            for node in ast.walk(tree):
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        label = target.id if isinstance(target, ast.Name) else getattr(target, "attr", "")
                        self.assertNotIn("TIMEOUT", label.upper(), f"{name} defines a limit of its own, {label}")
                if not isinstance(node, ast.Call):
                    continue
                for keyword in node.keywords:
                    if keyword.arg != "timeout":
                        continue
                    if isinstance(keyword.value, ast.Constant):
                        probes.append((name, keyword.value.value))
                        continue
                    self.assertEqual(ast.unparse(keyword.value), "board_check.KICAD_TIMEOUT_S", f"{name}:{node.lineno}")
                    passed += 1
        # The one figure that is not the limit is the short probe that asks resvg its version.
        self.assertEqual(probes, [("board_views.py", 120)])
        self.assertEqual(passed, 2, "the KiCad command and the rasteriser each take the limit from the constant")

    def test_the_views_tool_reads_the_constant_when_it_runs_not_a_copy_taken_at_import(self):
        # SOL-PRE-ORDER-CHECK-KICAD-RUN-LIMIT-FITS-A-POURED-BOARD.C1: board_views.py applies that same constant to its KiCad runs
        for seconds in (1, 2):
            with self.subTest(seconds=seconds):
                self.shorten(seconds)
                program, folder = self.sleeper(f"kicad-cli-{seconds}")
                with self.assertRaises(board_views.Unreadable) as raised:
                    board_views.kicad([program, "pcb", "drc"], folder, "check the board")
                self.assertEqual(str(raised.exception), f"KiCad did not check the board within {seconds} s")
                resvg, folder = self.sleeper(f"resvg-{seconds}")
                with self.assertRaises(board_views.CannotRun) as raised:
                    board_views.rasterise(resvg, os.path.join(folder, "a.svg"), os.path.join(folder, "a.png"))
                self.assertIn(f"timed out after {seconds}", str(raised.exception))


class AKiCadRunPastTheLimitFailsByName(unittest.TestCase):
    """SOL-PRE-ORDER-CHECK-KICAD-RUN-LIMIT-FITS-A-POURED-BOARD.C2: With a KiCad run replaced by one that outlives a shortened limit, the check fails the design with the message "KiCad did not finish within <limit> s" naming the limit in force, and the views tool reports the same message, and neither waits unbounded."""

    def test_the_views_tool_names_the_limit_in_force_and_does_not_wait_unbounded(self):
        # SOL-PRE-ORDER-CHECK-KICAD-RUN-LIMIT-FITS-A-POURED-BOARD.C2: the views tool reports the message naming the limit in force, and does not wait unbounded
        for seconds in (1, 3):
            with self.subTest(seconds=seconds):
                was, board_check.KICAD_TIMEOUT_S = board_check.KICAD_TIMEOUT_S, seconds
                try:
                    with tempfile.TemporaryDirectory(prefix="board-views-limit-") as folder:
                        program = tool(folder, "kicad-cli", "exec sleep 30")
                        started = time.monotonic()
                        with self.assertRaises(board_views.Unreadable) as raised:
                            board_views.kicad([program, "pcb", "export", "glb"], folder, "load the models of the board")
                        elapsed = time.monotonic() - started
                finally:
                    board_check.KICAD_TIMEOUT_S = was
                self.assertEqual(str(raised.exception), f"KiCad did not load the models of the board within {seconds} s")
                self.assertLess(elapsed, 20)


class ExportStatusThroughTheCommand(unittest.TestCase):
    """SOL-BOARD-GATES-PASS-ON-HOSTED-RUNNER.C2: The board tooling's tests that the nightly runs, namely the view renderer's tests, the seeded review folder's tests and the check task's whole-repository test, pass on a hosted Ubuntu runner with the KiCad and fonts that workflow installs. The runner's KiCad is a different build from the author's, and where its command-line tool reports a non-zero status while still writing the artefact asked for, the tooling decides from what it actually wrote and reports the cause, rather than failing every render on the status alone, and a non-zero status with no artefact or an unreadable one is still reported as unreadable with its cause. Tests drive that decision with a stand-in for the command-line tool that writes the artefact with a non-zero status and one that writes nothing, in text and in JSON output."""

    def command(self, how: str) -> str:
        """A stand-in for KiCad's command-line tool that passes every command to the real one except the
        three-dimensional export, which it ends as `how` says: "real" writes the real export, "none" writes
        nothing, "empty" an empty file, "corrupt" text, each saying STAND_IN_CAUSE and exiting 1; "zero" writes the
        real export and exits 0 saying nothing, whatever status the real tool gave it."""
        real = shutil.which(KICAD_CLI) or KICAD_CLI
        writes = {"real": f"'{real}' \"$@\" >/dev/null 2>&1", "none": ":", "empty": ': > "$out"',
                  "corrupt": 'echo "not a model" > "$out"', "zero": f"'{real}' \"$@\" >/dev/null 2>&1"}[how]
        ending = "exit 0" if how == "zero" else f"echo '{STAND_IN_CAUSE}' >&2; exit 1"
        folder = tempfile.mkdtemp(prefix="board-views-stand-in-")
        self.addCleanup(shutil.rmtree, folder, True)
        script = (FIND_OUTPUT + 'case " $* " in\n'
                  f" *' pcb export glb '*) {writes}; {ending} ;;\n"
                  f" *) exec '{real}' \"$@\" ;;\nesac")
        return tool(folder, "kicad-cli", script)

    def run_views(self, how: str):
        design = Design()
        status, lines, errors = design.run(kicad_cli=self.command(how))
        return design, status, lines, errors

    def test_a_non_zero_export_that_wrote_a_readable_file_still_renders_and_states_the_cause_in_text_and_json(self):
        # SOL-BOARD-GATES-PASS-ON-HOSTED-RUNNER.C2: Tests drive that decision with a stand-in for the command-line tool that writes the artefact with a non-zero status ... in text and in JSON output
        design, status, lines, errors = self.run_views("real")
        self.assertEqual(status, 0, lines + [errors])
        line = ("3D EXPORT | exit 1 | KiCad ended the export of the models with a non-zero status but wrote a readable "
                f"file, which the three-dimensional views use; KiCad said: {STAND_IN_CAUSE}")
        self.assertIn(line, lines)
        with open(os.path.join(design.out, "index.txt"), encoding="utf-8") as handle:
            self.assertIn(line, handle.read().splitlines())
        with open(os.path.join(design.out, "index.json"), encoding="utf-8") as handle:
            index = json.load(handle)
        self.assertEqual(index["three_dimensional_export"], {"exit_status": 1, "said": STAND_IN_CAUSE})
        # The parts the export drew are still judged from it, so the status did not cost the views their content.
        unseen = {part["reference"]: part["reason"] for part in index["not_in_3d"]}
        self.assertEqual(unseen["C2"], "model not found")
        self.assertEqual(sum(image["file"].startswith("3d-") for image in index["images"]), 3)

    def test_a_non_zero_export_that_wrote_nothing_or_nothing_readable_is_unreadable_with_its_cause_and_writes_no_views(self):
        # SOL-BOARD-GATES-PASS-ON-HOSTED-RUNNER.C2: a non-zero status with no artefact or an unreadable one is still reported as unreadable with its cause. Tests drive that decision with ... one that writes nothing, in text and in JSON output
        for how, fault in (("none", "wrote no export"), ("empty", "wrote an empty export"),
                           ("corrupt", "wrote an export that cannot be read")):
            with self.subTest(how=how):
                design, status, lines, errors = self.run_views(how)
                self.assertEqual(status, 1, lines + [errors])
                self.assertEqual(len(lines), 2, lines)
                self.assertTrue(lines[0].startswith("UNREADABLE | KiCad could not load the three-dimensional models of "), lines)
                self.assertIn(f"(exit 1: {STAND_IN_CAUSE}) and {fault}", lines[0])
                self.assertEqual(lines[1], "RESULT | FAIL | the input cannot be read, so no views were written")
                self.assertFalse(os.path.exists(os.path.join(design.out, "index.json")))
                self.assertFalse(os.path.exists(os.path.join(design.out, "index.txt")))

    def test_a_zero_status_export_adds_no_export_line_or_field_to_the_report_or_the_index(self):
        # SOL-BOARD-GATES-PASS-ON-HOSTED-RUNNER.C2: where its command-line tool reports a non-zero status while still writing the artefact asked for, the tooling decides from what it actually wrote and reports the cause; an export that ended with status zero has no status to report
        design, status, lines, errors = self.run_views("zero")
        self.assertEqual(status, 0, lines + [errors])
        self.assertFalse([line for line in lines if "3D EXPORT" in line], lines)
        with open(os.path.join(design.out, "index.txt"), encoding="utf-8") as handle:
            self.assertNotIn("3D EXPORT", handle.read())
        with open(os.path.join(design.out, "index.json"), encoding="utf-8") as handle:
            index = json.load(handle)
        self.assertNotIn("three_dimensional_export", index)
        self.assertEqual({part["reference"]: part["reason"] for part in index["not_in_3d"]}["C2"], "model not found")


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
