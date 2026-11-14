#!/usr/bin/env python3
"""The pre-order check against KiCad itself on the pad numbering rule: where KiCad places the pads of a footprint on the back of the board, and the rule's seeded fault.

This is one of the files the check's KiCad tests are divided into by topic; the
shared setup, the seeded-fault proof's pooled outcomes and the exclusion of what
needs that proof are in board_kicad_fixtures.py.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_fixtures  # noqa: E402
import board_prove  # noqa: E402
from board_kicad_fixtures import load_tests, setUpModule  # noqa: E402,F401
from board_kicad_fixtures import KICAD_CLI, Proved, outcomes  # noqa: E402
from test_board_check_pad_numbering import pad, part  # noqa: E402

FAULT = "a footprint numbered clockwise"


class KiCadPlacesTheOwnPadsOfABackFootprintAtItsPosition(unittest.TestCase):
    def test_kicad_itself_places_a_back_footprints_pad_at_the_footprints_position_plus_the_pads_own(self):
        # SOL-PRE-ORDER-CHECK-FAILS-A-FOOTPRINT-NUMBERED-CLOCKWISE.C2: A footprint numbered counter-clockwise passes, on the front and on the back of the board
        # A via takes the net of the pad it stands on, so the net KiCad gives the via at x = 32 names the pad it put there:
        # pad 2, written at x = +2 of a footprint at x = 30, not pad 1 as a mirrored placement would have it.
        back = ('"B.Cu"', '"B.Mask"')
        flat = part("U1", [pad(1, -2, 0, layers=back), pad(2, 2, 0, layers=back)], layer="B.Cu", x=30, y=20)
        via = (f'(via (at 32 20) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net "/NET_9") (uuid {board_fixtures.uuid()}))')
        design = board_fixtures.Design(board_fixtures.layout([flat, via]), board_fixtures.project())
        self.addCleanup(board_fixtures.cleanup)
        report = os.path.join(design.root, "drc.json")
        subprocess.run([KICAD_CLI, "pcb", "drc", "--format", "json", "--severity-all", "--units", "mm", "-o", report,
                        design.board], capture_output=True, check=True)
        with open(report, encoding="utf-8") as handle:
            drc = json.load(handle)
        dangling = [item["description"] for entry in drc["violations"] if entry["type"] == "via_dangling"
                    for item in entry["items"]]
        self.assertEqual(dangling, ["Via [/NET_2] on F.Cu - B.Cu"])


class TheClockwiseFootprintSeedIsCaught(Proved):
    def test_the_seeded_fault_adds_a_clockwise_numbered_part_to_a_copy_of_the_proof_design_and_the_check_catches_it(self):
        # SOL-PRE-ORDER-CHECK-FAILS-A-FOOTPRINT-NUMBERED-CLOCKWISE.C5: The seeded-fault proof holds a design whose footprint is numbered clockwise, and the check catches it
        # OBL-VERIFICATION-DISCIPLINE-001.C9: A check is shown to fail on the defect it exists to catch rather than asserted to be capable of it
        faults = [fault for fault in board_prove.FAULTS if fault[0] == FAULT]
        self.assertEqual(len(faults), 1)
        self.assertEqual(faults[0][2], "pad_numbering")
        self.assertEqual(board_prove.target_of(faults[0]), (board_prove.DESIGN, board_prove.NAME),
                         "seeded into a copy of the throwaway gate proof design")
        caught, evidence = outcomes()[FAULT]
        self.assertTrue(caught, evidence)
        self.assertIn(" | pad_numbering | X3 (Seeded_Part) | ", evidence)
        self.assertIn("hardware/proof/gate-proof/gate-proof.kicad_pro", evidence)


if __name__ == "__main__":
    unittest.main()
