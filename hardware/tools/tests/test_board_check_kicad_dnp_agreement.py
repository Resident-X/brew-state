#!/usr/bin/env python3
"""The pre-order check against KiCad itself on the do-not-populate rule: the rule's seeded fault.

This is one of the files the check's KiCad tests are divided into by topic; the
shared setup, the seeded-fault proof's pooled outcomes and the exclusion of what
needs that proof are in board_kicad_fixtures.py.
"""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
import tempfile
import unittest
import sys

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_prove  # noqa: E402
import production_seed  # noqa: E402
from board_kicad_fixtures import load_tests, setUpModule  # noqa: E402,F401
from board_kicad_fixtures import KICAD_CLI, Proved, outcomes  # noqa: E402

FAULT = "a part the layout marks do not populate and the schematic leaves fitted"


PROOF_DESIGN = os.path.join(os.path.dirname(TOOLS), "proof", "gate-proof")


def symbol_block(text, reference):
    """The start and end of the one placed-symbol block whose Reference property is `reference`."""
    marker = f'(property "Reference" "{reference}"'
    assert text.count(marker) == 1, reference
    at = text.index(marker)
    start = text.rindex("\n\t(symbol\n", 0, at)
    end = text.index("\n\t)\n", at)
    return start, end


class KiCadsPartsListReadsTheSymbolAttributeAndNotATextField(unittest.TestCase):
    def test_the_ordering_steps_parts_list_leaves_out_a_symbol_marked_by_attribute_and_keeps_one_marked_only_by_a_text_field(self):
        # SOL-HW-DO-NOT-POPULATE-PARITY-LINES-ARE-LISTED-AND-BOARD-DRIVES-BILL.C1: On a synthetic schematic with one symbol marked do-not-populate by attribute and one fitted, the parts list the production seed builds lists no row for the marked part and lists the fitted one. Out of scope is a symbol marked only by a text field, which the parts list does not read.
        # SOL-PRE-ORDER-CHECK-HOLDS-DO-NOT-POPULATE-TO-ONE-ANSWER.C3: A schematic symbol whose text field says do-not-populate while its attribute says fitted fails the design
        with tempfile.TemporaryDirectory(prefix="dnp-bom-") as scratch:
            design = os.path.join(scratch, "gate-proof")
            shutil.copytree(PROOF_DESIGN, design)
            schematic = os.path.join(design, "gate-proof.kicad_sch")
            with open(schematic, encoding="utf-8") as handle:
                text = handle.read()
            start, end = symbol_block(text, "R1")
            block = text[start:end]
            self.assertEqual(block.count("(dnp no)"), 1)
            text = text[:start] + block.replace("(dnp no)", "(dnp yes)") + text[end:]
            start, end = symbol_block(text, "R2")
            block = text[start:end]
            self.assertEqual(block.count("(dnp no)"), 1)
            field = '\n\t\t(property "dnp" "true"\n\t\t\t(at 0 0 0)\n\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)'
            anchor = block.index('\n\t\t(property "Reference" "R2"')
            text = text[:start] + block[:anchor] + field + block[anchor:] + text[end:]
            with open(schematic, "w", encoding="utf-8") as handle:
                handle.write(text)
            parts = os.path.join(scratch, "parts.csv")
            result = subprocess.run([KICAD_CLI] + production_seed.command(production_seed.PARTS_COMMAND, parts_list=parts,
                                                                          schematic=schematic),
                                    capture_output=True, text=True, cwd=design, timeout=300)
            self.assertEqual(result.returncode, 0, result.stderr)
            with open(parts, encoding="utf-8", newline="") as handle:
                listed = {reference.strip() for row in csv.DictReader(handle)
                          for reference in row["Designator"].split(",")}
            self.assertNotIn("R1", listed, "a symbol whose attribute says do not populate is left out")
            self.assertIn("R2", listed, "a symbol marked only by a text field named dnp is listed as fitted")


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
