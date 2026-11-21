#!/usr/bin/env python3
"""One answer to "is this position numbered" at every public entry, driven with uncooperative catalogue numbers.

A number that is blank, only whitespace, not text, or `none` in any case is no catalogue number: the assembler is refused on
such a position, naming it, and `none` or the owner is allowed. Synthetic files only.
"""

from __future__ import annotations

import io
import json
import os
import sys
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
import production_files  # noqa: E402
import test_production_files_sets as sets  # noqa: E402

UNNUMBERED = ["", "   ", "None", "NONE", " none ", "nOnE"]
ASSEMBLER_NEEDS = "assembler but it has no catalogue number"


class Numbered(unittest.TestCase):
    def test_the_one_function_answers_for_every_spelling(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C7: The parts specification records for every part whether the assembler or the owner fits it
        for number in UNNUMBERED + [None, 12, 1.5, ["C1"], {}]:
            self.assertFalse(board_check.is_numbered(number), repr(number))
            self.assertIn(ASSEMBLER_NEEDS, board_check.fitter_problem("assembler", number) or "", repr(number))
            self.assertIsNone(board_check.fitter_problem("none", number), repr(number))
            self.assertIsNone(board_check.fitter_problem("owner", number), repr(number))
        for number in ("C100", " C100 ", "nonesuch"):
            self.assertTrue(board_check.is_numbered(number), repr(number))
            self.assertIn("fitted_by is none but", board_check.fitter_problem("none", number) or "")
            self.assertIsNone(board_check.fitter_problem("assembler", number))

    def test_a_comment_with_a_control_or_separator_character_is_refused(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C6: Each board's parts list gives one comment for each catalogue number
        for bad in ("a\tb", "a b", "a b", "a\x0bb", "a\x0cb", "a\x85b", "a\x00b", "a\x7fb", "a​b", "a\nb", "a\rb"):
            self.assertIn("control or separator", board_check.comment_problem(bad) or "", repr(bad))
        for good in ("resistor 10 kohm", 'say "hi"', "10 µF"):
            self.assertIsNone(board_check.comment_problem(good), repr(good))


class Placement(sets.Synthetic):
    def with_m1(self, board_number, record_number, fitter="assembler"):
        text = open(self.board, encoding="utf-8").read().replace('(property "LCSC" "none")', f'(property "LCSC" "{board_number}")')
        sets.write(self.board, text)
        sets.write(self.record, sets.record_text([
            ("U1", "C0001", {"fitted_by": "assembler"}), ("R1", "C0002", {"fitted_by": "assembler"}),
            ("C1", "C0003", {"fitted_by": "assembler"}), ("J1", "C0004", {"fitted_by": "assembler"}),
            ("X1", "C0002", {"fitted_by": "owner"}), ("M1", json.dumps(record_number), {"fitted_by": fitter})]))

    def test_an_unnumbered_position_the_assembler_is_to_fit_is_refused_naming_it_in_text_and_json(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C7: The parts specification records for every part whether the assembler or the owner fits it
        for number in UNNUMBERED:
            for fmt in ("text", "json"):
                self.setUp()
                self.with_m1(number, number)
                status, lines, folder = self.place(fmt=fmt)
                shown = "\n".join(lines)
                self.assertEqual(status, 1, (number, shown))
                self.assertIn("M1", shown)
                self.assertIn(ASSEMBLER_NEEDS, shown, (number, fmt))
                self.assertFalse(os.path.exists(folder))
                if fmt == "json":
                    self.assertEqual(json.loads(shown)["result"], "REFUSED")

    def test_an_unnumbered_position_stated_none_or_owner_is_allowed_in_any_spelling(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C7: The parts specification records for every part whether the assembler or the owner fits it
        for number in ("None", "NONE", "none"):
            for fitter in ("none", "owner"):
                self.setUp()
                self.with_m1(number, number, fitter)
                status, lines, _ = self.place()
                self.assertEqual(status, 0, (number, fitter, lines))

    def test_fetch_footprints_selects_no_unnumbered_position_in_any_spelling(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C2: The assembler's footprints are fetched once for each catalogue number; only the assembler-fitted parts' numbers are fetched
        service = json.dumps({"result": {"packageDetail": {"dataStr": {"head": {"x": 4000, "y": 3000},
                                                                       "shape": ["PAD~RECT~4002.966~3000~3~3~1~~2~0~"]}}}})
        for number in ("None", "NONE", "   ", ""):
            self.setUp()
            self.with_m1(number, number)
            calls = []
            stream = io.StringIO()
            status = production_files.fetch_footprints(self.board, os.path.join(self.work, "f"), self.record, 0, "json", stream,
                                                       lambda n: calls.append(n) or service, lambda s: None)
            self.assertEqual((status, calls), (0, ["C0001", "C0002", "C0003", "C0004"]), (number, stream.getvalue()))


class PartsList(sets.TheParts):
    def test_an_unnumbered_assembler_position_is_refused_naming_it_in_text_and_json(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C6: Each board's parts list gives one comment for each catalogue number
        for number in ("None", "NONE", " none "):
            self.setUp()
            sets.write(self.board, open(self.board, encoding="utf-8").read().replace('(property "LCSC" "none")', f'(property "LCSC" "{number}")'))
            sets.write(self.record, sets.record_text([
                ("U1", "C0001", {"fitted_by": "assembler"}), ("R1", "C0002", {"fitted_by": "assembler"}),
                ("C1", "C0003", {"fitted_by": "assembler"}), ("J1", "C0004", {"fitted_by": "assembler"}),
                ("X1", "C0002", {"fitted_by": "assembler"}), ("M1", json.dumps(number), {"fitted_by": "assembler"})]))
            symbols = self.clean()[:-1] + [("M1", "shield", number, "")]
            for fmt in ("text", "json"):
                status, lines, folder = self.list(symbols, fmt=fmt)
                shown = "\n".join(lines)
                self.assertEqual(status, 1, (number, shown))
                self.assertIn("M1", shown)
                self.assertIn("no catalogue number", shown)
                self.assertFalse(os.path.exists(folder))


if __name__ == "__main__":
    unittest.main()
