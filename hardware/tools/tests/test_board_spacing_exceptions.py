#!/usr/bin/env python3
"""The pre-order check's reading and judgement of the owner's signed spacing exceptions, driven on synthetic fixtures with no KiCad involved.

What is under test here is what the check decides for itself: whether an
accepted_exceptions list is in the one form the record is read in, and what each
entry makes of the spacing shortfalls a layout rule check reported, given as the
report KiCad writes them. What KiCad then reports of a seeded layout is driven
against the real tool in test_board_check_kicad_spacing_exceptions.py.
"""

from __future__ import annotations

import copy
import datetime
import os
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import sexpr  # noqa: E402

TODAY = datetime.date(2026, 10, 12)
RECORD = "hardware/m/separation-basis.yaml"
DESIGN = board_check.Design("hardware/m/board/board.kicad_pro")


def entry(**changes) -> dict:
    """A well-formed accepted_exceptions entry, with `changes` set over it and a key set to None left out."""
    held = {"pair": "mains_to_low_voltage", "constraint": "creepage", "between": ["R1.2", "J2.1"], "accepted_mm": 13.0,
            "reason": "a synthetic ground", "bounded_by": "a synthetic independent element",
            "accepted_by": "maintainer", "accepted_on": "2026-10-01"}
    held.update(changes)
    return {key: value for key, value in held.items() if value is not None}


def basis(*entries, **changes) -> dict:
    """A mains-present record accepting `entries`, with `changes` set over it and a key set to None left out."""
    record = {
        "standard": "synthetic", "supply": "230 V", "working_voltage": "250 V rms", "pollution_degree": 2, "material_group": "IIIb",
        "environment": "indoors", "overvoltage_category": 2, "altitude_m": 2000, "barriers": [], "barrier_types": [],
        "mains_to_low_voltage": {"clearance_mm": 3.0, "creepage_mm": 14.0},
        "mains_to_mains": {"clearance_mm": 1.5, "terminal_clearance_mm": 2.0, "creepage_mm": 2.5,
                           "creepage_ahead_of_fuse_mm": 2.5, "entry_fuse": "F1", "held_at_reinforced": []},
        "accepted_exceptions": list(entries),
        "accepted_by": "maintainer", "accepted_on": "2026-10-05", "synthetic": True}
    record.update(changes)
    return {key: value for key, value in record.items() if value is not None}


def read_text(text: str):
    """What read_record finds of a record written as `text` in a temporary folder."""
    import yaml
    with tempfile.TemporaryDirectory() as folder:
        os.makedirs(os.path.join(folder, os.path.dirname(RECORD)))
        with open(os.path.join(folder, RECORD), "w", encoding="utf-8") as handle:
            handle.write(text)
        return board_check.read_record(yaml, folder, DESIGN, RECORD, True, TODAY)


def read(data: dict):
    import yaml
    return read_text(yaml.safe_dump(data))


LAYOUT = sexpr.parse_one(
    '(kicad_pcb'
    ' (footprint "R" (property "Reference" "R1") (pad "1" thru_hole circle (net "/MAINS_L")) (pad "2" thru_hole circle (net "/MAINS_N")))'
    ' (footprint "J" (property "Reference" "J2") (pad "1" thru_hole circle (net "/LV_A")) (pad "2" thru_hole circle (net "/LV_B")))'
    ' (footprint "K" (property "Reference" "K1") (pad "1" thru_hole circle (net "/MAINS_L")) (pad "2" thru_hole circle (net "/MAINS_N"))))')

#: How KiCad's report describes the pads of the layout above.
DESCRIBED = {"R1.1": "PTH pad 1 [/MAINS_L] of R1", "R1.2": "PTH pad 2 [/MAINS_N] of R1", "J2.1": "PTH pad 1 [/LV_A] of J2",
             "J2.2": "PTH pad 2 [/LV_B] of J2", "K1.1": "PTH pad 1 [/MAINS_L] of K1", "K1.2": "PTH pad 2 [/MAINS_N] of K1"}


def shortfall(kind: str, rule: str, figure: float, actual: float, first: str, second: str) -> dict:
    """One violation as KiCad's JSON report writes it, between two of the pads above."""
    return {"type": kind, "severity": "error",
            "description": f"{kind.capitalize()} violation (rule '{rule}' {kind} {figure:.4f} mm; actual {actual:.4f} mm)",
            "items": [{"description": DESCRIBED[first], "pos": {"x": 1, "y": 2}}, {"description": DESCRIBED[second], "pos": {"x": 3, "y": 4}}]}


LOW_VOLTAGE = f"{board_check.RESERVED}: signed separation basis"
TERMINAL = board_check.TERMINAL_RULE


def judge(violations, *entries, **changes):
    signed, problems = read(basis(*entries, **changes))
    assert problems == [], [problem.line() for problem in problems]
    return board_check.judge_exceptions(DESIGN, RECORD, signed, violations, LAYOUT, TODAY)


class TheListIsRead(unittest.TestCase):
    def assertFails(self, data: dict, location_end: str, words: str):
        signed, problems = read(data)
        self.assertIsNone(signed)
        self.assertTrue(any(v.rule == "separation_basis" and v.location.endswith(location_end) and words in v.message
                            for v in problems), [problem.line() for problem in problems])

    def test_a_well_formed_list_is_read_and_its_entries_kept(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C1: An accepted_exceptions that is not a list, an entry lacking pair, constraint, between, accepted_mm, reason, bounded_by, accepted_by or accepted_on, an unknown key in an entry, a repeated key, a pair outside mains_to_low_voltage and mains_to_mains, a constraint outside clearance and creepage, a between that is not a list of two items each a pad or a net name, and an accepted_mm that is not a positive number each fail separation_basis naming the entry's position and the key. A record with no accepted_exceptions key, or an explicit empty list, passes this check. The judgement of shortfalls is out of scope here and is the next criterion's.
        signed, problems = read(basis(entry(), entry(pair="mains_to_mains", constraint="clearance", between=["/MAINS_L", "/MAINS_N"])))
        self.assertEqual(problems, [])
        self.assertEqual(signed.exceptions[1]["between"], ["/MAINS_L", "/MAINS_N"])
        self.assertEqual(len(signed.exceptions), 2)

    def test_a_record_with_no_list_or_an_empty_one_passes_and_accepts_nothing(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C1: An accepted_exceptions that is not a list, an entry lacking pair, constraint, between, accepted_mm, reason, bounded_by, accepted_by or accepted_on, an unknown key in an entry, a repeated key, a pair outside mains_to_low_voltage and mains_to_mains, a constraint outside clearance and creepage, a between that is not a list of two items each a pad or a net name, and an accepted_mm that is not a positive number each fail separation_basis naming the entry's position and the key. A record with no accepted_exceptions key, or an explicit empty list, passes this check. The judgement of shortfalls is out of scope here and is the next criterion's.
        for data in (basis(accepted_exceptions=None), basis()):
            with self.subTest(keys=sorted(data)):
                signed, problems = read(data)
                self.assertEqual(problems, [])
                self.assertEqual(signed.exceptions, [])

    def test_a_list_that_is_not_a_list_fails_naming_the_key(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C1: An accepted_exceptions that is not a list, an entry lacking pair, constraint, between, accepted_mm, reason, bounded_by, accepted_by or accepted_on, an unknown key in an entry, a repeated key, a pair outside mains_to_low_voltage and mains_to_mains, a constraint outside clearance and creepage, a between that is not a list of two items each a pad or a net name, and an accepted_mm that is not a positive number each fail separation_basis naming the entry's position and the key. A record with no accepted_exceptions key, or an explicit empty list, passes this check. The judgement of shortfalls is out of scope here and is the next criterion's.
        for bad in ("none", {"pair": "mains_to_mains"}, 3):
            with self.subTest(bad=bad):
                self.assertFails(basis(accepted_exceptions=bad), "accepted_exceptions", "is not a list")
        # a key written with no value is a null, which is no list either
        import yaml
        written = yaml.safe_dump(basis(accepted_exceptions=None)) + "accepted_exceptions:\n"
        signed, problems = read_text(written)
        self.assertIsNone(signed)
        self.assertTrue(any(v.location.endswith("accepted_exceptions") and "is not a list" in v.message for v in problems))

    def test_an_entry_that_is_not_a_mapping_fails_naming_its_position(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C1: An accepted_exceptions that is not a list, an entry lacking pair, constraint, between, accepted_mm, reason, bounded_by, accepted_by or accepted_on, an unknown key in an entry, a repeated key, a pair outside mains_to_low_voltage and mains_to_mains, a constraint outside clearance and creepage, a between that is not a list of two items each a pad or a net name, and an accepted_mm that is not a positive number each fail separation_basis naming the entry's position and the key. A record with no accepted_exceptions key, or an explicit empty list, passes this check. The judgement of shortfalls is out of scope here and is the next criterion's.
        self.assertFails(basis(entry(), "J2.1"), "accepted_exceptions[1]", "is not a mapping")

    def test_an_entry_lacking_a_key_fails_naming_its_position_and_the_key(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C1: An accepted_exceptions that is not a list, an entry lacking pair, constraint, between, accepted_mm, reason, bounded_by, accepted_by or accepted_on, an unknown key in an entry, a repeated key, a pair outside mains_to_low_voltage and mains_to_mains, a constraint outside clearance and creepage, a between that is not a list of two items each a pad or a net name, and an accepted_mm that is not a positive number each fail separation_basis naming the entry's position and the key. A record with no accepted_exceptions key, or an explicit empty list, passes this check. The judgement of shortfalls is out of scope here and is the next criterion's.
        for key in ("pair", "constraint", "between", "accepted_mm", "reason", "bounded_by", "accepted_by", "accepted_on"):
            with self.subTest(key=key):
                self.assertFails(basis(entry(), entry(**{key: None})), f"accepted_exceptions[1].{key}", f"lacks {key}")

    def test_an_unknown_key_in_an_entry_fails_naming_it(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C1: An accepted_exceptions that is not a list, an entry lacking pair, constraint, between, accepted_mm, reason, bounded_by, accepted_by or accepted_on, an unknown key in an entry, a repeated key, a pair outside mains_to_low_voltage and mains_to_mains, a constraint outside clearance and creepage, a between that is not a list of two items each a pad or a net name, and an accepted_mm that is not a positive number each fail separation_basis naming the entry's position and the key. A record with no accepted_exceptions key, or an explicit empty list, passes this check. The judgement of shortfalls is out of scope here and is the next criterion's.
        for key in ("connector", "pitch_mm", "note"):
            with self.subTest(key=key):
                self.assertFails(basis(entry(**{key: 1})), f"accepted_exceptions[0].{key}", f"holds the key '{key}'")

    def test_a_key_given_twice_in_an_entry_fails_the_record_naming_the_key(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C1: An accepted_exceptions that is not a list, an entry lacking pair, constraint, between, accepted_mm, reason, bounded_by, accepted_by or accepted_on, an unknown key in an entry, a repeated key, a pair outside mains_to_low_voltage and mains_to_mains, a constraint outside clearance and creepage, a between that is not a list of two items each a pad or a net name, and an accepted_mm that is not a positive number each fail separation_basis naming the entry's position and the key. A record with no accepted_exceptions key, or an explicit empty list, passes this check. The judgement of shortfalls is out of scope here and is the next criterion's.
        text = ("accepted_by: maintainer\naccepted_on: 2026-10-05\nsynthetic: true\naccepted_exceptions:\n"
                "  - pair: mains_to_mains\n    pair: mains_to_low_voltage\n")
        signed, problems = read_text(text)
        self.assertIsNone(signed)
        self.assertTrue(any(v.rule == "separation_basis" and "more than once" in v.message and "'pair'" in v.message
                            for v in problems), [problem.line() for problem in problems])

    def test_a_pair_or_constraint_outside_the_closed_values_fails(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C1: An accepted_exceptions that is not a list, an entry lacking pair, constraint, between, accepted_mm, reason, bounded_by, accepted_by or accepted_on, an unknown key in an entry, a repeated key, a pair outside mains_to_low_voltage and mains_to_mains, a constraint outside clearance and creepage, a between that is not a list of two items each a pad or a net name, and an accepted_mm that is not a positive number each fail separation_basis naming the entry's position and the key. A record with no accepted_exceptions key, or an explicit empty list, passes this check. The judgement of shortfalls is out of scope here and is the next criterion's.
        for pair in ("low_voltage_to_low_voltage", "", None, 3):
            with self.subTest(pair=pair):
                self.assertFails(basis(entry(pair=pair if pair is not None else [])), "accepted_exceptions[0].pair", "where it is mains_to_low_voltage or mains_to_mains or same_connector_pins")
        for constraint in ("hole_to_hole", "Clearance", "", 3):
            with self.subTest(constraint=constraint):
                self.assertFails(basis(entry(constraint=constraint)), "accepted_exceptions[0].constraint", "where it is clearance or creepage")

    def test_a_between_that_is_not_a_list_of_two_items_each_naming_a_pad_or_net_fails(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C1: An accepted_exceptions that is not a list, an entry lacking pair, constraint, between, accepted_mm, reason, bounded_by, accepted_by or accepted_on, an unknown key in an entry, a repeated key, a pair outside mains_to_low_voltage and mains_to_mains, a constraint outside clearance and creepage, a between that is not a list of two items each a pad or a net name, and an accepted_mm that is not a positive number each fail separation_basis naming the entry's position and the key. A record with no accepted_exceptions key, or an explicit empty list, passes this check. The judgement of shortfalls is out of scope here and is the next criterion's.
        for bad in ("R1.2", ["R1.2"], ["R1.2", "J2.1", "J2.2"], [], {"a": "R1.2", "b": "J2.1"}):
            with self.subTest(bad=bad):
                self.assertFails(basis(entry(between=bad)), "accepted_exceptions[0].between", "list of two items")
        for bad in ("", "  ", 3, None, ["J2"]):
            with self.subTest(item=bad):
                self.assertFails(basis(entry(between=["R1.2", bad])), "accepted_exceptions[0].between[1]", "non-empty string")

    def test_an_accepted_distance_that_is_not_a_positive_number_fails(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C1: An accepted_exceptions that is not a list, an entry lacking pair, constraint, between, accepted_mm, reason, bounded_by, accepted_by or accepted_on, an unknown key in an entry, a repeated key, a pair outside mains_to_low_voltage and mains_to_mains, a constraint outside clearance and creepage, a between that is not a list of two items each a pad or a net name, and an accepted_mm that is not a positive number each fail separation_basis naming the entry's position and the key. A record with no accepted_exceptions key, or an explicit empty list, passes this check. The judgement of shortfalls is out of scope here and is the next criterion's.
        for bad in (0, -1.5, "13", True, float("nan"), float("inf"), [13]):
            with self.subTest(bad=bad):
                self.assertFails(basis(entry(accepted_mm=bad)), "accepted_exceptions[0].accepted_mm", "not a positive number")

    def test_an_entry_for_a_part_as_a_whole_without_a_pair_of_items_fails_the_reader(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C7: On a seeded layout with an entry for one pad pair of a part and a shortfall at the same part between a different pair of its pads, the first is reported as an accepted exception and the second fails as an ordinary violation naming its pads. An entry written for the part as a whole, without a pair, fails the record reader. Pairs of different parts are out of scope here.
        self.assertFails(basis(entry(between=["J2"])), "accepted_exceptions[0].between", "list of two items")
        self.assertFails(basis(entry(between=None)), "accepted_exceptions[0].between", "lacks between")


class AnAcceptedShortfallIsReportedAndNotFailed(unittest.TestCase):
    def test_a_creepage_shortfall_at_or_above_the_accepted_distance_is_accepted_with_its_line(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C2: On a seeded layout with the pair of items an entry's between lists closer than the signed figure but no closer than the entry's accepted_mm, the report holds a line naming the pair, the measured distance, the accepted distance and the owner's reason, and the design passes. The same holds for a mains_to_low_voltage creepage entry and a mains_to_mains clearance entry. Shortfalls between any other pair are out of scope and keep failing.
        reported = shortfall("creepage", LOW_VOLTAGE, 14.0, 13.19, "R1.2", "J2.1")
        judged = judge([reported], entry(accepted_mm=13.0))
        self.assertEqual(judged.violations, [])
        self.assertEqual(judged.consumed, {id(reported)})
        (line,) = judged.accepted
        self.assertTrue(line.startswith("ACCEPTED | "), line)
        for words in ("mains_to_low_voltage creepage", "R1.2 and J2.1", "measures 13.19 mm", "accepted down to 13 mm",
                      "signed 14 mm", "reason: a synthetic ground", "bounded by: a synthetic independent element",
                      "accepted_exceptions[0]"):
            self.assertIn(words, line)

    def test_a_clearance_shortfall_between_mains_to_mains_items_is_accepted_the_same_way(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C2: On a seeded layout with the pair of items an entry's between lists closer than the signed figure but no closer than the entry's accepted_mm, the report holds a line naming the pair, the measured distance, the accepted distance and the owner's reason, and the design passes. The same holds for a mains_to_low_voltage creepage entry and a mains_to_mains clearance entry. Shortfalls between any other pair are out of scope and keep failing.
        reported = shortfall("clearance", TERMINAL, 2.0, 1.84, "R1.2", "K1.1")
        judged = judge([reported], entry(pair="mains_to_mains", constraint="clearance", between=["K1.1", "R1.2"], accepted_mm=1.8))
        self.assertEqual(judged.violations, [])
        self.assertEqual(len(judged.accepted), 1)
        self.assertIn("mains_to_mains clearance", judged.accepted[0])
        self.assertIn("measures 1.84 mm", judged.accepted[0])

    def test_a_distance_exactly_the_accepted_one_is_accepted(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C2: On a seeded layout with the pair of items an entry's between lists closer than the signed figure but no closer than the entry's accepted_mm, the report holds a line naming the pair, the measured distance, the accepted distance and the owner's reason, and the design passes. The same holds for a mains_to_low_voltage creepage entry and a mains_to_mains clearance entry. Shortfalls between any other pair are out of scope and keep failing.
        reported = shortfall("creepage", LOW_VOLTAGE, 14.0, 13.0, "R1.2", "J2.1")
        self.assertEqual(judge([reported], entry(accepted_mm=13.0)).violations, [])

    def test_an_entry_between_nets_accepts_a_shortfall_between_any_items_on_those_nets_in_either_order(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C2: On a seeded layout with the pair of items an entry's between lists closer than the signed figure but no closer than the entry's accepted_mm, the report holds a line naming the pair, the measured distance, the accepted distance and the owner's reason, and the design passes. The same holds for a mains_to_low_voltage creepage entry and a mains_to_mains clearance entry. Shortfalls between any other pair are out of scope and keep failing.
        for between in (["/MAINS_N", "/LV_A"], ["/LV_A", "/MAINS_N"]):
            with self.subTest(between=between):
                judged = judge([shortfall("creepage", LOW_VOLTAGE, 14.0, 13.19, "R1.2", "J2.1")], entry(between=between))
                self.assertEqual((judged.violations, len(judged.accepted)), ([], 1))

    def test_a_report_that_lists_one_shortfall_twice_prints_it_once(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C2: On a seeded layout with the pair of items an entry's between lists closer than the signed figure but no closer than the entry's accepted_mm, the report holds a line naming the pair, the measured distance, the accepted distance and the owner's reason, and the design passes. The same holds for a mains_to_low_voltage creepage entry and a mains_to_mains clearance entry. Shortfalls between any other pair are out of scope and keep failing.
        twice = [shortfall("creepage", LOW_VOLTAGE, 14.0, 13.19, "R1.2", "J2.1") for _ in range(2)]
        judged = judge(twice, entry())
        self.assertEqual((judged.violations, len(judged.accepted)), ([], 1))
        self.assertEqual(judged.consumed, {id(item) for item in twice})


class AShortfallTheEntryDoesNotCoverFails(unittest.TestCase):
    def test_a_distance_below_the_accepted_one_fails_naming_the_entry_and_both_distances(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C3: A layout whose measured distance is below accepted_mm fails spacing_exception naming the entry and both distances. A shortfall between a pair with no entry, including another pair of the same part, for an entry of the other pair kind, or for the other constraint of the same pair fails as an ordinary violation, so an exception for one pair of a part's pads does not excuse another pair of them, nor an exception for creepage its clearance. Parts whose measured distance meets the signed figure are out of scope and never reported.
        reported = shortfall("creepage", LOW_VOLTAGE, 14.0, 12.9, "R1.2", "J2.1")
        judged = judge([reported], entry(accepted_mm=13.0))
        self.assertEqual(judged.accepted, [])
        (found,) = judged.violations
        self.assertEqual(found.rule, "spacing_exception")
        self.assertTrue(found.location.endswith("accepted_exceptions[0]"), found.location)
        for words in ("accepted_exceptions[0]", "R1.2 and J2.1", "down to 13 mm", "leaves 12.9 mm"):
            self.assertIn(words, found.message)
        self.assertEqual(judged.consumed, {id(reported)})

    def test_a_shortfall_between_a_pair_with_no_entry_is_left_an_ordinary_violation(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C3: A layout whose measured distance is below accepted_mm fails spacing_exception naming the entry and both distances. A shortfall between a pair with no entry, including another pair of the same part, for an entry of the other pair kind, or for the other constraint of the same pair fails as an ordinary violation, so an exception for one pair of a part's pads does not excuse another pair of them, nor an exception for creepage its clearance. Parts whose measured distance meets the signed figure are out of scope and never reported.
        other = shortfall("creepage", LOW_VOLTAGE, 14.0, 13.1, "K1.2", "J2.1")
        judged = judge([other], entry())
        self.assertEqual(judged.consumed, set())
        self.assertEqual(judged.accepted, [])
        self.assertEqual([found.rule for found in judged.violations], ["spacing_exception"])
        self.assertIn("reports no shortfall", judged.violations[0].message)

    def test_an_entry_of_the_other_pair_kind_or_the_other_constraint_excuses_nothing(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C3: A layout whose measured distance is below accepted_mm fails spacing_exception naming the entry and both distances. A shortfall between a pair with no entry, including another pair of the same part, for an entry of the other pair kind, or for the other constraint of the same pair fails as an ordinary violation, so an exception for one pair of a part's pads does not excuse another pair of them, nor an exception for creepage its clearance. Parts whose measured distance meets the signed figure are out of scope and never reported.
        reported = shortfall("creepage", LOW_VOLTAGE, 14.0, 13.19, "R1.2", "J2.1")
        for changes in ({"pair": "mains_to_mains"}, {"constraint": "clearance"}):
            with self.subTest(changes=changes):
                judged = judge([reported], entry(**changes))
                self.assertEqual((judged.accepted, judged.consumed), ([], set()))
                self.assertEqual([found.rule for found in judged.violations], ["spacing_exception"])

    def test_a_report_with_no_readable_distance_is_never_read_as_meeting_the_accepted_one(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C3: A layout whose measured distance is below accepted_mm fails spacing_exception naming the entry and both distances. A shortfall between a pair with no entry, including another pair of the same part, for an entry of the other pair kind, or for the other constraint of the same pair fails as an ordinary violation, so an exception for one pair of a part's pads does not excuse another pair of them, nor an exception for creepage its clearance. Parts whose measured distance meets the signed figure are out of scope and never reported.
        for tail in ("", "; actual -0.2000 mm", "; actual not a number mm"):
            description = f"Creepage violation (rule '{LOW_VOLTAGE}' creepage 14.0000 mm{tail})"
            with self.subTest(description=description):
                reported = shortfall("creepage", LOW_VOLTAGE, 14.0, 13.19, "R1.2", "J2.1")
                reported["description"] = description
                judged = judge([reported], entry(accepted_mm=13.0))
                self.assertEqual(judged.accepted, [])
                self.assertEqual([found.rule for found in judged.violations], ["spacing_exception"])

    def test_a_shortfall_under_a_rule_the_entries_do_not_name_is_never_excused(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C3: A layout whose measured distance is below accepted_mm fails spacing_exception naming the entry and both distances. A shortfall between a pair with no entry, including another pair of the same part, for an entry of the other pair kind, or for the other constraint of the same pair fails as an ordinary violation, so an exception for one pair of a part's pads does not excuse another pair of them, nor an exception for creepage its clearance. Parts whose measured distance meets the signed figure are out of scope and never reported.
        held = shortfall("creepage", f"{board_check.RESERVED}: net pair held at reinforced 1", 14.0, 13.19, "R1.2", "J2.1")
        judged = judge([held], entry())
        self.assertEqual((judged.accepted, judged.consumed), ([], set()))
        # and a violation that is not a spacing one at all, nor a shortfall between two items
        other = {"type": "track_dangling", "description": "Track has unconnected end", "items": [{"description": DESCRIBED["R1.2"]}]}
        self.assertEqual(judge([other], entry()).consumed, set())


class AnEntryThatIsNoAcceptanceFailsClosed(unittest.TestCase):
    REPORTED = [shortfall("creepage", LOW_VOLTAGE, 14.0, 13.19, "R1.2", "J2.1")]

    def failed(self, changes, words, **record):
        judged = judge(self.REPORTED, entry(**changes), **record)
        self.assertEqual(judged.accepted, [], "an entry that is no acceptance excused a shortfall")
        self.assertEqual(judged.consumed, set(), "the shortfall an entry that is no acceptance covers was consumed")
        (found,) = judged.violations
        self.assertEqual(found.rule, "spacing_exception")
        self.assertTrue(found.location.endswith("accepted_exceptions[0]"), found.location)
        self.assertIn("accepted_exceptions[0]", found.message)
        self.assertIn(words, found.message)

    def test_an_entry_signed_by_a_placeholder_or_nobody_fails(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C4: An entry whose accepted_by is a placeholder or empty, or whose accepted_on is invalid, later than the day of the run or later than the record's own accepted_on, fails; so does one whose accepted_mm is at or above the figure it relaxes, one naming a pad or net the layout lacks, and one that no reported shortfall uses. Each fails spacing_exception naming the entry, and an exception in an unsigned or synthetic-on-an-orderable-board record is never honoured. A signed entry used by a shortfall is out of scope here.
        for by in ("unsigned", "TBD", "<name>", "none", "placeholder", "", "   ", 7):
            with self.subTest(accepted_by=by):
                self.failed({"accepted_by": by}, "accepted_by")

    def test_an_entry_whose_date_is_invalid_or_after_today_or_after_the_records_fails(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C4: An entry whose accepted_by is a placeholder or empty, or whose accepted_on is invalid, later than the day of the run or later than the record's own accepted_on, fails; so does one whose accepted_mm is at or above the figure it relaxes, one naming a pad or net the layout lacks, and one that no reported shortfall uses. Each fails spacing_exception naming the entry, and an exception in an unsigned or synthetic-on-an-orderable-board record is never honoured. A signed entry used by a shortfall is out of scope here.
        for on, words in (("2026-13-40", "not a valid calendar date"), ("yesterday", "not a valid calendar date"), (None, "not a valid calendar date"),
                          ("2026-10-13", "later than today"), ("2026-10-06", "later than the record's own accepted_on 2026-10-05")):
            with self.subTest(accepted_on=on):
                self.failed({"accepted_on": on if on is not None else "n/a"}, words)

    def test_an_entry_dated_the_day_the_record_was_accepted_is_signed(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C4: An entry whose accepted_by is a placeholder or empty, or whose accepted_on is invalid, later than the day of the run or later than the record's own accepted_on, fails; so does one whose accepted_mm is at or above the figure it relaxes, one naming a pad or net the layout lacks, and one that no reported shortfall uses. Each fails spacing_exception naming the entry, and an exception in an unsigned or synthetic-on-an-orderable-board record is never honoured. A signed entry used by a shortfall is out of scope here.
        judged = judge(self.REPORTED, entry(accepted_on="2026-10-05"))
        self.assertEqual((judged.violations, len(judged.accepted)), ([], 1))

    def test_an_entry_accepting_a_distance_at_or_above_the_figure_it_relaxes_fails(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C4: An entry whose accepted_by is a placeholder or empty, or whose accepted_on is invalid, later than the day of the run or later than the record's own accepted_on, fails; so does one whose accepted_mm is at or above the figure it relaxes, one naming a pad or net the layout lacks, and one that no reported shortfall uses. Each fails spacing_exception naming the entry, and an exception in an unsigned or synthetic-on-an-orderable-board record is never honoured. A signed entry used by a shortfall is out of scope here.
        for accepted in (14.0, 14.5):
            with self.subTest(accepted_mm=accepted):
                self.failed({"accepted_mm": accepted}, "relaxes nothing")

    def test_an_entry_naming_a_pad_or_net_the_layout_lacks_fails_naming_it(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C4: An entry whose accepted_by is a placeholder or empty, or whose accepted_on is invalid, later than the day of the run or later than the record's own accepted_on, fails; so does one whose accepted_mm is at or above the figure it relaxes, one naming a pad or net the layout lacks, and one that no reported shortfall uses. Each fails spacing_exception naming the entry, and an exception in an unsigned or synthetic-on-an-orderable-board record is never honoured. A signed entry used by a shortfall is out of scope here.
        for between, absent in ((["R1.9", "J2.1"], "R1.9"), (["R1.2", "J9.1"], "J9.1"), (["R1.2", "/NO_SUCH_NET"], "/NO_SUCH_NET"),
                                (["R1", "J2.1"], "R1")):
            with self.subTest(between=between):
                self.failed({"between": between}, f"names {absent}, which the layout has neither as a pad")

    def test_an_entry_that_no_reported_shortfall_uses_fails(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C4: An entry whose accepted_by is a placeholder or empty, or whose accepted_on is invalid, later than the day of the run or later than the record's own accepted_on, fails; so does one whose accepted_mm is at or above the figure it relaxes, one naming a pad or net the layout lacks, and one that no reported shortfall uses. Each fails spacing_exception naming the entry, and an exception in an unsigned or synthetic-on-an-orderable-board record is never honoured. A signed entry used by a shortfall is out of scope here.
        judged = judge([], entry())
        self.assertEqual(judged.accepted, [])
        (found,) = judged.violations
        self.assertEqual(found.rule, "spacing_exception")
        self.assertIn("reports no shortfall", found.message)

    def test_an_entry_that_only_repeats_another_stays_unused(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C4: An entry whose accepted_by is a placeholder or empty, or whose accepted_on is invalid, later than the day of the run or later than the record's own accepted_on, fails; so does one whose accepted_mm is at or above the figure it relaxes, one naming a pad or net the layout lacks, and one that no reported shortfall uses. Each fails spacing_exception naming the entry, and an exception in an unsigned or synthetic-on-an-orderable-board record is never honoured. A signed entry used by a shortfall is out of scope here.
        judged = judge(self.REPORTED, entry(), entry(between=["/MAINS_N", "/LV_A"]))
        self.assertEqual(len(judged.accepted), 1)
        (found,) = judged.violations
        self.assertTrue(found.location.endswith("accepted_exceptions[1]"), found.location)

    def test_an_entry_in_an_unsigned_or_orderable_synthetic_record_is_never_read_as_one_to_honour(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C4: An entry whose accepted_by is a placeholder or empty, or whose accepted_on is invalid, later than the day of the run or later than the record's own accepted_on, fails; so does one whose accepted_mm is at or above the figure it relaxes, one naming a pad or net the layout lacks, and one that no reported shortfall uses. Each fails spacing_exception naming the entry, and an exception in an unsigned or synthetic-on-an-orderable-board record is never honoured. A signed entry used by a shortfall is out of scope here.
        for changes in ({"accepted_by": "unsigned"}, {"accepted_on": "2099-01-01"}, {"accepted_by": None}):
            with self.subTest(changes=changes):
                signed, problems = read(basis(entry(), **changes))
                self.assertIsNone(signed)
                self.assertTrue(any(v.rule == "separation_basis" for v in problems))
        import yaml
        with tempfile.TemporaryDirectory() as folder:
            os.makedirs(os.path.join(folder, os.path.dirname(RECORD)))
            with open(os.path.join(folder, RECORD), "w", encoding="utf-8") as handle:
                handle.write(yaml.safe_dump(basis(entry())))
            signed, problems = board_check.read_record(yaml, folder, DESIGN, RECORD, False, TODAY)
        self.assertIsNone(signed)
        self.assertTrue(any("marked synthetic" in v.message for v in problems))


class AnExceptionForOnePairDoesNotExcuseAnother(unittest.TestCase):
    def test_a_shortfall_between_another_pair_of_the_same_part_is_left_for_the_ordinary_violation(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C7: On a seeded layout with an entry for one pad pair of a part and a shortfall at the same part between a different pair of its pads, the first is reported as an accepted exception and the second fails as an ordinary violation naming its pads. An entry written for the part as a whole, without a pair, fails the record reader. Pairs of different parts are out of scope here.
        covered = shortfall("creepage", LOW_VOLTAGE, 14.0, 13.19, "R1.2", "J2.1")
        other = shortfall("creepage", LOW_VOLTAGE, 14.0, 13.4, "R1.2", "J2.2")
        judged = judge([covered, other], entry(between=["R1.2", "J2.1"]))
        self.assertEqual(judged.violations, [])
        self.assertEqual(len(judged.accepted), 1)
        self.assertIn("R1.2 and J2.1", judged.accepted[0])
        self.assertEqual(judged.consumed, {id(covered)})
        self.assertNotIn(id(other), judged.consumed)

    def test_a_pair_of_nets_entry_excuses_only_items_on_those_nets(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C7: On a seeded layout with an entry for one pad pair of a part and a shortfall at the same part between a different pair of its pads, the first is reported as an accepted exception and the second fails as an ordinary violation naming its pads. An entry written for the part as a whole, without a pair, fails the record reader. Pairs of different parts are out of scope here.
        covered = shortfall("creepage", LOW_VOLTAGE, 14.0, 13.19, "R1.2", "J2.1")
        other = shortfall("creepage", LOW_VOLTAGE, 14.0, 13.4, "R1.2", "J2.2")
        judged = judge([covered, other], entry(between=["/MAINS_N", "/LV_A"]))
        self.assertEqual(judged.consumed, {id(covered)})

    def test_an_entry_for_a_part_named_without_a_pad_names_nothing_of_the_layout(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C7: On a seeded layout with an entry for one pad pair of a part and a shortfall at the same part between a different pair of its pads, the first is reported as an accepted exception and the second fails as an ordinary violation naming its pads. An entry written for the part as a whole, without a pair, fails the record reader. Pairs of different parts are out of scope here.
        judged = judge([shortfall("creepage", LOW_VOLTAGE, 14.0, 13.19, "R1.2", "J2.1")], entry(between=["J2", "R1.2"]))
        self.assertEqual((judged.accepted, judged.consumed), ([], set()))
        self.assertIn("names J2, which the layout has neither as a pad", judged.violations[0].message)


#: A layout with a two-row header J5 at 2.0 mm pitch, a single-row header J6 at 2.54 mm pitch and a resistor R1, each pad on the
#: board where KiCad's report puts it.
HOLES = sexpr.parse_one(
    '(kicad_pcb'
    ' (footprint "J" (at 10 10) (property "Reference" "J5") (pad "1" thru_hole circle (at 0 0)) (pad "2" thru_hole circle (at 0 2))'
    ' (pad "3" thru_hole circle (at 2 0)) (pad "4" thru_hole circle (at 2 2)))'
    ' (footprint "J" (at 30 10) (property "Reference" "J6") (pad "1" thru_hole circle (at 0 0)) (pad "2" thru_hole circle (at 0 2.54)))'
    ' (footprint "R" (at 10 14) (property "Reference" "R1") (pad "1" thru_hole circle (at 0 0)) (pad "2" smd rect (at 2 0)))'
    ' (footprint "H" (at 50 10) (property "Reference" "H1") (pad "1" np_thru_hole circle (at 0 0)) (pad "2" np_thru_hole circle (at 2 0))))')
PADS = {"J5.1": (10.0, 10.0), "J5.2": (10.0, 12.0), "J5.3": (12.0, 10.0), "J5.4": (12.0, 12.0), "J6.1": (30.0, 10.0),
        "J6.2": (30.0, 12.54), "R1.1": (10.0, 14.0)}
PLATED = board_check.PLATED_HOLE_RULE


def hole_shortfall(figure: float, actual: float, first: str, second: str, rule: str = PLATED, moved: dict = None) -> dict:
    """One hole_to_hole violation as KiCad's JSON report writes it, between two of the pads above, each at `moved`'s place where it has one."""
    places = dict(PADS, **(moved or {}))
    items = []
    for name in (first, second):
        reference, pad = name.split(".")
        x, y = places[name]
        items.append({"description": f"PTH pad {pad} [/N_{name}] of {reference}", "pos": {"x": x, "y": y}})
    return {"type": "hole_to_hole", "severity": "error", "items": items,
            "description": f"Drilled hole too close to other hole (rule '{rule}' min {figure:.4f} mm; actual {actual:.4f} mm)"}


def connector_entry(**changes) -> dict:
    """A well-formed same_connector_pins entry, with `changes` set over it and a key set to None left out."""
    held = {"pair": "same_connector_pins", "constraint": "hole_to_hole", "connector": "J5", "pitch_mm": 2.0, "accepted_mm": 1.0,
            "reason": "a synthetic ground: slow signals only", "bounded_by": "a synthetic independent element",
            "accepted_by": "maintainer", "accepted_on": "2026-10-01"}
    held.update(changes)
    return {key: value for key, value in held.items() if value is not None}


def judge_holes(violations, *entries, **changes):
    signed, problems = read(basis(*entries, **changes))
    assert problems == [], [problem.line() for problem in problems]
    return board_check.judge_exceptions(DESIGN, RECORD, signed, violations, HOLES, TODAY)


class TheSameConnectorFormIsRead(unittest.TestCase):
    def assertFails(self, data: dict, location_end: str, words: str):
        signed, problems = read(data)
        self.assertIsNone(signed)
        self.assertTrue(any(v.rule == "separation_basis" and v.location.endswith(location_end) and words in v.message
                            for v in problems), [problem.line() for problem in problems])

    def test_a_well_formed_entry_is_read_beside_a_spacing_entry_and_kept(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C1: An entry with pair same_connector_pins that lacks connector, pitch_mm, accepted_mm, reason, bounded_by, accepted_by or accepted_on, that holds a between or any other key the decision does not name, that repeats a key, that has a constraint other than hole_to_hole, that has a connector which is not a reference designator, or that has a pitch_mm or accepted_mm which is not a positive number, fails separation_basis naming the entry's position and the key. Two entries naming the same connector fail likewise. A record with no such entry passes this check. The judgement of shortfalls is out of scope here and is the next criterion's.
        signed, problems = read(basis(entry(), connector_entry()))
        self.assertEqual(problems, [])
        self.assertEqual([found["pair"] for found in signed.exceptions], ["mains_to_low_voltage", "same_connector_pins"])
        self.assertEqual(signed.exceptions[1]["connector"], "J5")

    def test_an_entry_lacking_a_key_fails_naming_its_position_and_the_key(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C1: An entry with pair same_connector_pins that lacks connector, pitch_mm, accepted_mm, reason, bounded_by, accepted_by or accepted_on, that holds a between or any other key the decision does not name, that repeats a key, that has a constraint other than hole_to_hole, that has a connector which is not a reference designator, or that has a pitch_mm or accepted_mm which is not a positive number, fails separation_basis naming the entry's position and the key. Two entries naming the same connector fail likewise. A record with no such entry passes this check. The judgement of shortfalls is out of scope here and is the next criterion's.
        for key in board_check.SAME_CONNECTOR_KEYS:
            if key == "pair":
                continue
            with self.subTest(key=key):
                self.assertFails(basis(entry(), connector_entry(**{key: None})), f"accepted_exceptions[1].{key}", f"lacks {key}")

    def test_a_between_or_any_other_key_the_decision_does_not_name_fails_naming_it(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C1: An entry with pair same_connector_pins that lacks connector, pitch_mm, accepted_mm, reason, bounded_by, accepted_by or accepted_on, that holds a between or any other key the decision does not name, that repeats a key, that has a constraint other than hole_to_hole, that has a connector which is not a reference designator, or that has a pitch_mm or accepted_mm which is not a positive number, fails separation_basis naming the entry's position and the key. Two entries naming the same connector fail likewise. A record with no such entry passes this check. The judgement of shortfalls is out of scope here and is the next criterion's.
        for key, value in (("between", ["J5.1", "J5.2"]), ("note", "x"), ("net", "/A")):
            with self.subTest(key=key):
                self.assertFails(basis(connector_entry(**{key: value})), f"accepted_exceptions[0].{key}", f"holds the key '{key}'")

    def test_a_key_given_twice_in_an_entry_fails_the_record_naming_the_key(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C1: An entry with pair same_connector_pins that lacks connector, pitch_mm, accepted_mm, reason, bounded_by, accepted_by or accepted_on, that holds a between or any other key the decision does not name, that repeats a key, that has a constraint other than hole_to_hole, that has a connector which is not a reference designator, or that has a pitch_mm or accepted_mm which is not a positive number, fails separation_basis naming the entry's position and the key. Two entries naming the same connector fail likewise. A record with no such entry passes this check. The judgement of shortfalls is out of scope here and is the next criterion's.
        text = ("accepted_by: maintainer\naccepted_on: 2026-10-05\nsynthetic: true\naccepted_exceptions:\n"
                "  - pair: same_connector_pins\n    connector: J5\n    connector: J6\n")
        signed, problems = read_text(text)
        self.assertIsNone(signed)
        self.assertTrue(any(v.rule == "separation_basis" and "more than once" in v.message and "'connector'" in v.message
                            for v in problems), [problem.line() for problem in problems])

    def test_a_constraint_other_than_hole_to_hole_fails(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C1: An entry with pair same_connector_pins that lacks connector, pitch_mm, accepted_mm, reason, bounded_by, accepted_by or accepted_on, that holds a between or any other key the decision does not name, that repeats a key, that has a constraint other than hole_to_hole, that has a connector which is not a reference designator, or that has a pitch_mm or accepted_mm which is not a positive number, fails separation_basis naming the entry's position and the key. Two entries naming the same connector fail likewise. A record with no such entry passes this check. The judgement of shortfalls is out of scope here and is the next criterion's.
        for constraint in ("clearance", "creepage", "Hole_to_hole", "", 3):
            with self.subTest(constraint=constraint):
                self.assertFails(basis(connector_entry(constraint=constraint)), "accepted_exceptions[0].constraint", "where it is hole_to_hole")

    def test_a_connector_that_is_not_a_reference_designator_fails(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C1: An entry with pair same_connector_pins that lacks connector, pitch_mm, accepted_mm, reason, bounded_by, accepted_by or accepted_on, that holds a between or any other key the decision does not name, that repeats a key, that has a constraint other than hole_to_hole, that has a connector which is not a reference designator, or that has a pitch_mm or accepted_mm which is not a positive number, fails separation_basis naming the entry's position and the key. Two entries naming the same connector fail likewise. A record with no such entry passes this check. The judgement of shortfalls is out of scope here and is the next criterion's.
        for bad in ("", "J", "630", "J6 30", "J5.1", "J5\n", ["J5"], 5, True):
            with self.subTest(connector=bad):
                self.assertFails(basis(connector_entry(connector=bad)), "accepted_exceptions[0].connector", "reference designator of one connector")

    def test_a_pitch_or_an_accepted_distance_that_is_not_a_positive_number_fails(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C1: An entry with pair same_connector_pins that lacks connector, pitch_mm, accepted_mm, reason, bounded_by, accepted_by or accepted_on, that holds a between or any other key the decision does not name, that repeats a key, that has a constraint other than hole_to_hole, that has a connector which is not a reference designator, or that has a pitch_mm or accepted_mm which is not a positive number, fails separation_basis naming the entry's position and the key. Two entries naming the same connector fail likewise. A record with no such entry passes this check. The judgement of shortfalls is out of scope here and is the next criterion's.
        for key in ("pitch_mm", "accepted_mm"):
            for bad in (0, -2.0, "2.0", True, float("nan"), float("inf"), [2.0]):
                with self.subTest(key=key, bad=bad):
                    self.assertFails(basis(connector_entry(**{key: bad})), f"accepted_exceptions[0].{key}", "not a positive number")

    def test_two_entries_naming_the_same_connector_fail_at_the_second_naming_the_first(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C1: An entry with pair same_connector_pins that lacks connector, pitch_mm, accepted_mm, reason, bounded_by, accepted_by or accepted_on, that holds a between or any other key the decision does not name, that repeats a key, that has a constraint other than hole_to_hole, that has a connector which is not a reference designator, or that has a pitch_mm or accepted_mm which is not a positive number, fails separation_basis naming the entry's position and the key. Two entries naming the same connector fail likewise. A record with no such entry passes this check. The judgement of shortfalls is out of scope here and is the next criterion's.
        self.assertFails(basis(connector_entry(), connector_entry(pitch_mm=2.54)), "accepted_exceptions[1].connector",
                         "accepted_exceptions[0] names already")
        # the same connector named by a mains entry's between is no second entry of the form
        signed, problems = read(basis(entry(between=["J5.1", "J2.1"]), connector_entry()))
        self.assertEqual(problems, [])

    def test_a_reason_or_bound_that_is_blank_fails(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C1: An entry with pair same_connector_pins that lacks connector, pitch_mm, accepted_mm, reason, bounded_by, accepted_by or accepted_on, that holds a between or any other key the decision does not name, that repeats a key, that has a constraint other than hole_to_hole, that has a connector which is not a reference designator, or that has a pitch_mm or accepted_mm which is not a positive number, fails separation_basis naming the entry's position and the key. Two entries naming the same connector fail likewise. A record with no such entry passes this check. The judgement of shortfalls is out of scope here and is the next criterion's.
        for key in ("reason", "bounded_by"):
            with self.subTest(key=key):
                self.assertFails(basis(connector_entry(**{key: "  "})), f"accepted_exceptions[0].{key}", "non-empty string")

    def test_a_record_with_no_entry_of_the_form_passes_this_check(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C1: An entry with pair same_connector_pins that lacks connector, pitch_mm, accepted_mm, reason, bounded_by, accepted_by or accepted_on, that holds a between or any other key the decision does not name, that repeats a key, that has a constraint other than hole_to_hole, that has a connector which is not a reference designator, or that has a pitch_mm or accepted_mm which is not a positive number, fails separation_basis naming the entry's position and the key. Two entries naming the same connector fail likewise. A record with no such entry passes this check. The judgement of shortfalls is out of scope here and is the next criterion's.
        for data in (basis(), basis(entry()), basis(accepted_exceptions=None)):
            with self.subTest(keys=sorted(data)):
                signed, problems = read(data)
                self.assertEqual(problems, [])


class AShortfallOfTheEntrysConnectorAtItsPitchIsAccepted(unittest.TestCase):
    def test_a_shortfall_at_the_pitch_no_nearer_than_the_accepted_distance_is_accepted_with_its_line(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C2: On a synthetic design whose connector has two pads pitch_mm apart that the plated-hole spacing rule reports as a hole_to_hole shortfall, with an entry for that connector whose accepted_mm is no greater than the measured edge-to-edge distance, the check, matching centres to pitch_mm within 0.01 mm, reports no hole_to_hole violation for that pair; on a two-row connector a row-to-row pair at the same distance is accepted by the same entry and prints one accepted-exception line giving the connector, the pitch, the measured and accepted distances and the reason. Both the rule's report and the check's text report are read; no other output form exists. Shortfalls outside the entry are the next criterion's and out of scope here.
        reported = hole_shortfall(1.5, 1.0, "J5.1", "J5.2")
        judged = judge_holes([reported], connector_entry(accepted_mm=1.0))
        self.assertEqual(judged.violations, [])
        self.assertEqual(judged.consumed, {id(reported)})
        (line,) = judged.accepted
        self.assertTrue(line.startswith("ACCEPTED | "), line)
        for words in ("spacing_exception", "accepted_exceptions[0]", "connector J5", "2 mm pitch", "between J5.1 and J5.2",
                      "measures 1 mm", "accepted down to 1 mm", "plated-hole rule's 1.5 mm",
                      "reason: a synthetic ground: slow signals only", "bounded by: a synthetic independent element"):
            self.assertIn(words, line)

    def test_a_distance_above_the_accepted_one_is_accepted_too(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C2: On a synthetic design whose connector has two pads pitch_mm apart that the plated-hole spacing rule reports as a hole_to_hole shortfall, with an entry for that connector whose accepted_mm is no greater than the measured edge-to-edge distance, the check, matching centres to pitch_mm within 0.01 mm, reports no hole_to_hole violation for that pair; on a two-row connector a row-to-row pair at the same distance is accepted by the same entry and prints one accepted-exception line giving the connector, the pitch, the measured and accepted distances and the reason. Both the rule's report and the check's text report are read; no other output form exists. Shortfalls outside the entry are the next criterion's and out of scope here.
        judged = judge_holes([hole_shortfall(1.5, 1.4, "J5.1", "J5.2")], connector_entry(accepted_mm=1.0))
        self.assertEqual((judged.violations, len(judged.accepted)), ([], 1))

    def test_a_row_to_row_pair_at_the_same_distance_is_accepted_by_the_same_entry_with_a_line_of_its_own(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C2: On a synthetic design whose connector has two pads pitch_mm apart that the plated-hole spacing rule reports as a hole_to_hole shortfall, with an entry for that connector whose accepted_mm is no greater than the measured edge-to-edge distance, the check, matching centres to pitch_mm within 0.01 mm, reports no hole_to_hole violation for that pair; on a two-row connector a row-to-row pair at the same distance is accepted by the same entry and prints one accepted-exception line giving the connector, the pitch, the measured and accepted distances and the reason. Both the rule's report and the check's text report are read; no other output form exists. Shortfalls outside the entry are the next criterion's and out of scope here.
        reported = [hole_shortfall(1.5, 1.0, "J5.1", "J5.2"), hole_shortfall(1.5, 1.0, "J5.3", "J5.1"),
                    hole_shortfall(1.5, 1.0, "J5.2", "J5.4")]
        judged = judge_holes(reported, connector_entry(accepted_mm=1.0))
        self.assertEqual(judged.violations, [])
        self.assertEqual(judged.consumed, {id(item) for item in reported})
        self.assertEqual(len(judged.accepted), 3)
        self.assertEqual(sum("between J5.3 and J5.1" in line for line in judged.accepted), 1)
        self.assertEqual(sum("between J5.2 and J5.4" in line for line in judged.accepted), 1)

    def test_centres_within_a_hundredth_of_a_millimetre_of_the_pitch_match_and_no_further(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C2: On a synthetic design whose connector has two pads pitch_mm apart that the plated-hole spacing rule reports as a hole_to_hole shortfall, with an entry for that connector whose accepted_mm is no greater than the measured edge-to-edge distance, the check, matching centres to pitch_mm within 0.01 mm, reports no hole_to_hole violation for that pair; on a two-row connector a row-to-row pair at the same distance is accepted by the same entry and prints one accepted-exception line giving the connector, the pitch, the measured and accepted distances and the reason. Both the rule's report and the check's text report are read; no other output form exists. Shortfalls outside the entry are the next criterion's and out of scope here.
        for drift, accepted in ((0.0, True), (0.009, True), (-0.009, True), (0.0101, False), (-0.0101, False), (0.1, False)):
            with self.subTest(drift=drift):
                moved = {"J5.2": (10.0, 12.0 + drift)}
                judged = judge_holes([hole_shortfall(1.5, 1.0, "J5.1", "J5.2", moved=moved)],
                                     connector_entry(accepted_mm=1.0))
                self.assertEqual(len(judged.accepted), 1 if accepted else 0, drift)

    def test_either_order_of_the_two_items_in_the_report_is_matched(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C2: On a synthetic design whose connector has two pads pitch_mm apart that the plated-hole spacing rule reports as a hole_to_hole shortfall, with an entry for that connector whose accepted_mm is no greater than the measured edge-to-edge distance, the check, matching centres to pitch_mm within 0.01 mm, reports no hole_to_hole violation for that pair; on a two-row connector a row-to-row pair at the same distance is accepted by the same entry and prints one accepted-exception line giving the connector, the pitch, the measured and accepted distances and the reason. Both the rule's report and the check's text report are read; no other output form exists. Shortfalls outside the entry are the next criterion's and out of scope here.
        for first, second in (("J5.1", "J5.2"), ("J5.2", "J5.1")):
            with self.subTest(first=first):
                judged = judge_holes([hole_shortfall(1.5, 1.0, first, second)], connector_entry(accepted_mm=1.0))
                self.assertEqual((judged.violations, len(judged.accepted)), ([], 1))

    def test_a_report_that_lists_one_shortfall_twice_prints_it_once(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C2: On a synthetic design whose connector has two pads pitch_mm apart that the plated-hole spacing rule reports as a hole_to_hole shortfall, with an entry for that connector whose accepted_mm is no greater than the measured edge-to-edge distance, the check, matching centres to pitch_mm within 0.01 mm, reports no hole_to_hole violation for that pair; on a two-row connector a row-to-row pair at the same distance is accepted by the same entry and prints one accepted-exception line giving the connector, the pitch, the measured and accepted distances and the reason. Both the rule's report and the check's text report are read; no other output form exists. Shortfalls outside the entry are the next criterion's and out of scope here.
        twice = [hole_shortfall(1.5, 1.0, "J5.1", "J5.2") for _ in range(2)]
        judged = judge_holes(twice, connector_entry(accepted_mm=1.0))
        self.assertEqual((judged.violations, len(judged.accepted)), ([], 1))
        self.assertEqual(judged.consumed, {id(item) for item in twice})

    def test_a_connector_of_another_pitch_is_matched_at_its_own(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C2: On a synthetic design whose connector has two pads pitch_mm apart that the plated-hole spacing rule reports as a hole_to_hole shortfall, with an entry for that connector whose accepted_mm is no greater than the measured edge-to-edge distance, the check, matching centres to pitch_mm within 0.01 mm, reports no hole_to_hole violation for that pair; on a two-row connector a row-to-row pair at the same distance is accepted by the same entry and prints one accepted-exception line giving the connector, the pitch, the measured and accepted distances and the reason. Both the rule's report and the check's text report are read; no other output form exists. Shortfalls outside the entry are the next criterion's and out of scope here.
        judged = judge_holes([hole_shortfall(1.6, 1.54, "J6.1", "J6.2")], connector_entry(connector="J6", pitch_mm=2.54, accepted_mm=1.5))
        self.assertEqual((judged.violations, len(judged.accepted)), ([], 1))
        self.assertIn("2.54 mm pitch", judged.accepted[0])


class AHoleShortfallTheEntryDoesNotCoverFails(unittest.TestCase):
    def test_a_shortfall_at_another_centre_spacing_of_the_same_connector_is_left_an_ordinary_violation(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C3: On a synthetic design, a hole_to_hole shortfall fails, naming the two pads, when it lies between pads of the same connector at a centre spacing differing from the entry's pitch_mm by more than 0.01 mm, between pads of two different parts, for a connector with no entry, or at a measured distance below the entry's accepted_mm, the last also naming the entry. An entry for one connector does not excuse a shortfall of another. The judgement of the entry's own validity is the next criterion's and out of scope here.
        reported = hole_shortfall(1.5, 1.1, "J5.2", "J5.4", moved={"J5.4": (12.1, 12.0)})
        judged = judge_holes([reported, hole_shortfall(1.5, 1.0, "J5.1", "J5.2")], connector_entry(accepted_mm=1.0))
        self.assertEqual(judged.violations, [])
        self.assertNotIn(id(reported), judged.consumed)
        self.assertEqual(len(judged.accepted), 1)

    def test_a_shortfall_between_pads_of_two_different_parts_is_left_an_ordinary_violation(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C3: On a synthetic design, a hole_to_hole shortfall fails, naming the two pads, when it lies between pads of the same connector at a centre spacing differing from the entry's pitch_mm by more than 0.01 mm, between pads of two different parts, for a connector with no entry, or at a measured distance below the entry's accepted_mm, the last also naming the entry. An entry for one connector does not excuse a shortfall of another. The judgement of the entry's own validity is the next criterion's and out of scope here.
        reported = hole_shortfall(1.5, 1.0, "J5.1", "R1.1", moved={"R1.1": (10.0, 12.0)})
        judged = judge_holes([reported, hole_shortfall(1.5, 1.0, "J5.1", "J5.2")], connector_entry(accepted_mm=1.0))
        self.assertNotIn(id(reported), judged.consumed)
        self.assertEqual((judged.violations, len(judged.accepted)), ([], 1))

    def test_a_shortfall_of_a_connector_with_no_entry_is_left_an_ordinary_violation_and_one_connectors_entry_excuses_not_another(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C3: On a synthetic design, a hole_to_hole shortfall fails, naming the two pads, when it lies between pads of the same connector at a centre spacing differing from the entry's pitch_mm by more than 0.01 mm, between pads of two different parts, for a connector with no entry, or at a measured distance below the entry's accepted_mm, the last also naming the entry. An entry for one connector does not excuse a shortfall of another. The judgement of the entry's own validity is the next criterion's and out of scope here.
        elsewhere = hole_shortfall(1.5, 1.54, "J6.1", "J6.2")
        judged = judge_holes([elsewhere, hole_shortfall(1.5, 1.0, "J5.1", "J5.2")], connector_entry(accepted_mm=1.0))
        self.assertNotIn(id(elsewhere), judged.consumed)
        self.assertEqual((judged.violations, len(judged.accepted)), ([], 1))
        judged = judge_holes([elsewhere], connector_entry(accepted_mm=1.0))
        self.assertEqual(judged.consumed, set())

    def test_a_distance_below_the_accepted_one_fails_naming_the_entry_the_pads_and_both_distances(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C3: On a synthetic design, a hole_to_hole shortfall fails, naming the two pads, when it lies between pads of the same connector at a centre spacing differing from the entry's pitch_mm by more than 0.01 mm, between pads of two different parts, for a connector with no entry, or at a measured distance below the entry's accepted_mm, the last also naming the entry. An entry for one connector does not excuse a shortfall of another. The judgement of the entry's own validity is the next criterion's and out of scope here.
        reported = hole_shortfall(1.5, 0.9, "J5.1", "J5.2")
        judged = judge_holes([reported], connector_entry(accepted_mm=1.0))
        self.assertEqual(judged.accepted, [])
        (found,) = judged.violations
        self.assertEqual(found.rule, "spacing_exception")
        self.assertTrue(found.location.endswith("accepted_exceptions[0]"), found.location)
        for words in ("accepted_exceptions[0]", "connector J5", "J5.1 and J5.2", "down to 1 mm", "leaves 0.9 mm", "pad 1 [/N_J5.1] of J5"):
            self.assertIn(words, found.message)
        self.assertEqual(judged.consumed, {id(reported)})

    def test_a_shortfall_under_a_rule_other_than_the_plated_hole_rule_is_never_excused(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C3: On a synthetic design, a hole_to_hole shortfall fails, naming the two pads, when it lies between pads of the same connector at a centre spacing differing from the entry's pitch_mm by more than 0.01 mm, between pads of two different parts, for a connector with no entry, or at a measured distance below the entry's accepted_mm, the last also naming the entry. An entry for one connector does not excuse a shortfall of another. The judgement of the entry's own validity is the next criterion's and out of scope here.
        for rule in ("board setup", "Hole spacing", "plated hole spacing", ""):
            with self.subTest(rule=rule):
                judged = judge_holes([hole_shortfall(1.5, 1.0, "J5.1", "J5.2", rule=rule)], connector_entry(accepted_mm=1.0))
                self.assertEqual(judged.accepted, [])
                self.assertEqual(judged.consumed, set())

    def test_a_shortfall_with_no_readable_distance_is_never_read_as_meeting_the_accepted_one(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C3: On a synthetic design, a hole_to_hole shortfall fails, naming the two pads, when it lies between pads of the same connector at a centre spacing differing from the entry's pitch_mm by more than 0.01 mm, between pads of two different parts, for a connector with no entry, or at a measured distance below the entry's accepted_mm, the last also naming the entry. An entry for one connector does not excuse a shortfall of another. The judgement of the entry's own validity is the next criterion's and out of scope here.
        for tail in ("", "; actual -0.2000 mm", "; actual not a number mm"):
            with self.subTest(tail=tail):
                reported = hole_shortfall(1.5, 1.0, "J5.1", "J5.2")
                reported["description"] = f"Drilled hole too close to other hole (rule '{PLATED}' min 1.5000 mm{tail})"
                judged = judge_holes([reported], connector_entry(accepted_mm=1.0))
                self.assertEqual(judged.accepted, [])
                self.assertEqual([found.rule for found in judged.violations], ["spacing_exception"])

    def test_a_hole_shortfall_is_never_excused_by_a_spacing_entry_nor_a_spacing_shortfall_by_this_form(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C3: On a synthetic design, a hole_to_hole shortfall fails, naming the two pads, when it lies between pads of the same connector at a centre spacing differing from the entry's pitch_mm by more than 0.01 mm, between pads of two different parts, for a connector with no entry, or at a measured distance below the entry's accepted_mm, the last also naming the entry. An entry for one connector does not excuse a shortfall of another. The judgement of the entry's own validity is the next criterion's and out of scope here.
        reported = hole_shortfall(1.5, 1.0, "J5.1", "J5.2")
        judged = judge_holes([reported], entry(between=["J5.1", "J5.2"]))
        self.assertEqual((judged.accepted, judged.consumed), ([], set()))
        spacing = shortfall("creepage", LOW_VOLTAGE, 14.0, 13.19, "R1.2", "J2.1")
        spacing["items"] = [dict(hole_shortfall(1.5, 1.0, "J5.1", "J5.2")["items"][0]), dict(hole_shortfall(1.5, 1.0, "J5.1", "J5.2")["items"][1])]
        judged = judge_holes([spacing], connector_entry())
        self.assertEqual((judged.accepted, judged.consumed), ([], set()))


class AnEntryThatIsNoAcceptanceFailsClosedForTheSameConnector(unittest.TestCase):
    REPORTED = [hole_shortfall(1.5, 1.0, "J5.1", "J5.2")]

    def failed(self, changes, words, **record):
        judged = judge_holes(self.REPORTED, connector_entry(**changes), **record)
        self.assertEqual(judged.accepted, [], "an entry that is no acceptance excused a shortfall")
        self.assertEqual(judged.consumed, set(), "the shortfall an entry that is no acceptance covers was consumed")
        (found,) = judged.violations
        self.assertEqual(found.rule, "spacing_exception")
        self.assertTrue(found.location.endswith("accepted_exceptions[0]"), found.location)
        self.assertIn("accepted_exceptions[0]", found.message)
        self.assertIn(words, found.message)

    def test_an_entry_signed_by_a_placeholder_or_nobody_fails(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C4: An entry whose accepted_by is a placeholder or empty, whose accepted_on is invalid, later than the day of the run or later than the record's own accepted_on, whose accepted_mm is at or above the distance the plated-hole rule holds, whose connector the layout lacks or places without two pads pitch_mm apart, or which no reported shortfall uses, fails spacing_exception naming the entry. An entry in an unsigned or synthetic-on-an-orderable-board record is honoured for no shortfall. The pairs a valid entry accepts are the second criterion's and out of scope here.
        for by in ("unsigned", "TBD", "<name>", "none", "placeholder", "", "   ", 7):
            with self.subTest(accepted_by=by):
                self.failed({"accepted_by": by}, "accepted_by")

    def test_an_entry_whose_date_is_invalid_or_after_today_or_after_the_records_fails(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C4: An entry whose accepted_by is a placeholder or empty, whose accepted_on is invalid, later than the day of the run or later than the record's own accepted_on, whose accepted_mm is at or above the distance the plated-hole rule holds, whose connector the layout lacks or places without two pads pitch_mm apart, or which no reported shortfall uses, fails spacing_exception naming the entry. An entry in an unsigned or synthetic-on-an-orderable-board record is honoured for no shortfall. The pairs a valid entry accepts are the second criterion's and out of scope here.
        for on, words in (("2026-13-40", "not a valid calendar date"), ("yesterday", "not a valid calendar date"),
                          ("2026-10-13", "later than today"), ("2026-10-06", "later than the record's own accepted_on 2026-10-05")):
            with self.subTest(accepted_on=on):
                self.failed({"accepted_on": on}, words)

    def test_an_entry_accepting_a_distance_at_or_above_the_figure_the_rule_holds_fails(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C4: An entry whose accepted_by is a placeholder or empty, whose accepted_on is invalid, later than the day of the run or later than the record's own accepted_on, whose accepted_mm is at or above the distance the plated-hole rule holds, whose connector the layout lacks or places without two pads pitch_mm apart, or which no reported shortfall uses, fails spacing_exception naming the entry. An entry in an unsigned or synthetic-on-an-orderable-board record is honoured for no shortfall. The pairs a valid entry accepts are the second criterion's and out of scope here.
        for accepted in (1.5, 1.7):
            with self.subTest(accepted_mm=accepted):
                self.failed({"accepted_mm": accepted}, "relaxes nothing")

    def test_an_entry_for_a_connector_the_layout_lacks_fails_naming_it(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C4: An entry whose accepted_by is a placeholder or empty, whose accepted_on is invalid, later than the day of the run or later than the record's own accepted_on, whose accepted_mm is at or above the distance the plated-hole rule holds, whose connector the layout lacks or places without two pads pitch_mm apart, or which no reported shortfall uses, fails spacing_exception naming the entry. An entry in an unsigned or synthetic-on-an-orderable-board record is honoured for no shortfall. The pairs a valid entry accepts are the second criterion's and out of scope here.
        self.failed({"connector": "J9"}, "names the connector J9, which the layout lacks")

    def test_an_entry_for_a_connector_with_no_two_plated_pads_at_its_pitch_fails_naming_it(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C4: An entry whose accepted_by is a placeholder or empty, whose accepted_on is invalid, later than the day of the run or later than the record's own accepted_on, whose accepted_mm is at or above the distance the plated-hole rule holds, whose connector the layout lacks or places without two pads pitch_mm apart, or which no reported shortfall uses, fails spacing_exception naming the entry. An entry in an unsigned or synthetic-on-an-orderable-board record is honoured for no shortfall. The pairs a valid entry accepts are the second criterion's and out of scope here.
        for connector, pitch in (("J5", 2.5), ("J5", 2.02), ("J6", 2.0), ("R1", 2.0)):
            with self.subTest(connector=connector, pitch=pitch):
                judged = judge_holes([], connector_entry(connector=connector, pitch_mm=pitch))
                (found,) = judged.violations
                self.assertIn(f"names the connector {connector}, which the layout places without two plated pads {pitch:g} mm apart",
                              found.message)

    def test_a_connector_whose_pads_at_the_pitch_are_not_plated_through_holes_fails_naming_it(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C4: An entry whose accepted_by is a placeholder or empty, whose accepted_on is invalid, later than the day of the run or later than the record's own accepted_on, whose accepted_mm is at or above the distance the plated-hole rule holds, whose connector the layout lacks or places without two pads pitch_mm apart, or which no reported shortfall uses, fails spacing_exception naming the entry. An entry in an unsigned or synthetic-on-an-orderable-board record is honoured for no shortfall. The pairs a valid entry accepts are the second criterion's and out of scope here.
        judged = judge_holes([], connector_entry(connector="H1", pitch_mm=2.0))
        (found,) = judged.violations
        self.assertIn("names the connector H1, which the layout places without two plated pads 2 mm apart", found.message)
        self.assertEqual(judged.accepted, [])

    def test_two_shortfalls_of_one_entry_are_judged_against_the_larger_figure(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C4: An entry whose accepted_by is a placeholder or empty, whose accepted_on is invalid, later than the day of the run or later than the record's own accepted_on, whose accepted_mm is at or above the distance the plated-hole rule holds, whose connector the layout lacks or places without two pads pitch_mm apart, or which no reported shortfall uses, fails spacing_exception naming the entry. An entry in an unsigned or synthetic-on-an-orderable-board record is honoured for no shortfall. The pairs a valid entry accepts are the second criterion's and out of scope here.
        reported = [hole_shortfall(1.8, 1.95, "J5.1", "J5.2"), hole_shortfall(2.0, 1.95, "J5.3", "J5.4")]
        judged = judge_holes(reported, connector_entry(accepted_mm=1.9))
        self.assertEqual(judged.violations, [])
        self.assertEqual(len(judged.accepted), 2)
        judged = judge_holes(reported, connector_entry(accepted_mm=2.0))
        (found,) = judged.violations
        self.assertIn("relaxes nothing", found.message)
        self.assertIn("the 2 mm the plated-hole rule holds", found.message)

    def test_a_hole_shortfall_between_other_than_two_items_is_left_an_ordinary_violation(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C4: An entry whose accepted_by is a placeholder or empty, whose accepted_on is invalid, later than the day of the run or later than the record's own accepted_on, whose accepted_mm is at or above the distance the plated-hole rule holds, whose connector the layout lacks or places without two pads pitch_mm apart, or which no reported shortfall uses, fails spacing_exception naming the entry. An entry in an unsigned or synthetic-on-an-orderable-board record is honoured for no shortfall. The pairs a valid entry accepts are the second criterion's and out of scope here.
        whole = hole_shortfall(1.5, 1.0, "J5.1", "J5.2")
        third = hole_shortfall(1.5, 1.0, "J5.3", "J5.4")["items"][0]
        for items in (whole["items"][:1], whole["items"] + [third]):
            with self.subTest(items=len(items)):
                reported = [dict(whole, items=items)]
                judged = judge_holes(reported, connector_entry())
                self.assertEqual(judged.accepted, [])
                self.assertEqual(judged.consumed, set())
                (found,) = judged.violations
                self.assertIn("where the layout rule check reports no shortfall", found.message)
                self.assertEqual(board_check.reported_shortfalls(reported), [])

    def test_an_entry_that_no_reported_shortfall_uses_fails_and_an_entry_that_only_repeats_another_stays_unused(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C4: An entry whose accepted_by is a placeholder or empty, whose accepted_on is invalid, later than the day of the run or later than the record's own accepted_on, whose accepted_mm is at or above the distance the plated-hole rule holds, whose connector the layout lacks or places without two pads pitch_mm apart, or which no reported shortfall uses, fails spacing_exception naming the entry. An entry in an unsigned or synthetic-on-an-orderable-board record is honoured for no shortfall. The pairs a valid entry accepts are the second criterion's and out of scope here.
        judged = judge_holes([], connector_entry())
        self.assertEqual(judged.accepted, [])
        (found,) = judged.violations
        self.assertEqual(found.rule, "spacing_exception")
        self.assertIn("where the layout rule check reports no shortfall", found.message)
        judged = judge_holes([hole_shortfall(1.5, 1.0, "J5.1", "J5.2")], connector_entry(), connector_entry(connector="J6", pitch_mm=2.54))
        self.assertEqual(len(judged.accepted), 1)
        (found,) = judged.violations
        self.assertTrue(found.location.endswith("accepted_exceptions[1]"), found.location)

    def test_an_entry_dated_the_day_the_record_was_accepted_is_signed(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C4: An entry whose accepted_by is a placeholder or empty, whose accepted_on is invalid, later than the day of the run or later than the record's own accepted_on, whose accepted_mm is at or above the distance the plated-hole rule holds, whose connector the layout lacks or places without two pads pitch_mm apart, or which no reported shortfall uses, fails spacing_exception naming the entry. An entry in an unsigned or synthetic-on-an-orderable-board record is honoured for no shortfall. The pairs a valid entry accepts are the second criterion's and out of scope here.
        judged = judge_holes(self.REPORTED, connector_entry(accepted_on="2026-10-05"), connector_entry(connector="J6", pitch_mm=2.54, accepted_mm=1.0, accepted_on="2026-10-05"))
        self.assertEqual(len(judged.accepted), 1)

    def test_an_entry_in_an_unsigned_or_orderable_synthetic_record_is_never_read_as_one_to_honour(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C4: An entry whose accepted_by is a placeholder or empty, whose accepted_on is invalid, later than the day of the run or later than the record's own accepted_on, whose accepted_mm is at or above the distance the plated-hole rule holds, whose connector the layout lacks or places without two pads pitch_mm apart, or which no reported shortfall uses, fails spacing_exception naming the entry. An entry in an unsigned or synthetic-on-an-orderable-board record is honoured for no shortfall. The pairs a valid entry accepts are the second criterion's and out of scope here.
        for changes in ({"accepted_by": "unsigned"}, {"accepted_on": "2099-01-01"}, {"accepted_by": None}):
            with self.subTest(changes=changes):
                signed, problems = read(basis(connector_entry(), **changes))
                self.assertIsNone(signed)
                self.assertTrue(any(v.rule == "separation_basis" for v in problems))
        import yaml
        with tempfile.TemporaryDirectory() as folder:
            os.makedirs(os.path.join(folder, os.path.dirname(RECORD)))
            with open(os.path.join(folder, RECORD), "w", encoding="utf-8") as handle:
                handle.write(yaml.safe_dump(basis(connector_entry())))
            signed, problems = board_check.read_record(yaml, folder, DESIGN, RECORD, False, TODAY)
        self.assertIsNone(signed)
        self.assertTrue(any("marked synthetic" in v.message for v in problems))


class TheHardwareNotesStateTheExceptions(unittest.TestCase):
    NOTES = os.path.join(os.path.dirname(os.path.dirname(TOOLS)), "hardware", "README.md")

    def sections(self):
        with open(self.NOTES, encoding="utf-8") as handle:
            text = handle.read()
        (records,) = [line for line in text.splitlines() if line.startswith("- be held to a signed **separation basis record**")]
        rows = [line for line in text.splitlines() if line.startswith("| ")]
        adopter = text[text.index("## Re-deriving the separation basis"):]
        report = text[text.index("## The report"):]
        return records, rows, adopter, report

    def test_the_record_key_list_the_checks_table_and_the_adopter_section_state_the_exceptions(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C6: Every tracked design passes the check, in the build round for board changes and nightly on main. The hardware notes' record-key list, checks table and adopter section state accepted_exceptions, spacing_exception and the report line, and say that an exception is signed by the record's owner and that an adopter writes their own. The exceptions of the machine's own record are out of scope; the record leaf adds them.
        records, rows, adopter, report = self.sections()
        for words in ("accepted_exceptions", "`pair`", "`constraint`", "`between`", "`accepted_mm`", "`reason`", "`bounded_by`",
                      "`accepted_by` and `accepted_on`"):
            self.assertIn(words, records)
        (table,) = [row for row in rows if row.startswith("| `spacing_exception` |")]
        self.assertIn("accepted_exceptions", table)
        self.assertIn("is used by no reported shortfall", table)
        self.assertTrue(any(row.startswith("| Separation basis record |") and "accepted_exceptions" in row for row in rows))
        self.assertIn("ACCEPTED", report)
        self.assertIn("accepted_exceptions", adopter)
        self.assertIn("An exception is the owner's to sign and no one else's", adopter)
        self.assertIn("write your own", adopter.lower())

    def test_the_notes_state_the_same_connector_form_its_rule_name_its_report_line_and_who_signs_it(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C7: Every tracked design passes the check, in the build round for board changes and nightly on main. The hardware notes' record-key list and adopter section state the same_connector_pins entry form, spacing_exception for it and the report line, and say that the owner signs it and that an adopter writes their own. The item GROUND-5 in docs/board-design-method.md states, beside its passing condition, that a shortfall between pins of one connector at its own pitch passes only on the owner's signed exception, and leaves the item's figure and derivation as they are. The owner's acceptance of the record is out of scope here.
        records, rows, adopter, report = self.sections()
        for words in ("`same_connector_pins`", "`connector`", "`pitch_mm`", "`hole_to_hole`", "holds no `between`",
                      "owner's assertion, which the check does not test", "a second entry naming a connector an earlier one names"):
            self.assertIn(words, records)
        self.assertNotIn("is read by a later rule", records)
        (table,) = [row for row in rows if row.startswith("| `spacing_exception` |")]
        for words in ("`same_connector_pins` entry", "`Plated hole spacing`", "within 0.01 mm", "On a two-row connector a row-to-row pair",
                      "is used by no reported shortfall", "an `ACCEPTED` line naming the connector, the pitch"):
            self.assertIn(words, table)
        self.assertTrue(any(row.startswith("| Separation basis record |") and "`pitch_mm`" in row for row in rows))
        self.assertIn("`same_connector_pins` entry for that connector", adopter)
        self.assertIn("An exception is the owner's to sign and no one else's", adopter)
        self.assertIn("the check does not test your ground", adopter)

    def test_the_item_ground_5_states_the_exception_beside_its_passing_condition_and_keeps_its_figure(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C7: Every tracked design passes the check, in the build round for board changes and nightly on main. The hardware notes' record-key list and adopter section state the same_connector_pins entry form, spacing_exception for it and the report line, and say that the owner signs it and that an adopter writes their own. The item GROUND-5 in docs/board-design-method.md states, beside its passing condition, that a shortfall between pins of one connector at its own pitch passes only on the owner's signed exception, and leaves the item's figure and derivation as they are. The owner's acceptance of the record is out of scope here.
        with open(os.path.join(os.path.dirname(self.NOTES), "..", "docs", "board-design-method.md"), encoding="utf-8") as handle:
            text = handle.read()
        item = text[text.index("#### GROUND-5."):text.index("#### GROUND-5.") + text[text.index("#### GROUND-5."):].index("\n### ")]
        passes = item[item.index("- **Passes:**"):item.index("- **Fails, as the views show it:**")]
        self.assertIn("passes only on a `same_connector_pins` exception that the owner has signed", passes)
        self.assertIn("the rule, its figure and its derivation above stay as they are", passes)
        # the figure and its derivation are untouched
        self.assertIn("The figure is 0.70 + 0.50 + 0.25 = 1.45 mm", passes)
        self.assertIn("(constraint hole_to_hole (min <figure>mm))", passes)

    def test_every_rule_name_the_judgement_reports_is_in_the_checks_table(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SIGNED-SPACING-EXCEPTIONS.C6: Every tracked design passes the check, in the build round for board changes and nightly on main. The hardware notes' record-key list, checks table and adopter section state accepted_exceptions, spacing_exception and the report line, and say that an exception is signed by the record's owner and that an adopter writes their own. The exceptions of the machine's own record are out of scope; the record leaf adds them.
        _, rows, _, _ = self.sections()
        with open(os.path.join(TOOLS, "board_check.py"), encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn('"spacing_exception"', source)
        self.assertTrue(any(row.startswith("| `spacing_exception` |") for row in rows))


if __name__ == "__main__":
    unittest.main()
