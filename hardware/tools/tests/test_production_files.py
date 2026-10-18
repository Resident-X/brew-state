#!/usr/bin/env python3
"""The ordering step's two commands, the placement conversion and the layer rendering, against KiCad and gerbonara themselves.

The commands are run as shipped on the production files KiCad exports from a
copy of hardware/proof/review-proof, with the real kicad-cli named by KICAD_CLI,
the real resvg named by RESVG (or found on the search path) and the Python that
holds gerbonara 1.6.3 named by GERBONARA_PYTHON (or python3 on the search path).
Nothing is skipped when a tool is absent: a missing tool fails the run with a
CANNOT RUN line naming it, because a command that cannot be exercised has not
been shown to work.
"""

from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import board_fixtures  # noqa: E402
import board_prove  # noqa: E402
import production_files  # noqa: E402
import production_seed  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
KICAD_CLI = os.environ.get("KICAD_CLI") or "kicad-cli"
RESVG = os.environ.get("RESVG") or "resvg"
GERBONARA_PYTHON = os.environ.get("GERBONARA_PYTHON") or "python3"
METHOD = os.path.join(REPO, "docs", "board-design-method.md")

#: The layers the export names and the images the render draws from them.
IMAGES = ["F.Cu", "F.Mask", "F.SilkS", "B.Cu", "B.Mask", "B.SilkS", "In1.Cu", "In2.Cu", "Edge.Cuts", "drill"]

_STATE = {}


def setUpModule():
    board_fixtures.require_tools(KICAD_CLI, RESVG)
    board_fixtures.require_gerbonara(GERBONARA_PYTHON)
    scratch = tempfile.mkdtemp(prefix="production-files-test-")
    _STATE["scratch"] = scratch
    seed = board_prove.prepare(os.path.join(scratch, "clean"), production_seed.DESIGN, production_seed.NAME)
    _STATE["placement"], _STATE["parts"] = production_seed.export_parts(seed, KICAD_CLI, os.path.join(scratch, "parts"))
    _STATE["positions"] = os.path.join(scratch, "parts", "positions.csv")
    production_seed.export_fabrication(seed, KICAD_CLI, os.path.join(scratch, "gerbers"))
    _STATE["gerbers"] = os.path.join(scratch, "gerbers")
    _STATE["seed"] = seed


def tearDownModule():
    shutil.rmtree(_STATE.get("scratch", ""), ignore_errors=True)


def run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        status = production_files.main(argv)
    return status, out.getvalue().splitlines()


def rendered(args, gerbers, out):
    """The render command as it is run for real, under the Python that holds gerbonara."""
    result = subprocess.run([GERBONARA_PYTHON, os.path.join(TOOLS, "production_files.py"), "render", "--gerbers", gerbers,
                             "--out", out, "--resvg", RESVG] + args, capture_output=True, text=True)
    return result.returncode, (result.stdout + result.stderr).splitlines()


def png_size(path):
    with open(path, "rb") as handle:
        return struct.unpack(">II", handle.read(24)[16:24])


def read_rows(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle))


def write_positions(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(production_files.POSITION_COLUMNS)
        writer.writerows(rows)


class ThePlacementConversion(unittest.TestCase):
    """SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C1: The method's ordering step compares every placed part's position, rotation and polarity with the assembler's preview before payment."""

    def setUp(self):
        self.work = tempfile.mkdtemp(prefix="production-files-placement-")
        self.out = os.path.join(self.work, "placement.csv")

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_the_export_is_converted_to_the_assemblers_columns_with_a_row_for_every_part(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C1: The method's ordering step compares every placed part's position, rotation and polarity with the assembler's preview before payment
        status, lines = run(["placement", "--positions", _STATE["positions"], "--out", self.out])
        self.assertEqual(status, 0, lines)
        self.assertEqual(lines[-1], f"RESULT | WRITTEN | {self.out}")
        exported = read_rows(_STATE["positions"])[1:]
        rows = read_rows(self.out)
        self.assertEqual(rows[0], ["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        self.assertEqual([row[0] for row in rows[1:]], [row[0] for row in exported])
        self.assertEqual(len(rows) - 1, 28, "the proof design places 28 parts")
        for row in rows[1:]:
            self.assertIn(row[3], ("Top", "Bottom"))
            self.assertTrue(0 <= float(row[4]) < 360, row)
        self.assertEqual({row[3] for row in rows[1:]}, {"Top", "Bottom"})
        self.assertIn("PARTS | 28 parts | 6 on the bottom side", lines)

    def test_the_converted_coordinates_are_in_the_frame_of_the_exported_gerber_files(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C1: The method's ordering step compares every placed part's position, rotation and polarity with the assembler's preview before payment
        # The step states that the export's Y is in the Gerber frame, so TP1, at editor (37, 30), is flashed at (37, -30) in
        # the bottom copper file and the converted file gives that point; a Y with its sign changed would put it at (37, 30).
        status, lines = run(["placement", "--positions", _STATE["positions"], "--out", self.out])
        self.assertEqual(status, 0, lines)
        converted = {row[0]: row for row in read_rows(self.out)[1:]}
        script = ("import warnings, json, sys; warnings.simplefilter('ignore'); "
                  "from gerbonara import LayerStack; from gerbonara.graphic_objects import Flash; "
                  "layer = LayerStack.open(sys.argv[1])['bottom', 'copper']; "
                  "print(json.dumps([[round(o.x, 3), round(o.y, 3)] for o in layer.objects if isinstance(o, Flash)]))")
        result = subprocess.run([GERBONARA_PYTHON, "-c", script, _STATE["gerbers"]], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        flashes = {tuple(point) for point in json.loads(result.stdout)}
        for designator in ("TP1", "TP3", "TP6"):
            x, y = float(converted[designator][1]), float(converted[designator][2])
            self.assertIn((round(x, 3), round(y, 3)), flashes, f"{designator} is not where the Gerber file flashes its pad")
            self.assertNotIn((round(x, 3), round(-y, 3)), flashes, f"{designator}'s mirror image is flashed too")
        self.assertEqual((converted["TP1"][1], converted["TP1"][2]), ("37", "-30"))

    def test_the_rotation_is_written_counter_clockwise_in_zero_to_three_hundred_sixty_degrees(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C1: The method's ordering step compares every placed part's position, rotation and polarity with the assembler's preview before payment
        positions = os.path.join(self.work, "positions.csv")
        write_positions(positions, [["A1", "x", "p", "1.5", "-2.25", "-90.000000", "top"],
                                    ["A2", "x", "p", "0", "-0.000000", "0.000000", "bottom"],
                                    ["A3", "x", "p", "10", "-5", "360", "top"],
                                    ["A4", "x", "p", "10", "-5", "-180", "top"],
                                    ["A5", "x, with a comma", "p", "-16.774999", "4", "45.5", "top"]])
        self.assertEqual(run(["placement", "--positions", positions, "--out", self.out])[0], 0)
        self.assertEqual(read_rows(self.out), [
            ["Designator", "Mid X", "Mid Y", "Layer", "Rotation"],
            ["A1", "1.5", "-2.25", "Top", "270"], ["A2", "0", "0", "Bottom", "0"], ["A3", "10", "-5", "Top", "0"],
            ["A4", "10", "-5", "Top", "180"], ["A5", "-16.775", "4", "Top", "45.5"]])

    def refused(self, positions, because):
        status, lines = run(["placement", "--positions", positions, "--out", self.out])
        self.assertEqual(status, 1, lines)
        self.assertTrue(any(line.startswith("REFUSED | ") and because in line for line in lines), lines)
        self.assertEqual(lines[-1], "RESULT | REFUSED | nothing was written")
        self.assertFalse(os.path.exists(self.out))

    def test_an_export_with_other_columns_is_refused(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C1: The method's ordering step compares every placed part's position, rotation and polarity with the assembler's preview before payment
        positions = os.path.join(self.work, "positions.csv")
        with open(positions, "w", encoding="utf-8") as handle:
            handle.write("Designator,Mid X,Mid Y,Layer,Rotation\nR1,1,2,Top,0\n")
        self.refused(positions, "has the columns Designator,Mid X,Mid Y,Layer,Rotation, not KiCad's")

    def test_an_empty_export_and_one_listing_no_part_are_refused(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C1: The method's ordering step compares every placed part's position, rotation and polarity with the assembler's preview before payment
        positions = os.path.join(self.work, "positions.csv")
        open(positions, "w", encoding="utf-8").close()
        self.refused(positions, "is empty")
        write_positions(positions, [])
        self.refused(positions, "lists no part")

    def test_a_part_that_cannot_be_read_is_refused(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C1: The method's ordering step compares every placed part's position, rotation and polarity with the assembler's preview before payment
        positions = os.path.join(self.work, "positions.csv")
        for row, because in ((["R1", "x", "p", "one", "2", "0", "top"], "R1's PosX is 'one', not a number"),
                             (["R1", "x", "p", "1", "nan", "0", "top"], "not a finite number"),
                             (["R1", "x", "p", "1", "2", "0", "middle"], "R1 is on the side 'middle'"),
                             (["", "x", "p", "1", "2", "0", "top"], "names no designator"),
                             (["R1", "x", "p", "1", "2", "0"], "has 6 columns, not 7")):
            with self.subTest(because=because):
                write_positions(positions, [row])
                self.refused(positions, because)
        write_positions(positions, [["R1", "x", "p", "1", "2", "0", "top"], ["r1", "x", "p", "3", "4", "0", "top"]])
        self.refused(positions, "lists r1 twice")

    def test_a_missing_export_and_an_output_that_exists_are_refused(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C1: The method's ordering step compares every placed part's position, rotation and polarity with the assembler's preview before payment
        self.refused(os.path.join(self.work, "no-such.csv"), "cannot be read")
        with open(self.out, "w", encoding="utf-8") as handle:
            handle.write("left from an earlier run")
        status, lines = run(["placement", "--positions", _STATE["positions"], "--out", self.out])
        self.assertEqual((status, lines[-1]), (1, "RESULT | REFUSED | nothing was written"), lines)
        self.assertEqual(open(self.out, encoding="utf-8").read(), "left from an earlier run")
        os.remove(self.out)
        os.makedirs(self.out)
        status, lines = run(["placement", "--positions", _STATE["positions"], "--out", self.out])
        self.assertEqual(status, 1, lines)
        self.assertTrue(any("is a folder" in line for line in lines), lines)

    def test_the_method_names_the_conversion_command_as_it_is_run(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C1: The method's ordering step compares every placed part's position, rotation and polarity with the assembler's preview before payment
        self.assertIn("python3 hardware/tools/production_files.py placement --positions <work>/positions.csv --out <work>/placement.csv",
                      ordering_section())
        self.assertTrue(os.path.isfile(os.path.join(TOOLS, "production_files.py")))


def ordering_section():
    with open(METHOD, encoding="utf-8") as handle:
        found = re.search(r"^## Ordering[ \t]*\n(.*?)(?=^## |\Z)", handle.read(), re.M | re.S)
    return found.group(1) if found else ""


class TheLayerImages(unittest.TestCase):
    """SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C2: The method's ordering step has every rendered fabrication layer looked at before ordering."""

    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.mkdtemp(prefix="production-files-render-")
        cls.out = os.path.join(cls.work, "layers")
        cls.status, cls.lines = rendered([], _STATE["gerbers"], cls.out)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.work, ignore_errors=True)

    def test_every_exported_layer_and_the_drill_file_is_drawn_into_one_frame(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C2: The method's ordering step has every rendered fabrication layer looked at before ordering
        self.assertEqual(self.status, 0, "\n".join(self.lines))
        self.assertTrue(self.lines[-1].startswith("RESULT | WRITTEN | 10 images and their index | "), self.lines)
        self.assertEqual(sorted(os.listdir(self.out)),
                         sorted(["index.txt", "index.json"] + [f"layer-{name}.png" for name in IMAGES]))
        sizes = {png_size(os.path.join(self.out, f"layer-{name}.png")) for name in IMAGES}
        self.assertEqual(len(sizes), 1, f"the images do not share one frame: {sizes}")
        width, height = sizes.pop()
        self.assertLessEqual(max(width, height), 1568, "an image is larger than a reading model takes without downsampling")

    def test_the_index_lists_every_image_with_its_file_and_the_frame_as_text_and_json(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C2: The method's ordering step has every rendered fabrication layer looked at before ordering
        with open(os.path.join(self.out, "index.json"), encoding="utf-8") as handle:
            index = json.load(handle)
        with open(os.path.join(self.out, "index.txt"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertEqual([image["layer"] for image in index["images"]], ["F.Cu", "F.Mask", "F.SilkS", "B.Cu", "B.Mask", "B.SilkS",
                                                                      "In1.Cu", "In2.Cu", "Edge.Cuts", "drill"])
        self.assertEqual(index["gerbonara"], "1.6.3")
        frame = index["frame_mm"]
        self.assertLess(frame["x_min"], 0)
        self.assertGreater(frame["x_max"], 92)
        self.assertLess(frame["y_max"], 2, "the Gerber frame runs Y up, so the board sits at negative Y")
        self.assertLess(frame["y_min"], -60)
        for image in index["images"]:
            self.assertIn(f"IMAGE | {image['file']} | layer {image['layer']} | read from {image['source']}", text)
            self.assertTrue(image["source"], image)
        self.assertIn("a point of the design's own editor coordinates (x, y) is at (x, -y)", text)
        self.assertNotIn(_STATE["gerbers"], text, "the index names the folder it was read from")

    def test_a_drill_files_header_warning_is_listed_and_does_not_fail_the_command(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C2: The method's ordering step has every rendered fabrication layer looked at before ordering
        self.assertEqual(self.status, 0)
        notes = [line for line in self.lines if line.startswith("NOTE | gerbonara: ")]
        self.assertTrue(any("G90" in line and "review-proof.drl" in line for line in notes), self.lines)

    def draw(self, edit):
        """The images drawn from the layers exported from a copy of the board that `edit` has changed."""
        with tempfile.TemporaryDirectory(prefix="production-files-edited-") as scratch:
            seed = board_prove.prepare(scratch, production_seed.DESIGN, production_seed.NAME)
            seed.layout(edit)
            production_seed.export_fabrication(seed, KICAD_CLI, os.path.join(scratch, "files"))
            out = os.path.join(scratch, "images")
            status, lines = rendered([], os.path.join(scratch, "files"), out)
            self.assertEqual(status, 0, lines)
            return {name: open(os.path.join(out, name), "rb").read() for name in os.listdir(out) if name.endswith(".png")}

    def test_a_mirrored_legend_shows_in_its_own_image_and_in_no_other(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C2: The method's ordering step has every rendered fabrication layer looked at before ordering
        clean = {name: open(os.path.join(self.out, name), "rb").read() for name in os.listdir(self.out) if name.endswith(".png")}
        mirrored = self.draw(production_seed.legend_mirrored)
        self.assertNotEqual(mirrored["layer-F.SilkS.png"], clean["layer-F.SilkS.png"])
        self.assertEqual({name for name in clean if mirrored[name] != clean[name]}, {"layer-F.SilkS.png"},
                         "an image other than the mirrored legend changed, so the frame is not common")

    def test_a_shifted_hole_and_missing_mask_openings_show_in_the_images_of_their_layers(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C2: The method's ordering step has every rendered fabrication layer looked at before ordering
        clean = {name: open(os.path.join(self.out, name), "rb").read() for name in os.listdir(self.out) if name.endswith(".png")}
        shifted = self.draw(production_seed.hole_moved("H1", 4, 4))
        self.assertNotEqual(shifted["layer-drill.png"], clean["layer-drill.png"])
        self.assertEqual(shifted["layer-F.Cu.png"], clean["layer-F.Cu.png"])
        self.assertEqual(shifted["layer-B.SilkS.png"], clean["layer-B.SilkS.png"])
        uncovered = self.draw(production_seed.mask_openings_missing("J1"))
        self.assertNotEqual(uncovered["layer-F.Mask.png"], clean["layer-F.Mask.png"])
        self.assertEqual(uncovered["layer-drill.png"], clean["layer-drill.png"])

    def test_the_method_names_the_render_command_as_it_is_run(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C2: The method's ordering step has every rendered fabrication layer looked at before ordering
        self.assertIn('"$GERBONARA_PYTHON" hardware/tools/production_files.py render --gerbers <work>/gerbers --out <work>/layers '
                      '--resvg "$RESVG"', ordering_section())


class TheRenderRefusals(unittest.TestCase):
    """SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C2: The method's ordering step has every rendered fabrication layer looked at before ordering."""

    def setUp(self):
        self.work = tempfile.mkdtemp(prefix="production-files-refusals-")
        self.out = os.path.join(self.work, "layers")

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def refused(self, gerbers, because, out=None):
        out = out or self.out
        status, lines = rendered([], gerbers, out)
        self.assertEqual(status, 1, lines)
        self.assertTrue(any(line.startswith("REFUSED | ") and because in line for line in lines), lines)
        self.assertEqual(lines[-1], "RESULT | REFUSED | nothing was written")

    def test_a_folder_that_is_not_one_is_refused(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C2: The method's ordering step has every rendered fabrication layer looked at before ordering
        self.refused(os.path.join(self.work, "no-such-folder"), "is not a folder")
        self.assertFalse(os.path.exists(self.out))

    def test_an_empty_folder_and_one_of_files_that_are_not_gerber_files_are_refused(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C2: The method's ordering step has every rendered fabrication layer looked at before ordering
        empty = os.path.join(self.work, "empty")
        os.makedirs(empty)
        self.refused(empty, "holds no Gerber or drill file")
        self.assertFalse(os.path.exists(self.out))
        junk = os.path.join(self.work, "junk")
        os.makedirs(junk)
        with open(os.path.join(junk, "notes.txt"), "w", encoding="utf-8") as handle:
            handle.write("not a layer\n")
        status, lines = rendered([], junk, self.out)
        self.assertEqual(status, 1, lines)
        self.assertEqual(lines[-1], "RESULT | REFUSED | nothing was written")
        self.assertFalse(os.path.exists(self.out))

    def test_an_output_that_holds_files_is_a_file_or_lies_inside_the_gerber_folder_is_refused(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C2: The method's ordering step has every rendered fabrication layer looked at before ordering
        os.makedirs(self.out)
        with open(os.path.join(self.out, "left-over.txt"), "w", encoding="utf-8") as handle:
            handle.write("from an earlier run")
        self.refused(_STATE["gerbers"], "already holds files")
        self.assertEqual(os.listdir(self.out), ["left-over.txt"])
        shutil.rmtree(self.out)
        with open(self.out, "w", encoding="utf-8") as handle:
            handle.write("not a folder")
        self.refused(_STATE["gerbers"], "is a file")
        self.refused(_STATE["gerbers"], "is inside the Gerber folder", out=os.path.join(_STATE["gerbers"], "images"))
        self.assertFalse(os.path.exists(os.path.join(_STATE["gerbers"], "images")))

    def test_a_gerbonara_of_another_version_or_none_stops_the_command_naming_it(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C2: The method's ordering step has every rendered fabrication layer looked at before ordering
        for found, words in (("1.6.2", "gerbonara 1.6.2 is installed"), (None, "gerbonara could not be imported")):
            with self.subTest(found=found), mock.patch.object(production_files, "gerbonara_version", return_value=found):
                err = io.StringIO()
                with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                    status = production_files.main(["render", "--gerbers", _STATE["gerbers"], "--out", self.out, "--resvg", RESVG])
                self.assertEqual(status, 2)
                self.assertTrue(err.getvalue().startswith("CANNOT RUN | "), err.getvalue())
                self.assertIn(words, err.getvalue())
                self.assertIn("gerbonara==1.6.3", err.getvalue())
                self.assertFalse(os.path.exists(self.out))


if __name__ == "__main__":
    unittest.main()
