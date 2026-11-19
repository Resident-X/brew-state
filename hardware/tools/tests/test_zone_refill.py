#!/usr/bin/env python3
"""The safe zone refill, driven on synthetic boards against KiCad's own scripting interface."""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import zone_fill_diff  # noqa: E402
import zone_refill  # noqa: E402
from layout_tool_fixtures import Work, board_text, require_kicad_python, square, track, zone  # noqa: E402

PREFIX = "SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD"
PROPERTIES = (("MAINS", "present"), ("BOARD_REV", "B 2"), ("NOTE", "a | b"))


def setUpModule():
    require_kicad_python()


def clearances(text: str):
    """Every (clearance ...) value written inside a zone's (connect_pads ...), in order."""
    return re.findall(r"\(connect_pads[^()]*\(clearance ([^)]*)\)", text)


class TheRefillKeepsWhatKiCadsSaveDrops(Work):
    def refill(self, text, *extra, name="b.kicad_pcb"):
        board = self.write(name, text)
        output = self.path("out.kicad_pcb")
        status, lines = self.run_tool(zone_refill.main, "--board", board, "--output", output, *extra)
        return status, lines, output

    def test_every_property_line_survives_and_the_zone_is_filled(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C2: Run over a synthetic board that carries property lines and zone clearances, the refill command leaves every property line and every zone clearance as it was before the run and never writes a zero zone clearance, with the refilled copper otherwise as the zone fill computes it. Tests cover a board with property lines, a zone with an explicit clearance and a board with no zones, in text and in JSON. This does not cover the refill's speed or any zone other than a copper zone.
        text = board_text([zone("Z1", "/PWR", "B.Cu", square(30, 30, 10))], PROPERTIES)
        status, lines, output = self.refill(text)
        self.assertEqual(status, 0, lines)
        result = self.read(output)
        self.assertEqual(self.property_lines(result), self.property_lines(text))
        self.assertEqual(len(self.property_lines(result)), 3)
        self.assertIn("(filled_polygon", result)
        self.assertNotIn("(filled_polygon", text)
        self.assertEqual([line.split(" | ")[:2] for line in lines if line.startswith("KEPT | property")],
                         [["KEPT", f"property {name}"] for name, _ in PROPERTIES])
        self.assertTrue(lines[-1].startswith("RESULT | REFILLED | 1 zone refilled, 3 property lines"), lines)

    def test_a_board_without_the_property_lines_gains_none(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C2: Run over a synthetic board that carries property lines and zone clearances, the refill command leaves every property line and every zone clearance as it was before the run and never writes a zero zone clearance, with the refilled copper otherwise as the zone fill computes it. Tests cover a board with property lines, a zone with an explicit clearance and a board with no zones, in text and in JSON. This does not cover the refill's speed or any zone other than a copper zone.
        status, lines, output = self.refill(board_text([zone("Z1", "/PWR", "B.Cu", square(30, 30, 10))]))
        self.assertEqual(status, 0, lines)
        self.assertEqual(self.property_lines(self.read(output)), [])

    def test_an_explicit_zone_clearance_is_kept_and_the_fill_honours_it(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C2: Run over a synthetic board that carries property lines and zone clearances, the refill command leaves every property line and every zone clearance as it was before the run and never writes a zero zone clearance, with the refilled copper otherwise as the zone fill computes it. Tests cover a board with property lines, a zone with an explicit clearance and a board with no zones, in text and in JSON. This does not cover the refill's speed or any zone other than a copper zone.
        foreign = track("/LV", (30, 35), (40, 35), "B.Cu", 0.25)
        wide = board_text([zone("Z1", "/PWR", "B.Cu", square(30, 30, 10), "(clearance 2)"), foreign], PROPERTIES)
        narrow = board_text([zone("Z1", "/PWR", "B.Cu", square(30, 30, 10), "(clearance 0.25)"), foreign], PROPERTIES)
        status, lines, wide_out = self.refill(wide, name="wide.kicad_pcb")
        self.assertEqual(status, 0, lines)
        self.assertEqual(clearances(self.read(wide_out)), ["2"])
        self.assertIn("KEPT | zone Z1 | clearance 2 mm is as it was", lines)
        narrow_board = self.write("narrow.kicad_pcb", narrow)
        narrow_out = self.path("narrow-out.kicad_pcb")
        self.assertEqual(self.run_tool(zone_refill.main, "--board", narrow_board, "--output", narrow_out)[0], 0)
        self.assertEqual(clearances(self.read(narrow_out)), ["0.25"])
        status, found = self.run_json(zone_fill_diff.main, "--first", wide_out, "--second", narrow_out)
        self.assertEqual(status, 1)
        self.assertGreater(found["differences"][0]["only_second"], 5.0, "the wider clearance must have taken copper from the fill")

    def test_a_zone_with_no_clearance_of_its_own_is_written_with_none_and_never_a_zero(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C2: Run over a synthetic board that carries property lines and zone clearances, the refill command leaves every property line and every zone clearance as it was before the run and never writes a zero zone clearance, with the refilled copper otherwise as the zone fill computes it. Tests cover a board with property lines, a zone with an explicit clearance and a board with no zones, in text and in JSON. This does not cover the refill's speed or any zone other than a copper zone.
        text = board_text([zone("Plain", "/PWR", "B.Cu", square(30, 30, 10), ""),
                           zone("Explicit", "/GND", "F.Cu", square(30, 30, 10), "(clearance 0.75)")], PROPERTIES)
        status, lines, output = self.refill(text)
        self.assertEqual(status, 0, lines)
        result = self.read(output)
        self.assertEqual(clearances(result), ["0.75"])
        self.assertNotRegex(result, r"\(clearance 0(\.0+)?\)")
        self.assertEqual(len(re.findall(r"\(connect_pads", result)), 1)
        dropped = [line for line in lines if line.startswith("DROPPED")]
        self.assertEqual(len(dropped), 1, lines)
        self.assertIn("zone Plain", dropped[0])
        self.assertIn("(filled_polygon", result)

    def test_an_explicit_zero_clearance_in_the_board_is_not_written_back(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C2: Run over a synthetic board that carries property lines and zone clearances, the refill command leaves every property line and every zone clearance as it was before the run and never writes a zero zone clearance, with the refilled copper otherwise as the zone fill computes it. Tests cover a board with property lines, a zone with an explicit clearance and a board with no zones, in text and in JSON. This does not cover the refill's speed or any zone other than a copper zone.
        text = board_text([zone("Zero", "/PWR", "B.Cu", square(30, 30, 10), "(clearance 0)")], PROPERTIES)
        status, lines, output = self.refill(text)
        self.assertEqual(status, 0, lines)
        self.assertEqual(clearances(self.read(output)), [])
        self.assertNotRegex(self.read(output), r"\(clearance 0(\.0+)?\)")
        self.assertTrue(any(line.startswith("DROPPED | zone Zero | clearance removed: the board gave a zero") for line in lines), lines)

    def test_a_board_with_no_zones_is_written_unchanged(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C2: Run over a synthetic board that carries property lines and zone clearances, the refill command leaves every property line and every zone clearance as it was before the run and never writes a zero zone clearance, with the refilled copper otherwise as the zone fill computes it. Tests cover a board with property lines, a zone with an explicit clearance and a board with no zones, in text and in JSON. This does not cover the refill's speed or any zone other than a copper zone.
        text = board_text([track("/PWR", (0, 0), (5, 0))], PROPERTIES)
        status, lines, output = self.refill(text)
        self.assertEqual(status, 0, lines)
        self.assertEqual(self.read(output), text)
        self.assertTrue(lines[-1].startswith("RESULT | REFILLED | 0 zones refilled"), lines)

    def test_the_output_may_be_the_board_itself(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C2: Run over a synthetic board that carries property lines and zone clearances, the refill command leaves every property line and every zone clearance as it was before the run and never writes a zero zone clearance, with the refilled copper otherwise as the zone fill computes it. Tests cover a board with property lines, a zone with an explicit clearance and a board with no zones, in text and in JSON. This does not cover the refill's speed or any zone other than a copper zone.
        board = self.write("b.kicad_pcb", board_text([zone("Z1", "/PWR", "B.Cu", square(30, 30, 10), "(clearance 0.75)")], PROPERTIES))
        status, lines = self.run_tool(zone_refill.main, "--board", board, "--output", board)
        self.assertEqual(status, 0, lines)
        result = self.read(board)
        self.assertIn("(filled_polygon", result)
        self.assertEqual(clearances(result), ["0.75"])
        self.assertEqual(len(self.property_lines(result)), 3)

    def test_the_refilled_copper_is_what_kicads_own_fill_computes(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C2: Run over a synthetic board that carries property lines and zone clearances, the refill command leaves every property line and every zone clearance as it was before the run and never writes a zero zone clearance, with the refilled copper otherwise as the zone fill computes it. Tests cover a board with property lines, a zone with an explicit clearance and a board with no zones, in text and in JSON. This does not cover the refill's speed or any zone other than a copper zone.
        import subprocess
        text = board_text([zone("Z1", "/PWR", "B.Cu", square(30, 30, 10), "(clearance 1)"),
                           track("/LV", (32, 35), (38, 35), "B.Cu")], PROPERTIES)
        board = self.write("b.kicad_pcb", text)
        direct = self.path("direct.kicad_pcb")
        script = ("import sys, pcbnew\nb = pcbnew.LoadBoard(sys.argv[1])\npcbnew.ZONE_FILLER(b).Fill(b.Zones())\n"
                  "pcbnew.SaveBoard(sys.argv[2], b)\n")
        python = require_kicad_python()
        done = subprocess.run([python, "-I", "-c", script, board, direct], capture_output=True, text=True, timeout=600)
        self.assertEqual(done.returncode, 0, done.stderr)
        output = self.path("out.kicad_pcb")
        self.assertEqual(self.run_tool(zone_refill.main, "--board", board, "--output", output)[0], 0)
        status, found = self.run_json(zone_fill_diff.main, "--first", direct, "--second", output, "--tolerance", "0.0001")
        self.assertEqual(status, 0, found)
        self.assertEqual(found["result"], "SAME")

    def test_json_report_carries_the_result_and_each_kept_item(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C2: Run over a synthetic board that carries property lines and zone clearances, the refill command leaves every property line and every zone clearance as it was before the run and never writes a zero zone clearance, with the refilled copper otherwise as the zone fill computes it. Tests cover a board with property lines, a zone with an explicit clearance and a board with no zones, in text and in JSON. This does not cover the refill's speed or any zone other than a copper zone.
        board = self.write("b.kicad_pcb", board_text([zone("Z1", "/PWR", "B.Cu", square(30, 30, 10), "(clearance 0.75)"),
                                                      zone("Z2", "/GND", "F.Cu", square(30, 30, 10), "")], PROPERTIES))
        output = self.path("out.kicad_pcb")
        status, found = self.run_json(zone_refill.main, "--board", board, "--output", output)
        self.assertEqual(status, 0, found)
        self.assertEqual(found["result"], "REFILLED")
        self.assertEqual(found["output"], output)
        kinds = sorted((item["finding"], item["item"]) for item in found["findings"])
        self.assertEqual(kinds, sorted([("KEPT", "property MAINS"), ("KEPT", "property BOARD_REV"), ("KEPT", "property NOTE"),
                                        ("KEPT", "zone Z1"), ("DROPPED", "zone Z2")]))

    def test_a_board_that_cannot_be_read_is_refused_and_nothing_is_written(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C2: Run over a synthetic board that carries property lines and zone clearances, the refill command leaves every property line and every zone clearance as it was before the run and never writes a zero zone clearance, with the refilled copper otherwise as the zone fill computes it. Tests cover a board with property lines, a zone with an explicit clearance and a board with no zones, in text and in JSON. This does not cover the refill's speed or any zone other than a copper zone.
        output = self.path("out.kicad_pcb")
        for label, text in (("garbage", "this is not a board"), ("other file", "(kicad_sch (version 1))"), ("empty", "")):
            with self.subTest(label):
                board = self.write("bad.kicad_pcb", text)
                status, lines = self.run_tool(zone_refill.main, "--board", board, "--output", output)
                self.assertEqual(status, 1, lines)
                self.assertTrue(lines[0].startswith("UNREADABLE | "), lines)
                self.assertTrue(lines[-1].startswith("RESULT | REFUSED"), lines)
                self.assertFalse(os.path.exists(output))
        status, found = self.run_json(zone_refill.main, "--board", self.path("missing.kicad_pcb"), "--output", output)
        self.assertEqual(status, 1)
        self.assertEqual(found["result"], "REFUSED")
        self.assertEqual(found["findings"][0]["finding"], "UNREADABLE")

    def test_a_board_open_in_an_editor_is_refused(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C2: Run over a synthetic board that carries property lines and zone clearances, the refill command leaves every property line and every zone clearance as it was before the run and never writes a zero zone clearance, with the refilled copper otherwise as the zone fill computes it. Tests cover a board with property lines, a zone with an explicit clearance and a board with no zones, in text and in JSON. This does not cover the refill's speed or any zone other than a copper zone.
        board = self.write("b.kicad_pcb", board_text([zone("Z1", "/PWR", "B.Cu", square(30, 30, 10))]))
        self.write("~b.kicad_pcb.lck", "{}")
        output = self.path("out.kicad_pcb")
        status, lines = self.run_tool(zone_refill.main, "--board", board, "--output", output)
        self.assertEqual(status, 1, lines)
        self.assertTrue(lines[0].startswith("OPEN | "), lines)
        self.assertFalse(os.path.exists(output))

    def test_an_output_that_cannot_be_written_is_refused(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C2: Run over a synthetic board that carries property lines and zone clearances, the refill command leaves every property line and every zone clearance as it was before the run and never writes a zero zone clearance, with the refilled copper otherwise as the zone fill computes it. Tests cover a board with property lines, a zone with an explicit clearance and a board with no zones, in text and in JSON. This does not cover the refill's speed or any zone other than a copper zone.
        board = self.write("b.kicad_pcb", board_text([track("/PWR", (0, 0), (5, 0))]))
        status, lines = self.run_tool(zone_refill.main, "--board", board, "--output", self.path("no-such-folder/out.kicad_pcb"))
        self.assertEqual(status, 1, lines)
        self.assertTrue(lines[0].startswith("UNWRITABLE | "), lines)


if __name__ == "__main__":
    import unittest
    unittest.main()
