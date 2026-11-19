"""The silkscreen table: the board's own choices, read and checked before anything is placed.

This module needs neither KiCad nor the placement packages: the table is read by plain Python.
"""

from __future__ import annotations

import os
import sys
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import silkscreen_table  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
MAIN_BOARD_TABLE = os.path.join(REPO, "hardware", "sunbeam-em7000", "main-board", "silkscreen.yaml")


class Table(unittest.TestCase):
    def refused(self, text, key):
        with self.assertRaises(silkscreen_table.TableError) as caught:
            silkscreen_table.load(text)
        self.assertIn(key, str(caught.exception))

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C6: Run twice over the same synthetic board and the same table, the command writes boards whose silkscreen is identical in both runs. Tests cover several parts, a part with an override in the table, a part whose label cannot be placed, which is listed in the unplaced report, and an empty board, in text and in JSON. This does not cover the choice of text heights and legends, which the board's table holds.
    def test_an_empty_table_gives_the_defaults_and_the_same_table_always_reads_the_same(self):
        first, second = silkscreen_table.load(""), silkscreen_table.load("# nothing but a comment\n")
        self.assertEqual(first, second)
        self.assertEqual(first["reference_sizes"], [1.0, 0.8])
        self.assertEqual(first["thickness"][1.0], 0.15)
        self.assertEqual(first["legends"], [])

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C6: Run twice over the same synthetic board and the same table, the command writes boards whose silkscreen is identical in both runs. Tests cover several parts, a part with an override in the table, a part whose label cannot be placed, which is listed in the unplaced report, and an empty board, in text and in JSON. This does not cover the choice of text heights and legends, which the board's table holds.
    def test_a_given_key_replaces_its_default_and_leaves_the_others(self):
        table = silkscreen_table.load("reference_sizes: [1.5, 1.0]\nthickness: {1.5: 0.2, 1.0: 0.15, 0.8: 0.15}\nparts: {R1: {pin1: dot}}\n"
                                      "fuses: {format: 'F{amps}'}\n")
        self.assertEqual(table["reference_sizes"], [1.5, 1.0])
        self.assertEqual(table["name_sizes"], [1.0, 0.8])
        self.assertEqual(table["fuses"]["format"], "F{amps}")
        self.assertEqual(table["fuses"]["pattern"], r"^F\d+$")
        self.assertEqual(table["parts"]["R1"]["pin1"], "dot")

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C6: Run twice over the same synthetic board and the same table, the command writes boards whose silkscreen is identical in both runs. Tests cover several parts, a part with an override in the table, a part whose label cannot be placed, which is listed in the unplaced report, and an empty board, in text and in JSON. This does not cover the choice of text heights and legends, which the board's table holds.
    def test_a_mistake_in_the_table_is_refused_naming_the_key(self):
        self.refused("colour: red\n", "colour")
        self.refused("reference_sizes: []\n", "reference_sizes")
        self.refused("reference_sizes: [1.2]\n", "no stroke for the text height 1.2")
        self.refused("fuses: {pattern: '(('}\n", "fuses.pattern")
        self.refused("fuses: {format: nothing}\n", "fuses.format")
        self.refused("clearance: -1\n", "clearance")
        self.refused("parts: {R1: {colour: red}}\n", "parts.R1")
        self.refused("parts: {R1: {reference: hide}}\n", "parts.R1.reference")
        self.refused("parts: {R1: {pin1: star}}\n", "parts.R1.pin1")
        self.refused("pin1: {dot: U1}\n", "pin1.dot")
        self.refused("tabs: {known: [J1]}\n", "tabs.known")
        self.refused("thickness: {1.0: 0.01}\n", "thickness.1.0")
        self.refused("- a\n- b\n", "mapping")
        self.refused("a: [\n", "not YAML")

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C6: Run twice over the same synthetic board and the same table, the command writes boards whose silkscreen is identical in both runs. Tests cover several parts, a part with an override in the table, a part whose label cannot be placed, which is listed in the unplaced report, and an empty board, in text and in JSON. This does not cover the choice of text heights and legends, which the board's table holds.
    def test_legends_and_fixed_texts_are_checked_whole(self):
        legend = "legends:\n  - {id: a, region: mains, lines: [{text: DANGER, size: 1.0}]}\n"
        self.assertEqual(silkscreen_table.load(legend)["legends"][0]["id"], "a")
        self.refused("legends:\n  - {id: a, lines: [{text: X, size: 1.0}]}\n", "legends[0].region")
        self.refused("legends:\n  - {id: a, region: mains, lines: []}\n", "legends[0].lines")
        self.refused("legends:\n  - {id: a, region: mains, symbol: skull, lines: [{text: X, size: 1.0}]}\n", "symbol")
        self.refused("legends:\n  - {id: a, region: mains, lines: [{text: X, size: 3.0}]}\n", "no stroke for the text height 3.0")
        self.refused(legend + "fixed_texts:\n  - {id: a, text: T, size: 1.0, at: [1, 2]}\n", "'a' is used twice")
        self.refused("fixed_texts:\n  - {id: t, text: T, size: 1.0}\n", "fixed_texts[0].at")
        self.refused("fixed_texts:\n  - {id: t, text: T, size: 1.0, at: [1, 2], angle: 45}\n", "fixed_texts[0].angle")
        self.refused("fixed_texts:\n  - {text: T, size: 1.0, at: [1, 2]}\n", "fixed_texts[0].id")
        self.refused("fixed_texts:\n  - {id: t, text: T, size: 1.0, at: [1, 2], side: top}\n", "side")

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C11: Each tool in this set has a test that runs it on a synthetic design built by the test, and the hardware notes describe each tool's command, its inputs, the board folder table it reads and the manual step of fetching an assembler's library footprints. Checked by reading the hardware notes against the list of tools clause by clause. This does not apply to the fetch of an assembler's library footprints, which stays a documented manual step.
    def test_the_main_boards_own_table_is_a_table_the_command_reads(self):
        with open(MAIN_BOARD_TABLE, encoding="utf-8") as handle:
            table = silkscreen_table.load(handle.read())
        self.assertGreater(len(table["fixed_texts"]), 0)
        self.assertEqual({l["id"] for l in table["legends"]}, {"danger-front", "danger-back"})
        self.assertIn("J862", table["parts"])
        self.assertEqual(table["tabs"]["known"]["J102"], "LINE IN")
        ids = [f["id"] for f in table["fixed_texts"]]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
