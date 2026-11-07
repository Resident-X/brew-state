#!/usr/bin/env python3
"""The pre-order check against KiCad itself, on the throwaway proof designs, here the owner's workmanship acceptance record.

This is one of the files the check's KiCad tests are divided into by topic; the
shared setup, the seeded-fault proof's pooled outcomes and the exclusion of what
needs that proof are in board_kicad_fixtures.py. What the check makes of each
entry, given the lines it reports, is held on synthetic lines in
test_workmanship_acceptance.py; here a seeded fault makes KiCad and the check's
own measures report real ones.
"""

from __future__ import annotations

import os
import sys

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_prove  # noqa: E402
from board_kicad_fixtures import load_tests, setUpModule  # noqa: E402,F401
from board_kicad_fixtures import KICAD_CLI, Copy, Proved  # noqa: E402
from review_proof_fixtures import ReviewProofCopy  # noqa: E402

entry = board_prove.acceptance_entry


class Accepting(Copy):
    def seed_with(self, *edits):
        for edit in edits:
            edit(self.seed)
        status, lines = self.check()
        return status, lines, [line for line in lines if line.startswith("ACCEPTED | ")], \
            [fields for fields in self.violations(lines)]

    def jog(self):
        return board_prove.reroute("/LV_A", (board_prove.LV_A_ENDS,), [(40, 10), (42, 10), (42.3, 10.3), (45, 10.3)])


class AnAcceptedLineIsToldFromADefect(Accepting):
    def test_the_clean_design_with_a_record_that_accepts_none_passes_and_accepts_nothing(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C5: For each failure of the preceding criteria, a seeded copy of the throwaway proof design carrying that fault fails the check under the named rule, the clean copy passes, and the proof run records each seed as caught. Out of scope is any committed design.
        status, lines, accepted, violations = self.seed_with(board_prove.accepting())
        self.assertEqual((status, accepted, violations), (0, [], []), lines)

    def test_two_lines_of_a_rule_at_a_place_under_a_signed_entry_of_count_two_pass_the_check(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C2: On a synthetic design with three lines of one workmanship rule at one place and a signed entry for that rule and place with a count of three, the check reports an ACCEPTED line naming the rule, the place, the measured figure against the allowed one and the reason, the three lines do not fail the check, and the check exits zero when they are its only lines, in the check's text report, which is its only report. Out of scope is any rule outside the closed set of workmanship and neatness rules the solution names.
        status, lines, accepted, violations = self.seed_with(board_prove.right_angle, board_prove.accepting(entry("track_angle", "/LV_B", 2)))
        self.assertEqual(violations, [], lines)
        self.assertEqual(status, 0, lines)
        self.assertEqual(len(accepted), 2, lines)
        for report in accepted:
            for said in ("workmanship_acceptance", "track_angle", "Track [/LV_B] on F.Cu", "min angle 135.000", "actual 90.000",
                         "a synthetic ground, chosen to exercise the check", "proof-owner", "2026-10-01"):
                self.assertIn(said, report)
        self.assertIn("DESIGN | hardware/proof/gate-proof/gate-proof.kicad_pro | PASS", lines)
        self.assertIn("RESULT | PASS | all 1 designs passed", lines)

    def test_a_line_beyond_the_count_still_fails_the_check(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C3: On the same synthetic design with a fourth line of the entry's rule at its place, with a line of a different workmanship rule, and with a line of the same rule at another place, each of those lines fails the check as before and the three covered lines still pass. Out of scope is the wording of the report.
        status, lines, accepted, violations = self.seed_with(board_prove.right_angle, board_prove.accepting(entry("track_angle", "/LV_B", 1)))
        self.assertEqual(status, 1, lines)
        self.assertEqual(len(accepted), 1, lines)
        self.assertEqual([v[2] for v in violations], ["track_angle"], lines)

    def test_a_line_of_another_rule_or_at_another_place_fails_as_before(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C3: On the same synthetic design with a fourth line of the entry's rule at its place, with a line of a different workmanship rule, and with a line of the same rule at another place, each of those lines fails the check as before and the three covered lines still pass. Out of scope is the wording of the report.
        for name, wrong in (("another rule", entry("track_segment_length", "/LV_B", 2)), ("another place", entry("track_angle", "/LV_A", 2))):
            with self.subTest(entry=name):
                self.setUp()
                status, lines, accepted, violations = self.seed_with(board_prove.right_angle, board_prove.accepting(wrong))
                self.assertEqual((status, accepted), (1, []), lines)
                self.assertEqual(sorted(v[2] for v in violations), ["track_angle", "track_angle", "workmanship_acceptance"], lines)

    def test_a_line_of_a_second_rule_under_its_own_entry_passes_the_design(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C2: On a synthetic design with three lines of one workmanship rule at one place and a signed entry for that rule and place with a count of three, the check reports an ACCEPTED line naming the rule, the place, the measured figure against the allowed one and the reason, the three lines do not fail the check, and the check exits zero when they are its only lines, in the check's text report, which is its only report. Out of scope is any rule outside the closed set of workmanship and neatness rules the solution names.
        # The short jog on /LV_A is reported as one track_segment_length line, which an entry for that rule at that place covers.
        status, lines, accepted, violations = self.seed_with(self.jog(), board_prove.accepting(entry("track_segment_length", "/LV_A", 1)))
        self.assertEqual((status, violations), (0, []), lines)
        self.assertEqual(len(accepted), 1, lines)
        self.setUp()
        status, lines, accepted, violations = self.seed_with(self.jog(), board_prove.accepting(entry("track_angle", "/LV_A", 1)))
        self.assertEqual((status, accepted), (1, []), lines)
        self.assertEqual(sorted(v[2] for v in violations), ["track_segment_length", "workmanship_acceptance"], lines)


class TheFloorplanRegionsRuleIsAcceptedAndTheCrystalKeepClearIsNot(ReviewProofCopy):
    def test_a_part_outside_its_region_is_accepted_and_the_crystal_keep_clear_line_beside_it_still_fails(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C4: On a synthetic design, an entry with an empty, placeholder or angle-bracketed accepted-by value, an entry with an empty, malformed or future date, an entry naming a rule outside the closed set the leaf states (each of hole_to_hole, workmanship_rule, workmanship_figure and workmanship_pad_copper, and any rule that is not a workmanship or neatness rule), a courtyards_overlap entry used by a line that names a custom rule such as the crystal keep-clear, an items_not_allowed entry used by a line that names a rule other than the floorplan region rule, an entry naming a mains spacing, derated-voltage or pin-limit rule, an entry for a place the design does not have, and an entry that no line uses each fail the check naming the entry, and a design marked synthetic is honoured only when it is marked not for manufacture. On the same design an entry for each rule of the closed set, signed and used by a line of that rule, is accepted. Out of scope is a well-formed signed entry that a line uses.
        board_prove.region_crowded(self.seed)
        board_prove.accepting(entry("items_not_allowed", "D1"), entry("courtyards_overlap", "D1"))(self.seed)
        status, lines, stderr = board_prove.check(self.seed, KICAD_CLI)
        self.assertEqual(status, 1, stderr)
        violations = [line.split(" | ") for line in lines if line.startswith("VIOLATION | ")]
        accepted = [line for line in lines if line.startswith("ACCEPTED | ")]
        self.assertEqual(len(accepted), 1, lines)
        self.assertIn("items_not_allowed at Footprint D1", accepted[0])
        self.assertIn("rule 'Digital region parts'", accepted[0])
        self.assertNotIn("items_not_allowed", [v[2] for v in violations])
        crystal = [v for v in violations if v[2] == "courtyards_overlap"]
        self.assertEqual(len(crystal), 1, violations)
        self.assertIn("rule 'Crystal keep-clear'", crystal[0][4])
        stale = [v for v in violations if v[2] == "workmanship_acceptance"]
        self.assertEqual(len(stale), 1, violations)
        self.assertIn("accepted_workmanship[1] (courtyards_overlap at D1) is used by no line", stale[0][4])


class EachNewFailureIsCaughtOnASeededFault(Proved):
    def test_every_acceptance_failure_fails_on_its_seeded_fault_and_the_clean_design_passes(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C5: For each failure of the preceding criteria, a seeded copy of the throwaway proof design carrying that fault fails the check under the named rule, the clean copy passes, and the proof run records each seed as caught. Out of scope is any committed design.
        faults = [fault[0] for fault in board_prove.FAULTS if fault[1].startswith("workmanship acceptance:")]
        # five of C1, three of C3 and twenty-one of C4: each named failure has its own seed
        self.assertEqual(len(faults), 29)
        self.assertCaught(*faults)
        rules = {fault[2] for fault in board_prove.FAULTS if fault[1].startswith("workmanship acceptance:")}
        self.assertGreaterEqual(rules, {"workmanship_acceptance", "track_angle", "courtyards_overlap", "items_not_allowed"})


if __name__ == "__main__":
    import unittest
    unittest.main()
