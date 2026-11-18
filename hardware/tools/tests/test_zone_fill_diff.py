#!/usr/bin/env python3
"""The fill difference, driven on synthetic boards filled by KiCad itself."""

from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import zone_fill_diff  # noqa: E402
import zone_refill  # noqa: E402
from layout_tool_fixtures import Work, board_text, require_kicad_python, square, track, zone  # noqa: E402


def setUpModule():
    require_kicad_python()


class TheFillDifference(Work):
    def filled(self, name, items):
        """A board of `items` written, refilled by the safe refill, and its path."""
        board = self.write(name + ".src.kicad_pcb", board_text(items))
        output = self.path(name + ".kicad_pcb")
        self.assertEqual(self.run_tool(zone_refill.main, "--board", board, "--output", output)[0], 0)
        return output

    def diff(self, first, second, *extra):
        return self.run_json(zone_fill_diff.main, "--first", first, "--second", second, *extra)

    def test_identical_boards_report_no_difference(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C3: Run over two synthetic boards whose zones differ, the command reports for each zone and each layer the copper area present in one board and absent in the other, and reports no difference for identical boards. Tests cover a zone that gains copper, one that loses copper, a layer that holds no zone and boards with different zone sets, in text and in JSON. This does not cover differences outside zones, which the other checks report.
        a = self.filled("a", [zone("Z1", "/PWR", "B.Cu", square(30, 30, 10)), zone("Z2", "/GND", "F.Cu", square(5, 5, 8))])
        for first, second in ((a, a), (a, self.write("copy.kicad_pcb", self.read(a)))):
            status, lines = self.run_tool(zone_fill_diff.main, "--first", first, "--second", second)
            self.assertEqual(status, 0, lines)
            self.assertEqual(len(lines), 1, lines)
            self.assertTrue(lines[0].startswith("RESULT | SAME | no zone differs by more than 0.01 mm2 on any of 2 zone layers"), lines)
        status, found = self.diff(a, a)
        self.assertEqual((status, found["result"], found["differences"], found["findings"]), (0, "SAME", [], []))

    def test_a_zone_that_gains_copper_reports_the_area_gained_on_its_layer(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C3: Run over two synthetic boards whose zones differ, the command reports for each zone and each layer the copper area present in one board and absent in the other, and reports no difference for identical boards. Tests cover a zone that gains copper, one that loses copper, a layer that holds no zone and boards with different zone sets, in text and in JSON. This does not cover differences outside zones, which the other checks report.
        first = self.filled("a", [zone("Z1", "/PWR", "B.Cu", square(30, 30, 10))])
        second = self.filled("b", [zone("Z1", "/PWR", "B.Cu", square(30, 30, 20))])
        status, lines = self.run_tool(zone_fill_diff.main, "--first", first, "--second", second)
        self.assertEqual(status, 1, lines)
        self.assertTrue(lines[0].startswith("DIFFERENT | zone Z1 on B.Cu | on both boards: 0.0000 mm2 of copper in the first board and not the second, 300."), lines)
        self.assertTrue(lines[-1].startswith("RESULT | DIFFERENT | 1 zone layer differ"), lines)
        status, found = self.diff(first, second)
        row = found["differences"][0]
        self.assertEqual((status, row["zone"], row["layer"]), (1, "Z1", "B.Cu"))
        self.assertAlmostEqual(row["only_second"], 300.0, delta=1.0)
        self.assertAlmostEqual(row["only_first"], 0.0, delta=0.01)

    def test_a_zone_that_loses_copper_reports_the_area_lost(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C3: Run over two synthetic boards whose zones differ, the command reports for each zone and each layer the copper area present in one board and absent in the other, and reports no difference for identical boards. Tests cover a zone that gains copper, one that loses copper, a layer that holds no zone and boards with different zone sets, in text and in JSON. This does not cover differences outside zones, which the other checks report.
        first = self.filled("a", [zone("Z1", "/PWR", "B.Cu", square(30, 30, 20))])
        second = self.filled("b", [zone("Z1", "/PWR", "B.Cu", square(30, 30, 10))])
        status, found = self.diff(first, second)
        row = found["differences"][0]
        self.assertEqual(status, 1)
        self.assertAlmostEqual(row["only_first"], 300.0, delta=1.0)
        self.assertAlmostEqual(row["only_second"], 0.0, delta=0.01)

    def test_a_foreign_track_inside_a_zone_shows_as_copper_the_zone_lost(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C3: Run over two synthetic boards whose zones differ, the command reports for each zone and each layer the copper area present in one board and absent in the other, and reports no difference for identical boards. Tests cover a zone that gains copper, one that loses copper, a layer that holds no zone and boards with different zone sets, in text and in JSON. This does not cover differences outside zones, which the other checks report.
        zones = [zone("Z1", "/PWR", "B.Cu", square(30, 30, 10), "(clearance 1)")]
        first = self.filled("a", zones)
        second = self.filled("b", zones + [track("/LV", (32, 35), (38, 35), "B.Cu")])
        status, found = self.diff(first, second)
        self.assertEqual(status, 1)
        row = found["differences"][0]
        self.assertAlmostEqual(row["only_first"], 6 * (0.25 + 2.0) + 3.14159 * 1.125 ** 2 - 0.4, delta=3.0)
        self.assertAlmostEqual(row["only_second"], 0.0, delta=0.01)

    def test_a_layer_that_holds_no_zone_is_not_reported_and_a_zone_on_two_layers_is_reported_per_layer(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C3: Run over two synthetic boards whose zones differ, the command reports for each zone and each layer the copper area present in one board and absent in the other, and reports no difference for identical boards. Tests cover a zone that gains copper, one that loses copper, a layer that holds no zone and boards with different zone sets, in text and in JSON. This does not cover differences outside zones, which the other checks report.
        both = zone("Z1", "/PWR", "B.Cu", square(30, 30, 10)).replace('(layer "B.Cu")', '(layers "F.Cu" "B.Cu")')
        only_back = zone("Z1", "/PWR", "B.Cu", square(30, 30, 10))
        first = self.filled("a", [both])
        second = self.filled("b", [only_back])
        status, found = self.diff(first, second)
        self.assertEqual(status, 1)
        self.assertEqual([(row["layer"], row["in_first"], row["in_second"]) for row in found["differences"]],
                         [("F.Cu", True, False)])
        self.assertAlmostEqual(found["differences"][0]["only_first"], 100.0, delta=0.1)
        layers = {row["layer"] for row in found["differences"]}
        self.assertTrue({"In1.Cu", "In2.Cu", "B.Cu"}.isdisjoint(layers))
        status, lines = self.run_tool(zone_fill_diff.main, "--first", first, "--second", second)
        self.assertIn("only on the first board", lines[0])
        self.assertTrue(lines[0].startswith("DIFFERENT | zone Z1 on F.Cu | "), lines)

    def test_boards_with_different_zone_sets_report_each_zone_only_one_has(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C3: Run over two synthetic boards whose zones differ, the command reports for each zone and each layer the copper area present in one board and absent in the other, and reports no difference for identical boards. Tests cover a zone that gains copper, one that loses copper, a layer that holds no zone and boards with different zone sets, in text and in JSON. This does not cover differences outside zones, which the other checks report.
        first = self.filled("a", [zone("Shared", "/PWR", "B.Cu", square(30, 30, 10)), zone("Gone", "/GND", "F.Cu", square(5, 5, 8))])
        second = self.filled("b", [zone("Shared", "/PWR", "B.Cu", square(30, 30, 10)), zone("New", "/GND", "In1.Cu", square(5, 5, 4))])
        status, found = self.diff(first, second)
        self.assertEqual(status, 1)
        rows = {(row["zone"], row["layer"]): row for row in found["differences"]}
        self.assertEqual(sorted(rows), [("Gone", "F.Cu"), ("New", "In1.Cu")])
        self.assertAlmostEqual(rows[("Gone", "F.Cu")]["only_first"], 64.0, delta=0.1)
        self.assertEqual(rows[("Gone", "F.Cu")]["in_second"], False)
        self.assertAlmostEqual(rows[("New", "In1.Cu")]["only_second"], 16.0, delta=0.1)
        self.assertEqual(rows[("New", "In1.Cu")]["in_first"], False)
        self.assertTrue(found["detail"].startswith("2 zone layers differ"), found)

    def test_kicads_own_save_noise_is_not_a_difference_but_a_real_change_below_a_zero_tolerance_is(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C3: Run over two synthetic boards whose zones differ, the command reports for each zone and each layer the copper area present in one board and absent in the other, and reports no difference for identical boards. Tests cover a zone that gains copper, one that loses copper, a layer that holds no zone and boards with different zone sets, in text and in JSON. This does not cover differences outside zones, which the other checks report.
        odd = [(30.123457, 30.987654), (41.333333, 30.111111), (40.777777, 42.222223), (29.999999, 41.5)]
        first = self.filled("a", [zone("Z1", "/PWR", "B.Cu", odd, "(clearance 0.3)"), track("/LV", (31, 36), (39, 36), "B.Cu")])
        saved = self.path("saved.kicad_pcb")
        script = "import sys, pcbnew\npcbnew.SaveBoard(sys.argv[2], pcbnew.LoadBoard(sys.argv[1]))\n"
        done = subprocess.run([require_kicad_python(), "-I", "-c", script, first, saved], capture_output=True, text=True, timeout=600)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotEqual(self.read(first), self.read(saved), "KiCad's save should have rewritten the file")
        status, found = self.diff(first, saved)
        self.assertEqual((status, found["result"]), (0, "SAME"), found)
        shifted = self.filled("b", [zone("Z1", "/PWR", "B.Cu", [(x, y) for x, y in odd[:3]] + [(29.999999, 41.5005)], "(clearance 0.3)"),
                                    track("/LV", (31, 36), (39, 36), "B.Cu")])
        status, found = self.diff(first, shifted)
        self.assertEqual(status, 0, "a change smaller than the tolerance is noise")
        status, found = self.diff(first, shifted, "--tolerance", "0")
        self.assertEqual((status, found["result"]), (1, "DIFFERENT"), found)

    def test_a_negative_tolerance_and_unreadable_boards_are_refused(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C3: Run over two synthetic boards whose zones differ, the command reports for each zone and each layer the copper area present in one board and absent in the other, and reports no difference for identical boards. Tests cover a zone that gains copper, one that loses copper, a layer that holds no zone and boards with different zone sets, in text and in JSON. This does not cover differences outside zones, which the other checks report.
        a = self.filled("a", [zone("Z1", "/PWR", "B.Cu", square(30, 30, 10))])
        status, found = self.diff(a, a, "--tolerance", "-1")
        self.assertEqual((status, found["result"], found["findings"][0]["finding"]), (1, "REFUSED", "REFUSED"))
        junk = self.write("junk.kicad_pcb", "(kicad_sch)")
        for first, second in ((a, junk), (junk, a), (a, self.path("missing.kicad_pcb"))):
            status, lines = self.run_tool(zone_fill_diff.main, "--first", first, "--second", second)
            self.assertEqual(status, 1, lines)
            self.assertTrue(lines[0].startswith("UNREADABLE | "), lines)
            self.assertTrue(lines[-1].startswith("RESULT | REFUSED | a board cannot be read"), lines)
        status, found = self.diff(a, junk)
        self.assertEqual((status, found["result"]), (1, "REFUSED"))


if __name__ == "__main__":
    import unittest
    unittest.main()
