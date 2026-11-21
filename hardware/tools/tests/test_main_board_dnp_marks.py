#!/usr/bin/env python3
"""The committed main board held to the pre-order check's do-not-populate rule, with no KiCad involved.

The board's unfitted parts are read from its own schematic, and the rule is run over the committed layout,
schematic and parts record; a scratch copy with one symbol's mark flipped shows the rule would notice.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
import main_board_fixtures as main_board  # noqa: E402
import sexpr  # noqa: E402


def judge(root, tracked=None):
    """The lines of the do-not-populate rule for the board's design as held under `root`."""
    design = main_board.design()
    with open(os.path.join(root, design.layout), encoding="utf-8") as handle:
        tree = sexpr.parse_one(handle.read())
    return board_check.dnp_agreement(design, tree, board_check.require_yaml(), root,
                                     main_board.repository(root, tracked), False)


class CommittedMainBoard(unittest.TestCase):
    def test_the_committed_board_passes_the_rule_and_a_flipped_symbol_mark_is_reported_naming_the_part(self):
        # SOL-HW-DO-NOT-POPULATE-PARITY-LINES-ARE-LISTED-AND-BOARD-DRIVES-BILL.C2: A part marked do-not-populate on its footprint and not on its symbol, or the reverse, is reported by the check's dnp_agreement rule naming the part, and the committed main board passes that rule, with no footprint_symbol_mismatch line for a part it leaves unfitted in the pre-order check's own run. Out of scope is the check's other parity lines.
        unfitted = main_board.unfitted()
        self.assertTrue(unfitted, "no symbol of the committed board is marked do-not-populate")
        self.assertEqual([v.line() for v in judge(main_board.REPO)], [])
        for reference in sorted(unfitted):
            with self.subTest(reference=reference), tempfile.TemporaryDirectory(prefix="main-board-dnp-") as scratch:
                tracked = main_board.scratch_board(scratch)
                main_board.flip_symbol(scratch, reference)
                found = judge(scratch, tracked)
                self.assertEqual({v.rule for v in found}, {"dnp_agreement"})
                self.assertTrue(all(v.location.split()[0] == reference for v in found), [v.line() for v in found])
                disagreement = [v for v in found if v.location == reference]
                self.assertEqual(len(disagreement), 1, [v.line() for v in found])
                self.assertIn("the layout marks it not populated", disagreement[0].message)
                self.assertIn("the schematic marks it fitted", disagreement[0].message)


if __name__ == "__main__":
    unittest.main()
