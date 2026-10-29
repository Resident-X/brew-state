#!/usr/bin/env python3
"""The method's definition of a part related to the oscillator held against the review proof design's crystal keep-clear.

The proof design's rules table row and its rules file exempt the parts the method's CLOCK-3 counts related to the
oscillator. Nothing else ties the three together, so this reads the method, the row and the rules file as they stand and
fails when they drift apart. It also holds the distance CLOCK-3 and CLOCK-4 state, the board check's floor and the proof
rule's minimum in agreement. It reads only the synthetic proof, the method and the check's source, and needs no
board-design program.
"""

from __future__ import annotations

import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PROOF = os.path.join(REPO, "hardware", "proof", "review-proof")

#: The kinds of part the row's exempt parts are named by, as the row words them.
KINDS = ("load capacitors", "controller", "decoupling capacitor", "regulator")

#: The clause of CLOCK-3's definition that counts each kind related, as that definition words it, so one can be missing alone.
CLAUSES = {
    "load capacitors": "one of its load capacitors",
    "controller": "the controller whose oscillator pins it joins",
    "decoupling capacitor": "its decoupling capacitors",
    "regulator": "the regulator that feeds it with the regulator's own capacitors",
}

#: The clause counting the oscillator's own parts related, which the row names no kind for.
CRYSTAL_CLAUSE = "the crystal or ceramic resonator"

NUMBER = r"(\d+(?:\.\d+)?)"

#: Where CLOCK-3 states its distance, in its Passes and Fails lines, as that item words it.
CLOCK3_FIGURES = (rf"within {NUMBER} mm of the crystal", rf"keeps the {NUMBER} mm")

#: Where CLOCK-4 states its distance, outside its Source line, as that item words it.
CLOCK4_FIGURES = (rf"keep {NUMBER} mm from the crystal's courtyard", rf"at least {NUMBER} mm from the crystal",
                  rf"\(min {NUMBER}mm\)", rf"CLOCK-3`'s {NUMBER} mm", rf"below {NUMBER} mm")


def read(*parts: str) -> str:
    with open(os.path.join(*parts), encoding="utf-8") as handle:
        return handle.read()


def related_set(method: str) -> str:
    """CLOCK-3's Passes line, which holds its definition of a part related to the oscillator."""
    start = method.index("#### CLOCK-3. ")
    block = method[start:method.index("\n#### ", start + 1)]
    return next(line for line in block.split("\n") if line.startswith("- **Passes:**"))


def item_block(method: str, item: str) -> str:
    start = method.index(f"#### {item}. ")
    return method[start:method.index("\n#### ", start + 1)]


def stated_figures(method: str, item: str, patterns: tuple) -> list:
    """Every distance the item states by the given wordings, in its lines other than its Source; each wording must state one."""
    lines = [line for line in item_block(method, item).split("\n") if not line.startswith("- **Source:**")]
    text = "\n".join(lines)
    found = []
    for pattern in patterns:
        figures = re.findall(pattern, text)
        assert figures, f"{item} does not state its distance as {pattern!r}"
        found += [float(figure) for figure in figures]
    return found


def check_floor(check_source: str) -> float:
    return float(re.search(rf"^KEEP_CLEAR_MM = {NUMBER}$", check_source, re.M).group(1))


def rule_minimum(rules: str) -> float:
    rule = rules[rules.index('(rule "Crystal keep-clear"'):]
    return float(re.search(rf"courtyard_clearance \(min {NUMBER}mm\)", rule).group(1))


def figure_disagreements(method: str, check_source: str, rules: str) -> list:
    problems = []
    clock3 = set(stated_figures(method, "CLOCK-3", CLOCK3_FIGURES))
    clock4 = set(stated_figures(method, "CLOCK-4", CLOCK4_FIGURES))
    floor = check_floor(check_source)
    if len(clock3) != 1:
        problems.append(f"CLOCK-3 states more than one distance: {sorted(clock3)}")
    if len(clock4) != 1:
        problems.append(f"CLOCK-4 states more than one distance: {sorted(clock4)}")
    if clock3 != clock4 or clock3 != {floor}:
        problems.append(f"CLOCK-3 states {sorted(clock3)}, CLOCK-4 {sorted(clock4)} and the check's floor is {floor}")
    if rule_minimum(rules) < floor:
        problems.append(f"the proof rule's minimum {rule_minimum(rules)} is below the floor {floor}")
    return problems


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
    problems += [f"CLOCK-3 lacks the kind {kind}, which the row names" for kind in named if CLAUSES[kind] not in definition]
    if CRYSTAL_CLAUSE not in definition:
        problems.append(f"CLOCK-3 lacks the clause {CRYSTAL_CLAUSE}")
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
        self.check = read(REPO, "hardware", "tools", "board_check.py")

    def test_the_committed_row_rules_file_and_method_agree(self):
        # SOL-LAYOUT-CATALOGUE-CRYSTAL-RELATED-PARTS.C2: The proof design's crystal keep-clear row and rule agree with the catalogue, and a test holds the two together
        self.assertEqual(disagreements(self.method, self.table, self.rules, self.board), [])
        self.assertEqual(row_exempt(row_of(self.table)), {"C5", "C6", "U4", "C4", "U2", "C1", "C2"})

    def test_the_method_keeps_the_stated_distance_for_other_parts_and_lists_the_pin_side_kinds(self):
        # SOL-LAYOUT-CATALOGUE-CRYSTAL-KEEP-CLEAR-10MM.C3: A test holds the method's figure, the check's floor and the proof design's rule in agreement
        definition = related_set(self.method)
        for words in ("series resistors on its pins", "pull-up, pull-down and filter parts", "reset network",
                      "boot-mode network", "debug header", "any other crystal or resonator on its oscillator pins",
                      "A test point on a supply net is not pin-side", "Every other part keeps the 10 mm"):
            self.assertIn(words, definition)
        start = self.method.index("#### CLOCK-4. ")
        clock4 = self.method[start:self.method.index("\n#### ", start + 1)]
        self.assertIn("as `CLOCK-3` defines it", clock4)
        self.assertNotIn("series resistors", clock4)
        source = next(line for line in self.method[self.method.index("#### CLOCK-3. "):].split("\n") if line.startswith("- **Source:**"))
        self.assertIn("controller-board-division.md", source)

    def test_each_kind_dropped_from_the_catalogue_copy_is_caught(self):
        # SOL-LAYOUT-CATALOGUE-CRYSTAL-RELATED-PARTS.C2: The proof design's crystal keep-clear row and rule agree with the catalogue, and a test holds the two together
        for kind, clause in CLAUSES.items():
            with self.subTest(kind=kind):
                self.assertEqual(self.method.count(clause), 1)
                method = self.method.replace(clause, "nothing else")
                self.assertEqual(disagreements(method, self.table, self.rules, self.board),
                                 [f"CLOCK-3 lacks the kind {kind}, which the row names"])

    def test_the_crystal_clause_dropped_from_the_catalogue_copy_is_caught(self):
        # SOL-LAYOUT-CATALOGUE-CRYSTAL-RELATED-PARTS.C2: The proof design's crystal keep-clear row and rule agree with the catalogue, and a test holds the two together
        self.assertEqual(self.method.count(CRYSTAL_CLAUSE), 1)
        method = self.method.replace(CRYSTAL_CLAUSE, "nothing else")
        self.assertEqual(disagreements(method, self.table, self.rules, self.board), [f"CLOCK-3 lacks the clause {CRYSTAL_CLAUSE}"])

    def test_an_exemption_added_to_the_rules_file_copy_is_caught(self):
        # SOL-LAYOUT-CATALOGUE-CRYSTAL-RELATED-PARTS.C2: The proof design's crystal keep-clear row and rule agree with the catalogue, and a test holds the two together
        rules = self.rules.replace("&& B.Reference != 'C2'", "&& B.Reference != 'C2' && B.Reference != 'R1'")
        self.assertEqual(disagreements(self.method, self.table, rules, self.board), ["R1 is exempt in the rules file and not in the row"])

    def test_an_exemption_removed_from_the_rules_file_copy_is_caught(self):
        # SOL-LAYOUT-CATALOGUE-CRYSTAL-RELATED-PARTS.C2: The proof design's crystal keep-clear row and rule agree with the catalogue, and a test holds the two together
        rules = self.rules.replace(" && B.Reference != 'C2'", "")
        self.assertEqual(disagreements(self.method, self.table, rules, self.board), ["C2 is exempt in the row and not in the rules file"])

    def test_an_exempt_reference_that_is_not_on_the_board_is_caught(self):
        # SOL-LAYOUT-CATALOGUE-CRYSTAL-RELATED-PARTS.C2: The proof design's crystal keep-clear row and rule agree with the catalogue, and a test holds the two together
        table = self.table.replace("C1 and C2 |", "C1 and Z9 |")
        rules = self.rules.replace("B.Reference != 'C2'", "B.Reference != 'Z9'")
        self.assertEqual(disagreements(self.method, table, rules, self.board), ["Z9 is exempt and is not a footprint on the board"])

    def test_the_method_the_check_and_the_proof_rule_state_one_distance(self):
        # SOL-LAYOUT-CATALOGUE-CRYSTAL-KEEP-CLEAR-10MM.C3: A test holds the method's figure, the check's floor and the proof design's rule in agreement
        self.assertEqual(figure_disagreements(self.method, self.check, self.rules), [])
        floor = check_floor(self.check)
        self.assertEqual(set(stated_figures(self.method, "CLOCK-3", CLOCK3_FIGURES)), {floor})
        self.assertEqual(set(stated_figures(self.method, "CLOCK-4", CLOCK4_FIGURES)), {floor})
        self.assertGreaterEqual(rule_minimum(self.rules), floor)

    def test_a_clock_3_copy_with_a_different_figure_is_caught(self):
        # SOL-LAYOUT-CATALOGUE-CRYSTAL-KEEP-CLEAR-10MM.C3: A test holds the method's figure, the check's floor and the proof design's rule in agreement
        floor = check_floor(self.check)
        block = item_block(self.method, "CLOCK-3")
        other = re.sub(CLOCK3_FIGURES[0], lambda m: f"within {floor + 1:g} mm of the crystal", block)
        self.assertNotEqual(other, block)
        problems = figure_disagreements(self.method.replace(block, other), self.check, self.rules)
        self.assertEqual(len(problems), 2)
        self.assertTrue(problems[0].startswith("CLOCK-3 states more than one distance"))
        self.assertTrue(problems[1].startswith("CLOCK-3 states"))

    def test_a_clock_4_copy_with_a_different_figure_is_caught(self):
        # SOL-LAYOUT-CATALOGUE-CRYSTAL-KEEP-CLEAR-10MM.C3: A test holds the method's figure, the check's floor and the proof design's rule in agreement
        floor = check_floor(self.check)
        block = item_block(self.method, "CLOCK-4")
        other = re.sub(r"\(min [\d.]+mm\)", f"(min {floor + 1:g}mm)", block)
        self.assertNotEqual(other, block)
        problems = figure_disagreements(self.method.replace(block, other), self.check, self.rules)
        self.assertEqual(len(problems), 2)
        self.assertTrue(problems[0].startswith("CLOCK-4 states more than one distance"))

    def test_a_check_floor_that_differs_from_the_method_is_caught(self):
        # SOL-LAYOUT-CATALOGUE-CRYSTAL-KEEP-CLEAR-10MM.C3: A test holds the method's figure, the check's floor and the proof design's rule in agreement
        floor = check_floor(self.check)
        check = self.check.replace(f"KEEP_CLEAR_MM = {floor}", f"KEEP_CLEAR_MM = {floor + 1}")
        problems = figure_disagreements(self.method, check, self.rules)
        self.assertEqual(len(problems), 1)
        self.assertIn("the check's floor is", problems[0])

    def test_a_proof_rule_copy_with_a_minimum_below_the_floor_is_caught(self):
        # SOL-LAYOUT-CATALOGUE-CRYSTAL-KEEP-CLEAR-10MM.C3: A test holds the method's figure, the check's floor and the proof design's rule in agreement
        floor = check_floor(self.check)
        rules = re.sub(r"(courtyard_clearance \(min )[\d.]+mm", lambda m: f"{m.group(1)}{floor / 2:g}mm", self.rules)
        self.assertNotEqual(rules, self.rules)
        problems = figure_disagreements(self.method, self.check, rules)
        self.assertEqual(len(problems), 1)
        self.assertIn("is below the floor", problems[0])

    def test_a_clause_dropped_from_a_clock_item_is_caught(self):
        # SOL-LAYOUT-CATALOGUE-CRYSTAL-KEEP-CLEAR-10MM.C3: A test holds the method's figure, the check's floor and the proof design's rule in agreement
        block = item_block(self.method, "CLOCK-3")
        self.assertEqual(block.count("keeps the"), 1)
        method = self.method.replace(block, block.replace("keeps the", "holds the"))
        with self.assertRaises(AssertionError):
            figure_disagreements(method, self.check, self.rules)


if __name__ == "__main__":
    unittest.main()
