#!/usr/bin/env python3
"""The pre-order check against KiCad itself, on the throwaway proof design, here the owner's net-pair spacing exceptions.

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
from fractions import Fraction

import yaml

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import board_prove  # noqa: E402
import sexpr  # noqa: E402
from board_kicad_fixtures import load_tests, setUpModule  # noqa: E402,F401
from board_kicad_fixtures import Copy, Proved, outcomes  # noqa: E402

pair = board_prove.net_pair_entry
Q = sexpr.Quoted
#: The band rows the faults read: at 125 V the creepage band is 0.5 mm and the clearance band 0.4 mm.
BANDS = board_prove.NET_PAIR_BANDS


def via_beside_mains_l(seed) -> None:
    """A via on /MAINS_N 0.3 mm from the edge of the /MAINS_L track, which leaves a clearance and a creepage shortfall."""
    via = ["via", ["at", "12.5", "10.95"], ["size", "0.8"], ["drill", "0.4"], ["layers", Q("F.Cu"), Q("B.Cu")],
           ["net", Q("/MAINS_N")], ["uuid", Q("0b0e5c1a-0000-4000-8000-000000000e01")]]
    seed.layout(lambda tree: tree.insert(len(tree) - 1, via))


def zone_beside_j1_pad(seed) -> None:
    """A fill of /MAINS_N that KiCad leaves 0.6005 mm from J1 pad 1, on /MAINS_L: a creepage shortfall."""
    zone = ["zone", ["net", Q("/MAINS_N")], ["layer", Q("F.Cu")], ["uuid", Q("0b0e5c1a-0000-4000-8000-000000000f01")],
            ["hatch", "edge", "0.5"], ["connect_pads", ["clearance", "0.2"]], ["min_thickness", "0.25"],
            ["fill", ["thermal_gap", "0.5"], ["thermal_bridge_width", "0.5"]],
            ["polygon", ["pts", ["xy", "11", "10.5"], ["xy", "14", "10.5"], ["xy", "14", "11.5"], ["xy", "11", "11.5"]]]]
    seed.layout(lambda tree: tree.insert(len(tree) - 1, zone))


class NetPairExceptionsRunDirectly(Copy):
    def accepted(self, lines):
        return [line.split(" | ") for line in lines if line.startswith("ACCEPTED | ")]

    def spacing(self, lines):
        return [v for v in self.violations(lines) if v[2] == "spacing_exception"]

    def ordinary(self, lines):
        return [v for v in self.violations(lines) if v[2] in ("clearance", "creepage")]

    def test_a_pad_to_pad_clearance_shortfall_at_or_above_the_accepted_distance_is_one_accepted_line_and_the_design_passes(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C3: The pure helper judging one entry against the basis, called with no layout, finds a well-formed signed entry sound and a flawed one flawed with the same findings the check reports. On a synthetic layout with a signed entry, net-pair entries being judged after the between and same-connector entries, a creepage shortfall between a pad of a net in nets_a and a track of a net in nets_b at or above accepted_mm is printed as one ACCEPTED line per entry carrying the constraint, both lists, the number of shortfalls covered, the narrowest reported distance, the accepted distance, the signed figure, the working voltage with its band figure, the reason and the bounding element, and fails nothing. The same holds for a via and a zone as either item, and for a pair inside nets_a where nets_b is omitted. Out of scope is a shortfall outside the lists.
        board_prove.TERMINAL_SHORTFALL(self.seed)
        BANDS(self.seed)
        board_prove.exceptions(pair("clearance", ("/MAINS_L",), 125, 0.8, ("/MAINS_N",)))(self.seed)
        status, lines = self.check()
        self.assertEqual(status, 0, lines)
        (line,) = self.accepted(lines)
        self.assertEqual(line[2], "spacing_exception")
        self.assertTrue(line[3].endswith("separation-basis.yaml accepted_exceptions[0]"), line)
        for words in ("net pair mains_to_mains clearance between [/MAINS_L] and [/MAINS_N]", "1 of 1 shortfalls covered",
                      "narrowest 0.84 mm", "accepted down to 0.8 mm", "against the signed 1 mm", "working voltage 125 V, band 0.4 mm",
                      "reason: synthetic -- a divider chain", "bounded by: synthetic -- an independent element"):
            self.assertIn(words, line[4])
        self.assertEqual(self.violations(lines), [], lines)

    def test_a_pair_inside_nets_a_with_nets_b_omitted_is_accepted_the_same(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C3: The pure helper judging one entry against the basis, called with no layout, finds a well-formed signed entry sound and a flawed one flawed with the same findings the check reports. On a synthetic layout with a signed entry, net-pair entries being judged after the between and same-connector entries, a creepage shortfall between a pad of a net in nets_a and a track of a net in nets_b at or above accepted_mm is printed as one ACCEPTED line per entry carrying the constraint, both lists, the number of shortfalls covered, the narrowest reported distance, the accepted distance, the signed figure, the working voltage with its band figure, the reason and the bounding element, and fails nothing. The same holds for a via and a zone as either item, and for a pair inside nets_a where nets_b is omitted. Out of scope is a shortfall outside the lists.
        board_prove.TERMINAL_SHORTFALL(self.seed)
        BANDS(self.seed)
        board_prove.exceptions(pair("clearance", ("/MAINS_N", "/MAINS_L"), 125, 0.8))(self.seed)
        status, lines = self.check()
        self.assertEqual(status, 0, lines)
        (line,) = self.accepted(lines)
        self.assertIn("between [/MAINS_N, /MAINS_L] and [/MAINS_N, /MAINS_L]", line[4])

    def test_a_track_beside_a_track_is_accepted_for_both_constraints_by_two_entries(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C3: The pure helper judging one entry against the basis, called with no layout, finds a well-formed signed entry sound and a flawed one flawed with the same findings the check reports. On a synthetic layout with a signed entry, net-pair entries being judged after the between and same-connector entries, a creepage shortfall between a pad of a net in nets_a and a track of a net in nets_b at or above accepted_mm is printed as one ACCEPTED line per entry carrying the constraint, both lists, the number of shortfalls covered, the narrowest reported distance, the accepted distance, the signed figure, the working voltage with its band figure, the reason and the bounding element, and fails nothing. The same holds for a via and a zone as either item, and for a pair inside nets_a where nets_b is omitted. Out of scope is a shortfall outside the lists.
        board_prove.mains_beside_mains(0.55)(self.seed)
        BANDS(self.seed)
        board_prove.exceptions(pair("clearance", ("/MAINS_L",), 125, 0.5, ("/MAINS_N",)),
                               pair("creepage", ("/MAINS_L",), 125, 0.5, ("/MAINS_N",)))(self.seed)
        status, lines = self.check()
        found = self.accepted(lines)
        self.assertEqual(len(found), 2, lines)
        self.assertIn("mains_to_mains clearance", found[0][4])
        self.assertIn("mains_to_mains creepage", found[1][4])
        for line in found:
            self.assertIn("narrowest 0.55 mm", line[4])
        self.assertEqual(self.ordinary(lines), [])
        self.assertEqual(self.spacing(lines), [])

    def test_a_via_stands_as_either_item_and_is_accepted_for_both_constraints(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C3: The pure helper judging one entry against the basis, called with no layout, finds a well-formed signed entry sound and a flawed one flawed with the same findings the check reports. On a synthetic layout with a signed entry, net-pair entries being judged after the between and same-connector entries, a creepage shortfall between a pad of a net in nets_a and a track of a net in nets_b at or above accepted_mm is printed as one ACCEPTED line per entry carrying the constraint, both lists, the number of shortfalls covered, the narrowest reported distance, the accepted distance, the signed figure, the working voltage with its band figure, the reason and the bounding element, and fails nothing. The same holds for a via and a zone as either item, and for a pair inside nets_a where nets_b is omitted. Out of scope is a shortfall outside the lists.
        via_beside_mains_l(self.seed)
        BANDS(self.seed)
        board_prove.exceptions(pair("clearance", ("/MAINS_N",), 50, 0.2, ("/MAINS_L",)),
                               pair("creepage", ("/MAINS_L",), 50, 0.3, ("/MAINS_N",)))(self.seed)
        status, lines = self.check()
        found = self.accepted(lines)
        self.assertEqual(len(found), 2, lines)
        for line in found:
            self.assertIn("narrowest 0.3 mm", line[4])
            self.assertIn("working voltage 50 V", line[4])
        self.assertEqual(self.ordinary(lines), [], lines)
        self.assertEqual(self.spacing(lines), [], lines)

    def test_a_zone_stands_as_either_item(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C3: The pure helper judging one entry against the basis, called with no layout, finds a well-formed signed entry sound and a flawed one flawed with the same findings the check reports. On a synthetic layout with a signed entry, net-pair entries being judged after the between and same-connector entries, a creepage shortfall between a pad of a net in nets_a and a track of a net in nets_b at or above accepted_mm is printed as one ACCEPTED line per entry carrying the constraint, both lists, the number of shortfalls covered, the narrowest reported distance, the accepted distance, the signed figure, the working voltage with its band figure, the reason and the bounding element, and fails nothing. The same holds for a via and a zone as either item, and for a pair inside nets_a where nets_b is omitted. Out of scope is a shortfall outside the lists.
        zone_beside_j1_pad(self.seed)
        BANDS(self.seed)
        board_prove.exceptions(pair("creepage", ("/MAINS_L",), 125, 0.6, ("/MAINS_N",)))(self.seed)
        status, lines = self.check()
        (line,) = self.accepted(lines)
        self.assertIn("net pair mains_to_mains creepage between [/MAINS_L] and [/MAINS_N]", line[4])
        self.assertIn("narrowest 0.6005 mm", line[4])
        self.assertIn("band 0.5 mm", line[4])
        self.assertEqual(self.ordinary(lines), [], lines)

    def test_a_distance_below_the_accepted_one_fails_naming_the_entry_the_nets_and_both_distances(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C4: On the same layout a shortfall between a net inside a list and a net outside both lists, a shortfall of the constraint the entry does not name, a shortfall of a pair already judged by a between entry, and a shortfall below accepted_mm each fail, the last naming the entry, and a report with no distance counts as 0.0 mm and fails. Out of scope is the plated-hole form.
        board_prove.TERMINAL_SHORTFALL(self.seed)
        BANDS(self.seed)
        board_prove.exceptions(pair("clearance", ("/MAINS_L",), 125, 0.9, ("/MAINS_N",)))(self.seed)
        status, lines = self.check()
        self.assertEqual(status, 1, lines)
        self.assertEqual(self.accepted(lines), [])
        (found,) = self.spacing(lines)
        self.assertTrue(found[3].endswith("separation-basis.yaml accepted_exceptions[0]"), found)
        for words in ("[/MAINS_L] and [/MAINS_N]", "down to 0.9 mm", "leaves 0.84 mm"):
            self.assertIn(words, found[4])
        self.assertEqual(self.ordinary(lines), [], lines)

    def test_the_other_constraint_of_the_same_pair_stays_the_ordinary_violation(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C4: On the same layout a shortfall between a net inside a list and a net outside both lists, a shortfall of the constraint the entry does not name, a shortfall of a pair already judged by a between entry, and a shortfall below accepted_mm each fail, the last naming the entry, and a report with no distance counts as 0.0 mm and fails. Out of scope is the plated-hole form.
        board_prove.mains_beside_mains(0.55)(self.seed)
        BANDS(self.seed)
        board_prove.exceptions(pair("clearance", ("/MAINS_L",), 125, 0.5, ("/MAINS_N",)))(self.seed)
        status, lines = self.check()
        self.assertEqual(status, 1, lines)
        self.assertEqual(len(self.accepted(lines)), 1)
        self.assertEqual([v[2] for v in self.ordinary(lines)], ["creepage"], lines)
        self.assertEqual(self.spacing(lines), [])

    def test_a_between_entry_takes_the_shortfall_first_whatever_the_order_of_the_record(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C4: On the same layout a shortfall between a net inside a list and a net outside both lists, a shortfall of the constraint the entry does not name, a shortfall of a pair already judged by a between entry, and a shortfall below accepted_mm each fail, the last naming the entry, and a report with no distance counts as 0.0 mm and fails. Out of scope is the plated-hole form.
        board_prove.TERMINAL_SHORTFALL(self.seed)
        BANDS(self.seed)
        board_prove.exceptions(pair("clearance", ("/MAINS_L",), 125, 0.8, ("/MAINS_N",)),
                               board_prove.exception_entry("mains_to_mains", "clearance", ("J1.1", "J1.2"), 0.8))(self.seed)
        status, lines = self.check()
        self.assertEqual(len(self.accepted(lines)), 1, lines)
        self.assertIn("between J1.1 and J1.2", self.accepted(lines)[0][4])
        (found,) = self.spacing(lines)
        self.assertTrue(found[3].endswith("accepted_exceptions[0]"), found)
        self.assertIn("reports no shortfall", found[4])

    def test_an_entry_listing_a_low_voltage_net_fails_and_excuses_nothing(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C6: With the Mains class unresolved every net-pair entry fails closed, and an entry listing a net the layout lacks, a net outside the Mains class, both nets of a pair in held_at_reinforced on opposite sides, or covering no reported shortfall fails as spacing_exception naming the entry, and a record that is unsigned or synthetic on an orderable board is honoured for no entry. Out of scope is a shortfall the check does not report.
        board_prove.TERMINAL_SHORTFALL(self.seed)
        BANDS(self.seed)
        board_prove.exceptions(pair("clearance", ("/MAINS_L", "/LV_A"), 125, 0.8, ("/MAINS_N",)))(self.seed)
        status, lines = self.check()
        self.assertEqual(status, 1, lines)
        self.assertEqual(self.accepted(lines), [])
        (found,) = self.spacing(lines)
        self.assertIn("/LV_A, which is not in the Mains net class", found[4])
        self.assertTrue(self.ordinary(lines), lines)

    def test_a_record_with_no_band_rows_honours_no_entry(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C5: An entry whose acceptance is empty, a placeholder, in angle brackets, later than today or later than the record's own, whose constraint is creepage and accepted_mm is below the creepage band figure for its working_voltage_v or below its clearance band figure, whose constraint is clearance and accepted_mm is below the clearance band figure for its working_voltage_v, whose accepted_mm is below 0.2 mm, whose working_voltage_v exceeds the record's working voltage or the highest band row, or whose accepted_mm is not below the figure of the rule that reports its shortfalls, fails as spacing_exception naming the entry and excuses nothing. Out of scope is any entry of another form.
        board_prove.TERMINAL_SHORTFALL(self.seed)
        board_prove.exceptions(pair("clearance", ("/MAINS_L",), 125, 0.8, ("/MAINS_N",)))(self.seed)
        status, lines = self.check()
        self.assertEqual(status, 1, lines)
        self.assertEqual(self.accepted(lines), [])
        (found,) = self.spacing(lines)
        self.assertIn("give no clearance_mm for 125 V", found[4])
        self.assertTrue(self.ordinary(lines), lines)

    def test_an_entry_in_an_unsigned_record_or_a_synthetic_record_of_an_orderable_board_is_never_honoured(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C6: With the Mains class unresolved every net-pair entry fails closed, and an entry listing a net the layout lacks, a net outside the Mains class, both nets of a pair in held_at_reinforced on opposite sides, or covering no reported shortfall fails as spacing_exception naming the entry, and a record that is unsigned or synthetic on an orderable board is honoured for no entry. Out of scope is a shortfall the check does not report.
        board_prove.TERMINAL_SHORTFALL(self.seed)
        BANDS(self.seed)
        board_prove.exceptions(pair("clearance", ("/MAINS_L",), 125, 0.8, ("/MAINS_N",)))(self.seed)
        self.seed.replace("separation-basis.yaml", "accepted_by: david\naccepted_on: 2026-10-12\nsynthetic: true",
                          "accepted_by: david\naccepted_on: 2999-01-01\nsynthetic: true")
        status, lines = self.check()
        self.assertEqual(status, 1, lines)
        self.assertEqual(self.accepted(lines), [])
        self.assertTrue([v for v in self.violations(lines) if v[2] == "separation_basis" and "later than today" in v[4]], lines)


class TheExceptionsKeepTheTrackedDesignsPassing(unittest.TestCase):
    """Every design the repository tracks passes the check with the net-pair form judged, none of them carrying an entry or a seeded band row."""

    def test_every_tracked_design_passes_with_no_net_pair_entry_and_no_seeded_band_row(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C8: The check over every tracked design reports no new failure, and hardware/README.md states the net-pairs form in the record keys, the reader row, the spacing_exception row and the adopter step for exceptions, including that the working voltage is the owner's assertion and the check does not recompute it. Out of scope is the main board's own design, whose record entries are another leaf's.
        tracked = sorted(subprocess.run(["git", "ls-files", "*.kicad_pro"], cwd=board_prove.REPO, capture_output=True,
                                        text=True, check=True).stdout.split())
        self.assertTrue(tracked)
        from board_kicad_fixtures import KICAD_CLI
        for project in tracked:
            design = os.path.dirname(project)
            name = os.path.basename(design)
            with self.subTest(design=name), tempfile.TemporaryDirectory(prefix="board-test-") as scratch:
                seed = board_prove.prepare(scratch, design, name)
                with open(seed.path("separation-basis.yaml"), encoding="utf-8") as handle:
                    text = handle.read()
                self.assertNotIn(board_check.NET_PAIR_FORM_KEY, text)
                self.assertNotIn("synthetic band table", text)
                status, lines, stderr = board_prove.check(seed, KICAD_CLI)
                self.assertNotEqual(status, 2, stderr)
                self.assertEqual(status, 0, lines)
                self.assertEqual([line for line in lines if line.startswith(("VIOLATION", "ACCEPTED"))], [])


class TheNetPairExceptionRules(Proved):
    """Each new failure of the judgement fails on a fault seeded for it in a throwaway copy of the proof design."""

    #: The seeded faults the proof must hold, each with the rule that must report it and the words its line must carry.
    FAULTS = {
        "a net-pair entry lacking its working voltage": ("separation_basis", ("accepted_exceptions[0].working_voltage_v", "lacks working_voltage_v")),
        "a net-pair entry that is unsigned": ("spacing_exception", ("accepted_by 'unsigned' is a placeholder",)),
        "a net-pair creepage entry below the creepage band figure": ("spacing_exception", ("below the band creepage 0.5 mm",)),
        "a net-pair creepage entry below the clearance band figure": ("spacing_exception", ("below the band clearance 0.7 mm",)),
        "a net-pair entry accepting the rule's own figure": ("spacing_exception", ("relaxes nothing",)),
        "a net-pair entry listing a net the layout lacks": ("spacing_exception", ("/MAINS_X, which the layout lacks",)),
        "a net-pair entry listing a net outside the Mains class": ("spacing_exception", ("/LV_A, which is not in the Mains net class",)),
        "a net-pair entry across the pair held at reinforced": ("spacing_exception", ("the pair held at reinforced across the open contact",)),
        "a net-pair entry at a working voltage above the highest band row": ("spacing_exception", ("above the highest functional band row",)),
        "a net-pair entry that no shortfall uses": ("spacing_exception", ("reports no shortfall",)),
        "a shortfall between nets outside a net-pair entry's lists": ("clearance", ("pad 1 [/MAINS_L] of J1", "pad 2 [/MAINS_N] of J1")),
        "a shortfall below the distance a net-pair entry accepts": ("spacing_exception", ("down to 0.9 mm", "leaves 0.84 mm")),
    }

    def test_each_new_failure_is_caught_on_a_seeded_fault_under_the_rule_named_for_it(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C7: The proof run seeds into a throwaway copy of a proof design, never the tracked design, one fault for each failure of this leaf's criteria (a malformed entry, an unsigned entry, an accepted_mm below the band figure, below the clearance, not below the rule figure, an absent net, a net outside the Mains class, the open-contact pair, a working voltage above the top row, an entry no shortfall uses, a shortfall outside the lists, a shortfall below the accepted distance), requires each to fail under its rule name, and requires the unseeded design to pass first. Out of scope is any fault not listed.
        self.assertCaught(*self.FAULTS)
        found = outcomes()
        for name, (rule, words) in self.FAULTS.items():
            with self.subTest(fault=name):
                fields = found[name][1].split(" | ")
                self.assertEqual((fields[1], fields[2]), ("hardware/proof/gate-proof/gate-proof.kicad_pro", rule))
                for word in words:
                    self.assertIn(word, found[name][1])
                self.assertEqual([entry[2] for entry in board_prove.FAULTS if entry[0] == name], [rule])


class TheNetPairExceptionRowsOfTheProof(unittest.TestCase):
    """The rows the proof holds for the net-pair exceptions, read without running it."""

    def test_the_proof_holds_one_row_for_each_of_the_twelve_failures_and_leaves_the_other_rules_their_rows(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C7: The proof run seeds into a throwaway copy of a proof design, never the tracked design, one fault for each failure of this leaf's criteria (a malformed entry, an unsigned entry, an accepted_mm below the band figure, below the clearance, not below the rule figure, an absent net, a net outside the Mains class, the open-contact pair, a working voltage above the top row, an entry no shortfall uses, a shortfall outside the lists, a shortfall below the accepted distance), requires each to fail under its rule name, and requires the unseeded design to pass first. Out of scope is any fault not listed.
        rows = [fault for fault in board_prove.FAULTS if fault[1].startswith("net-pair exceptions:")]
        self.assertEqual(sorted(fault[0] for fault in rows), sorted(TheNetPairExceptionRules.FAULTS))
        self.assertEqual(len(rows), 12)
        # each is seeded in a copy of the gate's proof design outside the tracked tree
        self.assertEqual({board_prove.target_of(fault) for fault in rows}, {(board_prove.DESIGN, board_prove.NAME)})
        # and the rules the leaf did not touch keep exactly the rows they had
        for prefix, count in (("accepted exceptions:", 3), ("mains to mains:", 8), ("mounting holes:", 5),
                              ("separation floor:", 4), ("same-connector exceptions:", 8)):
            with self.subTest(prefix=prefix):
                self.assertEqual(len([fault for fault in board_prove.FAULTS if fault[1].startswith(prefix)]), count)
        # the tracked record holds no entry and no band row: a fault copies the design and edits the copy
        with open(os.path.join(board_prove.REPO, board_prove.DESIGN, "separation-basis.yaml"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertNotIn(board_check.NET_PAIR_FORM_KEY, text)
        self.assertNotIn("synthetic band table", text)

    def test_every_row_seeds_its_edits_into_a_copy_and_the_unseeded_record_gains_nothing(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C7: The proof run seeds into a throwaway copy of a proof design, never the tracked design, one fault for each failure of this leaf's criteria (a malformed entry, an unsigned entry, an accepted_mm below the band figure, below the clearance, not below the rule figure, an absent net, a net outside the Mains class, the open-contact pair, a working voltage above the top row, an entry no shortfall uses, a shortfall outside the lists, a shortfall below the accepted distance), requires each to fail under its rule name, and requires the unseeded design to pass first. Out of scope is any fault not listed.
        with tempfile.TemporaryDirectory(prefix="board-test-") as scratch:
            seed = board_prove.prepare(scratch)
            before = seed.read("separation-basis.yaml")
            board_prove.band_rows((50, 0.3, 0.2))(seed)
            board_prove.exceptions(pair("clearance", ("/MAINS_L",), 125, 0.8, ("/MAINS_N",)))(seed)
            after = yaml.safe_load(seed.read("separation-basis.yaml"))
            self.assertEqual(len(after["table_rows"]), len(yaml.safe_load(before)["table_rows"]) + 1)
            self.assertEqual(after["accepted_exceptions"][0]["nets_a"], ["/MAINS_L"])
            self.assertEqual(after["accepted_exceptions"][0]["working_voltage_v"], 125)
        self.assertEqual(board_check.band_figure(after, "creepage_mm", 50), Fraction("0.3"))


if __name__ == "__main__":
    unittest.main()
