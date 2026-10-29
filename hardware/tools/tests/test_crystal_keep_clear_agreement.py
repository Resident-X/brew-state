#!/usr/bin/env python3
"""The method's definition of a part related to the oscillator held against the review proof design's crystal keep-clear.

The proof design's rules table row and its rules file exempt the parts the method's CLOCK-3 counts related to the
oscillator. Nothing else ties the three together, so this reads the method, the row and the rules file as they stand and
fails when they drift apart. It reads only the synthetic proof and the method, and needs no board-design program.
"""

from __future__ import annotations

import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PROOF = os.path.join(REPO, "hardware", "proof", "review-proof")

#: The kinds of part the row's exempt parts are named by, as the row words them.
KINDS = ("load capacitors", "controller", "decoupling capacitor", "regulator")


def read(*parts: str) -> str:
    with open(os.path.join(*parts), encoding="utf-8") as handle:
        return handle.read()


def related_set(method: str) -> str:
    """CLOCK-3's Passes line, which holds its definition of a part related to the oscillator."""
    start = method.index("#### CLOCK-3. ")
    block = method[start:method.index("\n#### ", start + 1)]
    return next(line for line in block.split("\n") if line.startswith("- **Passes:**"))


def row_of(rules_table: str) -> str:
    return next(line for line in rules_table.split("\n") if line.startswith("| Crystal keep-clear |"))


def row_exempt(row: str) -> set:
    return set(re.findall(r"\b[A-Z]+\d+\b", re.search(r"exempting (.*?) \|", row).group(1)))


def row_kinds(row: str) -> list:
    clause = row.split("related to the oscillator:", 1)[1]
    return [kind for kind in KINDS if kind in clause]


def rule_exempt(rules: str) -> set:
    rule = rules[rules.index('(rule "Crystal keep-clear"'):]
    return set(re.findall(r"B\.Reference != '(\w+)'", rule[:rule.index("(constraint")]))


def board_references(board: str) -> set:
    return set(re.findall(r'\(property "Reference" "(\w+)"', board))


def disagreements(method: str, rules_table: str, rules: str, board: str) -> list:
    problems = []
    row = row_of(rules_table)
    named, definition = row_kinds(row), related_set(method)
    if named != list(KINDS):
        problems.append(f"the row names the kinds {named}, not {list(KINDS)}")
    problems += [f"CLOCK-3 lacks the kind {kind}, which the row names" for kind in named if kind not in definition]
    in_row, in_rules = row_exempt(row), rule_exempt(rules)
    problems += [f"{ref} is exempt in the row and not in the rules file" for ref in sorted(in_row - in_rules)]
    problems += [f"{ref} is exempt in the rules file and not in the row" for ref in sorted(in_rules - in_row)]
    problems += [f"{ref} is exempt and is not a footprint on the board" for ref in sorted((in_row | in_rules) - board_references(board))]
    return problems


class TheProofDesignsCrystalKeepClearAgreesWithTheMethod(unittest.TestCase):
    def setUp(self):
        self.method = read(REPO, "docs", "board-design-method.md")
        self.table = read(PROOF, "design-rules.md")
        self.rules = read(PROOF, "review-proof.kicad_dru")
        self.board = read(PROOF, "review-proof.kicad_pcb")

    def test_the_committed_row_rules_file_and_method_agree(self):
        # SOL-LAYOUT-CATALOGUE-CRYSTAL-RELATED-PARTS.C2: a test reads CLOCK-3's related-set text, the row and the rules file as they stand
        self.assertEqual(disagreements(self.method, self.table, self.rules, self.board), [])
        self.assertEqual(row_exempt(row_of(self.table)), {"C5", "C6", "U4", "C4", "U2", "C1", "C2"})

    def test_the_method_keeps_the_25_mm_for_other_parts_and_lists_the_pin_side_kinds(self):
        # SOL-LAYOUT-CATALOGUE-CRYSTAL-RELATED-PARTS.C1: CLOCK-3 names the controller's own pin-side parts as a closed list and keeps 25 mm for every other part
        definition = related_set(self.method)
        for words in ("series resistors on its pins", "pull-up, pull-down and filter parts", "reset network",
                      "boot-mode network", "debug header", "any other crystal or resonator on its oscillator pins",
                      "A test point on a supply net is not pin-side", "Every other part keeps the 25 mm"):
            self.assertIn(words, definition)
        start = self.method.index("#### CLOCK-4. ")
        clock4 = self.method[start:self.method.index("\n#### ", start + 1)]
        self.assertIn("as `CLOCK-3` defines it", clock4)
        self.assertNotIn("series resistors", clock4)
        source = next(line for line in self.method[self.method.index("#### CLOCK-3. "):].split("\n") if line.startswith("- **Source:**"))
        self.assertIn("controller-board-division.md", source)

    def test_a_kind_dropped_from_the_catalogue_copy_is_caught(self):
        # SOL-LAYOUT-CATALOGUE-CRYSTAL-RELATED-PARTS.C2: seeded in-memory copies are caught: a kind dropped from the catalogue copy
        method = self.method.replace("and the regulator that feeds it with the regulator's own capacitors", "and nothing else")
        self.assertIn("CLOCK-3 lacks the kind regulator, which the row names", disagreements(method, self.table, self.rules, self.board))

    def test_an_exemption_added_to_the_rules_file_copy_is_caught(self):
        # SOL-LAYOUT-CATALOGUE-CRYSTAL-RELATED-PARTS.C2: seeded in-memory copies are caught: an exemption added to the rules-file copy
        rules = self.rules.replace("&& B.Reference != 'C2'", "&& B.Reference != 'C2' && B.Reference != 'R1'")
        self.assertEqual(disagreements(self.method, self.table, rules, self.board), ["R1 is exempt in the rules file and not in the row"])

    def test_an_exemption_removed_from_the_rules_file_copy_is_caught(self):
        # SOL-LAYOUT-CATALOGUE-CRYSTAL-RELATED-PARTS.C2: seeded in-memory copies are caught: one removed from it
        rules = self.rules.replace(" && B.Reference != 'C2'", "")
        self.assertEqual(disagreements(self.method, self.table, rules, self.board), ["C2 is exempt in the row and not in the rules file"])

    def test_an_exempt_reference_that_is_not_on_the_board_is_caught(self):
        # SOL-LAYOUT-CATALOGUE-CRYSTAL-RELATED-PARTS.C2: fails when an exempt reference is not a footprint on the proof board
        table = self.table.replace("C1 and C2 |", "C1 and Z9 |")
        rules = self.rules.replace("B.Reference != 'C2'", "B.Reference != 'Z9'")
        self.assertEqual(disagreements(self.method, table, rules, self.board), ["Z9 is exempt and is not a footprint on the board"])


if __name__ == "__main__":
    unittest.main()
