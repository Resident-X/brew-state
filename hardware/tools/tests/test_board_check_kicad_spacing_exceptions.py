#!/usr/bin/env python3
"""The pre-order check against KiCad itself, on the throwaway proof design, here the owner's signed spacing exceptions.

This is one of the files the check's KiCad tests are divided into by topic; the
shared setup, the seeded-fault proof's pooled outcomes and the exclusion of what
needs that proof are in board_kicad_fixtures.py.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest

import yaml

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_prove  # noqa: E402
from board_kicad_fixtures import load_tests, setUpModule  # noqa: E402,F401
from board_kicad_fixtures import Copy, Proved, outcomes, KICAD_CLI  # noqa: E402

entry = board_prove.exception_entry
#: The three shortfalls the seeded layouts leave: the mains-to-mains clearance between the two pads of J1, and the
#: mains-to-low-voltage creepage between R1 pad 2 and each of the two pads of J2.
CLEARANCE = ("mains_to_mains", "clearance", ("J1.1", "J1.2"))
CREEPAGE_FIRST = ("mains_to_low_voltage", "creepage", ("R1.2", "J2.1"))
CREEPAGE_SECOND = ("mains_to_low_voltage", "creepage", ("R1.2", "J2.2"))


class SpacingExceptionsRunDirectly(Copy):
    def accepted(self, lines):
        return [line.split(" | ") for line in lines if line.startswith("ACCEPTED | ")]

    def spacing(self, lines):
        return [v for v in self.violations(lines) if v[2] == "spacing_exception"]

    def ordinary(self, lines):
        return [v for v in self.violations(lines) if v[2] in ("clearance", "creepage")]

    def test_a_mains_to_mains_clearance_shortfall_at_or_above_the_accepted_distance_is_reported_and_the_design_passes(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C2: On a seeded layout with the pair of items an entry's between lists closer than the signed figure but no closer than the entry's accepted_mm, the report holds a line naming the pair, the measured distance, the accepted distance and the owner's reason, and the design passes. The same holds for a mains_to_low_voltage creepage entry and a mains_to_mains clearance entry. Shortfalls between any other pair are out of scope and keep failing.
        board_prove.TERMINAL_SHORTFALL(self.seed)
        board_prove.exceptions(entry(*CLEARANCE, 0.8))(self.seed)
        status, lines = self.check()
        self.assertEqual(status, 0, lines)
        (line,) = self.accepted(lines)
        self.assertEqual(line[2], "spacing_exception")
        self.assertTrue(line[3].endswith("separation-basis.yaml accepted_exceptions[0]"), line)
        for words in ("mains_to_mains clearance between J1.1 and J1.2", "pad 1 [/MAINS_L] of J1", "pad 2 [/MAINS_N] of J1",
                      "measures 0.84 mm", "accepted down to 0.8 mm", "against the signed 1 mm", "reason: synthetic -- a ground",
                      "bounded by: synthetic -- an independent element"):
            self.assertIn(words, line[4])
        self.assertEqual(self.violations(lines), [], lines)

    def test_a_mains_to_low_voltage_creepage_shortfall_at_or_above_the_accepted_distance_is_reported_and_the_design_passes(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C2: On a seeded layout with the pair of items an entry's between lists closer than the signed figure but no closer than the entry's accepted_mm, the report holds a line naming the pair, the measured distance, the accepted distance and the owner's reason, and the design passes. The same holds for a mains_to_low_voltage creepage entry and a mains_to_mains clearance entry. Shortfalls between any other pair are out of scope and keep failing.
        board_prove.CREEPAGE_SHORTFALL(self.seed)
        board_prove.exceptions(entry(*CREEPAGE_FIRST, 13.0), entry(*CREEPAGE_SECOND, 13.0))(self.seed)
        status, lines = self.check()
        self.assertEqual(status, 0, lines)
        found = self.accepted(lines)
        self.assertEqual(len(found), 2, lines)
        self.assertIn("measures 13.19 mm", found[0][4])
        self.assertIn("measures 13.4058 mm", found[1][4])
        for line in found:
            self.assertIn("mains_to_low_voltage creepage between R1.2 and J2.", line[4])
            self.assertIn("accepted down to 13 mm against the signed 13.5 mm", line[4])
        self.assertEqual(self.violations(lines), [], lines)

    def test_the_net_pair_form_excuses_the_same_shortfall(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C2: On a seeded layout with the pair of items an entry's between lists closer than the signed figure but no closer than the entry's accepted_mm, the report holds a line naming the pair, the measured distance, the accepted distance and the owner's reason, and the design passes. The same holds for a mains_to_low_voltage creepage entry and a mains_to_mains clearance entry. Shortfalls between any other pair are out of scope and keep failing.
        board_prove.TERMINAL_SHORTFALL(self.seed)
        board_prove.exceptions(entry("mains_to_mains", "clearance", ("/MAINS_N", "/MAINS_L"), 0.8))(self.seed)
        status, lines = self.check()
        self.assertEqual(status, 0, lines)
        self.assertEqual(len(self.accepted(lines)), 1)

    def test_a_shortfall_with_no_exception_is_the_ordinary_violation_and_prints_no_accepted_line(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C3: A layout whose measured distance is below accepted_mm fails spacing_exception naming the entry and both distances. A shortfall between a pair with no entry, including another pair of the same part, for an entry of the other pair kind, or for the other constraint of the same pair fails as an ordinary violation, so an exception for one pair of a part's pads does not excuse another pair of them, nor an exception for creepage its clearance. Parts whose measured distance meets the signed figure are out of scope and never reported.
        board_prove.TERMINAL_SHORTFALL(self.seed)
        status, lines = self.check()
        self.assertEqual(status, 1)
        self.assertTrue(self.ordinary(lines), lines)
        self.assertEqual((self.accepted(lines), self.spacing(lines)), ([], []))

    def test_a_distance_below_the_accepted_one_fails_naming_the_entry_and_both_distances(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C3: A layout whose measured distance is below accepted_mm fails spacing_exception naming the entry and both distances. A shortfall between a pair with no entry, including another pair of the same part, for an entry of the other pair kind, or for the other constraint of the same pair fails as an ordinary violation, so an exception for one pair of a part's pads does not excuse another pair of them, nor an exception for creepage its clearance. Parts whose measured distance meets the signed figure are out of scope and never reported.
        board_prove.TERMINAL_SHORTFALL(self.seed)
        board_prove.exceptions(entry(*CLEARANCE, 0.9))(self.seed)
        status, lines = self.check()
        self.assertEqual(status, 1)
        (found,) = self.spacing(lines)
        self.assertTrue(found[3].endswith("accepted_exceptions[0]"), found)
        for words in ("accepted_exceptions[0]", "J1.1 and J1.2", "down to 0.9 mm", "leaves 0.84 mm"):
            self.assertIn(words, found[4])
        self.assertEqual((self.accepted(lines), self.ordinary(lines)), ([], []), lines)

    def test_an_entry_of_the_other_pair_kind_or_the_other_constraint_excuses_nothing(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C3: A layout whose measured distance is below accepted_mm fails spacing_exception naming the entry and both distances. A shortfall between a pair with no entry, including another pair of the same part, for an entry of the other pair kind, or for the other constraint of the same pair fails as an ordinary violation, so an exception for one pair of a part's pads does not excuse another pair of them, nor an exception for creepage its clearance. Parts whose measured distance meets the signed figure are out of scope and never reported.
        for changed in (("mains_to_low_voltage", "clearance", ("J1.1", "J1.2")), ("mains_to_mains", "creepage", ("J1.1", "J1.2"))):
            with self.subTest(entry=changed):
                self.setUp()
                board_prove.TERMINAL_SHORTFALL(self.seed)
                board_prove.exceptions(entry(*changed, 0.8))(self.seed)
                status, lines = self.check()
                self.assertEqual(status, 1)
                self.assertTrue(self.ordinary(lines), "the shortfall was excused by an entry for another kind")
                self.assertEqual(self.accepted(lines), [])
                (found,) = self.spacing(lines)
                self.assertIn("reports no shortfall", found[4])

    def assertNotHonoured(self, entry_text, words):
        board_prove.TERMINAL_SHORTFALL(self.seed)
        board_prove.exceptions(entry_text)(self.seed)
        status, lines = self.check()
        self.assertEqual(status, 1)
        self.assertEqual(self.accepted(lines), [], "an entry that is no acceptance excused a shortfall")
        (found,) = self.spacing(lines)
        self.assertTrue(found[3].endswith("accepted_exceptions[0]"), found)
        self.assertIn(words, found[4])
        # the shortfall stays the layout rule check's own violation
        self.assertTrue(self.ordinary(lines), lines)

    def test_an_unsigned_entry_is_not_honoured_and_fails_naming_it(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C4: An entry whose accepted_by is a placeholder or empty, or whose accepted_on is invalid, later than the day of the run or later than the record's own accepted_on, fails; so does one whose accepted_mm is at or above the figure it relaxes, one naming a pad or net the layout lacks, and one that no reported shortfall uses. Each fails spacing_exception naming the entry, and an exception in an unsigned or synthetic-on-an-orderable-board record is never honoured. A signed entry used by a shortfall is out of scope here.
        for by in ("unsigned", "TBD", "<name>"):
            with self.subTest(accepted_by=by):
                self.setUp()
                self.assertNotHonoured(entry(*CLEARANCE, 0.8, by=by), f"accepted_by '{by}' is a placeholder")

    def test_an_entry_dated_after_the_record_or_after_today_is_not_honoured_and_fails_naming_it(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C4: An entry whose accepted_by is a placeholder or empty, or whose accepted_on is invalid, later than the day of the run or later than the record's own accepted_on, fails; so does one whose accepted_mm is at or above the figure it relaxes, one naming a pad or net the layout lacks, and one that no reported shortfall uses. Each fails spacing_exception naming the entry, and an exception in an unsigned or synthetic-on-an-orderable-board record is never honoured. A signed entry used by a shortfall is out of scope here.
        for on, words in (("2026-10-13", "later than the record's own accepted_on 2026-10-12"), ("2999-01-01", "later than today")):
            with self.subTest(accepted_on=on):
                self.setUp()
                self.assertNotHonoured(entry(*CLEARANCE, 0.8, on=on), words)

    def test_an_entry_accepting_no_less_than_the_figure_relaxes_nothing_and_fails_naming_it(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C4: An entry whose accepted_by is a placeholder or empty, or whose accepted_on is invalid, later than the day of the run or later than the record's own accepted_on, fails; so does one whose accepted_mm is at or above the figure it relaxes, one naming a pad or net the layout lacks, and one that no reported shortfall uses. Each fails spacing_exception naming the entry, and an exception in an unsigned or synthetic-on-an-orderable-board record is never honoured. A signed entry used by a shortfall is out of scope here.
        self.assertNotHonoured(entry(*CLEARANCE, 1.0), "relaxes nothing")

    def test_an_entry_naming_a_pad_or_net_the_layout_lacks_fails_naming_it(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C4: An entry whose accepted_by is a placeholder or empty, or whose accepted_on is invalid, later than the day of the run or later than the record's own accepted_on, fails; so does one whose accepted_mm is at or above the figure it relaxes, one naming a pad or net the layout lacks, and one that no reported shortfall uses. Each fails spacing_exception naming the entry, and an exception in an unsigned or synthetic-on-an-orderable-board record is never honoured. A signed entry used by a shortfall is out of scope here.
        for between in (("J1.1", "J9.9"), ("J1.1", "/NO_SUCH_NET")):
            with self.subTest(between=between):
                self.setUp()
                self.assertNotHonoured(entry("mains_to_mains", "clearance", between, 0.8), f"names {between[1]}, which the layout has neither")

    def test_an_entry_that_no_shortfall_uses_fails_naming_it(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C4: An entry whose accepted_by is a placeholder or empty, or whose accepted_on is invalid, later than the day of the run or later than the record's own accepted_on, fails; so does one whose accepted_mm is at or above the figure it relaxes, one naming a pad or net the layout lacks, and one that no reported shortfall uses. Each fails spacing_exception naming the entry, and an exception in an unsigned or synthetic-on-an-orderable-board record is never honoured. A signed entry used by a shortfall is out of scope here.
        board_prove.exceptions(entry(*CLEARANCE, 0.5))(self.seed)
        status, lines = self.check()
        self.assertEqual(status, 1)
        (found,) = self.spacing(lines)
        self.assertIn("reports no shortfall", found[4])
        self.assertEqual(self.accepted(lines), [])

    def test_an_exception_in_an_unsigned_record_is_never_honoured(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C4: An entry whose accepted_by is a placeholder or empty, or whose accepted_on is invalid, later than the day of the run or later than the record's own accepted_on, fails; so does one whose accepted_mm is at or above the figure it relaxes, one naming a pad or net the layout lacks, and one that no reported shortfall uses. Each fails spacing_exception naming the entry, and an exception in an unsigned or synthetic-on-an-orderable-board record is never honoured. A signed entry used by a shortfall is out of scope here.
        for changes in (("accepted_by: david", "accepted_by: unsigned"), ("accepted_on: 2026-10-12", "accepted_on: 2999-01-01")):
            with self.subTest(changes=changes):
                self.setUp()
                board_prove.TERMINAL_SHORTFALL(self.seed)
                board_prove.exceptions(entry(*CLEARANCE, 0.8))(self.seed)
                board_prove.record(*changes)(self.seed)
                status, lines = self.check()
                self.assertEqual(status, 1)
                self.assertEqual(self.accepted(lines), [])
                self.assertTrue([v for v in self.violations(lines) if v[2] == "separation_basis"], lines)

    def test_an_exception_in_a_synthetic_record_of_an_orderable_board_is_never_honoured(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C4: An entry whose accepted_by is a placeholder or empty, or whose accepted_on is invalid, later than the day of the run or later than the record's own accepted_on, fails; so does one whose accepted_mm is at or above the figure it relaxes, one naming a pad or net the layout lacks, and one that no reported shortfall uses. Each fails spacing_exception naming the entry, and an exception in an unsigned or synthetic-on-an-orderable-board record is never honoured. A signed entry used by a shortfall is out of scope here.
        board_prove.TERMINAL_SHORTFALL(self.seed)
        board_prove.exceptions(entry(*CLEARANCE, 0.8))(self.seed)
        self.seed.project(lambda data: data["text_variables"].pop("NOT_FOR_MANUFACTURE"))
        status, lines = self.check()
        self.assertEqual(status, 1)
        self.assertEqual(self.accepted(lines), [])
        self.assertTrue([v for v in self.violations(lines) if v[2] == "separation_basis" and "marked synthetic" in v[4]], lines)

    def test_an_exception_for_one_pad_pair_of_a_part_does_not_excuse_another_pair_of_its_pads(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C7: On a seeded layout with an entry for one pad pair of a part and a shortfall at the same part between a different pair of its pads, the first is reported as an accepted exception and the second fails as an ordinary violation naming its pads. An entry written for the part as a whole, without a pair, fails the record reader. Pairs of different parts are out of scope here.
        board_prove.CREEPAGE_SHORTFALL(self.seed)
        board_prove.exceptions(entry(*CREEPAGE_FIRST, 13.0))(self.seed)
        status, lines = self.check()
        self.assertEqual(status, 1)
        (line,) = self.accepted(lines)
        self.assertIn("between R1.2 and J2.1", line[4])
        (other,) = self.ordinary(lines)
        self.assertEqual(other[2], "creepage")
        self.assertIn("pad 2 [/MAINS_N] of R1", other[3])
        self.assertIn("pad 2 [/LV_B] of J2", other[3])
        self.assertIn("actual 13.4058 mm", other[4])
        self.assertEqual(self.spacing(lines), [])


class TheExceptionsKeepTheTrackedDesignsPassing(unittest.TestCase):
    """Every design the repository tracks passes the check with the exceptions judged, none of them carrying one."""

    def test_every_tracked_design_passes_and_none_of_them_holds_an_exception(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C6: Every tracked design passes the check, in the build round for board changes and nightly on main. The hardware notes' record-key list, checks table and adopter section state accepted_exceptions, spacing_exception and the report line, and say that an exception is signed by the record's owner and that an adopter writes their own. The exceptions of the machine's own record are out of scope; the record leaf adds them.
        tracked = sorted(subprocess.run(["git", "ls-files", "*.kicad_pro"], cwd=board_prove.REPO, capture_output=True,
                                        text=True, check=True).stdout.split())
        self.assertTrue(tracked)
        for project in tracked:
            design = os.path.dirname(project)
            name = os.path.basename(design)
            with self.subTest(design=name), tempfile.TemporaryDirectory(prefix="board-test-") as scratch:
                seed = board_prove.prepare(scratch, design, name)
                with open(seed.path("separation-basis.yaml"), encoding="utf-8") as handle:
                    self.assertFalse(yaml.safe_load(handle).get("accepted_exceptions"))
                status, lines, stderr = board_prove.check(seed, KICAD_CLI)
                self.assertNotEqual(status, 2, stderr)
                self.assertEqual(status, 0, lines)
                self.assertEqual([line for line in lines if line.startswith(("VIOLATION", "ACCEPTED"))], [])


class TheSpacingExceptionRules(Proved):
    """Each new failure of the judgement fails on a fault seeded for it in a throwaway copy of the proof design."""

    #: The seeded faults the proof must hold, each with the rule that must report it and the words its line must carry.
    FAULTS = {
        "a shortfall below the distance its exception accepts": ("down to 0.9 mm", "leaves 0.84 mm"),
        "an exception that is unsigned": ("accepted_by 'unsigned' is a placeholder",),
        "an exception that no shortfall uses": ("where the layout rule check reports no shortfall",),
    }

    def test_each_new_failure_is_caught_on_a_seeded_fault_under_spacing_exception(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C5: The on-demand seeded-fault proof gains a row for a shortfall below its accepted distance, one for an unsigned entry and one for an unused entry, each made in a copy outside the tracked tree and caught under spacing_exception; the rows join the proof's required-names dictionary. A seeded run with the entry correct and used passes. Faults in rules this leaf does not touch are out of scope and get no row.
        self.assertCaught(*self.FAULTS)
        found = outcomes()
        for name, words in self.FAULTS.items():
            with self.subTest(fault=name):
                fields = found[name][1].split(" | ")
                self.assertEqual((fields[1], fields[2]), ("hardware/proof/gate-proof/gate-proof.kicad_pro", "spacing_exception"))
                for word in words:
                    self.assertIn(word, found[name][1])
                self.assertEqual([entry[2] for entry in board_prove.FAULTS if entry[0] == name], ["spacing_exception"])


class TheSpacingExceptionRowsOfTheProof(unittest.TestCase):
    """The rows the proof holds for the spacing exceptions, read without running it."""

    def test_the_proof_holds_a_row_for_each_of_the_three_failures_and_for_no_rule_this_leaf_leaves_alone(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C5: The on-demand seeded-fault proof gains a row for a shortfall below its accepted distance, one for an unsigned entry and one for an unused entry, each made in a copy outside the tracked tree and caught under spacing_exception; the rows join the proof's required-names dictionary. A seeded run with the entry correct and used passes. Faults in rules this leaf does not touch are out of scope and get no row.
        rows = [fault for fault in board_prove.FAULTS if fault[1].startswith("accepted exceptions:")]
        self.assertEqual(sorted(fault[0] for fault in rows), sorted(TheSpacingExceptionRules.FAULTS))
        self.assertEqual(len(rows), 3)
        # each is seeded in a copy of the gate's proof design outside the tracked tree
        self.assertEqual({board_prove.target_of(fault) for fault in rows}, {(board_prove.DESIGN, board_prove.NAME)})
        # and the rules the leaf did not touch keep exactly the rows they had
        self.assertEqual(len([fault for fault in board_prove.FAULTS if fault[1].startswith("mains to mains:")]), 8)
        self.assertEqual(len([fault for fault in board_prove.FAULTS if fault[1].startswith("mounting holes:")]), 5)
        self.assertEqual(len([fault for fault in board_prove.FAULTS if fault[1].startswith("separation floor:")]), 4)
        # a seeded fault copies the design and edits the copy; the tracked records hold no exception
        with open(os.path.join(board_prove.REPO, board_prove.DESIGN, "separation-basis.yaml"), encoding="utf-8") as handle:
            self.assertNotIn("accepted_exceptions", handle.read())


if __name__ == "__main__":
    unittest.main()
