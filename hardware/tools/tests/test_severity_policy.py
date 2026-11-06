#!/usr/bin/env python3
"""The pre-order check's reading and judgement of the owner's severity policy, driven on synthetic fixtures with no KiCad involved.

What is under test here is what the check decides for itself: whether the policy
record is in the one form it is read in, and which of the cosmetic and neatness
lines a design's check reported it makes WARNING lines, counts and fails, given
as the report writes them. What KiCad reports of a seeded layout, and the text
report of a design that passes on warnings, is driven against the real tool in
test_board_check_kicad_severity_policy.py.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import sys
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
from test_workmanship_acceptance import FOLDER, PROJECT, RECORD as ACCEPTANCE_RECORD, TODAY, YAML, Synthetic  # noqa: E402
from test_workmanship_acceptance import entry as acceptance_entry  # noqa: E402

POLICY = f"{FOLDER}/{board_check.SEVERITY_POLICY_NAME}"
REPOSITORY = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORNER = "Track angle (rule 'Corners' min angle 135.000; actual 90.000)"


def entry(cls="track_angle", severity="WARNING", count=None, **changed) -> dict:
    """A well-formed, signed entry of the policy; an ERROR entry carries no count."""
    base = {"class": cls, "severity": severity, "reason": "a synthetic ground for the test", "accepted_by": "test-owner",
            "accepted_on": "2026-11-01"}
    if severity == "WARNING" or count is not None:
        base["count"] = 2 if count is None else count
    return {**base, **changed}


def without(item: dict, key: str) -> dict:
    return {k: v for k, v in item.items() if k != key}


def corner(net="/NET_A", at="(1, 2)") -> board_check.Violation:
    return board_check.Violation(PROJECT, "track_angle", f"Track [{net}] on F.Cu @ {at} mm", CORNER)


def silk(rule="silk_overlap", place="Footprint R1 @ (10, 10) mm") -> board_check.Violation:
    return board_check.Violation(PROJECT, rule, place, f"{rule} measured 0.10 mm, where the rule allows 0.20 mm")


def other(rule="workmanship_detour", net="/NET_A") -> board_check.Violation:
    return board_check.Violation(PROJECT, rule, f"net {net}: 3 pads, from R1 at (10, 10) mm",
                                 f"{rule} measured 1.50 times, where the figure allows 1.3 times")


class Policed(Synthetic):
    def policy(self, entries, path=POLICY, **top):
        """The policy as written beside the design, tracked; JSON is YAML."""
        self.write(path, json.dumps({"severity_policy": entries, "synthetic": True, **top}))
        if path not in self.tracked:
            self.tracked.append(path)

    def run_policy(self, lines, entries=None, acceptance=None, **top):
        """(the violations left, the report lines of warnings and counts, the ACCEPTED lines) of `lines`."""
        if entries is not None:
            self.policy(entries, **top)
        if acceptance is not None:
            self.record(acceptance)
        self.write(PROJECT, json.dumps({"text_variables": self.variables}))
        warnings: list = []
        accepted: list = []
        left = board_check.judge_accepted_workmanship(YAML, board_check.Repository(self.root, self.tracked),
                                                      board_check.Design(PROJECT), TODAY, list(lines), accepted, warnings)
        return left, warnings, accepted

    def read(self, entries=None, **top):
        if entries is not None:
            self.policy(entries, **top)
        self.write(PROJECT, json.dumps({"text_variables": self.variables}))
        return board_check.load_severity_policy(YAML, self.root, board_check.Repository(self.root, self.tracked),
                                                board_check.Design(PROJECT), self.variables.get("NOT_FOR_MANUFACTURE") == "true")

    @staticmethod
    def failures(left):
        return [v for v in left if v.rule == "severity_policy"]

    @staticmethod
    def shown(warnings):
        return [w for w in warnings if w.startswith("WARNING | ")]

    def assertVoid(self, lines, left, warnings):
        """No line became a WARNING and every line stands as a violation beside the policy's own failure."""
        self.assertEqual(warnings, [])
        for line in lines:
            self.assertIn(line.line(), [v.line() for v in left])
        self.assertTrue(self.failures(left), left)


class TheRecordForm(Policed):
    def test_a_malformed_entry_fails_the_record_naming_the_entry_and_the_key_and_voids_the_whole_policy(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C1: On a synthetic design, a severity policy with an entry that is not a mapping, one with a missing key, one with an extra key, one whose severity is neither ERROR nor WARNING, two entries for one class, a WARNING entry with no count or a count that is not a non-negative whole number and an ERROR entry carrying a count each fail the check under the rule `severity_policy` naming the entry and the key, and in each case the whole policy is void: a line of a class that a well-formed signed entry of the same policy marks WARNING stands as a violation and no line is printed as a WARNING. On the same design a policy file with the top-level severity_policy key missing, with that key not a list, or with a top-level key other than severity_policy and synthetic fails under the rule severity_policy naming the key and marks nothing a WARNING, while an explicit empty severity_policy list is a valid policy that marks nothing a WARNING and does not fail as a record, and the record is read from the nearest tracked file of that name at or above the design folder. The same policy with well-formed entries does not fail as a record. Out of scope is the judgement of a well-formed entry.
        good = entry(count=5)
        cases = [
            ("an entry that is not a mapping", "just words", "severity_policy[1]", "is not a mapping of the keys"),
            ("an extra key", dict(entry("silk_overlap"), note="x"), "severity_policy[1].note", "holds the key 'note'"),
            ("two entries for one class", dict(good), "severity_policy[1].class", "repeats the class 'track_angle' of severity_policy[0]"),
            ("another severity", entry("silk_overlap", severity="FATAL"), "severity_policy[1].severity", "is 'FATAL'"),
            ("a WARNING entry with no count", without(entry("silk_overlap"), "count"), "severity_policy[1].count", "lacks count"),
            ("a negative count", entry("silk_overlap", count=-1), "severity_policy[1].count", "is -1"),
            ("a fractional count", entry("silk_overlap", count=1.5), "severity_policy[1].count", "is 1.5"),
            ("a boolean count", entry("silk_overlap", count=True), "severity_policy[1].count", "is True"),
            ("a count written as text", entry("silk_overlap", count="2"), "severity_policy[1].count", "is '2'"),
            ("an ERROR entry carrying a count", entry("silk_overlap", severity="ERROR", count=3), "severity_policy[1].count",
             "carries count 3"),
        ] + [(f"a missing {key}", without(entry("silk_overlap"), key), f"severity_policy[1].{key}", f"lacks {key}")
             for key in ("class", "severity", "reason", "accepted_by", "accepted_on")] + [
            (f"an empty {key}", dict(entry("silk_overlap"), **{key: " "}), f"severity_policy[1].{key}", f"{key} is ' '")
            for key in ("class", "reason")]
        lines = [corner(), corner(at="(3, 4)")]
        for name, bad, key, said in cases:
            with self.subTest(case=name):
                path, entries, problems = self.read([good, bad])
                self.assertEqual(path, POLICY)
                self.assertEqual({p.rule for p in problems}, {"severity_policy"}, problems)
                named = [p for p in problems if p.location == f"{POLICY} {key}"]
                self.assertTrue(named, f"no violation at {key}: {problems}")
                self.assertIn(said, named[0].message)
                self.assertIn(good, [e for _, e in entries], "the well-formed entry beside it is still read")
                left, warnings, _ = self.run_policy(lines, [good, bad])
                self.assertVoid(lines, left, warnings)

    def test_a_record_that_is_not_in_its_form_marks_nothing_and_fails_naming_the_key(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C1: On a synthetic design, a severity policy with an entry that is not a mapping, one with a missing key, one with an extra key, one whose severity is neither ERROR nor WARNING, two entries for one class, a WARNING entry with no count or a count that is not a non-negative whole number and an ERROR entry carrying a count each fail the check under the rule `severity_policy` naming the entry and the key, and in each case the whole policy is void: a line of a class that a well-formed signed entry of the same policy marks WARNING stands as a violation and no line is printed as a WARNING. On the same design a policy file with the top-level severity_policy key missing, with that key not a list, or with a top-level key other than severity_policy and synthetic fails under the rule severity_policy naming the key and marks nothing a WARNING, while an explicit empty severity_policy list is a valid policy that marks nothing a WARNING and does not fail as a record, and the record is read from the nearest tracked file of that name at or above the design folder. The same policy with well-formed entries does not fail as a record. Out of scope is the judgement of a well-formed entry.
        lines = [corner()]
        for name, text, key in (("a list in place of the mapping", "- class: x\n", "it is not a mapping of keys"),
                                ("no severity_policy", json.dumps({"synthetic": True}), "lacks severity_policy"),
                                ("severity_policy that is no list", json.dumps({"severity_policy": {}, "synthetic": True}),
                                 "severity_policy is not a list"),
                                ("another top-level key", json.dumps({"severity_policy": [entry()], "synthetic": True, "extra": 1}),
                                 "holds the key 'extra'"),
                                ("a key given twice", '{"severity_policy": [], "severity_policy": []}', "")):
            with self.subTest(record=name):
                self.write(POLICY, text)
                if POLICY not in self.tracked:
                    self.tracked.append(POLICY)
                left, warnings, _ = self.run_policy(lines)
                self.assertVoid(lines, left, warnings)
                self.assertTrue(all(v.rule == "severity_policy" for v in left if v.rule != "track_angle"), left)
                if key:
                    self.assertIn(key, " ".join(v.message for v in self.failures(left)))
                self.tracked.remove(POLICY)

    def test_an_explicit_empty_list_is_a_valid_policy_that_marks_nothing_and_does_not_fail_as_a_record(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C1: On a synthetic design, a severity policy with an entry that is not a mapping, one with a missing key, one with an extra key, one whose severity is neither ERROR nor WARNING, two entries for one class, a WARNING entry with no count or a count that is not a non-negative whole number and an ERROR entry carrying a count each fail the check under the rule `severity_policy` naming the entry and the key, and in each case the whole policy is void: a line of a class that a well-formed signed entry of the same policy marks WARNING stands as a violation and no line is printed as a WARNING. On the same design a policy file with the top-level severity_policy key missing, with that key not a list, or with a top-level key other than severity_policy and synthetic fails under the rule severity_policy naming the key and marks nothing a WARNING, while an explicit empty severity_policy list is a valid policy that marks nothing a WARNING and does not fail as a record, and the record is read from the nearest tracked file of that name at or above the design folder. The same policy with well-formed entries does not fail as a record. Out of scope is the judgement of a well-formed entry.
        lines = [corner()]
        self.assertEqual(self.read([])[1:], ([], []))
        left, warnings, _ = self.run_policy(lines, [])
        self.assertEqual((self.failures(left), warnings), ([], []))
        self.assertEqual([v.line() for v in left], [v.line() for v in lines], "the line stands as a violation, with no failure of the record")

    def test_the_same_policy_with_well_formed_entries_does_not_fail_as_a_record(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C1: On a synthetic design, a severity policy with an entry that is not a mapping, one with a missing key, one with an extra key, one whose severity is neither ERROR nor WARNING, two entries for one class, a WARNING entry with no count or a count that is not a non-negative whole number and an ERROR entry carrying a count each fail the check under the rule `severity_policy` naming the entry and the key, and in each case the whole policy is void: a line of a class that a well-formed signed entry of the same policy marks WARNING stands as a violation and no line is printed as a WARNING. On the same design a policy file with the top-level severity_policy key missing, with that key not a list, or with a top-level key other than severity_policy and synthetic fails under the rule severity_policy naming the key and marks nothing a WARNING, while an explicit empty severity_policy list is a valid policy that marks nothing a WARNING and does not fail as a record, and the record is read from the nearest tracked file of that name at or above the design folder. The same policy with well-formed entries does not fail as a record. Out of scope is the judgement of a well-formed entry.
        path, entries, problems = self.read([entry(), entry("silk_overlap", severity="ERROR"), entry("designator_astray", count=0)])
        self.assertEqual((path, problems), (POLICY, []))
        self.assertEqual([(i, e["class"]) for i, e in entries], [(0, "track_angle"), (1, "silk_overlap"), (2, "designator_astray")])

    def test_the_record_is_read_from_the_nearest_tracked_file_at_or_above_the_design_folder(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C1: On a synthetic design, a severity policy with an entry that is not a mapping, one with a missing key, one with an extra key, one whose severity is neither ERROR nor WARNING, two entries for one class, a WARNING entry with no count or a count that is not a non-negative whole number and an ERROR entry carrying a count each fail the check under the rule `severity_policy` naming the entry and the key, and in each case the whole policy is void: a line of a class that a well-formed signed entry of the same policy marks WARNING stands as a violation and no line is printed as a WARNING. On the same design a policy file with the top-level severity_policy key missing, with that key not a list, or with a top-level key other than severity_policy and synthetic fails under the rule severity_policy naming the key and marks nothing a WARNING, while an explicit empty severity_policy list is a valid policy that marks nothing a WARNING and does not fail as a record, and the record is read from the nearest tracked file of that name at or above the design folder. The same policy with well-formed entries does not fail as a record. Out of scope is the judgement of a well-formed entry.
        above = "hardware/synth/" + board_check.SEVERITY_POLICY_NAME
        self.policy([entry(count=7)], above)
        self.assertEqual(self.read()[0], above)
        left, warnings, _ = self.run_policy([corner()])
        self.assertEqual((left, len(self.shown(warnings))), ([], 1), "the record above the folder marks the line WARNING")
        self.policy([entry(count=1)], POLICY)
        self.assertEqual(self.read()[0], POLICY, "the nearer file is the one read")
        self.tracked.remove(POLICY)
        path, entries, problems = self.read()
        self.assertEqual((path, entries), (POLICY, []), "the nearer file is still the one found, and untracked it is not read")
        self.assertIn("not tracked", " ".join(p.message for p in problems))

    def test_the_designs_reads_list_the_severity_policy_where_the_design_holds_one(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C1: On a synthetic design, a severity policy with an entry that is not a mapping, one with a missing key, one with an extra key, one whose severity is neither ERROR nor WARNING, two entries for one class, a WARNING entry with no count or a count that is not a non-negative whole number and an ERROR entry carrying a count each fail the check under the rule `severity_policy` naming the entry and the key, and in each case the whole policy is void: a line of a class that a well-formed signed entry of the same policy marks WARNING stands as a violation and no line is printed as a WARNING. On the same design a policy file with the top-level severity_policy key missing, with that key not a list, or with a top-level key other than severity_policy and synthetic fails under the rule severity_policy naming the key and marks nothing a WARNING, while an explicit empty severity_policy list is a valid policy that marks nothing a WARNING and does not fail as a record, and the record is read from the nearest tracked file of that name at or above the design folder. The same policy with well-formed entries does not fail as a record. Out of scope is the judgement of a well-formed entry.
        self.write(PROJECT, json.dumps({"text_variables": self.variables}))
        self.write(f"{FOLDER}/board.kicad_sch", "(kicad_sch)")
        self.tracked.append(f"{FOLDER}/board.kicad_sch")
        self.assertNotIn(POLICY, board_check.design_reads(self.root, list(self.tracked)))
        self.policy([entry()])
        self.assertIn(POLICY, board_check.design_reads(self.root, list(self.tracked)))


class AWarningLineIsToldFromAViolation(Policed):
    def test_each_line_of_a_class_marked_warning_prints_as_a_warning_line_with_its_class_place_and_figures_and_is_counted(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C2: On a synthetic design whose only lines are two of one class and one of another, each marked WARNING by a signed policy entry, the check prints one WARNING line for each carrying the class, the place and the measured figure against the allowed one, prints the count of warning lines for each class, and exits zero, in the check's text report, which is its only report. Out of scope is any class the policy does not mark WARNING.
        lines = [corner(), corner(at="(3, 4)"), silk()]
        left, warnings, _ = self.run_policy(lines, [entry(count=2), entry("silk_overlap", count=1)])
        self.assertEqual(left, [])
        shown = self.shown(warnings)
        self.assertEqual(len(shown), 3, warnings)
        for text, said in zip(shown, ("track_angle", "track_angle", "silk_overlap")):
            self.assertEqual(text.split(" | ")[2], said)
        self.assertIn("Track [/NET_A] on F.Cu @ (1, 2) mm", shown[0])
        self.assertIn("min angle 135.000; actual 90.000", shown[0])
        self.assertIn("recorded count of 2", shown[0])
        self.assertIn("Footprint R1 @ (10, 10) mm", shown[2])
        self.assertIn("measured 0.10 mm, where the rule allows 0.20 mm", shown[2])
        counts = [w for w in warnings if w.startswith("COUNT | ")]
        self.assertEqual([c.split(" | ")[2:4] for c in counts][0][0], "track_angle")
        self.assertIn("found 2 of recorded 2", counts[0])
        self.assertIn("found 1 of recorded 1", counts[1])

    def test_a_check_with_nowhere_to_print_warnings_keeps_every_line_as_a_violation_instead_of_dropping_it(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C2: On a synthetic design whose only lines are two of one class and one of another, each marked WARNING by a signed policy entry, the check prints one WARNING line for each
        lines = [corner(), corner(at="(3, 4)"), silk()]
        self.policy([entry(count=2), entry("silk_overlap", count=1)])
        self.write(PROJECT, json.dumps({"text_variables": self.variables}))
        left = board_check.judge_accepted_workmanship(YAML, board_check.Repository(self.root, self.tracked),
                                                      board_check.Design(PROJECT), TODAY, list(lines), [])
        self.assertEqual([v.line() for v in left], [v.line() for v in lines])

    def test_a_line_that_no_policy_entry_names_stays_a_violation_with_the_warning_lines_unchanged(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C3: On the same synthetic design with a line of a class that no policy entry names, that line is printed as a violation and the check exits non-zero, with the warning lines unchanged. Out of scope is the wording of the report.
        lines = [corner(), corner(at="(3, 4)"), silk()]
        _, before, _ = self.run_policy(lines, [entry(count=2), entry("silk_overlap", count=1)])
        unnamed = other()
        left, warnings, _ = self.run_policy(lines + [unnamed], [entry(count=2), entry("silk_overlap", count=1)])
        self.assertEqual([v.line() for v in left], [unnamed.line()])
        self.assertEqual(warnings, before)
        # a class the policy marks ERROR is named and still stands
        left, warnings, _ = self.run_policy([silk(), unnamed], [entry("silk_overlap", severity="ERROR")])
        self.assertEqual(sorted(v.rule for v in left), ["silk_overlap", "workmanship_detour"])
        self.assertEqual(warnings, [])

    def test_a_design_without_a_policy_record_judges_every_line_as_before(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C4: On the same synthetic design, with the policy file absent, with it unparseable, and with each entry's accepted-by value empty, a placeholder or in angle brackets or its date empty, malformed or later than today, every line prints as a violation, none as a WARNING, and the check exits non-zero; and when one entry among otherwise well-formed signed entries is unsigned, the whole policy is void, so the lines of the classes the other entries mark WARNING also stand as violations. Out of scope is a policy that is signed and readable.
        lines = [corner(), silk()]
        left, warnings, _ = self.run_policy(lines)
        self.assertEqual(([v.line() for v in left], warnings), ([v.line() for v in lines], []))
        self.assertEqual(self.read()[:2], (None, []))

    def test_an_unreadable_policy_makes_every_line_a_violation(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C4: On the same synthetic design, with the policy file absent, with it unparseable, and with each entry's accepted-by value empty, a placeholder or in angle brackets or its date empty, malformed or later than today, every line prints as a violation, none as a WARNING, and the check exits non-zero; and when one entry among otherwise well-formed signed entries is unsigned, the whole policy is void, so the lines of the classes the other entries mark WARNING also stand as violations. Out of scope is a policy that is signed and readable.
        lines = [corner(), silk()]
        self.write(POLICY, "severity_policy: [unclosed\n  - {")
        self.tracked.append(POLICY)
        left, warnings, _ = self.run_policy(lines)
        self.assertVoid(lines, left, warnings)
        self.tracked.remove(POLICY)
        self.policy([entry(), entry("silk_overlap", count=1)])
        self.tracked.remove(POLICY)
        left, warnings, _ = self.run_policy(lines)
        self.assertVoid(lines, left, warnings)
        self.assertIn("not tracked", self.failures(left)[0].message)

    def test_an_unsigned_entry_makes_every_line_a_violation_and_voids_the_whole_policy(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C4: On the same synthetic design, with the policy file absent, with it unparseable, and with each entry's accepted-by value empty, a placeholder or in angle brackets or its date empty, malformed or later than today, every line prints as a violation, none as a WARNING, and the check exits non-zero; and when one entry among otherwise well-formed signed entries is unsigned, the whole policy is void, so the lines of the classes the other entries mark WARNING also stand as violations. Out of scope is a policy that is signed and readable.
        lines = [corner(), silk()]
        unsigned = [("an empty accepted_by", {"accepted_by": ""}, "accepted_by is ''"),
                    ("a blank accepted_by", {"accepted_by": "  "}, "accepted_by is '  '"),
                    ("a missing accepted_by", {"accepted_by": None}, "accepted_by is None"),
                    ("a placeholder", {"accepted_by": "unsigned"}, "is a placeholder"),
                    ("a TBD placeholder", {"accepted_by": "TBD"}, "is a placeholder"),
                    ("angle brackets", {"accepted_by": "<owner>"}, "accepted_by '<owner>' is a placeholder"),
                    ("an empty date", {"accepted_on": ""}, "is not a valid calendar date"),
                    ("a malformed date", {"accepted_on": "tomorrow"}, "accepted_on tomorrow is not a valid calendar date"),
                    ("a future date", {"accepted_on": "2026-11-08"}, "is later than today")]
        for name, change, said in unsigned:
            with self.subTest(entry=name):
                left, warnings, _ = self.run_policy(lines, [entry(), dict(entry("silk_overlap", count=1), **change)])
                self.assertVoid(lines, left, warnings)
                failed = self.failures(left)
                self.assertEqual(len(failed), 1, failed)
                self.assertIn(said, failed[0].message)
                self.assertIn("severity_policy[1]", failed[0].location)
        # the same two entries signed mark both classes
        left, warnings, _ = self.run_policy(lines, [entry(), entry("silk_overlap", count=1)])
        self.assertEqual((left, len(self.shown(warnings))), ([], 2))

    def test_a_date_of_today_is_signed(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C4: On the same synthetic design, with the policy file absent, with it unparseable, and with each entry's accepted-by value empty, a placeholder or in angle brackets or its date empty, malformed or later than today, every line prints as a violation, none as a WARNING, and the check exits non-zero; and when one entry among otherwise well-formed signed entries is unsigned, the whole policy is void, so the lines of the classes the other entries mark WARNING also stand as violations. Out of scope is a policy that is signed and readable.
        left, warnings, _ = self.run_policy([corner()], [entry(accepted_on=TODAY.isoformat())])
        self.assertEqual((left, len(self.shown(warnings))), ([], 1))

    def test_a_synthetic_policy_is_honoured_only_when_the_design_is_marked_not_for_manufacture(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C4: On the same synthetic design, with the policy file absent, with it unparseable, and with each entry's accepted-by value empty, a placeholder or in angle brackets or its date empty, malformed or later than today, every line prints as a violation, none as a WARNING, and the check exits non-zero; and when one entry among otherwise well-formed signed entries is unsigned, the whole policy is void, so the lines of the classes the other entries mark WARNING also stand as violations. Out of scope is a policy that is signed and readable.
        self.variables.pop("NOT_FOR_MANUFACTURE")
        lines = [corner()]
        left, warnings, _ = self.run_policy(lines, [entry()])
        self.assertVoid(lines, left, warnings)
        self.assertIn("marked synthetic", self.failures(left)[0].message)
        left, warnings, _ = self.run_policy(lines, [entry()], synthetic=False)
        self.assertEqual((left, len(self.shown(warnings))), ([], 1))


class TheRatchet(Policed):
    def test_a_count_above_the_recorded_count_fails_naming_the_class_and_both_counts(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C5: On the same synthetic design with the recorded count of a class at two, a design with three lines of that class fails the check naming the class, the recorded count and the found count, a design with two or with one line of it does not fail on the count, and in each case the check prints the found count beside the recorded count. Out of scope is the lines of any other class and a class whose list KiCad has cut at its cap.
        lines = [corner(at=f"({n}, 1)") for n in range(3)]
        left, warnings, _ = self.run_policy(lines, [entry(count=2)])
        failed = self.failures(left)
        self.assertEqual(len(failed), 1, left)
        self.assertIn("track_angle", failed[0].message)
        self.assertIn("found 3 lines", failed[0].message)
        self.assertIn("recorded count of 2", failed[0].message)
        self.assertEqual(failed[0].location, f"{POLICY} severity_policy[0].count")
        self.assertEqual(len(self.shown(warnings)), 3)
        self.assertIn("found 3 of recorded 2", [w for w in warnings if w.startswith("COUNT | ")][0])

    def test_a_count_at_or_below_the_recorded_count_passes_and_prints_the_found_count_beside_it(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C5: On the same synthetic design with the recorded count of a class at two, a design with three lines of that class fails the check naming the class, the recorded count and the found count, a design with two or with one line of it does not fail on the count, and in each case the check prints the found count beside the recorded count. Out of scope is the lines of any other class and a class whose list KiCad has cut at its cap.
        for found in (2, 1, 0):
            with self.subTest(found=found):
                left, warnings, _ = self.run_policy([corner(at=f"({n}, 1)") for n in range(found)], [entry(count=2)])
                self.assertEqual(left, [])
                counts = [w for w in warnings if w.startswith("COUNT | ")]
                self.assertEqual(len(counts), 1, warnings)
                self.assertIn(f"found {found} of recorded 2", counts[0])
                self.assertEqual(len(self.shown(warnings)), found)

    def test_a_recorded_count_of_zero_fails_on_the_first_line(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C5: On the same synthetic design with the recorded count of a class at two, a design with three lines of that class fails the check naming the class, the recorded count and the found count, a design with two or with one line of it does not fail on the count, and in each case the check prints the found count beside the recorded count. Out of scope is the lines of any other class and a class whose list KiCad has cut at its cap.
        left, _, _ = self.run_policy([silk()], [entry("silk_overlap", count=0)])
        self.assertEqual(len(self.failures(left)), 1)
        self.assertIn("recorded count of 0", self.failures(left)[0].message)

    def test_the_lines_of_another_class_are_not_counted_against_the_class(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C5: On the same synthetic design with the recorded count of a class at two, a design with three lines of that class fails the check naming the class, the recorded count and the found count, a design with two or with one line of it does not fail on the count, and in each case the check prints the found count beside the recorded count. Out of scope is the lines of any other class and a class whose list KiCad has cut at its cap.
        left, warnings, _ = self.run_policy([corner(), corner(at="(3, 4)"), silk(), silk(place="Footprint R2 @ (1, 1) mm")],
                                            [entry(count=2), entry("silk_overlap", count=2)])
        self.assertEqual(left, [])
        self.assertEqual(len(self.shown(warnings)), 4)


class OnlyTheClassesThePolicyCoversCanBeNamed(Policed):
    REFUSED = ("silk_over_copper", "test_point_courtyard", "courtyards_overlap", "items_not_allowed", "workmanship_width",
               "clearance", "creepage", "separation_floor", "separation_rule", "separation_basis", "derated_voltage", "pin_limit",
               "mounting_hole", "plated_hole", "hole_to_hole", "annular_width", "hole_size", "connectivity", "unconnected_items",
               "track_width", "via_dangling", "track_dangling", "solder_mask_bridge", "paste", "mains_class", "no_such_class")

    def test_an_entry_naming_a_class_outside_the_closed_list_fails_the_check_naming_it_and_voids_the_policy(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C6: On a synthetic design, a policy entry, at either severity, naming a class outside the closed list of ten (`silk_overlap`, `silk_edge_clearance`, `designator_astray`, `reference_off_silkscreen`, `track_angle`, `track_segment_length`, `workmanship_direction`, `workmanship_pad_entry`, `workmanship_pad_corner` and `workmanship_detour`), among them `silk_over_copper`, `test_point_courtyard`, `courtyards_overlap`, `items_not_allowed`, `workmanship_width`, and a class that carries a safety, mains spacing, creepage, clearance, derated-voltage, pin-limit, mounting-hole, plated-hole, connectivity, hole, annular ring, drill, other manufacturing, paste, solder or separation basis finding, fails the check under the rule `severity_policy` naming the entry, as does an entry naming a class the check does not report, and in each case the whole policy is void: no line is printed as a WARNING and every line stands as a violation. Out of scope is any class the policy may cover.
        lines = [corner(), silk()]
        for severity in ("WARNING", "ERROR"):
            for name in self.REFUSED:
                with self.subTest(severity=severity, cls=name):
                    left, warnings, _ = self.run_policy(lines, [entry(), entry("silk_overlap", count=1), entry(name, severity=severity, count=1 if severity == "WARNING" else None)])
                    self.assertVoid(lines, left, warnings)
                    failed = self.failures(left)
                    self.assertEqual(len(failed), 1, failed)
                    self.assertIn(f"({name}) names the class {name}, which the policy does not cover", failed[0].message)
                    self.assertEqual(failed[0].location, f"{POLICY} severity_policy[2].class")

    def test_the_closed_list_is_exactly_the_ten_classes_and_each_is_accepted_at_either_severity(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C6: On a synthetic design, a policy entry, at either severity, naming a class outside the closed list of ten (`silk_overlap`, `silk_edge_clearance`, `designator_astray`, `reference_off_silkscreen`, `track_angle`, `track_segment_length`, `workmanship_direction`, `workmanship_pad_entry`, `workmanship_pad_corner` and `workmanship_detour`), among them `silk_over_copper`, `test_point_courtyard`, `courtyards_overlap`, `items_not_allowed`, `workmanship_width`, and a class that carries a safety, mains spacing, creepage, clearance, derated-voltage, pin-limit, mounting-hole, plated-hole, connectivity, hole, annular ring, drill, other manufacturing, paste, solder or separation basis finding, fails the check under the rule `severity_policy` naming the entry, as does an entry naming a class the check does not report, and in each case the whole policy is void: no line is printed as a WARNING and every line stands as a violation. Out of scope is any class the policy may cover.
        closed = ("silk_overlap", "silk_edge_clearance", "designator_astray", "reference_off_silkscreen", "track_angle",
                  "track_segment_length", "workmanship_direction", "workmanship_pad_entry", "workmanship_pad_corner",
                  "workmanship_detour")
        self.assertEqual(board_check.POLICY_CLASSES, closed)
        for name in closed:
            for severity in ("WARNING", "ERROR"):
                with self.subTest(cls=name, severity=severity):
                    left, warnings, _ = self.run_policy([], [entry(name, severity=severity, count=1 if severity == "WARNING" else None)])
                    self.assertEqual((left, self.shown(warnings)), ([], []))
                    self.assertEqual(self.failures(left), [])

    def test_a_refused_class_voids_the_policy_even_when_it_is_the_only_entry(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C6: On a synthetic design, a policy entry, at either severity, naming a class outside the closed list of ten (`silk_overlap`, `silk_edge_clearance`, `designator_astray`, `reference_off_silkscreen`, `track_angle`, `track_segment_length`, `workmanship_direction`, `workmanship_pad_entry`, `workmanship_pad_corner` and `workmanship_detour`), among them `silk_over_copper`, `test_point_courtyard`, `courtyards_overlap`, `items_not_allowed`, `workmanship_width`, and a class that carries a safety, mains spacing, creepage, clearance, derated-voltage, pin-limit, mounting-hole, plated-hole, connectivity, hole, annular ring, drill, other manufacturing, paste, solder or separation basis finding, fails the check under the rule `severity_policy` naming the entry, as does an entry naming a class the check does not report, and in each case the whole policy is void: no line is printed as a WARNING and every line stands as a violation. Out of scope is any class the policy may cover.
        lines = [silk("silk_over_copper", "Pad 3 of Q741")]
        left, warnings, _ = self.run_policy(lines, [entry("silk_over_copper", count=1)])
        self.assertVoid(lines, left, warnings)
        self.assertIn("solderable area", self.failures(left)[0].message)


class ANeatnessLineIsAWarningOnAnyNet(Policed):
    NEATNESS = ("track_angle", "track_segment_length", "workmanship_direction", "workmanship_pad_entry", "workmanship_pad_corner",
                "workmanship_detour")

    def test_a_neatness_line_on_a_mains_sensing_critical_or_ordinary_net_prints_as_a_warning_and_is_counted(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C7: On a synthetic design whose signed policy marks a routing-neatness class WARNING, a line of that class on a mains net, on a sensing net, on a net of a critical class and on an ordinary net each prints as a WARNING line and is counted, none as a violation, and a clearance or creepage shortfall on the same net still fails under its own rule. Out of scope is a silkscreen or designator class.
        nets = ("/MAINS_L", "/SENSE_I", "/CLK_FAST", "/LV_A")
        for name in self.NEATNESS:
            with self.subTest(cls=name):
                if name.startswith("track_"):
                    lines = [board_check.Violation(PROJECT, name, f"Track [{net}] on F.Cu @ (1, 2) mm", "measured against allowed")
                             for net in nets]
                else:
                    lines = [other(name, net) for net in nets]
                left, warnings, _ = self.run_policy(lines, [entry(name, count=4)])
                self.assertEqual(left, [])
                self.assertEqual(len(self.shown(warnings)), 4)
                for net in nets:
                    self.assertTrue([w for w in self.shown(warnings) if net in w], net)
                self.assertIn("found 4 of recorded 4", [w for w in warnings if w.startswith("COUNT | ")][0])

    def test_a_clearance_or_creepage_shortfall_on_the_same_net_still_fails_under_its_own_rule(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C7: On a synthetic design whose signed policy marks a routing-neatness class WARNING, a line of that class on a mains net, on a sensing net, on a net of a critical class and on an ordinary net each prints as a WARNING line and is counted, none as a violation, and a clearance or creepage shortfall on the same net still fails under its own rule. Out of scope is a silkscreen or designator class.
        shortfalls = [board_check.Violation(PROJECT, rule, f"Track [/MAINS_L] on F.Cu @ (1, 2) mm; Pad 1 of J1 [/MAINS_N]", "short")
                      for rule in ("clearance", "creepage", "separation_rule", "sensing_clearance")]
        lines = [board_check.Violation(PROJECT, "track_angle", "Track [/MAINS_L] on F.Cu @ (1, 2) mm", CORNER)] + shortfalls
        left, warnings, _ = self.run_policy(lines, [entry(count=1)] + [entry(n, "ERROR") for n in ("silk_overlap",)])
        self.assertEqual([v.rule for v in left], ["clearance", "creepage", "separation_rule", "sensing_clearance"])
        self.assertEqual(len(self.shown(warnings)), 1)


class TheSeverityPolicyAndThePerLineRecord(Policed):
    def test_a_per_line_entry_for_a_class_the_valid_policy_marks_warning_is_stale_and_the_lines_are_warnings(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C8: On a synthetic design carrying a valid signed policy WARNING entry for a class and a signed per-line acceptance entry for the same class, the per-line entry is reported stale as one that no violation uses, and the class's lines are still reported as WARNING lines and none as ACCEPTED, while with the policy void by an unsigned entry the same per-line entry is judged as before. Out of scope is a per-line entry for a class the policy does not mark WARNING.
        lines = [corner(), corner(at="(3, 4)")]
        left, warnings, accepted = self.run_policy(lines, [entry(count=2)], acceptance=[acceptance_entry("track_angle", "/NET_A", 2)])
        self.assertEqual(accepted, [])
        self.assertEqual(len(self.shown(warnings)), 2)
        stale = [v for v in left if v.rule == "workmanship_acceptance"]
        self.assertEqual(len(stale), 1, left)
        self.assertEqual([v.rule for v in left], ["workmanship_acceptance"])
        self.assertIn("is stale", stale[0].message)
        self.assertEqual(stale[0].location, f"{ACCEPTANCE_RECORD} accepted_workmanship[0].rule")

    def test_with_the_policy_void_by_an_unsigned_entry_the_same_per_line_entry_is_judged_as_before(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C8: On a synthetic design carrying a valid signed policy WARNING entry for a class and a signed per-line acceptance entry for the same class, the per-line entry is reported stale as one that no violation uses, and the class's lines are still reported as WARNING lines and none as ACCEPTED, while with the policy void by an unsigned entry the same per-line entry is judged as before. Out of scope is a per-line entry for a class the policy does not mark WARNING.
        lines = [corner(), corner(at="(3, 4)")]
        left, warnings, accepted = self.run_policy(
            lines, [entry(count=2), entry("silk_overlap", count=1, accepted_by="")], acceptance=[acceptance_entry("track_angle", "/NET_A", 2)])
        self.assertEqual(warnings, [])
        self.assertEqual(len(accepted), 2)
        self.assertEqual([v.rule for v in left], ["severity_policy"])

    def test_a_per_line_entry_for_a_class_the_policy_does_not_mark_warning_still_accepts_its_lines(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C8: On a synthetic design carrying a valid signed policy WARNING entry for a class and a signed per-line acceptance entry for the same class, the per-line entry is reported stale as one that no violation uses, and the class's lines are still reported as WARNING lines and none as ACCEPTED, while with the policy void by an unsigned entry the same per-line entry is judged as before. Out of scope is a per-line entry for a class the policy does not mark WARNING.
        lines = [corner(), other()]
        left, warnings, accepted = self.run_policy(
            lines, [entry(count=1)], acceptance=[acceptance_entry("workmanship_detour", "/NET_A", 1)])
        self.assertEqual(left, [])
        self.assertEqual((len(self.shown(warnings)), len(accepted)), (1, 1))
        # and a policy that marks the class ERROR is not a WARNING mark, so the entry is used
        left, warnings, accepted = self.run_policy([corner()], [entry(severity="ERROR")], acceptance=[acceptance_entry("track_angle", "/NET_A", 1)])
        self.assertEqual((left, warnings, len(accepted)), ([], [], 1))

    def test_no_line_is_both_a_warning_and_accepted(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C8: On a synthetic design carrying a valid signed policy WARNING entry for a class and a signed per-line acceptance entry for the same class, the per-line entry is reported stale as one that no violation uses, and the class's lines are still reported as WARNING lines and none as ACCEPTED, while with the policy void by an unsigned entry the same per-line entry is judged as before. Out of scope is a per-line entry for a class the policy does not mark WARNING.
        lines = [corner(), corner(at="(3, 4)"), corner(net="/NET_B", at="(5, 6)")]
        left, warnings, accepted = self.run_policy(lines, [entry(count=3)], acceptance=[acceptance_entry("track_angle", "/NET_A", 2)])
        self.assertEqual((len(self.shown(warnings)), accepted), (3, []))


class ACappedListIsAFloorNotACount(Policed):
    def lines(self, rule, number):
        return [board_check.Violation(PROJECT, rule, f"Track [/NET_A] on F.Cu @ ({n}, 1) mm", CORNER) for n in range(number)]

    def test_a_list_at_the_cap_passes_only_when_the_signed_count_equals_the_cap(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C11: On a synthetic design whose KiCad list for a policy class has reached the cap, `REPORT_LIMIT` (199), the found count is reported as at least the cap, and the check passes the class only when the signed count equals the cap, while a signed count below the cap fails the check under the rule `severity_policy` naming the class, the signed count and the cap; with a list below its cap and a found count above the recorded one the class fails on the ratchet, and with a found count at or below it the class passes. Out of scope is a class whose list KiCad does not cut.
        for rule in board_check.POLICY_CAPPED:
            with self.subTest(cls=rule):
                left, warnings, _ = self.run_policy(self.lines(rule, board_check.REPORT_LIMIT), [entry(rule, count=board_check.REPORT_LIMIT)])
                self.assertEqual(left, [])
                counts = [w for w in warnings if w.startswith("COUNT | ")]
                self.assertEqual(len(counts), 1)
                self.assertIn("found at least 199, KiCad having cut its list at 199 of recorded 199", counts[0])
                self.assertEqual(len(self.shown(warnings)), 199)

    def test_a_signed_count_below_the_cap_fails_naming_the_class_the_signed_count_and_the_cap(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C11: On a synthetic design whose KiCad list for a policy class has reached the cap, `REPORT_LIMIT` (199), the found count is reported as at least the cap, and the check passes the class only when the signed count equals the cap, while a signed count below the cap fails the check under the rule `severity_policy` naming the class, the signed count and the cap; with a list below its cap and a found count above the recorded one the class fails on the ratchet, and with a found count at or below it the class passes. Out of scope is a class whose list KiCad does not cut.
        for rule in board_check.POLICY_CAPPED:
            for signed in (150, 198, 0):
                with self.subTest(cls=rule, signed=signed):
                    left, _, _ = self.run_policy(self.lines(rule, board_check.REPORT_LIMIT), [entry(rule, count=signed)])
                    failed = self.failures(left)
                    self.assertEqual(len(failed), 1, left)
                    self.assertIn(f"({rule})", failed[0].message)
                    self.assertIn(f"signed count of {signed}", failed[0].message)
                    self.assertIn("cap of 199", failed[0].message)

    def test_a_signed_count_above_the_cap_fails_with_a_list_at_the_cap(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C11: On a synthetic design whose KiCad list for a policy class has reached the cap, `REPORT_LIMIT` (199), the found count is reported as at least the cap, and the check passes the class only when the signed count equals the cap, while a signed count below the cap fails the check under the rule `severity_policy` naming the class, the signed count and the cap; with a list below its cap and a found count above the recorded one the class fails on the ratchet, and with a found count at or below it the class passes. Out of scope is a class whose list KiCad does not cut.
        left, _, _ = self.run_policy(self.lines("track_angle", 199), [entry(count=250)])
        self.assertEqual(len(self.failures(left)), 1)
        self.assertIn("signed count of 250", self.failures(left)[0].message)

    def test_a_list_below_the_cap_is_ratcheted_normally(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C11: On a synthetic design whose KiCad list for a policy class has reached the cap, `REPORT_LIMIT` (199), the found count is reported as at least the cap, and the check passes the class only when the signed count equals the cap, while a signed count below the cap fails the check under the rule `severity_policy` naming the class, the signed count and the cap; with a list below its cap and a found count above the recorded one the class fails on the ratchet, and with a found count at or below it the class passes. Out of scope is a class whose list KiCad does not cut.
        left, warnings, _ = self.run_policy(self.lines("track_angle", 198), [entry(count=197)])
        self.assertEqual(len(self.failures(left)), 1)
        self.assertIn("found 198 lines, above its recorded count of 197", self.failures(left)[0].message)
        for signed in (198, 199, 250):
            with self.subTest(signed=signed):
                left, warnings, _ = self.run_policy(self.lines("track_angle", 198), [entry(count=signed)])
                self.assertEqual(left, [])
                self.assertIn(f"found 198 of recorded {signed}", [w for w in warnings if w.startswith("COUNT | ")][0])

    def test_a_class_whose_list_kicad_does_not_cut_has_no_cap(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C11: On a synthetic design whose KiCad list for a policy class has reached the cap, `REPORT_LIMIT` (199), the found count is reported as at least the cap, and the check passes the class only when the signed count equals the cap, while a signed count below the cap fails the check under the rule `severity_policy` naming the class, the signed count and the cap; with a list below its cap and a found count above the recorded one the class fails on the ratchet, and with a found count at or below it the class passes. Out of scope is a class whose list KiCad does not cut.
        left, _, _ = self.run_policy(self.lines("silk_overlap", 199), [entry("silk_overlap", count=150)])
        self.assertIn("found 199 lines, above its recorded count of 150", self.failures(left)[0].message)
        left, warnings, _ = self.run_policy(self.lines("silk_overlap", 199), [entry("silk_overlap", count=199)])
        self.assertEqual(left, [])
        self.assertIn("found 199 of recorded 199", [w for w in warnings if w.startswith("COUNT | ")][0])


class TheHardwareNotesStateThePolicy(unittest.TestCase):
    def notes(self):
        with open(os.path.join(REPOSITORY, "README.md"), encoding="utf-8") as handle:
            return handle.read()

    def test_the_notes_state_the_tiers_the_entry_form_the_report_lines_and_each_failure(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C10: The hardware notes state the policy's entry form with each key, the WARNING line, the count line, each failure of the policy, the classes the policy can never mark WARNING, that an unnamed class and an unsigned policy fail closed, and that the policy is the owner's to sign. Out of scope is any board's own policy.
        text = self.notes()
        start = text.index("severity policy")
        section = text[start:start + 12000]
        for words in (board_check.SEVERITY_POLICY_NAME, "severity_policy", "class", "severity", "count", "reason", "accepted_by",
                      "accepted_on", "ERROR", "WARNING", "`WARNING | ", "`COUNT | ", "found", "recorded", "REPORT_LIMIT", "199",
                      "at least", "the owner's to sign", "unsigned", "fails closed", "void", "synthetic", "NOT_FOR_MANUFACTURE"):
            self.assertIn(words, section)
        for name in board_check.POLICY_CLASSES:
            self.assertIn(f"`{name}`", section)
        for name in ("silk_over_copper", "test_point_courtyard", "courtyards_overlap", "items_not_allowed", "workmanship_width"):
            self.assertIn(f"`{name}`", section)
        for never in ("safety", "mains spacing", "creepage", "clearance", "derated-voltage", "pin-limit", "mounting-hole", "plated-hole",
                      "connectivity", "annular ring", "drill", "paste", "solder", "courtyard overlap", "separation basis"):
            self.assertIn(never, section)

    def test_the_rule_table_has_a_row_for_the_severity_policy_and_the_kicad_silkscreen_pass_through(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C10: The hardware notes state the policy's entry form with each key, the WARNING line, the count line, each failure of the policy, the classes the policy can never mark WARNING, that an unnamed class and an unsigned policy fail closed, and that the policy is the owner's to sign. Out of scope is any board's own policy.
        text = self.notes()
        table = text[text.index("| Rule | Meaning |"):]
        table = table[:table.index("\n\n")]
        rows = {line.split("|")[1].strip().strip("`"): line.split("|")[2] for line in table.splitlines()[2:]}
        self.assertIn("severity_policy", rows)
        for words in ("unsigned", "count", "cap", "class"):
            self.assertIn(words, rows["severity_policy"])
        self.assertIn("silk_edge_clearance", rows)
        self.assertIn("silk_overlap", rows)

    def test_the_designs_records_line_names_the_severity_policy(self):
        # SOL-PRE-ORDER-CHECK-CLASSIFIES-COSMETIC-LINES-AS-RATCHETED-WARNINGS-UNDER-OWNER-SIGNED-POLICY.C10: The hardware notes state the policy's entry form with each key, the WARNING line, the count line, each failure of the policy, the classes the policy can never mark WARNING, that an unnamed class and an unsigned policy fail closed, and that the policy is the owner's to sign. Out of scope is any board's own policy.
        self.assertIn(board_check.SEVERITY_POLICY_NAME, self.notes().splitlines()[4])


if __name__ == "__main__":
    unittest.main()
