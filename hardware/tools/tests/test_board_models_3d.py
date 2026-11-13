#!/usr/bin/env python3
"""The 3D picture commands' board reading, model injection and vendor-model alignment, on synthetic text."""

from __future__ import annotations

import os
import sys
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_models_3d as bm  # noqa: E402
import fetch_3d_models as fm  # noqa: E402
import render_board_3d as rb  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
