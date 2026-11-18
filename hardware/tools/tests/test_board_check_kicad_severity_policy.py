#!/usr/bin/env python3
"""The pre-order check against KiCad itself, on the throwaway proof design, here the owner's severity policy.

This is one of the files the check's KiCad tests are divided into by topic; the
shared setup, the seeded-fault proof's pooled outcomes and the exclusion of what
needs that proof are in board_kicad_fixtures.py. What the check makes of each
entry, given the lines it reports, is held on synthetic lines in
test_severity_policy.py; here a seeded fault makes KiCad and the check's own
measures report real ones, and the text report of a design that passes on
warnings is read as the check prints it.
"""

from __future__ import annotations

import os
import sys

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_prove  # noqa: E402
from board_kicad_fixtures import load_tests, setUpModule  # noqa: E402,F401
from board_kicad_fixtures import Copy, Proved  # noqa: E402

entry = board_prove.policy_entry
DESIGN_LINE = "DESIGN | hardware/proof/gate-proof/gate-proof.kicad_pro | "


class Policing(Copy):
    def seed_with(self, *edits):
        for edit in edits:
            edit(self.seed)
        status, lines = self.check()
        return (status, lines, [line for line in lines if line.startswith("WARNING | ")],
                [line for line in lines if line.startswith("COUNT | ")], self.violations(lines))



class AWarningLineIsPrintedAndDoesNotFailTheCheck(Policing):
    def test_a_design_whose_only_lines_are_warning_lines_passes_with_its_warning_count(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C2: On a synthetic design whose only lines are two of one class and one of another, each marked WARNING by a signed policy entry, the check prints one WARNING line for each carrying the class, the place and the measured figure against the allowed one, prints the count of warning lines for each class, and exits zero, in the check's text report, which is its only report. Out of scope is any class the policy does not mark WARNING.
        status, lines, warnings, counts, violations = self.seed_with(
            board_prove.right_angle, board_prove.short_jog, board_prove.policing(entry("track_angle", count=2), entry("track_segment_length", count=1)))
        self.assertEqual(violations, [], lines)
        self.assertEqual(status, 0, lines)
        self.assertEqual(len(warnings), 3, lines)
        angles = [w for w in warnings if "| track_angle |" in w]
        self.assertEqual(len(angles), 2)
        for report in angles:
            for said in ("Track [/LV_B] on F.Cu", "min angle 135.000", "actual 90.000", "recorded count of 2", "proof-owner", "2026-10-01"):
                self.assertIn(said, report)
        self.assertEqual(len([w for w in warnings if "| track_segment_length |" in w]), 1)
        self.assertIn(DESIGN_LINE + "PASS | 3 warnings", lines)
        self.assertIn("RESULT | PASS | all 1 designs passed", lines)
        self.assertEqual(len(counts), 2)
        self.assertTrue(any("found 2 of recorded 2" in c for c in counts) and any("found 1 of recorded 1" in c for c in counts), counts)
        self.assertEqual([line for line in lines if line.startswith("ACCEPTED | ")], [])

    def test_a_line_of_a_class_the_policy_does_not_name_fails_beside_the_unchanged_warning_lines(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C3: On the same synthetic design with a line of a class that no policy entry names, that line is printed as a violation and the check exits non-zero, with the warning lines unchanged. Out of scope is the wording of the report.
        status, lines, warnings, counts, violations = self.seed_with(
            board_prove.right_angle, board_prove.short_jog, board_prove.policing(entry("track_angle", count=2)))
        self.assertEqual(status, 1, lines)
        self.assertEqual([v[2] for v in violations], ["track_segment_length"], lines)
        self.assertEqual(len(warnings), 2, lines)
        self.assertIn(DESIGN_LINE + "FAIL | 1 violation, 2 warnings", lines)

    def test_without_a_policy_every_line_fails_as_before(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C4: On the same synthetic design, with the policy file absent, with it unparseable, and with each entry's accepted-by value empty, a placeholder or in angle brackets or its date empty, malformed or later than today, every line prints as a violation, none as a WARNING, and the check exits non-zero; and when one entry among otherwise well-formed signed entries is unsigned, the whole policy is void, so the lines of the classes the other entries mark WARNING also stand as violations. Out of scope is a policy that is signed and readable.
        status, lines, warnings, counts, violations = self.seed_with(board_prove.right_angle)
        self.assertEqual((status, warnings, counts), (1, [], []), lines)
        self.assertEqual(sorted(v[2] for v in violations), ["track_angle", "track_angle"])

    def test_an_unsigned_entry_among_signed_ones_leaves_every_line_a_violation(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C4: On the same synthetic design, with the policy file absent, with it unparseable, and with each entry's accepted-by value empty, a placeholder or in angle brackets or its date empty, malformed or later than today, every line prints as a violation, none as a WARNING, and the check exits non-zero; and when one entry among otherwise well-formed signed entries is unsigned, the whole policy is void, so the lines of the classes the other entries mark WARNING also stand as violations. Out of scope is a policy that is signed and readable.
        status, lines, warnings, counts, violations = self.seed_with(
            board_prove.right_angle, board_prove.policing(entry("track_angle"), entry("silk_overlap", count=1, accepted_by="")))
        self.assertEqual((status, warnings, counts), (1, [], []), lines)
        self.assertEqual(sorted(v[2] for v in violations), ["severity_policy", "track_angle", "track_angle"])

    def test_a_count_above_the_recorded_count_fails_the_check_and_one_at_it_passes(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C5: On the same synthetic design with the recorded count of a class at two, a design with three lines of that class fails the check naming the class, the recorded count and the found count, a design with two or with one line of it does not fail on the count, and in each case the check prints the found count beside the recorded count. Out of scope is the lines of any other class and a class whose list KiCad has cut at its cap.
        status, lines, warnings, counts, violations = self.seed_with(board_prove.right_angle, board_prove.policing(entry("track_angle", count=1)))
        self.assertEqual(status, 1, lines)
        self.assertEqual([v[2] for v in violations], ["severity_policy"], lines)
        self.assertIn("found 2 lines, above its recorded count of 1", violations[0][4])
        self.assertIn("track_angle", violations[0][4])
        self.assertEqual(len(warnings), 2)
        self.assertIn("found 2 of recorded 1", counts[0])
        self.setUp()
        status, lines, warnings, counts, violations = self.seed_with(board_prove.right_angle, board_prove.policing(entry("track_angle", count=3)))
        self.assertEqual((status, violations), (0, []), lines)
        self.assertIn("found 2 of recorded 3", counts[0])

    def test_a_per_line_entry_for_a_class_the_policy_marks_warning_is_stale_beside_the_warning_lines(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C8: On a synthetic design carrying a valid signed policy WARNING entry for a class and a signed per-line acceptance entry for the same class, the per-line entry is reported stale as one that no violation uses, and the class's lines are still reported as WARNING lines and none as ACCEPTED, while with the policy void by an unsigned entry the same per-line entry is judged as before. Out of scope is a per-line entry for a class the policy does not mark WARNING.
        status, lines, warnings, counts, violations = self.seed_with(
            board_prove.right_angle, board_prove.policing(entry("track_angle")),
            board_prove.accepting(board_prove.acceptance_entry("track_angle", "/LV_B", 2)))
        self.assertEqual(status, 1, lines)
        self.assertEqual([v[2] for v in violations], ["workmanship_acceptance"], lines)
        self.assertEqual(len(warnings), 2)
        self.assertEqual([line for line in lines if line.startswith("ACCEPTED | ")], [])


class AKicadListAtItsCapIsAFloor(Policing):
    def test_a_staircase_that_fills_kicads_lists_is_warned_at_the_cap_when_the_signed_count_equals_it(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C11: On a synthetic design whose KiCad list for a policy class has reached the cap, `REPORT_LIMIT` (199), the found count is reported as at least the cap, and the check passes the class only when the signed count equals the cap, while a signed count below the cap fails the check under the rule `severity_policy` naming the class, the signed count and the cap; with a list below its cap and a found count above the recorded one the class fails on the ratchet, and with a found count at or below it the class passes. Out of scope is a class whose list KiCad does not cut.
        status, lines, warnings, counts, violations = self.seed_with(
            board_prove.staircase, board_prove.policing(entry("track_angle", count=199), entry("track_segment_length", count=199)))
        self.assertNotIn("severity_policy", [v[2] for v in violations], lines)
        self.assertEqual(len([w for w in warnings if "| track_angle |" in w]), 199)
        self.assertEqual(len([w for w in warnings if "| track_segment_length |" in w]), 199)
        for count in counts:
            self.assertIn("found at least 199, KiCad having cut its list at 199 of recorded 199", count)

    def test_a_signed_count_below_the_cap_fails_naming_the_class_the_signed_count_and_the_cap(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C11: On a synthetic design whose KiCad list for a policy class has reached the cap, `REPORT_LIMIT` (199), the found count is reported as at least the cap, and the check passes the class only when the signed count equals the cap, while a signed count below the cap fails the check under the rule `severity_policy` naming the class, the signed count and the cap; with a list below its cap and a found count above the recorded one the class fails on the ratchet, and with a found count at or below it the class passes. Out of scope is a class whose list KiCad does not cut.
        status, lines, warnings, counts, violations = self.seed_with(
            board_prove.staircase, board_prove.policing(entry("track_angle", count=150), entry("track_segment_length", count=199)))
        failed = [v for v in violations if v[2] == "severity_policy"]
        self.assertEqual(len(failed), 1, lines)
        for said in ("(track_angle)", "signed count of 150", "cap of 199"):
            self.assertIn(said, failed[0][4])
        self.assertEqual(status, 1)


class EachNewFailureIsCaughtOnASeededFault(Proved):
    def test_every_severity_policy_failure_fails_on_its_seeded_fault_and_the_clean_design_with_a_policy_passes(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C9: For each failure of the other criteria of this item, among them the capped-list failure, a seeded copy of the throwaway proof design carrying that fault fails the check under the named rule, a clean copy carrying a signed policy and lines within its counts passes with its WARNING lines printed, and the proof run records each seed as caught. Out of scope is any committed design.
        faults = [fault[0] for fault in board_prove.FAULTS if fault[1].startswith("severity policy:")]
        self.assertEqual(len(faults), 31)
        self.assertCaught(*faults)
        rules = {fault[2] for fault in board_prove.FAULTS if fault[1].startswith("severity policy:")}
        self.assertEqual(rules, {"severity_policy", "track_angle", "workmanship_acceptance"})
        capped = [fault for fault in board_prove.FAULTS if fault[0].startswith("a capped KiCad list")]
        self.assertEqual(len(capped), 2)


class TheCleanDesignWithAPolicyPasses(Policing):
    def test_a_clean_copy_carrying_a_signed_policy_and_lines_within_its_counts_passes_with_its_warning_lines_printed(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C9: For each failure of the other criteria of this item, among them the capped-list failure, a seeded copy of the throwaway proof design carrying that fault fails the check under the named rule, a clean copy carrying a signed policy and lines within its counts passes with its WARNING lines printed, and the proof run records each seed as caught. Out of scope is any committed design.
        status, lines, warnings, counts, violations = self.seed_with(board_prove.right_angle, board_prove.policing(entry("track_angle", count=5)))
        self.assertEqual((status, violations, len(warnings)), (0, [], 2), lines)
        self.setUp()
        status, lines, warnings, counts, violations = self.seed_with(board_prove.policing(entry("track_angle", count=5)))
        self.assertEqual((status, violations, warnings), (0, [], []), lines)
        self.assertIn("found 0 of recorded 5", counts[0])
        self.assertIn(DESIGN_LINE + "PASS", lines)


if __name__ == "__main__":
    import unittest
    unittest.main()
