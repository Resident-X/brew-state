#!/usr/bin/env python3
"""The pre-order check's reading and judgement of the owner's workmanship acceptance record, driven on synthetic fixtures with no KiCad involved.

What is under test here is what the check decides for itself: whether the record
is in the one form it is read in, and what each entry makes of the workmanship
and neatness lines a design's check reported, given as the report writes them.
What KiCad then reports of a seeded layout is driven against the real tool in
test_board_check_kicad_workmanship_acceptance.py.
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
import board_fixtures  # noqa: E402

TODAY = datetime.date(2026, 11, 7)
FOLDER = "hardware/synth/board"
PROJECT = f"{FOLDER}/board.kicad_pro"
LAYOUT = f"{FOLDER}/board.kicad_pcb"
RECORD = f"{FOLDER}/{board_check.WORKMANSHIP_ACCEPTANCE_NAME}"
YAML = board_check.require_yaml()


def entry(rule="workmanship_detour", scope="/NET_A", count=1, **changed) -> dict:
    """A well-formed, signed entry of the record, with `changed` keys replacing its own."""
    return {**{"rule": rule, "scope": scope, "count": count, "reason": "a synthetic ground for the test",
               "bounded_by": "a synthetic element, which is no real part", "accepted_by": "test-owner",
               "accepted_on": "2026-11-01"}, **changed}


def without(item: dict, key: str) -> dict:
    return {k: v for k, v in item.items() if k != key}


def line(rule="workmanship_detour", place="net /NET_A: 3 pads, from R1 at (10, 10) mm", message=None) -> board_check.Violation:
    """A line of the design's check as it reports one: the figure measured against the figure allowed."""
    return board_check.Violation(PROJECT, rule, place, message or f"{rule} measured 1.50 times, where the figure allows 1.3 times")


class Synthetic(unittest.TestCase):
    """A design in a repository of its own, with two nets and the parts R1, R2, TP1 and D1, and a record beside it."""

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="workmanship-acceptance-")
        self.addCleanup(self.scratch.cleanup)
        self.root = self.scratch.name
        self.variables = {"MAINS": "none", "NOT_FOR_MANUFACTURE": "true", "WORK_DETOUR_RATIO": "1.3"}
        self.tracked = [PROJECT, LAYOUT]
        self.write(LAYOUT, board_fixtures.layout([
            board_fixtures.footprint("R1", 10, 10, [board_fixtures.pad(1, 0, 0, "/NET_A", "passive")]),
            board_fixtures.footprint("R2", 30, 10, [board_fixtures.pad(1, 0, 0, "/NET_B", "passive")]),
            board_fixtures.footprint("TP1", 10, 30, [board_fixtures.pad(1, 0, 0, "/NET_B", "passive")]),
            board_fixtures.footprint("D1", 30, 30, [board_fixtures.pad(1, 0, 0, "/NET_A", "passive")])]))

    def write(self, path: str, text: str) -> None:
        full = os.path.join(self.root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(text)

    RULES = f"{FOLDER}/board.kicad_dru"

    def region_rules(self, *names, extra="") -> None:
        """The design's rules file, tracked, holding a floorplan region rule for each of `names` in the form the floorplan gives."""
        text = "(version 1)\n" + "".join(
            f'(rule "{name}"\n\t(condition "A.Type == \'Footprint\' && A.intersectsArea(\'{name.split()[0].lower()}\') && '
            f'A.Reference != \'U9\'")\n\t(constraint disallow footprint))\n' for name in names) + extra
        self.write(self.RULES, text)
        if self.RULES not in self.tracked:
            self.tracked.append(self.RULES)

    def record(self, entries, **top) -> None:
        """The record as written beside the design, tracked; JSON is YAML."""
        self.write(RECORD, json.dumps({"accepted_workmanship": entries, "synthetic": True, **top}))
        if RECORD not in self.tracked:
            self.tracked.append(RECORD)

    def judge(self, lines, entries=None, **top):
        """(the violations left, the ACCEPTED report lines) of `lines` against a record of `entries`, none written when None."""
        if entries is not None:
            self.record(entries, **top)
        self.write(PROJECT, json.dumps({"text_variables": self.variables}))
        accepted: list = []
        left = board_check.judge_accepted_workmanship(YAML, board_check.Repository(self.root, self.tracked),
                                                      board_check.Design(PROJECT), TODAY, list(lines), accepted)
        return left, accepted

    def read(self, entries=None, **top):
        if entries is not None:
            self.record(entries, **top)
        self.write(PROJECT, json.dumps({"text_variables": self.variables}))
        return board_check.load_workmanship_acceptance(YAML, self.root, board_check.Repository(self.root, self.tracked),
                                                       board_check.Design(PROJECT),
                                                       self.variables.get("NOT_FOR_MANUFACTURE") == "true")

    def failures(self, left):
        return [v for v in left if v.rule == "workmanship_acceptance"]


class TheRecordForm(Synthetic):
    def test_a_malformed_entry_fails_the_record_naming_the_entry_and_the_key(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C1: On a synthetic design, an acceptance record with an entry that is not a mapping, one with a missing key, one with an extra key, two entries for the same rule and scope, and one with a count of zero each fail the check naming the entry and the key, and the same record with a well-formed entry does not fail as a record; a record with an explicit empty list of entries, and a design with no acceptance record at all, do not fail as a record and accept nothing, so every workmanship line of that design fails the check as before. Out of scope is the judgement of a well-formed entry.
        good = entry()
        cases = [
            ("an entry that is not a mapping", "just words", "accepted_workmanship[1]", "is not a mapping of the keys"),
            ("an extra key", dict(good, note="x"), "accepted_workmanship[1].note", "holds the key 'note'"),
            ("two entries for the same rule and scope", dict(good), "accepted_workmanship[1].scope",
             "repeats the rule 'workmanship_detour' and scope '/NET_A' of accepted_workmanship[0]"),
            ("a count of zero", entry(scope="/NET_B", count=0), "accepted_workmanship[1].count", "accepted_workmanship[1].count is 0"),
            ("a negative count", entry(scope="/NET_B", count=-2), "accepted_workmanship[1].count", "is -2"),
            ("a fractional count", entry(scope="/NET_B", count=1.5), "accepted_workmanship[1].count", "is 1.5"),
            ("a boolean count", entry(scope="/NET_B", count=True), "accepted_workmanship[1].count", "is True"),
            ("a count written as text", entry(scope="/NET_B", count="2"), "accepted_workmanship[1].count", "is '2'"),
        ] + [(f"a missing {key}", without(entry(scope="/NET_B"), key), f"accepted_workmanship[1].{key}", f"lacks {key}")
             for key in board_check.WORKMANSHIP_ENTRY_KEYS] + [
            (f"an empty {key}", dict(entry(scope="/NET_B"), **{key: " "}), f"accepted_workmanship[1].{key}", f"{key} is ' '")
            for key in ("rule", "scope", "reason", "bounded_by")]
        for name, bad, key, said in cases:
            with self.subTest(case=name):
                path, entries, problems = self.read([good, bad])
                self.assertEqual(path, RECORD)
                self.assertEqual([p.rule for p in problems], ["workmanship_acceptance"] * len(problems), problems)
                named = [p for p in problems if p.location == f"{RECORD} {key}"]
                self.assertTrue(named, f"no violation at {key}: {problems}")
                self.assertIn(said, named[0].message)
                self.assertIn(good, [e for _, e in entries], "the well-formed entry beside it is still read")

    def test_the_same_record_with_a_well_formed_entry_does_not_fail_as_a_record(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C1: On a synthetic design, an acceptance record with an entry that is not a mapping, one with a missing key, one with an extra key, two entries for the same rule and scope, and one with a count of zero each fail the check naming the entry and the key, and the same record with a well-formed entry does not fail as a record; a record with an explicit empty list of entries, and a design with no acceptance record at all, do not fail as a record and accept nothing, so every workmanship line of that design fails the check as before. Out of scope is the judgement of a well-formed entry.
        path, entries, problems = self.read([entry(), entry(rule="track_angle", scope="R1", count=4)])
        self.assertEqual((path, problems), (RECORD, []))
        self.assertEqual([(i, e["rule"]) for i, e in entries], [(0, "workmanship_detour"), (1, "track_angle")])
        # an explicit empty list is a record that accepts none, and the same rule and another scope are two entries
        self.assertEqual(self.read([])[1:], ([], []))
        self.assertEqual(self.read([entry(), entry(scope="/NET_B")])[2], [])

    def test_a_record_that_is_not_in_its_form_accepts_nothing_and_fails(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C1: On a synthetic design, an acceptance record with an entry that is not a mapping, one with a missing key, one with an extra key, two entries for the same rule and scope, and one with a count of zero each fail the check naming the entry and the key, and the same record with a well-formed entry does not fail as a record; a record with an explicit empty list of entries, and a design with no acceptance record at all, do not fail as a record and accept nothing, so every workmanship line of that design fails the check as before. Out of scope is the judgement of a well-formed entry.
        for name, text in (("a list in place of the mapping", "- rule: x\n"), ("an unknown top key", json.dumps({"accepted_workmanship": [], "extra": 1})),
                           ("no accepted_workmanship", json.dumps({"synthetic": True})),
                           ("accepted_workmanship that is no list", json.dumps({"accepted_workmanship": {}, "synthetic": True})),
                           ("a key given twice", '{"accepted_workmanship": [], "accepted_workmanship": []}')):
            with self.subTest(record=name):
                self.write(RECORD, text)
                self.tracked.append(RECORD)
                left, accepted = self.judge([line()])
                self.assertEqual(accepted, [])
                self.assertIn(line().rule, [v.rule for v in left], "the line still fails")
                self.assertTrue(self.failures(left), left)
                self.tracked.remove(RECORD)

    def test_an_explicit_empty_list_and_a_design_with_no_record_accept_nothing_and_every_line_fails_as_before(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C1: On a synthetic design, an acceptance record with an entry that is not a mapping, one with a missing key, one with an extra key, two entries for the same rule and scope, and one with a count of zero each fail the check naming the entry and the key, and the same record with a well-formed entry does not fail as a record; a record with an explicit empty list of entries, and a design with no acceptance record at all, do not fail as a record and accept nothing, so every workmanship line of that design fails the check as before. Out of scope is the judgement of a well-formed entry.
        lines = [line(rule) for rule in board_check.ACCEPTABLE_WORKMANSHIP]
        for name, entries in (("an explicit empty list", []), ("no record", None)):
            with self.subTest(record=name):
                self.setUp()
                left, accepted = self.judge(lines, entries)
                self.assertEqual(accepted, [])
                self.assertEqual([v.line() for v in left], [v.line() for v in lines], "no failure as a record, every line stands")
                self.assertEqual(self.failures(left), [])

    def test_a_design_with_no_record_is_judged_as_before_and_accepts_nothing(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C3: On the same synthetic design with a fourth line of the entry's rule at its place, with a line of a different workmanship rule, and with a line of the same rule at another place, each of those lines fails the check as before and the three covered lines still pass. Out of scope is the wording of the report.
        lines = [line(), line("track_angle", "Track [/NET_A] on F.Cu @ (1, 2) mm", "Track angle (rule 'Corners' min angle 135.000; actual 90.000)")]
        left, accepted = self.judge(lines)
        self.assertEqual(([v.line() for v in left], accepted), ([v.line() for v in lines], []))
        self.assertEqual(self.read()[:2], (None, []))

    def test_a_record_untracked_by_the_repository_is_not_read(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C4: On a synthetic design, an entry with an empty, placeholder or angle-bracketed accepted-by value, an entry with an empty, malformed or future date, an entry naming a rule outside the closed set the leaf states (each of hole_to_hole, workmanship_rule, workmanship_figure and workmanship_pad_copper, and any rule that is not a workmanship or neatness rule), a courtyards_overlap entry used by a line that names a custom rule such as the crystal keep-clear, an items_not_allowed entry used by a line that names a rule other than the floorplan region rule, an entry naming a mains spacing, derated-voltage or pin-limit rule, an entry for a place the design does not have, and an entry that no line uses each fail the check naming the entry, and a design marked synthetic is honoured only when it is marked not for manufacture. On the same design, for each of the nineteen names of the closed set (workmanship_detour, workmanship_pad_entry, workmanship_pad_corner, workmanship_width, workmanship_direction, track_angle, track_segment_length, courtyards_overlap, test_point_courtyard, designator_astray, silk_overlap, items_not_allowed, pour_gap, decoupling_via, starved_thermal, silk_over_copper, footprint_symbol_field_mismatch, footprint_symbol_mismatch and lib_footprint_mismatch), a signed entry at the place of a line of that name, with a count equal to the lines there, is accepted and used by that line, and the same entry fails as stale when no line of that name stands at its place; a signed entry whose accepted-by value reads 'david (signed by Claude on his standing instruction of 2026-11-07)' is accepted as signed. The same entry for side_fiducials, hole_to_hole, workmanship_rule, workmanship_figure or workmanship_pad_copper fails as naming a rule outside the set. Out of scope is a well-formed signed entry that a line uses.
        self.record([entry()])
        self.tracked.remove(RECORD)
        left, accepted = self.judge([line()])
        self.assertEqual(accepted, [])
        self.assertIn("workmanship_detour", [v.rule for v in left])
        self.assertTrue([v for v in self.failures(left) if "not tracked" in v.message], left)


class TheJudgement(Synthetic):
    def three(self):
        return [line(place=f"net /NET_A: {n} pads, from R1 at (10, 10) mm") for n in (3, 4, 5)]

    def test_three_lines_under_a_signed_entry_of_count_three_pass_and_are_reported_as_accepted(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C2: On a synthetic design with three lines of one workmanship rule at one place and a signed entry for that rule and place with a count of three, the check reports an ACCEPTED line naming the rule, the place, the measured figure against the allowed one and the reason, the three lines do not fail the check, and the check exits zero when they are its only lines, in the check's text report, which is its only report. Out of scope is any rule outside the closed set of workmanship and neatness rules the solution names.
        lines = self.three()
        left, accepted = self.judge(lines, [entry(count=3)])
        self.assertEqual(left, [], "the three lines do not fail the check, which has no other line")
        self.assertEqual(len(accepted), 3)
        for report, source in zip(accepted, lines):
            fields = [field.strip() for field in report.split(" | ")]
            self.assertEqual(fields[:3], ["ACCEPTED", PROJECT, "workmanship_acceptance"])
            self.assertEqual(fields[3], f"{RECORD} accepted_workmanship[0]")
            for said in ("workmanship_detour", source.location, "measured 1.50 times, where the figure allows 1.3 times",
                         "a synthetic ground for the test", "a synthetic element, which is no real part", "test-owner", "2026-11-01"):
                self.assertIn(said, fields[4])

    def test_the_check_has_no_other_report_than_its_text_report(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C2: On a synthetic design with three lines of one workmanship rule at one place and a signed entry for that rule and place with a count of three, the check reports an ACCEPTED line naming the rule, the place, the measured figure against the allowed one and the reason, the three lines do not fail the check, and the check exits zero when they are its only lines, in the check's text report, which is its only report. Out of scope is any rule outside the closed set of workmanship and neatness rules the solution names.
        shown = subprocess.run([sys.executable, os.path.join(TOOLS, "board_check.py"), "--help"], capture_output=True, text=True)
        self.assertEqual(shown.returncode, 0, shown.stderr)
        self.assertNotIn("json", shown.stdout.lower())
        self.assertNotIn("--format", shown.stdout)

    def test_a_fourth_line_a_line_of_another_rule_and_a_line_at_another_place_fail_as_before(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C3: On the same synthetic design with a fourth line of the entry's rule at its place, with a line of a different workmanship rule, and with a line of the same rule at another place, each of those lines fails the check as before and the three covered lines still pass. Out of scope is the wording of the report.
        covered = self.three()
        fourth = line(place="net /NET_A: 6 pads, from R1 at (10, 10) mm")
        other_rule = line("workmanship_width", "net /NET_A: Track [/NET_A] on F.Cu @ (1, 2) mm")
        other_place = line(place="net /NET_B: 3 pads, from R2 at (30, 10) mm")
        left, accepted = self.judge(covered + [fourth, other_rule, other_place], [entry(count=3)])
        self.assertEqual([v.line() for v in left], [v.line() for v in (fourth, other_rule, other_place)])
        self.assertEqual(len(accepted), 3)

    def test_an_entry_covers_the_lines_of_a_reference_designator_or_a_figure_it_names(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C3: On the same synthetic design with a fourth line of the entry's rule at its place, with a line of a different workmanship rule, and with a line of the same rule at another place, each of those lines fails the check as before and the three covered lines still pass. Out of scope is the wording of the report.
        at_r1 = line("test_point_courtyard", "R1 pad 1 at (10, 10) mm")
        at_r2 = line("test_point_courtyard", "R2 pad 1 at (30, 10) mm")
        left, accepted = self.judge([at_r1, at_r2], [entry("test_point_courtyard", "R1")])
        self.assertEqual([v.line() for v in left], [at_r2.line()])
        self.assertEqual(len(accepted), 1)
        by_figure = line(message="routes run direct: 1.50 times, where WORK_DETOUR_RATIO allows 1.3 times")
        elsewhere = line(message="routes run direct: 1.50 times, where a figure allows 1.3 times")
        left, accepted = self.judge([by_figure, elsewhere], [entry(scope="WORK_DETOUR_RATIO", count=2)])
        self.assertEqual([v.line() for v in left], [elsewhere.line()])
        self.assertEqual(len(accepted), 1)

    def test_a_reference_designator_is_matched_whole_and_a_net_by_its_own_name(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C3: On the same synthetic design with a fourth line of the entry's rule at its place, with a line of a different workmanship rule, and with a line of the same rule at another place, each of those lines fails the check as before and the three covered lines still pass. Out of scope is the wording of the report.
        near_miss = line("silk_overlap", "Footprint R10 @ (1, 2) mm")
        left, accepted = self.judge([near_miss], [entry("silk_overlap", "R1")])
        self.assertIn(near_miss.line(), [v.line() for v in left])
        self.assertEqual(accepted, [])
        kicad = line("track_angle", "Track [/NET_A] on F.Cu @ (1, 2) mm; Track [/NET_A] on F.Cu @ (3, 4) mm")
        left, accepted = self.judge([kicad], [entry("track_angle", "/NET_A")])
        self.assertEqual((left, len(accepted)), ([], 1))

    def test_an_entry_covers_up_to_its_count_across_entries_of_the_same_rule(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C3: On the same synthetic design with a fourth line of the entry's rule at its place, with a line of a different workmanship rule, and with a line of the same rule at another place, each of those lines fails the check as before and the three covered lines still pass. Out of scope is the wording of the report.
        lines = self.three()
        left, accepted = self.judge(lines, [entry(count=2), entry(scope="R1", count=1)])
        self.assertEqual(left, [])
        self.assertEqual(sorted(a.split(" | ")[3][-2] for a in accepted), ["0", "0", "1"])


class TheClosedSet(Synthetic):
    #: A line of each rule of the closed set as the check reports one, and the scope an entry for it names.
    LINES = {
        "workmanship_detour": (line("workmanship_detour"), "/NET_A"),
        "workmanship_pad_entry": (line("workmanship_pad_entry", "net /NET_A: Track [/NET_A] on F.Cu @ (1, 2) mm, entering R1 pad 1"), "/NET_A"),
        "workmanship_pad_corner": (line("workmanship_pad_corner", "net /NET_A: R1 pad 1 at (10, 10) mm on F.Cu"), "/NET_A"),
        "workmanship_width": (line("workmanship_width", "net /NET_A: Track [/NET_A] on F.Cu @ (1, 2) mm"), "/NET_A"),
        "workmanship_direction": (line("workmanship_direction", "net /NET_A: Track [/NET_A] on F.Cu @ (1, 2) mm"), "/NET_A"),
        "track_angle": (line("track_angle", "Track [/NET_A] on F.Cu @ (1, 2) mm", "Track angle (rule 'Corners' min angle 135.000; actual 90.000)"), "/NET_A"),
        "track_segment_length": (line("track_segment_length", "Track [/NET_A] on F.Cu @ (1, 2) mm", "Track segment length (rule 'Jog' min length 1.000 mm; actual 0.4 mm)"), "/NET_A"),
        "courtyards_overlap": (line("courtyards_overlap", "Footprint R1 @ (10, 10) mm; Footprint D1 @ (12, 10) mm", "Courtyards overlap (actual -0.5 mm)"), "R1"),
        "test_point_courtyard": (line("test_point_courtyard", "TP1 pad 1 at (10, 30) mm"), "TP1"),
        "designator_astray": (line("designator_astray", "R2 text at (30, 5) mm"), "R2"),
        "silk_overlap": (line("silk_overlap", "Footprint D1 @ (30, 30) mm; Footprint R2 @ (30, 10) mm"), "D1"),
        "items_not_allowed": (line("items_not_allowed", "Footprint D1 @ (30, 30) mm", "Items not allowed (rule 'Digital region parts')"), "D1"),
        "pour_gap": (line("pour_gap", "net /NET_A: pad 1 of R1 at (10, 10) mm on F.Cu", "MFG-6 pour gap: the pour stops 0.063 mm short of pad 1 of R1, narrower than the board's 0.09 mm minimum clearance"), "/NET_A"),
        "decoupling_via": (line("decoupling_via", "net /NET_A: via at (95.35, 34.25) mm, between pad 1 of R1 and pad 1 of D1", "DECOUPLE-6 no via sits between a decoupling capacitor's supply pad and the pin it decouples"), "/NET_A"),
        "starved_thermal": (line("starved_thermal", "Zone 'GND pour B.Cu' [/NET_A] on B.Cu, priority 0 @ (3.1, 119.1) mm; PTH pad 2 [/NET_A] of D1 @ (30, 30) mm", "Thermal relief connection to zone incomplete (layer B.Cu; zone min spoke count 2; actual 1)"), "D1"),
        "silk_over_copper": (line("silk_over_copper", "Reference field of R2 @ (30, 12) mm; Pad 3 [/NET_B] of TP1 on F.Cu @ (10, 30) mm", "Silkscreen clipped by solder mask"), "R2"),
        "footprint_symbol_field_mismatch": (line("footprint_symbol_field_mismatch", "Footprint D1 @ (30, 30) mm", "Field 'Description' differs (PCB: 'a', Schematic: 'b')"), "D1"),
        "footprint_symbol_mismatch": (line("footprint_symbol_mismatch", "Footprint R2 @ (30, 10) mm", "Footprint attributes don't match symbol: 'Do not populate' settings differ"), "R2"),
        "lib_footprint_mismatch": (line("lib_footprint_mismatch", "Footprint TP1 @ (10, 30) mm", "Footprint 'TP' does not match copy in library 'board'"), "TP1"),
    }
    #: The seven names the main board's check reports beyond the twelve workmanship and neatness ones.
    PARITY = ("pour_gap", "decoupling_via", "starved_thermal", "silk_over_copper", "footprint_symbol_field_mismatch",
              "footprint_symbol_mismatch", "lib_footprint_mismatch")

    def setUp(self):
        super().setUp()
        self.region_rules("Digital region parts")

    def test_an_entry_for_each_rule_of_the_closed_set_signed_and_used_by_a_line_of_that_rule_is_accepted(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C4: On a synthetic design, an entry with an empty, placeholder or angle-bracketed accepted-by value, an entry with an empty, malformed or future date, an entry naming a rule outside the closed set the leaf states (each of hole_to_hole, workmanship_rule, workmanship_figure and workmanship_pad_copper, and any rule that is not a workmanship or neatness rule), a courtyards_overlap entry used by a line that names a custom rule such as the crystal keep-clear, an items_not_allowed entry used by a line that names a rule other than the floorplan region rule, an entry naming a mains spacing, derated-voltage or pin-limit rule, an entry for a place the design does not have, and an entry that no line uses each fail the check naming the entry, and a design marked synthetic is honoured only when it is marked not for manufacture. On the same design, for each of the nineteen names of the closed set (workmanship_detour, workmanship_pad_entry, workmanship_pad_corner, workmanship_width, workmanship_direction, track_angle, track_segment_length, courtyards_overlap, test_point_courtyard, designator_astray, silk_overlap, items_not_allowed, pour_gap, decoupling_via, starved_thermal, silk_over_copper, footprint_symbol_field_mismatch, footprint_symbol_mismatch and lib_footprint_mismatch), a signed entry at the place of a line of that name, with a count equal to the lines there, is accepted and used by that line, and the same entry fails as stale when no line of that name stands at its place; a signed entry whose accepted-by value reads 'david (signed by Claude on his standing instruction of 2026-11-07)' is accepted as signed. The same entry for side_fiducials, hole_to_hole, workmanship_rule, workmanship_figure or workmanship_pad_copper fails as naming a rule outside the set. Out of scope is a well-formed signed entry that a line uses.
        self.assertEqual(sorted(self.LINES), sorted(board_check.ACCEPTABLE_WORKMANSHIP))
        for rule, (source, scope) in self.LINES.items():
            with self.subTest(rule=rule):
                left, accepted = self.judge([source], [entry(rule, scope)])
                self.assertEqual(left, [])
                self.assertEqual(len(accepted), 1)
                self.assertIn(source.location, accepted[0])

    def test_the_closed_set_is_nineteen_names_and_side_fiducials_is_not_one_of_them(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C4: On a synthetic design, an entry with an empty, placeholder or angle-bracketed accepted-by value, an entry with an empty, malformed or future date, an entry naming a rule outside the closed set the leaf states (each of hole_to_hole, workmanship_rule, workmanship_figure and workmanship_pad_copper, and any rule that is not a workmanship or neatness rule), a courtyards_overlap entry used by a line that names a custom rule such as the crystal keep-clear, an items_not_allowed entry used by a line that names a rule other than the floorplan region rule, an entry naming a mains spacing, derated-voltage or pin-limit rule, an entry for a place the design does not have, and an entry that no line uses each fail the check naming the entry, and a design marked synthetic is honoured only when it is marked not for manufacture. On the same design, for each of the nineteen names of the closed set (workmanship_detour, workmanship_pad_entry, workmanship_pad_corner, workmanship_width, workmanship_direction, track_angle, track_segment_length, courtyards_overlap, test_point_courtyard, designator_astray, silk_overlap, items_not_allowed, pour_gap, decoupling_via, starved_thermal, silk_over_copper, footprint_symbol_field_mismatch, footprint_symbol_mismatch and lib_footprint_mismatch), a signed entry at the place of a line of that name, with a count equal to the lines there, is accepted and used by that line, and the same entry fails as stale when no line of that name stands at its place; a signed entry whose accepted-by value reads 'david (signed by Claude on his standing instruction of 2026-11-07)' is accepted as signed. The same entry for side_fiducials, hole_to_hole, workmanship_rule, workmanship_figure or workmanship_pad_copper fails as naming a rule outside the set. Out of scope is a well-formed signed entry that a line uses.
        self.assertEqual(len(board_check.ACCEPTABLE_WORKMANSHIP), 19)
        self.assertEqual(len(set(board_check.ACCEPTABLE_WORKMANSHIP)), 19)
        self.assertNotIn("side_fiducials", board_check.ACCEPTABLE_WORKMANSHIP)
        self.assertIn("side_fiducials", board_check.NEVER_ACCEPTED_WORKMANSHIP)

    def test_an_entry_for_each_of_the_seven_added_names_fails_stale_when_no_line_of_that_name_stands_at_its_place(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C4: On a synthetic design, an entry with an empty, placeholder or angle-bracketed accepted-by value, an entry with an empty, malformed or future date, an entry naming a rule outside the closed set the leaf states (each of hole_to_hole, workmanship_rule, workmanship_figure and workmanship_pad_copper, and any rule that is not a workmanship or neatness rule), a courtyards_overlap entry used by a line that names a custom rule such as the crystal keep-clear, an items_not_allowed entry used by a line that names a rule other than the floorplan region rule, an entry naming a mains spacing, derated-voltage or pin-limit rule, an entry for a place the design does not have, and an entry that no line uses each fail the check naming the entry, and a design marked synthetic is honoured only when it is marked not for manufacture. On the same design, for each of the nineteen names of the closed set (workmanship_detour, workmanship_pad_entry, workmanship_pad_corner, workmanship_width, workmanship_direction, track_angle, track_segment_length, courtyards_overlap, test_point_courtyard, designator_astray, silk_overlap, items_not_allowed, pour_gap, decoupling_via, starved_thermal, silk_over_copper, footprint_symbol_field_mismatch, footprint_symbol_mismatch and lib_footprint_mismatch), a signed entry at the place of a line of that name, with a count equal to the lines there, is accepted and used by that line, and the same entry fails as stale when no line of that name stands at its place; a signed entry whose accepted-by value reads 'david (signed by Claude on his standing instruction of 2026-11-07)' is accepted as signed. The same entry for side_fiducials, hole_to_hole, workmanship_rule, workmanship_figure or workmanship_pad_copper fails as naming a rule outside the set. Out of scope is a well-formed signed entry that a line uses.
        for rule in self.PARITY:
            source, scope = self.LINES[rule]
            with self.subTest(rule=rule, case="a line of another rule at the place"):
                other = line("workmanship_detour")
                left, accepted = self.judge([other], [entry(rule, scope if scope != "/NET_A" else "R1")])
                self.assertEqual(accepted, [])
                self.assertIn(other.line(), [v.line() for v in left])
                self.assertIn("is used by no line", self.failures(left)[0].message)
            with self.subTest(rule=rule, case="a line of the rule at another place"):
                elsewhere = "D1" if rule == "silk_over_copper" else "R2" if scope != "R2" else "TP1"
                left, accepted = self.judge([source], [entry(rule, elsewhere)])
                self.assertEqual(accepted, [])
                self.assertIn(source.line(), [v.line() for v in left])
                self.assertIn("is used by no line", self.failures(left)[0].message)

    def test_an_entry_for_each_of_the_seven_added_names_covers_only_its_count_and_place(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C4: On a synthetic design, an entry with an empty, placeholder or angle-bracketed accepted-by value, an entry with an empty, malformed or future date, an entry naming a rule outside the closed set the leaf states (each of hole_to_hole, workmanship_rule, workmanship_figure and workmanship_pad_copper, and any rule that is not a workmanship or neatness rule), a courtyards_overlap entry used by a line that names a custom rule such as the crystal keep-clear, an items_not_allowed entry used by a line that names a rule other than the floorplan region rule, an entry naming a mains spacing, derated-voltage or pin-limit rule, an entry for a place the design does not have, and an entry that no line uses each fail the check naming the entry, and a design marked synthetic is honoured only when it is marked not for manufacture. On the same design, for each of the nineteen names of the closed set (workmanship_detour, workmanship_pad_entry, workmanship_pad_corner, workmanship_width, workmanship_direction, track_angle, track_segment_length, courtyards_overlap, test_point_courtyard, designator_astray, silk_overlap, items_not_allowed, pour_gap, decoupling_via, starved_thermal, silk_over_copper, footprint_symbol_field_mismatch, footprint_symbol_mismatch and lib_footprint_mismatch), a signed entry at the place of a line of that name, with a count equal to the lines there, is accepted and used by that line, and the same entry fails as stale when no line of that name stands at its place; a signed entry whose accepted-by value reads 'david (signed by Claude on his standing instruction of 2026-11-07)' is accepted as signed. The same entry for side_fiducials, hole_to_hole, workmanship_rule, workmanship_figure or workmanship_pad_copper fails as naming a rule outside the set. Out of scope is a well-formed signed entry that a line uses.
        for rule in self.PARITY:
            source, scope = self.LINES[rule]
            with self.subTest(rule=rule):
                left, accepted = self.judge([source, source], [entry(rule, scope, 1)])
                self.assertEqual(len(accepted), 1)
                self.assertEqual([v.line() for v in left], [source.line()], "the line beyond the count fails")

    def test_the_scope_forms_of_the_seven_added_names_match_the_places_their_lines_name(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C4: On a synthetic design, an entry with an empty, placeholder or angle-bracketed accepted-by value, an entry with an empty, malformed or future date, an entry naming a rule outside the closed set the leaf states (each of hole_to_hole, workmanship_rule, workmanship_figure and workmanship_pad_copper, and any rule that is not a workmanship or neatness rule), a courtyards_overlap entry used by a line that names a custom rule such as the crystal keep-clear, an items_not_allowed entry used by a line that names a rule other than the floorplan region rule, an entry naming a mains spacing, derated-voltage or pin-limit rule, an entry for a place the design does not have, and an entry that no line uses each fail the check naming the entry, and a design marked synthetic is honoured only when it is marked not for manufacture. On the same design, for each of the nineteen names of the closed set (workmanship_detour, workmanship_pad_entry, workmanship_pad_corner, workmanship_width, workmanship_direction, track_angle, track_segment_length, courtyards_overlap, test_point_courtyard, designator_astray, silk_overlap, items_not_allowed, pour_gap, decoupling_via, starved_thermal, silk_over_copper, footprint_symbol_field_mismatch, footprint_symbol_mismatch and lib_footprint_mismatch), a signed entry at the place of a line of that name, with a count equal to the lines there, is accepted and used by that line, and the same entry fails as stale when no line of that name stands at its place; a signed entry whose accepted-by value reads 'david (signed by Claude on his standing instruction of 2026-11-07)' is accepted as signed. The same entry for side_fiducials, hole_to_hole, workmanship_rule, workmanship_figure or workmanship_pad_copper fails as naming a rule outside the set. Out of scope is a well-formed signed entry that a line uses.
        for rule, scope in (("pour_gap", "R1"), ("decoupling_via", "D1"), ("decoupling_via", "R1"), ("starved_thermal", "/NET_A"),
                            ("silk_over_copper", "TP1"), ("silk_over_copper", "/NET_B")):
            with self.subTest(rule=rule, scope=scope):
                left, accepted = self.judge([self.LINES[rule][0]], [entry(rule, scope)])
                self.assertEqual((left, len(accepted)), ([], 1))

    def test_an_entry_for_side_fiducials_fails_as_naming_a_rule_outside_the_set_and_its_line_still_fails(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C4: On a synthetic design, an entry with an empty, placeholder or angle-bracketed accepted-by value, an entry with an empty, malformed or future date, an entry naming a rule outside the closed set the leaf states (each of hole_to_hole, workmanship_rule, workmanship_figure and workmanship_pad_copper, and any rule that is not a workmanship or neatness rule), a courtyards_overlap entry used by a line that names a custom rule such as the crystal keep-clear, an items_not_allowed entry used by a line that names a rule other than the floorplan region rule, an entry naming a mains spacing, derated-voltage or pin-limit rule, an entry for a place the design does not have, and an entry that no line uses each fail the check naming the entry, and a design marked synthetic is honoured only when it is marked not for manufacture. On the same design, for each of the nineteen names of the closed set (workmanship_detour, workmanship_pad_entry, workmanship_pad_corner, workmanship_width, workmanship_direction, track_angle, track_segment_length, courtyards_overlap, test_point_courtyard, designator_astray, silk_overlap, items_not_allowed, pour_gap, decoupling_via, starved_thermal, silk_over_copper, footprint_symbol_field_mismatch, footprint_symbol_mismatch and lib_footprint_mismatch), a signed entry at the place of a line of that name, with a count equal to the lines there, is accepted and used by that line, and the same entry fails as stale when no line of that name stands at its place; a signed entry whose accepted-by value reads 'david (signed by Claude on his standing instruction of 2026-11-07)' is accepted as signed. The same entry for side_fiducials, hole_to_hole, workmanship_rule, workmanship_figure or workmanship_pad_copper fails as naming a rule outside the set. Out of scope is a well-formed signed entry that a line uses.
        source = line("side_fiducials", "side B: 4 assembled surface-mount parts", "MFG-10 holds 0 fiducials where 3 are the least")
        left, accepted = self.judge([source], [entry("side_fiducials", "/NET_A")])
        self.assertEqual(accepted, [])
        self.assertIn(source.line(), [v.line() for v in left])
        self.assertIn("names the rule side_fiducials, which the record does not accept", self.failures(left)[0].message)

    def test_an_entry_for_a_rule_outside_the_set_fails_naming_it_and_its_line_still_fails(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C4: On a synthetic design, an entry with an empty, placeholder or angle-bracketed accepted-by value, an entry with an empty, malformed or future date, an entry naming a rule outside the closed set the leaf states (each of hole_to_hole, workmanship_rule, workmanship_figure and workmanship_pad_copper, and any rule that is not a workmanship or neatness rule), a courtyards_overlap entry used by a line that names a custom rule such as the crystal keep-clear, an items_not_allowed entry used by a line that names a rule other than the floorplan region rule, an entry naming a mains spacing, derated-voltage or pin-limit rule, an entry for a place the design does not have, and an entry that no line uses each fail the check naming the entry, and a design marked synthetic is honoured only when it is marked not for manufacture. On the same design, for each of the nineteen names of the closed set (workmanship_detour, workmanship_pad_entry, workmanship_pad_corner, workmanship_width, workmanship_direction, track_angle, track_segment_length, courtyards_overlap, test_point_courtyard, designator_astray, silk_overlap, items_not_allowed, pour_gap, decoupling_via, starved_thermal, silk_over_copper, footprint_symbol_field_mismatch, footprint_symbol_mismatch and lib_footprint_mismatch), a signed entry at the place of a line of that name, with a count equal to the lines there, is accepted and used by that line, and the same entry fails as stale when no line of that name stands at its place; a signed entry whose accepted-by value reads 'david (signed by Claude on his standing instruction of 2026-11-07)' is accepted as signed. The same entry for side_fiducials, hole_to_hole, workmanship_rule, workmanship_figure or workmanship_pad_copper fails as naming a rule outside the set. Out of scope is a well-formed signed entry that a line uses.
        for rule in ("hole_to_hole", "workmanship_rule", "workmanship_figure", "workmanship_pad_copper", "creepage", "clearance",
                     "mains_to_mains", "derated_voltage", "pin_limit", "spacing_exception", "separation_basis", "hole_clearance", "unheard_of"):
            with self.subTest(rule=rule):
                source = line(rule, "net /NET_A: something at R1")
                left, accepted = self.judge([source], [entry(rule, "/NET_A")])
                self.assertEqual(accepted, [])
                self.assertIn(source.line(), [v.line() for v in left], "the line is not accepted")
                failed = self.failures(left)
                self.assertEqual(len(failed), 1, left)
                self.assertEqual(failed[0].location, f"{RECORD} accepted_workmanship[0].rule")
                self.assertIn(f"names the rule {rule}, which the record does not accept", failed[0].message)
        for rule in ("hole_to_hole", "workmanship_rule", "workmanship_figure", "workmanship_pad_copper"):
            self.assertIn(rule, board_check.NEVER_ACCEPTED_WORKMANSHIP)
            self.assertNotIn(rule, board_check.ACCEPTABLE_WORKMANSHIP)

    def test_a_courtyard_entry_does_not_accept_a_line_naming_a_custom_rule_such_as_the_crystal_keep_clear(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C4: On a synthetic design, an entry with an empty, placeholder or angle-bracketed accepted-by value, an entry with an empty, malformed or future date, an entry naming a rule outside the closed set the leaf states (each of hole_to_hole, workmanship_rule, workmanship_figure and workmanship_pad_copper, and any rule that is not a workmanship or neatness rule), a courtyards_overlap entry used by a line that names a custom rule such as the crystal keep-clear, an items_not_allowed entry used by a line that names a rule other than the floorplan region rule, an entry naming a mains spacing, derated-voltage or pin-limit rule, an entry for a place the design does not have, and an entry that no line uses each fail the check naming the entry, and a design marked synthetic is honoured only when it is marked not for manufacture. On the same design, for each of the nineteen names of the closed set (workmanship_detour, workmanship_pad_entry, workmanship_pad_corner, workmanship_width, workmanship_direction, track_angle, track_segment_length, courtyards_overlap, test_point_courtyard, designator_astray, silk_overlap, items_not_allowed, pour_gap, decoupling_via, starved_thermal, silk_over_copper, footprint_symbol_field_mismatch, footprint_symbol_mismatch and lib_footprint_mismatch), a signed entry at the place of a line of that name, with a count equal to the lines there, is accepted and used by that line, and the same entry fails as stale when no line of that name stands at its place; a signed entry whose accepted-by value reads 'david (signed by Claude on his standing instruction of 2026-11-07)' is accepted as signed. The same entry for side_fiducials, hole_to_hole, workmanship_rule, workmanship_figure or workmanship_pad_copper fails as naming a rule outside the set. Out of scope is a well-formed signed entry that a line uses.
        crystal = line("courtyards_overlap", "Footprint FB1 @ (73.8, 38) mm; Footprint Y1 @ (69.7, 13.75) mm",
                       "Courtyards overlap (rule 'Crystal keep-clear' clearance 25.0000 mm; actual 20.4369 mm)")
        self.write(LAYOUT, board_fixtures.layout([board_fixtures.footprint("FB1", 10, 10, [board_fixtures.pad(1, 0, 0, "/NET_A", "passive")])]))
        left, accepted = self.judge([crystal], [entry("courtyards_overlap", "FB1")])
        self.assertEqual(accepted, [])
        self.assertIn(crystal.line(), [v.line() for v in left])
        self.assertIn("is used by no line", self.failures(left)[0].message)
        # beside a plain overlap of the same part, only the plain one is accepted
        plain = line("courtyards_overlap", "Footprint FB1 @ (10, 10) mm; Footprint Y1 @ (12, 10) mm", "Courtyards overlap (actual -0.5 mm)")
        left, accepted = self.judge([crystal, plain], [entry("courtyards_overlap", "FB1", count=2)])
        self.assertEqual([v.line() for v in left], [crystal.line()])
        self.assertEqual(len(accepted), 1)

    def test_an_items_not_allowed_entry_accepts_only_the_floorplan_regions_rule(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C4: On a synthetic design, an entry with an empty, placeholder or angle-bracketed accepted-by value, an entry with an empty, malformed or future date, an entry naming a rule outside the closed set the leaf states (each of hole_to_hole, workmanship_rule, workmanship_figure and workmanship_pad_copper, and any rule that is not a workmanship or neatness rule), a courtyards_overlap entry used by a line that names a custom rule such as the crystal keep-clear, an items_not_allowed entry used by a line that names a rule other than the floorplan region rule, an entry naming a mains spacing, derated-voltage or pin-limit rule, an entry for a place the design does not have, and an entry that no line uses each fail the check naming the entry, and a design marked synthetic is honoured only when it is marked not for manufacture. On the same design, for each of the nineteen names of the closed set (workmanship_detour, workmanship_pad_entry, workmanship_pad_corner, workmanship_width, workmanship_direction, track_angle, track_segment_length, courtyards_overlap, test_point_courtyard, designator_astray, silk_overlap, items_not_allowed, pour_gap, decoupling_via, starved_thermal, silk_over_copper, footprint_symbol_field_mismatch, footprint_symbol_mismatch and lib_footprint_mismatch), a signed entry at the place of a line of that name, with a count equal to the lines there, is accepted and used by that line, and the same entry fails as stale when no line of that name stands at its place; a signed entry whose accepted-by value reads 'david (signed by Claude on his standing instruction of 2026-11-07)' is accepted as signed. The same entry for side_fiducials, hole_to_hole, workmanship_rule, workmanship_figure or workmanship_pad_copper fails as naming a rule outside the set. Out of scope is a well-formed signed entry that a line uses.
        other = line("items_not_allowed", "Footprint D1 @ (30, 30) mm", "Items not allowed (rule 'Digital keepout')")
        bare = line("items_not_allowed", "Footprint D1 @ (30, 30) mm", "Items not allowed")
        region = line("items_not_allowed", "Footprint D1 @ (30, 30) mm", "Items not allowed (rule 'Mains region parts')")
        self.region_rules("Mains region parts")
        left, accepted = self.judge([other, bare, region], [entry("items_not_allowed", "D1", count=3)])
        self.assertEqual([v.line() for v in left], [other.line(), bare.line()])
        self.assertEqual(len(accepted), 1)
        left, accepted = self.judge([other], [entry("items_not_allowed", "D1")])
        self.assertEqual(accepted, [])
        self.assertIn("is used by no line", self.failures(left)[0].message)

    def test_a_rule_named_for_a_region_that_is_not_a_floorplan_region_rule_of_the_design_is_not_accepted(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C4: On a synthetic design, an entry with an empty, placeholder or angle-bracketed accepted-by value, an entry with an empty, malformed or future date, an entry naming a rule outside the closed set the leaf states (each of hole_to_hole, workmanship_rule, workmanship_figure and workmanship_pad_copper, and any rule that is not a workmanship or neatness rule), a courtyards_overlap entry used by a line that names a custom rule such as the crystal keep-clear, an items_not_allowed entry used by a line that names a rule other than the floorplan region rule, an entry naming a mains spacing, derated-voltage or pin-limit rule, an entry for a place the design does not have, and an entry that no line uses each fail the check naming the entry, and a design marked synthetic is honoured only when it is marked not for manufacture. On the same design, for each of the nineteen names of the closed set (workmanship_detour, workmanship_pad_entry, workmanship_pad_corner, workmanship_width, workmanship_direction, track_angle, track_segment_length, courtyards_overlap, test_point_courtyard, designator_astray, silk_overlap, items_not_allowed, pour_gap, decoupling_via, starved_thermal, silk_over_copper, footprint_symbol_field_mismatch, footprint_symbol_mismatch and lib_footprint_mismatch), a signed entry at the place of a line of that name, with a count equal to the lines there, is accepted and used by that line, and the same entry fails as stale when no line of that name stands at its place; a signed entry whose accepted-by value reads 'david (signed by Claude on his standing instruction of 2026-11-07)' is accepted as signed. The same entry for side_fiducials, hole_to_hole, workmanship_rule, workmanship_figure or workmanship_pad_copper fails as naming a rule outside the set. Out of scope is a well-formed signed entry that a line uses.
        keepout = line("items_not_allowed", "Footprint D1 @ (30, 30) mm", "Items not allowed (rule 'Mains region parts')")
        # the name alone: the rules file holds a safety keepout of that name in another form
        self.write(self.RULES, "(version 1)\n(rule \"Mains region parts\"\n\t(condition \"A.Type == 'Footprint' && A.hasNetclass('Mains')\")\n"
                               "\t(constraint disallow footprint))\n")
        left, accepted = self.judge([keepout], [entry("items_not_allowed", "D1")])
        self.assertEqual(accepted, [])
        self.assertIn(keepout.line(), [v.line() for v in left])
        self.assertIn("is used by no line", self.failures(left)[0].message)
        # the form, but a constraint that is not the disallow of a footprint
        self.write(self.RULES, "(version 1)\n(rule \"Mains region parts\"\n\t(condition \"A.Type == 'Footprint' && A.intersectsArea('mains')\")\n"
                               "\t(constraint disallow track))\n")
        self.assertEqual(self.judge([keepout], [entry("items_not_allowed", "D1")])[1], [])
        # a name the design's rules file does not hold at all
        self.region_rules("Digital region parts")
        self.assertEqual(self.judge([keepout], [entry("items_not_allowed", "D1")])[1], [])
        # no rules file
        os.remove(os.path.join(self.root, self.RULES))
        self.tracked.remove(self.RULES)
        self.assertEqual(self.judge([keepout], [entry("items_not_allowed", "D1")])[1], [])
        # and the design's own region rule is accepted
        self.region_rules("Mains region parts")
        self.assertEqual(len(self.judge([keepout], [entry("items_not_allowed", "D1")])[1]), 1)

    def test_an_entry_that_is_unsigned_fails_naming_it_and_accepts_nothing(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C4: On a synthetic design, an entry with an empty, placeholder or angle-bracketed accepted-by value, an entry with an empty, malformed or future date, an entry naming a rule outside the closed set the leaf states (each of hole_to_hole, workmanship_rule, workmanship_figure and workmanship_pad_copper, and any rule that is not a workmanship or neatness rule), a courtyards_overlap entry used by a line that names a custom rule such as the crystal keep-clear, an items_not_allowed entry used by a line that names a rule other than the floorplan region rule, an entry naming a mains spacing, derated-voltage or pin-limit rule, an entry for a place the design does not have, and an entry that no line uses each fail the check naming the entry, and a design marked synthetic is honoured only when it is marked not for manufacture. On the same design, for each of the nineteen names of the closed set (workmanship_detour, workmanship_pad_entry, workmanship_pad_corner, workmanship_width, workmanship_direction, track_angle, track_segment_length, courtyards_overlap, test_point_courtyard, designator_astray, silk_overlap, items_not_allowed, pour_gap, decoupling_via, starved_thermal, silk_over_copper, footprint_symbol_field_mismatch, footprint_symbol_mismatch and lib_footprint_mismatch), a signed entry at the place of a line of that name, with a count equal to the lines there, is accepted and used by that line, and the same entry fails as stale when no line of that name stands at its place; a signed entry whose accepted-by value reads 'david (signed by Claude on his standing instruction of 2026-11-07)' is accepted as signed. The same entry for side_fiducials, hole_to_hole, workmanship_rule, workmanship_figure or workmanship_pad_copper fails as naming a rule outside the set. Out of scope is a well-formed signed entry that a line uses.
        for name, change, key, said in (
                ("an empty accepted_by", {"accepted_by": ""}, "accepted_by", "accepted_by is ''"),
                ("a blank accepted_by", {"accepted_by": "  "}, "accepted_by", "accepted_by is '  '"),
                ("an accepted_by that is no text", {"accepted_by": 7}, "accepted_by", "accepted_by is 7"),
                ("a placeholder accepted_by", {"accepted_by": "unsigned"}, "accepted_by", "accepted_by 'unsigned' is a placeholder"),
                ("a tbd accepted_by", {"accepted_by": "TBD"}, "accepted_by", "is a placeholder"),
                ("an angle-bracketed accepted_by", {"accepted_by": "<owner>"}, "accepted_by", "accepted_by '<owner>' is a placeholder"),
                ("an empty date", {"accepted_on": ""}, "accepted_on", "is not a valid calendar date written as YYYY-MM-DD"),
                ("a malformed date", {"accepted_on": "07/11/2026"}, "accepted_on", "accepted_on 07/11/2026 is not a valid calendar date"),
                ("a date with a time", {"accepted_on": "2026-11-01T10:00:00"}, "accepted_on", "is not a valid calendar date"),
                ("a future date", {"accepted_on": "2026-11-08"}, "accepted_on", "accepted_on 2026-11-08 is later than today (2026-11-07)")):
            with self.subTest(entry=name):
                source = line()
                left, accepted = self.judge([source], [entry(**change)])
                self.assertEqual(accepted, [])
                self.assertIn(source.line(), [v.line() for v in left])
                failed = self.failures(left)
                self.assertEqual(len(failed), 1, left)
                self.assertEqual(failed[0].location, f"{RECORD} accepted_workmanship[0].{key}")
                self.assertIn(said, failed[0].message)
                self.assertIn("accepted_workmanship[0] (workmanship_detour at /NET_A)", failed[0].message)
        # today itself is not later than today
        self.assertEqual(self.judge([line()], [entry(accepted_on="2026-11-07")])[0], [])

    def test_an_entry_for_a_place_the_design_does_not_have_fails_and_one_no_line_uses_is_stale(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C4: On a synthetic design, an entry with an empty, placeholder or angle-bracketed accepted-by value, an entry with an empty, malformed or future date, an entry naming a rule outside the closed set the leaf states (each of hole_to_hole, workmanship_rule, workmanship_figure and workmanship_pad_copper, and any rule that is not a workmanship or neatness rule), a courtyards_overlap entry used by a line that names a custom rule such as the crystal keep-clear, an items_not_allowed entry used by a line that names a rule other than the floorplan region rule, an entry naming a mains spacing, derated-voltage or pin-limit rule, an entry for a place the design does not have, and an entry that no line uses each fail the check naming the entry, and a design marked synthetic is honoured only when it is marked not for manufacture. On the same design, for each of the nineteen names of the closed set (workmanship_detour, workmanship_pad_entry, workmanship_pad_corner, workmanship_width, workmanship_direction, track_angle, track_segment_length, courtyards_overlap, test_point_courtyard, designator_astray, silk_overlap, items_not_allowed, pour_gap, decoupling_via, starved_thermal, silk_over_copper, footprint_symbol_field_mismatch, footprint_symbol_mismatch and lib_footprint_mismatch), a signed entry at the place of a line of that name, with a count equal to the lines there, is accepted and used by that line, and the same entry fails as stale when no line of that name stands at its place; a signed entry whose accepted-by value reads 'david (signed by Claude on his standing instruction of 2026-11-07)' is accepted as signed. The same entry for side_fiducials, hole_to_hole, workmanship_rule, workmanship_figure or workmanship_pad_copper fails as naming a rule outside the set. Out of scope is a well-formed signed entry that a line uses.
        source = line()
        left, accepted = self.judge([source], [entry(scope="/NO_SUCH_NET")])
        self.assertEqual(accepted, [])
        failed = self.failures(left)
        self.assertEqual([(v.location, "names /NO_SUCH_NET, which is no net, reference designator or text variable of the design" in v.message)
                          for v in failed], [(f"{RECORD} accepted_workmanship[0].scope", True)])
        self.assertIn(source.line(), [v.line() for v in left])
        # a place the design has, that no line of the rule falls in
        left, accepted = self.judge([source], [entry(scope="/NET_B")])
        self.assertEqual(accepted, [])
        self.assertEqual([v.location for v in self.failures(left)], [f"{RECORD} accepted_workmanship[0]"])
        self.assertIn("is used by no line", self.failures(left)[0].message)
        left, _ = self.judge([], [entry()])
        self.assertEqual([v.location for v in left], [f"{RECORD} accepted_workmanship[0]"])
        self.assertIn("accepted_workmanship[0] (workmanship_detour at /NET_A) is used by no line", left[0].message)

    def test_an_entry_names_a_net_a_reference_or_a_text_variable_the_design_has(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C4: On a synthetic design, an entry with an empty, placeholder or angle-bracketed accepted-by value, an entry with an empty, malformed or future date, an entry naming a rule outside the closed set the leaf states (each of hole_to_hole, workmanship_rule, workmanship_figure and workmanship_pad_copper, and any rule that is not a workmanship or neatness rule), a courtyards_overlap entry used by a line that names a custom rule such as the crystal keep-clear, an items_not_allowed entry used by a line that names a rule other than the floorplan region rule, an entry naming a mains spacing, derated-voltage or pin-limit rule, an entry for a place the design does not have, and an entry that no line uses each fail the check naming the entry, and a design marked synthetic is honoured only when it is marked not for manufacture. On the same design, for each of the nineteen names of the closed set (workmanship_detour, workmanship_pad_entry, workmanship_pad_corner, workmanship_width, workmanship_direction, track_angle, track_segment_length, courtyards_overlap, test_point_courtyard, designator_astray, silk_overlap, items_not_allowed, pour_gap, decoupling_via, starved_thermal, silk_over_copper, footprint_symbol_field_mismatch, footprint_symbol_mismatch and lib_footprint_mismatch), a signed entry at the place of a line of that name, with a count equal to the lines there, is accepted and used by that line, and the same entry fails as stale when no line of that name stands at its place; a signed entry whose accepted-by value reads 'david (signed by Claude on his standing instruction of 2026-11-07)' is accepted as signed. The same entry for side_fiducials, hole_to_hole, workmanship_rule, workmanship_figure or workmanship_pad_copper fails as naming a rule outside the set. Out of scope is a well-formed signed entry that a line uses.
        for scope in ("/NET_A", "R2", "WORK_DETOUR_RATIO"):
            with self.subTest(scope=scope):
                self.assertFalse([v for v in self.failures(self.judge([], [entry(scope=scope)])[0]) if "no net" in v.message])

    def test_a_layout_that_cannot_be_read_leaves_every_entry_failing_and_every_line_standing(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C4: On a synthetic design, an entry with an empty, placeholder or angle-bracketed accepted-by value, an entry with an empty, malformed or future date, an entry naming a rule outside the closed set the leaf states (each of hole_to_hole, workmanship_rule, workmanship_figure and workmanship_pad_copper, and any rule that is not a workmanship or neatness rule), a courtyards_overlap entry used by a line that names a custom rule such as the crystal keep-clear, an items_not_allowed entry used by a line that names a rule other than the floorplan region rule, an entry naming a mains spacing, derated-voltage or pin-limit rule, an entry for a place the design does not have, and an entry that no line uses each fail the check naming the entry, and a design marked synthetic is honoured only when it is marked not for manufacture. On the same design, for each of the nineteen names of the closed set (workmanship_detour, workmanship_pad_entry, workmanship_pad_corner, workmanship_width, workmanship_direction, track_angle, track_segment_length, courtyards_overlap, test_point_courtyard, designator_astray, silk_overlap, items_not_allowed, pour_gap, decoupling_via, starved_thermal, silk_over_copper, footprint_symbol_field_mismatch, footprint_symbol_mismatch and lib_footprint_mismatch), a signed entry at the place of a line of that name, with a count equal to the lines there, is accepted and used by that line, and the same entry fails as stale when no line of that name stands at its place; a signed entry whose accepted-by value reads 'david (signed by Claude on his standing instruction of 2026-11-07)' is accepted as signed. The same entry for side_fiducials, hole_to_hole, workmanship_rule, workmanship_figure or workmanship_pad_copper fails as naming a rule outside the set. Out of scope is a well-formed signed entry that a line uses.
        self.write(LAYOUT, "(kicad_pcb (unclosed")
        source = line()
        for scope in ("/NET_A", "R1", "WORK_DETOUR_RATIO"):
            with self.subTest(scope=scope):
                left, accepted = self.judge([source], [entry(scope=scope)])
                self.assertEqual(accepted, [])
                self.assertIn(source.line(), [v.line() for v in left])
                failed = self.failures(left)
                self.assertEqual(len(failed), 1, left)
                self.assertIn("cannot be judged: the layout's nets and parts cannot be read", failed[0].message)

    def test_an_early_end_of_the_design_check_still_judges_the_record(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C4: On a synthetic design, an entry with an empty, placeholder or angle-bracketed accepted-by value, an entry with an empty, malformed or future date, an entry naming a rule outside the closed set the leaf states (each of hole_to_hole, workmanship_rule, workmanship_figure and workmanship_pad_copper, and any rule that is not a workmanship or neatness rule), a courtyards_overlap entry used by a line that names a custom rule such as the crystal keep-clear, an items_not_allowed entry used by a line that names a rule other than the floorplan region rule, an entry naming a mains spacing, derated-voltage or pin-limit rule, an entry for a place the design does not have, and an entry that no line uses each fail the check naming the entry, and a design marked synthetic is honoured only when it is marked not for manufacture. On the same design, for each of the nineteen names of the closed set (workmanship_detour, workmanship_pad_entry, workmanship_pad_corner, workmanship_width, workmanship_direction, track_angle, track_segment_length, courtyards_overlap, test_point_courtyard, designator_astray, silk_overlap, items_not_allowed, pour_gap, decoupling_via, starved_thermal, silk_over_copper, footprint_symbol_field_mismatch, footprint_symbol_mismatch and lib_footprint_mismatch), a signed entry at the place of a line of that name, with a count equal to the lines there, is accepted and used by that line, and the same entry fails as stale when no line of that name stands at its place; a signed entry whose accepted-by value reads 'david (signed by Claude on his standing instruction of 2026-11-07)' is accepted as signed. The same entry for side_fiducials, hole_to_hole, workmanship_rule, workmanship_figure or workmanship_pad_copper fails as naming a rule outside the set. Out of scope is a well-formed signed entry that a line uses.
        self.write(PROJECT, json.dumps({"text_variables": {**self.variables, "WORK_DETOUR_RATIO": 1.3}}))
        self.record([entry(scope="/NET_B")])
        accepted: list = []
        found = board_check.check_design(board_check.Design(PROJECT), board_check.Repository(self.root, self.tracked), "kicad-cli-absent",
                                         YAML, TODAY, [], None, accepted)
        self.assertTrue([v for v in found if v.rule == "project_file"], found)
        self.assertEqual([v.location for v in self.failures(found)], [f"{RECORD} accepted_workmanship[0]"])
        self.assertIn("is used by no line", self.failures(found)[0].message)

    def test_the_designs_reads_list_the_workmanship_acceptance_record_where_the_design_holds_one(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C4: On a synthetic design, an entry with an empty, placeholder or angle-bracketed accepted-by value, an entry with an empty, malformed or future date, an entry naming a rule outside the closed set the leaf states (each of hole_to_hole, workmanship_rule, workmanship_figure and workmanship_pad_copper, and any rule that is not a workmanship or neatness rule), a courtyards_overlap entry used by a line that names a custom rule such as the crystal keep-clear, an items_not_allowed entry used by a line that names a rule other than the floorplan region rule, an entry naming a mains spacing, derated-voltage or pin-limit rule, an entry for a place the design does not have, and an entry that no line uses each fail the check naming the entry, and a design marked synthetic is honoured only when it is marked not for manufacture. On the same design, for each of the nineteen names of the closed set (workmanship_detour, workmanship_pad_entry, workmanship_pad_corner, workmanship_width, workmanship_direction, track_angle, track_segment_length, courtyards_overlap, test_point_courtyard, designator_astray, silk_overlap, items_not_allowed, pour_gap, decoupling_via, starved_thermal, silk_over_copper, footprint_symbol_field_mismatch, footprint_symbol_mismatch and lib_footprint_mismatch), a signed entry at the place of a line of that name, with a count equal to the lines there, is accepted and used by that line, and the same entry fails as stale when no line of that name stands at its place; a signed entry whose accepted-by value reads 'david (signed by Claude on his standing instruction of 2026-11-07)' is accepted as signed. The same entry for side_fiducials, hole_to_hole, workmanship_rule, workmanship_figure or workmanship_pad_copper fails as naming a rule outside the set. Out of scope is a well-formed signed entry that a line uses.
        self.write(PROJECT, json.dumps({"text_variables": self.variables}))
        self.write(f"{FOLDER}/board.kicad_sch", "(kicad_sch)")
        self.tracked.append(f"{FOLDER}/board.kicad_sch")
        self.assertNotIn(RECORD, board_check.design_reads(self.root, list(self.tracked)))
        self.record([entry()])
        self.assertIn(RECORD, board_check.design_reads(self.root, list(self.tracked)))

    def test_a_design_marked_synthetic_is_honoured_only_when_it_is_marked_not_for_manufacture(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C4: On a synthetic design, an entry with an empty, placeholder or angle-bracketed accepted-by value, an entry with an empty, malformed or future date, an entry naming a rule outside the closed set the leaf states (each of hole_to_hole, workmanship_rule, workmanship_figure and workmanship_pad_copper, and any rule that is not a workmanship or neatness rule), a courtyards_overlap entry used by a line that names a custom rule such as the crystal keep-clear, an items_not_allowed entry used by a line that names a rule other than the floorplan region rule, an entry naming a mains spacing, derated-voltage or pin-limit rule, an entry for a place the design does not have, and an entry that no line uses each fail the check naming the entry, and a design marked synthetic is honoured only when it is marked not for manufacture. On the same design, for each of the nineteen names of the closed set (workmanship_detour, workmanship_pad_entry, workmanship_pad_corner, workmanship_width, workmanship_direction, track_angle, track_segment_length, courtyards_overlap, test_point_courtyard, designator_astray, silk_overlap, items_not_allowed, pour_gap, decoupling_via, starved_thermal, silk_over_copper, footprint_symbol_field_mismatch, footprint_symbol_mismatch and lib_footprint_mismatch), a signed entry at the place of a line of that name, with a count equal to the lines there, is accepted and used by that line, and the same entry fails as stale when no line of that name stands at its place; a signed entry whose accepted-by value reads 'david (signed by Claude on his standing instruction of 2026-11-07)' is accepted as signed. The same entry for side_fiducials, hole_to_hole, workmanship_rule, workmanship_figure or workmanship_pad_copper fails as naming a rule outside the set. Out of scope is a well-formed signed entry that a line uses.
        self.variables.pop("NOT_FOR_MANUFACTURE")
        source = line()
        left, accepted = self.judge([source], [entry()])
        self.assertEqual(accepted, [])
        self.assertIn(source.line(), [v.line() for v in left])
        self.assertTrue([v for v in left if v.rule == "workmanship_acceptance" and "marked synthetic" in v.message], left)
        left, accepted = self.judge([source], [entry()], synthetic=False)
        self.assertEqual((left, len(accepted)), ([], 1))
        left, _ = self.judge([source], [entry()], synthetic="yes")
        self.assertTrue([v for v in left if "synthetic is 'yes'" in v.message], left)

    def test_an_entry_signed_by_claude_on_the_owners_standing_instruction_is_accepted_as_signed(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C4: On a synthetic design, an entry with an empty, placeholder or angle-bracketed accepted-by value, an entry with an empty, malformed or future date, an entry naming a rule outside the closed set the leaf states (each of hole_to_hole, workmanship_rule, workmanship_figure and workmanship_pad_copper, and any rule that is not a workmanship or neatness rule), a courtyards_overlap entry used by a line that names a custom rule such as the crystal keep-clear, an items_not_allowed entry used by a line that names a rule other than the floorplan region rule, an entry naming a mains spacing, derated-voltage or pin-limit rule, an entry for a place the design does not have, and an entry that no line uses each fail the check naming the entry, and a design marked synthetic is honoured only when it is marked not for manufacture. On the same design, for each of the nineteen names of the closed set (workmanship_detour, workmanship_pad_entry, workmanship_pad_corner, workmanship_width, workmanship_direction, track_angle, track_segment_length, courtyards_overlap, test_point_courtyard, designator_astray, silk_overlap, items_not_allowed, pour_gap, decoupling_via, starved_thermal, silk_over_copper, footprint_symbol_field_mismatch, footprint_symbol_mismatch and lib_footprint_mismatch), a signed entry at the place of a line of that name, with a count equal to the lines there, is accepted and used by that line, and the same entry fails as stale when no line of that name stands at its place; a signed entry whose accepted-by value reads 'david (signed by Claude on his standing instruction of 2026-11-07)' is accepted as signed. The same entry for side_fiducials, hole_to_hole, workmanship_rule, workmanship_figure or workmanship_pad_copper fails as naming a rule outside the set. Out of scope is a well-formed signed entry that a line uses.
        by = "david (signed by Claude on his standing instruction of 2026-11-07)"
        source = line()
        left, accepted = self.judge([source], [entry(accepted_by=by)])
        self.assertEqual(left, [])
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0].split(" | ")[0], "ACCEPTED")
        self.assertIn(by, accepted[0])
        self.assertEqual(self.failures(left), [])

    def test_one_failing_entry_does_not_stop_a_signed_one_beside_it_accepting(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C4: On a synthetic design, an entry with an empty, placeholder or angle-bracketed accepted-by value, an entry with an empty, malformed or future date, an entry naming a rule outside the closed set the leaf states (each of hole_to_hole, workmanship_rule, workmanship_figure and workmanship_pad_copper, and any rule that is not a workmanship or neatness rule), a courtyards_overlap entry used by a line that names a custom rule such as the crystal keep-clear, an items_not_allowed entry used by a line that names a rule other than the floorplan region rule, an entry naming a mains spacing, derated-voltage or pin-limit rule, an entry for a place the design does not have, and an entry that no line uses each fail the check naming the entry, and a design marked synthetic is honoured only when it is marked not for manufacture. On the same design, for each of the nineteen names of the closed set (workmanship_detour, workmanship_pad_entry, workmanship_pad_corner, workmanship_width, workmanship_direction, track_angle, track_segment_length, courtyards_overlap, test_point_courtyard, designator_astray, silk_overlap, items_not_allowed, pour_gap, decoupling_via, starved_thermal, silk_over_copper, footprint_symbol_field_mismatch, footprint_symbol_mismatch and lib_footprint_mismatch), a signed entry at the place of a line of that name, with a count equal to the lines there, is accepted and used by that line, and the same entry fails as stale when no line of that name stands at its place; a signed entry whose accepted-by value reads 'david (signed by Claude on his standing instruction of 2026-11-07)' is accepted as signed. The same entry for side_fiducials, hole_to_hole, workmanship_rule, workmanship_figure or workmanship_pad_copper fails as naming a rule outside the set. Out of scope is a well-formed signed entry that a line uses.
        left, accepted = self.judge([line()], [entry(scope="/NET_B", accepted_by=""), entry()])
        self.assertEqual(len(accepted), 1)
        self.assertEqual([v.location for v in left], [f"{RECORD} accepted_workmanship[0].accepted_by"])


class TheHardwareNotesStateTheRecord(unittest.TestCase):
    def test_the_notes_state_the_entry_form_the_accepted_line_each_failure_the_rules_refused_and_whose_it_is_to_sign(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-OWNER-ACCEPTED-WORKMANSHIP-LINES.C6: The hardware notes state the record's entry form with each key, the ACCEPTED line, each failure of an entry, the rules the record cannot accept, that an entry is the owner's to sign (and how a signature by Claude on his written standing instruction reads), and a row in its rule table for each of the nineteen names the record accepts, including the rows for silk_over_copper, starved_thermal, footprint_symbol_field_mismatch, footprint_symbol_mismatch and lib_footprint_mismatch. Out of scope is any board's own records.
        with open(os.path.join(os.path.dirname(TOOLS), "README.md"), encoding="utf-8") as handle:
            notes = handle.read()
        start = notes.index("## Owner-accepted workmanship lines")
        section = notes[start:notes.index("\n## ", start + 1)]
        for said in [board_check.WORKMANSHIP_ACCEPTANCE_NAME, "accepted_workmanship", "synthetic"] + [f"`{key}`" for key in board_check.WORKMANSHIP_ENTRY_KEYS]:
            self.assertIn(said, section)
        self.assertIn("ACCEPTED | <design> | workmanship_acceptance |", section)
        for rule in list(board_check.ACCEPTABLE_WORKMANSHIP) + list(board_check.NEVER_ACCEPTED_WORKMANSHIP):
            self.assertIn(f"`{rule}`", section)
        for said in ("never any mains, creepage, clearance, derating, pin-limit or other safety rule", "the crystal keep-clear", "FLOOR-4",
                     "an entry is the owner's to sign", "is not a mapping, lacks a key, holds another key, repeats a rule and scope",
                     "a `count` of zero", "is unsigned", "empty, malformed or later than today", "is outside the set above",
                     "names a place the design does not have", "no line uses it, so that it is stale", "synthetic on a design not marked not for manufacture"):
            self.assertIn(said, section)
        for said in ("Claude may sign an entry", "signed by Claude on his standing instruction of 2026-11-07", "the wording is the audit trail"):
            self.assertIn(said, section)
        self.assertIn("| `workmanship_acceptance` |", notes)
        self.assertIn("(`workmanship-acceptance.yaml`), read where the design's folders hold one", notes)


if __name__ == "__main__":
    unittest.main()
