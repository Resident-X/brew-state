#!/usr/bin/env python3
"""The rules text of the mounting-hole and sensing passes holds no creepage constraint, driven with no KiCad involved.

without_creepage is what the two passes apply to the whole rules text they
write. What is under test is which constraints it takes out, that it takes out
only those, and that anything it does not recognise stays, since a creepage
constraint left in only makes a pass slower and one wrongly kept out of a
rule could never hide a finding the passes read. The passes run against KiCad,
on a design with a creepage shortfall, are in test_board_check_kicad_creepage_once.py.
"""

from __future__ import annotations

import os
import re
import sys
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402

SIGNED = board_check.appended_rules((3.0, 6.0), "nonce", "/N")

DESIGN_RULES = (
    "(version 1)\n"
    "# a comment with a bracket ( and (constraint creepage (min 1mm))\n"
    '(rule "Mains separation"\n'
    "\t(condition \"A.hasNetclass('Mains') && !B.hasNetclass('Mains')\")\n"
    "\t(constraint clearance (min 3mm))\n"
    "\t(constraint creepage (min 10mm)))\n"
)


class WithoutCreepage(unittest.TestCase):
    def test_a_creepage_constraint_is_taken_out_and_the_clearance_beside_it_stays_in_the_same_rule(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C2: The rules the mounting-hole pass and the sensing pass hand the rule engine hold no creepage constraint
        out = board_check.without_creepage(DESIGN_RULES)
        self.assertNotIn("creepage (min 10mm)", out)
        self.assertIn("(constraint clearance (min 3mm))", out)
        self.assertIn('(rule "Mains separation"', out)
        self.assertTrue(out.startswith("(version 1)\n"))

    def test_the_rule_the_check_writes_for_the_signed_separation_keeps_its_clearance_and_loses_its_creepage(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C2: The rules the mounting-hole pass and the sensing pass hand the rule engine hold no creepage constraint
        self.assertIn("(constraint creepage (min 6mm))", SIGNED)
        out = board_check.without_creepage(SIGNED)
        self.assertNotIn("creepage", out)
        self.assertIn(f'(rule "{board_check.SIGNED_RULE}"', out)
        self.assertIn("(constraint clearance (min 3mm))", out)
        self.assertIn(f'(rule "{board_check.marker_rule("nonce")}"', out)

    def test_a_rule_left_with_no_constraint_is_dropped_whole_for_KiCad_refuses_a_rule_with_none(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C2: The rules the mounting-hole pass and the sensing pass hand the rule engine hold no creepage constraint
        text = ('(version 1)\n(rule "only creepage"\n\t(condition "A.Type == \'Pad\'")\n\t(constraint creepage (min 5mm)))\n'
                '(rule "kept"\n\t(constraint clearance (min 1mm)))\n')
        out = board_check.without_creepage(text)
        self.assertEqual(out, '(version 1)\n(rule "kept"\n\t(constraint clearance (min 1mm)))\n')

    def test_a_rule_that_held_no_constraint_before_is_left_as_written(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C2: The rules the mounting-hole pass and the sensing pass hand the rule engine hold no creepage constraint
        text = '(version 1)\n(rule "odd"\n\t(condition "A.Type == \'Pad\'"))\n'
        self.assertEqual(board_check.without_creepage(text), text)

    def test_every_form_of_the_figures_the_check_reads_is_taken_out_whatever_the_spacing(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C2: The rules the mounting-hole pass and the sensing pass hand the rule engine hold no creepage constraint
        for form in ("(constraint creepage (min 4mm))", "(constraint  creepage  (min  4.5mm ) )", "( constraint creepage (opt 4mm))",
                     "(constraint creepage (min 4mm) (opt 5mm))", "(constraint CREEPAGE (max 4mm))"):
            with self.subTest(form=form):
                text = f'(rule "r"\n\t(constraint clearance (min 1mm))\n\t{form})\n'
                out = board_check.without_creepage(text)
                self.assertNotIn("creepage", out.lower())
                self.assertIn("(constraint clearance (min 1mm))", out)

    def test_a_creepage_constraint_in_a_form_it_does_not_recognise_stays_in(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C2: The rules the mounting-hole pass and the sensing pass hand the rule engine hold no creepage constraint
        for form in ("(constraint creepage (foo 4mm))", "(constraint creepage 4mm)", "(constraint creepage)",
                     "(constraint creepage (min 4mm) extra)", '(constraint creepage (min "4mm"))'):
            with self.subTest(form=form):
                text = f'(version 1)\n(rule "r"\n\t(constraint clearance (min 1mm))\n\t{form})\n'
                self.assertEqual(board_check.without_creepage(text), text)

    def test_a_rule_whose_only_constraint_is_an_unrecognised_creepage_form_is_not_dropped(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C2: The rules the mounting-hole pass and the sensing pass hand the rule engine hold no creepage constraint
        text = '(rule "r"\n\t(constraint creepage (foo 4mm)))\n'
        self.assertEqual(board_check.without_creepage(text), text)

    def test_text_that_does_not_balance_is_returned_unchanged(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C2: The rules the mounting-hole pass and the sensing pass hand the rule engine hold no creepage constraint
        for text in ('(rule "r"\n\t(constraint creepage (min 4mm))\n', '(rule "r")\n)\n(rule "s" (constraint creepage (min 4mm)))\n',
                     '(rule "r" (condition "unterminated)\n\t(constraint creepage (min 4mm)))\n'):
            with self.subTest(text=text):
                self.assertEqual(board_check.without_creepage(text), text)

    def test_a_creepage_constraint_written_inside_a_string_or_a_comment_is_not_a_constraint(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C2: The rules the mounting-hole pass and the sensing pass hand the rule engine hold no creepage constraint
        text = ('# (rule "x" (constraint creepage (min 4mm)))\n(rule "(constraint creepage (min 4mm))"\n'
                "\t(condition \"A.Name == '(constraint creepage (min 4mm))'\")\n\t(constraint clearance (min 1mm)))\n")
        self.assertEqual(board_check.without_creepage(text), text)

    def test_the_clearance_constraints_and_the_order_of_the_rules_are_untouched(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C2: The rules the mounting-hole pass and the sensing pass hand the rule engine hold no creepage constraint
        signed = (3.0, 6.0)
        text = DESIGN_RULES + "(rule \"ahead\"\n\t(constraint clearance (min 0.5mm)))\n" + board_check.appended_rules(signed, "nonce", "/N")
        out = board_check.without_creepage(text)
        order = lambda rules: [line for line in rules.splitlines() if line.startswith("(rule")]
        self.assertEqual(order(out), order(text))
        clearances = lambda rules: re.findall(r"\(constraint clearance \(min [0-9.]+mm\)\)", rules)
        self.assertEqual(clearances(out), clearances(text))
        self.assertEqual([line for line in out.splitlines() if "creepage" in line and not line.startswith("#")], [])

    def test_taking_creepage_out_twice_changes_nothing_the_second_time(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C2: The rules the mounting-hole pass and the sensing pass hand the rule engine hold no creepage constraint
        once = board_check.without_creepage(DESIGN_RULES + SIGNED)
        self.assertEqual(board_check.without_creepage(once), once)

    def test_text_with_no_creepage_is_returned_unchanged(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C2: The rules the mounting-hole pass and the sensing pass hand the rule engine hold no creepage constraint
        for text in ("", "(version 1)\n", board_check.hole_rules(4.0)):
            self.assertEqual(board_check.without_creepage(text), text)


if __name__ == "__main__":
    unittest.main()
