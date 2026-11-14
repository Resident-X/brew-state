#!/usr/bin/env python3
"""The pre-order check against KiCad itself on the do-not-populate rule: the rule's seeded fault.

This is one of the files the check's KiCad tests are divided into by topic; the
shared setup, the seeded-fault proof's pooled outcomes and the exclusion of what
needs that proof are in board_kicad_fixtures.py.
"""

from __future__ import annotations

import os
import sys
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_prove  # noqa: E402
from board_kicad_fixtures import load_tests, setUpModule  # noqa: E402,F401
from board_kicad_fixtures import Proved, outcomes  # noqa: E402

FAULT = "a part the layout marks do not populate and the schematic leaves fitted"


class TheDoNotPopulateDisagreementSeedIsCaught(Proved):
    def test_the_seeded_fault_marks_a_part_do_not_populate_in_the_layout_only_in_a_copy_of_the_proof_design_and_the_check_catches_it(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-DO-NOT-POPULATE-TO-ONE-ANSWER.C6: The seeded-fault proof holds a design whose schematic and layout disagree on do-not-populate, and the check catches it
        # OBL-VERIFICATION-DISCIPLINE-001.C9: A check is shown to fail on the defect it exists to catch rather than asserted to be capable of it
        faults = [fault for fault in board_prove.FAULTS if fault[0] == FAULT]
        self.assertEqual(len(faults), 1)
        self.assertEqual(faults[0][2], "dnp_agreement")
        self.assertEqual(board_prove.target_of(faults[0]), (board_prove.DESIGN, board_prove.NAME),
                         "seeded into a copy of the throwaway gate proof design")
        caught, evidence = outcomes()[FAULT]
        self.assertTrue(caught, evidence)
        self.assertIn(" | dnp_agreement | R2 | ", evidence)
        self.assertIn("hardware/proof/gate-proof/gate-proof.kicad_pro", evidence)


if __name__ == "__main__":
    unittest.main()
