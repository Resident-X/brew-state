#!/usr/bin/env python3
"""The 3D picture commands' board reading, model injection and vendor-model alignment, on synthetic text."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
import unittest
import urllib.error
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_models_3d as bm  # noqa: E402
import fetch_3d_models as fm  # noqa: E402
import render_board_3d as rb  # noqa: E402
import render_fallback_models as ff  # noqa: E402

BOARD = '''(kicad_pcb
\t(version 20240108)
\t(footprint "lib:Part_A"
\t\t(layer "F.Cu")
\t\t(at 10 20 90)
\t\t(property "Reference" "U1" (at 0 0 0) (layer "F.SilkS"))
\t\t(property "LCSC" "C12345" (at 0 0 0) (layer "F.Fab"))
\t\t(pad "1" smd rect (at -1 0) (size 1 1) (layers "F.Cu"))
\t\t(pad "2" smd rect (at 1 0) (size 1 1) (layers "F.Cu"))
\t)
\t(footprint "lib:Stock"
\t\t(layer "F.Cu")
\t\t(at 0 0)
\t\t(property "Reference" "R1" (at 0 0 0) (layer "F.SilkS"))
\t\t(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu"))
\t\t(model "${KICAD10_3DMODEL_DIR}/x.step"
\t\t\t(offset (xyz 0 0 0))
\t\t)
\t)
\t(footprint "lib:TestPoint_Pad"
\t\t(layer "B.Cu")
\t\t(at 5 5)
\t\t(property "Reference" "TP1" (at 0 0 0) (layer "F.SilkS"))
\t\t(pad "1" smd circle (at 0 0) (size 1 1) (layers "B.Cu"))
\t)
)
'''


class BoardReading(unittest.TestCase):
    def test_reads_lcsc_reference_pads_and_existing_model(self):
        fps = bm.read_footprints(BOARD)
        self.assertEqual([f.reference for f in fps], ["U1", "R1", "TP1"])
        self.assertEqual([f.lcsc for f in fps], ["C12345", "", ""])
        self.assertEqual([f.has_model for f in fps], [False, True, False])
        self.assertEqual([(p.name, p.x) for p in fps[0].pads], [("1", -1.0), ("2", 1.0)])
        self.assertEqual((fps[0].x, fps[0].y, fps[0].rot), (10.0, 20.0, 90.0))
        self.assertEqual([f.has_body for f in fps], [True, True, False])

    def test_injection_adds_a_model_only_where_asked_and_keeps_the_rest(self):
        out = bm.inject_models(BOARD, {0: bm.model_line("/c/a.step", (1, 2, 3), (0, 0, 90))})
        fps = bm.read_footprints(out)
        self.assertEqual([f.has_model for f in fps], [True, True, False])
        self.assertIn('(model "/c/a.step"', out)
        self.assertIn("(xyz 1.0000 2.0000 3.0000)", out)
        self.assertEqual(out.count("(footprint "), 3)
        self.assertEqual(out.count("(") , out.count(")"))
        # the footprints that were not given a block are byte for byte as before
        self.assertEqual(out[fps[1].start:fps[1].end], BOARD[bm.read_footprints(BOARD)[1].start:bm.read_footprints(BOARD)[1].end])

    def test_manifest_blocks_skip_stock_and_bodiless_footprints(self):
        manifest = {"lib:Part_A|C12345": {"source": "fallback", "file": "fallback/a.step",
                                          "offset": [0, 0, 0], "rotate": [0, 0, 0]},
                    "lib:TestPoint_Pad|": {"source": "none"}}
        blocks, report = rb.model_blocks(BOARD, manifest, "/cache")
        self.assertEqual(sorted(blocks), [0])
        self.assertEqual((report["stock"], report["fallback"], report["none"], report["unlisted"]), (1, 1, 1, []))
        self.assertIn("/cache/fallback/a.step", blocks[0])


class VendorModel(unittest.TestCase):
    def test_model_reference_from_component_answer(self):
        node = '{"attrs":{"c_etype":"outline3D","uuid":"abc","z":"-13.7795"}}'
        answer = {"result": {"packageDetail": {"dataStr": {"shape": ["PAD~x", "SVGNODE~" + node]}}}}
        uuid, z = fm.extract_model_ref(answer)
        self.assertEqual(uuid, "abc")
        self.assertAlmostEqual(z, -3.5, places=2)
        self.assertIsNone(fm.extract_model_ref({"result": {"packageDetail": {"dataStr": {"shape": ["PAD~x"]}}}}))
        self.assertIsNone(fm.extract_model_ref({}))

    def test_alignment_finds_the_turn_and_offset_that_put_pins_on_pads(self):
        pads = [bm.Pad("1", "thru_hole", 0.0, 0.0, 2, 2, 0), bm.Pad("2", "thru_hole", 0.0, 7.6, 2, 2, 0)]
        # model pins stand along x at 100 and 107.6 (model frame, y up), reaching below the board
        verts = []
        for x in (100.0, 107.6):
            verts += [(x - 0.2, 5.0, -3.0), (x + 0.2, 5.2, -3.0), (x, 5.1, 0.5)]
        placement, note = fm.align_model(pads, verts)
        self.assertIsNotNone(placement, note)
        self.assertEqual(placement["quarter"] % 2, 1)  # a quarter or three-quarter turn, the pins lie along y
        # pins that no turn can bring onto the pads are refused
        far = [(0.0, 0.0, -3.0), (3.0, 0.0, -3.0), (6.0, 0.0, -3.0)]
        placement, note = fm.align_model(pads, far)
        self.assertIsNone(placement)
        self.assertIn("pads", note)


STOCK_MOD = '''(footprint "R_X"
\t(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu"))
\t(model "${KICAD10_3DMODEL_DIR}/Lib.3dshapes/R_X.step"
\t\t(offset
\t\t\t(xyz 0 0 0)
\t\t)
\t\t(scale
\t\t\t(xyz 1 1 1)
\t\t)
\t\t(rotate
\t\t\t(xyz 0 0 0)
\t\t)
\t)
)
'''


class StockModels(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fp_dir = os.path.join(self.tmp.name, "footprints")
        self.model_dir = os.path.join(self.tmp.name, "3dmodels")
        os.makedirs(os.path.join(self.fp_dir, "Lib.pretty"))
        os.makedirs(os.path.join(self.model_dir, "Lib.3dshapes"))
        with open(os.path.join(self.fp_dir, "Lib.pretty", "R_X.kicad_mod"), "w") as handle:
            handle.write(STOCK_MOD)

    def test_a_board_without_the_stock_model_gets_the_librarys_block(self):
        open(os.path.join(self.model_dir, "Lib.3dshapes", "R_X.step"), "w").close()
        block = bm.stock_model_block("Lib:R_X", self.fp_dir, self.model_dir)
        self.assertIn('(model "${KICAD10_3DMODEL_DIR}/Lib.3dshapes/R_X.step"', block)
        self.assertEqual(block.count("("), block.count(")"))
        # it sits as a footprint's last child: two tabs for the model line, deeper for its fields
        self.assertTrue(block.startswith('\t\t(model '))
        self.assertIn("\t\t\t(offset\n\t\t\t\t(xyz 0 0 0)\n\t\t\t)\n", block)
        board = "(kicad_pcb\n\t(footprint \"Lib:R_X\"\n\t\t(layer \"F.Cu\")\n\t\t(at 0 0)\n\t)\n)\n"
        out = bm.inject_models(board, {0: block})
        self.assertTrue(bm.read_footprints(out)[0].has_model)
        self.assertEqual(out.count("("), out.count(")"))

    def test_no_block_for_a_footprint_the_library_lacks_or_whose_model_file_is_missing(self):
        self.assertIsNone(bm.stock_model_block("Lib:R_X", self.fp_dir, self.model_dir))  # step file missing
        self.assertIsNone(bm.stock_model_block("Lib:Nope", self.fp_dir, self.model_dir))
        self.assertIsNone(bm.stock_model_block("main-board:R_X", self.fp_dir, self.model_dir))
        self.assertIsNone(bm.stock_model_block("R_X", self.fp_dir, self.model_dir))
        self.assertIsNone(bm.stock_model_block("Lib:R_X", "", self.model_dir))

    def test_stock_entries_of_the_manifest_are_injected_for_footprints_without_a_model(self):
        manifest = {"lib:Part_A|C12345": {"source": "stock", "block": "\t\t(model \"X\")\n"},
                    "lib:TestPoint_Pad|": {"source": "none"}}
        blocks, report = rb.model_blocks(BOARD, manifest, "/cache")
        self.assertEqual(blocks, {0: "\t\t(model \"X\")\n"})
        self.assertEqual(report["stock"], 2)  # the entry, and the footprint that already carries one


class FallbackModels(unittest.TestCase):
    def wrl(self, name):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, name + ".wrl")
            ff.write_wrl(path, name, ff.PARTS[name]())
            return open(path).read()

    def test_every_part_is_a_coloured_vrml_with_muted_low_gloss_materials(self):
        for name in ff.PARTS:
            text = self.wrl(name)
            self.assertTrue(text.startswith("#VRML V2.0 utf8"), name)
            self.assertEqual(text.count("{"), text.count("}"), name)
            self.assertEqual(text.count("["), text.count("]"), name)
            colours = re.findall(r"diffuseColor ([\d. ]+)", text)
            self.assertTrue(colours, name)
            for colour in colours:
                r, g, b = (float(v) for v in colour.split())
                self.assertLessEqual(max(r, g, b), 0.7, f"{name}: {colour} is not muted")
                self.assertGreater(max(r, g, b), 0.0, f"{name}: black")
                self.assertLess(max(float(v) for v in re.findall(r"shininess ([\d.]+)", text)), 0.5, name)
            for spec in re.findall(r"specularColor ([\d. ]+)", text):
                self.assertLessEqual(max(float(v) for v in spec.split()), 0.3, name)

    def test_the_part_functions_and_their_material_table_agree(self):
        self.assertTrue(all(m in ff.MATERIALS for build in ff.PARTS.values() for _, _, m in build()))

    def test_writing_is_repeatable(self):
        self.assertEqual(self.wrl("LTV-814S_SMD-4"), self.wrl("LTV-814S_SMD-4"))

    def test_the_reed_body_is_under_the_board_and_its_leads_reach_the_front(self):
        solids = ff.PARTS["REED_PADS_P20.00mm"]()
        glass = [pts for pts, _, m in solids if m == "glass"][0]
        self.assertLess(max(z for _, _, z in glass), -ff.BOARD_THICKNESS)
        tops = [max(z for _, _, z in pts) for pts, _, m in solids if m == "tin"]
        self.assertGreater(max(tops), 0.5)  # a lead end and its solder cone stand above the front surface

    def test_a_convex_solid_is_wound_outward_and_the_y_is_negated(self):
        box = ff.body(0, 2, 10, 12, 0, 1, "body")
        pts = [(x, -y, z) for x, y, z in box[0]]
        centre = [sum(p[i] for p in pts) / len(pts) for i in range(3)]
        for face in ff._outward(pts, box[1]):
            n = [0.0, 0.0, 0.0]
            for k in range(len(face)):
                c = ff._cross(pts[face[k]], pts[face[(k + 1) % len(face)]])
                n = [n[m] + c[m] for m in range(3)]
            mid = [sum(pts[i][m] for i in face) / len(face) for m in range(3)]
            self.assertGreater(sum(n[m] * (mid[m] - centre[m]) for m in range(3)), 0)

    def test_fetch_writes_the_vrml_for_a_named_part_and_a_generic_block_otherwise(self):
        fps = bm.read_footprints(BOARD.replace("lib:Part_A", "main-board:LTV-814S_SMD-4"))
        with tempfile.TemporaryDirectory() as tmp:
            name, how = fm.fallback_model(fps[0], tmp)
            self.assertEqual(name, os.path.join("fallback", "LTV-814S_SMD-4.wrl"))
            self.assertIn("simplified body", how)
            generic = bm.read_footprints(BOARD)[0]
            generic.lib_id = "lib:Unknown_Thing"
            name, how = fm.fallback_model(generic, tmp)
            self.assertTrue(name.endswith("Unknown_Thing.wrl"))
            self.assertIn("generic block", how)
            self.assertTrue(open(os.path.join(tmp, "Unknown_Thing.wrl")).read().startswith("#VRML V2.0"))


class FetchRobustness(unittest.TestCase):
    def test_a_transient_failure_is_retried_and_a_404_is_not(self):
        calls = []

        class Answer:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b"ok"

        def flaky(request, timeout):
            calls.append(1)
            if len(calls) < 3:
                raise urllib.error.URLError("reset")
            return Answer()

        with mock.patch.object(fm.urllib.request, "urlopen", flaky), mock.patch.object(fm.time, "sleep"):
            self.assertEqual(fm.http_get("https://x"), b"ok")
        self.assertEqual(len(calls), 3)
        calls.clear()

        def missing(request, timeout):
            calls.append(1)
            raise urllib.error.HTTPError("https://x", 404, "nf", {}, None)

        with mock.patch.object(fm.urllib.request, "urlopen", missing), mock.patch.object(fm.time, "sleep"):
            with self.assertRaises(urllib.error.HTTPError):
                fm.http_get("https://x")
        self.assertEqual(len(calls), 1)

    def test_a_no_model_answer_expires_and_can_be_asked_again_on_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "C1.json")
            json.dump({"status": "none", "detail": "d", "at": time.time()}, open(path, "w"))
            self.assertEqual(fm.fetch_vendor("C1", tmp, 0, True), ("none", "d"))
            # asked again on request: offline, so it reports that it could not
            self.assertEqual(fm.fetch_vendor("C1", tmp, 0, True, retry_none=True)[0], "error")
            json.dump({"status": "none", "detail": "d", "at": time.time() - 2 * fm.NONE_TTL_SECONDS}, open(path, "w"))
            self.assertEqual(fm.fetch_vendor("C1", tmp, 0, True)[0], "error")
            json.dump({"status": "none", "detail": "d"}, open(path, "w"))  # an old file without a time is stale
            self.assertEqual(fm.fetch_vendor("C1", tmp, 0, True)[0], "error")


class AlignmentChoices(unittest.TestCase):
    def test_overshoot_measures_how_far_the_body_stands_outside_the_courtyard(self):
        verts = [(-3.0, -1.0, 0.0), (3.0, 1.0, 0.0)]
        court = (-2.5, -1.8, 2.5, 1.8)
        self.assertAlmostEqual(fm._overshoot(verts, 0.0, 0.0, court), 1.0)  # 0.5 beyond each x side
        rot = fm._rotate(verts, 1)  # a quarter turn puts the 6 mm length along y, beyond the 3.6 mm courtyard
        self.assertGreater(fm._overshoot(rot, 0.0, 0.0, court), 0.0)
        self.assertEqual(fm._overshoot(verts, 0.0, 0.0, None), 0.0)
        self.assertEqual(fm._overshoot(verts, 0.0, 0.0, (-9, -9, 9, 9)), 0.0)

    def test_pins_a_little_off_the_footprints_pitch_are_centred_on_it(self):
        pads = [bm.Pad("1", "thru_hole", -11.0, 0.0, 1.2, 2.4, 0, 0.6), bm.Pad("2", "thru_hole", 11.0, 0.0, 1.2, 2.4, 0, 0.6)]
        verts = []
        for x in (-10.95, 11.9):  # a 22.85 pitch against 22; each pin two prongs apart
            for y in (-0.6, 0.6):
                verts += [(x, y, -4.0), (x, y, 0.5)]
        placement, note = fm.align_model(pads, verts)
        self.assertIsNotNone(placement, note)
        self.assertAlmostEqual(placement["offset"][0], -0.475, places=2)

    def test_a_model_drawn_about_its_middle_is_lowered_to_the_boards_underside(self):
        pads = [bm.Pad("1", "thru_hole", 0.0, 0.0, 7.0, 1.45, 0, 1.0)]
        verts = [(x, y, z) for x in (-3.15, 3.15) for y in (-0.4, 0.4) for z in (-7.15, -5.5, 7.15)] + [(8.0, 0.0, -3.0)]
        placement, note = fm.align_model(pads, verts)
        self.assertIsNotNone(placement, note)
        self.assertAlmostEqual(placement["offset"][2], 5.55, places=2)

    def test_a_sense_pad_beside_the_terminals_needs_no_lead(self):
        pads = [bm.Pad("1", "smd", -2.5, 0, 3.3, 3.3, 0), bm.Pad("2", "smd", 0.0, -0.85, 0.76, 0.51, 0),
                bm.Pad("3", "smd", 2.5, 0, 3.3, 3.3, 0)]
        verts = [(x, y, 0.0) for x in (-3.1, -1.9, 1.9, 3.1) for y in (-1.5, 1.5)] + [(0, 0, 0.7)]
        placement, note = fm.align_model(pads, verts)
        self.assertIsNotNone(placement, note)
        self.assertEqual(placement["quarter"] % 2, 0)


class ClosePictures(unittest.TestCase):
    def test_a_close_up_from_below_mirrors_the_pan_in_x(self):
        fp = bm.read_footprints(BOARD)[0]
        text = BOARD
        top = rb.close_up_args(text, fp)
        below = rb.close_up_args(text, fp, mirror=True)
        tx, ty, _ = top[3].split(",")
        bx, by, _ = below[3].split(",")
        self.assertEqual((float(bx), by), (-float(tx), ty))
        self.assertIn("angled_opposite", rb.ANGLES)
        self.assertIn("low_side", rb.ANGLES)


if __name__ == "__main__":
    unittest.main()
